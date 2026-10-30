"""FM synthesis approximations: Yamaha YM2612/OPN2 (4-op, 8 algorithms, op1 feedback, Mega Drive)
and OPL2/YM3812 (2-op, AdLib/Sound Blaster, 4 waveforms). Phase modulation with per-operator
ratio, level and decay; DAC output quantized (9-bit for YM2612 ladder, 'ladder' effect ignored)."""
from .._deps import need_numpy
from .base import Chip

# algorithm -> (list of (modulator, carrier) edges, carriers). Ops numbered 0..3.
ALGORITHMS = {
    0: ([(0, 1), (1, 2), (2, 3)], [3]),
    1: ([(0, 2), (1, 2), (2, 3)], [3]),
    2: ([(0, 3), (1, 2), (2, 3)], [3]),
    3: ([(0, 1), (1, 3), (2, 3)], [3]),
    4: ([(0, 1), (2, 3)], [1, 3]),
    5: ([(0, 1), (0, 2), (0, 3)], [1, 2, 3]),
    6: ([(0, 1)], [1, 2, 3]),
    7: ([], [0, 1, 2, 3]),
}


def fm_voice(f, rate, ratios, levels, decays, algorithm=4, feedback=0.0):
    """Render a 4-op FM voice. f: per-sample Hz. Vectorised per operator (feedback via 1-sample loop on op0)."""
    np = need_numpy()
    n = len(f)
    t = np.arange(n) / rate
    edges, carriers = ALGORITHMS[algorithm]
    out = [None] * 4
    for op in range(4):
        ph = 2 * np.pi * np.cumsum(f * ratios[op]) / rate
        env = levels[op] * np.exp(-t / max(decays[op], 1e-4))
        mod = sum((out[m] for m, c in edges if c == op), np.zeros(n))
        if op == 0 and feedback:
            y, p1, p2 = np.empty(n), 0.0, 0.0
            for i in range(n):
                v = np.sin(ph[i] + feedback * (p1 + p2) / 2) * env[i]
                y[i], p2, p1 = v, p1, v
            out[op] = y
        else:
            out[op] = np.sin(ph + np.pi * mod) * env
    return sum(out[c] for c in carriers) / len(carriers)


class YM2612(Chip):
    name, era = "fm", "16bit"
    description = "YM2612/OPN2: 4-operator FM, 8 algorithms, op1 feedback, 9-bit DAC"

    def tone(self, f, seg, rate, seed):
        np = need_numpy()
        x = fm_voice(f, rate, seg.get("ratios", (1, 2, 1, 1)), seg.get("levels", (1.2, 0.8, 0.9, 1.0)),
                     seg.get("decays", (0.08, 0.2, 0.15, 0.4)), seg.get("algorithm", 4),
                     seg.get("feedback", 0.6))
        return np.round(x * 255) / 255

    def noise(self, f, seg, rate, seed):  # FM "noise": heavy feedback + inharmonic ratio
        return fm_voice(f, rate, (7.13, 1.41, 3.3, 1), (3, 2, 2, 1), (1, 1, 1, 1), 0, 3.0)


class OPL2(YM2612):
    name, era = "opl", "16bit"
    description = "OPL2/YM3812: 2-operator FM (AdLib), feedback, waveforms sine/half/abs/quarter"

    def tone(self, f, seg, rate, seed):
        if seg.get("rhythm"):  # rhythm-mode instrument (channels 7-9)
            return opl_rhythm(seg["rhythm"], f, rate, seed, seg.get("f8", RHYTHM_F8), seg.get("f9", RHYTHM_F9))
        np = need_numpy()
        n = len(f)
        t = np.arange(n) / rate
        mr, cr = seg.get("ratios", (2, 1))[:2]
        m = np.sin(2 * np.pi * np.cumsum(f * mr) / rate) * seg.get("mod", 1.5) * np.exp(-t / seg.get("mdecay", 0.15))
        x = np.sin(2 * np.pi * np.cumsum(f * cr) / rate + m)
        ws = seg.get("ws", 0)
        if ws == 1:
            x = np.maximum(x, 0)
        elif ws == 2:
            x = np.abs(x)
        elif ws == 3:
            x = np.abs(x) * (((np.cumsum(f * cr) / rate) * 4).astype(int) % 2 == 0)
        return x


# ---------------------------------------------------------------- OPL2 rhythm mode (register 0xBD bit 5)
RHYTHM_F8, RHYTHM_F9 = 360.0, 270.0  # default block/F-number pitches of channels 8 and 9 (shared by SD/HH, TOM/CYM)


def opl_noise(n, seed=0):
    """OPL 23-bit noise LFSR (taps 0x800302, as in the YM3812), one step per sample -> 0/1 bits."""
    np = need_numpy()
    reg, out = 1 + (seed % 0x7FFFFF), np.empty(n, dtype=np.int8)
    for i in range(n):
        if reg & 1:
            reg ^= 0x800302
        reg >>= 1
        out[i] = reg & 1
    return out


def opl_rhythm(hit, f, rate, seed=0, f8=RHYTHM_F8, f9=RHYTHM_F9):
    """One OPL2 rhythm-mode instrument. Channels 7-9 lose their melodic role:
    BD = channel 7 (normal 2-op FM, pitch from f); SD = ch8 carrier, phase from bit 8 of the ch8 modulator (op13)
    XOR noise; TOM = ch9 modulator alone (plain sine at f9); HH and CYM = 10-bit phase built from bit tricks of
    op13 (ch8 mod) and op17 (ch9 carrier) phases, HH also mixed with noise. Same bit logic as the hardware."""
    np = need_numpy()
    n = len(f)
    t = np.arange(n) / rate
    if hit == "bd":
        m = np.sin(2 * np.pi * np.cumsum(f) / rate) * 0.8 * np.exp(-t / 0.03)
        return np.sin(2 * np.pi * np.cumsum(f) / rate + m)
    if hit == "tom":
        return np.sin(2 * np.pi * f9 * t)
    p13 = (np.floor(f8 * t * 1024).astype(np.int64)) & 0x3FF
    p17 = (np.floor(f9 * t * 1024).astype(np.int64)) & 0x3FF
    noise = opl_noise(n, seed).astype(bool)
    res1 = (((p13 >> 2) ^ (p13 >> 7)) | (p13 >> 3)) & 1
    res2 = ((p17 >> 5) ^ (p17 >> 3)) & 1
    either = (res1 | res2).astype(bool)
    if hit == "hh":
        phase = np.where(either, 0x200 | (0xD0 >> 2), 0xD0)
        phase = np.where(phase & 0x200, np.where(noise, 0x200 | 0xD0, phase), np.where(noise, 0xD0 >> 2, phase))
    elif hit == "sd":
        phase = np.where((p13 >> 8) & 1, 0x200, 0x100)
        phase = np.where(noise, phase ^ 0x100, phase)
    elif hit == "cym":
        phase = np.where(either, 0x300, 0x100)
    else:
        raise ValueError(f"unknown OPL rhythm instrument {hit!r}")
    return np.sin(2 * np.pi * phase / 1024.0)

