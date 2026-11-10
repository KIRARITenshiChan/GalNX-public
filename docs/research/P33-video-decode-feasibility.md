# P33 OP 视频解码可行性研究（NVDEC 硬解 / H.264 软解）

- 日期: 2026-11-07
- 研究: audit-switch（只读审计 + 本机转码，未在真机操作、未安装任何软件）
- 范围: GalNX rfvp/Siglus Switch 移植的 OP 播放路径（IROSEKA FHD，movie/01.wmv）
- 结论等级: E1=本机实测 / E2=官方文档或源码原文 / E3=第三方项目 README/源码 / E4=推断（未实测）

## 0. 摘要（结论先行）

1. **NVDEC 硬解：技术上可行，但不可作为近期主线依赖。** Switch homebrew 上已存在可用的 NVDEC 实现——averne/FFmpeg 的 `nvtegra` hwaccel（分支 `nvtegra`，SHA `caeec83b791be08ed43468a2ef426d6901d51c78`，2024-10-06，E2），并已被 NXMP、SwitchWave、OpenNOW-Switch 三个项目用于生产（E3）。但它**不在 libnx 官方 API**（E2：libnx v4.12.0 只有 MMU/PCV 的模块 ID 登记），**不在 devkitPro 包**，且该实现是 **GPL-2.0-or-later**（`hwcontext_nvtegra.h` 头 + `--enable-gpl` 构建）。若静态链接进 GalNX 的 NRO，整个分发物将受 GPL-2+ 约束，与主树 MPL-2.0 策略冲突，需用户/Lead 决策。
2. **更划算的近期路线：H.264 720p30 软解。** 本机已用 ffmpeg 9.0 产出 720p30/540p30 H.264 样片（E1，§6）；宿主单线程解码 3.85 ms/帧（≈8.7× 实时），按 A57 相对现代 x86 约 6–10× 降速估算为 23–49 ms/帧（E4），30fps 预算 33.3 ms，**处于临界但值得实测**；且 devkitPro 的 `switch-ffmpeg 7.1-5` 已安装在 D:/devkitPro（E1），无需安装新东西。建议先做 1 人日的真机 bench，再决定 720p 还是 540p。
3. **立即止损**：现有 720p30 WMV2 + 自研 wmv2 解码器（`crates/na_wmv_player`）在真机帧率低（E4，见 docs/builds/038-rfvp-op-playback.md 基线）；换成 H.264 或退回 540p WMV2 都比现状好。
4. **术语更正**：任务书写的「H.264+NVENC 硬解」表述有误。NVENC 是 NVIDIA 的**编码器**（本机转码用），Switch 端对应的是 **NVDEC 解码器**；本报告统一用 NVDEC。
5. **VC-1 硬解不可假设**：素材原片是 VC-1 Advanced（WVC1）。NXMP README 列的硬件解码格式只有 H.264/HEVC/VP8/VP9/MPEG2，无 VC-1（E3）。无论走哪条路线都必须先转 H.264（本报告素材已转好）。

## 1. 现状数据

### 1.1 素材与既有转码（E1/E4）

| 项 | 路径 | 大小(B) | sha256 | 规格 |
| --- | --- | ---: | --- | --- |
| 原片 | /e/galnx-build/p31/game/movie/01.wmv | 244,843,229 | 7e84354badaa94816bab4ece3e07d557c7d1b25fced8983396a747aa7d36a6d3 | ASF/VC-1 Advanced(WVC1) 1920x1080 16Mbps 59.94fps + wmav2 48kHz 192kbps，120.49s |
| P31 720p30 | /e/galnx-build/p31/game/movie720_30/01.wmv | 124,386,038 | 62abe508…（doc 038 记录） | 1280x720 WMV2 8Mbps 29.97fps |
| P31 540p30 | /e/galnx-build/p31/game/movie540_30/01.wmv | 84,808,438 | 76cedf0b…（doc 038 记录） | 960x540 WMV2 5Mbps 29.97fps |
| 音频 | /e/galnx-build/p31/game/movie/01.ogg | 2,343,033 | - | OGG（与 720p/540p 同名配对） |
| P33 720p30 H.264 | E:/galnx-build/p33/research/h264_720p30_8M.mp4 | 113,881,554 | e9ee8fd99f54c62ec93579bcd9fdb83a4959ce335b69d553ae4a2991399309fa | H.264 High L4.0 1280x720 yuv420p 29.97fps 3597帧 7.59Mbps 120.0199s |
| P33 540p30 H.264 | E:/galnx-build/p33/research/h264_540p30_4M.mp4 | 57,289,603 | cc7d14f53c1a5edeb2e396ecda50069184eaad5b9e0d9f523d580cb5bd2517a3 | H.264 High L3.1 960x540 yuv420p 29.97fps 3597帧 3.82Mbps 120.0199s |

