"""Interactive loop for the unified menu. Reads with input() so piped stdin works; EOF exits."""
from .registry import ENTRIES, LABELS, availability, _KEYS


class Menu:
    def __init__(self, app, entries=ENTRIES, inp=input, out=print):
        self.app, self.entries, self.inp, self.out = app, entries, inp, out

    def label(self, key):
        return self.app.t(key) if key in _KEYS else LABELS.get(key, key)

    def render(self):
        lines = ["== %s ==" % self.label("menu_title")]
        for e in self.entries:
            ok, why = availability(e.module)
            tag = "" if ok else "  [%s: %s]" % (self.label("menu_unavailable"), why)
            lines.append("%3s. %s%s" % (e.key, self.label(e.label), tag))
        lines.append("  q. %s" % self.label("quit"))
        return "\n".join(lines)

    def ask(self, what):
        try:
            return self.inp("  %s: " % what).strip()
        except EOFError:
            return ""

    def run_entry(self, e):
        ok, why = availability(e.module)
        if not ok:
            return "%s: %s" % (self.label("menu_unavailable"), why)
        try:
            return e.action(self.app, self.ask)
        except SystemExit:
            raise
        except Exception as ex:  # one entry failing never kills the menu
            return "error in %s: %r" % (e.module or e.label, ex)

    def loop(self):
        by_key = {e.key: e for e in self.entries}
        while True:
            self.out(self.render())
            try:
                c = self.inp("%s> " % self.label("menu_choose")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                self.out(""); return 0
            if c in ("q", "quit", "exit", "0"):
                return 0
            e = by_key.get(c)
            res = self.run_entry(e) if e else self.label("invalid_command") + ": " + c
            if res:
                self.out(res)
