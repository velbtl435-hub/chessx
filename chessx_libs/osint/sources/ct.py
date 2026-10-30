"""Certificate Transparency via crt.sh JSON: subdomains seen in public certificates."""
from urllib.parse import urlencode
from ..base import Source, register
from ..types import Entity, Finding


@register
class CrtShSource(Source):
    name = "crtsh"
    accepts = frozenset({"domain"})
    host = "crt.sh"
    rate = (1, 5.0)   # crt.sh is a shared community service: be gentle
    ttl = 7 * 86400
    license = "crt.sh (Sectigo) public CT search; no published ToS, low volume only"

    def parse(self, e: Entity, rows: list, url: str, limit: int = 500):
        names = {}
        for r in rows or []:
            for n in str(r.get("name_value", "")).lower().split("\n"):
                n = n.strip().lstrip("*.")
                if n and (n == e.value or n.endswith("." + e.value)):
                    first = names.get(n)
                    nb = r.get("not_before", "")
                    if first is None or nb < first:
                        names[n] = nb
        out = []
        for n in sorted(names)[:limit]:
            out.append(Finding(e, self.name, "subdomain", n, {"first_seen_cert": names[n]},
                               "https://crt.sh/?" + urlencode({"q": n}), confidence=0.7,
                               related=[Entity("domain", n)] if n != e.value else []))
        return out

    def lookup(self, e, client):
        url = "https://crt.sh/?" + urlencode({"q": "%." + e.value, "output": "json"})
        return self.parse(e, client.get_json(url, source=self), url)
