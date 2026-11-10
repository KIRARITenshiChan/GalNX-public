# 第一轮工具链审计：分集群原始资料

- **审计日期**：2026-10-29
- **方式**：纯只读审计（未安装 devkitPro、未构建、未克隆大仓库、未下载/运行任何上游 release 二进制、未读取任何密钥内容、未接触商业游戏数据）
- **执行**：Lead（本机取证 + 合并 + 交叉核验）+ 4 个审计 agent（audit-switch / audit-engines / audit-web / audit-package）
- **上游依据**：`docs/PLAN_DRAFT_v0.1.md` §7（仓库索引）与 §14 第 1–4 项
- **合并结论**：`docs/TOOLCHAIN_AUDIT.md`（主报告；本目录只放分集群原始资料）
- **补充审计（同日）**：`04-renpy-official.md`（Ren'Py 官方源码独立移植可行性专项，独立于 A–D 四集群合并数据）
- **联网复核（v1.3，同日夜间）**：`05-toolchain-refresh.md`（工具链是否落后 + CMake 空格路径实测）、`06-engines-refresh.md`（引擎路线复核与新增候选）、`07-web-citron.md`（Citron Neo 审计 + Web 冒烟 v2）、`08-packaging-refresh.md`（打包链/测试后端复核 + keys 合规策略）；对应实验记录 `docs/experiments/web-02-citron-smoke.md`

## 1. 文件索引

| 文件 | 集群 | 记录数 | 字节 | 行数 | 覆盖对象 |
| --- | --- | --- | --- | --- | --- |
| [`00-switch-base.md`](00-switch-base.md) | A · Switch 基础工具链 | 6 | 49,854 | 456 | devkitPro 安装器/包体系、`devkitPro/pacman-packages`、`switchbrew/libnx`、`Atmosphere-NX/Atmosphere`、`switchbrew/nx-hbloader`、`switchbrew/switch-tools`（nxlink） |
| [`01-engines.md`](01-engines.md) | B · Galgame 引擎移植 | 5 | 60,829 | 356 | `DrFlyingPig/krkr-ns`、`jvrcruzGAMES/RenpySwitch`、`Otorhin/Ren2Switch`、`clamintus/onscripter-nx`、`xmoezzz/rfvp` |
| [`02-web.md`](02-web.md) | C · Web / JS 运行时 | 7 | 76,061 | 535 | `natureglass/Brewser`、`natureglass/nx.js_extended`、`ETCHDEV/BurialNX`、`TooTallNate/nx.js`、§7.7 旁支 3 项（rexglue / XenonRecomp / XenosRecomp） |
| [`03-packaging-testing.md`](03-packaging-testing.md) | D · NSP 打包与测试环境 | 9 | 101,438 | 649 | `rlaphoenix/NTON`、`rlaphoenix/hacBrewPack`、`jakcron/nstool`、`TooTallNate/switch-nsp-forwarder`、`autorunhq/autorun`、`autorunhq/autorun-horizon-dlls`、`carafe-nx/carafe`、`switchbrew/switch-tools`（nxlink 重复引用）、Ryujinx 源流 |
| [`04-renpy-official.md`](04-renpy-official.md) | B+ · Ren'Py 官方源码专项（补充审计） | 7 | 84,638 | 599 | `renpy/renpy`、`renpy/renpy-build`、`jvrcruzGAMES/NXPython`、`jvrcruzGAMES/RenpySwitch`、`knautilus/RenpySwitch`、`Otorhin/Ren2Switch`、`uyjulian/renpy-switch`；含专项 A–G（构建依赖/平台抽象层、社区血统对照、C1–C10 断点、路线 a–d、前置条件、PoC 步骤、测试资源候选） |
| [`05-toolchain-refresh.md`](05-toolchain-refresh.md) | F · 工具链刷新复核 | 8 | 42,541 | 523 | devkitPro installer / pacman-packages / buildscripts / devkitPro-pacman、`switchbrew/libnx`、`Atmosphere-NX/Atmosphere`、`switchbrew/nx-hbmenu`、`switchbrew/nx-hbloader`；含 `pacman -Sy`+`pacman -Si` 全量 1088 条与本机 212 包对照（17/17 最新）、CMake 空格路径实测 |
| [`06-engines-refresh.md`](06-engines-refresh.md) | G · 引擎路线刷新 | 14 | 100,399 B | 768 | krkrsdl2 上游（重大更正：官方 Switch 目标与 CI）、krkr-ns 复核、Kirikiroid2-NX、ONScripter-jh-Switch、ONScripter-NX 复核、rfvp 复核、siglus_rs、renpy/renpy+renpy-build 复核、4 个社区 Ren'Py 移植与 NXPython 许可证复核 |
| [`07-web-citron.md`](07-web-citron.md) | H · Web/Citron 测试后端 | 7 | 21,104 | 135 | `citron-neo/emulator`（GPL-3.0-or-later，HEAD `c3aa70f8`，release tag `2026-04-27` 但资产来自 nightly `0237a9b88`）、Brewser v0.1.131 复核、Web 冒烟 v2（**2/2 通过**）；对应实验 `docs/experiments/web-02-citron-smoke.md` |
| [`08-packaging-refresh.md`](08-packaging-refresh.md) | I · 打包链与测试后端刷新 | 12 | 85,064 | 809 | NTON / hacBrewPack / nstool / switch-nsp-forwarder / Carafe / Autorun / switch-tools 复核（**零变化**）、nx-hbmenu / nx-hbloader / DBI / hb-appstore / Citron 新增登记；含 keys 合规策略、NSP 自包含契约、M3 前置与版本锁定表 |
| [`audit_merged.json`](audit_merged.json) | A–D 合并 | 27 | 91,044 | — | 上述 27 条记录的机读合并（22 字段 + 内部 `_cluster` 标记）；**不含 `04-renpy-official.md` 的 7 条**（补充审计，按需另行合并），也不含 05–08 复核记录 |