### 1.2 性能基线（来自 docs/builds/038-rfvp-op-playback.md，E4）

- 1080p VC-1 软解：宿主 decode 19.97 ms + convert 9.73 ms = 29.7 ms/帧（≈33.7fps 上限）；A57 估算 3–5× → 7–16fps；Citron 实测 1080p60 仅 6fps。
- 720p30 WMV2：宿主 8.98 ms/帧（≈111fps）。540p30 WMV2：宿主 5.37 ms/帧。按 P29 Citron 折算系数 5.6×，540p 真机预计 25–40fps（推断）。
- P31 真机采用 720p30 WMV2 + 同名 OGG；构建必须走 devkitPro MSYS2（env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc ...）。

### 1.3 现有解码与渲染（E2，本地源码 /e/galnx-build/p31/rfvp-v117）

- 自研 WMV2 解码器：`crates/na_wmv_player/src/{api,bitreader,color,decoder,ffi,lib,na_rl_tables,na_simple_idct,na_wmv2dsp}.rs`。
- Switch 渲染：`platform/switch/runtime/sdl_video.c` 使用 SDL_Texture + SDL_Renderer（SDL2）；`platform/switch/host/src/decode.rs`、`render.rs` 为现有接线。
- 全树无 ffmpeg/avcodec 依赖（grep 无命中）→ 接入 H.264 需要新增 C 依赖与 Rust FFI。

## 2. NVDEC 可行性（证据链）

### 2.1 libnx 官方：没有 NVDEC API（E2）

- D:/devkitPro/libnx/include/switch/services/mm.h:15-16：`MmuModuleId_Nvdec = 6`、`MmuModuleId_Nvjpg = 7`（仅 MMU 模块枚举）。
- D:/devkitPro/libnx/include/switch/services/pcv.h:61：`PcvModule_NVDEC = 49`；pcv.h:154：`PcvModuleId_NVDEC = 0x40000032`（仅电源/时钟域）。
- D:/devkitPro/libnx/include/switch/nvidia/ 仅有 GPU 相关：address_space.h、channel.h、fence.h、gpu.h、gpu_channel.h、graphic_buffer.h、ioctl.h、map.h、types.h，ioctl.h 只覆盖 NvhostCtrl/NvhostAsGpu/NvhostCtrlGpu。
- GitHub 仓库 switchbrew/libnx issues 搜索 q=nvdec：0 命中（E1，API search/issues）。

### 2.2 官方文档缺失（E2）

- https://switchbrew.org/wiki/NVDEC 为空页，正文为 "There is currently no text in this page."。
- wiki API `srsearch=NVDEC` 返回 totalhits=0；但同一 API 对 `nvdrv` 也返回 0，说明该搜索索引不可靠；/wiki/Nvhost 被 Cloudflare "Just a moment..." 拦截（curl + 代理 + UA 仍失败）。因此「wiki 无 NVDEC 文档」只能作为参考，不作为否证。

### 2.3 第三方实现存在（E2/E3，关键）

