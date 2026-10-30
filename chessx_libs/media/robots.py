"""robots.txt compliance + per-host rate limiting (stdlib urllib.robotparser)."""
import threading, time, urllib.error, urllib.parse, urllib.robotparser
from . import netguard

ROBOTS_MAX_BYTES = 512 * 1024


class RateLimiter:
    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._last = {}
        self._lock = threading.Lock()

    def wait(self, host: str, interval: float = None):
        interval = self.min_interval if interval is None else interval
        with self._lock:
            now = time.monotonic()
            delay = self._last.get(host, 0) + interval - now
            self._last[host] = max(now, self._last.get(host, 0) + interval)
        if delay > 0:
            time.sleep(delay)
        return max(delay, 0)


class RobotsCache:
    """Per-host robots.txt cache.

    fail_open controls what happens when robots.txt cannot be fetched (network error,
    timeout): False (default) = treat as disallowed, True = treat as allowed.
    A 404 means "allow all"; 401/403 means "disallow all" (urllib.robotparser rules).
    robots.txt is fetched through netguard (timeout, ROBOTS_MAX_BYTES cap, guarded redirects);
    a URL that netguard blocks is never fetched and is reported as not allowed.
    Crawl-delay is exposed via crawl_delay() and honored by Downloader/MediaQueue.
    """
    def __init__(self, user_agent: str = "ChessX", fail_open: bool = False,
                 timeout: float = 15, allow_private: bool = False):
        self.ua, self.fail_open, self._cache = user_agent, fail_open, {}
        self.timeout, self.allow_private = timeout, allow_private
        self._lock = threading.Lock()

    def _parser(self, url: str):
        p = urllib.parse.urlparse(url)
        root = f"{p.scheme}://{p.netloc}"
        if root not in self._cache:
            rp = self._fetch(root + "/robots.txt")
            with self._lock:
                self._cache[root] = rp
        return self._cache[root]

    def _fetch(self, robots_url: str):
        rp = urllib.robotparser.RobotFileParser(robots_url)
        try:
            with netguard.open_url(robots_url, timeout=self.timeout, max_bytes=ROBOTS_MAX_BYTES,
                                   headers={"User-Agent": self.ua},
                                   allow_private=self.allow_private) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                rp.disallow_all = True
            elif 400 <= e.code < 500:
                rp.allow_all = True
            else:
                return None
            return rp
        except Exception:  # network error, timeout, oversize, blocked redirect -> fail_open policy
            return None
        rp.parse(raw.decode("utf-8", "replace").splitlines())
        return rp

    def allowed(self, url: str) -> bool:
        try:
            netguard.check_url(url, self.allow_private)
        except netguard.BlockedURL:
            return False
        rp = self._parser(url)
        return self.fail_open if rp is None else rp.can_fetch(self.ua, url)

    def crawl_delay(self, url: str):
        try:
            netguard.check_url(url, self.allow_private)
        except netguard.BlockedURL:
            return None
        rp = self._parser(url)
        return rp.crawl_delay(self.ua) if rp else None
