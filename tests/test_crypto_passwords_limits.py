"""CRY-03: verify_password must reject over-cost parameters from a stored hash BEFORE hashing."""
import os, sys, unittest, importlib
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = importlib.import_module("chessx_libs.crypto.passwords")
kdf = importlib.import_module("chessx_libs.crypto.kdf")
SALT, HASH = "AAAAAAAAAAAAAAAAAAAAAA", "A" * 43


class TestLimits(unittest.TestCase):
    def _no_hash_called(self, phc):
        with mock.patch.object(kdf, "argon2id", side_effect=AssertionError("hashed")), \
             mock.patch.object(P.hashlib, "scrypt", side_effect=AssertionError("hashed")), \
             mock.patch.object(P, "_ph", None):
            self.assertFalse(P.verify_password(phc, "pw"))
        fake = mock.Mock(**{"verify.side_effect": AssertionError("hashed")})  # argon2-cffi path guarded too
        with mock.patch.object(P, "_ph", fake):
            self.assertFalse(P.verify_password(phc, "pw"))
        fake.verify.assert_not_called()

    def test_tampered_argon2(self):
        for prm in ("m=2147483648,t=3,p=4", "m=65536,t=100000,p=4", "m=65536,t=3,p=255", "m=0,t=3,p=4", "m=65536,t=3"):
            self._no_hash_called(f"$argon2id$v=19${prm}${SALT}${HASH}")

    def test_tampered_scrypt(self):
        for prm in ("ln=40,r=8,p=1", "ln=15,r=1024,p=1", "ln=15,r=8,p=64"):
            self._no_hash_called(f"$scrypt${prm}${SALT}${HASH}")

    def test_bad_lengths_and_version(self):
        self._no_hash_called(f"$argon2id$v=19$m=65536,t=3,p=4${'A' * 200}${HASH}")
        self._no_hash_called(f"$argon2id$v=16$m=65536,t=3,p=4${SALT}${HASH}")

    def test_normal_hash_and_override(self):
        try:
            h = P.hash_password("pw")
        except kdf.Argon2Unavailable:
            self.skipTest("no argon2 backend")
        self.assertTrue(P.verify_password(h, "pw"))
        self.assertFalse(P.verify_password(h, "pw", max_params={"argon2id": {"m": 1024}}))


if __name__ == "__main__":
    unittest.main()
