# 051 · GLES2 双平面零拷贝：NV12 Y/UV 直传 + GPU YUV→RGB（P44，v1.4.1-test）

- 日期：2026-11-10
- 相关：`docs/builds/patches/rfvp-switch/rfvp-nv12-zerocopy.patch`、`docs/milestones/evidence/P44-nv12-zerocopy/`、计划 v1.42（决策 57）
- 状态：模拟器（Citron）A/B 与 NSP(romfs) 冒烟完成；真机由用户安装 v1.4.1-test 验收

## 1. 背景

probe9（`docs/builds/045-nvdec-probe9.md`）在真机上把 OP 慢放拆到了阶段级：NVDEC 解码 0.44 ms/帧、Copy Engine 传输 3.79 ms/帧，而 **CPU 把 NV12 转成 RGBA 要 43.54 ms/帧**（C2 阶段 5.50 fps）。P40 的 H.264 管线（`docs/builds/046`）只是把这个转换换成 NEON 定点 BT.709（convert ≈3.5 ms/720p、≈7.3 ms/1080p），本质仍是「CPU 转 RGBA + 按 4 B/px 上传」。

用户 m40030 指定下一步：**做 GLES2 双平面 shader 零拷贝**。目标是把 Y/UV 两个平面直接交给 GPU，由 SDL 的 NV12 shader 做 YUV→RGB，从而在 1080p 下同时省掉 CPU 转换与 3/4 的上传带宽。

## 2. 设计

### 2.1 数据通路

```
FFmpeg 解码帧 (NVDEC → AV_PIX_FMT_NVTEGRA / 软解 → YUV420P)
   │  galnx_movie_stage_nv12()  ← 新增 C 侧打包
   ▼
紧密 NV12 (Y: w*h, UV: ((w+1)/2)*2*((h+1)/2))
   │  MovieFrame.nv12
   ▼
RfvpRenderer::create_texture_nv12(id, w, h, y_plane, uv_plane)   ← 默认 Unsupported
   ▼
galnx_sdl_texture_create_nv12() → SDL_CreateTexture(SDL_PIXELFORMAT_NV12)
   │  SDL_UpdateNVTexture(texture, NULL, y_plane, width, uv_plane, uv_pitch)
   ▼
GLES2_RenderDriver 的 NV12 BT.709 shader（Y 在 .r，UV 在 .rg，两平面在 GPU 内合成）
```

RGB 帧只是「多绕一圈」：`TextureBackend::create_texture` 在 `data.len() == width*height*3/2` 时把 `data` 切成 Y/UV 两段直接走 `create_texture_nv12`，所以渲染层（`prim_commands`）不需要知道格式细节，只在 `graph.get_nv12_planes()` 为真时传 `TextureFormat::Nv12`。

### 2.2 为什么必须是「双平面」而不是一次 RGBA 之外的新格式

devkitPro 的 `libSDL2.a` 只编入了 `GLES2_RenderDriver` 与 `SW_RenderDriver`（没有桌面 GL 驱动），所以 Switch 上 `SDL_Renderer` 必定走 opengles2。SDL 2.28 的 GLES2 驱动已经内置 NV12 专用 shader（`GLES2_Fragment_TextureNV12BT709_RA`、`GLES2_Fragment_TextureNV12BT601_RA` 等），`SDL_PIXELFORMAT_NV12` 纹理经 `SDL_UpdateNVTexture` 上传后由该 shader 完成色彩空间转换 —— 这正是「双平面零拷贝」的落点：CPU 只搬紧凑 NV12（1.5 B/px），转换在 GPU 上做。

### 2.3 回退策略

- `galnx_sdl_nv12_supported()` 在首次调用时 `SDL_CreateTexture(SDL_PIXELFORMAT_NV12, STREAMING, 16, 16)` 探测并缓存结果；失败则整条电影路径继续走原有 RGBA 路径（行为与 v1.4.0 完全一致）。
- 调试 marker `sdmc:/switch/rfvp/nv12_off.txt` 存在即强制回退，用于 A/B 对比（与 `h264_sw.txt` 同级，真机发布时绝不能存在）。
- 单帧 staging 失败（FFmpeg 像素格式不认识、容量不足）时 `decode_one` 打 warn 并回退该帧到 RGBA 转换，不丢帧。

