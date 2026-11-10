# Web-02：Citron Neo 上 Brewser 最小 HTML5 冒烟实验

- 实验日期: 2026-10-29
- 执行: audit-web
- 关联任务: task-11（Web 路线复核 + Citron Neo 模拟器审计与 Brewser 实测）
- 前置: [web-01-brewser-smoke.md](web-01-brewser-smoke.md)（Ryujinx Canary 1.3.265 加载 nx.js 系 NRO 停滞，结论为环境阻塞）
- 性质: **本机模拟器实测**（非只读审计；但仅运行官方 release 二进制 + 自写 HTML 探针页）
- 结论: **可行** —— Citron Neo nightly `0237a9b88`（Windows msvc / Vulkan）成功运行 Brewser v0.1.131 预编译 NRO，HTML/DOM/CSS/JS/Canvas2D/WebGL/localStorage 全部实测通过，JS 定时器与 rAF 持续运行，两次启动均可复现。

## 0. 边界声明

- 未构建、未修改 Brewser 或 Citron；未安装任何工具/包；未克隆仓库；未下载 ROM/商业游戏数据。
- 未读取、未打印、未入库模拟器密钥内容：`prod.keys`/`title.keys` 为用户本机既有文件，仅以文件复制方式供给 Citron 启动使用。
- 所有资产 sha256 为本机实测（`sha256sum`）；截图与日志为原始证据。
- 探针页为自写最小页面，无第三方版权内容。

## 1. 目的

M4（Web 路线）前置验证：H1 Citron Neo nightly 能否加载 Brewser 预编译 NRO？H2 页面能否真实执行 HTML/DOM/CSS/JS/Canvas2D/WebGL/localStorage？H3 是否可复现、能否作为 M4 开发循环模拟器？

## 2. 环境

| 项 | 值（实测） |
|---|---|
| 主机 | Windows 11 24H2 Build 26100.9711；i7-12650H（10C/16T，AVX2 FMA）；RAM 31.74 GiB |
| GPU/驱动 | NVIDIA GeForce RTX 4060 Laptop GPU；Driver 621.1.0.0；Vulkan 1.4.357；VRAM 6.14 GiB（上限 5032 MB） |
| 模拟器 | Citron Neo nightly Windows msvc `Citron-windows-nightly-0237a9b88-x64-msvc.zip`；版本串 `citron Development Build | main-0237a9b88`；MSVC Compiler 1944 / Runtime 14.51.36247.0；Qt 6.9.3 |
| 图形设置 | Renderer.backend Vulkan；vsync Fifo；resolution 1x；async GPU emulation ON；docked 模式（状态栏 DOCKED） |
| 固件 | **未安装**；日志 `SystemVersion: called - Using hardcoded firmware version 'NintendoSDK Firmware for NX 22.0.0-3.0'`、`SetFirmwareVersion: Installed firmware: No firmware available` |
| 兼容性列表 | 空（`LoadCompatibilityList: Game compatibility list is empty or unreadable`） |
| 密钥 | 用户本机已有 `prod.keys`（12,007 B）/`title.keys`（11,492 B），复制到 Citron 用户目录，未打印内容 |
| 网络 | 未改动 Citron 网络设置；本探针页不发网络请求（Brewser 自身联网能力未测） |

## 3. 资产与校验（本机实测 sha256）

| 资产 | 大小 (B) | sha256 | 来源 |
|---|---|---|---|
| `brewser.nro`（v0.1.131，release tag `v0.1.1.31`） | 76,546,123 | `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13` | https://github.com/natureglass/Brewser/releases/download/v0.1.1.31/brewser.nro |
| `Citron-msvc.zip`（解压到 `workspaces/web-02/citron/`） | 40,497,628 | `0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb` | https://github.com/citron-neo/emulator/releases/download/2026-04-27/Citron-windows-nightly-0237a9b88-x64-msvc.zip |
| `hbmenu.nro`（对照，nx-hbmenu v3.6.1） | 2,455,539 | `6cf6d130515723ebe0041c2479420caf9726895087439ff7b2e528c2ed39c100` | https://github.com/switchbrew/nx-hbmenu/releases |
| `probe.html`（自写探针页） | 2,672 | `88906752edc16ea8de2ec89a17fe31f00e1da73441524a0d4948b3c92eb5859f` | 本实验附录 A |

