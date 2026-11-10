# 真机 v1.0.9 卡顿画像（perf_slow 日志分析）

- 日期：2026-11-05
- 对象：IROSEKA FHD v1.0.9 自包含 NSP（`010047420000A000`）
- 数据来源：Switch 真机 `sdmc:/switch/rfvp/perf_slow.log`（MTP 取回，`E:/galnx-build/p21/device-logs/`）
- 相关：`docs/builds/027-rfvp-async-off.md`（v1.0.9 交付）、`docs/experiments/rfvp-async-hang-rca.md`（async 冻结根因）

## 1. 取证方法

1. Switch 用 DBI MTP 连接后，PowerShell COM（Shell.Application）逐级下钻 `This PC > Switch > 1: SD Card > switch > rfvp`，按 `System.Size` 取大小后 `CopyHere` 到本机。脚本：`E:/galnx-build/p21/fetch-device-logs.ps1`。
2. 取回文件：
   - `perf_slow.log` 313,346 B
   - `debug_report.txt` 109,823 B
   - `frame_status.txt`：`frame=3150 status=0 async=0`
   - `async_status.txt`：`enabled=0 create=0x0 start=0x0 hb=0 stage=0`（v1.0.9 默认关闭生效）
   - 无 `last_error.txt`（无崩溃）
3. `perf_slow.log` 为多次运行累积：共 **1079 条慢帧记录 / 13 次运行**，最大 frame 75,930。

## 2. 分类统计（单位 ms，仅统计该 stage 在场的慢帧）

| 类别 | 帧数 | p50 | p90 | max | 说明 |
|---|---:|---:|---:|---:|---|
| vfs_read | 223 | 192.59 | 1235.88 | 3382.21 | 同步读 pack（mean 505.2） |
| graph_decode | 166 | 159.37 | 407.68 | 704.20 | 大图解码（mean 204.0） |
| audio_cmds | 149 | 4.52 | 543.67 | 1314.16 | >100ms 共 34 帧（415–1314ms） |
| parts_decode | 37 | 147.68 | — | 177.17 | 立绘/表情 sheet（mean 135.7） |
| save（真实写盘，含 finalize） | 137 | 89.98 | 95.34 | 115.85 | 其中 finalize p50 59.58 / thumb p50 24.73 |
| save（仅 prepare，不写盘） | 260 | 6.76 | — | — | thumb p50 1.69、snapshot p50 4.92 |
| save（全部含上面两类） | 397 | 7.14 | 91.60 | 979.05 | 离群 f42443 979.05、f7399 511.89 |

启动一次性：frame1 1.35–4.45 s（vfs_read 544–3382、syscalls 701–2269）；frame4 约 1.0–1.4 s（vfs_read 474–486 + graph_decode 368–704）。

大过渡帧（换场景 / 换 CG / 开菜单）：

| frame | total | vfs_read | graph_decode | audio_cmds | parts_decode |
|---:|---:|---:|---:|---:|---:|
| f777 | 4473.7 | 2116.72 | 520.90 | 1314.16 | 158.81 |
| f825 | 3962.8 | 1795.3 | 527.45 | 1174.62 | 58.31 |
| f2777 | 2391.1 | 1452.95 | 630.37 | — | 162.08 |
| f1506 | 1682.3 | 1020.34 | 481.49 | — | — |
| f1071 | 1197.8 | 647.70 | 424.03 | — | — |
| f2603 | 1192.7 | — | — | — | — |
| f1683 | 982.2 | 643.26 | 149.21 | — | 162.65 |

另有稳定的 **~950–1000 ms 模式**（f995/f2368/f2878/f3462/f4039/f4449/f5099/f6085 等）：vfs_read 620–650 + graph_decode 144–162 + parts_decode 158–162 → 换立绘/表情类。

纯音频尖峰：f136 504.0、f1908 513.8；每次运行早期 f212 约 530–546（疑似 BGM 首次加载）。

## 3. 结论

