# chessx_libs.crypto
Pure-Python, stdlib-only reference implementations, verified against RFC/NIST test vectors
(RFC 7748 X25519, RFC 8032 Ed25519, RFC 8439 ChaCha20-Poly1305, NIST GCM, RFC 5869 HKDF, RFC 4226/6238 HOTP/TOTP).
They are NOT constant-time and are slow: for production swap to `cryptography` (pip install cryptography).

Optional deps:
- `argon2-cffi` (or `cryptography`>=44) -> real Argon2id. With neither, `argon2id()` and `hash_password()`
  raise `Argon2Unavailable`; scrypt is used only with an explicit `allow_fallback=True`. Check `ARGON2_BACKEND`.
- netsec: DoH/proxies need network; kill switch never falls back to a direct connection.
- guard: anti-debug / sandbox detection are heuristics, best-effort.

## 2FA (otp.py)
`hotp`/`totp` (SHA1/256/512, `algo` as hashlib fn or "SHA256"), `verify_totp` (stateless, validates format, passes digits/algo),
`TOTPVerifier(store)` (replay protection via last accepted time step per account + lockout after N failures -> `LockedOut`),
`provisioning_uri` (otpauth://totp/Issuer:account?...), `provisioning_qr` (needs optional `qrcode`),
`generate_backup_codes` -> (plain to show once, salted PBKDF2 hashes to store), `use_backup_code` (constant-time, single-use).

## Passwords (passwords.py)
`hash_password(pw)` -> PHC `$argon2id$v=19$m=65536,t=3,p=4$salt$hash` (random 16-byte salt, RFC 9106/OWASP params),
`verify_password(phc, pw)` (constant-time, False on malformed), `check_needs_rehash(phc)`.
Use these for stored passwords; use `kdf.argon2id` only to derive raw keys (e.g. keystore wrapping).

## Backend + high-level AEAD (aead.py)
`CRYPTO_BACKEND` = "cryptography" (used automatically when installed) or "pure". The exported
`x25519_keypair`/`x25519_shared`/`ed25519_*` (asym.py) and
`chacha20_poly1305_*` / `aes_gcm_*` names dispatch to it (same outputs). Prefer the high-level API:
`seal(key, pt, aad=b"", alg="chacha20-poly1305"|"aes-256-gcm")` -> `CX|ver|alg|nonce12|ct|tag16` (random nonce,
header authenticated), `open_sealed(key, blob, aad)` raises `DecryptError`. Rotate a key before ~2^32 messages.

## Stored data (envelope.py)
`seal_box(recipient_pk, data, context)` / `open_box(recipient_sk, blob, context)`: ephemeral X25519 + HKDF-SHA256 + AEAD,
versioned `CXSB` header, `context` bound as AAD (anonymous sender; no sender authentication -- sign separately if needed).
`envelope_encrypt(kek, data, context)` / `envelope_decrypt` / `rewrap_envelope(old, new, blob)` (KEK rotation without
re-encrypting data): random per-object DEK wrapped by the KEK, `CXEV` header.
