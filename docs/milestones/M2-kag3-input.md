# M2-c：KAG3 输入语义取证与键位映射基线（只读）

- 任务：task-18（M2-c：KAG3 输入语义取证与语义映射基线文档）
- 执行：audit-engines（Team Lead: lead）
- 日期：2026-10-30
- 证据等级：**source-inspected + Citron 模拟器实测（E2）**（源码逐行实读 E1；2026-10-30 用 M2-a harness 在 Citron main-0237a9b88 完成注入实测，结果见第 8 节；真机仍未验证）
- 取证对象：KAG 3.x 运行时（krkrsdl2 上游 DEMO 内容 external/kag3）+ krkrsdl2 上游 Switch 输入桥（HEAD 124bdf84）
- 只读声明：本文件仅基于本机源码与配置文件的静态阅读，未修改任何上游源码、未运行构建、未执行任何游戏数据操作。

被测基线（全部本机实测，UTC 之外按 +08:00 记录）：

| 对象 | 版本/提交 | 本机路径 |
| --- | --- | --- |
| krkrsdl2 上游 | HEAD 124bdf841f09e7ce02aa99b7b55791a0f7a900ff（commit 2026-09-30T22:11:23-05:00） | E:/galnx-build/m1-krkrsdl2 |
| KAG3 DEMO 内容仓库（krkrsdl2-kag3-demo） | HEAD 56b5ec7aacf09bb8e0095192dfb423d1dfd93046（2025-03-16） | E:/galnx-build/m1-content/demo |
| KAG3 引擎脚本子模块 external/kag3 | b21b16ea684a3274488282687ca4184df49bec9f | E:/galnx-build/m1-content/demo/external/kag3 |
| 构建产物 NRO（参照） | build5/krkrsdl2.nro 17,907,245 B sha256 e324c2d0…（M1-c） | E:/galnx-build/m1-krkrsdl2/build5 |

---

## 0. 结论摘要（TL;DR）

1. **推进文本（advance_text）的唯一语义出口是 `conductor.trigger('click')`。** 引擎在等待点注册 `conductor.wait(%[click: ...])`（返回码 -2 即 break），任何最终进入 `KAGWindow.onPrimaryClick()` 的输入（鼠标左键 down、触摸、键盘 Enter/Space 经 `checkProceedingKey`）都会解除等待并 `run()` 继续标签循环。
2. **选项/分支（confirm_choice）在本 DEMO 中不是 [select] 标签，而是 [link …][endlink]。** 鼠标命中链接 → `MessageLayer.processLink(n)` → `window.process(storage,target,countPage)` → `conductor.goToLabel()` + `run()`；键盘路径为 `MessageLayer.onKeyDown` 中 `VK_SPACE/VK_RETURN → processLink(keyLink)`，用方向键/TAB 在链接间聚焦。
3. **KAG 标签循环的返回码语义已完整取证**（Conductor.tjs L109-166）：-5 事件后回填重试、-4 丢弃当前标签、-3 回填后 break、-2 break（不回收）、-1 剧本结束；正返回值 = 下一个定时器间隔（毫秒，即打字速度/等待时长）。
4. **Switch 手柄映射（krkrsdl2 上游）**：VK_PAD1=A→VK_RETURN、PAD2=B→VK_ESCAPE、PAD3=X→显示历史、PAD4=Y（未映射）、十字键→VK_LEFT/UP/RIGHT/DOWN。**摇杆轴（SDL_CONTROLLERAXISMOTION）在 src/core/sdl2 中完全未处理** → 上游不支持摇杆当鼠标/或当方向键。
5. **重大缺口：KAG3 系统菜单在 krkrsdl2 下不可显示。** 因为 `Window.menu` 由 system_polyfill/MenuItem_stub.tjs（L3、L21-26、L29）提供，`add/insert/remove/popup` 全为空函数 → Menus.tjs 构建的菜单只存在于内存中，`popup()` 不绘制。**但** `KAGMenuItem.click()`（Menus.tjs L191-205）仍会执行 `command(this)`，因此键盘快捷（S/L/A/B/F/R/ESC）通过 `processKeys` 直接 `click()` 依然可用。**结论：Switch 上必须由 GalNX 提供菜单/存档 UI，或把 KAG3 快捷键映射到手柄组合键。**
6. **右键≠菜单**：`onPrimaryRightClick()`（MainWindow.tjs L2833-2855）默认行为是「隐藏消息层」；进入菜单记录的入口是 `VK_ESCAPE`（processKeys L3856-3917 → `rightClickMenuItem.click()`，其 command 也是 `onPrimaryRightClick`）。
7. **输入层必须提供「按住状态快照」而非仅边沿事件**：KAG3 的 `checkProceedingKey`（L3929-3961）用 `getKeyState` 轮询当前是否按住 Enter/Space，长按重复（`shift & ssRepeat`）触发早送り `skipToStop2()`；`processKeys` 用 `getKeyState` 判断 Ctrl/Shift 组合。
8. **Citron 键盘映射已实测**（见 §2.2）：A/B/X/Y = C/X/V/Z，PLUS/MINUS = M/N，十字键 = 方向键（16777234-37），左摇杆 = Shift+W/A/S/D（analog_from_button）。
9. **`@s` 页的推进必须走「选择」而不是「推进」**：`s` handler（MainWindow.tjs L5116-5131）置 `inSleep=true` 并 `return -1`，Conductor 把它当「シナリオ終了」→ 停止标签循环并 `onStop()`；此后 Enter/Space/C 的 `onPrimaryClick()` 只会 `trigger('click')`，而 conductor 已不在 `mWait`（L410-431 直接返回 false）→ **无效**。恢复执行只能由链接选择 `window.process(...)` → `conductor.run()` 完成。因此本 DEMO 的首屏（first.ks L99 `@s`）不能用推进键离开，必须先选中链接。
10. **【2026-10-30 实测确认】** Citron main-0237a9b88 内运行 M1-c NRO，advance_text（A/C 键）与 ESC 隐藏消息层均实测生效且像素级可往返：A 0.556076（0.7186→0.7211）、B 0.556076（→0.7186）、再 A 0.556076；标题页链接点击 0.494465、方向键焦点移动 0.0074/0.0165、A 确认 0.554372。详见第 8 节。
11. **【2026-10-30 实测负面发现】** X 键（PAD3 → showHistoryByKey）在本 DEMO 上无可见变化（diff 0.000000/0.0002）；源码路径存在，但历史层可能未启用/未写入，不能据此否定真机行为（U12）。
12. **【实测边界】Switch 上无法触达 KAG3 的键盘快捷键（F/A/B/R/S/L）与系统菜单**：输入只以手柄按钮到达引擎（只合成 RETURN/ESC/方向/历史函数），且 MenuItem 为 stub；因此存档/读档/自动/回退的 UI 入口必须由 GalNX（或 krkr-ns 启动器）提供。

