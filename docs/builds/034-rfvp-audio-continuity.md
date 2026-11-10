# 034 — rfvp 音频连续性（v1.1.3-test）

- 日期：2026-11-07
- 目标：修复真机 v1.1.2-test「卡顿时音频跟着一起卡」。用户原话：**「只要音频别跟着一起卡就能把这些读取卡顿给掩盖过去」**。
- 版本：1.1.3-test（nacp 版本号来自 `platform/switch/host/Cargo.toml:3`）
- 分支基线：p26-work HEAD cf0ea4f（含 P22 v1.1.0-test / P25 prefetch-only / P26 SD 读+4K 缓存）
- 构建 worktree：`/e/galnx-build/p27/rfvp-v113`（分支 p27-work，不污染 m5-rfvp 主树）
- 状态：Citron 级验证 PASS（probe4，三次模拟 1.2 s 长帧 underrun=0，async=on 不冻结）；真机验收待 Lead 统一执行。P24 音频流式补丁未并入本线。

## 1. 缺陷与根因

### 1.1 现象

真机 v1.1.2-test：vfs/解码长帧（300–1500 ms）期间 BGM 与语音同时断掉，卡顿结束后才恢复。用户反馈的观感是「音频跟着卡」。

### 1.2 根因：128 ms 硬件缓冲，只由主线程每帧补

P26 及以前的音频路径（P27 前的 `platform/switch/runtime/main.c`）：

- `audio_init()`：6 个 `AudioDriverWaveBuf` × 1024 帧 × 2ch ≈ **128 ms** 硬件缓冲；
- `audio_pump()` 每个主循环帧调用一次（原 main.c 帧循环），每次只补已经播完的 wavebuf；
- 主线程一旦被 `vfs_read` / 解码阻塞 300–1500 ms，这 128 ms 播完后没有任何 wavebuf 被补 → **audio underrun**，音频停住，直到主线程回去。
- 只加大 wavebuf 不能根治：wavebuf 的完成回收依赖主线程每帧 `audrvUpdate()`，主线程不运行就没人回收补料；必须有一个不被主线程阻塞的消费者线程。

## 2. 修复设计

### 2.1 3.07 s SPSC ring + 独立音频线程

`platform/switch/runtime/main.c`（+330/−4）：

- **Ring**：`AudioRingPages=144` 页 × `AudioBufferFrames=1024` 帧 = `AudioRingFrames=147456` 帧（48 kHz 下 **3.07 s**），`int16_t audio_ring[294912]`，`aligned(0x1000)`，≈576 KiB（L260）。
- **SPSC 无锁**：`audio_ring_write` / `audio_ring_read` 为 `_Atomic uint64_t`（L269-270）；主线程唯一生产者，音频线程唯一消费者，acquire/release 配对，不需要锁。
- **主线程只做渲染**：`audio_render_pages()`（L397）每帧渲染 8 页（≈170 ms）写入 ring。渲染仍走 `rfvp_switch_audio_render(app, pcm, 1024)`，**rfvp Session 不跨线程**——音频线程只消费已经渲染好的 PCM。
- **音频线程** `rfvp_audio_thread`（L436）：prio `0x2D`、栈 `0x10000`、cpu 依次尝试 `{2, 1, -2}`（L555）。4 ms 循环：
  1. 每 ~20 ms **无条件 `audrvUpdate()`** 回收已完成 wavebuf（见 §2.2）；
  2. 扫描 `Free/Done` 的 wavebuf，从 ring 取 1024 帧（`armDCacheFlush` → 填 `audio_buffers[i]` → `audrvVoiceAddWaveBuf`；返回 false 时 continue 下轮重试）；
  3. refilled>0 时 release store `audio_ring_read`、再 `audrvUpdate()`、更新 starve/underrun/最低水位统计。
- **启动预填**：`start_audio_thread()`（L547）先预填 24 页（≈512 ms）再 `threadCreate` + `threadStart`；成功 log `rfvp: audio thread cpu=%d ring=%d frames prio=0x2d`。线程创建失败时 log 并回退旧 `audio_pump_direct()`（L413）逐帧泵，功能不退化。
- **退出**：`audio_exit()`（L574）先 `g_audio_thread_stop=1` 等最多 200 ms，再 `audrvClose`/`audrenExit`。

