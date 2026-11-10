/* Self-contained NVDEC reference decode (MPEG-2 128x128, from the
 * envideo test suite) used to establish whether NVDEC + envideo decode
 * works at all on this console. */
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

/* Returns 0 when the reference decode produces the expected NV12 frame
 * (status ok + XXH64 match), non-zero otherwise.  Logs every step through
 * galnx_logf(). */
int galnx_ref_mpeg2_run(void);

#ifdef __cplusplus
}
#endif
