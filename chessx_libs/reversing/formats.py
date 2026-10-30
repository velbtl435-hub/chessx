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
    delay = parse_pe_delay_imports(data, secs, base, opt, magic)
    rich = parse_pe_rich(data)
    # PE optional header linker version (MajorLinkerVersion / MinorLinkerVersion)
    link_maj, link_min = struct.unpack_from("<BB", data, opt + 2)
    # DLL characteristics (ASLR/NX/…) live after the data directories start — offset depends on magic
    dll_chars = struct.unpack_from("<H", data, opt + (70 if magic == 0x20B else 70))[0] if magic in (0x10B, 0x20B) else 0
    # Correct offsets: PE32+ DataDirectory at opt+112, DLLCharacteristics at opt+70; PE32 same at opt+70
    try:
        dll_chars = struct.unpack_from("<H", data, opt + 70)[0]
    except struct.error:
        dll_chars = 0
    return {"format": "PE", "bits": 64 if magic == 0x20B else 32, "machine": PE_MACHINES.get(mach, hex(mach)),
            "timestamp": ts, "dll": bool(chars & 0x2000), "entrypoint": base + entry, "image_base": base,
            "linker_version": f"{link_maj}.{link_min}", "dll_characteristics": dll_chars,
            "sections": secs, "imports": sorted({f"{d}!{f}" for d, fs in imports.items() for f in fs}),
            "import_table": imports, "delay_imports": delay,
            "imphash": imphash(imports), "dotnet": b"mscoree.dll" in data.lower() or b"mscoree.dll" in data,
            "rich": rich}


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


# --- PE Rich header (MSVC) and delay-load imports (#24 program reversal) ------
# Product IDs: common subset from open-source tables (VS 2005–2022). Unknown IDs kept numeric.
_RICH_PRODUCT = {
    0x00: "Imported", 0x01: "Import0", 0x02: "Linker510", 0x04: "Cvtomf510",
    0x0A: "Import", 0x0B: "Import", 0x0E: "Utc10_0_C", 0x0F: "Utc10_0_CPP",
    0x5A: "Utc1500_C", 0x5C: "Utc1500_CPP", 0x5E: "Utc1500_LTCG_C",
    0x5F: "Utc1500_LTCG_CPP", 0x60: "Utc1500_POGO_i386", 0x6D: "Linker800",
    0x6E: "Cvtomf800", 0x73: "Utc1600_C", 0x74: "Utc1600_CPP",
    0x7A: "Linker900", 0x7B: "Export900", 0x7C: "Utc1700_C", 0x7D: "Utc1700_CPP",
    0x83: "Linker1000", 0x84: "Cvtomf1000", 0x91: "Utc1800_C", 0x92: "Utc1800_CPP",
    0x9B: "Linker1100", 0x9D: "Utc1900_C", 0x9E: "Utc1900_CPP",
    0xAA: "Linker1200", 0xAB: "Utc1910_C", 0xAC: "Utc1910_CPP",
    0xC9: "Linker1400", 0xCA: "Utc1920_C", 0xCB: "Utc1920_CPP",
    0xCD: "Utc1921_C", 0xCE: "Utc1921_CPP", 0xD0: "Utc1922_C", 0xD1: "Utc1922_CPP",
    0xD3: "Utc1923_C", 0xD4: "Utc1923_CPP", 0xD6: "Utc1924_C", 0xD7: "Utc1924_CPP",
    0xD9: "Utc1925_C", 0xDA: "Utc1925_CPP", 0xDC: "Utc1926_C", 0xDD: "Utc1926_CPP",
    0xDF: "Utc1927_C", 0xE0: "Utc1927_CPP", 0xE2: "Utc1928_C", 0xE3: "Utc1928_CPP",
    0xE5: "Utc1929_C", 0xE6: "Utc1929_CPP", 0xE8: "Utc1930_C", 0xE9: "Utc1930_CPP",
    0xEB: "Utc1931_C", 0xEC: "Utc1931_CPP", 0xEE: "Utc1932_C", 0xEF: "Utc1932_CPP",
}


def parse_pe_rich(data: bytes) -> dict:
    """Decode the MSVC Rich header between DOS stub and PE signature. Empty dict if absent."""
    if not data.startswith(b"MZ") or len(data) < 0x80:
        return {}
    try:
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if pe > len(data) or data[pe:pe + 4] != b"PE\x00\x00":
            return {}
        rich = data.find(b"Rich", 0x40, pe)
        if rich < 0 or rich + 8 > pe:
            return {}
        key = struct.unpack_from("<I", data, rich + 4)[0]
        # DanS marker XOR key starts the records
        dans = 0x536E6144  # 'DanS'
        start = None
        for o in range(0x40, rich - 15, 4):
            if struct.unpack_from("<I", data, o)[0] ^ key == dans:
                # next 12 bytes are also XOR'd zeros padding
                if all(struct.unpack_from("<I", data, o + 4 * i)[0] ^ key == 0 for i in (1, 2, 3)):
                    start = o + 16
                    break
        if start is None:
            return {"present": True, "key": f"0x{key:08x}", "compids": [], "warning": "DanS not found"}
        comps = []
        for o in range(start, rich, 8):
            v = struct.unpack_from("<I", data, o)[0] ^ key
            c = struct.unpack_from("<I", data, o + 4)[0] ^ key
            prod, build = v >> 16, v & 0xFFFF
            comps.append({"product_id": prod, "product": _RICH_PRODUCT.get(prod, f"id_{prod}"),
                          "build": build, "count": c})
        # linker product heuristic: highest Linker* id present
        linker = next((c for c in reversed(comps) if c["product"].startswith("Linker")), None)
        return {"present": True, "key": f"0x{key:08x}", "compids": comps, "linker": linker}
    except (struct.error, IndexError):
        return {}


def parse_pe_delay_imports(data: bytes, secs: list, base: int, opt: int, magic: int, limit: int = 2048) -> dict:
    """Delay-load Import Directory (data directory #13) -> {dll: [func, ...]}."""
    out = {}
    try:
        dd = opt + (112 if magic == 0x20B else 96) + 13 * 8
        rva, _size = struct.unpack_from("<II", data, dd)
        off = _rva2off(rva, secs, base) if rva else None
        is64, n = magic == 0x20B, 0
        while off is not None and n < 256:
            # ImgDelayDescr (new): attrs, name, hmod, IAT, INT, BoundIAT, UnloadIAT, timestamp
            _attrs, name_rva, _h, _iat, int_rva = struct.unpack_from("<IIIII", data, off)[:5]
            if not (name_rva or int_rva):
                break
            no = _rva2off(name_rva, secs, base)
            dll = _cstr(data, no).lower() if no is not None else "?"
            funcs, to = [], _rva2off(int_rva, secs, base)
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
            off += 32; n += 1
    except (struct.error, IndexError, ValueError):
        pass
    return out
