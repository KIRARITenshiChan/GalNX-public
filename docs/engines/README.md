# 引擎注册表、能力模型与适配器契约

- 日期: 2026-11-11
- 适用版本: galnx 0.1.0
- 相关代码: `src/galnx/engines/`（descriptor.py / registry.py / contract.py / __init__.py）
- 相关 schema: `schemas/engine.schema.json`、`schemas/game-manifest.schema.json`（engine 段）
- 相关测试: `tests/test_engines_descriptor.py`、`tests/test_engines_registry.py`、`tests/test_engines_contract.py`、`tests/test_engines_cli.py`
- 验证记录: `docs/engines/verification-matrix.md`（游戏级）、各引擎 descriptor 的 `verification` 块（引擎级）

本文件说明 GalNX 的「引擎注册表 + 能力模型 + 适配器契约」。一个引擎以**描述符**（descriptor）与**适配器**（adapter）两个概念接入：描述符声明它是谁、锁定什么版本、能力到什么程度；适配器决定 `galnx engines plan` 生成什么构建步骤、怎么校验产物、交给 harness 什么启动参数。接入后核心工作流（manifest 校验、输入层、打包数据模型）不需要改动。

## 0 术语

0.1 Preview 的文档与代码里，同一个词以前混用过多种含义。本文件统一如下：

| 术语 | 含义 | 例子 |
| --- | --- | --- |
| **built-in adapter（内置适配器）** | 在 `src/galnx/engines/` 里用 Python 实现的适配器，import 时注册，`galnx engines list` 默认只列这些 | `krkrsdl2`、`brewser`、`onscripter-nx` |
| **external descriptor（外部描述符）** | 只有 YAML 描述符、没有专属 Python 适配器（走通用 `EngineAdapter`），必须用 `--engines-dir` 或 manifest 的 `engine.descriptor` 才会被加载 | `examples/engines/rfvp.yaml`、`examples/engines/kirikiroid2-nx.yaml` |
| **engine runtime（引擎运行时）** | 上游引擎本体的构建产物（NRO/NSP/Web 包） | KiriKiri SDL2、RFVP、ONScripter-NX、Brewser |
| **game profile（游戏配置）** | 一款游戏的内容布局与构建/打包参数，写在 manifest 里 | `examples/pilot02-iroseka.yaml` |
| **引擎级验证（engine verification）** | 这个引擎整体在什么环境验证过，写在描述符顶层 `verification` 块 | `device_verified` + 证据列表 |
| **游戏级验证（game verification）** | 某款具体游戏在某个 runtime 版本上哪些测试项真的跑过，记录在验证矩阵 | `docs/engines/verification-matrix.md` 的一行 |
| **capability（能力项）** | 引擎/游戏在某方面的支持声明，固定 6 个键 | `graphics`、`movie`、`audio`、`input`、`save`、`touch` |

## 1 目标与范围

- 目标：让第二、第三个引擎尽量只新增 YAML 描述符就能接入构建计划（计划 §10 M4 验收①），且引擎配置、输入配置、构建参数互相独立（验收②）。
- 能力模型（本版新增）：把「引擎能做什么」（capabilities）与「做到什么程度、在什么环境验证过」（verification）分开；把「引擎级整体结论」与「单款游戏的兼容性」分开。
- 明确不做：`plan` 不执行真实构建、不下载上游源码、不启动模拟器；它只产出步骤与校验项。
- 与打包数据模型的分界：`galnx package` 负责 NSP/NRO 元数据与打包契约；`galnx engines` 负责引擎如何被构建、用什么输入配置、产物长什么样。

## 2 注册表模型

```
schemas/engine.schema.json        描述符 JSON Schema（结构约束）
src/galnx/engines/descriptor.py   EngineDescriptor 数据类 + schema/语义校验 + YAML 读写 + 能力模型
src/galnx/engines/registry.py     内置注册表（3 个）+ 外部目录加载 + 与 manifest.engine 的一致性校验
src/galnx/engines/contract.py     适配器契约（plan_build / verify_artifact / run_spec）与三个具体适配器
examples/engines/*.yaml           描述符示例：3 个内置项的镜像 + 2 个外部描述符（rfvp、kirikiroid2-nx）
docs/engines/verification-matrix.md  游戏级验收索引
```

