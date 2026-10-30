"""Password-protected keystore: keys wrapped (AEAD) by a KEK derived with Argon2id.

File (JSON, written atomically, mode 0600):
  {"format": "chessx-keystore", "version": 1,
   "kdf": {"alg": "argon2id", "salt": b64, "t": 3, "m": 65536, "p": 4},
   "check": b64(seal(kek, b"chessx-keystore", aad)),
   "keys": {name: {"active": n, "versions": {"n": {"wrapped": b64, "created": ts}}}}}
Each wrapped key's AAD binds the store path-independent name + version, so blobs cannot be swapped.

Zeroization is BEST-EFFORT: the KEK and returned keys live in bytearrays that `zeroize()` / `close()` overwrite,
but Python may already have copied them (bytes() conversions, the cryptography/argon2 C layers, the str password,
GC, swap, core dumps). It reduces exposure; it does not guarantee secrets are gone from memory."""
import base64, json, os, secrets, tempfile, time
from . import aead
from .kdf import argon2id

FORMAT, VERSION, CHECK = "chessx-keystore", 1, b"chessx-keystore"
DEFAULT_KDF = {"t": 3, "m": 65536, "p": 4}


class KeystoreError(ValueError):
    pass


def zeroize(buf):
    """Overwrite a bytearray/memoryview in place (best-effort, see module docstring)."""
    if isinstance(buf, (bytearray, memoryview)):
        for i in range(len(buf)):
            buf[i] = 0


def _e(b):
    return base64.b64encode(bytes(b)).decode()


def _d(s):
    return base64.b64decode(s)


def _aad(name, ver):
    return f"{FORMAT}|v{VERSION}|{name}|{ver}".encode()


def _keyring():
    try:
        import keyring
    except ImportError:
        raise RuntimeError("optional OS keyring support needs `pip install keyring`") from None
    return keyring


def keyring_store_password(service: str, account: str, password: str):
    _keyring().set_password(service, account, password)


def keyring_get_password(service: str, account: str) -> str:
    pw = _keyring().get_password(service, account)
    if pw is None:
        raise KeystoreError("no password stored in the OS keyring for that service/account")
    return pw


class Keystore:
    def __init__(self, path, data, kek):
        self.path, self._data, self._kek = path, data, kek

    # ---- lifecycle ----
    @classmethod
    def create(cls, path, password, kdf_params=None, overwrite=False):
        if os.path.exists(path) and not overwrite:
            raise FileExistsError(path)
        params = dict(DEFAULT_KDF, **(kdf_params or {}))
        salt = secrets.token_bytes(16)
        kek = bytearray(argon2id(password, salt, 32, params["t"], params["m"], params["p"]))
        data = {"format": FORMAT, "version": VERSION, "kdf": dict(alg="argon2id", salt=_e(salt), **params),
                "check": _e(aead.seal(bytes(kek), CHECK, _aad("", 0))), "keys": {}}
        ks = cls(path, data, kek)
        ks.save()
        return ks

    @classmethod
    def open(cls, path, password=None, keyring_service=None, keyring_account=None):
        if password is None:
            if not keyring_service:
                raise KeystoreError("password or keyring_service required")
            password = keyring_get_password(keyring_service, keyring_account or path)
        with open(path) as fh:
            data = json.load(fh)
        if data.get("format") != FORMAT or data.get("version") != VERSION:
            raise KeystoreError("unsupported keystore format")
        k = data["kdf"]
        kek = bytearray(argon2id(password, _d(k["salt"]), 32, k["t"], k["m"], k["p"]))
        try:
            aead.open_sealed(bytes(kek), _d(data["check"]), _aad("", 0))
        except aead.DecryptError:
            zeroize(kek)
            raise KeystoreError("wrong password or corrupted keystore") from None
        return cls(path, data, kek)

    def save(self):
        d = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".ks-")
        try:
            os.chmod(tmp, 0o600)
            with os.fdopen(fd, "w") as fh:
                json.dump(self._data, fh, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def close(self):
        zeroize(self._kek)
        self._kek = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _need_open(self):
        if self._kek is None:
            raise KeystoreError("keystore is closed")
        return bytes(self._kek)

    # ---- keys ----
    def names(self):
        return sorted(self._data["keys"])

    def versions(self, name):
        return sorted(int(v) for v in self._data["keys"][name]["versions"])

    def put(self, name, key=None, nbytes=32) -> int:
        """Add a new version of `name` (random if key is None), make it active, save. Returns version."""
        kek = self._need_open()
        if "|" in name:
            raise ValueError("'|' not allowed in key names")
        key = secrets.token_bytes(nbytes) if key is None else bytes(key)
        ent = self._data["keys"].setdefault(name, {"active": 0, "versions": {}})
        ver = max([0] + [int(v) for v in ent["versions"]]) + 1
        ent["versions"][str(ver)] = {"wrapped": _e(aead.seal(kek, key, _aad(name, ver))), "created": int(time.time())}
        ent["active"] = ver
        self.save()
        return ver

    rotate = put  # rotation = new active version; old versions stay readable until retired

    def get(self, name, version=None) -> bytearray:
        """Return the key as a bytearray (call zeroize() on it when done)."""
        kek = self._need_open()
        if name not in self._data["keys"]:
            raise KeyError(name)
        ent = self._data["keys"][name]
        ver = ent["active"] if version is None else int(version)
        try:
            w = ent["versions"][str(ver)]["wrapped"]
        except KeyError:
            raise KeyError(f"{name} v{ver}") from None
        try:
            return bytearray(aead.open_sealed(kek, _d(w), _aad(name, ver)))
        except aead.DecryptError:
            raise KeystoreError(f"{name} v{ver}: integrity check failed") from None

    def active_version(self, name) -> int:
        return self._data["keys"][name]["active"]

    def retire(self, name, version):
        ent = self._data["keys"][name]
        if int(version) == ent["active"]:
            raise KeystoreError("cannot retire the active version; rotate first")
        del ent["versions"][str(int(version))]
        self.save()

    def delete(self, name):
        del self._data["keys"][name]
        self.save()

    def change_password(self, new_password, kdf_params=None):
        """Re-derive the KEK with a fresh salt and re-wrap every key version."""
        old = self._need_open()
        params = dict(DEFAULT_KDF, **(kdf_params or {}))
        salt = secrets.token_bytes(16)
        new = bytearray(argon2id(new_password, salt, 32, params["t"], params["m"], params["p"]))
        for name, ent in self._data["keys"].items():
            for v, item in ent["versions"].items():
                raw = bytearray(aead.open_sealed(old, _d(item["wrapped"]), _aad(name, int(v))))
                item["wrapped"] = _e(aead.seal(bytes(new), bytes(raw), _aad(name, int(v))))
                zeroize(raw)
        self._data["kdf"] = dict(alg="argon2id", salt=_e(salt), **params)
        self._data["check"] = _e(aead.seal(bytes(new), CHECK, _aad("", 0)))
        zeroize(self._kek)
        self._kek = new
        self.save()
