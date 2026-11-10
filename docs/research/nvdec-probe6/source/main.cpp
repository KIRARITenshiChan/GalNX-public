/* GalNX NVDEC probe6 -- averne/FFmpeg nvtegra hwaccel on Switch.
 *
 * Single phase (the envideo question is settled: native envideo decode works,
 * FFmpeg-envideo VC-1 does not):
 *   1. software-decode two target frames with a plain FFmpeg build (reference)
 *   2. decode the movie through FFmpeg's nvtegra hwaccel
 *   3. for the target frames compare the transferred NV12 luma/chroma against
 *      the software reference (PSNR) and dump a BMP
 *
 * Success criteria on the console: hw=1 frames, transfer time in the tens of
 * milliseconds (not the 20 s seen with FFmpeg-envideo), high PSNR, sane BMP.
 */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <switch.h>
#include <SDL.h>

extern "C" {
#include <libavutil/log.h>
}

#include "galnx_nvdec.h"
#include "galnx_swref.h"

static FILE *g_log = NULL;

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
        fflush(g_log);
    }
    fflush(stdout);
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

static bool file_exists(const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) return false;
    fclose(fp);
    return true;
}

static bool find_input(int argc, char **argv, char *out, size_t outlen) {
    if (argc > 1 && argv[1] && argv[1][0] && file_exists(argv[1])) {
        snprintf(out, outlen, "%s", argv[1]);
        return true;
    }
    const char *override_path = "sdmc:/switch/nvdec-file.txt";
    if (file_exists(override_path)) {
        FILE *fp = fopen(override_path, "rb");
        if (fp) {
            char line[512] = {0};
            if (fgets(line, sizeof(line), fp)) {
                size_t n = strlen(line);
                while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = '\0';
                if (n > 0) {
                    fclose(fp);
                    snprintf(out, outlen, "%s", line);
                    return true;
                }
            }
            fclose(fp);
        }
    }
    static const char *candidates[] = {
        "sdmc:/nvdec-poc.wmv",
        "sdmc:/switch/nvdec-poc.wmv",
        "sdmc:/switch/nvdec/poc-1080p-vc1.wmv",
        "sdmc:/switch/rfvp/game/movie/01.wmv",
        "sdmc:/nvdec-poc.mp4",
    };
    for (size_t i = 0; i < sizeof(candidates) / sizeof(candidates[0]); i++) {
        if (file_exists(candidates[i])) {
            snprintf(out, outlen, "%s", candidates[i]);
            return true;
        }
    }
    return false;
}

static void pump_events(bool &quit) {
    SDL_Event ev;
    while (SDL_PollEvent(&ev)) {
        if (ev.type == SDL_QUIT) {
            quit = true;
        } else if (ev.type == SDL_KEYDOWN) {
            const SDL_Keycode k = ev.key.keysym.sym;
            if (k == SDLK_ESCAPE || k == SDLK_q || k == SDLK_PLUS || k == SDLK_KP_PLUS) quit = true;
        } else if (ev.type == SDL_JOYBUTTONDOWN) {
            if (ev.jbutton.button == 10) quit = true; /* PLUS */
        }
    }
}

/* PSNR between two planes with independent strides. */
static double psnr_plane(const uint8_t *a, int as, const uint8_t *b, int bs, int w, int h) {
    double se = 0.0;
    for (int y = 0; y < h; y++) {
        const uint8_t *ra = a + (size_t)y * (size_t)as;
        const uint8_t *rb = b + (size_t)y * (size_t)bs;
        for (int x = 0; x < w; x++) {
            const double d = (double)ra[x] - (double)rb[x];
            se += d * d;
        }
    }
    const double mse = se / ((double)w * (double)h);
    if (mse <= 0.0) return 99.0;
    return 10.0 * log10((255.0 * 255.0) / mse);
}

