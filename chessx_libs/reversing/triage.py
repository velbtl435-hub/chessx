"""Defensive static malware triage (PRIORITY #25, spec docs/specs/MALWARE_TRIAGE.md).

Static only: the sample is NEVER executed, no network calls, nothing uploaded.
Heuristics are NOT an antivirus — every verdict carries its score and evidence.

Rules: ChessX TOML/JSON (``cx.*``, MIT) evaluated over the existing reversing
report (strings/imports/sections/entropy/hashes/imphash/fingerprint/packing),
plus optional yara-python (stage D). No eval/exec/pickle anywhere.
"""
from __future__ import annotations

import fnmatch, json, math, os, re

try:  # Python 3.11+
    import tomllib as _toml
except Exception:  # pragma: no cover - fallback to tomli, else JSON-only
    try:
        import tomli as _toml  # type: ignore
    except Exception:
        _toml = None

SCHEMA_VERSION = 1
RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules")
BUILTIN_DIR = os.path.join(RULES_DIR, "builtin")
ENV_RULES = "CHESSX_TRIAGE_RULES"
SEVERITIES = ("info", "low", "medium", "high", "critical")
REQUIRED = {"id": str, "name": str, "severity": str, "description": str, "license": str,
            "version": str, "weight": (int, float), "condition": dict}
OPTIONAL = {"references": list, "author": str, "enabled": bool, "tags": list}
THRESHOLDS = {"suspicious": 15, "likely_malicious": 40}
MAX_REGEX_LEN = 200
MAX_RULE_FILE = 1 << 20  # 1 MiB per rule file
ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,80}$")
PREDICATES = ("strings", "imports", "libraries", "sections", "entropy", "packing", "hashes",
              "imphash", "fingerprint", "headers", "reversal", "file", "indicators")
DISCLAIMER = ("Triagem estática defensiva; amostra nunca executada; sem rede. "
              "Heurísticas não são antivírus.")


class RuleError(ValueError):
    pass


# ---------------------------------------------------------------- loading / validation
def _validate_node(node, path="condition"):
    if not isinstance(node, dict) or len(node) != 1:
        raise RuleError(f"{path}: nó deve ser um dict com exatamente uma chave")
    (k, v), = node.items()
    if k in ("all", "any"):
        if not isinstance(v, list) or not v:
            raise RuleError(f"{path}.{k}: lista não vazia esperada")
        for i, sub in enumerate(v):
            _validate_node(sub, f"{path}.{k}[{i}]")
    elif k == "not":
        _validate_node(v, f"{path}.not")
    elif k in PREDICATES:
        if not isinstance(v, dict) or not v:
            raise RuleError(f"{path}.{k}: dict de parâmetros esperado")
        for rx in v.get("regex_any", []) or []:
            if not isinstance(rx, str) or len(rx) > MAX_REGEX_LEN:
                raise RuleError(f"{path}.{k}: regex inválida/longa demais")
            try:
                re.compile(rx)
            except re.error as exc:
                raise RuleError(f"{path}.{k}: regex inválida: {exc}")
    else:
        raise RuleError(f"{path}: operador/predicado desconhecido {k!r}")


def validate_rule(rule: dict) -> dict:
    """Validate one rule dict (pure data). Raises RuleError. Returns normalized copy."""
    if not isinstance(rule, dict):
        raise RuleError("regra deve ser objeto")
    for k, t in REQUIRED.items():
        if k not in rule:
            raise RuleError(f"campo obrigatório ausente: {k}")
        if not isinstance(rule[k], t) or isinstance(rule[k], bool) and k == "weight":
            raise RuleError(f"campo {k}: tipo inválido")
    for k, t in OPTIONAL.items():
        if k in rule and not isinstance(rule[k], t):
            raise RuleError(f"campo {k}: tipo inválido")
    unknown = set(rule) - set(REQUIRED) - set(OPTIONAL)
    if unknown:
        raise RuleError(f"campos desconhecidos: {sorted(unknown)}")
    if not ID_RE.match(rule["id"]):
        raise RuleError(f"id inválido: {rule['id']!r}")
    if rule["severity"] not in SEVERITIES:
        raise RuleError(f"severity inválida: {rule['severity']!r}")
    if not 0 <= rule["weight"] <= 100:
        raise RuleError("weight fora de 0..100")
    _validate_node(rule["condition"])
    out = dict(rule)
    out.setdefault("references", [])
    out.setdefault("tags", [])
    out.setdefault("enabled", True)
    return out


