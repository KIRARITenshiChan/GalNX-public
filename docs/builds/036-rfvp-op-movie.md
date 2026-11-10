# 036 · P29 OP 影片播放（wmv-decoder no_std 移植 + Switch 视频层上屏）

- 状态：Citron 级已验证（NRO 松散目录：memory 路径与 streaming 路径均视频上屏；回归见 §3.4），待真机验收
- 版本：1.1.5-test（platform/switch/host/Cargo.toml）
- 基线：P28 之后的 v1.1.4-test（worktree 提交 1c7c6e4，父 7210094 = P27）
- 分支/worktree：`/e/galnx-build/p29/rfvp-v115`，P29 提交 `a901961`（父 `1c7c6e4`）

## 1. 问题与根因

IROSEKA 在序章结束、进入第一章前有一段 OP 影片 `movie/01.wmv`（1920x1080 VC-1/WVC1，123.5 s，244,843,229 B，平均码率 ≈15.9 Mbps）。v1.1.4-test 真机与 Citron 上都「跳过 OP」：脚本调用 `MoviePlay` 后立即返回，画面直接进正文。

根因链：

1. `crates/rfvp/src/subsystem/resources/videoplayer/mod.rs` 的 fallback `open()` 在 no_std/Switch 构建下直接 `anyhow::bail!("no movie decoder in this build: {name}")`；
2. `movie_play` 遍历候选路径全部失败后只打一条 `Movie: no playable movie ...`，脚本继续往下执行（P25 起为避免崩溃而加的兜底），表现为「OP 被跳过」；
3. `crates/rfvp/Cargo.toml` 里虽有 `native-video`（wmv-decoder + na_mpeg2_decoder）features，但实测在 Switch no_std 目标上无法编译——`native-video`/`uefi-native-video` 都会拉 `runtime-core-deps`（anyhow/std、serde/std、bincode、chrono、crossbeam-channel、pollster、regex、image 等 std-only 依赖）。实际构建报 `serde_core` 5829 个 E0405/E0425/E0432/E0433/E0463/E0531 错误。

因此正确路线是：**只移植 wmv-decoder 的解码部分到 no_std（视频-only），不启用 runtime-core-deps**，再由 rfvp 新增一个只含解码器的 feature 接进 Switch 构建。

## 2. 实现

### 2.1 `crates/na_wmv_player`（package `wmv-decoder`）no_std 移植

新增/修改：

- `crates/na_wmv_player/Cargo.toml`：
  - `byteorder` 改 `default-features = false`；`thiserror` 改 optional；新增 `hashbrown 0.14.5`（`default-features = false`，optional）；
  - features：`default = ["audio", "std-error"]`、`video-only = []`、`std-error = ["dep:thiserror"]`、`nostd = ["dep:hashbrown"]`；`crate-type = ["rlib"]`（作为 rfvp 的 rlib 依赖，不再产出 cdylib/staticlib）。
- `crates/na_wmv_player/src/nostd_support.rs`（新）：no_std 下最小 `std` 垫片——`array/fmt/mem/result/slice/str` 重导出 core，`ffi::{c_void}`，`hash`（FNV-1a `FnvHasher`/`FnvBuildHasher`），`collections::HashMap = hashbrown::HashMap<K,V,FnvBuildHasher>`，`io`（`Error/ErrorKind/Read/Seek/SeekFrom/Cursor<Vec<u8>>`，`read_exact` 默认实现读满或报 `UnexpectedEof`）。
- `crates/na_wmv_player/src/byte_read.rs`（新）：`ReadBytesExt` trait，提供 `read_u8/read_u16<E: ByteOrder>/read_u32<E>/read_u64<E>/read_i32<E>`（替代 `byteorder::ReadBytesExt` 的 std 依赖）。
- `crates/na_wmv_player/src/lib.rs`：`#![cfg_attr(feature = "nostd", no_std)]`；nostd 下 `extern crate alloc`、`extern crate self as std`、挂 `nostd_support` 并 `pub use` 其子模块；`nostd_prelude` 导出 `Box/format/String/ToString/vec/Vec`；新增 `pub type BytesDecoder = AsfWmv2Decoder<Cursor<Vec<u8>>>` 与 `BytesDecoder::open_bytes(Vec<u8>)`。
- `crates/na_wmv_player/src/error.rs`：nostd 分支手写 `DecoderError{Io,InvalidData,Unsupported,EndOfStream}` + `Display` + `core::error::Error`（std-error 分支仍用 thiserror）。
- 其余 16 个视频源文件仅在头部加 `#[cfg(feature = "nostd")] use crate::nostd_prelude::*;`；`asf.rs` 改用 `byte_read::ReadBytesExt`；`ffi.rs` 在 nostd 下用 `crate::nostd_support::ffi::c_void`。

