/* GalNX NVDEC movie decode module -- probe8 (diagnostics build).
 *
 * probe7 proved on hardware that NVDEC really decodes (every VC-1 and H.264
 * frame came out as AV_PIX_FMT_NVTEGRA).  probe8 adds the instrumentation the
 * outside reviewer asked for, so one device run can separate "NVDEC decode
 * throughput" from "post-processing cost":
 *
 *  - strict hardware mode: get_format() must offer NVTEGRA, otherwise the
 *    decoder fails instead of silently falling back to yuv420p;
 *  - stage control: 0 = decode only, 1 = + av_hwframe_transfer_data,
 *    2 = + NV12/YUV420P -> RGBA (the probe7 behaviour);
 *  - frame format statistics (how many frames were NVTEGRA vs software).
 *
 * Hardware decode goes through FFmpeg's nvtegra hwaccel, the same path
 * SwitchWave uses.  Only avctx->hw_device_ctx is set: the decoder derives
 * hw_frames_ctx itself in ff_nvtegra_decode_init() (probe6 failed because it
 * set the frames context by hand -- ff_get_format() unrefs it).
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
    int hw_requested;
    int hw_used;
    double fps;
    int64_t duration_ms;
    int64_t frames_hint;
} GalnxNvdecInfo;

typedef struct GalnxNvdecStats {
    int frames_total;      /* frames received from the decoder */
    int frames_hw;         /* frames whose format was AV_PIX_FMT_NVTEGRA */
    int frames_sw;         /* frames with any other (software) format */
    int first_sw_index;    /* 1-based index of the first software frame, 0 = none */
    int strict_failed;     /* 1 = strict mode, but get_format() had no NVTEGRA */
    int hw_enabled;        /* 1 = an nvtegra device context was created */
    int frame_pool_size;   /* derived hw frame pool size, 0 = unknown */
    int last_format;       /* AVPixelFormat of the last received frame */
} GalnxNvdecStats;

/* Fine-grained timing of one galnx_nvdec_next() call (probe9).  probe8 could
 * only report "next" vs "decode", which left ~83 ms per frame unexplained. */
typedef struct GalnxNvdecTiming {
    double read_ms;   /* total time inside av_read_frame() during that call */
    double recv_ms;   /* total time inside avcodec_receive_frame() during that call */
    int read_calls;   /* av_read_frame() calls (video + skipped audio packets) */
    int recv_calls;   /* avcodec_receive_frame() calls (incl. the EAGAIN polls) */
    int eagain;       /* how many of those returns were EAGAIN */
} GalnxNvdecTiming;

/* Strict hardware mode.  Must be called before galnx_nvdec_open().
 * When on: if the decoder does not offer AV_PIX_FMT_NVTEGRA in get_format(),
 * or if any received frame is not NVTEGRA, decoding fails with an error.
 * This is the "debug-only hard-decode mode" -- no silent software fallback. */
void galnx_nvdec_require_hw(int on);

/* How far galnx_nvdec_next() goes after receiving a frame:
 *   0 = decode only           (no transfer, no conversion; rgba = NULL)
 *   1 = + hardware transfer   (NV12 in system memory; rgba = NULL)
 *   2 = + YUV -> RGBA         (default, probe7 behaviour) */
void galnx_nvdec_set_stage(GalnxNvdecCtx *ctx, int stage);

/* Open a movie file ("file:" is added internally).  Returns NULL on failure. */
GalnxNvdecCtx *galnx_nvdec_open(const char *path, GalnxNvdecInfo *info,
                                char *err, size_t errlen);

/* Decode the next video frame.
 * Returns 1 = new frame, 0 = end of stream, -1 = error (err filled).
 * rgba is NULL for stages 0 and 1.  The RGBA buffer is owned by ctx. */
int galnx_nvdec_next(GalnxNvdecCtx *ctx,
                     const uint8_t **rgba,
                     int *width, int *height,
                     int64_t *pts_ms,
                     double *decode_ms,
                     double *transfer_ms,
                     double *convert_ms,
                     char *err, size_t errlen);

void galnx_nvdec_stats(GalnxNvdecCtx *ctx, GalnxNvdecStats *out);

/* 1 once a NVTEGRA (hardware) frame has been received. */
int galnx_nvdec_hw_used(GalnxNvdecCtx *ctx);

/* 1 if the last received frame came from NVDEC. */
int galnx_nvdec_last_hw(GalnxNvdecCtx *ctx);

/* Raw NV12 planes of the last transferred frame (stage >= 1). */
const uint8_t *galnx_nvdec_nv12(GalnxNvdecCtx *ctx, int *y_stride, int *uv_stride,
                                int *w, int *h);

/* Display-order index of the last received frame. */
int galnx_nvdec_frame_index(GalnxNvdecCtx *ctx);

/* Timing breakdown of the last galnx_nvdec_next() call. */
void galnx_nvdec_last_timing(GalnxNvdecCtx *ctx, GalnxNvdecTiming *out);

/* Logging hook implemented by the caller (probe8 main.cpp). */
void galnx_nv6_log(const char *fmt, ...);

void galnx_nvdec_close(GalnxNvdecCtx *ctx);

#ifdef __cplusplus
}
#endif

#endif /* GALNX_NVDEC_H */
