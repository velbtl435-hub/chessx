"""Voice language selection: en (default), pt (pt-BR), ja. Follows the ChessX i18n setting.

Priority: voice.set_lang(...) > bound Translator (bind_translator(app.t)) > global chessx_libs.i18n.t
> env CHESSX_LANG > 'en'.
"""
import os

SUPPORTED = ("en", "pt", "ja")
ALIASES = {"jp": "ja", "ja-jp": "ja", "pt-br": "pt", "pt_br": "pt", "br": "pt", "en-us": "en", "en_us": "en"}
LOCALE = {"en": "en-US", "pt": "pt-BR", "ja": "ja-JP"}
_state = {"lang": None, "translator": None}


def normalize(lang):
    """'pt-BR' -> 'pt', 'jp' -> 'ja'. Unknown -> ValueError."""
    l = ALIASES.get(str(lang).lower(), str(lang).lower()).split("-")[0].split("_")[0]
    if l not in SUPPORTED:
        raise ValueError("unsupported voice language: %r (use en/pt/ja)" % lang)
    return l


def set_lang(lang):
    """Force the voice language (None = follow i18n again)."""
    _state["lang"] = None if lang is None else normalize(lang)
    return _state["lang"]


def bind_translator(translator):
    """Follow an i18n Translator instance (e.g. the app's self.t) so `lang` switches apply to voice too."""
    _state["translator"] = translator


def current_lang(lang=None):
    for cand in (lang, _state["lang"], getattr(_state["translator"], "lang", None)):
        if cand:
            return normalize(cand)
    try:
        from chessx_libs.i18n import t
        if getattr(t, "lang", None) and t.lang != "en":
            return normalize(t.lang)
    except Exception:
        pass
    try:
        return normalize(os.environ.get("CHESSX_LANG") or "en")
    except ValueError:
        return "en"
