#include "chessx.h"
#include <stdlib.h>

int32_t cx_abi_version(void) { return CX_ABI_VERSION; }
void *cx_alloc(size_t n) { return malloc(n ? n : 1); }
void cx_free(void *p) { free(p); }
