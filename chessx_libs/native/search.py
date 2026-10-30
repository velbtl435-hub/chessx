"""Search core backend: URL normalisation, fusion and ranking.
Uses c/search (libcx_search) via ctypes when built, else the identical pure-Python reference below.
chessx_libs.search.fusion.fuse() calls fuse_indices(); its public API and results do not change
(scores pass through fixed point 1e-9, so they may differ from pure floats by < 1e-8)."""
import ctypes
from . import load as _load

ONE = 1_000_000_000           # CX_SCORE_ONE
BONUS = 250_000_000           # CX_AGREEMENT_BONUS (0.25)


def _lib():
    lib = _load("search")
    if lib is not None and not getattr(lib, "_cx_typed", False):
        P32, P64 = ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int64)
        lib.cx_norm_url.restype = ctypes.c_int32
        lib.cx_norm_url.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
        lib.cx_search_fuse.restype = ctypes.c_int32
        lib.cx_search_fuse.argtypes = [ctypes.c_char_p, P32, P32, P32, P64, ctypes.c_int32, P32, P64, P32]
        lib.cx_search_rank.restype = ctypes.c_int32
        lib.cx_search_rank.argtypes = [P64, ctypes.c_int32, P32]
        lib._cx_typed = True
    return lib


def backend():
    return "native" if _lib() is not None else "python"


def native_ok(url: str) -> bool:
    """C handles ASCII URLs without IPv6 brackets (those keep exact urllib semantics in Python)."""
    return url.isascii() and "[" not in url and "]" not in url


def to_fixed(x) -> int:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0
    return int(round(min(1.0, max(0.0, x)) * ONE)) if x == x else 0


# ---- pure-Python reference (same algorithm as search.c) ----
def norm_url_py(url: str) -> str:
    from ..search.fusion import norm_url
    return norm_url(url)


def rank_py(scores):
    return sorted(range(len(scores)), key=lambda i: -scores[i])  # stable


def fuse_py(items):
    """items: [(engine_id, fixed_score, url)] -> (groups_of_input, group_scores, ranked_group_order)."""
    keys, gscore, group, seen = {}, [], [], set()
    for e, s, url in items:
        s = min(ONE, max(0, int(s)))
        k = norm_url_py(url)
        if k not in keys:
            keys[k] = len(gscore)
            gscore.append(s)
        else:
            g = keys[k]
            if (g, e) not in seen:
                gscore[g] += s + BONUS
            else:
                gscore[g] = max(gscore[g], s)
        group.append(keys[k])
        seen.add((keys[k], e))
    return group, gscore, rank_py(gscore)


# ---- public API ----
def norm_url(url: str) -> str:
    lib = _lib()
    if lib is None or not native_ok(url):
        return norm_url_py(url)
    b = url.encode()
    out = ctypes.create_string_buffer(len(b) + 1)
    m = lib.cx_norm_url(b, len(b), out, len(b))
    return out.raw[:m].decode() if m >= 0 else norm_url_py(url)


def rank(scores):
    lib = _lib()
    n = len(scores)
    if lib is None or not n:
        return rank_py(list(scores))
    o = (ctypes.c_int32 * n)()
    lib.cx_search_rank((ctypes.c_int64 * n)(*scores), n, o)
    return list(o)


def fuse_indices(items):
    """Same contract as fuse_py; native when every URL is native_ok."""
    items = [(int(e), int(s), u) for e, s, u in items]
    lib = _lib()
    if lib is None or not items or not all(native_ok(u) for _, _, u in items):
        return fuse_py(items)
    n = len(items)
    enc = [u.encode() for _, _, u in items]
    offs, p = [], 0
    for b in enc:
        offs.append(p); p += len(b)
    I32, I64 = ctypes.c_int32 * n, ctypes.c_int64 * n
    grp, gs, order = I32(), I64(), I32()
    m = lib.cx_search_fuse(b"".join(enc), I32(*offs), I32(*[len(b) for b in enc]), I32(*[e for e, _, _ in items]),
                           I64(*[s for _, s, _ in items]), n, grp, gs, order)
    if m < 0:
        return fuse_py(items)
    return list(grp), list(gs[:m]), list(order[:m])
