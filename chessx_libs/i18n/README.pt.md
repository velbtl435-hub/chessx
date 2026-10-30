[English](README.md) | **Português** | [日本語](README.ja.md)

# chessx_libs.i18n
Textos da interface em inglês (padrão), português e japonês (84 chaves).

- **Origem:** tabela de textos do chessx.py v0.5, ampliada para os novos pacotes.
- **Licença:** a mesma do repositório ChessX.
- **Adaptações:** uma tabela com exatamente 84 chaves por idioma; apelidos de idioma (`jp`, `pt-br`); chaves ausentes caem para o inglês e depois para a própria chave.
- **API:** `t(chave, **kw)`, `t.set_lang("pt")` (troca em tempo de execução), `Translator(lang)`, `STRINGS`, `KEYS`.
- **Autoteste:** `python3 -m chessx_libs.i18n`.
- **Namespaces:** `namespaces/<nome>.py` guarda chaves como `menu.title` (mesmo conjunto em en/pt/ja); `t("menu.title")` procura na tabela base, depois nos namespaces, depois no inglês. Novo namespace: `register_namespace(nome, tabela)`.
- Dependências: apenas a biblioteca padrão do Python 3.
