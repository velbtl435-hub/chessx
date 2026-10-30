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


SUS_C = r'''
#include <stdio.h>
extern void VirtualAllocEx(void) __attribute__((weak));
extern void WriteProcessMemory(void) __attribute__((weak));
extern void CreateRemoteThread(void) __attribute__((weak));
const char *a = "UPX!";
const char *b = "http://203.0.113.7:8080/panel/gate.php";
const char *c = "abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwx.onion";
int main(void){ if (VirtualAllocEx) { VirtualAllocEx(); WriteProcessMemory(); CreateRemoteThread(); }
  puts(a); puts(b); puts(c); return 0; }
'''


@pytest.fixture(scope="module")
def suspicious_bin(tmp_path_factory):
    import shutil, subprocess
    if not shutil.which("gcc"):
        pytest.skip("gcc not available")
    d = tmp_path_factory.mktemp("sus")
    (d / "s.c").write_text(SUS_C)
    out = d / "sus"
    subprocess.run(["gcc", "-O0", "-o", str(out), str(d / "s.c")], check=True)  # compiled, never run
    return str(out)


def _triage_path(p, **kw):
    from chessx_libs.reversing.detective import investigate
    r = investigate(p)
    with open(p, "rb") as fh:
        return tr.triage(r, fh.read(), **kw)


def test_synthetic_suspicious_binary(suspicious_bin):
    t = _triage_path(suspicious_bin)
    ids = {m["id"] for m in t["matched"]}
    assert {"cx.inj.process", "cx.pack.known", "cx.c2.url", "cx.c2.ip", "cx.c2.onion"} <= ids
    assert t["verdict"] == "likely_malicious" and t["score"] >= 40
    assert all(m["evidence"] for m in t["matched"])
    assert any(e["offset"] is not None for m in t["matched"] for e in m["evidence"] if e["kind"] == "string")


def test_allowlist_forces_clean(suspicious_bin, tmp_path):
    import hashlib
    h = hashlib.sha256(open(suspicious_bin, "rb").read()).hexdigest()
    al = tmp_path / "al.sha256"
    al.write_text("".join(l.split()[0] + "\n" for l in tr.build_allowlist([os.path.dirname(suspicious_bin)]) if l.endswith(suspicious_bin)))
    assert h in tr.load_allowlist([str(al)])
    t = _triage_path(suspicious_bin, allowlist={h})
    assert t["allowlisted"] and t["verdict"] == "clean" and t["score"] == 0 and t["matched"]
    assert t["evidence"][0]["kind"] == "allowlist"


def test_info_low_only_never_likely():
    m = [{"weight": 30, "severity": "low"}, {"weight": 30, "severity": "info"}]
    assert tr.verdict_for(tr.score_matches(m)) == "suspicious"
    assert tr.score_matches([{"weight": 80, "severity": "high"}] * 2) == 100


def test_investigate_triage_key_last(suspicious_bin):
    from chessx_libs.reversing.detective import investigate
    r = investigate(suspicious_bin)
    keys = list(r)
    assert keys[-1] == "triage" and keys[-2] == "reversal_summary"
    assert r["triage"]["verdict"] == "likely_malicious" and r["triage"]["evidence"]
    json.dumps(r, default=str)


def test_cli_triage_section(suspicious_bin, capsys):
    from chessx_libs.reversing.__main__ import main
    assert main([suspicious_bin]) == 0
    out = capsys.readouterr().out
    assert "--- Triagem" in out and "likely_malicious" in out and "cx.inj.process" in out
    assert tr.main(["--list-rules"]) == 0 and "cx.c2.onion" in capsys.readouterr().out


def test_public_api_exports():
    from chessx_libs import reversing as rv
    assert callable(rv.triage.triage) and callable(rv.triage_file) and callable(rv.investigate) and callable(rv.reversal_summary)


def test_yara_absent_graceful(monkeypatch):
    monkeypatch.setattr(tr, "_yara_module", lambda: None)
    t = tr.triage({"file": {"sha256": "1" * 64}}, b"data")
    assert t["engines"]["yara"] is False and t["engines"]["yara_rules_loaded"] == 0 and t["verdict"] == "clean"


def test_yara_fake_engine_match_offsets_and_attribution(monkeypatch, tmp_path):
    import types
    calls = {}

    class Inst:
        offset = 4

    class SM:
        identifier = "$a"
        instances = [Inst()]

    class M:
        rule, namespace = "Demo_Rule", "default"
        meta = {"author": "Florian Roth", "license": "Detection Rule License 1.1", "severity": "high", "score": 45}
        strings = [SM()]

    class Rules:
        def match(self, data, timeout):
            calls["timeout"] = timeout
            return [M()]

    def compile(filepath, includes):
        calls["includes"] = includes
        return Rules()
    monkeypatch.setattr(tr, "_yara_module", lambda: types.SimpleNamespace(compile=compile))
    (tmp_path / "demo.yar").write_text("rule Demo_Rule { condition: true }")
    t = tr.triage({"file": {"sha256": "2" * 64}}, b"xxxxabc", [str(tmp_path)])
    m = [x for x in t["matched"] if x["engine"] == "yara"][0]
    assert calls == {"includes": False, "timeout": tr.YARA_TIMEOUT}
    assert m["author"] == "Florian Roth" and m["evidence"][0]["offset"] == 4 and t["verdict"] == "likely_malicious"
    assert t["engines"]["yara"] and t["engines"]["yara_rules_loaded"] == 1


# ---- stage E: optional false-positive corpus over system binaries (never executed, read-only)
def _fp_files():
    if sys.platform.startswith("win"):
        pytest.skip("FP corpus: Unix only")
    dirs = [d for d in ("/bin", "/usr/bin") if os.path.isdir(d)]
    if not dirs:
        pytest.skip("FP corpus: /bin and /usr/bin missing")
    files = []
    for d in dirs:
        for n in sorted(os.listdir(d)):
            p = os.path.join(d, n)
            if os.path.isfile(p) and not os.path.islink(p) and os.path.getsize(p) < 8 << 20:
                files.append(p)
    full = os.environ.get("CHESSX_TRIAGE_FP") == "1"  # opt-in for the whole corpus
    return files if full else files[:: max(1, len(files) // 12)][:12]


def test_fp_corpus_system_binaries():
    from chessx_libs.reversing.detective import investigate
    files = _fp_files()
    if not files:
        pytest.skip("FP corpus empty")
    allow = {l.split()[0] for l in tr.build_allowlist(sorted({os.path.dirname(f) for f in files}))}
    likely = 0
    for f in files:
        try:
            r = investigate(f, expanded=True)
        except OSError:
            continue
        data = open(f, "rb").read()
        raw = tr.triage(r, data, allowlist=set())
        al = tr.triage(r, data, allowlist=allow)
        assert al["verdict"] != "likely_malicious" and al["evidence"]  # allowlisted ⇒ never likely
        likely += raw["verdict"] == "likely_malicious"
    assert likely / len(files) <= 0.10  # loose ratio, never exact counts
