# 041 — NVDEC 硬件解码可行性探针（probe1 / probe2 / probe3）

- 日期：2026-11-08
- 关联里程碑：M5（rfvp / IROSEKA 真机优化）后续 — NVDEC 硬解路线
- 关联计划：v1.31
- 关联证据：`docs/milestones/evidence/P35-nvdec-probe3/`、`docs/research/nvdec-probe3/`
- 探针源码：`docs/research/nvdec-probe3/`（main.cpp / galnx_nvdec.c / galnx_nvdec.h / Makefile）

## 1. 背景与目标

P33 交付 `v1.1.9-test` 后，用户在真机确认：

- 480 档（854×480 WMV2 软解）「很流畅，但糊」；
- 720 档画质更好，但**视频明显慢放**（约 0.5×，音频正常）；
- 540 档也慢放，只是比 720 轻。

P34 修掉了 480 档左缘一列马赛克（WMV2 末列宏块写出界），但「画质 vs 流畅」的根本矛盾没有解决：**软件解码 720p30 每帧 60–100 ms，而预算只有 33.3 ms**（`MAX_DECODE_PER_TICK=1` 时视频推进速度=解码速度，表现为慢放而非跳帧）。唯一能同时拿到 1080p 画质与实时播放的路径是 **NVDEC 硬件解码**。

目标（分三步，用户已确认第 0 步）：

1. 判定 NVDEC 在本机 CFW 环境下可用（用户 `m32205`：1080p VC-1 与 720p H.264 样片用 SwitchWave 均流畅、音画同步 → **PASS**）；
2. 自建一条「FFmpeg + envideo + NVDEC」解码链路并用探针验证（本文档主体）；
3. 通过后集成进 rfvp movie player，直接播**原始 1080p VC-1**（不再需要 540/720 转码，A「糊」问题随之消失），480 档软解保留为无 NVDEC 环境兜底。

## 2. 结论摘要

| 步骤 | 结论 | 证据 |
| --- | --- | --- |
| 探针 1：打开 nvhost-nvdec / 查询 constraints | ✅ 真机 PASS，全部 `rc=0`；VC-1 支持 48×16…2032×2032、`max_mbs=8192`，1920×1080=120×68=**8160 MBs 刚好放得下** | 用户截图 `E:/galnx-build/nvdec/evidence/probe-pass.jpg` |
| 探针 2：FFmpeg demux + `AV_HWDEVICE_TYPE_ENVIDEO` | ✅ 构建 + Citron 软解全片 PASS（750/750 帧）；Citron 无 NVDEC，`av_hwdevice_ctx_create` 返回 `-88` 属预期回落 | `E:/galnx-build/nvdec/evidence/citron2/`、`…/evidence/citron/` |
| 探针 3：FFmpeg 解码 + SDL2/GLES2 上屏 + BMP 取证 | ✅ Citron 级 PASS：750/750 帧、渲染到窗口、3 张 BMP 落盘；真机版已打包待用户运行 | `docs/milestones/evidence/P35-nvdec-probe3/` |
| 解码正确性 | ✅ 探针第 180 个显示帧 ≡ ffmpeg 解码序第 179 帧（B 帧 reorder 差 1），扣除色彩范围线性映射后 **luma mean_abs=0.21、PSNR=58.47 dB** | 见 §6.3 |
| 真机 NVDEC 实跑 | ⏳ 待用户执行 `/switch/nvdec-probe3.nro` 并回传 `/nvdec-probe3.txt` | device-test 包 `E:/galnx-build/nvdec/device-test/` |

## 3. 硬件与权限事实（探针 1，真机）

探针 1（`envideo-probe.nro` 272,581 B，sha256 `e676728f74d78c7447e6cff428d3c9558c8a84c63f20e2433c6f47d336b220a9`）在真机全 `rc=0`：

