# P4 真机 runbook — NS1 安装与验收（首款垂直试点）

> 状态：**待用户设备（Nintendo Switch 1，已装 CFW）**。本文件是 P4 的执行清单：按顺序做完并勾选，每步附「证据采集」要求。
> **v1.3 更新**：A5（日文 1.0.4，退出修复）与 **A6（中文 1.0.5，汉化版）** 均已构建 + 模拟器级验收通过，均待真机复验；A6 的安装与验收见 §10。
> **v1.4 更新**：A7（中文 1.0.6，中文 OP）与 **A8（中文 1.0.7，手柄映射 v2 + 三个真机 bug 修复）** 已构建 + 模拟器级验收通过；当前建议直接装 **A8**（见 §11），A5/A6/A7 已被取代（同 TitleID 互相覆盖）。patch G 内容见 `docs/builds/013-k2nx-controller-input-v2.md`。
> **v1.5 更新**：**A9（中文 1.0.8）** = A8 + **patch H**（R 肩键 = 按住 Ctrl 快进、左摇杆滚轮方向修正）+ 封面图标（`examples/pilot01/icon-cover.jpg`）；已构建 + 结构校验 + Citron 首启冒烟 PASS，**当前建议直接装 A9**（见 §11，A5–A8 同 TitleID 被取代）。patch H 内容见 `docs/builds/014-k2nx-input-tweaks.md`。
> 上游结论：模拟器（Citron Nightly `0237a9b88`）侧 A3 自包含 NSP 已验收通过（启动 / 手柄推进 / 工程化复现），见 `docs/pilot/P2-acceptance.md`、`docs/pilot/P3-pipeline.md`；真机侧要验证的是**同一份 NSP 在真实硬件与真实手柄上的行为**。

## 0. 目标与验收标准

真机 NS1 上：

1. 从 HOME 菜单**直接启动** Haruno（=A3 自包含 NSP 安装成功、签名绕过正确）；
2. 首次启动自动解包内嵌 payload（2.87 GB）到 SD，随后 autostart 进标题；
3. **物理手柄**能推进剧情（RIGHT+A 进入正文、A 翻页）；
4. 能**用手柄完成存档 / 读档**（A9 起为默认映射：**+=SAVE 面板、Y=LOAD 面板、-=退出确认、B=返回、X=自动、R 按住=Ctrl 快进、左摇杆上下=滚轮**；触摸亦可）；
5. 音频有声、帧率可接受；
6. 二次启动走 marker 跳过解包（快启）。

## 1. 前置条件

| 项 | 要求 | 说明 |
| --- | --- | --- |
| 设备 | NS1（Erista / Mariko 均可） | 用户设备 |
| CFW | Atmosphère ≥ 1.12.1 | 计划 v1.0 记录：AMS 1.12.1 支持到 FW 23.0.0 |
| sigpatches | 与 AMS / FW 版本匹配 | 未签名 homebrew NSP 必需（不匹配会报 「无法启动软件」） |
| SD 卡 | 建议 exFAT，空闲 ≥ 8 GiB | A5 NSP 2,906,138,328 B + 解包 2,870,635,309 B ≈ 5.6 GiB |
| 安装器 | DBI（推荐 MTP）或 Goldleaf | DBI 无明确 LICENSE，**不入库、不分发**，用户自备 |
| 数据线 | USB-C 数据线 | DBI MTP 安装 |
| 电脑 | Windows + 读卡器（可选） | 拷 NSP / 校验哈希 / 取日志 |

**NSP 产物（本机唯一来源，A5 = 手柄存档热键 + 退出修复）**：`E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-A5-010047410000A000.nsp`
- 大小 2,906,138,328 B，sha256 `f179f0a20b9ede113231a7bfd0046180a8b90d5408745fbcc73520d73ec3b188`
- PROVENANCE：同目录 `.nsp.PROVENANCE.json`（14,009 B，sha256 `872c4421dab16a599a8b07ddc2c122f2b54e128feec3333837c13bb10ad9734f`）
- TitleID `010047410000A000`（base 0x2000 对齐，合规）、NACP name `Haruno`、version `1.0.4`（version_code 65540）
- 引擎补丁：`D-virtual-mouse-dpad` + `E-controller-ui-saveload` + `F-close-exit`（退出崩溃修复，见 `docs/builds/011-k2nx-exit-crash-fix.md`）
- `galnx package nsp verify`：19 checks / 18 ok / 1 warn（`verify.signature` = 未签名 homebrew 预期）
- ⚠️ 历史产物勿用：A3（version 1.0.2）没有手柄存档热键；A4（version 1.0.3）有手柄存档热键但**退出会崩溃**（Error Code 2-0000）。真机请用 **A5**。
- ⚠️ 编号说明：本章步骤编号 A1–A6 指「准备动作」，产物代号 A3/A4/A5 指 NSP 版本，两套编号互不相关。

## 2. 准备 SD 卡与 CFW

- **A1 记录环境**：进 CFW 后截图「系统设置 → 主机 → 系统更新」页（显示 AMS/FW 版本），或记录 Hekate 启动页版本号。→ 证据 E4
- **A2 放置 sigpatches**：按所用 AMS 包的说明放 `/atmosphere/exefs_patches/`（含 ES/FS/NIM 补丁）与 `/bootloader/patches.ini`（如包内含）。
- **A3 拷入 NSP**：`sdmc:/switch/galnx/Kirikiroid2-NX-A5-010047410000A000.nsp`（目录可自建）。
- **A4 校验哈希**：电脑读卡器 / DBI 里核对该 NSP 的 size + sha256（与第 1 节 A5 数值一致才继续）。→ 证据 E3
- **A5 安装**：DBI → 运行 → `MTP`（或 `Browse SD`）→ 选中 NSP → `Install` → 目标 **SD 卡**。安装完成后 DBI 显示 title id `010047410000A000`（若装着旧版，先卸载再装，避免混版）。
- **A6 确认图标**：回 HOME 菜单，出现 `Haruno` 图标（NACP name），大小约 2.8 GiB。

## 3. 首次启动（核心验收）

1. HOME 菜单选中 `Haruno` → **A** 启动；
2. 观察屏幕：黑屏若干秒 → （内部）解包 → **autostart** → 标题画面；
3. 计时：从按下 A 到标题出现的时间（模拟器参考：解包 14.4 s + 启动到 title 约 38 s；真机 SD 顺序读 2.7 GB 预计 40–120 s，总时长可能 1–3 min，**首启慢是预期**）。

**预期日志**（`sdmc:/switch/kirikiroid2/k2s_log.txt`，启动后用 DBI 拷出）：
```
[GALNX] free space check ok: <N> MiB free for a 2737 MiB payload
[GALNX] first boot: copying 23 payload file(s) to sdmc:/kirikiri/haruno
[GALNX] payload copy finished: 23 copied, 0 kept, 0 failed, 2737 MiB total
[GALNX] autostarting game from /kirikiri/haruno/data.xp3
...
Scenario loaded : title.ks
```

