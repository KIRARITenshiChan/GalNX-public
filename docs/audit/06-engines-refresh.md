# 集群 F（刷新）：引擎移植与候选引擎 复审（只读）

- 审计日期: 2026-10-29
- 审计员: audit-engines（Team Lead: lead；共享任务 task-10）
- 方法: GitHub REST/GraphQL API（GH_TOKEN 经 cred_use 请求通道；api.github.com 在代理直连名单内）+ raw.githubusercontent.com 原文与 COPYING/LICENSE 文件经 env_download 下载（走 http://127.0.0.1:7897 代理）并落盘比对；所有 SHA、日期、许可证、release 资产、CI 配置均来自本轮实际抓取。未执行 git clone、未构建、未安装任何软件、未下载或打开任何商业游戏数据。REST 响应超过约 20,000 字符会被截断，长响应改用 GraphQL 精选字段或 raw 文件获取。
- 覆盖: 14 个条目（4 个新增候选：krkrsdl2 上游、Kirikiroid2-NX、ONScripter-jh-Switch、siglus_rs；10 个上轮对象的状态复核：krkr-ns、ONScripter-NX、rfvp、renpy/renpy、renpy/renpy-build、jvrcruzGAMES/RenpySwitch、knautilus/RenpySwitch、Otorhin/Ren2Switch、uyjulian/renpy-switch、jvrcruzGAMES/NXPython）

## 0. 结论先行（TL;DR）

1. **重大发现：krkrsdl2 上游本体已有官方 Switch 目标与 CI 出包**。CMakeLists.txt 有 `if(NINTENDO_SWITCH)` 分支（SWITCH_APP_NAME "Kirikiri SDL2"、SWITCH_AUTHOR "uyjulian"、SWITCH_VERSION "v2.0.0"、nacptool + elf2nro），.github/workflows/ci.yml 的 matrix 含 `switch`（container `devkitpro/devkita64:20241023`），release 标签 `latest` 下附 `krkrsdl2.nro`（12,011,585 B）。此前把 Switch 支持视为 krkr-ns fork 独有能力的判断需要更正：krkr-ns 是在上游之上叠加启动器/插件/音视频修复的下游增强。
2. **上游 NRO 是“单游戏内嵌”形态**：CMake 把 `EMBED_DATA_PATH`（默认 data/；CI 用 kag3 demo 的 data.xp3）symlink 进 RomFS 后打包，没有多游戏启动器。krkr-ns 的启动器、存档目录隔离、E-mote/AlphaMovie/LayerExRaster 是其增量价值；但 krkr-ns 标称实验性，且构建依赖仓库外工具目录（D:/KRKR-ns-tools、Switch.toolchain.cmake）与兄弟目录 WA2-ns。
3. **krkr-ns 的 v0.1.0 release 不能当不可变版本**：REST 返回 published_at 2026-09-14T15:08:56Z 早于 created_at 2026-10-16T13:43:28Z，tag target_commitish 指向当前 HEAD 949faf9a，NRO 资产 created_at 2026-10-16T14:07:43Z —— 说明 release/tag 被重新指向，版本锁定必须用 commit SHA + 自行重建。
4. **Ren'Py 官方仍以 8.5.3.26051504 为最新稳定**（commit 39895c1e017f0b36ffea2447d97eccd69d76ee1c，2026-05-16T01:14:41Z，SDL2 体系）；master 为 8.99.99 开发版（已迁 SDL3）；官方构建矩阵无 Switch，README 原文“Setup.py does not support cross-compiling”。4 个社区 Switch 移植与 NXPython 全部仍无 LICENSE（/license 404）→ 法律阻塞未解除，Ren'Py 继续不作为第一引擎。
5. **新增 3 个可用候选**：wetor/ONScripter-jh-Switch（GPL-2.0，221 stars，v21.2.1 于 2026-02-01，中文 UI + 游戏浏览器，NRO 16,735,572 B）、Erige005/Kirikiroid2-NX（KiriKiri 许可 BSD-style 非 SPDX，v1.0.1 2026-10-18，NRO 42,338,934 B，插件缺口）、xmoezzz/siglus_rs（MPL-2.0，125 stars，pre-release 含 NRO 14,531,824 B，deko3d 渲染）。
6. **ONScripter-NX 仍是 GPL-2.0、v0.3.1**（commit a8439a86393f74c503d28df176f010ca544af56f）；其 v0.3.1 release 资产内含月姬/歌月十夜游戏数据 zip（商业作品），只可作技术观察，禁止下载/用作测试数据。GPL-2.0 分发义务必须满足。
7. **接入排序修订**：第一梯队 **DrFlyingPig/krkr-ns**（MIT、有可直接安装的成品 NRO、启动器产品化，仍是第一款原型的首选）→ **krkrsdl2 上游自建**（MIT、官方 CI 出包、可复现，作为受控基线/无启动器场景的备选）；第二梯队 ONScripter 双实现（GPL-2.0，wetor/ONScripter-jh-Switch 活跃度与易用性更好）；第三梯队 Kirikiroid2-NX（非 SPDX 许可 + 依赖官方 APK 抽 UI 资产）；研究项 rfvp / siglus_rs；Ren'Py 暂缓（社区移植无许可证 + CPython 交叉为硬阻塞）。详见第 5 节。

## 1. 本轮状态差异表（相对 00–04 轮）

| 条目 | 上轮（00–04）已知 | 本轮实测（2026-10-29） | 变化 / 更正 |
| --- | --- | --- | --- |
| DrFlyingPig/krkr-ns | HEAD 949faf9a、v0.1.0、MIT、21 stars、release 时间戳矛盾 | HEAD 不变、22 stars、open issues 2；release 复核：tag=HEAD、NRO 29,576,369 B 上传于 2026-10-16T14:07 | 补充不可变性问题；构建依赖细节 |
| krkrsdl2/krkrsdl2 | 仅作为上游依赖出现，未单独成条 | **新增条目**：官方 Switch 目标/CI、MIT、latest release NRO 12,011,585 B dl16、latest 标签可变 | **重大新增/更正** |
| Erige005/Kirikiroid2-NX | 未覆盖 | **新增条目**：v1.0.1（e96b6034）、NRO 42.3 MB dl87、KiriKiri license | 新候选 |
| clamintus/ONScripter-NX | GPL-2.0、v0.3.1、37 stars | 状态未变；复核 COPYING 全文、release 资产（含商业游戏数据 zip） | 风险细化 |
| wetor/ONScripter-jh-Switch | 未覆盖 | **新增条目**：GPL-2.0、221 stars、v21.2.1（tag 15a6fec3→commit 573301c1，2026-02-01）、NRO 16,735,572 B dl914 | 新候选 |
| xmoezzz/rfvp | HEAD 9f07ade、MPL-2.0、152 stars、实验性 | 复核 Switch 构建链（build_switch.sh、自定义 target json、libnx runtime、软渲染 1280x720、仅 Ryujinx 跑过） | 细化 |
| xmoezzz/siglus_rs | 未覆盖 | **新增条目**：MPL-2.0、125 stars、pre-release 含 siglus-switch.nro 14,531,824 B | 新候选 |
| renpy/renpy | HEAD 98401410、8.5.3.26051504、MIT+LGPL | 复核 tag→commit 39895c1e（2026-05-16）、master 8.99.99 已迁 SDL3、无根 LICENSE | 版本锚定 |
| renpy/renpy-build | HEAD cff4919a | tag renpy-8.5.3.26051504→7bfab40c（2026-05-13）、tasks 47 项无 switch、无 license 文件 | 细化 |
| jvrcruzGAMES/RenpySwitch | HEAD 7824039a、无 license | 复核仍无 LICENSE/LICENSE.md/LICENSE.txt | 无变化 |
| knautilus/RenpySwitch | HEAD d361e44f、tag 7.6.3_1.0、无 license | 复核仍无 license | 无变化 |
| Otorhin/Ren2Switch | HEAD 5fce4a28、14 tags 最新 v1.7.5 | 复核仍无 license | 无变化 |
| uyjulian/renpy-switch | archived、HEAD 8a75ca3b | 复核仍 archived、仍无 license | 无变化 |
| jvrcruzGAMES/NXPython | HEAD 86cde186、无 license、CPython 3.14 补丁栈 | 复核 tags=0、releases=0、license null | 无变化 |

## 2. 条目详情

### 1. DrFlyingPig/krkr-ns

- URL: https://github.com/DrFlyingPig/krkr-ns
- 默认分支: `main`
- HEAD: `949faf9a874f54b149a3fe5382cfccb38afb99bb`，commit 日期 2026-10-16T13:43:28Z（pushed 2026-10-16T14:07:20Z）
- 最近 tag: `v0.1.0` → `949faf9a874f54b149a3fe5382cfccb38afb99bb`（与 HEAD 同一 commit；tag 日期按 commit 日期 2026-10-16；lightweight tag，无独立 tagger 时间）
- 最近 release: `v0.1.0`，published_at 2026-09-14T15:08:56Z，created_at 2026-10-16T13:43:28Z，target_commitish=949faf9a…，资产 krkrsdl2.nro 29,576,369 B（uploaded 2026-10-16T14:07:43Z，download_count 108）→ **时间戳互相矛盾，说明 tag/资产被后续重指或替换**。
- 对应引擎与版本范围: KiriKiri Z（krkrsdl2 基线 `bf207f2` + krkrz 基线 `b11c43a`；README 原文“移植基线 krkrsdl2 bf207f2 · krkrz b11c43a”），TJS2 + KAG/KAGEX；兼容实现参考 Kirikiroid2；面向 .xp3 打包的 KiriKiri2/Z 时代游戏；商业游戏兼容性未验证。
- 许可证: **MIT**（LICENSE 1,616 B：Copyright (C) Kirikiri SDL2 Developers，标准 MIT 条款；追加段落声明本仓库为 krkrsdl2 派生、沿用同一 MIT-style 许可；krkrz/FAudio/SDL2/simde/zlib/FreeType/libjpeg-turbo/libpng/libogg/libvorbis/libopus/jxrlib 等第三方保留各自许可；声明不分发商业游戏资源）。E-mote/AlphaMovie/LayerExRaster 的移植来源许可分别记录在 krkrsdl2/src/plugins/emoteplayer/UPSTREAM-LICENSE.txt、alphamovie/LICENSE.krkrsdl3、layerexraster/LICENSE.krkrsdl3。
- 健康: archived=false；stars 22、forks 0、open issues 2；releases 1；无 CI（根目录无 .github）；created 2026-09-07；disk 46,081 KB。
- 构建系统: CMake + Ninja 构建仓库内 vendored 的 krkrsdl2 树，入口 `build_nro.sh`（--no-patch / --no-emu-copy 开关），toolchain 用仓库外的 `$TOOLS/Switch.toolchain.cmake`（D:/KRKR-ns-tools），并假定 DEVKITPRO=D:/devkitPro。
- 关键依赖: devkitPro devkitA64 + libnx；Switch 依赖库（devkitPro portlibs）；CMake 3.31.6 / Ninja / pkg-config（来自外部 D:/KRKR-ns-tools）；**私有 FFmpeg 7.1 子集**（tools/build_ffmpeg_switch.sh：--target-os=horizon、--disable-network/GPL/version3/nonfree，demuxer=asf,mov,mpegps,mpegvideo,mp3，decoder=wmv3,vc1,wmav1,wmav2,wmapro,wmavoice,h264,aac,mpeg1video,mpeg2video,mp2,mp3，可执行程序来自兄弟目录 ../WA2-ns/out，归档默认 ../WA2-ns/out/ffmpeg-7.1.tar.xz，校验 sha256=40973d44970dbc83ef302b0609f2e74982be2d85916dd2ee7472d30678a7abe6）；.gitmodules 列 external/krkrz（krkrsdl2/krkrz）、external/simde、external/meson_toolchains、external/SDL、external/zlib、external/FAudio。
- 构建入口与产物: `build_nro.sh` → `build-switch/krkrsdl2.nro`；elf2nro 带 --icon=krkrsdl2/src/resources/nswitch/icon.jpg、--nacp、--romfsdir；RomFS 根放 krkrsdl2/data（startup.tjs 在归档根）+ compat-patches/system（E-mote motion.tjs 等兼容补丁）。需要 devkitPro；不需要额外密钥。
- README 声称: 原文“⚠️ 属实验性项目，难以保证稳定性 ⚠️”；启动器以 .xp3 为游戏入口，内置浅色游戏库 UI（手柄+触摸、预览图/头像/显示名、Names.tjs 别名、切换游戏只更新界面）；真机游戏路径不能包含中文（游戏目录、入口 .xp3 文件名、SD 路径必须 ASCII）；真机需完整内存模式（HBMenu 按住 R 启动已安装游戏再加载 NRO），模拟器直接加载；存档 sdmc:/switch/KRKR-ns/saves/<GameFolder>/、日志保留最近 3 份；已实现 KAG/KRKR 常见特性、多资源包、设置/选项/确认弹窗、快速存档、MenuItem 菜单、补丁/翻译优先加载、中/日字体、解密脚本、E-mote 动态立绘、AlphaMovie、原生 LayerExRaster、音频 WAV/OGG/Opus/部分 AAC/M4A/MP3、视频部分 WMV/MP4/MPEG（不支持变速与多音轨）、并行转场；目前必须 .xp3 入口（只有展开 startup.tjs 的不能启动）。
- 未验证 / 风险: ①release/tag 可变，v0.1.0 不是不可变版本；②构建依赖仓库外工具目录与兄弟仓库（WA2-ns）路径，仓库不自包含；③无 CI，构建可复现性未验证；④无真机验证（README 的“实验性”自述）；⑤中文路径限制属产品级硬限制（对中文 Galgame 目录影响大）；⑥E-mote/AlphaMovie 等第三方插件许可文件存在但未逐条复核全文。
- 来源 URLs: https://github.com/DrFlyingPig/krkr-ns ; https://github.com/DrFlyingPig/krkr-ns/blob/main/README.md ; https://github.com/DrFlyingPig/krkr-ns/blob/main/LICENSE ; https://github.com/DrFlyingPig/krkr-ns/blob/main/build_nro.sh ; https://github.com/DrFlyingPig/krkr-ns/blob/main/tools/build_ffmpeg_switch.sh ; https://api.github.com/repos/DrFlyingPig/krkr-ns/releases/tags/v0.1.0


