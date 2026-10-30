"""Geolocation: Nominatim (OpenStreetMap) geocoding / reverse geocoding, ipapi.co IP geolocation."""
import re
from urllib.parse import urlencode
from ..base import Source, register
from ..types import Finding

LATLON = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


@register
class NominatimSource(Source):
    """Entity kind "geo": a place name ("Sao Paulo") or "lat,lon" for reverse geocoding."""
    name = "nominatim"
    accepts = frozenset({"geo"})
    host = "nominatim.openstreetmap.org"
    rate = (1, 1.0)            # usage policy: absolute max 1 request/second, identifiable UA, cache results
    ttl = 30 * 86400
    license = "OSM Nominatim usage policy (ODbL data, attribution required, no bulk/heavy use)"

    def lookup(self, e, client):
        m = LATLON.match(e.value)
        if m:
            q = {"lat": m.group(1), "lon": m.group(2), "format": "jsonv2"}
            d = client.get_json("https://nominatim.openstreetmap.org/reverse?" + urlencode(q), source=self)
            rows = [d] if d and "error" not in d else []
        else:
            q = {"q": e.value, "format": "jsonv2", "limit": 5}
            rows = client.get_json("https://nominatim.openstreetmap.org/search?" + urlencode(q), source=self)
        return self.parse(e, rows)

    def parse(self, e, rows):
        out = []
        for i, r in enumerate(rows or []):
            url = "https://www.openstreetmap.org/%s/%s" % (r.get("osm_type"), r.get("osm_id")) \
                if r.get("osm_type") else "https://www.openstreetmap.org/?mlat=%s&mlon=%s" % (r.get("lat"), r.get("lon"))
            out.append(Finding(e, self.name, "place", r.get("display_name", "?"),
                               {"lat": r.get("lat"), "lon": r.get("lon"), "type": r.get("type"),
                                "category": r.get("category"), "attribution": "(c) OpenStreetMap contributors"},
                               url, confidence=round(0.8 - 0.1 * i, 2)))
        return out


@register
class IPAPISource(Source):
    name = "ipapi"
    accepts = frozenset({"ip"})
    host = "ipapi.co"
    rate = (1, 2.0)
    ttl = 7 * 86400
    license = "ipapi.co free tier (~1000 req/day), NON-COMMERCIAL without a paid plan"
    commercial_ok = False
    FIELDS = ("ip", "network", "city", "region", "country_name", "country_code", "postal", "latitude",
              "longitude", "timezone", "asn", "org")

    def lookup(self, e, client):
        return self.parse(e, client.get_json("https://ipapi.co/%s/json/" % e.value, source=self))

    def parse(self, e, d):
        if not d or d.get("error"):
            return []
        data = {k: d.get(k) for k in self.FIELDS if d.get(k) is not None}
        title = "%s ~ %s, %s, %s (%s)" % (e.value, d.get("city"), d.get("region"), d.get("country_name"), d.get("org"))
        return [Finding(e, self.name, "ip.geo", title, data, "https://ipapi.co/%s/" % e.value, confidence=0.6)]
