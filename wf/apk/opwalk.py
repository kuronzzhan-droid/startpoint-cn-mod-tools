"""AVM2 bytecode walker with a full operand table (read + rewrite)."""

U30 = 'u30'; U8 = 'u8'; S24 = 's24'; SW = 'switch'

OPS = {
    0x01: [], 0x02: [], 0x03: [], 0x04: [U30], 0x05: [U30], 0x06: [U30], 0x07: [],
    0x08: [U30], 0x09: [], 0x0a: [], 0x0b: [],
    0x0c: [S24], 0x0d: [S24], 0x0e: [S24], 0x0f: [S24], 0x10: [S24], 0x11: [S24],
    0x12: [S24], 0x13: [S24], 0x14: [S24], 0x15: [S24], 0x16: [S24], 0x17: [S24],
    0x18: [S24], 0x19: [S24], 0x1a: [S24], 0x1b: [SW],
    0x1c: [], 0x1d: [], 0x1e: [], 0x1f: [], 0x20: [], 0x21: [], 0x22: [], 0x23: [],
    0x24: [U8], 0x25: [U30], 0x26: [], 0x27: [], 0x28: [], 0x29: [], 0x2a: [], 0x2b: [],
    0x2c: [U30], 0x2d: [U30], 0x2e: [U30], 0x2f: [U30], 0x30: [], 0x31: [U30],
    0x32: [U30, U30],
    0x35: [], 0x36: [], 0x37: [], 0x38: [], 0x39: [], 0x3a: [], 0x3b: [], 0x3c: [],
    0x3d: [], 0x3e: [],
    0x40: [U30], 0x41: [U30], 0x42: [U30], 0x43: [U30, U30], 0x44: [U30, U30],
    0x45: [U30, U30], 0x46: [U30, U30], 0x47: [], 0x48: [], 0x49: [U30],
    0x4a: [U30, U30], 0x4b: [U30, U30], 0x4c: [U30, U30], 0x4d: [U30, U30],
    0x4e: [U30, U30], 0x4f: [U30, U30],
    0x50: [], 0x51: [], 0x52: [], 0x53: [U30], 0x55: [U30], 0x56: [U30], 0x57: [],
    0x58: [U30], 0x59: [U30], 0x5a: [U30], 0x5b: [U30], 0x5c: [U30],
    0x5d: [U30], 0x5e: [U30], 0x5f: [U30],
    0x60: [U30], 0x61: [U30], 0x62: [U30], 0x63: [U30], 0x64: [], 0x65: [U8],
    0x66: [U30], 0x67: [U30], 0x68: [U30], 0x6a: [U30], 0x6b: [],
    0x6c: [U30], 0x6d: [U30], 0x6e: [U30], 0x6f: [U30],
    0x70: [], 0x71: [], 0x72: [], 0x73: [], 0x74: [], 0x75: [], 0x76: [], 0x77: [],
    0x78: [], 0x79: [], 0x7a: [], 0x7b: [],
    0x80: [U30], 0x81: [], 0x82: [], 0x83: [], 0x84: [], 0x85: [], 0x86: [U30],
    0x87: [], 0x88: [], 0x89: [], 0x8a: [], 0x8b: [], 0x8c: [], 0x8d: [], 0x8e: [], 0x8f: [],
    0x90: [], 0x91: [], 0x92: [U30], 0x93: [], 0x94: [U30], 0x95: [], 0x96: [], 0x97: [],
    0xa0: [], 0xa1: [], 0xa2: [], 0xa3: [], 0xa4: [], 0xa5: [], 0xa6: [], 0xa7: [],
    0xa8: [], 0xa9: [], 0xaa: [], 0xab: [], 0xac: [], 0xad: [], 0xae: [], 0xaf: [],
    0xb0: [], 0xb1: [], 0xb2: [U30], 0xb3: [], 0xb4: [],
    0xc0: [], 0xc1: [], 0xc2: [U30], 0xc3: [U30], 0xc4: [], 0xc5: [], 0xc6: [], 0xc7: [],
    0xd0: [], 0xd1: [], 0xd2: [], 0xd3: [], 0xd4: [], 0xd5: [], 0xd6: [], 0xd7: [],
    0xef: [U8, U30, U8, U30], 0xf0: [U30], 0xf1: [U30], 0xf2: [U30], 0xf3: [],
}


