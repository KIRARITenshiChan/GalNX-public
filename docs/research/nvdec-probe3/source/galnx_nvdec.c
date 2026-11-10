/* GalNX NVDEC movie decode module -- implementation.
 *
 * Design notes (see docs/builds/041 for the long version):
 *  - The Switch exposes NVDEC through /dev/nvhost-nvdec; averne/envideo wraps
 *    it and averne/FFmpeg's envideo backend plugs it into avcodec as
 *    AV_HWDEVICE_TYPE_ENVIDEO / AV_PIX_FMT_ENVIDEO.
 *  - av_hwframe_transfer_data() only converts block-linear tiling <-> pitch
 *    (no pixel format conversion), so we always ask for a plain YUV420P/NV12
 *    frame and do YUV->RGBA ourselves (BT.601/709, limited/full range).
 *  - Video packet pts is the only reliable timestamp for this ASF/VC-1 file
 *    (frame->pts can come out as AV_NOPTS_VALUE), so we remember the last
 *    packet ts and use it when needed.
 */
#include "galnx_nvdec.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <switch.h>

#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avstring.h>
#include <libavutil/avutil.h>
#include <libavutil/error.h>
#include <libavutil/hwcontext.h>
#include <libavutil/imgutils.h>
#include <libavutil/pixdesc.h>

struct GalnxNvdecCtx {
    AVFormatContext *fmt;
    AVCodecContext *dec;
    AVBufferRef *hwdev;
    AVFrame *frame;
    AVFrame *sw;
    AVPacket *pkt;
    int stream_index;
    int hw_used;
    int last_hw;
    int drain_sent;
    int64_t pending_ts;
    AVRational tb;
    uint8_t *rgba;
    size_t rgba_cap;
    int out_w, out_h;
    int64_t out_pts_ms;
    double t_send;
};

static double now_ms(void) {
    /* 19.2 MHz system tick counter (same clock used by libnx/armTicksToNs). */
    return (double)svcGetSystemTick() / 19200.0;
}

static void set_err(char *err, size_t errlen, const char *fmt, ...) {
    if (!err || errlen == 0) return;
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(err, errlen, fmt, ap);
    va_end(ap);
}

static void set_av_err(char *err, size_t errlen, const char *what, int ret) {
    char buf[AV_ERROR_MAX_STRING_SIZE] = {0};
    av_strerror(ret, buf, sizeof(buf));
    set_err(err, errlen, "%s: %s (%d / 0x%08x)", what, buf, ret, (unsigned)ret);
}

static inline uint8_t clamp_u8(int v) {
    if (v < 0) return 0;
    if (v > 255) return 255;
    return (uint8_t)v;
}

static int use_bt709(const AVFrame *f) {
    if (f->colorspace == AVCOL_SPC_BT709) return 1;
    if (f->colorspace != AVCOL_SPC_UNSPECIFIED && f->colorspace != AVCOL_SPC_RESERVED)
        return 0;
    return (f->width >= 1280) ? 1 : 0;
}

