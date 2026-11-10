# 029 · rfvp 异步解码并发修复（v1.1.0-test）

> 里程碑：M5-m（rfvp Switch 后端）
> 日期：2026-11-05
> 状态：**真机验收未通过 → 已回退 v1.0.9（async off）**（Citron 证据见 §7；真机缺陷与根因见 [rfvp-async-device-defect.md](../experiments/rfvp-async-device-defect.md)；本分支未 push，补丁仅作实验记录）
> 基线：v1.0.9（m5-rfvp 工作区导出，commit `37503e88` = 上游 `9f07ade` + v1.0.9 补丁集）
> 修复 worktree：`/e/galnx-build/p22/rfvp-asyncfs`
> 根因报告：`E:/galnx-build/p21/rca-async-hang.md`；仓库版：`docs/experiments/rfvp-async-hang-rca.md`
> 触发：用户批准 async 并发修复实验（v1.0.9 因真机黑屏默认关闭 async，剩余卡顿仍在）

## 1. 现象与目标

- v1.0.9 默认关闭 async（`read_async_enabled()` 硬编码 `return 0`），真机可玩但大图/CG 切场景仍卡。
- 真机 async=on 证据（v1.0.8 会话）：`enabled=1 create=0x0 start=0x0 hb=3 stage=0`，进程整卡死、无 panic、无 crash report。
- 目标：**async=on 时真机不冻结**，同时保留「默认关闭、只有 `async.txt` 写 on 才启用」的 v1.0.9 行为。

## 2. 根因摘要（P21 RCA）

1. **H1（≈85%）同核优先级反转 + spin 锁跨阻塞 SD 读**：decode worker 与主线程同在 ideal core 0；worker prio 0x30 低于主线程 0x2C；`HostPackFile::read_at` 用 crate 的 spin::Mutex 保护 `FILE*`，持锁做 fseek/fread 读 13 MB 包数据。主线程同锁时在用户态自旋，而 Horizon 同核严格优先级使低优先级 worker 永远分不到 CPU → 双线程冻结。
2. **H2（次因）resource_cache 持锁 log/drop**：`static CACHES: spin::Mutex` 的 `put_*` 在锁内做 `perf::event`（格式化 + 嵌套取 ring_log 锁）并 drop 被淘汰的大 Arc。
3. **看门狗结构性失效（100%）**：引擎内 `watchdog_stalled`/`drain_inline` 只在主线程 tick 的 `apply_async_decodes` 里调用，主线程一卡就永不运行；且 `drain_inline` 会撞同一把 pack 锁。C 侧 `rfvp_switch_async_disable()` 全仓无调用者。
4. 另有 `stage=2`（读包中）从未上报，导致真机状态文件无法区分「卡在读」还是「卡在解码」。

## 3. 修复措施（v1.1.0-test）

### 3.0 修复点索引（文件:行，均相对修复 worktree `/e/galnx-build/p22/rfvp-asyncfs`）

| 根因 | 修复 | 位置 |
| --- | --- | --- |
| H1：pack 读 spin 锁跨阻塞 SD 读 | `mod pack_lock`（libnx `mutexLock`/`mutexUnlock` 睡眠互斥，guard Drop 解锁）+ `HostPackFile.file` 换类型 | `vfs.rs:39`（mod）、`:50`（PackMutex）、`:150-151`（file 字段）、`:175`（read_at） |
| H1：单次持锁窗口 13 MB | `READ_CHUNK_BYTES = 1 MiB` 分块 + `report_stage(2)` | `async_decode.rs:331`、`:333-345` |
| H1：同核优先级反转 | decode worker `cpuid=1`（失败回退 -2），prio 0x30 不变 | `main.c:358-370`（start_decode_worker）、`main.c:469-470` |
| 看门狗结构性失效 | 独立 watchdog 线程（prio 0x2F，cpu 1→-2）、`watchdog_status.txt`、10 s 兜底关 async | `main.c:382-417`（watchdog 线程）、`main.c:419-430`（start_watchdog）、`main.c:155-160`（write_watchdog_status） |
| H2：cache 锁内 log/drop | `Lru::put` 收集 evicted，锁外 `perf::event`+drop，report/clear 锁外 | `resource_cache.rs:83`（put）、`:145`/`:164`/`:181`（put_*）、`:201`（report）、`:225`（clear） |
| 开关/版本 | `read_async_enabled` 恢复读 `async.txt`（默认 0）；version 1.1.0-test | `main.c:105-120`、`platform/switch/host/Cargo.toml:3` |

