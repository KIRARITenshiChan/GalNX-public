# 010 — K2NX 手柄可控虚拟鼠标 + 原生存档/读档入口（patch D / E）

> 记录时间：2026-10-30。上游：`Erige005/Kirikiroid2-NX` pin `e96b6034c292c6ccdb099823ab6a0a6b505f77f3`（v1.0.1，license NOASSERTION，不可分发）。
> 目的：让**只有手柄、没有触摸屏**的环境（真机 docked / TV 模式；以及无法向 Citron 注入鼠标/触摸的自动化测试）能完成「开菜单 + 存档/读档」，从而闭环试点的 U20 验收项。
> 结论：**PASS**。手柄完成一次完整存档 → 落盘 → 重启 → 读档 → 画面回到存档点 → 继续推进正常（模拟器层面，NRO 与 NSP 形态均验证）。

## 1. 背景：为什么必须改引擎

| 事实 | 出处 | 影响 |
| --- | --- | --- |
| K2S 抽屉 `TVPGameMainMenu` 的 `btn_gamemenu` / `btn_mousemode` 等全部是 cocos 触摸控件（`addClickEventListener`） | `src/core/environ/ui/GameMainMenu.cpp:64-127` | 手柄按键打不到抽屉 UI |
| 游戏内菜单 `TVPInGameMenuForm` 同样只有触摸 click listener，无键盘导航 | `src/core/environ/ui/InGameMenuForm.cpp` | 即使菜单打开也无法用手柄选择 |
| 虚拟鼠标模式下 A/B 只把左右键事件发给 `_currentWindowLayer->onMouseClick()` | `src/core/environ/cocos2d/MainScene.cpp:2365-2395` | 只对游戏层（KAG/TJS）有效，对 K2S 抽屉/表单无效 |
| 摇杆轴要 >0.5 才触发 `showVirtualMouseCursor()`，且 `onAxisEvent` 开头要求 `_currentWindowLayer->PrimaryLayerArea` 非空 | `MainScene.cpp:2300-2360` | 本作无 PrimaryLayerArea → 摇杆永远出不来光标 |
| 本作是自研 **BASE ADV SYSTEM**（Kazuyuki Uchino, 2008），不是标准 KAG3：无 `global.kag`、无 `Window.menu` | `extract/data/sys_source/Init.tjs`、`MainWindow.tjs` | 「打开游戏菜单」的通用入口在本作不存在，必须直接调用其原生存档 UI |

## 2. 补丁构成

两组补丁按序应用（都相对 pristine `k2nx-src`，路径前缀 `src/`）：

| 补丁 | 大小 | sha256 | 内容 |
| --- | --- | --- | --- |
| `D-virtual-mouse-dpad.patch` | 2,406 B | `11f501939e16397f15d435eda7a55365ed2fe7f1eca6a217295f552430da1dc7` | 手柄开关/移动虚拟鼠标光标（绕开 PrimaryLayerArea 早退） |
| `E-controller-ui-saveload.patch` | 20,233 B | `4ae7eda96aa425dfa359aa1e9849dd906d3aade370f1ce615a68118aeb16e85c` | 手柄直通存档/读档：原生 SAVE/LOAD UI、直接存档/读档/系统存档热键、`TVPInGameMenuForm` 键盘导航、`GalNXLog` 诊断日志 |

E 改 5 个文件（最终字节状态，CRLF）：

| 文件 | 大小 | sha256 |
| --- | --- | --- |
| `src/core/environ/cocos2d/MainScene.cpp` | 94,194 B | `4e3b75eacd1027961bef89556a1bcf8820efca1b1141c1173b7015998ccc3d15` |
| `src/core/environ/ui/InGameMenuForm.h` | 990 B | `6910d16294fbc93beff048f0ef7d6dc42875efcc57715ee23a22d15e43c8fb99` |
| `src/core/environ/ui/InGameMenuForm.cpp` | 4,994 B | `abe098d74691707cf95bbc8f4d40235b8336a2a894a63ccb254ab7bdac5cb719` |
| `src/core/environ/ui/PreferenceForm.h` | 9,495 B | `0cb41e7aa434a57c7311ca3d90c37fc68967cad82ef54d4a3c9117cf3d4c97b8` |
| `src/core/environ/ui/PreferenceForm.cpp` | 18,067 B | `48d16e783ace372060138ee79e1058ab013dbf4cf321db931056ce7f38256dfd` |

