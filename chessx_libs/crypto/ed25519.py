"""Ed25519 (RFC 8032) pure-Python reference. Not constant-time."""
import hashlib, secrets

p = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
d = -121665 * pow(121666, p - 2, p) % p
SQRT_M1 = pow(2, (p - 1) // 4, p)


def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % p
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % p
    C = 2 * P[3] * Q[3] * d % p
    D = 2 * P[2] * Q[2] % p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % p, G * H % p, F * G % p, E * H % p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _recover_x(y, sign):
    if y >= p:
        return None
    x2 = (y * y - 1) * pow(d * y * y + 1, p - 2, p)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (p + 3) // 8, p)
    if (x * x - x2) % p:
        x = x * SQRT_M1 % p
    if (x * x - x2) % p:
        return None
    if (x & 1) != sign:
        x = p - x
    return x


_gy = 4 * pow(5, p - 2, p) % p
_gx = _recover_x(_gy, 0)
G = (_gx, _gy, 1, _gx * _gy % p)


def _enc(P):
    zi = pow(P[2], p - 2, p)
    x, y = P[0] * zi % p, P[1] * zi % p
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _dec(s):
    y = int.from_bytes(s, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    if x is None:
        raise ValueError("bad point")
    return (x, y, 1, x * y % p)


def _eq(P, Q):
    return (P[0] * Q[2] - Q[0] * P[2]) % p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % p == 0


def _H(m):
    return int.from_bytes(hashlib.sha512(m).digest(), "little")


def _expand(sk):
    h = hashlib.sha512(sk).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8; a |= 1 << 254
    return a, h[32:]


def public_key(sk: bytes) -> bytes:
    return _enc(_mul(_expand(sk)[0], G))


def ed25519_keypair():
    sk = secrets.token_bytes(32)
    return sk, public_key(sk)


def ed25519_sign(sk: bytes, msg: bytes) -> bytes:
    a, prefix = _expand(sk)
    A = _enc(_mul(a, G))
    r = _H(prefix + msg) % L
    R = _enc(_mul(r, G))
    s = (r + _H(R + A + msg) * a) % L
    return R + s.to_bytes(32, "little")


def ed25519_verify(pk: bytes, msg: bytes, sig: bytes) -> bool:
    try:
        A, R = _dec(pk), _dec(sig[:32])
    except ValueError:
        return False
    s = int.from_bytes(sig[32:], "little")
    if len(sig) != 64 or s >= L:
        return False
    h = _H(sig[:32] + pk + msg) % L
    return _eq(_mul(s, G), _add(R, _mul(h, A)))
