"""Media downloader (video/audio/image) honoring robots.txt, rate limits and a size cap.

Type is detected from the Content-Type header, then magic bytes, then URL extension;
the saved filename gets an extension matching the detected type and never overwrites.
"""
import os, threading, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from .robots import RobotsCache, RateLimiter
from .detect import detect_type, kind_of, ext_for, unique_path

MEDIA_EXT = {"image": (".jpg", ".jpeg", ".png", ".gif", ".webp"),
             "audio": (".mp3", ".ogg", ".wav", ".flac"), "video": (".mp4", ".webm", ".mkv")}


class SizeLimitExceeded(Exception):
    pass


def media_kind(url: str) -> str:
    """Legacy: kind guessed from URL extension only."""
    path = urllib.parse.urlparse(url).path.lower()
    return next((k for k, exts in MEDIA_EXT.items() if path.endswith(exts)), "other")


class Downloader:
    def __init__(self, dest="downloads", min_interval=1.0, respect_robots=True, user_agent="ChessX",
                 max_bytes=None, timeout=30, robots_fail_open=False, limiter=None):
        self.dest, self.ua, self.max_bytes, self.timeout = dest, user_agent, max_bytes, timeout
        self.robots = RobotsCache(user_agent, fail_open=robots_fail_open) if respect_robots else None
        self.limiter = limiter or RateLimiter(min_interval)
        self._name_lock = threading.Lock()

    def fetch(self, url: str, chunk=65536) -> dict:
        res = {"url": url, "ok": False}
        if self.robots and not self.robots.allowed(url):
            return {**res, "error": "robots.txt disallow", "status": None}
        host = urllib.parse.urlparse(url).netloc
        self.limiter.wait(host, self.robots.crawl_delay(url) if self.robots else None)
        path = None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                res["status"] = r.status
                clen = r.headers.get("Content-Length")
                if self.max_bytes is not None and clen and clen.isdigit() and int(clen) > self.max_bytes:
                    raise SizeLimitExceeded(f"Content-Length {clen} > max_bytes {self.max_bytes}")
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
                        if self.max_bytes is not None and size > self.max_bytes:
                            raise SizeLimitExceeded(f"stream exceeded max_bytes {self.max_bytes}")
                        fh.write(b)
                        b = r.read(chunk)
            return {**res, "ok": True, "path": path, "bytes": size, "mime": mime,
                    "kind": kind, "detected_by": src}
        except Exception as e:
            if path and os.path.exists(path):
                os.remove(path)
            if isinstance(e, urllib.error.HTTPError):
                res.update(status=e.code, retry_after=e.headers.get("Retry-After") if e.headers else None)
            if isinstance(e, SizeLimitExceeded):
                res["size_limited"] = True
            return {**res, "error": f"{type(e).__name__}: {e}"}

    def batch(self, urls, workers: int = 4):
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(self.fetch, urls))


def download(url, dest="downloads", **kw):
    return Downloader(dest, **kw).fetch(url)


def batch_download(urls, dest="downloads", workers=4, **kw):
    return Downloader(dest, **kw).batch(urls, workers)
