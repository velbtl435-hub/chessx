"""NOAA validation.

SOURCE of reference values: the official NOAA GML spreadsheets
  https://gml.noaa.gov/grad/solcalc/NOAA_Solar_Calculations_day.xls   (2010-06-21, lat 40, lon -105, tz -6)
  https://gml.noaa.gov/grad/solcalc/NOAA_Solar_Calculations_year.xls  (2010, local noon tz -7, lat 40, lon -105)
downloaded 2026-10-30 (HTTP 200); values are the CACHED computed cells as saved in the published files
(read with xlrd): "Solar Elevation corrected for atm refraction (deg)" and "Solar Azimuth Angle (deg cw from N)".
The instant of each row is taken from the sheet's own Julian Day column (day sheet: JD0 + k*0.1h; year sheet:
local 12:00 at tz -7 = 19:00 UTC). No values were invented or recomputed by us. Tolerance 0.5 deg.
"""
import math, unittest
from datetime import datetime, timezone
from chessx_libs.geoforensics.solar import (solar_position, julian_day, elevation_from_shadow,
                                            sun_azimuth_from_shadow, latitude_bands)

U = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
NOAA = [  # (UTC, lat, lon, corrected elevation, azimuth)
    ("2010-06-21 06:06", 40.0, -105.0, -25.2335, 345.8691),
    ("2010-06-21 08:30", 40.0, -105.0, -23.2943, 22.0451),
    ("2010-06-21 10:54", 40.0, -105.0, -6.6187, 51.6197),
    ("2010-06-21 13:18", 40.0, -105.0, 17.8322, 73.9680),
    ("2010-06-21 15:42", 40.0, -105.0, 45.0834, 96.0785),
    ("2010-06-21 18:06", 40.0, -105.0, 69.6868, 140.4221),
    ("2010-06-21 20:30", 40.0, -105.0, 65.1214, 234.9033),
    ("2010-06-21 22:54", 40.0, -105.0, 38.9043, 269.4467),
    ("2010-06-22 01:18", 40.0, -105.0, 11.9785, 290.7166),
    ("2010-06-22 03:42", 40.0, -105.0, -11.2947, 314.2305),
    ("2010-01-01 19:00", 40.0, -105.0, 27.0641, 179.0475),
    ("2010-02-15 19:00", 40.0, -105.0, 37.4038, 175.6561),
    ("2010-03-21 19:00", 40.0, -105.0, 50.4003, 177.2169),
    ("2010-06-21 19:00", 40.0, -105.0, 73.4385, 178.5332),
    ("2010-09-21 19:00", 40.0, -105.0, 50.5029, 182.7421),
    ("2010-12-21 19:00", 40.0, -105.0, 26.5929, 180.4620),
]


class TestNOAA(unittest.TestCase):
    def test_julian_day_matches_sheet(self):
        self.assertAlmostEqual(julian_day(U("2010-01-01 19:00")), 2455198.2916666665, 6)
        self.assertAlmostEqual(julian_day(U("2010-06-21 06:06")), 2455368.754166667, 6)

    def test_reference_table(self):
        worst = 0.0
        for t, lat, lon, el, az in NOAA:
            p = solar_position(lat, lon, U(t))
            de, da = abs(p.elevation - el), abs((p.azimuth - az + 180) % 360 - 180)
            worst = max(worst, de, da)
            self.assertLessEqual(de, 0.5, t)
            self.assertLessEqual(da, 0.5, t)
        self.assertLess(worst, 0.05)  # same formulas -> essentially exact

    def test_range_check(self):
        with self.assertRaises(ValueError):
            solar_position(91, 0, U("2010-01-01 00:00"))


class TestInverse(unittest.TestCase):
    def test_shadow_geometry(self):
        self.assertAlmostEqual(elevation_from_shadow(1, 1), 45.0)
        self.assertAlmostEqual(sun_azimuth_from_shadow(350), 170.0)
        with self.assertRaises(ValueError):
            elevation_from_shadow(1, 0)

    def test_band_contains_truth_lon_given(self):
        t = U("2010-06-21 18:06")
        p = solar_position(40, -105, t)
        L = 1 / math.tan(math.radians(p.elevation))
        el = elevation_from_shadow(1, L)
        bands = latitude_bands(t, el, lon=-105, tol=0.5)
        self.assertTrue(any(b["lat_min"] <= 40 <= b["lat_max"] for b in bands))
        # azimuth disambiguates the two-solution case
        withaz = latitude_bands(t, el, azimuth=sun_azimuth_from_shadow((p.azimuth + 180) % 360), lon=-105, tol=0.5)
        self.assertTrue(withaz and all(b["lat_min"] <= 40 <= b["lat_max"] for b in withaz))
        self.assertAlmostEqual(withaz[0]["best_lat"], 40, delta=0.5)

    def test_lon_scan_deterministic(self):
        t = U("2010-03-21 19:00")
        a = latitude_bands(t, 50.4, azimuth=177.2, tol=0.5, lon_step=5)
        self.assertEqual(a, latitude_bands(t, 50.4, azimuth=177.2, tol=0.5, lon_step=5))
        self.assertTrue(any(b["lon"] == -105 and b["lat_min"] <= 40 <= b["lat_max"] for b in a))


if __name__ == "__main__":
    unittest.main()
