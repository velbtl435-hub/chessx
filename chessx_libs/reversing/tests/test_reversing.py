import json, os, shutil, subprocess, sys
import pytest
from chessx_libs import reversing as rv

HELLO_C = '#include <stdio.h>\nint helper(int x){return x*2;}\nint main(void){puts("hello chessx https://example.com/x");return helper(1);}\n'


@pytest.fixture(scope="session")
def hello(tmp_path_factory):
    if not shutil.which("gcc"):
        pytest.skip("gcc not available")
    d = tmp_path_factory.mktemp("bin")
    (d / "hello.c").write_text(HELLO_C)
    out = d / "hello"
    subprocess.run(["gcc", "-O0", "-o", str(out), str(d / "hello.c")], check=True)
    return str(out)


def test_legacy_api_still_works():
    assert rv.convert("ff", 16, 2) == "11111111" and rv.to_base(-10, 16) == "-a"
    assert rv.detect(b"\x7fELF....")["type"] == "ELF executable"
    assert "nop" in rv.disasm_x86(b"\x90")[0]
    assert rv.extract_urls(b"go http://a.com/x, ok") == ["http://a.com/x"]


def test_strings_offsets_ascii_and_utf16():
    blob = b"\x00\x00hello\x00\x01\x01" + "wide!".encode("utf-16-le") + b"\x00"
    s = rv.strings_with_offsets(blob, 4)
    assert {"offset": 2, "encoding": "ascii", "value": "hello"} in s
    assert any(x["encoding"] == "utf-16le" and x["value"] == "wide!" for x in s)


def test_origin_markers():
    names = [h["toolchain"] for h in rv.origin_hints(b"xx UPX! yy \xff Go buildinf: zz /rustc/abc")]
    assert {"UPX packer", "Go", "Rust"} <= set(names)


def test_elf_headers(hello):
    h = rv.parse_headers(open(hello, "rb").read())
    assert h["format"] == "ELF" and h["entrypoint"] > 0
    assert "puts" in h["imports"] and any(s["name"] == ".text" for s in h["sections"])
    assert any("libc" in lib for lib in h["libraries"])


def test_gcc_origin(hello):
    assert any(o["toolchain"] == "GCC" for o in rv.origin_hints(open(hello, "rb").read()))


def test_analyze_binary(hello):
    r = rv.analyze_binary(hello)
    assert r["entrypoint"] and r["entry_disasm"]
    if r["backend"] != "builtin" and r["functions"]:
        assert any("main" in (f["name"] or "") for f in r["functions"])


def test_pe_and_macho_minimal():
    pe = bytearray(512); pe[:2] = b"MZ"; pe[0x3C:0x40] = (64).to_bytes(4, "little")
    pe[64:68] = b"PE\x00\x00"; pe[68:70] = (0x8664).to_bytes(2, "little")
    pe[84:86] = (240).to_bytes(2, "little"); pe[88:90] = (0x20B).to_bytes(2, "little")
    h = rv.parse_pe(bytes(pe))
    assert h["format"] == "PE" and h["machine"] == "x86-64" and h["bits"] == 64
    assert rv.parse_macho(b"\xcf\xfa\xed\xfe" + (0x1000007).to_bytes(4, "little") + bytes(24))["machine"] == "x86-64"


def test_malformed_input_does_not_crash(tmp_path):
    p = tmp_path / "junk"; p.write_bytes(b"\x7fELF\x02\x01" + os.urandom(40))
    json.dumps(rv.investigate(str(p)))


def test_investigate_json_bin_ls():
    r = rv.investigate("/bin/ls")
    json.dumps(r)
    assert r["headers"]["format"] == "ELF" and r["strings"]["count"] > 10


def test_cli(hello):
    out = subprocess.run([sys.executable, "-m", "chessx_libs.reversing", hello, "--json"],
                         capture_output=True, text=True, check=True,
                         cwd=os.path.dirname(os.path.dirname(os.path.dirname(rv.__file__))))
    assert json.loads(out.stdout)["headers"]["format"] == "ELF"


@pytest.mark.skipif(not rv.HAVE_ANGR, reason="angr not installed")
def test_angr_cfg_and_reachability(hello):
    s = rv.cfg_summary(hello)
    assert s["available"] and s["function_count"] > 0
    assert rv.reachable(hello, "main", "helper")["reachable"] is True


