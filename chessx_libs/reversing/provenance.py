"""Expanded detective mode (#11): provenance trail, embedded metadata, fuzzy hashes,
per-section entropy and toolchain fingerprinting for stripped binaries.

Static analysis only: the sample is read as bytes and never executed.
"""
import hashlib, io, os, re, struct, time, zipfile
from .detector import entropy
from .formats import parse_headers

PACKED_ENTROPY = 7.2
DATA_ENTROPY = 7.6  # data/resource sections legitimately hold compressed blobs (icons, Go tables)
DATA_SECTIONS = {".rodata", ".data", ".noptrdata", ".rsrc", ".rdata", ".gopclntab", ".typelink", ".data.rel.ro"}


# --- hashes -----------------------------------------------------------------
def hashes(data: bytes) -> dict:
    out = {a: hashlib.new(a, data).hexdigest() for a in ("md5", "sha1", "sha256")}
    out["ssdeep"] = out["tlsh"] = None
    for mod in ("ssdeep", "ppdeep"):  # optional fuzzy hashes
        try:
            out["ssdeep"] = __import__(mod).hash(data); break
        except Exception:
            pass
    try:
        import tlsh
        h = tlsh.hash(data)
        out["tlsh"] = h if h and h != "TNULL" else None
    except Exception:
        pass
    return out


# --- filesystem provenance --------------------------------------------------
def _ts(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))


def fs_trail(path: str) -> dict:
    st = os.stat(path)
    out = {"path": os.path.abspath(path), "size": st.st_size, "mtime": _ts(st.st_mtime), "ctime": _ts(st.st_ctime),
           "atime": _ts(st.st_atime), "owner_uid": st.st_uid, "mode": oct(st.st_mode & 0o7777), "xattrs": {}, "sidecars": {}}
    if hasattr(os, "listxattr"):  # e.g. user.xdg.origin.url / referrer.url set by browsers & wget
        try:
            for k in os.listxattr(path):
                out["xattrs"][k] = os.getxattr(path, k)[:512].decode("utf-8", "replace")
        except OSError:
            pass
    for suffix in (":Zone.Identifier", ".Zone.Identifier"):  # Windows MOTW copied as a sidecar file
        sc = path + suffix
        if os.path.isfile(sc):
            with open(sc, "r", errors="replace") as fh:
                out["sidecars"][suffix] = dict(re.findall(r"^(\w+)=(.*)$", fh.read(4096), re.M))
    return out


# --- embedded metadata ------------------------------------------------------
def _elf_notes(data: bytes, hdr: dict) -> dict:
    out = {}
    for s in hdr.get("sections", []):
        blob = data[s["offset"]:s["offset"] + s["size"]]
        if s["name"] == ".note.gnu.build-id" and len(blob) > 16:
            out["build_id"] = blob[16:].hex()
        elif s["name"] == ".note.go.buildid" and len(blob) > 16:
            out["go_build_id"] = blob[16:].rstrip(b"\x00").decode("latin-1")
        elif s["name"] == ".note.ABI-tag" and len(blob) >= 32:
            os_, a, b, c = struct.unpack_from("<IIII", blob, 16)
            out["abi_tag"] = f"{['Linux','GNU','Solaris','FreeBSD'][os_] if os_ < 4 else os_} {a}.{b}.{c}"
        elif s["name"] == ".gnu_debuglink":
            out["debuglink"] = blob.split(b"\x00")[0].decode("latin-1")
        elif s["name"] == ".comment":
            out["comment"] = sorted({x.decode("latin-1") for x in blob.split(b"\x00") if x})
    return out


VERSION_KEYS = ("CompanyName", "FileDescription", "FileVersion", "InternalName", "LegalCopyright",
                "OriginalFilename", "ProductName", "ProductVersion")


def pe_version_info(data: bytes) -> dict:
    """VS_VERSIONINFO StringFileInfo pairs (UTF-16LE key\\0 value\\0) from the resource blob."""
    out = {}
    for k in VERSION_KEYS:
        key = k.encode("utf-16-le") + b"\x00\x00"
        i = data.find(key)
        if i < 0:
            continue
        j = i + len(key)
        j += (-j) % 4  # DWORD alignment
        end = data.find(b"\x00\x00", j)
        while end > 0 and (end - j) % 2:
            end = data.find(b"\x00\x00", end + 1)
        if end > j:
            out[k] = data[j:end].decode("utf-16-le", "replace")[:256]
    return out