注册表来源有三层，后者可覆盖前者的同名 id：

1. **内置**（`BUILTIN_ENGINES`：`krkrsdl2`、`brewser`、`onscripter-nx`），import 时即完成校验，非法描述符会让进程直接报错。
2. **`--engines-dir <dir>`**：CLI 可重复传入的目录，加载其中全部 `*.yaml` / `*.yml`。
3. **manifest 的 `engine.descriptor`**：指向一个描述符 YAML（相对 manifest 目录解析），用于让单个 manifest 自带非内置适配器。

注意：`galnx engines list` 默认**只列 3 个内置适配器**；`rfvp`、`kirikiroid2-nx` 等外部描述符只有加上 `--engines-dir examples/engines` 才会出现在列表与 `info` 里。这是本版有意保留的行为，用于区分「已实现适配器」与「只有描述符的引擎」。

注册表以 id 为键，`get()` 返回 `Optional`，`require()` 在缺失时抛出 `unknown engine adapter ...` 错误。

## 3 描述符字段语义

固定 19 个字段（`EngineDescriptor.to_dict()` 的顺序），未知顶层键会被 schema 拒绝（`additionalProperties: false`）；另有可选的顶层 `verification` 块（见 §4.4，存在时出现在 `to_dict()` 末尾）。

| 字段 | 类型 | 必填性 | 语义 |
| --- | --- | --- | --- |
| id | string | 必填 | 适配器 id，小写 slug（2-64 字符，`[a-z0-9._-]`，首字符为字母或数字）；必须与 manifest `engine.adapter` 一致 |
| display_name | string | 必填 | 人类可读名称 |
| upstream_url | string | 必填 | 上游仓库/主页，必须 https:// |
| pinned_commit | string | 源码构建必填 | 40 位十六进制 commit SHA；prebuilt 适配器可为空 |
| pinned_version | string | prebuilt 必填 | 锁定版本的人类可读写法（如 `krkrsdl2@124bdf84 (2026-10-01)`） |
| license_spdx | string | 必填 | SPDX 标识（如 MIT、MPL-2.0、GPL-2.0-or-later） |
| license_url | string | 必填 | 许可证原文链接（证据） |
| license_notes | string | 可选 | 许可证补充说明（第三方组件、子模块许可） |
| target_kind | enum | 必填 | `nro` / `self_contained_nsp` / `web` |
| build_backend | enum | 必填 | `cmake-switch` / `make-switch` / `devkitpro-make` / `custom-script` / `prebuilt` / `none` |
| capabilities | object | 必填 | 固定 6 个键：graphics / movie / audio / input / save / touch（见 §4） |
| default_input_profile | string | 必填 | 必须是 `src/galnx/input` 的内置 profile 名（kb_mouse / generic-vn / krkrsdl2 / krkr-ns） |
| artifact_naming | string | 必填 | 产物命名模板，占位符仅 `{id}` `{version}` `{target}` `{kind}`；后缀必须匹配 target_kind（nro→.nro，nsp→.nsp，web→.nro 或 .nsp） |
| content_layout | object | 必填 | `mode`（romfs / sdmc / none）+ `entry` + `destination` + `notes`；mode 非 none 时 entry/destination 必填 |
| status | enum | 必填 | `ready` / `research` / `blocked`；非 ready 必须有 status_reason |
| status_reason | string | 条件必填 | 非 ready 时必填；ready 但仍有重要限制时也建议写 |
| artifact_sha256 | string | 可选 | 预编译产物的 SHA-256（64 位十六进制）；空串表示未记录 |
| evidence_urls | array | 必填 | 证据链接列表（仓库内相对路径或 URL），至少 1 条 |
| notes | string | 可选 | 自由备注 |
| verification | object | 可选 | 引擎级整体验证结论（见 §4.4）；存在时随 `to_dict()` 输出 |

`status` 的语义：`ready` = 可以作为交付路径使用（不等于「所有能力都真机验证过」，看 verification）；`research` = 仅研究/模拟器级，不能对用户承诺；`blocked` = 有硬阻塞（许可证、缺工具链等），必须写 status_reason。

`content_layout` 表达「游戏内容放在哪里」：