### 3.1 pack 读改用睡眠互斥（H1 关键）

- `crates/rfvp/src/subsystem/resources/vfs.rs`：新增 `mod pack_lock`（cfg `all(target_os = "horizon", feature = "no_std")`）：
  - `PackMutex<T> { lock: UnsafeCell<u32>, value: UnsafeCell<T> }`，`const fn new` 支持静态初始化；
  - `lock()` 调 libnx `mutexLock`，guard 的 `Drop` 调 `mutexUnlock`（通过 `extern "C"` 声明，最终由 `-lnx` 解析）；
  - libnx Mutex = newlib `_LOCK_T`（uint32，0 即静态解锁态）；`svcArbitrateLock` 在内核 park 等待者并做优先级继承，**不再用户态自旋**；
  - 非 horizon 构建退回 `std::sync::Mutex`，行为不变。
- `HostPackFile::file` 由 `Mutex<F>`（no_std 下即 spin::Mutex）改为 `PackFileLock<F>`；`read_at` 不再返回 poison 错误。
- `crates/rfvp/src/subsystem/resources/async_decode.rs`：`read_bytes` 改为 **1 MiB 分块**读（`READ_CHUNK_BYTES`），并在读循环前 `report_stage(2)` —— 单次持锁窗口从「整个 13 MB」缩到「1 MiB」，stage 也能反映「正在读包」。

### 3.2 decode worker 换核（并发保险，不提高优先级）

- `platform/switch/runtime/main.c`：新增 `start_decode_worker()`，`threadCreate(..., prio 0x30, cpuid)` 依次尝试 `cpuid=1` → `-2`（进程默认核），成功则记录 `g_rfvp_async_cpu`；`async_status.txt` 增加 `cpu=%d` 字段。
- **为何不把 worker 提到 0x2B（高于主线程）**：worker 仍可能在主线程持有 QUEUE/CACHES 等 spin 锁时抢占主线程，同核自旋会反向死锁。真正的修法是 3.1 的睡眠互斥（等待即 park + 优先级继承），换核只是额外保险。worker 优先级保持 0x30。
- 附带：worker 仍在 CPU1 上跑，与主线程（CPU0）真正并行，大图解码不再占用主线程时间片。

### 3.3 C 侧独立看门狗线程（替代引擎内 tick 看门狗）

- 新增 `rfvp_watchdog_thread`（stack 0x10000，prio 0x2F，cpuid 1 → -2 兜底）：每 500 ms 采样主线程帧计数 `g_rfvp_main_frame`；
  - async 关闭时只继续采样；
  - 停滞 ≥3 s：写 `sdmc:/switch/rfvp/watchdog_status.txt`（`frame/stalled_ms/stage/hb/enabled/cpu`）并 `rfvp_switch_log` 打一条；
  - 停滞 ≥10 s：置 `g_rfvp_async_enabled = 0`（帧线程若恢复则下一帧走同步路径，最坏丢 async 收益而不是永久黑屏）；
  - watchdog 线程创建失败**只记录日志，不关闭 async**（不能因诊断线程失败而退化）。
- `async_status.txt` 增加 `wdt=%d main=%u stalled=%d` 字段（每 600 帧由主线程刷新，worker 每 1000 心跳也刷）。
- 引擎内旧 watchdog 保留（仅主线程 tick 可见时生效，Citron/真机 perf 关闭时本就不运行），但真机保障改由该独立线程负责。

### 3.4 resource_cache 锁外 log/drop（H2）

