# GalNX 补丁包：Kirikiroid2-NX（K2NX）自包含改造

> 上游：`Erige005/Kirikiroid2-NX`，pin `e96b6034c292c6ccdb099823ab6a0a6b505f77f3`（= tag `v1.0.1`）。
> 许可：仓库 LICENSE 为 KiriKiri 许可（NOASSERTION），**非 OSI**。本补丁包仅作本地构建/验证记录，构建产物（NRO/NSP）不入库、不分发。
> 用途：让 K2NX 在 Switch 上「首启把 romfs 内游戏 payload 解包到 SD + 自动启动 + 插件名别名 + 手柄虚拟光标 + 手柄存档/读档 UI + 干净退出」，构成自包含 NSP 形态。验收见 `docs/pilot/P2-acceptance.md`、`docs/pilot/saveload-acceptance.md`、`docs/builds/011-k2nx-exit-crash-fix.md`。

## 文件

| 文件 | 内容 | 说明 |
| --- | --- | --- |
| `k2nx-patched-vs-v1.0.1.diff` | 最终 9 文件 diff（52,375 B，sha256 `42436d3e…`，840 insertions / 57 deletions） | **权威记录**：A→I 全部补丁后的树 vs v1.0.1 的 9 个在库文件；文件表见下。补丁 G 另改的 `src/vendor/cocos2d-x/current-3.11.1/cocos/base/CCController-switch.cpp` 不在上游 GitHub 树内（vendor 由 pin 的构建环境提供），故只在 `G-controller-input-v2.patch` 中记录；补丁 H 只改 `MainScene.cpp`，已包含在 diff 内 |
| `galnx_autostart.inc` | 补丁 A 的替换代码块（1,899 B） | 由 `apply_k2nx_patches.py` 内联 |
| `galnx_extract.inc` | 补丁 B 的 **v1** 代码块 | 仅作历史/对照；v1 有 EISDIR 致命 bug，勿直接使用 |
| `galnx_extract_v2.inc` | 补丁 B 的 **v2** 代码块（9,705 B） | 由 `apply_extract_v2.py` 替换进 main.cpp |
| `apply_k2nx_patches.py` | 应用 A + B(v1) | 幂等（已打则跳过），路径写死在脚本顶部 |
| `apply_extract_v2.py` | 把 main.cpp 里的 payload 块换成 v2 | 幂等，须在 `apply_k2nx_patches.py` 之后跑 |
| `apply_plugin_alias_patch.py` | 应用补丁 C（CRLF 字节替换） | 幂等检查较宽松；上游文件须保持 CRLF |
| `D-virtual-mouse-dpad.patch` | 补丁 D（增量 diff，相对 C 之后状态） | DPAD 驱动虚拟光标；见 `docs/builds/010-k2nx-controller-saveload.md` |
| `E-controller-ui-saveload.patch` | 补丁 E（增量 diff，相对 D 之后状态，5 文件） | 手柄热键打开原生 SAVE/LOAD UI 与直接存档/读档 |
| `F-close-exit.patch` | 补丁 F（增量 diff，相对 E 之后状态，2 文件 4,592 B sha256 `21af948c…`） | Switch 上确认关闭 = 退出应用（修 `SystemObj` 崩溃）；`Window` 补 `minimized/maximized`；见 `docs/builds/011-k2nx-exit-crash-fix.md` |
| `G-controller-input-v2.patch` | 补丁 G（增量 diff，相对 F 之后状态，2 文件 22,152 B sha256 `7cf01df0…`） | 手柄映射 v2（B=原生 back、X=自动、Y/+ = 读/存档面板、- = 退出确认、ZR/ZL=左右键、右摇杆半速光标、左摇杆滚轮单步）+ 修 `ProgramClosing` 退出链（K2S 抽屉电源键 `SystemObj` 崩溃）；`CCController-switch.cpp` 把 Minus 变成 `BUTTON_SELECT`；见 `docs/builds/013-k2nx-controller-input-v2.md` |
| `H-input-tweaks.patch` | 补丁 H（增量 diff，相对 G 之后状态，1 文件 2,390 B sha256 `b28b77bd…`） | R 肩键 = 按住持续 Ctrl（快进 skip）、左摇杆滚轮方向修正（上推 = backlog/LOG，下拉 = 下一句）；封面图标随 A9 打包；见 `docs/builds/014-k2nx-input-tweaks.md` |
| `I-save-exit-mouse.patch` | 补丁 I（增量 diff，相对 H 之后状态，1 文件 7,372 B sha256 `3cbcad8d…`，+56/−14） | 退出前显式存档（`MainObj.TraceSave()`+`SystemSave()` 后延迟 1 s 再 `TVPExitApplication`）、ZR/ZL 改为按住鼠标左/右键、`onAxisEvent` 的 `PrimaryLayerArea` 早退后移（标题/设置界面也能用摇杆光标与滚轮）、ZR/ZL 重新显示已淡出的虚拟光标；见 `docs/builds/015-k2nx-save-exit-drag.md` |
| `keymap/Kirikiroid2Preference.xml` | 游戏内键位映射 **v1（golden oracle）**（1,293 B，sha256 `aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543`） | pilot payload 内置模板 + `galnx payload plan\|verify` 的 oracle（GOLDEN_KEYMAP_BYTES/SHA256 硬编码此文件）；**框架侧保持 v1 不变** |
| `keymap/Kirikiroid2Preference.patchG.xml` | patch G 键位映射 **v2**（1,600 B，sha256 `bd9cfc34dc4461fb422da565a78098d5f33fd1e429992113442b445e8f3e3893`） | 只留 A→VK_RETURN 与 D-Pad 方向键；B/X/ZL/ZR/PLUS/MINUS 由 patch G 引擎层处理。A8 romfs payload 实际内嵌这份，解包后落 `sdmc:/kirikiri/haruno/` |