- `romfs`：内容打进 NRO/NSP 的 RomFS（krkrsdl2 的 `data.xp3` → `romfs/data.xp3`；rfvp 的 `romfs:/game`）。
- `sdmc`：内容通过 SD 卡目录部署（brewser 的 `index.html` → `sdmc:/switch/brewser/apps/<app-id>/`）。
- `none`：无内容部署步骤。

## 4 能力模型

### 4.1 六个能力键

| 键 | 语义 | backend 示例（描述符里的自由字符串） |
| --- | --- | --- |
| `graphics` | **图形渲染**（画面如何画出来），不包含视频解码 | `sdl2-gles2`、`cocos2d-x-egl`、`skia+webgl` |
| `movie` | **视频解码与播放**（OP/过场），与 graphics 分开 | `h264+nvdec+nvtegra+ffmpeg`、`ffmpeg`、`html5-video` |
| `audio` | 音频输出与混音 | `audren`、`faudio+sdl2`、`web-audio` |
| `input` | 输入映射（手柄/键盘/鼠标到游戏事件的路径） | `pad-to-kag`、`cocos-keymap`、`html5-input` |
| `save` | 存档/读档读写 | `engine-native`、`private-bin`、`web-localstorage` |
| `touch` | 触摸屏输入 | `software-cursor` |

**`video` 是已弃用别名**：只映射到 `graphics`。加载旧描述符时，`video` 会被自动改名为 `graphics` 并产生一条 warning（`capabilities.video: deprecated alias of 'graphics'`），同时补齐缺失的 `movie` 项（`supported: false`、`verification: unknown`）。新写的描述符禁止使用 `video`——旧的 `video: true` 语义含糊（有人指渲染、有人指视频解码），这正是本次拆成 `graphics` + `movie` 的原因。

### 4.2 能力项字段

每个能力项是一个 object，字段如下：

| 字段 | 类型 | 必填性 | 语义 |
| --- | --- | --- | --- |
| `supported` | bool | 必填（兼容保留） | 实现是否存在且可用；只表示「有」，程度看 `verification` |
| `note` | string | 必填 | 依据/限制的一句话说明，避免把「未验证」写成支持 |
| `verification` | enum | `graphics`/`movie`/`audio`/`input`/`save` 必填，`touch` 可省略 | 验证到哪一档（见 §4.3） |
| `backend` | string | 可选 | 实现技术，自由字符串（例如 `sdl2-gles2`） |
| `features` | array[string] | 可选 | 关键子特性列表（例如 `nvdec`、`nv12-zero-copy`、`software-fallback`） |
| `details` | object | 可选 | 任意 JSON 对象，仅供人读/工具展示，**不参与决策**；不要往里塞会变的状态 |

约定：`supported: true` + `verification: unknown` 是合法组合（实现存在但没验证）；`supported: false` 时 `note` 必须写清为什么。

### 4.3 verification 枚举

| 值 | 含义 |
| --- | --- |
| `source_review` | 只读过源码/文档，未构建、未运行 |
| `build_verified` | 在本仓库工具链下构建成功，未运行 |
| `emulator_verified` | 在模拟器（当前为 Citron Nightly）里跑通所述测试项 |
| `device_verified` | 在 Nintendo Switch 真机上跑通所述测试项（至少启动/画面） |
| `game_verified` | 真机上完成单款游戏的完整验收（启动→剧情→存档/读档→手柄→退出） |
| `partial` | 只有部分测试项通过，或有已知阻塞缺陷 |
| `unknown` | 没有证据，不要据此承诺 |
| `in_progress` | 正在验证，结果尚未定稿 |

真机结论一律以用户签收为准（引用用户消息编号或验收文档）；模拟器结论不作为真机结论使用。游戏级逐项记录见 `docs/engines/verification-matrix.md`。

### 4.4 引擎级 verification 块

描述符顶层可选 `verification` 字段，回答「这个引擎整体验证到哪一档」：

