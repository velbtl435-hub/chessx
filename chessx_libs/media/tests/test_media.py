"""Offline tests for chessx_libs.media (local http.server, no real network).
Run: python3 -m unittest discover -s chessx_libs/media/tests -t .
"""
import http.server, os, shutil, tempfile, threading, time, unittest, wave
from chessx_libs.media import (Downloader, MediaQueue, RobotsCache, RateLimiter, detect_type,
                               ext_for, unique_path, parse_retry_after)
from chessx_libs.media.gen import text, board

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 100
COUNTS = {}


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="application/octet-stream", extra=None, clen=True):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if clen:
            self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path
        COUNTS[p] = COUNTS.get(p, 0) + 1
        if p == "/robots.txt":
            return self._send(200, b"User-agent: *\nDisallow: /private\n", "text/plain")
        if p == "/img":
            return self._send(200, PNG, "image/png")
        if p == "/magic.dat":
            return self._send(200, PNG, "application/octet-stream")
        if p == "/song.mp3":
            return self._send(200, b"xxxx", "")
        if p == "/private/x.png":
            return self._send(200, PNG, "image/png")
        if p == "/big":  # declared too big
            return self._send(200, b"a" * 5000, "text/plain")
        if p == "/stream":  # no Content-Length, streams too much
            return self._send(200, b"a" * 200000, "text/plain", clen=False)
        if p == "/flaky":
            if COUNTS[p] <= 2:
                return self._send(429, b"slow down", "text/plain", {"Retry-After": "0"})
            return self._send(200, PNG, "image/png")
        if p == "/err500":
            return self._send(500, b"boom", "text/plain")
        if p == "/404":
            return self._send(404, b"nope", "text/plain")
        return self._send(200, b"hello", "text/plain")


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        COUNTS.clear()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dl(self, **kw):
        kw.setdefault("min_interval", 0)
        kw.setdefault("allow_private", True)
        return Downloader(self.tmp, **kw)


class TestDetection(Base):
    def test_unit(self):
        self.assertEqual(detect_type("image/png; x=1", b"", "a.mp3"), ("image/png", "header"))
        self.assertEqual(detect_type("application/octet-stream", PNG, "a.mp3"), ("image/png", "magic"))
        self.assertEqual(detect_type(None, b"zz", "/a.mp3")[1], "extension")
        self.assertEqual(detect_type(None, b"RIFF\0\0\0\0WAVE", "")[0], "audio/wav")
        self.assertEqual(ext_for("image/jpeg"), ".jpg")

    def test_header(self):
        r = self.dl().fetch(self.base + "/img")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["mime"], r["detected_by"], r["kind"]), ("image/png", "header", "image"))
        self.assertTrue(r["path"].endswith("img.png"))

    def test_magic_and_ext(self):
        r = self.dl().fetch(self.base + "/magic.dat")
        self.assertEqual((r["detected_by"], os.path.splitext(r["path"])[1]), ("magic", ".png"))
        r = self.dl().fetch(self.base + "/song.mp3")
        self.assertEqual((r["detected_by"], r["kind"]), ("extension", "audio"))

    def test_no_collision(self):
        d = self.dl()
        p1, p2 = d.fetch(self.base + "/img")["path"], d.fetch(self.base + "/img")["path"]
        self.assertNotEqual(p1, p2)
        self.assertTrue(os.path.exists(p1) and os.path.exists(p2))
        self.assertTrue(unique_path(self.tmp, "x", ".a").endswith("x.a"))


class TestSizeKill(Base):
    def test_content_length(self):
        r = self.dl(max_bytes=1000).fetch(self.base + "/big")
        self.assertFalse(r["ok"])
        self.assertTrue(r["size_limited"])
        self.assertIn("Content-Length", r["error"])

    def test_mid_stream_deletes_partial(self):
        r = self.dl(max_bytes=70000).fetch(self.base + "/stream")
        self.assertFalse(r["ok"])
        self.assertIn("exceeded max_bytes", r["error"])
        files = [f for _, _, fs in os.walk(self.tmp) for f in fs]
        self.assertEqual(files, [])

    def test_under_limit(self):
        self.assertTrue(self.dl(max_bytes=10000).fetch(self.base + "/big")["ok"])


class TestRobots(Base):
    def test_disallow(self):
        r = self.dl().fetch(self.base + "/private/x.png")
        self.assertEqual(r["error"], "robots.txt disallow")
        self.assertNotIn("/private/x.png", COUNTS)
        self.assertTrue(self.dl(respect_robots=False).fetch(self.base + "/private/x.png")["ok"])

    def test_fail_open_explicit(self):
        dead = "http://127.0.0.1:9/x"  # discard port: connection refused
        self.assertFalse(RobotsCache(fail_open=False).allowed(dead))
        self.assertTrue(RobotsCache(fail_open=True).allowed(dead))


class TestRateLimit(Base):
    def test_limiter(self):
        rl, t = RateLimiter(0.2), time.monotonic()
        for _ in range(3):
            rl.wait("h")
        self.assertGreaterEqual(time.monotonic() - t, 0.38)

    def test_queue_per_host(self):
        q = MediaQueue(self.tmp, allow_private=True, workers=3, per_host_interval=0.25, retries=0)
        q.add(*[self.base + "/img"] * 3)
        t = time.monotonic()
        q.run()
        self.assertGreaterEqual(time.monotonic() - t, 0.45)
        self.assertEqual(q.stats["ok"], 3)


