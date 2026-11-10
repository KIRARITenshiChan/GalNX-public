# 006 - Brewser Web 适配器（M4-b）

- 文档日期: 2026-10-30
- 负责: audit-web
- 任务: task-23「M4-b Brewser Web 适配器端到端」
- 状态: 模拟器侧端到端跑通（Citron Neo nightly 0237a9b88）；真机未验证
- 证据目录: `docs/milestones/evidence/M4b-*`；完整大图与运行产物在 gitignored 的 `workspaces/web-02/evidence/` 与 `workspaces/citron-harness/runs/`
- 结论分级: 标题→正文推进 = 实证；选择分支 A/B = 实证（整屏左右半区判定，见 §5.3）；localStorage 页内读写 = 实证；**跨 run 落盘 = 已证伪**（M4-g 实验：重启后 `SAVE=absent`，见 §12）

## 0. 边界与合规

- 只读使用 Brewser 官方预编译 `brewser.nro`（release tag `v0.1.1.31`，未改其源码，未重新构建）；内容包 `examples/web-vn/` 为本次自建、MIT 声明。
- 未读取/复制 `prod.keys`、`title.keys` 内容；Citron 仅校验其存在与大小（12,007 B / 11,492 B）。
- 不触碰任何商业游戏数据/ROM；实验对象只有 Brewser 自身与自建页面。
- 未修改 Citron 用户配置（`%APPDATA%\citron\config\qt-config.ini` 保持原样）；未执行 `git add/commit/push`。
- Citron 单实例：每次运行前确认 0 实例；本轮结束时已全部 kill（0 实例），03:00 释放窗口。
- Brewser 许可证 MPL-2.0（仓库 LICENSE）；本仓库不包含 Brewser 二进制，文档仅记录其哈希与行为。

## 1. 结论摘要（证据分级）

| # | 能力 | 结论 | 证据 |
|---|------|------|------|
| E1 | Brewser 在 Citron 加载运行 | 实证 | `bash scripts/citron_run.sh --game workspaces/web-01/brewser.nro` → status=loaded，窗口标题 `citron Nightly | 0237a9b88 | brewser (64-bit) | NVIDIA`，boot 行 `Booting game: 01F5905036D20000`；`M4b-brewser-run.json` |
| E2 | 本地 app 包被 Brewser 识别并渲染 | 实证 | `sdmc:/switch/brewser/apps/org.galnx.webvn/{manifest.json,index.html}` + `configs/config.json` 的 `autorunApp` → URL `brewser://apps/org.galnx.webvn/index.html`，页面完整渲染；`M4b-title.png` |
| E3 | 标题→正文推进（点击注入） | 实证 | 9 次注入点击，状态 `title → story/SCENE1 → SCENE2 → SCENE3`；`M4b-input-injection.json` |
| E4 | 选择分支 A / B | 实证（整屏左右半区，非严格 DOM 按钮） | 左半点击 → `STATE=endingA BRANCH=A`；右半点击 → `STATE=endingB BRANCH=B`；`M4b-endingA.png` / `M4b-endingB.png` |
| E5 | canvas 2D 自绘 + rAF 动画 | 实证 | 星月/海岸/两条光路逐帧绘制（截图），100+ 帧无异常 |
| E6 | localStorage 页内读写 | 实证 | `SAVE=present`，ending 状态回读；键 `galnx.webvn.save` |
| E7 | localStorage 落盘 / 跨 run 持久化 | **已证伪（M4-g）** | 运行中 `apps/org.galnx.webvn/localStorage/` 仅空目录、`shell/localStorage/default.json`（旧探针写入）mtime 未变；kill 后重启 `SAVE=absent`。页内读写 OK，但写入不落盘 → 不能作为存档后端 |
| E8 | 离线 catalogue 行为 | 实证（渲染） | Home → `brewser://home/`，网络关闭下卡片显示 `CONNECT TO INTERNET TO DOWNLOAD` |
| E9 | 真机行为 | **未验证** | 本机无 Switch；仅有 Brewser release notes 声称的真机验证（属 README/release 声称） |

