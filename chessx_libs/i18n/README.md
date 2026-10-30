# chessx_libs.i18n
UI strings in English, Portuguese and Japanese (61 keys).

- **Origin:** string table taken from chessx.py v0.5 and expanded for the new packages.
- **License:** same as the ChessX repository.
- **Adapted:** one table of exactly 61 keys per language; language aliases (`jp`, `pt-br`); missing keys fall back to English and then to the key itself.
- **API:** `t(key, **kw)`, `Translator(lang)`, `STRINGS`, `KEYS`.
- Dependencies: Python 3 stdlib only.
