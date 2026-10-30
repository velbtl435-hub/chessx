"""Chip base class: a sound = list of segments rendered by a chip's tone/noise voices.

Segment keys: wave ('tone'|'noise'|'rest'), f0, f1 (Hz glide), dur (s), vol, curve ('exp'|'lin'),
arp (semitone list cycled at arp_hz), vib (depth ratio), env (a, d, s, r) or decay (tau seconds),
plus chip-specific voice options (duty, wave shape, operator ratios, ...).
"""
from .._deps import need_numpy
from .. import dsp
from ..dsp import RATE


class Chip:
    name, era, description = "base", "8bit", ""

    def freq_curve(self, seg, n, rate):
        np = need_numpy()
        f0, f1 = float(seg.get("f0", 440)), float(seg.get("f1", seg.get("f0", 440)))
        if seg.get("curve", "exp") == "exp" and f0 > 0 and f1 > 0:
            f = f0 * (f1 / f0) ** np.linspace(0, 1, n)
        else:
            f = np.linspace(f0, f1, n)
        if seg.get("arp"):
            arp = np.asarray(seg["arp"])
            f = f * 2 ** (arp[(np.arange(n) * seg.get("arp_hz", 30) / rate).astype(int) % len(arp)] / 12)
        if seg.get("vib"):
            f = f * (1 + seg["vib"] * np.sin(2 * np.pi * seg.get("vib_hz", 7) * np.arange(n) / rate))
        return f

    def envelope(self, seg, n, rate):
        if "decay" in seg:
            return dsp.exp_decay(n, seg["decay"], rate)
        return dsp.adsr(n, *seg.get("env", (0.002, 0.02, 0.8, 0.02)), rate=rate)

    # chip voices (override)
    def tone(self, f, seg, rate, seed):
        return dsp.osc("square", f, len(f) / rate, rate)

    def noise(self, f, seg, rate, seed):
        return dsp.osc("noise", 0, len(f) / rate, rate, seed=seed)

    def post(self, x, rate, seed):
        return x

    def render(self, segments, rate=RATE, seed=0):
        np = need_numpy()
        parts = []
        for i, seg in enumerate(segments):
            n = int(round(seg["dur"] * rate))
            if seg.get("wave") == "rest" or n == 0:
                parts.append(np.zeros(n))
                continue
            f = self.freq_curve(seg, n, rate)
            v = (self.noise if seg.get("wave") == "noise" else self.tone)(f, seg, rate, seed + i)
            parts.append(v[:n] * self.envelope(seg, n, rate) * seg.get("vol", 1.0))
        out = dsp.concat(parts)
        return dsp.normalize(self.post(dsp.fade(out, 0.002, rate), rate, seed), 0.89)