/* PSNR between planar YUV420P reference and NV12 hardware frame (interleaved UV). */
static void compare_frame(const char *tag,
                          const uint8_t *ref, int rw, int rh,
                          const uint8_t *nv12_y, int y_stride, int uv_stride, int hw_w, int hw_h,
                          double *out_y, double *out_u, double *out_v) {
    const int w = rw < hw_w ? rw : hw_w;
    const int h = rh < hw_h ? rh : hw_h;
    const uint8_t *refY = ref;
    const uint8_t *refU = ref + (size_t)rw * (size_t)rh;
    const uint8_t *refV = refU + (size_t)(rw / 2) * (size_t)(rh / 2);
    const uint8_t *hwU = nv12_y + (size_t)y_stride * (size_t)hw_h;
    const uint8_t *hwV = hwU + 1;

    const double py = psnr_plane(refY, rw, nv12_y, y_stride, w, h);
    /* Chroma: 4:2:0, one sample per 2x2 luma block. Compare R(U) and G(V). */
    const int cw = w / 2;
    const int ch = h / 2;
    double seu = 0.0, sev = 0.0;
    for (int y = 0; y < ch; y++) {
        const uint8_t *ru = refU + (size_t)y * (size_t)(rw / 2);
        const uint8_t *rv = refV + (size_t)y * (size_t)(rw / 2);
        const uint8_t *hu = hwU + (size_t)y * (size_t)uv_stride;
        for (int x = 0; x < cw; x++) {
            const double du = (double)ru[x] - (double)hu[x * 2 + 0];
            const double dv = (double)rv[x] - (double)hu[x * 2 + 1];
            seu += du * du;
            sev += dv * dv;
        }
    }
    const double mseu = (cw > 0 && ch > 0) ? seu / ((double)cw * (double)ch) : 0.0;
    const double msev = (cw > 0 && ch > 0) ? sev / ((double)cw * (double)ch) : 0.0;
    *out_y = psnr_plane(refY, rw, nv12_y, y_stride, w, h);
    *out_u = (mseu <= 0.0) ? 99.0 : 10.0 * log10((255.0 * 255.0) / mseu);
    *out_v = (msev <= 0.0) ? 99.0 : 10.0 * log10((255.0 * 255.0) / msev);

    logf("cmp %s: %dx%d vs hw %dx%d psnrY=%.2f psnrU=%.2f psnrV=%.2f (y=%.2f)\n", tag, rw, rh,
         hw_w, hw_h, *out_y, *out_u, *out_v, py);
}

static const int kTargetIdx[2] = {1, 30};
static const int kTargetCount = 2;

