# chessx_libs.crypto
Pure-Python, stdlib-only reference implementations, verified against RFC/NIST test vectors
(RFC 7748 X25519, RFC 8032 Ed25519, RFC 8439 ChaCha20-Poly1305, NIST GCM, RFC 5869 HKDF, RFC 4226/6238 HOTP/TOTP).
They are NOT constant-time and are slow: for production swap to `cryptography` (pip install cryptography).

Optional deps:
- `argon2-cffi` -> real Argon2id. Without it, `argon2id()` is a STUB that falls back to `hashlib.scrypt`
  (check `ARGON2_BACKEND`; outputs differ from Argon2id).
- netsec: DoH/proxies need network; kill switch never falls back to a direct connection.
- guard: anti-debug / sandbox detection are heuristics, best-effort.

## 2FA (otp.py)
`hotp`/`totp` (SHA1/256/512, `algo` as hashlib fn or "SHA256"), `verify_totp` (stateless, validates format, passes digits/algo),
`TOTPVerifier(store)` (replay protection via last accepted time step per account + lockout after N failures -> `LockedOut`),
`provisioning_uri` (otpauth://totp/Issuer:account?...), `provisioning_qr` (needs optional `qrcode`),
`generate_backup_codes` -> (plain to show once, salted PBKDF2 hashes to store), `use_backup_code` (constant-time, single-use).
