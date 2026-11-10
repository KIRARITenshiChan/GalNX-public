# 013 — Kirikiroid2-NX 手柄映射 v2（patch G）与三个真机问题修复

- 状态：模拟器级 PASS（Citron 1.3.265+0237a9b88，K2NX NRO/NSP 双形态验证）；真机待复验
- 日期：2026-10-30
- 关联：`docs/builds/010-k2nx-controller-saveload.md`（patch E 手柄存读档）、`docs/builds/011-k2nx-exit-crash-fix.md`（patch F 退出崩溃）、`docs/pilot/saveload-acceptance.md`、`docs/pilot/P4-device-runbook.md`
- 产物：A8 中文 CN NSP `Kirikiroid2-NX-A8-CN-010047410000A000.nsp`

## 1. 背景

真机复验（用户 2026-10-30 反馈，A7 中文版）三项 PASS：开始游戏正常、PLUS 能呼出 K2S 菜单。同时报告三个问题与一份新的默认映射需求：

| # | 现象 | 触发路径 |
|---|------|----------|
| Bug 1 | 游戏冻结（K2NX 仍在跑、UI 卡住只剩渐暗动画） | PLUS 打开 K2S 抽屉菜单后按 R（patch E 的「打开游戏 LOAD UI」热键） |
| Bug 2 | 崩溃 Error Code 2-0000 / `Member "SystemObj" does not exist @line(365) checkdialog.tjs` | K2S 抽屉（右下角 ☰）→ 电源按钮 → 游戏弹确认框 |
| Bug 3 | 光标移动过快 | 摇杆控虚拟光标 |
| 需求 | 新默认映射 | A=Enter、B=Esc、ZL=右键、ZR=左键、右摇杆控光标、左摇杆上下=滚轮单步、D-Pad=方向键、+=存档、-=退出、X=自动、Y=读档 |

## 2. 映射表 v2（patch G 之后）

| 手柄 | 行为 | 实现层 |
|------|------|--------|
| A | Enter（确认/推进文本） | keymap XML（`Kirikiroid2Preference.patchG.xml`）：`448 → 13` |
| B | back（取消/关闭上一层，等价游戏原生右键） | 引擎 pad 层 `GalNX_GameBack()` |
| X | 自动模式开关 | 引擎 pad 层 `GalNX_ToggleAuto()` |
| Y | 读档面板 | 引擎 pad 层 `GalNX_OpenGameSaveLoad(false)` |
| +（PLUS/START） | 存档面板 | 同上 `true` |
| -（MINUS/SELECT） | 退出（走游戏原生确认框） | 引擎 pad 层 `GalNX_RequestExit()` |
| ZR | 鼠标左键（点击虚拟光标处） | 引擎 pad 层 `_mouseBtn=mbLeft` + `onMouseClick` |
| ZL | 鼠标右键 | 同上 `mbRight` |
| 右摇杆 | 移动虚拟光标（速度 = patch E 的 1/2） | `onAxisEvent` 🔁 `JOYSTICK_RIGHT_X/Y` |
| 左摇杆上下 | 滚轮单步（每推一次 ±120，回中才能再触发） | `onAxisEvent` 迟滞 + `GalNX_SendWheel()` |
| D-Pad | 方向键 | keymap XML（`Kirikiroid2Preference.patchG.xml`）：`437-440 → 37-40` |

**B 为什么不是 ESC**：本作 `userFix.ks:500-505` 设 `nESC_KEY = false` → `MainWindow.tjs:1418-1425` 走 `EscapeWork()`（`MainWindow.tjs:3411`），它停定时器/音频后置 `EscapeObj = true` 并调 `this.minimize()`；patch F 让 `minimized` 恒 0、`minimize()` no-op，于是 `EscapeObj` 永不复位，之后所有按键都被 `onKeyUp` 的 `EscapeObj !== void` 守卫拦掉 → **假死**。因此 B 用「游戏原生右键」实现 back 语义：`MainObj.ActiveObj.RightMouseUpAction()`，该虚方法由 CheckDialog/ConfigObject/LogObject/MessObject/MovieObject/SaveLoadObject/SelectObject/TitleObject 各自覆写。

## 3. 三个 Bug 的根因与修复

