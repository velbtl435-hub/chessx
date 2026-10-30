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


def disasm_x86(code: bytes, base: int = 0) -> list:
    try:
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