Roundtrip 验证（`E:/galnx-build/pilot-01/tmp/verifyE5`）：pristine → `git apply -p1` D → `git apply -p1` E → 5 个文件与构建副本**逐字节相同**，两个补丁 apply 均 RC 0。

### 2.1 patch D（虚拟鼠标光标，手柄可达）

在 `TVPMainScene::onPadKeyDown` 的 `#ifdef __SWITCH__` 段内：

- `BUTTON_START`（PLUS）→ `toggleVirtualMouseCursor()`（创建/隐藏 `default.cur` 光标，初始位于画面中心）；
- 光标显示时 DPAD 四向 → 按 24 px 步进移动，clamp 到 `GameNode` 内容尺寸，并调用 `_refadeMouseCursor()` + `_currentWindowLayer->onMouseMove()`；
- 保留原有 A/B → 左/右键（`onMouseClick`）。

> 后续 patch E 把「开关光标」改到 `BUTTON_Y`（PLUS 让位给 SAVE UI 热键）。

### 2.2 patch E（存档/读档直通 + 菜单键盘导航）

新增 `GalNX_QuickSaveLoad(int keyCode)`（在 `onPadKeyDown` 最先调用），全部经由 `TVPExecuteExpression`（`src/core/base/ScriptMgnIntf.cpp:660`）在 TJS 层执行：

| guest 按键 | 动作 | TJS 表达式要点 |
| --- | --- | --- |
| L (1015) | 存档到槽 1 + 系统存档 | `MainObj.f["savetitle"]="GalNX save"` → `MainObj.SaveAction(1)` → `MainObj.SystemSave()` |
| R (1016) | 打开**原生 LOAD 界面** | `s["dlg_load"]=false` → `MainObj.SaveLoadObj = new _SAVELOADOBJECT(MainObj, MainObj.PrimaryLayer, nLOAD_SC)` → `MainObj.ActiveObj = MainObj.SaveLoadObj` |
| PLUS (1021) | 打开**原生 SAVE 界面** | 同上但 `s["dlg_save"]=false` + `nSAVE_SC` |
| ZR (1018) | 直接读 10 号槽 | `MainObj.DataLoadAction(10)` |
| ZL (1017) | 只做系统存档 | `MainObj.SystemSave()` |
| X (1006) | 诊断 probe | 读 `f["lastmess"]`、`Savefolder`、缩略图尺寸等并写日志 |

同时在 `TVPInGameMenuForm` 增加键盘导航（`navMove`/`navActivate`/`updateNavVisual`，配合 `iPreferenceItem::setSelectedVisual()` 高亮）：DPAD 上下移动、A 激活 —— 对**注册了 Window.menu 的游戏**可直接用手柄操作游戏菜单；本作未注册 `Window.menu`（`TVPGetMenuDispatch()` 返回 NULL），这条路径在本作上不生效，保留给通用适配器。

诊断：`GalNXLog()` 追加写 `sdmc:/galnx-input.log`（`[pad]` / `[virt]` / `[tjs]` 行），仅用于实验取证。

## 3. 键位表（真机手柄 / Citron harness 复现）

