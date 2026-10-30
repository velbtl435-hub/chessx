"""SEC-01: browser fetch() must refuse local files, private/internal targets and abusive redirects.

Network-free: socket.getaddrinfo is mocked and socket.socket is replaced by a fake that serves canned
HTTP responses keyed by the IP actually connected to (so DNS rebinding / wrong-IP connects are visible).
fetch() routes everything through chessx_libs.media.netguard; cases run with requests hidden and visible
to prove `requests` is never used as a bypass.
"""
import io, os, socket, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.browser import fetch, FetchError

PUBLIC = "93.184.216.34"
DNS = {"example.com": [PUBLIC], "evil.test": ["10.0.0.7"], "public.test": [PUBLIC]}


def _resp(status=200, body=b"<h1>ok</h1>", headers=None):
    h = {"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(body))}
    h.update(headers or {})
    h = {k: v for k, v in h.items() if v is not None}
    head = f"HTTP/1.1 {status} X\r\n" + "".join(f"{k}: {v}\r\n" for k, v in h.items()) + "Connection: close\r\n\r\n"
    return head.encode() + body


class Net:
    """Fake network. routes: {(ip, path): bytes}; records every IP connected to."""

    def __init__(self, routes):
        self.routes, self.connected = routes, []

    def getaddrinfo(self, host, port, family=0, type=0, proto=0, flags=0):
        host = host.strip("[]")
        try:
            socket.inet_pton(socket.AF_INET6 if ":" in host else socket.AF_INET, host)
            ips = [host]
        except OSError:
            if host not in DNS:
                raise socket.gaierror(f"no such host {host}")
            ips = DNS[host]
        port = int(port or 80)
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "",
                 (ip, port, 0, 0) if ":" in ip else (ip, port)) for ip in ips]

    def socket_cls(net):
        class FakeSock:
            def __init__(self, family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
                self.family, self.type, self.proto = family, type, proto
                self.ip, self.req, self.buf = None, b"", None
            def connect(self, addr):
                self.ip = addr[0]; net.connected.append(addr[0])
            def connect_ex(self, addr):
                self.connect(addr); return 0
            def settimeout(self, t): pass
            def gettimeout(self): return 10
            def setblocking(self, f): pass
            def setsockopt(self, *a): pass
            def getsockopt(self, *a): return 0
            def fileno(self): return -1
            def getpeername(self): return (self.ip, 80)
            def sendall(self, data):
                self.req += data
            send = lambda self, d: (self.sendall(d), len(d))[1]
            def _out(self):
                if self.buf is None:
                    path = self.req.split(b" ", 2)[1].decode() if self.req else "/"
                    self.buf = io.BytesIO(net.routes.get((self.ip, path), _resp(404, b"nf")))
                return self.buf
            def recv(self, n): return self._out().read(n)
            def recv_into(self, b, n=0):
                d = self._out().read(n or len(b)); b[:len(d)] = d; return len(d)
            def makefile(self, mode="rb", *a, **k): return self._out()
            def shutdown(self, *a): pass
            def close(self): pass
            def detach(self): return -1
        return FakeSock


class SSRFBase:
    use_requests = False

    def go(self, url, routes=None):
        net = Net(routes or {})
        hide = {} if self.use_requests else {"requests": None}
        with mock.patch.dict(sys.modules, hide), \
             mock.patch("socket.getaddrinfo", net.getaddrinfo), \
             mock.patch("socket.socket", net.socket_cls()):
            try:
                return fetch(url), net
            except FetchError as e:
                return e, net

    def assertBlocked(self, url, routes=None):
        r, net = self.go(url, routes)
        self.assertIsInstance(r, FetchError, f"{url} should be blocked, got {r!r}")
        return net

    def test_file_scheme_rejected(self):
        net = self.assertBlocked("file:///etc/passwd"); self.assertEqual(net.connected, [])

    def test_other_schemes_rejected(self):
        for u in ("ftp://example.com/x", "gopher://example.com/", "data:text/html,hi"):
            self.assertBlocked(u)

    def test_private_literals_rejected(self):
        for u in ("http://127.0.0.1/", "http://127.1/", "http://169.254.169.254/latest/meta-data/",
                  "http://10.1.2.3/", "http://192.168.0.1/", "http://172.16.5.4/", "http://100.64.0.1/",
                  "http://0.0.0.0/", "http://224.0.0.1/", "http://240.0.0.1/", "http://[::1]/",
                  "http://[fe80::1]/", "http://[fc00::1]/", "http://[::ffff:127.0.0.1]/",
                  "http://[::ffff:169.254.169.254]/", "http://[::ffff:a00:1]/"):
            with self.subTest(u):
                net = self.assertBlocked(u); self.assertEqual(net.connected, [])

    def test_dns_to_private_rejected(self):
        net = self.assertBlocked("http://evil.test/"); self.assertEqual(net.connected, [])

    def test_redirect_to_private_rejected(self):
        routes = {(PUBLIC, "/"): _resp(302, b"", {"Location": "http://169.254.169.254/latest/"}),
                  ("169.254.169.254", "/latest/"): _resp(200, b"SECRET")}
        net = self.assertBlocked("http://example.com/", routes)
        self.assertNotIn("169.254.169.254", net.connected)

    def test_redirect_to_file_rejected(self):
        self.assertBlocked("http://example.com/", {(PUBLIC, "/"): _resp(301, b"", {"Location": "file:///etc/passwd"})})

    def test_redirect_chain_too_long(self):
        routes = {(PUBLIC, f"/{i}"): _resp(302, b"", {"Location": f"/{i + 1}"}) for i in range(10)}
        routes[(PUBLIC, "/10")] = _resp(200, b"<p>end</p>")
        self.assertBlocked("http://example.com/0", routes)

    def test_redirect_within_limit_ok(self):
        routes = {(PUBLIC, f"/{i}"): _resp(302, b"", {"Location": f"/{i + 1}"}) for i in range(3)}
        routes[(PUBLIC, "/3")] = _resp(200, b"<p>end</p>")
        r, net = self.go("http://example.com/0", routes)
        self.assertNotIsInstance(r, FetchError, r)
        self.assertIn("end", r[1]); self.assertTrue(r[0].endswith("/3"))

    def test_connects_to_validated_ip_only(self):
        r, net = self.go("http://public.test/", {(PUBLIC, "/"): _resp(200, b"<p>hi</p>")})
        self.assertNotIsInstance(r, FetchError, r)
        self.assertTrue(net.connected and set(net.connected) == {PUBLIC})

    def test_oversize_body_capped(self):
        big = b"<p>" + b"A" * (64 * 1024 * 1024) + b"</p>"
        r, net = self.go("http://example.com/", {(PUBLIC, "/"): _resp(200, big)})
        if isinstance(r, FetchError):
            return  # refusing oversize is acceptable
        self.assertLess(len(r[1]), len(big))  # otherwise must be truncated
        self.assertLessEqual(len(r[1]), 16 * 1024 * 1024)

    def test_oversize_streamed_without_length(self):
        big = b"<p>" + b"B" * (32 * 1024 * 1024) + b"</p>"
        r, net = self.go("http://example.com/", {(PUBLIC, "/"): _resp(200, big, {"Content-Length": None})})
        self.assertIsInstance(r, FetchError, "streamed oversize body must be refused")
        self.assertIn("too large", str(r).lower())

    def test_error_page_shows_reason(self):
        from chessx_libs.browser import Browser
        b = Browser(lambda u: self.go(u)[0] if isinstance(self.go(u)[0], tuple) else (_ for _ in ()).throw(self.go(u)[0]))
        b.open("http://169.254.169.254/")
        self.assertIn("Blocked for safety", b.error)
        self.assertIn("non-public", "\n".join(x.text for x in b.page.blocks))

    def test_public_ip_allowed(self):
        r, net = self.go(f"http://{PUBLIC}/", {(PUBLIC, "/"): _resp(200, b"<h1>hello</h1>")})
        self.assertNotIsInstance(r, FetchError, r)
        self.assertIn("hello", r[1])

    def test_demo_still_offline(self):
        r, net = self.go("about:demo")
        self.assertIn("ChessX", r[1]); self.assertEqual(net.connected, [])


class TestSSRFUrllib(SSRFBase, unittest.TestCase):
    use_requests = False


try:
    import requests  # noqa: F401
    HAVE_REQ = True
except ImportError:
    HAVE_REQ = False


@unittest.skipUnless(HAVE_REQ, "requests not installed")
class TestSSRFRequests(SSRFBase, unittest.TestCase):
    use_requests = True


if __name__ == "__main__":
    unittest.main()
