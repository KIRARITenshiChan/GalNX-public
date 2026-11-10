# 集群 C：Web / JS 运行时 审计（只读）

- 审计日期: 2026-10-29
- 审计员: audit-web
- 方法: ① GitHub REST API（`web_fetch` 读取 `api.github.com`，长响应完整无截断；`cred_use` GH_TOKEN 作为备用通道）取仓库元数据、HEAD commit、tags、releases、license；② 原始文件抓取（`curl -x http://127.0.0.1:7897` 访问 `raw.githubusercontent.com`；`web_fetch` 抓 `raw.githubusercontent.com` 在本会话返回 404，故 raw 文件走 curl）逐文件阅读 README/LICENSE/Makefile/package.json/CI/源码树；③ 官方站点 `docs.brewser.io` 逐页抓取并剥标签阅读；④ 逐行阅读仓库内构建脚本与迁移文档。**未执行任何构建/编译，未在真机或模拟器运行，未克隆仓库、未读取任何商业游戏数据。**
- 覆盖: 7 个条目（核心 4：Brewser、nx.js_extended、BurialNX、上游 nx.js；旁支登记 3：rexglue-sdk、XenonRecomp、XenosRecomp）

## 总览表

| 条目 | 用途 | 精确版本（tag/commit） | 许可证(SPDX) | 健康 | 结论 |
|---|---|---|---|---|---|
| natureglass/Brewser | Switch 上的 Web 应用运行时外壳（自研 DOM/CSS/layout + V8 + Skia + WebGL1/2，基于 nx.js fork） | v0.1.1.31 / `8040580e92e40a60f704a6478ee296b105212f1b` | MPL-2.0 | 活跃（2026-09-17 push，1 open，15★） | M4 首要评估对象；可用预编译 NRO 直接做真机验证 |
| natureglass/nx.js_extended | Brewser 背后的引擎 fork（V8/Skia/WebGL 原生层与 V8 迁移） | 分支 `nxjs-extended@90fbed8b…`（main `f41fb550…` = v1.0.0-beta.6） | MIT | 活跃（2026-09-17 push，0 open，1★） | 构建链重（devkitPro + 自定义 GHCR 包）；实验性，不作发布依赖 |
| ETCHDEV/BurialNX | 针对单一 RPG Maker MV 作品（TCOAAL）的专用 nx.js loader/兼容层 | v0.1.1 / `c2c6691c0c73a2fbefadadd2bde8ecbe7d3f013b` | AGPL-3.0-or-later | 新项目（2026-10-18 创建，2026-10-19 push，2 open，2★） | 只作架构/诊断参考，AGPL 传染，禁止直接引代码 |
| TooTallNate/nx.js | Switch homebrew 的 JS 运行时（V8 + Skia + WebGL2 + FFmpeg） | v1.0.0-beta.7 / `a649611a1a4daca09924cd1a436c7ca786f91592` | MIT | 活跃（2026-10-13 push，12 open，269★） | 可作 HTML5/Canvas 底座；**无 DOM/CSS**，非浏览器 |
| rexglue/rexglue-sdk | Xbox 360 PowerPC 静态重编译工具/运行时 | v0.10.0 / `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2` | BSD-3-Clause | 活跃（2026-10-02 push，114 open，1200★） | 与 Galgame 路线无关；§7.7 旁支 |
| hedge-dev/XenonRecomp | Xbox 360 可执行文件 → C++ 反编译工具 | none（无 tag）/ `ddd128bcca99fe8bfbb99bea583c972351fa6ace` | MIT | 停更约 14 个月（2025-08-04 push，94 open，6640★） | 不列入第一阶段依赖 |
| hedge-dev/XenosRecomp | Xbox 360 着色器 → HLSL 转换 | none（无 tag）/ `990d03b28a27b50277ee5d8d942e1c5f873869d1` | MIT | 低活跃（2026-03-12 push，10 open，505★） | 不列入第一阶段依赖 |

## 条目详情

### 1. natureglass/Brewser

- **URL**: https://github.com/natureglass/Brewser ｜ **默认分支**: `main`
- **HEAD**: `8040580e92e40a60f704a6478ee296b105212f1b`，提交日期 2026-09-17（2026-09-17T20:30:21Z，msg "HLS playback - FreeTV support"）
- **最近 tag**: `v0.1.1.31` → `8040580e92e40a60f704a6478ee296b105212f1b`（该 commit 的日期 2026-09-17）；对应 GitHub release 名/标题为 "v0.1.131"，published 2026-09-15T11:44:46Z，target_commitish=main，draft=false，prerelease=false。前序 tag：`v0.1.120` → `dc2ffb10b3051b31d08e8b1db23b5de735f5c849`、`v0.1.118` → `82e370aa9c15603f380575ff561c8d73de983ca3`、`v0.1.114` → `a9b3a87528f78ccddb777e695b61467e4adf97eb`（GitHub tags API 按名称字典序返回，不能当日期序用）。**异常**：release 发布日 2026-09-15 早于 tag 指向 commit 的日期 2026-09-17 → tag 可能被移动/重建；但 `dist/checksums.txt`（main HEAD）中的 sha256 与 release asset digest 完全一致，故发布二进制 = main HEAD 的 dist，溯源可接受。
- **许可证**: SPDX `MPL-2.0`，许可证文件 `LICENSE`（16,726 B，Mozilla Public License Version 2.0 全文）；README badge 标注 MPL-2.0。**冲突**：`package.json` 的 `license` 字段写 "MIT"（与仓库 LICENSE 不一致），以 LICENSE 文件为准 → MPL-2.0。义务要点：MPL-2.0 为文件级 copyleft，分发修改过的 MPL 文件须公开该文件源码；未修改文件只需保留声明与获取途径；允许与专有代码同包分发。
- **健康**: archived=false；最后 push 2026-09-17T20:32:54Z；open issues=1；stars=15；forks=1；仓库 size 284,935 KB；主语言 TypeScript；创建于 2026-05-27。
- **构建系统**: GNU make。`Makefile` 默认目标 = bump version → build shell（`node scripts/build-main.mjs`，esbuild 打包 `src/main.ts`，注入 `__BREWSER_VERSION__`/`__BREWSER_COUNTER__`/`__BREWSER_KEYRING_JSON__`）→ `stage-main.mjs` 把 `build/main.js` 复制进 `romfs/` → package（`@nx.js/nro --fat`）→ sign/verify，产出 `dist/brewser.nro` + `dist/update.json`。**默认构建不需要 devkitPro**（只需 node/npm/python，复用预编译 engine NRO）；`make -f Makefile_nxjs` 重建引擎时才需 devkitPro（msys2）。`make sdmc=<path>` 是 Citron 模拟器 dev loop（不 bump、不签名）。无公开 CI workflow（`.github/` 仅 ISSUE_TEMPLATE，`/actions/workflows` 返回 404）。
- **关键依赖**: `@switch-web/runtime`（`link:./runtime`，本地私有包，源码不在公仓）＋ `css-tree ^3.2.1`（lock 3.2.1）；devDeps：`@nx.js/nro`、`@nx.js/nsp`、`@nx.js/runtime` 全为 `link:../nxjs-extended/packages/*`，`esbuild ^0.27.3`（lock 0.27.7）、`typescript 5.2.2`。`versions.json`：nx.js `1.0.0-beta.5`、runtime `0.0.1`、brewser `0.1.131`。NACP app id `01f5905036d20000`。
- **发布资产**（release v0.1.1.31）: `brewser.nro` 76,546,123 B，sha256 `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13`（500 次下载）；`brewser-forwarder.nsp` 363,224 B，sha256 `1e3268fe83d45a811c38366645ed59854d6a0a4243de9c97ab156ffdc1a33af8`（322 次下载）；`checksums.txt` 166 B。分布版 `dist/update.json`：format `brewser-update/1`，keyId `k_b88260ef6beba84b`，payload（base64）含 version 0.1.131、counter 143、nroSize 76,546,123、chunkSize 4,194,304、20 个 chunk sha256、rootHash、components、nro URL（raw.githubusercontent.com/natureglass/Brewser/main/dist/brewser.nro），signature 存在。
- **README 声称**: "A web runtime and app platform for devices your browser can't reach - starting with the Nintendo Switch."；要求 Atmosphère CFW（tested on 1.10+）+ hbmenu，装到 `sd:/switch/brewser.nro`，用 hbmenu 全内存 application mode（按住 R 启动游戏）而非 applet mode；每 release 附 `brewser-forwarder.nsp`（需 sigpatches）；内置 Apps→Check for Updates（用 baked keyring 做密码学校验、拒绝回滚）；nightly 在 `dist/`；声明不运行商业 Switch 游戏/ROM。功能声称：WebUSB/Web Bluetooth/Web Audio/Sensor APIs；hosted WebSocket relay 多人；按 app 声明并被强制执行的权限系统（含 allowed_origins 与 user_origins 首次审批）；Offline Mode；on-screen keyboard；toolbar；save-data；leaderboards；catalogue；Google sign-in；可主题化 shell。Under the hood：nx.js fork，"V8 with JIT and WebAssembly, Skia rendering, and WebGL 1/2 on Mesa (Nouveau)"；Three.js/PixiJS/Phaser；硬件视频含 HLS 720p60；硬件 API 另含 WebHID、Web Serial（CH340 & CP2102）、Web MIDI、Web NFC、WebNN。

#### 1.1 运行时架构与版本

- 分层（官方 `/docs/runtime/architecture`）：JavaScript engine = **V8 (JIT)**；2D rendering = **Skia**；GPU driver = **Mesa/Nouveau**（OpenGL ES via EGL）；Base runtime = **Fork of nx.js with Brewser extensions**。Canvas 2D 由 Skia 绘制；WebGL1/2 走 Brewser 自己的 bridge（在 nx.js 初始 GL wiring 上扩展）+ Mesa Nouveau GLES；runtime 管理共享 GL state，使 Skia UI 与 WebGL app 共存；每次 app launch 建立全新 JS context，退出时释放 GL resources/audio graph/pending work。
- 版本取证（来自引擎 fork 分支 `natureglass/nx.js_extended@nxjs-extended` 的 Makefile 与 MIGRATION_PLAN；**Brewser 发布二进制内嵌版本未直接验证**）：V8 = `switch-v8 15.0.243-9`（对应 upstream V8 tag 15.0.243，monolith 无 ICU）；Skia = `switch-skia 149-3`（MIGRATION_PLAN 明确 **pinned 不得随意升级**：recipe 依赖 Skia 不假设自己拥有持久 GL state，升级须重验 Skia/WebGL coexistence）；GL = Mesa Nouveau，项目日志样本 `[skia] GL version=OpenGL ES 3.2 Mesa 20.1.0-rc3 vendor=nouveau renderer=NV120`；FFmpeg（libavformat/libavcodec/libswscale/libswresample/libavutil + dav1d）、mbedTLS、freetype/harfbuzz、libuv、ada、libnx。
- **无 SDL/GLFW**：nx.js_extended Makefile 直接链 libnx + `-lEGL -lGLESv2 -lglapi -ldrm_nouveau`（Mesa Nouveau），窗口/输入事件由 libnx 提供。
- 与上游差异：upstream nx.js 无 WebGL1、无 WebGL extensions（MIGRATION_PLAN 注明要自己加）；module list 硬编码在 `source/main.cc`，扩展通过新增 `nx_init_*` 行注册；"Zero fork is impossible; thin patch is the goal"。
- 已知引擎限制：switch-v8 **不带 ICU**（`/\p{Extended_Pictographic}/u` 解析即抛错，Brewser 用静态表替代）；Mesa Nouveau 不能 SAMPLE `sampler3D`/`sampler2DArray`/`samplerCube`（返回 `vec4(0)`，需 workaround）；`--jitless`（Citron/模拟器）下 **完全没有 WebAssembly**（Liftoff 需 JIT code arena），WASM 首次调用即硬错。

