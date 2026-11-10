/* GalNX NVDEC probe8 -- staged performance diagnosis (see README).
 *
 * probe7 proved NVDEC decodes on hardware but the user still saw frame drops
 * and slow motion.  probe8 measures each stage separately on the device so
 * the bottleneck is identified by numbers, not by how playback "feels":
 *
 *   A  verify     stage 0  strict: every frame must be AV_PIX_FMT_NVTEGRA
 *   B  decode600  stage 0  600 frames, decode-only throughput + percentiles
 *   C1 transfer   stage 1  + av_hwframe_transfer_data
 *   C2 rgba       stage 2  + NV12 -> RGBA (probe7 pipeline), BMP sanity dump
 *   C3 upload     stage 2  + SDL_UpdateTexture only
 *   C4 render     stage 2  + SDL render/present (no vsync)
 *   C5 pace       stage 2  + 59.94 fps frame pacing (sleep to the frame clock)
 *
 * Stages run in order against the same file, each with a fresh decoder, and
 * every stage reports mean/P50/P95/P99 of its own cost plus the wall clock.
 * Set sdmc:/probe8-allow-soft.txt to disable strict mode (emulator smoke).
 */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include <switch.h>
#include <SDL.h>

extern "C" {
#include <libavutil/log.h>
}

#include "galnx_nvdec.h"

static FILE *g_log = NULL;
static bool g_quit = false;
static double g_last_flush = 0.0;
static int g_ffmsg = 0;   /* ffmpeg log messages seen (probe8 printed+flushed all of them) */
static int g_pcv_ok = 0;  /* pcvGetClockRate works? (the emulator HLE has no PCV) */

static double now_ms(void) {
    return (double)svcGetSystemTick() / 19200.0;
}

static void logf_impl(const char *fmt, va_list ap) {
    va_list aq;
    va_copy(aq, ap);
    vprintf(fmt, aq);
    va_end(aq);
    if (g_log) {
        va_list ar;
        va_copy(ar, ap);
        vfprintf(g_log, fmt, ar);
        va_end(ar);
        /* probe9: no per-line fflush().  probe8 did fflush(g_log) for every
         * line, i.e. 61-72 SD-card writes per decoded frame. */
        if (now_ms() - g_last_flush > 2000.0) {
            fflush(g_log);
            g_last_flush = now_ms();
        }
    }
}

static void log_flush(void) {
    if (g_log) fflush(g_log);
    g_last_flush = now_ms();
}

static void logf(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    logf_impl(fmt, ap);
    va_end(ap);
}

/* Logging hook for the C decoder module (galnx_nvdec.c). */
extern "C" void galnx_nv6_log(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    logf_impl(fmt, ap);
    va_end(ap);
}

static void av_log_cb(void *avcl, int level, const char *fmt, va_list vl) {
    (void)avcl;
    (void)level;
    g_ffmsg++;
    if (g_ffmsg > 20) return;   /* probe9: count, do not log 70k lines */
    char buf[1024];
    vsnprintf(buf, sizeof(buf), fmt, vl);
    size_t n = strlen(buf);
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r')) buf[--n] = '\0';
    if (n > 0) logf("[ffmpeg] %s\n", buf);
}