> 上游 hbmenu 版本号来自 web-01 记录（v3.6.1）；本轮仅用其作为已知-good homebrew 对照。

## 4. 部署

### 4.1 用户目录与 SD 根

- Citron 无 `user/` 目录时使用 `%APPDATA%\citron`（源码 `src/common/fs/path_util.cpp:91-94`：Windows 下若 exe 同级 `PORTABLE_DIR` 存在则便携，否则 `GetAppDataRoamingDirectory() / CITRON_DIR`；BUILDING 文档也称每个输出目录含空 `user/` 供便携 profile）。本轮**未**创建 `user/`，使用默认目录：
  - 用户目录：`%APPDATA%\citron\`（`config/`、`keys/`、`log/`、`nand/`、`sdmc/`、`saves？`→ 实际子目录 amiibo/cache/config/crash_dumps/dump/icons/keys/load/log/nand/play_time/screenshots/sdmc/shader/tas）；
  - SD 根：`%APPDATA%\citron\sdmc\`。
### 4.2 SD 布局（本实验）

```text
%APPDATA%\citron\sdmc\switch\
  brewser.nro                     # 76,546,123 B
  hbmenu.nro                      # 2,455,539 B（对照）
  brewser\configs\config.json     # {"autorunApp":"brewser://probe/"}（Brewser 启动后自动导航到探针页）
  brewser\shell\probe.html        # 2,672 B 自写探针页
  brewser\logs\                   # 预留，Brewser 诊断日志目录
```

- `configs/config.json` 只在缺失时 seed（`seedConfigSync` missing-only），故自定义 `autorunApp` 不会被 romfs 覆盖；`shell/probe.html` 不在 romfs 中，也不会被 seed walker 覆盖。
- 运行后 Brewser 自行完成首次 seed：`seed-fingerprint`（32 B）、`shell/home.html`（39,591 B）等 → 这是 Brewser 主程序真实执行的客观证据。

### 4.3 启动方式

- CLI（`src/citron/main.cpp` 实测）：`citron.exe` 参数 `args.size()==2` 且不以 `-` 开头时直接作为 game path；另有 `-f`（全屏）、`-u <user>`、`-g <path>`。
- wrapper（无空格路径，供 runas 调用）：`C:\Users\ACETaffy\glx\launch-citron-brewser.cmd`：`@echo off` / `cd /d "<citron 解压目录>"` / `"citron.exe" -g "<sdmc>\switch\brewser.nro"`。
- 启动：`powershell Start-Process runas.exe -ArgumentList '/trustlevel:0x20000','C:\Users\ACETaffy\glx\launch-citron-brewser.cmd'`。本 agent shell 为 elevated 会话，为与 web-01 工作流一致用 runas 去提权启动；**Citron 本身是否拒绝管理员运行未单独验证**。

## 5. 探针页（`probe.html`，全文见附录 A）

覆盖：静态 DOM 文本、CSS 盒模型/字体/颜色、inline `<script>` 执行、`setInterval` 250 ms 计数、`requestAnimationFrame` + Canvas2D 动画与文字绘制、`localStorage` 读写、`getContext('webgl2')||getContext('webgl')` 与 `gl.getParameter(gl.VERSION)`、`window.onerror` 捕获与错误显示（`#err`）。

## 6. 时间线

| 序号 | 动作 | 观察 |
|---|---|---|
| 1 | 下载 `Citron-msvc.zip`（curl 走本机代理） | HTTP 200；40,497,628 B；sha256 与 release digest 一致 |
| 2 | 解压到 `workspaces/web-02/citron/` | `citron.exe` 23,272,960 B；Qt6.9.3/SDL2/FFmpeg DLL 齐全；无 `user/` |
| 3 | 复制用户既有 keys 到 `%APPDATA%\citron\keys\` | 未打印内容；文件大小 12,007 / 11,492 B |
| 4 | 部署 SD（brewser.nro、hbmenu.nro、config.json、probe.html） | 见 `4.2 |
| 5 | 运行 1：wrapper + runas | 窗口标题 `citron Nightly | 0237a9b88 | brewser (64-bit) | NVIDIA`；探针页渲染成功；截图 01 |
| 6 | 同一次运行约 15–20 s 后再截图 | `TICKS 17→75`、`frame 219→1119` → 定时器与 rAF 持续运行；截图 02 |
| 7 | 关闭，运行 2（复现性） | 同样成功；截图 03（`TICKS 48`、`frame 697`） |
| 8 | 对照：以 hbmenu.nro 启动 | 渲染 `Error: launchInit() failed. Press the + button to exit.`（与 Ryujinx 下相同，预期） |
| 9 | 关闭全部 Citron 进程 | 进程数 0 |

