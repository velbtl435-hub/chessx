**English** | [Português](README.pt.md) | [日本語](README.ja.md)

# chessx_libs.i18n
UI strings in English (default), Portuguese and Japanese (87 keys).

- **Origin:** string table taken from chessx.py v0.5 and expanded for the new packages.
- **License:** same as the ChessX repository.
- **Adapted:** one table of exactly 87 keys per language; language aliases (`jp`, `pt-br`); missing keys fall back to English and then to the key itself.
- **API:** `t(key, **kw)`, `t.set_lang("pt")` (runtime switch), `Translator(lang)`, `STRINGS`, `KEYS`.
- **Self-test:** `python3 -m chessx_libs.i18n` (87 keys per language, equal key sets, set_lang, fallback).
- **Namespaces:** `namespaces/<name>.py` holds keys like `menu.title` (same en/pt/ja key sets); `t("menu.title")` looks in the base table, then namespaces, then English. Add one with `register_namespace(name, table)`.
- Dependencies: Python 3 stdlib only.
