"""Media downloader (video/audio/image) honoring robots.txt, rate limits and a size cap.

Type is detected from the Content-Type header, then magic bytes, then URL extension;
the saved filename gets an extension matching the detected type and never overwrites.
"""
import os, threading, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from . import netguard
from .robots import RobotsCache, RateLimiter
from .detect import detect_type, kind_of, ext_for, unique_path

MEDIA_EXT = {"image": (".jpg", ".jpeg", ".png", ".gif", ".webp"),
             "audio": (".mp3", ".ogg", ".wav", ".flac"), "video": (".mp4", ".webm", ".mkv")}


class SizeLimitExceeded(netguard.ResponseTooLarge):
    """Kept for compatibility; size/deadline failures from netguard are ResponseTooLarge (its base)."""


def media_kind(url: str) -> str:
    """Legacy: kind guessed from URL extension only."""
    path = urllib.parse.urlparse(url).path.lower()
    return next((k for k, exts in MEDIA_EXT.items() if path.endswith(exts)), "other")


class Downloader:
    def __init__(self, dest="downloads", min_interval=1.0, respect_robots=True, user_agent="ChessX",
                 max_bytes=None, timeout=30, robots_fail_open=False, limiter=None, allow_private=False):
        """All fetches go through netguard (http/https only, public destinations, guarded redirects).
        allow_private=True is an explicit opt-in (local test servers)."""
        self.dest, self.ua, self.max_bytes, self.timeout = dest, user_agent, max_bytes, timeout
        self.allow_private = allow_private
        self.robots = RobotsCache(user_agent, fail_open=robots_fail_open, timeout=timeout,
                                  allow_private=allow_private) if respect_robots else None
        self.limiter = limiter or RateLimiter(min_interval)
        self._name_lock = threading.Lock()

    def fetch(self, url: str, chunk=65536) -> dict:
        res = {"url": url, "ok": False}
        try:
            netguard.check_url(url, self.allow_private)
        except netguard.BlockedURL as e:  # never touches the network (no robots fetch either)
            return {**res, "error": f"blocked: {e.reason}", "blocked": True, "status": None}
        if self.robots and not self.robots.allowed(url):
            return {**res, "error": "robots.txt disallow", "status": None}
        host = urllib.parse.urlparse(url).netloc
        self.limiter.wait(host, self.robots.crawl_delay(url) if self.robots else None)
        path = None
        try:
            with netguard.open_url(url, timeout=self.timeout, max_bytes=self.max_bytes,
                                   headers={"User-Agent": self.ua}, allow_private=self.allow_private) as r:
                res["status"] = r.status
                first = r.read(chunk)
                mime, src = detect_type(r.headers.get("Content-Type"), first, url)
                kind = kind_of(mime)
                sub = os.path.join(self.dest, kind)
                os.makedirs(sub, exist_ok=True)
                stem = os.path.splitext(os.path.basename(urllib.parse.urlparse(url).path))[0] or "index"
                with self._name_lock:
                    path = unique_path(sub, stem, ext_for(mime, url))
                    open(path, "wb").close()  # reserve name
                size = 0
                with open(path, "wb") as fh:
                    b = first
                    while b:
                        size += len(b)
                        fh.write(b)
                        b = r.read(chunk)
            return {**res, "ok": True, "path": path, "bytes": size, "mime": mime,
                    "kind": kind, "detected_by": src}
        except Exception as e:
            if path and os.path.exists(path):
                os.remove(path)
            if isinstance(e, urllib.error.HTTPError):
                res.update(status=e.code, retry_after=e.headers.get("Retry-After") if e.headers else None)
            if isinstance(e, netguard.ResponseTooLarge):
                res["size_limited"] = True
            if isinstance(e, netguard.BlockedURL):  # e.g. a redirect hop to a private address
                res["blocked"] = True
                return {**res, "error": f"blocked: {e.reason}"}
            return {**res, "error": f"{type(e).__name__}: {e}"}

    def batch(self, urls, workers: int = 4):
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(self.fetch, urls))


def download(url, dest="downloads", **kw):
    return Downloader(dest, **kw).fetch(url)


def batch_download(urls, dest="downloads", workers=4, **kw):
    return Downloader(dest, **kw).batch(urls, workers)