**失败分支**：

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 「free space check failed」/ 直接退出 | SD 空闲 < 2.87 GB+256 MiB | 清理 SD 重试 |
| 一直黑屏，无 `k2s_log.txt` | 引擎没启动：NSP 安装不完整 / sigpatches 不匹配 | 重装 NSP；检查 patches |
| 报「无法启动软件」(0x…) | 签名方案不匹配 | 换匹配 AMI/FW 的 sigpatches |
| 解包到一半失败 | SD 写入错误/空间不足 | 重试（幂等：已拷贝文件按大小跳过） |
| 解包完卡住不进标题 | 检查 k2s_log 末行 | 记录日志，回到 P2 排查 |

**证据**：解包过程录屏或关键帧照片（E2）、首启后 k2s_log.txt + k2s_boot.txt（E1）、`sdmc:/kirikiri/haruno` 文件清单（应 23 文件 / 2,870,635,309 B，含 14 个 xp3 + haruno.cf + Kirikiroid2Preference.xml + plugin/ 7 个 tpm）（E3）。

## 4. 手柄验收

标题菜单顺序（KAG3 菜单，横向 7 项）：`はじめから / ロード / クイックロード / コンティニュー / コンフィグ / スペシャル / 終了する`。

- **B1 进正文**：初始选中「ロード」；按 **方向键/D-Pad RIGHT**（或左摇杆右）→ 高亮「はじめから」→ 按 **A** 确认 → 进 `start.ks` → 正文。
  - ⚠️ **不要按 LEFT**：初始 MapReg=0，按 LEFT 会落到第 7 项「終了する」并退出游戏（P2 实测）。
  - ⚠️ 初始「ロード」直接按 A 可能无反应（无存档时），属预期。
- **B2 推进**：**A** 翻页；**B** 返回/菜单（本作菜单需触摸或虚拟鼠标，见 B3）；**X** = space（备选推进）。
  - 说明：手柄键→guest 的映射由 NSP 内置 `Kirikiroid2Preference.xml` 提供（A→VK_RETURN 13、B→VK_ESCAPE 27、X→VK_SPACE 32、方向 437–440→37–40），**不需要用户做任何配置**。
- **B3 存档/读档（两条路，任选其一；A5 起手柄可独立完成）**

  **路线 1：手柄热键（推荐，无需触摸）** —— A5 内置 patch D/E：

  | 功能 | 手柄键 | 说明 |
  | --- | --- | --- |
  | 存档 + 系统存档 | **L** | 直接存到槽 1（`savedata001.bmp`），不弹任何对话框 |
  | 打开 LOAD 界面 | **R** | 原生 LOAD 界面，槽位列表 |
  | 打开 SAVE 界面 | **PLUS** | 原生 SAVE 界面 |
  | 直接读槽 10 | **ZR** | 跳过界面直接读档 |
  | 只做系统存档 | **ZL** | 一般不需要手动用 |
  | 虚拟鼠标开关 | **Y** | 打开后画面中央出现鼠标箭头 |
  | 移动光标 | **D-Pad** | 每次 24 px；闲置约 1 s 会淡出，再按方向键即恢复 |
  | 左键点击 / 右键 | **A / B** | 光标模式下才是点击；非光标模式 A 仍是「推进」 |

  存档步骤：正文中按 **PLUS** → 看到 SAVE 界面 → **Y** 开光标 → D-Pad 把光标移到某个空槽（槽位网格两列 ×5 行/页，右侧 01–20 是页码）→ **A** 点击该槽 → 检查屏幕出现槽位缩略图 + 标题 + 日期。
  读档步骤：重启游戏 → 标题画面按 **R** → LOAD 界面 → **Y** 开光标 → 移到刚存的槽 → **A** → 画面应回到存档点那句文本。
  快速验证：正文中按 **L** 直接存档，重启后按 **ZR** 直接读回槽 10。

  **路线 2：触摸（真机可用）**：右下角抽屉把手 → K2S 抽屉 → `GAME MENU` 打开游戏 TJS 菜单（本作未注册 `Window.menu`，此入口在本作上为空）/ 或用 `MOUSE` 打开虚拟光标再点；触摸直接点槽位即可。
  模拟器侧只能用路线 1（Citron 的鼠标/触摸注入不可靠，见 `docs/pilot/saveload-acceptance.md` §6）。

  验证落盘：`sdmc:/kirikiri/haruno/savedata/` 下应出现 `savedata<NNN>.bmp`（编号 = 页码×10 + 槽位，如「01 01」= `savedata010.bmp`，约 45 KB）与 `system.bmp`（约 1 KB）→ 拷出目录清单 + 哈希（E3）。

- **B4 热键**：A5 起 `L` / `R` / `PLUS` / `ZL` / `ZR` / `Y` 已被 patch E 占用（见 B3 表），`X` 为 patch F 的退出诊断入口（会弹「ゲームを終了しますか？」）。计划里的 `L+R+PLUS` 组合热键**仍未实现**（当前是分键），记为后续增强项，不阻塞 P4。
- **B5 退出（patch F 验收，本轮新增）**：正文任意处按 **X**（或走 K2S 抽屉电源键）→ 弹「ゲームを終了しますか？」→ 光标移到「はい」→ **A**。期望：进程正常退出回 HOME，**不出现** Error Code 2-0000 / `Member "SystemObj" does not exist`。模拟器侧同路径已通过（`docs/builds/011-k2nx-exit-crash-fix.md` §9）。
- **B6 读档→退出组合**：读档进正文后直接退出（B5），确认退出不依赖存档/解包状态。

## 5. 音频与性能

- **音频**：标题 BGM、点击音、正文语音应可闻；`k2s_log.txt` 里应有 `Sound Driver/Device found : ...`。
- **性能**：观察正文翻页、场景切换是否流畅；无明显卡顿即通过（K2NX 无 FPS overlay，必要时录屏 30 s 目测）。
- **内存**：如出现崩溃/退出，记录退出码与 k2s_log 末尾。

## 6. 证据采集清单（P4）

| 级别 | 内容 | 采集方式 |
| --- | --- | --- |
| E4 | CFW/AMS/FW 版本、sigpatches 来源与版本、K2NX pin `e96b6034` | 截图 + 备注 |
| E3 | NSP size + sha256；解包目录 23 文件/2,870,635,309 B；savedata 文件哈希 | 读卡器 / DBI MTP |
| E2 | HOME 图标、首启解包完成、标题画面、手柄推进正文、存档菜单、读档后画面 | 截图（真机截图 = 系统截图键） |
| E1 | `k2s_log.txt`、`k2s_boot.txt` | DBI MTP 拷出 |

归档到 `docs/milestones/evidence/P4-*`（仓库只收结论 + 关键截图；完整数据留本机）。

## 7. 回滚 / 卸载

1. 卸载 NSP：DBI → 已安装 title 列表 → 删除 `010047410000A000`；或系统设置 → 数据管理。
2. 清理运行数据：删 `sdmc:/kirikiri/`（2.87 GB）与 `sdmc:/switch/kirikiroid2/`（marker/autostart/日志）。
3. CFW 异常时：用 Hekate 的备份还原（升级前务必备份）。

## 8. 已知限制与预期（真机）