验证：`cargo check -p wmv-decoder --no-default-features --features video-only,nostd --target platform/switch/aarch64-nintendo-switch-rfvp.json -Zjson-target-spec -Zbuild-std=core,alloc,compiler_builtins` → exit 0（日志 /e/galnx-build/p29/check2.log）。

### 2.2 rfvp 接线

- `crates/rfvp/Cargo.toml:282`：`switch-video = ["dep:wmv-decoder", "wmv-decoder/nostd"]`（不启用 runtime-core-deps）。
- `platform/switch/host/Cargo.toml:3`：版本 `1.1.5-test`；features 追加 `switch-video`：`["no_std", "switch-zlib", "switch-async", "switch-video"]`。
- `crates/rfvp/src/subsystem/resources/videoplayer/mod.rs`：
  - `#[cfg(all(feature = "switch-video", feature = "no_std"))] pub(crate) mod horizon;` 与 `use horizon::open;`；fallback `open()` 的 cfg 改为排除 `switch-video + no_std` 组合（避免重复定义）。
- `crates/rfvp/src/subsystem/resources/videoplayer/horizon.rs`（新，≈340 行）：
  - `VfsMovieReader { source: Arc<dyn PackSource>, base, len, pos }` 实现 `wmv_decoder::io::{Read, Seek}`（读走 `PackSource::read_at`，`Ok(0)` 即 EOF；seek 支持 Start/Current/End，越界报错）；
  - `vfs.rs::pack_location` 扩展：原来只查 `*.bin` pack，现先查 pack，未命中再查 `loose_dir`（`LooseDir::find` 大小写不敏感）并用 `open_pack(dir.storage, real)` 打开该松散文件、返回 `(source, 0, source.len())`。这样 `movie/01.wmv` 这种**松散文件**（游戏目录只有 `*.bin` 是 pack，movie 是真实文件）也能流式读，不必整文件进内存；
  - `enum WmvDecoder { Stream(AsfWmv2Decoder<VfsMovieReader>), Memory(BytesDecoder) }`，`open()` 先 `request.vfs.pack_location(name)` 走流式（日志 `Movie: opened (Switch WMV video-only, streaming)`），streaming 打开失败时才回退 `read_file` 整文件内存（日志 `... memory`）；
  - 每 tick 最多解码 1 帧（`MAX_DECODE_PER_TICK = 1`），`stash` 低水位补帧，按 `pts_ms` 与 `Instant` 丢弃过期帧；第 1 帧与每 30 帧打 `movie: decoded frame=... pts=... ms WxH`；
  - 影片音频（WMA v2）无解码器：`warn_movie_audio()` 打 `movie audio is not decoded on Switch (no WMA decoder); playing video only`。
- `crates/rfvp/src/no_std_core.rs:143/:183`：RfvpCore 新增 `debug_movie_started: bool`；`tick()` 在 `apply_async_decodes` 之后（:664 附近）插一次性调试钩子：若 `horizon::debug_movie_requested()` 为真则调 `movie::movie_play(&mut game_data, "movie/01.wmv", &Variant::Nil)`（仅测试构建使用；投放版本只有 debug.txt 含 `movie=1` 才触发）。
- `platform/switch/runtime/main.c:103`：`int rfvp_switch_debug_movie(void)` 读 `sdmc:/switch/rfvp/debug.txt`，命中 `movie=1` 返回 1；引擎侧 `extern "C"` 调用。
- 构建入口不变（`platform/switch/build_switch.sh`），产物 `rfvp.nro` / `rfvp.elf`。

### 2.3 上屏修复（关键 bug）

首轮实现中视频已经解码成功但画面仍是标题页。原因：

- no_std 渲染端（`rendering/prim_commands.rs` 的 `collect_tree`）**不做 z 排序**，按 prim 子链表顺序 emit；
- `VideoPlayerManager::ensure_layer()` 在 `start()` 时把影片 group（4095）/ sprite（4094）append 到 root 0 末尾，但影片启动发生在一帧很早的位置（调试钩子在第 1 帧），之后标题场景的 prim 继续 attach 到 root 0 末尾，把不透明的标题背景画在影片层之上；
- `refresh_prims(MOVIE_GRAPH_ID)` 也不会命中（sprite 的 `texture_id = -2`，而 `refresh_prims` 比较的是 `texture_id as u16 == graph_id`）。纹理会按 generation 变化上传，但层序被盖住。