1. **逐句卡顿已基本消除**：P16 惰性存档后，每句触发的 prepare-only 存档仅 ~7 ms（save 6.76 + thumb 1.69 + snapshot 4.92），低于 16.7 ms 帧预算。用户"与先前一致"的体感主要来自下面三类事件。
2. **最大头是场景/CG/立绘过渡**：0.5–4.5 s，构成 = vfs_read（0.6–2.1 s，同步读盘）+ graph_decode（0.1–0.7 s）+ parts_decode（0.15 s）+ audio_cmds（偶发 1.2–1.3 s）。P18 async decode 只覆盖 graph_decode 部分，**vfs_read 仍是主线程同步**。
3. **音频相关 >100 ms 尖峰 34 次**（0.4–1.3 s），需要区分 BGM/语音/pack 加载路径。
4. **真实写盘帧 ~90 ms**（137 次）：thumb 24.7（疑似 GPU 快路径未生效，回退到全帧 readback+CPU 缩放）+ finalize 编码 59.6 + snapshot 5；另有 0.5–1.0 s 离群需单独查。
5. 无崩溃、无 last_error；`[ERROR] Invalid duration` 大量来自 `motion.rs` 6 处 `log::error!`（功能瑕疵，与卡顿无直接关系，后续单独清理）。

## 4. 修复优先级与方案

| 优先级 | 问题 | 方案 | 预期 |
|---|---|---|---|
| P1 | 过渡帧 vfs_read 0.6–2.1 s | 把 vfs 读取也搬进异步 worker（async job = read + decode，主线程不阻塞）；大图（≥1 MiB）直接整文件交给 worker | 过渡帧总时长降到 graph_decode 水平以下；配合 async 解码可 <100–200 ms |
| P1 | 过渡帧 graph_decode 0.1–0.7 s | task-49 async 并发修复（E1/E2/pack 睡眠锁/独立看门狗） | 已排期 |
| P2 | audio_cmds 0.4–1.3 s | 插桩拆分 audio_cmds 内部阶段（bgm/voice/se），确认是 pack 读还是解码；预读下一 BGM / 语音异步 | 消除 0.5–1.3 s 音频尖峰 |
| P3 | 真实写盘 ~90 ms | ①查 thumb GPU 快路径为何回退（`frame_targets_ready`/TARGET 纹理创建/RenderReadPixels）②encode（59.6 ms）移到 worker 异步提交 ③thumb 复用上一帧缓存 | 写盘帧 <20 ms |
| P3 | save 离群 0.5–1.0 s | 查 f42443/f7399 上下文（是否同时叠加 vfs/audio） | 消除离群 |

**实施状态（2026-11-05，P24，详见 `docs/builds/030-rfvp-perf.md`）**：

- **P2 audio 已实施**：`platform/switch/host/src/audio.rs` 实现 `RfvpAudio::load_stream`（流式，转发 `SoftAudioMixer`/`read_stream` 回调），不再命中 `Unsupported` 回退。Citron 同内容帧对照 audio_cmds 180.08 → 29.39 ms、335.17 → 21.34 ms（−83.7% / −93.6%），slow frame 中 >100 ms 音频帧 2 → 0；独立重复轮 0 帧（max 34.37 ms）。真机数值待复测。
- **P1 vfs_read 未实施**：P24 补丁未改 vfs 读路径；Citron diag 同窗口 vfs p50 30,538 → 33,232 us（+8.8%，同内容项在 −14.4%…+29.2% 间涨跌），无系统性变化。需单独立项（读+解码进 async worker / 大图整文件交 worker / 场景切换前预取），并与 task-53 的 async 语义返工协调。
- **P1 graph_decode**：由 task-49/task-53 处理，P24 未改。
- **P3 真实写盘与 save 离群未实施**：P24 未改 `save_manager.rs`/thumbnail readback；Citron 可观测窗口内 `save_capture` 无样本，写盘项无数据。
- **纹理缓存（本表外的防御性改动）**：`resource_cache.rs` 的 `TEXTURE_BUDGET` 160→256 MiB、`MAX_ENTRY_BYTES` 16→48 MiB；本轮路线前 128 s 缓存峰值 123.26 MB、最大单条 12.96 MB，未触碰旧上限 ⇒ 无可观测收益；4K CG（33.18 MB > 旧单条上限）需 CG 场景/真机验证。

## 5. 已知证据路径

- 设备原始日志：`E:/galnx-build/p21/device-logs/{perf_slow.log,debug_report.txt,frame_status.txt,async_status.txt}`
- 取回脚本：`E:/galnx-build/p21/fetch-device-logs.ps1`
- 相关源码（E:/galnx-build/m5-rfvp）：
  - `platform/switch/host/src/vfs.rs`（HostPackFile::read_at，spin::Mutex 内做 fseek/fread）
  - `platform/switch/runtime/sdl_video.c`（`galnx_sdl_read_pixels_scaled` 缩略图快/慢路径）
  - `crates/rfvp/src/subsystem/saveload/save_manager.rs`（finalize/materialize/try_commit）
  - `crates/rfvp/src/subsystem/saveload/save_state.rs:94`（append_state_chunk_v1）
  - `crates/rfvp/src/subsystem/perf.rs`（STAGES 索引）
