# P38 — NVDEC 探针 probe6 证据（nvtegra 路线，Citron 冒烟 + PC 对照）

对应记录：`docs/builds/044-nvdec-probe6.md`；源码：`docs/research/nvdec-probe6/`。

## 这些文件能证明什么

| 文件 | 能证明 |
| --- | --- |
| `nvdec-probe6-citron.txt`（11,120 B，去 `[ffmpeg]`） | Citron 上 probe6 全链路可运行：`hw: nvtegra device created`（仅上下文创建）、`hw: frames ctx 1920x1080 format=nvtegra sw=nv12`、软解 120 帧 `hw_frames=0`、目标帧 BMP 写出、`PROBE6 verdict: hw=SOFTWARE-ONLY`、`=== DONE ===` |
| `citron-result.json`（2,510 B） | Citron harness 单行结果（返回码、窗口、截图、日志切片） |
| `probe6-citron-f001.png`（8,591 B） | Citron 软解显示序第 1 帧：**纯白**（mean 255 / std 0） |
| `probe6-citron-f030.png`（1,148,567 B） | Citron 软解显示序第 30 帧：正常画面（mean ≈ [150.7,177.7,166.3]、std 68.06） |
| `pcframe-01.png`（8,656 B） | PC ffmpeg 9.0 解同一素材显示序第 1 帧：同样纯白 ⇒ 白帧来自片源，不是探针 bug |
| `pcframe-03.png`（453,979 B） | PC ffmpeg 9.0 显示序第 30 帧（降采样 960×540）：彩色正常，用于与 Citron 帧对照 |
| `SHA256SUMS` | 上述文件哈希 |

## 这些文件不能证明什么

1. **不能**证明 nvtegra 硬解在真机可用 —— Citron 没有 NVDEC，`hw=0`，结论必须等真机日志。
2. Citron 上 `hw: nvtegra device created` **不代表**硬解可用（device/frames 上下文可创建，解码帧仍是软件帧）。
3. PC 帧与 Citron 帧不同源（一个 PC ffmpeg 软解、一个探针软解），只能用于「是否白帧」的定性对照，不能当逐像素校验。
4. 本目录尚无真机证据；真机结果回传后另建 `P39`（或补入本目录并更新本 README 的证明边界）。