static int write_bmp(const char *path, const uint8_t *rgba, int w, int h) {
    FILE *fp = fopen(path, "wb");
    if (!fp) return -1;
    const int row = w * 3;
    const int pad = (4 - (row % 4)) % 4;
    const uint32_t imgsize = (uint32_t)((size_t)(row + pad) * (size_t)h);
    uint8_t hdr[54] = {0};
    hdr[0] = 'B';
    hdr[1] = 'M';
    const uint32_t filesize = 54u + imgsize;
    const uint32_t off = 54u;
    const uint32_t hdrsize = 40u;
    const int32_t ww = w;
    const int32_t hh = h;
    const uint16_t planes = 1;
    const uint16_t bpp = 24;
    memcpy(&hdr[2], &filesize, 4);
    memcpy(&hdr[10], &off, 4);
    memcpy(&hdr[14], &hdrsize, 4);
    memcpy(&hdr[18], &ww, 4);
    memcpy(&hdr[22], &hh, 4);
    memcpy(&hdr[26], &planes, 2);
    memcpy(&hdr[28], &bpp, 2);
    memcpy(&hdr[34], &imgsize, 4);
    fwrite(hdr, 1, 54, fp);
    uint8_t *line = (uint8_t *)malloc((size_t)(row + pad));
    if (!line) {
        fclose(fp);
        return -1;
    }
    for (int y = h - 1; y >= 0; y--) {
        const uint8_t *src = rgba + (size_t)y * (size_t)w * 4u;
        for (int x = 0; x < w; x++) {
            line[x * 3 + 0] = src[x * 4 + 2];
            line[x * 3 + 1] = src[x * 4 + 1];
            line[x * 3 + 2] = src[x * 4 + 0];
        }
        for (int p = 0; p < pad; p++) line[row + p] = 0;
        fwrite(line, 1, (size_t)(row + pad), fp);
    }
    free(line);
    fclose(fp);
    return 0;
}

/* ---- samples ------------------------------------------------------------- */
struct Samples {
    std::vector<double> v;
    void add(double x) {
        if (v.size() < 4096) v.push_back(x);
    }
    double mean() const {
        if (v.empty()) return 0.0;
        double s = 0.0;
        for (double x : v) s += x;
        return s / (double)v.size();
    }
    double pct(double p) const {
        if (v.empty()) return 0.0;
        std::vector<double> s = v;
        std::sort(s.begin(), s.end());
        double idx = p * (double)(s.size() - 1);
        size_t i = (size_t)std::floor(idx);
        if (i + 1 < s.size()) {
            double f = idx - (double)i;
            return s[i] * (1.0 - f) + s[i + 1] * f;
        }
        return s[i];
    }
    std::string line(const char *name) const {
        char buf[192];
        snprintf(buf, sizeof(buf), "  %-8s mean=%.2f p50=%.2f p95=%.2f p99=%.2f max=%.2f ms%s",
                 name, mean(), pct(0.50), pct(0.95), pct(0.99), pct(1.0), v.empty() ? " (none)" : "");
        return std::string(buf);
    }
};

struct StageResult {
    int opened = 0;
    int rendered = 0;
    int hw_frames = 0;
    int rc = -1;
    double wall_ms = 0.0;
    GalnxNvdecStats stats;
    Samples next, dec, xfer, conv, upload, render, pace;
    Samples readms, recvms;
    int read_calls = 0, recv_calls = 0, eagain = 0;
};

static void pump_events(void) {
    SDL_Event e;
    while (SDL_PollEvent(&e)) {
        if (e.type == SDL_QUIT) g_quit = true;
        if (e.type == SDL_KEYDOWN) {
            const SDL_Scancode sc = e.key.keysym.scancode;
            if (sc == SDL_SCANCODE_ESCAPE || sc == SDL_SCANCODE_Q) g_quit = true;
        }
        if (e.type == SDL_JOYBUTTONDOWN && e.jbutton.button == 10) g_quit = true; /* PLUS */
    }
}

static void log_clocks(const char *tag) {
    static int warned = 0;
    u32 cpu = 0, emc = 0, gpu = 0;
    if (!g_pcv_ok) {
        if (!warned) {
            warned = 1;
            logf("[%s] clocks: unavailable (pcvGetClockRate rc=0x%08x); cpu/emc/gpu MHz "
                 "reporting disabled\n", tag, pcvGetClockRate(PcvModule_CpuBus, &cpu));
        }
        return;
    }
    const Result rc1 = pcvGetClockRate(PcvModule_CpuBus, &cpu);
    const Result rc2 = pcvGetClockRate(PcvModule_EMC, &emc);
    const Result rc3 = pcvGetClockRate(PcvModule_GPU, &gpu);
    logf("[%s] clocks: cpu=%.1f MHz (rc=0x%08x) emc=%.1f MHz (rc=0x%08x) gpu=%.1f MHz "
         "(rc=0x%08x)\n",
         tag, (double)cpu / 1e6, rc1, (double)emc / 1e6, rc2, (double)gpu / 1e6, rc3);
}

