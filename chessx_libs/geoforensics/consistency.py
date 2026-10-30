"""Internal-consistency checks -> score in [0, 1] (1 = no contradictions found) + flags.

A high score means "no contradiction detected", NOT that metadata is authentic: every field can be forged.
Limits of the timezone check: civil time zones follow politics, not lon/15 (China spans ~60° on UTC+8,
Spain sits on UTC+1/+2, India +5:30, Nepal +5:45, DST adds 1 h, some zones are +13/+14). We therefore
allow |offset - lon/15| <= 2.5 h before flagging (plus 0.5 h warning band) and only ever WARN.
"""
from datetime import datetime, timezone, timedelta
from .solar import solar_position, elevation_from_shadow, sun_azimuth_from_shadow

PENALTY = {"info": 0.0, "low": 0.05, "medium": 0.15, "high": 0.35}
EDITORS = ("photoshop", "lightroom", "gimp", "snapseed", "affinity", "pixelmator", "picsart", "facetune",
           "capture one", "darktable", "rawtherapee", "paint.net", "canva", "luminar", "exiftool", "vsco")


def normalize_shadow(shadow):
    """dict with (height & length) or elevation; optional bearing (shadow direction, deg) or azimuth (sun)."""
    if not shadow:
        return None
    el = shadow.get("elevation")
    if el is None and shadow.get("height") is not None:
        el = elevation_from_shadow(float(shadow["height"]), float(shadow["length"]))
    az = shadow.get("azimuth")
    if az is None and shadow.get("bearing") is not None:
        az = sun_azimuth_from_shadow(float(shadow["bearing"]))
    return {"elevation": el, "azimuth": az}


def _flag(flags, code, severity, detail):
    flags.append({"code": code, "severity": severity, "detail": detail})


def check(gps, tinfo, shadow=None, now=None, el_tol=2.0, az_tol=10.0):
    """gps: exif.gps_info dict; tinfo: exif.time_info dict; shadow: see normalize_shadow.
    now: aware datetime for the future-date check (pass explicitly for determinism).
    Returns (score, flags, sun_dict|None)."""
    flags, sun = [], None
    now = now or datetime.now(timezone.utc)
    orig, utc, gutc = tinfo.get("original"), tinfo.get("utc"), tinfo.get("gps_utc")
    has_gps = gps.get("lat") is not None

    if orig is None:
        _flag(flags, "no_datetime_original", "low", "DateTimeOriginal missing")
    if orig is not None and not tinfo.get("offset"):
        _flag(flags, "missing_offset", "low", "no OffsetTimeOriginal/OffsetTime: local time zone unknown")
    if not has_gps:
        _flag(flags, "no_gps", "info", "no GPS position in EXIF/XMP")

    # future dates (local time could be up to +14h ahead of UTC)
    for name, dt in (("original", utc), ("gps_utc", gutc)):
        if dt is not None and dt > now + timedelta(minutes=5):
            _flag(flags, "future_date", "high", f"{name} {dt.isoformat()} is after {now.isoformat()}")
    if utc is None and orig is not None and orig > (now + timedelta(hours=14)).replace(tzinfo=None):
        _flag(flags, "future_date", "high", f"DateTimeOriginal {orig} is in the future")
    if orig is not None and orig.year < 1990:
        _flag(flags, "implausible_date", "medium", f"DateTimeOriginal year {orig.year} (camera clock reset?)")

    # GPS timestamp vs DateTimeOriginal
    if gutc is not None and utc is not None:
        d = abs((gutc - utc).total_seconds())
        if d > 3600:
            _flag(flags, "gps_time_mismatch", "high", f"GPS time differs from DateTimeOriginal by {d/3600:.1f} h")
        elif d > 120:
            _flag(flags, "gps_time_mismatch", "low", f"GPS time differs by {d:.0f} s (GPS fix may be stale)")
    elif gutc is not None and orig is not None and has_gps:
        d = (orig - gutc.replace(tzinfo=None)).total_seconds() / 3600  # implied offset
        if abs(d * 4 - round(d * 4)) > 0.05 or abs(d) > 14:
            _flag(flags, "gps_time_mismatch", "medium", f"implied UTC offset {d:+.2f} h is not a real zone")

    # Offset vs longitude
    if has_gps and utc is not None and orig is not None:
        off_h = (orig - utc.replace(tzinfo=None)).total_seconds() / 3600
        diff = abs((off_h - gps["lon"] / 15 + 12) % 24 - 12)
        if diff > 3.0:
            _flag(flags, "offset_vs_longitude", "medium",
                  f"offset {off_h:+.2f} h vs lon/15 = {gps['lon']/15:+.2f} h (Δ {diff:.1f} h; zones are political, see limits)")
        elif diff > 2.5:
            _flag(flags, "offset_vs_longitude", "low", f"offset {off_h:+.2f} h vs lon/15 {gps['lon']/15:+.2f} h")

    # Software / edits
    sw = (tinfo.get("software") or "")
    if sw and any(e in sw.lower() for e in EDITORS):
        _flag(flags, "edited_software", "medium", f"Software tag: {sw}")
    mod = tinfo.get("modified")
    if mod is not None and orig is not None and abs((mod - orig).total_seconds()) > 60:
        _flag(flags, "modified_after_capture", "low", f"DateTime {mod} differs from original {orig}")

    # Sun / shadow
    sh = normalize_shadow(shadow)
    when = utc or gutc
    if sh and has_gps and when is not None:
        p = solar_position(gps["lat"], gps["lon"], when)
        sun = {"expected": p.to_dict(), "observed": sh, "utc": when.isoformat()}
        if sh["elevation"] is not None:
            de = abs(p.elevation - sh["elevation"])
            sun["elevation_error"] = round(de, 3)
            if p.elevation <= 0:
                _flag(flags, "sun_below_horizon", "high", f"sun at {p.elevation:.1f}° at EXIF time/place, but shadow present")
            elif de > 3 * el_tol:
                _flag(flags, "shadow_elevation_mismatch", "high", f"shadow implies {sh['elevation']:.1f}°, NOAA {p.elevation:.1f}°")
            elif de > el_tol:
                _flag(flags, "shadow_elevation_mismatch", "low", f"shadow {sh['elevation']:.1f}° vs NOAA {p.elevation:.1f}°")
        if sh["azimuth"] is not None:
            da = abs((p.azimuth - sh["azimuth"] + 180) % 360 - 180)
            sun["azimuth_error"] = round(da, 3)
            if da > 3 * az_tol:
                _flag(flags, "shadow_azimuth_mismatch", "high", f"shadow implies sun az {sh['azimuth']:.1f}°, NOAA {p.azimuth:.1f}°")
            elif da > az_tol:
                _flag(flags, "shadow_azimuth_mismatch", "low", f"sun az {sh['azimuth']:.1f}° vs NOAA {p.azimuth:.1f}°")
    elif sh:
        _flag(flags, "shadow_unchecked", "info", "shadow given but GPS or UTC time missing")

    score = 1.0 - sum(PENALTY[f["severity"]] for f in flags)
    return round(max(0.0, min(1.0, score)), 3), flags, sun
