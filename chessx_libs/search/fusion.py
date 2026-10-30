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


def fuse(lists: List[List[Result]]) -> List[Result]:
    merged: Dict[str, Result] = {}
    for results in lists:
        for r in results:
            k = norm_url(r.url)
            if k in merged:
                m = merged[k]
                if r.engine not in m.engines:  # bonus only when a *different* engine agrees
                    m.score += r.score + AGREEMENT_BONUS
                    m.engines.append(r.engine)
                else:
                    m.score = max(m.score, r.score)
                if len(r.snippet) > len(m.snippet):
                    m.snippet = r.snippet
            else:
                merged[k] = Result(r.title, r.url, r.snippet, r.engine, r.score, [r.engine])
    return sorted(merged.values(), key=lambda r: r.score, reverse=True)


def multi_search(engines, query: str, limit: int = 10) -> List[Result]:
    with ThreadPoolExecutor(max_workers=max(1, len(engines))) as ex:
        lists = list(ex.map(lambda e: e.safe_search(query, limit), engines))
    return fuse(lists)
