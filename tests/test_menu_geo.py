import math, os, tempfile, unittest
from datetime import datetime, timezone
from chessx_libs.menu import registry as r
from chessx_libs.geoforensics import solar_position
from chessx_libs.geoforensics.synth import build_tiff, build_jpeg, gps_ifd

UTC = datetime(2010, 6, 21, 18, 6, tzinfo=timezone.utc)


def _img(d):
    ifd0 = {0x010F: (2, "SynthCam"), 0x0110: (2, "S1")}
    ex = {0x9003: (2, "2010:06:21 12:06:00"), 0x9011: (2, "-06:00")}
    g = gps_ifd(40.0, -105.0, alt=1600, bearing=90, date="2010:06:21", time=(18, 6, 0))
    p = os.path.join(d, "s.jpg")
    with open(p, "wb") as f:
        f.write(build_jpeg(build_tiff(ifd0, ex, g)))
    return p


def _ask(answers):
    it = iter(answers)
    return lambda prompt: next(it, "")


class TestMenuGeo(unittest.TestCase):
    def test_entry_registered(self):
        e = [e for e in r.ENTRIES if e.key == "30"][0]
        self.assertEqual(e.label, "menu_geo")
        self.assertEqual(r.LABELS["menu_geo"], "Geolocalização forense")

    def test_parse_shadow(self):
        self.assertIsNone(r._parse_shadow(""))
        self.assertEqual(r._parse_shadow("1.8 2.1"), {"height": 1.8, "length": 2.1})
        self.assertEqual(r._parse_shadow("1,2,315")["bearing"], 315.0)
        with self.assertRaises(ValueError):
            r._parse_shadow("1")

    def test_no_shadow(self):
        with tempfile.TemporaryDirectory() as d:
            out = r._geo(None, _ask([_img(d), ""]))
        self.assertIn("consistency", out)
        self.assertIn("gps:", out)
        self.assertIn("disclaimer", out)

    def test_consistent_shadow(self):
        p = solar_position(40, -105, UTC)
        sh = "1 %f %f" % (1 / math.tan(math.radians(p.elevation)), (p.azimuth + 180) % 360)
        with tempfile.TemporaryDirectory() as d:
            out = r._geo(None, _ask([_img(d), sh]))
        self.assertNotIn("shadow_elevation_mismatch", out)

    def test_bad_shadow_clean_error(self):
        with tempfile.TemporaryDirectory() as d:
            out = r._geo(None, _ask([_img(d), "x y"]))
        self.assertTrue(out.startswith("geoforensics error: ValueError"))

    def test_missing_file_clean_error(self):
        out = r._geo(None, _ask(["/nonexistent/x.jpg", ""]))
        self.assertTrue(out.startswith("geoforensics error:"))
        self.assertNotIn("Traceback", out)

    def test_no_path(self):
        self.assertEqual(r._geo(None, _ask([""])), "no path")


if __name__ == "__main__":
    unittest.main()
