# ChessX Web: deploy no Vercel (Hobby)

## Status (2026-10-30)
- Next.js (App Router, TS) em `web/`; CI `web-ci.yml` passando no main.
- Cron diário do Vercel (09:00 UTC / 06:00 BRT) chama `/api/refresh`.
- Ping extra a cada 3h via `refresh-ping.yml` (pula sem a variável `CHESSX_URL`).
- **Deploy pendente:** a criação do projeto pela API do Vercel voltou 403 (sem permissão). Precisa importar pelo painel.

## Como publicar
1. Acesse https://vercel.com/new e importe `velbtl435-hub/chessx`.
2. Root Directory: `web` (framework Next.js detectado sozinho).
3. Se o repo não aparecer, libere o acesso do app Vercel ao repo nas configurações do GitHub.
4. Depois disso, todo push no `main` faz deploy automático.

## Variáveis (opcionais)
| Onde | Nome | Para quê |
|---|---|---|
| Vercel | `CRON_SECRET` | **obrigatório**: sem ele `/api/refresh` responde 503 (fail-closed) |
| Vercel | `BRAVE_API_KEY`, `SEARXNG_URL` | ativa esses motores de busca |
| Vercel | `CHESSX_FEED_QUERIES` | troca as buscas do feed |
| Vercel | `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` (ou `KV_REST_API_URL`/`KV_REST_API_TOKEN`) | rate limit por IP do `/api/search` compartilhado entre instâncias; sem eles usa memória por instância |
| Vercel | `SEARCH_RATE_MAX` (padrão 20), `SEARCH_RATE_WINDOW_MS` (padrão 60000) | ajusta o rate limit (429 + `Retry-After`); `q` máx. 200 caracteres (400) |
| GitHub (variável) | `CHESSX_URL` | liga o ping de 3h |
| GitHub (secrets) | `CRON_SECRET` | mesmo valor do Vercel |
| GitHub (secrets) | `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | deploy pelo Actions em vez do Git do Vercel |

## Limite do Hobby
Cron do Vercel Hobby roda no máximo 1x por dia; refresh mais frequente fica com o GitHub Actions.
