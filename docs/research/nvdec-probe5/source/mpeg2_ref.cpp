/* GalNX NVDEC probe5 -- Phase A: envideo's own self-contained MPEG-2
 * reference decode.
 *
 * Rationale: probe4 showed that a real VC-1 stream decoded through FFmpeg's
 * envideo hwaccel never wrote the output surface (fence timed out after 5 s,
 * surface all zeroes, AVERROR_UNKNOWN from the status check).  Before blaming
 * FFmpeg, prove that NVDEC + envideo can decode *anything* on this console.
 * envideo ships test/decode.cpp, which decodes a 128x128 MPEG-2 frame with a
 * known-good result hash (XXH64 == 0xa2c4a330592602d5).  This file is a
 * stripped copy of that test, with:
 *   - every envideo call logged with its return code,
 *   - fence waiting done with poll loops (the test blocks for 5 s),
 *   - the NVDEC status block dumped, and
 *   - the resulting frame saved to SD so the answer survives the log.
 */
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <switch.h>

#include <envideo.h>
#include <nvmisc.h>
#include <clc9b0.h>
#include <nvdec_drv.h>

#include "ref_mpeg2_data.h"
#include "xxh64.h"
#include "mpeg2_ref.h"

extern "C" void galnx_logf(const char *fmt, ...);
extern "C" int galnx_write_bmp(const char *path, const unsigned char *rgba, int w, int h);

