"""Tiny i18n: English default, Portuguese, Japanese. Usage: t('welcome'); t.set_lang('pt')."""
from .strings import STRINGS

KEYS = tuple(STRINGS["en"])
ALIASES = {"jp": "ja", "pt-br": "pt", "pt_br": "pt", "en-us": "en"}


class Translator:
    def __init__(self, lang: str = "en"):
        self.lang = "en"
        self.set_lang(lang)

    def set_lang(self, lang: str) -> str:
        lang = ALIASES.get(lang.lower(), lang.lower())
        if lang not in STRINGS:
            raise ValueError(f"unsupported language: {lang!r} (use en/pt/ja)")
        self.lang = lang
        return lang

    def __call__(self, key: str, **kw) -> str:
        text = STRINGS[self.lang].get(key) or STRINGS["en"].get(key, key)
        return text.format(**kw) if kw else text

    def missing(self):
        return {l: [k for k in KEYS if k not in STRINGS[l]] for l in STRINGS}


t = Translator()
