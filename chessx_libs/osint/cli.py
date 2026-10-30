"""Command line: python -m chessx_libs.osint <command> ...

  lookup ENTITY [--kind K] [--source S ...] [--depth N] [--case NAME] [--format text|json|csv|md]
  sources [--kind K]                 list sources with licence / commercial flag
  pwned                              read a password from stdin (never argv) and check k-anonymity range
  case list | case show NAME [--format ..] | case export NAME --format F [-o FILE] | case delete NAME
  audit [--tail N]
Global: --offline (cache only), --commercial (drop non-commercial sources), --dir PATH (data dir).
"""
import argparse, getpass, json, os, sys
from .types import Entity, KINDS


def _out(text, path=None):
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _parser():
    p = argparse.ArgumentParser(prog="python -m chessx_libs.osint", description="ChessX public-source OSINT")
    p.add_argument("--offline", action="store_true", help="cache only, no network")
    p.add_argument("--commercial", action="store_true", help="commercial use: disable non-commercial sources")
    p.add_argument("--dir", help="data dir (cache, audit, cases); default CHESSX_OSINT_DIR or ~/.chessx/osint")
    sub = p.add_subparsers(dest="cmd", required=True)
    lk = sub.add_parser("lookup")
    lk.add_argument("entity")
    lk.add_argument("--kind", choices=KINDS)
    lk.add_argument("--source", action="append")
    lk.add_argument("--depth", type=int, default=1)
    lk.add_argument("--case")
    lk.add_argument("--format", choices=("text", "json", "csv", "md"), default="text")
    s = sub.add_parser("sources")
    s.add_argument("--kind", choices=KINDS)
    sub.add_parser("pwned")
    c = sub.add_parser("case")
    c.add_argument("action", choices=("list", "show", "export", "delete"))
    c.add_argument("name", nargs="?")
    c.add_argument("--format", choices=("text", "json", "csv", "md"), default="text")
    c.add_argument("-o", "--output")
    a = sub.add_parser("audit")
    a.add_argument("--tail", type=int, default=20)
    return p


def _text(findings, errors=()):
    lines = ["%.2f  %-10s %-12s %s%s" % (f.confidence, f.source if len(f.sources) == 1 else "+".join(f.sources),
                                       f.kind, f.title, ("  <%s>" % f.url) if f.url else "") for f in findings]
    lines += ["! %s %s: %s" % e for e in errors]
    return "\n".join(lines) or "(no findings)"


def main(argv=None, client=None, stdin=None) -> int:
    """CLI entry point. Returns a process exit code (0 ok, 1 nothing found / error, 2 usage)."""
    args = _parser().parse_args(argv)
    if args.dir:
        os.environ["CHESSX_OSINT_DIR"] = args.dir
    commercial = True if args.commercial else None
    from .engine import investigate, default_client
    from .case import Case, CaseStore
    from .base import sources as select
    store = CaseStore()

    if args.cmd == "sources":
        for s in select(args.kind, commercial=commercial):
            _out("%-11s %-26s commercial_ok=%-5s %s  [%s]" % (s.name, ",".join(sorted(s.accepts)), s.commercial_ok,
                                                             s.license, s.host))
        return 0
    if args.cmd == "audit":
        from .audit import AuditLog
        from .cache import default_dir
        for r in AuditLog(os.path.join(default_dir(), "audit.jsonl")).read()[-args.tail:]:
            _out(json.dumps(r, ensure_ascii=False))
        return 0
    if args.cmd == "case":
        if args.action == "list":
            _out("\n".join(store.list()) or "(no cases)")
            return 0
        if not args.name:
            _out("case name required")
            return 2
        if args.action == "delete":
            return 0 if store.delete(args.name) else 1
        try:
            case = store.load(args.name)
        except FileNotFoundError:
            _out("no such case: %s" % args.name)
            return 1
        _out(_text(case.findings) if args.format == "text" else case.export(args.format), args.output)
        return 0

    client = client or default_client(args.offline)
    if args.offline:
        client.offline = True
    if args.cmd == "pwned":
        from .sources import pwned
        pw = (stdin or sys.stdin).readline().rstrip("\n") if (stdin or not sys.stdin.isatty()) \
            else getpass.getpass("password (not stored, only 5 SHA-1 chars are sent): ")
        n = pwned.password_count(pw, client)
        _out("FOUND in breaches %d times - do not use it" % n if n else "not found in Pwned Passwords")
        return 1 if n else 0

    try:
        ent = Entity.parse(args.entity, args.kind)
        if ent.kind == "asn" and not ent.value[2:].isdigit():
            raise ValueError("invalid ASN: %s" % args.entity)
    except ValueError as e:
        _out(str(e))
        return 2
    found = investigate(ent, sources=args.source, depth=args.depth, client=client, commercial=commercial)
    if args.case:
        case = store.open(args.case)
        case.add(ent, found)
        store.save(case)
    if args.format == "text":
        _out(_text(found, client.errors))
    else:
        tmp = Case(args.case or "lookup", found, entities=[str(ent)])
        _out(tmp.export(args.format))
    return 0 if found else 1
