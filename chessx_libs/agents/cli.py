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
    r = sp.add_parser("run"); r.add_argument("name"); r.add_argument("--pet", action="store_true", help="TamagóX: run as pet")
    pt = sp.add_parser("pet", help="TamagóX pet of an agent"); pt.add_argument("name")
    pt.add_argument("action", nargs="?", default="show", choices=["show", "feed", "play", "sleep", "revive", "json"])
    d = sp.add_parser("delete"); d.add_argument("name")
    i = sp.add_parser("import"); i.add_argument("path")
    sp.add_parser("types")
    g = sp.add_parser("gen-type"); g.add_argument("description"); g.add_argument("--name"); g.add_argument("--from", dest="base")
    sa = sp.add_parser("schedule", help="schedule an agent"); sa.add_argument("name")
    sa.add_argument("--every", type=int, default=0, help="0 = one-shot"); sa.add_argument("--unit", default="second",
                    help="second|minute|hour|day|week|month|year (PT ok: segundo, minuto, hora, dia, mes, ano)")
    sa.add_argument("--at", default="now", help="now | +30s | +5m | HH:MM | YYYY-MM-DD HH:MM"); sa.add_argument("--times", type=int)
    sp.add_parser("jobs")
    ur = sp.add_parser("unschedule"); ur.add_argument("job_id")
    rr = sp.add_parser("runner", help="run the scheduler loop"); rr.add_argument("--duration", type=float)
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
        if a.pet:
            import os
            from chessx_libs import tamagox
            store = tamagox.PetStore(os.path.join(f.root, "pets")); pet = store.get(a.name)
            ag = f.build(a.name); tamagox.attach(ag, pet, store, force=True)
            out = ag.run(); store.save(pet); print(pet.render())
        else:
            out = f.run(a.name)
    elif a.cmd == "pet":
        import os
        from chessx_libs import tamagox
        store = tamagox.PetStore(os.path.join(f.root, "pets")); f.load(a.name); pet = store.get(a.name)
        if a.action in ("feed", "play", "sleep", "revive"):
            getattr(pet, a.action)()
        store.save(pet)
        out = pet.to_dict() if a.action == "json" else pet.render()
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
    elif a.cmd in ("schedule", "jobs", "unschedule", "runner"):
        from dataclasses import asdict
        from .schedule import AgentScheduler, parse_when
        import os
        sch = AgentScheduler(os.path.join(f.root, "schedule.json"), f.run)
        if a.cmd == "schedule":
            f.load(a.name)
            out = asdict(sch.add(a.name, a.every, a.unit, parse_when(a.at), a.times))
        elif a.cmd == "jobs":
            out = [asdict(j) for j in sch.list()]
        elif a.cmd == "unschedule":
            sch.remove(a.job_id); out = "removed " + a.job_id
        else:
            print("runner: %d jobs, Ctrl+C to stop" % len(sch.jobs))
            try:
                sch.run(a.duration)
            except KeyboardInterrupt:
                pass
            out = [asdict(j) for j in sch.list()]
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str) if not isinstance(out, str) else out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
