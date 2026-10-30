/* cx_disasm: thin ChessX shim over vendored capstone 5.0.7 (c/capstone/vendor).
 * arch/mode use capstone's own numeric CS_ARCH_* / CS_MODE_* values (same as the Python binding). */
#ifndef CX_CAPSTONE_H
#define CX_CAPSTONE_H
#include "chessx.h"

/* 1 if built with the vendored engine (module.mk), 0 for the stub build. */
CX_API(cx_cs_available) int32_t cx_cs_available(void);
/* bitmask of supported archs: bit n set <=> CS_ARCH n compiled in. */
CX_API(cx_cs_archs) int32_t cx_cs_archs(void);
/* Disassemble `len` bytes at virtual address `addr` (max_insns<=0: all).
 * Writes one line per instruction into caller-owned `out` (NUL-terminated):
 *   "<addr hex>\t<size>\t<mnemonic>\t<op_str>\n"
 * Returns the instruction count, or <0: -1 unavailable, -2 bad arch/mode, -3 out too small. */
CX_API(cx_disasm) int32_t cx_disasm(int32_t arch, int32_t mode, const uint8_t *code, size_t len,
                                    uint64_t addr, int32_t max_insns, char *out, size_t out_cap);
#endif
