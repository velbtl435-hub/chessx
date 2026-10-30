"""Bridge to chessx_libs.search fusion: Finding <-> search.Result, de-dup by URL, cross-source agreement bonus."""
from typing import List
from ..search.base import Result
from ..search.fusion import fuse, norm_url
from .types import Finding


def to_result(f: Finding) -> Result:
    return Result(f.title, f.key_url, "", f.source, f.confidence)


def fuse_findings(lists: List[List[Finding]]) -> List[Finding]:
    """Merge findings from several sources. Same normalized URL (or same synthetic osint:// key) => one Finding,
    with all contributing sources in .sources, merged data/related, and the search fusion score
    (sum of confidences + agreement bonus) re-clamped to [0, 1] as confidence. Sorted by score."""
    by_key, order = {}, []
    for lst in lists:
        for f in lst:
            k = norm_url(f.key_url)
            if k not in by_key:
                by_key[k] = Finding(f.entity, f.source, f.kind, f.title, dict(f.data), f.url, f.fetched_at,
                                    f.confidence, list(f.related), [f.source])
                order.append(k)
            else:
                m = by_key[k]
                if f.source not in m.sources:
                    m.sources.append(f.source)
                for kk, vv in f.data.items():
                    m.data.setdefault(kk, vv)
                for r in f.related:
                    if r not in m.related:
                        m.related.append(r)
    fused = fuse([[to_result(f) for f in lst] for lst in lists])
    score = {norm_url(r.url): r.score for r in fused}
    out = [by_key[k] for k in order]
    for f in out:
        s = score.get(norm_url(f.key_url), f.confidence)
        f.confidence = round(min(1.0, s / max(1, len(f.sources)) + 0.1 * (len(f.sources) - 1)), 3)
    return sorted(out, key=lambda f: (-score.get(norm_url(f.key_url), 0), f.title))
