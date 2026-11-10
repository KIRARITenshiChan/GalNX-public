# task-7 Web 可行性小验证：Brewser 在 Ryujinx 上的冒烟实验（只读/无框架改动）

- 实验日期: 2026-10-29
- 执行: audit-web（GalNX 审计员，Web/JS 运行时集群）
- 任务: 下载并校验 Brewser 预编译 brewser.nro，在 Ryujinx Canary 1.3.265 上加载，用最小 HTML 页面（DOM+canvas+JS）验证实际能力
- verification_level: **not-verified**（目标能力——Brewser 在 Ryujinx 中执行 HTML 页面——未达成；本报告记录的是环境阻塞结论与对照证据）
- 结论一句话: **Ryujinx Canary 1.3.265 能加载并运行普通 homebrew NRO（nx-hbmenu v3.6.1、hb-appstore v2.3.2 均正常启动渲染），但加载 nx.js 系 NRO（Brewser v0.1.131 与上游 nx.js v1.0.0-beta.7）时稳定停滞在日志 `LoadGuestApplication: Loading as homebrew.` 之后，应用从不执行；该阻塞可复现（3 次 Brewser + 2 次 nx.js），根因未定位，真机能力未验证。**

## 0. 边界与声明

- 只做了下载/校验/启动/截图/读日志，不构建、不安装、不修改 Brewser 源码。
- 未读取、未外传任何商业游戏数据、模拟器密钥或固件（Ryujinx portable/system/ 下的 prod.keys/title.keys 仅确认存在，未读取内容）。
- 对 Ryujinx 的配置改动只有一处：临时把 `portable/Config.json` 的 `enable_discord_integration` 改为 false 做归因测试（后已**还原为原始文件** `Config.json.bak-web01`；另有一个 debug 日志实验备份 `Config.json.bak-web01-debug`，未删除，供复核）。实验结束后 Ryujinx 进程已全部关闭。

## 1. 资产下载与校验（实测）

| 资产 | 来源 URL | 大小 | sha256 | 校验结果 |
|---|---|---|---|---|
| brewser.nro | https://github.com/natureglass/Brewser/releases/download/v0.1.1.31/brewser.nro | 76,546,123 B | `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13` | 与 GitHub release asset digest、dist/checksums.txt 三方一致 |
| nxjs.nro（对照） | https://github.com/TooTallNate/nx.js/releases/download/v1.0.0-beta.7/nxjs.nro | 56,436,901 B | `602ced49d93afc1704c8dd14da199b151201cb9bcd55ce3b75738f5ae39637ae` | 与审计记录（beta.7 release asset 大小/内容）一致 |
| hbmenu.nro（对照） | https://github.com/switchbrew/nx-hbmenu/releases/download/v3.6.1/nx-hbmenu_v3.6.1.zip | 2,455,539 B（zip 1,249,201 B） | — | 解压后得到 hbmenu.nro |
| appstore.nro（对照） | https://github.com/fortheusers/hb-appstore/releases/download/v2.3.2/appstore.nro | 11,104,808 B | `de1ab28c4c142cafd45fb4bfef9ce560122d8aec063f5947982c759e3691e978` | — |

- Brewser release 元数据（GitHub API `/repos/natureglass/Brewser/releases/latest`，HTTP 200）：release id 389073004，tag `v0.1.1.31`，name "Brewser v0.1.131 - Game Engines, WebSockets & the Network Consent Model"，published_at 2026-09-15T11:44:46Z，created_at 2026-09-17T20:30:21Z，asset id 571065664，download_count 511。
- 下载方式：`curl -L -x http://127.0.0.1:7897`，HTTP 200，76,546,123 B，3.52 s（2026-10-29T14:04:57Z→14:05:02Z）。
- 本地副本：`Workspace/GalNX/workspaces/web-01/brewser.nro`（gitignore 忽略）。

## 2. Ryujinx 环境（实测）

