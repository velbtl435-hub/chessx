"""Offline tests for stage 3: profiles (exact username, official APIs), geo, Pwned Passwords k-anonymity."""
import hashlib, json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.osint.types import Entity
from chessx_libs.osint.http import Client, fixture_transport, HTTPError, RateLimited
from chessx_libs.osint.audit import AuditLog
from chessx_libs.osint.cache import Cache
from chessx_libs.osint.base import REGISTRY, SourceError, sources
from chessx_libs.osint.sources import pwned
import chessx_libs.osint.sources  # noqa: F401

FX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chessx_libs", "osint", "fixtures")


def fx(n):
    with open(os.path.join(FX, n), "rb") as f:
        return f.read()


def client(routes, calls=None, audit=None):
    return Client(transport=fixture_transport(routes, calls), audit=audit, sleep=lambda s: None)


ROUTES = {"api.github.com/users/niklasf": (200, {}, fx("gh.json")),
          "mastodon.social/api/v1/accounts/lookup": (200, {}, fx("masto.json")),
          "public.api.bsky.app": (200, {}, fx("bsky.json")),
          "lichess.org/api/user/": (200, {}, fx("lichess.json")),
          "api.chess.com/pub/player/": (200, {}, fx("chesscom.json"))}


class TestProfiles(unittest.TestCase):
    def test_each_platform_exact_lookup(self):
        calls, audit = [], AuditLog(":memory:")
        c = client(ROUTES, calls, audit)
        want = {"github": "niklasf", "mastodon": "Gargron", "bluesky": "bsky.app", "lichess": "DrNykterstein",
                "chesscom": "hikaru"}
        for name, user in want.items():
            out = REGISTRY[name].lookup(Entity("username", user), c)
            self.assertEqual(len(out), 1, name)
            self.assertTrue(out[0].url.startswith("https://"), name)
            self.assertEqual(out[0].kind, "profile")
        self.assertEqual(len(audit.read()), 5)  # every query audited
        for url, _ in calls:  # never follower/following enumeration
            self.assertNotRegex(url, r"follow")
        gh = REGISTRY["github"].lookup(Entity("username", "niklasf"), c)[0]
        self.assertNotIn("followers_url", gh.data)
        self.assertEqual(gh.data["login"], "niklasf")

    def test_not_found_and_invalid(self):
        c = client({"api.github.com": (404, {}, b"{}"), "bsky": (400, {}, b'{"error":"InvalidRequest"}')})
        self.assertEqual(REGISTRY["github"].lookup(Entity("username", "nobody"), c), [])
        self.assertEqual(REGISTRY["bluesky"].lookup(Entity("username", "nobody"), c), [])
        for bad in ("../etc", "a b", "x?y=1", "a@evil"):
            with self.assertRaises(SourceError):
                REGISTRY["github"].lookup(Entity("username", bad), c)

    def test_mastodon_respects_opt_out(self):
        d = json.loads(fx("masto.json"))
        d["discoverable"] = False
        out = REGISTRY["mastodon"].lookup(Entity("username", "Gargron"), client({"mastodon.social": (200, {}, d)}))
        self.assertEqual(out[0].data, {"acct": "Gargron", "opted_out_of_discovery": True})

    def test_lichess_ratings(self):
        out = REGISTRY["lichess"].lookup(Entity("username", "DrNykterstein"), client(ROUTES))[0]
        self.assertIn("blitz", out.data["ratings"])


class TestGeo(unittest.TestCase):
    def test_nominatim_search_and_reverse(self):
        c = client({"nominatim.openstreetmap.org/search": (200, {}, fx("nomi.json")),
                    "nominatim.openstreetmap.org/reverse": (200, {}, fx("nomirev.json"))})
        out = REGISTRY["nominatim"].lookup(Entity("geo", "Sao Paulo"), c)
        self.assertTrue(out and "OpenStreetMap" in out[0].data["attribution"])
        rev = REGISTRY["nominatim"].lookup(Entity("geo", "-23.55,-46.63"), c)
        self.assertIn("Paulo", rev[0].title)
        self.assertEqual(REGISTRY["nominatim"].rate, (1, 1.0))

    def test_ipapi_noncommercial(self):
        out = REGISTRY["ipapi"].lookup(Entity("ip", "8.8.8.8"), client({"ipapi.co": (200, {}, fx("ipapi.json"))}))
        self.assertEqual(out[0].data["city"], "Mountain View")
        self.assertFalse(REGISTRY["ipapi"].commercial_ok)
        self.assertNotIn("ipapi", {s.name for s in sources(commercial=True)})


class TestPwned(unittest.TestCase):
    def test_k_anonymity(self):
        pw = "password"
        full = hashlib.sha1(pw.encode()).hexdigest().upper()
        body = "003D68EB55068C33ACE09247EE4C639306B:29\n%s:52372427\n" % full[5:]
        calls, audit = [], AuditLog(":memory:")
        c = Client(transport=fixture_transport({"pwnedpasswords": (200, {}, body)}, calls), audit=audit,
                   cache=Cache(":memory:"))
        self.assertEqual(pwned.password_count(pw, c), 52372427)
        url, hdr = calls[0]
        self.assertTrue(url.endswith("/range/" + full[:5]))
        self.assertEqual(hdr["Add-Padding"], "true")
        blob = json.dumps(audit.read()) + url + json.dumps(hdr)
        self.assertNotIn(pw, blob.replace("pwnedpasswords", ""))
        self.assertNotIn(full[5:], blob)
        self.assertNotIn(full[:5], json.dumps(audit.read()))
        self.assertEqual(pwned.password_count("correct horse battery staple x9", c), 0)

    def test_parse_padding_zero(self):
        self.assertEqual(pwned.parse_range("ABC:0\nDEF:3", "DEF"), 3)


@unittest.skipUnless(os.environ.get("CHESSX_E2E") == "1", "real-network E2E: set CHESSX_E2E=1")
class TestPeopleE2E(unittest.TestCase):
    def test_live(self):
        cases = {"github": Entity("username", "niklasf"), "mastodon": Entity("username", "Gargron"),
                 "bluesky": Entity("username", "bsky.app"), "lichess": Entity("username", "DrNykterstein"),
                 "chesscom": Entity("username", "hikaru"), "nominatim": Entity("geo", "Sao Paulo"),
                 "ipapi": Entity("ip", "8.8.8.8")}
        for name, ent in cases.items():
            with self.subTest(source=name):
                try:
                    out = REGISTRY[name].lookup(ent, Client(max_wait=10))
                except RateLimited as e:
                    self.skipTest("%s rate limited: %s" % (name, e))
                except (HTTPError, OSError) as e:
                    self.skipTest("%s network failure: %s" % (name, e))
                self.assertTrue(out, name)
        try:
            self.assertGreater(pwned.password_count("password", Client()), 1000)
        except (HTTPError, OSError) as e:
            self.skipTest("pwned network failure: %s" % e)


if __name__ == "__main__":
    unittest.main()
