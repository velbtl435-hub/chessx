"""robots.txt compliance + per-host rate limiting (stdlib urllib.robotparser)."""
import threading, time, urllib.parse, urllib.robotparser


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
    def __init__(self, user_agent: str = "ChessX", fail_open: bool = False):
        self.ua, self.fail_open, self._cache = user_agent, fail_open, {}

    def _parser(self, url: str):
        p = urllib.parse.urlparse(url)
        root = f"{p.scheme}://{p.netloc}"
        if root not in self._cache:
            rp = urllib.robotparser.RobotFileParser(root + "/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None
            self._cache[root] = rp
        return self._cache[root]

    def allowed(self, url: str) -> bool:
        rp = self._parser(url)
        return self.fail_open if rp is None else rp.can_fetch(self.ua, url)

    def crawl_delay(self, url: str):
        rp = self._parser(url)
        return rp.crawl_delay(self.ua) if rp else None
