"""Terminal entry point:  python3 chessx.py agent <cmd> ...   (or python3 -m chessx_libs.agents)"""
import argparse, json, sys

from .factory import Factory
from .types import Generator


def wizard(f: Factory):
    """Interactive builder (terminal UI)."""
    ask = lambda q, d="": (input("%s%s: " % (q, " [%s]" % d if d else "")).strip() or d)
    many = lambda q: [x for x in iter(lambda: input(q + " (blank = done): ").strip(), "")]
    print("== ChessX Agent Factory ==  types: " + ", ".join(f.registry.names()))
    d = dict(name=ask("name"), type=ask("type", "researcher"), prompt=ask("prompt"),
             sub_prompts=many("sub-prompt"), script=ask("script (shell)"), code=ask("code (python)"),
             materials=many("material file"), links=many("link"))
    return f.create(**d)


def main(argv=None, factory: Factory = None):
    ap = argparse.ArgumentParser(prog="chessx agent")
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("create"); c.add_argument("name"); c.add_argument("--type", default="researcher")
    c.add_argument("--prompt", default=""); c.add_argument("--sub", action="append", default=[], help="sub-prompt (repeat)")
    c.add_argument("--script", default=""); c.add_argument("--code", default="")
    c.add_argument("--material", action="append", default=[]); c.add_argument("--link", action="append", default=[])
    c.add_argument("--max-depth", type=int); c.add_argument("--budget", type=float)
    c.add_argument("--force", action="store_true")
    sp.add_parser("new", help="interactive wizard")
    sp.add_parser("list")
    s = sp.add_parser("show"); s.add_argument("name")
    r = sp.add_parser("run"); r.add_argument("name")
    d = sp.add_parser("delete"); d.add_argument("name")
    i = sp.add_parser("import"); i.add_argument("path")
    sp.add_parser("types")
    g = sp.add_parser("gen-type"); g.add_argument("description"); g.add_argument("--name"); g.add_argument("--from", dest="base")
    a = ap.parse_args(argv)
    f = factory or Factory()
    if a.cmd == "create":
        lim = {k: v for k, v in (("max_depth", a.max_depth), ("budget", a.budget)) if v is not None}
        out = f.create(overwrite=a.force, name=a.name, type=a.type, prompt=a.prompt, sub_prompts=a.sub, script=a.script,
                       code=a.code, materials=a.material, links=a.link, limits=lim).to_dict()
    elif a.cmd == "new":
        out = wizard(f).to_dict()
    elif a.cmd == "list":
        out = f.list()
    elif a.cmd == "show":
        out = f.load(a.name).to_dict()
    elif a.cmd == "run":
        out = f.run(a.name)
    elif a.cmd == "delete":
        f.delete(a.name); out = "deleted " + a.name
    elif a.cmd == "import":
        out = f.import_file(a.path).to_dict()
    elif a.cmd == "types":
        out = {n: f.registry.resolve(n)["capabilities"] for n in f.registry.names()}
    elif a.cmd == "gen-type":
        gen = Generator(f.registry)
        t = gen.derive(a.base, a.name or a.description, description=a.description) if a.base else gen.from_description(a.description, a.name)
        out = t.to_dict()
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str) if not isinstance(out, str) else out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