- 帧阶段索引：VFS_READ=23、GRAPH_DECODE=24、PARTS_DECODE=25、PARTS_COMPOSE=26、CPU_RESTORE=27、SAVE_SNAPSHOT=33、SAVE_FINALIZE=34。

## 6. 限制

- perf_slow.log 为多次运行累积，未按运行分段；p50/p90 为跨运行混合值，量级判断可用，单次精确对比需下次运行前清日志。
- 设备日志与 Citron 环境有差异（真机 SD I/O 与 GPU 路径不同），以真机数据为准。
- 音频为客观阶段耗时，未做听感验证。

## 7. audio_cmds 尖峰根因（源码定位，2026-11-05）

> 给后续 task-51/P24 的实现者。结论来自 `E:/galnx-build/m5-rfvp` 源码，未在真机逐条验证；但与本文件第 2 节 34 个 >100 ms 帧（415–1314 ms）吻合。

- `audio_cmds`（STAGES 索引 18）测的是 `no_std_core.rs:729-731` 的 `self.flush_audio(host)`，即把本帧累积的音频命令交给 host 后端。
- `flush_audio`（`crates/rfvp/src/no_std_core.rs:1099-1158`）对 `AudioCommand::LoadStream` 先调 `host.audio().load_stream(id, kind, stream)`；**若返回 `RfvpError::Unsupported`，就在主线程上 `stream.read_all()` 把整首 BGM 从 SD 读进内存，再 `load_encoded` 解码**。Switch 后端 `platform/switch/host/src/audio.rs` 只实现了 `load_encoded`（:85）与 `create_stream`（:94），**没有实现 `load_stream`**，于是命中 trait 默认的 `Err(Unsupported)`（`crates/rfvp/src/host_api/audio.rs:151-158`）→ 必然走全量读回退。
- 何时走流式：`crates/rfvp/src/rfvp_audio/commands.rs:69-76` `STREAM_FROM_BYTES = 1 MiB`；`load()` 对长度 ≥1 MiB 的命名音源（BGM 为主）发 `LoadStream`（:112-123），否则 `LoadEncoded`。这解释了 >100 ms 的尖峰集中在换 BGM/播放长语音的帧。
- 可行修法（按成本排序）：
  1. **Switch 实现 `RfvpAudio::load_stream`**（转发 `SoftAudioMixer::load_stream`，其内部走 `SoftAudioVorbis::open_stream`；`crates/rfvp/src/host_api/audio.rs:327-333`）。问题：`platform/switch/host/src/audio.rs` 的 `HorizonVorbisBackend` 目前只包装 `rfvp_ogg_open_memory`（整块内存），需给 C shim 增加“按需读取”的解码入口（stb_vorbis 自定义读回调 / 预读窗口）。
  2. **把回退读+解码移出主线程**：把 `LoadStream` 的 `read_all + load_encoded` 打包成 async job（与 async_decode worker 同栈或独立线程），完成后在主线程 `load_encoded` 前应用；BGM 有淡入，延迟 1–2 帧可接受。比 1 便宜、且顺带覆盖语音。
  3. 短期兜底：预读即将播放的 BGM（脚本可观测到播放请求前加载），把整块读到内存缓存，避免播放帧同步读 SD。
- 注意：`STREAM_FROM_BYTES` 也影响内存峰值；方案 2 的队列要限制同时 pending 数（如 ≤2），避免瞬时内存翻倍。

## 8. P24 修复与 Citron 复测（2026-11-05）

> 本节回填 P24/task-51 的 Citron 复测结果：§1–§3 是 v1.0.9 真机画像，本节是对应修复后的模拟器验证。完整构建/打包/验收证据见 `docs/builds/030-rfvp-perf.md`。

### 8.1 被测对象与条件

- 新版 NSP：`E:/galnx-build/p24/out/IROSEKA_FHD-010047420000a000.nsp`（9,979,497,176 B，sha256 `79aedc0382abe55260b40d27fb611995a77823ee13885a0e99f0c57c1653ffaa`，version 1.0.10-test2，含 audio 流式 + 纹理缓存两项改动，补丁 159 行/4 文件）。
- 基线 NSP：`E:/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp`（9,979,495,640 B，sha256 `726bb2d1…3c0d9`，version 1.0.9）。
- 同一 162 步路线（`E:/galnx-build/p22/steps-long.json`，sha256 `617310b8…`），同一 Citron（main-0237a9b88），两轮均强制 NSP 内嵌 romfs。基线轮在 t=407 s 被 Citron 停止（NVDRV syncpoint 断言 → ForceStop，无 guest 崩溃），仅前 407 s 有效；新版轮 162/162 步完成。2026-11-05 23:33/23:36 两次补跑基线全量均 abort（与 Lead 验收轮撞车；之后 Citron 被他人占用），故基线窗口仍为前 407 s（详见 `docs/builds/030-rfvp-perf.md` §7.7）。

