"""Solar position — NOAA Solar Calculator algorithm (Meeus-based), as in the NOAA GML spreadsheets
NOAA_Solar_Calculations_day.xls / _year.xls (https://gml.noaa.gov/grad/solcalc/calcdetails.html).
Column names below mirror the spreadsheet. Accuracy ~0.01° for 1800-2100 (NOAA's own statement:
theoretical accuracy better than one minute of arc; real-world limited by refraction).

Inverse (shadow) helpers: a vertical object of height h casting a shadow of length L on flat ground
gives apparent sun elevation atan(h/L); the shadow points away from the sun, so sun azimuth = shadow bearing + 180.
"""
import math
from dataclasses import dataclass
from datetime import datetime, timezone

_r, _d = math.radians, math.degrees


def julian_day(dt):
    """Aware datetime (naive = UTC) -> Julian Day."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp() / 86400.0 + 2440587.5


def datetime_from_jd(jd):
    return datetime.fromtimestamp((jd - 2440587.5) * 86400.0, tz=timezone.utc)


@dataclass(frozen=True)
class SunPosition:
    azimuth: float          # degrees clockwise from true north
    elevation: float        # apparent (refraction-corrected) degrees
    elevation_geometric: float
    declination: float
    equation_of_time: float  # minutes
    hour_angle: float

    def to_dict(self):
        return {k: round(v, 4) for k, v in self.__dict__.items()}


def _core(jd):
    jc = (jd - 2451545.0) / 36525.0                                            # Julian Century
    l0 = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360               # Geom Mean Long Sun
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)                        # Geom Mean Anom Sun
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)                   # Eccent Earth Orbit
    c = (math.sin(_r(m)) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
         + math.sin(_r(2 * m)) * (0.019993 - 0.000101 * jc) + math.sin(_r(3 * m)) * 0.000289)  # Eq of Ctr
    true_long = l0 + c
    omega = 125.04 - 1934.136 * jc
    app_long = true_long - 0.00569 - 0.00478 * math.sin(_r(omega))            # Sun App Long
    mean_obliq = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    obliq = mean_obliq + 0.00256 * math.cos(_r(omega))                         # Obliq Corr
    decl = _d(math.asin(math.sin(_r(obliq)) * math.sin(_r(app_long))))         # Sun Declin
    y = math.tan(_r(obliq / 2)) ** 2                                           # var y
    eot = 4 * _d(y * math.sin(2 * _r(l0)) - 2 * e * math.sin(_r(m))
                 + 4 * e * y * math.sin(_r(m)) * math.cos(2 * _r(l0))
                 - 0.5 * y * y * math.sin(4 * _r(l0)) - 1.25 * e * e * math.sin(2 * _r(m)))  # Eq of Time (min)
    return decl, eot


def refraction(elev):
    """Approx atmospheric refraction (degrees), NOAA spreadsheet formula."""
    if elev > 85:
        return 0.0
    t = math.tan(_r(elev))
    if elev > 5:
        s = 58.1 / t - 0.07 / t ** 3 + 0.000086 / t ** 5
    elif elev > -0.575:
        s = 1735 + elev * (-518.2 + elev * (103.4 + elev * (-12.79 + elev * 0.711)))
    else:
        s = -20.772 / t
    return s / 3600.0


def _position(lat, lon, jd, decl, eot):
    frac = (jd + 0.5) % 1.0                                                    # UTC day fraction
    tst = (frac * 1440 + eot + 4 * lon) % 1440                                 # True Solar Time (min)
    ha = tst / 4 + 180 if tst / 4 < 0 else tst / 4 - 180                        # Hour Angle
    cz = (math.sin(_r(lat)) * math.sin(_r(decl))
          + math.cos(_r(lat)) * math.cos(_r(decl)) * math.cos(_r(ha)))
    zen = _d(math.acos(max(-1.0, min(1.0, cz))))
    elev = 90 - zen
    den = math.cos(_r(lat)) * math.sin(_r(zen))
    if abs(den) < 1e-12:
        az = 180.0 if lat > decl else 0.0
    else:
        a = _d(math.acos(max(-1.0, min(1.0, (math.sin(_r(lat)) * math.cos(_r(zen)) - math.sin(_r(decl))) / den))))
        az = (a + 180) % 360 if ha > 0 else (540 - a) % 360
    return SunPosition(az, elev + refraction(elev), elev, decl, eot, ha)


def solar_position(lat, lon, utc_datetime):
    """NOAA solar position. lon east-positive. utc_datetime aware (any zone) or naive UTC."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("lat/lon out of range")
    jd = julian_day(utc_datetime)
    return _position(lat, lon, jd, *_core(jd))


# ------------------------------------------------------------------ inverse from a shadow
def elevation_from_shadow(height, length):
    if height <= 0 or length <= 0:
        raise ValueError("height and shadow length must be > 0")
    return _d(math.atan2(height, length))


def sun_azimuth_from_shadow(shadow_bearing):
    return (shadow_bearing + 180.0) % 360.0


def _angdiff(a, b):
    return abs((a - b + 180) % 360 - 180)


def latitude_bands(utc_datetime, elevation, azimuth=None, lon=None, tol=0.5, az_tol=None,
                   lat_step=0.05, lon_step=1.0):
    """Candidate latitude intervals where |apparent elevation - observed| <= tol (and, if azimuth given,
    |azimuth error| <= az_tol, default 4*tol). lon given -> scanned only there; else every lon_step degrees.
    Returns list of dicts {lon, lat_min, lat_max, best_lat, best_err} sorted by best_err. Deterministic."""
    az_tol = 4 * tol if az_tol is None else az_tol
    jd = julian_day(utc_datetime)
    decl, eot = _core(jd)
    lons = [lon] if lon is not None else [-180 + i * lon_step for i in range(int(round(360 / lon_step)))]
    n = int(round(180 / lat_step))
    bands = []
    for lo in lons:
        cur = None
        for i in range(n + 1):
            la = -90 + i * lat_step
            p = _position(la, lo, jd, decl, eot)
            err = abs(p.elevation - elevation)
            ok = err <= tol and (azimuth is None or _angdiff(p.azimuth, azimuth) <= az_tol)
            if ok:
                score = err + (_angdiff(p.azimuth, azimuth) / 4 if azimuth is not None else 0)
                if cur is None:
                    cur = {"lon": lo, "lat_min": la, "lat_max": la, "best_lat": la, "best_err": score}
                cur["lat_max"] = la
                if score < cur["best_err"]:
                    cur["best_lat"], cur["best_err"] = la, score
            elif cur is not None:
                bands.append(cur)
                cur = None
        if cur is not None:
            bands.append(cur)
    for b in bands:
        for k in ("lat_min", "lat_max", "best_lat", "best_err"):
            b[k] = round(b[k], 4)
    return sorted(bands, key=lambda b: (b["best_err"], b["lon"], b["lat_min"]))
