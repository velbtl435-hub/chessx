"""Program reversal (#24 / master §14.2): reconstruct how a binary was built.

Static analysis only — the sample is never executed. Produces a `reversal_summary`
dict with language/compiler/linker/runtime, build settings, packer verdict,
capability groups from imports, optional CFG highlights, a Portuguese narrative
and per-field confidence + evidence. Graceful when r2 / capstone / angr are absent.
"""
from __future__ import annotations
import re, struct
from .formats import parse_headers, parse_pe_rich
from .detector import entropy

# ---------------------------------------------------------------------------
# 1. Build settings / hardening
# ---------------------------------------------------------------------------
def _elf_dynamic_flags(data: bytes, hdr: dict) -> dict:
    """Read DT_FLAGS / DT_FLAGS_1 and GNU property-ish bits from ELF dynamic + notes."""
    out = {}
    if hdr.get("format") != "ELF" or not data.startswith(b"\x7fELF"):
        return out
    is64, e = data[4] == 2, "<" if data[5] == 1 else ">"
    try:
        if is64:
            _etype, _m, _v, _en, phoff, shoff, _f, _eh, phes, phn, shes, shn, shstr = struct.unpack_from(
                e + "HHIQQQIHHHHHH", data, 16)
        else:
            _etype, _m, _v, _en, phoff, shoff, _f, _eh, phes, phn, shes, shn, shstr = struct.unpack_from(
                e + "HHIIIIIHHHHHH", data, 16)
        # PT_GNU_STACK / PT_GNU_RELRO / PT_DYNAMIC
        for i in range(phn):
            o = phoff + i * phes
            if is64:
                ptype, flags, _off, _v, _p, filesz, memsz = struct.unpack_from(e + "IIQQQQQ", data, o)[:7]
                # actually: p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz
                ptype, flags = struct.unpack_from(e + "II", data, o)
            else:
                ptype, _off, _v, _p, filesz, memsz, flags = struct.unpack_from(e + "IIIIIII", data, o)[:7]
                ptype, flags = struct.unpack_from(e + "I", data, o)[0], struct.unpack_from(e + "I", data, o + 24)[0]
            if ptype == 0x6474e551:  # PT_GNU_STACK
                out["nx"] = not bool(flags & 1)  # PF_X
            if ptype == 0x6474e552:  # PT_GNU_RELRO
                out["relro"] = "partial"  # full if BIND_NOW too
        # sections for canary / fortify / debug / pie hints
        names = {s.get("name") for s in hdr.get("sections", [])}
        out["has_debug"] = bool(names & {".debug_info", ".debug_abbrev", ".zdebug_info", ".DWARF"})
        out["has_eh_frame"] = ".eh_frame" in names or ".eh_frame_hdr" in names
        # scan dynsym imports for canary / fortify
        imps = set(hdr.get("imports") or [])
        out["stack_canary"] = any(x in imps for x in ("__stack_chk_fail", "__stack_chk_guard", "__intel_security_cookie"))
        out["fortify"] = any(x.startswith("__") and x.endswith("_chk") for x in imps) or any(
            x in imps for x in ("__sprintf_chk", "__printf_chk", "__memcpy_chk", "__strcpy_chk"))
        # BIND_NOW from dynamic
        for s in hdr.get("sections", []):
            if s.get("name") != ".dynamic":
                continue
            # re-parse via raw: already have libraries; look for tag 0x18 (BIND_NOW) / FLAGS_1
            break
        # Use program headers dynamic
        for i in range(phn):
            o = phoff + i * phes
            ptype = struct.unpack_from(e + "I", data, o)[0]
            if ptype != 2:  # PT_DYNAMIC
                continue
            if is64:
                off, filesz = struct.unpack_from(e + "QQ", data, o + 8)[0], struct.unpack_from(e + "Q", data, o + 32)[0]
                fmt, step = e + "qQ", 16
            else:
                off, filesz = struct.unpack_from(e + "I", data, o + 4)[0], struct.unpack_from(e + "I", data, o + 16)[0]
                fmt, step = e + "iI", 8
            bind_now, flags1 = False, 0
            for j in range(0, filesz, step):
                tag, val = struct.unpack_from(fmt, data, off + j)
                if tag == 0:
                    break
                if tag == 0x18:  # DT_BIND_NOW
                    bind_now = True
                if tag == 0x6ffffffb:  # DT_FLAGS_1
                    flags1 = val
            if bind_now or (flags1 & 0x8):  # DF_1_NOW
                if out.get("relro") == "partial":
                    out["relro"] = "full"
                elif "relro" not in out:
                    out["relro"] = "bind_now"
            if flags1 & 0x8000000:  # DF_1_PIE
                out["pie_flag"] = True
    except (struct.error, IndexError, KeyError):
        out.setdefault("warning", "partial ELF hardening parse")
    return out


