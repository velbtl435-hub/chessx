import math, os, shutil, struct, subprocess, sys, tempfile, wave

RATE = 22050
# effect -> list of (freq_hz, duration_s)
EFFECTS = {
    "boot": [(262, .08), (330, .08), (392, .08), (523, .16)],
    "move": [(880, .03)], "select": [(660, .05), (990, .05)],
    "error": [(220, .12), (165, .2)], "success": [(523, .07), (659, .07), (784, .14)],
    "found": [(1047, .05), (1319, .08)], "alert": [(988, .1), (0, .05), (988, .1)],
}


def _player():
    if sys.platform == "win32":
        return "winsound"
    for p in ("aplay", "paplay", "afplay", "ffplay"):
        if shutil.which(p):
            return p
    return "noop"


PLAYER = _player()


def synth(name: str, volume: float = 0.4) -> bytes:
    frames = bytearray()
    for freq, dur in EFFECTS[name]:
        n = int(RATE * dur)
        for i in range(n):
            env = min(1.0, i / 200, (n - i) / 200)  # click-free envelope
            v = volume * env * math.sin(2 * math.pi * freq * i / RATE) if freq else 0.0
            frames += struct.pack("<h", int(v * 32767))
    return bytes(frames)


def save_wav(name: str, path: str) -> str:
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(synth(name))
    return path


def play(name: str, enabled: bool = True) -> str:
    """Play effect; returns player used. Never raises; 'noop' when silent."""
    if not enabled or PLAYER == "noop" or name not in EFFECTS or os.environ.get("CHESSX_MUTE"):
        return "noop"
    try:
        path = save_wav(name, os.path.join(tempfile.gettempdir(), f"chessx_{name}.wav"))
        if PLAYER == "winsound":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            args = [PLAYER, "-nodisp", "-autoexit", "-loglevel", "quiet", path] if PLAYER == "ffplay" else [PLAYER, path]
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return PLAYER
    except Exception:
        return "noop"