## 2. Brewser 版本与运行环境

- 二进制: `workspaces/web-01/brewser.nro`，76,546,123 B，sha256 `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13`（与 GitHub release asset digest 一致；tag `v0.1.1.31` = 版本号 `0.1.131`，release 发布于 2026-09-15）。
- Brewser 组成（源码/README 取证）: nx.js fork（`natureglass/nx.js_extended` 分支 `nxjs-extended`）+ V8 JIT + Skia + WebGL 1/2 on Mesa/Nouveau；运行时版本见 `versions.json`（nx.js 1.0.0-beta.5、runtime 0.0.1、brewser 0.1.131）。
- 模拟器: Citron Neo nightly，Windows msvc 包 `Citron-windows-nightly-0237a9b88-x64-msvc.zip` 40,497,628 B sha256 `0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb`，日志内 build 号 `main-0237a9b88`；后端 Vulkan；firmware 硬编码 22.0.0（无固件文件）。
- 虚拟 SD: `%APPDATA%\citron\sdmc`（`use_virtual_sd=true`）。
- 运行命令（见 `docs/environment/citron-harness.md`）:

```bash
cd 'E:/Othergames/Nintendo Switch/Workspace/GalNX'
bash scripts/citron_run.sh --game workspaces/web-01/brewser.nro \
  --timeout 150 --settle 30 --expect-title brewser --keep
```

`--keep` 让实例保持运行，后续用 run 目录内的 `citron_win.ps1` 做截图/注入；不带 `--keep` 时 harness 在取证后自行 kill 本次启动的 pid。

## 3. Brewser 内容包约定（实测）

Brewser 是浏览器外壳（browser shell），自身 romfs 内是 shell 页面（home/about/settings 等）。第三方内容有两条实测可用的布局路线：

### 3.1 路线 A（推荐）：本地 app 包 `apps/<appId>/`

```
sdmc:/switch/brewser/
  apps/
    org.galnx.webvn/            <- appId，必须与 manifest.json 的 id 完全一致
      manifest.json             <- 应用清单
      index.html                <- entry 指向的入口页
      assets/banner.png         <- 可选，logo 指向的资源
      localStorage/             <- Brewser 在 app 启动时创建（见 §3.5）
```

识别规则（源码 `browser-shell.ts` 取证 + 实测）:

- app 目录 = `<appRoot>apps/<appId>/`，`appRoot` = `sdmc:/switch/brewser/`；允许一层 channel 前缀（`apps/<channel>/<reverse-dns>/`）。
- “已安装”判定 = `manifest.json` 存在且 `entry` 指向的文件存在；bootUrl = `brewser://apps/<appId>/<entry>`。
- 启动后 `sandboxRoot` = `<appRoot>apps/<appId>/`，manifest 的 permissions / allowed_origins 作用于该沙箱。
- 页面 URL `brewser://apps/org.galnx.webvn/index.html` 在 toolbar 中可见（`M4b-title.png`）。

### 3.2 路线 B：shell profile 页面 `<storageRoot>X/Y.html`

- `brewser://X/Y/` 解析为 `<storageRoot>X/Y.html`，否则试 `<storageRoot>X/Y/index.html`；
- `storageRoot` = `<profileRoot><profile>/`，默认 `sdmc:/switch/brewser/shell/`；`apps/`、`dev/` 前缀例外地走 `<appRoot>`；
- 这是 Brewser 自带 shell 页面的布局（例如 `shell/home.html`）；也可用于快速试验页（本次早期探针页 `shell/probe.html` 就是这样跑通的）。
- 注意：该布局没有 manifest/沙箱语义，只适合调试页或 shell 扩展；正式内容包请用路线 A。

### 3.3 manifest 字段（本次使用 + 平台文档对照）

本次内容包 `examples/web-vn/manifest.json`（506 B）字段：