- 路径：`E:\Othergames\Nintendo Switch\Ryujinx-canary\Ryujinx.exe`，FileVersion 1.3.265.0，ProductVersion `1.3.265+4e81a4c`，Launch Mode **Portable**，.NET 10.0.5，firmware 22.0.0，图形后端 **Vulkan**（NVIDIA RTX 4060 Laptop，驱动 v621.1.0.0），`memory_manager_mode=HostMappedUnsafe`，`enable_internet_access=false`，`enable_docked_mode=true`，`audio_backend=SDL3`。
- SD 卡根：`Ryujinx-canary/portable/sdcard`（默认 portable 布局）；日志目录：`Ryujinx-canary/portable/Logs/`（Ryujinx 只保留最近几个日志文件，旧文件会被清理——这是部分日志无法附上的原因）。
- **必须去提权启动**：本 agent 的 shell 是 elevated，直接 `Start-Process Ryujinx.exe` 会弹模态错误框：原文 **"Ryujinx is not intended to be run as an administrator."**（截图 `evidence/ryu-dialog-01.png`）。可行方式：`runas /trustlevel:0x20000 <wrapper.cmd>`（用户提供的 Run.bat 同款思路），wrapper .cmd 内用完整引号命令行 `"Ryujinx.exe" "<path>.nro"`；直接给 `runas` 传整串带空格参数会被拆散（日志 `The file was not found: 'Switch\Ryujinx-canary\...'`，见 `evidence/logs/attempt3-arg-split.log`）。
- 实际启动命令：
  - `powershell Start-Process runas.exe -ArgumentList '/trustlevel:0x20000','C:\Users\<user>\glx\launch-ryujinx-hbmenu.cmd'`（同类还有 launch-ryujinx-appstore.cmd / launch-ryujinx-nxjs.cmd）
  - wrapper 内容：`@echo off` / `cd /d "E:\Othergames\Nintendo Switch\Ryujinx-canary"` / `"E:\...\Ryujinx.exe" "E:\...\portable\sdcard\switch\<file>.nro"`
- 截图方式：`window_capture`（DWM thumbnail，不抢焦点），证据见第 8 节。

## 3. SD 卡布局与最小探针页（为 Brewser 准备）

Brewser 约定（来自其源码/文档，见 02-web.md 审计）：appRoot = `sdmc:/switch/brewser/`，profile 默认 `shell`，配置 `switch/brewser/configs/config.json` 的 `autorunApp` 可在启动时直接导航到指定 URL；页面从 `sdmc:/switch/brewser/shell/` 读取（HTML 请求先试 `<rel>.html`，再试 `<rel>/index.html`）。

已写入 SD 的内容（`portable/sdcard/switch/`）：

- `brewser.nro`（sha256 8ce31f5b…，76,546,123 B）
- `brewser/configs/config.json` = `{"autorunApp":"brewser://probe/"}`
- `brewser/shell/probe.html`（自写探针，未粘贴到本报告；关键内容：标题 GALNX WEB PROBE 01；静态 DOM 文本 "STATIC DOM TEXT OK"；红色 CSS box；`#status` 初始 `JS: PENDING`；`#counter` 初始 `TICKS 0`；2D canvas `#c2d` 480×200 + WebGL canvas `#cgl` 480×120；inline script 设 `JS: INLINE OK`、`setInterval(250ms)` 计数、rAF 2D 动画、localStorage 读写探针、WebGL2/WebGL getContext 探针、window.onerror 把错误写进 `#err`）
- `brewser/logs/` 目录（空）

**注意**：`probe.html` 不在 Brewser 的 romfs 中，seed walker 不会覆盖；`config.json` 为 missing-only 写入，也不会被覆盖（依据 02-web.md 审计中 browser-profile.ts / browser-toolbar.ts 源码取证）。

## 4. 实验时间线（全部为实测，时间为 2026-10-29 本地 UTC+8）

