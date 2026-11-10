# 032 — rfvp async 返工为 prefetch-only（v1.1.1-test）

- 日期：2026-11-05
- 目标：修复 v1.1.0-test 真机出现的「部分 CG 不显示（只剩对话框/UI）」「UI 开合残留旧像素」「OP 跳过」，同时保留 async 解码对加载卡顿的收益。
- 版本：1.1.1-test（nacp 版本号来自 `platform/switch/host/Cargo.toml:3`）
- 分支基线：9f07ade（上游 pre-release）＋ P22 v1.1.0-test 源码副本（worktree 初始提交 6c166f6）
- 构建 worktree：`/e/galnx-build/p25/rfvp-v111`（不污染 m5-rfvp 主树）
- 状态：Citron 级验证通过；真机 4 项验收待 Lead 统一执行。

## 1. 缺陷与根因

### 1.1 现象（真机，见 docs/milestones/evidence/P22d-async-device-fail/README.md）

- 部分 CG 场景不显示：画面只剩对话框/UI；
- 打开/关闭存档、菜单等 UI 后残留旧像素（残留层没有被新状态覆盖或清除）；
- 序幕→第一章的 OP 被跳过；
- 日志中 `graph_load: invalid id : Nil` 共 44 条。

### 1.2 根因（graph.rs 的 async 分支）

v1.1.0-test 的 `crates/rfvp/src/subsystem/components/syscalls/graph.rs` 在 async 分支里：

1. `submit_graph(...)` 把解码任务塞给 worker；
2. **立即 `return Ok(Variant::Nil)`**。

而 rfvp 的渲染树每帧按图层 id 重画：只要该 id 的纹理尚未就绪（或已被重新分配），这一层就**不会被画**，也不会主动清屏/补背景。于是：

- CG 层（大图，必然走 async）在解码完成前几帧不画 → 对话框/UI 还在，背景空白或停在旧内容 → 「CG 不显示」；
- UI 开合时被延迟/重新分配的图层不画 → 旧像素残留；
- 解码完成后结果以 `graph_load_cached` 应用时，如果期间 id 生命周期已经变化，脚本侧看到的是一个「无效 id」→ `invalid id : Nil`。

结论：async 解码本身没有坏，坏在**load 语义被 async 化了**——GraphLoad 必须同步返回一个可用的纹理，异步只能用于「提前准备」，不能用于「延迟交付」。

### 1.3 OP 跳过（独立根因，与 async 无关）

`crates/rfvp/src/subsystem/resources/videoplayer/mod.rs:113-115`：

```rust
#[cfg(any(feature = "no_std", not(any(feature = "native-video", feature = "uefi-native-video"))))]
fn open(request: &MovieRequest<'_>) -> Result<Box<dyn MovieSource>> {
    anyhow::bail!("no movie decoder in this build: {}", request.name)
}
```

Switch no_std 构建没有启用 `native-video`，因此 `movie_play` 的每个候选都失败、返回 Nil，脚本继续往下走 = OP 被跳过。**这不是 async 的回归**，是构建能力缺失。

## 2. 修复设计：prefetch-only

一句话：**async 只预取，load 永不延迟。**

| 位置 | v1.1.0-test | v1.1.1-test |
| --- | --- | --- |
| graph_load | 未命中 → submit → 立即 return Nil | 未命中 → 预取同组伙伴图 → 等预取最多 300ms（命中即用）→ 否则同步 `vfs_load_file` 解码并返回真实纹理 |
| parts_load | 未命中 → submit → 返回「稍后再来」 | 未命中 → 等预取最多 300ms → 否则同步解码，永不延迟 |
| graph_buff/parts_manager snapshot | 未命中 → submit → 该层不更新 | 只保留 prefetch 预热，不再延迟 |
| 队列 | 混合 on-demand 与 prefetch | 按 path 去重；prefetch 入队尾、on-demand 入队头（on-demand 优先） |
| 结果应用 | apply_async_decodes 应用异步 load | 只服务预取缓存，命中后可供后续 load 直接取用 |

