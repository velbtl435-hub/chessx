"""MOS 6581/8580 SID approximation (C64).

3 voices; waveforms saw/triangle/pulse(12-bit width)/noise (23-bit LFSR, clocked by the oscillator
MSB like the real chip); ring modulation (triangle XOR with previous voice's MSB -> here: multiply
by sign of modulator), hard sync (reset phase on modulator wrap), SID-style ADSR (exponential decay/
release), multimode resonant state-variable filter (LP/BP/HP, cutoff sweep), 4-bit master volume.
"""
from .._deps import need_numpy
from .. import dsp
from .base import Chip


def _phase(f, rate, sync_f=None):
    np = need_numpy()
    if sync_f is None:
        return (np.cumsum(f) / rate) % 1.0
    ph, m, out = 0.0, 0.0, np.empty(len(f))
    for i in range(len(f)):  # hard sync: carrier resets when modulator wraps
        m += sync_f[i] / rate
        if m >= 1.0:
            m -= 1.0
            ph = 0.0
        ph = (ph + f[i] / rate) % 1.0
        out[i] = ph
    return out


def sid_noise(ph, seed=0):
    """23-bit LFSR clocked on oscillator bit-19 rising edges (approx: each phase wrap*16)."""
    np = need_numpy()
    clk = np.floor(np.cumsum(np.diff(ph, prepend=ph[:1]) % 1.0) * 16).astype(int)
    steps = int(clk[-1]) + 1 if len(clk) else 1
    reg, vals = 0x7FFFF8 ^ (seed & 0xFFFF), np.empty(steps)
    for i in range(steps):
        bit = ((reg >> 22) ^ (reg >> 17)) & 1
        reg = ((reg << 1) | bit) & 0x7FFFFF
        vals[i] = ((reg >> 15) & 0xFF) / 127.5 - 1
    return vals[clk]


def svf(x, cutoff, res=0.5, mode="lp", rate=44100):
    """Chamberlin state-variable filter; cutoff scalar or per-sample array; res 0..1."""
    np = need_numpy()
    fc = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    F = 2 * np.sin(np.pi * np.clip(fc, 20, rate / 6) / rate)
    q = 1.0 - 0.9 * np.clip(res, 0, 1)
    lp = bp = 0.0
    out = np.empty_like(x)
    for i, v in enumerate(x):
        hp = v - lp - q * bp
        bp += F[i] * hp
        lp += F[i] * bp
        out[i] = lp if mode == "lp" else bp if mode == "bp" else hp
    return out


class SID(Chip):
    name, era = "sid", "8bit"
    description = "MOS SID: saw/tri/pulse/noise, ring mod, hard sync, ADSR, resonant multimode filter"

    def tone(self, f, seg, rate, seed):
        np = need_numpy()
        w = seg.get("shape", "saw")
        sync = f * seg["sync"] if seg.get("sync") else None
        ph = _phase(f, rate, sync)
        if w == "noise":
            return sid_noise(ph, seed)
        if w == "pulse":
            pw = seg.get("pw", 0.5)
            if seg.get("pwm"):  # pulse-width modulation sweep
                pw = pw + seg["pwm"] * np.sin(2 * np.pi * 3 * np.arange(len(f)) / rate)
            x = np.where(ph < np.clip(pw, 0.02, 0.98), 1.0, -1.0)
        elif w == "triangle":
            x = 4 * np.abs(ph - 0.5) - 1
        else:
            x = 2 * ph - 1
        if seg.get("ring"):  # ring mod by a modulator at f * ring ratio
            x = np.abs(x) * np.sign(np.sin(2 * np.pi * np.cumsum(f * seg["ring"]) / rate)) if w == "triangle" \
                else x * np.sign(np.sin(2 * np.pi * np.cumsum(f * seg["ring"]) / rate))
        if seg.get("combined"):  # crude combined waveform (saw AND tri) "SID growl"
            x = np.minimum(x, 4 * np.abs(ph - 0.5) - 1)
        return x

    def noise(self, f, seg, rate, seed):
        np = need_numpy()
        return sid_noise((np.cumsum(np.maximum(f, 50) * 8) / rate) % 1.0, seed)

    def envelope(self, seg, n, rate):
        np = need_numpy()
        a, d, s, r = seg.get("env", (0.002, 0.06, 0.5, 0.08))
        A, R = min(n, int(a * rate)), min(n, int(r * rate))
        body = n - A - R
        t = np.arange(max(body, 0)) / rate
        dec = s + (1 - s) * np.exp(-t / max(d / 3, 1e-4))  # exponential decay like the SID
        rel = (dec[-1] if len(dec) else 1) * np.exp(-np.arange(R) / rate / max(r / 4, 1e-4))
        return np.concatenate([np.linspace(0, 1, A), dec, rel])[:n]

    def render(self, segments, rate=dsp.RATE, seed=0):
        x = super().render(segments, rate, seed)
        filt = next((s["filter"] for s in segments if s.get("filter")), None)
        if filt:
            np = need_numpy()
            c0, c1 = filt.get("from", 3000), filt.get("to", filt.get("from", 3000))
            cut = c0 * (c1 / c0) ** np.linspace(0, 1, len(x))
            x = dsp.normalize(svf(x, cut, filt.get("res", 0.6), filt.get("mode", "lp"), rate), 0.89)
        return x

    def voices3(self, v1, v2, v3, rate=dsp.RATE, seed=0, filter=None):
        """Mix three voices (each a segment list), optional global filter."""
        np = need_numpy()
        vs = [Chip.render(self, v, rate, seed + k) for k, v in enumerate((v1, v2, v3)) if v]
        x = dsp.mix(*vs) / max(1, len(vs))
        if filter:
            x = svf(x, filter.get("cutoff", 2000), filter.get("res", 0.5), filter.get("mode", "lp"), rate)
        return dsp.normalize(x)
