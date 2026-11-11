# GalNX 仓库整理与 0.1 Preview 发布收敛计划

- **文档类型**：工程整改计划 / Release Readiness Plan
- **审查基线**：`KIRARITenshiChan/GalNX-public` 的 `main` 分支，按 2026-11-11 可见内容审查；公开快照记录的私有源提交为 `7306669`，公开提交为 `ff49e0d`
- **目标版本**：GalNX `0.1.0 Preview`
- **核心目标**：不推翻现有架构，不为发布临时扩大功能面；把已经完成的引擎移植成果收敛成可理解、可复现、可审计、可交付的工作台。
- **执行方式**：分任务交给 Agent；每个任务独立分支/提交、先审计后修改、附测试和证据。不得把多项架构改动捆成一个大补丁。

> **执行状态（2026-11-11）：本计划的 P0-1…P1-6 已全部落地并随 0.1.0 Preview 收敛提交；实际结果、偏差与证据见文末 §11「执行状态与偏差记录」。**
> 本文件正文保留审查当时的判断，不再逐条改写；凡与 §11 冲突处，以 §11 为准。
>
> 本文是整理路线，不是要求一次性完成所有长期规划。优先解决会误导使用者、导致构建结果不可信、可能泄漏第三方内容或影响二进制分发的事项。当前进行中的 **GLES2 双平面 / NV12 零拷贝工作应继续独立推进**，不要为了仓库整理而中断或提前宣称完成。

---

## 0. 执行原则与范围

### 0.1 本轮要达成什么

1. 让 README、Manifest 文档、Engine Descriptor、CLI 实际行为和真机证据相互一致。
2. 让公开仓库中的构建步骤在干净环境下可理解、可复现；不能复现的步骤必须明确标注为人工/本机流程，而不是暗示已自动化。
3. 让缓存只在真正相同的输入下命中，避免源代码或工具链变化后错误复用旧产物。
4. 让公开快照和 Release ZIP 有可验证的素材、密钥、二进制及历史隔离流程。
5. 让第三方组件清单对应实际使用的源码版本、构建参数和交付产物。
6. 让后续开发者能够区分：内置适配器、外部 Descriptor、已构建运行时、模拟器验证和真机验证。

### 0.2 本轮明确不做什么

- 不重写 GalNX 的核心架构。
- 不为了 0.1 临时开发 GUI 或 NS 端启动器。
- 不将所有游戏运行时合并成一个统一 NS Host。
- 不要求首发前增加第三款引擎。
- 不把低频、非阻断的视觉细节强行变成发布阻塞项。
- 不把正在进行的 GLES2 双平面零拷贝直接并入仓库清理补丁。
- 不把“代码中存在实现”当成“已在真机验证”。

### 0.3 变更纪律

- 整理工作先从私有主仓库进行；通过测试和审查后，再生成 sanitized public snapshot。
- 不直接在公开镜像中手工修补单独文件。公开仓库继续由私有源仓库导出干净快照。
- 修改 Schema 时，必须同步修改解析器、校验器、示例、文档和测试。
- 涉及运行时的改动，必须提供最小复现样本和回归测试；单纯文档/元数据整理不得改变运行时行为。
- 每个 Agent 任务完成后必须交付：改动文件列表、决策记录、测试命令及结果、尚未解决的问题。

---

## 1. 当前项目基线

以下为本轮整理时应当保留的项目定位和已知状态。若私有主仓库比公开快照更新，以最新真机证据及对应私有提交为准，并同步更新公开快照。

### 1.1 产品定位

GalNX 是 **PC 端 Nintendo Switch Galgame 移植工作台**：负责编排游戏识别、引擎适配、资源预处理、运行时构建、内容暂存、NSP 打包和验证；不自研通用 Galgame 引擎，也不分发商业游戏本体及其受版权保护的资源。

当前采用的主要交付模式是每款游戏生成独立、自包含 NSP，安装后由 Switch HOME 菜单直接启动。PC 工作台是核心产品；NS 端统一游戏库/启动器不是 0.1 前置条件。

### 1.2 已公开的试点与适配路线

公开 README 当前列出四个垂直试点：

- Pilot-01：`kirikiroid2-nx`，晴霁之后定是菜花盛开的好天气（CN）。
- Pilot-02：`rfvp`，IROSEKA FHD。
- Pilot-03：`rfvp`，さくら、もゆ。（CN）。
- Pilot-04：`rfvp`，AKASEKA HD。

README 同时列出 `krkrsdl2`、`onscripter-nx`、`brewser`、`renpy` 等研究路线。必须继续保留“适配器存在 ≠ 具体游戏已验证”的区别。

### 1.3 当前 RFVP 进展（来自项目最新交流，更新 Descriptor 时需对照私有证据）

- SDL2 + GLES2 显示后端已取代原有 CPU SoftRaster 显示路径。
- FVP 动态效果中已发现并修复标题粒子缺失问题。
- NVDEC 硬件视频解码已接入；《樱花，萌放。》和 IROSEKA 的视频样本已能以 60 FPS 播放，无已观察到的慢放或颜色异常；测试也证明播放行为不应被描述成仅针对某个 OP 的专用逻辑。
- 当前正在研究 **GLES2 双平面 / NV12 零拷贝**，目标是避免 CPU RGBA 转换和不必要的读回/上传。该项在完成真机验收前只能标记为 `in_progress` / `experimental`，不能写成已完成能力。
  - **【2026-11-11 更新】** 该项已在 P44 完成并在 AKASEKA HD v1.4.1-test 真机验收（颜色正确、播放流畅，用户 m40951）：1080p 单帧省 ≈9.5 ms（CPU 转换 7.3→1.8 ms、上传 8.29→3.11 MB），并在 P45 同步到 IROSEKA FHD v1.2.5-test / SAKURA MOYU CN v1.3.3-test。
    因此在 `docs/engines/verification-matrix.md` 中记为 `device_verified`；对外表述仍按 §5.3 的规则写「零 CPU NV12→RGBA 转换 + 双平面直传」，不写绝对「零拷贝」。
- 资源读取、缓存、预读、存档惰性编码、音频独立线程等优化已经显著改善实际体验，但公开 Descriptor 的说明必须逐项对照最新构建和证据，不能把过往试验值直接当作最终性能承诺。

### 1.4 当前公开快照暴露出的明确不一致

