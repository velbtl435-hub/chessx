"""Named sound-event registry + integration API (render / save / play).

Every event is a function (rate, seed, **kw) -> float numpy array in [-1, 1].
TamagoX or any other module only needs: list_events(), render(), save(), play(), register().
"""
import os, shutil, subprocess, sys, tempfile
from . import dsp, chiptune, synthwave, cabinet, sfx
from .dsp import RATE
from ._errors import UnknownSound  # noqa: F401  (public: sounds.UnknownSound)

_REGISTRY, _CATEGORY = {}, {}


def register(name, fn=None, category="custom"):
    """register('x', fn) or @register('x'). fn(rate=..., seed=..., **kw) -> np.ndarray."""
    def deco(f):
        _REGISTRY[name], _CATEGORY[name] = f, category
        return f
    return deco(fn) if fn is not None else deco


def list_events(category=None):
    return sorted(n for n in _REGISTRY if category is None or _CATEGORY[n] == category)


def categories():
    return {c: list_events(c) for c in sorted(set(_CATEGORY.values()))}


def _check(event):
    if event not in _REGISTRY:
        raise UnknownSound(event, _REGISTRY)


def render(event, rate=RATE, seed=0, **kw):
    """Render event to a float64 mono array in [-1, 1] (deterministic for a given seed)."""
    _check(event)
    np = dsp.need_numpy()
    x = np.clip(np.nan_to_num(np.asarray(_REGISTRY[event](rate=rate, seed=seed, **kw), float)), -1, 1)
    return x


def save(event, path=None, rate=RATE, seed=0, **kw):
    """Render and write a 16-bit mono WAV; returns path (temp file if path is None)."""
    _check(event)
    path = path or os.path.join(tempfile.gettempdir(), f"chessx_{event}_{seed}.wav")
    return dsp.write_wav(path, render(event, rate, seed, **kw), rate)


def find_player():
    if sys.platform == "win32":
        return "winsound"
    for p in ("aplay", "paplay", "ffplay", "afplay"):
        if shutil.which(p):
            return p
    return "noop"


