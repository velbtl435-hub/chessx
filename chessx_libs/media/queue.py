"""MediaQueue: worker pool over Downloader with per-host rate limit, retries + backoff."""
import email.utils, queue as _q, threading, time
from .downloader import DEFAULT_MAX_BYTES, DEFAULT_MAX_SECONDS, Downloader
from .robots import RateLimiter

RETRY_STATUS = {429, 500, 502, 503, 504}


def parse_retry_after(value):
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        return max(0.0, email.utils.parsedate_to_datetime(value).timestamp() - time.time())
    except Exception:
        return None


class MediaQueue:
    """q = MediaQueue("out", workers=4, per_host_interval=1.0, retries=3); q.add(url); q.run()

    Retries on 429/5xx/network errors with exponential backoff (backoff * 2**attempt,
    capped at max_backoff); a Retry-After header overrides the computed delay (capped too).
    Robots-disallowed, size-limited and netguard-blocked (SSRF policy) downloads are not retried.
    """
    def __init__(self, dest="downloads", workers=4, per_host_interval=1.0, retries=3, backoff=0.5,
                 max_backoff=30.0, max_bytes=DEFAULT_MAX_BYTES, respect_robots=True, robots_fail_open=False,
                 user_agent="ChessX", timeout=30, allow_private=False,
                 max_seconds=DEFAULT_MAX_SECONDS):
        self.workers, self.retries, self.backoff, self.max_backoff = workers, retries, backoff, max_backoff
        self.dl = Downloader(dest, respect_robots=respect_robots, user_agent=user_agent,
                             max_bytes=max_bytes, timeout=timeout, robots_fail_open=robots_fail_open,
                             limiter=RateLimiter(per_host_interval), allow_private=allow_private,
                     max_seconds=max_seconds)
        self._q, self._lock = _q.Queue(), threading.Lock()
        self.results = []
        self.stats = {"queued": 0, "ok": 0, "failed": 0, "retries": 0, "bytes": 0}

    def add(self, *urls):
        for u in urls:
            self._q.put(u)
            self.stats["queued"] += 1
        return self

    def _retryable(self, r):
        if r.get("ok") or r.get("blocked") or r.get("size_limited") or r.get("error") == "robots.txt disallow":
            return False
        st = r.get("status")
        return st is None or st in RETRY_STATUS

    def _one(self, url):
        for attempt in range(self.retries + 1):
            r = self.dl.fetch(url)
            r["attempts"] = attempt + 1
            if attempt == self.retries or not self._retryable(r):
                return r
            delay = parse_retry_after(r.get("retry_after"))
            delay = min(self.max_backoff, delay if delay is not None else self.backoff * 2 ** attempt)
            with self._lock:
                self.stats["retries"] += 1
            time.sleep(delay)

    def _worker(self):
        while True:
            try:
                url = self._q.get_nowait()
            except _q.Empty:
                return
            r = self._one(url)
            with self._lock:
                self.results.append(r)
                self.stats["ok" if r["ok"] else "failed"] += 1
                self.stats["bytes"] += r.get("bytes", 0)
            self._q.task_done()

    def run(self):
        """Process everything queued; returns results (completion order)."""
        ts = [threading.Thread(target=self._worker, daemon=True) for _ in range(max(1, self.workers))]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        return self.results
