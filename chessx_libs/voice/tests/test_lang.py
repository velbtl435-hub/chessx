import pytest
from chessx_libs.voice import lang, stt
from chessx_libs.i18n import Translator


@pytest.fixture(autouse=True)
def reset():
    lang._state.update(lang=None, translator=None); yield; lang._state.update(lang=None, translator=None)


def test_normalize():
    assert [lang.normalize(x) for x in ("pt-BR", "jp", "EN-us")] == ["pt", "ja", "en"]
    with pytest.raises(ValueError):
        lang.normalize("xx")


def test_follows_translator_and_override(monkeypatch):
    monkeypatch.delenv("CHESSX_LANG", raising=False)
    assert lang.current_lang() == "en"
    t = Translator("en"); lang.bind_translator(t); t.set_lang("ja")
    assert lang.current_lang() == "ja"
    lang.set_lang("pt-BR")
    assert lang.current_lang() == "pt" and lang.current_lang("en") == "en"


def test_stt_uses_language_model(tmp_path, monkeypatch):
    monkeypatch.setattr(stt, "MODEL_DIR", str(tmp_path))
    (tmp_path / "vosk-model-small-ja-0.22").mkdir()
    lang.set_lang("ja")
    assert stt.find_model(lang.current_lang()).endswith("ja-0.22")
