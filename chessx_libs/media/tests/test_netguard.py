"""netguard tests: offline (literal IPs + mock resolver) and a local 127.0.0.1 server via allow_private=True."""
import http.server, threading, unittest, urllib.error
from unittest import mock
from chessx_libs.media import netguard as ng


class _H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.path
        if p == "/ok":
            return self._send(200, b"hello")
        if p == "/host":
            return self._send(200, (self.headers.get("Host") or "").encode())
        if p == "/big":
            return self._send(200, b"x" * 5000)
        if p == "/nolen":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"y" * 5000)
            self.close_connection = True
            return
        if p.startswith("/chain/"):
            n = int(p.rsplit("/", 1)[1])
            return self._redirect("/ok" if n == 0 else f"/chain/{n - 1}")
        targets = {"/to-file": "file:///etc/passwd", "/to-meta": "http://169.254.169.254/latest/meta-data/",
                   "/to-ftp": "ftp://example.com/x", "/to-loopback-name": "http://internal.test/ok"}
        if p in targets:
            return self._redirect(targets[p])
        self._send(404, b"nope")

    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, loc):
        self.send_response(302)
        self.send_header("Location", loc)
        self.send_header("Content-Length", "0")
        self.end_headers()


class TestCheckURL(unittest.TestCase):
    BLOCKED = ["file:///etc/passwd", "ftp://example.com/", "data:text/plain,hi", "gopher://x/", "javascript:alert(1)",
               "example.com/x", "//example.com/x", "http://user:pw@8.8.8.8/", "http://@8.8.8.8/", "http:///nohost",
               "http://8.8.8.8/a b", "http://8.8.8.8/\r\nX: y", "http://8.8.8.8:99999/",
               "http://127.0.0.1/", "http://127.1/", "http://2130706433/", "http://0x7f.1/", "http://0177.0.0.1/",
               "http://0x7f000001/", "http://10.0.0.1/", "http://172.16.5.4/", "http://192.168.1.1/",
               "http://169.254.169.254/", "http://100.64.0.1/", "http://0.0.0.0/", "http://224.0.0.1/",
               "http://240.0.0.1/", "http://255.255.255.255/", "http://192.0.2.1/", "http://198.18.0.1/",
               "http://[::1]/", "http://[::]/", "http://[fe80::1]/", "http://[fc00::1]/", "http://[fd12::1]/",
               "http://[ff02::1]/", "http://[::ffff:127.0.0.1]/", "http://[::ffff:10.0.0.1]/",
               "http://[::ffff:7f00:1]/", "http://[64:ff9b::7f00:1]/", "http://[2002:7f00:1::]/",
               "http://[2001:db8::1]/", "https://localhost./"]

    def test_blocked(self):
        res = lambda h, p: {"localhost": ["127.0.0.1"]}.get(h, [])  # noqa: E731
        for u in self.BLOCKED:
            with self.subTest(u=u), self.assertRaises(ng.BlockedURL) as cm:
                ng.check_url(u, resolver=res)
            self.assertIsInstance(cm.exception, ValueError)
            self.assertTrue(cm.exception.reason)

    def test_public_literals_and_resolver(self):
        i = ng.check_url("https://8.8.8.8/x")
        self.assertEqual((i.scheme, i.host, i.port, i.addresses), ("https", "8.8.8.8", 443, ("8.8.8.8",)))
        self.assertEqual(ng.check_url("http://[2606:4700::1111]:8080/").addresses, ("2606:4700::1111",))
        i = ng.check_url("HTTP://Example.COM./p", resolver=lambda h, p: ["93.184.216.34", "93.184.216.34"])
        self.assertEqual((i.host, i.port, i.addresses), ("example.com", 80, ("93.184.216.34",)))

    def test_resolver_any_private_blocks(self):  # DNS answer mixing public + private (rebinding style)
        for addrs in (["93.184.216.34", "127.0.0.1"], ["10.1.2.3"], ["::1"], ["::ffff:192.168.0.1"], [], ["bogus"]):
            with self.subTest(addrs=addrs), self.assertRaises(ng.BlockedURL):
                ng.check_url("http://evil.test/", resolver=lambda h, p, a=addrs: a)

    def test_resolver_error_blocks(self):
        def boom(h, p):
            raise OSError("nxdomain")
        with self.assertRaises(ng.BlockedURL):
            ng.check_url("http://nx.test/", resolver=boom)

    def test_allow_private_keeps_scheme_rules(self):
        self.assertEqual(ng.check_url("http://127.0.0.1:1/", allow_private=True).addresses, ("127.0.0.1",))
        for u in ("file:///etc/passwd", "http://u@127.0.0.1/"):
            with self.assertRaises(ng.BlockedURL):
                ng.check_url(u, allow_private=True)

    def test_is_public_ip(self):
        self.assertTrue(ng.is_public_ip("1.1.1.1"))
        self.assertFalse(ng.is_public_ip("::ffff:169.254.169.254"))

    def test_open_url_blocked_offline(self):
        for u in ("file:///etc/passwd", "http://169.254.169.254/", "http://[::1]:1/"):
            with self.assertRaises(ng.BlockedURL):
                ng.open_url(u, timeout=1)

    def test_opener_has_no_file_ftp_data_proxy(self):
        names = {type(h).__name__ for h in ng.build_opener().handlers}
        for bad in ("FileHandler", "FTPHandler", "DataHandler", "ProxyHandler", "HTTPHandler", "HTTPSHandler"):
            self.assertNotIn(bad, names)