### 2. krkrsdl2/krkrsdl2（重大更正：上游本体已官方支持 Switch）
- URL / 默认分支 / HEAD: https://github.com/krkrsdl2/krkrsdl2 · main · HEAD `124bdf841f09e7ce02aa99b7b55791a0f7a900ff`（committed 2026-10-01T03:11:23Z，pushed 2026-10-01T03:11:27Z）；REST 实测 default_branch=`main`、license=`MIT`（spdx_id=MIT）。GitHub 上另有 docs@59b58dec71（2026-09-18）、gh-pages@3bc175abfa（2025-01-18）与旧 master@a3a52ca6a0（2021-02-15）分支——旧 master 为 2021 遗留线，克隆/取证须用 main。
- 最近 tag: 仅 `latest`（旧 master 遗留）→ annotated tag `bf207f27d683834d35146736ec8d83d397ec75a2`；对应 release（prerelease，2026-08-31T04:23:14Z，由 github-actions[bot] 发布，标题 Latest development builds），资产含 `krkrsdl2.nro` 12,011,585 B（下载 16 次）
- 许可证: MIT（SPDX `MIT`）；文件 `LICENSE`（1,063B，Copyright (C) Kirikiri SDL2 Developers）；README 明确 src 目录 MIT、含第三方组件（非 GPL）。非 SPDX 内容仅出现在第三方目录，需按文件逐个核对
- 健康: archived=false；last push 2026-10-01；stars 438、forks 45、open issues 33、open PR 0；无 8.5.x 类发布节奏；语言构成 C++ 为主
- 构建系统 / 关键依赖: CMake（`CMakeLists.txt` 24,823B，769 行）+ 可选 meson（`meson.build`）；CI `.github/workflows/ci.yml`（20,719B）matrix 含 target `switch`，容器 `devkitpro/devkita64:20241023`，cmake 追加 `-DCMAKE_TOOLCHAIN_FILE=${DEVKITPRO}/cmake/Switch.cmake -DEMBED_DATA_PATH=data.xp3`，artifact 为 build/*.nro；CMakeLists L132 `if(NINTENDO_SWITCH)` 设 SWITCH_APP_NAME=Kirikiri SDL2、SWITCH_AUTHOR=uyjulian、SWITCH_VERSION=v2.0.0、SWITCH_RESOURCES_ROOT=src/resources/nswitch，L725 起用 nacptool/elf2nro 出 NRO；EMBED_DATA_PATH 默认带仓库内 data/。依赖 SDL2、SDL2_image（Zlib）、FFmpeg（LGPL）、FreeType、harfbuzz、fribidi、zlib、libpng、libjpeg-turbo、simde、OpenAL/FAudio 类音频（以 CMake 选项为准，未逐条展开）
- README 声称: README.md（1,347B）原文只写 Kirikiri SDL2 是 Kirikiri Z 的 SDL2 平台移植、可在支持 SDL2 的 macOS/Linux 运行；**完全未提及 Switch**；商用游戏原文「Running unmodified commercial games using this project is not supported. Please use Wine or Kirikiroid2 instead.」→ README 声称与仓库实际 CI/CMake 能力不一致，Switch 支持属「有实现、无文档」
- 未验证 / 风险: ①NRO 是单一内嵌数据（`-DEMBED_DATA_PATH=data.xp3`）构建，不带多游戏启动器；要跑自己的游戏必须以自有游戏数据重新构建或改用 krkr-ns 类启动器 fork；②README 未声明 Switch，官方支持无文档承诺，可能随时被 CI 移除；③旧 master 分支为 2021 遗留线（REST default_branch 实测为 main），取证须注意分支选择；④未在真机验证（本人只读审计，无 Switch 硬件）；⑤第三方组件与插件目录许可未逐文件复核
- 来源 URLs: https://github.com/krkrsdl2/krkrsdl2 ; https://github.com/krkrsdl2/krkrsdl2/blob/main/CMakeLists.txt ; https://github.com/krkrsdl2/krkrsdl2/blob/main/.github/workflows/ci.yml ; https://github.com/krkrsdl2/krkrsdl2/blob/main/LICENSE ; https://github.com/krkrsdl2/krkrsdl2/releases/tag/latest ; https://github.com/krkrsdl2/krkrsdl2/blob/main/README.md

### 3. Erige005/Kirikiroid2-NX（新候选，Kirikiroid2 1.3.9 移植）
- URL / 默认分支 / HEAD: https://github.com/Erige005/Kirikiroid2-NX · main · HEAD `e96b6034c292c6ccdb099823ab6a0a6b505f77f3`（committed 2026-10-18T17:27:29Z，pushed 同日 17:27:33Z；created 2026-09-30，很新）
- 最近 tag: `v1.0.1` → 同一 HEAD SHA `e96b6034c292c6ccdb099823ab6a0a6b505f77f3`；release v1.0.1 2026-10-18T17:01:12Z，资产 `Kirikiroid2-NX.nro` 42,338,934 B（dl 87）+ LICENSE.txt 44,184B + THIRD_PARTY_LICENSES.md 3,546B；此前 v1.0.0 2026-10-11、v0.1.2-alpha 2026-10-01、v0.1.1/0.1.0-alpha 2026-09-30
- 许可证: GitHub licenseInfo=NOASSERTION；文件 `LICENSE`（43,292B）= KiriKiri license（Copyright (c), W.Dee and contributors，日文三条款 BSD-style，允许再分发但须保留版权/条款/免责、二进制须在文档中附声明、未经书面许可不得用组织或贡献者名号推广派生品），文末另附 libjpeg-turbo 的 BSD 文本；非 OSI SPDX，机读块记 `NOASSERTION`；另有 `THIRD_PARTY_LICENSES.md` 逐组件列表
- 健康: archived=false；stars 18、forks 0、open issues 1、open PR 0；唯一维护者；无 CI 文件夹（构建全在 Linux/WSL2 脚本里）
- 构建系统 / 关键依赖: 非 CMake 主流程，脚本化：`platforms/switch/tools/` 下 setup_wsl_devkitpro.sh → fetch_cocos.sh（cocos2d-x 3.11.1 + Switch patches）→ fetch_lzma_sdk.sh（p7zip 16.02 + LZMA SDK 16.04）→ portlibs build_{libiconv,ffmpeg,opencv,unrar,libbpg,jxrlib,blend2d}.sh → extract_apk_assets.sh（从官方 1.3.9 APK 抽 UI 资源/图标）→ build_k2.sh → `kirikiroid2.nro`；工作区默认 `K2NX_WS=/mnt/d/Kirikiroid2-Switch`、repo 在 `$K2NX_WS/src`；依赖 devkitPro devkitA64+libnx、cocos2d-x 3.11.1、FFmpeg 3.2.19（LGPL-2.1-or-later，无 GPL 部分）、OpenCV 3.4.20（BSD-3）、libiconv 1.17（LGPL-2.1-or-later）、UnRAR 5.6.5（UnRAR license）、libbpg 0.9.8、jxrlib、Blend2D（zlib）
- README 声称: 原文「The first port of Kirikiroid2 to the Nintendo Switch」；基于 zeas2 原版 Kirikiroid2 1.3.9 源码（非重写）；v1.0.1 状态原文「Real games run from start to finish (video, voice, BGM, text, menus, transitions, saves). A few plugins and features are still missing」；要求 Atmosphère 任意机型、必须 title-takeover（启动游戏时按住 R）否则内存不足；NRO 放 sdmc:/switch/；游戏按 Android Kirikiroid2 结构放 sdmc:/kirikiri/<game>/（data.xp3）；只支持合法拥有的游戏。What works：TJS2、KAG/KAGEX 3、XP3（含 xp3filter.tjs）、auto path、patches；图片 PNG/JPEG/TLG/WebP/BPG/JPEG XR；字体 FreeType+游戏内 TTF；越/日/中文；音频 OpenAL（Ogg Vorbis/Opus/WAV/TCWF）；视频 FFmpeg 3.2；layerExImage/layerExDraw(Blend2D)/fstat/AlphaMovie .amv；性能 NEON blend、软件渲染下 CPU boost 官方 1785MHz（非超频）。Known issues：系统消息框 Yes/No 恒选第一个按钮；缺 KAGParserEx、E-mote/motion player、scriptsEx、layerExRaster、shrinkCopy、json、sqlite 等插件；退出可能报错；仅软件渲染
- 未验证 / 风险: ①极新（2026-09-30 创建）且单一维护者，长期维护风险高；②KiriKiri license 非 SPDX 标准，法律审阅成本高，且 LICENSE 42KB 含日文条款；③43MB NRO 体积大；④插件缺失对部分商业游戏是硬阻塞（E-mote 尤甚）；⑤构建需要从官方 APK 抽资源，复现依赖 zeas2 的 APK 分发；⑥未在真机验证（README 声称已完成流程，本人未复现）
- 来源 URLs: https://github.com/Erige005/Kirikiroid2-NX ; https://github.com/Erige005/Kirikiroid2-NX/blob/main/README.md ; https://github.com/Erige005/Kirikiroid2-NX/blob/main/LICENSE ; https://github.com/Erige005/Kirikiroid2-NX/blob/main/THIRD_PARTY_LICENSES.md ; https://github.com/Erige005/Kirikiroid2-NX/releases/tag/v1.0.1

### 4. clamintus/ONScripter-NX（复核，无状态变化）
- URL / 默认分支 / HEAD: https://github.com/clamintus/onscripter-nx · main · HEAD `a8439a86393f74c503d28df176f010ca544af56f`（committed 2026-01-14T18:46:39Z；与上一轮相同，未变化）
- 最近 tag: `v0.3.1` → HEAD 同一比提交 `a8439a86393f74c503d28df176f010ca544af56f`；release v0.3.1 2026-01-15T23:20:46Z；历史 release v0.3（2022-09-18）、v0.2（2022-01-23）、v0.1（2022-01-21）→ 4 个 release，2022 年后几乎停滞，2026-01 有一次性更新
- 许可证: GPL-2.0（`COPYING` 17,992B = GNU GPL Version 2, June 1991 全文；grep `or (at your option) any later version` 为 false → 判 `GPL-2.0-only` 更准确；机读记 `GPL-2.0`）；源码再分发与修改版分发须以 GPL 兼容条款开源并提供源码；release 包内嵌月姬/歌月十夜商业游戏数据——该数据版权不属 GPL，禁止再分发
- 健康: archived=false；last push 2026-01-15；stars 37、forks 3、open issues 0、open PR 0；无 CI；release 资产含 6 个 zip：onscripter-nx.zip 4,637,370 B（dl 60）、onscripter-nx-hd.zip 4,637,594 B（dl 76）、tsukihime.zip 6,076,415 B（dl 46）、tsukihime-hd.zip 6,079,243 B（dl 75）、kagetsu_tohya.zip 7,683,585 B（dl 30）、kagetsu_tohya-hd.zip 7,686,900 B（dl 47）
- 构建系统 / 关键依赖: 自写 `Makefile`（8,883B）+ `Makefile.extlibs`（873B，用于重建 SDL2_ttf 修 TTF_RenderUTF8_Shaded bug）；TARGET=onscripter-nx；APP_VERSION 0.3.1；CFLAGS 含 `-D__SWITCH__ -DUSE_OGG_VORBIS -DENABLE_1BYTE_CHAR -DFORCE_1BYTE_CHAR -DINSANI -DSDL2`、ENABLE_HD 开关；CXXFLAGS `-fno-rtti -fno-exceptions`；LDFLAGS `-specs=${DEVKITPRO}/libnx/switch.specs`；LIBS sdl2-config、smpeg2-config、-lSDL2_ttf -lSDL2_image -lfreetype -lharfbuzz -lbz2 -lz -lpng16 -lSDL2_mixer -lSDL2 -lvorbisidec；devkitPro 依赖：switch-dev、switch-sdl2、switch-sdl2_image、switch-sdl2_mixer、switch-sdl2_ttf、switch-smpeg2、switch-libvorbis；产物 `onscripter-nx.nro`（可选 APP_TITLEID）
- README 声称: 原文「A port of onscripter-20060724-insani-sdl2 to the Switch」，专为在新版 ONScripter 上会坏掉的老 NScripter 游戏；Tested games 只列 Tsukihime、Kagetsu Tohya（均为商业作品）；Features 4:3 模拟、触屏、RomFS、优化 flush；Controls 完整表；HD 模式自述「文字/内部图形更清晰、资源只缩放、偶发小 glitch、CPU 负担增加、输入略延迟、跳字变慢」；switch-sdl2_ttf 当时 broken（文字不显示），需 `make -f Makefile.extlibs` 重建
- 未验证 / 风险: ①GPL-2.0-only 对 GalNX 若闭源分发有传染性，需法务确认；②release 内嵌商业游戏数据，任何再分发/镜像都侵权，必须只在本地使用官方 zip 中的引擎部分；③switch-sdl2_ttf broken 的修复依赖 extlibs 补丁，devkitPro 版本漂移会复发；④无 CI，可复现性未验证；⑤HD 模式 CPU 负担在 Switch 上未量化；⑥本人未在真机验证
- 来源 URLs: https://github.com/clamintus/onscripter-nx ; https://github.com/clamintus/onscripter-nx/blob/main/README.md ; https://github.com/clamintus/onscripter-nx/blob/main/COPYING ; https://github.com/clamintus/onscripter-nx/blob/main/Makefile ; https://github.com/clamintus/onscripter-nx/blob/main/Makefile.extlibs ; https://github.com/clamintus/onscripter-nx/releases/tag/v0.3.1

### 5. wetor/ONScripter-jh-Switch（新候选，ONScripter Yuri 移植）
- URL / 默认分支 / HEAD: https://github.com/wetor/ONScripter-jh-Switch · master · HEAD `35f55c89b7b6b4e7997cc2a5a6e2afc4ef3e079a`（committed 2026-02-02T14:37:13Z，pushed 14:37:14Z；created 2019-10-02，非 fork）
- 最近 tag: `v21.2.1` → annotated tag `15a6fec3660aab33806c845e4fc47d20f2953a55`（tagger cai 2026-02-01T13:33:25Z，message「Release v21.2.1 - Fix CJK folder name display in game browser - Use UTF-8 text sizing to center CJK titles」）→ commit `573301c1e3c0ceffed33aae73acab9df95aaa076`（2026-02-01T13:31:14Z）；release v21.2.1 2026-02-01，资产 `ONScripter_Switch.nro` 16,735,572 B（dl 914）；另有 v21.2.0、v21.1.0（2026-01-17）、V2.0.2（2021-07-04）、V2.0（2021-07-03）、1.1fix、1.0 共 7 个 release
- 许可证: GPL-2.0（`LICENSE` 18,092B、`COPYING` 17,992B = GPLv2 全文；grep `or any later version` 为 false → `GPL-2.0-only` 更准确）；GPL 分发义务同条目 4；本仓库基于 YuriSizuku/OnscripterYuri（GPL-2.0）与 Ogapee 原版 ONScripter
- 健康: archived=false；last push 2026-02-02；stars 221、forks 9、open issues 1、open PR 1；有 `.github/workflows/build_switch.yml`；README 顶部 CI badge 指向上游 YuriSizuku/OnscripterYuri 的 build_switch.yml，但上游 workflows 只有 build_android/darwin/linux/web/win/win_msvc → badge 失效（本仓库自身 workflow 存在）
- 构建系统 / 关键依赖: `Makefile.switch`（8,129B）；TARGET=onsyuri；BUILD=build_switch；SOURCES src/onsyuri/{,renderer,simd,builtin_dll}；排除 AVIWrapper.cpp/simple_aviplay.cpp；APP_TITLE=ONScripter Yuri、APP_VERSION=1.0.0；ARCH `-march=armv8-a+crc+crypto -mtune=cortex-a57`；CFLAGS `-D__SWITCH__ -DSWITCH -DUSE_SDL2 -DUSE_GLES -DUSE_FILELOG`、CXXFLAGS `-fno-rtti -fno-exceptions -std=gnu++17`；LIBS SDL2_mixer/SDL2_image/SDL2_ttf/SDL2/vorbisidec/ogg/modplug/mpg123/opusfile/opus/png/jpeg/webp/freetype/harfbuzz/bz2/z/lua5.1/EGL/glapi/drm_nouveau/nx/m；ROMFS=romfs、elf2nro → `onsyuri.nro`；dkp-pacman 依赖 switch-dev、switch-sdl2、switch-sdl2_ttf、switch-sdl2_image、switch-sdl2_mixer、switch-liblua51、switch-freetype、switch-harfbuzz
- README 声称: 标题 ONScripter Yuri for Nintendo Switch，基于 OnscripterYuri 移植并针对 Switch 优化；特性：内置中文游戏浏览器、完美支持 Atmosphere、全中文 UI、触屏、ARM NEON SIMD、C++17、Lua 脚本、存档管理、复制即用；安装 onsyuri.nro → sdmc:/switch/；游戏放 sdmc:/onsemu/<name>/ 需 0.txt 或 00.txt（必需）+ arc*.nsa 等；**不支持中文文件夹名称**；系统要求破解机+Atmosphère+系统 9.0.0+；编译：clone https://github.com/YuriSizuku/OnscripterYuri.git（**写的是上游仓库而不是本仓库，复现歧义**）→ 打本仓库 Makefile.switch → `make -f Makefile.switch -j$(nproc)` → onsyuri.nro
- 未验证 / 风险: ①GPL-2.0-only 传染性（同条目 4）；②README 编译步骤 clone 的是上游仓库，直接照做会缺少 Makefile.switch 与 Switch 改动 → 复现歧义，需从本仓库取源码；③CI badge 失效暗示上游与 fork 关系松散；④仅软件渲染/GLES 混合依赖 EGL/glapi/drm_nouveau，devkitPro 包版本敏感；⑤中文文件夹名不支持（与 krkr-ns 同类硬限制）；⑥未在真机验证
- 来源 URLs: https://github.com/wetor/ONScripter-jh-Switch ; https://github.com/wetor/ONScripter-jh-Switch/blob/master/README.md ; https://github.com/wetor/ONScripter-jh-Switch/blob/master/Makefile.switch ; https://github.com/wetor/ONScripter-jh-Switch/blob/master/LICENSE ; https://github.com/wetor/ONScripter-jh-Switch/releases/tag/v21.2.1 ; https://github.com/YuriSizuku/OnscripterYuri

### 6. xmoezzz/rfvp（复核，Switch 目标仍为 experimental）
- URL / 默认分支 / HEAD: https://github.com/xmoezzz/rfvp · main · HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`（committed 2026-10-25T14:17:46Z，pushed 14:30:48Z；与上一轮相同）
- 最近 tag: `pre-release` → 同一 HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`（release 2026-10-25T14:30:48Z，isPrerelease=true，含 NRO 资产；注意 tag 名刻意用 pre-release，每次滚动发布）；稳定 tag `0.7.0` = `99435f22e94eaec27c0c1b9f22cc2a6b1910d7d1`（2026-10-19T06:12:39Z）；历史 0.6.0（2026-09-09）、0.5.0（2026-07-11）、0.4.0（2026-05-15）、0.3.0（2026-03-30，prerelease）
- 许可证: MPL-2.0（`LICENSE`，GitHub licenseInfo=MPL-2.0）；MPL 为文件级 copyleft：修改过的 MPL 文件须以 MPL 公开源码，可与闭源代码组合；需保留版权与许可声明
- 健康: archived=false；last push 2026-10-25；stars 152、forks 24、open issues 2（GraphQL 含 PR；open PR 2、merged PR 23）→ 纯 open issue 0；极活跃：2026 年 8 个 release
- 构建系统 / 关键依赖: Cargo workspace（`Cargo.toml` / `Cargo.lock`、`crates/`）+ Rust nightly（`platform/consoles/toolchain.env` 固定 `RFVP_CONSOLE_NIGHTLY`）；Switch 目标：`platform/switch/build_switch.sh`（2,972B）→ `target/rfvp-switch/switch/rfvp.nro`；`runtime/main.c` = libnx 运行时（进程循环/手柄与触摸/audren+audrv 音频/默认窗口 framebuffer/vsync 60fps），`host/` = Rust staticlib `rfvp-horizon` 0.1.0（license MPL-2.0，`crate-type=staticlib`，依赖 `rfvp` path、`no_std` feature、build-dep `cc 1`）；自定义 target `aarch64-nintendo-switch-rfvp.json`（arch aarch64、dynamic-linking=false、features +v8a,+neon,+crypto,+crc、llvm-target `aarch64-unknown-none`、os horizon、panic abort、PIE、tier 3、std=false，自定义 link script 把 .bss 放进 data 段）；cargo 参数 `--target ... -Zjson-target-spec -Zbuild-std=core,alloc,compiler_builtins`；链接 `-specs=${DEVKITPRO}/libnx/switch.specs -lnx -lm`；依赖 devkitPro（devkitA64+libnx+switch-tools）+ rustup + pinned nightly
- README 声称: 非官方 Rust 跨平台 FVP 引擎与 IDE 重实现，从零逆向重写、不含原作者源码；必须拥有正版、禁止分发游戏数据；License MPL-2.0。平台表原文：Switch = Standalone (.nro)、arch arm64-v8a、Status Experimental；Status 定义原文「Experimental (PS Vita, Switch): rfvp-psv and rfvp-horizon are the real console targets. They build on every change that touches them, and the core they run boots, plays and saves a real game in a desktop test host, but they have not been run on a console yet.」；ADR-0007 把 PS Vita 与 Switch 定为 primary mainstream console targets。`platform/switch/README.md` 原文「It runs in Ryujinx at 60 fps with picture and sound; it has not been run on a console yet.」，显示为软件光栅器 SoftRaster 渲染 1280x720 后缩放/letterbox 拷入 framebuffer（`RfvpRenderer` host API 后可替换 GPU 渲染器），存档 game/save/（rfvp_sNNN.bin + rfvp_global.bin，约每 2 分钟/存档后/退出时写，与桌面版编码不兼容），可选 nls.txt（sjis 默认/gbk/utf8）
- 未验证 / 风险: ①**从未在真机运行**（README 自述，仅 Ryujinx 60fps）；②无 GPU 渲染，软件光栅器在真机 CPU 负载未知；③Rust nightly + 自定义 target json + `-Zbuild-std` 对工具链版本敏感，nightly 漂移会破坏构建；④pre-release 是滚动 tag，不可复现锁定；⑤存档格式与桌面不兼容，迁移风险；⑥依赖用户自有 FVP 游戏，无免费 demo；⑦真机未验证音频（audren/audrv）延迟
- 来源 URLs: https://github.com/xmoezzz/rfvp ; https://github.com/xmoezzz/rfvp/blob/main/README.md ; https://github.com/xmoezzz/rfvp/blob/main/platform/switch/README.md ; https://github.com/xmoezzz/rfvp/blob/main/platform/switch/build_switch.sh ; https://github.com/xmoezzz/rfvp/blob/main/platform/switch/aarch64-nintendo-switch-rfvp.json ; https://github.com/xmoezzz/rfvp/blob/main/LICENSE ; https://github.com/xmoezzz/rfvp/releases/tag/pre-release

### 7. xmoezzz/siglus_rs（新候选，SiglusEngine 纯 Rust 重实现）
- URL / 默认分支 / HEAD: https://github.com/xmoezzz/siglus_rs · main · HEAD `5f358ef1360b0439e92aed2b749e8f25d8721954`（committed 2026-10-08T09:44:55Z，pushed 2026-10-26）
- 最近 tag: `1.0.0` → 同一 HEAD `5f358ef1360b0439e92aed2b749e8f25d8721954`（release 1.0.0 2026-10-08T09:46:15Z，**无 assets**）；真正带二进制的是同一 tag 上的 prerelease `pre-release`（2026-10-08T09:56:33Z），含 `siglus-switch.nro` 14,531,824 B（dl 12）以及 linux/macos/wasm/psvita/freebsd/windows/apk 产物
- 许可证: MPL-2.0（根目录 `LICENSE-MPL-2.0`；GitHub licenseInfo=MPL-2.0）；义务同条目 6（文件级 copyleft，修改文件须开源、保留声明）
- 健康: archived=false；last push 2026-10-26；stars 125、forks 20、open issues 1、open PR 3；created 2026-02-06，活跃
- 构建系统 / 关键依赖: Cargo workspace（`Cargo.toml` / `crates/`，Rust）+ Switch 平台脚本 `platform/switch/build_switch.sh` → `platform/switch/runtime/siglus_switch.nro`；`platform/switch/README.md`（3,703B）：复用 siglus_scene_vm 的 host/Scene VM/resource loader/script runtime/image manager/audio engine；libnx 接管 lifecycle/input/audio（`runtime/source/main.c`）；无 winit/wgpu 桌面依赖；渲染 `crates/siglus_scene_vm/src/render/horizon` 用 **deko3d** 替代 wgpu，shader 由桌面 WGSL 构建时经 shaderc/(naga 0.20) 转 GLSL、再由 devkitPro uam 编译进 RomFS；deko3d 调用在 `runtime/source/gpu.c`；部署 NRO → sdmc:/switch/siglus_rs/siglus_switch.nro，游戏 → sdmc:/switch/siglus_rs/game/；`package_game_nro.sh <game> <out.nro>` 可内嵌资源（优先 romfs:/game），>4GiB 需 exFAT，模拟器 32-bit buffer 限制时用 `--sdmc` 出 SD 部署包；游戏侧依赖 key.toml（二级密钥，README 称可暴力破解）+ 字符串加密 xor/none/mdl
- README 声称: UK2/AVG32/RealLive/SiglusEngine 的纯 Rust 重实现，主攻 SiglusEngine，**非商业研究用途**；平台表明确含 Nintendo Switch aarch64（另 PS Vita armv7、Linux x86_64/aarch64、FreeBSD x86_64、Windows x86_64/ARM64、macOS、iOS arm64/sim、Android arm64-v8a/x86_64、WASM），截图含 Anemoi for Nintendo Switch；运行 `cargo run --release -p siglus_scene_vm --bin siglus_engine -- --project-dir …`；文档 xmoezzz.github.io/siglus_rs
- 未验证 / 风险: ①README 未量化 Switch 真机状态，未声明真机通过（只给平台表与截图，截图来源未核实）；②deko3d 渲染路径与 shader 离线转换链（WGSL→GLSL→uam）是新代码，无 CI 产物可对照（release 的 NRO 是否由该路径构建未验证）；③1.0.0 无 assets、产物都在 pre-release，版本语义混乱；④游戏需自备正版 Siglus 数据，无免费 demo；⑤key.toml 密钥获取流程可能触及第三方工具，需合法自查；⑥MPL 文件级 copyleft 义务需保留；⑦未在真机验证
- 来源 URLs: https://github.com/xmoezzz/siglus_rs ; https://github.com/xmoezzz/siglus_rs/blob/main/README.md ; https://github.com/xmoezzz/siglus_rs/blob/main/platform/switch/README.md ; https://github.com/xmoezzz/siglus_rs/blob/main/LICENSE-MPL-2.0 ; https://github.com/xmoezzz/siglus_rs/releases/tag/pre-release
### 8. renpy/renpy（官方，复核：8.5.3 仍最新，无 9.0）
- URL / 默认分支 / HEAD: https://github.com/renpy/renpy · master · HEAD `98401410511152b98f2b38fecc942dc084f523eb`（committed 2026-10-29T03:38:36Z，pushed 2026-10-29T13:57:34Z；与上一轮相同）
- 最近 tag: `8.5.3.26051504` = annotated tag oid `3c707741828458ce41ee76cd7b5b688a48eead56`（tagger 2026-05-16T01:39:18Z，message「Tagging Ren'Py + 8.5.3.26051504 release.」）→ commit `39895c1e017f0b36ffea2447d97eccd69d76ee1c`（committed 2026-05-16T01:14:41Z）；对应 release published 2026-05-16T02:09:49Z，非预发布。**本轮确认无 8.6、无 9.0 发布**：releases totalCount 44，最近依次 8.5.3（2026-05-16）、8.5.2.26010301（2026-01-04）、8.5.1.25123106（2026-01-01）、8.5.0.25111603（created 2025-11-16）、8.4.1.25072401（2025-07-25）；tags top=8.5.3.26051504、8.5.3.26051401、8.5.3.26051007…
- 许可证: 主 SPDX `MIT`（GitHub licenseInfo=null、`/license` 404，**根目录无 LICENSE 文件**；许可证只存在于 `sphinx/source/license.rst` 与 https://www.renpy.org/doc/html/license.html）；license.rst 原文「Most of Ren'Py is covered by the terms of the following (MIT) license」，同时原文「Portions of Ren'Py are derived from source code that is licensed under the GNU Lesser General Public License, so Ren'Py games must be distributed in a manner that satisfies the LGPL.」→ 实际是 MIT 主体 + LGPL 部分；依赖清单含 LGPL（chardet、FFmpeg、Fribidi、libusb）、MPL-2.0（certifi）、Apache-2.0（requests、rsa）、Zlib（SDL2/SDL2_image/SDL2_ttf/freetype/tinyfiledialogs/zlib）、多 BSD、Python License；Generated Project Dedication：未修改的生成项目文件（game/gui.rpy、options.rpy、screens.rpy、script.rpy、game/gui 图片）为 CC0 1.0
- 健康: archived=false；last push 2026-10-29（当天）；stars 6,951、forks 957、open issues 251（含 48 PR → 纯 issue 203）；有 dependabot、无 CI workflow；分支：master（2026-10-29）、fix（2026-10-14）、大量 work/* 特性分支（如 work/andy_kl/pep-517-build-backend、work/andy_kl/remove-tfd、work/andy_kl/custom-mouse）
- 构建系统 / 关键依赖: Python + setuptools + Cython（官方明确不支持交叉编译）；`setup.py`（8.5.3 版，5,672B）用 pkg-config 找 libavformat/libavcodec/libavutil/libswresample/libswscale/harfbuzz/freetype2/fribidi/**sdl2**，library assimp/SDL2_image/SDL2/png/jpeg/z；C 扩展：_renpy、renpy.pygame.*（SDL2_rotozoom.c、SDL_gfxPrimitives.c、alphablit.c、write_png.c/write_jpeg.c）、renpy.audio.renpysound（src/renpysound_core.c + src/ffmedia.c）、renpy.text.ftfont（src/ftsupport.c + ttgsubtable.c）、renpy.text.bidi（src/renpybidicore.c）、assimp（src/assimpio.cc）；`pyproject.toml` requires-python `>=3.12.8,<3.13`、依赖 future/six/pefile/requests/rsa/chardet/websockets/pysocks/certifi/jinja2/truststore，dev 组 Cython>=3.3.0；`run.sh` 用 python setup.py build_ext --inplace 构建模块；**master 已迁 SDL3**（setup.py packages=`sdl3`、pyproject 无 build-system 段；README 仍写 SDL2）；README 原文「Setup.py does not support cross-compiling. See https://github.com/renpy/renpy-build for software that cross-compiles Ren'Py for many platforms.」
- README 声称: 官方支持平台为 Linux/macOS/Windows/Android/iOS/Web（README 枚举这些平台的构建方式，开发脚本假定 POSIX-like，Windows 需 MSYS）；依赖 apt 列表、SDL_image>=2.6、RENPY_CFLAGS/RENPY_LDFLAGS/RENPY_CC/RENPY_CXX/RENPY_LD 环境变量；README 不含 Switch
- 未验证 / 风险: ①官方无 Switch 目标、无交叉编译支持（README 明示）；②许可证只在文档文件里，无根 LICENSE，SPDX 扫描工具会报 NOASSERTION；③LGPL 部分对分发有合规义务（FFmpeg/chardet/Fribidi/libusb）；④master 正处 SDL2→SDL3 迁移，8.5.3 与 master 构建依赖不兼容（SDL2 vs SDL3），基线必须锁 8.5.3；⑤本人未在 Switch 验证任何 Ren'Py 运行时
- 来源 URLs: https://github.com/renpy/renpy ; https://github.com/renpy/renpy/blob/master/README.rst ; https://github.com/renpy/renpy/blob/master/sphinx/source/license.rst ; https://github.com/renpy/renpy/blob/master/setup.py ; https://github.com/renpy/renpy/blob/master/pyproject.toml ; https://github.com/renpy/renpy/releases/tag/8.5.3.26051504 ; https://www.renpy.org/doc/html/license.html

### 9. renpy/renpy-build（官方交叉构建系统，复核：仍无 Switch 后端）
- URL / 默认分支 / HEAD: https://github.com/renpy/renpy-build · master · HEAD `cff4919ae0ff9976470dbc1d78a1a3ec7fb6432f`（committed 2026-10-26T05:55:15Z，pushed 05:55:42Z；与上一轮相同）
- 最近 tag: `renpy-8.5.3.26051504` = annotated tag oid `0cacf3957d4194e29f01c2c5bbb39bb9060b463a` → commit `7bfab40c1174f622f644b24669afd5fb167fbb79`（committed 2026-05-13T04:17:01Z）；无 GitHub release（totalCount 0）
- 许可证: **无任何许可证文件**（GitHub licenseInfo=null、`/license` 404）；README 无明确 SPDX 声明 → 机读记空串 + license_notes 说明「无许可证文件，默认版权保留，不可再分发/修改」
- 健康: archived=false；last push 2026-10-26；stars 120、forks 85、open issues 16（含 9 PR → 纯 issue 7）；无 CI（`.github/` 为空）；仓库 558 MB（含锁定的第三方源码包）
- 构建系统 / 关键依赖: Python 构建编排器；`build.sh`（111B）= exec uv --project renpy run -m renpybuild（透传参数）；`prepare.sh`（2,227B）装 LLVM_MAJOR=22、clang-22、debootstrap、libsdl3-dev、libsdl3-image-dev、libav*/harfbuzz/freetype/fribidi、cmake、ninja、uv，解压 prebuilt/clang_rt.tar.gz，可选 nightly/ 环境；`build.py` 平台矩阵（README 原文表格）：linux x86_64/aarch64、windows x86_64、mac x86_64/arm64、android x86_64/arm64_v8a/armeabi_v7a、ios arm64/sim-x86_64/sim-arm64、web wasm——**无 switch/nx**；`tasks/` 47 个模块：**master 只有 sdl3.py/sdl3_image.py（SDL 3.4.18 + 下游补丁），8.5.3 tag 才是 sdl2.py/sdl2_image.py（SDL2 2.0.20 / SDL2_image 2.6.2）**；source/ 锁版本：Python-3.12.8.tar.xz（win 用 3.12.7 Setup.stdlib）、ffmpeg-4.3.1、freetype-2.13.3、fribidi-1.0.7、harfbuzz-8.0.1、libjpeg-turbo-1.5.3、libpng-1.6.43、zlib-1.3.1、openssl-3.3.2、brotli、bzip2、xz、nasm；`runtime/librenpython.c`（10,393B）用 PLATFORM 宏 `#ifdef LINUX / MAC / WINDOWS / IOS / WEB` 决定 Python home 布局与路径，**无 SWITCH 分支**；`tasks/python3.py` 走 autoconf/configure + config.site（ac_cv_file__dev_ptmx=no、ac_cv_file__dev_ptc=no），依赖 autoconf；`tasks/sysroot.py` 用 debootstrap Ubuntu jammy **glibc sysroot**（非 newlib）；`tasks/toolchain.py`：windows llvm-mingw-20241217、android NDK、mac MacOSX12.3.sdk、ios 需自备 iPhoneOS.sdk.tar.gz（缺则 RuntimeError）、web emsdk 5.0.2
- README 声称: 原文要求 **Ubuntu 24.04、部分流程必须 root、虚拟机建议、≥64 GB 磁盘、8 vCPU/16 GB RAM**；「Support for unofficial builds of Ren'Py will be limited.」；「The iOS build uses SDL 3.4.18 with a downstream scene-orientation patch. The current SDK inputs are iPhoneOS and iPhoneSimulator 27.1; the minimum deployment target remains iOS 15.0.」
- 未验证 / 风险: ①无 Switch 后端，独立移植需自写平台模块（Python home/paths/工具链/sysroot 全链路）；②官方明确「非官方构建支持有限」；③master 已完全 SDL3 化，与 8.5.3 的 SDL2 线分裂，锁版本时必须同一 tag 同时锁 renpy 与 renpy-build；④无许可证文件，法律状态不明；⑤构建要求 root/64GB/8vCPU，对普通开发机成本高；⑥未验证其在非 Ubuntu 环境（Windows/WSL2）的可运行性
- 来源 URLs: https://github.com/renpy/renpy-build ; https://github.com/renpy/renpy-build/blob/master/README.rst ; https://github.com/renpy/renpy-build/blob/master/build.sh ; https://github.com/renpy/renpy-build/blob/master/prepare.sh ; https://github.com/renpy/renpy-build/blob/master/tasks/python3.py ; https://github.com/renpy/renpy-build/blob/master/tasks/sysroot.py ; https://github.com/renpy/renpy-build/blob/master/runtime/librenpython.c ; https://github.com/renpy/renpy-build/tree/master/tasks
### 10. jvrcruzGAMES/RenpySwitch（社区 Ren'Py 8.3.4 移植，复核：仍无许可证）
- URL / 默认分支 / HEAD: https://github.com/jvrcruzGAMES/RenpySwitch · master · HEAD `7824039a7d0353b7bfa79ddfcecbf30a375d3d62`（committed 2026-08-10T19:16:50Z，pushed 19:17:04Z；与上一轮相同）；fork=true，parent knautilus/RenpySwitch
- 最近 tag: **none**（tags totalCount 0）；releases 0
- 许可证: **无**（GitHub licenseInfo=null；`/license` 404，LICENSE / LICENSE.md / LICENSE.txt 均为 null）→ 法律上默认版权保留，**禁止接入/再分发**
- 健康: archived=false；last push 2026-08-10；stars 2、forks 2、open issues 0；无真实社区；仓库 7,458 KB
- 构建系统 / 关键依赖: GitHub Actions（`.github/workflows/main.yml`，847B）+ Bash；容器 `devkitpro/devkita64:20230910`；`setup.bash`（6,371B）：RENPY_VER=8.3.4、PYGAME_SDL2_VER=2.1.0、python3 venv + Cython==3.0.10、git clone jvrcruzGAMES/NXPython（CPYTHON_REF=1b1c61a94f0685bb0be707b5374376f3084159fe）构建 libpython3.14.a 装入 devkitPro portlibs、dkp-pacman 装 switch-mesa/switch-glad/switch-libdrm_nouveau/switch-sdl2/switch-sdl2_gfx/switch-sdl2_image/switch-sdl2_mixer/switch-sdl2_ttf/switch-ffmpeg/switch-freetype/switch-curl/switch-mbedtls/switch-liblzma/switch-libzstd/switch-zlib/switch-bzip2 及 fribidi 包，下载 renpy-8.3.4-sdk.zip/source.tar.bz2、pygame_sdl2-2.1.0+renpy8.3.4.tar.gz，patch renpy.patch；`build.bash`（6,647B）用 venv cython 先构建 pygame_sdl2 与 renpy-source/module，再 source switchvars.sh、cmake 构建 `switch/build/renpy-switch.nso`，组装 raw/switch/{exefs,romfs}（romfs/Contents/{renpy.py,renpy/common}、lib.zip 含 python stdlib），最后 python generate_private.py；`switch/CMakeLists.txt`（9,044B）SWITCH_VERSION 8.3.4、REQUIRED pkg-config：egl/freetype2/glapi/glesv2/libav*/libdrm_nouveau/libsw*/sdl2/SDL2_gfx/SDL2_image/SDL2_mixer/SDL2_ttf/zlib，大量硬编码 /opt/devkitpro 路径；产物 main NSO + RomFS（另有 pack_nro.bash/pack_nsp.bash 出 NRO/NSP）
- README 声称: 原文「Build pipeline for Ren'Py on Nintendo Switch, powered by GitHub Actions and NXPython」；表格 Ubuntu 24.04 / devkitpro/devkita64 20230910 / Ren'Py SDK 8.3.4 / Python 3.14 (via NXPython) / Cython 3.0.10；6 步流程（下载源码→应用 Switch 补丁→Cython 编译→打包 lib.zip→交叉编译 NSO→组装空白工程）；要求 Linux（WSL2/Docker）
- 未验证 / 风险: ①**无许可证，法务红线，禁止任何形式的接入或再分发**；②基于 Ren'Py 8.3.4（非当前 8.5.3），且绑定 Python 3.14（NXPython），与官方 8.5.3 要求的 Python 3.12.8 不一致；③依赖 fork 的 NXPython（无许可证）；④CMakeLists 硬编码 /opt/devkitpro 路径，可复现性差；⑤本人未在真机验证
- 来源 URLs: https://github.com/jvrcruzGAMES/RenpySwitch ; https://github.com/jvrcruzGAMES/RenpySwitch/blob/master/README.md ; https://github.com/jvrcruzGAMES/RenpySwitch/blob/master/setup.bash ; https://github.com/jvrcruzGAMES/RenpySwitch/blob/master/build.bash ; https://github.com/jvrcruzGAMES/RenpySwitch/blob/master/switch/CMakeLists.txt ; https://github.com/jvrcruzGAMES/RenpySwitch/tree/master/.github/workflows