| 资产 | 事实 | 证据 |
| --- | --- | --- |
| averne/FFmpeg 分支 nvtegra | SHA `caeec83b791be08ed43468a2ef426d6901d51c78`，HEAD 提交 2024-10-06T15:26:34Z，提交信息 "nvtegra/filter: update for ffmpeg 7.1"；同仓库还有 envideo `8a49f6e67e2ca3160706f90cde3d06c6709f9542`（2026-08-01）、master `932a872dbc1a300a45b085cd0195ce6ab8e0b3fa` | `git ls-remote https://github.com/averne/FFmpeg`（E1）；GitHub API commits?sha=nvtegra（E2） |
| hwaccel 头文件 | `extern/ffmpeg/include/libavutil/hwcontext_nvtegra.h`：92 行/2,748 B，头注释 "Copyright (c) 2024 averne"，GPL-2.0-or-later；宏 `AV_NVTEGRA_ENCODE_REV(maj,min)` 等 | OpenNOW-Switch 仓库原文（E3） |
| nvhost ioctl | `extern/ffmpeg/include/libavutil/nvhost_ioctl.h`：511 行/14,917 B，NVIDIA 2016-2020 版权，GPL-2.0-or-later，为 Tegra host 驱动 uapi | OpenNOW-Switch 仓库原文（E3） |
| NXMP | GPL-3.0，BUILD.md 明确 "https://github.com/averne/FFmpeg/tree/nvtegra"；configure 参数含 `--enable-gpl --enable-nvtegra --enable-mbedtls --enable-version3`；另需 averne/libuam 与 averne/mpv | https://github.com/proconsule/nxmp/blob/master/BUILD.md（E3） |
| SwitchWave | GPL-3.0，desc "Hardware-accelerated media player for the Nintendo Switch"；.gitmodules: ffmpeg=averne/FFmpeg branch tx1；Makefile FFMPEG_CONFIG 含 `--enable-asm --enable-gpl --enable-nvtegra --target-os=horizon --cpu=cortex-a57 --enable-neon` | https://github.com/averne/SwitchWave（E3） |
| OpenNOW-Switch | MIT，README "H.264 video, Opus audio, NVDEC hardware decoding, and software-decoder fallback"；CMakeLists `OPENNOW_ENABLE_NVDEC`、报错文案 "uam is required for the NVDEC/Deko3D video shaders"；extern/ffmpeg 为预编译库（libavcodec.a 17,941,808 B、libavformat.a 4,120,330 B、libavutil.a 1,446,344 B、libcurl.a 1,707,444 B、libswresample.a 161,458 B）；app/src/stream/ffmpeg/FFmpegVideoDecoder.cpp 448 行/14,564 B | https://github.com/OpenCloudGaming/OpenNOW-Switch（E3）；HEAD 730704d7ad80d15a6ca6020121be5313559de87e（2026-10-29T19:41:07Z，E2） |

### 2.4 硬件支持格式与实际限制（E3/E4）

- NXMP README：0.7.0 起 HW 解码 H.264/HEVC/VP8/VP9/MPEG2，最高 4K HDR@30fps；0.8.3 deko3d 版最高 4K HDR@60fps；0.9.1 起同范围 60fps。
- SwitchWave README：H.264/AVC（10bit+ 硬件不支持）、H.265/HEVC（12bit+ 不支持）、VP9（10bit+ 不支持）；无 VC-1 → VC-1 硬解不可假设。
- 结论：对我们来说可用的硬解格式只有 H.264 8-bit（H.264 High profile 8bit 正是本报告 §6 转码产物）。

### 2.5 访问方式与依赖（E3，部分 E4）

- 通道：NVDEC 通过 `/dev/nvhost-nvdec`（nvhost 通道 + ioctl 命令缓冲）访问，代码在 averne/FFmpeg 的 nvtegra hwaccel；`nvhost_ioctl.h` 即其 uapi 头（E3）。
- 进程权限：走 nvdrv 服务；switchbrew /wiki/NV_services 记录 nvdrv 权限掩码为 [11.0.0+] 0xA83B、[1.0.0-2.3.0] 0x2B、[3.0.0+] 0xA82B（E2），但该页文本未直接列出 nvdec 设备，无法据此判定 homebrew 进程是否可开通道——**只能由第三方项目实际可用来反证可行**（E3）。
- 固件：NVDEC 需要 nvservices 加载对应固件 ucode；固件版本要求、所需分区文件未取证（U3）。
- 渲染：OpenNOW 的 NVDEC 路径要求 deko3d + uam（shader 编译器，https://github.com/averne/libuam）；GalNX 当前用 SDL2 渲染（sdl_video.c），要么把 NVDEC 输出 NV12 表面转成 SDL 纹理（多一次拷贝，但可保留 SDL2），要么引入 deko3d 零拷贝（改动大）。

## 3. Switch 播放器/实现横向对比（E2/E3）