/* Sequential SD read benchmark -- is the storage stack the real bottleneck? */
static void io_bench(const char *tag, const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        logf("[io] %s: cannot open %s\n", tag, path);
        return;
    }
    const int chunk = 64 * 1024;
    const int iters = 256;
    unsigned char *buf = (unsigned char *)malloc((size_t)chunk);
    if (!buf) {
        fclose(f);
        return;
    }
    double t0 = now_ms();
    size_t total = 0;
    for (int i = 0; i < iters; i++) total += fread(buf, 1, (size_t)chunk, f);
    double dt = now_ms() - t0;
    logf("[io] %s: %d x 64KiB = %.1f MiB in %.1f ms = %.1f MiB/s (%.3f ms/read)\n", tag, iters,
         (double)total / 1048576.0, dt,
         dt > 0.0 ? (double)total / 1048576.0 / (dt / 1000.0) : 0.0, dt / (double)iters);
    fseek(f, 20 * 1024 * 1024, SEEK_SET);
    t0 = now_ms();
    total = 0;
    for (int i = 0; i < 1024; i++) total += fread(buf, 1, 4096, f);
    dt = now_ms() - t0;
    logf("[io] %s: 1024 x 4KiB mid-file = %.1f MiB in %.1f ms (%.3f ms/read)\n", tag,
         (double)total / 1048576.0, dt, dt / 1024.0);
    free(buf);
    fclose(f);
}

