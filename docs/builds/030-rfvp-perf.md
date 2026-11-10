# 030 — rfvp Switch 后端残余卡顿优化（P24，1.0.10-test2）

- 日期：2026-11-05
- 任务：task-51（P24）；上游画像：`docs/experiments/perf-02-device-v109.md`
- 对象：rfvp Switch 后端（`platform/switch/host` + `platform/switch/runtime`，Rust + C）
- 基线：v1.0.9 全量补丁 `docs/builds/patches/rfvp-switch/rfvp-full.diff`（HEAD `9f07ade`）
- 增量补丁：`docs/builds/patches/rfvp-switch/rfvp-perf.patch`（文本 diff 159 行、4 个文件；6057 B，sha256 `9418d20f45c5e58c369fafe88640e6da1aef7baa980043d69a0a6e460bb19844`）
- 构建 wheel：`E:/galnx-build/p24/rfvp-v110`（独立 worktree，未动 `m5-rfvp`）
- 版本标识：`platform/switch/host/Cargo.toml` → `version = "1.0.10-test2"`（NACP 内版本号）

## 1. 背景与目标

真机 v1.0.9 画像（`perf-02-device-v109.md`）显示三类残余卡顿：

| 类别 | 帧数 | p50 | p90 | max | 备注 |
|---|---:|---:|---:|---:|---|
| vfs_read | 223 | 192.59 | 1235.88 | 3382.21 | 同步读 pack |
| graph_decode | 166 | 159.37 | 407.68 | 704.20 | 大图 CPU 解码 |
| audio_cmds | 149 | 4.52 | 543.67 | 1314.16 | >100ms 34 帧 |
| save（真实写盘） | 137 | 89.98 | 95.34 | 115.85 | finalize 59.58 + thumb 24.73 |

任务目标（task-51 验收）：Citron 上同一路线对比 v1.0.9 基线，audio_cmds >100ms 帧清零或大幅下降；vfs_read p50 降 30%+；写盘不带 thumb 回退。

约束：不动 async 语义（P18 async 真机缺陷归 task-53）；只做同步路径优化；不引入新依赖。

## 2. 根因定位（源码）

### 2.1 audio_cmds 尖峰 = 主线程整文件读+解码

- `crates/rfvp/src/no_std_core.rs` L1097-1158 `flush_audio` 处理 `AudioCommand::LoadStream`：
  ```rust
  match host.audio().load_stream(id, kind, stream.clone()) {
      Err(RfvpError::Unsupported) => stream.read_all().and_then(|bytes| host.audio().load_encoded(id, kind, &bytes)),
      other => other,
  }
  ```
- Switch 后端 `platform/switch/host/src/audio.rs` 原先只实现 `load_encoded`/`create_stream`，**没有覆写 `load_stream`**，命中 trait 默认 `Err(Unsupported)`（`crates/rfvp/src/host_api/audio.rs` L151-158）⇒ 回退到主线程 `read_all()`（整条 BGM/语音从 SD 全量读入）+ `load_encoded`（整块解码挂到 mixer）。
- `crates/rfvp/src/rfvp_audio/commands.rs` L69-76 `STREAM_FROM_BYTES = 1 MiB`：长度 ≥1MiB 的音源走 `LoadStream`，因此尖峰集中在换 BGM/长语音（真机 f777 1314ms、f825 1174ms）。
- 3DS 后端已有完整参考实现（`platform/3ds/host/src/audio.rs` L102-110、L160-234）：`load_stream` 直接转给 `SoftAudioMixer::load_stream`，解码器持有 `AudioByteStream`，通过 C 回调按需读。

### 2.2 graph_decode / vfs_read = 大纹理无法进缓存

真机 `debug_report.txt`（`E:/galnx-build/p21/device-logs/debug_report.txt`）证据：

- texture LRU 常态打满：`[cache] texture put size=7850880 total=155899188/167772160` → `8294400 total=164320052/167772160` → `240640 total=166891160/167772160`
- 4K CG（3840x2160x4 = 33,177,600 B）提交时 total 不再增长：`size=33177600 total=164744140/167772160` ⇒ 被 `MAX_ENTRY_BYTES = 16 MiB` 的单条上限直接丢弃（`crates/rfvp/src/subsystem/resources/resource_cache.rs` Lru::put 开头 `if size > MAX_ENTRY_BYTES { return; }`），**永不缓存**，每次出现都要重新 SD 读 + CPU 解码。
- 单次慢读/解码量级（同文件）：`vfs path="graph/EF_e08" bytes=452200 us=85900`、`vfs path="graph/opt_parts" bytes=520210 us=74066`；`graph decoded path="graph/EF_e08" 1920x1080 us=55668`、`graph decoded path="graph/opt_parts" 1740x1128 us=60550`。
- bytes 缓存只用 45.5MB / 192MB ⇒ 瓶颈在 texture 侧容量与单条上限，不在 bytes 侧。