修复：`videoplayer/mod.rs` tick 中上传纹理后调用 `raise_layer(motion)`（`mod.rs:276`）：`prim_manager.unlink_prim(MOVIE_GROUP_PRIM_ID)` 后 `set_prim_group_in(0, MOVIE_GROUP_PRIM_ID)`，即每帧把影片 group 重新 append 到 root 0 末尾，保证绘制顺序在场景之上；同时新增 `frames` 计数与 `movie: presented frame=... WxH` 日志（第 1 帧与每 30 帧）。

## 3. Citron 验证

### 3.1 probe1：NRO + 松散 game 目录（memory 路径）

- 脚本：`/e/galnx-build/p29/run-movie.sh`；步骤 `steps-movie.json` 24 步：wait 14 s → 10×(wait 4 s + capture) → wait 2 s → capture；`debug.txt` = `shot=300` + `movie=1`；`async.txt` = `on`。
- run dir：`E:/galnx-build/p29/run-movie/20261107-030627-rfvp`，24/24 步 ok。
- 截图肉眼确认视频上屏：`step-04-m1.png`（sha256 `715d5a94…`）为金色图书馆/飞行书页 OP 画面；`step-12-m5.png`（sha256 `b706cc5b…`）为角色原画 + 制作名单（司田カズヒロ 等）。12 张截图字节数 1.75–3.04 MB（此前标题页仅 ≈1.41 MB）。
- 日志（`sdmc/switch/rfvp/debug_report.txt`）：
  - `[INFO] MoviePlay: path=movie/01.wmv flag=Nil is_layer_effect=true`
  - `[INFO] [diag] vfs path="movie/01.wmv" bytes=244843229 us=1829873 reads=0`
  - `[INFO] Movie: opened (Switch WMV video-only, memory) name=movie/01.wmv bytes=244843229`
  - `[INFO] movie: decoded frame=1 pts=0 ms 1920x1080` / `movie: presented frame=1 1920x1080`，之后每 30 帧成对出现，直到 `frame=720`（约 24 s 内解码并上屏 720 帧）。
- 该路径是松散目录（`pack_location` 返回 None）→ 244 MB 整文件读入内存（Citron 1.83 s）。真机投放使用 NSP 内嵌 romfs，应走 streaming 路径（见 §3.2）。
- 帧率：Citron 状态条约 6 FPS（每帧 149–177 ms，1080p VC-1 软件解码 + 纹理上传）。`decode_us=0` 是测量假象（`platform_time` 的 `Instant` 每 tick 才更新一次，同一帧内 elapsed 恒为 0），不是真实解码耗时。

### 3.2 probe2：NRO + 松散 game 目录（streaming 路径，PASS）

- 修复上一条「松散目录只能整文件读」后重建：NRO 8,286,264 B / sha256 `de972809…`，ELF 17,693,296 B / sha256 `45026b45…`（构建 9.01 s）。
- 脚本/步骤同 §3.1；run dir `E:/galnx-build/p29/run-movie/20261107-031352-rfvp`，24/24 步 ok；Citron 启动后自行退出，无残留。
- 日志关键行：
  - `[INFO] Movie: opened (Switch WMV video-only, streaming) name=movie/01.wmv bytes=244843229`
  - 已无 `[diag] vfs path="movie/01.wmv" bytes=244843229 …` 整文件读行；
  - `movie: decoded frame=1 pts=0 ms 1920x1080` / `movie: presented frame=1 1920x1080`，之后每 30 帧成对出现直到 `frame=720`。
- 截图 12 张字节数 2.11–3.18 MB（标题页仅 ≈1.41 MB），画面持续变化；`async_status`：enabled=1 hb=95000 stage=0 cpu=1 wdt=1 main=753 stalled=0；`frame_status` frame=750 status=0 async=1；无 watchdog/last_error → async=on 不冻结回归 PASS。
- 结论：松散目录与 romfs 共用同一条 VFS streaming 读取链路（`PackSource::read_at`），真机 NSP romfs 应同样走 streaming；NSP 实测见 §3.3。

### 3.3 probe4：NSP + romfs（streaming 路径，PASS）

