# chessx_libs.detective
Origin: written for ChessX (2026). License: MIT. Extends reversing.detective (kept for compat).
Collects: fs metadata, type/entropy, hashes, PNG tEXt, PDF /Info, ZIP/OOXML core props, JPEG EXIF strings,
xattrs (user.xdg.origin.url), Windows Zone.Identifier; builds a provenance chain and reverse-search links
(VirusTotal, DuckDuckGo, archive.org -- links only, nothing is uploaded). Stdlib only.

Delegação (2026-10): hashes, PDF/PNG/OOXML/EXIF, xattrs e carving de payloads embutidos agora vêm de
`chessx_libs.reversing.provenance` (implementação única). A API pública não mudou; `investigate()` ganhou a
chave aditiva `embedded_payloads` (última). Se `reversing` não importar, há fallback stdlib (hashes + metadados
de sistema de arquivos). Testes: `python -m pytest chessx_libs/detective/tests`
(`CHESSX_DETECTIVE_REF=<dir com investigate.py antigo>` ativa a comparação com a versão anterior).
