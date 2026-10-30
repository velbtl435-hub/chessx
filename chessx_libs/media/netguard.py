"""netguard: SSRF-safe HTTP(S) fetching (stdlib only). Public, stable API (see README "netguard"):

    check_url(url, allow_private=False, resolver=None) -> URLInfo     # raises BlockedURL
    open_url(url, timeout=30, max_bytes=..., headers=None, allow_private=False, max_redirects=5,
             max_seconds=None, resolver=None) -> Response               # raises BlockedURL / ResponseTooLarge /
                                                                        # urllib.error.HTTPError / URLError / OSError
    is_public_ip(ip) -> bool

Rules: only http/https with a host; no userinfo, control chars or spaces; every address the host resolves to must be
public (rejects private, loopback, link-local, CGNAT, multicast, reserved, unspecified, documentation; IPv6 ULA /
link-local; IPv4-mapped / 6to4 / NAT64 addresses are unwrapped; legacy decimal/hex/octal IPv4 such as 2130706433 or
0x7f.1 are parsed as literals). The TCP connection goes to the validated IP (no second DNS lookup -> no rebinding);
Host header and TLS SNI/certificate use the hostname. The opener has no file/ftp/data/proxy handlers, and each
redirect hop is validated again (max_redirects). allow_private=True is an explicit opt-in for tests/local tools.
"""
import http.client, ipaddress, socket, ssl, time, urllib.error, urllib.parse, urllib.request
from dataclasses import dataclass

__all__ = ["BlockedURL", "ResponseTooLarge", "URLInfo", "Response", "check_url", "open_url", "is_public_ip",
           "DEFAULT_MAX_BYTES", "ALLOWED_SCHEMES"]

ALLOWED_SCHEMES = ("http", "https")
DEFAULT_MAX_BYTES = 512 * 1024 * 1024
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


class BlockedURL(ValueError):
    """URL refused by policy (scheme, userinfo, malformed, or a non-public destination). .reason has the cause."""
    def __init__(self, url, reason):
        super().__init__(f"blocked {url!r}: {reason}")
        self.url, self.reason = url, reason


class ResponseTooLarge(OSError):
    """Body exceeded max_bytes (declared Content-Length or streamed), or the max_seconds deadline passed."""


@dataclass(frozen=True)
class URLInfo:
    url: str
    scheme: str
    host: str          # hostname as written (lowercase, no brackets)
    port: int
    addresses: tuple   # validated IP strings to connect to (first one is used)


def _unwrap(ip):
    if ip.version == 6:
        if ip.ipv4_mapped:
            return ip.ipv4_mapped
        if ip.sixtofour:
            return ip.sixtofour
        if ip in _NAT64:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return ip


def is_public_ip(ip) -> bool:
    """True only for globally routable unicast addresses (after unwrapping mapped/6to4/NAT64 IPv6)."""
    ip = _unwrap(ipaddress.ip_address(ip))
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
                or ip.is_unspecified or (ip.version == 4 and ip in _CGNAT)
                or getattr(ip, "is_site_local", False)) and ip.is_global


def _literal_ip(host):
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if host and all(c in "0123456789abcdefxABCDEFX." for c in host) and host[0].isdigit():
        try:  # legacy IPv4 forms accepted by inet_aton / getaddrinfo: 2130706433, 0x7f.1, 0177.0.0.1
            return ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            pass
    return None


def _default_resolver(host, port):
    return [ai[4][0] for ai in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]


def check_url(url, allow_private=False, resolver=None) -> URLInfo:
    """Validate url and resolve its host. Returns URLInfo; raises BlockedURL. resolver(host, port) -> [ip, ...]
    replaces DNS (tests). With allow_private=True only the address checks are skipped (scheme rules still apply)."""
    if not isinstance(url, str) or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise BlockedURL(url, "control characters or spaces in URL")
    try:
        p = urllib.parse.urlsplit(url)
        port = p.port
    except ValueError as e:
        raise BlockedURL(url, f"malformed URL ({e})") from None
    scheme = p.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise BlockedURL(url, f"scheme {scheme or '(none)'!r} not allowed (http/https only)")
    if "@" in p.netloc:
        raise BlockedURL(url, "userinfo (user:pass@) not allowed")
    host = (p.hostname or "").rstrip(".")
    if not host:
        raise BlockedURL(url, "missing host")
    port = port or (443 if scheme == "https" else 80)
    lit = _literal_ip(host)
    if lit is not None:
        addrs = [str(lit)]
    else:
        try:
            addrs = list(dict.fromkeys((resolver or _default_resolver)(host, port)))
        except (OSError, UnicodeError) as e:
            raise BlockedURL(url, f"cannot resolve host ({e})") from None
        if not addrs:
            raise BlockedURL(url, "host resolved to no addresses")
    clean = []
    for a in addrs:
        try:
            ip = ipaddress.ip_address(str(a).split("%", 1)[0])
        except ValueError:
            raise BlockedURL(url, f"resolver returned invalid address {a!r}") from None
        if not allow_private and not is_public_ip(ip):
            raise BlockedURL(url, f"non-public address {ip}")
        clean.append(str(ip))
    return URLInfo(url, scheme, host, port, tuple(clean))


