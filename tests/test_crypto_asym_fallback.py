"""CRY-02: secret-key X25519/Ed25519 ops fail closed without `cryptography` unless allow_fallback=True."""
import os, sys, unittest, importlib, warnings
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import crypto
S = importlib.import_module("chessx_libs.crypto.asym")
A = importlib.import_module("chessx_libs.crypto.aead")
E_ = importlib.import_module("chessx_libs.crypto.envelope")
H = importlib.import_module("chessx_libs.crypto.session")


class TestAsymStrict(unittest.TestCase):
    def test_secret_ops_raise(self):
        sk = os.urandom(32)
        with mock.patch.object(S, "HAVE_CRYPTOGRAPHY", False):
            for call in (lambda: S.x25519_public(sk), lambda: S.x25519_keypair(), lambda: S.x25519_shared(sk, sk),
                         lambda: S.ed25519_public(sk), lambda: S.ed25519_keypair(), lambda: S.ed25519_sign(sk, b"m")):
                with self.assertRaises(S.AsymUnavailable):
                    call()
        self.assertIs(crypto.AsymUnavailable, S.AsymUnavailable)

    def test_verify_public_only_still_works(self):
        sk, pk = S.ed25519_keypair()
        sig = S.ed25519_sign(sk, b"m")
        with mock.patch.object(S, "HAVE_CRYPTOGRAPHY", False):
            self.assertTrue(S.ed25519_verify(pk, b"m", sig))

    def test_opt_in_warns_and_matches(self):
        sk = os.urandom(32)
        ref = S.x25519_public(sk)
        with mock.patch.object(S, "HAVE_CRYPTOGRAPHY", False), self.assertWarns(A.InsecureFallbackWarning):
            self.assertEqual(S.x25519_public(sk, allow_fallback=True), ref)

    def test_callers_propagate(self):
        rsk, rpk = S.x25519_keypair()
        isk, ipk = S.ed25519_keypair()
        with mock.patch.object(S, "HAVE_CRYPTOGRAPHY", False):
            with self.assertRaises(S.AsymUnavailable):
                E_.seal_box(rpk, b"x")
            with self.assertRaises(S.AsymUnavailable):
                H.Handshake(isk, ipk, ipk, True)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", A.InsecureFallbackWarning)
                blob = E_.seal_box(rpk, b"x", allow_fallback=True)
        self.assertEqual(E_.open_box(rsk, blob), b"x")


if __name__ == "__main__":
    unittest.main()