- 启动耗时（run1 日志相对时间）：`BootGame: citron starting...` 2.17 s → `Loading brewser` 2.42 s → `Booting game` 3.76 s → `shell/home.html` 12.23 s → `seed-fingerprint` 15.97 s。即从启动到页面可交互约 **10–15 s**（首次 seed 含在内）。

## 7. 结果

| # | 检查项 | 期望 | 实测 | 证据 |
|---|---|---|---|---|
| 1 | homebrew NRO 加载 | 进入应用 | ✅ 日志 `Loading brewser (01F5905036D20000)`、`Booting game: ... brewser (64-bit)`；窗口标题变更 | run1.log |
| 2 | SD 首次 seed | 生成 seed-fingerprint 等 | ✅ `sdmc/switch/brewser/{seed-fingerprint, configs/*, shell/*, themes/*}` 全部生成 | 目录快照 |
| 3 | 静态 DOM | 文本渲染 | ✅ `GALNX WEB PROBE 01`、`STATIC DOM TEXT OK` | 截图 01/03 |
| 4 | CSS | 背景/字体/盒 | ✅ 深蓝背景、红色 220×56 盒、字号/颜色正确 | 截图 01/03 |
| 5 | inline JS | 执行 | ✅ `JS: INLINE OK`（页面脚本经 Brewser `runPageScripts` 执行） | 截图 01/03 |
| 6 | `setInterval` | 计数递增 | ✅ `TICKS 17 → 75`（两截图间）；run2 `48` | 截图 01/02/03 |
| 7 | `requestAnimationFrame` | 帧递增 | ✅ `CANVAS 2D OK frame 219 → 1119`；绿色方块位移 | 截图 01/02/03 |
| 8 | Canvas2D 绘制 | 图形+文字 | ✅ 黑底、白字、绿色方块 | 截图 |
| 9 | `localStorage` | 读写持久 | ✅ 状态行 `localStorage:1` | 截图 |
| 10 | WebGL 上下文 | 可创建 | ✅ `WebGL:OK OpenGL ES 3.2 Mesa 20.1.0-rc3` | 截图状态行 |
| 11 | WebGL 实际绘制 | 像素级验证 | ⚠️ **未验证**：仅创建上下文/取 VERSION，未做 `readPixels`/绘制图元校验；画面中 WebGL canvas 只有边框内黑底 | — |
| 12 | 页面错误 | 无异常 | ✅ `window.onerror` 未触发（`#err` 仅探针自检输出） | 截图 |
| 13 | 复现性 | 二次启动成功 | ✅ 2/2 成功（run1、run2） | 日志/截图 03 |
| 14 | hbmenu 对照 | 已知-good 行为 | ✅ 与 web-01/Ryujinx 下一致 | 截图 control |
| 15 | 输入（手柄/触摸映射） | — | ⚠️ **未测**：本轮无输入注入；Brewser 键位（ZR 地址栏、B/X/Y 导航等）未验证 | — |
| 16 | 音频 | — | ⚠️ **未测** | — |
| 17 | 联网 | — | ⚠️ **未测**：日志中 BSD socket 读为 `STUBBED`；Brewser 联网/WebSocket 能力未验证 | 日志 |

## 8. 关键日志摘录（原文）

运行 1（`evidence/logs/citron-brewser-run1.log`，164,418 B）：

