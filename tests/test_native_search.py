"""c/search core vs the pure-Python reference (chessx_libs/search/fusion.py). Native legs skip if not built."""
import os, random, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.native import search as cs
from chessx_libs.search import fusion
from chessx_libs.search.base import Result

ALPHABET = "abcXYZ019:/?#;.@-_+%= \t\nwW[]"
PIECES = ["https://", "http://", "HTTP://", "//", "www.", "WWW.", "ftp://", "mailto:", "a.com", "/", "//", "?",
          "#", ";", "q=1", "x", "B", " ", "1http:"]


def rand_url(rng):
    return "".join(rng.choice(PIECES) if rng.random() < .6 else rng.choice(ALPHABET) for _ in range(rng.randint(0, 9)))


def rand_lists(rng):
    urls = ["https://a.com/x", "http://www.a.com/x/", "https://b.org", "https://b.org/?", "https://c.net/p;k",
            "https://c.net/p", "https://d.io?q=1"]
    return [[Result("t%d" % i, rng.choice(urls), "s" * rng.randint(0, 5), "e%d" % rng.randint(0, 2),
                    rng.choice([rng.random(), 1.5, -0.2, 0.0, 1.0, "x", None]))
             for i in range(rng.randint(0, 6))] for _ in range(rng.randint(0, 4))]


class TestReference(unittest.TestCase):
    def test_python_reference_matches_fusion_semantics(self):
        rng = random.Random(7)
        for _ in range(300):
            lists = rand_lists(rng)
            flat = [r for l in lists for r in l]
            eng = {}
            items = [(eng.setdefault(r.engine, len(eng)), cs.to_fixed(r.score), r.url) for r in flat]
            _, gs, order = cs.fuse_py(items)
            ref = fusion._fuse_py(lists)
            self.assertEqual(len(ref), len(order))
            for r, g in zip(ref, order):
                self.assertAlmostEqual(r.score, gs[g] / cs.ONE, places=7)

    def test_to_fixed(self):
        self.assertEqual([cs.to_fixed(x) for x in (2, -1, "x", None, 0.5, float("nan"))],
                         [cs.ONE, 0, 0, 0, cs.ONE // 2, 0])


@unittest.skipUnless(cs.backend() == "native", "libcx_search not built (make -C c native)")
class TestNative(unittest.TestCase):
    def test_norm_url_fuzz(self):
        rng = random.Random(1)
        for _ in range(3000):
            u = rand_url(rng)
            if cs.native_ok(u):
                try:
                    want = cs.norm_url_py(u)
                except ValueError:
                    continue
                self.assertEqual(cs.norm_url(u), want, repr(u))

    def test_fuse_native_equals_python(self):
        rng = random.Random(3)
        for _ in range(500):
            lists = rand_lists(rng)
            got, ref = fusion.fuse(lists), fusion._fuse_py(lists)
            self.assertEqual([(r.url, r.engines, r.snippet) for r in got], [(r.url, r.engines, r.snippet) for r in ref])
            for a, b in zip(got, ref):
                self.assertAlmostEqual(a.score, b.score, places=7)

    def test_rank_stable(self):
        self.assertEqual(cs.rank([5, 3, 5, 9]), [3, 0, 2, 1])

    def test_non_ascii_falls_back(self):
        self.assertEqual(cs.norm_url("https://WWW.Ünï.de/a/"), "ünï.de/a")


if __name__ == "__main__":
    unittest.main()