### 2.3 写盘（本轮未改）

真机 save 慢帧 = `SAVE_FINALIZE` p50 59.58ms（postcard 编码 + 写盘）+ `PSV_THUMBNAIL` p50 24.73ms（GPU readback）。缩略图路径见 `platform/switch/runtime/sdl_video.c` L812-897 `galnx_sdl_read_pixels_scaled`：快路径要求 `frame_targets_ready && frame_previous != frame_current`，否则回退为 1920x1080 全屏 readback + CPU box filter。本轮未改动该路径（见 §7 未验证/遗留）。

## 3. 改动内容（增量补丁）

补丁：`docs/builds/patches/rfvp-switch/rfvp-perf.patch`（在 `rfvp-full.diff` 之上应用；`git apply` 干净通过，已在基线 worktree 验证）。

### 3.1 Switch 音频后端实现流式 BGM/语音（`platform/switch/host/src/audio.rs`，+72 行）

照 3DS 后端模式移植：

1. 新增 extern 声明 `rfvp_ogg_open_stream`（`crates/rfvp/vendor/rfvp_ogg_vorbis.h` L42-47 已有 C 实现，Switch 构建已编译该 vendor 文件，**C 侧零改动**）。
2. `impl RfvpAudio for HorizonAudio` 新增：
   ```rust
   fn load_stream(&mut self, id: u32, kind: AudioKind, stream: AudioByteStream) -> RfvpResult<()> {
       self.mixer.load_stream(id, kind, stream)
   }
   ```
3. `HorizonVorbisDecoder` 增加 `stream: Option<Box<AudioByteStream>>` 字段保活；新增 `unsafe extern "C" fn read_stream(user, offset, buf, len)` 回调（`AudioByteStream::read_at`），实现 `SoftAudioVorbis::open_stream` → `rfvp_ogg_open_stream`。

效果：`LoadStream` 命中 `SoftAudioMixer::load_stream`（`crates/rfvp/src/host_api/audio.rs` L326-337），主线程只付打开头部成本（vendor 先读 32KiB 解析头，缓冲上限 1MiB）；**整条流的读与解码在 audio_pump 线程**（`platform/switch/runtime/main.c` L259-275 调用 `rfvp_switch_audio_render`），不再阻塞主线程。

### 3.2 放大 texture 缓存（`crates/rfvp/src/subsystem/resources/resource_cache.rs`，2 个常量）

```rust
-const TEXTURE_BUDGET: usize = 160 * 1024 * 1024;
+const TEXTURE_BUDGET: usize = 256 * 1024 * 1024;
-const MAX_ENTRY_BYTES: usize = 16 * 1024 * 1024;
+const MAX_ENTRY_BYTES: usize = 48 * 1024 * 1024;
```

- 256MB 预算：覆盖真机观测的 155-167MB 常态使用 + 若干 4K CG，减少 LRU 抖动导致的重复解码。
- 48MB 单条上限：使 33,177,600 B 的 4K CG 可入缓存（真机证据中该尺寸被丢弃）。
- 未改 parts(48MB)/bytes(192MB) 预算与预取策略。

### 3.3 版本号（`platform/switch/host/Cargo.toml`、`Cargo.lock`）

`version = "1.0.10-test2"`，仅用于测试版 NACP 标识（`build_switch.sh` L27 读取该字段传给 `nacptool`）。

## 4. 构建

工作树：`E:/galnx-build/p24/rfvp-v110` = `git -C E:/galnx-build/m5-rfvp worktree add --detach ... 9f07ade` + `git apply rfvp-full.diff` + 本增量补丁。

构建脚本：`E:/galnx-build/p24-build.sh`（由 `m5-build-instr.sh` 改写，路径指向 p24 worktree，去掉 rustup 联网行），经 WMI 脱离启动：
```
cmd.exe /c E:\galnx-build\p24\launch-build.cmd
  → run2.sh (echo pid; exec) → bash /e/galnx-build/p24-build.sh
```
调用姿势：`env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash ...'`。

