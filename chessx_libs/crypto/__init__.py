"""ChessX crypto & privacy suite. Pure-Python reference primitives (NOT constant-time;
for production use the `cryptography` package -- see README.md)."""
from .kdf import hkdf, hkdf_extract, hkdf_expand, argon2id, ARGON2_BACKEND, Argon2Unavailable
from .passwords import hash_password, verify_password, check_needs_rehash
from .otp import (hotp, totp, verify_totp, match_totp, new_secret, provisioning_uri, provisioning_qr,
                  TOTPVerifier, LockedOut, generate_backup_codes, use_backup_code)
from .x25519 import x25519, x25519_keypair, x25519_shared
from .ed25519 import ed25519_keypair, ed25519_sign, ed25519_verify
from .chacha import chacha20_poly1305_encrypt, chacha20_poly1305_decrypt
from .aesgcm import aes_gcm_encrypt, aes_gcm_decrypt
from .netsec import ProxyRotator, KillSwitchEngaged, doh_resolve, FingerprintRotator
from .guard import debugger_attached, sandbox_indicators, in_sandbox
