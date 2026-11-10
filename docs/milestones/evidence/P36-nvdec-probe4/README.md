# P36 — NVDEC probe4（CPU 直读 block-linear 表面）证据

采集日期：2026-11-08。关联记录：`docs/builds/041-nvdec-probe3.md`、`docs/builds/042-nvdec-probe4.md`、
`docs/research/nvdec-probe4/`。

## 文件

| 文件 | 来源 | 说明 |
| --- | --- | --- |
| `nvdec-probe3-device.txt` | 用户在真机运行 `nvdec-probe3.nro` 后回传（504 B / 12 行） | **probe4 的立项依据**：`dec=1.67ms` 但 `xfer=20000.25ms`，`hw=7 sw=0`，`fps=0.10` |
| `nvdec-probe4.txt` | Citron `0237a9b88` 运行 `nvdec-probe4.nro` 的探针日志（裁剪版） | 原始 729,255 B / 10,389 行，其中 10,229 行 `[ffmpeg] ...` 库日志已删，保留 160 行（仅加头部注释） |
| `citron-result.json` | `scripts/citron_run.sh` 输出 | `status=loaded`、`CITRON_RC=0`、截图 nonblack_ratio 0.9998 |

## 这份证据能证明什么

1. probe3 **真机**：NVDEC 硬解本身可用（1.67 ms/1080p 帧）；Copy Engine 的 tiled→linear 转换不可用（20 s/帧、内容错误）。
2. probe4 探针程序在模拟器（Citron，无 NVDEC）上**链路完整**：软解参考帧采集成功（`swref: found=2 … 655.4 ms`）、
   SDL 窗口/渲染器/纹理创建成功、120 帧解码循环无异常、退出码 0 并打印 `=== DONE ===`。

## 这份证据**不能**证明什么

- Citron 没有 NVDEC，日志中全部是 `hw=0`，因此 **probe4 的 hw 分支（fence 等待、CPU 直读、de-tile、PSNR 标定）
  一行都没被执行**；该分支只有真机运行 `nvdec-probe4.nro` 才能验证。
- 截图 `citron-window-p03.png` 是**程序退出后**抓的 Citron 窗口（只剩游戏列表），不能当作渲染正确性的证据；
  所以本目录没有放 probe4 的截图。渲染正确性判据仍是真机回传的 `-f001/-f030.bmp`。