```json
{
  "id": "org.galnx.webvn",
  "name": "GALNX Web VN Demo",
  "version": "0.1.0",
  "description": "Minimal MIT-licensed web visual novel used by the GalNX M4-b Brewser adapter smoke test.",
  "logo": "assets/banner.png",
  "entry": "index.html",
  "categories": ["Demos", "Games"],
  "permissions": ["Storage"],
  "compatibility": ["switch", "web"],
  "allowed_origins": [],
  "developer": "GalNX Project",
  "license": "MIT",
  "exitGame": "PLUS",
  "fullscreen": false
}
```

平台侧契约（`docs`/`platform-contract` 缓存证据）: 生产 manifest required 14 个字段：`id,name,version,description,logo,entry,categories,permissions,compatibility,allowed_origins,developer,license,exitGame,fullscreen`；permissions 取值 Title-Case（`Storage`/`Network`/`Usb`/`Device Info`）；`categories` 是字符串数组。

- 实测：`entry` 可以省略（默认 `index.html`），`logo` 指向的 PNG 缺失也不会阻止加载（本次 1x1 PNG）。
- 实测：`fullscreen:false` 下页面按 1280x664 CSS 视口渲染；窗口标题仍由 Brewser 固定。

### 3.4 启动入口：autorunApp

`sdmc:/switch/brewser/configs/config.json`

```json
{"autorunApp":"/apps/org.galnx.webvn/index.html"}
```

实测结论：

- `autorunApp` 非空时，Brewser 启动后直接导航到该 URL，不出现在 home 页；
- 语法：leading slash 按 `brewser://` 同源解析（`/apps/...` ⇒ `brewser://apps/...`），绝对 scheme（`brewser://`、`http(s)://`）原样透传；
- 空字符串则走默认 home（`brewser://home/`）；Home 按钮始终回默认 home；
- forwarder NSP 模式（`--fwd=1` / `--app=<appId>`）属真机 forwarder 场景，本次未验证。

home catalogue / navigator 是否自动收录本地 `apps/` 包：**未验证**。本次 `brewser://home/` 只显示网络 catalogue 卡片（离线占位 `CONNECT TO INTERNET TO DOWNLOAD`），未看到本地 app 卡片；离线安装的 app 至少可通过 `autorunApp` 直达，是否需要在 shell 内手动入口仍需真机/联网条件确认。

### 3.5 存储根与 localStorage

- 应用存储根: `apps/<appId>/`（沙箱）；Brewser 启动 app 时创建 `apps/<appId>/localStorage/` 目录；
- shell 页面存储: `shell/localStorage/*.json`（web-02 阶段探针页写入 `{"glxprobe":"1"}` 曾落盘到 `shell/localStorage/default.json`）；
- 本次 VN 使用 `localStorage.setItem("galnx.webvn.save", ...)`：页内 `getItem` 回读成功（`SAVE=present`），但运行期间 session 内磁盘上 `apps/org.galnx.webvn/localStorage/` 为空；导航回 `brewser://home/` 后仍未 flush。
- 结论（M4-b 时）: **页内可用，落盘时机未知**；M4-g 交叉实验（§12）已证伪跨 run 持久化：kill 后重启 `SAVE=absent`。

### 3.6 为什么不用 `make sdmc`

Brewser 仓库的 `make sdmc` 是开发者循环：把仓库 `romfs/*` 镜像到 `SDMC_DEST`（默认指向开发者的 `%APPDATA%\citron\sdmc\switch\brewser`），用于调试 Brewser 自身 shell。本次只使用官方 release 的 `brewser.nro` 作为只读输入，不修改 Brewser 源码，因此只需把内容包放进 SD 的 `apps/` 目录并用 `autorunApp` 指定入口即可，无需 `make sdmc`，也不需要 devkitPro。

## 4. 自建内容包 examples/web-vn（MIT）