| # | 限制 | 影响 / 预期 |
| --- | --- | --- |
| L1 | ~~中文（xmoe）不可用~~ → **已解决（v1.3 / A6）** | v0.1 的结论（Windows DLL 注入不可移植）只适用于原注入补丁；现改用公开汉化源码重打包 XP3（零引擎改动），A6 = 中文自包含 NSP，Citron 中文标题/正文已 PASS；真机待复验 |
| L2 | K2NX 许可 NOASSERTION | 产物仅本机自用、不可分发（R11） |
| L3 | 未签名 homebrew | 必须 sigpatches；nstool 的 `Signature: FAIL` 是预期 |
| L4 | 首启解包耗时 | 真机 SD 慢，1–3 min 属正常；二启走 marker 快启 |
| L5 | 存档固定位置 | `sdmc:/kirikiri/haruno/savedata`，清理 SD 前务必备份 |
| L6 | 模拟器侧触摸/鼠标注入不可用 | 已定位并绕过：guest 侧 ADV 层不消费触摸，Citron 渲染子窗口又是独立 HWND，注入不可靠 → 模拟器验收统一走「手柄 + 虚拟光标」；真机触摸直接可用（见 `docs/pilot/saveload-acceptance.md` §6） |
| L7 | 存档热键绑定本作 | patch E 调用的是 BASE ADV SYSTEM 的 `MainObj` API；换游戏需改表达式（`docs/builds/010` §2.2 / §6 E6） |
| L8 | `GalNXLog` 写 SD | 每次按键向 `sdmc:/galnx-input.log` 追加一行（实验取证用），正式发布应移除 |
| L9 | `X` 是诊断热键 | patch F 把 X 映射到游戏自身的退出确认（`MainObj.onCloseQuery(true)`），误触会弹退出框；正式发布前移除该映射 |
| L10 | ESC 路径仅源码级修复 | `MainWindow.tjs` 读 `this.minimized` 的路径在标题画面未触发，patch F 已补兼容成员但未端到端复现；真机若遇 ESC 崩溃请记录日志 |

## 9. 验收检查表

- [ ] A1–A6 准备完成（CFW 版本、sigpatches、**A5 或 A6** NSP 安装（同 TitleID，二选一）、HOME 图标）
- [ ] 首启：解包 23 文件 → autostart → 标题（附 k2s_log）
- [ ] 手柄：D-Pad RIGHT + A 进入 start.ks → 正文；A 翻页（A8/A9 映射；A5/A6 同 A 推进）
- [ ] 存档：正文按 **+（PLUS）** → SAVE 面板（A8/A9）；A5/A6 为 PLUS→K2S 菜单；Y 光标或触摸选槽 → A → 槽位显示缩略图/标题/日期；`savedata/` 出现 `savedata<NNN>.bmp`
- [ ] 读档：重启或正文按 **Y** → LOAD 面板（A8/A9；A5/A6 为 R 键）→ 选该槽 → A → 画面回到存档点 → A 能继续推进
- [ ] 快捷热键：正文按 **L** 直存、重启按 **ZR** 直读（可选，辅助验证）
- [ ] 退出：**-（MINUS）** →「结束游戏吗？」→ 是 → 回 HOME，无 Error Code 2-0000 / SystemObj（A9 = patch F+G 验收；A5 为 X 键）
- [ ] 音频：标题 BGM / 语音可闻
- [ ] 二启：marker 跳过解包（`already extracted`）
- [ ] 证据归档 `docs/milestones/evidence/P4-*` + 更新 `docs/pilot/README.md` 判定表

## 10. A6 中文版安装与验收（v1.3 新增）

> 结论先行：CN 内容已做为 **A6 自包含 NSP** 构建完成（`Kirikiroid2-NX-A6-CN-010047410000A000.nsp`，2,906,318,552 B，sha256 `1941a317baea186bb6f8ac9cdd8e9d11d2125a25abfcc32f83a14339a70a49d7`），Citron 上「首启解包 → 中文标题菜单 → 中文正文」全通；真机待复验。内容来源、XP3 重打包与四个编码坑见 `docs/builds/012-k2nx-cn-content.md`。

### 10.1 安装（与 A5 二选一）

1. A6 与 A5 **同一 TitleID**（`010047410000A000`）→ 装 A6 会覆盖 A5，二者不能并存；切换 = 重装。
2. 方式 A（推荐，上传即安装）：Switch 打开 **DBI → Run FTP server**，记下屏幕上的 `IP:端口`；本机执行
   `python E:/galnx-build/pilot-01/p5/ftp_upload_a6.py`（脚本内默认 `192.168.31.254:5000`，若变化先改脚本两行）。约 2.9 GB / 7–8 分钟。
3. 方式 B：NSP 拷到 SD 卡 `switch/`，DBI → Install from SD。
4. 首次启动解包 23 文件（2737 MiB）到 `sdmc:/kirikiri/haruno/`，1–3 min；二次启动走 marker 快启。

### 10.2 验收检查表（A6 中文）

- [ ] HOME 图标 `Haruno CN`；首启解包完成后进中文标题菜单（开始游戏 / 读档 / 快速读档 / 继续游戏 / 游戏设置 / 鉴赏模式 / 结束游戏）
- [ ] 中文字形正常（romfs 自带 `DroidSansFallback.ttf`），无豆腐块/乱码
- [ ] 手柄：RIGHT + A → `start.ks` → 中文正文（「我拼命地伸出了手。」等）；A 翻页
- [ ] 存读档：**PLUS**（SAVE）/ **R**（LOAD）→ Y 光标 + D-Pad + A 完成存档与读档
- [ ] 退出：**X** →「ゲームを終了しますか？」→ はい → 回 HOME，无 `Error Code 2-0000` / SystemObj（patch F 在 A6 中同样生效）
- [ ] 音频：标题 BGM / 语音可闻；二次启动 marker 命中
- [ ] 证据：系统截图 + `k2s_log.txt` 拷出 → 归档 `docs/milestones/evidence/P4b-*`，并在 `docs/pilot/saveload-acceptance.md` 记录

已知未覆盖：OP 影片/字幕仍为日文（`movie_chs.xp3` 未纳入，见 012 §9 L2）；只验证了序章连续对白，长流程 / 选项分支 / 鉴赏模式未遍历。

## 11. A9 中文版安装与验收（v1.5 更新，当前推荐版本）

> 结论先行：A9 = A8 的 CN 内容 + patch G 映射 v2 + **patch H**（R 按住 = Ctrl 快进、左摇杆滚轮方向修正）+ 封面图标；模拟器端到端验收全通（h1 + NSP 首启冒烟），真机待复验。

### 11.1 安装

1. **与 A5/A6/A7/A8 同一 TitleID**（`010047410000A000`）：装 A9 会覆盖旧版，装回旧版同理；不能并存。
2. 方式 A（推荐，上传即安装）：Switch 打开 **DBI → Run FTP server**，执行 `python E:/galnx-build/pilot-01/p7/ftp_upload_a9.py`（默认 `192.168.31.254:5000`，若屏幕 IP 不同改脚本两行）。约 2.87 GB / 7–8 分钟（2026-10-30 22:17–22:25 已按此方式上传 A9：`UPLOAD_DONE … 2870911192 in 469.5 s`，≈5.85 MiB/s，DBI 上传完成即自动安装）。
3. 方式 B：NSP 拷贝到 SD 卡 `switch/`，DBI → Install from SD。
4. 首次启动解包 23 文件（2704 MiB）到 `sdmc:/kirikiri/haruno/`，约 1–3 min；二次启动走 marker 快启（`already extracted`）。