def _pdf_info(data):
    return {k: m.group(1).decode("latin-1")[:200] for k in ("Title", "Author", "Creator", "Producer", "CreationDate", "ModDate")
            for m in [re.search(rb"/" + k.encode() + rb"\s*\(([^)]*)\)", data)] if m}


def _png_text(data):
    out, i = {}, 8
    while i + 8 <= len(data):
        ln, typ = struct.unpack(">I4s", data[i:i + 8])
        if typ == b"tEXt":
            k, _, v = data[i + 8:i + 8 + ln].partition(b"\x00")
            out[k.decode("latin-1")] = v.decode("latin-1")[:200]
        if typ == b"IEND":
            break
        i += 12 + ln
    return out


EMBEDDED = [(b"PK\x03\x04", "zip"), (b"%PDF-", "pdf"), (b"\x89PNG\r\n\x1a\n", "png"), (b"\x1f\x8b\x08", "gzip"),
            (b"7z\xbc\xaf\x27\x1c", "7z"), (b"MZ\x90\x00", "pe"), (b"\x7fELF\x02\x01\x01", "elf"),
            (b"-----BEGIN CERTIFICATE-----", "pem-cert"), (b"\x30\x82", None)]


def embedded_resources(data: bytes, limit: int = 32) -> list:
    """Carve signatures of payloads embedded past offset 0 (installers, droppers, bundled assets)."""
    out = []
    for sig, kind in EMBEDDED:
        if not kind:
            continue
        start = 1
        while len(out) < limit:
            i = data.find(sig, start)
            if i < 0:
                break
            item = {"offset": i, "type": kind}
            if kind == "zip":
                try:
                    z = zipfile.ZipFile(io.BytesIO(data[i:]))
                    item["entries"] = z.namelist()[:20]; item["comment"] = z.comment.decode("latin-1")[:200]
                except Exception:
                    pass
            elif kind == "pdf":
                item["info"] = _pdf_info(data[i:i + 1_000_000])
            out.append(item)
            start = i + len(sig)
    return sorted(out, key=lambda d: d["offset"])


