# chessx_libs.osint - public-source OSINT (Team 1 / Search)

Stdlib only (dnspython optional). Every request: identifiable User-Agent, per-host token bucket,
Retry-After/backoff, SQLite TTL cache, JSONL audit log (secrets redacted). `--offline` = cache only.

```python
from chessx_libs import osint
for f in osint.investigate("example.com", depth=2):        # domain/ip/asn/username/geo/file
    print(f.confidence, f.sources, f.kind, f.title, f.url)
osint.investigate("DrNykterstein", kind="username", sources=["lichess", "chesscom"])
osint.cli.main(["lookup", "8.8.8.8", "--format", "md"])
```
CLI: `python -m chessx_libs.osint [--offline] [--commercial] [--dir D] lookup|sources|pwned|case|audit ...`
(`case list|show|export|delete`, export JSON/CSV/MD). Live smoke: `python -m chessx_libs.osint.e2e`.

| source | kinds | commercial_ok | notes |
|---|---|---|---|
| rdap | domain, ip, asn | yes | rdap.org bootstrap |
| dns | domain, ip | yes | DoH Cloudflare, dns.google fallback, PTR |
| crtsh | domain | yes | CT subdomains, 1 req / 5 s |
| wayback | domain, url | yes | CDX |
| ripestat | ip, asn | yes | sourceapp=chessx |
| internetdb, hackertarget, urlscan, ipapi | ip / domain | **no** | free tiers, non-commercial |
| github, mastodon, bluesky, lichess, chesscom | username | yes | exact username, official APIs, no follower lists, Mastodon opt-out respected |
| nominatim | geo | yes | 1 req/s, OSM attribution |
| metadata | file | yes | local, offline (detective + media.detect) |

Pwned Passwords: `osint.password_count(pw, client)` / `echo pw | python -m chessx_libs.osint pwned`.
Only the 5-char SHA-1 prefix is sent (with Add-Padding); the audit log does not record the password, the
hash or the prefix. No breached-account e-mail lookups, no dark-web sources, no auto-pivot to people
(depth pivots only domain/ip/asn). Tests: `tests/test_osint_*.py` (offline); `CHESSX_E2E=1` for live.
