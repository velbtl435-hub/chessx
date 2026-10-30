"""Engine adapters. All network access is guarded; use safe_search() offline."""
import html, os, re, urllib.parse
from typing import List
from .base import Engine, Result, SearchError, http_get, http_json

_TAG = re.compile(r"<[^>]+>")


def _clean(s: str) -> str:
    return html.unescape(_TAG.sub("", s)).strip()


class DuckDuckGoEngine(Engine):
    """Scrapes html.duckduckgo.com (no key). Tolerates class-name changes."""
    name = "duckduckgo"
    URL = "https://html.duckduckgo.com/html/?q="
    LINK = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    SNIP = re.compile(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div|td)>', re.S)

    def parse(self, page: str, limit: int) -> List[Result]:
        links, snips = self.LINK.findall(page), self.SNIP.findall(page)
        out = []
        for i, (href, title) in enumerate(links[:limit]):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            url = q.get("uddg", [href])[0]
            out.append(Result(_clean(title), url, _clean(snips[i]) if i < len(snips) else "",
                              self.name, self.rank_score(i, limit)))
        return out

    def search(self, query, limit=10):
        page = http_get(self.URL + urllib.parse.quote_plus(query)).decode("utf-8", "replace")
        out = self.parse(page, limit)
        if not out and "anomaly" in page:
            raise SearchError("duckduckgo served a bot-check (anomaly) page")
        return out


class BraveEngine(Engine):
    """Brave Search API. Needs env BRAVE_API_KEY (free tier ~2000 req/month)."""
    name = "brave"
    URL = "https://api.search.brave.com/res/v1/web/search?"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY")

    def search(self, query, limit=10):
        if not self.api_key:
            raise SearchError("BRAVE_API_KEY not set")
        data = http_json(self.URL + urllib.parse.urlencode({"q": query, "count": min(limit, 20)}),
                         headers={"Accept": "application/json", "X-Subscription-Token": self.api_key})
        items = data.get("web", {}).get("results", [])[:limit]
        # fix: real rank-based score instead of constant 0.0
        return [Result(_clean(r.get("title", "")), r.get("url", ""), _clean(r.get("description", "")),
                       self.name, self.rank_score(i, len(items))) for i, r in enumerate(items)]


class DDGSEngine(Engine):
    """Optional: uses the `ddgs` package (pip install ddgs) if installed."""
    name = "ddgs"

    def search(self, query, limit=10):
        try:
            from ddgs import DDGS  # optional external dep
        except ImportError as e:
            raise SearchError("ddgs not installed (pip install ddgs)") from e
        rows = list(DDGS().text(query, max_results=limit))
        return [Result(r.get("title", ""), r.get("href", ""), r.get("body", ""), self.name,
                       self.rank_score(i, len(rows))) for i, r in enumerate(rows)]


class WebSerpEngine(Engine):
    """Generic SERP JSON API adapter. Env WEBSERP_URL (endpoint, `{q}` placeholder) + optional WEBSERP_KEY.
    Expects JSON {"results":[{"title","url","snippet"}]}."""
    name = "webserp"

    def __init__(self, endpoint: str = None, api_key: str = None):
        self.endpoint = endpoint or os.environ.get("WEBSERP_URL")
        self.api_key = api_key or os.environ.get("WEBSERP_KEY")

    def search(self, query, limit=10):
        if not self.endpoint:
            raise SearchError("WEBSERP_URL not set")
        hdr = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = http_json(self.endpoint.replace("{q}", urllib.parse.quote_plus(query)), headers=hdr)
        rows = (data.get("results") or data.get("organic_results") or [])[:limit]
        return [Result(r.get("title", ""), r.get("url") or r.get("link", ""), r.get("snippet", ""),
                       self.name, self.rank_score(i, len(rows))) for i, r in enumerate(rows)]


class SearXNGEngine(Engine):
    """SearXNG instance JSON API. Env SEARXNG_URL (e.g. http://localhost:8888)."""
    name = "searxng"

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or os.environ.get("SEARXNG_URL", "http://localhost:8888")).rstrip("/")

    def search(self, query, limit=10):
        data = http_json(f"{self.base_url}/search?" + urllib.parse.urlencode({"q": query, "format": "json"}))
        rows = data.get("results", [])[:limit]
        return [Result(r.get("title", ""), r.get("url", ""), r.get("content", ""), self.name,
                       float(r.get("score") or self.rank_score(i, len(rows)))) for i, r in enumerate(rows)]


class MockEngine(Engine):
    """Offline engine for tests (no emojis, plain ASCII)."""
    def __init__(self, name="mock", seed_urls=None):
        self.name = name
        self.seed_urls = seed_urls or ["https://example.com/a", "https://example.org/b", "https://example.net/c"]

    def search(self, query, limit=10):
        n = min(limit, len(self.seed_urls))
        return [Result(f"{query} - {u.split('/')[-1]}", u, f"mock result for {query}", self.name,
                       self.rank_score(i, n)) for i, u in enumerate(self.seed_urls[:n])]


ENGINES = {c.name: c for c in (DuckDuckGoEngine, BraveEngine, DDGSEngine, WebSerpEngine, SearXNGEngine)}