### 8.2 同内容逐帧对照（perf_slow.log）

| 帧（基线/新版） | 基线 total / audio_cmds / vfs_read (ms) | 新版 total / audio_cmds / vfs_read (ms) | 判读 |
|---|---|---|---|
| 4 / 4 | 518.1 / 0.04 / 169.81 | 520.0 / 0.04 / 170.22 | 测量可复现，对照锚点（差异 <1%） |
| 245 / 245 | 183.4 / **180.08** / — | 32.0 / **29.39** / — | audio_cmds −83.7% |
| 2439 / 2501 | 1301.5 / **335.17** / 512.32 | 923.1 / **21.34** / 470.67 | audio_cmds −93.6%，vfs_read −8.1% |

### 8.3 slow frame 阶段统计（对比 §1 的设备画像）

| 指标 | v1.0.9 设备（§1，真机） | v1.0.9 Citron（基线，407 s） | 1.0.10-test2 Citron（全量） | 判定 |
|---|---|---|---|---|
| audio_cmds >100 ms 帧数 / 峰值 | 34 帧 / 1314.16 ms | 2 帧 / 335.17 ms | **0 帧 / 29.39 ms** | Citron 达成，真机待复测 |
| vfs_read p50 / max | 192.59 / 3382.21 ms | 169.81 / 887.28 ms | 320.44 / 1003.75 ms | 未改善（未改 vfs 路径） |
| graph_decode p50 / max | 159.37 / 704.20 ms | 97.53 / 215.01 ms | 93.83 / 215.84 ms | 持平（归 task-49/task-53） |
| save（写盘帧）p50 / max | 89.98 / 115.85 ms | 38.16 / 80.77 ms | 7.66 / 57.49 ms | 样本少，未验证 |

注：设备与 Citron 的绝对值不可直接比较（SD I/O、GPU readback、帧率上限不同），只用于判断修复方向是否生效；slow frame 统计受运行间波动影响（本路线独立两轮 12 vs 39 帧），故不以 slow frame 计数总量对比。

### 8.4 结论（对 §4 优先级表的更新）

1. **P2（audio_cmds 尖峰）已在 Citron 上消除**，机制与 §7 的源码定位完全一致（`load_stream` 实现取代主线程 `read_all+load_encoded` 回退）；建议保留改动并做真机复测 + 音频副作用检查（BGM 循环切头、语音打断、pack `Mutex` 竞争下的 underrun）。
2. **P1（vfs_read）仍未解决**，是剩余最大头（Citron 0.47–1.0 s，设备 0.6–2.1 s）；需要单独立项，把读+解码搬进 async worker 或场景切换前预取。
3. **P3（写盘/缩略图）未实施、也未取得 Citron 数据**（可观测窗口无 `save_capture`）；需设计能触发存档的路线或直接在真机复测。
4. **纹理缓存防御性改动（160→256 MiB、单条 16→48 MiB）本轮无可观测收益**（缓存峰值 123.26 MB、最大单条 12.96 MB），保留待 4K CG/真机验证；需关注真机内存预算。

### 8.5 证据路径

- 文档：`docs/builds/030-rfvp-perf.md`（§6 验证、§10 结论）
- 统计：`E:/galnx-build/p24/compare-win.json`、`E:/galnx-build/p24/compare-full.json`、`E:/galnx-build/p24/perf-test2.json`（22:27 独立重复轮留档）
- 原始日志：`E:/galnx-build/p24/evidence/test2/{perf_slow.log,debug_report.txt,result.json}`；基线原始日志已被补跑 abort 覆盖丢失，残片在 `E:/galnx-build/p24/evidence/baseline-abort-20261105-2334/`，基线统计见 `compare-win.json`/`compare-full.json`
- run 目录：`E:/galnx-build/p24/run-test2/20261105-230948-IROSEKA_FHD-010047420000a000/`（12 张 step-*.png）、`E:/galnx-build/p24/run-baseline/20261105-225832-IROSEKA_FHD-010047420000a000/`

