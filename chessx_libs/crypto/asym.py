"""X25519 / Ed25519 with the `cryptography` backend when installed (constant-time), else the
pure-Python reference in x25519.py / ed25519.py. Same raw 32-byte key formats either way."""
import secrets
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


def x25519_public(sk: bytes) -> bytes:
    if HAVE_CRYPTOGRAPHY:
        return X25519PrivateKey.from_private_bytes(bytes(sk)).public_key().public_bytes(**_RAW)
    return _px.x25519(sk, _px.BASE)


def x25519_keypair():
    sk = secrets.token_bytes(32)
    return sk, x25519_public(sk)


def x25519_shared(sk: bytes, peer_pk: bytes) -> bytes:
    if len(peer_pk) != 32:
        raise ValueError("peer public key must be 32 bytes")
    if HAVE_CRYPTOGRAPHY:
        try:
            return X25519PrivateKey.from_private_bytes(bytes(sk)).exchange(X25519PublicKey.from_public_bytes(peer_pk))
        except ValueError:
            raise ValueError("low-order point") from None
    return _px.x25519_shared(sk, peer_pk)


def ed25519_public(sk: bytes) -> bytes:
    if HAVE_CRYPTOGRAPHY:
        return Ed25519PrivateKey.from_private_bytes(bytes(sk)).public_key().public_bytes(**_RAW)
    return _pe.public_key(sk)


def ed25519_keypair():
    sk = secrets.token_bytes(32)
    return sk, ed25519_public(sk)


def ed25519_sign(sk: bytes, msg: bytes) -> bytes:
    if HAVE_CRYPTOGRAPHY:
        return Ed25519PrivateKey.from_private_bytes(bytes(sk)).sign(msg)
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