| 功能 | guest Nintendo 键 | Citron 宿主 VK（qt-config 默认） | harness `--input-steps` |
| --- | --- | --- | --- |
| 确认 / 推进 | A | `67`（C） | `key:C` |
| 返回 / 隐藏消息窗 | B | `88`（X） | `key:X` |
| 虚拟鼠标开关 | Y | `90`（Z） | `key:Y` |
| 光标移动 | D-Pad | `37`–`40` | `key:UP/DOWN/LEFT/RIGHT` |
| 左键点击 | A（光标模式） | `67` | `key:C` |
| 右键点击 | B（光标模式） | `88` | `key:X` |
| 存档 + 系统存档 | L | `81`（Q） | `key:Q` |
| 打开 LOAD 界面 | R | `69`（E） | `key:E` |
| 打开 SAVE 界面 | PLUS | `77`（M） | `key:M` |
| 直接读槽 10 | ZR | `84`（T） | `key:T` |
| 仅系统存档 | ZL | `82`（R） | `key:R` |

> 注意：`B`/`ESC` 在本作会触发 KAG3 风格 `EscapeWork()`（`mainwindow.tjs` 在 Switch 端口有 `Member "minimized" does not exist` 异常，见 `savedata/krkr.console.log` 历史记录），因此自动化流程不要用 B 做「返回」。

## 4. 构建

