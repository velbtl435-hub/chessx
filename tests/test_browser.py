import io, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.browser import render_page, parse_html, Browser, FetchError, DEMO_HTML, DEMO_URL, run

PAGES = {"a.com": "<title>A</title><h1>Hi</h1><p>x</p><a href='http://b.com'>B</a><a href='/c'>C</a>",
         "http://b.com": "<h2>B page</h2><img alt='pic'><ul><li>one</li></ul>"}


def fake(url):
    if url == DEMO_URL:
        return url, DEMO_HTML
    if url in PAGES:
        return url, PAGES[url]
    raise FetchError("offline " + url)


class TestBrowser(unittest.TestCase):
    def test_parse(self):
        p = parse_html(PAGES["a.com"], "http://a.com/x")
        self.assertEqual(p.title, "A")
        self.assertEqual([b.kind for b in p.blocks], ["heading", "text", "link", "link"])
        self.assertEqual(p.links[1].href, "http://a.com/c")

    def test_render(self):
        s = render_page(PAGES["http://b.com"], 40)
        self.assertIn("[img] pic", s); self.assertIn("\u25a0 one", s)
        self.assertNotIn("\033[", s)
        self.assertIn("\033[", render_page(DEMO_HTML, 60, color=True))
        self.assertTrue(all(len(l) <= 60 for l in render_page(DEMO_HTML, 60).splitlines()))

    def test_navigation(self):
        b = Browser(fake); b.open("a.com")
        b.handle("n"); self.assertEqual(b.focus, 1); b.handle("p"); b.handle("")
        self.assertEqual(b.url, "http://b.com")
        b.handle("b"); self.assertEqual(b.url, "a.com")
        b.handle("f"); self.assertEqual(b.url, "http://b.com")
        b.handle("g nowhere.x"); self.assertIn("offline", b.error)
        b.handle("1"); self.assertEqual(b.url, DEMO_URL)
        self.assertFalse(b.handle("q"))

    def test_run_headless(self):
        cmds = iter(["n", "q"]); out = io.StringIO()
        b = run(None, input_fn=lambda _: next(cmds), out=out)
        self.assertIn("ChessX", out.getvalue()); self.assertEqual(b.focus, 1)


if __name__ == "__main__":
    unittest.main()
