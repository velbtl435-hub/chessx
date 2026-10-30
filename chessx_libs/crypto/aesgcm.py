"""AES-GCM (NIST SP 800-38D) pure-Python, AES-128/192/256. Slow, not constant-time."""
import hmac, struct

SBOX = [0] * 256
_p = _q = 1
while True:  # generate S-box
    _p = _p ^ ((_p << 1) & 0xFF) ^ (0x1B if _p & 0x80 else 0)
    _q ^= _q << 1; _q ^= _q << 2; _q ^= _q << 4; _q &= 0xFF
    if _q & 0x80:
        _q ^= 0x09
    x = _q ^ ((_q << 1 | _q >> 7) & 0xFF) ^ ((_q << 2 | _q >> 6) & 0xFF) ^ ((_q << 3 | _q >> 5) & 0xFF) ^ ((_q << 4 | _q >> 4) & 0xFF)
    SBOX[_p] = x ^ 0x63
    if _p == 1:
        break
SBOX[0] = 0x63


def _xt(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else a << 1


def _expand_key(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        t = w[i - 1][:]
        if i % nk == 0:
            t = [SBOX[b] for b in t[1:] + t[:1]]
            t[0] ^= rcon
            rcon = _xt(rcon)
        elif nk > 6 and i % nk == 4:
            t = [SBOX[b] for b in t]
        w.append([a ^ b for a, b in zip(w[i - nk], t)])
    return [sum(w[4 * r:4 * r + 4], []) for r in range(nr + 1)]


def _encrypt_block(rk, block):
    s = [b ^ k for b, k in zip(block, rk[0])]
    for r in range(1, len(rk)):
        s = [SBOX[b] for b in s]
        s = [s[(i + 4 * (i % 4)) % 16] for i in range(16)]  # ShiftRows (column-major)
        if r != len(rk) - 1:
            n = []
            for c in range(4):
                a = s[4 * c:4 * c + 4]
                t = a[0] ^ a[1] ^ a[2] ^ a[3]
                n += [a[i] ^ t ^ _xt(a[i] ^ a[(i + 1) % 4]) for i in range(4)]
            s = n
        s = [b ^ k for b, k in zip(s, rk[r])]
    return bytes(s)


def _gmul(x, y):
    R, z = 0xE1 << 120, 0
    for i in range(127, -1, -1):
        if (y >> i) & 1:
            z ^= x
        x = (x >> 1) ^ R if x & 1 else x >> 1
    return z


def _ghash(h, aad, ct):
    y = 0
    data = aad + b"\0" * (-len(aad) % 16) + ct + b"\0" * (-len(ct) % 16) + struct.pack(">QQ", len(aad) * 8, len(ct) * 8)
    for i in range(0, len(data), 16):
        y = _gmul(y ^ int.from_bytes(data[i:i + 16], "big"), h)
    return y


def _ctr(rk, j0, data):
    out, c = bytearray(), int.from_bytes(j0[12:], "big")
    for i in range(0, len(data), 16):
        c = (c + 1) & 0xFFFFFFFF
        ks = _encrypt_block(rk, j0[:12] + c.to_bytes(4, "big"))
        out += bytes(a ^ b for a, b in zip(data[i:i + 16], ks))
    return bytes(out)


def _setup(key, nonce):
    if len(key) not in (16, 24, 32) or len(nonce) != 12:
        raise ValueError("key must be 16/24/32 bytes, nonce 12 bytes")
    rk = _expand_key(key)
    h = int.from_bytes(_encrypt_block(rk, bytes(16)), "big")
    return rk, h, nonce + b"\0\0\0\1"


def aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    rk, h, j0 = _setup(key, nonce)
    ct = _ctr(rk, j0, plaintext)
    tag = (_ghash(h, aad, ct) ^ int.from_bytes(_encrypt_block(rk, j0), "big")).to_bytes(16, "big")
    return ct + tag


def aes_gcm_decrypt(key: bytes, nonce: bytes, data: bytes, aad: bytes = b"") -> bytes:
    rk, h, j0 = _setup(key, nonce)
    ct, tag = data[:-16], data[-16:]
    exp = (_ghash(h, aad, ct) ^ int.from_bytes(_encrypt_block(rk, j0), "big")).to_bytes(16, "big")
    if not hmac.compare_digest(exp, tag):
        raise ValueError("authentication failed")
    return _ctr(rk, j0, ct)
