"""EXIF / XMP metadata extraction (stdlib; Pillow optional).

Parses JPEG APP1 Exif and XMP, raw TIFF, PNG eXIf/iTXt. TIFF IFD0 + ExifIFD + GPS IFD, both byte orders,
all standard types (BYTE ASCII SHORT LONG RATIONAL UNDEFINED SLONG SRATIONAL). Robust: bounds-checked,
loop-protected, never raises on malformed data (errors are collected in Metadata.errors).
"""
import re
import struct
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

TAGS = {  # IFD0 / ExifIFD
    0x010F: "Make", 0x0110: "Model", 0x0131: "Software", 0x0132: "DateTime", 0x013B: "Artist",
    0x0112: "Orientation", 0x8769: "ExifIFDPointer", 0x8825: "GPSInfoIFDPointer",
    0x9003: "DateTimeOriginal", 0x9004: "DateTimeDigitized", 0x9010: "OffsetTime",
    0x9011: "OffsetTimeOriginal", 0x9012: "OffsetTimeDigitized", 0x9290: "SubSecTime",
    0xA433: "LensMake", 0xA434: "LensModel", 0xA432: "LensSpecification", 0x920A: "FocalLength",
    0xA405: "FocalLengthIn35mmFilm", 0xA431: "BodySerialNumber",
}
GPS_TAGS = {
    0: "GPSVersionID", 1: "GPSLatitudeRef", 2: "GPSLatitude", 3: "GPSLongitudeRef", 4: "GPSLongitude",
    5: "GPSAltitudeRef", 6: "GPSAltitude", 7: "GPSTimeStamp", 16: "GPSImgDirectionRef", 17: "GPSImgDirection",
    18: "GPSMapDatum", 29: "GPSDateStamp",
}
_TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 6: ("b", 1), 7: ("B", 1),
          8: ("h", 2), 9: ("i", 4), 10: ("ii", 8), 11: ("f", 4), 12: ("d", 8)}
MAX_ENTRIES = 1000


@dataclass
class Metadata:
    tags: dict = field(default_factory=dict)     # flat: name -> value (IFD0/Exif/GPS)
    xmp: dict = field(default_factory=dict)      # 'ns:Name' -> string
    source: str = ""                             # 'jpeg', 'tiff', 'png', 'pillow', ...
    errors: list = field(default_factory=list)

    # ---- convenience accessors
    def get(self, *names):
        for n in names:
            if self.tags.get(n) not in (None, ""):
                return self.tags[n]
            for k, v in self.xmp.items():
                if k.split(":")[-1] == n and v not in (None, ""):
                    return v
        return None

    @property
    def gps(self):
        return gps_info(self)

    def camera(self):
        return {"make": _s(self.get("Make")), "model": _s(self.get("Model")),
                "lens": _s(self.get("LensModel", "Lens")), "software": _s(self.get("Software", "CreatorTool"))}


def _s(v):
    return v.strip("\x00 ").strip() if isinstance(v, str) else v


