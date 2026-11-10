# Game Manifest v1（`schemas/game-manifest.schema.json`）

GalNX 的输入是**每款游戏一份 manifest**（YAML）。它是工作台唯一的配置入口：源目录、引擎适配器、Switch 侧元数据、输入默认值、构建参数。

> 状态：M1 完成（krkrsdl2 在 Citron 出画面）；输入层数据模型已实现（M2-b，见 [input/README.md](input/README.md)）；打包数据模型/TitleID/契约校验已实现（M3-c，`galnx package plan|check`，见 [packaging/README.md](packaging/README.md)）；引擎注册表与适配器契约已实现（M4-a，`galnx engines list|info|plan`）；内置 3 个适配器 krkrsdl2（nro/cmake-switch）、brewser（web/prebuilt）、onscripter-nx（nro/devkitpro-make，M4-f），见 [engines/README.md](engines/README.md)；批量预检/报告已实现（M6-a，`galnx batch run|diff|clean`）；真实构建执行/缓存/依赖锁定已实现（M6-b，`galnx batch build|lock`、`galnx build run`，见 [batch/README.md](batch/README.md)）。`engines plan` 仍只产出参考计划、不执行（真实构建只执行 manifest 显式声明的 `build.commands`）。

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
| `build` | 是 | `output_dir`、`reproducible`、`clean_workspace_before_build`、`keys_env`（兼容字段；**实际出包用显式 `--keyset`**，见下）、`romfs_mode`；真实构建可选：`commands`（元素为 argv 数组或 shell 字符串）、`workdir`、`artifact`（相对 workdir）、`env`、`timeout_s`（默认 600） |
| `package` | 否 | 打包元数据：`type`（self_contained_nsp/forwarder_nsp/nro）、`title_name`/`title_author`/`version`/`title_id`、`icon`、`startup_user_account`、`romfs_dir`；缺省时类型由 `switch.target` 推导。见 [packaging/README.md](packaging/README.md) |

`additionalProperties: false`：拼错字段名直接报错，避免“看起来生效其实没生效”。

## 校验规则（`preflight`）

- manifest 可解析 + 通过 JSON Schema（draft 2020-12）
- `game.source_dir` 存在且可枚举（只读检查）
- `engine.entry` 存在性（缺失只给 warn，适配器可能自己定位入口）
- `galnx engines plan` 额外做引擎一致性校验：`engine.adapter` 必须在注册表内（未知=error）、blocked 适配器=warning；`--engines-dir` 可加载外部描述符
- `title_id` 格式与 `01` 前缀
- `output_dir` 无空格（devkitPro make 模板在含空格路径下会拆词失败）、长度 < 259（Windows MAX_PATH）
- 构建根 `E:/galnx-build` 可写、无空格
- `target: nsp` 时检查 `prod.keys` 元数据（存在性 + `header_key`/`key_area_key_application_*` 关键字 + SHA-256，**不打印内容**）；注意本环境 DSH 会剔除名字含 KEY 的子进程环境变量，出包脚本要求显式 `--keyset <path>`（见 `docs/builds/005-nsp-selfcontained.md`）

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

- 无 `test` 子命令（`package plan|check`、`engines plan`、`input list|validate`、`batch run|build|lock|diff|clean`、`build run` 已有；NSP 出包仍由 `scripts/build_nsp_demo.sh` 完成）
- 真实引擎（krkrsdl2/ONScripter-NX/NSP）的 `build.commands` 尚未接入示例：执行器/缓存/锁定本体已验证（demo-build），真实编译命令需在引擎准入时逐个固化
- 构建缓存只对 manifest/工具链首行版本敏感（跨机器命中不保证）；`batch` 报告/缓存/日志默认写 `<root>/.galnx/`（gitignore）
- `engine.adapter` 的 schema 枚举不含自定义引擎名：接入新引擎需新增枚举值，或用枚举内名字 + 内联 `engine.descriptor` / `--engines-dir`（见 [engines/README.md](engines/README.md)）
- Title ID 分配块是 GalNX 本地约定（0x01004741…，未注册），只在本仓库注册表内自洽（见 [packaging/README.md](packaging/README.md) §11）
- `input` 段已接入数据模型/校验/冲突检测（M2-b），但 HID 注入、组合键拦截、指针缩放属工作台实现，尚未落地
- 机器相关默认值集中在 `src/galnx/paths.py`，后续做 `galnx config` 时会外置到 profile