1. README 的 `galnx build run` 说明写成“由适配器 descriptor 的 `build.commands` 驱动”；但 `docs/MANIFEST.md` 明确写着 `engines plan` 只生成参考计划，真实构建只执行 Manifest 显式声明的 `build.commands`。需要统一文档与真实执行契约。
2. `docs/MANIFEST.md` 仍说明真实引擎构建命令未接入示例，NSP 出包仍由单独脚本完成。这与 README 快速开始中的端到端构建示例容易让读者产生不同预期。
3. README 对 Kirikiroid2-NX 的 Pilot-01 标记真机 PASS；但 `examples/engines/kirikiroid2-nx.yaml` 的 `status_reason` 仍称 Switch 硬件未验证。必须根据真实设备证据裁决，不能自行选择其中一个。
4. RFVP Descriptor 仍有旧版本和旧验证文字，例如 audio `supported: false`、旧的 Citron 说明、旧构建记录。README 已描述更晚的能力。这些状态需要重新核对并更新。
5. RFVP Descriptor 的 `video` 字段实际描述 SDL/GLES 图像渲染，不应让使用者误以为它也代表视频文件解码/播放；电影能力应该单独描述。
6. `cache.py` 当前工具链指纹主要记录 devkitPro GCC 和 CMake 版本；缓存键包括 Manifest 路径、引擎 pin、构建命令、部分 input 和工具链指纹，但没有对所有真实源代码/补丁输入生成完整内容摘要。
7. 公开清理脚本当前的游戏素材规则针对指定路径前缀下的 PNG/JPG/JPEG/WebP/GIF。它解决了已知截图、封面和图标的隔离，但不能单独证明任意路径、任意格式的游戏数据、可执行文件、密钥或证书都不会进入最终 ZIP。
8. README / Manifest 示例和 `paths.py` 中仍可见开发机环境默认值。应将“历史试点记录”和“新用户可复制模板”明确分开。

---

## 2. P0：首发前必须处理

### P0-1：统一 Manifest、Descriptor、Build Runner 的构建契约

**问题**

当前文档存在两种表述：README 暗示 Runner 执行 Descriptor 中的 `build.commands`；Manifest 文档与 `executor.py` 则表明 Runner 读取 Manifest 的 `build.commands`。`executor.py` 在 `config.commands` 为空时返回成功且无命令结果，这可能被误解为“构建已成功”，实际更接近“没有配置构建命令”。

**本轮建议决策：采用最小可交付方案，不在 0.1 前临时引入复杂的 Descriptor/Manifest 自动合并。**

- Manifest 是某款游戏这次构建的最终执行配置来源。
- Descriptor 负责引擎身份、上游来源、固定版本、补丁、平台约束、默认构建说明和能力元数据。
- 若本轮还不实现 descriptor 默认命令注入，README 必须明确写“`build run` 执行 Manifest 中显式声明的 `build.commands`”，不得再写“由 Descriptor 的 build.commands 驱动”。
- 对尚未接入 GalNX Build Runner 的 Pilot，明确标注需运行哪个外部脚本/人工步骤，不得把 `build run` 描述成完整端到端流程。
- `engines plan` 继续保持只生成计划、不执行命令的语义，并在 CLI 输出中明确标记 `plan_only`。

**具体工作**

- [ ] 检查 `src/galnx/build/executor.py`、Manifest parser、BuildConfig、engine descriptor loader 及 CLI `build run` 调用链。
- [ ] 明确空 `build.commands` 的状态：建议返回 `skipped / not_configured`，而不是让用户误认为 build 成功；若为兼容暂时保留零退出码，至少在终端和 JSON 报告中明确显示 `skipped`。
- [ ] 修正文档：README、`docs/MANIFEST.md`、`docs/engines/README.md`、快速开始和示例注释使用同一套术语。
- [ ] 将每个 Pilot 的真实构建步骤写清楚：GalNX CLI 能执行的步骤、仍由脚本执行的步骤、NSP 打包步骤分别列出。
- [ ] 如果将来要实现 Descriptor defaults + Manifest overrides，先单独写 BuildPlan 合并规则和 Schema，再作为 0.2 功能讨论，不与本次文档修正混做。

**验收标准**

- [ ] 空命令不会被误报为构建完成。
- [ ] `galnx build run` 的实际命令来源与文档一致。
- [ ] 每个公开 Pilot 都能明确回答：从源目录到运行时产物，哪一步由哪个命令完成。
- [ ] `--json` / batch report 能区分 `success`、`skipped`、`failed`。
- [ ] 用一个无命令 Manifest、一个最小 demo build、一个真实 RFVP build 配置做回归测试；真实游戏资源不进入测试 fixture。

### P0-2：统一引擎状态与真机证据

**问题**

README、RFVP Descriptor、K2NX Descriptor 对“是否真机验证”“音频是否支持”“具体游戏是否完整通过”等描述存在不一致。兼容性数据是用户判断能否使用的依据，必须比宣传文案更严格。

**具体工作**

- [ ] 对 Pilot-01 至 Pilot-04 建立一份统一的验收索引：游戏 ID、游戏版本/语言、适配器 ID、构建版本、构建产物 SHA-256、NS 系统/CFW 环境、测试日期、测试项目和结果。
- [ ] 逐项核对 Pilot-01：README 声称 2026-10-31 真机 PASS，而 K2NX Descriptor 仍写 Nintendo Switch hardware unverified。找出真实设备日志/视频/截图/操作者记录，裁决后同步更新两处。
- [ ] 逐项核对 RFVP：更新 Descriptor 中过期的 pinned version、audio 状态、存档状态、视频能力、性能说明、设备验证信息。
- [ ] 更新 Pilot-02 中已过时的“CG/背景切换卡顿持续优化”等描述；只在确认最新设备测试后改为 PASS。
- [ ] 将当前双平面零拷贝明确标记为实验中，不得覆盖现有已验证路径的状态。
- [ ] 对每条能力记录证据类型：`source_review`、`build_verified`、`emulator_verified`、`device_verified`、`game_verified`。

**建议的兼容性证据字段**

```yaml
verification:
  status: device_verified
  game_id: pilot03-moyu-cn
  game_version: "填写实际版本"
  runtime_version: "填写实际版本"
  galnx_revision: "填写私有/公开源提交"
  hardware: switch-v1
  firmware: "填写实际版本"
  atmosphere: "填写实际版本"
  tested_at: "YYYY-MM-DD"
  evidence:
    - type: device_log
      path: "公开可用的非版权证据路径"
    - type: manual_checklist
      path: "验收记录"
```

**验收标准**

- [ ] README 与 Descriptor 对同一游戏的状态一致。
- [ ] `galnx engines info` 显示的状态与 README 不冲突。
- [ ] 模拟器 PASS 不会被升级成真机 PASS。
- [ ] 引擎级 `ready/stable` 与游戏级 PASS 分开表达。
- [ ] 没有证据的字段使用 `unknown / unverified`，不靠推测补齐。

### P0-3：补强公开快照安全检查

**现状**

`scripts/public_release_sanitize.py` 当前按路径前缀和图片扩展名排除游戏截图、封面及图标；这是有效的已知素材隔离机制，但它不是完整的游戏数据/二进制/密钥扫描器。

**原则**

不要简单扩大一份超长扩展名黑名单并假定安全。采用“明确允许的公开文件类型 + 高风险文件扫描 + 大文件/二进制人工审查 + 最终 ZIP 再扫描”的组合。

**具体工作**

