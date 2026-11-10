# 007 — ONScripter-NX（clamintus/onscripter-nx）Switch 构建记录

| 项目 | 值 |
| --- | --- |
| 编号 | 007 |
| 对象 | clamintus/onscripter-nx（ONScripter 的 Nintendo Switch 移植，GPL-2.0-or-later） |
| 锁定版本 | HEAD `a8439a86393f74c503d28df176f010ca544af56f`（2026-01-14T18:46:39Z，subject `Don't write logs on the SD card`） |
| 关联任务 | task-24（M4-c：ONScripter-NX 构建可行性评估，第三引擎候选） |
| 执行 | audit-engines（Team Lead: lead） |
| 执行时间 | 2026-10-30 02:39–02:52（构建）、02:58–03:04（Citron 运行验证，见 §10.3） |
| 构建根目录 | `E:/galnx-build/m4-ons`（无空格） |
| 结果 | **构建成功**（源码零修改、含合法自建内容包）；**Citron 运行验证通过**（启动/推进/两分支选择，菜单未测）→ 结论「正式适配候选（P2）」 |

## 1. 目标

回答 M4 里程碑的问题：**ONScripter-NX 能否作为 GalNX 的第三引擎候选（原生 NScripter 路线）？** 本轮只做：

1. 按上游 commit 克隆并构建出 `.nro`，记录命令/耗时/退出码/产物哈希；
2. 自建一份**合法（自有版权、无第三方素材）最小 NScript 内容包**并内嵌进 RomFS，用于运行验证；
3. 在 Citron（Switch 模拟器）上做标题→正文推进、选择分支的运行验证（窗口由 Lead 协调，实测结果见 §10）；
4. 给出结论：正式适配 / 继续研究 / 搁置。

约束：不接触 prod.keys、不修改用户 Citron 配置、不 git add/commit；临时文件全部在 `E:/galnx-build/m4-ons/`。

## 2. 结论摘要

1. **可构建**：devkitPro MSYS2 + 纯 Makefile，全量 clean build `make -j16` 成功，`ELAPSED_S=20`、`MAKE_EXIT=0`，源码**零修改**。
2. **产物**：含自建内容 NRO `m4-ons-with-content.nro` = **10,449,140 B**，SHA-256 `d8f9bb116e11c25b0850890202e4c4e7de0e21f830c212f40ce6d54c527f828d`；纯引擎对照 NRO 10,437,716 B，SHA-256 `d84e9f4a2842ce47a370b47a890c85d7dcb755228dbb576c521f15c1e9467a1d`。
3. **缺 2 个 devkitPro 包**，已按任务授权安装并记录：`switch-smpeg2 2.0.0-1`、`switch-libvorbis 1.3.7-1`（首轮构建失败根因即缺 `vorbis/vorbisfile.h`）。
4. **合法内容包可行**：1-byte（insani）模式用全 ASCII 的 `0.txt` 即可驱动「标题 → 正文 → `click` 推进 → `select` 两分支」；`bg.png` 由本机 node 程序化生成（无第三方素材）；**必须**在 RomFS 放一个 `arc.nsa`/`arc.sar`（0 字节占位）以通过 `switch_check_files()` 门禁。
5. **静态结构已校验**（nstool）：NRO 头/入口点/ModuleId/段表/NACP 全部正常，NACP 标题 `ONScripter-NX`、作者 `clamintus`；RomFS 资产段 23,276 B 内确认含 `0.txt` 等自建文件。
6. **许可证**：GitHub 检测为 GPL-2.0，但 24/25 个源文件头写明 `either version 2 of the License, or (at your option) any later version` → 精确 SPDX 应记 **GPL-2.0-or-later**（`COPYING` 是 GPLv2 全文）。分发修改版 `.nro` 需按 GPL 提供对应源码。
7. **运行验证（Citron，02:58–03:04）**：R1–R5 全部通过——启动即显示自建内容、`C`（手柄 A→RETURN）推进翻页、`select` 选项显示、方向键移动光标后 `C` 确认分别进入 Branch A/B；**负结果**：只按 `C` 不按方向键时 RETURN 不确认选项（光标未定位，见 §10.3 R4a）。
8. **结论：正式适配候选（P2）**。构建+运行链路已实测闭环；剩余前置条件不在引擎本身：①GalNX 需提供启动器/多游戏管理与菜单·存档 UI（上游 Switch 分支没这些入口）；②GPL-2.0-or-later 传染性需法务确认；③真机未验证（§14）。

## 3. 环境