结果：`BUILD_EXIT=0`，cargo 增量 11.53s（全量首编约 20s 量级），产物：

- ELF：`E:/galnx-build/p24/rfvp-v110/target/rfvp-switch-runtime/rfvp.elf`
- NRO：`E:/galnx-build/p24/rfvp-v110/target/rfvp-switch/switch/rfvp.nro`
  - 大小 7,929,912 B
  - sha256 `ee1a50eacf5549b1938df764f2527cdc79a16ff963c4f09618290b9cccab0d8c`

阶段 A（仅音频流式、版本 1.0.10-test）NRO 为 7,929,912 B sha256 `0353323b07ba1720c169c7256994e980bd86e698bb7e94cf386fce047dfd02f1`；其 NSP 保留为 `E:/galnx-build/p24/out/IROSEKA_FHD-1.0.10-test-audio.nsp`（9,979,497,176 B）。

## 5. NSP 打包

脚本：`E:/galnx-build/p24/build-nsp.sh` → 仓库 `scripts/build_nsp_game.sh`（自包含 romfs 模式，IROSEKA FHD romfs ≈9.9GB，故 NSP ≈10GB；hacBrewPack 单次约 10 分钟）。

参数：title-id `010047420000a000`，name `IROSEKA FHD`，version `1.0.10-test2`，icon `examples/pilot02/icon-256.jpg`，`--romfs-mode hardlink`，keyset `Ryujinx-canary/portable/system/prod.keys`。

产物：`E:/galnx-build/p24/out/IROSEKA_FHD-010047420000a000.nsp`（9,979,497,176 B，sha256 `79aedc0382abe55260b40d27fb611995a77823ee13885a0e99f0c57c1653ffaa`）。

基线对照 NSP（v1.0.9，`E:/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp`）：9,979,495,640 B，sha256 `726bb2d1b0494256b5e5b12ca9d8e08b053ab56022593f562762d256c0d3c0d9`。

## 6. 验证（Citron）

### 6.1 运行条件与轮次

| 轮次 | NSP | 版本 | NSP sha256 | Citron 启动 | 结束 | 路线步数 | 结果 |
|---|---|---|---|---|---|---|---|
| baseline | p21/out/IROSEKA_FHD-010047420000a000.nsp | 1.0.9 | 726bb2d1…3c0d9 | 23:00:22（pid 29360） | t=407 s 时模拟被 Citron 停止（见 6.4） | 159 ok / 3 capture fail（step130/152/162） | 不完整（仅覆盖前 407 s，约 frame 23328） |
| test2 | p24/out/IROSEKA_FHD-010047420000a000.nsp | 1.0.10-test2 | 79aedc03…53ffaa | 23:11:33（pid 31160） | 23:20:31 | 162/162 ok | 完整 |

- 路线同一份：`E:/galnx-build/p22/steps-long.json`（sha256 `617310b8776d26687f76d6801ad886d1d78361e17b4836506ec392d360449f23`，162 步，纯 wait 累计 329,000 ms）；两轮均把虚拟 SD 的 `switch/rfvp/game` 移出（→ `game-hold`）以强制走 NSP 内嵌 romfs，加载路径一致；两轮均写 `debug.txt`（`shot=900`）开启 perf/diag 输出。
- 对照有效性锚点：两轮 slow frame 帧号高度对应（1、2、4、245、902、~1800、~2450、~4100、5239、~6800），且 frame 4 的逐阶段耗时几乎相同（总 518.1 vs 520.0 ms、vfs_read 169.81 vs 170.22 ms、audio_cmds 0.04 vs 0.04 ms）⇒ 慢帧日志可在同内容处直接对照。
- test2 结果证据：`result.json` status=loaded、window_title 含 `1.0.10-test2`、boot_line `[ 2.927741] … BootGame 010047420000A000`、final capture `step-162-t9-final.png` nonblack=0.9018、162 步全 ok（harness 断言 `ok=162 failed=0`）。

### 6.2 主线程慢帧阶段对比（perf_slow.log）

单位为 ms，样本为两轮各自记录的 slow frame。

