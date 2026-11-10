/* GalNX NVDEC movie decode module -- probe6 build (averne/FFmpeg nvtegra).
 *
 * Differences from probe4/probe5: the hardware backend is FFmpeg's own
 * "nvtegra" hwaccel (same one SwitchWave uses), not averne/envideo.  nvtegra
 * exposes NV12 system-memory frames through av_hwframe_transfer_data()
 * (VIC copy, or a CPU de-tile fallback inside FFmpeg), so this module no
 * longer needs the block-linear readback experiments of probe4.
 *
 * The module still depends only on FFmpeg + libnx; the caller gets RGBA8888
 * frames plus per-stage timings, and can also read the raw NV12 planes of the
 * last hardware frame to run a PSNR check against a software decode.
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
    int hw_requested;    /* 1: we asked the decoder for NVTEGRA hardware decoding */
    int hw_used;         /* 1: the decoder actually output NVTEGRA frames (set on first frame) */
    double fps;
    int64_t duration_ms;
    int64_t frames_hint;
} GalnxNvdecInfo;

/* Open a movie file (sdmc:/..., "file:" is added internally) and prepare decoding.
 * Returns NULL on failure and fills err. */
GalnxNvdecCtx *galnx_nvdec_open(const char *path, GalnxNvdecInfo *info,
                                char *err, size_t errlen);

/* Decode the next video frame.
 * Returns 1 = new RGBA frame, 0 = end of stream, -1 = error (err filled).
 * The RGBA buffer is owned by ctx and stays valid until the next call. */
int galnx_nvdec_next(GalnxNvdecCtx *ctx,
                     const uint8_t **rgba,
                     int *width, int *height,
                     int64_t *pts_ms,
                     double *decode_ms,
                     double *transfer_ms,
                     double *convert_ms,
                     char *err, size_t errlen);

/* 1 once the decoder has produced at least one NVTEGRA (hardware) frame. */
int galnx_nvdec_hw_used(GalnxNvdecCtx *ctx);

/* 1 if the frame returned by the last galnx_nvdec_next() call came from NVDEC. */
int galnx_nvdec_last_hw(GalnxNvdecCtx *ctx);

/* Raw NV12 planes of the last transferred hardware frame (or of the software
 * frame when the hardware is unavailable).  Valid until the next call.
 * Returns data[0] (luma) or NULL. */
const uint8_t *galnx_nvdec_nv12(GalnxNvdecCtx *ctx, int *y_stride, int *uv_stride,
                                int *w, int *h);

/* Display-order index of the last hardware frame (0 before the first one). */
int galnx_nvdec_frame_index(GalnxNvdecCtx *ctx);

/* Logging hook implemented by the caller (probe6 main.cpp): writes both to
 * stdout and to the SD-card report file. */
void galnx_nv6_log(const char *fmt, ...);

void galnx_nvdec_close(GalnxNvdecCtx *ctx);

#ifdef __cplusplus
}
#endif

#endif /* GALNX_NVDEC_H */
