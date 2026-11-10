# P42 · OP H.264 硬解真机验收证据（v1.2.1-test）

- 日期：2026-11-09
- 设备：NS1 真机（Horizon），被测应用 = IROSEKA FHD v1.2.1-test（NSP 10,087,536,344 B sha256 `16d4cee091cdbe64ba3660344d29e781974b114ac24b60648c51afb2721e162d`）
- 采集方式：MTP **只读**（用户 m36353/m34580 授权；设备写入归用户 m31356），脚本 `E:/galnx-build/p40/mtp-pull-rfvp.ps1`
- 用户回执（m36694）：「颜色正常，播放速度正常。有需要的话你仍然可以从mtp拿log，不过我认为没什么问题了」
- 原始设备文件（本机留档，不入库）：`sdmc:/switch/rfvp/debug_report.txt` 101,342 B / 1,210 行 sha256 `89cef8075186c3438522a5798ce02a11c4b7ba939ca5b10db5946952e784121f`；`sdmc:/switch/rfvp/perf_slow.log` 2,632,802 B / 10,563 行 sha256 `3ae5a16df2a458cf693da2eff015e6f0c22836f0241514f21a96ccbc53e0bb85`

## 能证明

1. OP 走 P40 新增的 NVDEC H.264 路径：`Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4`。
2. 全程硬件解码、无静默回落：decoded 采样 124 行全部 `hw=1`（`hw=0` 计数 0）；`movie h264: end of stream after 3597 frames (3597 hardware)`、`finished flag set (eof=true stash=0 decoded=3597 hw=3597)`。
3. P40b 的 UV 修复不改变时间预算：`decode_us` 1,886–9,264 µs、`convert_us` ≈3.5 ms（720p NEON，与 Citron p50 2.5 ms 同量级）。
4. OP 时段帧率达标：OP 后 `frame 7620: 60.0 fps over the last 60 frames, slowest frame 26.0 ms`，与 v1.2.0-test 的 60 fps 持平。
5. 颜色正确（用户观感），即硬件 NV12 分支的 `uvr + i` / `uvr + i + 8` 步进修复在真机生效。

## 不能证明

1. 只覆盖 720p30 H.264 单资产（IROSEKA 120 s OP）；1080p60、HEVC、其它游戏资产未验。
2. 没有 OP 段逐帧 fps 曲线：`perf_slow.log` 只记录 >25 ms 慢帧且跨会话累积，无法按 OP 段切分。
3. 故事区既有慢帧（大存档、资源加载）与 OP 无关，本证据不涉及，也不代表已优化。
4. 不含 NSP 公开分发合规结论（FFmpeg `--enable-gpl` + nvtegra ⇒ GPL 组合）。

## 文件

| 文件 | 说明 |
| --- | --- |
| `device-debug-report-excerpt.txt` | `debug_report.txt` 的 OP 相关原文摘录（帧率心跳、OP 启动、124 条 decoded 采样、EOS） |
| `device-perf-slow-stats.txt` | `perf_slow.log` 统计（条数/分位/TOP 15 尖峰与阶段分解）+ 跨会话说明 |
| `SHA256SUMS` | 上述两文件的 sha256 |

原始大文件不入库；复核时用 `mtp-pull-rfvp.ps1` 重新拉取（只读）。
