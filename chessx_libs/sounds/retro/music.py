"""Tracker-style retro music on the section-27 chips (master list section 27, music).

Song model (tracker):
  * Song(chip, bpm, speed, channels, patterns, order, loop)
  * row duration = speed * 2.5 / bpm seconds (classic tracker tick = 2.5/bpm s; speed = ticks/row).
  * pattern = {channel_name: [cell, ...]} with the same number of rows per channel.
  * cell = None (hold / empty) or dict: n (MIDI note) | off (note cut) | drum ('k' kick, 's' snare, 'h' hat)
    + effects: arp (semitone list, cycled per tick), vib (depth), slide (semitones over the note: portamento),
    vol (0..1), duty (pulse duty / SID pulse width).
  * channel = Channel(name, kind 'tone'|'drums', opts (chip voice keys), vol).
Channel layouts per chip are in LAYOUTS (NES 2 pulse + tri + noise, GB 4ch, SID 3 voices, AY 3 + noise/env,
SN 3 + noise, YM2612 6ch, OPL2 9ch, SNES 8ch + echo, PS1 24ch + reverb); compose() fills the musical roles
(lead, harmony, bass, arp, pad, drums) onto the first channels that carry them, unused channels stay silent.
Rendering re-uses the chip classes: each channel is one segment list rendered by the chip (its tone/noise
voices, envelopes and post effects such as SNES echo or PS1 reverb), then channels are mixed and era-crushed.
"""
from dataclasses import dataclass, field
from .._deps import need_numpy
from .. import dsp
from .chips import chip as get_chip
from .crush import era_crush, stereo
from .base import Chip

# ---------------------------------------------------------------- song model
@dataclass
class Channel:
    name: str
    kind: str = "tone"          # 'tone' | 'drums'
    opts: dict = field(default_factory=dict)
    vol: float = 1.0
    role: str = ""              # lead/harmony/bass/arp/pad/drums/echo/counter/drums2 ('' = free)
    pan: float = None           # -1..1 (None = role default)
    detune: float = 0.0         # cents
    octave: int = 0             # transpose in octaves
    hits: str = "kshc"          # drum letters this channel plays (others are rests)


@dataclass
class Song:
    chip: str
    bpm: float = 140
    speed: int = 6
    channels: list = field(default_factory=list)
    patterns: dict = field(default_factory=dict)
    order: list = field(default_factory=list)
    loop: bool = True
    title: str = ""
    style: str = ""
    rhythm: bool = False        # OPL2 rhythm mode (channels 7-9 -> BD/SD/TOM/CYM/HH)
    sid_filter: dict = None     # SID global filter: {mode, res, cutoff | from/to, voices: [routed channel names]}
    automation: dict = field(default_factory=dict)  # param -> [(row, value), ...] (rows within one order pass)

    @property
    def row_dur(self):
        return self.speed * 2.5 / self.bpm

    def rows(self):
        return sum(len(next(iter(self.patterns[p].values()), [])) for p in self.order)

    def duration(self, loops=1):
        return self.rows() * self.row_dur * loops


def midi_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ---------------------------------------------------------------- channel layouts per chip
def _L(*chs):
    return [Channel(*c) for c in chs]


LAYOUTS = {
    "nes": lambda: _L(("pulse1", "tone", {"voice": "pulse", "duty": 0.5}, 1.0, "lead"),
                      ("pulse2", "tone", {"voice": "pulse", "duty": 0.25}, 0.6, "arp"),
                      ("triangle", "tone", {"voice": "triangle"}, 1.0, "bass"),
                      ("noise", "drums", {}, 0.6, "drums", None, 0, 0, "sh"),
                      ("dpcm", "drums", {"voice": "dpcm"}, 0.8, "drums", None, 0, 0, "k")),
    "gb": lambda: _L(("square1", "tone", {"voice": "pulse", "duty": 0.5}, 1.0, "lead"),
                     ("square2", "tone", {"voice": "pulse", "duty": 0.125}, 0.6, "arp"),
                     ("wave", "tone", {"voice": "wave"}, 0.9, "bass"),
                     ("noise", "drums", {}, 0.6, "drums")),
    "sid": lambda: _L(("voice1", "tone", {"shape": "pulse", "pw": 0.4, "pwm": 0.15, "env": (.003, .1, .7, .05)}, 1.0, "lead"),
                      ("voice2", "tone", {"shape": "saw", "env": (.002, .08, .6, .03)}, 0.9, "bass"),
                      ("voice3", "drums", {"shape": "noise"}, 0.6, "drums")),
    "ay": lambda: _L(("A", "tone", {}, 1.0, "lead"), ("B", "tone", {}, 0.55, "arp"),
                     ("C", "tone", {"hw_env": "saw", "env_hz": 0}, 0.9, "bass"),
                     ("noise", "drums", {}, 0.55, "drums")),
    "sn": lambda: _L(("tone1", "tone", {}, 1.0, "lead"), ("tone2", "tone", {}, 0.55, "arp"),
                     ("tone3", "tone", {}, 0.9, "bass"), ("noise", "drums", {}, 0.55, "drums")),
    "fm": lambda: _L(("fm1", "tone", {"algorithm": 4, "feedback": 0.6}, 1.0, "lead"),
                     ("fm2", "tone", {"algorithm": 7, "ratios": (1, 2, 4, 1), "levels": (.6, .4, .3, .8)}, 0.5, "harmony"),
                     ("fm3", "tone", {"algorithm": 0, "feedback": 0.9, "ratios": (1, 1, 2, 1), "decays": (.1, .15, .1, .3)}, 0.95, "bass"),
                     ("fm4", "tone", {"algorithm": 5, "ratios": (3, 1, 2, 1)}, 0.45, "arp"),
                     ("fm5", "tone", {"algorithm": 6, "levels": (.5, .5, .6, .6), "decays": (.5, .8, .8, .8)}, 0.4, "pad"),
                     ("fm6/dac", "drums", {}, 0.6, "drums")),
    "opl": lambda: _L(*([("opl1", "tone", {"ws": 0, "mod": 2.0}, 1.0, "lead"),
                         ("opl2", "tone", {"ws": 1}, 0.5, "harmony"),
                         ("opl3", "tone", {"ws": 2, "ratios": (1, 1), "mod": 1.2}, 0.95, "bass"),
                         ("opl4", "tone", {"ws": 3}, 0.45, "arp"),
                         ("opl5", "tone", {"ws": 0, "mod": 0.6, "mdecay": 1.0}, 0.4, "pad"),
                         ("opl6", "drums", {}, 0.6, "drums")]
                        + [("opl7", "tone", {"ws": 1, "mod": 1.0}, 0.35, "echo", 0.5),
                           ("opl8", "tone", {"ws": 0, "mod": 0.8}, 0.45, "counter", -0.5),
                           ("opl9", "tone", {"ws": 0, "mod": 0.4, "mdecay": 1.0}, 0.3, "pad", 0.5, 8, 1)])),
    "snes": lambda: _L(*([("dsp1", "tone", {"table": "brass"}, 1.0, "lead"),
                          ("dsp2", "tone", {"table": "strings"}, 0.5, "harmony"),
                          ("dsp3", "tone", {"table": "bass"}, 0.95, "bass"),
                          ("dsp4", "tone", {"table": "bell"}, 0.45, "arp"),
                          ("dsp5", "tone", {"table": "pad"}, 0.4, "pad"),
                          ("dsp6", "drums", {}, 0.6, "drums")]
                         + [("dsp7", "tone", {"table": "bell"}, 0.35, "echo", 0.5),
                            ("dsp8", "tone", {"table": "organ"}, 0.45, "counter", -0.5)])),
    "ps1": lambda: _L(*([("spu1", "tone", {"table": "brass"}, 1.0, "lead"),
                         ("spu2", "tone", {"table": "strings"}, 0.5, "harmony"),
                         ("spu3", "tone", {"table": "bass"}, 0.95, "bass"),
                         ("spu4", "tone", {"table": "bell"}, 0.45, "arp"),
                         ("spu5", "tone", {"table": "pad"}, 0.45, "pad"),
                         ("spu6", "drums", {}, 0.6, "drums")]
                        + _ps1_extra())),
}


