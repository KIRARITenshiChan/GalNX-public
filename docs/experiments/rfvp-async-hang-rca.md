# rfvp 异步解码冻结根因分析（RCA，v1.0.8 真机会话）

> 归档：2026-11-05，由 teammate `async-rca` 产出，原文 `/e/galnx-build/p21/rca-async-hang.md`（32,759 B）。
> 本文只做静态源码分析，未改源码、未构建、未跑真机；结论用于决定 v1.0.9 的 async 策略。

---

# GalNX RFVP v1.0.8 async=on 首帧双线程冻结 — 根因分析（RCA）

- 报告人：async-rca（GalNX team），2026-11-05
- 代码基线：E:/galnx-build/m5-rfvp（HEAD 632fba1 "P19 baseline" + P20/v1.0.8 未提交工作区改动；v1.0.9 的临时禁用 read_async_enabled()→0 已在工作区）
- 对照补丁：E:/galnx-build/p18/rfvp-async-decode.patch（v1.0.6 引入 async worker）、E:/galnx-build/p20/rfvp-async-watchdog.patch（v1.0.8 加 stage / watchdog / 1 MiB 栈）
- 性质：**只读**代码分析 + 既有日志与模拟器取证复核；未修改源码、未构建、未上机。

---

## 0. 结论（TL;DR）

**最可能的根因（H1，高置信 ≈85%）**：v1.0.8 的 decode worker 与主线程在**同一条 Horizon 逻辑核（ideal core 0）**上；worker 在 read_bytes 里**持着 HostPackFile 的 spin::Mutex 做一次 13 MB 级的阻塞 SD 读**，读到一半在 libnx fs IPC 上睡眠；此时高优先级主线程（prio 0x2C）也在同一帧里读同一个 pack 文件，跟着在**同一个自旋锁**上用户态空转（spin::Mutex 无 sleep / 无优先级继承）。Horizon 同核严格优先级抢占 ⇒ 自旋的主线程永不让出 core 0 ⇒ 低优先级 worker（0x30）永远拿不到 CPU ⇒ 锁永不释放 ⇒ 双线程永久停住、黑屏、无 crash、无 last_error；watchdog 的轮询点（主线程每个 tick 调一次）在主线程卡住后**结构上不可能再运行**，所以 3 s 看门狗未触发是设计使然，不是证据缺失。

| 排名 | 假设 | 置信度 | 一句话 | 关键证据 |
|---|---|---|---|---|
| **H1** | 同核优先级反转 + 自旋锁跨阻塞 SD I/O（pack 文件锁） | **高** | worker 持 pack 自旋锁阻塞在 fread；主线程同锁自旋；同核 0x2C > 0x30，worker 永久饿死 | vfs.rs:23,67-101 + lib.rs:975-983 + async_decode.rs:328-342 + fs.rs:94-102 + main.c:350 + Atmosphère 调度 |
| **H2** | 同族：resource_cache 的 CACHES 自旋锁临界区过长（持锁 log / LRU 淘汰 drop 大对象） | 中低 | 同一反转模式，但临界区 µs–ms 级，解释"首帧必现"概率低 | resource_cache.rs:107-157、ring_log.rs:19,30-48 |
| **H3** | newlib stdio / FILE / fs 并发安全 | 低 | libnx 每线程独立 struct _reent，剩下共享的 malloc 锁、fs IPC 都是"睡眠型"锁，不会饿死 | libnx thread.c threadCreate、libnx Mutex |
| **H4** | 1 MiB 栈溢出 / panic / 分配失败 | **排除** | 无 crash 报告、无 last_error.txt；且 v1.0.6 用 0x20000 栈同样黑屏 | 设备证据 + p18 patch |
| — | **看门狗自身设计缺陷**（独立结论，100% 确定） | — | 看门狗代码在主线程 tick 内；主线程一卡住就永远不会被调用；恢复路径 drain_inline 还会撞同一个 pack 锁；rfvp_switch_async_disable() 声明了但**全仓无人调用** | no_std_core.rs:522-536, 656-658、grep 结果、main.c:86-89 |

> **一句话修复方向**：不要用 spin 锁保护可能阻塞的 I/O（pack 文件句柄）；把 no_std 的 sync::Mutex 换成会睡眠的锁（或让 worker 用独立 FILE 句柄）；看门狗必须移出主线程。

---

## 1. 现场证据与判读

### 1.1 任务给定的设备证据（v1.0.8，真机）

~~~
sdmc:/switch/rfvp/async_status.txt:
  enabled=1 create=0x0 start=0x0 hb=3 stage=0
~~~