**产物**：`E:/galnx-build/pilot-01/p7/out/Kirikiroid2-NX-A9-CN-010047410000A000.nsp`
- 大小 **2,870,911,192 B**，sha256 `ee0603b45cb6d9b7223c224c4d118877a1ea3baa3174536ec5df2765ba4a39c3`
- PROVENANCE `…nsp.PROVENANCE.json`（14,064 B，sha256 `537c2ae7…`），version **1.0.8** / version_code 65544 / title `Haruno CN`
- 结构校验 `galnx package nsp verify` = ok，19 checks（18 ok + 1 warn「未签名，符合 homebrew 预期」）

### 11.2 验收检查表（A9）

- [ ] HOME 图标 `Haruno CN`；首启解包 → 中文标题菜单（开始游戏 / 读档 / 快速读档 / 继续游戏 / 游戏设置 / 鉴赏模式 / 结束游戏）
- [ ] 中文字形正常（`DroidSansFallback.ttf`），无豆腐块；窗口标题 `Haruno CN (64-bit) | 1.0.8`
- [ ] **A** = Enter：标题菜单 D-Pad 选择 + A → 进入 `start.ks` → 正文「我拼命地伸出了手。」；A 连续翻页
- [ ] **B** = 返回：正文中切消息窗显隐 / 在存读档面板中关闭面板（**不会**触发 ESC 的最小化路径，因为本作 `nESC_KEY=false`，走 ESC 会假死——这是 v2 映射的刻意偏差）
- [ ] **+（PLUS）** = 存档面板（SAVE，中文「复制/移动/删除/注释」）；**Y** = 读档面板（LOAD）；面板可 A 点选、B 返回
- [ ] **-（MINUS）** = 退出确认框「结束游戏吗？ 是 / 否 / 总是确认」→ 是 → 回 HOME，**无 Error Code 2-0000 / `Member "SystemObj" does not exist`**（patch G 修复点 1）
- [ ] **K2S 抽屉电源键退出**：画面底部 ☰ → 电源图标 → 游戏确认框 → 是 → 回 HOME，**无 2-0000 崩溃**（patch G 修复点 2，真机 bug 原始复现路径）
- [ ] **X** = 自动模式开关（正文自动推进；再按 X 取消）；**ZR** = 鼠标左键、**ZL** = 鼠标右键（虚拟光标处点击）
- [ ] **R** = 按住持续 Ctrl：正文中按住 R 快进（skip），松开即停；能跨脚本快进（`@0000A_Z01.ks` → `@0000A_Z02.ks`）（patch H）
- [ ] **右摇杆** = 虚拟光标移动（速度已降为旧版一半）；**左摇杆上下** = 滚轮（每次推到底只滚一格：**上推 = 打开 BackLog（LOG）/ 下拉 = 下一句**，patch H 修正方向）
- [ ] **D-Pad** = 方向键（标题菜单/选项/文本框移动）；**PLUS 长按/连按**无卡死（旧版「PLUS 菜单打开时按 R 冻结」已修）
- [ ] 中文 OP 播放（替换 `movie.xp3` 中的 `opening.mpg`，含中文硬字幕）；音频 BGM / 语音可闻
- [ ] **HOME 图标为封面图**（`examples/pilot01/icon-cover.jpg`，256×256 JPEG；Citron 不显示，仅真机可见）（A9）
- [ ] 二次启动 marker 命中；`savedata/` 能新增/读取槽位
- [ ] 证据：系统截图 + `sdmc:/switch/kirikiroid2/k2s_log.txt` + `sdmc:/galnx-input.log`（引擎热键日志）→ 归档 `docs/milestones/evidence/P7b-*`

### 11.3 已知限制

- **B ≠ Esc**：本作 ESC 语义是「最小化」，Switch 上会让游戏进入不可恢复的 `EscapeObj` 状态（假死），因此 v2 映射把 B 实现为游戏原生「返回」（`ActiveObj.RightMouseUpAction()`）。副作用：无法用 B 直接呼出确认退出，退出统一走 **-**。
- **R = Ctrl 与游戏 skip 状态叠加**：存读档面板/菜单打开时按住 R，游戏的 `SkipCheck()` 也会返回真（与键盘 Ctrl 一致）；出现异常快进时先松开 R 或关闭面板。
- 左摇杆滚轮为单步脉冲（不是连续滚动），快速翻页仍用 A。
- 右摇杆光标与 ZR/ZL 点击依赖虚拟光标（首次操作会自动打开光标；也可点 K2S 抽屉的鼠标图标切换）。
- 长流程 / 选项分支 / 鉴赏模式未遍历；OP 之后的剧情仍以序章验证为主。
## 12. A10 中文版安装与验收（v1.8 新增，当前推荐版本）

> 结论先行：A10 = A9 + **patch I**（退出前显式 `TraceSave + SystemSave`、ZR/ZL 改为按住鼠标、光标淡出后重显、标题/设置画面 axis 早退后移）。模拟器端 i6/i8 + A10 RUN A–D 全 PASS；真机待复验用户 m13042 的四个问题。

### 12.1 安装

1. **与 A5–A9 同一 TitleID**（`010047410000A000`）：装 A10 覆盖旧版，不能并存。
2. 方式 A（推荐，上传即安装）：Switch 打开 **DBI → Run FTP server**，执行 `python E:/galnx-build/pilot-01/p8/ftp_upload_a10.py`（默认 `192.168.31.254:5000`，IP 不同改脚本两行）。约 2.87 GB / 7–9 分钟。2026-10-31 00:04 已按此方式上传 A10：`UPLOAD_DONE … 2870911704 in 449.7 s`（≈6.12 MiB/s，DBI 上传完成即自动安装）。
3. 方式 B：NSP 拷贝到 SD 卡 `switch/`，DBI → Install from SD。
4. 首启解包 23 文件（约 2843 MiB 有效 / 2704 MiB 磁盘）到 `sdmc:/kirikiri/haruno/`；二次启动走 marker（`already extracted`）。

**产物**：`E:/galnx-build/pilot-01/p8/out/Kirikiroid2-NX-A10-CN-010047410000A000.nsp`
- 大小 **2,870,911,704 B**，sha256 `0efc23f66f57a016c15ea3944cdb8ce5b396f03f6bef3b8f5ddc1794d03186f2`
- PROVENANCE `…nsp.PROVENANCE.json`（14,100 B），version **1.0.9** / version_code 65545 / title `Haruno CN`
- 结构校验 `galnx package nsp verify` = ok，19 checks（18 ok + 1 warn「未签名，符合 homebrew 预期」）

### 12.2 验收检查表（A10，重点 = 上一版四问题）