def _parse_file(path: str) -> list:
    if os.path.getsize(path) > MAX_RULE_FILE:
        raise RuleError("arquivo de regras grande demais")
    with open(path, "rb") as fh:
        raw = fh.read()
    if path.endswith(".json"):
        doc = json.loads(raw.decode("utf-8"))
    elif path.endswith(".toml"):
        if _toml is None:
            raise RuleError("TOML indisponível (Python<3.11 sem tomli); use JSON")
        doc = _toml.loads(raw.decode("utf-8"))
    else:
        raise RuleError("extensão não suportada")
    if isinstance(doc, list):
        rules = doc
    elif isinstance(doc, dict):
        rules = doc.get("rule", doc.get("rules", [doc] if "id" in doc else []))
    else:
        raise RuleError("documento inválido")
    if not isinstance(rules, list):
        raise RuleError("'rule' deve ser lista")
    return rules


def _safe_files(directory: str, exts) -> list:
    """Files directly under *directory* whose realpath stays inside it (no .. / symlink escape)."""
    base = os.path.realpath(directory)
    out = []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return out
    for n in names:
        if not n.endswith(exts):
            continue
        p = os.path.realpath(os.path.join(base, n))
        if os.path.dirname(p) == base and os.path.isfile(p):
            out.append(p)
    return out


def rule_dirs(extra=None) -> list:
    """Load order: builtin → $CHESSX_TRIAGE_RULES (os.pathsep) → *extra* argument."""
    dirs = [BUILTIN_DIR]
    dirs += [d for d in os.environ.get(ENV_RULES, "").split(os.pathsep) if d]
    dirs += list(extra or [])
    return dirs


def manifest() -> dict:
    p = os.path.join(RULES_DIR, "MANIFEST.toml")
    if _toml is None or not os.path.isfile(p):
        return {"schema_version": SCHEMA_VERSION}
    with open(p, "rb") as fh:
        return _toml.load(fh)


def load_rules(extra=None) -> tuple:
    """Return (rules, errors). Invalid file/rule is skipped and reported (fail closed per pack)."""
    rules, errors, seen = [], [], set()
    for d in rule_dirs(extra):
        for f in _safe_files(d, (".toml", ".json")):
            if os.path.basename(f) == "MANIFEST.toml":
                continue
            try:
                raw = _parse_file(f)
                batch = [validate_rule(r) for r in raw]
            except Exception as exc:
                errors.append(f"{f}: {exc}")
                continue
            for r in batch:
                if r["id"] in seen:
                    errors.append(f"{f}: id duplicado {r['id']}")
                    continue
                seen.add(r["id"])
                if r["enabled"]:
                    r["_source"] = f
                    rules.append(r)
    return rules, errors


# ---------------------------------------------------------------- context from report
def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return round(-sum(c / n * math.log2(c / n) for c in counts if c), 3)


def build_context(report: dict, data: bytes | None = None, max_strings: int = 20000) -> dict:
    """Flatten the investigate() report (+ raw bytes) into the fields rules can test."""
    from .strings import strings_with_offsets
    hdr = report.get("headers") or {}
    pv = report.get("provenance") or {}
    rs = report.get("reversal_summary") or {}
    fi = report.get("file") or {}
    strs = strings_with_offsets(data, 5)[:max_strings] if data is not None else (report.get("strings") or {}).get("sample", [])
    imports = [str(i) for i in hdr.get("imports", [])]
    dl = (rs.get("capabilities") or {}).get("delay_imports") or {}
    for lib, funcs in (dl.items() if isinstance(dl, dict) else []):
        imports += [f"{lib}!{f}" for f in funcs]
    ind = report.get("indicators") or {}
    hashes = dict(pv.get("hashes") or {})
    hashes.setdefault("sha256", fi.get("sha256"))
    hashes.setdefault("md5", fi.get("md5"))
    return {
        "strings": strs,
        "imports": imports,
        "libraries": [str(x) for x in hdr.get("libraries", [])],
        "sections": [{"name": s.get("name", ""), "entropy": s.get("entropy")} for s in pv.get("section_entropy", [])]
                    or [{"name": s.get("name", ""), "entropy": None} for s in hdr.get("sections", [])],
        "file_entropy": (report.get("detect") or {}).get("entropy", _entropy(data) if data is not None else 0.0),
        "packing": pv.get("packing") or {},
        "hashes": {k: (v or "").lower() for k, v in hashes.items() if v},
        "imphash": (pv.get("imphash") or hdr.get("imphash") or "") or "",
        "fingerprint": [f.get("toolchain", "") for f in pv.get("fingerprint", []) if f.get("score", 1)]
                       + [o.get("toolchain", "") for o in report.get("origin", []) if isinstance(o, dict)],
        "format": hdr.get("format") or "",
        "capabilities": list(((rs.get("capabilities") or {}).get("capabilities") or {}).keys()),
        "size": fi.get("size", len(data) if data is not None else 0),
        "indicators": ind,
    }


