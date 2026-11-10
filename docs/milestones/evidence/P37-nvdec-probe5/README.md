# P37 — NVDEC 探针 probe5 证据（PASS）

对应记录：`docs/builds/043-nvdec-probe5.md`；源码：`docs/research/nvdec-probe5/`。

## 这些文件能证明什么

| 文件 | 能证明 |
| --- | --- |
| `nvdec-probe5-device.txt`（7,289 B / 135 行，原件 581,748 B / 8,349 行的去 `[ffmpeg]` 裁剪版） | **真机**：envideo 原生参考解码全链路可用 —— `device_create rc=0`、`decode signalled after 0 us`、`status error=0 mbs_ok=64 cycles=5042`、`hash map=nv12=expected=a2c4a330592602d5`、`REF_MPEG2 ... verdict=PASS`、`PHASE A verdict: PASS`；同时记录 Phase B（FFmpeg envideo VC-1）失败明细 |
| `probe5-mpeg2.nv12`（24,576 B） | 真机从 NVDEC 表面经 CE 搬出、cache writeback 后的 NV12 像素；XXH64 = `a2c4a330592602d5`（与 envideo 官方期望值一致） |
| `probe5-mpeg2-device.bmp`（49,206 B） | 同一帧的可视化（128×128 彩条 + 时间码 `00:00:00.000`），肉眼可核 |
| `nvdec-probe5-citron.txt`（730,533 B） | Citron 链路完整且优雅降级：`device_create rc=-88` → `PHASE A verdict: FAIL`，Phase B 120 帧、`=== DONE ===`，无崩溃 |
| `citron-result.json`（2,510 B） | Citron harness 单行结果（返回码、窗口、截图、日志切片） |
| `SHA256SUMS` | 上述文件哈希 |

## 这些文件不能证明什么

1. **不能**证明 FFmpeg envideo 的 VC-1 硬解可用 —— Phase B 在同一台真机上失败（`AVERROR_UNKNOWN`）。
2. **不能**证明 1080p 播放可行 —— Phase A 只有 128×128 MPEG-2。
3. Citron 日志**不能**作为硬解证据（Citron 无 envideo/NVDEC 后端，`device_create` 直接失败）。
4. 裁剪日志去掉了 FFmpeg 的 `[ffmpeg]` 行；需要完整原始日志用于排查时应回到用户回传的 581,748 B 原件。
