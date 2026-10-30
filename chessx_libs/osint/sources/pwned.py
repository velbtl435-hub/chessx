"""Pwned Passwords k-anonymity check (Have I Been Pwned range API, free, no key).

Only the first 5 hex chars of the SHA-1 are sent. The password and its full hash are never sent,
logged, cached under a revealing key, or returned. Not an entity source on purpose (passwords are not targets).
Breached-account (e-mail) lookups need a paid HIBP key and are intentionally not implemented.
"""
import hashlib

API = "https://api.pwnedpasswords.com/range/"
LICENSE = "Have I Been Pwned Pwned Passwords API (CC BY 4.0, free, no key)"


class _Src:  # rate/ttl holder for Client.get
    name, host, rate, ttl = "pwned", "api.pwnedpasswords.com", (5, 1.0), 86400


def split_hash(password: str):
    h = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    return h[:5], h[5:]


def parse_range(text: str, suffix: str) -> int:
    for line in text.splitlines():
        s, _, n = line.strip().partition(":")
        if s.upper() == suffix:
            try:
                return int(n)
            except ValueError:
                return 0
    return 0


def password_count(password: str, client) -> int:
    """How many times this password appears in known breaches (0 = not found). Uses Add-Padding."""
    prefix, suffix = split_hash(password)
    text = client.get_text(API + prefix, source=_Src, headers={"Add-Padding": "true"},
                           audit_url=API + "<5-char-prefix>")
    return parse_range(text, suffix)