### Bug 1：K2S 菜单打开时按存档/读档热键 → 冻结
- 根因：patch E 的热键直接构造游戏 `_SAVELOADOBJECT` 并设为 `MainObj.ActiveObj`，但 K2S 表单（`TVPInGameMenuForm`）仍在 UI 栈顶，形成「两层模态」：K2S 表单吞输入，游戏面板等输入 → 假死。
- 修复：新增 `GalNX_CloseAllK2SForms()`，在打开游戏 SAVE/LOAD 面板前先把 K2S 表单栈全部 `popUIForm`（最多 8 次 + 防重复）；同时先用 `MainObj.SaveLoadObj.TempActive` 关闭已存在的游戏面板，避免重复构造。
- 验证（g1）：抽屉打开状态下按 Y → LOAD 面板正常打开（`P6-g1-loadui-from-drawer.png`、`P6-g1-saveui.png`），glog 出现 `[tjs] sl-replace / loadui-nodlg / loadui-open -> ok`。

### Bug 2：K2S 抽屉电源键 → SystemObj 崩溃
- 根因：抽屉电源按钮走 `TVPGetActiveWindow()->Close()`（`ui/GameMainMenu.cpp:114-119`）→ `TVPWindowLayer::Close()` 置 `ProgramClosing = true` → `OnCloseQuery()`：原实现直接 `CanCloseWork = true` 返回，不等游戏回调，于是 `Close()` 继续 `OnClose(action)`，对主窗口执行 `obj->Invalidate()` → TJS 世界在自己顺序里 teardown，`CheckDialog.tjs` finalize 触碰 `MainWnd.SystemObj` 即抛 Member not exist。patch F 的分支只在 `!ProgramClosing` 生效，覆盖不到这条路径。
- 修复（两处）：
  1. `OnCloseQuery()` 的 `CanCloseWork = true` 改为 `false`（程序关闭时先放弃，等待游戏 `onCloseQuery` 回调 `OnCloseQueryCalled` 再置位；未回调则不关闭）；
  2. `OnClose(CloseAction&)` 的主窗口分支（`ProgramClosing` 路径）在 invalidate 前插入 `__SWITCH__` 早退：`GalNXLog("[close] program close of main window confirmed; terminating application"); TJSNativeInstance=NULL; SetVisible(false); TVPExitApplication(0); return;`。
- 验证（g3）：☰（image 1585,916）→ 抽屉打开（`P6-g3-drawer.png`）→ 电源（image 1495,876）→ 游戏 CN 确认框「结束游戏吗？ 是 / 否 / 总是确认」（`P6-g3-powerdlg.png`，走的就是真机 bug 2 的触发路径）→ 连点「是」（image 800,530 ×3）→ glog `[close] main window close confirmed; terminating application` → Citron 回到游戏列表（`P6-g3-after-yes.png`，71,022 B），`k2s_log` 0 exception。

### Bug 3：光标过快
- 根因：patch E 摇杆步进 `step = 12.f * v * |v| + (v>0?1.f:-1.f)`。
- 修复：改为 `step = 6.f * v * |v| + (v>0?0.5f:-0.5f)`（≈旧值的 50%），并把驱动摇杆从 `JOYSTICK_LEFT` 换成 `JOYSTICK_RIGHT`。
- 验证（g2）：glog `[pad] key=1022 virt=1 cursor=0x...` 证明右摇杆已建虚拟光标；g2-02 截图里光标已淡出（`_refadeMouseCursor` 行为，patch E 原有）。

## 4. MINUS（- 键）映射修复

- 现象：MINUS 完全收不到 pad 事件（g1 无任何 `[pad]` 行，而 PLUS 正常）。
- 根因：`vendor/cocos2d-x/current-3.11.1/cocos/base/CCController-switch.cpp` 的 `kButtons[]` 没有 Minus，作者把 Minus 单独派发成 `EventKeyboard::KEY_MENU`（Android menu key 语义）→ `TVPMainScene::onPadKeyDown` 永远收不到 `BUTTON_SELECT`。
- 修复：`kButtons[]` 加 `{ HidNpadButton_Minus, Controller::BUTTON_SELECT }`，删除 KEY_MENU 派发块。
- 验证（g2）：glog `[pad] key=1022`（BUTTON_SELECT）→ `[tjs] exit -> ok` → 游戏 CN 确认框（`P6-g2-exitdlg.png`）→ 连点「是」→ `[close]` → 干净退出（`P6-g2-after-exit.png`）。

## 5. patch G 内容

增量补丁（基于 A→F 之后的源码状态）：
`E:/Othergames/Nintendo Switch/Workspace/GalNX/docs/builds/patches/k2nx-switch/G-controller-input-v2.patch`