- [ ] 保留现有 `GAME_ART_PREFIXES`、`GAME_ART_SUFFIXES`、`IMAGE_ALLOWLIST` 机制；每个 allowlist 项必须有理由、来源和许可说明。
- [ ] 新增高风险扩展名检查：游戏归档/镜像/ROM、商业游戏容器、NRO/NSP/NCA、视频/音频/图片资源包、密钥/证书/私有配置等。命中后默认阻断，确有合法理由时通过显式 allowlist 放行。
- [ ] 扫描不只看扩展名：对无扩展名文件、伪装扩展名文件和大文件使用文件签名/magic bytes 检查。
- [ ] 对文件大小异常、路径包含 `save`、`dump`、`romfs`、`game_data`、`keys`、`cert` 等词的文件输出审查清单；这些词是审查提示，不应不加判断地全部删除。
- [ ] 对文本扫描可能的密钥、证书、token、私人路径、用户名及本机绝对路径。输出时对疑似 secret 做脱敏。
- [ ] 生成 sanitized tree 后扫描一次；生成 ZIP 后再从 ZIP 解包到临时目录复扫一次。
- [ ] 保持公开仓库新历史/干净快照机制，不把私有主仓库的完整历史推到公开端。
- [ ] 将扫描报告与源 commit、生成时间、文件数/大小、排除文件清单一起写入 `PUBLIC_RELEASE.md`。
- [ ] `tests/test_public_release.py` 增加：允许图片白名单、未知二进制、游戏归档、伪装扩展名、密钥特征、ZIP 内文件、Markdown 引用改写等测试。

**验收标准**

- [ ] 清理脚本对未识别的高风险二进制默认 fail closed。
- [ ] 同一输入重复生成结果可复现（时间戳等明确排除在内容确定性之外，或单独记录）。
- [ ] sanitized tree 和最终 ZIP 均通过扫描。
- [ ] `PUBLIC_RELEASE.md` 的数字由脚本生成，不在文档手工硬编码。
- [ ] 公共快照不会包含游戏本体、商业资源、密钥、证书或未经许可的二进制。

### P0-4：许可证与最终交付产物逐项对账

**问题**

第三方许可证不能仅按“仓库有这个项目”来判断；必须根据实际构建、链接方式、补丁、最终 NSP 是否携带该组件来确定义务。FFmpeg 的 configure 参数尤其需要核对：历史 NVTEGRA 探针曾使用 `--enable-gpl`，不能直接用某一次探针配置推定最终 NSP 的 FFmpeg 许可证，也不能在未核对最终库的情况下继续标为 LGPL。

**具体工作**

- [ ] 为每个实际分发的二进制建立组件清单：组件名、上游 URL、准确版本/commit、许可证、修改补丁、静态/动态链接、是否包含在 NSP、随包提供的源码/声明位置。
- [ ] RFVP 最终构建中的 FFmpeg：核对源码分支/commit、configure 完整参数、启用的 decoder/codec/filter、是否启用 GPL/nonfree、最终静态库和链接 map。
- [ ] 不要把“NVTEGRA 探针 FFmpeg”与“最终 RFVP 发行构建 FFmpeg”当作同一个产物，除非 hash 和 build record 证明它们相同。
- [ ] 对 Kirikiroid2-NX：继续按其实际 LICENSE 的日文条款和捆绑组件逐项审查，尤其关注 UnRAR 再分发限制及 FFmpeg/OpenCV/cocos2d-x 等依赖。
- [ ] 对 ONScripter-NX：若 0.1 不分发其运行时二进制，文档明确它是研究/构建路线；不得用“未来可能用到”代替实际交付分析。
- [ ] 将依赖分为 `runtime-linked`、`runtime-bundled`、`build-only`、`development-only` 四类，避免把 devkitPro 构建工具与 NSP 运行时组件混为一谈。
- [ ] 核对引擎补丁的源文件可获取性和对应上游许可证；为每个补丁系列维护来源 commit 和补丁 hash。
- [ ] 生成 `SBOM` 或至少一份机器可读 third-party inventory（JSON/YAML 均可），并由 `THIRD_PARTY_NOTICES.md` 汇总引用。

**验收标准**

- [ ] 每个实际分发的 NSP 都能追溯其运行时组件和版本。
- [ ] FFmpeg 声明与最终链接产物配置一致。
- [ ] K2NX 的非 SPDX 条款有单独说明，不被误写成 MIT/BSD。
- [ ] 第三方源码/许可证义务与实际二进制分发行为相匹配。
- [ ] 未完成许可核查的组件不进入公开二进制分发。

---

## 3. P1：建议在 0.1 发布前完成

### P1-1：让构建缓存真正对构建输入敏感

**现状**

当前 `cache.py` 的 `cache_payload()` 已包含 Manifest 路径、引擎 adapter/pinned commit/build backend、构建命令、workdir、artifact、env、timeout、部分 `input` 和工具链指纹；`fingerprint_toolchain()` 目前主要采集 devkitPro GCC 与 CMake 版本。

风险是：源码或补丁在相同路径下变化，或者 Rust/Cargo/SDL2/FFmpeg 等工具链产物发生变化时，缓存键未必变化。

**具体工作**

- [ ] 新增显式 `build.inputs`，列出构建实际依赖的源代码目录、补丁、Cargo.lock、CMake 配置、FFmpeg configure 文件、资源处理器版本等。
- [ ] 对目录生成确定性 Tree Digest：路径、文件类型、内容 hash、必要时记录可执行位；排序规则固定，忽略明确声明的临时文件。
- [ ] 对文件单独计算 SHA-256；对 Git 管理的上游依赖优先纳入 commit/tree ID，但本地补丁仍要独立 hash。
- [ ] 工具链指纹扩展到实际使用的组件：devkitA64/GCC、CMake/Ninja、Rust toolchain、Cargo.lock、SDL2 portlib 版本、FFmpeg 源码 commit/configure 参数及关键静态库 hash。
- [ ] 对无法确定版本的工具标记为 `unknown` 并禁用强缓存命中，或要求用户显式选择非可复现模式；不要静默把 unknown 当作稳定输入。
- [ ] 不将 `prod.keys`、Nintendo 证书、token 等秘密明文加入 key 或日志；若构建本身不依赖密钥，则将它们排除在编译缓存键之外，只在 NSP packaging 阶段单独管理。
- [ ] 修改缓存输入模型后提升 `CACHE_SCHEMA_VERSION`，防止旧缓存被误读为新语义。

**必须增加的缓存测试**

- [ ] 内容不变、路径不变 → 命中缓存。
- [ ] 同路径修改一个源文件 → 缓存 miss。
- [ ] 同路径修改一个 patch → 缓存 miss。
- [ ] 更改 Cargo.lock / FFmpeg configure 参数 / 工具链版本 → 缓存 miss。
- [ ] 仅更改无关文档 → 根据声明的输入范围决定是否 miss，规则必须明确。
- [ ] 缓存产物被改写或截断 → SHA-256/size 校验失败并重新构建。
- [ ] 缓存记录来自旧 schema → 安全失效，不错误复用。

### P1-2：明确 Manifest 命令执行的信任边界