#### 1.2 依赖获取方式（是否必须自建 V8/Skia；构建一次需要什么；是否有预编译运行时）

- **构建 Brewser shell 不需要自建 V8/Skia**：默认 `make` 只在 Node 里用 esbuild 打包 `src/main.ts`，再复用预编译 engine NRO 打 fat NRO（`@nx.js/nro --fat`）；环境 = node + npm + python（无 devkitPro）。
- **重建 engine 才需要**：devkitPro（`DEVKITPRO` 未设置时 Makefile 直接报 "Please set DEVKITPRO"）+ `make -f Makefile_nxjs`；V8/Skia/libuv/ada/dav1d 全部来自预编译 GHCR 包 `ghcr.io/tootallnate/pacman-packages:nxjs`（`docker pull` → `docker run ... cp packages/*/*.pkg.tar.zst /host` → `sudo dkp-pacman -U *.pkg.tar.zst`），即 **不是从源码编译 V8/Skia**；另需 Node 22、pnpm、jq、Docker（仅 Linux/macOS/WSL）。这套流程与 upstream nx.js README 描述一致。
- **可直接使用的预编译运行时/release：有**。`natureglass/Brewser` release `v0.1.1.31` 提供 76,546,123 B 的 `brewser.nro`（+ forwarder NSP + checksums.txt），digest 与仓库 `dist/` 完全一致；另有 `dist/update.json` 分块签名更新源；nightly 也在 `dist/`。**对 M4 关键：无需自建 V8/Skia 即可把 Web 路线落到真机验证。**
- 未验证：发布二进制内嵌的 V8/Skia 版本是否恰为 15.0.243-9 / 149-3（`versions.json` 只写 nx.js `1.0.0-beta.5`）；engine NRO 与 nx.js_extended 分支 HEAD 是否同源。

#### 1.3 许可证与再分发义务

- 主仓库：**MPL-2.0**（`LICENSE`，16,726 B）。文件级 copyleft：修改过的 MPL 文件分发时须公开对应源码；未修改文件保留声明/出处即可；可与专有代码同包分发。`package.json` 写 "MIT"，与 LICENSE 冲突，报告与后续使用以 LICENSE 为准并注明该冲突。
- 引擎：nx.js fork，**MIT**（`LICENSE`，Copyright (c) 2023 Nathan Rajlich）；Brewser 公仓只含 shell + release tooling，engine 源码在 `nx.js_extended` 分支与私有 `brewser-runtime-v8`。
- 随附第三方组件（V8、Skia、Mesa、FFmpeg、mbedTLS、freetype、harfbuzz、libpng/libjpeg-turbo/libwebp/zlib/zstd/brotli 等）的许可证**未在本仓集中登记**；发布含整个 engine 的 fat NRO 前必须逐项核对 notice/源码义务（V8、Skia 上游为 BSD 类，FFmpeg 许可取决于编译开关 LGPL/GPL——本次均未逐项抓取，按未验证处理）。
- 分发签名：更新源用 baked keyring（`keys/` 仅公钥），私钥不入仓；构建产物带 update.json 签名，拒绝回滚。

#### 1.4 DOM / Canvas / WebGL / WebAudio / localStorage-IndexedDB / fs API 覆盖（官方自称 vs 证据）

下述百分比与缺口来自官方 `docs.brewser.io/docs/engine-status`（官方自称，非本审计实测）：

| API | 官方覆盖 | 已知缺口（官方列出） |
|---|---|---|
| DOM | ~84% | children 不含 text/comment 节点；outerHTML 无 setter；document/window 的 capture-phase listeners 未接；dialog.showModal 无 focus trap/Esc；setPointerCapture 不重定向事件 |
| HTML | ~80% | 无 spec tokenizer/insertion modes；无 content model 与隐式 html/head/body/tbody 合成；comments/doctype 丢弃；无 multipart/form-data（urlencoded GET/POST 可以）；inline SVG 仅子集（无 SMIL）；video 无 subtitle track、poster 不加载；iframe sandbox/CSP 解析但不强制（视为 same-origin） |
| CSS | ~84% | 无 @supports/@import/@layer/@container；无 ::placeholder/::marker/::selection；vertical margin collapsing 部分；grid 无 dense packing/named lines/subgrid；border-collapse 近似；sticky 仅 vertical+page-level；transform 3D 压平、无 true 3D perspective；transition 不覆盖几何属性；@keyframes 不覆盖 geometric box；无 clip-path；3D border styles 画成实心线 |
| Canvas 2D | 支持 | 由 Skia 绘制；性能/一致性未实测 |
| WebGL 1 / 2 | WebGL1 ~92%（官方称最安全目标）、WebGL2 ~85%、合计 ~88% | bridge-backed on Tegra X1；缺口在 extension 覆盖与 layered/3D-texture sampling（Mesa Nouveau 驱动限制）；WebGL conformance 仍 WIP |
| Web Audio | graph ~70% | 硬件后端有；缺 effect nodes：filter/convolver/delay/compressor；audio/video decode（FFmpeg）~85% |
| localStorage | 真持久 | JSON 文件写 SD；全局共享、非 per-app sandbox；无 quota（不会 QuotaExceededError） |
| IndexedDB | 真持久（core API） | databases/versioning、object stores、put/add/get/delete/clear/count/getAll/getAllKeys；**无 cursors/IDBKeyRange/indexes/auto-increment** |
| sessionStorage | **未实现** | — |
| Cache API (`caches`) | **未实现** | — |
| navigator.storage.estimate() | 有 | 报 SD 卡空间 |
| Node fs / require | **无** | app 是纯浏览器语义；无 Node API，无文件系统直访；网络受 allowed_origins 约束（media/img 元素豁免） |
| 总体 | ~26K 行 TS 自研 DOM/CSS/layout，DOM+HTML+CSS 整体 ~83% | 官方目标 "if Chrome does it, Brewser should too"，实际不是 Chrome |

另：官方 Known Limitations 明确 **Unity WebGL 2 exports 尚不支持**（WebGL 1 exports 可以）、video codec 有限、touch 仅 handheld、apps 应 self-contained（runtime module resolution local-only）。

#### 1.5 应用打包与启动方式（离线资源如何放入 SD、入口约定、存档路径）

- **启动流程**：hbmenu 打开 `sd:/switch/brewser.nro` → catalogue 从 `play.brewser.io` 加载 → 选择 app → 抓取 bundle → 在 fresh isolated JS context 启动 → app 渲染并访问 input/audio/manifest 声明的硬件 API；离开 app 时完全 teardown。
- **打包/发布**：app 就是普通 web app（folder + entry，默认 `index.html`）；提交到 brewser.io dashboard，上传 **zip bundle**，平台生成 `manifest.json`（publisher 不手写；严格 schema，未知字段拒绝）。manifest 关键字段：id（reverse-domain）、name、version（semver）、description、logo、entry、categories、permissions、compatibility（switch|web|mobile）、allowed_origins、user_origins、developer、license（SPDX-style）、exitGame、fullscreen、hideMouseDocked/hideMouseUndocked、buttonMapping、publishedAt。管道：Waiting for review → deployed to staging → published（play.brewser.io）/rejected；每次提交自动 security scan。
- **离线资源放 SD**：本地 sideload 直接把 app 目录放到 **`sdmc:/switch/brewser/apps/<reverse-domain-id>/`**（folder 名即 app id，内含 `index.html` 即可，**本地 sideload 不需要 manifest**）；启动 Brewser 后与已下载 app 并列出现。已下载 apps、catalogue cache、app storage 全在 `sdmc:/switch/brewser/` 下；无网络时跳过 boot sync、用 cached catalogue，已下载 app 可长期离线运行。
- **入口约定**：manifest `entry` 字段（默认 `index.html`，必须存在于 bundle）；本地 sideload 以文件夹名作为 app id，入口仍是 `index.html`。
- **存档路径**：`localStorage` / `IndexedDB` → JSON 文件写在 `sdmc:/switch/brewser/…` 下，启动时加载，跨 app launch 与 Brewser self-update 持久（update 不碰 storage）；**storage 全局共享、非 per-app 沙箱**，需用 app id 前缀（`brewser.js` SDK 自动 namespaced，save box 以 package id 为 key）。cloud saves 由 brewser.io 提供（每 user×app ≤256KB JSON blob，Bearer；SDK local-first：先写本地，后台同步）。`sessionStorage`、`Cache API` 未实现。
- **配置/快捷方式**：`sdmc:/switch/brewser/configs/config.json`（含 offlineMode 等）；Create shortcut 会写 `sdmc:/switch/<AppName>.nro`（hbmenu entry，携带 app id 启动参数，直接进 app、跳过 shell；不是 app/runtime 拷贝，`brewser.nro` 必须保持在 `sd:/switch/brewser.nro`；只生成 NRO shortcut，不生成 NSP forwarder）。
- **更新**：内置 updater（`update.json` 分块 sha256 + rootHash + 签名，keyId `k_b88260ef6beba84b`，拒绝回滚）；也可手工替换 nro。

#### 1.6 输入（手柄/触摸）支持方式

- **Gamepad API**（`navigator.getGamepads()`）Standard mapping：0=A、1=B、2=X、3=Y、4=L、5=R、6=ZL、7=ZR、8=−、9=+、10=LStick、11=RStick、12=DpadUp、13=DpadDown、14=DpadLeft、15=DpadRight；4 条 axes（leftX、leftY、rightX、rightY；Y 反相，向上为负）。Nintendo 物理 A/B、X/Y 与 Xbox 位置相反，按钮提示须用 index-to-label，不要假设 Xbox 布局。
- **触摸**：标准 Touch + Pointer events（并合成 click），**仅 handheld**；docked 无触摸，须同时提供手柄路径。
- **体感**：DeviceOrientationEvent 按 W3C spec 映射到 landscape 物理帧，官方称在真机验证（竖直 β=+90°、右滚 γ=−90°）。
- **键盘**：on-screen keyboard 覆盖层（dpad 移动、A 确认、B 取消、+ 提交），web form 需要输入时自动调起；manifest `buttonMapping` 可把键盘键映射到 Switch 控件，让键盘驱动游戏可用手柄玩。
- **退出**：L 回 catalogue；+ 退出 app（published apps 配置 exitGame=PLUS）；HOME 退出 Brewser；L+R 退出 ad-hoc fullscreen；720p 渲染，docked 放大到 TV；software cursor 由 manifest `hideMouseDocked`/`hideMouseUndocked` 控制。

#### 1.7 真机证据与未验证项

