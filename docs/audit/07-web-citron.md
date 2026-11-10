# Citron Neo 模拟器 审计（只读）+ Web 路线复核

- 审计日期: 2026-10-29
- 审计员: audit-web
- 集群: C+（Web/JS 运行时补充：M4 开发循环模拟器）
- 覆盖: **1 个条目**（citron-neo/emulator）＋ Web 路线复核结论（`1.1）

## 方法

1. **GitHub REST API**（cred_use GH_TOKEN，审计时 x-ratelimit-remaining 4811）取 repo 元数据、HEAD commit、`/tags`、`/releases/latest`、`/license`、根目录 `contents`、指定 commit（`0076ee8f…`、`0237a9b88…`）。注：cred_use 返回串超过约 20k 字符会被截断，采用「首个 `{`/`[` 到最后一个 `}`/`]`」的容错解析；`/releases?per_page=10` 因此不可用，只用 `/releases/latest`。
2. **raw.githubusercontent.com**（`curl -x http://127.0.0.1:7897`）逐文件抓取并阅读：`README.md`、`LICENSE`、`.gitmodules`、`CMakeLists.txt`、`vcpkg.json`、`docs/BUILDING-CITRON-WINDOWS.md`、`src/common/fs/path_util.cpp`、`src/citron/main.cpp`。
3. **GitHub HTML 目录页**抓 `LICENSES/` 文件名（contents API 响应超限被截断，见「未验证 / 失败项」）。
4. **本地实测**（只运行官方 release 二进制，未构建）：下载 Windows msvc nightly 资产 → 校验 sha256 → 解压 → 部署 Brewser 预编译 NRO＋最小 HTML 探针页 → `window_capture` 截图 + 读 Citron 日志；另用 hbmenu 作对照。实测细节、截图与日志见 [web-02-citron-smoke.md](../experiments/web-02-citron-smoke.md)。

本轮**未**克隆仓库、**未**构建 Citron/Brewser、**未**安装任何软件、**未**下载/读取商业游戏数据或固件；`prod.keys`/`title.keys` 为用户本机既有文件，仅复制到 Citron 用户目录供启动使用，未打印内容、未入库。

## 总览表

| 条目 | 用途 | 精确版本（tag/commit） | 许可证(SPDX) | 健康 | 结论 |
|---|---|---|---|---|---|
| citron-neo/emulator | Switch 模拟器（Citron 代码库续作），M4 开发循环/冒烟验证候选 | HEAD `c3aa70f81e15ea97ee85b6a9a71cbf75d370851e`（2026-10-25）；最新 tag `2026-04-27` → `0076ee8fcaab0346de59a357a80700541decbaeb`；**实测 nightly `0237a9b88a5047b9940ab3b3c3412d71cf8e50be`（2026-04-27）** | GPL-3.0-or-later | 活跃（2026-10-25 push；597★；93 open；无公开 CI） | **通过**：能完整运行 Brewser v0.1.131 预编译 NRO（HTML/DOM/CSS/JS/Canvas2D/WebGL/localStorage）；仅作开发/CI 模拟器，GPL 代码不并入 GalNX 发布物 |

## 条目详情

### 1. citron-neo/emulator