### 11. knautilus/RenpySwitch（社区 Ren'Py 7.6.3 移植，复核：仍无许可证）
- URL / 默认分支 / HEAD: https://github.com/knautilus/RenpySwitch · master · HEAD `d361e44fbf15cd1bda66d77cce74e29fc2a7f115`（committed 2025-06-21T22:10:45Z，pushed 2026-02-07T14:12:46Z）；fork=true，parent Otorhin/Ren2Switch
- 最近 tag: `7.6.3_1.0` → HEAD `d361e44fbf15cd1bda66d77cce74e29fc2a7f115`（唯一 tag）；release 1 个：名称「Renpy 7.6.3」，published 2025-06-21T22:42:38Z
- 许可证: **无**（licenseInfo=null、`/license` 404）→ 禁止接入
- 健康: archived=false；last push 2026-02-07；stars 6、forks 4、open issues 0；仓库 246 KB（纯构建管线）
- 构建系统 / 关键依赖: 与条目 10 同源（Otorhin/Ren2Switch 血统）；`setup.bash` / `build.bash` / `generate_private.py` / `link_sources.bash` / `renpy.patch` / `switch/` + CI；README（俄语）原文「Данный репозиторий служит сборщиком RenPy на Github Actions」；所用：ubuntu-24.04、devkitpro/devkita64:20230910、Ren'Py SDK **7.6.3**、Python **2.7**、pefile 2019.4.18、Cython 0.29.36、setuptools 0.9.8；renpy.patch 规模 **44 个文件 / 116 个 hunk**（Ren'Py 7.6.3 基线）
- README 声称: 俄语 README 说明其为 GitHub Actions 构建器；无平台功能宣称、无真机验证表述
- 未验证 / 风险: ①无许可证（禁止接入）；②Python 2.7 + Ren'Py 7.6.3，技术栈过时（官方已 8.5.x / Python 3.12）；③补丁规模大（44 文件/116 hunk），维护成本高；④本人未在真机验证
- 来源 URLs: https://github.com/knautilus/RenpySwitch ; https://github.com/knautilus/RenpySwitch/blob/master/README.md ; https://github.com/knautilus/RenpySwitch/blob/master/renpy.patch ; https://github.com/knautilus/RenpySwitch/releases/tag/7.6.3_1.0

