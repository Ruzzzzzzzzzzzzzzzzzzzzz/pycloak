"""Embedded VM interpreter source."""

INTERP_SOURCE = r'''
import builtins as _bi

_DONE = object()


def _off(v):
    return v - 0x10000 if v >= 0x8000 else v


def _cmp_eq(l, r): return l == r
def _cmp_ne(l, r): return l != r
def _cmp_lt(l, r): return l < r
def _cmp_le(l, r): return l <= r
def _cmp_gt(l, r): return l > r
def _cmp_ge(l, r): return l >= r
def _cmp_in(l, r): return l in r
def _cmp_ni(l, r): return l not in r
def _cmp_is(l, r): return l is r
def _cmp_nis(l, r): return l is not r

_CMPF = (_cmp_eq, _cmp_ne, _cmp_lt, _cmp_le, _cmp_gt, _cmp_ge,
         _cmp_in, _cmp_ni, _cmp_is, _cmp_nis)

_CACHE = {}


def _vm_run(code, consts, names, strtab, nlocals, args, glb):
    st = list(args)
    if len(st) < nlocals:
        st.extend([None] * (nlocals - len(st)))
    stack = []
    ip = 0
    total = len(code) // 3
    while ip < total:
        p = ip * 3
        op = code[p]
        a = (code[p + 1] << 8) | code[p + 2]
        ip += 1
        if op == NOP:
            pass
        elif op == LOAD_CONST:
            stack.append(consts[a])
        elif op == LOAD_GLOBAL:
            nm = names[a]
            stack.append(glb[nm] if nm in glb else _bi.__dict__[nm])
        elif op == STORE_GLOBAL:
            glb[names[a]] = stack.pop()
        elif op == LOAD_FAST:
            stack.append(st[a])
        elif op == STORE_FAST:
            st[a] = stack.pop()
        elif op == LOAD_ATTR:
            stack.append(getattr(stack.pop(), names[a]))
        elif op == STORE_ATTR:
            v = stack.pop()
            setattr(stack.pop(), names[a], v)
        elif op == LOAD_SUBSCR:
            k = stack.pop()
            stack.append(stack.pop()[k])
        elif op == STORE_SUBSCR:
            v = stack.pop()
            k = stack.pop()
            stack.pop()[k] = v
        elif op == BUILD_LIST:
            stack.append([stack.pop() for _ in range(a)][::-1])
        elif op == BUILD_TUPLE:
            stack.append(tuple([stack.pop() for _ in range(a)][::-1]))
        elif op == BUILD_SET:
            stack.append({stack.pop() for _ in range(a)})
        elif op == BUILD_MAP:
            items = [stack.pop() for _ in range(a * 2)][::-1]
            stack.append(dict(zip(items[0::2], items[1::2])))
        elif op == LOAD_STR:
            stack.append(strtab[a])
        elif op == BINARY_ADD:
            r = stack.pop(); stack.append(stack.pop() + r)
        elif op == BINARY_SUB:
            r = stack.pop(); stack.append(stack.pop() - r)
        elif op == BINARY_MULT:
            r = stack.pop(); stack.append(stack.pop() * r)
        elif op == BINARY_FLOORDIV:
            r = stack.pop(); stack.append(stack.pop() // r)
        elif op == BINARY_TRUE_DIV:
            r = stack.pop(); stack.append(stack.pop() / r)
        elif op == BINARY_MOD:
            r = stack.pop(); stack.append(stack.pop() % r)
        elif op == BINARY_POW:
            r = stack.pop(); stack.append(stack.pop() ** r)
        elif op == BINARY_AND:
            r = stack.pop(); stack.append(stack.pop() & r)
        elif op == BINARY_OR:
            r = stack.pop(); stack.append(stack.pop() | r)
        elif op == BINARY_XOR:
            r = stack.pop(); stack.append(stack.pop() ^ r)
        elif op == BINARY_LSHIFT:
            r = stack.pop(); stack.append(stack.pop() << r)
        elif op == BINARY_RSHIFT:
            r = stack.pop(); stack.append(stack.pop() >> r)
        elif op == COMPARE:
            r = stack.pop()
            stack.append(_CMPF[a](stack.pop(), r))
        elif op == UNARY_NEG:
            stack.append(-stack.pop())
        elif op == UNARY_NOT:
            stack.append(not stack.pop())
        elif op == UNARY_INVERT:
            stack.append(~stack.pop())
        elif op == POP_JUMP_IF_FALSE:
            if not stack.pop():
                ip += _off(a)
        elif op == POP_JUMP_IF_TRUE:
            if stack.pop():
                ip += _off(a)
        elif op == JUMP:
            ip += _off(a)
        elif op == CALL_FUNCTION:
            nargs = a & 0xFF
            nkw = (a >> 8) & 0xFF
            f = stack.pop()
            kw = {}
            for i in range(nkw):
                kw[names[code[p + 3 + i]]] = stack.pop()
            args_l = [stack.pop() for _ in range(nargs)][::-1]
            stack.append(f(*args_l, **kw))
        elif op == RETURN_VALUE:
            return stack.pop()
        elif op == POP_TOP:
            stack.pop()
        elif op == DUP_TOP:
            stack.append(stack[-1])
        elif op == JUMP_IF_FALSE_OR_POP:
            if stack[-1]:
                stack.pop()
            else:
                ip += _off(a)
        elif op == JUMP_IF_TRUE_OR_POP:
            if stack[-1]:
                ip += _off(a)
            else:
                stack.pop()
        elif op == GET_ITER:
            stack.append(iter(stack.pop()))
        elif op == FOR_ITER:
            v = next(stack[-1], _DONE)
            if v is _DONE:
                stack.pop()
                ip += _off(a)
            else:
                stack.append(v)
        elif op == BUILD_SLICE:
            if a == 2:
                up = stack.pop()
                lo = stack.pop()
                stack.append(slice(lo, up))
            else:
                stp = stack.pop()
                up = stack.pop()
                lo = stack.pop()
                stack.append(slice(lo, up, stp))
        elif op == UNPACK_SEQUENCE:
            vals = list(stack.pop())
            if len(vals) != a:
                raise ValueError('not enough values to unpack')
            stack.extend(reversed(vals))
        elif op == IMPORT_NAME:
            stack.append(_bi.__import__(names[a]))
        elif op == IMPORT_FROM:
            stack.append(getattr(stack.pop(), names[a]))
        elif op == LOAD_NONE:
            stack.append(None)
        elif op == RAISE:
            raise stack.pop()
        else:
            raise RuntimeError('illegal opcode %d' % op)
    return None


def _vm_call(blob_id, args, glb):
    st = _CACHE.get(blob_id)
    if st is None:
        raw = _VM_DEC(blob_id)
        st = __import__('marshal').loads(raw)
        _CACHE[blob_id] = st
    return _vm_run(st[0], st[1], st[2], st[3], st[4], args, glb)
'''


def module_source(opcode_prefix):
    return opcode_prefix + '\n' + INTERP_SOURCE + '\n'