def _ps1_extra():
    """PS1 channels 7-24: layered detuned pads, string harmony section, lead doubles, echoes, counter."""
    ex = [("spu7", "tone", {"table": "brass"}, 0.35, "echo", 0.6),
          ("spu8", "tone", {"table": "bell"}, 0.25, "echo", -0.6, 0, 1),
          ("spu9", "tone", {"table": "strings"}, 0.45, "counter", -0.4),
          ("spu10", "tone", {"table": "organ"}, 0.3, "counter", 0.4, 6, -1),
          ("spu11", "tone", {"table": "brass"}, 0.4, "lead", -0.25, 7),
          ("spu12", "tone", {"table": "brass"}, 0.4, "lead", 0.25, -7),
          ("spu13", "tone", {"table": "strings"}, 0.3, "lead", 0.0, 0, -1),
          ("spu14", "tone", {"table": "bass"}, 0.5, "bass", 0.0, 0, 1),
          ("spu15", "tone", {"table": "strings"}, 0.35, "harmony", 0.5, 9),
          ("spu16", "tone", {"table": "strings"}, 0.35, "harmony", -0.5, -9),
          ("spu17", "tone", {"table": "bell"}, 0.3, "arp", -0.5, 0, 1)]
    for k, (cents, pan) in enumerate(((12, -0.9), (-12, 0.9), (5, -0.6), (-5, 0.6), (18, -0.3), (-18, 0.3), (0, 0.0))):
        ex.append((f"spu{18 + k}", "tone", {"table": "pad"}, 0.22, "pad", pan, cents, k % 2))
    return ex


def opl_rhythm_layout():
    """OPL2 with rhythm mode on: 6 melodic channels + the 5 rhythm instruments carved out of channels 7-9."""
    chans = LAYOUTS["opl"]()[:6]
    chans[5] = Channel("opl6", "tone", {"ws": 1, "mod": 1.0}, 0.35, "echo", 0.5)
    return chans + _L(("bd", "drums", {}, 0.8, "drums", 0.0, 0, 0, "k"),
                      ("sd", "drums", {}, 0.6, "drums", 0.1, 0, 0, "s"),
                      ("hh", "drums", {}, 0.4, "drums", 0.3, 0, 0, "h"),
                      ("tom", "drums", {}, 0.6, "drums", -0.2, 0, 0, "t"),
                      ("cym", "drums", {}, 0.35, "drums", -0.3, 0, 0, "c"))


def layout(chip_name, rhythm=False):
    if rhythm:
        if chip_name != "opl":
            raise ValueError("rhythm mode exists only on the OPL2 ('opl')")
        return opl_rhythm_layout()
    try:
        return LAYOUTS[chip_name]()
    except KeyError:
        raise KeyError(f"no channel layout for chip {chip_name!r}; choose from {sorted(LAYOUTS)}") from None


# ---------------------------------------------------------------- rendering
DRUMS = {  # drum hit -> segment (rendered by the chip's noise/tone voices)
    "k": {"wave": "tone", "f0": 160, "f1": 45, "decay": 0.05, "vol": 1.0},
    "s": {"wave": "noise", "f0": 2500, "f1": 1200, "decay": 0.06, "vol": 0.8},
    "h": {"wave": "noise", "f0": 9000, "decay": 0.015, "vol": 0.45},
}


