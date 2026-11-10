# 044 — NVDEC 探针 probe6：改用 averne/FFmpeg 的 nvtegra 硬解

- 日期：2026-11-08
- 关联：`docs/builds/043-nvdec-probe5.md`（envideo 参考解码真机 PASS）、`docs/builds/042-nvdec-probe4.md`、`docs/research/nvdec-probe6/`、`docs/milestones/evidence/P38-nvdec-probe6/`
- 上游：averne/FFmpeg 分支 `nvtegra` tip `caeec83b791be08ed43468a2ef426d6901d51c78`（2024-10-06，nvtegra/filter: update for ffmpeg 7.1）

## 1. 背景：probe5 把问题域二分开

| probe5 结果 | 含义 |
| --- | --- |
| Phase A（envideo 原生 MPEG-2 128×128，真机） | **PASS**：`mbs_ok=64 cycles=5042`、哈希 = 官方期望 `a2c4a330592602d5` |
| Phase B（FFmpeg envideo + VC-1 1080p，真机） | **FAIL**：fence 2 s 不 signal、表面全 0、`AVERROR_UNKNOWN`（`envideo_decode.c:255`） |

⇒ 硬件、Copy Engine、tiled 布局、cache 操作、fence 全都没问题；失败点在 **FFmpeg 的 envideo VC-1 封装路径**，
而 envideo 上游没有任何 FFmpeg hwaccel 自测覆盖。继续修 envideo 封装收益不确定。

平行事实：averne/FFmpeg 的另一分支 **nvtegra** 是社区成熟路线 —— SwitchWave 1.1.2（`devkitpro/devkita64:20260215`）
以 `--enable-nvtegra` 构建，并在用户真机上实际播放过 1080p VC-1（window 内可见）。因此在 probe5 之后选择：
**先用 nvtegra hwaccel 复验同一条 VC-1 素材**。如果它 hw=1 且 PSNR 高，就可以直接进播放器集成，不必再回头修 envideo。

## 2. 结论摘要

| 项 | 结果 |
| --- | --- |
| nvtegra 分支 FFmpeg 交叉编译 | ✅ 成功（先修 `__SWITCH__` 缺失，见 §4） |
| probe6 源码 | ✅ 完成并通过 Citron 链路冒烟（软件降级路径完整） |
| probe6 产物 | `nvdec-probe6.nro` 9,117,752 B `92e1796a…` |
| Citron 硬解 | ❌ 不可用（能在 Citron 创建 nvtegra device/frames，但解码帧 `hw=0`）—— 符合预期，Citron 无 NVDEC |
| 片头白帧疑点 | ✅ 排除：PC ffmpeg 9.0 解同一 wmv，显示序第 0/1 帧同样纯白，第 30 帧彩色 ⇒ 片源白闪 |
| 真机验证 | ⏳ device-test-v6 已交付，等用户回传 txt + 2 BMP |

## 3. nvtegra 路线要点

| 事实 | 说明 |
| --- | --- |
| 分支树 | `libavcodec/nvtegra_decode.c/.h` + `nvtegra_{h264,hevc,mjpeg,mpeg12,mpeg4,vc1,vp8}.c` |
| 配置开关 | `--enable-nvtegra`、`--enable-hwaccel=vc1_nvtegra,wmv3_nvtegra` |
| 像素格式 | `AV_PIX_FMT_NVTEGRA`（hw frame），`sw_format=NV12` |
| 设备类型 | `AV_HWDEVICE_TYPE_NVTEGRA` |
| 与 envideo 的区别 | envideo 是「envideo 库 + FFmpeg 薄封装」，nvtegra 直接在 FFmpeg 内操作 nvmap/NVDEC；后者的 VC-1 路径已被 SwitchWave 真机使用 |
| 许可 | FFmpeg 构建带 `--enable-gpl`（与 probe5 相同），仅内部研究，不分发 |

## 4. FFmpeg 交叉编译（含一个关键坑）

构建脚本：`docs/research/nvdec-probe6/build-ffmpeg-nvtegra-msys.sh`（工作副本 `/e/galnx-build/nvdec/build-ffmpeg-nvtegra-msys.sh`）。

```text
--target-os=horizon --enable-cross-compile --cross-prefix=aarch64-none-elf-
--host-cc=D:/Scoop/apps/mingw/current/bin/gcc.exe --arch=aarch64 --cpu=cortex-a57 --enable-neon
--enable-gpl --enable-nvtegra
--enable-decoder=vc1,h264,wmv3 --enable-parser=vc1,h264
--enable-demuxer=asf,mov --enable-protocol=file
--enable-hwaccel=vc1_nvtegra,wmv3_nvtegra
--extra-ldflags="-fPIE -specs=/opt/devkitpro/libnx/switch.specs -L/opt/devkitpro/libnx/lib"
```

**坑（首次构建失败）**：

```
libavutil/nvhost_ioctl.h:27:13: fatal error: linux/ioctl.h: No such file or directory
  → libavcodec/nvtegra_decode.c、nvtegra_vc1.c
make: *** [.../ffbuild/common.mak:81: .../nvtegra_decode.o] Error 1
```

