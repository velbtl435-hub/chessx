"""Rule-based intent classifier ("good old fashioned AI").

Fix: commands followed by numbers ("open 3") and multi-term phrases
("convert hex to binary") now classify correctly.
"""
import re
from dataclasses import dataclass, field

BASES = {"bin": 2, "binary": 2, "oct": 8, "octal": 8, "dec": 10, "decimal": 10,
         "hex": 16, "hexadecimal": 16}
_BASE_RE = "(" + "|".join(sorted(BASES, key=len, reverse=True)) + ")"


@dataclass
class Intent:
    name: str
    confidence: float
    args: dict = field(default_factory=dict)


# (name, compiled regex, arg extractor) -- checked in order, most specific first
_PATTERNS = [
    ("convert", re.compile(r"^\s*(?:convert|conv|cvt)\s+(?:(?P<value>[0-9a-fx]+)\s+)?(?:from\s+)?"
                           + _BASE_RE.replace("(", "(?P<src>", 1) + r"\s+(?:to|->|in|into)\s+"
                           + _BASE_RE.replace("(", "(?P<dst>", 1) + r"(?:\s+(?P<value2>[0-9a-fx]+))?\s*$", re.I)),
    ("open", re.compile(r"^\s*(?:open|o|abrir|abre|go|goto)\s*#?(?P<index>\d+)\s*$", re.I)),
    ("save", re.compile(r"^\s*(?:save|salvar|export)\s*(?P<fmt>json|csv|pdf)?\s*$", re.I)),
    ("lang", re.compile(r"^\s*(?:lang|language|idioma)\s+(?P<lang>en|pt|ja|jp)\s*$", re.I)),
    ("refresh", re.compile(r"^\s*(?:refresh|r|reload|auto)\b(?:\s+(?P<seconds>\d+))?\s*$", re.I)),
    ("stats", re.compile(r"^\s*(?:stats|statistics|estat\w*)\s*$", re.I)),
    ("help", re.compile(r"^\s*(?:help|h|\?|ajuda)\s*$", re.I)),
    ("quit", re.compile(r"^\s*(?:quit|exit|q|sair)\s*$", re.I)),
    ("reverse", re.compile(r"^\s*(?:strings|reverse|rev|hexdump)\s+(?P<path>\S+)\s*$", re.I)),
]

INTENTS = [p[0] for p in _PATTERNS] + ["search"]


def classify(text: str) -> Intent:
    text = (text or "").strip()
    if not text:
        return Intent("empty", 1.0)
    for name, rx in _PATTERNS:
        m = rx.match(text)
        if not m:
            continue
        args = {k: v for k, v in m.groupdict().items() if v is not None}
        if name == "convert":
            args["src"] = BASES[args["src"].lower()]
            args["dst"] = BASES[args["dst"].lower()]
            if "value2" in args:
                args["value"] = args.pop("value2")
        if name == "open":
            args["index"] = int(args["index"])
        if name == "refresh" and "seconds" in args:
            args["seconds"] = int(args["seconds"])
        if name == "lang":
            args["lang"] = "ja" if args["lang"].lower() == "jp" else args["lang"].lower()
        return Intent(name, 0.95, args)
    # loose fallback: separate terms anywhere in the sentence
    words = re.findall(r"[a-z]+", text.lower())
    found = [w for w in words if w in BASES]
    if ("convert" in words or "to" in words) and len(found) >= 2:
        return Intent("convert", 0.7, {"src": BASES[found[0]], "dst": BASES[found[1]]})
    return Intent("search", 0.5, {"query": text})
