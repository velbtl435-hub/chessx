"""Triage (#25) tests — synthetic inputs only; EICAR built at runtime, never stored."""
import json, os, sys
import pytest
from chessx_libs.reversing import triage as tr


@pytest.fixture
def eicar_file(tmp_path):
    # Assembled from fragments so the canonical test string never appears in the repo.
    parts = ["X5O!P%@AP[4", "\\PZX54(P^)7CC)7}$", "EIC" + "AR-STANDARD-", "ANTI" + "VIRUS-TEST-", "FILE!$H+H*"]
    p = tmp_path / "t.bin"
    p.write_bytes("".join(parts).encode())
    yield str(p)
    try:
        p.unlink()
    except FileNotFoundError:
        pass


def _r(rule, **kw):
    base = {"id": "cx.t.x", "name": "n", "severity": "low", "description": "d", "license": "MIT",
            "version": "1.0.0", "weight": 5, "condition": {"strings": {"contains_any": ["zz"]}}}
    base.update(rule, **kw)
    return base


def test_validate_ok_and_errors():
    assert tr.validate_rule(_r({}))["enabled"] is True
    for bad in ({"severity": "huge"}, {"weight": 500}, {"id": "../x"}, {"condition": {"eval": {}}},
                {"condition": {"all": []}}, {"extra": 1}, {"condition": {"strings": {"regex_any": ["("]}}}):
        with pytest.raises(tr.RuleError):
            tr.validate_rule(_r(bad))
    with pytest.raises(tr.RuleError):
        tr.validate_rule({"id": "cx.a"})


def test_builtin_rules_load_clean():
    rules, errors = tr.load_rules()
    assert errors == [] and any(r["id"] == "cx.test.eicar" for r in rules)
    assert all(r["license"] == "MIT" and r["id"].startswith("cx.") for r in rules)


def test_load_order_dups_and_bad_pack(tmp_path, monkeypatch):
    (tmp_path / "a.json").write_text(json.dumps([_r({"id": "cx.test.eicar"}), _r({"id": "cx.t.ok"})]))
    (tmp_path / "b.toml").write_text("not = [valid")
    monkeypatch.setenv(tr.ENV_RULES, str(tmp_path))
    rules, errors = tr.load_rules()
    ids = [r["id"] for r in rules]
    assert ids.index("cx.test.eicar") < ids.index("cx.t.ok")  # builtin first
    assert any("duplicado" in e for e in errors) and any("b.toml" in e for e in errors)


def test_symlink_escape_ignored(tmp_path):
    outside = tmp_path / "out"; outside.mkdir()
    (outside / "x.json").write_text(json.dumps([_r({"id": "cx.t.esc"})]))
    d = tmp_path / "rules"; d.mkdir()
    try:
        os.symlink(outside / "x.json", d / "x.json")
    except (OSError, NotImplementedError):
        pytest.skip("symlink unsupported")
    rules, _ = tr.load_rules([str(d)])
    assert "cx.t.esc" not in [r["id"] for r in rules]


def test_boolean_logic():
    ctx = {"strings": [{"value": "hello UPX! x", "offset": 7}], "imports": ["VirtualAllocEx"], "libraries": [],
           "sections": [], "file_entropy": 1, "packing": {}, "hashes": {}, "imphash": "", "fingerprint": [],
           "format": "PE", "capabilities": [], "size": 10, "indicators": {}}
    ok, ev = tr.evaluate({"all": [{"strings": {"contains_any": ["upx!"]}}, {"imports": {"any": ["virtualalloc*"]}}]}, ctx)
    assert ok and ev[0]["offset"] == 7
    assert not tr.evaluate({"not": {"headers": {"format_any": ["PE"]}}}, ctx)[0]
    assert tr.evaluate({"any": [{"imports": {"any": ["nope"]}}, {"file": {"size_lt": 100}}]}, ctx)[0]


def test_eicar_detected_without_literal(eicar_file):
    with open(eicar_file, "rb") as fh:
        data = fh.read()
    import hashlib
    rep = {"file": {"sha256": hashlib.sha256(data).hexdigest(), "md5": hashlib.md5(data).hexdigest(), "size": len(data)}}
    t = tr.triage(rep, data)
    assert [m["id"] for m in t["matched"]] == ["cx.test.eicar"] and t["score"] >= 40
    assert t["verdict"] == "likely_malicious" and t["evidence"] and t["matched"][0]["evidence"]


def test_no_eicar_literal_in_repo():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    needle = ("EICAR" + "-STANDARD-ANTIVIRUS").encode()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__", "node_modules")]
        for f in fn:
            p = os.path.join(dp, f)
            try:
                if os.path.getsize(p) < 5 << 20:
                    with open(p, "rb") as fh:
                        assert needle not in fh.read(), p
            except OSError:
                pass


def test_clean_verdict_still_has_score_and_evidence():
    t = tr.triage({"file": {"sha256": "0" * 64, "size": 3}}, b"abc")
    assert t["verdict"] == "clean" and t["score"] == 0 and t["evidence"] and "antivírus" in t["disclaimer"]
