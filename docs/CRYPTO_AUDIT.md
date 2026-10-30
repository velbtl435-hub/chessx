# Auditoria de criptografia — ChessX (2026-10-30)

Autor: Team 1 / crypto. Worktree `chessx-t1crypto`, base `origin/main` em 2026-10-30.

## Escopo e método
- Escopo: todos os `.py` versionados (`git ls-files`, 207 arquivos de código), mais `web/` (TS/TSX/MJS), `desktop/` (Rust, JS, config Tauri) e `c/` (C). Ficaram fora: código vendorizado/terceiros e `node_modules`.
- Comandos (`rg -n` sobre a lista de arquivos):
  - RNG: `import random|random\.(random|randint|choice|...|Random)|Math\.random|rand\(\)|srand`
  - Comparação: `(digest|token|sig|mac|tag|hash|password|secret|otp)\w*\s*[!=]=` e o inverso; `!==`/`===` em TS
  - Hash/cifra: `md5|sha1|pbkdf2|ECB|DES|RC4|createHash|sha256\(`
  - Nonce/IV: `nonce|\biv\b|bytes\(12\)`
  - Segredos: `(api_key|secret|token|password|private_key|bearer)\s*[:=]\s*'...'` e prefixos conhecidos (`ghp_`, `AKIA`, `sk-`, `xox?-`, `AIza`)
  - Outros: `eval(|exec(|pickle.load|marshal.load|yaml.load(|verify=False|CERT_NONE|_create_unverified_context|tempfile.mktemp|shell=True|rejectUnauthorized`, `"csp"` no Tauri
- Cada achado foi revisado à mão. O dono saiu do diretório e do prefixo dos commits (`git log -- <arquivo>`).

## Resumo
Status atualizado em 2026-10-30 (tarde), após o [AUDIT_REPORT.md](../AUDIT_REPORT.md) (DOC-01). Cada correção foi conferida no código de `main`, não só pela mensagem de commit.

| # | Achado | Arquivo:linha (original) | Sev. | Dono | Status |
|---|---|---|---|---|---|
| 1 | Comparação do segredo de cron com `!==` (tempo não constante) | web/app/api/refresh/route.ts:6 | média | web | corrigido (144d4c4) |
| 2 | Endpoint de refresh aberto (fail-open) sem `CRON_SECRET` | web/app/api/refresh/route.ts:5-6 | média | web | corrigido (144d4c4) |
| 3 | CSP do Tauri desativada (`"csp": null`) | desktop/src-tauri/tauri.conf.json:14 | média | desktop | corrigido (f56bc10), ver nota |
| 4 | `tempfile.mktemp` | chessx_libs/voice/tts.py:203, :280 | média | voice | corrigido (aee1f8b) |
| 5 | `tempfile.mktemp` | chessx_libs/voice/stt.py:85, :111 | média | voice | corrigido (aee1f8b) |
| 6 | `tempfile.mktemp` no self-test | chessx.py:197 | baixa | Coder (Team 1) | corrigido (035e7a0) |
| 7 | `marshal.load` em `.pyc` do usuário | chessx_libs/reversing/disasm.py:24 | baixa | Reversing (Team 1) | corrigido (1f29b9a) |
| 8 | Chave/nonce zerados no self-test ChaCha20 | chessx.py:179-180 | baixa (info) | Coder (Team 1) | corrigido (035e7a0): comentário de vetor fixo |
| 9 | `random.Random` na rotação de fingerprint | chessx_libs/crypto/netsec.py:72 | baixa | crypto (Team 1) | corrigido (8a072c2) |

Placar: 9 de 9 corrigidos, 0 abertos.

