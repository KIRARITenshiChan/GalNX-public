# M4 第二种引擎（Web 优先）

- 状态：done（模拟器级；真机不涉及本轮验收）
- 日期：2026-10-30（Asia/Shanghai）
- 关联任务：task-22（M4-a，audit-switch）、task-23（M4-b，audit-web）、task-24（M4-c，audit-engines）、task-25（M4-d，Lead）
- 上游依据：计划 v0.6 §10「M4：第二种引擎（优先 Web）」

## 1. 目标与验收标准

计划 v0.6 §10 的 M4 验收只有两条：

| # | 验收标准 | 判定 | 依据 |
| --- | --- | --- | --- |
| 1 | 第二个适配器不需要修改核心工作流即可接入 | ✅ 达成（模拟器级） | `src/galnx/engines/` 统一 `EngineDescriptor`（19 字段）与 `plan_build / verify_artifact / run_spec` 契约；krkrsdl2（原生 NRO / CMake）与 brewser（Web / 预编译 NRO）同时注册为内置适配器，`galnx engines plan` 走同一条计划流水线；manifest 结构未改（仅新增可选 `engine.descriptor`） |
| 2 | 引擎配置、输入配置和构建参数保持独立 | ✅ 达成 | 三份配置分离：引擎描述符 `examples/engines/*.yaml`（id/upstream/target/build backend/artifact 命名/能力）、输入 profile（krkrsdl2 用 `generic-vn`，brewser 用 `kb_mouse`）、构建参数（krkrsdl2 的 CMake toolchain/EMBED_DATA_PATH vs brewser 的预编译产物零构建）；`engines plan` 只做引擎一致性校验（未知适配器=error、blocked=warning），不改写 input/build 语义 |

结论：M4 两条验收在**模拟器级**均达成。第二个引擎接入的成本被压缩为「写一个描述符 YAML（必要时加一个小适配器类）+ 在注册表登记」，CLI/manifest/preflight 核心代码零改动。

## 2. 环境与版本

| 组件 | 版本 / 标识 |
| --- | --- |
| Python | 3.14.x（本机 `python`），PyYAML + jsonschema |
| 测试 | `pytest` → 331 passed, 60 subtests passed in 2.64s（M3 基线 234/51 未破，新增 97 用例） |
| 模拟器（全部运行验证） | Citron Neo nightly `main-0237a9b88`（Windows msvc，Vulkan，firmware 硬编码 22.0.0；zip sha256 `0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb`） |
| Web 运行时（M4-b） | Brewser `v0.1.131`（release tag `v0.1.1.31`），`brewser.nro` 76,546,123 B sha256 `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13`，MPL-2.0 |
| 原生引擎（M4-c） | ONScripter-NX `clamintus/onscripter-nx` HEAD `a8439a86393f74c503d28df176f010ca544af56f`（2026-01-14），GPL-2.0-or-later |
| 构建工具链（M4-c） | devkitPro MSYS2 `D:/devkitPro` + devkitA64 gcc 16.1.0；新增 `switch-smpeg2 2.0.0-1`、`switch-libvorbis 1.3.7-1` |
| harness | `scripts/citron_run.sh`（M3-b 版，支持 `--game/--nro`、输入注入、截图 diff、JSON 结果） |

## 3. 步骤与命令

### 3.1 M4-a：引擎注册表与适配器契约

```bash
cd "E:/Othergames/Nintendo Switch/Workspace/GalNX"
PYTHONPATH=src python -m pytest -q                 # 331 passed, 60 subtests
PYTHONPATH=src python -m galnx engines list --json
PYTHONPATH=src python -m galnx engines info brewser --json
PYTHONPATH=src python -m galnx engines plan --manifest examples/manifest.krkr.yaml
```

`engines list`：2 个内置适配器 —— `krkrsdl2`（ready / nro / cmake-switch / input `krkrsdl2` / MIT）、`brewser`（ready / web / prebuilt / input `kb_mouse` / MPL-2.0）。

### 3.2 M4-b：Brewser Web 端到端（Citron）

```bash
cd "E:/Othergames/Nintendo Switch/Workspace/GalNX"
# 内容包投放到虚拟 SD（%APPDATA%/citron/sdmc）
#   sdmc:/switch/brewser/apps/org.galnx.webvn/{manifest.json,index.html}
#   sdmc:/switch/brewser/configs/config.json -> {"autorunApp":"/apps/org.galnx.webvn/index.html"}
bash scripts/citron_run.sh --game workspaces/web-01/brewser.nro \
  --timeout 150 --settle 30 --expect-title brewser --keep
# 随后在 run 目录内用 citron_win.ps1 注入 9 次点击（标题→SCENE1→SCENE2→SCENE3→ending）
```