### 2.2 关键坑：`audrvUpdate()` 必须周期性调用

首轮 Citron 运行 `audio_status.txt` 里 `consumed` 停在 6144（6 页）、ring 只进不出。根因：

- libnx 的 wavebuf 完成状态**只由 `audrvUpdate()` 回填**；`audrvVoiceStart()` 只是 `audrvVoiceSetPaused(false)`（`/d/devkitPro/libnx/include/switch/audio/driver.h:116-119`）。
- 旧 `audio_pump` 每帧都调 `audrvUpdate`，所以看不出问题；新线程最初只在「补了料」时调用 → 6 个 buffer 全部排队后再也没有 Done 事件 → ring 永不排空。

修复：音频线程每 ~20 ms 无条件 `audrvUpdate()` 一次，并在补料后立即再调一次；`audrvVoiceAddWaveBuf` 返回值检查。修复后 `consumed` 稳定以 **48,030 帧/秒** 增长（实测，见 §4）。

### 2.3 可观测性

- `sdmc:/switch/rfvp/audio_status.txt`（每 600 帧写一次，L295）：`driver/thread/alive/cpu/cap/ring/min_water/underrun/max_underrun_ms/starve_ms/produced/consumed/stalls/stall_ms`。
- `sdmc:/switch/rfvp/audio_stall.txt`（append，L326）：每次模拟长帧写 pre/post 两行：`phase stall=N ms= ring= underrun= min_water= t_us=`。pre 行会把最低水位重置为当前 fill，post 行反映本次卡顿的最低水位。
- `min_water` 单位是帧（48 kHz）。

## 3. 长帧测试开关（debug.txt）

`sdmc:/switch/rfvp/debug.txt` 支持追加两行（与已有的 `shot=NNN` 共存）：

- `stall=1200`：注入的长帧毫秒数，clamp 到 2000；
- `stall_at=1200`：第一次注入的帧号，clamp 300–60000，默认 1200。

主循环（L830-846）在 `frame == stall_at + k*600` 且 `k < 3` 时：先写 `audio_stall("pre")` → `svcSleepThread(ms)` → 写 `("post")`，并在 log 里打 begin/end ring。也就是**每 10 秒注入一次 1.2 s 主线程停帧，最多 3 次**。该开关与 `async.txt` 的 on/off 正交，只影响测试包。

真机验收时把 `stall` 行删掉即可恢复正常，无任何编译期差异。

## 4. Citron 验证（probe4，PASS）

### 4.1 环境

- Citron Nightly `0237a9b88`（Windows），直接加载 NRO；
- `async.txt` = `on`；
- `debug.txt` = `shot=300` + `stall=1200` + `stall_at=1200`；
- run dir：`E:/galnx-build/p27/run-nro-audio4/20261107-011542-rfvp`；
- 19/19 输入步 ok（标题 → Continue → CONTINUE → 正文两段），截图确认已进正文（真红「抱歉了啊」），全程无冻结。

### 4.2 结果：三次 1.2 s 长帧，underrun=0

`audio_status.txt` 终值：

| 字段 | 值 | 说明 |
| --- | --- | --- |
| driver / thread / alive | 1 / 1 / 1 | 音频驱动 + 音频线程存活 |
| cpu | 2 | 音频线程在核心 2 |
| cap / ring | 147456 / 147456 | 3.07 s ring 容量 / 当前 fill |
| min_water | **89088** | 全程最低水位 ≈1.86 s |
| underrun / max_underrun_ms / starve_ms | **0 / 0 / 0** | 无 underrun、无 starve |
| produced / consumed | 6151168 / **6003712** | 125 s 内消费 6,003,712 帧 ≈ **48,030 帧/秒**（48 kHz 实时） |
| stalls / stall_ms | 3 / 1200 | 三次注入的长帧 |

`audio_stall.txt`（三对 pre/post）：

| 阶段 | ring | underrun | min_water | t_us |
| --- | --- | --- | --- | --- |
| pre 0 | 147456 | 0 | 2048 | 184066409031 |
| post 1 | **90112** | **0** | 90112 | 184067610551 |
| pre 1 | 147456 | 0 | 90112 | 184077561365 |
| post 2 | **89088** | **0** | 89088 | 184078763143 |
| pre 2 | 147456 | 0 | 89088 | 184088793053 |
| post 3 | **89088** | **0** | 89088 | 184089994828 |