def build_settings(data: bytes, hdr: dict) -> dict:
    """PIE, RELRO, NX, canary, fortify, stripped, static/dynamic, debug info."""
    fmt = hdr.get("format")
    ev, conf = [], 0.5
    out = {"format": fmt, "stripped": bool(hdr.get("stripped")), "static": False, "dynamic": False,
           "pie": None, "relro": None, "nx": None, "stack_canary": None, "fortify": None,
           "debug_info": None, "evidence": []}
    if fmt == "ELF":
        h = _elf_dynamic_flags(data, hdr)
        out["nx"] = h.get("nx")
        out["relro"] = h.get("relro") or ("none" if h.get("nx") is not None else None)
        out["stack_canary"] = h.get("stack_canary")
        out["fortify"] = h.get("fortify")
        out["debug_info"] = h.get("has_debug")
        # PIE: ET_DYN shared/PIE type
        out["pie"] = hdr.get("type") == "shared/PIE" or bool(h.get("pie_flag"))
        libs = hdr.get("libraries") or []
        interp = hdr.get("interpreter")
        out["static"] = not libs and not interp
        out["dynamic"] = bool(libs or interp)
        if out["stripped"]:
            ev.append("sem .symtab (stripped)")
        if out["static"]:
            ev.append("sem PT_INTERP/DT_NEEDED (estático)")
        if interp:
            ev.append(f"interpreter={interp}")
        if out["pie"]:
            ev.append("ET_DYN/PIE")
        if out["nx"] is True:
            ev.append("PT_GNU_STACK NX")
        if out["relro"]:
            ev.append(f"RELRO={out['relro']}")
        if out["stack_canary"]:
            ev.append("__stack_chk_fail")
        if out["fortify"]:
            ev.append("FORTIFY_SOURCE (*_chk)")
        if out["debug_info"]:
            ev.append("seções .debug_*")
        conf = 0.85 if ev else 0.4
    elif fmt == "PE":
        dc = hdr.get("dll_characteristics") or 0
        out["nx"] = bool(dc & 0x100)          # IMAGE_DLLCHARACTERISTICS_NX_COMPAT
        out["pie"] = bool(dc & 0x40)          # DYNAMIC_BASE (ASLR) as PIE-ish
        out["aslr"] = bool(dc & 0x40)
        out["cfg"] = bool(dc & 0x4000)        # GUARD_CF
        out["high_entropy_va"] = bool(dc & 0x20)
        out["dynamic"] = bool(hdr.get("import_table") or hdr.get("delay_imports"))
        out["static"] = not out["dynamic"]
        out["debug_info"] = any(s.get("name", "").lower() in (".debug", ".pdata") for s in hdr.get("sections", []))
        # PE rarely exposes canary via imports: /GS -> __security_check_cookie
        imps = " ".join(hdr.get("imports") or []).lower()
        out["stack_canary"] = "__security_check_cookie" in imps or "@__security_check_cookie" in imps
        out["relro"] = None  # N/A
        if hdr.get("linker_version"):
            ev.append(f"PE linker {hdr['linker_version']}")
        if out["nx"]:
            ev.append("NX_COMPAT")
        if out["pie"]:
            ev.append("DYNAMIC_BASE/ASLR")
        if out["cfg"]:
            ev.append("GUARD_CF")
        if out["stack_canary"]:
            ev.append("/GS (__security_check_cookie)")
        conf = 0.8 if ev else 0.4
    elif fmt and "Mach-O" in str(fmt):
        out["pie"] = True  # modern Mach-O is PIE by default on Darwin
        out["dynamic"] = True
        ev.append("Mach-O (assumindo PIE moderno)")
        conf = 0.5
    else:
        conf = 0.2
        ev.append("formato sem hardening tipado")
    out["evidence"] = ev
    out["confidence"] = round(conf, 2)
    return out