- `crates/rfvp/src/subsystem/resources/resource_cache.rs`：
  - `Lru::put` 返回被替换/淘汰的 value 列表，`put_texture/put_parts/put_bytes` 在锁内只做 LRU 插入并取回 evicted，`perf::event` 与 `drop(evicted)` 全部移到锁外；
  - `put_bytes` 的 `Arc::from(bytes)` 复制移到锁外，超 `MAX_ENTRY_BYTES` 直接返回；
  - `Lru::touch` 复用已有 key（不再 clone String/alloc）；
  - `report()` 锁内只取计数元组，格式化在锁外；`clear()` 锁内 `core::mem::replace` 换出，锁外 drop。

### 3.5 开关与版本

- `read_async_enabled()` 恢复读 `sdmc:/switch/rfvp/async.txt`：文件不存在/打不开返回 0；内容去空白/CRLF 后为 `on` 或 `1` 才启用。**默认无文件 = 关闭，与 v1.0.9 一致**。
- `platform/switch/host/Cargo.toml` version `1.0.9` → `1.1.0-test`（build_switch.sh 取该字段生成 nacp 版本；`Cargo.lock` 同步）。

## 4. 构建

| 项 | 值 |
| --- | --- |
| 构建根 | `/e/galnx-build/p22/rfvp-asyncfs`（git worktree --detach，基线 commit `37503e88`） |
| 命令 | `env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p22/build-instr.sh'`（同 m5 wrapper，仅 cd 到 worktree） |
| NRO | `target/rfvp-switch/switch/rfvp.nro` 7,929,912 B sha256 `69bdd09cd63540a3bcca4e775951b98a3c1bdd37c07079b90c11b56b1227646f` |
| ELF | `target/rfvp-switch-runtime/rfvp.elf` 17,264,504 B sha256 `ef311f9a78a4d2f5a3218f7b14ec25a8d38c65b587b6df4dfd14738f4ae23da0` |
| NSP | `E:/galnx-build/p22/out/IROSEKA_FHD-010047420000a000-v1.1.0-test.nsp` 9,979,498,200 B sha256 `753082b7da4e37f1eebe9d2558ffbfe1d907fc8885e01f02711a37e7709b0b0d` |
| NSP 构建 | `bash /e/galnx-build/p22/build-nsp-v110.sh`（`scripts/build_nsp_game.sh --version 1.1.0-test`，romfs hardlink，game dir `/e/galnx-build/m5-rfvp-run/game`） |

## 5. Citron 验证（模拟器，非真机）

> Citron 的线程调度不模拟 Horizon 同核严格优先级，**不能复现真机冻结**；以下只证明「修复版在 async=on 下长时间运行/连续剧情不冻结、指标健康」。真机是最终裁判。

### 5.1 冒烟 A：NSP 内嵌 romfs，连续剧情约 5 分钟（主证据）

- 命令：`citron_run.sh --game <NSP> --no-stage --detach --timeout 420 --settle 8 --allow-existing --expect-title IROSEKA`，`async.txt` = `on`，`debug.txt` = `shot=900`。
- run dir：`E:/galnx-build/p22/run-nsp-clean/20261105-161131-IROSEKA_FHD-010047420000a000-v1.1.0-test`（16:11:31 → 16:18:14）。
- 输入：Continue → CONTINUE 列表项 → 30 次 `key:C`（每次间隔 4 s），中途 3 次截图校验正文；**未开任何 UI**。
- 结果：`ok=73 failed=0 diff_ratio=0.806`；`debug_report` 头 `frame 19200: 60.0 fps over the last 60 frames, slowest 19.6 ms`；游戏 async=on 共 19200 帧 ≈ 320 s。
- 截图正文连续推进：`step-08-c2-story`「悠马『家庭教师？』」→ `step-50-c4-min2`「湊『就是这样。我真希望不要再这样下去了』」→ `step-73-c7-final`「湊『不要』」。
- final `async_status.txt`：`enabled=1 create=0x0 start=0x0 hb=295384 stage=0 cpu=1 wdt=1 main=19199 stalled=0`；无 `watchdog_status.txt`、无 `last_error.txt`。

