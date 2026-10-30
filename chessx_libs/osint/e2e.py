"""Live smoke run of every source (python -m chessx_libs.osint.e2e). Prints a table; 429/network = SKIP."""
import sys, time
from .http import Client, HTTPError, RateLimited
from .types import Entity
from .engine import investigate

CASES = [("domain", "example.com"), ("ip", "8.8.8.8"), ("asn", "AS15169"), ("username", "DrNykterstein"),
         ("geo", "Sao Paulo")]


def run(cases=CASES, client=None, out=sys.stdout):
    from .base import sources
    client = client or Client(max_wait=10)
    rows = []
    for kind, value in cases:
        ent = Entity(kind, value)
        for s in sources(kind, commercial=False):
            t0, before = time.time(), len(client.errors)
            try:
                n, st = len(s.lookup(ent, client)), "OK"
            except RateLimited as e:
                n, st = 0, "SKIP(429 %s)" % e
            except (HTTPError, OSError) as e:
                n, st = 0, "SKIP(net %s)" % e
            except Exception as e:  # noqa: BLE001
                n, st = 0, "FAIL(%s: %s)" % (type(e).__name__, e)
            if st == "OK" and n == 0:
                st = "EMPTY"
            rows.append((s.name, str(ent), st, n, round(time.time() - t0, 2)))
            out.write("%-11s %-22s %-6s n=%-4d %.2fs\n" % (s.name, ent, st[:60], n, rows[-1][4]))
    return rows


if __name__ == "__main__":
    r = run()
    sys.exit(1 if any(x[2].startswith("FAIL") for x in r) else 0)
