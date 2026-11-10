# 试点验收 — 存档 / 读档（U20）

> 记录时间：2026-10-30。形如「U20」的编号来自 `docs/pilot/P1-engine-k2nx.md` 的未验证项清单。
> 结论：**PASS（模拟器层面）**。全程只用**手柄按键**（无鼠标、无触摸），完成「存档 → 落盘 → 重启 → 读档 → 画面回到存档点 → 继续推进」闭环；NRO 形态与自包含 NSP（A4）形态均实测通过。
> 实现方式见 `docs/builds/010-k2nx-controller-saveload.md`（patch D 虚拟鼠标光标 + patch E 原生 SAVE/LOAD 界面热键）。

## 1. 为什么需要「手柄存档」

KiriKiri2-NX 的存档/读档入口只有两条，且都依赖触摸：

| 入口 | 实现 | 手柄可达？ |
| --- | --- | --- |
| K2S 抽屉 `btn_gamemenu` → 游戏 TJS 菜单 | `src/core/environ/ui/GameMainMenu.cpp` 触摸按钮 → `TVPInGameMenuForm`（也是触摸 ListView） | ✗ 抽屉与表单都没有键盘导航 |
| 游戏内菜单 `Window.menu` | `TVPGetMenuDispatch()` 由游戏 TJS 设置 | ✗ 本作（BASE ADV SYSTEM）**根本没有** `Window.menu` |

而真机 TV / docked 模式没有触摸屏，Citron 侧的鼠标/触摸注入也不可用（见 §5）。因此按计划 v1.0 的决策 12（优先打通手柄可玩），给引擎补了：

- **patch D**：`Y` 开关**虚拟鼠标光标**，D-Pad 每次移动 24 px，`A`=左键 / `B`=右键（绕开 `onAxisEvent` 对 `PrimaryLayerArea` 的早退）；
- **patch E**：手柄热键直通本作原生存档系统（`MainObj.SaveAction` / `DataLoadAction` / `_SAVELOADOBJECT`），并关掉存档/读档确认框，使「点槽位 = 立即读档」。

## 2. 验收项与结果

| # | 验收项 | 判据 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| S1 | 存档写入 SD | `savedata/savedata010.bmp` 出现且非空 | ✅ 45,941 B | `P3g-a4-savedata.txt` |
| S2 | 游戏识别存档 | 原生 SAVE / LOAD 界面槽位 01 01 显示缩略图 + 标题 + 日期 | ✅ | `P3g-a4-01-loadui.png`、`P3g-a4-06-saveui.png` |
| S3 | 重启后仍可读 | 新进程打开 LOAD 界面仍显示该槽位 | ✅ | 同上（重启后新会话） |
| S4 | 读档回到存档点 | 读档后画面/文本 = 存档时那句 | ✅ | `P3g-a4-04-loaded.png` |
| S5 | 读档后可继续 | A 推进进入下一句，无异常 | ✅ | `P3g-a4-05-adv1.png`、k2s 无 error |
| S6 | 全手柄操作 | 全程只发手柄键（A/B/X/Y/方向/L/R/ZL/ZR/PLUS/MINUS） | ✅ | `P3g-a4-glog.txt` 的 `[pad]`/`[virt]` 行 |
| S7 | 退出游戏（U21） | 确认「ゲームを終了しますか？」→「はい」后干净退出，无 `SystemObj` 错误框 | ✅ 模拟器（真机待 A5） | `P4a-exit-01-dialog.png`、`P4a-exit-02-after-yes.png`、`P4a-exit-glog.txt` |

## 3. 两次实测（NRO 与 NSP）

| 形态 | run dir | 时间线 | 关键截图 |
| --- | --- | --- | --- |
| NRO（引擎直跑） | `workspaces/citron-harness/runs/20261030-124145-kirikiroid2` | title 12:46:26 → 注入 → 12:46:59 `@0000A_Z01.ks`（读档落点） | `P3g-s27b-*` 8 张 |
| NSP（A4 自包含） | `workspaces/citron-harness/runs/20261030-125742-Kirikiroid2-NX-A4-010047410000A000` | title 12:58:40（启动 58 s，payload 已解包）→ 12:59:14 `@0000A_Z01.ks` | `P3g-a4-*` 7 张 + k2s/glog |

NSP 形态窗口标题 `citron Nightly | 0237a9b88 | Haruno (64-bit) | 1.0.3 | NVIDIA` —— 与 A4 的 manifest 版本一致，证明跑的是本次打包产物。

步骤（harness `--input-steps` 等价的宿主 VK 序列）：

1. `wait` 到 `Scenario loaded : title.ks`，等 6 s；
2. `69`（E→R 肩）打开原生 **LOAD** 界面 → 截图；
3. `90`（Z→Y）开虚拟光标 → `40`×9、`37`×11、`38`×15（下/左/上）把光标移到槽位 01 01（`[virt] cursor=(216.0,414.0)`）；
4. `67`（C→A）点击槽位 → 直接触发 `DataLoadAction(10)` → 截图（游戏自带 NOW LOADING）；
5. `67` 推进 → 截图（存档点那句）；
6. `77`（M→PLUS）打开原生 **SAVE** 界面 → 截图（槽位有数据）。

## 4. 存档文件与槽位规则