### Revisão das correções (o que foi conferido)
- **#1/#2 (144d4c4).** `route.ts` agora usa `timingSafeEqual` sobre `Buffer`s e responde 503 quando falta `CRON_SECRET` (fail-closed). Ressalva menor: o `if (ab.length !== bb.length) return false` sai cedo e assim vaza o *tamanho* de `Bearer <segredo>`. O conteúdo não vaza, e o tamanho de um segredo aleatório não ajuda o atacante. Aceitável. Para zerar até isso, basta comparar `sha256(a)` com `sha256(b)` (tamanho fixo de 32 B).
- **#3 (f56bc10).** CSP definida: `default-src`/`script-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, `connect-src` só `self` e IPC. `style-src 'self' 'unsafe-inline'` vem junto com `dangerousDisableAssetCspModification: ["style-src"]`. **Aceitável**: o xterm.js (`desktop/ui/vendor/xterm.js`) injeta estilos inline em tempo de execução, e se o Tauri acrescentasse nonce/hash ao `style-src` o `'unsafe-inline'` seria ignorado e o terminal quebraria. O risco que sobra é só injeção de CSS, porque scripts continuam restritos a `'self'`. Nota extra: `withGlobalTauri: true` expõe `window.__TAURI__` ao webview e amplia o impacto de um eventual XSS. Não é regressão, fica como sugestão ao desktop.
- **#4/#5 (aee1f8b).** `voice/tts.py` e `voice/stt.py` usam um `_tmpfile()` com `mkstemp` (fd fechado, arquivo 0600) e limpam em `finally`/`except`. O teste `voice/tests/test_tempfiles.py` garante que não há `mktemp(`. Sem problemas.
- **#6/#8 (035e7a0).** `chessx.py:199` usa `mkstemp` + `os.fdopen` e remove o arquivo no `finally`. O self-test ChaCha20 (`chessx.py:178-182`) ganhou um comentário dizendo que é vetor fixo. OK.
- **#7 (1f29b9a).** `disasm_pyc` valida magic, flags, tamanho (16 MiB) e TYPE_CODE, e decodifica o marshal num subprocesso `python -I -S` com `RLIMIT_AS` de 512 MiB e timeout de 10 s. Nunca executa o código. Ressalva: é isolamento de processo, não sandbox (sem seccomp/namespaces, e o `RLIMIT_AS` é ignorado silenciosamente fora do POSIX). Basta para o risco (crash/DoS de `marshal`).
- **#9 (8a072c2).** `SystemRandom()` por padrão. A seed só vale para teste (`tests/test_crypto_netsec_rng.py`).

## Achados CRY-* do AUDIT_REPORT.md (dono: crypto)
| ID | Sev. | Achado | Status |
|---|---|---|---|
| CRY-01 | média | AEAD caía em silêncio para Python puro sem `cryptography` | corrigido (87f1c1b): `AEADUnavailable` por padrão; `allow_fallback=True` + `InsecureFallbackWarning` (RuntimeWarning); propagado para envelope/session/keystore |
| CRY-02 | baixa | Fallback X25519/Ed25519 puro | corrigido (29aafe1): operações com chave secreta levantam `AsymUnavailable` sem opt-in; `ed25519_verify` (só dados públicos) segue funcionando |
| CRY-03 | baixa | `verify_password` aceitava m/t/p/ln sem teto vindos do hash | corrigido (b20aeb0): `MAX_PARAMS` checado antes de qualquer derivação, em todos os backends, inclusive argon2-cffi |
| CRY-04 | baixa | Anti-replay do TOTP só em memória e sem lock entre processos | corrigido (4d40e42): `JSONFileStore` (lock fcntl/msvcrt + replace atômico, 0600); o store em dict continua como padrão |
| CRY-05 | baixa | Keystore sem lock entre processos (lost update) | corrigido (859aeb5): lock + compare-and-swap; o segundo escritor recebe `KeystoreConflict` em vez de apagar chaves |
| CRY-06/07, PERF-03 | info | Conferências / fallbacks lentos | sem ação (PERF-03 coberto por CRY-01/02) |