---

## 1. 证据分级与取证范围

### 1.1 分级定义

| 级别 | 定义 | 本文件使用情况 |
| --- | --- | --- |
| E1 | 本机源码/配置文件逐行实读，给出绝对路径与行号 | 主体证据（§3 全部链路） |
| E2 | 上游官方 README/文档原文 | 仅用于 KAG3 是 KAG 3 系、krkrsdl2 平台支持等背景 |
| E3 | 社区二手描述（论坛/issue） | 未使用 |
| E4 | 推断/未验证（含运行时行为预测） | 集中在 §6 未验证清单 |

### 1.2 实读文件清单（E1）

| 文件 | 大小/行数 | 作用 | 本机绝对路径 |
| --- | --- | --- | --- |
| MainWindow.tjs | 5,931 行 | KAGWindow（Window 子类）、标签处理器注册表、键/鼠标分派、skip/auto/存档入口 | E:/galnx-build/m1-content/demo/external/kag3/data/system/MainWindow.tjs |
| MessageLayer.tjs | 约 2,400 行 | 链接（link）命中、点击处理、消息层键盘导航 | E:/galnx-build/m1-content/demo/external/kag3/data/system/MessageLayer.tjs |
| Conductor.tjs | 532 行 | KAG 主循环 timerCallback、等待/触发、返回码 switch | E:/galnx-build/m1-content/demo/external/kag3/data/system/Conductor.tjs |
| KAGParser.tjs（polyfill） | 2,590 行（69,325 B） | 剧本解析器（krkrsdl2 无原生 KAGParser，使用该 polyfill） | E:/galnx-build/m1-content/demo/external/kag3/data/system_polyfill/KAGParser.tjs |
| MenuItem_stub.tjs（polyfill） | 31 行（451 B） | `Window.menu` 的空实现（菜单不可显示的根因） | E:/galnx-build/m1-content/demo/external/kag3/data/system_polyfill/MenuItem_stub.tjs |
| Menus.tjs | 213 行 | KAGWindow_createMenus、KAGMenuItem.click() | E:/galnx-build/m1-content/demo/external/kag3/data/system/Menus.tjs |
| Config.tjs | 766 行 | 速度/等待/菜单可见性默认模板（多为注释行） | E:/galnx-build/m1-content/demo/external/kag3/data/system/Config.tjs |
| Initialize.tjs | 约 240 行 | 启动顺序：KAGLoadScript 列表、new KAGWindow() | E:/galnx-build/m1-content/demo/external/kag3/data/system/Initialize.tjs |
| SDLApplication.cpp | 3,370 行（92,886 B） | Switch 端 SDL2→TJS VK 键/鼠标/触摸/手柄桥 | E:/galnx-build/m1-krkrsdl2/src/core/sdl2/SDLApplication.cpp |
| first.ks / snow.ks | 628 / 283 行 | DEMO 剧本：链接菜单、[l]/[p]/[r] 等待点的实际用法 | E:/galnx-build/m1-content/demo/data-demo/scenario/first.ks |
| qt-config.ini（Citron） | 1,376 行 | Citron 模拟器键盘→Switch 手柄映射 | C:/Users/<user>/AppData/Roaming/citron/config/qt-config.ini |

> 说明：KAG3 侧文件名在 system/ 与 system_polyfill/ 的差异是本次取证的关键：**krkrsdl2/krkrz 均不含 KAGParser 与 MenuItem 的原生实现**，DEMO 由 polyfill 提供（`grep KAGParser` 在 E:/galnx-build/m1-krkrsdl2 全树 0 命中；`grep MenuItem` 在 krkrz 全树仅命中 win32/android 的平台消息字符串）。

---
## 2. 键位 ↔ 语义映射表

### 2.1 Switch 手柄（krkrsdl2 上游 -> KAG3）

映射分两层：① SDL2 手柄按钮 -> TJS VK_PAD（SDLApplication.cpp L134-147）；② VK_PAD -> 键盘 VK（MainWindow.createPadKeyMap L663-697）。KAG3 逻辑层只认第二层的键盘 VK。

| Switch 键 | TJS 键值（第一层） | KAG3 内生效键（第二层） | 语义 | 证据（文件:行号） |
| --- | --- | --- | --- | --- |
| A | VK_PAD1 | VK_RETURN | 推进文本/确认选项 | SDLApplication.cpp L134-147；MainWindow.tjs L673-684；checkProceedingKey L3929-3961 |
| B | VK_PAD2 | VK_ESCAPE | 「メッセージを消す」（隐藏消息层），非菜单 | 同上；processKeys L3856-3917；onPrimaryRightClick L2833-2855 |
| X | VK_PAD3 | 直接调用 showHistoryByKey | 显示历史记录（Citron 实测无可见变化，见 8.2 用例 6 / U12） | MainWindow.tjs L673-684（PAD3 映射为函数）；L3977-4003 |
| Y | VK_PAD4 | 无映射 | 无 | createPadKeyMap L673-684 |
| 十字 上/下/左/右 | VK_PADUP/DOWN/LEFT/RIGHT | VK_UP/DOWN/LEFT/RIGHT | 链接聚焦导航；消息层内方向键 | MainWindow.tjs L673-684；MessageLayer.onKeyDown L2311-2378 |
| L / R | VK_PAD5/6（LEFTSHOULDER/RIGHTSHOULDER） | 无映射 | 无（KAG3 未绑定） | SDLApplication.cpp L134-147；L673-684 无 PAD5/6 |
| ZL / ZR | 未在 src/core/sdl2 中发现显式 VK_PAD 映射（SDL 标准序 LEFTSHOULDER/RIGHTSHOULDER 对应 VK_PAD5/6） | 无映射 | KAG3 未绑定 | SDLApplication.cpp L134-147；MainWindow.tjs L673-684 无 PAD5/6 |
| + / − | VK_PAD7/PAD8？ | 无映射 | KAG3 未绑定（PAD7/8 未进 padKeyMap） | SDLApplication.cpp L134-147；MainWindow.tjs L673-684（未验证 U4） |
| 左摇杆 | 轴事件 | **无处理** | 上游 krkrsdl2 不把摇杆映射为鼠标或方向键 | 全树 grep SDL_CONTROLLERAXIS / SDL_JoystickGetAxis 0 命中 |

**关键细节（原文）**：createPadKeyMap L663-697 注释「十字キーはキーボードのカーソルキーにマッピング、ボタン1 は Return、ボタン2 は ESC、ボタン3 は メッセージ履歴の表示」；反向 `padKeyMapReverse` 使 `getKeyState(键盘键)` 能感知对应手柄键（L699-713），这是「按住手柄 A 也算按住 Enter」的依据。

### 2.2 Citron 模拟器键盘映射（实测 C:/Users/<user>/AppData/Roaming/citron/config/qt-config.ini）