| 字段 | 类型 | 必填性 | 语义 |
| --- | --- | --- | --- |
| `status` | string | 块存在时必填 | 该引擎整体的验证等级，取值同 §4.3 |
| `hardware` | string | 可选 | 硬件与环境描述（如 `Nintendo Switch (user-owned console via hbloader)`、`Citron Nightly 0237a9b88 (Windows, Vulkan)`） |
| `firmware` | string | 可选 | Switch 固件版本；没有记录就**留空**，不要猜 |
| `atmosphere` | string | 可选 | Atmosphère 版本；没有记录留空 |
| `tested_at` | string | 可选 | 最近一次有效验证的日期（YYYY-MM-DD） |
| `evidence` | array[string] | 可选 | 证据路径（仓库内相对路径） |
| `notes` | string | 可选 | 结论、限制、待补材料 |

引擎级 `verification` 与游戏级矩阵**不能互相替代**：引擎可以是 `device_verified`，但某款游戏仍可能只做过模拟器验证；反过来，单款游戏 PASS 也不能把引擎未验证的能力升级。

## 5 适配器契约

适配器是 Python 对象（`EngineAdapter` 及其子类），只要实现三个方法：

| 方法 | 输入 | 输出 | 作用 |
| --- | --- | --- | --- |
| plan_build(descriptor, manifest, manifest_path) | 描述符 + 已校验 manifest | `BuildStep` 元组 | 生成构建步骤（命令是建议文本，不执行） |
| verify_artifact(descriptor, path, expected_sha256) | 产物路径 | `Check` 列表 | 校验产物：存在、大小、后缀、NRO0/HOMEBREW 或 PFS0 magic、SHA-256 |
| run_spec(descriptor, manifest) | 描述符 + manifest | dict | 给出 harness 参数建议（引擎、load 类型、artifact、arguments、sdmc、notes） |

`BuildStep` 字段：id / summary / command / requires / notes；`to_dict()` 固定 5 键。
`Check` 字段：id / name / status（ok、warn、fail、skip）/ detail / hint；`to_dict()` 固定 5 键，可 JSON 序列化。
`run_spec()` 的键：engine / harness（当前固定 `citron`）/ target_kind / load（`nro` 或 `nsp`）/ artifact / arguments（默认 `["-g", "<artifact>"]`）/ sdmc / notes。

通用 `EngineAdapter` 按 `build_backend` 生成步骤，已覆盖 cmake-switch、make-switch、devkitpro-make、custom-script、prebuilt、none 六类后端；只有「需要额外步骤或特殊产物校验」的引擎才需要写子类。外部描述符（rfvp、kirikiroid2-nx）都走通用 `EngineAdapter`，没有专属 Python 适配器。

`devkitpro-make` 与 `make-switch` 的区别：`make-switch` 是通用 `make -j8`（内容由构建后的 content 步再部署），而 `devkitpro-make` 对应 devkitPro `switch_rules` Makefile——它把仓库内 `romfs/` 在链接阶段直接内嵌进 NRO，因此 plan 把 `prepare-content`（把内容拷进源码 `romfs/`）放在 `compile` 之前，并跳过构建后的 content 步；改过 `romfs/` 后必须在编译前 `make clean`（libnx 的 romfs 规则依赖文件列表），且构建目录不能含空格（switch_rules 引号缺陷，见 `docs/audit/00-switch-base.md`）。

现有具体适配器：

- `Krkrsdl2Adapter`：8 步（manifest / source / patches / prepare-data / configure / compile / artifact / verify），额外校验 NRO 体积（<1 MiB 会警告，已知带内嵌 data.xp3 的产物约 17.9 MB）。
- `BrewserAdapter`：6 步（manifest / fetch / verify-source / content / install / artifact），内容部署到 sdmc 目录。
- `OnscripterNxAdapter`：6 步（manifest / source / prepare-content / compile / artifact / verify），内容在编译前拷入源码 `romfs/`；额外校验 NRO 体积（<1 MiB 会警告，已知带内嵌内容的产物约 10.4 MB），`run_spec` 附带 Citron 实测记录与「无启动器/无存档菜单 UI/触摸被上游注释」备注。

## 6 新增引擎接入 checklist

最小接入（推荐先走这条路）：

