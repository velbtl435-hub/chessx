import hashlib, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.crypto import otp

K1 = b"12345678901234567890"
K256 = b"12345678901234567890123456789012"
K512 = b"1234567890123456789012345678901234567890123456789012345678901234"
RFC6238 = [  # t, sha1, sha256, sha512
    (59, "94287082", "46119246", "90693936"),
    (1111111109, "07081804", "68084774", "25091201"),
    (1111111111, "14050471", "67062674", "99943326"),
    (1234567890, "89005924", "91819424", "93441116"),
    (2000000000, "69279037", "90698825", "38618901"),
    (20000000000, "65353130", "77737706", "47863826"),
]


class TestOTPVectors(unittest.TestCase):
    def test_hotp_rfc4226(self):
        exp = ["755224", "287082", "359152", "969429", "338314",
               "254676", "287922", "162583", "399871", "520489"]
        self.assertEqual([otp.hotp(K1, i) for i in range(10)], exp)

    def test_totp_rfc6238(self):
        for t, a, b, c in RFC6238:
            self.assertEqual(otp.totp(K1, t, digits=8), a)
            self.assertEqual(otp.totp(K256, t, digits=8, algo=hashlib.sha256), b)
            self.assertEqual(otp.totp(K512, t, digits=8, algo="SHA512"), c)

    def test_verify_passes_digits_algo_and_format(self):
        self.assertTrue(otp.verify_totp(K512, "90693936", t=59, digits=8, algo=hashlib.sha512))
        self.assertFalse(otp.verify_totp(K512, "90693936", t=59, digits=8))
        self.assertTrue(otp.verify_totp(K1, otp.totp(K1, 1000), t=1030))
        self.assertFalse(otp.verify_totp(K1, otp.totp(K1, 1000), t=1100))
        for bad in ("12345", "1234567", "12a456", "", None, "١٢٣٤٥٦"):
            self.assertFalse(otp.verify_totp(K1, bad, t=59))


class TestVerifier(unittest.TestCase):
    def test_replay_rejected(self):
        v = otp.TOTPVerifier()
        c = otp.totp(K1, 1000)
        self.assertTrue(v.verify("u", K1, c, t=1000))
        self.assertFalse(v.verify("u", K1, c, t=1001))
        self.assertFalse(v.verify("u", K1, otp.totp(K1, 970), t=1001))  # older step
        self.assertTrue(v.verify("u", K1, otp.totp(K1, 1030), t=1030))

    def test_lockout(self):
        store = {}
        v = otp.TOTPVerifier(store, max_failures=3, lockout_seconds=60)
        for _ in range(3):
            self.assertFalse(v.verify("u", K1, "000000", t=1000))
        with self.assertRaises(otp.LockedOut):
            v.verify("u", K1, otp.totp(K1, 1000), t=1010)
        self.assertTrue(v.verify("u", K1, otp.totp(K1, 1100), t=1100))
        self.assertIn("u", store)


class TestProvisioningAndBackup(unittest.TestCase):
    def test_uri(self):
        u = otp.provisioning_uri("JBSWY3DPEHPK3PXP", "alice@example.com", "ChessX Co")
        self.assertTrue(u.startswith("otpauth://totp/ChessX%20Co:alice@example.com?"))
        for p in ("secret=JBSWY3DPEHPK3PXP", "issuer=ChessX%20Co", "algorithm=SHA1", "digits=6", "period=30"):
            self.assertIn(p, u)
        with self.assertRaises(ValueError):
            otp.provisioning_uri("AA", "a", "bad:issuer")

    def test_qr_optional(self):
        try:
            import qrcode  # noqa
        except ImportError:
            with self.assertRaises(RuntimeError):
                otp.provisioning_qr("otpauth://totp/x?secret=AA")

    def test_backup_codes(self):
        plain, hashes = otp.generate_backup_codes(5)
        self.assertEqual(len(set(plain)), 5)
        self.assertFalse(any(p in h for p in plain for h in hashes))
        self.assertTrue(otp.use_backup_code(hashes, plain[2].upper().replace("-", " ")))
        self.assertEqual(len(hashes), 4)
        self.assertFalse(otp.use_backup_code(hashes, plain[2]))
        self.assertFalse(otp.use_backup_code(hashes, "nope-nope"))


if __name__ == "__main__":
    unittest.main()