DRUM_ALIASES = {"t": "k", "c": "h"}  # tom/cymbal fall back to kick/hat on kits without them

OPL_RHYTHM_KIT = {  # true OPL2 rhythm mode instruments (see fm.opl_rhythm)
    "k": {"wave": "tone", "rhythm": "bd", "f0": 110, "f1": 50, "decay": 0.12, "vol": 1.0},
    "s": {"wave": "tone", "rhythm": "sd", "f0": 360, "decay": 0.08, "vol": 0.8},
    "h": {"wave": "tone", "rhythm": "hh", "f0": 360, "decay": 0.03, "vol": 0.45},
    "t": {"wave": "tone", "rhythm": "tom", "f0": 270, "decay": 0.15, "vol": 0.8},
    "c": {"wave": "tone", "rhythm": "cym", "f0": 270, "decay": 0.25, "vol": 0.4},
}


def drum_segment(song, hit):
    kit = OPL_RHYTHM_KIT if (song.rhythm and song.chip == "opl") else DRUM_KITS.get(song.chip, DRUMS)
    return kit.get(hit) or kit[DRUM_ALIASES[hit]]


def _kit(**hits):
    return {**DRUMS, **hits}


DRUM_KITS = {  # chip-accurate-ish drum synthesis through each chip's own voices
    "nes": _kit(k={"wave": "tone", "voice": "dpcm", "f0": 110, "f1": 40, "decay": 0.08, "vol": 1.0},
                s={"wave": "noise", "f0": 2000, "f1": 600, "decay": 0.08, "vol": 0.8},
                h={"wave": "noise", "f0": 12000, "short": True, "decay": 0.02, "vol": 0.4}),
    "gb": _kit(k={"wave": "noise", "f0": 300, "f1": 60, "decay": 0.07, "vol": 1.0},
               s={"wave": "noise", "f0": 3000, "f1": 1500, "decay": 0.07, "vol": 0.8},
               h={"wave": "noise", "f0": 12000, "short": True, "decay": 0.02, "vol": 0.4}),
    "sid": _kit(k={"wave": "tone", "shape": "pulse", "pw": 0.5, "pwm": 0, "f0": 180, "f1": 40, "decay": 0.06, "vol": 1.0},
                s={"wave": "noise", "f0": 2500, "decay": 0.07, "vol": 0.8},
                h={"wave": "noise", "f0": 12000, "decay": 0.015, "vol": 0.4}),
    "ay": _kit(k={"wave": "tone", "hw_env": "decay", "env_hz": 12, "f0": 130, "f1": 50, "decay": 0.09, "vol": 1.0},
               s={"wave": "noise", "f0": 3000, "decay": 0.08, "vol": 0.8},
               h={"wave": "noise", "f0": 20000, "decay": 0.02, "vol": 0.4}),
    "sn": _kit(k={"wave": "noise", "periodic": True, "f0": 110, "f1": 50, "decay": 0.08, "vol": 1.0},
               s={"wave": "noise", "f0": 2000, "decay": 0.07, "vol": 0.8},
               h={"wave": "noise", "f0": 8000, "decay": 0.02, "vol": 0.4}),
    "fm": _kit(k={"wave": "tone", "algorithm": 0, "feedback": 0.0, "ratios": (1, 1, 1, 1), "levels": (.6, .4, .3, 1),
                  "decays": (.02, .03, .04, .12), "f0": 150, "f1": 40, "decay": 0.12, "vol": 1.0},
               s={"wave": "noise", "f0": 400, "decay": 0.08, "vol": 0.8},
               h={"wave": "tone", "algorithm": 7, "ratios": (7.13, 9.31, 11.7, 13.9), "levels": (1, 1, 1, 1),
                  "decays": (.02, .02, .02, .02), "f0": 700, "decay": 0.02, "vol": 0.3}),
    "opl": _kit(k={"wave": "tone", "ws": 0, "mod": 0.5, "ratios": (1, 1), "f0": 120, "f1": 45, "decay": 0.1, "vol": 1.0},
                s={"wave": "noise", "f0": 400, "decay": 0.07, "vol": 0.8},
                h={"wave": "tone", "ws": 3, "mod": 6.0, "ratios": (7.3, 1), "f0": 3000, "decay": 0.02, "vol": 0.3}),
    "snes": _kit(k={"wave": "tone", "table": "bass", "f0": 110, "f1": 38, "decay": 0.09, "vol": 1.0},
                 s={"wave": "noise", "decay": 0.09, "vol": 0.8},
                 h={"wave": "noise", "decay": 0.02, "vol": 0.35}),
    "ps1": _kit(k={"wave": "tone", "table": "bass", "f0": 100, "f1": 35, "decay": 0.1, "vol": 1.0},
                s={"wave": "noise", "decay": 0.1, "vol": 0.8},
                h={"wave": "noise", "decay": 0.025, "vol": 0.35}),
}


def _duty(chip_name, d):
    """NES/GB take a duty index 0..3; others take a fraction."""
    if chip_name in ("nes", "gb") and isinstance(d, float):
        return min(range(4), key=lambda i: abs((0.125, 0.25, 0.5, 0.75)[i] - d))
    return d


