# c/search - ChessX search core (Search Engineer, Team 1)
C99 port of `chessx_libs/search/fusion.py`: `cx_norm_url` (same rules as `norm_url`, i.e. urllib.parse.urlparse:
lowercase host without `www.`, path without trailing `/` and `;params`, `?query` kept, fragment dropped),
`cx_search_fuse` (dedupe by normalised URL; a different engine agreeing adds score + 0.25, the same engine keeps
the max; every input score clamped to [0, 1]) and `cx_search_rank` (stable score-desc ranking).
Scores are fixed point (1.0 = 1e9) so native and wasm are bit-identical. ASCII URLs only; the Python wrapper
(`chessx_libs/native/search.py`) keeps non-ASCII and `[IPv6]` URLs on the pure-Python path.
CLI: `search_cli norm <url> | fuse e:s:url ... | rank s ...`. Parity: `c/search/vectors.txt`, `make -C c test`.
Python: `chessx_libs.search.fuse()` uses this core automatically when `libcx_search` is built.
