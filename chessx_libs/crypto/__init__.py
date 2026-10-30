"""ChessX crypto & privacy suite. Pure-Python reference primitives; AEAD calls use the
`cryptography` package automatically when installed (CRYPTO_BACKEND) -- see README.md)."""
from .kdf import hkdf, hkdf_extract, hkdf_expand, argon2id, ARGON2_BACKEND, Argon2Unavailable
from .passwords import hash_password, verify_password, check_needs_rehash
from .otp import (hotp, totp, verify_totp, match_totp, new_secret, provisioning_uri, provisioning_qr,
                  TOTPVerifier, LockedOut, generate_backup_codes, use_backup_code)
from .x25519 import x25519
from .asym import (x25519_keypair, x25519_shared, x25519_public, ed25519_keypair, ed25519_sign,
                   ed25519_verify, ed25519_public)
from .aead import (chacha20_poly1305_encrypt, chacha20_poly1305_decrypt, aes_gcm_encrypt, aes_gcm_decrypt,
                   seal, open_sealed, new_key, DecryptError, BACKEND as CRYPTO_BACKEND)
from .envelope import seal_box, open_box, envelope_encrypt, envelope_decrypt, rewrap_envelope
from .session import Handshake, HandshakeError, Session
from .netsec import ProxyRotator, KillSwitchEngaged, doh_resolve, FingerprintRotator
from .guard import debugger_attached, sandbox_indicators, in_sandbox
