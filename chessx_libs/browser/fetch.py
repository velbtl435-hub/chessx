"""Fetch pages for the ASCII browser. about:demo works offline.

SEC-01: every network fetch goes through chessx_libs.media.netguard.open_url: http/https only, public IPs only
(v4/v6/mapped), connection pinned to the validated IP, each redirect re-validated (max 5), timeout and size cap.
`requests` is intentionally NOT used: it cannot be pinned to netguard's validated IP without re-implementing
the guard, so it would reopen DNS rebinding / redirect SSRF.
"""
import socket, urllib.error
from chessx_libs.media.netguard import open_url, BlockedURL, ResponseTooLarge

DEMO_URL = "about:demo"
MAX_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 5
DEMO_HTML = """<html><head><title>ChessX ASCII Browser</title></head><body>
<h1>Welcome to ChessX</h1><p>Pages are drawn as colored square tiles. Use the keys below.</p>
<h2>Keys</h2><ul><li>n / p: next / previous link</li><li>Enter or number: open link</li>
<li>b / f: back / forward</li><li>g: address bar</li><li>q: quit</li></ul>
<img alt="chess knight" src="knight.png">
<h2>Links</h2><a href="https://example.com/">Example Domain</a>
<a href="https://lichess.org/">Lichess</a><a href="about:demo">This page again</a></body></html>"""


class FetchError(Exception):
    pass


def _charset(headers):
    try:
        return headers.get_content_charset() or "utf-8"
    except AttributeError:
        return "utf-8"


def fetch(url: str, timeout: float = 10.0, resolver=None) -> tuple:
    """Return (final_url, html). Raises FetchError with a clear message. resolver(host, port)->[ip] for tests."""
    if not url or url == DEMO_URL:
        return DEMO_URL, DEMO_HTML
    if "://" not in url and not url.split(":", 1)[0].lower() in ("file", "data", "javascript", "about", "mailto"):
        url = "https://" + url
    headers = {"User-Agent": "Mozilla/5.0 (ChessX ASCII browser)"}
    try:
        with open_url(url, timeout=timeout, max_bytes=MAX_BYTES, headers=headers, max_redirects=MAX_REDIRECTS,
                      max_seconds=max(30, timeout * 3), resolver=resolver) as r:
            return r.url, r.read().decode(_charset(r.headers), "replace")
    except BlockedURL as e:
        raise FetchError(f"Blocked for safety: {e.reason} ({e.url})") from e
    except ResponseTooLarge as e:
        raise FetchError(f"Page too large or too slow: {e} (limit {MAX_BYTES // (1024 * 1024)} MB)") from e
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            raise FetchError(f"Too many redirects or bad redirect at {e.url} (HTTP {e.code}, max {MAX_REDIRECTS})") from e
        raise FetchError(f"HTTP {e.code} {e.reason} for {e.url}") from e
    except (socket.timeout, TimeoutError) as e:
        raise FetchError(f"Timed out after {timeout:g}s loading {url}") from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise FetchError(f"Could not load {url}: {getattr(e, 'reason', e)} (offline? try 'about:demo')") from e
