# chessx_libs.search
Multi-engine web search with result fusion (rank-based scoring, URL de-duplication).

- **Origin:** written for ChessX; replaces the single DuckDuckGo scraper in chessx.py v0.5.
- **License:** same as the ChessX repository. The optional `ddgs` package is MIT-licensed.
- **Adapted:** engines DuckDuckGo HTML, ddgs, Brave API, a generic WebSerp endpoint, SearXNG, and a Mock engine for offline tests.
  DuckDuckGo: tries curl_cffi browser impersonation first, then rotating User-Agent/Accept-Language headers over
  html./lite. with GET and POST. It raises a clear `SearchError` only when every attempt gets the bot-check ("anomaly") page.
  ddgs: titles that come back glued to other results' titles are split and joined with " | " (`split_glued_title`).
- **Known external limitation:** DuckDuckGo's anti-bot blocks scripted clients intermittently, depending on UA, endpoint and IP.
  This is outside ChessX's control, so prefer ddgs/Brave/SearXNG for reliability.
- **Env:** `BRAVE_API_KEY`, `SEARXNG_URL` (default http://localhost:8888), `WEBSERP_URL` with a `{q}` placeholder, optional `WEBSERP_KEY`.
- **Optional dependency:** `ddgs` (`pip install ddgs`), which is the most reliable backend. `safe_search()`/`multi_search()` return [] on failure.

## End-to-end (real network) checks
- Table per engine (ok/skip/blocked/error, results, latency, DuckDuckGo attempt stats) plus fusion:
  `python3 -m chessx_libs.search.e2e` (optional queries as args; default `python-chess`, `stockfish`).
- Tests: `python3 -m unittest tests.test_search_e2e -v` runs only the offline fusion tests;
  `CHESSX_E2E=1 python3 -m unittest tests.test_search_e2e -v` adds the real-network tests.
- Engines without config are skipped, not failed: Brave (`BRAVE_API_KEY`), WebSerp (`WEBSERP_URL`),
  SearXNG (`SEARXNG_URL`, else probes http://localhost:8888; `SEARXNG_PUBLIC=1` also probes a few public instances,
  which usually refuse `format=json`). ddgs is skipped if not installed. DuckDuckGo is skipped if every attempt is blocked.
- `DuckDuckGoEngine.attempt_log` holds `(how, impersonate, endpoint, method, outcome)` for each attempt of the last search.
- Fusion: the agreement bonus applies only when a *different* engine returns the same normalized URL.
- Scores: every engine returns per-result scores in [0, 1]. SearXNG's unbounded raw score is mapped to
  `0.5 * rank_score + 0.5 * raw / max(raw)` (order preserved); `fuse()` also clamps each input score to [0, 1].