| 项目 | 值 |
| --- | --- |
| 宿主 | Windows 10.0.26100 x64，16 核 |
| devkitPro | `D:/devkitPro`（MSYS2 在 `D:/devkitPro/msys2`） |
| 调用姿势 | `env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/<script>.sh'` |
| devkitA64 | `r30-1`，`aarch64-none-elf-gcc 16.1.0` |
| libnx | `4.12.0-1` |
| switch-tools | `1.13.1-1`（elf2nro/nacptool） |
| SDL2 栈 | `switch-sdl2 2.28.5-4`、`switch-sdl2_image 2.0.4-1`、`switch-sdl2_mixer 2.0.4-2`、`switch-sdl2_ttf 2.22.0-2` |
| 媒体/字体 | `switch-smpeg2 2.0.0-1`（本轮新装）、`switch-libvorbis 1.3.7-1`（本轮新装）、`switch-libvorbisidec 1.2.1-2`、`switch-freetype 2.13.3-1`、`switch-harfbuzz 10.0.1-1` |
| 其他 | `switch-libjpeg-turbo 2.1.2-2`、`switch-libpng 1.6.48-1`、`switch-libwebp 1.0.2-2`、`switch-libmodplug 0.8.9.0-2`、`switch-mpg123 1.31.3-3`、`switch-opusfile 0.10-3`、`switch-libopus 1.3-2`、`switch-libogg 1.3.4-2`、`switch-bzip2 1.0.8-1`、`switch-zlib 1.3.1-1`、`switch-pkg-config 0.28-4`、`zlib 1.3.1-1` |
| MSYS2 工具 | `cmake 4.0.2`（本工程未用）、GNU make 4.4.1、ninja 1.13.2（未用） |

完整 `pacman -Q` 记录见 `docs/milestones/evidence/M4c-build-20261030/environment-versions.txt`。

## 4. 上游事实（只读取证）

### 4.1 仓库 / 许可证

- URL：https://github.com/clamintus/onscripter-nx（仓库名在 GraphQL 中为 `clamintus/ONScripter-NX`，`nameWithOwner` 大小写不影响 clone）
- 默认分支：`main`；HEAD：`a8439a86393f74c503d28df176f010ca544af56f` @ 2026-01-14T18:46:39Z；created 2022-01-21；stars 37、forks 3；release 4 个（最新 v0.3.1 2026-01-15）；非 archived、非 fork；仓库约 3.5 MB、无 submodule。
- 许可证：`COPYING`（18,332 B，GNU GPL v2 全文）；GitHub `/license` 检测为 `GPL-2.0`；但 `source/` 下 25 个源码文件中 24 个文件头写明「either version 2 of the License, or (at your option) any later version」→ **SPDX: GPL-2.0-or-later**（`ONScommand.cpp` 系列沿用 Ogapee/insani 原头；Switch 新增的 `switch_mitm.cpp`、`switch_nofile_splash.cpp` 同）。
- 再分发义务（对 GalNX 的含义）：分发 `.nro` 二进制时必须随附**完整对应源码**（含我们自己的修改，如有），保留版权声明与 GPL 声明，允许接收者再分发；GPL 的传染性只作用于该可执行程序本身，**不自动波及 GalNX 框架其余部分**，但如果把 GPL 代码静态链进同一程序，则整个程序按 GPL 分发。
- 注意：上游 release v0.3.1 的资产里含 `tsukihime*.zip`、`kagetsu_tohya*.zip`（**商业游戏数据**）——本任务不下载、不使用、不再分发；本记录只使用自建内容包。

### 4.2 构建系统（纯 devkitPro Makefile，无 CMake）

- 入口：仓库根 `Makefile`（9,150 B），`include $(DEVKITPRO)/libnx/switch_rules`；`TARGET := $(notdir $(CURDIR))` → **产物名默认取克隆目录名**（本机目录 `m4-ons`，故产物为 `m4-ons.nro/.elf/.nacp`）。
- 关键变量：`APP_TITLE = ONScripter-NX`（`ENABLE_HD` 时带 `(HD)`）、`APP_AUTHOR = clamintus`、`APP_VERSION = 0.3.1`；`ARCH = -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE`。
- 编译宏（决定性）：`-D__SWITCH__`、`-DUSE_OGG_VORBIS -DENABLE_1BYTE_CHAR -DFORCE_1BYTE_CHAR -DINSANI -DSDL2`；CXX 另加 `-fno-rtti -fno-exceptions`。
- 链接库：`sdl2-config --libs`、`smpeg2-config --libs`、`-lSDL2_ttf -lnx -lSDL2_image -lz -lm -ljpeg -lwebp -lfreetype -lharfbuzz -lbz2 -lpng16 -lSDL2_mixer -lSDL2 -lEGL -lglapi -ldrm_nouveau -lnx -lpthread -lvorbisidec -logg -lmodplug -lstdc++ -lmpg123 -lopusfile -logg -lopus`。
- 产物规则由 libnx `switch_rules` 提供：`NROFLAGS = --icon=icon.jpg --nacp=$(TARGET).nacp --romfsdir=romfs`；`make ENABLE_HD=1` 出 HD 版本。
- 可选 `Makefile.extlibs`：仅当 devkitPro 的 `switch-sdl2_ttf` 文字渲染 bug 出现时用 `make -f Makefile.extlibs` 重编（`extlibs/SDL2_ttf/bug1433.patch`）；本机 `switch-sdl2_ttf 2.22.0-2` **未触发**该 bug，未使用该路径。
- 版本字符串（`include/version.h`）：`ONS_VERSION "20060724-insani"`、`PORT_CREDIT "SDL2 port by clamintus"`、`NSC_VERSION 255`、`NX_VERSION 31`（→ 显示 3.1，与 Makefile 的 0.3.1 对应）。