- [ ] **①设置持久**：游戏设置里改任一项（画面模式 / 效果 / 确认对话框等）→ 用 **-** 正常退出回 HOME → 重启游戏 → 设置仍是修改后的值（旧版因 `finalize()` 从未执行而回退）
- [ ] **②存档带时间与文本**：正文中按 **+** 打开 SAVE 面板，存到任意槽（如 01 02）→ SAVE/LOAD 面板中该槽显示缩略图 + 首句文本 + 日期时间；**NEW 徽标出现在最新槽**而不是永远槽 1；设置状态不再锁死在槽 1
- [ ] **③继续游戏无「强制终止」警告**：退出再启动 → 标题菜单「继续游戏」→ 直接续读，**无**「強制終了の為このデータが確実に使用可能か保証できません」警告（该警告由未正常保存触发，patch I 修复）
- [ ] **④ZR 可按住拖拽**：正文中 **ZR 按住不放**并推右摇杆 → 可拖拽 / 连续左键（旧版只单击）；ZL 同理右键；光标淡出后再按 ZR 会重新出现（patch I 修复）
- [ ] 回归 A9 项：B 返回、X 自动、Y 读档、**-** 退出无 2-0000、K2S 抽屉电源退出无 2-0000、R 快进、左摇杆上下滚轮方向、D-Pad、中文 OP / 音频
- [ ] **标题 / 设置 / SAVE / LOAD 画面**（`PrimaryLayerArea` 为 NULL）也能右摇杆移光标 + 左摇杆滚轮（patch I 修复点 3）
- [ ] 退出时 `k2s_log.txt` 出现 `[close] persisted system data (TraceSave + SystemSave)` 与 `[close] main window close confirmed; terminating application after save`
- [ ] 证据：截图 + `sdmc:/switch/kirikiroid2/k2s_log.txt` + `sdmc:/galnx-input.log` → 归档 `docs/milestones/evidence/P8b-*`

### 12.3 已知限制

- 退出保存是 **best-effort**：保存后还有 1 s 延迟退出，若期间强制断电或从 HOME 强杀进程，最后一次设置/存档元数据仍可能丢失。
- Citron 侧虚拟光标显示时 `clickpost` 注入点击失效（harness 限制），真机由 ZR 自身点击，不受影响。
- 未遍历长流程 / 选项分支 / 鉴赏模式；OP 之后的剧情仍以序章验证为主。

### 12.4 真机验收结果（2026-10-31，用户确认）

- 用户 m13918：**测试通过**，v1.8 四问题（①设置持久 ②存档时间/文本与 NEW ③继续游戏不再提示强制终止 ④ZR 按住拖动）全部解决，暂未发现明显问题。
- A10 由 DBI FTP 上传自动安装：`UPLOAD_DONE … 2870911704 in 449.7 s`（≈6.12 MiB/s，2026-10-31 00:04 完成）。
- 结论：**A10（1.0.9）作为本作交付基线；首款垂直试点按用户完成标准达成**。后续回归关注 §12.2 长流程/分支/鉴赏模式与 §12.3 best-effort 保存限制。

## 13. Pilot-02 / Pilot-03：rfvp 引擎两作安装与验收（v1.6 新增）

> 结论先行：rfvp 适配器（FVP 引擎）已从「研究级」推进到**真机可用**：
> - **Pilot-02《五彩斑斓的世界 HD Re:GENERATION》（IROSEKA_FHD）1.0.9** —— 修复 v1.0.8 真机黑屏；async 路径强制关闭 + 可选帧心跳；P16/P17 性能补丁（60 fps、惰性存档、资源缓存）全部保留。
> - **Pilot-03《さくら、もゆ。HD Re:GENERATION》1.0.0** —— 720p 基线构建，用于判断 NS 硬件性能瓶颈；**显示日文原版**（PC 汉化 patch.bin 是 Windows 运行时注入，rfvp 不加载）。
> - **Pilot-03 中文《さくら、もゆ。HD Re:GENERATION》1.0.2** —— PC 汉化 patch.dat 经 hcb 字节码原位重打包（剧情全中文）+ patch.bin 60 条 UI 贴图 loose 覆盖（标题 logo 中文，菜单按钮仍日文）；title_id `010047420000C200`。

### 13.1 安装（两个 NSP 都可用 MTP「SD Card install」）

1. Switch 用 USB-C 连电脑，进 **DBI → MTP**（或直接弹出盘符）。资源管理器出现多个盘符，选中 **`5: SD Card install`**。
2. 把 NSP 拖进该盘符 → 系统自动安装（无需 DBI 菜单操作）。约 10 分钟/9.9 GB，完成后 HOME 出现图标。
3. 也可用 `scripts/ftp_upload_*.py` 走 DBI FTP（上传即安装）或拷到 SD 卡 `switch/` 用 DBI 安装。

> **MTP 安装实测（2026-11-05，v1.0.9 + Sakura）**：向 `5: SD Card install` 复制时 Explorer 会显示「正在复制…」对话框；被复制的 NSP **不会**出现在该目录列表里（DBI 边收边装），随后可能显示「正在等待: Switch 正忙。」，属于正常安装中状态。
> 宿主侧**无法用目录枚举或 SD 剩余空间确认安装结果**：本机用 emuMMC，安装落到 emuMMC raw 分区，MTP 暴露的 FAT32 剩余空间与 `Nintendo/Contents/registered` 都不变。唯一可靠确认 = Switch HOME 出现新图标并能启动。记录见 `docs/milestones/evidence/P21b-mtp-install/`。

| 产物 | 大小 | sha256 | TitleID / 版本 |
| --- | --- | --- | --- |
| `E:/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp` | 9,979,495,640 B | `726bb2d1b0494256b5e5b12ca9d8e08b053ab56022593f562762d256c0d3c0d9` | `010047420000A000` / 1.0.9 |
| `E:/galnx-build/p21/out/SAKURA_MOYU-010047420000c000.nsp` | 7,990,691,032 B | `d2d4278372eb9a79d18d42932d0ad9722585bef9cfc48301abbc3000c72bd5cf` | `010047420000C000` / 1.0.0 |
| `E:/galnx-build/p23/out-v2/SAKURA_MOYU_CN-010047420000c200.nsp` | 8,004,355,288 B | `5708da95640b91928829a746c36a73571025c1db5ec83a8e4ce47bc9e64bad8b` | `010047420000C200` / 1.0.2（中文 UI） |
| `E:/galnx-build/p22/out/IROSEKA_FHD-010047420000a000-v1.1.0-test.nsp` | 9,979,498,200 B | `753082b7da4e37f1eebe9d2558ffbfe1d907fc8885e01f02711a37e7709b0b0d` | `010047420000A000` / 1.1.0-test（async 修复，仅测试） |

- IROSEKA 清单 `examples/pilot02-iroseka.yaml`；Sakura 清单 `examples/pilot03-sakura.yaml`（`options: nls=sjis`、romfs 直出）。
- 两者均为 **自包含 NSP**：游戏数据在 romfs 内，不依赖 `sdmc:/switch/rfvp/game`。若 SD 上残留旧的 `switch/rfvp/game` 目录，**NRO 形态**会优先用它（调试用），NSP 形态不受影响。
- 结构校验：`galnx package nsp verify` 均 ok（12–19 checks，0 fail，1 warn = 未签名 homebrew 预期）。

### 13.2 IROSEKA 1.0.9 验收检查表（重点 = 黑屏修复）

