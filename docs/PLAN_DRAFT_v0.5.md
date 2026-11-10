# GalNX：Nintendo Switch 视觉小说移植框架计划草案

- **文档状态：** 讨论草案 v0.5（在 v0.4 基础上回填 M1/M2/M3 实现进展：krkrsdl2 在 Citron 出画面、输入注入与输入数据模型落地、自包含 NSP 出包并在模拟器引导成功；真机项待用户设备），供后续与 Agent 协作拆解、验证和修订
- **最后整理日期：** 2026-10-30（v0.5）
- **版本记录约定【v0.2】：** 后续修改在对应位置用 `【v0.x】` 标记并登记到文末“修订记录”；每次升版先把上一版备份到 `Workspace/`（v0.1 备份：`GalNX_移植框架计划草案_v0.1_20261029.md`；v0.2 备份：`GalNX_移植框架计划草案_v0.2_20261029.md`；v0.3 备份：`GalNX_移植框架计划草案_v0.3_20261029.md`）。【v0.4】沿用同一约定，本次升版已备份 v0.3。【v0.5】沿用同一约定，本次升版已备份 v0.4（`GalNX_移植框架计划草案_v0.4_20261030.md`）。
- **暂定项目名：** GalNX（名称可改）
- **目标平台：** Nintendo Switch / NS1（Horizon OS，Homebrew 环境）
- **开发主机：** Windows PC；允许通过 WSL2、Docker 或 Linux 构建环境执行部分工具链
- **重要约定：** 本文中的“已知”表示已找到公开项目或文档，不表示已在本机成功构建，更不表示已在真实主机上验证。所有适配状态均应通过实际测试更新。

---

## 1. 项目目标

构建一个运行于 PC 的、可扩展的 Galgame 移植工作台。它负责组织一部视觉小说从原始游戏目录到 Switch 可运行程序、测试、打包和归档的整个流程。

长期目标是：在已支持的引擎范围内，用户选择本地游戏目录、确认识别结果和适配配置后，框架能够自动生成可安装的 NSP；安装后游戏拥有独立的 HOME 菜单图标与名称，点击即可启动，并提供合理的控制器体验。

### 1.1 目标体验

- 游戏能够通过 HOME 菜单中的独立图标直接启动。
- 每部游戏拥有唯一的 Title ID、标题名、图标、配置和存档隔离策略。
- 通用键鼠模拟是默认输入模式，不要求每个游戏先有专门手柄配置。
- 对已经完成适配的游戏，可选用专门的手柄语义映射，并可通过组合键切换模式。
- PC 端工作台能够管理适配器、依赖版本、补丁、构建日志和测试结果。
- 开发阶段优先使用 NRO 与模拟器进行快速迭代；确认运行稳定后，再验证最终 NSP。
- 保留每次构建的输入、配置、工具版本和输出记录，便于复现与回归测试。

### 1.2 非目标（第一阶段不做）

- 不承诺自动兼容任意 Windows 游戏或任意 Galgame 引擎。
- 不在第一阶段自行开发一套通用视觉小说引擎。
- 不把任意进程内存读写、内核级调试或主机系统修改作为框架的前置条件。
- 不先开发复杂 GUI；先以 CLI、配置文件和清晰的构建日志跑通工作流。
- 不把“生成 NSP”与“游戏可运行”视为同一件事。
- 不随框架分发商业游戏原始资源、商业字体、视频、音频、脚本或其他未获授权的数据。

---

## 2. 设计原则

1. **工作台与运行时分离。** PC 端工作台负责编排流程；实际游戏由 Switch 端的引擎或运行时执行。
2. **引擎适配器优先。** 以引擎为单位复用移植成果，必要时允许单个游戏增加独立补丁。
3. **原始游戏目录只读。** 所有修改均发生在由工作台创建的临时或持久化工作区中。
4. **先构建 NRO，再构建 NSP。** NRO 便于调试；NSP 是后续发布和 HOME 菜单体验的构建目标。二者必须区分。
5. **区分转发包与自包含包。** NRO-to-NSP forwarder 仅提供 HOME 菜单入口，通常仍依赖 SD 卡上的 NRO 和其他文件；自包含 NSP 的运行时与资源布局完全不同。
6. **通用输入先行，游戏语义映射可选。** 默认提供键盘/鼠标事件模拟；只有在有适配配置时才启用游戏专用手柄映射。
7. **模拟器和真机测试互补。** 模拟器用于高频功能回归；真实主机用于硬件兼容、性能和最终体验验收。
8. **所有工具链都锁定版本。** 不依赖随时间变化的 `latest` 作为唯一构建基准；记录 Git 提交、release、镜像标签和依赖版本。
9. **许可证和来源可追踪。** 接入第三方引擎或工具时记录许可证、修改内容、上游来源和分发义务。
10. **允许逐步支持不同技术路线。** Web 游戏、开源/重实现引擎、已存在的原生移植和 Windows 兼容运行时不应被强行塞进同一套执行模型。

---

## 3. 总体架构

```text
┌─────────────────────────────────────────────────────────────┐
│                       GalNX Workbench                        │
│                 PC 端 CLI（后续可加 GUI）                    │
├─────────────────────────────────────────────────────────────┤
│ 项目/游戏清单 │ 识别与检查 │ 依赖锁定 │ 构建编排 │ 日志/报告 │
├─────────────────────────────────────────────────────────────┤
│ 引擎适配器注册表                                             │
│  ├─ KiriKiri / KRKR                                           │
│  ├─ Ren'Py                                                     │
│  ├─ NScripter / ONScripter                                     │
│  ├─ Web / HTML5 / TyranoScript / RPG Maker MV 类              │
│  ├─ FVP / rfvp（实验）                                         │
│  └─ Windows 兼容运行时（备选，不作为默认路线）                │
├─────────────────────────────────────────────────────────────┤
│ 通用输入配置 │ 资源布局 │ 补丁管理 │ NRO 构建 │ NSP 打包     │
├─────────────────────────────────────────────────────────────┤
│ 测试后端：Citron／Ryujinx（固定版本）│ 真机部署/日志 │ 结果归档 │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 模块职责建议

| 模块 | 职责 | 第一版要求 |
|---|---|---|
| CLI / Workbench | 接收命令、读取配置、调度任务 | 必须 |
| Game Manifest | 保存游戏身份、引擎、资源路径、图标、输入配置 | 必须 |
| Engine Registry | 注册可用适配器、报告支持范围与依赖 | 必须 |
| Game Analyzer | 扫描目录、根据文件特征辅助判断引擎 | 可从规则式识别开始；必须允许手动指定 |
| Workspace Manager | 创建可清理、可复现的构建工作区 | 必须 |
| Patch Manager | 对运行时/资源应用有版本和哈希记录的补丁 | 第一版可简化，但接口需预留 |
| Input Profiles | 管理键鼠模拟、语义映射和模式切换 | 先定义配置与事件模型，再逐步集成 |
| Build Backend | 调用上游构建脚本/交叉编译器，输出 NRO | 必须 |
| Package Backend | 输出 forwarder NSP 或自包含 NSP；两种模式不能混淆 | 第二阶段接入也可，但接口应预留 |
| Test Backend | 启动模拟器、传入产物、收集日志与退出码 | 第一版至少支持手动/半自动；自动测试逐步增加。【v0.4】测试后端优先级=①Citron Neo（开发循环，实测能跑 Brewser）②本机留档 Ryujinx 1.3.265（第二意见）③真机 NS1（唯一验收权威）；见 §7.6 |
| Device Backend | 真机部署、命令、日志拉取或诊断接口 | 先做明确可控的传输与日志，避免任意内存读写依赖 |
| Artifact Store | 归档二进制、清单、哈希、构建日志、测试结果 | 必须 |

---

## 4. 标准工作流程

### 4.1 游戏导入

1. 用户选择本地游戏目录。
2. 框架扫描目录结构、入口文件、资源文件类型、可执行文件和已知引擎特征。
3. 输出识别建议及不确定项；用户可以手动指定引擎和游戏版本。
4. 创建游戏清单，原始目录保持只读。
5. 检查授权资源是否由用户自行提供；框架只负责处理资源，不内置或代为分发商业游戏文件。

### 4.2 选择适配器与准备工作区

1. 从引擎注册表选择适配器。
2. 检查宿主工具、交叉编译工具、依赖库、SDK/运行时版本和补丁版本。
3. 将依赖固定到明确版本或 commit；缺失时给出可复现的安装/构建提示。
4. 创建独立工作区，复制或引用只读资源，应用补丁和路径/输入配置。
5. 输出 preflight 报告：已满足、警告、阻断构建的问题分开列出。

### 4.3 构建与测试

1. 调用适配器构建 NRO 或其他引擎规定的中间产物。
2. 对产物进行基础检查：文件存在、大小合理、构建退出码为 0、元数据/资源清单完整。
3. 在固定版本的 Ryujinx 中启动，收集模拟器日志、程序日志、退出码和测试记录。
4. 通过后，再向真实 NS1 部署开发版本（通常先用 NRO），验证硬件表现。
5. 修复兼容性问题；补丁、配置或依赖变化后执行受影响测试和必要回归。

### 4.4 打包与验收

1. 选择以下一种构建目标：
   - **NRO 开发包：** 适合快速部署和调试。
   - **NRO-to-NSP forwarder：** HOME 菜单入口，运行文件仍需位于预期路径，不能称为自包含包。
   - **自包含 NSP：** 将目标运行时、配置和所需游戏数据按该引擎支持的布局组织为独立应用包。
2. 生成唯一且无冲突的 Title ID、标题、发布者、图标和版本信息。
3. 检查安装包清单；确认所需资源没有被意外遗漏，也没有把无权分发的游戏内容带入可分发构建。
4. 真机安装并从 HOME 菜单启动最终 NSP；不以模拟器加载 NRO 代替此项验收。
5. 生成报告并归档：源码版本、依赖、补丁、游戏版本/资源哈希、构建日志、测试结果和输出包哈希。

---

## 5. 输入系统草案

### 5.1 基础模式：键盘/鼠标模拟

所有已适配运行时尽可能实现基础输入模式，不要求游戏拥有专门手柄配置。

建议初始默认值（可配置，不作为不可更改的统一标准）：

| Switch 输入 | 基础模式行为（示例） |
|---|---|
| 右摇杆 | 鼠标指针移动 |
| A | 鼠标左键 |
| B | Escape 或鼠标右键，具体由配置选择 |
| X / Y | 可映射为鼠标中键、Enter、Space 等键 |
| 十字键 / 左摇杆 | 方向键或鼠标微调，按游戏类型选择 |
| ZR / ZL | 可映射为按住 Ctrl、Shift、快进键等 |
| 触摸屏 | 鼠标移动、点击；优先保留原生触摸支持 |

实现要求：

- 输入后端要维护明确的 key-down / key-up、mouse-down / mouse-up 状态，避免长按与释放错误。
- 鼠标指针应处理窗口/画面缩放、宽高比和边缘裁切。
- 支持组合键及组合键优先拦截，触发切换的按键不得再被游戏接收。
- 不同运行时可能有不同输入接口；通用层应输出统一事件，再由适配器转换为 SDL、libnx、浏览器 DOM 或引擎内部事件。

### 5.2 可选模式：游戏专用手柄语义映射

仅当该游戏有经过验证的配置时才提供此模式。语义动作例如：

- `advance_text`
- `confirm_choice`
- `back`
- `open_menu`
- `show_history`
- `auto_mode`
- `skip_hold`
- `previous_choice` / `next_choice`

建议提供组合键切换，例如 L + R + PLUS，但最终按键应可配置，并确认不会与目标游戏的常规操作冲突。切换时显示短暂提示。

### 5.3 输入配置优先级

建议采用以下优先级（由高到低）：

1. 单个游戏覆写配置
2. 引擎级默认映射
3. 框架通用默认映射

适配器需声明其支持哪些语义动作和输入能力；若目标不支持某语义动作，构建器应给出警告，而不是静默吞掉映射。

### 5.4 【v0.5】输入层实现进展（M2 交付）

- **数据模型已落地**（`src/galnx/input/`）：4 个内置 profile（`kb_mouse`/`generic-vn`/`krkr-ns`/`krkrsdl2`）、7 个语义动作（`advance_text`/`confirm_choice`/`back`/`open_menu`/`show_history`/`auto_mode`/`skip_hold`）、7 条冲突规则（`button_duplicate`/`button_ambiguous`/`action_unmapped`/`hotkey_duplicate_combo`/`hotkey_overlap`/`adapter_key_ambiguous`/`mouse_pointer_missing`）、manifest `input` 段与 `schemas/input-profile.schema.json`、CLI `galnx input list|validate`（支持 `--json`，rc 0/2）；pytest 87 项 + 11 subtests 通过。详见 `docs/input/README.md`。
- **模拟器侧注入已实测可用**（`scripts/citron_run.sh` 输入模式）：鼠标点击走 SendInput `mouse_event` 有效；键盘 SendInput 到不了 Citron 的 Qt key handler（`src/citron/bootmanager.cpp:505-560` 的 `keyPressEvent` 有 `if (!first_frame) { event->ignore(); return; }`），改 **PostMessage(WM_KEYDOWN/WM_KEYUP)** 有效；必须等游戏首帧且焦点在渲染子窗口。KAG3 demo 上标题页→正文页 diff≈0.554、正文页 A 键/鼠标推进 diff≈0.556 可复现；B(Esc) 隐藏消息层后同值 diff 可复现往返。
- **未落地/未验证**：真机（libnx/SDL 侧）输入语义与组合键拦截（L+R+PLUS 热键吃掉逻辑）、指针缩放与触摸事件在真机上的表现、KAG3 键位未逐键核验（社区常见默认）。语义取证见 `docs/milestones/M2-kag3-input.md`。

---

## 6. Game Manifest 配置样例

以下为第一版的概念示例，字段和格式需在 M0 中再确定；不是与任何现有上游直接兼容的配置格式。

```yaml
schema_version: 1

