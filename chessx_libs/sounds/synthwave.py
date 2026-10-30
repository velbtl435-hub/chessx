"""Synthwave: detuned saw pads, lowpass sweeps, delay/chorus, bass and arps, gated-ish drums."""
from ._deps import need_numpy
from . import dsp
from .dsp import RATE, note_freq


def supersaw(freq, seconds, voices=5, detune=0.012, rate=RATE, seed=0):
    np = need_numpy()
    r = dsp.rng(seed)
    offs = np.linspace(-detune, detune, voices)
    return sum(dsp.osc("saw", freq * (1 + o), seconds, rate, phase=r.random()) for o in offs) / voices


def pad(chord, seconds, cutoff=1800, rate=RATE, seed=0):
    """Detuned saw chord through lowpass + chorus, slow attack/release."""
    x = sum(supersaw(note_freq(n), seconds, rate=rate, seed=seed + i) for i, n in enumerate(chord)) / len(chord)
    x = dsp.lowpass(x, cutoff, rate) * dsp.adsr(len(x), 0.3 * seconds, 0.1, 0.8, 0.3 * seconds, rate)
    return dsp.chorus(x, rate=rate)


def bass(notes, step, rate=RATE, cutoff=500):
    parts = []
    for n in notes:
        f = note_freq(n)
        x = dsp.osc("saw", f, step, rate) + 0.5 * dsp.osc("square", f / 2, step, rate) if f else dsp.osc("sine", 0, step, rate)
        parts.append(dsp.lowpass(x, cutoff, rate) * dsp.adsr(len(x), 0.003, 0.08, 0.5, 0.02, rate))
    return dsp.concat(parts)


def arp(chord, step, steps, rate=RATE, cutoff=3000, seed=0):
    need_numpy()
    freqs = [note_freq(n) for n in chord]
    seq = [freqs[i % len(freqs)] * (2 if (i // len(freqs)) % 2 else 1) for i in range(steps)]
    parts = [dsp.osc("saw", f, step, rate) * dsp.exp_decay(int(round(step * rate)), step / 3, rate) for f in seq]
    return dsp.delay(dsp.lowpass(dsp.concat(parts), cutoff, rate), seconds=step * 3, rate=rate)


def drums(steps, step, rate=RATE, seed=0):
    """Kick on beats, gated noise snare on 2 and 4 (in 16ths: 4 and 12)."""
    np = need_numpy()
    n_step = int(round(step * rate))
    out = np.zeros(n_step * steps)
    kn = int(0.25 * rate)
    t = np.arange(kn) / rate
    kick = np.sin(2 * np.pi * (50 * t + 60 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 12)
    sn = dsp.bandpass(dsp.osc("noise", 0, 0.18, rate, seed=seed), 900, 6000, rate)
    sn = sn * (np.arange(len(sn)) < int(0.12 * rate))  # gate
    for i in range(steps):
        if i % 4 == 0:
            dsp.place(out, kick, i * n_step)
        if i % 16 in (4, 12):
            dsp.place(out, 0.5 * sn, i * n_step)
    return out


def loop(bars=2, bpm=100, rate=RATE, seed=0):
    """Classic i-VI-III-VII synthwave loop (Am-F-C-G), one chord per bar."""
    np = need_numpy()
    step = 60 / bpm / 4
    chords = [["A3", "C4", "E4"], ["F3", "A3", "C4"], ["C4", "E4", "G4"], ["G3", "B3", "D4"]]
    roots = ["A1", "F1", "C2", "G1"]
    bar_n = int(round(step * rate)) * 16
    out = np.zeros(bar_n * bars)
    for b in range(bars):
        ch = chords[b % 4]
        fit = lambda x: np.pad(x, (0, max(0, bar_n - len(x))))[:bar_n]
        seg = 0.5 * fit(pad(ch, 16 * step, rate=rate, seed=seed + b))
        seg = seg + 0.6 * fit(bass([roots[b % 4], roots[b % 4][:-1] + str(int(roots[b % 4][-1]) + 1)] * 8, step, rate))
        seg = seg + 0.25 * fit(arp(ch, step, 16, rate, seed=seed))
        seg = seg + 0.5 * fit(drums(16, step, rate, seed=seed))
        dsp.place(out, seg, b * bar_n)
    return dsp.normalize(dsp.delay(out, seconds=step * 3, feedback=0.3, mix=0.15, rate=rate))
