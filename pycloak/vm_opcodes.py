"""Custom VM instruction set shared by the compiler and the embedded runtime."""

OP = {
    'NOP': 0,
    'LOAD_CONST': 1,
    'LOAD_GLOBAL': 2,
    'STORE_GLOBAL': 3,
    'LOAD_FAST': 4,
    'STORE_FAST': 5,
    'LOAD_ATTR': 6,
    'STORE_ATTR': 7,
    'LOAD_SUBSCR': 8,
    'STORE_SUBSCR': 9,
    'BUILD_LIST': 10,
    'BUILD_TUPLE': 11,
    'BUILD_MAP': 12,
    'LOAD_STR': 13,
    'BINARY_ADD': 14,
    'BINARY_SUB': 15,
    'BINARY_MULT': 16,
    'BINARY_FLOORDIV': 17,
    'BINARY_TRUE_DIV': 18,
    'BINARY_MOD': 19,
    'BINARY_POW': 20,
    'BINARY_AND': 21,
    'BINARY_OR': 22,
    'BINARY_XOR': 23,
    'BINARY_LSHIFT': 24,
    'BINARY_RSHIFT': 25,
    'COMPARE': 26,
    'UNARY_NEG': 27,
    'UNARY_NOT': 28,
    'UNARY_INVERT': 29,
    'POP_JUMP_IF_FALSE': 30,
    'POP_JUMP_IF_TRUE': 31,
    'JUMP': 32,
    'CALL_FUNCTION': 33,
    'RETURN_VALUE': 34,
    'POP_TOP': 35,
    'DUP_TOP': 36,
    'JUMP_IF_FALSE_OR_POP': 37,
    'JUMP_IF_TRUE_OR_POP': 38,
    'GET_ITER': 39,
    'FOR_ITER': 40,
    'BUILD_SLICE': 41,
    'UNPACK_SEQUENCE': 42,
    'IMPORT_NAME': 43,
    'IMPORT_FROM': 44,
    'LOAD_NONE': 45,
    'BUILD_SET': 46,
    'RAISE': 47,
}

CMP = {
    '==': 0, '!=': 1, '<': 2, '<=': 3, '>': 4, '>=': 5,
    'in': 6, 'not in': 7, 'is': 8, 'is not': 9,
}

BINOP_MAP = {
    'Add': OP['BINARY_ADD'], 'Sub': OP['BINARY_SUB'],
    'Mult': OP['BINARY_MULT'], 'FloorDiv': OP['BINARY_FLOORDIV'],
    'Div': OP['BINARY_TRUE_DIV'], 'Mod': OP['BINARY_MOD'],
    'Pow': OP['BINARY_POW'], 'BitAnd': OP['BINARY_AND'],
    'BitOr': OP['BINARY_OR'], 'BitXor': OP['BINARY_XOR'],
    'LShift': OP['BINARY_LSHIFT'], 'RShift': OP['BINARY_RSHIFT'],
}

UNARY_MAP = {
    'USub': OP['UNARY_NEG'], 'Not': OP['UNARY_NOT'], 'Invert': OP['UNARY_INVERT'],
    'UAdd': None,
}


def runtime_constants_source():
    lines = ['# vm opcode constants']
    for name, val in OP.items():
        lines.append('%s = %d' % (name, val))
    lines.append('CMP_KINDS = ' + repr({v: k for k, v in CMP.items()}))
    return '\n'.join(lines)
