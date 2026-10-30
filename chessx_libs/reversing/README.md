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

## Reversão de programa (#24 / master §14.2)
`reversal_summary` (chave **nova, sempre por último** em `investigate()`) reconstrói como o binário
foi construído — **somente estático**:

| Campo | Conteúdo |
|---|---|
| `build_settings` | PIE, RELRO, NX, canary, FORTIFY, stripped, static/dynamic, debug |
| `toolchain` | linguagem/compilador/linker/runtime + versões (Go buildinfo, rustc, GCC/clang `.comment`, Rich MSVC, PE linker, PyInstaller/Nuitka/.NET) |
| `capabilities` | bibliotecas + grupos (network/crypto/process/file/…) e delay-load PE |
| `packing` | reutiliza o veredito de `provenance` |
| `cfg` | contagem/funções maiores/entry→main quando r2 ou angr existem (senão conf baixa) |
| `narrative_pt` | parágrafo em português |
| `confidence` / `evidence` | notas por campo |

Fallback stdlib: sem r2/capstone/angr o resumo ainda sai (headers + strings + `.comment`/Rich).
CLI: seção `--- Reversão (#24) ---` no modo texto.

## Triagem defensiva de malware (#25)

> **Aviso: estas heurísticas NÃO são um antivírus.** São sinais estáticos para priorizar
> análise humana. Um `clean` não prova que o arquivo é seguro; um `likely_malicious`
> não prova que é malware. Todo veredito vem sempre com `score` e `evidence`.

- **Só estático:** a amostra **nunca** é executada; sem detonation, sem rede, sem upload a terceiros.
- Spec: `docs/specs/MALWARE_TRIAGE.md`.
- Saída: chave `triage` **no fim** de `investigate()` (depois de `reversal_summary`):
  `score` (0–100), `verdict` (`clean` 0–14 / `suspicious` 15–39 / `likely_malicious` ≥40),
  `evidence` (resumo), `matched[]` (id, severity, weight, engine, evidence com offsets),
  `engines` (chessx / yara), `allowlisted`, `limits`, `errors`.
- CLI: `python -m chessx_libs.reversing <arquivo>` mostra a seção `--- Triagem ---`;
  `python -m chessx_libs.reversing.triage <arquivo> [--json] [--rules DIR] [--list-rules]`.
- Regras embutidas: `rules/builtin/*.toml` (`cx.*`, MIT): packing/entropia, combos de imports
  (injeção, persistência, anti-debug, crypto+rede, LSASS), wrappers, strings tipo C2
  (URL de painel, IP:porta, User-Agent antigo, `.onion`) e `cx.test.eicar` (só por hash).
- Regras extras: `CHESSX_TRIAGE_RULES=dir1:dir2` (TOML/JSON ChessX e, se `yara-python`
  estiver instalado, `.yar`/`.yara`; sem includes, timeout 5 s, scan até 32 MiB).
  Sem `yara-python` tudo funciona com `engines.yara=false`.
- Allowlist: `rules/allowlist.sha256` + `CHESSX_TRIAGE_ALLOWLIST=arquivo`; gerar com
  `python -m chessx_libs.reversing.triage --build-allowlist /bin /usr/bin > minha.sha256`.

### Testes e métricas
- Só binários **sintéticos** (compilados no teste, nunca executados) e EICAR **montado em
  tempo de teste** a partir de fragmentos, gravado em arquivo temporário e apagado ao fim —
  a string EICAR não existe no repositório (há teste que verifica isso).
- Corpus de falso positivo `/bin` + `/usr/bin`: opcional, pulado no Windows ou se os
  diretórios não existirem; amostra pequena por padrão, corpus inteiro com
  `CHESSX_TRIAGE_FP=1`. Só verifica "nenhum `likely_malicious` em binário allowlisted" e
  razão frouxa (≤10 %), nunca contagens exatas.
- Medição local (2026-10-30, Debian, 60 binários de `/usr/bin`): 0 % `suspicious`/
  `likely_malicious`; p95 ≈ 0,5 s por arquivo (investigate completo, sem YARA).

### Pacotes de regras de terceiros
| Fonte | Licença | Uso no ChessX |
|---|---|---|
| ChessX `cx.*` | MIT | embutido |
| ReversingLabs `reversinglabs-yara-rules` | MIT | opcional (download manual; manter LICENSE/NOTICE) |
| Neo23x0 `signature-base` | DRL 1.1 | opcional (download manual); `author` preservado no match |
| Yara-Rules `rules` | GPL-2.0 | só via caminho local do usuário; nunca embutido |
| Elastic `protections-artifacts` | Elastic License 2.0 | evitado |
