/* GalNX NVDEC probe4 -- software decoded reference frames (implementation). */
#include "galnx_swref.h"

#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <switch.h>

#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avstring.h>
#include <libavutil/error.h>
#include <libavutil/frame.h>
#include <libavutil/pixdesc.h>

static double now_ms(void) {
    return (double)svcGetSystemTick() / 19200.0;
}

static void set_err(char *err, size_t errlen, const char *fmt, ...) {
    if (!err || errlen == 0) return;
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(err, errlen, fmt, ap);
    va_end(ap);
}

/* Copy a decoded frame into a malloc'ed, tightly packed planar YUV420P buffer. */
static int frame_to_planar420(const AVFrame *f, uint8_t **out, int *ow, int *oh,
                              char *err, size_t errlen) {
    const int w = f->width;
    const int h = f->height;
    if (w <= 0 || h <= 0) {
        set_err(err, errlen, "invalid frame size %dx%d", w, h);
        return -1;
    }
    int nv12;
    if (f->format == AV_PIX_FMT_NV12) {
        nv12 = 1;
    } else if (f->format == AV_PIX_FMT_YUV420P || f->format == AV_PIX_FMT_YUVJ420P) {
        nv12 = 0;
    } else {
        set_err(err, errlen, "unsupported software pixel format %s",
                av_get_pix_fmt_name(f->format) ? av_get_pix_fmt_name(f->format) : "?");
        return -1;
    }
    const int cw = w / 2;
    const int ch = h / 2;
    const size_t yn = (size_t)w * (size_t)h;
    const size_t cn = (size_t)cw * (size_t)ch;
    uint8_t *buf = (uint8_t *)malloc(yn + 2u * cn);
    if (!buf) {
        set_err(err, errlen, "out of memory for %dx%d reference frame", w, h);
        return -1;
    }
    for (int y = 0; y < h; y++) {
        memcpy(buf + (size_t)y * w, f->data[0] + (size_t)y * f->linesize[0], (size_t)w);
    }
    uint8_t *up = buf + yn;
    uint8_t *vp = up + cn;
    if (nv12) {
        for (int y = 0; y < ch; y++) {
            const uint8_t *row = f->data[1] + (size_t)y * f->linesize[1];
            for (int x = 0; x < cw; x++) {
                up[(size_t)y * cw + x] = row[x * 2];
                vp[(size_t)y * cw + x] = row[x * 2 + 1];
            }
        }
    } else {
        for (int y = 0; y < ch; y++) {
            memcpy(up + (size_t)y * cw, f->data[1] + (size_t)y * f->linesize[1], (size_t)cw);
            memcpy(vp + (size_t)y * cw, f->data[2] + (size_t)y * f->linesize[2], (size_t)cw);
        }
    }
    *out = buf;
    *ow = w;
    *oh = h;
    return 0;
}

int galnx_swref_collect(const char *path, const int *idxs, int n,
                        uint8_t **out_yuv, int *out_w, int *out_h,
                        double *out_ms, char *err, size_t errlen) {
    if (err && errlen) err[0] = '\0';
    if (out_w) *out_w = 0;
    if (out_h) *out_h = 0;
    if (!path || !path[0] || n <= 0) {
        set_err(err, errlen, "invalid arguments");
        return -1;
    }

    char url[1024];
    if (av_strstart(path, "file:", NULL)) {
        snprintf(url, sizeof(url), "%s", path);
    } else {
        snprintf(url, sizeof(url), "file:%s", path);
    }

    AVFormatContext *fmt = NULL;
    AVCodecContext *dec = NULL;
    AVPacket *pkt = NULL;
    AVFrame *frame = NULL;
    int found = 0;
    int rc = -1;

    if (avformat_open_input(&fmt, url, NULL, NULL) < 0) {
        set_err(err, errlen, "software decode: avformat_open_input failed");
        goto done;
    }
    if (avformat_find_stream_info(fmt, NULL) < 0) {
        set_err(err, errlen, "software decode: avformat_find_stream_info failed");
        goto done;
    }
    const int si = av_find_best_stream(fmt, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
    if (si < 0) {
        set_err(err, errlen, "software decode: no video stream");
        goto done;
    }
    const AVCodec *codec = avcodec_find_decoder(fmt->streams[si]->codecpar->codec_id);
    if (!codec) {
        set_err(err, errlen, "software decode: no decoder");
        goto done;
    }
    dec = avcodec_alloc_context3(codec);
    if (!dec) {
        set_err(err, errlen, "software decode: avcodec_alloc_context3 failed");
        goto done;
    }
    if (avcodec_parameters_to_context(dec, fmt->streams[si]->codecpar) < 0) {
        set_err(err, errlen, "software decode: avcodec_parameters_to_context failed");
        goto done;
    }
    dec->thread_count = 0;
    if (avcodec_open2(dec, codec, NULL) < 0) {
        set_err(err, errlen, "software decode: avcodec_open2 failed");
        goto done;
    }
    pkt = av_packet_alloc();
    frame = av_frame_alloc();
    if (!pkt || !frame) {
        set_err(err, errlen, "software decode: out of memory");
        goto done;
    }

    const double t0 = now_ms();
    int counter = 0;
    int eof = 0;
    while (!eof) {
        int ret = avcodec_receive_frame(dec, frame);
        if (ret == 0) {
            counter++; /* 1-based display order */
            for (int k = 0; k < n; k++) {
                if (out_yuv[k] || idxs[k] != counter) continue;
                if (frame_to_planar420(frame, &out_yuv[k], out_w, out_h, err, errlen) == 0) {
                    found++;
                }
            }
            av_frame_unref(frame);
            if (found == n) break;
            continue;
        }
        if (ret == AVERROR_EOF) break;
        if (ret != AVERROR(EAGAIN)) {
            set_err(err, errlen, "software decode: avcodec_receive_frame %d", ret);
            break;
        }
        int rr = av_read_frame(fmt, pkt);
        if (rr == AVERROR_EOF) {
            avcodec_send_packet(dec, NULL);
            eof = 1;
            continue;
        }
        if (rr < 0) {
            set_err(err, errlen, "software decode: av_read_frame %d", rr);
            break;
        }
        if (pkt->stream_index == si) {
            int sr = avcodec_send_packet(dec, pkt);
            if (sr < 0 && sr != AVERROR(EAGAIN)) {
                av_packet_unref(pkt);
                set_err(err, errlen, "software decode: avcodec_send_packet %d", sr);
                break;
            }
        }
        av_packet_unref(pkt);
    }
    if (out_ms) *out_ms = now_ms() - t0;
    rc = found;

done:
    if (pkt) av_packet_free(&pkt);
    if (frame) av_frame_free(&frame);
    if (dec) avcodec_free_context(&dec);
    if (fmt) avformat_close_input(&fmt);
    return rc;
}