1. 复制 `examples/engines/krkrsdl2.yaml`（CMake 引擎）或 `examples/engines/onscripter-nx.yaml`（devkitPro Makefile 引擎）为模板，改 id / display_name / upstream_url / pinned_commit / license / target_kind / content_layout。
2. 按 §4 填写 6 个能力项：`graphics`（渲染）与 `movie`（视频解码）分开写，每项给 `note` 与 `verification`；引擎整体做过真机验收就补顶层 `verification` 块。
3. 用 `PYTHONPATH=src python -m galnx engines info <id> --engines-dir <dir>` 验证描述符能被加载且无问题（`problems` 为空）。
4. 在 manifest 的 `engine.adapter` 填该 id；若不想加 `--engines-dir`，把描述符路径写进 manifest 的 `engine.descriptor`（相对 manifest 目录）。
5. 用 `python -m galnx engines plan --manifest <manifest>` 检查步骤与校验项是否符合预期。
6. 在 `docs/engines/verification-matrix.md` 补一行游戏级验收（如适用）。

需要自定义步骤时的接入：

1. 在 `src/galnx/engines/contract.py` 中继承 `EngineAdapter`，覆写 `plan_build` / `verify_artifact` / `run_spec` 中需要变化的方法。
2. 在 `ADAPTER_FACTORIES` 注册 `{id: YourAdapter}`；未注册的 id 自动使用通用 `EngineAdapter`。
3. 增加对应测试（步骤顺序、产物校验的 ok/warn/fail 分支），并更新本文件。
4. 适配器 id 必须同时出现在 `schemas/game-manifest.schema.json` 的 engine.adapter enum 中，否则 manifest 结构校验会先拒绝。
5. 若引擎使用新的构建后端，还要扩 `descriptor.BUILD_BACKENDS`、`schemas/engine.schema.json` 的 `build_backend` enum 与通用 `EngineAdapter.plan_build` 分支，并补测试（`devkitpro-make`、`custom-script` 即如此接入）。

## 7 内置适配器与证据

三个内置适配器当前都标为 `research`：它们有构建/模拟器级证据，但没有真机验收，因此不能当成交付路径对用户承诺。

### 7.1 krkrsdl2（KiriKiri SDL2）

| 项 | 值 | 证据 |
| --- | --- | --- |
| 上游 | https://github.com/krkrsdl2/krkrsdl2 | 上游仓库 |
| 锁定 commit | 124bdf841f09e7ce02aa99b7b55791a0f7a900ff（2026-10-01） | `docs/builds/001-krkrsdl2-upstream.md` |
| 许可证 | MIT（上游 LICENSE 1063 B，Kirikiri SDL2 Developers；子模块各自保留许可） | `docs/audit/01-engines.md`、`docs/builds/001` |
| 构建后端 | cmake-switch（Switch.cmake + Ninja；需 switch-sdl2、FAudio） | `docs/builds/001` |
| 产物 | 约 17.9 MB 的 NRO，内嵌 data.xp3；已在 Citron 渲染出 KAG3 demo | `docs/builds/004-krkrsdl2-switch-fixes.md` |
| 能力 | graphics/input = `emulator_verified`；movie/audio/save/touch = `unknown` | descriptor + 验证矩阵 |
| 已知风险 | KAG3 demo 默认依赖系统字体（MS PMincho / MS Gothic），Switch 无系统字体，需改用内嵌字体的 data.xp3；上游预编译 NRO 在 Citron 不出画面（VI STUBBED） | `docs/builds/003-kag3-demo-content.md`、`docs/builds/004` |

### 7.2 brewser（nx.js Web 运行时）

| 项 | 值 | 证据 |
| --- | --- | --- |
| 上游 | https://github.com/natureglass/Brewser | 上游仓库 |
| 锁定版本 | v0.1.1.31（commit 8040580e92e40a60f704a6478ee296b105212f1b） | `docs/audit/02-web.md` |
| 许可证 | MPL-2.0 | `docs/audit/02-web.md` |
| 产物 | brewser.nro（76,546,123 B，SHA-256 8ce31f5b…）预编译，另附 forwarder NSP | `docs/audit/02-web.md` |
| 内容布局 | sdmc:/switch/brewser/apps/&lt;app-id&gt;/（本地 sideload 只需 index.html） | `docs/audit/02-web.md` |
| 能力 | graphics/save = `emulator_verified`；input/touch = `source_review`；movie/audio = `unknown` | descriptor + 验证矩阵 |
| 已知限制 | 存档跨 run 不持久（localStorage 重启后丢失，已证伪）；--jitless 环境无 WebAssembly；Mesa Nouveau 不支持 sampler3D/sampler2DArray/samplerCube；真机未验证 | `docs/builds/006-brewser-web-adapter.md`、`docs/experiments/web-02-citron-smoke.md` |