def metadata(data: bytes, hdr: dict) -> dict:
    out = {}
    if hdr.get("format") == "ELF":
        out.update(_elf_notes(data, hdr))
    if hdr.get("format") == "PE":
        out["pe_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(hdr["timestamp"])) if hdr.get("timestamp") else None
        out["version_info"] = pe_version_info(data)
        m = re.search(rb"[A-Za-z]:\\[^\x00]{3,200}\.pdb", data)
        out["pdb_path"] = m.group().decode("latin-1") if m else None
    if data.startswith(b"%PDF"):
        out["pdf"] = _pdf_info(data)
    if data.startswith(b"\x89PNG"):
        out["png_text"] = _png_text(data)
    if data.startswith(b"PK\x03\x04"):
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
            out["zip"] = {"entries": len(z.namelist()), "comment": z.comment.decode("latin-1")[:200],
                          "first": z.namelist()[:10], "latest_entry_date": max((i.date_time for i in z.infolist()), default=None)}
        except Exception:
            pass
    return out


# --- entropy per section ----------------------------------------------------
def section_entropy(data: bytes, hdr: dict) -> list:
    out = []
    for s in hdr.get("sections", []):
        blob = data[s["offset"]:s["offset"] + s["size"]] if s["size"] and s["offset"] < len(data) else b""
        if not blob:
            continue
        e = round(entropy(blob), 3)
        out.append({"name": s["name"], "size": len(blob), "entropy": e, "suspicious": len(blob) > 512 and e > (DATA_ENTROPY if s["name"] in DATA_SECTIONS else PACKED_ENTROPY)})
    return out


# --- toolchain fingerprint (works on stripped binaries) ----------------------
SECTION_FP = {".gopclntab": "Go", ".go.buildinfo": "Go", ".note.go.buildid": "Go", "UPX0": "UPX packer",
              "UPX1": "UPX packer", ".rustc": "Rust", ".ndata": "NSIS installer", ".themida": "Themida packer",
              ".vmp0": "VMProtect", ".aspack": "ASPack packer", ".petite": "Petite packer", ".mpress1": "MPRESS packer",
              "__go_buildinfo": "Go", ".CRT": "MSVC/MinGW CRT", ".tls": None}
BYTE_FP = [(rb"\xff Go buildinf:", "Go"), (rb"runtime\.gopanic|runtime\.morestack", "Go"),
           (rb"/rustc/[0-9a-f]{40}", "Rust"), (rb"rust_panic|core::panicking|RUST_BACKTRACE", "Rust"),
           (rb"GCC: \([^)]*\) [\d.]+", "GCC"), (rb"clang version [\d.]+", "Clang/LLVM"),
           (rb"MEI\x0c\x0b\x0a\x0b\x0e|pyi-runtime-tmpdir|_MEIPASS", "PyInstaller"), (rb"__nuitka|Nuitka", "Nuitka"),
           (rb"UPX!", "UPX packer"), (rb"Rich[\x00-\xff]{4}", None), (rb"Nim(Main|_)|nimGC", "Nim"),
           (rb"\bdruntime\.|_d_run_main|__dmd_", "D"), (rb"GHC\.|ghczm", "Haskell/GHC"),
           (rb"Zig |zig_panic|std\.debug\.panic", "Zig"), (rb"__swift5_|swift_", "Swift"),
           (rb"Delphi|Borland|Embarcadero", "Delphi/Borland"), (rb"mscoree\.dll|_CorExeMain", ".NET")]
FUNC_FP = [(r"^(sym\.)?runtime\.", "Go"), (r"_ZN.*17h[0-9a-f]{16}E$|rust_begin_unwind", "Rust"),
           (r"__libc_start_main|__libc_csu_init", "glibc C runtime"), (r"__mingw_|___mingw", "MinGW"),
           (r"__security_init_cookie|__scrt_", "MSVC")]


def fingerprint(data: bytes, hdr: dict, functions=None) -> list:
    """Evidence-weighted toolchain guesses: section names, byte patterns, r2/angr function names."""
    score, ev = {}, {}

    def hit(name, why, w):
        if name:
            score[name] = score.get(name, 0) + w
            ev.setdefault(name, []).append(why)
    for s in hdr.get("sections", []):
        hit(SECTION_FP.get(s["name"]), f"section {s['name']}", 3)
    for pat, name in BYTE_FP:
        m = re.search(pat, data)
        if m:
            hit(name, f"bytes {m.group()[:40]!r} @0x{m.start():x}", 2)
    for imp in hdr.get("imports", []):
        if re.search(r"msvcr\d+|vcruntime|ucrtbase", imp, re.I):
            hit("MSVC", f"import {imp}", 2)
        if "mscoree" in imp.lower():
            hit(".NET", f"import {imp}", 3)
    for f in list(functions or []) + [{"name": i} for i in hdr.get("imports", [])]:
        for pat, name in FUNC_FP:
            if re.search(pat, f.get("name") or ""):
                hit(name, f"function {f['name']}", 1); break
    if hdr.get("format") == "ELF" and hdr.get("stripped"):
        hit("(stripped)", "no .symtab", 0)
    total = sum(score.values()) or 1
    return sorted(({"toolchain": k, "score": v, "confidence": round(v / total, 2), "evidence": ev[k][:5]}
                   for k, v in score.items()), key=lambda d: -d["score"])


def packing_verdict(data: bytes, sections: list, fp: list) -> dict:
    reasons = [f"high entropy in {s['name']} ({s['entropy']})" for s in sections if s["suspicious"]]
    reasons += [f"packer signature: {f['toolchain']}" for f in fp
                if any(k in f["toolchain"] for k in ("packer", "Themida", "VMProtect"))]
    if not sections and entropy(data[:65536]) > PACKED_ENTROPY:
        reasons.append("high overall entropy")
    return {"likely_packed": bool(reasons), "reasons": reasons}


def provenance(path: str, functions=None) -> dict:
    """Full #11 report: hashes, fs trail, embedded metadata/resources, entropy, fingerprint."""
    with open(path, "rb") as fh:
        data = fh.read()
    hdr = parse_headers(data)
    secs = section_entropy(data, hdr)
    fp = fingerprint(data, hdr, functions)
    trail = fs_trail(path)
    meta = metadata(data, hdr)
    timeline = sorted([(v, k) for k, v in (("fs.mtime", trail["mtime"]), ("fs.ctime", trail["ctime"]),
                                            ("pe.compile_time", meta.get("pe_timestamp"))) if v])
    return {"hashes": hashes(data), "filesystem": trail, "metadata": meta, "embedded": embedded_resources(data),
            "section_entropy": secs, "fingerprint": fp, "packing": packing_verdict(data, secs, fp),
            "imphash": hdr.get("imphash"), "timeline": [{"when": w, "event": e} for w, e in timeline]}
