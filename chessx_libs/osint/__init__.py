"""chessx_libs.osint: public, keyless, legal OSINT sources with caching, rate limiting, audit log and fusion.

Public API (stable):
    investigate(entity, sources=None, depth=1, client=None, commercial=None, offline=False, kind=None)
        -> List[Finding]   fused, sorted by confidence; source errors land on client.errors
    cli.main(argv=None) -> int          same as `python -m chessx_libs.osint ...`
    password_count(password, client) -> int   Pwned Passwords k-anonymity (only 5 SHA-1 chars leave the box)
    Entity, Finding, detect_kind, Source, register, sources(kind, commercial, names), REGISTRY,
    Client, Cache, AuditLog, Case, CaseStore, fuse_findings, commercial_mode
Licences: sources with commercial_ok=False (internetdb, hackertarget, urlscan, ipapi) are dropped when
commercial=True or env CHESSX_COMMERCIAL=1. Data dir: CHESSX_OSINT_DIR (default ~/.chessx/osint).
"""
from .types import Entity, Finding, detect_kind
from .base import Source, SourceError, REGISTRY, register, sources, commercial_mode
from .fusion import fuse_findings
from .http import Client
from .cache import Cache
from .audit import AuditLog
from .engine import investigate
from .case import Case, CaseStore
from .sources.pwned import password_count
from . import cli

__all__ = ["investigate", "cli", "password_count", "Entity", "Finding", "detect_kind", "Source", "SourceError",
           "REGISTRY", "register", "sources", "commercial_mode", "fuse_findings", "Client", "Cache", "AuditLog",
           "Case", "CaseStore"]
