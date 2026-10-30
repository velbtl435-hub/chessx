"""Bit-depth / sample-rate crushing and stereo helpers."""
import wave
from .._deps import need_numpy
from ..dsp import RATE

# era -> (bits, effective sample rate)
ERAS = {"8bit": (4, 11025), "16bit": (12, 22050), "32bit": (16, 44100)}


def bitcrush(x, bits=8):
    """Quantize amplitude to `bits` (mid-tread), keeps |x|<=1."""
    np = need_numpy()
    q = 2 ** (bits - 1) - 1
    return np.clip(np.round(np.asarray(x) * q) / q, -1, 1)


def srcrush(x, target_rate, rate=RATE):
    """Sample-and-hold down to target_rate (aliasing grit), same length out."""
    np = need_numpy()
    x = np.asarray(x)
    if target_rate >= rate:
        return x.copy()
    hold = rate / target_rate
    idx = (np.floor(np.arange(len(x)) / hold) * hold).astype(int)
    return x[np.clip(idx, 0, len(x) - 1)]


def era_crush(x, era, rate=RATE):
    bits, sr = ERAS[era]
    return bitcrush(srcrush(x, sr, rate), bits)


def stereo(x, pan=0.0, width=0.0, rate=RATE, seed=0):
    """Mono -> (n, 2). pan -1..1 (constant power); width adds Haas-delayed decorrelation."""
    np = need_numpy()
    x = np.asarray(x, float)
    a = (pan + 1) * np.pi / 4
    l, r = x * np.cos(a), x * np.sin(a)
    if width:
        d = int(0.012 * rate)
        r = (1 - width) * r + width * np.concatenate([np.zeros(d), r[:-d] if d else r])[:len(r)]
    out = np.stack([l, r], axis=1)
    m = np.max(np.abs(out)) if out.size else 0
    return out / m * 0.89 if m > 1 else out


def write_wav_stereo(path, x, rate=RATE):
    np = need_numpy()
    x = np.asarray(x)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return str(path)
