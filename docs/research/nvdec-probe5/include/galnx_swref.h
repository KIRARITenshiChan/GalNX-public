/* GalNX NVDEC probe4 -- software decoded reference frames.
 *
 * Decodes the same movie with the plain software decoder up to the requested
 * (1-based) display-order frame indices and returns tightly packed planar
 * YUV420P frames, which serve as the ground truth for the de-tile PSNR check.
 */
#ifndef GALNX_SWREF_H
#define GALNX_SWREF_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Decode the movie at path and capture frames idxs[0..n-1] (1-based, display
 * order).  out_yuv[k] receives a malloc'ed planar YUV420P frame (caller frees)
 * or NULL when that index was not reached.  Returns the number of frames
 * captured (>= 0), or -1 on a hard error (err filled). */
int galnx_swref_collect(const char *path, const int *idxs, int n,
                        uint8_t **out_yuv, int *out_w, int *out_h,
                        double *out_ms, char *err, size_t errlen);

#ifdef __cplusplus
}
#endif

#endif /* GALNX_SWREF_H */
