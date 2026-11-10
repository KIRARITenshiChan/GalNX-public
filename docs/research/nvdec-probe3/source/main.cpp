/*
 * nvdec-probe3 -- GalNX NVDEC playback probe (real device validation).
 *
 * Purpose: prove the full hardware video path end to end before wiring it into
 * rfvp: FFmpeg(averne/envideo) -> NVDEC -> sw NV12/YUV420P -> RGBA -> SDL2.
 * The decoder module (source/galnx_nvdec.c) is written so it can be lifted
 * into rfvp's platform/switch/runtime unchanged.
 *
 * Behaviour:
 *   - picks the first existing input from the candidate list below, or the
 *     path written in sdmc:/switch/nvdec-file.txt (one line);
 *   - plays the whole file on screen, real-time paced by pts;
 *   - writes a log to sdmc:/nvdec-probe3.txt;
 *   - dumps BMP screenshots of frames 1/60/180 to sdmc:/nvdec-probe3-NNN.bmp
 *     (copy them off the SD card to eyeball colour and sharpness);
 *   - waits for PLUS before exiting so the log is complete when inspected.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

#include <SDL.h>
#include <switch.h>

/* FFmpeg headers need explicit C linkage when used from C++ here. */
extern "C" {
#include <libavutil/log.h>
}

#include "galnx_nvdec.h"

/* Heap: leave libnx's default in place (same as rfvp's platform/switch runtime).
 * An earlier build forced __nx_heap_size = 128 MiB; that was far too small for
 * a 1080p VC-1 decoder (FFmpeg frame buffers + RGBA + BMP dump), and it also
 * starved the GLES texture allocation (SDL_CreateTexture OOM in Citron). */

static const char *kLogFile = "sdmc:/nvdec-probe3.txt";
static const char *kOverrideFile = "sdmc:/switch/nvdec-file.txt";

static const char *kCandidates[] = {
    "sdmc:/nvdec-poc.wmv",
    "sdmc:/switch/nvdec-poc.wmv",
    "sdmc:/nvdec-poc.mp4",
    "sdmc:/switch/nvdec-poc.mp4",
    "sdmc:/switch/rfvp/game/movie/01.wmv",
};

static FILE *g_log = NULL;

static void logf(const char *fmt, ...)
{
    char buf[1024];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    fputs(buf, stdout);
    fflush(stdout);
    if (g_log) {
        fputs(buf, g_log);
        fflush(g_log);
    }
}

static void av_log_cb(void *avcl, int level, const char *fmt, va_list vl)
{
    (void)avcl;
    if (level > AV_LOG_INFO)
        return;
    char buf[768];
    vsnprintf(buf, sizeof(buf), fmt, vl);
    logf("[ffmpeg] %s", buf);
}

static int file_exists(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f)
        return 0;
    fclose(f);
    return 1;
}

static int trim_line(char *s)
{
    int n = (int)strlen(s);
    while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r' || s[n - 1] == ' '))
        s[--n] = '\0';
    return n;
}

static int find_input(char *out, size_t outlen)
{
    FILE *f = fopen(kOverrideFile, "rb");
    if (f) {
        if (fgets(out, (int)outlen, f)) {
            fclose(f);
            if (trim_line(out) > 0)
                return 1;
        } else {
            fclose(f);
        }
    }
    for (size_t i = 0; i < sizeof(kCandidates) / sizeof(kCandidates[0]); i++) {
        if (file_exists(kCandidates[i])) {
            snprintf(out, outlen, "%s", kCandidates[i]);
            return 1;
        }
    }
    return 0;
}

static void put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFF);
    p[1] = (uint8_t)(v >> 8);
}

static void put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFF);
    p[1] = (uint8_t)((v >> 8) & 0xFF);
    p[2] = (uint8_t)((v >> 16) & 0xFF);
    p[3] = (uint8_t)((v >> 24) & 0xFF);
}