| 项目 | 性质 | Switch 端解码方式 | 许可证 | 对本项目可复用性 |
| --- | --- | --- | --- | --- |
| Moonlight-Switch | 游戏串流客户端 | FFmpeg **软解**（CMakeLists 链接 lib/switch/libavcodec.a；README 的 "Use hardware decoding" 仅在 Linux 桌面走 VA-API/CUDA/VDPAU，credits 的 Averne NVDEC 是 PC 版 ffmpeg nvdec hwaccel） | GPL-3.0 | 仅参考（软解可行性佐证） |
| NXMP | mpv 播放器 | NVDEC 硬解（averne/FFmpeg nvtegra） | GPL-3.0 | 仅参考 |
| SwitchWave | mpv 播放器 | NVDEC 硬解（averne/FFmpeg，动态调频） | GPL-3.0 | 仅参考 |
| OpenNOW-Switch | GeForce NOW 客户端 | NVDEC 硬解 + 软解回退（MIT 应用层 + 预编译 nvtegra ffmpeg） | MIT（仓库）；ffmpeg 二进制仍为 GPL 构建 | **应用层代码可复用**（448 行解码器 + 接线），ffmpeg 层受 GPL |
| pPlay | mpv 播放器 | 未确认（README/源码未取证） | GPL-3.0 | 仅参考 |
| libnx | 官方库 | 无 NVDEC API | ISC | 不可用 |
| devkitPro switch-ffmpeg 7.1-5 | 官方包（已在本机） | H.264 软解（libavcodec） | FFmpeg 许可证（包 PKGBUILD 未取证，U9） | **直接可用，无需新装** |

## 4. 方案对比

| 方案 | 解码 | 分辨率/帧率 | 素材体积 | 实现成本(人日) | 真机性能预期 | 主要风险 | 许可证 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| A. NVDEC 硬解（复用 nvtegra） | 硬件 | 1280x720@30 | 113.9 MB | 12–20（FFmpeg Switch 构建 2–3 + Rust FFI 5–8 + NV12→SDL 纹理 2–4 + 联调 3–5） | CPU 极低，30fps 稳；渲染另计 | **GPL-2+ 传染整个 NRO**；Citron 大概率不支持 NVDEC；无官方文档；固件/权限未知 | GPL-2.0-or-later |
| B. H.264 软解 720p30（switch-ffmpeg） | 软件 | 1280x720@30 | 113.9 MB | 4–7（FFI 2–3 + 纹理/转换 1–2 + 联调 1–2） | 宿主单线程 3.85 ms/帧；A57 6–10× → 23–49 ms/帧，30fps 临界（E4） | CPU 与引擎竞争；内存；音画同步 | LGPL-2.1+（FFmpeg） |
| C. H.264 软解 540p30 | 软件 | 960x540@30 | 57.3 MB | 4–7（同 B） | 解码量约为 720p 的 56% → 12–27 ms/帧，余量较大（E4） | 画质下降 | 同上 |
| D. 维持 540p30 WMV2（现状解码器） | 软件 | 960x540@30 | 84.8 MB | 0.5（仅换素材重打包） | P29 折算 25–40fps（E4） | WMV2 解码器效率低；画质最低 | 自有 |
| E. 720p24/720p15 WMV2 | 软件 | 1280x720@24/15 | 略小于 720p30 | 0.5–1 | 24fps 预算 41.7 ms → 可能达标（E4） | 动作不流畅；默认解码器仍是瓶颈 | 自有 |
| F. MJPEG 720p30 | 软件（libjpeg-turbo）或 nvjpg（无 API） | 1280x720@30 | 未测，预计显著大于 H.264 | 3–6 | 解码快但 IO/内存大 | 体积、码率、封装 | 视实现 |
| G. 静态图/跳过 OP | 无 | - | 极小 | 0.5 | 无视频 | 体验 | 自有 |

> 备注：方案 A 的人日估算在本轮另有 15–25 的粗估，两者同量级；关键不是人日而是 GPL 决策与 Citron 无法验证。

## 5. 推荐路线与成本

**P0 止血（0.5–1 人日）**：先选 E（720p24 WMV2）或 D（540p30 WMV2）重打包，用现有解码器验证真机帧率下限；确认瓶颈是否仍在解码而非渲染。

**P1 主推（4–7 人日，约 1 周）：H.264 软解接入 switch-ffmpeg 7.1-5**

1. 先写最小 bench（1 人日）：Rust FFI 调 `avcodec_send_packet`/`avcodec_receive_frame`，直接测 720p30 与 540p30 的真机 decode+copy 帧耗时（不接入引擎）。
2. 接入：用 `sws_scale` 或 SDL YUV 纹理把 NV12/YUV420P 送 SDL2 渲染（`platform/switch/runtime/sdl_video.c` 已有 SDL_Texture 路径）；音频沿用现有 OGG 路径。
3. 验收：真机 ≥24fps、音画偏差 <100 ms、峰值内存 <64 MB、退出无泄漏；若 720p 不达标则改 540p（体积 57.3 MB，更稳）。

