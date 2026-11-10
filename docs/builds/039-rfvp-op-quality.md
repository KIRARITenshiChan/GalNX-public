# 039 — P33：rfvp OP 分档播放（720/540/480/360）+ 原生尺寸路径（v1.1.9-test）

- 日期：2026-11-07
- 对应里程碑：M5-z（P33）
- 对应引擎：rfvp `9f07ade`（MPL-2.0），叠加 P29+P30+P31+P32 与 P33 增量
- 产物：自包含 NSP **v1.1.9-test** 9,977,492,184 B sha256 `bd909c1eb1e6e3f9339a28b662943d0d06f74873b2dd36639824df54a90b535b`
- 证据：`docs/milestones/evidence/P33a-op-quality/`
- 真机验收：待用户设备在线（本轮设备离线，无法 MTP 上传）

## 1. 背景

用户 m29780 在 P32 之后提出的目标是「修好 OP 的视频帧率和声音」：真机上 v1.1.7-test 的 OP 有画面有音轨，但 Citron 只有 15 FPS（`MAX_DECODE_PER_TICK = 1`），OP 呈 0.5–0.6× 慢放。真机解码/内存吞吐未知，若 720p30 软解仍撑不住，需要**更低分辨率/帧率的 OP 变体**；同时 720p 源在 no_std 路径上会先软件上采样到 1920×1080 再上传纹理，浪费带宽与内存。

P33 因此做两件事：

1. **OP 分档**：romfs 内嵌 4 档同内容变体（720/540/480/360），运行时由 `sdmc:/switch/rfvp/video.txt` 一个关键词选档，默认 480，可在真机上 A/B；
2. **原生尺寸路径**：解码输出按变体原始尺寸转 RGBA（不再上采样），渲染层把纹理拉伸到全屏；复用解码侧 RGBA `spare_buffer`，避免每帧重新分配。

## 2. 设计

### 2.1 选档接口

`sdmc:/switch/rfvp/video.txt` 单行关键词（大小写不敏感，忽略首尾空白/换行）：

| 关键词 | level | 文件 | 分辨率 / 帧率 | 字节数 | sha256 |
| --- | --- | --- | --- | --- | --- |
| `720` 或 `0` | 0 | `movie/01.wmv` | 1280×720 / 30 | 124,386,038 | `62abe508b4201df8d8a29184dadfe2a479f6b1a152f5a873665c2c3ab253dd93` |
| `540` 或 `1` | 1 | `movie/01_q540.wmv` | 960×540 / 29.97 | 59,387,638 | `4c4c524b7c89b745c727f9fa44b7adc98f4da1600b651488749edc8f300ea2e1` |
| `480` 或 `2` | 2 | `movie/01_q480.wmv` | 854×480 / 24 | 38,610,038 | `d6cccf036aacfa747dbb4c41e1c1cbe4025e764f664960991a6a097528bdc1e7` |
| `360` 或 `3` | 3 | `movie/01_q360.wmv` | 640×360 / 24 | 17,870,838 | `1e3502fb0fd4274f29a8a97efa8cf4de394bad7bae5fe47684d5241810be17cc` |

- **缺文件或无法识别 → level=2（480p）**：真机首次试装即可用更低码流，避免用户不配置时又看到慢放；日志会打印实际选档。
- **变体文件缺失 → 回退原片**（`movie/01.wmv`）并 log 一行，保证不会因此无画面。
- 音轨不随档位变化：始终读取 `movie/01.ogg`（2,343,033 B，P32 既有机制）。
- 调试钩子 `debug.txt` 里新增 `movie=nil`：以游戏真实的「layer movie、无音轨」调用进入 OP，用于对照纯画面行为（`movie=1` 是强制带音轨路径）。

### 2.2 变体命名

`movie_variant_name(name, level)`：把 `movie/01.wmv` 改成 `movie/01_q480.wmv`（保留目录与扩展名）；level 0 直接返回原名。找不到变体时回退原名并打 log。

### 2.3 原生尺寸与渲染

- 解码端 `yuv420p_to_rgba_native_into`：输出缓冲按变体原始宽高（如 854×480）转换，**不再软件上采样到 1920×1080**；
- 渲染端仍然把该纹理铺满屏幕（IROSEKA 的 OP 为全屏 CG，拉伸比上采样后再全屏更省一次全屏拷贝与一份 1080p 缓冲）；
- `spare_buffer` 复用 RGBA 帧缓冲，避免每帧分配；
- 计时改用 `perf::start()` 的**宿主微秒时钟**（no_std 的 `Instant` 只在每次 tick 前进，无法测量帧内解码耗）。

## 3. 素材转码

原片为 1080p VC-1 16 Mbps 59.94 tbr（P31 实测宿主 decode+convert 29.7 ms/帧，Switch 无法实时），P31 已转出 720p30 wmv2 8 Mbps 作为主线，P33 追加 3 档：