- create=0x0 / start=0x0：threadCreate / threadStart 均成功（0 = 成功），worker 线程确实创建并启动过。
- 主线程在创建线程后立刻写一次 status（main.c:358），此后**不再刷新**（主线程卡死）。
- worker 心跳 hb=3：worker 在 status 被写下的瞬间恰好跑过 3 圈空闲循环（每圈 svcSleepThread(1ms)），之后也未再刷新（worker 也停住，或至少没活到 hb=1000 的写盘点）。
- stage=0：**这是主线程写文件那一刻的快照**（worker 空闲），不能证明 worker 死时 stage=0——stage 只在 run_next_job 里更新，而 worker 冻结后没有任何东西会再写这个文件。
- 无 crash 报告、无 last_error.txt（panic_handler 会写它，ffi.rs:109-121），排除 Rust panic / abort。
- 同版本 async=off 可跑 1800 帧 60 fps。

### 1.2 本轮复核/补充的设备与模拟器证据

| 证据 | 内容 | 判读 |
|---|---|---|
| E:/galnx-build/p19/device-logs/mtp/perf_slow.log | frame 1 slow 4337.9 ms ... stages(ms): vfs_read 3267.02 graph_decode 18.48（另一行 4287.8 / 3233.01） | **首帧要做 ~3.2 s 的 pack 读**——给了"主线程正在大量读 pack"与"worker 持锁读 pack"的完美碰撞窗口；v1.0.8 只是把其中 ≥1 MiB 的解码挪到 worker，读盘竞争没变 |
| p20/device-logs/crash/*.log | 两份 crash 分别属于 010000000000100f（LibAppletOf，User Break）与 01009bc00c38a000（hbloader/sphaira，Data Abort at 0x0），**都不是 RFVP 游戏进程** | 与"游戏无 crash"自洽，不能用来证明栈溢出/panic |
| p20/run-async-on/20261101-222311-rfvp/（Citron 模拟器） | 20 s 正常运行，status=loaded，点击/按键步骤全部推进，截图至 step-11-a3-adv.png | **模拟器不复现**：guest 线程被映射为宿主线程，调度完全由 Windows 抢占式调度器负责，不存在 Horizon 的"同核按优先级 + 只在 idle core 迁移 suggested 线程"语义，也没有真实 SD 延迟 |
| p19/device-logs/mtp/async_status.txt、p20/device-logs/crash/async_status.txt | 均为 v1.0.7 格式 enabled=1 create=0x0 start=0x0 hb=4（无 stage 字段） | 磁盘上未找到 v1.0.8 的 hb=3 stage=0 快照；任务给出的这条来自真机 SD，属于 v1.0.8 格式，作为一手证据采信 |
| p19 ring log | 无任何 [async] 行 + 2760 帧 60fps | 该次成功运行为 async=off（或异步从未提交），可作为"同步路径健康"的基线 |

### 1.3 证据缺口（诚实声明）

1. 没有冻结时刻的 thread_info/dmnt dump（现有两份 dump 属于别的进程），因此 H1 的内核调度结论来自**代码+日志推演**，不是直接观测。第 8 节给出决定性的 A/B/C 验证实验。
2. hb=3 是主线程写的快照，不是 worker 死时的计数；worker 的真实死亡位置（stage=1/3/4）没有落盘。这本身就是 P20 探针的缺陷（见第 7 节）。
3. cpuid=-2 的解析、进程 ideal core=0 的结论来自 Atmosphère master 源码（第 2.2 节）；不同固件/内核版本若有差异，需真机实验确认。

---

## 2. 平台模型：为什么在真机上这是"永久冻结"

### 2.1 no_std 构建里所有 std::sync::Mutex 都是纯自旋锁

~~~rust
// crates/rfvp/src/lib.rs:968-988
#[cfg(feature = "no_std")]
pub mod sync {
    pub struct Mutex<T>(spin::Mutex<T>);
    impl<T> Mutex<T> {
        pub const fn new(value: T) -> Self { Self(spin::Mutex::new(value)) }
        pub fn lock(&self) -> Result<spin::MutexGuard<'_, T>, ()> { Ok(self.0.lock()) }
    }
}
~~~

~~~toml
# crates/rfvp/Cargo.toml:81
spin = { version = "0.9.8", optional = true, default-features = false, features = ["mutex", "spin_mutex"] }
~~~

spin_mutex 策略 = 纯 spin_loop 忙等：**不睡眠、不让出 CPU、无优先级继承、无公平性**。Switch 构建启用了 no_std（platform/switch/host/Cargo.toml:17），所以引擎里所有 std::sync::Mutex（pack 文件、缓存、日志、队列……）都是这个自旋锁。

### 2.2 Horizon 同核调度：严格优先级 + 迁移只服务 idle core 的 suggested 队列

~~~cpp
// Atmosphère master: libraries/libmesosphere/source/svc/kern_svc_thread.cpp:28-33
Result CreateThread(..., int32_t priority, int32_t core_id) {
    KProcess &process = GetCurrentProcess();
    if (core_id == ams::svc::IdealCoreUseProcessValue) {  // -2
        core_id = process.GetIdealCoreId();
    }
    ...
}
// libraries/libmesosphere/source/kern_k_process.cpp:207  (KProcess::Initialize)
m_ideal_core_id = 0;
// libraries/libmesosphere/source/kern_k_process.cpp:983  (创建主线程)
KThread::InitializeUserThread(main_thread, ..., priority, m_ideal_core_id, this)
~~~

- cpuid=-2 = IdealCoreUseProcessValue（svc_types_common.hpp:379-381），解析为**进程 ideal core = 0**；主线程初始化时用的也是同一个 m_ideal_core_id ⇒ **主线程与 worker 的 ideal core 都是 0**。
- 优先级：main.c:350 创建 worker 时传 0x30；libnx 文档（/d/devkitPro/libnx/include/switch/kernel/thread.h:37）明确"0x2C 是主线程常用优先级"。**数值越小优先级越高**，所以 worker（0x30=48）低于主线程（0x2C=44）。
- 同核调度是严格按优先级的抢占式调度：只要主线程是 runnable，core 0 上就不会调度 worker。
- 核迁移（kern_k_scheduler.cpp:110-205 UpdateHighestPriorityThreadsImpl）：只有在**有核空闲**时，对每个 idle core 取 priority_queue.GetSuggestedFront(core_id)，看该核 suggested 队列（本质是"ideal core 指向该核"的线程）里有没有可迁移者，才做 SetActiveCore 迁移；且 kern_k_scheduler.cpp:161 有保护 if (top_thread != nullptr && top_thread->GetPriority() < HighestCoreMigrationAllowedPriority /* =2, kern_k_scheduler.hpp:37 */) break;（只拦优先级 0/1 的内核线程，与我们无关）。
- 关键结论：**ideal core = 0、已经在 core 0 上 runnable 的 worker，不会因为"另一核空闲"而被迁走**。它的 suggested 目标是 core 0，而 core 0 被自旋的主线程占着 ⇒ 永久饿死。这就是"主机永久冻结、只能断电重启"的内核层解释。

