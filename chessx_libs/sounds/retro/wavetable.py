"""Sample-less 16/32-bit wavetable approximations.

SNES S-DSP: 8 voices of BRR-like wavetables (4-bit ADPCM-ish quantization of a short procedural cycle),
gaussian interpolation (approximated by a lowpass), 8-tap FIR echo with feedback.
PS1 SPU: 24 voices of 16-bit wavetables at 44.1 kHz, ADSR, richer layered detune, reverb and stereo
(see `render_stereo`)."""
from .._deps import need_numpy
from .. import dsp
from .base import Chip
from .crush import stereo

TABLES = ("strings", "brass", "bell", "organ", "bass", "pad")


def table(kind, size=64):
    np = need_numpy()
    t = np.arange(size) / size
    harm = {"strings": [1, .5, .33, .25, .2, .16], "brass": [1, .8, .6, .4, .3], "organ": [1, 0, .6, 0, .3, 0, .2],
            "bell": [1, 0, 0, .5, 0, 0, .3], "bass": [1, .4, .1], "pad": [1, .3, .15, .07]}[kind]
    w = sum(a * np.sin(2 * np.pi * (k + 1) * t) for k, a in enumerate(harm))
    return w / np.abs(w).max()


def brr(w):
    """BRR-like: 4-bit nibbles with a per-16-sample block shift (range) + filter-1 prediction."""
    np = need_numpy()
    out, prev = np.empty_like(w), 0.0
    for b in range(0, len(w), 16):
        blk = w[b:b + 16]
        resid = blk - 15 / 16 * np.concatenate([[prev], blk[:-1]])
        scale = max(np.abs(resid).max(), 1e-6) / 7
        q = np.clip(np.round(resid / scale), -8, 7) * scale
        for i, r in enumerate(q):
            prev = 15 / 16 * prev + r
            out[b + i] = prev
    return out / max(np.abs(out).max(), 1e-9)


def play_table(w, f, rate):
    np = need_numpy()
    idx = (np.cumsum(f) / rate * len(w)) % len(w)
    i0 = idx.astype(int)
    fr = idx - i0
    return w[i0] * (1 - fr) + w[(i0 + 1) % len(w)] * fr


def fir_echo(x, rate, delay=0.12, feedback=0.4, taps=(0.5, 0.25, 0.125, 0.06, 0.03, 0.015, 0.008, 0.004), mix=0.35):
    np = need_numpy()
    d = max(1, int(delay * rate))
    out = np.concatenate([x, np.zeros(int(d * 4))])
    buf = out.copy()
    for k in range(1, 5):
        buf[k * d:] += (feedback ** k) * np.convolve(out[:-k * d], np.asarray(taps), "same")
    return out * (1 - mix) + buf * mix


def reverb(x, rate, size=0.6, mix=0.3):
    """Schroeder-ish: 4 combs + 2 allpass-like delays (numpy loops kept short)."""
    np = need_numpy()
    tail = int(rate * size * 1.5)
    y = np.concatenate([x, np.zeros(tail)])
    acc = np.zeros_like(y)
    for ms, g in ((29.7, .77), (37.1, .75), (41.1, .73), (43.7, .71)):
        d = int(ms / 1000 * rate)
        c = y.copy()
        for k in range(1, int(size * 1.5 * rate / d)):
            c[k * d:] += (g ** k) * y[:-k * d]
        acc += c
    acc = dsp.lowpass(acc / 4, 5000, rate)
    return y * (1 - mix) + acc / max(np.abs(acc).max(), 1e-9) * np.abs(y).max() * mix


class SNES(Chip):
    name, era = "snes", "16bit"
    description = "SNES S-DSP: BRR-like 4-bit wavetables, gaussian-ish interpolation, FIR echo"

    def tone(self, f, seg, rate, seed):
        return play_table(brr(table(seg.get("table", "strings"))), f, rate)

    def noise(self, f, seg, rate, seed):
        return dsp.osc("noise", 0, len(f) / rate, rate, seed=seed)

    def post(self, x, rate, seed):
        return fir_echo(dsp.lowpass(x, 10000, rate), rate)


class PS1(Chip):
    name, era = "ps1", "32bit"
    description = "PS1 SPU: 16-bit wavetables, detuned layers, ADSR, reverb, stereo"

    def tone(self, f, seg, rate, seed):
        w = table(seg.get("table", "pad"), 256)
        return sum(play_table(w, f * d, rate) for d in (1.0, 1.004, 0.996, 2.0 * 1.001)) / 3

    def noise(self, f, seg, rate, seed):
        return dsp.lowpass(dsp.osc("noise", 0, len(f) / rate, rate, seed=seed), 6000, rate)

    def post(self, x, rate, seed):
        return reverb(x, rate)

    def render_stereo(self, segments, rate=44100, seed=0, pan=0.0, width=0.6):
        return stereo(self.render(segments, rate, seed), pan, width)
