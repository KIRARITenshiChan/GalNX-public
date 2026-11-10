# GalNX：Nintendo Switch 视觉小说移植框架计划草案

- **文档状态：** 讨论草案 v0.1，供后续与 Agent 协作拆解、验证和修订
- **最后整理日期：** 2026-10-29
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
│ 测试后端：Ryujinx（固定版本） │ 真机部署/日志 │ 测试结果归档   │
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
| Test Backend | 启动模拟器、传入产物、收集日志与退出码 | 第一版至少支持手动/半自动；自动测试逐步增加 |
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
| nx-hbloader | <https://github.com/Atmosphere-NX/nx-hbloader> | Homebrew NRO 加载相关组件 | 研究 NRO 启动机制时参考；不默认要求修改主机系统 |

**提醒：** 第一版尽量不自行构建或修改 CFW。构建应用优先依赖公开 Homebrew 工具链和普通应用 API。

### 7.2 现成 Galgame 引擎移植

| 引擎/项目 | 地址 | 用途 / 可复用内容 | 当前判断 / 风险 |
|---|---|---|---|
| KRKR-ns | <https://github.com/DrFlyingPig/krkr-ns> | KiriKiri / KRKR Switch 移植；基于 krkrsdl2，参考 Kirikiroid2；含启动器、平台适配、兼容补丁、插件、构建和测试资料 | **优先研究样板**。项目明确标注实验性；需按目标游戏验证 XP3、TJS、插件、视频、E-mote、字体与存档兼容性。真机路径对非 ASCII 字符存在限制，实际以项目当前文档为准 |
| RenpySwitch | <https://github.com/jvrcruzGAMES/RenpySwitch> | Ren'Py Switch 构建流水线；下载 Ren'Py/Pygame 相关源码、应用补丁、编译模块并生成 Switch 项目 | 可研究独立 NSP 构建流程。文档使用特定依赖组合；必须验证许可证、当前分支可重复构建性和目标 Ren'Py 版本覆盖范围 |
| Ren2Switch | <https://github.com/Otorhin/Ren2Switch> | Ren'Py 的 Switch 移植/构建工程，fork 自 renpy-switch | 作为第二个 Ren'Py 实现对照；检查它与 RenpySwitch 的源码、依赖和当前维护状态差异 |
| ONScripter-NX | <https://github.com/clamintus/onscripter-nx> | 较旧 ONScripter 版本的 Switch 移植，目标是兼容部分旧 NScripter 游戏；支持触摸与特定控制器操作 | 适合老式 NScripter 样本；文档提到 HD 构建可能增加 CPU 负担。测试游戏和脚本变体覆盖有限 |
| RFVP / rfvp | <https://github.com/xmoezzz/rfvp> | Rust 编写的非官方 FVP 引擎及工具重实现；目标包含 FVP 脚本/资源格式 | **实验研究项，不作为首个里程碑依赖**。仓库列出 Switch NRO 为 experimental，且说明尚未在真实 Switch 上运行；需检查 `platform/switch/README.md`、依赖、渲染/输入/音频后端和实际构建产物 |

### 7.3 Web / JavaScript 运行时与游戏专用样板

| 工具/仓库 | 地址 | 用途 / 可复用内容 | 当前判断 / 风险 |
|---|---|---|---|
| Brewser | <https://github.com/natureglass/Brewser> | 面向 Switch 的完整 Web runtime 外壳；可参考离线 Web 应用的运行、发布和应用管理 | 仓库描述显示 shell 与引擎代码分开；Brewser 不是简单的 HTML 打包器，须检查其运行时分发/调用限制和应用入口机制 |
| nx.js_extended | <https://github.com/natureglass/nx.js_extended> | Brewser 背后的扩展 JavaScript/Web 技术运行时之一，包含 V8、Skia、WebGL 等能力和相应自定义依赖 | Web 方向重点研究对象；依赖链较重，部分包通过自定义 Docker/包仓库提供。验证版本、离线部署、DOM/API 覆盖和许可证 |
| BurialNX | <https://github.com/ETCHDEV/BurialNX> | 基于 nx.js 的 Switch Homebrew loader，面向特定 RPG Maker MV 游戏；有输入、显示、存档路径与诊断示例 | **仅作架构/诊断参考，不应当当作通用 RPG Maker MV 引擎**。仓库明确声明是针对特定游戏的专用运行时，其他游戏不受支持 |