def test_angr_absent_graceful(monkeypatch):
    from chessx_libs.reversing import angr_helper
    monkeypatch.setattr(angr_helper, "HAVE_ANGR", False)
    assert angr_helper.cfg_summary("/bin/ls")["available"] is False


# --- per-backend tests for analyze_binary -----------------------------------
from chessx_libs.reversing.disasm import _have_r2


@pytest.mark.skipif(not _have_r2(), reason="r2pipe or radare2 binary missing")
@pytest.mark.parametrize("target", ["hello", "/bin/ls"])
def test_backend_radare2(target, request):
    path = request.getfixturevalue("hello") if target == "hello" else target
    r = rv.analyze_binary(path, backend="r2")
    assert r["backend"] == "radare2" and "note" not in r
    assert r["entrypoint"] and r["entry_disasm"] and r["imports"] and r["sections"]
    assert r["function_count"] > 0
    if target == "hello":
        names = {f["name"] for f in r["functions"]}
        assert "main" in names and any("puts" in i for i in r["imports"])


def test_backend_capstone(hello):
    pytest.importorskip("capstone")
    r = rv.analyze_binary(hello, backend="capstone")
    assert r["backend"] == "capstone" and "note" not in r
    assert r["entry_disasm"][0].endswith("xor ebp, ebp")
    assert "puts" in r["imports"]


def test_backend_builtin(hello):
    r = rv.analyze_binary(hello, backend="builtin")
    assert r["backend"] == "builtin" and r["entry_disasm"]
    assert r["entrypoint"] == rv.parse_headers(open(hello, "rb").read())["entrypoint"]


def test_backend_invalid():
    with pytest.raises(ValueError):
        rv.analyze_binary("/bin/ls", backend="ida")


# --- #11 expanded detective mode ------------------------------------------------
import struct as _st
from chessx_libs.reversing import provenance as _prov_mod  # noqa: F401


def _mini_pe_with_imports():
    """Hand-built PE32+ with one .idata section importing KERNEL32.dll!ExitProcess and ordinal #5."""
    b = bytearray(0x400)
    b[:2] = b"MZ"; _st.pack_into("<I", b, 0x3C, 0x40); b[0x40:0x44] = b"PE\x00\x00"
    _st.pack_into("<HHIIIHH", b, 0x44, 0x8664, 1, 0x5F5E1000, 0, 0, 240, 0x22)
    opt = 0x58; _st.pack_into("<H", b, opt, 0x20B); _st.pack_into("<I", b, opt + 16, 0x1000)
    _st.pack_into("<Q", b, opt + 24, 0x140000000)
    _st.pack_into("<II", b, opt + 112 + 8, 0x1000, 40)  # import data directory
    sh = opt + 240; b[sh:sh + 8] = b".idata\x00\x00"
    _st.pack_into("<IIII", b, sh + 8, 0x200, 0x1000, 0x200, 0x200)
    base = 0x200  # file offset of RVA 0x1000
    _st.pack_into("<IIIII", b, base, 0x1040, 0, 0, 0x1080, 0x1040)  # descriptor; next 20 bytes zero = end
    _st.pack_into("<QQQ", b, base + 0x40, 0x1090, (1 << 63) | 5, 0)  # ILT: by-name, by-ordinal, end
    b[base + 0x80:base + 0x8D] = b"KERNEL32.dll\x00"
    b[base + 0x92:base + 0x9E] = b"ExitProcess\x00"
    vi = b""
    for k, v in (("CompanyName", "ChessX Test Co"), ("OriginalFilename", "mini.exe")):
        kk = k.encode("utf-16-le") + b"\x00\x00"
        pad = (-(0x300 + len(vi) + len(kk))) % 4
        vi += kk + b"\x00" * pad + v.encode("utf-16-le") + b"\x00\x00\x00\x00"
    b[0x300:0x300 + len(vi)] = vi
    return bytes(b)


def test_pe_import_table_and_imphash():
    h = rv.parse_pe(_mini_pe_with_imports())
    assert h["import_table"] == {"kernel32.dll": ["ExitProcess", "#5"]}
    assert "kernel32.dll!ExitProcess" in h["imports"]
    assert h["imphash"] == __import__("hashlib").md5(b"kernel32.exitprocess,kernel32.#5").hexdigest()


