"""Byte/text encodings: base32/base32hex (RFC 4648), base58/base58check (Bitcoin),
base64/base64url (padding-tolerant), base85/ascii85, plus per-byte oct/hex/bin. Stdlib only."""
import base64
import binascii
import hashlib
import hmac
import re

B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {c: i for i, c in enumerate(B58_ALPHABET)}
FORMATS = ("hex", "oct", "bin", "base32", "base32hex", "base58", "base58check",
           "base64", "base64url", "base85", "ascii85")


def _b(data) -> bytes:
    return data.encode("utf-8") if isinstance(data, str) else bytes(data)


def _clean(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _pad(s: str, block: int) -> str:
    s = s.rstrip("=")
    return s + "=" * (-len(s) % block)


# ---- base58 ----
def int_to_base58(n: int) -> str:
    if n < 0:
        raise ValueError("negative int")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58_ALPHABET[r] + s
    return s or "1"


def base58_to_int(text: str) -> int:
    n = 0
    for c in text.strip():
        if c not in _B58_INDEX:
            raise ValueError(f"invalid base58 character {c!r}")
        n = n * 58 + _B58_INDEX[c]
    return n


def b58encode(data) -> str:
    data = _b(data)
    zeros = len(data) - len(data.lstrip(b"\0"))
    n = int.from_bytes(data, "big")
    return "1" * zeros + (int_to_base58(n) if n else "")


def b58decode(text: str) -> bytes:
    text = text.strip()
    zeros = len(text) - len(text.lstrip("1"))
    n = base58_to_int(text)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * zeros + body


def _checksum(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]


def b58check_encode(data) -> str:
    data = _b(data)
    return b58encode(data + _checksum(data))


def b58check_decode(text: str) -> bytes:
    raw = b58decode(text)
    if len(raw) < 4:
        raise ValueError("base58check: too short")
    payload, chk = raw[:-4], raw[-4:]
    if not hmac.compare_digest(chk, _checksum(payload)):
        raise ValueError("base58check: bad checksum")
    return payload


# ---- per-byte octal ----
def oct_to_bytes(text: str) -> bytes:
    """Parse '110 145 154', '0o110,0o145' or '\\110\\145' (one octal number per byte)."""
    toks = re.findall(r"[0-7]+", re.sub(r"0o", " ", text.lower()))
    out = []
    for t in toks:
        v = int(t, 8)
        if v > 255:
            raise ValueError(f"octal byte out of range: {t}")
        out.append(v)
    return bytes(out)


def bytes_to_oct(data, sep: str = " ") -> str:
    return sep.join(f"{b:03o}" for b in _b(data))


# ---- generic API ----
def encode(data, fmt: str) -> str:
    d, f = _b(data), fmt.lower()
    if f == "hex":
        return d.hex()
    if f == "oct":
        return bytes_to_oct(d)
    if f == "bin":
        return " ".join(f"{b:08b}" for b in d)
    if f == "base32":
        return base64.b32encode(d).decode()
    if f == "base32hex":
        return base64.b32hexencode(d).decode()
    if f == "base58":
        return b58encode(d)
    if f == "base58check":
        return b58check_encode(d)
    if f == "base64":
        return base64.b64encode(d).decode()
    if f == "base64url":
        return base64.urlsafe_b64encode(d).decode()
    if f == "base85":
        return base64.b85encode(d).decode()
    if f == "ascii85":
        return base64.a85encode(d).decode()
    raise ValueError(f"unknown format {fmt!r}; use one of {FORMATS}")


def decode(text: str, fmt: str) -> bytes:
    f = fmt.lower()
    try:
        if f == "hex":
            from .readers import hex_to_bytes
            return hex_to_bytes(text)
        if f == "oct":
            return oct_to_bytes(text)
        if f == "bin":
            from .readers import bin_to_bytes
            return bin_to_bytes(text)
        if f == "base32":
            return base64.b32decode(_pad(_clean(text), 8), casefold=True)
        if f == "base32hex":
            return base64.b32hexdecode(_pad(_clean(text), 8), casefold=True)
        if f == "base58":
            return b58decode(text)
        if f == "base58check":
            return b58check_decode(text)
        if f == "base64":
            return base64.b64decode(_pad(_clean(text), 4), validate=True)
        if f == "base64url":
            return base64.b64decode(_pad(_clean(text), 4), altchars=b"-_", validate=True)
        if f == "base85":
            return base64.b85decode(_clean(text))
        if f == "ascii85":
            return base64.a85decode(_clean(text))
    except binascii.Error as e:
        raise ValueError(f"invalid {fmt}: {e}") from None
    raise ValueError(f"unknown format {fmt!r}; use one of {FORMATS}")


def transcode(text: str, src: str, dst: str) -> str:
    return encode(decode(text, src), dst)


def encode_all(data, formats=FORMATS) -> dict:
    """Show bytes/text in every encoding (parallel to convert.convert_all for ints)."""
    d = _b(data)
    return {f: encode(d, f) for f in formats}


def detect(text: str) -> list:
    """Return formats that decode `text` and round-trip (best-effort guess, most specific first)."""
    order = ("bin", "oct", "hex", "base58check", "base32hex", "base32", "base58",
             "base64url", "base64", "ascii85", "base85")
    hits = []
    for f in order:
        try:
            decode(text, f)
            hits.append(f)
        except (ValueError, TypeError):
            pass
    return hits