### 4.3 README 声称（原文要点，**README 声称≠已验证**）

- 「A port of onscripter-20060724-insani-sdl2 to the Switch. I specifically made this to support running older NScripter-based games that would break on newer versions of ONScripter or ONScripter-EN.」
- Features：4:3 aspect ratio simulation、Touchscreen support、RomFS integration、Optimized flush implementation。
- Tested games：**Tsukihime、Kagetsu Tohya**；「Any game that uses legacy ONScripter should run just fine though. If not, please open an issue!」
- 构建依赖原文：`switch-dev`、`switch-sdl2 switch-sdl2_image switch-sdl2_mixer switch-sdl2_ttf`、`switch-smpeg2`、`switch-libvorbis`；并提示 `switch-sdl2_ttf` 当时 broken 需 `make -f Makefile.extlibs`。
- HD 说明（v0.3 起）：引擎可高清渲染文字/内部图形，但**游戏素材只会被缩放**、偶发小 glitch、CPU 负担增加导致输入略延迟、跳过文字时更明显；release 同时提供 HD/非 HD。
- 控制：A=Enter/推进、B=返回或推进、X=右键菜单、Y=整页绘制、D-Pad Up 或 L / Down 或 R=历史、左摇杆=文字速度、按住 ZL/ZR=跳过、Plus=退出。

## 5. 检出（clone）

```bash
git -c http.proxy=http://127.0.0.1:7897 clone --depth 1 \
  https://github.com/clamintus/onscripter-nx /e/galnx-build/m4-ons
cd /e/galnx-build/m4-ons && git log -1 --format='%H %cI %s'
# a8439a86393f74c503d28df176f010ca544af56f 2026-01-14T19:46:39+01:00 Don't write logs on the SD card
```

仓库无 submodule；`romfs/` 初始只有 `default.ttf`（11,248 B）。

## 6. 依赖安装记录（任务授权范围内的 pacman）

首轮构建失败：`include/ONScripterLabel.h:53` → `fatal error: vorbis/vorbisfile.h: No such file or directory`。根因：本机缺 `switch-libvorbis`（`switch-libvorbisidec` 不含该头）。

```bash
# 在 devkitPro MSYS2 中执行（脚本 E:/galnx-build/m4-ons-install-smpeg.sh 与 m4-ons-install-vorbis.sh）
pacman -S --needed --noconfirm switch-smpeg2 switch-libvorbis
# -> switch-smpeg2 2.0.0-1, switch-libvorbis 1.3.7-1
```

安装后同一构建脚本成功（增量 18 s）。两个包均来自 devkitPro 官方源，未引入第三方二进制。

## 7. 构建步骤与日志

```bash
#!/usr/bin/env bash   # E:/galnx-build/m4-ons-build3.sh
export DEVKITPRO=/opt/devkitpro
export DEVKITA64=/opt/devkitpro/devkitA64
export PATH=/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin:/opt/devkitpro/portlibs/switch/bin:$PATH
cd /e/galnx-build/m4-ons
make clean
T0=$(date +%s); make -j16; RC=$?; T1=$(date +%s)
echo "MAKE_EXIT=$RC"; echo "ELAPSED_S=$((T1-T0))"
sha256sum m4-ons.nro m4-ons.elf m4-ons.nacp
```

调用：`env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m4-ons-build3.sh'`。

结果：`MAKE_EXIT=0`、`ELAPSED_S=20`；日志尾部 `linking m4-ons.elf` → `Writing E:/galnx-build/m4-ons/romfs/0.txt to RomFS image...` → `built ... m4-ons.nro`；仅有 `-Wparentheses/-Wformat-truncation/-Wdangling-else/-Wunused-variable` 等警告，无 error。

完整日志：`docs/milestones/evidence/M4c-build-20261030/build-full-clean.log`（53,120 B）；增量成功日志 `build-incremental.log`；脚本 `build-full-clean.sh` / `build-incremental.sh`。

## 8. 产物

