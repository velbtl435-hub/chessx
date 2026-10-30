"""HOTP (RFC 4226) / TOTP (RFC 6238) 2FA -- stdlib only.

Also: otpauth:// provisioning URIs (+ optional QR via `qrcode`), a replay-protected
TOTPVerifier with failure lockout, and single-use hashed backup codes."""
import base64, contextlib, hashlib, hmac, json, os, re, secrets, struct, tempfile, threading, time
from urllib.parse import quote, urlencode
from ._filelock import locked as _locked

_ALGOS = {"SHA1": hashlib.sha1, "SHA256": hashlib.sha256, "SHA512": hashlib.sha512}


def new_secret(nbytes: int = 20) -> str:
    return base64.b32encode(secrets.token_bytes(nbytes)).decode().rstrip("=")


def _key(secret) -> bytes:
    if isinstance(secret, (bytes, bytearray)):
        return bytes(secret)
    s = secret.upper().replace(" ", "")
    return base64.b32decode(s + "=" * (-len(s) % 8))


def _algo(algo):
    return _ALGOS[algo.upper().replace("-", "")] if isinstance(algo, str) else algo


def hotp(secret, counter: int, digits: int = 6, algo=hashlib.sha1) -> str:
    h = hmac.new(_key(secret), struct.pack(">Q", counter), _algo(algo)).digest()
    o = h[-1] & 0x0F
    code = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** digits
    return str(code).zfill(digits)