| Switch 键 | 键盘键 | Qt key code | 配置行 |
| --- | --- | --- | --- |
| A | C | 67 | L280 player_0_button_a |
| B | X | 88 | L282 |
| X | V | 86 | L284 |
| Y | Z | 90 | L286 |
| L | Q | 81 | L292 |
| R | E | 69 | L294 |
| ZL | R | 82 | L296 |
| ZR | T | 84 | L298 |
| PLUS | M | 77 | L300 |
| MINUS | N | 78 | L302 |
| 十字 左/上/右/下 | ←/↑/→/↓ | 16777234 / 16777235 / 16777236 / 16777237 | L304-L310 |
| 左摇杆 | Shift + A/W/D/S（analog_from_button，modifier=16777248=Qt::Key_Shift） | 65/87/68/83 | L324 |
| 右摇杆 | I/J/K/L（无 modifier） | 73/74/75/76 | L326 |
| L3 / R3 | F / G | 70 / 71 | L288 / L290 |

其他实测配置：`keyboard_enabled=false`（L69，键盘不作为 Citron 的 Profile 输入源，而是走按键映射）；`emulate_analog_keyboard=false`（L67）；`player_0_motionleft=55`、`player_0_motionright=56`（L328/L330）。

> **重要含义**：用 SendInput 向 Citron 窗口注入键盘时，能直接触达的 KAG3 语义只有「A/B/X + 十字方向」这 6 个（即推进、隐藏消息层、历史、上下左右链接导航）。**skip/auto/back/save/load 在默认映射下无法用手柄键触发**（KAG3 把它们绑在键盘 F/A/B/S/L/R/ESC 上，而手柄层只映射了 PAD1/PAD2/PAD3/DPAD）。

### 2.3 键盘（PC 侧 KAG3 原生）+ 鼠标语义

| 输入 | KAG3 语义 | 证据（文件:行号） |
| --- | --- | --- |
| Enter / Space（单击） | 推进（onPrimaryClickByKey） | checkProceedingKey L3929-3961；onPrimaryClickByKey L3829-3835 |
| Enter / Space（按住重复） | 早送り（skipMode=4，skipToStop2） | L3943-3956（shift & ssRepeat -> skipToStop2） |
| 鼠标左键 down/up | 推进（onPrimaryClick） | onMouseDown L4037-4060；onPrimaryClick L3783-3827 |
| 鼠标右键 | 隐藏消息层（默认）；若左键同时按住则进入自动模式 | onPrimaryRightClick L2833-2855 |
| 滚轮上 | 打开历史 | onMouseWheel L4012-4035（delta>0 -> showHistoryByKey） |
| 滚轮下 | 推进 | 同上（delta<0 且距上次隐藏 >150 tick -> onPrimaryClick） |
| F | skipToNextStopByKey（跳到下一停止点） | processKeys L3856-3917 |
| B | goBackByKey（回退） | 同上 |
| A | switchAutoModeByKey（自动模式） | 同上 |
| R 或 Shift+Up | showHistoryByKey（历史） | 同上 |
| S / L | storeMenu.click / restoreMenu.click（存档/读档，需 freeSaveDataMode） | 同上 |
| ESC | rightClickMenuItem.click（= 隐藏消息层） | 同上 |
| Ctrl（按住）+ 点击 | 键盘操作判定（隐藏鼠标光标） | MessageLayer.processClick L423-438；processLink 内 getKeyState 检查 VK_RETURN / VK_SPACE |
| ↑↓←→ / TAB | 链接间焦点移动（Keyboard focus） | MessageLayer.onKeyDown L2311-2378 |

---
## 3. 完整输入链路（源码级）

### 3.1 KAG 主循环与等待模型（Conductor.tjs）

主循环是 `Timer` 驱动的 `timerCallback()`（Conductor.tjs L55-189）：

1. `for(;;)` 循环内优先取 `pendings[0]`（L72-76），否则 `obj = getNextTag()`（L81）。
2. `obj === void` → 剧本结束：`timer.enabled=false; onStop(); return`（L91-100）。
3. `var step = onTag(obj)`（L104）→ `onTag` 查 `handlers[tagname]`（L433-445），返回 step。
4. step 语义（L109-166）：

| step | 语义原文 | 引擎行为 | 输入相关性 |
| --- | --- | --- | --- |
| 0 | ウェイトを掛けずに次へ | `timer.interval=0; continue` | 无 |
| -1 | シナリオ終了 | `timer.enabled=false; onStop()` | 无 |
| -2 | ブレーク | `timer.interval=0; return`（标签已处理，不回填） | **等待点：等输入触发 trigger** |
| -3 | 後回ししてブレーク | `pendings.insert(0,obj); return`（自动翻页清屏用） | 定时器/点击均可能 |
| -4 | いったんイベントを処理 | `oneshot.trigger(); return`（丢弃当前标签） | 让输入/重绘先跑 |
| -5 | いったんイベントを処理(現在のタグは後回し) | `pendings.insert(0,obj); oneshot.trigger(); return` | 同 -4 但保留标签 |
| >0 | 定时器间隔 | `timer.interval=step`（毫秒） | 打字速度/等待时长 |

等待模型（Conductor 子类，L331-469）：`wait(until)` 把 `status` 设为 `mWait` 并 `stop()`，再 `Dictionary.assign` 到 `waitUntil`；`trigger(name)`（L410-431）检查 `status==mWait`，执行回调、清空 `waitUntil`、然后 `run()` 重新启动标签循环。**这就是「任何点击/按键最终都收敛到 trigger('click')」。**

> 补充：`KAGParser`（剧本解析）由 system_polyfill/KAGParser.tjs 提供（class __internal_KAGParser L211、class KAGParser L2070、_getNextTag L1170-1801、getNextTag L1989-1997）；krkrsdl2/krkrz 仓库内均无原生实现。

### 3.2 推进文本（advance_text）

等待点有三类，均注册 click 回调：

| 标签/函数 | 注册点 | 证据 |
| --- | --- | --- |
| [l] 行クリック待ち | `showLineBreak(elm)` → `conductor.wait(%[click: ...])` | MainWindow.tjs L4977-4981（handler l）、L4118-4163 |
| [p] ページクリック待ち | `showPageBreak(elm)` → 同上 | MainWindow.tjs L4983-4988（handler p）、L4165-4201 |
| [wait]/[wc] | `doWait` 把 `waitTime(waittime,canskip)` 注册 `waitWithTimeOut` 或 `wait` | MainWindow.tjs L5168-5184、L3579-3615、L3617-3642 |
| [r] 改行 | `current.processReturn()`，必要时 `showPageBreakAndClear()`（返回 -5/-3） | MainWindow.tjs L4814-4830、L4203-4265 |

