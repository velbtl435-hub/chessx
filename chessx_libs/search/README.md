# chessx_libs.search
Multi-engine web search with result fusion (rank-based scoring, URL de-duplication).

- **Origin:** written for ChessX; replaces the single DuckDuckGo scraper in chessx.py v0.5.
- **License:** same as the ChessX repository. The optional `ddgs` package is MIT-licensed.
- **Adapted:** engines DuckDuckGo HTML, ddgs, Brave API, a generic WebSerp endpoint, SearXNG, and a Mock engine for offline tests.
  DuckDuckGo HTML now raises `SearchError` when it serves its bot-check ("anomaly") page instead of silently returning nothing.
- **Env:** `BRAVE_API_KEY`, `SEARXNG_URL` (default http://localhost:8888), `WEBSERP_URL` with a `{q}` placeholder, optional `WEBSERP_KEY`.
- **Optional dependency:** `ddgs` (`pip install ddgs`), which is the most reliable backend. `safe_search()`/`multi_search()` return [] on failure.