| 产物 | 字节 | SHA-256 |
| --- | --- | --- |
| `m4-ons-with-content.nro`（含自建内容 RomFS，交付物） | 10,449,140 | `d8f9bb116e11c25b0850890202e4c4e7de0e21f830c212f40ce6d54c527f828d` |
| `m4-ons-engine-only.nro`（纯引擎对照，romfs 仅 default.ttf） | 10,437,716 | `d84e9f4a2842ce47a370b47a890c85d7dcb755228dbb576c521f15c1e9467a1d` |
| `m4-ons.elf`（两次构建哈希一致 → 可复现） | 23,565,056 | `888f32c7f06513ca9c55996033cc71e13691c8246370c23df98c7a4594eca4cd` |
| `m4-ons.nacp` | 16,384 | `3cd7982c424b7048a86c08522b6c2a77914241756bb139ad4fd2881c4b035b7f` |

产物位置：`E:/galnx-build/m4-ons/out/`（NRO 副本）与构建目录（ELF/NACP）；哈希文件 `hashes-with-content.json` / `hashes-engine-only.json`。

### 8.1 NRO 静态结构校验（nstool v1.9.2）

- `[NRO Header]`：EntryPoint `0x14000020`、ModOffset `0xf0`、ModuleId `730a7293c055b5b3e55643fa9b7bab32ebe9f2b4000000000000000000000000`；段表 `.text 0x75d000`、`.ro 0x223000`、`.data 0x63000`、`.bss 0x105000`；`NroSize = 0x9e3000`（10,366,976 B）。
- `[ApplicationControlProperty]`：Title `ONScripter-NX`、Publisher `clamintus`（各语言一致）、StartupUserAccount Required。
- `ASET` 资产段（偏移 0x9e3000，共 82,164 B）：icon 42,448 B（JPEG `ffd8ffe0`…）、NACP 16,384 B、**RomFS 23,276 B**；RomFS 内确认含 `*define`、`GALNX M4-c minimal test`、`Page 2: advance works`、`Branch A` 等自建字符串。
- 结论：NRO/NACP/RomFS 结构完整，elf2nro 打包链路正确；模拟器外的静态校验全部通过。
## 9. 自建合法最小内容包（自有版权，无第三方素材）

### 9.1 动机与合规

ONScripter-NX 本身只是引擎，**不带任何游戏内容**；上游 release 里随附的 `tsukihime*.zip`、`kagetsu_tohya*.zip` 是商业游戏数据，本轮**不下载、不使用、不再分发**。为验证「引擎能启动、能读脚本、能推进、能分支」，本任务自建一份最小 NScript 内容包：

- 文本与脚本：本轮作者原创（CC0-1.0 意图声明，见 §9.4）；
- 背景图：本机 node 脚本程序化生成的 640×480 渐变 PNG（无第三方图像素材）；
- `arc.nsa`：0 字节占位文件，仅用于通过引擎的文件门禁（见 §9.3）；
- 字体：使用仓库自带的 `romfs/default.ttf`（上游随引擎分发，11,248 B）。

### 9.2 文件清单与哈希

| 文件 | 字节 | SHA-256 | 说明 |
| --- | --- | --- | --- |
| `0.txt` | 418 | `c0a9efacc1b06bd0a0efd3763bfbe10f50534669c11f91c124dae435f590a555` | NScript 主脚本（ASCII/CRLF，insani 1-byte 模式） |
| `bg.png` | 10,854 | `17e0cd7b050cee1daef0064258364e5cbd0aca075d175ff87eb74860a51c3b08` | 程序化生成的 640×480 RGB 渐变背景 |
| `arc.nsa` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 空归档，仅过 `switch_check_files()` 门禁 |
| `default.ttf` | 11,248 | `9e0c70f71148984389ef6d7ff7ae1ece446259c34ae373f2aba181d8b7ef74ca` | 上游仓库自带字体（不在本轮版权声明范围） |

源文件在 `E:/galnx-build/m4-ons/content/`；构建时被复制进 `E:/galnx-build/m4-ons/romfs/` 并与引擎一起打包进 NRO 的 RomFS 段（证据副本见 `docs/milestones/evidence/M4c-build-20261030/content/`）。清单与脚本全文另存 `content-manifest.json`。

### 9.3 脚本全文与设计要点

```text
*define
game

*start
bg "bg.png",1
`GALNX M4-c minimal test
br
`Self-authored content only.
br
`Press A or click to advance.
click
`Page 2: advance works.
br
`Pick one branch below.
br
select `Branch A`,*ca,`Branch B`,*cb

*ca
`You picked Branch A.
br
`Input mapping works.
click
goto *halt

*cb
`You picked Branch B.
br
`Input mapping works.
click
goto *halt