def _u30(d, p):
    v = 0; sh = 0
    for _ in range(5):
        b = d[p]; p += 1
        v |= (b & 0x7f) << sh
        if not (b & 0x80): break
        sh += 7
    return v, p


def _s24(d, p):
    v = d[p] | (d[p + 1] << 8) | (d[p + 2] << 16)
    if v & 0x800000: v -= 0x1000000
    return v, p + 3


def walk(code):
    """Yield (opcode, [operands])."""
    p = 0; n = len(code)
    while p < n:
        op = code[p]; p += 1
        fmt = OPS.get(op)
        if fmt is None:
            raise ValueError('unknown opcode 0x%02x at %d' % (op, p - 1))
        args = []
        for f in fmt:
            if f == U30:
                v, p = _u30(code, p); args.append(v)
            elif f == U8:
                args.append(code[p]); p += 1
            elif f == S24:
                v, p = _s24(code, p); args.append(v)
            elif f == SW:
                d, p = _s24(code, p)
                cnt, p = _u30(code, p)
                cases = []
                for _ in range(cnt + 1):
                    v, p = _s24(code, p); cases.append(v)
                args.append((d, cnt, cases))
        yield op, args


def enc_u30(v):
    out = bytearray()
    while True:
        b = v & 0x7f; v >>= 7
        if v: out.append(b | 0x80)
        else: out.append(b); break
    return bytes(out)


def rewrite(code, fn):
    """Rebuild bytecode, letting fn(op, index_in_operand_list, kind, value) return a new value.

    kind is one of 'multiname', 'string', 'int', 'uint', 'double', 'class', 'method',
    'namespace', 'other'. Branch offsets are preserved verbatim only when every
    rewritten operand keeps its encoded width; the caller must check `same_len`.
    """
    out = bytearray()
    same_len = True
    p = 0; n = len(code)
    while p < n:
        op = code[p]; start = p; p += 1
        fmt = OPS[op]
        out.append(op)
        for i, f in enumerate(fmt):
            if f == U30:
                v, p = _u30(code, p)
                nv = fn(op, i, v)
                a = enc_u30(v); b = enc_u30(nv)
                if len(a) != len(b): same_len = False
                out += b
            elif f == U8:
                out.append(code[p]); p += 1
            elif f == S24:
                out += code[p:p + 3]; p += 3
            elif f == SW:
                q = p
                d, p = _s24(code, p)
                cnt, p = _u30(code, p)
                for _ in range(cnt + 1):
                    _, p = _s24(code, p)
                out += code[q:p]
    return bytes(out), same_len


# operand slot -> pool kind, per opcode
KIND = {}
for _op in (0x04, 0x05, 0x06, 0x59, 0x5b, 0x5c, 0x5d, 0x5e, 0x5f, 0x60, 0x61, 0x66,
            0x68, 0x6a, 0x80, 0x86, 0xb2):
    KIND[(_op, 0)] = 'multiname'
for _op in (0x41, 0x42, 0x49, 0x53, 0x55, 0x56, 0x62, 0x63, 0x08, 0x25, 0x6c, 0x6d,
            0x6e, 0x6f, 0x92, 0x94, 0xc2, 0xc3, 0x5a, 0x67):
    KIND[(_op, 0)] = 'other'
KIND[(0x2c, 0)] = 'string'
KIND[(0x2d, 0)] = 'int'
KIND[(0x2e, 0)] = 'uint'
KIND[(0x2f, 0)] = 'double'
KIND[(0x31, 0)] = 'namespace'
KIND[(0x40, 0)] = 'method'
KIND[(0x44, 0)] = 'method'
KIND[(0x58, 0)] = 'class'
KIND[(0x43, 0)] = 'other'
for _op in (0x45, 0x46, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f):
    KIND[(_op, 0)] = 'multiname'
    KIND[(_op, 1)] = 'other'   # arg count
KIND[(0x43, 1)] = 'other'
KIND[(0x44, 1)] = 'other'
KIND[(0x32, 0)] = 'other'
KIND[(0x32, 1)] = 'other'
KIND[(0xf0, 0)] = 'other'
KIND[(0xf1, 0)] = 'string'
KIND[(0xf2, 0)] = 'other'
KIND[(0xef, 1)] = 'string'
KIND[(0xef, 3)] = 'other'
