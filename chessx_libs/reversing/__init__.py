"""Reverse-engineering helpers. Authorized targets only (own code or with permission)."""
from .strings import (extract_strings, extract_quoted, extract_urls, extract_emails, extract_ips,
                      indicators, strings_from_file, strings_with_offsets, QUOTED_RE, URL_RE, EMAIL_RE)
from .detector import detect, detect_file, entropy
from .origin import origin_hints
from .disasm import disasm_python, disasm_pyc, disasm_x86, analyze_binary, PycError, check_pyc_header
from .baseconv import convert, to_base, hexdump, bindump
from .detective import file_info, investigate, optional_backends
from .formats import parse_headers, parse_elf, parse_pe, parse_macho
from .angr_helper import cfg_summary, reachable, HAVE_ANGR
__all__ = [n for n in dir() if not n.startswith("_")]
from .provenance import provenance, hashes, fingerprint, section_entropy, embedded_resources, pe_version_info
from .formats import parse_pe_imports, imphash
__all__ = [n for n in dir() if not n.startswith("_")]
from .reversal import reversal_summary, build_settings, toolchain_recovery, capability_story, cfg_highlights
__all__ = [n for n in dir() if not n.startswith("_")]