# ---------------------------------------------------------------- pinned connections
class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, ip, **kw):
        super().__init__(host, **kw)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip, context, **kw):
        super().__init__(host, context=context, **kw)
        self._ip, self._ctx = ip, context

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._ctx.wrap_socket(sock, server_hostname=self.host)


class _GuardedHandler(urllib.request.AbstractHTTPHandler):
    """http/https handler that validates every request (incl. each redirect hop) and connects to the checked IP."""
    def __init__(self, allow_private, resolver, context):
        super().__init__()
        self.allow_private, self.resolver, self.context = allow_private, resolver, context

    def _open(self, req, https):
        info = check_url(req.full_url, self.allow_private, self.resolver)
        ip = info.addresses[0]
        if https:
            factory = lambda host, **kw: _PinnedHTTPS(host, ip, self.context, **kw)  # noqa: E731
        else:
            factory = lambda host, **kw: _PinnedHTTP(host, ip, **kw)  # noqa: E731
        return self.do_open(factory, req)

    def http_open(self, req):
        return self._open(req, False)

    def https_open(self, req):
        return self._open(req, True)

    http_request = https_request = urllib.request.AbstractHTTPHandler.do_request_


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    _SENSITIVE = ("authorization", "cookie", "proxy-authorization")

    def __init__(self, max_redirects, allow_private, resolver):
        super().__init__()
        self.max_redirections = self.max_repeats = max_redirects
        self.allow_private, self.resolver = allow_private, resolver

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl, self.allow_private, self.resolver)  # early, explicit refusal (http_open checks again)
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            old, nu = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
            if (old.scheme, old.netloc) != (nu.scheme, nu.netloc):
                for h in list(new.headers):
                    if h.lower() in self._SENSITIVE:
                        del new.headers[h]
        return new

    def http_error_302(self, req, fp, code, msg, headers):
        if self.max_redirections == 0:
            raise urllib.error.HTTPError(req.full_url, code, "redirects disabled (max_redirects=0)", headers, fp)
        loc = headers.get("location") or headers.get("uri")
        if loc:  # validate before urllib's own scheme check so file:/ftp: hops raise BlockedURL too
            check_url(urllib.parse.urljoin(req.full_url, loc), self.allow_private, self.resolver)
        return super().http_error_302(req, fp, code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def build_opener(allow_private=False, max_redirects=5, resolver=None, context=None):
    """OpenerDirector with ONLY guarded http/https + redirect + error handlers (no file/ftp/data/proxy)."""
    od = urllib.request.OpenerDirector()
    for h in (_GuardedHandler(allow_private, resolver, context or ssl.create_default_context()),
              _GuardedRedirect(max_redirects, allow_private, resolver),
              urllib.request.HTTPDefaultErrorHandler(), urllib.request.HTTPErrorProcessor(),
              urllib.request.UnknownHandler()):
        od.add_handler(h)
    return od


class Response:
    """Thin wrapper over the urllib response enforcing max_bytes / max_seconds on read().
    Attributes: url (final, after redirects), status, headers. Context manager; close()."""
    def __init__(self, raw, max_bytes, deadline):
        self._raw, self.max_bytes, self._deadline, self.bytes_read = raw, max_bytes, deadline, 0
        self.url, self.status, self.headers = raw.geturl(), raw.status, raw.headers

    def geturl(self):
        return self.url

    def read(self, n=-1):
        if self._deadline is not None and time.monotonic() > self._deadline:
            raise ResponseTooLarge("download deadline (max_seconds) exceeded")
        if self.max_bytes is None:
            b = self._raw.read() if n is None or n < 0 else self._raw.read(n)
        else:
            left = self.max_bytes - self.bytes_read + 1
            b = self._raw.read(left if n is None or n < 0 else min(n, left))
        self.bytes_read += len(b)
        if self.max_bytes is not None and self.bytes_read > self.max_bytes:
            raise ResponseTooLarge(f"response exceeded max_bytes {self.max_bytes}")
        return b

    def close(self):
        self._raw.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def open_url(url, timeout=30, max_bytes=DEFAULT_MAX_BYTES, headers=None, allow_private=False, max_redirects=5,
             max_seconds=None, resolver=None, context=None) -> Response:
    """GET url through the guarded opener. max_bytes=None disables the size cap (explicitly);
    a declared Content-Length above max_bytes fails before reading. HTTP errors raise urllib.error.HTTPError."""
    check_url(url, allow_private, resolver)
    req = urllib.request.Request(url, headers=dict(headers or {}))
    raw = build_opener(allow_private, max_redirects, resolver, context).open(req, timeout=timeout)
    clen = raw.headers.get("Content-Length")
    if max_bytes is not None and clen and clen.strip().isdigit() and int(clen) > max_bytes:
        raw.close()
        raise ResponseTooLarge(f"Content-Length {clen} > max_bytes {max_bytes}")
    return Response(raw, max_bytes, time.monotonic() + max_seconds if max_seconds else None)