- **URL**: https://github.com/citron-neo/emulator ｜ **默认分支**: `main`
- **HEAD**: `c3aa70f81e15ea97ee85b6a9a71cbf75d370851e`，提交日期 **2026-10-25**（2026-10-25T23:55:59Z）；msg 首行 `Merge pull request #386 from HopeSuffers/fix/macos-thread-priority`（作者 Ploo）。
- **最近 tag**: 共 4 个（全部早于 HEAD 约 6 个月）：`2026-04-27` → `0076ee8fcaab0346de59a357a80700541decbaeb`（commit date 2026-04-27T09:04:54Z，msg `shader_recompiler/texture_pass: fall back to 8 when cbuf size is unknown`）；`2026-04-17` → `0db11ed05fa63dfa401584c7cd7afb2e1190643d`；`2026-03-27` → `4797110b08c186ea89ec66a4b7cd49ff721060a2`；`2026-03-20` → `bf34817f7b064ccd1c527d599caba41bde2bdd18`。
- **最新 release**: tag_name `2026-04-27`，name `2026-04-27`，published_at **2026-04-27T13:57:23Z**，prerelease=false，draft=false，target_commitish `main`。**关键不一致**：release 资产文件名带 `nightly-0237a9b88`，而 `0237a9b88a5047b9940ab3b3c3412d71cf8e50be`（2026-04-27T07:21:23Z，作者 collecting）≠ tag `2026-04-27` 指向的 `0076ee8f…` → **资产构建 commit 与 tag 不对应**；且版本串为 `main-0237a9b88`。故版本锁定必须锁**资产 sha256**，不能只锁 tag。
- **发布资产**（release `2026-04-27`，Windows 相关）：
  - `Citron-windows-nightly-0237a9b88-x64-msvc.zip` **40,497,628 B**，GitHub digest `sha256:0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb`，下载 73,258 次（**本轮实测使用**）；
  - `Citron-windows-nightly-0237a9b88-x64-clangtron.zip` 53,286,760 B（digest `sha256:8729798b…3e20c`，下载 94,303 次）；
  - `Citron-macOS-nightly-0237a9b88.dmg` 73,751,331 B；Linux AppImage 三档 96,062,994 / 97,390,347 / 97,460,881 B；Android APK 22,157,733 B 等。下载前缀：`https://github.com/citron-neo/emulator/releases/download/2026-04-27/`。