### 5.2 冒烟 B：NSP 内嵌 romfs，10.6 分钟长跑（含 UI 开关）

- run dir：`E:/galnx-build/p22/run-nsp-long/20261105-155500-IROSEKA_FHD-010047420000a000-v1.1.0-test`（15:52:54 → 16:08）。
- 162 步（64 次推进 + 3 次 UI 开合 + 若干截图）：`ok=162 failed=0`，`frame_status frame=39600`（≈10.6 min @60fps）。
- final `async_status`：`hb=598914 stage=0 cpu=1 wdt=1 main=39599 stalled=0`；无 watchdog 告警。
- **注意**：该轮输入脚本里 `key:M`（Plus）打开了 DATA EDIT 存档界面并弹出「确定要覆盖存档?」，从约 15:59 起画面停在 UI（截图 `step-27-ui-plus1`、`step-80-t4-min2`、`step-116-t5-min3`、`step-162-t9-final`），只有 `step-08-t2-story` 是正文；存档目录 mtime 未变化（未写盘）。故该轮只用于证明「async=on 长时间不冻结」，剧情连续性以 5.1 为准。

### 5.3 async 解码次数与耗时（供真机前后对比）

冒烟 A（5 分钟剧情，ring 中保留的片段）：

| 类型 | 资源 | 字节 | 结果 | 耗时 |
| --- | --- | --- | --- | --- |
| graph | `graph_bs/CHR_郰_斶_壞惂暈L` | 1,166,612 | ok | 56.97 ms |
| parts | `graph_bs/CHR_郰_斶_壞惂暈L_昞忣` | 1,813,474 | fail（Multi32Bit）→ 重试 ok | 13.73 / 51.58 ms |
| graph | `graph_bs/CHR_郰_婎_壞惂暈L` | 1,369,631 | ok | 55.90 ms |
| parts | `graph_bs/CHR_郰_婎_壞惂暈L_昞忣` | 3,447,414 | fail（Multi32Bit） | 16.08 ms |

冒烟 B（10.6 分钟，ring 中保留的片段）：6 次成功 + 1 次失败（`Multi32Bit`，29.5 ms）；成功耗时 us：title_bg1_A 93,460、BG043_000 117,480、BG043_000b 77,129、parts 95,256、graph 54,334、parts 重试 97,644 —— 均值约 69.5 ms，最大 117.5 ms。这些原本都是主线程 `graph_decode`/`parts_decode` 的阻塞时间（真机 v1.0.9 perf_slow：graph_decode 0.1–0.7 s）。

### 5.4 perf_slow 观察（冒烟 A）

- 启动期：frame 1 2,048.4 ms（首次加载）、frame 4 399.1 ms。
- 稳态：大多 25–36 ms；慢帧大项为 `audio_cmds`（frame 250 204.7 ms、frame 2873 357.4 ms）、`vfs_read`（frame 2873 265.6 ms）、`parts_compose`（frame 4780 79.0 ms、8989 101.9 ms、9874 90.3 ms）。
- **没有 graph_decode 大项**：async 解码已移出主线程；剩余慢帧属音频命令、同步 vfs_read、parts 合成，不在本任务范围（音频/写盘另案）。
- Citron 上 `apply_async_decodes` 每帧 tick 正常（冒烟 A 有 11 条 `[async] tick`、3 次 submit、5 条 decoded），无 watchdog 行。

### 5.5 证据与校验

