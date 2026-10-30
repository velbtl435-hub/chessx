"""Stage 5: offline file metadata source and the public API surface."""
import io, contextlib, inspect, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import osint
from chessx_libs.osint.http import Client, fixture_transport


class TestMetadata(unittest.TestCase):
    def test_file_investigation_offline(self):
        calls = []
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("contact admin@example.org, see https://www.example.com/x and 8.8.8.8\n")
        try:
            c = Client(offline=True, transport=fixture_transport({}, calls), audit=osint.AuditLog(":memory:"))
            out = osint.investigate(f.name, client=c)
            kinds = {x.kind for x in out}
            self.assertTrue({"file.meta", "file.hash", "file.indicators"} <= kinds, kinds)
            self.assertEqual(calls, [])
            ind = [x for x in out if x.kind == "file.indicators"][0]
            self.assertIn(osint.Entity("domain", "www.example.com"), ind.related)
            self.assertIn("email:admin@example.org", [str(e) for e in ind.related])
        finally:
            os.unlink(f.name)

    def test_depth_does_not_pivot_to_people(self):
        from chessx_libs.osint.engine import PIVOT_KINDS
        self.assertNotIn("email", PIVOT_KINDS)
        self.assertNotIn("username", PIVOT_KINDS)

    def test_detect_file(self):
        self.assertEqual(osint.detect_kind("/etc/hostname"), "file")
        self.assertEqual(osint.detect_kind("./x.bin"), "file")


class TestPublicAPI(unittest.TestCase):
    def test_signatures(self):
        self.assertEqual(list(inspect.signature(osint.investigate).parameters),
                         ["entity", "sources", "depth", "client", "commercial", "offline", "kind"])
        self.assertIn("argv", inspect.signature(osint.cli.main).parameters)
        for name in osint.__all__:
            self.assertTrue(hasattr(osint, name), name)
        self.assertTrue(osint.investigate.__doc__ and osint.cli.main.__doc__)

    def test_cli_sources_lists_all(self):
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(buf):
            self.assertEqual(osint.cli.main(["--dir", d, "sources"]), 0)
        os.environ.pop("CHESSX_OSINT_DIR", None)
        for n in ("rdap", "github", "nominatim", "metadata", "ipapi"):
            self.assertIn(n, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
