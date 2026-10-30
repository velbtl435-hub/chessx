"""8-bit chiptune synth: pulse/square (duty), triangle, noise channels, ADSR, arpeggio,
and a tiny tracker-style pattern sequencer.

Pattern syntax (whitespace separated, one token per step):
  C4 / F#3 / Eb5  start a note        -   hold previous note     .  rest
  C4:047          arpeggio (semitone offsets cycled fast)        x  noise hit (noise channel)
"""
from ._deps import need_numpy
from . import dsp
from .dsp import RATE

INSTRUMENTS = {  # name -> (wave, duty, adsr)
    "pulse12": ("pulse", 0.125, (0.002, 0.04, 0.6, 0.03)),
    "pulse25": ("pulse", 0.25, (0.002, 0.05, 0.6, 0.03)),
    "square": ("square", 0.5, (0.002, 0.05, 0.6, 0.03)),
    "triangle": ("triangle", 0.5, (0.001, 0.0, 1.0, 0.02)),
    "noise": ("noise", 0.5, (0.001, 0.06, 0.0, 0.01)),
}


def chip_note(freq, seconds, instrument="square", arp=None, arp_rate=50.0, vibrato=0.0, rate=RATE, seed=None):
    """Render one note. arp: semitone offsets cycled at arp_rate Hz (classic chip chord)."""
    np = need_numpy()
    wave_, duty, env = INSTRUMENTS[instrument]
    n = int(round(rate * seconds))
    if wave_ == "noise":
        period = max(1, int(rate / max(freq, 1) * 4)) if freq else 6
        x = dsp.nes_noise(seconds, rate, period, seed)
    else:
        f = np.full(n, float(freq))
        if arp:
            step = (np.arange(n) * arp_rate / rate).astype(int) % len(arp)
            f = f * 2 ** (np.asarray(arp)[step] / 12)
        if vibrato:
            f = f * (1 + vibrato * np.sin(2 * np.pi * 6 * np.arange(n) / rate))
        x = dsp.osc(wave_, f, seconds, rate, duty=duty)
        x = np.round(x * 7) / 7  # 4-bit-ish amplitude steps
    return x[:n] * dsp.adsr(n, *env, rate=rate)


def parse_pattern(pattern):
    """'C4 - . E4:047' -> list of (freq, steps, arp) events with start step."""
    toks = pattern.split() if isinstance(pattern, str) else list(pattern)
    events = []
    for i, t in enumerate(toks):
        if t == "-" and events:
            events[-1][2] += 1
        elif t in (".", "-"):
            continue
        else:
            note, _, arp = t.partition(":")
            freq = 1000.0 if note.lower() == "x" else dsp.note_freq(note)
            events.append([i, freq, 1, [int(c) for c in arp] if arp else None])
    return events, len(toks)


def render_pattern(channels, bpm=140, steps_per_beat=4, rate=RATE, seed=0, gains=None):
    """channels: {name: (instrument, pattern)}. Returns normalized mono mix."""
    np = need_numpy()
    step = 60.0 / bpm / steps_per_beat
    parsed = {k: (inst, *parse_pattern(p)) for k, (inst, p) in channels.items()}
    total = max(n for _, _, n in parsed.values())
    out = np.zeros(int(round(total * step * rate)) + 1)
    for ci, (name, (inst, events, _)) in enumerate(parsed.items()):
        g = (gains or {}).get(name, 0.6 if inst == "noise" else 1.0)
        for start, freq, steps, arp in events:
            clip = chip_note(freq, steps * step, inst, arp=arp, rate=rate, seed=seed + ci * 1000 + start)
            dsp.place(out, g * clip, start * step * rate)
    return dsp.normalize(out)


def jingle(notes, instrument="pulse25", step=0.08, rate=RATE, bass=True):
    """Quick melody from note names, optional triangle bass an octave below."""
    pat = " ".join(notes)
    ch = {"lead": (instrument, pat)}
    if bass:
        low = [n if n in (".", "-") else f"{n.split(':')[0][:-1]}{int(n.split(':')[0][-1]) - 1}" for n in notes]
        ch["bass"] = ("triangle", " ".join(low))
    return render_pattern(ch, bpm=60 / step / 4, rate=rate)


JINGLES = {
    "win": ["C5", "E5", "G5", "C6", "-", "-"],
    "lose": ["G4", "F#4", "F4", "E4", "-", "-"],
    "coin": ["B5", "E6", "-", "-"],
    "powerup": ["C5:047", "E5:047", "G5:047", "C6:047", "-"],
    "notify": ["E5", "A5", "-"],
    "boot": ["C4", "G4", "C5", "E5", "G5", "C6", "-", "-"],
}


def theme(rate=RATE, bars=2, seed=0):
    """Short looping chiptune theme (lead, arp, triangle bass, noise drums)."""
    lead = "E5 - G5 - A5 - G5 E5 D5 - C5 - D5 - E5 - " * bars
    arp = "C4:047 - - - A3:037 - - - F3:047 - - - G3:047 - - - " * bars
    bass = "C3 . C3 . A2 . A2 . F2 . F2 . G2 . G2 . " * bars
    drums = "x . x x . . x . x . x x . . x x " * bars
    return render_pattern({"lead": ("pulse25", lead), "arp": ("pulse12", arp), "bass": ("triangle", bass),
                           "drums": ("noise", drums)}, bpm=150, rate=rate, seed=seed,
                          gains={"arp": 0.35, "drums": 0.3})