- 项目方证据（release notes）：v0.1.114（2026-08-17，首个 stable release）称 "Real V8 JavaScript engine with JIT, verified on actual CFW hardware"、"WebGL2 rendering via Mesa/Nouveau — full curated Three.js demo suite runs on-device"、WebUSB、forwarder generation；v0.1.120（2026-09-07）称 "HW-validated (2026-09-06)"，720p60 视频在设备上稳定 60fps；v0.1.1.31（2026-09-15）称 PixiJS v8 + Phaser、Spine、@pixi/sound 在真机跑，multi-WebGL canvas 各自 tenant FBO，WOFF2 字体，HTML-in-Canvas/foreignObject。引擎侧证据：nx.js_extended `docs/HW_SESSION_RUNBOOK.md` 记录 2026-07-03 真机 session（Tegra X1 / Nouveau NV120 / CFW hbmenu）；MIGRATION_PLAN 记录 Step1 hardware GO（Brewser shell 在真 CFW 硬件启动、UI 渲染、sustained session tick=231+）。
- **独立验证状态**：本审计为只读，未在真机运行、未用 Citron 验证；以上全部是项目方声明，不等于我方验证。verification_level 记 `source-inspected` 而非硬件实测。
- 未验证项：DOM/CSS 覆盖数字的真实样本；发布 NRO 与 nx.js_extended 分支 HEAD 同源性；`@switch-web/runtime` 行为；真机性能/稳定性/长时运行；catalogue 与云存档后端；forwarder NSP 的 sigpatches 合规性；V8/Skia 二进制版本。
- 来源 URLs: https://github.com/natureglass/Brewser ；https://api.github.com/repos/natureglass/Brewser ；https://github.com/natureglass/Brewser/commit/8040580e92e40a60f704a6478ee296b105212f1b ；https://github.com/natureglass/Brewser/releases/tag/v0.1.1.31 ；https://github.com/natureglass/Brewser/blob/main/README.md ；https://github.com/natureglass/Brewser/blob/main/Makefile ；https://github.com/natureglass/Brewser/blob/main/Makefile_nxjs ；https://github.com/natureglass/Brewser/blob/main/package.json ；https://github.com/natureglass/Brewser/blob/main/versions.json ；https://github.com/natureglass/Brewser/blob/main/dist/checksums.txt ；https://github.com/natureglass/Brewser/blob/main/dist/update.json ；https://docs.brewser.io/docs/engine-status ；https://docs.brewser.io/docs/runtime/architecture ；https://docs.brewser.io/docs/runtime/storage ；https://docs.brewser.io/docs/runtime/controls ；https://docs.brewser.io/docs/runtime/input-and-sensors ；https://docs.brewser.io/docs/runtime/shortcuts ；https://docs.brewser.io/docs/publishing/quickstart ；https://docs.brewser.io/docs/publishing/manifest ；https://docs.brewser.io/docs/offline-mode ；https://docs.brewser.io/docs/support/limitations

### 2. natureglass/nx.js_extended

- **URL**: https://github.com/natureglass/nx.js_extended（**上游是 TooTallNate/nx.js 的 fork**；计划 §7.3 未列上游仓库）｜ **默认分支**: `main`
- **HEAD（默认分支）**: `f41fb5506a2da21337d6c9b41f14c69ae2e1418f`，提交日期 2026-07-08（= 上游 tag `v1.0.0-beta.6`）。**真正审计对象是分支 `nxjs-extended`**：HEAD `90fbed8b7bb2f442b38521878a2aa315080bce1a`，提交日期 2026-09-17T21:34:55Z，msg "HLS playback - FreeTV support"；该分支**无 tag**。其余分支：`legacy-qjs` `d5feeed2540dc30da86143992497d8031de56f91`、`upstream-pr/modules-page-level` `a83ee572d3566e3ab565267d5a199da3d93754d3`。
- **最近 tag**: 默认分支 main HEAD 对应上游 `v1.0.0-beta.6`（fork 侧 tags 未逐条复抓，见 verification_failures）；活动分支 `nxjs-extended` 无 tag → M4 只能按分支 HEAD 锁定。
- **许可证**: SPDX `MIT`；`LICENSE`（1,071 B，Copyright (c) 2023 Nathan Rajlich，与上游 nx.js 相同）。义务：保留版权与许可声明；无 copyleft。
- **健康**: archived=false；最后 push 2026-09-17T21:34:59Z；open issues=0；stars=1；forks=1；size 39,338 KB；语言 TypeScript；创建 2026-05-09。
- **构建系统**: devkitPro（devkitA64 + libnx）标准 Makefile（`Makefile` 14,005 B；`TARGET=nxjs`、`APP_TITLEID=016e782e6a730000`、`APP_VERSION` 由 jq 读 `packages/runtime/package.json`；`source/` 109 个 C/C++ 文件，含 `canvas.cc` 120,733 B、`main.cc` 106,066 B、`audio-graph.cc`、`media-decoder.cc`、`skia_gpu.cc`、`gamepad.cc`、`fs.cc`、`tls.cc` 等）；`runtime.js` 经 `tools/embed-runtime.mjs` 嵌为 C 数组；`bootstrap/` + `bootstrap-artifact/` 提供自定义包安装流程；`build.sh`。依赖自定义 GHCR docker 包：`switch-v8 15.0.243-9`（V8 monolith，无 ICU）、`switch-skia 149-3`（Ganesh GL，`skia-horizon-port.o`）、`switch-libuv`、`switch-ada`、`switch-dav1d`；官方 dkp-pacman 提供 switch-dev、freetype、harfbuzz、turbojpeg、webp、png、zstd、mbedtls、ffmpeg 等；vendored `source/brotli` = google/brotli 1.2.0（MIT，WOFF2 用）；Node 22 + pnpm 10.30.3 + jq + Docker。
- **关键依赖（链接行）**: V8 `--start-group -lv8_monolith -labsl -lchrome_zlib -lcompression_utils_portable`；Skia `-DSK_GL -DSK_BUILD_FOR_UNIX -I$(PORTLIBS)/include/skia` + `-lskia-gl -lskcms-gl -lskshaper-gl -lskunicode_core-gl -lskunicode_libgrapheme-gl`；GL `-lEGL -lGLESv2 -lglapi -ldrm_nouveau`；FFmpeg `-lavformat -lavcodec -lswscale -lswresample -lavutil -ldav1d`；`-lmbedtls -lmbedx509 -lmbedcrypto`；freetype/harfbuzz/turbojpeg/webp/jpeg/png/bz2/z/lzstd/libnx。**无 SDL、无 GLFW**（libnx + EGL/GLES 直连）。
- **README 声称**: 即 nx.js README（fork 继承）：由 V8 驱动（"the same engine that powers Chrome and Node.js"）；支持 setTimeout/fetch/new URL/Canvas/WebGL2/Web Audio/Web Bluetooth/WASM；Canvas 由 Skia GPU 加速；WebGL2 是真实 OpenGL ES 3 context；Audio/Video 走 FFmpeg；从源码构建需 devkitPro + 自定义包（docker pull ghcr.io/tootallnate/pacman-packages:nxjs），需 Node 22、pnpm、jq 与 `./build.sh`。

#### 2.1 运行时架构与版本（Brewser 的引擎侧）

- V8 迁移已完成：QuickJS → V8；`MIGRATION_PLAN.md` 的 north star 是 "Stop carrying a 750KB QuickJS-era fork of nx.js. Reduce nxjs-source to a THIN extension patch on top of upstream V8 nx.js: a small native GL/EGL bridge + a few main.cc init lines."
- 版本：V8 = `switch-v8 15.0.243-9`（upstream V8 tag 15.0.243）；Skia = `switch-skia 149-3`（pin 原因见 1.1）；GL = Mesa Nouveau（NV120，GLES 3.2）；其余见上（FFmpeg/mbedTLS/libuv/ada/dav1d）。
- 后端共存方案（已 Go）：single shared ES3 context；`gl_state_save` → WebGL → `restore` → `GrDirectContext::resetContext()`；overlays 用 `SkImages::BorrowTextureFrom`；实测 0.71% of 60Hz budget over 4,013 frames（Citron）。
- 关键修复与坑：`SetStackLimit`（V8 auto-detect StackGuard 假定 desktop stack，Switch 1 MiB libnx 主线程栈不会抛 catchable RangeError → 改为从 `threadGetSelf()->stack_mem` + 256 KiB headroom 推导）；WebGL null stub；ICU 缺失的 emoji 正则；Citron 的 phantom JIT faults（Defect A Sparkplug-OSR transition、Defect B JIT-frame stack overflow）真机不复现 → "Citron is NOT authoritative for JIT payloads; hardware is source of truth"；single-NRO auto-detect（2-of-3 信号判 Citron：hbloader env-block absent、`svcGetInfo(CoreMask)&0x8` 未强制 core-3、`splGetConfig(HardwareType)` 失败），Citron 强制 `--jitless`、hardware 全 JIT；override 优先级 `[v8] jit` > `[v8] target` > auto，SD override 文件 `sdmc:/switch/nxjs-override.ini`。
- 分支拓扑（MIGRATION_PLAN 原文）：`nxjs-source @ nxjs-extended` = QuickJS 参考（只读）；`nxjs-extended @ v8-migration`（from upstream v1.0.0-beta.5）= 原生工作；`brewser-runtime-v8 @ v8-migration`（TS shell + WebGL 语义）；`brewser @ main` 通过 Makefile overlay 消费 built NRO。**后两者为私有分支/仓库。**

#### 2.2 依赖获取方式

- 必须自建（或从 GHCR 拉预编译包）：devkitPro + Docker 拉 `ghcr.io/tootallnate/pacman-packages:nxjs`，`dkp-pacman -U` 安装 switch-v8/switch-skia/switch-libuv/switch-ada/switch-dav1d —— 官方 devkitPro registry 没有这些包；V8/Skia 本身不在此仓源码编译。
- 若只要运行时（不重建引擎）：上游 npm `@nx.js/nro` / `@nx.js/runtime` 提供预编译 runtime（npm 2026-10-29 实测：`@nx.js/nro` latest `1.0.0-beta.7`，unpacked 56,757,054 B、6 files、published 2026-10-13T06:40:50Z，带 SLSA provenance；`@nx.js/runtime` latest `1.0.0-beta.7`，335,926 B、3 files）；但 **`@switch-web/runtime` npm 404**，Brewser shell 所需 runtime 包不在公网。
- 预编译 NRO：上游 nx.js release `beta.7` 提供 `nxjs.nro` 56,436,901 B（可作运行时底座）；Brewser release 提供 76,546,123 B `brewser.nro`（含 shell+engine）。

#### 2.3 许可证与再分发义务

- 本仓 MIT（LICENSE 1,071 B）；上游 nx.js MIT；fork 新增文件同样以 MIT 分发。
- 但构建产物链接的第三方组件（V8、Skia、Mesa/Nouveau、FFmpeg、mbedTLS、libuv、dav1d、ada、freetype、harfbuzz、libpng/jpeg-turbo/webp/zlib/zstd/brotli）各自许可证不同；本仓未集中登记 NOTICE，发布含引擎的 NRO/NSP 前须逐项核对（与 BurialNX NOTICE 的警告同类）。FFmpeg 具体许可取决于编译开关（LGPL/GPL），本次未验证。
- Brewser 发布包还依赖其自有 keyring 签名更新源；再分发 shell 时 MPL-2.0 义务适用于 shell 文件。

