/* Minimal XXH64 (64-bit xxHash) implementation, written from the published
 * algorithm description (Yann Collet, public domain).  Only used to compare
 * the NVDEC reference decode against the value recorded upstream. */
#include "xxh64.h"

#include <string.h>

#define P1 UINT64_C(11400714785074694791)
#define P2 UINT64_C(14029467366897019727)
#define P3 UINT64_C(1609587929392839161)
#define P4 UINT64_C(9650029242287828579)
#define P5 UINT64_C(2870177450012600261)

static inline uint64_t rotl64(uint64_t x, int r) {
    return (x << r) | (x >> (64 - r));
}

static inline uint64_t rd64(const uint8_t *p) {
    uint64_t v;
    memcpy(&v, p, 8);
    return v;
}

static inline uint32_t rd32(const uint8_t *p) {
    uint32_t v;
    memcpy(&v, p, 4);
    return v;
}

static inline uint64_t round64(uint64_t acc, uint64_t input) {
    acc += input * P2;
    acc = rotl64(acc, 31);
    acc *= P1;
    return acc;
}

static inline uint64_t merge_round(uint64_t acc, uint64_t val) {
    val = round64(0, val);
    acc ^= val;
    acc = acc * P1 + P4;
    return acc;
}

uint64_t galnx_xxh64(const void *data, size_t len, uint64_t seed) {
    const uint8_t *p = (const uint8_t *)data;
    const uint8_t *const end = p + len;
    uint64_t h;

    if (len >= 32) {
        const uint8_t *const limit = end - 32;
        uint64_t v1 = seed + P1 + P2;
        uint64_t v2 = seed + P2;
        uint64_t v3 = seed;
        uint64_t v4 = seed - P1;

        do {
            v1 = round64(v1, rd64(p)); p += 8;
            v2 = round64(v2, rd64(p)); p += 8;
            v3 = round64(v3, rd64(p)); p += 8;
            v4 = round64(v4, rd64(p)); p += 8;
        } while (p <= limit);

        h = rotl64(v1, 1) + rotl64(v2, 7) + rotl64(v3, 12) + rotl64(v4, 18);
        h = merge_round(h, v1);
        h = merge_round(h, v2);
        h = merge_round(h, v3);
        h = merge_round(h, v4);
    } else {
        h = seed + P5;
    }

    h += (uint64_t)len;

    while (p + 8 <= end) {
        h ^= round64(0, rd64(p));
        h = rotl64(h, 27) * P1 + P4;
        p += 8;
    }
    if (p + 4 <= end) {
        h ^= (uint64_t)rd32(p) * P1;
        h = rotl64(h, 23) * P2 + P3;
        p += 4;
    }
    while (p < end) {
        h ^= (uint64_t)(*p) * P5;
        h = rotl64(h, 11) * P1;
        p++;
    }

    h ^= h >> 33;
    h *= P2;
    h ^= h >> 29;
    h *= P3;
    h ^= h >> 32;
    return h;
}
