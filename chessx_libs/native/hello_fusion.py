"""Proof module for the C/WASI pipeline: CRC-32 and (id, score) fusion.
Uses c/hello_fusion via ctypes when built, else identical pure-Python code."""
import ctypes
from . import load as _load

I32_MIN, I64_MIN, I64_MAX = -2 ** 31, -2 ** 63, 2 ** 63 - 1


def _lib():
    lib = _load("hello_fusion")
    if lib is not None and not getattr(lib, "_cx_typed", False):
        lib.cx_crc32.restype = ctypes.c_uint32
        lib.cx_crc32.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.cx_fuse.restype = ctypes.c_int32
        lib.cx_fuse.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int64), ctypes.c_int32,
                                ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int64)]
        lib._cx_typed = True
    return lib


def backend():
    return "native" if _lib() is not None else "python"


# ---- pure-Python reference (same algorithm as hello_fusion.c) ----
def crc32_py(data: bytes) -> int:
    c = 0xFFFFFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ (0xEDB88320 if c & 1 else 0)
    return c ^ 0xFFFFFFFF


def _wrap64(v):  # C int64 wraparound, so overflow behaves the same everywhere
    return (v + 2 ** 63) % 2 ** 64 - 2 ** 63


def fuse_py(pairs):
    order, acc = [], {}
    for i, s in pairs:
        if i not in acc:
            order.append(i); acc[i] = 0
        acc[i] = _wrap64(acc[i] + s)
    return sorted(((i, acc[i]) for i in order), key=lambda p: (-p[1], p[0]))


# ---- public API ----
def crc32(data) -> int:
    data = data.encode() if isinstance(data, str) else bytes(data)
    lib = _lib()
    return lib.cx_crc32(data, len(data)) if lib else crc32_py(data)


def fuse(pairs):
    """[(id, score), ...] -> deduped [(id, summed_score)] sorted by score desc, id asc."""
    pairs = [(int(i), int(s)) for i, s in pairs]
    lib = _lib()
    if lib is None or not pairs:
        return fuse_py(pairs)
    n = len(pairs)
    ids = (ctypes.c_int32 * n)(*[i for i, _ in pairs]); sc = (ctypes.c_int64 * n)(*[s for _, s in pairs])
    oi = (ctypes.c_int32 * n)(); os_ = (ctypes.c_int64 * n)()
    m = lib.cx_fuse(ids, sc, n, oi, os_)
    return [(oi[k], os_[k]) for k in range(m)]
