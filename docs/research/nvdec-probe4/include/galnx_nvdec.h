/* GalNX NVDEC movie decode module (probe build, also the blueprint for the
 * rfvp platform/switch integration).
 *
 * Only depends on FFmpeg (built with --enable-envideo) + libnx.  The caller
 * gets RGBA8888 frames plus per-stage timings; hardware (AV_PIX_FMT_ENVIDEO)
 * decoding is used when the device exposes it, otherwise the module silently
 * falls back to software decoding of the same file.
 */
#ifndef GALNX_NVDEC_H
#define GALNX_NVDEC_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct GalnxNvdecCtx GalnxNvdecCtx;

typedef struct GalnxNvdecInfo {
    int width;
    int height;
    int codec_id;
    char codec_name[32];
    char pix_fmt_name[32];
    int hw_requested;    /* 1: we asked the decoder for ENVIDEO hardware decoding */
    int hw_used;         /* 1: the decoder actually output ENVIDEO frames (set on first frame) */
    double fps;
    int64_t duration_ms;
    int64_t frames_hint;
} GalnxNvdecInfo;

/* Open a movie file (sdmc:/..., "file:" is added internally) and prepare decoding.
 * Returns NULL on failure and fills err. */
GalnxNvdecCtx *galnx_nvdec_open(const char *path, GalnxNvdecInfo *info,
                                char *err, size_t errlen);

/* Decode the next video frame.
 * Returns 1 = new RGBA frame, 2 = frame decoded but skipped on purpose
 * (probe mode), 0 = end of stream, -1 = error (err filled).
 * The RGBA buffer is owned by ctx and stays valid until the next call. */
int galnx_nvdec_next(GalnxNvdecCtx *ctx,
                     const uint8_t **rgba,
                     int *width, int *height,
                     int64_t *pts_ms,
                     double *decode_ms,
                     double *transfer_ms,
                     double *convert_ms,
                     char *err, size_t errlen);

/* 1 once the decoder has produced at least one ENVIDEO (hardware) frame. */
int galnx_nvdec_hw_used(GalnxNvdecCtx *ctx);

/* 1 if the frame returned by the last galnx_nvdec_next() call came from NVDEC. */
int galnx_nvdec_last_hw(GalnxNvdecCtx *ctx);

/* --- probe4 readback extension ----------------------------------------
 * Instead of av_hwframe_transfer_data() (Copy Engine tiled->linear), the
 * listed 1-based display-order frames are read out of the block-linear
 * surface and un-tiled on the CPU.  Used by nvdec-probe4 to locate the
 * reason for the 20 s transfer on the device. */
void galnx_nvdec_set_probe(GalnxNvdecCtx *ctx, const char *prefix, const int *idxs, int n);

/* Attach a software decoded planar YUV420P reference to probe slot 'slot'
 * (same order as idxs); NULL means "dump only, no PSNR". */
void galnx_nvdec_set_probe_ref(GalnxNvdecCtx *ctx, int slot, const uint8_t *yuv420p, int w, int h);

/* Multi-line report of the probe (layout trials, PSNR, dumps) or "" . */
const char *galnx_nvdec_probe_report(GalnxNvdecCtx *ctx);

/* Display-order index of the last hardware frame (0 when probe mode is off). */
int galnx_nvdec_frame_index(GalnxNvdecCtx *ctx);

void galnx_nvdec_close(GalnxNvdecCtx *ctx);

#ifdef __cplusplus
}
#endif

#endif /* GALNX_NVDEC_H */