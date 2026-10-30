"""Search package tests.

Offline (always run): fusion dedup + cross-engine agreement bonus with MockEngine.
Real network (opt-in): CHESSX_E2E=1 python3 -m unittest tests.test_search_e2e -v
  Engines without config (BRAVE_API_KEY, WEBSERP_URL, SEARXNG_URL) are skipped, never failed.
  DuckDuckGo is skipped (not failed) when every attempt gets the anti-bot "anomaly" page.
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.search import (DuckDuckGoEngine, BraveEngine, DDGSEngine, WebSerpEngine,
                                SearXNGEngine, MockEngine, fuse, multi_search)
from chessx_libs.search.fusion import norm_url, AGREEMENT_BONUS
from chessx_libs.search import e2e

E2E = os.environ.get("CHESSX_E2E") == "1"
QUERIES = e2e.QUERIES


class TestFusionOffline(unittest.TestCase):
    def test_dedup_and_agreement_bonus(self):
        a = MockEngine("m1", ["https://www.example.com/a/", "https://example.org/b"])
        b = MockEngine("m2", ["https://example.com/a", "https://example.net/c"])
        fused = multi_search([a, b], "q")
        keys = [norm_url(r.url) for r in fused]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(fused[0].engines, ["m1", "m2"])
        self.assertAlmostEqual(fused[0].score, 2.0 + AGREEMENT_BONUS)

    def test_same_engine_duplicate_gets_no_bonus(self):
        r = MockEngine("m1", ["https://example.com/a", "https://www.example.com/a/"]).search("q")
        fused = fuse([r])
        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0].engines, ["m1"])
        self.assertLessEqual(fused[0].score, 1.0)


@unittest.skipUnless(E2E, "real-network E2E: set CHESSX_E2E=1")
class TestSearchE2E(unittest.TestCase):
    def check(self, engine, query):
        r = e2e.run_engine(engine, query)
        print("\n  %-10s %-13s %-7s n=%d latency=%.2fs %s" % (
            engine.name, query, r["status"], r["n"], r["latency"], r["error"][:80]), end="")
        return r

    def assert_results(self, r):
        self.assertEqual(r["status"], "ok", r["error"])
        self.assertGreater(r["n"], 0)
        for res in r["results"]:
            self.assertTrue(res.title.strip(), res)
            self.assertRegex(res.url, r"^https?://")

    def test_duckduckgo(self):
        eng = DuckDuckGoEngine()
        for q in QUERIES:
            with self.subTest(q=q):
                r = self.check(eng, q)
                print("  [%s]" % e2e.ddg_summary(r["ddg_attempts"]), end="")
                if r["status"] == "blocked":
                    self.skipTest("DuckDuckGo anti-bot blocked every attempt: " + r["error"])
                self.assert_results(r)

    def test_ddgs(self):
        try:
            import ddgs  # noqa: F401
        except ImportError:
            self.skipTest("ddgs not installed (pip install ddgs)")
        for q in QUERIES:
            with self.subTest(q=q):
                self.assert_results(self.check(DDGSEngine(), q))

    @unittest.skipUnless(os.environ.get("BRAVE_API_KEY"), "BRAVE_API_KEY not set")
    def test_brave(self):
        for q in QUERIES:
            with self.subTest(q=q):
                self.assert_results(self.check(BraveEngine(), q))

    @unittest.skipUnless(os.environ.get("WEBSERP_URL"), "WEBSERP_URL not set")
    def test_webserp(self):
        for q in QUERIES:
            with self.subTest(q=q):
                self.assert_results(self.check(WebSerpEngine(), q))

    def test_searxng(self):
        base, why = e2e.find_searxng()
        if not base:
            self.skipTest(why)
        for q in QUERIES:
            with self.subTest(q=q):
                self.assert_results(self.check(SearXNGEngine(base), q))

    def test_mock(self):
        for q in QUERIES:
            self.assert_results(self.check(MockEngine(), q))

    def test_fused_real(self):
        live = [e for e, _ in e2e.build_engines() if e is not None]
        for q in QUERIES:
            with self.subTest(q=q):
                runs = [e2e.run_engine(e, q) for e in live]
                ok = [r for r in runs if r["status"] == "ok" and r["results"] and r["results"][0].engine != "mock"]
                fused = fuse([r["results"] for r in runs])
                keys = [norm_url(r.url) for r in fused]
                self.assertEqual(len(keys), len(set(keys)), "duplicate normalized URLs after fusion")
                if len(ok) < 2:
                    self.skipTest("need 2+ real engines ok for agreement check")
                multi = [r for r in fused if len(r.engines) > 1]
                if not multi:  # live engines legitimately disagree sometimes (ddgs rotates backends)
                    self.skipTest("no URL shared between real engines for %r this run" % q)
                for m in multi:  # agreement raises score above every contributing engine's own score
                    own = max(r.score for run in runs for r in run["results"] if norm_url(r.url) == norm_url(m.url))
                    self.assertGreater(m.score, own + AGREEMENT_BONUS - 1e-9)


if __name__ == "__main__":
    unittest.main()
