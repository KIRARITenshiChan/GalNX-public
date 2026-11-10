# 046 · OP 换 H.264 + NVDEC(nvtegra) 硬解接入（P40，v1.2.0-test）

- 日期：2026-11-09
- 相关：`docs/builds/045-nvdec-probe9.md`、`docs/builds/040-wmv2-left-edge.md`、`docs/builds/patches/rfvp-switch/P40-op-h264.diff`、`docs/milestones/evidence/P40-op-h264/`
- 状态：已构建并完成模拟器侧验证（NRO 影子 + NSP romfs 冒烟）；真机 60 fps 待用户运行。

## 1. 背景：为什么必须换掉 OP 资产

P33/P34 把 OP 做到「720p WMV2 软解 + 分档（720/540/480/360）」，真机结果是「流畅但糊，最左侧一列马赛克」，P34 修掉了左缘马赛克。P39（probe9）在真机上把 NVDEC 链路拆分测了一遍：

| 阶段 | 真机结果 |
| --- | --- |
| A-verify（strict 硬件 60 帧） | 218.3 ms → **274.84 fps**，`hw=60 sw=0` |
| B-decode600（decode-only） | 2,014.8 ms → **297.80 fps**（decode mean 0.44 ms） |
| C1-transfer（硬帧 → NV12） | 704.7 ms → 170.29 fps（xfer mean 3.79 ms） |
| C2-rgba（CPU NV12→RGBA，标量） | 10,900.2 ms → **5.50 fps**（43.54 ms/帧） |

结论：NVDEC 解码与 Copy Engine 传输在真机都极快，**慢放的唯一主因是 CPU 端 NV12→RGBA 用了标量循环**。而游戏真正的 OP 是 `movie/01.wmv`：`wmv2 1280x720 30000/1001 8 Mbps 120.02 s`——**WMV2 在任何 Tegra 硬件上都没有解码器**（nvtegra 只覆盖 vc1 / wmv3 / h264）。因此路线定为：

1. 把 OP 重编码为 **H.264 High**（Tegra NVDEC 最成熟、probe9 实测 297.8 fps 解码）；
2. 运行时用 `averne/FFmpeg` 的 **nvtegra hwaccel** 解 H.264，硬帧 `av_hwframe_transfer_data` 拿 NV12；
3. NV12→RGBA 换成 **NEON 定点内核**（720p 目标 2–3 ms，替代 43.54 ms 标量）；
4. 旧的 WMV2 软解路径保留为兜底（资产缺失 / 解码失败时自动回退）。

## 2. 资产重编码

```bash
ffmpeg -i /e/galnx-build/p31/game/movie/01.wmv \
  -c:v libx264 -preset slow -crf 18 -profile:v high -level 4.0 \
  -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
  -an -movflags +faststart -threads 16 \
  /e/galnx-build/p40/assets709/01_h264.mp4
```

| 文件 | 大小 | SHA-256 | ffprobe |
| --- | --- | --- | --- |
| `movie/01_h264.mp4` | 108,361,267 B | `bddf82fc7e78e256d812051a4f548c2dce07d8cdcda6c80562ea588f32757bad` | h264 High, 1280x720, yuv420p, 30000/1001, 7,220,533 bps, 120.0199 s |
| 原 `movie/01.wmv` | 124,386,038 B | `…`（保持不变，作兜底） | wmv2, 1280x720, 30000/1001, 8 Mbps, 120.02 s |
| 音轨 `movie/01.ogg` | 2,343,033 B | 不变 | 既有 OGG 音轨，本次未动 |

要点：

- **必须带 BT.709 三件套**（`-colorspace/-color_primaries/-color_trc`），否则 ffmpeg 默认不写色彩标记，硬解 NV12 走 shader 转换时颜色会偏。第一版没写标记（`/e/galnx-build/p40/assets/01_h264.mp4`，111,978,839 B）已作废。
- `-an`：音轨继续用 `movie/01.ogg`，不把音频塞进 MP4。
- `-movflags +faststart`：moov 前置，romfs 上顺序读即可开播。

## 3. 代码结构（2 个接线点 + 5 个新文件）