namespace {

constexpr unsigned kFrameWidth  = 128;
constexpr unsigned kFrameHeight = 128;
constexpr unsigned kFrameSize   = kFrameWidth * kFrameHeight + kFrameWidth * kFrameHeight / 2;
constexpr unsigned kLumaOff     = 0;
constexpr unsigned kChromaOff   = kFrameWidth * kFrameHeight;
constexpr uint64_t kExpectedHash = UINT64_C(0xa2c4a330592602d5);

#define GALNX_ALIGN(x, a) (((x) + (a) - 1) & ~((a) - 1))
#define GALNX_ALIGN_MAP(x) GALNX_ALIGN(x, ENVIDEO_MAP_ALIGN)

constexpr size_t kPicSetupLen   = sizeof(pic_setup_bin);
constexpr size_t kBitstreamLen  = sizeof(bitstream_bin);
constexpr size_t kSliceOffsLen  = sizeof(slice_offsets_bin);

constexpr size_t kStatusOff     = 0;
constexpr size_t kSetupOff      = GALNX_ALIGN_MAP(kStatusOff + sizeof(nvdec_status_s));
constexpr size_t kBitstreamOff  = GALNX_ALIGN_MAP(kSetupOff + sizeof(nvdec_mpeg2_pic_s));
constexpr size_t kSliceOffsOff  = GALNX_ALIGN_MAP(kBitstreamOff + sizeof(bitstream_bin));
constexpr size_t kInputSize     = GALNX_ALIGN(kSliceOffsOff, 0x1000);

#define CHK(expr)                                                                    \
    do {                                                                             \
        int chk_rc = (expr);                                                         \
        if (chk_rc != 0) {                                                           \
            galnx_logf("ref: FAILED %s -> rc=%d (line %d)\n", #expr, chk_rc, __LINE__); \
            return -1;                                                               \
        }                                                                            \
    } while (0)

struct DecodeContext {
    EnvideoDevice  *dev         = nullptr;
    EnvideoMap     *cmdbuf_map  = nullptr;
    EnvideoMap     *input_map   = nullptr;
    EnvideoMap     *frame       = nullptr;
    EnvideoMap     *result      = nullptr;
    EnvideoChannel *chan        = nullptr;
    EnvideoChannel *copy_chan   = nullptr;
    EnvideoCmdbuf  *cmdbuf      = nullptr;
    EnvideoCmdbuf  *copy_cmdbuf = nullptr;

    int initialize(EnvideoDevice *device) {
        this->dev = device;

        int rc = envideo_map_create(this->dev, &this->cmdbuf_map, 0x10000, 0x1000,
            static_cast<EnvideoMapFlags>(EnvideoMap_CpuWriteCombine | EnvideoMap_GpuUncacheable |
                                         EnvideoMap_LocationHost    | EnvideoMap_UsageCmdbuf));
        galnx_logf("ref: map_create(cmdbuf) rc=%d\n", rc);
        if (rc != 0) return rc;

        rc = envideo_channel_create(this->dev, &this->chan, EnvideoEngine_Nvdec);
        galnx_logf("ref: channel_create(nvdec) rc=%d\n", rc);
        if (rc != 0) return rc;

        rc = envideo_channel_create(this->dev, &this->copy_chan, EnvideoEngine_Copy);
        galnx_logf("ref: channel_create(copy) rc=%d\n", rc);
        if (rc != 0) return rc;

        rc = envideo_map_pin(this->cmdbuf_map, this->chan);
        galnx_logf("ref: map_pin(cmdbuf, nvdec) rc=%d\n", rc);
        rc = envideo_map_pin(this->cmdbuf_map, this->copy_chan);
        galnx_logf("ref: map_pin(cmdbuf, copy) rc=%d\n", rc);

        rc = envideo_cmdbuf_create(this->chan, &this->cmdbuf);
        galnx_logf("ref: cmdbuf_create(nvdec) rc=%d\n", rc);
        if (rc != 0) return rc;

        rc = envideo_cmdbuf_create(this->copy_chan, &this->copy_cmdbuf);
        galnx_logf("ref: cmdbuf_create(copy) rc=%d\n", rc);
        if (rc != 0) return rc;

        auto size = envideo_map_get_size(this->cmdbuf_map);
        galnx_logf("ref: cmdbuf_map size=%u\n", (unsigned)size);
        rc = envideo_cmdbuf_add_memory(this->cmdbuf, this->cmdbuf_map, 0, size / 2);
        galnx_logf("ref: cmdbuf_add_memory(nvdec) rc=%d\n", rc);
        rc = envideo_cmdbuf_add_memory(this->copy_cmdbuf, this->cmdbuf_map, size / 2, size / 2);
        galnx_logf("ref: cmdbuf_add_memory(copy) rc=%d\n", rc);

        rc = envideo_map_create(this->dev, &this->input_map, kInputSize, 0x1000,
            static_cast<EnvideoMapFlags>(EnvideoMap_CpuWriteCombine | EnvideoMap_GpuCacheable |
                                         EnvideoMap_LocationDevice  | EnvideoMap_UsageEngine));
        galnx_logf("ref: map_create(input) size=%u rc=%d\n", (unsigned)kInputSize, rc);
        if (rc != 0) return rc;
        rc = envideo_map_pin(this->input_map, this->chan);
        galnx_logf("ref: map_pin(input, nvdec) rc=%d\n", rc);

        rc = envideo_map_create(this->dev, &this->frame, kFrameSize, 0x1000,
            static_cast<EnvideoMapFlags>(EnvideoMap_CpuUnmapped    | EnvideoMap_GpuCacheable |
                                         EnvideoMap_LocationDevice | EnvideoMap_UsageFramebuffer));
        galnx_logf("ref: map_create(frame) size=%u rc=%d\n", (unsigned)kFrameSize, rc);
        if (rc != 0) return rc;
        rc = envideo_map_pin(this->frame, this->chan);
        galnx_logf("ref: map_pin(frame, nvdec) rc=%d\n", rc);
        rc = envideo_map_pin(this->frame, this->copy_chan);
        galnx_logf("ref: map_pin(frame, copy) rc=%d\n", rc);

        rc = envideo_map_create(this->dev, &this->result, kFrameSize, 0x1000,
            static_cast<EnvideoMapFlags>(EnvideoMap_CpuCacheable  | EnvideoMap_GpuCacheable |
                                         EnvideoMap_LocationHost  | EnvideoMap_UsageFramebuffer));
        galnx_logf("ref: map_create(result) size=%u rc=%d\n", (unsigned)kFrameSize, rc);
        if (rc != 0) return rc;
        rc = envideo_map_pin(this->result, this->copy_chan);
        galnx_logf("ref: map_pin(result, copy) rc=%d\n", rc);

        return 0;
    }

    void finalize() {
        if (this->frame)       envideo_map_destroy(this->frame);
        if (this->input_map)   envideo_map_destroy(this->input_map);
        if (this->result)      envideo_map_destroy(this->result);
        if (this->copy_cmdbuf) envideo_cmdbuf_destroy(this->copy_cmdbuf);
        if (this->cmdbuf)      envideo_cmdbuf_destroy(this->cmdbuf);
        if (this->cmdbuf_map)  envideo_map_destroy(this->cmdbuf_map);
        if (this->copy_chan)   envideo_channel_destroy(this->copy_chan);
        if (this->chan)        envideo_channel_destroy(this->chan);
        this->frame = this->input_map = this->result = this->cmdbuf_map = nullptr;
        this->cmdbuf = this->copy_cmdbuf = nullptr;
        this->chan = this->copy_chan = nullptr;
        this->dev = nullptr;
    }
};

/* Wait for a fence by polling, so that a non-signalling fence is reported as
 * such instead of turning into a multi-second block. */
int wait_fence_polled(EnvideoDevice *dev, EnvideoFence fence, const char *tag) {
    constexpr unsigned long long kStepUs    = 50ULL * 1000ULL;
    constexpr unsigned long long kTimeoutUs = 3ULL * 1000ULL * 1000ULL;

    unsigned long long waited = 0;
    bool done = false;
    int  rc   = 0;

    while (waited < kTimeoutUs) {
        done = false;
        rc = envideo_fence_poll(dev, fence, &done);
        if (rc != 0) {
            galnx_logf("ref: %s poll rc=%d after %llu us\n", tag, rc, waited);
            return rc;
        }
        if (done) {
            galnx_logf("ref: %s signalled after %llu us (poll)\n", tag, waited);
            return 0;
        }
        svcSleepThread((int64_t)kStepUs * 1000);
        waited += kStepUs;
    }

    done = false;
    rc = envideo_fence_poll(dev, fence, &done);
    galnx_logf("ref: %s NOT signalled after %llu us (last poll rc=%d done=%d)\n",
               tag, waited, rc, (int)done);
    int wrc = envideo_fence_wait(dev, fence, 0);
    galnx_logf("ref: %s blocking wait(0) rc=%d\n", tag, wrc);
    return -1;
}

void dump_hex(const char *tag, const void *p, size_t n) {
    const unsigned char *b = static_cast<const unsigned char *>(p);
    char line[256];
    for (size_t i = 0; i < n;) {
        int off = snprintf(line, sizeof(line), "ref: %s+%02u =", tag, (unsigned)i);
        for (size_t k = 0; k < 16 && i < n; k++, i++)
            off += snprintf(line + off, sizeof(line) - (size_t)off, " %02x", b[i]);
        galnx_logf("%s\n", line);
    }
}

int nv12_to_rgba(const uint8_t *nv12, uint8_t *rgba, unsigned w, unsigned h) {
    if (!nv12 || !rgba) return -1;
    const uint8_t *y = nv12;
    const uint8_t *uv = nv12 + (size_t)w * h;
    for (unsigned j = 0; j < h; j++) {
        for (unsigned i = 0; i < w; i++) {
            int Y = y[(size_t)j * w + i] - 16;
            int U = uv[((size_t)(j / 2) * (w / 2) + i / 2) * 2 + 0] - 128;
            int V = uv[((size_t)(j / 2) * (w / 2) + i / 2) * 2 + 1] - 128;
            int c = (298 * Y + 128) >> 8;
            int r = (c + (409 * V + 128) >> 8);
            int g = (c - ((100 * U + 128) >> 8) - ((208 * V + 128) >> 8));
            int b = (c + (516 * U + 128) >> 8);
            uint8_t *px = rgba + ((size_t)j * w + i) * 4;
            px[0] = (uint8_t)(r < 0 ? 0 : (r > 255 ? 255 : r));
            px[1] = (uint8_t)(g < 0 ? 0 : (g > 255 ? 255 : g));
            px[2] = (uint8_t)(b < 0 ? 0 : (b > 255 ? 255 : b));
            px[3] = 0xff;
        }
    }
    return 0;
}

int decode_mpeg2(DecodeContext &ctx) {
    EnvideoFence decode_fence = 0;
    EnvideoFence copy_fence   = 0;

    galnx_logf("ref: input layout status=%u setup=%u bitstream=%u sliceoffs=%u input_size=%u\n",
               (unsigned)kStatusOff, (unsigned)kSetupOff, (unsigned)kBitstreamOff,
               (unsigned)kSliceOffsOff, (unsigned)kInputSize);

    CHK(envideo_cmdbuf_clear(ctx.cmdbuf));
    CHK(envideo_cmdbuf_clear(ctx.copy_cmdbuf));

    std::uint8_t *input_addr = static_cast<std::uint8_t *>(envideo_map_get_cpu_addr(ctx.input_map));
    if (!input_addr) {
        galnx_logf("ref: input map has no cpu address\n");
        return -1;
    }
    std::memcpy(input_addr + kSetupOff,     pic_setup_bin,     kPicSetupLen);
    std::memcpy(input_addr + kBitstreamOff, bitstream_bin,     kBitstreamLen);
    std::memcpy(input_addr + kSliceOffsOff, slice_offsets_bin, kSliceOffsLen);

    EnvideoDeviceInfo info = envideo_device_get_info(ctx.dev);
    auto *setup = reinterpret_cast<nvdec_mpeg2_pic_s *>(input_addr + kSetupOff);
    galnx_logf("ref: device tegra_layout=%d -> tileFormat=%d (setup was %d)\n",
               (int)info.tegra_layout, info.tegra_layout ? 1 : 0, (int)setup->tileFormat);
    setup->tileFormat = !info.tegra_layout;

    galnx_logf("ref: push nvdec commands\n");
    CHK(envideo_cmdbuf_begin(ctx.cmdbuf, EnvideoEngine_Nvdec));
    CHK(envideo_cmdbuf_push_value(ctx.cmdbuf, NVC9B0_SET_APPLICATION_ID,
        DRF_DEF(C9B0, _SET_APPLICATION_ID, _ID, _MPEG12)));
    CHK(envideo_cmdbuf_push_value(ctx.cmdbuf, NVC9B0_SET_PICTURE_INDEX, 0));
    CHK(envideo_cmdbuf_push_value(ctx.cmdbuf, NVC9B0_SET_CONTROL_PARAMS,
        DRF_DEF(C9B0, _SET_CONTROL_PARAMS, _CODEC_TYPE,     _MPEG2) |
        DRF_NUM(C9B0, _SET_CONTROL_PARAMS, _GPTIMER_ON,     1)      |
        DRF_NUM(C9B0, _SET_CONTROL_PARAMS, _ERR_CONCEAL_ON, 1)      |
        DRF_NUM(C9B0, _SET_CONTROL_PARAMS, _MBTIMER_ON,     1)));

    CHK(envideo_cmdbuf_push_reloc(ctx.cmdbuf, NVC9B0_SET_DRV_PIC_SETUP_OFFSET,
        ctx.input_map, (uint32_t)kSetupOff, EnvideoRelocType_Default, 8));
    CHK(envideo_cmdbuf_push_reloc(ctx.cmdbuf, NVC9B0_SET_IN_BUF_BASE_OFFSET,
        ctx.input_map, (uint32_t)kBitstreamOff, EnvideoRelocType_Default, 8));
    CHK(envideo_cmdbuf_push_reloc(ctx.cmdbuf, NVC9B0_SET_SLICE_OFFSETS_BUF_OFFSET,
        ctx.input_map, (uint32_t)kSliceOffsOff, EnvideoRelocType_Default, 8));
    CHK(envideo_cmdbuf_push_reloc(ctx.cmdbuf, NVC9B0_SET_NVDEC_STATUS_OFFSET,
        ctx.input_map, (uint32_t)kStatusOff, EnvideoRelocType_Default, 8));

    CHK(envideo_cmdbuf_push_reloc(ctx.cmdbuf, NVC9B0_SET_PICTURE_LUMA_OFFSET0,
        ctx.frame, kLumaOff, EnvideoRelocType_Tiled, 8));
    CHK(envideo_cmdbuf_push_reloc(ctx.cmdbuf, NVC9B0_SET_PICTURE_CHROMA_OFFSET0,
        ctx.frame, kChromaOff, EnvideoRelocType_Tiled, 8));

    CHK(envideo_cmdbuf_push_value(ctx.cmdbuf, NVC9B0_EXECUTE,
        DRF_DEF(C9B0, _EXECUTE, _NOTIFY, _DISABLE) |
        DRF_DEF(C9B0, _EXECUTE, _AWAKEN, _ENABLE)));
    CHK(envideo_cmdbuf_end(ctx.cmdbuf));

    galnx_logf("ref: submit nvdec chapter\n");
    CHK(envideo_channel_submit(ctx.chan, ctx.cmdbuf, &decode_fence));
    galnx_logf("ref: decode fence = %llu\n", (unsigned long long)decode_fence);

    /* The reference test waits for the decode fence from the GPU (Host engine
     * cmdbuf).  Poll from the CPU instead so a stalled fence shows up here. */
    if (wait_fence_polled(ctx.dev, decode_fence, "decode") != 0) {
        galnx_logf("ref: decode fence never signalled; aborting copy path\n");
        return -1;
    }

    galnx_logf("ref: build copy chapter\n");
    CHK(envideo_cmdbuf_begin(ctx.copy_cmdbuf, EnvideoEngine_Host));
    CHK(envideo_cmdbuf_wait_fence(ctx.copy_cmdbuf, decode_fence));
    CHK(envideo_cmdbuf_end(ctx.copy_cmdbuf));

    EnvideoSurfaceInfo luma_src = {
        .map        = ctx.frame,
        .map_offset = kLumaOff,
        .width      = kFrameWidth,
        .height     = kFrameHeight,
        .stride     = kFrameWidth,
        .tiled      = true,
        .gob_height = 2,
    };
    EnvideoSurfaceInfo luma_dst = {
        .map        = ctx.result,
        .map_offset = kLumaOff,
        .width      = kFrameWidth,
        .height     = kFrameHeight,
        .stride     = kFrameWidth,
    };
    CHK(envideo_surface_transfer(ctx.copy_cmdbuf, &luma_src, &luma_dst));

    EnvideoSurfaceInfo chroma_src = {
        .map        = ctx.frame,
        .map_offset = kChromaOff,
        .width      = kFrameWidth,
        .height     = kFrameHeight / 2,
        .stride     = kFrameWidth,
        .tiled      = true,
        .gob_height = 2,
    };
    EnvideoSurfaceInfo chroma_dst = {
        .map        = ctx.result,
        .map_offset = kChromaOff,
        .width      = kFrameWidth,
        .height     = kFrameHeight / 2,
        .stride     = kFrameWidth,
        .tiled      = false,
    };
    CHK(envideo_surface_transfer(ctx.copy_cmdbuf, &chroma_src, &chroma_dst));

    CHK(envideo_cmdbuf_begin(ctx.copy_cmdbuf, EnvideoEngine_Host));
    CHK(envideo_cmdbuf_cache_op(ctx.copy_cmdbuf, EnvideoCache_Writeback));
    CHK(envideo_cmdbuf_end(ctx.copy_cmdbuf));

    galnx_logf("ref: submit copy chapter\n");
    CHK(envideo_channel_submit(ctx.copy_chan, ctx.copy_cmdbuf, &copy_fence));
    galnx_logf("ref: copy fence = %llu\n", (unsigned long long)copy_fence);

    CHK(envideo_map_cache_op(ctx.result, 0, envideo_map_get_size(ctx.result), EnvideoCache_Invalidate));
    if (wait_fence_polled(ctx.dev, copy_fence, "copy") != 0) {
        galnx_logf("ref: copy fence never signalled\n");
        return -1;
    }
    CHK(envideo_map_cache_op(ctx.result, 0, envideo_map_get_size(ctx.result), EnvideoCache_Invalidate));

    /* ---- status ------------------------------------------------------- */
    auto *status = reinterpret_cast<nvdec_status_s *>(input_addr + kStatusOff);
    galnx_logf("ref: status error=%u mbs_ok=%u mbs_err=%u cycles=%u slice_err=%u\n",
               status->error_status, status->mbs_correctly_decoded, status->mbs_in_error,
               status->cycle_count, status->slice_header_error_code);
    dump_hex("status", status, 64);

    const unsigned expected_mbs = (kFrameWidth / 16) * (kFrameHeight / 16);
    int status_bad = 0;
    if (status->error_status != 0) {
        galnx_logf("ref: CHECK error_status != 0\n");
        status_bad = 1;
    }
    if (status->mbs_correctly_decoded != expected_mbs) {
        galnx_logf("ref: CHECK mbs_correctly_decoded %u != %u\n",
                   status->mbs_correctly_decoded, expected_mbs);
        status_bad = 1;
    }
    if (status->mbs_in_error != 0) {
        galnx_logf("ref: CHECK mbs_in_error != 0\n");
        status_bad = 1;
    }
    if (status->cycle_count == 0) {
        galnx_logf("ref: CHECK cycle_count == 0\n");
        status_bad = 1;
    }
    galnx_logf("ref: status verdict = %s\n", status_bad ? "BAD" : "OK");

    /* ---- result ------------------------------------------------------- */
    std::uint8_t *out = static_cast<std::uint8_t *>(envideo_map_get_cpu_addr(ctx.result));
    if (!out) {
        galnx_logf("ref: result map has no cpu address\n");
        return -1;
    }
    const size_t result_size = envideo_map_get_size(ctx.result);
    const uint64_t hash_map  = galnx_xxh64(out, result_size, 0);
    const uint64_t hash_nv12 = galnx_xxh64(out, kFrameSize, 0);
    galnx_logf("ref: hash map(%u B)=%016llx nv12(%u B)=%016llx expected=%016llx\n",
               (unsigned)result_size, (unsigned long long)hash_map,
               (unsigned)kFrameSize, (unsigned long long)hash_nv12,
               (unsigned long long)kExpectedHash);

    dump_hex("result", out, 32);

    FILE *fp = fopen("sdmc:/probe5-mpeg2.nv12", "wb");
    if (fp) {
        fwrite(out, 1, kFrameSize, fp);
        fclose(fp);
        galnx_logf("ref: wrote sdmc:/probe5-mpeg2.nv12 (%u B)\n", (unsigned)kFrameSize);
    } else {
        galnx_logf("ref: could not open sdmc:/probe5-mpeg2.nv12\n");
    }

    std::uint8_t *rgba = static_cast<std::uint8_t *>(std::malloc((size_t)kFrameWidth * kFrameHeight * 4));
    if (rgba) {
        nv12_to_rgba(out, rgba, kFrameWidth, kFrameHeight);
        int brc = galnx_write_bmp("sdmc:/probe5-mpeg2.bmp", rgba, kFrameWidth, kFrameHeight);
        galnx_logf("ref: bmp rc=%d\n", brc);
        std::free(rgba);
    }

    const int hash_ok = (hash_nv12 == kExpectedHash);
    galnx_logf("REF_MPEG2: status=%s hash=%s verdict=%s\n",
               status_bad ? "BAD" : "OK", hash_ok ? "MATCH" : "MISMATCH",
               (!status_bad && hash_ok) ? "PASS" : "FAIL");
    return (!status_bad && hash_ok) ? 0 : -1;
}

}  // namespace

extern "C" int galnx_ref_mpeg2_run(void) {
    galnx_logf("--- Phase A: envideo MPEG-2 reference decode ---\n");
    galnx_logf("ref: arrays setup=%u bitstream=%u sliceoffs=%u\n",
               (unsigned)kPicSetupLen, (unsigned)kBitstreamLen, (unsigned)kSliceOffsLen);

    EnvideoDevice *dev = nullptr;
    int rc = envideo_device_create(&dev);
    galnx_logf("ref: device_create rc=%d dev=%p\n", rc, (void *)dev);
    if (rc != 0 || !dev) return -1;

    EnvideoDeviceInfo info = envideo_device_get_info(dev);
    galnx_logf("ref: device info tegra_layout=%d\n", (int)info.tegra_layout);

    DecodeContext ctx;
    int irc = ctx.initialize(dev);
    int drc = -1;
    if (irc == 0) {
        drc = decode_mpeg2(ctx);
    } else {
        galnx_logf("ref: context init failed rc=%d\n", irc);
    }
    ctx.finalize();
    envideo_device_destroy(dev);
    galnx_logf("--- Phase A done rc=%d ---\n", drc);
    return drc;
}
