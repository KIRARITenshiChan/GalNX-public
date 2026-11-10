# M4-c 运行验证证据说明（ONScripter-NX）

- 归属任务：task-24（M4-c ONScripter-NX 评估）
- 主文档：[`docs/builds/007-onscripter-nx.md`](../../builds/007-onscripter-nx.md)（§10.3 实测结果 / §13 结论 / §14 未验证 / §15 证据）
- 执行日期：2026-10-30（Asia/Shanghai）
- 被测产物：`m4-ons-with-content.nro`（10,449,140 B，sha256 `d8f9bb116e11c25b0850890202e4c4e7de0e21f830c212f40ce6d54c527f828d`），源码 HEAD `a8439a86393f74c503d28df176f010ca544af56f`
- 被测内容：自建合法内容包（`0.txt` / `bg.png` / 空 `arc.nsa`，自有版权，无第三方素材），打包进 RomFS，见 [`M4c-build-20261030/content-manifest.json`](M4c-build-20261030/content-manifest.json)
- 运行环境：Citron Nightly `0237a9b88`（Kirikiroid SDL2 64-bit，Windows），harness `scripts/citron_run.sh`；每个 run 的 preflight 均确认 0 个 citron 实例；写入仅为 NRO 静态注入（`postmessage`）

## 目录一览

| 目录 | 内容 | 大小 |
| --- | --- | --- |
| `M4c-build-20261030/` | 构建证据：全量/增量构建脚本与日志、环境版本、产物哈希、`nstool` 结构（`nro-structure.json`）、自建内容包与其清单、依赖安装脚本 | 12 项 / 109,412 B |
| `M4c-run-startup/` | R1 启动：`result.json`、`run.log`、`window.png` | 3 文件 / 299,062 B |
| `M4c-run-advance/` | R2 推进：`result.json`、`run.log`、`window-after-input.png` | 3 文件 / 370,071 B |
| `M4c-run-branch-b/` | R3 Branch B：同上三件 | 3 文件 / 254,668 B |
| `M4c-run-branch-right/` | R4b RIGHT 尝试：同上三件 | 3 文件 / 254,670 B |
| `M4c-run-branch-a/` | R5 Branch A：同上三件 | 3 文件 / 254,899 B |

说明：为控制仓库体积，每个 run 目录只保留 `result.json` + `run.log` + **1 张关键截图**；完整 harness 原始 run（含前后两张截图、诊断信息）仍在工作区 `workspaces/citron-harness/runs/<RUN_ID>/`（未入审计证据目录）。

## run 一览

| run | 目录 | run id | PID | 注入 keys（VK） | 截图 diff | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| R1 启动 | `M4c-run-startup` | `20261030-025835-m4-ons-with-content` | 38860 | 无（`injected=false`） | —（仅 nonblack 0.723） | 启动成功；画面显示 `GALNX M4-c minimal test / Self-authored content only. / Press A or click to advance.`，自绘背景 + 左右 4:3 黑边 |
| R2 推进 | `M4c-run-advance` | `20261030-025913-m4-ons-with-content` | 30836 | `C,C`（67,67） | 0.01296 | 翻到第 2 页并出现 `Branch A / Branch B` 选项 |
| R3 Branch B | `M4c-run-branch-b` | `20261030-030021-m4-ons-with-content` | 2464 | `C,C,LEFT,C`（67,67,37,67） | 0.021765 | 显示 `You picked Branch B. / Input mapping works.` |
| R4a 负结果 | （无独立目录，见 harness runs） | `20261030-030112-m4-ons-with-content` | 38264 | `C,C,C`（67,67,67） | 0.01296 | after 截图与 R2 **逐字节相同** → 不按方向键时 RETURN 不确认选项，停在第 2 页 |
| R4b RIGHT | `M4c-run-branch-right` | `20261030-030210-m4-ons-with-content` | 15776 | `C,C,RIGHT,C`（67,67,39,67） | 0.021765 | after 截图与 R3 **逐字节相同** → RIGHT×1 同样落 Branch B |
| R5 Branch A | `M4c-run-branch-a` | `20261030-030317-m4-ons-with-content` | 37280 | `C,C,LEFT,LEFT,C`（67,67,37,37,67） | 0.02167 | 显示 `You picked Branch A. / Input mapping works.` |

关系：R2 为 R3/R4/R5 的共同前置（推进到选项页）；R4a 为负对照；R4b 与 R3 同结果，说明光标从「无选中」态出发时 RIGHT 与 LEFT 各一次均落到第 2 项（Branch B），LEFT 两次才到 Branch A（选项光标语义未在源码层逐行确认，见 007 §14 U9）。

## 关键截图 SHA-256

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `M4c-run-startup/window.png` | 295,984 | `95807c3200c7fe6d…`（全文见下） |
| `M4c-run-advance/window-after-input.png` | 366,239 | `cd87171c719f5ac9091df98abcd020c950f006adac851ab611c21772be1cd092` |
| `M4c-run-branch-b/window-after-input.png` | 250,831 | `84aabcdc5666beb1…`（与 `M4c-run-branch-right` 同名截图**完全一致**） |
| `M4c-run-branch-right/window-after-input.png` | 250,831 | 同上 `84aabcdc5666beb1…` |
| `M4c-run-branch-a/window-after-input.png` | 251,059 | `ce48269f1139963d27b79d08e7b73cb53f465e80326109de24593638dce7e351` |

（表格中省略号处为便于阅读截断；判定依据以 `result.json` 的 `diff_ratio` 与截图逐字节比对为准。）

## 复现单次 run

```bash
cd "E:/Othergames/Nintendo Switch/Workspace/GalNX"
export CITRON_USER_DIR=/c/Users/ACETaffy/AppData/Roaming/citron
bash scripts/citron_run.sh --nro /e/galnx-build/m4-ons/out/m4-ons-with-content.nro \
  --expect-title 'ONScripter-NX' --input-keys C,C --input-delay 3000 --input-gap 1500 --input-settle 2500 --keep
```

- 分支验证：`--input-keys C,C,LEFT,C` → Branch B；`--input-keys C,C,LEFT,LEFT,C` → Branch A。
- 首帧门控：`--input-delay` 需 ≥2500 ms，否则注入落在首帧之前无效（M2-c 已实测）。
- 运行前须确认无 citron 进程（harness 的 preflight 会检查；不要并发跑）。

## 结论

- Citron 上**启动、文字推进、两项分支选择均可工作**；A/B 键映射未涉及（本内容包只用 click/RETURN 推进与方向键选项）。
- 未覆盖：KAG 式右键菜单/存档 UI（R6 未执行，见 007 §14 U10）、音视频、CJK 字体、HD 内容、真机、触屏注入。

Open questions: 真机行为与 HD 内容性能（007 §14 U1/U7）；选项光标在 3 项以上菜单的语义（U9）。