### 3.3 M4-c：ONScripter-NX 构建与运行

```bash
git clone https://github.com/clamintus/onscripter-nx /e/galnx-build/m4-ons
# devkitPro MSYS2 内：pacman -S switch-smpeg2 switch-libvorbis；make -j16（ELAPSED_S=20, MAKE_EXIT=0）
# 自建内容 0.txt/bg.png/arc.nsa 放入 romfs 后重打包为 m4-ons-with-content.nro
bash scripts/citron_run.sh --game /e/galnx-build/m4-ons/out/m4-ons-with-content.nro \
  --expect-title ONScripter --input-keys C,C,LEFT,C --input-delay 2500
```

## 4. 证据清单

### 4.1 代码与文档（E3/E4）

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `docs/engines/README.md` | 14,539 B | `e636a842e8ba1a7b3052c01fa59810d82edc5eb33ab82b16329c38c2c8c932fe` |
| `schemas/engine.schema.json` | 5,860 B | `b91761b46b5b3b6ea70ed88ef34684f840a7b4fa4a4b1713ba0a457aa63ab83f` |
| `docs/builds/006-brewser-web-adapter.md` | 21,310 B | `ca4173eda2bcec1a2c191d6b09b8a3fb69ecc6794cd79f844862f77ae93847dd` |
| `docs/builds/007-onscripter-nx.md` | 30,982 B | `50e4effbd603c64c74ffa5d9bd43f7a88fcd8205ad16dbb83b70e27c8d07a600` |
| `examples/web-vn/index.html` | 9,558 B | `a28594ea7c3735be5f4c3df592e861568f7b901c61684faa5190c5e45522feb3` |
| `examples/web-vn/manifest.json` | 506 B | `aca5f494dff67141be252ed0d83e6f692377438025ed1ef823f89593a73084fb` |

### 4.2 M4-b 运行证据（E1/E2，仓库子集）

| 证据 | 说明 | SHA-256 |
| --- | --- | --- |
| `docs/milestones/evidence/M4b-title.png` (171,263 B) | Brewser 加载本地 app 包后的标题页 | `f9b802be3502e88dc40449f8923dc508f05bbe9f8f56a7217d2d51cade57103b` |
| `docs/milestones/evidence/M4b-endingA.png` (177,678 B) | 左半区点击 → `STATE=endingA BRANCH=A` | `7183c12b19a6a2921aa16c610b3d8c5e3632da8b49c9d668865ecc8ea6352ee0` |
| `docs/milestones/evidence/M4b-endingB.png` (176,543 B) | 右半区点击 → `STATE=endingB BRANCH=B` | `d8d012379e69069ecd9b34411c8cfabdd688ddd309aa66d21804d2aba79e5798` |
| `docs/milestones/evidence/M4b-brewser-run.json` (1,774 B) | harness 结果：status=loaded、elapsed 37s、pid 10492 | `00e0d0a0b94633539348e56ce39b872db21eb1f09e9f3035506634a431a449f0` |
| `docs/milestones/evidence/M4b-input-injection.json` (6,134 B) | 9 次点击注入与状态迁移 | `f065d6099aae09cca5c8b71b01a04e9a73f21fc87c5715f6f1695ea4570410bd` |
| `docs/milestones/evidence/M4b-citron-log-slice.txt` (8,306 B) | boot 行 `Booting game: 01F5905036D20000` | `60c0cbd9f31694c43a95be0864a40b87ec0b533854b48dda7329b075a7b48c1c` |
| `docs/milestones/evidence/M4b-artifacts-sha256.txt` | 产物哈希清单 | `82c58ba863d9aea03dd3b7a9419fbadb76df4c7bf3662cc34f6bd4d600a84d65` |

### 4.3 M4-c 构建与运行证据（E1/E2/E3，仓库子集）

