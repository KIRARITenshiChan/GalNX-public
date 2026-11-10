/* GalNX NVDEC probe4 -- read the block-linear NVDEC surface from the CPU.
 *
 * See galnx_probe4.h for the rationale.  This file only touches the frame
 * produced by averne/FFmpeg's envideo backend (private AVEnvideoFrame header),
 * so it must be compiled with -I$(FFMPEG_SRC).
 */
#include "galnx_probe4.h"

#include <math.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <switch.h>

#include <libavutil/frame.h>
#include <libavutil/hwcontext.h>
#include <libavutil/pixdesc.h>
#include <libavutil/pixfmt.h>

#include <envideo/envideo.h>
/* Private FFmpeg header: AVEnvideoFrame / AVEnvideoDeviceContext. */
#include <libavutil/hwcontext_envideo.h>

#define P4_MAX_TARGETS 4
#define P4_REPORT_CAP  8192
#define P4_MAX_TRIALS  4

typedef struct P4Target {
    int frame_index;
    int ref_present;
    const uint8_t *ref_yuv; /* tightly packed planar YUV420P */
    int ref_w, ref_h;
    int handled;
    int fence_rc;
    int64_t fence_us;
    int tile_rows;
    int stride0, rows0, stride1, rows1;
    int64_t off1;
    int raw_bytes;
    double psnr_y;
    double detile_ms;
    double convert_ms;
    int w, h;
} P4Target;

typedef struct P4State {
    int enabled;
    int n;
    char prefix[192];
    P4Target t[P4_MAX_TARGETS];
    uint8_t *rgba;
    int rgba_cap;
    uint8_t *det0;
    uint8_t *det1;
    size_t det_cap;
    char report[P4_REPORT_CAP];
    int report_len;
} P4State;

static P4State g;

static double now_ms(void) {
    return (double)svcGetSystemTick() / 19200.0;
}

static void rep(const char *fmt, ...) {
    if (g.report_len >= (int)sizeof(g.report) - 1) return;
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(g.report + g.report_len, sizeof(g.report) - (size_t)g.report_len, fmt, ap);
    va_end(ap);
    if (n > 0) {
        g.report_len += n;
        if (g.report_len > (int)sizeof(g.report) - 1) g.report_len = (int)sizeof(g.report) - 1;
    }
}

/* Copy a block-linear ("tiled") plane into a linear one.
 *
 * The NVDEC surface uses gob_height=2 => 64x16 byte blocks (tiles).  Tiles are
 * laid out left-to-right inside a band, bands follow each other vertically.
 * Inside a tile the 16 rows are stored back-to-back (each 64 B = one GOB row),
 * which is exact for 64-byte-wide GOBs. */
static void detile_plane(uint8_t *dst, int dst_stride, const uint8_t *src,
                         int width_bytes, int height_rows, int tile_rows,
                         size_t avail) {
    const int tile_w = 64;
    if (width_bytes <= 0 || height_rows <= 0 || tile_rows <= 0) return;
    const int tiles_per_row = width_bytes / tile_w;
    if (tiles_per_row <= 0) return;
    const int tile_bytes = tile_w * tile_rows;
    const int bands = (height_rows + tile_rows - 1) / tile_rows;
    for (int b = 0; b < bands; b++) {
        for (int t = 0; t < tiles_per_row; t++) {
            size_t src_off = ((size_t)b * (size_t)tiles_per_row + (size_t)t) * (size_t)tile_bytes;
            if (src_off + (size_t)tile_bytes > avail) continue;
            const uint8_t *tile = src + src_off;
            for (int r = 0; r < tile_rows; r++) {
                int row = b * tile_rows + r;
                if (row >= height_rows) break;
                memcpy(dst + (size_t)row * (size_t)dst_stride + (size_t)t * tile_w,
                       tile + (size_t)r * tile_w, (size_t)tile_w);
            }
        }
    }
}