### 2.3 由此得到的一般性规则（本次事故的教训）

> 在 Horizon 上，一个**比持锁者优先级高**的线程如果在用户态自旋等锁，而持锁者恰好**在睡眠中持有该锁**（例如阻塞 I/O），那么系统进入不可恢复状态：自旋者永不让出，持锁者永不被调度。

v1.0.8 的 worker 路径正好踩中这个模式（见下节）。

---

## 3. H1（主因）：同核优先级反转 + 自旋锁跨阻塞 SD 读

### 3.1 共享的 pack 文件句柄与自旋锁（主线程与 worker 共用同一个锁实例）

~~~rust
// crates/rfvp/src/subsystem/resources/vfs.rs:19-23
// std is the crate's own shim in no_std builds.
use std::sync::Mutex;                 // ← no_std 下就是 lib.rs:975 的 spin::Mutex

// vfs.rs:67-85
pub struct HostPackFile<F: RfvpFile> {
    file: Mutex<F>,                   // ← 保护整个 FILE 句柄
    len: u64,
}
// SAFETY: a FILE may be used from any thread; the VFS only touches it under a lock.
unsafe impl<F: RfvpFile> Send for HostPackFile<F> {}
unsafe impl<F: RfvpFile> Sync for HostPackFile<F> {}

// vfs.rs:92-101
fn read_at(&self, offset: u64, buf: &mut [u8]) -> Result<usize> {
    let mut file = self.file.lock()...;   // ① 拿自旋锁
    file.read_at(offset, buf)             // ② 阻塞 fseek+fread，锁一直 held
        .map_err(...)
}
~~~

底层 HorizonFile::read_at（platform/switch/host/src/fs.rs:94-102）就是 fseek(SEEK_SET) + fread(buf,1,len,file)——在真实 SD 上会通过 libnx fs IPC 睡眠等待，**时间从几百 µs 到几百 ms 不等**。

pack 文件句柄在 boot 时打开（crates/rfvp/src/no_std_core.rs:1547-1553：host.fs().open(&path) → HostPackFile::new(file) → Arc<dyn PackSource>），由 Vfs 持有；pack_location()（vfs.rs:617-635）把它 clone 成 Arc 交出去：

~~~rust
// vfs.rs:617-635（简化）
pub fn pack_location(&self, path: &str) -> Option<(Arc<dyn PackSource>, u64, u64)> {
    ...
    Some((file.pack.0.clone(), entry.offset, entry.size))   // 同一个 Arc、同一个 Mutex
}
~~~

⇒ **worker 的 Job.source 与主线程 Vfs 读文件走的是同一个 HostPackFile / 同一个 spin::Mutex。**

### 3.2 worker 侧：一次 read_bytes 就把整张 13 MB 图读完，全程持锁