# ---------------------------------------------------------------------------
# 2. Toolchain / version recovery
# ---------------------------------------------------------------------------
_GCC_RE = re.compile(rb"GCC: \(([^)]*)\) ([0-9]+\.[0-9.]+)")
_CLANG_RE = re.compile(rb"clang version ([0-9]+\.[0-9.]+)")
_GO_BUILDINFO = re.compile(rb"\xff Go buildinf:")
_GO_VER = re.compile(rb"(go1\.[0-9]+(?:\.[0-9]+)?)")
_RUSTC_PATH = re.compile(rb"/rustc/([0-9a-f]{40})")
_RUSTC_VER = re.compile(rb"rustc[/\s-]([0-9]+\.[0-9]+\.[0-9]+)")
_PYI = re.compile(rb"PyInstaller|MEI\d{3}|_MEIPASS", re.I)
_NUITKA = re.compile(rb"Nuitka|__nuitka_", re.I)
_DOTNET = re.compile(rb"mscoree\.dll|BSJB|_CorExeMain|_CorDllMain", re.I)
_MSVC_VER = re.compile(rb"Microsoft \(R\) (?:C/C\+\+|Optimizing) Compiler|MSVC", re.I)


def _comment_section(data: bytes, hdr: dict) -> bytes:
    for s in hdr.get("sections") or []:
        if s.get("name") == ".comment" and s.get("size"):
            return data[s["offset"]:s["offset"] + s["size"]]
    return b""


def _go_buildinfo(data: bytes) -> dict:
    """Best-effort Go buildinfo blob (version + modules). No execution."""
    i = data.find(b"\xff Go buildinf:")
    if i < 0:
        # section name fallback
        return {}
    blob = data[i:i + 512]
    vers = _GO_VER.findall(blob) or _GO_VER.findall(data[i:i + 8192])
    # Go 1.18+ buildinfo also has readable strings after magic
    mods = [m.decode() for m in re.findall(rb"(?:path|mod)\x00([^\x00]{2,80})", data[i:i + 4096])[:8]]
    out = {"go_buildinfo_offset": i, "evidence": ["\\xff Go buildinf:"]}
    if vers:
        out["version"] = vers[0].decode()
        out["evidence"].append(out["version"])
    if mods:
        out["modules"] = mods
    return out


