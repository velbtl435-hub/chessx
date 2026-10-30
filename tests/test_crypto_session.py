import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import crypto as C
from chessx_libs.crypto.session import Handshake, HandshakeError


def pair():
    a, b = C.ed25519_keypair(), C.ed25519_keypair()
    A = Handshake(a[0], a[1], b[1], True); B = Handshake(b[0], b[1], a[1], False)
    m3, sa = A.finish(B.respond(A.start()))
    return sa, B.complete(m3)


class TestSession(unittest.TestCase):
    def test_bidirectional(self):
        sa, sb = pair()
        self.assertEqual(sa.session_id, sb.session_id)
        for i in range(3):
            self.assertEqual(sb.decrypt(sa.encrypt(b"move %d" % i, b"g1"), b"g1"), b"move %d" % i)
            self.assertEqual(sa.decrypt(sb.encrypt(b"ack")), b"ack")
        f = sa.encrypt(b"x")
        with self.assertRaises(C.DecryptError):
            sb.decrypt(f, b"wrong aad")
        self.assertEqual(sb.decrypt(f), b"x")  # failed attempt did not advance counter

    def test_replay_and_reorder(self):
        sa, sb = pair()
        f0, f1 = sa.encrypt(b"0"), sa.encrypt(b"1")
        with self.assertRaises(C.DecryptError):
            sb.decrypt(f1)
        sb.decrypt(f0)
        with self.assertRaises(C.DecryptError):
            sb.decrypt(f0)
        sb.decrypt(f1)
        with self.assertRaises(C.DecryptError):
            sa.decrypt(f0)  # reflection: own frames rejected (different direction key)

    def test_mitm_and_wrong_identity(self):
        a, b, m = C.ed25519_keypair(), C.ed25519_keypair(), C.ed25519_keypair()
        A = Handshake(a[0], a[1], b[1], True)
        M = Handshake(m[0], m[1], a[1], False)  # attacker with its own identity
        with self.assertRaises(HandshakeError):
            A.finish(M.respond(A.start()))
        A = Handshake(a[0], a[1], b[1], True); B = Handshake(b[0], b[1], a[1], False)
        m2 = bytearray(B.respond(A.start())); m2[10] ^= 1  # swap ephemeral
        with self.assertRaises(HandshakeError):
            A.finish(bytes(m2))
        A = Handshake(a[0], a[1], b[1], True); B = Handshake(b[0], b[1], m[1], False)  # B expects M
        with self.assertRaises(HandshakeError):
            A.finish(B.respond(A.start()))  # A verifies B's sig over a transcript naming different ids

    def test_state_machine(self):
        a, b = C.ed25519_keypair(), C.ed25519_keypair()
        A = Handshake(a[0], a[1], b[1], True)
        A.start()
        with self.assertRaises(HandshakeError):
            A.start()
        with self.assertRaises(ValueError):
            Handshake(a[0], b[1], a[1], True)
        sa, sb = pair()
        sa.close()
        self.assertEqual(bytes(sa._send), bytes(32))


if __name__ == "__main__":
    unittest.main()