构建副本：`E:/galnx-build/pilot-01/k2nx-ws`（pristine `k2nx-src` + A/B/C/D/E）。Windows 上唯一可用的构建姿势（`ar-chunk.sh` 硬编码 devkitPro MSYS2 内的 `aarch64-none-elf-gcc-ar`，git-bash 直接 ninja 会在归档 `libcocos2d.a` 时 E2BIG/127 失败）：

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  '/e/galnx-build/pilot-01/k2nx-ws/build-scripts/rerun_ninja.sh'
```

产物（2026-10-30 12:55 构建）：

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| `build/cmake-Release/kirikiroid2.elf` | 113,891,072 B | `7461bbe0b21ca0d2df926b4fe9c694430d8165951cbe68ec9bfdc805da5fd58c` |
| `build/cmake-Release/kirikiroid2.nro` | 42,363,510 B | `a84f6be0b817e22062d26df7cf4745bd38bd6341c0ef0ee88dff5b0eb0e9615c` |

> CRLF 归一的 5 个源文件重新构建后 ELF/NRO 哈希与归一前**完全相同**，证明补丁的换行处理不影响产物；A4 NSP 即由此 ELF 打包。

## 5. A4 自包含 NSP 与验收

打包命令见 `examples/pilot01-haruno.yaml` 头部注释（`galnx package nsp --build`，romfs 与 A3 相同：109 文件 / 2,878,186,922 B）。manifest `game.version` 升到 `1.0.3`。

| 项 | 值 |
| --- | --- |
| NSP | `E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-A4-010047410000A000.nsp`，2,906,135,768 B |
| NSP sha256 | `2003ec1eb1ccd78d4e74ff10965376a7248c00962262e7582258d8545fb03c39` |
| PROVENANCE | 同目录 `.PROVENANCE.json`，14,013 B sha256 `c82930ae263cb8bbd3cac4365155c4bcc521c75908e0a1253efd99980e62a978` |
| `galnx package nsp verify` | 19 checks / 18 ok / 1 warn（`verify.signature` = 未签名 homebrew 预期） |
| TitleID | `010047410000A000`（base 0x2000 对齐） |

### 5.1 存档/读档闭环（NRO 形态，S27b，2026-10-30 12:41–12:47）

run dir：`workspaces/citron-harness/runs/20261030-124145-kirikiroid2`；键序：`RIGHT+C` → 正文 →（L 存档）→ 重启 → `R` 开 LOAD UI → `Y` 光标 → DPAD 到槽位 01 01 → `A` 点击 → 直接读档 → `C` 推进 → `PLUS` 截 SAVE UI。

| 截图 | 大小 | sha256 | 内容 |
| --- | --- | --- | --- |
| `s27b-01-loadui.png` | 1,276,484 B | `bc61558c6b93013ef5406a7b36644233a9c899712dbd51a6dd6490d6b3330ad6` | 原生 LOAD 界面，槽位 01 01 有 NEW + 缩略图 + 存档标题 + 日期 |
| `s27b-03-afterclick.png` | 1,169,002 B | `c9588a2d4036755b16075a6edacad37510e78e07450bc053344e811ee8248d2f` | 点击后游戏自带 NOW LOADING |
| `s27b-04-loaded.png` | 934,366 B | `dbb367f63c43af5ccb23ff05f840cfc1676a91f87ea1c89985437955c313331d` | 回到存档点那句正文 |
| `s27b-05-adv1.png` | 908,430 B | `6d1098ae474b55244db661fce92928a4986f6b29e710c9a9832396beed666888` | 继续推进正常 |
| `s27b-07-saveui.png` | 1,219,758 B | `91559c621ced4819ed75c042d31fd14a3b131df686aa0a9fe70646f7a59ccd93` | SAVE 界面槽位 01 01 有数据 |

- 存档文件：`sdmc:/kirikiri/haruno/savedata/savedata010.bmp` 45,941 B（缩略图）+ `system.bmp` 989 B；槽位号规则 = `NowPage*10 + DataNum`，显示「01 01」即 `savedata010.bmp`。
- 日志：k2s 无 error/exception，无新增 Scenario 行（读档不重载脚本）；`krkr.console.log` 未增长。
- A4 NSP 形态的 Citron 冒烟（`--detach` + 同一键序）：见 `docs/pilot/P4-device-runbook.md` §4 与证据目录 `P3g-*`。

## 6. 限制

| # | 限制 | 说明 |
| --- | --- | --- |
| E1 | 本作无 `Window.menu` | `TVPGetMenuDispatch()` 返回 NULL，patch E 的 `TVPInGameMenuForm` 键盘导航对本作不可达（保留给注册了菜单的游戏） |
| E2 | 合成触摸不可用 | 用 `GLView::handleTouchesBegin/End` 伪造触摸会在 Citron 上导致进程硬终止（S16/S17 复现两次，无崩溃日志）；已放弃该路线 |
| E3 | 原生 UI 仍需虚拟光标 | 存档/读档界面是 TJS 图层 + 触摸按钮，只能靠 patch D 的虚拟光标 + A 点击操作 |
| E4 | `InternalKeyDown` 的 ESC 分支 bug 未修 | `MainScene.cpp` 里 `VK_ESCAPE` 走 `OnMouseDown(mbLeft)` 而 key-up 是 `OnMouseUp(mbRight)`；本作 `UseMouseKey` 为 false 时不触发，故未纳入补丁 |
| E5 | `GalNXLog` 写 SD 卡 | 每次按键追加一行到 `sdmc:/galnx-input.log`；仅实验取证用途，发布版应移除 |
| E6 | 键位绑定到本作 | 热键调用的是 BASE ADV SYSTEM 的 `MainObj.SaveAction/DataLoadAction/SaveLoadObj`；换游戏需按该作 TJS API 调整表达式 |

## 7. 复现命令（本机）

```bash
# 1) 构建（唯一姿势）
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  '/e/galnx-build/pilot-01/k2nx-ws/build-scripts/rerun_ninja.sh'

# 2) 打 A4 NSP（参数见 examples/pilot01-haruno.yaml 注释；--elf 用上面 ELF）
bash /e/galnx-build/pilot-01/p3/a4-build.sh

# 3) 独立校验
cd /e/Othergames/Nintendo\\ Switch/Workspace/GalNX && PYTHONPATH=src python -m galnx package nsp verify \
  --nsp E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-A4-010047410000A000.nsp \
  --manifest examples/pilot01-haruno.yaml --nstool E:/galnx-build/m3-tools/nstool.exe \
  --keyset 'E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys' \
  --provenance E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-A4-010047410000A000.nsp.PROVENANCE.json

# 4) Citron 存档/读档冒烟（NRO 形态；NSP 形态把 --game 换成 NSP、--expect-title Haruno）
bash /e/galnx-build/pilot-01/p3/save-exp/run-s27b.sh
```
