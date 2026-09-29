"""Pure-Python AES (FIPS-197), CBC mode, zero third-party deps."""

SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)

RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D)


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11B
    return a & 0xFF


_TE = None
_TD = None
_INV_S = None
_IM = None


def _build_tables():
    global _TE, _TD, _INV_S, _IM
    if _TE is not None:
        return
    inv = [0] * 256
    for i, v in enumerate(SBOX):
        inv[v] = i
    te0, te1, te2, te3 = [0] * 256, [0] * 256, [0] * 256, [0] * 256
    td0, td1, td2, td3 = [0] * 256, [0] * 256, [0] * 256, [0] * 256
    for i in range(256):
        s = SBOX[i]
        x2 = _xtime(s)
        x3 = s ^ x2
        te0[i] = (x2 << 24) | (s << 16) | (s << 8) | x3
        te1[i] = (x3 << 24) | (x2 << 16) | (s << 8) | s
        te2[i] = (s << 24) | (x3 << 16) | (x2 << 8) | s
        te3[i] = (s << 24) | (s << 16) | (x3 << 8) | x2
        d = inv[i]
        x2 = _xtime(d)
        x4 = _xtime(x2)
        x8 = _xtime(x4)
        x9 = x8 ^ d
        xb = x8 ^ x2 ^ d
        xd = x8 ^ x4 ^ d
        xe = x8 ^ x4 ^ x2
        td0[i] = (xe << 24) | (x9 << 16) | (xd << 8) | xb
        td1[i] = (xb << 24) | (xe << 16) | (x9 << 8) | xd
        td2[i] = (xd << 24) | (xb << 16) | (xe << 8) | x9
        td3[i] = (x9 << 24) | (xd << 16) | (xb << 8) | xe
    _TE = (te0, te1, te2, te3)
    _TD = (td0, td1, td2, td3)
    _INV_S = inv
    global _IM
    im0, im1, im2, im3 = [0] * 256, [0] * 256, [0] * 256, [0] * 256
    for i in range(256):
        im0[i] = td0[SBOX[i]]
        im1[i] = td1[SBOX[i]]
        im2[i] = td2[SBOX[i]]
        im3[i] = td3[SBOX[i]]
    _IM = (im0, im1, im2, im3)


def _subw(v):
    s = SBOX
    return ((s[(v >> 24) & 0xFF] << 24) | (s[(v >> 16) & 0xFF] << 16)
            | (s[(v >> 8) & 0xFF] << 8) | s[v & 0xFF])