| 阶段 | 基线 n / p50 / p90 / max / >100ms | 新版 n / p50 / p90 / max / >100ms | 判读 |
|---|---|---|---|
| audio_cmds | 5 / 8.25 / 273.13 / **335.17** / 2 | 4 / 14.73 / 26.98 / **29.39** / **0** | max −91.2%，>100 ms 由 2 帧降为 0 帧 |
| vfs_read | 5 / 169.81 / 737.30 / 887.28 / 4 | 4 / 320.44 / 843.83 / 1003.75 / 4 | 未改善（本补丁未改 vfs 读路径，见 6.5） |
| graph_decode | 4 / 97.53 / 196.30 / 215.01 / 2 | 4 / 93.83 / 194.73 / 215.84 / 2 | 持平 |
| parts_decode | 2 / 72.59 / 74.80 / 75.35 / 0 | 2 / 71.50 / 72.41 / 72.64 / 0 | 持平 |
| save | 4 / 38.16 / 77.92 / 80.77 / 0 | 4 / 7.66 / 42.71 / 57.49 / 0 | 样本少、方向偏轻，不足以定论 |
| save_finalize | 1 / 30.67 / — / 30.67 / 0 | 1 / 35.93 / — / 35.93 / 0 | 单样本，持平（写盘路径未改） |
| save_snapshot | 2 / 5.50 / 7.18 / 7.60 / 0 | 3 / 5.26 / 7.01 / 7.45 / 0 | 持平 |
| syscalls | 13 / 9.97 / 259.75 / 393.13 / 4 | 11 / 9.93 / 279.22 / 394.68 / 3 | 持平（含音频回退读盘的牵连） |
| vm | 14 / 28.29 / 359.63 / 861.59 / 5 | 12 / 37.23 / 385.60 / 805.78 / 4 | 持平（首帧/场景切换的大头） |
| tree | 14 / 4.01 / 54.20 / 81.11 / 0 | 12 / 9.26 / 59.09 / 83.90 / 0 | 持平 |
| end_frame | 14 / 0.64 / 18.75 / 70.06 / 0 | 12 / 0.86 / 2.12 / 80.20 / 0 | 持平 |
| host.thumb | 14 / 0.00 / 1.09 / 28.36（mean 2.14） | 12 / 0.00 / 4.55 / 9.98（mean 1.38） | 样本少，方向偏轻 |
| **总（slow frame）** | **14 / 158.45 / 1066.48 / 1593.60** | **12 / 115.75 / 882.79 / 1780.90** | p50 −26.9%、p90 −17.2%；max 由启动帧决定（新版 1780.9 更差，属首帧波动） |

### 6.3 同内容逐帧对照（本轮最有力的证据）

| 帧号（基线 / 新版） | 基线 total / audio_cmds / vfs_read | 新版 total / audio_cmds / vfs_read | 判读 |
|---|---|---|---|
| 4 / 4 | 518.1 / 0.04 / 169.81 | 520.0 / 0.04 / 170.22 | 同内容下测量可复现（差异 <1%），对照有效 |
| 245 / 245 | 183.4 / **180.08** / — | 32.0 / **29.39** / — | audio_cmds −83.7%，总帧 −82.5% |
| 2439 / 2501 | 1301.5 / **335.17** / 512.32 | 923.1 / **21.34** / 470.67 | audio_cmds −93.6%，vfs_read −8.1%，总帧 −29.1% |

- 基线两处 audio_cmds >100 ms 的慢帧正是上表后两行；新版在对应内容帧上分别降到 29.39 / 21.34 ms，与 §2 的根因判断（`flush_audio` 在主线程 `read_all` 回退被 `load_stream` 流式实现消除）一致。
- 独立重复性：22:27–22:37 另跑过一次 1.0.10-test2 同路线（统计留档 `E:/galnx-build/p24/perf-test2.json`，原始日志被后续并发轮覆盖）——同样 0 个 audio_cmds >100 ms（max 34.37 ms）、vfs_read p50 305.06 ms，与本轮结论一致 ⇒ audio 结论对运行间波动稳健，vfs 未改善也一致。
- 注意运行间波动较大：该独立轮记录到 39 个 slow frame（本轮 12 个），因此**不能用 slow frame 计数直接比较总量**，只能逐阶段/逐内容帧对照。

### 6.4 基线轮异常中止（证据链）

