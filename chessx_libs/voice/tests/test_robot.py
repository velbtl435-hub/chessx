import wave
import numpy as np
from chessx_libs.voice import robot, tts


def test_robotize_changes_signal_and_stays_bounded():
    rate = 16000
    x = 0.5 * np.sin(2 * np.pi * 220 * np.arange(rate) / rate)
    y = robot.robotize(x, rate)
    assert np.max(np.abs(y)) <= 1.0 and len(y) > len(x)  # pitch down lengthens
    assert len(np.unique(np.round(y, 6))) < 200  # bitcrushed: few levels


def test_save_to_file_robot(monkeypatch, tmp_path):
    def render(b, text, path, lang):
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes((np.sin(np.arange(8000) / 4) * 9000).astype("<i2").tobytes())
        return True
    monkeypatch.setattr(tts, "available_backends", lambda lang="en": ["espeak-ng"])
    monkeypatch.setattr(tts, "_render", render)
    out = str(tmp_path / "r.wav")
    assert tts.save_to_file("beep", out, "en", robot=True) == "espeak-ng"
    with wave.open(out) as w:
        assert w.getnframes() > 8000


def test_toggle_and_cli(tmp_path, monkeypatch):
    old = tts.robot_mode()
    assert tts.robot_mode(True) is True and tts._binary_cmd("espeak-ng", "x", "pt")[2].endswith("+klatt3")
    tts.robot_mode(old)
    from chessx_libs.voice.__main__ import main
    seen = {}
    monkeypatch.setattr(tts, "save_to_file", lambda t, o, l, robot=None: seen.update(l=l, r=robot) or "x")
    assert main(["olá", "--lang", "pt-BR", "--robot", "-o", str(tmp_path / "a.wav")]) == 0
    assert seen == {"l": "pt", "r": True}