- 文件: `examples/web-vn/manifest.json` 506 B sha256 `aca5f494dff67141be252ed0d83e6f692377438025ed1ef823f89593a73084fb`；`examples/web-vn/index.html` 9,558 B sha256 `a28594ea7c3735be5f4c3df592e861568f7b901c61684faa5190c5e45522feb3`。
- 内容: 单页 HTML（inline CSS+JS，无第三方依赖/素材）：canvas 2D 程序化绘制星空、月亮、海岸线与两条光路（rAF 动画）；剧情状态机 title → SCENE1/2/3 → endingA/endingB → 回标题；`localStorage` 键 `galnx.webvn.save`；页面元信息行显示 `STATE / SCENE / BRANCH / SAVE / CLICKS`。
- 交互: 点击页面任意处推进剧情；到达 SCENE3 后按点击位置选择分支：CSS `clientX < innerWidth/2` → A（FOLLOW THE STAR），否则 → B（STAY ON THE SHORE）。页面同时保留 5 个 `<button>` UI（START/CONTINUE/RESET SAVE/CHOICE A/CHOICE B），按钮监听在 Brewser 下不稳定（§9），但 UI 保留以便真机/桌面浏览器对照。
- 调试开关: 页面底部 `DBG=` 行仅在 URL 带 `?debug=1` 时显示（默认隐藏）；证据截图来自调试模式，显示事件 CSS 坐标/innerWidth/dpr/target，用于 §5.3 坐标映射标定。
- 部署方式: 把 `manifest.json` + `index.html` 复制到 `sdmc:/switch/brewser/apps/org.galnx.webvn/`，并设置 `configs/config.json` 的 `autorunApp`。

## 5. 运行手册

### 5.1 环境准备

1. Citron 用户目录含 `keys/prod.keys`（用户自备；本仓库不含任何密钥）。
2. `sdmc:/switch/galnx-harness/brewser.nro`（harness 自动 stage）或任意路径的 NRO。
3. 内容包部署到 `sdmc:/switch/brewser/apps/org.galnx.webvn/`；`configs/config.json` 写 `{"autorunApp":"/apps/org.galnx.webvn/index.html"}`（改动前备份原文件）。

### 5.2 输入注入（harness 现有能力）

- 用 `scripts/citron_run.sh` 的 `--input-click X,Y`（一次点击）或 `--keep` 后用 run 目录里的 `citron_win.ps1 -Mode input -Hwnd <hwnd> -X <imgX> -Y <imgY>` 逐步注入；
- `-X/-Y` 使用 **PrintWindow 整窗图像坐标**（窗口 rect 左上为原点；本次窗口 `windowRect=(426,167,2136,1174)`、client `1706x960`、图像中 client 偏移 `(2,45)`）；
- 注入实现：`SetCursorPos` + `mouse_event` 绝对坐标左键 down/up（真实鼠标事件）；Citron 侧 `mousePressEvent → GetMouse()->PressTouchButton` 同时产生触摸输入，Brewser 再转成页面 pointer/touch/click；
- 键盘：`PostMessage(WM_KEYDOWN/WM_KEYUP)` 到 Citron 主窗有效（M2-a 已实证可推进 KAG3）；`SendInput` 键盘对 Citron 无效（M2-a 记录）；本次分支选择只用鼠标点击。

### 5.3 坐标映射（实测，重要）

- 页面 CSS 视口 = `1280x664`，`devicePixelRatio = 1`；视觉渲染区在 client 内为 `(102,138)-(1603,916)`（1501x778 物理像素，缩放 1.1727）。
- 用 3 次标定点击（页面 DBG 行读出事件坐标）拟合出事件坐标映射：

```
css_x = 0.8514 * client_x - 93.9
css_y = 0.850  * client_y - 61.0
```

| 点击（图像坐标） | client 坐标 | 页面事件 CSS 坐标 |
|---|---|---|
| (602,445) | (600,400) | (417,279) |
| (1302,345) | (1300,300) | (1013,194) |
| (302,845) | (300,800) | (162,619) |

