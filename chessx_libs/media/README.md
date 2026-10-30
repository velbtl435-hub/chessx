# chessx_libs.media
Polite downloader that respects robots.txt and rate limits.

- **Origin:** written for ChessX; the robots handling wraps the stdlib `urllib.robotparser`.
- **License:** same as the ChessX repository.
- **Adapted:** per-host robots cache, a per-host minimum-interval rate limiter, a 30 s timeout on downloads, and threaded batch download.
- **API:** `RobotsCache`, `RateLimiter`, `Downloader`, `download`, `batch_download`.
- Dependencies: Python 3 stdlib only.
