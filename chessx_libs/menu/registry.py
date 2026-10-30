"""Menu entries. Every action imports its package lazily, so a broken package or a missing
optional dependency only marks that entry unavailable."""
import importlib, json, os

# English fallback labels. i18n is used when a key exists there; the rest are listed for the i18n team.
LABELS = {
    "search": "Web search", "board": "Results board", "save": "Save results",
    "menu_math": "Math (evaluate expression)", "menu_prof": "PhD professor",
    "convert": "Base converter", "menu_crypto": "Crypto (TOTP / AEAD demo)",
    "reverse": "Reverse a file", "menu_detective": "File detective (metadata)",
    "download": "Downloader (robots-aware)", "menu_voice": "Voice: speak",
    "menu_robot": "Voice: robot mode on/off", "menu_stt": "Voice: transcribe wav",
    "menu_sounds": "Sound effects", "menu_windows": "Windows layout",
    "menu_pixel": "Interface: sprites / retro text", "menu_scheduler": "Scheduler status",
    "menu_audit": "Code audit", "menu_agents": "Agent Factory", "menu_tamagox": "TamagoX pet",
    "menu_intent": "Intent classifier", "language": "Language", "stats": "Stats",
    "menu_shell": "Free-text shell", "menu_selftest": "Selftest",
    "menu_browser": "ASCII browser", "menu_pixelart": "Pixel-art critters",
    "menu_title": "ChessX menu", "menu_unavailable": "unavailable", "menu_choose": "Choose",
    "quit": "Quit",
}
try:
    from chessx_libs.i18n import KEYS as _KEYS
except Exception:  # i18n itself broken
    _KEYS = ()
MISSING_I18N = sorted(k for k in LABELS if k not in _KEYS)


class Entry:
    def __init__(self, key, module, label, action, needs=()):
        self.key, self.module, self.label, self.action, self.needs = key, module, label, action, needs


def _imp(name):
    return importlib.import_module("chessx_libs." + name)


def availability(module):
    """(ok, reason) for chessx_libs.<module>; never raises."""
    if module is None:
        return True, ""
    try:
        _imp(module)
        return True, ""
    except ModuleNotFoundError as e:
        if e.name and e.name.endswith(module):
            return False, "not installed yet (chessx_libs/%s missing)" % module
        return False, "missing dependency: %s" % e.name
    except Exception as e:
        return False, "import error: %r" % e


# ---- actions: fn(app, ask) -> str ---------------------------------------
def _search(app, ask):
    q = ask("query")
    return app.search(q) if q else ""

def _board(app, ask): return app.board()
def _save(app, ask): return app.handle("save " + (ask("json|csv") or "json"))

def _math(app, ask):
    e = ask("expr")
    return _imp("mathx").dispatch("math " + e, app.t.lang, app._read_block) if e else ""

def _prof(app, ask):
    e = ask("topic args (e.g. ohm V=12 R=4)")
    return _imp("mathx").dispatch("prof " + e, app.t.lang, app._read_block) if e else ""

def _convert(app, ask):
    b = _imp("bases")
    v = ask("value (auto-detect 0x/0b/0o)")
    if not v:
        return ""
    return json.dumps(b.convert_all(v), ensure_ascii=False)

def _crypto(app, ask):
    c = _imp("crypto")
    s = c.new_secret()
    k, n = os.urandom(32), os.urandom(12)
    ok = c.chacha20_poly1305_decrypt(k, n, c.chacha20_poly1305_encrypt(k, n, b"chessx")) == b"chessx"
    return "TOTP secret %s -> code %s | chacha20-poly1305 roundtrip %s | argon2 backend %s" % (
        s, c.totp(s), "ok" if ok else "FAIL", c.ARGON2_BACKEND)

def _reverse(app, ask):
    p = ask("file path")
    if not p:
        return ""
    if not os.path.isfile(p):
        return "file not found: " + p
    r = _imp("reversing")
    data = open(p, "rb").read()
    return json.dumps({"detect": r.detect(data), "urls": r.extract_urls(data)[:20]}, default=str, indent=1)[:4000]

def _detective(app, ask):
    p = ask("file path")
    if not p:
        return ""
    if not os.path.isfile(p):
        return "file not found: " + p
    return json.dumps(_imp("detective").investigate(p), default=str, ensure_ascii=False, indent=1)[:4000]

def _download(app, ask):
    u = ask("url (empty = cancel)")
    return str(_imp("media").download(u)) if u else ""

