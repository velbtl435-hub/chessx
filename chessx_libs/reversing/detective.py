"""Detective mode: provenance info + full static reversal pipeline (one JSON report).

Defensive use only: every step is static analysis; the sample is never executed.
"""
import hashlib, os, time

MAGIC = {b"\x7fELF": "ELF", b"MZ": "PE/DOS", b"%PDF": "PDF", b"\x89PNG": "PNG",
         b"PK\x03\x04": "ZIP", b"\xff\xd8\xff": "JPEG", b"#!": "script", b"\xca\xfe\xba\xbe": "Mach-O/Java"}


def file_info(path: str) -> dict:
    with open(path, "rb") as fh:
        data = fh.read()
    st = os.stat(path)
    kind = next((v for k, v in MAGIC.items() if data.startswith(k)), "unknown")
    return {"path": path, "size": st.st_size, "type": kind,
            "sha256": hashlib.sha256(data).hexdigest(), "md5": hashlib.md5(data).hexdigest(),
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))}


def _libmagic(path: str):
    try:
        import magic
        return magic.from_file(path)
    except Exception:
        return None


def optional_backends() -> dict:
    import importlib.util, shutil
    mods = {m: importlib.util.find_spec(m) is not None for m in ("capstone", "r2pipe", "elftools", "lief", "magic", "angr")}
    mods["r2_binary"] = bool(shutil.which("r2") or shutil.which("radare2"))
    return mods


def investigate(path: str, min_str: int = 5, max_strings: int = 200, use_angr: bool = False,
                expanded: bool = True) -> dict:
    """Run every analysis step and return one JSON-serializable report."""
    from .detector import detect
    from .formats import parse_headers
    from .origin import origin_hints
    from .strings import strings_with_offsets, indicators
    from .disasm import analyze_binary
    with open(path, "rb") as fh:
        data = fh.read()
    report = {"disclaimer": "Static analysis only; authorized targets only.",
              "file": file_info(path), "libmagic": _libmagic(path), "detect": detect(data),
              "headers": parse_headers(data), "origin": origin_hints(data),
              "indicators": indicators(data), "backends": optional_backends(), "errors": []}
    strs = strings_with_offsets(data, min_str)
    report["strings"] = {"count": len(strs), "sample": strs[:max_strings]}
    if report["headers"].get("format"):
        try:
            report["disasm"] = analyze_binary(path)
        except Exception as exc:
            report["errors"].append(f"disasm: {exc}")
    if use_angr:
        from .angr_helper import cfg_summary
        try:
            report["cfg"] = cfg_summary(path)
        except Exception as exc:
            report["errors"].append(f"angr: {exc}")
    if expanded:  # #11 expanded detective mode
        from .provenance import provenance
        funcs = list(report.get("disasm", {}).get("functions", [])) + list(report.get("cfg", {}).get("functions", []))  # r2 + angr names
        try:
            report["provenance"] = provenance(path, funcs)
        except Exception as exc:
            report["errors"].append(f"provenance: {exc}")
    # #24 program reversal — NEW key appended LAST (menu entry 9 / key order untouched above)
    try:
        from .reversal import reversal_summary
        report["reversal_summary"] = reversal_summary(
            path, data=data, hdr=report.get("headers") or {},
            provenance=report.get("provenance"), disasm=report.get("disasm"), cfg=report.get("cfg"))
    except Exception as exc:
        report["errors"].append(f"reversal: {exc}")
        report["reversal_summary"] = {"error": str(exc), "narrative_pt": "reversão indisponível", "confidence": 0}
    return report
