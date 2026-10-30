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

### Optional packages (pinned, hash-locked)

`requirements.txt` and `requirements-optional.txt` pin exact tested versions (`==`).
`requirements.lock` and `requirements-optional.lock` add every transitive dependency with
SHA-256 hashes (generated with `pip-compile --generate-hashes`, Python 3.13). For a
verified install:

```bash
pip install --require-hashes -r requirements.lock
pip install --require-hashes -r requirements-optional.lock   # heavy reversing extras
```

To refresh: edit the pins, then
`pip-compile --generate-hashes --allow-unsafe --strip-extras -o requirements.lock requirements.txt`
(same for the optional file) and check with `pip-audit -r requirements.lock`.

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
- [x] Desktop version (Tauri) — see [Desktop app](#desktop-app-tauri)
- [ ] STT/TTS and voice mode
- [ ] Final custom name
- [ ] Boot sequence (Linux-style, 5-7s, knight ASCII logo)
- [ ] i18n: EN default + PT + JP in-program
- [ ] Docs in PT and JP (separate files)

## Desktop app (Tauri)

```
       ,....,
     ,::::::<
    ,::/^\"``.
   ,::/, `   e`.
  ,::; |        '.
  ,::|  \___,-.  c)
  ;::|     \   '-'
  ;::|      \
  ;::|   _.=`\
  `;:|.=` _.=`\
    '|_.=`   __\
    `\_..==`` /
     .'.___.-'.
    /          \
   ('--......--')
   /'--......--'\
   `"--......--"`
          C h e s s X
```

ChessX ships as a native desktop app for **Linux, Windows and macOS** built with
[Tauri 2](https://tauri.app). The Python code is not rewritten:

- `chessx.py` + `chessx_libs/` are frozen into a single standalone binary with **PyInstaller**
  (`chessx-engine`), bundled as a Tauri **sidecar** (`externalBin`). No Python needed on the user's machine.
- The Tauri window hosts an **xterm.js** terminal. The Rust side spawns the sidecar inside a real
  pseudo-terminal (`portable-pty`, ConPTY on Windows) and streams I/O both ways, so the boot sequence,
  colors and the interactive shell behave exactly like in a normal terminal.
- The app icon is the ASCII knight above, rendered green-on-black (`desktop/assets/chessx-knight-1024.png`).

```
desktop/
  ui/                 xterm.js front end (index.html, main.js; vendor/ is generated)
  src-tauri/          Rust shell: PTY bridge, tauri.conf.json, icons/, binaries/ (sidecar output)
  scripts/            build_sidecar.py, render_icon.py, copy-vendor.mjs
  assets/             knight.txt (ASCII logo) + rendered 1024px icon
```

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.9+ | plus `pip install pyinstaller` (and `pip install -r requirements.txt` for the full feature set inside the binary) |
| Node.js | 18+ | for the Tauri CLI and xterm.js |
| Rust | stable, 1.90+ | via [rustup](https://rustup.rs) |
| Linux only | | `sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev libayatana-appindicator3-dev patchelf file` (`libpython3.x` too if PyInstaller complains) |
| Windows only | | Visual Studio C++ Build Tools + WebView2 (preinstalled on Windows 10/11) |
| macOS only | | Xcode Command Line Tools (`xcode-select --install`) |

PyInstaller does not cross-compile: build each OS's binary on that OS (or use CI, below).

### Run in development

```bash
cd desktop
npm install
npm run sidecar        # freezes ../chessx.py -> src-tauri/binaries/chessx-engine-<target-triple>
npm run dev            # copies xterm.js into ui/vendor and opens the app with hot reload
```

Re-run `npm run sidecar` whenever the Python code changes. The terminal app keeps working as before
(`python3 chessx.py`); the desktop build does not modify it.

### Build installers

```bash
cd desktop
npm install
npm run sidecar
npm run build
```

Output goes to `desktop/src-tauri/target/release/bundle/`:

| OS | Command (same on every OS) | Artifacts |
|----|----------------------------|-----------|
| Linux | `npm run build` | `appimage/ChessX_<ver>_amd64.AppImage`, `deb/ChessX_<ver>_amd64.deb`, `rpm/ChessX-<ver>-1.x86_64.rpm` |
| Windows | `npm run build` | `msi/ChessX_<ver>_x64_en-US.msi`, `nsis/ChessX_<ver>_x64-setup.exe` |
| macOS | `npm run build` | `macos/ChessX.app`, `dmg/ChessX_<ver>_<arch>.dmg` |

To build only some formats: `npx tauri build --bundles deb` (or `appimage`, `msi`, `nsis`, `dmg`, `app`).
macOS builds are unsigned; first launch needs right-click → Open (or configure signing in `tauri.conf.json`).

### CI releases (GitHub Actions)

`.github/workflows/desktop-release.yml` builds on `ubuntu-22.04`, `windows-latest`, `macos-latest` (Apple Silicon)
and `macos-13` (Intel). Each job freezes the sidecar with PyInstaller, runs its `--selftest`, then builds with
`tauri-action`.

- **Release:** push a tag `desktop-vX.Y.Z` (`git tag desktop-v0.6.0 && git push origin desktop-v0.6.0`) →
  a draft GitHub Release with all installers attached.
- **Artifacts only:** run the workflow manually (Actions → desktop-release → Run workflow) and download the
  `chessx-desktop-<target>` artifacts.

### Regenerating the icon

Edit the ASCII art in `desktop/assets/knight.txt`, then:

```bash
cd desktop
npm run icon     # render_icon.py (Pillow) -> assets/chessx-knight-1024.png, then `tauri icon` -> src-tauri/icons/*
```

## License

Free to use. Personal project in development.

Agents / Agent Factory / TamagóX: see [docs/AGENT_FACTORY.md](docs/AGENT_FACTORY.md) (`python3 chessx.py agent --help`).
