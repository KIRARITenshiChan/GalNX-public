# 引擎注册表与适配器契约（M4-a / M4-f）

- 日期: 2026-10-30
- 适用版本: galnx 0.1.0
- 相关代码: `src/galnx/engines/`（descriptor.py / registry.py / contract.py / __init__.py）
- 相关 schema: `schemas/engine.schema.json`、`schemas/game-manifest.schema.json`（engine 段）
- 相关测试: `tests/test_engines_descriptor.py`、`tests/test_engines_registry.py`、`tests/test_engines_contract.py`、`tests/test_engines_cli.py`

本文件说明 GalNX 的「引擎注册表 + 适配器契约」：一个引擎（模拟器/运行时/自制程序）以描述符（descriptor）和适配器（adapter）两个概念接入，
接入后 `galnx engines plan` 能给出构建步骤与产物校验计划，`galnx engines info` 能展示锁定版本与出处，而核心工作流（manifest 校验、输入层、打包数据模型）不需要改动。

## 1. 目标与范围

- 目标：让第二个、第三个引擎只通过新增 YAML 描述符即可接入构建计划（计划 §10 M4 验收①），且引擎配置、输入配置、构建参数互相独立（验收②）。
- 已内置三个适配器：`krkrsdl2`（原生 NRO，cmake-switch 源码构建）、`brewser`（Web 运行时，预编译产物）与 `onscripter-nx`（原生 NRO，devkitPro switch_rules Makefile 源码构建，M4-f 新增）。
- 明确不做：不执行真实构建、不下载上游源码、不启动模拟器；`plan` 只产出步骤与校验项。
- 与 M3-c 打包数据模型的分界：`galnx package` 负责 NSP/NRO 元数据与打包契约；`galnx engines` 负责引擎如何被构建、用什么输入配置、产物长什么样。

## 2. 注册表模型

```
schemas/engine.schema.json       描述符 JSON Schema（结构约束）
src/galnx/engines/descriptor.py  EngineDescriptor 数据类 + schema/语义校验 + YAML 读写
src/galnx/engines/registry.py    内置注册表 + 外部目录加载 + 与 manifest.engine 的一致性校验
src/galnx/engines/contract.py    适配器契约（plan_build / verify_artifact / run_spec）与三个具体适配器
examples/engines/*.yaml          与内置描述符等价的 YAML 示例（可作为自定义描述符的模板）
```

注册表来源有三层，后者可覆盖前者的同名 id：

1. 内置（`BUILTIN_ENGINES`：`krkrsdl2`、`brewser`、`onscripter-nx`），import 时即完成校验，非法描述符会让进程直接报错。
2. `--engines-dir <dir>`：CLI 可重复传入的目录，加载其中全部 `*.yaml` / `*.yml`。
3. manifest 的 `engine.descriptor`：指向一个描述符 YAML（相对 manifest 目录解析），用于让单个 manifest 自带非内置适配器。

注册表以 id 为键，`get()` 返回 `Optional`，`require()` 在缺失时抛出 `unknown engine adapter ...` 错误。

## 3. 描述符字段语义

字段固定 19 个（`EngineDescriptor.to_dict()` 的顺序），未知顶层键会被 schema 拒绝（`additionalProperties: false`）。