### 12. Otorhin/Ren2Switch（社区 Ren'Py 7.6.1 移植，复核：仍无许可证）
- URL / 默认分支 / HEAD: https://github.com/Otorhin/Ren2Switch · master · HEAD `5fce4a28afaa1df262876b7bcce0bee10b3a0360`（committed 2023-09-04T22:05:13Z = pushed；与上一轮相同）；fork=true，parent uyjulian/renpy-switch
- 最近 tag: `v1.7.5` → commit `e41dfbe5ee77e9ad673bb4d2854f5983d5f05935`（2020-12-20T05:10:03Z）；共 14 个 tag（v1.0…v1.7.5），但 releases totalCount 0（tag 多、release 少）
- 许可证: **无**（licenseInfo=null、`/license` 404）→ 禁止接入
- 健康: archived=false；last push 2023-09-04；stars 12、forks 4、open issues 0；仓库 263 KB
- 构建系统 / 关键依赖: 与条目 10/11 同源；CI `.github/workflows/ci.yml`（744B）容器 `devkitpro/devkita64:20221113`；`setup.bash`（2,611B）：RENPY_VER=7.6.1、python2 pip（future/six/typing/requests/ecdsa/pefile==2019.4.18/Cython==0.29.36）、从 dl.otorh.in 下载空白工程骨架 rawproject.zip 与 python27-switch.tar.gz，从 renpy.org/dl/7.6.1 下载 SDK/source，patch renpy.patch；`build.bash` 全 python2，产物 raw/switch/exefs/main（renpy-switch.nso）+ romfs/Contents/{renpy.py,renpy/common,lib.zip}，最后 7z 打包 raw.zip；`switch/CMakeLists.txt`（7,920B）SWITCH_VERSION 7.6.1、INCLUDES python2.7、同一组 REQUIRED pkg-config 依赖
- README 声称: 无实质 README 表述（历史移植，Ren'Py 7.6.1 / Python 2.7）
- 未验证 / 风险: ①无许可证（禁止接入）；②Python 2.7 + Ren'Py 7.6.1，已完全过时；③2023 年后停更；④构建依赖作者自建域名 dl.otorh.in 分发资产，长期可用性风险；⑤本人未在真机验证
- 来源 URLs: https://github.com/Otorhin/Ren2Switch ; https://github.com/Otorhin/Ren2Switch/blob/master/setup.bash ; https://github.com/Otorhin/Ren2Switch/blob/master/build.bash ; https://github.com/Otorhin/Ren2Switch/blob/master/switch/CMakeLists.txt ; https://github.com/Otorhin/Ren2Switch/tree/master/.github/workflows

