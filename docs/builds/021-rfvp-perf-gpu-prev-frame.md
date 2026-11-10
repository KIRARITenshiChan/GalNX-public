# 021 · rfvp 真机性能修复：GPU prev-frame 与诊断回读消除

- 日期：2026-11-01
- 引擎：rfvp（upstream 9f07ade + GalNX P9–P14 补丁栈）
- 试点：IROSEKA FHD（五彩斑斓的世界 HD Re:GENERATION）
- 结论：真机反馈的「转场/淡入卡顿、周期性卡顿、音频停滞」中的两类主因已消除或显著收敛；
  Citron 上 perf3→perf4 的 slow 帧总数 154→19、帧>7 的 slow 总时长 9,221.4 ms→639.9 ms；
  真机复验待用户执行（见 §9 U1）。

## 1. 症状（用户真机反馈，m20518 / m20552 / m20493）

用户列出的现象可归为：

1. 转场（logo → 标题、标题 → 正文）明显掉帧，类似卡住半秒；
2. 游戏中每隔数秒周期性一顿；
3. 音频在卡顿时出现停滞/断续；
4. 其他项（光标、性能感知、原生退出、− 键退出确认）已在 P13（NSP v1.0.2）修复。

用户在 Ryujinx 上也能复现同一现象（m20552），说明不是 Citron 特有问题，而是引擎 + 宿主层路径。

## 2. 定位方法（本轮新增）

在宿主层加了逐帧计时与阶段归属，把引擎侧已有 `perf_slow` 行扩展为：

```
rfvp: frame N slow X ms | vm .. scene .. render .. ms | ops .. | mark 500 |
stages(ms): tree .. submit .. end_frame .. vm .. syscalls .. | 
host(ms): begin .. upload ../calls present .. thumb X/calls draws N flush N
```

实现：

- `platform/switch/runtime/sdl_video.c` 新增 `galnx_sdl_take_stats(u64 out[8])`
  （begin / draw calls / upload μs / upload calls / flush calls / present μs / thumb μs / thumb calls），
  在 `begin/present/texture_create/texture_update/read_pixels_scaled` 内计时；
- `platform/switch/host/src/ffi.rs` 每帧取一次并累加，`debug_report` 的慢帧行与 60 帧平均值行输出 host 段；
- 慢帧行只在 `rfvp: frame N slow` 出现，Citron 的 `citron_log.txt` 会完整保留（guest 侧 `debug_report.txt`
  会被下一次运行覆盖，所以以 Citron 日志为证据源）。

这一步把「render 60 ms 但找不到阶段」的盲区补上了：所有未归属时间都落在 host 段。

## 3. 根因（四类）

### R1 · Sprt texture id = -1 的 prev-frame 回读（转场卡顿主因）

引擎在需要「上一帧画面」的精灵（`texture id = -1`，常见于淡入/叠化）时会：

- `crates/rfvp/src/rendering/prim_commands.rs:756-792`：发出 `DrawTextureKey::PrevFrame`（`PREV_FRAME_TEXTURE = u32::MAX - 2`）；
- `crates/rfvp/src/no_std_core.rs:857-872`：每帧调用 `capture_thumbnail(1920,1080)` 回读整屏并上传为纹理。

Switch 宿主上这是 **1920×1080×4 = 8.29 MB 的回读 + 8.29 MB 上传**，实测单次 40–75 ms。
命中转场帧（perf3 帧 81–85）时直接造成 30–85 ms 卡顿。

### R2 · debug_screen.bmp 周期回读（周期性卡顿主因）

`platform/switch/host/src/ffi.rs` 每 300 帧写一张 `debug_screen.bmp`，内含一次全屏回读，
perf3 中每 300 帧的帧 8401/8701/9001 出现 `slow 53.8/49.9/49.7 ms`、而 `render` 只有 0.47–0.64 ms、
`thumb 41.20/39.16/38.15 ms`。这是**诊断伪影**，真机同样会表现为 5 秒一次的规律卡顿。

### R3 · 顶点逐条提交

`galnx_sdl_draw_quad/draw_solid` 每条命令一次 `SDL_RenderGeometry`，perf3 稳态 14 draws → 14 flushes。
虽然稳态时 `present` 已等于 VSync 等待（15.27 ms），但提交次数多会放大每帧 CPU 占用与抖动。