## 应用顺序（新克隆）

```bash
SRC=/path/to/Kirikiroid2-NX            # 已 checkout e96b6034
# 1) 改脚本顶部 WS/INC 指向 SRC 与本目录
python3 apply_k2nx_patches.py          # 补丁 A + B(v1) + 头文件/调用点
python3 apply_extract_v2.py            # 补丁 B 升级为 v2
python3 apply_plugin_alias_patch.py    # 补丁 C
cd "$SRC"
git apply -p1 --recount --whitespace=nowarn D-virtual-mouse-dpad.patch        # 补丁 D
git apply -p1 --recount --whitespace=nowarn E-controller-ui-saveload.patch    # 补丁 E（必须在 D 之后）
git apply -p1 --recount --whitespace=nowarn F-close-exit.patch                # 补丁 F（必须在 E 之后）
git apply -p1 --recount --whitespace=nowarn G-controller-input-v2.patch        # 补丁 G（必须在 F 之后；含 vendor CCController-switch.cpp）
git apply -p1 --recount --whitespace=nowarn H-input-tweaks.patch               # 补丁 H（必须在 G 之后；只改 MainScene.cpp）
git apply -p1 --recount --whitespace=nowarn I-save-exit-mouse.patch            # 补丁 I（必须在 H 之后；只改 MainScene.cpp）
```

> D/E/F/G/H 是**增量 diff**（各自相对前一个补丁之后的状态），必须按 C→D→E→F→G→H→I 顺序应用；A→I 后的 9 个在库文件等于 `k2nx-patched-vs-v1.0.1.diff`（验证方法见 `docs/builds/010` §5 与 `docs/builds/011` §4：CRLF 归一后逐字节一致）。

历史脚本中的绝对路径（`E:/galnx-build/pilot-01/...`）是构建机记录，复现时需改成自己的路径。

## 八处补丁的作用（摘要）

