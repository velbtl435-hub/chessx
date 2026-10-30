"""CLI: python -m chessx_libs.reversing <file> [--json] [--angr]"""
import argparse, json, sys
from .detective import investigate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chessx_libs.reversing", description="Static file analysis (authorized targets only).")
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true", help="print full JSON report")
    ap.add_argument("--angr", action="store_true", help="add angr CFG summary (if installed)")
    ap.add_argument("--min-len", type=int, default=5)
    a = ap.parse_args(argv)
    try:
        r = investigate(a.file, min_str=a.min_len, use_angr=a.angr)
    except OSError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, indent=2, default=str))
        return 0
    h, d = r["headers"], r.get("disasm", {})
    print(f"Arquivo : {r['file']['path']} ({r['file']['size']} bytes)")
    print(f"SHA-256 : {r['file']['sha256']}")
    print(f"Tipo    : {r['detect']['type']} | formato={h.get('format')} arch={h.get('machine')} entropia={r['detect']['entropy']}")
    if r["libmagic"]:
        print(f"libmagic: {r['libmagic']}")
    print("Origem  : " + (", ".join(o["toolchain"] for o in r["origin"]) or "-"))
    if d:
        print(f"Disasm  : backend={d.get('backend')} entry={hex(d['entrypoint']) if d.get('entrypoint') is not None else '-'} "
              f"funções={d.get('function_count')} imports={len(d.get('imports', []))}")
        for line in d.get("entry_disasm", [])[:8]:
            print("   " + line)
    pv = r.get("provenance") or {}
    if pv:
        print("Toolchain: " + (", ".join(f"{f['toolchain']}({f['confidence']})" for f in pv["fingerprint"]) or "-"))
        print(f"Empacotado: {'sim' if pv['packing']['likely_packed'] else 'não'} {pv['packing']['reasons'][:2]}")
        meta = {k: v for k, v in pv["metadata"].items() if v}
        if meta:
            print(f"Metadados: {meta}")
        if pv["embedded"]:
            print(f"Embutidos: {[(hex(e['offset']), e['type']) for e in pv['embedded'][:5]]}")
    print(f"Strings : {r['strings']['count']}  URLs={len(r['indicators']['urls'])}")
    rs = r.get("reversal_summary") or {}
    if rs and not rs.get("error"):
        print("--- Reversão (#24) ---")
        print(rs.get("narrative_pt") or "-")
        tc = rs.get("toolchain") or {}
        print(f"Toolchain: lang={tc.get('language')} comp={tc.get('compiler')} "
              f"link={tc.get('linker')} rt={tc.get('runtime')} conf={tc.get('confidence')}")
        bs = rs.get("build_settings") or {}
        print(f"Build    : PIE={bs.get('pie')} NX={bs.get('nx')} RELRO={bs.get('relro')} "
              f"canary={bs.get('stack_canary')} fortify={bs.get('fortify')} "
              f"stripped={bs.get('stripped')} static={bs.get('static')}")
        caps = rs.get("capabilities") or {}
        if caps.get("capabilities"):
            print("Caps     : " + ", ".join(f"{k}:{len(v)}" for k, v in caps["capabilities"].items()))
        cfg = rs.get("cfg") or {}
        if cfg.get("function_count"):
            print(f"CFG      : funcs={cfg['function_count']} backend={cfg.get('backend')} entry→{cfg.get('entry_to_main')}")
        print(f"Confiança: {rs.get('confidence')}")
    tg = r.get("triage") or {}
    if tg:
        print("--- Triagem (#25, estática; não é antivírus) ---")
        print(f"Veredito : {tg.get('verdict')}  score={tg.get('score')}"
              + ("  [allowlist]" if tg.get("allowlisted") else ""))
        for m in (tg.get("matched") or [])[:8]:
            ev = m.get("evidence") or [{}]
            off = ev[0].get("offset")
            print(f"  {m['severity']:<8} +{m['weight']:<3} {m['id']}: {str(ev[0].get('value'))[:60]}"
                  + (f" @0x{off:x}" if isinstance(off, int) else ""))
        for e in (tg.get("evidence") or [])[:2]:
            print(f"  · {e.get('value')}")
        eng = tg.get("engines") or {}
        print(f"Engines  : chessx={eng.get('chessx_rules_loaded')} yara={eng.get('yara')}({eng.get('yara_rules_loaded')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
