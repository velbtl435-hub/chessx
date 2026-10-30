"""PSG approximations: General Instrument AY-3-8910 (ZX Spectrum 128/MSX/Atari ST) and TI SN76489
(Master System/Mega Drive/BBC). Square tones with period quantization from the chip clock, noise,
logarithmic 4-bit volume, AY hardware envelopes (shapes: decay \\, attack /, saw \\\\\\, tri /\\/\\).
"""
from .._deps import need_numpy
from .base import Chip
from . import nes


def log_volume(levels=16, db_step=2.0):
    np = need_numpy()
    v = 10 ** (-db_step * np.arange(levels)[::-1] / 20)
    v[0] = 0
    return v


class AY8910(Chip):
    name, era = "ay", "8bit"
    description = "AY-3-8910: 3 square (12-bit period), 5-bit noise, hardware envelope, log volume"
    clock = 1773400.0  # ZX Spectrum 128

    def quant(self, f):
        np = need_numpy()
        tp = np.clip(np.round(self.clock / (16 * np.maximum(f, 1))), 1, 4095)
        return self.clock / (16 * tp)

    def tone(self, f, seg, rate, seed):
        np = need_numpy()
        ph = (np.cumsum(self.quant(f)) / rate) % 1.0
        x = np.where(ph < 0.5, 1.0, -1.0)
        if seg.get("hw_env"):
            x = (x + 1) / 2 * self.hw_env(len(f), seg["hw_env"], seg.get("env_hz", 20), rate) * 2 - 1
        return x

    def hw_env(self, n, shape, hz, rate):
        np = need_numpy()
        ph = (np.arange(n) * hz / rate)
        fr = ph % 1.0
        shp = {"decay": 1 - np.minimum(ph, 1), "attack": np.minimum(ph, 1), "saw": 1 - fr,
               "tri": np.where(ph.astype(int) % 2 == 0, 1 - fr, fr)}[shape]
        lv = log_volume()
        return lv[np.clip((shp * 15).astype(int), 0, 15)]

    def noise(self, f, seg, rate, seed):
        np = need_numpy()
        period = int(np.clip(round(self.clock / 16 / max(f[0], 100)), 1, 31))
        clocks = self.clock / 16 / period / rate
        n = len(f)
        reg, steps = 1, int(n * clocks) + 2
        vals = np.empty(steps)
        for i in range(steps):  # 17-bit LFSR, taps 0 and 3
            reg = (reg >> 1) | ((((reg >> 0) ^ (reg >> 3)) & 1) << 16)
            vals[i] = 1.0 if reg & 1 else -1.0
        return vals[(np.arange(n) * clocks).astype(int)]

    def envelope(self, seg, n, rate):  # quantize software envelope to 16 log steps
        np = need_numpy()
        e = super().envelope(seg, n, rate)
        return log_volume()[np.clip(np.round(e * 15).astype(int), 0, 15)]


class SN76489(AY8910):
    name, era = "sn", "8bit"
    description = "SN76489: 3 square (10-bit period) + periodic/white noise (15/16-bit LFSR), 2 dB attenuation"
    clock = 3579545.0

    def quant(self, f):
        np = need_numpy()
        n = np.clip(np.round(self.clock / (32 * np.maximum(f, 1))), 1, 1023)
        return self.clock / (32 * n)

    def noise(self, f, seg, rate, seed):
        if seg.get("periodic"):  # periodic noise = buzzy tone
            np = need_numpy()
            ph = (np.cumsum(self.quant(f) / 15) / rate) % 1.0
            return np.where(ph < 1 / 15, 1.0, -1.0)
        return nes.lfsr_noise(len(f), max(4, int(self.clock / 2 / nes.CPU * 2 * 32 * 16 / max(f[0], 100))),
                              rate)