static int run_stage(const char *tag, const char *title, const char *path, int stage,
                     int max_frames, int do_upload, int do_render, int do_pace,
                     int save_bmp, SDL_Window *win, SDL_Renderer *ren, StageResult *res) {
    (void)win;
    char err[512] = {0};
    GalnxNvdecInfo info;
    memset(&info, 0, sizeof(info));

    logf("\n=== STAGE %s: %s | stage=%d frames<=%d upload=%d render=%d pace=%d ===\n", tag,
         title, stage, max_frames, do_upload, do_render, do_pace);
    const int ff0 = g_ffmsg;
    GalnxNvdecCtx *c = galnx_nvdec_open(path, &info, err, sizeof(err));
    if (!c) {
        logf("[%s] OPEN FAILED: %s\n", tag, err);
        res->rc = -1;
        return -1;
    }
    res->opened = 1;
    galnx_nvdec_set_stage(c, stage);
    logf("[%s] info: %dx%d codec=%s(%d) fps=%.3f duration=%lldms frames_hint=%lld hw_requested=%d\n",
         tag, info.width, info.height, info.codec_name, info.codec_id, info.fps,
         (long long)info.duration_ms, (long long)info.frames_hint, info.hw_requested);
    log_clocks(tag);

    SDL_Texture *tex = NULL;
    if (do_upload && ren) {
        tex = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STREAMING,
                                info.width > 0 ? info.width : 1920,
                                info.height > 0 ? info.height : 1080);
        logf("[%s] sdl texture=%p (%dx%d)\n", tag, (void *)tex, info.width, info.height);
    }

    const double t_stage = now_ms();
    int failed = 0;
    for (int i = 0; i < max_frames && !g_quit; i++) {
        const uint8_t *rgba = NULL;
        int w = 0, h = 0;
        int64_t pts = -1;
        double dec_ms = 0.0, xfer_ms = 0.0, conv_ms = 0.0;
        err[0] = '\0';

        const double t0 = now_ms();
        const int r = galnx_nvdec_next(c, &rgba, &w, &h, &pts, &dec_ms, &xfer_ms, &conv_ms,
                                       err, sizeof(err));
        const double next_ms = now_ms() - t0;
        if (r < 0) {
            logf("[%s] decode error after %d frames: %s\n", tag, res->rendered, err);
            if (strstr(err, "-1313558101") || strstr(err, "Unknown error"))
                logf("[%s] hint: AVERROR_UNKNOWN from nvtegra = NVDEC error_status/mbs_in_error "
                     "(libavcodec/nvtegra_decode.c:186)\n", tag);
            failed = 1;
            break;
        }
        if (r == 0) {
            logf("[%s] eos after %d frames\n", tag, res->rendered);
            res->rc = 0;
            break;
        }

        res->rendered++;
        const int idx_now = galnx_nvdec_frame_index(c);
        const int is_hw = galnx_nvdec_last_hw(c);
        if (is_hw) res->hw_frames++;

        res->next.add(next_ms);
        res->dec.add(dec_ms);
        res->xfer.add(xfer_ms);
        res->conv.add(conv_ms);
        GalnxNvdecTiming tm;
        galnx_nvdec_last_timing(c, &tm);
        res->readms.add(tm.read_ms);
        res->recvms.add(tm.recv_ms);
        res->read_calls += tm.read_calls;
        res->recv_calls += tm.recv_calls;
        res->eagain += tm.eagain;

        double upload_ms = 0.0, render_ms = 0.0;
        if (do_upload && tex && rgba && w > 0 && h > 0) {
            const double u0 = now_ms();
            SDL_UpdateTexture(tex, NULL, rgba, w * 4);
            upload_ms = now_ms() - u0;
        }
        if (do_render && tex) {
            const double r0 = now_ms();
            SDL_RenderClear(ren);
            SDL_RenderCopy(ren, tex, NULL, NULL);
            SDL_RenderPresent(ren);
            render_ms = now_ms() - r0;
        }
        res->upload.add(upload_ms);
        res->render.add(render_ms);

        if (res->rendered <= 2 || (res->rendered % 60) == 0) {
            logf("[%s] frame idx=%d %dx%d pts=%lldms next=%.2f dec=%.2f read=%.2f recv=%.2f "
                 "reads=%d recvs=%d eagain=%d xfer=%.2f conv=%.2f upload=%.2f render=%.2f hw=%d\n",
                 tag, idx_now, w, h, (long long)pts, next_ms, dec_ms, tm.read_ms, tm.recv_ms,
                 tm.read_calls, tm.recv_calls, tm.eagain, xfer_ms, conv_ms, upload_ms, render_ms,
                 is_hw);
        }
        if (res->rendered == 1 || (res->rendered % 300) == 0) log_clocks(tag);

        if (save_bmp && rgba && (idx_now == 1 || idx_now == 30)) {
            char bmp[256];
            snprintf(bmp, sizeof(bmp), "sdmc:/probe9-f%03d.bmp", idx_now);
            const int brc = write_bmp(bmp, rgba, w, h);
            logf("[%s] bmp: %s rc=%d\n", tag, bmp, brc);
        }

        if (do_pace) {
            const double target = t_stage + (double)res->rendered * (1000.0 / 59.94);
            const double now = now_ms();
            if (now < target) {
                const double wait_ms = target - now;
                res->pace.add(wait_ms);
                svcSleepThread((int64_t)(wait_ms * 1000000.0));
            } else {
                res->pace.add(0.0);
            }
        }
        pump_events();
    }
    /* rc = -1 only when a decode call failed; reaching the frame cap is success. */
    res->rc = failed ? -1 : 0;
    res->wall_ms = now_ms() - t_stage;

    galnx_nvdec_stats(c, &res->stats);
    const double fps = res->wall_ms > 0.0 ? 1000.0 * (double)res->rendered / res->wall_ms : 0.0;
    logf("[%s] STAGE RESULT: frames=%d hw=%d sw=%d wall=%.1f ms fps=%.2f rc=%d\n", tag,
         res->rendered, res->stats.frames_hw, res->stats.frames_sw, res->wall_ms, fps, res->rc);
    logf("%s\n", res->next.line("next").c_str());
    logf("%s\n", res->dec.line("decode").c_str());
    logf("%s\n", res->readms.line("read").c_str());
    logf("%s\n", res->recvms.line("recv").c_str());
    if (stage >= 1) logf("%s\n", res->xfer.line("transfer").c_str());
    if (stage >= 2) logf("%s\n", res->conv.line("rgba").c_str());
    if (do_upload) logf("%s\n", res->upload.line("upload").c_str());
    if (do_render) logf("%s\n", res->render.line("render").c_str());
    if (do_pace) logf("%s\n", res->pace.line("pace-sleep").c_str());
    logf("[%s] decoder stats: total=%d hw=%d sw=%d first_sw=%d strict_failed=%d pool=%d "
         "last_fmt=%s\n",
         tag, res->stats.frames_total, res->stats.frames_hw, res->stats.frames_sw,
         res->stats.first_sw_index, res->stats.strict_failed, res->stats.frame_pool_size,
         res->stats.last_format >= 0 ? "?" : "?");
    logf("[%s] calls: av_read_frame=%d avcodec_receive_frame=%d EAGAIN=%d ffmpeg_messages=%d\n",
         tag, res->read_calls, res->recv_calls, res->eagain, g_ffmsg - ff0);
    log_clocks(tag);
    log_flush();

    if (tex) SDL_DestroyTexture(tex);
    galnx_nvdec_close(c);
    return res->rc;
}