```text
[   1.629716] Frontend <Info> citron\main.cpp:411:GMainWindow: citron Version: citron Development Build | main-0237a9b88
[   1.638431] Common.Filesystem <Warning> core\file_sys\system_archive\system_version.cpp:17:SystemVersion: called - Using hardcoded firmware version 'NintendoSDK Firmware for NX 22.0.0-3.0'
[   1.638465] Frontend <Info> citron\main.cpp:6104:SetFirmwareVersion: Installed firmware: No firmware available
[   1.638573] Frontend <Error> citron\game_list.cpp:3354:LoadCompatibilityList: Game compatibility list is empty or unreadable
[   2.182976] Config <Info> common\settings.cpp:111:operator (): -- Renderer.backend: Vulkan
[   2.461631] Render.Vulkan <Warning> video_core\vulkan_common\vulkan_device.cpp:563:Device: Ampere and newer have broken float16 math
[   2.461632] Render.Vulkan <Warning> video_core\vulkan_common\vulkan_device.cpp:572:Device: NVIDIA Drivers >= 510 do not support MSAA image blits
[   3.686845] Render.Vulkan <Info> video_core\renderer_vulkan\renderer_vulkan.cpp:197:Report: Device: NVIDIA GeForce RTX 4060 Laptop GPU
[   2.170606] Frontend <Info> citron\main.cpp:2322:BootGame: citron starting...
[   2.421734] Core <Info> core\core.cpp:392:Load: Loading brewser (01F5905036D20000) ...
[   3.755415] Frontend <Info> citron\main.cpp:2475:BootGame: Booting game: 01F5905036D20000 | brewser (64-bit) | 
[  12.231881] Service.FS <Warning> ...:GetFileTimeStampRaw: (Partial Implementation) called. file=/switch/brewser/shell/home.html
[  15.969084] Service.FS <Warning> ...:GetFileTimeStampRaw: (Partial Implementation) called. file=/switch/brewser/seed-fingerprint
```

- 运行期间着 Shader 解码断言 **112 条**：`Debug <Critical> shader_recompiler\frontend\maxwell\decode.cpp:49:operator (): Assertion Failed!`（非致命，持续刷日志）。
- 日志尾部有多条 `Service <Warning> core\hle\service\sockets\bsd.cpp:456:Read: (STUBBED) called.` → 网络栈未实现，任何联网行为都无法判为可用。

hbmenu 对照（`evidence/logs/citron-hbmenu-run.log`）：

```text
[   1.271791] Core <Info> core\core.cpp:392:Load: Loading nx-hbmenu (0000000000000000) ...
[   1.741099] Frontend <Info> citron\main.cpp:2475:BootGame: Booting game: 0000000000000000 | nx-hbmenu (64-bit) | 
```

## 9. 证据清单（sha256 本机实测）

| 路径（相对 `workspaces/web-02/`） | 内容 | sha256 |
|---|---|---|
| `evidence/citron-brewser-boot-01.png` | 运行 1 首次截图（探针页 + TICKS 17 + frame 219 + localStorage/WebGL 状态行） | `6ace26c1cd47207e9b94d0ac1d7f3bdcc36679beac848f0f86c30c481bc2ad87` |
| `evidence/citron-brewser-boot-02.png` | 运行 1 二次截图（TICKS 75 + frame 1119） | `9fa950f3f6876705e355c889196846e4feeec503124bc2caf38b4e328fe09b03` |
| `evidence/citron-brewser-boot-03-run2.png` | 运行 2 复现截图（TICKS 48 + frame 697） | `18025734315b2da7796b2ad11fe594bfa179390701055670db4bb94b1f1e086a` |
| `evidence/citron-hbmenu-control-01.png` | hbmenu 对照（launchInit 失败屏） | `502b31e47f3af0b3975d92d2d11fda0a156440bf7942c87e0ed55f5186459dcf` |
| `evidence/logs/citron-brewser-run1.log` | 运行 1 完整日志（164,418 B） | `08d161eb9f13aff552129eaaf8bbe3b8c79b187429c055b0bab0dc8da309c527` |
| `evidence/logs/citron-brewser-run2.log` | 运行 2 完整日志 | `246f37597d3fda95c3b61f8bc4fed340de1a8df09fe38d190402dc579996ccf8` |
| `evidence/logs/citron-hbmenu-run.log` | hbmenu 对照日志 | `d1a96ceb60caed7081ec5b2fe4cd91d0f22c309bae1f34a1b0de4a6f51ba0a10` |
| `citron/Citron-msvc.zip` | 官方 nightly 原始资产 | `0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb` |
| `../../workspaces/web-01/brewser.nro`（复用 web-01 下载） | Brewser 预编译 NRO | `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13` |

