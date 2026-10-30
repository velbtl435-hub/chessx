# chessx_libs.bases
Origin: written for ChessX (2026); extends reversing.baseconv (kept for compat). License: MIT. Stdlib only.
convert/convert_all/to_base/from_base (bases 2..36, names bin/oct/dec/hex, prefixes, negatives, digit grouping);
hexdump (xxd-like), bindump (bin/oct/dec/hex per byte), hex_to_bytes / bin_to_bytes (round-trip), read_file.

## codecs (bytes/text encodings)
`encode(data, fmt)` / `decode(text, fmt)` / `transcode(text, src, dst)` / `encode_all(data)` / `detect(text)`.
Formats: hex, oct, bin (per byte), base32 + base32hex (RFC 4648; case-insensitive, missing padding tolerated),
base58 + base58check (Bitcoin alphabet, leading zero bytes -> '1', double-SHA256 checksum verified on decode),
base64 + base64url (padding-tolerant, strict alphabet), base85 + ascii85. `data` may be bytes or str (UTF-8).
Helpers: `int_to_base58`, `base58_to_int`, `oct_to_bytes`, `bytes_to_oct`. Invalid input raises `ValueError`.