def _channel_segments(song, ch, loops):
    """Walk order list rows for one channel -> chip segment list."""
    rd = song.row_dur
    tick_hz = 1.0 / (rd / max(1, song.speed))
    segs, cur = [], None
    rest = {"wave": "rest", "f0": 0, "dur": 0.0}

    def close():
        if cur is not None:
            segs.append(cur)

    for _ in range(loops):
        for pname in song.order:
            for cell in song.patterns[pname].get(ch.name, []):
                if cell is not None and set(cell) == {"auto"}:
                    cell = None  # automation-only row = hold
                if cell is None:  # hold
                    if cur is None:
                        cur = dict(rest)
                    cur["dur"] += rd
                    continue
                close()
                if cell.get("off"):
                    cur = dict(rest, dur=rd)
                elif "drum" in cell and cell["drum"] not in ch.hits:
                    cur = dict(rest, dur=rd)
                elif "drum" in cell:
                    d = drum_segment(song, cell["drum"])
                    cur = {**ch.opts, **d, "dur": rd, "vol": d["vol"] * cell.get("vol", 1.0)}
                    if ch.name == "voice3" and d["wave"] == "tone":
                        cur["shape"] = "triangle"
                else:
                    f = midi_freq(cell["n"] + 12 * ch.octave) * 2 ** (ch.detune / 1200)
                    cur = {**ch.opts, "wave": "tone", "f0": f, "dur": rd, "vol": cell.get("vol", 1.0)}
                    if "env" not in cur and "decay" not in cur:
                        cur["env"] = (0.004, 0.08, 0.65, 0.03)
                    if cell.get("arp"):
                        cur["arp"], cur["arp_hz"] = list(cell["arp"]), tick_hz
                    if cell.get("vib"):
                        cur["vib"], cur["vib_hz"] = cell["vib"], 6.0
                    if cell.get("slide"):
                        cur["f1"], cur["curve"] = f * 2 ** (cell["slide"] / 12), "exp"
                    if "duty" in cell:
                        cur["duty"], cur["pw"] = _duty(song.chip, cell["duty"]), cell["duty"]
                    if "duty" in cur:
                        cur["duty"] = _duty(song.chip, cur["duty"])
        close()
        cur = None
    # merge consecutive rests
    out = []
    for s in segs:
        if out and s["wave"] == "rest" and out[-1]["wave"] == "rest":
            out[-1]["dur"] += s["dur"]
        else:
            out.append(s)
    return out


def _sid_bus(song, c, rate, seed, loops, total):
    """Real SID routing: voices with their filter-enable bit set are summed into ONE multimode filter;
    the others bypass it. Returns (filtered_bus or None, set of routed channel names)."""
    np = need_numpy()
    f = song.sid_filter
    routed = [ch for ch in song.channels if ch.name in set(f.get("voices", ()))]
    vs = []
    for i, ch in enumerate(song.channels):
        if ch in routed and ch.vol > 0:
            segs = [{k: v for k, v in sg.items() if k != "filter"} for sg in _channel_segments(song, ch, loops)]
            if any(sg["wave"] != "rest" for sg in segs):
                vs.append(Chip.render(c, segs, rate, seed + i) * ch.vol)
    if not vs:
        return None, {ch.name for ch in routed}
    x = dsp.mix(*vs)
    n = len(x)
    cut = cutoff_curve(song, f, n, rate, loops)
    from .sid import svf
    ares = song_automation(song).get("res")
    res = auto_curve(song, ares, n, rate, loops) if ares else f.get("res", 0.6)
    y = svf(x, cut, res, f.get("mode", "lp"), rate)
    return dsp.normalize(y, float(np.abs(x).max())), {ch.name for ch in routed}  # keep pre-filter level


AUTO_PARAMS = {"cutoff": (20.0, 20000.0), "res": (0.0, 1.0), "echo_fb": (0.0, 0.9), "echo_mix": (0.0, 1.0)}


def song_automation(song):
    """Merge Song.automation with per-cell automation effects (f/q/e/m) -> {param: sorted [(row, value)]}.
    Rows are absolute within one pass of the order list (pattern rows concatenated in order)."""
    pts = {k: list(v) for k, v in (song.automation or {}).items() if k != "echo_delay"}
    for k in pts:
        if k not in AUTO_PARAMS:
            raise ValueError(f"unknown automation parameter {k!r}; use {sorted(AUTO_PARAMS)}")
    base = 0
    for pname in song.order:
        pat = song.patterns[pname]
        for ch in song.channels:
            for r, cell in enumerate(pat.get(ch.name, [])):
                for k, v in ((cell or {}).get("auto") or {}).items():
                    pts.setdefault(k, []).append((base + r, v))
        base += len(next(iter(pat.values()), []))
    out = {}
    for k, v in pts.items():
        lo, hi = AUTO_PARAMS[k]
        out[k] = sorted({float(r): min(hi, max(lo, float(x))) for r, x in v}.items())
    return out


def auto_curve(song, points, n, rate, loops=1, log=False):
    """Per-sample curve from automation points (linear between rows, held at ends; repeats each loop pass)."""
    np = need_numpy()
    rows = max(1, song.rows())
    t = np.arange(n) / rate / song.row_dur
    t = np.where(t >= rows * loops, rows - 1e-9, t % rows)
    r, v = np.array([p[0] for p in points]), np.array([p[1] for p in points])
    if log:
        return np.exp(np.interp(t, r, np.log(np.maximum(v, 1e-6))))
    return np.interp(t, r, v)


def automated_echo(x, rate, fb, mix, delay=0.12, tail=1.5):
    """Feedback delay with per-sample feedback/mix curves (block-vectorised by delay length). Adds a tail."""
    np = need_numpy()
    d = max(1, int(delay * rate))
    n = len(x) + int(tail * rate)
    pad = lambda c: np.concatenate([c, np.full(n - len(c), c[-1] if len(c) else 0.0)])
    xs, fb, mix = np.concatenate([x, np.zeros(n - len(x))]), pad(np.asarray(fb, float)), pad(np.asarray(mix, float))
    wet = np.zeros(n)  # wet[i] = delayed (x + feedback) line
    line = xs.copy()
    for s in range(d, n, d):
        e = min(n, s + d)
        wet[s:e] = line[s - d:e - d]
        line[s:e] = xs[s:e] + fb[s:e] * wet[s:e]
    return xs + mix * wet


