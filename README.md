# ChessX v0.5

Agentic meta-search in the terminal. Aggregates results from multiple search engines,
fuses them by URL, displays them on a board of squares, and lets you navigate by keyboard.

## Engines

- **DuckDuckGo** — HTML scraping, no key required
- **Brave Search** — API (export `BRAVE_API_KEY` before running)
- **Startpage, Searx, Bing, Google** — mocks for now

## Install

```bash
git clone https://github.com/velbtl435-hub/chessx.git
cd chessx
python3 chessx.py
```

Python 3.8 or higher. No external dependencies.

## Commands

| Key | Action |
|-----|--------|
| Enter | Open result in browser |
| d | Show detail without opening |
| Tab / Shift+Tab | Move cursor |
| n / p | Next / previous page |
| s | Save as JSON or CSV |
| r | Refresh search |
| a | Auto-refresh (min 5s) |
| aa | Disable auto-refresh |
| q | Quit |

## Math engine
`prof`, `math`, `draw` (ASCII-art equations), `render`, `steps`, `check`, `export`, `translate`, `calc`.
See [MATH_ENGINE.md](MATH_ENGINE.md).

## Structure

- `chessx.py` — everything: engines, fusion, interface, persistence

## Roadmap

- [ ] DuckDuckGo parser tested with real HTML
- [ ] Color palette by type (teal, purple, blue, orange)
- [ ] Emojis and pixel art
- [ ] Source code download with vulnerability scanning
- [ ] Media batch download (video, audio, image)
- [ ] Web version on Vercel
- [ ] Desktop version (Tauri/Electron)
- [ ] STT/TTS and voice mode
- [ ] Final custom name
- [ ] Boot sequence (Linux-style, 5-7s, knight ASCII logo)
- [ ] i18n: EN default + PT + JP in-program
- [ ] Docs in PT and JP (separate files)

## License

Free to use. Personal project in development.

Agents / Agent Factory / TamagóX: see [docs/AGENT_FACTORY.md](docs/AGENT_FACTORY.md) (`python3 chessx.py agent --help`).