**现状**

`executor.py` 支持 argv 数组和 shell 字符串；字符串命令使用 `shell=True`。构建执行会启动本机子进程，因此 Manifest/Descriptor 不只是数据文件，也可能携带代码执行行为。

**具体工作**

- [ ] 文档明确：执行来自不可信来源的 Manifest、Descriptor 或构建脚本，等价于在本机执行其中的命令。
- [ ] 示例默认使用 argv 数组；只有确实依赖 shell 语法时才使用字符串命令，并写明原因。
- [ ] 执行前输出完整命令、工作目录、超时和环境变量名称；敏感变量值必须遮蔽。
- [ ] 增加 `--dry-run` 或保证现有 plan 能展示最终实际执行命令，而不仅是概念计划。
- [ ] 对外部来源配置增加首次执行确认；CI/自动化场景通过显式 `--yes` 或可信配置文件跳过交互。
- [ ] 检查 workdir、artifact、output_dir 的路径规范化与允许范围，避免路径逃逸和意外覆盖。
- [ ] 环境变量采用 allowlist/denylist 规则：继承哪些宿主变量、哪些 secrets 不得写入日志，必须在文档中说明。

### P1-3：拆分新手模板与历史 Pilot 记录

**目标**

公开仓库既是技术记录，又承担新用户入口。目前示例包含特定机器的 `E:/galnx-build`、devkitPro 路径、模拟器位置和真实游戏资源布局，不能把所有 Pilot 文件都当成通用模板。

**建议目录**

```text
examples/
  templates/
    minimal-manifest.yaml
    external-engine-descriptor.yaml
    input-profile.yaml
  engines/
    rfvp.yaml
    kirikiroid2-nx.yaml
    krkrsdl2.yaml
    onscripter-nx.yaml
    brewser.yaml
  pilots/
    pilot01-haruno-cn.yaml
    pilot02-iroseka.yaml
    pilot03-moyu-cn.yaml
    pilot04-akaseka.yaml
```

目录迁移可以按实际仓库情况调整，不能为了追求结构漂亮而破坏已有引用。

**具体工作**

- [ ] 保留 Pilot 配置作为真实项目记录，但在文件头注明“不是通用模板，需按本机环境修改”。
- [ ] 新增最小模板，路径使用相对路径、环境变量或 `galnx config` 提供的配置项，不出现开发者私人绝对路径。
- [ ] 盘点 `src/galnx/paths.py` 的默认值；将 `E:/...`、`D:/...` 这类个人机器默认值改为平台标准目录、环境变量或显式配置。
- [ ] 对 Windows 之外的平台：要么提供真实验证步骤，要么清楚标注当前 Windows-only verified，不能仅凭 Python 跨平台就宣称 Linux 可用。
- [ ] README Quick Start 只引用 templates；Pilot 页面用于展示已验证游戏和历史证据。

### P1-4：重做能力模型的命名和验证粒度

**问题**

目前 `video` 既可能被读者理解为图形渲染，也可能理解为视频文件播放。RFVP 当前的 SDL/GLES2 渲染后端、NVDEC、NV12/VIC/GLES 图像路径应当拆开表达。

**建议语义**

```yaml
capabilities:
  graphics:
    backend: sdl2-gles2
    features: [sprite, alpha, blend_multiply, blend_screen]
    verification: device_verified

  movie:
    codecs: [h264]
    decode_backends: [nvdec, software_fallback]
    output_formats: [nv12]
    transfer_path: "以当前实际实现填写"
    verification: device_verified
    notes: "记录真机已验证分辨率/帧率/素材，不夸大到全部编码格式"

  audio:
    output: true
    streaming: true
    independent_pump: true
    verification: device_verified

  input:
    controller: true
    virtual_pointer: true
    touch: false
    verification: game_verified

  save:
    save: true
    load: true
    thumbnail: true
    verification: game_verified
```

以上是建议模型，不要求照抄字段；必须先检查现有 JSON Schema 和 parser 是否允许嵌套对象，再决定如何升级 schema。

**具体工作**

- [ ] 将 `graphics` 和 `movie` 拆开，避免 `video` 歧义。
- [ ] 支持 `implemented/build_verified/emulator_verified/device_verified/game_verified/partial/unknown/in_progress` 等状态，或采用等价的结构化证据模型。
- [ ] 能力状态与游戏兼容性状态分开：引擎实现了某能力，不代表所有游戏都正确使用。
- [ ] 将当前 GLES2 双平面零拷贝标为 `in_progress`；完成真机性能和颜色正确性回归后再升级。
- [ ] 公开性能数值时带上分辨率、编码、帧率、硬件/固件、测量区间及是否包含 vsync。

### P1-5：建立最小 CI / 回归门槛

**不要求** 在 GitHub Actions 云端直接构建所有 Switch 游戏。当前 Windows + devkitPro 环境具有现实依赖，硬件 NVDEC 也必须在真机验证。

**建议 CI 至少覆盖**

- [ ] Python package 安装和 import。
- [ ] `pytest` 全量测试。
- [ ] YAML/JSON Schema 校验。
- [ ] Manifest/Descriptor 引用检查。
- [ ] Public sanitizer 测试及生成树扫描。
- [ ] License inventory 必需文件检查。
- [ ] `--help`、doctor JSON schema 和主要 CLI 命令 smoke test。

**本机 Release Gate**

- [ ] Windows + devkitPro 环境完整构建。
- [ ] 至少一个真实 RFVP Pilot 的 NRO/NSP 构建与 nstool 校验。
- [ ] 至少一个 K2NX Pilot 的构建/打包路径校验；真机状态按证据填写。
- [ ] Citron 冒烟测试与真机验收分开记录。
- [ ] 最终 NSP 的 TitleID、RomFS 内容 hash、ELF/NSO/NPDM 结构、图标和版本信息校验。

### P1-6：更新项目元数据和文档入口

- [ ] `pyproject.toml` 的 description 不再使用 `framework skeleton` 等早期措辞。
- [ ] README 的 0.1 使用入口指向新手模板、安装文档和兼容性表。
- [ ] README 的 Pilot 状态以验收记录自动/半自动生成，或至少由单一数据源维护。
- [ ] 术语统一：内置适配器（built-in adapter）、外部 Descriptor、引擎运行时、游戏 Profile、游戏级验证。
- [ ] `engines list` 说明只显示内置注册项还是也显示外部 Descriptor；README 与 CLI 行为必须一致。
- [ ] 对 `krkrsdl2`、`onscripter-nx`、`brewser`、`renpy` 等研究路线写明当前只是研究/模拟器级/受阻，不与已真机验证 Pilot 放在同一状态层级。

---

## 4. P2：首发后或不阻塞 0.1 的整理

### P2-1：发布记录与版本化文档