def _speak(app, ask):
    v = _imp("voice")
    txt = ask("text") or "ChessX"
    v.speak(txt, lang=app.t.lang)
    return "spoken via %s" % (v.available_backends() or ["none"])[0]

def _robot(app, ask):
    v = _imp("voice")
    return "robot mode: %s" % v.robot_mode(not v.robot_mode())

def _stt(app, ask):
    p = ask("wav path")
    if not p:
        return ""
    r = _imp("voice").transcribe_file(p)
    return r if r is not None else "no transcription (file missing or no Vosk model)"

def _sounds(app, ask):
    s = _imp("sounds")
    fx = ask("effect %s" % sorted(s.EFFECTS)) or "success"
    s.play(fx)
    return "played %s via %s" % (fx, s.PLAYER)

def _windows(app, ask): return _imp("windows").Layout(60, 10).render()

def _pixel(app, ask):
    i = _imp("interface")
    return i.render_sprite("knight") + "\n" + i.retro_text(ask("text") or "CHESSX")

def _scheduler(app, ask): return str(_imp("scheduler").Scheduler().status())

def _audit(app, ask):
    a = _imp("audit")
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return a.render_report(a.audit_tree(root), root)[:4000]

def _agents(app, ask):
    cmd = ask("agent command (list | types | show <name> | run <name> ...)") or "list"
    from chessx_libs.agents.cli import main as agent_main
    try:
        agent_main(cmd.split())
    except SystemExit as e:
        return "agent: exit %s" % e.code
    return ""

def _tamagox(app, ask):
    t = _imp("tamagox")
    p = t.Pet(ask("pet name") or "chessx")
    act = ask("action feed|play|sleep|none")
    if act in ("feed", "play", "sleep"):
        getattr(p, act)()
    return p.render()

def _intent(app, ask):
    it = _imp("chess_ai").classify(ask("text"))
    return "%s %s" % (it.name, it.args)

def _lang(app, ask):
    l = ask("en|pt|ja")
    return app.handle("lang " + l) if l else ""

def _stats(app, ask): return app.handle("stats")

def _shell(app, ask):
    app.repl(); return ""

def _selftest(app, ask):
    import chessx
    return "\n".join("%-10s %s" % kv for kv in chessx.selftest().items())

def _browser(app, ask):
    b = _imp("browser")
    url = ask("url (empty = demo page)") or None
    # hands control to the browser's own loop; it reads from the same stdin (q exits)
    b.run(url, input_fn=input)
    return ""

def _pixelart(app, ask):
    import sys
    p = _imp("pixelart")
    name = ask("sprite %s" % p.list_sprites()) or p.list_sprites()[0]
    if sys.stdout.isatty():
        return "frames: %d" % p.animate(name, frames=16)
    return "\n".join(p.render_frame(name, i, color=False) for i in range(2))


def _future(mod, fn_names):
    def run(app, ask):
        m = _imp(mod)
        for n in fn_names:  # first public entry point that exists
            if callable(getattr(m, n, None)):
                return str(getattr(m, n)() or "")
        return "%s has no entry point (%s)" % (mod, "/".join(fn_names))
    return run


ENTRIES = [
    Entry("1", "search", "search", _search), Entry("2", "interface", "board", _board),
    Entry("3", None, "save", _save),
    Entry("4", "mathx", "menu_math", _math), Entry("5", "mathx", "menu_prof", _prof),
    Entry("6", "bases", "convert", _convert), Entry("7", "crypto", "menu_crypto", _crypto),
    Entry("8", "reversing", "reverse", _reverse), Entry("9", "detective", "menu_detective", _detective),
    Entry("10", "media", "download", _download),
    Entry("11", "voice", "menu_voice", _speak), Entry("12", "voice", "menu_robot", _robot),
    Entry("13", "voice", "menu_stt", _stt), Entry("14", "sounds", "menu_sounds", _sounds),
    Entry("15", "windows", "menu_windows", _windows), Entry("16", "interface", "menu_pixel", _pixel),
    Entry("17", "scheduler", "menu_scheduler", _scheduler), Entry("18", "audit", "menu_audit", _audit),
    Entry("19", "agents", "menu_agents", _agents), Entry("20", "tamagox", "menu_tamagox", _tamagox),
    Entry("21", "chess_ai", "menu_intent", _intent), Entry("22", "i18n", "language", _lang),
    Entry("23", None, "stats", _stats), Entry("24", None, "menu_shell", _shell),
    Entry("25", None, "menu_selftest", _selftest),
    Entry("26", "browser", "menu_browser", _browser),
    Entry("27", "pixelart", "menu_pixelart", _pixelart),
]