- **许可证**: SPDX **GPL-3.0-or-later**（README 原文 `GPL-3.0-or-later. See LICENSE. Third-party components and their licences are in LICENSES/`；GitHub API `/license` 报告 key `gpl-3.0` / spdx_id `GPL-3.0`）。许可证文件：根 `LICENSE`（35,149 B，GPLv3 标准全文，首行 `GNU GENERAL PUBLIC LICENSE / Version 3, 29 June 2007`）。第三方许可文本位于 `LICENSES/`（REUSE 布局；抓到的文件名：`Apache-2.0`、`BSD-2-Clause`、`BSD-3-Clause`、`BSL-1.0`、`CC-BY-4.0`、`CC-BY-SA-3.0`、`CC0-1.0`、`GPL-2.0-or-later`、`GPL-3.0-or-later`、`LGPL-3.0-or-later`、`LLVM-exception`、`MIT`、`MPL-2.0`、`Unlicense`、`WTFPL`、`Zlib` 的 `.txt`）。注意：`CMakeLists.txt`、`.gitmodules` 等源文件 SPDX 头为 `GPL-2.0-or-later`（Citra/yuzu/citron 血统），README 与 LICENSE 为 GPL-3.0-or-later → **以 GPL-3.0-or-later 处理分发义务**。义务要点：分发修改版/衍生二进制须提供对应源码并以同许可授权；若 GalNX 仅把官方二进制当作**外部开发工具/测试模拟器**使用、不捆绑不分发其代码，则 GPL 不传染 GalNX 自身。
- **健康**: archived=false；pushed_at 2026-10-25T23:55:59Z；stars 597；forks 67；open issues 93；size 73,729 KB；主语言 C++；创建 2026-03-14T03:23:07Z；description `The switch fell off https://citron-neo.org/`；homepage 空。**无 `.github/` 目录 → 无公开 CI workflow 证据**（README 称开发/维护在 Discord）。
- **构建系统**: CMake（最低 3.22）+ Ninja；依赖双轨获取：**CPM**（Linux/Clangtron；README 原文 `Library dependencies are fetched at configure time by CPM, so you don't need to initialise submodules first.`）或 **vcpkg**（native MSVC/Android，`vcpkg.json` builtin-baseline `c3173be258001c60814b6adf161322b6eb3688ee`）。Windows 两条路径（`docs/BUILDING-CITRON-WINDOWS.md`，26,132 B）：① `clang-cl` 原生（VS2022 + C++ Clang tools + Win11 SDK + MSYS2 CLANG64 + Strawberry Perl + Python 3.12 + aqtinstall，Qt 用 msvc2022_64 预编译），PGO（IR/CS-IRPGO）+ full LTO，`./build-clangtron-windows.sh setup/generate/use --compiler clang-cl`；② `llvm-mingw` 交叉（Linux 或 MSYS2 CLANG64；clang-21/lld-21/llvm-profdata-21，BOLT/Propeller 为实验阶段、不推荐）。Linux：`./build-citron-linux.sh setup` → `use --pgo none --lto full`，产物 `build/use-nopgo/bin/citron`。Android：`./gradlew assembleMainlineRelease`。**无公开 CI 配置**。
- **关键依赖**（`.gitmodules` + `vcpkg.json` + `CMakeLists.txt` options + 实测 DLL）：Boost 1.90（`boost_context-vc143-mt-x64-1_90.dll`）、Qt 6.9.3（`Qt6Core/Gui/Network/Svg/Widgets.dll`）、SDL2、FFmpeg（`avcodec-62`/`avfilter-11`/`avutil-60`/`swscale-9`，vcpkg 中 `avcodec,avfilter,swscale`）、OpenSSL 3（`libcrypto-3-x64`/`libssl-3-x64`）、OpenAL32、cubeb、enet、libusb、mbedtls、xbyak、oaknut、Vulkan-Headers、Vulkan-Utility-Libraries、SPIRV-Headers、breakpad、simpleini、libadrenotools、cpp-jwt、cpp-httplib、opus、zstd/lz4/zlib/fmt/nlohmann-json/libarchive；overrides：catch2 3.3.1、fmt 12.1.0。渲染后端 Vulkan。
- **README 声称**: `Citron Neo is an open-source emulator that continues the Citron codebase. Runs on Windows, Linux, macOS and Android (arm64). Development and maintenance happen on Discord.`；`Library dependencies are fetched at configure time by CPM…`；Windows `Build with clang-cl natively, or cross-compile from Linux with llvm-mingw`；Android `./gradlew assembleMainlineRelease`（无 release keystore 时用内置 debug key 签名）；`Licence: GPL-3.0-or-later. See LICENSE.`（README 1,435 B）。
- **未验证 / 风险**:
  1. **资产 ≠ tag**：release 资产对应 `0237a9b88`，tag `2026-04-27` 指向 `0076ee8f` → 无法用 tag 复现二进制；只能锁资产 sha256。
  2. **无公开 CI**：无 workflow 可核验构建来源，官方 nightly 渠道指向 `api.github.com/repos/citron-neo/CI/releases`（实测日志中出现，该仓库不在本审计范围）。
  3. **兼容性未知**：本机启动日志 `LoadCompatibilityList: Game compatibility list is empty or unreadable`（本地列表缺失、内置资源为空）→ 无逐游戏兼容性证据；93 个 open issues。
  4. **Grass/Unity 等发行说明不等于验证**：release body 仅称 TOMODACHI LIFE 渲染修复、fw22 兼容、FFmpeg 更新、unity build 修复；未声称对 Galgame/网页运行时兼容。
  5. **无固件**：日志 `SetFirmwareVersion: Installed firmware: No firmware available` + `SystemVersion: called - Using hardcoded firmware version 'NintendoSDK Firmware for NX 22.0.0-3.0'` → 用硬编码兼容版本，真实固件行为可能不同；`prod.keys`/`title.keys` 需用户自备，不得入库。
  6. **着色器解码断言**：本轮运行 Brewser 期间出现 112 条 `Debug <Critical> shader_recompiler\frontend\maxwell\decode.cpp:49:operator (): Assertion Failed!`（非致命，但持续刷日志，说明存在未覆盖的 Maxwell 指令解码路径）。
  7. **模拟器 ≠ 真机**：主机 GPU/驱动（NVIDIA Vulkan）与 Switch（Tegra X1 / Mesa Nouveau）不同，`Ampere and newer have broken float16 math`、`NVIDIA Drivers >= 510 do not support MSAA image blits` 等警告说明渲染路径有已知妥协；不能替代真机验收。
  8. **许可混杂**：README/LICENSE 为 GPL-3.0-or-later，源文件 SPDX 为 GPL-2.0-or-later，第三方文本在 `LICENSES/`；若未来把模拟器或其代码并入 GalNX 分发，须整体按 GPL-3.0-or-later 合规（本阶段不计划如此）。
