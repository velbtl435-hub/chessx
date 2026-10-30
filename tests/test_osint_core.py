"""Offline tests for chessx_libs.osint core: types, registry/licence switch, cache, audit, http client, fusion."""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.osint.types import Entity, Finding, detect_kind
from chessx_libs.osint import base
from chessx_libs.osint.base import Source, sources
from chessx_libs.osint.cache import Cache
from chessx_libs.osint.audit import AuditLog
from chessx_libs.osint.http import (Client, TokenBucket, RateLimited, OfflineMiss, HTTPError,
                                    fixture_transport, retry_after_seconds, UA)
from chessx_libs.osint.fusion import fuse_findings


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.slept = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class TestTypes(unittest.TestCase):
    def test_detect_and_normalize(self):
        self.assertEqual(detect_kind("8.8.8.8"), "ip")
        self.assertEqual(detect_kind("as15169"), "asn")
        self.assertEqual(detect_kind("WWW.Example.COM."), "domain")
        self.assertEqual(detect_kind("a@b.io"), "email")
        self.assertEqual(detect_kind("https://x.y/z"), "url")
        self.assertEqual(detect_kind("niklasf"), "username")
        self.assertEqual(Entity.parse("WWW.Example.COM.").value, "example.com")
        self.assertEqual(Entity("asn", "15169").value, "AS15169")
        self.assertEqual(Entity("ip", "2001:DB8::0001").value, "2001:db8::1")
        with self.assertRaises(ValueError):
            Entity("nope", "x")

    def test_finding_roundtrip_and_clamp(self):
        f = Finding(Entity("domain", "example.com"), "s", "k", "t", {"a": 1}, confidence=3,
                    related=[Entity("ip", "1.2.3.4")])
        self.assertEqual(f.confidence, 1.0)
        g = Finding.from_dict(f.to_dict())
        self.assertEqual(g.entity, f.entity)
        self.assertEqual(g.related, f.related)
        self.assertTrue(f.key_url.startswith("osint://"))


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.saved = dict(base.REGISTRY)
        base.REGISTRY.clear()

        @base.register
        class Free(Source):
            name, accepts = "free_t", frozenset({"ip"})

        @base.register
        class NC(Source):
            name, accepts, commercial_ok, license = "nc_t", frozenset({"ip", "domain"}), False, "non-commercial"

    def tearDown(self):
        base.REGISTRY.clear()
        base.REGISTRY.update(self.saved)
        os.environ.pop("CHESSX_COMMERCIAL", None)

    def test_filters_and_commercial_switch(self):
        self.assertEqual({s.name for s in sources("ip", commercial=False)}, {"free_t", "nc_t"})
        self.assertEqual({s.name for s in sources("domain", commercial=False)}, {"nc_t"})
        self.assertEqual({s.name for s in sources(commercial=True)}, {"free_t"})
        os.environ["CHESSX_COMMERCIAL"] = "1"
        self.assertEqual({s.name for s in sources()}, {"free_t"})
        self.assertEqual({s.name for s in sources(names=["nc_t"], commercial=False)}, {"nc_t"})

    def test_safe_lookup_records_error(self):
        class Boom(Source):
            name = "boom"

            def lookup(self, e, c):
                raise RuntimeError("x")
        c = Client(transport=fixture_transport({}))
        self.assertEqual(Boom().safe_lookup(Entity("ip", "1.1.1.1"), c), [])
        self.assertEqual(c.errors[0][0], "boom")


class TestCacheAudit(unittest.TestCase):
    def test_cache_ttl_and_stale(self):
        clk = FakeClock()
        c = Cache(":memory:", clock=clk)
        c.set("k", b"v", 10)
        self.assertEqual(c.get("k"), b"v")
        clk.t = 11
        self.assertIsNone(c.get("k"))
        self.assertEqual(c.get("k", allow_stale=True), b"v")
        self.assertEqual(c.purge(), 1)

    def test_audit_file_and_redaction(self):
        d = tempfile.mkdtemp()
        a = AuditLog(os.path.join(d, "a.jsonl"))
        a.log("q", source="s", password="hunter2", sha1_hash="abc", url="u")
        rec = a.read()[0]
        self.assertEqual(rec["password"], "<redacted>")
        self.assertEqual(rec["sha1_hash"], "<redacted>")
        self.assertEqual(rec["url"], "u")
        a.clear()
        self.assertEqual(a.read(), [])


class TestHTTP(unittest.TestCase):
    def test_token_bucket_waits(self):
        clk = FakeClock()
        b = TokenBucket(2, 1.0, clock=clk, sleep=clk.sleep)
        self.assertEqual(b.acquire(), 0)
        self.assertEqual(b.acquire(), 0)
        self.assertAlmostEqual(b.acquire(), 0.5)

    def test_retry_after_then_ok_and_cache_and_ua(self):
        clk, calls = FakeClock(), []
        t = fixture_transport({"x.test": [(429, {"Retry-After": "3"}, b""), (200, {}, {"ok": 1})]}, calls)
        audit = AuditLog(":memory:")
        c = Client(cache=Cache(":memory:"), audit=audit, transport=t, sleep=clk.sleep, clock=clk)
        self.assertEqual(c.get_json("https://x.test/a"), {"ok": 1})
        self.assertIn(3.0, clk.slept)
        self.assertEqual(calls[0][1]["User-Agent"], UA)
        self.assertEqual(c.get_json("https://x.test/a"), {"ok": 1})  # cached
        self.assertEqual(len(calls), 2)
        self.assertEqual(c.stats["cache_hits"], 1)
        self.assertEqual(len(audit.read()), 2)

    def test_rate_limited_raises_and_offline(self):
        clk = FakeClock()
        c = Client(transport=fixture_transport({"x.test": (429, {"Retry-After": "1"}, b"slow")}),
                   sleep=clk.sleep, clock=clk, max_retries=1)
        with self.assertRaises(RateLimited):
            c.get("https://x.test/")
        with self.assertRaises(HTTPError):
            Client(transport=fixture_transport({})).get("https://nothing.test/")
        off = Client(cache=Cache(":memory:"), offline=True, transport=None)
        with self.assertRaises(OfflineMiss):
            off.get("https://x.test/")

    def test_retry_after_date(self):
        self.assertEqual(retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT", now=1445412480 - 10), 10)
        self.assertEqual(retry_after_seconds("garbage"), 0.0)


class TestFusion(unittest.TestCase):
    def test_dedup_and_agreement(self):
        e = Entity("domain", "example.com")
        a = [Finding(e, "crtsh", "subdomain", "www.example.com", url="https://www.example.com/", confidence=0.6),
             Finding(e, "crtsh", "subdomain", "mail.example.com", url="https://mail.example.com", confidence=0.9)]
        b = [Finding(e, "hackertarget", "subdomain", "www.example.com", {"ip": "1.2.3.4"},
                     url="https://example.com", confidence=0.6)]
        out = fuse_findings([a, b])
        self.assertEqual(len(out), 2)
        top = out[0]
        self.assertEqual(top.sources, ["crtsh", "hackertarget"])
        self.assertEqual(top.data, {"ip": "1.2.3.4"})
        self.assertGreater(top.confidence, 0.6)
        self.assertTrue(all(0 <= f.confidence <= 1 for f in out))


if __name__ == "__main__":
    unittest.main()
