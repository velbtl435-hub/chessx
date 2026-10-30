"""ChaCha20-Poly1305 AEAD (RFC 8439) pure-Python. Slow; fine for small payloads."""
import hmac, struct


def _rotl(v, c):
    return ((v << c) & 0xFFFFFFFF) | (v >> (32 - c))


def _qr(s, a, b, c, d):
    s[a] = (s[a] + s[b]) & 0xFFFFFFFF; s[d] = _rotl(s[d] ^ s[a], 16)
    s[c] = (s[c] + s[d]) & 0xFFFFFFFF; s[b] = _rotl(s[b] ^ s[c], 12)
    s[a] = (s[a] + s[b]) & 0xFFFFFFFF; s[d] = _rotl(s[d] ^ s[a], 8)
    s[c] = (s[c] + s[d]) & 0xFFFFFFFF; s[b] = _rotl(s[b] ^ s[c], 7)


def _block(key, counter, nonce):
    st = list(struct.unpack("<4I", b"expand 32-byte k")) + list(struct.unpack("<8I", key)) + \
        [counter] + list(struct.unpack("<3I", nonce))
    w = st[:]
    for _ in range(10):
        _qr(w, 0, 4, 8, 12); _qr(w, 1, 5, 9, 13); _qr(w, 2, 6, 10, 14); _qr(w, 3, 7, 11, 15)
        _qr(w, 0, 5, 10, 15); _qr(w, 1, 6, 11, 12); _qr(w, 2, 7, 8, 13); _qr(w, 3, 4, 9, 14)
    return struct.pack("<16I", *[(x + y) & 0xFFFFFFFF for x, y in zip(w, st)])


def chacha20(key: bytes, counter: int, nonce: bytes, data: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(data), 64):
        ks = _block(key, counter + i // 64, nonce)
        out += bytes(a ^ b for a, b in zip(data[i:i + 64], ks))
    return bytes(out)


def poly1305(key: bytes, msg: bytes) -> bytes:
    r = int.from_bytes(key[:16], "little") & 0x0ffffffc0ffffffc0ffffffc0fffffff
    s, acc, P = int.from_bytes(key[16:], "little"), 0, (1 << 130) - 5
    for i in range(0, len(msg), 16):
        n = int.from_bytes(msg[i:i + 16] + b"\x01", "little")
        acc = (acc + n) * r % P
    return ((acc + s) & ((1 << 128) - 1)).to_bytes(16, "little")


def _pad16(b):
    return b"\0" * (-len(b) % 16)


def _tag(key, nonce, aad, ct):
    otk = chacha20(key, 0, nonce, bytes(32))
    mac = aad + _pad16(aad) + ct + _pad16(ct) + struct.pack("<QQ", len(aad), len(ct))
    return poly1305(otk, mac)


def chacha20_poly1305_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    if len(key) != 32 or len(nonce) != 12:
        raise ValueError("key must be 32 bytes, nonce 12 bytes")
    ct = chacha20(key, 1, nonce, plaintext)
    return ct + _tag(key, nonce, aad, ct)


def chacha20_poly1305_decrypt(key: bytes, nonce: bytes, data: bytes, aad: bytes = b"") -> bytes:
    ct, tag = data[:-16], data[-16:]
    if not hmac.compare_digest(_tag(key, nonce, aad, ct), tag):
        raise ValueError("authentication failed")
    return chacha20(key, 1, nonce, ct)