class TestOpenURLLocal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def open(self, path, **kw):
        kw.setdefault("allow_private", True)
        return ng.open_url(self.base + path, timeout=5, **kw)

    def test_ok_and_default_blocks_loopback(self):
        with self.open("/ok") as r:
            self.assertEqual((r.status, r.read()), (200, b"hello"))
        with self.assertRaises(ng.BlockedURL):
            ng.open_url(self.base + "/ok", timeout=5)

    def test_pinned_ip_keeps_hostname(self):  # connects to the validated IP, Host header keeps the name
        seen = []

        def res(h, p):
            seen.append(h)
            return ["127.0.0.1"]
        with ng.open_url(f"http://pinned.test:{self.port}/host", timeout=5, allow_private=True, resolver=res) as r:
            self.assertEqual(r.read(), f"pinned.test:{self.port}".encode())
        self.assertIn("pinned.test", seen)

    def test_fallback_to_next_validated_ip(self):  # 127.0.0.2:<port> is closed -> refused fast
        tried = []
        real = ng.socket.create_connection

        def spy(addr, *a, **k):
            tried.append(addr[0])
            return real(addr, *a, **k)
        with mock.patch.object(ng.socket, "create_connection", spy):
            with ng.open_url(f"http://multi.test:{self.port}/ok", timeout=5, allow_private=True,
                             resolver=lambda h, p: ["127.0.0.2", "127.0.0.1"]) as r:
                self.assertEqual((r.status, r.read()), (200, b"hello"))
        self.assertEqual(tried, ["127.0.0.2", "127.0.0.1"])

    def test_fallback_all_fail(self):
        tried = []
        real = ng.socket.create_connection

        def spy(addr, *a, **k):
            tried.append(addr[0])
            return real(addr, *a, **k)
        with mock.patch.object(ng.socket, "create_connection", spy):
            with self.assertRaises(OSError) as cm:  # URLError wrapping the last connect error
                ng.open_url(f"http://dead.test:{self.port}/ok", timeout=5, allow_private=True,
                            resolver=lambda h, p: ["127.0.0.2", "127.0.0.3"])
        self.assertNotIsInstance(cm.exception, ng.BlockedURL)
        self.assertEqual(tried, ["127.0.0.2", "127.0.0.3"])  # only validated addresses, in order

    def test_no_retry_after_response(self):  # an HTTP error response is final: no second address tried
        tried = []
        real = ng.socket.create_connection

        def spy(addr, *a, **k):
            tried.append(addr[0])
            return real(addr, *a, **k)
        with mock.patch.object(ng.socket, "create_connection", spy):
            with self.assertRaises(urllib.error.HTTPError):
                ng.open_url(f"http://multi.test:{self.port}/nope-404", timeout=5, allow_private=True,
                            resolver=lambda h, p: ["127.0.0.1", "127.0.0.2"])
        self.assertEqual(tried, ["127.0.0.1"])

    def test_rebinding_pinned(self):  # second lookup would say 10.x: connection still goes to the checked IP
        answers = iter([["127.0.0.1"]] * 2 + [["10.9.9.9"]] * 10)
        with ng.open_url(f"http://rebind.test:{self.port}/ok", timeout=5, allow_private=True,
                         resolver=lambda h, p: next(answers)) as r:
            self.assertEqual(r.read(), b"hello")

    def test_redirects_revalidated(self):
        for path in ("/to-file", "/to-ftp"):
            with self.subTest(path=path), self.assertRaises(ng.BlockedURL):
                self.open(path)
        def res(h, p):  # second hop's host does not resolve -> refused at the hop, not followed
            if h == "internal.test":
                raise OSError("nxdomain")
            return ["127.0.0.1"]
        with self.assertRaises(ng.BlockedURL):
            ng.open_url(f"http://first.test:{self.port}/to-loopback-name", timeout=5, allow_private=True,
                        resolver=res)

    def test_redirect_handler_public_mode(self):
        import urllib.request
        h = ng._GuardedRedirect(5, False, lambda host, p: {"pub.test": ["93.184.216.34"]}.get(host, ["10.0.0.7"]))
        req = urllib.request.Request("http://pub.test/a", headers={"Authorization": "x", "Cookie": "c"})
        for bad in ("http://169.254.169.254/latest/", "http://inner.test/", "file:///etc/passwd", "http://[::1]/"):
            with self.subTest(bad=bad), self.assertRaises(ng.BlockedURL):
                h.redirect_request(req, None, 302, "Found", {}, bad)
        new = h.redirect_request(req, None, 302, "Found", {}, "http://8.8.8.8/b")
        self.assertFalse({k.lower() for k in new.headers} & {"authorization", "cookie"})
        same = h.redirect_request(req, None, 302, "Found", {}, "http://pub.test/b")
        self.assertIn("authorization", {k.lower() for k in same.headers})

    def test_redirect_limit(self):
        with self.open("/chain/4") as r:  # /chain/N = N+1 redirects -> exactly 5
            self.assertEqual((r.read(), r.url), (b"hello", self.base + "/ok"))
        with self.assertRaises(urllib.error.HTTPError):
            self.open("/chain/5")  # 6 redirects
        with self.assertRaises(urllib.error.HTTPError):
            self.open("/chain/1", max_redirects=0)

    def test_size_caps(self):
        with self.assertRaises(ng.ResponseTooLarge):
            self.open("/big", max_bytes=1000)
        with self.open("/nolen", max_bytes=1000) as r, self.assertRaises(ng.ResponseTooLarge):
            while r.read(300):
                pass
        with self.open("/nolen", max_bytes=None) as r:
            self.assertEqual(len(r.read()), 5000)

    def test_http_error(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.open("/missing")
        self.assertEqual(cm.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