### 13. uyjulian/renpy-switch（历史移植，复核：仍 archived、仍无许可证）
- URL / 默认分支 / HEAD: https://github.com/uyjulian/renpy-switch · **landing**（默认分支；仓库已 archived）· HEAD `8a75ca3bd5f1c50612a33abae216ecf772b7d330`（committed 2022-01-04T04:13:35Z）
- 最近 tag: `v1.7.5` → commit `e41dfbe5ee77e9ad673bb4d2854f5983d5f05935`（2020-12-20T05:10:03Z，= Otorhin 同名 tag）；共 14 个 release（v1.0…v1.7.5），最新 v1.7.5 published 2020-12-20T05:16:10Z
- 许可证: **无**（licenseInfo=null、`/license` 404）→ 禁止接入
- 健康: **archived=true**；last push 2022-01-04；stars 70、forks 24、open issues 7；根目录只有 README.md（landing 分支为成品分支，非源码分发）
- 构建系统 / 关键依赖: 仓库不可构建（archived、根目录仅 README）；历史 release 提供二进制；README 原文「Sorry, this project is archived! Please use Switchroot Android with the official port of Ren'Py.」
- README 声称: 明确停止维护并推荐 **Switchroot Android + 官方 Ren'Py Android 构建** 的替代路线
- 未验证 / 风险: ①archived + 无许可证 = 不可用；②其推荐路线（Switchroot Android）值得作为「无需移植」的备选方案记录；③历史二进制在新固件兼容性未知
- 来源 URLs: https://github.com/uyjulian/renpy-switch ; https://github.com/uyjulian/renpy-switch/blob/landing/README.md ; https://github.com/uyjulian/renpy-switch/releases/tag/v1.7.5

### 14. jvrcruzGAMES/NXPython（CPython 3.14 Switch 移植，社区 Ren'Py 移植的运行时依赖）
- URL / 默认分支 / HEAD: https://github.com/jvrcruzGAMES/NXPython · main · HEAD `86cde186653a89593359bd59102ed2b878c6fa5b`（committed 2026-08-09T00:58:47Z，pushed 22:35:16Z；created 2026-08-09，极新）
- 最近 tag: **none**（tags 0、releases 0）
- 许可证: **无**（licenseInfo=null；根目录无 LICENSE）→ 禁止接入；CPython 自身 PSF 许可不覆盖本仓库新增的补丁文件与构建脚本
- 健康: archived=false；stars 0、forks 0、open issues 0；仓库 78 KB（patch 仓库）
- 构建系统 / 关键依赖: 只跟踪补丁与脚本；`CPYTHON_COMMIT` = `1b1c61a94f0685bb0be707b5374376f3084159fe`；`patches/0001-nxpython-cpython-3.14.patch` = 299,892 B（对官方 CPython 3.14 的补丁栈）；`build.sh`（4,240B）克隆/拉取 CPython 指定 commit、打补丁、用 devkitA64 构建；命令 DEVKITPRO=/opt/devkitpro DEVKITA64=/opt/devkitpro/devkitA64 PATH=/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin:$PATH ./build.sh -j 8；参数透传 CPython 的 Platforms/NX/build-portlibs.sh（--destdir 可选）；产物静态 libpython3.14.a 安装进 devkitPro portlibs。补丁证据：让 `sys.platform == 'nx'`，并给 posixpath 增加 `romfs:` / `sdmc:` 挂载根语义（原文示例：posixpath.splitroot('sdmc:/switch/python') -> ('sdmc:', '/', 'switch/python')）
- README 声称: 原文「NXPython keeps the Nintendo Switch CPython port outside the CPython checkout. This repository tracks patch files only; CPython itself is downloaded into ignored working directories.」；仅说明跟踪补丁、需 devkitPro 构建
- 未验证 / 风险: ①**无许可证**（禁止直接使用其补丁产物，仅可作为「CPython 能在 Switch 上构建」的存在性证据）；②仅单一补丁文件，未在真机验证；③固定 CPython 3.14 而 Ren'Py 8.5.3 要求 Python 3.12.8 → 版本不匹配，不能直接复用；④sys.platform='nx' 与 Ren'Py 平台判定不兼容（Ren'Py 无 nx 分支）
- 来源 URLs: https://github.com/jvrcruzGAMES/NXPython ; https://github.com/jvrcruzGAMES/NXPython/blob/main/README.md ; https://github.com/jvrcruzGAMES/NXPython/blob/main/build.sh ; https://github.com/jvrcruzGAMES/NXPython/blob/main/CPYTHON_COMMIT
## 3. 更正表（本轮对既有审计的更正）

| # | 前轮记录（01/04） | 本轮实测 | 影响 |
| --- | --- | --- | --- |
| C1 | 01 与 04 均未记录 krkrsdl2 上游支持 Switch | krkrsdl2 **CMakeLists 有 NINTENDO_SWITCH 分支、CI 有 switch target、release latest 附 12MB NRO**（作者 uyjulian） | 上游本体即可作为候选；但由于 NRO 内嵌单一 data.xp3、README 不提 Switch，仍以 krkr-ns（启动器）为第一款 |
| C2 | 01 将 krkr-ns 描述为唯一 KiriKiri Switch 路径 | 新增 Kirikiroid2-NX（Kirikiroid2 1.3.9 移植，KiriKiri license，42MB NRO，2026-09-30 新建） | KiriKiri 路线有两个独立实现可对照；但 K2NX 许可证非 SPDX、极新、插件缺失 |
| C3 | 04 未把 Ren'Py master 与 8.5.3 的 SDL 代际分开 | **8.5.3 用 SDL2；master（8.99.99）已全面 SDL3**；renpy-build 同 tag 也是 SDL2 | 移植基线必须锁定 renpy 8.5.3.26051504 + renpy-build renpy-8.5.3.26051504，禁止用 master |
| C4 | 01/04 记 ONScripter-NX 为唯一 ONScripter Switch 实现 | 新增 wetor/ONScripter-jh-Switch（ONScripter Yuri 移植，GPL-2.0，NRO 16.7MB，v21.2.1 2026-02-01，stars 221） | ONScripter 路线有更新、更活跃的实现；两者均 GPL-2.0，二选一即可 |
| C5 | 01/04 记录 4 个社区 Ren'Py 移植「无许可证」 | 本轮逐一复核 LICENSE / LICENSE.md / LICENSE.txt 与 /license：**全部仍无许可证**，NXPython 亦无 | 法律阻塞未解除，社区 Ren'Py 移植继续禁止接入 |
| C6 | 01 未提 Siglus / FVP 之外的引擎族 | 新增 xmoezzz/siglus_rs（SiglusEngine Rust 重实现，MPL-2.0，有 siglus-switch.nro 14.5MB，deko3d 渲染） | Siglus 系游戏第一次有 Switch 原生路径（实验性） |
| C7 | rfvp 记为「仓库称 Switch experimental」 | 复核 README 与 platform/switch/README：**明确自述从未在真机运行、仅 Ryujinx 60fps** | 维持研究项，不进入第一款依赖 |
| C8 | 01 记 krkr-ns release v0.1.0 published 2026-09-14 | REST 实测 release **created_at 2026-10-16T13:43:28Z 晚于 published_at 2026-09-14T15:08:56Z**（GitHub 时间线矛盾，资产 created 2026-10-16T14:07:43Z） | 版本锁定不能只信 release 名，需同时锁 commit SHA（949faf9a…） |

## 4. 可复现构建前置条件矩阵（Ren'Py 与已存引擎）

