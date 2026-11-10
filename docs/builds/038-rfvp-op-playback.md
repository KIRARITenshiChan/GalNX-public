# 038 — P31/P32：rfvp OP 影片播放（720p 视频 + OGG 音轨，v1.1.7-test）

- 日期：2026-11-07
- 状态：Citron 级 PASS（P32 NRO 验收 + Lead NSP 冒烟），真机待验
- 相关：`036-rfvp-op-movie.md`（P29 OP 视频，未并入主线）、`037-rfvp-audio-jit.md`（P30 音频 JIT）、`docs/builds/patches/rfvp-switch/rfvp-op-movie.patch`、`rfvp-audio-jit.patch`、`rfvp-op-audio.patch`
- 目标：用户验收 v1.1.6-test 后明确「剩下的就是把视频解码做好，做完 fvp 就算完美收工」（m28838）。P31 把 P29 的 OP 视频播放合并进 P30 音频 JIT 主线并解决 1080p 无法实时的问题；P32 补上 OP 音轨（原片 WMA 在 Switch 无解码器）。

## 1. 背景

- P29（v1.1.5-test）已让 no_std 构建能解码 WMV/ASF 并播放 OP，但基于 v1.1.4，**未含 P30 音频 JIT**，且 lib 输出 1080p 原片在 Switch 上只能跑到个位数 fps。
- P30（v1.1.6-test）修复 3 秒音频延迟，是当前主线；真机已全部验收通过，但 OP 仍不播（no_std 构建没有视频解码器）。
- 因此需要：P29 视频能力并入 P30 主线 → OP 视频能播；再把 OP 音轨做出来 → OP 有声音；最后按「720p30 源 + 同名 OGG 音轨」出 v1.1.7-test。

## 2. 合并结构（P31）

两个补丁都基于 v1.1.4（1c7c6e4）且都改了 `platform/switch/runtime/main.c`，不能顺序 apply。实际采用**反向合并**：

1. 复制 P29 工作树（= v1.1.4 + P26/P27/P28 + P29）为 `/e/galnx-build/p31/rfvp-v117`；
2. 用 P30 的 4 个文件覆盖：`platform/switch/host/src/audio.rs`（JIT 重写版）、`platform/switch/runtime/main.c`（P30 audio 段），并手工把 P29 的调试钩子 `rfvp_switch_debug_movie()`（读 `sdmc:/switch/rfvp/debug.txt` 的 `movie=1`）插回 `rfvp_switch_async_disable()` 之后；`platform/switch/host/Cargo.toml` 与 `Cargo.lock` 版本 → **1.1.7-test**（保留 `switch-video` feature）；
3. P29 工作树里的 `.git` 是指向 `E:/galnx-build/p25/rfvp-v111/.git/worktrees/rfvp-v115` 的指针文件，**使用前必须删除并重建**，否则污染 p25 仓库。

合并后 `crates/rfvp/src/no_std_core.rs` 的 OP 调试钩子、`videoplayer/horizon.rs` 的流式 WMV 解码、P30 的 JIT 音频线程共存，编译通过（首轮 22 s）。

## 3. OP 素材：1080p 原片不可用 → 720p30 转码

原片规格（`game/movie/01.wmv`，244,843,229 B sha256 `7e84354badaa94816bab4ece3e07d557c7d1b25fced8983396a747aa7d36a6d3`）：

| 项 | 值 |
| --- | --- |
| 容器 | ASF（WMV） |
| 视频 | VC-1 Advanced（WVC1）1920x1080，16 Mbps，59.94 tbr |
| 音频 | WMA v2（wmav2）48 kHz stereo 192 kbps |
| 时长 | 120.49 s |

- 1080p 宿主 bench（`bench-wmv`，decode + `yuv420p_to_rgba_scaled`）：decode 19.97 ms + convert 9.73 ms = **29.7 ms/帧**（≈33.7 fps 上限）；A57 估算 3–5× → 7–16 fps；P29 在 Citron 实测 1080p60 仅 6 fps。
- 转码（ffmpeg 9.0 / gyan build，`D:/Scoop/shims/ffmpeg.exe`）：

