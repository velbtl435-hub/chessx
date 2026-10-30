#include "../search.h"
#include <string.h>

static int is_c0sp(uint8_t c) { return c <= 0x20; }
static int is_alpha(uint8_t c) { return (c | 32) >= 'a' && (c | 32) <= 'z'; }
static int is_scheme_char(uint8_t c) {
    return is_alpha(c) || (c >= '0' && c <= '9') || c == '+' || c == '-' || c == '.';
}
static uint8_t lower(uint8_t c) { return (c >= 'A' && c <= 'Z') ? (uint8_t)(c + 32) : c; }

static int scheme_uses_params(const uint8_t *s, size_t n) {  /* urllib.parse.uses_params */
    static const char *L[] = {"", "ftp", "hdl", "prospero", "http", "imap", "https", "shttp", "rtsp", "rtsps",
                              "rtspu", "sip", "sips", "mms", "sftp", "tel"};
    for (size_t k = 0; k < sizeof L / sizeof *L; k++) {
        size_t m = strlen(L[k]);
        if (m != n) continue;
        size_t j = 0;
        while (j < n && lower(s[j]) == (uint8_t)L[k][j]) j++;
        if (j == n) return 1;
    }
    return 0;
}

static int64_t find(const uint8_t *s, size_t a, size_t b, uint8_t c) {
    for (size_t i = a; i < b; i++) if (s[i] == c) return (int64_t)i;
    return -1;
}

/* Mirrors urllib.parse.urlparse + fusion.norm_url for ASCII input. */
static int32_t norm_core(const uint8_t *in, size_t len, uint8_t *u, uint8_t *out) {
    size_t n = 0, i = 0, o = 0;
    while (i < len && is_c0sp(in[i])) i++;                 /* lstrip C0 control/space */
    for (; i < len; i++)                                    /* remove \t \r \n */
        if (in[i] != '\t' && in[i] != '\r' && in[i] != '\n') u[n++] = in[i];
    size_t p = 0, sch_a = 0, sch_n = 0;
    int64_t colon = find(u, 0, n, ':');
    if (colon > 0 && is_alpha(u[0])) {
        size_t k = 0;
        while (k < (size_t)colon && is_scheme_char(u[k])) k++;
        if (k == (size_t)colon) { sch_a = 0; sch_n = k; p = k + 1; }
    }
    size_t host_a = p, host_b = p;
    if (n - p >= 2 && u[p] == '/' && u[p + 1] == '/') {
        size_t e = p + 2;
        while (e < n && u[e] != '/' && u[e] != '?' && u[e] != '#') e++;
        host_a = p + 2; host_b = e; p = e;
    }
    size_t end = n;
    int64_t h = find(u, p, n, '#');
    if (h >= 0) end = (size_t)h;
    size_t path_b = end, q_a = end, q_b = end;
    int64_t q = find(u, p, end, '?');
    if (q >= 0) { path_b = (size_t)q; q_a = (size_t)q + 1; }
    if (scheme_uses_params(u + sch_a, sch_n) && find(u, p, path_b, ';') >= 0) {
        int64_t slash = -1;
        for (size_t k = p; k < path_b; k++) if (u[k] == '/') slash = (int64_t)k;
        int64_t semi = slash >= 0 ? find(u, (size_t)slash, path_b, ';') : find(u, p, path_b, ';');
        if (semi >= 0) path_b = (size_t)semi;
    }
    /* host: lower, removeprefix("www.") */
    size_t ha = host_a;
    if (host_b - host_a >= 4 && lower(u[ha]) == 'w' && lower(u[ha + 1]) == 'w' && lower(u[ha + 2]) == 'w' &&
        u[ha + 3] == '.') ha += 4;
    for (size_t k = ha; k < host_b; k++) out[o++] = lower(u[k]);
    while (path_b > p && u[path_b - 1] == '/') path_b--;     /* path.rstrip('/') */
    for (size_t k = p; k < path_b; k++) out[o++] = u[k];
    if (q_b > q_a) { out[o++] = '?'; for (size_t k = q_a; k < q_b; k++) out[o++] = u[k]; }
    return (int32_t)o;
}

