/* Minimal public-domain XXH64 implementation (xxHash spec). */
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

uint64_t galnx_xxh64(const void *data, size_t len, uint64_t seed);

#ifdef __cplusplus
}
#endif
