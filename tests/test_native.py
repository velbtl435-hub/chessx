import os, sys, unittest, zlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import native
from chessx_libs.native import hello_fusion as hf

PAIRS = [[(1, 10), (2, 5), (1, 3), (3, 7)], [(5, 1), (4, 1), (3, 1)], [], [(9, -4), (9, 4), (8, 0)],
         [(1, 2 ** 63 - 1), (1, 1)]]
DATA = [b"", b"a", b"123456789", b"ChessX", bytes(range(256))]


class TestPythonFallback(unittest.TestCase):
    def test_crc_matches_zlib(self):
        for d in DATA:
            self.assertEqual(hf.crc32_py(d), zlib.crc32(d))

    def test_fuse(self):
        self.assertEqual(hf.fuse_py(PAIRS[0]), [(1, 13), (3, 7), (2, 5)])
        self.assertEqual(hf.fuse_py(PAIRS[4]), [(1, -2 ** 63)])  # int64 wrap like C

    def test_disabled_env_falls_back(self):
        os.environ["CHESSX_NATIVE"] = "0"
        try:
            self.assertIsNone(native.load("hello_fusion"))
            self.assertEqual(hf.backend(), "python")
            self.assertEqual(hf.crc32("123456789"), 0xCBF43926)
        finally:
            del os.environ["CHESSX_NATIVE"]

    def test_missing_module_is_none(self):
        self.assertIsNone(native.load("no_such_module"))


@unittest.skipUnless(native.find("hello_fusion"), "libcx_hello_fusion not built (make -C c native)")
class TestNativeParity(unittest.TestCase):
    def test_backend(self):
        if os.environ.get("CHESSX_NATIVE") == "0" or native.load("hello_fusion") is None:
            self.skipTest("native disabled (CHESSX_NATIVE=0) or lib not loadable")
        self.assertEqual(hf.backend(), "native")

    def test_crc(self):
        for d in DATA:
            self.assertEqual(hf.crc32(d), hf.crc32_py(d))

    def test_fuse(self):
        for p in PAIRS:
            self.assertEqual(hf.fuse(p), hf.fuse_py(p))


if __name__ == "__main__":
    unittest.main()
