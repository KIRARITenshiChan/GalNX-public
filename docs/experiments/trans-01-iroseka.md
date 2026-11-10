# trans-01 — IROSEKA 场景转场实验记录（hcb 静态分析 + 无头运行时取证）

- 日期：2026-11-07
- 对象：IROSEKA / 五彩斑斓的世界 HD Re:GENERATION，rfvp 引擎，Switch NRO/NSP
- 目的：定位「真机场景切换全部硬切、看不到过渡动画」的机制，验证修复
- 关联：修复交付见 docs/builds/035-rfvp-transition.md（补丁 docs/builds/patches/rfvp-switch/rfvp-transition.patch）
- 结论先行：原版**双轨**用两种转场：ColoredFadeIn/Out（纯色淡入淡出，黑 22 / 白 255）与 MaskFadeInOut（`graph/diss00`、`graph/diss08` 掩膜溶解）；硬切的根因不是脚本没调用，而是 no_std（Switch）渲染路径缺少「上一帧快照」，掩膜溶解退化为瞬时切换。

## 1. 问题与假设

用户现象：真机 v1.1.2-test 场景切换瞬间完成，无过渡。可能是：

| 假设 | 判定 | 依据 |
| --- | --- | --- |
| H1 脚本没调用转场命令 | 否 | hcb 中有 Dissolve 调用（§2） |
| H2 rfvp 未实现 mask dissolve | 否 | mask_dissolve.rs / gpu_prim / prim_commands 均有实现 |
| H3 mask 资源加载失败被吞 | 否 | 修复后 mask_build 成功，dims 1920×1080 |
| H4 时长/参数解析错误 | 部分 | 存在大量 `Invalid duration`（§5.4），但转场时长参数解析正确 |
| **H5 no_std 路径缺上一帧快照** | **是** | §3/§4 |

## 2. hcb 静态分析（Lead 独立解码 + 本人反汇编复核）

工具：`/e/galnx-build/p23/l10n/hcb_tool.py`（decode/encode，opcode 表来自 rfvp `crates/assembler/src/inst.rs`；`parse_syscalls()` 读 sys_desc 段得 id→名字）。

```
python hcb_tool.py decode /e/galnx-build/m5-rfvp-run/game/iroseka.hcb  # 948,219 条指令
python hcb_tool.py parse_syscalls ...                                  # 148 个 syscall，5,064 次调用
```

统计（**关键**）：

| syscall | 次数 | 用途 |
| --- | --- | --- |
| Dissolve | 2 | mask 溶解起点（带 mask 名 + inout 标志） |
| DissolveWait | 16 | 等待转场结束 |
| Movie | 3 | OP 等视频（no_std 无 native video → P29） |
| rule / trans / 其它转场族 | 0 | 不存在其他转场 API |

本人用自写反汇编脚本（`/e/galnx-build/p28/scripts/{disasm*.py,dump_42ae0.py,callers.py,dump_func.py,list_sys.py}`）复核调用点：

| 函数 | 行为 | 调用点数 |
| --- | --- | --- |
| f_00042AE0 | 算时长 + `Dissolve(duration, Nil)` → **ColoredFadeIn**（默认 650 ms，若干条件分支 40/÷3×2/=1） | — |
| f_00042C92 | 颜色码 → `ColorSet` + `Dissolve(duration, Int)` → **ColoredFadeOut**（id 1/255/250/251/22） | — |
| f_00042AC6(duration, flag) | g23=true + f_00042AE0 + DissolveWait(true) + g23=nil | 49 |
| f_00042B98 | f_00042C92 + DissolveWait + 切 bg prim + color pick | 66 |
| f_00042E14 | 场景切换辅助 | 151 |
| f_00042E9C | 最常用 load/场景切换辅助 | 3,221 |
| f_00035955 | Dissolve 包装 | 3 |

⇒ 原版转场 100% 走 Dissolve 与 DissolveWait 两个 syscall，没有其它转场通道。

## 3. Dissolve 语义（rfvp 源码）

`crates/rfvp/src/subsystem/components/syscalls/other_anm.rs:200-300`：

- 参数 1 duration：必须 Int 1..=300000，否则 log error 并跳过；
- 参数 2：
  - String → `MaskFadeIn` / `MaskFadeInOut`（inout 标志）；
  - Int 1..=255 → `ColoredFadeOut` + `set_dissolve_color_id`；
  - **其它（含 Nil）→ `ColoredFadeIn`，且不设颜色 id（沿用上一次的颜色）**。

