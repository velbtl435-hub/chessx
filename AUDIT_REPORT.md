# AUDIT_REPORT — ChessX (auditoria completa, só relatório)

- **Data:** 2026-10-30 (America/Sao_Paulo, UTC-3)
- **Commit auditado (`main`):** `bbf46654ea568bfa8c12d00aa423825491809d69` (commit de 2026-10-30 11:52 UTC-3). Outros agentes enviam ao `main` em paralelo; commits posteriores não estão cobertos.
- **Escopo:** todo o repositório, exceto o código de terceiros em `c/capstone/vendor/` (capstone 5.0.7, só a integração foi revisada).
- **Nada foi corrigido.** Commit com prefixo `t1(audit):`.

## Ferramentas e versões

Python 3.13.5 · ruff 0.17.3 (E9,F,B,S) · bandit 1.9.4 · vulture 2.16 (≥80%) · mypy 2.4.1 (leniente) · pip-audit 2.10.1 · coverage 7.17.0 · pytest 9.2.0 · yamllint 1.38.0 · Node 24.22.1 / npm audit · TypeScript 5.9.3 (`tsc --noEmit`) · cargo 1.99.1 · gcc 14.2.0 · wasi-sdk clang 23.1.0 · varredura de segredos por regex (estilo gitleaks) · verificação de links relativos em Markdown · histórico de Actions pela API pública do GitHub. Sem cppcheck/clang-analyzer na máquina: o C foi revisado à mão (shims em `c/search`, `c/capstone`, `c/hello_fusion`) mais o build com os avisos do Makefile.

## Resultados dos testes

| Execução | Resultado |
|---|---|
| `python3 chessx.py --selftest` | 18/18 ok (exit 0) |
| `pytest tests chessx_libs` (3 vezes) | 351 passed, 15 skipped, 210 subtests, idêntico nas 3 (~35 s) |
| `tests/` | 231 passed, 10 skipped |
| `chessx_libs/detective` · `media` · `reversing` · `sounds` · `voice` | 5 ok/1 skip · 21 ok · 34 ok/4 skip · 40 ok (+210 subtests) · 20 ok |
| Outros pacotes de `chessx_libs` | sem pasta de testes própria; cobertos por `tests/` |
| `CHESSX_NATIVE=0 pytest tests/test_native.py` | 7 passed |
| `make -C c all test` | ok: hello_fusion 15 vetores × 5 backends, search 25 × 4, capstone 14 × 5, todos ALL MATCH |
| `web`: `tsc --noEmit` | ok · `npm audit`: 1 high (postcss), 1 moderate (next) |
| `desktop`: `npm audit` | 0 vulnerabilidades · `cargo check`: falha por sidecar ausente (BUG-08) |
| Cobertura (coverage.py, total) | 81% de 10.289 statements. Por pacote: agents 87, audit 0, bases 94, browser 68, chess_ai 0, crypto 85, detective 90, i18n 42, interface 51, mathx 81, media 93, menu 41, native 89, osint 92, pixelart 93, reversing 80, scheduler 0, search 49, sounds 95, tamagox 94, voice 81, windows 0 |

## Resumo por severidade e área

| Área | CRÍTICO | ALTO | MÉDIO | BAIXO | INFO | Total |
|---|---|---|---|---|---|---|
| 1. Bugs de código (Python, TS, C, Rust, YAML, JSON, Markdown) | 0 | 0 | 0 | 2 | 7 | 9 |
| 2. Cibersegurança | 0 | 0 | 8 | 4 | 3 | 15 |
| 3. Arquitetura | 0 | 0 | 0 | 2 | 1 | 3 |
| 4. Performance | 0 | 0 | 0 | 1 | 3 | 4 |
| 5. Testes | 0 | 0 | 2 | 2 | 2 | 6 |
| 6. Documentação | 0 | 0 | 1 | 2 | 2 | 5 |
| 7. i18n | 0 | 0 | 0 | 2 | 1 | 3 |
| 8. CI/CD | 0 | 0 | 3 | 2 | 1 | 6 |
| 9. OSINT e sandbox | 0 | 0 | 0 | 3 | 2 | 5 |
| 10. Criptografia | 0 | 0 | 1 | 4 | 2 | 7 |
| **Total** | **0** | **0** | **15** | **24** | **24** | **63** |

