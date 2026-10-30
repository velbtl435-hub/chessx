"""Real-network end-to-end check of every search engine + fusion.

Run:  python3 -m chessx_libs.search.e2e ["query" ...]
Env:  BRAVE_API_KEY, WEBSERP_URL (+WEBSERP_KEY), SEARXNG_URL. Engines without config are SKIPPED.
      SEARXNG_PUBLIC=1 also probes a few public SearXNG instances when SEARXNG_URL is unset.
Status per engine: ok / skip (not configured) / blocked (DuckDuckGo anti-bot) / error.
"""
import os, sys, time
from .base import SearchError
from .engines import (DuckDuckGoEngine, BraveEngine, DDGSEngine, WebSerpEngine,
                      SearXNGEngine, MockEngine)
from .fusion import fuse, norm_url

QUERIES = ("python-chess", "stockfish")
PUBLIC_SEARXNG = ("https://searx.be", "https://search.inetol.net", "https://priv.au",
                  "https://searx.tiekoetter.com", "https://opnxng.com")


def find_searxng():
    """Returns (base_url or None, reason)."""
    if os.environ.get("SEARXNG_URL"):
        return os.environ["SEARXNG_URL"], "SEARXNG_URL"
    candidates = ["http://localhost:8888"]
    if os.environ.get("SEARXNG_PUBLIC") == "1":
        candidates += list(PUBLIC_SEARXNG)
    for base in candidates:
        try:
            if SearXNGEngine(base).search("chess", 3):
                return base, "probe"
        except Exception:
            continue
    return None, "no SearXNG reachable with format=json (set SEARXNG_URL; tried %s)" % ", ".join(candidates)


def build_engines():
    """[(engine or None, skip_reason)]"""
    out = [(DuckDuckGoEngine(), None), (DDGSEngine(), None)]
    try:
        import ddgs  # noqa: F401
    except ImportError:
        out[1] = (None, "ddgs not installed (pip install ddgs)")
    out.append((BraveEngine(), None) if os.environ.get("BRAVE_API_KEY") else (None, "BRAVE_API_KEY not set"))
    out.append((WebSerpEngine(), None) if os.environ.get("WEBSERP_URL") else (None, "WEBSERP_URL not set"))
    base, why = find_searxng()
    out.append((SearXNGEngine(base), None) if base else (None, why))
    out.append((MockEngine(), None))
    return out


NAMES = ("duckduckgo", "ddgs", "brave", "webserp", "searxng", "mock")


def valid(r):
    return bool(r.title.strip()) and r.url.startswith(("http://", "https://"))


def run_engine(engine, query, limit=10):
    """Returns dict(status, n, valid, latency, error, ddg_attempts)."""
    t = time.perf_counter()
    status, res, err = "ok", [], ""
    try:
        res = engine.search(query, limit)
        if not res:
            status, err = "error", "0 results"
    except SearchError as e:
        err = str(e)
        status = "blocked" if "anomaly" in err else "error"
    except Exception as e:  # unexpected: report, don't crash the table
        status, err = "error", "%s: %s" % (type(e).__name__, e)
    return {"status": status, "n": len(res), "valid": sum(map(valid, res)), "results": res,
            "latency": time.perf_counter() - t, "error": err,
            "ddg_attempts": list(getattr(engine, "attempt_log", []))}


def ddg_summary(attempts):
    blocked = sum(a[-1] == "blocked" for a in attempts)
    ok = [a for a in attempts if a[-1] == "ok"]
    plan = ("%s/%s %s %s" % (ok[0][0], ok[0][1] or "-", ok[0][2].split("//")[1].split(".")[0], ok[0][3])) if ok else "none"
    return "%d attempts, %d anomaly, %d error, winner: %s" % (
        len(attempts), blocked, sum(a[-1] == "error" for a in attempts), plan)


def main(argv=None):
    queries = (argv or sys.argv[1:]) or QUERIES
    engines = build_engines()
    print("%-11s %-14s %-8s %5s %6s %8s  %s" % ("engine", "query", "status", "n", "valid", "latency", "notes"))
    for (eng, skip), name in zip(engines, NAMES):
        for q in queries:
            if eng is None:
                print("%-11s %-14s %-8s %5s %6s %8s  %s" % (name, q, "skip", "-", "-", "-", skip))
                continue
            r = run_engine(eng, q)
            note = r["error"][:90]
            if name == "duckduckgo":
                note = ddg_summary(r["ddg_attempts"]) + ("; " + note if note else "")
            print("%-11s %-14s %-8s %5d %6d %7.2fs  %s" % (name, q, r["status"], r["n"], r["valid"], r["latency"], note))
    live = [e for e, _ in engines if e is not None]
    for q in queries:
        t = time.perf_counter()
        runs = [run_engine(e, q) for e in live]  # sequential: shows which engine failed, unlike multi_search
        fused = fuse([r["results"] for r in runs])
        keys = [norm_url(r.url) for r in fused]
        multi = [r for r in fused if len(r.engines) > 1]
        print("fused       %-14s %-8s %5d %6s %7.2fs  inputs=%s dupes=%d multi-engine=%d%s" % (
            q, "ok" if fused else "error", len(fused), "-", time.perf_counter() - t,
            ",".join("%s:%s" % (e.name, r["status"]) for e, r in zip(live, runs)),
            len(keys) - len(set(keys)), len(multi),
            (" top-agreed=%s %s" % (multi[0].url, multi[0].engines)) if multi else ""))

if __name__ == "__main__":
    main()