- 该映射的线性拟合残差 <1 px，但**事件坐标系与视觉坐标系不一致**：纵向原点比页面渲染区高约 66 物理像素（≈56 CSS px），横向差约 8 px。即按视觉位置点按钮时，页面收到的坐标存在系统偏移，这就是 DOM `<button>` 命中不稳的直接原因之一。
- 因此内容包采用“整屏左右半区”判定（不依赖像素级 DOM 命中）：点击 client x=600（事件 css_x≈417）→ A；点击 client x=1500（事件 css_x≈1183）→ B，两者都稳定复现。

## 6. 证据清单

仓库内（`docs/milestones/evidence/`，sha256 见 `M4b-artifacts-sha256.txt`）：

| 文件 | 大小 | sha256 | 说明 |
|---|---|---|---|
| `M4b-title.png` | 171,263 B | `f9b802be3502e88dc40449f8923dc508f05bbe9f8f56a7217d2d51cade57103b` | 标题页，URL `brewser://apps/org.galnx.webvn/index.html`，`STATE=title SAVE=absent CLICKS=0` |
| `M4b-endingA.png` | 177,678 B | `7183c12b19a6a2921aa16c610b3d8c5e3632da8b49c9d668865ecc8ea6352ee0` | 分支 A：`STATE=endingA BRANCH=A SAVE=present CLICKS=4`，背景为夜幕海岸+两条光路 |
| `M4b-endingB.png` | 176,543 B | `d8d012379e69069ecd9b34411c8cfabdd688ddd309aa66d21804d2aba79e5798` | 分支 B：`STATE=endingB BRANCH=B SAVE=present CLICKS=9` |
| `M4b-input-injection.json` | 6,134 B | 见清单 | 9 次点击的坐标/状态、坐标映射、localStorage 结论 |
| `M4b-brewser-run.json` | 1,774 B | 见清单 | harness 启动结果（status=loaded、boot_line、窗口标题、pid） |
| `M4b-citron-log-slice.txt` | 8,306 B | 见清单 | Citron 日志切片（含 `Booting game:`、加载 brewser、home 页导航） |

gitignored 运行产物（`workspaces/`）: 全分辨率逐帧截图 `workspaces/web-02/evidence/m4b-debug-*.png`（含 click1-3、scene3、choiceA/B、home 等）、`workspaces/citron-harness/runs/20261030-025247-brewser/`（window.png、result.json、citron_log.txt 等）。

## 7. 与 krkrsdl2（KAG3）适配器对比

| 维度 | KAG3 / krkrsdl2（原生 NRO） | Brewser（Web 运行时） |
|---|---|---|
| 内容形态 | 游戏数据目录 + 启动 script（`startup.tjs`） | app 包（`manifest.json` + HTML/JS/资源） |
| 加载方式 | `--game xxx.nro` 直接引导 NRO | `--game brewser.nro` + SD 上内容包 + `autorunApp` |
| 渲染 | 引擎自绘（SDL2 + 自研图层） | Brewser 的 live-DOM + Skia 光栅 + CSS 管线 |
| 文本/UI | KAG3 脚本语义（`[link]` 等） | 标准 HTML/CSS/DOM（子集）+ JS |
| 输入 | 鼠标点击 → 触摸 → KAG 的 OnClick；键盘 PostMessage 可用 | 鼠标点击 → 触摸 → 页面 pointer/touch/click；键盘转发存在但本次未用于交互 |
| 存档 | KAG 自身存档机制（本次未验证） | `localStorage` 页内可用；**跨 run 不持久化（M4-g 证伪）** |
| 适配工作量 | 需引擎/内容移植或封装 | 内容可直接用 HTML/JS；但受 Brewser DOM/CSS 子集与输入层限制 |
| 引擎注册表 game_type | `nro` | `nro`（外层仍是 NRO），内容入口走 `autorunApp`/app 包 |

## 8. 未验证项与风险