## 10. 限制与未验证项

1. **输入**：未注入手柄/键盘输入，Brewser 输入映射（ZR 呼出键盘、B/X/Y 导航、摇杆滚动、L+R+Minus 退出）未验证。
2. **音频**：未验证（Brewser WebAudio、BGM 播放）。
3. **联网**：Citron BSD socket 为 STUBBED；Brewser catalogue/登录/WebSocket/HLS 在线能力未验证。
4. **WebGL 绘制质量**：仅验证上下文创建与 VERSION 字符串，未做像素级校验/复杂着色器验证；Three.js/PixiJS 等真实负载未测。
5. **Brewser 内部页面**（home/apps/settings/history/bookmarks 等）与工具栏交互未测；仅验证自写 `brewser://probe/` 页 + `autorunApp` 机制。
6. **离线 app 打包/安装**（Brewser 的 app 打包格式、SD 离线部署、存档位置）未测。
7. **长时间稳定性/性能**：仅跑约 20–30 s ×2；未做 30 min+ soak、未测帧率稳定性/内存增长。
8. **模拟器保真度**：未安装固件（硬编码 22.0.0-3.0 兼容值）；112 条 Maxwell 解码断言；NVIDIA Vulkan 与真机 Mesa Nouveau 路径不同 → **不能替代真机验收**。
9. **真机**：本轮未接触 Switch 硬件；Brewser 真机证据仍来自其官方 release notes（见 02-web.md）。

## 11. 结论与对 M4 的建议

- **结论：模拟器侧打通**。Citron Neo nightly `0237a9b88` 可完整运行 Brewser v0.1.131 预编译 NRO，HTML 页面脚本真实执行（Brewser `runPageScripts` 路径生效），JS 定时器/rAF/Canvas2D/localStorage 均正常，SD seed 完成，2/2 复现。web-01 在 Ryujinx 上的停滞是**环境问题**，不是 Brewser 缺陷。
- **版本锁定**：固定 Citron 资产 `Citron-windows-nightly-0237a9b88-x64-msvc.zip` 的 sha256（`0d2c9bf3…`）；运行后用日志版本串 `main-0237a9b88` 校验。
- **M4 开发循环**：可用 Citron + Brewser `make sdmc`（Brewser Makefile 的 SD 目标）做快速迭代；CI/冒烟三维校验：窗口标题 `brewser (64-bit)`、日志 `Loading brewser (01F5905036D20000)` + `Booting game`、`sdmc/switch/brewser/seed-fingerprint` 出现。
- **剩余阻塞**：① 真机验收（Atmosphère 1.10+ / hbmenu 完整内存模式）；② Brewser 私有 `@switch-web/runtime` 源码不可得；③ RPG Maker MV / TyranoScript 兼容层未验证（见 02-web.md 差距分析）；④ Citron GPL-3.0-or-later 仅作外部工具，不并入发布物；keys/firmware 不入库。

## 12. 复现步骤（命令级，已脱敏）

```bash
# 1) 下载并校验 Citron（代理 http://127.0.0.1:7897）
curl -L -x http://127.0.0.1:7897 -o Citron-msvc.zip \
  https://github.com/citron-neo/emulator/releases/download/2026-04-27/Citron-windows-nightly-0237a9b88-x64-msvc.zip
sha256sum Citron-msvc.zip   # 期望 0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb
# 2) 解压（Windows；git-bash 的 tar 不支持 zip）
powershell -NoProfile -Command "Expand-Archive -Path Citron-msvc.zip -DestinationPath citron -Force"
# 3) 用户既有 keys 复制到 %APPDATA%/citron/keys/（不打印内容）
# 4) 部署 SD：%APPDATA%/citron/sdmc/switch/{brewser.nro, hbmenu.nro, brewser/configs/config.json, brewser/shell/probe.html}
# 5) 启动（elevated shell 下经 runas 去提权）
#    launch-citron-brewser.cmd: cd /d <citron dir> && citron.exe -g <...>\brewser.nro
powershell Start-Process runas.exe -ArgumentList '/trustlevel:0x20000','C:\Users\ACETaffy\glx\launch-citron-brewser.cmd'
# 6) 截图窗口（标题含 'brewser (64-bit)'）并读取 %APPDATA%/citron/log/citron_log.txt
```

