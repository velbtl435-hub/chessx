#!/usr/bin/env python3
"""ChessX v0.6 - root orchestrator wiring every chessx_libs package.

Usage:
  python3 chessx.py                 interactive shell
  python3 chessx.py -q "query"      one-shot (search / convert / reverse ...)
  python3 chessx.py --selftest      offline smoke test of every package
Flags: --lang en|pt|ja  --no-boot  --mute  --json
The previous v0.5 single-file version is kept as chessx_v05_legacy.py.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chessx_libs.chess_ai import classify
from chessx_libs.i18n import Translator
from chessx_libs.interface import boot_sequence, Board, Cell
from chessx_libs.search import multi_search, DuckDuckGoEngine, DDGSEngine, BraveEngine
from chessx_libs import crypto, media, reversing, voice, windows, sounds, detective, bases, scheduler, audit

VERSION = "0.6"


class ChessX:
    def __init__(self, lang="en", mute=False, as_json=False):
        self.t = Translator(lang)
        self.as_json = as_json
        if mute:
            os.environ["CHESSX_MUTE"] = "1"
        self.results = []
        self.engines = [DDGSEngine(), DuckDuckGoEngine()]
        if os.environ.get("BRAVE_API_KEY"):
            self.engines.append(BraveEngine())

    # ---- actions -------------------------------------------------------
    def search(self, query, limit=10):
        print(self.t("searching"), query)
        self.results = multi_search(self.engines, query, limit=limit)
        sounds.play("result" if self.results else "error")
        if self.as_json:
            return json.dumps([r.to_dict() for r in self.results], ensure_ascii=False, indent=1)
        if not self.results:
            return self.t("no_results")
        lines = []
        for i, r in enumerate(self.results, 1):
            lines.append("%2d. %s  [%s %.2f]\n    %s" % (i, r.title, ",".join(r.engines or [r.engine]), r.score, r.url))
        return "\n".join(lines)

    def board(self):
        cells = [Cell(r.title[:30], r.url, "web", r.score) for r in self.results]
        return Board(cells).render() if cells else self.t("no_results")

    def handle(self, text):
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
                sounds.play("error")
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
    check("i18n", lambda: Translator("pt")("welcome") or 1 / 0)
    check("interface", lambda: Board([Cell("a"), Cell("b")]).render())
    check("crypto", lambda: crypto.chacha20_poly1305_decrypt(bytes(32), bytes(12),
          crypto.chacha20_poly1305_encrypt(bytes(32), bytes(12), b"x")) == b"x" or 1 / 0)
    check("media", lambda: media.RateLimiter)
    check("reversing", lambda: reversing.extract_urls(b"see https://x.io/a") == ["https://x.io/a"] or 1 / 0)
    check("voice", lambda: voice.TTS_BACKEND)
    check("windows", lambda: windows.Layout(60, 10).render())
    check("sounds", lambda: sounds.synth("boot"))
    def det():
        p = tempfile.mktemp(); open(p, "wb").write(b"%PDF-1.4 /Author (x)"); detective.investigate(p); os.remove(p)
    check("detective", det)
    check("bases", lambda: bases.convert("ff", 16, 2) == "11111111" or 1 / 0)
    check("scheduler", lambda: scheduler.Scheduler().status())
    check("audit", lambda: audit.audit_tree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chessx_libs")))
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(prog="chessx")
    ap.add_argument("-q", "--query")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--no-boot", action="store_true")
    ap.add_argument("--mute", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
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
    if not a.no_boot:
        boot_sequence(duration=2.0)
    sounds.play("boot")
    app.repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
