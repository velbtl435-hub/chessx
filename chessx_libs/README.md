# chessx_libs
The library packages behind ChessX v0.6. The root `chessx.py` wires them together, and
`python3 chessx.py --selftest` smoke-tests all 14 packages offline.

- **Origin:** split out of the single-file chessx.py v0.5 (kept as `chessx_v05_legacy.py`) and extended.
- **License:** same as the ChessX repository. Third-party dependencies keep their own licenses.
- **Packages:** chess_ai, i18n, interface, crypto, search, media, reversing, voice, windows, sounds,
  detective, bases, scheduler, audit. Each has its own README covering origin, license and what was adapted.

## Dependencies: required vs optional
The **core runs on the Python 3 stdlib alone**. Every third-party package is detected at import time and
has a fallback, so a missing package downgrades a feature instead of breaking ChessX.

**`requirements.txt`: required for the full feature set** (`pip install -r requirements.txt`)

| Area | Packages | Status in code today / fallback without it |
|---|---|---|
| Voice | `pyttsx3` (needs the system eSpeak NG on Linux), `vosk` | **used** by voice: falls back to the espeak-ng/say binary, then noop |
| Search | `ddgs`, `curl_cffi` | **used** by search: ddgs is the most reliable engine; curl_cffi impersonation beats DuckDuckGo's anti-bot more often (urllib + rotating headers otherwise) |
| Crypto | `argon2-cffi` | **used** by crypto.kdf.argon2id: without it, a clearly labelled scrypt fallback (`ARGON2_BACKEND`) |
| Scraping | `requests`, `beautifulsoup4`, `scrapy`, `playwright` | installed for the planned scraper/media features; not imported yet |
| Crypto | `cryptography` | installed for planned hardware-accelerated AEAD; pure-Python primitives are used today |
| Terminal UI | `rich`, `asciimatics`, `urwid` | installed for the planned TUI; plain ANSI rendering today |
| Media/numeric | `pillow`, `numpy` | installed for planned image/audio features; not imported yet |

**`requirements-optional.txt`: optional reversing extras** (`pip install -r requirements-optional.txt`)
- `r2pipe` (also needs the `radare2` binary) and `angr` (large, hundreds of MB). Only advanced reversing uses them.
  `capstone` is used by reversing/disasm when present.

**System packages and data, not installed by pip:**
- `espeak-ng` (Debian/Ubuntu: `apt install espeak-ng`), needed by pyttsx3 on Linux.
- `ffmpeg`, used by voice/stt to convert any WAV to 16 kHz mono for Vosk.
- Vosk models. They are never stored in the repo. Unzip them into `~/.cache/chessx/`
  (e.g. `vosk-model-small-pt-0.3`, `vosk-model-small-en-us-0.15` from https://alphacephei.com/vosk/models),
  or set `CHESSX_VOSK_MODEL` / `CHESSX_MODEL_DIR`.
- Playwright browsers: `python -m playwright install chromium`.
