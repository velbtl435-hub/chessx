"""Encryption for stored data.

Sealed box (public-key, anonymous sender):
    b"CXSB" | ver(1) | eph_pk(32) | aead.seal(...)
    key = HKDF-SHA256(X25519(eph_sk, recipient_pk), salt=eph_pk||recipient_pk,
                      info=b"chessx/sealedbox/v1|" + context)
    AAD  = header || eph_pk || context   (context binds the ciphertext to e.g. a file/record id)

Envelope (symmetric KEK -> random per-object DEK):
    b"CXEV" | ver(1) | len(wrapped_dek)(2, BE) | wrapped_dek | aead.seal(dek, data)
    Rotating the KEK only re-wraps the DEK (rewrap_envelope), the bulk data is untouched."""
import secrets, struct
from . import aead
from .asym import x25519_keypair, x25519_shared, x25519_public
from .kdf import hkdf

SB_MAGIC, EV_MAGIC, VERSION = b"CXSB", b"CXEV", 1


def _sb_key(shared, eph_pk, rpk, context):
    return hkdf(shared, salt=eph_pk + rpk, info=b"chessx/sealedbox/v1|" + context, length=32)


def seal_box(recipient_pk: bytes, plaintext: bytes, context: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    eph_sk, eph_pk = x25519_keypair(allow_fallback=allow_fallback)
    key = _sb_key(x25519_shared(eph_sk, recipient_pk, allow_fallback=allow_fallback), eph_pk, recipient_pk, context)
    header = SB_MAGIC + bytes([VERSION])
    return header + eph_pk + aead.seal(key, plaintext, header + eph_pk + context, allow_fallback=allow_fallback)


def open_box(recipient_sk: bytes, blob: bytes, context: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    if len(blob) < 5 + 32 + aead.MIN_BLOB:
        raise aead.DecryptError("sealed box too short")
    header, eph_pk, body = blob[:5], blob[5:37], blob[37:]
    if header[:4] != SB_MAGIC or header[4] != VERSION:
        raise aead.DecryptError("not a v1 sealed box")
    try:
        shared = x25519_shared(recipient_sk, eph_pk, allow_fallback=allow_fallback)
    except ValueError:
        raise aead.DecryptError("invalid ephemeral key") from None
    key = _sb_key(shared, eph_pk, x25519_public(recipient_sk, allow_fallback=allow_fallback), context)
    return aead.open_sealed(key, body, header + eph_pk + context, allow_fallback=allow_fallback)


def _ev_aad(context, part):
    return EV_MAGIC + bytes([VERSION]) + part + b"|" + context


def envelope_encrypt(kek: bytes, data: bytes, context: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    dek = secrets.token_bytes(32)
    wrapped = aead.seal(kek, dek, _ev_aad(context, b"dek"), allow_fallback=allow_fallback)
    body = aead.seal(dek, data, _ev_aad(context, b"data"), allow_fallback=allow_fallback)
    return EV_MAGIC + bytes([VERSION]) + struct.pack(">H", len(wrapped)) + wrapped + body


def _ev_split(blob):
    if len(blob) < 7 or blob[:4] != EV_MAGIC or blob[4] != VERSION:
        raise aead.DecryptError("not a v1 envelope")
    n = struct.unpack(">H", blob[5:7])[0]
    wrapped, body = blob[7:7 + n], blob[7 + n:]
    if len(wrapped) != n or len(body) < aead.MIN_BLOB:
        raise aead.DecryptError("truncated envelope")
    return wrapped, body


def envelope_decrypt(kek: bytes, blob: bytes, context: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    wrapped, body = _ev_split(blob)
    dek = aead.open_sealed(kek, wrapped, _ev_aad(context, b"dek"), allow_fallback=allow_fallback)
    return aead.open_sealed(dek, body, _ev_aad(context, b"data"), allow_fallback=allow_fallback)


def rewrap_envelope(old_kek: bytes, new_kek: bytes, blob: bytes, context: bytes = b"", *, allow_fallback: bool = False) -> bytes:
    """KEK rotation: re-wrap the DEK under new_kek without re-encrypting the data."""
    wrapped, body = _ev_split(blob)
    dek = aead.open_sealed(old_kek, wrapped, _ev_aad(context, b"dek"), allow_fallback=allow_fallback)
    w2 = aead.seal(new_kek, dek, _ev_aad(context, b"dek"), allow_fallback=allow_fallback)
    return EV_MAGIC + bytes([VERSION]) + struct.pack(">H", len(w2)) + w2 + body
