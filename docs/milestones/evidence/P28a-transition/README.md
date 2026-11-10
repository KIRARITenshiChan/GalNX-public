# P28a：过渡动画 mask 快照修复证据（rfvp v1.1.4-test）

日期：2026-11-06/07 · 任务：task-56（P28）· 执行：audit-engines（Citron/CPU harness），Lead 复核

## 1. 缺陷与根因
- 真机/模拟器现象：场景切换（IROSEKA 序幕→第一章等）没有过渡动画，直接硬切。
- hcb 反编译（`/e/galnx-build/m5-rfvp-run/game/iroseka.hcb`，4,275,282 B）确认转场 100% 使用 Dissolve 家族（Dissolve 2、DissolveWait 16；无 rule/trans 类转场）。
- rfvp 已实现 `other_anm.rs` 的 MaskFadeInOut/FadeIn/ColoredFadeOut/In，std 渲染路径 `app.rs` 会把上一帧作为 mask 快照传入；**no_std（Switch）路径 `no_std_core.rs` 的 render_game_frame 没有接线**，`mask_dissolve.rs` 的 nosnap 分支直接「没有上一帧就立刻显示新场景」→ 硬切。
- 修复：`no_std_core.rs` +17 行（render_motion_to_host 前 capture_thumbnail → set_mask_snapshot，条件 mask_frame_wants_snapshot）+ `prim_commands.rs` +12 行转发 + 版本 1.1.4-test；共 4 文件 +31/−2。
- 补丁：`docs/builds/patches/rfvp-switch/rfvp-transition.patch` 3,178 B / 76 行 / sha256 b9717fea74a1c46e4ca2e42e22433b15d015d851bccb45aeb2dd58bae21a7d83。
- 文档：`docs/builds/035-rfvp-transition.md`；实验：`docs/experiments/trans-01-iroseka.md`。

## 2. 证据构成
- `gpu-transition/`（13 PNG）：Citron GPU 路径（v114 NRO）抓到的过渡中间帧——白场转场 4–5 帧淡出/淡入、CG 切换的双重曝光中间态。
- `cpu-harness/`（12 PNG）：P28 自建 CPU 渲染 harness 对照。修复前 `run4_frame_01061` 的 MaskFadeInOut 之后从 01062 起纯白 255/std=0 持续 114+ 帧（硬切）；修复后 `run5` mask_build=1（graph/diss00 1920x1080）、mask_phase 508→215 共 188 帧灰度渐变。
- `SHA256SUMS.txt`：上游导出的原始清单；`SHA256SUMS.verify.txt`：本目录 26 个 PNG 的复核清单。

## 3. 结论与限制
- 结论：no_std 渲染路径已能把上一帧当 mask 快照，Dissolve 系列转场在 Citron GPU 与 CPU harness 两条路径上都产生中间态；P26/P27 行为无回归。
- 限制：Citron 回读时序 ≠ 真机 EGL；每次 mask 转场多一次 8,294,400 B 回读，耗时/内存未在真机测；CPU 中间帧接近均匀灰的空间形态未完全解释；真机验收见 P28b / runbook §13.7。

## 4. 关联
- NSP（与 P26+P27 合并）：`E:/galnx-build/p28/out/IROSEKA_FHD-010047420000a000-v1.1.4-test.nsp` 9,979,503,832 B sha256 444af465aa5250312a9d2d205eb711c67d7c1bbbcf23e8268b4ecd52a9223113
- Lead Citron 冒烟：`docs/milestones/evidence/P28b-lead-smoke/`

## 仓库内证据裁剪

仓库内仅保留白场转场渐变的关键 2 帧（`gpu-transition/r20-1.png` 起始、`r20-3.png` 中间态）+ 全部 CPU harness 小图（<2 KB/张）；完整 GPU 14 张在 `E:/galnx-build/p28/evidence/gpu-transition/`，CPU harness 12 张同源 `cpu-harness/`。
完整原始集合：`E:/galnx-build/p28/evidence`。SHA256SUMS 仅覆盖本目录保留文件。