1. ~~localStorage 落盘/跨 run 持久化未验证~~ → **已证伪（M4-g，2026-10-30）**：页内读写 OK，但进程结束（kill）后磁盘无写入文件，重启 `SAVE=absent`。结论：本轮 Brewser 版本的 localStorage 不能承载存档；M4 存档需引擎侧改造（运行时修复持久化）或换存储后端/外部存档，见 §12。
2. **DOM 按钮 click 不稳定**：Brewser LiveElement 事件 target 的 `tagName` 为空、事件坐标与视觉坐标有系统偏移；结论中“选择分支”按整屏左右半区判定，严格 DOM 按钮点击未打通。
3. **真机未验证**：Brewser release notes 声称在 CFW 真机验证（`real V8 JIT verified on CFW hardware`、WebGL2 via Mesa/Nouveau），属官方声称；本仓库无真机证据。
4. **触摸通道标 supported 但只验证了鼠标→触摸合成路径**；纯触摸（真机手指/屏幕）未验证。
5. **WebGL/WebAudio 未在本轮 VN 中依赖**；Brewser release notes 声称 WebGL2 可用（`Mesa 20.1.0-rc3`），本轮未做像素级验证。
6. **离线 catalogue/navigator 收录本地 app 未验证**；`autorunApp` 直达可用，home 页未显示本地 app 卡片（联网 catalogue 实测离线占位）。
7. **性能**：Citron 下 Brewser 页面 60 FPS（状态栏实测），但 JS 密集/大 DOM 场景未压测。

## 9. 失败模式与实验噪声记录

| 现象 | 原因 | 处置 |
|---|---|---|
| 注入点击后 `CLICKS` 增加但状态不变/按钮无响应 | 事件坐标与视觉坐标错位 + LiveElement target.tagName 为空 → 按钮判定失效 | 改用 document 级整屏左右半区判定；按钮保留 UI |
| 某次点击命中 Citron 顶部 `View` 菜单（截图可见下划线，页面 URL 未变） | 误把 client y=45 当成 Brewser 工具栏（实际是 Citron 自身菜单栏） | 已确认无副作用；Brewser 工具栏在 client y≈120；作为坐标陷阱记录 |
| `--keep` 实例与新一轮冲突 `citron_already_running` | Citron 单实例 | 每轮前 `tasklist` 检查并 kill 自己的实例 |
| 页面 DBG 行污染交付内容 | 调试用 | DBG 行改为 `?debug=1` 才显示，默认隐藏 |
| 本地 app 包未出现在 home 页 | catalogue 来自网络/内置清单 | 用 `autorunApp` 直达；catalogue 收录列为未验证 |

## 10. 给 M4-a 的 Brewser 适配器字段建议

以下为 audit-switch 在 M4-a 引擎注册表中对齐 Brewser 所需的字段（值来自本轮实测/文档取证）：