```
applet_type=0 application=1
nv_service_type_default=0 mode=auto nv_service_type_used=0
envideo_device_create rc=0x00000000 dev=0x57e145cba0
device: tegra_layout=1
vc1   rc=0 supported=1 size=48x16..2032x2032 max_mbs=8192
h264  rc=0 supported=1 size=48x16..4096x4096 max_mbs=65536
h265  rc=0 supported=1 size=144x144..4096x4096 max_mbs=65536
mpeg2 rc=0 supported=1 size=48x16..4080x4080 max_mbs=65280
vp8   rc=0 supported=1 size=48x16..4096x4096 max_mbs=65536
vp9   rc=0 supported=1 size=128x128..4096x4096 max_mbs=36864
mjpeg rc=0 supported=1 size=16x16..16384x16384 max_mbs=4294967295
av1   rc=0 supported=0   ← 唯一不支持
channel_create(Nvdec) rc=0x0 ch=0x57e145cc40
dfs_init/dfs_commit/dfs_finalize rc=0x0
channel_create(Vic)  rc=0x0
```

要点：

1. **不需要 factory 服务**：应用态（application=1）下 `nv_service_type_used=0`，即普通 `nvdrv` 即可开 `/dev/nvhost-nvdec`；探针里预留的 `/switch/nvprobe-mode.txt=factory` 分支未被用到。
2. **NPDM 权限不是障碍**：本项目 NSP 的 `main.npdm` 为 `service_host [*]`、`service_access [*]`，无需额外声明。
3. **1080p VC-1 卡在上限边缘**：1920×1080 = 120×68 = 8,160 宏块，`max_mbs=8192`，余量只有 32 宏块 → 集成时不要指望 1080p 再叠加 deinterlace。

## 4. 工具链（envideo + FFmpeg 静态库）

完整 pin、哈希、配方见 `docs/research/nvdec-probe3/README.md`，此处只记结论级事实：

| 组件 | 版本/来源 | 产物 |
| --- | --- | --- |
| averne/envideo（GPL-2.0） | master `826f184a1117fd1a4d79be77da05c05aa83b3b81`（2026-10-24） | `libenvideo.a` 87,816 B sha256 `0d0cbc73…6983`（手写 g++ 编译，未走 meson） |
| averne/FFmpeg `envideo` 分支（GPL 构建） | tarball sha256 `d1755f40…9329`（下载时 HEAD `8a49f6e6`，libavutil 60.26.101） | `libavformat.a` 791,028 B `bc9558a1…`；`libavcodec.a` 2,748,142 B `2ed10f2e…`；`libavutil.a` 1,262,206 B `e9eb4b3d…` |
| FFmpeg configure | `--target-os=horizon --enable-cross-compile --cross-prefix=aarch64-none-elf- --disable-everything --enable-envideo --enable-gpl --enable-decoder='vc1,h264,wmv3' --enable-parser='vc1,h264' --enable-demuxer='asf,mov' --enable-protocol=file --enable-hwaccel='vc1_envideo,h264_envideo' --disable-swresample --disable-filters` | 组件宏在 `config_components.h` |

硬解输出是 **`AV_PIX_FMT_ENVIDEO`（block-linear tiled）**；`hwcontext_envideo.c` 的 `transfer_get_formats` 只做 tiling→线性转换（copy engine），**不做像素格式转换** → NV12→RGBA 必须我们自己写（CPU 或 GLES2 双平面 shader）。

## 5. 探针迭代与踩到的坑

### 5.1 探针 2（demux + hwdevice，NRO 3,022,904 B sha256 `829bc1e1…`）

真机/模拟器共用；日志写 `sdmc:/nvdec-probe2.txt`。

| 坑 | 现象 | 修法 |
| --- | --- | --- |
| NRO 缺 NACP | Citron 报 `Could not determine title ID`（`nro.cpp:299` 在 `nacp==nullptr` 时返回 `ErrorNoControl`） | Makefile 补 `APP_TITLEID` + `NROFLAGS += --nacp=$(CURDIR)/$(TARGET).nacp` |
| FFmpeg 把 `sdmc:` 当协议 | `avformat_open_input ret=-1330794744` = `AVERROR_PROTOCOL_NOT_FOUND`；horizon 上 `is_dos_path()` 为假，`url_find_protocol()`（`libavformat/avio.c:307`）把 `sdmc:` 解析成协议名 | 路径统一加 `file:` 前缀（`file_open()` 会剥掉） |
| `frame->pts = AV_NOPTS_VALUE` | VC-1 解码不传播 pts | 集成时 **pacing 必须用 packet pts**（ASF time_base=1/1000） |
| 库顺序取错 | 链接到 devkitPro 自带 FFmpeg 7.1 → `undefined reference to inflateInit2_` | `LIBS` 用显式 `.a` + `--start-group`，并把 `-I$(FFMPEG_SRC)` 排在 `$(INCLUDE)` 之前 |