关键代码：

- `crates/rfvp/src/subsystem/components/syscalls/graph.rs:1041-1069`：prefetch 伙伴图 `prefetch_graph_siblings`（L1049）→ `async_decode::wait_for_graph(path, 300)`（L1053）→ cache 命中且 `load_graph_cached(...).is_ok()` 时 `refresh_prims` 后 return Nil（L1056-1066）；否则落到 L1070 `vfs_load_file` 同步解码。
- `crates/rfvp/src/subsystem/components/syscalls/parts.rs:45-60`：删除 `Action::Async`；`get_parts` 未命中时 `wait_for_parts(p, 300)`（L49），仍未命中直接 `vfs_load_file` → `Action::Load`（L52/L58）。
- `crates/rfvp/src/subsystem/resources/async_decode.rs`：
  - `KIND_GRAPH_PREFETCH: u8 = 2`（L36）；
  - `push()` 去重 + 队列优先级（L168-172）；
  - `is_pending_any_path()`（L243）供 submit 判重；
  - `submit_graph`/`submit_parts` 保留但引擎已无调用者（L179 注释）。
- `crates/rfvp/src/subsystem/resources/graph_buff.rs:1459` 与 `parts_manager.rs:498`：删除延迟分支，改为 `let _ = async_id;` + 注释（保留末尾 prefetch）。
- `crates/rfvp/src/subsystem/components/syscalls/movie.rs:56-84`：记录最后一个候选的错误，全失败时 `log::warn!("Movie: no playable movie for {path:?}; last error: {}", ...)`，用于真机定位 OP 候选与错误。

## 3. 改动清单

增量：`git diff 6c166f6`，8 files changed, **+87 / −110**（净删 23 行）。

| 文件 | 变化 |
| --- | --- |
| crates/rfvp/src/subsystem/resources/async_decode.rs | 模块改 prefetch-only；push 按 path 去重+队列优先级；is_pending_any_path；submit_* 降级为兼容 API |
| crates/rfvp/src/subsystem/components/syscalls/graph.rs | 删除 submit 后立即 Nil 分支；改为 wait 300ms 预取命中即用，未命中同步解码 |
| crates/rfvp/src/subsystem/components/syscalls/parts.rs | 删除 Action::Async；未命中同步解码 |
| crates/rfvp/src/subsystem/resources/graph_buff.rs | 删除 submit_graph 延迟分支 |
| crates/rfvp/src/subsystem/resources/parts_manager.rs | 删除 submit_parts 延迟分支 |
| crates/rfvp/src/subsystem/components/syscalls/movie.rs | 新增 last_error 与失败 warn（OP 诊断） |
| platform/switch/host/Cargo.toml / Cargo.lock | version 1.1.0-test → 1.1.1-test |

未改 `no_std_core.rs`：apply_async_decodes/watchdog/drain 保留；prefetch-only 下 KIND_GRAPH/KIND_PARTS 分支不再触发，仅 take_done 丢弃预取结果。

## 4. Citron 验证

### 4.1 NRO 常规冒烟（73 步，通过）

- run dir：`E:/galnx-build/p25/run-nro/20261105-214840-rfvp`
- 73/73 步 ok，diff_ratio=0.805511，title_match=true；
- 截图：title → LOAD 列表（DATA_001/005/009 缩略图与日期正常）→ 正文「家庭教师？」→ 逐句推进到「不要」；画面/立绘/背景/文本正常；
- async_status：`enabled=1 hb=189000 stage=0 cpu=1 wdt=1 main=12163 stalled=0`；无 watchdog_status、无 last_error；
- debug_report 头部 `frame 12180: 60.0 fps slowest 17.2ms`。

### 4.2 CG 读取验证（20 步，通过）

- run dir：`E:/galnx-build/p25/run-nro-cg/20261105-215645-rfvp`；20/20 ok；
- Continue → LOAD → DATA_001：`step-08-cg-after-load.png` 为金发女主角完整 CG（真红台词），CG 层+背景+文本全部显示，无缺失；后续 4 次 C 键推进正常（`step-20-cg-adv4.png` 为蓝天白云 CG 场景）。证明存档路径的大图同步解码可正常交付。

