"""ChessX native (C) module loader. Finds libcx_<module>.(so|dylib|dll) and returns a
ctypes.CDLL, or None so callers fall back to pure Python. Never raises on a missing lib.

Search order: $CHESSX_NATIVE_DIR, <repo>/c/build/native, chessx_libs/native/lib.
Set CHESSX_NATIVE=0 to force the pure-Python fallbacks (used by parity tests)."""
import ctypes, os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
EXT = ".dll" if sys.platform == "win32" else ".dylib" if sys.platform == "darwin" else ".so"
ABI_VERSION = 1
_cache = {}


def search_dirs():
    env = os.environ.get("CHESSX_NATIVE_DIR")
    return [d for d in (env, os.path.join(_REPO, "c", "build", "native"), os.path.join(_HERE, "lib")) if d]


def find(module):
    name = "libcx_%s%s" % (module, EXT)
    for d in search_dirs():
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def load(module):
    """ctypes.CDLL for chessx C module `module`, or None (missing, wrong ABI, disabled)."""
    if os.environ.get("CHESSX_NATIVE") == "0":
        return None
    if module in _cache:
        return _cache[module]
    lib, p = None, find(module)
    if p:
        try:
            lib = ctypes.CDLL(p)
            lib.cx_abi_version.restype = ctypes.c_int32
            if lib.cx_abi_version() != ABI_VERSION:
                lib = None
        except (OSError, AttributeError):
            lib = None
    _cache[module] = lib
    return lib


def status():
    return {m: (find(m) if load(m) else None) for m in ("hello_fusion", "search")}


from . import hello_fusion, search  # noqa: E402
__all__ = ["load", "find", "search_dirs", "status", "hello_fusion", "search", "EXT", "ABI_VERSION"]