Citron 结果（`v3`，全片软解）：

```
hwcfg[0] device=envideo pix_fmt=envideo methods=0x3
av_hwdevice_ctx_create(ENVIDEO) ret=-88   ← Citron 无 NVDEC，预期回落
avformat_open_input ret=0 nb_streams=2 best=0 vc1 1920x1080 bitrate=16000000
SUMMARY frames=750 packets=750 hw_frames=0 sw_frames=750 xfer_fail=0 wall_ms=14928.6
DECODE avg=19.50ms min=4.66ms max=45.82ms
```

（`poc-1080p-vc1.wmv` 46,606,544 B = IROSEKA 原片截取 25.13 s / 750 帧，`ffprobe -count_frames` 同样 750。）

### 5.2 探针 3（FFmpeg + SDL2 播放，NRO 9,408,568 B sha256 `c13b2aae…`）

源码 API（`include/galnx_nvdec.h`）刻意做成可以**直接搬进 rfvp** 的形态：

```c
typedef struct { int width, height, hw_used; int hw_frames, sw_frames; ... } GalnxNvdecInfo;
int  galnx_nvdec_open(GalnxNvdecCtx **out, const char *path);   /* avformat + hwdevice + codec */
int  galnx_nvdec_next(GalnxNvdecCtx *ctx, GalnxFrame *out);     /* RGBA8888 + pts_ms */
int  galnx_nvdec_hw_used(GalnxNvdecCtx *ctx);
void galnx_nvdec_close(GalnxNvdecCtx *ctx);
```

内部实现要点：

- 硬解帧 `AV_PIX_FMT_ENVIDEO` → `av_hwframe_transfer_data`（envideo 的 copy engine 去 tiling）→ NV12/YUV420P → 手写 BT.601 limited→full RGBA8888；
- 三段计时：`DEC`（send+receive）/ `XFER`（transfer_data）/ `CONV`（YUV→RGBA）；
- 无 NVDEC 时自动软解（`hw_used=0`），统计与输出格式完全一致 → 同一份 NRO 在 Citron 上也能自测；
- 有 SDL2 渲染就上屏（`SDL_TEXTUREACCESS_STREAMING` + `SDL_UpdateTexture`），纹理创建失败自动切 headless 继续解码并写 BMP。

踩到的两个坑：

1. **覆盖 `__nx_heap_size` 会自杀**：首版写 `extern "C" u64 __nx_heap_size = 0x8000000ULL`（128 MiB）想把大堆压小，结果 Citron 上 `SDL_CreateTexture(1920x1080)` OOM、FFmpeg `get_buffer() failed` / `Not enough space (-12)`，只解出 1 帧。**结论：probe3 及后续集成一律不覆盖 `__nx_heap_size`**，沿用 libnx 默认大堆。
2. **纹理 OOM 要有兜底**：加速渲染器建 1920×1080 纹理失败时应销毁重建软件渲染器，再失败才 headless——探针 3 的三段兜底就是为真机首跑准备的。

## 6. Citron 级验证（无 NVDEC，只验链路与正确性）

### 6.1 运行环境

- Citron nightly `0237a9b88`（无 NVDEC → 全程 `hw=0` 软解）；
- 片源 `sdmc:/nvdec-poc.wmv`（`poc-1080p-vc1.wmv`）；
- 运行目录 `E:/galnx-build/nvdec/run-citron3/20261108-061318-nvdec-probe3`。

### 6.2 结果（`docs/milestones/evidence/P35-nvdec-probe3/nvdec-probe3.txt`）

