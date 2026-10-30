"""Privacy networking: proxy rotation with kill switch, DNS-over-HTTPS, rotating fingerprint."""
import itertools, json, random, threading, urllib.parse, urllib.request


class KillSwitchEngaged(RuntimeError):
    """Raised instead of ever falling back to a direct (unproxied) connection."""


class ProxyRotator:
    def __init__(self, proxies, max_failures: int = 3):
        if not proxies:
            raise ValueError("at least one proxy required")
        self.proxies = list(proxies)
        self.failures = {p: 0 for p in self.proxies}
        self.max_failures = max_failures
        self._cycle = itertools.cycle(self.proxies)
        self._lock = threading.Lock()
        self.killed = False

    def healthy(self):
        return [p for p in self.proxies if self.failures[p] < self.max_failures]

    def next(self) -> str:
        with self._lock:
            if self.killed or not self.healthy():
                self.killed = True
                raise KillSwitchEngaged("no healthy proxy; traffic blocked")
            for p in self._cycle:
                if self.failures[p] < self.max_failures:
                    return p

    def report_failure(self, proxy):
        with self._lock:
            self.failures[proxy] += 1

    def opener(self):
        p = self.next()
        return p, urllib.request.build_opener(urllib.request.ProxyHandler({"http": p, "https": p}))

    def open(self, url, timeout=15, headers=None):
        """Fetch through rotating proxies; never falls back to direct."""
        while True:
            p, op = self.opener()
            try:
                return op.open(urllib.request.Request(url, headers=headers or {}), timeout=timeout).read()
            except OSError:
                self.report_failure(p)


DOH_SERVERS = {"cloudflare": "https://cloudflare-dns.com/dns-query",
               "google": "https://dns.google/resolve", "quad9": "https://dns.quad9.net:5053/dns-query"}


def doh_resolve(name: str, rtype: str = "A", server: str = "cloudflare", timeout=10):
    url = DOH_SERVERS.get(server, server) + "?" + urllib.parse.urlencode({"name": name, "type": rtype})
    req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return [a["data"] for a in data.get("Answer", [])]


class FingerprintRotator:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    ]
    LANGS = ["en-US,en;q=0.9", "pt-BR,pt;q=0.9,en;q=0.8", "ja-JP,ja;q=0.9,en;q=0.8", "en-GB,en;q=0.8"]

    def __init__(self, seed=None):
        # seed only for reproducible tests; default uses the OS CSPRNG so the
        # rotation order is not predictable from a guessable seed/state.
        self.rng = random.Random(seed) if seed is not None else random.SystemRandom()

    def headers(self) -> dict:
        return {"User-Agent": self.rng.choice(self.USER_AGENTS), "Accept-Language": self.rng.choice(self.LANGS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "DNT": "1"}