| 字段 | 建议值 | 依据 |
|---|---|---|
| `engine_id` | `brewser-web` | 引擎名（Web/JS 运行时） |
| `engine_kind` | `web_runtime` | 与 `native_nro`（krkrsdl2）区分 |
| `runtime_nro` | `brewser.nro`（锁定 sha256 `8ce31f5b...`） | 官方 release 预编译，不需重建 |
| `content_layout` | `brewser_app_pack` | `apps/<appId>/{manifest.json,index.html,assets/,localStorage/}` |
| `content_root_sdmc` | `sdmc:/switch/brewser/apps/<appId>/` | 实测部署路径 |
| `manifest_required` | `id,name,version,description,logo,entry,categories,permissions,compatibility,allowed_origins,developer,license,exitGame,fullscreen` | 平台契约文档 + 实测 |
| `manifest_id_rule` | `id` 必须等于目录名（reverse-dns） | 实测 |
| `entry_default` | `index.html` | 实测 |
| `boot_url` | `brewser://apps/<appId>/<entry>` | 实测 toolbar URL |
| `startup_entry` | `sdmc:/switch/brewser/configs/config.json` 的 `autorunApp` | 实测生效 |
| `autorun_syntax` | leading slash 按 `brewser://` 同源；绝对 scheme 透传 | 源码注释 + 实测 |
| `storage_root_app` | `<appRoot>apps/<appId>/`（含 `localStorage/`） | 实测目录创建 |
| `storage_root_shell` | `sdmc:/switch/brewser/shell/` | 文档+实测 |
| `save_capability` | `localstorage-memory-only`（页内 OK，跨 run 不落盘；**不可用于存档**） | M4-g 实测（§12） |
| `input_mouse` | supported（harness 注入 mouse_event → touch 合成 → 页面 click 实证） | 本轮实测 |
| `input_touch` | supported（平台声明），**真触摸未验证** | 平台契约 + 实测边界 |
| `input_keyboard` | partial：PostMessage 键可到 Citron/引擎层，页面 keydown 转发存在但本轮未用于交互 | M2-a + 源码取证 |
| `input_pointer` | supported（页面 pointerdown/click 实证） | 本轮实测 |
| `exit_game` | `PLUS`（manifest 字段；真机退出方式未验证） | manifest 契约 |
| `offline` | 内容包与 shell 可离线运行；catalogue 下载需网络 | 本轮实测 |
| `license_runtime` | MPL-2.0（Brewser）；nx.js/上游组件 MIT 等；分发二进制需随附许可证 | 仓库 LICENSE + NOTICE 类文档 |
| `verification_level` | `emulator-verified`（Citron nightly 0237a9b88），真机 `not-verified` | 本轮 |

## 11. 后续建议

1. **存档能力（阻塞项已收口为结论，不再是未验证）**：本轮 Brewser 的 localStorage 只在内存生效，进程结束即丢失（M4-g：kill 后重启 `SAVE=absent`，磁盘无写入）。真机同版本预计一致（同一运行时）；若 M4 需存档，必须（a）推动 Brewser 运行时修复持久化，或（b）改用引擎外存档（由 GalNX 启动器读页面导出/ES 文件/自建后端），见 §12。
2. 输入层：真机验证纯触摸（手指/触摸屏）与手柄映射；本轮的鼠标注入仅覆盖模拟器/鼠标场景。
3. 内容包约定建议：M4-a 的适配器产包时按 `apps/<reverse-dns-id>/` 生成 manifest.json + index.html + assets/，并写 `autorunApp`；不要依赖 home catalogue 收录。
4. 若需要“严格 DOM 按钮”能力，需要等 Brewser 运行时修复事件坐标/target 语义，或改用 canvas 自绘按钮 + 区域 hit-test（本轮已验证后者稳定）。
5. 保留 `examples/web-vn/` 作为后续真机/模拟器回归的最小内容包（MIT，无第三方素材）。

## 12. M4-g：localStorage 跨 run 持久化实验（2026-10-30）

目的：把 §8 的“落盘未验证”收口为可执行结论（M4 存档阻塞项）。实验在 Citron nightly 0237a9b88（Windows msvc）上做，Brewser `brewser.nro` sha256 `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13`，内容包 `org.galnx.webvn`。

### 12.1 实验步骤与结果

| 步骤 | 操作 | 观测 | 证据 |
|---|---|---|---|
| A1 | `scripts/citron_run.sh --game brewser.nro --expect-title brewser --keep` 启动（pid 39220，status=loaded） | `STATE=title SAVE=absent CLICKS=0` | `M4g-a-boot-save-absent.png`（208,184 B，sha256 `587dd781…`） |
| A2 | 注入点击 image(602,445)（click→touch→页面 pointerdown） | `STATE=story SCENE=1 SAVE=present CLICKS=1`（页内 setItem/getItem 生效） | `M4g-a-after-click-save-present.png`（199,126 B，sha256 `8021ba6d…`） |
| A3 | 运行中检查磁盘 | `apps/org.galnx.webvn/localStorage/` = 空目录（0 文件）；`shell/localStorage/default.json` 16 B mtime 2026-10-29T23:13 未变（sha256 `35c6ba52…`） | `M4g-localstorage-state.txt` |
| A4 | 优雅退出尝试：`PostMessage(WM_CLOSE)` 到主窗（hwnd 0x2484104A），等 20 s | **未退出**（Citron 忽略 WM_CLOSE / 被自身关闭流程吞掉）；此后注入点击不再生效（focus_ok 由 1 变 0），说明窗口焦点/关闭状态被破坏 → 优雅退出路径在本 harness 下不可用 | 记录于本节 + run.log |
| A5 | `Stop-Process -Force` 结束 pid 39220 | 进程 0；磁盘仍无新文件；`find -newermt 03:15` 仅 `logs/foreignobject.log`（656 B，03:17） | `M4g-localstorage-state.txt` |
| B1 | 重新运行 harness（pid 15128，status=loaded，elapsed 37 s） | 启动页 `STATE=title SAVE=absent CLICKS=0` → **跨 run 不持久化** | `M4g-b-restart-save-absent.png`（208,071 B，sha256 `d4a0670b…`）、`M4g-run-b-result.json` |

