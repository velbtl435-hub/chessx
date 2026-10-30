"""Static disassembly through the vendored capstone C module (c/capstone, cx_disasm shim).

Lazy: libcx_capstone is dlopen'd only on the first disasm()/_lib() call (never at import).
Backend order: native ctypes (libcx_capstone, built with c/capstone/module.mk) -> pip `capstone`
-> pure Python (x86 only, reversing's built-in decoder). Bytes in, text out: nothing is executed.
Archs in the native/wasm build: x86, ARM, ARM64, MIPS, RISC-V (see c/capstone/README.md)."""
import ctypes
from . import load as _load

# capstone 5 numeric constants (identical to the Python binding)
ARCH = {"arm": 0, "arm64": 1, "aarch64": 1, "mips": 2, "x86": 3, "riscv": 15}
MODE = {"16": 2, "32": 4, "64": 8, "arm": 0, "thumb": 16, "mips32": 4, "mips64": 8,
        "riscv32": 1, "riscv64": 2, "riscvc": 4, "big": 1 << 31, "little": 0}
_ERR = {-1: "native capstone unavailable", -2: "bad arch/mode", -3: "output buffer too small"}


def _lib():
    lib = _load("capstone")
    if lib is not None and not getattr(lib, "_cx_typed", False):
        lib.cx_cs_available.restype = ctypes.c_int32
        lib.cx_cs_archs.restype = ctypes.c_int32
        lib.cx_disasm.restype = ctypes.c_int32
        lib.cx_disasm.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_char_p, ctypes.c_size_t,
                                  ctypes.c_uint64, ctypes.c_int32, ctypes.c_char_p, ctypes.c_size_t]
        lib._cx_typed = True
    if lib is not None and not lib.cx_cs_available():  # stub build (no module.mk)
        return None
    return lib


def _pip():
    try:
        import capstone
        return capstone
    except ImportError:
        return None


def backend() -> str:
    return "native" if _lib() is not None else "pip" if _pip() is not None else "python"


def _num(v, table):
    if isinstance(v, int):
        return v
    out = 0
    for part in str(v).lower().replace("|", "+").split("+"):
        out |= table[part.strip()]
    return out


def disasm_native(code: bytes, arch=3, mode=8, addr=0, max_insns=0):
    lib = _lib()
    if lib is None:
        raise RuntimeError(_ERR[-1])
    code = bytes(code)
    cap = max(4096, len(code) * 96 + 256)
    for _ in range(4):
        buf = ctypes.create_string_buffer(cap)
        n = lib.cx_disasm(_num(arch, ARCH), _c32(_num(mode, MODE)),
                          code, len(code), addr, max_insns, buf, cap)
        if n != -3:
            break
        cap *= 4
    if n < 0:
        raise ValueError(_ERR.get(n, "error %d" % n))
    out = []
    for line in buf.value.decode("utf-8", "replace").splitlines():
        a, s, m, o = line.split("\t", 3)
        out.append((int(a, 16), int(s), m, o))
    return out


def _c32(v):  # pass CS_MODE_BIG_ENDIAN (1<<31) through a signed int32
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v >= 1 << 31 else v


def disasm_pip(code: bytes, arch=3, mode=8, addr=0, max_insns=0):
    cs = _pip()
    if cs is None:
        raise RuntimeError("pip capstone not installed")
    md = cs.Cs(_num(arch, ARCH), _num(mode, MODE))
    return [(i.address, i.size, i.mnemonic, i.op_str) for i in md.disasm(bytes(code), addr, max_insns)]


def disasm(code: bytes, arch="x86", mode="64", addr=0, max_insns=0):
    """[(address, size, mnemonic, op_str)] using the best available backend."""
    if _lib() is not None:
        return disasm_native(code, arch, mode, addr, max_insns)
    if _pip() is not None:
        return disasm_pip(code, arch, mode, addr, max_insns)
    if _num(arch, ARCH) != 3:
        raise RuntimeError("no capstone backend for this arch (build c/capstone or pip install capstone)")
    from ..reversing.disasm import disasm_x86  # pure-Python x86 subset
    res = []
    for line in disasm_x86(bytes(code), addr, use_capstone=False):
        a, _, txt = line.partition(": ")
        m, _, o = txt.partition(" ")
        res.append((int(a, 16), 0, m, o))
    return res[:max_insns] if max_insns > 0 else res