- 冒烟 A：`E:/galnx-build/p22/evidence-clean/`（`async_status.txt`、`debug_report.txt` 92,932 B、`perf_slow.log` 8,872 B、7 张截图、`result.json`、`harness.err`、`input-steps.tsv`、`SHA256SUMS.txt`）
- 冒烟 B：`E:/galnx-build/p22/evidence/`（含 timeline-1..4、frame-1..4、最终 status、`SHA256SUMS.txt`）
- 两轮汇总（标注 A=干净剧情、B=长跑）：`E:/galnx-build/p22/evidence/SHA256SUMS-ALL.txt` 与 `E:/galnx-build/p22/evidence/README.txt`
- 关键 sha256：`async_status`(A) `60245d876a18e06dff8e71f88f4eab909dfbf14d6856af058d628553df102769`；`debug_report`(A) `a83ace8a5d3c440aa2cc0697b35798b06e88c5a08c12bc53167d3e1d7dc180cb`；`perf_slow`(A) `7121ec357bb087b08e9e0a0f337b16617ba8707a0494ad17ec90440049aa15b7`；`async_status`(B) `71771720cb55a540e60b03933855e6aa6c58a9d5e15933e411acb53d0090abf5`

## 6. 已知问题 / 未覆盖

1. **Multi32Bit parts 解码失败**：async parts 解码对 Multi32Bit 纹理类型返回失败（`id=65535`），主线程回退同步 `vfs_load_file` 后正常。这是既有解码器能力问题，不是冻结，也不在本任务范围（后续可让 async 对 Multi32Bit 直接不提交）。
2. **Citron 不能复现真机冻结**：本报告的 Citron 结果只是「不冻结」的必要证据；机制是否在真机生效必须靠真机 `async_status` 的 `cpu=1 wdt=1 hb 递增 stalled=0` 与无 `watchdog_status.txt` 判定。
3. **线程数**：NSP 进程内主线程 + SDL 音频线程 + decode worker + watchdog = 4 线程；若真机线程上限导致 watchdog 创建失败，日志会记录但 async 仍开启（设计如此）。
4. **watchdog 极慢帧误判**：停滞阈值 3 s；真机大片同步读若偶发 >3 s，会写一次 `watchdog_status.txt`（不致命，10 s 才关 async）。可用于定位而不是故障。
5. **性能回归面**：pack 读改 libnx 互斥后，正常同步路径每次多一次内核 lock/unlock 成本（已用 1 MiB 分块摊薄），Citron 未见明显回退。

## 7. 真机验证清单（Lead 执行）

1. 安装 `IROSEKA_FHD-010047420000a000-v1.1.0-test.nsp`；默认（无 `async.txt`）启动应等同 v1.0.9：可玩、`async_status` 不生成（enabled=0）。
2. 在 `sdmc:/switch/rfvp/` 放 `async.txt` 内容 `on`，清掉旧的 `async_status.txt`/`frame_status.txt`/`watchdog_status.txt`/`last_error.txt`/`debug_report.txt`/`perf_slow.log`，再启动并进入正文游玩 3–5 分钟（建议 ≥5 分钟）、切换场景/开 UI 数次。
3. 验收：
   - 不冻结；`frame_status.txt` 帧号持续增长（需 `debug.txt`）；
   - `async_status.txt`：`enabled=1 create=0x0 start=0x0`、`hb` 递增、`stage` 在 0/1/2/3/4 间变化并回 0、`cpu=1`、`wdt=1`、`main` 递增、`stalled=0`；
   - 不出现 `watchdog_status.txt`；不出现 `last_error.txt`；
   - `perf_slow.log` 中 `graph_decode` 大项显著减少（对比 v1.0.9 的 0.1–0.7 s）。
4. 若冻结仍出现：保留 `async_status.txt`/`watchdog_status.txt`/`last_error.txt`/`perf_slow.log`/`debug_report.txt`，先回退（见 §9）再取证。

## 8. 产物与校验