### 4.3 prefetch 实测

NRO 冒烟 debug_report 的 `[async]` 行（P25）：

- `prefetch graph_bs/CHR_郰_斶_壞惂暈L_昞忣 1,813,474B decode failed Unexpected texture type: Multi32Bit us=29117 ok=false`
- `prefetch graph_bs/CHR_郰_婎_壞惂暈L_昞忣 3,447,414B fail us=5690`
- `tick seen=1 pending=0` ×2

即：预取失败**不影响主路径**（主路径同步解码成功）；Multi32Bit 类型 prefetch 不支持的已知限制，仅损失预取收益，不会再造成缺失。

### 4.4 NSP 1.1.1-test 长测（主证据，152 步 / 约 10 分钟）

- 测试 NSP：`E:/galnx-build/p25/out/IROSEKA_FHD-010047420000a000-v1.1.1-test.nsp`（内嵌 romfs；测试期间 sdmc 的 game 目录临时改名为 game-long3-hold，跑完已恢复）
- 输入：`/e/galnx-build/p25/steps-nsp-long3.json`（152 步）：标题→Continue→LOAD→DATA_001（大图 CG）→ 3 次推进 → 60 句连续剧情（每 4s 一句，期间截图）→ Plus 打开存档 UI 截图 → 尝试关闭 → 收尾截图。
- run dir：`E:/galnx-build/p25/run-nsp-long3/20261105-224516-IROSEKA_FHD-010047420000a000-v1.1.1-test/`（22:45:16–22:55:25）
- 结果：152/152 步 ok、steps_failed=0、steps_diff_ratio=0.816125，title_match=true，窗口标题含 1.1.1-test；全程无 panic/exception、无 last_error、无 watchdog_status。
- 时长：152 步 duration 合计 462,275ms；剧情段 step 19–138 合计 348,300ms = **5.8 分钟连续剧情**。
- CG 证据：`step-08-f2-cg.png`（金发女主完整 CG + 真红台词）、`step-15-f3-cg-adv.png`（蓝天白云 CG）；剧情证据 `step-56/97/138-f4-story-*.png`。CG 层+立绘+背景+文本全部正常，无缺失。
- UI 证据：`step-141-f5-menu-open.png` 为 Plus 打开的 DATA EDIT 全屏存档 UI，渲染完整、未见旧像素残留；但**关闭动作未闭环**：`step-144-f6-after-exit.png` 仍为 UI（click 1508,180 未命中），`step-147-f7-after-m.png` 与 `step-150-f8-after-c.png` 字节级相同（sha256 09a7b0ff…），均停在「确定要覆盖存档?」对话框。判定为输入坐标未扣除窗口标题栏 ~70px / 键位映射问题（X=B 只取消子对话框），不是应用残留（用像素网格复核：EXIT 标签实际在窗口图 x≈1490–1600、y≈125–158，中心 ≈(1545,140)；旧脚本点击 (1508,180) 落在下方 AS 35–40 图标行）。按 Lead 裁决（23:04）：UI 关闭动作属输入坐标问题而非应用缺陷，且 prefetch-only 已从机制上删除「延迟绘制」路径、UI 残留的原根因不复存在，故不补跑 Citron 探针，由 Lead 在 23:20 后的真机/独立冒烟验收中顺带覆盖（修正点击坐标为 (1545,140)）。
- 逐帧 diff / 残留检查：harness 对 152 张截图平均差异 0.816125（正常画面变化）；UI 打开帧为完整 UI 覆盖、其下方无旧剧情像素透出；UI 关闭帧受上述输入问题阻挡，未作为残留证据。
- async/watchdog 状态（收尾）：`enabled=1 create=0x0 start=0x0 hb=456000 stage=0 cpu=1 wdt=1 main=29812 stalled=0`；`frame_status frame=29835 status=0 async=1`；debug_report 头部 `frame 29820: 60.0 fps over the last 60 frames, slowest frame 17.2 ms`；无 watchdog_status.txt、无 last_error.txt。长跑末段 debug_report ring 仅 4000 行，早期 `[async]` 预取行被挤出；预取实测见 4.3。
- 性能：perf_slow 22 行，帧 1（启动）1788.4ms、帧 4 528.4ms、帧 2367 1070.7ms（vm 690/audio_cmds 282，应为 DATA_001 大图同步解码）、帧 4249 284.3ms、帧 6514 317.8ms、帧 12130 276.3ms，其余 <220ms。即预取未命中的 on-demand 同步解码仍有 100–300ms 级帧峰（与 §6 风险 1 一致），但**没有冻结**。

