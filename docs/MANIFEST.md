# Game Manifest v1（`schemas/game-manifest.schema.json`）

GalNX 的输入是**每款游戏一份 manifest**（YAML）。它是工作台唯一的配置入口：源目录、引擎适配器、Switch 侧元数据、输入默认值、构建参数。

> 状态（0.1.0 Preview）：manifest 是**唯一的执行配置源**——真实构建只执行 manifest 显式声明的 `build.commands`，引擎描述符只提供身份/版本/补丁/能力，不驱动构建。M1 完成（krkrsdl2 在 Citron 出画面）；输入层数据模型已实现（M2-b，见 [input/README.md](input/README.md)）；打包数据模型/TitleID/契约校验已实现（M3-c，`galnx package plan|check`，见 [packaging/README.md](packaging/README.md)）；引擎注册表与适配器契约已实现（M4-a，`galnx engines list|info|plan`）；内置 3 个适配器 krkrsdl2（nro/cmake-switch）、brewser（web/prebuilt）、onscripter-nx（nro/devkitpro-make，M4-f），见 [engines/README.md](engines/README.md)；批量预检/报告已实现（M6-a，`galnx batch run|diff|clean`）；真实构建执行/缓存/依赖锁定已实现（M6-b，`galnx batch build|lock`、`galnx build run`，见 [batch/README.md](batch/README.md)）。`engines plan` 仍只产出参考计划、不执行（真实构建只执行 manifest 显式声明的 `build.commands`）。

## 快速开始

```bash
# 1) 检查本机构建/测试环境（devkitPro、SDL2 包、keys、模拟器、构建根）
PYTHONPATH=src python -m galnx doctor

# 2) 校验一份 manifest（不构建、不读取游戏内容）
PYTHONPATH=src python -m galnx preflight --manifest examples/manifest.krkr.yaml

# 3) 机器可读输出（可进 CI / 后续 GUI）
PYTHONPATH=src python -m galnx doctor --json
```

安装为命令（可选）：

```bash
pip install -e .
galnx doctor
```

## 字段

| 区块 | 必填 | 说明 |
| --- | --- | --- |
| `schema_version` | 是 | 固定 `1`；不兼容变更时递增 |
| `game` | 是 | `id`（slug，用于目录/产物名）、`title`、`source_dir`（**只读**，GalNX 不写原目录）、可选 publisher/version/notes |
| `engine` | 是 | `adapter` 枚举（krkrsdl2/krkr-ns/onscripter-nx/onscripter-jh/kirikiroid2-nx/renpy/brewser/siglus/rfvp/custom）、`adapter_version`、`profile`、`entry`（相对源目录，如 `data.xp3`）、`options`、可选 `descriptor`（内联引擎描述符；接入未内置适配器时用，见 [engines/README.md](engines/README.md)） |
| `switch` | 是 | `title_id`（16 位十六进制且以 `01` 开头，应用区间 0x0100…–0x0FFF…）、`target`（`nro`/`nsp`）、`title`/`author`/`icon`/`display_mode`/`save_policy` |
| `input` | 否 | `default_mode`（keyboard_mouse/controller/off）、`toggle_combo`（字符串 `L+R+PLUS` 或按钮数组）、`profile`（内置名或 YAML 路径，相对 manifest 目录）；数据模型与冲突检测见 [input/README.md](input/README.md) |
| `build` | 是 | `output_dir`、`reproducible`、`clean_workspace_before_build`、`keys_env`（兼容字段；**实际出包用显式 `--keyset`**，见下）、`romfs_mode`；真实构建可选：`commands`（元素为 argv 数组或 shell 字符串）、`workdir`、`artifact`（相对 workdir）、`env`、`timeout_s`（默认 600）、`inputs`（显式构建输入清单，元素 `path`/`kind`(file 或 tree，默认 tree)/`optional`(默认 false)/`ignore`(glob 数组)；内容摘要纳入缓存键，`optional=false` 且路径缺失时该次缓存按 miss 处理）、`toolchain_components`（必须已知版本的工具链指纹分量，默认 devkitpro_gcc/cmake/ninja；任一声明分量的版本为 unknown 时仍会计算确定性命中键并在命中键里记录 unknown（不静默当成已知版本），同时输出 cache.degraded 警告；本地缓存继续可用，因为缓存目录属于工程根而不是跨机器共享） |
| `package` | 否 | 打包元数据：`type`（self_contained_nsp/forwarder_nsp/nro）、`title_name`/`title_author`/`version`/`title_id`、`icon`、`startup_user_account`、`romfs_dir`；缺省时类型由 `switch.target` 推导。见 [packaging/README.md](packaging/README.md) |

`additionalProperties: false`：拼错字段名直接报错，避免“看起来生效其实没生效”。
- `build.inputs` 中的相对路径按 manifest 所在目录解析；`kind: tree` 会递归收集文件、按相对 POSIX 路径排序后计算 sha256 摘要，任意层级的 `.git`/`.galnx` 恒被忽略，`ignore` 使用 fnmatch 语义（不支持 `!` 取反）。
- 缓存条目 schema 已升到 2：旧 schema 条目会被当作缺失处理（安全重建），不需要手工清理 `.galnx/cache`。
- 未声明 `build.inputs` 的工程不参与构建缓存：声明了 `build.commands` 但没有 `build.inputs` 时，缓存一律按 miss 处理并给出 `cache.miss` 警告（不读也不写 `.galnx/cache`），避免源文件变化后复用旧产物；需要缓存必须显式声明 `inputs`。

## 校验规则（`preflight`）