```bash
# 720p30（采用）
ffmpeg -i 01.wmv -vf "scale=1280:720,fps=30000/1001" -c:v wmv2 -b:v 8M -an 01.wmv
# 540p30（真机过慢时的退路）
ffmpeg -i 01.wmv -vf "scale=960:540,fps=30000/1001" -c:v wmv2 -b:v 5M -an 01.wmv
# 音轨（原 wmav2 → Ogg Vorbis，与视频同名）
ffmpeg -i 01.wmv -vn -c:a libvorbis -q:a 5 01.ogg
```

| 素材 | 大小 | sha256 | 规格 |
| --- | --- | --- | --- |
| `movie720_30/01.wmv` | 124,386,038 B | `62abe508b4201df8d8a29184dadfe2a479f6b1a152f5a873665c2c3ab253dd93` | 1280x720 wmv2 8 Mbps 29.97 fps 120.02 s |
| `movie540_30/01.wmv` | 84,808,438 B | `76cedf0bc51bfc2ba337879392cea00e4b88a2d63df76ed2ab44bc96a6c14f6e` | 960x540 wmv2 5 Mbps 29.97 fps |
| `movie720_30/01.ogg` | 2,343,033 B | `ca95c441e252406c2322bf2d0a5653aeb26e4bc66ce3cf5028277a257a6b2c8e` | Vorbis 48 kHz stereo 160 kbps 120.06 s |
| `movie720/01.wmv`（早期 60fps 试验，未采用） | 119,352,438 B | `b0ac65ea3bdef12dfa872421e32db0179859c6f052898366b21f8310d64cd6af` | 1280x720 wmv2 8 Mbps 59.94 fps |

宿主 bench（720p30 8.98 ms/帧 ≈111 fps、540p30 5.37 ms/帧）。按 P29 的 Citron 5.6× 折算，Switch 上 720p30 预计 25–40 fps，足以实时；540p30 作为退路。

**决策**：v1.1.7-test 采用 720p30 + 同名 OGG。原 1080p 片保留在游戏目录不动（staging 之外），romfs 内替换为转码版。

## 4. 引擎实现

### 4.1 OP 视频（P29 内容，合并后生效）

- no_std 构建不启用 `native-video`，`videoplayer/mod.rs` 的 fallback 直接 `bail!("no movie decoder in this build")` → `movie_play` 返回 Nil，脚本跳过 OP。
- 方案：`na_wmv_player`（wmv-decoder）做 no_std 移植（新增 `nostd_support.rs` / `byte_read.rs`，video-only），rfvp 新增 feature `switch-video = ["dep:wmv-decoder", "wmv-decoder/nostd"]`。
- `videoplayer/horizon.rs`：`VfsMovieReader` 实现 `wmv_decoder::io::{Read, Seek}`，走 `PackSource::read_at` 流式读取（不整片读入内存）；`WmvDecoder::{Stream, Memory}`；`MAX_DECODE_PER_TICK = 1` 控制每帧最多解一帧；按 PTS 丢弃过期帧并在 stash 中只呈现最新一帧。
- 上屏：每帧上传纹理后 `raise_layer`（unlink + `set_prim_group_in(0, id)`），否则标题层会盖住视频。
- 无音频解码器（WMA 不可用）；P32 前只打「video only」警告。

### 4.2 OP 音轨（P32）

- **不改视频容器**：读取与 `.wmv` 同名的 `.ogg`（`movie/01.wmv` → `movie/01.ogg`）。缺失只 warn，视频继续无声播放。
- `crates/rfvp/src/host_api/audio.rs`：新增 `AudioSlotKind::Movie`；`AudioStreamId::classify` 识别 `AudioStreamId::MOVIE = Self(0x2000)`；`SoftAudioMixer` 的容量检查对 Movie 直接 `Ok(())`（最多一路，后来者替换）。
- `crates/rfvp/src/no_std_core.rs`：调试钩子 `movie_play` 的 flag 由 `Variant::Nil` 改为 `Variant::True`——**Nil 会映射 `MovieMode::LayerNoAudio`，没有音轨**；flag 真值只用于区分 nil/非 nil。正式剧情里 `MoviePlay` 的 flag 由游戏脚本给出，不受这个调试钩子影响。
- `crates/rfvp/src/subsystem/resources/videoplayer/horizon.rs`：新增 `MovieAudio`（`Arc<AudioManager>` + 已读入内存的 `Arc<[u8]>`）：
  - `open()` 时 `request.vfs.read_file("movie/01.ogg")` 一次读入（2.3 MB，可接受）；
  - **首个视频帧呈现时**才 `backend.load(AudioStreamId::MOVIE, &SoundSource::Bytes(bytes), &Vfs::default())` + `backend.play(..., AudioParams{volume:1.0,pan:0.0,repeat:false}, Tween::default(), &vfs)`，让音画一起开始；命令进入 P30 的 JIT 音频队列，帧线程不解码/不混音；
  - `MovieSource::stop` 与 `Drop` 都发 `stop + unload`（错误路径也不会残留）。