根因：`nvhost_ioctl.h` 是 `#ifndef __SWITCH__ / #include <linux/ioctl.h> ... #else #include <switch.h> #endif`，
而 devkitA64 的 `aarch64-none-elf-gcc` **不会自动定义 `__SWITCH__`**，也不默认带 libnx 头文件目录。

修法（脚本第 22 行）：

```text
--extra-cflags="-D__SWITCH__ -D_GNU_SOURCE -D_POSIX_VERSION=200809L -isystem /opt/devkitpro/libnx/include -O2 -fPIC"
```

参照：`research/SwitchWave-master/Makefile` 第 44/93/98/110 行同样用 DEFINES(`__SWITCH__ _GNU_SOURCE _POSIX_VERSION=200809L timegm=mktime …`) + export CFLAGS。

结果：`/e/galnx-build/nvdec/ffmpeg-build-nvtegra/` 下 `libavcodec.a` 2,477,152 B、`libavformat.a` 733,444 B、`libavutil.a` 1,128,760 B。

## 5. probe6 工程

工程目录 `/e/galnx-build/nvdec/probe6`（由 probe5 复制后裁剪，源码归档 `docs/research/nvdec-probe6/`）：

| 文件 | 作用 |
| --- | --- |
| `source/galnx_nvdec.c`（17,289 B） | FFmpeg 解码封装：`init_hw` 里 `av_hwdevice_ctx_create(AV_HWDEVICE_TYPE_NVTEGRA)` → `av_hwframe_ctx_alloc` → `fc->format=AV_PIX_FMT_NVTEGRA`、`fc->sw_format=AV_PIX_FMT_NV12` → `av_hwframe_ctx_init` → `dec->hw_frames_ctx=av_buffer_ref`；失败打印 `hw: unavailable (%s) -> software decode` 并清硬件引用；`get_format_cb` 有 hwframes 时优先 NVTEGRA；`emit_frame` 以 `f->format==AV_PIX_FMT_NVTEGRA` 判 hw，hw 帧先 `av_hwframe_transfer_data(sw,f,0)` 再转 RGBA（NV12/YUV420P、BT.601/709、limited/full） |
| `source/main.cpp`（14,573 B） | 报告写 `sdmc:/nvdec-probe6.txt`；软解参考帧（显示序 {1,30}）；SDL 1280×720 ABGR8888 窗口；最多 120 帧，每帧记录 `dec/xfer/conv` 与 hw 标记；目标帧写 `sdmc:/probe6-f%03d.bmp` 并与参考算 `psnrY/U/V`；结束打印 `SUMMARY`/`avg`/`PROBE6 verdict: hw=HARDWARE|SOFTWARE-ONLY` |
| `source/galnx_swref.c` | 软解参考帧采集（probe5 复用） |
| `Makefile`（3,093 B） | `TARGET=nvdec-probe6`、`APP_TITLEID=01000000000000A6`，链接 `--start-group libavcodec/libavformat/libavutil --end-group -lSDL2 -lEGL -lglapi -ldrm_nouveau -lnx -lpthread -lstdc++ -lm` |

### 5.1 一个必须修的 bug：frame_index 语义

初版 `frame_index` 只在 hw 帧上自增 ⇒ 在 Citron（软解）上永远不会命中目标帧，`cmp` 与 BMP 全部落空。
改为**显示序计数器**（软解也自增），hw 状态由 `last_hw` 单独报告；这样 Citron 上也能产出 BMP 做像素对照。

