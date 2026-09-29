"""AST-level obfuscation passes: flatten, rename, dead code, strings, numbers."""

import ast
import random


class Obfuscator:
    def __init__(self, rng=None, rename_params=False, dead_code=0, flatten=False):
        self.rng = rng or random.Random()
        self.rename_params = rename_params
        self.dead_code = dead_code
        self.flatten_enabled = flatten
        self.s_func = '_s'
        self.strings = []
        self.sentinel = '_sentinel'
        self.used = set()
        self._junk_words = (
            'initializing', 'syncing', 'caching', 'prefetching', 'warming',
            'refreshing', 'indexing', 'buffering', 'balancing', 'normalizing',
        )

    def fresh_name(self, prefix='_x'):
        while True:
            n = '%s%04x' % (prefix, self.rng.randrange(0x10000))
            if n not in self.used:
                self.used.add(n)
                return n

    def process(self, tree):
        self.strip_docstrings(tree)
        self.strip_annotations(tree)
        if self.flatten_enabled:
            self.flatten_pass(tree)
        self.rename_pass(tree)
        if self.dead_code > 0:
            self.deadcode_pass(tree)
        self.strings_pass(tree)
        self.numbers_pass(tree)
        ast.fix_missing_locations(tree)
        return tree

    def strip_docstrings(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    node.body = node.body[1:] or [ast.Pass()]

    def strip_annotations(self, tree):
        class _Strip(ast.NodeTransformer):
            def visit_arg(self, node):
                node.annotation = None
                return node

            def visit_AnnAssign(self, node):
                if node.value is None:
                    return ast.Pass()
                return ast.Assign(targets=[node.target], value=node.value)

            def visit_FunctionDef(self, node):
                node.returns = None
                self.generic_visit(node)
                return node

        _Strip().visit(tree)

    class _Blk:
        __slots__ = ('stmts', 'term', 'seq')

        def __init__(self, seq):
            self.stmts = []
            self.term = None
            self.seq = seq

    def flatten_pass(self, tree):
        fns = [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        fns.sort(key=lambda f: getattr(f, 'lineno', 0), reverse=True)
        for fn in fns:
            self._flatten_fn(fn)

    def _flatten_fn(self, fn):
        if isinstance(fn, ast.AsyncFunctionDef):
            return
        for n in ast.walk(fn):
            if isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await)):
                return
        if len(fn.body) < 3:
            return
        self._seq_counter = 0
        self._seq_map = {}
        state = self.fresh_name('_st_')
        self._flatten_state = state
        exit_blk = self._Blk(self._seq_counter)
        self._seq_map[exit_blk.seq] = exit_blk
        self._seq_counter += 1
        entry = self._cfg_seq(fn.body, None, exit_blk)
        fn.body = self._build_state_machine(entry, state)

    def _fin(self, cur, exit_blk):
        if cur.term is None and cur is not exit_blk:
            cur.term = ('jump', exit_blk)

    def _new_blk(self):
        b = self._Blk(self._seq_counter)
        self._seq_map[b.seq] = b
        self._seq_counter += 1
        return b

    def _cfg_seq(self, stmts, loop, exit_blk):
        head = self._new_blk()
        cur = head
        for s in stmts:
            if isinstance(s, ast.If):
                self._fin(cur, exit_blk)
                then_head = self._cfg_seq(s.body, loop, exit_blk)
                else_head = self._cfg_seq(s.orelse, loop, exit_blk) if s.orelse else None
                cb = self._new_blk()
                cb.stmts.append(self._mk_cond(s.test, then_head, else_head or exit_blk))
                cur.term = ('jump', cb)
                cur = exit_blk
            elif isinstance(s, ast.While):
                self._fin(cur, exit_blk)
                cb = self._new_blk()
                body_head = self._cfg_seq(s.body, {'break': exit_blk, 'continue': cb}, cb)
                cb.stmts.append(self._mk_cond(s.test, body_head, exit_blk))
                cur.term = ('jump', cb)
                cur = exit_blk
            elif isinstance(s, ast.For):
                self._fin(cur, exit_blk)
                it_blk = self._new_blk()
                it_var = self.fresh_name('_it_')
                it_blk.stmts.append(ast.Assign(
                    targets=[ast.Name(id=it_var, ctx=ast.Store())],
                    value=ast.Call(func=ast.Name(id='iter', ctx=ast.Load()), args=[s.iter], keywords=[])))
                nx_blk = self._new_blk()
                tmp = self.fresh_name('_nx_')
                nx_blk.stmts.append(ast.Assign(
                    targets=[ast.Name(id=tmp, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id='next', ctx=ast.Load()),
                        args=[ast.Name(id=it_var, ctx=ast.Load()),
                              ast.Name(id=self.sentinel, ctx=ast.Load())],
                        keywords=[])))
                body_head = self._cfg_seq(s.body, {'break': exit_blk, 'continue': nx_blk}, nx_blk)
                cmp = ast.Compare(
                    left=ast.Name(id=tmp, ctx=ast.Load()),
                    ops=[ast.Is()],
                    comparators=[ast.Name(id=self.sentinel, ctx=ast.Load())])
                nx_blk.stmts.append(self._mk_cond(cmp, exit_blk, body_head))
                target = s.target
                body_head.stmts.insert(0, ast.Assign(
                    targets=[target], value=ast.Name(id=tmp, ctx=ast.Load())))
                it_blk.term = ('jump', nx_blk)
                cur.term = ('jump', it_blk)
                cur = exit_blk
            elif isinstance(s, ast.Break):
                self._fin(cur, exit_blk)
                cur.term = ('jump', loop['break'] if loop else exit_blk)
                cur = exit_blk
            elif isinstance(s, ast.Continue):
                self._fin(cur, exit_blk)
                cur.term = ('jump', loop['continue'] if loop else exit_blk)
                cur = exit_blk
            elif isinstance(s, ast.Return):
                self._fin(cur, exit_blk)
                cur.stmts.append(s)
                cur.term = ('ret',)
                cur = exit_blk
            else:
                cur.stmts.append(s)
        self._fin(cur, exit_blk)
        return head

    def _mk_cond(self, test, then_blk, else_blk):
        return ast.If(
            test=test,
            body=[ast.Assign(targets=[ast.Name(id=self._flatten_state, ctx=ast.Store())],
                             value=ast.Constant(value=then_blk.seq))],
            orelse=[ast.Assign(targets=[ast.Name(id=self._flatten_state, ctx=ast.Store())],
                               value=ast.Constant(value=else_blk.seq))])

    def _build_state_machine(self, entry, state):
        self._flatten_state = state
        blocks = []
        seen = set()

        def collect(b):
            if id(b) in seen:
                return
            seen.add(id(b))
            blocks.append(b)
            if b.term and b.term[0] == 'jump':
                collect(b.term[1])
            for s in b.stmts:
                if isinstance(s, ast.If):
                    for br in (s.body, s.orelse):
                        for a in br:
                            if (isinstance(a, ast.Assign)
                                    and isinstance(a.value, ast.Constant)
                                    and isinstance(a.value.value, int)):
                                tgt = self._seq_map.get(a.value.value)
                                if tgt is not None:
                                    collect(tgt)

        collect(entry)
        id_map = {}
        for b in blocks:
            id_map[b.seq] = self.rng.randrange(0x1000, 0x7FFFFFFF)

        tail = None
        for b in reversed(blocks):
            stmts = []
            for s in b.stmts:
                stmts.append(self._map_cond_ids(s, state, id_map))
            if b.term and b.term[0] == 'jump':
                stmts.append(ast.Assign(
                    targets=[ast.Name(id=state, ctx=ast.Store())],
                    value=ast.Constant(value=id_map[b.term[1].seq])))
            else:
                stmts.append(ast.Break())
            cond = ast.Compare(
                left=ast.Name(id=state, ctx=ast.Load()),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=id_map[b.seq])])
            branch = ast.If(test=cond, body=stmts or [ast.Pass()],
                            orelse=[tail] if tail else [])
            tail = branch
        return [
            ast.Assign(targets=[ast.Name(id=state, ctx=ast.Store())],
                       value=ast.Constant(value=id_map[entry.seq])),
            ast.While(test=ast.Constant(value=True), body=[tail], orelse=[]),
        ]

    def _map_cond_ids(self, node, state, id_map):
        if isinstance(node, ast.If):
            for branch in (node.body, node.orelse):
                for i, s in enumerate(branch):
                    if (isinstance(s, ast.Assign) and len(s.targets) == 1
                            and isinstance(s.targets[0], ast.Name)
                            and s.targets[0].id == state
                            and isinstance(s.value, ast.Constant)
                            and isinstance(s.value.value, int)
                            and s.value.value in id_map):
                        branch[i] = ast.Assign(
                            targets=s.targets,
                            value=ast.Constant(value=id_map[s.value.value]))
        return node

    def rename_pass(self, tree):
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._rename_function(node, [])
            elif isinstance(node, ast.ClassDef):
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self._rename_function(m, [])

    def _rename_function(self, fn, outer_maps):
        local = set()
        self._collect_stores(fn, local)
        decl = set()
        for stmt in fn.body:
            if isinstance(stmt, (ast.Global, ast.Nonlocal)):
                decl.update(stmt.names)
        arg_names = {a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}
        if fn.args.vararg:
            arg_names.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            arg_names.add(fn.args.kwarg.arg)
        mapping = {}
        for name in sorted(local - decl):
            if name.startswith('__') or name in ('self', 'cls') or name == self.s_func:
                continue
            if not self.rename_params and name in arg_names:
                continue
            mapping[name] = self.fresh_name()
        maps = [mapping] + list(outer_maps)
        for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs:
            if a.arg in mapping:
                a.arg = mapping[a.arg]
        if fn.args.vararg and fn.args.vararg.arg in mapping:
            fn.args.vararg.arg = mapping[fn.args.vararg.arg]
        if fn.args.kwarg and fn.args.kwarg.arg in mapping:
            fn.args.kwarg.arg = mapping[fn.args.kwarg.arg]
        for d in fn.args.defaults:
            self._rename_expr(d, outer_maps)
        for d in fn.args.kw_defaults:
            if d is not None:
                self._rename_expr(d, outer_maps)
        for dec in fn.decorator_list:
            self._rename_expr(dec, outer_maps)
        for stmt in fn.body:
            self._rename_stmt(stmt, maps)

    def _collect_stores(self, fn, out):
        for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs:
            out.add(a.arg)
        if fn.args.vararg:
            out.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            out.add(fn.args.kwarg.arg)
        for stmt in fn.body:
            self._collect_stmt(stmt, out)

    def _collect_stmt(self, node, out):
        n = type(node)
        if n in (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda):
            if n is not ast.Lambda:
                out.add(node.name)
            return
        if n in (ast.Global, ast.Nonlocal):
            return
        for child in ast.iter_child_nodes(node):
            self._collect_stmt(child, out)

    def _lookup(self, name, maps):
        for m in maps:
            if name in m:
                return m[name]
        return None

    def _rename_expr(self, node, maps):
        if node is None:
            return
        if isinstance(node, ast.Lambda):
            self._rename_lambda(node, maps)
            return
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                new = self._lookup(node.id, maps)
                if new:
                    node.id = new
            elif isinstance(node.ctx, ast.Store):
                if maps and node.id in maps[0]:
                    node.id = maps[0][node.id]
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            self._rename_comp_expr(node, maps)
            return
        for child in ast.iter_child_nodes(node):
            self._rename_expr(child, maps)

    def _rename_comp_expr(self, node, maps):
        cur_maps = maps
        for g in node.generators:
            cur_maps = self._rename_comp_gen(g, cur_maps)
        if isinstance(node, ast.DictComp):
            self._rename_expr(node.key, cur_maps)
            self._rename_expr(node.value, cur_maps)
        else:
            self._rename_expr(node.elt, cur_maps)

    def _rename_stmt(self, node, maps):
        n = type(node)
        if n in (ast.FunctionDef, ast.AsyncFunctionDef):
            self._rename_function(node, maps)
            return
        if n is ast.ClassDef:
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._rename_function(m, maps)
                else:
                    self._rename_stmt(m, maps)
            for base in node.bases + [k.value for k in node.keywords]:
                self._rename_expr(base, maps)
            for dec in node.decorator_list:
                self._rename_expr(dec, maps)
            return
        if n is ast.Lambda:
            self._rename_lambda(node, maps)
            return
        if n in (ast.Global, ast.Nonlocal):
            return
        self._rename_expr(node, maps)

    def _rename_lambda(self, lm, maps):
        args = [a.arg for a in lm.args.posonlyargs + lm.args.args + lm.args.kwonlyargs]
        if lm.args.vararg:
            args.append(lm.args.vararg.arg)
        if lm.args.kwarg:
            args.append(lm.args.kwarg.arg)
        mapping = {}
        for name in args:
            if name.startswith('__') or name in ('self', 'cls'):
                continue
            mapping[name] = self.fresh_name()
        for a in lm.args.posonlyargs + lm.args.args + lm.args.kwonlyargs:
            if a.arg in mapping:
                a.arg = mapping[a.arg]
        if lm.args.vararg and lm.args.vararg.arg in mapping:
            lm.args.vararg.arg = mapping[lm.args.vararg.arg]
        if lm.args.kwarg and lm.args.kwarg.arg in mapping:
            lm.args.kwarg.arg = mapping[lm.args.kwarg.arg]
        for d in lm.args.defaults:
            self._rename_expr(d, maps)
        self._rename_expr(lm.body, [mapping] + list(maps))

    def _rename_comp_gen(self, comp, maps):
        targets = []
        for t in (comp.target.elts if isinstance(comp.target, (ast.Tuple, ast.List)) else [comp.target]):
            if isinstance(t, ast.Name):
                targets.append(t)
        own = {}
        for t in targets:
            own[t.id] = self.fresh_name()
            t.id = own[t.id]
        self._rename_expr(comp.iter, maps)
        comp_maps = [own] + list(maps)
        for cond in comp.ifs:
            self._rename_expr(cond, comp_maps)
        return comp_maps

    def deadcode_pass(self, tree):
        class _Dead(ast.NodeTransformer):
            def __init__(self, obf):
                self.obf = obf

            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                self.obf._insert_junk(node.body, 3)
                return node

            def visit_Module(self, node):
                self.generic_visit(node)
                self.obf._insert_junk(node.body, 2)
                return node

        _Dead(self).visit(tree)

    def _insert_junk(self, body, cap):
        if len(body) < 4:
            return
        if any(isinstance(n, (ast.Yield, ast.YieldFrom))
               for n in ast.walk(ast.Module(body=body, type_ignores=[]))):
            return
        n = min(cap, 1 + self.rng.randrange(3))
        for _ in range(n):
            pos = self.rng.randrange(len(body))
            cond = self._opaque_true()
            val = self._junk_value()
            var = self.fresh_name('_j_')
            junk = ast.If(test=cond,
                          body=[ast.Assign(targets=[ast.Name(id=var, ctx=ast.Store())], value=val)],
                          orelse=[])
            body.insert(pos, junk)

    def _opaque_true(self):
        a = self.rng.randrange(2, 40)
        c = self.rng.randrange(2, 20)
        d = self.rng.randrange(-50, 50)
        lhs = ast.BinOp(left=ast.BinOp(left=ast.Constant(value=a), op=ast.Mult(),
                                       right=ast.Constant(value=c)),
                        op=ast.Add(), right=ast.Constant(value=d))
        rhs = ast.BinOp(left=ast.BinOp(left=ast.Constant(value=a), op=ast.Mult(),
                                       right=ast.Constant(value=c)),
                        op=ast.Add(), right=ast.Constant(value=d))
        return ast.Compare(left=lhs, ops=[ast.Eq()], comparators=[rhs])

    def _junk_value(self):
        if self.rng.random() < 0.4 and self.s_func:
            idx = len(self.strings)
            self.strings.append(self.rng.choice(self._junk_words) + '-' + self.fresh_name('_w_')[1:])
            return ast.Call(func=ast.Name(id=self.s_func, ctx=ast.Load()),
                            args=[ast.Constant(value=idx)], keywords=[])
        a = self.rng.randrange(3, 60)
        b = self.rng.randrange(3, 60)
        c = self.rng.randrange(1, 100)
        return ast.BinOp(
            left=ast.BinOp(left=ast.Constant(value=a), op=ast.BitXor(), right=ast.Constant(value=b)),
            op=ast.Add(), right=ast.Constant(value=c))

    def strings_pass(self, tree):
        class _StrEnc(ast.NodeTransformer):
            def __init__(self, obf):
                self.obf = obf

            def visit_Constant(self, node):
                if isinstance(node.value, str):
                    idx = len(self.obf.strings)
                    self.obf.strings.append(node.value)
                    call = ast.Call(
                        func=ast.Name(id=self.obf.s_func, ctx=ast.Load()),
                        args=[ast.Constant(value=idx)], keywords=[])
                    ast.copy_location(call, node)
                    return call
                return node

            def visit_JoinedStr(self, node):
                node.values = [self.visit(v) if isinstance(v, ast.FormattedValue) else v
                               for v in node.values]
                return node

        _StrEnc(self).visit(tree)

    def numbers_pass(self, tree):
        class _NumEnc(ast.NodeTransformer):
            def __init__(self, obf):
                self.obf = obf

            def visit_Constant(self, node):
                if (isinstance(node.value, int) and not isinstance(node.value, bool)
                        and abs(node.value) >= 2 and abs(node.value) < 2 ** 31
                        and self.obf.rng.random() < 0.75):
                    e = self.obf._int_expr(abs(node.value))
                    if node.value < 0:
                        e = ast.UnaryOp(op=ast.USub(), operand=e)
                    ast.copy_location(e, node)
                    return e
                return node

        _NumEnc(self).visit(tree)

    def _int_expr(self, v):
        mode = self.rng.random()
        if mode < 0.35:
            a = self.rng.randrange(3, 13)
            b = self.rng.randrange(3, 17)
            c = v - a * b
            e = ast.BinOp(
                left=ast.BinOp(left=ast.Constant(value=a), op=ast.Mult(), right=ast.Constant(value=b)),
                op=ast.Add(), right=ast.Constant(value=c))
        elif mode < 0.6:
            a = self.rng.randrange(3, 15)
            b = self.rng.randrange(3, 15)
            d = self.rng.randrange(-9, 10)
            c = (v - d) ^ (a * b)
            e = ast.BinOp(
                left=ast.BinOp(
                    left=ast.BinOp(left=ast.Constant(value=a), op=ast.Mult(), right=ast.Constant(value=b)),
                    op=ast.BitXor(), right=ast.Constant(value=c)),
                op=ast.Add(), right=ast.Constant(value=d))
        elif mode < 0.8:
            m = self.rng.randrange(0x1000, 0x7FFFFFFF)
            e = ast.BinOp(left=ast.Constant(value=v ^ m), op=ast.BitXor(),
                          right=ast.Constant(value=m))
        else:
            m = self.rng.randrange(0x1000, 0xFFFFFFF)
            e = ast.BinOp(
                left=ast.BinOp(left=ast.Constant(value=v & m), op=ast.BitAnd(),
                               right=ast.Constant(value=m)),
                op=ast.Add(),
                right=ast.BinOp(left=ast.Constant(value=v & ~m), op=ast.BitAnd(),
                                right=ast.Constant(value=~m)))
        if self.rng.random() < 0.4:
            inner = e
            outer = self.rng.randrange(0x10, 0xFFFF)
            e = ast.BinOp(
                left=ast.BinOp(left=inner, op=ast.BitXor(), right=ast.Constant(value=outer)),
                op=ast.BitXor(), right=ast.Constant(value=outer))
        return e