def toolchain_recovery(data: bytes, hdr: dict, fingerprint: list | None = None) -> dict:
    """Language / compiler / linker / runtime + versions where recoverable."""
    lang, compiler, linker, runtime = None, None, None, None
    versions, evidence = {}, []
    conf = 0.3

    # .comment (GCC/clang)
    comment = _comment_section(data, hdr)
    for m in _GCC_RE.finditer(comment or data[:65536]):
        compiler = "GCC"
        versions["gcc"] = m.group(2).decode()
        evidence.append(m.group(0).decode("utf-8", "replace"))
        lang = lang or "C/C++"
        conf = max(conf, 0.9)
    for m in _CLANG_RE.finditer(comment or data[:65536]):
        compiler = compiler or "Clang/LLVM"
        versions["clang"] = m.group(1).decode()
        evidence.append(m.group(0).decode("utf-8", "replace"))
        lang = lang or "C/C++"
        conf = max(conf, 0.9)

    # Go
    gi = _go_buildinfo(data)
    if gi or any(s.get("name") in (".gopclntab", ".go.buildinfo", ".note.go.buildid") for s in hdr.get("sections") or []):
        lang, runtime = "Go", "go runtime"
        if gi.get("version"):
            versions["go"] = gi["version"]
        evidence += gi.get("evidence", [".gopclntab"])
        conf = max(conf, 0.95 if gi.get("version") else 0.85)
        compiler = compiler or "gc (Go)"

    # Rust
    rm = _RUSTC_PATH.search(data) or _RUSTC_VER.search(data)
    if rm or any(s.get("name") == ".rustc" for s in hdr.get("sections") or []) or b"rust_panic" in data:
        lang = "Rust"
        runtime = "libstd"
        if rm:
            versions["rustc"] = rm.group(1).decode() if rm.lastindex else "?"
            evidence.append(rm.group(0)[:60].decode("utf-8", "replace"))
        conf = max(conf, 0.9)
        compiler = compiler or "rustc"

    # Packers / wrappers / .NET / Python
    if _PYI.search(data):
        lang, runtime = lang or "Python", "PyInstaller"
        evidence.append("PyInstaller marker"); conf = max(conf, 0.85)
    if _NUITKA.search(data):
        lang, compiler = lang or "Python", compiler or "Nuitka"
        evidence.append("Nuitka marker"); conf = max(conf, 0.85)
    if hdr.get("dotnet") or _DOTNET.search(data[: min(len(data), 2_000_000)]):
        lang, runtime = ".NET", "CLR"
        evidence.append("mscoree.dll / BSJB"); conf = max(conf, 0.9)

    # PE Rich + linker version
    rich = hdr.get("rich") if hdr.get("format") == "PE" else parse_pe_rich(data)
    if rich and rich.get("present"):
        compiler = compiler or "MSVC"
        lang = lang or "C/C++"
        if rich.get("linker"):
            linker = rich["linker"]["product"]
            versions["msvc_linker_build"] = rich["linker"]["build"]
            evidence.append(f"Rich {rich['linker']['product']} build {rich['linker']['build']}")
        versions["rich_compids"] = len(rich.get("compids") or [])
        conf = max(conf, 0.9)
    if hdr.get("linker_version"):
        linker = linker or f"PE linker {hdr['linker_version']}"
        versions["pe_linker"] = hdr["linker_version"]
        evidence.append(f"OptionalHeader linker {hdr['linker_version']}")
        conf = max(conf, 0.7)

    # Fingerprint fallback (provenance #11)
    _FP_LANG = {"Go": "Go", "Rust": "Rust", "GCC": "C/C++", "Clang/LLVM": "C/C++", "MSVC": "C/C++",
                "MSVC/MinGW CRT": "C/C++", "glibc C runtime": "C/C++", "musl libc": "C/C++",
                "Python": "Python", ".NET": ".NET", "PyInstaller": "Python", "Nuitka": "Python"}
    for f in fingerprint or []:
        tc = f.get("toolchain") or ""
        if tc.startswith("("):  # "(stripped)" etc.
            continue
        mapped = next((v for k, v in _FP_LANG.items() if k in tc), None)
        if mapped and not lang:
            lang = mapped
            evidence.append(f"fingerprint:{tc}")
            conf = max(conf, float(f.get("confidence") or 0.5) * 0.9)
        if tc in ("GCC", "Clang/LLVM", "MSVC", "rustc", "gc (Go)") and not compiler:
            compiler = tc
        if "glibc" in tc.lower():
            runtime = runtime or "glibc"
        if "musl" in tc.lower():
            runtime = runtime or "musl"

    # ELF interpreter / libc hint
    if hdr.get("interpreter"):
        evidence.append(hdr["interpreter"])
        if "ld-musl" in hdr["interpreter"]:
            runtime = runtime or "musl"
        elif "ld-linux" in hdr["interpreter"]:
            runtime = runtime or "glibc"

    return {"language": lang, "compiler": compiler, "linker": linker, "runtime": runtime,
            "versions": versions, "rich": rich or None, "go_buildinfo": gi or None,
            "evidence": evidence[:12], "confidence": round(min(conf, 0.99), 2)}


