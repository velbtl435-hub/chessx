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
