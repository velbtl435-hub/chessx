"""ChessX crypto & privacy suite. Pure-Python reference primitives (NOT constant-time;
for production use the `cryptography` package -- see README.md)."""
from .kdf import hkdf, hkdf_extract, hkdf_expand, argon2id, ARGON2_BACKEND
from .otp import hotp, totp, verify_totp, new_secret
from .x25519 import x25519, x25519_keypair, x25519_shared
from .ed25519 import ed25519_keypair, ed25519_sign, ed25519_verify
from .chacha import chacha20_poly1305_encrypt, chacha20_poly1305_decrypt
from .aesgcm import aes_gcm_encrypt, aes_gcm_decrypt
from .netsec import ProxyRotator, KillSwitchEngaged, doh_resolve, FingerprintRotator
from .guard import debugger_attached, sandbox_indicators, in_sandbox
