import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import crypto as C


class TestSealedBox(unittest.TestCase):
    def test_roundtrip_and_binding(self):
        sk, pk = C.x25519_keypair()
        b = C.seal_box(pk, b"secret game", b"file:1")
        self.assertEqual(b[:5], b"CXSB\x01")
        self.assertNotEqual(b, C.seal_box(pk, b"secret game", b"file:1"))
        self.assertEqual(C.open_box(sk, b, b"file:1"), b"secret game")
        with self.assertRaises(C.DecryptError):
            C.open_box(sk, b, b"file:2")
        with self.assertRaises(C.DecryptError):
            C.open_box(C.x25519_keypair()[0], b, b"file:1")
        tampered = bytearray(b); tampered[10] ^= 1  # ephemeral key byte
        with self.assertRaises(C.DecryptError):
            C.open_box(sk, bytes(tampered), b"file:1")
        for bad in (b"", b[:40], b"CXSB\x02" + b[5:]):
            with self.assertRaises(C.DecryptError):
                C.open_box(sk, bad, b"file:1")


class TestEnvelope(unittest.TestCase):
    def test_roundtrip_rewrap(self):
        k1, k2 = C.new_key(), C.new_key()
        data = os.urandom(1000)
        e = C.envelope_encrypt(k1, data, b"db:games")
        self.assertEqual(C.envelope_decrypt(k1, e, b"db:games"), data)
        with self.assertRaises(C.DecryptError):
            C.envelope_decrypt(k2, e, b"db:games")
        with self.assertRaises(C.DecryptError):
            C.envelope_decrypt(k1, e, b"db:other")
        e2 = C.rewrap_envelope(k1, k2, e, b"db:games")
        self.assertEqual(e2[-len(e) + 100:], e[-len(e) + 100:])  # body untouched
        self.assertEqual(C.envelope_decrypt(k2, e2, b"db:games"), data)
        with self.assertRaises(C.DecryptError):
            C.envelope_decrypt(k1, e2, b"db:games")
        for bad in (b"", e[:10], b"CXEV\x01\xff\xff" + e[7:]):
            with self.assertRaises(C.DecryptError):
                C.envelope_decrypt(k1, bad, b"db:games")


if __name__ == "__main__":
    unittest.main()