- [ ] 建立 `CHANGELOG.md`，记录用户可见改动和兼容性变化。
- [ ] 建立 `0.1.0 Preview` Git tag 和 GitHub Release。
- [ ] Release 附带源码快照 ZIP、校验 SHA-256、简要变更、已知问题和测试矩阵；不附商业游戏内容、密钥或游戏 NSP。
- [ ] README 不再作为唯一的、持续被改写的版本文档；每个 Release 指向固定 tag 的文档。
- [ ] 在公开快照中保留来源私有 commit、公开 commit 和生成报告。

### P2-2：部署模式的长期扩展

当前继续采用 `self_contained_nsp` 作为主要交付方式，不因大体积游戏立即重构。

以后可以评估：

- `self_contained_nsp`：游戏数据封装在 RomFS，安装后直接运行。
- `external_content`：运行时在 NSP 中，游戏数据单独放 SD 卡。

只有当更新成本、安装体积或多个游戏共享运行时的收益足够明确时才立项。0.1 不需要实现。

### P2-3：游戏兼容性数据库

- [ ] 为每款游戏建立独立 ID 和兼容性记录。
- [ ] 记录原始版本、语言/汉化版本、适配器版本、GalNX revision、设备和固件环境。
- [ ] 分开记录“启动成功”“可推进剧情”“存读档验证”“视频验证”“完整通关验证”。
- [ ] 不以“引擎支持”替代“游戏兼容”。
- [ ] 允许社区提交不含游戏资源的日志、测试步骤和兼容性报告。

### P2-4：NS 游戏库 / Launcher

不列入 0.1。独立 NSP + HOME 菜单已经满足当前直接启动需求。若未来游戏数量导致管理不便，再实现只管理 GalNX 自己生成标题的轻量 Library；不要为了统一入口提前将所有游戏改成单一 Host 运行时。

---

## 5. GLES2 双平面 / NV12 零拷贝：独立 R&D 工作流

此项是当前正在推进的性能工作，不属于本次仓库清理的前置任务。建议单独维护分支或明确的里程碑，完成后再更新相关文档和能力元数据。

### 5.1 在整理期间必须保留的边界

- 不要在仓库清理分支内改写 NVDEC/GLES 代码。
- 不要在尚未真机验证时将 `transfer_path: zero_copy` 或类似字段标为稳定。
- 不要把“NVDEC 硬解成功”与“硬件表面直接被 GLES 采样”视为同一事实。
- 记录当前可用 fallback；零拷贝路径失败时必须能够回退到已验证的路径。

### 5.2 完成后需要归档的证据

- [ ] 输入编码/分辨率/帧率和色彩参数。
- [ ] NVDEC 输出格式、plane 数、stride、offset、surface layout。
- [ ] GLES2 纹理导入方式、所需扩展、同步 fence 行为。
- [ ] 是否真正消除了 CPU RGBA conversion、CPU readback 和重复上传；分别给出证据。
- [ ] 颜色范围、色彩矩阵、UV 采样、stride 对齐、黑边/绿屏/色偏测试。
- [ ] 真机上的 frame time P50/P95/P99、CPU time、GPU time、音画同步和长视频稳定性。
- [ ] 软解/原有硬件帧传输路径 fallback 回归。
- [ ] 至少对 IROSEKA 与《樱花，萌放。》的不同视频样本进行验证。

### 5.3 对外表述规则

在上述证据完成前，README 只能写“NVDEC 硬解已验证；GLES2 双平面/零拷贝路径开发中”。完成后也应准确区分“零 CPU RGBA 转换”“零 CPU readback”“零拷贝”这三个不同强度的声明。

---

## 6. 建议执行顺序

建议按小任务逐个交给 Agent，不要一次要求它全面重构。

| 顺序 | 任务 ID | 任务 | 预计交付 | 阻塞级别 |
|---|---|---|---|---|
| 1 | `AUDIT-BASELINE` | 固定当前私有源 commit、公开快照 commit、构建版本和未提交工作 | 基线记录 + 差异清单 | 必须先做 |
| 2 | `AUDIT-BUILD-CONTRACT` | 对齐 Manifest / Descriptor / Executor / README | 构建契约决策 + 测试 | P0 |
| 3 | `AUDIT-ENGINE-EVIDENCE` | 对账 Pilot-01~04 和 RFVP/K2NX Descriptor | 能力与验收矩阵 | P0 |
| 4 | `AUDIT-PUBLIC-SAFETY` | 增强 sanitizer 并扫描最终 ZIP | 扫描器 + 测试 + 报告 | P0 |
| 5 | `AUDIT-LICENSE-SBOM` | 对账最终 NSP 实际依赖和许可证 | 组件清单 + notices 修订 | P0 |
| 6 | `FIX-BUILD-CONTRACT` | 实施最小构建闭环/准确标注手工步骤 | 代码或文档修正 | P0 |
| 7 | `FIX-CACHE-INPUTS` | 完善源/补丁/工具链指纹 | 缓存 schema + 回归测试 | P1 |
| 8 | `FIX-MANIFEST-TRUST` | shell 命令预览、确认和敏感日志处理 | 文档/CLI/测试 | P1 |
| 9 | `DOC-QUICKSTART` | 新手模板、路径配置、快速开始 | 模板和文档 | P1 |
| 10 | `CI-RELEASE-GATE` | CI smoke、Windows build gate、版本与 Release 模板 | Release checklist | P1/P2 |
| 11 | `PUBLIC-SNAPSHOT` | 从私有主仓生成最终 sanitized 快照 | 新公开 commit + ZIP + SHA256 | 最后执行 |

### 6.1 每个 Agent 任务的固定交付格式

让 Agent 按以下结构汇报，避免只给“已修复/测试全绿”：

```text
Task ID:
Source commit:
Files changed:
Observed problem:
Decision made:
Behavior before:
Behavior after:
Tests added:
Commands executed:
Test results:
Unverified assumptions:
Known limitations:
Rollback method:
```

### 6.2 本轮分支建议

- `cleanup/build-contract`
- `cleanup/capability-evidence`
- `cleanup/public-release-gate`
- `cleanup/license-inventory`
- `cleanup/cache-fingerprint`
- `cleanup/docs-quickstart`

不要将所有修改长期堆在一个 `cleanup` 大分支里。任务通过后再汇总合并。

---

## 7. 0.1.0 Preview 发布验收清单

### 产品定位与交付

- [ ] README 清楚说明 GalNX 是 PC 端移植工作台，而不是游戏分发平台或通用模拟器。
- [ ] 明确用户必须自行准备其有权使用的游戏文件；公开仓库不含商业游戏数据、NSP、密钥和证书。
- [ ] 至少两条不同的引擎适配路线有可引用的真机游戏验收证据。
- [ ] 公开兼容性表按“游戏 + 版本 + 适配器 + GalNX revision”列出结果。

### 构建与复现

- [ ] 干净 Windows 环境按照 Quick Start 能完成环境检查。
- [ ] 模板 Manifest 可通过 schema 和 preflight。
- [ ] 构建执行状态不会把空命令误报为成功。
- [ ] 至少一个公开 Pilot 的构建/打包步骤与文档逐条一致。
- [ ] 输出 NSP 能被 nstool 验证，TitleID / ProgramID / RomFS 信息正确。
- [ ] 缓存对源码、补丁和工具链变化敏感。