## 3. 实现（13 文件 / +446/−24，patch 785 行）

| 文件 | 改动 |
| --- | --- |
| `platform/switch/runtime/sdl_video.c` | `FormatNv12 = 6`、`TextureEntry.format`、`galnx_sdl_nv12_supported()`、`sdl_texture_create_nv12_impl`（`SDL_UpdateNVTexture`）、公共 FFI `galnx_sdl_texture_create_nv12(id,w,h,y,y_len,uv,uv_len)`、上传耗时统计 |
| `platform/switch/runtime/rfvp_movie_h264.c/.h` | `galnx_movie_stage_nv12(dst, capacity)`：NV12 源按行 `memcpy`（`uv_pitch = width*2`）、planar 源把 U/V 交织；返回写入字节数，负值表示不可用 |
| `platform/switch/host/src/render.rs` | extern 声明 + `HorizonRenderer::create_texture_nv12`（rc!=0 只打日志、不中断） |
| `crates/rfvp/src/host_api/render.rs` | `RfvpRenderer::create_texture_nv12` 默认 `Err(Unsupported)`；`TextureFormat::Nv12`；`TextureBackend::create_texture` 按 `w*h` 切分双平面 |
| `crates/rfvp/src/rendering/prim_commands.rs` | `upload_graph_if_needed` 先判 `get_nv12_planes()`，命中则按 `TextureFormat::Nv12` 建纹理 |
| `crates/rfvp/src/subsystem/resources/graph_buff.rs` | `nv12: Option<Vec<u8>>` + `get_nv12_planes()` + `load_from_nv12_recycle()`（校验 `w*h + uv_pitch*((h+1)/2)`）；RGBA 装载与 `unload` 清空；`capture_snapshot_with_id` 跳过 NV12（解码器 scratch 不进存档） |
| `crates/rfvp/src/subsystem/resources/motion_manager/mod.rs` | `load_texture_nv12_recycle(id, planes, w, h)` |
| `crates/rfvp/src/subsystem/resources/videoplayer/mod.rs` | `MovieFrame.nv12`、`MovieSource::recycle_nv12()` 默认空实现、`tick` 分派 NV12 并回收缓冲区 |
| `crates/rfvp/src/subsystem/resources/videoplayer/horizon_h264.rs` | `DecodedFrame.nv12_planes`、`plane_buffer` 复用、`stage_nv12()` 计时、`try_open` 探测 NV12 能力并打 `upload=nv12/rgba` |
| 其余 4 处 `MovieFrame` 字面量 | `nv12: Vec::new()` |

设计要点：

1. **纹理池复用**：`plane_buffer` 与 `load_from_nv12_recycle` 让每帧只做一次 `Vec` 所有权转移（避免 3.1 MB 级拷贝与频繁分配），与 P17 的 LRU 缓存思路一致。
2. **存档安全**：`GraphBuffSnapshotV1` 的像素快照必须能跨进程重建，而 NV12 写的是解码器 scratch —— 因此 NV12 图直接跳过快照采集，落盘的仍是可重放的 motion 层（否则读档会依赖一个并不存在的解码器状态）。
3. **纹理 id 不变**：上传仍落在 `host_texture_id(graph_id)`，所以 `videoplayer` 的 MOVIE_GRAPH_ID 复用、销毁与日志语义完全不变。

## 4. A/B 量化（Citron 0237a9b88，统一判据）

判据：同一 run 内 `presented ... upload_us` 与 `decoded ... decode_us/stage_us` 日志 + host 每 60 帧汇总。NV12 组无 `nv12_off.txt`，RGBA 组有该 marker，其余条件完全相同。

### 4.1 720p（v1.4.0 交付档位）

| 组 | 解码后处理 | 转换/打包 | 上传 | present |
| --- | --- | --- | --- | --- |
| NV12 | `stage_us=837` | 0.84 ms | 0.95 ms（30 calls） | 7.61 ms |
| RGBA | `convert_us=3745` | 3.75 ms | 1.77 ms（30 calls） | 4.28 ms |

### 4.2 1080p（本次新转码的 H.264 OP）

