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
| # | Achado | Arquivo:linha | Sev. | Dono | Status |
|---|---|---|---|---|---|
| 1 | Comparação do segredo de cron com `!==` (tempo não constante) | web/app/api/refresh/route.ts:6 | média | web | aberto |
| 2 | Endpoint de refresh fica aberto (fail-open) quando `CRON_SECRET` não existe | web/app/api/refresh/route.ts:5-6 | média | web | aberto |
| 3 | CSP do Tauri desativada (`"csp": null`) | desktop/src-tauri/tauri.conf.json:14 | média | desktop | aberto |
| 4 | `tempfile.mktemp` (corrida TOCTOU/symlink) | chessx_libs/voice/tts.py:203, :280 | média | voice | aberto |
| 5 | `tempfile.mktemp` | chessx_libs/voice/stt.py:85, :111 | média | voice | aberto |
| 6 | `tempfile.mktemp` no self-test | chessx.py:197 | baixa | Coder (Team 1) | aberto |
| 7 | `marshal.load` em `.pyc` vindo do usuário | chessx_libs/reversing/disasm.py:24 | baixa | Reversing (Team 1) | aberto |
| 8 | Chave e nonce zerados no self-test ChaCha20 | chessx.py:179-180 | baixa (informativo) | Coder (Team 1) | aberto |
| 9 | `random.Random` (Mersenne Twister) na rotação de fingerprint | chessx_libs/crypto/netsec.py:72 | baixa | crypto (Team 1) | corrigido com 8a072c2 |

Total: 0 alta, 5 média, 4 baixa.

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
- Lock entre processos (arquivo + `fcntl`/`msvcrt`) para o estado do `TOTPVerifier` (anti-replay/lockout) e para o `keystore`.
- Double Ratchet (forward secrecy por mensagem) sobre a sessão E2E (`session.py`).
- Testar QR e keyring de verdade quando `qrcode[pil]` e `keyring` entrarem em `requirements-optional.txt` (Coder).
- Ligar 2FA, senhas e keystore no `chessx.py` (Coder). Em web/agents (outros times), só quando eles pedirem.
- Achados 1-8 acima, com os respectivos donos.
