# chessx_libs.reversing (módulo OPCIONAL)

Origem: escrito do zero para o ChessX (2026). Licença: MIT (igual ao repositório).
**Uso defensivo apenas:** análise estática e relatório; o arquivo analisado **nunca é executado**.
Use somente em código próprio ou alvos autorizados. Não faz parte do núcleo do ChessX.

## Recursos
- `detector` — tipo por magic bytes + entropia (indício de compactação/criptografia).
- `formats` — parsers stdlib de cabeçalhos ELF (seções, entrypoint, imports, DT_NEEDED, interpretador),
  PE (máquina, seções, timestamp, .NET) e Mach-O (inclusive universal).
- `origin` — pistas de compilador/empacotador: GCC, Clang, MSVC, Go, Rust, PyInstaller, Nuitka, UPX, Electron etc.
- `strings` — extração ASCII + UTF-16LE com tamanho mínimo e offsets (`strings_with_offsets`), URLs, e-mails, IPs.
- `disasm` — `analyze_binary()`: radare2 (r2pipe) → capstone → decodificador embutido; funções, entrypoint,
  imports, seções e disassembly do entrypoint. Forçar backend: `analyze_binary(p, backend="r2"|"capstone"|"builtin")`. Também `disasm_python`/`disasm_pyc` via `dis`.
- `angr_helper` — `cfg_summary()` (CFGFast) e `reachable(path, "main", "helper")` quando o angr existe.
- `baseconv` — conversão de bases 2..36, hexdump, bindump.
- `detective` — `file_info()` (hashes, mtime) e `investigate()`: pipeline completo → um relatório JSON.

## Dependências opcionais (o módulo funciona só com stdlib)
`capstone`, `pyelftools` (lista de funções), `r2pipe` + binário `radare2` (testado com 6.2.4, .deb oficial), `python-magic`, `lief`, `angr`.
Sem elas, cada etapa cai num fallback ou retorna `{"available": false}`.

## Uso
```bash
python -m chessx_libs.reversing /bin/ls            # resumo legível
python -m chessx_libs.reversing amostra.bin --json # relatório JSON completo
python -m chessx_libs.reversing amostra.bin --angr # inclui resumo de CFG (se angr instalado)
```
```python
from chessx_libs.reversing import investigate
relatorio = investigate("amostra.bin")
```

## Testes
`python -m pytest chessx_libs/reversing/tests` (compila um hello world com gcc; testes de angr são pulados se ausente).

## Modo detetive expandido (#11) — `provenance.py`
- **Hashes:** md5/sha1/sha256 + ssdeep (`ssdeep`/`ppdeep`) e TLSH (`tlsh`) quando instalados; `imphash` para PE.
- **Trilha de origem:** mtime/ctime/atime, dono, permissões, xattrs (`user.xdg.origin.url`, `referrer.url`)
  e sidecars `Zone.Identifier` (Mark-of-the-Web do Windows); linha do tempo com o timestamp de compilação PE.
- **Metadados embutidos:** ELF build-id, ABI tag, `.gnu_debuglink`, `.comment`, Go build ID; PE VersionInfo
  (CompanyName, OriginalFilename…), caminho PDB; PDF Info, PNG tEXt, comentário/entradas ZIP.
- **Recursos embutidos:** carving de ZIP/PDF/PNG/gzip/7z/PE/ELF/PEM após o offset 0.
- **Tabela de imports PE** (`parse_pe_imports`, por nome e ordinal).
- **Entropia por seção** + veredito de empacotamento (UPX, Themida, VMProtect, ASPack, MPRESS…).
- **Fingerprint de toolchain em binários stripped:** nomes de seção, padrões de bytes, imports e nomes de
  função do radare2/angr (Go, Rust, GCC, Clang, MSVC, MinGW, PyInstaller, Nuitka, Nim, Zig, Swift, .NET…), com pontuação.
- `investigate(path)` inclui `report["provenance"]` (desative com `expanded=False`); `--angr` alimenta o fingerprint.

## Segurança: `.pyc` não confiável (auditoria CRYPTO_AUDIT #7)
`disasm_pyc()` é **somente estático**: valida o cabeçalho PEP 552 (magic igual ao do Python atual, flags,
tamanho máx. 16 MiB, payload tipo código) e faz o `marshal` num **subprocesso isolado** (`python -I -S`,
limite de memória, timeout de 10 s). O objeto de código **nunca é executado**. Falha/crash/timeout →
`PycError` (subclasse de `ValueError`) com mensagem clara, sem derrubar o processo principal.
