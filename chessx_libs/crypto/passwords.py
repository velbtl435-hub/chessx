"""Password hashing (storage/verification) with PHC strings -- separate from raw KDF.

hash_password -> "$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>" (random 16-byte salt).
Backends: argon2-cffi PasswordHasher, else cryptography Argon2id; strict by default.
scrypt ("$scrypt$ln=15,r=8,p=1$...") only with allow_fallback=True."""
import base64, hashlib, hmac, secrets
from . import kdf

T_COST, M_COST, PARALLELISM, HASH_LEN, SALT_LEN = 3, 65536, 4, 32, 16

try:
    import argon2 as _argon2
    from argon2 import PasswordHasher as _PH
    _ph = _PH(time_cost=T_COST, memory_cost=M_COST, parallelism=PARALLELISM,
              hash_len=HASH_LEN, salt_len=SALT_LEN, type=_argon2.Type.ID)
except ImportError:
    _ph = None


def _b64(b):
    return base64.b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.b64decode(s + "=" * (-len(s) % 4))


def _pw(password):
    if isinstance(password, str):
        password = password.encode("utf-8")
    if not password:
        raise ValueError("empty password")
    return password


def backend() -> str:
    return "argon2-cffi" if _ph else kdf.ARGON2_BACKEND


def hash_password(password, allow_fallback: bool = False) -> str:
    pw = _pw(password)
    if _ph:
        return _ph.hash(pw)
    salt = secrets.token_bytes(SALT_LEN)
    if kdf.ARGON2_BACKEND == "cryptography":
        h = kdf.argon2id(pw, salt, HASH_LEN, T_COST, M_COST, PARALLELISM)
        return f"$argon2id$v=19$m={M_COST},t={T_COST},p={PARALLELISM}${_b64(salt)}${_b64(h)}"
    if not allow_fallback:
        raise kdf.Argon2Unavailable("hash_password needs argon2-cffi (pip install argon2-cffi); "
                                    "pass allow_fallback=True to accept scrypt")
    h = hashlib.scrypt(pw, salt=salt, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=HASH_LEN)
    return f"$scrypt$ln=15,r=8,p=1${_b64(salt)}${_b64(h)}"


def _parse(phc):
    parts = phc.split("$")
    if len(parts) == 6 and parts[1] == "argon2id":
        params = dict(kv.split("=") for kv in parts[3].split(","))
        return "argon2id", {k: int(v) for k, v in params.items()}, _unb64(parts[4]), _unb64(parts[5])
    if len(parts) == 5 and parts[1] == "scrypt":
        params = dict(kv.split("=") for kv in parts[2].split(","))
        return "scrypt", {k: int(v) for k, v in params.items()}, _unb64(parts[3]), _unb64(parts[4])
    raise ValueError("unrecognised password hash format")


def verify_password(phc: str, password) -> bool:
    """Constant-time verification. Returns False on mismatch or malformed hash."""
    try:
        pw = _pw(password)
        if _ph and phc.startswith("$argon2"):
            try:
                return _ph.verify(phc, pw)
            except (_argon2.exceptions.VerificationError, _argon2.exceptions.InvalidHashError):
                return False
        kind, p, salt, h = _parse(phc)
        if kind == "argon2id":
            got = kdf.argon2id(pw, salt, len(h), p["t"], p["m"], p["p"])
        else:
            got = hashlib.scrypt(pw, salt=salt, n=2 ** p["ln"], r=p["r"], p=p["p"],
                                 maxmem=256 * 1024 * 1024, dklen=len(h))
        return hmac.compare_digest(got, h)
    except (ValueError, KeyError, kdf.Argon2Unavailable):
        return False


def check_needs_rehash(phc: str) -> bool:
    """True if the hash uses weaker/older params or a non-Argon2id scheme."""
    if _ph and phc.startswith("$argon2"):
        try:
            return _ph.check_needs_rehash(phc)
        except Exception:
            return True
    try:
        kind, p, salt, h = _parse(phc)
    except (ValueError, KeyError):
        return True
    if kind != "argon2id":
        return backend() != "none"
    return (p.get("m", 0) < M_COST or p.get("t", 0) < T_COST or p.get("p", 0) < PARALLELISM
            or len(salt) < SALT_LEN or len(h) < HASH_LEN)
