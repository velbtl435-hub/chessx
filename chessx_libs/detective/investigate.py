import hashlib, os, re, stat, struct, time, urllib.parse, zipfile
from ..reversing.detector import detect
from ..reversing.origin import origin_hints
from ..reversing.strings import indicators


def hashes(data: bytes) -> dict:
    return {a: hashlib.new(a, data).hexdigest() for a in ("md5", "sha1", "sha256")}


def _ts(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def _png_text(data):
    out, i = {}, 8
    while i + 8 <= len(data):
        ln, typ = struct.unpack(">I4s", data[i:i + 8])
        if typ == b"tEXt":
            k, _, v = data[i + 8:i + 8 + ln].partition(b"\0")
            out[k.decode("latin-1")] = v.decode("latin-1")
        if typ == b"IEND":
            break
        i += 12 + ln
    return out


def _pdf_info(data):
    keys = ("Title", "Author", "Creator", "Producer", "CreationDate", "ModDate")
    out = {}
    for k in keys:
        m = re.search(rb"/" + k.encode() + rb"\s*\(([^)]*)\)", data)
        if m:
            out[k] = m.group(1).decode("latin-1")
    return out


def _zip_info(path):
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        meta = {"entries": len(infos), "first_files": [i.filename for i in infos[:10]]}
        if "docProps/core.xml" in z.namelist():
            core = z.read("docProps/core.xml").decode("utf-8", "replace")
            for tag in ("creator", "lastModifiedBy", "created", "modified"):
                m = re.search(r"<[^>]*" + tag + r"[^>]*>([^<]*)<", core)
                if m:
                    meta[tag] = m.group(1)
        return meta


def _jpeg_exif_tags(data):
    i = data.find(b"Exif\0\0")
    if i < 0:
        return {}
    found = re.findall(rb"[\x20-\x7e]{4,40}", data[i:i + 4096])
    return {"exif_strings": [s.decode() for s in found[:12]]}


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
    xattrs = {}
    if hasattr(os, "listxattr"):
        try:
            for a in os.listxattr(path):  # e.g. user.xdg.origin.url set by browsers
                xattrs[a] = os.getxattr(path, a).decode("utf-8", "replace")
        except OSError:
            pass
    meta["xattrs"] = xattrs
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


def investigate(path: str) -> dict:
    with open(path, "rb") as fh:
        data = fh.read()
    meta = metadata(path)
    h = hashes(data)
    iocs = indicators(data)
    hints = origin_hints(data)
    return {"metadata": meta, "hashes": h, "indicators": iocs, "origin_hints": hints,
            "provenance": provenance_chain(meta, iocs, hints),
            "reverse_search": reverse_search_links(h, os.path.basename(path))}