~~~rust
// crates/rfvp/src/subsystem/resources/async_decode.rs:328-342
fn read_bytes(job: &Job) -> Result<Vec<u8>> {
    let size = usize::try_from(job.size)...;
    let mut out = vec![0u8; size];          // 13 MB 级分配
    let mut done = 0usize;
    while done < out.len() {
        let n = job.source.read_at(job.offset + done as u64, &mut out[done..])?;  // 一次传剩余全部
        ...
    }
}
~~~

read_at 一次性接收 13 MB 缓冲区 ⇒ HostPackFile::read_at 里的 fread 单次调用就要读 13 MB（内部按 libnx fs 读块循环，每块都有 IPC 睡眠机会），**整个期间锁被 worker 持有**。worker 的调用链：

platform/switch/runtime/main.c:301-310 worker 循环 → rfvp_switch_decode_step()（platform/switch/host/src/decode.rs）→ async_decode::run_next_job()（async_decode.rs:441-467）→ report_stage(1) → read_bytes（锁内阻塞）→ report_stage(3) → decode → report_stage(4) → finish_job → report_stage(0)。

### 3.3 主线程侧：提交异步后**立刻**在同一帧继续同步读 pack

~~~rust
// crates/rfvp/src/subsystem/components/syscalls/graph.rs:1041-1069（简化）
prefetch_graph_siblings(game_data, path);
if let Some((source, offset, size)) = game_data.vfs.pack_location(path) {
    if size >= async_decode::ASYNC_INLINE_MIN_BYTES            // 1 MiB
        && async_decode::submit_graph(id as u16, path, source, offset, size)
    {
        return Ok(Variant::Nil);        // ← 不等 worker，保留旧纹理，继续当前帧
    }
}
if async_decode::wait_for_graph(path, 400) { ... }             // 睡眠等待，不致命
// graph.rs:1070：异步未命中/小于阈值时，主线程同步读 pack
let buff = game_data.vfs_load_file(path)?;                     // world.rs:402 → vfs.read_file
~~~

Vfs::read_file（vfs.rs:557-580）→ open_stream_with_len → PackSlice::read（vfs.rs:120-135）→ self.source.read_at(...)（vfs.rs:127）→ HostPackFile::read_at → self.file.lock() → **自旋**。

首帧除了这张大 CG，还要加载大量 <1 MiB 的资源（背景、UI、脚本、音频），p19 的 perf_slow.log 显示首帧 vfs_read 累计 **3.27 s**——主线程几乎连续在读同一个 pack。

### 3.4 事故时序（t0 之后全部发生在第一帧 tick 内）

| 时刻 | 主线程（prio 0x2C / core 0） | worker（prio 0x30 / core 0） | pack spin 锁 |
|---|---|---|---|
| t0 | threadStart 成功，写 async_status（main.c:350-358） | 已在 runnable 队列，但优先级低；主线程在 fopen/fprintf/fclose 的 fs 睡眠间隙里跑过 3 圈（hb=3） | free |
| t1 | 进入第 1 帧 tick：apply_async_decodes（watchdog 检查 pending=0，通过）→ 场景/VM 更新 → graph_load 大 CG | 收到 job，run_next_job：report_stage(1) → vec![0u8; 13MB] → read_at → **拿到锁** → fread 阻塞在 fs IPC（锁未释放） | **worker held** |
| t2 | 同帧继续同步加载其它资源 → Vfs::read_file → HostPackFile::read_at → file.lock() | 仍在 fs IPC 上睡眠（锁未释放） | held；主线程**自旋** |
| t3 | fs 读完一块，worker 变 runnable（prio 0x30）；但主线程 prio 0x2C 更高且是 runnable 的自旋者 → worker 永不被调度 | 饿死 | 永不释放 |
| t4+ | 永久自旋在 spin::Mutex::lock 的 spin_loop 里 → 帧不再推进、audio 停、watchdog 永不运行 | 永久 runnable-but-starved（或停在 fs 睡眠） | 死锁 |
| 断电前 | async_status.txt 停在 hb=3 stage=0；无 crash、无 last_error | — | — |

### 3.5 与所有已知证据的吻合性

- **双线程同时停**：主线程自旋（用户态），worker 要么在 fs 睡眠要么 runnable 被饿死——两者都"停"，且心跳不再增长。
- **无 crash / 无 last_error**：没有任何异常/abort/栈溢出，只是调度层面的活锁。
- **async=off 正常**：只有一个线程读 pack，锁永远自由；阻塞读能正常完成。
- **v1.0.6（P18）"some consoles stayed black before the first frame"**：同一机制的早期版本（无条件启用 worker，0x20000 栈、prio 0x30、cpuid -2 完全相同）。
- **不同主机表现不同**（P18 时 some consoles）：SD 速度/系统负载决定首帧 3 s I/O 内碰撞的时机，但一旦碰上就永久冻结。
- **Citron 不重现**：模拟器里 guest 线程是宿主线程，调度由 Windows 抢占式负责，I/O 是宿主缓存/文件系统，"优先级反转饿死"的语义不存在。
- **3 s 看门狗未触发**：见第 7 节——看门狗根本没有机会运行，且即使运行也救不了（会撞同一个锁）。

