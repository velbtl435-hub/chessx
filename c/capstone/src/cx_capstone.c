/* ChessX shim over capstone. STATIC disassembly only: bytes in, text out; nothing is executed.
 * Without CX_CAPSTONE_VENDOR (plain Makefile build, no module.mk) this compiles to a stub that
 * reports cx_cs_available()==0 so Python falls back to pip capstone / built-in decoder. */
#include "../capstone.h"

#ifdef CX_CAPSTONE_VENDOR
#include <stdio.h>
#include <string.h>
#include <capstone/capstone.h>

int32_t cx_cs_available(void) { return 1; }

int32_t cx_cs_archs(void) {
    int32_t m = 0;
    for (int a = 0; a < 31; a++) if (cs_support(a)) m |= (int32_t)(1u << a);
    return m;
}

int32_t cx_disasm(int32_t arch, int32_t mode, const uint8_t *code, size_t len,
                  uint64_t addr, int32_t max_insns, char *out, size_t out_cap) {
    csh h;
    if (!out || out_cap == 0) return -3;
    out[0] = 0;
    if (cs_open((cs_arch)arch, (cs_mode)mode, &h) != CS_ERR_OK) return -2;
    cs_insn *insn = cs_malloc(h);
    const uint8_t *p = code; size_t n = len; uint64_t a = addr; size_t used = 0; int32_t cnt = 0;
    while ((max_insns <= 0 || cnt < max_insns) && cs_disasm_iter(h, &p, &n, &a, insn)) {
        int w = snprintf(out + used, out_cap - used, "%llx\t%u\t%s\t%s\n",
                         (unsigned long long)insn->address, (unsigned)insn->size, insn->mnemonic, insn->op_str);
        if (w < 0 || (size_t)w >= out_cap - used) { out[used] = 0; cnt = -3; break; }
        used += (size_t)w; cnt++;
    }
    cs_free(insn, 1);
    cs_close(&h);
    return cnt;
}
#else
int32_t cx_cs_available(void) { return 0; }
int32_t cx_cs_archs(void) { return 0; }
int32_t cx_disasm(int32_t arch, int32_t mode, const uint8_t *code, size_t len,
                  uint64_t addr, int32_t max_insns, char *out, size_t out_cap) {
    (void)arch; (void)mode; (void)code; (void)len; (void)addr; (void)max_insns;
    if (out && out_cap) out[0] = 0;
    return -1;
}
#endif