| 文件 | 作用 |
| --- | --- |
| `platform/switch/runtime/rfvp_movie_h264.c`（新，约 430 行） | FFmpeg + nvtegra 单例播放器。`galnx_movie_init(game_root)` / `galnx_movie_open(rel, allow_sw)` / `galnx_movie_next()`（1=帧 0=EOS <0=错误）/ `galnx_movie_close()`；`galnx_movie_plane_y/u/v`、`galnx_movie_planar()`、`width/height/y_stride/uv_stride`、`galnx_movie_pts_ms()`、`galnx_movie_is_hw()`、`galnx_movie_frame_index()`、`galnx_movie_error()` |
| `platform/switch/runtime/rfvp_movie_h264.h`（新） | 上述 API 声明 |
| `platform/switch/runtime/rfvp_movie_color.c`（新） | BT.709 limited→full 定点 + **NEON 16 像素/轮**：`galnx_nv12_to_rgba()` / `galnx_yuv420p_to_rgba()` |
| `crates/rfvp/src/subsystem/resources/videoplayer/horizon_h264.rs`（新，约 420 行） | `H264Playback` 实现 `MovieSource`；复用 `load_movie_audio`（`movie/01.ogg`）；`h264_sibling()` 把 `movie/01.wmv` 映射成 `movie/01_h264.mp4` |
| `crates/rfvp/src/subsystem/resources/videoplayer/horizon.rs` | 加 `#[path = "horizon_h264.rs"] mod h264_movie;`；`open()` 在 is_wmv 检查后、加载音频前：`if let Some(source) = h264_movie::try_open(request) { return Ok(source); }` |
| `platform/switch/runtime/main.c` | `#include "rfvp_movie_h264.h"`；在 `rfvp_switch_start(game_root)` 之前 `(void)galnx_movie_init(game_root);`——把**绝对游戏根**传给播放器，OP 走 `<root>/movie/01_h264.mp4`，不经引擎堆 |
| `platform/switch/build_switch.sh` | 新增 `FFMPEG_SRC`/`FFMPEG_BUILD`（默认 `$HOME/ffmpeg-nvtegra`、`$HOME/ffmpeg-build-nvtegra`，可用 `RFVP_FFMPEG_SRC`/`RFVP_FFMPEG_BUILD` 覆盖）；CFLAGS 加 `-I"$FFMPEG_SRC" -I"$FFMPEG_BUILD"`；源文件列表 `main sdl_video rfvp_movie_h264 rfvp_movie_color`；链接把三个 FFmpeg 静态库放进 `-Wl,--start-group … -Wl,--end-group` |

hw 初始化姿势沿用 probe9 已验证的写法（**关键**）：

```c
av_hwdevice_ctx_create(&c->hw_device, AV_HWDEVICE_TYPE_NVTEGRA, NULL, NULL, 0);
dec->hw_device_ctx = av_buffer_ref(c->hw_device);   /* 不手工建 hw_frames_ctx，让 ff_get_format 派生 */
dec->pix_fmt = AV_PIX_FMT_NONE;                      /* 强制重新协商 */
```

`get_format` 回调在候选里看到 `AV_PIX_FMT_NVTEGRA` 就选硬件，否则回退 NV12/YUV420P。硬帧先 `av_hwframe_transfer_data(sw, f, 0)` 得 NV12 再送 NEON 内核。

三处为「模拟器上也要能跑」而加的工程细节：

1. **`file:` 前缀**：horizon 的 FFmpeg 只编译了 `file` 协议，`avformat_open_input("sdmc:/…")` 会被当成未知协议。`galnx_movie_open()` 里若路径不以 `file:` 开头就 `snprintf(url, "file:%s", path)`（devoptab 的 `sdmc:/`/`romfs:/` 由 libc `open` 直达）。
2. **持久错误缓冲**：失败分支会 `galnx_movie_close()` 清掉 `g_ctx`，Rust 侧再取错误只会拿到 "no movie context"。加 `static char g_last_error[256]`，`galnx_movie_error()` 在 `g_ctx == NULL` 时返回它。
3. **force-software 标记**：`sdmc:/switch/rfvp/h264_sw.txt` 存在时跳过 `av_hwdevice_ctx_create` 与 nvtegra 候选，直接软解。Citron 的 nvtegra 只有 HLE，第二个包必报 `AVERROR_UNKNOWN (-1313558101)`（probe7/8/9 同现象），没有这个开关就无法在 Citron 上验管线。

## 4. 构建

