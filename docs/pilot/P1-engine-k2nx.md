# P1-b K2NX 引擎审计与自包含 NSP 改造可行性（只读 + 源码级）

- 任务：P1-b（task-33），K2NX（Kirikiroid2-NX）源码机制审计 + 自包含 NSP 改造可行性评估
- 对象：Erige005/Kirikiroid2-NX v1.0.1（预编译 NRO 与源码），以及试点游戏「晴霁之后定是菜花盛开的好天气」（PC KiriKiri2 版）
- 审计员：audit-engines
- 审计日期：2026-10-30
- 证据分级：**E1** 运行日志原文 / **E2** 截图 / **E3** 哈希、大小 / **E4** 源码原文（文件:行号）
- 性质：**只读审计 + 源码取证**。本审计未修改 K2NX 仓库任何文件、未执行 K2NX 构建（本机构建由 Lead 并行执行）、未启动 Citron（本轮 Citron 归 P1-a）
- 结论：**路径 A（重建 K2NX + ROMFS 首启解包 + 自动启动补丁）推荐为主方案**；路径 B（预编译 NRO 转 NSP + 数据外置）仅作快速演示/回退；路径 C（改用 krkrsdl2）只有在 A 被证伪时才考虑

---

## §0 摘要（结论先行）

### 0.1 结论

| 项 | 结论 | 依据 |
| --- | --- | --- |
| A 路径是否可行 | **可行**，改动面小（3 处补丁：A1 自动启动、A2 首启解包、patch C 插件别名，合计约 140 行 C/C++） | §2.2/§2.3/§2.4/§2.11/§5 |
| 是否满足「NSP 自包含 + 直接启动 + 手柄」 | 可满足（数据进 ROMFS，首启解包到 SD，之后自动启动） | §4 |
| 三条「不阻塞」判定 | ROMFS 枚举不阻塞 / 内存不阻塞 / 签名不阻塞 | §0.2 |
| 多 xp3 是否需要改引擎 | **不需要**，由游戏自己的 Init.tjs 用 System.exePath + Storages.addAutoPath 完成 | §2.6（关键新证据） |
| 插件缺失是否致命 | **已定位为确定缺陷**：原始 NRO 因 .tpm/.dll 别名不一致导致内建的 csvParser/extrans/fstat/layerExImage/windowEx 全部未激活，E1 实证崩在 mainwindow.tjs:990 registerExEvent；patch C 修复（§2.11/§2.12） | §2.11/§2.12 |
| 唯一硬前置 | 构建链路（devkitPro switch-portlibs 组 + 7 个自建 portlibs + cocos2d-x 3.11.1 + APK 1.3.9 UI 资源） | §6 |

> **2026-10-30 更新（E1 实证）**：P1-a 的 Citron 运行日志（k2s_log.prev.txt，06:03 那次运行）已证实原始 NRO 在 `mainwindow.tjs(990) SetExEvent` 抛 TJS 异常（registerExEvent 不存在）——插件问题不是「低风险猜测」，而是**已定位的确定阻塞缺陷**；根因与 patch C 复核见 §2.11，8 插件完整映射见 §2.12。引入 patch C 后 A 路径的补丁数由 2 处变为 3 处。

### 0.2 三条「不阻塞」结论（Lead 提出的三个担忧）

1. **ROMFS 目录枚举不阻塞。** libnx 4.12.0 的 romfs devoptab 实现了目录操作：对 libnx.a 的符号表实测存在 romfs_diropen / romfs_dirnext / romfs_dirclose / romfs_dirreset / romfs_stat / romfs_fstat / romfs_chdir / romFS_devoptab，且 romfsInit() 就是 romfsMountSelf("romfs")（libnx/include/switch/runtime/devices/romfs_dev.h:113-121）。因此首启解包可以纯 POSIX（opendir/readdir/stat）递归遍历 romfs:/game/haruno，不需要自建文件索引。
2. **ROMFS 内存不阻塞。** 解包实现为流式拷贝（64KB 缓冲区逐文件读/写），不需要把 3.4GB 读进 RAM；SD 剩余空间检查可用 statvfs("sdmc:/") 或 fsFsGetFreeSpace。
3. **签名不阻塞。** 全仓库 grep 「Trusted / IsTrusted / .sig / CheckSignature / VerifySignature」在 src/core 与 src/plugins 零命中；src/core/environ/switch/Protect.h（373 B）注释说明那是 Android APK 的完整性/Licence 检查，Switch 上为 inline bool TVPProtectInit() { return true; }。游戏 xp3 旁的 212 B .sig 是 PC 版权签名，引擎不读取。

### 0.3 关键新证据：多 xp3 由游戏脚本挂载，引擎零改动

- 引擎自身没有「自动挂同目录 xp3」逻辑：TVPAddAutoPath / TVPRebuildAutoPathTable 定义在 src/core/base/StorageIntf.cpp:978-1120，唯一外部调用点是 TJS 原生方法 Storages.addAutoPath（同文件 :1382）。
- 但试点游戏的 data/sys_source/Init.tjs 自己做了：useArchiveIfExists(name) 用 System.exePath 拼 arcname，命中则 Storages.addAutoPath(arcname + ">")；全脚本 addAutoPath 命中 96 处（含 image/movie/voice 与 @_共通 分支目录）。
- System.exePath = Application.ExePath() = TVPNativeProjectDir（Application.cpp:265-267），而 TVPGetAppPath() = TVPExtractStoragePath(TVPProjectDir)（StorageImpl.cpp:511-519），即**项目 archive 所在目录**。
- ⇒ 只要启动路径传 /kirikiri/haruno/data.xp3 且 14 个 xp3 原样在该目录，image/movie/voice 全部会被游戏脚本自动挂上。这条把 A 路径的补丁面从「文件系统 + 自动路径」缩减为「自动启动 + 首启解包」两处。

### 0.4 一个必须做首启解包的正确性理由（不是性能优化）

per-game 偏好写在**游戏所在目录**：MainScene.cpp:1739-1740 在 startupFrom 里调 IndividualConfigManager::UsePreferenceAt(PathSplit(path).first)，配置文件名为 Kirikiroid2Preference.xml（IndividualConfigManager.cpp:5）。若把游戏目录直接放在只读 ROMFS 上，该配置（以及跟随 TVPProjectDir 的存档写入）会失败。因此 A 路径必须解包到可写 SD，ROMFS 只作为分发载体。

### 0.5 建议的下一步（给 Lead 的排期建议）

1. **P2-1（先验证能不能直启）**：打 A1 自动启动补丁 → 本机构建 NRO → Citron 用**现有 SD 数据目录**（C:/Users/<user>/AppData/Roaming/citron/sdmc/kirikiri/haruno，已存在）验证「跳过选择器、直接进游戏、手柄可操作」。这一步不涉及 3.4GB ROMFS 打包，成本最低，能最早暴露插件/渲染问题。
2. **P2-2（再做自包含）**：把游戏数据放进 ROMFS + 打 A2 首启解包补丁 → 删除 SD 上已解包目录 → 验证首次启动解包 + 二次启动直读 marker。
3. **P3（出包）**：ELF → NSO/NPDM/NACP → hacBrewPack 生成带 ROMFS 的 NSP（复用 docs/builds/005 的链路），Citron 安装后验收。
4. CI（§7）只用于「让构建可重复」，不阻塞 P2-1 本机构建。

---

## §1 对象与版本

### 1.1 K2NX 仓库（源码）

| 项 | 值 | 来源 |
| --- | --- | --- |
| URL | https://github.com/Erige005/Kirikiroid2-NX | E4/GitHub API |
| 默认分支 | main | E4 |
| HEAD | e96b6034c292c6ccdb099823ab6a0a6b505f77f3 | E4（git rev-parse / GitHub API） |
| HEAD 日期 | 2026-10-18T17:27:29Z（提交主题：Switch: create the GL view at 1280x720 (16:9 games had black bars)） | E4 |
| 最近 tag | v1.0.1 → e96b6034c292c6ccdb099823ab6a0a6b505f77f3；v1.0.0 → 09965397859ecea994d57e70fb45b0cff9e21472；v0.1.2-alpha → 9c29e493156272b541fbb77b8a443e3897415d12 | E4（GitHub API /tags） |
| release | v1.0.1，published 2026-10-18T17:01:12Z，prerelease false | E4 |
| 健康 | archived=false；stars 18；forks 0；open issues 1；created 2026-09-30；pushed 2026-10-18T17:27:33Z | E4（GitHub API /repos） |
| 上游 CI | **无**（仓库无 .github/ 目录） | E4 |
| 上游来源 | README 自述 built from zeas2's original Kirikiroid2 1.3.9 source code；仓库内含完整引擎源码（src/core、src/plugins 31 项），**不需要另 clone zeas2/Kirikiroid2** | E4 |

release v1.0.1 资产（GitHub API 实测）：

| 资产 | 大小 | sha256 |
| --- | --- | --- |
| Kirikiroid2-NX.nro | 42,338,934 B | ce3c0169610eb2d65f332e26a16d14c283f9dcf39634dc4f46c2c004860919b8 |
| LICENSE.txt | 44,184 B | 27dd616e…（前缀，完整值见 release API） |
| THIRD_PARTY_LICENSES.md | 3,546 B | 8a7130b8…（前缀） |

### 1.2 许可证与再分发义务

- 仓库根 LICENSE（44,184 B）：KiriKiri license，首段 Copyright (c), W.Dee and contributors，All rights reserved；正文为 BSD 风格三条件：源码再頒布须保留版权声明/条件/免责；二进制再頒布须在随附文档中包含同样声明；未经书面许可不得用组织或贡献者名做产品宣传。文件后附 libjpeg-turbo / libpng / FreeType / Apache-2.0 等第三方文本。
- THIRD_PARTY_LICENSES.md（3,580 B）逐项列出：Kirikiroid2 1.3.9 = KiriKiri license (BSD-style)；extrans = krkrz/SamplePlugin（KiriKiri）；layerExImage = wtnbgo + CxImage（zlib-style）；fstat/layerExDraw/windowEx = 由 krkr2 移植（KiriKiri）；AlphaMovie = 自行重实现（KiriKiri）；Blend2D d2027eb（zlib）；cocos2d-x 3.11.1（MIT）；cocos2d-x 依赖 v3-deps-94（zlib/MIT/BSD/Apache-2.0）；FFmpeg 3.2.19（**LGPL-2.1-or-later，无 GPL 部分**）；OpenCV 3.4.20（BSD-3-Clause）；p7zip/LZMA SDK（LGPL-2.1 + unRAR restriction / public domain）；UnRAR 5.6.5（UnRAR license，不得用来重建 RAR 压缩算法）；libbpg 0.9.8（BSD + bundled HEVC 的 LGPL）；jxrlib（BSD-2-Clause）；libiconv 1.17（LGPL-2.1-or-later）；DroidSansFallback.ttf（Apache-2.0，来自 AOSP）；libnx 4.12.0（ISC）；devkitPro portlibs（MIT/zlib/LGPL-2.0(OpenAL)/FTL/BSD）。
- 再分发义务（对 GalNX 的直接影响）：
  1. 分发 GalNX 构建的 NSP 时**必须**随附 KiriKiri license 全文 + THIRD_PARTY_LICENSES.md，并保留作者署名（Erige005 / zeas2 / W.Dee and contributors）。
  2. FFmpeg 3.2.19 与 libiconv 1.17 是 LGPL：K2NX 静态链接，其 THIRD_PARTY_LICENSES.md 声明 provides the means to relink against modified versions of the LGPL-licensed libraries —— 我们分发 NSP 时也须保留该声明并提供可重链接手段（至少公开我们的补丁、构建脚本与对象/静态库获取方式）。
  3. UnRAR 的 license 禁止用其源码重建 RAR 压缩算法（只解压用途，K2NX 仅解包 RAR 素材，符合）。
  4. **UI 资源不来自源码仓库**：ROMFS 里的 UI 资源是构建时从 zeas2 官方 Kirikiroid2 1.3.9 APK 抽出的（extract_apk_assets.sh），属第三个分发来源，同样受 KiriKiri license + 第三方条款约束，NSP 里携带时需一并声明。
  5. 试点游戏数据本身**不得入库、不得分发**（版权归发行方）；自包含 NSP 只能在本地构建/自用，不得公开分发。此条已由 Pilot README 风险 R6 记录。

### 1.3 预编译 NRO（P1-a 已放入工作区）

- 路径：Workspace/GalNX/workspaces/pilot-01/Kirikiroid2-NX-v1.0.1.nro（与 release 资产同哈希）
- 大小 42,338,934 B；sha256 ce3c0169610eb2d65f332e26a16d14c283f9dcf39634dc4f46c2c004860919b8（E3）
- nstool 解析（E4/E3）：EntryPoint 0x14000020；ModOffset 0xf0；NroSize 0x2121000；ModuleId e3181864542bc0065e5ccd19a935dd77371e0b7b000000000000000000000000；段 .text 0x0/0x1773000、.ro 0x1773000/0x840000、.data 0x1fb3000/0x16e000、.bss 0xb4a000；ROMFS DirNum 7 / FileNum 85
- NACP：Title 全语言 Kirikiroid2-NX；Publisher Erige005 (Kirikiroid2 by zeas2)；DisplayVersion 1.0.1；SupportedLanguage 11 种（AmE/BrE/Ja/Fr/De/LaS/Es/It/Nl/CaFr/Ru，**无中文**）；StartupUserAccount Required；DataLossConfirmation Required；UserAccountSaveDataSize 62 MiB；JournalSize 1 MiB
- ROMFS 内容（romfs_list.py 实测）：约 7.5 MB，7 目录 83 文件，全部为 APK 1.3.9 的 UI 资源（Default/Button_*.png、img/menu_icon.png、res/…、DroidSansFallback.ttf 等）→ **当前 ROMFS 不含任何游戏数据**
- P1-a 已实测（E1/E2）：Citron run 20261030-053221 启动该 NRO 成功，显示 Kirikiroid2 文件选择器 UI，nonblack 0.9018

### 1.4 试点游戏（只读元数据，未读内容）

- 路径：E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气/（约 2.9 GB，运行副本 3.4 GB 在 Citron 虚拟 SD 的 sdmc/kirikiri/haruno）
- 14 个 xp3（data / scenario / image00.. / movie / voice 系列等），每个大 xp3 旁 212 B 的 .sig
- 8 个插件：plugin/csvParser.tpm、extrans.tpm、fstat.tpm、krmovie.dll、layerExImage.tpm、windowEx.tpm、wumsadp.tpm、wuvorbis.tpm
- 中文补丁（xmoe 体系：haruno.xmoe、xmoeParser.dll、data.xm3、*_chs.xp3 等）**本轮不使用**，先保日文原版
- 脚本内插件引用扫描（Lead 用脚本提取自 data.xp3，报告 E:/galnx-build/pilot-01/report_plugins_scan.txt）：fstat 2 处（LogThumbObject.tjs:373、MainWindow.tjs:2245/2416/2467 Storages.fstat(…).size）、csvparser 1 处（Utility.tjs:322 var CSV = new CSVParser();）、plugin 2 处（Affine.tjs、ImageObject.tjs）、font 40 处；wuvorbis/wumsadp/krmovie/layerex/windowex/extrans/kagparserex/json/sqlite 零命中
- 合规：游戏原件只读、不入库、不进入任何提交；本审计只读取目录清单/大小/脚本文本摘录（脚本摘录由 Lead 已完成，本审计引用其报告）

---

## §2 机制审计（源码取证）

> 坐标说明：本节所有「文件:行号」均相对 K2NX 源码根（本机副本 E:/galnx-build/pilot-01/k2nx-src，HEAD e96b6034）。

### 2.1 ROMFS 现状与使用边界

