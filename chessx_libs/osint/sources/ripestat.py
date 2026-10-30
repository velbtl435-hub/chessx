"""RIPEstat Data API: whois records and routing info for IPs, prefixes and ASNs (keyless)."""
from urllib.parse import urlencode
from ..base import Source, register
from ..types import Finding


@register
class RIPEstatSource(Source):
    name = "ripestat"
    accepts = frozenset({"ip", "asn"})
    host = "stat.ripe.net"
    rate = (2, 1.0)
    ttl = 86400
    license = "RIPEstat Data API terms; free, identify with sourceapp"
    KEYS = ("NetRange", "inetnum", "CIDR", "NetName", "netname", "Organization", "OrgName", "org-name",
            "Country", "country", "ASNumber", "aut-num", "ASName", "as-name", "descr")

    def parse(self, e, d: dict):
        recs = (d.get("data") or {}).get("records") or []
        fields = {}
        for rec in recs:
            for kv in rec:
                k = kv.get("key")
                if k in self.KEYS and k not in fields:
                    fields[k] = kv.get("value")
        if not fields:
            return []
        name = fields.get("NetName") or fields.get("netname") or fields.get("ASName") or fields.get("as-name") or "?"
        return [Finding(e, self.name, "whois", "%s whois: %s" % (e.value, name), fields,
                        "https://stat.ripe.net/app/launchpad/%s" % e.value, confidence=0.85)]

    def lookup(self, e, client):
        url = "https://stat.ripe.net/data/whois/data.json?" + urlencode({"resource": e.value, "sourceapp": "chessx"})
        return self.parse(e, client.get_json(url, source=self))
