"""Offline tests for network sources (stage 2) with recorded/synthetic fixtures.
Real network: CHESSX_E2E=1 (skips with reason on 429 or network failure)."""
import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.osint.types import Entity
from chessx_libs.osint.http import Client, fixture_transport, HTTPError, RateLimited
from chessx_libs.osint.base import REGISTRY, SourceError, sources
import chessx_libs.osint.sources  # noqa: F401 - registers sources

FX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chessx_libs", "osint", "fixtures")


def fx(name):
    with open(os.path.join(FX, name), "rb") as f:
        return f.read()


def client(routes, calls=None):
    return Client(transport=fixture_transport(routes, calls), sleep=lambda s: None)


D, IP, AS = Entity("domain", "example.com"), Entity("ip", "8.8.8.8"), Entity("asn", "AS15169")
DOH = {"Status": 0, "Answer": [{"name": "example.com.", "type": 1, "TTL": 60, "data": "93.184.215.14"},
                               {"name": "example.com.", "type": 15, "TTL": 60, "data": "10 mx.example.com."},
                               {"name": "example.com.", "type": 2, "TTL": 60, "data": "a.iana-servers.net."}]}


class TestSources(unittest.TestCase):
    def test_rdap_domain_ip_asn(self):
        c = client({"rdap.org/domain/": (200, {}, fx("rdap_dom.json")), "rdap.org/ip/": (200, {}, fx("rdap_ip.json")),
                    "rdap.org/autnum/15169": (200, {}, fx("rdap_asn.json"))})
        s = REGISTRY["rdap"]
        f = s.lookup(D, c)[0]
        self.assertIn("1995-08-14", f.title)
        self.assertIn(Entity("domain", "elliott.ns.cloudflare.com"), f.related)
        self.assertTrue(f.url.startswith("https://rdap.verisign.com"))
        self.assertIn("GOGL", s.lookup(IP, c)[0].title)
        self.assertIn("GOOGLE", s.lookup(AS, c)[0].title)

    def test_dns_doh_and_ptr(self):
        calls = []
        c = client({"dns-query": (200, {}, DOH)}, calls)
        out = REGISTRY["dns"].lookup(D, c)
        kinds = {f.kind for f in out}
        self.assertEqual(kinds, {"dns.A", "dns.MX", "dns.NS"})
        a = [f for f in out if f.kind == "dns.A"][0]
        self.assertEqual(a.related, [Entity("ip", "93.184.215.14")])
        mx = [f for f in out if f.kind == "dns.MX"][0]
        self.assertEqual(mx.related, [Entity("domain", "mx.example.com")])
        self.assertTrue(all(h["Accept"] == "application/dns-json" for _, h in calls))
        ptr = client({"dns-query": (200, {}, {"Answer": [{"name": "8.8.8.8.in-addr.arpa.", "type": 12,
                                                          "data": "dns.google."}]})})
        self.assertEqual(REGISTRY["dns"].lookup(IP, ptr)[0].related, [Entity("domain", "dns.google")])

    def test_dns_falls_back_to_google(self):
        c = client({"cloudflare-dns.com": (500, {}, b"x"), "dns.google": (200, {}, DOH)})
        self.assertTrue(REGISTRY["dns"].lookup(D, c))

    def test_crtsh_subdomains_scoped(self):
        out = REGISTRY["crtsh"].lookup(D, client({"crt.sh": (200, {}, fx("crt.json"))}))
        names = [f.title for f in out]
        self.assertEqual(names, ["dev.example.com", "example.com", "www.example.com"])
        self.assertEqual(out[2].data["first_seen_cert"], "2020-02-02T00:00:00")

    def test_wayback(self):
        out = REGISTRY["wayback"].lookup(D, client({"web.archive.org/cdx": (200, {}, fx("cdx.json"))}))
        self.assertEqual(out[0].kind, "archive.summary")
        self.assertTrue(out[1].url.startswith("https://web.archive.org/web/2002"))

    def test_internetdb_and_404(self):
        out = REGISTRY["internetdb"].lookup(IP, client({"internetdb": (200, {}, fx("idb.json"))}))
        self.assertEqual(out[0].data["ports"], [53, 443])
        self.assertIn(Entity("domain", "dns.google"), out[0].related)
        self.assertEqual(REGISTRY["internetdb"].lookup(IP, client({"internetdb": (404, {}, b"{}")})), [])

    def test_ripestat(self):
        f = REGISTRY["ripestat"].lookup(IP, client({"stat.ripe.net": (200, {}, fx("ripe.json"))}))[0]
        self.assertIn("GOGL", f.title)
        self.assertEqual(f.data["CIDR"], "8.8.8.0/24")

    def test_hackertarget_and_quota(self):
        out = REGISTRY["hackertarget"].lookup(D, client({"hackertarget": (200, {}, fx("ht.txt"))}))
        self.assertEqual([f.title for f in out], ["example.com", "www.example.com"])
        with self.assertRaises(SourceError):
            REGISTRY["hackertarget"].lookup(D, client({"hackertarget": (200, {}, b"API count exceeded - Increase Quota")}))

    def test_urlscan_public_only(self):
        d = json.loads(fx("urlscan.json"))
        d["results"].append({"task": {"visibility": "private"}, "page": {"url": "secret"}})
        out = REGISTRY["urlscan"].lookup(D, client({"urlscan.io": (200, {}, d)}))
        self.assertTrue(out)
        self.assertFalse(any(f.data.get("url") == "secret" for f in out))
        self.assertTrue(out[0].url.startswith("https://urlscan.io/result/"))

    def test_licence_flags_and_switch(self):
        nc = {s.name for s in REGISTRY.values() if not s.commercial_ok}
        self.assertTrue({"internetdb", "hackertarget", "urlscan"} <= nc)
        self.assertFalse(nc & {s.name for s in sources(commercial=True)})
        self.assertTrue(all(s.license and not s.needs_key for s in REGISTRY.values()))

    def test_safe_lookup_on_429(self):
        c = Client(transport=fixture_transport({"crt.sh": (429, {"Retry-After": "1"}, b"")}), sleep=lambda s: None)
        self.assertEqual(REGISTRY["crtsh"].safe_lookup(D, c), [])
        self.assertIn("429", c.errors[0][2])


@unittest.skipUnless(os.environ.get("CHESSX_E2E") == "1", "real-network E2E: set CHESSX_E2E=1")
class TestSourcesE2E(unittest.TestCase):
    CASES = {"rdap": D, "dns": D, "crtsh": D, "wayback": D, "internetdb": IP, "ripestat": IP,
             "hackertarget": D, "urlscan": D}

    def test_live(self):
        for name, ent in self.CASES.items():
            with self.subTest(source=name):
                try:
                    out = REGISTRY[name].lookup(ent, Client(max_wait=10))
                except RateLimited as e:
                    self.skipTest("%s rate limited: %s" % (name, e))
                except (HTTPError, OSError, SourceError) as e:
                    self.skipTest("%s network failure: %s" % (name, e))
                self.assertTrue(out, name)
                self.assertTrue(all(f.title and f.source == name for f in out))


if __name__ == "__main__":
    unittest.main()