鼠标路径：`MainWindow.onMouseDown(x,y,button)`（L4037-4060）→ 光标在画面外时 `mbLeft -> onPrimaryClick()`；`onPrimaryClick()`（L3783-3827）：clickCount++ → `callHook(leftClickHook)` → 若消息层被用户隐藏则 `showMessageLayerByUser()` → 否则处理 auto/skip 取消，最后 `conductor.trigger('click')`，未处理且 `st==runst` 时 `skipToClick()`。

键盘路径：`MainWindow.onKeyDown(key,shift)`（L4005-4010）→ `internalOnKeyDown`（L3919-3927）→ `preProcessKeys`（keyDownHook）→ `processKeys`（L3856-3917）→ `checkProceedingKey(key,shift)`（L3929-3961）：仅 `VK_RETURN` 或 `supportReadingKey`（默认 `VK_SPACE`，L214）有效，且必须 `getKeyState` 确认按住；单击 → `onPrimaryClickByKey()`（L3829-3835，onPrimaryClick + hideMouseCursor）；按住重复（`shift & ssRepeat` 且 `clickSkipEnabled`）→ `skipToStop2()` 早送り。

手柄路径：SDL_CONTROLLERBUTTONDOWN（SDLApplication.cpp L2743-2760）→ `sdl_gamecontrollerbutton_to_vk_key(A)=VK_PAD1` → KAGWindow.action（L717-739）把 VK_PAD* 经 `padKeyMap` 转成 `VK_RETURN` 的 onKeyDown → 上述键盘路径。

### 3.3 选项 / 分支（confirm_choice，[link] 模型）

本 DEMO **没有 [select]/[endselect] 标签**（first.ks 标签统计：r 127、l 124、p 34、link 24、endlink 24、font 16、resetfont 16、ruby 14、s 8、style 4、emb 4、graph 2、edit 2、i 1），选项全部是链接文本：

- first.ks L77-86：六个 `[link target=*about_...]…[endlink][r]` 菜单项；L624 `[link target=*to_syokai_start]Return to the menu[endlink]`。
- 注册：`link` handler（MainWindow.tjs L4888-4894）→ `current.beginHyperLink(elm)`；`endlink`（L4896-4902）→ `current.endHyperLink(elm)`。
- 鼠标选中：`MessageLayer.internalOnMouseDown`（L2131-2161）→ `findLink(x,y)`（L1677-1698）≠ -1 → `processLink(n)`（L1991-2014）：`Scripts.eval(ln.exp)`（若有 exp）→ `window.lockMessageLayerSelProcess()` → `window.process(ln.storage, ln.target, ln.countPage)`。
- 键盘选中：`MessageLayer.onKeyDown`（L2311-2378）：`VK_SPACE/VK_RETURN` → 若 `keyLink==-1` 则（hasClick→processClick，否则 window.checkProceedingKey）；否则 `processLink(keyLink)`。焦点移动：`VK_UP/Shift+TAB` 上一链接、`VK_DOWN/TAB` 下一链接（边界回绕），竖排时左右互换。
- 执行：`KAGWindow.process(file,label,countpage,immediate)`（L2412-2441）：`conductor.loadScenario(file)`（若 file 非空）→ `conductor.goToLabel(label)`（若 label 非空）→ `conductor.run(immediate)`。

> 结论：在 GalNX 侧，「确认选项」不需要模拟鼠标坐标，只要把「上/下/确认」映射为方向键 + Enter，就能复用 KAG3 自带的 `keyLink` 焦点链路（MessageLayer L2311-2378）。

### 3.4 菜单 / 系统 UI

- 菜单结构在 Menus.tjs `KAGWindow_createMenus()`（L4 起）：systemMenu（右クリックメニュー）、showHistoryMenuItem、skipToNextStopMenuItem、autoModeMenuItem、goBackMenuItem、goToStartMenuItem、exitMenuItem、characterMenu（chSpeed）、bookMarkMenu、restoreMenu、storeMenu、displayMenu、helpMenu、debugMenu。
- **显示层缺失**：system_polyfill/MenuItem_stub.tjs L3 `class MenuItem`，L21-26 `add/insert/remove/popup/onClick/fireClick` 全空，L29 `global.Window.menu = new MenuItem()` → 菜单永远不可见、`popup()` 无效果。
- **但命令层仍在**：KAGMenuItem.click()（Menus.tjs L191-205）执行 `command(this)`（字符串则 `Scripts.eval`），因此 processKeys 的快捷键路径可直接触发菜单项命令（F/A/B/R/S/L/ESC）。
- ESC 的具体目标：processKeys（L3856-3917）中 `VK_ESCAPE -> rightClickMenuItem.click()`，而其 command `onRightClickMenuItemClick`（MainWindow L764-767）= `onPrimaryRightClick()`（L2833-2855）→ 默认 `switchMessageLayerHiddenByUser()`（隐藏消息层）；`rightClickEnabled` 默认 true（L192）。

### 3.5 存档 / 读档

| 入口 | 实现 | 证据 |
| --- | --- | --- |
| 玩家快捷键 S（存档） | `storeMenu.click()` | MainWindow.processKeys L3856-3917 |
| 玩家快捷键 L（读档） | `restoreMenu.click()` | 同上 |
| 剧本标签 [save]/[load] | `saveBookMark(+elm.place)` / `loadBookMark(+elm.place)`，返回 -4 | MainWindow L5320-5328 / L5310-5318 |
| 書簽（bookmark）启用 | [store] → `setStoreEnabled(+elm.enabled)` | MainWindow L5303-5308 |
| 回退/回到开头 | [goback] → `goBack()`；[gotostart] → `goToStart()` | L5347-5355 / L5337-5345 |

> 注意：S/L 快捷键依赖 `freeSaveDataMode`（未取证默认值，列入 U9）；Switch 默认映射下**无手柄键可触发存档/读档**。

### 3.6 快进 / 自动 / 历史 / 回退

| 语义 | 入口 | 状态机 | 证据 |
| --- | --- | --- | --- |
| 快进到点击/页/停止 | `skipToClick/skipToPage/skipToStop/skipToStop2` | `skipMode` 0/1/2/3/4（4=早送り） | MainWindow L147-149、L3482-3518 |
| 取消快进 | `cancelSkip()`（点击判定 `canCancelSkipByClick`） | skipMode==4 时清 `skipKeyRepressed` | L3482-3518、onPrimaryClick L3783-3827 |
| 自动模式 | `enterAutoMode/cancelAutoMode/switchAutoModeByKey` | 自动翻页等待 `autoModePageWait` | L2833-2855、L3977-4003；Config L161-173 |
| 历史 | `showHistoryByKey/showHistoryByScenario` | 历史层 | MainWindow L3977-4003、L5193-5200；滚轮上 L4012-4035 |
| 回退 | `goBackByKey` → goBackMenuItem.click | 回退一层 | L3977-4003、L5347-5355 |

