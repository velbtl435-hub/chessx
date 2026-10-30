"""Source interface + registry with a single switch for non-commercial sources."""
import os
from typing import Dict, Iterable, List, Optional
from .types import Entity, Finding


class SourceError(Exception):
    pass


class Source:
    """One public, keyless OSINT source.

    Subclasses set: name, accepts (entity kinds), host (for rate limiting), rate=(n, per_seconds),
    ttl (cache seconds), license (short text), commercial_ok (False for free-tier/non-commercial terms),
    and implement lookup(entity, client) -> list[Finding] using client.get_json/get_text.
    """
    name = "base"
    accepts: frozenset = frozenset()
    host = ""
    rate = (1, 1.0)
    ttl = 86400
    license = "public"
    commercial_ok = True
    needs_key = False

    def lookup(self, entity: Entity, client) -> List[Finding]:
        raise NotImplementedError

    def safe_lookup(self, entity: Entity, client) -> List[Finding]:
        """Never raises; errors are recorded on client.errors."""
        try:
            return self.lookup(entity, client)
        except Exception as e:  # noqa: BLE001 - one bad source must not stop an investigation
            client.errors.append((self.name, str(entity), "%s: %s" % (type(e).__name__, e)))
            return []


REGISTRY: Dict[str, Source] = {}


def register(cls):
    """Class decorator: instantiate and add to REGISTRY."""
    REGISTRY[cls.name] = cls()
    return cls


def commercial_mode() -> bool:
    """CHESSX_COMMERCIAL=1 means the user runs ChessX commercially: non-commercial sources get disabled."""
    return os.environ.get("CHESSX_COMMERCIAL") == "1"


def sources(kind: str = None, commercial: Optional[bool] = None, names: Iterable[str] = None) -> List[Source]:
    """Registered sources, filtered by entity kind, by name, and by licence.
    commercial=True (or env CHESSX_COMMERCIAL=1 when None) drops every source with commercial_ok=False."""
    if commercial is None:
        commercial = commercial_mode()
    out = []
    for s in REGISTRY.values():
        if names is not None and s.name not in set(names):
            continue
        if kind and kind not in s.accepts:
            continue
        if commercial and not s.commercial_ok:
            continue
        out.append(s)
    return out
