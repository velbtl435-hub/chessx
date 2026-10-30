"""Media downloader (video/audio/image) honoring robots.txt and rate limits."""
import os, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from .robots import RobotsCache, RateLimiter

MEDIA_EXT = {"image": (".jpg", ".jpeg", ".png", ".gif", ".webp"),
             "audio": (".mp3", ".ogg", ".wav", ".flac"), "video": (".mp4", ".webm", ".mkv")}


def media_kind(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    return next((k for k, exts in MEDIA_EXT.items() if path.endswith(exts)), "other")


class Downloader:
    def __init__(self, dest="downloads", min_interval=1.0, respect_robots=True, user_agent="ChessX"):
        self.dest, self.ua = dest, user_agent
        self.robots = RobotsCache(user_agent) if respect_robots else None
        self.limiter = RateLimiter(min_interval)

    def fetch(self, url: str, chunk=65536) -> dict:
        if self.robots and not self.robots.allowed(url):
            return {"url": url, "ok": False, "error": "robots.txt disallow"}
        host = urllib.parse.urlparse(url).netloc
        delay = self.robots.crawl_delay(url) if self.robots else None
        self.limiter.wait(host, delay)
        name = os.path.basename(urllib.parse.urlparse(url).path) or "index.html"
        sub = os.path.join(self.dest, media_kind(url))
        os.makedirs(sub, exist_ok=True)
        path = os.path.join(sub, name)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as fh:
                size = 0
                while True:
                    b = r.read(chunk)
                    if not b:
                        break
                    fh.write(b)
                    size += len(b)
            return {"url": url, "ok": True, "path": path, "bytes": size}
        except Exception as e:
            return {"url": url, "ok": False, "error": str(e)}

    def batch(self, urls, workers: int = 4):
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(self.fetch, urls))


def download(url, dest="downloads", **kw):
    return Downloader(dest, **kw).fetch(url)


def batch_download(urls, dest="downloads", workers=4, **kw):
    return Downloader(dest, **kw).batch(urls, workers)