#### 2.4 DOM/Canvas/WebGL/WebAudio/localStorage-IndexedDB/fs API 覆盖

- 引擎层提供：Canvas（Skia）、WebGL2（真实 GLES 3 context；upstream 无 WebGL1/扩展，fork 补）、Web Audio graph、HTMLAudio/Video + FFmpeg、fetch、Web Bluetooth、WASM（JIT 下）、timers。
- **引擎层没有 DOM/CSS/HTML**：DOM/CSS/layout 是 Brewser shell 在其上自研（见 1.4 覆盖表）；nx.js 本身只是 JS 运行时，不含浏览器。localStorage/IndexedDB 属 Brewser runtime/shell 层，非 upstream nx.js 原生 API。
- fs：nx.js 提供原生 fs 模块（`source/fs.cc`），但 Brewser 页面不暴露 Node `require`/fs（页面是浏览器语义）；两者不可混淆。

#### 2.5 应用打包与启动方式

- 引擎自身不负责 app 打包；打包模型由 Brewser 决定（app 目录 + index.html + 可选 manifest；`@nx.js/nro --fat` 把 runtime 嵌入 NRO、`@nx.js/nsp` 生成 forwarder NSP）。
- 启动：NRO（nxjs 或 brewser）→ V8 初始化 → 嵌入的 `runtime.js` → app JS context（Brewser 每次 launch 新建 context）。V8 heap/stack 参数有单独 handoff 文档（`V8-HEAP-SIZING-HANDOFF.md`）。
- 存档：由上层（Brewser storage / BurialNX saves）决定，nx.js 不强制路径。

#### 2.6 输入

- 引擎层 `source/gamepad.cc`、`software-keyboard.cc` 提供原生手柄与软键盘；映射到 Web Gamepad/Keyboard 语义由 runtime JS 层完成；Brewser 的 16 键 Standard mapping 见 1.6。

#### 2.7 真机证据与未验证项

- 项目文档 `docs/HW_SESSION_RUNBOOK.md`：2026-07-03 真机 session（Tegra X1、Nouveau NV120、CFW hbmenu）；`#56 getBufferSubData 硬件返回 0` 于 2026-07-04 CLOSED；MIGRATION_PLAN Step1 hardware GO、Step1 brewser.nro 66,763,898 B（V8+Skia+libuv embedded via --fat）。
- 未验证：本次未构建、未真机运行；分支无 tag，无法用 tag 锁定；`brewser-v8`/`brewser-runtime-v8` 私有，无法审计 shell 与 engine 的接口契约；`switch-v8`/`switch-skia` 的 GHCR 包内容与许可证清单未逐项核对。
- 来源 URLs: https://github.com/natureglass/nx.js_extended ；https://github.com/natureglass/nx.js_extended/tree/nxjs-extended ；https://github.com/natureglass/nx.js_extended/commit/90fbed8b7bb2f442b38521878a2aa315080bce1a ；https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/Makefile ；https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/MIGRATION_PLAN.md ；https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/NXJS_PATCHES_NEEDED.md ；https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/docs/HW_SESSION_RUNBOOK.md ；https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/README.md ；https://www.npmjs.com/package/@nx.js/nro

### 3. ETCHDEV/BurialNX

- **URL**: https://github.com/ETCHDEV/BurialNX ｜ **默认分支**: `main`
- **HEAD**: `c2c6691c0c73a2fbefadadd2bde8ecbe7d3f013b`，提交日期 2026-10-19（2026-10-19T11:07:40Z，msg 为 v0.1.1 release 提交）
- **最近 tag**: `v0.1.1` → `c2c6691c0c73a2fbefadadd2bde8ecbe7d3f013b`（=HEAD，日期 2026-10-19）；前序 `v0.1.0` → `878a6d4b48e61c0d96c4ed5861b1bb25c949297b`。release：`v0.1.1` published 2026-10-19T11:09:34Z，**prerelease=true**，assets `burialnx.nro` 56,512,253 B（13 dl）、`burialnx-debug.nro` 56,512,157 B（4 dl）；`v0.1.0` published 2026-10-18T12:51:35Z，prerelease=true，nro 56,492,606 B。
- **许可证**: SPDX `AGPL-3.0-or-later`；许可证文件 `LICENSE`（34,523 B，AGPLv3 全文）；`NOTICE.md` 明确写 "AGPL-3.0-or-later"。随附的 nx.js runtime 为 MIT（`LICENSES/nx.js-MIT.txt`）；NOTICE 还提醒：fat NRO 内包含预编译 nx.js runtime 及其 bundled components，发布二进制前需核对该 runtime 的第三方许可/源码/notice 义务；本地 artwork 来源不明不得发布；并含 Section 1201 法律风险提示。GitHub API license 显示 `AGPL-3.0`。
- **健康**: archived=false；最后 push 2026-10-19T11:09:33Z；open issues=2；stars=2；forks=1；size 109 KB；语言 TypeScript；创建于 2026-10-18（极新项目）。
- **构建系统**: Node.js 22+、`npm ci`/`npm test`/`npm run build`；**无需 devkitPro**（`@nx.js/nro` 1.0.0-beta.7 提供 prebuilt runtime）；devDeps：`@nx.js/nro 1.0.0-beta.7`、`esbuild 0.25.12`、`jpeg-js 0.4.4`、`pngjs 7.0.0`。产物 `burialnx.nro` / `burialnx-debug.nro`（fat package，二者同 application ID `01a144e6a07a0000`）；icon 由 jpg/png 转 256×256 JPEG（≤16MiB/16MP）；无 icon 时用 nx.js 占位。desktop smoke：`BURIALNX_GAME_ROOT=.../www npm run smoke`。构建控制台：`tools/{build,icon,smoke,test}.mjs`。维护者声明 Windows/Linux build 未经其验证，macOS packaging + JS tests 已跑。
- **README 声称**: "An optimized Nintendo Switch homebrew runtime environment for **TCOAAL**, built around nx.js and a targeted RPG Maker MV compatibility host"。加载用户独立提供的 game deployment（不是反编译/重制）；原桌面版用 NW.js，BurialNX 改用 nx.js（不用 Switch WebApplet）；受 `Kidev-org/TCOAALBrowserLoader`（AGPL）影响、非 clean-room；OpenAI Codex 协助开发；16 MiB 有界缓存、map prefetch、canvas 复用；从用户选择的 SD 目录解析游戏与 Hash 资源，可选 unpacked mod overlay；存档三选（Switch user save data / 独立 SD 目录 / game-folder `save/` 或 `www/save/`）；输入映射、fit/native 显示、长按 Minus 菜单（load screen、显示模式、FPS、存档位置、Steam 导入、mod）与 FPS 显示；debug build 诊断快照；安装 `sdmc:/switch/burialnx/`；settings `sdmc:/switch/burialnx/settings.json`；debug 日志 `sdmc:/switch/burialnx/LOGS/` 与 `sdmc:/switch/nxjs-debug.log`；Credits 场景会 hang/crash 已禁用入口。
- **未验证 / 风险**: 极新（2026-10-18 创建）、2★、单作者、release 均标 prerelease；**专用运行时**（见 3.1），对其它 MV 作品不保证；Windows/Linux 构建未验证；fat NRO 内第三方组件许可未逐项核对；依赖预编译 nx.js runtime（beta.7）；AGPL 传染（见 3.3）。

#### 3.1 「针对特定 RPG Maker MV 游戏的专用运行时」原文证据

README IMPORTANT 段原文（2026-10-19 版）："BurialNX is a specialized loader, not a universal RPG Maker MV player. Its runtime behavior and compatibility code are tailored to TCOAAL's specific memory demands, asset layout, and plugin footprint. Other RPG Maker MV deployments are not supported, and compatibility with every version or mod of TCOAAL is not guaranteed."
`AGENTS.md` 也要求：禁止把游戏资产入库、禁止保存档、勿宣称通用兼容、披露 Codex 使用。`WORKING.md` 补充："The NRO contains only the nx.js runtime plus the BurialNX loader. The loader provides the limited browser-like API that RPG Maker MV expects ... it is not a full browser or a universal RPG Maker MV player."

#### 3.2 可借鉴的输入/存档/诊断实现（对照 GalNX M4）

- **输入**：`game-compat.ts` 把 Switch 按键映射到 RPG Maker input；`browser-host.ts` 提供小型 `document`/`canvas`/`image`/local request/`script` 接口；SMOKE 测试模拟帧走到 new-game map。
- **存档**：`saves.ts` / `save-slots.ts`；三选存档后端（Switch user save data / 独立 SD 目录 / game folder `save/` 或 `www/save/`）；保持本地 save key 兼容；读游戏语言表/字体；`localStorage` 兼容层。
- **诊断**：`runtime-plan.ts` 选择游戏正常 load handler（缺失时起 boot scene）；`map-prefetch.ts` 扫当前 map transfer events 预热最多 3 个目标 map（16 MiB cache、单项 2 MiB）；debug build 快照、`LOGS/native-host.log`、`nxjs-debug-<ts>.log`、`sdmc:/switch/nxjs-debug.log`；长按 Minus 菜单显示 FPS/load screen/显示模式/存档位置。
- **资源访问**：`game-assets.ts` 读可选 mod overlay、解析编码资源、共享并发 image/data 读、有界缓存且不写游戏目录；`browser-host.ts` 的 resource fetch bridge 拒绝 external/native filesystem URL（注意：文档说明这不是 sandbox）。
- **兼容补丁清单**（`game-compat.ts` / WORKING.md，均标 experimental）：跳过 desktop audio streaming plugin 改用 RPG Maker 音频路径；从 region plugin 移除 Node-specific payload 保留 collision rules；禁用 Credits；hashed-path lookup；audio panning/async decode 适配；text/intro 定位微调。
- 注意：以上为**针对单一作品的专用适配**，不可直接当通用 MV 层复用；但其文件组织（host/compat/plan/assets/saves/diagnostics 分离）可作 GalNX 适配器结构参考。

#### 3.3 许可证

- 项目：AGPL-3.0-or-later（LICENSE 全文 + NOTICE）；**AGPL 强 copyleft**：分发修改版本必须提供完整对应源码（含通过 NRO 分发）；若 GalNX 复制其代码，GalNX 相关部分须整体 AGPL 化。仅阅读设计思路、独立实现不受此约束（但需注意其 NOTICE 所述非 clean-room 与第三方代码来源）。
- 内含 nx.js MIT runtime（LICENSES/nx.js-MIT.txt）；发布 fat NRO 时 MIT notice 必须保留，且 nx.js 内部 bundled 组件的许可需逐项核对（NOTICE 明确警告）。
- 存档兼容注意：其 Y=旧 loader 共享存档键、Steam 导入等实现与 TCOAAL 专属，不能作为通用格式承诺。

### 4. TooTallNate/nx.js（上游）