| 字段 | 类型 | 必填性 | 语义 |
| --- | --- | --- | --- |
| id | string | 必填 | 适配器 id，小写 slug（2-64 字符，`[a-z0-9._-]`，首字符为字母或数字）；必须与 manifest `engine.adapter` 一致 |
| display_name | string | 必填 | 人类可读名称 |
| upstream_url | string | 必填 | 上游仓库/主页，必须 https:// |
| pinned_commit | string | 源码构建必填 | 40 位十六进制 commit SHA；prebuilt 适配器可为空 |
| pinned_version | string | prebuilt 必填 | 锁定版本的人类可读写法（如 `krkrsdl2@124bdf84 (2026-10-01)`） |
| license_spdx | string | 必填 | SPDX 标识（如 MIT、MPL-2.0） |
| license_url | string | 必填 | 许可证原文链接（证据） |
| license_notes | string | 可选 | 许可证补充说明（第三方组件、子模块许可） |
| target_kind | enum | 必填 | `nro` / `self_contained_nsp` / `web` |
| build_backend | enum | 必填 | `cmake-switch` / `make-switch` / `devkitpro-make` / `prebuilt` / `none` |
| capabilities | object | 必填 | 固定 5 个键：video/audio/input/save/touch，每个 `{supported: bool, note: str}` |
| default_input_profile | string | 必填 | 必须是 `src/galnx/input` 的内置 profile 名（kb_mouse / generic-vn / krkrsdl2 / krkr-ns） |
| artifact_naming | string | 必填 | 产物命名模板，占位符仅 `{id}` `{version}` `{target}` `{kind}`；后缀必须匹配 target_kind（nro→.nro，nsp→.nsp，web→.nro 或 .nsp） |
| content_layout | object | 必填 | `mode`（romfs / sdmc / none）+ `entry` + `destination` + `notes`；mode 非 none 时 entry/destination 必填 |
| status | enum | 必填 | `ready` / `research` / `blocked`；非 ready 必须有 status_reason |
| status_reason | string | 条件必填 | 非 ready 时必填 |
| artifact_sha256 | string | 可选 | 预编译产物的 SHA-256（64 位十六进制）；空串表示未记录 |
| evidence_urls | array | 必填 | 证据链接列表（仓库内相对路径或 URL），至少 1 条 |
| notes | string | 可选 | 自由备注 |

`capabilities` 的 5 个键是固定集合：video（渲染）、audio（音频）、input（输入）、save（存档）、touch（触摸）。
`supported` 是布尔值，`note` 写清依据（例如「SDL2 renderer through switch-sdl2 + EGL」），避免把「未验证」写成支持。

`content_layout` 表达「游戏内容放在哪里」：

- `romfs`：内容打进 NRO/NSP 的 RomFS（krkrsdl2 的 `data.xp3` → `romfs/data.xp3`）。
- `sdmc`：内容通过 SD 卡目录部署（brewser 的 `index.html` → `sdmc:/switch/brewser/apps/<app-id>/`）。
- `none`：无内容部署步骤。

## 4. 适配器契约

适配器是 Python 对象（`EngineAdapter` 及其子类），只要实现三个方法：

| 方法 | 输入 | 输出 | 作用 |
| --- | --- | --- | --- |
| plan_build(descriptor, manifest, manifest_path) | 描述符 + 已校验 manifest | `BuildStep` 元组 | 生成构建步骤（命令是建议文本，不执行） |
| verify_artifact(descriptor, path, expected_sha256) | 产物路径 | `Check` 列表 | 校验产物：存在、大小、后缀、NRO0/HOMEBREW 或 PFS0 magic、SHA-256 |
| run_spec(descriptor, manifest) | 描述符 + manifest | dict | 给出 harness 参数建议（引擎、load 类型、artifact、arguments、sdmc、notes） |

`BuildStep` 字段：id / summary / command / requires / notes；`to_dict()` 固定 5 键。
`Check` 字段：id / name / status（ok、warn、fail、skip）/ detail / hint；`to_dict()` 固定 5 键，可 JSON 序列化。
`run_spec()` 的键：engine / harness（当前固定 `citron`）/ target_kind / load（`nro` 或 `nsp`）/ artifact / arguments（默认 `["-g", "<artifact>"]`）/ sdmc / notes。

通用 `EngineAdapter` 按 `build_backend` 生成步骤，已覆盖 cmake-switch、make-switch、devkitpro-make、prebuilt、none 五类后端；只有「需要额外步骤或特殊产物校验」的引擎才需要写子类。

