import os, tempfile, unittest
from datetime import datetime, timezone
from chessx_libs.geoforensics import read_metadata, gps_info, time_info
from chessx_libs.geoforensics.exif import parse_tiff, xmp_coord, parse_offset
from chessx_libs.geoforensics.synth import build_tiff, build_jpeg, gps_ifd, xmp_packet

IFD0 = {0x010F: (2, "TestCam"), 0x0110: (2, "Model X"), 0x0132: (2, "2024:03:10 14:00:00")}
EXIF = {0x9003: (2, "2024:03:10 13:59:58"), 0x9011: (2, "-03:00"), 0xA434: (2, "50mm f/1.8")}


class TestTiff(unittest.TestCase):
    def check(self, endian):
        t = build_tiff(IFD0, EXIF, gps_ifd(-23.5505, -46.6333, alt=760.5, bearing=123.25,
                                           date="2024:03:10", time=(16, 59, 58)), endian=endian)
        md = read_metadata(t)
        self.assertEqual(md.source, "tiff")
        self.assertEqual(md.errors, [])
        g = gps_info(md)
        self.assertAlmostEqual(g["lat"], -23.5505, 4)
        self.assertAlmostEqual(g["lon"], -46.6333, 4)
        self.assertAlmostEqual(g["alt"], 760.5, 3)
        self.assertAlmostEqual(g["bearing"], 123.25, 3)
        self.assertEqual(g["bearing_ref"], "T")
        ti = time_info(md)
        self.assertEqual(ti["utc"], datetime(2024, 3, 10, 16, 59, 58, tzinfo=timezone.utc))
        self.assertEqual(ti["gps_utc"], ti["utc"])
        self.assertEqual(md.camera()["lens"], "50mm f/1.8")
        self.assertEqual(md.camera()["make"], "TestCam")

    def test_little_endian(self):
        self.check("<")

    def test_big_endian(self):
        self.check(">")

    def test_negative_altitude(self):
        md = read_metadata(build_tiff(IFD0, None, gps_ifd(10, 20, alt=-5)))
        self.assertAlmostEqual(gps_info(md)["alt"], -5)


class TestJpegXmp(unittest.TestCase):
    def test_jpeg_exif_file(self):
        j = build_jpeg(build_tiff(IFD0, EXIF, gps_ifd(48.8584, 2.2945)))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "synthetic.jpg")
            with open(p, "wb") as f:
                f.write(j)
            md = read_metadata(p)
        self.assertEqual(md.source, "jpeg")
        self.assertAlmostEqual(md.gps["lat"], 48.8584, 4)
        self.assertEqual(md.tags["Model"], "Model X")

    def test_xmp_only(self):
        x = xmp_packet(exif__GPSLatitude="40,26.767N", exif__GPSLongitude="79,58.933W",
                       exif__DateTimeOriginal="2023-07-01T12:30:00-04:00", tiff__Make="XmpCam",
                       xmp__CreatorTool="Editor 9", exif__GPSImgDirection="2700/10")
        md = read_metadata(build_jpeg(None, x))
        g = gps_info(md)
        self.assertEqual(g["source"], "xmp")
        self.assertAlmostEqual(g["lat"], 40 + 26.767 / 60, 6)
        self.assertAlmostEqual(g["lon"], -(79 + 58.933 / 60), 6)
        self.assertAlmostEqual(g["bearing"], 270.0)
        ti = time_info(md)
        self.assertEqual(ti["utc"], datetime(2023, 7, 1, 16, 30, tzinfo=timezone.utc))
        self.assertEqual(ti["software"], "Editor 9")
        self.assertEqual(md.camera()["make"], "XmpCam")

    def test_xmp_coord_forms(self):
        self.assertAlmostEqual(xmp_coord("10,30,0S"), -10.5)
        self.assertAlmostEqual(xmp_coord("-12.25"), -12.25)
        self.assertIsNone(xmp_coord("garbage"))

    def test_offsets(self):
        self.assertIsNone(parse_offset("+25:00"))
        self.assertEqual(parse_offset("+05:30").utcoffset(None).total_seconds(), 19800)

    def test_pillow_written_exif(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        import io
        ex = Image.Exif()
        ex[0x010F] = "PilCam"
        bio = io.BytesIO()
        Image.new("RGB", (4, 4)).save(bio, "JPEG", exif=ex.tobytes())
        self.assertEqual(read_metadata(bio.getvalue()).tags.get("Make"), "PilCam")


class TestMalformed(unittest.TestCase):
    def test_garbage_never_raises(self):
        good = build_jpeg(build_tiff(IFD0, EXIF, gps_ifd(1, 2)), pixels=False)
        import random
        rnd = random.Random(33)
        for blob in [b"", b"\xff\xd8", b"II*\x00\xff\xff\xff\xff", b"MM\x00*\x00\x00\x00\x08\xff\xff",
                     good[:40], b"\x89PNG\r\n\x1a\n" + b"\x00" * 5]:
            read_metadata(blob)
        for _ in range(300):
            b = bytearray(good)
            for _ in range(rnd.randint(1, 8)):
                b[rnd.randrange(len(b))] = rnd.randrange(256)
            read_metadata(bytes(b)[: rnd.randint(2, len(b))])

    def test_ifd_loop(self):
        import struct
        t = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<HHHII", 1, 0x8769, 4, 1, 8) + b"\x00" * 4
        errs = []
        parse_tiff(t, errs)
        self.assertTrue(any("loop" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
