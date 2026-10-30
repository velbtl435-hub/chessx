"""HKDF (RFC 5869, stdlib hmac) and Argon2id (optional dep; scrypt fallback)."""
import hashlib, hmac


def hkdf_extract(salt: bytes, ikm: bytes, hash_=hashlib.sha256) -> bytes:
    return hmac.new(salt or b"\0" * hash_().digest_size, ikm, hash_).digest()


def hkdf_expand(prk: bytes, info: bytes = b"", length: int = 32, hash_=hashlib.sha256) -> bytes:
    out, t, i = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([i]), hash_).digest()
        out += t
        i += 1
    return out[:length]


def hkdf(ikm: bytes, salt: bytes = b"", info: bytes = b"", length: int = 32) -> bytes:
    return hkdf_expand(hkdf_extract(salt, ikm), info, length)


try:  # optional: pip install argon2-cffi
    from argon2.low_level import hash_secret_raw, Type as _T
    ARGON2_BACKEND = "argon2-cffi"
except ImportError:
    hash_secret_raw = None
    ARGON2_BACKEND = "scrypt-fallback"


def argon2id(password: bytes, salt: bytes, length: int = 32, t_cost: int = 3,
             m_cost_kib: int = 65536, parallelism: int = 4) -> bytes:
    """Argon2id if argon2-cffi is installed; otherwise STUB fallback to hashlib.scrypt
    (memory-hard, stdlib, but NOT Argon2 -- outputs differ). Check ARGON2_BACKEND."""
    if hash_secret_raw:
        return hash_secret_raw(password, salt, t_cost, m_cost_kib, parallelism, length, _T.ID)
    return hashlib.scrypt(password, salt=salt, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=length)