`audit_merged.json` 的 `meta` 记录生成日期、来源文件、条数与集群分布；`meta.normalization_notes` 记录 4 条规范化处理（见 §3）。主报告的 §3 总览表、§4 分集群表、§10.1 附录、§10.2 元数据快照均由这份 JSON + Lead 的 GitHub API 快照生成。

## 2. 各集群结论提要

### A · Switch 基础工具链

- **M0 第一阻塞**：`pkg.devkitpro.org`（`dkp-libs.db` 与包目录）实测 HTTP 403（Cloudflare），`switch-dev` 包组成员、版本与哈希暂不可取证。
- 官方 Windows 安装器 v3.0.3 是 2018-06-03 产物（内置 MSYS2 2.10.0），下载资产实测可达，**今日能否完成安装待实测**（详见主报告 §8 的三条路径与验收命令）。
- devkitPro 包库为滚动 latest、无官方 snapshot；锁定手段 = `pacman -Q` 快照 + `pacman -Sw` 包缓存 + Docker digest + 上游源码 tag。
- 已核实源码版本：`libnx v4.12.0 = 7644c9b2…`（ISC）、`Atmosphère 1.12.1 = 6b0c077b…`（GPL-2.0，仅真机测试环境）、`switchbrew/nx-hbloader v2.4.5 = 82b95122…`（ISC，原 `Atmosphere-NX/nx-hbloader` 链接已 404）、`switchbrew/switch-tools v1.13.1 = 22756068…`（ISC，nxlink 所属）。

### B · Galgame 引擎移植

