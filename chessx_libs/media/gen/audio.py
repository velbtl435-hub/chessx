"""WAV tone/sequence synthesis (numpy + stdlib wave) incl. chess move sounds."""
import wave
from ._deps import need_numpy

RATE = 22050
CHESS_SOUNDS = {  # name -> list of (freq Hz, seconds); freq 0 = silence
    "move": [(660, 0.06)], "capture": [(440, 0.05), (330, 0.08)],
    "check": [(880, 0.08), (0, 0.03), (880, 0.08)], "castle": [(523, 0.06), (659, 0.06)],
    "promote": [(523, 0.07), (659, 0.07), (784, 0.1)], "illegal": [(150, 0.2)],
    "game_end": [(784, 0.15), (659, 0.15), (523, 0.3)],
}


def tone(freq, seconds, rate=RATE, volume=0.5, wave_shape="sine", fade=0.005):
    np = need_numpy()
    t = np.arange(int(rate * seconds)) / rate
    if freq <= 0:
        return np.zeros_like(t)
    ph = 2 * np.pi * freq * t
    y = {"sine": np.sin(ph), "square": np.sign(np.sin(ph)),
         "saw": 2 * (t * freq - np.floor(0.5 + t * freq))}[wave_shape] * volume
    n = min(int(rate * fade), len(y) // 2)
    if n:
        ramp = np.linspace(0, 1, n)
        y[:n] *= ramp
        y[-n:] *= ramp[::-1]
    return y


def sequence(notes, rate=RATE, **kw):
    np = need_numpy()
    parts = [tone(f, d, rate, **kw) for f, d in notes]
    return np.concatenate(parts) if parts else np.zeros(0)


def write_wav(path, samples, rate=RATE):
    np = need_numpy()
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return str(path)


def chess_sound(name, path, rate=RATE, **kw):
    if name not in CHESS_SOUNDS:
        raise KeyError(f"unknown sound {name!r}; choose from {sorted(CHESS_SOUNDS)}")
    return write_wav(path, sequence(CHESS_SOUNDS[name], rate, **kw), rate)