| 产物 | 路径 | 大小 | sha256 |
| --- | --- | --- | --- |
| 增量 patch（vs v1.0.9） | `docs/builds/patches/rfvp-switch/rfvp-async-fix.patch` | 24,772 B | `203d936dadd5d540ee33189e360a94cae20bb76b565079137bb770ea303d9788` |
| 全量 diff（vs 上游 9f07ade，**仓库外暂存**） | `/e/galnx-build/p22/rfvp-full-v110.diff` | 212,537 B | `3d25d9b856e6a6579a712c774d902e1658e91f3b31d6beae4e6e2d7ede1f944e` |
| 测试 NSP | `E:/galnx-build/p22/out/IROSEKA_FHD-010047420000a000-v1.1.0-test.nsp` | 9,979,498,200 B | `753082b7da4e37f1eebe9d2558ffbfe1d907fc8885e01f02711a37e7709b0b0d` |
| NRO | `/e/galnx-build/p22/rfvp-asyncfs/target/rfvp-switch/switch/rfvp.nro` | 7,929,912 B | `69bdd09cd63540a3bcca4e775951b98a3c1bdd37c07079b90c11b56b1227646f` |

- 增量 patch 改动：6 files changed, +321/−69（`Cargo.lock`、`async_decode.rs`、`resource_cache.rs`、`vfs.rs`、`host/Cargo.toml`、`main.c`）；已在干净 worktree 用 `git apply --check` 验证可应用到 `37503e88`。
- 全量 diff：33 files changed, +4,064/−248；按要求**暂存于仓库外** `/e/galnx-build/p22/rfvp-full-v110.diff`，未覆盖仓库现有 `docs/builds/patches/rfvp-switch/rfvp-full.diff`（v1.0.9 全量）；是否合并进仓库由 Lead 决定。
- 本次产物均未提交、未推送；`rfvp-async-fix.patch` 与本文档为仓库内新增未跟踪文件，由 Lead 合并时统一处理。

## 9. 回退

- 直接回退：重装 v1.0.9 NSP 即可（新 NSP 未写存档格式、未升级 title version 之外的持久化数据；v1.1.0-test 与 v1.0.9 存档兼容）。
- 仅关 async：删除/改名 `sdmc:/switch/rfvp/async.txt`（或写 `off`），启动即回到同步路径，无需换 NSP。
- 代码回退：`git apply -R docs/builds/patches/rfvp-switch/rfvp-async-fix.patch`（或 revert 对应 commit）。

## 10. 参考

- `E:/galnx-build/p21/rca-async-hang.md`（H1/H2/看门狗结构性失效取证）
- `docs/experiments/rfvp-async-hang-rca.md`（仓库版）
- `docs/builds/024-rfvp-async-decode.md`、`025-rfvp-async-toggle.md`、`026-rfvp-async-watchdog.md`、`027-rfvp-async-off.md`（async 演进史）
- libnx `switch/kernel/mutex.h`（Mutex = `_LOCK_T`，静态 0 初始化）、`switch/kernel/thread.h`（prio/cpuid 语义）
- `docs/environment/citron-harness.md`（Citron 运行姿势）

## 11. 真机验证结果（2026-11-05，未通过）

- 安装 v1.1.0-test（`async.txt=on`）后，用户在真机观察到：部分 CG 不显示（只剩对话框/UI）、UI 开合残留旧像素、序幕→第一章 OP 被跳过。
- 设备取证：`enabled=1 hb=1020000 stage=0 cpu=1 wdt=1 stalled=0`（**并发/看门狗机制本身工作正常，未冻结**）；但 `graph_load: invalid id : Nil` 44 条、`prim_set_uv: invalid v : Nil` 461 条，全程仅 3 次异步解码，8.3 MB 的 `graph_vis1/KANA_e01b` 解码 589,851 us。
- 根因：`graph.rs:1046-1058` 对大图 `submit_graph` 后**立即返回 Variant::Nil** 的延迟绘制语义，与 rfvp「按 id 逐帧重画」模型不兼容 → 纹理未就绪/被重新分配时该层不画，且不清屏导致残留。属 P18 设计缺陷（Citron 解码快未暴露），与本次并发修复无关。
- 处置：回退 v1.0.9（同步解码，确定性正确）；v1.1.0-test 不进主线；后续修复改为 **prefetch-only async**（graph_load 永不返回 Nil）+ 延迟层补偿 + OP/movie 排查，见 P25。
- 结论：**async 并发修复（pack 睡眠锁/换核/看门狗）本身可用，但 async 的延迟绘制必须重做**；真机推送继续冻结。