static double psnr_u8(const uint8_t *a, int a_stride, const uint8_t *b, int b_stride,
                      int w, int h) {
    if (!a || !b || w <= 0 || h <= 0) return -1.0;
    uint64_t se = 0, n = 0;
    for (int y = 0; y < h; y++) {
        const uint8_t *pa = a + (size_t)y * a_stride;
        const uint8_t *pb = b + (size_t)y * b_stride;
        for (int x = 0; x < w; x++) {
            int d = (int)pa[x] - (int)pb[x];
            se += (uint64_t)(d * d);
        }
        n += (uint64_t)w;
    }
    if (!n) return -1.0;
    double mse = (double)se / (double)n;
    if (mse <= 0.0) return 99.0;
    return 10.0 * log10((255.0 * 255.0) / mse);
}

static inline uint8_t clamp_u8(int v) {
    if (v < 0) return 0;
    if (v > 255) return 255;
    return (uint8_t)v;
}

/* NV12 (chroma interleaved) -> packed RGBA8888, same math as galnx_nvdec.c. */
static int nv12_to_rgba(const uint8_t *yp, int ys, const uint8_t *uvp, int uvs,
                        int w, int h, int bt709, int full, uint8_t **buf,
                        int *cap, char *why, size_t whylen) {
    const size_t need = (size_t)w * (size_t)h * 4u;
    if (*cap < (int)need || !*buf) {
        free(*buf);
        *buf = (uint8_t *)malloc(need);
        if (!*buf) {
            *cap = 0;
            snprintf(why, whylen, "out of memory for RGBA (%u bytes)", (unsigned)need);
            return -1;
        }
        *cap = (int)need;
    }
    for (int y = 0; y < h; y++) {
        const uint8_t *yrow = yp + (size_t)y * (size_t)ys;
        const uint8_t *uvrow = uvp + (size_t)(y >> 1) * (size_t)uvs;
        uint8_t *orow = *buf + (size_t)y * (size_t)w * 4u;
        for (int x = 0; x < w; x++) {
            const int Y = yrow[x];
            const int ci = (x >> 1) * 2;
            const int U = (int)uvrow[ci] - 128;
            const int V = (int)uvrow[ci + 1] - 128;
            int r, gg, b;
            if (full) {
                r = Y + ((1436 * V) >> 10);
                gg = Y - ((352 * U + 731 * V) >> 10);
                b = Y + ((1815 * U) >> 10);
            } else {
                const int C = (Y - 16) * 298;
                if (bt709) {
                    r = (C + 459 * V + 128) >> 8;
                    gg = (C - 55 * U - 136 * V + 128) >> 8;
                    b = (C + 541 * U + 128) >> 8;
                } else {
                    r = (C + 409 * V + 128) >> 8;
                    gg = (C - 100 * U - 208 * V + 128) >> 8;
                    b = (C + 516 * U + 128) >> 8;
                }
            }
            orow[x * 4 + 0] = clamp_u8(r);
            orow[x * 4 + 1] = clamp_u8(gg);
            orow[x * 4 + 2] = clamp_u8(b);
            orow[x * 4 + 3] = 255;
        }
    }
    return 0;
}

static int dump_file(const char *path, const uint8_t *data, size_t n) {
    FILE *fp = fopen(path, "wb");
    if (!fp) return -1;
    size_t wr = fwrite(data, 1, n, fp);
    int rc = fclose(fp);
    if (wr != n || rc != 0) return -2;
    return 0;
}

void galnx_probe4_setup(const char *prefix, const int *idxs, int n) {
    memset(&g, 0, sizeof(g));
    g.enabled = 1;
    snprintf(g.prefix, sizeof(g.prefix), "%s", (prefix && prefix[0]) ? prefix : "sdmc:/nvdec-probe4");
    if (n > P4_MAX_TARGETS) n = P4_MAX_TARGETS;
    if (n < 0) n = 0;
    g.n = n;
    rep("probe4: prefix=%s targets=", g.prefix);
    for (int i = 0; i < n; i++) {
        g.t[i].frame_index = idxs[i];
        rep("%d ", idxs[i]);
    }
    rep("\n");
}

int galnx_probe4_enabled(void) { return g.enabled; }

