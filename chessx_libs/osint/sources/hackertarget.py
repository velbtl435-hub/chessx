"""HackerTarget hostsearch (free tier, ~50 queries/day/IP, no key): host names + IPs of a domain."""
from urllib.parse import urlencode
from ..base import Source, register
from ..types import Entity, Finding


@register
class HackerTargetSource(Source):
    name = "hackertarget"
    accepts = frozenset({"domain"})
    host = "api.hackertarget.com"
    rate = (1, 2.0)
    ttl = 7 * 86400
    license = "HackerTarget free API tier (quota-limited); commercial use needs a paid plan"
    commercial_ok = False

    def parse(self, e, text: str):
        out = []
        if "API count exceeded" in text or text.startswith("error"):
            from ..base import SourceError
            raise SourceError("hackertarget: " + text.strip()[:80])
        for line in text.splitlines():
            if "," not in line:
                continue
            host, ip = [x.strip() for x in line.split(",", 1)]
            if host == e.value or host.endswith("." + e.value):
                rel = ([Entity("domain", host)] if host != e.value else [])
                try:
                    rel.append(Entity("ip", ip))
                except ValueError:
                    pass
                out.append(Finding(e, self.name, "subdomain", host, {"ip": ip},
                                   "https://crt.sh/?q=" + host, confidence=0.6, related=rel))
        return out

    def lookup(self, e, client):
        return self.parse(e, client.get_text("https://api.hackertarget.com/hostsearch/?" +
                                             urlencode({"q": e.value}), source=self))
