"""Menu entry 28 (OSINT) + argon2 label: offline, mocked client, password never echoed."""
import hashlib, os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.menu import registry as r
from chessx_libs import osint
from chessx_libs.osint.types import Finding, Entity

SECRET = "hunter2-correct-horse"


class FakeClient:
    def __init__(self, count=7):
        sha = hashlib.sha1(SECRET.encode()).hexdigest().upper()
        self.suffix, self.count, self.calls = sha[5:], count, []
        self.errors, self.audit, self.offline = [], None, True

    def get_text(self, url, **kw):
        self.calls.append((url, kw))
        return "0000000000000000000000000000000000A:1\r\n%s:%d\r\n" % (self.suffix, self.count)


def asker(*answers):
    it = iter(answers)
    return lambda prompt: next(it, "")


class TestOsintEntry(unittest.TestCase):
    def test_registered_lazy(self):
        e = [x for x in r.ENTRIES if x.module == "osint"]
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0].label, "menu_osint")
        self.assertIn("menu_osint", r.LABELS)

    def test_investigate_commercial_false_compact(self):
        f = Finding(entity=Entity("domain", "example.com"), source="rdap", kind="rdap",
                    title="registrar X", url="https://rdap.org/domain/example.com", confidence=0.9)
        with mock.patch.object(osint, "investigate", return_value=[f]) as inv:
            out = r._osint(None, asker("example.com"), client=FakeClient())
        self.assertEqual(inv.call_args.kwargs["commercial"], False)
        self.assertIn("[rdap] rdap", out)
        self.assertIn("example.com", out)
        self.assertEqual(len(out.splitlines()), 1)

    def test_no_findings(self):
        with mock.patch.object(osint, "investigate", return_value=[]):
            self.assertIn("no findings", r._osint(None, asker("nobody"), client=FakeClient()))

    def test_empty_entity(self):
        self.assertEqual(r._osint(None, asker(""), client=FakeClient()), "")

    def test_pwned_uses_getpass_and_never_echoes(self):
        c = FakeClient(count=7)
        gp = mock.Mock(return_value=SECRET)
        ask = mock.Mock(side_effect=["pwned"])
        out = r._osint(None, ask, client=c, getpass_fn=gp)
        gp.assert_called_once()
        self.assertIn("7 times", out)
        self.assertNotIn(SECRET, out)
        for url, kw in c.calls:  # only the 5-char prefix leaves; no plaintext anywhere
            self.assertNotIn(SECRET, url + repr(kw))
            self.assertNotIn(c.suffix, url)
        for call in ask.call_args_list:
            self.assertNotIn(SECRET, repr(call))

    def test_pwned_not_found(self):
        out = r._osint(None, asker("pwned"), client=FakeClient(count=0), getpass_fn=lambda p: SECRET)
        self.assertIn("not found", out)

    def test_pwned_error_hides_password(self):
        class Boom(FakeClient):
            def get_text(self, url, **kw):
                raise RuntimeError("bad " + SECRET)
        out = r._osint(None, asker("pwned"), client=Boom(), getpass_fn=lambda p: SECRET)
        self.assertIn("failed", out)
        self.assertNotIn(SECRET, out)


class TestArgon2Label(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(r.argon2_label("argon2-cffi"), "argon2-cffi")
        self.assertIn("cryptography", r.argon2_label("cryptography"))
        self.assertIn("unavailable", r.argon2_label("none"))
        for v in r.ARGON2_LABELS.values():
            self.assertNotIn("scrypt", v)


if __name__ == "__main__":
    unittest.main()