**P2 研究（timebox ≤5 人日，不阻塞主线）：NVDEC 原型**

- 复用 OpenNOW-Switch 的 FFmpegVideoDecoder.cpp（MIT，448 行）与预编译 nvtegra FFmpeg 做「能解码一帧」的最小验证；同时把 GPL-2+ 合规问题交 Lead/用户决策。
- 不建议本轮直接投入 12–20 人日：许可证会改变整个发行物，且 Citron 大概率无法验证硬解路径（U2）。

## 6. 本机实验（已完成，E1）

转码脚本 E:/galnx-build/p33/research/build-encodes.sh，日志 build-encodes.log；ffmpeg 9.0-full_build-www.gyan.dev（gcc 16.1.0，含 libx264）。

```bash
ffmpeg -y -i /e/galnx-build/p31/game/movie/01.wmv \
  -vf "scale=1280:720:flags=lanczos,fps=30000/1001" \
  -c:v libx264 -profile:v high -preset medium \
  -b:v 8M -maxrate 10M -bufsize 16M -g 60 -an \
  -movflags +faststart h264_720p30_8M.mp4
# 540p: -vf "scale=960:540:flags=lanczos,fps=30000/1001" -b:v 4M -maxrate 5M -bufsize 8M
```

ffprobe 结果（两条均 3597 帧 / 120.0199 s / yuv420p / 29.97 fps）：

- 720p：H.264 High L4.0，bit_rate=7,588,712 bps，容器 7,590,844 bps，113,881,554 B，sha256 e9ee8fd99f54c62ec93579bcd9fdb83a4959ce335b69d553ae4a2991399309fa。
- 540p：H.264 High L3.1，bit_rate=3,815,987 bps，容器 3,818,673 bps，57,289,603 B，sha256 cc7d14f53c1a5edeb2e396ecda50069184eaad5b9e0d9f523d580cb5bd2517a3。

宿主解码 bench（ffmpeg -benchmark -f null -，16 核 x86）：

| 样片 | 线程 | rtime | 折算 | 每帧 CPU |
| --- | --- | ---: | ---: | ---: |
| 720p | 默认多线程 | 2.032 s / 120 s | 59.1× 实时 | utime 17.594 s → 4.89 ms |
| 720p | -threads 1 | 13.859 s / 120 s | 8.66× 实时 | 3.81 ms |
| 540p | 默认多线程 | 1.283 s / 120 s | 93.5× 实时 | utime 10.766 s → 2.99 ms |

→ 720p H.264 软解在宿主单线程已接近 9× 实时；Switch A57（无 SMT、主频 1.0 GHz 级、NEON）按 6–10× 降速估计，仍在 30fps 预算边缘，必须真机 bench 定夺。

## 7. 复现与证据路径

- 样片/脚本/日志：E:/galnx-build/p33/research/{h264_720p30_8M.mp4,h264_540p30_4M.mp4,build-encodes.sh,build-encodes.log}
- 校验：`cd /e/galnx-build/p33/research && sha256sum h264_720p30_8M.mp4 h264_540p30_4M.mp4`
- 软件解码可用性：`D:/devkitPro/msys2/usr/bin/pacman.exe -Q switch-ffmpeg` → switch-ffmpeg 7.1-5；库文件 D:/devkitPro/portlibs/switch/lib/libavcodec.a、libavformat.a、libavutil.a、libswresample.a、libswscale.a（E1）。
- NVDEC 分支取证：`GIT_TERMINAL_PROMPT=0 git -c http.proxy=http://127.0.0.1:7897 ls-remote https://github.com/averne/FFmpeg | grep heads` → envideo 8a49f6e6…、master 932a872d…、nvtegra caeec83b…。
- OpenNOW 证据：https://raw.githubusercontent.com/OpenCloudGaming/OpenNOW-Switch/main/app/src/stream/ffmpeg/FFmpegVideoDecoder.cpp 、.../extern/ffmpeg/include/libavutil/hwcontext_nvtegra.h 、.../extern/ffmpeg/include/libavutil/nvhost_ioctl.h 、.../CMakeLists.txt 。
- P31 基线：Workspace/GalNX/docs/builds/038-rfvp-op-playback.md。

## 8. 许可证合规分析