### 4.5 OP 段

- Citron 长测（152 步）未推进到 OP 段（debug_report 中 `Movie:` 行数为 0），且本构建无 movie decoder，OP 必然被跳过。
- 本次只做了**独立根因定位**（videoplayer no_std bail）与**诊断埋点**（movie.rs warn）；「OP 正常播放」属于新能力开发，不在本次 async 返工范围。
- 真机验证时可用 `Movie: no playable movie for ...` warn 确认为构建能力问题而非 async 回归。

## 5. 真机待验证（4 项）

1. **所有 CG 正常显示**：进入有 CG 的存档（DATA_001）与剧情 CG 段，确认 CG 层完整、不再只剩对话框/UI。
2. **UI 无残留**：反复打开/关闭存档、设置等全屏 UI，确认无旧像素残留。
3. **OP 行为**：序幕→第一章处观察 OP；预期仍跳过（无 decoder），但需确认不再因 async 产生额外异常（查看 `Movie: no playable movie` warn 与 last_error）。
4. **长时游玩不冻结**：async=on 游玩 ≥10 分钟，确认帧心跳递增、无 watchdog stall、无 last_error（沿用 P22 真机心跳取证方法）。

> Citron 已覆盖：①CG 完整（DATA_001 大图 + 剧情 CG）；④async=on 10 分钟不冻结（frame 29835 / hb 456000 / cpu=1 / wdt=1 / stalled=0 / 无 watchdog_status）。
> Citron 未闭环：②UI **关闭**动作（输入坐标/键位问题，UI 打开渲染已验证无残留）——按 Lead 裁决由 Lead 真机/独立冒烟覆盖，修正坐标为 (1545,140)；③OP（构建无 decoder，仅定位根因）。

取证用文件（sdmc:/switch/rfvp/）：`async_status.txt`（enabled=1 / hb 递增 / stage=0 / cpu=1 / wdt=1 / stalled=0）、`frame_status.txt`、`debug_report.txt`（`[async]` 预取行、movie warn）、`last_error.txt` 应不存在。

## 6. 风险与回退

- **风险 1**：load 路径改成同步解码后，个别超大 CG 会让该帧耗时回到 100–600ms 级（P22 真机 async 解码实测 182–590ms）。这是「正确性优先于卡顿」的有意取舍；预取命中时可抵消大部分。
- **风险 2**：`wait_for_graph/wait_for_parts` 最长 300ms 的有界等待，最坏情况让 load 帧多等最多 300ms——但比出一张空 CG 更可接受；且只在有同 path 预取在飞时发生。
- **风险 3**：prefetch 对 Multi32Bit 等纹理类型仍会失败（只影响预取收益，不影响画面）。
- **回退**：本次改动只涉及 async 的加载语义；回退到 v1.1.0-test 的 async 分支即恢复旧行为（但会重现 CG 缺失）。关闭 async（删 `sdmc:/switch/rfvp/async.txt` 或写非 on）时，所有 load 走同步路径，行为等同旧版默认关闭。

## 7. 产物与校验