- manifest 可解析 + 通过 JSON Schema（draft 2020-12）
- `game.source_dir` 存在且可枚举（只读检查）
- `engine.entry` 存在性（缺失只给 warn，适配器可能自己定位入口）
- `galnx engines plan` 额外做引擎一致性校验：`engine.adapter` 必须在注册表内（未知=error）、blocked 适配器=warning；`--engines-dir` 可加载外部描述符
- `title_id` 格式与 `01` 前缀
- `output_dir` 无空格（devkitPro make 模板在含空格路径下会拆词失败）、长度 < 259（Windows MAX_PATH）
- 构建根 `E:/galnx-build` 可写、无空格
- `target: nsp` 时检查 `prod.keys` 元数据（存在性 + `header_key`/`key_area_key_application_*` 关键字 + SHA-256，**不打印内容**）；注意本环境 DSH 会剔除名字含 KEY 的子进程环境变量，出包脚本要求显式 `--keyset <path>`（见 `docs/builds/005-nsp-selfcontained.md`）

## 信任边界：manifest 就是可执行配置（P1-2）

一份 manifest 里的 `build.commands` 会在本机直接执行（argv 数组或 shell 字符串），因此把别人给的 manifest 当成代码来对待：

- **先看后跑**：`galnx build run` 在 spawn 之前总是先打印解析后的执行计划——每条命令、`cwd`、`timeout`、以及 manifest 分配的**环境变量名**（名字命中 `KEY|TOKEN|SECRET|PASSWORD` 的值显示为 `(value hidden)`，值永不打印）。交互式终端下会再问一次 `Execute these commands? [y/N]`，回答不是 y/yes 就中止；CI 用 `--yes` 跳过确认，但计划仍会打印。
- **非交互不默认放行**：stdin 不是 TTY 且没有显式 `--yes` 时，`galnx build run` 与 `galnx batch build` 一律**拒绝执行**命令，stderr 打印 `refusing to execute build.commands: no interactive terminal and no --yes; re-run with --yes to execute`，退出码 2，且不创建任何产物——无头环境/CI/被管道调用的脚本必须自己传 `--yes`。
- **只读预演**：`galnx build run --dry-run` 只解析并打印计划、绝不 spawn；`--json` 时计划走 stderr、报告走 stdout，便于管道消费。
- **不静默跳过**：声明了 `artifact` 却没有 `commands`（或反之）在解析阶段直接报错；两者都没有时执行状态是 `not_configured`，CLI 退出码 3、batch 报告 `build_state=not_configured`，不会被算成构建成功。
- **路径不越界**：`build.workdir` 缺省为 manifest 所在目录；`build.artifact` 必须落在 `workdir` 内（`..` 逃逸直接报错）；`game.output_dir` 同样做越界与 Windows MAX_PATH 检查。
- **环境变量白名单**：执行器只注入 manifest `build.env` 显式声明的变量 + `GALNX_MANIFEST`/`GALNX_PROJECT`，其余继承宿主环境；敏感变量名只以名字出现，不落日志。
- **外部配置不自动信任**：`--engines-dir` 加载的描述符同样只用于计划与校验，不执行构建；`galnx engines plan` 的输出带 `plan_only: true`，人类输出首行是 `plan only: engine descriptors are advisory; nothing is built or executed`。

## 环境变量

| 变量 | 默认 | 用途 |
| --- | --- | --- |
| `GALNX_DEVKITPRO` | `D:\devkitPro` | devkitPro 根 |
| `GALNX_BUILD_ROOT` | `E:\galnx-build` | 无空格构建根 |
| `GALNX_PROD_KEYS` | Ryujinx portable 的 `prod.keys` | 兼容字段（preflight 提示用）；**本环境不可靠**（DSH 剔除含 KEY 的子进程变量）→ 出包请显式 `--keyset`，值不入库不入日志 |
| `GALNX_CITRON` | `workspaces/web-02/citron/citron.exe` | 主测试后端 |
| `GALNX_RYUJINX` | `Ryujinx-canary/Ryujinx.exe` | 对照后端 |
| `GALNX_SCHEMA_DIR` | 仓库 `schemas/` | 覆盖 schema 搜索路径 |

## 已知限制（M0 → M6）

- 无 `test` 子命令（`package plan|check`、`engines list|info|plan`、`input list|validate`、`batch run|build|lock|diff|clean`、`build run` 已有；NSP 出包仍由 `scripts/build_nsp_game.sh` 调用）
- 真实引擎（krkrsdl2/ONScripter-NX/NSP）的 `build.commands` 尚未接入示例：执行器/缓存/锁定本体已验证（demo-build），真实编译命令需在引擎准入时逐个固化；引擎能力与验证等级见 [engines/README.md](engines/README.md) 与 [engines/verification-matrix.md](engines/verification-matrix.md)
- 构建缓存只对 manifest/工具链首行版本敏感（跨机器命中不保证）；`batch` 报告/缓存/日志默认写 `<root>/.galnx/`（gitignore）
- `engine.adapter` 的 schema 枚举不含自定义引擎名：接入新引擎需新增枚举值，或用枚举内名字 + 内联 `engine.descriptor` / `--engines-dir`（见 [engines/README.md](engines/README.md)）
- Title ID 分配块是 GalNX 本地约定（0x01004741…，未注册），只在本仓库注册表内自洽（见 [packaging/README.md](packaging/README.md) §11）
- `input` 段已接入数据模型/校验/冲突检测（M2-b），但 HID 注入、组合键拦截、指针缩放属工作台实现，尚未落地
- 机器相关默认值集中在 `src/galnx/paths.py`，后续做 `galnx config` 时会外置到 profile