def cutoff_curve(song, f, n, rate, loops=1):
    """Cutoff per sample: automation 'cutoff' if present, else from/to exponential sweep, or fixed 'cutoff'."""
    np = need_numpy()
    auto = song_automation(song).get("cutoff")
    if auto:
        return auto_curve(song, auto, n, rate, loops, log=True)
    c0 = float(f.get("from", f.get("cutoff", 2000)))
    c1 = float(f.get("to", c0))
    return c0 * (c1 / c0) ** np.linspace(0, 1, n)


def _apply_automation(song, x, auto, rate, loops):
    """Song-level automation: global cutoff/res filter (non-SID chips; SID automates its own filter) and
    automated feedback echo (echo_fb / echo_mix)."""
    if not auto:
        return x
    np = need_numpy()
    from .sid import svf
    if ("cutoff" in auto or "res" in auto) and not (song.chip == "sid" and song.sid_filter):
        n = len(x)
        cut = auto_curve(song, auto["cutoff"], n, rate, loops, log=True) if "cutoff" in auto else 20000.0
        res = auto_curve(song, auto["res"], n, rate, loops) if "res" in auto else 0.0
        peak = float(np.abs(x).max()) if n else 0.0
        x = dsp.normalize(svf(x, cut, res, "lp", rate), peak)
    if "echo_fb" in auto or "echo_mix" in auto:
        n = len(x)
        fb = auto_curve(song, auto["echo_fb"], n, rate, loops) if "echo_fb" in auto else np.full(n, 0.4)
        mix = auto_curve(song, auto["echo_mix"], n, rate, loops) if "echo_mix" in auto else np.full(n, 0.35)
        x = automated_echo(x, rate, fb, mix, delay=float((song.automation or {}).get("echo_delay", 0.12)))
    return x


def fold_tail(x, n):
    """Seamless loop: add everything past sample n (echo/reverb/release tail) back onto the start, repeatedly if
    the tail is longer than n, and trim to n samples. Playing the result end-to-end continues the tail across the
    loop point instead of cutting it. Works on mono (n,) and stereo (n,2)."""
    np = need_numpy()
    if n <= 0 or len(x) <= n:
        out = np.zeros((n,) + x.shape[1:])
        out[:len(x)] = x[:n]
        return out
    out = np.array(x[:n], dtype=float)
    for k in range(n, len(x), n):
        part = x[k:k + n]
        out[:len(part)] += part
    return out


def render_song(song, rate=dsp.RATE, seed=0, loops=1, crush=True, stereo_out=False, seamless=False):
    """Render a Song to mono float array (or (n,2) if stereo_out). Deterministic, peak <= 0.89.
    seamless=True: exact song length with the echo/reverb tail folded onto the start (see fold_tail) so the clip
    loops without a gap or a cut tail; default keeps the tail appended after the song."""
    np = need_numpy()
    c = get_chip(song.chip)
    total = int(round(song.duration(loops) * rate))
    auto = song_automation(song)
    echo_auto = "echo_fb" in auto or "echo_mix" in auto
    if echo_auto and song.chip == "snes":  # automated echo replaces the fixed per-channel S-DSP echo
        c = type(c)()
        c.post = lambda x, rate, seed: x
    tracks, pans = [], []
    routed = set()
    if song.chip == "sid" and song.sid_filter:
        bus, routed = _sid_bus(song, c, rate, seed, loops, total)
        if bus is not None:
            tracks.append(bus)
            pans.append(0.0)
    for i, ch in enumerate(song.channels):
        if ch.vol <= 0 or ch.name in routed:
            continue
        segs = _channel_segments(song, ch, loops)
        if not any(s["wave"] != "rest" for s in segs):
            continue
        x = c.render(segs, rate, seed + i)  # chip voices + post fx (echo/reverb) per channel
        tracks.append(x * ch.vol)
        pans.append(ch.pan if ch.pan is not None else
                    {"harmony": -0.4, "arp": 0.4, "pad": -0.2, "echo": 0.5, "counter": -0.5}.get(ch.role, 0.0))
    if not tracks:
        return np.zeros((total, 2) if stereo_out else total)
    if stereo_out:
        n = max(len(t) for t in tracks)
        st = np.zeros((n, 2))
        for t, p in zip(tracks, pans):
            s = stereo(t, pan=p, width=0.3 if c.era == "32bit" else 0.0, rate=rate)
            st[:len(s)] += s
        if auto:
            chans = [_apply_automation(song, st[:, k], auto, rate, loops) for k in (0, 1)]
            st = np.stack([chans[0], chans[1]], axis=1)
        if seamless:
            st = fold_tail(st, total)
        return dsp.normalize(st, 0.89)
    x = dsp.mix(*tracks)
    x = _apply_automation(song, x, auto, rate, loops)
    if seamless:
        x = fold_tail(x, total)
    if crush:
        x = era_crush(dsp.normalize(x, 0.89), c.era, rate)
    return dsp.normalize(x, 0.89)


# ---------------------------------------------------------------- procedural composition
MODES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10],
         "phrygian": [0, 1, 3, 5, 7, 8, 10], "harmonic_minor": [0, 2, 3, 5, 7, 8, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10]}

SID_FILTER = {  # bass filter sweep per style
    "title": {"from": 300, "to": 3500, "res": 0.6, "mode": "lp"},
    "battle": {"from": 5000, "to": 500, "res": 0.85, "mode": "lp"},
    "victory": {"from": 800, "to": 5000, "res": 0.5, "mode": "lp"},
    "chess_thinking": {"from": 250, "to": 900, "res": 0.8, "mode": "lp"},
    "game_over": {"from": 2500, "to": 150, "res": 0.7, "mode": "lp"},
}

