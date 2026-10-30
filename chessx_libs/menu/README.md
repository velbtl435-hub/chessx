# chessx_libs/menu (Team 1)
Unified numbered menu for `chessx.py` (`python3 chessx.py` or `--menu`).
- Every entry lazy-imports its package (`importlib`); an import failure marks the entry
  `[unavailable: reason]` instead of crashing.
- Only public package APIs are called; no package internals are touched.
- 26 `browser/` (run(url)) and 27 `pixelart/` (animate / render_frame) degrade to `[unavailable]`
  when the package or one of its deps is missing. `_future()` is a generic slot for later modules.
- Labels use i18n when a key exists, else English fallback; `MISSING_I18N` lists keys for the i18n team.
