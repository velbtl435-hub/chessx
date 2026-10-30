import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.crypto import kdf, passwords as P


class TestPasswords(unittest.TestCase):
    def test_hash_verify(self):
        h = P.hash_password("correct horse")
        self.assertTrue(h.startswith("$argon2id$v=19$m=65536,t=3,p=4$"))
        self.assertTrue(P.verify_password(h, "correct horse"))
        self.assertFalse(P.verify_password(h, "wrong"))
        self.assertFalse(P.verify_password("garbage", "x"))
        self.assertNotEqual(h, P.hash_password("correct horse"))  # random salt
        self.assertFalse(P.check_needs_rehash(h))
        with self.assertRaises(ValueError):
            P.hash_password("")

    def test_needs_rehash_weak(self):
        weak = P.hash_password("pw").replace("m=65536,t=3", "m=65536,t=3")
        import argon2
        weak = argon2.PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash("pw")
        self.assertTrue(P.verify_password(weak, "pw"))
        self.assertTrue(P.check_needs_rehash(weak))

    def test_cryptography_backend_interop(self):
        with mock.patch.object(P, "_ph", None), mock.patch.object(kdf, "hash_secret_raw", None), \
             mock.patch.object(kdf, "ARGON2_BACKEND", "cryptography"):
            from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
            with mock.patch.object(kdf, "_CryArgon2id", Argon2id, create=True):
                h = P.hash_password("pw")
                self.assertTrue(P.verify_password(h, "pw"))
                self.assertFalse(P.check_needs_rehash(h))
        self.assertTrue(P.verify_password(h, "pw"))  # argon2-cffi verifies cryptography-made PHC

    def test_strict_and_fallback(self):
        with mock.patch.object(P, "_ph", None), mock.patch.object(kdf, "hash_secret_raw", None), \
             mock.patch.object(kdf, "_CryArgon2id", None, create=True), \
             mock.patch.object(kdf, "ARGON2_BACKEND", "none"):
            with self.assertRaises(kdf.Argon2Unavailable):
                P.hash_password("pw")
            with self.assertRaises(kdf.Argon2Unavailable):
                kdf.argon2id(b"pw", b"saltsaltsalt")
            h = P.hash_password("pw", allow_fallback=True)
            self.assertTrue(h.startswith("$scrypt$"))
            self.assertTrue(P.verify_password(h, "pw"))
            self.assertEqual(len(kdf.argon2id(b"pw", b"saltsaltsalt", allow_fallback=True)), 32)
        self.assertTrue(P.check_needs_rehash(h))

    def test_raw_argon2id_vector(self):
        # RFC 9106-style check via both backends agreeing
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
        a = kdf.argon2id(b"password", b"somesalt12345678", 32, 2, 1024, 1)
        b = Argon2id(salt=b"somesalt12345678", length=32, iterations=2, lanes=1, memory_cost=1024).derive(b"password")
        self.assertEqual(a, b)
        with self.assertRaises(ValueError):
            kdf.argon2id(b"pw", b"short")


if __name__ == "__main__":
    unittest.main()
