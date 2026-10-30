DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
BASE_NAMES = {"bin": 2, "binary": 2, "oct": 8, "octal": 8, "dec": 10, "decimal": 10, "hex": 16, "hexadecimal": 16}
PREFIX = {2: "0b", 8: "0o", 16: "0x"}


def _base(b):
    return BASE_NAMES[b.lower()] if isinstance(b, str) else int(b)


def to_base(n: int, base=16, prefix: bool = False, group: int = 0) -> str:
    base = _base(base)
    if not 2 <= base <= 36:
        raise ValueError("base must be 2..36")
    sign, n, s = ("-" if n < 0 else ""), abs(n), ""
    while True:
        n, r = divmod(n, base)
        s = DIGITS[r] + s
        if not n:
            break
    if group:
        s = s.zfill(-(-len(s) // group) * group)
        s = " ".join(s[i:i + group] for i in range(0, len(s), group))
    return sign + (PREFIX.get(base, "") if prefix else "") + s


def from_base(s: str, base=10) -> int:
    base = _base(base)
    s = s.strip().lower().replace("_", "").replace(" ", "")
    neg = s.startswith("-")
    s = s.lstrip("+-")
    if base in PREFIX and s.startswith(PREFIX[base]):
        s = s[2:]
    v = int(s, base)
    return -v if neg else v


def parse_auto(s: str) -> int:
    """Accepts 0x.., 0o.., 0b.., or decimal."""
    return int(s.strip().replace("_", ""), 0)


def convert(value: str, src, dst, prefix: bool = False) -> str:
    return to_base(from_base(value, src), dst, prefix)


def convert_all(value: str, src=None) -> dict:
    n = parse_auto(value) if src is None else from_base(value, src)
    return {"bin": to_base(n, 2), "oct": to_base(n, 8), "dec": str(n), "hex": to_base(n, 16)}