- 删除旧的 `warn_movie_audio()`。

## 5. 构建与产物

构建（必须走 devkitPro MSYS2，直接 git-bash 会污染 `CARGO_HOME` 路径）：

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p31/build.sh'
```

| 产物 | 路径 | 大小 | sha256 |
| --- | --- | --- | --- |
| NRO | `target/rfvp-switch/switch/rfvp.nro` | 8,290,360 B | `a8fb7b7ba5f86f7e75f5c9fcc7ca218a75f9a3be1db6a9221581bade8fbf78a8` |
| ELF | `target/rfvp-switch-runtime/rfvp.elf` | 17,684,312 B | `e9ee44c986150d79a0e00b6ccaa5283601561b61a7f6c0646c08ddc1aa60c02f` |
| NSP | `E:/galnx-build/p31/out/IROSEKA_FHD-010047420000a000.nsp` | 9,861,393,624 B | `cb019f27136b5b80936c5c5067477c6a08e19ae02a6535f48e9f12785ba16c7d` |

NSP 组成：title_id `010047420000A000`、romfs **162 项 9,814,160,982 B**（hardlink，100% 内嵌，含 720p30 视频与 OGG）、main 4,912,136 B sha `4b323e7a…`、`main.npdm` 972 B、control.nacp 16,384 B sha `6294d66a…`、icon 22,454 B；hacBrewPack OK in 483 s；nstool structure check exit=1 属已知 hacBrewPack 尾行 `[tc::io::Path ERROR] Path literal has both forward ('/') and backward ('\') path separators.` 告警，不影响产物。

`galnx package nsp verify --manifest examples/pilot02-iroseka.yaml` → **ok=true，12 checks：0 fail / 1 warn**（`verify.signature` 未签名属预期）；3 个 NCA 的 ProgID 全为 `0x010047420000A000`。

### 5.1 补丁与全量 diff

| 平台 | 文件 | 大小 / 行 | sha256 | 基准 |
| --- | --- | --- | --- | --- |
| 增量 P29 | `rfvp-op-movie.patch` | 46,709 B | `95abafc8…` | v1.1.4（1c7c6e4） |
| 增量 P30 | `rfvp-audio-jit.patch` | 1,059 行 | `e81cd49c…` | v1.1.4 树副本（cf5c8bc） |
| 增量 P32 | `rfvp-op-audio.patch` | 338 行（3 文件 +203/−18） | `9e4297798fd6ea74f7d694743aa8645bdbc842552f5e470976537f619f2624c8` | **P31 合并树**（P29+P30，非单一 commit） |
| 全量 | `/e/galnx-build/p31/rfvp-full-v117.diff` | 305,725 B，62 文件 +5,889/−296 | `cf911433f8983779f8c96659f7b989684c1f159d4494f4945affe30cda3a1270` | upstream `9f07ade`（LF 规范化） |

P32 增量补丁的 roundtrip 已在临时树上验证：对 P32 树 `git apply -R --check` → 反向后 `git apply --check` → 前向应用 → 与源树 `diff -r` **逐字节一致**（`ROUNDTRIP_IDENTICAL`）。

全量 diff 的生成方式（重要，见 §8）：把 upstream 9f07ade 与 v1.1.7 树都做 **LF 规范化**后放进临时 git 仓库，`git diff --binary HEAD~1 HEAD`；在 LF 规范化的 upstream 副本上 `git apply --check -p1` = `FULL_APPLY_CHECK_OK`。

## 6. 验收

### 6.1 P32 NRO 形态（Citron，async-fix 交付）

- 环境：Citron Nightly 0237a9b88；`--nro` + sdmc game junction 指向 `E:\galnx-build\m5-rfvp-run\game`；临时把 `movie/01.wmv` 换成 720p30、放 `01.ogg`，跑完已还原（还原后 01.wmv = 244,843,229 B sha `7e84354b…`，无残留 01.ogg）。
- run dir `E:\galnx-build\p32\run-movie-v2\20261107-163426-rfvp`，22 步全 ok（0 failed），11 张截图 sha 全不相同。
- 日志关键行：

```
[INFO] MoviePlay: path=movie/01.wmv flag=True is_layer_effect=false
[INFO] movie audio: loaded movie/01.ogg (Ogg Vorbis, 2343033 bytes); queued for the audio thread
[INFO] Movie: opened (Switch WMV video-only, streaming) name=movie/01.wmv bytes=124386038
[INFO] movie audio: playing movie/01.ogg (Ogg Vorbis, 2343033 bytes)
```

- decoded/presented 各 37 条（frame=1..1080，最后 pts=36003 ms），无 `last_error` / watchdog。
- `audio_status` 终值：`mode=jit driver=1 thread=1 alive=1 cpu=2 pages=2571 rendered_ms=54848 uptime_ms=54735 lag_ms=-113 underrun=0 max_refill_gap_ms=48 stalls=0 stall_ms=0` → OP 期间音频线程正常推进、无 underrun，且延迟仍在 ±300 ms 内（P30 JIT 未回退）。
- `async_status`：`enabled=1 create=0x0 start=0x0 hb=83000 stage=0 cpu=1 wdt=1 main=1094 stalled=0`；`frame_status frame=1095 status=0 async=1`。
- 证据：`E:/galnx-build/p32/evidence/probe-movie-v2/`（23 文件，含 11 张截图 m0..m10、debug_report、三个 status、result.json、input-steps.tsv、staged/restored-movie-sha.txt、run 脚本、SHA256SUMS）。

### 6.2 Lead 最终 NSP 冒烟（内嵌 romfs，v1.1.7-test）

- 脚本 `E:/galnx-build/p32/run-lead-op.sh`：临时把 sdmc `rfvp/game` 改名为 `game-sakura-hold` 让 NSP 使用内嵌 romfs（trap 恢复）；`async.txt=on`；`debug.txt = shot=900 + movie=1`；清旧 status 文件；steps = 等 20 s → 20 次「等 8–10 s + 截图」。
- 判定项：窗口标题含 `1.1.7-test`；`movie audio: loaded ...` / `playing ...` 各出现 1 次；decoded/presented 持续增长；20 张截图 sha 互异且能肉眼看到 OP 画面推进；`audio_status` `underrun=0`；无 `last_error`。
- 结果：见 §6.3（**PASS**，2026-11-07）。

### 6.3 最终 NSP 冒烟结果（Lead 独立，**PASS**）

- 产物与启动：`E:/galnx-build/p31/out/IROSEKA_FHD-010047420000a000.nsp` 9,861,393,624 B sha256 `cb019f27136b5b80936c5c5067477c6a08e19ae02a6535f48e9f12785ba16c7d`；窗口标题含 `IROSEKA FHD (64-bit) | 1.1.7-test`，boot 行 `Booting game: 010047420000A000`。
- 运行：job `bash-dcd6a54213bd45ba` exit 0；run dir `E:/galnx-build/p32/run-lead-op/20261107-165307-IROSEKA_FHD-010047420000a000`；**36/36 步 0 failed**，`steps_diff_ratio=0.822764`；18 张截图（n01..n18）sha256 互不相同、相邻 mad **42.93–81.22** → 画面连续变化（非静止帧）。
- 画面肉眼确认：n01 = staff 字幕「脚本 漆原雪人」、n05 = 「SDキャラ CHAN×CO」、n12/n17 = OP 动画场景（校园走廊、角色 CG）→ 播放内容确为 OP 影片。
- `debug_report.txt`（1,140 行）：`Movie: opened`×1（`movie/01.wmv bytes=124386038`，即 romfs 内嵌 720p30 源）、`movie audio: loaded`×1 / `playing`×1（`movie/01.ogg (Ogg Vorbis, 2343033 bytes)`）、`movie: decoded`=**109** / `presented`=**109**，frame 1..3240，最后 `pts=108075 ms`；无 eof/closed 属正常（harness 在 OP 结束前收尾）。
- 音频：`audio_status` 终值 `mode=jit driver=1 thread=1 alive=1 cpu=2 pages=9405 rendered_ms=200640 uptime_ms=200538 lag_ms=-102 underrun=0 max_refill_gap_ms=44 stalls=0 stall_ms=0` → OP 全程音频线程健康、**underrun=0**、`lag_ms=-102` 未见 P30 JIT 回退。
- async/帧：`async_status = enabled=1 create=0x0 start=0x0 hb=197000 stage=0 cpu=1 wdt=1 main=3233 stalled=0`；`frame_status = frame=3240 status=0 async=1`；无 `last_error`。
- 噪声：1 条 `[ERROR] id must be in range 0..256`（紧随 Movie 音轨 `audio source id=8192` 日志，未观察到播放/音频异常，根因未定）；2 条既有 `[WARN] float_to_int: Invalid value type`；无异常/崩溃。
- 度量口径注意：日志 `decoded frame=... 1920x1080` 中的尺寸是 `self.screen_w/self.screen_h`（输出上采样到屏幕分辨率），**不是源分辨率**；源为 `movie/01.wmv` 720p30 + `movie/01.ogg`。
- 证据：`docs/milestones/evidence/P32a-op-nsp-lead/`（README、result.json、三个 status、debug 摘录 224 行、4 张代表截图、SHA256SUMS）。

## 7. 限制与已知问题

- **Citron 15 FPS**：模拟器下 OP 为 0.5–0.6× 慢放（内容 pts 36 s / 实际约 60 s）；这是 Citron 的 CPU 模拟开销，真机 ARM64 原生预计 720p30 可达实时，**必须真机确认**。
- **无 WMA 解码**：音轨固定取同名 `.ogg`，缺文件时自动退回无声播放；换游戏/换片需要重新转码。
- **OP 触发依赖调试钩子**：目前用 `sdmc:/switch/rfvp/debug.txt` 的 `movie=1` 强制播放 `movie/01.wmv`；游戏剧情里 OP 的真实触发点由 HCB 脚本运行时拼接路径，静态不可见，真机试玩时需确认剧情触发是否同样走通。
- **音轨只有一条**：Ogg 为 160 kbps 单轨（原 WMA 192 kbps），无多语言/多音轨选择。
- 1080p 原片仍不可实时（保留 P29 结论）；romfs 内已替换为 720p30，游戏目录原片未动。
- Citron 每帧状态条仍报告 `Invalid duration` 一类已知噪声（P28 起记录），与本次改动无关。
- OP 播放期间出现过 1 次 `[ERROR] id must be in range 0..256`（紧随 Movie 音轨 `audio source id=8192`），未影响播放、未触发 underrun，根因待查（疑似 Movie 流 id 超出 8-bit 通道参数的校验范围）。

## 8. 复现

1. 取 upstream rfvp `9f07ade` 源码树，按 §5.1 的全量 diff（`rfvp-full-v117.diff`，LF 规范化 upstream 上 `git apply -p1`）得到 v1.1.7 源码；或按 P29/P30/P32 三个增量补丁依次构造（P32 基准为 P31 合并树）。
2. 准备 game staging（162 文件，含 `.iroseka.hcb` 隐藏文件；`movie/01.wmv` 换 720p30、放 `movie/01.ogg`）。
3. `env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p31/build.sh'`；
4. 打包：`E:/galnx-build/p31/build-nsp-117.sh`（`scripts/build_nsp_game.sh` + `--romfs-mode hardlink`、显式 `--keyset`）。

## 9. 教训

- **CRLF 会污染全量 diff**：upstream 副本 1,027 个文本文件是 CRLF，而 P29 工作树是 LF；直接 diff 得到 20.3 MB / 1,035 文件 / +326k 的假差异。正确做法是两侧都做 LF 规范化后再 diff（得到 305,725 B / 62 文件），并在 LF 化副本上验证 `git apply`。（P30 的全量 diff 是 CRLF↔CRLF 才能 apply 到 CRLF 副本，不能作为通用做法。）
- **git worktree 复制后必须删 .git**：P29 工作树的 `.git` 是指向 p25 仓库的指针文件，直接 cp -a 会污染原仓库。
- **main.c 冲突按函数段裁剪**：P29 与 P30 都改 `main.c`，不要整文件覆盖，否则丢调试钩子或丢音频线程。
- **movie_play 的 flag 语义**：Nil = `LayerNoAudio`（无音轨），调试钩子必须传非 nil 才能测音轨。
