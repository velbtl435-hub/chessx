"""DNS records via DNS-over-HTTPS JSON (Cloudflare, Google fallback). dnspython is not required."""
from urllib.parse import urlencode
from ..base import Source, register
from ..types import Entity, Finding

TYPES = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 15: "MX", 16: "TXT", 28: "AAAA", 12: "PTR"}


def reverse_name(ip: str) -> str:
    import ipaddress
    return ipaddress.ip_address(ip).reverse_pointer


@register
class DoHSource(Source):
    name = "dns"
    accepts = frozenset({"domain", "ip"})
    host = "cloudflare-dns.com"
    rate = (5, 1.0)
    ttl = 3600
    license = "free public resolvers (Cloudflare 1.1.1.1 / Google Public DNS)"
    RESOLVERS = ("https://cloudflare-dns.com/dns-query", "https://dns.google/resolve")
    RECORDS = ("A", "AAAA", "MX", "NS", "TXT", "CNAME")

    def query(self, client, name, rtype):
        last = None
        for base in self.RESOLVERS:
            url = base + "?" + urlencode({"name": name, "type": rtype})
            try:
                return url, client.get_json(url, source=self, headers={"Accept": "application/dns-json"})
            except Exception as ex:  # noqa: BLE001 - try next resolver
                last = ex
        raise last

    def parse(self, e: Entity, rtype: str, d: dict, url: str):
        out = []
        for a in d.get("Answer", []) or []:
            t = TYPES.get(a.get("type"), str(a.get("type")))
            if t != rtype:
                continue
            val = str(a.get("data", "")).strip()
            rel = []
            if t in ("A", "AAAA"):
                rel = [Entity("ip", val)]
            elif t in ("NS", "CNAME", "PTR"):
                rel = [Entity("domain", val)] if val.rstrip(".") else []
            elif t == "MX" and " " in val and val.split()[-1].rstrip("."):
                rel = [Entity("domain", val.split()[-1])]
            out.append(Finding(e, self.name, "dns." + t, "%s %s %s" % (a.get("name", "").rstrip("."), t, val),
                               {"type": t, "value": val, "ttl": a.get("TTL")},
                               "", confidence=0.95, related=rel))
        return out

    def lookup(self, e, client):
        out = []
        if e.kind == "ip":
            url, d = self.query(client, reverse_name(e.value), "PTR")
            return self.parse(e, "PTR", d, url)
        for t in self.RECORDS:
            url, d = self.query(client, e.value, t)
            out += self.parse(e, t, d, url)
        return out