- [ ] HOME 直接启动 → 出现厂商 logo 后进入标题（「五彩斑斓的世界 HD Re:GENERATION」+ New Game/Continue/Album/Option/Exit，60 FPS OSD）
- [ ] **不再黑屏**：v1.0.8 在真机卡死（async 路径整进程冻结）；v1.0.9 即使 SD 卡上残留 `sdmc:/switch/rfvp/async.txt = on` 也必须忽略该文件直接进游戏
- [ ] **New Game → 正文**：A=Enter 推进、B=Esc 开暂停菜单、X=自动、Y=读档、ZR=左键按住（右摇杆移动光标拖拽）、ZL=右键、R=按住 Ctrl 快进、方向键=方向、左摇杆上下=滚轮（上=backlog）、+=存档、-=退出确认
- [ ] **逐句无卡顿**：P16 惰性存档后每句 save 从 112–135 ms 降到 5.3–5.8 ms；若仍有卡顿，用 `sdmc:/switch/rfvp/perf_slow.log` 取证（详见 `docs/builds/022`）
- [ ] 存读档：`+` 面板存档后显示缩略图/文本/时间；退出重进 → Continue 正常续读
- [ ] 退出：`-` → 中文确认框「结束游戏吗？」→ 是 → 干净退出回 HOME（无 Error Code / 无崩溃）
- [ ] 可选诊断：SD 卡放 `sdmc:/switch/rfvp/debug.txt`（内容如 `shot=600`）可让 v1.0.9 每 15 帧写 `frame_status.txt`（`frame=… status=… async=0`），用于确认渲染心跳；不放则不产生额外开销
- [ ] 证据：屏摄/截图 + `sdmc:/switch/rfvp/debug_report.txt`（若产生）+ `perf_slow.log` → 归档 `docs/milestones/evidence/P21b-*`

### 13.3 Sakura 验收检查表（日文 1.0.0 / 中文 1.0.2，720p）

- [ ] **中文 1.0.2**：标题 logo 中文（「樱花萌放」风格）；New Game → 正文中文（「世界于此，暂作叹息——」等），无方框/错位；菜单按钮仍英文+日文 ruby（已知资产缺口）
- [ ] 启动 → 标题「さくら、もゆ。」（夜樱 + NEW GAME/CONTINUE/ALBUM/OPTION/EXIT），**60 FPS**
- [ ] New Game → 正文日文显示正确（SJIS；若出现乱码说明 `nls` 配置错，本构建已固定 sjis）
- [ ] **动作/表情/背景切换**观察：与 IROSEKA 的 1080p 表现对比，记录是否有整句卡顿
- [ ] 存档/读档往返（P16 后的 rfvp 走同一 save 子系统）
- [ ] 取证：`sdmc:/switch/rfvp/perf_slow.log`（慢帧 + stages）、`debug_report.txt`、屏摄 → 归档 `docs/milestones/evidence/PERF-01b-*`
- [ ] 若 720p 在真机稳定 60 FPS 且无长帧 → 说明 NS 性能可覆盖 720p；IROSEKA 1080p 的卡顿应优先按「消除一次性长帧」处理，资源压缩降为备选（判断见 `docs/experiments/perf-01-sakura-720p.md`）

### 13.4 已知限制

- Sakura 汉化：**已可用**（中文 1.0.1 剧情、1.0.2 再加 UI 贴图），路线为离线 hcb 字节码重打包 + loose 贴图覆盖，不依赖 Windows 注入；剩余缺口是菜单按钮贴图与译文精校（见 `docs/builds/031-sakura-cn-nsp.md`）。日文 1.0.0 保留作对照。
- IROSEKA async 解码/异步 restore **暂不启用**（v1.0.9 强制 off）；根因（同核优先级反转 + spin 锁跨阻塞 SD 读）与修复方向见 `docs/experiments/rfvp-async-hang-rca.md`，属后续实验，不阻塞当前交付。
- 两作的长流程 / 分支 / 鉴赏模式 / 视频播放未遍历；本次验收以「启动 + 进正文 + 存读档 + 退出」为主。



### 13.5 async v1.1.1-test 真机验证（prefetch-only，真机确认前不推送）

> 用途：验证 async 在真机的两项前提——①并发安全（pack 睡眠互斥 + worker 换核 + 独立看门狗）②**prefetch-only** 不再出现「CG 缺失 / UI 残留」（v1.1.0-test 的延迟绘制缺陷已由 task-53 修复，见 `docs/builds/032-rfvp-async-prefetch.md`）。**测试包，不发布**。

1. 安装 `IROSEKA_FHD-010047420000a000-v1.1.1-test.nsp`（`E:/galnx-build/p25/out/`，9,979,496,152 B，sha256 `bf83fa6e…ded2e5b`；title_id 与 1.0.9 相同，覆盖安装）。
2. SD 卡写 `sdmc:/switch/rfvp/async.txt` 内容 `on`；清空旧 `async_status.txt` / `watchdog_status.txt` / `last_error.txt` / `perf_slow.log` / `debug_report.txt`（用覆盖写空文件，不要用资源管理器删除，避免 MTP 模态确认框）。
3. 先验缺陷三项（v1.1.0-test 的真机问题，v1.1.1-test 用 prefetch-only 重做）：
   - **CG**：读档 DATA_001（或推进到任意 CG 场景）→ CG 必须完整显示，只有对话框而缺背景/立绘 = 失败
   - **UI 残留**：打开存档/设置/backlog 再关闭 → 关闭后不应残留旧像素；下一个可显示图像出现前不应有黑块/错位
   - **OP**：序幕→第一章的 OP 本构建仍**预期跳过**（no_std 无 movie 解码器，见 032 §5），只在 `debug_report.txt` 里找 `movie ... no movie decoder` 诊断，未新增异常即通过；OP 正片播放属另立项
4. 再跑 async 健康度：New Game → 连续推进正文/切场景 **3–5 分钟**（不要停在存档 UI）。
5. 取回判定：
   - `async_status.txt`：`enabled=1`、`hb` 持续递增、`stage=0`、`cpu=1`（worker 已换核）、`wdt=1`、`stalled=0`
   - 不应出现 `watchdog_status.txt`（出现即看门狗触发过）与 `last_error.txt`
   - `debug_report.txt` 应有若干 `async decode applied`；画面无黑屏/花屏/卡死
6. 通过 → 才推送 v1.1.1-test 相关 commit；未通过 → 保持 `async.txt=off`（等价 v1.0.9）并回传日志。
7. 回退：删 `async.txt` 或写 `off` 即恢复同步解码（等价 v1.0.9 行为）。
> **真机结果（2026-11-05，未通过）**：并发/看门狗机制正常（`enabled=1 hb 递增 stage=0 cpu=1 wdt=1 stalled=0`，未冻结），但出现「部分 CG 不显示 / UI 开合残留 / OP 跳过」。根因是大图异步解码的**延迟绘制语义**与按 id 逐帧重画不兼容（`graph.rs:1046-1058` 立即返回 Nil），与并发修复无关。已回退 v1.0.9；详见 `docs/experiments/rfvp-async-device-defect.md`。

### 13.6 P26 v1.1.2-test 真机验证（SD 读放大 + 4K 差分纹理缓存）

> 用途：验证真机 Album 4K CG 差分切换卡顿（用户 m27413，v1.1.1-test 上有时 >1 s）的两项修复——①pack 整条目 4 MiB 分块读（消除 4 KiB 读放大）②MAX_ENTRY_BYTES 16→64 MiB 让 33,177,600 B 的 4K 差分纹理入缓存。测试包，不发布。