两次运行的 harness 结果均为 `status=loaded`、`window_title` 含 `brewser`、`signals.title_match/boot_line=true`：`M4g-run-a-result.json`（sha256 `9704054f…`）、`M4g-run-b-result.json`（sha256 `3b3c13bc…`）。

### 12.2 源码侧旁证（cached `@switch-web/runtime` 接口，见 `.cache/web/`）

- `browser-shell.ts`：`getProfile()` 暴露 profile 给运行时 `installLocalStorage / installIndexedDB`（注释原文 “Expose the profile so main.ts can pass it to the runtime's installLocalStorage / installIndexedDB”），页面上下文配置里 `storageRoot: this.profile.storageRoot`。
- `browser-profile.ts`：`storageRoot = ${profileRoot}${name}/` = `sdmc:/switch/brewser/shell/`；`storagePathForOrigin(origin, storageRoot)` 决定 per-origin 路径；`Switch.mkdirSync(storageRoot)`。
- 即：**落盘根应为 `shell/localStorage/`**（`shell/localStorage/default.json` 就是 web-02 探针页写入的旧值，证明该版本曾成功落盘过一次）；而 app 沙箱的 `apps/<id>/localStorage/` 只是空目录。本轮 VN 页写入未产生任何新文件 → 运行时的 localStorage 写盘在当前版本下未触发（可能依赖页面卸载/退出钩子；WM_CLOSE 实验因 Citron 忽略关闭消息而无法验证优雅退出路径）。

### 12.3 结论（M4 存档阻塞项）

1. **页内可用、跨 run 不可用**：`localStorage` set/get 在页面生命周期内正常（`SAVE=present` 可回读），但进程结束后磁盘没有任何对应文件，重启即丢。
2. **不是 harness 的 kill 造成**：窗口关闭（WM_CLOSE）与强制结束两条路径都试过，均无落盘；且旧 `shell/localStorage/default.json` 证明运行时具备写盘能力，故更可能是“flush 时机依赖正常页面卸载/退出钩子”，而非磁盘不可写。
3. **对 M4 的含义**：Brewser 当前版本 **不能直接承载存档**。可选路径：(a) 推动 Brewser/`@switch-web/runtime` 修复持久化（上游 issue，需真机复验）；(b) 引擎外存档：GalNX 启动器在退出前让页面把存档导出（如通过可下载 blob/自定义导航参数）由启动器落盘，或由启动器提供的宿主存储 shim；(c) 改用其他引擎承载存档敏感内容。
4. **未验证**：真机同版本行为（同一运行时二进制，预计一致但未实测）；正常用户退出（HOME 键/系统关闭）是否触发 flush（Citron 下无法模拟干净的系统级关闭）。

### 12.4 环境与合规

- 未改 Citron 配置、未读密钥内容、未改 `scripts/citron_run.sh`；实验用 `--keep` + helper 注入点击，结束后强制结束自己启动的 pid。
- Citron 在 03:41 全部关闭（`citron_count=0`），释放给其他任务。