`crates/rfvp/src/subsystem/resources/motion_manager/mod.rs:1024 start_dissolve`：`dur.max(1)`；`tick_dissolve` 每帧推进 alpha（ColoredFadeIn/MaskFadeIn: 1-t；ColoredFadeOut: t）；ColoredFadeOut 结束转 Static(1.0) 并持久保留。

⇒ 与 §2 的调用点完全吻合：场景内切换多用 ColoredFadeOut(黑/白) + ColoredFadeIn；大场景切换用 MaskFadeInOut(graph/dissNN)。

## 4. 渲染路径：为什么 Switch 上 mask 退化为硬切

| 路径 | 是否处理 mask 快照 | 位置 |
| --- | --- | --- |
| std / desktop GPU | 有 | `app.rs:968` wants_snapshot → render target 回读 → `:978` set_mask_snapshot |
| soft（CPU 光栅，harness 用） | 有 | `rendering/soft_render/renderer.rs` 内部 set_snapshot |
| **no_std（Switch NRO）** | **无（修复前）** | `no_std_core.rs` 无任何调用 |

`rendering/mask_dissolve.rs:37 prepare()`：MaskFadeIn/InOut 且 serial 不符 → wants_snapshot=true；若 texture 存在但 snapshot 缺失 → nosnap 分支（源码注释 :45）：

> Without the previous frame there is nothing to wipe: the new scene shows at once.

即：**没有上一帧快照 → 直接显示新场景 = 硬切**。这与用户现象一致，也解释了「纯色淡入淡出正常、只有掩膜转场坏」。

## 5. 无头运行时取证（CPU harness）

### 5.1 方法

rfvp 自带 `crates/rfvp/src/no_std_harness.rs`（`#[cfg(all(test, feature="no_std"))]`，由 `lib.rs:1041` 挂载）：在 std 宿主上跑 RfvpCore（与 Switch 同一 no_std 核心代码）+ CPU 软光栅，逐帧输出 PPM。用自加 P28DIAG 打点（仅诊断，不入正式补丁）观察 mask 路径。

```
bash /e/galnx-build/p28/harness-build.sh
bash /e/galnx-build/p28/run-harness.sh <label> <frames> <out_from> <out_to> <out_every> <start_xy>
# 例：bash /e/galnx-build/p28/run-harness.sh run5 1250 1040 1260 4 0.84,0.50
```

起点 0.84,0.50 = 标题画面 New Game 按钮（默认 0.20,0.93 点不中，run1 的教训）。

### 5.2 run4（修复前）

4000 帧，PPM 1035–1176 每 3 帧。ring 计数：`dissolve_call=11`、`start_dissolve=11`、`dissolve_int=4`、`tick_dissolve=1376`、`fade_emit=794`、`mask_prepare=3842`、`mask_nosnap=4000`、**`mask_build=0`**、**`mask_phase=0`**。

转场全程表（帧 / 类型 / 参数）：

| # | 帧 | 调用 | 结果 |
| --- | --- | --- | --- |
| 1 | 2 | Dissolve(1960ms, Nil) | ColoredFadeIn color_id=0（首启无色，透明） |
| 2 | 683 | Dissolve(3960ms, Int 22) | ColoredFadeOut 黑，359 帧 alpha 0.0043→1 |
| 3 | 1042 | Dissolve(1ms, Int 22) | ColoredFadeOut 19 帧 alpha=1 |
| 4 | **1061** | **Dissolve(5410ms, "graph/diss00", inout=true)** | **MaskFadeInOut，mask_build=0，走 nosnap → 硬切** |
| 5 | 1509 | Dissolve(1ms, Int 255) | ColoredFadeOut 白 |
| 6 | 1519 | Dissolve(2910ms, Nil) | ColoredFadeIn 白（沿用上一色 255） |
| 7 | 2349 | Dissolve(1810ms, Int 255) | ColoredFadeOut |
| 8 | 2464 | Dissolve(1360ms, "graph/diss00", inout=true) | MaskFadeInOut，无 fade |
| 9 | 3194 | Dissolve(3910ms, "graph/diss00", inout=true) | MaskFadeInOut，无 fade |
| 10 | 3550 | Dissolve(1160ms, "graph/diss08", inout=true) | MaskFadeInOut，无 fade |
| 11 | 3850 | Dissolve(360ms, "graph/diss00", inout=true) | MaskFadeInOut，无 fade |

视觉：1062 帧起画面**纯白 255、std=0**，持续 114 帧以上。

