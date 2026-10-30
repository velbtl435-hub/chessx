"""Offline: SearXNG score normalization and fusion clamping (no network)."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.search import SearXNGEngine, Result, fuse

PAYLOAD = {"results": [
    {"title": "A", "url": "https://a.example/", "content": "a", "score": 7.5},
    {"title": "B", "url": "https://b.example/", "content": "b", "score": 3.2},
    {"title": "C", "url": "https://c.example/", "content": "c", "score": 1.4},
    {"title": "D", "url": "https://d.example/", "content": "d", "score": 0.0},
    {"title": "E", "url": "https://e.example/", "content": "e"},
    {"title": "F", "url": "https://f.example/", "content": "f", "score": "bad"},
]}


class TestSearXNGScores(unittest.TestCase):
    def test_in_unit_range_and_order_preserved(self):
        res = SearXNGEngine("http://unused").parse(PAYLOAD, 10)
        scores = [r.score for r in res]
        self.assertEqual([r.title for r in res], list("ABCDEF"))
        self.assertTrue(all(0.0 <= s <= 1.0 for s in scores), scores)
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(scores[0], 1.0)

    def test_no_scores_falls_back_to_rank(self):
        rows = [{"title": t, "url": "https://%s.x/" % t} for t in "abc"]
        res = SearXNGEngine("http://unused").parse({"results": rows})
        self.assertEqual([r.score for r in res], [SearXNGEngine.rank_score(i, 3) for i in range(3)])

    def test_limit(self):
        self.assertEqual(len(SearXNGEngine("http://unused").parse(PAYLOAD, 2)), 2)

    def test_fusion_clamps_unbounded_engine_scores(self):
        fused = fuse([[Result("x", "https://x.example/", engine="rogue", score=42.0)],
                      [Result("y", "https://y.example/", engine="neg", score=-3.0)]])
        self.assertEqual({r.url: r.score for r in fused},
                         {"https://x.example/": 1.0, "https://y.example/": 0.0})

    def test_searxng_does_not_dominate_fusion(self):
        sx = SearXNGEngine("http://unused").parse(PAYLOAD, 10)
        other = [Result("Z", "https://z.example/", engine="ddgs", score=1.0)]
        top = fuse([sx, other])
        self.assertLessEqual(max(r.score for r in top if r.engines == ["searxng"]), 1.0)


if __name__ == "__main__":
    unittest.main()
