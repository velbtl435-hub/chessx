"""RDAP (registration data) via rdap.org, which redirects to the authoritative registry (IANA bootstrap)."""
from urllib.parse import quote
from ..base import Source, register
from ..types import Entity, Finding


def _events(d):
    return {e.get("eventAction"): e.get("eventDate") for e in d.get("events", []) if e.get("eventAction")}


def _entities(d):
    out = []
    for e in d.get("entities", []) or []:
        name = ""
        for item in (e.get("vcardArray") or [None, []])[1]:
            if item and item[0] == "fn":
                name = item[3]
        out.append({"handle": e.get("handle", ""), "roles": e.get("roles", []), "name": name})
    return out


def _self_link(d, fallback):
    for l in d.get("links", []) or []:
        if l.get("rel") == "self" and l.get("href"):
            return l["href"]
    return fallback


@register
class RDAPSource(Source):
    name = "rdap"
    accepts = frozenset({"domain", "ip", "asn"})
    host = "rdap.org"
    rate = (1, 1.0)
    ttl = 7 * 86400
    license = "public registry data (RDAP, RFC 9083); rdap.org is a free redirector"
    BASE = "https://rdap.org/"

    def url_for(self, e: Entity) -> str:
        path = {"domain": "domain/", "ip": "ip/", "asn": "autnum/"}[e.kind]
        return self.BASE + path + quote(e.value.removeprefix("AS") if e.kind == "asn" else e.value)

    def parse(self, e: Entity, d: dict, url: str):
        data = {"handle": d.get("handle"), "status": d.get("status", []), "events": _events(d),
                "entities": _entities(d)}
        related = []
        if e.kind == "domain":
            ns = [n.get("ldhName", "").lower() for n in d.get("nameservers", []) or [] if n.get("ldhName")]
            data["nameservers"] = ns
            related = [Entity("domain", n) for n in ns]
            title = "RDAP %s (registered %s)" % (e.value, data["events"].get("registration", "?"))
        elif e.kind == "ip":
            data.update(name=d.get("name"), start=d.get("startAddress"), end=d.get("endAddress"),
                        country=d.get("country"))
            title = "RDAP %s: %s %s-%s" % (e.value, d.get("name"), d.get("startAddress"), d.get("endAddress"))
        else:
            data.update(name=d.get("name"))
            title = "RDAP %s: %s" % (e.value, d.get("name"))
        return [Finding(e, self.name, "rdap", title, data, _self_link(d, url), confidence=0.9, related=related)]

    def lookup(self, e, client):
        url = self.url_for(e)
        return self.parse(e, client.get_json(url, source=self, headers={"Accept": "application/rdap+json"}), url)
