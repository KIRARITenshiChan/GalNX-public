# P39 · nvdec-probe9 证据

## 能证明

1. 真机 NVDEC 硬解全程生效：每帧 `hw=1`，`HARDWARE PROOF: PASS (frames=60 hw=60 sw=0 strict_failed=0)`。
2. 真机 decode-only 297.80 fps（600 帧 2,014.8 ms）、H.264 332.98 fps（200 帧 600.6 ms）。
3. 真机 `av_hwframe_transfer_data` 3.79 ms/帧（C1 120 帧 704.7 ms = 170.29 fps）。
4. 真机 CPU NV12→RGBA 43.54 ms/帧（C2 60 帧 10,900.2 ms = 5.50 fps），是 17 fps 慢放的唯一主因。
5. probe8 的 10.77 fps 是探针日志 IO 污染（probe8 日志 4,922,445 B / 70,478 行 vs probe9 27,860 B / 326 行）。
6. Citron 侧代码路径完好（force-software 全阶段 rc=0、`=== DONE ===`），但 Citron 的 NVDEC 是 HLE，不能证明硬件。

## 不能证明

1. 音频同步、丢帧策略、长时间播放稳定性（OP 仅 25 s）。
2. 真实 CPU/EMC/GPU 频率（`pcvGetClockRate` 在真机返回 `rc=0x00004b59`，读数为 0）。
3. 双平面 NV12 shader 路径的实际成本（本轮未实现，只有估算）。
4. 零拷贝（deko3d/NVN/VIC）路径的可行性。

## 文件

| 文件 | 说明 |
| --- | --- |
| `nvdec-probe9-device.txt` | 真机 `sdmc:/nvdec-probe9.txt`（原件 326 行，去掉 20 行 `[ffmpeg]` TRACE） |
| `nvdec-probe9-citron.txt` | Citron 冒烟日志（原件 302 行，去掉 `[ffmpeg]` 行） |
| `citron-result.json` | Citron harness 结果（CITRON_RC=0、窗口标题、截图信息） |
| `probe9-device-f001.png` / `probe9-device-f030.png` | 真机 BMP 转 PNG（960×540）；f001 纯白=片头白闪，f030 正常彩色 |
| `probe9-citron-f001.png` / `probe9-citron-f030.png` | Citron 软解同帧对照（与 PC ffmpeg 一致） |
| `SHA256SUMS` | 上述文件哈希 |

原图（未降采样）与原始完整日志在 `E:/galnx-build/nvdec/evidence/citron9/` 与用户回传目录，不入库。