*halt
click
goto *halt
```

设计要点（均来自源码取证，见 §10.1 的引擎依据）：

1. **`*define` 必须有**：`ONScripterLabel_command.cpp:2530-2539 defineresetCommand()` 会 `setCurrentLabel("define")`，缺该标签启动即失败；`*define` 段内不得出现文本行（`ONScripterLabel.cpp:1089` 会 `errorAndExit("text cannot be displayed in define section.")`）。
2. **`game` 命令结束 define 段并跳 `*start`**：`gameCommand()` 在 `ONScripterLabel_command.cpp:2112-2165` 设置 `current_mode = NORMAL_MODE` 并 `setCurrentLabel("start")`，所以 `*start` 必须存在。
3. **1-byte 文本行必须以反引号开头**：本构建定义 `ENABLE_1BYTE_CHAR + FORCE_1BYTE_CHAR`，`ScriptHandler.cpp:176-259` 把反引号开头的行当文本；反之纯 ASCII 行首字母会被当命令解析。渲染时反引号被剥掉（`ONScripterLabel_text.cpp:224-287`）。
4. **`click` = 等待一次点击/按键**：`clickCommand()`（`ONScripterLabel_command.cpp:2617-2629`）设置 `event_mode = WAIT_INPUT_MODE` 并 `return RET_WAIT|RET_REREAD`。
5. **分支用 `select`（GOTO 模式）**：`selectCommand()`（`ONScripterLabel_command.cpp:657-810`）按 `select "文本",*标签,"文本2",*标签2` 解析，选中后 `setCurrentLabel(label)` 跳转。
6. **标签不是执行边界**（NScripter 语义）：`executeLabel()`（`ONScripterLabel.cpp:992-1057`）线性执行并在行耗尽后 `lookupLabelNext` 继续，因此分支块末尾必须 `goto *halt` 走掉，否则会顺序落入另一分支。
7. **`*halt` 死循环**：脚本执行到末尾会触发 `endCommand()` 退出程序，`*halt` 用 `click` + `goto *halt` 静默保持，便于反复注入输入观察。
8. **必须存在 `arc.nsa`/`arc.sar`**：`switch_check_files()`（`source/switch_nofile_splash.cpp:33-49`）只检查 `romfs:/arc.nsa`、`romfs:/arc.sar`、`arc.nsa`、`arc.sar` 四个路径，全缺则显示「No assets file found.」并 `exit(1)`。0 字节占位符即可，因为脚本读取走 `ScriptHandler`/`DirectReader`，不依赖归档内容。
9. **内容随 RomFS 内嵌**：直接把脚本/图/占位归档放进仓库 `romfs/` 再 `make`，产物 NRO 自带内容，运行时不依赖 SD 卡当前目录。

### 9.4 内容版权声明

本轮生成的 `0.txt` 文本与 `bg.png` 由 audit-engines 脚本原创生成，声明为 **CC0-1.0**（公有领域贡献，便于未来测试复用）；不含任何第三方图像/文本/字体素材。`default.ttf` 与引擎代码的许可证仍按上游（GPL-2.0-or-later，字体另按上游随附条款，本记录不改变其许可）。

## 10. 运行验证（Citron 模拟器）

> 本轮 Citron 由 Lead 协调排期（task-23/M4-b 先用）。本节记录运行计划与 preflight；**实测结果回填于 §10.3**。

### 10.1 运行前提

- 被测 NRO：`E:/galnx-build/m4-ons/out/m4-ons-with-content.nro`（10,449,140 B，sha256 `d8f9bb11…`），内容包已内嵌 RomFS。
- 模拟器：Citron `main-0237a9b88`（`E:/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/web-02/citron/citron.exe`），Vulkan 后端。
- 输入通道（M2-c 已实测于 krkrsdl2）：鼠标 `SendInput mouse_event` 有效；键盘须用 `PostMessage(WM_KEYDOWN/WM_KEYUP)` 注入（普通 SendInput 键盘对 Citron 无效）；Citron 首帧门控要求 `--input-delay >= 2500ms`。
- Citron 键盘→手柄映射（`qt-config.ini` 实测）：C(67)=A、X(88)=B、V(86)=X、Z(90)=Y、Q(81)=L、E(69)=R、R(82)=ZL、T(84)=ZR、M(77)=**Plus（会退出）**、N(78)=Minus、方向键 16777234/35/36/37 = DPAD 左/上/右/下。
- ONScripter-NX 手柄合成（`source/switch_mitm.cpp`）：A→`SDLK_RETURN`；B→文本模式 `SDLK_RETURN`、否则 `SDLK_ESCAPE`；X→`SDLK_ESCAPE`；Y→`'o'`（整页绘制）；DPAD Up 或 L→`SDLK_UP`；DPAD Down 或 R→`SDLK_DOWN`；DPAD Left/Right→`'h'`/`'l'`；StickL→`'0'`（文字速度）；按住 ZL/ZR→持续 `LCTRL`（跳过）；Plus→`SDL_QUIT`。**触屏注入代码在上游被整段注释掉，Switch 上触摸不可用。**

### 10.2 预写命令与 preflight

```bash
# 0) preflight：必须 0 个 citron 实例
tasklist //FI "IMAGENAME eq citron.exe"
# 1) 启动 + 注入 C（手柄 A → RETURN）三次推进到第 2 页与选项
cd "/e/Othergames/Nintendo Switch/Workspace/GalNX"
bash scripts/citron_run.sh \
  --nro "E:/galnx-build/m4-ons/out/m4-ons-with-content.nro" \
  --input-delay 3000 --input-settle 2500 --input-gap 1200 \
  --input-keys C,C,C