- **来源 URLs**:
  - 仓库 https://github.com/citron-neo/emulator
  - README https://github.com/citron-neo/emulator/blob/main/README.md
  - LICENSE https://github.com/citron-neo/emulator/blob/main/LICENSE ｜ 第三方许可目录 https://github.com/citron-neo/emulator/tree/main/LICENSES
  - HEAD commit https://github.com/citron-neo/emulator/commit/c3aa70f81e15ea97ee85b6a9a71cbf75d370851e
  - tags 列表 https://github.com/citron-neo/emulator/tags ｜ tag commit https://github.com/citron-neo/emulator/commit/0076ee8fcaab0346de59a357a80700541decbaeb
  - release https://github.com/citron-neo/emulator/releases/tag/2026-04-27 ｜ 实测资产 https://github.com/citron-neo/emulator/releases/download/2026-04-27/Citron-windows-nightly-0237a9b88-x64-msvc.zip
  - nightly 构建 commit https://github.com/citron-neo/emulator/commit/0237a9b88a5047b9940ab3b3c3412d71cf8e50be
  - 构建文档 https://github.com/citron-neo/emulator/blob/main/docs/BUILDING-CITRON-WINDOWS.md ｜ CMakeLists https://github.com/citron-neo/emulator/blob/main/CMakeLists.txt ｜ vcpkg https://github.com/citron-neo/emulator/blob/main/vcpkg.json ｜ gitmodules https://github.com/citron-neo/emulator/blob/main/.gitmodules
  - 路径逻辑 https://github.com/citron-neo/emulator/blob/main/src/common/fs/path_util.cpp ｜ CLI https://github.com/citron-neo/emulator/blob/main/src/citron/main.cpp

#### 1.1 Web 路线复核（本轮实测结论）

**背景**：web-01 在 Ryujinx Canary 1.3.265 上加载 Brewser/nx.js 系 NRO 停滞（`Loading as homebrew.` 后无后续；hbmenu/appstore 正常），当时无法进入 M4 开发循环。

**本轮结果**（详见 [web-02 实验报告](../experiments/web-02-citron-smoke.md)）：Citron Neo nightly `0237a9b88`（Windows msvc，Vulkan 后端，firmware 兼容值 22.0.0-3.0）**成功运行 Brewser v0.1.131 预编译 NRO**：

- 窗口标题变为 `citron Nightly | 0237a9b88 | brewser (64-bit) | NVIDIA`；
- 探针页（DOM＋CSS＋inline JS＋`setInterval`＋`requestAnimationFrame`＋Canvas2D＋WebGL＋`localStorage`）全部通过，状态行 `localStorage:1 | WebGL:OK OpenGL ES 3.2 Mesa 20.1.0-rc3 |`；两次截图之间 `TICKS 17→75`、`frame 219→1119` → JS 定时器与 rAF 持续运行；
- Brewser 完成 `sdmc:/switch/brewser/` 首次 seed（`seed-fingerprint`、`shell/home.html` 等），证明主程序真实执行；
- 第二次启动复现成功（2/2）；hbmenu 对照行为与 Ryujinx 一致（`Error: launchInit() failed.`，属 hbmenu 以 application 模式直接启动的预期）。

→ **Web 路线在模拟器侧的加载/执行阻塞已被排除**；Brewser 自身 API 覆盖与私有运行时风险不变（见 [02-web.md](02-web.md) 的 Brewser 条目），真机验证仍待做。

## 未验证 / 失败项

1. `LICENSES/` 目录逐项**内容**未读取：GitHub contents API 响应超 20k 被截断，仅通过 HTML 目录页取得文件名列表；未逐个核对每份许可文本与组件映射。
2. `/releases?per_page=10` 列表不可用（cred_use 截断导致解析为空数组），仅取 `/releases/latest` 一个 release；更早 release 未审计。
3. `0237a9b88` 与 tag `0076ee8f` 的祖先/分支关系未验证（只确认两者 commit 不同）。
4. Citron 官方 nightly 构建渠道（`citron-neo/CI` 仓库、Discord）未审计，无法核验资产构建环境。
5. 本机**未安装固件**（用硬编码 22.0.0-3.0 兼容值）→ 固件相关行为、真实 NAND/存档路径未验证。
6. 兼容性表在本机为空，未验证 Citron 对任何商业游戏的兼容性（本轮也按要求不接触商业游戏数据）。
7. 输入映射（手柄）、音频输出、联网（BSD socket 为 `STUBBED`）、长时间稳定性、性能基准均未验证。

## 对 GalNX 的建议（版本锁定、接入顺序、阻塞项）

