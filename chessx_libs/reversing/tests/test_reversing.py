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