### 5.3 run5（修复后，1250 帧）

ring 计数：`dissolve_call=4`、`start_dissolve=4`、`tick_dissolve=545`、`fade_emit=495`、`mask_prepare=1109`、**`mask_build=1`**、**`mask_phase=188`**、Mask 类型 nosnap=0。

关键日志原文：

```
[ERROR] P28DIAG mask_build path=graph/diss00 dims=Some((1920, 1080)) snap=true
[ERROR] P28DIAG mask_phase phase=508 hard=false gen=0   ...（188 条，gen 递增）
[ERROR] P28DIAG mask_phase phase=215 hard=false gen=187
```

视觉（PPM 640×360 灰度统计）：1044–1156 黑 → 1160 mean 0.1 → 1164 22.1 → 1168 50.1 → 1176 81.0 → 1200 131.0 → 1240 183.0（std 0.2–1.2）。

⇒ 同一帧 1061 的转场从「1 帧跳到纯白」变成「188 帧连续渐变」；mask 相位连续递减，快照被正确保存和使用。

## 6. GPU（Citron）运行时取证

NRO：v1.1.4-test（`/e/galnx-build/p28/rfvp-v114/target/rfvp-switch/switch/rfvp.nro`，7,938,104 B，sha256 641af84c…）。
方法：`scripts/citron_run.sh --keep` 保持 Citron 进程，用 run 目录自带 `citron_win.ps1 -Mode input/-Mode capture` 逐帧驱动（约 0.7 s/帧，1728×1016）。

路线：标题 → 点 New Game(1378,536) → 黑场 → FAVORITE/FVP logo 白场（点击无效，需按键）→ A×3+ENTER×2 跳过 logo/OP → 序章正文 → 每按一次 C(A) 连拍 4 帧，共 ~70 轮。

观察到（详见 035 §6.2）：白场淡出/淡入 4 帧序列（r20-1..r21-1）、CG 切换重影中间态（r39-1、r68-2）。**v114 在 GPU 路径上转场有多帧中间态**，不再是一帧硬切。

局限：截图间隔 0.7 s、转场 1.8–5.4 s，每段仅 2–5 帧；修复前 NRO 未在同路线抓 GPU 对照（用 run4 CPU 证据 + 用户真机反馈间接支撑）。

## 7. 结论

1. 原版转场由 hcb 脚本显式调用 Dissolve/DissolveWait 驱动，共 26 个调用点函数族；两种形态：纯色淡入淡出、掩膜溶解（graph/diss00、diss08）。
2. 硬切根因 = no_std(Switch) 渲染路径没有在渲染本帧前保存「上一帧快照」，mask_dissolve 的 nosnap 分支直接把新场景显示出来。
3. 修复（035 补丁）= 给 no_std_core 补 17 行快照接线 + prim_commands 两个转发方法；CPU harness 与 Citron GPU 双证据显示转场恢复为多帧过程。
4. 未解释/未验证：CPU 中间帧均匀灰的空间形态、真机时序、每次转场 8.3 MB 回读开销、motion.rs 的 3,968 条 Invalid duration（独立缺陷）。

## 8. 未解释现象与后续

- `[ERROR] Invalid duration`（Citron debug_report 3,968 条，仅 4,006 行）：来自 `subsystem/components/syscalls/motion.rs:76/205/326/470/593/739` 六处，属 Motion 系 syscall 参数解析失败；与转场无关，但可能影响其它动画（转场外的 Motion 播放），建议单独立项。
- 标题后 logo/OP 段白场等待输入（约 60 s），按键可跳过；对应 hcb 的 Movie 3 次调用，属 P29（native video）范围。
- r68-2/r39-1 的重影究竟是 mask 空间图案还是 CG 缩放叠加，需要更高帧率或引擎内截图才能归因。

## 9. 证据路径

- `/e/galnx-build/p28/harness-out/run4/`、`run5/`（PPM + .log + .log.ring）
- `/e/galnx-build/p28/evidence/cpu-harness/`（关键帧 PNG）、`gpu-transition/`（Citron 关键帧 PNG）、`SHA256SUMS`
- `/e/galnx-build/p28/trframes3/`（Citron 全序列截图）、`run-keep/20261107-015413-rfvp/`
- hcb 与脚本：`/e/galnx-build/m5-rfvp-run/game/iroseka.hcb`、`/e/galnx-build/p23/l10n/hcb_tool.py`、`/e/galnx-build/p28/scripts/`