- **版本锁定**：M4 的模拟器基线 = Citron Neo Windows msvc nightly 资产 `Citron-windows-nightly-0237a9b88-x64-msvc.zip`，**sha256 `0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb`（40,497,628 B）**，来源 URL 记入脚本；运行后应在日志确认 `citron Version: citron Development Build | main-0237a9b88`。**不要**把 tag `2026-04-27` 当作二进制版本（资产与 tag commit 不一致）。
- **接入顺序**：M4 起用 Citron 作 Brewser 开发循环（Brewser 官方 `make sdmc` 路径）＋ CI 冒烟三件套：① 窗口标题含 `brewser (64-bit)`；② 日志含 `Loading brewser (01F5905036D20000)` 与 `Booting game: 01F5905036D20000 | brewser (64-bit)`；③ `sdmc:/switch/brewser/seed-fingerprint` 生成。Ryujinx 仅作第二意见/回归对照。
- **阻塞项**：模拟器侧**无硬阻塞**。遗留：① 真机验证（Atmosphère + hbmenu 完整内存模式）；② Brewser 私有 `@switch-web/runtime` 源码不可得（见 02-web.md）；③ RPG Maker MV/TyranoScript 兼容层未验证（M4 前需 PoC）；④ keys/firmware 合规：用户自备、不入库、不随发布物分发。
- **合规**：Citron Neo 为 GPL-3.0-or-later，GalNX **不捆绑、不修改、不分发**其代码；脚本只记录官方 release URL + sha256，属工具链外部依赖。