STYLES = {
    #               mode            bpm  speed progressions (scale degrees, 0-based)        drums (16 steps)                          density
    "title":         dict(mode="major", bpm=150, speed=6, progs=[[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 4, 4]],
                          drums=("k...h...s...h.h.", "k..kh...s...h..."), density=0.6, bass="octave", arp=True),
    "battle":        dict(mode="harmonic_minor", bpm=180, speed=5, progs=[[0, 5, 6, 4], [0, 0, 5, 4], [0, 3, 5, 4]],
                          drums=("k.h.s.h.k.k.s.h.", "k.hkh.s.k.h.s.hh"), density=0.8, bass="eighths", arp=True),
    "victory":       dict(mode="major", bpm=160, speed=6, progs=[[0, 3, 4, 0], [0, 4, 3, 4]],
                          drums=("k...s...k.k.s...",), density=0.7, bass="root", arp=True),
    "chess_thinking": dict(mode="dorian", bpm=96, speed=6, progs=[[0, 3, 0, 4], [0, 6, 3, 0]],
                          drums=("....h.......h...", "h.......h......."), density=0.35, bass="root", arp=False),
    "game_over":     dict(mode="minor", bpm=72, speed=6, progs=[[0, 5, 3, 4], [0, 6, 5, 4]],
                          drums=None, density=0.4, bass="root", arp=False),
}


