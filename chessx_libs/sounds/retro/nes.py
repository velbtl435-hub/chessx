"""NES 2A03 and Game Boy DMG approximations.

2A03: 2 pulse channels (duty 12.5/25/50/75%), 11-bit period quantization (CPU 1.789773 MHz),
triangle with 32-step 4-bit staircase, 15-bit LFSR noise (long/short mode) with the 16 NTSC
period table, DPCM-ish 1-bit delta playback of a procedurally generated waveform.
DMG: same pulse/noise idea + 4-bit 32-sample wave channel; output 4-bit DAC + highpass.
"""
from .._deps import need_numpy
from .. import dsp
from .base import Chip

CPU = 1789773.0
NOISE_PERIODS = [4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068]
DUTIES = {0: 0.125, 1: 0.25, 2: 0.5, 3: 0.75}


def quantize_pulse(f):
    """Snap to frequencies reachable by an 11-bit pulse timer: f = CPU / (16 * (t + 1))."""
    np = need_numpy()
    t = np.clip(np.round(CPU / (16 * np.maximum(f, 1)) - 1), 8, 2047)
    return CPU / (16 * (t + 1))


def lfsr(steps, short=False):
    """2A03 noise shift register output (+1/-1), `steps` clocks."""
    np = need_numpy()
    reg, tap, out = 1, 6 if short else 1, np.empty(steps)
    for i in range(steps):
        fb = (reg & 1) ^ ((reg >> tap) & 1)
        reg = (reg >> 1) | (fb << 14)
        out[i] = 1.0 if reg & 1 else -1.0
    return out


def lfsr_noise(n, period, rate, short=False):
    np = need_numpy()
    clocks_per_sample = CPU / 2 / period / rate
    steps = int(n * clocks_per_sample) + 2
    seq = lfsr(min(steps, 200000), short)
    idx = (np.arange(n) * clocks_per_sample).astype(int) % len(seq)
    return seq[idx]


def triangle4(f, rate):
    """32-step 4-bit staircase triangle (15..0..15)."""
    np = need_numpy()
    ph = (np.cumsum(f) / rate) % 1.0
    step = (ph * 32).astype(int)
    lvl = np.where(step < 16, 15 - step, step - 16)
    return lvl / 7.5 - 1


def dpcm(f, rate, seed=0):
    """DPCM-ish: 1-bit delta coding of a sine+noise source at 33 kHz-ish, 7-bit counter."""
    np = need_numpy()
    src = 0.7 * np.sin(2 * np.pi * np.cumsum(f) / rate) + 0.3 * dsp.rng(seed).uniform(-1, 1, len(f))
    out, c = np.empty(len(f)), 64
    for i, s in enumerate(src):
        target = (s + 1) * 63.5
        c = min(127, c + 2) if target > c else max(0, c - 2)
        out[i] = c / 63.5 - 1
    return out


class NES(Chip):
    name, era = "nes", "8bit"
    description = "Ricoh 2A03: 2 pulse (duty), 4-bit triangle, LFSR noise, DPCM-ish"

    def tone(self, f, seg, rate, seed):
        np = need_numpy()
        v = seg.get("voice", "pulse")
        if v == "triangle":
            return triangle4(f, rate)
        if v == "dpcm":
            return dpcm(f, rate, seed)
        fq = quantize_pulse(f)
        ph = (np.cumsum(fq) / rate) % 1.0
        x = np.where(ph < DUTIES.get(seg.get("duty", 2), 0.5), 1.0, -1.0)
        return np.round(x * 7.5) / 7.5  # 4-bit volume stage

    def noise(self, f, seg, rate, seed):
        np = need_numpy()
        n = len(f)
        idx = int(np.clip(seg.get("period", 4), 0, 15))
        if seg.get("f0") and seg.get("sweep", True):  # higher f0 -> shorter period
            out, chunk = np.empty(n), max(1, n // 16)
            for k in range(0, n, chunk):
                p = int(np.clip(round(15 - np.log2(max(f[k], 2)) * 1.2), 0, 15))
                out[k:k + chunk] = lfsr_noise(min(chunk, n - k), NOISE_PERIODS[p], rate, seg.get("short", False))
            return out
        return lfsr_noise(n, NOISE_PERIODS[idx], rate, seg.get("short", False))

    def post(self, x, rate, seed):  # NES output filters: HP 90 Hz, LP 14 kHz
        return dsp.lowpass(dsp.highpass(x, 90, rate, 1), 14000, rate, 1)


WAVE_RAM = [0, 2, 4, 6, 8, 10, 12, 14, 15, 15, 14, 13, 12, 10, 8, 6, 4, 2, 0, 1, 3, 5, 7, 9,
            11, 13, 15, 14, 11, 7, 3, 1]


class GameBoy(NES):
    name, era = "gb", "8bit"
    description = "Game Boy DMG: pulse (duty), 32x4-bit wave RAM channel, 7/15-bit LFSR noise"

    def tone(self, f, seg, rate, seed):
        np = need_numpy()
        if seg.get("voice") == "wave":
            ph = (np.cumsum(f) / rate) % 1.0
            return np.asarray(WAVE_RAM)[(ph * 32).astype(int)] / 7.5 - 1
        return super().tone(f, {**seg, "voice": "pulse"}, rate, seed)

    def post(self, x, rate, seed):  # tinny speaker: HP 200 Hz, 4-bit-ish DAC
        np = need_numpy()
        return np.round(dsp.highpass(x, 200, rate, 1) * 15) / 15
