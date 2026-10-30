"""Self-test: python -m chessx_libs.i18n"""
from .strings import STRINGS
from .translator import Translator

# Keep in sync with strings.py: every language must have exactly this many keys.
EXPECTED_KEYS = 61


def run() -> bool:
    en = set(STRINGS["en"])
    assert set(STRINGS) == {"en", "pt", "ja"}, STRINGS.keys()
    for lang, table in STRINGS.items():
        assert len(table) == EXPECTED_KEYS, (lang, len(table))
        assert set(table) == en, (lang, en ^ set(table))
        assert all(v.strip() for v in table.values()), lang
    tr = Translator()
    assert tr.lang == "en" and tr("welcome") == STRINGS["en"]["welcome"]
    assert tr.set_lang("pt") == "pt" and tr("welcome") == STRINGS["pt"]["welcome"]
    assert tr.set_lang("jp") == "ja" and tr("welcome") == STRINGS["ja"]["welcome"]
    del_key = "goodbye"
    saved = STRINGS["ja"].pop(del_key)
    try:
        assert tr(del_key) == STRINGS["en"][del_key]  # fallback to English
    finally:
        STRINGS["ja"][del_key] = saved
    assert tr("no_such_key") == "no_such_key"
    assert tr("result_count", n=3) == STRINGS["ja"]["result_count"].format(n=3)
    try:
        tr.set_lang("xx")
        raise AssertionError("unsupported lang accepted")
    except ValueError:
        pass
    return True