1. **安装当前受阻**（2026-11-06 05:28–05:45）：`5: SD Card install` 与 `6: NAND install` 目标 CopyHere 均**静默不启动**（无「正在复制」对话框、目标目录无文件、14 B 探针同样无反应），而 MTP 浏览/反向拷贝正常 → 判断 DBI 当前不在 MTP install 模式。处理顺序：
   - 让 Switch 回到 DBI，进入其 **MTP install** 模式（或 MTP → Install 选项）后重试；
   - 或改用 DBI 其它安装方式（USB install / HTTP install / 前端安装器）；
   - `1: SD Card\switch\galnx-nsp` 是 FAT32，**不能**放 9.98 GB 单文件（>4 GiB 即失败，历史已踩）。
2. 安装 E:/galnx-build/p26/out/IROSEKA_FHD-010047420000a000-v1.1.2-test.nsp（9,979,500,248 B sha256 0cbac98ef8c292b69d64eef87d6340fee9477c8f007ee8b38e4d5cfb229789b8，title_id 与 1.0.9 相同，覆盖安装）。
3. SD 卡写 sdmc:/switch/rfvp/async.txt 内容 on（本包 async 默认关，靠该文件开启）；保留 debug.txt（如 shot=600）以启用帧心跳。
4. 验证路径：标题 → **Album**（y≈694）→ CG MODE（y≈281）→ 左上已解锁 CG（540,270）→ 进入 4K CG 后**连续按 A/Enter（或 ZL/右键）切换差分 ≥10 次**（左键是放大，不是切差分）。
5. 判定：
   - 主观：每次差分切换 <600 ms 为通过；出现 >1 s 卡顿 = 失败。
   - 日志：debug_report.txt 期望 vfs ... us=<300000 reads=2~5、[async] decoded texture ... 3840x2160 px=33177600、[cache] texture put ... size=33177600 evicted=0、反复 graph cache hit。
   - watchdog_status.txt 若存在且内容仍为 frame=4133 stalled_ms=3000 ... hb=85083（历史值）= 本轮无新阻塞；帧号/hb 变化 = 出现新卡顿，按失败处理。
   - 无 last_error.txt，无黑屏/花屏/冻结，标题与正文无回归。
6. 回退：装回 v1.1.1-test 或 v1.0.9；若 256 MiB 纹理预算引发内存压力，改回 TEXTURE_BUDGET=160 MiB + lookahead=0。风险：setvbuf(_IONBF) 作用于所有 rb 流，小文件流式读取可能变慢（必要时只对 pack 句柄关缓冲）。
7. 真机结果（未验）：待 DBI MTP install 恢复后补。

## 13.7 P27 音频连续性 + P28 过渡动画（v1.1.4-test）真机验收

1. 安装包（用户自行 MTP 拖入）：`E:/galnx-build/p28/out/IROSEKA_FHD-010047420000a000-v1.1.4-test.nsp`，9,979,503,832 B sha256 `444af465aa5250312a9d2d205eb711c67d7c1bbbcf23e8268b4ecd52a9223113`（基线 = P26+P27，含音频连续性与过渡动画；title_id 与 1.0.9 相同，覆盖安装）。
2. 准备：`sdmc:/switch/rfvp/async.txt` = `on`（async 仍为 prefetch-only，真机已由 P25 验证 CG/UI 无回归）；`debug.txt` 可写 `shot=600`（帧心跳）与可选的 `stall=1200`/`stall_at=1200`（仅联调时注入主线程停顿，正常试玩请删除该行）。
3. 音频连续性判定：进入正文后连续游玩 ≥5 分钟（含切场景、打开/关闭存档 UI）。判定 = 长帧（画面轻微停顿）期间**音频不中断、不爆音**；日志 `audio_status.txt` 每 600 帧刷新，期望 `underrun=0`、`starve_ms` 低、`alive=1 thread=1`；若 `underrun` 递增或听感断流则失败，回退 v1.0.9（无音频线程）。
4. 过渡动画判定：触发场景/背景切换（含序章→第一章、CG→日常、白场转场）。判定 = 出现淡出/淡入或双重曝光等中间态，而非瞬间硬切；Citron 侧证据见 `docs/milestones/evidence/P28a-transition/`（gpu-transition 13 张、cpu-harness 12 张）。若仍硬切，查 `perf_slow.log` 与 `debug_report.txt` 是否出现 mask 相关慢帧，并回报。
5. 回归项：CG 完整显示（无缺层）、UI 开合无残留、存档/读档正常、无黑屏/冻结、标题与正文（中文）无异常；`last_error.txt` 不存在，`watchdog_status.txt` 不应新出现。
6. 已知限制：OP/Movie 仍不播放（no_std 构建无 native-video，P29 处理）；每次 mask 转场多一次 8,294,400 B 回读，真机耗时/内存待测；Citron 日志约 3,968 条 `Invalid duration` 属 motion 独立缺陷。
7. 回退：装回 v1.0.9（`E:/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp`，9,979,495,640 B sha256 `726bb2d1…`）；音频线程可通过删除 `audio_status.txt` 无法关闭（编译期启用），需换回旧 NSP。

## 13.8 P30 音频 JIT（v1.1.6-test）真机验收

1. 安装包（用户自行 MTP 拖入）：`E:/galnx-build/p30/out/IROSEKA_FHD-010047420000a000-v1.1.6-test.nsp`，9,979,505,368 B sha256 `d7eb77ecf8bcba1f131ccaa5e26136a913e080203ccf096eca51e3e995e14461`（P26+P27+P28+P30；title_id 与 1.0.9 相同，覆盖安装）。
2. 准备：`sdmc:/switch/rfvp/async.txt` = `on`；正常试玩请勿在 `debug.txt` 写 `stall`（仅联调注入主线程停顿用）。
3. 判定（核心）：进入正文后连续游玩 5–10 分钟，BGM/语音应在触发后立刻听到（不应再有约 3 秒滞后）；画面偶发长帧期间音频不中断、不爆音。
4. 日志：`audio_status.txt` 期望 `mode=jit`、`lag_ms` 在 ±300 ms 内、`underrun=0`、`alive=1 thread=1`；若 `lag_ms` 接近 +3000 说明仍是 ring 版（装错包）。
5. 回归：场景切换有过渡中间态（P28）、CG 完整、UI 开合无残留、存档/读档、`-` 退出、async 不冻结；`last_error.txt` 不应出现、`watchdog_status.txt` 不应新写。
6. 回退：装回 v1.0.9（`E:/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp`，9,979,495,640 B sha256 `726bb2d1…`）。

## 13.9 P31+P32 OP 影片播放（v1.1.7-test）真机验收

