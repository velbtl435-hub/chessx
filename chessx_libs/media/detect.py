"""Media type detection: Content-Type header -> magic bytes -> URL extension."""
import mimetypes, os, urllib.parse

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


def ext_for(mime: str, url: str = "") -> str:
    if mime in CT_EXT:
        return CT_EXT[mime]
    e = mimetypes.guess_extension(mime or "") if mime else None
    return e or os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".bin"


def unique_path(directory: str, stem: str, ext: str) -> str:
    """Return a non-existing path, appending -1, -2... on collision."""
    path, i = os.path.join(directory, stem + ext), 1
    while os.path.exists(path):
        path, i = os.path.join(directory, f"{stem}-{i}{ext}"), i + 1
    return path
