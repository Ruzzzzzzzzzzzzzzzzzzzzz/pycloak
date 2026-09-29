"""Compile a plain Python function into PyCloak custom-VM bytecode."""

import ast

from .vm_opcodes import OP, CMP, BINOP_MAP, UNARY_MAP


class VMUnsupported(Exception):
    pass


_OPNAME = {
    ast.Eq: '==', ast.NotEq: '!=', ast.Lt: '<', ast.LtE: '<=',
    ast.Gt: '>', ast.GtE: '>=', ast.In: 'in', ast.NotIn: 'not in',
    ast.Is: 'is', ast.IsNot: 'is not',
}


class _Compiler:
    def __init__(self, fn):
        self.fn = fn
        self.code = bytearray()
        self.consts = []
        self.names = []
        self.strtab = []
        self.args = [a.arg for a in fn.args.posonlyargs + fn.args.args]
        self.defaults = [None] * len(self.args)
        self.vars = {}
        self.globals_decl = set()
        self.loops = []
        self._next_slot = 0

    def prepare(self):
        fn = self.fn
        if fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs:
            raise VMUnsupported('varargs/kwonly args')
        if fn.decorator_list:
            raise VMUnsupported('decorators')
        ndef = len(fn.args.defaults)
        for i, d in enumerate(fn.args.defaults):
            if not isinstance(d, ast.Constant):
                raise VMUnsupported('non-literal default arg')
            self.defaults[len(self.args) - ndef + i] = d.value
        self._scan(fn)

    def _scan(self, fn):
        stores = set()
        nonlocal_seen = False
        for node in ast.walk(fn):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and node is not fn:
                raise VMUnsupported('nested function')
            if isinstance(node, (ast.ClassDef,)):
                raise VMUnsupported('nested class')
            if isinstance(node, ast.Nonlocal):
                nonlocal_seen = True
            if isinstance(node, ast.Global):
                self.globals_decl.update(node.names)
        if nonlocal_seen:
            raise VMUnsupported('nonlocal (closure access)')
        for name in self.args:
            stores.add(name)
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                stores.add(node.id)
            elif isinstance(node, ast.comprehension):
                for t in node.target.elts if isinstance(node.target, (ast.Tuple, ast.List)) else [node.target]:
                    if isinstance(t, ast.Name):
                        stores.add(t.id)
            elif isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
                stores.add(node.target.id)
            elif isinstance(node, ast.arg):
                pass
        stores -= self.globals_decl
        for name in self.args:
            self.vars[name] = self._alloc()
        for name in sorted(stores - set(self.args)):
            self.vars[name] = self._alloc()

    def _alloc(self):
        s = self._next_slot
        self._next_slot += 1
        return s

    def tmp_slot(self):
        return self._alloc()

    def emit(self, op, arg=0):
        self.code += bytes((op, (arg >> 8) & 0xFF, arg & 0xFF))

    def here(self):
        return len(self.code) // 3

    def jump(self, op):
        pos = self.here()
        self.emit(op, 0)
        return pos

    def patch(self, pos, target):
        off = target - (pos + 1)
        if not -32768 <= off <= 32767:
            raise VMUnsupported('jump offset out of range (function too large)')
        self.code[pos * 3 + 1] = (off >> 8) & 0xFF
        self.code[pos * 3 + 2] = off & 0xFF

    def const_idx(self, v):
        for i, c in enumerate(self.consts):
            if type(c) is type(v) and c == v:
                return i
        self.consts.append(v)
        return len(self.consts) - 1

    def name_idx(self, s):
        for i, n in enumerate(self.names):
            if n == s:
                return i
        if len(self.names) >= 256:
            raise VMUnsupported('too many global/attr names')
        self.names.append(s)
        return len(self.names) - 1

    def str_idx(self, s):
        for i, n in enumerate(self.strtab):
            if n == s:
                return i
        self.strtab.append(s)
        return len(self.strtab) - 1

    def load_name(self, name):
        if name in self.globals_decl or name not in self.vars:
            self.emit(OP['LOAD_GLOBAL'], self.name_idx(name))
        else:
            self.emit(OP['LOAD_FAST'], self.vars[name])

    def store_name(self, name):
        if name in self.globals_decl:
            self.emit(OP['STORE_GLOBAL'], self.name_idx(name))
        else:
            self.emit(OP['STORE_FAST'], self.vars[name])

    def compile_stmts(self, body):
        for s in body:
            self.stmt(s)

    def compile_body(self, body):
        self.compile_stmts(body)
        self.emit(OP['LOAD_NONE'])
        self.emit(OP['RETURN_VALUE'])

    def stmt(self, s):
        n = type(s)
        if n is ast.Expr:
            self.expr(s.value)
            self.emit(OP['POP_TOP'])
        elif n is ast.Pass:
            self.emit(OP['NOP'])
        elif n is ast.Assign:
            self.expr(s.value)
            for i, t in enumerate(s.targets):
                if i < len(s.targets) - 1:
                    self.emit(OP['DUP_TOP'])
                self.assign_target(t)
        elif n is ast.AnnAssign:
            if s.value is None:
                raise VMUnsupported('bare AnnAssign')
            self.expr(s.value)
            self.assign_target(s.target)
        elif n is ast.AugAssign:
            self.augassign(s)
        elif n is ast.Return:
            if s.value is None:
                self.emit(OP['LOAD_NONE'])
            else:
                self.expr(s.value)
            self.emit(OP['RETURN_VALUE'])
        elif n is ast.If:
            self.expr(s.test)
            jf = self.jump(OP['POP_JUMP_IF_FALSE'])
            self.compile_stmts(s.body)
            if s.orelse:
                je = self.jump(OP['JUMP'])
                self.patch(jf, self.here())
                self.compile_stmts(s.orelse)
                self.patch(je, self.here())
            else:
                self.patch(jf, self.here())
        elif n is ast.While:
            cond = self.here()
            self.expr(s.test)
            jf = self.jump(OP['POP_JUMP_IF_FALSE'])
            self.loops.append({'breaks': [], 'continues': []})
            self.compile_stmts(s.body)
            loop = self.loops.pop()
            jb = self.jump(OP['JUMP'])
            self.patch(jb, cond)
            end = self.here()
            for p in loop['continues']:
                self.patch(p, cond)
            for p in loop['breaks']:
                self.patch(p, end)
            self.patch(jf, end)
        elif n is ast.For:
            self.expr(s.iter)
            self.emit(OP['GET_ITER'])
            fit = self.here()
            jf = self.jump(OP['FOR_ITER'])
            self.assign_target(s.target)
            self.loops.append({'breaks': [], 'continues': []})
            self.compile_stmts(s.body)
            loop = self.loops.pop()
            jb = self.jump(OP['JUMP'])
            self.patch(jb, fit)
            end = self.here()
            for p in loop['continues']:
                self.patch(p, fit)
            for p in loop['breaks']:
                self.emit(OP['POP_TOP'])
                self.patch(p, self.here())
            self.patch(jf, end)
        elif n is ast.Break:
            if not self.loops:
                raise VMUnsupported('break outside loop')
            self.loops[-1]['breaks'].append(self.jump(OP['JUMP']))
        elif n is ast.Continue:
            if not self.loops:
                raise VMUnsupported('continue outside loop')
            self.loops[-1]['continues'].append(self.jump(OP['JUMP']))
        elif n is ast.Import:
            for alias in s.names:
                self.emit(OP['IMPORT_NAME'], self.name_idx(alias.name))
                self.store_name(alias.asname or alias.name.split('.')[0])
        elif n is ast.ImportFrom:
            if s.level or s.module is None:
                raise VMUnsupported('relative import')
            for alias in s.names:
                if alias.name == '*':
                    raise VMUnsupported('star import')
                self.emit(OP['IMPORT_NAME'], self.name_idx(s.module))
                self.emit(OP['IMPORT_FROM'], self.name_idx(alias.name))
                self.store_name(alias.asname or alias.name)
        elif n is ast.Global:
            pass
        elif n is ast.Assert:
            end = self.jump(OP['POP_JUMP_IF_TRUE'])
            if s.msg is not None:
                self.expr(s.msg)
            else:
                self.emit(OP['LOAD_NONE'])
            self.emit(OP['LOAD_GLOBAL'], self.name_idx('AssertionError'))
            self.emit(OP['RAISE'])
            self.patch(end, self.here())
        else:
            raise VMUnsupported(type(s).__name__)

    def assign_target(self, t):
        if isinstance(t, ast.Name):
            self.store_name(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            self.emit(OP['UNPACK_SEQUENCE'], len(t.elts))
            for e in reversed(t.elts):
                self.assign_target(e)
        elif isinstance(t, ast.Attribute):
            self.expr(t.value)
            self.emit(OP['STORE_ATTR'], self.name_idx(t.attr))
        elif isinstance(t, ast.Subscript):
            self.expr(t.value)
            self.expr(t.slice)
            self.emit(OP['STORE_SUBSCR'])
        else:
            raise VMUnsupported('assign target %s' % type(t).__name__)

    def augassign(self, s):
        op = BINOP_MAP.get(type(s.op).__name__)
        if op is None:
            raise VMUnsupported('augmented op %s' % type(s.op).__name__)
        t = s.target
        if isinstance(t, ast.Name):
            self.load_name(t.id)
            self.expr(s.value)
            self.emit(op)
            self.store_name(t.id)
        elif isinstance(t, ast.Attribute):
            tmp = self.tmp_slot()
            self.expr(t.value)
            self.emit(OP['STORE_FAST'], tmp)
            self.emit(OP['LOAD_FAST'], tmp)
            self.emit(OP['LOAD_ATTR'], self.name_idx(t.attr))
            self.expr(s.value)
            self.emit(op)
            self.emit(OP['LOAD_FAST'], tmp)
            self.emit(OP['STORE_ATTR'], self.name_idx(t.attr))
        elif isinstance(t, ast.Subscript):
            tmp = self.tmp_slot()
            self.expr(t.value)
            self.emit(OP['STORE_FAST'], tmp)
            self.emit(OP['LOAD_FAST'], tmp)
            self.expr(t.slice)
            self.emit(OP['LOAD_SUBSCR'])
            self.expr(s.value)
            self.emit(op)
            self.emit(OP['LOAD_FAST'], tmp)
            self.expr(t.slice)
            self.emit(OP['STORE_SUBSCR'])
        else:
            raise VMUnsupported('augassign target %s' % type(t).__name__)

    def expr(self, e):
        n = type(e)
        if n is ast.Constant:
            v = e.value
            if v is None:
                self.emit(OP['LOAD_NONE'])
            elif isinstance(v, str):
                self.emit(OP['LOAD_STR'], self.str_idx(v))
            elif isinstance(v, (bool, int, float, complex, bytes)):
                self.emit(OP['LOAD_CONST'], self.const_idx(v))
            else:
                raise VMUnsupported('constant %r' % type(v).__name__)
        elif n is ast.Name:
            self.load_name(e.id)
        elif n is ast.BinOp:
            op = BINOP_MAP.get(type(e.op).__name__)
            if op is None:
                raise VMUnsupported('binop %s' % type(e.op).__name__)
            self.expr(e.left)
            self.expr(e.right)
            self.emit(op)
        elif n is ast.UnaryOp:
            self.expr(e.operand)
            m = UNARY_MAP.get(type(e.op).__name__)
            if m:
                self.emit(m)
        elif n is ast.BoolOp:
            self.boolop(e)
        elif n is ast.Compare:
            self.compare(e)
        elif n is ast.IfExp:
            self.expr(e.test)
            jf = self.jump(OP['POP_JUMP_IF_FALSE'])
            self.expr(e.body)
            je = self.jump(OP['JUMP'])
            self.patch(jf, self.here())
            self.expr(e.orelse)
            self.patch(je, self.here())
        elif n is ast.List:
            for elt in e.elts:
                self.expr(elt)
            self.emit(OP['BUILD_LIST'], len(e.elts))
        elif n is ast.Tuple:
            for elt in e.elts:
                self.expr(elt)
            self.emit(OP['BUILD_TUPLE'], len(e.elts))
        elif n is ast.Set:
            for elt in e.elts:
                self.expr(elt)
            self.emit(OP['BUILD_SET'], len(e.elts))
        elif n is ast.Dict:
            if any(k is None for k in e.keys):
                raise VMUnsupported('dict unpacking')
            for k, v in zip(e.keys, e.values):
                self.expr(k)
                self.expr(v)
            self.emit(OP['BUILD_MAP'], len(e.keys))
        elif n is ast.Subscript:
            self.expr(e.value)
            if isinstance(e.slice, ast.Slice):
                for part in (e.slice.lower, e.slice.upper, e.slice.step):
                    if part is None:
                        self.emit(OP['LOAD_NONE'])
                    else:
                        self.expr(part)
                self.emit(OP['BUILD_SLICE'], 3 if e.slice.step is not None else 2)
            else:
                self.expr(e.slice)
            self.emit(OP['LOAD_SUBSCR'])
        elif n is ast.Attribute:
            self.expr(e.value)
            self.emit(OP['LOAD_ATTR'], self.name_idx(e.attr))
        elif n is ast.Call:
            self.call(e)
        else:
            raise VMUnsupported('expr %s' % type(e).__name__)

    def boolop(self, e):
        jumpop = OP['JUMP_IF_FALSE_OR_POP'] if isinstance(e.op, ast.And) else OP['JUMP_IF_TRUE_OR_POP']
        for v in e.values[:-1]:
            self.expr(v)
            j = self.jump(jumpop)
            self.patch(j, self.here())
        self.expr(e.values[-1])

    def compare(self, e):
        pairs = list(zip(e.ops, e.comparators))
        tmp = self.tmp_slot()
        self.expr(e.left)
        jumps = []
        for i, (op, comp) in enumerate(pairs):
            self.expr(comp)
            if i < len(pairs) - 1:
                self.emit(OP['STORE_FAST'], tmp)
            self.emit(OP['COMPARE'], CMP[_OPNAME[type(op)]])
            if i < len(pairs) - 1:
                jumps.append(self.jump(OP['JUMP_IF_FALSE_OR_POP']))
                self.emit(OP['LOAD_FAST'], tmp)
        end = self.here()
        for j in jumps:
            self.patch(j, end)

    def call(self, e):
        for a in e.args:
            if isinstance(a, ast.Starred):
                raise VMUnsupported('star args')
            self.expr(a)
        kw_idx = []
        for kw in e.keywords:
            if kw.arg is None:
                raise VMUnsupported('**kwargs')
            self.expr(kw.value)
            kw_idx.append(self.name_idx(kw.arg))
        self.expr(e.func)
        self.emit(OP['CALL_FUNCTION'], len(e.args) | (len(kw_idx) << 8))
        for i in kw_idx:
            self.code.append(i & 0xFF)


def compile_function(fn):
    c = _Compiler(fn)
    c.prepare()
    c.compile_body(fn.body)
    return {
        'code': bytes(c.code),
        'consts': c.consts,
        'names': c.names,
        'strtab': c.strtab,
        'nlocals': c._next_slot,
        'argcount': len(c.args),
        'argnames': list(c.args),
        'defaults': c.defaults,
    }
