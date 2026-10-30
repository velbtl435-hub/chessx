"""HOTP (RFC 4226) / TOTP (RFC 6238) for 2FA -- stdlib only."""
import base64, hashlib, hmac, secrets, struct, time


def new_secret(nbytes: int = 20) -> str:
    return base64.b32encode(secrets.token_bytes(nbytes)).decode().rstrip("=")


def _key(secret) -> bytes:
    if isinstance(secret, bytes):
        return secret
    s = secret.upper().replace(" ", "")
    return base64.b32decode(s + "=" * (-len(s) % 8))


def hotp(secret, counter: int, digits: int = 6, algo=hashlib.sha1) -> str:
    h = hmac.new(_key(secret), struct.pack(">Q", counter), algo).digest()
    o = h[-1] & 0x0F
    code = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** digits
    return str(code).zfill(digits)


def totp(secret, t: float = None, step: int = 30, digits: int = 6, algo=hashlib.sha1) -> str:
    return hotp(secret, int((time.time() if t is None else t) // step), digits, algo)


def verify_totp(secret, code: str, window: int = 1, t: float = None, step: int = 30) -> bool:
    now = time.time() if t is None else t
    return any(hmac.compare_digest(totp(secret, now + w * step, step), code) for w in range(-window, window + 1))