### 7.3 onscripter-nx（ONScripter-NX）

| 项 | 值 | 证据 |
| --- | --- | --- |
| 上游 | https://github.com/clamintus/onscripter-nx | 上游仓库 |
| 锁定 commit | a8439a86393f74c503d28df176f010ca544af56f（2026-01-14，v0.3.1） | `docs/builds/007-onscripter-nx.md` |
| 许可证 | GPL-2.0-or-later（COPYING 为 GPLv2 全文；source/ 25 个文件中 24 个文件头声明 "or any later version"） | `docs/builds/007` |
| 构建后端 | devkitpro-make（仓库根 Makefile `include $(DEVKITPRO)/libnx/switch_rules`；无 CMake） | `docs/builds/007` |
| 内容布局 | romfs：编译前把内容拷进源码 `romfs/`，链接时内嵌进 NRO；内容需含 `*define`/`game`/`*start` 与至少一个 `arc.nsa`/`arc.sar`（0 字节占位可过启动门禁） | `docs/builds/007` |
| 产物 | m4-ons-with-content.nro 10,449,140 B（SHA-256 d8f9bb11…）；纯引擎 m4-ons-engine-only.nro 10,437,716 B | `docs/builds/007` |
| 能力 | graphics/input = `emulator_verified`；movie/audio/save/touch = `unknown` | descriptor + 验证矩阵 |
| 已知风险 | ①无多游戏启动器（单目录 arc.nsa 模型）②无菜单/存档 UI，rmenu 未定义时右键仅隐藏文字层 ③GPL-2.0-or-later 分发需随附完整对应源码（传染性待法务评估）④真机未验证，触摸注入代码在上游被整段注释 | `docs/builds/007` |

## 8 外部描述符（examples/engines）

下列引擎只有 YAML 描述符，走通用 `EngineAdapter`，需要 `--engines-dir examples/engines` 才能被 CLI 看到。它们是当前唯二 `ready` 的引擎。

### 8.1 rfvp（FVP 兼容运行时，自包含 NSP）

| 项 | 值 | 证据 |
| --- | --- | --- |
| 上游 | https://github.com/xmoezzz/rfvp | 上游仓库 |
| 锁定 commit | 9f07adef2eb5d559777f9bf59a67b756875cb24f（HEAD 2026-10-25；tag 0.7.0 = 99435f22） | descriptor；`docs/builds/008-rfvp-evaluation.md` |
| 许可证 | MPL-2.0 | descriptor；`docs/audit/05` |
| 构建后端 | custom-script（`platform/switch/build_switch.sh` + 自建 portlibs；Rust nightly 交叉到 aarch64-nintendo-switch） | `docs/builds/001`、`docs/builds/016`–`026` |
| 产物 | 自包含 NSP（内容 100% 内嵌 romfs:/game），例：AKASEKA 1.4.0-test 6,676,387,544 B（sha256 569af9fb…） | `docs/builds/050-akaseka-fd-nsp.md` |
| 能力 | graphics/input = `game_verified`；movie/audio/save = `device_verified`；touch = `unknown` | descriptor + 验证矩阵 |
| 引擎级验证 | `device_verified`，2026-11-10，4 个 Pilot 真机 PASS | descriptor `verification` 块 |
| 已知限制 | 默认 720p（1080p 突破帧预算）、私有存档格式不与 PC 互通、IROSEKA/MOYU 的 OP 分档与 WMV2 路径待各自确认、no_std 构建的视频解码器依赖 NVDEC/nvtegra | descriptor `status_reason`、`docs/pilot/akaseka-fd-acceptance.md` |

### 8.2 kirikiroid2-nx（KiriKiri2 移植，自包含 NSP）

