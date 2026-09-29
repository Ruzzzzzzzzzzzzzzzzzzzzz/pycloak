"""RSA keygen + PKCS#1 v1.5 SHA-256 signing/verification, zero third-party deps."""

import base64
import getpass
import hashlib
import platform
import random
import uuid

OID_RSA = bytes.fromhex('2a864886f70d010101')
DI_SHA256 = bytes.fromhex('3031300d060960864801650304020105000420')


def _der_len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, 'big')
    return bytes([0x80 | len(b)]) + b


def _der_int(v):
    b = v.to_bytes(max(1, (v.bit_length() + 7) // 8), 'big')
    if b[0] & 0x80:
        b = b'\x00' + b
    return b'\x02' + _der_len(len(b)) + b


def _der_seq(*parts):
    body = b''.join(parts)
    return b'\x30' + _der_len(len(body)) + body


def _der_oid():
    return b'\x06' + _der_len(len(OID_RSA)) + OID_RSA


def _der_null():
    return b'\x05\x00'


def _der_bitstr(b):
    return b'\x03' + _der_len(len(b) + 1) + b'\x00' + b


def _der_read(der, pos):
    tag = der[pos]
    pos += 1
    ln = der[pos]
    pos += 1
    if ln & 0x80:
        n = ln & 0x7F
        ln = int.from_bytes(der[pos:pos + n], 'big')
        pos += n
    return tag, der[pos:pos + ln], pos + ln


def _sieve(limit):
    sieve = bytearray(b'\x01') * (limit + 1)
    sieve[0:2] = b'\x00\x00'
    for i in range(2, int(limit ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i::i] = b'\x00' * (((limit - i * i) // i) + 1)
    return [i for i in range(limit + 1) if sieve[i]]


_SMALL_PRIMES = _sieve(1000)
_MR_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53)


def _is_prime(n):
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in _MR_BASES:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _rand_prime(bits, rng):
    while True:
        p = rng.getrandbits(bits) | (1 << (bits - 1)) | 1
        if _is_prime(p):
            return p


def generate_keypair(bits=2048, seed=None):
    rng = random.Random(seed)
    e = 65537
    while True:
        p = _rand_prime(bits // 2, rng)
        while True:
            q = _rand_prime(bits // 2, rng)
            if q != p:
                break
        n = p * q
        phi = (p - 1) * (q - 1)
        if phi % e == 0:
            continue
        d = pow(e, -1, phi)
        return {
            'n': n, 'e': e, 'd': d, 'p': p, 'q': q,
            'dp': d % (p - 1), 'dq': d % (q - 1), 'qi': pow(q, -1, p),
        }


def _b64wrap(b):
    s = base64.b64encode(b).decode('ascii')
    return '\n'.join(s[i:i + 64] for i in range(0, len(s), 64))


def private_key_pem(k):
    der = _der_seq(
        _der_int(0), _der_int(k['n']), _der_int(k['e']), _der_int(k['d']),
        _der_int(k['p']), _der_int(k['q']), _der_int(k['dp']),
        _der_int(k['dq']), _der_int(k['qi']))
    return '-----BEGIN RSA PRIVATE KEY-----\n%s\n-----END RSA PRIVATE KEY-----\n' % _b64wrap(der)


def public_key_pem(k):
    inner = _der_seq(_der_int(k['n']), _der_int(k['e']))
    spki = _der_seq(_der_seq(_der_oid(), _der_null()), _der_bitstr(inner))
    return '-----BEGIN PUBLIC KEY-----\n%s\n-----END PUBLIC KEY-----\n' % _b64wrap(spki)


def _pem_body(text):
    return base64.b64decode(''.join(
        l.strip() for l in text.splitlines() if not l.startswith('-----')))


def parse_public_pem(text):
    der = _pem_body(text)
    _, seq, _ = _der_read(der, 0)
    _, alg, p = _der_read(seq, 0)
    _, bits, p = _der_read(seq, p)
    bits = bits[1:]
    _, rsaseq, _ = _der_read(bits, 0)
    _, nb, p = _der_read(rsaseq, 0)
    _, eb, _ = _der_read(rsaseq, p)
    return {'n': int.from_bytes(nb, 'big'), 'e': int.from_bytes(eb, 'big')}


def parse_private_pem(text):
    der = _pem_body(text)
    _, seq, _ = _der_read(der, 0)
    _, ver, p = _der_read(seq, 0)
    vals = []
    for _ in range(8):
        _, v, p = _der_read(seq, p)
        vals.append(int.from_bytes(v, 'big'))
    n, e, d, p_, q, dp, dq, qi = vals
    return {'n': n, 'e': e, 'd': d, 'p': p_, 'q': q, 'dp': dp, 'dq': dq, 'qi': qi}


def sign_sha256(msg, key):
    k = (key['n'].bit_length() + 7) // 8
    t = DI_SHA256 + hashlib.sha256(msg).digest()
    em = b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t
    s = pow(int.from_bytes(em, 'big'), key['d'], key['n'])
    return s.to_bytes(k, 'big')


def verify_sha256(msg, sig, n, e):
    k = (n.bit_length() + 7) // 8
    m = pow(int.from_bytes(sig, 'big'), e, n).to_bytes(k, 'big')
    t = b'\x00\x01' + b'\xff' * (k - 51 - 3) + b'\x00' + DI_SHA256 + hashlib.sha256(msg).digest()
    return __import__('hmac').compare_digest(m, t)


def machine_fingerprint():
    try:
        user = getpass.getuser()
    except Exception:
        user = __import__('os').environ.get('USERNAME', 'unknown')
    parts = (uuid.getnode(), platform.node(), platform.machine(), user, platform.system())
    return hashlib.sha256('|'.join(str(p) for p in parts).encode('utf-8')).hexdigest()


def make_payload(fp, exp_ts=0):
    return ('pycloak1|%d|%s' % (exp_ts, fp)).encode('utf-8')


def parse_payload(data):
    parts = data.decode('utf-8').split('|')
    if len(parts) != 3 or parts[0] != 'pycloak1':
        raise ValueError('bad payload')
    return int(parts[1]), parts[2]


def license_text(payload, sig):
    return ('-----PYCLOAK LICENSE-----\npayload=%s\nsig=%s\n-----END PYCLOAK-----\n'
            % (base64.b64encode(payload).decode(), base64.b64encode(sig).decode()))


def parse_license(text):
    payload = sig = None
    for ln in text.strip().splitlines():
        if ln.startswith('payload='):
            payload = base64.b64decode(ln[8:])
        elif ln.startswith('sig='):
            sig = base64.b64decode(ln[4:])
    if payload is None or sig is None:
        raise ValueError('malformed license')
    return payload, sig
