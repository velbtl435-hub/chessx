"""ChessX forensic geolocation (master list section 33, image part). Offline, deterministic.
Ethics: only analyze files you have the right to analyze; locations are estimates, never proof; no tracking people.

    from chessx_libs.geoforensics import analyze
    rep = analyze("photo.jpg", shadow={"height": 1.8, "length": 2.1, "bearing": 315})
    rep.consistency, rep.flags, rep.to_dict()
"""
from .exif import read_metadata, parse_tiff, parse_xmp, gps_info, time_info, Metadata
from .solar import solar_position, latitude_bands, elevation_from_shadow, sun_azimuth_from_shadow, SunPosition
from .consistency import check
from .report import analyze, Report

__all__ = ["analyze", "Report", "read_metadata", "parse_tiff", "parse_xmp", "gps_info", "time_info", "Metadata",
           "solar_position", "latitude_bands", "elevation_from_shadow", "sun_azimuth_from_shadow",
           "SunPosition", "check"]