CX_API(cx_norm_url) int32_t cx_norm_url(const uint8_t *url, size_t len, uint8_t *out, size_t cap) {
    uint8_t *u = cx_alloc(len + 1), *tmp = cx_alloc(len + 1);
    if (!u || !tmp) { cx_free(u); cx_free(tmp); return -1; }
    int32_t m = norm_core(url, len, u, tmp);
    if ((size_t)m > cap) m = -1; else if (m > 0) memcpy(out, tmp, (size_t)m);
    cx_free(u); cx_free(tmp);
    return m;
}

static int64_t clamp(int64_t s) { return s < 0 ? 0 : s > CX_SCORE_ONE ? CX_SCORE_ONE : s; }

/* stable merge sort of idx by key desc */
static void msort(int32_t *idx, int32_t *tmp, const int64_t *key, int32_t n) {
    for (int32_t w = 1; w < n; w *= 2) {
        for (int32_t lo = 0; lo < n; lo += 2 * w) {
            int32_t mid = lo + w < n ? lo + w : n, hi = lo + 2 * w < n ? lo + 2 * w : n, a = lo, b = mid, k = lo;
            while (a < mid && b < hi) tmp[k++] = key[idx[b]] > key[idx[a]] ? idx[b++] : idx[a++];
            while (a < mid) tmp[k++] = idx[a++];
            while (b < hi) tmp[k++] = idx[b++];
        }
        memcpy(idx, tmp, sizeof *idx * (size_t)n);
    }
}

CX_API(cx_search_rank) int32_t cx_search_rank(const int64_t *scores, int32_t n, int32_t *out_order) {
    if (n <= 0) return 0;
    int32_t *tmp = cx_alloc(sizeof *tmp * (size_t)n);
    if (!tmp) return -1;
    for (int32_t i = 0; i < n; i++) out_order[i] = i;
    msort(out_order, tmp, scores, n);
    cx_free(tmp);
    return n;
}

CX_API(cx_search_fuse) int32_t cx_search_fuse(const uint8_t *blob, const int32_t *off, const int32_t *lens,
                                              const int32_t *engines, const int64_t *scores, int32_t n,
                                              int32_t *out_group, int64_t *out_score, int32_t *out_order) {
    if (n < 0) return -1;
    if (n == 0) return 0;
    size_t total = 0, maxlen = 0;
    for (int32_t i = 0; i < n; i++) {
        if (off[i] < 0 || lens[i] < 0) return -1;
        total += (size_t)lens[i];
        if ((size_t)lens[i] > maxlen) maxlen = (size_t)lens[i];
    }
    uint8_t *keys = cx_alloc(total + 1), *scratch = cx_alloc(maxlen + 1);
    int32_t *koff = cx_alloc(sizeof(int32_t) * (size_t)n), *klen = cx_alloc(sizeof(int32_t) * (size_t)n);
    int32_t *first = cx_alloc(sizeof(int32_t) * (size_t)n);   /* first input index of each group */
    int32_t ng = -1;
    if (!keys || !scratch || !koff || !klen || !first) goto done;
    size_t pos = 0;
    ng = 0;
    for (int32_t i = 0; i < n; i++) {
        koff[i] = (int32_t)pos;
        klen[i] = norm_core(blob + off[i], (size_t)lens[i], scratch, keys + pos);
        pos += (size_t)klen[i];
        int64_t s = clamp(scores[i]);
        int32_t g = -1;
        for (int32_t j = 0; j < ng; j++) {                  /* O(n*groups): result lists are small */
            int32_t f = first[j];
            if (klen[f] == klen[i] && !memcmp(keys + koff[f], keys + koff[i], (size_t)klen[i])) { g = j; break; }
        }
        if (g < 0) { g = ng++; first[g] = i; out_score[g] = s; out_group[i] = g; continue; }
        int seen = 0;
        for (int32_t k = 0; k < i && !seen; k++) seen = out_group[k] == g && engines[k] == engines[i];
        if (!seen) out_score[g] += s + CX_AGREEMENT_BONUS;
        else if (s > out_score[g]) out_score[g] = s;
        out_group[i] = g;
    }
    if (cx_search_rank(out_score, ng, out_order) < 0) ng = -1;
done:
    cx_free(keys); cx_free(scratch); cx_free(koff); cx_free(klen); cx_free(first);
    return ng;
}