def _chord(mode, root, degree):
    sc = MODES[mode]
    return [root + sc[(degree + k) % 7] + 12 * ((degree + k) // 7) for k in (0, 2, 4)]


def compose(chip_name, style="title", seed=0, bars=4, root=None, automation=None, rhythm=False):
    """Deterministic procedural Song for chip/style/seed. bars = bars of 16 rows (one chord per bar).
    automation: {param: [(row, value), ...]} for cutoff (Hz), res (0..1), echo_fb (0..0.9), echo_mix (0..1).
    rhythm=True (OPL only): OPL2 rhythm mode, drums on BD/SD/HH/TOM/CYM from channels 7-9."""
    np = need_numpy()
    if style not in STYLES:
        raise KeyError(f"unknown style {style!r}; choose from {sorted(STYLES)}")
    st = STYLES[style]
    r = np.random.default_rng([seed, sum(map(ord, chip_name)), sum(map(ord, style))])
    root = root if root is not None else int(57 + r.integers(0, 7))  # A3..D#4
    mode, sc = st["mode"], MODES[st["mode"]]
    prog = st["progs"][int(r.integers(len(st["progs"])))]
    chords = [prog[b % len(prog)] for b in range(bars)]
    chans = layout(chip_name, rhythm=rhythm)
    roles = {}
    for c in chans:
        if c.role:
            roles.setdefault(c.role, []).append(c)
    scale_notes = [root + 12 * o + s for o in (0, 1, 2) for s in sc]
    drum_pats = st["drums"]

    def bar_parts(b, deg, variant):
        ch = _chord(mode, root, deg)
        p = {}
        # lead melody
        mel, last = [None] * 16, int(r.integers(7, 12))
        for step in range(16):
            strong = step % 4 == 0
            if step == 0 or (r.random() < st["density"] * (1.0 if strong else 0.5)):
                if strong:
                    tgt = [i for i, n in enumerate(scale_notes) if (n - ch[0]) % 12 in [(c - ch[0]) % 12 for c in ch]]
                    last = min(tgt, key=lambda i: abs(i - last) + r.random())
                else:
                    last = int(np.clip(last + r.choice([-2, -1, 1, 2]), 0, len(scale_notes) - 1))
                cell = {"n": scale_notes[last] + 12}
                if style == "victory" and step == 0 and b == bars - 1:
                    cell["arp"] = [0, 4, 7]
                if r.random() < 0.2:
                    cell["vib"] = 0.01
                if style == "battle" and r.random() < 0.08:
                    cell["slide"] = int(r.choice([-12, 12]))
                mel[step] = cell
            elif step % 8 == 7 and r.random() < 0.3:
                mel[step] = {"off": True}
        p["lead"] = mel
        # bass
        bass = [None] * 16
        b0 = ch[0] - 24 if ch[0] - 24 >= 33 else ch[0] - 12
        for step in range(16):
            if st["bass"] == "eighths" and step % 2 == 0:
                bass[step] = {"n": b0 + (12 if step % 4 == 2 else 0)}
            elif st["bass"] == "octave" and step % 4 == 0:
                bass[step] = {"n": b0 + (12 if step % 8 == 4 else 0)}
            elif st["bass"] == "root" and step in (0, 8):
                bass[step] = {"n": b0 if step == 0 else b0 + sc[4]}
        p["bass"] = bass
        # arpeggio: tracker-style arp effect on held chord root (cycled each tick)
        if st["arp"]:
            iv = [c - ch[0] for c in ch]
            p["arp"] = [{"n": ch[0] + 12, "arp": iv, "vol": 0.8, "duty": 0.125 if variant else 0.25}
                        if s % 4 == 0 else None for s in range(16)]
        else:
            p["arp"] = [{"n": ch[(s // 4) % 3] + 12, "vol": 0.6} if s % 4 == 0 else None for s in range(16)]
        p["echo"] = [{"off": True}] * 3 + [dict(c, vol=0.7) if c and "n" in c else c for c in mel[:13]]
        cnt, prev = [None] * 16, ch[2] + 12
        for step in (0, 8) if st["density"] < 0.6 else (0, 4, 8, 12):  # countermelody: contrary motion on chord tones
            lead_up = mel[step] and "n" in mel[step] and mel[step]["n"] > prev
            opts = sorted({c + 12 for c in ch} | {c for c in ch})
            below = [n for n in opts if n < prev] or opts[:1]
            above = [n for n in opts if n > prev] or opts[-1:]
            prev = below[-1] if lead_up else above[0]
            cnt[step] = {"n": prev, "vol": 0.8}
        p["counter"] = cnt
        p["harmony"] = [{"n": ch[1], "vib": 0.006}] + [None] * 15
        p["pad"] = [{"n": ch[2] - 12, "vol": 0.7}] + [None] * 15
        if drum_pats:
            pat = drum_pats[(b + variant) % len(drum_pats)]
            if b == bars - 1 and style in ("title", "battle"):
                pat = pat[:12] + ("sstt" if rhythm else "ssss")  # fill (toms in OPL rhythm mode)
            if rhythm and b % 2 == 0:
                pat = "c" + pat[1:] if pat[0] == "." else pat
            if rhythm and b == 0:
                pat = pat[:8] + "c" + pat[9:] if pat[8] == "." else pat
            p["drums"] = [None if c == "." else {"drum": c} for c in pat]
        else:
            p["drums"] = [None] * 16
        return p

    patterns, order = {}, []
    half = max(1, bars // 2)
    for pi, (start, end) in enumerate(((0, half), (half, bars)) if bars > 1 else ((0, 1),)):
        if start >= end:
            continue
        name = "AB"[pi]
        rows = {c.name: [] for c in chans}
        for b in range(start, end):
            parts = bar_parts(b, chords[b], pi)
            for role, cells in parts.items():
                for c in roles.get(role, []):
                    rows[c.name] += cells
        for c in chans:  # unused channels / roles: pad with holds
            n = 16 * (end - start)
            rows[c.name] = (rows[c.name] + [None] * n)[:n]
        patterns[name] = rows
        order.append(name)
    if chip_name == "sid" and style == "battle":  # SID flavour: ring-modulated lead, hard-synced bass
        roles["lead"][0].opts.update(shape="triangle", ring=1.5)
        roles["bass"][0].opts.update(sync=1.98)
    sid_filter = None
    if chip_name == "sid":  # ONE global SID filter; bass (and lead for chess_thinking) have their filter bit set
        voices = [roles["bass"][0].name] + ([roles["lead"][0].name] if style in ("chess_thinking", "battle") else [])
        sid_filter = dict(SID_FILTER[style], voices=voices)
    return Song(chip=chip_name, bpm=st["bpm"], speed=st["speed"], channels=chans, patterns=patterns,
                order=order, loop=style not in ("game_over", "victory"), title=f"{style} #{seed}", style=style,
                sid_filter=sid_filter, rhythm=bool(rhythm), automation=dict(automation or {}))


def render_music(chip_name, style="title", seed=0, bars=2, rate=dsp.RATE, loops=1, loop=False, seamless=False):
    """loops=N repeats the order list N times; loop=True is shorthand for loops=2.
    seamless=True returns an exactly loop-length clip with the tail crossfaded into the start."""
    loops = max(1, int(loops)) if not (loop and loops == 1) else 2
    return render_song(compose(chip_name, style, seed, bars), rate=rate, seed=seed, loops=loops, seamless=seamless)


# ---------------------------------------------------------------- compact text format
_NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def parse_note(tok):
    """'C4' 'C#4' 'Db3' -> MIDI."""
    n = _NOTE[tok[0].upper()]
    i = 1
    while i < len(tok) and tok[i] in "#b":
        n += 1 if tok[i] == "#" else -1
        i += 1
    return n + 12 * (int(tok[i:]) + 1)


def _bad(tok):
    raise ValueError(f"only automation effects (f/q/e/m) are allowed on a hold row: {tok!r}")


def parse_cell(tok):
    """'.'=hold, '-' or '---'=off, 'k'/'s'/'h'/'t'/'c'=drum (kick/snare/hat/tom/cymbal; t/c fall back to k/h off OPL rhythm mode), 'C4' note, effects after ':' e.g. C4:a047 v u12 d5 @7 w1.
    a=arpeggio (hex semitone digits), v=vibrato, u/d=slide up/down N semitones, @=volume 0-9, w=duty 0-3.
    Automation (song-wide, set at this row, linear to the next point): f<Hz> cutoff, q<0-9> resonance,
    e<0-9> echo feedback (tenths, max 0.9), m<0-9> echo mix. A bare '.:f800' sets automation on a hold row."""
    if tok in (".", "..", "..."):
        return None
    if tok.startswith(".:"):
        c = parse_cell("C4" + tok[1:])
        return {"auto": c["auto"]} if set(c) == {"n", "auto"} else _bad(tok)
    if set(tok) == {"-"}:
        return {"off": True}
    head, *fx = tok.split(":")
    if head in DRUMS or head in DRUM_ALIASES:
        cell = {"drum": head}
    else:
        cell = {"n": parse_note(head)}
    for f in fx:
        if not f:
            continue
        k, v = f[0], f[1:]
        if k == "a":
            cell["arp"] = [int(ch, 16) for ch in v]
        elif k == "v":
            cell["vib"] = 0.01 * (int(v) if v else 1)
        elif k in "ud":
            cell["slide"] = int(v or 12) * (1 if k == "u" else -1)
        elif k == "@":
            cell["vol"] = int(v) / 9
        elif k == "w":
            cell["duty"] = (0.125, 0.25, 0.5, 0.75)[int(v)]
        elif k in "fqem":  # automation points at this row
            try:
                x = float(v)
            except ValueError:
                raise ValueError(f"bad automation value {f!r} in {tok!r}") from None
            name, val = {"f": ("cutoff", x), "q": ("res", x / 9), "e": ("echo_fb", x / 10), "m": ("echo_mix", x / 9)}[k]
            cell.setdefault("auto", {})[name] = val
        else:
            raise ValueError(f"unknown effect {f!r} in {tok!r}")
    return cell


# ---------------------------------------------------------------- per-channel instruments ('inst' lines)
_TABLES = ("strings", "brass", "organ", "bell", "bass", "pad")
INST_KEYS = {  # chip -> {key: allowed (tuple of strings) | "num" | "nums" (comma list)}
    "nes": {"voice": ("pulse", "triangle", "noise", "dpcm"), "duty": "num"},
    "gb": {"voice": ("pulse", "wave", "noise"), "duty": "num"},
    "sid": {"shape": ("saw", "pulse", "triangle", "noise"), "pw": "num", "pwm": "num", "ring": "num", "sync": "num",
            "combined": "num"},
    "ay": {"hw_env": "num", "env_hz": "num"},
    "sn": {"periodic": "num"},
    "fm": {"algorithm": "num", "feedback": "num", "ratios": "nums", "levels": "nums", "decays": "nums"},
    "opl": {"ws": "num", "mod": "num", "mdecay": "num", "ratios": "nums"},
    "snes": {"table": _TABLES},
    "ps1": {"table": _TABLES},
}
INST_COMMON = {"vol": "num", "pan": "num", "detune": "num", "octave": "num", "hits": "hits", "decay": "num",
               "env": "num", "vib": "num", "vib_hz": "num"}
_CHANNEL_ATTRS = ("vol", "pan", "detune", "octave", "hits")


def _inst_value(chip, key, raw):
    spec = INST_KEYS.get(chip, {}).get(key, INST_COMMON.get(key))
    if spec is None:
        allowed = sorted(set(INST_KEYS.get(chip, {})) | set(INST_COMMON))
        raise ValueError(f"unknown instrument key {key!r} for chip {chip}; use {allowed}")
    try:
        if spec == "num":
            return float(raw)
        if spec == "nums":
            return tuple(float(v) for v in raw.split(","))
    except ValueError:
        raise ValueError(f"instrument key {key!r} needs a number{' list' if spec == 'nums' else ''}, got {raw!r}") \
            from None
    if spec == "hits":
        if not raw or set(raw) - set("kshtc"):
            raise ValueError(f"hits must be drum letters from 'kshtc', got {raw!r}")
        return raw
    if raw not in spec:
        raise ValueError(f"instrument key {key!r} must be one of {list(spec)}, got {raw!r}")
    return raw


def apply_inst(song, args):
    """'inst <channel> [tone|drums] key=val ...': set the channel's kind and chip voice options (validated per chip),
    or its vol/pan/detune/octave/hits. Comma lists become tuples. Errors raise ValueError."""
    if not args:
        raise ValueError("inst needs a channel: inst <channel> [tone|drums] key=val ...")
    ch = next((c for c in song.channels if c.name == args[0]), None)
    if ch is None:
        raise ValueError(f"unknown channel {args[0]!r} for chip {song.chip}; use {[c.name for c in song.channels]}")
    for tok in args[1:]:
        if "=" not in tok:
            if tok not in ("tone", "drums"):
                raise ValueError(f"inst kind must be 'tone' or 'drums', got {tok!r}")
            ch.kind = tok
            continue
        key, raw = tok.split("=", 1)
        val = _inst_value(song.chip, key, raw)
        if key in _CHANNEL_ATTRS:
            setattr(ch, key, int(val) if key == "octave" else val)
        else:
            ch.opts[key] = val
    return ch


def parse_song(text):
    """Compact text song:

        chip nes
        bpm 150
        speed 6
        pattern A
        pulse1   C5 . E5 . G5:v . --- .
        triangle C3 . . . G2 . . .
        noise    k . h . s . h .
        pattern B
        ...
        order A B A
        loop yes

        inst pulse1 duty=0.125 vol=0.8   # per-channel instrument (see INST_KEYS / INST_COMMON)

    Channel names come from the chip layout (see LAYOUTS); omitted channels stay silent. '#' starts a comment.
    """
    song, pat = None, None
    meta = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, *rest = line.split()
        if key in ("chip", "bpm", "speed", "loop", "title", "order"):
            meta[key] = rest
            if key == "chip":
                song = Song(chip=rest[0], channels=layout(rest[0]))
            continue
        if song is None:
            raise ValueError("song text must start with 'chip <name>'")
        if key == "rhythm":
            if song.patterns:
                raise ValueError("'rhythm' must come before any pattern")
            on = (rest or ["on"])[0].lower() in ("on", "yes", "1", "true")
            song.rhythm, song.channels = on, layout(song.chip, rhythm=on)
            continue
        if key == "inst":
            apply_inst(song, rest)
            continue
        if key == "pattern":
            pat = song.patterns.setdefault(rest[0], {})
            continue
        if pat is None:
            raise ValueError(f"row data before any 'pattern': {line!r}")
        names = {c.name for c in song.channels}
        if key not in names:
            raise ValueError(f"unknown channel {key!r} for chip {song.chip}; use {sorted(names)}")
        pat[key] = [parse_cell(t) for t in rest]
    if song is None:
        raise ValueError("empty song")
    song.bpm = float(meta.get("bpm", [song.bpm])[0])
    song.speed = int(meta.get("speed", [song.speed])[0])
    song.loop = meta.get("loop", ["yes"])[0].lower() in ("yes", "1", "true", "on")
    song.title = " ".join(meta.get("title", []))
    song.order = meta.get("order") or list(song.patterns)
    for p in song.patterns.values():  # equalise rows in a pattern
        n = max((len(v) for v in p.values()), default=0)
        for c in song.channels:
            p[c.name] = (p.get(c.name, []) + [None] * n)[:n]
    return song


DEMO = """
chip nes
title chessx demo
bpm 150
speed 6
pattern A
pulse1   E5 . . G5 . . C6:v . B5 . G5 . E5:u2 . --- .
pulse2   C5:a047 . . . A4:a037 . . . F4:a049 . . . G4:a047 . . .
triangle C3 . C4 . A2 . A3 . F2 . F3 . G2 . G3 .
noise    . . h . s . h . . . h . s . h h
dpcm     k . . . . . . . k k . . . . . .
order A A
loop yes
"""