### 3.6 为什么这是"必现"而不是"小概率"

- 首帧的 pack 读窗口是 **秒级**（3.2 s），而 worker 只要完成一次 13 MB 读就必然长时间持锁；
- 主线程读同一 pack 的频率是每帧多次，且在 async 提交后的同帧就会发生；
- 只要 worker 在"持锁 + fs 睡眠"的任意瞬间主线程来抢锁，就永久死锁——窗口覆盖首帧大部分时间。

---

## 4. H2（同族次因）：resource_cache 的 CACHES 自旋锁临界区

~~~rust
// crates/rfvp/src/subsystem/resources/resource_cache.rs:107-119
static CACHES: spin::Mutex<Option<Caches>> = spin::Mutex::new(None);
fn with_caches<R>(f: impl FnOnce(&mut Caches) -> R) -> R {
    let mut guard = CACHES.lock();
    if guard.is_none() { *guard = Some(Caches { ... }); }
    f(guard.as_mut().expect("caches initialized"))    // ← 闭包在持锁时执行
}

// resource_cache.rs:132-141
pub fn put_texture(path: &str, entry: DecodedTexture, size: usize) {
    let key = key(path);
    with_caches(|c| {
        c.textures.put(key, entry, size);             // LRU 淘汰时 drop Arc<DynamicImage>（13 MB 级 free）
        if crate::perf::enabled() {
            let (bytes, budget) = (...);
            crate::perf::event(format_args!("[cache] texture put ..."));  // → log::info! → LINES 锁
        }
    });
}
~~~

问题形态与 H1 **完全同族**：CACHES 是自旋锁；worker 在持锁期间可能因 LRU 淘汰而 free 十几 MB（走 newlib malloc 锁）或做日志格式化（嵌套 ring_log::LINES 自旋锁，ring_log.rs:19,30-48）；主线程每帧多次 get_texture（graph.rs:1026-1040）。如果主线程在 worker 持 CACHES 的瞬间自旋，同样会饿死 worker。

**为什么排在 H1 之后**：CACHES 临界区是 µs–ms 级（无阻塞 I/O；malloc 锁是睡眠型），要命中需要精确的抢占时刻；而 H1 的窗口是秒级、覆盖整帧。**若 H1 修复后仍有偶发冻结，应首先排查这里。** 修复同 H1：持锁期间不做日志、不 drop，或换睡眠锁。

---

## 5. H3（低置信，已降级）：newlib stdio / FILE / fs 并发

- **每线程独立 reent**：libnx threadCreate（libnx nx/source/kernel/thread.c）为每个线程分配独立的 struct _reent（TLS 内的 _impure_ptr），_REENT_INIT_PTR 后继承父线程的 _stdin/_stdout/_stderr；FILE 对象由每次 fopen 独立创建。⇒ "两个线程共享 newlib stdio 状态导致踩踏"的经典假设**基本不成立**。
- **仍然共享**：newlib 堆（全局 __malloc_lock 递归锁，libnx 上是睡眠型）、libnx fs IPC 会话（IPC 互斥，睡眠型）。两者都不会造成 H1 那种"自旋者饿死持锁者"。
- 唯一的多线程写文件点：worker 的 hb%1000==0 写 async_status.txt（main.c:304-305）与主线程写同一文件（main.c:358，每 600 帧一次）。并发 fopen("w") 可能产生内容交错或截断，但**不会让进程挂起**；且本故障死亡时间 <1 s（hb<1000），worker 根本没走到写盘点。
- 结论：与本故障症状不匹配，排在第 3。

---

## 6. H4（排除）：1 MiB 栈溢出 / panic / 分配失败

- panic_handler（platform/switch/host/src/ffi.rs:109-121）会写 sdmc:/switch/rfvp/last_error.txt 并 abort()；现场**没有** last_error.txt。
- 栈溢出在 Horizon 上会触发内核异常报告（crash report / error applet）或进程终止；现场无 crash。
- v1.0.6（P18）用 0x20000（128 KiB）栈也同样黑屏，说明与 1 MiB 栈无关。
- threadCreate 的 1 MiB 栈来自 newlib 堆（libnx thread.c：stack_sz + tls_sz + reent_sz 一次 __libnx_aligned_alloc），若分配失败会返回错误码，而现场 create=0x0 成功。

---

## 7. 为什么 3 s 看门狗未触发（结构性缺陷，独立于 H1）

### 7.1 位置决定它看不见"主线程卡死"

~~~rust
// crates/rfvp/src/no_std_core.rs:656-658（tick 内）
host.audio().tick(elapsed_us)?;
#[cfg(feature = "switch-async")]
self.apply_async_decodes(host);       // ← watchdog 的唯一轮询点

