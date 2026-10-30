/* search - ChessX search core: URL normalisation, result fusion (dedupe by normalised URL with a
 * cross-engine agreement bonus) and ranking. Reference implementation: chessx_libs/search/fusion.py
 * (pure-Python fallback in chessx_libs/native/search.py).
 *
 * Scores are fixed point: 1.0 == CX_SCORE_ONE (1e9), so native and wasm give bit-identical results.
 * URLs are ASCII byte strings (the Python wrapper routes non-ASCII / bracketed-IPv6 URLs to Python). */
#ifndef CX_SEARCH_H
#define CX_SEARCH_H
#include "chessx.h"

#define CX_SCORE_ONE 1000000000LL
#define CX_AGREEMENT_BONUS 250000000LL  /* 0.25, same as fusion.AGREEMENT_BONUS */

/* norm_url(url) == host(lowercase, no "www.") + path(no trailing "/", no ;params) + ["?" query].
 * Writes at most cap bytes; returns the output length (always <= len), or -1 if cap is too small. */
CX_API(cx_norm_url) int32_t cx_norm_url(const uint8_t *url, size_t len, uint8_t *out, size_t cap);

/* Fuse n results. url i = blob[off[i] .. off[i]+lens[i]), engine id engines[i], score scores[i]
 * (clamped to [0, CX_SCORE_ONE]). Same URL key from a *different* engine: score += s + bonus;
 * same engine again: score = max(score, s). Outputs (caller-owned, n entries each):
 *   out_group[i]  group index of input i (groups numbered in first-seen order)
 *   out_score[g]  fused score of group g
 *   out_order[k]  groups ranked by score desc, first-seen asc (stable)
 * Returns the number of groups, or -1 on bad input / allocation failure. */
CX_API(cx_search_fuse) int32_t cx_search_fuse(const uint8_t *blob, const int32_t *off, const int32_t *lens,
                                              const int32_t *engines, const int64_t *scores, int32_t n,
                                              int32_t *out_group, int64_t *out_score, int32_t *out_order);

/* Stable ranking: out_order = indices of scores sorted desc (ties keep input order). Returns n. */
CX_API(cx_search_rank) int32_t cx_search_rank(const int64_t *scores, int32_t n, int32_t *out_order);
#endif