- 每次停帧 1.2 s 消耗 ≈57–58 k 帧（≈1.2 s 音频），ring 从 147456 降到 90 k 左右，仍余 **1.86 s**；
- 三次 `t_us` 间隔 1,201,520 / 1,201,778 / 1,201,775 us，证明注入确实是 1.2 s；
- **三次 underrun 均为 0，post min_water 均 > 0** → 验收核心条件满足。

### 4.3 交叉验证（perf_slow）

注入帧在主循环里体现为 frame 1201 / 1801 / 2401 的 1208.8 / 1211.2 / 1209.9 ms 慢帧，其 `vm` 阶段仅 0.12–0.15 ms（纯 `svcSleepThread`），说明这不是游戏逻辑卡顿而是被测的长帧；这些帧期间音频无 underrun。

### 4.4 async 回归

- `async_status.txt`：`enabled=1 create=0x0 start=0x0 hb=119000 stage=0 cpu=1 wdt=1 main=7487 stalled=0`；
- `frame_status.txt`：`frame=7530 status=0 async=1`；
- 无 `watchdog_status.txt`、无 `last_error`；
- → async=on 不冻结的回归通过（音频线程与 decode worker/watchdog 共存：main + decode@cpu1 + audio@cpu2 + watchdog）。

### 4.5 Citron 结论的适用范围

Citron 是宿主文件系统/调度，不能代表真机 SD 吞吐；但**音频 underrun 结论走的是 libnx audren/audrv 设备侧路径**（wavebuf 消费速率实测 48,030 帧/秒），与真机同一套代码路径，因此对真机有较强参考价值。真机仍需按 §6 实测确认。

## 5. 产物

| 产物 | 路径 | 大小 | sha256 |
| --- | --- | --- | --- |
| NSP（1.1.3-test） | `E:/galnx-build/p27/out/IROSEKA_FHD-010047420000a000-v1.1.3-test.nsp` | 9,979,503,320 B | `eaea4446ac9b373b60a3b9c6f083b1567b931f1a38ee6ab8dd49b1ae62ca13a8` |
| NRO | `/e/galnx-build/p27/rfvp-v113/target/rfvp-switch/switch/rfvp.nro` | 7,938,104 B | `e3557f53a08159a33e53212ee6b73c967acf43202fccc95c7c835445e55aea32` |
| ELF | `/e/galnx-build/p27/rfvp-v113/target/rfvp-switch-runtime/rfvp.elf` | 17,284,120 B | `437862fe56d51b7399ec4f97ce9ead3d4e8e480ccb65e15323d4fd31a0ce3c62` |
| 增量 patch（相对 P26 / cf0ea4f） | `docs/builds/patches/rfvp-switch/rfvp-audio-continuity.patch` | 22,016 B | `4f7a207f44492b9249015600bf998d9647ec56853d660e4536b82333cd478acc` |
| 全量 diff（相对 6c166f6，仓库外） | `/e/galnx-build/p27/rfvp-full-v113.diff` | 53,685 B | `c62e4ad4d1393258dd4435a9d01fdc6499bfae986b285978019a1d148a3879f6` |
| 证据目录 | `E:/galnx-build/p27/evidence/` | — | 见 SHA256SUMS.txt |

增量 patch 内容：3 文件 +330/−4（`platform/switch/runtime/main.c` 全部逻辑、`platform/switch/host/Cargo.toml` 版本、`Cargo.lock`）。无新文件。已在 cf0ea4f 的干净 worktree 上 `git apply --check` 通过；全量 diff 已在 6c166f6 干净 worktree 上 `git apply --check --binary` 通过。

## 6. 真机验收清单（Lead）