/* Convert one YUV420P / NV12 frame into packed RGBA8888. */
static int to_rgba(GalnxNvdecCtx *c, const AVFrame *f, char *err, size_t errlen) {
    const int w = f->width;
    const int h = f->height;
    const enum AVPixelFormat pf = f->format;

    int nv12;
    if (pf == AV_PIX_FMT_NV12) {
        nv12 = 1;
    } else if (pf == AV_PIX_FMT_YUV420P || pf == AV_PIX_FMT_YUVJ420P) {
        nv12 = 0;
    } else {
        set_err(err, errlen, "unsupported sw pixel format %s (%d)",
                av_get_pix_fmt_name(pf) ? av_get_pix_fmt_name(pf) : "?", (int)pf);
        return -1;
    }

    if (w <= 0 || h <= 0) {
        set_err(err, errlen, "invalid frame size %dx%d", w, h);
        return -1;
    }

    const size_t need = (size_t)w * (size_t)h * 4u;
    if (c->rgba_cap < need || !c->rgba) {
        av_freep(&c->rgba);
        c->rgba = av_malloc(need);
        if (!c->rgba) {
            c->rgba_cap = 0;
            set_err(err, errlen, "out of memory for RGBA buffer (%u bytes)", (unsigned)need);
            return -1;
        }
        c->rgba_cap = need;
    }

    const int bt709 = use_bt709(f);
    const int full = (f->color_range == AVCOL_RANGE_JPEG);

    const uint8_t *yp = f->data[0];
    const uint8_t *up;
    const uint8_t *vp;
    int ys = f->linesize[0];
    int us, vs;
    if (nv12) {
        up = f->data[1];
        vp = f->data[1] + 1;
        us = vs = f->linesize[1];
    } else {
        up = f->data[1];
        vp = f->data[2];
        us = f->linesize[1];
        vs = f->linesize[2];
    }
    if (!yp || !up || !vp) {
        set_err(err, errlen, "frame has no YUV planes (format=%d)", (int)pf);
        return -1;
    }

    for (int y = 0; y < h; y++) {
        const uint8_t *yrow = yp + (size_t)y * (size_t)ys;
        const uint8_t *urow = up + (size_t)(y >> 1) * (size_t)us;
        const uint8_t *vrow = vp + (size_t)(y >> 1) * (size_t)vs;
        uint8_t *orow = c->rgba + (size_t)y * (size_t)w * 4u;
        for (int x = 0; x < w; x++) {
            const int Y = yrow[x];
            const int ci = nv12 ? ((x >> 1) * 2) : (x >> 1);
            const int U = (int)urow[ci] - 128;
            const int V = (int)vrow[ci] - 128;
            int r, g, b;
            if (full) {
                r = Y + ((1436 * V) >> 10);
                g = Y - ((352 * U + 731 * V) >> 10);
                b = Y + ((1815 * U) >> 10);
            } else {
                const int C = (Y - 16) * 298;
                if (bt709) {
                    r = (C + 459 * V + 128) >> 8;
                    g = (C - 55 * U - 136 * V + 128) >> 8;
                    b = (C + 541 * U + 128) >> 8;
                } else {
                    r = (C + 409 * V + 128) >> 8;
                    g = (C - 100 * U - 208 * V + 128) >> 8;
                    b = (C + 516 * U + 128) >> 8;
                }
            }
            orow[x * 4 + 0] = clamp_u8(r);
            orow[x * 4 + 1] = clamp_u8(g);
            orow[x * 4 + 2] = clamp_u8(b);
            orow[x * 4 + 3] = 255;
        }
    }

    c->out_w = w;
    c->out_h = h;
    return 0;
}

static enum AVPixelFormat get_format_cb(AVCodecContext *ctx,
                                        const enum AVPixelFormat *pix_fmts) {
    GalnxNvdecCtx *c = (GalnxNvdecCtx *)ctx->opaque;

    /* Prefer the envideo hardware format, then whatever the decoder offers. */
    if (c->hwdev) {
        for (const enum AVPixelFormat *p = pix_fmts; *p != AV_PIX_FMT_NONE; p++) {
            if (*p == AV_PIX_FMT_ENVIDEO) return *p;
        }
    }
    for (const enum AVPixelFormat *p = pix_fmts; *p != AV_PIX_FMT_NONE; p++) {
        if (*p == AV_PIX_FMT_YUV420P || *p == AV_PIX_FMT_NV12) return *p;
    }
    return pix_fmts[0];
}

