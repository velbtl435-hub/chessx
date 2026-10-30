"""E2E session: authenticated X25519 handshake (Ed25519 identities, SIGMA-style) + per-direction
ChaCha20-Poly1305 keys with strict nonce counters. See README "E2E session -- threat model".

    A = Handshake(a_sk, a_pk, peer_id_pk=b_pk, initiator=True)
    B = Handshake(b_sk, b_pk, peer_id_pk=a_pk, initiator=False)
    m1 = A.start(); m2 = B.respond(m1); m3, sa = A.finish(m2); sb = B.complete(m3)
    frame = sa.encrypt(b"hi"); sb.decrypt(frame) == b"hi"
"""
import hashlib, struct
from . import aead
from .asym import x25519_keypair, x25519_shared, ed25519_sign, ed25519_verify, ed25519_public
from .kdf import hkdf

PROTO, VERSION = b"chessx/e2e/v1", 1
M1, M2, M3, MSG = b"CXH1", b"CXH2", b"CXH3", b"CXM"


class HandshakeError(ValueError):
    pass


class Session:
    def __init__(self, send_key, recv_key, session_id):
        self._send, self._recv = bytearray(send_key), bytearray(recv_key)
        self.session_id = session_id
        self.send_counter = 0
        self.recv_counter = 0

    def _aad(self, ctr, aad):
        return MSG + bytes([VERSION]) + struct.pack(">Q", ctr) + self.session_id + aad

    def encrypt(self, plaintext: bytes, aad: bytes = b"") -> bytes:
        if self.send_counter >= 2 ** 64 - 1:
            raise OverflowError("nonce counter exhausted; re-handshake")
        c = self.send_counter
        self.send_counter += 1
        nonce = b"\0\0\0\0" + struct.pack(">Q", c)
        return MSG + bytes([VERSION]) + struct.pack(">Q", c) + aead.chacha20_poly1305_encrypt(
            bytes(self._send), nonce, plaintext, self._aad(c, aad))

    def decrypt(self, frame: bytes, aad: bytes = b"") -> bytes:
        """Strict in-order delivery: replayed, dropped-ahead or reordered frames are rejected."""
        if len(frame) < 12 + aead.TAG_LEN or frame[:3] != MSG or frame[3] != VERSION:
            raise aead.DecryptError("malformed frame")
        c = struct.unpack(">Q", frame[4:12])[0]
        if c != self.recv_counter:
            raise aead.DecryptError(f"replayed or out-of-order frame (got {c}, expected {self.recv_counter})")
        try:
            pt = aead.chacha20_poly1305_decrypt(bytes(self._recv), b"\0\0\0\0" + frame[4:12], frame[12:],
                                                self._aad(c, aad))
        except ValueError:
            raise aead.DecryptError("authentication failed") from None
        self.recv_counter += 1
        return pt

    def close(self):
        for b in (self._send, self._recv):
            for i in range(len(b)):
                b[i] = 0


class Handshake:
    def __init__(self, id_sk: bytes, id_pk: bytes, peer_id_pk: bytes, initiator: bool):
        if ed25519_public(id_sk) != id_pk:
            raise ValueError("identity keypair mismatch")
        self.id_sk, self.id_pk, self.peer, self.initiator = id_sk, id_pk, peer_id_pk, initiator
        self.eph_sk, self.eph_pk = x25519_keypair()
        self._state = "new"

    def _transcript(self, ea, eb):
        ia, ib = (self.id_pk, self.peer) if self.initiator else (self.peer, self.id_pk)
        return hashlib.sha256(PROTO + ea + eb + ia + ib).digest()

    def _keys(self, shared, th):
        i2r = hkdf(shared, th, PROTO + b"|i2r", 32)
        r2i = hkdf(shared, th, PROTO + b"|r2i", 32)
        sid = hkdf(shared, th, PROTO + b"|sid", 16)
        return (i2r, r2i, sid) if self.initiator else (r2i, i2r, sid)

    def _expect(self, st):
        if self._state != st:
            raise HandshakeError(f"wrong handshake step (state={self._state})")

    def start(self) -> bytes:
        self._expect("new"); assert self.initiator
        self._state = "sent1"
        return M1 + bytes([VERSION]) + self.eph_pk

    def respond(self, m1: bytes) -> bytes:
        self._expect("new")
        if self.initiator or len(m1) != 37 or m1[:5] != M1 + bytes([VERSION]):
            raise HandshakeError("bad hello")
        self.peer_eph = m1[5:]
        try:
            self._shared = x25519_shared(self.eph_sk, self.peer_eph)
        except ValueError:
            raise HandshakeError("bad ephemeral key") from None
        self._th = self._transcript(self.peer_eph, self.eph_pk)
        self._state = "sent2"
        return M2 + bytes([VERSION]) + self.eph_pk + ed25519_sign(self.id_sk, b"resp" + self._th)

    def finish(self, m2: bytes):
        self._expect("sent1")
        if len(m2) != 5 + 32 + 64 or m2[:5] != M2 + bytes([VERSION]):
            raise HandshakeError("bad response")
        peer_eph, sig = m2[5:37], m2[37:]
        th = self._transcript(self.eph_pk, peer_eph)
        if not ed25519_verify(self.peer, b"resp" + th, sig):
            raise HandshakeError("responder signature invalid (wrong identity or MITM)")
        try:
            shared = x25519_shared(self.eph_sk, peer_eph)
        except ValueError:
            raise HandshakeError("bad ephemeral key") from None
        self._state = "done"
        s, r, sid = self._keys(shared, th)
        return M3 + bytes([VERSION]) + ed25519_sign(self.id_sk, b"init" + th), Session(s, r, sid)

    def complete(self, m3: bytes) -> Session:
        self._expect("sent2")
        if len(m3) != 5 + 64 or m3[:5] != M3 + bytes([VERSION]):
            raise HandshakeError("bad finish")
        if not ed25519_verify(self.peer, b"init" + self._th, m3[5:]):
            raise HandshakeError("initiator signature invalid (wrong identity or MITM)")
        self._state = "done"
        return Session(*self._keys(self._shared, self._th))
