"""RFC / NIST known-answer tests for the pure-Python primitives (+ cross-check vs cryptography)."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib
X, E, C, G, K = (importlib.import_module("chessx_libs.crypto." + m) for m in ("x25519", "ed25519", "chacha", "aesgcm", "kdf"))

h = bytes.fromhex
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
except ImportError:
    AESGCM = None


class TestX25519(unittest.TestCase):
    def test_rfc7748_5_2(self):
        self.assertEqual(X.x25519(h("a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4"),
                                  h("e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c")),
                         h("c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552"))

    def test_rfc7748_6_1(self):
        a = h("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a")
        b = h("5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb")
        A, B = X.x25519(a, X.BASE), X.x25519(b, X.BASE)
        self.assertEqual(A, h("8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a"))
        self.assertEqual(B, h("de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f"))
        k = h("4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742")
        self.assertEqual(X.x25519_shared(a, B), k)
        self.assertEqual(X.x25519_shared(b, A), k)

    def test_low_order_rejected(self):
        with self.assertRaises(ValueError):
            X.x25519_shared(os.urandom(32), bytes(32))


class TestEd25519(unittest.TestCase):
    V = [("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
          "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
          "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
         ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
          "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
          "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00")]

    def test_rfc8032(self):
        for sk, pk, m, sig in self.V:
            self.assertEqual(E.public_key(h(sk)), h(pk))
            self.assertEqual(E.ed25519_sign(h(sk), h(m)), h(sig))
            self.assertTrue(E.ed25519_verify(h(pk), h(m), h(sig)))
            bad = bytearray(h(sig)); bad[5] ^= 1
            self.assertFalse(E.ed25519_verify(h(pk), h(m), bytes(bad)))
            self.assertFalse(E.ed25519_verify(h(pk), h(m) + b"x", h(sig)))


class TestChaCha(unittest.TestCase):
    def test_rfc8439_2_8_2(self):
        key = bytes(range(0x80, 0xa0))
        nonce, aad = h("070000004041424344454647"), h("50515253c0c1c2c3c4c5c6c7")
        pt = (b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip "
              b"for the future, sunscreen would be it.")
        out = C.chacha20_poly1305_encrypt(key, nonce, pt, aad)
        self.assertEqual(out[:16], h("d31a8d34648e60db7b86afbc53ef7ec2"))
        self.assertEqual(out[-16:], h("1ae10b594f09e26a7e902ecbd0600691"))
        self.assertEqual(C.chacha20_poly1305_decrypt(key, nonce, out, aad), pt)
        with self.assertRaises(ValueError):
            C.chacha20_poly1305_decrypt(key, nonce, out, b"other aad")

    @unittest.skipIf(AESGCM is None, "cryptography not installed")
    def test_cross_cryptography(self):
        for n in (0, 1, 63, 64, 65, 300):
            k, nn, pt, aad = os.urandom(32), os.urandom(12), os.urandom(n), os.urandom(7)
            self.assertEqual(C.chacha20_poly1305_encrypt(k, nn, pt, aad), ChaCha20Poly1305(k).encrypt(nn, pt, aad))


class TestAESGCM(unittest.TestCase):
    def test_nist_cases(self):
        self.assertEqual(G.aes_gcm_encrypt(bytes(16), bytes(12), b""), h("58e2fccefa7e3061367f1d57a4e7455a"))
        self.assertEqual(G.aes_gcm_encrypt(bytes(16), bytes(12), bytes(16)),
                         h("0388dace60b6a392f328c2b971b2fe78ab6e47d42cec13bdf53a67b21257bddf"))
        # NIST test case 4 (AES-128, with AAD)
        key = h("feffe9928665731c6d6a8f9467308308")
        iv = h("cafebabefacedbaddecaf888")
        pt = h("d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a721c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b39")
        aad = h("feedfacedeadbeeffeedfacedeadbeefabaddad2")
        out = G.aes_gcm_encrypt(key, iv, pt, aad)
        self.assertEqual(out[-16:], h("5bc94fbc3221a5db94fae95ae7121a47"))
        self.assertEqual(G.aes_gcm_decrypt(key, iv, out, aad), pt)
        with self.assertRaises(ValueError):
            G.aes_gcm_decrypt(key, iv, out[:-1] + bytes([out[-1] ^ 1]), aad)

    @unittest.skipIf(AESGCM is None, "cryptography not installed")
    def test_cross_cryptography(self):
        for klen in (16, 24, 32):
            k, nn, pt, aad = os.urandom(klen), os.urandom(12), os.urandom(77), os.urandom(5)
            self.assertEqual(G.aes_gcm_encrypt(k, nn, pt, aad), AESGCM(k).encrypt(nn, pt, aad))


class TestHKDF(unittest.TestCase):
    def test_rfc5869_case1(self):
        okm = K.hkdf(b"\x0b" * 22, bytes(range(13)), bytes(range(0xf0, 0xfa)), 42)
        self.assertEqual(okm, h("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"))

    def test_rfc5869_case3_empty_salt_info(self):
        self.assertEqual(K.hkdf(b"\x0b" * 22, b"", b"", 42),
                         h("8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8"))


if __name__ == "__main__":
    unittest.main()
