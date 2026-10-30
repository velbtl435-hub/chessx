"""File-type detector by magic bytes + entropy (packed/encrypted hint)."""
import math
from collections import Counter

MAGIC = [
    (b"\x7fELF", "ELF executable"), (b"MZ", "PE/DOS executable"), (b"\xca\xfe\xba\xbe", "Mach-O fat / Java class"),
    (b"\xcf\xfa\xed\xfe", "Mach-O 64"), (b"%PDF", "PDF"), (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"\xff\xd8\xff", "JPEG"), (b"GIF8", "GIF"), (b"PK\x03\x04", "ZIP/JAR/DOCX/APK"),
    (b"\x1f\x8b", "gzip"), (b"BZh", "bzip2"), (b"\xfd7zXZ\x00", "xz"), (b"7z\xbc\xaf\x27\x1c", "7-Zip"),
    (b"Rar!", "RAR"), (b"SQLite format 3\x00", "SQLite"), (b"\x00asm", "WebAssembly"),
    (b"ID3", "MP3"), (b"OggS", "Ogg"), (b"RIFF", "RIFF (WAV/AVI/WEBP)"), (b"#!", "script (shebang)"),
    (b"dex\n", "Android DEX"),
]
PYC_MAGIC_SUFFIX = b"\r\n"


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    n = len(data)
    return -sum(c / n * math.log2(c / n) for c in Counter(data).values())


def detect(data: bytes) -> dict:
    kind = next((name for sig, name in MAGIC if data.startswith(sig)), None)
    if kind is None and data[2:4] == PYC_MAGIC_SUFFIX:
        kind = "Python bytecode (.pyc)"
    if kind is None:
        try:
            data[:4096].decode("utf-8")
            kind = "text"
        except UnicodeDecodeError:
            kind = "unknown binary"
    e = entropy(data[:65536])
    return {"type": kind, "entropy": round(e, 3), "likely_packed_or_encrypted": e > 7.2, "size": len(data)}


def detect_file(path: str) -> dict:
    with open(path, "rb") as fh:
        return {"path": path, **detect(fh.read())}
