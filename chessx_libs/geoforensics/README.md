# chessx_libs.geoforensics — forensic geolocation (image part, master list §33)

Offline, deterministic, stdlib-only (Pillow optional). Extracts EXIF/XMP, computes the NOAA solar
position, inverts shadow measurements into latitude bands, and scores internal consistency.

```python
from chessx_libs.geoforensics import analyze
r = analyze("photo.jpg", shadow={"height": 1.8, "length": 2.1, "bearing": 315}, now=None)
r.gps, r.time, r.camera, r.sun, r.consistency, r.flags
r.to_dict()   # JSON-safe
```

Modules
- `exif.py` — JPEG APP1 Exif/XMP, raw TIFF, PNG eXIf/iTXt; IFD0/ExifIFD/GPS IFD, both endians, rationals;
  `gps_info` (lat, lon, alt, GPSImgDirection + ref), `time_info` (DateTimeOriginal + OffsetTime*, UTC, GPS UTC).
  Malformed input never raises; problems land in `errors`.
- `solar.py` — NOAA spreadsheet algorithm (`solar_position(lat, lon, utc) -> SunPosition`), `elevation_from_shadow`
  (atan(h/L)), `sun_azimuth_from_shadow` (bearing+180), `latitude_bands(utc, elevation, azimuth=None, lon=None, tol)`.
- `consistency.py` — `check(gps, time, shadow, now)` -> (score 0..1, flags, sun). Severities: info 0, low .05,
  medium .15, high .35 subtracted from 1.
- `synth.py` — hand-built TIFF/JPEG/XMP bytes for tests (no real photos).

Validation: `tests/test_solar.py` checks 16 rows of the official NOAA GML spreadsheets
(NOAA_Solar_Calculations_day.xls / _year.xls, cached cell values) at 0.5° tolerance; max observed error ~5e-5°.

Limits
- Time zone vs longitude: zones are political (China UTC+8 over ~60°, Spain, India +5:30, DST). Only flagged
  beyond 2.5 h, and only as a warning.
- Shadow method assumes a vertical object on level ground and true-north bearings; refraction is a standard-atmosphere
  approximation. One elevation gives a ring of positions; latitude bands are candidates, not a fix.
- A score of 1.0 means "no contradiction found", not "authentic": all metadata can be forged or stripped.

## Ethics
- Only analyze files you own or have the explicit right to analyze (your photos, consented case material,
  authorized investigations). Respect local privacy law.
- Every location/time produced here is an **estimate, never proof**. Do not accuse anyone based on it; corroborate.
- **Never use this to track, locate, stalk or identify people.** Do not run it on photos of private individuals
  to find where they live or are. Prefer stripping location metadata before sharing your own images.

Run tests: `python3 -m unittest discover -s chessx_libs/geoforensics/tests -t .`