| # | 时间 | 加载对象 | 方式 | 结果 |
|---|---|---|---|---|
| 1 | 22:10:10 | brewser.nro | runas wrapper | 进程启动，日志 `Loading as homebrew.` 后停滞；~127 s 后日志出现 Ryujinx 内部 Discord/HLE 异常（见 5-c） |
| 2 | 22:12:56 | brewser.nro | 同上（事先把 Config.json 的 `enable_discord_integration` 改 false） | 完全相同：停滞 + 00:02:08.442 同一 Discord 异常栈 |
| 3 | 22:16:36 | nxjs.nro（上游 nx.js beta.7） | 同上 | 相同停滞（`Loading as homebrew.` 后无任何后续日志、无 guest 服务日志） |
| 4 | 22:19:36 | hbmenu.nro（nx-hbmenu v3.6.1） | 同上 | **成功**：`GetNpdm`→`LoadNsos`→`Application Loaded`，GUI 切换到游戏视图（窗口标题变为 `Ryujinx 1.3.265 / v3.6.1 / (010000000000100D) (64-bit)`），画面显示 "Error: launchInit() failed. Press the + button to exit."（hbmenu 直接以 NRO 启动时的预期行为） |
| 5 | 22:22:34 | appstore.nro（hb-appstore v2.3.2，自带 ASET 资产 11.1 MB） | 同上 | 加载日志正常（`Application Loaded ... v2.3.2`），画面渲染出红色启动画面（`evidence/ryu-appstore-known-good-01.png`） |
| 6 | 22:24:25 | nxjs.nro（还原原始 Config.json 后复测） | 同上 | 稳定复现停滞（41 行日志，末行 `Loading as homebrew.`；`evidence/logs/ryu-nxjs-beta7-stall-cleanconfig.log`） |

- Brewser 停滞时：`sdcard/switch/brewser/` 始终只有我们写入的 `config.json`、`probe.html`、空 `logs/` —— 没有 `seed-fingerprint`、没有 romfs shell 文件被 seed 出来，说明 **Brewser 主程序从未执行**。
- 停滞时主窗口保持游戏列表（P5R 图标，底部 "1/1 游戏加载完成"），同进程另有 2 个隐藏 AvaloniaSimpleWindow（1898×941）从未 visible；Ryujinx CPU 低占用（约 10–13 s/2 min，不是 JIT/渲染负载），窗口 Responding=True。
- 另一次（22:21:14）在 Config.json 打开 `logging_enable_debug/trace/fs_access_log` 后启动 nxjs.nro：**日志连 `LoadGuestApplication` 都不再出现**（末行 `UI LoadCompatibility: Compatibility CSV loaded.`，日志文件 mtime 停在启动后 1.5 s），说明 **开启 debug/trace 日志会破坏命令行参数加载路径**（或使其死锁）；恢复原始 Config.json 后立刻恢复正常。此为 Ryujinx 侧环境怪癖，记录备查（`evidence/logs/ryu-debug-config-noarg.log`）。

## 5. 关键日志原文

### 5-a. 正常 homebrew 加载（hbmenu v3.6.1，`evidence/logs/ryu-hbmenu-known-good.log` 片段）
```
00:00:00.453 |N| Application LoadGuestApplication: Loading content archive from 'E:\...\sdcard\switch\hbmenu.nro'.
00:00:00.453 |I| Application LoadGuestApplication: Loading as homebrew.
00:00:00.458 |W| Loader GetNpdm: NPDM file not found, using default values!
00:00:00.847 |I| Ptc Initialize: Initializing Profiled Persistent Translation Cache (enabled: False).
00:00:00.849 |I| Application ParseCapability: Application requested cores with index range 0 to 2
00:00:00.850 |I| Loader LoadNsos: Loading image 0 at 0x0000000008500000...
00:00:00.994 |I| Loader Start: Application Loaded: Firmware Application <Unknown Name> v3.6.1 [010000000000100d] [64-bit]
00:00:03.609 |S| HLE.OsThread.47 ServiceAm GetAppletResourceUserId: Stubbed. {appletResourceUserId: 1}
...
```

### 5-b. nx.js / Brewser 停滞（`evidence/logs/ryu-nxjs-beta7-stall-cleanconfig.log` 末尾）
```
00:00:00.359 |N| Application LoadGuestApplication: Using Firmware Version: 22.0.0
00:00:00.359 |N| Application LoadGuestApplication: Loading content archive from 'E:\...\sdcard\switch\nxjs.nro'.
00:00:00.359 |I| Application LoadGuestApplication: Loading as homebrew.
```
（之后无任何行；hbmenu/appstore 会在 5–15 ms 内打出 `GetNpdm`，nx.js/Brewser 没有 → 停滞发生在 Ryujinx 加载器内部、guest CPU 启动之前。）