GalnxNvdecCtx *galnx_nvdec_open(const char *path, GalnxNvdecInfo *info,
                                char *err, size_t errlen) {
    if (err && errlen) err[0] = '\0';
    if (!path || !path[0]) {
        set_err(err, errlen, "empty input path");
        return NULL;
    }

    GalnxNvdecCtx *c = (GalnxNvdecCtx *)av_mallocz(sizeof(*c));
    if (!c) {
        set_err(err, errlen, "out of memory for context");
        return NULL;
    }
    c->pending_ts = AV_NOPTS_VALUE;
    c->stream_index = -1;

    /* libavformat on horizon has no is_dos_path(), so "sdmc:/x" is parsed as
     * protocol "sdmc:" -> AVERROR_PROTOCOL_NOT_FOUND.  Always use file:. */
    char url[1024];
    if (av_strstart(path, "file:", NULL)) {
        snprintf(url, sizeof(url), "%s", path);
    } else {
        snprintf(url, sizeof(url), "file:%s", path);
    }

    c->fmt = avformat_alloc_context();
    if (!c->fmt) {
        set_err(err, errlen, "avformat_alloc_context failed");
        galnx_nvdec_close(c);
        return NULL;
    }

    int ret = avformat_open_input(&c->fmt, url, NULL, NULL);
    if (ret < 0) {
        set_av_err(err, errlen, "avformat_open_input", ret);
        galnx_nvdec_close(c);
        return NULL;
    }

    ret = avformat_find_stream_info(c->fmt, NULL);
    if (ret < 0) {
        set_av_err(err, errlen, "avformat_find_stream_info", ret);
        galnx_nvdec_close(c);
        return NULL;
    }

    c->stream_index = av_find_best_stream(c->fmt, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
    if (c->stream_index < 0) {
        set_err(err, errlen, "no video stream (av_find_best_stream=%d)", c->stream_index);
        galnx_nvdec_close(c);
        return NULL;
    }

    AVStream *st = c->fmt->streams[c->stream_index];
    c->tb = st->time_base;

    const AVCodec *codec = avcodec_find_decoder(st->codecpar->codec_id);
    if (!codec) {
        set_err(err, errlen, "no decoder for codec_id=%d", (int)st->codecpar->codec_id);
        galnx_nvdec_close(c);
        return NULL;
    }

    c->dec = avcodec_alloc_context3(codec);
    if (!c->dec) {
        set_err(err, errlen, "avcodec_alloc_context3 failed");
        galnx_nvdec_close(c);
        return NULL;
    }
    ret = avcodec_parameters_to_context(c->dec, st->codecpar);
    if (ret < 0) {
        set_av_err(err, errlen, "avcodec_parameters_to_context", ret);
        galnx_nvdec_close(c);
        return NULL;
    }

    /* Try to bring up NVDEC through envideo; software fallback keeps the
     * module usable on the emulator and on any future codec change. */
    if (av_hwdevice_ctx_create(&c->hwdev, AV_HWDEVICE_TYPE_ENVIDEO, NULL, NULL, 0) >= 0 &&
        c->hwdev) {
        c->dec->hw_device_ctx = av_buffer_ref(c->hwdev);
        if (!c->dec->hw_device_ctx) {
            av_buffer_unref(&c->hwdev);
        }
    } else {
        av_buffer_unref(&c->hwdev);
        c->hwdev = NULL;
    }
    c->dec->opaque = c;
    c->dec->get_format = get_format_cb;
    c->dec->thread_count = 0; /* single threaded: NVDEC is async internally */

    ret = avcodec_open2(c->dec, codec, NULL);
    if (ret < 0) {
        set_av_err(err, errlen, "avcodec_open2", ret);
        galnx_nvdec_close(c);
        return NULL;
    }

    c->frame = av_frame_alloc();
    c->sw = av_frame_alloc();
    c->pkt = av_packet_alloc();
    if (!c->frame || !c->sw || !c->pkt) {
        set_err(err, errlen, "out of memory for frame/packet");
        galnx_nvdec_close(c);
        return NULL;
    }

    if (info) {
        memset(info, 0, sizeof(*info));
        info->width = c->dec->width > 0 ? c->dec->width : st->codecpar->width;
        info->height = c->dec->height > 0 ? c->dec->height : st->codecpar->height;
        info->codec_id = (int)st->codecpar->codec_id;
        snprintf(info->codec_name, sizeof(info->codec_name), "%s",
                 avcodec_get_name(st->codecpar->codec_id));
        const char *pfn = av_get_pix_fmt_name((enum AVPixelFormat)st->codecpar->format);
        snprintf(info->pix_fmt_name, sizeof(info->pix_fmt_name), "%s", pfn ? pfn : "?");
        AVRational fr = av_guess_frame_rate(c->fmt, st, NULL);
        info->fps = (fr.num > 0 && fr.den > 0) ? (double)fr.num / (double)fr.den : 0.0;
        info->duration_ms = (c->fmt->duration != AV_NOPTS_VALUE)
                                ? (int64_t)(c->fmt->duration / 1000)
                                : -1;
        info->frames_hint = (st->nb_frames > 0) ? (int64_t)st->nb_frames : -1;
        info->hw_requested = 1;
        info->hw_used = 0;
    }

    return c;
}

static int emit_frame(GalnxNvdecCtx *c,
                      const uint8_t **rgba,
                      int *width, int *height,
                      int64_t *pts_ms,
                      double *decode_ms,
                      double *transfer_ms,
                      double *convert_ms,
                      double recv_ms,
                      char *err, size_t errlen) {
    AVFrame *f = c->frame;
    const int hw = (f->format == AV_PIX_FMT_ENVIDEO);
    const AVFrame *src = f;
    double t0 = now_ms();

    *transfer_ms = 0.0;
    if (hw) {
        av_frame_unref(c->sw);
        int ret = av_hwframe_transfer_data(c->sw, f, 0);
        if (ret < 0) {
            set_av_err(err, errlen, "av_hwframe_transfer_data", ret);
            av_frame_unref(f);
            return -1;
        }
        src = c->sw;
        *transfer_ms = now_ms() - t0;
        c->hw_used = 1;
    }
    c->last_hw = hw;

    double t1 = now_ms();
    if (to_rgba(c, src, err, errlen) != 0) {
        av_frame_unref(f);
        return -1;
    }
    *convert_ms = now_ms() - t1;

    if (decode_ms) {
        *decode_ms = (c->t_send > 0.0) ? (recv_ms - c->t_send) : 0.0;
    }

    int64_t ts = f->best_effort_timestamp;
    if (ts == AV_NOPTS_VALUE) ts = f->pts;
    if (ts == AV_NOPTS_VALUE) ts = c->pending_ts;
    if (ts != AV_NOPTS_VALUE) {
        const AVRational ms_tb = {1, 1000};
        c->out_pts_ms = av_rescale_q(ts, c->tb, ms_tb);
    } else {
        c->out_pts_ms = -1;
    }

    *rgba = c->rgba;
    if (width) *width = c->out_w;
    if (height) *height = c->out_h;
    if (pts_ms) *pts_ms = c->out_pts_ms;

    av_frame_unref(f);
    return 1;
}

int galnx_nvdec_next(GalnxNvdecCtx *c,
                     const uint8_t **rgba,
                     int *width, int *height,
                     int64_t *pts_ms,
                     double *decode_ms,
                     double *transfer_ms,
                     double *convert_ms,
                     char *err, size_t errlen) {
    if (err && errlen) err[0] = '\0';
    if (!c || !c->dec || !c->frame) {
        set_err(err, errlen, "invalid decoder context");
        return -1;
    }

    for (;;) {
        int ret = avcodec_receive_frame(c->dec, c->frame);
        if (ret == 0) {
            const double recv_ms = now_ms();
            return emit_frame(c, rgba, width, height, pts_ms, decode_ms, transfer_ms,
                              convert_ms, recv_ms, err, errlen);
        }
        if (ret == AVERROR_EOF) return 0;
        if (ret != AVERROR(EAGAIN)) {
            set_av_err(err, errlen, "avcodec_receive_frame", ret);
            return -1;
        }
        if (c->drain_sent) return 0; /* flush finished */

        /* Feed exactly one packet of the video stream, then try receiving again. */
        for (;;) {
            int rr = av_read_frame(c->fmt, c->pkt);
            if (rr == AVERROR_EOF) {
                c->drain_sent = 1;
                avcodec_send_packet(c->dec, NULL);
                break;
            }
            if (rr < 0) {
                set_av_err(err, errlen, "av_read_frame", rr);
                return -1;
            }
            if (c->pkt->stream_index != c->stream_index) {
                av_packet_unref(c->pkt);
                continue;
            }
            if (c->pkt->pts != AV_NOPTS_VALUE) {
                c->pending_ts = c->pkt->pts;
            } else if (c->pkt->dts != AV_NOPTS_VALUE) {
                c->pending_ts = c->pkt->dts;
            }
            c->t_send = now_ms();
            int sr = avcodec_send_packet(c->dec, c->pkt);
            av_packet_unref(c->pkt);
            if (sr == AVERROR(EAGAIN)) break; /* drain what we have first */
            if (sr < 0) {
                set_av_err(err, errlen, "avcodec_send_packet", sr);
                return -1;
            }
            break;
        }
    }
}

int galnx_nvdec_hw_used(GalnxNvdecCtx *c) {
    return c ? c->hw_used : 0;
}

int galnx_nvdec_last_hw(GalnxNvdecCtx *c) {
    return c ? c->last_hw : 0;
}

void galnx_nvdec_close(GalnxNvdecCtx *c) {
    if (!c) return;
    if (c->sw) av_frame_free(&c->sw);
    if (c->frame) av_frame_free(&c->frame);
    if (c->pkt) av_packet_free(&c->pkt);
    if (c->dec) avcodec_free_context(&c->dec);
    if (c->fmt) avformat_close_input(&c->fmt);
    if (c->hwdev) av_buffer_unref(&c->hwdev);
    av_freep(&c->rgba);
    av_free(c);
}