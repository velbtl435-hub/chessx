# chessx_libs.media
Polite media downloader (robots.txt, per-host rate limits, size cap, retry queue) plus
media generation for ChessX (move sounds, board images, GIFs, text captions).

- **Origin:** written for ChessX; robots handling wraps stdlib `urllib.robotparser`.
- **License:** same as the ChessX repository.
- **Dependencies:** download/queue/text = stdlib only. Optional: `numpy` (gen.audio), `Pillow` (gen.image, gen.gif). Missing ones raise `MissingDependency` with the pip command.

## netguard (SSRF-safe fetching) — public, stable API
`chessx_libs.media.netguard` is the shared guard for anything that fetches a URL taken from input (media downloader,
robots.txt, ASCII browser SEC-01). Stability: these names and keyword arguments are stable, so new keywords will only
be added with defaults. Everything it raises is either `BlockedURL` or an `OSError` subclass.

```python
from chessx_libs.media import netguard as ng
info = ng.check_url(url, allow_private=False, resolver=None)   # -> URLInfo(url, scheme, host, port, addresses)
with ng.open_url(url, timeout=30, max_bytes=ng.DEFAULT_MAX_BYTES, headers=None, allow_private=False,
                 max_redirects=5, max_seconds=None, resolver=None, context=None) as r:
    r.status, r.headers, r.url   # final URL after redirects
    data = r.read(65536)         # read()/read(n); enforces max_bytes and max_seconds
ng.is_public_ip("10.0.0.1")      # False
```
* **Rules:**
  * Only `http` and `https` URLs with a host are accepted.
  * Userinfo (`user:pass@`), control characters and spaces are refused.
  * Every address the host resolves to must be public. Refused ranges: private, loopback, link-local
    (169.254.169.254), CGNAT 100.64/10, multicast, reserved, unspecified and documentation ranges; IPv6 `::1`,
    `fc00::/7` and `fe80::/10`. IPv4-mapped, 6to4 and NAT64 IPv6 addresses are unwrapped and checked as IPv4.
    Legacy IPv4 forms (`2130706433`, `0x7f.1`, `0177.0.0.1`) are treated as literal IPs.
* **Connection:** the socket connects to the validated IP, so there is no second DNS lookup and no rebinding. The
  `Host` header and TLS SNI/certificate checks still use the hostname.
* **Opener:** it has only guarded http/https, redirect and error handlers, and no file, ftp, data or proxy handlers.
* **Redirects:** every redirect hop is validated again. At most `max_redirects` hops are followed (default 5).
  Authorization and Cookie headers are dropped when a redirect goes to another origin.
* **Exceptions:**
  * `BlockedURL(ValueError)`, with `.url` and `.reason`: the URL was refused by policy, including on a redirect hop.
  * `ResponseTooLarge(OSError)`: Content-Length above `max_bytes`, a streamed body over `max_bytes`, or the
    `max_seconds` deadline passed.
  * Otherwise `urllib.error.HTTPError` for 4xx/5xx and too many redirects, and `URLError` or `OSError` for network
    errors.
* **Testing:** `allow_private=True` is an explicit opt-in for local servers in tests; the scheme and userinfo rules
  still apply. `resolver(host, port) -> [ip, ...]` replaces DNS.

## Download
```python
from chessx_libs.media import Downloader, MediaQueue
d = Downloader("downloads", min_interval=1.0, max_bytes=50_000_000, robots_fail_open=False)
r = d.fetch("https://example.org/media/clip")  # dict: ok, path, bytes, mime, kind, detected_by, status, error
```
- **Type detection** (`detect.py`): `Content-Type` header → magic bytes of the first chunk → URL extension. File saved under `dest/<image|audio|video|other>/` with an extension matching the detected type; names never collide (`name-1.png`, ...).
- **Size kill:** `max_bytes` aborts before reading if `Content-Length` is larger, and aborts mid-stream (partial file deleted) otherwise. Result has `size_limited: True` and a clear `error`.
- **robots.txt:** respected by default, `Crawl-delay` honored. `robots_fail_open` decides what happens when robots.txt can't be fetched: `False` (default) = disallow, `True` = allow. 404 = allow all, 401/403 = disallow all.

## Queue
```python
q = MediaQueue("downloads", workers=4, per_host_interval=1.0, retries=3, backoff=0.5, max_bytes=10**8)
q.add(url1, url2); results = q.run(); print(q.stats)  # queued/ok/failed/retries/bytes
```
Retries on 429/5xx/network errors with exponential backoff (capped by `max_backoff`); `Retry-After` (seconds or HTTP date) overrides. No retry for robots disallow, size kill, or other 4xx. Each result has `attempts`.

## Generation (`chessx_libs.media.gen`)
- `gen.audio`: `tone`, `sequence`, `write_wav`, `chess_sound(name, path)` — names: move, capture, check, castle, promote, illegal, game_end (16-bit mono WAV).
- `gen.image`: `board_image(fen, square=60, flip=False, highlight=["e2","e4"])`, `save_board`, `banner(text, path=...)`.
- `gen.gif`: `animate_fens(fens, path)`, `animate_moves(["e2e4","e7e5"], path)`, `fens_from_moves`.
- `gen.text`: `parse_pgn`, `summarize_pgn`, `describe_san("Qxf7#")`, `move_list_text`, `caption`.
- `gen.board`: minimal FEN model `parse_fen`, `board_to_fen`, `apply_uci` (no legality check).

## Legacy API (kept)
`download`, `batch_download`, `Downloader.batch`, `media_kind`, `RobotsCache`, `RateLimiter`.

## Tests

`test_netguard.py`: blocked cases run offline (literal IPs plus a mock resolver). Fetching, pinning, redirects
and size caps use a local 127.0.0.1 server with `allow_private=True`.

`python3 -m unittest discover -s chessx_libs/media/tests -t .` — fully offline (local `http.server`).