### 5-c. Brewser 两次运行 ~127 s 后的 Ryujinx 内部异常（`evidence/logs/attempt4-discord-crash.log`）
```
00:02:07.556 |E| Application Task<VoidTaskResult>: Unhandled exception caught: Ryujinx.Common.RyujinxException: The HLE Process map did not have a process with ID 0. Are you missing firmware?
   at Ryujinx.HLE.Loaders.Processes.ProcessLoader.get_ActiveApplication() in .../ProcessLoader.cs:line 35
   at Ryujinx.Ava.Systems.DiscordIntegrationModule.Use(Optional`1 titleId) in .../DiscordIntegrationModule.cs:line 86
   at Ryujinx.Ava.Systems.DiscordIntegrationModule.<>c.<Initialize>b__20_0(...) in .../DiscordIntegrationModule.cs:line 54
   at Ryujinx.Common.ReactiveObject`1.set_Value(T value) in .../ReactiveObject.cs:line 41
   at Ryujinx.HLE.Loaders.Processes.ProcessLoader.LoadNxo(String path) in .../ProcessLoader.cs:line 217
   at Ryujinx.HLE.Switch.LoadProgram(String fileName) in .../Switch.cs:line 163
   at Ryujinx.Ava.Systems.AppHost.LoadGuestApplication(...) in .../AppHost.cs:line 854
   at Ryujinx.Ava.UI.ViewModels.MainWindowViewModel.LoadApplication(...) in .../MainWindowViewModel.cs:line 1782
   at Ryujinx.Ava.UI.Windows.MainWindow.CheckLaunchState() in .../MainWindow.axaml.cs:line 392
```
- 两次 Brewser 运行都在启动后 ~127 s（127.1 / 127.4 s）出现同一栈；把 `enable_discord_integration` 设为 false 后依然出现（说明该配置项未阻止 DiscordIntegrationModule 初始化，或异常另有确定性触发点）。
- 上游 nx.js.nro 的那次运行没有等到该异常（观察约 160 s 后手动结束）——该异常是否为停滞的后果而非原因是**未定**。
- 结论边界：此异常是 **Ryujinx 自身**（Ava GUI + Discord 集成 + HLE 进程表）在 homebrew 加载路径上的内部错误，不能归因于 Brewser。

## 6. NRO 文件结构对比（本地二进制解析，供根因定位参考）

| 文件 | 大小 | "ASET" 资产偏移 | 0x18 处 NRO size | 0x24/0x2c/0x34 段尺寸字段 | 结果 |
|---|---|---|---|---|---|
| hbmenu.nro | 2,455,539 (0x2577f3) | 0x247000 | 0x247000 | 0x1b0000 / 0x7f000 / 0x18000 | 正常加载 |
| appstore.nro | 11,104,808 (0xa97228) | 0xa8a000 | 0xa8a000 | 0x6fd000 / 0x293000 / 0xfa000 | 正常加载 |
| nxjs.nro | 56,436,901 (0x35d28a5) | 0x3507000 | 0x3507000 | 0x2a26000 / 0x98c000 / 0x155000 | 停滞 |
| brewser.nro | 76,546,123 (0x490004b) | 0x360b000 | 0x360b000 | 0x2a6b000 / 0xa4a000 / 0x156000 | 停滞 |

- 四者头部同构（NRO magic 在 0x10，前置 0x10 字节 "HOME/BREW" 前缀），都带 ASET 资产；两个**能加载**的对照 NRO 也带 ASET（appstore 11.1 MB 也证明了"带资产/十 MB 级 NRO"本身不是问题）。
- 差异集中在**代码段规模**：nx.js/Brewser 的 0x24 字段约 44 MB（0x2a26000/0x2a6b000），已知-good 对照为 1.7 MB/7.3 MB。可疑方向：Ryujinx 1.3.265 的 homebrew NRO 加载路径对超大代码段/NRO 的处理（例如分配/映射或 NSO 提取路径），本实验未能进一步定位。
- 字符串检索：nxjs.nro/brewser.nro 中未见 NACP magic（ASCII "NACP"），因此"附带 NACP 导致停滞"的假设**未被证据支持**，暂不列入。

## 7. 未验证 / 未完成