```bash
# 540p29.97（真机 720p 仍慢时第一退路）
ffmpeg -i opening.mpg -vf scale=960:540 -r 30000/1001 -c:v wmv2 -b:v 5M -an movie/01_q540.wmv
# 480p24（默认档）
ffmpeg -i opening.mpg -vf scale=854:480  -r 24 -c:v wmv2 -b:v 2.5M -an movie/01_q480.wmv
# 360p24（兜底）
ffmpeg -i opening.mpg -vf scale=640:360  -r 24 -c:v wmv2 -b:v 1.2M -an movie/01_q360.wmv
```

变体只带视频流（`-an`），音轨统一由同名 `.ogg` 提供（P32 已定的机制：no_std 无 WMA 解码器）。四档视频合计 240,254,552 B，使 romfs 从 9,814,160,982 B 增至 9,930,029,496 B（+115,868,514 B），NSP 仍在 10 GB 以内。

## 4. 引擎实现

### 4.1 选档与打开（`videoplayer/horizon.rs`）

- 新增 `movie_quality_level()`：读 `sdmc:/switch/rfvp/video.txt` 首行关键词 → 0..3；任何异常返回 2。
- `open()` 里先按 level 生成变体名并尝试打开，失败回落原名；`Movie: opened (Switch WMV video-only, streaming, P33 quality) name=... level=... bytes=...` 记录实际档位与字节数。
- 新增调试入口 `debug_movie_nil_requested()`（`debug.txt` 的 `movie=nil`），与既有 `movie=1` 并存。

### 4.2 解码与呈现（`videoplayer/horizon.rs`）

- `yuv420p_to_rgba_native_into`：按解码器输出宽高转换；
- `spare_buffer` 复用；`presented ... upload_us` 记录上传耗时（实测 0–410 us）；
- 每帧 decode/convert 计时走宿主 `perf::start()`，日志形如
  `movie: decoded frame=2880 pts=119958 ms 854x480 decode_us=9591 convert_us=3025`。

### 4.3 宿主钩子（`platform/switch/runtime/main.c`）

- `rfvp_switch_movie_quality(void)`：把 `video.txt` 的关键词映射成 level（C 端实现，供视频线程读）；
- `rfvp_switch_debug_movie_nil(void)`：`debug.txt` 的 `movie=nil` 分支；
- 另同步改了颜色转换/批处理/图元上传/快照相关 10 个文件中的 8 个（原生尺寸输出改变纹理尺寸，需要跟批处理与快照路径对齐）。

### 4.4 涉及文件（P33 增量 10 个）

`videoplayer/horizon.rs`、`videoplayer/mod.rs`、`no_std_core.rs`、`host_api/audio.rs`（仅调试日志）、`subsystem/resources/color.rs`、`subsystem/resources/graph_buff.rs`、`subsystem/motion_manager/mod.rs`、`primitives/prim_commands.rs`、`lib.rs`、`platform/switch/runtime/main.c`。

## 5. 构建与产物

### 5.1 补丁与全量 diff

| 平台 | 文件 | 大小 / 行 | sha256 | 基准 |
| --- | --- | --- | --- | --- |
| 增量 P33 | `docs/builds/patches/rfvp-switch/rfvp-op-quality.patch` | 30,381 B / 727 行，10 文件 +414/−79 | `76e2f12dfe1759b215a3abfede0af9a907e91e0184c26794760b95c42b90a920` | **P32 合并树**（`3dd9e56` = v1.1.7-test，非单一 commit） |
| 全量 | `/e/galnx-build/p33/rfvp-full-v119.diff`（仓库外） | 324,166 B / 8,182 行，62 文件 +6,250/−322 | `e1793be2d35a9a01a9a8296b5f08e69ebd41a200d7c1994527fbf96d9d224a34` | upstream `9f07ade`（两侧 LF 规范化） |

- 全量 diff 的基准仓库：`E:/galnx-build/p31/fullgit2`（LF 规范化 git 仓库），base commit `9758423`（= upstream `9f07ade`），v1.1.7-test commit `3dd9e56`，P33 commit = `v1.1.9-test: P33 OP quality variants + native-size movie path`（分支 `p33verify`）。
- **INC 的生成**：`git reset --hard 3dd9e56` → 复制 p31 工作树 10 个源文件（LF 归一）→ commit → `git diff 3dd9e56 HEAD`。**必须** reset 到 `3dd9e56`；reset 到 base 再一次性复制会得到错误的 2 文件 diff（本轮已踩过一次）。
- **构建脚本不进补丁**：`platform/switch/build_switch_instr.sh` 的 `OUT_DIR` 硬编码本机路径，仅本地构建用，故 10 文件清单不含它。反证：INC 在 `3dd9e56` worktree `git apply --check` rc0，apply 后与 p31 树比对 1135 文件仅该脚本不同；FULL 在 base worktree apply rc0，与 p33 HEAD tree 比对 missing 0 / extra 0 / mismatch 仅该脚本 → 补丁完整覆盖所有引擎改动。

