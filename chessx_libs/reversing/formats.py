"""Stdlib-only header parsers for ELF, PE and Mach-O (static, never executes the sample)."""
import struct

MACHO_MAGICS = {b"\xfe\xed\xfa\xce": ("Mach-O 32", ">"), b"\xce\xfa\xed\xfe": ("Mach-O 32", "<"),
                b"\xfe\xed\xfa\xcf": ("Mach-O 64", ">"), b"\xcf\xfa\xed\xfe": ("Mach-O 64", "<")}
ELF_MACHINES = {3: "x86", 0x3E: "x86-64", 0x28: "ARM", 0xB7: "AArch64", 0xF3: "RISC-V", 8: "MIPS"}
PE_MACHINES = {0x14C: "x86", 0x8664: "x86-64", 0x1C0: "ARM", 0xAA64: "AArch64"}
MACHO_CPU = {7: "x86", 0x1000007: "x86-64", 12: "ARM", 0x100000C: "AArch64"}


def _cstr(blob: bytes, off: int) -> str:
    end = blob.find(b"\x00", off)
    return blob[off:end if end >= 0 else len(blob)].decode("utf-8", "replace")


def parse_elf(data: bytes) -> dict:
    if not data.startswith(b"\x7fELF") or len(data) < 52:
        return {}
    is64, e = data[4] == 2, "<" if data[5] == 1 else ">"
    if is64:
        (etype, mach, _v, entry, phoff, shoff, _f, _eh, phes, phn, shes, shn, shstr) = struct.unpack_from(e + "HHIQQQIHHHHHH", data, 16)
    else:
        (etype, mach, _v, entry, phoff, shoff, _f, _eh, phes, phn, shes, shn, shstr) = struct.unpack_from(e + "HHIIIIIHHHHHH", data, 16)
    info = {"format": "ELF", "bits": 64 if is64 else 32, "endian": "little" if e == "<" else "big",
            "type": {1: "relocatable", 2: "executable", 3: "shared/PIE", 4: "core"}.get(etype, etype),
            "machine": ELF_MACHINES.get(mach, hex(mach)), "entrypoint": entry,
            "sections": [], "imports": [], "libraries": [], "interpreter": None}
    secs = []
    try:
        for i in range(shn):
            o = shoff + i * shes
            if is64:
                name, typ, _fl, addr, off, size, link, _i, _a, entsz = struct.unpack_from(e + "IIQQQQIIQQ", data, o)
            else:
                name, typ, _fl, addr, off, size, link, _i, _a, entsz = struct.unpack_from(e + "IIIIIIIIII", data, o)
            secs.append(dict(name_off=name, type=typ, addr=addr, offset=off, size=size, link=link, entsize=entsz))
        if secs and shstr < len(secs):
            strtab = data[secs[shstr]["offset"]:secs[shstr]["offset"] + secs[shstr]["size"]]
            for s in secs:
                s["name"] = _cstr(strtab, s["name_off"])
        for s in secs:
            if s["type"] == 11 and s["entsize"]:  # SHT_DYNSYM
                st = secs[s["link"]]
                strs = data[st["offset"]:st["offset"] + st["size"]]
                for j in range(1, s["size"] // s["entsize"]):
                    o = s["offset"] + j * s["entsize"]
                    if is64:
                        nm, _inf, _o, shndx, _v, _sz = struct.unpack_from(e + "IBBHQQ", data, o)
                    else:
                        nm, _v, _sz, _inf, _o, shndx = struct.unpack_from(e + "IIIBBH", data, o)
                    if shndx == 0 and nm:
                        info["imports"].append(_cstr(strs, nm))
            if s["type"] == 6 and s["entsize"]:  # SHT_DYNAMIC -> DT_NEEDED
                st = secs[s["link"]]
                strs = data[st["offset"]:st["offset"] + st["size"]]
                fmt = e + ("qQ" if is64 else "iI")
                for j in range(s["size"] // s["entsize"]):
                    tag, val = struct.unpack_from(fmt, data, s["offset"] + j * s["entsize"])
                    if tag == 0:
                        break
                    if tag == 1:
                        info["libraries"].append(_cstr(strs, val))
        for i in range(phn):  # PT_INTERP
            o = phoff + i * phes
            ptype = struct.unpack_from(e + "I", data, o)[0]
            if ptype == 3:
                off, sz = (struct.unpack_from(e + "QQQQ", data, o + 8)[0], struct.unpack_from(e + "Q", data, o + 32)[0]) if is64 \
                    else (struct.unpack_from(e + "I", data, o + 4)[0], struct.unpack_from(e + "I", data, o + 16)[0])
                info["interpreter"] = data[off:off + sz].rstrip(b"\x00").decode("utf-8", "replace")
    except (struct.error, IndexError):
        info["warning"] = "truncated or malformed section table"
    info["sections"] = [{"name": s.get("name", ""), "addr": s["addr"], "offset": s["offset"], "size": s["size"]} for s in secs]
    info["imports"] = sorted(set(info["imports"]))
    info["stripped"] = not any(s.get("name") == ".symtab" for s in secs)
    return info


def parse_pe(data: bytes) -> dict:
    if not data.startswith(b"MZ") or len(data) < 64:
        return {}
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\x00\x00":
        return {"format": "DOS MZ"}
    mach, nsec, ts, _p, _n, optsz, chars = struct.unpack_from("<HHIIIHH", data, pe + 4)
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    entry = struct.unpack_from("<I", data, opt + 16)[0]
    base = struct.unpack_from("<Q" if magic == 0x20B else "<I", data, opt + (24 if magic == 0x20B else 28))[0]
    secs = []
    for i in range(nsec):
        o = opt + optsz + i * 40
        name = data[o:o + 8].rstrip(b"\x00").decode("latin-1")
        vsz, va, rsz, roff = struct.unpack_from("<IIII", data, o + 8)
        secs.append({"name": name, "addr": base + va, "offset": roff, "size": rsz, "vsize": vsz})
    imports = parse_pe_imports(data, secs, base, opt, magic)
    return {"format": "PE", "bits": 64 if magic == 0x20B else 32, "machine": PE_MACHINES.get(mach, hex(mach)),
            "timestamp": ts, "dll": bool(chars & 0x2000), "entrypoint": base + entry, "image_base": base,
            "sections": secs, "imports": sorted({f"{d}!{f}" for d, fs in imports.items() for f in fs}),
            "import_table": imports, "imphash": imphash(imports), "dotnet": b"mscoree.dll" in data.lower()}


def parse_macho(data: bytes) -> dict:
    if data[:4] in (b"\xca\xfe\xba\xbe",) and len(data) > 8 and struct.unpack_from(">I", data, 4)[0] < 30:
        return {"format": "Mach-O universal", "arch_count": struct.unpack_from(">I", data, 4)[0]}
    if data[:4] not in MACHO_MAGICS:
        return {}
    name, e = MACHO_MAGICS[data[:4]]
    cpu, _sub, ftype, ncmds = struct.unpack_from(e + "iiII", data, 4)
    return {"format": name, "machine": MACHO_CPU.get(cpu, hex(cpu & 0xFFFFFFFF)), "filetype": ftype, "ncmds": ncmds}


def parse_headers(data: bytes) -> dict:
    return parse_elf(data) or parse_pe(data) or parse_macho(data) or {"format": None}


def _rva2off(rva: int, secs: list, base: int):
    for s in secs:
        va = s["addr"] - base
        if va <= rva < va + max(s["size"], s.get("vsize", 0)):
            return s["offset"] + (rva - va)
    return None


def parse_pe_imports(data: bytes, secs: list, base: int, opt: int, magic: int, limit: int = 4096) -> dict:
    """Import Directory Table -> {dll: [function or #ordinal, ...]}. Tolerates malformed input."""
    out = {}
    try:
        dd = opt + (112 if magic == 0x20B else 96) + 8  # data directory #1 (imports)
        rva, _size = struct.unpack_from("<II", data, dd)
        off = _rva2off(rva, secs, base) if rva else None
        is64, n = magic == 0x20B, 0
        while off is not None and n < 512:
            ilt, _t, _f, name_rva, iat = struct.unpack_from("<IIIII", data, off)
            if not (ilt or name_rva or iat):
                break
            no = _rva2off(name_rva, secs, base)
            dll = _cstr(data, no).lower() if no is not None else "?"
            funcs, to = [], _rva2off(ilt or iat, secs, base)
            while to is not None and len(funcs) < limit:
                ent = struct.unpack_from("<Q" if is64 else "<I", data, to)[0]
                if not ent:
                    break
                if ent >> (63 if is64 else 31):
                    funcs.append(f"#{ent & 0xFFFF}")
                else:
                    ho = _rva2off(ent & 0x7FFFFFFF, secs, base)
                    funcs.append(_cstr(data, ho + 2) if ho is not None else "?")
                to += 8 if is64 else 4
            out.setdefault(dll, []).extend(funcs)
            off += 20; n += 1
    except (struct.error, IndexError):
        pass
    return out


def imphash(imports: dict):
    """pefile-compatible-ish imphash (md5 of 'dll.func' list, lowercased, extension stripped)."""
    import hashlib
    items = []
    for dll, funcs in imports.items():
        d = dll.rsplit(".", 1)[0] if dll.endswith((".dll", ".ocx", ".sys")) else dll
        items += [f"{d}.{f.lower()}" for f in funcs]
    return hashlib.md5(",".join(items).encode()).hexdigest() if items else None
