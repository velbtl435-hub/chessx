"""Numeral-base suite: bin/oct/dec/hex (and 2..36) conversion, hex reader, binary reader."""
from .convert import to_base, from_base, convert, convert_all, parse_auto, BASE_NAMES
from .readers import hexdump, bindump, hex_to_bytes, bin_to_bytes, read_file
__all__ = ["to_base", "from_base", "convert", "convert_all", "parse_auto", "BASE_NAMES",
           "hexdump", "bindump", "hex_to_bytes", "bin_to_bytes", "read_file"]