static void write_bmp(const char *path, const uint8_t *rgba, int w, int h)
{
    const int row = (w * 3 + 3) & ~3;
    const uint32_t datasize = (uint32_t)row * (uint32_t)h;
    uint8_t hdr[54];
    memset(hdr, 0, sizeof(hdr));
    hdr[0] = 'B';
    hdr[1] = 'M';
    put_u32(hdr + 2, 54 + datasize);
    put_u32(hdr + 10, 54);
    put_u32(hdr + 14, 40);
    put_u32(hdr + 18, (uint32_t)w);
    put_u32(hdr + 22, (uint32_t)h);
    put_u16(hdr + 26, 1);
    put_u16(hdr + 28, 24);
    put_u32(hdr + 34, datasize);
    put_u32(hdr + 38, 2835);
    put_u32(hdr + 42, 2835);

    FILE *f = fopen(path, "wb");
    if (!f) {
        logf("bmp: cannot write %s\n", path);
        return;
    }
    fwrite(hdr, 1, sizeof(hdr), f);
    uint8_t *line = (uint8_t *)malloc((size_t)row);
    if (!line) {
        fclose(f);
        return;
    }
    for (int y = h - 1; y >= 0; y--) {
        memset(line, 0, (size_t)row);
        const uint8_t *src = rgba + (size_t)y * (size_t)w * 4u;
        for (int x = 0; x < w; x++) {
            line[x * 3 + 0] = src[x * 4 + 2];
            line[x * 3 + 1] = src[x * 4 + 1];
            line[x * 3 + 2] = src[x * 4 + 0];
        }
        fwrite(line, 1, (size_t)row, f);
    }
    free(line);
    fclose(f);
    logf("bmp: wrote %s (%dx%d)\n", path, w, h);
}

static int pump_events(void)
{
    SDL_Event ev;
    while (SDL_PollEvent(&ev)) {
        if (ev.type == SDL_QUIT)
            return 0;
        if (ev.type == SDL_KEYDOWN && ev.key.keysym.sym == SDLK_PLUS)
            return 0;
        if (ev.type == SDL_JOYBUTTONDOWN && ev.jbutton.button == 10 /* PLUS */)
            return 0;
    }
    return 1;
}

static void sleep_ms(int ms)
{
    Uint32 until = SDL_GetTicks() + (Uint32)ms;
    while ((Sint32)(until - SDL_GetTicks()) > 0) {
        SDL_PumpEvents();
        SDL_Delay(1);
    }
}