- **URL**: https://github.com/TooTallNate/nx.js ｜ **默认分支**: `main` ｜ homepage https://nxjs.n8.io
- **HEAD**: `a649611a1a4daca09924cd1a436c7ca786f91592`，提交日期 2026-10-13（2026-10-13T06:35:05Z，msg "Version Packages (beta) (#427)"，作者 github-actions[bot]）
- **最近 tag**: `v1.0.0-beta.7` → `a649611a1a4daca09924cd1a436c7ca786f91592`（=HEAD，commit 日期 2026-10-13）；前序 `v1.0.0-beta.6` → `f41fb5506a2da21337d6c9b41f14c69ae2e1418f`（2026-07-08）、`beta.5` → `34d2d03…`、`beta.4` → `273927a…`、`beta.3` → `54f2a85…`、`beta.2` → `453c64c…`、`beta.1` → `dc90244…`、`beta.0` → `a2f8552…`、`v0.0.70` → `7f3547f…`（共 77 tags）。releases：beta.7 pub 2026-10-13T06:39:45Z，`nxjs.nro` 56,436,901 B（147 dl）；beta.6 pub 2026-07-08T17:24:21Z，56,436,309 B（636 dl）；beta.5 pub 2026-06-27，56,431,285 B（104 dl）；v0.0.70 pub 2026-05-06，7,962,553 B。
- **许可证**: SPDX `MIT`；`LICENSE`（Copyright (c) 2023 Nathan Rajlich）。
- **健康**: archived=false；最后 push 2026-10-13T06:39:44Z；open issues=12；stars=269；forks=20；size 21,161 KB；语言 TypeScript；创建 2023-05-08；描述 "JavaScript runtime for Nintendo Switch homebrew applications"。
- **构建系统**: devkitPro（仅 Linux/macOS/WSL）；Node 22（`curl -sfLS install-node.vercel.app/22 | bash`）、pnpm、jq；`./build.sh`（bundle TS runtime + make 编译 nxjs.nro + 打包 `apps/` 示例）；Makefile 需 `DEVKITPRO`（未设直接 error），`APP_TITLE nx.js`、`APP_TITLEID 016e782e6a730000`、`APP_VERSION` 读 `packages/runtime/package.json`；架构 cflags `-march=armv8-a+crc+crypto -mtune=cortex-a57`；链接 V8 monolith、Skia Ganesh GL（`skia-horizon-port.o` + `-lskia-gl -lskcms-gl -lskshaper-gl -lskunicode_*`）、`-lEGL -lGLESv2 -lglapi -ldrm_nouveau`、FFmpeg + dav1d、mbedTLS、libuv（pkg-config）；注释 "Cairo and pixman are fully removed in Phase 2.1 (Skia is the sole rendering backend)"。
- **关键依赖**: devkitPro 包 switch-dev/switch-freetype/switch-libjpeg-turbo/switch-libpng/switch-harfbuzz/switch-libwebp/switch-libzstd/switch-mbedtls/switch-ffmpeg；**自定义包** switch-v8、switch-skia、switch-libuv、switch-ada、switch-dav1d 经 `docker pull ghcr.io/tootallnate/pacman-packages:nxjs` + `dkp-pacman -U`；runtime TS 包依赖 `@xmldom/xmldom ^0.9.10`（devDep geist ^1.7.0，字体提取进 romfs）；根 package.json pnpm 10.30.3、typescript 5.6.3。
- **README 声称**: "JavaScript runtime for Nintendo Switch homebrew applications"，由 V8 驱动（同 Chrome/Node.js 引擎）；web standards APIs：setTimeout/fetch/new URL/Canvas/WebGL2/Web Audio/Web Bluetooth/WASM；Features：Input（buttons/touch/motion）、Canvas（Skia GPU）、WebGL2（真实 OpenGL ES 3 context）、Audio & Video elements + full Web Audio（FFmpeg）、Web Bluetooth GATT、WASM。**注意：这不是浏览器，无 DOM/CSS/HTML 管线**。
- **未验证 / 风险**: beta 阶段；自定义 docker 包只有 GHCR 单一来源（非官方 devkitPro），构建可复现性依赖该 tag；无 ICU（emoji/unicode 属性正则风险）；`--jitless` 下无 WASM；release 未附源码 tarball 之外的构建 provenance（本次未核 asset digest）；Mesa Nouveau 的 GL 限制会传递到上层（sampler3D/2DArray/Cube、extension 覆盖）。
- 来源 URLs: https://github.com/TooTallNate/nx.js ；https://api.github.com/repos/TooTallNate/nx.js ；https://github.com/TooTallNate/nx.js/releases/tag/v1.0.0-beta.7 ；https://github.com/TooTallNate/nx.js/blob/main/README.md ；https://github.com/TooTallNate/nx.js/blob/main/Makefile ；https://github.com/TooTallNate/nx.js/blob/main/build.sh

### 5. rexglue/rexglue-sdk（§7.7 旁支登记，不深入）

- **URL**: https://github.com/rexglue/rexglue-sdk ｜ **默认分支**: `main` ｜ HEAD `c94f5ebdcb3c9d1a460ca48e04f9758448f8d518`（2026-08-21T22:11:28Z）
- **最近 tag**: `v0.10.0` → `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2`（commit 日期 2026-08-21T22:10:13Z；共 34 tags）
- **许可证**: `LICENSE`（1,659 B）原文为 Copyright (c) 2026 Tom Clay + "Portions of this software are derived from the Xenia project" + 标准 3 条款 BSD（含 Neither the name… 条款）→ **BSD-3-Clause**；GitHub `/license` API 返回 `NOASSERTION`（因附加声明），以 LICENSE 原文判断为准。
- **健康**: archived=false；last push 2026-10-02T12:11:33Z；open 114；stars 1200；forks 245；size 28,694 KB；语言 C；描述 "Xbox 360 Recompilation Runtime and Toolkit"。
- **一句话**: "ReXGlue converts Xbox 360 PowerPC code into portable C++ that runs natively on modern platforms."（README 另有 early development CAUTION）。构建：CMake + CMakePresets（CI：build-win-amd64 / build-linux-amd64 / build-linux-aarch64 + nightly）。
- **结论**: 与 Galgame/Web 路线无关，仅 §7.7 旁支；第一阶段不引入。

### 6. hedge-dev/XenonRecomp（§7.7 旁支登记，不深入）

- **URL**: https://github.com/hedge-dev/XenonRecomp ｜ 默认分支 `main` ｜ HEAD `ddd128bcca99fe8bfbb99bea583c972351fa6ace`（2025-08-04T13:56:26Z）｜ **最近 tag: none**（tags API 返回空数组）｜ license `MIT`，`LICENSE.md`（Copyright (c) 2025 hedge-dev and contributors）。
- **健康**: archived=false；last push 2025-08-04T13:56:30Z（约 14 个月未更新）；open 94；stars 6640；size 9,399 KB。
- **一句话**: "XenonRecomp is a tool that converts Xbox 360 executables into C++ code, which can then be recompiled for any platform."，且 "does not provide a runtime implementation... Making the game work is your responsibility."；构建需 CMake ≥3.20 + Clang ≥18（submodules 递归）。
- **结论**: Xbox 360 专用、无 tag、无运行时；不列入第一阶段依赖。

### 7. hedge-dev/XenosRecomp（§7.7 旁支登记，不深入）

- **URL**: https://github.com/hedge-dev/XenosRecomp ｜ 默认分支 `main` ｜ HEAD `990d03b28a27b50277ee5d8d942e1c5f873869d1`（2025-08-03T13:45:31Z）｜ **最近 tag: none** ｜ license `MIT`，`LICENSE.md`（Copyright (c) 2025 hedge-dev and contributors）。
- **健康**: archived=false；last push 2026-03-12T17:36:37Z；open 10；stars 505；size 53 KB。
- **一句话**: "XenosRecomp is a tool that converts Xbox 360 shader binaries to HLSL"，产物经 DXC recompile 到 DXIL/SPIR-V（D3D12/Vulkan），围绕 Unleashed Recompiled；"Do not expect the recompiler to work out of the box."；构建需 CMake 3.20 + C++17（Clang tested，submodules 递归）。
- **结论**: Xbox 360 着色器专用；不列入第一阶段依赖。

## 附加 A：TyranoScript / 普通 HTML5 / RPG Maker MV 的 Web 路线 API 差距分析

分析基于：① Brewser/nx.js 的官方能力表与源码；② BurialNX 的兼容层实现（对 MV 需求的一手证据）；③ TyranoScript 公开仓库元数据（`ShikemokuMK/tyranoscript`，master，538★，2026-03-19 push，license NOASSERTION，描述 "novel game engine for Browser, iOS, Android, etc"）。**不针对任何具体商业游戏下结论**；逐游戏差异（发行 wrapper、插件、媒体格式）必须另行核验。

### A.1 三类目标在 Web 运行时侧的 API 需求与 Brewser 差距