速度默认（Config.tjs，模板注释值）：`chSpeeds.fast=10 / normal=30 / slow=50`（ms/字，L155-157）；autoModePageWaits fast 400 / faster 700 / medium 1000 / slower 1300 / slow 2000（L161-165）；autoModeLineWaits 180/240/300/360/500（L169-173）。

### 3.7 Switch 输入桥（SDLApplication.cpp，krkrsdl2 上游）

| SDL 事件 | 转换 | TJS 事件 | 证据行号 |
| --- | --- | --- | --- |
| SDL_MOUSEMOTION | 坐标 | tTVPOnMouseMoveInputEvent | L2646-2654 |
| SDL_MOUSEBUTTONDOWN/UP | LEFT→mbLeft / RIGHT→mbRight / MIDDLE→mbMiddle；DOWN 发 OnMouseDown；UP 若 clicks>=2 发 OnDoubleClick 否则 OnClick，再发 OnMouseUp | OnMouseDown/OnClick/OnDoubleClick/OnMouseUp | L2655-2711 |
| SDL_MOUSEWHEEL | 方向/幅度 | OnMouseWheel | L2712-2717 |
| SDL_FINGERMOTION/DOWN/UP | 归一化坐标（tfinger.x/y ∈ 0..1） | OnTouchMove/OnTouchDown/OnTouchUp | L2718-2736 |
| SDL_MULTIGESTURE | 手势 | 手势事件 | L2737-2742 |
| SDL_CONTROLLERBUTTONDOWN/UP | 按钮→VK_PAD；DOWN 发 OnKeyDown；UP 若非文本输入发 OnKeyPress+OnKeyUp | OnKeyDown/OnKeyPress/OnKeyUp | L2743-2760 |
| SDL_KEYDOWN | keysym→VK；repeat 时置 TVP_SS_REPEAT；Shift/Ctrl/Alt 额外补发修饰键事件 | OnKeyDown | L2761-2797 |
| SDL_KEYUP | 同上 | OnKeyUp | L2798+ |
| SDL_CONTROLLERAXISMOTION | **未处理** | 无 | grep 0 命中 |

按键映射函数：`sdl_key_to_vk_key` L322-450+（RETURN L330、ESCAPE L333、SPACE L334、方向键 L339-342、数字 L349-358、a-z L359-384、小键盘 L388-402、F1-F24 L403-426）；`sdl_gamecontrollerbutton_to_vk_key` L134-147；`getKeyState` 走 `SDL_GetKeyboardState`（L3108）。

---
## 4. 引擎适配输入需求（面向 M4/M5 键位抽象）

判据：某个动作若 **KAG3 无法用已映射的手柄键触达**，则必须由 GalNX 输入层或上层 UI 兜底；否则可只透传。

### 4.1 必须动作（MVP 不可缺）

| 动作 ID | 语义 | KAG3 依据 | krkrsdl2 默认可否用 Switch 键触达 | GalNX 要求 |
| --- | --- | --- | --- | --- |
| `advance` | 推进对话/确认 | onPrimaryClick L3783-3827；checkProceedingKey L3929-3961 | 可以（A=RETURN，按住=早送り） | 透传 + 保留 repeat 标志 |
| `select_up` / `select_down` | 选项上下移动 | MessageLayer.onKeyDown L2311-2378；createPadKeyMap L673-684 | 可以（十字键） | 透传方向键事件 |
| `confirm` | 确认选项 | MessageLayer.onKeyDown L2311-2378（VK_SPACE/RETURN → processLink） | 可以（A=RETURN） | 同 advance |
| `cancel` / `hide_ui` | 隐藏消息层（右键语义） | onPrimaryRightClick L2833-2855；processKeys ESC→rightClickMenuItem | 可以（B=ESCAPE） | 需明确「隐藏 UI」语义（不是返回菜单） |
| `history` | 历史记录 | showHistoryByKey L3977-4003；PAD3 直绑 | 可以（X） | 透传 |
| `quit_to_launcher` | 返回启动器（krkr-ns 场景） | KAG3 无（exitMenuItem 才是 [終了]） | **不可以** | GalNX 自定义（如 HOME/PLUS 长按） |
| `system_menu` | 打开 GalNX 菜单 | KAG3 菜单在 krkrsdl2 下不可显示（§3.4） | **不可以** | **GalNX 自建 overlay UI**（存档/读档/设置/退出） |

### 4.2 可默认动作（可后置或映射为组合键）

| 动作 ID | 语义 | KAG3 依据 | 默认可达性 | 建议 |
| --- | --- | --- | --- | --- |
| `skip` | 快进到下一停止点 | processKeys F；skipToStop L3482-3518 | 键盘 F 可达，手柄不可达 | 映射到 ZR 或长按 A（KAG3 长按 A 已是早送り） |
| `auto` | 自动模式 | processKeys A；switchAutoModeByKey | 手柄不可达 | 映射到 PLUS 或菜单项 |
| `back` | 回退 | processKeys B；goBackByKey | 手柄不可达 | 映射到 MINUS |
| `save` / `load` | 存档/读档 | processKeys S/L（需 freeSaveDataMode） | 手柄不可达 | GalNX 存档 UI（避免与 KAG3 書簽语义冲突） |
| `ctrl_skip` | Ctrl 加速/键盘操作态 | MessageLayer.processClick L423-438 | 无条件键 | 可用 ZL 模拟修饰键 |
| `mouse_move` | 指针/触屏 | SDL_MOUSEMOTION / SDL_FINGER* | 触屏原生可达 | 触屏点击即 advance（KAG3 无独立指针 UI） |

### 4.3 对输入层的关键契约（从源码倒推）

1. **事件 + 状态双通道**：KAG3 同时使用边沿事件（onKeyDown/onMouseDown）与 `getKeyState` 轮询（L699-713、L3929-3961、L3963-3975）→ GalNX 输入层必须能提供「当前按住的物理键集合」快照，且**与事件源同一帧内一致**。
2. **重复/长按标志**：SDL_KEYDOWN 的 `event.key.repeat` 被映射为 `TVP_SS_REPEAT`（SDLApplication.cpp L2761-2797），KAG3 用它触发早送り（L3943-3956）→ 输入层需保留 repeat 标志；自研输入映射不要「吞掉」重复事件。
3. **修饰键**：Shift/Ctrl/Alt 由 SDL 层自动补发（L2775-2794），KAG3 用 Ctrl 判定键盘操作（MessageLayer L423-438）→ 组合键映射时需同时产生修饰键事件。
4. **触摸归一化坐标**：SDL_FINGER* 事件 x/y ∈ [0,1]（L2718-2736），而 KAG3/窗口层期望像素坐标 → 若启用触屏，需在桥接层换算成 1280x720 像素（未验证 KAG3 是否处理 OnTouch*）。
5. **手柄按钮时钟序**：DOWN 发 OnKeyDown、UP 发 OnKeyPress+OnKeyUp（L2743-2760），且 UP 时才判定「非文本输入」→ 输入层不得把 DOWN/UP 合并成单个 click 再注入。