// no_std_core.rs:522-536
fn apply_async_decodes<H: RfvpHost>(&mut self, host: &mut H) {
    if async_decode::watchdog_stalled() {      // 每 tick 调一次
        let drained = async_decode::drain_inline();
        ...
    }
    ...
}
~~~

看门狗是**主线程**在每个 tick 开头做的检查。任何"主线程自己卡住"的故障（自旋等锁、阻塞 I/O、死锁）都会让 apply_async_decodes 再也不被调用——3 s 后当然不会触发。它只能发现"主线程还活着、但 worker 不动"的情况，而本故障恰恰是主线程先卡住。

### 7.2 即使看门狗能运行，恢复路径也会死锁

drain_inline()（async_decode.rs:396-418）在主线程上逐 job 执行 read_bytes → 走**同一个 HostPackFile 自旋锁**。在 H1 场景里该锁正被 worker 持有（worker 在 fs 睡眠）⇒ 主线程 drain 时同样自旋 ⇒ 照样死。恢复逻辑对"worker 持锁卡住"这一最可能的故障形态无效。

### 7.3 其它探针缺陷

- runtime/main.c:86-89 定义了 rfvp_switch_async_disable()，注释说 the engine's watchdog calls this before draining，但**全仓没有任何调用点**（grep -rn rfvp_switch_async_disable crates platform 只命中声明 async_decode.rs:65 与定义 main.c:87）⇒ 即使看门狗触发，g_rfvp_async_enabled 仍为 1，后续仍会继续提交 job 给死掉的 worker。
- worker 只在 hb%1000==0 时写 status（main.c:304-305），约 1 s 一次；冻结发生在 1 s 内时**不会留下 worker 侧任何新证据**，现场永远看到主线程写的旧快照（hb=3 stage=0）。
- stage 语义还有一个坑：async_decode.rs:70-80 注释说 2 = reading pack bytes，但 run_next_job（async_decode.rs:441-467）实际只报 1 → 3 → 4 → 0，**stage=2 从未使用**；worker 卡在 read_bytes 时应表现为 stage=1，而不是 2。
- 结论：**"3 s 看门狗未触发"不是"故障不严重"的证据，而是该看门狗架构上就不可能捕获此类故障。**

---

## 8. 最小验证方案（按代价从低到高）

> 所有实验都在真机、async.txt=on 下做；每次只改一个变量，记录 async_status.txt、frame_status.txt、是否黑屏、帧数。

### E0（零改动，只需现有工具）：冻结后抓线程快照

- 冻结后用 Atmosphère dmnt 的线程调试（如 dmnt:cht 的 threadinfo / getthreadlist，或 hbmenu 的 sysmodule 工具）导出该进程所有线程的 PC/LR/状态。
- **若 H1 成立**：主线程 PC 落在 spin::Mutex 的自旋循环（vfs.rs HostPackFile::read_at 的 lock() 内，符号可能内联，可对照 aarch64-none-elf-objdump 的 ldaxr/stlxr 循环）；worker PC 落在 svcWaitSynchronization（libnx fs IPC）或 fread 内部。
- 注意：现有 p20/device-logs/crash/dumps/*.bin 属于 LibAppletOf / sphaira，**不是**本游戏进程，别误用。

### E1（一行改动，最直接的因果判别）：把 worker 优先级提高到主线程之上

~~~c
// platform/switch/runtime/main.c:350
threadCreate(&decode_thread, rfvp_decode_thread, NULL, NULL, 0x100000, 0x2B /* was 0x30 */, -2);
~~~

- **预期（若 H1 成立）**：不再冻结；async_status 的 hb 增长到 1000 以上并被 worker 重写；ring log 出现 [async] decoded ...；帧继续推进。
- **若仍冻结**：优先级反转不是充分解释，转向 H2（CACHES）或真正的 ABBA 死锁排查。

### E2（一行改动，区分"同核"与"锁本身"）：把 worker 放到另一核

~~~c
threadCreate(&decode_thread, rfvp_decode_thread, NULL, NULL, 0x100000, 0x30, 1 /* was -2 */);
~~~

- **预期（若 H1 成立）**：不再冻结（worker 在 core 1 独立运行，主线程在 core 0 自旋也饿不死它）。
- **若仍冻结**：说明不是同核调度问题，而是两核都卡在某个共享锁/fs 层，需要重新排序假设。

### E3（诊断补强，1~2 h）：让冻结留下 worker 侧证据

1. worker 的 C 侧循环里，stage 变化时立即写 worker_status.txt（hb, stage, pending_atomic；stage 来自已有 g_rfvp_async_stage），不要只依赖 hb%1000；
2. 主线程保留 debug.txt 时的 frame_status.txt（v1.0.9 代码已具备，main.c:109-124），每帧写；
3. 在 HostPackFile::read_at 加两个原子计数（spin 次数 / 阻塞读次数）并落盘。
- **预期（若 H1 成立）**：冻结后 worker_status 最后一行 stage=1（卡在 read_bytes）、hb 不再增长；frame_status 停在某个小帧号；spin 计数巨大。

