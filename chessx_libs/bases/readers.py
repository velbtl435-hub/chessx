import re


def hexdump(data: bytes, width: int = 16, offset: int = 0) -> str:
    lines = []
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        hx = " ".join(f"{b:02x}" for b in chunk)
        if width >= 16:
            hx = hx[:3 * 8] + " " + hx[3 * 8:]
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset + off:08x}  {hx.ljust(width * 3)} |{asc}|")
    return "\n".join(lines)


def bindump(data: bytes, width: int = 4, fmt: str = "bin", offset: int = 0) -> str:
    f = {"bin": "08b", "oct": "03o", "dec": "3d", "hex": "02x"}[fmt]
    return "\n".join(f"{offset + o:08x}  " + " ".join(format(b, f) for b in data[o:o + width])
                     + "  |" + "".join(chr(b) if 32 <= b < 127 else "." for b in data[o:o + width]) + "|"
                     for o in range(0, len(data), width))


def hex_to_bytes(text: str) -> bytes:
    """Parse '48 65 6c', '0x48,0x65', '48656c', or an xxd-style dump back to bytes."""
    rows = []
    for line in text.splitlines():
        line = line.split("|")[0]
        line = re.sub(r"^\s*[0-9a-fA-F]{6,}[:\s]\s", "", line)  # drop offset column
        rows.append(re.sub(r"0x|[^0-9a-fA-F]", "", line))
    h = "".join(rows)
    if len(h) % 2:
        raise ValueError("odd number of hex digits")
    return bytes.fromhex(h)


def bin_to_bytes(text: str) -> bytes:
    bits = re.sub(r"[^01]", "", text)
    if len(bits) % 8:
        raise ValueError("bit count not a multiple of 8")
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def read_file(path: str, start: int = 0, length: int = 256, mode: str = "hex") -> str:
    with open(path, "rb") as fh:
        fh.seek(start)
        data = fh.read(length)
    return hexdump(data, offset=start) if mode == "hex" else bindump(data, fmt="bin", offset=start)