唯一姿势（MSYS2、Windows 宿主机）：

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p40/build.sh'
```

`build.sh` 负责：导出 `DEVKITPRO`/`CARGO_HOME`/`RUSTUP_HOME`/代理与 `RFVP_FFMPEG_SRC`/`RFVP_FFMPEG_BUILD`，`sed '/rustup toolchain install/d'` 生成 `build_switch_instr.sh`（本机联网装 toolchain 会 TLS 失败），调用后打印 `BUILD_EXIT`/`ELAPSED_S` 与 NRO 哈希。

本轮踩到的两个编译坑：

1. `libavutil/macros.h` 会 `#include "libavutil/avconfig.h"`，**该头在 build 目录生成**——CFLAGS 必须同时 `-I"$FFMPEG_SRC" -I"$FFMPEG_BUILD"`，只加 SRC 会 `fatal error: libavutil/avconfig.h: No such file or directory`。
2. `rfvp_movie_color.c` 用了 `size_t` 却没 `#include <stddef.h>` → `error: 'size_t' undeclared`。

产物：

| 产物 | 大小 | SHA-256 |
| --- | --- | --- |
| `rfvp.nro` | 10,670,136 B | `875336aa1efb0996abff222429bca80eaca0867fb648be1ed826eb5f9de39519` |
| `rfvp.elf` | 20,397,352 B | `9ff49413bd9e5d7e04a82375b24f31a722296dccec993878a228cbd265b9197f` |

路径：`/e/galnx-build/p40/rfvp/target/rfvp-switch/switch/rfvp.nro`、`…/target/rfvp-switch-runtime/rfvp.elf`。Rust 增量约 5 s，全量构建 11 s。

## 5. Citron 影子验证（两条形态）

Citron 没有真 NVDEC，一律 `hw=0` 软解；但足以验证「读资产 → 解 H.264 → NV12→RGBA → 纹理上传 → 上屏」以及 romfs 路径。

### 5.1 NRO 形态（SD 卡游戏目录）

- 脚本 `/e/galnx-build/p40/run-h264-citron.sh`（git-bash 启动；sdmc 写 `h264_sw.txt`、`debug.txt` = `shot=900`+`movie=1`）
- run_dir `E:/galnx-build/p40/run-citron-01/h264/20261109-100610-rfvp`，24/24 步 ok
- `Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4`
- 整段播完：`movie h264: end of stream after 3597 frames`（0 hardware）
- `convert_us` n=190，p50 **2,520 µs**，p95 2,827，max 7,322
- 截图：staff credits / OP 角色画面均正常（证据 `docs/milestones/evidence/P40-op-h264/citron-nro-*.png`）

### 5.2 NSP 形态（romfs 内的资产）

- 脚本 `/e/galnx-build/p40/run-nsp-romfs-citron.sh`：先 `mv game game.parked` 把 `sdmc:/switch/rfvp/game` junction 挪走（`JUNCTION_PARKED`），跑完 `trap` 恢复（`JUNCTION_RESTORED`）→ main.c 走 `game_root = romfs:/game`
- `--game NSP --no-stage`（10 GB NSP 不拷进 sdmc），sdmc 写 `h264_sw.txt`/`debug.txt`/`video.txt=720`
- run_dir `E:/galnx-build/p40/run-citron-03/nsp-romfs/20261109-110511-IROSEKA_FHD-010047420000a000`
- 窗口标题 `… | IROSEKA FHD (64-bit) | 1.2.0-test | NVIDIA`；24/24 步 ok，`nonblack_ratio=0.9018`
- OP 从 romfs 打开并整段播完（同上 3597 帧 EOS，pts 到 119,085 ms）
- OP 结束后游戏正常：`frame 5880: 60.0 fps over the last 60 frames, slowest frame 18.1 ms`
- `convert_us` n=190，p50 **2,532 µs**，p95 3,053，max 8,260
- 唯一 ERROR 是既有无关项 `id must be in range 0..256`（`color.rs:35`）

### 5.3 失败与诊断路径

在 Citron 上**不写** `h264_sw.txt` 时，第一帧后必然 `movie h264: next_due_frame failed: h264 decode failed: avcodec_send_packet: Unknown error occurred (-1313558101)`（nvtegra HLE 无真实 `nvdec_status`）。这不是我们代码的 bug——同一份代码在 probe9 真机是 297.8 fps。调试期正是把这条日志与 probe7/8 对比后才定位到「Citron 只能走软解」。

## 6. 自包含 NSP（v1.2.0-test）