| 证据 | 说明 | SHA-256 |
| --- | --- | --- |
| `M4c-build-20261030/` | 全量 clean 构建日志、环境版本、NRO 结构、内容清单 | 见 `M4c-run-README.md` 与各 json |
| `M4c-run-startup/window.png` | R1 启动渲染自建内容 | `95807c3200c7fe6dd73e4877938af7ac37989395cfec27e30dd642f939a944b3` |
| `M4c-run-advance/window-after-input.png` | R2 `C,C` → 第 2 页 + Branch A/B 选项（diff 0.01296） | `cd87171c719f5ac9091df98abcd020c950f006adac851ab611c21772be1cd092` |
| `M4c-run-branch-b/window-after-input.png` | R3 `C,C,LEFT,C` → `You picked Branch B.`（diff 0.021765） | `84aabcdc5666beb19204659aae535fdcacabf939fdeb5bbb57c9255cd4cf33bb` |
| `M4c-run-branch-right/window-after-input.png` | R4b `C,C,RIGHT,C` → 与 R3 逐字节相同（RIGHT 也落 B） | `84aabcdc5666beb19204659aae535fdcacabf939fdeb5bbb57c9255cd4cf33bb` |
| `M4c-run-branch-a/window-after-input.png` | R5 `C,C,LEFT,LEFT,C` → `You picked Branch A.` | `ce48269f1139963d27b79d08e7b73cb53f465e80326109de24593638dce7e351` |
| `M4c-run-README.md` (5,576 B) | 5 个 run 的 run id / PID / keys / diff / 截图哈希 / 复现命令 | `25467e5c6eba988fc6af22986cacefa0f17a8b869fc6afda0eb2007ba4398bc4` |
| `M4c-run-*/result.json` | harness 原始结果（startup `75f1cfa8…` / advance `dab81d43…` / branch-a `4a9402b1…` / branch-b `700324fb…` / branch-right `40795a3f…`） | 见文件 |

## 5. 结果与结论

### 5.1 M4-a 引擎注册表与适配器契约（task-22）

- 交付：`src/galnx/engines/{__init__.py, descriptor.py, registry.py, contract.py}`、`schemas/engine.schema.json`、`examples/engines/{krkrsdl2,brewser}.yaml`、`galnx engines list|info|plan`、`tests/test_engines_*`（97 个新用例）、`docs/engines/README.md` 200 行。
- `EngineDescriptor` 19 字段覆盖：id/name/upstream(commit)/license/status/target(kind=nro|nsp|web)/runtime/build(backend + 参数)/artifact 命名/能力矩阵（render/input/save/audio/video/touch）/默认输入 profile/备注。
- 契约三件：`plan_build()` 产出构建步骤与检查项；`verify_artifact()` 校验产物（NRO/NSO/结构）；`run_spec()` 产出模拟器运行规格（当前固定 Citron，真机 hbmenu 参数待补）。
- 复核命令结果：`engines plan --manifest examples/manifest.krkr.yaml` → 8 步、9 checks、0 fail 0 warn、rc=0；`engine.pinned` = `124bdf841f09e7ce02aa99b7b55791a0f7a900ff`、`artifact` = `krkrsdl2-1.0.nro`、input 来源标注 `source: manifest`。
- 关键设计：引擎差异全部收敛到描述符 + 可选适配器类；`galnx` 的 manifest/preflight/package 核心未因第二引擎而分叉。

### 5.2 M4-b Brewser Web 适配器端到端（task-23）

- Brewser 在 Citron 完整加载：status=loaded、窗口标题 `citron Nightly | 0237a9b88 | brewser (64-bit) | NVIDIA`、boot 行 `Booting game: 01F5905036D20000`、elapsed 37 s。
- 内容包路线（实测）：`sdmc:/switch/brewser/apps/<appId>/{manifest.json,index.html,assets/,localStorage/}` + `configs/config.json` 的 `autorunApp` → 页面以 `brewser://apps/<appId>/index.html` 渲染；不需要 `make sdmc`、不需要 devkitPro。
- 端到端交互：9 次注入点击把 `title → SCENE1 → SCENE2 → SCENE3 → ending`；`STATE` 行与 `SAVE=present` 证明页面状态机与页内 localStorage 正常。
- 分支：整屏左右半区点击 → `endingA/BRANCH=A` 与 `endingB/BRANCH=B`；**DOM `<button>` 精确点击未打通**（事件坐标与 CSS 坐标存在系统偏移，实测 `css = 0.8514*client − 93.9 / −61.0`），结论按「等价用户点击屏幕左右半区」表述。
- 存档阻塞项（M4-g 已收口）：`localStorage` 页内读写 OK，但**跨 run 不持久化已证伪**——kill 后重启 `SAVE=absent`、磁盘无写入文件（006 §12）。M4 存档需引擎侧改造或引擎外存档。

### 5.3 M4-c ONScripter-NX 评估（task-24）