- 路线时间戳（`input-steps.tsv`）：step128 key M（Plus）@399.8 s → step130 capture 失败 @~404.4 s → step131 key X @405.7 s，即 Citron 在 Plus 按下后 4–5 s 消失。
- Citron 日志（`C:/Users/ACETaffy/AppData/Roaming/citron/log/citron_log.txt`）最后一条 perf 行为 t=398.376（frame 23328）；t=407.048 起依次出现：`Service.NVDRV <Warning> nvhost_gpu.cpp:162 SetErrorNotifier (STUBBED)` → `syncpoint_manager.cpp:74/113 Assertion Failed` ×12 → `nvmap.cpp:273 UnpinHandle: Pin count imbalance detected` → `AM SetFocusHandlingMode`/`SetOutOfFocusSuspendingEnabled` → `VI SetWindowVisibility managed_layer=1 visible=false` → `bootmanager.h:110 ForceStop` ×4 → `ShutdownMainProcess [Before: 4038MB] -> [After: 3003MB]` → `OnEmulationStopped: … Emulation stopped`。
- 无 guest 崩溃、无新 crash dump（最新仍是 22:22 的 `citron.exe.31964.dmp` 69,946,267 B，属更早的字体合成崩溃）；harness 只记录到窗口消失（`GetWindowRect failed`），`result.json` 仍为 status=loaded / killed=false。
- 根因未定论，候选：① Citron NVDRV syncpoint 断言导致模拟线程被自停（与高纹理 churn 相关，未证）；② guest 主动退出（无法解释为何恰在 Plus 后）；③ 外部干预（已排除，当时只有本轮的 test2 前序流程在排队）。
- 影响：基线数据只覆盖前 407 s；两轮前 128 s 的 diag 内容完全一致（同为 10 次 graph decode、154 次 texture put，见 6.5），故**前段对比成立**，后段（含 Plus 菜单/存档界面）缺失；2026-11-05 23:33/23:36 两次补跑基线均 abort（见 §7.7），故以「同内容前 407 s」为正式对比窗口。

### 6.5 diag 统计（debug_report.txt）与限制

- **日志容量上限导致窗口不对称**：`debug_report.txt` 约 107.5 KB / 899 条 `[diag t=…]` 行即写满停止。基线写满于 392.6 s（≈覆盖整轮 407 s），新版写满于 128.3 s（事件更密）⇒ 两轮 diag 的**绝对计数/分位数不可直接跨轮比较**。
- 同内容项对照（两轮首 128 s 的 vfs 慢读，同一批资源）：

| 资源 | 基线 bytes / us | 新版 bytes / us | 变化 |
|---|---|---|---|
| graph_bg/BG043_000 | 3,838,866 / 164,123 | 3,838,866 / 140,576 | −14.4% |
| graph_bs/CHR_…昞忣 | 3,447,414 / 140,464 | 3,447,414 / 136,866 | −2.6% |
| graph_bs/CHR_…昞忣（另一张） | 3,380,169 / 104,500 | 3,380,169 / 107,627 | +3.0% |
| graph/title_bg1_A | 2,051,578 / 105,842 | 2,051,578 / 102,165 | −3.5% |
| graph_bg/BG043_000b | 2,223,174 / 86,636 | 2,223,174 / 84,691 | −2.2% |
| graph/slf_load_bg | 1,653,827 / 50,086 | 1,653,827 / 64,722 | +29.2% |
| graph/diss07 | 1,459,381 / 49,609 | 1,459,381 / 53,006 | +6.8% |

  （vfs 慢读整体：基线 n=41 p50 30,538 us；新版 n=43 p50 33,232 us，即 +8.8%。同内容项互有涨跌、无系统性下降，且本补丁未改动 vfs 读路径。）
- `graph_decode`：基线 n=10 p50 38,562 us / max 86,311 us；新版 n=10 p50 39,245 us / max 81,861 us ⇒ 持平。`graph_cache_hits` 127 vs 120（同窗口）⇒ 持平。
- 纹理缓存：两轮前 128 s 均为 `texture put n=154`、`max_total=123,259,040 B` 完全相同；基线预算 167,772,160 B（160 MiB）、新版 268,435,456 B（256 MiB）；`over_entry_limit_size_entries=0`（旧 16 MiB 单条上限下也为 0 —— 可观测窗口内最大单条 12,960,000 B）。⇒ **本轮路线前 128 s 既未触及旧预算也未触碰旧单条上限，缓存改动在此窗口内无可观测收益**；4K CG（33,177,600 B > 旧 16 MiB 上限）未出现在可观测窗口，需后续 CG 场景/真机复测。
- `save_capture`：两轮均为 n=0（可观测窗口内未触发缩略图/存档捕获）⇒ 写盘相关验收项本轮无数据。

