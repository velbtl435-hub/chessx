"""Offline tests for stage 4: investigate engine, cases/export, CLI."""
import contextlib, csv, io, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.osint.http import Client, fixture_transport, OfflineMiss
from chessx_libs.osint.cache import Cache
from chessx_libs.osint.audit import AuditLog
from chessx_libs.osint.engine import investigate
from chessx_libs.osint.case import Case, CaseStore
from chessx_libs.osint import cli

FX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chessx_libs", "osint", "fixtures")


def fx(n):
    with open(os.path.join(FX, n), "rb") as f:
        return f.read()


def gh_client(calls=None):
    return Client(transport=fixture_transport({"api.github.com/users/niklasf": (200, {}, fx("gh.json")),
                                               "lichess.org": (500, {}, b"boom")}, calls), max_retries=0,
                  cache=Cache(":memory:"), audit=AuditLog(":memory:"), sleep=lambda s: None)


class TestEngine(unittest.TestCase):
    def test_investigate_restricted_and_errors_collected(self):
        c = gh_client()
        out = investigate("niklasf", kind="username", sources=["github", "lichess"], client=c)
        self.assertEqual([f.source for f in out], ["github"])
        self.assertEqual(c.errors[0][0], "lichess")  # unrouted fixture -> error recorded, not raised
        self.assertTrue(any(r["action"] == "investigate" for r in c.audit.read()))

    def test_offline_uses_cache_only(self):
        calls = []
        c = gh_client(calls)
        investigate("niklasf", kind="username", sources=["github"], client=c)
        out = investigate("niklasf", kind="username", sources=["github"], client=c, offline=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(len(calls), 1)
        c2 = Client(cache=Cache(":memory:"), offline=True, transport=fixture_transport({}))
        self.assertEqual(investigate("8.8.8.8", sources=["ipapi"], client=c2), [])
        self.assertIn("OfflineMiss", c2.errors[0][2])

    def test_commercial_filter(self):
        c = Client(transport=fixture_transport({"ipapi.co": (200, {}, fx("ipapi.json"))}), sleep=lambda s: None)
        self.assertEqual(investigate("8.8.8.8", sources=["ipapi"], client=c, commercial=True), [])
        self.assertEqual(len(investigate("8.8.8.8", sources=["ipapi"], client=c, commercial=False)), 1)


class TestCase_(unittest.TestCase):
    def test_roundtrip_and_exports(self):
        with tempfile.TemporaryDirectory() as d:
            st = CaseStore(d)
            f = investigate("niklasf", kind="username", sources=["github"], client=gh_client())
            c = Case("demo")
            c.add("username:niklasf", f)
            st.save(c)
            self.assertEqual(st.list(), ["demo"])
            back = st.load("demo")
            self.assertEqual(back.findings[0].title, f[0].title)
            self.assertEqual(json.loads(back.to_json())["entities"], ["username:niklasf"])
            rows = list(csv.reader(io.StringIO(back.to_csv())))
            self.assertEqual(rows[0][0], "entity")
            self.assertEqual(rows[1][1], "github")
            self.assertIn("## username:niklasf", back.to_markdown())
            self.assertTrue(st.delete("demo"))
            with self.assertRaises(ValueError):
                Case("../x")


class TestCLI(unittest.TestCase):
    def run_cli(self, argv, **kw):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(argv, **kw)
        return code, buf.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("CHESSX_OSINT_DIR")

    def tearDown(self):
        self.tmp.cleanup()
        if self.old is None:
            os.environ.pop("CHESSX_OSINT_DIR", None)
        else:
            os.environ["CHESSX_OSINT_DIR"] = self.old

    def test_lookup_case_export(self):
        d = self.tmp.name
        code, out = self.run_cli(["--dir", d, "lookup", "niklasf", "--kind", "username", "--source", "github",
                                  "--case", "c1"], client=gh_client())
        self.assertEqual(code, 0)
        self.assertIn("GitHub niklasf", out)
        self.assertEqual(self.run_cli(["--dir", d, "case", "list"])[1].strip(), "c1")
        code, md = self.run_cli(["--dir", d, "case", "show", "c1", "--format", "md"])
        self.assertIn("# Case c1", md)
        p = os.path.join(d, "x.csv")
        self.run_cli(["--dir", d, "case", "export", "c1", "--format", "csv", "-o", p])
        self.assertTrue(open(p).read().startswith("entity,"))
        self.assertEqual(self.run_cli(["--dir", d, "case", "delete", "c1"])[0], 0)

    def test_sources_and_commercial(self):
        _, out = self.run_cli(["--dir", self.tmp.name, "sources"])
        self.assertIn("ipapi", out)
        _, out = self.run_cli(["--dir", self.tmp.name, "--commercial", "sources"])
        self.assertNotIn("ipapi", out)
        self.assertIn("rdap", out)

    def test_pwned_stdin_json(self):
        import hashlib
        h = hashlib.sha1(b"hunter2").hexdigest().upper()
        c = Client(transport=fixture_transport({"pwnedpasswords": (200, {}, "%s:17\n" % h[5:])}),
                   audit=AuditLog(":memory:"))
        code, out = self.run_cli(["--dir", self.tmp.name, "pwned"], client=c, stdin=io.StringIO("hunter2\n"))
        self.assertEqual(code, 1)
        self.assertIn("17", out)
        self.assertNotIn("hunter2", json.dumps(c.audit.read()))

    def test_bad_entity(self):
        self.assertEqual(self.run_cli(["--dir", self.tmp.name, "lookup", "x", "--kind", "asn"])[0], 2)


if __name__ == "__main__":
    unittest.main()