`devkitpro-make` 与 `make-switch` 的区别：`make-switch` 是通用 `make -j8`（内容由构建后的 content 步再部署），而 `devkitpro-make` 对应 devkitPro `switch_rules` Makefile——它把仓库内 `romfs/` 在链接阶段直接内嵌进 NRO，因此 plan 把 `prepare-content`（把内容拷进源码 `romfs/`）放在 `compile` 之前，并跳过构建后的 content 步；改过 `romfs/` 后必须在编译前 `make clean`（libnx 的 romfs 规则依赖文件列表），且构建目录不能含空格（switch_rules 引号缺陷，见 `docs/audit/00-switch-base.md`）。

现有具体适配器：

- `Krkrsdl2Adapter`：8 步（manifest / source / patches / prepare-data / configure / compile / artifact / verify），额外校验 NRO 体积（<1 MiB 会警告，已知带内嵌 data.xp3 的产物约 17.9 MB）。
- `BrewserAdapter`：6 步（manifest / fetch / verify-source / content / install / artifact），内容部署到 sdmc 目录。
- `OnscripterNxAdapter`：6 步（manifest / source / prepare-content / compile / artifact / verify），内容在编译前拷入源码 `romfs/`；额外校验 NRO 体积（<1 MiB 会警告，已知带内嵌内容的产物约 10.4 MB），`run_spec` 附带 Citron 实测记录与「无启动器/无存档菜单 UI/触摸被上游注释」备注。

## 5. 新增引擎接入 checklist

最小接入（推荐先走这条路）：

1. 复制 `examples/engines/krkrsdl2.yaml`（CMake 引擎）或 `examples/engines/onscripter-nx.yaml`（devkitPro Makefile 引擎）为模板，改 id / display_name / upstream_url / pinned_commit / license / target_kind / content_layout。
2. 用 `PYTHONPATH=src python -m galnx engines info <id> --engines-dir <dir>` 验证描述符能被加载且无问题（`problems` 为空）。
3. 在 manifest 的 `engine.adapter` 填该 id；若不想加 `--engines-dir`，把描述符路径写进 manifest 的 `engine.descriptor`（相对 manifest 目录）。
4. 用 `python -m galnx engines plan --manifest <manifest>` 检查步骤与校验项是否符合预期。

需要自定义步骤时的接入：

1. 在 `src/galnx/engines/contract.py` 中继承 `EngineAdapter`，覆写 `plan_build` / `verify_artifact` / `run_spec` 中需要变化的方法。
2. 在 `ADAPTER_FACTORIES` 注册 `{id: YourAdapter}`；未注册的 id 自动使用通用 `EngineAdapter`。
3. 增加对应测试（步骤顺序、产物校验的 ok/warn/fail 分支），并更新本文件。
4. 适配器 id 必须同时出现在 `schemas/game-manifest.schema.json` 的 engine.adapter enum 中，否则 manifest 结构校验会先拒绝。
5. 若引擎使用新的构建后端，还要扩 `descriptor.BUILD_BACKENDS`、`schemas/engine.schema.json` 的 `build_backend` enum 与通用 `EngineAdapter.plan_build` 分支，并补测试（本例 `devkitpro-make` 即如此接入）。

## 6. 内置适配器与证据

### 6.1 krkrsdl2（KiriKiri SDL2）

| 项 | 值 | 证据 |
| --- | --- | --- |
| 上游 | https://github.com/krkrsdl2/krkrsdl2 | 上游仓库 |
| 锁定 commit | 124bdf841f09e7ce02aa99b7b55791a0f7a900ff（2026-10-01） | `docs/builds/001-krkrsdl2-upstream.md` |
| 许可证 | MIT（上游 LICENSE 1063 B，Kirikiri SDL2 Developers；子模块各自保留许可） | `docs/audit/01-engines.md`、`docs/builds/001-krkrsdl2-upstream.md` |
| 构建后端 | cmake-switch（Switch.cmake + Ninja；需 switch-sdl2、FAudio） | `docs/builds/001-krkrsdl2-upstream.md` |
| 产物 | 约 17.9 MB 的 NRO，内嵌 data.xp3；已在 Citron 渲染出 KAG3 demo | `docs/builds/004-krkrsdl2-switch-fixes.md` |
| 已知风险 | KAG3 demo 默认依赖系统字体（MS PMincho / MS Gothic），Switch 无系统字体，需改用内嵌字体的 data.xp3 | `docs/builds/003-kag3-demo-content.md` |

