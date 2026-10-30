/* capstone CLI for parity tests:  capstone_cli <arch> <mode> <addr-hex> <code-hex>  */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "capstone.h"

static int hexval(int c) {
    return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
}

int main(int argc, char **argv) {
    static uint8_t code[4096];
    static char out[1 << 16];
    if (argc < 5) { fprintf(stderr, "usage: %s arch mode addr hex\n", argv[0]); return 2; }
    size_t hl = strlen(argv[4]), n = 0;
    for (size_t i = 0; i + 1 < hl && n < sizeof code; i += 2) {
        int hi = hexval(argv[4][i]), lo = hexval(argv[4][i + 1]);
        if (hi < 0 || lo < 0) return 2;
        code[n++] = (uint8_t)(hi * 16 + lo);
    }
    int32_t r = cx_disasm((int32_t)atoi(argv[1]), (int32_t)(uint32_t)strtoull(argv[2], NULL, 0), code, n,
                          (uint64_t)strtoull(argv[3], NULL, 16), 0, out, sizeof out);
    if (r < 0) { printf("error %d\n", (int)r); return 0; }
    fputs(out, stdout);
    return 0;
}