# ---------------------------------------------------------------- evaluation
def _ev(kind, value, offset=None):
    return {"kind": kind, "value": str(value)[:200], "offset": offset}


def _globs(names, pats):
    hits = []
    for p in pats:
        pl = p.lower()
        for n in names:
            if fnmatch.fnmatchcase(n.lower(), pl):
                hits.append((p, n))
                break
    return hits


def _pred(kind: str, p: dict, ctx: dict):
    """Return (matched, evidence). Every key inside *p* must hold (AND)."""
    ev = []
    if kind == "strings":
        if "contains_any" in p:
            found = []
            for needle in p["contains_any"]:
                nl = needle.lower()
                s = next((s for s in ctx["strings"] if nl in s["value"].lower()), None)
                if s:
                    found.append(_ev("string", s["value"], s.get("offset")))
            if len(found) < int(p.get("min_matches", 1)):
                return False, []
            ev += found
        if "regex_any" in p:
            found = []
            for rx in p["regex_any"]:
                c = re.compile(rx, re.I)
                s = next((s for s in ctx["strings"] if c.search(s["value"][:4096])), None)
                if s:
                    found.append(_ev("string", s["value"], s.get("offset")))
            if len(found) < int(p.get("min_matches", 1)):
                return False, []
            ev += found
        return bool(ev), ev
    if kind in ("imports", "libraries"):
        names = ctx[kind]
        if "all" in p:
            h = _globs(names, p["all"])
            if len(h) != len(p["all"]):
                return False, []
            ev += [_ev("import" if kind == "imports" else "library", n) for _, n in h]
        if "any" in p:
            h = _globs(names, p["any"])
            if len(h) < int(p.get("min_matches", 1)):
                return False, []
            ev += [_ev("import" if kind == "imports" else "library", n) for _, n in h]
        return bool(ev), ev
    if kind == "sections":
        secs = ctx["sections"]
        if "name_any" in p:
            want = {x.lower() for x in p["name_any"]}
            hit = [s for s in secs if s["name"].lower() in want]
            if not hit:
                return False, []
            ev += [_ev("section", s["name"]) for s in hit]
        if "entropy_gt" in p:
            hit = [s for s in secs if s["entropy"] is not None and s["entropy"] > p["entropy_gt"]]
            if not hit:
                return False, []
            ev += [_ev("section_entropy", f"{s['name']}={s['entropy']}") for s in hit[:5]]
        return bool(ev), ev
    if kind == "entropy":
        e = ctx["file_entropy"] or 0.0
        ok = e > p.get("file_gt", -1) and e < p.get("file_lt", 9)
        return ok, [_ev("entropy", e)] if ok else []
    if kind == "packing":
        lp = bool(ctx["packing"].get("likely_packed"))
        ok = lp == bool(p.get("likely_packed", True))
        return ok, [_ev("packing", "; ".join(ctx["packing"].get("reasons", [])[:3]) or lp)] if ok else []
    if kind == "hashes":
        for algo in ("sha256", "md5", "sha1"):
            vals = {v.lower() for v in p.get(f"{algo}_any", [])}
            if vals and ctx["hashes"].get(algo) in vals:
                return True, [_ev("hash", f"{algo}:{ctx['hashes'][algo]}")]
        return False, []
    if kind == "imphash":
        ih = ctx["imphash"].lower()
        ok = bool(ih) and ih in {v.lower() for v in p.get("any", [])}
        return ok, [_ev("imphash", ih)] if ok else []
    if kind == "fingerprint":
        needle = p.get("toolchain_contains", "").lower()
        hit = next((f for f in ctx["fingerprint"] if needle and needle in f.lower()), None)
        return bool(hit), [_ev("fingerprint", hit)] if hit else []
    if kind == "headers":
        want = [x.lower() for x in p.get("format_any", [])]
        ok = any(ctx["format"].lower().startswith(w) for w in want)
        return ok, [_ev("format", ctx["format"])] if ok else []
    if kind == "reversal":
        hit = [c for c in ctx["capabilities"] if c in p.get("capability_any", [])]
        return bool(hit), [_ev("capability", c) for c in hit]
    if kind == "file":
        sz = ctx["size"] or 0
        ok = sz > p.get("size_gt", -1) and sz < p.get("size_lt", 1 << 62)
        return ok, [_ev("size", sz)] if ok else []
    if kind == "indicators":
        ind = ctx["indicators"]
        for key in ("urls", "ips", "emails"):
            if f"{key}_count_gt" in p:
                vals = ind.get(key, []) or []
                if len(vals) <= p[f"{key}_count_gt"]:
                    return False, []
                ev += [_ev(key[:-1], v) for v in vals[:5]]
        return bool(ev), ev
    return False, []