# ---------------------------------------------------------------------------
# 3. Capability / import story
# ---------------------------------------------------------------------------
_CAP_RULES = [
    ("network", re.compile(r"(?i)socket|connect|send|recv|bind|listen|WSA|getaddrinfo|Internet|Http|curl|ssl|tls")),
    ("crypto", re.compile(r"(?i)crypt|AES|SHA|RSA|BCrypt|NCrypt|EVP_|HMAC|randombytes|libsodium")),
    ("process", re.compile(r"(?i)CreateProcess|execve|fork|system|posix_spawn|OpenProcess|TerminateProcess|ptrace")),
    ("file", re.compile(r"(?i)CreateFile|ReadFile|WriteFile|fopen|open\b|read\b|write\b|unlink|mkdir|RemoveFile")),
    ("registry", re.compile(r"(?i)Reg(Open|Set|Query|Create|Delete)")),
    ("thread", re.compile(r"(?i)pthread_|CreateThread|NtCreateThread|std::thread")),
    ("ui", re.compile(r"(?i)MessageBox|CreateWindow|gtk_|qt_|XOpenDisplay|WinMain")),
    ("service", re.compile(r"(?i)OpenSCManager|CreateService|StartServiceCtrlDispatcher")),
]


def capability_story(hdr: dict) -> dict:
    """Group imports/libraries into capability buckets + short story."""
    imports = list(hdr.get("imports") or [])
    libs = list(hdr.get("libraries") or [])
    delay = hdr.get("delay_imports") or {}
    # PE import_table keys are dlls
    if hdr.get("import_table"):
        libs = sorted(set(libs) | set(hdr["import_table"]))
        flat = []
        for d, fs in hdr["import_table"].items():
            flat += [f"{d}!{f}" for f in fs]
        imports = sorted(set(imports) | set(flat))
    delay_flat = [f"{d}!{f}" for d, fs in delay.items() for f in fs]
    groups = {name: [] for name, _ in _CAP_RULES}
    for item in imports + delay_flat:
        for name, rx in _CAP_RULES:
            if rx.search(item):
                if len(groups[name]) < 12:
                    groups[name].append(item)
                break
    groups = {k: v for k, v in groups.items() if v}
    story_parts = []
    if libs:
        story_parts.append(f"liga com {len(libs)} bibliotecas ({', '.join(libs[:6])}{'…' if len(libs) > 6 else ''})")
    if groups:
        story_parts.append("capacidades: " + ", ".join(f"{k}({len(v)})" for k, v in groups.items()))
    if delay:
        story_parts.append(f"delay-load: {', '.join(delay)[:80]}")
    if not story_parts:
        story_parts.append("sem imports dinâmicos visíveis (estático ou stripped sem dynsym)")
    conf = 0.8 if imports or libs else 0.35
    return {"libraries": libs[:40], "import_count": len(imports), "delay_imports": delay,
            "capabilities": groups, "story": "; ".join(story_parts),
            "evidence": (libs[:5] + imports[:5])[:10], "confidence": round(conf, 2)}


# ---------------------------------------------------------------------------
# 4. CFG highlights (optional r2 / angr)
# ---------------------------------------------------------------------------
def cfg_highlights(path: str, disasm: dict | None = None, cfg: dict | None = None) -> dict:
    """Function count, largest functions, entry hints. Soft-fail without r2/angr."""
    ev, conf = [], 0.3
    funcs = []
    entry = None
    backend = None
    if disasm:
        backend = disasm.get("backend")
        entry = disasm.get("entrypoint")
        funcs = list(disasm.get("functions") or [])
        if funcs:
            conf = 0.75 if backend == "r2" else 0.55
            ev.append(f"disasm.backend={backend}")
    if cfg and cfg.get("functions"):
        # angr cfg_summary shape
        names = cfg.get("functions") or []
        funcs = funcs or [{"name": n, "size": 0} for n in names]
        conf = max(conf, 0.8)
        ev.append("angr cfg_summary")
        backend = backend or "angr"
        entry = entry or cfg.get("entry")
    # normalize
    norm = []
    for f in funcs:
        if isinstance(f, str):
            norm.append({"name": f, "size": 0})
        elif isinstance(f, dict):
            norm.append({"name": f.get("name") or f.get("label") or "?", "size": int(f.get("size") or f.get("realsize") or 0),
                         "addr": f.get("offset") or f.get("addr") or f.get("address")})
    largest = sorted(norm, key=lambda x: -x["size"])[:8]
    mainish = [f for f in norm if (f["name"] or "").lower() in ("main", "wmain", "winmain", "_main", "entry0", "main.main")]
    out = {"backend": backend, "function_count": len(norm), "largest": largest,
           "entry": entry, "entry_to_main": [f["name"] for f in mainish] or None,
           "entry_disasm": (disasm or {}).get("entry_disasm", [])[:8],
           "evidence": ev, "confidence": round(conf, 2)}
    return out


