**English** | [Português](README.pt.md) | [日本語](README.ja.md)

# chessx_libs.i18n
UI strings in English (default), Portuguese and Japanese (84 keys).

- **Origin:** string table taken from chessx.py v0.5 and expanded for the new packages.
- **License:** same as the ChessX repository.
- **Adapted:** one table of exactly 84 keys per language; language aliases (`jp`, `pt-br`); missing keys fall back to English and then to the key itself.
- **API:** `t(key, **kw)`, `t.set_lang("pt")` (runtime switch), `Translator(lang)`, `STRINGS`, `KEYS`.
- **Self-test:** `python3 -m chessx_libs.i18n` (84 keys per language, equal key sets, set_lang, fallback).
- Dependencies: Python 3 stdlib only.
