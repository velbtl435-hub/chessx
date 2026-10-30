"""urlscan.io public search (keyless, low quota): PUBLIC scans of a domain only."""
from urllib.parse import urlencode
from ..base import Source, register
from ..types import Entity, Finding


@register
class URLScanSource(Source):
    name = "urlscan"
    accepts = frozenset({"domain"})
    host = "urlscan.io"
    rate = (1, 2.0)
    ttl = 86400
    license = "urlscan.io terms: free tier for non-commercial use; only public scans are read"
    commercial_ok = False

    def parse(self, e, d: dict):
        out = []
        for r in d.get("results", []) or []:
            if (r.get("task") or {}).get("visibility", "public") != "public":
                continue
            p = r.get("page") or {}
            rel = []
            if p.get("ip"):
                try:
                    rel.append(Entity("ip", p["ip"]))
                except ValueError:
                    pass
            out.append(Finding(e, self.name, "scan", "%s %s %s (%s)" % (
                (r.get("task") or {}).get("time", "")[:10], p.get("url", ""), p.get("status", ""), p.get("asnname", "")),
                {k: p.get(k) for k in ("url", "ip", "asn", "asnname", "server", "title", "tlsIssuer", "domainAgeDays")},
                (r.get("result") or "").replace("/api/v1/result/", "/result/"), confidence=0.6, related=rel))
        return out

    def lookup(self, e, client):
        url = "https://urlscan.io/api/v1/search/?" + urlencode({"q": "domain:" + e.value, "size": 20})
        return self.parse(e, client.get_json(url, source=self))