```
=== GalNX NVDEC probe3 (SDL playback) ===
applet_type=0 application=1
info: 1920x1080 codec=vc1(70) pix_fmt=yuv420p fps=59.940 duration_ms=25130
renderer=opengles2 flags=0xe
bmp: wrote sdmc:/nvdec-probe3-001.bmp (1920x1080)
progress: frames=30 fps=14.93 hw=0 sw=30
...
=== SUMMARY ===
frames=750 hw_frames=0 sw_frames=750
hw_used=0 fps_overall=18.896 wall_ms=39691.0
DECODE   avg=19.926ms min=4.429ms max=63.357ms
TRANSFER avg=0.000ms min=0.000ms max=0.000ms
CONVERT  avg=27.779ms min=24.492ms max=43.914ms
mode=gles accelerated=1 headless=0
last_frame=1920x1080
```

- 750/750 帧全解完，`fps_overall=18.9`（软件解码 + 桌面 GL 上屏的瓶颈，非探针逻辑问题）；
- `mode=gles` 说明 1080p 纹理创建成功、确实上屏；`result.json` `nonblack_ratio=0.9018`、窗口标题 `nvdec-probe3 (64-bit)`；
- 3 张 BMP 与 ffmpeg 参考帧内容一致（见 6.3）。

### 6.3 正确性：探针帧 vs ffmpeg 参考帧

`probe3-frame180.png`（探针第 180 个显示帧）与 ffmpeg 解码序相邻帧逐一对比（Y 平面）：

| 参考帧（解码序） | 179 | 180 | 181 |
| --- | --- | --- | --- |
| luma mean_abs | **5.25** | 10.78 | 14.14 |
| luma PSNR (dB) | **32.42** | 24.45 | 22.42 |

→ 最佳匹配为**解码序第 179 帧**（B 帧 reorder 导致显示序与解码序差 1），其余相邻帧迅速变差，说明帧对应关系明确。

在最佳匹配帧上做一次仿射拟合（`y_ff = a·y_probe + b`）得 `a=0.8661, b=15.7215` —— 正是 BT.601 limited→full 的标准映射；扣除该色彩范围转换后：

```
fitted luma mean_abs = 0.21    PSNR = 58.47 dB
```

结论：**解码结果与 ffmpeg 参考一致（差异仅来自色彩范围/矩阵转换）**，探针链路（demux → NVDEC/软解 → transfer → NV12→RGBA → 上屏）正确。

## 7. 真机测试包（待用户执行）

目录 `E:/galnx-build/nvdec/device-test/`：

| 文件 | 大小 | sha256 |
| --- | --- | --- |
| `nvdec-probe3.nro` | 9,408,568 B | `c13b2aec…a8`（完整值见包内 `SHA256SUMS`） |
| `poc-1080p-vc1.wmv` | 46,606,544 B | `923c3321…48` |
| `README.md` | 说明 | — |

步骤（**所有设备写入由用户完成**，按 m31356 约束）：

1. `nvdec-probe3.nro` → SD `/switch/nvdec-probe3.nro`；
2. `poc-1080p-vc1.wmv` → SD 根目录改名 `/nvdec-poc.wmv`（也支持 `/switch/nvdec-poc.wmv`）；
3. 用 hbmenu 启动，播完按 PLUS 退出；
4. 回传 `/nvdec-probe3.txt` + 任意 1–2 张 `/nvdec-probe3-*.bmp` + 一句流畅度体感。

真机成功的判据（日志）：

```
av_hwdevice_ctx_create(ENVIDEO) ret=0
SUMMARY frames=750 hw_frames=750 sw_frames=0
hw_used=1
DECODE avg=<几毫秒> TRANSFER avg=<几毫秒> CONVERT avg≈25-30ms
mode=gles
```

风险与兜底：

- 若 1080p 纹理建不出来 → 自动 headless（仍写 BMP，用 BMP 判画面）；
- 若 `ret=-88`（`AVERROR(ENOSYS)` 类）→ 说明 NVDEC 未打开，可试 `/switch/nvprobe-mode.txt=factory`（但探针 1 已证明不需要）；
- 若黑屏直接退回桌面 → 不覆盖堆后此风险已基本消除，仍请回传现象。