## 附录 A：probe.html 全文（2,672 B）

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>GALNX-WEB-PROBE-01</title>
<style>
body { background-color: #102030; color: #e8f0ff; margin: 24px; }
h1 { color: #77ccff; font-size: 40px; }
#static { font-size: 30px; color: #ffffff; }
#status { font-size: 30px; color: #ffd54f; }
#counter { font-size: 56px; color: #66ff66; }
#err { font-size: 18px; color: #ff8888; }
canvas { border: 4px solid #44aaff; background-color: #000000; margin-top: 12px; }
.box { width: 220px; height: 56px; background-color: #cc3333; margin-top: 10px; }
</style>
</head>
<body>
<h1>GALNX WEB PROBE 01</h1>
<p id="static">STATIC DOM TEXT OK</p>
<div class="box"></div>
<p id="status">JS: PENDING</p>
<div id="counter">TICKS 0</div>
<canvas id="c2d" width="480" height="200"></canvas>
<canvas id="cgl" width="480" height="120"></canvas>
<div id="err"></div>
<script>
(function () {
  function $(id) { try { return document.getElementById(id); } catch (e) { return null; } }
  var err = $('err');
  function fail(m) { try { if (err) err.textContent = err.textContent + m + ' | '; } catch (e) {} }
  try {
    window.onerror = function (m) { fail('onerror:' + m); };
    var status = $('status');
    if (!status) { fail('NO #status ELEMENT'); return; }
    status.textContent = 'JS: INLINE OK';
    try { document.title = 'GALNX-WEB-PROBE-01-JS'; } catch (e) { fail('title fail'); }
    var counterEl = $('counter');
    var n = 0;
    setInterval(function () {
      n = n + 1;
      if (counterEl) counterEl.textContent = 'TICKS ' + n;
    }, 250);
    var cv = $('c2d');
    if (!cv) { fail('NO c2d CANVAS'); return; }
    var ctx = cv.getContext('2d');
    if (!ctx) { fail('NO 2D CONTEXT'); return; }
    var t = 0;
    function draw() {
      t = t + 0.05;
      ctx.fillStyle = '#000000';
      ctx.fillRect(0, 0, 480, 200);
      ctx.fillStyle = '#00ff00';
      ctx.fillRect(10 + ((t * 80) % 380), 110, 70, 70);
      ctx.fillStyle = '#ffffff';
      ctx.font = '24px sans-serif';
      ctx.fillText('CANVAS 2D OK frame ' + Math.round(t * 20), 10, 40);
      if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(draw);
      } else {
        setTimeout(draw, 50);
      }
    }
    draw();
    try {
      localStorage.setItem('glxprobe', '1');
      fail('localStorage:' + localStorage.getItem('glxprobe'));
    } catch (e) { fail('localStorage FAIL:' + e); }
    try {
      var gl = $('cgl').getContext('webgl2') || $('cgl').getContext('webgl');
      fail('WebGL:' + (gl ? ('OK ' + gl.getParameter(gl.VERSION)) : 'NULL'));
    } catch (e) { fail('WebGL FAIL:' + e); }
  } catch (e) {
    fail('FATAL:' + e);
  }
})();
</script>
</body>
</html>
```

## 附录 B：config.json 与启动 wrapper

```text
sdmc/switch/brewser/configs/config.json: {"autorunApp":"brewser://probe/"}

C:\Users\ACETaffy\glx\launch-citron-brewser.cmd:
@echo off
cd /d "E:\Othergames\Nintendo Switch\Workspace\GalNX\workspaces\web-02\citron"
"citron.exe" -g "%APPDATA%\citron\sdmc\switch\brewser.nro"
```

- 说明：`autorunApp` 为 Brewser 工具栏配置字段（源码 `browser-toolbar.ts` `DEFAULT_CONFIG`/`loadConfig`），非空时 boot 后直接导航到该 URL；探针页因此可在启动后自动打开，无需输入操作。
