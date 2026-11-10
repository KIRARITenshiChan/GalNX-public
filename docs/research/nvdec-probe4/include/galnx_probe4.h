/* GalNX NVDEC probe4 -- CPU-side block-linear ("tiling") readback helper.
 *
 * probe3 showed that NVDEC decoding itself works on the device (1.67 ms per
 * frame) but av_hwframe_transfer_data() (Copy Engine tiled->linear) takes
 * 20 s per frame and returns a green surface.  On Horizon the envideo map
 * backing an NVDEC frame is plain CPU-mapped host memory, so we can wait for
 * the decode fence, read the block-linear bytes directly, un-tile them in
 * software and hand back a normal RGBA frame without the Copy Engine.
 *
 * The module validates candidate layouts against a software decoded reference
 * frame (same display order index) using plane PSNR, so one device run tells us
 * which layout the hardware really produced.
 */
#ifndef GALNX_PROBE4_H
#define GALNX_PROBE4_H

#include <stdint.h>
#include <stddef.h>

#include <libavutil/frame.h>

typedef struct GalnxProbeResult4 {
    uint8_t *rgba;      /* packed RGBA8888, owned by the probe module */
    int w;
    int h;
    double detile_ms;   /* CPU un-tile time (Y + chroma) */
    double convert_ms;  /* un-tiled NV12 -> RGBA */
} GalnxProbeResult4;

/* Install a probe: the listed (1-based) display-order frame indices are
 * captured instead of being transferred through the Copy Engine. */
void galnx_probe4_setup(const char *prefix, const int *idxs, int n);

int galnx_probe4_enabled(void);

/* Attach a software decoded reference frame (planar YUV420P, tightly packed)
 * to probe slot 'slot' (same order as the idxs passed to setup).  NULL means
 * "no reference, dump only". */
void galnx_probe4_set_ref(int slot, const uint8_t *yuv420p, int w, int h);

/* Called by the decode module with a hardware (AV_PIX_FMT_ENVIDEO) frame.
 * Returns 1 = handled (out filled, frame must not be transferred),
 *         0 = not a probe target (frame must not be transferred either),
 *        -1 = error. */
int galnx_probe4_handle(int frame_index, const AVFrame *f, GalnxProbeResult4 *out);

/* Multi-line textual report of everything observed so far. */
const char *galnx_probe4_report(void);

#endif /* GALNX_PROBE4_H */