class TestQueueRetries(Base):
    def test_429_retry_after(self):
        q = MediaQueue(self.tmp, allow_private=True, workers=1, per_host_interval=0, retries=3, backoff=0.01)
        res = q.add(self.base + "/flaky").run()
        self.assertTrue(res[0]["ok"], res)
        self.assertEqual(res[0]["attempts"], 3)
        self.assertEqual(q.stats["retries"], 2)

    def test_500_exhausts(self):
        q = MediaQueue(self.tmp, allow_private=True, workers=2, per_host_interval=0, retries=2, backoff=0.01)
        res = q.add(self.base + "/err500", self.base + "/404").run()
        by = {r["url"].rsplit("/", 1)[1]: r for r in res}
        self.assertEqual((by["err500"]["attempts"], by["err500"]["status"]), (3, 500))
        self.assertEqual(by["404"]["attempts"], 1)
        self.assertEqual(q.stats["failed"], 2)

    def test_blocked_not_fetched_nor_retried(self):
        q = MediaQueue(self.tmp, per_host_interval=0, retries=3)  # default: public destinations only
        q.add(self.base + "/img.png", "file:///etc/passwd", "http://169.254.169.254/x").run()
        self.assertEqual(len(q.results), 3)
        for r in q.results:
            self.assertTrue(r["blocked"], r)
            self.assertEqual(r["attempts"], 1)
            self.assertTrue(r["error"].startswith("blocked: "))
        self.assertEqual(q.stats["retries"], 0)
        self.assertEqual(os.listdir(self.tmp), [])

    def test_no_retry_on_robots_or_size(self):
        q = MediaQueue(self.tmp, allow_private=True, per_host_interval=0, retries=3, max_bytes=10)
        res = q.add(self.base + "/private/x.png", self.base + "/big").run()
        self.assertTrue(all(r["attempts"] == 1 for r in res))

    def test_parse_retry_after(self):
        self.assertEqual(parse_retry_after("3"), 3.0)
        self.assertIsNone(parse_retry_after(None))
        self.assertGreaterEqual(parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT"), 0)


class TestGenText(unittest.TestCase):
    PGN = '[Event "Test"]\n[White "Ann"]\n[Black "Bob"]\n1. e4 e5 2. Qh5 {hmm} Nc6 (2... g6) 3. Bc4 Nf6 4. Qxf7# 1-0'

    def test_parse_summary(self):
        h, moves, res = text.parse_pgn(self.PGN)
        self.assertEqual(moves, ["e4", "e5", "Qh5", "Nc6", "Bc4", "Nf6", "Qxf7#"])
        self.assertEqual(res, "1-0")
        s = text.summarize_pgn(self.PGN)
        self.assertIn("Ann vs Bob", s)
        self.assertIn("White wins", s)

    def test_describe(self):
        self.assertEqual(text.describe_san("Qxf7#"), "Queen takes f7, checkmate")
        self.assertEqual(text.describe_san("e8=Q+"), "Pawn to e8, promotes to Queen, check")
        self.assertEqual(text.describe_san("O-O"), "Castles kingside")
        self.assertEqual(text.caption(board.START_FEN), "White to move")
        self.assertEqual(text.move_list_text(["e4", "e5", "Nf3"]), "1. e4 e5 2. Nf3")

    def test_board(self):
        f = board.apply_uci(board.START_FEN, "e2e4")
        self.assertTrue(f.startswith("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b"))
        with self.assertRaises(ValueError):
            board.parse_fen("bad")


try:
    import numpy  # noqa
    HAVE_NP = True
except ImportError:
    HAVE_NP = False
try:
    import PIL  # noqa
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


class TestGenMedia(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @unittest.skipUnless(HAVE_NP, "numpy not installed")
    def test_audio(self):
        from chessx_libs.media.gen import audio
        p = audio.chess_sound("check", os.path.join(self.tmp, "c.wav"))
        with wave.open(p) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, audio.RATE))
            self.assertAlmostEqual(w.getnframes() / w.getframerate(), 0.19, places=2)
        with self.assertRaises(KeyError):
            audio.chess_sound("nope", p)

    @unittest.skipUnless(HAVE_PIL, "Pillow not installed")
    def test_image_gif(self):
        from PIL import Image
        from chessx_libs.media.gen import image, gif
        p = image.save_board(board.START_FEN, os.path.join(self.tmp, "b.png"), square=40)
        with Image.open(p) as im:
            self.assertEqual(im.size, (40 * 8 + 13, 40 * 8 + 13))
        self.assertEqual(image.banner("Hi", size=(300, 100)).size, (300, 100))
        g = gif.animate_moves(["e2e4", "e7e5", "g1f3"], os.path.join(self.tmp, "a.gif"), square=20)
        with Image.open(g) as im:
            self.assertEqual(im.n_frames, 4)

    def test_missing_dep_message(self):
        import builtins
        from chessx_libs.media.gen import _deps
        real = builtins.__import__

        def fake(name, *a, **k):
            if name in ("numpy", "PIL"):
                raise ImportError(name)
            return real(name, *a, **k)
        builtins.__import__ = fake
        try:
            with self.assertRaisesRegex(_deps.MissingDependency, "pip install numpy"):
                _deps.need_numpy()
            with self.assertRaisesRegex(_deps.MissingDependency, "pip install pillow"):
                _deps.need_pil()
        finally:
            builtins.__import__ = real


if __name__ == "__main__":
    unittest.main()