### 引擎/游戏验收

- [ ] RFVP 的能力状态以最新真机证据更新。
- [ ] K2NX 的硬件验证状态与 Pilot-01 的真实证据一致。
- [ ] 模拟器和真机验证明确分开。
- [ ] 进行中的 GLES2 双平面工作没有被标记为稳定能力。

### 安全与合规

- [ ] Sanitizer 和最终 ZIP 扫描通过。
- [ ] 没有游戏资源、游戏数据、密钥、证书、私人 token 或不应公开的构建产物。
- [ ] 公开历史来自 sanitized snapshot，不含私有历史中的排除素材。
- [ ] 第三方组件清单与最终 NSP 依赖一致。
- [ ] FFmpeg 最终 configure 参数及许可证状态已核对。
- [ ] K2NX 的特殊许可条款已单独审查。

### 文档与发布

- [ ] `pyproject.toml` 等项目元数据已更新。
- [ ] Quick Start 使用通用模板，不要求照抄个人机器路径。
- [ ] README、Manifest 文档、Descriptor 和 CLI 输出一致。
- [ ] `CHANGELOG.md`、`0.1.0 Preview` tag 和 Release notes 已准备。
- [ ] Release ZIP 有 SHA-256 和来源 commit 信息。

---

## 8. 发布后的维护规则

### 8.1 问题收敛

收到反馈后按以下顺序处理：

1. 确认游戏版本、语言/汉化版本、GalNX revision 和设备环境。
2. 收集复现步骤、日志和预期行为。
3. 尝试独立复现；不能复现的先记录，不直接改底层架构。
4. 判断问题属于 Core、Platform Layer、Engine Adapter 还是 Game Profile。
5. 评估影响范围和修复成本后排期。

### 8.2 Bug 分类

- **P0**：无法启动/退出、崩溃、存档损坏、剧情推进阻断、可能损坏数据、安全/隐私/许可证问题。
- **P1**：常见功能失效、明显音画问题、反复可复现的严重卡顿、重要演出缺失。
- **P2**：低频装饰效果、非阻断的视觉差异、少数特殊资源或罕见分支问题。
- **P3**：文案、易用性、非关键优化和愿望功能。

修复优先级同时考虑影响范围、复现性、修复成本和回归风险；不以“与 PC 每个像素完全一致”作为唯一标准。

### 8.3 引擎准入原则

新引擎在大规模投入前至少完成一个 Go/No-Go 探针：

- 能否启动最小程序；
- 能否读取实际游戏资源；
- 核心脚本是否能执行；
- 图形、音频、输入是否存在可行路径；
- 存档/退出是否可行；
- 许可证和分发边界是否允许继续。

没有通过关键探针的路线，只记录研究结果，不提前承诺完整支持，也不阻塞已有引擎的发布。

---

## 9. 本轮结论

GalNX 当前不需要推翻架构，也不需要为了 0.1 增加更多引擎或客户端。真正需要的是把研发阶段的成果沉淀为标准化、可追溯的工作流。

**本轮的成功标准不是“完成更多功能”，而是：公开声明准确、构建路径诚实可复现、缓存不会错误复用、第三方内容与许可证边界清楚、已有真机成果能被别人正确理解。**

完成 P0 后，GalNX 就具备发布 0.1.0 Preview 的基本工程条件。P1 尽量在首发前完成；P2 不应拖延首发。

---

## 10. 审查参考入口

以下链接指向本次审查时的公开仓库文件。后续若目录迁移，应同步更新本文件或改用固定 commit 链接。