def test_pe_metadata_version_info_timestamp(tmp_path):
    p = tmp_path / "mini.exe"; p.write_bytes(_mini_pe_with_imports())
    r = rv.provenance(str(p))
    assert r["metadata"]["version_info"]["CompanyName"] == "ChessX Test Co"
    assert r["metadata"]["pe_timestamp"].startswith("2020-")
    assert r["imphash"] and any(t["event"] == "pe.compile_time" for t in r["timeline"])


def test_hashes_and_optional_fuzzy():
    h = rv.hashes(b"abc")
    assert h["sha1"] == "a9993e364706816aba3e25717850c26c9cd0d89d" and "ssdeep" in h and "tlsh" in h


def test_elf_metadata_and_fingerprint(hello):
    r = rv.provenance(hello)
    assert r["metadata"].get("build_id") and any("GCC" in c for c in r["metadata"]["comment"])
    assert r["fingerprint"][0]["toolchain"] in ("GCC", "glibc C runtime")
    assert not r["packing"]["likely_packed"]
    assert {s["name"] for s in r["section_entropy"]} >= {".text"}


def test_packing_detection_high_entropy(tmp_path):
    p = tmp_path / "blob.bin"; p.write_bytes(os.urandom(200_000))
    assert rv.provenance(str(p))["packing"]["likely_packed"]


def test_embedded_zip_and_pdf_carving():
    import io, zipfile
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w") as z:
        z.writestr("payload.txt", "x"); z.comment = b"made-by-test"
    blob = b"HEADER" * 10 + zb.getvalue() + b"%PDF-1.4 /Author (Sam) /Producer (TeX)"
    emb = rv.embedded_resources(blob)
    zipi = next(e for e in emb if e["type"] == "zip")
    assert zipi["offset"] == 60 and zipi["entries"] == ["payload.txt"] and zipi["comment"] == "made-by-test"
    assert next(e for e in emb if e["type"] == "pdf")["info"]["Author"] == "Sam"


def test_xattr_and_zone_identifier_trail(tmp_path):
    p = tmp_path / "dl.bin"; p.write_bytes(b"data")
    (tmp_path / "dl.bin:Zone.Identifier").write_text("[ZoneTransfer]\nZoneId=3\nHostUrl=https://example.com/dl.bin\n")
    try:
        os.setxattr(p, "user.xdg.origin.url", b"https://example.com/dl.bin")
        has_x = True
    except (OSError, AttributeError):
        has_x = False
    t = rv.provenance(str(p))["filesystem"]
    assert t["sidecars"][":Zone.Identifier"]["HostUrl"] == "https://example.com/dl.bin"
    if has_x:
        assert t["xattrs"]["user.xdg.origin.url"] == "https://example.com/dl.bin"


def _build(tool, src, ext, cmd, tmp):
    if not shutil.which(tool):
        pytest.skip(f"{tool} missing")
    s = tmp / f"m.{ext}"; s.write_text(src); out = tmp / f"m_{ext}"
    subprocess.run(cmd(str(s), str(out)), check=True, capture_output=True, cwd=tmp, timeout=300)
    return str(out)


def test_fingerprint_stripped_go(tmp_path):
    b = _build("go", 'package main\nimport "fmt"\nfunc main(){fmt.Println("hi")}\n', "go",
               lambda s, o: ["go", "build", "-ldflags=-s -w", "-o", o, s], tmp_path)
    fp = rv.provenance(b)["fingerprint"]
    assert fp[0]["toolchain"] == "Go" and "D" not in [f["toolchain"] for f in fp]


def test_fingerprint_stripped_rust(tmp_path):
    b = _build("rustc", 'fn main(){println!("hi");}\n', "rs",
               lambda s, o: ["rustc", "-O", "-C", "strip=symbols", "-o", o, s], tmp_path)
    assert rv.provenance(b)["fingerprint"][0]["toolchain"] == "Rust"


def test_investigate_includes_provenance_json():
    r = rv.investigate("/bin/ls")
    json.dumps(r)
    assert r["provenance"]["hashes"]["sha256"] == r["file"]["sha256"]
    assert "provenance" not in rv.investigate("/bin/ls", expanded=False)
