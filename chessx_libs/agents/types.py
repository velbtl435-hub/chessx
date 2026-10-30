"""Agent type registry + automatic generator (from description, template, existing types, or usage)."""
import json, os, re
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# keyword -> capability (base ChessX packages a type can use)
CAPS = {
    "search": ["search", "pesquis", "research", "find", "busca", "web"],
    "crypto": ["crypto", "cripto", "encrypt", "security", "seguran", "monitor"],
    "i18n": ["translat", "tradu", "language", "idioma"],
    "media": ["media", "mídia", "midia", "download", "image", "video", "music", "audio", "gif"],
    "reversing": ["code", "código", "codigo", "binary", "reverse", "analy", "anális"],
    "voice": ["voice", "voz", "speak", "fala", "listen"],
    "audit": ["audit", "lint", "check", "verific"],
    "scheduler": ["schedul", "agenda", "cron", "periodic", "daily"],
}


@dataclass
class AgentType:
    name: str
    role: str = "generic"
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    prompt: str = ""
    parent: Optional[str] = None
    defaults: Dict = field(default_factory=dict)
    generated: bool = False

    def to_dict(self):
        return asdict(self)


BUILTIN = [
    AgentType("researcher", "researcher", "Researches the web", ["search"], "You research {topic} and cite sources."),
    AgentType("code_analyst", "code_analyst", "Analyzes code and binaries", ["reversing", "audit"], "You analyze code for bugs."),
    AgentType("security_monitor", "security", "Monitors security", ["crypto", "audit", "scheduler"], "You watch for security issues."),
    AgentType("media_collector", "media", "Collects media", ["media", "search"], "You collect media about {topic}."),
    AgentType("translator", "translator", "Translates text", ["i18n"], "You translate text to {lang}."),
]


def slug(text, maxlen=32):
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:maxlen].strip("_") or "agent"


class Registry:
    """Holds agent types; persists generated ones to JSON."""

    def __init__(self, path: str = None, builtins=True):
        self.path = path
        self.types: Dict[str, AgentType] = {}
        if builtins:
            for t in BUILTIN:
                self.types[t.name] = t
        if path and os.path.exists(path):
            self.load()

    def register(self, t: AgentType, overwrite=False) -> AgentType:
        if t.name in self.types and not overwrite:
            raise KeyError("type exists: " + t.name)
        self.types[t.name] = t
        self.save()
        return t

    def get(self, name) -> AgentType:
        return self.types[name]

    def names(self):
        return sorted(self.types)

    def resolve(self, name) -> dict:
        """Flatten inheritance chain (parent first); child overrides. Guards against cyclic parents."""
        chain, seen, t = [], set(), self.types[name]
        while t:
            if t.name in seen:
                raise ValueError("cyclic type inheritance at " + t.name)
            seen.add(t.name); chain.append(t)
            t = self.types.get(t.parent) if t.parent else None
        out = {"capabilities": [], "defaults": {}}
        for t in reversed(chain):
            out["capabilities"] = sorted(set(out["capabilities"]) | set(t.capabilities))
            out["defaults"].update(t.defaults)
            for k in ("role", "description", "prompt"):
                if getattr(t, k):
                    out[k] = getattr(t, k)
        out["name"] = name
        return out

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        data = [t.to_dict() for t in self.types.values() if t.generated or t.name not in {b.name for b in BUILTIN}]
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def load(self):
        with open(self.path, encoding="utf-8") as fh:
            for d in json.load(fh):
                self.types[d["name"]] = AgentType(**d)


def infer_caps(text: str) -> List[str]:
    low = text.lower()
    return sorted(c for c, kws in CAPS.items() if any(k in low for k in kws))


class Generator:
    """Creates new agent types automatically."""

    def __init__(self, registry: Registry):
        self.reg = registry

    def _unique(self, base):
        name, i = base, 2
        while name in self.reg.types:
            name = "%s_%d" % (base, i); i += 1
        return name

    def from_description(self, description: str, name: str = None, parent: str = None) -> AgentType:
        caps = infer_caps(description)
        if parent is None:  # pick best-matching existing type as parent
            best = max(self.reg.types.values(), key=lambda t: len(set(t.capabilities) & set(caps)), default=None)
            if best and set(best.capabilities) & set(caps):
                parent = best.name
        t = AgentType(self._unique(slug(name or description)), slug(description, 16), description, caps,
                      "You are an agent that: %s" % description, parent, generated=True)
        return self.reg.register(t)

    def from_template(self, template: dict, **values) -> AgentType:
        """template values may contain {placeholders} filled from values."""
        d = {k: (v.format(**values) if isinstance(v, str) else v) for k, v in template.items()}
        d.setdefault("name", slug(d.get("description", "agent")))
        d["name"] = self._unique(slug(d["name"]))
        d["generated"] = True
        return self.reg.register(AgentType(**{k: v for k, v in d.items() if k in AgentType.__dataclass_fields__}))

    def derive(self, base: str, name: str, add_caps=(), **overrides) -> AgentType:
        b = self.reg.get(base)
        t = AgentType(self._unique(slug(name)), overrides.get("role", b.role), overrides.get("description", b.description),
                      sorted(set(add_caps)), overrides.get("prompt", ""), base, overrides.get("defaults", {}), True)
        return self.reg.register(t)

    def combine(self, a: str, b: str, name: str = None) -> AgentType:
        ra, rb = self.reg.resolve(a), self.reg.resolve(b)
        t = AgentType(self._unique(slug(name or "%s_%s" % (a, b))), "hybrid", "%s + %s" % (ra.get("description", a), rb.get("description", b)),
                      sorted(set(ra["capabilities"]) | set(rb["capabilities"])), "%s\n%s" % (ra.get("prompt", ""), rb.get("prompt", "")),
                      a, {**ra["defaults"], **rb["defaults"]}, True)
        return self.reg.register(t)

    def from_usage(self, history: List[str], min_count: int = 3) -> List[AgentType]:
        """Generate types for recurring tasks in a usage history (e.g. queries/commands)."""
        counts = Counter()
        for h in history:
            for c in infer_caps(h):
                counts[c] += 1
        out = []
        for cap, n in counts.most_common():
            if n < min_count:
                break
            name = "auto_" + cap
            if name not in self.reg.types:
                out.append(self.reg.register(AgentType(name, cap, "Auto-generated: %d uses of %s" % (n, cap), [cap],
                                                       "You specialize in %s tasks." % cap, generated=True)))
        return out
