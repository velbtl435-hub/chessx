"""Regression tests for chessx_libs.detective public API (used by menu entry 9 and chessx.py 'reverse')."""
import importlib, inspect, io, json, os, struct, sys, zipfile, zlib
import pytest
from chessx_libs import detective as dt
from chessx_libs.detective import investigate as inv_mod

INV_KEYS = ["metadata", "hashes", "indicators", "origin_hints", "provenance", "reverse_search", "embedded_payloads"]


def _png(text_k=b"Software", text_v=b"ChessX-Painter " + b"x" * 300):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + chunk(b"tEXt", text_k + b"\x00" + text_v) + chunk(b"IEND", b""))


def _docx():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<x/>")
        z.writestr("docProps/core.xml", "<cp><dc:creator>Sam</dc:creator><cp:lastModifiedBy>Coder</cp:lastModifiedBy>"
                                        "<dcterms:created>2026-10-30</dcterms:created></cp>")
    return b.getvalue()


@pytest.fixture
def samples(tmp_path):
    files = {"pdf": b"%PDF-1.4 /Author (x) /Producer (TeX) see https://ex.com/a", "png": _png(), "docx": _docx(),
             "jpg": b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00Canon EOS 5D camera" + b"\x00" * 20,
             "txt": b"hello http://example.org/z", "bin": b"MZ" + b"\x00" * 100 + _docx()}
    out = {}
    for k, v in files.items():
        p = tmp_path / f"s.{k}"; p.write_bytes(v); out[k] = str(p)
    return out


def test_public_api_names_and_signatures():
    assert dt.__all__[:5] == ["investigate", "metadata", "provenance_chain", "hashes", "reverse_search_links"]
    sig = {n: str(inspect.signature(getattr(dt, n))) for n in dt.__all__[:5]}
    assert sig == {"investigate": "(path: str) -> dict", "metadata": "(path: str) -> dict",
                   "provenance_chain": "(meta: dict, iocs: dict, hints: list) -> list",
                   "hashes": "(data: bytes) -> dict", "reverse_search_links": "(h: dict, name: str) -> dict"}


def test_menu_entry9_path(samples):
    """Exactly what chessx_libs/menu/registry.py::_detective and chessx.py 'reverse' do."""
    for p in samples.values():
        rep = dt.investigate(p)
        assert list(rep) == INV_KEYS
        s = json.dumps(rep, default=str, ensure_ascii=False, indent=1)[:4000]
        assert s.startswith("{") and '"metadata"' in s


def test_menu_registry_entry9_callable(samples):
    reg = importlib.import_module("chessx_libs.menu.registry")
    out = reg._detective(None, lambda prompt: samples["pdf"])
    assert '"pdf_info"' in out and '"Author": "x"' in out
    assert reg._detective(None, lambda prompt: "/nope/missing") == "file not found: /nope/missing"


def test_return_shapes(samples):
    r = dt.investigate(samples["pdf"])
    assert set(r["hashes"]) == {"md5", "sha1", "sha256"}
    assert r["metadata"]["pdf_info"] == {"Author": "x", "Producer": "TeX"}
    assert ("authored", "Author", "x") in r["provenance"] and r["provenance"][-1][:2] == ("filesystem", "modified")
    assert set(r["reverse_search"]) == {"virustotal", "web_hash", "web_name", "archive"}
    png = dt.metadata(samples["png"])["png_text"]["Software"]
    assert len(png) > 300  # detective keeps untruncated values (as before)
    z = dt.metadata(samples["docx"])["zip"]
    assert z["entries"] == 2 and z["creator"] == "Sam" and z["lastModifiedBy"] == "Coder"
    assert "Canon EOS 5D camera" in dt.metadata(samples["jpg"])["exif_strings"]
    assert any(e["type"] == "zip" and e["offset"] == 102 for e in dt.investigate(samples["bin"])["embedded_payloads"])


def test_matches_reference_implementation(samples):
    """Compare against the pre-refactor implementation if a copy is available (CHESSX_DETECTIVE_REF dir)."""
    ref = os.environ.get("CHESSX_DETECTIVE_REF")
    if not ref:
        pytest.skip("set CHESSX_DETECTIVE_REF to a dir holding the old investigate.py")
    spec = importlib.util.spec_from_file_location("chessx_libs.detective._ref", os.path.join(ref, "investigate.py"))
    old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
    for p in samples.values():
        a, b = old.investigate(p), dt.investigate(p)
        b.pop("embedded_payloads")
        assert json.loads(json.dumps(a, default=str)) == json.loads(json.dumps(b, default=str)), p


def test_fallback_without_reversing(samples, monkeypatch):
    saved = {k: v for k, v in sys.modules.items() if k.startswith("chessx_libs.reversing") or k.startswith("chessx_libs.detective")}
    for k in saved:
        monkeypatch.delitem(sys.modules, k)
    monkeypatch.setitem(sys.modules, "chessx_libs.reversing", None)
    try:
        m = importlib.import_module("chessx_libs.detective.investigate")
        assert m.HAVE_REVERSING is False
        r = m.investigate(samples["pdf"])
        assert list(r) == INV_KEYS and set(r["hashes"]) == {"md5", "sha1", "sha256"}
        assert r["embedded_payloads"] == [] and r["metadata"]["size"] > 0
        json.dumps(r, default=str)
    finally:
        for k in [k for k in sys.modules if k.startswith("chessx_libs.detective")]:
            sys.modules.pop(k, None)
        sys.modules.update(saved)
