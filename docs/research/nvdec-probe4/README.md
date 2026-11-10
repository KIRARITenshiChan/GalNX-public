# NVDEC 探针 probe4：CPU 直读 block-linear 表面（源码与配方）

本目录保存 probe4 的**自有代码**（不包含 envideo / FFmpeg 上游源码，pin 见 `docs/research/nvdec-probe3/README.md`）。
许可：envideo GPL-2.0、envideo 版 FFmpeg 启用 `--enable-gpl` ⇒ 探针/未来 NSP 若分发构成 GPL 组合（自用无碍，公开分发需附源码）。
本目录代码仅作研究记录。

## 为什么有 probe4

probe3 真机日志（`docs/milestones/evidence/P36-nvdec-probe4/nvdec-probe3-device.txt`）：

```
frame=1 pts=33ms dec=1.67ms xfer=20000.25ms conv=35.35ms hw=1 1920x1080
progress: frames=7 fps=0.10 hw=7 sw=0
```

结论：**NVDEC 解码在真机可用（1.67 ms/帧）**，但 `av_hwframe_transfer_data()`（Copy Engine tiled→linear）
首帧 20.000 s、后续 ~10 s/帧，且目标缓冲内容错误（整屏绿 + 顶部约 17% 扫描线乱码）。
Horizon 上 NVDEC 帧的 envideo map 是 CPU 可写主机内存（`device.cpp:794-797 #if defined(__SWITCH__) this->map_cpu();`），
所以 probe4 干脆**绕过 Copy Engine**：等解码 fence → CPU 读 block-linear 字节 → 软件 de-tile → PSNR 标定布局。

## 文件

| 文件 | 作用 |
| --- | --- |
| `include/galnx_probe4.h` / `source/galnx_probe4.c` | de-tile 候选布局扫描 + PSNR + NV12→RGBA + 落盘 |
| `include/galnx_swref.h` / `source/galnx_swref.c` | 纯软解参考帧（显示序 1/30，planar YUV420P） |
| `source/galnx_nvdec.c` / `include/galnx_nvdec.h` | probe3 的解码/上屏层，新增 `probe_mode` 分叉与 1 基帧号 |
| `source/main.cpp` | 设备侧实验入口（软解参考 → NVDEC 探针 → SDL 上屏 → 报告） |
| `Makefile` | devkitPro Makefile（`TARGET=nvdec-probe4`、`APP_TITLEID=01000000000000A4`） |

## 数据流

1. `galnx_swref_collect(path, {1,30})` 软解出 2 帧参考（实测 1080p VC-1 两帧 655.4 ms）。
2. `galnx_nvdec_open()` 打开同一文件，`galnx_nvdec_set_probe(prefix, {1,30}, 2)` 打开探针分叉：
   目标帧不再 `av_hwframe_transfer_data`，而是交 `galnx_probe4_handle()`。
3. `galnx_probe4_handle()`：
   - `AVHWFramesContext *fc = f->hw_frames_ctx->data`；`AVEnvideoDeviceContext *ec = fc->device_ref->data->hwctx`；
   - `AVEnvideoFrame *ev = f->buf[0]->data`；`map = envideo_map_from_fence(...)` 不可用时走 `f->data[0]` 的 map；
   - **先 `envideo_fence_wait(ec->device, ev->fence, 5000000ULL)`** 并记录 rc/耗时（判据：解码是否真的完成）；
   - `envideo_map_cache_op(map, off0, msize-off0, EnvideoCache_Invalidate)`；
   - 候选平面 1 偏移 ∈ {实测 `f->data[1]-gpu0`, `stride0*h`, `stride0*align32(h)`} × tile 行高 ∈ {16, 8, 32, 64}
     （共 12 组）逐组 `detile_plane()` 后用亮度 PSNR 与参考帧比对，取最优；
   - 最终落盘 raw 表面 / 参考 YUV / de-tile 后 YUV，并转 RGBA 交给 SDL 上屏与 BMP。

`detile_plane(dst, dst_stride, src, width_bytes, height_rows, tile_rows, avail)` 的布局假设：
tile 宽固定 64 B，`tiles_per_row = width_bytes / 64`，band 高 = `tile_rows`，band 内 tile 行优先
（`src_off = (band * tiles_per_row + t) * 64 * tile_rows`），tile 内按行 `memcpy(..., 64)`。

## 构建

```bash
# 唯一姿势：devkitPro MSYS2（git-bash 里没有 /opt/devkitpro 的库搜索路径）
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  'cd /e/galnx-build/nvdec/probe4 && make -j8'
```

依赖：`libenvideo.a` + FFmpeg（envideo 分支）静态库，构建配方与 pin 见 `docs/research/nvdec-probe3/README.md`。
产物（2026-11-08 实测，一次编译通过）：

- `nvdec-probe4.nro` 9,420,856 B sha256 `b5acc4ded3991dbcc17e973c9631f5672e3ac9072452d746c50feb5cf3792acd`
- `nvdec-probe4.elf` 18,631,880 B sha256 `e56b76766af7d1320a54318cc511085b3988b11883df31a5702637a2450aeff9`
- `nvdec-probe4.nacp` 16,384 B sha256 `7045f12bb07c5e9b5400b75c7ff772950a6b0ad35e0184afc51c9e1f26b40e98`

## 运行（真机）

```
sdmc:/switch/nvdec-probe4.nro
sdmc:/nvdec-poc.wmv          # 1080p VC-1 (WMV3)，46,606,544 B sha 923c3321…
```

产物：`sdmc:/nvdec-probe4.txt`、`-f001/-f030-raw.bin`、`-ref.yuv`、`-detiled.yuv`、`-f001/-f030.bmp`。
成功判据：日志 `chosen: tile_rows=.. psnrY=..` 中 `psnrY` 高（>40 dB 可用，99 = 逐字节相同），BMP 人像清楚不绿。
