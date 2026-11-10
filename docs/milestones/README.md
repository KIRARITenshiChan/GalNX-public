# 里程碑记录规范与索引

本目录记录 GalNX 每一个里程碑的**可复核**过程与结论。规则：每个里程碑一个文件 `M<id>-<slug>.md`，证据分级归档，完成后更新本索引并提交。

## 1. 文件结构（固定模板）

```text
# M1-x <标题>
- 状态：planned | in-progress | done | blocked | partial
- 日期：YYYY-MM-DD（Asia/Shanghai）
- 关联任务：task-N（Team 任务板）
- 上游依据：计划 vX.Y 的对应章节

## 1. 目标与验收标准   （可勾选 checklist，逐条给判定）
## 2. 环境与版本       （工具链、模拟器、依赖包的精确版本）
## 3. 步骤与命令       （可复制粘贴；失败的命令也保留）
## 4. 证据清单         （E1/E2/E3 分级；路径 + SHA-256 + 采集时间）
## 5. 结果与结论       （一句话结论 + 事实展开）
## 6. 未验证与剩余风险 （明确边界，禁含糊）
## 7. 下一步
```

## 2. 证据分级（与审计报告同一套口径）

| 级别 | 含义 | 存放位置 | 是否入库 |
| --- | --- | --- | --- |
| E1 | 命令原始输出 / 日志 / 退出码 | `workspaces/<id>/evidence/` | 否（gitignored），关键片段抄进里程碑文档 |
| E2 | 截图 / 屏摄（GUI 状态） | `workspaces/<id>/evidence/`，关键图复制到 `docs/milestones/evidence/<id>/` | 关键图是 |
| E3 | 哈希 / 文件元数据（大小、mtime、SHA-256） | 里程碑文档表格 | 是 |
| E4 | 源码 / 配置文件的精确片段（行号+内容） | 文档正文，路径写全 | 是 |

原则：**不把原始日志整段塞进仓库**；仓库只留结论、哈希、关键截图和可重放命令。workspaces/ 与 artifacts/ 不进 git（见根 `.gitignore`），但文档必须写明证据在哪个绝对路径、SHA-256 是多少。

## 3. 写入与提交约定

1. 里程碑文档在**验收通过后**更新状态并提交；进行中的内容可先提交为 `in-progress`。
2. 每个里程碑结束必须做一次 git commit（`m<N>: <结论>`）+ push 到私有远端。
3. 涉及模拟器/真机的结论必须带截图与日志双证据；模拟器 ≠ 真机，文档中要写明验证层级（emulator / hardware）。
4. 任何『网站声称』与『本地实测』分开写，禁止把 README 声明当已验证。

## 4. 索引

| 里程碑 | 状态 | 日期 | 要点 | 文档 |
| --- | --- | --- | --- | --- |
| M0 工具链与框架基线 | done | 2026-10-29 | devkitPro 补装完成（switch-dev 14 包）、最小 NRO 构建通过、审计 v1.3 | `docs/TOOLCHAIN_AUDIT.md` / `docs/environment/devkitpro-2026-10-29.md` |
| M1 KiriKiri 原型 + SDL2 地基 | **done（模拟器级）** | 2026-10-30 | krkrsdl2 上游构建 + 4 处 Switch 兼容补丁；Citron 渲染合法 KAG3 demo 标题画面；SDL2 最小 NRO 与 Citron harness 就绪 | [`M1-kirikiri.md`](M1-kirikiri.md) |
| M2 输入层与通用配置 | **done（模拟器级）** | 2026-10-30 | 注入通道打通（鼠标 SendInput、键盘 PostMessage，KAG3 标题→正文 diff 0.494/翻页 0.556）；7 语义动作/4 内置 profile/7 冲突规则；87 pytest+11 subtests（M3-c 后全量 234 passed） | [`M2-input.md`](M2-input.md)（汇总）；[`M2-kag3-input.md`](M2-kag3-input.md)（KAG3 取证） |
| M3 NSP 打包后端 | **done（模拟器级；真机 M3-d 待用户设备）** | 2026-10-30 | M3-a 自包含 NSP 出包链（真实 keys 仅本机离线，不入库）；M3-b Citron 直接引导 `Hello World!`；M3-c 打包数据模型/TitleID 冲突检查/契约校验；M3-e 汇总 | [`M3-nsp.md`](M3-nsp.md) |
| M4 第二种引擎（Web 优先） | **done（模拟器级）** | 2026-10-30 | M4-a 引擎注册表/适配器契约（内置 krkrsdl2/brewser 两适配器 + `engines list|info|plan`，331 passed/60 subtests）；M4-b Brewser Web 端到端（自建 MIT 内容包，title→endingA/B）；M4-c ONScripter-NX 零源码修改构建 + R1–R5（P2 有条件）；M4-d 汇总 | [`M4-second-engine.md`](M4-second-engine.md) |
| M5 FVP / rfvp 评估 | **done（研究级）** | 2026-10-30 | M5-a rfvp Switch target 构建可复现（rfvp.nro 1,372,216 B sha256 4964dda9…）+ Citron R1–R3（渲染 Luax Painter、M=Plus 触发 quit 证明输入链路）+ PC host 2/3；结论=继续研究（P3 研究项）；附 M4-f ONScripter-NX 第 3 内置适配器、M4-g Brewser 存档持久化证伪 | [`M5-fvp.md`](M5-fvp.md)（汇总）；[`008-rfvp-evaluation.md`](../builds/008-rfvp-evaluation.md) |
| M6 批量构建与回归 | **done（CLI 级；GUI 按计划后置）** | 2026-10-30 | M6-a 批量预检 + JSON 报告 + diff/clean；M6-b 真实构建执行/缓存/依赖锁定（`batch build`/`build run`/`batch lock`，401 passed/63 subtests）；M6-c 汇总；GUI 明确后置 | [`M6-batch.md`](M6-batch.md) |

