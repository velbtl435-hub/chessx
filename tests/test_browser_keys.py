import io, os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.browser import Browser, KeyState, handle_key, run, DEMO_URL, DEMO_HTML, FetchError
from chessx_libs.browser import app, keys

PAGES = {"a.com": "<title>A</title>" + "".join(f"<p>line {i}</p>" for i in range(40)) +
         "<a href='http://b.com'>B</a><a href='http://c.com'>C</a>",
         "http://b.com": "<h1>B</h1>", "http://c.com": "<h1>C</h1>"}


def fake(u):
    if u == DEMO_URL:
        return u, DEMO_HTML
    if u in PAGES:
        return u, PAGES[u]
    raise FetchError("offline " + u)


class TestKeys(unittest.TestCase):
    def setUp(self):
        self.b = Browser(fake); self.b.open("a.com"); self.st = KeyState(page_h=10)

    def k(self, key, total=60, prompt=None):
        return handle_key(self.b, self.st, key, total, prompt)

    def test_links_and_history(self):
        self.k("n"); self.assertEqual(self.b.focus, 1)
        self.k("p"); self.k("p"); self.assertEqual(self.b.focus, 1)
        self.k(keys.ENTER); self.assertEqual(self.b.url, "http://c.com")
        self.k("b"); self.assertEqual(self.b.url, "a.com")
        self.k("f"); self.assertEqual(self.b.url, "http://c.com")
        self.assertEqual(self.k("q"), "quit")

    def test_digits(self):
        self.k("1"); self.assertEqual(self.st.digits, "1")
        self.k(keys.ENTER); self.assertEqual(self.b.url, "http://b.com")
        self.k("b"); self.k("9"); self.k(keys.ENTER)
        self.assertEqual(self.b.url, "a.com"); self.assertIn("no link", self.st.status)
        self.k("2"); self.k(keys.ESC); self.assertEqual(self.st.digits, "")

    def test_scroll(self):
        self.k(keys.DOWN); self.assertEqual(self.st.scroll, 1)
        self.k(keys.PGDN); self.assertEqual(self.st.scroll, 10)
        self.k(keys.END); self.assertEqual(self.st.scroll, 50)
        self.k(keys.PGDN); self.assertEqual(self.st.scroll, 50)
        self.k(keys.PGUP); self.assertEqual(self.st.scroll, 41)
        self.k(keys.HOME); self.k(keys.UP); self.assertEqual(self.st.scroll, 0)
        self.assertEqual(self.k("z"), "noop")

    def test_address_bar(self):
        self.k("g", prompt=lambda _: "http://b.com"); self.assertEqual(self.b.url, "http://b.com")
        self.k("g", prompt=lambda _: ""); self.assertEqual(self.b.url, "http://b.com")
        self.k("g", prompt=lambda _: "x.invalid"); self.assertIn("offline", self.b.error)

    def test_ansi_segments(self):
        seg = keys.ansi_segments("ab\033[1;38;5;45mcd\033[0mef")
        self.assertEqual(seg, [("ab", None, False), ("cd", 45, True), ("ef", None, False)])

    def test_mode_selection(self):
        out = io.StringIO()
        self.assertEqual(app._pick_mode(None, lambda _: "q", out), "prompt")
        self.assertEqual(app._pick_mode(None, input, out), "prompt")  # StringIO is not a tty
        self.assertEqual(app._pick_mode("keys", input, out), "keys")
        with mock.patch("chessx_libs.browser.tui.available", return_value=False):
            b = run(None, input_fn=lambda _: "q", out=out, mode="keys")  # falls back
        self.assertEqual(b.url, DEMO_URL)

    @unittest.skipUnless(hasattr(os, "fork") and keys and __import__("importlib").util.find_spec("curses"), "needs pty+curses")
    def test_curses_smoke_in_pty(self):
        import pty, select, time
        pid, fd = pty.fork()
        if pid == 0:
            os.environ["TERM"] = "xterm-256color"
            try:
                b = run(None, mode="keys"); os._exit(0 if b.url == "https://example.com/" else 3)
            except BaseException:
                os._exit(4)
        def drain(t=1.0):
            end = time.time() + t; buf = b""
            while time.time() < end:
                r, _, _ = select.select([fd], [], [], 0.1)
                if r:
                    try:
                        buf += os.read(fd, 65536)
                    except OSError:
                        break
            return buf
        screen = drain()
        for k in (b"1", b"\r"):
            os.write(fd, k); drain(0.3)
        os.write(fd, b"b"); drain(0.3); os.write(fd, b"f"); drain(0.3)
        os.write(fd, b"q"); drain(0.5)
        _, status = os.waitpid(pid, 0)
        self.assertIn(b"ChessX", screen)
        # link 1 of demo is example.com; offline still lands there as an error page with that url
        self.assertEqual(os.WEXITSTATUS(status), 0)


if __name__ == "__main__":
    unittest.main()