### R4 · 启动/存档/音频（非本轮主目标）

- 启动帧 1：`vfs_read 675.52 ms`、`graph_decode 66.44 ms`（冷读 romfs + 首次解码），属一次性成本；
- 帧 4：`graph_decode 521.47 ms`（首次大量纹理解码）；
- 存档帧：`save_finalize 32.43 ms` + 存档缩略图 `thumb 11.43 ms`（2 次/分钟，`GLOBAL_SAVE_INTERVAL_US = 120 s`）；
- 帧 226：`audio_cmds 150.31 ms`，Citron 音频环境相关，真机是否复现待 U4。

## 4. 修法（P14 补丁，6 文件 +481/−50）

### 4.1 GPU prev-frame（R1）

`platform/switch/runtime/sdl_video.c`：

- 新增 `#define PREV_FRAME_TEXTURE_ID 0xFFFFFFFDu` 与两个 `SDL_TEXTUREACCESS_TARGET` 离屏纹理
  `frame_targets[2]`（1280×720、ABGR8888），`ensure_frame_targets()` 惰性创建；
- `galnx_sdl_begin`：`SDL_SetRenderTarget(renderer, frame_targets[frame_current])`，整帧先画进离屏；
- `batch_flush`：纹理 id 为 `PREV_FRAME_TEXTURE_ID` 时使用 `frame_targets[frame_previous]`，即上一帧的离屏结果；
- `galnx_sdl_present`：flush → 切回默认 target → `RenderCopy(frame_current)` → 交换 `frame_previous/frame_current`
  → overlay → `RenderPresent`；
- `read_pixels_scaled` / `write_screen_bmp` 临时绑定 `frame_previous` 读回后恢复；shutdown 销毁两个 target。

引擎侧最小改动（不改变渲染语义）：

- `crates/rfvp/src/host_api/render.rs`：`RfvpRenderer` 新增 `fn supports_gpu_prev_frame(&self) -> bool { false }`；
- `platform/switch/host/src/render.rs`：`HorizonRenderer` 覆盖为 `true`；
- `crates/rfvp/src/rendering/prim_commands.rs`：新增 `set_prev_frame_gpu(width,height)`（只标记 `prev_frame=Some` 并清 `wants_prev_frame`，不建 CPU 纹理）；
- `crates/rfvp/src/no_std_core.rs:860`：支持 GPU 时走 `set_prev_frame_gpu`，否则保留旧 `capture_thumbnail` 路径。

### 4.2 关闭诊断截图（R2）

`platform/switch/host/src/ffi.rs`：新增 `const DEBUG_SCREEN_ENABLED: bool = false;`，周期写 BMP 走该开关。
（`main.c` 的首次截图仍保留，属一次性成本。）

### 4.3 顶点批处理（R3）

`sdl_video.c`：`DrawBatch`（8192 顶点 / 12288 索引，`SDL_Vertex`），
`batch_begin` 只在 texture/blend/filter/clip 完全一致时继续累积，否则先 flush；
`draw_quad/draw_solid` 改为填顶点入批；`present` 前 flush。
顺序语义不变（只能合并连续同状态），texture create/update/destroy 前先 flush 保证依赖顺序。

### 4.4 host 计时插桩（可观测性）

见 §2；这是后续继续优化的基础设施，不改变渲染行为。

## 5. 验证：perf3 vs perf4（Citron，同一脚本同一路径）

| 指标 | perf3（CPU 回读） | perf4（GPU prev-frame） |
|---|---|---|
| slow 帧行数 | 154 | 19 |
| 帧>7 的 slow 帧 | 151 | 15 |
| ≥30 ms | 150 | 13 |
| ≥50 ms | 136 | 5 |
| slow 总时长 | 12,133.7 ms | 3,567.8 ms |
| 帧>7 的 slow 总时长 | 9,221.4 ms | 639.9 ms |
| thumb 回读 >5 ms 的帧 | 145 | 4 |
| thumb 回读 ≥20 ms 的帧 | 142 | **0** |

- 转场帧 81–85：perf3 帧 81 `slow 84.5 ms / thumb 66.49`、帧 82 `59.1 / 47.30`、帧 83 `59.2 / 47.66`；
  perf4 这些帧**完全不再进入 slow 列表**，且不存在任何 thumb ≥20 ms 的帧。