- **第一款原型首选 `DrFlyingPig/krkr-ns`**（MIT，HEAD `949faf9a…`，活跃）；但 `v0.1.0` tag 被移动到 HEAD，**发布 NRO 不可按 tag 溯源**；构建需 devkitPro + CMake 3.31.6 + 自建 FFmpeg 7.1 + 仓库外 toolchain 文件，无 CI。
- **Ren'Py 路线法律硬阻塞**：`jvrcruzGAMES/RenpySwitch`、`Otorhin/Ren2Switch` 均无 LICENSE（后者 2023-09 停更、父仓库已 archived）→ 取得书面授权前不得接入。
- `clamintus/ONScripter-NX`（GPL-2.0-or-later，`v0.3.1 = a8439a86…`）为第二候选；其 release 附带商业游戏数据（tsukihime/kagetsu_tohya），GalNX 不得复用。
- `xmoezzz/rfvp`（MPL-2.0，`0.7.0 = 99435f22…`）README 明确 Switch 从未真机运行、releases 无 NRO → 研究项，不排期。

### B+ · Ren'Py 官方源码独立移植（补充审计）

- **社区移植全部无许可证**：`jvrcruzGAMES/RenpySwitch` / `knautilus/RenpySwitch` / `Otorhin/Ren2Switch` / `uyjulian/renpy-switch`（已 archived）/ `NXPython` 均无 LICENSE → 只作技术差异参考，**禁止复制代码**。
- **官方源码路线**：`renpy/renpy` 基线锁 `8.5.3.26051504 = 39895c1e…`（2026-05-16，仍 SDL2；master 已迁 SDL3，不可当起点）；`renpy-build` 同 tag `7bfab40c…` 锁 Python 3.12.8 / FFmpeg 4.3.1 / SDL2 2.0.20。
- **许可**：两仓库均无根 LICENSE，许可只在 `sphinx/source/license.rst`：主体 MIT + 明确 LGPL 条款（FFmpeg/Fribidi 等组件）+ MPL-2.0/Apache-2.0/BSD/Zlib/Python License。
- **技术结论**：官方无 Switch 平台（`build.py`/`librenpython.c`/README 均确认不支持 cross-compiling）；唯一硬阻塞 = CPython 3.12.8 交叉到 devkitA64/newlib；建议 4–6 周 go/no-go 探针，3–5 人月最小可跑、6–12 人月可发布；并行备选 Switchroot Android + 官方 Android 构建。

### C · Web / JS 运行时

- **M4 首选 `natureglass/Brewser`**（MPL-2.0；tag `v0.1.1.31 = 8040580e…`，与 release 资产 `brewser.nro` 76,546,123 B / sha256 `8ce31f5b…` 对应）；默认 `make` 只需 node/npm/python。
- 风险：私有 `@switch-web/runtime` 与 `brewser-runtime-v8` 源码不可得（npm/GitHub 404），V8/Skia 版本只能从分支构建脚本推断，属「黑盒运行时」；DOM/CSS/WebGL 覆盖率为官方自称、未实测；RPG Maker MV / TyranoScript 需要 Node/fs 兼容层，不能直接跑。
- `natureglass/nx.js_extended`（MIT，上游 fork）引擎链重、源码不完整；`ETCHDEV/BurialNX` 为 AGPL-3.0 且明确「仅支持特定游戏」，只可参考设计、禁止引码。
- 补录真实上游 `TooTallNate/nx.js`（MIT，`v1.0.0-beta.7 = a649611a…`）；§7.7 的 rexglue / XenonRecomp / XenosRecomp 仅一行状态登记（read-only）。

### D · NSP 打包与测试环境

