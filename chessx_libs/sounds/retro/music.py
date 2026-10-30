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

# ---------------------------------------------------------------- song model
@dataclass
class Channel:
    name: str
    kind: str = "tone"          # 'tone' | 'drums'
    opts: dict = field(default_factory=dict)
    vol: float = 1.0
    role: str = ""              # lead/harmony/bass/arp/pad/drums ('' = free)


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
                      ("noise", "drums", {}, 0.6, "drums"),
                      ("dpcm", "drums", {"voice": "dpcm"}, 0.0, "")),
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
                        + [(f"opl{i}", "tone", {}, 0.0, "") for i in (7, 8, 9)])),
    "snes": lambda: _L(*([("dsp1", "tone", {"table": "brass"}, 1.0, "lead"),
                          ("dsp2", "tone", {"table": "strings"}, 0.5, "harmony"),
                          ("dsp3", "tone", {"table": "bass"}, 0.95, "bass"),
                          ("dsp4", "tone", {"table": "bell"}, 0.45, "arp"),
                          ("dsp5", "tone", {"table": "pad"}, 0.4, "pad"),
                          ("dsp6", "drums", {}, 0.6, "drums")]
                         + [(f"dsp{i}", "tone", {}, 0.0, "") for i in (7, 8)])),
    "ps1": lambda: _L(*([("spu1", "tone", {"table": "brass"}, 1.0, "lead"),
                         ("spu2", "tone", {"table": "strings"}, 0.5, "harmony"),
                         ("spu3", "tone", {"table": "bass"}, 0.95, "bass"),
                         ("spu4", "tone", {"table": "bell"}, 0.45, "arp"),
                         ("spu5", "tone", {"table": "pad"}, 0.45, "pad"),
                         ("spu6", "drums", {}, 0.6, "drums")]
                        + [(f"spu{i}", "tone", {}, 0.0, "") for i in range(7, 25)])),
}


def layout(chip_name):
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
                if cell is None:  # hold
                    if cur is None:
                        cur = dict(rest)
                    cur["dur"] += rd
                    continue
                close()
                if cell.get("off"):
                    cur = dict(rest, dur=rd)
                elif "drum" in cell:
                    d = DRUMS[cell["drum"]]
                    cur = {**ch.opts, **d, "dur": rd, "vol": d["vol"] * cell.get("vol", 1.0)}
                    if ch.name == "voice3" and d["wave"] == "tone":
                        cur["shape"] = "triangle"
                else:
                    f = midi_freq(cell["n"])
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
                        cur["duty"] = cur["pw"] = cell["duty"]
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


def render_song(song, rate=dsp.RATE, seed=0, loops=1, crush=True, stereo_out=False):
    """Render a Song to mono float array (or (n,2) if stereo_out). Deterministic, peak <= 0.89."""
    np = need_numpy()
    c = get_chip(song.chip)
    total = int(round(song.duration(loops) * rate))
    tracks, pans = [], []
    for i, ch in enumerate(song.channels):
        if ch.vol <= 0:
            continue
        segs = _channel_segments(song, ch, loops)
        if not any(s["wave"] != "rest" for s in segs):
            continue
        x = c.render(segs, rate, seed + i)  # chip voices + post fx (echo/reverb) per channel
        tracks.append(x * ch.vol)
        pans.append({"lead": 0.0, "bass": 0.0, "drums": 0.0, "harmony": -0.4, "arp": 0.4, "pad": -0.2}.get(ch.role, 0.0))
    if not tracks:
        return np.zeros((total, 2) if stereo_out else total)
    if stereo_out:
        n = max(len(t) for t in tracks)
        st = np.zeros((n, 2))
        for t, p in zip(tracks, pans):
            s = stereo(t, pan=p, width=0.3 if c.era == "32bit" else 0.0, rate=rate)
            st[:len(s)] += s
        return dsp.normalize(st, 0.89)
    x = dsp.mix(*tracks)
    if crush:
        x = era_crush(dsp.normalize(x, 0.89), c.era, rate)
    return dsp.normalize(x, 0.89)


# ---------------------------------------------------------------- procedural composition
MODES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10],
         "phrygian": [0, 1, 3, 5, 7, 8, 10], "harmonic_minor": [0, 2, 3, 5, 7, 8, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10]}

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


def compose(chip_name, style="title", seed=0, bars=4, root=None):
    """Deterministic procedural Song for chip/style/seed. bars = bars of 16 rows (one chord per bar)."""
    np = need_numpy()
    if style not in STYLES:
        raise KeyError(f"unknown style {style!r}; choose from {sorted(STYLES)}")
    st = STYLES[style]
    r = np.random.default_rng([seed, sum(map(ord, chip_name)), sum(map(ord, style))])
    root = root if root is not None else int(57 + r.integers(0, 7))  # A3..D#4
    mode, sc = st["mode"], MODES[st["mode"]]
    prog = st["progs"][int(r.integers(len(st["progs"])))]
    chords = [prog[b % len(prog)] for b in range(bars)]
    chans = layout(chip_name)
    roles = {c.role: c for c in chans if c.role}
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
        p["harmony"] = [{"n": ch[1], "vib": 0.006}] + [None] * 15
        p["pad"] = [{"n": ch[2] - 12, "vol": 0.7}] + [None] * 15
        if drum_pats:
            pat = drum_pats[(b + variant) % len(drum_pats)]
            if b == bars - 1 and style in ("title", "battle"):
                pat = pat[:12] + "ssss"  # fill
            p["drums"] = [None if c == "." else {"drum": c} for c in pat]
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
                if role in roles:
                    rows[roles[role].name] += cells
        for c in chans:  # unused channels / roles: pad with holds
            n = 16 * (end - start)
            rows[c.name] = (rows[c.name] + [None] * n)[:n]
        patterns[name] = rows
        order.append(name)
    if chip_name == "sid" and style == "battle":  # SID flavour: ring-modulated lead, hard-synced bass
        roles["lead"].opts.update(shape="triangle", ring=1.5)
        roles["bass"].opts.update(sync=1.98)
    return Song(chip=chip_name, bpm=st["bpm"], speed=st["speed"], channels=chans, patterns=patterns,
                order=order, loop=style not in ("game_over", "victory"), title=f"{style} #{seed}", style=style)


def render_music(chip_name, style="title", seed=0, bars=2, rate=dsp.RATE, loops=1):
    return render_song(compose(chip_name, style, seed, bars), rate=rate, seed=seed, loops=loops)


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


def parse_cell(tok):
    """'.'=hold, '-' or '---'=off, 'k'/'s'/'h'=drum, 'C4' note, effects after ':' e.g. C4:a047 v u12 d5 @7 w1.
    a=arpeggio (hex semitone digits), v=vibrato, u/d=slide up/down N semitones, @=volume 0-9, w=duty 0-3."""
    if tok in (".", "..", "..."):
        return None
    if set(tok) == {"-"}:
        return {"off": True}
    head, *fx = tok.split(":")
    if head in DRUMS:
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
        else:
            raise ValueError(f"unknown effect {f!r} in {tok!r}")
    return cell


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
noise    k . h . s . h . k k h . s . h h
order A A
loop yes
"""