---

## 5. 对 GalNX input 数据模型（task-17 / src/galnx/input）的建议

1. **语义动作枚举与设备解耦**：以 §4 的动作 ID 为唯一键（advance/confirm/cancel/select_*/history/skip/auto/back/save/load/system_menu/quit_to_launcher），设备映射表（手柄/键盘/触摸）独立配置，可运行时重绑。
2. **两套事件模型**：`ActionEvent`（离散：press/repeat/release）与 `ActionState`（快照：按下的动作集合，供 `getKeyState` 轮询等价物）。KAG3 适配器需要把 ActionState 翻译成对应 VK 键的按键集合再交给引擎。
3. **默认 profile 必须包含「手柄可达性补丁」**：因为 krkrsdl2 上游未把 PLUS/MINUS/ZL/ZR 映射到 KAG3 动作，GalNX 侧默认 profile 应补：PLUS→system_menu、MINUS→back、ZR→skip（或长按 advance）、ZL→ctrl_skip。
4. **不要复用 KAG3 的菜单实现**：MenuItem_stub 为空实现（§3.4），任何「存档/读档/设置」UI 都应由 GalNX 的 overlay 提供；KAG3 的 S/L 快捷键仅作为兼容兜底。
5. **可测试性**：任务板 M2 需要「注入 → 画面变化」的自动化证据，建议 input 模块提供 `--input-script`（动作序列 + 时间戳）重放入口，便于 Citron harness 驱动（与 M2-a SendInput 路径解耦）。

---

## 6. 未验证 / 限制（U1–U13）

| 编号 | 项 | 状态/影响 |
| --- | --- | --- |
| U1 | 真机（Atmosphère）上的输入行为 | **未验证**：本次证据全部来自 PC 侧源码与 Citron 配置，Switch 真机未测试 |
| U2 | Citron 注入实测（SendInput -> KAG3 推进/选项） | **已完成 2026-10-30**：scripts/citron_run.sh（35,916 B）含 --input-click/--input-keys；实测见第 8 节（advance 0.556076、ESC 0.556076、焦点 0.0074/0.0165、确认 0.554372） |
| U3 | 触摸事件到 KAG3 的映射 | SDL_FINGER*→OnTouch* 存在（L2718-2736），但 KAG3 层未找到 onTouch 处理；是否被 TVP 转为鼠标事件未验证 |
| U4 | ZL/ZR/PLUS/MINUS 在 Switch SDL2 下的具体按钮索引 | 未在真机/模拟器验证（SDL 标准序推断 PAD5/6/7/8） |
| U5 | krkr-ns 启动器与 KAG3 的按键争用 | krkr-ns 启动器用 A/B/翻页（README 声称），进游戏后同一物理键交给引擎；切换时序未验证 |
| U6 | 字体缺失风险 | DEMO 默认 MS Gothic/MS PMincho（KAG3 system/Config.tjs），Switch 无系统字体；M1-d 已换 data-withfont.xp3，但本文件未验证渲染 |
| U7 | 「菜单不可显示」结论 | 基于 MenuItem_stub.tjs 静态分析（add/popup 空函数）；ESC 后实际画面未截图验证 |
| U8 | 手柄长按是否产生 repeat | SDL_CONTROLLERBUTTONDOWN 无 repeat 语义（L2743-2760），KAG3 早送り依赖键盘 repeat → 手柄长按 A 是否走 skipToStop2 未验证 |
| U9 | `freeSaveDataMode` 默认值 | 未查 Config.tjs；影响 S/L 快捷键是否生效 |
| U10 | [select]/[endselect] 标签路径 | 本 DEMO 未使用；KAG3 其他脚本可能使用，未取证 |
| U11 | 右键/ESC 后消息层隐藏的恢复条件 | **部分实测**：ESC 隐藏后按 A 可恢复（diff 0.556076，见 8.2 用例 5）；onPrimaryClick 内部 messageLayerHiding→showMessageLayerByUser 分支未逐步断点验证 |
| U12 | PAD3（X 键）历史层实测 | **实测无可见变化**（diff 0.000000/0.0002，2026-10-30）：可能因 DEMO 无 [history] 标签/历史层未启用；真机行为未验证 |
| U13 | 手柄长按/早送り（skipToStop2）在真机上的行为 | 未验证：SDL_CONTROLLERBUTTONDOWN 无 repeat，KAG3 早送り依赖 shift&ssRepeat；Citron 键盘 repeat 未映射为手柄 repeat |

---

## 7. 实测计划（已于 2026-10-30 执行，结果见第 8 节）

1. **前置**：task-16（audit-web）交付 `--input-keys`（SendInput）后，claim task-18 并复跑。
2. **用例 B（confirm_choice/选项，必须先做）**：启动 M1-c NRO（krkrsdl2 + KAG3 DEMO）→ 等待标题画面（first.ks L62-99 的链接菜单，末尾 `@s` 停止）→ 注入 ↓（=D-pad↓=VK_DOWN，聚焦首个链接）+ C（=A=VK_RETURN，确认）→ 截图；判据：进入 first.ks L109 `*about_kirikiri` 分支，背景换为 `_24_4` 且出现日文正文（L111-114），即链接菜单选择生效。
3. **用例 A（advance_text）**：在用例 B 进入的正文页继续注入 C 键 2-3 次，每次间隔 800 ms → 截图；判据：正文按 `[l]` 行等待逐行推进、到 `[p]` 后进入下一页 `*about_kirikiri2`（L115-120，`@cm` 后新文本）。**注意：标题 `@s` 页的 C 键无效（见 §0 第 9 条），所以 advance 用例必须在选择之后做。**
4. **用例 C（菜单/stub 验证）**：注入 X（=B=ESC）→ 截图；判据：消息层隐藏（验证 U7），并确认无可见系统菜单。
5. **证据**：PNG + JSON（时间戳/按键序列/窗口标题/日志 tail）+ 日志，存 `docs/milestones/evidence/M2c-*`；临时脚本放 `E:/galnx-build/`（不污染仓库）。
6. **失败处理**：若 Citron 键盘映射不生效（窗口未聚焦/`keyboard_enabled=false` 的 Profile 语义），改用鼠标左键注入（mouse 路径：onPrimaryClick）作为 advance 的兜底证据，并在文档更新 U2。

> **执行结果（2026-10-30 02:19–02:22）**：用例 A/B/C 全部执行，鼠标与键盘两条通道均可用；结果与证据见第 8 节，U2 已关闭。另外发现键盘 fallback 不必启用：PostMessage 通道在 Citron 内有效。

---

## 8. Citron 实测结果（2026-10-30，E2 级：模拟器实测）