片源 `E:/Othergames/Galgame/AKASEKA_HD/movie/01.wmv` 是 VC-1 1920x1080（3364 帧 / 29.97 fps），转码为 `/e/galnx-build/p44/encode1080/01_h264.mp4`：121,601,536 B、H.264 High、30000/1001、8.67 Mbps、BT.709 tv、无音轨、faststart；音频复用 `01.ogg`。

| 组 | 解码后处理 | 转换/打包 | 上传 | 画质/帧率 |
| --- | --- | --- | --- | --- |
| NV12 | `stage_us=1812` | 1.81 ms | **2.72 ms**（8.29 MB→3.11 MB，1.5 B/px） | 20.4 fps |
| RGBA | `convert_us=9251` | 9.25 ms | 6.75 ms（60 calls） | 18.1 fps |

**结论：单帧 CPU 侧省下约 9.5 ms**（转换 7.4 ms + 上传 4.0 ms），1080p 全帧 NV12 只有 3.11 MB。真机上 NVDEC 解码仅 0.44 ms、CE 传输 3.79 ms，因此 1080p OP 的每帧成本回到 16.67 ms 预算内 —— 这是把「1080p 只能 720p 播放」的结论正式推翻的关键一步（计划决策 49 的落地）。

Citron 的 `present` 在 NV12 下反而变慢（7.61 ms vs 4.28 ms @720p）：Citron 没有真 NVDEC，且 guest 的 GLES2 `NV12 shader` 在 Vulkan 上需要额外的双采样与格式模拟。该数值**不具真机代表性**，不作为结论依据；真机 present 以用户安装 v1.4.1-test 后的实测与 `perf_slow.log` 为准。

## 5. 构建与产物

- 唯一构建脚本 `/e/galnx-build/p40/build.sh`（`RFVP_FFMPEG_SRC` / `RFVP_FFMPEG_BUILD` 指向 nvtegra 树，先 sed 掉联网 rustup 行）：

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p40/build.sh'
```

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| `rfvp.nro` | 10,678,328 | `32e0c725233b771b4f7b8dc87b53d444d2b6ad0da2bf7279df60221c3198c2db` |
| `rfvp.elf` | 20,418,056 | `296b198c6b1dc970ed6544cac40c0c4da97bf581dda031c0a8acb4cc0a073973` |

AKASEKA HD 自包含 NSP（`/e/galnx-build/p45/build-nsp.sh`，romfs 6,718,475,156 B / 141 文件，`--romfs-mode hardlink`）：

| 项目 | 值 |
| --- | --- |
| 包 | `E:/galnx-build/p45/out/AKASEKA_HD-010047420000d000.nsp` 6,738,209,496 B |
| sha256 | `db31a312c745e46b73f11445168af94ad6790989d847f184a8d2cd6312190c8f` |
| title_id / 版本 | `010047420000D000` / `1.4.1-test` |
| exefs/main | 6,385,492 B `536531738648db31fc466a1913a2d4607081b79cc302c9ff2a904eb25623ba11` |
| verify | `ok=true`，13 checks / 0 fail / 1 warn（未签名 homebrew 预期），3 个 NCA ProgID 全为 `0x010047420000D000` |

## 6. NSP(romfs) 冒烟（决定性）

`/e/galnx-build/p45/run-nsp1080.sh`：强制软解（`h264_sw.txt`，Citron 无真 NVDEC）、`movie_debug.txt=movie=1`、`video.txt=720`、`debug=1`；`--game <nsp> --no-stage --timeout 200 --settle 2 --input-delay 30000`，随后三次截图。

- 结果：`status=loaded`、窗口标题 `citron Nightly | 0237a9b88 | AKASEKA HD (64-bit) | 1.4.1-test`、`Booting game: 010047420000D000`、非黑比 0.9018、`steps_failed=0`。
- 关键日志（`evidence/nsp1080/debug_report.txt`）：

```
Movie: opened (Switch NVDEC H.264, upload=nv12) asset=movie/01_h264.mp4
decoded frame=1 ... 1920x1080 hw=0 decode_us=95785 stage_us=2178 nv12=1
presented ... upload_us=4..10 nv12=1
host avg over 60 frames: begin 0.06 ms, upload 2.80 ms (60 calls), present 0.79 ms
frame 2220: 23.0 fps
```

- 无 `using CPU`、无 `NV12 textures unavailable`；三张截图分别是 OP 正片（女主特写 / 转场 / 字幕「ひとつだけ恋して――」），颜色正常。
- 23.0 fps 是 Citron 软解 35–43 ms/帧 主导的结果，与上传路径无关。

## 7. 补丁

`docs/builds/patches/rfvp-switch/rfvp-nv12-zerocopy.patch`：785 行、13 文件、+446/−24，sha256 `afbf3fb0a2544a053e05219b32742a1722cbff0a44bac48afb60d76bddf9800b`。应用顺序：P40 → P40b → P40c → P41 → 本补丁；生成方式是从 40 个增量 hunk 逆序重建「打补丁前」树再正向重放，重放结果与当前构建树逐字节一致（roundtrip 验证通过）。

## 8. 限制

1. Citron 无真 NVDEC：本轮的 NV12 组走的是软解 YUV420P→NV12 打包，只能证明上传/着色路径正确与耗时量级；硬件 NVDEC 的 `NVTEGRA` 平面布局在 probe3/probe9 已独立验证可用，但「NVDEC → 双平面 → 屏幕」的整链仍未在同一 run 里跑过。
2. `present` 数值不可用于真机推断（见 §4.2）。
3. 1080p 只对 OP 生效：故事区仍是 1280x720 渲染分辨率；1080p 全局渲染没有做，也不在本轮范围。
4. NV12 纹理依赖 GLES2 驱动能力探测；若将来换渲染后端（如 deko3d），需要新的上传实现，`RfvpRenderer::create_texture_nv12` 的默认 Unsupported 就是留给它的口子。
5. `h264_sw.txt`/`nv12_off.txt` 都是自测 marker，发布说明要求用户不要创建。

## 9. 复现

```bash
# 1) 构建（git-bash 内执行 MSYS2 包装）
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p40/build.sh'