# ---------------------------------------------------------------- TIFF
def parse_tiff(data, errors=None):
    """TIFF/Exif bytes (starting at 'II*\\0' or 'MM\\0*') -> flat {tag_name: value}."""
    errors = errors if errors is not None else []
    out = {}
    if len(data) < 8 or data[:2] not in (b"II", b"MM"):
        errors.append("not a TIFF header")
        return out
    e = "<" if data[:2] == b"II" else ">"
    try:
        if struct.unpack(e + "H", data[2:4])[0] != 42:
            errors.append("bad TIFF magic")
            return out
        ifd0 = struct.unpack(e + "I", data[4:8])[0]
    except struct.error:
        errors.append("truncated TIFF header")
        return out
    seen = set()

    def read_ifd(off, names, depth=0):
        if off in seen or depth > 4 or off + 2 > len(data):
            if off in seen:
                errors.append(f"IFD loop at {off}")
            return
        seen.add(off)
        n = struct.unpack(e + "H", data[off:off + 2])[0]
        if n > MAX_ENTRIES:
            errors.append(f"IFD at {off} has {n} entries")
            return
        for i in range(n):
            p = off + 2 + 12 * i
            if p + 12 > len(data):
                errors.append("truncated IFD")
                return
            tag, typ, cnt = struct.unpack(e + "HHI", data[p:p + 8])
            if typ not in _TYPES:
                continue
            fmt, size = _TYPES[typ]
            total = size * cnt
            if cnt > 1 << 20:
                errors.append(f"tag {tag:#x} count too large")
                continue
            if total <= 4:
                raw = data[p + 8:p + 8 + total]
            else:
                vo = struct.unpack(e + "I", data[p + 8:p + 12])[0]
                if vo + total > len(data):
                    errors.append(f"tag {tag:#x} value out of bounds")
                    continue
                raw = data[vo:vo + total]
            try:
                val = _decode(e, typ, fmt, cnt, raw)
            except (struct.error, ValueError) as ex:
                errors.append(f"tag {tag:#x}: {ex}")
                continue
            name = names.get(tag, f"Tag{tag:#06x}")
            if tag == 0x8769 and names is TAGS:
                read_ifd(_first(val), TAGS, depth + 1)
            elif tag == 0x8825 and names is TAGS:
                read_ifd(_first(val), GPS_TAGS, depth + 1)
            elif name not in out:
                out[name] = val

    try:
        read_ifd(ifd0, TAGS)
    except Exception as ex:  # pragma: no cover - last-resort robustness
        errors.append(f"TIFF parse error: {ex}")
    return out


def _first(v):
    return v[0] if isinstance(v, (list, tuple)) else v


def _decode(e, typ, fmt, cnt, raw):
    if typ == 2:
        return raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
    if typ == 7:
        return bytes(raw) if cnt > 4 or cnt == 0 else list(raw)
    if typ in (5, 10):
        vals = struct.unpack(e + fmt[0] * (2 * cnt), raw)
        rs = [(vals[2 * i] / vals[2 * i + 1]) if vals[2 * i + 1] else float("nan") for i in range(cnt)]
        return rs[0] if cnt == 1 else rs
    vals = list(struct.unpack(e + fmt * cnt, raw))
    return vals[0] if cnt == 1 else vals


# ---------------------------------------------------------------- XMP
_XMP_ATTR = re.compile(r'\b([A-Za-z][\w-]*):([A-Za-z][\w-]*)\s*=\s*"([^"]*)"')
_XMP_ELEM = re.compile(r"<([A-Za-z][\w-]*):([A-Za-z][\w-]*)>([^<]*)</\1:\2>")
XMP_NS = ("exif", "exifEX", "tiff", "xmp", "aux", "photoshop", "dc")


