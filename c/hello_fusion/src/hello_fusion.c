#include "../hello_fusion.h"

uint32_t cx_crc32(const uint8_t *data, size_t len) {
    uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        c ^= data[i];
        for (int k = 0; k < 8; k++)
            c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return c ^ 0xFFFFFFFFu;
}

static int before(int32_t ia, int64_t sa, int32_t ib, int64_t sb) {
    return sa > sb || (sa == sb && ia < ib);
}

int32_t cx_fuse(const int32_t *ids, const int64_t *scores, int32_t n,
                int32_t *out_ids, int64_t *out_scores) {
    int32_t m = 0;
    if (n <= 0) return 0;
    for (int32_t i = 0; i < n; i++) {          /* dedupe: O(n*m), fine for result lists */
        int32_t j = 0;
        while (j < m && out_ids[j] != ids[i]) j++;
        if (j == m) { out_ids[m] = ids[i]; out_scores[m] = 0; m++; }
        out_scores[j] = (int64_t)((uint64_t)out_scores[j] + (uint64_t)scores[i]); /* defined wrap */
    }
    for (int32_t i = 1; i < m; i++) {          /* stable insertion sort */
        int32_t id = out_ids[i]; int64_t s = out_scores[i]; int32_t j = i - 1;
        while (j >= 0 && before(id, s, out_ids[j], out_scores[j])) {
            out_ids[j + 1] = out_ids[j]; out_scores[j + 1] = out_scores[j]; j--;
        }
        out_ids[j + 1] = id; out_scores[j + 1] = s;
    }
    return m;
}