| 文件 | 变化 |
|------|------|
| `src/core/environ/cocos2d/MainScene.cpp` | +199/−137：右摇杆光标/左摇杆滚轮、`GalNX_SendWheel`、`GalNX_EvalScript/CloseAllK2SForms/GameBack/ToggleAuto/OpenGameSaveLoad/RequestExit`、pad 映射重写、`OnClose`/`OnCloseQuery` 修复 |
| `src/vendor/cocos2d-x/current-3.11.1/cocos/base/CCController-switch.cpp` | Minus → BUTTON_SELECT，删除 KEY_MENU 派发 |

- 补丁文件：22,152 B sha256 `7cf01df0870b7d736f1047629921f675716d2cfa5c7c08d4d43c53629293d0d7`（2 文件 +199/−137）。
- 迁移性验证：把 patch G `git apply` 到 prepatch 副本 → `MainScene.cpp` 4a96f1f0…、`CCController-switch.cpp` 2e6a1fec… 与构建树逐字节一致（roundtrip PASS）。
- keymap XML v2：`keymap/Kirikiroid2Preference.patchG.xml` 1,600 B sha256 `bd9cfc34dc4461fb422da565a78098d5f33fd1e429992113442b445e8f3e3893`（相对 v1 的 1,293 B 删掉 `449→27` 与 `451→32`）。**注意**：v1 文件 `keymap/Kirikiroid2Preference.xml`（1,293 B sha `aa4fa8aa…`）仍是框架 golden oracle（`src/galnx/payload/keymap.py` 的 `GOLDEN_KEYMAP_BYTES/SHA256`、pilot payload 内置模板），patch G 的 v2 作为独立文件保存、A8 romfs 内嵌 v2，二者有意分离。
- 引擎产物（patch G 后）：ELF 113,892,192 B sha256 `db84100db08eab33a116e6632166861a118444c99080723dcec1478d59ff41d8`；NRO 42,363,510 B sha256 `012bc8116c044979e2cb6f0292e84e4ed6eb97e75e4d7fe9892efb21c3da9a72`。

## 6. 验证矩阵

| 项 | run | 证据 |
|----|-----|------|
| 右摇杆光标/半速、ZR/ZL 点击、A 推进、D-Pad、X 自动、Y 读档、PLUS 存档、B back、抽屉+Y 不冻结 | g1（`runs/20261030-193130-kirikiroid2`） | `P6-g1-loadui-from-drawer.png` a35688b4…、`P6-g1-saveui.png` 295ce56a…、`P6-g1-glog.txt` 0968ee6f… |
| MINUS 退出确认 → 干净退出 | g2（`runs/20261030-193835-kirikiroid2`） | `P6-g2-exitdlg.png` 3e4986dd…、`P6-g2-after-exit.png` e84daad0…、`P6-g2-glog.txt` 58ef948c…、`P6-g2-k2s.txt` efcbc302… |
| 抽屉电源键 → 确认 → 干净退出（bug 2） | g3（`runs/20261030-194304-kirikiroid2`） | `P6-g3-drawer.png` c28db593…、`P6-g3-powerdlg.png` 93a68436…、`P6-g3-after-yes.png` e84daad0…、`P6-g3-glog.txt` 6ccb0822…、`P6-g3-k2s.txt` ad7c0808… |
| NSP 形态首启解包 + 中文标题/正文 + MINUS 退出 | a8smoke（2026-10-30 19:52，`runs/20261030-195231-Kirikiroid2-NX-A8-CN-010047410000A000`） | `P6a-a8-titlemenu.png` 3a8ff18d…、`P6a-a8-story1.png` ee8246ac…、`P6a-a8-exitdlg.png` b6868c77…、`P6a-a8-after-yes.png` e84daad0…、`P6a-a8-k2s.txt` 42e9d5f6…、`P6a-a8-glog.txt` d6ada756… |

- 三次 run 均：`k2s_log` 0 exception、退出后 `citron.exe` 计数 0。
- 证据清单：`docs/milestones/evidence/P6.sha256`（12 行）。

## 7. A8 NSP（中文版 + patch G）

| 项 | 值 |
|----|----|
| NSP | 2,870,873,816 B sha256 `ec74b0b4e39d14d9512a1656a3066397e21b1fdc9d79d6dfed4609d8fec5755b` |
| PROVENANCE | 14,042 B sha256 `f61085e9b2c62bbdd32d585ccc5a0dbf318390d5e8cc53cc67f7aac7e1661f06` |
| manifest | `examples/pilot01-haruno-cn3.yaml`（version 1.0.7 / version_code 65543 / title_id 010047410000A000） |
| romfs | `E:/galnx-build/pilot-01/p6/romfs-a8`，109 文件 / 2,843,019,052 B；payload 23 文件 / 2,835,467,438 B（game_files.txt version=pilot01-cn3） |
| embedded keymap | 1,600 B bd9cfc34…（= 仓库 `keymap/Kirikiroid2Preference.patchG.xml`） |
| verify | `galnx package nsp verify` ok=true，19 checks = 18 ok + 1 warn（未签名，预期） |

