import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import bases as B

RFC = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar"]
B64 = ["", "Zg==", "Zm8=", "Zm9v", "Zm9vYg==", "Zm9vYmE=", "Zm9vYmFy"]
B32 = ["", "MY======", "MZXQ====", "MZXW6===", "MZXW6YQ=", "MZXW6YTB", "MZXW6YTBOI======"]
B32H = ["", "CO======", "CPNG====", "CPNMU===", "CPNMUOG=", "CPNMUOJ1", "CPNMUOJ1E8======"]


class TestConvertUnchanged(unittest.TestCase):
    def test_convert(self):
        self.assertEqual(B.to_base(255, "hex", prefix=True), "0xff")
        self.assertEqual(B.to_base(-8, "oct", prefix=True), "-0o10")
        self.assertEqual(B.to_base(5, 2, group=4), "0101")
        self.assertEqual(B.from_base("0o17", "octal"), 15)
        self.assertEqual(B.convert("ff", 16, 2), "11111111")
        self.assertEqual(B.convert_all("0x10"), {"bin": "10000", "oct": "20", "dec": "16", "hex": "10"})
        self.assertEqual(B.hex_to_bytes(B.hexdump(b"hello")), b"hello")


class TestRFC4648(unittest.TestCase):
    def test_vectors(self):
        for raw, b64, b32, b32h in zip(RFC, B64, B32, B32H):
            self.assertEqual(B.encode(raw, "base64"), b64)
            self.assertEqual(B.encode(raw, "base32"), b32)
            self.assertEqual(B.encode(raw, "base32hex"), b32h)
            self.assertEqual(B.decode(b64, "base64"), raw)
            self.assertEqual(B.decode(b32, "base32"), raw)
            self.assertEqual(B.decode(b32h, "base32hex"), raw)

    def test_tolerant_decode(self):
        self.assertEqual(B.decode("mzxw6ytboi", "base32"), b"foobar")
        self.assertEqual(B.decode("Zm9vYg", "base64"), b"foob")
        self.assertEqual(B.decode("Zm9v\nYmFy", "base64"), b"foobar")
        self.assertEqual(B.encode(b"\xfb\xff", "base64url"), "-_8=")
        self.assertEqual(B.decode("-_8", "base64url"), b"\xfb\xff")
        with self.assertRaises(ValueError):
            B.decode("Zm9v!", "base64")


class TestBase58(unittest.TestCase):
    def test_vectors(self):
        self.assertEqual(B.b58encode(b"Hello World!"), "2NEpo7TZRRrLZSi2U")
        self.assertEqual(B.b58encode(b""), "")
        self.assertEqual(B.b58encode(b"\0\0\x01"), "112")
        self.assertEqual(B.b58decode("112"), b"\0\0\x01")
        self.assertEqual(B.b58encode(b"\0"), "1")
        self.assertEqual(B.int_to_base58(0), "1")
        self.assertEqual(B.base58_to_int(B.int_to_base58(123456789)), 123456789)
        with self.assertRaises(ValueError):
            B.b58decode("0OIl")

    def test_base58check_address(self):
        payload = bytes.fromhex("00" + "62e907b15cbf27d5425399ebf6f0fb50ebb88f18")  # genesis coinbase
        addr = B.b58check_encode(payload)
        self.assertEqual(addr, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        self.assertEqual(B.b58check_decode(addr), payload)
        bad = addr[:-1] + ("b" if addr[-1] != "b" else "c")
        with self.assertRaises(ValueError):
            B.b58check_decode(bad)


class TestOctalAndMisc(unittest.TestCase):
    def test_oct_bytes(self):
        self.assertEqual(B.bytes_to_oct(b"Hi"), "110 151")
        self.assertEqual(B.oct_to_bytes("0o110,0o151"), b"Hi")
        self.assertEqual(B.oct_to_bytes("\\110\\151"), b"Hi")
        with self.assertRaises(ValueError):
            B.oct_to_bytes("400")

    def test_roundtrip_random(self):
        for n in (0, 1, 2, 5, 31, 64, 257):
            for _ in range(5):
                d = os.urandom(n)
                if n and _ == 0:
                    d = b"\0\0" + d
                for f in B.FORMATS:
                    self.assertEqual(B.decode(B.encode(d, f), f), d, f)

    def test_encode_all_detect_transcode(self):
        allf = B.encode_all("hi")
        self.assertEqual(set(allf), set(B.FORMATS))
        self.assertEqual(allf["hex"], "6869")
        self.assertIn("base58check", B.detect(B.b58check_encode(b"x")))
        self.assertEqual(B.transcode("Zm9vYmFy", "base64", "base32"), "MZXW6YTBOI======")
        with self.assertRaises(ValueError):
            B.encode(b"x", "nope")


if __name__ == "__main__":
    unittest.main()