game:
  id: example_title
  title: Example Title
  publisher: User
  version: "1.0"
  source_dir: "D:/Games/ExampleTitle"
  source_version: "user-supplied"
  # 可选：对关键资源文件生成相对路径 + SHA-256 清单

engine:
  adapter: tyrano_web
  adapter_version: "git:abcdef123456"
  profile: default
  entry: index.html

switch:
  title_id: "0x0100ABCDEF012000" # 示例 ID；实际构建时必须生成并检查冲突
  icon: assets/icon.png
  target: nro_then_nsp
  display_mode: fit
  save_policy: per_title

input:
  default_mode: keyboard_mouse
  toggle_combo: [L, R, PLUS]
  profile: custom_title

build:
  output_dir: "artifacts/example_title"
  reproducible: true
  clean_workspace_before_build: false
```

注意：Title ID 的具体生成规则、合法性与冲突检查必须根据最终采用的打包工具验证，样例值不可直接复用。

---

## 7. 已知工具链与仓库索引

本节用于 Agent 后续调查。链接指向截至文档日期找到的公开仓库或文档。先做仓库健康度、许可证、构建依赖和真实主机状态审查；不要仅凭 README 将项目标记为“可直接使用”。

### 7.1 Switch 通用开发基础

| 工具/仓库 | 地址 | 用途 | 当前判断 / 待验证事项 |
|---|---|---|---|
| devkitPro 文档 | <https://devkitpro.org/wiki/Getting_Started> | Switch Homebrew 编译环境安装入口 | 作为通用工具链安装参考；记录实际安装版本 |
| devkitPro pacman packages | <https://github.com/devkitPro/pacman-packages> | Switch 相关包定义、依赖包构建信息 | 用于核验 SDL2、音视频库等包版本 |
| libnx（Switchbrew） | <https://github.com/switchbrew/libnx> | Horizon OS Homebrew API | 核心依赖；优先通过 devkitPro 的包管理安装，版本锁定 |
| Atmosphère | <https://github.com/Atmosphere-NX/Atmosphere> | NS1 Homebrew 常见的系统环境背景 | 不作为 GalNX 的依赖库；仅记录真机测试所依赖的环境/版本 |
| nx-hbloader 【v0.2 URL 修正】 | <https://github.com/switchbrew/nx-hbloader> | Homebrew NRO 加载相关组件 | 原 `Atmosphere-NX/nx-hbloader` 已 404；真实仓库为 `switchbrew/nx-hbloader`，`v2.4.5 = 82b95122…`（2025-11-15，ISC）。研究 NRO 启动机制时参考；不默认要求修改主机系统 |

**提醒：** 第一版尽量不自行构建或修改 CFW。构建应用优先依赖公开 Homebrew 工具链和普通应用 API。

**【v0.2】devkitPro 实际安装状态（2026-10-29 实测）**

- 已安装于 `D:\devkitPro`（官方安装器 v3.0.3 + 内置 MSYS2）；`switch-dev` 14 个包 / 434.93 MiB：`devkitA64 r30-1`、`devkita64-gcc 16.1.0-1`、`devkita64-binutils 2.46.0-1`、`devkita64-newlib 4.6.0.20260123-4`、`libnx 4.12.0-1`、`deko3d 0.5.0-1`、`switch-cmake 1.5.2-1`、`switch-tools 1.13.1-1` 等。`aarch64-none-elf-gcc 16.1.0`、`nxlink` 验证通过。
- **安装渠道注意**：`pkg.devkitpro.org` 对直连返回 HTTP 403（Cloudflare），而 devkitPro MSYS2 的 login shell 没有代理变量；需在 `D:\devkitPro\msys2\etc\pacman.conf` 的 `XferCommand` 中显式经本地代理 + 浏览器 UA 下载。换机/CI 必须重做，且不能假定代理端口恒定（本机为 `127.0.0.1:7897`）。
- **构建路径不能含空格**：devkitPro 的 make 工程在 `E:\Othergames\Nintendo Switch\...` 下会因 `$(CURDIR)` 空格拆词失败；目录 junction 与 8.3 短路径都被 MSYS2 解析回长物理路径，同样无效。M0 最小构建改在 `E:\galnx-build\m0-hello` 完成（`m0-hello.nro` 166,085 B，sha256 `a341e775…`，make 退出码 0）。
- 详见 `docs/TOOLCHAIN_AUDIT.md` §8 与 `docs/environment/`。

**【v0.4】工具链刷新复核（2026-10-29 联网实测，`docs/audit/05-toolchain-refresh.md`）**

- 本机 17 个 Switch 相关包 **17/17 与上游 dkp-libs.db 一致、0 个可升级** → 工具链未落后；安装器仍是 2018 年的 v3.0.3，但包仓库为滚动发布，安装器版本不决定工具链版本。
- 锁定基线（三位一体）：`pacman -Q` 快照 + `D:\devkitPro\msys2\var\cache\pacman\pkg` 包缓存（64 包含 SHA-256）+ 产物 SHA-256（`m0-hello.nro a341e775…`）；MSYS2 侧 cmake 4.0.2-1 / make 4.4.1-2 落后于仓库最新（4.4.4-1 / 4.4.1-3），不影响 switch-dev，若升级需单独记录。
- **CMake 空格路径实测通过**：devkitPro `$DEVKITPRO/cmake/Switch.cmake` 在含空格目录下 configure+build 均成功（`m0-cmake.nro` 161,989 B，sha256 `f4c08034…`）；受空格限制的只是 make 模板。→ GalNX 构建后端优先采用 CMake。
- libnx 基线仍取 release `v4.12.0 = 7644c9b2`（`b156b477` 为开发提交，若使用须注明）；Atmosphère 1.12.1（2026-10-16，release 声明支持 firmware 23.0.0）、nx-hbmenu v3.6.1、nx-hbloader v2.4.5 仅作测试环境记录，不作依赖。
- 下一步实测：安装 `switch-sdl2 2.28.5-4` + `switch-freetype 2.13.3-1` 做最小 SDL2 窗口+字体链接验证；音视频 portlibs（ffmpeg/libmpv/openal）后置。

### 7.2 现成 Galgame 引擎移植

| 引擎/项目 | 地址 | 用途 / 可复用内容 | 当前判断 / 风险 |
|---|---|---|---|
| KRKR-ns | <https://github.com/DrFlyingPig/krkr-ns> | KiriKiri / KRKR Switch 移植；基于 krkrsdl2，参考 Kirikiroid2；含启动器、平台适配、兼容补丁、插件、构建和测试资料 | **优先研究样板，且已定为第一款原型（v0.2 拍板）**。项目明确标注实验性；需按目标游戏验证 XP3、TJS、插件、视频、E-mote、字体与存档兼容性。真机路径对非 ASCII 字符存在限制。【v0.2 审计】MIT，HEAD `949faf9a`（2026-10-16）；release `v0.1.0` 的 tag 已移动到 HEAD → 发布 NRO 不可按 tag 溯源，M1 只从源码自建；构建需 devkitPro + CMake 3.31.6 + 自建 FFmpeg 7.1，且依赖仓库外的 `Switch.toolchain.cmake`（KRKR-ns-tools） |
| RenpySwitch | <https://github.com/jvrcruzGAMES/RenpySwitch> | Ren'Py Switch 构建流水线；下载 Ren'Py/Pygame 相关源码、应用补丁、编译模块并生成 Switch 项目 | 【v0.2 审计】**无任何 LICENSE（父仓库 knautilus/RenpySwitch 同）→ 法律硬阻塞，取得书面授权前不接入**。Ren'Py 路线已改为**官方源码独立移植**：`renpy/renpy`（主源码）+ `renpy/renpy-build`（构建仓库），可行性见 `docs/audit/04-renpy-official.md`。【v0.3 审计交付】该专项已完成（`docs/audit/04-renpy-official.md`，7 条记录 / 84,638 B，全部 source-inspected）：基线（【v0.4 更正】）`renpy/renpy` 的 GitHub 并无现代 release tag（只有 7.x 及更早旧 tag）；版本由 **`renpy/renpy-build` 的 tag `renpy-8.5.3.26051504`**（annotated tag `0cacf395…` → commit `7bfab40c…`，2026-05-13）定义，对应 `renpy/renpy` 源码 commit `39895c1e…`（2026-05-16）；官方平台表无 Switch 且明确不支持 cross-compiling；**唯一硬阻塞=CPython 3.12.8 交叉到 devkitA64/newlib**；建议先用 4–6 周 go/no-go 探针，未过则改走 Switchroot Android + 官方 Android 构建 |
| Ren2Switch | <https://github.com/Otorhin/Ren2Switch> | Ren'Py 的 Switch 移植/构建工程，fork 自 renpy-switch | 【v0.2 审计】无许可证、2023-09 停更、父仓库 uyjulian/renpy-switch 已 archived → **不接入** |
| ONScripter-NX | <https://github.com/clamintus/onscripter-nx> | 较旧 ONScripter 版本的 Switch 移植，目标是兼容部分旧 NScripter 游戏；支持触摸与特定控制器操作 | 【v0.2 审计】GPL-2.0-or-later，`v0.3.1 = a8439a86…`（2026-01-14）；构建最简单（make）；但 release 附商业游戏数据 zip（**禁止复用资产**），字体许可未核实。**第二接入候选（视 GPL 决策）** |
| RFVP / rfvp | <https://github.com/xmoezzz/rfvp> | Rust 编写的非官方 FVP 引擎及工具重实现；目标包含 FVP 脚本/资源格式 | **实验研究项，不作为首个里程碑依赖**。仓库列出 Switch NRO 为 experimental，且说明尚未在真实 Switch 上运行。【v0.2 审计】MPL-2.0，`0.7.0 = 99435f22…`（2026-10-19）；需 Rust nightly + build-std + 自定义 target；releases 无 Switch NRO |

**【v0.4】引擎路线复核（2026-10-29 联网实测，`docs/audit/06-engines-refresh.md`，14 条记录）**

- **重大更正：krkrsdl2 上游本体已官方支持 Switch**——`CMakeLists.txt` 含 `if(NINTENDO_SWITCH)` 分支（SWITCH_APP_NAME "Kirikiri SDL2"、作者 uyjulian、`SWITCH_VERSION v2.0.0`、nacptool+elf2nro），`.github/workflows/ci.yml` 矩阵含 `switch`（容器 `devkitpro/devkita64:20241023`），release tag `latest` 附 `krkrsdl2.nro` 12,011,585 B。但 README 完全不提 Switch 且原文声明不支持未修改商业游戏 → 属“有实现、无文档”，随时可能被移除。
  → **第一款原型策略改为双层**：① **krkrsdl2 上游先行**（MIT、CI 出包、可复现；`main HEAD 124bdf84…`，2026-10-01）验证“自有 data.xp3 → NRO”最小闭环；② **krkr-ns 作产品化启动器**（启动器/存档隔离/E-mote/AlphaMovie/LayerExRaster 等增量，`949faf9a…`、实验性、构建依赖仓库外 `KRKR-ns-tools` 与兄弟仓库 `WA2-ns`）。上游 NRO 是单游戏内嵌（`-DEMBED_DATA_PATH=data.xp3`）形态，没有多游戏启动器，因此两者不可互相替代。
- **新增候选（06 §2）**：① `wetor/ONScripter-jh-Switch`（GPL-2.0，`v21.2.1` = annotated `15a6fec3…` → commit `573301c1…`（2026-02-01）；NRO 16,735,572 B；中文 UI + 游戏浏览器；ONScripter Yuri 系，活跃度优于 ONScripter-NX）；② `Erige005/Kirikiroid2-NX`（Kirikiroid2 1.3.9 移植，KiriKiri 自定义 BSD-style 许可，`v1.0.1` = `e96b6034…`，NRO 42,338,934 B；插件缺 E-mote/motion player/scriptsEx 等；构建链最重且需官方 APK 资源）；③ `xmoezzz/siglus_rs`（MPL-2.0，`5f358ef1…`，pre-release `siglus-switch.nro` 14,531,824 B，deko3d 渲染，未真机）。
- **ONScripter 双实现法务注意**：两者的 `COPYING` 均判 **GPL-2.0-only**（无 “or later”）；ONScripter-NX release 内嵌月姬/歌月十夜商业数据 → 只能本地取引擎部分，**禁止下载/再分发其数据 zip**。
- **Ren'Py 复核结论（06 §8）**：8.5.3.26051504 仍是官方最新稳定（SDL2），master `8.99.99` 已全面迁 SDL3 → **移植基线锁 8.5.3，禁止用 master**；官方平台矩阵仍无 Switch；4 个社区移植与 NXPython 逐一复核仍**全部无 LICENSE** → 法律阻塞未解除，继续只作技术参考、禁止接码。
- **版本锁定基线（06 §8.1）**：krkr-ns `949faf9a`（release v0.1.0 的 published/created 时间戳矛盾，资产 2026-10-16 上传，**禁止只按 tag 溯源**）；krkrsdl2 `124bdf84` 或 CI 镜像 `devkitpro/devkita64:20241023`；ONScripter-NX `a8439a86`；ONScripter-jh `35f55c89`（`573301c1` 为 tag 指向 commit）；rfvp `9f07adef` + nightly；siglus_rs `5f358ef1`；Ren'Py 官方 `39895c1e` + renpy-build `7bfab40c`。
- **接入排序（06 §5.1 修订）**：krkrsdl2 上游 → krkr-ns → ONScripter-jh / ONScripter-NX（二选一，接受 GPL-2.0）→ Kirikiroid2-NX（非 SPDX + 重构建链，第三梯队）→ rfvp / siglus_rs（研究项，均未真机、不进首批）→ Ren'Py 独立移植（长期，先解 CPython 交叉）。社区 Ren'Py 移植与 NXPython **一律不接入**。
- **合法测试资源（06 §6，待用户核实）**：首选自建 Ren'Py 工程（生成项目文件 CC0 1.0）；其次 krkrsdl2-kag3-demo（KAG3 自定义“自由修改/分发”条款、非 SPDX，内嵌字体许可需单独核实）；官方 SDK 示例 `the_question`/`tutorial` 资产无明确许可，**仅本地测试**。
- **硬限制（产品级）**：krkr-ns 真机路径（游戏目录/入口 .xp3/SD 路径）不得含中文；必须 .xp3 入口；HBMenu 需按住 R 以完整内存模式加载 NRO。

### 7.3 Web / JavaScript 运行时与游戏专用样板

| 工具/仓库 | 地址 | 用途 / 可复用内容 | 当前判断 / 风险 |
|---|---|---|---|
| Brewser | <https://github.com/natureglass/Brewser> | 面向 Switch 的完整 Web runtime 外壳；可参考离线 Web 应用的运行、发布和应用管理 | 【v0.2 审计】MPL-2.0（LICENSE 为准；package.json 写 MIT 属冲突）；`v0.1.1.31 = 8040580e…`（2026-09-17；release 名称 `Brewser v0.1.131`）；`brewser.nro` 76,546,123 B / sha256 `8ce31f5b…`，另带 `brewser-forwarder.nsp`；默认 `make` 只需 node/npm/python（复用预编译引擎），重建引擎才需 devkitPro。**M4 首选评估对象**；但 shell 运行时源码/@switch-web/runtime 不可得，不能作发布依赖。 |
| nx.js_extended | <https://github.com/natureglass/nx.js_extended> | Brewser 背后的扩展 JavaScript/Web 技术运行时之一，包含 V8、Skia、WebGL 等能力和相应自定义依赖 | 【v0.2 审计】MIT，`f41fb550`（v1.0.0-beta.6）；引擎为 switch-v8 15.0.243-9 + switch-skia 149-3 + Mesa Nouveau，版本不可随意升。私有 `@switch-web/runtime` 源码不可得 → **不作发布依赖**；上游通用底座为 `TooTallNate/nx.js`（MIT，`v1.0.0-beta.7 = a649611a…`，无 DOM/CSS，可作 HTML5/Canvas 底座） |
| BurialNX | <https://github.com/ETCHDEV/BurialNX> | 基于 nx.js 的 Switch Homebrew loader，面向特定 RPG Maker MV 游戏；有输入、显示、存档路径与诊断示例 | **仅作架构/诊断参考，不应当当作通用 RPG Maker MV 引擎**。仓库明确声明是针对特定游戏的专用运行时，其他游戏不受支持。【v0.2 审计】AGPL-3.0-or-later，`v0.1.1 = c2c6691c…`（2026-10-19）→ **禁止引代码**，只参考设计 |

**Web 方向初步假设：** 某些 HTML5/TyranoScript 游戏可能适合通过 Web runtime 适配，而不必移植 Electron 本身。但每个游戏仍要核验其实际发行版本、Electron/NW.js 特有 API、Node API、插件、文件系统访问和存档机制。不得只凭 `index.html` 存在就认定可以直接运行。

**【v0.2 决策】** Web 方向先做“可行性小验证”而不是直接接引擎：用已校验的 Brewser `brewser.nro` 在本机 Ryujinx 上跑最小 HTML 页（DOM+canvas+JS），实测通过后 M4 再谈 RPG Maker MV；Teaching Feeling 是否为合适首目标待其发行包结构核验。证据与结论见 `docs/experiments/web-01-brewser-smoke.md`。

**【v0.3 实测·阻塞】Web 冒烟结论（2026-10-29）：** 本机 Ryujinx Canary 1.3.265 能正常加载普通 homebrew（nx-hbmenu v3.6.1、hb-appstore v2.3.2 均 `Application Loaded` 并渲染），但 **nx.js 系 NRO 稳定停滞在 `LoadGuestApplication: Loading as homebrew.` 之后**：Brewser `brewser.nro`（76,546,123 B，sha256 `8ce31f5b…`，与 release digest 三方一致）3 次、上游 nx.js beta.7 2 次复现；SD 卡无 `switch/brewser/` seed → 主程序从未执行。差异线索：失败 NRO 代码段约 44 MB（对照 1.7/7.3 MB），根因未定位；约 127 s 后的 `HLE Process map ... process with ID 0` 异常属 Ryujinx 自身 bug（关 discord 集成仍复现）。**结论边界：不能据此判定 Brewser/Web 路线可行或不可行**（Brewser 运行时能力全部未验证，verification_level=`not-verified`）。M4 验证改走：真机（Atmosphère 1.10+ + hbmenu，完整内存 application mode）优先，或换模拟器/版本并用 hbmenu/appstore 作“加载链路健康检查”对照。实验记录：`docs/experiments/web-01-brewser-smoke.md`（158 行）。

**【v0.4 实测·恢复】Web 路线模拟器侧已打通（2026-10-29，`docs/audit/07-web-citron.md` + `docs/experiments/web-02-citron-smoke.md`）**

- 换用 **Citron Neo nightly `0237a9b88`**（Windows msvc / Vulkan 后端）后，Brewser v0.1.131 预编译 NRO **完整运行、2/2 复现**：DOM＋CSS＋inline JS＋`setInterval`＋rAF＋Canvas2D＋`localStorage` 全通过，WebGL 上下文 `OpenGL ES 3.2 Mesa 20.1.0-rc3`；Brewser 完成 `sdmc:/switch/brewser/` 首次 seed（`seed-fingerprint`、`shell/home.html` 39,591 B）→ 主程序真实执行。web-01 在 Ryujinx 上的停滞归因为**模拟器环境问题**，不是 Brewser 缺陷。
- 版本锁定必须锁**资产 SHA-256**：release tag `2026-04-27 = 0076ee8f` 与 Windows 资产的构建 commit `0237a9b88` 不一致 → 基线为 `Citron-windows-nightly-0237a9b88-x64-msvc.zip` 40,497,628 B、sha256 `0d2c9bf3…`，运行后用日志确认 `citron Development Build | main-0237a9b88`。
- M4 开发循环 = Citron（Brewser 官方 `make sdmc`）+ CI 冒烟三件套（窗口标题含 `brewser (64-bit)`；日志含 `Loading brewser (01F5905036D20000)` 与 `Booting game`；`seed-fingerprint` 生成）；Ryujinx 1.3.265 降为第二意见/回归对照；**真机仍是最终验收门槛**（模拟器无固件、硬编码 22.0.0-3.0，显卡/驱动路径与 Tegra X1 不同）。
- 仍未验证：Brewser 私有 `@switch-web/runtime` 源码不可得（不作发布依赖）；RPG Maker MV/TyranoScript 兼容层未验证；输入/音频/联网/长时稳定未测。

### 7.4 Windows PC 兼容运行时（备选路线）

| 工具/仓库 | 地址 | 用途 / 可复用内容 | 当前判断 / 风险 |
|---|---|---|---|
| Autorun（原 Wine-NX） | <https://github.com/autorunhq/autorun> | 在 Switch Horizon OS 上运行 Windows 程序；组合 Wine、CPU 翻译、Mesa、DXVK/VKD3D-Proton 等 | 实验性兼容路线。适合评估缺少原生移植的游戏，不作为默认 Galgame 执行方案。需按游戏逐一测试性能和 API 兼容性 |
| Autorun DLL 仓库 | <https://github.com/autorunhq/autorun-horizon-dlls> | Autorun 使用的 Windows DLL / 运行环境内容 | 作为 Autorun 构建依赖参考；锁定版本，不在本项目中自行复制/分发不符合其许可证的文件 |
| Carafe | <https://github.com/carafe-nx/carafe> | PC 桌面工具，将 Windows 游戏文件夹与 Autorun 运行时/配置制作成独立 NSP；使用者可以设置游戏名和图标 | 是“PC 工作台→独立 NSP”概念的直接参考。重点研究其任务编排、元数据生成、构建日志和打包依赖，不要假设其 Windows 兼容运行适用于每部 Galgame |
| Carafe 构建依赖说明 | 同上仓库 `CONTRIBUTING.md` / `runtime` 目录 | Docker、Node、Rust、hacBrewPack 等构建链 | 后续按其锁定的版本与许可证做依赖审查 |

### 7.5 NRO / NSP 与应用打包

| 工具/仓库 | 地址 | 用途 | 限制/注意事项 |
|---|---|---|---|
| NTON | <https://github.com/rlaphoenix/nton> | PC 端 NRO-to-NSP forwarder 生成器；可设置标题、图标、Title ID 等 | **生成的是转发器，不是把 NRO/游戏资源自动装进 NSP 的自包含包**；运行时仍依赖 SD 卡上固定路径的 NRO。其 README 明确提示此类 NSP 安装可能有主机封禁风险，需纳入风险说明。【v0.2 审计】GPL-3.0，`v3.0.1 = c5d543a9…`（2026-09-15）；Windows PyInstaller；需 prod.keys；FW 12.0.0+ → **仅作对照，不作主路线** |
| hacBrewPack（NTON 所用） | <https://github.com/rlaphoenix/hacBrewPack> | NSP 构建工具，供 NTON 等项目打包使用 | 接入前确认上游来源、许可证、所需输入/密钥处理方式和当前兼容性；不要将 forwarder 与完整自包含应用混为一谈。【v0.2 审计】GPL-2.0，`v3.05 = 745b16ec…`（代码停 2019-10，2026-09 由 rlaphoenix 镜像重建）；C/Makefile，CLI 支持 `--exefsdir/--romfsdir/--titleid/--titlename` 等；需 header_key + key_area_key；输出 RSA-PSS 随机盐**非确定性**。主路线采用“子进程调用”，不把 GPL 代码并入 GalNX |
| nstool | <https://github.com/jakcron/nstool> | NSP/NRO 等相关文件的信息提取与检查工具；NTON 的依赖之一 | 用于构建产物检测时需要固定版本并验证读取范围。【v0.2 审计】MIT，`v1.9.2 = e89ea84b…`（2024-10-14）；默认分支 `development-tip`（锁版本只用 tag）；`-y` 校验不需密钥 → 作为**产物验证第一步** |
| switch-nsp-forwarder | <https://github.com/TooTallNate/switch-nsp-forwarder> | NRO forwarder 的模板/相关实现，可研究启动入口 | 仅是转发路线的参考；需单独检查许可证、兼容性和系统风险。【v0.2 审计】`0.0.8 = 61edd504…`（2026-05-03）；无根 LICENSE，仅 package.json 声明 MIT；TitleID 由 NRO 路径 SHA-256 派生（与 sphaira 一致）→ 只引用其模板思路 |
| nx-link / nxlink 【v0.2 归属修正】 | 上游 `switchbrew/switch-tools`（<https://github.com/switchbrew/switch-tools>），devkitPro 包名 `switch-tools` | 将 homebrew 构建产物通过网络传输/启动，辅助快速调试 | 【v0.2 实测】本机 devkitPro 已装 `switch-tools 1.13.1-1`（v1.13.1 = `22756068…`，2024-10-23，ISC）；命令 `nxlink [-a addr] [-p port] [-s] nro`，`-s` 可回收程序 stdout/stderr（开发期日志通道）。不得硬编码只适用于某一主机地址的参数 |

**【v0.2 决策】NSP 首个目标 = 自包含包（非 forwarder）。** 路线=ExeFS 启动器 + RomFS 游戏数据，由 GalNX 编排 `hacBrewPack`（子进程）+ `nstool`（产物校验）生成，可控制 HOME 图标/名称/存档命名空间；前置条件=用户自备 `prod.keys`（**绝不入库/绝不注入 CI**）+ CFW/sigpatches。forwarder（NTON 路线）只作对照实验，因其仍依赖 SD 卡上固定路径的 NRO、且上游 README 明确提示封禁与 DMCA 风险。详见 `docs/TOOLCHAIN_AUDIT.md` §4.D 与附录 B。

**【v0.4 复核】打包链未变 + keys 合规策略（`docs/audit/08-packaging-refresh.md`，2026-10-29 联网复核）**

- 打包链与测试后端版本自 v0.3 起**无变化**：hacBrewPack v3.05=`745b16ec`、nstool v1.9.2=`e89ea84b`、NTON v3.0.1=`c5d543a9`、switch-nsp-forwarder 0.0.8=`61edd504`、Carafe v0.4.0=`9b69701b`、Autorun test-build-4=`9b717050`；新增登记：nx-hbmenu v3.6.1=`fd26270a`、nx-hbloader v2.4.5=`82b95122`、DBI 912ru=`e5ba7324`（**无许可证，不可分发**）、hb-appstore v2.3.2（停更，可选）。
- **keys 策略（已拍板）**：本机可用 Ryujinx 自带 `portable/system/prod.keys`（12,007 B，sha256 `7bb3b6d2…`；221 条 key 名，含 `header_key` 与 `key_area_key_application_00–15`）与 `title.keys`（11,492 B，sha256 `2b338398…`；打包不需要）。GalNX 只通过 `GALNX_PROD_KEYS` 只读路径读取，只记录 path+size+SHA-256；**不入库、不打印、不进日志/CI、不随产物分发**，`.gitignore` 覆盖 `*.keys`。
- **【v0.5 实测修正】环境变量通道不可用**：本机 DSH 运行时会从子进程环境中剔除名字匹配 `KEY/PASSWORD/SECRET/TOKEN` 的变量 → 计划中的 `GALNX_PROD_KEYS` 环境变量在本环境不可靠。改为**显式命令行参数**：`hacBrewPack --keyset <path>` / `nstool -k <path>`，脚本不内置默认路径、不 fallback；PROVENANCE 仍只记 path+size+SHA-256+mtime。实测可用 keyset：`E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys`（12,007 B，sha256 `7bb3b6d2…`）与 `C:/Users/<user>/AppData/Roaming/citron/keys/prod.keys`（同尺寸，同目录 `title.keys` 11,492 B）。注意：`C:/Users/<user>/.switch/prod.keys` **不存在**（旧记录有误）。
- **【v0.5 实测】hacBrewPack 强制要求 keyset**：即使 `--plaintext` 也报 `Error: Unable to open keyset file`（rc=1）；README 要求 `header_key` + `key_area_key_application_xx`。因此离线/CI 冒烟改用**合成 keyset 模式**，产物标 `NOT INSTALLABLE`，不得作为验收证据。
- **【v0.5 完成】自包含 NSP 出包链已打通**（M3-a，`docs/builds/005-nsp-selfcontained.md`）：ELF→`elf2nso`/`npdmtool`/`nacptool`→hacBrewPack→nstool 校验；产物 PFS0 含 Program/Control/Meta 三个 NCA，CNMT 的 ContentInfo 哈希与实际 NCA SHA-256 逐字节一致；两次构建 SHA-256 不同（非确定性已验证）。产物**未签名**（NCA Header / ACID Signature FAIL 属预期）→ 真机安装需 CFW+sigpatches（M3-d 待用户设备）。
- Lockpick_RCM 仓库已被 DMCA（`shchmue/Lockpick_RCM` HTTP 451，2023-05-04 Nintendo）→ 文档只写社区通行提取步骤概要，不提供下载源、不内置 payload；真机安装仍需 CFW + sigpatches。
- NSP 自包含契约：ExeFS(`main`+`main.npdm`) + control(`control.nacp`+256×256 JPEG 图标) + RomFS(+可选 logo)；输出**非确定性**（RSA-PSS 随机盐）→ 验收用 nstool 结构校验，不做 bitwise 对比；Windows 259 B 路径上限；hacBrewPack 会就地修改输入 → 必须传副本。M3 仍缺：hacBrewPack 二进制来源+哈希、真机 CFW/sigpatches 记录、端到端打包实测。

### 7.6 模拟器测试环境

| 工具/源码 | 地址 | 用途 | 当前判断 / 风险 |
|---|---|---|---|
| Ryujinx Canary-1.3.265 源码标签镜像 | <https://gitlab.hugofnm.fr/publicmirrors/Ryujinx/-/tags/Canary-1.3.265> | 用户已找到 1.3.265 构建产物；该镜像列出 `Canary-1.3.265` 标签，对应提交 `4e81a4c2` | 这是第三方公开镜像，不应无条件视为官方可信源。第一步验证源码快照、标签、提交和构建产物的对应关系，并保存本地 commit hash。【v0.2 实测】**该镜像匿名访问需登录（网页 302→登录页、GitLab API 404）**；官方 `git.ryujinx.app` 当前 TLS 不可达；GitHub `ryujinx-mirror/ryujinx` 已被 DMCA 屏蔽（451，2025-03-06 Nintendo）、`Ryubing/ryujinx` 404 → **官方 tag↔commit 的独立核验本轮未完成**。本机证据内部一致：`Ryujinx.exe` ProductVersion `1.3.265+4e81a4c`，同目录源码 zip 的 7z 归档 Comment=`4e81a4c2f4fee6f31e28fbb129759ec2369da6eb`。策略=本机二进制+源码 zip 只读留档 + SHA-256 校验 + 断网禁更新，证据等级标 `not-verified` |
| Ryujinx 项目说明 | <https://github.com/Ryujinx> | 原项目公告称原始 Ryujinx 项目已停止，建议关注 Ryubing 或 ryujinx-mirror | 测试环境应按具体分支/commit 固定；不要把“Ryujinx”抽象成永远不变的单一版本。【v0.2 实测】原组织 GitHub 仅剩 `.github` 仓库；现状=`Ryubing` fork（自管 GitLab `git.ryujinx.app`，MIT）+ 本机 1.3.265 留档。更新端点 `update.ryujinx.app` 在本机日志中 SSL 失败 → 按“离线固定环境”使用 |
| Citron Neo（第二测试后端）【v0.4 新增】 | <https://github.com/citron-neo/emulator> | Switch 模拟器（Citron 代码库续作）；Web/Brewser 开发循环与回归冒烟 | 【v0.4 实测】GPL-3.0-or-later；HEAD `c3aa70f8`（2026-10-25），597★/93 open，**无公开 CI**；最新 release tag `2026-04-27 = 0076ee8f`，但 Windows 资产构建 commit 为 `0237a9b88`（≠ tag）→ 锁资产 `Citron-windows-nightly-0237a9b88-x64-msvc.zip` 40,497,628 B / sha256 `0d2c9bf3…`。实测能完整运行 Brewser v0.1.131（见 §7.3）。**仅作外部工具，不捆绑不分发其代码，GPL 不传染；模拟器≠真机** |

**模拟器使用原则：** 将其作为回归测试工具，而非真机兼容性的最终裁判。模拟器配置、固件/密钥来源和测试 ROM/游戏数据由使用者自行合法准备；框架不应将其纳入公开发布包。

**【v0.2 实测】启动方式与已知坑：** 必须以**非管理员**启动（`E:\Othergames\Nintendo Switch\Ryujinx-canary\Run.bat` 用 `runas /trustlevel:0x20000` 降权；直接以管理员运行会报 “Ryujinx is not intended to be run as administrator.”）。若报 CET/硬件强制堆栈保护错误，按 `启动不了的解决办法.txt` 在 Windows 安全中心→Exploit Protection 中为该 exe 关闭硬件强制堆栈保护。自动化测试时的日志目录=`portable/Logs/`，文件名含版本与时间戳。

**【v0.4】模拟器生态现状（2026-10-29 联网核查）：** `suyu-emu/suyu` 已被 DMCA（GitHub 451）、`Eden-Emulator/eden` / `sudachi-emu/sudachi` / `Ryubing/CANARY` 均 404、Ryujinx 上游 TLS 不可达且镜像需登录/GitHub mirror 451 → **当前可公开访问的活跃开源 Switch 模拟器只剩 Citron Neo**。因此测试环境必须依赖本机留档 + 资产 SHA-256，不假定可在线获取；无论 Citron 还是 Ryujinx，都不能替代真机验收。

**【v0.5】Citron 自动化 harness（`scripts/citron_run.sh`，819 行）**：非管理员启动（`runas /trustlevel:0x20000`）、sdcard staging、`PrintWindow` 截图、日志切片、单行 JSON 结果、失败码（`no_window_or_boot`/`citron_already_running`/`input_helper_failed` 等）；支持 `--nro` 与 `--game/--nsp`（NSP 以 `-g` 直接加载），输入注入 `--input-click X,Y` / `--input-keys LIST`。**Citron 为单实例**（yuzu 血统，第二个实例只做转发）→ 并发任务必须时间窗排队：跑前 `tasklist | findstr /i citron` 确认 0 实例、以 `citron_already_running` 失败码为准，禁止 `--allow-existing` 抢占或 kill 他人进程。**M3-b 实测**：自包含 NSP 被 Citron 直接加载并运行（窗口标题 `m0-hello (64-bit) | 1.0.0`、日志 `Booting game: 0100000000001000 | m0-hello`、画面渲染 `Hello World!`）→ 未签名 homebrew NSP 在模拟器可运行，但**不能据此认定真机可安装**。详见 `docs/environment/citron-harness.md` 与 `docs/milestones/M3-nsp.md`。

### 7.7 可作为旁支研究、但暂不进入 GalNX 核心的工具

| 项目 | 地址 | 与本项目的关系 | 结论 |
|---|---|---|---|
| ReXGlue SDK | <https://github.com/rexglue/rexglue-sdk> | Xbox 360 PowerPC 静态重编译工具/运行时 | 主要针对 Xbox 360 游戏，不是 Galgame 核心路线；仅在之后研究主机版本代码重编译时参考 |
| XenonRecomp | <https://github.com/hedge-dev/XenonRecomp> | Xbox 360 机器码转 C++ 的静态重编译工具 | 不列入第一阶段依赖 |
| XenosRecomp | <https://github.com/hedge-dev/XenosRecomp> | Xbox 360 Xenos 着色器转换工具 | 不列入第一阶段依赖 |

---

## 8. 主机调试、存储与内存访问策略

### 8.1 第一阶段必须有的调试能力

- 运行时日志：初始化、资源加载、输入事件、存档、异常和退出原因。
- 日志导出：写入 SD 卡，或通过受控网络通道回传 PC。
- 可选诊断接口：报告引擎版本、游戏场景、FPS/帧时间、内存水位、当前输入模式、资源加载失败等。
- 构建产物部署、日志拉取与测试报告归档。
- 运行时崩溃后保留最近一段日志；敏感路径和用户内容可选择性脱敏。

### 8.2 不作为前置条件的能力

- 对任意游戏进程做无约束的内存读写。
- 修改任意主机进程或系统状态。
- 依赖未核实的特权接口来完成普通测试。

优先在自己控制的运行时中实现调试命令和诊断点。这比外部随意修改地址更容易复现，也更不容易因版本变化而失效。若后续确有需要，再独立评估合法、受控的调试方案。

---

## 9. 测试策略与验收矩阵

### 9.1 统一测试层次

1. **静态/预检：** 资源清单、配置格式、Title ID 冲突、依赖检查、构建工具版本检查。
2. **构建测试：** 适配器构建成功、输出文件存在、日志不含已知阻断错误、资源布局齐备。
3. **模拟器冒烟测试：** 启动、标题画面、输入、存档、音频、返回/退出、日志导出。
4. **真机冒烟测试：** 在实际使用模式启动，验证内存模式、性能、手柄、触摸、音视频和长时间稳定性。
5. **最终 NSP 验收：** 独立图标、名称、Title ID、安装、HOME 菜单直接启动、存档隔离、卸载/重装行为。
6. **回归测试：** 引擎、输入层、打包器或工具链变更后，重新运行受影响的测试集。

### 9.2 第一部游戏的最低验收标准

- 原始游戏目录不被修改。
- 通过一个命令或一份声明式配置完成预检和构建。
- 可以生成有效的 NRO。
- 能在固定版模拟器上启动，并且日志可以被框架收集。
- 能在真实 NS1 上手动完成基本流程；模拟器通过不代表此项自动通过。
- 基础键鼠模式可推进文本、点击选项、操作菜单和退出游戏。
- 若该游戏完成语义映射，则可通过组合键切换模式，且切换热键不会误传给游戏。
- 存档可持久化并与其他游戏隔离。
- 生成的 NSP 类型明确标识为 forwarder 或自包含包。
- 真机安装后的 HOME 菜单图标与标题正常；点击可启动预期游戏。
- 保存依赖版本、源码 commit、构建日志、游戏资源哈希和测试结果。

---

## 10. 里程碑草案

### M0：框架骨架和工具链审计

**工作项**

- [x] 【v0.2 已完成】选定项目语言和最小 CLI 方案：**Python CLI**；所有耗时工作通过子进程调用上游工具。
- [ ] 建立仓库结构、配置 schema、日志格式、工作区策略、引擎注册机制（仓库骨架与 `docs/` 已建，schema/CLI 待实现）。
- [x] 【v0.2 已完成】固定 devkitPro/libnx 版本、一个模拟器版本和构建环境说明（见 `docs/TOOLCHAIN_AUDIT.md` §8、`docs/environment/`；模拟器按本机 1.3.265 留档，标 `not-verified`）。
- [x] 【v0.2 已完成】对 §7 全部仓库（含 krkr-ns、RenpySwitch、Brewser/nx.js_extended、NTON/hacBrewPack、Carafe、Autorun、Ryujinx）做状态/许可证/构建可行性审计 → `docs/TOOLCHAIN_AUDIT.md` v1.1（26 个上游对象 / 27 条记录）。
- [x] 【v0.2 已完成】Ren'Py 官方源码独立移植可行性专项审计（`docs/audit/04-renpy-official.md`）。
- [x] 【v0.4 完成】Brewser 最小 Web 冒烟实验：web-01 在 Ryujinx 上阻塞（`not-verified`），web-02 换 Citron Neo 后**通过（2/2）**（见 §7.3）；记录 `docs/experiments/web-01-brewser-smoke.md`、`docs/experiments/web-02-citron-smoke.md`。
- [x] 【v0.4 完成】模拟器最小启动测试：Citron Neo nightly 成功加载运行 hbmenu v3.6.1、hb-appstore v2.3.2、Brewser v0.1.131 等 homebrew NRO（日志+截图见 `workspaces/web-02/evidence/`）；Ryujinx 1.3.265 亦能加载 hbmenu/appstore。**残余**：`m0-hello.nro` 尚未单独冒烟 → 移入 M1 首项。

**已完成验收（2026-10-29 实测）**

- devkitPro Switch 工具链补全并验证：`switch-dev` 14 包 / 434.93 MiB；`aarch64-none-elf-gcc 16.1.0`、`libnx 4.12.0-1`、`nxlink` 可用。
- 最小 Homebrew 构建通过：`m0-hello.nro` 166,085 B / sha256 `a341e775…`，`make` 退出码 0（构建须在无空格路径，见 `workspaces/m0-hello/`）。
- 第一轮审计文档 v1.1 提交；全部 27 条记录带 URL、commit/tag、最后验证日期与许可证字段。
- 【v0.4】4 份联网复核报告落盘：`docs/audit/05-toolchain-refresh.md`（工具链未落后 + CMake 空格路径通过）、`06-engines-refresh.md`（引擎路线复核）、`07-web-citron.md`（Citron 审计 + Web 冒烟通过）、`08-packaging-refresh.md`（打包链未变 + keys 合规）。

**待完成验收（M0 收尾）**

- 能读取一份 manifest，执行 preflight 并生成机器可读报告。
- 报告能区分阻断项、警告和可忽略信息。
- 不需要真正移植游戏就能完成最小端到端的流程编排测试。

### M1：第一款原型游戏跑通 NRO 流程

优先选取已存在 Switch 移植工程、文档相对完整、无复杂 DRM、能够合法使用资源的测试作品。不要为选择一个测试作品引入额外逆向工作。

**验收**

- 框架可以调用上游构建并输出 NRO。
- 输出产物与具体源版本/依赖版本绑定。
- 能在固定 Ryujinx 版本中启动并归档日志。
- 能在真实 NS1 上进行手动验证，记录未通过项。

### M2：输入层与通用配置

**验收**

- 建立统一输入事件模型。
- 基础键鼠模拟可在至少一个原生运行时或 Web 运行时中使用。
- 支持 key-down/key-up、mouse-down/mouse-up、触摸事件和组合键拦截。
- 支持游戏专用映射配置和能力校验。

**【v0.5】状态：M2 完成（模拟器级）。** 输入数据模型/校验/CLI 已实现（`src/galnx/input/`、`galnx input list|validate`、87 项测试）；Citron harness 注入通道打通并复现 KAG3 标题→正文推进；KAG3 输入语义取证见 `docs/milestones/M2-kag3-input.md`。未完成项=真机侧输入、组合键优先拦截、指针缩放/触摸。

### M3：NSP 打包后端

**验收**

- 清楚区分 NRO、forwarder NSP、自包含 NSP。
- 可以自动设置标题、图标、Title ID、版本等元数据。
- 检查 Title ID 冲突，避免不同游戏意外复用。
- 真机上验证最终包的安装与 HOME 菜单启动。
- 在用户文档中明确 forwarder 的资源路径依赖及封禁/系统环境风险。

**【v0.5】状态：M3 部分完成（模拟器级）。** 已完成=①NRO/forwarder/自包含 NSP 三者区分的契约与校验（`src/galnx/package/`）②元数据（标题/图标/TitleID/版本）与 TitleID 冲突检查 CLI（`galnx package plan|check`）③自包含 NSP 出包链（hacBrewPack+nstool）+ **模拟器（Citron）直接引导成功**。**未完成=真机安装与 HOME 菜单启动（M3-d，待用户设备 + CFW/sigpatches）。** 产出：`docs/builds/005-nsp-selfcontained.md`、`docs/milestones/M3-nsp.md`、`docs/packaging/README.md`；风险提示文档已有（forwarder 资源路径依赖、封禁风险）。

### M4：第二种引擎（优先 Web）

**候选**

- 使用 `nx.js_extended`/Brewser 研究 Web 运行环境。
- 使用 BurialNX 学习专用 Web/RPG Maker 游戏的输入、存档和诊断方式，但不要把它当成通用运行时。
- 对类似 Teaching Feeling 的目标，先核验实际 PC 发行版本的 Electron/TyranoScript 结构与 API 依赖，再决定是 Web runtime、原生移植还是其他方案。

**验收**

- 第二个适配器不需要修改核心工作流即可接入。
- 引擎配置、输入配置和构建参数保持独立。

### M5：FVP / rfvp 评估

**验收**

- 确认当前 Switch target 的构建命令、依赖与输出产物。
- 在 PC host 测试中验证脚本和资源读取。
- 查明 Switch 端渲染、音频、文件 I/O、输入和存档后端的完成情况。
- 不将仓库标注的 experimental 状态误写成“已在真机可用”。
- 根据验证结果决定是正式适配、继续研究还是搁置。

### M6：批量构建、回归与可选 GUI

**验收**

- 支持批量预检/构建，单个项目失败不会破坏其他项目。
- 支持构建缓存、依赖锁定、测试报告差异、重新构建和清理工作区。
- 在 CLI 稳定后再设计 GUI，不以 GUI 进度替代引擎兼容工作。

---

## 11. 建议的仓库目录（初稿）

```text
GalNX/
├─ README.md
├─ docs/
│  ├─ ARCHITECTURE.md
│  ├─ ROADMAP.md
│  ├─ TOOLCHAIN_AUDIT.md
│  ├─ TESTING.md
│  └─ decisions/                 # 架构决策记录（ADR）
├─ schemas/
│  └─ game-manifest.schema.json
├─ src/galnx/
│  ├─ cli/
│  ├─ manifest/
│  ├─ analyzer/
│  ├─ engines/
│  ├─ input/
│  ├─ build/
│  ├─ package/
│  ├─ test_backends/
│  ├─ device/
│  └─ artifacts/
├─ adapters/
│  ├─ krkr/
│  ├─ renpy/
│  ├─ onscripter/
│  ├─ web/
│  └─ fvp/
├─ profiles/
│  ├─ input-defaults/
│  └─ engines/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ fixtures/
├─ workspaces/                   # 可被清理，不提交原始游戏数据
└─ artifacts/                    # 构建输出、测试报告；按需忽略/外置
```

具体目录名可以随 Agent 的技术设计调整。原则是不要把第三方仓库源码直接混入核心逻辑；能作为独立子模块、固定版本外部依赖或构建依赖时优先保持边界。

---

## 12. 主要风险与待决策问题

| 问题 | 风险 | 建议验证方式 |
|---|---|---|
| 各类引擎的资源/脚本兼容范围 | 识别引擎不等于所有版本/插件兼容 | 每个适配器建立已测试游戏/版本清单，标注已知问题 |
| 专有引擎和游戏专用插件 | 可能需要大量逆向、重实现或兼容补丁 | 先寻找已有重实现和公开格式文档；给适配设置独立预算与退出条件 |
| Web 游戏依赖 Electron/Node API | 普通 Web runtime 不一定支持文件系统/Node 模块 | 先检查包结构、依赖及调用点，制作最小可运行样本 |
| 资源/补丁版本漂移 | 官方更新可能导致补丁失效 | 记录文件哈希、版本特征和补丁前置条件；不匹配时阻止静默构建 |
| NSP 生成路线 | forwarder 与完整应用包的行为不同 | 在 manifest 明确 `target_package_type`，验收分别进行 |
| 模拟器与真机差异 | 测试误报或漏报 | 记录测试平台和结果来源，不允许自动把模拟器通过改写为真机通过 |
| 可复现构建 | 上游分支变化或远程依赖改变结果 | 固定 commit/tag、容器镜像 digest、包版本和下载哈希 |
| 手柄映射冲突 | 热键误触发游戏操作，按键状态卡住 | 输入层集中拦截热键；测试 down/up、重复和焦点恢复 |
| 存档隔离 | 多游戏互相覆盖或路径变更导致存档丢失 | 以游戏 ID/标题 ID 为命名空间，提供备份/迁移策略 |
| 真机部署及日志 | 网络、应用退出后日志丢失 | SD 卡日志为基础，网络诊断为增强功能 |
| 前向兼容和系统风险 | Homebrew/NSP 转发方式可能受固件变化影响 | 工具与固件组合记录在测试矩阵中；明确风险并避免系统修改成为第一阶段条件 |
| 第三方许可证 | 引擎/工具可能要求署名、源码提供或保留版权声明 | 为每个适配器记录许可证、补丁差异、NOTICE 和分发要求 |
| 【v0.2】上游分发/网络可复现性 | devkitPro 包站对直连返回 403（Cloudflare）；Ryujinx 官方源 TLS 不可达、镜像需登录、GitHub 镜像被 DMCA 屏蔽 | 包下载显式走代理 + UA；把所需包/源码归档进本地缓存并留 SHA-256；报告证据等级如实标 `not-verified` |
| 【v0.2】构建路径含空格 | devkitPro make 工程在含空格路径下 `$(CURDIR)` 拆词失败（junction/短路径均无效） | 构建工作区强制放在无空格路径（如 `E:\galnx-build\`），产物归档回带空格的工作区 |
| 【v0.2】Ren'Py 交叉编译 | 官方无 Switch 平台且明确不支持 cross-compiling；唯一硬阻塞是 CPython 3.12.8 → devkitA64/newlib | 先做 4–6 周 go/no-go 探针；未过则改走 Switchroot Android + 官方 Android 构建 |
| 【v0.2】GPL/AGPL 传染 | hacBrewPack 为 GPL-2.0、Carafe/Autorun 为 GPL-3.0、BurialNX 为 AGPL-3.0 | 一律以子进程/文档参考方式隔离；不复制其代码进 GalNX 源树 |
| 【v0.3】模拟器无法加载 nx.js 系 NRO | Ryujinx Canary 1.3.265 加载 Brewser/上游 nx.js 的 NRO 时停在 guest 启动前（根因未定位，代码段约 44 MB 为差异线索）；普通 homebrew 正常 | **【v0.4 已缓解】**换 Citron Neo nightly 0237a9b88 后 Brewser 完整运行 2/2 → 归因 Ryujinx 环境问题；Ryujinx 降为第二意见 |
| 【v0.4】模拟器生态萎缩 / DMCA | Suyu 已 451、Eden/Sudachi/Ryubing 404、Ryujinx 官方源不可达、Lockpick_RCM 451 → 依赖面收窄，长期可维护性差 | 测试后端多版本本机留档并记录资产 SHA-256；不把模拟器放入发布路径；真机为最终依据 |
| 【v0.4】Citron 资产≠tag / GPL | release 资产由 nightly commit 构建，与 tag commit 不一致；仓库为 GPL-3.0-or-later | 锁**资产 SHA-256** 而非 tag；仅作外部工具，不捆绑/不分发其代码（GPL 不传染） |
| 【v0.4】keys 合规 | keyset 属用户主机派生数据，分发/入库/入日志有法律与安全风险 | `GALNX_PROD_KEYS` 只读、只记录 path+size+SHA-256、`.gitignore` 覆盖、日志脱敏、CI 禁注入 |
| 【v0.4】NSP 非确定性构建 | hacBrewPack 用 RSA-PSS 随机盐，两次产物不同 | 不做 bitwise 对比；用 nstool 结构校验 + TitleID/名称/图标断言 + 输入哈希 |
| 【v0.5】hacBrewPack 强依赖 keyset | 即使 `--plaintext` 也要求 keyset（rc=1），CI/离线环境无 keyset 无法真实出包 | 真实模式=显式 `--keyset` 参数（不内置路径/不 fallback）；CI 只跑合成 keyset 冒烟并标 `NOT INSTALLABLE`；keyset 只记元数据不入库 |
| 【v0.5】homebrew NSP 未签名 | 无任天堂私钥 → NCA/ACID 签名 FAIL 属预期；Citron 可运行，真机需 CFW+sigpatches，且属封禁风险面 | 模拟器结果不得冒充真机结论；真机验收（M3-d）只在用户设备+CFW 下进行并如实记录；用户文档写明风险 |
| 【v0.5】Citron 单实例与模拟器竞态 | 同 yuzu 血统只能有一个实例跑游戏；多 Agent/多任务并发会互相阻塞甚至误杀进程 | harness 内置 `citron_already_running` 失败码；跑前 tasklist 检查、禁止 `--allow-existing` 抢占；多任务用时间窗排队（M2-c/M3-b 已实践） |
| 【v0.5】DSH 环境变量脱敏 | 运行时剔除名字含 `KEY/PASSWORD/SECRET/TOKEN` 的子进程变量 → `GALNX_PROD_KEYS` 等通道失效 | 改用显式参数传 keyset 路径；文档与脚本不得依赖此类环境变量 |

### 第一版需要由用户/Agent 明确的决策

1. 【v0.2 已拍板】工作台采用 **Python CLI**（之后才加 GUI）。
2. 【v0.2 已拍板】第一款端到端测试游戏 = **krkr-ns**（KiriKiri 引擎，源码自建；tag 已移动故不以 release NRO 为基线）。【v0.4 细化】KiriKiri 走**双层路线**：先用 `krkrsdl2` 上游本体（MIT、官方 CI 出包，HEAD `124bdf84`）验证「自有 data.xp3 → NRO」可复现构建，再用 krkr-ns 做启动器产品化（详见 §7.2【v0.4】引擎路线复核）。
3. 【v0.2 已拍板】第一版**先 NRO + 模拟器**，同时保留真实 NS1 的手动验收项（用户已有可用 NS1 真机）；不以模拟器结果冒充真机结果。
4. 【v0.2 已拍板】NSP 首个目标 = **自包含包**（ExeFS+RomFS），forwarder 仅作对照实验。
5. 【v0.3 已完成·阻塞】Web 方案先做 **Brewser 最小冒烟可行性验证** → 已执行并交付 `docs/experiments/web-01-brewser-smoke.md`：本机 Ryujinx 1.3.265 无法加载 nx.js 系 NRO（普通 homebrew 对照正常），结论 `not-verified`；M4 验证改走真机或换模拟器/版本。Teaching Feeling 是否适合作为首个 Web 目标，待其发行包结构/Electron/Node 依赖核验后再定。
6. 【v0.2 已延后】输入事件模型初版只读外置配置，**配置热加载延后**。
7. 【v0.5 已拍板】keyset 传参改**显式 `--keyset` 路径**（不依赖环境变量、不内置默认路径、不 fallback）；CI/离线冒烟只跑合成 keyset 并标 `NOT INSTALLABLE`。
7. 【v0.2 新增·已拍板】**GitLab 路线绕行**：用户在本机无法注册/登录 GitLab，也不接受依赖需登录的镜像；GalNX 不依赖任何 GitLab 资源，Ryujinx 改为“本机留档 + SHA-256 校验 + 断网使用”，证据等级标 `not-verified`。
8. 【v0.2 新增·已拍板】**Ren'Py 方向**：不接入任何无许可证的社区移植仓库；以 `renpy/renpy`（主源码）+ `renpy/renpy-build`（构建仓库）的**官方源码独立移植**为方向，可行性见 `docs/audit/04-renpy-official.md`（结论：唯一硬阻塞=CPython 3.12.8 交叉编译，建议先 4–6 周 go/no-go 探针）。
9. 【v0.4 已拍板】**测试后端优先级**：Citron Neo（开发循环/CI 冒烟，实测可跑 Brewser）→ 本机留档 Ryujinx 1.3.265（第二意见/回归对照）→ 真机 NS1（唯一验收权威）；模拟器结果不得写成真机通过。
10. 【v0.4 已拍板】**keys 使用策略**：直接使用本机 Ryujinx 自带 `prod.keys`/`title.keys`（用户已授权，本机自用）；框架只读、只记录元数据，禁止入库/入日志/进 CI/随产物分发；真机提取只写文档步骤（Lockpick_RCM 已被 DMCA，不提供下载源、不内置 payload）。
11. 【v0.4 已拍板】**构建后端改用 CMake**（含空格路径实测通过），make 模板仅作参考；构建根仍建议无空格路径。

---

## 13. Agent 协作方式建议

为了避免 Agent 在尚未验证上游工具前就大量写抽象层，建议按以下顺序推进：

1. **审计先于实现。** 逐个阅读所选仓库的 README、LICENSE、构建脚本、依赖定义、最近提交与已知问题。
2. **先复现上游。** 每次只选一个工具链，记录宿主环境、命令、产物、失败原因，不要直接把上游失败归咎于 GalNX。
3. **先建立最小端到端样板。** 从 manifest 读取一个已存在的移植工程，调用其构建脚本，输出 NRO，启动模拟器并归档日志。
4. **观察重复步骤再抽象。** 先实际构建两种工程，再决定哪些内容应进入统一接口，以免过早设计过度通用的插件系统。
5. **每项工作带有验收条件。** 不接受只新增代码而没有构建记录、测试结果或明确阻塞说明的里程碑。
6. **将研究结果落入文档。** 每个适配器维护 `README.md` 或独立兼容性矩阵，说明已验证、部分验证、未验证和不支持的项目。
7. **不要让 Agent 下载或提交商业游戏数据。** 测试资源由用户自行提供；测试 fixtures 应使用自制或可合法再分发的数据。

每次 Agent 完成任务，建议更新：

- `docs/TOOLCHAIN_AUDIT.md`：工具链状态、commit、依赖、许可证、可复现步骤。
- `docs/TESTING.md`：模拟器/真机环境、测试日期、测试结果和日志位置。
- `docs/decisions/`：需要长期保留的架构决定与原因。
- 版本化的 manifest/schema 和适配器兼容性声明。

---

## 14. 第一轮实际执行清单

以下清单适合作为计划获批后的第一个 Agent 任务集，不要求一次性实现全部功能。

- [x] 【v0.2】审核 devkitPro/libnx、KRKR-ns、RenpySwitch、Brewser/nx.js_extended、NTON、Carafe、Autorun、Ryujinx Canary-1.3.265 镜像的当前状态和许可证 → `docs/TOOLCHAIN_AUDIT.md` v1.1：26 个上游对象 / 27 条记录，全部带字段。
- [x] 【v0.2】把每个仓库的精确 URL、commit/tag、最后验证日期和许可证写入 `docs/TOOLCHAIN_AUDIT.md`（含未验证清单与需修正 URL：nx-hbloader、nx.js、nxlink、Ryujinx 镜像是重点）。
- [x] 【v0.2】在干净环境复现一个简单 Homebrew 工程的构建：devkitPro 补装（14 包）+ `m0-hello.nro`（166,085 B，sha256 `a341e775…`，make 退出码 0，`workspaces/m0-hello/`）。
- [x] 【v0.2】明确本机 Ryujinx 1.3.265 二进制与源码提交的对应关系 → 本机内部一致（`+4e81a4c` ↔ 7z Comment `4e81a4c2…`）；官方 tag↔commit 独立核验未完成，已标注 `not-verified`（`docs/TOOLCHAIN_AUDIT.md` §5）。
- [x] 【v0.5】建立 `game-manifest` 初版 schema 和 `galnx doctor` / `galnx preflight` 命令 → `galnx 0.1.0`（commit `1ebdb9a`），`doctor` 20 checks 0 fail/warn，`preflight` 可校验 manifest。
- [ ] 实现工作区、构建命令执行、stdout/stderr 日志保存、退出码归档（构建编排仍在脚本层：`scripts/build_nsp_demo.sh`、`scripts/citron_run.sh`；`src/galnx` 尚无 build 模块）。
- [ ] 通过配置调用一个现有适配器生成 NRO，并记录实际构建过程（引擎构建目前是人工/脚本文档化流程，见 `docs/builds/004-krkrsdl2-switch-fixes.md`）。
- [x] 【v0.5】在模拟器中完成一次最小启动测试 → Citron 0237a9b88：`m1-sdl2.nro` 渐变画面、`krkrsdl2` KAG3 标题/正文、自包含 `m0-hello` NSP（`Hello World!`）；真实 NS1 测试另行登记（M3-d），不根据模拟器结果推断。
- [x] 【v0.2】根据首次构建暴露的问题修订本文，而不是预先实现所有模块（本文 v0.2）。
- [x] 【v0.3 完成】Ren'Py 官方源码独立移植可行性审计 → `docs/audit/04-renpy-official.md`（7 条记录 / 84,638 B，全部 source-inspected；结论：唯一硬阻塞=CPython 3.12.8 交叉编译，建议 4–6 周 go/no-go 探针；是否进入探针待拍板）。
- [x] 【v0.3 完成·阻塞】Brewser 最小 Web 冒烟实验 → `docs/experiments/web-01-brewser-smoke.md`（158 行，`not-verified`；本机 Ryujinx 1.3.265 无法加载 nx.js 系 NRO，普通 homebrew 对照正常；M4 改走真机/换模拟器）。
- [x] 【v0.4 完成】工具链刷新复核（本机 17 包 17/17 最新、0 可升级；CMake 空格路径实测通过；Docker 不作基线）→ `docs/audit/05-toolchain-refresh.md`。
- [x] 【v0.4 完成】引擎路线复核与新增候选调研 → `docs/audit/06-engines-refresh.md`。
- [x] 【v0.4 完成】Web 路线复核 + Citron Neo 审计/实测（Brewser 2/2 通过）→ `docs/audit/07-web-citron.md`、`docs/experiments/web-02-citron-smoke.md`。
- [x] 【v0.4 完成】打包链与测试后端复核 + keys 合规策略 → `docs/audit/08-packaging-refresh.md`。
- [x] 【v0.5】M1 首项：把 `m0-hello.nro` 在 Citron/Ryujinx 中冒烟并归档日志（加载链健康检查）→ m0-hello 已以自包含 NSP 形式在 Citron 运行（M3-b）；NRO 形态未单独复跑（ELF→NSO 变体已由 `elf2nso` 流程覆盖）。
- [x] 【v0.5】安装 `switch-sdl2 2.28.5-4` + `switch-freetype 2.13.3-1`，验证最小 SDL2 窗口+字体链接 → `m1-sdl2.nro` 6,740,165 B sha256 `d46ae7c0…`（CMake 12.8 s exit 0，Citron 截图非黑 0.8907）。
- [x] 【v0.5 完成】M1：krkrsdl2 上游源码构建 + Switch 修复补丁 + Citron KAG3 出画面（`docs/milestones/M1-kirikiri.md`、`docs/builds/004-krkrsdl2-switch-fixes.md`）。
- [x] 【v0.5 完成】M2：输入数据模型 + CLI + Citron 注入 harness（`docs/milestones/M2-*.md`）。
- [x] 【v0.5 完成·模拟器级】M3：自包含 NSP 出包链 + Citron 直接引导（`docs/builds/005-nsp-selfcontained.md`、`docs/milestones/M3-nsp.md`）；真机安装=待用户设备。

---

## 15. 资料链接与状态说明

本草案以公开仓库主页、README 和构建文档为主要索引。项目的主分支、发布标签、依赖和兼容性可能变化；后续每次使用之前，均应重新确认。

重点入口汇总：

- [KRKR-ns](https://github.com/DrFlyingPig/krkr-ns)
- [RenpySwitch](https://github.com/jvrcruzGAMES/RenpySwitch)
- [Ren2Switch](https://github.com/Otorhin/Ren2Switch)
- [ONScripter-NX](https://github.com/clamintus/onscripter-nx)
- [rfvp](https://github.com/xmoezzz/rfvp)
- [Brewser](https://github.com/natureglass/Brewser)
- [nx.js_extended](https://github.com/natureglass/nx.js_extended)
- [BurialNX](https://github.com/ETCHDEV/BurialNX)
- [Autorun](https://github.com/autorunhq/autorun)
- [Autorun Horizon DLLs](https://github.com/autorunhq/autorun-horizon-dlls)
- [Carafe](https://github.com/carafe-nx/carafe)
- [NTON](https://github.com/rlaphoenix/nton)
- [hacBrewPack](https://github.com/rlaphoenix/hacBrewPack)
- [nstool](https://github.com/jakcron/nstool)
- [libnx](https://github.com/switchbrew/libnx)
- [devkitPro Getting Started](https://devkitpro.org/wiki/Getting_Started)
- [Atmosphère](https://github.com/Atmosphere-NX/Atmosphere)
- [Ryujinx Canary-1.3.265 标签镜像](https://gitlab.hugofnm.fr/publicmirrors/Ryujinx/-/tags/Canary-1.3.265)
- [ReXGlue SDK（旁支参考）](https://github.com/rexglue/rexglue-sdk)
- [XenonRecomp（旁支参考）](https://github.com/hedge-dev/XenonRecomp)

【v0.2 新增/修正】

- [Ren'Py 官方主源码](https://github.com/renpy/renpy)
- [Ren'Py 官方构建仓库](https://github.com/renpy/renpy-build)
- [nx-hbloader（修正：switchbrew）](https://github.com/switchbrew/nx-hbloader)
- [switch-tools（nxlink 上游）](https://github.com/switchbrew/switch-tools)
- [TooTallNate/nx.js（上游 nx.js）](https://github.com/TooTallNate/nx.js)
- [Citron Neo 模拟器（v0.4 新增，M4 测试后端）](https://github.com/citron-neo/emulator)

> 【v0.2 标注】Ryujinx Canary-1.3.265 标签镜像需登录且官方源当前不可达，本机留档与 SHA-256 为验证基线；GitHub 侧镜像存在 DMCA 屏蔽，**不要**再把 Ryujinx 源码作为可公开再分发的依赖。

**本草案不是对所有上述工具的兼容性背书。** 它的目的在于为后续调查建立共同清单，逐项将“看起来可能可行”转换为“能复现、有日志、有范围声明的实际结果”。

---

## 16. 修订记录

| 版本 | 日期 | 修订摘要 |
|---|---|---|
| v0.1 | 2026-10-29 | 初稿（讨论草案）。 |
| v0.2 | 2026-10-29 | 首轮工具链审计（26 个上游对象 / 27 条记录，`docs/TOOLCHAIN_AUDIT.md` v1.1）与 M0 实测后修订：①【§7.1】nx-hbloader 改 `switchbrew/nx-hbloader`，新增 devkitPro 实际安装状态（14 包、403/代理修复、无空格路径约束、m0-hello）；②【§7.2】KRKR-ns 定为第一款原型、RenpySwitch 无许可证不接入（改官方源码方向）、Ren2Switch 不接入、ONScripter-NX 第二候选（GPL 决策）、rfvp 研究项；③【§7.3】Brewser/nx.js_extended/BurialNX 许可证与可复现性结论、Web 先做最小冒烟；④【§7.5】nxlink 归属修正为 switchbrew/switch-tools，NSP 首个目标拍板“自包含包”；⑤【§7.6】Ryujinx 溯源实测（镜像需登录、官方 TLS 不可达、DMCA 451）→ 本机留档 + `not-verified`；⑥【§10】M0 完成项/新增项；⑦【§12】六项决策落定 + 新增 GitLab 绕行与 Ren'Py 官方源码方向，风险表补 4 行；⑧【§14】执行清单状态更新；⑨【§15】链接修正与新增。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.1_20261029.md`。 |
| v0.3 | 2026-10-29 | Ren'Py 补充审计与 Web 冒烟实验回填：①【§7.2】Ren'Py 官方源码专项审计交付（7 条记录、`8.5.3.26051504 = 39895c1e`、CPython 硬阻塞、4–6 周探针）；②【§7.3】Brewser Web 冒烟实测（本机 Ryujinx 1.3.265 无法加载 nx.js 系 NRO，普通 homebrew 对照正常，`not-verified`，M4 改走真机/换模拟器）；③【§12】风险表补 1 行、Web 决策项更新；④【§14】两项新增任务完成；⑤同步 `docs/TOOLCHAIN_AUDIT.md` v1.2（新增 §4.C.7、更新 R-18）与 `docs/experiments/web-01-brewser-smoke.md`。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.2_20261029.md`。 |
| v0.4 | 2026-10-29 | 全面联网复核与生态修补：①【§7.1】工具链刷新复核（本机 17 个 switch 相关包 17/17 与仓库最新一致、0 可升级；CMake 空格路径实测通过 `m0-cmake.nro` 161,989 B；锁定=pacman -Q 快照 + 包缓存 + 产物哈希三位一体；Docker `devkitpro/devkita64:latest` 不作基线；Atmosphère 1.12.1 声明支持 FW 23.0.0）；②【§7.2】Ren'Py 基线更正（`renpy/renpy` 无现代 release tag；版本由 `renpy/renpy-build` tag `renpy-8.5.3.26051504`=`7bfab40c` 定义，对应 renpy 源码 commit `39895c1e`）；③【§7.3】Brewser 版本表述统一为 v0.1.131（release tag `v0.1.1.31`）+ Web 路线模拟器侧**恢复**（Citron Neo nightly `0237a9b88` 完整运行 Brewser 2/2，探针页 DOM/CSS/JS/Canvas2D/WebGL/localStorage 全通过，M4 冒烟三件套）；④【§7.5】打包链零变化 + keys 合规策略（`GALNX_PROD_KEYS` 只读、只记元数据、不入库/不入日志/不进 CI；Lockpick_RCM 已被 DMCA 不提供下载源；NSP 非确定性）；⑤【§7.6】新增 Citron Neo 测试后端行与模拟器生态现状（suyu 451、Eden/Sudachi/Ryubing 404、Ryujinx 官方源不可达 → 仅 Citron 可公开访问；本机留档 + 资产 SHA-256）；⑥【§10】M0 两项改完成、4 份 refresh 报告记入已验收；⑦【§12】新增 4 条风险 + 3 项决策（测试后端优先级 Citron→Ryujinx→真机、keys 策略、构建后端改 CMake）；⑧【§14】4 项 refresh 标 [x] + 2 项新待办（m0-hello.nro 冒烟、装 switch-sdl2/freetype）；⑨【§15】新增 Citron Neo 链接；⑩【§7.2】krkrsdl2 上游官方 Switch 目标重大更正（CMake `NINTENDO_SWITCH` 分支 + CI matrix switch + release NRO 12.0 MB）→ KiriKiri 改为「krkrsdl2 上游先行可复现 / krkr-ns 启动器产品化」双层路线，新增 ONScripter-jh-Switch、Kirikiroid2-NX、siglus_rs 三个候选并修订接入排序；决策 2 补 v0.4 细化。本版同步产出 `docs/audit/05-toolchain-refresh.md`、`06-engines-refresh.md`、`07-web-citron.md`、`08-packaging-refresh.md` 与 `docs/experiments/web-02-citron-smoke.md`。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.3_20261029.md`。 |
| v0.5 | 2026-10-30 | M1/M2/M3 实现进展回填：①【§5.4 新增】输入层实现进展（`src/galnx/input/` 4 profile / 7 语义动作 / 7 冲突规则、`galnx input list|validate`、87 项 pytest；Citron 注入通道实测=mouse_event 有效、SendInput 键盘无效→PostMessage(WM_KEYDOWN/UP)、first_frame+焦点前提；KAG3 标题→正文 diff≈0.554）；②【§7.5】keys 通道修正（DSH 剔除 `KEY` 类环境变量→改显式 `--keyset`；`C:/Users/<user>/.switch/prod.keys` 不存在，实际路径=Ryujinx-canary 与 citron/keys；hacBrewPack 即使 `--plaintext` 也强制 keyset）+ 自包含 NSP 出包链打通（PFS0 三 NCA、CNMT 哈希一致、非确定性）；③【§7.6】Citron 自动化 harness 与单实例时间窗规程 + NSP 直接引导实测（`m0-hello` 渲染 `Hello World!`）；④【§10】M2 标完成（模拟器级）、M3 标部分完成（真机 M3-d 待用户设备）；⑤【§12】新增 4 条风险（keyset 强依赖/未签名 NSP/单实例竞态/DSH 变量脱敏）+ 决策 7；⑥【§14】执行清单状态同步（5 项打勾、3 项保留待办）。本版同步产出 `docs/milestones/M1-kirikiri.md`、`M2-kag3-input.md`、`M3-nsp.md`、`docs/builds/004-krkrsdl2-switch-fixes.md`、`005-nsp-selfcontained.md`、`docs/packaging/README.md`、`docs/input/README.md`、`docs/environment/citron-harness(-input).md` 等。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.4_20261030.md`。 |