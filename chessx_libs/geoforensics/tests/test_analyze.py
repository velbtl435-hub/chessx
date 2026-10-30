import io, json, math, os, tempfile, unittest
from datetime import datetime, timezone
from chessx_libs.geoforensics import analyze, Report, solar_position
from chessx_libs.geoforensics.synth import build_tiff, build_jpeg, gps_ifd

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
UTC = datetime(2010, 6, 21, 18, 6, tzinfo=timezone.utc)


def synthetic(lat=40.0, lon=-105.0, offset="-06:00", local="2010:06:21 12:06:00", software=None, gps=True):
    ifd0 = {0x010F: (2, "SynthCam"), 0x0110: (2, "S1")}
    if software:
        ifd0[0x0131] = (2, software)
    ex = {0x9003: (2, local), 0xA434: (2, "Synth 35mm")}
    if offset:
        ex[0x9011] = (2, offset)
    g = gps_ifd(lat, lon, alt=1600, bearing=90, date="2010:06:21", time=(18, 6, 0)) if gps else None
    return build_jpeg(build_tiff(ifd0, ex, g))


class TestAnalyze(unittest.TestCase):
    def test_full_report_from_file(self):
        p = solar_position(40, -105, UTC)
        shadow = {"height": 1.0, "length": 1 / math.tan(math.radians(p.elevation)), "bearing": (p.azimuth + 180) % 360}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "synthetic.jpg")
            with open(path, "wb") as f:
                f.write(synthetic())
            r = analyze(path, shadow=shadow, now=NOW)
        self.assertIsInstance(r, Report)
        self.assertEqual(r.consistency, 1.0, r.flags)
        self.assertAlmostEqual(r.gps["lat"], 40, 4)
        self.assertEqual(r.camera["lens"], "Synth 35mm")
        self.assertTrue(any(b["lat_min"] <= 40 <= b["lat_max"] for b in r.sun["latitude_bands"]))
        d = r.to_dict()
        json.dumps(d)
        self.assertEqual(d["time"]["utc"], "2010-06-21T18:06:00+00:00")

    def test_deterministic(self):
        b = synthetic(software="GIMP 2.10")
        a1 = analyze(b, shadow={"elevation": 30}, now=NOW).to_dict()
        self.assertEqual(a1, analyze(b, shadow={"elevation": 30}, now=NOW).to_dict())
        codes = {f["code"] for f in a1["flags"]}
        self.assertTrue({"edited_software", "shadow_elevation_mismatch"} <= codes)
        self.assertLess(a1["consistency"], 0.7)

    def test_no_gps_bands_scan(self):
        r = analyze(synthetic(gps=False), shadow={"elevation": 69.69, "azimuth": 140.42}, now=NOW)
        self.assertIn("no_gps", {f["code"] for f in r.flags})
        self.assertTrue(any(b["lon"] == -105 and b["lat_min"] <= 40 <= b["lat_max"] for b in r.sun["latitude_bands"]))

    def test_pillow_made_image_no_metadata(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        bio = io.BytesIO()
        Image.new("RGB", (16, 16), (10, 200, 30)).save(bio, "PNG")
        r = analyze(bio.getvalue(), now=NOW)
        self.assertIsNone(r.gps["lat"])
        self.assertEqual(r.errors, [])

    def test_garbage(self):
        r = analyze(b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00MM\x00*zz", now=NOW)
        self.assertTrue(r.errors)
        json.dumps(r.to_dict())


if __name__ == "__main__":
    unittest.main()
