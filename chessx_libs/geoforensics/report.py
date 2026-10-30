"""Public API: analyze(path, shadow=None) -> Report. Offline, deterministic (pass now= for the future check)."""
from dataclasses import dataclass, field
from datetime import datetime
from .exif import read_metadata, gps_info, time_info
from .consistency import check, normalize_shadow
from .solar import latitude_bands


def _j(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.hex() if len(v) <= 64 else f"<{len(v)} bytes>"
    if isinstance(v, dict):
        return {str(k): _j(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_j(x) for x in v]
    if isinstance(v, float) and v != v:
        return None
    return v


@dataclass
class Report:
    path: str
    exif: dict = field(default_factory=dict)
    gps: dict = field(default_factory=dict)
    time: dict = field(default_factory=dict)
    camera: dict = field(default_factory=dict)
    sun: dict = None
    consistency: float = 1.0
    flags: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    disclaimer: str = "Location/time are estimates from metadata and geometry, never proof."

    def to_dict(self):
        return _j(self.__dict__)


def analyze(path, shadow=None, now=None, band_tol=0.5):
    """path: file path or bytes. shadow: {'height','length'[, 'bearing']} or {'elevation'[, 'azimuth']}.
    If the image has no GPS but has a UTC time and shadow, sun['latitude_bands'] gives candidate bands."""
    md = read_metadata(path)
    gps, ti = gps_info(md), time_info(md)
    score, flags, sun = check(gps, ti, shadow, now=now)
    sh = normalize_shadow(shadow)
    when = ti["utc"] or ti["gps_utc"]
    if sh and sh["elevation"] is not None and when is not None:
        sun = sun or {"observed": sh, "utc": when.isoformat()}
        sun["latitude_bands"] = latitude_bands(when, sh["elevation"], sh["azimuth"], lon=gps.get("lon"),
                                               tol=band_tol, lon_step=5.0)[:20]
    exif = dict(md.tags)
    exif.update({f"xmp:{k}": v for k, v in md.xmp.items()})
    return Report(path=path if isinstance(path, str) else "<bytes>", exif=exif, gps=gps, time=ti,
                  camera=md.camera(), sun=sun, consistency=score, flags=flags, errors=md.errors)