- NSP：`/e/galnx-build/p29/out/IROSEKA_FHD-010047420000a000-v1.1.5-test.nsp`，9,979,732,184 B / sha256 `9fbc17b04e2d8c4149a96ef5f740ba7a2a5cd381bfe5ca26186fc740c9e0aab0`；hacBrewPack OK 576 s、romfs 161 项 / 9,932,275,140 B、nstool exit=0（PFS0 FileNum 3）。
- 方法：先把 `sdmc:/switch/rfvp/game`（junction → `E:/galnx-build/m5-rfvp-run/game`）移成 `game-p29-hold`，让 Citron 走 NSP 内嵌 romfs；跑完已恢复 junction。`debug.txt` = `shot=300` + `movie=1`，`async.txt` = `on`。21 步（wait 25 s + capture s0 + 9×(wait 4 s + capture s1..s9)）。
- run dir `E:/galnx-build/p29/run-nsp-movie/20261107-032825-IROSEKA_FHD-010047420000a000-v1.1.5-test`；status=loaded、steps_failed=0、20/20 步 ok（wait 步不计入 tsv）。
- 日志关键行（`debug_report.txt` 82,774 B）：
  - `[INFO] MoviePlay: path=movie/01.wmv flag=Nil is_layer_effect=true`
  - `[INFO] Movie: opened (Switch WMV video-only, streaming) name=movie/01.wmv bytes=244843229`
  - 27 条 `movie: decoded frame=... pts=... 1920x1080` + 27 条 `movie: presented frame=... 1920x1080`，每 30 帧成对，直到 `frame=540`；**无 244 MB `vfs path="movie/01.wmv"` 整文件读行** → romfs 同样走 VFS streaming。
  - 仅 1 条 `[ERROR] id must be in range 0..256`（脚本 `ColorSet` id 越界，既有，与影片无关）。
- 截图 10 张 2.21–3.04 MB：s0 2,354,108 / s1 2,676,637 / s2 2,584,429 / s3 3,041,305 / s4 2,880,379 / s5 2,346,060 / s6 2,206,562 / s7 2,828,008 / s8 2,616,159 / s9 2,953,008 B，画面持续变化（OP 帧上屏）。
- async（P22/P26 回归）：`async_status` enabled=1 hb=102000 stage=0 cpu=1 wdt=1 main=777 stalled=0；`frame_status` frame=780 status=0 async=1；无 watchdog/last_error → async=on 不冻结 PASS。
- 音频（P27 交互，记录为限制）：本 run `audio_status` underrun=4、max_underrun_ms=266、min_water=0（ring 147456、produced 4,157,440 / consumed 4,009,984）。这是「debug 钩子在启动即播放 1080p VC-1、主线程仅 ≈6 fps」导致音频生产者（主线程）短时低于消费速率的场景；同版本正常游玩回归（§3.4）underrun=0。OP 段音频本身无 WMA 解码（静音），对听感无影响；真机 OP 帧率更低时可能在 OP 期间出现 underrun 告警，但 OP 结束后正常游玩不受影响。

### 3.4 回归（NRO，album CG + 音频）

- 脚本 `/e/galnx-build/p29/run-nro-regress.sh`，31 步：标题 → Album → CG MODE → 第一格 CG → 6×key:C 切差分；run dir `E:/galnx-build/p29/run-nro-regress/20261107-031705-rfvp`，31/31 步 ok。
- Album 差分：截图字节 1,775,989 / 1,768,482 / 1,775,042 / 1,515,875 / 1,775,991 / 1,768,489 / 1,775,042 / 1,775,048，8 张互不相同（CG 正常切换，无缺失）；`graph cache hit path="graph_vis/SHINKU_e01b"` 与 `..._e01c` 各 1 次（P26 预取链路仍工作）。
- 音频（P27）：`audio_status` driver=1 thread=1 alive=1 cpu=2 cap=147456 ring=147456 min_water=4096 underrun=0 max_underrun_ms=0 starve_ms=0 produced=6008832 consumed=5861376，无 audio_stall 记录。
- async（P22/P26）：`async_status` enabled=1 hb=113000 stage=0 cpu=1 wdt=1 main=7309 stalled=0；`frame_status` frame=7365 status=0 async=1；无 watchdog_status、无 last_error。
- 已知噪声：Album 打开时 `motion.rs` 打 3935 条 `[ERROR] Invalid duration`（P26 证据中已有，非本补丁引入），不影响渲染与输入。

## 4. 已知限制

1. **性能**：1920x1080 VC-1 软件解码在 x86 上约 21 ms/帧（解码）+ 8.8 ms/帧（YUV→RGBA），Citron ≈6 fps，Switch A57 真机预计更低。当前实现按 pts 丢帧以保持接近实时（影片以约 123 s 墙钟时长播放，画面不流畅）。若要更流畅需转码成低分辨率/H.264（平台硬解）或改用预渲染序列。
2. **音频**：No WMA 解码器（na_mpeg2_decoder 未移植），OP 期间只有视频无声音；脚本中影片后的 BGM 不受影响。
3. **内存**：streaming 路径峰值只占解码器内部缓冲（适用于 pack 内文件、松散目录文件、romfs 文件）；只有 streaming 打开失败时才回退 244 MB 整文件读入内存（真机有 OOM 风险，应视为异常兜底）。
4. **调试钩子**：`debug.txt` 含 `movie=1` 才会在第 1 帧自动播放影片，仅供自动化测试；正常流程由游戏脚本触发。