| 产物 | 路径 | 大小 | sha256 |
| --- | --- | --- | --- |
| 测试 NSP | E:/galnx-build/p25/out/IROSEKA_FHD-010047420000a000-v1.1.1-test.nsp | 9,979,496,152 | bf83fa6edb0134c60c04756b6c02c21b191b43e3567561e68628962b4ded2e5b |
| NRO | /e/galnx-build/p25/rfvp-v111/target/rfvp-switch/switch/rfvp.nro | 7,929,912 | 08354233918b3492dfa9b939b8b1de37f6782fa807931a0eea04abafb41fe9bd |
| ELF | /e/galnx-build/p25/rfvp-v111/target/rfvp-switch-runtime/rfvp.elf | 17,264,608 | a4243c2405eb591adff4cb0b51423f33f9d18f5ee9b58bffe3b2826d117b1f32 |
| 增量 patch | docs/builds/patches/rfvp-switch/rfvp-async-prefetch.patch | 17,298 | 295ee7252fd2becfb82d3ff755c87df4febf2007ae772794000de57c9babcd05 |
| 全量 diff v1.1.1 | /e/galnx-build/p25/rfvp-full-v111.diff（仓库外暂存） | 212,899 | 4c3cd3b717db94a575d9ab197235de8976dbb32a0109f7571b1c1506245c1429 |
| 证据 | E:/galnx-build/p25/evidence/（nro-story/、nro-cg/、nsp-long3/，含 SHA256SUMS.txt） | — | 见文件 |

## 8. 证据

- NRO 常规冒烟：E:/galnx-build/p25/run-nro/20261105-214840-rfvp/
- NRO CG 验证：E:/galnx-build/p25/run-nro-cg/20261105-215645-rfvp/
- NSP 长测（主证据）：E:/galnx-build/p25/run-nsp-long3/20261105-224516-IROSEKA_FHD-010047420000a000-v1.1.1-test/
- NSP 长测 1（101 步，输入脚本误触存档 UI，仅作「不冻结 / 预取不报错」参考）：E:/galnx-build/p25/run-nsp-long/20261105-221004-IROSEKA_FHD-010047420000a000-v1.1.1-test/
- 汇总拷贝：E:/galnx-build/p25/evidence/（nsp-long3/ 为主证据，含 SHA256SUMS.txt）
- UI 关闭探针：未跑（Citron 22:58–23:20 被 audit-engines 占用做 baseline/test2，单实例不可并行；Lead 裁决不抢档期，UI 关闭交 Lead 真机/独立冒烟覆盖）。

## 9. Lead 独立 Citron 验收（2026-11-05 23:32–23:35）

为确认 async-fix 的结果可独立复现，Lead 用同一 NSP 在 Citron 重跑「读档 → CG → 推进」路线（脚本 `E:/galnx-build/p25/run-lead-v111c.sh`，证据 `docs/milestones/evidence/P25a-async-prefetch-lead-smoke/`）：

| 检查 | 结果 |
| --- | --- |
| 启动/标题 | PASS，窗口 `IROSEKA FHD (64-bit) | 1.1.1-test`，60 FPS |
| 读档列表 | PASS（`step-05-f1-list.png`，1,813,828 B） |
| CG 完整显示 | **PASS**（`step-08-f2-cg.png` sha `68e3eeaa…a1f5`，真红 CG 全幅无缺层） |
| CG 内推进/切场景 | PASS（`step-14-f4.png` sha `f6df85f7…49fd`、`step-26-f8.png` sha `d7b3d185…335e68`，无 UI 残留） |
| async 真正启用 | `async_status.txt`=`enabled=1 create=0x0 start=0x0 hb=105000 stage=0 cpu=1 wdt=1 main=6785 stalled=0` |
| 帧心跳 | `frame_status.txt`=`frame=6840 status=0 async=1` |
| 异常 | 无 `last_error.txt`；35 个输入步骤 0 失败 |

补充说明：
- 23:32–23:34 与 audit-engines 的 baseline 轮存在 Citron 单实例重叠，本轮证据窗口标题/时间戳连续，按有效记录；其影响已在其 030 文档中标注。
- UI「关闭」动作仍无专项点击探针（输入坐标问题，非应用缺陷）；prefetch-only 已删除「不画该层也不清屏」路径，残留根因不复存在，真机复验时按 032 §5 第 2 项确认。