- 挂载：src/core/environ/switch/main.cpp:35  Result rc0 = romfsInit();（注释：UI assets from APK 1.3.9 (tools/extract_apk_assets.sh)）；退出时 romfsExit()（同文件 :45）。
- 用途：ROMFS 只放 UI 资源。证据三条：①platforms/switch/tools/extract_apk_assets.sh 把 APK 的 assets/* 解到 $K2NX_WS/build/romfs；②cocos2dx 的 Switch patch 里 _defaultResRootPath = romfs:/（platforms/switch/cocos2dx/patches/0001-switch-platform.patch:719）；③src/core/visual/FontImpl.cpp:221 注释原文：… through cocos (it lives in RomFS; a romfs:/... path can't go through TJS storages).
- 结论：当前设计下**游戏数据不能直接从 ROMFS 读**（TJS storage 层与 ROMFS 不互通）。A 路径采用「ROMFS 只作分发载体 + 首启解包到 SD」，正是绕开这一点，而不需要给 TJS storage 增加 romfs 媒体类型。

### 2.2 启动流程（从 main 到 StartApplication）

链路（E4，逐跳）：

1. src/core/environ/switch/main.cpp:29-47  main()：K2SBootMark("3 main") → socketInitializeDefault() → setupLogging()（nxlinkStdio 失败则写 sdmc:/switch/kirikiroid2/k2s_log.txt，setvbuf 256KB，dup2 stderr）→ romfsInit() → TVPAppDelegate app; → cocos2d::Application::getInstance()->run() → appletSetCpuBoostMode(ApmCpuBoostMode_Normal) → romfsExit()/socketExit()
2. src/core/environ/cocos2d/AppDelegate.cpp:33-107  applicationDidFinishLaunching：SDL_SetMainReady；FileUtils::setDelegate(TVPCreateCustomFileUtils())；:42-48 __SWITCH__ 下 GLViewImpl::createWithRect("kirikiroid2 frame", Rect(0,0,1280,720))；designResolutionSize(960,640)、SHOW_ALL；TVPSkinManager::InitSkin()；TVPMainScene::CreateInstance()/runWithScene；setAnimationInterval(1/60)；TVPInitUIExtension()；LocaleConfigManager::Initialize(...)
3. AppDelegate.cpp:96-102  启动期 scheduleOnce（"launch"）：
   ~~~cpp
   scene->scheduleOnce([](float dt){
       TVPMainScene::GetInstance()->unschedule("launch");
       TVPGlobalPreferenceForm::Initialize();
       if (!TVPCheckStartupArg()) {
           TVPMainScene::GetInstance()->pushUIForm(TVPMainFileSelectorForm::create());
       }
   }, 0, "launch");
   ~~~
   ⇒ **TVPCheckStartupArg 是唯一的「是否进入文件选择器」开关**；它返回 true 即跳过选择器。
4. 选择器路径（现状）：src/core/environ/ui/MainFileSelectorForm.cpp:199/202 startup(info.FullPath)、:538 startup(fullpath)；:270-286  startup(path)（首次启动先弹 TVPTipsHelpForm，回调里 scheduleOnce 到 doStartup）→ doStartup(path) → TVPMainScene::GetInstance()->startupFrom(path)。传入形如 /kirikiri/haruno/data.xp3（无 sdmc: 前缀，见 2.5）。
5. src/core/environ/cocos2d/MainScene.cpp:1729-1779  startupFrom(path)：TVPCheckStartupPath(path) → IndividualConfigManager::GetInstance()->UsePreferenceAt(TVPBaseFileSelectorForm::PathSplit(path).first) → 若有 UI 子节点 popUIForm(nullptr) → scheduleOnce(doStartup) → doStartup 内 ::Application->StartApplication(path)（:1779）→ 创建 TVPGameMainMenu。
6. src/core/environ/Application.cpp:546-620  StartApplication(path)：TVPNativeProjectDir = path（:564）；TVPProjectDir = TVPNormalizeStorageName(path)（:572）；TVPInitScriptEngine / TVPInitFontNames / TVPInitializeBaseSystems / Initialize / TVPExecuteUserConfig / image_load_thread / TVPLoadPluigins()（:590）/ TVPSystemInit / SetTitle / TVPSystemControl / CheckDigitizer / TVPInitializeStartupScript()（:603）。

### 2.3 自动启动补丁点（A1）

TVPCheckStartupArg 的三个实现：

| 平台 | 位置 | 行为 |
| --- | --- | --- |
| Switch（当前） | src/core/environ/switch/SwitchUtils.cpp:133-136 | bool TVPCheckStartupArg() { return false; // Android: only dump check; no launch arguments on Switch (yet) } |
| win32（参考实现） | src/core/environ/win32/Platform.cpp:91-130+ | 解析 argv；若 TVPCheckExistentLocalFile(argv[1]) 且 TVPCheckArchive(argv[1])==1 → TVPMainScene::GetInstance()->startupFrom(path) 并 return true；若是目录则 TVPListDir 找大小写不敏感的 startup.tjs 再 startupFrom |
| Android（参考实现） | src/core/environ/android/AndroidUtils.cpp:590-605 | 只做 TVPCheckAndSendDumps(...) 后 return false（真启动路径在 Java 侧，不在这个函数） |

补丁方案（A1）：把 Switch 实现改为「读 sdmc:/switch/kirikiroid2/startup.txt，存在则 startupFrom 并返回 true」：

- 伪代码见 §5.1；关键点：
  1. startup.txt 内容是一行 Unix 路径（例：/kirikiri/haruno/data.xp3），与选择器传给 startupFrom 的形式一致；
  2. SwitchUtils.cpp 现有 include 不含 MainScene.h（L4-22 只有 switch.h/tjsCommHead/Platform/StorageImpl/EventIntf/RenderManager/LocaleConfigManager/CCFileUtils/CCDirector/CCScheduler/EGL/…），补丁需补 #include "MainScene.h"；
  3. 调用时机安全：TVPCheckStartupArg 在 AppDelegate 的 scheduleOnce 里被调，此时 TVPMainScene 已 CreateInstance（AppDelegate.cpp:89）、TVPGlobalPreferenceForm::Initialize() 已执行（:97），startupFrom 内部再次 scheduleOnce(doStartup)，与选择器点击走同一条路径，回归面小；
  4. 失败回退：startup.txt 不存在 / 空 / startupFrom 返回 false 时仍 return false → 弹选择器，保持原行为。

### 2.4 首启解包补丁点（A2）与可行性

- 插入点：src/core/environ/switch/main.cpp:35 romfsInit() 之后、:38 TVPAppDelegate app; 之前（该文件 :29-47 为 main 全文，见 2.2）。
- ROMFS 枚举能力（E3/E4 实测）：
  - D:/devkitPro/libnx/include/switch/runtime/devices/romfs_dev.h:113-121：static inline Result romfsInit(void) { return romfsMountSelf("romfs"); }；romfsExit() 即 romfsUnmount("romfs")。
  - 对 D:/devkitPro/libnx/lib/libnx.a 做 aarch64-none-elf-nm：romfs_dev.o 内含 romfs_diropen / romfs_dirnext / romfs_dirclose / romfs_dirreset / romfs_stat / romfs_fstat / romfs_chdir / romfs_open / romfs_read / romfs_seek / romfs_close 与 romFS_devoptab 符号 ⇒ opendir("romfs:/game/haruno")、readdir、stat、fopen 均可用。
  - 因此解包可纯 POSIX 递归：opendir/readdir 判断目录（stat）→ mkdir -p 对应 SD 目录 → 逐文件 64KB 缓冲读写。无需自建索引文件，也不需要 libnx 私有 API。
- 目标侧：sdmc 由 libnx 自动挂载（P1-a 实测：K2NX 已把 k2s_log.txt 写到 sdmc:/switch/kirikiroid2/，E1）；目录创建 mkdir()，空间检查 statvfs("sdmc:/")（libnx fsdev 提供 statvfs 系列）。
- marker：sdmc:/switch/kirikiroid2/.game_extracted（存在即跳过解包）；解包成功后再写 startup.txt（内容 /kirikiri/haruno/data.xp3）供 A1 使用；若 marker 存在但 startup.txt 丢失则按固定路径重建。
- 失败处理：任一步失败 → 打印进度与错误到 stdout（已重定向进 k2s_log.txt）并**不写 marker**，下次启动重试；不放 marke 的半成品目录用临时目录 + rename 保证原子性（rename 同设备原子）。
- 解包耗时（估算，未实测）：3.4 GB / SD 写速（Citron 虚拟 SD 是宿主磁盘，几十至数百 MB/s）→ 约 1–3 分钟；期间显示什么？A2 在 cocos run() 之前执行，屏幕为黑（无 UI），需在文档/README 说明「首次启动黑屏 1–3 分钟属正常」，或后续增强为 libnx 控制台进度条（非必需）。

### 2.5 存储路径语义（决定 startup.txt 写法）

src/core/environ/switch/SwitchUtils.cpp:100-108 注释原文（E4）：

> The engine must only ever see Unix-style paths ("/switch/..."): libnx resolves a leading '/' on the default device (sdmc), while a "sdmc:" prefix is parsed by TJS as a *media type* ("Not supported media type sdmc") and gets its trailing '/' stripped by the file selector ("sdmc:" = current directory). The UI already treats "/" as the root (FileSelectorForm RootPathLen = 1).

配套实现：TVPGetDriverPath() 返回 {"/"}；TVPGetAppStoragePath() 返回 {}；TVPCheckStartupPath 恒 true（同文件）。

⇒ startup.txt 必须写 /kirikiri/haruno/data.xp3（Unix 路径），不能写 sdmc:/...。

文件访问落地路径（StorageImpl.cpp）：
- :387-427 TVPPreNormalizeStorageName：posix 下 name[0]=='/' 时改写成 file://<name>，不处理 romfs: 等自定义前缀；
- :258-368 tTVPFileMedia::GetLocallyAccessibleName：逐段 opendir 做大小写不敏感校正，某段不存在则把该段及之后全部丢弃并 break；
- :362-368 GetLocalName：GetLocallyAccessibleName 为空则抛 TVPCannotGetLocalName；
- :525-537 TVPOpenStream → GetLocalName → :740-803 tTVPLocalFileStream ctor（__SWITCH__ 下 open(holder, rw, 0666)，写模式走 MemBuffer → TVPWriteDataToFile）。
⇒ 这也解释了为什么「游戏数据直接放 ROMFS 只读运行」不可行：该链路从 "/"（SD 根）出发 walk，romfs: 前缀会被当媒体类型，若要支持需同时改 GetLocallyAccessibleName / TVPListDir / TVP_stat / TVPOpenStream 等多处；A 路径用解包完全避开了这组补丁。

### 2.6 多 xp3 / System.exePath（A 路径的关键证据）

- 引擎不自带「自动挂载同目录 xp3」：src/core/base/StorageIntf.cpp:978-1020 定义 TVPAutoPathList / TVPAddAutoPath / TVPRemoveAutoPath；:1041+ TVPRebuildAutoPathTable 对 # 与 TVPArchiveDelimiter 分隔的 archive 条目建表；唯一外部入口是同文件 :1382 的 TJS 原生方法 Storages.addAutoPath。
- 游戏自己挂载（E4，脚本原文由 Lead 提取，报告 E:/galnx-build/pilot-01/report_scripts2.txt）：data/sys_source/Init.tjs 内
  ~~~tjs
  function useArchiveIfExists(name) {
      var arcname = "";
      if (Storages.isExistentStorage(arcname = System.exePath + name)) {
          Storages.addAutoPath(arcname + ">");
          return true;
      }
      return false;
  }
  ~~~
  以及 Init.tjs:36 Storages.addAutoPath(Savefolder)；:139 addAutoPath(arcname + ">")；:151-154 System.exePath + "/"、System.exePath + "data/"、"sys_source/"、"macro/"；:258 sys_source/debug/；:304-308 name + "@_共通/" 等分支目录。全脚本 addAutoPath 命中 96 处。
- System.exePath 的实现：Application.cpp:265-267 ttstr ExePath() { return TVPNativeProjectDir; }；StorageImpl.cpp:511-519 TVPGetAppPath() = TVPExtractStoragePath(TVPProjectDir)；SystemImpl.cpp:1035-1046 TJS 属性 System.exePath 的 getter 调 TVPGetAppPath()。
- ⇒ **结论**：只要启动路径 = /kirikiri/haruno/data.xp3 且目录内 14 个 xp3 原样存在，image/scenario/movie/voice 等会被游戏脚本按 System.exePath（= data.xp3 所在目录）逐个挂载。A 路径无需任何自动路径补丁。（此结论依赖 Init.tjs 实际执行，属**源码级推断 E4**，运行验证待 P2-1。）

### 2.7 插件、.tpm 与 .sig

- .tpm 加载：src/core/base/win32/PluginImpl.cpp:449-452  TVPLoadPlugin 只有一行 bool success = TVPLoadInternalPlugin(name); return;（其后外部 DLL 的 dlopen 逻辑被 #if 0 封死）；:558-589 TVPLoadPluigins 先 TVPLoadInternalPlugins()，再扫 exepath、exepath/system、exepath/plugin 下的 .tpm（:527 TVPSearchPluginsAt 只认 .tpm）并逐个 TVPLoadPlugin。
- 内建插件注册表（src/plugins/InternalPlugins.cpp）：TVPLoadInternalPlugins() 做 ncbAutoRegister::AllRegist() 并 LoadModule("xp3filter.dll")；TVPLoadInternalPlugin(name) = ncbAutoRegister::LoadModule(TVPExtractStorageName(name))。全仓库 NCB_MODULE_NAME 共 19 个：addFont、AlphaMovie、csvParser、dirlist、extrans、fftgraph、fstat、getabout、getSample、layerExDraw、layerExImage、layerExMovie、perspective、saveStruct、varfile、win32dialog、windowEx、wutcwf、xp3filter（均 .dll 后缀）。
- 试点游戏 8 个插件对照：

| 游戏插件 | K2NX 处理 | 依据 |
| --- | --- | --- |
| csvParser.tpm | ⚠️ 有内建实现（src/plugins/csvParser.cpp，NCB 键 csvParser.dll），但原始 NRO 因名字不一致**未激活**；patch C 后生效 | E1/E4，§2.11 |
| extrans.tpm | ⚠️ 有内建实现（src/plugins/extrans/，NCB 键 extrans.dll），原始 NRO 未激活；patch C 后生效。脚本层零直接调用（可能由 KAG 标签间接使用，未验证） | E4，§2.12 |
| fstat.tpm | ⚠️ 有内建实现（src/plugins/fstat/，挂 Storages 类，NCB 键 fstat.dll），原始 NRO 未激活；patch C 后生效。脚本有 4 处 Storages.fstat 调用 | E4，§2.12 |
| layerExImage.tpm | ⚠️ 有内建实现（src/plugins/layerExImage/，挂 Layer 类，NCB 键 layerExImage.dll），原始 NRO 未激活；patch C 后生效。脚本层零直接调用（可能由 KAG 间接使用，未验证） | E4，§2.12 |
| windowEx.tpm | ⚠️ 有内建实现（src/plugins/windowEx/，K2NX 自研移植，NCB 键 windowEx.dll），原始 NRO 未激活；patch C 后生效。**E1 崩溃就是这个插件未激活导致的** | E1/E4，§2.11 |
| krmovie.dll | 无内建 NCB 名，但视频走核心 FFmpeg overlay：VideoOvlImpl.cpp:198-205 调 GetVideoOverlayObject / GetVideoLayerObject / GetMixingVideoOverlayObject / GetMFVideoOverlayObject，实现在 src/core/movie/ffmpeg/krffmpeg.cpp:60+（:45 TVPInitLibAVCodec） | E4 |
| wuvorbis.tpm | 无内建 NCB 名，但 Vorbis 解码是核心内建 src/core/sound/VorbisWaveDecoder.cpp（日志前缀 wuvorbis:） | E4 |
| wumsadp.tpm | 无内建 NCB 名；ADPCM 由 libavcodec 兜底（src/core/sound/FFWaveDecoder.cpp 用 avcodec_find_decoder/avcodec_open2） | E4（解码路径）+ 未验证（实际播放） |

- 未内建的插件**不会在加载期报错**（PluginImpl.cpp:449-452 只 return），而是在游戏调用其函数时由 TJS 抛 not found 类异常 → 表现可能是脚本中断/黑屏，诊断要看 k2s_log.txt。**E1 已实证这条链**：windowEx 未激活 → mainwindow.tjs:990 抛异常（§2.11）。⇒ 上表 ⚠️ 行必须在引入 patch C 后才算「有内建可用」；csvParser 与 fstat 是脚本层实际调用点，patch C 后仍有 TJS 炸点的可能性已很低，但需 P2-1 实跑确认。
- .tpm/.sig：全仓库 grep Trusted|IsTrusted|\.sig\b|CheckSignature|VerifySignature 在 src/core 与 src/plugins 零命中；src/core/environ/switch/Protect.h（373 B）为 APK 完整性 stub（TVPProtectInit() 恒 true，注释说明与游戏数据保护无关）。⇒ **K2NX 不读取、不校验 xp3 旁 212 B 的 .sig**；.sig 文件留在目录里也无影响（但会增加 NSP 体积，打包时可剔除，需先确认引擎不依赖其存在——源码级可确认不依赖）。

### 2.8 存档与偏好路径

- per-game 偏好：MainScene.cpp:1739-1740 在 startupFrom 里 IndividualConfigManager::UsePreferenceAt(PathSplit(path).first)；IndividualConfigManager.cpp:5 #define FILENAME "Kirikiroid2Preference.xml"；:25 CheckExistAt = <folder>/Kirikiroid2Preference.xml；:30-47 CreatePreferenceAt 只 Clear() 并设 CurrentPath（文件由 SaveToFile 创建）；:49 UsePreferenceAt 不存在返回 false（不报错）。
- 全局偏好：MainScene.cpp:2479-2498 TVPGetDataPath() = cocos FileUtils::getWritablePath() → sdmc:/switch/kirikiroid2；实测该目录下有 .preference/recentpath.xml（118 B，E1/E3）。
- 存档：跟随 TVPProjectDir 的应用内路径规则（TVPCreateFolders mkdir；k2s_WriteDataToFile 先写 <name>.<time>.bak 再替换；TVPWriteDataToFile 打印 [K2S] write %s (%u bytes, %u ms): %s）。
- **E1 已观察到存档根（2026-10-30 更新）**：k2s_log.prev.txt 第 7 行原文 `06:03:26 (info) Data path : file://./kirikiri/haruno/savedata/` ⇒ 存档与偏好都落在 **sdmc 上的游戏目录内**（`/kirikiri/haruno/savedata/`），A 路径解包到 SD 后该目录天然可写，**不需要额外补丁**；但「首次真实写入/读回成功」仍需 P3 实测确认（当前未验证）。反过来说，这也再次排除了「游戏数据只放 romfs、不复制到 SD」的形态（除非后续专门做存档重定向补丁）。
- ⇒ 正确性要求：per-game 偏好与存档都在**游戏目录**内，游戏目录必须可写 ⇒ 解包到 SD（§0.4）。

### 2.9 输入（手柄 / 虚拟鼠标）

- libnx 手柄初始化（cocos patch platforms/switch/cocos2dx/patches/0001-switch-platform.patch:50-128 新增 cocos/base/CCController-switch.cpp）：padConfigureInput(1, HidNpadStyleSet_NpadStandard)；padInitializeDefault(&s_pad)（Joy-Con 双/单、Pro、掌机模式统一报为一个 controller）。
- ButtonMap：A→BUTTON_A、B→BUTTON_B、X→BUTTON_X、Y→BUTTON_Y、L/R→shoulder、ZL/ZR→AXIS_LEFT/RIGHT_TRIGGER、StickL/R→LEFT/RIGHT_THUMBSTICK、Plus→BUTTON_START、D-pad→DPAD_*。
- 游戏层输入（E4）：MainScene.cpp:2300-2363 onAxisEvent —— __SWITCH__ 下首次推左摇杆自动显示虚拟鼠标光标（showVirtualMouseCursor(true)），光标在 GameNode 空间移动（dead=0.15，step = 12*v*|v| + sign，clamp 到屏幕），并合成 onMouseMove；:2365-2395 onPadKeyDown —— UI 层（选择器/设置/对话框）只认 Android back key ⇒ B 映射 KEY_BACK；游戏层虚拟鼠标模式下 A=左键点击光标位置、B=右键（_mouseBtn 切换 + _currentWindowLayer->onMouseClick(GameNode->convertToWorldSpace(_mouseCursor->getPosition()))）。
- 虚拟光标外观：MainScene.cpp:2083-2120 showVirtualMouseCursor 用 TVPCreateCUR()（加载 default.cur，经 cocos FileUtils 从 romfs:/res 取），缩放取偏好 vcursor_scale（默认 0.5）。
- README 声称（属 README 声称，非本审计验证）：A=advance/confirm、B=cancel/right-click、D-pad=select、左摇杆=鼠标光标（A/B 在光标处点击）、−=Kirikiroid2 menu、X/Y/L/R/ZL/ZR/+ 同 Android。与源码 K2S 实现一致（E4 交叉确认），但**未在本游戏上实测**。

### 2.10 已知限制（README 声称 + 源码）

- README 自述（README.md，属 README 声称）：需要 CFW Atmosphère + **title takeover** 模式（Album 的 applet mode 内存不足）；已知问题：Yes/No 系统消息框恒选第一按钮；未移植插件（KAGParserEx / E-mote / scriptsEx / layerExRaster / shrinkCopy / json / sqlite 等）；退出时可能报 software was closed because an error occurred；**仅软件渲染**。
- 渲染实现（E1）：P1-a 实测 k2s_log.txt 记录 GL_VERSION: OpenGL ES 3.2 Mesa 20.1.0-rc3、GL ext: VAO=yes mapbuffer=yes ⇒ cocos 走 Mesa 软件 GLES；平台表注释也说 OpenGL ES 2.0 via mesa + switch-glfw（cocos2dx/CMakeLists.txt:3）⇒ 性能上限受软渲染限制，3D/大分辨率场景需实测（本游戏为 2D VN，风险中等）。
- 仓库 issue：#2 Grisaia chronos rebellion won't run（2026-10-19，0 评论）—— 说明存在个别游戏不兼容；维护者单人、18 stars、0 forks，长期维护风险中等。
- 硬编码版本风险：K2NX README 记录 build 过程需 pin 一整套外部版本（cocos2d-x 3.11.1、FFmpeg 3.2.19、OpenCV 3.4.20、UnRAR 5.6.5、libbpg 0.9.8、jxrlib master、Blend2D 固定 commit、libiconv 1.17、p7zip 16.02 / LZMA SDK 16.04、APK 1.3.9）—— 这些版本关系是「1.3.9 时代 API」决定的，不能随意升级（例如 1.3.9 movie 代码用 FFmpeg 5.0 前 API）。

---

### 2.11 插件名别名缺陷（E1 崩溃根因）与 patch C 复核（已实施）

> **实施状态（2026-10-30，Lead 确认）**：patch C 已在 k2nx-ws 工作副本 `E:/galnx-build/pilot-01/k2nx-ws/src` 落地（生成脚本 `E:/galnx-build/pilot-01/patches/apply_plugin_alias_patch.py`），并已通过本审计的源码级复核——结论：**必要、安全、最小可用**（复核细节见本节后半）；构建与运行验证由 Lead 用重建 NRO 回填。Lead 决定：本审计提出的「已注册时误打印 no built-in module」定位为 cosmetic 改进，暂不改动已通过审计的代码，仅当重建后日志出现误导性 no-module 行时再处理。<br>**2026-10-30 06:33 构建 / 06:34 Citron 首跑已实证**：日志出现 5 条 `[GalNX] internal plugin loaded via .tpm alias`（csvParser / extrans / fstat / layerExImage / windowEx），`registerExEvent` 异常消失、本次运行 0 exception（证据见 §2.13.5）。

**E1 证据（Citron 运行日志原文）**

- 日志路径：Citron 虚拟 SD 的 sdmc/switch/kirikiroid2/k2s_log.prev.txt（引擎每次启动会把上一次的 k2s_log.txt 改名为 k2s_log.prev.txt）；本次为 06:03 那轮运行结束时留存的版本。
- 本审计副本：E:/galnx-build/pilot-01/refs/k2s_log-prev-20261030-0603.txt（4,604 B，sha256 891e90ca1bab38afdf6bf9c9e040128d3a68a1b3bf161af40e4fd36c108fb945）。
- 关键原文（逐行摘录）：

~~~
06:03:27 (info) Loading csvParser.tpm
06:03:27 (info) Loading extrans.tpm
06:03:27 (info) Loading fstat.tpm
06:03:27 (info) Loading layerExImage.tpm
06:03:27 (info) Loading windowEx.tpm
06:03:27 (info) Loading wumsadp.tpm
06:03:27 (info) Loading wuvorbis.tpm
...
06:03:28 ==== An exception occured at mainwindow.tjs(990)[(function) SetExEvent], VM ip = 15 ====
#(990) 		this.registerExEvent();
00000015 calld %0, %-1.*2()	// *2 = (string)"registerExEvent"
~~~

注意：krmovie.dll 不在 Loading 列表中——扫描器只认 .tpm 后缀（PluginImpl.cpp:527），这本身是预期行为。

**因果链（四步，全部有源码依据）**

1. 启动时 TVPLoadPluigins() 扫描 exepath、exepath/system、exepath/plugin 下的 .tpm（PluginImpl.cpp:558-589），对每个文件先打印 "(info) Loading <name>"，再调 TVPLoadPlugin()。因此**日志里的 Loading 不代表加载成功**，它是在调用之前打印的。
2. TVPLoadPlugin() 的实现只有一行：bool success = TVPLoadInternalPlugin(name); return;（PluginImpl.cpp:449-452）。success 被丢弃，其后外部 DLL 的 dlopen 逻辑被 #if 0 封死——加载失败**完全静默**。
3. TVPLoadInternalPlugin() = ncbAutoRegister::LoadModule(TVPExtractStorageName(name))；LoadModule 把名字小写后到注册表里**精确匹配**（ncbind.cpp:15-32）。内建模块注册键是 windowEx.dll（src/plugins/windowEx/main.cpp:12 #define NCB_MODULE_NAME TJS_W("windowEx.dll")），而游戏请求的是 windowEx.tpm → 查不到，返回 false。
4. ncbAutoRegister::AllRegist() 只把各编译单元的静态注册对象填进 _internal_plugins 表（ncbind.hpp:2115-2166；AllRegist() 在 :2150，逐行 AllRegist(line) 在 :2132-2141；源码里的 p->Regist() 被注释掉），**真正 Regist 只发生在 LoadModule 成功时**。所以没有任何回退路径能让内建实现生效。
5. 结果：Window 类上没有 registerExEvent 方法；游戏 MainWindow.tjs:990 的 this.registerExEvent() 抛 "Member ... does not exist" 类 TJS 异常 → E1 记录的 VM ip=15 异常，游戏停在打开主窗口的时刻（P1-a 截图即停在标题/前奏之后）。

**影响面（比单个 windowEx 大）**

- 试点游戏 plugin/ 下 7 个 .tpm 全部与内建键不一致（.tpm vs .dll）⇒ csvParser / extrans / fstat / layerExImage / windowEx 五个「已经编译进 NRO 的内建实现」在原始版本里**一个都没有被激活**。
- E1 只暴露了第一个炸点（windowEx 在 MainWindow 构造期最早被调用）；即使没有它，CSVParser（Utility.tjs:322）与 Storages.fstat（MainWindow.tjs:2245/2416/2467 等）也会在后续脚本路径上再炸。

**patch C（Lead 工作副本）diff 摘要**

- 唯一改动文件：src/plugins/InternalPlugins.cpp（相对 K2NX HEAD e96b6034c292c6ccdb099823ab6a0a6b505f77f3）。
- 补丁应用脚本：E:/galnx-build/pilot-01/patches/apply_plugin_alias_patch.py（按 CRLF 精确字节替换函数体）。
- 改动 1：顶部新增 #include <cstdio>。
- 改动 2：TVPLoadInternalPlugin 的函数体由一行扩展为：
  - 先 ttstr name = TVPExtractStorageName(_name); 调 ncbAutoRegister::LoadModule(name)，成功则 printf("[GalNX] internal plugin loaded: %s\n", ...) 并 return true；
  - 否则取 name.AsLowerCase()，若长度大于 4 且尾部 4 个字符是 ".tpm"，构造去掉 ".tpm" 再加 ".dll" 的别名，再 LoadModule(别名)，成功则 printf("[GalNX] internal plugin loaded via .tpm alias: %s -> %s\n", ...) 并 return true；
  - 两者都失败时打印 "[GalNX] no built-in module for game plugin: %s"（.tpm 路径）或 "[GalNX] no built-in module for plugin: %s"（非 .tpm 路径），return false。
- 规模：约 +20 行；不改 ncbind.cpp 的 LoadModule；不触碰 TVPLoadPlugin 的外部加载封死逻辑。

**复核结论：必要、安全、最小可用**

- **必要性**：E1 已证明原始 NRO 必崩；patch C 不新增功能，只是把已经静态链接进二进制的内建实现与游戏请求的名字对上——属于「接线修复」。
- **大小写安全**：LoadModule 入口处统一 AsLowerCase（ncbind.cpp:16），别名同样走该入口，不会出现大小写漏配。
- **重复加载安全**：LoadModule 对已注册名字直接返回 false（ncbind.cpp:18-20），不会重复 Regist；TVPRegisteredPlugins 保证幂等。
- **xp3filter.dll 无冲突**：TVPLoadInternalPlugins() 启动时已 LoadModule("xp3filter.dll")；游戏 plugin/ 目录里没有 xp3filter，不存在竞争。
- **krmovie.dll 打不中**：直名不是 .tpm，走 "no built-in module for plugin" 分支（预期行为，视频由内建 FFmpeg overlay 处理，见 §2.12）。
- **封死语义不变**：TVPLoadPlugin 在 return 之后即结束，外部 .tpm 仍然永远不会被 dlopen。
- **生效范围完整**：TVPLoadPlugin 的两个调用点（PluginImpl.cpp:587 自动扫描、:989 TJS Plugins.link(name)）都经过 TVPLoadInternalPlugin，patch C 对两者同时生效；本游戏脚本层无 Plugins.link 调用，因此主要靠扫描路径。
- **编译安全（已逐项核对 tjsString.h）**：ttstr 有 operator==(const tjs_char*)（:218）、operator+=(const tjs_char*)（:272）、GetLen()（:420）、SubString(unsigned int pos, unsigned int len)（:450）、AsLowerCase()（:366）。注意 SubString 的两个参数都是 unsigned int 位宽，写补丁时不要传 int。

**两处非阻塞改进建议**

1. **日志准确性**：当 LoadModule 因「已经注册」返回 false 时，patch C 会错误地打印 "no built-in module"。建议在失败分支先查 TVPRegisteredPlugins（或调用方可忽略返回值这一点在日志里注明），把「已加载」与「无模块」区分开。该问题只影响日志，不影响功能（TVPLoadPlugin 本来就丢弃返回值）。
2. **收口方式（可选）**：把别名逻辑下沉到 ncbAutoRegister::LoadModule（单一收口，所有调用点自动受益），或在 TVPLoadInternalPlugins() 里启动时预注册 5 条别名（windowEx.tpm → windowEx.dll 等），避免每次请求都走别名分支。当前补丁实现已够用，不必在 P2 阶段改动。

### 2.12 游戏 plugin/ 8 文件 → K2NX 内建模块映射表

游戏 plugin/ 目录实测（Citron 虚拟 SD 的 sdmc/kirikiri/haruno/plugin/，只列文件名与大小，未读取内容）：8 个插件文件 + 8 个同名 .sig（每个 212 B）。

| 游戏文件 | 大小 | K2NX 内建模块键 | 原始 NRO 行为 | patch C 后 | 内建实现位置 | 脚本调用点（E1 提取） | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| csvParser.tpm | 86,016 B | csvParser.dll | 未激活 | **激活** | src/plugins/csvParser.cpp:5（NCB 名）、:370 TJSCreateNativeClassForPlugin("CSVParser")、:471 addMember(global,"CSVParser",...) | Utility.tjs:322 的 new CSVParser() | patch C 后可用；启动期不炸，首次 CSV 使用点才炸（原始 NRO 的隐患 2 号） |
| extrans.tpm | 237,568 B | extrans.dll | 未激活 | **激活** | src/plugins/extrans/（Main.cpp:17 有 NCB 名；attach 宏未逐行确认） | 脚本零直接命中（可能由 KAG 标签间接使用） | patch C 后可用；间接使用未验证（U6） |
| fstat.tpm | 128,000 B | fstat.dll | 未激活 | **激活** | src/plugins/fstat/main.cpp（K2S 移植 krkr2）：NCB_ATTACH_CLASS(StoragesFstat, Storages) :933、TVPExecuteExpression(StoragesFstatPreScript) :1022 | LogThumbObject.tjs:373、MainWindow.tjs:2245/2416/2467 的 Storages.fstat(...) | patch C 后可用；原版会在这些点抛 not found（隐患 3 号） |
| layerExImage.tpm | 126,976 B | layerExImage.dll | 未激活 | **激活** | src/plugins/layerExImage/（NCB_ATTACH_CLASS_WITH_HOOK(layerExImage, Layer)，Main.cpp:29） | 脚本零直接命中（KAG 的 Layer 扩展可能间接使用） | patch C 后可用；间接使用未验证（U6） |
| windowEx.tpm | 229,376 B | windowEx.dll | 未激活 | **激活** | src/plugins/windowEx/（K2NX 自研移植 krkr2 的 windowEx；NCB_ATTACH_CLASS_WITH_HOOK(WindowEx, Window)，main.cpp:176） | MainWindow.tjs:985-1000 SetExEvent：registerExEvent / setMessageHook / disableResize | **E1 崩溃根因**；patch C 后可用（空实现，只保证不中断，无真实窗口行为） |
| wumsadp.tpm | 57,856 B | 无（19 个内建键里没有） | 未加载（不报错） | 仍未加载（预期） | 无独立模块；ADPCM 解码由核心兜底：src/core/sound/WaveIntf.cpp:744-767 注册 4 个 creator，RIFF WAV 解码器只接受 PCM/IEEE_FLOAT/EXTENSIBLE（:630-632），其他 format_tag 落到 FFWaveDecoder（FFWaveDecoder.cpp:100-109，libavcodec） | 脚本层零命中（.ogg 为主；Parser.tjs:2020-2023 有 .ogg → .wav 回退） | 不需要插件；ADPCM/WMA 解码**未实测**（U4） |
| wuvorbis.tpm | 200,704 B | 无 | 未加载（不报错） | 仍未加载（预期） | 无独立模块；Vorbis 是核心内建解码器（src/core/sound/VorbisWaveDecoder.cpp，日志前缀 wuvorbis:），TVPCreateWaveDecoder 逆序优先命中 vorbis creator | 脚本大量 .ogg（BGM/语音，ConfigObject.tjs、EndingObject.tjs 等） | 不需要插件；.ogg 播放路径成立（源码级），实际音质/同步未实测（U4） |
| krmovie.dll | 278,528 B | 无 | 不扫描（.dll 不是 .tpm） | 同左 | 无独立模块；视频走核心 overlay：VideoOvlImpl.cpp:198-205 调 GetVideoOverlayObject / GetVideoLayerObject / GetMixingVideoOverlayObject / GetMFVideoOverlayObject，实现在 src/core/movie/ffmpeg/krffmpeg.cpp:60+（:45 TVPInitLibAVCodec） | 脚本层零命中（视频由游戏脚本/引擎视频层触发） | 不需要插件；movie 播放**未实测**（U3），软渲染下视频性能风险较高 |

**「无对应时会不会在某个 TJS 调用点再炸」的逐项判定**

- 会炸的三个：windowEx（已实证）、csvParser、fstat。三者内建实现都在仓库里，patch C 之后均可加载成功；是否还有语义差异（例如 windowEx 的 registerExEvent 是空实现、fstat 返回的 size 语义与 PC 版是否一致）需要 P2-1 实跑确认。
- 不会炸的两个：wumsadp、wuvorbis——脚本层没有按名字调用它们，它们的职责（解码器注册）在 K2NX 里改由核心 WaveIntf 的 decoder manager 完成；风险从「插件缺失」转移为「解码结果是否正确」，只能靠实跑音频验证。
- krmovie.dll 既不扫描也无调用点，视频由核心 FFmpeg overlay 接管；风险同样转移到「实际播放」而非「加载报错」。
- extrans、layerExImage：脚本零直接命中，但它们在 PC 版里通常由 KAG 的图形/转场标签间接使用。若 P2-1 后续场景出现 TJS 异常，优先怀疑这两个（它们是「已激活但实现可能有简化」的一类，与「未激活」不同）。

**一个容易误读的日志点**：k2s_log.txt 里的 "(info) Loading xxx.tpm" 是 TVPAddImportantLog 在调用加载之前打印的（PluginImpl.cpp:587 附近），**不代表加载成功**；判断是否成功要看 patch C 新增的 "[GalNX] internal plugin loaded ..." 行，以及是否仍出现 "An exception occured at ..." 行。

---


### 2.13 对 Lead 落地补丁（A1/A2）的源码级预复核 + 首次落地构建验证（2026-10-30 06:5x / 06:3x）

审查对象（均只读，未修改）：

| 文件 | 大小 | 作用 |
| --- | --- | --- |
| E:/galnx-build/pilot-01/patches/apply_k2nx_patches.py | 2,512 B / 56 行 | 只负责 A1+A2 两个替换；带标记检测（幂等，可重复运行） |
| E:/galnx-build/pilot-01/patches/galnx_autostart.inc | 1,899 B / 47 行 | A1：替换 SwitchUtils.cpp 的 TVPCheckStartupArg（读 sdmc:/switch/kirikiroid2/autostart.txt） |
| E:/galnx-build/pilot-01/patches/galnx_extract.inc | 6,534 B / 190 行 | A2：main.cpp 插 GalNX_MaybeExtractGame()，按 romfs:/game_files.txt 清单把 payload 拷到 SD 并写 autostart |

当前工作副本状态（2026-10-30 06:33 构建后实查）：k2nx-ws 已同时打上 A1（SwitchUtils.cpp 的 TVPCheckStartupArg 读 sdmc:/switch/kirikiroid2/autostart.txt）、A2（main.cpp 插入 GalNX_MaybeExtractGame() 并在 romfsInit() 之后调用）与 patch C（InternalPlugins.cpp .tpm→.dll 别名）；三者均已进入 06:33 构建的 NRO（ELF strings 可见三条日志文案与符号）并通过 Citron 首跑验证（A1/patch C 生效、A2 因 romfs 无清单而 no-op，见 2.13.5）。

#### 2.13.1 P0：打包清单的 startup= 必须指向 .xp3 文件（写成目录会静默丢全部 14 个 xp3）

四条源码证据（链式，任意一环都可单独复核）：

1. TVPExtractStoragePath 返回「含最后一个分隔符」的路径 —— src/core/base/StorageIntf.cpp:917-935（第 919 行原注释：extract "name"'s path ( including last delimiter ) and return it.）。
2. TVPGetAppPath() = TVPExtractStoragePath(TVPProjectDir) —— src/core/base/win32/StorageImpl.cpp:511-519（第 517 行 static ttstr apppath(TVPExtractStoragePath(TVPProjectDir));，首次调用即缓存）。
3. TJS 的 System.exePath getter 直接返回 TVPGetAppPath() —— src/core/base/win32/SystemImpl.cpp:1035-1046（第 1039 行 *result = TVPGetAppPath();）。
4. 游戏脚本自己用 System.exePath 拼全部 xp3，且**不在中间补斜杠**：extract/data/sys_source/Init.tjs:23（System.exePath + "savedata/"）、:137（useArchiveIfExists 里 arcname = System.exePath + name）、:302/319/325/333/342/356/369/382/396/404/409/414/435/456/464（System.exePath + "xxx.xp3"，共 14 个 xp3）。

推论（关键）：

- startup=/kirikiroid/haruno（目录、无尾斜杠）→ StartApplication（src/core/environ/Application.cpp:564/572）令 TVPProjectDir=file://./kirikiroid/haruno → TVPGetAppPath 走到最后一个 / 后返回 file://./kirikiroid/（**父目录**）→ 所有 System.exePath + "image01.xp3" 等全部指到 /kirikiri/ 下 → 14 个 xp3 一个都挂不上。引擎仍能启动到标题（脚本能找到 sys_source），但所有图像/语音/视频/脚本资源缺失，表现为白屏/报错/黑图，且不会在启动期给出明确错误。
- startup=/kirikiroid/haruno/data.xp3（文件）→ TVPProjectDir=file://./kirikiroid/haruno/data.xp3 → TVPGetAppPath=file://./kirikiroid/haruno/（**正确**）→ 14 个 xp3 正常挂载。这与 P1-a 手工在选择器里点 data.xp3 的路径形态完全一致，也是 E1 日志里 Data path : file://./kirikiroid/haruno/savedata/ 的来源。
- 顺带修 per-game 偏好：MainScene.cpp:1740 用 UsePreferenceAt(TVPBaseFileSelectorForm::PathSplit(path).first)。PathSplit（src/core/environ/ui/FileSelectorForm.cpp:47-80）对尾斜杠路径在第 56-59 行直接 ret.second=path; return;（first 为空）；对目录无尾斜杠则 first=/kirikiri（父目录）。只有 .xp3 形态能同时得到 first=/kirikiroid/haruno（偏好落在游戏目录）和 exePath 正确。

结论：A2 生成的 romfs:/game_files.txt 中 `startup=` 必须写成 `<target>/data.xp3`（本作即 /kirikiroid/haruno/data.xp3），**不要**写成目录。galnx_extract.inc 第 10 行注释示例（startup=/kirikiri/<game>）应同步修正，否则打包脚本按注释实现就会踩此坑。

#### 2.13.2 A2（galnx_extract.inc）复核结论：结构正确，5 点建议

| 编号 | 问题 | 建议 | 影响 |
| --- | --- | --- | --- |
| A2-1 | 无 SD 剩余空间检查（payload 约 2.9-3.4 GB；空间不足时会在中途失败留半解包） | manifest 增 bytes= 总字节（打包脚本已知），解包前用 statvfs("sdmc:/") 或 fsOpenSdCardFileSystem+fsFsGetFreeSpace 预检，不足则打印明确错误并直接返回（不写 marker） | 真机/模拟器 SD 空间不足场景可诊断 |
| A2-2 | 解包发生在 TVPAppDelegate 构造之前，未设 CPU boost（默认频率拷 3 GB 可能数分钟黑屏） | GalNX_MaybeExtractGame() 前后用 appletSetCpuBoostMode(ApmCpuBoostMode_FastLoad) → Normal 包住（libnx applet 已由 __appInit 初始化，可调用） | 首启时长/稳定性 |
| A2-3 | 写 marker / autostart 前未保证 sdmc:/switch/kirikiroid2 存在：setupLogging 只在 nxlinkStdio 失败时才 mkdir 该目录（main.cpp:9-25）；nxlink 可用（如 Citron）时 marker 与 autostart 都会写失败 | GalNX_MaybeExtractGame 开头与 GalNX_WriteAutostart 内先 GalNX_MkDirs("sdmc:/switch/kirikiroid2") | 边缘场景下回落到选择器、marker 永不写入（每次启动全量 stat 比对） |
| A2-4 | marker 命中分支只信版本号：用户清掉/损坏 SD 游戏目录但 marker 还在时，会直接写 autostart 打开不存在的路径 | marker 命中后额外 stat("sdmc:" + startup)（或 target 下 data.xp3）校验，失败则视为需要重拷 | 避免二次启动失败无提示 |
| A2-5 | startup= 为空时 GalNX_WriteAutostart 静默 return（打包脚本漏写该行 → 永远进选择器且无日志） | 解析后若 startup 为空打印 WARNING 并说明原因 | 可诊断性 |

其余已核对正确的点：stdlib/头文件齐全（<stdio.h>/<sys/stat.h>/<string>/<vector>/<switch.h>）；GalNX_MkDirs 的 sdmc: 前缀断点（i<=4 skip）逻辑可用；1 MB 静态缓冲与断点续传（GalNX_FileHasSize）正确；failed!=0 时不写 marker 下次重试正确；manifest 行 1024 B 上限对 255 B 文件名足够；解包在 romfsInit 之后、文件读取可用。

#### 2.13.3 A1（galnx_autostart.inc）复核结论：逻辑正确，1 点小建议

- 正确项：文件路径 sdmc:/switch/kirikiroid2/autostart.txt 单行、GalNX_TrimLine 去尾空白、GalNX_AutostartPathExists 用 stat("sdmc:"+path) 校验、` TVPMainScene::GetInstance()->startupFrom(path) ` 与选择器路径同入口、不存在时回落选择器 —— 与 §2.3 分析的补丁点一致。
- 建议：printf 后补 fflush(stdout)。setupLogging 把 stdout 设成 256 KB 全缓冲（main.cpp:20-24），若 startupFrom 随后在引擎内崩溃，最后几行日志（包括 autostart 使用了哪个路径）可能丢失，影响现场诊断。

#### 2.13.4 与 §5 草案的差异说明

- 实际落地版（本次审查对象）与 §5 草案有两处不同，**以落地版为准**：①A1 的触发文件名是 autostart.txt（草案为 startup.txt）；②A2 是「romfs:/game_files.txt 清单驱动 + 解包到 target」，而非草案的「固定 romfs:/game/haruno 递归拷贝」——清单驱动更通用（引擎与游戏内容解耦），但把正确性责任前移到打包脚本（见 2.13.1）。
- 因此 §5 保留为设计记录；若后续对照实现，先读 §2.13。

#### 2.13.5 首次落地构建与 P2-1 Citron 首跑（2026-10-30 06:33 构建 / 06:34 运行，audit-engines 只读复核 Lead 产物）

**构建产物（r1）**：NRO `E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r1.nro` **42,351,222 B / sha256 c1d76767dd32a816e08d5917992b3eda21ed5db5a586483450e19f5f954efc10**；ELF `K2NX-rebuilt-galnx-r1.elf` **113,874,232 B / sha256 f39628ae6d3017bfe98ac71e3666058f589c08e9d01f5a2b9cf23fafd7ad14c3**。nstool：ModuleId `d3fac54ddf05feed19809f7378c012faad832662000000000000000000000000`、NroSize `0x2124000`、.text `0x1775000` / .ro `0x841000` / .data `0x16e000` / .bss `0xc4a000`。三处补丁的字符串与符号均在 ELF/NRO 内（A1 的 `sdmc:/switch/kirikiroid2/autostart.txt`、A2 的 `romfs:/game_files.txt`、patch C 的 `internal plugin loaded via .tpm alias: %s -> %s`）。

**构建期新增的 Windows 专属坑（E2BIG，最终修复已进 run_build_k2.sh）**：链接阶段归档 `libcocos2d.a` 时 Windows CreateProcess 命令行上限（32,767 字符）被击穿，`aarch64-none-elf-gcc-ar.exe: Argument list too long`，ninja 报 FAILED code=126 且**日志里没有 "error:" 前缀**（grep error 抓不到）。修法：`build-scripts/ar-chunk.sh`（CHUNK=120，首块 `qc` 后续 `q`，末尾 ranlib）+ 在 configure 之后用 `patch_ar_rules.py` 改 `CMakeFiles/rules.ninja` 里 3 条 `CXX_STATIC_LIBRARY_LINKER__*` 规则的 command。注意：**每次重新 configure 都会覆盖 rules.ninja，必须重跑该 patch**（`run_build_k2.sh` 已内置）。

**P2-1 首跑（run `workspaces/citron-harness/runs/20261030-063440-K2NX-rebuilt-galnx-r1/`，pid 31200，06:34:51→06:36，elapsed 37 s）逐项复核**：

| 检查项 | 结果 | 证据（k2s_log / 截图） |
| --- | --- | --- |
| A1 自动启动 | **PASS** | `[GALNX] autostarting game from /kirikiri/haruno/data.xp3`（随后不再出现文件选择器） |
| P0：startup= 必须是 .xp3 | **PASS** | 同日志 `06:34:51 (info) Data path : file://./kirikiri/haruno/savedata/`（exePath 落在游戏目录，而非父目录）；14 个 xp3 全部被自动路径表挂载 |
| patch C：.tpm→.dll 别名 | **PASS** | 5 条 `[GalNX] internal plugin loaded via .tpm alias:`：csvParser / extrans / fstat / layerExImage / windowEx；wumsadp.tpm、wuvorbis.tpm 走 `no built-in module` 分支（预期，核心解码替代见 §2.12） |
| P1-b 的 mainwindow.tjs(990) 崩溃 | **消失** | 本次日志 `registerExEvent` 无异常、`0 exception`（旧 NRO 在 06:24 的日志里才有该异常） |
| 启动脚本链 | **PASS** | `Loading startup script` → startup.soc → userMacro.ks → eyecatch.ks → logo.ks → `Startup script ended.` |
| 标题画面 | **PASS** | `06:35:29 Scenario loaded : title.ks`；截图 `step-02-title.png`（2,551,528 B sha256 87cb2857fac0…），菜单「はじめから／ロード／クイックロード／コンティニュー／コンフィグ／スペシャル／終了する」 |
| 资源挂载规模 | **PASS（到标题为止）** | Auto Path 三次重建 `Total 81 → 3,244 → 19,183 file(s) found, 19,171 activated`；14 个 xp3 逐个 `Trying to read XP3` |
| 视频解码（logo.mpg） | **部分** | FFmpeg 解出 `mpeg1video 1280x720 30fps` + `mp2 44100 Hz stereo`；`[swscaler] No accelerated colorspace conversion found from yuv420p to rgba`（软转）；是否肉眼可见播放未单独验证 |
| 音频 | **部分** | `Sound Driver/Device found : OpenAL Soft`、CPU boost 已生效（`[K2S] CPU boost: on (rc=0x0)`）；实际出声未验 |
| 存档 | **部分（位置已实证）** | `sdmc:/kirikiri/haruno/savedata/` 已由游戏创建，含 `krenvprf.kep`、`krkr.console.log`；写读回未验 |
| A2 首启解包 | **no-op（符合预期）** | `k2s_boot.txt` 出现 `5b galnx payload`（函数被调用并返回）；r1 NRO 的 romfs 仍是 DirNum 7 / FileNum 85、无 `game_files.txt`；`build/romfs` 只有 UI 资源 |
| 异常总数 | **0** | 本次日志无 `An exception occured` |

**输入语义硬约束（P2 首跑暴露，必须写进后续适配）**：键盘 C（Citron 映射到 A/确认）在标题菜单**零像素变化** —— `step-08-adv2.png` 与 `step-02-title.png` sha256 完全相同；`step-05-adv1.png` 与标题的差异仅 0.000057，bbox `(1566,978)-(1576,992)` 是 Citron 右下角帧率数字，不是游戏画面。源码根因：`src/core/environ/cocos2d/MainScene.cpp:2365-2395 onPadKeyDown` 在 `__SWITCH__` 下、无 UI 弹窗且虚拟鼠标激活时，A/B 不是「确认/取消」，而是 `_currentWindowLayer->onMouseClick(GameNode->convertToWorldSpace(_mouseCursor->getPosition()))`（A=左键、B=右键）；虚拟光标初始在 GameNode 中心（约 640,360，来自 `platform/switch/host/src/event.rs` 的 `HorizonInput::new()`），并不在底部菜单项上。光标只能由 `:2300-2330 onAxisEvent` 的左摇杆 `JOYSTICK_LEFT_X/Y` 移动（dead=0.15，`step = 12*v*|v| + sign`，clamp 到 GameNode）。

⇒ **结论（硬约束）**：在 Switch/K2NX 上，「A 键」等于「在虚拟光标处单击鼠标」，不是 KAG 的确认键；任何依赖「按键推进/确认」的验收（菜单选择、正文推进、存档界面）都必须通过 ①鼠标/触屏点击目标坐标，或 ②先把虚拟光标用左摇杆移到目标再按 A。纯键盘键位序列无法完成菜单选择。K2NX README 的「A=advance/confirm」只在有对话推进语义的场景近似成立，在 KAG 菜单/链接上是点击语义。

#### 2.13.6 A2 v2 补丁复核（2026-10-30 06:4x，Lead 已重建 r2）与 v1 致命 bug 登记

审查对象：`E:/galnx-build/pilot-01/patches/galnx_extract_v2.inc`（9,705 B / 266 行，LF）+ 应用脚本 `apply_extract_v2.py`；已应用进工作副本（`main.cpp` 内可见 `GalNX_MkParentDirs`、`statvfs`、`GalNX_BoostMode`、`bytes=` 解析）。r2 产物：NRO `E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.nro` **42,351,222 B / sha256 f6134790c56ddb97b6a50b0160f69a0ba3cbf97216c3b15661f86f7ef6bbb7e8**；ELF `K2NX-rebuilt-galnx-r2.elf` **113,874,760 B / sha256 4b4515837d0239ee2e7448dd5dbed65e8fdda72c37fb0bac0d0dd10ef849b882**。

**v1 的致命 bug（R13，v2 已修）**：v1 的 `GalNX_MkDirs(const std::string &native)` 循环条件 `for (i = 0; i <= native.size(); ++i) if (i == native.size() || native[i] == '/')`，在 `i == size` 时会对**完整路径**再 mkdir 一次；当传入的是文件路径（`GalNX_CopyFile` 里的 `GalNX_MkDirs(dst)`）时，会在 SD 卡上创建**与文件同名的目录**（如 `data.xp3/`），随后 `fopen(dst,"wb")` 必然 EISDIR 失败 → 首启解包全量失败、marker 永不写入、每次启动重试。该路径在 r1 的 no-op 场景下未触发（romfs 无清单），属于「一旦带上 payload 就会 100% 失败」的隐藏 killer，Lead 在 v2 已拆分为 `GalNX_MkDirs(目录)` 与 `GalNX_MkParentDirs(文件父目录)`。

**v2 复核结论：PASS**，逐项：

| v2 改动 | 复核结果 | 说明 |
| --- | --- | --- |
| MkDirs/MkParentDirs 拆分 | 正确 | `MkParentDirs` 取 `find_last_of('/')` 后只建父目录；`MkDirs` 在 `i == dir.size()` 时先判 `dir[i-1] == '/'`（尾斜杠跳过）、且循环条件 `i != dir.size() && dir[i] != '/'` 用短路避免越界读；对 `sdmc:/...` 前缀的 `i<=4` 跳过保留 |
| 空间预检（`bytes=` + statvfs） | 正确 | `GalNX_FreeBytes()` 用 `f_frsize ?: f_bsize × f_bavail`；statvfs 失败返回 -1 → 只 WARNING 跳过预检（安全降级）；不足 `declaredBytes + 256 MiB` 时打印 FAILED 并 **return 不写 marker** |
| CPU boost 包裹 | 正确 | `GalNX_BoostMode(true)` 在拷贝循环前、`GalNX_BoostMode(false)` 在循环后；`appletSetCpuBoostMode` 失败只 WARNING 不中断（`R_FAILED` 判断） |
| marker/autostart 前 MkDirs | 正确 | `GalNX_WriteAutostart` 内先 `GalNX_MkDirs("sdmc:/switch/kirikiroid2")`；`GalNX_WriteWholeFile` 内也调 `GalNX_MkParentDirs`（双保险） |
| marker 命中后校验 startup | 正确 | `alreadyDone && !startup.empty() && !GalNX_FileExists("sdmc:"+startup)` → 打印 `re-extracting` 并置 `alreadyDone=false` 重拷 |
| startup 为空告警 | 正确 | 解析后立刻 WARNING，随后仍可拷贝但不自动启动（回落到选择器） |
| fflush | 正确 | 每步进度、WARNING、autostart 写后均 fflush |
| 其余 | 正确 | 断点续传 `GalNX_FileHasSize` + failed!=0 不写 marker；1 MiB 静态缓冲；`<sys/statvfs.h>` 在 .inc 顶部以文件作用域 include（插入位置合法） |

**v2 可改进但非阻塞（供参考，不建议现在改）**：① `GalNX_MkDirs("sdmc:/...")` 在 `i=5` 会尝试 `mkdir("sdmc:")`（设备前缀，必然失败且被忽略，无副作用）；② 若历史上 v1 曾在某设备跑过 payload 并留下「与文件同名的目录」，v2 的 `fopen(dst,"wb")` 仍会失败——当前 v1 从未带 payload 运行过，无实际残留，可不处理；③ `GalNX_FileHasSize` 只比大小、不比内容（续传可能保留同尺寸坏文件），首启场景可接受。


#### 2.13.7 A1 自包含 NSP 首启实测（2026-10-30 06:53–06:58，只读复核 Lead / audit-package 的运行与 SD 证据）

**对象与运行方式**：NSP `K2NX-A1-selfcontained-010047410000b0b2.nsp`（TitleID `010047410000b0b2`，由 `scripts/citron_run.sh` 以 nsp 类型加载，staged 到 Citron 虚拟 SD 的 `switch/galnx-harness/`）。run 目录 `workspaces/citron-harness/runs/20261030-065340-K2NX-A1-selfcontained-010047410000b0b2`，steps 只有 `wait:90000` → `capture:t90` → `wait:90000` → `capture:t180`，**没有任何输入注入**。Citron 窗口标题 `citron Nightly | 0237a9b88 | Kirikiroid2-NX (64-bit) | 1.0.1 | NVIDIA`：末段 `1.0.1` 来自 NSP 内 NACP 的 DisplayVersion，可作为「NSP 运行」与「NRO 运行（标题无该段）」的区分标志。

**运行结果（harness `result.json`）**：`status=loaded`、`pid=35140`、`elapsed_s=38`、`killed=true`（`--keep` 保留窗口）；`boot_line` 原文 `BootGame: Booting game: 010047410000B0B2 | Kirikiroid2-NX (64-bit) | 1.0.1`；Citron 版本行 `citron Version: citron Development Build | main-0237a9b88`。

**E2（截图）**：`step-02-t90.png` 与 `step-04-t180.png` 均为 1,728x1,016、各 **2,551,781 B、sha256 均 `3fa32cd3f75b0b794cd24335e48fcdd8f24a93981c930c5a7bda939dd20ba9ca`**（逐字节相同；第三张 `step-06-t300.png` 同样 2,551,781 B / 同哈希 ⇒ 到 300 s 仍完全静止、无崩溃）。`window.png`（06:54 首次截图）显示的是游戏自身启动前的 CAUTION / 18 禁提示画面（1,101,196 B / sha256 `497b057da85370d00861e9f07169b39669464d006e459211091c53969d248d07`），数秒后自动前进到标题；另有 `window-steps-final.png` 2,551,775 B（标题，PNG 压缩差异导致哈希不同）。内容为游戏标题画面（晴のちきっと菜の花びより Logo + 菜单 はじめから / ロード / クイックロード / コンティニュー / コンフィグ / スペシャル / 終了する），Citron 状态栏 `Scale: 1x  Game: 60 FPS  Frame: 16.67 ms`。`window.png` 1,101,196 B / sha256 `497b057da85370d00861e9f07169b39669464d006e459211091c53969d248d07`。

**E1（`C:/Users/<user>/AppData/Roaming/citron/sdmc/switch/kirikiroid2/k2s_log.txt`：123 行、7,492 B、sha256 `0bb6f611f05d0105ef424cdf3f9a3dfd3f4322f0b1a77e9be524a8f3bb30b51c`）**，原文摘录（按文件顺序）：

~~~
Kirikiroid2-Switch log (build Oct 30 2026 06:42:14)
[GALNX] free space check ok: 27563 MiB free for a 2737 MiB payload
[GALNX] first boot: copying 22 payload file(s) to sdmc:/kirikiri/haruno
[GALNX] progress: 3/22 files, 538 MiB
[GALNX] progress: 4/22 files, 988 MiB
[GALNX] progress: 7/22 files, 1707 MiB
[GALNX] progress: 10/22 files, 1983 MiB
[GALNX] progress: 13/22 files, 2685 MiB
[GALNX] payload copy finished: 22 copied, 0 kept, 0 failed, 2737 MiB total
applicationDidFinishLaunching
GL_VERSION: OpenGL ES 3.2 Mesa 20.1.0-rc3
GL ext: VAO=yes mapbuffer=yes
[GALNX] autostarting game from /kirikiri/haruno/data.xp3
06:54:05 (info) Data path : file://./kirikiri/haruno/savedata/
06:54:05 (info) Loading csvParser.tpm
[GalNX] internal plugin loaded via .tpm alias: csvParser.tpm -> csvParser.dll
...（同型 5 条：extrans / fstat / layerExImage / windowEx）
[GalNX] no built-in module for game plugin: wumsadp.tpm
[GalNX] no built-in module for game plugin: wuvorbis.tpm
06:54:05 (info) Total physical memory : 2907701248
[K2S] NEON blend routines: on
[K2S] OpenCV threads: 1
[K2S] CPU boost: on (rc=0x0)
06:54:05 (info) Trying to read XP3 virtual file system information from : file://./kirikiri/haruno/data.xp3
06:54:05 (info) Done. (contains 37 file(s), 37 segment(s))
06:54:05 (info) Loading startup script : file://./kirikiri/haruno/data.xp3>startup.tjs
06:54:06 (info) Total 19152 file(s) found, 19140 file(s) activated. (249ms)
06:54:06 Detected CPU core(s): 3
06:54:06 Scenario loaded : startup.soc
06:54:06 Scenario loaded : userMacro.ks
06:54:06 Scenario loaded : eyecatch.ks
06:54:06 Scenario loaded : logo.ks
06:54:06 (info) Startup script ended.
06:54:08 (info) Sound Driver/Device found : OpenAL Soft
Input #0, mpeg, from 'logo.mpg':
  Duration: 00:00:03.50, start: 0.153122, bitrate: 4044 kb/s
    Stream #0:0: Video: mpeg1video, yuv420p(tv), 1280x720, 30 fps
    Stream #0:1: Audio: mp2, 44100 Hz, stereo, s16p, 192 kb/s
[swscaler @ 0x20d400ff0] No accelerated colorspace conversion found from yuv420p to rgba.
[K2S] slow tick 204 ms
[K2S]   AlphaBlend_d                   8194 us x2
06:54:43 Scenario loaded : title.ks
~~~

全文 123 行，逐行核对：**0 行 error / exception / warn**；无 `mainwindow.tjs(990)` 异常（对照 §2.11 的 E1 崩溃日志，patch C 生效后该异常消失）。

**E3（SD 实测：`sdmc:/kirikiri/haruno/`）**：解包后 14 个 xp3（2,869,566,751 B）+ `haruno.cf` 769 B + `plugin/` 7 个 tpm（1,066,496 B），合计 **2,870,634,016 B = 2,737.2 MiB**，与清单 `bytes=2870634016` 逐字节一致；22 个 payload 文件 = 14 xp3 + haruno.cf + 7 tpm，与日志 `22 copied, 0 kept, 0 failed` 一致。

| 文件 | 字节 | 文件 | 字节 |
| --- | ---: | --- | ---: |
| data.xp3 | 198,550 | media.xp3 | 110,513,170 |
| scenario.xp3 | 1,551,254 | movie.xp3 | 164,394,346 |
| image00.xp3 | 22,230,877 | voice01.xp3 | 17,431,512 |
| image01.xp3 | 542,381,164 | voice02.xp3 | 717,704,696 |
| image02.xp3 | 472,173,601 | voice02_2.xp3 | 53,192,145 |
| image02_2.xp3 | 74,766,214 | haruno.cf | 769 |
| image03.xp3 | 31,429,614 | plugin/csvParser.tpm | 86,016 |
| image04.xp3 | 646,837,304 | plugin/extrans.tpm | 237,568 |
| image06.xp3 | 14,762,304 | plugin/fstat.tpm | 128,000 |
| plugin/layerExImage.tpm | 126,976 | plugin/windowEx.tpm | 229,376 |
| plugin/wumsadp.tpm | 57,856 | plugin/wuvorbis.tpm | 200,704 |

- marker `sdmc:/switch/kirikiroid2/.galnx_extracted`：11 B、内容 `pilot01-r1` + 换行、sha256 `5a95de3a3d9b96a8861f1a22016f55f2d6065003eb5786b7aea9f96b759c728e`。
- `sdmc:/switch/kirikiroid2/autostart.txt`：26 B、内容 `/kirikiri/haruno/data.xp3` + 换行、sha256 `75b6df8004ab7c2831d6d6de844e124f173a8d10c2e2a58130c0cfda4377d966`。
- **解包耗时 ≈ 14 s**：文件 mtime 从 2026-10-29T22:53:52Z 到 22:54:06Z（本地 06:53:52–06:54:06），即 2.87 GB / 14 s ≈ **205 MB/s**（注意：Citron 的 sdmc 是宿主机磁盘目录，不代表真机 SD 卡速度）。
- `k2s_boot.txt`（234 B / sha256 `2d3ca872b99976c451bf34941d1f75eac00a6bf452180ed3a9524e9180c2696a`）逐行：`0 build Oct 30 2026 06:28:53` / `1 static-init start (image base 0x8000000, 305 init entries)` / `2 prioritized static-init done` / `3 main` / `4 logging ready` / `5 romfs ok` / `5b galnx payload` / `6 app delegate created, entering run()` ⇒ A2 在 romfs 挂载后、cocos run 前被调用并返回。

**首启解包链路逐项判定（对应 §2.13.6 的 v2 五项改进）**：

| 项 | 实测证据 | 判定 |
| --- | --- | --- |
| 空间预检（`bytes=` + statvfs） | `free space check ok: 27563 MiB free for a 2737 MiB payload` | **PASS**（v2 新增行被执行；阈值判断未触发，不足分支未验） |
| CPU boost 包裹 | 日志无 A2 的 boost WARNING；另有 `[K2S] CPU boost: on (rc=0x0)`（K2S 自己在启动后设的 boost，与 A2 的 FastLoad 不是同一行） | **未验证**（boost 生效与否无独立日志，归 U15） |
| 22 文件拷贝 + 进度 | `first boot: copying 22 payload file(s)`、`progress: 3/22 … 13/22`、`payload copy finished: 22 copied, 0 kept, 0 failed, 2737 MiB total` | **PASS** |
| marker / autostart 写入 | marker 内容 `pilot01-r1`、autostart 内容 `/kirikiri/haruno/data.xp3`，均在 SD 上读到 | **PASS** |
| marker 命中后校验 startup | 本轮为首次解包（marker 不存在），该分支未触发 | **未验证**（二次启动归 U15） |
| startup 为空告警 | 本轮 startup 非空，未触发 | 未验证 |
| A1 自动启动 | `[GALNX] autostarting game from /kirikiri/haruno/data.xp3` → `Data path : file://./kirikiri/haruno/savedata/` | **PASS**（P0 修复后 startup 指向 .xp3，savedata 落点正确） |
| patch C 插件别名 | 5× `internal plugin loaded via .tpm alias`；wumsadp/wuvorbis 打印 no built-in module（预期，走核心解码） | **PASS** |
| 多 xp3 自动挂载 | 14 个 xp3 `Trying to read XP3` → `Total 19152 file(s) found, 19140 file(s) activated` | **PASS** |
| 启动脚本链 | `startup.tjs` → `startup.soc` → `userMacro.ks` → `eyecatch.ks` → `logo.ks` → `Startup script ended.` → `Scenario loaded : title.ks` | **PASS**（到标题） |
| 内存预算 | `Total physical memory : 2907701248`（≈2.71 GiB）、`Detected CPU core(s): 3` | 记录（3 GB 级内容 + 软渲染在 Switch 侧的内存余量需真机复核） |

**标题菜单点击坐标定标（供后续复跑与 P2-a 用）**：对 1,728x1,016 的 Citron 截图做像素统计，16:9 游戏区精确落在 **x 112..1615（宽 1504）、y 117..962（高 846）**，缩放 **1.175**（1504/1280 = 846/720）；换算公式 `px = 112 + 1.175·X`、`py = 117 + 1.175·Y`（X,Y 为 K2NX 的 1280x720 游戏虚拟坐标）。标题菜单「はじめから」的虚拟矩形（`TitleObject.tjs` 的 `[TitleCreate]` 循环：x=180, y=675, w=114, h=27）→ 窗口像素 x 323..458 / y 910..942，**中心 ≈ (390, 925)**。此前 audit-web 用的 `click:380,905` 换算回虚拟坐标为 (228, 670.6)，y 比按钮上沿（675）高 4.4 px ⇒ **落空**；由此也可解释 06:40 那次 run 的 `steps_diff_ratio=0.795` 只是标题动画（云/光）造成的假阳性，不能作为「点击成功」判据——应以 `k2s_log` 出现 `Scenario loaded : start.ks` 为准。

**手柄操作路径（Citron 键盘映射实测配置，`C:/Users/<user>/AppData/Roaming/citron/config/qt-config.ini`）**：`player_0_lstick="engine:analog_from_button,modifier:…code$016777248…,left:…code$065…,up:…code$087…,right:…code$068…,down:…code$083…,modifier_scale:0.500000"` ⇒ **键盘 A(65)=左、W(87)=上、D(68)=右、S(83)=下 模拟左摇杆**（Shift 为半速 modifier）。K2NX 侧：左摇杆首次推动即 `showVirtualMouseCursor(true)` 并置 `_k2sStickCursor`，之后按 `step = 12·v·|v| + sign`（满杆 13 px/次，dead=0.15）移动虚拟光标并转发 `onMouseMove`；`onPadKeyDown` 在无 UI 子节点时把 **A = 虚拟光标处左键单击、B = 右键单击**，D-pad 不移动光标（见 §2.13.5）。⇒ 「手柄操作」在源码层可行，但需要**左摇杆把光标移到菜单矩形内再按 A**；键盘模拟摇杆可作为 Citron 上的注入通道，真机验证归 P4。

**结论**：A1 自包含 NSP 在 Citron 上完成「加载 → 首启空间预检 → 22 文件 / 2,737 MiB 解包（≈14 s）→ 写 marker + autostart → A1 自动启动 → 5 插件别名激活 → 14 xp3 挂载 → 启动脚本链 → 标题画面 60 FPS」全链路，**P3 的「已打包 NSP + 直接启动」已在模拟器上成立**；剩余缺口是「菜单点击/手柄推进」注入通道（U14）与真机验证（P4）。

#### 2.13.8 手柄按键链路根因（pad → VK_PAD*）与零重建修复（keymap XML，2026-10-30 07:2x）

**现象（E1/E2）**：Lead 的 RUN A（click:390,925 / 864,520）与 RUN B（key:A×31 + key:S×26 + key:C）在 k2s_log 里都停在 `Scenario loaded : title.ks`，无 start.ks、无异常；像素 diff 0.57 级（标题相机动画）是假阳性。A=31 次/S=26 次是键盘模拟左摇杆的注入（Citron `player_0_lstick` 的 analog_from_button 映射），C=67 在 Citron 里映射到 pad A（`player_0_button_a=67`）。

**根因（E4，四步链）**：

1. K2NX 把 pad 按键转成 VK_PAD*，不是游戏认识的 VK_*：`src/core/environ/cocos2d/CCKeyCodeConv.cpp:191-216 TVPConvertPadKeyCodeToVKCode()`（A=VK_PAD1、B=VK_PAD2、X=VK_PAD4、D-pad=VK_PADLEFT/UP/RIGHT/DOWN），数值见 `src/core/visual/tvpinputdefs.h:74-91`（VK_PADLEFT=0x1B5=437 … VK_PAD1=0x1C0=448）。
2. pad 路径在 `src/core/environ/cocos2d/MainScene.cpp:2365-2395 onPadKeyDown` / `:2397-2406 onPadKeyUp`：`unsigned int code = TVPConvertPadKeyCodeToVKCode(keyCode); if (!code || code >= 0x200) return; code = _keymap[code];` 然后 `_currentWindowLayer->InternalKeyDown/OnKeyUp(...)`。
3. 游戏脚本只处理真实 VK：`MainWindow.tjs:1400-1452 onKeyUp` 分派 VK_ESCAPE(:1411)/VK_SPACE(:1422)/VK_RETURN(:1429→`ActiveObj.KeyUpAction`)/VK_UP|DOWN|LEFT|RIGHT(:1445-1452)；在提取出的 data/ 目录 grep `VK_PAD` 零命中 ⇒ 默认情况下 A/B/D-pad 不触发任何游戏动作。
4. 因此游戏内「手柄可玩」目前只有一条路径：左摇杆推动 → `showVirtualMouseCursor(true)` + `_k2sStickCursor` → A/B 变成「虚拟光标处左键/右键点击」；按键（A/B/D-pad）本身完全无效。RUN B 里 A×31/S×26 移动了虚拟光标但 C（=pad A）的点击落在画布中心，未命中标题菜单矩形，故零变化。

**修复（零重建，已落地）**：keymap 注入点是「每游戏偏好文件」，因为 `MainScene.cpp:1749-1757` 用 `IndividualConfigManager::GetKeyMap()` 填 `_keymap[物理VK] = _keymap[目标VK]`，而 `IndividualConfigManager.cpp:49-58 UsePreferenceAt(folder)` 读的是 `<folder>/Kirikiroid2Preference.xml`（`folder = PathSplit(startup).first` = `/kirikiri/haruno`），`GlobalConfigManager.cpp:69-76` 解析 `<KeyMap key="int" value="int"/>`。

- 文件：`C:/Users/<user>/AppData/Roaming/citron/sdmc/kirikiri/haruno/Kirikiroid2Preference.xml`（1,293 B，sha256 `aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543`；归档副本 `E:/galnx-build/pilot-01/patches/keymap/Kirikiroid2Preference.xml`）。
- 内容：`<GlobalPreference>` + `<KeyMap key="448" value="13"/>`（A→VK_RETURN）、449→27（B→ESC）、451→32（X→SPACE）、437/438/439/440→37/38/39/40（D-pad→方向键）。
- 语义：Map 的 key=物理 VK（VK_PAD*）、value=目标 VK；`_keymap` 是 `static tjs_uint16 _keymap[0x200]`（`MainScene.cpp:64`），448 在界内。

**标题菜单的确定性按键序列（源码推导，供下一次 run 用）**：

- 初始 `MapReg=0`、`keyactive` 未设（`TitleObject.tjs:481-483`），TitleLoop 在 `!keyactive` 时用鼠标 province 像素更新 MapReg（`:604`），鼠标不动则保持 0；`CodeWork`（即 `ClickWork`）第一句是 `if(MapReg <= 0) return;`（`:850`）⇒ **首个 RETURN 只会画按下态、不会开始游戏**。
- 先按一次 **D-pad RIGHT**：`TitleObject.tjs:1199-1243 KeyUpAction(VK_RIGHT)` → `keyactive=true`、`++MapReg=1`（跳过不可用项的 switch 只处理 MapReg==2..8/11，1 不受影响）⇒ MapReg=1 =「はじめから」。
- 再按 **A（keymap 后=RETURN）**：`MainWindow.tjs:1429-1443` → `ActiveObj.KeyUpAction(VK_RETURN)` → `TitleObject.tjs:1148-1153 LeftMouseUpAction()` → `ClickWork`（:853 case1 画按下态）→ TitleLoop 发现 `ButtonLayer[i].PaintFlag` → `ButtonWork`（:916-935 case1：`f.changefile=1`、停 DefaultTimer、`ContinueFlag=true`、`DeleteWork(TitleDelete)`）→ 进入开局。
- ⚠ 不要用 LEFT 从 0 开始：`--MapReg` = -1 → `<1` 归 8 →（未通关时）落到 7，而 **MapReg=7 是「終了する」**（`ClickWork` :881 case7/end）⇒ 会退出游戏。这是本作标题菜单的一个陷阱。
- 对应 harness 步骤（title.ks 实测约启动后 40–60 s 才加载）：`wait:75000;capture:title;key:RIGHT;wait:1500;capture:menu;key:C;wait:8000;capture:started`；判据用 k2s_log 出现 `Scenario loaded : start.ks`（或非 title.ks 的场景）且无 exception，不要用像素 diff。

**判定**：本条把 U5/U14 的「手柄不可用」从「注入通道未定」收窄为「明确的引擎默认行为缺陷 + 已给出零重建修复与可执行测试序列」；修复本身**尚未实测**（Citron 本轮归 Lead），列为 U17。

#### 2.13.9 P2 关键达成：自包含 NSP + 手柄按键进入正文（RUN G 实测，2026-10-30 07:26–07:29）

**结论（E1+E2+E3）**：在三处补丁（A1 自动启动、A2 首启解包、C 插件别名）+ 预置 keymap XML 的条件下，**A1 自包含 NSP 在 Citron 上走通「直接启动 → 首启解包 → 自动启动 → 标题菜单（D-pad RIGHT）→ A（keymap→VK_RETURN）确认 → 进入 start.ks 正文 → 再 A 推进一页」的全链路，0 exception**。这是第一款试点「已打包 NSP、可直接启动、支持手柄操作」在模拟器侧的首次端到端达成（**真机仍未验**）。

**运行对象**

- 形态：A1 自包含 NSP `E:/galnx-build/pilot-01/out/K2NX-A1-selfcontained-010047410000b0b2.nsp`（romfs 含 2.67 GiB payload + game_files.txt，version=pilot01-r1）。
- 追加输入：`sdmc:/kirikiri/haruno/Kirikiroid2Preference.xml`（1,293 B，sha256 `aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543`，即 §2.13.8 的 keymap）。
- run 目录：`E:/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/citron-harness/runs/20261030-072607-K2NX-A1-selfcontained-010047410000b0b2`；pid 2772、elapsed_s 32、killed=true、`status=loaded`；窗口标题 `citron Nightly | 0237a9b88 | Kirikiroid2-NX (64-bit) | 1.0.1 | NVIDIA`（`1.0.1` = NSP DisplayVersion，与 NRO 运行形态可区分）。

**输入步骤（11/11 全部 ok）**：`wait:75000` → `capture:title` → `key:RIGHT` → `wait:2000` → `capture:menu` → `key:C` → `wait:10000` → `capture:started` → `key:C` → `wait:6000` → `capture:adv1`。键盘 Right(=16777236) 在 Citron 映射为 D-pad right；C(=67) 映射为 pad A（qt-config `player_0_button_a=67`），经 keymap 变 VK_RETURN。

**E3 证据文件（我实测 size/sha256）**

| 文件 | 字节 | sha256 | 内容 / 判据 |
| --- | --- | --- | --- |
| result.json | 4,314 | `da228445c00846d2f823bfad8ecac1259517eee456c58fb2ffa9078b9b6f6713` | status=loaded、pid=2772、elapsed_s=32、steps 11/11 ok、killed=true |
| run.log | 1,967 | `54095157…`（见 run 目录） | harness 注入与截图记录 |
| step-02-title.png | 2,377,784 | `884786a6ef6aa33a626fb52bc24d98c30289ef6bc35c1a154657e9b726c83994` | 标题菜单 |
| step-05-menu.png | 2,377,402 | `7978d2a5…` | 按 RIGHT 后（菜单高亮移动） |
| **step-08-started.png** | 882,522 | `a5ceed1c97314f6af201cd6716e1ba4eb34e328b7e1ff953d95018caec908bf3` | **已离开标题进入故事（画面与菜单形态完全不同）** |
| **step-11-adv1.png** | 921,899 | `4ea7b8e71431c55154bccf511efc9f2143c16fa2d93e8522859b01c1bca3d537` | **正文第一页：少女立绘 + 台词「どこの誰だかもわからない、目の前にいる逆光の中の"彼女"に向けて……」+ 标题 logo 水印；Citron 状态 60 FPS / 16.66 ms** |
| window-steps-final.png | 922,819 | `d1e5b0dd…` | 结束时窗口画面 |

**E1 日志时间线（k2s_log 副本：`docs/milestones/evidence/P2b-runG-k2s_log.txt`，7,646 B / 126 行；另一副本 `E:/galnx-build/pilot-01/p2-evidence/runG-k2s_log.txt`）**

~~~text
[GALNX] payload pilot01-r1 already extracted, starting game      <- 二次启动、marker 命中（U15 的一项实测）
[GALNX] autostarting game from /kirikiri/haruno/data.xp3
<5x> [GalNX] internal plugin loaded via .tpm alias: <p>.tpm -> <p>.dll   <- patch C：csvParser/extrans/fstat/layerExImage/windowEx
[GalNX] no built-in module for game plugin: wumsadp.tpm / wuvorbis.tpm
(info) Total 19153 file(s) found, 19141 file(s) activated.
(info) Scenario loaded : title.ks
(info) Scenario loaded : start.ks            <- 07:28:14 进入开局
(info) Scenario loaded : @0000A_Z01.ks      <- 07:28:18 第一章脚本
~~~

0 条 error / exception（该副本中 `grep -c "exception|error"` = 0）。

**判定（按 U 编号回填）**

- U5 手柄可玩性：**P2-2 达成前半**——D-pad RIGHT + A 可从标题确定性开始游戏，A 再按推进一页（场景文件从 title.ks → start.ks → @0000A_Z01.ks 连续切换，是 E1 级判据，不依赖像素 diff）。仍未验：B 菜单、D-pad 上下选项/历史、存档界面操作。
- U7 深层场景：进入 start.ks 与第一章脚本，读取 14 个 xp3 的深层资源成功；更远剧情未验。
- U15 二次启动 marker：`already extracted, starting game` 实测 PASS（keep existing 分支）。
- U17 keymap 修复：**实测 PASS**（预测的「D-pad RIGHT 一次 → A」序列一次命中）。
- per-game 偏好：**引擎不会覆写**——RUN G 结束后 `Kirikiroid2Preference.xml` mtime 仍为写入时刻（07:22）、大小 1293 B 未变；写入口仅 `GlobalConfigManager::SaveToFile()`（写 Global 路径）与 `IndividualPreferenceForm` 的用户显式保存（§2.13.8 已给代码位置）。⇒ 该 XML 可安全预置；自包含分发仍需 A2 固定写或进 payload。

**「NSP 形态鼠标点不动 vs NRO 能点」— 已证伪（E1+E4）**

- 对照 RUN C/E/F（同一 A1 NSP，click 分别 390,925 / 350,920 / 380,905、wait 80000）全部停在 title.ks；但 Lead 提到的「NRO r1 + click:380,905 成功」在 run 目录 `runs/20261030-064039-K2NX-rebuilt-galnx-r1` 里并不成立：该 run 的 `step-07-story1.png` 视觉上仍是标题菜单，0.79 的 diff 来自标题相机动画（假阳性）。
- `docs/milestones/evidence/P2a-k2s_log.txt` 时间线：06:40:47 autostart → 06:41:25 title.ks → **06:50:17 start.ks**；该 run 的 click 发生在 wait:5000 之后（早于 title.ks 约 8 秒），之后约 9 分钟无任何 harness 输入 ⇒ 那次 start.ks 只能来自人工鼠标或其它外部注入，不能作为「click 在 NRO 形态可行」的证据。
- 源码层同样无形态分支：Citron `src/citron/bootmanager.cpp:571-595 mousePressEvent` → `src/core/frontend/emu_window.cpp:18-42 MapToTouchScreen`（裁剪+归一化）→ `Mouse::PressTouchButton`，与 NRO/NSP 无关；K2NX `MainScene.cpp:2123 onTouchBegan` 在 `_virutalMouseMode=false`（`MainScene.cpp:58` 默认）时走 `:588-608 onTouchEnded` 的绝对坐标 Post 序列。
- **真正的差别在 harness 注入通道**：键盘走 `PostMessage(WM_KEYDOWN/WM_KEYUP)`（`scripts/citron_run.sh:682-684`，与焦点无关——RUN G 的 `input.focus_ok=false` 仍然生效）；点击走 `SetCursorPos` + `mouse_event`（`scripts/citron_run.sh:660-666`，真实输入，要求光标下是最顶层窗口；harness 提权 shell、Citron `runas-deelevated`，且 `focus_ok` 只在 SetForegroundWindow 后立即比对 `:673`，不能反映 120 ms 后的实际状态）。
- ⇒ 结论：**自动化交互一律走键盘（keymap = 真实手柄路径），不要把 mouse_event 点击的成败当判据**；真机触摸屏直通（`!_touchMoved` 分支）仍未验。

**本轮独立复跑作废说明（诚实记录）**：我 07:31:27 启动的 RUN H 目录 `runs/20261030-073127-K2NX-A1-selfcontained-010047410000b0b2` 只有 0 字节 run.log、无 result.json/截图——原因是我启动的同时 Lead 正在做 A2「全新 SD」验收并 `rm -rf sdmc:/kirikiri` + marker/autostart，harness 轮询的 boot 证据被清空导致卡到超时；该 run 记为**作废（0 步完成）**，不构成证据。随后按 Lead 的申请-释放协议，我 07:40 释放 Citron，独立复跑改到 A2 验收之后进行（U18）。

#### 2.13.10 A2 自包含 NSP「全新 SD 首启解包」验收（Lead 执行，E1/E3 只读取证，2026-10-30 07:35–07:43）

**结论**：A2 v2（清单驱动 + `bytes=` 空间预检 + FastLoad boost + marker）在**清空 SD 后全新首启**场景下**一次通过**：23 个 payload 文件（含 keymap XML）共 2,737 MiB 全部解包到 `sdmc:/kirikiri/haruno/`，写 marker `pilot01-r2` 与 autostart，随后自动启动到标题；`start.ks` / `@0000A_Z01.ks` 也在本轮出现（输入归因见末尾）。全程 0 error/exception。

**运行对象**

- 包：`E:/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b4.nsp`（2,906,125,016 B，sha256 `eb6c6a15151c2a5936c6549eebb26ca25a059744f0136cb5b8cce773fd9c705f`；romfs-a2、payload 23 文件、version=pilot01-r2）。
- run 目录：`E:/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/citron-harness/runs/20261030-073555-Kirikiroid2-NX-010047410000b0b4`（`game type : nsp`、citron pid 38316、`--keep`）。
- 前置：Lead 在 07:35:20 左右 `rm -rf sdmc:/kirikiri` + marker/autostart，确保是全新首启（日志中 `first boot: copying ...` 而非 `already extracted` 亦印证）。

**E1 日志摘录**（`sdmc/switch/kirikiroid2/k2s_log.txt`；我 07:43 只读快照 7,995 B，sha256 `c0eb1c4062115b84995362b98f2269e3da27efbb3f69d80084a0e661b85bdfe4`，临时副本 `E:/galnx-build/pilot-01/p2-evidence/a2-run-k2s_log.txt`）

~~~text
Kirikiroid2-Switch log (build Oct 30 2026 06:42:14)
[GALNX] free space check ok: 28196 MiB free for a 2737 MiB payload
[GALNX] first boot: copying 23 payload file(s) to sdmc:/kirikiri/haruno
[GALNX] progress: 3/23 files, 538 MiB
[GALNX] progress: 4/23 files, 988 MiB
[GALNX] progress: 7/23 files, 1707 MiB
[GALNX] progress: 10/23 files, 1983 MiB
[GALNX] progress: 13/23 files, 2685 MiB
[GALNX] payload copy finished: 23 copied, 0 kept, 0 failed, 2737 MiB total
applicationDidFinishLaunching
[GALNX] autostarting game from /kirikiri/haruno/data.xp3
07:40:09 (info) Data path : file://./kirikiri/haruno/savedata/
07:40:11 Scenario loaded : startup.soc / eyecatch.ks / logo.ks
07:40:47 Scenario loaded : title.ks
07:42:36 Scenario loaded : start.ks
07:42:40 Scenario loaded : @0000A_Z01.ks
~~~

全 133 行检索 error/exception = **0 行**；5× `internal plugin loaded via .tpm alias` 与 `no built-in module` wumsadp/wuvorbis 与本轮一致（patch C 稳定）。

**E3 落地核对（stat mtime，UTC+8）**

- 首个落地文件 `data.xp3` 07:39:56.147 → 末个 `Kirikiroid2Preference.xml` 07:40:10.574 ⇒ **23 文件 / 2,737 MiB 解包总耗时 ≈14.4 s（≈190 MB/s，Citron 虚拟 SD）**。
- 落地文件集合与清单 `bytes=2,870,634,016` 一致（14 个 xp3 + haruno.cf + plugin/ 7 个 + keymap XML）。
- `Kirikiroid2Preference.xml`（1,293 B，sha256 `aa4fa8ab…`）mtime 07:40:10、晚于解包开始 ⇒ **keymap 确实从 payload 解包出来**，「keymap 随自包含 NSP 分发」这条从设计变为实测（U18 关键项）。
- marker `sdmc:/switch/kirikiroid2/.galnx_extracted` 内容 `pilot01-r2`；`autostart.txt` 内容 `/kirikiri/haruno/data.xp3`（均 07:40 写入）。

**输入注入方式（Lead 确认：不是 harness 跑完的）**：`scripts/citron_run.sh` 在该多步 run 上异常早退（见 R14：07:39:33 启动、07:40:17 退出 exit 0，但无 result.json/截图/JSON，run.log 只到 `stage path`，Citron 进程仍活着），实际输入由 Lead 用 run 目录里的 `citron_win.ps1 -Mode input -Hwnd <hwnd> -Vks 39,67` 通过 **PostMessage** 在标题画面上发 RIGHT+C，随后 C/C 翻页；A 键无独立作用（设计使然）、B 本轮无可见变化（记为 U，不作结论）。⇒ 「键盘 PostMessage 是可靠的自动化/手柄按键通道」在 A2 形态再次复验（与 §2.13.9 的 E4 结论一致）。

**Lead 提供的 E2/E3 证据（原文摘录）**

| 对象 | 值 |
| --- | --- |
| `p2c-live-now.png`（title 前 live 窗口） | sha256 `45b24203…` |
| `p2c-started.png`（进入正文） | sha256 `b0c095e4…`，首句「懸命に手を伸ばした。」 |
| `p2c-adv1.png` / `p2c-adv2.png` | `d55235cf…` / `a281a23b…` |
| `p2c-menuB.png`（按 B 后） | `9051cfc5…`（无可见变化，记 U） |
| `p2c-k2s_log.txt` | sha256 `c0eb1c40…` —— **与我 07:43 只读快照完全一致**（互为独立副本校验） |
| `p2c-k2s_boot.txt` | sha256 `2d3ca872…`（与 RUN G 同值） |

**keymap 来源证据链（排除「旧 SD 残留」）**：payload 内 `romfs-a2/game/Kirikiroid2Preference.xml` 的 sha256 = `aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543`（1,293 B）= 解包后 `sdmc:/kirikiri/haruno/Kirikiroid2Preference.xml` 的 sha256；而 Lead 在 07:39:33 已 `rm -rf sdmc:/kirikiri` 删除旧数据 ⇒ **该 XML 确实由 NSP 自带并解包产生**。

**A2 验收本身只需「解包 + marker/autostart + 到 title.ks」这三项，已由 E1/E3 独立证成**；`start.ks`/`@0000A_Z01.ks` 由 Lead 的 PostMessage 输入触发，属 P2 手柄路径的补充实证（U5/U17）。

**与 A1（RUN G，§2.13.9）对比**：A1 = 22 文件 / 2,737 MiB / ≈14 s（首启）；A2 = 23 文件（+keymap XML）/ 2,737 MiB / ≈14.4 s，行为一致且多分发一个文件；二启 `already extracted` 分支在 A1 形态已实测（RUN G），A2 形态的二次启动仍待补证（U18 剩余项）。

---

#### 2.13.11 A2 独立复跑（audit-engines：R1 全新 SD 首启 + R2 二启 marker，2026-10-30 07:55–08:02）

**目的与协议**：对 §2.13.10 的 Lead 单方验收做独立复验——不同 run 目录、独立清场、独立驱动脚本。Lead 于 07:53 释放 Citron 后接手，08:01:43 释放；全程不 commit、不构建、不碰 keys。被验收物 A2 NSP `Kirikiroid2-NX-010047410000b0b4.nsp` 2,906,125,016 B sha256 `eb6c6a15…`。

**R1（run `20261030-075524-Kirikiroid2-NX-010047410000b0b4`，RC=0，23:55:16Z–23:58:49Z）**：清场前快照 sdmc/kirikiri 23 文件 2,870,635,309 B、marker `pilot01-r2`、autostart 均存在（`P2e-r1-prewipe.txt` `c7a8e96a…`）→ 删除三处。输入序列与 §4.5/Lead 完全相同（`wait:120000;capture:title;key:RIGHT;wait:2500;key:C;wait:15000;capture:started;key:C;wait:5000;capture:adv1`；`--timeout 300 --settle 25 --input-delay 3000 --input-gap 250`，32 s 完成未触超时）；result.json `bd149a3a…`（loaded、10/10 步 ok、steps_diff_ratio=0.809225）。k2s 关键行：`[GALNX] free space check ok: 28196 MiB free for a 2737 MiB payload` → `[GALNX] first boot: copying 23 payload file(s)` → `[GALNX] payload copy finished: 23 copied, 0 kept, 0 failed, 2737 MiB total` → `[GALNX] autostarting game from /kirikiri/haruno/data.xp3`；`Scenario loaded : title.ks` 07:56:26 → RIGHT+C → `start.ks` 07:58:13 → `@0000A_Z01.ks` 07:58:16（k2s sha256 `dde7eba6…`，133 行）。解包净耗时：SD 文件 mtime 窗口 07:55:35.256→07:55:48.476 = **13.22 s**；解包后 23 文件、2,870,635,309 B（与 wipe 前一致）；launch→title ≈62 s。落地物 marker `5109bb58…`、autostart `75b6df80…`、keymap XML 1,293 B `aa4fa8aa…`。截图：title `5b001042…`（2,377,811 B）、started `d10f50b0…`（882,695 B，正文「懸命に手を伸ばした。」）、adv1 `7d0e9436…`（924,381 B，下一句「どこの誰だかもわからない…」⇒ C 推进/翻页生效）。

**R2（run `20261030-075931-Kirikiroid2-NX-010047410000b0b4`，RC=0，23:59:30Z–00:01:43Z）**：不清 SD 二启（`wait:80000;capture:second-title`；2/2 步 ok、steps_diff_ratio=0.822459）；k2s 首行 `[GALNX] payload pilot01-r2 already extracted, starting game` → autostarting → `title.ks` 08:00:19（launch 07:59:31→title 48 s，**无解包段**，k2s sha256 `5ec17d1d…`，116 行）；R2 后 marker/autostart/keymap sha 全部不变（poststate `b32a239a…`）。

**与 Lead 证据交叉校验**：一致项 ①解包后 SD 23 文件 2,870,635,309 B 与 Lead 07:39 解包后字节级一致；②k2s 行数一致（R1 133 vs Lead run3 133，逐行仅时间戳与一处 `(5ms)/(4ms)` 计时差；R2 116 vs Lead 二启 116，逐行仅时间戳）；③marker/autostart/keymap 哈希与 Lead 记录相同；④title.ks→start.ks→@0000A_Z01.ks 时序与 C 推进一致；⑤起跑 SD 同源——我的 R1 前 k2s 旧内容 sha256 `b097234b…`（7,143 B）与 Lead 二启快照 `b097234b…` 完全相同。差异项——截图 sha256 跨进程不同（title `5b001042…` vs `06f4d1b8…`、started `d10f50b0…` vs `243de31c…`、adv1 `7d0e9436…` vs `6603d6f9…`、R2 title `884786a6…` vs `06f4d1b8…`），但像素差极小（title MAD 0.0043 / changed 0.0059% / maxdiff 134；started MAD 0.0200 / 0.0489%，bbox 1404,913–1575,991 共 858 px；adv1 MAD 0.0139 / 0.0390%；R2 title MAD 0.0046 / 0.0063%）；目视裁剪 `P2e-crop-started-diff.png` 确认差异仅右下角游戏 UI 图标动画状态（水滴 vs 水滴框）与 Citron OSD `Frame: 16.66/16.67 ms` 数字 ⇒ **渲染内容一致，截图 sha 只保证同一 Citron 进程内逐字节可复现**（已写入 P2-acceptance §6 L10）。

**结论**：A2 自包含 NSP 的「全新 SD 首启解包 → autostart → title.ks → 手柄 RIGHT+C → start.ks/@0000A_Z01.ks → C 推进」与「二启 marker 命中、无重复解包」两条链路独立复现 **PASS**，与 Lead 证据无实质不一致、无阻塞项。证据：`docs/milestones/evidence/P2e-*`（22 文件，全量 sha256 与对照表 `P2e-artifacts-sha256.txt`）；驱动脚本 `P2e-r1-driver.sh` / `P2e-r2-driver.sh`；原始备份 `E:/galnx-build/pilot-01/review/a2-indep/`；Citron 释放 08:01:43（0 实例复查）。**方法注记**：R14 早退的规避方式是在单次 run_code 内同步 spawnSync 跑完 harness（DSH 会在 run_code 退出时杀掉其整棵进程树，node spawn(detached) 不足以规避）。


---

## §3 三条 NSP 化路径对比

### 3.1 对比表

| 维度 | A：重建 K2NX + ROMFS 首启解包 | B：预编译 NRO→NSP + 数据外置 | C：改用 krkrsdl2 |
| --- | --- | --- | --- |
| 是否满足「NSP 自包含」 | **是**（游戏数据进 ROMFS） | 否（数据仍在 SD） | 否（需另做 ROMFS 改造 + 数据迁移） |
| 是否满足「直接启动」 | **是**（A1 补丁跳过选择器） | 否（仍要点 data.xp3；除非再做二进制补丁，风险高） | 需自研启动参数/配置（krkrsdl2 无 K2 选择器，反而更接近直接启动，但兼容性未证） |
| 是否满足「手柄操作」 | 是（已有 K2S 实现，2.9） | 是（同一 NRO 行为） | 未验证（krkrsdl2 的 Switch 输入映射未在本游戏验证） |
| 引擎改动量 | 3 处补丁（A1 约 40 行、A2 约 80 行、patch C 约 20 行，见 §5 与 §2.11） | 0 | 大：需从 K2NX 移植 csvParser/extrans/fstat/layerExImage/windowEx 等插件，并重建 xp3 多包自动路径机制 |
| 构建前提 | K2NX 全量工具链（§6）：devkitPro + switch-portlibs 组 + 7 个自建 portlibs + cocos2d-x 3.11.1 + APK 1.3.9 UI 资源 | 无需构建（直接包装 release NRO）；但需 NRO→ELF 转换工具链且**未实测** | M1 已打通本机构建（krkrsdl2 上游 CMake + devkitPro），但 krkrsdl2 的 K2 插件覆盖缺失（src/plugins 只有 kremscripten.cpp，无 csvParser/fstat/layerExImage/windowEx 实现） |
| 主要风险 | 首次打通构建链的时间成本；解包首启 1–3 分钟黑屏体验；插件别名缺陷已定位并已有最小补丁（§2.11），构建验证待 Lead | 不满足验收标准；NRO→NSP 结构转换（NRO 非 PFS0，需转 ELF/NSO）未经实测，失败即废路 | 工作量以周计；插件/脚本兼容性未知；等于换引擎重做兼容层 |
| 预计耗时 | P2-1 验证 0.5–1 天（构建打通后）+ P2-2 解包 0.5 天 + P3 打包 0.5 天 | 1–2 天（且只作演示） | 数周 |
| 结论 | **推荐（主方案）** | 仅作快速演示/回退（满足「能跑」但不满足「自包含+直启」） | 仅当 A 被证伪时启动 |

### 3.2 路径 B 补充说明（为什么不做主方案）

- NRO 是 NRO0 头 + 段 + ASET（icon/NACP/ROMFS），**不是 PFS0**；要装进 NSP 必须先还原成 ELF（或直接构造 NSO），再走 elf2nso → npdmtool → hacBrewPack（docs/builds/005 结论）。仓库/本机当前只有 elf2nro 与 elf2nso，没有 nro→elf 官方工具；Lead 工作区有自研 nro2elf.py（E:/galnx-build/pilot-01/nro2elf.py），但**本审计未验证其能否还原可链接 ELF**。
- 即使转换成功，B 路径也只能解决「NSP 外壳」，数据仍在 SD 且启动仍需点选择器 ⇒ 不满足用户验收标准。
- 反过来说，A 路径产出的 ELF 是**直接可用**的 NSP 输入（elf2nso 走 005 已验证链路），比 B 更干净。

### 3.3 路径 C 补充说明（为什么暂不选）

- krkrsdl2（/e/galnx-build/m1-krkrsdl2，KiriKiri Z SDL2 移植）已在 M1 打通 Switch 构建与 ROMFS 数据读取，且有 MIT/上游官方 Switch 支持（见 06-engines-refresh.md）；但它的插件目录 src/plugins/ 只有 istream_compat.h、kremscripten.cpp、tp_stub.h，**没有 K2 时代插件实现**；试点游戏脚本明确使用 CSVParser 与 Storages.fstat，若用 krkrsdl2 需要把 K2NX 的对应插件（以及 K2 的 fstat 语义）移植过去，属数周量级。
- 另一个未知：试点游戏是 KiriKiri2（TVP 2.x 时代），而 krkrsdl2 目标是 KiriKiri Z（TVP 3.x）；TJS2 语法与部分 syscall 兼容，但 UI/插件/存档格式差异需逐个验证。故 C 仅作 A 失败时的备选。

## §4 A 路径实施设计

### 4.1 目标形态与启动时序

目标 NSP 的结构（沿用 K2NX 现有 CMake 的 nx_create_nro 参数，见 platforms/switch/CMakeLists.txt）：

- ROMFS 内容 = 现有 UI 资源（res/、default.cur、字体等，来自 APK 1.3.9 的 extract_apk_assets.sh）+ 新增 game/haruno/ 目录（完整游戏目录：data.xp3、14 个 xp3、plugin/、default.ttf 等）。
- NACP / icon / TitleID 由打包步骤决定（P3 用 docs/builds/005 的 elf2nso → npdmtool → nacptool → hacBrewPack 链路；TitleID 按 GalNX 分配规则）。

启动时序（A1 + A2 都打开之后）：

1. main()：socketInitializeDefault() → setupLogging()（日志落 sdmc:/switch/kirikiroid2/k2s_log.txt）→ romfsInit()。
2. [A2] 若 sdmc:/switch/kirikiroid2/.game_extracted 不存在：递归复制 romfs:/game/haruno → sdmc:/kirikiroid/haruno，写 startup.txt（内容 /kirikiroid/haruno/data.xp3）与 marker；失败则删临时 marker 并继续（后续 A1 会回退到文件选择器，不会黑屏死锁）。
3. TVPAppDelegate app; cocos run()；AppDelegate 创建 scene 后 scheduleOnce 回调（AppDelegate.cpp:96-102）里调用 TVPCheckStartupArg()。
4. [A1] TVPCheckStartupArg() 读 sdmc:/switch/kirikiroid2/startup.txt，得到 /kirikiroid/haruno/data.xp3 → 调 TVPMainScene::GetInstance()->startupFrom(path) → 返回 true 跳过文件选择器。
5. startupFrom 内部：TVPCheckStartupPath（恒 true）→ UsePreferenceAt(游戏目录) → popUIForm → scheduleOnce(doStartup) → ::Application->StartApplication(path) → 引擎初始化 + TVPLoadPluigins()（patch C 让 5 个内建插件激活）→ 游戏脚本启动 → MainWindow 构造（windowEx 方法存在）。
6. 二次启动：marker 已在 → 跳过解包（第 2 步秒过）→ 直接第 3 步起，等效于「NSP 自包含 + 直接启动」。

时序上的一个硬约束：**A1 不能提前到 main()**。startupFrom 依赖 cocos 的 scene/调度器（scheduleOnce），而 scene 在 applicationDidFinishLaunching 里才创建；因此必须挂在 AppDelegate 的 launch lambda 上（原代码正是留了这个钩子）。

### 4.2 分阶段验收（每阶段都可独立回退）

| 阶段 | 改动 | 游戏数据位置 | 验收标准 | 预计工作量 |
| --- | --- | --- | --- | --- |
| P2-1 直启验证 | patch C + A1 | 现有 SD 目录（C:/Users/<user>/AppData/Roaming/citron/sdmc/kirikiri/haruno，3.4 GB 已在） | Citron 启动 NRO 后**不出现文件选择器**，直接进游戏标题/主菜单；手柄 A 可推进；k2s_log.txt 无 "An exception occured"；出现 5 条 [GalNX] internal plugin loaded 日志 | 0.5–1 天（构建打通后） |
| P2-2 自包含 | + A2（+ 把数据塞 ROMFS） | ROMFS（首启解包到 SD） | 删除 SD 上的 kirikiri/haruno 后首次启动：解包 → 自动进游戏；第二次启动 <10 秒跳过解包；SD 侧文件数/总字节与源一致（至少抽样 10 个文件 sha256 一致） | 0.5 天 |
| P3 出包 | ELF → NSO → NPDM/NACP → hacBrewPack | ROMFS（NSP 内） | Citron 安装 NSP 并启动：自包含 + 直接进游戏 + 手柄可操作；NSP 大小与 ROMFS 内容相符 | 0.5–1 天（P1-d 并行提供打包脚本） |
| P4 真机 | 无改动（title takeover 运行） | 同 P3 | 真机首次启动解包 → 进游戏；性能达到可玩（目标 30 fps，软渲染下需实测） | 后续里程碑 |

### 4.3 体积 / 时间 / 空间预算

- 游戏目录约 2.9 GB（P1-a 记录：14 个 xp3 合计约 2.9 GB，另有 plugin/ 约 1.4 MB、字体等）。
- NSP 大小 ≈ 游戏数据 2.9 GB + UI 资源约 7.5 MB + 引擎代码段约 42 MB ≈ **3.0 GB**；hacBrewPack 打包时临时工作目录需要约再一份空间（本机盘需 ≥6 GB 空闲）。
- 设备侧占用：ROMFS 内那份（NSP 内）约 3.0 GB 只读 + 解包到 SD 的约 2.9 GB ≈ **5.9 GB**。这是「自包含」的代价；若用户的 SD 空间不足，唯一干净的回退是路径 B（数据外置），不能靠删除 NSP 内 ROMFS 解决（NSP 不可部分删除）。
- 解包时间：按 SD 写入 10–20 MB/s 估算 2.9 GB ≈ 2.5–5 分钟；Citron 的虚拟 SD 落在宿主机 SSD 上，预期更快，但 emulator 的 fs 层性能尚未实测（U1）。首次启动期间没有 UI（cocos 还没初始化），只有日志/黑屏，建议在文档和打包产物里说明「首启需要几分钟」。
- NSP 打包时间：hacBrewPack 对 3 GB 内容做 NCA 封装 + PFS0，估算 5–15 分钟、内存峰值 1–2 GB（**未实测**，P1-d 的 005 链路只验证过 309 KB 级 demo）。

### 4.4 风险缓解（对应 §8 风险编号）

- R1 软渲染性能：P2-1 先用 NRO 在 Citron 观察标题/菜单帧率；若不可接受，先评估关闭透明混合/降低 GL 分辨率，再决定是否换 GPU 通道（K2NX 当前无 GPU 渲染路径）。
- R4 解包黑屏体验：可选增强——解包前用 libnx framebuffer/consoleInit 画一行进度文字（不依赖 cocos）；或退而在 NSP 启动前由启动器提示。该项不阻塞 P2/P3。
- R5 插件语义差异：保留 k2s_log.txt 作为唯一运行时诊断面；P2-1 测试前把 debug 日志级别开到最大（现有 setupLogging 已把 stdout/stderr 落盘）。
- R6 部分解包/断电：marker 只在全部复制成功并写完 startup.txt 后写入；失败时删临时 marker，下次启动重新解包；复制中途产生的半文件会被下一次覆盖（同名文件 open("wb") 截断）。
- R7 数据一致性：解包结束后打印 files/bytes；与构建时 ROMFS 的清单（构建日志里 romfs 目录的 du -sb）比对；P2-2 抽样 sha256。

## §5 补丁草案（A 路径三处改动）

> 注：Lead 已在工作副本中落地 A1/A2，落地版与本文草案的差异及源码级复核结论见 §2.13（含 P0 级 startup= 取参要求）；本节保留为设计记录。

> 以下为**草案代码**，用于记录改动点与可编译性判断；实际改动由 Lead 在 k2nx-ws 工作副本落地（patch C 已落地，A1/A2 待落地后构建验证）。

### 5.1 A1：自动启动（文件 src/core/environ/switch/SwitchUtils.cpp）

现有实现只有 3 行（:133-136）：

~~~cpp
void TVPCheckAndSendDumps(const std::string &dumpdir, const std::string &packageName, const std::string &versionStr);
bool TVPCheckStartupArg() {
	return false; // Android: only dump check; no launch arguments on Switch (yet)
}
~~~

替换为（新增 include：MainScene.h、cstdio、cstring，其余沿用文件已有 include）：

~~~cpp
// [GalNX 补丁 A1] 自动启动：读取 startup.txt 跳过文件选择器
// startup.txt 由 A2 首启解包写入；内容为一个 Unix 形式路径，例如 /kirikiroid/haruno/data.xp3
#include "MainScene.h"   // TVPMainScene::GetInstance() / startupFrom() 需要完整定义
#include <cstdio>
#include <cstring>
#include <string>

bool TVPCheckStartupArg()
{
    const char *kStartupFile = "sdmc:/switch/kirikiroid2/startup.txt";
    FILE *fp = fopen(kStartupFile, "rb");
    if (!fp) return false;                      // 没有 startup.txt：保持原行为（弹选择器）
    char buf[512] = {0};
    size_t n = fread(buf, 1, sizeof(buf) - 1, fp);
    fclose(fp);
    if (n == 0) return false;
    buf[n] = 0;
    for (size_t i = 0; i < n; i++) {
        if (buf[i] == '\r' || buf[i] == '\n') { buf[i] = 0; break; }
    }
    if (buf[0] == 0) return false;
    // 引擎只接受 Unix 形式路径：libnx 把前导 / 解析到 sdmc（见 SwitchUtils.cpp:100-108 注释）。
    if (buf[0] != '/') {
        printf("[GalNX] autostart: startup.txt must be an absolute Unix path: %s\n", buf);
        return false;
    }
    bool ok = TVPMainScene::GetInstance()->startupFrom(std::string(buf));
    printf("[GalNX] autostart %s: %s\n", ok ? "ok" : "FAILED", buf);
    return ok;                                  // 失败回退文件选择器，避免黑洞
}
~~~

要点与可编译性核对：

- TVPMainScene 类定义在 src/core/environ/cocos2d/MainScene.h，SwitchUtils.cpp 当前未 include（需新增）；startupFrom 声明在 MainScene.h（实现 MainScene.cpp:1729）。
- AppDelegate.cpp:20 已有 bool TVPCheckStartupArg(); 前置声明，签名不变，无需改调用方。
- 调用上下文是 scheduleOnce 回调（cocos 主线程、scene 已创建），startupFrom 内部再 scheduleOnce(doStartup) 合法。
- startupFrom 返回 false 的情况：TVPCheckStartupPath 失败（Switch 恒 true，但保留防御）、或路径不存在时后续 StartApplication 会在日志里报错；返回 true 只代表已排期启动，TJS 异常仍会出现在 k2s_log.txt。
- 可选变体：若希望 startup.txt 从 ROMFS 读（防 SD 被篡改），可先试 romfs:/startup.txt 再回退 sdmc:；当前只做 SD 版本，够用。

### 5.2 A2：首启解包（新增 src/core/environ/switch/galnx_extract.cpp/.h + main.cpp 插一行 + CMake 加一个源文件）

新增头文件 src/core/environ/switch/galnx_extract.h：

~~~cpp
#pragma once
// [GalNX 补丁 A2] 首启解包：ROMFS 内置游戏数据 → SD 可写目录
#ifdef __cplusplus
extern "C" {
#endif
bool galnx_extract_needed(void);
bool galnx_extract_if_needed(void);
#ifdef __cplusplus
}
#endif
~~~

新增源文件 src/core/environ/switch/galnx_extract.cpp：

~~~cpp
// [GalNX 补丁 A2] 首启解包：romfs:/game/haruno -> sdmc:/kirikiroid/haruno
// 纯 POSIX + libnx：opendir/readdir/stat 遍历 ROMFS（libnx 4.12.0 的 romfs devoptab 已实现，
// 见 libnx/include/switch/runtime/devices/romfs_dev.h 与 libnx.a 的 romfs_diropen/romfs_dirnext 符号）。
#include "galnx_extract.h"

#include <cstdio>
#include <cstring>
#include <cerrno>
#include <cstdint>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <dirent.h>
#include <switch.h>

namespace {

const char *kRomfsGame   = "romfs:/game/haruno";
const char *kSdRoot      = "sdmc:/kirikiroid";
const char *kSdGame      = "sdmc:/kirikiroid/haruno";
const char *kMarker      = "sdmc:/switch/kirikiroid2/.game_extracted";
const char *kTempMarker  = "sdmc:/switch/kirikiroid2/.game_extracting";
const char *kStartup     = "sdmc:/switch/kirikiroid2/startup.txt";
const char *kStartupPath = "/kirikiroid/haruno/data.xp3";   // 引擎侧 Unix 形式（无 sdmc: 前缀）
const unsigned long long kMinFreeBytes = 3300ULL * 1024ULL * 1024ULL;   // 约为游戏大小 2.9 GB + 余量
const size_t kBufSize = 64 * 1024;

char g_buf[kBufSize];

int ensure_dir(const char *path)
{
    char tmp[512];
    snprintf(tmp, sizeof(tmp), "%s", path);
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = 0;
            mkdir(tmp, 0777);
            *p = '/';
        }
    }
    if (mkdir(tmp, 0777) != 0 && errno != EEXIST) {
        printf("[GalNX] extract: mkdir(%s) failed: %s\n", tmp, strerror(errno));
        return -1;
    }
    return 0;
}

int copy_file(const char *src, const char *dst)
{
    FILE *in = fopen(src, "rb");
    if (!in) { printf("[GalNX] extract: open read %s failed: %s\n", src, strerror(errno)); return -1; }
    FILE *out = fopen(dst, "wb");
    if (!out) {
        printf("[GalNX] extract: open write %s failed: %s\n", dst, strerror(errno));
        fclose(in);
        return -1;
    }
    size_t n;
    bool ok = true;
    while ((n = fread(g_buf, 1, kBufSize, in)) > 0) {
        if (fwrite(g_buf, 1, n, out) != n) { ok = false; break; }
    }
    if (ferror(in)) ok = false;
    fflush(out);
    fclose(out);
    fclose(in);
    if (!ok) { printf("[GalNX] extract: copy failed %s -> %s\n", src, dst); remove(dst); return -1; }
    return 0;
}

int copy_tree(const char *src, const char *dst, unsigned long long *files, unsigned long long *bytes)
{
    if (ensure_dir(dst) != 0) return -1;
    DIR *d = opendir(src);
    if (!d) { printf("[GalNX] extract: opendir(%s) failed: %s\n", src, strerror(errno)); return -1; }
    int rc = 0;
    struct dirent *e;
    while ((e = readdir(d)) != nullptr) {
        if (strcmp(e->d_name, ".") == 0 || strcmp(e->d_name, "..") == 0) continue;
        char s[512], t[512];
        snprintf(s, sizeof(s), "%s/%s", src, e->d_name);
        snprintf(t, sizeof(t), "%s/%s", dst, e->d_name);
        struct stat st;
        if (stat(s, &st) != 0) {
            printf("[GalNX] extract: stat(%s) failed: %s\n", s, strerror(errno));
            rc = -1;
            continue;
        }
        if (S_ISDIR(st.st_mode)) {
            if (copy_tree(s, t, files, bytes) != 0) rc = -1;
        } else if (S_ISREG(st.st_mode)) {
            if (copy_file(s, t) != 0) { rc = -1; continue; }
            (*files)++;
            *bytes += (unsigned long long)st.st_size;
            if (((*files) % 200) == 0) {
                printf("[GalNX] extract: %llu files, %llu MB\n",
                       *files, (unsigned long long)(*bytes >> 20));
            }
        }
    }
    closedir(d);
    return rc;
}

bool has_free_space()
{
    struct statvfs v;
    if (statvfs("sdmc:/", &v) != 0) {
        printf("[GalNX] extract: statvfs(sdmc:/) failed: %s (skip check)\n", strerror(errno));
        return true;
    }
    unsigned long long avail = (unsigned long long)v.f_bavail * (unsigned long long)v.f_frsize;
    printf("[GalNX] extract: free on sdmc = %llu MB, need >= %llu MB\n",
           avail >> 20, kMinFreeBytes >> 20);
    return avail >= kMinFreeBytes;
}

} // namespace

bool galnx_extract_needed(void)
{
    struct stat st;
    return stat(kMarker, &st) != 0;
}

bool galnx_extract_if_needed(void)
{
    if (!galnx_extract_needed()) {
        printf("[GalNX] extract: marker present, skip\n");
        return true;
    }
    printf("[GalNX] extract: first boot, %s -> %s\n", kRomfsGame, kSdGame);
    if (!has_free_space()) {
        printf("[GalNX] extract: NOT enough free space on sdmc, aborting (fallback to file selector)\n");
        return false;
    }
    ensure_dir("sdmc:/switch/kirikiroid2");
    ensure_dir(kSdRoot);
    FILE *m = fopen(kTempMarker, "wb");
    if (m) fclose(m);

    appletSetCpuBoostMode(ApmCpuBoostMode_FastLoad);   // 只加速首启拷贝
    unsigned long long files = 0, bytes = 0;
    int rc = copy_tree(kRomfsGame, kSdGame, &files, &bytes);
    appletSetCpuBoostMode(ApmCpuBoostMode_Normal);
    printf("[GalNX] extract: done rc=%d files=%llu bytes=%llu\n", rc, files, bytes);
    if (rc != 0) {
        remove(kTempMarker);
        return false;
    }
    FILE *f = fopen(kStartup, "wb");
    if (f) { fputs(kStartupPath, f); fputc('\n', f); fclose(f); }
    f = fopen(kMarker, "wb");
    if (f) { fputs("galnx-extract-v1\n", f); fclose(f); }
    remove(kTempMarker);
    printf("[GalNX] extract: marker + startup.txt written\n");
    return true;
}
~~~

main.cpp 插入（src/core/environ/switch/main.cpp，现有 :29-47）：

~~~cpp
#include "galnx_extract.h"   // [GalNX A2]（与 main.cpp 同目录）
...
    Result rc0 = romfsInit(); // UI assets from APK 1.3.9 (tools/extract_apk_assets.sh)
    K2SBootMark(R_SUCCEEDED(rc0) ? "5 romfs ok" : "5 romfs FAILED");
    if (R_SUCCEEDED(rc0)) {
        galnx_extract_if_needed();   // [GalNX A2] 首启解包；失败时 A1 找不到 startup.txt 会自动回退选择器
    }
    TVPAppDelegate app;
~~~

CMake 改动（platforms/switch/CMakeLists.txt）：把新增源文件加入可执行目标 kirikiroid2 的源列表。文件末尾现在是：

~~~cmake
add_executable(kirikiroid2 APP_DIR/environ/switch/main.cpp)
~~~

（APP_DIR 是文档里的占位，实际为 CMake 变量 CORE 拼出的路径；见文件里 list(REMOVE_ITEM CORE_SRC ...main.cpp) 与 add_executable 那一段。）

改成在同一个 add_executable 里追加 environ/switch/galnx_extract.cpp 即可（用 CORE 变量拼路径）；不要加到 krkr2core 静态库里，否则会与 main.cpp 的 REMOVE_ITEM 逻辑纠缠。

A2 的可行性依据（全部已核实）：

- ROMFS 目录枚举可用：libnx 4.12.0 devoptab 实现 romfs_diropen / romfs_dirnext / romfs_dirclose / romfs_dirreset / romfs_stat / romfs_fstat / romfs_chdir（对 libnx.a 符号表实测）；romfsInit() = romfsMountSelf("romfs")（romfs_dev.h:113-121）。⇒ opendir("romfs:/...")、readdir、stat 均为标准 POSIX 调用，不需要自建索引。
- SD 写入：newlib 的 fopen("sdmc:/...","wb") 经 libnx fsdev 可用（引擎自身的 setupLogging 已在用 sdmc:/switch/kirikiroid2/k2s_log.txt，E1 已证）。
- 空间检查：statvfs("sdmc:/") 由 fsdev_statvfs 提供（libnx.a 有该符号）；若个别 newlib 版本字段名不一致，退回 fsFsGetFreeSpace + fsOpenSdCardFileSystem（fs.h:505/623）。
- 内存：64 KB 静态缓冲 + 每次一个文件流式复制，与 2.9 GB 数据量无关。
- CPU 加速：appletSetCpuBoostMode 已在 main.cpp 现有代码使用（ApmCpuBoostMode_Normal），FastLoad 是同一 API 的另一个枚举值。

### 5.3 patch C（已由 Lead 落地）

见 §2.11：src/plugins/InternalPlugins.cpp 增加 .tpm → .dll 别名回退 + 三条 [GalNX] 日志；约 +20 行；复核结论为必要、安全、最小。该补丁与 A1/A2 正交，可单独先构建验证（P2-1 的三件套之一）。

### 5.4 三处补丁的兼容性核对表

| 检查项 | A1 自动启动 | A2 首启解包 | patch C 插件别名 |
| --- | --- | --- | --- |
| 改动文件数 | 1（SwitchUtils.cpp） | 3（新增 .h/.cpp + main.cpp + CMake） | 1（InternalPlugins.cpp） |
| 是否需要新增头文件 | 需要（MainScene.h） | 不需要（libnx/newlib 已有） | 不需要 |
| 是否改公共/上游代码 | 是（switch 平台层） | 是（switch 平台层 + 构建脚本） | 是（plugins 公共层） |
| 不生效时的行为 | 弹文件选择器（原行为） | 由 A1 回退到选择器 | TJS 异常（原崩溃行为） |
| 可独立回退 | 是（删 startup.txt 即回退） | 是（删 marker 会重新解包；删 ROMFS 数据则 A1 回退） | 是（patch 反向撤销） |
| 编译依赖 | C++17、cocos2d-x 头文件 | C++17、libnx 4.12.0 | C++17、TJS2 头文件 |
| 本次是否已实测编译 | 否（草案） | 否（草案） | 否（Lead 已落地，构建进行中） |

## §6 可复现构建前置矩阵

### 6.1 工具链（本机与 CI 都必须）

| 组件 | 版本（本机实测） | 来源/安装方式 | 备注 |
| --- | --- | --- | --- |
| devkitA64 | r30-1 | devkitPro pacman（dkp-pacman） | K2NX 构建使用 aarch64-none-elf-gcc |
| devkita64-gcc | 16.1.0-1 | 同上 | K2NX CMake 注释特别提到 GCC15+ 会删除 TJS2 的空指针检查，已用 -fno-delete-null-pointer-checks 规避 |
| devkita64-binutils | 2.46.0-1 | 同上 | |
| devkita64-newlib | 4.6.0.20260123-4 | 同上 | |
| libnx | 4.12.0-1 | 同上 | romfs devoptab、sdmc 自动挂载、audren 均由它提供 |
| switch-tools（elf2nro/nacptool/build_romfs） | 1.13.1-1 | 同上 | NRO 产物生成 |
| switch-dev + switch-portlibs 组 | — | dkp-pacman -S --needed switch-dev switch-portlibs | **必须**：本机原缺 libonig / libopenal / libarchive / libglfw3 / libzstd / liblz4 / libexpat，它们都在该组内（已用 dkp-libs.db 核实：switch-glfw-3.3.4-2、switch-oniguruma-6.9.2-2、switch-openal-soft-1.21.1-5、switch-libarchive-3.7.2-7、switch-libexpat-2.2.5-3、switch-lz4-1.9.3-1、switch-libzstd-1.5.7-1） |
| cocos2d-x | 3.11.1（APK 1.3.9 内置版本） | fetch_cocos.sh（git clone --branch cocos2d-x-3.11.1 + v3-deps-94.zip + 两个 patch） | UI/渲染/输入/GL 上下文 |
| p7zip / LZMA SDK | p7zip 16.02 / LZMA SDK 16.04 | fetch_lzma_sdk.sh | 需要宿主 7z 命令；拷 C/ 与 CPP/ 到 src/core/base/7zip |
| 宿主工具 | bash、make、cmake（>=3.21 建议）、ninja、git、curl、sed、tar、xz、python3、unzip、7z、patch | apt（CI）/ MSYS2（本机） | 7z 是 fetch_lzma_sdk.sh 的硬依赖（脚本 command -v 7z || exit 2）；python3 给 make_icon.py；unzip 给 extract_apk_assets.sh |

### 6.2 必须自建的 7 个 portlibs（版本与固定方式）

| 库 | 版本 / commit | 下载地址 | 脚本内的关键处理 | 不能升级的理由 |
| --- | --- | --- | --- | --- |
| GNU libiconv | 1.17 | https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.17.tar.gz | --host=aarch64-none-elf --disable-shared --enable-static --disable-nls；先 make -C libcharset | newlib 无 iconv，引擎的编码转换需要 |
| FFmpeg | 3.2.19 | https://ffmpeg.org/releases/ffmpeg-3.2.19.tar.xz | sed 给 libavcodec/aarch64/{fft_neon.S,imdct15_neon.S} 加 relocate=1（PIE NRO 只读段重定位）；--target-os=none --extra-libs=-lnx；只关 encoder 不关 decoder；构建后 sed 置 HAVE_SECTION_DATA_REL_RO 1 | K2 1.3.9 的 movie 代码用 FFmpeg 5.0 之前的 API（AVStream->codec / avcodec_decode_video2），devkitPro 自带 FFmpeg 7.1 不可用 |
| OpenCV | 3.4.20 | https://github.com/opencv/opencv/archive/refs/tags/3.4.20.tar.gz | -DBUILD_LIST=core,imgproc；sed modules/core/src/system.cpp 在 __SWITCH__ 下置 have[CV_CPU_NEON]=true、have[CV_CPU_FP16]=true | 1.3.9 使用 OpenCV 3.0/3.1 era API；新版 CPU baseline 检测会在启动期抛异常 |
| UnRAR | 5.6.5 | https://www.rarlab.com/rar/unrarsrc-5.6.5.tar.gz | 条件化 newlib 缺失的 utimensat/UTIME_NOW；static RARDLL | 1.3.9 同期 import；UnRAR 源码许可禁止用其重建 RAR 压缩算法（再分发注意，见 §1.2/§8 R8） |
| libbpg | 0.9.8 | https://bellard.org/bpg/libbpg-0.9.8.tar.gz | decoder only + patches/libbpg_gray_line.c 与头文件声明 | 1.3.9 的 BPG 图片支持 |
| jxrlib | master（**未 pin**） | https://github.com/4creators/jxrlib/archive/refs/heads/master.tar.gz | -D__ANSI__ -DDISABLE_PERF_MEASUREMENT -D_byteswap_ulong=__builtin_bswap32 等；产物 libjpegxr/libjxrglue | JPEG XR 支持；**风险：master 不固定，构建可重复性差（R9）**，建议 CI 里锁定 tar 的 sha256 或在本地缓存（该建议已被 Lead 在试点计划中采纳，见 R9） |
| Blend2D | commit d2027ebfd6aaf53b190b6b3b497425fc85f14251 | 由 build_blend2d.sh 内的上游仓库 clone 后 checkout | 为 __SWITCH__ 启用 Apple 分支（newlib 64-bit off_t、无 *64 file API） | krkr2 的 LayerExDraw 用 camelCase API（vcpkg baseline 2025-03-08 对应的 commit） |

说明：这些库都是**静态链接**进 NRO，所以 K2NX 二进制体积约 42 MB（NRO 实测 42,338,934 B）；也意味着 LGPL 类组件（FFmpeg、libiconv）的再分发需提供 relink 手段（THIRD_PARTY_LICENSES.md 已声明）。

### 6.3 外部资源（非源码，构建时下载或提取）

| 资源 | 来源 | 用途 | 备注 |
| --- | --- | --- | --- |
| Kirikiroid2 1.3.9 APK | https://github.com/zeas2/Kirikiroid2/releases/download/1.3.9/Kirikiroid2_1.3.9.apk | extract_apk_assets.sh 抽出 assets/* 作为 ROMFS UI 资源（res/、DroidSansFallback.ttf、default.cur 等），并用 make_icon.py 生成 icon.jpg | 必须用 1.3.9 版（源码与资源版本配套） |
| cocos2d-x 第三方依赖包 | https://github.com/cocos2d/cocos2d-x-3rd-party-libs-bin/archive/v3-deps-94.zip | 解压到 cocos external/ | 与 3.11.1 配套 |
| p7zip 16.02 源码 | https://downloads.sourceforge.net/project/p7zip/p7zip/16.02/p7zip_16.02_src_all.tar.bz2 | 7z 解压 LZMA SDK 用 | 脚本注释要求 WSL/Linux 环境 |
| LZMA SDK 16.04 | https://www.7-zip.org/a/lzma1604.7z | src/core/base/7zip | 需要宿主 7z |

### 6.4 构建命令与 K2NX_WS 布局（上游 README 记录 + 脚本实测）

K2NX 的脚本假定一种固定目录布局：**仓库本身必须在 K2NX_WS/src**（fetch_cocos.sh 把 cocos 放 K2NX_WS/src/vendor/cocos2d-x，K2S_SRC_CACHE 在 K2NX_WS/.cache/src）。完整顺序：

~~~
export K2NX_WS=/path/to/workspace          # 该目录下 src/ 就是 K2NX 仓库
export K2S_PORTLIBS=$HOME/k2s-portlibs     # 可选覆盖；默认值见 portlibs/env.sh

# 1) 工具链（本机已装可跳过；脚本需要 root/apt）
bash platforms/switch/tools/setup_wsl_devkitpro.sh

# 2) 拉 cocos2d-x 3.11.1 + 打 Switch patch
bash platforms/switch/tools/fetch_cocos.sh

# 3) 拉 p7zip/LZMA SDK（需要宿主 7z）
bash platforms/switch/tools/fetch_lzma_sdk.sh

# 4) 7 个自建 portlibs（顺序无关，各自独立构建）
for s in libiconv ffmpeg opencv unrar libbpg jxrlib blend2d; do
  bash platforms/switch/tools/portlibs/build_$s.sh
done

# 5) 从 APK 1.3.9 提取 UI 资源到 $K2NX_WS/build/romfs 与 build/icon.jpg
bash platforms/switch/tools/extract_apk_assets.sh

# 6) 构建 NRO（TGT=all，CFG=Debug|Release）
bash platforms/switch/tools/build_k2.sh all Release
~~~ 

build_k2.sh 的实现细节：source /etc/profile.d/devkit-env.sh；用 **/opt/devkitpro/portlibs/switch/bin/aarch64-none-elf-cmake** 配置（这个 wrapper 决定交叉工具链），-G Ninja、-DCMAKE_BUILD_TYPE=$CFG、-DCMAKE_POLICY_VERSION_MINIMUM=3.5；构建目录 $HOME/k2s-build/k2-$CFG；ninja -j4 -k 0 $TGT。ROMFS 与 icon 的路径由 CMake 的 K2NX_ASSETS 指向 $K2NX_WS/build。