- 目录：`sdmc:/kirikiri/haruno/savedata/`（`System.exePath + "savedata/"`，由 `Init.tjs` 的 `Savefolder` 决定）；
- 文件名：`savedata%03d.bmp`，编号 = `NowPage*10 + DataNum`（NowPage 1 基、DataNum 0..9）→ 界面显示「01 01」= `savedata010.bmp`；
- 另见 `system.bmp`（系统存档字典，989 B）与 `krkr.console.log`（引擎控制台输出，UTF-16LE）；
- 缩略图 + 存档正文是同一个文件（BMP 后追加 `Dictionary.saveStruct` 数据），所以存档文件既是截图又是数据。

## 5. 限制（详见 `docs/builds/010-k2nx-controller-saveload.md` §6）

| # | 限制 | 影响 |
| --- | --- | --- |
| E1 | 本作无 `Window.menu` | patch E 的通用菜单导航对本作无效（保留给其他游戏） |
| E2 | 合成触摸会崩 Citron | 放弃「伪造触摸点 UI」路线，改用虚拟光标 |
| E3 | 原生 UI 是 TJS 图层 | 只能靠虚拟光标 + A 点击操作 |
| E4 | `InternalKeyDown` 的 ESC 分支 bug 未修 | 本作 `UseMouseKey` 为 false，不受影响 |
| E5 | `GalNXLog` 会写 `sdmc:/galnx-input.log` | 仅实验取证，发布版应移除 |
| E6 | 热键绑定本作 TJS API | 换游戏需按该作 `MainObj` 等价 API 调整 |

## 6. 与 Citron 前端的关系（L6 修正）

早期记录（P2 阶段）把「NSP 形态鼠标点击全失效」列为 Citron 前端行为。本次定位的结果更精确：

- Citron 的渲染子窗口是独立原生 HWND，`GRenderWindow::mousePressEvent` 用 `mapFromGlobal(QCursor::pos())` 取点 —— 自动化注入（PostMessage / SendInput）在 Task Scheduler 降权启动路线下不可靠；
- 即使点击送达，**guest 侧 KAG/ADV 层也不处理触摸**（`onTouchBegan` 只有当虚拟鼠标模式关闭时才把触摸转给游戏层，而本作游戏层不消费），所以「模拟器里点屏幕推进剧情」本身就不成立；
- 真机触摸屏是另一条通路（K2S 抽屉与 TJS UI 都能真触摸），不受此限制。

因此：**模拟器上的验收统一走「手柄 + 虚拟光标」**；真机验收可按 P4 runbook 用触摸或手柄热键。

## 7. 复现

```bash
# NRO 形态
bash /e/galnx-build/pilot-01/p3/save-exp/run-s27b.sh
# NSP（A4）形态
bash /e/galnx-build/pilot-01/p3/save-exp/run-a4smoke.sh
```

两个脚本都内置「杀残留 Citron → 断言 0 实例 → 启动 → 等 title → 取 hwnd → 按键序列 → 收日志 → 杀进程」；失败自动重试 3 次（Citron 偶发启动崩溃）。

## 8. 退出验收（U21 / patch F，2026-10-30）

真机报告：K2S 抽屉电源键退出 → Error Code 2-0000、`Member "SystemObj" does not exist @line(365) checkdialog.tjs`。根因与修复见 `docs/builds/011-k2nx-exit-crash-fix.md`（patch F：Switch 上确认关闭 = `TVPExitApplication(0)`，并给 `Window` 补 `minimized/maximized` 兼容成员）。

模拟器实测（`run-exit3.sh`）：

| 步骤 | 结果 |
| --- | --- |
| X 热键 → `MainObj.onCloseQuery(true)` | 弹出「ゲームを終了しますか？」确认框（`P4a-exit-01-dialog.png`） |
| Y + DPAD + A 点「はい」 | glog 末行 `[close] main window close confirmed; terminating application` |
| 进程退出后 | 回 Citron 游戏列表，无错误框、k2s 无 error/exception（`P4a-exit-02-after-yes.png`） |
| 存档目录 | 未变（`savedata010.bmp` 45,941 B、`system.bmp` 989 B） |
| ESC 路径 | 标题画面按 B 未触发 `EscapeWork` → `minimized` 修复仅源码级证据，未端到端复现 |

真机复验步骤见 `docs/pilot/P4-device-runbook.md`（A5 NSP 上传 → 启动 → 抽屉电源键 → 确认 → 期望回 HOME 且无错误码）。

## 9. A5 NSP 回归（2026-10-30，Citron）

A5 是把 patch F 打进 exeFS 的自包含 NSP（version 1.0.4，2,906,138,328 B sha256 `f179f0a2…`），本轮回测「读档 + 退出」在**打包形态**下是否仍成立。

| 项 | 结果 |
| --- | --- |
| 窗口标题 | `citron Nightly | 0237a9b88 | Haruno (64-bit) | 1.0.4 | NVIDIA` |
| R 打开原生 LOAD UI | 槽 01 01 正常显示 12:23 存档（缩略图 + 标题 + 日期） |
| 读档 | 进正文，k2s `Scenario loaded : @0000A_Z01.ks` |
| 推进 | C 两次，文本正常前进 |
| 退出 | X →「ゲームを終了しますか？」→ はい → glog `[close] main window close confirmed; terminating application` → 回游戏列表、无错误框、k2s 0 error/exception |
| 存档目录 | `savedata010.bmp` / `system.bmp` 未变；新增 `savedata400.bmp`（46,065 B，读档后游戏自写，语义待确认） |

证据：`docs/milestones/evidence/P4b-a5-*`（`P4b-a5smoke.sha256` 含全部哈希）；脚本 `/e/galnx-build/pilot-01/p3/save-exp/run-a5smoke.sh`；完整构建/校验记录见 `docs/builds/011-k2nx-exit-crash-fix.md` §9。
