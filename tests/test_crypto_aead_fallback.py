"""CRY-01: without `cryptography`, AEAD must fail closed unless allow_fallback=True (and then warn)."""
import os, sys, unittest, importlib, tempfile, warnings
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import crypto
A = importlib.import_module("chessx_libs.crypto.aead")
E_ = importlib.import_module("chessx_libs.crypto.envelope")
S = importlib.import_module("chessx_libs.crypto.session")
K = importlib.import_module("chessx_libs.crypto.keystore")


def no_cryptography():
    return mock.patch.multiple(A, _CC=None, _AESGCM=None, BACKEND="pure")


class TestNoCryptography(unittest.TestCase):
    k, n = bytes(range(32)), bytes(12)

    def test_primitives_raise_by_default(self):
        with no_cryptography():
            for f in (A.chacha20_poly1305_encrypt, A.aes_gcm_encrypt):
                with self.assertRaises(A.AEADUnavailable):
                    f(self.k, self.n, b"x")
            with self.assertRaises(A.AEADUnavailable):
                A.chacha20_poly1305_decrypt(self.k, self.n, bytes(20))
            with self.assertRaises(A.AEADUnavailable):
                A.aes_gcm_decrypt(self.k, self.n, bytes(20))

    def test_unavailable_is_not_a_decrypt_error(self):
        blob = A.seal(self.k, b"hi")
        with no_cryptography():
            with self.assertRaises(A.AEADUnavailable):
                A.seal(self.k, b"hi")
            with self.assertRaises(A.AEADUnavailable):  # must not be masked as "authentication failed"
                A.open_sealed(self.k, blob)
        self.assertFalse(issubclass(A.AEADUnavailable, ValueError))
        self.assertIs(crypto.AEADUnavailable, A.AEADUnavailable)

    def test_opt_in_warns_and_interoperates(self):
        blob = A.seal(self.k, b"hi", b"a")
        with no_cryptography(), warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self.assertEqual(A.open_sealed(self.k, blob, b"a", allow_fallback=True), b"hi")
            b2 = A.seal(self.k, b"yo", alg="aes-256-gcm", allow_fallback=True)
        self.assertTrue(w and all(issubclass(x.category, A.InsecureFallbackWarning) for x in w))
        self.assertTrue(issubclass(A.InsecureFallbackWarning, RuntimeWarning))
        self.assertEqual(A.open_sealed(self.k, b2), b"yo")

    def test_callers_fail_closed_and_opt_in(self):
        kek = os.urandom(32)
        with no_cryptography():
            with self.assertRaises(A.AEADUnavailable):
                E_.envelope_encrypt(kek, b"d")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", A.InsecureFallbackWarning)
                blob = E_.envelope_encrypt(kek, b"d", allow_fallback=True)
                self.assertEqual(E_.envelope_decrypt(kek, blob, allow_fallback=True), b"d")
                s = S.Session(kek, kek, b"sid", allow_fallback=True)
                frame = s.encrypt(b"m")
            with self.assertRaises(A.AEADUnavailable):
                S.Session(kek, kek, b"sid").encrypt(b"m")
        self.assertEqual(S.Session(kek, kek, b"sid").decrypt(frame), b"m")

    def test_keystore_fail_closed(self):
        with tempfile.TemporaryDirectory() as d, no_cryptography():
            try:
                K.Keystore.create(os.path.join(d, "ks.json"), "pw", kdf_params={"m": 8 * 1024, "t": 1, "p": 1})
            except A.AEADUnavailable:
                pass
            except crypto.Argon2Unavailable:
                self.skipTest("no argon2 backend")
            else:
                self.fail("keystore created without a constant-time AEAD")


if __name__ == "__main__":
    unittest.main()
