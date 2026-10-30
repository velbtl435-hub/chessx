"""Internet Archive Wayback Machine CDX API: archived snapshots of a domain/URL."""
from urllib.parse import urlencode
from ..base import Source, register
from ..types import Finding


@register
class WaybackSource(Source):
    name = "wayback"
    accepts = frozenset({"domain", "url"})
    host = "web.archive.org"
    rate = (1, 1.0)
    ttl = 7 * 86400
    license = "Internet Archive Terms of Use; light, non-bulk use"
    LIMIT = 20

    def parse(self, e, rows: list):
        if not rows:
            return []
        head, out = rows[0], []
        recs = [dict(zip(head, r)) for r in rows[1:]]
        if recs:
            first, last = recs[0], recs[-1]
            out.append(Finding(e, self.name, "archive.summary", "%s archived %s..%s (%d sampled)" % (
                e.value, first["timestamp"][:8], last["timestamp"][:8], len(recs)),
                {"first": first["timestamp"], "last": last["timestamp"], "sampled": len(recs)},
                "https://web.archive.org/web/*/%s*" % e.value, confidence=0.8))
        for r in recs:
            out.append(Finding(e, self.name, "snapshot", "%s %s %s" % (r["timestamp"], r.get("statuscode"),
                                                                     r["original"]),
                               {k: r.get(k) for k in ("timestamp", "original", "mimetype", "statuscode", "digest")},
                               "https://web.archive.org/web/%s/%s" % (r["timestamp"], r["original"]),
                               confidence=0.6))
        return out

    def lookup(self, e, client):
        q = {"url": e.value + ("/*" if e.kind == "domain" else ""), "output": "json", "limit": self.LIMIT,
             "collapse": "urlkey" if e.kind == "domain" else "digest", "filter": "statuscode:200"}
        url = "https://web.archive.org/cdx/search/cdx?" + urlencode(q)
        return self.parse(e, client.get_json(url, source=self))