static int run_probe(int argc, char **argv) {
    char path[512] = {0};
    if (!find_input(argc, argv, path, sizeof(path))) {
        logf("input: no movie found (put poc-1080p-vc1.wmv at sdmc:/nvdec-poc.wmv)\n");
        return 2;
    }
    logf("input: %s\n", path);

    /* ---- step 1: software reference frames ---------------------------- */
    uint8_t *ref[2] = {NULL, NULL};
    int ref_w = 0, ref_h = 0;
    double sw_ms = 0.0;
    char err[512] = {0};
    const int got = galnx_swref_collect(path, kTargetIdx, kTargetCount, ref, &ref_w, &ref_h,
                                        &sw_ms, err, sizeof(err));
    logf("swref: found=%d %dx%d time=%.1f ms err=%s\n", got, ref_w, ref_h, sw_ms,
         err[0] ? err : "-");
    for (int i = 0; i < kTargetCount; i++) {
        logf("swref[%d]: target frame %d -> %s\n", i, kTargetIdx[i], ref[i] ? "ok" : "missing");
    }

    /* ---- step 2: open the decoder (nvtegra) ---------------------------- */
    GalnxNvdecInfo info;
    memset(&info, 0, sizeof(info));
    err[0] = '\0';
    GalnxNvdecCtx *dec = galnx_nvdec_open(path, &info, err, sizeof(err));
    if (!dec) {
        logf("open failed: %s\n", err);
        for (int i = 0; i < kTargetCount; i++) free(ref[i]);
        return 3;
    }
    logf("info: %dx%d codec=%s(%d) pix=%s fps=%.3f duration=%lld ms frames_hint=%lld hw_requested=%d\n",
         info.width, info.height, info.codec_name, info.codec_id, info.pix_fmt_name, info.fps,
         (long long)info.duration_ms, (long long)info.frames_hint, info.hw_requested);

    /* ---- SDL window (optional: the probe still works headless) -------- */
    SDL_Window *win = NULL;
    SDL_Renderer *ren = NULL;
    SDL_Texture *tex = NULL;
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS | SDL_INIT_JOYSTICK) == 0) {
        for (int i = 0; i < SDL_NumJoysticks(); i++) SDL_JoystickOpen(i);
        win = SDL_CreateWindow("nvdec-probe6", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                               1280, 720, SDL_WINDOW_SHOWN);
        if (win) {
            ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
            if (!ren) ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_SOFTWARE);
        }
        if (ren) {
            tex = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STREAMING,
                                    info.width > 0 ? info.width : 1920,
                                    info.height > 0 ? info.height : 1080);
        }
        logf("sdl: window=%p renderer=%p texture=%p\n", (void *)win, (void *)ren, (void *)tex);
    } else {
        logf("sdl: init failed: %s (headless probe)\n", SDL_GetError());
    }

    /* ---- step 3: hardware decode loop --------------------------------- */
    int rendered = 0;
    int hw_frames = 0;
    bool quit = false;
    double sum_dec = 0.0, sum_xfer = 0.0, sum_conv = 0.0;
    int target_hits = 0;
    const double t_start = now_ms();
    for (int iter = 0; iter < 2000 && !quit; iter++) {
        const uint8_t *rgba = NULL;
        int w = 0, h = 0;
        int64_t pts = -1;
        double dec_ms = 0.0, xfer_ms = 0.0, conv_ms = 0.0;
        err[0] = '\0';
        const int r = galnx_nvdec_next(dec, &rgba, &w, &h, &pts, &dec_ms, &xfer_ms, &conv_ms,
                                       err, sizeof(err));
        if (r < 0) {
            logf("decode error: %s\n", err);
            break;
        }
        if (r == 0) {
            logf("eos reached\n");
            break;
        }
        const int idx_now = galnx_nvdec_frame_index(dec);
        const int is_hw = galnx_nvdec_last_hw(dec);
        rendered++;
        sum_dec += dec_ms;
        sum_xfer += xfer_ms;
        sum_conv += conv_ms;
        if (is_hw) hw_frames++;
        logf("frame idx=%d %dx%d pts=%lldms dec=%.2f xfer=%.2f conv=%.2f hw=%d\n", idx_now, w, h,
             (long long)pts, dec_ms, xfer_ms, conv_ms, is_hw);
        if (tex && ren && rgba && w > 0 && h > 0) {
            SDL_UpdateTexture(tex, NULL, rgba, w * 4);
            SDL_RenderClear(ren);
            SDL_RenderCopy(ren, tex, NULL, NULL);
            SDL_RenderPresent(ren);
        }
        for (int k = 0; k < kTargetCount; k++) {
            if (kTargetIdx[k] != idx_now) continue;
            target_hits++;
            if (rgba) {
                char bmp[256];
                snprintf(bmp, sizeof(bmp), "sdmc:/probe6-f%03d.bmp", idx_now);
                const int brc = write_bmp(bmp, rgba, w, h);
                logf("bmp: %s rc=%d\n", bmp, brc);
            }
            int y_stride = 0, uv_stride = 0, hw_w = 0, hw_h = 0;
            const uint8_t *nv12_y = galnx_nvdec_nv12(dec, &y_stride, &uv_stride, &hw_w, &hw_h);
            if (ref[k] && nv12_y && hw_w > 0 && hw_h > 0) {
                double py = 0.0, pu = 0.0, pv = 0.0;
                char tag[32];
                snprintf(tag, sizeof(tag), "f%03d", idx_now);
                compare_frame(tag, ref[k], ref_w, ref_h, nv12_y, y_stride, uv_stride, hw_w, hw_h,
                              &py, &pu, &pv);
            } else {
                logf("cmp f%03d: skipped (ref=%p nv12=%p hw=%dx%d)\n", idx_now, (void *)ref[k],
                     (void *)nv12_y, hw_w, hw_h);
            }
        }
        pump_events(quit);
        if (rendered >= 120 || idx_now >= 120) break;
    }
    const double elapsed = now_ms() - t_start;

    /* ---- step 4: report ----------------------------------------------- */
    logf("SUMMARY: rendered=%d hw_frames=%d targets=%d idx=%d elapsed=%.1f ms\n", rendered,
         hw_frames, target_hits, galnx_nvdec_frame_index(dec), elapsed);
    if (rendered > 0) {
        logf("avg: dec=%.2f xfer=%.2f conv=%.2f ms/frame, %.2f fps\n", sum_dec / rendered,
             sum_xfer / rendered, sum_conv / rendered, 1000.0 * rendered / elapsed);
    }
    logf("PROBE6 verdict: hw=%s\n", hw_frames > 0 ? "HARDWARE" : "SOFTWARE-ONLY");

    SDL_Delay(300);
    if (tex) SDL_DestroyTexture(tex);
    if (ren) SDL_DestroyRenderer(ren);
    if (win) SDL_DestroyWindow(win);
    SDL_Quit();

    galnx_nvdec_close(dec);
    for (int i = 0; i < kTargetCount; i++) free(ref[i]);
    return 0;
}

int main(int argc, char **argv) {
    fsInitialize();
    fsdevMountSdmc();
    g_log = fopen("sdmc:/nvdec-probe6.txt", "wb");
    av_log_set_callback(av_log_cb);

    logf("=== GalNX NVDEC probe6 v1 (nvtegra hwaccel) ===\n");
    logf("build: " __DATE__ " " __TIME__ "\n");

    const int rc = run_probe(argc, argv);
    logf("PROBE6 rc=%d\n", rc);

    logf("=== DONE ===\n");
    logf("files on sdmc: nvdec-probe6.txt / probe6-f001.bmp / probe6-f030.bmp\n");

    if (g_log) {
        fclose(g_log);
        g_log = NULL;
    }
    fsdevUnmountAll();
    fsExit();
    return 0;
}
