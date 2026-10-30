/* WASI/native CLI used by the parity tests (wasmtime run hello_fusion.wasm ...).
 *   crc <text>            -> 8 hex digits
 *   crchex <hexbytes>     -> 8 hex digits
 *   fuse id:score ...     -> "id:score id:score ..." (fused order)            */
#include "hello_fusion.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: crc <text> | crchex <hex> | fuse id:score...\n"); return 2; }
    if (!strcmp(argv[1], "crc")) {
        const char *s = argc > 2 ? argv[2] : "";
        printf("%08x\n", (unsigned)cx_crc32((const uint8_t *)s, strlen(s)));
        return 0;
    }
    if (!strcmp(argv[1], "crchex")) {
        const char *h = argc > 2 ? argv[2] : ""; size_t n = strlen(h) / 2;
        uint8_t *b = malloc(n + 1);
        for (size_t i = 0; i < n; i++) { unsigned v; sscanf(h + 2 * i, "%2x", &v); b[i] = (uint8_t)v; }
        printf("%08x\n", (unsigned)cx_crc32(b, n)); free(b);
        return 0;
    }
    if (!strcmp(argv[1], "fuse")) {
        int32_t n = argc - 2;
        int32_t *ids = malloc(sizeof *ids * (n + 1)), *oi = malloc(sizeof *oi * (n + 1));
        int64_t *sc = malloc(sizeof *sc * (n + 1)), *os = malloc(sizeof *os * (n + 1));
        for (int32_t i = 0; i < n; i++) {
            long long s = 0; int id = 0;
            if (sscanf(argv[i + 2], "%d:%lld", &id, &s) != 2) { fprintf(stderr, "bad pair %s\n", argv[i + 2]); return 2; }
            ids[i] = id; sc[i] = s;
        }
        int32_t m = cx_fuse(ids, sc, n, oi, os);
        for (int32_t i = 0; i < m; i++) printf(i ? " %d:%lld" : "%d:%lld", (int)oi[i], (long long)os[i]);
        printf("\n");
        free(ids); free(oi); free(sc); free(os);
        return 0;
    }
    fprintf(stderr, "unknown command %s\n", argv[1]);
    return 2;
}
