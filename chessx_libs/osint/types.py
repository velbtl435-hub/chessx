"""Core OSINT types: Entity (what we look up) and Finding (what a source says about it)."""
import ipaddress, os, re, time
from dataclasses import dataclass, field, asdict
from typing import List

KINDS = ("domain", "ip", "asn", "email", "username", "url", "hash", "phone", "geo", "file", "query")
_DOMAIN = re.compile(r"^(?=.{1,253}$)(?!-)([a-z0-9-]{1,63}\.)+[a-z]{2,63}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HASH = re.compile(r"^(?:[a-f0-9]{32}|[a-f0-9]{40}|[a-f0-9]{64})$")


def normalize(kind: str, value: str) -> str:
    v = (value or "").strip()
    if kind == "domain":
        v = v.lower().rstrip(".")
        if v.startswith("www."):
            v = v[4:]
        try:
            v = v.encode("idna").decode("ascii")
        except UnicodeError:
            pass
    elif kind == "ip":
        v = str(ipaddress.ip_address(v))
    elif kind == "asn":
        v = "AS" + v.upper().removeprefix("AS")
    elif kind in ("email", "hash"):
        v = v.lower()
    elif kind == "username":
        v = v.lstrip("@")
    return v


def detect_kind(value: str) -> str:
    """Best-effort guess of an entity kind from a raw string."""
    v = (value or "").strip()
    if v.startswith(("/", "./", "../", "~/")) or (os.sep in v and os.path.isfile(v)):
        return "file"
    try:
        ipaddress.ip_address(v)
        return "ip"
    except ValueError:
        pass
    if re.fullmatch(r"(?i)AS\d+", v):
        return "asn"
    if v.startswith(("http://", "https://")):
        return "url"
    if _EMAIL.match(v):
        return "email"
    if _HASH.match(v.lower()):
        return "hash"
    if _DOMAIN.match(v.lower().rstrip(".")):
        return "domain"
    return "username"


@dataclass(frozen=True)
class Entity:
    kind: str
    value: str

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError("unknown entity kind %r (one of %s)" % (self.kind, ", ".join(KINDS)))
        object.__setattr__(self, "value", normalize(self.kind, self.value))

    @classmethod
    def parse(cls, value: str, kind: str = None) -> "Entity":
        return cls(kind or detect_kind(value), value)

    def __str__(self):
        return "%s:%s" % (self.kind, self.value)


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class Finding:
    entity: Entity
    source: str
    kind: str                      # e.g. "rdap", "dns.A", "subdomain", "snapshot", "profile"
    title: str
    data: dict = field(default_factory=dict)
    url: str = ""                  # where the fact came from (always set when possible)
    fetched_at: str = field(default_factory=utcnow)
    confidence: float = 0.5        # [0, 1]
    related: List[Entity] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)  # filled by fusion when several sources agree

    def __post_init__(self):
        self.confidence = min(1.0, max(0.0, float(self.confidence)))
        if not self.sources:
            self.sources = [self.source]

    @property
    def key_url(self) -> str:
        """URL used for de-duplication; synthetic osint:// URL when the fact has no natural one."""
        return self.url or "osint://%s/%s/%s" % (self.kind, self.entity.kind, self.title)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["entity"] = str(self.entity)
        d["related"] = [str(e) for e in self.related]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        d = dict(d)
        k, v = d.pop("entity").split(":", 1)
        rel = [Entity(*r.split(":", 1)) for r in d.pop("related", [])]
        return cls(Entity(k, v), related=rel, **d)