> 本节把第 7 节的「待实测」计划执行完毕。所有数字均为 Citron（main-0237a9b88）内运行 build5/krkrsdl2.nro 的 window.png 像素 diff 实测；diff_ratio 定义见 8.1。证据目录 docs/milestones/evidence/M2c-*（清单见 8.5）。

### 8.1 实测方法与环境

| 项 | 值 |
| --- | --- |
| NRO | E:/galnx-build/m1-krkrsdl2/build5/krkrsdl2.nro（17,907,245 B，sha256 e324c2d08b0a2d46…，内嵌 data-withfont.xp3 6,628,897 B） |
| 模拟器 | Citron Nightly main-0237a9b88（E:/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/web-02/citron/citron.exe） |
| 窗口 | 1728×1016（150% DPI），游戏区 y=70..950；diff 采样 380,160 点，ΔRGB 绝对值 >30 记差异，diff_ratio=差异/采样 |
| 输入通道 A（鼠标） | SendInput mouse_event + SetCursorPos（Citron mousePressEvent -> SDL 触摸 -> KAG3 OnClick）；click 坐标 = window.png 物理像素坐标 |
| 输入通道 B（键盘） | PostMessage WM_KEYDOWN/WM_KEYUP 到 Citron 主窗口（SendInput 键盘实测无效，diff≈0.0003） |
| 键位换算 | Citron 键盘 -> 手柄：C(67)=A、X(88)=B、V(86)=X、Z(90)=Y、方向键 40/38=十字上下；krkrsdl2 再把 PAD1..PAD4 映射成 VK_RETURN / VK_ESCAPE / showHistoryByKey / 无 |
| 前置 | 首帧门控：--input-delay 需 ≥2500ms（Citron keyPressEvent 在首帧前丢弃输入）；启动后先 --input-settle 3200ms 再注入 |
| 驱动方式 | ① scripts/citron_run.sh 一次注入一个通道并出 result.json；② --keep 启动后用 run 目录内 citron_win.ps1 -Mode input/capture/diff 分步驱动（本报告多数步骤用它，避免多进程争用） |

### 8.2 实测用例与结果

| # | 用例 | 注入 | 结果（diff_ratio） | 判定 | 证据目录 |
| --- | --- | --- | --- | --- | --- |
| 1 | 标题页 -> 分支（confirm_choice / [link] 点击） | mouse click 860,375（「吉里吉里とは」链接行） | **0.494465**（nonblack 0.7159→0.7193），after = *about_kirikiri 日文正文 + ▼ | **通过** | M2c-click-link-20261030-021105 |
| 2 | 标题页链接焦点导航 + 确认 | DOWN(40) / DOWN(40) / A(67) | **0.007397** / **0.016511**（焦点高亮移动）/ **0.554372**（进入正文页） | **通过** | M2c-title-focus-confirm-20261030-021602 |
| 3 | 正文推进（advance_text） | A(67) | **0.556076**（nonblack 0.7186→0.7211），翻页且 ▼ 出现 | **通过** | M2c-body-semantics-20261030-021958 |
| 4 | ESC -> 隐藏消息层（B 键语义） | B(88) | **0.556076**（nonblack 0.7211→0.7186），消息层消失、背景全显 | **通过** | M2c-body-semantics-20261030-021958 |
| 5 | 再按 A 恢复消息层 | A(67) | **0.556076**（nonblack 回到 0.7211），与步骤 3 同值 | **通过（可往返）** | M2c-body-semantics-20261030-021958 |
| 6 | X -> 历史记录（PAD3 -> showHistoryByKey） | X(86) ×2 | **0.000000** / **0.0002**（无可见变化） | **未生效（负面发现）** | M2c-body-semantics-20261030-021958、M2c-x-history-20261030-022129 |
| 7 | 正文推进（鼠标通道） | mouse click 860,780（画面中央） | **0.556042**（与键盘通道同量级；p4≈p1 说明两页循环） | **通过** | workspaces/citron-harness/runs/20261030-021427-krkrsdl2 |
| 8 | 键盘通道稳定性 | C(67) 按住 350ms、间隔 700ms、连按 3 次 | **0.556042**，p2 与 p3 字节完全相同 | **通过** | 同上 |

数值复现性：步骤 3/4/5 的 A→B→A 往返三次均精确回到 0.556076 同一数值（像素级复位），说明 diff 指标稳定、无闪烁噪声干扰。

### 8.3 实测结论（与第 3 节源码链路交叉验证）

**已被实测确认的语义**（E1 源码 + E2 模拟器实测双证）：

- **advance_text**：等待点（showLineBreak / showPageBreak 注册 conductor.wait(%[click: …]) 并返回 -2）收到 onPrimaryClick -> conductor.trigger('click') -> run() 继续标签循环；实测按键 A（PAD1 -> VK_RETURN，经 checkProceedingKey -> onPrimaryClickByKey）与鼠标点击两条通道都能推进，diff 0.556076 / 0.556042。
- **confirm_choice / [link]**：鼠标命中链接 -> MessageLayer.processLink(n) -> window.process(storage,target) -> conductor.goToLabel；键盘路径 = 方向键移动 keyLink 焦点（实测 0.0074 / 0.0165）+ A 确认（0.554372）。标题菜单由 6 个 [link] 构成、无 [select] 标签，与源码一致。
- **B 键（PAD2 -> VK_ESCAPE）**：调用 rightClickMenuItem.click() -> onPrimaryRightClick() -> 默认隐藏消息层（不是打开菜单）；实测按 B 后消息层消失（0.556076），再按 A 恢复——同一物理键在可见/隐藏两态下语义不同，与源码一致。

**负面 / 边界发现**：

- **X（PAD3 -> showHistoryByKey）实测无可见变化**（0.000000 / 0.0002）：源码路径存在（MainWindow.tjs L3977-4003），但本次 DEMO 场景无 [history] 标签、历史层可能未启用或未写入，故不能据此否定真机行为；记为 U12。
- **KAG3 键盘快捷键不可达（引擎适配关键结论）**：F / A / B / R / S / L（快进 / 自动 / 回退 / 历史 / 存档 / 读档）只存在于 processKeys 的键盘分支；Citron 与真机的输入只以手柄按钮形式到达（VK_PAD* 合成的键盘键仅 RETURN / ESC / 方向 / 历史函数），因此 **Switch 上无法触达 KAG3 的存档 / 读档 / 自动 / 回退快捷键**；配合 MenuItem stub（popup 为空），**UI 入口也不存在**。krkr-ns 自建启动器 / 游戏内菜单正是补这个缺口。
- 历史功能只能靠 PAD3（X 键），但本次 demo 未生效；MVP 不应把历史当必需功能。

### 8.4 实验规程与失败模式（可复用）