本机（MSYS2）可行性结论：devkitPro 自带 MSYS2 在 D:/devkitPro/msys2，进入方式 env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '...'；其中 DEVKITPRO=/opt/devkitpro 已可用、/etc/profile.d/devkit-env.sh 存在（但 PATH 只加了 tools/bin，需手工补 /opt/devkitpro/devkitA64/bin 与 /opt/devkitpro/portlibs/switch/bin）；MSYS2 侧原缺 unzip/python3/patch/7z，需用 /d/devkitPro/msys2/usr/bin/pacman.exe 补装。⇒ 本机可以跑通，但需要先补包与 PATH，且仓库布局要满足 $K2NX_WS/src（Lead 的 k2nx-ws 正是这种布局）。本审计不重复 Lead 正在进行的构建。

## §7 GitHub Actions CI 设计（重建可重复性）

### 7.1 为什么需要 CI

- 构建链依赖 7 个自建 portlibs + cocos2d-x + APK 资源，本机一次冷构建预计 90–150 分钟（见 7.4）；日常迭代不可能每次全量。
- 上游仓库**没有 .github/**（无任何 CI），所以本 workflow 需要新建。
- CI 只负责「NRO 可重复产出」；NSP 打包不放进 CI（hacBrewPack 需要 keyset，属于本机版权密钥，按项目约定不得进入 CI/仓库，见 docs/builds/005 §5.2 与打包约定）。

### 7.2 workflow 结构（草案文件：E:/galnx-build/pilot-01/gha/ci-k2nx.yml，4,813 B；已用 PyYAML 校验可解析，jobs=build）

- 触发：workflow_dispatch（手动）+ push tag v*（发布构建）；不做每次 push 构建（成本）。
- job 容器：devkitpro/devkita64:20260219（与 platform/consoles/README.md 记录的官方镜像一致；install_devkitpro_from_docker.sh 注释也说明 apt.devkitpro.org 在该网络会被 Cloudflare 403，官方镜像是最稳的获取方式）。
- 步骤：
  1. actions/checkout@v4，**path: src**（满足 K2NX_WS/src 布局），K2NX_WS 设为 GitHub workspace。
  2. apt-get 安装宿主依赖：git cmake ninja-build pkg-config python3 unzip p7zip-full curl bison flex nasm yasm autoconf automake libtool file ca-certificates（p7zip-full 提供 7z）。
  3. dkp-pacman -S --needed switch-dev switch-portlibs（容器内幂等；补齐 oniguruma/openal/libarchive/libexpat/lz4/libzstd 等）。
  4. 导出 PATH：在 /etc/profile.d/devkit-env.sh 基础上追加 /opt/devkitpro/devkitA64/bin 与 /opt/devkitpro/portlibs/switch/bin（上游脚本的 devkit-env.sh 不含这两项，这是本审计发现的 CI 坑）。
  5. actions/cache 恢复（key 见 7.3）：$HOME/k2s-portlibs、$K2NX_WS/.cache/src、$K2NX_WS/src/vendor/cocos2d-x、$K2NX_WS/build/romfs。
  6. 依次运行 fetch_cocos.sh、fetch_lzma_sdk.sh、7 个 build_*.sh、extract_apk_assets.sh（已缓存的步骤会自动跳过：fetch() 函数与 cocos clone 都是「存在即跳过」语义，portlibs 脚本按产物存在判断）。
  7. bash platforms/switch/tools/build_k2.sh all Release。
  8. 上传产物：kirikiroid2.nro（构建日志里打印的确切路径）、构建日志、以及 $K2NX_WS/build/romfs 的文件清单（用于 NSP 打包前核对）。
- 超时：timeout-minutes: 240；失败时上传日志 artifact（if: failure()）。

### 7.3 缓存策略（4 项）

| 缓存路径 | key 依据 | 预期体积 | 说明 |
| --- | --- | --- | --- |
| $HOME/k2s-portlibs | hashFiles('src/platforms/switch/tools/portlibs/**') | 数百 MB（FFmpeg/OpenCV/Blend2D 静态库为主） | 最重要的缓存项；命中后 7 个 portlibs 全部跳过 |
| $K2NX_WS/.cache/src | 同上（脚本内 URL/版本） | ~200 MB（源码 tar 包） | 次要；命中可省下载时间 |
| $K2NX_WS/src/vendor/cocos2d-x | hashFiles('src/platforms/switch/cocos2dx/patches/**') + cocos 版本常量 | ~1.5–2 GB（cocos2d-x + v3-deps-94） | 体积大，GitHub 缓存上限 10 GB/仓库，注意与其他缓存争用；若频繁被驱逐可改为每次重建（约 +5–8 分钟） |
| $K2NX_WS/build/romfs | hashFiles('src/platforms/switch/tools/make_icon.py') + APK 版本 | ~8 MB | UI 资源，命中后不必每次拉 APK（APK 本身约 30–40 MB） |

### 7.4 构建时长与成本估算

| 场景 | 预估（2 vCPU GitHub 私有仓库 runner） | 依据 |
| --- | --- | --- |
| 冷构建（无缓存） | 90–150 分钟 | FFmpeg 3.2.19 交叉编译约 15–25 min；OpenCV 3.4.20 core+imgproc 约 10–15 min；Blend2D/UnRAR/libbpg/jxrlib/libiconv 合计约 10–15 min；cocos2d-x + 引擎本体（NRO 42 MB、ninja -j4）约 25–40 min；下载/解压/APK 约 5–10 min |
| 热构建（portlibs + cocos 缓存命中） | 35–50 分钟 | 只剩引擎增量编译 + 链接 + NRO 打包 |
| 仅引擎改动（只缓存 portlibs/cocos） | 30–45 分钟 | 与热构建接近 |

- 私库配额 2,000 分钟/月：按冷构建 13–22 次，或热构建 40–57 次。建议策略：**日常在本机 MSYS2 构建；CI 只在发版 tag / 需要可复现证据时跑**，并把 workflow_dispatch 保留给补丁验证。
- GitHub Actions 缓存不保证跨分支/跨 PR 复用，且 7 天未访问会被清理；因此 CI 的定位是「可重复的发布构建」，不是日常开发循环。

### 7.5 不在 CI 中做的事（明确边界）

- 不做 NSP 打包（需要 keyset；按项目约定密钥不进 CI/仓库，本机用 docs/builds/005 的 elf2nso → npdmtool → nacptool → hacBrewPack 链路）。
- 不接触游戏数据（3.4 GB 商业内容不进仓库、不进 CI；ROMFS 数据在打包阶段由本机注入）。
- 不做真机测试（无设备）；Citron 运行验证也在本机（单实例约束，见 docs/pilot/README.md）。

## §8 风险与未验证项

### 8.1 风险登记（R1–R14）

| 编号 | 风险 | 等级 | 触发条件 | 缓解措施 |
| --- | --- | --- | --- | --- |
| R1 | 软渲染性能不足（Mesa GLES 3.2 on Switch，cocos 全场景每帧软光栅） | 中高 | 标题/场景帧率 < 20 fps | P2-1 先实测；降低 GL 分辨率/关闭高成本特效；K2NX 无 GPU 渲染路径，必要时评估上游未来版本 |
| R2 | 3 GB 级 NSP 打包/安装失败 | 中 | hacBrewPack 内存/时间超限；Citron 装载 3 GB NSP 失败 | P1-d 先行验证 005 链路在 GB 级内容的可行性；备选：分卷/数据外置 NSP（路径 B） |
| R3 | 首启解包时间过长/中断（2.9 GB，2.5–5 分钟） | 中 | SD 写速低、电量不足、用户强制退出 | marker 只在成功后写；失败重试；日志进度；文档说明首启需等待 |
| R4 | 插件语义差异（内建实现是简化移植，例如 windowEx 全部 nop、fstat 语义） | 中 | 后续脚本调用更深的 windowEx/fstat 特性 | k2s_log 观察 + P2-1 跑通首场景/存档界面；必要时补实现（工作量按调用点） |
| R5 | wumsadp / wuvorbis / krmovie 无插件模块，实际解码未验 | 中 | 播放 ADPCM/WMA 语音或视频时无声/崩溃 | 源码层面已有 FFmpeg 兜底（§2.12）；P2-1 重点测 BGM/语音/OP 视频 |
| R6 | 中文 xmoe 补丁无法在 Switch 运行（haruno_chs.exe / xmoe dll 是 PC 注入器） | 高（对中文化目标） | 需要中文文本 | 本轮明确只保日文原版（P1-a 已记录）；中文化属独立研究项 |
| R7 | 外部下载源不稳定（sourceforge / 7-zip.org / rarlab / bellard.org / devkitPro apt 的 Cloudflare 403） | 中 | CI 或本机构建时下载失败 | 缓存 + 重试；CI 用官方 devkitPro 镜像；把下载物也纳入缓存 |
| R8 | 许可与再分发（KiriKiri license BSD-style；UnRAR 限制；LGPL 静态链接） | 中 | 对外分发自制构建 | 自制引擎改动可分发（保留版权声明）；**游戏数据不得分发**；LGPL 需提供 relink 手段；UnRAR 不得用于重建 RAR 算法 |
| R9 | 构建可重复性（jxrlib master 未 pin；APK/源码下载源版本） | 中 | 需要复现同一二进制 | CI 锁定 tar sha256 / 记录 commit；本地缓存源码 tar；文档记录所有版本（§6）。**本项建议已被 Lead 在试点计划中采纳：CI 锁 jxrlib tar 的 sha256** |
| R10 | 上游维护风险（单人维护、18 stars、0 forks、1 open issue） | 中 | 需要长期修 bug/跟进 Switch 系统更新 | 保留本地 fork/patch 集（本审计的 patch 均记录在文档与 patch 脚本）；必要时接管维护 |
| R11 | 真机未验证（README 明示需要 title takeover；内存/性能/系统版本） | 高（对真机目标） | 进入 P4 真机阶段 | P3 达标后再上真机；优先验证 title takeover 模式内存与帧率 |
| R12 | **启动路径形态错误**：清单 startup= 写成目录（无尾斜杠）→ System.exePath 退化为父目录 → 14 个 xp3 全部挂不上（引擎能起标题但无素材/报错） | 高（若清单写错，属静默失败） | 打包脚本 startup= 取值错误 | 固定取 `<target>/data.xp3`（§2.13.1 四步证据链）；P2-2 日志核对 Auto Path 的 file(s) found 数量与 Trying to read XP3 序列是否出现 data.xp3 之外的文件 |
| R13 | **A2 v1 的 MkDirs 会把文件路径当目录创建**（`GalNX_MkDirs(dst)` 在 `i==size` 时对完整文件路径 mkdir → 生成与文件同名的目录 → `fopen(dst,"wb")` EISDIR 失败 → 首启解包 100% 失败、marker 永不写、每次启动重试） | 高（一旦 NSP 带 payload 即致命；r1 因 romfs 无清单未触发） | v1 的 `GalNX_MkDirs` 语义缺陷 | 已由 Lead 在 A2 v2 修复：拆分 `GalNX_MkDirs(目录)` 与 `GalNX_MkParentDirs(文件父目录)`（§2.13.6 复核 PASS） |
| R14 | **harness 多步 run 早退缺陷**：`scripts/citron_run.sh` 在多步 input-steps 的 run 上可能打印 `polling up to 420 s for boot evidence` 后约 27 s 静默退出 exit 0，且**无 result.json / 无截图 / 无 stdout JSON**；此时 Citron 进程仍在（不作为「游戏没起来」的判据） | 中（影响自动化取证） | 多步 run 且窗口已出现 | **已定位（2026-10-30 07:2x）**：run3 的 bash -x trace 显示脚本能完整跑完并 `exit 0`（result.json/10 步骤全齐），失败样本均死于 bash 空闲期（poll 的 `sleep 2` 或 steps 的 `sleep_ms`）且无 result.json ⇒ 判定为**调用方杀掉 bash 进程树**（Citron 经 runas/Start-Process 转手而存活），非脚本逻辑；修复方向=让 harness 脱离调用方进程树 + 加 `trap ... EXIT` 自证 rc。规避方式=在单次 run_code 内同步 spawnSync 跑完（§2.13.11），detached spawn 无效 |

### 8.2 未验证项（U1–U20，均需后续实测）

| 编号 | 未验证内容 | 验证方法 |
| --- | --- | --- |
| U1 | 首启解包的真实耗时与稳定性（Citron 虚拟 SD / 真机 SD） | **A1 NSP 首启已实测（Citron）**：27563 MiB free → 22 文件 / 2737.2 MiB、mtime 跨度 ≈14 s（≈205 MB/s，§2.13.7）；**真机 SD 卡速度与稳定性未验** |
| U2 | 存档与 per-game 偏好实际写入位置与写读回成功（是否 game/savedata，日志 [K2S] write 行） | **位置已实证，写读回仍未验**：Data path : file://./kirikiroid/haruno/savedata/；`sdmc:/kirikiri/haruno/savedata/` 已存在（krenvprf.kep、krkr.console.log）；**RUN G 进入正文后仍未做存档操作**（无 [K2S] write 行）⇒ 需 P2-3 存档一次并回读（见 U20） |
| U3 | 视频播放（movie.xp3 的实际编解码与软渲染性能） | **部分**：logo.mpg（mpeg1video 1280x720 30fps + mp2 44100）已进入解码/播放路径；movie.xp3 内的实际过场视频（OP/章节动画）与软渲染帧率未验（RUN G 只到第一章开头） |
| U4 | 音频（.ogg BGM/语音、可能的 ADPCM/WMA）实际是否正确 | **部分收窄**：OpenAL Soft 初始化成功、logo.mpg 的 mp2 进入解码路径；.ogg BGM/语音实际出声、ADPCM/WMA 回退均未验（Citron 侧未做音频采样，当前运行环境静音） |
| U5 | 手柄在游戏内完整可玩性（虚拟鼠标点击 UI、A 推进、B 返回、存档界面操作） | **P2-2 达成前半（RUN G，E1/E2，§2.13.9）**：keymap 后 D-pad RIGHT + A 从标题确定性开始游戏（title.ks→start.ks→@0000A_Z01.ks），再按 A 推进一页；根因见 §2.13.8（pad 默认转 VK_PAD*、脚本只认 VK_*，已用零重建 keymap XML 修复）。仍未验：B=ESC 菜单、D-pad 上下选项/历史、存档界面操作、真机手柄；A2 run（07:42）中按 B 无可见变化（Lead 记 U，未作结论） |
| U6 | extrans / layerExImage 是否被 KAG 标签间接使用，简化实现是否够用 | **P2-2 进一步收窄**：5 个内建插件已激活（内含 extrans/layerExImage），标题 → 正文 → 第一章脚本全程 0 TJS 异常；extrans/layerExImage 的实际调用路径仍未证（脚本层直接引用为 0） |
| U7 | 14 个 xp3 的完整挂载与深层场景读取（E1 已见 Auto Path 19183 files，但只到标题界面） | **P2-2 达成前半**：14 个 xp3 全部 Trying to read XP3、Auto Path 19,153 found / 19,141 activated、标题 → start.ks → @0000A_Z01.ks 三连切换成功；更远剧情/分支/结局未验 |
| U8 | NSP 打包（3 GB ROMFS）与 Citron 安装/启动 | **P3 部分达成**：A1 自包含 NSP（romfs 含 2.67 GiB payload + game_files.txt）已被 Citron 直接加载（`BootGame: ... 010047410000B0B2`）、首启解包、自动启动到标题、60 FPS（§2.13.7）；**真机安装（Atmosphère + sigpatches）与「安装为 title 后从 Home 菜单启动」未验** |
| U9 | SD 空间不足时的用户可见行为 | 人为填满 SD 后启动 |
| U10 | 部分解包（断电/强制退出）后的恢复路径 | 解包中途 kill，再次启动验证重新解包 |
| U11 | 中文化可行性（xmoe 体系移植到 Switch） | 独立研究项，不在本轮范围 |
| U12 | GitHub Actions 实际构建时长与缓存命中率 | 首次 CI 运行后回填本节 |
| U13 | 以 .xp3 为 startup 时 per-game 偏好与存档落点（Kirikiroid2Preference.xml 是否出现在 /kirikiroid/haruno/、savedata/ 是否生成） | **P2-1/A1 部分达成**：`sdmc:/kirikiri/haruno/savedata/` 已由引擎创建且 Data path 指向它；per-game 偏好 XML 与真实存档写读回仍未验（尚无存档操作） |
| U15 | CPU boost 是否真正覆盖解包窗口、真机 SD 解包耗时、二次启动 marker 命中路径 | **部分**：k2s_log 有 `[K2S] CPU boost: on (rc=0x0)`（API 返回成功，不代表频率窗口正确）；二次启动（marker `pilot01-r1` 命中 → keep existing → 直接 autostart）尚未实测；真机 SD 未测 |
| U14 | Citron 下「鼠标点击 / 虚拟光标」注入通道（标题菜单链接点击坐标映射、harness 是否支持 clicks= 或左摇杆模拟量） | **坐标已定标**：游戏区 rect 112..1615 × 117..962、缩放 1.175，公式 px=112+1.175X / py=117+1.175Y，「はじめから」窗口坐标 **(390,925)**（§2.13.7）；**注入通道本身待验**：click 需要 `_virutalMouseMode` 为假（触屏直通）或先用摇杆推杆打开虚拟光标；Citron `analog_from_button` 轴值已定论（不按 Shift=满幅 0.99997、无渐变，§2.13.7）→ 摇杆注入可行但有「每键 1 步 vs 每帧 1 步」的过冲不确定性；**07:2x 更新**：按键根本不必走虚拟光标——预置 keymap XML 后 D-pad RIGHT + A(RETURN) 即可确定性开始游戏（§2.13.8），该序列待跑 |
| U17 | 手柄按键 keymap 修复的实际效果（D-pad RIGHT + A 能否从标题进入 start.ks；A 推进正文、B 菜单、D-pad 上下选项/历史） | **实测 PASS（RUN G，2026-10-30 07:26–07:29）**：预置 `sdmc:/kirikiri/haruno/Kirikiroid2Preference.xml`（1,293 B sha256 `aa4fa8ab…`）后，`wait:75000;key:RIGHT;key:C;key:C` 使 k2s_log 出现 `Scenario loaded : start.ks`（07:28:14）与 `@0000A_Z01.ks`（07:28:18），0 exception（§2.13.9）；B 菜单、D-pad 上下效果、以及该 XML 随自包含 NSP 分发（U18）仍待验 |
| U18 | A2 自包含 NSP「全新 SD 首启解包」验收（23 文件含 keymap XML、bytes= 空间预检、FastLoad boost、marker 写 pilot01-r2） | **PASS（E1/E3，2026-10-30 07:35–07:43，§2.13.10）**：清空 `sdmc:/kirikiri` 后，NSP `Kirikiroid2-NX-010047410000b0b4`（2,906,125,016 B sha256 `eb6c6a15…`）首启日志 = `free space check ok: 28196 MiB free for a 2737 MiB payload` → `copying 23 payload file(s)` → `payload copy finished: 23 copied, 0 kept, 0 failed, 2737 MiB total`；mtime 07:39:56.147→07:40:10.574 ⇒ ≈14.4 s；marker= pilot01-r2；`Kirikiroid2Preference.xml`（1,293 B）从 payload 解出 ⇒ keymap 随 NSP 分发成立；随后 autostart→title.ks（07:40:47）→start.ks（07:42:36），0 exception。**2026-10-30 08:0x 补证 PASS（§2.13.11）**：audit-engines 独立复跑（不同 run 目录/驱动）——R1 全新 SD 首启：解包 23 文件/2,870,635,309 B（mtime 跨度 13.22 s）、marker=pilot01-r2、keymap 从 payload 解出、title.ks 07:56:26→start.ks 07:58:13→@0000A_Z01.ks 07:58:16；R2 二启：`payload pilot01-r2 already extracted`→title.ks 08:00:19（48 s，无解包段）；与 Lead 证据一致（截图仅像素级，见 U18b/§6 L10）。**剩余**：真机 SD |
| U19 | 点击注入通道（mouse_event）在 Citron 下的可用性 | **已定论为「不可靠、不作判据」**（E1+E4，§2.13.9）：click 走 `SetCursorPos`+`mouse_event`（`scripts/citron_run.sh:660-666`），要求光标下为最顶层窗口，且 `focus_ok` 只在 SetForegroundWindow 后立即比对（不反映 120 ms 后状态）；RUN C/E/F 三次 click 均未触发菜单，而 06:50 那次成功的 start.ks 无对应 harness run。⇒ 自动化一律走键盘/keymap；真机触摸屏直通分支（MainScene.cpp:588-608）仍未验 |
| U20 | 存档写读回（savedata/ 下真实存档写入、退出重进读取、per-game 偏好随 NSP 分发） | **未验**：RUN G 到正文但未存档；per-game XML 已证实引擎不覆写（RUN G 后 mtime 与大小不变）**2026-10-30 08:0x 补证**：A2 形态下 keymap XML 由 payload 解包（§2.13.11，R2 后 sha 不变）⇒「随 NSP 分发」成立；**存档写入/读回仍未验**，建议 P2-3：进正文后存档 → 检查 `[K2S] write` 行与文件、重启后读档 |

## §9 来源

### 9.1 本地源码与工作区

- K2NX 源码：E:/galnx-build/pilot-01/k2nx-src（HEAD e96b6034c292c6ccdb099823ab6a0a6b505f77f3，tag v1.0.1，committer date 2026-10-18T17:27:29Z）
- Lead 工作副本（已打 patch C）：E:/galnx-build/pilot-01/k2nx-ws/src
- 预编译 NRO：E:/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/pilot-01/Kirikiroid2-NX-v1.0.1.nro（42,338,934 B，sha256 ce3c0169610eb2d65f332e26a16d14c283f9dcf39634dc4f46c2c004860919b8）
- E1 崩溃日志副本：E:/galnx-build/pilot-01/refs/k2s_log-prev-20261030-0603.txt（4,604 B，sha256 891e90ca1bab38afdf6bf9c9e040128d3a68a1b3bf161af40e4fd36c108fb945）
- 脚本提取报告：E:/galnx-build/pilot-01/report_scripts2.txt（tjs 全文摘录）、report_plugins_scan.txt（插件名扫描）、report_k2nx_plugins.txt（内建 NCB 名）
- 游戏脚本副本：E:/galnx-build/pilot-01/extract/data/sys_source/（30 个 tjs，只读提取用于插件调用点分析）
- 游戏 plugin/ 目录：C:/Users/<user>/AppData/Roaming/citron/sdmc/kirikiri/haruno/plugin/（只列文件名与大小）
- 关联文档：docs/pilot/README.md（P1 任务书与风险登记）、docs/builds/005-nsp-selfcontained.md（NSP 链路）、docs/audit/06-engines-refresh.md（引擎候选）、docs/packaging/README.md（打包契约）

### 9.2 关键源码位置（K2NX HEAD e96b6034）

- 启动/自动启动：src/core/environ/switch/main.cpp:29-47、src/core/environ/cocos2d/AppDelegate.cpp:20/33-107（:96-102 launch lambda）、src/core/environ/ui/MainFileSelectorForm.cpp:199/202/270-286/538
- 引擎启动：src/core/environ/cocos2d/MainScene.cpp:1729-1779（startupFrom/doStartup）、src/core/environ/Application.cpp:265-267（ExePath）/546-620（StartApplication）
- 存储路径：src/core/base/win32/StorageImpl.cpp:258-368（GetLocallyAccessibleName/GetLocalName）/387-427（TVPPreNormalizeStorageName）/511-519（TVPGetAppPath）/525-537（TVPOpenStream）/740-803（tTVPLocalFileStream）、src/core/base/StorageIntf.cpp:978-1120（AutoPath 表）/1382（Storages.addAutoPath）
- 插件：src/core/base/win32/PluginImpl.cpp:449-452（TVPLoadPlugin）/486-506（TVPUnloadPlugin #if 0）/527-534（TVPSearchPluginsAt）/557-589（TVPLoadPluigins）/989（Plugins.link 路径）、src/plugins/InternalPlugins.cpp、src/plugins/ncbind/ncbind.cpp:11-32、src/plugins/ncbind/ncbind.hpp:2115-2166
- 各内建插件：src/plugins/csvParser.cpp:5/370/471、src/plugins/fstat/main.cpp:933/1022、src/plugins/layerExImage/Main.cpp:29、src/plugins/windowEx/main.cpp:1-9/12/143/176/210/218/222
- 音频/视频：src/core/sound/WaveIntf.cpp:585-735/744-767/789+、src/core/sound/FFWaveDecoder.cpp:100-109、src/core/sound/VorbisWaveDecoder.cpp、src/core/visual/win32/VideoOvlImpl.cpp:198-205、src/core/movie/ffmpeg/krffmpeg.cpp:45-60+
- 输入：src/core/environ/cocos2d/MainScene.cpp:2083-2120（虚拟光标）/2300-2363（摇杆）/2365-2395（A/B 点击）、platforms/switch/cocos2dx/patches/0001-switch-platform.patch:50-128
- 构建：platforms/switch/CMakeLists.txt（含结尾 add_executable/link/NACP/NRO）、platforms/switch/tools/{build_k2.sh,fetch_cocos.sh,fetch_lzma_sdk.sh,extract_apk_assets.sh,install_devkitpro_from_docker.sh,setup_wsl_devkitpro.sh}、platforms/switch/tools/portlibs/{env.sh,build_*.sh}

### 9.3 外部来源（均为本审计实测抓取或源码内 URL）

- K2NX 仓库与发布：https://github.com/Erige005/Kirikiroid2-NX（tag v1.0.1 = e96b6034c292c6ccdb099823ab6a0a6b505f77f3；release asset Kirikiroid2-NX.nro 42,338,934 B sha256 ce3c0169…）
- K2NX README（安装/控制/已知问题/构建步骤）：仓库根 README.md
- Kirikiroid2 1.3.9 APK：https://github.com/zeas2/Kirikiroid2/releases/download/1.3.9/Kirikiroid2_1.3.9.apk
- cocos2d-x 3.11.1：https://github.com/cocos2d/cocos2d-x（tag cocos2d-x-3.11.1）；依赖包 https://github.com/cocos2d/cocos2d-x-3rd-party-libs-bin/archive/v3-deps-94.zip
- FFmpeg 3.2.19：https://ffmpeg.org/releases/ffmpeg-3.2.19.tar.xz
- OpenCV 3.4.20：https://github.com/opencv/opencv/archive/refs/tags/3.4.20.tar.gz
- UnRAR 5.6.5：https://www.rarlab.com/rar/unrarsrc-5.6.5.tar.gz
- libbpg 0.9.8：https://bellard.org/bpg/libbpg-0.9.8.tar.gz
- jxrlib：https://github.com/4creators/jxrlib（master 分支）
- libiconv 1.17：https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.17.tar.gz
- p7zip 16.02：https://downloads.sourceforge.net/project/p7zip/p7zip/16.02/p7zip_16.02_src_all.tar.bz2；LZMA SDK 16.04：https://www.7-zip.org/a/lzma1604.7z
- devkitPro 官方镜像：devkitpro/devkita64:20260219（Docker Hub）

## §10 变更记录

| 时间（UTC+8） | 变更 | 作者 |
| --- | --- | --- |
| 2026-10-30 05:38 前 | 初版 §0–§3（摘要、对象版本、机制审计、三路径对比），基于源码取证与 P1-a 运行记录 | audit-engines |
| 2026-10-30 06:0x | 新增 §2.11 插件名别名缺陷（E1 k2s_log.prev.txt 崩溃证据 + patch C 复核）、§2.12 8 插件映射表；修订 §0.1/§2.7/§3.1（插件从「低风险」升级为「已定位确定缺陷，patch C 修复」） | audit-engines |
| 2026-10-30 06:1x | 新增 §4 实施设计（启动时序、P2-1/P2-2/P3 验收、体积时间预算、风险缓解）、§5 补丁草案（A1 自动启动、A2 首启解包、兼容性核对表）、§6 构建前置矩阵、§7 GHA CI 设计、§8 风险 R1–R11 与未验证 U1–U12、§9 来源 | audit-engines |
| 2026-10-30 06:2x | 落盘 GHA workflow 草案 E:/galnx-build/pilot-01/gha/ci-k2nx.yml（4,813 B，PyYAML 可解析）；§7.2 补草案说明 | audit-engines |
| 2026-10-30 06:3x | 按 Lead 确认：§2.11 标题标注「已实施」并补实施状态说明（patch C 已落地 k2nx-ws 且通过源码审计；cosmetic 改进暂不做）；§2.8 补 E1 存档根证据（Data path : file://./kirikiri/haruno/savedata/ ⇒ A 路径无需存档重定向补丁）；jxrlib 锁 sha256 建议标注已被 Lead 在试点计划采纳（§6.2/R9） | audit-engines |
| 2026-10-30 06:5x | 新增 §2.13 对 Lead 落地补丁的源码级预复核：P0 级 startup= 取参陷阱（四步证据链，必须指向 data.xp3）、A2 五点改进、A1 fflush 建议、与 §5 草案差异；§8.1 增 R12、§8.2 增 U13；§5 头注指向 §2.13 | audit-engines |
| 2026-10-30 07:0x | 新增 §2.13.7 A1 自包含 NSP 首启实测（run 20261030-065340、三张同哈希截图、k2s_log 原文空间预检/22 文件/2737 MiB/19152 files activated/OpenAL/logo.mpg/title.ks/CPU boost 行、marker 与 autostart 内容、E3 SD 总量与 ≈14 s 耗时、点击坐标公式与 (390,925)、Citron analog_from_button 轴值定论）；§8.2 标题改 U1–U16、回填 U1/U8/U13/U14 并新增 U15 | audit-engines |
| 2026-10-30 06:4x | 新增 §2.13.5 首次落地构建与 P2-1 Citron 首跑（r1 NRO sha256、E2BIG 构建坑、12 项逐条复核表、A 键=虚拟光标单击的硬约束）、§2.13.6 A2 v2 复核（r2 NRO/ELF sha256、v1 MkDirs 致命 bug 登记、7 项 PASS 明细）；§2.11 补首跑实证；§8.1 增 R13；§8.2 回填 U2/U4/U5/U6/U7 状态并增 U14 | audit-engines |
| 2026-10-30 07:2x | 手柄按键根因闭环：§2.9 追加「pad→VK_PAD*、脚本只认 VK_*、默认 A/B/D-pad 无效」缺陷说明与 keymap XML 注入点；新增 §2.13.8（四步根因链、零重建 Kirikiroid2Preference.xml 已落盘 1,293 B sha256 aa4fa8ab…、标题菜单确定性序列 D-pad RIGHT→A 与 LEFT 会退出的陷阱、harness 步骤与「不用像素 diff」判据）；§8.2 标题 U1–U17、U5/U14 追加收窄说明、新增 U17（keymap 修复实际效果待测） | audit-engines |
| 2026-10-30 07:4x | **P2-2 关键达成记录**：新增 §2.13.9（RUN G：A1 自包含 NSP + keymap → `key:RIGHT` + A 进入 start.ks，run 目录/result.json/截图 size+sha256/k2s_log 时间线/60 FPS/0 exception；并记录 per-game XML 不被引擎覆写、「NSP vs NRO 鼠标差异」已被证伪——06:50 的 start.ks 来自人工注入而非 harness click、click 通道不可靠的原因此外 RUN H 组因同期清 SD 作废）；§8.2 标题改 U1–U20，回填 U2/U3/U4/U5/U6/U7/U17，新增 U18（A2 全新 SD 首启验收待跑）、U19（mouse_event 不可靠）、U20（存档写读回） | audit-engines |
| 2026-10-30 07:5x | 新增 §2.13.10 A2「全新 SD 首启解包」验收（Lead 的 run 20261030-073555，E1/E3 只读取证：28196 MiB free→23 文件/2737 MiB、mtime 跨度 ≈14.4 s、marker pilot01-r2、keymap XML 来自 payload、title.ks 07:40:47 / start.ks 07:42:36 / 0 exception；k2s_log 快照 sha256 `c0eb1c40…`）；§8.2 U18 由「待跑」改为 **PASS**（剩二次启动补证 + 真机 SD） | audit-engines |
| 2026-10-30 08:0x | 按 Lead m04088 确认补强 §2.13.10：A2 时间线（07:39:33 rm → 07:39:45 启动 → 07:40:47 title.ks → 07:42:36 start.ks）、输入方式=`citron_win.ps1 -Mode input -Vks 39,67` PostMessage（非 harness）、截图 sha256 清单、keymap 来源证据链（payload sha = 解包后 sha = `aa4fa8ab…`）；§8.1 标题 R1–R14、新增 R14（harness 多步 run 早退缺陷）；§8.2 U5 追加「B 无可见变化」、U18 追加「A2 二启补证 + 修复版 harness 复跑」 | audit-engines |
| 2026-10-30 08:1x | **A2 独立复跑（P2 收尾）**：新增 §2.13.11（audit-engines，R1 run 20261030-075524 / R2 run 20261030-075931：解包 23 文件 2,870,635,309 B ≈13.22 s、k2s 逐行仅时间戳差、title.ks 07:56:26→start.ks 07:58:13→@0000A_Z01.ks 07:58:16、二启 already extracted 48 s；截图 sha 跨进程不同的像素量化与判断、证据 P2e-* 22 文件）；§8.1 R14 补定位（调用方杀 bash 进程树 + 同步 spawnSync 规避）；§8.2 U18 追加二启与独立复跑 PASS、U20 追加 keymap 随 NSP 分发已实证；同步回填 docs/pilot/P2-acceptance.md §7 附录 + §6 新增 L10（截图哈希仅同进程可复现） | audit-engines |