### 5.2 NSP 内容

- 构建：`scripts/build_nsp_game.sh --elf /e/galnx-build/p33/lto2/rfvp.elf --game-dir /e/galnx-build/p31/game --title-id 010047420000a000 --name "IROSEKA FHD" --author GalNX --version 1.1.9-test --icon examples/pilot02/icon-256.jpg --keyset <Ryujinx prod.keys> --romfs-mode hardlink --out /e/galnx-build/p33/out2 --work /e/galnx-build/p33/work2`；`hacBrewPack` OK in 917 s；exit 0。
- 输入产物：ELF `/e/galnx-build/p33/lto2/rfvp.elf` 17,421,312 B sha256 `d8daa64319e98ce15c3f222061223e053e456da24cb9a24820cefe84b608fe1e`；NRO `/e/galnx-build/p33/lto2/rfvp.nro` 8,228,920 B sha256 `cb018355226984a771728a1bb1cdd7878964c670aa0b2f9923395770df401bf3`。
- NSP：`E:/galnx-build/p33/out2/IROSEKA_FHD-010047420000a000.nsp` **9,977,492,184 B sha256 `bd909c1e…`**；romfs 9,930,029,496 B / **165 项**（`movie/01.wmv`+`01_q540`+`01_q480`+`01_q360`+`01.ogg`+其余游戏数据）；`exefs/main` 4,913,869 B sha256 `476a86a9…`、`main.npdm` 972 B、`control.nacp` 16,384 B sha256 `ac358d18…`、icon 22,454 B sha256 `10daef90…`。
- verify：`galnx package nsp verify --nsp ... --manifest examples/pilot02-iroseka.yaml --nstool /e/galnx-build/m3-tools/nstool.exe --keyset <Ryujinx prod.keys>` → **13 checks / 0 fail / 1 warn**（NCA 签名 FAIL，未签名预期）；PFS0 FileNum 3；Program/Control/Meta 三个 NCA 的 ProgID 均为 `0x010047420000A000`。
- 已知噪声：hacBrewPack 结尾打印 `[tc::io::Path ERROR] Path literal has both forward ('/') and backward ('\') path separators.`，会让脚本里 nstool structure check 报 exit=1；属打包器尾行噪声，不影响产物（verify 全绿）。

## 6. 验收（Citron，**PASS**）

### 6.1 环境与脚本

- Citron Nightly `0237a9b88`；运行器 `scripts/citron_run.sh`（detach 模式）经 `E:/galnx-build/p33/run-lead-119.sh` 驱动，36 步；`video.txt=480`；`async.txt=on`；`debug.txt` 含 `shot=900` 与 `movie=1`。
- 为了让 NSP 使用**内嵌** romfs：运行前把 sdmc 的 `rfvp/game` 临时改名（trap 恢复），否则运行时会优先读 SD 上的 loose 游戏数据。
- run dir：`E:/galnx-build/p33/run-lead-119/20261107-232940-IROSEKA_FHD-010047420000a000`。

### 6.2 结果

- 窗口标题 `citron Nightly | 0237a9b88 | IROSEKA FHD (64-bit) | 1.1.9-test | NVIDIA`；boot `Booting game: 010047420000A000`；36/36 步 0 failed；`steps_diff_ratio=0.820757`。
- 选档生效：`Movie: opened (Switch WMV video-only, streaming, P33 quality) name=movie/01_q480.wmv level=2 bytes=38610038`。
- 原生尺寸：`movie: decoded frame=1 pts=0 ms 854x480 decode_us=15134 convert_us=5764`；片尾 `frame=2880 pts=119958 ms 854x480 decode_us=9591 convert_us=3025`。
- 完整播放：decoded/presented 到 frame 2880（480p 变体全长 120 s），随后 `movie audio: stopped movie/01.ogg`；OP 结束回到标题（n12/n14/n16/n17/n18 同哈希 `34904f92…`，确认为静止标题帧，非卡死）。
- 音轨：`movie audio: loaded movie/01.ogg` → `playing` → 片尾 `stopped`；`audio_status.txt` = `mode=jit driver=1 thread=1 alive=1 cpu=2 pages=10376 rendered_ms=221354 uptime_ms=221246 lag_ms=-108 underrun=0 max_refill_gap_ms=56 stalls=0 stall_ms=0`；`audio_stall.txt` 空。
- 帧循环：`frame_status.txt` = `frame=13425 status=0 async=1`；`perf avg over 60 ticks: vm 0.17 ms, scene 0.02 ms, render 16.30 ms, total 16.49 ms`（Citron 60 fps）；`async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=206000 stage=0 cpu=1 wdt=1 main=13397 stalled=0`；无 `last_error`。
- 截图：n01–n09 逐帧变化（OP 前段），n18 = OP 结束后的标题帧；代表截图 3 张入证据目录。

