/* chessx.h - shared header for every ChessX C module (native .so/.dll/.dylib and wasm32-wasi).
 * Rules: C99, no globals with state, no malloc in hot paths (caller owns buffers),
 * fixed-width ints only (identical results on native and wasm). */
#ifndef CHESSX_H
#define CHESSX_H
#include <stddef.h>
#include <stdint.h>

#if defined(__wasm__)
#  define CX_API(name) __attribute__((export_name(#name))) __attribute__((visibility("default")))
#elif defined(_WIN32)
#  define CX_API(name) __declspec(dllexport)
#else
#  define CX_API(name) __attribute__((visibility("default")))
#endif

#define CX_ABI_VERSION 1

/* common/ */
CX_API(cx_abi_version) int32_t cx_abi_version(void);
CX_API(cx_alloc) void *cx_alloc(size_t n);   /* for JS/wasm hosts to pass buffers */
CX_API(cx_free) void cx_free(void *p);

#endif