# 2) 1080p A/B（Citron，开关 nv12_off.txt 对比两组）
/d/Scoop/apps/git/current/bin/bash.exe -c 'bash /e/galnx-build/p44/run-ab1080.sh'

# 3) NSP 打包 + 校验
/d/Scoop/apps/git/current/bin/bash.exe -c 'bash /e/galnx-build/p45/build-nsp.sh'
cd '/e/Othergames/Nintendo Switch/Workspace/GalNX'
PYTHONPATH=src python -m galnx package nsp verify \
  --nsp 'E:\galnx-build\p45\out\AKASEKA_HD-010047420000d000.nsp' \
  --manifest examples/pilot04-akaseka.yaml \
  --nstool 'E:\galnx-build\m3-tools\nstool.exe' \
  --keyset 'E:\Othergames\Nintendo Switch\Ryujinx-canary\portable\system\keys' --json

# 4) NSP(romfs) 冒烟
/d/Scoop/apps/git/current/bin/bash.exe -c 'bash /e/galnx-build/p45/run-nsp1080.sh'
```

## 10. 教训

1. **先量化再动手**：probe9 把「慢放」拆成 43.54 ms 的 CPU 转换，才有零拷贝这个明确目标；如果直接上「优化视频管线」，很容易先去改解码而完全错靶。
2. **模拟器只能验证到「路径正确 + 相对省时」**：Citron 的 present 反向劣化说明模拟器的后端开销会淹没微观收益，判断真机必须靠设备日志而非模拟器帧率。
3. **回退面越小越好**：NV12 能力探测失败、单帧 staging 失败、marker 强制关闭三条路都回到原路径，所以这个补丁对既有 720p 交付是零风险的；先做可回退的增量，再考虑替换。
4. **存档快照不能存解码器 scratch**：NV12 图跳过快照是正确性要求（不是优化），这类「看起来是性能、实际是正确性」的取舍要写在代码注释里。
5. 生成 patch 时 Python 三引号会把 `\n` 展开成真换行，C 字符串被截断却仍能编译（只是内容错）—— 生成后必须 roundtrip 比对整树，不能只看 `git apply` 成功。