<!-- AUDIT-JSON-BEGIN -->
```galnx-audit
[
  {
    "name": "citron-neo/emulator",
    "url": "https://github.com/citron-neo/emulator",
    "default_branch": "main",
    "head_sha": "c3aa70f81e15ea97ee85b6a9a71cbf75d370851e",
    "head_date": "2026-10-25",
    "pinned": "tag 2026-04-27 = 0076ee8fcaab0346de59a357a80700541decbaeb; tested nightly asset = 0237a9b88a5047b9940ab3b3c3412d71cf8e50be (zip sha256 0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb, 40497628 B)",
    "license_spdx": "GPL-3.0-or-later",
    "license_file": "LICENSE",
    "license_notes": "Root LICENSE = GPLv3 full text (35149 B). README states GPL-3.0-or-later; GitHub API license key gpl-3.0 / spdx_id GPL-3.0. Source file SPDX headers (CMakeLists.txt, .gitmodules) say GPL-2.0-or-later. Third-party licence texts in LICENSES/ (REUSE layout; names observed: Apache-2.0, BSD-2-Clause, BSD-3-Clause, BSL-1.0, CC-BY-4.0, CC-BY-SA-3.0, CC0-1.0, GPL-2.0-or-later, GPL-3.0-or-later, LGPL-3.0-or-later, LLVM-exception, MIT, MPL-2.0, Unlicense, WTFPL, Zlib). Distribution of modified/derived code requires source + same licence; using the official binary only as an external dev/test tool does not impose GPL on GalNX.",
    "archived": false,
    "last_push": "2026-10-25T23:55:59Z",
    "stars": 597,
    "open_issues": 93,
    "build_system": "CMake >= 3.22 + Ninja. Deps via CPM (Linux/Clangtron, fetched at configure time) or vcpkg (native MSVC/Android, builtin-baseline c3173be258001c60814b6adf161322b6eb3688ee). Windows paths: native clang-cl (VS2022 C++ Clang tools + Win11 SDK + MSYS2 CLANG64 + Strawberry Perl + Python 3.12 + aqt; PGO+full LTO, build-clangtron-windows.sh setup/generate/use --compiler clang-cl) or llvm-mingw cross-compile from Linux/MSYS2 (clang-21/lld-21, BOLT/Propeller experimental). Linux build-citron-linux.sh setup + use --pgo none --lto full -> build/use-nopgo/bin/citron. Android ./gradlew assembleMainlineRelease (src/android). No public CI workflow (.github/ absent).",
    "build_deps": "Boost 1.90 (boost_context-vc143-mt-x64-1_90), Qt 6.9.3 (Core/Gui/Network/Svg/Widgets), SDL2, FFmpeg (avcodec-62/avfilter-11/avutil-60/swscale-9; vcpkg features avcodec,avfilter,swscale), OpenSSL 3 (libcrypto-3-x64/libssl-3-x64), OpenAL32, cubeb, enet, libusb, mbedtls, xbyak, oaknut, Vulkan-Headers, Vulkan-Utility-Libraries, SPIRV-Headers, breakpad, simpleini, libadrenotools, cpp-jwt, cpp-httplib, opus, zstd/lz4/zlib/fmt/nlohmann-json/libarchive; vcpkg overrides catch2 3.3.1, fmt 12.1.0. Vulkan renderer.",
    "readme_claims": "README: 'Citron Neo is an open-source emulator that continues the Citron codebase. Runs on Windows, Linux, macOS and Android (arm64). Development and maintenance happen on Discord.' 'Library dependencies are fetched at configure time by CPM, so you don't need to initialise submodules first.' Windows: 'Build with clang-cl natively, or cross-compile from Linux with llvm-mingw'; Android './gradlew assembleMainlineRelease'; 'Licence: GPL-3.0-or-later. See LICENSE.' Release body claims TOMODACHI LIFE rendering fixes, fw22 compatibility, audio crash fixes, mip map fixes, FFmpeg update, full unity build fixes.",
    "readme_claim_url": "https://github.com/citron-neo/emulator/blob/main/README.md",
    "risks": "1) Release asset commit 0237a9b88 != tag 2026-04-27 commit 0076ee8f -> cannot rebuild from tag; lock by asset sha256. 2) No public CI workflow; official nightly channel is citron-neo/CI (not audited). 3) Compatibility list empty on this host; 93 open issues; no per-game compatibility evidence. 4) No firmware installed -> hardcoded firmware 22.0.0-3.0 compatibility value; keys must be user-supplied and never redistributed. 5) 112 Maxwell shader decode assertion failures during Brewser run (non-fatal but indicates uncovered decode paths). 6) Emulator != hardware: NVIDIA Vulkan vs Tegra X1/Mesa Nouveau; warnings 'Ampere and newer have broken float16 math', 'NVIDIA Drivers >= 510 do not support MSAA image blits'. 7) Licence mix: README/LICENSE GPL-3.0-or-later but source SPDX GPL-2.0-or-later; treat distribution as GPL-3.0-or-later. 8) Not a substitute for hardware acceptance testing.",
    "verification_level": "read-only",
    "verification_failures": "LICENSES/ contents not read file-by-file (contents API response >20k truncated; only HTML directory name list obtained). /releases?per_page=10 unusable due to cred_use response truncation; only /releases/latest audited. Ancestry relation of 0237a9b88 vs tag commit 0076ee8f not verified. Official nightly CI repo not audited. Firmware not installed (hardcoded 22.0.0-3.0). No commercial-game compatibility tested by design.",
    "source_urls": [
      "https://github.com/citron-neo/emulator",
      "https://github.com/citron-neo/emulator/blob/main/README.md",
      "https://github.com/citron-neo/emulator/blob/main/LICENSE",
      "https://github.com/citron-neo/emulator/tree/main/LICENSES",
      "https://github.com/citron-neo/emulator/commit/c3aa70f81e15ea97ee85b6a9a71cbf75d370851e",
      "https://github.com/citron-neo/emulator/commit/0076ee8fcaab0346de59a357a80700541decbaeb",
      "https://github.com/citron-neo/emulator/commit/0237a9b88a5047b9940ab3b3c3412d71cf8e50be",
      "https://github.com/citron-neo/emulator/releases/tag/2026-04-27",
      "https://github.com/citron-neo/emulator/releases/download/2026-04-27/Citron-windows-nightly-0237a9b88-x64-msvc.zip",
      "https://github.com/citron-neo/emulator/blob/main/docs/BUILDING-CITRON-WINDOWS.md",
      "https://github.com/citron-neo/emulator/blob/main/CMakeLists.txt",
      "https://github.com/citron-neo/emulator/blob/main/vcpkg.json",
      "https://github.com/citron-neo/emulator/blob/main/.gitmodules",
      "https://github.com/citron-neo/emulator/blob/main/src/common/fs/path_util.cpp",
      "https://github.com/citron-neo/emulator/blob/main/src/citron/main.cpp"
    ],
    "audited_at": "2026-10-29"
  }
]
```
<!-- AUDIT-JSON-END -->
