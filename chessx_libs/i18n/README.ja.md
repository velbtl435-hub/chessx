[English](README.md) | [Português](README.pt.md) | **日本語**

# chessx_libs.i18n
英語（デフォルト）、ポルトガル語、日本語の UI 文字列（84 キー）。

- **由来:** chessx.py v0.5 の文字列テーブルを新パッケージ向けに拡張。
- **ライセンス:** ChessX リポジトリと同じ。
- **変更点:** 各言語ちょうど 84 キー。言語エイリアス（`jp`、`pt-br`）。欠けているキーは英語、次にキー名そのものにフォールバック。
- **API:** `t(key, **kw)`、`t.set_lang("ja")`（実行時に切り替え）、`Translator(lang)`、`STRINGS`、`KEYS`。
- **セルフテスト:** `python3 -m chessx_libs.i18n`
- **名前空間:** `namespaces/<名前>.py` に `menu.title` のようなキーを置く（en/pt/ja で同じキー集合）。`t("menu.title")` は基本テーブル、名前空間、英語の順に探す。追加は `register_namespace(名前, テーブル)`。
- 依存関係: Python 3 標準ライブラリのみ。