1. 安装 `IROSEKA_FHD-010047420000a000-v1.1.3-test.nsp`（ProgID 0x010047420000a000）。
2. 保留 `sdmc:/switch/rfvp/async.txt` = `on`。
3. 往 `sdmc:/switch/rfvp/debug.txt` 追加 `stall=1200` 与 `stall_at=1200`（想更狠可用 `stall=1800`，上限 2000）。
4. 进正文听 BGM/语音；每约 10 s 会有一次 1.2 s 画面停顿（第 1200/1800/2400 帧），**要求音频不中断、不爆音**。
5. 退出后取文件：
   - `audio_status.txt`：要求 `underrun=0`、`stalls=3`、`min_water` 明显 > 0（1.2 s 停帧理论值 ≈ 1.86 s）、`cpu` 为 1/2/3 之一、`alive=1`；
   - `audio_stall.txt`：三对 pre/post，post `underrun=0` 且 `min_water>0`；
   - `async_status.txt` / `frame_status.txt`：hb/frame 持续递增、无 `watchdog_status.txt`、无 `last_error`。
6. 删掉 `debug.txt` 里的 `stall`/`stall_at` 两行，正常游玩 10 分钟以上（含 Album 连切、UI 开合、场景切换），再次确认 `underrun=0`（真机 SD 读 0.3–1.5 s 正是 ring 要吸收的对象）。
7. 回归项：async=on 不冻结（P22）、Album 4K 差分预取（P26）、OP 段。

## 7. 风险与回退

- **音频线程创建失败**（进程线程数上限、内存不足）：自动回退旧 `audio_pump_direct()` 逐帧泵，功能等同 v1.1.2-test；`audio_status.txt` 显示 `thread=0`。
- **内存开销**：ring ≈576 KiB + 线程栈 64 KiB。进程当前线程：main / decode worker / watchdog / audio = 4（另 SDL2 可能有音频线程）；若线程上限紧张，先牺牲 watchdog（P22 的看门狗只写状态，不影响功能）。
- **优先级**：音频线程 prio 0x2D 高于 decode worker 0x30（低于主线程 0x2C）。音频线程只做 audrv IPC + memcpy，不持引擎锁；若真机观测到它抢占导致渲染变慢，可降到 0x31 再验。
- **CPU 竞争**：音频线程优先 cpu 2，与 decode worker（cpu 1）、主线程分开；若失败回退任意核，仍不应与主线程同核竞争（cpuid 列表最后才是 -2）。
- **回退**：撤销 `rfvp-audio-continuity.patch` 即回到 v1.1.2-test 行为（逐帧 direct 泵，版本号回落 1.1.2-test）；async/P26 其余改动不受影响。

## 8. Lead 独立 Citron 验收（NSP 形态，2026-11-07）

独立于实现者，用 **NSP（内嵌 romfs）** 形态复跑，覆盖「主线程被 1.2 s 长帧阻塞时音频是否继续」这一核心命题。

- run dir：`E:/galnx-build/p27/run-lead-audio/20261107-013414-IROSEKA_FHD-010047420000a000-v1.1.3-test`
- 注入：`debug.txt = shot=600 / stall=1200 / stall_at=1800`；`async.txt = on`（P25 prefetch + P26 缓存全部在）。
- 路线：标题 18 s → Continue (1386,638) → 读档列表 6 s → DATA_001 (420,300) → 正文 22 s → 再等 36 s（覆盖第 1800/2400/3000 帧三次 1.2 s 停顿）。14/14 步 ok，60 FPS。
- 状态（PASS）：`audio_status` = `driver=1 thread=1 alive=1 cpu=2 cap=147456 ring=147456 min_water=91136 underrun=0 max_underrun_ms=0 starve_ms=0 produced=5186560 consumed=5039104 stalls=3 stall_ms=1200`。
- `audio_stall.txt` 三对 pre/post：pre ring=147456 → post 90112/90112/91136，**underrun 全 0**，相邻 t_us 差 1.2015–1.2017 s，与注入停顿一致。
- async 回归：`enabled=1 hb=104000 stage=0 cpu=1 wdt=1 main=6508 stalled=0`；`frame=6510 status=0 async=1`；无 `watchdog_status.txt`、无 `last_error.txt`。
- 证据归档：`docs/milestones/evidence/P27a-audio-continuity/`（README.md、SHA256SUMS.txt、截图 5、status 4、run 3、logs/）。

结论：Citron 级音频连续性达标，可进入真机听感验收（用户手动 MTP 安装 `E:/galnx-build/p27/out/IROSEKA_FHD-010047420000a000-v1.1.3-test.nsp`，sha256 `eaea4446…`）。

