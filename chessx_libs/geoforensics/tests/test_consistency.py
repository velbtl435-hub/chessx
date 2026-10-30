import math, unittest
from datetime import datetime, timezone, timedelta
from chessx_libs.geoforensics.consistency import check
from chessx_libs.geoforensics.solar import solar_position

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
UTC = datetime(2010, 6, 21, 18, 6, tzinfo=timezone.utc)
GPS = {"lat": 40.0, "lon": -105.0}


def tinfo(offset="-06:00", hours=-6, gps_utc=UTC, software=None, utc=UTC):
    orig = (utc + timedelta(hours=hours)).replace(tzinfo=None) if utc else None
    return {"original": orig, "offset": offset, "utc": utc if offset else None, "gps_utc": gps_utc,
            "software": software, "modified": None}


def codes(fl):
    return {f["code"] for f in fl}


class TestConsistency(unittest.TestCase):
    def test_clean(self):
        p = solar_position(40, -105, UTC)
        L = 2 / math.tan(math.radians(p.elevation))
        s, fl, sun = check(GPS, tinfo(), {"height": 2, "length": L, "bearing": (p.azimuth + 180) % 360}, now=NOW)
        self.assertEqual(s, 1.0, fl)
        self.assertLess(sun["elevation_error"], 0.01)

    def test_shadow_mismatch(self):
        s, fl, _ = check(GPS, tinfo(), {"elevation": 20, "azimuth": 90}, now=NOW)
        self.assertIn("shadow_elevation_mismatch", codes(fl))
        self.assertIn("shadow_azimuth_mismatch", codes(fl))
        self.assertLess(s, 0.5)

    def test_night_shadow(self):
        t = datetime(2010, 6, 21, 8, 30, tzinfo=timezone.utc)
        _, fl, _ = check(GPS, tinfo(utc=t, gps_utc=t), {"elevation": 30}, now=NOW)
        self.assertIn("sun_below_horizon", codes(fl))

    def test_offset_vs_lon(self):
        _, fl, _ = check(GPS, tinfo(offset="+08:00", hours=8), None, now=NOW)
        self.assertIn("offset_vs_longitude", codes(fl))

    def test_future_missing_offset_gps_mismatch_software(self):
        fut = NOW + timedelta(days=3)
        _, fl, _ = check(GPS, tinfo(utc=fut, gps_utc=fut), None, now=NOW)
        self.assertIn("future_date", codes(fl))
        _, fl, _ = check(GPS, tinfo(offset=None), None, now=NOW)
        self.assertIn("missing_offset", codes(fl))
        _, fl, _ = check(GPS, tinfo(gps_utc=UTC + timedelta(hours=5)), None, now=NOW)
        self.assertIn("gps_time_mismatch", codes(fl))
        s, fl, _ = check(GPS, tinfo(software="Adobe Photoshop 25.0"), None, now=NOW)
        self.assertIn("edited_software", codes(fl))
        self.assertTrue(0 <= s < 1)


if __name__ == "__main__":
    unittest.main()