1. **Brewser 运行时能力全部未验证**（V8 JIT、Skia、WebGL/WebGL2、WebAudio、DOM/CSS 管线、HTML 页面脚本执行、autorunApp 配置、SD 存档路径、输入映射）——实验没跑起来，全部属于"未验证"，不得视为可用。
2. 停滞的**根因未定位**（Ryujinx 1.3.265 对 nx.js 系 NRO 的加载器行为）。未做的排查方向：Ryujinx 源码比对 1.3.265 的 `ProcessLoader.LoadNxo`；换 Ryujinx 版本（如 1.1.x / canary 更早版本）；换其他模拟器（yuzu 系/suyu 等，均未在本机验证）；用真机（CFW + hbmenu）验证 Brewser。
3. **GUI 文件菜单加载方式未试**（需要输入注入、会抢焦点，按"不打扰用户桌面"原则未做）。
4. Brewser 的 `autorunApp` 配置是否生效**未验证**（应用未执行）。
5. 未验证 Ryujinx 的 GPU/WebGL 在本机是否能给 Brewser 提供可用的 Mesa/Nouveau 等价路径（Ryujinx 本身走 Vulkan，Brewser 需要 GL ES 3.2；真机上由 Mesa Nouveau 提供，模拟器下未知）。
6. 本报告的"真机可用"信息仅来自 **Brewser README/release notes 声称**，无真机证据。

## 8. 证据清单（全部在 `Workspace/GalNX/workspaces/web-01/`；该目录被 .gitignore 忽略）

- `brewser.nro`（sha256 8ce31f5b…）
- `alt-nxjs/nxjs.nro`（sha256 602ced49…）
- `alt-hbmenu/hbmenu.nro`（nx-hbmenu v3.6.1）
- `alt-appstore/appstore.nro`（hb-appstore v2.3.2，sha256 de1ab28c…）
- `probe.html` 同步副本见 SD 路径（`.../portable/sdcard/switch/brewser/shell/probe.html`）
- 截图：
  - `evidence/ryu-dialog-01.png` — "Ryujinx is not intended to be run as an administrator." 模态框
  - `evidence/ryu-loading-01.png` — Brewser 加载停滞时主窗口（游戏列表）
  - `evidence/ryu-stuck-discord-off-01.png` — 关闭 Discord 集成后的停滞界面
  - `evidence/ryu-console-hidden-01.png` — 隐藏控制台窗口（只有 C:\> 提示符）
  - `evidence/ryu-hbmenu-known-good-01.png` — hbmenu 成功运行画面
  - `evidence/ryu-appstore-known-good-01.png` — appstore 成功运行画面
- 日志：
  - `evidence/logs/attempt3-arg-split.log` — runas 参数被拆散的失败
  - `evidence/logs/attempt4-discord-crash.log` — Brewser 停滞 + 127 s Discord 异常栈
  - `evidence/logs/ryu-debug-config-noarg.log` — debug 日志导致的参数不处理怪癖
  - `evidence/logs/ryu-hbmenu-known-good.log` — hbmenu 正常加载全量日志
  - `evidence/logs/ryu-appstore-known-good.log` — appstore 正常加载全量日志
  - `evidence/logs/ryu-nxjs-beta7-stall-cleanconfig.log` — nxjs 停滞（干净配置复测）

## 9. 对 GalNX / M4 的结论与建议（本次实验直接支撑）

1. **结论：以本机 Ryujinx Canary 1.3.265 作为 M4 "Web 路线可行性验证"的工具是阻塞的**——与 Brewser 质量无关，是 nx.js 系 NRO 在该模拟器上的加载问题；**不能**据此判定 Brewser/Web 路线不可行，也**不能**据此判定可行。
2. M4 的 Web 验证必须换路径（按优先级）：
   - 真机（CFW + hbmenu，按 Brewser README 要求 Atmosphère 1.10+，完整内存 application mode）——唯一权威路径；
   - 换 Ryujinx 版本/其他模拟器（需单独做"NRO 加载"冒烟，用 hbmenu/appstore 做对照物）；
   - 若必须在当前 Ryujinx 上推进：把"nx.js 系 NRO 加载停滞"作为独立技术问题单独立项（Ryujinx 版本行为差异/加载器差异），不要混入 Brewser 评估。
3. 本实验同时证明：**Ryujinx portable + runas 去提权 + sdcard/switch/ 放 NRO + window_capture 截图 + Logs 读日志**这套验证流程本身可用，可直接复用于后续其他 homebrew NRO（hbmenu/appstore 是可复用的"加载链路健康检查"对照物）。
4. 版本/校验值记录：Brewser v0.1.131（v0.1.1.31）brewser.nro sha256 `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13`，大小 76,546,123 B——已本地校验，可作为后续真机验证的同一二进制。
