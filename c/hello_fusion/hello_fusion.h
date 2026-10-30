/* hello_fusion - proof module for the C/WASI pipeline.
 * cx_crc32:  IEEE 802.3 CRC-32 (zlib/binascii compatible).
 * cx_fuse:   dedupe (id, score) pairs by id, summing scores, then sort by
 *            score desc, id asc. Writes up to n pairs into out_ids/out_scores,
 *            returns the number of unique ids. In-place safe? No: out must not alias in. */
#ifndef CX_HELLO_FUSION_H
#define CX_HELLO_FUSION_H
#include "chessx.h"

CX_API(cx_crc32) uint32_t cx_crc32(const uint8_t *data, size_t len);
CX_API(cx_fuse) int32_t cx_fuse(const int32_t *ids, const int64_t *scores, int32_t n,
                                int32_t *out_ids, int64_t *out_scores);
#endif