class AES:
    def __init__(self, key):
        if len(key) not in (16, 24, 32):
            raise ValueError('AES key must be 16/24/32 bytes')
        _build_tables()
        self.nr = {16: 10, 24: 12, 32: 14}[len(key)]
        nk = len(key) // 4
        w = [int.from_bytes(key[i:i + 4], 'big') for i in range(0, len(key), 4)]
        for i in range(nk, 4 * (self.nr + 1)):
            t = w[i - 1]
            if i % nk == 0:
                r = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
                t = _subw(r) ^ (RCON[i // nk - 1] << 24)
            elif nk > 6 and i % nk == 4:
                t = _subw(t)
            w.append(w[i - nk] ^ t)
        self.rk = w

    def encrypt_block(self, block):
        te = _TE
        rk = self.rk
        s0, s1, s2, s3 = (int.from_bytes(block[i:i + 4], 'big') for i in range(0, 16, 4))
        s0 ^= rk[0]; s1 ^= rk[1]; s2 ^= rk[2]; s3 ^= rk[3]
        r = 4
        for _ in range(self.nr - 1):
            t0 = te[0][(s0 >> 24) & 0xFF] ^ te[1][(s1 >> 16) & 0xFF] ^ te[2][(s2 >> 8) & 0xFF] ^ te[3][s3 & 0xFF] ^ rk[r]
            t1 = te[0][(s1 >> 24) & 0xFF] ^ te[1][(s2 >> 16) & 0xFF] ^ te[2][(s3 >> 8) & 0xFF] ^ te[3][s0 & 0xFF] ^ rk[r + 1]
            t2 = te[0][(s2 >> 24) & 0xFF] ^ te[1][(s3 >> 16) & 0xFF] ^ te[2][(s0 >> 8) & 0xFF] ^ te[3][s1 & 0xFF] ^ rk[r + 2]
            t3 = te[0][(s3 >> 24) & 0xFF] ^ te[1][(s0 >> 16) & 0xFF] ^ te[2][(s1 >> 8) & 0xFF] ^ te[3][s2 & 0xFF] ^ rk[r + 3]
            s0, s1, s2, s3 = t0, t1, t2, t3
            r += 4
        S = SBOX
        t0 = ((S[(s0 >> 24) & 0xFF] << 24) | (S[(s1 >> 16) & 0xFF] << 16)
              | (S[(s2 >> 8) & 0xFF] << 8) | S[s3 & 0xFF]) ^ rk[r]
        t1 = ((S[(s1 >> 24) & 0xFF] << 24) | (S[(s2 >> 16) & 0xFF] << 16)
              | (S[(s3 >> 8) & 0xFF] << 8) | S[s0 & 0xFF]) ^ rk[r + 1]
        t2 = ((S[(s2 >> 24) & 0xFF] << 24) | (S[(s3 >> 16) & 0xFF] << 16)
              | (S[(s0 >> 8) & 0xFF] << 8) | S[s1 & 0xFF]) ^ rk[r + 2]
        t3 = ((S[(s3 >> 24) & 0xFF] << 24) | (S[(s0 >> 16) & 0xFF] << 16)
              | (S[(s1 >> 8) & 0xFF] << 8) | S[s2 & 0xFF]) ^ rk[r + 3]
        return b''.join(v.to_bytes(4, 'big') for v in (t0, t1, t2, t3))

    def decrypt_block(self, block):
        im = _IM
        S = _INV_S
        rk = self.rk
        s0, s1, s2, s3 = (int.from_bytes(block[i:i + 4], 'big') for i in range(0, 16, 4))
        r = 4 * self.nr
        s0 ^= rk[r]; s1 ^= rk[r + 1]; s2 ^= rk[r + 2]; s3 ^= rk[r + 3]
        s0, s1, s2, s3 = (
            (S[(s0 >> 24) & 0xFF] << 24) | (S[(s3 >> 16) & 0xFF] << 16)
            | (S[(s2 >> 8) & 0xFF] << 8) | S[s1 & 0xFF],
            (S[(s1 >> 24) & 0xFF] << 24) | (S[(s0 >> 16) & 0xFF] << 16)
            | (S[(s3 >> 8) & 0xFF] << 8) | S[s2 & 0xFF],
            (S[(s2 >> 24) & 0xFF] << 24) | (S[(s1 >> 16) & 0xFF] << 16)
            | (S[(s0 >> 8) & 0xFF] << 8) | S[s3 & 0xFF],
            (S[(s3 >> 24) & 0xFF] << 24) | (S[(s2 >> 16) & 0xFF] << 16)
            | (S[(s1 >> 8) & 0xFF] << 8) | S[s0 & 0xFF])
        r -= 4
        for _ in range(self.nr - 1):
            s0 ^= rk[r]; s1 ^= rk[r + 1]; s2 ^= rk[r + 2]; s3 ^= rk[r + 3]
            s0 = im[0][(s0 >> 24) & 0xFF] ^ im[1][(s0 >> 16) & 0xFF] ^ im[2][(s0 >> 8) & 0xFF] ^ im[3][s0 & 0xFF]
            s1 = im[0][(s1 >> 24) & 0xFF] ^ im[1][(s1 >> 16) & 0xFF] ^ im[2][(s1 >> 8) & 0xFF] ^ im[3][s1 & 0xFF]
            s2 = im[0][(s2 >> 24) & 0xFF] ^ im[1][(s2 >> 16) & 0xFF] ^ im[2][(s2 >> 8) & 0xFF] ^ im[3][s2 & 0xFF]
            s3 = im[0][(s3 >> 24) & 0xFF] ^ im[1][(s3 >> 16) & 0xFF] ^ im[2][(s3 >> 8) & 0xFF] ^ im[3][s3 & 0xFF]
            s0, s1, s2, s3 = (
                (S[(s0 >> 24) & 0xFF] << 24) | (S[(s3 >> 16) & 0xFF] << 16)
                | (S[(s2 >> 8) & 0xFF] << 8) | S[s1 & 0xFF],
                (S[(s1 >> 24) & 0xFF] << 24) | (S[(s0 >> 16) & 0xFF] << 16)
                | (S[(s3 >> 8) & 0xFF] << 8) | S[s2 & 0xFF],
                (S[(s2 >> 24) & 0xFF] << 24) | (S[(s1 >> 16) & 0xFF] << 16)
                | (S[(s0 >> 8) & 0xFF] << 8) | S[s3 & 0xFF],
                (S[(s3 >> 24) & 0xFF] << 24) | (S[(s2 >> 16) & 0xFF] << 16)
                | (S[(s1 >> 8) & 0xFF] << 8) | S[s0 & 0xFF])
            r -= 4
        s0 ^= rk[0]; s1 ^= rk[1]; s2 ^= rk[2]; s3 ^= rk[3]
        return b''.join(v.to_bytes(4, 'big') for v in (s0, s1, s2, s3))


def pkcs7_pad(data, bs=16):
    n = bs - len(data) % bs
    return data + bytes([n]) * n


def pkcs7_unpad(data):
    n = data[-1]
    if n < 1 or n > 16 or data[-n:] != bytes([n]) * n:
        raise ValueError('bad padding')
    return data[:-n]


def cbc_encrypt(key, data, iv):
    aes = AES(key)
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        blk = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
        prev = aes.encrypt_block(blk)
        out += prev
    return bytes(out)


def cbc_decrypt(key, data, iv):
    aes = AES(key)
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        out += bytes(a ^ b for a, b in zip(aes.decrypt_block(blk), prev))
        prev = blk
    return bytes(out)


def encrypt_blob(data, key):
    iv = __import__('os').urandom(16)
    return iv + cbc_encrypt(key, pkcs7_pad(data), iv)


def decrypt_blob(raw, key):
    iv, ct = raw[:16], raw[16:]
    return pkcs7_unpad(cbc_decrypt(key, ct, iv))
