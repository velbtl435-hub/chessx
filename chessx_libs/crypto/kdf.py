"""HKDF (RFC 5869, stdlib hmac) and Argon2id (argon2-cffi or cryptography; scrypt only on explicit opt-in)."""
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


class Argon2Unavailable(RuntimeError):
    pass


try:  # optional: pip install argon2-cffi
    from argon2.low_level import hash_secret_raw, Type as _T
    ARGON2_BACKEND = "argon2-cffi"
except ImportError:
    hash_secret_raw = None
    try:  # cryptography >= 44 ships Argon2id
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id as _CryArgon2id
        ARGON2_BACKEND = "cryptography"
    except ImportError:
        _CryArgon2id = None
        ARGON2_BACKEND = "none"

MIN_SALT = 16


def argon2id(password: bytes, salt: bytes, length: int = 32, t_cost: int = 3,
             m_cost_kib: int = 65536, parallelism: int = 4, allow_fallback: bool = False) -> bytes:
    """Raw Argon2id key derivation (RFC 9106). Backends: argon2-cffi, then cryptography.
    Strict by default: raises Argon2Unavailable if neither is installed; with
    allow_fallback=True uses hashlib.scrypt instead (NOT Argon2 -- outputs differ).
    For password *storage* use crypto.passwords.hash_password instead."""
    if isinstance(password, str):
        password = password.encode()
    if len(salt) < 8:
        raise ValueError("salt must be at least 8 bytes (16+ recommended)")
    if hash_secret_raw:
        return hash_secret_raw(password, salt, t_cost, m_cost_kib, parallelism, length, _T.ID)
    if _CryArgon2id:
        return _CryArgon2id(salt=salt, length=length, iterations=t_cost, lanes=parallelism,
                            memory_cost=m_cost_kib).derive(password)
    if not allow_fallback:
        raise Argon2Unavailable("Argon2id needs argon2-cffi or cryptography>=44 (pip install argon2-cffi); "
                                "pass allow_fallback=True to accept scrypt")
    return hashlib.scrypt(password, salt=salt, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=length)