def evaluate(node: dict, ctx: dict):
    """Boolean tree evaluation → (bool, evidence)."""
    (k, v), = node.items()
    if k == "all":
        ev = []
        for sub in v:
            ok, e = evaluate(sub, ctx)
            if not ok:
                return False, []
            ev += e
        return True, ev
    if k == "any":
        ev, hit = [], False
        for sub in v:
            ok, e = evaluate(sub, ctx)
            if ok:
                hit, ev = True, ev + e
        return hit, ev
    if k == "not":
        ok, _ = evaluate(v, ctx)
        return (not ok), ([_ev("not", "condição negada ausente")] if not ok else [])
    return _pred(k, v, ctx)


def verdict_for(score: float) -> str:
    if score >= THRESHOLDS["likely_malicious"]:
        return "likely_malicious"
    if score >= THRESHOLDS["suspicious"]:
        return "suspicious"
    return "clean"


def score_matches(matched: list) -> float:
    """Sum of weights, capped at 100; info/low-only hits never exceed the suspicious band."""
    s = min(100.0, float(sum(m["weight"] for m in matched)))
    if matched and all(m["severity"] in ("info", "low") for m in matched):
        s = min(s, THRESHOLDS["likely_malicious"] - 1)
    return round(s, 1)


def run_rules(ctx: dict, rules: list) -> list:
    out = []
    for r in rules:
        try:
            ok, ev = evaluate(r["condition"], ctx)
        except Exception:  # defensive: a bad rule never breaks triage
            continue
        if ok:
            out.append({"id": r["id"], "name": r["name"], "severity": r["severity"], "weight": r["weight"],
                        "engine": "chessx", "evidence": ev[:20], "references": r["references"],
                        "license": r["license"], "author": r.get("author")})
    return out


# ---------------------------------------------------------------- optional YARA engine (stage D)
YARA_MAX_BYTES = 32 << 20
YARA_TIMEOUT = 5
YARA_MAX_FILES = int(os.environ.get("CHESSX_TRIAGE_YARA_MAX", "500") or 500)
_SEV_WEIGHT = {"info": 5, "low": 10, "medium": 20, "high": 35, "critical": 50}


def _yara_module():
    try:
        import yara  # optional: yara-python
        return yara
    except Exception:
        return None


def pack_license(directory: str) -> str:
    """Classify a rule pack by its LICENSE file (walks up to 2 parents). Read-only, offline."""
    d = os.path.realpath(directory)
    for _ in range(3):
        for n in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"):
            p = os.path.join(d, n)
            if os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        t = fh.read(4096)
                except OSError:
                    return "unknown"
                if "Elastic License 2.0" in t:
                    return "Elastic-2.0"
                if "Detection Rule License" in t:
                    return "DRL-1.1"
                if "GNU GENERAL PUBLIC LICENSE" in t:
                    return "GPL-2.0" if "Version 2" in t else "GPL"
                if "Permission is hereby granted, free of charge" in t:
                    return "MIT"
                return "unknown"
        d = os.path.dirname(d)
    return "unknown"


