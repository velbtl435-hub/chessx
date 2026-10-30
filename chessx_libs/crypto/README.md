# chessx_libs.crypto
Pure-Python, stdlib-only reference implementations, verified against RFC/NIST test vectors
(RFC 7748 X25519, RFC 8032 Ed25519, RFC 8439 ChaCha20-Poly1305, NIST GCM, RFC 5869 HKDF, RFC 4226/6238 HOTP/TOTP).
They are NOT constant-time and are slow: for production swap to `cryptography` (pip install cryptography).

Optional deps:
- `argon2-cffi` -> real Argon2id. Without it, `argon2id()` is a STUB that falls back to `hashlib.scrypt`
  (check `ARGON2_BACKEND`; outputs differ from Argon2id).
- netsec: DoH/proxies need network; kill switch never falls back to a direct connection.
- guard: anti-debug / sandbox detection are heuristics, best-effort.
