"""Disassembly helpers.

- Python: real disassembly via stdlib `dis` (source, code objects, .pyc files).
  .pyc input is untrusted: header-validated, unmarshalled in an isolated subprocess,
  and NEVER executed (static only).
- x86-64: tiny table-driven decoder for common one/two-byte opcodes (educational;
  for full coverage install `capstone` -- optional, auto-used if present).
"""
import dis, importlib.util, io, os, subprocess, sys

X86 = {0x90: "nop", 0xC3: "ret", 0xCC: "int3", 0x55: "push rbp", 0x5D: "pop rbp", 0xC9: "leave",
       0x50: "push rax", 0x53: "push rbx", 0x58: "pop rax", 0x5B: "pop rbx", 0xF4: "hlt", 0x99: "cdq"}


def disasm_python(obj) -> str:
    if isinstance(obj, str):
        obj = compile(obj, "<src>", "exec")
    buf = io.StringIO()
    dis.dis(obj, file=buf)
    return buf.getvalue()


class PycError(ValueError):
    """Raised when a .pyc is rejected (bad header/size) or the isolated loader crashes/times out."""


PYC_MAX_BYTES = 16 * 1024 * 1024
PYC_TIMEOUT = 10.0
PYC_MEM_LIMIT = 512 * 1024 * 1024

# Runs in a separate `python -I` process. It ONLY unmarshals and disassembles:
# the code object is never executed (no exec/eval, no import of the sample).
_PYC_CHILD = r"""
import sys, marshal, dis, io
try:
    import resource
    lim = int(sys.argv[1])
    resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
except Exception:
    pass
data = sys.stdin.buffer.read()
co = marshal.loads(data)
if type(co).__name__ != "code":
    sys.stderr.write("not a code object: " + type(co).__name__); sys.exit(3)
buf = io.StringIO(); dis.dis(co, file=buf); sys.stdout.write(buf.getvalue())
"""


def check_pyc_header(data: bytes) -> dict:
    """Validate a PEP 552 .pyc header against the running interpreter. Raises PycError."""
    if len(data) < 17:
        raise PycError("truncated .pyc (header is 16 bytes plus payload)")
    if len(data) > PYC_MAX_BYTES:
        raise PycError(f".pyc too large ({len(data)} > {PYC_MAX_BYTES} bytes)")
    if data[:4] != importlib.util.MAGIC_NUMBER:
        raise PycError(f"magic {data[:4].hex()} does not match this Python "
                       f"({importlib.util.MAGIC_NUMBER.hex()}, {sys.version.split()[0]})")
    flags = int.from_bytes(data[4:8], "little")
    if flags & ~0b11:
        raise PycError(f"invalid .pyc flags 0x{flags:x}")
    info = {"flags": flags, "hash_based": bool(flags & 1)}
    if not flags & 1:
        info["source_mtime"] = int.from_bytes(data[8:12], "little")
        info["source_size"] = int.from_bytes(data[12:16], "little")
    if data[16] & 0x7F != ord("c"):  # TYPE_CODE (optionally with FLAG_REF)
        raise PycError("payload is not a marshalled code object")
    return info


def disasm_pyc(path: str, timeout: float = PYC_TIMEOUT) -> str:
    """Disassemble a .pyc STATICALLY. The header is validated here; the untrusted
    marshal payload is decoded in an isolated subprocess (`python -I`, memory-capped,
    timeout) so a malformed file cannot crash this interpreter. Never executes the code.
    Raises PycError on rejection, crash or timeout."""
    if os.path.getsize(path) > PYC_MAX_BYTES:
        raise PycError(f".pyc too large (> {PYC_MAX_BYTES} bytes)")
    with open(path, "rb") as fh:
        data = fh.read(PYC_MAX_BYTES + 1)
    check_pyc_header(data)
    try:
        r = subprocess.run([sys.executable, "-I", "-S", "-c", _PYC_CHILD, str(PYC_MEM_LIMIT)], input=data[16:],
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise PycError(f"isolated .pyc loader timed out after {timeout}s") from None
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip().splitlines()
        how = f"killed by signal {-r.returncode}" if r.returncode < 0 else f"exit {r.returncode}"
        raise PycError(f"isolated .pyc loader failed ({how}): {err[-1] if err else 'no output'}")
    return r.stdout.decode("utf-8", "replace")


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