### 6.6 验收判定

| 验收项（task-51） | 判据 | 本轮结果 | 判定 |
|---|---|---|---|
| audio>100 ms 帧清零或大幅下降 | 基线 audio_cmds >100 ms 帧数/峰值 | 2 帧 → **0 帧**；峰值 335.17 → 29.39 ms（同内容帧 −83.7% / −93.6%） | **达成**（Citron；真机待复测） |
| vfs p50 降 30%+ | 同路线 vfs p50 | slow-frame 样本 169.81 → 320.44 ms；diag 同窗口 30,538 → 33,232 us（+8.8%）；同内容项 ±15% 内涨跌 | **未达成**（补丁未触及 vfs 路径） |
| 写盘不带 thumb 回退 | save/thumb 阶段耗时与快路径证据 | `save_capture` 无样本；slow frame 中 save 38.16 → 7.66 ms（样本各 4） | **未验证** |
| 不引入新依赖、不动 async 语义 | 补丁内容 | 仅 4 文件（`platform/switch/host/src/audio.rs`、`platform/switch/host/Cargo.toml`、`Cargo.lock`、`crates/rfvp/src/subsystem/resources/resource_cache.rs`），无新 crate | **达成** |

### 6.7 本轮验证的局限

- 基线轮仅前 407 s（见 6.4），后段（Plus 菜单、存档界面、换场景后段）无基线数据；2026-11-05 两次补跑全量基线均 abort（撞车 / Citron 被占用，见 §7.7），该缺口保留。
- 所有数据来自 Citron（main-0237a9b88），不是真机；SD I/O 与 GPU readback 成本不同，真机数值需下一轮复测。
- slow frame 只记录超过阈值的帧，统计量受运行间波动影响（本路线独立两轮 12 vs 39 帧），故只做逐阶段/同内容帧对照，不做 slow frame 计数对比。
- diag 日志窗口不对称（6.5），vfs/纹理的绝对值不作为验收依据。


## 7. 未验证 / 遗留

1. **真机未验证**：本轮所有对比在 Citron（main-0237a9b88）完成，真机 SD I/O 与 GPU readback 成本不同；audio>100ms 与 vfs p50 的真机数值需下一轮真机复测（用同一 NSP 与同一 debug.txt 直方图）。
2. **写盘（save）路径未改**：finalize 的 postcard 编码 + 写盘、缩略图 24-25ms readback 仍在主线程（`no_std_core.rs` L846-930）。真机验收项「写盘不带 thumb 回退」本轮未优化，仅采集了 Citron 数据。
3. **vfs_read 深层优化未做**：未实现后台预取 worker（本补丁只通过扩大缓存减少重复读+解码）；如 vfs p50 降幅不足，下一步是启动/场景切换前的异步预取（需与 task-53 的 async 返工协调，避免语义冲突）。
4. **音频流式副作用未验**：BGM 循环切头（`rfvp_ogg_seek_start` 重开 headers）、语音快进/打断、audio 线程与主线程共用 pack 文件 `Mutex` 的竞争（可能偶发 underrun）均未做听感/长跑验证。
5. **内存占用上升**：texture 预算 160MB→256MB、单条 48MB，Switch 应用内存预算下需真机确认无 OOM（Citron 未测内存上限）。
6. 阶段 A（仅音频）NSP 与最终版 NSP 的 A/B 对比未做时间片分离（两者分别跑一次同路线）。
7. **基线轮中止根因未定**：v1.0.9 基线轮在 t=407 s 被 Citron 停掉（NVDRV syncpoint 断言 → ForceStop，见 §6.4），导致后段无基线数据；若再复现会再次缺失对比。建议：补跑基线全量，并把该日志片段报给 Citron 侧；必要时改用「同内容前 407 s」作为正式基线窗口。补跑记录（2026-11-05）：第 1 次 23:31:52 启动（`E:/galnx-build/p24/launch-bl.cmd` → run-session.sh baseline），与 Lead 的 P25 验收轮 23:32:26–23:35 重叠（单实例转发），Citron 23:33:50 起、23:34:45 消失且无 result.json（`E:/galnx-build/p24/session-baseline.log`），整轮作废；第 2 次 23:36:20 启动，因 Citron 被他人占用（pid 29872，23:35:34–23:45:43），等待 300 s 后 `[session] ABORT citron busy`（23:41:29）。23:55 交付窗口内无法再跑满约 11 分钟的全量，按 Lead 指示以现有 407 s 基线数据交付并保留该限制。
8. **diag 日志容量上限导致窗口不对称**：`debug_report.txt` 约 107.5 KB / 899 条 diag 行写满即停（基线覆盖 392.6 s、新版仅 128.3 s），diag 绝对值不可跨轮比较，只做同内容项对照（§6.5）。
9. **真机 audio 副作用未验**：见 §7.4；流式实现改变了 BGM/长语音的读取路径，真机上需检查 BGM 循环切头、语音快进/打断、以及 pack 文件 `Mutex` 竞争下的 underrun。