| 项 | 值 | 证据 |
| --- | --- | --- |
| 上游 | https://github.com/Erige005/Kirikiroid2-NX | 上游仓库 |
| 锁定版本 | v1.0.1（commit e96b6034c292c6ccdb099823ab6a0a6b505f77f3，2026-10-18） | descriptor；`docs/builds/009` |
| 许可证 | NOASSERTION（仓库 LICENSE 为 KiriKiri BSD-style 44,184 B + THIRD_PARTY_LICENSES.md；再分发前需逐项复核） | `docs/audit/06-engines-refresh.md`、`docs/builds/009` |
| 构建后端 | cmake-switch（cocos2d-x 3.11.1 + 7 个自建 portlibs + 9 个游戏侧补丁） | `docs/builds/009`、`docs/builds/patches/k2nx-switch/README.md` |
| 产物 | 自包含 NSP（游戏数据首启解包到 sdmc），例：A10 1.0.9 2,870,911,704 B（sha256 0efc23f6…） | `docs/pilot/P4-device-runbook.md` §12.4 |
| 能力 | graphics/input = `game_verified`；movie/audio/save = `device_verified`；touch = `unknown` | descriptor + 验证矩阵 |
| 引擎级验证 | `game_verified`，2026-10-31，Pilot-01 真机 PASS（用户 m13918） | descriptor `verification` 块 |
| 已知限制 | 单一游戏真机验收、9 个补丁未上游、退出保存 best-effort（保存后约 1 s 延迟退出，强制断电可能丢最后一次元数据）、私有存档格式 | `docs/pilot/P4-device-runbook.md` §12.3、descriptor `status_reason` |

## 9 与 manifest 的一致性校验

`manifest.validate` 在 schema 校验通过后追加引擎校验（实现见 `registry.validate_manifest_engine`），错误进入 manifest 的 errors 列表，`galnx preflight` / `galnx engines plan` 都会显示：

| 情况 | 级别 | 消息形态 |
| --- | --- | --- |
| `engine.adapter` 未注册 | error | `engine.adapter: unknown engine adapter ... (registered: ...; add a descriptor via engine.descriptor or --engines-dir)` |
| `engine.adapter` 缺失或非字符串 | error | `engine.adapter: required` |
| `engine` 段不是 mapping | error | `engine: must be a mapping` |
| 描述符 id 与 adapter 不一致 | error | `engine.descriptor: descriptor id ... does not match engine.adapter ...` |
| `engine.descriptor` 文件缺失/非法 | error | `engine.descriptor: ...` |
| 适配器 status 为 blocked / research | warning | `engine.adapter: adapter ... is blocked: ...` / `... still marked research: ...` |
| `engine.adapter_version` 未包含锁定 commit 前 8 位 | warning | `engine.adapter_version: ... does not mention the pinned commit ...` |

约定：`engine.adapter_version` 建议写成 `krkrsdl2@124bdf84 (2026-10-01)` 这种形式，既能人工读，也能被上述校验核对；示例 manifest 用的是 `ONScripter-NX@a8439a86 (v0.3.1)`。

CLI 的 `--engines-dir` 会同时用于 manifest 校验与 plan 解析（`manifest.validate(..., engines_dir=...)`），因此用外部描述符时 plan 不会因为「未知 adapter」失败。

## 10 CLI 用法

```
# 列出内置适配器（默认只有 3 个；文本 / JSON）
python -m galnx engines list
python -m galnx engines list --json

# 查看单个适配器（锁定版本、许可、产物名、适配器类、能力与 verification）
python -m galnx engines info krkrsdl2
python -m galnx engines info onscripter-nx
python -m galnx engines info brewser --json

# 外部描述符必须带 --engines-dir 才会出现在列表/info 里
python -m galnx engines list --engines-dir examples/engines
python -m galnx engines info rfvp --engines-dir examples/engines
python -m galnx engines info kirikiroid2-nx --engines-dir examples/engines

# 生成构建计划（只校验与打印，不执行构建）
python -m galnx engines plan --manifest examples/manifest.krkr.yaml
python -m galnx engines plan --manifest examples/manifest.packaged.yaml --json
python -m galnx engines plan --manifest examples/manifest.onscripter.yaml
python -m galnx engines plan --manifest examples/pilot04-akaseka.yaml --engines-dir examples/engines
```

退出码：0 = 成功（plan 全部检查通过）；2 = 校验失败或适配器未知。
`plan --json` 的稳定键：version、manifest、ok、errors、warnings、checks、adapter、engine、build_steps、input_profile（name/source）、expected_artifact、run_spec。
`info --json` 的稳定键：version、engine（19 个固定字段，描述符带顶层 verification 时多一个 verification 键）、adapter（class/methods）、artifact_name、input_profile、problems。