### 6.3 开销解读（决定真机档位）

480p 变体在**桌面宿主**上的单帧开销：decode 8.4–15.1 ms + convert 3.0–5.8 ms + upload ≈0，合计 11–21 ms/帧；24 fps 的帧预算 41.7 ms，桌面余量约 2×。A57（SWITCH CPU）相对现代桌核按 3–5× 粗估 → 33–105 ms/帧，**可能仍不足 24 fps**；因此保留 360p（17.9 MB，640×360）作为真机兜底，720p 原片仍随包携带用于画质对照。真机档位判定以实际 OP 播放观感 + `decode_us/convert_us` 日志为准。

## 7. 限制与已知问题

1. **真机帧率仍未证**：本轮设备离线（`ping 192.168.31.254` 100% loss），无法 MTP 上传；480p/360p 是否实时、音画是否同步需要真机验收。
2. **默认档是 480p**：不配置 `video.txt` 时画质降为 854×480；若真机 720p 也流畅，应在安装后写 `720`（或后续把默认改回）。
3. **变体只降视频**：音轨始终是同名 `.ogg`（P32 机制），只含 WMA 音轨的其它作品仍需另配 ogg。
4. **触发依赖调试钩子**：本轮仍用 `debug.txt` 的 `movie=1` 触发 OP，剧情内自然触发点在真机尚未确认（P32 遗留风险）。
5. **NSP 逼近 10 GB**：9,977,492,184 B；再加档位/素材会超 FAT32 与安装余量，后续若扩档需重新评估。
6. **日志噪声**：`[ERROR] id must be in range 0..256` ×1（Movie 音轨 `audio source id=8192`，P32 起既有，不影响播放）。
7. **NRO 形态未回归**：本轮只跑 NSP 形态；NRO 走同一 ELF，差异仅在 romfs 与 sdmc 路径，风险低但未复测。

## 8. 复现

1. 从 upstream `9f07ade` 起按顺序应用：016（SDL2 后端）→ … → P31 合并树 → P32 `rfvp-op-audio.patch` → P33 `rfvp-op-quality.patch`；或直接用全量 `rfvp-full-v119.diff`（先对 upstream 与树做 LF 规范化）。
2. 构建：devkitPro MSYS2 环境跑 `platform/switch/build_switch_instr.sh`（本机 `OUT_DIR=/e/galnx-build/p33/lto2`），产物 `rfvp.nro`/`rfvp.elf`。
3. 游戏数据：`/e/galnx-build/p31/game`（含 `movie/01.wmv`、`01_q540/480/360.wmv`、`01.ogg`）。
4. 打包：见 §5.2 命令；`--keyset` 显式传入（不落仓库/日志）。
5. 运行：在 `sdmc:/switch/rfvp/` 写 `video.txt`（`720|540|480|360`）、`async.txt=on`、`debug.txt`（`movie=1` 或 `movie=nil`、`shot=900`）。

## 9. 教训

1. **补丁基准必须是「上一个测试版的合并 commit」**：P33 的 10 个改动文件里有 8 个是「原生尺寸」的连带修改，靠单点 diff 很容易漏；用 LF 规范化的 fullgit2 仓库 + `git reset --hard 3dd9e56` 再复制工作树，才能既完整又可复核（apply 后 1135 文件比对）。
2. **构建脚本不要进补丁**：本机路径硬编码脚本会让 patch 无法在别处 apply；用「apply 后逐文件比对」把这类文件识别出来并显式排除。
3. **No_std 上计时必须用宿主时钟**：`Instant` 只在 tick 前进，帧内耗时会全为 0；换 `perf::start()` 后才拿到真实的 decode/convert 分解。
4. **上采样是白烧的带宽**：720p 源上采样到 1080p 再全屏拉伸，多一份 1080p 缓冲与一次满屏拷贝；改原生尺寸后同一 720p 变体的 convert/upload 明显下降（本轮 480p 已到 3–6 ms / ≈0）。
5. **OP 结束的「静止帧」不是卡死**：n10–n18 截图字节近乎一致容易被误判为渲染停止，必须结合 `decoded/presented` 到 2880 与 `audio stopped` 一起判。
6. **大 NSP 打包静默截断**：hacBrewPack 在磁盘不足时可能不会非零退出（P18 教训），本轮打包前确认 E: 余量充足并核对产物尺寸 ≥ romfs + ~47 MB。