- 构建：零源码修改，devkitPro MSYS2 `make -j16` 全量 clean build 20 s 成功；缺失依赖 `vorbis/vorbisfile.h` 通过安装 `switch-smpeg2 2.0.0-1`、`switch-libvorbis 1.3.7-1` 解决。
- 产物：含自建内容 NRO 10,449,140 B sha256 `d8f9bb116e11c25b0850890202e4c4e7de0e21f830c212f40ce6d54c527f828d`；纯引擎对照 10,437,716 B sha256 `d84e9f4a2842ce47a370b47a890c85d7dcb755228dbb576c521f15c1e9467a1d`；nstool 静态结构校验通过。
- 自建合法内容：`0.txt` 418 B sha256 `c0a9efac…`（标题 + 正文 + `click` 推进 + `select` 两分支）、`bg.png` 10,854 B sha256 `17e0cd7b…`（node 程序化生成）、`arc.nsa` 0 B（仅过 `switch_check_files()` 门禁）。
- Citron 运行 R1–R5 全通过：R1 启动渲染；R2 `C,C` 推进并显示 Branch A/B 选项；R3 `C,C,LEFT,C` → Branch B；R4b `C,C,RIGHT,C` → 与 R3 逐字节相同；R5 `C,C,LEFT,LEFT,C` → Branch A。负结果 R4a：`C,C,C` 与 R2 截图逐字节相同 → **无方向键时 RETURN 不确认选项**（光标需先由方向键定位）。
- 结论：**正式适配候选（P2，有条件）**——构建门槛最低一档、原生 NScripter 老游戏生态位，但需 GalNX 自建启动器/多游戏管理与菜单·存档 UI，且 GPL-2.0-or-later 传染需法务确认；接入定位排在 KiriKiri 之后、RenPy 之前。

### 5.4 里程碑判定

| 验收 | 结果 |
| --- | --- |
| 第二个适配器不改核心工作流接入 | ✅ 两个引擎（krkrsdl2 原生 / brewser Web）在同一注册表与计划流水线下工作；新增引擎=描述符+（可选）适配器类+注册表登记 |
| 引擎/输入/构建配置独立 | ✅ 描述符、输入 profile、构建参数三处分离且有测试覆盖（`tests/test_engines_*`） |
| 第二引擎在模拟器跑通真实内容 | ✅ Brewser 跑自建 Web VN（标题→正文→分支→页内存档） |
| 第三引擎评估（额外，计划 M4 未强制） | ✅ ONScripter-NX 构建+运行闭环，结论 P2 有条件 |

## 6. 未验证与剩余风险

1. ~~Brewser localStorage 落盘/跨 run 持久化未验证~~ → **M4-g 已证伪**：页内可用但跨 run 丢失（kill 后重启 `SAVE=absent`，磁盘无写入）；M4 存档需引擎侧修复或外部存档（006 §12）。
2. **DOM `<button>` 精确点击未打通**：Brewser LiveElement 事件 target `tagName` 为空且坐标有系统偏移；分支结论按整屏左右半区判定，不等价于「按钮点击已通」。
3. **真机全部未验证**：Brewser/ONScripter 的 CFW 真机行为均只有上游 release notes 声称（README 声称 ≠ 已验证）。
4. **纯触摸未验证**：只验证了鼠标→触摸合成路径；Brewser 适配器描述符里 `touch` 能力标 supported 但未逐项实测（与 M4-a 自报偏差一致）。
5. **ONScripter-NX 的 CJK 字体、音视频、HD 模式、存档写盘、3 项以上菜单光标语义均未验证**（007 §14 U1–U10）。
6. **GPL-2.0-or-later 传染性**：分发内置 ONScripter 引擎的 GalNX 修改版需按 GPL 开源相应部分，法务未确认前不得对外分发。
7. `run_spec()` 目前固定 Citron，真机 hbmenu/安装启动参数未实现；`engine.adapter` 的 manifest enum 未开放自定义引擎名（需用 enum 内名字 + `engine.descriptor`）。
8. 计划 M4「候选」里提到的 BurialNX 与 Teaching Feeling（Electron/TyranoScript）发行结构核验**未在本轮展开**——本轮范围收在适配器契约 + 两个引擎闭环，列为后续研究项。

## 7. 下一步

1. 将 ONScripter-NX 登记为第 3 个内置适配器（`engines` 目前只有 krkrsdl2/brewser），补齐其 build/run 契约与 `docs/engines` 说明。
2. 补 M4 遗留：Brewser 存档方案选型（引擎修复/引擎外存档）、DOM 按钮坐标模型、触摸能力逐项实测；localStorage 跨 run 已由 M4-g 证伪（006 §12）。
3. 进入 **M5：FVP / rfvp 评估**（构建命令/依赖/产物、PC host 脚本与资源读取、Switch 端渲染/音频/IO/输入/存档完成度，结论=正式适配/继续研究/搁置）。
4. M3-d 真机验收仍待用户设备接入（模拟器结论不替代真机）。

## 8. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-30 | 初稿：汇总 M4-a/b/c，判定 M4 两条验收达成（模拟器级） |