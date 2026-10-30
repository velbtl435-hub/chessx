"""Shodan InternetDB: open ports, hostnames, CPEs and known CVEs for an IP (keyless, non-commercial)."""
from ..base import Source, register
from ..types import Entity, Finding


@register
class InternetDBSource(Source):
    name = "internetdb"
    accepts = frozenset({"ip"})
    host = "internetdb.shodan.io"
    rate = (1, 1.0)
    ttl = 86400
    license = "Shodan InternetDB: free, NON-COMMERCIAL use only"
    commercial_ok = False

    def parse(self, e, d: dict):
        if not d or "detail" in d and not d.get("ports"):
            return []
        url = "https://internetdb.shodan.io/" + e.value
        data = {k: d.get(k, []) for k in ("ports", "hostnames", "cpes", "tags", "vulns")}
        title = "%s ports=%s vulns=%d" % (e.value, ",".join(map(str, data["ports"])) or "-", len(data["vulns"]))
        return [Finding(e, self.name, "exposure", title, data, url, confidence=0.75,
                        related=[Entity("domain", h) for h in data["hostnames"]])]

    def lookup(self, e, client):
        from ..http import HTTPError
        try:
            return self.parse(e, client.get_json("https://internetdb.shodan.io/" + e.value, source=self))
        except HTTPError as ex:
            if ex.status == 404:  # "No information available"
                return []
            raise
