import os, sys, unittest, importlib
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import crypto
A = importlib.import_module("chessx_libs.crypto.aead")


class TestAEAD(unittest.TestCase):
    def test_backend_and_compat_exports(self):
        self.assertIn(crypto.CRYPTO_BACKEND, ("cryptography", "pure"))
        k, n = bytes(32), bytes(12)
        self.assertEqual(crypto.chacha20_poly1305_decrypt(k, n, crypto.chacha20_poly1305_encrypt(k, n, b"x")), b"x")
        self.assertEqual(crypto.aes_gcm_decrypt(k, n, crypto.aes_gcm_encrypt(k, n, b"x", b"a"), b"a"), b"x")

    def test_pure_and_backend_agree(self):
        k, n, pt, aad = os.urandom(32), os.urandom(12), os.urandom(50), b"ctx"
        with mock.patch.object(A, "_CC", None), mock.patch.object(A, "_AESGCM", None):
            p1, p2 = A.chacha20_poly1305_encrypt(k, n, pt, aad), A.aes_gcm_encrypt(k, n, pt, aad)
        self.assertEqual(p1, A.chacha20_poly1305_encrypt(k, n, pt, aad))
        self.assertEqual(p2, A.aes_gcm_encrypt(k, n, pt, aad))

    def test_seal_open(self):
        k = A.new_key()
        for alg in ("chacha20-poly1305", "aes-256-gcm"):
            b1, b2 = A.seal(k, b"hello", b"user:1", alg), A.seal(k, b"hello", b"user:1", alg)
            self.assertNotEqual(b1, b2)  # fresh nonce
            self.assertEqual(b1[:3], b"CX\x01")
            self.assertEqual(A.open_sealed(k, b1, b"user:1"), b"hello")
            for bad_aad in (b"", b"user:2"):
                with self.assertRaises(A.DecryptError):
                    A.open_sealed(k, b1, bad_aad)
            with self.assertRaises(A.DecryptError):
                A.open_sealed(A.new_key(), b1, b"user:1")
        self.assertEqual(A.open_sealed(k, A.seal(k, b""), b""), b"")

    def test_malformed(self):
        k = A.new_key()
        b = A.seal(k, b"x")
        for bad in (b"", b[:A.MIN_BLOB - 1], b"XX" + b[2:], b[:2] + b"\x09" + b[3:], b[:3] + b"\x07" + b[4:],
                    b[:3] + b"\x02" + b[4:]):  # alg swap must fail auth
            with self.assertRaises(A.DecryptError):
                A.open_sealed(k, bad)
        with self.assertRaises(ValueError):
            A.seal(b"short", b"x")


if __name__ == "__main__":
    unittest.main()


class TestAsymBackend(unittest.TestCase):
    def test_matches_pure(self):
        S = importlib.import_module("chessx_libs.crypto.asym")
        px = importlib.import_module("chessx_libs.crypto.x25519")
        pe = importlib.import_module("chessx_libs.crypto.ed25519")
        a, A_ = S.x25519_keypair(); b, B_ = S.x25519_keypair()
        self.assertEqual(A_, px.x25519(a, px.BASE))
        self.assertEqual(S.x25519_shared(a, B_), px.x25519_shared(b, A_))
        sk, pk = S.ed25519_keypair()
        self.assertEqual(pk, pe.public_key(sk))
        sig = S.ed25519_sign(sk, b"m")
        self.assertEqual(sig, pe.ed25519_sign(sk, b"m"))
        self.assertTrue(S.ed25519_verify(pk, b"m", sig))
        self.assertFalse(S.ed25519_verify(pk, b"n", sig))
        self.assertFalse(S.ed25519_verify(pk, b"m", sig[:63]))
        with self.assertRaises(ValueError):
            S.x25519_shared(a, bytes(32))
        with mock.patch.object(S, "HAVE_CRYPTOGRAPHY", False):
            self.assertTrue(S.ed25519_verify(pk, b"m", S.ed25519_sign(sk, b"m")))
            self.assertEqual(S.x25519_shared(a, B_), px.x25519_shared(a, B_))
