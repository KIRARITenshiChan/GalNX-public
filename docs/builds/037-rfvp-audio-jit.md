# 037 — P30：rfvp 音频 JIT 渲染（修复 3 秒延迟）

- 日期：2026-11-07
- 状态：Citron 级 PASS（Lead 独立验收），真机待验
- 相关：\`034-rfvp-audio-continuity.md\`（P27，3.07 s 预渲染 ring）、\`docs/builds/patches/rfvp-switch/rfvp-audio-jit.patch\`
- 目标：P27 解决了「主线程长帧导致音频断流/卡顿」，但引入了新的体感缺陷——所有音频比游戏状态晚约 3 秒触发。P30 在保留「长帧期间音频不断」的前提下把延迟压回 ~100 ms 以内。

## 1. 缺陷与根因

用户真机反馈（v1.1.4-test）：**所有音频都在应当触发的时机之后约 3 秒才播放**。

根因（代码级确认）：

- P27 的实现是「主线程预渲染 + 音频线程照单播放」：\`platform/switch/runtime/main.c\` 的 \`audio_pump()\` 每帧调用 \`audio_render_pages(app, 8)\`，只要 3.07 s 的 SPSC ring（144 页 × 1024 帧 = 147,456 帧）还有空位就继续渲染（每帧最多 8 页 ≈ 170 ms）。
- 音频线程只按硬件节奏取**最旧**的 6 页喂 \`AudioDriverWaveBuf\`。主线程的渲染速度（约 40 倍实时）远高于消费速度，稳态下 ring 恒满。
- 因此实际听到的 PCM 永远是「3.07 秒之前」的混音结果：角色台词与嘴型/文字不同步，BGM 触发也与场景错位。
- 本质矛盾：**预渲染越多，抗卡顿越强，但延迟越高**；ring 方案在数学上不可能同时做到「长帧不断音」和「低延迟」。

## 2. 方案：JIT（即时）混音

把混音改成音频线程按需即时进行：

- 帧线程不再渲染 PCM，只把 \`AudioCommand\` 入队（load/play/stop/参数等）。
- 音频线程在每块 \`AudioDriverWaveBuf\` 空闲时，先把队列里的命令全部 apply 到 \`SoftAudioMixer\`，然后立即 \`mix\` 出这一块 1024 帧（≈21.3 ms）并提交给硬件。
- 延迟 = 硬件 FIFO 深度（6 × 1024 帧 ≈ 128 ms），与 P27 之前的直接路径相同；主线程被 vfs/解码卡住 1 s 以上时音频线程仍在独立渲染，音乐/语音不断。

## 3. 实现

### 3.1 \`platform/switch/host/src/audio.rs\`（重写，+615/−? 行）

- 自实现 \`SpinLock<T>\`（\`AtomicBool\` + \`UnsafeCell\` + guard），两个全局：
  - \`static QUEUE: SpinLock<VecDeque<Command>>\`
  - \`static ENGINE: SpinLock<Option<AudioEngine>>\`
- \`enum Command\` 覆盖全部 \`RfvpAudio\` 方法：\`LoadEncoded / CreateStream / SubmitI16 / SubmitF32 / Play / Stop / Pause / Resume / SetParams / SetMasterVolume / DestroyStream\`。
- \`HorizonAudio\` 退化为零尺寸代理：\`new()\` 负责 \`install_mixer()\`，各 trait 方法只把命令 push 进 \`QUEUE\`，不触碰 mixer（因此不会和音频线程并发访问引擎）。
- \`render(&mut self, out: &mut [i16])\`（由音频线程调用）：\`mem::take(QUEUE)\` 取走全部命令 → 取 \`ENGINE\` 锁 → 逐条 \`apply\` → \`engine.render(out)\`。
- 命令 apply 失败不再静默：\`crate::ffi::log("rfvp: audio command failed: ...")\` 写 ODS，便于真机排查。
- 移除 \`Drop for HorizonAudio\`（引擎静态持有，进程退出由系统回收）。

### 3.2 \`platform/switch/runtime/main.c\`（audio 段重写）

- 删除：SPSC ring 数组、producer 计数、\`audio_render_pages\`、\`AudioRingPages/AudioProducePagesPerFrame/AudioPrimePages\`、ring 相关统计。
- 保留：\`audio_init\` / \`audio_pump_direct\`（线程创建失败时的单线程回退）/ \`audio_exit\`。
- \`rfvp_audio_thread(void* arg)\`：
  - 每 2 ms 轮询一次；每约 20 ms 调一次 \`audrvUpdate\`；
  - 对状态为 Free/Done 的 wave buffer 立即 \`rfvp_switch_audio_render(app, buf, AudioBufferFrames)\` → \`armDCacheFlush\` → \`audrvVoiceAddWaveBuf\`；
  - 统计 \`audio_pages_rendered\` / \`audio_start_us\` / \`audio_underrun_events\`（refill 间隔 > 300 ms 记一次）/ \`audio_max_refill_gap_ms\`。
- \`audio_pump()\` 在线程存在时直接 return（不再有任何主线程渲染）。
- 线程参数：\`threadCreate(..., 0x10000, 0x2D, {2,1,-2})\`（优先级高于主线程 0x2C，A57 上优先落 cpu2）。
- \`audio_status.txt\` 新格式（每 600 帧写一次）：

\`\`\`
mode=jit driver=%d thread=%d alive=%d cpu=%d pages=%llu rendered_ms=%llu uptime_ms=%llu lag_ms=%lld underrun=%u max_refill_gap_ms=%u stalls=%u stall_ms=%u
\`\`\`

  \`lag_ms = uptime_ms - rendered_ms\`。JIT 路径应稳定在 ±300 ms 内；P27 的 ring 路径会稳定在 +3000 ms 附近——这是区分两版实现最简单的判据。
- \`audio_stall.txt\`（debug.txt 注入 \`stall=\`/\`stall_at=\` 时，每对 pre/post 一行）同样记录 \`rendered_ms/lag_ms/underrun/gap_ms\`，用来证明长帧期间音频线程仍在独立推进。
- 调试钩子保留：\`debug.txt\` 的 \`stall=NNNN\` + \`stall_at=NNNN\` 让主线程 sleep，用于制造 >1 s 长帧做对照实验。

### 3.3 版本

\`platform/switch/host/Cargo.toml\` 与 \`Cargo.lock\` → **1.1.6-test**（1.1.5-test 已被 P29 OP 播放占用，尚未合入本线）。

## 4. 构建与产物

构建（必须走 devkitPro MSYS2）：

\`\`\`bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p30/build-115.sh'
\`\`\`

| 产物 | 路径 | 大小 | sha256 |
| --- | --- | --- | --- |
| NRO | \`target/rfvp-switch/switch/rfvp.nro\` | 7,946,296 B | \`a33db7ffdf4d7570b92342a8010e0fa5aab34412034513cd922692fc7902bab5\` |
| ELF | \`target/rfvp-switch-runtime/rfvp.elf\` | 17,284,432 B | \`bc948c1bb24d4cf55086fa380e9591ea07bab2be852887364bee935ef910424d\` |
| NSP | \`E:/galnx-build/p30/out/IROSEKA_FHD-010047420000a000-v1.1.6-test.nsp\` | 9,979,505,368 B | \`d7eb77ecf8bcba1f131ccaa5e26136a913e080203ccf096eca51e3e995e14461\` |

NSP 组成：title_id \`010047420000A000\`、romfs 161 项 9,932,275,140 B（hardlink，100% 内嵌）、hacBrewPack OK in 579 s；main 4,682,649 B sha \`1a40cf11…\`、control.nacp 16,384 B sha \`da75a9b9…\`。

\`galnx package nsp verify --manifest examples/pilot02-iroseka.yaml\` → **ok=true，12 checks：0 fail / 1 warn**（未签名属预期）；3 个 NCA 的 ProgID 一致为 \`0x010047420000A000\`。


## 4.1 补丁与全量 diff

- 增量补丁（入库）：`docs/builds/patches/rfvp-switch/rfvp-audio-jit.patch`：1,059 行 / 4 文件（+508/−382），sha256 `e81cd49c9f0dfe708b0914eca920b61a8419ad82d69db7ce896280d410593c5d`；基于基线 `cf5c8bc`（v1.1.4 源码树副本），`git apply --check` 通过。
- 全量（仓库外，base = 上游 `9f07ade`）：`/e/galnx-build/p30/rfvp-full-v116.diff`，688,326 B sha256 `a489c3e9a57d793430ee38f511021612bac10e482a4bac7552c92736bfd230c9`，37 files +13,089/−8,590，`git apply --check -p1` 通过。生成方式见 `E:/galnx-build/p30/make-full-diff-git.sh`（临时 git 仓库：base 提交 + v1.1.6 提交后 `git diff --binary`；`diff -ruN` 的 header 在 Windows 下会被二次前缀，不可直接用于 `git apply`）。

## 5. Citron 独立验收（Lead，v1.1.6-test NSP）

脚本 \`E:/galnx-build/p30/run-lead-audio-jit.sh\`：故意 \`async.txt=on\`、\`debug.txt\` 注入三次 1.2 s 主线程停顿（\`stall=1200 / stall_at=3800\`，落在正文台词段），走「标题 → Continue → DATA_001 → 连续 12 次 C 推进」。

run_dir \`E:/galnx-build/p30/run-lead-audio-jit/20261107-034903-IROSEKA_FHD-010047420000a000-v1.1.6-test\`：窗口 \`IROSEKA FHD (64-bit) | 1.1.6-test\`，35/35 步 ok，0 failed，diff_ratio 0.812134，60 FPS，无异常。

\`audio_status.txt\`：

\`\`\`
mode=jit driver=1 thread=1 alive=1 cpu=2 pages=5879 rendered_ms=125418 uptime_ms=125317 lag_ms=-101 underrun=0 max_refill_gap_ms=44 stalls=3 stall_ms=1200
\`\`\`

\`audio_stall.txt\`（三对 pre/post）：

| stall | pre rendered_ms | post rendered_ms | Δrendered | post lag_ms | underrun | gap_ms |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 64,874 | 66,069 | **+1,195 ms** | −87 | 0 | 44 |
| 1 | 76,032 | 77,226 | **+1,194 ms** | −95 | 0 | 44 |
| 2 | 87,210 | 88,405 | **+1,195 ms** | −91 | 0 | 44 |

- \`lag_ms ≈ −100\`：音频与游戏状态基本同步（对照 P27 ring 路径应 ≈ +3,000）。
- 每次 1.2 s 主线程停顿期间，音频线程仍渲染了 ≈1,195 ms 的 PCM，\`underrun=0\`、refill gap 44 ms —— 说明「长帧不断音」仍然成立。
- async 回归：\`enabled=1 hb=120000 stage=0 cpu=1 wdt=1 main=7488 stalled=0\`，\`frame=7500 status=0 async=1\`，无 \`last_error\`。
- 画面回归：标题、读档列表、正文两处台词截图均正常（t2「映入眼瞳的是一位半透明的女孩。二阶堂真红。」、t3 后续场景），60 FPS。

证据目录：\`docs/milestones/evidence/P30a-audio-jit/\`。

## 6. 真机验收点（v1.1.6-test）

1. 安装 \`E:/galnx-build/p30/out/IROSEKA_FHD-010047420000a000-v1.1.6-test.nsp\`（同 TitleID 覆盖，用户手动 MTP）。
2. 正常游玩 5–10 分钟：BGM/语音应在触发后立刻听到（不应再有约 3 秒滞后）；场景切换、点击推进后音效不拖尾。
3. 观察 \`sdmc:/switch/rfvp/audio_status.txt\`：\`mode=jit\`、\`lag_ms\` 在 ±300 ms 内、\`underrun=0\`；长帧瞬间不应出现 \`underrun\` 增长。
4. 可选：\`debug.txt\` 写 \`stall=1200\` + \`stall_at=1500\` 做一次对照，\`audio_stall.txt\` 应出现 pre/post 且 rendered_ms 在停顿期间推进 ≈1200 ms。
5. 回归项：CG/差分显示、UI 开合无残留、存档/读档、\`-\` 退出、async 不冻结。

回退：装回 v1.0.9（\`E:/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp\` 9,979,495,640 B sha256 \`726bb2d1…\`）；源码回退为撤销 \`rfvp-audio-jit.patch\`。

## 7. 已知限制

- 音频线程首次 apply \`load_encoded\`/\`load_stream\` 时会解码音频（Ogg/Vorbis），若单条解码超过一个 buffer，可能产生一次轻微 gap（当前记录 \`max_refill_gap_ms=44\`，未触发 underrun）。后续可把「解码」与「混音」再拆开（解码线程 + ring）。
- 混音与分配现在发生在音频线程（\`Vec\`/\`Box\` 分配）；devkitPro newlib 的多线程 malloc 与 async 解码线程已并存多个版本，暂未观察到堆问题，真机仍需观察。
- \`audio_status.txt\` 每 600 帧才刷新一次，紧邻事件可能滞后 ≤10 s。
- 低延迟不等于无卡顿：vfs/解码造成的**画面**长帧依旧存在（P24/P26 另立项），但音频不再随之停摆。

## 8. 复现

\`\`\`bash
# 构建 + NSP
bash /e/galnx-build/p30/build-115.sh
bash /e/galnx-build/p30/build-nsp-115.sh
# Citron 验��（音频 + 三次注入长帧）
bash /e/galnx-build/p30/run-lead-audio-jit.sh
\`\`\`

## 9. 教训

- 预渲染抗卡顿与低延迟是同一根轴的两端：想同时要，就必须把「渲染时刻」移到消费侧（JIT），而不是把渲染结果囤在中间。
- 验收指标要写进运行时状态文件（\`lag_ms\`），否则「延迟」这种体感问题只能靠人耳主观判断，容易在模拟器上漏掉。
- 本轮构建再次踩到 git-bash 与 MSYS2 的路径差异（\`/d/Scoop\` 被 rustc 解释成 \`E:\\d\\Scoop\`），以及 \`build_switch.sh\` 的 CRLF；这两点已写进脚本注释，后续不再重复。