- 周期性帧：perf3 帧 8401/8701/9001 `slow 53.8/49.9/49.7` 由 thumb 41.20/39.16/38.15 主导；
  perf4 帧 6751/7365/9261 `slow 29.2/30.7/35.6` 全部为 `end_frame/present 27.9–34.3 ms`、`thumb 0`
  （VSync 等待；perf3 也有同类，非回归）。
- 稳态：perf4 `perf avg over 60 ticks: vm 0.55–0.63 ms, render 15.68 ms, total 16.32 ms`，
  `host avg: begin 0.03–0.04, upload 0.00/0, present 15.27–15.40, thumb 0.00/0, draws 14.0, flushes 14.0`
  ⇒ render ≈ present = VSync 等待，渲染管线已无 CPU 侧余量压力（余量极小但稳定 60 fps）。
- 仍存在的尖峰（见 R4）：帧 1 1744.4 ms、帧 4 818.6 ms、帧 2 333.2 ms、帧 226 155.1 ms、
  帧 5819 70.9 ms、帧 6151 42.5 ms（后两者是存档缩略图 10.82 ms + 存档写盘）。

证据：`docs/milestones/evidence/P14-rfvp-perf/`
（`perf3-slow-lines.txt` 154 行、`perf4-slow-lines.txt` 19 行、`perf-compare.txt`、
perf4 标题/淡入/正文截图、`SHA256SUMS.txt`）。

## 6. 视觉正确性

GPU prev-frame 改了「上一帧」的取样来源，必须确认画面无回归。
perf4 目视结果（`perf4-title.png`、`perf4-title-fade.png`、`perf4-story-intro.png`）：

- 标题画面完整（logo/New Game/Continue/Album/Option/Exit/钟面/羽毛），无花屏、无残影；
- 正文开场白底 + 居中「……羽毛。」+ 主机菱形光标，与 P13 已知正确画面一致；
- 存档缩略图仍由 `read_pixels_scaled` 生成（perf4 帧 2/577/6149 的 thumb 10.8–11.8 ms），内容正常（LOAD 面板可见缩略图，见 P13 证据）。

## 7. 产物

| 产物 | 大小 | sha256 |
|---|---|---|
| NRO `rfvp.nro` | 7,843,896 B | `e5373bd76f2beda3583711dea0eded5f00b10f542778bf73522e2fe2c97a2484` |
| ELF `rfvp.elf` | 17,069,080 B | `e4040e7b6e759f6f30ee1351a9e74cc20f6ecb3dda2c7ddd8afb4055c9c9eb46` |
| 增量补丁 `rfvp-perf-gpu-prev-frame.patch` | 32,781 B | `e64dfb71453a49095e303d8ad7f8fb39c4d59727ed7649049e526165299e4501` |
| 全量 diff `rfvp-full.diff` | 107,938 B | `2050a79c6cca851ca9bf1a1ed1a32eeb94c25cd5b03e1af966e97dc539500eca` |
| NSP v1.0.3 | 9,979,441,368 B | `b9e0d6a54a44bf3a3dde8e3f32f22f41d3ee4e009101e9df4f6892e4fb85aa3e` |

NSP v1.0.3 组件：`exefs/main` 4,618,532 B `67a29a73…`、`main.npdm` 972 B `3cfb9877…`、
`control.nacp` 16,384 B `d4c922ee…`、icon 22,454 B `10daef90…`、
romfs 9,932,275,140 B / 161 顶层条目；TitleID `010047420000a000`、version `1.0.3`；hacBrewPack 538 s。

- `galnx package nsp verify`（v1.0.3）：**ok=true，12 checks = 11 ok / 0 fail / 1 warn**（warn = 未签名 NCA，homebrew 预期），
  3 个 NCA 的 ProgID 全为 `0x010047420000A000`；JSON 结果 `E:/galnx-build/p14/verify.json`。
- Citron NSP 形态冒烟（强制 romfs，SD 游戏目录临时改名）：窗口 `IROSEKA FHD (64-bit) | 1.0.3`、
  `Booting game: 010047420000A000`、`rfvp: game root: romfs:/game (romfs mounted)`、`GameConfig { hcb: Some(".iroseka.hcb"), nls: Some(GBK) }`、
  first frame 6.70 s、`exit confirmed by the player` → `quit requested by host event` t=121.17 s、EXCEPTION 0 / panic 0。