### 5.2 构建

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'cd /e/galnx-build/nvdec/probe6 && make -j8'
```

| 产物 | 大小 | SHA-256 |
| --- | --- | --- |
| `nvdec-probe6.nro` | 9,117,752 B | `92e1796a3941b422ee259ba75939e992ccb0f4c1ed63a25b23306f35a9fb0d11` |
| `nvdec-probe6.elf` | 18,291,904 B | `75b6f3575ac6d7fa00f1247aadf3bacec14df435e42b8a29d14fd3ea1113f319` |
| `nvdec-probe6.nacp` | 16,384 B | `6d38784e626cc37d31f6f032f98dd079bbe303b01bfba7be2178edd2df082b9f` |

## 6. Citron 冒烟（两次，第二次为最终 NRO）

脚本 `/e/galnx-build/nvdec/run-probe6-citron.sh`，run dir `/e/galnx-build/nvdec/run-citron6`，证据 `docs/milestones/evidence/P38-nvdec-probe6/`。

```
swref: found=2 1920x1080 time=981.3 ms
hw: nvtegra device created
hw: frames ctx 1920x1080 format=nvtegra sw=nv12
info: 1920x1080 codec=vc1(70) pix=yuvp420p fps=59.940
pkt[0] size=9198 head=c0 82 ...
frame idx=1 ... hw=0 / bmp: sdmc:/probe6-f001.bmp rc=0 / cmp f001: skipped (ref=0x.. nv12=0x0 hw=0x0)
frame idx=30 ... hw=0 / bmp f030 rc=0 / cmp f030: skipped
SUMMARY: rendered=120 hw_frames=0 targets=2 idx=120 elapsed=10027.3 ms
avg: dec=31.82 xfer=0.00 conv=39.46 ms/frame, 11.97 fps
PROBE6 verdict: hw=SOFTWARE-ONLY
=== DONE ===
```

要点：

- **Citron 上 `hw: nvtegra device created` 不能当证据**：device/frames 上下文能创建成功，但解码帧仍是软件帧（`hw=0`）。
- Citron 只能验证「代码路径、软解降级、BMP 写出、退出」这条链路。真正的硬解必须真机。
- 软解性能参考：dec 31.82 ms + conv 39.46 ms ⇒ 约 12 fps（Citron 上本来就不适合当性能基线）。

### 6.1 片头白帧疑点（已排除）

Citron 产出的 `probe6-f001.bmp` 纯白（mean [255,255,255]、std 0.0），`probe6-f030.bmp` 正常（mean [150.7,177.7,166.3]、std 68.06）。
用 PC ffmpeg 9.0 解同一素材对照：

```bash
ffmpeg -v error -y -i poc/poc-1080p-vc1.wmv -vf "select='lt(n,2)+eq(n,30)'" -fps_mode passthrough evidence/pcframe-%02d.png
```

| 帧（显示序） | PC 结果 |
| --- | --- |
| 0 | 纯白（std 0） |
| 1 | 纯白（std 0） |
| 30 | 彩色（mean [142.3,175.4,155.6]、std 67.8） |

⇒ **片源本身以白闪开场**，探针行为正确；不影响真机判据（判据看 f030 与 hw 标记）。
顺带记录：ffmpeg 9.0 已不接受 `-vsync`（`Unrecognized option 'vsync'`），要用 `-fps_mode passthrough`。

## 7. 真机测试包 v6

目录 `E:/galnx-build/nvdec/device-test-v6/`（设备写入按长期约定由用户执行）：

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `nvdec-probe6.nro` | 9,117,752 B | `92e1796a3941b422ee259ba75939e992ccb0f4c1ed63a25b23306f35a9fb0d11` |
| `poc-1080p-vc1.wmv` | 46,606,544 B | `923c33214f145ae47f1f3ee9a425780a26ee56b78236f129ec660e558cbd7948` |
| `README.md` | 4,905 B | `2e508b5f79b3440f9e05f51425850f62912d4279f55a6b8c0e20249a4185ea91` |
| `SHA256SUMS` | 167 B | `f7605b48f068077adfb5327b1da2d9a350bcd2bcb2d54bad313da0e637753fe5` |

安装：NRO → `sdmc:/switch/nvdec-probe6.nro`；wmv → `sdmc:/nvdec-poc.wmv`；hbmenu 启动。
回传：`sdmc:/nvdec-probe6.txt` + `sdmc:/probe6-f001.bmp` + `sdmc:/probe6-f030.bmp`。

判据（README 已列 7 条）：

1. `hw: nvtegra device created`；
2. `frame idx=... hw=1`（至少 f001/f030 命中）；
3. `xfer` 在数十毫秒量级（不是 probe3 的 10,000 ms）；
4. `cmp f030: psnrY > 40`（f001 白帧不作判据）；
5. `avg: fps` 明显高于软解；
6. `PROBE6 verdict: hw=HARDWARE`；
7. BMP 人像清楚、不绿。

## 8. 限制

1. probe6 只是探针：解码输出经 `av_hwframe_transfer_data` 到 NV12 再转 RGBA，多一次拷贝，不代表最终播放器性能；
2. nvtegra 是 FFmpeg 分支（非上游），版本锁在 `caeec83b…`；升级 FFmpeg 需重新验证；
3. 构建带 `--enable-gpl`，分发需附源码；
4. Citron 无法验证硬解，只有真机日志能定论；
5. probe6 仅 VC-1/wmv3/h264 解码器，OP 素材为 VC-1 in ASF，足够，但其他容器需另测。

## 9. 复现

```text
1) 构建 FFmpeg（nvtegra）：bash /e/galnx-build/nvdec/build-ffmpeg-nvtegra-msys.sh（MSYS2）。
2) 构建探针：见 §5.2。
3) Citron：bash /e/galnx-build/nvdec/run-probe6-citron.sh。
4) 真机：按 §7 安装并回传。
```

## 10. 教训

1. **换实现比修实现便宜**：envideo 封装上游零测试覆盖，nvtegra 有真实用户（SwitchWave）⇒ 先换路线再谈修补。
2. 交叉编译缺宏要查头文件条件分支：`linux/ioctl.h` 报错的正解是 `-D__SWITCH__` + `-isystem libnx/include`，不是补 linux 头。
3. 「在模拟器上创建成功」≠ 可用：Citron 能建 nvtegra device/frames 却没有 NVDEC，判据必须落在 `hw=1` 与 PSNR。
4. 探针的帧号语义（解码序 vs 显示序）会决定对照是否成立；帧号错会让整轮实验静默失效。
5. 像素异常先找片源：白帧用 PC 解码器交叉验证一次，避免误判自研代码。