## 8. 复现命令

```bash
# 1) 基线 worktree
git -C E:/galnx-build/m5-rfvp worktree add --detach /e/galnx-build/p24/rfvp-v110 9f07ade
git -C /e/galnx-build/p24/rfvp-v110 apply docs/builds/patches/rfvp-switch/rfvp-full.diff
git -C /e/galnx-build/p24/rfvp-v110 apply docs/builds/patches/rfvp-switch/rfvp-perf.patch

# 2) 构建 NRO
#    （脚本已封装：/e/galnx-build/p24-build.sh）
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p24-build.sh'

# 3) 打包 NSP
bash /e/galnx-build/p24/build-nsp.sh

# 4) Citron 对比（同一路线：标题→新游戏→推进→backlog/存档→换场景）
bash /e/galnx-build/p24/run-citron.sh baseline /e/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp
bash /e/galnx-build/p24/run-citron.sh test2    /e/galnx-build/p24/out/IROSEKA_FHD-010047420000a000.nsp
python /e/galnx-build/p24/parse_perf.py /e/galnx-build/p24/evidence/baseline/perf_slow.log
python /e/galnx-build/p24/parse_perf.py /e/galnx-build/p24/evidence/test2/perf_slow.log
python /e/galnx-build/p24/parse_diag.py /e/galnx-build/p24/evidence/baseline/debug_report.txt
python /e/galnx-build/p24/parse_diag.py /e/galnx-build/p24/evidence/test2/debug_report.txt
```

## 9. 证据路径

- 构建日志：`E:/galnx-build/p24/build-v110.log`、`E:/galnx-build/p24/build-nsp.log`
- 增量补丁：`E:/galnx-build/p24/rfvp-perf.patch` → 入仓 `docs/builds/patches/rfvp-switch/rfvp-perf.patch`
- Citron 运行目录：`E:/galnx-build/p24/run-<label>/`；日志/截图拷贝：`E:/galnx-build/p24/evidence/<label>/`
- 统计 JSON：test2 为 `E:/galnx-build/p24/evidence/test2/{perf-full.json,diag-full.json,result.json}`；基线的 `perf-win.json`/`diag-w128.json` 已随补跑 abort 的 `rm -rf` 丢失，基线统计数值保留在 `E:/galnx-build/p24/compare-win.json` 与 `compare-full.json` 内
- 路线：`E:/galnx-build/p22/steps-long.json`（6,631 B，sha256 `617310b8776d26687f76d6801ad886d1d78361e17b4836506ec392d360449f23`，162 步，纯 wait 累计 329,000 ms）
- 统计产物：`E:/galnx-build/p24/compare-win.json`（同内容窗口 max_frame=6828 / max_t=128 s）、`E:/galnx-build/p24/compare-full.json`（全量）、`evidence/<label>/perf-full.json`、`evidence/test2/diag-full.json`（基线 diag-w128 数值已并入 `compare-win.json`，原始 diag 文件丢失）、`E:/galnx-build/p24/perf-test2.json`（22:27 独立重复轮留档）
- Citron run 目录：baseline `E:/galnx-build/p24/run-baseline/20261105-225832-IROSEKA_FHD-010047420000a000/`（result.json 22,805 B）、test2 `E:/galnx-build/p24/run-test2/20261105-230948-IROSEKA_FHD-010047420000a000/`（result.json 23,185 B，12 张 step-*.png 截图，含 `step-162-t9-final.png`）
- 基线轮中止现场：`C:/Users/ACETaffy/AppData/Roaming/citron/log/citron_log.txt` t=398.376→407.048 段；更早的字体合成崩溃转储 `C:/Users/ACETaffy/AppData/Local/CrashDumps/citron.exe.31964.dmp` 69,946,267 B（与本轮结论无关）。
- 补跑 abort 现场：`E:/galnx-build/p24/session-baseline.log`（第 1 次，23:33:42 建 job、23:34:45 窗口消失无 result.json）、`E:/galnx-build/p24/evidence/baseline-abort-20261105-2334/`（abort 轮残片：async_status.txt 81 B、debug_report.txt 91,236 B、frame_status.txt 28 B、perf_slow.log 2,633 B）。原 407 s 基线原始日志已被第 2 次补跑的 `rm -rf evidence/baseline` 覆盖，统计数值见 `compare-win.json`/`compare-full.json` 与 §6.2/§6.5。