### E4（修复候选验证）：解除"跨阻塞 I/O 的 spin 锁"

任选其一，验证 async=on 是否能跑到 1800 帧：
1. 把 HostPackFile.file 的保护换成睡眠锁（libnx Mutex / svcArbitrateLock 封装；注意需要 const 初始化或懒初始化）；
2. 或让 worker 的 read_at 使用**独立的 FILE 句柄**（每次 fopen 或用线程本地缓存），主线程与 worker 不共享 FILE 及其锁；
3. 或把 read_bytes 改成分块（如 256 KiB/次）并在块间释放锁——**注意这只能缩小窗口，不能根治**（主线程仍可能在 worker 阻塞读的块间自旋；必须配合睡眠锁）。

### E5（可选）：在模拟器侧构造对照

在 Citron 里人为把 I/O 拖慢（如放到慢速网络盘/大量小读）也未必能复现，因为模拟器调度语义不同；不建议把模拟器作为主要验证手段。

---

## 9. 修复建议

### 9.1 根修（必须）

1. **不要让 spin 锁保护可能阻塞的 I/O。**
   - 最优：HostPackFile 的读路径改用**睡眠锁**（libnx Mutex / svcArbitrateLock；若 const fn 初始化不便，可做成 OnceCell + static，或自建 AtomicU32 + svcArbitrateLock 的 const 锁）。睡眠的等待者不会吃 CPU，持锁者总能被调度，反转不再致命。
   - 等价方案：**主线程与 worker 各自持有独立 FILE 句柄**（同一文件可多次 fopen），彻底消除跨线程共享锁。HostPackFile 可拆成 main handle 与 worker handle（read_at_worker）。
   - 顺带修 vfs.rs:397 的 LooseDir.listings（目录枚举 I/O 期间持 spin 锁，boot 期主线程自用，非本案主因，但属同类隐患）。
2. **resource_cache 不在自旋锁内做日志/淘汰 drop**：把 perf::event 与 Lru::put 的淘汰对象挪到锁外（先 replace/返回淘汰列表再统一 drop），或整体换睡眠锁。
3. **worker 的 pack 读取分块**（256 KiB–1 MiB/块），每块后 report_stage/释放锁，作为辅助手段缩短最坏持锁时长（**不能单独作为修复**，理由见 E4-3）。

### 9.2 看门狗重设计（工程必做）

1. 用**独立线程**做 watchdog：优先级略高于主线程（如 0x2B）或至少 0x2C-1，专门监视两个原子量：main_frame_counter（主线程每帧 ++）与 worker_heartbeat（worker 每圈 ++）。
2. 3 s 无进展时：写 watchdog.txt（含 frame/hb/stage/pending、ring_log::dump()）、再尝试恢复（把 g_rfvp_async_enabled=0 并让主线程下一帧走同步路径——但主线程若已卡死则无效），最后可 svcExitProcess/触发 crash report 方便事后取证。**注意**：watchdog 线程写文件时不要与卡死持锁线程共享同一把锁/同一个 FILE。
3. rfvp_switch_async_disable() 要么真正接到 watchdog 路径，要么删掉（目前是死代码，误导维护者）。
4. v1.0.9 的 frame_status.txt 探针（debug.txt 开关）保留，但冻结时它只能证明"主线程死了"，需要 worker 侧独立状态文件才能定位到阶段。

### 9.3 防御性配置（低成本）

- worker 创建时显式 cpuid = 1（或 2/3）+ prio = 0x2B：即使未来还有共享锁，也基本消除"同核饿死"路径（但**不能**替代 9.1 的锁修复）；
- 把 ASYNC_INLINE_MIN_BYTES 抬高/把异步范围限制在真正的大 CG，减少首帧内 worker 与主线程同时读 pack 的窗口（缓解，不根治）；
- 短期发布：保持 v1.0.9 行为（真机 async 强制 off），在 main.c:91-97 注释里引用本报告路径，避免下次误开。

### 9.4 建议的验证顺序

E1（优先级）→ E2（换核）→ E3（探针）→ 修复（9.1-1 或 9.1-2）→ E4 验证 1800 帧 60 fps → 再逐步恢复 async 默认值。

---

## 10. 关键证据行号表

