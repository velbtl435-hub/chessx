"""Shared HTTP client: identifiable UA, per-host token bucket, Retry-After/backoff, TTL cache, offline mode,
and an audit record per request. The transport is injectable so tests run with fixtures, no network."""
import email.utils, json, threading, time, urllib.error, urllib.parse, urllib.request

UA = "ChessX-OSINT/0.1 (+https://github.com/velbtl435-hub/chessx; public-source research tool)"


class HTTPError(Exception):
    def __init__(self, status, url, msg=""):
        super().__init__("HTTP %s for %s %s" % (status, url, msg))
        self.status, self.url = status, url


class RateLimited(HTTPError):
    pass


class OfflineMiss(Exception):
    pass


class TokenBucket:
    def __init__(self, n: int, per: float, clock=time.monotonic, sleep=time.sleep):
        self.capacity, self.rate = float(n), n / per
        self.tokens, self.clock, self.sleep = float(n), clock, sleep
        self.t = clock()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Block until a token is available; returns seconds waited."""
        with self._lock:
            now = self.clock()
            self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.rate)
            self.t = now
            wait = 0.0 if self.tokens >= 1 else (1 - self.tokens) / self.rate
            self.tokens -= 1
        if wait:
            self.sleep(wait)
        return wait


def urllib_transport(url, headers, timeout):
    """Default transport: returns (status, headers dict, body bytes); never raises on HTTP status."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() if e.fp else b""


def retry_after_seconds(value, now=None) -> float:
    if not value:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            dt = email.utils.parsedate_to_datetime(value)
            return max(0.0, dt.timestamp() - (now or time.time()))
        except (TypeError, ValueError):
            return 0.0


class Client:
    def __init__(self, cache=None, audit=None, offline=False, transport=urllib_transport, ua=UA,
                 timeout=20.0, max_retries=2, max_wait=30.0, sleep=time.sleep, clock=time.monotonic):
        self.cache, self.audit, self.offline = cache, audit, offline
        self.transport, self.ua, self.timeout = transport, ua, timeout
        self.max_retries, self.max_wait, self.sleep, self.clock = max_retries, max_wait, sleep, clock
        self.buckets = {}
        self.errors = []      # (source, entity, message) collected by Source.safe_lookup
        self.stats = {"requests": 0, "cache_hits": 0, "retries": 0}
        self._lock = threading.Lock()

    def bucket(self, host, rate):
        with self._lock:
            if host not in self.buckets:
                self.buckets[host] = TokenBucket(rate[0], rate[1], clock=self.clock, sleep=self.sleep)
            return self.buckets[host]

    def get(self, url, source=None, headers=None, ttl=None, rate=None, audit_url=None) -> bytes:
        """GET with cache + rate limit + retry. `source` (a Source) provides host/rate/ttl/name.
        audit_url overrides what is written to the audit log (use it to avoid logging sensitive URLs)."""
        name = getattr(source, "name", "-")
        ttl = getattr(source, "ttl", 3600) if ttl is None else ttl
        rate = rate or getattr(source, "rate", (1, 1.0))
        key = "GET " + url
        if self.audit:
            self.audit.log("http_get", source=name, url=audit_url or url, offline=self.offline)
        if self.cache:
            hit = self.cache.get(key, allow_stale=self.offline)
            if hit is not None:
                self.stats["cache_hits"] += 1
                return hit
        if self.offline:
            raise OfflineMiss("offline and not cached: %s" % (audit_url or url))
        host = urllib.parse.urlparse(url).netloc
        hdr = {"User-Agent": self.ua, "Accept": "application/json, text/plain;q=0.9, */*;q=0.5", **(headers or {})}
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            self.bucket(host, rate).acquire()
            self.stats["requests"] += 1
            status, rh, body = self.transport(url, hdr, self.timeout)
            if 200 <= status < 300:
                if self.cache and ttl:
                    self.cache.set(key, body, ttl)
                return body
            if status in (429, 502, 503, 504) and attempt < self.max_retries:
                ra = retry_after_seconds({k.lower(): v for k, v in rh.items()}.get("retry-after"))
                wait = ra or delay
                if wait > self.max_wait:
                    break
                self.stats["retries"] += 1
                self.sleep(wait)
                delay *= 2
                continue
            break
        cls = RateLimited if status == 429 else HTTPError
        raise cls(status, audit_url or url, body[:120].decode("utf-8", "replace") if body else "")

    def get_json(self, url, **kw):
        return json.loads(self.get(url, **kw).decode("utf-8", "replace"))

    def get_text(self, url, **kw) -> str:
        return self.get(url, **kw).decode("utf-8", "replace")


def fixture_transport(routes: dict, calls: list = None):
    """Test helper: routes maps URL substring -> (status, headers, body) or a list of them (consumed in order)."""
    def t(url, headers, timeout):
        if calls is not None:
            calls.append((url, headers))
        for frag, resp in routes.items():
            if frag in url:
                if isinstance(resp, list):
                    r = resp.pop(0) if len(resp) > 1 else resp[0]
                else:
                    r = resp
                status, h, body = r
                if not isinstance(body, bytes):
                    body = json.dumps(body).encode() if not isinstance(body, str) else body.encode()
                return status, h, body
        return 404, {}, b"no fixture"
    return t
