"""Disassembly helpers.

- Python: real disassembly via stdlib `dis` (source, code objects, .pyc files).
- x86-64: tiny table-driven decoder for common one/two-byte opcodes (educational;
  for full coverage install `capstone` -- optional, auto-used if present).
"""
import dis, io, marshal

X86 = {0x90: "nop", 0xC3: "ret", 0xCC: "int3", 0x55: "push rbp", 0x5D: "pop rbp", 0xC9: "leave",
       0x50: "push rax", 0x53: "push rbx", 0x58: "pop rax", 0x5B: "pop rbx", 0xF4: "hlt", 0x99: "cdq"}


def disasm_python(obj) -> str:
    if isinstance(obj, str):
        obj = compile(obj, "<src>", "exec")
    buf = io.StringIO()
    dis.dis(obj, file=buf)
    return buf.getvalue()


def disasm_pyc(path: str) -> str:
    with open(path, "rb") as fh:
        fh.read(16)  # header (PEP 552) -- must match running interpreter version
        return disasm_python(marshal.load(fh))


def disasm_x86(code: bytes, base: int = 0, use_capstone: bool = True) -> list:
    try:
        if not use_capstone:
            raise ImportError
        import capstone  # optional
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        return [f"{i.address:08x}: {i.mnemonic} {i.op_str}".rstrip() for i in md.disasm(code, base)]
    except ImportError:
        pass
    out, i = [], 0
    while i < len(code):
        b = code[i]
        if b == 0x48 and code[i + 1:i + 3] == b"\x89\xe5":
            out.append(f"{base + i:08x}: mov rbp, rsp"); i += 3
        elif b == 0x0F and code[i + 1:i + 2] == b"\x05":
            out.append(f"{base + i:08x}: syscall"); i += 2
        elif b == 0xE8 and i + 5 <= len(code):
            rel = int.from_bytes(code[i + 1:i + 5], "little", signed=True)
            out.append(f"{base + i:08x}: call 0x{base + i + 5 + rel:x}"); i += 5
        elif b == 0xEB and i + 2 <= len(code):
            rel = int.from_bytes(code[i + 1:i + 2], "little", signed=True)
            out.append(f"{base + i:08x}: jmp 0x{base + i + 2 + rel:x}"); i += 2
        elif b in X86:
            out.append(f"{base + i:08x}: {X86[b]}"); i += 1
        else:
            out.append(f"{base + i:08x}: db 0x{b:02x}"); i += 1
    return out


# ---------------------------------------------------------------------------
# Binary-level analysis: radare2 (r2pipe) -> capstone -> builtin decoder.
# All backends are static: the sample is never executed.
import shutil


def _have_r2() -> bool:
    try:
        import r2pipe  # noqa: F401
    except ImportError:
        return False
    return shutil.which("r2") is not None or shutil.which("radare2") is not None


def _analyze_r2(path: str, max_functions: int) -> dict:
    import r2pipe
    r2 = r2pipe.open(path, flags=["-2"])
    try:
        r2.cmd("aaa")
        info = r2.cmdj("ij") or {}
        funcs = r2.cmdj("aflj") or []
        return {"backend": "radare2",
                "entrypoint": (r2.cmdj("iej") or [{}])[0].get("vaddr"),
                "functions": [{"addr": f.get("offset", f.get("addr")), "name": f.get("name"), "size": f.get("size")}
                              for f in funcs[:max_functions]],
                "function_count": len(funcs),
                "imports": sorted({i.get("name") for i in (r2.cmdj("iij") or []) if i.get("name")}),
                "sections": [{"name": s.get("name"), "addr": s.get("vaddr"), "size": s.get("size")}
                             for s in (r2.cmdj("iSj") or [])],
                "arch": info.get("bin", {}).get("arch"),
                "entry_disasm": [f"{o.get('addr', o.get('offset', 0)):08x}: {o.get('disasm', '')}" for o in (r2.cmdj("pdj 16 @ entry0") or [])]}
    finally:
        r2.quit()


def _code_at(data: bytes, hdr: dict, addr: int, n: int = 64) -> bytes:
    for s in hdr.get("sections", []):
        if s["addr"] and s["addr"] <= addr < s["addr"] + s["size"]:
            off = s["offset"] + (addr - s["addr"])
            return data[off:off + n]
    return b""


BACKENDS = ("auto", "r2", "capstone", "builtin")


def analyze_binary(path: str, backend: str = "auto", max_functions: int = 200) -> dict:
    """Entrypoint, sections, imports, functions and entry disassembly for ELF/PE/Mach-O.

    backend: "auto" (r2 -> capstone -> builtin), or force "r2", "capstone", "builtin".
    A forced backend that is unavailable falls back and reports it in "note".
    """
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}")
    from .formats import parse_headers
    if backend in ("auto", "r2") and _have_r2():
        try:
            return _analyze_r2(path, max_functions)
        except Exception as exc:  # fall through to static fallback
            err = f"r2 failed: {exc}"
        else:
            err = None
    else:
        err = "r2 unavailable" if backend == "r2" else None
    with open(path, "rb") as fh:
        data = fh.read()
    hdr = parse_headers(data)
    entry = hdr.get("entrypoint")
    code = _code_at(data, hdr, entry) if entry is not None else b""
    lines = []
    if code and hdr.get("machine") in ("x86-64", "x86") and backend == "builtin":
        lines, used = disasm_x86(code, entry, use_capstone=False)[:16], "builtin"
    elif code and hdr.get("machine") in ("x86-64", "x86"):
        try:
            import capstone
            mode = capstone.CS_MODE_64 if hdr.get("bits") == 64 else capstone.CS_MODE_32
            md = capstone.Cs(capstone.CS_ARCH_X86, mode)
            lines = [f"{i.address:08x}: {i.mnemonic} {i.op_str}".rstrip() for i in md.disasm(code, entry)][:16]
            used = "capstone"
        except ImportError:
            lines, used = disasm_x86(code, entry)[:16], "builtin"
            if backend == "capstone":
                err = "capstone unavailable"
    else:
        used = "headers-only"
    out = {"backend": used, "entrypoint": entry, "arch": hdr.get("machine"),
           "sections": hdr.get("sections", []), "imports": hdr.get("imports", []),
           "functions": _elf_functions(data, hdr)[:max_functions], "entry_disasm": lines}
    out["function_count"] = len(out["functions"])
    if err:
        out["note"] = err
    return out


def _elf_functions(data: bytes, hdr: dict) -> list:
    """Defined FUNC symbols from .symtab/.dynsym (via pyelftools when available)."""
    if hdr.get("format") != "ELF":
        return []
    try:
        import io
        from elftools.elf.elffile import ELFFile
        from elftools.elf.sections import SymbolTableSection
    except ImportError:
        return []
    funcs = {}
    try:
        elf = ELFFile(io.BytesIO(data))
        for sec in elf.iter_sections():
            if isinstance(sec, SymbolTableSection):
                for sym in sec.iter_symbols():
                    if sym["st_info"]["type"] == "STT_FUNC" and sym["st_value"]:
                        funcs.setdefault(sym["st_value"], {"addr": sym["st_value"], "name": sym.name, "size": sym["st_size"]})
    except Exception:
        return []
    return sorted(funcs.values(), key=lambda f: f["addr"])
