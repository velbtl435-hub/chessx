"""Fetch pages: requests if available, else urllib. about:demo works offline."""
import urllib.request

DEMO_URL = "about:demo"
DEMO_HTML = """<html><head><title>ChessX ASCII Browser</title></head><body>
<h1>Welcome to ChessX</h1><p>Pages are drawn as colored square tiles. Use the keys below.</p>
<h2>Keys</h2><ul><li>n / p: next / previous link</li><li>Enter or number: open link</li>
<li>b / f: back / forward</li><li>g: address bar</li><li>q: quit</li></ul>
<img alt="chess knight" src="knight.png">
<h2>Links</h2><a href="https://example.com/">Example Domain</a>
<a href="https://lichess.org/">Lichess</a><a href="about:demo">This page again</a></body></html>"""


class FetchError(Exception):
    pass


def fetch(url: str, timeout: float = 10.0) -> tuple:
    """Return (final_url, html). Raises FetchError with a clear message on failure."""
    if not url or url == DEMO_URL:
        return DEMO_URL, DEMO_HTML
    if "://" not in url:
        url = "https://" + url
    headers = {"User-Agent": "Mozilla/5.0 (ChessX ASCII browser)"}
    try:
        try:
            import requests
        except ImportError:
            requests = None
        if requests:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.url, r.text
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            cs = r.headers.get_content_charset() or "utf-8"
            return r.geturl(), r.read().decode(cs, "replace")
    except Exception as e:  # offline, DNS, HTTP error...
        raise FetchError(f"Could not load {url}: {e.__class__.__name__}: {e} (offline? try 'about:demo')") from e
