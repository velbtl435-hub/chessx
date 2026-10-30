"""Robot mode: turn any rendered speech WAV into a distinct synthetic robot voice (numpy, optional).

Chain: mono -> pitch shift (resample) -> ring modulation (carrier ~ 55 Hz) -> metallic comb echo
-> bitcrush (bit depth + sample-rate reduction) -> normalize. Pure functions, testable headless.
"""
import wave

DEFAULTS = {"carrier_hz": 55.0, "pitch": 0.9, "bits": 6, "downsample": 3, "comb_ms": 9.0, "comb_gain": 0.5}


def ring_modulate(x, rate, carrier_hz=55.0):
    import numpy as np
    t = np.arange(len(x)) / float(rate)
    return x * np.sin(2 * np.pi * carrier_hz * t)


def bitcrush(x, bits=6, downsample=3):
    import numpy as np
    levels = 2 ** (int(bits) - 1)
    y = np.round(x * levels) / levels
    if downsample > 1:
        y = np.repeat(y[::int(downsample)], int(downsample))[:len(x)]
    return y


def pitch_shift(x, factor=0.9):
    """factor<1 lowers pitch (and slows slightly); simple resampling, no deps beyond numpy."""
    import numpy as np
    if factor == 1 or not len(x):
        return x
    n = max(1, int(len(x) / factor))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def comb(x, rate, ms=9.0, gain=0.5):
    import numpy as np
    d = max(1, int(rate * ms / 1000.0))
    y = np.copy(x)
    y[d:] += gain * x[:-d]
    return y


def robotize(x, rate, **opts):
    """x: float array in [-1, 1]. Returns processed float array in [-1, 1]."""
    import numpy as np
    o = dict(DEFAULTS, **opts)
    y = pitch_shift(np.asarray(x, dtype=np.float64), o["pitch"])
    y = 0.6 * ring_modulate(y, rate, o["carrier_hz"]) + 0.4 * y  # keep some dry signal for intelligibility
    y = comb(y, rate, o["comb_ms"], o["comb_gain"])
    y = bitcrush(y / (np.max(np.abs(y)) or 1.0), o["bits"], o["downsample"])
    peak = np.max(np.abs(y)) or 1.0
    return 0.9 * y / peak


def robotize_wav(src, dst=None, **opts):
    """Apply robot effect to a PCM WAV file in place (or into dst). Returns dst path, or None if numpy missing."""
    try:
        import numpy as np
    except Exception:
        return None
    dst = dst or src
    with wave.open(src, "rb") as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        return None
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64).reshape(-1, ch).mean(axis=1) / 32768.0
    y = robotize(x, rate, **opts)
    with wave.open(dst, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes((y * 32767).astype("<i2").tobytes())
    return dst