void galnx_probe4_set_ref(int slot, const uint8_t *yuv420p, int w, int h) {
    if (slot < 0 || slot >= g.n) return;
    g.t[slot].ref_present = (yuv420p && w > 0 && h > 0) ? 1 : 0;
    g.t[slot].ref_yuv = yuv420p;
    g.t[slot].ref_w = w;
    g.t[slot].ref_h = h;
}

int galnx_probe4_handle(int frame_index, const AVFrame *f, GalnxProbeResult4 *out) {
    if (!g.enabled) return 0;

    int slot = -1;
    for (int i = 0; i < g.n; i++) {
        if (!g.t[i].handled && g.t[i].frame_index == frame_index) slot = i;
    }
    if (slot < 0) return 0;

    P4Target *t = &g.t[slot];
    t->handled = 1;

    if (!f || f->format != AV_PIX_FMT_ENVIDEO || !f->buf[0] || !f->buf[0]->data ||
        !f->hw_frames_ctx || !f->hw_frames_ctx->data) {
        rep("f%03d: not a hardware ENVIDEO frame (format=%d), skipped\n",
            frame_index, f ? (int)f->format : -1);
        return 0;
    }

    AVHWFramesContext *fc = (AVHWFramesContext *)f->hw_frames_ctx->data;
    AVHWDeviceContext *dc = (AVHWDeviceContext *)fc->device_ref->data;
    AVEnvideoDeviceContext *ec = (AVEnvideoDeviceContext *)dc->hwctx;
    AVEnvideoFrame *ev = (AVEnvideoFrame *)f->buf[0]->data;
    if (!ec || !ec->device || !ev->map) {
        rep("f%03d: missing envideo device/map\n", frame_index);
        return -1;
    }

    EnvideoMap *map = ev->map;
    const size_t msize = envideo_map_get_size(map);
    uint8_t *cpu = (uint8_t *)envideo_map_get_cpu_addr(map);
    const uint64_t gpu0 = envideo_map_get_gpu_addr(map);
    if (!cpu) {
        rep("f%03d: envideo_map_get_cpu_addr returned NULL (map size %u)\n",
            frame_index, (unsigned)msize);
        return -1;
    }

    const enum AVPixelFormat swf = fc->sw_format;
    const int w = f->width > 0 ? f->width : fc->width;
    const int h = f->height > 0 ? f->height : fc->height;
    const int stride0 = f->linesize[0] > 0 ? f->linesize[0] : w;
    const int stride1 = f->linesize[1] != 0 ? f->linesize[1] : stride0;
    const int64_t off0 = (int64_t)((uintptr_t)f->data[0] - (uintptr_t)gpu0);
    const int64_t off1 = (int64_t)((uintptr_t)f->data[1] - (uintptr_t)gpu0);
    const int64_t off2 = (int64_t)((uintptr_t)f->data[2] - (uintptr_t)gpu0);

    rep("f%03d: sw_fmt=%s %dx%d ls=(%d,%d,%d) off=(%lld,%lld,%lld) map=%u B "
        "is_pitch=%d gob_height=%d colorspace=%d range=%d\n",
        frame_index, av_get_pix_fmt_name(swf) ? av_get_pix_fmt_name(swf) : "?",
        w, h, stride0, stride1, f->linesize[2],
        (long long)off0, (long long)off1, (long long)off2, (unsigned)msize,
        (int)ev->is_pitch, (int)ev->gob_height, (int)f->colorspace, (int)f->color_range);

    if (off0 < 0 || (size_t)off0 >= msize) {
        rep("f%03d: plane0 offset out of range\n", frame_index);
        return -1;
    }

    /* Make sure the GPU finished writing the surface before the CPU reads it.
     * The frame is normally waited for with UINT64_MAX inside FFmpeg only when
     * the frame is freed, i.e. after our read would have happened. */
    double tw = now_ms();
    t->fence_rc = envideo_fence_wait(ec->device, ev->fence, 5000000ULL);
    t->fence_us = (int64_t)((now_ms() - tw) * 1000.0);
    rep("f%03d: fence_wait rc=%d took=%lld us\n", frame_index, t->fence_rc, (long long)t->fence_us);

    envideo_map_cache_op(map, (size_t)off0, msize - (size_t)off0, EnvideoCache_Invalidate);

    const uint8_t *base = cpu + off0;
    const size_t avail = msize - (size_t)off0;
    if (g.det_cap < avail) {
        free(g.det0);
        free(g.det1);
        g.det0 = (uint8_t *)malloc(avail);
        g.det1 = (uint8_t *)malloc(avail);
        g.det_cap = (g.det0 && g.det1) ? avail : 0;
        if (!g.det_cap) {
            rep("f%03d: out of memory for de-tile buffers (%u B each)\n",
                frame_index, (unsigned)avail);
            return -1;
        }
    }

    rep("f%03d: raw head =", frame_index);
    for (int i = 0; i < 32; i++) rep(" %02x", base[i]);
    rep("\n");

    /* Plane 1 offset candidates: what FFmpeg advertises, plus the two
     * plausible "height without / with 32-line alignment" pitches. */
    int64_t cand1[4];
    int ncand = 0;
    cand1[ncand++] = off1 - off0;
    cand1[ncand++] = (int64_t)stride0 * h;
    cand1[ncand++] = (int64_t)stride0 * ((h + 31) & ~31);
    for (int i = 1; i < ncand; i++) {
        for (int j = 0; j < i; j++) {
            if (cand1[i] == cand1[j]) {
                for (int k = i; k < ncand - 1; k++) cand1[k] = cand1[k + 1];
                ncand--;
                i--;
                break;
            }
        }
    }

    static const int kTileRows[P4_MAX_TRIALS] = {16, 8, 32, 64};
    int best_tr = 0;
    int64_t best_off1 = 0;
    double best_psnr = -99.0;
    const int nv12 = (swf == AV_PIX_FMT_NV12);

    if (nv12 && t->ref_present) {
        for (int ti = 0; ti < P4_MAX_TRIALS; ti++) {
            const int tr = kTileRows[ti];
            for (int ci = 0; ci < ncand; ci++) {
                const int64_t o1 = cand1[ci];
                if (o1 <= 0 || (size_t)o1 >= avail) continue;
                const int rows0 = (int)(o1 / stride0);
                if (rows0 < h) continue;
                const double t0 = now_ms();
                detile_plane(g.det0, stride0, base, stride0, rows0, tr, avail);
                const double dt = now_ms() - t0;
                const int cmp_h = (rows0 < t->ref_h) ? rows0 : t->ref_h;
                const int cmp_w = (w < t->ref_w) ? w : t->ref_w;
                const double p = psnr_u8(g.det0, stride0, t->ref_yuv, t->ref_w, cmp_w, cmp_h);
                rep("f%03d: trial tile_rows=%d off1=%lld rows0=%d detile=%.2fms psnrY=%.2f\n",
                    frame_index, tr, (long long)o1, rows0, dt, p);
                if (p > best_psnr) {
                    best_psnr = p;
                    best_tr = tr;
                    best_off1 = o1;
                }
            }
        }
    }

    if (best_tr == 0) {
        best_tr = 16;
        best_off1 = off1 - off0;
        best_psnr = -1.0;
        rep("f%03d: no PSNR sweep (nv12=%d ref=%d), assuming tile_rows=16 off1=%lld\n",
            frame_index, nv12, t->ref_present, (long long)best_off1);
    }
    rep("f%03d: chosen tile_rows=%d off1=%lld psnrY=%.2f\n",
        frame_index, best_tr, (long long)best_off1, best_psnr);

    /* Final de-tile of both planes with the winning parameters. */
    const double td0 = now_ms();
    int rows0 = (int)(best_off1 / stride0);
    if (rows0 < h) rows0 = ((h + best_tr - 1) / best_tr) * best_tr;
    detile_plane(g.det0, stride0, base, stride0, rows0, best_tr, avail);

    int rows1 = 0;
    if (best_off1 > 0 && (size_t)best_off1 < avail) {
        rows1 = (int)((avail - (size_t)best_off1) / (size_t)stride1);
        if (rows1 > 32 * 1024) rows1 = 32 * 1024; /* sanity */
        detile_plane(g.det1, stride1, base + best_off1, stride1, rows1, best_tr,
                     avail - (size_t)best_off1);
    }
    const double dt = now_ms() - td0;

    t->tile_rows = best_tr;
    t->off1 = best_off1;
    t->stride0 = stride0;
    t->rows0 = rows0;
    t->stride1 = stride1;
    t->rows1 = rows1;
    t->raw_bytes = (int)avail;
    t->psnr_y = best_psnr;
    t->w = w;
    t->h = h;

    char path[256];
    snprintf(path, sizeof(path), "%s-f%03d-raw.bin", g.prefix, frame_index);
    int drc = dump_file(path, base, avail);
    rep("f%03d: wrote %s (%u B) rc=%d\n", frame_index, path, (unsigned)avail, drc);

    if (t->ref_present) {
        const size_t refn = (size_t)t->ref_w * (size_t)t->ref_h * 3u / 2u;
        snprintf(path, sizeof(path), "%s-f%03d-ref.yuv", g.prefix, frame_index);
        drc = dump_file(path, t->ref_yuv, refn);
        rep("f%03d: wrote %s (%u B) rc=%d\n", frame_index, path, (unsigned)refn, drc);
    }

    /* Dump the de-tiled frame as planar YUV420P so the PC can diff it against
     * an ffmpeg reference without trusting the device-side PSNR only. */
    if (nv12 && rows1 > 0) {
        const int cw = (w + 1) / 2;
        const int ch = (h + 1) / 2;
        const size_t yn = (size_t)w * (size_t)h;
        const size_t cn = (size_t)cw * (size_t)ch;
        uint8_t *yuv = (uint8_t *)malloc(yn + 2u * cn);
        if (yuv) {
            for (int y = 0; y < h; y++) memcpy(yuv + (size_t)y * w, g.det0 + (size_t)y * stride0, (size_t)w);
            uint8_t *up = yuv + yn;
            uint8_t *vp = up + cn;
            for (int y = 0; y < ch && y < rows1; y++) {
                const uint8_t *row = g.det1 + (size_t)y * stride1;
                for (int x = 0; x < cw; x++) {
                    up[(size_t)y * cw + x] = row[x * 2];
                    vp[(size_t)y * cw + x] = row[x * 2 + 1];
                }
            }
            snprintf(path, sizeof(path), "%s-f%03d-detiled.yuv", g.prefix, frame_index);
            drc = dump_file(path, yuv, yn + 2u * cn);
            rep("f%03d: wrote %s (%u B) rc=%d\n", frame_index, path,
                (unsigned)(yn + 2u * cn), drc);
            free(yuv);
        }
    }

    if (!nv12 || rows1 <= 0) {
        rep("f%03d: no RGBA output (nv12=%d rows1=%d)\n", frame_index, nv12, rows1);
        return 0;
    }

    const double tc = now_ms();
    const int bt709 = (f->colorspace == AVCOL_SPC_BT709) ||
                      (f->colorspace != AVCOL_SPC_BT470BG && f->colorspace != AVCOL_SPC_SMPTE170M && w >= 1280);
    const int full = (f->color_range == AVCOL_RANGE_JPEG);
    char why[128] = {0};
    if (nv12_to_rgba(g.det0, stride0, g.det1, stride1, w, h, bt709, full, &g.rgba,
                     &g.rgba_cap, why, sizeof(why)) != 0) {
        rep("f%03d: RGBA conversion failed: %s\n", frame_index, why);
        return -1;
    }
    t->detile_ms = dt;
    t->convert_ms = now_ms() - tc;

    rep("f%03d: detile=%.2fms convert=%.2fms\n", frame_index, t->detile_ms, t->convert_ms);

    if (out) {
        out->rgba = g.rgba;
        out->w = w;
        out->h = h;
        out->detile_ms = t->detile_ms;
        out->convert_ms = t->convert_ms;
    }
    return 1;
}

const char *galnx_probe4_report(void) {
    return g.report;
}