- **路线判定**：forwarder（NTON，GPL-3.0，`v3.0.1 = c5d543a9…`）只解决启动器，NRO 仍在 SD 卡、路径硬编码，README 明确提示可能导致主机封禁；**GalNX 主方向改为自包含 NSP**（`nstool` 校验 + `hacBrewPack v3.05 = 745b16ec…` 子进程打包 + 自研编排，参考 Carafe 流程但不复制 GPL 代码）。
- 自包含打包需要用户自备 `prod.keys`（GalNX 不得分发/入库）、CFW + sigpatches；`hacBrewPack` 已停更（代码 2019）、RSA-PSS 随机盐导致产物非确定性，需额外处理可复现性。
- `carafe-nx/carafe`（GPL-3.0-or-later）与 `autorunhq/*`（许可证逐组件声明）只作流程/架构参考，禁止合并代码；`jakcron/nstool v1.9.2 = e89ea84b…`（MIT）为必装校验工具。
- 测试环境固定：Ryujinx Canary 1.3.265 本机二进制与源码归档自洽，但外部独立溯源未完成（详见主报告 §5）。

## 3. 机读数据契约（galnx-audit JSON）

每个分集群文件末尾都有一个 ```galnx-audit 围栏包裹的 JSON 数组（数组元素即记录）。字段固定 22 个：

`name`、`url`、`default_branch`、`head_sha`、`head_date`、`pinned`、`license_spdx`、`license_file`、`license_notes`、`archived`、`last_push`、`stars`、`open_issues`、`build_system`、`build_deps`、`readme_claims`、`readme_claim_url`、`risks`、`verification_level`、`verification_failures`、`source_urls`、`audited_at`。

- `verification_level` 仅允许 `read-only`（只读网页/API 观察）与 `source-inspected`（读过仓库源码文件）；`not-verified` 用于明确未完成的结论（如 Ryujinx tag↔commit）。
- `audited_at` 本轮统一为 `2026-10-29`；`head_sha` 为 40 位 hex（Ryujinx 源流条以归档 7z 注释的 commit 为准，另附说明字段）。
- 合并规范化（记入 `audit_merged.json` 的 `meta.normalization_notes`）：① 空 `license_spdx` → `NOASSERTION`，原文理由保留在 `license_notes`；② 空 `archived` → `false`；③ Ryujinx 条 `url`/`head_sha`/`head_date` 归一（`head_date` 为归档内部 mtime，非提交日期）；④ `stars`/`open_issues` 在合并报告中以 Lead 的 GitHub API 快照（主报告 §10.2）为准。
- `switchbrew/switch-tools` 在 A（nxlink 用法）与 D（打包日志通道）各出现一次，共 27 条记录 / 26 个唯一对象；主报告总览表按对象去重。

## 4. 校验规则（本轮使用的自检）

1. 4 个文件均含且仅含一个 `galnx-audit` 围栏，围栏内 JSON 可被 `python -m json.tool` / `JSON.parse` 解析；
2. 每条记录 22 字段齐全，`head_sha` 为 40 位 hex（Ryujinx 例外见上），日期为 `YYYY-MM-DD`，`audited_at = 2026-10-29`；
3. 集群记录数为 A=6、B=5、C=7、D=9，合计 27；
4. URL 规范性：GitHub 仓库形如 `https://github.com/<owner>/<repo>`，无 404/迁移链接（已知迁移已写进主报告 §6 的 I-01/I-02/I-03）。

校验脚本（`validate_audit.py`）与抓取缓存放在本地 `.cache/`，按约定不入库；规则如上，复查时可直接用一段 Python/Node 脚本重放。

## 5. 约定与边界

- 本目录是**只读审计快照**：README 声称一律不视为已验证，证据等级以 `verification_level` 为准。
- 不保存、不引用任何商业游戏数据、密钥/固件内容或 ROM；涉及密钥只写机制与路径，不写值。
- 下一轮审计请另建文件（例如 `docs/audit/<日期>-<主题>.md`）并同步更新本索引，不要就地覆盖本轮记录；结论变化请改主报告并留修订记录。
- 补充审计文件（如 `04-renpy-official.md`）同样使用 `galnx-audit` 围栏 + 22 字段契约，但不进入 `audit_merged.json`（该文件固定为第一轮 A–D 的 27 条合并快照）。
