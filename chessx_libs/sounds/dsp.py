"""DSP building blocks (numpy; scipy.signal used when available, numpy fallback otherwise).

All generators return float64 mono arrays in [-1, 1] at RATE unless noted.
"""
import wave
from ._deps import need_numpy, scipy_signal

RATE = 22050
NOTE_INDEX = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def note_freq(note) -> float:
    """'A4' -> 440, 'C#5', 'Eb3'; numbers pass through; None/'.'/'-' -> 0."""
    if note is None or note in (".", "-", "---", "0"):
        return 0.0
    if isinstance(note, (int, float)):
        return float(note)
    n = note.strip()
    semi = NOTE_INDEX[n[0].upper()]
    rest = n[1:]
    while rest and rest[0] in "#b":
        semi += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return 440.0 * 2 ** ((semi + 12 * (int(rest or 4) - 4)) / 12)


def rng(seed=None):
    return need_numpy().random.default_rng(seed)


def t_axis(seconds, rate=RATE):
    np = need_numpy()
    return np.arange(max(0, int(round(rate * seconds)))) / rate


def osc(kind, freq, seconds, rate=RATE, duty=0.5, phase=0.0, seed=None):
    """kind: sine|square|pulse|triangle|saw|noise. freq may be scalar or per-sample array."""
    np = need_numpy()
    n = max(0, int(round(rate * seconds)))
    if kind == "noise":
        return rng(seed).uniform(-1, 1, n)
    f = np.broadcast_to(np.asarray(freq, float), (n,)) if np.ndim(freq) == 0 else np.asarray(freq, float)[:n]
    ph = (np.cumsum(f) / rate + phase) % 1.0
    if kind == "sine":
        return np.sin(2 * np.pi * ph)
    if kind in ("square", "pulse"):
        return np.where(ph < (0.5 if kind == "square" else duty), 1.0, -1.0)
    if kind == "triangle":
        return 4 * np.abs(ph - 0.5) - 1
    if kind == "saw":
        return 2 * ph - 1
    raise ValueError(f"unknown oscillator {kind!r}")


def nes_noise(seconds, rate=RATE, period=8, seed=None):
    """Chiptune-style stepped noise (sample-and-hold every `period` samples)."""
    np = need_numpy()
    n = max(0, int(round(rate * seconds)))
    vals = rng(seed).choice([-1.0, 1.0], n // period + 1)
    return np.repeat(vals, period)[:n]


def adsr(n, a=0.005, d=0.05, s=0.7, r=0.05, rate=RATE):
    """ADSR envelope of n samples (release fitted inside n)."""
    np = need_numpy()
    A, D, R = (int(x * rate) for x in (a, d, r))
    A, R = min(A, n), min(R, max(0, n - A))
    D = min(D, max(0, n - A - R))
    S = n - A - D - R
    return np.concatenate([np.linspace(0, 1, A, endpoint=False), np.linspace(1, s, D, endpoint=False),
                           np.full(S, s), np.linspace(s, 0, R)])[:n]


def exp_decay(n, tau, rate=RATE):
    np = need_numpy()
    return np.exp(-np.arange(n) / (rate * tau))


def _onepole(x, cutoff, rate, high=False):
    np = need_numpy()
    a = np.exp(-2 * np.pi * cutoff / rate)
    y, prev = np.empty_like(x), 0.0
    for i, v in enumerate(x):  # fallback only; fine for short clips
        prev = (1 - a) * v + a * prev
        y[i] = prev
    return x - y if high else y


def lowpass(x, cutoff, rate=RATE, order=4):
    sig = scipy_signal()
    cutoff = min(cutoff, rate * 0.45)
    if sig is None:
        return _onepole(x, cutoff, rate)
    return sig.sosfilt(sig.butter(order, cutoff, "low", fs=rate, output="sos"), x)


def highpass(x, cutoff, rate=RATE, order=2):
    sig = scipy_signal()
    if sig is None:
        return _onepole(x, cutoff, rate, high=True)
    return sig.sosfilt(sig.butter(order, cutoff, "high", fs=rate, output="sos"), x)


def bandpass(x, lo, hi, rate=RATE, order=2):
    sig = scipy_signal()
    if sig is None:
        return _onepole(_onepole(x, hi, rate), lo, rate, high=True)
    return sig.sosfilt(sig.butter(order, [lo, min(hi, rate * 0.45)], "band", fs=rate, output="sos"), x)


def delay(x, seconds=0.25, feedback=0.35, mix=0.3, rate=RATE, taps=4):
    need_numpy()
    d = int(seconds * rate)
    out = x.copy()
    for k in range(1, taps + 1):
        if d * k >= len(x):
            break
        out[d * k:] += mix * feedback ** (k - 1) * x[:-d * k]
    return out


def chorus(x, depth=0.003, rate_hz=0.8, mix=0.5, rate=RATE):
    np = need_numpy()
    n = np.arange(len(x))
    dly = (depth * rate) * (1 + np.sin(2 * np.pi * rate_hz * n / rate)) / 2 + 1
    idx = np.clip(n - dly, 0, len(x) - 1)
    return (1 - mix) * x + mix * np.interp(idx, n, x)


def place(buf, clip, at):
    """Add clip into buf starting at sample index `at` (clipped to buf)."""
    at = int(at)
    if at >= len(buf) or at < 0:
        return buf
    m = min(len(clip), len(buf) - at)
    buf[at:at + m] += clip[:m]
    return buf


def concat(parts):
    np = need_numpy()
    return np.concatenate(parts) if parts else np.zeros(0)


def normalize(x, peak=0.89):
    """Scale to peak (never louder than 1); silent input stays silent."""
    np = need_numpy()
    x = np.nan_to_num(np.asarray(x, float))
    m = np.max(np.abs(x)) if x.size else 0
    return x * (peak / m) if m > 0 else x


def fade(x, seconds=0.005, rate=RATE):
    np = need_numpy()
    n = min(int(seconds * rate), len(x) // 2)
    if n:
        r = np.linspace(0, 1, n)
        x[:n] *= r
        x[-n:] *= r[::-1]
    return x


def to_pcm16(x):
    np = need_numpy()
    return (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()


def write_wav(path, x, rate=RATE):
    """Write mono 16-bit WAV with stdlib wave; returns path."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(to_pcm16(x))
    return str(path)


def mix(*clips):
    """Sum clips of different lengths (zero-padded to the longest)."""
    np = need_numpy()
    n = max((len(c) for c in clips), default=0)
    out = np.zeros(n)
    for c in clips:
        out[:len(c)] += c
    return out
