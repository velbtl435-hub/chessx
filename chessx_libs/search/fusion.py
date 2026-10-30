"""Result fusion by normalized URL with multi-engine agreement bonus."""
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
from .base import Result

AGREEMENT_BONUS = 0.25


def norm_url(url: str) -> str:
    p = urllib.parse.urlparse(url)
    host = p.netloc.lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}" + (f"?{p.query}" if p.query else "")


def _unit(x) -> float:
    """Clamp a per-engine score into [0, 1] (guards adapters that return unbounded scores)."""
    try:
        return min(1.0, max(0.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def fuse(lists: List[List[Result]]) -> List[Result]:
    """Merge results by norm_url; a *different* engine agreeing adds its score + AGREEMENT_BONUS, the same
    engine again keeps the max; per-input scores are clamped to [0, 1]. Backend: C core (c/search via
    chessx_libs.native.search) when built, else pure Python - same results either way."""
    flat = [r for results in lists for r in results]
    if not flat:
        return []
    try:
        from ..native import search as _core
    except ImportError:  # pragma: no cover
        _core = None
    if _core is None or _core.backend() != "native":
        return _fuse_py(lists)
    eng_ids: Dict[str, int] = {}
    items = [(eng_ids.setdefault(r.engine, len(eng_ids)), _core.to_fixed(r.score), r.url) for r in flat]
    group, gscore, order = _core.fuse_indices(items)
    merged: List[Result] = [None] * len(gscore)
    for r, g in zip(flat, group):
        m = merged[g]
        if m is None:
            merged[g] = Result(r.title, r.url, r.snippet, r.engine, 0.0, [r.engine])
            continue
        if r.engine not in m.engines:
            m.engines.append(r.engine)
        if len(r.snippet) > len(m.snippet):
            m.snippet = r.snippet
    for g, m in enumerate(merged):
        m.score = gscore[g] / _core.ONE
    return [merged[g] for g in order]


def _fuse_py(lists: List[List[Result]]) -> List[Result]:
    merged: Dict[str, Result] = {}
    for results in lists:
        for r in results:
            k = norm_url(r.url)
            sc = _unit(r.score)
            if k in merged:
                m = merged[k]
                if r.engine not in m.engines:  # bonus only when a *different* engine agrees
                    m.score += sc + AGREEMENT_BONUS
                    m.engines.append(r.engine)
                else:
                    m.score = max(m.score, sc)
                if len(r.snippet) > len(m.snippet):
                    m.snippet = r.snippet
            else:
                merged[k] = Result(r.title, r.url, r.snippet, r.engine, sc, [r.engine])
    return sorted(merged.values(), key=lambda r: r.score, reverse=True)


def multi_search(engines, query: str, limit: int = 10) -> List[Result]:
    with ThreadPoolExecutor(max_workers=max(1, len(engines))) as ex:
        lists = list(ex.map(lambda e: e.safe_search(query, limit), engines))
    return fuse(lists)