def parse_xmp(text):
    """XMP packet -> {'ns:Name': str} for exif/exifEX/tiff/xmp/aux/photoshop namespaces (attrs and elements)."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    out = {}
    for rx in (_XMP_ATTR, _XMP_ELEM):
        for ns, name, val in rx.findall(text):
            if ns in XMP_NS and ns != "xmlns":
                out.setdefault(f"{ns}:{name}", val.strip())
    return out


def xmp_coord(s):
    """XMP GPS string 'DDD,MM.mmk' or 'DDD,MM,SSk' (k in NSEW) or signed decimal -> float degrees."""
    if s is None:
        return None
    s = str(s).strip()
    m = re.fullmatch(r"(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)(?:,(\d+(?:\.\d+)?))?\s*([NSEWnsew])", s)
    if m:
        d = float(m[1]) + float(m[2]) / 60 + (float(m[3]) / 3600 if m[3] else 0)
        return -d if m[4].upper() in "SW" else d
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------- containers
def read_metadata(src):
    """Path or bytes -> Metadata. Never raises on malformed input (except unreadable path)."""
    if isinstance(src, (bytes, bytearray)):
        data = bytes(src)
    else:
        with open(src, "rb") as f:
            data = f.read()
    md = Metadata()
    try:
        if data[:2] == b"\xff\xd8":
            md.source = "jpeg"
            _jpeg(data, md)
        elif data[:4] in (b"II*\x00", b"MM\x00*"):
            md.source = "tiff"
            md.tags = parse_tiff(data, md.errors)
            xmp = md.tags.pop("Tag0x02bc", None)  # XMP in TIFF tag 700
            if xmp:
                md.xmp = parse_xmp(bytes(xmp) if isinstance(xmp, (list, bytes)) else xmp)
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            md.source = "png"
            _png(data, md)
        else:
            md.source = "unknown"
            _pillow(src, md)
        m = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", data, re.S)  # sidecar-style / any container
        if m and not md.xmp:
            md.xmp = parse_xmp(m.group(0))
    except Exception as ex:  # robustness: report, don't crash
        md.errors.append(f"parse error: {type(ex).__name__}: {ex}")
    return md


def _jpeg(data, md):
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            md.errors.append(f"bad JPEG marker at {i}")
            return
        marker = data[i + 1]
        if marker in (0xD9, 0xDA):  # EOI / start of scan: no more metadata
            return
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            i += 2
            continue
        ln = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i + 4:i + 2 + ln]
        if marker == 0xE1:
            if seg[:6] == b"Exif\x00\x00":
                md.tags.update(parse_tiff(seg[6:], md.errors))
            elif seg.startswith(b"http://ns.adobe.com/xap/1.0/\x00"):
                md.xmp.update(parse_xmp(seg[29:]))
        i += 2 + ln


def _png(data, md):
    i = 8
    while i + 8 <= len(data):
        ln, typ = struct.unpack(">I4s", data[i:i + 8])
        body = data[i + 8:i + 8 + ln]
        if typ == b"eXIf":
            md.tags.update(parse_tiff(body[6:] if body[:6] == b"Exif\x00\x00" else body, md.errors))
        elif typ == b"iTXt" and body.startswith(b"XML:com.adobe.xmp\x00"):
            rest = body[len(b"XML:com.adobe.xmp\x00"):]
            comp = rest[0] if rest else 0
            txt = rest[2:].split(b"\x00", 2)[-1]
            md.xmp.update(parse_xmp(zlib.decompress(txt) if comp else txt))
        if typ == b"IEND":
            break
        i += 12 + ln


def _pillow(src, md):
    try:
        from PIL import Image
    except ImportError:
        md.errors.append("unknown format and Pillow not installed")
        return
    try:
        import io
        img = Image.open(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src)
        raw = img.info.get("exif")
        if raw:
            md.source = "pillow"
            md.tags.update(parse_tiff(raw[6:] if raw[:6] == b"Exif\x00\x00" else raw, md.errors))
        if img.info.get("xmp"):
            md.xmp.update(parse_xmp(img.info["xmp"]))
    except Exception as ex:
        md.errors.append(f"Pillow: {ex}")


# ---------------------------------------------------------------- derived values
def _dms(v, ref):
    try:
        if isinstance(v, (list, tuple)):
            d = v[0] + (v[1] if len(v) > 1 else 0) / 60 + (v[2] if len(v) > 2 else 0) / 3600
        else:
            d = float(v)
    except (TypeError, ValueError):
        return None
    if d != d:  # NaN
        return None
    return -d if str(ref or "").strip().upper()[:1] in ("S", "W") else d


def gps_info(md):
    """-> dict lat, lon, alt, bearing, bearing_ref ('T' true / 'M' magnetic), utc (datetime|None), source."""
    t = md.tags
    lat, lon, src = _dms(t.get("GPSLatitude"), t.get("GPSLatitudeRef")), _dms(t.get("GPSLongitude"), t.get("GPSLongitudeRef")), "exif"
    if lat is None or lon is None:
        lat, lon, src = xmp_coord(md.xmp.get("exif:GPSLatitude")), xmp_coord(md.xmp.get("exif:GPSLongitude")), "xmp"
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        lat = lon = None
    alt = t.get("GPSAltitude")
    if alt is None and md.xmp.get("exif:GPSAltitude"):
        alt = _frac(md.xmp["exif:GPSAltitude"])
    if isinstance(alt, (int, float)) and alt == alt:
        ref = t.get("GPSAltitudeRef", md.xmp.get("exif:GPSAltitudeRef"))
        alt = -alt if _first(ref) in (1, "1") else alt
    else:
        alt = None
    bearing = t.get("GPSImgDirection")
    if bearing is None and md.xmp.get("exif:GPSImgDirection"):
        bearing = _frac(md.xmp["exif:GPSImgDirection"])
    bref = _s(t.get("GPSImgDirectionRef") or md.xmp.get("exif:GPSImgDirectionRef") or "") or None
    return {"lat": lat, "lon": lon, "alt": alt,
            "bearing": bearing if isinstance(bearing, (int, float)) and bearing == bearing else None,
            "bearing_ref": bref, "utc": gps_utc(md), "source": src if lat is not None else None}


def _frac(s):
    try:
        a, _, b = str(s).partition("/")
        return float(a) / float(b) if b else float(a)
    except (ValueError, ZeroDivisionError):
        return None


def gps_utc(md):
    t = md.tags
    ds, ts = t.get("GPSDateStamp"), t.get("GPSTimeStamp")
    if ds and isinstance(ts, (list, tuple)) and len(ts) == 3:
        try:
            d = datetime.strptime(_s(ds), "%Y:%m:%d")
            return (d + timedelta(hours=ts[0], minutes=ts[1], seconds=ts[2])).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
    x = md.xmp.get("exif:GPSTimeStamp")
    return parse_datetime(x) if x else None


def parse_offset(s):
    """'+05:30' / '-03:00' / 'Z' -> timezone or None."""
    if not s:
        return None
    s = _s(str(s))
    if s in ("Z", "+00:00", "-00:00"):
        return timezone.utc
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", s)
    if not m:
        return None
    mins = int(m[2]) * 60 + int(m[3])
    if mins > 14 * 60:
        return None
    return timezone(timedelta(minutes=mins if m[1] == "+" else -mins))


def parse_datetime(s):
    """EXIF 'YYYY:MM:DD HH:MM:SS' or ISO 8601 (XMP, optional offset) -> datetime (aware if offset given)."""
    if not s:
        return None
    s = _s(str(s))
    if "T" in s or s[4:5] == "-":
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def time_info(md):
    """-> dict original (naive local), offset (str), utc (aware|None), digitized, modified, gps_utc, software."""
    orig_s = md.get("DateTimeOriginal")
    orig = parse_datetime(orig_s)
    off_s = _s(md.tags.get("OffsetTimeOriginal") or md.tags.get("OffsetTime") or "") or None
    if orig is not None and orig.tzinfo is not None:  # XMP ISO with embedded offset
        tz = orig.tzinfo
        off_s = off_s or orig.strftime("%z")
        orig = orig.replace(tzinfo=None)
    else:
        tz = parse_offset(off_s)
    utc = (orig.replace(tzinfo=tz).astimezone(timezone.utc) if orig and tz else None)
    mod = parse_datetime(md.get("DateTime", "ModifyDate"))
    return {"original": orig, "offset": off_s, "utc": utc, "digitized": parse_datetime(md.get("DateTimeDigitized")),
            "modified": mod.replace(tzinfo=None) if mod else None, "gps_utc": gps_utc(md),
            "software": _s(md.get("Software", "CreatorTool"))}