def play_file(path, player=None, block=False):
    """Play a WAV with the first available player; silently returns 'noop' if none/failed."""
    player = player or find_player()
    if player == "noop" or os.environ.get("CHESSX_MUTE"):
        return "noop"
    try:
        if player == "winsound":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | (0 if block else winsound.SND_ASYNC))
            return player
        args = {"ffplay": [player, "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                "aplay": [player, "-q", path]}.get(player, [player, path])
        p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if block:
            p.wait()
        return player
    except Exception:
        return "noop"


def play(event, enabled=True, block=False, seed=0, **kw):
    """Play a registered event; returns player or 'noop' (muted / no player / playback error).
    Raises UnknownSound (a KeyError) for unknown names."""
    _check(event)
    if not enabled or os.environ.get("CHESSX_MUTE"):
        return "noop"
    try:
        player = find_player()
        if player == "noop":
            return "noop"
        return play_file(save(event, seed=seed, **kw), player, block)
    except Exception:  # e.g. numpy missing -> fall back to stdlib sfx
        return sfx.play(event) if event in sfx.EFFECTS else "noop"


# ---- built-in events -------------------------------------------------------

def _seq(notes, rate, wave_shape="sine", volume=0.6):
    np = dsp.need_numpy()
    parts = []
    for f, d in notes:
        x = dsp.osc(wave_shape, f, d, rate) * volume if f else np.zeros(int(round(d * rate)))
        parts.append(dsp.fade(x, 0.004, rate))
    return dsp.concat(parts)


def _chess_table():
    try:  # reuse media.gen.audio definitions instead of duplicating them
        from chessx_libs.media.gen.audio import CHESS_SOUNDS
        return CHESS_SOUNDS
    except Exception:
        return {"move": [(660, .06)], "capture": [(440, .05), (330, .08)],
                "check": [(880, .08), (0, .03), (880, .08)], "castle": [(523, .06), (659, .06)],
                "promote": [(523, .07), (659, .07), (784, .1)], "game_end": [(784, .15), (659, .15), (523, .3)]}


for _name in ("move", "capture", "check", "castle", "promote", "game_end"):
    def _chess(rate=RATE, seed=0, _n=_name, style="chip", **kw):
        notes = _chess_table()[_n]
        if style == "sine":
            return _seq(notes, rate)
        x = dsp.concat([chiptune.chip_note(f, d, "pulse25", rate=rate) if f else dsp.osc("sine", 0, d, rate)
                        for f, d in notes])
        if _n == "capture":  # add a little wooden knock
            x = dsp.mix(x, 0.6 * cabinet._click(rate, seed, 0.03, 200, 1500, 0.01))
        return dsp.normalize(x, 0.8)
    register(f"chess.{_name}", _chess, "chess")
    register(_name, _chess, "chess")  # short alias


@register("click", category="ui")
def _ui_click(rate=RATE, seed=0, **kw):
    return dsp.normalize(cabinet._click(rate, seed, 0.02, 2000, 8000, 0.003), 0.7)


@register("error", category="ui")
def _ui_error(rate=RATE, seed=0, **kw):
    return dsp.normalize(dsp.concat([chiptune.chip_note(f, .12, "square", rate=rate) for f in (220, 165)]), 0.7)


@register("notify", category="ui")
def _ui_notify(rate=RATE, seed=0, **kw):
    return dsp.normalize(chiptune.jingle(chiptune.JINGLES["notify"], rate=rate), 0.7)


@register("boot", category="ui")
def _ui_boot(rate=RATE, seed=0, **kw):
    return dsp.normalize(dsp.mix(chiptune.jingle(chiptune.JINGLES["boot"], rate=rate),
                                 0.4 * cabinet.hdd(1.0, seeks=3, rate=rate, seed=seed)), 0.85)


for _ln in ("select", "success", "found", "alert"):  # legacy sfx effects as events
    register(_ln, lambda rate=RATE, seed=0, _n=_ln, **kw: _seq(sfx.EFFECTS[_n], rate, volume=0.4), "ui")
register("result", lambda rate=RATE, seed=0, **kw: _seq(sfx.EFFECTS["success"], rate, volume=0.4), "ui")

for _cn, _fn in (("hdd", cabinet.hdd), ("fan", cabinet.fan), ("floppy", cabinet.floppy),
                 ("keyboard", cabinet.keyboard), ("crt", cabinet.crt)):
    register(_cn, lambda rate=RATE, seed=0, _f=_fn, **kw: _f(rate=rate, seed=seed, **kw), "cabinet")

register("chiptune_theme", lambda rate=RATE, seed=0, **kw: chiptune.theme(rate=rate, seed=seed, **kw), "music")
register("synthwave_loop", lambda rate=RATE, seed=0, **kw: synthwave.loop(rate=rate, seed=seed, **kw), "music")
for _jn in chiptune.JINGLES:
    register(f"jingle.{_jn}", lambda rate=RATE, seed=0, _j=_jn, **kw: chiptune.jingle(chiptune.JINGLES[_j], rate=rate), "music")


SCALE = ["C4", "D4", "E4", "G4", "A4", "C5", "D5", "E5", "G5", "A5"]


def sonify(data, steps=32, bpm=160, rate=RATE):
    """Procedural music from arbitrary data (bytes/str/list of numbers): pentatonic chip melody
    + bass whose notes come from the data (section 24.1: music from computer data)."""
    if isinstance(data, str):
        data = data.encode()
    vals = [int(v) for v in (list(data) or [0])]
    lead, bass = [], []
    for i in range(steps):
        v = vals[i % len(vals)] % 256
        lead.append("." if v % 7 == 0 else SCALE[v % len(SCALE)])
        bass.append(["C3", "A2", "F2", "G2"][(i // 8) % 4] if i % 4 == 0 else "-")
    return chiptune.render_pattern({"lead": ("pulse25", lead), "bass": ("triangle", bass)}, bpm=bpm, rate=rate)


register("data", lambda rate=RATE, seed=0, data=b"ChessX", **kw: sonify(data, rate=rate, **kw), "music")


# --- retro (master list section 27): retro.<chip>.<sfx>, category 'retro' ---
def _register_retro():
    try:
        from .retro import CHIPS, RECIPES, render_sfx
    except Exception:  # numpy missing etc.: retro events simply absent
        return
    for _c in CHIPS:
        for _s in RECIPES:
            register(f"retro.{_c}.{_s}",
                     lambda rate=RATE, seed=0, _c=_c, _s=_s, **kw: render_sfx(_c, _s, rate=rate, seed=seed), "retro")
    from .retro import music as _m
    for _c in _m.LAYOUTS:  # procedural tracker music, short by default (bars=2)
        for _st in _m.STYLES:
            register(f"retro.{_c}.music.{_st}",
                     lambda rate=RATE, seed=0, _c=_c, _st=_st, bars=2, loops=1, loop=False, **kw:
                     _m.render_music(_c, _st, seed=seed, bars=bars, rate=rate, loops=loops, loop=loop), "retro")
    register("retro.nes.music.demo",
             lambda rate=RATE, seed=0, loops=1, loop=False, **kw: _m.render_song(
                 _m.parse_song(_m.DEMO), rate=rate, seed=seed, loops=2 if loop and loops == 1 else max(1, int(loops))), "retro")


_register_retro()