| 能力 | 普通 HTML5（Canvas/WebGL 小游戏） | TyranoScript（典型） | RPG Maker MV（典型） | Brewser 现状 |
|---|---|---|---|---|
| DOM/CSS/layout | 少量（canvas、img、div、按钮） | 需要较完整 DOM/CSS（jQuery 驱动 UI、文字层、菜单、CSS 动画/过渡/transform） | 需要 DOM（canvas、input、部分 UI），并依赖浏览器事件模型 | DOM ~84%、CSS ~84%、HTML ~80%；无真正 DOM 完整性 |
| Canvas 2D | 核心 | 核心（文字/立绘/画面分层） | 核心（Pixi.js 前的画布/文字层） | Skia 支持 |
| WebGL | 可选（Pixi/Phaser/Three） | 一般不用 | JS 核心渲染走 Pixi（WebGL/Canvas 回退） | WebGL1 ~92%/WebGL2 ~85%，extension 覆盖不足 |
| Web Audio / 音频 | 常用 | 必需（BGM/语音/音效；常配合 HTML5 Audio） | 必需（AudioManager：WebAudio + HTML5 Audio 混合） | graph ~70%，缺 filter/convolver/delay/compressor |
| fetch/XHR | 常用 | 必需（加载 .ks 剧本、图片、音频） | 必需（加载 data/*.json、img、audio） | 支持，但受 allowed_origins 约束（本地 app 无外部 origin 时须注意） |
| localStorage | 常用 | 存档常用（也存在文件存档变体） | 存档核心（StorageManager 默认 localStorage，NW.js 下另有 fs 存档） | 支持且持久；全局命名空间需前缀 |
| IndexedDB | 少见 | 少见 | 少见于核心，插件可能用 | 支持 core API（无 cursors/indexes） |
| Node API（require/fs/path） | 不需要 | 不需要（浏览器引擎）；若发行 wrapper 为 NW.js/Electron 则可能被引擎/插件使用 | **需要**：MV 桌面发行基于 NW.js，`Utils.isNwjs()`、`require('fs')`（StorageManager/Decrypter/插件）普遍存在 | **无 Node API、无 fs**（页面语义）；需专有兼容层 |
| 输入 | 键盘/鼠标/触摸/手柄 | 鼠标/触摸/键盘（少量手柄） | 键盘/鼠标/触摸（MV 原生无手柄；需 shim） | Gamepad + touch + 软键盘；无物理键盘、鼠标为 software cursor |
| 视频/全屏 | 可选 | 部分作品有 OP/视频 | 部分插件有视频 | video ~85%、codec 有限；fullscreen 由 manifest 控制 |

### A.2 结论（逐类）

- **普通 HTML5**：与 Brewser 能力最匹配，PixiJS v8 / Phaser / Three.js 已被官方 release notes 声称在真机跑通；主要风险是 WebGL extension/3D 纹理限制、CSS 3D/新特性缺失、Unity WebGL2 导出不支持。若目标游戏是纯浏览器原生，Web 路线可直接用 Brewser 承载体，**无需移植代码**（但仍需解决内容授权与离线分发）。
- **TyranoScript**：典型引擎是纯浏览器实现（HTML5/JS），理论上是 Web 路线最有机会的一类；但需要逐游戏核验：发行 wrapper 是否 NW.js/Electron、是否使用 Node/插件 API、CSS/字体/视频/音频格式、存档是 localStorage 还是文件。Brewser 提供 localStorage/Canvas2D/WebAudio/fetch 基础，但 DOM/CSS 覆盖 ~84% 与 WebAudio effect 缺口可能命中其 UI/音频实现；`file://` 假设需要改写为 app 内相对路径。**未在本次审计中取得任何 TyranoScript 样本运行证据**（禁止读取商业数据），因此按「需逐游戏 PoC」处理。
- **RPG Maker MV**：桌面发行基于 NW.js（Chromium + Node），游戏脚本普遍调用 Node API（存档文件、资源路径、插件），并依赖 Chromium 的完整 DOM/Canvas/WebGL/WebAudio。Brewser **没有 Node API/fs**，也不是完整 Chromium，因此 MV 作品不能直接当 Brewser app 跑；BurialNX 的一手证据表明必须提供：小型 document/canvas/image/request/script 兼容层 + Node 特定插件 shim + 音频路径适配 + hashed path/存档键兼容 + 手柄映射。这正是 BurialNX `browser-host.ts` + `game-compat.ts` 所做的事，也说明 MV 适配是「每个作品一份兼容层」而非通用能力。**结论：MV 不应当作 Brewser/nx.js 的通用能力承诺；只能作为专用适配参考（与 §7.3 判断一致）。**

## 附加 B：M4 前置风险清单

| # | 风险 | 证据 | 影响 | 缓解 |
|---|---|---|---|---|
| B1 | 构建链重量：自建 engine 需 devkitPro + Docker + 自定义 GHCR 包（switch-v8 15.0.243-9、switch-skia 149-3、libuv、ada、dav1d）+ Node22/pnpm/jq；jitless 下无 WASM | nx.js README、nx.js_extended Makefile/MIGRATION_PLAN | 若必须从源码重建，M4 成本高且可复现性依赖第三方 GHCR tag | 先走预编译 release（brewser.nro / nxjs.nro），把自建 engine 列为非阻塞 |
| B2 | 离线部署：Brewser 需要先装 `sd:/switch/brewser.nro`，app 通过 catalogue 下载或 sideload；storage 无 per-app 沙箱 | docs publishing/quickstart、runtime/storage | 每游戏分发需 app id 命名空间、避免 storage 冲突；无网络时依赖 cached catalogue | sideload 目录 `sdmc:/switch/brewser/apps/<id>/` 可完全离线；GalNX 侧统一为每个游戏分配 reverse-domain id 前缀 |
| B3 | 许可证：Brewser shell MPL-2.0（文件级 copyleft）；engine nx.js MIT；fat NRO 内含 V8/Skia/FFmpeg 等未集中登记的第三方组件；BurialNX AGPL-3.0-or-later 强 copyleft | 各仓 LICENSE/NOTICE | 直接改 Brewser shell 需公开修改文件；复用 BurialNX 代码会传染 AGPL；再分发 NRO 需带全第三方 notice | 优先把 Brewser 当外部运行时（不改其源码）；只借鉴 BurialNX 设计不复制代码；发布前做许可清单 |
| B4 | API 缺口：DOM ~84%/HTML ~80%/CSS ~84%、WebAudio graph ~70%、WebGL2 ~85%；Unity WebGL2 不支持；无 sessionStorage/Cache API；video codec 有限 | docs/engine-status、support/limitations | 商业 Galgame UI/音频/视频可能踩缺口 | M4 用真实目标做 PoC 前先跑引擎状态页对照；准备 Canvas2D/DOM 降级方案 |
| B5 | MV 需要 Node API：Brewser 页面无 `require`/`fs`；MV 存档/资源/插件普遍依赖 NW.js Node | BurialNX WORKING.md/game-compat.ts | MV 无法直接跑；每作品需专用兼容层 | 只把 MV 当「专用适配」研究，不作为 Web 通用路线承诺 |
| B6 | 真机验证缺失：本次只读，无 CFW 硬件/未跑模拟器；所有「真机可用」均为项目方声明 | release notes / HW_SESSION_RUNBOOK | M4 里程碑不能引用为已验证 | M4 验收前必须在真机跑一次 release（brewser.nro 有公开预编译二进制，风险可控） |
| B7 | 版本锁定：Brewser tag 日期异常（tag commit 2026-09-17 晚于 release 2026-09-15）；`nxjs-extended` 分支无 tag；私有 `@switch-web/runtime`/`brewser-runtime-v8` 不可审计 | releases、branches、npm 404 | 只按分支/SHA 锁定，不能按语义版本假设 | 锁定 `brewser.nro` sha256 `8ce31f5b…` + `nx.js_extended@90fbed8b…`；记录 engine 包版本 15.0.243-9/149-3 |
| B8 | 维护风险：Brewser 单人/小团队（15★）、BurialNX 极新（2★）、nx.js beta 期；上游 nx.js 10-13 才发 beta.7，fork 落后一个 beta | 元数据 | 依赖上游节奏，接口可能破坏 | GalNX 适配层不直接依赖内部 API；只依赖 web 标准接口 + manifest/存储 |

## 未验证 / 失败项

- **未在真机或模拟器上运行任何 release**（本审计只读；真机证据全部引用项目方声明）。
- **未执行任何构建/编译**（任务禁止）；未验证 `make`/`build.sh` 是否可在当前 Windows 环境跑通。
- `@switch-web/runtime` 源码不可得：npm `@switch-web/runtime` 404；GitHub `natureglass/brewser-runtime`、`natureglass/switch-webapp-player` 均 404（私有或不存在）；Brewser 仓 `.gitignore` 忽略 `runtime/`，`sync-runtime.mjs` 从 sibling `../brewser-runtime/dist` 复制 → Brewser shell 与 runtime 的接口契约、构建可复现性无法完整审计。
- Brewser 发布 NRO 内嵌 V8/Skia 的实际版本未直接验证（只能由 nx.js_extended 分支构建脚本/MIGRATION_PLAN 推断为 switch-v8 15.0.243-9、switch-skia 149-3）；`versions.json` 写 nx.js 1.0.0-beta.5，与 fork 分支 HEAD 时间线的关系未核。
- Brewser release 日期早于 tag commit 日期的异常原因未查明（可能 tag 后移/重建）；二进制 digest 与 `dist/checksums.txt` 一致，故发布内容本身可校验。
- `natureglass/nx.js_extended` 的 fork tags 未逐条复抓（默认分支 HEAD = 上游 v1.0.0-beta.6；`nxjs-extended` 分支无 tag）。
- `docs.brewser.io` 部分页面通过 `web_fetch` 抓取时返回 404/500，改用 `curl` 代理抓 HTML 后剥标签阅读；页面内容为官方声明，未独立验证。
- 未认证 `curl api.github.com` 已触发 403 rate limit（本会话较早时发生），后续所有 API 读取改用 `web_fetch`/`cred_use`；未再出现取数失败。
- TyranoScript/普通 HTML5/RPG Maker MV 的桌面发行 wrapper 与具体 API 依赖需逐游戏核验；本次未取得任何具体游戏样本（遵守禁止读取/外传商业游戏数据的约束），差距分析属类型级推断。
- 旁支三仓仅取 README 一句话与元数据，未审计源码（按任务要求不深入）。
- 未核 nx.js beta.7 release asset 的 sha256 digest（仅取 size/downloads）。

## 对 GalNX 的建议

### 版本锁定（M4 若启动）

| 组件 | 建议锁定 | 校验方式 |
|---|---|---|
| Brewser 运行时 | release `v0.1.1.31`（名 v0.1.131）的 `brewser.nro`，sha256 `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13` | 与 `dist/checksums.txt` 比对；不要按 tag 日期推断顺序 |
| engine 源码参考 | `natureglass/nx.js_extended@90fbed8b7bb2f442b38521878a2aa315080bce1a`（分支，无 tag） | 记录 SHA；升级需重验 |
| V8 / Skia | `switch-v8 15.0.243-9` + `switch-skia 149-3`（MIGRATION_PLAN 明确 Skia 不得随意升） | 若自建 engine，锁 GHCR 包 tag |
| nx.js 上游（若单独使用） | `v1.0.0-beta.7` / `a649611a…`；npm `@nx.js/nro@1.0.0-beta.7` | release asset 与 npm provenance |
| BurialNX | `v0.1.1` / `c2c6691c…`，**仅参考不引入代码** | AGPL |

### 接入顺序（建议）

1. **M4-PoC-1**：用公开 `brewser.nro` 预编译二进制在真实 CFW 硬件（或至少 Citron）跑一个官方演示 app（Canvas/WebGL demo），验证安装路径 `sd:/switch/brewser.nro`、hbmenu application mode、离线 catalogue、storage 持久性 → 证明「Web 运行时可用」但不涉及商业内容。
2. **M4-PoC-2**：sideload 一个**自建的**简单 HTML5 Canvas 游戏目录到 `sdmc:/switch/brewser/apps/<reverse-domain-id>/`，验证入口约定、离线性、手柄/触摸输入、存档（localStorage 前缀）。
3. **M4-PoC-3**：若候选目标确为 TyranoScript/HTML5：先核验其 PC 发行 wrapper 与 API 使用（是否 NW.js/Node、存档方式、媒体格式、CSS/JS 特性），再决定 Brewser 适配 vs 原生移植；每作品单独 PoC。
4. **MV 路线（仅研究）**：以 BurialNX 的 host/compat/plan/assets/saves/diagnostics 分层为架构参考，**独立实现**专用适配层；不复制其代码（AGPL），不作通用承诺。

### 阻塞项（进入 M4 前必须解决）

- 目标游戏的内容授权与再分发许可（不仅技术可用）：Brewser app 发布需上传 bundle 到 brewser.io 管道或离线分发；商业 Galgame 资产禁止入库/外传（本审计约束）。
- 真机验证资源（CFW Switch 或可靠的 Citron 替代，但项目已声明 Citron 不是 JIT 权威）；Brewser 更新源依赖 baked keyring 签名，自建分发不能复用其更新通道。
- `@switch-web/runtime` 私有：若未来要改 shell 或做深度定制，需要向作者获取源码/许可，否则只能黑盒使用官方 release。
- 第三方组件许可清单（V8/Skia/FFmpeg/mbedTLS 等）在发布 NRO 前必须逐项核对并随附 notice（BurialNX NOTICE 已给出同类警告）。

## 附录：审计数据说明

- 全部数字（SHA、日期、stars、issue 数、license SPDX、文件大小、digest）均来自 2026-10-29 当天实际抓取（GitHub API v3 与 raw/HTML 页面）；未引用记忆值。
- 日期一律 UTC，格式 YYYY-MM-DD（commit 日期取 GitHub API ISO 字符串的日期部分）。
- verification_level：全部 7 条均为 `source-inspected`（阅读了仓库源码/脚本/文档）或 `read-only`（仅元数据+README 的旁支）；无任何条目达到硬件实测级。

<!-- AUDIT-JSON-BEGIN -->
```galnx-audit
[
  {
    "name": "natureglass/Brewser",
    "url": "https://github.com/natureglass/Brewser",
    "default_branch": "main",
    "head_sha": "8040580e92e40a60f704a6478ee296b105212f1b",
    "head_date": "2026-09-17",
    "pinned": "v0.1.1.31 / 8040580e92e40a60f704a6478ee296b105212f1b（release 名称 v0.1.131；brewser.nro sha256 8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13）",
    "license_spdx": "MPL-2.0",
    "license_file": "LICENSE",
    "license_notes": "LICENSE 16,726 B 为 MPL-2.0 全文；package.json 的 license 字段写 MIT，与仓库 LICENSE 冲突，以 LICENSE 为准（MPL-2.0 文件级 copyleft）。engine 为 nx.js MIT fork；随附 V8/Skia/FFmpeg/mbedTLS 等第三方组件许可未集中登记，分发 fat NRO 前须逐项核对 notice/源码义务。",
    "archived": false,
    "last_push": "2026-09-17T20:32:54Z",
    "stars": 15,
    "open_issues": 1,
    "build_system": "GNU make（bump+build+package+sign+verify → dist/brewser.nro + update.json）；shell 由 node scripts/build-main.mjs + esbuild 打包；默认构建仅需 node/npm/python、复用预编译 engine NRO（无需 devkitPro）；make -f Makefile_nxjs 重建引擎需 devkitPro(msys2)；无公开 CI workflow。",
    "build_deps": "esbuild 0.27.7(lock)、typescript 5.2.2、css-tree 3.2.1、@switch-web/runtime(link:./runtime，私有不可得)、@nx.js/nro|nsp|runtime(link:../nxjs-extended/packages/*)；重建引擎需 GHCR 包 switch-v8 15.0.243-9、switch-skia 149-3、switch-libuv、switch-ada、switch-dav1d。",
    "readme_claims": "面向 Switch 的完整 Web runtime/app platform（基于 nx.js fork）：V8 JIT+WASM、Skia、Mesa/Nouveau 上的 WebGL 1/2、Three.js/PixiJS/Phaser、720p60 HLS 视频、WebUSB/Web Bluetooth/Web Serial/WebHID/MIDI/NFC/WebNN、WebSockets、Web Audio、Sensor API、权限系统、Offline Mode、on-screen keyboard、catalogue、cloud saves、Google 登录；声明不运行商业 Switch 游戏/ROM。",
    "readme_claim_url": "https://github.com/natureglass/Brewser/blob/main/README.md",
    "risks": "私有 @switch-web/runtime 源码不可得（npm 404、GitHub 404），shell/engine 接口与构建可复现性无法审计；LICENSE(MPL-2.0) 与 package.json(license: MIT) 冲突；tag v0.1.1.31 的 commit 日期(2026-09-17)晚于 release 发布日(2026-09-15)，tag 可能后移；无公开 CI；发布 NRO 内含未集中登记的第三方组件许可义务；DOM/HTML/CSS 覆盖约 80-84%、Web Audio graph ~70%、Unity WebGL2 不支持；真机证据均为项目方声明。",
    "verification_level": "source-inspected",
    "verification_failures": "未真机运行、未构建；@switch-web/runtime 源码不可得；发布 NRO 内嵌 V8/Skia 实际版本未直接验证（推断 switch-v8 15.0.243-9 / switch-skia 149-3）；docs.brewser.io 部分页面 web_fetch 返回 404/500，改用 curl 抓 HTML；未认证 curl api.github.com 曾 403 rate limit。",
    "source_urls": [
      "https://github.com/natureglass/Brewser",
      "https://api.github.com/repos/natureglass/Brewser",
      "https://github.com/natureglass/Brewser/commit/8040580e92e40a60f704a6478ee296b105212f1b",
      "https://github.com/natureglass/Brewser/releases/tag/v0.1.1.31",
      "https://github.com/natureglass/Brewser/blob/main/README.md",
      "https://github.com/natureglass/Brewser/blob/main/Makefile",
      "https://github.com/natureglass/Brewser/blob/main/Makefile_nxjs",
      "https://github.com/natureglass/Brewser/blob/main/package.json",
      "https://github.com/natureglass/Brewser/blob/main/versions.json",
      "https://github.com/natureglass/Brewser/blob/main/dist/checksums.txt",
      "https://github.com/natureglass/Brewser/blob/main/dist/update.json",
      "https://docs.brewser.io/docs/engine-status",
      "https://docs.brewser.io/docs/runtime/architecture",
      "https://docs.brewser.io/docs/runtime/storage",
      "https://docs.brewser.io/docs/runtime/controls",
      "https://docs.brewser.io/docs/publishing/quickstart",
      "https://docs.brewser.io/docs/publishing/manifest"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "natureglass/nx.js_extended",
    "url": "https://github.com/natureglass/nx.js_extended",
    "default_branch": "main",
    "head_sha": "90fbed8b7bb2f442b38521878a2aa315080bce1a",
    "head_date": "2026-09-17",
    "pinned": "审计分支 nxjs-extended@90fbed8b7bb2f442b38521878a2aa315080bce1a（无 tag）；默认分支 main HEAD 为 f41fb5506a2da21337d6c9b41f14c69ae2e1418f（=上游 v1.0.0-beta.6，2026-07-08）；engine 依赖 switch-v8 15.0.243-9 + switch-skia 149-3",
    "license_spdx": "MIT",
    "license_file": "LICENSE",
    "license_notes": "LICENSE 1,071 B，MIT（Copyright (c) 2023 Nathan Rajlich，fork 自 TooTallNate/nx.js）。构建链接的 V8/Skia/Mesa/FFmpeg/mbedTLS/libuv/dav1d/ada/freetype/harfbuzz 等第三方组件许可未在本仓集中登记，分发含引擎的 NRO/NSP 前须逐项核对；FFmpeg 许可取决于编译开关（LGPL/GPL），未验证。",
    "archived": false,
    "last_push": "2026-09-17T21:34:59Z",
    "stars": 1,
    "open_issues": 0,
    "build_system": "devkitPro(devkitA64+libnx) Makefile（TARGET=nxjs、APP_TITLEID=016e782e6a730000、APP_VERSION 由 jq 读 packages/runtime/package.json）；source/ 109 个 C/C++ 文件（main.cc 106,066B、canvas.cc 120,733B、audio-graph.cc、media-decoder.cc、skia_gpu.cc、gamepad.cc 等）；runtime.js 由 tools/embed-runtime.mjs 嵌入；bootstrap/ + bootstrap-artifact/ 安装自定义包；build.sh；Node 22 + pnpm 10.30.3 + jq + Docker。",
    "build_deps": "switch-v8 15.0.243-9、switch-skia 149-3（GHCR ghcr.io/tootallnate/pacman-packages:nxjs）、switch-libuv、switch-ada、switch-dav1d；官方包 switch-dev/freetype/harfbuzz/turbojpeg/webp/png/zstd/mbedtls/ffmpeg；链接 -lv8_monolith -labsl -lchrome_zlib -lcompression_utils_portable、-lskia-gl -lskcms-gl -lskshaper-gl -lskunicode_*、-lEGL -lGLESv2 -lglapi -ldrm_nouveau、ffmpeg+dav1d、-lmbedtls、libuv；无 SDL/GLFW；vendored google/brotli 1.2.0。",
    "readme_claims": "fork 继承 nx.js README：由 V8 驱动（同 Chrome/Node.js）；支持 setTimeout/fetch/new URL/Canvas/WebGL2/Web Audio/Web Bluetooth/WASM；Canvas 由 Skia GPU 加速、WebGL2 是真实 OpenGL ES 3 context、音视频走 FFmpeg；从源码构建需 devkitPro + 自定义包（docker pull ghcr.io/tootallnate/pacman-packages:nxjs）+ Node 22/pnpm/jq + ./build.sh。",
    "readme_claim_url": "https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/README.md",
    "risks": "fork 落后上游一个 beta（main HEAD=beta.6，上游已 beta.7）；活动分支 nxjs-extended 无 tag，只能按 SHA 锁定；自定义 GHCR 包是唯一来源，构建可复现性依赖该 tag；brewser-runtime-v8 私有，shell/engine 接口契约不可审计；switch-v8 无 ICU、jitless 下无 WASM；Mesa Nouveau 的 sampler3D/2DArray/Cube 与 extension 限制；实验性项目。",
    "verification_level": "source-inspected",
    "verification_failures": "未构建、未真机运行；分支无 tag；fork tags 未逐条复抓（默认分支 main HEAD 对应上游 v1.0.0-beta.6）；GHCR 包内容与许可证清单未核对；私有 brewser-runtime-v8/brewser-v8 不可得。",
    "source_urls": [
      "https://github.com/natureglass/nx.js_extended",
      "https://github.com/natureglass/nx.js_extended/tree/nxjs-extended",
      "https://github.com/natureglass/nx.js_extended/commit/90fbed8b7bb2f442b38521878a2aa315080bce1a",
      "https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/Makefile",
      "https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/MIGRATION_PLAN.md",
      "https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/NXJS_PATCHES_NEEDED.md",
      "https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/docs/HW_SESSION_RUNBOOK.md",
      "https://github.com/natureglass/nx.js_extended/blob/nxjs-extended/README.md",
      "https://www.npmjs.com/package/@nx.js/nro"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "ETCHDEV/BurialNX",
    "url": "https://github.com/ETCHDEV/BurialNX",
    "default_branch": "main",
    "head_sha": "c2c6691c0c73a2fbefadadd2bde8ecbe7d3f013b",
    "head_date": "2026-10-19",
    "pinned": "v0.1.1 / c2c6691c0c73a2fbefadadd2bde8ecbe7d3f013b（release v0.1.1，prerelease=true，2026-10-19）",
    "license_spdx": "AGPL-3.0-or-later",
    "license_file": "LICENSE",
    "license_notes": "LICENSE 34,523 B 为 AGPLv3 全文；NOTICE.md 明确项目许可 AGPL-3.0-or-later。强 copyleft：分发修改版本须提供完整对应源码。内含 nx.js MIT runtime（LICENSES/nx.js-MIT.txt），发布 fat NRO 时须保留 MIT notice 并核对 runtime 内 bundled 组件的第三方许可（NOTICE 明确警告）。",
    "archived": false,
    "last_push": "2026-10-19T11:09:33Z",
    "stars": 2,
    "open_issues": 2,
    "build_system": "Node.js 22+ + npm ci/test/build；无需 devkitPro（@nx.js/nro 1.0.0-beta.7 提供 prebuilt runtime）；devDeps @nx.js/nro 1.0.0-beta.7、esbuild 0.25.12、jpeg-js 0.4.4、pngjs 7.0.0；tools/{build,icon,smoke,test}.mjs；产物 burialnx.nro 与 burialnx-debug.nro（fat，同 application ID 01a144e6a07a0000）；Windows/Linux 构建未经维护者验证。",
    "build_deps": "@nx.js/nro 1.0.0-beta.7（prebuilt nx.js runtime）、esbuild 0.25.12、jpeg-js 0.4.4、pngjs 7.0.0；Node.js 22+。",
    "readme_claims": "An optimized Nintendo Switch homebrew runtime environment for TCOAAL, built around nx.js and a targeted RPG Maker MV compatibility host；专用 loader 而非通用 MV 播放器（原文 IMPORTANT）；加载独立提供的 game deployment（非反编译）；16 MiB 有界缓存、map prefetch、canvas 复用；存档三选（Switch user save data / 独立 SD 目录 / game-folder save）；输入映射、fit/native 显示、长按 Minus 菜单、debug 快照；Credits 场景已禁用。",
    "readme_claim_url": "https://github.com/ETCHDEV/BurialNX/blob/main/README.md",
    "risks": "极新项目（2026-10-18 创建，2★，单作者，release 均标 prerelease）；专用运行时，其他 MV 作品不保证兼容；AGPL-3.0-or-later 强 copyleft（复制其代码会传染）；依赖预编译 nx.js runtime，fat NRO 内第三方组件许可未逐项核对；Windows/Linux 构建未经维护者验证。",
    "verification_level": "source-inspected",
    "verification_failures": "未构建、未真机运行；两个 release 均为 prerelease；未取得游戏样本（禁止读取商业数据），gamplay 可玩性仅项目方声明；未核 fat NRO 内 runtime 的完整第三方许可清单。",
    "source_urls": [
      "https://github.com/ETCHDEV/BurialNX",
      "https://api.github.com/repos/ETCHDEV/BurialNX",
      "https://github.com/ETCHDEV/BurialNX/commit/c2c6691c0c73a2fbefadadd2bde8ecbe7d3f013b",
      "https://github.com/ETCHDEV/BurialNX/releases/tag/v0.1.1",
      "https://github.com/ETCHDEV/BurialNX/blob/main/README.md",
      "https://github.com/ETCHDEV/BurialNX/blob/main/WORKING.md",
      "https://github.com/ETCHDEV/BurialNX/blob/main/Building%20%26%20Debugging.md",
      "https://github.com/ETCHDEV/BurialNX/blob/main/NOTICE.md",
      "https://github.com/ETCHDEV/BurialNX/blob/main/package.json"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "TooTallNate/nx.js",
    "url": "https://github.com/TooTallNate/nx.js",
    "default_branch": "main",
    "head_sha": "a649611a1a4daca09924cd1a436c7ca786f91592",
    "head_date": "2026-10-13",
    "pinned": "v1.0.0-beta.7 / a649611a1a4daca09924cd1a436c7ca786f91592（release 2026-10-13，nxjs.nro 56,436,901 B）；npm @nx.js/nro@1.0.0-beta.7",
    "license_spdx": "MIT",
    "license_file": "LICENSE",
    "license_notes": "MIT（Copyright (c) 2023 Nathan Rajlich）；无 copyleft；分发 NRO 需保留版权与许可声明。链接的 V8/Skia/FFmpeg/mbedTLS 等第三方组件许可未集中登记。",
    "archived": false,
    "last_push": "2026-10-13T06:39:44Z",
    "stars": 269,
    "open_issues": 12,
    "build_system": "devkitPro（仅 Linux/macOS/WSL）+ Node 22 + pnpm + jq；./build.sh（bundle TS runtime + make 编译 nxjs.nro + 打包 apps/ 示例）；Makefile 需 DEVKITPRO，APP_TITLEID 016e782e6a730000；-march=armv8-a+crc+crypto -mtune=cortex-a57；无公开 CI 说明（本次未核 workflows）。",
    "build_deps": "devkitPro switch-dev/freetype/libjpeg-turbo/libpng/harfbuzz/libwebp/libzstd/mbedtls/ffmpeg + 自定义 switch-v8、switch-skia、switch-libuv、switch-ada、switch-dav1d（docker ghcr.io/tootallnate/pacman-packages:nxjs）；runtime TS 依赖 @xmldom/xmldom ^0.9.10；pnpm 10.30.3、typescript 5.6.3。",
    "readme_claims": "JavaScript runtime for Nintendo Switch homebrew applications；由 V8 驱动（同 Chrome/Node.js）；web standards APIs：setTimeout/fetch/new URL/Canvas/WebGL2/Web Audio/Web Bluetooth/WASM；Canvas 由 Skia GPU 加速、WebGL2 为真实 OpenGL ES 3 context、音视频走 FFmpeg；从源码构建需 devkitPro + 自定义包 + Node 22/pnpm/jq。",
    "readme_claim_url": "https://github.com/TooTallNate/nx.js/blob/main/README.md",
    "risks": "beta 阶段；无 DOM/CSS/HTML 管线（不是浏览器，HTML5 游戏需 shell/Brewser 之类补足）；自定义 GHCR 包是唯一构建来源；无 ICU、jitless 下无 WASM；Mesa Nouveau GL 限制向上传递；release asset digest 未核。",
    "verification_level": "source-inspected",
    "verification_failures": "未构建、未真机运行；beta.7 release asset sha256 未取（仅 size/downloads）；未检查 CI workflow 明细。",
    "source_urls": [
      "https://github.com/TooTallNate/nx.js",
      "https://api.github.com/repos/TooTallNate/nx.js",
      "https://github.com/TooTallNate/nx.js/releases/tag/v1.0.0-beta.7",
      "https://github.com/TooTallNate/nx.js/blob/main/README.md",
      "https://github.com/TooTallNate/nx.js/blob/main/Makefile",
      "https://github.com/TooTallNate/nx.js/blob/main/build.sh"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "rexglue/rexglue-sdk",
    "url": "https://github.com/rexglue/rexglue-sdk",
    "default_branch": "main",
    "head_sha": "c94f5ebdcb3c9d1a460ca48e04f9758448f8d518",
    "head_date": "2026-08-21",
    "pinned": "v0.10.0 / f5337cdc947ff6d4c4196737e2c807a48f2a1fc2",
    "license_spdx": "BSD-3-Clause",
    "license_file": "LICENSE",
    "license_notes": "LICENSE 1,659 B：Copyright (c) 2026 Tom Clay，Portions derived from the Xenia project（Copyright (c) 2022 Ben Vanik and Xenia contributors），All rights reserved + 标准 3 条款 BSD，据此判定 BSD-3-Clause；GitHub /license API 返回 NOASSERTION（附加派生声明），以 LICENSE 原文为准。",
    "archived": false,
    "last_push": "2026-10-02T12:11:33Z",
    "stars": 1200,
    "open_issues": 114,
    "build_system": "CMake + CMakePresets（root 有 CMakeLists.txt、CMakePresets.json、cmake/、thirdparty/）；CI：build-win-amd64 / build-linux-amd64 / build-linux-aarch64 + nightly。",
    "build_deps": "C/C++ + CMake（thirdparty/ 子模块）；具体版本依赖本次未深入（旁支登记，不深入）。",
    "readme_claims": "ReXGlue converts Xbox 360 PowerPC code into portable C++ that runs natively on modern platforms；README 含 early development CAUTION 与免责声明。",
    "readme_claim_url": "https://github.com/rexglue/rexglue-sdk#readme",
    "risks": "仅 Xbox 360 PowerPC 重编译，与 Galgame/Web 路线无关；early development；§7.7 旁支，第一阶段不引入。",
    "verification_level": "read-only",
    "verification_failures": "按任务要求仅登记元数据/许可证/README 一句话，未审计源码；未核 CI 明细。",
    "source_urls": [
      "https://github.com/rexglue/rexglue-sdk",
      "https://api.github.com/repos/rexglue/rexglue-sdk",
      "https://github.com/rexglue/rexglue-sdk/releases/tag/v0.10.0"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "hedge-dev/XenonRecomp",
    "url": "https://github.com/hedge-dev/XenonRecomp",
    "default_branch": "main",
    "head_sha": "ddd128bcca99fe8bfbb99bea583c972351fa6ace",
    "head_date": "2025-08-04",
    "pinned": "none（无 tag）/ ddd128bcca99fe8bfbb99bea583c972351fa6ace",
    "license_spdx": "MIT",
    "license_file": "LICENSE.md",
    "license_notes": "LICENSE.md 为 MIT（Copyright (c) 2025 hedge-dev and contributors）。",
    "archived": false,
    "last_push": "2025-08-04T13:56:30Z",
    "stars": 6640,
    "open_issues": 94,
    "build_system": "CMake ≥3.20 + Clang ≥18（submodules 递归 clone）；Windows 可用 clang-cl + Visual Studio CMake integration。",
    "build_deps": "CMake ≥3.20、Clang ≥18（具体库依赖本次未深入）。",
    "readme_claims": "XenonRecomp is a tool that converts Xbox 360 executables into C++ code, which can then be recompiled for any platform；\"does not provide a runtime implementation... Making the game work is your responsibility.\"",
    "readme_claim_url": "https://github.com/hedge-dev/XenonRecomp#readme",
    "risks": "Xbox 360 专用、无 tag、约 14 个月未更新、不含运行时；不列入第一阶段依赖。",
    "verification_level": "read-only",
    "verification_failures": "按任务要求仅登记元数据/许可证/README 一句话，未审计源码。",
    "source_urls": [
      "https://github.com/hedge-dev/XenonRecomp",
      "https://api.github.com/repos/hedge-dev/XenonRecomp"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "hedge-dev/XenosRecomp",
    "url": "https://github.com/hedge-dev/XenosRecomp",
    "default_branch": "main",
    "head_sha": "990d03b28a27b50277ee5d8d942e1c5f873869d1",
    "head_date": "2025-08-03",
    "pinned": "none（无 tag）/ 990d03b28a27b50277ee5d8d942e1c5f873869d1",
    "license_spdx": "MIT",
    "license_file": "LICENSE.md",
    "license_notes": "LICENSE.md 为 MIT（Copyright (c) 2025 hedge-dev and contributors）。",
    "archived": false,
    "last_push": "2026-03-12T17:36:37Z",
    "stars": 505,
    "open_issues": 10,
    "build_system": "CMake 3.20 + C++17（Clang tested，submodules 递归 clone）。",
    "build_deps": "CMake 3.20、C++17 编译器（具体库依赖本次未深入）。",
    "readme_claims": "XenosRecomp is a tool that converts Xbox 360 shader binaries to HLSL；产物经 DirectX Shader Compiler (DXC) 重编译为 DXIL/SPIR-V（D3D12/Vulkan），围绕 Unleashed Recompiled；\"Do not expect the recompiler to work out of the box.\"",
    "readme_claim_url": "https://github.com/hedge-dev/XenosRecomp#readme",
    "risks": "Xbox 360 着色器专用、无 tag、低活跃；不列入第一阶段依赖。",
    "verification_level": "read-only",
    "verification_failures": "按任务要求仅登记元数据/许可证/README 一句话，未审计源码。",
    "source_urls": [
      "https://github.com/hedge-dev/XenosRecomp",
      "https://api.github.com/repos/hedge-dev/XenosRecomp"
    ],
    "audited_at": "2026-10-29"
  }
]
```
<!-- AUDIT-JSON-END -->
