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
    print(f"Strings : {r['strings']['count']}  URLs={len(r['indicators']['urls'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