**Web 方向初步假设：** 某些 HTML5/TyranoScript 游戏可能适合通过 Web runtime 适配，而不必移植 Electron 本身。但每个游戏仍要核验其实际发行版本、Electron/NW.js 特有 API、Node API、插件、文件系统访问和存档机制。不得只凭 `index.html` 存在就认定可以直接运行。

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
| NTON | <https://github.com/rlaphoenix/nton> | PC 端 NRO-to-NSP forwarder 生成器；可设置标题、图标、Title ID 等 | **生成的是转发器，不是把 NRO/游戏资源自动装进 NSP 的自包含包**；运行时仍依赖 SD 卡上固定路径的 NRO。其 README 明确提示此类 NSP 安装可能有主机封禁风险，需纳入风险说明 |
| hacBrewPack（NTON 所用） | <https://github.com/rlaphoenix/hacBrewPack> | NSP 构建工具，供 NTON 等项目打包使用 | 接入前确认上游来源、许可证、所需输入/密钥处理方式和当前兼容性；不要将 forwarder 与完整自包含应用混为一谈 |
| nstool | <https://github.com/jakcron/nstool> | NSP/NRO 等相关文件的信息提取与检查工具；NTON 的依赖之一 | 用于构建产物检测时需要固定版本并验证读取范围 |
| switch-nsp-forwarder | <https://github.com/TooTallNate/switch-nsp-forwarder> | NRO forwarder 的模板/相关实现，可研究启动入口 | 仅是转发路线的参考；需单独检查许可证、兼容性和系统风险 |
| nx-link / nxlink | 随 devkitPro / Switch 开发工具链提供；从 devkitPro 文档确认具体包与版本 | 将 homebrew 构建产物通过网络传输/启动，辅助快速调试 | 具体命令、依赖包名与当前版本待实测；不得硬编码只适用于某一主机地址的参数 |

### 7.6 模拟器测试环境

| 工具/源码 | 地址 | 用途 | 当前判断 / 风险 |
|---|---|---|---|
| Ryujinx Canary-1.3.265 源码标签镜像 | <https://gitlab.hugofnm.fr/publicmirrors/Ryujinx/-/tags/Canary-1.3.265> | 用户已找到 1.3.265 构建产物；该镜像列出 `Canary-1.3.265` 标签，对应提交 `4e81a4c2` | 这是第三方公开镜像，不应无条件视为官方可信源。第一步验证源码快照、标签、提交和构建产物的对应关系，并保存本地 commit hash |
| Ryujinx 项目说明 | <https://github.com/Ryujinx> | 原项目公告称原始 Ryujinx 项目已停止，建议关注 Ryubing 或 ryujinx-mirror | 测试环境应按具体分支/commit 固定；不要把“Ryujinx”抽象成永远不变的单一版本 |

**模拟器使用原则：** 将其作为回归测试工具，而非真机兼容性的最终裁判。模拟器配置、固件/密钥来源和测试 ROM/游戏数据由使用者自行合法准备；框架不应将其纳入公开发布包。

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

- 选定项目语言和最小 CLI 方案（初始建议 Python；所有耗时工作通过子进程调用上游工具）。
- 建立仓库结构、配置 schema、日志格式、工作区策略、引擎注册机制。
- 固定 devkitPro/libnx 版本、一个模拟器版本和构建环境说明。
- 对 KRKR-ns、RenpySwitch、Brewser/nx.js_extended 做构建可行性/许可证/维护状态审计。

**验收**

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

### M3：NSP 打包后端

**验收**

- 清楚区分 NRO、forwarder NSP、自包含 NSP。
- 可以自动设置标题、图标、Title ID、版本等元数据。
- 检查 Title ID 冲突，避免不同游戏意外复用。
- 真机上验证最终包的安装与 HOME 菜单启动。
- 在用户文档中明确 forwarder 的资源路径依赖及封禁/系统环境风险。

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

### 第一版需要由用户/Agent 明确的决策

1. 工作台采用 Python CLI 还是其他语言？当前建议 Python CLI，之后才加 GUI。
2. 第一款端到端测试游戏选哪一部？优先依据上游工程可构建性和目标游戏资源可用性决定，而非先选技术风险最高的作品。
3. 第一版只做 NRO + 模拟器，还是同时要求真机 NRO 测试？建议至少保留真实 NS1 的手动验收。
4. NSP 的首个目标是 forwarder 还是自包含包？建议接口同时区分，先用 NRO 把运行时验证完，再做最终 NSP；不要假定转发器等同自包含包。
5. Web 适配的首个目标是否为 Teaching Feeling？在决定之前要先核验具体 PC 发行包、引擎版本和 Electron/Node API 依赖。
6. 输入事件模型要否支持配置热加载？建议初版支持读取外置配置，热加载可以后续实现。

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

- [ ] 审核 devkitPro/libnx、KRKR-ns、RenpySwitch、Brewser/nx.js_extended、NTON、Carafe、Autorun、Ryujinx Canary-1.3.265 镜像的当前状态和许可证。
- [ ] 把每个仓库的精确 URL、commit/tag、最后验证日期和许可证写入 `docs/TOOLCHAIN_AUDIT.md`。
- [ ] 在干净环境中复现一个简单现有 Homebrew 工程的构建，验证开发机到 NRO 的基础路径。
- [ ] 明确本机 Ryujinx 1.3.265 二进制与源码提交的对应关系；如果不能验证，标注为“源码镜像已发现，复现关系未确认”。
- [ ] 建立 `game-manifest` 初版 schema 和 `galnx doctor` / `galnx preflight` 命令。
- [ ] 实现工作区、构建命令执行、stdout/stderr 日志保存、退出码归档。
- [ ] 通过配置调用一个现有适配器生成 NRO，并记录实际构建过程。
- [ ] 在模拟器中完成一次最小启动测试；真实 NS1 测试另行登记，不根据模拟器结果推断。
- [ ] 根据首次构建暴露的问题修订本文，而不是预先实现所有模块。

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

**本草案不是对所有上述工具的兼容性背书。** 它的目的在于为后续调查建立共同清单，逐项将“看起来可能可行”转换为“能复现、有日志、有范围声明的实际结果”。