- [GalNX-public README](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/README.md)
- [Manifest 规范](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/docs/MANIFEST.md)
- [RFVP Descriptor](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/examples/engines/rfvp.yaml)
- [Kirikiroid2-NX Descriptor](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/examples/engines/kirikiroid2-nx.yaml)
- [Build Executor](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/src/galnx/build/executor.py)
- [Build Cache](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/src/galnx/build/cache.py)
- [Public Sanitizer](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/scripts/public_release_sanitize.py)
- [公开仓库发布流程](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/docs/environment/public-release.md)
- [Third-party Notices](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/THIRD_PARTY_NOTICES.md)
- [Public Release 记录](https://github.com/KIRARITenshiChan/GalNX-public/blob/main/PUBLIC_RELEASE.md)


---

## 11. 执行状态与偏差记录（2026-11-11 收敛结果）

**结论：P0-1…P1-6 全部完成并合入 0.1.0 Preview 收敛提交；P2 中只有发布记录项（P2-1）随本轮完成，P2-2/3/4 留待 0.1 之后。**

| 任务 | 状态 | 落地内容 | 证据 |
| --- | --- | --- | --- |
| P0-1 构建契约 | 完成 | manifest 为唯一执行配置源；`build.commands`/`artifact` 严格成对；空命令 = `not_configured`（`build run` 退出码 3、batch 报告 `build_state`），batch report schema v2；`build run --dry-run` 打印完整命令/CWD/超时/env 名（敏感值掩码），`--json` 计划走 stderr；`engines plan` 标 `plan_only` | `src/galnx/build/{config,executor}.py`、`src/galnx/batch/{runner,report}.py`、`schemas/batch-report.schema.json`、`tests/test_build_contract.py`、`docs/MANIFEST.md` |
| P0-2 引擎状态与真机证据 | 完成 | 能力拆 graphics/movie/audio/input/save/touch + 每项 verification；rfvp=`ready`/`device_verified`（3 部 FVP 真机 PASS）、kirikiroid2-nx=`ready`/`game_verified`、krkrsdl2/onscripter-nx/brewser=`research`/`emulator_verified`；新增验证矩阵与签收索引 | `examples/engines/*.yaml`、`docs/engines/{README,verification-matrix}.md`、`docs/pilot/0.1.0-device-acceptance.md`、`tests/test_engines*.py`（145 passed） |
| P0-3 公开快照安全 | 完成 | sanitizer 重写为 fail-closed：素材前缀排除 + 白名单图片 + 高危扩展名/magic bytes/文本扫描（token、私钥、本机绝对路径）/大文件审查；导出后 BLOCK 校验 + ZIP 解包复扫；`PUBLIC_RELEASE.md` 数字由脚本生成；markdown 引用改写占位 | `scripts/public_release_sanitize.py`（1,043 行）、`scripts/public_release_publish.py`、`tests/test_public_release.py`（60 用例）、`docs/environment/public-release.md` |
| P0-4 许可 SBOM | 完成 | 33 组件 / 4 产物清单（上游、版本或 commit、许可、链接方式、是否入 NSP、义务、证据）；checker 退出码 0/1；FFmpeg nvtegra 分支 `CONFIG_GPL 1` ⇒ 保留 NVDEC 则 NSP 整体 GPL-2.0-or-later（方案 B）；K2NX 非 SPDX 条款与 UnRAR 再分发限制单列 | `docs/third_party/inventory.yaml`、`scripts/check_license_inventory.py`、`THIRD_PARTY_NOTICES.md`、`tests/test_license_inventory.py`（24 passed） |
| P1-1 缓存输入敏感 | 完成 | `build.inputs`（file/tree，确定性摘要，POSIX 排序，忽略 `.git`/`.galnx`）+ 8 分量工具链指纹（devkitPro GCC/CMake/Ninja/Rust/Cargo/SDL2/FFmpeg commit/host platform）；cache schema 2；**blocking（必需输入缺失/不可读）既不读也不写，degraded（工具链版本 unknown）写键并警告** | `src/galnx/build/{cache,config}.py`、`schemas/game-manifest.schema.json`、`tests/test_build_cache*.py`（26+17 用例）、`docs/release/tasks/TASK-CACHE.md` |
| P1-2 manifest 信任边界 | 完成 | 先打印计划再执行；TTY 交互确认、CI 用 `--yes`；artifact/workdir 防逃逸；env 名白名单与敏感值隐藏；文档新增信任边界一节 | `src/galnx/cli.py`、`src/galnx/build/executor.py`、`docs/MANIFEST.md`、`tests/test_build_contract.py` |
| P1-3 模板与历史分离 | 完成 | `examples/templates/{minimal-manifest,external-engine-descriptor,input-profile}.yaml`（无个人绝对路径）；10 个 pilot 清单标注「非通用模板」；`src/galnx/paths.py` 默认值改为相对/环境变量 | `examples/templates/`、`tests/test_templates.py`、pilot 清单头注释 |
| P1-4 能力模型 | 完成 | graphics 与 movie 拆分；graphics.backend/features、movie.codecs/decode_backends/output_formats/transfer_path、audio/input/save；verification 8 值枚举；性能数值带分辨率/编码/帧率/硬件 | `schemas/engine.schema.json`、`src/galnx/engines/descriptor.py`、`docs/engines/README.md` |
| P1-5 CI/回归门槛 | 完成 | `.github/workflows/ci.yml`（windows-latest）：install/import/pytest/schema/引用检查/sanitizer/license inventory/CLI smoke/build plan 契约；本机 Release Gate 另含 NSP verify 与 Citron 冒烟 | `.github/workflows/ci.yml`、`docs/release/0.1.0-preview.md` §8 |
| P1-6 元数据/文档 | 完成 | `pyproject.toml` description 去 skeleton；README 重写（定位/快速开始/兼容表/文档地图）；版本与验收单一来源 = verification-matrix；CHANGELOG 与 0.1.0 发布说明 | `README.md`、`pyproject.toml`、`CHANGELOG.md`、`docs/release/0.1.0-preview.md` |
| P2-1 发布记录 | 完成 | 公开快照链路（私有 commit → sanitized tree → 公开 commit）记录、tag/Release 流程、ZIP 校验清单 | `docs/release/README.md`、`docs/environment/public-release.md` §4.5 |
| P2-2/3/4 | 未做（0.1 后） | 部署模式、兼容性数据库、NS Launcher | — |

### 11.1 与计划的偏差（已接受）

1. **sanitizer 的个人路径处理**：计划要求「移除本机绝对路径」，实际采用「导出时确定性脱敏为 `C:\Users\<user>`，扫描器对残留仍 BLOCK」。理由：190 个历史文档共 448 处路径若逐文件改写会破坏历史证据；脱敏后不泄漏仍可审计，已在 `docs/environment/public-release.md` §2.6 记录。
2. **缓存语义**：计划的「unknown 不得静默当稳定」实现为 blocking/degraded 两档，而不是把所有 miss reason 都变成不缓存——本机 PATH 无 devkitA64（工具链版本 unknown）会让缓存永久失效，CI 同样失败。degraded 仍写警告并写入键内，不静默。
3. **研究级引擎**：krkrsdl2/onscripter-nx/brewser 保持 `research` 而非升为 `ready`，与 §1.4/§P1-6 的分层要求一致；Pilot 只承认 4 个真机验收包。
4. **FFmpeg 许可**：选方案 B（保留 NVDEC + GPL-2.0-or-later），而不是去掉 NVDEC 换 LGPL——NVDEC 是真机 60 fps 电影路径前提，去掉等于推翻已验收的 P40/P44；公开仓库只发 MIT 编排层与上游补丁，不发 NSP。
5. **分支与提交**：单人 maintainer，未按 §6.2 开每任务分支，改为「工作树并行 + 每任务 `docs/release/tasks/TASK-*.md` 固定格式报告 + 统一收敛 commit」；任务边界与报告格式仍遵守 §6.1。
6. **NV12 表述**：§5.2 证据清单中「真机 P50/P95/P99、长视频 soak」未做，已归档为后续项；对外只写「零 CPU NV12→RGBA 转换 + 双平面直传」，不写绝对「零拷贝」。

### 11.2 验证数字（本机 Release Gate）

- `PYTHONPATH=src GALNX_BUILD_ROOT=E:/galnx-build python -m pytest -q` → **737 passed / 63 subtests**。
- `python scripts/check_license_inventory.py --json` → rc 0，components=33、artifacts=4、errors=0、warnings=2。
- `python scripts/public_release_sanitize.py` → **0 BLOCK**；kept 985 / excluded 359 / 25.37 MB（HEAD 974a414 工作树）。
- 4 个 NSP 的 `galnx package nsp verify` → 均 13 checks / 0 fail / 1 warn（未签名 homebrew 预期）。
- 4 部真机验收：Pilot-01 K2NX A10 1.0.9、Pilot-02 IROSEKA 1.2.5-test、Pilot-03 MOYU 1.3.3-test、Pilot-04 AKASEKA 1.4.1-test（签收索引 `docs/pilot/0.1.0-device-acceptance.md`）。

### 11.3 后续（0.1 之后）

- P2-2 部署模式、P2-3 兼容性数据库、P2-4 NS Launcher。
- 跨平台构建（当前 CI 与构建链只验证 Windows）。
- 真机性能长跑（P50/P95/P99、OP 长视频 soak）与 IROSEKA/MOYU 的 1080p OP 可选启用。

## 12. FIX 一轮（复审后收口，2026-11-11）

复审（用户 m42143 转来的 6 项表格）之后，本仓库按风险顺序完成 FIX-01..FIX-06；全部在同一工作树内验证，未新增游戏功能，GLES2 零拷贝 / 更多引擎 / GUI / NS Launcher 按要求留到 0.1 之后。

| 编号 | 结论 | 关键改动 | 证据 |
| --- | --- | --- | --- |
| FIX-01 非 TTY 构建确认绕过 | 完成（fail-closed） | `build run` / `batch build` 非 TTY 且无 `--yes` ⇒ 退出码 2 且不执行；`EOFError` 视为拒绝；`docs/MANIFEST.md` 增「非交互不默认放行」 | `tests/test_build_contract.py` 19 passed；取证 `E:/galnx-build/fix01/evidence.json`（rc2 / NUL rc2 / `--yes` rc0） |
| FIX-02 真正可执行的构建示例 | 完成 | `examples/quickstart/`（manifest + 确定性打包器 + 内容 + README）+ CI step；根目录 RUN1 `1 executed` → RUN2 `1 cache hit` | artifact 269 B sha256 `5982bb06…`、magic `GALNXPK1`；`tests/test_quickstart_example.py` |
| FIX-03 Pilot-04 验证等级 | 完成 | `game_verified` → `device_verified`（缺口：剧情全流程/存档读档 soak/长时签收）；README、matrix、engine docs、device-acceptance 四处统一 | 152 passed / 12 subtests |
| FIX-04 空 `build.inputs` 缓存保护 | 完成 | 声明 commands 未声明 inputs ⇒ blocking reason、不读不写缓存；cache 段 `inputs_declared` | 41 passed（+24 相邻回归）；报告 `docs/release/tasks/FIX-04.md` |
| FIX-05 RFVP descriptor 旧信息 | 完成 | graphics/input 降级 `device_verified`，status_reason/notes 按 1.2.5 / 1.3.3 / 1.4.1-test 重写（pinned_commit、artifact sha 未变） | 与 `docs/engines/verification-matrix.md` 一致 |
| FIX-06 重新生成发布快照 | 完成 | 重新导出 sanitized 树、审核 REVIEW、ZIP 解包复扫、更新 `PUBLIC_RELEASE.md` 时间/来源 commit，并在公开仓库干净 clone 上复跑 quickstart | 见 `docs/environment/public-release.md` §4.5 最新行 |

### 12.1 与专家表的偏差

1. **FIX-04 越界 1 行**：`tests/test_batch_build_cli.py:59` 的 fixture 补了 `inputs`（不在原 write scope），否则该文件既有 miss→hit/stale 用例必红；Lead 已批准，改动仅 1 行。
2. **缓存键一次性失效**：新增 `inputs_declared` 字段使所有项目缓存键变化一次；语义是「一次性重建」而非数据错误，已写入 FIX-04 报告，未升 `CACHE_SCHEMA_VERSION`（blocking 在读写前判定，旧条目被自然忽略）。
3. **FIX-02 不覆盖真实引擎构建**：示例刻意只用 Python 打包器，保证公开环境无需 devkitPro；真实引擎构建闭环仍以 pilot 清单与 `docs/builds/` 记录为准，已作为风险登记。

### 12.2 验证数字（FIX 收敛后）

- `PYTHONPATH=src GALNX_BUILD_ROOT=E:/galnx-build python -m pytest -q` → **747 passed / 63 subtests**（76.35 s）。
- `python scripts/check_license_inventory.py --json` → rc 0、33 组件 / 4 产物 / 0 error / 2 warning（未随本轮变化）。
- `scripts/public_release_sanitize.py` 重新导出（私有源 `cc6148c`）→ kept=1018 / excluded=359 / bytes=26,606,932，BLOCK 0，review 469（dev path 439 + keyword 30）；ZIP 9,142,838 B sha256 `17688031…`，解包复扫 0 BLOCK。
- 公开仓库干净 clone（`071e2c9`）复跑 `examples/quickstart/`：首跑 exit 0、`1 executed`、artifact 269 B sha256 `5982bb06…`，二跑 `1 cache hit`、RC 0。

### 12.3 仍未做（0.1 之后）

- GLES2 双平面零拷贝的扩大使用、更多引擎、GUI、NS Launcher（专家明确不建议并入本轮）。
- Pilot-04 的剧情全流程 / 存档读档 / 长时 soak 签收（当前为 `device_verified`）。
- 跨平台构建与真机性能长跑（P50/P95/P99、OP soak）。

## 13. CLEAN 一轮（专家清单第 3 轮，2026-11-11）

专家第三轮清单（用户 m42594）只要求 4 项收口，并明确「完成这四项后不需要第三轮全面整理」。本轮只改文档、元数据与发布操作，未改源码/引擎/产物行为。

| 编号 | 结论 | 关键改动 | 证据 |
| --- | --- | --- | --- |
| CLEAN-01 README Pilot-04 状态 / RFVP 试点数量 | 完成 | README 的 rfvp 行「4 部试点」→「3 部试点（Pilot-02/03/04，Pilot-01 是 kirikiroid2-nx）」；试点表 Pilot-04 标 `device_verified PASS` 并保留缺口（剧情全流程 / 存档读档 soak 未签收） | 与 `docs/engines/verification-matrix.md`、`examples/engines/rfvp.yaml` 一致 |
| CLEAN-02 Pilot-04 构建命令示例 | 完成 | 删除 pilot 清单的 `--yes`「真正执行」示例；明确真实引擎构建由 `docs/builds/` 记录的脚本驱动；`--dry-run` 退出码 3、`--yes` 仅进入批处理预检（缺 prod.keys 退出码 2 / 齐全退出码 3）且不产生产物；可执行示例仅 `examples/quickstart/` | 实测 `DRY_RC=3`、`YES_RC=2/3`，日志 `E:/galnx-build/clean02-*.log` |
| CLEAN-03 AKASEKA SBOM 及组件关联 | 完成 | `inventory.yaml` 新增 `akaseka-nsp`（v1.4.1-test、6,738,209,496 B sha256 `db31a312…`），8 个运行时组件补 artifacts 关联；notices / third_party README 改「33 组件 / 5 产物」 | checker rc 0、components=33、artifacts=5、errors=0、warnings=2；`tests/test_license_inventory.py` 24 passed |
| CLEAN-04 重新生成 Sanitized Release | 完成 | 在本轮提交后的 HEAD 重跑 sanitizer + publish，推送公开快照 7；登记 `docs/environment/public-release.md` §4.5 与 `docs/release/0.1.0-preview.md` §8 | 快照数字见 `docs/environment/public-release.md` §4.5 最新行 |

### 13.1 验证数字（CLEAN 收敛后）

- `PYTHONPATH=src GALNX_BUILD_ROOT=E:/galnx-build python -m pytest -q` → **747 passed / 63 subtests**（本轮无代码改动，与 FIX 轮基线相同）。
- `python scripts/check_license_inventory.py --json` → rc 0、33 组件 / **5 产物** / 0 error / 2 warning。
- README 命令实测：`--dry-run` 退出码 3；`--yes` 缺 prod.keys 退出码 2、齐全退出码 3，两种情况均不产生产物。
- 公开快照 7：kept / excluded / bytes / BLOCK / REVIEW / ZIP sha256 以 `docs/environment/public-release.md` §4.5 最新行为准。

### 13.2 仍未做（0.1 之后）

- `docs/builds/` 的 50+ 篇历史记录与旧计划快照未按新口径回改（按「历史不可篡改」保留，仅新文档采用统一口径）。
- Pilot-04 的完整验收缺口（剧情全流程 / 存档读档 / 长时 soak）仍需真机签收。
- 专家已确认第三轮收口后不再需要全面整理；后续只按新反馈做增量修复。