1. **启动前必须确认 0 实例**：tasklist /FI "IMAGENAME eq citron.exe" 必须为 0；citron_run.sh 的 pre-flight 会拒绝在已有实例上启动，但脚本退出不等于没有实例——不要在返回非 0 后继续沿用旧 list 输出。
2. **启动后三重校验**：result.json 的 status==loaded、window_title 含 Kirikiri SDL2、helper -Mode list 的 W 行 PID 必须等于本次 result.json 的 pid；任一不满足则退出，不注入、不 kill。
3. **只 kill 自己的 PID**；不要用 -Mode list 的第一行（可能是别人的窗口）。
4. **事故记录（2026-10-30 02:16:50）**：我的第二次 keep-run 被 pre-flight 拒绝（existing pid 26100），但脚本仍把已存在的 m0-hello 窗口当作自己的实例注入并 kill（该实例属于 audit-web 的 M0 运行）。教训：pre-flight 失败必须直接退出，不能 fallback 到旧 list 输出。该检查已加入本轮脚本。
5. **MSYS bash 路径陷阱**：Windows 路径含空格时 powershell -File "$(cygpath -w …)" 会因命令替换 / 分词断开导致 PowerShell 只收到半截路径；kill 走 taskkill //PID 更稳。
6. **JSON 解析陷阱**：window_title 本身含竖线分隔符，用 cut -d'|' 解析会截断标题；应用 node 输出 TAB 分隔字段。
7. **一次注入一通道**：同一次 run 里先 click 再 keys 时键盘注入实测未推进（run 20261030-021200）；分步用 --keep 驱动可靠。
8. **首帧门控**：--input-delay < 2500ms 时按键被 Citron 丢弃（keyPressEvent 首帧前 ignore）。
9. **FPS 限制**：Citron 渲染约 19 FPS，注入间隔用 700ms 以上、每步后 sleep 2s 再截图，避免取到中间帧。

### 8.5 证据清单（docs/milestones/evidence/M2c-*）

| 证据目录 | run id | 关键文件（window-after-input.png 或等价物） |
| --- | --- | --- |
| M2c-click-link-20261030-021105 | 20261030-021105-krkrsdl2 | 1364390 B / sha256 61d60a6de38bc8ab… |
| M2c-title-focus-confirm-20261030-021602 | 20261030-021602-krkrsdl2 | 1002571 B / sha256 a748b8ee38ba5d48… |
| M2c-body-semantics-20261030-021958 | 20261030-021958-krkrsdl2 | 1381441 B / sha256 372944437cbf379f… |
| M2c-x-history-20261030-022129 | 20261030-022129-krkrsdl2 | 1381383 B / sha256 de1960129998329e… |

仓库内每个目录保留 result.json（一次注入的机读结果）、run.log、citron_log_slice.txt 与一张关键截图；完整文件集（window.png、window-before-input.png、全部分步 step*.png）在本机 workspaces/citron-harness/runs/<run id>/（gitignore，不入库）。

### 8.6 本次实测未覆盖（并入第 6 节 U 清单）

- 真机 Atmosphère 行为（全部为 Citron 模拟器）；触摸 / 摇杆轴；ZL/ZR/PLUS/MINUS 真机索引；历史层为何未生效；NRO 单游戏内嵌数据下的多游戏切换。

## 9. 来源清单（绝对路径 + 行号）

### 9.1 KAG3 运行时（E:/galnx-build/m1-content/demo/external/kag3/data/，commit b21b16ea）

- E:/galnx-build/m1-content/demo/external/kag3/data/system/MainWindow.tjs：L147-149、L192-197、L214、**L5116-5131（`s` handler = `@s` 実行停止，return -1）**、L663-697、L699-713、L717-739、L764-767、L933-966、L1245-1250、L1374-1379、L2412-2441、L2763-2771、L2833-2855、L3482-3518、L3579-3615、L3617-3642、L3747-3778、L3783-3827、L3829-3835、L3837-3845、L3856-3917、L3919-3927、L3929-3961、L3963-3975、L3977-4003、L4005-4010、L4012-4035、L4037-4060、L4112-4163、L4165-4201、L4203-4265、L4733-5896（handler 表：l L4977、p L4983、link L4888、endlink L4896、save L5320、load L5310、store L5303、goback L5347、gotostart L5337）
- E:/galnx-build/m1-content/demo/external/kag3/data/system/MessageLayer.tjs：L118-127、L180-189、L423-438、L1677-1698、L1991-2014、L2016-2020、L2131-2161、L2311-2378、L2400-2401
- E:/galnx-build/m1-content/demo/external/kag3/data/system/Conductor.tjs：L13、L28-37、L55-189、L204-244、L331-469
- E:/galnx-build/m1-content/demo/external/kag3/data/system/Menus.tjs：L4-145、L149-213
- E:/galnx-build/m1-content/demo/external/kag3/data/system/Config.tjs：L155-173、L359-439
- E:/galnx-build/m1-content/demo/external/kag3/data/system/Initialize.tjs：L188-204、L232
- E:/galnx-build/m1-content/demo/external/kag3/data/system_polyfill/KAGParser.tjs：L211、L2070-2085、L1170-1801、L1989-1997、L2176-2184、L275/L429/L639/L702/L746/L799/L943/L1146/L1151
- E:/galnx-build/m1-content/demo/external/kag3/data/system_polyfill/MenuItem_stub.tjs：L3-29
- E:/galnx-build/m1-content/demo/data-demo/scenario/first.ks：L74-86、L111-114、L286-292、L304-310、L330-333、L545-552、L624
- E:/galnx-build/m1-content/demo/data-demo/scenario/snow.ks：全文（6 个 [i] 插件演示）

### 9.2 krkrsdl2 上游（E:/galnx-build/m1-krkrsdl2，HEAD 124bdf841f09e7ce02aa99b7b55791a0f7a900ff）

- E:/galnx-build/m1-krkrsdl2/src/core/sdl2/SDLApplication.cpp：L134-147、L156-169、L189-320、L322-450、L2644-2798、L3108
- E:/galnx-build/m1-krkrsdl2/CMakeLists.txt：L132-140、L538-544、L725-748（Switch 目标/NRO 打包）

### 9.3 模拟器配置

- C:/Users/<user>/AppData/Roaming/citron/config/qt-config.ini：L66-69、L279-330（player_0 键位）

---

## 10. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-30 | 初版：M2-c 源码取证（source-inspected）；Citron 注入实测待 task-16 |
| 2026-10-30 | 补 `@s` 実行停止语义（MainWindow.tjs L5116-5131，return -1）并修正实测顺序：选择用例先行、推进用例随后 |
| 2026-10-30 | **新增第 8 节 Citron 实测结果**：advance/ESC/焦点/确认 实测数值、X 历史负面发现、实验规程与失败模式、M2c-* 证据清单；更新 §0（第 10-12 条）、U2/U11 关闭、新增 U12/U13、§2.1 X 行注记、§7 执行结果注记 |
