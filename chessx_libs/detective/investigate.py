"""Detective: reverse search of file origins, metadata and provenance chain.

Hashes, format metadata (PDF/PNG/ZIP-OOXML/JPEG EXIF), xattrs and embedded-payload
carving are delegated to ``chessx_libs.reversing.provenance`` (single implementation).
If that import fails, a minimal stdlib fallback keeps the public API working
(hashes + filesystem metadata; format parsers return nothing). Static analysis only.
"""
import hashlib, importlib, os, stat, time, urllib.parse, zipfile

try:
    # module (not the same-named function re-exported by chessx_libs.reversing)
    _pv = importlib.import_module("..reversing.provenance", __package__)
    from ..reversing.detector import detect
    from ..reversing.origin import origin_hints
    from ..reversing.strings import indicators
    HAVE_REVERSING = True
except Exception:  # reversing missing/broken: degrade gracefully
    _pv = None
    HAVE_REVERSING = False

    def detect(data):
        return {"type": "unknown", "size": len(data)}

    def origin_hints(data):
        return []

    def indicators(data):
        return {"urls": [], "emails": [], "ips": []}


def hashes(data: bytes) -> dict:
    """md5/sha1/sha256 hex digests (same keys as before)."""
    if _pv is not None:
        h = _pv.hashes(data)
        return {a: h[a] for a in ("md5", "sha1", "sha256")}
    return {a: hashlib.new(a, data).hexdigest() for a in ("md5", "sha1", "sha256")}


def _ts(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def _png_text(data):
    return _pv.png_text(data, limit=None) if _pv else {}


def _pdf_info(data):
    return _pv.pdf_info(data, limit=None) if _pv else {}


def _zip_info(path):
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        meta = {"entries": len(infos), "first_files": [i.filename for i in infos[:10]]}
        if _pv:
            meta.update(_pv.office_core_props(z))
        return meta


def _jpeg_exif_tags(data):
    found = _pv.jpeg_exif_strings(data) if _pv else []
    return {"exif_strings": found} if found else {}


def _xattrs(path):
    if _pv:
        return _pv.read_xattrs(path, limit=None)
    out = {}
    if hasattr(os, "listxattr"):
        try:
            for a in os.listxattr(path):
                out[a] = os.getxattr(path, a).decode("utf-8", "replace")
        except OSError:
            pass
    return out


def metadata(path: str) -> dict:
    st = os.stat(path)
    with open(path, "rb") as fh:
        data = fh.read()
    meta = {"path": os.path.abspath(path), "size": st.st_size, "mode": stat.filemode(st.st_mode),
            "modified": _ts(st.st_mtime), "accessed": _ts(st.st_atime), "changed": _ts(st.st_ctime),
            **detect(data)}
    try:
        if data.startswith(b"\x89PNG"):
            meta["png_text"] = _png_text(data)
        elif data.startswith(b"%PDF"):
            meta["pdf_info"] = _pdf_info(data)
        elif data.startswith(b"PK\x03\x04"):
            meta["zip"] = _zip_info(path)
        elif data.startswith(b"\xff\xd8"):
            meta.update(_jpeg_exif_tags(data))
    except Exception as e:
        meta["parse_error"] = str(e)
    meta["xattrs"] = _xattrs(path)
    zone = path + ":Zone.Identifier"  # Windows download origin (NTFS ADS)
    if os.name == "nt" and os.path.exists(zone):
        meta["zone_identifier"] = open(zone, encoding="utf-8", errors="replace").read()
    return meta


def reverse_search_links(h: dict, name: str) -> dict:
    q = urllib.parse.quote
    return {"virustotal": f"https://www.virustotal.com/gui/file/{h['sha256']}",
            "web_hash": f"https://duckduckgo.com/?q={q(h['sha256'])}",
            "web_name": f"https://duckduckgo.com/?q={q(chr(34) + name + chr(34))}",
            "archive": f"https://web.archive.org/web/*/{q(name)}*"}


def provenance_chain(meta: dict, iocs: dict, hints: list) -> list:
    chain = []
    for h in hints:
        chain.append(("built-with", h["toolchain"], h["evidence"]))
    for k in ("pdf_info", "png_text", "zip"):
        for kk, v in (meta.get(k) or {}).items():
            if kk in ("Creator", "Producer", "Author", "Software", "creator", "lastModifiedBy", "created"):
                chain.append(("authored", kk, v))
    for k, v in meta.get("xattrs", {}).items():
        if "origin" in k or "referrer" in k:
            chain.append(("downloaded-from", k, v))
    if "zone_identifier" in meta:
        chain.append(("downloaded-from", "Zone.Identifier", meta["zone_identifier"].strip()))
    for u in iocs.get("urls", [])[:5]:
        chain.append(("references", "url", u))
    chain.append(("filesystem", "modified", meta["modified"]))
    return chain


def embedded_payloads(data: bytes) -> list:
    """Payloads carved after offset 0 (zip/pdf/png/gzip/7z/pe/elf/pem); [] without reversing."""
    try:
        return _pv.embedded_resources(data) if _pv else []
    except Exception:
        return []


def investigate(path: str) -> dict:
    with open(path, "rb") as fh:
        data = fh.read()
    meta = metadata(path)
    h = hashes(data)
    iocs = indicators(data)
    hints = origin_hints(data)
    return {"metadata": meta, "hashes": h, "indicators": iocs, "origin_hints": hints,
            "provenance": provenance_chain(meta, iocs, hints),
            "reverse_search": reverse_search_links(h, os.path.basename(path)),
            "embedded_payloads": embedded_payloads(data)}  # additive key, kept last