Nenhum achado CRÍTICO ou ALTO confirmado. O `npm audit` classifica o postcss como *high*, mas aqui está em MÉDIO (SEC-09) porque só roda no build. Achados que só uma ferramenta apontou, sem confirmação manual, estão em INFO.

Times: **Time 1** = search, reversing, crypto, bases, media, sounds, interface, detective, browser, pixelart, menu, osint, geoforensics, native, c/, chessx.py, listas master/priority. **Time 2/3** = voice/, mathx/, agents/, tamagox/, web/, desktop/, i18n/.

## 1. Bugs de código (Python, TS, C, Rust, YAML, JSON, Markdown)

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| BUG-01 | BAIXO | chessx_libs/osint/e2e.py:18 | Variável `before` atribuída e nunca usada (ruff F841): a checagem que ela devia alimentar não existe. | O E2E pode passar sem verificar o que pretendia (ex.: delta de requisições/cache). | Usar `before` numa asserção ou remover. | Time 1 (osint) |
| BUG-02 | BAIXO | chessx_libs/mathx/steps.py:365 | `set(sp.solveset(...)) if True else set()`: ramo `else` inalcançável (vulture 100%). | Resto de depuração; esconde intenção. | Remover o condicional. | Time 2/3 (mathx) |
| BUG-03 | INFO | chessx_libs/reversing/disasm.py:183-189 | `try/except/else` em que o `try` sempre retorna; o `else: err = None` é inalcançável (vulture). | Só código morto. | Simplificar. | Time 1 (reversing) |
| BUG-04 | INFO | chessx_libs/sounds/cabinet.py:9, :56; sounds/dsp.py:112; sounds/retro/sid.py:110; sounds/synthwave.py:31 | Variáveis locais não usadas (`np`, `pos`), ruff F841. | Ruído. | Remover. | Time 1 (sounds) |
| BUG-05 | INFO | chessx_libs/** (107 ocorrências fora de testes) | Imports não usados (ruff F401). | Ruído; carga de import desnecessária. | `ruff check --select F401 --fix` após revisão. | Vários |
| BUG-06 | INFO | chessx_libs/mathx/core.py:67; mathx/langs.py:150 | `raise` dentro de `except` sem `from` (B904). | Perde a causa original no traceback. | `raise MathError(...) from e`. | Time 2/3 (mathx) |
| BUG-07 | INFO | chessx_libs (mypy, modo leniente) | mypy reportou 158 erros em 45 arquivos; os amostrados (i18n/selftest.py:40, media/gen/board.py:16, sounds/sfx.py:56) são falsos positivos de inferência ou plataforma. Nenhum confirmado como bug real. | Baixo; só ferramenta. | Adotar mypy gradual por pacote. | Vários |
| BUG-08 | INFO | desktop/src-tauri (cargo check) | `cargo check` falha: `resource path binaries/chessx-engine-x86_64-unknown-linux-gnu doesn't exist` (sidecar precisa ser gerado antes). | Build Rust não verificável sem o passo de empacotar o engine. | Documentar/automatizar o passo (desktop/scripts) antes do `cargo check`, ou CI do desktop. | Time 2/3 (desktop) |
| BUG-09 | INFO | web/ (tsc --noEmit), *.json, workflows | `tsc --noEmit` limpo (TS 5.9.3); todos os JSON versionados válidos; yamllint (relaxed) só avisos de estilo. | — | — | — |

## 2. Cibersegurança

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| SEC-01 | MÉDIO | chessx_libs/browser/fetch.py:22-37 | O navegador ASCII aceita qualquer URL com `://`. Sem `requests`, o fallback `urllib.request.urlopen` aceita `file://` (lê arquivos locais) e não bloqueia IPs privados/loopback/169.254.169.254. | Leitura de arquivo local e SSRF para serviços internos/metadata de nuvem quando a URL vem de link clicado numa página. | Allow-list de esquemas (`http`,`https`), resolver host e recusar IPs privados/link-local/loopback, inclusive após redirect. | Time 1 (browser) |
| SEC-02 | MÉDIO | chessx_libs/media/downloader.py:42 | `urlopen(url)` sem restrição de esquema (`file://`, `ftp://`) nem de destino privado. | SSRF/leitura local copiada para a pasta de downloads. | Mesmo filtro de SEC-01, compartilhado num helper único. | Time 1 (media) |
| SEC-03 | BAIXO | chessx_libs/media/downloader.py:27 | `max_bytes=None` por padrão: download ilimitado quando o servidor não manda Content-Length. | Enchimento de disco. | Default finito (ex.: 512 MB) e checar o tamanho acumulado no loop. | Time 1 (media) |
| SEC-04 | MÉDIO | chessx_libs/voice/stt.py:101-103 | Modelo Vosk baixado (`urlretrieve`) e extraído sem checksum/assinatura. `zipfile.extractall` já neutraliza `..`/caminho absoluto, então zip-slip está mitigado. | Supply chain: modelo trocado no servidor/espelho é instalado sem verificação. | Fixar SHA-256 por modelo em `VOSK_MODELS` e verificar antes de extrair. | Time 2/3 (voice) |
| SEC-05 | MÉDIO | web/app/page.tsx:66, :95 (fonte: web/lib/search.ts:23-26, :36, :44) | `window.open(r.url)` com URL vinda de HTML/JSON raspado de buscadores, sem validar esquema. | Resultado malicioso com `javascript:`/`data:` pode executar script ou phishing ao abrir. | Aceitar só `http(s):` (via `new URL()`) no parser e antes de abrir. | Time 2/3 (web) |
| SEC-06 | BAIXO | web/app/page.tsx:48 | Export CSV não escapa vírgulas/aspas na URL nem prefixos `= + - @` (CSV/formula injection). | Planilha executa fórmula vinda de título/URL de terceiros. | Quotar todos os campos e prefixar `'` em células que começam com `=+-@`. | Time 2/3 (web) |
| SEC-07 | MÉDIO | web/app/api/search/route.ts:3-8 | Endpoint público sem autenticação nem rate limit dispara até 30 resultados por consulta em vários buscadores. | Uso como proxy de scraping, bloqueio de IP pelos buscadores, custo no Vercel. | Rate limit por IP (middleware/KV), cache por consulta, limite de tamanho de `q`. | Time 2/3 (web) |
| SEC-08 | MÉDIO | web/next.config.mjs:2 | Nenhum cabeçalho de segurança (CSP, `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy`). | Clickjacking e ausência de defesa em profundidade contra XSS. | `headers()` no next.config com CSP restritiva e os demais cabeçalhos. | Time 2/3 (web) |
| SEC-09 | MÉDIO | web/package.json (`next ^15.5.0`), web/package-lock.json | `npm audit`: `postcss <=8.5.22` **high** (GHSA-qx2v-qp2m-jg93 XSS no stringify; GHSA-6g55-p6wh-862q, GHSA-fxqj-rqcc-2cmp, GHSA-r28c-9q8g-f849 leitura de .map via sourceMappingURL) e `next` moderate. Classifiquei MÉDIO porque o postcss roda só no build com CSS próprio. | Exploração exige CSS controlado por atacante no build. | `npm audit fix` / subir `next` para a versão corrigida e regenerar o lock. | Time 2/3 (web) |
| SEC-10 | MÉDIO | requirements.txt:1-15; requirements-optional.txt:1-10 | Nenhuma dependência Python fixada (sem `==` nem hashes); `pip-audit` não consegue auditar (“not pinned”). | Instalação puxa versões novas/comprometidas; auditoria de CVE impossível. | Gerar `requirements.lock` com `pip-compile --generate-hashes` e auditar no CI. | Time 1 (raiz) |
| SEC-11 | BAIXO | c/search/cli.c:31-35; c/hello_fusion/cli.c:19, :26-27 | Retornos de `malloc` não checados antes de `memcpy`/escrita. | Crash (NULL deref) com entrada enorme; só no CLI de teste. | Checar NULL e sair com código 2. | Time 1 (c/) |
| SEC-12 | BAIXO | c/capstone/src/cx_capstone.c:25 | `cs_malloc(h)` não checado antes de `cs_disasm_iter`. | NULL deref em falta de memória (wasm com memória limitada). | `if (!insn) { cs_close(&h); return -4; }`. | Time 1 (c/) |
| SEC-13 | INFO | c/capstone/cli.c:12-16 | Entrada hex maior que 4096 bytes é truncada em silêncio (sem overflow, o laço respeita `sizeof code`). | Resultado parcial sem aviso. | Avisar ou retornar erro quando truncar. | Time 1 (c/) |
| SEC-14 | INFO | c/search/src/search.c:71-75, :110-142 | Revisão manual: tamanhos validados (`off/len < 0`, `m > cap`), alocações checadas, saída nunca maior que a entrada. Sem overflow encontrado. | — | — | Time 1 (c/) |
| SEC-15 | INFO | todo o repo | Sem `shell=True`, `os.system`, `eval`/`exec` dinâmico, `pickle` ou `yaml.load` em código de produção (os nomes em chessx_libs/audit/checks.py:15-17 são as regras do auditor). Os 22 `subprocess` (S603) usam lista de argumentos. Varredura de segredos (regex estilo gitleaks + bandit): nenhum segredo real; só fixtures de teste (tests/test_menu_osint.py:9, tests/test_osint_core.py:102). | — | — | — |

## 3. Arquitetura

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| ARQ-01 | BAIXO | chessx_libs/native/search.py:45 ↔ chessx_libs/search/fusion.py:32; chessx_libs/native/capstone.py:95 ↔ chessx_libs/reversing/disasm.py:103 | Dependências circulares `native↔search` e `native↔reversing` (resolvidas por import tardio dentro de função). | Acoplamento; quebra fácil se algum import subir para o topo. | Mover as referências Python (`norm_url`, `disasm_x86`) para um módulo neutro ou injetar o fallback. | Time 1 (native) |
| ARQ-02 | BAIXO | chessx_v05_legacy.py:1-291 | Versão antiga inteira na raiz, sem nenhum import. | Código morto que aparece em buscas, auditorias e no ruff. | Mover para `docs/legacy/` ou tag git e apagar. | Time 1 (chessx.py) |
| ARQ-03 | INFO | chessx.py:68; agents/core.py:101; crypto/guard.py:19; mathx/__init__.py:78; menu/registry.py:79; reversing/disasm.py:106; reversing/provenance.py:22, :28, :172, :201; voice/lang.py:41; voice/stt.py:129; voice/tts.py:145 | `try/except: pass` engolindo erros (S110). | Falhas silenciosas dificultam diagnóstico. | Logar em nível debug ou restringir a exceção. | Vários |

## 4. Performance

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| PERF-01 | BAIXO | chessx_libs/osint/http.py:47; chessx_libs/browser/fetch.py:37 | `r.read()` lê a resposta inteira em memória, sem limite. | Memória alta com respostas grandes. | Ler em blocos com teto (ex.: 10 MB). | Time 1 (osint/browser) |
| PERF-02 | INFO | c/search/src/search.c:129-135 | Deduplicação O(n·grupos) e checagem de motor O(n²) (o comentário admite). | Irrelevante para dezenas de resultados. | Hash table se n crescer. | Time 1 (c/) |
| PERF-03 | INFO | chessx_libs/crypto/aesgcm.py, chacha.py, ed25519.py | Fallbacks em Python puro são lentos. | Ver CRY-01. | — | Time 1 (crypto) |
| PERF-04 | INFO | chessx_libs/sounds/tests | Suíte de sons leva ~23 s de ~35 s da suíte toda. | CI mais lento. | Reduzir duração dos renders nos testes. | Time 1 (sounds) |

## 5. Testes

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| TST-01 | MÉDIO | chessx_libs/audit (118 stmts), chess_ai (39), scheduler (109), windows (84) | Cobertura 0%: só são tocados pelo selftest, que não roda sob o pytest. | Regressões passam despercebidas. | Testes unitários mínimos por pacote. | Time 1 |
| TST-02 | MÉDIO | chessx_libs/menu (41%), i18n (42%), search (49%), interface (51%) | Cobertura baixa em pacotes centrais. | Menu/i18n quebram sem teste vermelho. | Testar cada entrada do menu com `ask` simulado; cobrir fusion/engines com fixtures. | Time 1 (menu, search, interface); Time 2/3 (i18n) |
| TST-03 | BAIXO | tests/test_search_e2e.py:52-95; tests/test_osint_sources.py:112; tests/test_osint_people.py:109 | 10 testes de rede real pulados por padrão (`CHESSX_E2E=1`), e nenhum workflow os roda. | Quebras de API externa só aparecem em produção. | Job agendado (cron) com `CHESSX_E2E=1`, não bloqueante. | Time 1 (search/osint) |
| TST-04 | BAIXO | .github/workflows (ausência) | Nenhum workflow roda a suíte Python completa nem o selftest; o c-wasm roda só `tests.test_native`. web/ e desktop/ não têm testes (só lint+build no web). | Merge quebrado no `main` sem alarme. | Workflow `python-ci` com `pytest tests chessx_libs` + `chessx.py --selftest`. | Time 1 |
| TST-05 | INFO | tests/test_native_capstone.py:20; reversing/tests/test_reversing.py:83, :100, :114; detective/tests/test_detective.py:79 | Pulados localmente por falta de capstone/angr/radare2/ref antiga (capstone é coberto no CI c-wasm). | — | — | Time 1 |
| TST-06 | INFO | — | Flakiness: 3 execuções completas deram resultado idêntico (351 ok, 15 skipped, 210 subtests). Nenhum `assert True` trivial encontrado. | — | — | — |

## 6. Documentação

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| DOC-01 | MÉDIO | docs/CRYPTO_AUDIT.md:19-26 | Os achados 1-8 continuam como "aberto", mas conferi no código que todos estão corrigidos: #1/#2 web/app/api/refresh/route.ts:8-19 (timingSafeEqual e fail-closed); #3 desktop/src-tauri/tauri.conf.json:21 (CSP definida); #4/#5 sem `mktemp` em voice/ (com teste voice/tests/test_tempfiles.py); #6 chessx.py:199 usa `mkstemp`; #7 reversing/disasm.py:31-45 (subprocesso `python -I`); #8 chessx.py:178-179 marcado como vetor fixo. Só o #9 está como corrigido. | Leitor acha que há 5 médios abertos. | Atualizar a coluna de status com os hashes das correções. | Time 1 (crypto) |
| DOC-02 | BAIXO | CHESSX_MASTER_LIST.md:524-555 | Numeração pula da seção 25 para a 27; não existe seção 26. | Referências “§26” ficam sem alvo. | Criar a 26 ou renumerar e registrar. | Time 1 (listas) |
| DOC-03 | BAIXO | PRIORITY_LIST.md:8-40 | Sem status por item: #11 e #23 estão feitos e não marcados; itens 22, 23 e 24 inseridos fora de ordem numérica. | Agentes pegam item já feito ou na ordem errada. | Coluna de status (feito/em andamento/livre) com hash. | Time 1 (listas) |
| DOC-04 | INFO | CHESSX_MASTER_LIST.md:604-612 | §29 (sandbox) descrita com containers, rede isolada e snapshots, mas não há implementação (ver OSB-01). | Expectativa errada de isolamento. | Marcar como “Not started”. | Time 1 (listas) |
| DOC-05 | INFO | *.md (fora de vendor) | Verificação de links relativos: 0 quebrados. Links externos não verificados. | — | — | — |

## 7. i18n

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| I18N-01 | BAIXO | chessx_libs/menu/registry.py:19-20, :28 | `menu_osint` e `menu_retro` não existem nas tabelas do i18n (`MISSING_I18N`); em pt/ja aparecem em inglês. | Menu misturando idiomas. | Adicionar as 2 chaves em en/pt/ja em chessx_libs/i18n/strings.py. | Time 2/3 (i18n) |
| I18N-02 | BAIXO | chessx_libs/i18n/namespaces/menu.py vs chessx_libs/menu/registry.py:6-24 | Dois esquemas de chave para o menu: namespace com ponto (`menu.back`, 15 chaves) e chaves planas `menu_*` no registry. As do namespace não são usadas pelo registry. | Chaves duplicadas/mortas; tradução no lugar errado. | Escolher um esquema (namespace `menu.*`) e migrar o registry. | Time 2/3 (i18n) + Time 1 (menu) |
| I18N-03 | INFO | chessx_libs/i18n/strings.py | 84 chaves completas em en/pt/ja, placeholders `{x}` consistentes. pt mantém `url`, `cursor`, `proxy` iguais ao inglês (estrangeirismo aceitável). | — | — | Time 2/3 (i18n) |

## 8. CI/CD

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| CI-01 | MÉDIO | .github/workflows/c-wasm.yml:1-61; refresh-ping.yml:1-17; web-ci.yml:1-40 | Nenhum workflow declara `permissions:`; o `GITHUB_TOKEN` herda o padrão do repositório. | Passo comprometido pode escrever no repo. | `permissions: contents: read` no topo de cada workflow. | Time 1 (c-wasm), Time 2/3 (web, refresh) |
| CI-02 | MÉDIO | c-wasm.yml:26-35 | wasi-sdk, wasmtime e wasmer baixados com `curl` e instalados com `sudo` sem checksum. | Tarball trocado roda como root no runner e contamina o artefato .wasm publicado. | Fixar SHA-256 e checar com `sha256sum -c`. | Time 1 (c/) |
| CI-03 | MÉDIO | web-ci.yml:38-40; c-wasm.yml:47 | `npx vercel@latest` (com `VERCEL_TOKEN` no ambiente) e `npm i @bjorn3/browser_wasi_shim@0.4` sem lock. | Versão nova/comprometida do CLI recebe o token de deploy. | Fixar versão exata do `vercel` e do shim. | Time 2/3 (web), Time 1 (c/) |
| CI-04 | BAIXO | c-wasm.yml:19-23, :51; web-ci.yml:15-16, :30 | Actions por tag (`@v4`, `@v5`), não por SHA. | Tag movida injeta código. | Pin por SHA (com Dependabot). | Time 1 / Time 2/3 |
| CI-05 | BAIXO | web-ci.yml:21-29 | Job `deploy` com secrets sem `environment:` protegido. | Deploy de produção sem aprovação. | `environment: production` com regras. | Time 2/3 (web) |
| CI-06 | INFO | GitHub Actions (últimas 10 execuções) | Todas `success` (c-wasm até e3bdcfa, web-ci até 144d4c4); a de 49a09a9 estava em andamento na consulta. Sem segredo exposto em log/arquivo. | — | — | — |

## 9. OSINT e sandbox

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| OSB-01 | INFO | CHESSX_MASTER_LIST.md:604 (§29); chessx_libs/crypto/guard.py | Não existe sandbox de execução: nada de namespaces, seccomp ou rede isolada. `guard.py` só *detecta* ambiente de VM/debugger. Isolamento real e escape não se aplicam por enquanto. | Ninguém deve rodar amostras achando que há isolamento. | Implementar §29 ou marcar como não iniciada. | Time 1 |
| OSB-02 | BAIXO | chessx_libs/osint/http.py:44-47 | `urllib_transport` segue redirects automaticamente e não checa o host final; os hosts de origem são fixos por fonte. | Redirect de uma fonte pode levar a host interno (SSRF limitado). | Handler de redirect que valida o host contra a allow-list da fonte. | Time 1 (osint) |
| OSB-03 | BAIXO | chessx_libs/reversing/disasm.py:35-39 | O limite `RLIMIT_AS` do subprocesso que faz `marshal.loads` é ignorado em silêncio onde não existe (Windows) ou não é aplicado (macOS). | `.pyc` malicioso pode consumir memória sem limite (não executa código). | Timeout no subprocesso e aviso quando o rlimit falha. | Time 1 (reversing) |
| OSB-04 | BAIXO | chessx_libs/mathx/langs.py:116-117 | O timeout do `safe_eval` é desligado fora da thread principal e no Windows (sem SIGALRM). Há guarda de expoente (testei `9^9^9`: rejeitado). | Expressão lenta trava o worker (agents/web) sem limite. | Rodar em subprocesso com timeout. | Time 2/3 (mathx) |
| OSB-05 | INFO | chessx_libs/osint/sources/pwned.py:18; osint/http.py | SHA-1 no pwned é exigido pela API k-anonymity (só 5 caracteres saem). Modo offline, cache, rate limit por host e audit log estão presentes; fontes não comerciais marcadas. | — | — | Time 1 (osint) |

## 10. Criptografia

| ID | Severidade | Arquivo:linha | Descrição | Risco | Correção sugerida | Dono |
|---|---|---|---|---|---|---|
| CRY-01 | MÉDIO | chessx_libs/crypto/aead.py:18, :40, :52, :59 | Sem o pacote `cryptography`, o AEAD cai em silêncio para AES-GCM/ChaCha20-Poly1305 em Python puro e sem tempo constante. Diferente do Argon2id, que agora exige `allow_fallback=True`. | Canal lateral de tempo; usuário não sabe que está no modo fraco. | Exigir opt-in explícito (como no Argon2) ou levantar erro; logar o backend. | Time 1 (crypto) |
| CRY-02 | BAIXO | chessx_libs/crypto/ed25519.py:1; chessx_libs/crypto/asym.py | Fallback Ed25519/X25519 em Python puro, também sem tempo constante. | Vazamento de chave por tempo em uso remoto. | Mesmo tratamento de CRY-01. | Time 1 (crypto) |
| CRY-03 | BAIXO | chessx_libs/crypto/passwords.py:75-80 | `verify_password` usa `m`, `t`, `p` e `ln` lidos do próprio hash armazenado, sem teto. | Hash adulterado no banco (ex.: `m=2^31`) causa DoS de memória/CPU. | Recusar parâmetros acima de um máximo configurado. | Time 1 (crypto) |
| CRY-04 | BAIXO | chessx_libs/crypto/otp.py:102-124 | `TOTPVerifier` guarda `last_step` num dict em memória por padrão e não tem trava entre processos (backlog conhecido). | Proteção contra replay some ao reiniciar ou com vários workers. | Store persistente com lock/CAS. | Time 1 (crypto) |
| CRY-05 | BAIXO | chessx_libs/crypto/keystore.py:100-107 | Gravação atômica (`mkstemp` 0600 + `os.replace`), mas sem lock entre processos (backlog conhecido). | Duas rotações simultâneas: a última vence e uma chave nova se perde. | `fcntl`/`msvcrt` lock em volta de ler-modificar-gravar. | Time 1 (crypto) |
| CRY-06 | INFO | crypto/passwords.py:3; crypto/otp.py:41-58, :142-165; crypto/aead.py:6 | Conferido como correto: Argon2id m=64 MiB, t=3, p=4, salt de 16 B (OWASP); TOTP janela ±1 com `compare_digest` e anti-replay por `last_step`; backup codes com PBKDF2-SHA256 100k, salt por código e uso único; AEAD com nonce aleatório de 12 B gerado automaticamente e blob versionado. | — | — | Time 1 (crypto) |
| CRY-07 | INFO | docs/CRYPTO_AUDIT.md | Cruzamento: os 9 achados da auditoria anterior estão corrigidos no código (ver DOC-01). Backlog ainda aberto: lock entre processos (CRY-04/05), Double Ratchet e teste real de QR/keyring. | — | — | Time 1 (crypto) |

## Reauditoria: triagem #25 fases C e D (ab2aa73, 5ec3b0c, a690606)

- **Data:** 2026-10-30 12:30 (UTC-3). Escopo: só os diffs desses 3 commits em `chessx_libs/reversing/{triage,detective,__main__,__init__}.py` e `tests/test_triage.py`, revisados no `main` de hoje.
- **Ambiente:** venv com yara-python 4.5.4 para testar o caminho real do YARA.
- **Testes:** `pytest chessx_libs/reversing`: 67 passed, 4 skipped. `test_triage.py` com yara real: 25 passed, 0 skipped.
- **Testes manuais com regras sintéticas:**
  - `include` foi recusado ("includes are disabled").
  - O symlink para fora da pasta de regras foi ignorado (`_safe_files` usa realpath com o diretório pai igual à base).
  - `import "console"` foi aceito e imprimiu no stdout.
  - Com `CHESSX_TRIAGE_YARA_MAX=abc`, o pacote inteiro dá `ValueError` ao importar.

| Severidade | CRÍTICO | ALTO | MÉDIO | BAIXO | INFO | Total |
|---|---|---|---|---|---|---|
| Triagem C/D | 0 | 0 | 2 | 5 | 3 | 10 |

| ID | Sev. | Arquivo:linha | Descrição | Risco | Correção sugerida | Time |
|---|---|---|---|---|---|---|
| TRI-01 | MÉDIO | reversing/triage.py (yara_scan, laço `rules.match`) | O timeout de 5 s vale por arquivo `.yar`, sem orçamento total. Com até 500 arquivos (`YARA_MAX_FILES`), um único `investigate()` pode levar cerca de 2500 s. | DoS por pacote de regras lento; trava a CLI e a UI. | Orçamento total (ex.: 15 s) por triagem, interrompendo o laço quando passar do prazo; ou compilar tudo num único `yara.compile(filepaths=…)` com um só `match`. | Time 1 |
| TRI-02 | MÉDIO | reversing/detective.py:79-86 | Se `triage()` levanta exceção, o fallback devolve `verdict: "clean"`. | Falha aberta: um erro (ou uma entrada feita para quebrar a triagem) aparece como "limpo". | Usar um veredito próprio (`"error"`/`"unknown"`) e mostrar isso na CLI/UI. | Time 1 |
| TRI-03 | BAIXO | reversing/triage.py:396 | `int(os.environ["CHESSX_TRIAGE_YARA_MAX"])` roda no import do módulo. Um valor inválido derruba `import chessx_libs.reversing` inteiro, inclusive o selftest. | Um env inválido quebra o pacote todo. | Ler o valor de forma tolerante (try/except, mínimo 1) e de preferência na hora do scan. | Time 1 |
| TRI-04 | BAIXO | reversing/triage.py (yara_scan, `yara.compile`) | Módulos YARA não são restritos: `import "console"` escreve direto no stdout (confirmado), e `magic`/`cuckoo` também são aceitos. | Regras de terceiros injetam texto na saída e corrompem o `--json`. | Rejeitar `import` fora de uma allowlist (pe, elf, math, hash) antes de compilar, ou usar `console_callback`. | Time 1 |
| TRI-05 | BAIXO | reversing/triage.py:140-145 | As pastas de `CHESSX_TRIAGE_RULES` e `--rules` são carregadas sem checar dono nem permissão (ex.: uma pasta em `/tmp` gravável por todos). | Outro usuário local pode plantar regras e mudar vereditos (forçar "clean" pela allowlist ou gerar falsos positivos). | Recusar pastas/arquivos graváveis por grupo/outros ou de outro dono; registrar a origem no relatório. | Time 1 |
| TRI-06 | BAIXO | reversing/triage.py (main, `open(a.file,"rb").read()`) | Com `--rules`, o arquivo é lido inteiro de novo, sem limite de tamanho e sem fechar o handle, e a triagem roda duas vezes (uma dentro de `investigate`, outra fora). | Memória/tempo dobrados em amostras grandes; ResourceWarning. | Passar `extra_rule_dirs` para `investigate()` ou reaproveitar os dados dele; usar `with open`. | Time 1 |
| TRI-07 | BAIXO | tests/test_triage.py:347-357 | O teste de timeout depende de relógio real (regex patológica, 1 s), e os testes de yara real dependem de `importorskip`. O CI não instala `yara-python`, então lá eles são sempre pulados. | Regressão no caminho real não é pega no CI; o teste de timeout pode oscilar em máquina lenta ou rápida. | Instalar `requirements-optional.txt` num job do CI; testar a detecção de timeout com um `match` simulado que levanta `yara.TimeoutError`. | Time 1 / CI |
| TRI-08 | INFO | reversing/triage.py (yara_scan) | Os arquivos `.yar` são recompilados a cada `investigate()`. | Custo repetido em lote (corpus FP, varredura de pastas). | Cache por (caminho, mtime, tamanho). | Time 1 |
| TRI-09 | INFO | reversing/triage.py:469-471 | A detecção de timeout ainda aceita a substring "timeout" em qualquer mensagem de erro, além de `yara.TimeoutError`. | Um erro qualquer cuja mensagem contenha "timeout" marca `timed_out=True`. | Depois do fix do a690606, confiar só em `isinstance(exc, yara.TimeoutError)`. | Time 1 |
| TRI-10 | INFO | reversing/README.md:90-92 | A doc fala em "timeout 5 s", mas não diz que é por arquivo nem cita o limite de 500 arquivos, `CHESSX_TRIAGE_YARA_MAX` ou o corte silencioso acima de 32 MiB (`limits.truncated`). | Expectativa errada de tempo e cobertura do scan. | Documentar os três limites e o comportamento de truncamento. | Time 1 |

Pontos verificados sem achado:
- `includes=False` funciona.
- Não há path traversal nem escape por symlink nas pastas de regras.
- O limite de 32 MiB é aplicado (com teste).
- A chave `triage` vem por último no relatório.
- A CLI limita a saída a 8 matches.
- A atribuição DRL (author/license) é preservada.
- Nada é executado nem baixado da rede.
