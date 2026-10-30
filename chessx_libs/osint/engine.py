"""Investigation driver: run matching sources for an entity, optionally pivot on related entities, fuse."""
import os
from typing import Iterable, List, Optional, Union
from .types import Entity, Finding
from .base import sources as select_sources
from .fusion import fuse_findings
import importlib
importlib.import_module(__package__ + ".sources")  # registers every built-in source (name clashes with base.sources)

PIVOT_KINDS = {"domain", "ip", "asn"}   # never auto-pivot to people (usernames/emails) - must be explicit
MAX_PIVOTS = 25


def default_client(offline=False):
    from .http import Client
    from .cache import Cache, default_dir
    from .audit import AuditLog
    d = default_dir()
    os.makedirs(d, exist_ok=True)
    return Client(cache=Cache(os.path.join(d, "cache.sqlite")), audit=AuditLog(os.path.join(d, "audit.jsonl")),
                  offline=offline)


def investigate(entity: Union[str, Entity], sources: Optional[Iterable[str]] = None, depth: int = 1,
                client=None, commercial: Optional[bool] = None, offline: bool = False,
                kind: Optional[str] = None) -> List[Finding]:
    """Look up `entity` ("example.com", "8.8.8.8", Entity("username", "x")...) in every registered public source
    that accepts its kind and return fused Findings sorted by confidence.

    sources: restrict to these source names. depth>1 pivots on related domain/ip/asn entities (bounded by
    MAX_PIVOTS). commercial=True (or CHESSX_COMMERCIAL=1) drops non-commercial sources. offline=True uses cache
    only. Source errors never raise; they are collected on client.errors."""
    ent = entity if isinstance(entity, Entity) else Entity.parse(entity, kind)
    client = client or default_client(offline)
    if offline:
        client.offline = True
    names = list(sources) if sources is not None else None
    seen, frontier, lists = {ent}, [ent], []
    for level in range(max(1, depth)):
        nxt = []
        for e in frontier:
            if client.audit:
                client.audit.log("investigate", entity=str(e), level=level)
            for src in select_sources(e.kind, commercial=commercial, names=names):
                found = src.safe_lookup(e, client)
                lists.append(found)
                for f in found:
                    for r in f.related:
                        if r.kind in PIVOT_KINDS and r not in seen and len(seen) < MAX_PIVOTS:
                            seen.add(r)
                            nxt.append(r)
        frontier = nxt
        if not frontier:
            break
    return sorted(fuse_findings(lists), key=lambda f: -f.confidence)