static int find_input(char *out, size_t n) {
    FILE *f = fopen("sdmc:/switch/nvdec-file.txt", "rb");
    if (f) {
        if (fgets(out, (int)n, f)) {
            size_t len = strlen(out);
            while (len > 0 && (out[len - 1] == '\n' || out[len - 1] == '\r')) out[--len] = '\0';
        }
        fclose(f);
        if (out[0]) return 1;
    }
    const char *cands[] = {"sdmc:/nvdec-poc.wmv", "sdmc:/nvdec-poc.mp4", "sdmc:/poc-1080p-vc1.wmv"};
    for (size_t i = 0; i < sizeof(cands) / sizeof(cands[0]); i++) {
        FILE *g = fopen(cands[i], "rb");
        if (g) {
            fclose(g);
            snprintf(out, n, "%s", cands[i]);
            return 1;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
    fsInitialize();
    fsdevMountSdmc();
    g_log = fopen("sdmc:/nvdec-probe9.txt", "wb");
    av_log_set_callback(av_log_cb);
    /* probe9: probe8 never raised the level, so FFmpeg emitted TRACE lines and every line
     * cost an SD-card fflush.  Silence the library and count messages instead. */
    av_log_set_level(AV_LOG_ERROR);
    const Result pcv_rc = pcvInitialize();
    g_pcv_ok = (R_SUCCEEDED(pcv_rc)) ? 1 : 0;

    logf("=== GalNX NVDEC probe9 (probe8 without the log bottleneck; read/recv split, "
         "clock + SD read baseline, H.264 cross-check) ===\n");
    logf("pcv: initialize rc=0x%08x\n", pcv_rc);
    logf("build: " __DATE__ " " __TIME__ "\n");
    logf("LOOP facts: single thread; galnx_nvdec_next() does send_packet + receive_frame "
         "(NVTEGRA waits its syncpt inside receive via post_process), then optional transfer "
         "and optional RGBA; SDL upload/render follow on the same thread; no frame queue, no "
         "decode-ahead; the frame is released before the next call; this probe has no "
         "MAX_DECODE_PER_TICK limit.\n");

    int allow_soft = 0;
    FILE *sf = fopen("sdmc:/probe8-allow-soft.txt", "rb");
    if (sf) {
        allow_soft = 1;
        fclose(sf);
    }
    /* 1 = strict hardware, -1 = force software for the emulator smoke path. */
    galnx_nvdec_require_hw(allow_soft ? -1 : 1);
    logf("hw mode: %s%d%s\n", allow_soft ? "force-software " : "strict hardware ",
         allow_soft ? -1 : 1,
         allow_soft ? " (sdmc:/probe8-allow-soft.txt present -> nvtegra disabled, "
                      "pipeline measured on software frames)"
                    : " (any software fallback is a failure)");

    SDL_Window *win = NULL;
    SDL_Renderer *ren = NULL;
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS | SDL_INIT_JOYSTICK) == 0) {
        for (int i = 0; i < SDL_NumJoysticks(); i++) SDL_JoystickOpen(i);
        win = SDL_CreateWindow("nvdec-probe9", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                               1280, 720, SDL_WINDOW_SHOWN);
        if (win) {
            /* no PRESENTVSYNC: measure the real render cost, not the vblank wait */
            ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED);
            if (!ren) ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_SOFTWARE);
        }
        logf("sdl: window=%p renderer=%p driver=%s (vsync off)\n", (void *)win, (void *)ren,
             ren ? SDL_GetCurrentVideoDriver() : "none");
    } else {
        logf("sdl: init failed: %s\n", SDL_GetError());
    }

    char path[512] = {0};
    StageResult st[8];
    for (int i = 0; i < 8; i++) st[i] = StageResult();
    if (!find_input(path, sizeof(path))) {
        logf("no movie found: put the sample at sdmc:/nvdec-poc.wmv "
             "(or list it in sdmc:/switch/nvdec-file.txt)\n");
    } else {
        logf("input: %s\n", path);
        io_bench("before", path);
        run_stage("A-verify", "strict hardware frame verification", path, 0, 60, 0, 0, 0, 0,
                  win, ren, &st[0]);
        const bool strict_ok = st[0].rc == 0 && st[0].rendered > 0 &&
                               st[0].stats.frames_hw == st[0].rendered &&
                               st[0].stats.frames_sw == 0 && st[0].stats.strict_failed == 0;
        logf("\nHARDWARE PROOF: %s (frames=%d hw=%d sw=%d strict_failed=%d pool=%d)\n",
             allow_soft ? "SKIPPED (force-software smoke run; only a real device can prove NVDEC)"
                        : (strict_ok ? "PASS - every decoded frame is NVTEGRA" : "FAIL"),
             st[0].rendered,
             st[0].stats.frames_hw, st[0].stats.frames_sw, st[0].stats.strict_failed,
             st[0].stats.frame_pool_size);

        if (strict_ok || allow_soft) {
            run_stage("B-decode600", "decode-only throughput (600 frames)", path, 0, 600, 0, 0,
                      0, 0, win, ren, &st[1]);
            io_bench("after-B", path);
            {
                /* cross-check: is VC-1 special?  H.264 is the codec the Switch ecosystem uses. */
                const char *h264 = "sdmc:/nvdec-poc.mp4";
                FILE *hf = fopen(h264, "rb");
                if (hf) {
                    fclose(hf);
                    run_stage("B2-h264", "decode-only throughput, H.264 cross-check (200 frames)",
                              h264, 0, 200, 0, 0, 0, 0, win, ren, &st[7]);
                } else {
                    logf("B2-h264 skipped: %s not found\n", h264);
                }
            }
            run_stage("C1-transfer", "+ av_hwframe_transfer_data", path, 1, 120, 0, 0, 0, 0,
                      win, ren, &st[2]);
            run_stage("C2-rgba", "+ NV12 -> RGBA (probe7 pipeline)", path, 2, 60, 0, 0, 0, 1,
                      win, ren, &st[3]);
            run_stage("C3-upload", "+ SDL_UpdateTexture", path, 2, 60, 1, 0, 0, 0, win, ren,
                      &st[4]);
            run_stage("C4-render", "+ SDL render/present (no vsync)", path, 2, 60, 1, 1, 0, 0,
                      win, ren, &st[5]);
            run_stage("C5-pace", "+ 59.94 fps frame pacing", path, 2, 120, 1, 1, 1, 0, win,
                      ren, &st[6]);
        } else {
            logf("stages B/C skipped: strict hardware proof failed, the rest of the pipeline "
                 "would all fail the same way\n");
        }
    }

    /* ---- overall summary ------------------------------------------------- */
    logf("\n=== PROBE9 SUMMARY ===\n");
    if (st[1].rendered > 0) {
        const double fps = 1000.0 * (double)st[1].rendered / st[1].wall_ms;
        logf("decode-only : %d frames in %.1f ms = %.2f fps (dec mean=%.2f p95=%.2f ms)\n",
             st[1].rendered, st[1].wall_ms, fps, st[1].dec.mean(), st[1].dec.pct(0.95));
    }
    if (st[7].rendered > 0) {
        logf("h264 cross  : %d frames in %.1f ms = %.2f fps (dec mean=%.2f p95=%.2f ms)\n",
             st[7].rendered, st[7].wall_ms, 1000.0 * (double)st[7].rendered / st[7].wall_ms,
             st[7].dec.mean(), st[7].dec.pct(0.95));
    }
    if (st[3].rendered > 0) {
        logf("rgba stage  : conv mean=%.2f ms, next mean=%.2f ms -> %.2f fps\n",
             st[3].conv.mean(), st[3].next.mean(),
             1000.0 * (double)st[3].rendered / st[3].wall_ms);
    }
    if (st[4].rendered > 0)
        logf("upload stage: upload mean=%.2f ms -> %.2f fps\n", st[4].upload.mean(),
             1000.0 * (double)st[4].rendered / st[4].wall_ms);
    if (st[5].rendered > 0)
        logf("render stage: render mean=%.2f ms -> %.2f fps\n", st[5].render.mean(),
             1000.0 * (double)st[5].rendered / st[5].wall_ms);
    if (st[6].rendered > 0)
        logf("paced stage : %d frames in %.1f ms -> %.2f fps (pace sleeps mean=%.2f ms)\n",
             st[6].rendered, st[6].wall_ms,
             1000.0 * (double)st[6].rendered / st[6].wall_ms, st[6].pace.mean());

    const int proof = (st[0].rendered > 0 && st[0].stats.frames_hw == st[0].rendered &&
                       st[0].stats.frames_sw == 0 && st[0].stats.strict_failed == 0);
    logf("PROBE9 verdict: hardware_decode=%s decode_only_fps=%.2f rgba_fps=%.2f render_fps=%.2f "
         "paced_fps=%.2f h264_fps=%.2f\n",
         proof ? "CONFIRMED" : "NOT-PROVEN",
         st[1].wall_ms > 0 ? 1000.0 * (double)st[1].rendered / st[1].wall_ms : 0.0,
         st[3].wall_ms > 0 ? 1000.0 * (double)st[3].rendered / st[3].wall_ms : 0.0,
         st[5].wall_ms > 0 ? 1000.0 * (double)st[5].rendered / st[5].wall_ms : 0.0,
         st[6].wall_ms > 0 ? 1000.0 * (double)st[6].rendered / st[6].wall_ms : 0.0,
         st[7].wall_ms > 0 ? 1000.0 * (double)st[7].rendered / st[7].wall_ms : 0.0);
    if (!proof)
        logf("next step: strict hardware proof failed - inspect the get_format/strict lines "
             "above before touching the pipeline\n");
    else if (st[3].conv.mean() > 10.0 && st[3].conv.mean() > 4.0 * st[2].xfer.mean())
        logf("next step: CPU NV12->RGBA dominates (conv %.2f ms vs transfer %.2f ms) - replace "
             "it with a GLES YUV shader and/or bind the hardware surface without a CPU copy\n",
             st[3].conv.mean(), st[2].xfer.mean());
    else
        logf("next step: inspect the per-stage table; the slowest stage is the target\n");

    logf("files on sdmc: nvdec-probe9.txt / probe9-f001.bmp / probe9-f030.bmp\n");
    logf("=== DONE ===\n");
    log_flush();

    SDL_Delay(300);
    if (ren) SDL_DestroyRenderer(ren);
    if (win) SDL_DestroyWindow(win);
    SDL_Quit();

    if (g_log) {
        fclose(g_log);
        g_log = NULL;
    }
    fsdevUnmountAll();
    fsExit();
    return 0;
}
