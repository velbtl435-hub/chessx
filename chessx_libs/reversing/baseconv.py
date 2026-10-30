"""Base conversion suite + hex/binary readers (stdlib only)."""
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
PREFIX = {2: "0b", 8: "0o", 16: "0x"}


def to_base(n: int, base: int) -> str:
    if not 2 <= base <= 36:
        raise ValueError("base must be 2..36")
    if n == 0:
        return "0"
    sign, n, out = ("-" if n < 0 else ""), abs(n), []
    while n:
        n, r = divmod(n, base)
        out.append(DIGITS[r])
    return sign + "".join(reversed(out))


def convert(value: str, src: int, dst: int) -> str:
    v = value.strip().lower()
    if src in PREFIX and v.startswith(PREFIX[src]):
        v = v[2:]
    return to_base(int(v, src), dst)


def hexdump(data: bytes, width: int = 16) -> str:
    lines = []
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        hx = " ".join(f"{b:02x}" for b in chunk).ljust(width * 3 - 1)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{off:08x}  {hx}  |{asc}|")
    return "\n".join(lines)


def bindump(data: bytes, width: int = 4, fmt: str = "bin") -> str:
    f = {"bin": "08b", "oct": "03o", "dec": "3d", "hex": "02x"}[fmt]
    return "\n".join(f"{off:08x}  " + " ".join(format(b, f) for b in data[off:off + width])
                     for off in range(0, len(data), width))