1. **averne/FFmpeg nvtegra = GPL-2.0-or-later**：hwcontext_nvtegra.h 头注释即 GPL-2+；NXMP/SwitchWave 的 configure 都带 `--enable-gpl`。静态链接进 NRO 后，整个 NRO 须按 GPL-2+ 发布（提供完整对应源码与可重链接对象）。GalNX 主树是 MPL-2.0；MPL-2.0 允许再许可为 GPL，但一旦合并分发，整个产物受 GPL 约束 → **需用户/Lead 明确决策，默认排除**。
2. **OpenNOW-Switch = MIT 仓库**，app 层代码（FFmpegVideoDecoder.cpp 等）可并入 MPL-2.0 项目（保留 MIT 声明）；但其 `extern/ffmpeg` 预编译库是 nvtegra GPL 构建，**不能当作 MIT** 使用。
3. **NXMP / SwitchWave / pPlay = GPL-3.0**：不可并入；只能作为技术参考。
4. **devkitPro switch-ffmpeg**：FFmpeg 默认 LGPL-2.1+，但包内构建参数（是否 --enable-gpl）未取证（U9）；静态链接 LGPL 库也需提供可重链接对象——采用前需确认 PKGBUILD。
5. **H.264 素材**：由 libx264 编码，输出视频文件本身不构成 GPL 衍生作品；但若分发编码脚本或 ffmpeg 二进制需注意 GPL（内部分发一般无碍）。

## 9. 未核实 / 失败项

- U1：NVDEC 在 GalNX 的 SDL2 应用内能否直接使用（现有实现均配 deko3d/mpv；SDL2 + NVDEC 组合未验证）。
- U2：Citron 模拟器是否支持 NVDEC（大概率不支持，若如此硬解无法在模拟器验证，只能真机）。
- U3：NVDEC 对固件版本/分区文件的具体要求未取证。
- U4：averne/FFmpeg nvtegra（最新提交 2024-10-06，面向 ffmpeg 7.1）与 switch-ffmpeg 7.1-5 的版本兼容性未实测。
- U5：H.264 720p30/540p30 软解在 Switch 真机的实际 fps（本报告只有宿主 bench 与 Moonlight-Switch 软解侧证）。
- U6：H.264 软解与 rfvp 引擎主线程的 CPU 竞争、内存峰值未实测。
- U7：NVDEC 输出 NV12 零拷贝到 SDL_Texture 的可行性与代价未验证。
- U8：OpenNOW 的 NVDEC 代码是否 100% 为其 MIT 应用层自研（依赖的 ffmpeg 头/库仍是 GPL）。
- U9：devkitPro switch-ffmpeg 7.1-5 的 PKGBUILD 与许可证构建参数未取证。
- U10：VC-1 硬解支持未知（wiki 无 NVDEC 页，NXMP/SwitchWave 均未列 VC-1）。
- U11：pPlay 的 Switch 端解码方式未取证。
- 失败项：switchbrew /wiki/Nvhost 被 Cloudflare 拦截（curl + 代理 + UA 重试仍失败）；wiki 搜索 API 返回 0（索引不可靠）；GitHub contents API 大目录响应被截断（改用 code search/raw 文件绕过）。

## 10. 参考来源

- libnx：https://github.com/switchbrew/libnx （pcv.h/mm.h 见本地 D:/devkitPro/libnx/include/switch/services/）
- switchbrew NVDEC 空页：https://switchbrew.org/wiki/NVDEC ；NV_services：https://switchbrew.org/wiki/NV_services
- averne/FFmpeg：https://github.com/averne/FFmpeg （分支 nvtegra / envideo）
- averne/libuam：https://github.com/averne/libuam
- NXMP：https://github.com/proconsule/nxmp （BUILD.md、README、release v0.9.3 2025-12-17）
- SwitchWave：https://github.com/averne/SwitchWave （.gitmodules、Makefile）
- OpenNOW-Switch：https://github.com/OpenCloudGaming/OpenNOW-Switch （README、CMakeLists.txt、extern/ffmpeg、app/src/stream/ffmpeg/FFmpegVideoDecoder.cpp）
- Moonlight-Switch：https://github.com/XITRIX/Moonlight-Switch （README、CMakeLists.txt）
- pPlay：https://github.com/Cpasjuste/pplay
- 本机 ffmpeg/ffprobe：D:/Scoop/shims/ffmpeg.exe（9.0-full_build-www.gyan.dev）
- P31 基线：Workspace/GalNX/docs/builds/038-rfvp-op-playback.md

## 11. 变更记录

- 2026-11-07：初版（timebox ≤40 分钟研究；只读 + 本机转码；未装软件、未改 P31 源码、未动游戏目录）。
