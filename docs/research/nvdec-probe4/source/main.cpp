/* GalNX NVDEC probe4 -- device-side experiment.
 *
 * Goal: find out why the Copy Engine tiled->linear transfer of NVDEC frames
 * takes ~20 s per frame on the real console and produces a green surface.
 *
 * Strategy: NVDEC *decoding* already works on the device (probe3: 1.67 ms per
 * 1080p VC-1 frame), and the envideo frame map is plain CPU-mapped memory, so
 * we bypass the Copy Engine completely:
 *
 *   1. decode the same movie in software and keep reference frames 1 and 30
 *      (planar YUV420P, ground truth),
 *   2. decode with NVDEC; for frames 1 and 30 read the raw block-linear
 *      surface through envideo_map_get_cpu_addr(), un-tile it with several
 *      candidate layouts and pick the one whose luma PSNR against the
 *      reference is highest,
 *   3. write the raw surface, the reference frame and the de-tiled frame to
 *      the SD card so the layout can also be verified on the PC,
 *   4. render the de-tiled frame through SDL and also save it as BMP.
 *
 * Nothing is written outside sdmc:/ and no Copy Engine transfer is used.
 */
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

static void logf(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    if (g_log) {
        va_start(ap, fmt);
        vfprintf(g_log, fmt, ap);
        va_end(ap);
        fflush(g_log);
    }
    fflush(stdout);
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
    int got = galnx_swref_collect(path, kTargetIdx, kTargetCount, ref, &ref_w, &ref_h, &sw_ms,
                                  err, sizeof(err));
    logf("swref: found=%d %dx%d time=%.1f ms err=%s\n", got, ref_w, ref_h, sw_ms,
         err[0] ? err : "-");
    for (int i = 0; i < kTargetCount; i++) {
        logf("swref[%d]: target frame %d -> %s\n", i, kTargetIdx[i], ref[i] ? "ok" : "missing");
    }

    /* ---- step 2: NVDEC pass with probe readback ----------------------- */
    GalnxNvdecInfo info;
    memset(&info, 0, sizeof(info));
    err[0] = '\0';
    GalnxNvdecCtx *dec = galnx_nvdec_open(path, &info, err, sizeof(err));
    if (!dec) {
        logf("open failed: %s\n", err);
        for (int i = 0; i < kTargetCount; i++) free(ref[i]);
        return 3;
    }
    logf("info: %dx%d codec=%s(%d) pix=%s fps=%.3f duration=%lld ms frames_hint=%lld\n",
         info.width, info.height, info.codec_name, info.codec_id, info.pix_fmt_name, info.fps,
         (long long)info.duration_ms, (long long)info.frames_hint);

    galnx_nvdec_set_probe(dec, "sdmc:/nvdec-probe4", kTargetIdx, kTargetCount);
    for (int i = 0; i < kTargetCount; i++) {
        if (ref[i]) galnx_nvdec_set_probe_ref(dec, i, ref[i], ref_w, ref_h);
    }

    /* ---- SDL window (optional: the probe still works headless) -------- */
    SDL_Window *win = NULL;
    SDL_Renderer *ren = NULL;
    SDL_Texture *tex = NULL;
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS | SDL_INIT_JOYSTICK) == 0) {
        for (int i = 0; i < SDL_NumJoysticks(); i++) SDL_JoystickOpen(i);
        win = SDL_CreateWindow("nvdec-probe4", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
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

    /* ---- step 3: decode loop ------------------------------------------ */
    int rendered = 0;
    int skipped = 0;
    bool quit = false;
    const double t_start = now_ms();
    for (int iter = 0; iter < 2000 && !quit; iter++) {
        const uint8_t *rgba = NULL;
        int w = 0, h = 0;
        int64_t pts = -1;
        double dec_ms = 0.0, xfer_ms = 0.0, conv_ms = 0.0;
        err[0] = '\0';
        int r = galnx_nvdec_next(dec, &rgba, &w, &h, &pts, &dec_ms, &xfer_ms, &conv_ms,
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
        if (r == 2) {
            skipped++;
            pump_events(quit);
            if (idx_now >= 120) break;
            continue;
        }
        rendered++;
        logf("frame idx=%d %dx%d pts=%lldms dec=%.2f xfer=%.2f conv=%.2f hw=%d\n",
             idx_now, w, h, (long long)pts, dec_ms, xfer_ms, conv_ms,
             galnx_nvdec_last_hw(dec));
        if (tex && ren && rgba && w > 0 && h > 0) {
            SDL_UpdateTexture(tex, NULL, rgba, w * 4);
            SDL_RenderClear(ren);
            SDL_RenderCopy(ren, tex, NULL, NULL);
            SDL_RenderPresent(ren);
        }
        for (int k = 0; k < kTargetCount; k++) {
            if (kTargetIdx[k] != idx_now || !rgba) continue;
            char bmp[256];
            snprintf(bmp, sizeof(bmp), "sdmc:/nvdec-probe4-f%03d.bmp", idx_now);
            int brc = write_bmp(bmp, rgba, w, h);
            logf("bmp: %s rc=%d\n", bmp, brc);
        }
        pump_events(quit);
        if (rendered >= 120 || idx_now >= 120) break;
    }
    const double elapsed = now_ms() - t_start;

    /* ---- step 4: report ----------------------------------------------- */
    const char *rp = galnx_nvdec_probe_report(dec);
    logf("--- probe4 report ---\n%s--- end report ---\n", rp ? rp : "(none)\n");
    const int idx_total = galnx_nvdec_frame_index(dec);
    logf("summary: rendered=%d skipped=%d hw=%d idx=%d elapsed=%.1f ms\n", rendered, skipped,
         galnx_nvdec_hw_used(dec), idx_total, elapsed);
    if (idx_total > 0) {
        logf("decode-only: %.2f ms/frame (%.2f fps, no Copy Engine transfer)\n",
             elapsed / (double)idx_total, 1000.0 * (double)idx_total / elapsed);
    } else {
        logf("decode-only: no hardware frames observed\n");
    }

    SDL_Delay(500);
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
    g_log = fopen("sdmc:/nvdec-probe4.txt", "wb");
    av_log_set_callback(av_log_cb);

    logf("=== GalNX NVDEC probe4 v1 ===\n");
    logf("build: " __DATE__ " " __TIME__ "\n");
    int rc = run_probe(argc, argv);
    logf("=== %s ===\n", rc == 0 ? "DONE" : "FAILED");
    logf("files on sdmc: nvdec-probe4*.bin / *.yuv / *.bmp / nvdec-probe4.txt\n");

    if (g_log) {
        fclose(g_log);
        g_log = NULL;
    }
    fsdevUnmountAll();
    fsExit();
    return rc;
}
