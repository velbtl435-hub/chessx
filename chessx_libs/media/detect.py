"""Media type detection: Content-Type header -> magic bytes -> URL extension."""
import mimetypes, os, re, urllib.parse

CT_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
          "image/svg+xml": ".svg", "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/wav": ".wav",
          "audio/x-wav": ".wav", "audio/wave": ".wav", "audio/flac": ".flac", "video/mp4": ".mp4",
          "video/webm": ".webm", "video/x-matroska": ".mkv", "application/pdf": ".pdf",
          "text/html": ".html", "text/plain": ".txt", "application/json": ".json",
          "application/x-chess-pgn": ".pgn"}
MAGIC = [(b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"GIF87a", "image/gif"),
         (b"GIF89a", "image/gif"), (b"ID3", "audio/mpeg"), (b"\xff\xfb", "audio/mpeg"),
         (b"OggS", "audio/ogg"), (b"fLaC", "audio/flac"), (b"%PDF", "application/pdf"),
         (b"\x1a\x45\xdf\xa3", "video/webm")]
GENERIC = {"", "application/octet-stream", "binary/octet-stream"}


def sniff(head: bytes):
    for sig, ct in MAGIC:
        if head.startswith(sig):
            return ct
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp":
        return "video/mp4"
    return None


def detect_type(content_type=None, head=b"", url=""):
    """Return (mime, source) where source in {'header','magic','extension','unknown'}."""
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in GENERIC:
        return ct, "header"
    m = sniff(head or b"")
    if m:
        return m, "magic"
    g = mimetypes.guess_type(urllib.parse.urlparse(url).path)[0]
    return (g, "extension") if g else ("application/octet-stream", "unknown")


def kind_of(mime: str) -> str:
    top = (mime or "").split("/")[0]
    return top if top in ("image", "audio", "video") else "other"


DANGEROUS_EXT = frozenset(
    ".exe .com .bat .cmd .scr .pif .msi .msp .dll .cpl .jar .js .jse .vbs .vbe .wsf .wsh .hta .ps1 "
    ".psm1 .lnk .reg .sh .bash .command .app .apk .py .pl .rb .php .html .htm .xhtml .svg .shtml "
    ".url .desktop .scf .inf".split())
_WIN_RESERVED = frozenset(["con", "prn", "aux", "nul"] + [f"com{i}" for i in range(1, 10)]
                          + [f"lpt{i}" for i in range(1, 10)])
MAX_STEM = 100


def safe_stem(stem: str) -> str:
    """Filesystem-safe stem: [A-Za-z0-9._-] only, no leading dots, <= MAX_STEM chars,
    Windows reserved device names prefixed with '_'."""
    s = re.sub(r"[^A-Za-z0-9._-]", "_", stem or "").lstrip(".")[:MAX_STEM] or "index"
    if s.split(".")[0].lower() in _WIN_RESERVED:
        s = "_" + s[:MAX_STEM - 1]
    return s


def ext_for(mime: str, url: str = "") -> str:
    """Extension from the detected type only (the URL's extension is never trusted);
    unknown or executable/script-like types become .bin."""
    e = CT_EXT.get(mime) or (mimetypes.guess_extension(mime) if mime else None) or ".bin"
    e = e.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", e) or e in DANGEROUS_EXT:
        return ".bin"
    return e


def reserve_path(directory: str, stem: str, ext: str, attempts: int = 10000):
    """Atomically create a new file (O_EXCL) named <safe stem>[-N]<ext> inside directory.
    Returns (path, fd); the caller owns fd. Raises if the path would escape directory."""
    stem, root = safe_stem(stem), os.path.realpath(directory)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    for i in range(attempts):
        path = os.path.join(root, f"{stem}{'-%d' % i if i else ''}{ext}")
        if os.path.dirname(os.path.realpath(path)) != root:
            raise ValueError(f"unsafe filename escapes {directory!r}: {path!r}")
        try:
            return path, os.open(path, flags, 0o644)
        except FileExistsError:
            continue
    raise FileExistsError(f"no free name for {stem}{ext} in {directory}")


def unique_path(directory: str, stem: str, ext: str) -> str:
    """Compat helper: reserve (create empty) and return a safe, non-colliding path."""
    path, fd = reserve_path(directory, stem, ext)
    os.close(fd)
    return path