## Detalhes
1. **route.ts:6.** A comparação `!==` com `` `Bearer ${secret}` `` vaza o tamanho do prefixo correto pelo tempo de resposta. Correção: comparar com `crypto.timingSafeEqual` sobre `Buffer`s de mesmo tamanho (checar o tamanho antes), ou comparar o SHA-256 dos dois lados.
2. **route.ts:5.** `if (secret && ...)` libera o acesso quando a variável não existe. Qualquer pessoa pode então disparar `revalidateTag` e `getFeed`, o que gasta a cota da API de busca (DoS de custo). Correção: fail-closed, ou seja, responder 401/503 quando `CRON_SECRET` estiver ausente em produção.
3. **tauri.conf.json:14.** Sem CSP, um XSS no webview ganha acesso às APIs do Tauri. Correção: `"csp": "default-src 'self'; connect-src 'self' http://127.0.0.1:*"`, ajustando ao que o sidecar usa.
4-6. **`mktemp`.** A função devolve só o nome, então outro processo pode criar ou trocar o arquivo antes de ele ser aberto. Correção: `fd, p = tempfile.mkstemp(suffix=...)` e `os.close(fd)` (ou `NamedTemporaryFile(delete=False)`), apagando no `finally`.
7. **disasm.py:24.** `marshal` não é feito para entrada não confiável: um `.pyc` malicioso pode derrubar o interpretador. Não há execução de código, porque só se desmonta. Correção: rodar num subprocesso isolado, ou documentar que só se deve abrir `.pyc` confiável.
8. **chessx.py:179.** Chave/nonce `bytes(32)`/`bytes(12)` aparecem só num round-trip de self-test, nunca em dados reais. Sugestão: usar `os.urandom` ou os vetores RFC 8439 para não virar exemplo copiado.
9. **netsec.py:72.** Sem seed, o MT tinha estado previsível. Agora usa `random.SystemRandom()` por padrão, e a seed continua valendo para testes reprodutíveis. Teste em `tests/test_crypto_netsec_rng.py`.

## Usos benignos descartados
- `chessx_v05_legacy.py:44-45`: `random.uniform`/`choice` para scores e tipos de resultados mock (legado, sem segurança).
- `chessx_libs/sounds/dsp.py:28` e testes: `numpy.random.default_rng` para síntese de áudio.
- `chessx_libs/audit/checks.py`: só strings de detecção do próprio auditor.
- MD5/SHA-1 para checksums forenses e imphash: `reversing/formats.py:163`, `reversing/provenance.py:17`, `reversing/detective.py:17`, `detective/investigate.py:36`.
- SHA-1 em HOTP/TOTP (`crypto/otp.py`, RFC 4226/6238).
- Checksum duplo SHA-256 do base58check (`bases/codecs.py:64`).
- `crypto/session.py:72`: SHA-256 para o transcript hash, não para senha.
- Backup codes com PBKDF2-SHA256 de 100k iterações e salt (`crypto/otp.py:143`). Os códigos são aleatórios de alta entropia e de uso único, então o custo basta. Senhas usam Argon2id (`passwords.py`).
- `web/lib/search.ts:34`: a chave vem de `process.env`, não está hardcoded.
- `.github/workflows/web-ci.yml:38-40`: usa `$VERCEL_TOKEN` via secrets.
- `tests/test_osint_core.py:102`: senha fictícia num teste de redação.
- Igualdades em `browser/parser.py`, `reversing/formats.py`, `voice/tts.py`: comparam tags HTML ou códigos de retorno, não segredos.
- `c/hello_fusion/cli.c`: `strcmp` só em argv.
- Nenhum segredo hardcoded encontrado. Nenhum `pickle`, `eval` em entrada, `verify=False`, ECB, DES ou RC4.

## Backlog
- ~~Lock entre processos para o `TOTPVerifier` e o keystore~~: feito em 4d40e42 e 859aeb5. É lock de host único: entre máquinas, o store precisa de CAS no banco.
- Double Ratchet (forward secrecy por mensagem) sobre a sessão E2E (`session.py`).
- Testar QR e keyring de verdade quando `qrcode[pil]` e `keyring` entrarem em `requirements-optional.txt` (Coder).
- Ligar 2FA, senhas e keystore no `chessx.py` (Coder). Em web/agents (outros times), só quando eles pedirem.
- Callers fora de crypto/ que dependem de `cryptography` desde o CRY-01: `chessx.py:181-182` (self-test) e `chessx_libs/menu/registry.py:94`. Sem o pacote, levantam `AEADUnavailable`. Coder: tratar/rotular ou passar `allow_fallback=True`.
- Opcional (web): comparar digests SHA-256 no `/api/refresh` para não vazar nem o tamanho. Opcional (desktop): avaliar `withGlobalTauri: false`.
