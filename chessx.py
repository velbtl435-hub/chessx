#!/usr/bin/env python3
"""ChessX v0.6 - root orchestrator wiring every chessx_libs package.

Usage:
  python3 chessx.py [--menu]        unified numbered menu (default)
  python3 chessx.py --shell         free-text interactive shell
  python3 chessx.py -q "query"      one-shot (search / convert / reverse ...)
  python3 chessx.py --selftest      offline smoke test of every package
  python3 chessx.py agent <cmd>     Agent Factory (create/new/list/run/types/gen-type...; see docs/AGENT_FACTORY.md)
Math: prof <topic> <args> (PhD professor: math, EE, CS, systems)   math <expr>
      draw (multi-line ASCII-art equation, empty line ends)   render <expr>
      steps solve|system|diff|integrate|simplify|limit|matrix <input>   check (multi-line working)
      export <lang|all> <expr>   translate <from> <to> <expr>   calc <snippet> (sandboxed)
Flags: --lang en|pt|ja  --no-boot  --mute  --json  --menu  --shell
The previous v0.5 single-file version is kept as chessx_v05_legacy.py.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib


class _Lazy:
    """Module proxy: imports chessx_libs.<name> on first attribute access, so a broken
    package only fails the feature that uses it (the menu shows it as unavailable)."""
    def __init__(self, name):
        self._name, self._mod = name, None

    def __getattr__(self, attr):
        if self._mod is None:
            self._mod = importlib.import_module("chessx_libs." + self._name)
        return getattr(self._mod, attr)


chess_ai, i18n, interface, search_pkg, mathx = (_Lazy(n) for n in ("chess_ai", "i18n", "interface", "search", "mathx"))
crypto, media, reversing, voice, windows, sounds, detective, bases, scheduler, audit = (_Lazy(n) for n in (
    "crypto", "media", "reversing", "voice", "windows", "sounds", "detective", "bases", "scheduler", "audit"))


def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception:
        return None


def classify(text): return chess_ai.classify(text)
def multi_search(*a, **kw): return search_pkg.multi_search(*a, **kw)


VERSION = "0.6"


class ChessX:
    def __init__(self, lang="en", mute=False, as_json=False):
        self.t = i18n.Translator(lang)
        _safe(voice.bind_translator, self.t)  # voice follows the UI language (en/pt/ja)
        self.as_json = as_json
        if mute:
            os.environ["CHESSX_MUTE"] = "1"
        self.results = []
        self.engines = []
        try:
            self.engines = [search_pkg.DDGSEngine(), search_pkg.DuckDuckGoEngine()]
            if os.environ.get("BRAVE_API_KEY"):
                self.engines.append(search_pkg.BraveEngine())
        except Exception:
            pass  # search unavailable; menu marks it

    # ---- actions -------------------------------------------------------
    def search(self, query, limit=10):
        print(self.t("searching"), query)
        self.results = multi_search(self.engines, query, limit=limit)
        _safe(sounds.play, "result" if self.results else "error")
        if self.as_json:
            return json.dumps([r.to_dict() for r in self.results], ensure_ascii=False, indent=1)
        if not self.results:
            return self.t("no_results")
        lines = []
        for i, r in enumerate(self.results, 1):
            lines.append("%2d. %s  [%s %.2f]\n    %s" % (i, r.title, ",".join(r.engines or [r.engine]), r.score, r.url))
        return "\n".join(lines)

    def board(self):
        cells = [interface.Cell(r.title[:30], r.url, "web", r.score) for r in self.results]
        return interface.Board(cells).render() if cells else self.t("no_results")

    def handle(self, text):
        if _safe(mathx.is_math_command, text):
            return mathx.dispatch(text, self.t.lang, self._read_block)
        it = classify(text)
        a = it.args
        if it.name == "empty":
            return ""
        if it.name == "quit":
            raise SystemExit(0)
        if it.name == "help":
            return __doc__
        if it.name == "lang":
            self.t.set_lang(a["lang"]); return "lang=" + a["lang"]
        if it.name == "convert":
            if "value" not in a:
                return "convert: value missing (e.g. convert ff hex to bin)"
            return bases.to_base(bases.from_base(a["value"], a["src"]), a["dst"])
        if it.name == "open":
            i = a["index"] - 1
            if 0 <= i < len(self.results):
                return self.results[i].url
            return "no result #%d" % a["index"]
        if it.name == "reverse":
            p = a["path"]
            if not os.path.isfile(p):
                return "file not found: " + p
            rep = detective.investigate(p)
            return json.dumps(rep, default=str, ensure_ascii=False, indent=1)[:4000]
        if it.name == "stats":
            return json.dumps({"results": len(self.results), "engines": [e.name for e in self.engines],
                               "tts": voice.TTS_BACKEND, "stt": voice.STT_BACKEND, "player": sounds.PLAYER})
        if it.name == "save":
            fmt = a.get("fmt", "json")
            path = "chessx_results." + ("csv" if fmt == "csv" else "json")
            with open(path, "w", encoding="utf-8") as fh:
                if fmt == "csv":
                    fh.write("title,url,score\n")
                    for r in self.results:
                        fh.write('"%s",%s,%.3f\n' % (r.title.replace('"', "'"), r.url, r.score))
                else:
                    json.dump([r.to_dict() for r in self.results], fh, ensure_ascii=False, indent=1)
            return "saved " + path
        if it.name == "refresh":
            return "refresh every %ss (use scheduler in interactive mode)" % a.get("seconds", 60)
        return self.search(a.get("query", text))

    def _read_block(self, prompt="... "):
        """Read a multi-line block from the terminal; an empty line (or EOF) ends it."""
        lines = []
        while True:
            try:
                line = input(prompt)
            except EOFError:
                break
            if not line.strip():
                break
            lines.append(line)
        return lines

    def repl(self):
        print("ChessX v" + VERSION)
        print(self.t("welcome"))
        while True:
            try:
                line = input(self.t("prompt") + " ")
            except (EOFError, KeyboardInterrupt):
                print(); break
            try:
                out = self.handle(line)
            except SystemExit:
                break
            except Exception as e:  # keep the shell alive, report the error
                out = "error: %s" % e
                _safe(sounds.play, "error")
            if out:
                print(out)


def selftest():
    import tempfile
    ok = {}
    def check(name, fn):
        try:
            fn(); ok[name] = "ok"
        except Exception as e:
            ok[name] = "FAIL: %r" % e
    check("chess_ai", lambda: [classify("open 3").name == "open" or 1 / 0,
                               classify("convert hex to binary").name == "convert" or 1 / 0])
    check("i18n", lambda: i18n.Translator("pt")("welcome") or 1 / 0)
    check("interface", lambda: interface.Board([interface.Cell("a"), interface.Cell("b")]).render())
    check("crypto", lambda: crypto.chacha20_poly1305_decrypt(bytes(32), bytes(12),
          crypto.chacha20_poly1305_encrypt(bytes(32), bytes(12), b"x")) == b"x" or 1 / 0)
    def srch():
        from chessx_libs.search import MockEngine, DuckDuckGoEngine as DDG
        from chessx_libs.search.engines import split_glued_title
        res = multi_search([MockEngine("a"), MockEngine("b")], "chess", limit=5)
        assert res and all(r.url for r in res)
        page = '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fx.io%2F">X</a>'
        assert DDG().parse(page, 5)[0].url == "https://x.io/"
        assert split_glued_title("A title - GitHubB other oneC third one", ["B other one", "C third one"]) \
            == "A title - GitHub | B other one | C third one"
    check("search", srch)
    check("media", lambda: media.RateLimiter)
    check("reversing", lambda: reversing.extract_urls(b"see https://x.io/a") == ["https://x.io/a"] or 1 / 0)
    check("voice", lambda: (voice.speak("x", dry_run=True), voice.transcribe_file("/nonexistent.wav") is None or 1 / 0))
    check("windows", lambda: windows.Layout(60, 10).render())
    check("sounds", lambda: sounds.synth("boot"))
    def det():
        p = tempfile.mktemp(); open(p, "wb").write(b"%PDF-1.4 /Author (x)"); detective.investigate(p); os.remove(p)
    check("detective", det)
    check("bases", lambda: bases.convert("ff", 16, 2) == "11111111" or 1 / 0)
    check("scheduler", lambda: scheduler.Scheduler().status())
    def agents_check():
        from chessx_libs.agents import Agent, Limits, AgentLimitError
        from chessx_libs import tamagox
        r = Agent("st", limits=Limits(max_depth=2)); r.spawn("a").spawn("b")
        try:
            r.children[0].children[0].spawn("c"); raise AssertionError("depth guard")
        except AgentLimitError:
            pass
        p = tamagox.Pet("st"); tamagox.attach(r, p, force=True); r.run(); assert p.xp > 0
    check("agents", agents_check)
    check("audit", lambda: audit.audit_tree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chessx_libs")))
    def menu_check():
        from chessx_libs.menu import ENTRIES, availability
        assert len({e.key for e in ENTRIES}) == len(ENTRIES)
        assert availability("definitely_not_a_pkg")[0] is False
    check("menu", menu_check)
    check("native", lambda: importlib.import_module("chessx_libs.native.hello_fusion").crc32(b"123456789") == 0xCBF43926 or 1 / 0)
    check("mathx", lambda: mathx.dispatch("prof ohm V=12 R=4").startswith("I = V/R") or 1 / 0)
    return ok


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("agent", "agents"):
        from chessx_libs.agents.cli import main as agent_main
        return agent_main(argv[1:])
    ap = argparse.ArgumentParser(prog="chessx")
    ap.add_argument("-q", "--query")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--no-boot", action="store_true")
    ap.add_argument("--mute", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--menu", action="store_true", help="unified numbered menu (default with no args)")
    ap.add_argument("--shell", action="store_true", help="free-text shell (the pre-menu default)")
    a = ap.parse_args(argv)
    if a.selftest:
        res = selftest()
        for k, v in res.items():
            print("%-10s %s" % (k, v))
        return 0 if all(v == "ok" for v in res.values()) else 1
    app = ChessX(a.lang, a.mute, a.json)
    if a.query:
        print(app.handle(a.query))
        return 0
    if not a.no_boot and sys.stdin.isatty():
        _safe(interface.boot_sequence, duration=2.0)
    _safe(sounds.play, "boot")
    if a.shell:
        app.repl()
        return 0
    from chessx_libs.menu import Menu  # --menu, and the default when no -q/--selftest/--shell
    return Menu(app).loop()


if __name__ == "__main__":
    sys.exit(main())
