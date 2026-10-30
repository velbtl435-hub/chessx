# chessx_libs.reversing
Origin: written from scratch for ChessX (2026). License: MIT (same as repo).
Modules: strings (strings/URL/email/IP/quoted extraction; regexes built by concatenation with chr()),
detector (magic bytes + entropy), origin (compiler/packer hints), disasm (Python via stdlib `dis`;
small x86-64 decoder), baseconv, detective (re-exported for compat; see chessx_libs.detective/bases).
Adapted: magic-byte table from public file-format specs; Unix `strings` behavior.
Optional dep: `capstone` for full x86-64 disassembly. Use only on own code or authorized targets.
