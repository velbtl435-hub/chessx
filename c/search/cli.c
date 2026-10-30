/* WASI/native CLI for parity tests (wasmtime run search.wasm ...).
 *   norm <url>                       -> normalised key
 *   fuse engine:score:url ...        -> "group:score group:score ..." ranked (url may contain ':')
 *   rank score ...                   -> ranked indices                                   */
#include "search.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: norm <url> | fuse e:s:url... | rank s...\n"); return 2; }
    int32_t n = argc - 2;
    if (!strcmp(argv[1], "norm")) {
        const char *s = argc > 2 ? argv[2] : ""; size_t L = strlen(s);
        uint8_t *o = malloc(L + 1);
        int32_t m = cx_norm_url((const uint8_t *)s, L, o, L);
        printf("[%.*s]\n", (int)(m < 0 ? 0 : m), (char *)o); free(o);
        return m < 0;
    }
    if (!strcmp(argv[1], "rank")) {
        int64_t *s = calloc((size_t)n + 1, sizeof *s); int32_t *o = calloc((size_t)n + 1, sizeof *o);
        for (int32_t i = 0; i < n; i++) s[i] = strtoll(argv[i + 2], NULL, 10);
        cx_search_rank(s, n, o);
        for (int32_t i = 0; i < n; i++) printf(i ? " %d" : "%d", (int)o[i]);
        printf("\n"); free(s); free(o);
        return 0;
    }
    if (!strcmp(argv[1], "fuse")) {
        size_t tot = 0;
        for (int32_t i = 0; i < n; i++) tot += strlen(argv[i + 2]);
        uint8_t *blob = malloc(tot + 1);
        int32_t *off = malloc(sizeof(int32_t) * (n + 1)), *len = malloc(sizeof(int32_t) * (n + 1));
        int32_t *eng = malloc(sizeof(int32_t) * (n + 1)), *grp = malloc(sizeof(int32_t) * (n + 1));
        int32_t *ord = malloc(sizeof(int32_t) * (n + 1));
        int64_t *sc = malloc(sizeof(int64_t) * (n + 1)), *gs = malloc(sizeof(int64_t) * (n + 1));
        size_t p = 0;
        for (int32_t i = 0; i < n; i++) {
            int e = 0, used = 0; long long s = 0;
            if (sscanf(argv[i + 2], "%d:%lld:%n", &e, &s, &used) != 2 || !used) { fprintf(stderr, "bad %s\n", argv[i + 2]); return 2; }
            const char *u = argv[i + 2] + used; size_t L = strlen(u);
            memcpy(blob + p, u, L); off[i] = (int32_t)p; len[i] = (int32_t)L; p += L; eng[i] = e; sc[i] = s;
        }
        int32_t m = cx_search_fuse(blob, off, len, eng, sc, n, grp, gs, ord);
        for (int32_t k = 0; k < m; k++) printf(k ? " %d:%lld" : "%d:%lld", (int)ord[k], (long long)gs[ord[k]]);
        printf("\n");
        free(blob); free(off); free(len); free(eng); free(grp); free(ord); free(sc); free(gs);
        return m < 0;
    }
    fprintf(stderr, "unknown command %s\n", argv[1]);
    return 2;
}