# ---------------------------------------------------------------------------
# Narrative + top-level summary
# ---------------------------------------------------------------------------
def _narrative(settings, tool, caps, packing, cfg) -> str:
    bits = []
    lang = tool.get("language") or "linguagem indeterminada"
    comp = tool.get("compiler") or "?"
    ver = tool.get("versions") or {}
    ver_s = ", ".join(f"{k}={v}" for k, v in ver.items() if not isinstance(v, (list, dict)))
    bits.append(f"Parece {lang} compilado com {comp}" + (f" ({ver_s})" if ver_s else "") + ".")
    if tool.get("linker"):
        bits.append(f"Linker: {tool['linker']}.")
    if tool.get("runtime"):
        bits.append(f"Runtime: {tool['runtime']}.")
    hs = []
    if settings.get("pie"):
        hs.append("PIE")
    if settings.get("nx"):
        hs.append("NX")
    if settings.get("relro"):
        hs.append(f"RELRO={settings['relro']}")
    if settings.get("stack_canary"):
        hs.append("canary")
    if settings.get("fortify"):
        hs.append("FORTIFY")
    if settings.get("stripped"):
        hs.append("stripped")
    if settings.get("static"):
        hs.append("estático")
    elif settings.get("dynamic"):
        hs.append("dinâmico")
    if hs:
        bits.append("Build: " + ", ".join(hs) + ".")
    if packing and packing.get("likely_packed"):
        bits.append("Possível empacotamento: " + "; ".join((packing.get("reasons") or [])[:2]) + ".")
    if caps and caps.get("story"):
        bits.append(caps["story"] + ".")
    if cfg and cfg.get("function_count"):
        bits.append(f"CFG: {cfg['function_count']} funções"
                    + (f", entrada→{cfg['entry_to_main']}" if cfg.get("entry_to_main") else "") + ".")
    return " ".join(bits)


def reversal_summary(path: str, data: bytes | None = None, hdr: dict | None = None,
                     provenance: dict | None = None, disasm: dict | None = None,
                     cfg: dict | None = None) -> dict:
    """Full #24 report. Safe with only stdlib parsers; enriches when extras exist."""
    if data is None:
        with open(path, "rb") as fh:
            data = fh.read()
    hdr = hdr or parse_headers(data)
    fp = (provenance or {}).get("fingerprint")
    packing = (provenance or {}).get("packing") or {"likely_packed": False, "reasons": []}
    settings = build_settings(data, hdr)
    tool = toolchain_recovery(data, hdr, fp)
    caps = capability_story(hdr)
    cfg_h = cfg_highlights(path, disasm, cfg)
    narrative = _narrative(settings, tool, caps, packing, cfg_h)
    overall = round(sum(x["confidence"] for x in (settings, tool, caps, cfg_h)) / 4, 2)
    return {
        "disclaimer": "Análise estática apenas; alvos autorizados somente. A amostra nunca é executada.",
        "build_settings": settings,
        "toolchain": tool,
        "capabilities": caps,
        "packing": packing,
        "cfg": cfg_h,
        "narrative_pt": narrative,
        "confidence": overall,
        "evidence": list(dict.fromkeys(
            (settings.get("evidence") or []) + (tool.get("evidence") or []) + (caps.get("evidence") or [])[:5]
        ))[:20],
    }