## 5. 产物与证据

| 产物 | 路径 | 大小 | sha256 |
| --- | --- | --- | --- |
| NSP 1.1.5-test | `/e/galnx-build/p29/out/IROSEKA_FHD-010047420000a000-v1.1.5-test.nsp` | 9,979,732,184 B | `9fbc17b04e2d8c4149a96ef5f740ba7a2a5cd381bfe5ca26186fc740c9e0aab0` |
| NRO | `/e/galnx-build/p29/rfvp-v115/target/rfvp-switch/switch/rfvp.nro` | 8,286,264 B | `de972809d87ca7bf5809cefcc7b23ad76fe2e43d0088a0df1d3c88db434fc69f` |
| ELF | `/e/galnx-build/p29/rfvp-v115/target/rfvp-switch-runtime/rfvp.elf` | 17,693,296 B | `45026b45c4e3c859e4a5c8eddc33b4d9a5d463539355e973ab24a1f3fcd9232f` |
| 增量 patch | `docs/builds/patches/rfvp-switch/rfvp-op-movie.patch`（仓库副本，源 /e/galnx-build/p29/rfvp-op-movie.patch） | 46,709 B | `95abafc8facac4b6fa8d242fc8d7f0004ff997f0cbaf64d650afe8c065c0ae2c` |
| 全量 diff | `/e/galnx-build/p29/rfvp-full-v115.diff`（仓库外，不覆盖 rfvp-full.diff） | 101,681 B | `0cea6aed169e19396bdc8a813f1a7e95c4fcbb0dad4acff9f22a29f947ae552d` |
| 证据 | `/e/galnx-build/p29/evidence/` | ≈105 MB / 84 files（含 README.txt、SHA256SUMS.txt） | `SHA256SUMS.txt`（f58c99b5…） |

增量 patch 相对 v1.1.4-test（1c7c6e4）：30 files changed, +947/−29（PATCH_ONTO_P28_OK）；全量 diff 相对 v1.1.0 基线（6c166f6）：40 files changed, +1560/−150（FULL_APPLIES_OK）。两者均已用干净 worktree `git apply --check` 验证。

## 6. 真机验收清单

1. 安装 `IROSEKA_FHD-…-v1.1.5-test.nsp`（标题 ID 010047420000a000），沿用现有存档。
2. 正常游玩到序章结束→第一章，观察 OP：应出现影片画面（不再直接跳正文）；记录实际帧率/卡顿时长。
3. `debug_report.txt` 应出现 `Movie: opened (Switch WMV video-only, streaming)`（NSP romfs 路径），以及 `movie: decoded/presented frame=...` 连续日志。
4. 若想跳过 OP 快速验证其它回归，可在 `sdmc:/switch/rfvp/debug.txt` 写 `movie=0` 或删除该文件（不影响正常脚本触发）。
5. 回归：async=on 不冻结（`async_status` hb 递增、wdt=1）、Album 差分切换、音频连续（`audio_status` underrun=0）。

## 7. 风险与回退

- 回退到「跳过 OP」：去掉 `switch-video` feature（`platform/switch/host/Cargo.toml`）重新构建即可恢复 v1.1.4 行为；`horizon.rs` / no_std_core 钩子均带 `switch-video + no_std` cfg，不影响其它平台。
- 播放性能不达预期时的选项（需产品决策）：(a) 保留低帧率播放并接受；(b) 转码为 720p/H.264 或预渲染帧序列；(c) 脚本侧跳过 OP。
- 内存：pack 内文件、松散目录文件、romfs 文件均走 streaming（P29 补丁扩展了 `pack_location`）；仅在 streaming 打开失败时回退 244 MB 整文件读，属异常兜底。

## 8. 未决问题

- OP 音频（WMA v2）未解码：Citron/真机均静音。若必须还原 OP 声音，需要移植 WMA 解码器或改脚本用 BGM 替代。
- 真机 streaming 读吞吐（P26 目标 8 MB ≈ <300 ms）与 1080p 软解帧率需真机实测；Citron 无法代表 SD/romfs 吞吐。
- Album 界面打开时 `motion.rs` 的 `[ERROR] Invalid duration` 刷屏（3935 条/次，P26 已存在）与本补丁无关，但会挤占 4000 行 ring，真机取证时需注意。