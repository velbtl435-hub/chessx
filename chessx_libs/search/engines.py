"""Engine adapters. All network access is guarded; use safe_search() offline."""
import html, os, re, urllib.parse
from typing import List
from .base import Engine, Result, SearchError, http_get, http_json

_TAG = re.compile(r"<[^>]+>")


def _clean(s: str) -> str:
    return html.unescape(_TAG.sub("", s)).strip()


def split_glued_title(title: str, others=()) -> str:
    """ddgs sometimes returns one title glued to the titles of other results, e.g.
    'python-chess - GitHubchess · PyPIchess — docs'. Split on the other titles
    of the same result set and join the pieces with ' | '."""
    known = {o for o in others if o and o != title and len(o) > 5}
    if sum(o in title for o in known) < 2:  # a real title may contain one other title
        return title
    parts = [title]
    for o in sorted(known, key=len, reverse=True):
        nxt = []
        for p in parts:
            if o in p and p not in known:
                bits = p.split(o)
                for i, b in enumerate(bits):
                    if b.strip():
                        nxt.append(b)
                    if i < len(bits) - 1:
                        nxt.append(o)
            else:
                nxt.append(p)
        parts = nxt
    parts = [p.strip(" -|\u00b7\u2014") for p in parts if p.strip(" -|\u00b7\u2014")]
    return " | ".join(parts) if parts else title


class DuckDuckGoEngine(Engine):
    """Scrapes DuckDuckGo's no-JS pages (html. and lite.), no key needed.

    DuckDuckGo intermittently answers scripted clients with a bot-check ("anomaly") page.
    Strategy: curl_cffi browser impersonation first (if installed), then rotating
    User-Agent/Accept-Language headers over html/lite and GET/POST. If every attempt is
    blocked, a clear SearchError is raised (external limitation, not a ChessX bug).
    """
    name = "duckduckgo"
    ENDPOINTS = ("https://html.duckduckgo.com/html/", "https://lite.duckduckgo.com/lite/")
    URL = ENDPOINTS[0] + "?q="  # kept for backwards compatibility
    LINK = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    LITE_LINK = re.compile(r"""<a[^>]+href="([^"]+)"[^>]+class=['"]result-link['"][^>]*>(.*?)</a>""", re.S)
    SNIP = re.compile(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div|td)>', re.S)
    LITE_SNIP = re.compile(r"""class=['"]result-snippet['"][^>]*>(.*?)</td>""", re.S)
    IMPERSONATE = ("chrome", "safari", "firefox")

    def __init__(self, attempts: int = 6, seed=None):
        self.attempts = attempts
        self.last_error = None
        self.attempt_log = []  # (how, impersonate, endpoint, method, outcome) per attempt of last search()
        try:
            from ..crypto.netsec import FingerprintRotator
            self.rotator = FingerprintRotator(seed)
        except Exception:
            self.rotator = None

    def parse(self, page: str, limit: int) -> List[Result]:
        links, snips = self.LINK.findall(page), self.SNIP.findall(page)
        if not links:
            links, snips = self.LITE_LINK.findall(page), self.LITE_SNIP.findall(page)
        out = []
        for i, (href, title) in enumerate(links[:limit]):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            url = q.get("uddg", [href])[0]
            if url.startswith("//"):
                url = "https:" + url
            out.append(Result(_clean(title), url, _clean(snips[i]) if i < len(snips) else "",
                              self.name, self.rank_score(i, limit)))
        return out

    def _plans(self):
        try:
            import curl_cffi  # noqa: F401  optional
            for imp in self.IMPERSONATE:
                yield ("curl_cffi", imp, self.ENDPOINTS[0], "GET")
        except ImportError:
            pass
        for i in range(self.attempts):
            yield ("urllib", None, self.ENDPOINTS[i // 2 % 2], ("POST", "GET")[i % 2])

    def _fetch(self, how, imp, endpoint, method, query):
        form = urllib.parse.urlencode({"q": query})
        if how == "curl_cffi":
            from curl_cffi import requests as creq
            return creq.get(endpoint + "?" + form, impersonate=imp, timeout=15).text
        headers = self.rotator.headers() if self.rotator else {"User-Agent": "Mozilla/5.0"}
        if method == "POST":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            return http_get(endpoint, headers=headers, data=form.encode(), timeout=15).decode("utf-8", "replace")
        return http_get(endpoint + "?" + form, headers=headers, timeout=15).decode("utf-8", "replace")

    def search(self, query, limit=10):
        blocked = 0
        self.attempt_log = []
        for plan in self._plans():
            try:
                page = self._fetch(*plan, query)
            except Exception as e:
                self.last_error = e
                self.attempt_log.append(plan + ("error",))
                continue
            out = self.parse(page, limit)
            if out:
                self.attempt_log.append(plan + ("ok",))
                return out
            if "anomaly" in page:
                blocked += 1
                self.attempt_log.append(plan + ("blocked",))
            else:
                self.attempt_log.append(plan + ("empty",))
                return []  # genuine empty result page
        raise SearchError("duckduckgo served a bot-check (anomaly) page on all %d attempts "
                          "(external anti-bot; use ddgs/Brave/SearXNG instead)" % blocked if blocked
                          else "duckduckgo unreachable: %r" % self.last_error)


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
        titles = [_clean(r.get("title", "")) for r in rows]
        for r, t in zip(rows, titles):
            r["title"] = split_glued_title(t, titles)
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