### 6.2 brewser（nx.js Web 运行时）

| 项 | 值 | 证据 |
| --- | --- | --- |
| 上游 | https://github.com/natureglass/Brewser | 上游仓库 |
| 锁定版本 | v0.1.1.31（commit 8040580e92e40a60f704a6478ee296b105212f1b） | `docs/audit/02-web.md` |
| 许可证 | MPL-2.0 | `docs/audit/02-web.md` |
| 产物 | brewser.nro（76,546,123 B，SHA-256 8ce31f5b 开头）为预编译产物，另附 forwarder NSP | `docs/audit/02-web.md` |
| 内容布局 | sdmc:/switch/brewser/apps/&lt;app-id&gt;/（本地 sideload 只需 index.html） | `docs/audit/02-web.md` |
| 运行时前提 | Atmosphère CFW + hbmenu（全内存 application mode），或模拟器 Citron（无需 sigpatches） | `docs/audit/02-web.md`、`docs/experiments/web-02-citron-smoke.md` |
| 已知限制 | --jitless 环境（部分模拟器）下没有 WebAssembly；Mesa Nouveau 不支持 sampler3D/sampler2DArray/samplerCube | `docs/audit/02-web.md` |

### 6.3 onscripter-nx（ONScripter-NX，M4-f 新增）

| 项 | 值 | 证据 |
| --- | --- | --- |
| 上游 | https://github.com/clamintus/onscripter-nx | 上游仓库 |
| 锁定 commit | a8439a86393f74c503d28df176f010ca544af56f（2026-01-14，v0.3.1） | `docs/builds/007-onscripter-nx.md` |
| 许可证 | GPL-2.0-or-later（COPYING 为 GPLv2 全文；source/ 25 个文件中 24 个文件头声明 "or any later version"） | `docs/builds/007-onscripter-nx.md` |
| 构建后端 | devkitpro-make（仓库根 Makefile `include $(DEVKITPRO)/libnx/switch_rules`；无 CMake） | `docs/builds/007-onscripter-nx.md` |
| 内容布局 | romfs：编译前把内容拷进源码 `romfs/`，链接时内嵌进 NRO；内容需含 `*define`/`game`/`*start` 与至少一个 `arc.nsa`/`arc.sar`（0 字节占位可过启动门禁） | `docs/builds/007-onscripter-nx.md` |
| 产物 | m4-ons-with-content.nro 10,449,140 B（SHA-256 d8f9bb11 开头）；纯引擎 m4-ons-engine-only.nro 10,437,716 B | `docs/builds/007-onscripter-nx.md` |
| 运行验证 | Citron Nightly 0237a9b88，R1-R5 全部通过（2026-10-30） | `docs/builds/007-onscripter-nx.md` |
| 已知风险 | ①无多游戏启动器（单目录 arc.nsa 模型）②无 KAG 式菜单/存档 UI，rmenu 未定义时右键仅隐藏文字层 ③GPL-2.0-or-later 分发需随附完整对应源码 ④真机未验证，触摸注入代码在上游被整段注释 | `docs/builds/007-onscripter-nx.md` |

## 7. 与 manifest 的一致性校验

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

## 8. CLI 用法