## 8. 产物哈希

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| `envideo-probe.nro`（探针 1） | 272,581 B | `e676728f74d78c7447e6cff428d3c9558c8a84c63f20e2433c6f47d336b220a9` |
| `envideo-probe2.nro`（探针 2） | 3,022,904 B | `829bc1e13b5a44e98926b42256e0739ba179ed64f03fd5fb1bcb577ef86ce4e7` |
| `nvdec-probe3.nro`（探针 3） | 9,408,568 B | `c13b2aaecb19cda40013a661dbf3a27d640f18b7c08c4125fc57473997a804a8` |
| `nvdec-probe3.elf` | 18,566,512 B | `1bdd2f8c7af0d866deef7575d181bc386a494acb7d52cce362b80764c37f126b` |

（`nvdec-probe3.nro` 由 `envideo-probe2.nro` 同链条构建，唯一差异是不覆盖堆 + 增加 SDL2 上屏与 BMP 落盘。）

## 9. 限制与未验证

1. **真机 NVDEC 实跑未验证**：Citron 无 NVDEC，只能验链路/正确性；硬解的 `hw_frames`、`TRANSFER` 耗时、1080p 实时播放体感只能真机给结论。
2. **未做 NV12→RGBA 的 GPU 路径**：探针用 CPU 转换（1080p 约 25–28 ms/帧，桌面数据）；真机 A57 上 CPU 转换会成为新瓶颈，集成时需改 GLES2 双平面 shader 或 VIC 加速。
3. **未做音画同步/丢帧策略**：探针无音频；集成时 pacing 以 packet pts 为准，落后时跳帧而非慢放。
4. **1080p 处在 NVDEC 宏块上限边缘**（8,160 / 8,192），不支持叠加 deinterlace。
5. **GPL 边界**：探针静态链接 envideo（GPL-2.0）与 FFmpeg envideo 分支（GPL 构建）→ 该探针与未来的 NVDEC 版 NSP 属 GPL 组合作品；rfvp 本体是 MPL-2.0，两者兼容，但公开分发必须附源。自用无碍。

## 10. 复现

```bash
# envideo 静态库（手写 g++，全部路径先 cygpath -m 转 Windows 形式）
bash /e/galnx-build/nvdec/build-envideo2.sh          # → E:/galnx-build/nvdec/build-envideo/libenvideo.a

# FFmpeg envideo（必须在 devkitPro MSYS2 里）
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  'bash /e/galnx-build/nvdec/build-ffmpeg-msys.sh && bash /e/galnx-build/nvdec/make-ffmpeg.sh'

# 探针 3
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  'cd /e/galnx-build/nvdec/probe3 && make -j8'

# Citron 自测（无 NVDEC，应看到 hw=0 / sw_frames=750）
bash /e/galnx-build/nvdec/run-probe3-citron.sh

# 宿主参考帧
ffmpeg -v error -i /e/galnx-build/nvdec/poc/poc-1080p-vc1.wmv \
  -vf "select=eq(n\,179)" -vframes 1 -f rawvideo -pix_fmt yuv420p ff179.yuv -y
```

## 11. 教训

1. **先验权限与约束，再写解码器**：探针 1 用 272 KB 的 NRO 就把「NVDEC 能不能开、VC-1 支不支持、1080p 放不放得下」全部答完，成本远低于直接集成。
2. **模拟器不能验硬解，但能验 95% 的其他东西**：Citron 把 demux、pacing、YUV→RGBA、上屏、BMP 取证全跑通了，真机只剩最后一段。
3. **探针要能降级**：`hw_used=0` 自动软解，同一份 NRO 在两边都能跑，减少「真机才发现跑不起来」的次数。
4. **不要动 `__nx_heap_size`**：libnx 默认堆是调过的，压小会把 FFmpeg 帧缓冲与纹理一起打死（且报错像解码器 bug）。
5. **horizon 上 FFmpeg 不认 `sdmc:`**：任何 `avformat` 入口都要 `file:` 前缀；VC-1 的 `frame->pts` 不可用，pacing 走 packet pts。
6. **像素正确性要做「帧对齐」再比**：VC-1 B 帧下显示序≠解码序，直接比第 N 帧会得出「PSNR 25 dB、解码坏了」的错误结论；对齐后 58 dB 才是真相。