def yara_scan(data: bytes, extra=None) -> dict:
    """Scan bytes with user-provided .yar/.yara files (no includes, no network). Graceful w/o yara."""
    res = {"available": False, "rules_loaded": 0, "matched": [], "errors": [], "truncated": False,
           "timed_out": False, "packs": []}
    yara = _yara_module()
    if yara is None:
        return res
    res["available"] = True
    files = []
    for d in rule_dirs(extra):
        found = _safe_files(d, (".yar", ".yara"))
        if not found:
            continue
        lic = pack_license(d)
        res["packs"].append({"dir": d, "license": lic, "files": len(found)})
        if lic == "Elastic-2.0":  # spec §5: avoided (ELv2 hosted-service limits)
            res["errors"].append(f"yara pack ignorado (Elastic License 2.0): {d}")
            continue
        files += found
    if len(files) > YARA_MAX_FILES:
        res["errors"].append(f"yara: {len(files)} arquivos > limite {YARA_MAX_FILES}; excedentes ignorados")
        files = files[:YARA_MAX_FILES]
    compiled = []
    for f in files:
        try:
            compiled.append((f, yara.compile(filepath=f, includes=False)))
        except Exception as exc:
            res["errors"].append(f"yara compile {os.path.basename(f)}: {exc}")
    res["rules_loaded"] = len(compiled)
    if not compiled:
        return res
    if len(data) > YARA_MAX_BYTES:
        data, res["truncated"] = data[:YARA_MAX_BYTES], True
    for f, rules in compiled:
        try:
            matches = rules.match(data=data, timeout=YARA_TIMEOUT)
        except Exception as exc:
            # real yara-python raises yara.TimeoutError("scanning timed out")
            if isinstance(exc, getattr(yara, "TimeoutError", ())) or "timed out" in str(exc).lower() \
                    or "timeout" in str(exc).lower():
                res["timed_out"] = True
            res["errors"].append(f"yara match {os.path.basename(f)}: {exc}")
            continue
        for m in matches:
            meta = dict(getattr(m, "meta", {}) or {})
            sev = str(meta.get("severity", "medium")).lower()
            sev = sev if sev in SEVERITIES else "medium"
            try:
                w = float(meta.get("score", _SEV_WEIGHT[sev]))
            except (TypeError, ValueError):
                w = _SEV_WEIGHT[sev]
            ev = []
            for sm in list(getattr(m, "strings", []) or [])[:20]:
                if hasattr(sm, "instances"):  # yara-python >= 4.3
                    for inst in list(sm.instances)[:3]:
                        ev.append(_ev("yara_string", sm.identifier, getattr(inst, "offset", None)))
                elif isinstance(sm, tuple) and len(sm) >= 2:  # legacy (offset, id, data)
                    ev.append(_ev("yara_string", sm[1], sm[0]))
            ev = ev or [_ev("yara_rule", m.rule)]
            refs = [str(meta[k]) for k in ("reference", "references", "url") if meta.get(k)]
            res["matched"].append({"id": f"yara.{getattr(m, 'namespace', 'default')}.{m.rule}", "name": m.rule,
                                   "severity": sev, "weight": min(100.0, max(0.0, w)), "engine": "yara",
                                   "evidence": ev[:20], "references": refs,
                                   "license": str(meta.get("license", "")) or None,
                                   "author": str(meta.get("author", "")) or None,  # DRL 1.1: keep attribution
                                   "source": os.path.basename(f)})
    return res


# ---------------------------------------------------------------- public entry point
def _evidence_summary(matched, verdict, score):
    if not matched:
        return [_ev("summary", f"nenhuma regra batida; score={score} → {verdict}")]
    return [_ev("summary", f"{len(matched)} regra(s) batida(s); score={score} → {verdict}")]