1. 安装包（用户自行 MTP 拖入 `5: SD Card install`）：`E:/galnx-build/p31/out/IROSEKA_FHD-010047420000a000.nsp`，9,861,393,624 B sha256 `cb019f27136b5b80936c5c5067477c6a08e19ae02a6535f48e9f12785ba16c7d`（P26+P27+P28+P30+P31+P32；title_id 不变，覆盖安装）。
2. 触发 OP（联调用）：在 `sdmc:/switch/rfvp/debug.txt` 写 `movie=1`；正常试玩请删除该行，避免重复触发（剧情内自然触发点仍待真机确认）。
3. 判定（核心）：OP 出现时有画面、有音乐且音画同步（不应静音、不应明显错位）；以真机实际帧率为准，画面允许轻微掉帧但不得卡死或黑屏。
4. 日志：`audio_status.txt` 期望 `mode=jit`、`lag_ms` 在 ±300 ms 内、`underrun=0`、`alive=1 thread=1`；`debug_report.txt` 应含 `Movie: opened`（`movie/01.wmv`）、`movie audio: loaded`、`playing`（`movie/01.ogg`）、`decoded`/`presented` 递增。
5. 回归：OP 结束后剧情正常推进；过渡中间态（P28）、音频无 3 秒延迟（P30）、Album 4K 差分、CG/UI/存档/`-` 退出、async 不冻结均无回归；`last_error.txt` 不应出现。
6. 已知限制：Citron 只有 15 FPS，OP 呈 0.5–0.6× 慢放（模拟器解码吞吐不足）；无 WMA 解码，只含 WMA 音轨的 WMV 会静音；日志偶发 1 条 `[ERROR] id must be in range 0..256` 属 Movie 流 0x2000，不影响播放。
7. 回退：装回 v1.0.9（`E:/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp`，9,979,495,640 B sha256 `726bb2d1…`）。

## 13.10 P33 OP 分档播放（v1.1.9-test）真机验收

1. 安装包（用户自行 MTP 拖入 `5: SD Card install`）：`E:/galnx-build/p33/out2/IROSEKA_FHD-010047420000a000.nsp`，9,977,492,184 B sha256 `bd909c1eb1e6e3f9339a28b662943d0d06f74873b2dd36639824df54a90b535b`（P33 = P32 + OP 分档 + 原生尺寸；title_id 不变，覆盖安装）。NRO/ELF 与补丁哈希见 `docs/builds/039-rfvp-op-quality.md` §5。
2. 准备（首次启动前写文件）：
   - `sdmc:/switch/rfvp/video.txt` = `480`（**缺省即 480**，可填 `720`/`540`/`480`/`360` 或直接写档位号 `0`–`3`）；
   - `sdmc:/switch/rfvp/async.txt` = `on`；
   - `sdmc:/switch/rfvp/debug.txt` 写 `movie=1` 触发 OP（联调用；正常试玩删除该行）。
   - 四档对应：`720`=movie/01.wmv（1280×720p30，原始版）、`540`=01_q540.wmv、`480`=01_q480.wmv、`360`=01_q360.wmv；音轨统一为 `movie/01.ogg`。档位写错或变体缺失时自动回退原片并记日志。
3. 判定（核心，按顺序做 A/B）：
   - **A（默认 480）**：OP 有画面、有音乐、音画同步；以真机实际观感为准，允许轻微掉帧，**不得整体慢放、不得卡死/黑屏**。
   - **B（改 360 或 720 复测）**：若 480 仍明显慢放，把 `video.txt` 改 `360` 重启复测；若 480 已流畅，可改 `720` 对照画质与帧率（720 是原始档，画面最好但最吃解码）。
   - 期望：OP 时长约 120 s（480/360 为 24 fps、540 约 30 fps）；相邻截图应有逐帧变化，播完后进入静止标题画面（n12 之后多帧同哈希属正常，不是卡死）。
4. 日志（每 600 帧刷新，位于 `sdmc:/switch/rfvp/`）：
   - `debug_report.txt` 应含 `Movie: opened ... name=movie/01_q480.wmv level=2 bytes=38610038`（档位生效证据）；`decoded frame=1 ... 854x480 decode_us=<微秒> convert_us=<微秒>` 与 `presented`/`frame=2880` 递增（原生尺寸生效证据）。
   - `audio_status.txt` 期望 `mode=jit`、`lag_ms` 在 ±300 ms 内、`underrun=0`、`alive=1 thread=1`、`max_refill_gap_ms` 低（Citron 基线 `lag_ms=-108 underrun=0 max_refill_gap_ms=56`）；`debug_report.txt` 应有 `movie audio: stopped movie/01.ogg`。
   - **关键读数**：把 `decode_us`/`convert_us` 的 P50/最大值记下来回报 —— 这是判断真机解码余量的直接依据（24 fps 预算 41,700 us/帧）。
5. 回归：OP 结束后剧情正常推进；过渡中间态（P28）、音频无 3 秒延迟（P30）、CG/UI/存档/读档、`-` 退出、async 不冻结均无回归；`last_error.txt` 不应出现，`watchdog_status.txt` 不应新写入。
6. 已知限制：四档视频合计 240,254,552 B，romfs 9,930,029,496 B / NSP 9.98 GB（比 v1.1.7-test 增约 116 MB）；进度未满时安装前确认 SD 余量；Citron 480p 桌面单帧 decode 8.4–15.1 ms + convert 3.0–5.8 ms，A57 估 3–5×，真机 480p 亦可能不足 24 fps（故保留 360 档）；日志偶发 1 条 `[ERROR] id must be in range 0..256` 属 Movie 流噪声。
7. 回退：装回 v1.0.9（`E:/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp`，9,979,495,640 B sha256 `726bb2d1…`）；或把 `video.txt` 改 `360` 先保帧率。

## 13.11 P34 WMV2 左缘马赛克修复（v1.1.10-test）真机验收

1. 安装包（**用户自行** MTP 拖入 `5: SD Card install`）：`E:/galnx-build/p33/out3/IROSEKA_FHD-010047420000a000.nsp`，9,977,492,696 B sha256 `fc35fa9880ba9e38db737f2648bfa309b4e54ab0dd2571265af58d7156c4ee1d`（P34 = P33 + WMV2 宏块对齐修复；title_id 不变，覆盖安装）。NRO/ELF/补丁哈希见 `docs/builds/040-wmv2-left-edge.md` §6。
2. 准备：`sdmc:/switch/rfvp/video.txt` 先保持 `480`（与 v1.1.9-test 同档，便于对照左缘）；`debug.txt` 保留 `movie=1` 触发 OP（测完删该行）；`async.txt` 保持 `on`。
3. 判定：
   - **A（修复确认，最重要）**：OP 视频区**最左侧不再有竖直一列马赛克方块**，左缘与画面其余部分连续（该列在 v1.1.9-test 上稳定出现）。
   - **B（画质对照）**：先拍一张左缘特写；再把 `video.txt` 改 `540` 重启复测（若 540 仍流畅，再试 `720`），回报「糊」的可接受程度与是否有慢放。这是决定默认档是否从 480 上调的依据。
   - **C（回归）**：OP 结束后正常进标题/正文；音轨正常；480 档 `decode_us` 应与 P33 同量级（8–18 ms，修复不应更慢）。
4. 日志（`sdmc:/switch/rfvp/debug_report.txt`）：应含 `Movie: opened ... name=movie/01_q480.wmv level=2 bytes=38610038`、`decoded ... 854x480 decode_us=<微秒> convert_us=<微秒>`。若左缘仍异常，回传 debug_report.txt + 一张 OP 截图（320×180 以上左缘可见即可）。
5. 回退：装回 v1.1.9-test（`E:/galnx-build/p33/out2/IROSEKA_FHD-010047420000a000.nsp`，9,977,492,184 B sha256 `bd909c1eb1e6e3f9339a28b662943d0d06f74873b2dd36639824df54a90b535b`），或把 `video.txt` 改 `360` 保帧率。
