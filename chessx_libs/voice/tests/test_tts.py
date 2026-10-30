import types
from chessx_libs.voice import tts

V = lambda id, name, langs=(): types.SimpleNamespace(id=id, name=name, languages=list(langs))
VOICES = [
    V("HKEY\\TTS_MS_EN-US_ZIRA_11.0", "Microsoft Zira Desktop - English (United States)", ["en_US"]),
    V("pt-br", "espeak Portuguese (Brazil)", ["pt-br"]),
    V("mb-br1", "mbrola br1 Portuguese", ["pt"]),
    V("com.apple.voice.premium.pt-BR.Luciana", "Luciana (Premium)", ["pt_BR"]),
    V("ja", "Kyoko", ["ja_JP"]),
]


def test_pick_best_voice_per_language():
    assert tts.pick_voice(VOICES, "pt").name.startswith("Luciana")
    assert tts.pick_voice(VOICES[:3], "pt-BR").id == "mb-br1"  # mbrola beats plain espeak
    assert tts.pick_voice(VOICES, "en").name.startswith("Microsoft Zira")
    assert tts.pick_voice(VOICES, "ja").name == "Kyoko"
    assert tts.pick_voice(VOICES[:1], "ja") is None


def test_configure_clamps():
    old = dict(tts.CONFIG)
    try:
        assert tts.configure(rate=120, volume=3)["volume"] == 1.0
        assert tts._binary_cmd("espeak-ng", "oi", "pt")[4] == "120"
    finally:
        tts.CONFIG.update(old)


def test_degrades_to_pyttsx3_and_noop(monkeypatch):
    monkeypatch.setattr(tts, "_piper_bin", lambda: None)
    monkeypatch.setattr(tts, "_edge_ok", lambda: False)
    monkeypatch.setattr(tts.shutil, "which", lambda b: None)
    monkeypatch.setattr(tts.sys, "platform", "linux")
    monkeypatch.setattr(tts, "_pyttsx3_engine", lambda: object())
    assert tts.available_backends("pt") == ["pyttsx3"]
    monkeypatch.setattr(tts, "_pyttsx3_engine", lambda: None)
    assert tts.available_backends("pt") == ["noop"]
    assert tts.speak("olá", "pt") == "noop"


def test_piper_preferred_when_installed(monkeypatch, tmp_path):
    m = tmp_path / "pt_BR-faber-medium.onnx"; m.write_text("x")
    monkeypatch.setenv("CHESSX_PIPER_MODEL_PT", str(m))
    monkeypatch.setattr(tts, "_piper_bin", lambda: "/usr/bin/piper")
    assert tts.available_backends("pt")[0] == "piper"


def test_save_to_file_falls_through(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "available_backends", lambda lang="en": ["piper", "espeak-ng"])
    def render(b, text, path, lang):
        if b == "piper":
            raise OSError("boom")
        open(path, "wb").write(b"\0" * 100); return True
    monkeypatch.setattr(tts, "_render", render)
    assert tts.save_to_file("oi", str(tmp_path / "o.wav"), "pt") == "espeak-ng"