- DBI FTP 上传（`ftp://192.168.31.254:5000`，DBI 匿名）：实测 9,979,441,368 B / 1,529.0 s ≈ 6.22 MiB/s（25 分 29 秒，无中断），`UPLOAD_DONE`，DBI 根目录回到投放占位条目（=自动安装）；脚本 `E:/galnx-build/p14/ftp_upload_nsp_103.py`，证据 `docs/milestones/evidence/P14-rfvp-perf/device-upload.txt`。
补丁基线：`E:/galnx-build/rfvp-base-p14`（detach 9f07ade + P13 全量 diff + commit c100e1b），
在该 worktree 应用 `rfvp-perf-gpu-prev-frame.patch` 即得 perf4 树；增量补丁已在
`E:/galnx-build/rfvp-verify-p14`（c100e1b）通过 `git apply --check` 与实应用
（6 文件 +481/−50，与 P14 树一致）。

## 8. 复现

构建（产物落到 `E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro`）：

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m5-switch-build3.sh'
```

Citron perf 探针（脚本 `E:/galnx-build/m5-rfvp-run/run-perf4.sh`，输出 run dir）：

```bash
"D:/Scoop/apps/git/current/bin/bash.exe" -c 'export CITRON_USER_DIR="C:/Users/ACETaffy/AppData/Roaming/citron"; export TEMP=/c/Users/ACETaffy/AppData/Local/Temp; bash /e/galnx-build/m5-rfvp-run/run-perf4.sh'
```

读结果：`<run dir>/citron_log.txt` 中 `rfvp: frame N slow` 行即 §5 数据源；
guest 侧 `sdmc/switch/rfvp/debug_report.txt` 为最近一次运行的可读摘要。

打 NSP：

```bash
bash /e/galnx-build/scripts/build_nsp_game.sh --elf <rfvp.elf> --game-dir /e/galnx-build/m5-rfvp-run/game \
  --title-id 010047420000a000 --name "IROSEKA FHD" --version 1.0.3 --icon <icon-256.jpg> \
  --keyset "<Ryujinx prod.keys>" --hacbrewpack <hacbrewpack.exe> --nstool <nstool.exe> \
  --out /e/galnx-build/p14/out --work /e/galnx-build/p14/work
```

## 9. 已知限制与未验证项

- U1：真机复验未执行（本轮以 Citron 数据定位与验证；用户需在真机确认转场/周期卡顿消失）。
- U2：Citron 的 `present 15.27 ms` 已等于 VSync 预算，perf4 稳态余量极小；真机若仍有轻微掉帧，
  需再压 `render`（下轮候选：离屏 target 直接当纹理、减少全屏合成、纹理格式/滤波）。
- U3：启动帧（vfs_read 675 ms / graph_decode 521 ms）未优化，冷启动仍有一次明显停顿。
- U4：音频 `audio_cmds 150 ms` 只在 Citron 观察到，真机是否复现待 U1 一并确认。
- U5：存档尖峰（save_finalize 32 ms + thumb 11 ms，2 次/分钟）未优化；需要时可延长
  `GLOBAL_SAVE_INTERVAL_US` 或仅在 dirty 时写。
- U6：批处理只合并连续同状态；perf4 仍 14 draws/14 flushes，未进一步合并（当前非瓶颈）。
- U7：GPU prev-frame 依赖 `SDL_TEXTUREACCESS_TARGET`，在 Switch 真机的 SDL2 视频后端需实测（Citron 已通过）。
- U8：`apply_clip` 已不被使用（编译 warning）；清理留到下一轮。

## 10. 参考

- 证据：`docs/milestones/evidence/P14-rfvp-perf/`
- 同系列：`docs/builds/016-rfvp-sdl2-backend.md`（SDL2/GLES2 后端）、
  `docs/builds/019-rfvp-input-mapping.md`（手柄映射）、`docs/builds/020-rfvp-device-fixes.md`（P13 真机修复）
- 补丁：`docs/builds/patches/rfvp-switch/rfvp-perf-gpu-prev-frame.patch`