static int run_probe(void)
{
    logf("=== GalNX NVDEC probe3 (SDL playback) ===\n");
    logf("applet_type=%d application=%d\n", (int)appletGetAppletType(),
         appletGetAppletType() == AppletType_Application ? 1 : 0);

    char input[512];
    if (!find_input(input, sizeof(input))) {
        logf("no input movie found; candidates tried:\n");
        for (size_t i = 0; i < sizeof(kCandidates) / sizeof(kCandidates[0]); i++)
            logf("  %s\n", kCandidates[i]);
        logf("hint: copy poc-1080p-vc1.wmv to sdmc:/nvdec-poc.wmv\n");
        return 0;
    }
    logf("input=%s\n", input);

    av_log_set_level(AV_LOG_INFO);
    av_log_set_callback(av_log_cb);

    GalnxNvdecInfo info;
    char err[512];
    GalnxNvdecCtx *ctx = galnx_nvdec_open(input, &info, err, sizeof(err));
    if (!ctx) {
        logf("open failed: %s\n", err);
        return 0;
    }
    logf("info: %dx%d codec=%s(%d) pix_fmt=%s fps=%.3f duration_ms=%lld frames_hint=%lld hw_requested=%d\n",
         info.width, info.height, info.codec_name, info.codec_id, info.pix_fmt_name,
         info.fps, (long long)info.duration_ms, (long long)info.frames_hint,
         info.hw_requested);

    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS | SDL_INIT_JOYSTICK) < 0) {
        logf("SDL_Init failed: %s\n", SDL_GetError());
        galnx_nvdec_close(ctx);
        return 0;
    }
    SDL_Window *window = SDL_CreateWindow("GalNX nvdec-probe3",
                                          SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                          1280, 720, SDL_WINDOW_SHOWN);
    if (!window) {
        logf("SDL_CreateWindow failed: %s\n", SDL_GetError());
        SDL_Quit();
        galnx_nvdec_close(ctx);
        return 0;
    }
    SDL_Renderer *renderer = SDL_CreateRenderer(window, -1,
                                                SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    if (!renderer) {
        logf("accelerated renderer failed (%s), falling back to software\n", SDL_GetError());
        renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
    }
    if (!renderer) {
        logf("SDL_CreateRenderer failed: %s\n", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        galnx_nvdec_close(ctx);
        return 0;
    }
    if (SDL_NumJoysticks() > 0)
        SDL_JoystickOpen(0);

    int accelerated = 0;
    SDL_RendererInfo rinfo;
    if (SDL_GetRendererInfo(renderer, &rinfo) == 0) {
        logf("renderer=%s flags=0x%x\n", rinfo.name, rinfo.flags);
        accelerated = (rinfo.flags & SDL_RENDERER_ACCELERATED) ? 1 : 0;
    }

    SDL_Texture *tex = NULL;
    int tex_w = 0, tex_h = 0;
    int tex_failed = 0;
    int headless = 0;
    int last_w = 0, last_h = 0;

    uint32_t frames = 0, hw_frames = 0, sw_frames = 0;
    double dec_total = 0.0, xfer_total = 0.0, conv_total = 0.0;
    double dec_min = 1e9, dec_max = 0.0;
    double xfer_min = 1e9, xfer_max = 0.0;
    double conv_min = 1e9, conv_max = 0.0;
    int64_t first_pts = -1;
    Uint32 t_start = SDL_GetTicks();
    Uint32 last_report = t_start;
    uint32_t frames_since_report = 0;
    int rc = 0;

    while (appletMainLoop()) {
        if (!pump_events()) {
            logf("quit requested by user\n");
            break;
        }

        const uint8_t *rgba = NULL;
        int w = 0, h = 0;
        int64_t pts_ms = -1;
        double dec_ms = 0.0, xfer_ms = 0.0, conv_ms = 0.0;

        int r = galnx_nvdec_next(ctx, &rgba, &w, &h, &pts_ms, &dec_ms, &xfer_ms, &conv_ms,
                                 err, sizeof(err));
        if (r < 0) {
            logf("decode error: %s\n", err);
            rc = 1;
            break;
        }
        if (r == 0) {
            logf("end of stream\n");
            break;
        }

        if ((!tex && !tex_failed) || tex_w != w || tex_h != h) {
            if (tex) {
                SDL_DestroyTexture(tex);
                tex = NULL;
            }
            tex = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ABGR8888,
                                    SDL_TEXTUREACCESS_STREAMING, w, h);
            if (!tex) {
                logf("SDL_CreateTexture(%dx%d) failed on %s renderer: %s\n", w, h,
                     accelerated ? "accelerated" : "software", SDL_GetError());
                if (accelerated) {
                    SDL_DestroyRenderer(renderer);
                    renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
                    if (renderer) {
                        accelerated = 0;
                        SDL_RendererInfo ri2;
                        if (SDL_GetRendererInfo(renderer, &ri2) == 0)
                            logf("renderer(rebuilt)=%s flags=0x%x\n", ri2.name, ri2.flags);
                        tex = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ABGR8888,
                                                SDL_TEXTUREACCESS_STREAMING, w, h);
                        if (tex)
                            logf("texture created %dx%d on software renderer\n", w, h);
                    }
                }
            }
            if (!tex) {
                tex_failed = 1;
                headless = 1;
                logf("headless mode: decode + BMP dump without display (%s)\n", SDL_GetError());
            }
            tex_w = w;
            tex_h = h;
        }
        last_w = w;
        last_h = h;

        if (tex) {
            SDL_UpdateTexture(tex, NULL, rgba, w * 4);

            int win_w = 1280, win_h = 720;
            SDL_GetWindowSize(window, &win_w, &win_h);
            float sx = (float)win_w / (float)w;
            float sy = (float)win_h / (float)h;
            float s = (sx < sy) ? sx : sy;
            SDL_Rect dst;
            dst.w = (int)(w * s);
            dst.h = (int)(h * s);
            dst.x = (win_w - dst.w) / 2;
            dst.y = (win_h - dst.h) / 2;

            SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
            SDL_RenderClear(renderer);
            SDL_RenderCopy(renderer, tex, NULL, &dst);
            SDL_RenderPresent(renderer);
        } else if (frames == 0) {
            logf("first frame decoded headless: %dx%d\n", w, h);
        }

        frames++;
        frames_since_report++;
        if (galnx_nvdec_last_hw(ctx))
            hw_frames++;
        else
            sw_frames++;

        dec_total += dec_ms;
        xfer_total += xfer_ms;
        conv_total += conv_ms;
        if (dec_ms < dec_min) dec_min = dec_ms;
        if (dec_ms > dec_max) dec_max = dec_ms;
        if (xfer_ms < xfer_min) xfer_min = xfer_ms;
        if (xfer_ms > xfer_max) xfer_max = xfer_ms;
        if (conv_ms < conv_min) conv_min = conv_ms;
        if (conv_ms > conv_max) conv_max = conv_ms;

        if (frames == 1 || frames == 60 || frames == 180) {
            char path[128];
            snprintf(path, sizeof(path), "sdmc:/nvdec-probe3-%03u.bmp", frames);
            write_bmp(path, rgba, w, h);
        }

        if (frames % 60 == 0 || frames == 1) {
            logf("frame=%u pts=%lldms dec=%.2fms xfer=%.2fms conv=%.2fms hw=%d %dx%d\n",
                 frames, (long long)pts_ms, dec_ms, xfer_ms, conv_ms,
                 galnx_nvdec_last_hw(ctx), w, h);
        }

        /* Real-time pacing: keep the presentation clock aligned to pts. */
        if (pts_ms >= 0) {
            if (first_pts < 0) {
                first_pts = pts_ms;
                t_start = SDL_GetTicks();
            } else {
                int64_t target = (pts_ms - first_pts);
                int64_t elapsed = (int64_t)(SDL_GetTicks() - t_start);
                if (target > elapsed)
                    sleep_ms((int)(target - elapsed));
            }
        }

        Uint32 now = SDL_GetTicks();
        if ((Sint32)(now - last_report) >= 2000) {
            double secs = (double)(now - last_report) / 1000.0;
            logf("progress: frames=%u fps=%.2f hw=%u sw=%u\n", frames,
                 secs > 0.0 ? frames_since_report / secs : 0.0, hw_frames, sw_frames);
            last_report = now;
            frames_since_report = 0;
        }
    }

    double wall_ms = (double)(SDL_GetTicks() - t_start);
    logf("\n=== SUMMARY ===\n");
    logf("frames=%u hw_frames=%u sw_frames=%u\n", frames, hw_frames, sw_frames);
    logf("hw_used=%d fps_overall=%.3f wall_ms=%.1f\n",
         galnx_nvdec_hw_used(ctx),
         wall_ms > 0.0 ? (double)frames * 1000.0 / wall_ms : 0.0, wall_ms);
    if (frames > 0) {
        logf("DECODE   avg=%.3fms min=%.3fms max=%.3fms\n", dec_total / frames, dec_min, dec_max);
        logf("TRANSFER avg=%.3fms min=%.3fms max=%.3fms\n", xfer_total / frames, xfer_min, xfer_max);
        logf("CONVERT  avg=%.3fms min=%.3fms max=%.3fms\n", conv_total / frames, conv_min, conv_max);
    }
    logf("mode=%s accelerated=%d headless=%d\n",
         tex ? (accelerated ? "gles" : "software") : "headless", accelerated, headless);
    logf("last_frame=%dx%d\n", last_w, last_h);

    if (tex)
        SDL_DestroyTexture(tex);
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
    galnx_nvdec_close(ctx);
    return rc;
}

int main(int argc, char *argv[])
{
    (void)argc;
    (void)argv;

    fsInitialize();
    fsdevMountSdmc();

    g_log = fopen(kLogFile, "wb");
    if (!g_log) {
        /* Nothing we can do; still let the app run so the screen shows life. */
    }

    run_probe();

    logf("\n=== DONE (press PLUS to exit) ===\n");
    PadState pad;
    padInitializeDefault(&pad);
    while (appletMainLoop()) {
        padUpdate(&pad);
        if (padGetButtonsDown(&pad) & HidNpadButton_Plus)
            break;
        svcSleepThread(50000000ULL); /* 50 ms */
    }

    if (g_log) {
        fclose(g_log);
        g_log = NULL;
    }
    fsdevUnmountAll();
    fsExit();
    return 0;
}