## 5. 里程碑拆解（历史与当前）

| 编号 | 任务 | 验收 | 状态 |
| --- | --- | --- | --- |
| M1-a | 最小 SDL2 应用 → NRO | make/cmake 退出 0；NRO 生成；SHA-256 记录 | ✅ 完成（`m1-sdl2.nro` 6,740,165 B；`002-sdl2-minimal.md`） |
| M1-b | Citron 可复用冒烟脚本 | 任意 NRO 输入 → 启动/截图/日志/JSON 结果 | ✅ 完成（`scripts/citron_run.sh` + `docs/environment/citron-harness.md`） |
| M1-c | krkrsdl2 上游 Switch 构建 | NRO 生成 + 启动到预期状态或定位阻塞 | ✅ 完成（`001` 构建 + `004` 修复版运行） |
| M1-d | Citron 冒烟 m1-sdl2.nro | 截图 + 日志 + 结论 | ✅ 完成（`M1a-*` 证据，窗口 + 60 FPS） |
| M1-e | 首个 KiriKiri 内容跑通（合法 data.xp3） | 画面/脚本/音频至少一项可见 | ✅ 完成（KAG3 demo 标题画面；音频/推进未验证） |

### M2 拆解（当前）

| 编号 | 任务 | 验收 | 状态 |
| --- | --- | --- | --- |
| M2-a | Citron harness 输入注入 + KAG3 推进实证 | 点击/按键注入能改变游戏画面并被像素 diff 量化；文档 + 失败模式 | ✅ 完成（task-16，commit 1e86d36；鼠标 SendInput、键盘 PostMessage；标题→正文 0.494、翻页 0.556；证据 `M2a-*`） |
| M2-b | `src/galnx/input/` 数据模型与测试 | 7 语义动作/内置 profile/冲突检测/CLI/MANIFEST 接入；现有测试不破 | ✅ 完成（task-17，commit 1e86d36；87 passed, 11 subtests；`docs/input/README.md`） |
| M2-c | KAG3 输入语义取证 + Citron 实测 | 文件:行号级语义证据 + 实测结论 | ✅ 完成（task-18；418 行源码取证 + 8 用例实测，含 X 历史负面发现） |
| M2-d | M2 里程碑汇总文档与提交 | 汇总 M2-a/b/c，更新索引，push | ✅ 完成（Lead：`docs/milestones/M2-input.md`） |

### M3 拆解（当前）

| 编号 | 任务 | 验收 | 状态 |
| --- | --- | --- | --- |
| M3-a | 自包含 NSP 出包链（hacBrewPack+nstool） | NRO→NSO/ExeFS+RomFS+control → NSP；nstool 结构校验；两次构建 sha256 非确定性 | ✅ 完成（task-19；NSP `m0-real-build1.nsp` 309,464 B sha256 cb6d061c…；两次构建 sha256 不同；Citron 直接引导见 M3-b） |
| M3-b | harness 直接引导 NSP + Citron 启动验证 | `--game/--nsp` 支持；自包含 NSP 在 Citron 的引导结论 | ✅ 完成（task-20；Citron `-g` 直接加载 NSP，窗口/日志/截图三证，截图 sha256 9a7e729e…；hbl.nsp 作反例 load_failed） |
| M3-c | 打包数据模型/TitleID 冲突/契约校验 | `galnx package plan/check`、pytest、`docs/packaging/README.md` 覆盖 M3 验收 1/2/3/5 | ✅ 完成（task-21；234 passed/51 subtests，docs/packaging/README.md 405 行） |
| M3-d | 真机安装与 HOME 菜单启动 | NS1 真机安装 + HOME 启动截图（M3 验收第 4 条） | ⬜ 待用户设备接入后（模拟器级结论先行） |
| M3-e | M3 里程碑汇总文档与提交 | `M3-nsp.md` 汇总 + 索引 + push | ✅ 完成（Lead：`M3-nsp.md` 定稿 + 索引 + push） |