def totp(secret, t: float = None, step: int = 30, digits: int = 6, algo=hashlib.sha1) -> str:
    return hotp(secret, int((time.time() if t is None else t) // step), digits, algo)


def _valid_format(code, digits) -> bool:
    return isinstance(code, str) and len(code) == digits and code.isascii() and code.isdigit()


def match_totp(secret, code: str, window: int = 1, t: float = None, step: int = 30,
               digits: int = 6, algo=hashlib.sha1):
    """Return the matching time-step counter (int) or None. Checks every window slot."""
    code = code.replace(" ", "") if isinstance(code, str) else code
    if not _valid_format(code, digits):
        return None
    now = int((time.time() if t is None else t) // step)
    hit = None
    for c in range(now - window, now + window + 1):
        if hmac.compare_digest(hotp(secret, c, digits, algo), code) and hit is None:
            hit = c
    return hit


def verify_totp(secret, code: str, window: int = 1, t: float = None, step: int = 30,
                digits: int = 6, algo=hashlib.sha1) -> bool:
    """Stateless check (no replay protection -- use TOTPVerifier for logins)."""
    return match_totp(secret, code, window, t, step, digits, algo) is not None


def provisioning_uri(secret, account: str, issuer: str = "ChessX", digits: int = 6,
                     period: int = 30, algorithm: str = "SHA1") -> str:
    """otpauth://totp/Issuer:account?secret=..&issuer=..&algorithm=..&digits=..&period=.."""
    sec = secret if isinstance(secret, str) else base64.b32encode(secret).decode()
    sec = sec.upper().replace(" ", "").rstrip("=")
    if ":" in issuer:
        raise ValueError("issuer must not contain ':'")
    label = quote(f"{issuer}:{account}" if issuer else account, safe=":@")
    q = {"secret": sec}
    if issuer:
        q["issuer"] = issuer
    q.update(algorithm=algorithm.upper(), digits=digits, period=period)
    return f"otpauth://totp/{label}?{urlencode(q, quote_via=quote)}"


def provisioning_qr(uri: str, path: str = None):
    """Render a QR for the URI if `qrcode` is installed; returns ASCII art (or saves a PNG
    when path is given). Raises RuntimeError if qrcode is missing."""
    try:
        import qrcode
    except ImportError:
        raise RuntimeError("pip install qrcode[pil] for QR output") from None
    qr = qrcode.QRCode(border=1)
    qr.add_data(uri)
    if path:
        qr.make_image().save(path)
        return path
    import io
    buf = io.StringIO()
    qr.print_ascii(out=buf)
    return buf.getvalue()


class LockedOut(Exception):
    pass


class JSONFileStore:
    """Persistent, cross-process TOTP state (CRY-04): a JSON file (0600) read-modify-written under an
    exclusive file lock with an atomic replace, so replay protection and lockouts survive restarts and
    are shared by every worker on the same host. Pass it as TOTPVerifier(store=JSONFileStore(path))."""

    def __init__(self, path):
        self.path = path

    def _load(self):
        try:
            with open(self.path) as fh:
                return json.load(fh)
        except FileNotFoundError:
            return {}

    @contextlib.contextmanager
    def transaction(self):
        with _locked(self.path):
            data = self._load()
            yield data
            d = os.path.dirname(os.path.abspath(self.path))
            fd, tmp = tempfile.mkstemp(dir=d, prefix=".totp-")
            try:
                os.chmod(tmp, 0o600)
                with os.fdopen(fd, "w") as fh:
                    json.dump(data, fh)
                os.replace(tmp, self.path)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise

    # read-only dict-like access
    def get(self, account, default=None):
        return self._load().get(account, default)

    def __getitem__(self, account):
        return self._load()[account]

    def __contains__(self, account):
        return account in self._load()


_NEW_STATE = {"last_step": -1, "failures": 0, "locked_until": 0}


class TOTPVerifier:
    """Replay-protected TOTP check + lockout. `store` is any dict-like (account -> state); an in-memory
    dict (default) is thread-safe but per-process and lost on restart. For several workers or restarts
    use JSONFileStore(path) (or any store with a `transaction()` context manager yielding a mutable
    dict): the whole check-and-update then runs under a cross-process lock."""

    def __init__(self, store=None, window: int = 1, step: int = 30, digits: int = 6,
                 algo=hashlib.sha1, max_failures: int = 5, lockout_seconds: int = 300):
        self.store = {} if store is None else store
        self.window, self.step, self.digits, self.algo = window, step, digits, algo
        self.max_failures, self.lockout_seconds = max_failures, lockout_seconds
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def _tx(self):
        with self._lock:
            if hasattr(self.store, "transaction"):
                with self.store.transaction() as data:
                    yield data
            else:
                yield self.store

    def _state(self, account):
        return self.store.setdefault(account, dict(_NEW_STATE))

    def locked(self, account, now: float = None) -> bool:
        now = time.time() if now is None else now
        st = self.store.get(account) or _NEW_STATE
        return st["locked_until"] > now

    def verify(self, account, secret, code, t: float = None) -> bool:
        now = time.time() if t is None else t
        with self._tx() as data:
            st = dict(data.get(account) or _NEW_STATE)
            if st["locked_until"] > now:
                raise LockedOut(f"{account}: locked for {int(st['locked_until'] - now)}s")
            c = match_totp(secret, code, self.window, now, self.step, self.digits, self.algo)
            if c is not None and c > st["last_step"]:
                st.update(last_step=c, failures=0)
                data[account] = st
                return True
            st["failures"] += 1
            if st["failures"] >= self.max_failures:
                st.update(failures=0, locked_until=now + self.lockout_seconds)
            data[account] = st
            return False


# ---- backup / recovery codes ----
_BC_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def _norm_code(code: str) -> str:
    return re.sub(r"[\s-]", "", code).lower()


def _hash_code(code: str, salt: bytes) -> str:
    return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", _norm_code(code).encode(), salt, 100_000).hex()


def generate_backup_codes(n: int = 10, length: int = 10):
    """Return (plain_codes_to_show_once, hashes_to_store). ~49 bits/code at length 10."""
    plain = []
    for _ in range(n):
        c = "".join(secrets.choice(_BC_ALPHABET) for _ in range(length))
        plain.append(c[:length // 2] + "-" + c[length // 2:])
    return plain, [_hash_code(c, secrets.token_bytes(16)) for c in plain]


def use_backup_code(hashes: list, code: str) -> bool:
    """Constant-time check against every stored hash; removes the used one (single-use).
    Mutates `hashes` in place -- persist it afterwards."""
    hit = None
    for i, h in enumerate(hashes):
        salt, _, _d = h.partition("$")
        if hmac.compare_digest(_hash_code(code, bytes.fromhex(salt)), h) and hit is None:
            hit = i
    if hit is None:
        return False
    del hashes[hit]
    return True
