"""Synthetic test-image builders (hand-built TIFF/Exif bytes; no real photos). Used by tests."""
import struct
from fractions import Fraction


def _rat(x, den=10000):
    f = Fraction(x).limit_denominator(den)
    return (f.numerator, f.denominator)


def build_tiff(ifd0=None, exif=None, gps=None, endian="<"):
    """Build TIFF bytes. Each dict maps tag -> (type, value). Types: 2 ASCII str, 3 SHORT, 4 LONG,
    5 RATIONAL (float or list of floats), 1 BYTE (list), 7 UNDEFINED (bytes)."""
    ifd0, exif, gps = dict(ifd0 or {}), dict(exif or {}), dict(gps or {})
    e = endian
    buf = bytearray((b"II" if e == "<" else b"MM") + struct.pack(e + "HI", 42, 8))

    def size(entries):
        extra = 0
        for t, (typ, v) in entries.items():
            b = _encode(e, typ, v)
            if len(b) > 4:
                extra += len(b) + (len(b) & 1)
        return 2 + 12 * len(entries) + 4 + extra

    if exif:
        ifd0[0x8769] = (4, 0)
    if gps:
        ifd0[0x8825] = (4, 0)
    off0 = 8
    off_exif = off0 + size(ifd0)
    off_gps = off_exif + (size(exif) if exif else 0)
    if exif:
        ifd0[0x8769] = (4, off_exif)
    if gps:
        ifd0[0x8825] = (4, off_gps)
    for entries, off in ((ifd0, off0), (exif, off_exif), (gps, off_gps)):
        if entries or off == off0:
            if len(buf) != off:  # A5: real check, survives python -O
                raise RuntimeError(f"TIFF layout mismatch: buffer at {len(buf)}, expected IFD at {off}")
            buf += _ifd(e, entries, off)
    return bytes(buf)


def _encode(e, typ, v):
    if typ == 2:
        return v.encode() + b"\x00"
    if typ in (1, 7):
        return bytes(v)
    vs = v if isinstance(v, (list, tuple)) else [v]
    if typ == 3:
        return struct.pack(e + "H" * len(vs), *vs)
    if typ == 4:
        return struct.pack(e + "I" * len(vs), *vs)
    if typ == 5:
        return b"".join(struct.pack(e + "II", *_rat(x)) for x in vs)
    raise ValueError(typ)


def _count(typ, v):
    if typ in (2, 1, 7):
        return len(_encode("<", typ, v))
    return len(v) if isinstance(v, (list, tuple)) else 1


def _ifd(e, entries, off):
    items = sorted(entries.items())
    data_off = off + 2 + 12 * len(items) + 4
    head, tail = bytearray(struct.pack(e + "H", len(items))), bytearray()
    for tag, (typ, v) in items:
        b = _encode(e, typ, v)
        head += struct.pack(e + "HHI", tag, typ, _count(typ, v))
        if len(b) <= 4:
            head += b.ljust(4, b"\x00")
        else:
            head += struct.pack(e + "I", data_off + len(tail))
            tail += b + (b"\x00" if len(b) & 1 else b"")
    head += struct.pack(e + "I", 0)
    return bytes(head + tail)


def dms(deg):
    deg = abs(deg)
    d = int(deg)
    m = int((deg - d) * 60)
    s = round(((deg - d) * 60 - m) * 60, 4)
    return [d, m, s]


def gps_ifd(lat, lon, alt=None, bearing=None, date=None, time=None):
    g = {1: (2, "N" if lat >= 0 else "S"), 2: (5, dms(lat)), 3: (2, "E" if lon >= 0 else "W"), 4: (5, dms(lon))}
    if alt is not None:
        g[5] = (1, [1 if alt < 0 else 0])
        g[6] = (5, abs(alt))
    if bearing is not None:
        g[16] = (2, "T")
        g[17] = (5, bearing)
    if date:
        g[29] = (2, date)
    if time:
        g[7] = (5, list(time))
    return g


def build_jpeg(tiff=None, xmp=None, pixels=True):
    """Minimal JPEG container: SOI, APP1 Exif, APP1 XMP, (tiny real image via Pillow if available), EOI."""
    out = bytearray(b"\xff\xd8")
    if tiff:
        seg = b"Exif\x00\x00" + tiff
        out += b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg
    if xmp:
        seg = b"http://ns.adobe.com/xap/1.0/\x00" + (xmp.encode() if isinstance(xmp, str) else xmp)
        out += b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg
    body = b"\xff\xd9"
    if pixels:
        try:
            import io
            from PIL import Image
            bio = io.BytesIO()
            Image.new("RGB", (8, 8), (120, 160, 200)).save(bio, "JPEG")
            body = bio.getvalue()[2:]  # strip SOI, keep rest incl. EOI
        except ImportError:
            pass
    return bytes(out + body)


def xmp_packet(**attrs):
    a = " ".join(f'{k.replace("__", ":")}="{v}"' for k, v in attrs.items())
    return ('<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
            'xmlns:exif="http://ns.adobe.com/exif/1.0/" xmlns:tiff="http://ns.adobe.com/tiff/1.0/" '
            f'xmlns:xmp="http://ns.adobe.com/xap/1.0/" {a}/></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')