A8 NSP 首启冒烟（`E:/galnx-build/pilot-01/p6/run-a8smoke.sh`，job 2026-10-30 19:52–19:54）：
- 首启解包：`free space check ok: 11593 MiB free for a 2704 MiB payload` → 23 文件复制完成（2704 MiB）；
- 场景链：`startup.soc → userMacro.ks → eyecatch.ks → logo.ks → title.ks（19:53:45）→ start.ks（19:54:02）→ @0000A_Z01.ks（19:54:06）`；
- 窗口标题 `Haruno CN (64-bit) | 1.0.7`，中文标题菜单与正文正常（`P6a-a8-titlemenu.png`、`P6a-a8-story1.png`）；
- MINUS（key=1022）→ `[tjs] exit -> ok` → 游戏确认框（`P6a-a8-exitdlg.png`）→ 连点「是」→ `[close] main window close confirmed; terminating application` → 干净退出（`P6a-a8-after-yes.png`），k2s 0 exception；
- 证据：`docs/milestones/evidence/P6a-a8.sha256`（6 行，titlemenu 3a8ff18d…、story1 ee8246ac…、exitdlg b6868c77…、after-yes e84daad0…、k2s 42e9d5f6…、glog d6ada756…）。

2026-10-30 20:08–20:15 真机侧安装（DBI FTP 推送）：运行 `python E:/galnx-build/pilot-01/p6/ftp_upload_a8.py` 上传 2,870,873,816 B、用时 427.5 s（6.43 MiB/s），DBI 服务端返回 WELCOME/LOGIN/UPLOAD_DONE；随后由用户在 NS1 安装 A8 1.0.7。真机验收清单见 `docs/pilot/P4-device-runbook.md` §11.2。

## 8. 限制

- L1 真机未验证：A8 需经 DBI 安装后复验（同 TitleID 会覆盖 A5/A7）。
- L2 B=back 与原需求「B=Esc」有意偏差（§2 理由）；本作 ESC 语义不可用。
- L3 右摇杆光标仍走虚拟光标（`_virutalMouseMode`），K2S 表单置顶时热键被吞是设计（先 B 关闭表单）。
- L4 左摇杆滚轮是 ±120 单步脉冲，不连续滚动；与游戏 `MouseWheelAction` 一致（上推=轮上=LOG）。
- L5 `onAxisEvent` 首行的 `PrimaryLayerArea` 早退仍在，本例走的是 `__SWITCH__` 专用分支。
- L6 K2S 抽屉图标坐标为 Citron 1728×1016 截图坐标（clickpost 前经 -11,-45 偏移），真机为触摸，不受影响。

## 9. 复现

```bash
# 构建（patch G 已落盘）
cd /e/galnx-build/pilot-01/k2nx-ws
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '/e/galnx-build/pilot-01/k2nx-ws/build-scripts/rerun_ninja.sh'
# g1/g2/g3 验证脚本
bash /e/galnx-build/pilot-01/p6/run-g1.sh   # 映射 + bug1
bash /e/galnx-build/pilot-01/p6/run-g2.sh   # MINUS 退出
bash /e/galnx-build/pilot-01/p6/run-g3.sh   # 抽屉电源键（bug2）
# A8 打包 + 校验
python /e/galnx-build/pilot-01/p6/make_a8_romfs.py
bash /e/galnx-build/pilot-01/p6/a8-build.sh
bash /e/galnx-build/pilot-01/p6/run-a8smoke.sh
```

## 10. 关联

- 上游：K2NX v1.0.1（`Erige005/Kirikiroid2-NX` HEAD e96b6034），补丁栈 A→G。
- 游戏侧关键源码：`KR/sys_source/MainWindow.tjs`（onKeyUp/EscapeWork/onCloseQuery）、`MessObject.tjs`（RightMouseUpAction/KeyUpAction/MouseWheelAction/ButtonWorkFunc AUTO）、`SaveLoadObject.tjs`（RightMouseUpAction/SaveLoadDeleteFunc）、`macro/userFix.ks`（nESC_KEY）。
- 与 patch F 的关系：F 修 OnCloseQueryCalled 路径（游戏确认后退出），G 修 ProgramClosing 路径（K2S 电源键）——两条 teardown 入口都要堵。