> 注：`src/galnx/cli.py` 的 `info` 文本输出目前只打印 `capabilities` 的 `supported` 摘要，不逐项打印 `verification`/`backend`；如需在 CLI 展示新字段，属于 Lead 的 scope，建议的 diff 已记录在 `docs/release/tasks/TASK-ENGINES.md`。

## 11 输入配置的独立性

`plan` 的输入 profile 来源有优先级：

1. manifest 有 `input.profile` → 使用 manifest 的（`input_profile.source = "manifest"`）。
2. 否则使用描述符的 `default_input_profile`（`source = "engine-default"`）。

引擎配置（描述符）与输入配置（input profile）互不覆盖：描述符只能指定默认值，manifest 始终可以覆盖；改输入映射不需要动引擎描述符。

## 12 研究路线与已验证试点分层

| 层级 | 引擎 | 依据 |
| --- | --- | --- |
| 真机已验证（可交付） | `rfvp`（4 个 Pilot）、`kirikiroid2-nx`（Pilot-01） | 验证矩阵 §2；descriptor `verification` |
| 模拟器级（研究/待真机） | `krkrsdl2`、`onscripter-nx`、`brewser` | 验证矩阵 §3；descriptor `status: research` |
| 暂缓（无适配器） | Ren'Py | `docs/audit/04-renpy-official.md`：官方无 Switch 平台，硬阻塞为 CPython 交叉编译 |

逐项验收记录、测试环境与未验证项见 `docs/engines/verification-matrix.md`。

## 13 限制与未验证

- `plan` 不执行任何构建命令；构建证据来自 `docs/builds/` 的对应记录，本文件不重新构建。
- `artifact_sha256` 只对 prebuilt 适配器有意义；源码构建的产物哈希会因工具链与时间戳变化，不应写进描述符。
- `run_spec` 当前 harness 固定为 `citron`，尚未实现真机（hbmenu）启动参数。
- `examples/engines/brewser.yaml` 与内置描述符核心字段一致，但 YAML 折叠文本会让 `license_notes` 等长字符串换行方式不同，因此测试不做逐字符相等断言（其余 4 个 YAML 与内置项/一致性已验证到 `to_dict()` 相等或字段级相等）。
- `touch` 在 5 个引擎上都没有真机验证；`supported: true` 只表示 Web 层/代码层有触摸事件。
- 真机验收文档没有记录 Switch firmware 与 Atmosphère 版本，descriptor 的 `verification.firmware` / `verification.atmosphere` 故意留空。
- 1.2.5-test / 1.3.3-test / 1.4.1-test 三个更新的 rfvp 构建只有用户确认，仓库内还没有对应验收日志（见验证矩阵 §2.1）。
- `make clean` 与「无空格构建路径」是 devkitPro Makefile 的硬约束（plan 的 compile 步已写入 make clean），本轮未在含空格路径下复测 onscripter-nx。

## 14 相关文件

- 验证矩阵：`docs/engines/verification-matrix.md`
- 计划草案：`docs/PLAN_DRAFT_v1.43.md`（§10 M4）
- 构建记录：`docs/builds/001-krkrsdl2-upstream.md`、`docs/builds/004-krkrsdl2-switch-fixes.md`、`docs/builds/007-onscripter-nx.md`、`docs/builds/008-rfvp-evaluation.md`、`docs/builds/009-k2nx-selfcontained-build.md`、`docs/builds/050-akaseka-fd-nsp.md`
- 审计证据：`docs/audit/01-engines.md`、`docs/audit/02-web.md`、`docs/audit/04-renpy-official.md`、`docs/audit/06-engines-refresh.md`、`docs/experiments/web-02-citron-smoke.md`
- 输入层：`docs/input/README.md`
- 打包数据模型：`docs/packaging/README.md`
- 示例：`examples/engines/*.yaml`、`examples/manifest.krkr.yaml`、`examples/manifest.packaged.yaml`、`examples/manifest.onscripter.yaml`、`examples/pilot02-iroseka.yaml`、`examples/pilot04-akaseka.yaml`