```bash
bash scripts/build_nsp_game.sh \
  --elf /e/galnx-build/p40/rfvp/target/rfvp-switch-runtime/rfvp.elf \
  --game-dir /e/galnx-build/p31/game \
  --title-id 010047420000a000 --name "IROSEKA FHD" --author GalNX --version 1.2.0-test \
  --icon examples/pilot02/icon-256.jpg \
  --keyset 'E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys' \
  --hacbrewpack /e/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c/hacbrewpack.exe \
  --nstool /e/galnx-build/m3-tools/nstool.exe \
  --romfs-mode hardlink --out /e/galnx-build/p40/out --work /e/galnx-build/p40/nspwork
```

| 项 | 值 |
| --- | --- |
| NSP | `E:/galnx-build/p40/out/IROSEKA_FHD-010047420000a000.nsp` **10,087,535,320 B** SHA-256 `5bc45ace24a3b262ebbbbc09f74652921237bc6e65a01e1065a39ceb82d8b3e8` |
| romfs | 166 项（hardlinked）；`game/movie/` 下 `01_h264.mp4` 108,361,267 + `01.ogg` 2,343,033 + `01.wmv` 124,386,038 + `01_q360/q480/q540` |
| verify | `galnx package nsp verify` = **13 checks / 0 fail / 1 warn**（未签名 homebrew 预期）；三个 NCA 的 ProgID 均 `0x010047420000A000`；Program NCA size `0x259417600` |
| manifest | `examples/pilot02-iroseka.yaml` `version: "1.2.0-test"` |

## 7. 限制

1. **Citron 不能证明硬件路径**。真机 60 fps 是 v1.2.0-test 的验收项，不是本记录已证事实。
2. 硬解帧经 `av_hwframe_transfer_data` 拷到 CPU 再上屏（probe9 实测 xfer 3.79 ms / 1080p）。若真机 720p 仍有富余不足，下一步是零拷贝：把 tiled 表面直接绑成 GLES 纹理用 shader 做 YUV→RGB（专家建议与 SwitchWave 的 deko3d 路线）。
3. H.264 资产只有 720p 单档；旧的 540/480/360 分档只对 WMV2 兜底路径有效。
4. 音频未改：仍由既有 `horizon::load_movie_audio` 在首个视频帧时启动 `movie/01.ogg`。
5. NSP 体积增加 108 MB（OP 双资产共存：H.264 + 原 WMV2 兜底）。

## 8. 复现

1. 构建 FFmpeg（nvtegra 分支，含 h264 hwaccel）：`/e/galnx-build/nvdec/build-ffmpeg-nvtegra-msys.sh`（产物 `/e/galnx-build/nvdec/ffmpeg-build-nvtegra`）。
2. `git apply docs/builds/patches/rfvp-switch/P40-op-h264.diff` 到 rfvp 树（基准 `/e/galnx-build/p31/rfvp-v117`，`git apply --check` 已通过）。
3. 放置资产：`game/movie/01_h264.mp4`（见 §2 哈希）。
4. 构建：§4 命令。
5. Citron 影子验证：§5 两个脚本。
6. NSP：§6 命令；真机安装后跑 OP（`debug.txt` 里 `movie=1` 或正常进 OP 触发）。

## 9. 教训

1. **先证明瓶颈再改架构**。probe9 把「慢放」拆成 decode/transfer/convert 三段，才确定 43.54 ms 的标量转换是唯一主因；否则很容易误判成「NVDEC 不行」或「渲染不行」。
2. **资产编码器选择受硬解能力约束**。WMV2 无硬解，OP 想用 NVDEC 就必须重编码；H.264 High 是 Tegra 上最稳的一条。
3. **色彩标记要显式写**。ffmpeg 默认不写 BT.709 标记，硬解 + shader 转换会偏色；第一版资产因此作废。
4. **模拟器验证要先关掉走不通的硬件路径**。Citron 的 nvtegra HLE 会「初始化成功、首帧后报错」，没有 force-software 标记就永远卡在第一条错误上，看不到后面的管线验证。
5. **FFmpeg 交叉编译要同时给源码目录和构建目录的头路径**（生成头在 build 目录）。这个坑值得写进所有 switch 侧 FFmpeg 集成文档。
6. **兜底要留在原位**。`h264_movie::try_open` 失败只 `warn` 并返回 `None`，旧 WMV2 路径原样接上；这样即使资产没打进 romfs，游戏也不会开不了 OP。