| 仓库 | 工具链 | 子模块 / 外部资产 | 需要密码学/密钥 | 需要 devkitPro | 产物 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| DrFlyingPig/krkr-ns | CMake/Ninja + devkitA64 + FFmpeg 7.1 私有子集（build_ffmpeg_switch.sh） | external/krkrz、simde、meson_toolchains、SDL-upstream、zlib、FAudio（.gitmodules 6 个）；**仓库外工具目录 /d/KRKR-ns-tools（cmake 3.31.6、ninja、pkgconf）+ 兄弟仓库 WA2-ns/out（ffmpeg 归档、msys make）** | 否（解密脚本能力随引擎，不含密钥） | 需（默认 D:/devkitPro） | build-switch/krkrsdl2.nro | 不自包含；无 CI；release NRO 29.6MB（dl 108） |
| krkrsdl2/krkrsdl2 | devkitpro/devkita64:20241023 容器 + CMake/Ninja | CI 下 data.xp3 示例从 krkrsdl2-kag3-demo release 下载；EMBED_DATA_PATH 指向自有游戏数据 | 否 | 需 | build/*.nro（发布 12.0MB） | 官方 CI 可复现，但产物是单游戏内嵌 |
| Erige005/Kirikiroid2-NX | devkitA64 + WSL2/Linux 脚本 | cocos2d-x 3.11.1、p7zip/LZMA SDK、OpenCV、libbpg、jxrlib、Blend2D、libiconv、unrar **均需脚本下载/构建**；UI 资源从官方 1.3.9 APK 抽取（不在仓库） | 否 | 需 | kirikiroid2.nro 42MB | 构建链最重（8 个 portlibs 脚本） |
| clamintus/ONScripter-NX | devkitA64 Makefile | switch-smpeg2、switch-libvorbis、switch-sdl2*；SDL2_ttf 需 extlibs 重建 | 否 | 需 | onscripter-nx.nro | 无 CI；release 含商业游戏数据（禁用） |
| wetor/ONScripter-jh-Switch | devkitA64 + Makefile.switch | switch-liblua51、switch-harfbuzz 等 dkp 包 | 否 | 需 | onsyuri.nro | README 编译步骤 clone 上游仓库，需改用本仓库源码 |
| xmoezzz/rfvp | devkitA64+libnx+switch-tools + rustup pinned nightly | 自定义 target json、-Zbuild-std；工具链版本由 toolchain.env 锁定 | 否 | 需 | target/rfvp-switch/switch/rfvp.nro | 无 GPU 渲染；从未真机 |
| xmoezzz/siglus_rs | devkitA64 + Rust + deko3d + shaderc/naga 0.20 + WGSL→GLSL 离线转换 | platform/switch 构建脚本；游戏需 key.toml | 游戏侧需 key.toml（二级密钥） | 需 | siglus_switch.nro | 渲染链最新、未真机验证 |
| renpy/renpy + renpy-build（官方基线 8.5.3.26051504） | Ubuntu 24.04 + root + LLVM 22 + debootstrap + uv；CPython 3.12.8 需 autoconf 构建 | renpy-build source/ 锁定 Python 3.12.8、SDL2 2.0.20、FFmpeg 4.3.1 等（自动下载） | 否 | **官方流程不需要，但需自写 Switch 后端** | SDK/桌面二进制（官方平台矩阵无 Switch） | 交叉编译支持官方声明有限；setup.py 不支持交叉编译 |
| 社区 Ren'Py 移植（jvrcruz） | devkitpro/devkita64:20230910 容器 | Ren'Py 8.3.4 SDK/source、pygame_sdl2 2.1.0、NXPython 补丁构建 CPython 3.14 | 否 | 需 | main NSO + RomFS → NRO/NSP | 无许可证，仅参考 |

## 5. 第一款原型接入排序（修订）

### 5.1 结论：仍选 DrFlyingPig/krkr-ns 作为第一款原型；RenpySwitch 出局

| 维度 | krkr-ns | jvrcruzGAMES/RenpySwitch | 判定 |
| --- | --- | --- | --- |
| 许可证 | MIT（LICENSE 1,616B，明确本仓库为 krkrsdl2 派生、同 MIT） | **无任何许可证**（/license 404） | krkr-ns 胜，RenpySwitch 不可用 |
| 维护活跃 | HEAD 2026-10-16（当月）、release v0.1.0 + NRO 资产（dl 108）、近期提交集中在音频/纹理/内存修复 | HEAD 2026-08-10、stars 2、无 release 二进制 | krkr-ns 胜 |
| 文档完整 | README 11.5KB：安装/路径限制/构建/架构/已实现/许可全覆盖 | README 有流程表但无产物发布、无真机说明 | krkr-ns 胜 |
| 构建明确性 | build_nro.sh + build_ffmpeg_switch.sh 可读，但依赖仓库外 tools 与 WA2-ns | CI 完整（GitHub Actions 一条流水线），但依赖无许可证的 NXPython | 平（各有可复现性缺口） |
| 引擎成熟度 | 基于 krkrsdl2 bf207f2 + krkrz b11c43a，已实现 E-mote/AlphaMovie/LayerExRaster/视频解码 | Ren'Py 8.3.4，Python 3.14 交叉，功能面广但未发布 | krkr-ns 略胜（有可下载成品） |
| 法律风险 | MIT + 第三方保留许可 | 无许可证 = 硬阻塞 | krkr-ns 胜 |

**排序建议（修订）**：1) **krkr-ns**（第一款原型，MIT、有成品 NRO、基于活跃上游）；2) **krkrsdl2 上游自建**（若要完全可控、无 launcher，用官方 CI 方式以自有 data.xp3 构建）；3) **ONScripter-jh-Switch 或 ONScripter-NX**（老 NScripter 库覆盖，GPL-2.0 需接受传染性，二选一，优先 jh 因其更活跃且有 2026-02 更新）；4) **rfvp / siglus_rs**（研究项，均未真机，不进首批）；5) **Ren'Py 独立移植**（长期项目，需先解 CPython 交叉硬阻塞）；6) 社区 Ren'Py 移植（jvrcruz/knautilus/Otorhin/uyjulian）与 NXPython **禁止接入**（无许可证）。

### 5.2 krkr-ns 作为第一款的具体入口
- 构建入口：仓库根 `build_nro.sh`（4,239B）→ `build-switch/krkrsdl2.nro`；FFmpeg 依赖由 `tools/build_ffmpeg_switch.sh`（5,027B）产出 ffmpeg 7.1 私有子集（sha256 40973d44…）；工具目录通过 `KRKRNS_TOOLS` 指定（默认 /d/KRKR-ns-tools），DEVKITPRO 默认 D:/devkitPro。
- 直接用发布产物：release v0.1.0 的 `krkrsdl2.nro`（29,576,369 B，dl 108）→ 放 sdmc:/switch/KRKR-ns/，游戏放 sdmc:/switch/KRKR-ns/Game/<ASCII 目录>/，真机需在 HBMenu 按住 R 启动（完整内存）。
- 硬限制：Switch 真机路径不能含中文（游戏目录/入口 .xp3 文件名/SD 路径均需 ASCII）；必须 .xp3 入口；不支持只有展开 startup.tjs 的游戏。

## 6. 可用于测试的合法资源候选（仍需用户核实）

| # | 资源 | 出处 | 许可证/条款 | 适用引擎 | 风险与核实点 |
| --- | --- | --- | --- | --- | --- |
| T1 | **KAG3 demo project（data.xp3）** | https://github.com/krkrsdl2/krkrsdl2-kag3-demo（release/CI 产出） | README 原文「デモンストレーションプロジェクトのライセンスはKAG3と同じ」；KAG3 repo README 原文「Copyright (C)2001-2009, W.Dee and contributors 改変・配布は自由です」（修改/分发自由，**非 OSI/SPDX 许可**） | krkrsdl2 / krkr-ns | demo 内嵌字体为「梅ゴシックO5」(Ume Gothic O5)，字体许可需单独核实；KAG3 仓库无 LICENSE 文件；分发前需法律确认 |
| T2 | **自建 Ren'Py 工程** | 用官方 SDK 新建项目，或 renpy/renpy 的 launcher/tutorial 模板 | license.rst「Generated Project Dedication」：未修改的生成项目文件（game/gui.rpy、options.rpy、screens.rpy、script.rpy、game/gui 图片）为 **CC0 1.0**；引擎本身 MIT + LGPL 部分 | Ren'Py（PC 先验证；未来 Switch 移植） | 若修改生成文件则不再适用 CC0 声明；引擎分发需满足 LGPL |
| T3 | **Ren'Py 官方 SDK 示例 the_question / tutorial** | https://github.com/renpy/renpy/tree/master/the_question 、/tutorial | **未单列资产许可**；license.rst 只覆盖引擎与生成项目文件 | Ren'Py（仅内部技术验证） | 资产（图片/音频/剧本）无明确再分发许可 → **仅本地测试、禁止再分发**，需用户核实 |

不推荐为测试资源：ONScripter-NX release 内嵌的月姬/歌月十夜（商业作品，禁止使用）；rfvp/siglus_rs/K2NX 均需用户自有正版游戏（无内置 demo）。

### 6.1 已排查但未入选的候选（筛查理由）

本轮除 4 个新增候选（krkrsdl2 上游、Kirikiroid2-NX、ONScripter-jh-Switch、siglus_rs）外，还按 task-10 第 6 项要求排查了 TyranoScript、Artemis、SiglusEngine 其他实现、Majiro、QLIE、Ethornell/BGI、NScripter 生态与其他 KiriKiri Switch 项目。下表全部为本轮 GitHub 搜索/GraphQL 实测结果（日期为 UTC），结论是「不进入 GalNX 主路线」。

| 候选 | 实测状态 | 未入选理由 |
| --- | --- | --- |
| ShikemokuMK/tyranoscript | 538 stars；HEAD c8dbfd492afd3d79b0954fcf4477236f5c6c4830（2026-02-18）；NOASSERTION，LICENCE.txt 3,698B 为自定义 freeware 条款（禁止再配布引擎本体、禁止作为手机转换商材），非 OSI SPDX；0 releases | JS/Web 引擎，无原生 Switch 运行时；自定义许可禁止再分发本体 |
| YuriSizuku/OnscripterYuri | 859 stars；GPL-2.0；HEAD 08f744b3（2026-06-23）；24 releases，最新 v0.7.7beta（2026-06-23） | 上游平台 windows/linux/mac/android/retroarch/psv 无 switch；Switch 移植由 wetor 仓库（第 5 条）承担，不重复接入 |
| krkrz/krkrz | 957 stars；NOASSERTION（LICENSE 43,292B = KiriKiri license）；HEAD fd5c4baa（2021-05-26），push 2024-03-24 | 官方 KiriKiri Z 已停滞；Switch 侧以 krkrsdl2（MIT）及其下游为准 |
| uyjulian/krkrs | archived；70 stars；HEAD 4374dd08（2022-10-27） | README 原文「Archived; multi-platform development has moved to Kirikiri SDL2」 |
| AetherKiri/Aether | GPL-3.0；Godot4 多运行时 | 无官方 Godot Switch 导出，不可行 |
| reAAAq/KrKr2-Next | Flutter+ANGLE | 面向移动端，非 Switch |
| Weiss-UltimateSavior/Tyranor-Next | 755 stars；GPL-2.0 | Android 多引擎启动器，非 Switch |
| vnovel-engine/krkrsdl2 | MIT；libretro fork，2026-10-26 仍活跃 | fork 无 Switch 增量，价值已被上游 krkrsdl2 覆盖 |
| xb65478/krkrsdl2-web | MIT；web 改造 | 同上（无 Switch 增量） |
| weimingtom/krkrsdl2-miyoo-a30 | MIT；Miyoo 掌机移植 | 同上（无 Switch 增量） |
| Galladite27/ONScripter-EN | GPL-2.0；120 stars；2026-01-26 | 无 Switch 目标；ONScripter 路线已由 clamintus/wetor 两仓覆盖 |
| ogapee/onscripter | GPL-2.0；57 stars；HEAD 848a6089（2023-08-29） | 上游本体，无 Switch 目标 |
| Tnt6n2/SiglusEngine | 无许可证；解包/工具立场 | 无许可不可接入；Siglus 路线以 MPL-2.0 的 xmoezzz/siglus_rs 为准 |
| OWCramer/ArtemisKit | MPL-2.0；Swift/iOS | 非 Switch；Artemis 引擎无 Switch 实现 |
| DeQxJ00/Art3m1sPSV | Artemis 引擎 PS Vita runner，2026-10-28 活跃 | 仅 PS Vita，无 Switch 目标 |

Majiro、QLIE、Ethornell/BGI 三个引擎：本轮搜索仅见格式资料与解包工具，未发现可核验的 Switch 原生运行时或移植仓库 → 记为「未发现候选」（属本轮未取得证据，不等于否定其存在）。

## 7. 未验证 / 失败项

| # | 项 | 状态 | 说明 |
| --- | --- | --- | --- |
| U1 | 所有 NRO / NSP 的真机运行 | **未验证** | 只读审计，无 Switch 硬件；本文件所有「能跑」均为 README 声称或模拟器声称 |
| U2 | Ren'Py 独立移植可行性 | **未验证（推断）** | CPython 3.12.8 交叉到 devkitA64/newlib 未验证；renpy-build 无 Switch 后端；Ren'Py 平台判定无 switch 分支 |
| U3 | switch-sdl3 在 devkitPro 的可用性 | **未验证** | 若未来追 Ren'Py master（SDL3），需确认 devkitPro 是否提供 switch-sdl3；8.5.3 用 SDL2，暂时规避 |
| U4 | krkrsdl2 上游 Switch 支持的文档承诺 | **未验证** | README 不提 Switch，仅 CMake/CI 有；可能被移除且无公告 |
| U5 | siglus_rs Switch 渲染链 | **未验证** | deko3d + WGSL→GLSL→uam 管线是否与 release 的 NRO 一致未核实；README 未声明真机通过 |
| U6 | K2NX release 流程 | **未验证** | README 声称 real games run start to finish；本人未复现，插件缺失清单仅来自 README |
| U7 | 中文路径限制的精确范围 | **部分验证** | krkr-ns README 与 onsjh README 均自述限制；未在各仓库代码层定位具体失败点 |
| U8 | Ren'Py 示例资产许可 | **未验证** | the_question/tutorial 无 LICENSE 文件，license.rst 未单列 → 只能标记需用户核实 |
| U9 | renpy/renpy 8.5.3 实际版本字符串 | **未验证** | pyproject/setup.py 中 version 仍写 8.99.99（开发占位），未取 vc_version.py；以 release tag 8.5.3.26051504 为准 |
| U10 | 第三方组件许可全文 | **部分验证** | 各仓库 THIRD_PARTY / LICENSE 清单已读，但未逐组件比对原始许可文本（如 KAG3 字体、Blend2D、libbpg） |

## 8. 对 GalNX 的建议（版本锁定 / 接入顺序 / 阻塞项）

1. **版本锁定（唯一可复现基线）**：krkr-ns → commit `949faf9a874f54b149a3fe5382cfccb38afb99bb`（2026-10-16，release v0.1.0 资产）；krkrsdl2 上游 → `124bdf841f09e7ce02aa99b7b55791a0f7a900ff`（main，2026-10-01）或 CI 容器 devkitpro/devkita64:20241023；ONScripter-NX → `a8439a86393f74c503d28df176f010ca544af56f`（v0.3.1）；ONScripter-jh → `35f55c89b7b6b4e7997cc2a5a6e2afc4ef3e079a`（v21.2.1）；rfvp → `9f07adef2eb5d559777f9bf59a67b756875cb24f` + 对应 nightly（toolchain.env）；siglus_rs → `5f358ef1360b0439e92aed2b749e8f25d8721954`；Ren'Py 官方 → renpy `8.5.3.26051504`（commit 39895c1e…）+ renpy-build `renpy-8.5.3.26051504`（commit 7bfab40c…），**禁止用 master（SDL3）**。
2. **接入顺序（修订）**：krkr-ns（原型 1）→ krkrsdl2 上游自建（可控构建）→ ONScripter-jh-Switch 或 ONScripter-NX（老库覆盖，GPL 需接受）→ rfvp/siglus_rs（研究）→ Ren'Py 独立移植（长期，先解 CPython 交叉）。社区 Ren'Py 移植与 NXPython **一律不接入（无许可证）**。
3. **授权测试资源**：首选 T2 自建 Ren'Py 工程（CC0 生成文件最干净），其次 T1 KAG3 demo（自定义「自由修改/分发」条款，需法律确认字体），T3 官方 SDK 示例仅内部测试。
4. **阻塞项**：①Ren'Py 独立移植的 CPython 交叉（唯一硬阻塞，建议 4–6 周 go/no-go 探针）；②KiriKiri license（K2NX）与 GPL-2.0（两个 ONScripter）的法务判定；③无真机验证（需用户提供硬件/或在报告中标注为未验证）。
5. **建议 Lead 在合并索引时**：把 krkrsdl2 上游官方 Switch 支持、Kirikiroid2-NX、ONScripter-jh-Switch、siglus_rs 作为**新增候选**收录；把「Ren'Py 基线锁 8.5.3（SDL2）」作为 04 的补充约束；更正「krkr-ns 是唯一 KiriKiri Switch 路径」的表述。

## 9. 本轮覆盖与条目映射
- 本文件覆盖 14 个条目：krkr-ns、krkrsdl2（上游）、Kirikiroid2-NX、ONScripter-NX、ONScripter-jh-Switch、rfvp、siglus_rs、renpy/renpy、renpy/renpy-build、jvrcruzGAMES/RenpySwitch、knautilus/RenpySwitch、Otorhin/Ren2Switch、uyjulian/renpy-switch、jvrcruzGAMES/NXPython。
- 与 00–04 的关系：本文件是「刷新 + 新增候选」，不修改 00–04 既有记录；差异与更正见第 3 节。

<!-- AUDIT-JSON-BEGIN -->
```galnx-audit
[
  {
    "name": "DrFlyingPig/krkr-ns",
    "url": "https://github.com/DrFlyingPig/krkr-ns",
    "default_branch": "main",
    "head_sha": "949faf9a874f54b149a3fe5382cfccb38afb99bb",
    "head_date": "2026-10-16",
    "pinned": "v0.1.0 (tag = HEAD; release asset krkrsdl2.nro 29,576,369 B, dl 108)",
    "license_spdx": "MIT",
    "license_file": "LICENSE",
    "license_notes": "MIT 全文 (Copyright (C) Kirikiri SDL2 Developers)，另声明本仓库为 krkrsdl2 派生并以同一 MIT 发布；第三方组件(krkrz、FAudio、SDL2、simde、zlib、FreeType、libjpeg-turbo、libpng、libogg/vorbis、libopus、jxrlib)保留各自许可；仓库不含商业游戏资源。",
    "archived": "false",
    "last_push": "2026-10-16",
    "stars": "22",
    "open_issues": "2",
    "build_system": "CMake + Ninja (Switch toolchain file) + devkitA64; 入口 build_nro.sh; 产物 build-switch/krkrsdl2.nro; 无 CI",
    "build_deps": "devkitPro devkitA64 默认 D:/devkitPro; CMake 3.31.6/Ninja/pkgconf 由 KRKRNS_TOOLS 外部工具目录提供(默认 /d/KRKR-ns-tools); FFmpeg 7.1 私有子集由 tools/build_ffmpeg_switch.sh 构建(sha256 40973d44...); 6 个 git submodule(krkrz/simde/meson_toolchains/SDL/zlib/FAudio)",
    "readme_claims": "README 原文称 属实验性项目，难以保证稳定性；基于 krkrsdl2 bf207f2 + krkrz b11c43a；含游戏库启动器、E-mote动态立绘、AlphaMovie、LayerExRaster、视频/音频解码；真机路径不能包含中文；需在 HBMenu 按住 R 启动以获完整内存。",
    "readme_claim_url": "https://github.com/DrFlyingPig/krkr-ns/blob/main/README.md",
    "risks": [
      "构建非自包含：依赖仓库外工具目录与兄弟仓库 WA2-ns/out 中的 ffmpeg 归档与 msys make",
      "无 CI，无法自动验证构建可复现",
      "release 时间线矛盾：published_at 2026-09-14 早于 created_at 2026-10-16，版本只能以 commit SHA 锁定",
      "README 自述实验性；未真机验证(只读审计)"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/DrFlyingPig/krkr-ns",
      "https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/README.md",
      "https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/LICENSE",
      "https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/build_nro.sh",
      "https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/tools/build_ffmpeg_switch.sh"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "krkrsdl2/krkrsdl2",
    "url": "https://github.com/krkrsdl2/krkrsdl2",
    "default_branch": "main",
    "head_sha": "124bdf841f09e7ce02aa99b7b55791a0f7a900ff",
    "head_date": "2026-10-01",
    "pinned": "tag latest -> bf207f27d683834d35146736ec8d83d397ec75a2 (prerelease 2026-08-31; NRO 12,011,585 B dl 16)",
    "license_spdx": "MIT",
    "license_file": "LICENSE",
    "license_notes": "MIT 全文 (Copyright (C) Kirikiri SDL2 Developers)；README 称 src 目录 MIT、含第三方组件(非 GPL)。",
    "archived": "false",
    "last_push": "2026-10-01",
    "stars": "438",
    "open_issues": "33",
    "build_system": "CMake (主) + Meson (备); .github/workflows/ci.yml 矩阵含 switch target，容器 devkitpro/devkita64:20241023; 产物 build/*.nro",
    "build_deps": "SDL2；CMake 需 -DCMAKE_TOOLCHAIN_FILE=${DEVKITPRO}/cmake/Switch.cmake -DNINTENDO_SWITCH=ON -DEMBED_DATA_PATH=<data.xp3>；CI 装 p7zip-full cmake make ninja-build git curl；external 子模块",
    "readme_claims": "Kirikiri SDL2 是 Kirikiri Z 的 SDL2 平台移植；README 未提 Switch(仅 CMake/CI 有 NINTENDO_SWITCH 分支，SWITCH_AUTHOR=uyjulian，SWITCH_VERSION=v2.0.0)；原文 Running unmodified commercial games using this project is not supported. Please use Wine or Kirikiroid2 instead.",
    "readme_claim_url": "https://github.com/krkrsdl2/krkrsdl2/blob/main/README.md",
    "risks": [
      "官方 NRO 为单游戏内嵌构建(EMBED_DATA_PATH)，不是多游戏启动器",
      "README 完全不宣传 Switch 支持，随时可能被移除且无公告",
      "README 明确不支持未修改商业游戏"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/krkrsdl2/krkrsdl2",
      "https://raw.githubusercontent.com/krkrsdl2/krkrsdl2/main/CMakeLists.txt",
      "https://raw.githubusercontent.com/krkrsdl2/krkrsdl2/main/.github/workflows/ci.yml",
      "https://raw.githubusercontent.com/krkrsdl2/krkrsdl2/main/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "Erige005/Kirikiroid2-NX",
    "url": "https://github.com/Erige005/Kirikiroid2-NX",
    "default_branch": "main",
    "head_sha": "e96b6034c292c6ccdb099823ab6a0a6b505f77f3",
    "head_date": "2026-10-18",
    "pinned": "v1.0.1 (release 2026-10-18; Kirikiroid2-NX.nro 42,338,934 B dl 87)",
    "license_spdx": "NOASSERTION (KiriKiri license, BSD-style, non-SPDX)",
    "license_file": "LICENSE",
    "license_notes": "LICENSE 43,292B = KiriKiri license(Copyright W.Dee and contributors，日文三条款 BSD-style 再分发条件) + libjpeg-turbo BSD 文本；GitHub licenseInfo 为 NOASSERTION；另附 THIRD_PARTY_LICENSES.md 3,546B 列出 FFmpeg 3.2.19 LGPL-2.1-or-later、OpenCV BSD-3、libiconv LGPL-2.1、UnRAR license、Blend2D zlib、DroidSansFallback Apache-2.0 等。",
    "archived": "false",
    "last_push": "2026-10-18",
    "stars": "18",
    "open_issues": "1",
    "build_system": "devkitPro devkitA64 + libnx，Linux/WSL2 脚本; platforms/switch/tools/ 系列脚本; 产物 kirikiroid2.nro",
    "build_deps": "cocos2d-x 3.11.1(含 Switch 补丁)、p7zip 16.02 + LZMA SDK 16.04、OpenCV 3.4.20、libbpg 0.9.8、jxrlib、Blend2D、libiconv 1.17、unrar 5.6.5、FFmpeg 3.2.19；UI 资源需从官方 Kirikiroid2 1.3.9 APK 抽取(不在仓库)；devkitpro/devkita64:20260219 portlibs",
    "readme_claims": "标题 The first port of Kirikiroid2 to the Nintendo Switch，基于 zeas2 原版 Kirikiroid2 1.3.9 源码；v1.0.1 原文 Real games run from start to finish (video, voice, BGM, text, menus, transitions, saves). A few plugins and features are still missing；必须 title-takeover(启动时按住 R)否则内存不足；游戏放 sdmc:/kirikiri/<game>/；仅软件渲染；缺 KAGParserEx/E-mote/scriptsEx/layerExRaster/json/sqlite 等插件。",
    "readme_claim_url": "https://github.com/Erige005/Kirikiroid2-NX/blob/main/README.md",
    "risks": [
      "KiriKiri license 非 OSI/SPDX，再分发义务需法务确认",
      "项目创建 2026-09-30 极新，仅 1 issue，稳定性证据少",
      "必须 title-takeover 才有足够内存，普通 hbmenu 启动不可用",
      "构建链最重：8 个 portlibs 需脚本构建 + 从 APK 抽取 UI 资源",
      "插件缺口明显(E-mote 等)，与 krkr-ns 功能互补而非替代"
    ],
    "verification_level": "read-only",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/Erige005/Kirikiroid2-NX",
      "https://raw.githubusercontent.com/Erige005/Kirikiroid2-NX/main/README.md",
      "https://raw.githubusercontent.com/Erige005/Kirikiroid2-NX/main/THIRD_PARTY_LICENSES.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "clamintus/ONScripter-NX",
    "url": "https://github.com/clamintus/onscripter-nx",
    "default_branch": "main",
    "head_sha": "a8439a86393f74c503d28df176f010ca544af56f",
    "head_date": "2026-01-14",
    "pinned": "v0.3.1 (release 2026-01-15; tag = HEAD)",
    "license_spdx": "GPL-2.0",
    "license_file": "COPYING",
    "license_notes": "GNU GPL v2 (June 1991) 全文 17,992B；未写 or later 条款 → GPL-2.0-only 语义；分发修改版需以同许可开源并提供源码。",
    "archived": "false",
    "last_push": "2026-01-15",
    "stars": "37",
    "open_issues": "0",
    "build_system": "devkitPro Makefile (EDKITPRO/libnx switch_rules, elf2nro)；make / make ENABLE_HD=1；产物 onscripter-nx.nro",
    "build_deps": "switch-dev、switch-sdl2、switch-sdl2_image、switch-sdl2_mixer、switch-sdl2_ttf、switch-smpeg2、switch-libvorbis、switch-libvorbisidec；SDL2_ttf 需 make -f Makefile.extlibs 重建(上游 TTF_RenderUTF8_Shaded bug)",
    "readme_claims": "onscripter-20060724-insani-sdl2 的 Switch 移植，专为老 NScripter 游戏；测试游戏 Tsukihime、Kagetsu Tohya；支持 4:3 模拟、触屏、RomFS 内嵌；v0.3 起 HD 渲染(CPU 负担增加、输入可能延迟)。",
    "readme_claim_url": "https://github.com/clamintus/onscripter-nx/blob/main/README.md",
    "risks": [
      "release 资产内嵌月姬/歌月十夜商业游戏数据(禁止下载/使用/外传)",
      "GPL-2.0 传染性：GalNX 若链接该代码需整体开源",
      "HD 模式 CPU 负担与输入延迟自述",
      "无 CI；v0.3.1 之后近 9 个月无更新"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/clamintus/onscripter-nx",
      "https://raw.githubusercontent.com/clamintus/onscripter-nx/main/README.md",
      "https://raw.githubusercontent.com/clamintus/onscripter-nx/main/Makefile",
      "https://raw.githubusercontent.com/clamintus/onscripter-nx/main/COPYING"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "wetor/ONScripter-jh-Switch",
    "url": "https://github.com/wetor/ONScripter-jh-Switch",
    "default_branch": "master",
    "head_sha": "35f55c89b7b6b4e7997cc2a5a6e2afc4ef3e079a",
    "head_date": "2026-02-02",
    "pinned": "v21.2.1 (annotated tag -> commit 573301c1e3c0ceffed33aae73acab9df95aaa076, 2026-02-01; ONScripter_Switch.nro 16,735,572 B dl 914)",
    "license_spdx": "GPL-2.0",
    "license_file": "COPYING",
    "license_notes": "LICENSE 18,092B 与 COPYING 17,992B 均为 GNU GPL v2 文本；README 声明 GPL v2.0；基于 YuriSizuku/OnscripterYuri 移植。",
    "archived": "false",
    "last_push": "2026-02-02",
    "stars": "221",
    "open_issues": "1",
    "build_system": "devkitPro Makefile.switch；make -f Makefile.switch -j$(nproc)；产物 onsyuri.nro；有 .github/workflows/build_switch.yml",
    "build_deps": "switch-dev、switch-sdl2、switch-sdl2_ttf、switch-sdl2_image、switch-sdl2_mixer、switch-liblua51、switch-freetype、switch-harfbuzz；C++17/-fno-rtti/-fno-exceptions；-march=armv8-a+crc+crypto",
    "readme_claims": "ONScripter Yuri for Nintendo Switch，基于 OnscripterYuri 移植；内置中文游戏浏览器、全中文 UI、触屏、ARM NEON SIMD、C++17、Lua 脚本、存档管理；游戏放 sdmc:/onsemu/<name>/ 需 0.txt 或 00.txt；不支持中文文件夹名；要求破解机+Atmosphere+系统 9.0.0+。",
    "readme_claim_url": "https://github.com/wetor/ONScripter-jh-Switch/blob/master/README.md",
    "risks": [
      "GPL-2.0 传染性，与 GalNX 闭源分发不兼容",
      "README 编译步骤写 clone 上游 YuriSizuku/OnscripterYuri 而非本仓库，复现有歧义",
      "README 顶部 CI badge 指向上游不存在的 workflow，badge 失效",
      "不支持中文文件夹名；未真机验证(只读审计)"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/wetor/ONScripter-jh-Switch",
      "https://raw.githubusercontent.com/wetor/ONScripter-jh-Switch/master/README.md",
      "https://raw.githubusercontent.com/wetor/ONScripter-jh-Switch/master/Makefile.switch"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "xmoezzz/rfvp",
    "url": "https://github.com/xmoezzz/rfvp",
    "default_branch": "main",
    "head_sha": "9f07adef2eb5d559777f9bf59a67b756875cb24f",
    "head_date": "2026-10-25",
    "pinned": "tags: pre-release(prerelease, = HEAD)、0.7.0 -> 99435f22e94eaec27c0c1b9f22cc2a6b1910d7d1 (2026-10-19)",
    "license_spdx": "MPL-2.0",
    "license_file": "LICENSE",
    "license_notes": "MPL-2.0 全文；文件级 copyleft，修改 MPL 覆盖文件需以 MPL 公开该文件源码；可与专有代码组合分发。",
    "archived": "false",
    "last_push": "2026-10-25",
    "stars": "152",
    "open_issues": "2",
    "build_system": "Rust (cargo build-std, 自定义 target json) + devkitA64/libnx；platform/switch/build_switch.sh -> target/rfvp-switch/switch/rfvp.nro；无 CI",
    "build_deps": "devkitPro(devkitA64+libnx+switch-tools, DEVKITPRO 默认 /opt/devkitpro)、rustup pinned nightly(RFVP_CONSOLE_NIGHTLY, platform/consoles/toolchain.env)、aarch64-nintendo-switch-rfvp.json、no_std/alloc、-Zbuild-std=core,alloc,compiler_builtins",
    "readme_claims": "非官方 Rust 跨平台 FVP 引擎重实现；平台表 Switch = Standalone(.nro) Experimental；platform/switch/README 原文 It runs in Ryujinx at 60 fps with picture and sound; it has not been run on a console yet；软件光栅器 1280x720；存档在 game/save 且与桌面版编码不兼容；禁止分发游戏数据。",
    "readme_claim_url": "https://github.com/xmoezzz/rfvp/blob/main/platform/switch/README.md",
    "risks": [
      "从未在真机运行(仓库自述)，仅 Ryujinx 60fps",
      "仅软件渲染、无 GPU 渲染器",
      "存档编码与桌面版不兼容",
      "无 CI；需自行安装 pinned nightly 工具链",
      "MPL-2.0 合规需保留源码可得性"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/xmoezzz/rfvp",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/README.md",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/switch/README.md",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/switch/build_switch.sh"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "xmoezzz/siglus_rs",
    "url": "https://github.com/xmoezzz/siglus_rs",
    "default_branch": "main",
    "head_sha": "5f358ef1360b0439e92aed2b749e8f25d8721954",
    "head_date": "2026-10-08",
    "pinned": "tags 1.0.0 / pre-release (= HEAD); siglus-switch.nro 14,531,824 B dl 12 在 pre-release",
    "license_spdx": "MPL-2.0",
    "license_file": "LICENSE-MPL-2.0",
    "license_notes": "MPL-2.0 全文在根目录 LICENSE-MPL-2.0；文件级 copyleft，需公开被 MPL 覆盖文件的源码。",
    "archived": "false",
    "last_push": "2026-10-26",
    "stars": "125",
    "open_issues": "1",
    "build_system": "Rust + devkitPro(deko3d/uam)；platform/switch/build_switch.sh -> platform/switch/runtime/siglus_switch.nro；.github/workflows/switch-image.yml",
    "build_deps": "devkitA64 + libnx + deko3d + uam；shaderc/(naga 0.20) 构建期 WGSL->GLSL；Cargo workspace(crates/siglus_scene_vm 等)；游戏侧需 key.toml(二级密钥)",
    "readme_claims": "UK2/AVG32/RealLive/SiglusEngine 的纯 Rust 重实现，主攻 SiglusEngine，非商业研究用途；平台表含 Nintendo Switch aarch64；Switch 前端复用 Scene VM/resource loader/audio engine，libnx 接管 lifecycle/input/audio，渲染用 deko3d 替代 wgpu；package_game_nro.sh 可内嵌资源；>4GiB 需 exFAT。",
    "readme_claim_url": "https://github.com/xmoezzz/siglus_rs/blob/main/platform/switch/README.md",
    "risks": [
      "未真机验证；README 未声明真机通过",
      "WGSL->GLSL->uam 构建链复杂，与 release NRO 是否一致未核实",
      "需游戏侧 key.toml(二级密钥)，涉及用户自有游戏数据",
      "MPL-2.0 合规需保留源码可得性",
      "Siglus 系列仅为引擎子集覆盖，兼容性未验证"
    ],
    "verification_level": "read-only",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/xmoezzz/siglus_rs",
      "https://raw.githubusercontent.com/xmoezzz/siglus_rs/main/README.md",
      "https://raw.githubusercontent.com/xmoezzz/siglus_rs/main/platform/switch/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "renpy/renpy",
    "url": "https://github.com/renpy/renpy",
    "default_branch": "master",
    "head_sha": "98401410511152b98f2b38fecc942dc084f523eb",
    "head_date": "2026-10-29",
    "pinned": "8.5.3.26051504 (annotated tag 3c707741828458ce41ee76cd7b5b688a48eead56 -> commit 39895c1e017f0b36ffea2447d97eccd69d76ee1c, 2026-05-16T01:14:41Z); release published 2026-05-16",
    "license_spdx": "MIT (with LGPL portions)",
    "license_file": "sphinx/source/license.rst (no root LICENSE file; /license 404)",
    "license_notes": "主许可 MIT(license.rst 首段 Most of Ren'Py is covered by the terms of the following (MIT) license)；原文 Portions of Ren'Py are derived from source code that is licensed under the GNU Lesser General Public License, so Ren'Py games must be distributed in a manner that satisfies the LGPL；依赖含 LGPL(chardet/FFmpeg/Fribidi/libusb)、MPL-2.0(certifi)、Apache-2.0(requests/rsa)、Zlib(SDL2 等)、BSD 多种、Python License；Generated Project Dedication：未修改的新项目生成文件(game/gui.rpy、options.rpy、screens.rpy、script.rpy、game/gui 图片)为 CC0 1.0。",
    "archived": "false",
    "last_push": "2026-10-29",
    "stars": "6951",
    "open_issues": "251",
    "build_system": "setuptools + Cython(setup.py build_ext)，pkg-config 探测依赖；run.sh 用 .venv 并 python setup.py build_ext --inplace；无 build-system 段(注释称 build isolation 太慢)；官方交叉编译走 renpy-build",
    "build_deps": "Python >=3.12.8,<3.13；Cython >=3.3.0；8.5.3 用 SDL2(+SDL2_image>=2.6)；FFmpeg libav*(format/codec/util/swresample/swscale)、Freetype、Harfbuzz、Fribidi、libpng、libjpeg、zlib、assimp；master 已全面迁移 SDL3",
    "readme_claims": "README.rst 原文 Setup.py does not support cross-compiling. See https://github.com/renpy/renpy-build for software that cross-compiles Ren'Py for many platforms；开发脚本假定 POSIX-like(Linux/macOS，Windows 需 MSYS)；支持 RENPY_CFLAGS/RENPY_LDFLAGS/RENPY_CC/RENPY_CXX/RENPY_LD 环境变量；贡献按 MIT；AI 使用政策不接受无人工审查的 agent 变更。",
    "readme_claim_url": "https://github.com/renpy/renpy/blob/master/README.rst",
    "risks": [
      "无根 LICENSE 文件，许可证只在 sphinx/source/license.rst 与官网；/license 返回 404",
      "含 LGPL 部分，分发游戏需满足 LGPL 合规(提供对应源码/重链接手段)",
      "master 已迁 SDL3，与 8.5.3(SDL2) 不兼容，基线必须锁 tag",
      "官方平台矩阵无 Switch，无任何 Switch 分支或交叉编译入口",
      "README 明示 setup.py 不支持交叉编译"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/renpy/renpy",
      "https://raw.githubusercontent.com/renpy/renpy/master/README.rst",
      "https://raw.githubusercontent.com/renpy/renpy/8.5.3.26051504/setup.py",
      "https://raw.githubusercontent.com/renpy/renpy/master/pyproject.toml",
      "https://raw.githubusercontent.com/renpy/renpy/master/sphinx/source/license.rst"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "renpy/renpy-build",
    "url": "https://github.com/renpy/renpy-build",
    "default_branch": "master",
    "head_sha": "cff4919ae0ff9976470dbc1d78a1a3ec7fb6432f",
    "head_date": "2026-10-26",
    "pinned": "renpy-8.5.3.26051504 (annotated tag 0cacf3957d4194e29f01c2c5bbb39bb9060b463a -> commit 7bfab40c1174f622f644b24669afd5fb167fbb79, 2026-05-13T04:17:01Z)",
    "license_spdx": "MIT",
    "license_file": "",
    "license_notes": "仓库无 LICENSE 文件(/license 404，licenseInfo null)；按 renpy/renpy 的 license.rst 声明，Ren'Py 依赖源码位于 renpy/renpy 与 renpy/renpy-build 两仓库并受同一 MIT(+LGPL 部分)条款约束 → 本字段为推定 MIT，未经仓库内文件确认。",
    "archived": "false",
    "last_push": "2026-10-26",
    "stars": "120",
    "open_issues": "16",
    "build_system": "build.sh(111B) = exec uv --project renpy run -m renpybuild \"$@\"；tasks/ 下 Python 构建任务驱动交叉编译；prepare.sh 改系统环境",
    "build_deps": "Ubuntu 24.04、root、LLVM 22/clang 22、debootstrap、libsdl3-dev(libsdl3-image-dev)、cmake、ninja、uv；source/ 锁版本：Python-3.12.8、SDL2-2.0.20(8.5.3 分支)/SDL3-3.4.18(master)、ffmpeg-4.3.1、freetype-2.13.3、harfbuzz-8.0.1、fribidi-1.0.7、libjpeg-turbo-1.5.3、libpng-1.6.43、zlib-1.3.1、openssl-3.3.2；tasks/python3.py 依赖 autoconf/configure(非 newlib)；tasks/sysroot.py 用 Ubuntu jammy glibc sysroot",
    "readme_claims": "README: 需 Ubuntu 24.04、部分流程必须 root、至少 64GB 磁盘、8 vCPU/16GB RAM；原文 Support for unofficial builds of Ren'Py will be limited；build.py 平台矩阵 linux x86_64/aarch64、windows x86_64、mac x86_64/arm64、android 三 ABI、ios、web wasm —— 无 switch/nx。",
    "readme_claim_url": "https://github.com/renpy/renpy-build/blob/master/README.rst",
    "risks": [
      "无 LICENSE 文件，许可状态只能靠同项目 license.rst 推定",
      "平台矩阵无 Switch，独立移植需自写平台后端(tasks/ 后端)与 runtime 分支",
      "构建要求 root + debootstrap + LLVM 22 + 64GB 磁盘，复现门槛高",
      "master 已迁 SDL3，8.5.3 分支仍是 SDL2 → 基线必须锁 tag",
      "README 声明非官方构建支持有限"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/renpy/renpy-build",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/README.rst",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/build.sh",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/prepare.sh",
      "https://raw.githubusercontent.com/renpy/renpy-build/renpy-8.5.3.26051504/tasks/python3.py"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "jvrcruzGAMES/RenpySwitch",
    "url": "https://github.com/jvrcruzGAMES/RenpySwitch",
    "default_branch": "master",
    "head_sha": "7824039a7d0353b7bfa79ddfcecbf30a375d3d62",
    "head_date": "2026-08-10",
    "pinned": "none (0 releases, 0 tags)；renpy.patch 基于 Ren'Py 8.3.4",
    "license_spdx": "NOASSERTION (no license file)",
    "license_file": "",
    "license_notes": "LICENSE / LICENSE.md / LICENSE.txt 均不存在，GitHub /license 404、licenseInfo null → 无任何许可证，禁止复制/分发其代码与产物。",
    "archived": "false",
    "last_push": "2026-08-10",
    "stars": "2",
    "open_issues": "0",
    "build_system": ".github/workflows/main.yml(GitHub Actions, container devkitpro/devkita64:20230910)；setup.bash -> build.bash -> raw/ 组装；pack_nro.bash / pack_nsp.bash 打包 NRO/NSP",
    "build_deps": "Ren'Py SDK/source 8.3.4、pygame_sdl2 2.1.0、NXPython(CPython 3.14, CPYTHON_COMMIT 1b1c61a94f0685bb0be707b5374376f3084159fe)、Cython 3.0.10、devkitPro switch-mesa/glad/libdrm_nouveau/ffmpeg/freetype/curl/mbedtls/liblzma/libzstd/zlib/bzip2、switch-libfribidi 1.0.12；产物 raw/switch/exefs/main(NSO) + RomFS",
    "readme_claims": "README: Build pipeline for Ren'Py on Nintendo Switch, powered by GitHub Actions and NXPython；表列 Ubuntu 24.04、devkitpro/devkita64:20230910、Ren'Py SDK 8.3.4、Python 3.14(NXPython)、Cython 3.0.10；需 Linux(WSL2/Docker)。",
    "readme_claim_url": "https://github.com/jvrcruzGAMES/RenpySwitch/blob/master/README.md",
    "risks": [
      "无许可证：法律上不可接入、不可复制其 patch 或产物",
      "依赖同样无许可证的 NXPython(CPython 3.14 补丁栈)",
      "无 release 二进制、stars 2，无真机验证记录",
      "仅作技术差异参考，禁止复制代码"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/jvrcruzGAMES/RenpySwitch",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/README.md",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/renpy.patch",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/setup.bash"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "knautilus/RenpySwitch",
    "url": "https://github.com/knautilus/RenpySwitch",
    "default_branch": "master",
    "head_sha": "d361e44fbf15cd1bda66d77cce74e29fc2a7f115",
    "head_date": "2025-06-21",
    "pinned": "7.6.3_1.0 (= HEAD；release Renpy 7.6.3, 2025-06-21)",
    "license_spdx": "NOASSERTION (no license file)",
    "license_file": "",
    "license_notes": "无 LICENSE 文件，/license 404、licenseInfo null → 无许可证，禁止接入。",
    "archived": "false",
    "last_push": "2026-02-07",
    "stars": "6",
    "open_issues": "0",
    "build_system": "GitHub Actions + setup.bash/build.bash(与 Otorhin/Ren2Switch 同构)；产物 NRO/NSP",
    "build_deps": "devkitpro/devkita64:20230910、Ren'Py 7.6.3 SDK、Python 2.7、Cython 0.29.36、pefile 2019.4.18；renpy.patch 44 文件/116 hunk",
    "readme_claims": "README(俄语): Данный репозиторий служит сборщиком RenPy на Github Actions；表列 ubuntu-24.04、devkitpro/devkita64:20230910、renpy sdk 7.6.3、python 2.7。",
    "readme_claim_url": "https://github.com/knautilus/RenpySwitch/blob/master/README.md",
    "risks": [
      "无许可证：不可接入",
      "Python 2.7 运行时，Ren'Py 7.6.3 已过时(官方 8.5.3 为 Python 3.12)",
      "无 CI 记录维护活跃度证据(只有 push 时间)"
    ],
    "verification_level": "read-only",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/knautilus/RenpySwitch",
      "https://raw.githubusercontent.com/knautilus/RenpySwitch/master/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "Otorhin/Ren2Switch",
    "url": "https://github.com/Otorhin/Ren2Switch",
    "default_branch": "master",
    "head_sha": "5fce4a28afaa1df262876b7bcce0bee10b3a0360",
    "head_date": "2023-09-04",
    "pinned": "v1.7.5 -> e41dfbe5ee77e9ad673bb4d2854f5983d5f05935 (2020-12-20；release 2020-12-20)",
    "license_spdx": "NOASSERTION (no license file)",
    "license_file": "",
    "license_notes": "无 LICENSE 文件，/license 404 → 无许可证，禁止接入；上游祖先 uyjulian/renpy-switch 亦无许可证。",
    "archived": "false",
    "last_push": "2023-09-04",
    "stars": "12",
    "open_issues": "0",
    "build_system": "GitHub Actions(container devkitpro/devkita64:20221113)；setup.bash/build.bash；产物 raw.zip(NRO/NSP)",
    "build_deps": "Ren'Py 7.6.1、Python 2.7、Cython 0.29.36、pefile 2019.4.18、python27-switch.tar.gz、switch-libfribidi；依赖从 Otorhin/scripts 与 dl.otorh.in 下载",
    "readme_claims": "Ren'Py to Nintendo Switch 构建器(README 短)；homepage 指向 lemmasoft 论坛帖；14 个 tag 最新 v1.7.5，但代码最迟 2020-12，2023 仅 push 时间。",
    "readme_claim_url": "https://github.com/Otorhin/Ren2Switch/blob/master/README.md",
    "risks": [
      "无许可证：不可接入",
      "Python 2.7 + Ren'Py 7.6.1，已完全过时",
      "依赖第三方 release 下载(dl.otorh.in / Otorhin/scripts)，可复现性差",
      "长期停更(最后提交 2023-09)"
    ],
    "verification_level": "read-only",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/Otorhin/Ren2Switch",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "uyjulian/renpy-switch",
    "url": "https://github.com/uyjulian/renpy-switch",
    "default_branch": "landing",
    "head_sha": "8a75ca3bd5f1c50612a33abae216ecf772b7d330",
    "head_date": "2022-01-04",
    "pinned": "v1.7.5 -> e41dfbe5ee77e9ad673bb4d2854f5983d5f05935 (2020-12-20)",
    "license_spdx": "NOASSERTION (no license file)",
    "license_file": "",
    "license_notes": "无 LICENSE 文件，/license 404 → 无许可证，禁止接入；仓库已 archived。",
    "archived": "true",
    "last_push": "2022-01-04",
    "stars": "70",
    "open_issues": "7",
    "build_system": "已归档；根目录仅 README.md(landing 分支)，历史产物见 14 个 release",
    "build_deps": "历史版本基于 Ren'Py 7.x + devkitPro(未在本轮复现)",
    "readme_claims": "README 原文 Sorry, this project is archived! Please use Switchroot Android with the official port of Ren'Py；仓库描述: (Project archived, please use Switchroot Android with the official port of Ren'Py) Open source port of Ren'Py to the Nintendo Switch。",
    "readme_claim_url": "https://github.com/uyjulian/renpy-switch/blob/landing/README.md",
    "risks": [
      "已归档且无许可证：不可接入",
      "作者建议改用 Switchroot Android + 官方 Ren'Py，即承认原生移植路线失败",
      "landing 分支只有 README，源码不在默认分支"
    ],
    "verification_level": "read-only",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/uyjulian/renpy-switch",
      "https://raw.githubusercontent.com/uyjulian/renpy-switch/landing/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "jvrcruzGAMES/NXPython",
    "url": "https://github.com/jvrcruzGAMES/NXPython",
    "default_branch": "main",
    "head_sha": "86cde186653a89593359bd59102ed2b878c6fa5b",
    "head_date": "2026-08-09",
    "pinned": "none (0 tags, 0 releases)；CPYTHON_COMMIT 1b1c61a94f0685bb0be707b5374376f3084159fe",
    "license_spdx": "NOASSERTION (no license file)",
    "license_file": "",
    "license_notes": "licenseInfo null、无 LICENSE 文件 → 无许可证，禁止接入；仅作 CPython 可在 Switch 上构建的存在性证据。",
    "archived": "false",
    "last_push": "2026-08-09",
    "stars": "0",
    "open_issues": "0",
    "build_system": "build.sh(4,240B) 克隆 CPython、打补丁、用 devkitA64 构建；DEVKITPRO=/opt/devkitpro ./build.sh -j 8；产物 static libpython3.14.a 安装进 devkitPro portlibs",
    "build_deps": "devkitA64 + devkitPro portlibs；上游 CPython 3.14(CPYTHON_COMMIT 1b1c61a9...)；单补丁 patches/0001-nxpython-cpython-3.14.patch(299,892B) 增加 sys.platform=nx 与 romfs:/sdmc: 路径语义",
    "readme_claims": "README: NXPython keeps the Nintendo Switch CPython port outside the CPython checkout. This repository tracks patch files only; CPython itself is downloaded into ignored working directories；build-portlibs.sh 支持 --runtime-prefix sdmc:/python、romfs:/python 与 romfs:/python_site。",
    "readme_claim_url": "https://github.com/jvrcruzGAMES/NXPython/blob/main/README.md",
    "risks": [
      "无许可证：其补丁栈不可复用",
      "单补丁 300KB 维护成本高、跟随上游 CPython 3.14 漂移",
      "stars 0、创建 2026-08-09，未被广泛验证",
      "仅证明可构建静态 libpython3.14.a，未证明 Ren'Py 在其上可运行"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/jvrcruzGAMES/NXPython",
      "https://raw.githubusercontent.com/jvrcruzGAMES/NXPython/main/README.md",
      "https://raw.githubusercontent.com/jvrcruzGAMES/NXPython/main/CPYTHON_COMMIT"
    ],
    "audited_at": "2026-10-29"
  }
]
```
<!-- AUDIT-JSON-END -->