```
# 列出内置适配器（文本 / JSON）
python -m galnx engines list
python -m galnx engines list --json

# 查看单个适配器（锁定版本、许可、产物名、适配器类、能力）
python -m galnx engines info krkrsdl2
python -m galnx engines info brewser --json
python -m galnx engines info onscripter-nx

# 生成构建计划（只校验与打印，不执行构建）
python -m galnx engines plan --manifest examples/manifest.krkr.yaml
python -m galnx engines plan --manifest examples/manifest.packaged.yaml --json
python -m galnx engines plan --manifest examples/manifest.onscripter.yaml

# 使用外部描述符目录
python -m galnx engines list --engines-dir path/to/engines
```

退出码：0 = 成功（plan 全部检查通过）；2 = 校验失败或适配器未知。
`plan --json` 的稳定键：version、manifest、ok、errors、warnings、checks、adapter、engine、build_steps、input_profile（name/source）、expected_artifact、run_spec。
`info --json` 的稳定键：version、engine（19 字段）、adapter（class/methods）、artifact_name、input_profile、problems。

## 9. 输入配置的独立性

`plan` 的输入 profile 来源有优先级：

1. manifest 有 `input.profile` → 使用 manifest 的（`input_profile.source = "manifest"`）。
2. 否则使用描述符的 `default_input_profile`（`source = "engine-default"`）。

引擎配置（描述符）与输入配置（input profile）互不覆盖：描述符只能指定默认值，manifest 始终可以覆盖；改输入映射不需要动引擎描述符。

## 10. 限制与未验证项

- `plan` 不执行任何构建命令，也没有在 2026-10-30 本轮重新构建 krkrsdl2（构建证据来自 `docs/builds/001` / `004`）。
- brewser 的 sdmc 细节（apps 目录、config.json、存档位置）来自只读审计 `docs/audit/02-web.md`，待 M4-b harness 文档产出后对齐，本文件的字段设计已按「可扩展」处理。
- `artifact_sha256` 只对 prebuilt 适配器有意义；源码构建的产物哈希会因工具链与时间戳变化，不应写进描述符。
- `run_spec` 当前 harness 固定为 `citron`，尚未实现真机（hbmenu）启动参数。
- `examples/engines/brewser.yaml` 与内置描述符核心字段一致，但 YAML 折叠文本会让 `license_notes` 等长字符串换行方式不同，因此不做逐字符相等断言。
- `capabilities.touch` 对 brewser 标为支持（Web 层有触摸事件），但未在真机上逐项验证。
- onscripter-nx 的 audio / save / touch 在描述符中标为 `supported: false`：007 的实测只覆盖渲染与输入，音频输出、存档写盘（save*.dat 写 CWD，RomFS 只读场景下可写性未测）、触摸（上游代码被注释）都未验证；video / input 标为 true 且 note 写明 Citron R1-R5 证据。
- onscripter-nx 的 `content_layout.entry` 用虚拟目录名 `ons-content`（示例 manifest 亦如此），表示「把这个目录的内容拷进源码 romfs/」；它不是上游仓库里真实存在的路径，实际游戏内容目录由调用方决定。
- `make clean` 与「无空格构建路径」是 devkitPro Makefile 的硬约束（plan 的 compile 步已写入 make clean；路径约束见 `docs/audit/00-switch-base.md`），本轮未在含空格路径下复测 onscripter-nx。

## 11. 相关文件

- 计划草案：`docs/PLAN_DRAFT_v0.4.md`（§10 M4）
- 构建记录：`docs/builds/001-krkrsdl2-upstream.md`、`docs/builds/004-krkrsdl2-switch-fixes.md`、`docs/builds/007-onscripter-nx.md`
- 审计证据：`docs/audit/01-engines.md`、`docs/audit/02-web.md`、`docs/experiments/web-02-citron-smoke.md`
- 输入层：`docs/input/README.md`
- 打包数据模型：`docs/packaging/README.md`
- 示例：`examples/engines/krkrsdl2.yaml`、`examples/engines/brewser.yaml`、`examples/engines/onscripter-nx.yaml`、`examples/manifest.krkr.yaml`、`examples/manifest.packaged.yaml`、`examples/manifest.onscripter.yaml`
