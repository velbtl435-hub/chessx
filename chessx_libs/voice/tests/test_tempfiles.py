import glob, os, pathlib, tempfile, wave
import numpy as np
from chessx_libs.voice import stt, tts

VOICE = pathlib.Path(__file__).resolve().parents[1]


def test_no_insecure_mktemp():
    bad = [str(p) for p in VOICE.rglob("*.py") if p.name != "test_tempfiles.py" and "mktemp(" in p.read_text()]
    assert bad == []


def _leftovers():
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "chessx_*")))


def test_resample_tempfile_cleaned(tmp_path, monkeypatch):
    before = _leftovers()
    src = str(tmp_path / "a.wav")
    with wave.open(src, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(np.zeros(4410 * 2, dtype="<i2").tobytes())
    monkeypatch.setattr(stt.shutil, "which", lambda b: None)
    out, is_tmp = stt._to_16k_mono(src)
    assert is_tmp and os.path.basename(out).startswith("chessx_")
    stt._rm(out); stt._rm(out)  # idempotent, ignores FileNotFoundError
    assert _leftovers() == before


def test_failed_resample_removes_temp(tmp_path, monkeypatch):
    before = _leftovers()
    bad = tmp_path / "x.wav"; bad.write_bytes(b"not a wav")
    monkeypatch.setattr(stt.shutil, "which", lambda b: None)
    assert stt._to_16k_mono(str(bad)) == (str(bad), False)
    assert _leftovers() == before


def test_speak_and_download_clean_up(monkeypatch):
    before = _leftovers()
    monkeypatch.setattr(tts, "_player", lambda: "aplay")
    monkeypatch.setattr(tts, "save_to_file", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    try:
        tts.speak("oi", "pt")
    except RuntimeError:
        pass
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlretrieve", lambda *a: (_ for _ in ()).throw(OSError("offline")))
    assert stt.download_model("pt", dest=tempfile.mkdtemp()) is None
    assert _leftovers() == before
