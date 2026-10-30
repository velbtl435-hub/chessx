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
