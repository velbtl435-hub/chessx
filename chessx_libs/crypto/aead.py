"""Backend selection + high-level AEAD with automatic nonces and a versioned format.

BACKEND is "cryptography" when that package is importable, else "pure". Without `cryptography` every
AEAD call raises AEADUnavailable unless the caller passes allow_fallback=True, which uses the slow,
NON-constant-time reference code in chacha.py / aesgcm.py and emits an InsecureFallbackWarning
(same opt-in pattern as kdf.argon2id). Outputs are identical either way.

Blob format v1:  b"CX" | version(1) | alg(1) | nonce(12) | ciphertext | tag(16)
The 4-byte header is authenticated (prepended to the caller's AAD)."""
import secrets, warnings
from . import chacha as _pc, aesgcm as _pa

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM, ChaCha20Poly1305 as _CC
    from cryptography.exceptions import InvalidTag as _InvalidTag
    BACKEND = "cryptography"
except ImportError:
    _AESGCM = _CC = None
    _InvalidTag = ValueError
    BACKEND = "pure"

MAGIC, VERSION = b"CX", 1
ALG_CHACHA, ALG_AESGCM = 1, 2
_ALGS = {"chacha20-poly1305": ALG_CHACHA, "chacha20": ALG_CHACHA, "aes-256-gcm": ALG_AESGCM, "aes-gcm": ALG_AESGCM}
NONCE_LEN, TAG_LEN, HEADER_LEN = 12, 16, 4
MIN_BLOB = HEADER_LEN + NONCE_LEN + TAG_LEN


class DecryptError(ValueError):
    pass


class AEADUnavailable(RuntimeError):
    """No constant-time AEAD backend (pip install cryptography) and no allow_fallback=True."""


class InsecureFallbackWarning(RuntimeWarning):
    """Emitted every time the pure-Python (non-constant-time) AEAD fallback is used."""


def _pure(allow_fallback, what):
    if not allow_fallback:
        raise AEADUnavailable(f"{what} needs the `cryptography` package (pip install cryptography); "
                              "pass allow_fallback=True to use the slow, non-constant-time pure-Python code")
    warnings.warn(f"{what}: using pure-Python fallback (not constant-time); install `cryptography`",
                  InsecureFallbackWarning, stacklevel=3)


def _check(key, nonce, sizes):
    if len(key) not in sizes or len(nonce) != NONCE_LEN:
        raise ValueError(f"key must be {'/'.join(map(str, sizes))} bytes, nonce 12 bytes")


def chacha20_poly1305_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    _check(key, nonce, (32,))
    if _CC:
        return _CC(bytes(key)).encrypt(nonce, plaintext, aad or None)
    _pure(allow_fallback, "ChaCha20-Poly1305")
    return _pc.chacha20_poly1305_encrypt(key, nonce, plaintext, aad)


def chacha20_poly1305_decrypt(key: bytes, nonce: bytes, data: bytes, aad: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    _check(key, nonce, (32,))
    if len(data) < TAG_LEN:
        raise ValueError("authentication failed")
    if _CC:
        try:
            return _CC(bytes(key)).decrypt(nonce, data, aad or None)
        except _InvalidTag:
            raise ValueError("authentication failed") from None
    _pure(allow_fallback, "ChaCha20-Poly1305")
    return _pc.chacha20_poly1305_decrypt(key, nonce, data, aad)


def aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    _check(key, nonce, (16, 24, 32))
    if _AESGCM:
        return _AESGCM(bytes(key)).encrypt(nonce, plaintext, aad or None)
    _pure(allow_fallback, "AES-GCM")
    return _pa.aes_gcm_encrypt(key, nonce, plaintext, aad)


def aes_gcm_decrypt(key: bytes, nonce: bytes, data: bytes, aad: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    _check(key, nonce, (16, 24, 32))
    if len(data) < TAG_LEN:
        raise ValueError("authentication failed")
    if _AESGCM:
        try:
            return _AESGCM(bytes(key)).decrypt(nonce, data, aad or None)
        except _InvalidTag:
            raise ValueError("authentication failed") from None
    _pure(allow_fallback, "AES-GCM")
    return _pa.aes_gcm_decrypt(key, nonce, data, aad)


_ENC = {ALG_CHACHA: chacha20_poly1305_encrypt, ALG_AESGCM: aes_gcm_encrypt}
_DEC = {ALG_CHACHA: chacha20_poly1305_decrypt, ALG_AESGCM: aes_gcm_decrypt}


def new_key() -> bytes:
    return secrets.token_bytes(32)


def seal(key: bytes, plaintext: bytes, aad: bytes = b"", alg: str = "chacha20-poly1305", *, allow_fallback: bool = False) -> bytes:
    """Encrypt with a fresh random 96-bit nonce. Random nonces are safe up to ~2^32 messages
    per key; rotate keys well before that."""
    a = _ALGS[alg.lower()]
    if len(key) != 32:
        raise ValueError("key must be 32 bytes")
    header = MAGIC + bytes([VERSION, a])
    nonce = secrets.token_bytes(NONCE_LEN)
    return header + nonce + _ENC[a](key, nonce, plaintext, header + aad, allow_fallback=allow_fallback)


def open_sealed(key: bytes, blob: bytes, aad: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    if len(blob) < MIN_BLOB:
        raise DecryptError("ciphertext too short")
    header, nonce, ct = blob[:HEADER_LEN], blob[HEADER_LEN:HEADER_LEN + NONCE_LEN], blob[HEADER_LEN + NONCE_LEN:]
    if header[:2] != MAGIC:
        raise DecryptError("not a ChessX AEAD blob")
    if header[2] != VERSION:
        raise DecryptError(f"unsupported version {header[2]}")
    if header[3] not in _DEC:
        raise DecryptError(f"unknown algorithm id {header[3]}")
    try:
        return _DEC[header[3]](key, nonce, ct, header + aad, allow_fallback=allow_fallback)
    except ValueError:
        raise DecryptError("authentication failed") from None
