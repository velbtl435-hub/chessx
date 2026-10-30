# chessx_libs.media
Polite media downloader (robots.txt, per-host rate limits, size cap, retry queue) plus
media generation for ChessX (move sounds, board images, GIFs, text captions).

- **Origin:** written for ChessX; robots handling wraps stdlib `urllib.robotparser`.
- **License:** same as the ChessX repository.
- **Dependencies:** download/queue/text = stdlib only. Optional: `numpy` (gen.audio), `Pillow` (gen.image, gen.gif). Missing ones raise `MissingDependency` with the pip command.

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
`python3 -m unittest discover -s chessx_libs/media/tests -t .` — fully offline (local `http.server`).