| 事实 | 位置 |
|---|---|
| no_std sync::Mutex = spin::Mutex（无睡眠/无 PI） | crates/rfvp/src/lib.rs:968-988 |
| spin 0.9 配置（纯 spin_loop） | crates/rfvp/Cargo.toml:81 |
| Switch 构建启用 no_std + switch-async | platform/switch/host/Cargo.toml:17 |
| std::sync::Mutex 在 vfs.rs 的引入 | crates/rfvp/src/subsystem/resources/vfs.rs:19-23 |
| HostPackFile { file: Mutex<F> } + Send/Sync | vfs.rs:67-85 |
| **锁跨阻塞读持有** | vfs.rs:92-101（lock() 后 file.read_at） |
| FILE 实际读 = fseek+fread（无内部锁） | platform/switch/host/src/fs.rs:88-102 |
| PackSlice::read 每次调用一次 read_at | vfs.rs:120-135 |
| pack_location 克隆共享 Arc<dyn PackSource> | vfs.rs:617-635 |
| pack 文件在 boot 打开并交给 Vfs | crates/rfvp/src/no_std_core.rs:1547-1553 |
| worker read_bytes：一次 13 MB read_at | crates/rfvp/src/subsystem/resources/async_decode.rs:328-342 |
| worker 主循环与心跳/status 写盘 | platform/switch/runtime/main.c:299-310（心跳 304-305） |
| threadCreate(...,0x100000,0x30,-2) + threadStart | platform/switch/runtime/main.c:349-357（create 350，start 352） |
| 启动时写 status（hb=3 的来源） | platform/switch/runtime/main.c:358（函数 102-107） |
| 异步提交后立即返回、同帧继续同步读 pack | crates/rfvp/src/subsystem/components/syscalls/graph.rs:1041-1070 |
| vfs_load_file → Vfs::read_file | crates/rfvp/src/subsystem/world.rs:402、vfs.rs:557-580 |
| watchdog 唯一调用点（tick 内） | crates/rfvp/src/no_std_core.rs:656-658 |
| watchdog 实现 + drain_inline | crates/rfvp/src/subsystem/resources/async_decode.rs:375-418 |
| watchdog 分支（主线程） | crates/rfvp/src/no_std_core.rs:522-536 |
| CACHES 自旋锁 + 持锁 log/LRU | crates/rfvp/src/subsystem/resources/resource_cache.rs:107-157 |
| ring_log LINES 自旋锁 | crates/rfvp/src/ring_log.rs:19,30-48 |
| rfvp_switch_async_disable 定义但无调用者 | async_decode.rs:65（声明）、main.c:86-89（定义）；grep 仅此两处 |
| cpuid 魔法值 | Atmosphère svc_types_common.hpp:379-381 |
| cpuid=-2 → 进程 ideal core | kern_svc_thread.cpp:28-33 |
| 进程（含主线程）ideal core = 0 | kern_k_process.cpp:207, 983 |
| 同核严格优先级调度 + 迁移只看 idle core suggested 队列 | kern_k_scheduler.cpp:110-205、kern_k_scheduler.hpp:37 |
| 主线程常用优先级 0x2C 的官方说明 | /d/devkitPro/libnx/include/switch/kernel/thread.h:37 |
| libnx 每线程 struct _reent | libnx nx/source/kernel/thread.c（threadCreate） |
| panic → last_error.txt（现场无此文件） | platform/switch/host/src/ffi.rs:109-121 |

---

## 11. 局限与未决

1. cpuid=-2 → ideal core 0 的结论基于 Atmosphère master 源码；未验证特定固件版本是否有差异，也未验证虚拟核到物理核的映射细节。E1/E2 两个一行实验即可给出行为层面的确证。
2. 没有冻结时刻的线程 dump；hb=3 stage=0 是主线程写的快照。建议按 E3 补探针后重跑一次，拿到 worker 真实 stage。
3. H1 与 H2 都源于"自旋锁 + 阻塞/长临界区"这一模式；若 E1/E2 均不能消除冻结，应按"锁内阻塞点清单"逐项排查（pack、CACHES、LINES、LooseDir.listings、malloc 锁）。
4. 未分析音频线程（audio_pump）与 SDL 线程的线程数/优先级；本故障中它们与本假设无直接耦合，但若后续引入更多线程需重审锁模型。

---

## 12. 参考

- Atmosphère（master）：libraries/libmesosphere/source/svc/kern_svc_thread.cpp、libraries/libmesosphere/source/kern_k_process.cpp、libraries/libmesosphere/source/kern_k_scheduler.cpp、libraries/libmesosphere/include/mesosphere/kern_k_scheduler.hpp、libraries/libvapours/include/vapours/svc/svc_types_common.hpp
- libnx：nx/source/kernel/thread.c（每线程 reent、栈分配）、include/switch/kernel/thread.h（优先级说明）
- 本仓库：E:/galnx-build/m5-rfvp；P18/P19/P20 补丁：E:/galnx-build/p18/rfvp-async-decode.patch、E:/galnx-build/p19/rfvp-async-toggle.patch、E:/galnx-build/p20/rfvp-async-watchdog.patch
- 既有取证：E:/galnx-build/p19/device-logs/mtp/perf_slow.log、E:/galnx-build/p20/device-logs/、E:/galnx-build/p20/run-async-on/20261101-222311-rfvp/