| 补丁 | 文件 | 作用 |
| --- | --- | --- |
| A autostart | `src/core/environ/switch/SwitchUtils.cpp` | `TVPCheckStartupArg()` 读 `sdmc:/switch/kirikiroid2/autostart.txt` → `startupFrom(path)`；绕过首次启动遮罩与文件选择器 |
| B 首启解包 v2 | `src/core/environ/switch/main.cpp` | `romfsInit()` 后 `GalNX_MaybeExtractGame()`：读 `romfs:/game_files.txt`，statvfs 预检 + FastLoad + 1 MiB 缓冲拷贝 + 同大小跳过 + marker 校验，写 marker/autostart |
| C 插件别名 | `src/plugins/InternalPlugins.cpp` | `TVPLoadInternalPlugin` 原名失败后 `.tpm`→`.dll` 重试（K2NX 内置模块名全是 `.dll`，游戏插件目录是 `.tpm`） |
| D 虚拟光标 | `src/core/environ/cocos2d/MainScene.cpp` | `_virutalMouseMode` 由 PLUS 开关、DPAD 24 px 步进、A/B 左右键，让纯手柄环境能点原生 UI 与消息窗 |
| E 手柄存档/读档 | `MainScene.cpp`、`src/core/environ/ui/InGameMenuForm.*`、`src/core/environ/ui/PreferenceForm.*`（5 文件） | 热键直接构造/打开游戏原生 `_SAVELOADOBJECT`（L=存 10 号位、R=开 LOAD UI、PLUS=开 SAVE UI、ZR/ZL=直存/直读），不依赖 Windows 鼠标 |
| F 干净退出 | `src/core/visual/WindowIntf.cpp`、`src/core/environ/cocos2d/MainScene.cpp`（2 文件） | ①Switch 上主窗口确认关闭 → `TVPExitApplication(0)`，避开 invalidate 导致 TJS 世界乱序 teardown（`Member "SystemObj" does not exist`）；②`Window` 补 `minimized/maximized` 属性与 `minimize/maximize/restore` 空实现，消除 `MainWindow.tjs` 的 `this.minimized` 异常 |
| G 手柄映射 v2 | `MainScene.cpp` + vendor `CCController-switch.cpp`（2 文件） | B=原生 back（`ActiveObj.RightMouseUpAction`，不能用 ESC）、X=自动、Y/+ = 读/存档（先 pop K2S 表单）、-=退出确认、ZR/ZL=虚拟鼠标左右键、右摇杆半速光标、左摇杆滚轮单步；`OnCloseQuery()` 等游戏确认再放行 + `OnClose()` 主窗口直接退出，堵住 K2S 电源键的 `ProgramClosing` teardown；Minus → `BUTTON_SELECT` |
| H 输入细节 | `src/core/environ/cocos2d/MainScene.cpp`（1 文件） | R 肩键按住即持续 Ctrl（`_scancode[VK_CONTROL]=0x11`，游戏 `SkipCheck()` 轮询 `System.getKeyState` → 快进/跳过）；左摇杆滚轮方向修正（上推 = `wheel 120` = backlog/LOG，下拉 = `wheel -120` = 下一句）；见 `docs/builds/014-k2nx-input-tweaks.md` |

| I 存档/手感 | `src/core/environ/cocos2d/MainScene.cpp`（1 文件） | 退出前显式 `TraceSave()+SystemSave()`（此前只有 `MainWindow.tjs` 的 `finalize()` 会写 `system.bmp`，patch F/G 的直退路径把它跳过了，导致设置/存档信息不落盘、`NEW` 标记卡槽 1）；ZR/ZL = 按住鼠标左/右键（可配合右摇杆拖动）；`onAxisEvent` 的 `PrimaryLayerArea` 早退移到 Switch 分支之后，标题/设置界面也能用摇杆；ZR/ZL 重新显示淡出后的光标；见 `docs/builds/015-k2nx-save-exit-drag.md` |

## 与上游的关系

- 9 个在库文件被修改，均可从 diff 逐行审计；无上游行为的功能删除（840 insertions / 57 deletions，全部是新增分支、属性或热键重排）。
- `[GALNX]` 前缀日志 = 补丁输出的运行时可观测点（首启解包进度、插件别名命中），用于验收取证。
- 补丁不改变渲染路径：A1 插桩版与 clean 版截图逐字节相同（见 `docs/milestones/M1-kirikiri.md` 同类结论）。