ENV_ALLOW = "CHESSX_TRIAGE_ALLOWLIST"
ALLOWLIST_FILE = os.path.join(RULES_DIR, "allowlist.sha256")
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def load_allowlist(extra=None) -> set:
    """Builtin allowlist + files in $CHESSX_TRIAGE_ALLOWLIST (os.pathsep) + *extra* paths."""
    files = [ALLOWLIST_FILE] + [f for f in os.environ.get(ENV_ALLOW, "").split(os.pathsep) if f] + list(extra or [])
    out = set()
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    tok = line.split("#", 1)[0].strip().split()
                    if tok and _HEX64.match(tok[0]):
                        out.add(tok[0].lower())
        except OSError:
            continue
    return out


def build_allowlist(dirs, max_size: int = 64 << 20):
    """Yield 'sha256  path' for regular files under *dirs* (read-only hashing, never executed)."""
    import hashlib
    for d in dirs:
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            p = os.path.join(d, n)
            try:
                if not os.path.isfile(p) or os.path.getsize(p) > max_size:
                    continue
                h = hashlib.sha256()
                with open(p, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                yield f"{h.hexdigest()}  {p}"
            except OSError:
                continue


def triage(report: dict, data: bytes | None = None, extra_rule_dirs=None, allowlist=None) -> dict:
    """Score an investigate() report. Never executes the sample; never touches the network."""
    rules, errors = load_rules(extra_rule_dirs)
    ctx = build_context(report, data)
    matched = run_rules(ctx, rules)
    ys = yara_scan(data, extra_rule_dirs) if data is not None else {"available": _yara_module() is not None,
                                                                    "rules_loaded": 0, "matched": [], "errors": [],
                                                                    "truncated": False, "timed_out": False, "packs": []}
    matched += ys["matched"]
    errors += ys["errors"]
    score = score_matches(matched)
    allow = load_allowlist() if allowlist is None else set(allowlist)
    allowlisted = bool(ctx["hashes"].get("sha256")) and ctx["hashes"]["sha256"] in allow
    if allowlisted:
        score = 0.0
    verdict = verdict_for(score)
    evidence = _evidence_summary(matched, verdict, score)
    if allowlisted:
        evidence.insert(0, _ev("allowlist", f"sha256:{ctx['hashes']['sha256']} na allowlist → clean"))
    return {"disclaimer": DISCLAIMER, "score": score, "verdict": verdict,
            "evidence": evidence, "matched": matched,
            "engines": {"chessx_rules": True, "chessx_rules_loaded": len(rules), "yara": ys["available"],
                        "yara_rules_loaded": ys["rules_loaded"],
                        "packs": ys.get("packs", [])},
            "allowlisted": allowlisted, "limits": {"bytes_scanned": len(data) if data is not None else 0,
                                             "truncated": ys["truncated"], "timed_out": ys["timed_out"]},
            "errors": errors, "confidence": round(min(1.0, 0.3 + 0.1 * len(matched)), 2) if matched else 0.5,
            "thresholds": dict(THRESHOLDS), "schema_version": SCHEMA_VERSION}


def triage_file(path: str, extra_rule_dirs=None) -> dict:
    """Convenience: investigate(path)['triage'] computed from a fresh static report."""
    from .detective import investigate
    r = investigate(path)
    if "triage" in r:
        return r["triage"]
    with open(path, "rb") as fh:
        return triage(r, fh.read(), extra_rule_dirs)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="chessx_libs.reversing.triage",
                                 description="Triagem estática defensiva (não executa amostras; não é antivírus).")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rules", action="append", default=[], help="diretório extra de regras")
    ap.add_argument("--build-allowlist", nargs="+", metavar="DIR", help="imprime 'sha256  path' dos arquivos")
    ap.add_argument("--list-rules", action="store_true")
    a = ap.parse_args(argv)
    if a.build_allowlist:
        for line in build_allowlist(a.build_allowlist):
            print(line)
        return 0
    if a.list_rules:
        rules, errors = load_rules(a.rules)
        for r in rules:
            print(f"{r['id']:<22} {r['severity']:<8} w={r['weight']:<3} {r['license']}  {r['name']}")
        for e in errors:
            print("erro: " + e)
        return 0
    if not a.file:
        ap.error("informe um arquivo")
    from .detective import investigate
    rep = investigate(a.file)
    t = rep["triage"] if not a.rules else triage(rep, open(a.file, "rb").read(), a.rules)
    print(json.dumps(t, indent=2, ensure_ascii=False, default=str) if a.json
          else f"{t['verdict']} score={t['score']} rules={[m['id'] for m in t['matched']]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
