# c/capstone — capstone 5.0.7 → native + wasm32-wasip1 (PRIORITY #23)
Owner: Reversing Engineer (Team 1). **Static disassembly only:** bytes in, text out; nothing is executed.

- `vendor/`: capstone **5.0.7** (tag `5.0.7`, commit `d2e5739c`, same version as pip `capstone==5.0.7`),
  trimmed to the core + `arch/{X86,ARM,AArch64,Mips,RISCV}` (other archs keep only their `*Module.h`,
  which `cs.c` includes). Licenses: `vendor/LICENSE.TXT` (BSD-3), `vendor/LICENSE_LLVM.TXT`. Unmodified.
- `capstone.h` + `src/cx_capstone.c`: `cx_disasm` shim (`CX_API`, simple types only, caller-owned output
  buffer; JS hosts use `cx_alloc`/`cx_free`). Exports: `cx_cs_available`, `cx_cs_archs`, `cx_disasm`.
  Output: one `"<addr hex>\t<size>\t<mnemonic>\t<op_str>\n"` per instruction; returns count or
  -1 unavailable / -2 bad arch|mode / -3 buffer too small. arch/mode = capstone's numeric `CS_ARCH_*`/`CS_MODE_*`.
- `cli.c`: `capstone_cli <arch> <mode> <addr-hex> <code-hex>` (parity tests).
- `module.mk`: vendor sources + flags (no `-Werror` for third-party code, `CAPSTONE_HAS_*`).
  **Needs `-include */module.mk` in c/Makefile** (Coder). Without it the Makefile builds a *stub*
  (`cx_cs_available()==0`) and Python falls back to pip capstone / built-in decoder. Today:
  `make -C c -f Makefile -f capstone/module.mk all test`.
- `vectors.txt`: parity vectors; `tests/run_parity.py` compares pip capstone (reference) = ctypes =
  native CLI = wasmtime = wasmer.

## Size / arch set
Even restricted to x86, ARM, ARM64, MIPS and RISC-V the build is ~4.5 MB `.wasm` (-O2; -Oz only saves
~25 KB), ~600 KB gzip: it is decoder tables. `CAPSTONE_X86_REDUCE` would shrink x86 but drops
AVX/AVX-512 etc. and breaks parity with pip capstone, so it is not used.

Python: `chessx_libs/native/capstone.py` (`disasm()`, `backend()`); `reversing.disasm.disasm_x86` uses
it only when pip capstone is missing (same output format, public API unchanged).
