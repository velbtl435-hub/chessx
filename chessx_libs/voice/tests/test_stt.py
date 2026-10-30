import os, wave, types, json
import numpy as np
import pytest
from chessx_libs.voice import stt


def _wav(path, rate=44100, ch=2, secs=0.1):
    a = (np.sin(np.arange(int(rate * secs)) / 5) * 8000).astype("<i2")
    a = np.repeat(a, ch)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate); w.writeframes(a.tobytes())
    return str(path)


def test_norm_lang():
    assert stt.norm_lang("pt-BR") == "pt" and stt.norm_lang("jp") == "ja" and stt.norm_lang(None) == "en"


def test_find_model_per_language(tmp_path, monkeypatch):
    monkeypatch.setattr(stt, "MODEL_DIR", str(tmp_path))
    monkeypatch.delenv("CHESSX_VOSK_MODEL", raising=False)
    (tmp_path / "vosk-model-small-en-us-0.15").mkdir()
    assert stt.find_model("pt") is None  # never falls back to an English model
    (tmp_path / "vosk-model-small-pt-0.3").mkdir()
    assert stt.find_model("pt-BR").endswith("vosk-model-small-pt-0.3")
    monkeypatch.setenv("CHESSX_VOSK_MODEL_PT", str(tmp_path / "vosk-model-small-en-us-0.15"))
    assert stt.find_model("pt").endswith("en-us-0.15")


def test_resample_to_16k_mono(tmp_path, monkeypatch):
    monkeypatch.setattr(stt.shutil, "which", lambda b: None)  # force numpy path
    out, tmp = stt._to_16k_mono(_wav(tmp_path / "a.wav"))
    assert tmp and stt._is_16k_mono(out)


def test_missing_model(tmp_path, monkeypatch):
    monkeypatch.setattr(stt, "MODEL_DIR", str(tmp_path))
    monkeypatch.delenv("CHESSX_VOSK_MODEL", raising=False)
    monkeypatch.setattr(stt, "_vosk", lambda: types.SimpleNamespace())
    monkeypatch.setattr(stt, "_sr", lambda: None)
    f = _wav(tmp_path / "a.wav")
    assert stt.transcribe_file(f, lang="pt") is None
    with pytest.raises(stt.ModelNotFound):
        stt.transcribe_file(f, lang="pt", strict=True)


def test_utf8_accents_with_fake_vosk(tmp_path, monkeypatch):
    class Rec:
        def __init__(self, m, r): assert r == 16000
        def AcceptWaveform(self, d): return False
        def FinalResult(self): return json.dumps({"text": "cavalo para é cinco ação"}, ensure_ascii=False)
    fake = types.SimpleNamespace(Model=lambda p: object(), KaldiRecognizer=Rec)
    monkeypatch.setattr(stt, "_vosk", lambda: fake)
    (tmp_path / "m").mkdir()
    assert stt.transcribe_file(_wav(tmp_path / "a.wav"), model_path=str(tmp_path / "m"), lang="pt") \
        == "cavalo para é cinco ação"
