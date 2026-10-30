"""X25519 / Ed25519 with the `cryptography` backend when installed (constant-time), . Without it,
every operation that touches a SECRET key (keypair, *_public, x25519_shared, ed25519_sign) raises
AsymUnavailable unless allow_fallback=True, which uses the non-constant-time pure-Python reference in
x25519.py / ed25519.py and emits InsecureFallbackWarning (CRY-02). ed25519_verify only handles public
data and keeps working (slowly). Same raw 32-byte key formats either way."""
import secrets, warnings
from .aead import InsecureFallbackWarning
import importlib
_px = importlib.import_module(__package__ + ".x25519")  # attribute is shadowed by the function
_pe = importlib.import_module(__package__ + ".ed25519")

try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization as _ser
    from cryptography.exceptions import InvalidSignature
    _RAW = dict(encoding=_ser.Encoding.Raw, format=_ser.PublicFormat.Raw)
    HAVE_CRYPTOGRAPHY = True
except ImportError:
    HAVE_CRYPTOGRAPHY = False


class AsymUnavailable(RuntimeError):
    """No constant-time X25519/Ed25519 backend (pip install cryptography) and no allow_fallback=True."""


def _pure(allow_fallback, what):
    if not allow_fallback:
        raise AsymUnavailable(f"{what} needs the `cryptography` package (pip install cryptography); "
                              "pass allow_fallback=True to use the non-constant-time pure-Python code")
    warnings.warn(f"{what}: using pure-Python fallback (not constant-time); install `cryptography`",
                  InsecureFallbackWarning, stacklevel=3)


def x25519_public(sk: bytes, *, allow_fallback: bool = False) -> bytes:
    if HAVE_CRYPTOGRAPHY:
        return X25519PrivateKey.from_private_bytes(bytes(sk)).public_key().public_bytes(**_RAW)
    _pure(allow_fallback, "X25519")
    return _px.x25519(sk, _px.BASE)


def x25519_keypair(*, allow_fallback: bool = False):
    sk = secrets.token_bytes(32)
    return sk, x25519_public(sk, allow_fallback=allow_fallback)


def x25519_shared(sk: bytes, peer_pk: bytes, *, allow_fallback: bool = False) -> bytes:
    if len(peer_pk) != 32:
        raise ValueError("peer public key must be 32 bytes")
    if HAVE_CRYPTOGRAPHY:
        try:
            return X25519PrivateKey.from_private_bytes(bytes(sk)).exchange(X25519PublicKey.from_public_bytes(peer_pk))
        except ValueError:
            raise ValueError("low-order point") from None
    _pure(allow_fallback, "X25519")
    return _px.x25519_shared(sk, peer_pk)


def ed25519_public(sk: bytes, *, allow_fallback: bool = False) -> bytes:
    if HAVE_CRYPTOGRAPHY:
        return Ed25519PrivateKey.from_private_bytes(bytes(sk)).public_key().public_bytes(**_RAW)
    _pure(allow_fallback, "Ed25519")
    return _pe.public_key(sk)


def ed25519_keypair(*, allow_fallback: bool = False):
    sk = secrets.token_bytes(32)
    return sk, ed25519_public(sk, allow_fallback=allow_fallback)


def ed25519_sign(sk: bytes, msg: bytes, *, allow_fallback: bool = False) -> bytes:
    if HAVE_CRYPTOGRAPHY:
        return Ed25519PrivateKey.from_private_bytes(bytes(sk)).sign(msg)
    _pure(allow_fallback, "Ed25519")
    return _pe.ed25519_sign(sk, msg)


def ed25519_verify(pk: bytes, msg: bytes, sig: bytes) -> bool:
    if len(pk) != 32 or len(sig) != 64:
        return False
    if HAVE_CRYPTOGRAPHY:
        try:
            Ed25519PublicKey.from_public_bytes(pk).verify(sig, msg)
            return True
        except (InvalidSignature, ValueError):
            return False
    return _pe.ed25519_verify(pk, msg, sig)