### M4 拆解（当前）

| 编号 | 任务 | 验收 | 状态 |
| --- | --- | --- | --- |
| M4-a | 引擎注册表 + 适配器契约（krkrsdl2 / brewser） | 第二个适配器不改核心工作流即可接入；引擎/输入/构建配置独立；`galnx engines list\|info\|plan` + schema + tests | ✅ 完成（task-22；331 passed/60 subtests，新增 97 用例；`engines list` 2 适配器、`plan` 8 步 9 checks 0 fail rc=0；`docs/engines/README.md` 200 行） |
| M4-b | Brewser Web 适配器端到端 | brewser.nro + 自建合法 Web VN 内容在 Citron 加载/推进/分支/存档；证据 + `docs/builds/006-*` | ✅ 完成（task-23；Citron loaded/37 s，`Booting game: 01F5905036D20000`；9 次输入 title→endingA/B；页内 localStorage OK、跨 run 落盘未验证；006 261 行） |
| M4-c | ONScripter-NX 构建可行性评估 | 构建命令/依赖/产物（或受阻根因）；成功则自建 NScript 内容 Citron 验证 + `docs/builds/007-*` | ✅ 完成（task-24；零源码修改 20 s 构建；`m4-ons-with-content.nro` 10,449,140 B sha256 `d8f9bb11…`；Citron R1–R5 全通过；结论 P2 有条件；007 349 行） |
| M4-d | M4 里程碑汇总文档与提交 | 汇总 M4-a/b/c，更新索引，commit+push | ✅ 完成（Lead：`docs/milestones/M4-second-engine.md` + 索引 + commit/push） |
| M4-f | ONScripter-NX 登记为第 3 个内置适配器 | 引擎描述符 + `engines list\|info\|plan` 可用；pytest 基线不破 | ✅ 完成（task-27；新增 devkitpro-make 后端；3 适配器、344 passed/63 subtests、`engines plan` 9 checks 0 fail rc=0；docs/engines/README.md 223 行） |
| M4-g | Brewser localStorage 跨 run 持久化实验 | 存档是否落盘 sdmc、能否跨进程重启；源码级根因 + 文档 | ✅ 完成（task-28；**结论：跨 run 不持久化（已证伪）**，页内 setItem OK、重启 SAVE=absent、磁盘无写入；006 §12 + 证据 M4g-*） |

### M5 拆解（当前）

| 编号 | 任务 | 验收 | 状态 |
| --- | --- | --- | --- |
| M5-a | rfvp（Rust FVP）Switch target 评估 | 计划 §10 M5 五条：构建命令/依赖/产物、PC host 验证、渲染/音频/IO/输入/存档后端完成度、experimental 边界、三选一结论 | ✅ 完成（task-26；构建 pin nightly-2026-02-01 + devkitA64 r30，Windows 需 build.rs 补丁；Citron 渲染 17.5 fps、M=Plus→quit；host 2/3；结论继续研究 P3；008 288 行） |
| M5-b | M5 里程碑汇总与提交 | 汇总 M5-a + 收尾 M4-f/M4-g，更新索引，commit+push | ✅ 完成（Lead：`M5-fvp.md` M5-b 五条验收判定 + 结论 P3 + 与正式适配差距 5 条；索引/MANIFEST/计划 v0.7/commit+push） |

### M6 拆解（当前）

| 编号 | 任务 | 验收 | 状态 |
| --- | --- | --- | --- |
| M6-a | 批量预检 + 报告 MVP（`galnx batch`） | 单项目失败不破坏其他；JSON 报告 + diff/clean；退出码 0/2；测试 | ✅ 完成（task-29；`batch run\\|diff\\|clean` + schema + 23 用例；367 passed/63 subtests；实测 3 项目 2 ok 1 fail rc=2、坏项目仅 manifest 阶段 fail、clean 保护生效；docs/batch/README.md） |
| M6-b | 真实批量构建执行与缓存 | `galnx batch build` / `galnx build run`；缓存/依赖锁定/重建/清理；manifest `build.commands` | ✅ 完成（task-30；`batch build`/`build run`/`batch lock`；sha256 缓存 miss→hit、`--rebuild`/`--no-cache`、`--locked` 漂移检测；34 用例，全量 401 passed/63 subtests；证据 `M6b-batch-build.log`/`M6b-batch-build-report.json`） |
| M6-c | M6 里程碑汇总与 GUI 决策 | 汇总 + 计划 v0.8 + push；GUI 明确后置 | ✅ 完成（Lead：`M6-batch.md` §5A 独立复核 + 计划 v0.8 + 提交推送） |