## 10. 结论

1. **audio 主线程尖峰已消除（本轮核心收益，达成）**：同内容帧对照下 audio_cmds 由 180.08 / 335.17 ms 降到 29.39 / 21.34 ms（−83.7% / −93.6%），slow frame 中 >100 ms 的 audio 帧由 2 个降为 0；独立重复轮同样 0 个（max 34.37 ms）。与 §2 根因（Switch 后端未实现 `load_stream`，`flush_audio` 回退为主线程 `read_all+load_encoded`）完全吻合 ⇒ **`platform/switch/host/src/audio.rs` 的流式实现建议保留并进入真机复测**。
2. **vfs p50 降 30% 的验收项未达成**：本补丁没有改 vfs 读路径；diag 同窗口 30,538 → 33,232 us（+8.8%），同内容资源项互有涨跌（−14.4%…+29.2%），属无系统性变化的噪声；这与「vfs_read 仍是主线程同步读」的既有结论一致。⇒ 需要单独立项：把 vfs 读+解码搬进 async worker / 大图整文件交 worker，或场景切换前预取；须与 task-53（async 返工，P18 缺陷）协调，避免两组改动在 async 语义上冲突。
3. **写盘验收项未取得数据**：本轮路线在可观测窗口内未触发 `save_capture`，缩略图/写盘路径未改，不能宣称改善；慢帧中 save 阶段 38.16 → 7.66 ms 样本各只有 4 个，仅记方向。写盘项仍按 §7.2 遗留。
4. **纹理缓存双上限改动在本轮无可观测收益、保留为防御性改动**：可观测窗口内缓存峰值 123.26 MB < 旧 160 MiB 预算，且无 >16 MiB 单条纹理，故 160→256 MiB 与 16→48 MiB 未改变行为；4K CG（33,177,600 B > 旧单条上限）需在 CG 场景/真机上才能验证。风险：256 MiB 预算在真机内存预算下可能更早逼近 OOM，需真机确认（§7.5）。
5. **交付状态**：NSP `E:/galnx-build/p24/out/IROSEKA_FHD-010047420000a000.nsp`（9,979,497,176 B，sha256 `79aedc0382abe55260b40d27fb611995a77823ee13885a0e99f0c57c1653ffaa`，version 1.0.10-test2）在 Citron 上完整走完 162 步路线；增量补丁 `docs/builds/patches/rfvp-switch/rfvp-perf.patch`（6,057 B，159 行 diff / 4 文件）已入仓；test2 证据在 `E:/galnx-build/p24/evidence/test2/`。
6. **下一步顺序建议**：① 真机复测同一 NSP，确认 audio>100 ms 清零且无音频副作用（循环切头/语音打断/underrun）；② 补跑基线全量，补齐 407–510 s 段（含 Plus 菜单/存档界面）——2026-11-05 两次尝试均 abort（见 §7.7），需先独占 Citron；③ 单独立项 vfs 预取（P1）；④ 写盘快路径（P3）在 vfs 预取后做，避免同时改动 I/O 栈。


## 11. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-05 | 初稿：音频流式 + 纹理缓存预算/单条上限；构建与 NSP；Citron 基线/新版对比；未验证项 |
| 2026-11-05 | 回填 §6 Citron 实测（基线 407 s + test2 全量；同内容逐帧对照；diag 窗口限制；验收判定）与 §10 结论；补 §7.7–7.9、§9 统计产物与 run 目录 |
| 2026-11-05 | 补记 baseline 全量补跑两次 abort（Lead P25 轮撞车 23:33；Citron 被占用 23:36–23:41），证据重命名 `E:/galnx-build/p24/evidence/baseline-abort-20261105-2334/`；明确前 407 s 为正式对比窗口 |