# 2) 出现选项后用 D-pad 左/右（LEFT/RIGHT=16777234 / 16777236 或 LEFT/RIGHT 键名）选分支，再 C 确认
bash scripts/citron_run.sh --nro ... --input-delay 3000 \
  --input-keys LEFT,C
# 3) 存档/退出等若要复现：仅 kill 自己的 PID；每次 run 的 result.json / window*.png 归档到 evidence
```

preflight 规则（M2-c 事故后固化）：

1. 启动前 `citron.exe` 实例数必须为 0（脚本已内建 `citron_already_running` 拒绝）；
2. 启动后三重校验：`result.json` 的 `status == loaded`、`window_title` 含 `ONScripter-NX`（本工程 APP_TITLE）、helper `-Mode list` 的 W 行 PID == 本次 PID；
3. 只 kill 本次启动的 PID；不传 `--allow-existing`；批次结束回报 Lead「Citron 释放 HH:MM」。

### 10.3 实测结果

执行时间 2026-10-30 02:58–03:04（Asia/Shanghai），Citron Nightly `0237a9b88`，产物 `m4-ons-with-content.nro`（SHA-256 见 §8），命令见 §10.2。每次 run 前 `citron.exe` 实例数 0；run 结束后 harness 只终止本次启动的 PID，无残留实例（**Citron 释放 03:04**，交由下一占用方）。

| 用例 | 注入 | 期望 | 实测（run / PID / diff） | 结论 |
| --- | --- | --- | --- | --- |
| R1 启动 | 无 | 第 1 页标题/正文可见 | run `20261030-025835`（pid 38860）：`status=loaded`、窗口标题含 `ONScripter-NX`、非黑像素 0.723；画面 = `GALNX M4-c minimal test / Self-authored content only. / Press A or click to advance.` + 自绘渐变背景 + 4:3 左右黑边 | **通过** |
| R2 advance_text | `C,C`（手柄 A → RETURN） | `click` 解除，翻到第 2 页并显示选项 | run `20261030-025913`（pid 30836）：keys_sent=2（postmessage 通道），diff=0.01296；截图 = `Page 2: advance works. / Pick one branch below.` + `Branch A`、`Branch B` 两行 | **通过** |
| R3 confirm_choice（B） | `C,C,LEFT,C` | 方向键移动光标后确认，进入分支文本 | run `20261030-030021`（pid 2464）：keys=67,67,37,67，diff=0.021765；截图 = `You picked Branch B. / Input mapping works.` | **通过** |
| R4a 无方向键确认 | `C,C,C` | 若光标默认在 A，应进入 Branch A | run `20261030-030112`（pid 38264）：diff=0.01296，after 截图与 R2 **逐字节相同**（sha256 `cd87171c719f5ac9091df98abcd020c950f006adac851ab611c21772be1cd092`），仍停在选项页 | **不成立**：无方向键时 RETURN 不确认选项 |
| R4b 反方向 | `C,C,RIGHT,C` | 右移光标后确认 | run `20261030-030210`（pid 15776）：keys=67,67,39,67，diff=0.021765，落 Branch B（与 R3 同值） | 通过（方向语义见 U9） |
| R5 confirm_choice（A） | `C,C,LEFT,LEFT,C` | 两次左移后确认进入 Branch A | run `20261030-030317`（pid 37280）：keys=67,67,37,37,67，diff=0.02167；截图（sha256 `ce48269f1139963d27b79d08e7b73cb53f465e80326109de24593638dce7e351`）= `You picked Branch A. / Input mapping works.` | **通过（两分支均可达）** |
| R6 菜单/退出 | 未注入（X=ESCAPE） | `rmenu` 未定义时期望无可见菜单 | **本轮未执行**：Citron 窗口于 03:04 释放、M4-b 为下一占用方，避免超时占用 | 未验证（U4） |

观察（不改变 R1–R5 结论，均记入 §14）：①选项文字渲染为暗色但可辨（`select` 默认未选中态）；②ASCII 文本按 1-byte 模式渲染，字符间有明显等宽间隙——属 `ENABLE_1BYTE_CHAR`/默认 TTF 度量路径，CJK 混合排版未验证（U6）；③键盘注入始终可用（`key_method=postmessage`，`focus_ok=0` 不影响）。

失败兜底：若键盘 PostMessage 通道对本 NRO 无效，改用鼠标点击画面推进（`--input-click`，ONScripter 的 `mousePressEvent` 与 `fingerPressEvent` 均会 `advancePhase`）。

## 11. 失败点与坑

| # | 现象 | 根因 | 处理 |
| --- | --- | --- | --- |
| 1 | `fatal error: vorbis/vorbisfile.h: No such file or directory`（`include/ONScripterLabel.h:53`） | 本机缺 `switch-libvorbis`（`switch-libvorbisidec` 不含该头） | `pacman -S switch-libvorbis`（已记录） |
| 2 | 多行命令塞进 `bash -lc` 被 Windows 引号/展开破坏 | MSYS2 bash 与 PowerShell 引号层叠 | 一律先写 `.sh` 脚本再 `bash -lc 'bash /e/galnx-build/xxx.sh'` |
| 3 | 产物名不是 `onscripter-nx.nro` 而是 `m4-ons.nro` | `Makefile` 的 `TARGET := $(notdir $(CURDIR))` | 记录命名差异，不视为偏差（可用 `make TARGET=...` 覆盖） |
| 4 | 改了 `romfs/` 后 NRO 未变 | libnx romfs 规则依赖文件列表 | 需 `make clean` 或删除目标后重建（本轮用全量 `make clean`） |
| 5 | 无内容时启动即退出 | `switch_check_files()` 门禁 + 无 `*define`/`*start` 时 `init()` 失败 | 内容包必须含 `*define`、`game`、`*start` 与至少一个 `arc.nsa`/`arc.sar` |
| 6 | `switch-sdl2_ttf` 文字不显示（README 声称的历史 bug） | 上游 `TTF_RenderUTF8_Shaded` 缺陷 | 本机 `switch-sdl2_ttf 2.22.0-2` 未触发；未用 `Makefile.extlibs`；若后续触发按 README 重编 |

## 12. 与上游 release 的偏差

| 项目 | 上游 release v0.3.1 | 本记录 |
| --- | --- | --- |
| 源码 | tag 对应的构建产物 | 从 `main` HEAD `a8439a86` 克隆，**零源码修改** |
| 内容数据 | 附带头文件/月姬等商业数据 zip | **不使用**；改用自建最小内容包（§9） |
| 产物名 | `onscripter-nx.zip`（含 NRO） | `m4-ons.nro`（目录名决定），内容内嵌 RomFS |
| 运行环境 | 真机（Atmosphère，建议 title-takeover） | Citron 模拟器；**真机未验证** |

## 13. 结论

- **构建可行性：是**（可复现、零修改、20 s 全量构建、依赖全在 devkitPro 官方源）。
- **运行可行性（Citron）：是**。R1–R5 通过：启动渲染、`click` 推进、`select` 选项、方向键移动光标 + `C` 确认（A/B 两分支均进入）。**负结果**：无方向键时 RETURN 不确认（§10.3 R4a），即选项必须由方向键定位后才可确认。
- **结论：正式适配候选（P2），有条件**。
  - 支持理由：构建门槛最低一档；GPL-2.0-or-later 明确可分发（需开源修改）；原生 NScripter 老游戏是 KiriKiri/Ren'Py 不覆盖的生态位；4:3 信箱与手柄映射内建且实测可用。
  - 前置条件（阻塞项，按重要性）：①**无启动器/多游戏管理**（单目录 `arc.nsa` 模型），GalNX 需自建前端或改引擎；②**无 KAG 式菜单/存档 UI**——Switch 分支手柄键只合成 Enter/ESC/方向/历史，`rmenu` 未定义时右键=隐藏文字层，存档/读档/自动/回退入口必须由 GalNX 提供；③**GPL-2.0-or-later 传染**：分发内置引擎的 GalNX 修改版需按 GPL 开源相应部分，法务须先确认；④真机未验证，HD 模式有已知 CPU/输入延迟代价。
- **接入定位**：第三引擎（P2），排在 KiriKiri 之后、Ren'Py 之前；适合作为「原生 NScripter 老游戏」兜底，不适合作为默认引擎。

## 14. 未验证 / 限制

| # | 项 | 说明 |
| --- | --- | --- |
| U1 | 真机运行 | 仅在（或即将在）Citron 模拟器验证；Atmosphère/内存/title-takeover 未测 |
| U2 | 触摸输入 | 上游 `switch_mitm.cpp` 的触屏注入被注释，Switch 上触摸不可用；README 的「Touchscreen support」需在真机复核 |
| U3 | 存档/读档 | Switch 分支 `save*.dat` 写 CWD（`ONScripterLabel_file.cpp:127-140`），RomFS 只读场景下 CWD 为 SD 卡根/应用目录，未实测可写性 |
| U4 | 系统菜单/右键菜单 | 依赖游戏脚本 `rmenu`/`menusetwindow` 定义；本内容包未定义 → X 键无可见菜单，未验证菜单渲染 |
| U5 | 音频/视频 | 内容包无声无视频；`smpeg2`/`libvorbis` 链接通过但未播片验证 |
| U6 | 中文字符集 | 本内容包为纯 ASCII；`ENABLE_1BYTE_CHAR + FORCE_1BYTE_CHAR` 下 CJK 渲染路径未验证（引擎另有 `sjis2utf16` 表，需真游戏验证） |
| U7 | HD 模式 | 未构建 `ENABLE_HD=1` 变体；README 声称的缩放/延迟代价未实测 |
| U8 | 商用游戏兼容性 | README 声称「legacy ONScripter 游戏基本都能跑」，本轮**无法也不应**用商业游戏验证 |
| U9 | 选项光标语义 | 实测（§10.3）：LEFT×1→Branch B、LEFT×2→Branch A、RIGHT×1→Branch B。光标从「无选中」态出发，方向/步数与目标按钮的映射未在源码层逐行确认，两项以上菜单未测；GalNX 若自建菜单需重做光标逻辑 |
| U10 | 菜单/存档 UI 入口 | 上游 Switch 分支只把按键合成 Enter/ESC/方向/历史，**无 KAG 式右键菜单与存档/读档入口**（`rmenu` 未定义时 X=隐藏文字层）；本轮未执行 R6，真机存档写盘可行性仍见 U3 |

## 15. 证据清单

| 证据 | 路径 |
| --- | --- |
| 构建日志（全量 clean） | `docs/milestones/evidence/M4c-build-20261030/build-full-clean.log` |
| 构建脚本 | `docs/milestones/evidence/M4c-build-20261030/build-full-clean.sh`、`build-incremental.sh` |
| 依赖安装脚本 | `docs/milestones/evidence/M4c-build-20261030/install-smpeg2.sh`、`install-libvorbis.sh` |
| 产物哈希 | `.../hashes-with-content.json`、`hashes-engine-only.json` |
| NRO 静态结构 | `.../nro-structure.json`（nstool v1.9.2 输出解析） |
| 环境版本 | `.../environment-versions.txt` |
| 自建内容包 | `.../content/0.txt`、`bg.png`、`arc.nsa`；`content-manifest.json` |
| 运行验证 R1 启动 | `docs/milestones/evidence/M4c-run-startup/`（`result.json`、`run.log`、`window.png`） |
| 运行验证 R2 推进 | `docs/milestones/evidence/M4c-run-advance/`（`result.json`、`run.log`、`window-after-input.png`） |
| 运行验证 R3 Branch B | `docs/milestones/evidence/M4c-run-branch-b/`（同上三件） |
| 运行验证 R4b RIGHT | `docs/milestones/evidence/M4c-run-branch-right/`（同上三件） |
| 运行验证 R5 Branch A | `docs/milestones/evidence/M4c-run-branch-a/`（同上三件） |
| 运行验证汇总 | `docs/milestones/evidence/M4c-run-README.md`（5 个 run 的 run id / PID / 注入 / diff / 结论一览） |

## 16. 复现清单

1. 安装 devkitPro（本机 `D:/devkitPro`，devkitA64 r30、libnx 4.12.0），并 `pacman -S switch-smpeg2 switch-libvorbis`（其余 switch-sdl2* 栈需已装）。
2. `git clone --depth 1 https://github.com/clamintus/onscripter-nx /e/galnx-build/m4-ons`，确认 HEAD `a8439a86393f74c503d28df176f010ca544af56f`。
3. 把 §9.2 的四个文件放入 `m4-ons/romfs/`（`0.txt`、`bg.png`、`arc.nsa`、保留自带 `default.ttf`）。
4. `env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m4-ons-build3.sh'`，期望 `MAKE_EXIT=0`、耗时约 20 s、产出 `m4-ons.nro`。
5. 校验产物 SHA-256（§8 表）与 `nstool` 结构（§8.1）；在 Citron 中用 §10.2 的命令注入：`C,C` 推进到选项页，`C,C,LEFT,C` 与 `C,C,LEFT,LEFT,C` 分别进入 Branch B / Branch A（判定见 §10.3）。

## 17. 变更记录

| 时间 | 变更 |
| --- | --- |
| 2026-10-30 02:52 | 初稿：环境/上游事实/构建/产物/NRO 校验/内容包/失败点（§1–§9、§11–§16） |
| 2026-10-30 03:04 | §10.3 回填 Citron 实测 R1–R5（含 R4a 负结果）；§2/§13 结论升级为「正式适配候选（P2）」；§14 补 U9/U10；§15 补 run 证据 |
| 2026-10-30 03:05 | 证据瘦身（每 run 仅 result.json + run.log + 1 张关键截图）；坏目录与仓库根 `%SystemDrive%` 已清理；新增 `M4c-run-README.md` |
