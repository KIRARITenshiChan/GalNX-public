# 已存 Galgame 引擎移植（集群 B）审计（只读）

- 审计日期: 2026-10-29
- 审计员: audit-engines
- 方法: GitHub REST API（/repos、/license、/releases、/tags、/commits；经 cred_use 使用 GH_TOKEN，未外传凭据）+ GitHub GraphQL API（licenseInfo、defaultBranchRef、refs/tags、releases、issues/PR 计数、git tree 列举）+ raw.githubusercontent.com 文件原文下载（README/LICENSE/构建脚本/CI/字体二进制）+ 本地 Node 解析 TTF name 表。未执行 git clone、构建、安装或下载游戏数据。
- 覆盖: 5 个条目

## 总览表

| 条目 | 用途 | 精确版本（tag/commit） | 许可证(SPDX) | 健康 | 结论 |
| --- | --- | --- | --- | --- | --- |
| DrFlyingPig/krkr-ns | KiriKiri/Z（krkrsdl2）Switch 移植，计划草案 L251 的优先研究样板 | v0.1.0 tag 指向 949faf9a874f54b149a3fe5382cfccb38afb99bb（2026-10-16）；release v0.1.0 发布于 2026-09-14 | MIT（仓库）；vendored 上游为 KiriKiri Z 自定义宽松许可 | 活跃；21★；2 open issues；1 release | 首选第一款原型；需先解决构建可复现性与 FFmpeg LGPL 合规 |
| jvrcruzGAMES/RenpySwitch | Ren'Py 8.3.4 运行时构建流水线（NXPython + NSO） | 无 tag/release；HEAD 7824039a7d0353b7bfa79ddfcecbf30a375d3d62（2026-08-10） | 无（未授权，All rights reserved） | 2026-08-09 创建，2★，0 issue/PR | 法律阻塞；仅可作只读参考，未经作者授权不得接入/再分发 |
| Otorhin/Ren2Switch | Ren'Py 7.6.1 旧构建器（第二个 Ren'Py 实现对照） | 无 release；HEAD 5fce4a28afaa1df262876b7bcce0bee10b3a0360（2023-09-04）；最新 tag v1.7.5 为上游遗留（2020-12-20） | 无（未授权） | 停更（2023-09-04）；12★；0 issue | 仅作历史对照，不接入 |
| clamintus/ONScripter-NX | NScripter/ONScripter（onscripter-20060724-insani-sdl2）Switch 移植 | v0.3.1 @ a8439a86393f74c503d28df176f010ca544af56f（2026-01-14） | GPL-2.0-or-later | 活跃；37★；0 open issue；4 releases | 可作第二接入候选（需接受 GPL 义务；release 内含商业游戏数据，禁止复用） |
| xmoezzz/rfvp | FVP 引擎的 Rust 重实现（含 Switch NRO 后端） | 最新 versioned tag 0.7.0 @ 99435f22e94eaec27c0c1b9f22cc2a6b1910d7d1（2026-10-19）；HEAD 9f07adef2eb5d559777f9bf59a67b756875cb24f（2026-10-25，pre-release） | MPL-2.0 | 活跃；151★；2 open PR；6 releases（均无 Switch NRO 资产） | 实验研究项，不作为首个里程碑依赖 |

## 条目详情

### 1. DrFlyingPig/krkr-ns

- URL / 默认分支 / HEAD SHA+日期: https://github.com/DrFlyingPig/krkr-ns / main / 949faf9a874f54b149a3fe5382cfccb38afb99bb，HEAD commit 2026-10-16T13:43:28Z；last push 2026-10-16T14:07:20Z。
- 最近 tag: v0.1.0（tag 指向 949faf9a874f54b149a3fe5382cfccb38afb99bb，2026-10-16；repository tags totalCount=1）。注意：release v0.1.0 发布于 2026-09-14T15:08:56Z，而 tag 当前指向 2026-10-16 的提交 → tag 被移动过，release 附带 NRO 的源不可核验。
- 对应引擎与版本范围: KiriKiri Z（krkrz 基线 b11c43a）经 krkrsdl2（基线声称 bf207f2）移植；面向 KiriKiri 2/3 的 .xp3 资源包与 KAG 脚本；README 称兼容实现参考 Kirikiroid2；入口必须是 .xp3，散装 startup.tjs 目录不能直接启动。
- 上游依赖（取证自 krkrsdl2/.gitmodules 与 krkrsdl2/CMakeLists.txt）:
  - krkrsdl2 上游 = https://github.com/krkrsdl2/krkrsdl2（MIT；main HEAD 124bdf841f09e7ce02aa99b7b55791a0f7a900ff，2026-10-01）；本仓库把整棵 krkrsdl2 树 vendored，根无 .gitmodules。
  - krkrz 上游 = https://github.com/krkrsdl2/krkrz（b11c43a；自定义 KiriKiri Z 许可，GitHub licenseInfo=NOASSERTION/Other）；krkrz/external 含 freetype、jxrlib、libjpeg-turbo、lpng、onig、picojson.h、zlib。
  - krkrsdl2/.gitmodules 另声明 external/krkrz、external/simde、external/meson_toolchains、external/zlib、external/FAudio、SDL（external/SDL 仅用于 Vita/Emscripten 等平台，Switch 用 pkg-config sdl2）。
  - CMake（bf207f2 上游）NINTENDO_SWITCH 分支：pkg_check_modules(SDL2 REQUIRED IMPORTED_TARGET sdl2)；FAudio 用 add_subdirectory(external/FAudio)（XNASONG OFF、BUILD_SHARED_LIBS OFF、TVP_FAUDIO_IMPLEMENT）；NRO 用 elf2nro 生成（--icon=.../icon.jpg --nacp，DEPENDS nacp+romfs）。
  - FAudio（vendored）LICENSE 为 zlib 风格许可（Copyright 2011-2022 Ethan Lee / Luigi Auriemma / MonoGame Team，This software is provided 'as-is'...）。
  - 视频：tools/build_ffmpeg_switch.sh 构建 FFmpeg 7.1 私有子集，源码 https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz，expected_sha256=40973d44970dbc83ef302b0609f2e74982be2d85916dd2ee7472d30678a7abe6，应用 tools/ffmpeg-horizon.patch；configure 用 --disable-gpl（LGPL 模式），启用 asf/mov/mpegps demuxer 与 wmv3/vc1/wmav1/wmav2/wmapro/wmavoice/h264/aac/mpeg1video/mpeg2video/mp2/mp3 等解码器；可用 FFMPEG_ARCHIVE / FFMPEG_HOST_CC / FFMPEG_MAKE 覆盖默认路径。
  - 注意：C++/C 项目，不需要 Rust 工具链；但需要 devkitPro（devkitA64、libnx、switch-tools）、CMake 3.31.6、Ninja、pkg-config 与自建 FFmpeg 7.1。
- 构建入口与产物:
  - 入口脚本 build_nro.sh（bash）：默认 DEVKITPRO=D:/devkitPro、PKG_CONFIG_PATH=D:/devkitPro/portlibs/switch/lib/pkgconfig；工具来自 KRKRNS_TOOLS 环境变量（默认 /d/KRKR-ns-tools，内含 cmake-3.31.6-windows-x86_64/bin/cmake.exe、ninja.exe、bin/pkg-config.exe 等）。
  - 核心命令：cmake -S krkrsdl2 -B build-switch -G Ninja -DCMAKE_TOOLCHAIN_FILE="$TOOLS/Switch.toolchain.cmake" -DNINTENDO_SWITCH=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_MAKE_PROGRAM="$NINJA"；随后用 Python 内联脚本改写 GCS unwind（搜字节 1F2503D5，把其后的 cbnz 0xB5xxxxxx 改写为 b，绕过 Nextendo 模拟器 chkfeat bug），产出 krkrsdl2-patched.elf；再组装 romfs（拷 krkrsdl2/data，删过时的 motion.tjs，拷 compat-patches/system），最后 elf2nro.exe --icon=krkrsdl2/src/resources/nswitch/icon.jpg --nacp=build-switch/krkrsdl2.nacp --romfsdir=build-switch/romfs，产物 build-switch/krkrsdl2.nro。
  - 参数 --no-patch（跳过 GCS patch）、--no-emu-copy（不复制到模拟器目录）；默认还会部署 compat patch 到模拟器 SD 卡 sdmc:/switch/krkrsdl2/patch/system/。
  - compat-patches/README.md：这些 TJS 脚本替换游戏中 Windows-only 插件的空实现；retired/motion.tjs 是历史桩，部署会关闭 E-mote 导致立绘消失。
- README 声称（README 声称，非已验证）: 吉里吉里/KiriKiri Switch 移植，「⚠️ 属实验性项目，难以保证稳定性 ⚠️」；基线 krkrsdl2 bf207f2 + krkrz b11c43a；支持常见 KRKR/KAG 游戏、多资源包、MenuItem 弹窗菜单、快速存读档、补丁/翻译优先、中日本地化与字体兼容、尝试解密脚本读加密包；E-mote 动态立绘、AlphaMovie 透明动画、内置 LayerExRaster 插件；音频 WAV/OGG/Opus/部分 AAC/M4A/MP3，视频部分 WMV/MP4/MPEG；「视频暂不支持变速和多音轨切换」；真机需「使用完整内存模式打开 HBMenu（通常按住 R 从已安装游戏进入）」；「Switch 真机的游戏路径不能包含中文」；「本项目不包含、也不分发任何商业游戏资源」。
- 已知限制: 真机非 ASCII 路径不可用（中文路径明确禁止）；视频不支持变速/多音轨；实验性，稳定性无保证；插件行为依赖游戏自带 TJS，需 compat shims；存档按 sdmc:/switch/KRKR-ns/saves/<GameFolder>/ 分目录；日志保留最近 3 份。
- 健康: archived=false；open issues 2、closed issues 7、PR 0；stars 21、forks 0；1 release（资产 krkrsdl2.nro 29,576,369 B）；无 .github/ → 无 CI。
- 未验证 / 风险: 构建依赖仓库外的 Switch.toolchain.cmake 与 KRKR-ns-tools（未随仓库提供，内容不可核验）；build_ffmpeg_switch.sh 默认归档/make 路径指向兄弟仓库 ../WA2-ns/out/...（外部仓库依赖，可复现性阻塞）；发布 NRO 与 tag 时间线矛盾，资产不可溯源；README 的 baseline bf207f2 无法用文件哈希证明（本仓库 krkrsdl2/CMakeLists.txt 与上游 bf207f2 哈希不同，1f15ee38e747 vs c55d6b6cc95a，属 Switch 适配改动）；NRO 内含 LGPL 模式构建的 FFmpeg，但仓库未随附 FFmpeg 源码/许可文本，再分发需补 LGPL-2.1 合规材料；无 CI，构建未自动验证。
- 来源 URLs: https://github.com/DrFlyingPig/krkr-ns ；https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/README.md ；https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/LICENSE ；https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/build_nro.sh ；https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/tools/build_ffmpeg_switch.sh ；https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/compat-patches/README.md ；https://github.com/krkrsdl2/krkrsdl2 ；https://github.com/krkrsdl2/krkrz ；https://github.com/DrFlyingPig/krkr-ns/releases ；https://api.github.com/repos/DrFlyingPig/krkr-ns

### 2. jvrcruzGAMES/RenpySwitch

- URL / 默认分支 / HEAD SHA+日期: https://github.com/jvrcruzGAMES/RenpySwitch / master / 7824039a7d0353b7bfa79ddfcecbf30a375d3d62，HEAD commit 2026-08-10T19:16:50Z；last push 2026-08-10T19:17:04Z；created 2026-08-09。
- 最近 tag: none（GraphQL refs/tags totalCount=0；releases totalCount=0）。
- 对应引擎与版本范围: Ren'Py 8.3.4（SDK+source），Python 3.14（NXPython 交叉构建的 CPython），pygame_sdl2 2.1.0；目标为 Ren'Py 8.3.x 游戏的 Switch NSO/NRO/NSP 打包流水线。
- 上游依赖（取证自 setup.bash/build.bash/switch/CMakeLists.txt/.github/workflows/main.yml）:
  - 容器 devkitpro/devkita64:20230910（CI runs-on ubuntu-24.04，步骤 checkout --recurse-submodules → sed 去 CR → sudo bash setup.bash → sudo bash build.bash → 上传 raw/ artifact）。
  - devkitPro 包：switch-mesa、switch-glad、switch-libdrm_nouveau、switch-sdl2、switch-sdl2_gfx、switch-sdl2_image、switch-sdl2_mixer、switch-sdl2_ttf、switch-ffmpeg、switch-freetype、switch-curl、switch-mbedtls、switch-liblzma、switch-libzstd、switch-zlib、switch-bzip2；另 dkp-pacman -U devkitpro-pkgbuild-helpers-2.2.4-2 与 switch-libfribidi-1.0.12-1（来自 knautilus/Utils v1.0 release）。
  - NXPython: RENPY 构建用 https://github.com/jvrcruzGAMES/NXPython（无 LICENSE；main HEAD 86cde186653a89593359bd59102ed2b878c6fa5b，2026-08-09），NXPYTHON_COMMIT=1b1c61a94f0685bb0be707b5374376f3084159fe，构建静态 libpython3.14.a 装入 portlibs。
  - Ren'Py 8.3.4 下载源为 https://www.renpy.org/dl/8.3.4/（source/sdk/pygame_sdl2 2.1.0 tarball）；renpy.patch 在 renpy-source 内 patch -p1。
  - switch/CMakeLists.txt 要求 devkitPRO 环境变量与 switch.cmake，pkg_check_modules REQUIRED：egl、freetype2、glapi、glesv2、libavcodec、libavfilter、libavformat、libavutil、libdrm_nouveau、libswresample、libswscale、sdl2、SDL2_gfx、SDL2_image、SDL2_mixer、SDL2_ttf、zlib；SWITCH_VERSION 8.3.4；输出 renpy-switch.nso。
  - setup.bash 会 sed 修改 devkitPro switch.cmake 的 CMAKE_EXE_LINKER_FLAGS_INIT 加 -fPIC（留 .bak）；并用 .venv 安装 Cython==3.0.10（历史版本）。
- 构建入口与产物: 入口 bash setup.bash（下载/解包/建 portlibs，缓存 ./downloads/，--force 重解压）→ bash build.bash（本地先构建 pygame_sdl2 与 renpy-source/module，再交叉编译 ./switch/build/renpy-switch.nso）；产物 raw/switch/exefs/main（NSO）、raw/switch/romfs/Contents/{renpy.py, lib.zip, renpy/common}、raw/renpy_clear/；打包 bash pack_nro.bash <game_dir> <out.nro> <title> [-p publisher] [-v ver]，bash pack_nsp.bash 同参（build_romfs+nacptool+build_pfs0 生成 NSP）；图标 wrestool 从 .exe 提取，退回 icon.png，再退回 libnx 默认图标；NSP TitleID 由 .exe sha256 得 0100<8hex>0000，否则随机。
- README 声称（README 声称）: 「Build pipeline for Ren'Py on Nintendo Switch, powered by GitHub Actions and NXPython」；下载 Ren'Py 8.3.4 源码与 SDL2 bindings、打 Switch 补丁、Cython 编译、打包 lib.zip、交叉编译 .nso、组装空白 Switch 工程 raw/；本地构建需 Linux（Windows 走 Docker/WSL2），Docker 命令为 docker pull devkitpro/devkita64:20230910 后 sed 去 CR、bash setup.bash、bash build.bash；依赖表写 Ubuntu 24.04、devkitpro/devkita64 20230910、Ren'Py SDK 8.3.4、Python 3.14（NXPython）、Cython 3.0.10。README 未声称已在真机运行。
- 已知限制: 只针对 Ren'Py 8.3.4 + Python 3.14 组合；需要游戏目录重建 lib.zip 与 romfs；构建链依赖 CPython 交叉编译（重、耗时）；无真机/模拟器运行声明；无存档/字体/视频兼容性说明。
- 健康: archived=false；stars 2、forks 2；issues 0、PR 0；releases 0、tags 0；fork=true（parent knautilus/RenpySwitch，同样无 LICENSE，pushed 2026-02-07，默认 master HEAD d361e44fbf15cd1bda66d77cce74e29fc2a7f115）。
- 未验证 / 风险: 仓库无任何许可证文件（GitHub license API = null）→ 默认 All rights reserved，法律上不可再分发或并入 GalNX；NXPython 与其父仓库同样无许可证；仓库创建 1 天后即当前状态（2026-08-09），无 release 验证；Ren'Py SDK/pygame_sdl2 下载无 sha256 校验；未验证 CI 实际通过（未查 Actions runs）；未在真机运行。
- 来源 URLs: https://github.com/jvrcruzGAMES/RenpySwitch ；https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/README.md ；https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/setup.bash ；https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/build.bash ；https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/switch/CMakeLists.txt ；https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/.github/workflows/main.yml ；https://github.com/knautilus/RenpySwitch ；https://github.com/jvrcruzGAMES/NXPython ；https://api.github.com/repos/jvrcruzGAMES/RenpySwitch

### 3. Otorhin/Ren2Switch

- URL / 默认分支 / HEAD SHA+日期: https://github.com/Otorhin/Ren2Switch / master / 5fce4a28afaa1df262876b7bcce0bee10b3a0360，HEAD commit 2023-09-04T22:05:13Z（=last push）；created 2022-09-06。
- 最近 tag: v1.7.5（e41dfbe5ee77e9ad673bb4d2854f5983d5f05935，2020-12-20T05:10:03Z）——全部 14 个 tag 均停在 2019-06 至 2020-12，明显沿袭上游历史（HEAD 2023-09-04），不能代表本仓库版本。
- 对应引擎与版本范围: Ren'Py 7.6.1（SDK+source，Python 2.7），pygame_sdl2 2.1.0；目标为 Ren'Py 7.6.x 游戏的 Switch 打包流水线。
- 上游依赖（取证自 setup.bash/build.bash/switch/CMakeLists.txt/.github/workflows/ci.yml）:
  - CI 容器 devkitpro/devkita64:20221113（runs-on ubuntu-latest）；步骤 sudo bash setup.bash、sudo bash build.bash、上传 raw.zip。
  - setup.bash apt 安装 python2.7、python-pip、p7zip-full、cython、libsdl2-dev/image/ttf/mixer/gfx、libjpeg-dev、libpng-dev、libavformat-dev、libfreetype6-dev、libswscale-dev、libglew-dev、libfribidi-dev、libavcodec-dev、libswresample-dev、libgl1-mesa-glx；pip2 安装 future/six/typing/requests/ecdsa/pefile==2019.4.18/Cython==0.29.36。
  - 从 https://github.com/Otorhin/scripts/releases/download/oof/ 下载 devkitpro-pkgbuild-helpers-2.2.3-1、python27-switch.tar.gz、switch-libfribidi-1.0.12-1；python27-switch 解压进 portlibs/switch；dkp-pacman -U 安装 helpers/fribidi。
  - 从 https://www.renpy.org/dl/7.6.1/ 下载 pygame_sdl2-2.1.0-for-renpy-7.6.1.tar.gz、renpy-7.6.1-sdk.zip、renpy-7.6.1-source.tar.bz2、android-native-symbols.zip；从 https://dl.otorh.in/github/rawproject.zip 下载空白工程骨架；android-native-symbols 解压进 ./raw/android/lib 并删除 x86_64；renpy.patch 在 renpy-source 内 patch -p1。
  - switch/CMakeLists.txt 与 RenpySwitch 同构：SWITCH_VERSION 7.6.1、INCLUDES python2.7、同一组 REQUIRED pkg-config（egl/freetype2/glapi/glesv2/libav*/libdrm_nouveau/libsw*/SDL2/SDL2_gfx/SDL2_image/SDL2_mixer/SDL2_ttf/zlib）；输出 renpy-switch.nso。
- 构建入口与产物: bash setup.bash → bash build.bash（全程 python2 工具链）；产物 raw/switch/exefs/main（renpy-switch.nso）+ raw/switch/romfs/Contents/{renpy.py, renpy/common, lib.zip}；python2.7 stdlib 进 private/lib/python2.7；最后 7z a -tzip raw.zip ./raw/*。
- README 声称（README 声称，俄文，未完成）: 仓库包含在 Switch 上运行 RenPy 所需全部文件；作者自称该仓库「служит мне сборщиком RenPy на Github Actions」——下载 RenPy 与 PyGame 源码、下载 Android .so 库、对 RenPy 打作者补丁、编译 RenPy、打包 lib.zip、编译 Switch 可执行文件、组装 PC(Win+Linux)/Android/Switch 空白工程；README 称以后可能补完（未完成）。
- 已知限制: 仅 Ren'Py 7.6.1（较旧）；构建宿主依赖 python2.7 与现代 Ubuntu 已移除的旧包；依赖外部站点 dl.otorh.in（可用性未知）；无真机/模拟器运行声明；tags/release 与自身开发不对应。
- 健康: archived=false；stars 12、forks 4；issues 0、PR 0；releases 0；fork=true（parent uyjulian/renpy-switch，isArchived=true，无 LICENSE，默认分支 landing，HEAD 8a75ca3bd5f1c50612a33abae216ecf772b7d330，pushedAt 2022-01-04T04:13:50Z）。
- 未验证 / 风险: 无许可证（GitHub license API = null；父仓库亦无）→ 不可再分发；停更 2023；python2.7 在现代 CI 镜像中安装可行性未验证；dl.otorh.in 与 Otorhin/scripts 下载可用性未验证；未验证 CI 现状。
- 来源 URLs: https://github.com/Otorhin/Ren2Switch ；https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/README.md ；https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/setup.bash ；https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/build.bash ；https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/switch/CMakeLists.txt ；https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/.github/workflows/ci.yml ；https://github.com/uyjulian/renpy-switch ；https://api.github.com/repos/Otorhin/Ren2Switch

### 4. clamintus/ONScripter-NX

- URL / 默认分支 / HEAD SHA+日期: https://github.com/clamintus/onscripter-nx（canonical nameWithOwner = clamintus/ONScripter-NX）/ main / a8439a86393f74c503d28df176f010ca544af56f，HEAD commit 2026-01-14T18:46:39Z；last push 2026-01-15T22:32:10Z；created 2022-01-21。
- 最近 tag: v0.3.1（a8439a86393f74c503d28df176f010ca544af56f，2026-01-14T18:46:39Z，=HEAD）；历史 tags：v0.3 d26c4330bf2d448d82a45ff126a2070bbd10dc36（2022-09-18）、v0.2 93d3249eff80c5d86e0a7453f8fc2d5b2d90fe09（2022-01-23）、v0.1 8c19b43b4d5ab4bdd79b3fa7d8946f846c084f37（2022-01-21）。
- 对应引擎与版本范围: onscripter-20060724-insani-sdl2（ONScripter 2006-07-24 版，insani 修改，clamintus 做 SDL2 化）→ Switch；引擎 APP_VERSION 0.3.1（Makefile）；面向 legacy NScripter 游戏（arc*.nsa/.sar、nscript.dat/.___、CD 音轨）；README 称专门用于在新版 ONScripter/ONScripter-EN 会出问题的老游戏。
- 上游依赖（取证自 Makefile/Makefile.extlibs/README.md）:
  - devkitPro + libnx：Makefile 第 5-10 行要求 DEVKITPRO 并 include $(DEVKITPRO)/libnx/switch_rules；LDFLAGS 用 -specs=$(DEVKITPRO)/libnx/switch.specs。
  - pacman 包（README）：switch-dev、switch-sdl2、switch-sdl2_image、switch-sdl2_mixer、switch-sdl2_ttf、switch-smpeg2、switch-libvorbis；Makefile LIBS 还硬编码 -L/opt/devkitpro/libnx/lib 与 -L/opt/devkitpro/portlibs/switch/lib，并链接 SDL2_image、jpeg、webp、freetype、harfbuzz、bz2、png16、SDL2_mixer、EGL、glapi、drm_nouveau、vorbisidec(tremor)、modplug、mpg123、opusfile、opus。
  - 编译器参数：ARCH=-march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE；CFLAGS 含 -D__SWITCH__ -DUSE_OGG_VORBIS -DENABLE_1BYTE_CHAR -DFORCE_1BYTE_CHAR -DINSANI -DSDL2（ENABLE_HD 时加 -DENABLE_HD）；CXXFLAGS -fno-rtti -fno-exceptions；产物 $(TARGET).nro（onscripter-nx.nro），romfs 可用。
  - switch_mitm 命名说明：source/switch_mitm.cpp + include/switch_mitm.h 实为 Switch 输入/ROMFS 辅助中间层（switch_init/switch_deinit/switch_getinput/romfsOpen/switch_nofile_splash），不是提权或系统级中间人机制。
  - 视频/字体：内置 SMPEG2（MPEG-1）与 SDL_ttf；romfs/default.ttf 为 Sazanami Gothic（11248 B，name 表 copyright "(C) 1990-2003 Wada Laboratory, Univ. of Tokyo. 2003-04 /efont/. All rights reserved."，family Sazanami Gothic，version 001.000；无 nameID 13/14 许可字段）。
  - Makefile.extlibs（873 B）：进入 extlibs/SDL2_ttf 执行 makepkg -f（PKGBUILD + bug1433.patch），再把 pkg/switch-sdl2_ttf/opt/devkitpro/portlibs/switch/* 拷回；原因：devkitPro/标准 MSYS2 的 SDL2_ttf 的 TTF_RenderUTF8_Shaded 有 bug，导致文字渲染异常。
- 构建入口与产物: make（或 make ENABLE_HD=1）；前置 make -f Makefile.extlibs 修 SDL2_ttf；产物 onscripter-nx.nro（含 --icon --nacp --romfsdir）；release 同时给 HD 与非 HD 包。
- README 声称（README 声称）: 「A port of onscripter-20060724-insani-sdl2 … to the Switch. I specifically made this to support running older NScripter-based games that would break on newer versions of ONScripter or ONScripter-EN.」；Features：4:3 aspect ratio simulation、Touchscreen support、RomFS integration、Optimized flush；Tested games：Tsukihime、Kagetsu Tohya，「Any game that uses legacy ONScripter should run just fine though.」；v0.3 起支持 HD（仅缩放、素材不提升、偶发轻微图形瑕疵 pics/glitches.jpg、CPU 负担增加、输入略延迟、跳过时变慢）；License 段仅「See COPYING」。README 未给出真机 vs 模拟器的明确区分（测试声明只写游戏名）。
- 已知限制: 4:3 模拟；HD 仅缩放且增加 CPU 负担/输入延迟；视频仅 SMPEG2（MPEG-1）能力；需要游戏通过 ONScripter legacy 脚本兼容；默认字体需 default.ttf 或内置 Sazanami（仅 11 KB 子集，可能缺字）；硬编码 /opt/devkitpro 路径；无 CI。
- 健康: archived=false；stars 37、forks 3；open issues 0、closed issues 2、PR 0；releases 4：v0.3.1（2026-01-15T23:20:46Z，6 资产：onscripter-nx.zip 4,637,370、onscripter-nx-hd.zip 4,637,594、tsukihime.zip 6,076,415、tsukihime-hd.zip 6,079,243、kagetsu_tohya.zip 7,683,585、kagetsu_tohya-hd.zip 7,686,900）、v0.3（2022-09-18）、v0.2（2022-01-23）、v0.1（2022-01-21）。
- 许可证: COPYING = GNU GPL Version 2, June 1991 全文；source/ONScripterLabel.cpp 头与 source/switch_mitm.cpp 头均声明 GPL v2 or later（「either version 2 of the License, or (at your option) any later version」）→ SPDX GPL-2.0-or-later（GitHub licenseInfo=GPL-2.0）；分发修改版 NRO 必须提供完整对应源码、保留版权与许可声明。romfs/default.ttf 的 Sazanami Gothic 字体许可未随文件提供，需单独核实（efont 系许可）。
- 未验证 / 风险: GPL 传染性（若 GalNX 框架链接/派生需整体 GPL 兼容，闭源分发不可行）；release 直接附带 Tsukihime / Kagetsu Tohya 商业游戏数据 zip，属作者侧的再分发行为，GalNX 不得下载复用或随附（法律风险）；Sazanami Gothic 字体许可未核实；SDLK2_ttf 必须从源码重打包（devkitPro 包 bug）；无 CI；硬编码路径降低可移植性；未解包 release zip，NRO 内容未核验。
- 来源 URLs: https://github.com/clamintus/ONScripter-NX ；https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/README.md ；https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/COPYING ；https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/Makefile ；https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/Makefile.extlibs ；https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/source/ONScripterLabel.cpp ；https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/source/switch_mitm.cpp ；https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/romfs/default.ttf ；https://github.com/clamintus/onscripter-nx/releases ；https://github.com/clamintus/onscripter-20060724-insani-sdl2 ；https://api.github.com/repos/clamintus/ONScripter-NX

### 5. xmoezzz/rfvp

- URL / 默认分支 / HEAD SHA+日期: https://github.com/xmoezzz/rfvp / main / 9f07adef2eb5d559777f9bf59a67b756875cb24f，HEAD commit 2026-10-25T14:17:46Z；last push 2026-10-25T14:30:48Z；created 2024-02-09；磁盘约 173,700 KB。
- 最近 tag: 最新 versioned tag 为 0.7.0（99435f22e94eaec27c0c1b9f22cc2a6b1910d7d1，2026-10-19T06:12:39Z）；另 pre-release tag（9f07adef2eb5d559777f9bf59a67b756875cb24f，2026-10-25T14:17:46Z = HEAD）；其余 0.6.0 304e7733（2026-09-09）、0.5.0 3b5ea6c9（2026-07-11）、0.4.0 65774725（2026-05-15）、0.3.0 9ae6f06f（2026-03-30）。
- 对应引擎与版本范围: FVP 引擎（原商业视觉小说引擎；游戏资源为 *.hcb 脚本 + *.bin 包 + default.ttf）的非官方 Rust 重实现与 IDE；README 称目标兼容「all versions of the original FVP engine」；Switch 平台状态 Experimental（NRO，arm64-v8a）。
- 上游依赖（取证自 platform/switch/build_switch.sh、platform/consoles/toolchain.env、Cargo.toml、CI）:
  - Rust：workspace（resolver 3，members crates/* 与 platform/{switch,vita,psp,ps2,3ds,ps3,ps1,wiiu,wii}/host）；host crate platform/switch/host = rfvp-horizon 0.1.0（MPL-2.0，crate-type staticlib）；依赖 crates/rfvp default-features=false features=['no_std']；build-dependency cc='1'。
  - 工具链 pin：platform/consoles/toolchain.env 的 RFVP_CONSOLE_NIGHTLY=nightly-2026-02-01（注释强调必须 pin，改它要两平台都构建后再提交）；build_switch.sh 会 rustup toolchain install nightly（--profile minimal --component rust-src），再 cargo +nightly build -p rfvp-horizon --release --target aarch64-nintendo-switch-rfvp.json -Zjson-target-spec -Zbuild-std=core,alloc,compiler_builtins。
  - 自定义 target：platform/switch/aarch64-nintendo-switch-rfvp.json（arch aarch64、os horizon、llvm-target aarch64-unknown-none、panic abort、features +v8a,+neon,+crypto,+crc、linker rust-lld、dynamic-linking false、tier 3、自定义 link script；关闭 dynamic-linking 是为了避免 freestanding target 允许动态库导致 rustc 也构建 cdylib 失败）。
  - devkitPro：devkitA64 + libnx + switch-tools（elf2nro、nacptool），DEVKITPRO 默认 /opt/devkitpro；runtime/main.c（libnx 进程循环、手柄/触摸、audren 音频、framebuffer、vsync 60fps、newlib stdio 读文件）用 aarch64-none-elf-gcc 以 -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE 编译，再用 libnx switch.specs 链接 -lnx -lm 得 rfvp.elf，最后 elf2nro --nacp 输出 target/rfvp-switch/switch/rfvp.nro。
  - CI：.github/workflows/console-artifacts.yml 用 docker/build-push-action 构建 platform/docker/Dockerfile.console 的 console-switch 目标，跑 bash platform/consoles/build-executable.sh switch，上传 artifact rfvp-switch（dist/consoles/rfvp.nro）；push 默认分支时推 ghcr.io/OWNER/rfvp-switch-builder 镜像。
- 构建入口与产物: ./platform/switch/build_switch.sh（固定工具链后）→ target/rfvp-switch/switch/rfvp.nro；无桌面依赖，NRO 独立运行；可执行文件版本取自 platform/switch/host/Cargo.toml（0.1.0）。
- README 声称（README 声称）: 标题「rfvp: A Non-Official Rust cross-platform implementation of the FVP engine and IDE.」；Console support 截图「These are game frames captured from RFVP running in emulators.」（Switch 用 Ryujinx）；平台表第 137 行「| Switch | Standalone (.nro) | No | Yes | arm64-v8a | Experimental |」；状态说明：Experimental（PS Vita, Switch）——这两个后端「build on every change that touches them, and the core they run boots, plays and saves a real game in a desktop test host, but they have not been run on a console」（README 截断处原文如此，platform/switch/README.md 明确「It runs in Ryujinx at 60 fps with picture and sound; it has not been run on a console yet.」）；主机端无启动器，读游戏目录 config.toml（hcb 指定脚本；错误写 last_error.txt 带行号；不同 hcb 存档按脚本名分开）；翻译仅 UTF-8 与 GBK，需切换 Nls；安装布局 sdmc:/switch/rfvp/{rfvp.nro, game/*.hcb,*.bin,default.ttf, save/}，可选 nls.txt；存档 rfvp_sNNN.bin + rfvp_global.bin（约每 2 分钟、每次存档和退出时写），与桌面版编码不兼容；软件光栅器 SoftRaster 渲染 1280x720 并缩放加黑边；控制映射（A/B/X/Y、L/R/ZL/ZR=Ctrl 跳过、+/−、十字键+左摇杆、触摸）。
- 已知限制: Switch 从未在真机运行（README 明确）；软件光栅化 1280x720（画质/性能受限）；需要用户自备 FVP 游戏 *.hcb/*.bin 与 CJK default.ttf（引擎不自带）；存档与桌面版不兼容；无启动器；无 debug HUD（桌面 F2）；翻译仅 UTF-8/GBK。
- 健康: archived=false；stars 151、forks 24；open PR 2、merged PR 23；GraphQL issues totalCount=2（含 PR，故纯 open issue 为 0；closed issues 30 含已合并/关闭 PR）；releases 6：pre-release（2026-10-25T14:30:48Z，isPrerelease=true，资产全为桌面/移动端——rfvp-wasm.zip 17,974,655、rfvp-freebsd-x86_64.tar.gz 22,369,002、BOOTX64.EFI 29,758,464、rfvp-linux-x86_64.tar.gz 23,668,249、rfvp-linux-aarch64.tar.gz 23,862,955、BOOTAA64.EFI 29,551,616、RFVP.dmg 49,852,605、RFVPLauncher.ipa 19,877,647、rfvp_arm64.exe 44,405,248、rfvp.exe 46,578,688；无 Switch .nro）、0.7.0（2026-10-19T06:14:00Z，无资产）、0.6.0（2026-09-09）、0.5.0（2026-07-11）、0.4.0（2026-05-15）、0.3.0（2026-03-30，prerelease，无资产）。
- 许可证: LICENSE（16,725 B）= Mozilla Public License 2.0 全文 → SPDX MPL-2.0；文件级 copyleft（修改 MPL 文件需公开该文件源码）；README 免责声明：纯逆向重实现、须持有正版游戏、禁止分发游戏数据/资源/内嵌可执行文件，原权利方保留全部 IP；不包含任何原版源码或游戏资源。
- 未验证 / 风险: Switch NRO 仅 CI artifact/本地构建可得（releases 无 NRO 资产）；未核验 CI artifact 实际下载可用性；未在真机验证（作者自述仅 Ryujinx）；nightly 工具链 pin（nightly-2026-02-01）+ build-std 使构建对工具链演进敏感；软件光栅化性能上限；FVP 游戏/字体需用户自备，无合法免费测试资源可用（本轮未能找到）。
- 来源 URLs: https://github.com/xmoezzz/rfvp ；https://raw.githubusercontent.com/xmoezzz/rfvp/main/README.md ；https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/switch/README.md ；https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/switch/build_switch.sh ；https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/consoles/toolchain.env ；https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/switch/aarch64-nintendo-switch-rfvp.json ；https://raw.githubusercontent.com/xmoezzz/rfvp/main/.github/workflows/console-artifacts.yml ；https://raw.githubusercontent.com/xmoezzz/rfvp/main/LICENSE ；https://github.com/xmoezzz/rfvp/releases ；https://api.github.com/repos/xmoezzz/rfvp

## 可复现构建前置条件矩阵

| 仓库 | 构建入口 | 必需工具链 | devkitPro / portlibs 依赖 | 仓库外下载物 / 子模块 | 运行时数据 / 密钥 | 本机缺口（本轮未安装） |
| --- | --- | --- | --- | --- | --- | --- |
| DrFlyingPig/krkr-ns | bash build_nro.sh（需先 bash tools/build_ffmpeg_switch.sh） | devkitPro devkitA64、libnx、switch-tools、CMake 3.31.6、Ninja、pkg-config、Python（内联 patch） | sdl2 portlibs（pkg-config REQUIRED）；vendored krkrsdl2 + krkrz + FAudio + simde + plutovg + zlib（无需在线子模块） | FFmpeg 7.1 tar.xz（SHA256 固定）+ ffmpeg-horizon.patch；仓库外的 Switch.toolchain.cmake（KRKR-ns-tools）；默认路径指向兄弟仓库 ../WA2-ns | 游戏 .xp3（用户自备）；无构建密钥 | devkitPro/dkp-pacman、CMake 外部工具包、Ninja 已有、make 缺、无 FFmpeg 源码包 |
| jvrcruzGAMES/RenpySwitch | bash setup.bash → bash build.bash（Docker: devkitpro/devkita64:20230910） | devkitPro devkitA64 20230910、Ubuntu 24.04、CMake、pkg-config、Cython 3.0.10、venv | switch-dev、SDL2 全家桶、ffmpeg、freetype、curl、mbedtls、lzma、zstd、zlib、bzip2、mesa、glad、libdrm_nouveau、fribidi 1.0.12-1、pkgbuild-helpers 2.2.4-2 | Ren'Py 8.3.4 sdk/source、pygame_sdl2 2.1.0、NXPython（CPython 3.14，pin 1b1c61a）；无 sha256 校验 | 游戏工程（用户自备）；无密钥 | Docker 缺、devkitPro 缺；PNG/图标工具（icoutils/wrestool）未装 |
| Otorhin/Ren2Switch | bash setup.bash → bash build.bash（容器 devkitpro/devkita64:20221113） | devkitPro devkitA64 20221113、python2.7 + pip2、CMake、pkg-config | 同上 SDL2/ffmpeg 组；python27-switch、helpers 2.2.3-1、fribidi 1.0.12-1（Otorhin/scripts oof release） | Ren'Py 7.6.1 sdk/source、pygame_sdl2 2.1.0、android-native-symbols.zip、rawproject.zip（dl.otorh.in） | 游戏工程（用户自备）；无密钥 | python2.7 不可用、Docker 缺、devkitPro 缺 |
| clamintus/ONScripter-NX | make（可选 make ENABLE_HD=1）；先 make -f Makefile.extlibs | devkitPro、GNU make、devkitPro 工具链 | switch-dev、switch-sdl2、switch-sdl2_image、switch-sdl2_mixer、switch-sdl2_ttf、switch-smpeg2、switch-libvorbis；链接另需 EGL/glapi/drm_nouveau/freetype/harfbuzz/bz2/png16/jpeg/webp/modplug/mpg123/opusfile/opus、patch 与 dkp-toolchain-vars（仅 extlibs） | extlibs/SDL2_ttf（PKGBUILD + bug1433.patch，仓库内）；无在线子模块 | NScripter 游戏数据（arc*.nsa/.sar、nscript.dat）与 default.ttf（用户自备，禁止用 release 内商业数据） | devkitPro 缺、make 缺；switch-* 包未装 |
| xmoezzz/rfvp | ./platform/switch/build_switch.sh（CI 用 Dockerfile.console） | devkitPro（devkitA64、libnx、switch-tools）、rustup + nightly-2026-02-01 + rust-src、cargo build-std、cc | libnx（无额外 portlibs） | crates.io 依赖（Cargo.lock 锁定）；ghcr.io 构建镜像（CI 用） | FVP 游戏 *.hcb/*.bin + CJK default.ttf（用户自备）；无密钥 | rustup/cargo 缺、Docker 缺、devkitPro 缺 |

说明：本机（2026-10-29）已装 git/node/python/cmake/ninja/clang 等，但缺 devkitPro/dkp-pacman、Docker、cargo/rustup、make、7z；按本轮禁令未安装任何软件、未执行构建。

## 第一款原型接入排序（基于证据）

**结论：第一款原型选 DrFlyingPig/krkr-ns，不选 jvrcruzGAMES/RenpySwitch。**

排序：

1. DrFlyingPig/krkr-ns（第一）——理由：
   - 许可证干净：仓库 MIT（LICENSE 原文 MIT 全文），vendored krkrsdl2/krkrz 为 KiriKiri Z 自定义宽松许可（BSD-3 风格，非 GPL），不阻碍 GalNX 以宽松许可分发框架代码；发布 NRO 内 FFmpeg 为 --disable-gpl 的 LGPL 模式，需补 LGPL 合规材料但可解。
   - 有可立即试跑的 release 工件（v0.1.0 的 krkrsdl2.nro 29.6 MB），可在不先解决构建的情况下评估引擎行为；计划草案 L251 已将其列为优先研究样板。
   - 维护活跃（2026-10-16 最后提交、21★、2 open issues），README 详述真机使用（完整内存模式 HBMenu、ASCII 路径）与功能边界（视频不支持变速/多音轨），已知限制写得比同类清楚。
   - 代价：构建可复现性差（外部 Switch.toolchain.cmake、FFmpeg 脚本默认指向兄弟仓库 WA2-ns、release 与 tag 时间线矛盾）→ 第一批工作应是「固定 source commit + 自建工具链 + 发布自构建 NRO 并记录 SHA256」，而非直接信任 release 资产。
2. clamintus/ONScripter-NX（第二）——构建最简单（make + libnx switch_rules，单 Makefile），release 有真机向测试声明（Tsukihime/Kagetsu Tohya），但 GPL-2.0-or-later 要求 GalNX 侧接受 copyleft（链接/派生需 GPL 兼容）；且 release 内含商业游戏数据（禁止复用）。若 GalNX 计划开源（GPL 兼容）则它是最低构建门槛的验证对象。
3. xmoezzz/rfvp（第三，研究项）——MPL-2.0 干净、活跃、架构清晰（Rust no_std + libnx runtime），但 Switch 后端明确 Experimental 且从未真机运行，release 无 NRO，需 pin nightly 工具链；只适合作为长期研究对象，不宜作第一个里程碑依赖（与计划草案 L255 一致）。
4. jvrcruzGAMES/RenpySwitch（暂缓，仅参考）——工程上它其实是四个 Ren'Py 相关仓库里构建流水线最完整、最可复现的（Docker 镜像固定、CI、setup/build/pack 全脚本、NRO+NSP 打包），但**仓库无任何许可证（All rights reserved）、NXPython 亦无许可证、父仓库同无**，且 2026-08-09 创建后无 release/tag、无真机运行声明。在取得作者书面授权/许可前，不得把其代码或产物纳入 GalNX。若目标是 Ren'Py 游戏且能拿到授权，它应升级为第一候选。
5. Otorhin/Ren2Switch（末位，仅历史对照）——2023-09 停更、无许可证、父仓库已 archived、依赖 python2.7 与外部下载站、tags 全部为上游遗留，技术与法律风险均最高。

为什么不是 RenpySwitch：其唯一优势是构建流水线可复现性（Docker+CI），但许可证缺失是硬阻塞（不能 fork/再分发/随框架发布），且仓库仅 1 天工作量、无 release、未声明真机运行；相比之下 KRKR-ns 许可证干净、有实测可用的 release NRO 与活跃维护，风险更可控。

## 可用于测试的合法资源候选（均需用户最终核实）

1. Ren'Py 官方 demo：the_question 与 tutorial（随 Ren'Py SDK 8.3.4/7.6.1 分发；源码在 https://github.com/renpy/renpy 的 the_question/ 与 tutorial/ 目录）。Ren'Py 许可文件（sphinx/source/license.rst）说明：由未修改的正式版 Ren'Py 生成的工程文件（如 game/gui.rpy、game/options.rpy）以 CC0 1.0 贡献公共领域；同时「The artwork in the demo is released by various copyright holders, under the same terms.」→ demo 美术由多个版权方按各自条款发布。可用于本地功能测试；若要把 demo 随 GalNX 再分发，需逐项核实美术版权。URL: https://github.com/renpy/renpy/tree/master/the_question （本轮未抓取该页面，仅从仓库根树与 license.rst 原文确认目录存在）。
2. Narcissu（NScripter 免费游戏，英文翻译版由 insani 发布）——适合 ONScripter-NX 测试；官网 http://alltogether.insani.org/narcissu.html（本轮 HTTPS 抓取未成功，因代理仅支持 https 目标；条款未核实）。免费下载不等于允许再分发/修改，需用户自行确认许可后再用于 GalNX 测试。
3. Ren'Py 免费游戏 Katawa Shoujo（https://www.katawa-shoujo.com/，免费下载，Ren'Py 引擎；本轮未抓取，再分发/修改条款未核实）——适合 Ren'Py 分支的端到端打包测试；若仅本地测试不随 GalNX 分发，风险较低，但商业/非商业使用与改编条款须用户核实。
4. 合成测试样本（推荐兜底）：用 krkrsdl2/ONScripter 自带样例脚本 + CC0 素材（如 CC0 图片/音频）自建最小 .xp3 或 NScripter 数据目录——不涉及第三方版权，是可长期保留的回归测试基线。
5. 明确禁止作为测试资源：ONScripter-NX release 内的 tsukihime.zip / kagetsu_tohya.zip 等为商业游戏数据（作者自行附带，GalNX 不得下载、复用或再分发）；rfvp 无官方免费 FVP 游戏，README 要求必须持有正版游戏副本，禁止分发游戏数据。

## 未验证 / 失败项

- 全局：web_fetch 工具在本会话不可用（DeepSeek API 404），改用 env_download 抓 raw 文件；web_search 对 Ren'Py demo 许可、Narcissu 再分发条款、免费 KiriKiri 游戏无可用返回（仅噪音来源），相关许可均标「需用户核实」。
- krkr-ns：release v0.1.0 tag 与发布时间矛盾（tag 指向 2026-10-16 的 HEAD，release 2026-09-14）→ NRO 资产无法溯源；krkrsdl2 基线 bf207f2 无法用文件哈希证明；Switch.toolchain.cmake 不在仓库内，未核验；未执行构建。
- RenpySwitch：无许可证（未授权）为记录事实而非失败；Ren'Py SDK/pygame_sdl2 下载无 SHA256 校验；未查 CI Actions runs 结论；未真机运行；README 无真机/模拟器声明。
- Ren2Switch：dl.otorh.in 与 Otorhin/scripts oof release 的可用性未验证；python2.7 在现代 ubuntu-latest 容器中的安装可行性未验证；未查 CI 结论。
- ONScripter-NX：未下载/解包 release zip（避免触碰商业游戏数据），NRO 内容未核验；Sazanami Gothic 字体许可条款未取得（字体文件内无 license 字段）；extlibs/SDL2_ttf 的 bug1433.patch 未逐行审阅；首次按 source/switch_mitm.h 取文件得 HTTP 404，后确认实际路径为 include/switch_mitm.h。
- rfvp：未核验 CI artifact 可下载性；未在 Ryujinx/真机运行；未验证 nightly-2026-02-01 工具链安装与构建；未找到可合法分发的 FVP 测试游戏。
- 所有仓库未在 Nintendo Switch 真机验证（本轮为只读审计，不涉及硬件、密钥、固件）。

## 对 GalNX 的建议

1. 版本锁定（建议写入后续工具链清单）：
   - krkr-ns：锁定源码 commit 949faf9a874f54b149a3fe5382cfccb38afb99bb（MIT）；不要以 release v0.1.0 的 NRO 作为可信基线，改为自构建后记录 SHA256；同时把 Switch.toolchain.cmake、FFmpeg 7.1 tar.xz（sha256 40973d44...）、ffmpeg-horizon.patch 一并纳入内部镜像/缓存，消除对 ../WA2-ns 与 /d/KRKR-ns-tools 的隐式依赖；随 NRO 附 FFmpeg LGPL-2.1 源码 offer 与许可文本。
   - ONScripter-NX：锁定 v0.3.1 a8439a86393f74c503d28df176f010ca544af56f（GPL-2.0-or-later）；先做 GPL 合规决策（GalNX 若分发链接 ONScripter 的二进制，需以 GPL 兼容方式提供对应源码）；不得使用其 release 内的 tsukihime/kagetsu_tohya 数据包。
   - rfvp：锁定 0.7.0 99435f22e94eaec27c0c1b9f22cc2a6b1910d7d1（MPL-2.0）+ nightly-2026-02-01；作为研究项单独跟踪，不进入首里程碑关键路径。
   - RenpySwitch / Ren2Switch：license_spdx 为空（未授权），在取得作者书面许可前不得复制代码、不得随 GalNX 分发任何派生 NRO/NSP；可仅作只读参考实现。
2. 接入顺序：krkr-ns（第一款原型，验证 NRO 加载/存档/视频兼容）→ ONScripter-NX（第二，视 GPL 合规结论）→ rfvp（研究）→ Ren'Py 分支（许可证解决后）。Ren2Switch 不接入。
3. 阻塞项（进入实现阶段前必须解决）：
   - 许可证：RenpySwitch/Ren2Switch/NXPython/knautilus-RenpySwitch 均无许可证；需联系作者（jvrcruzGAMES、Otorhin）取得授权或替换为许可清晰的实现；ONScripter 的 GPL 兼容性需架构决策。
   - 工具链：构建机需 devkitPro（devkitA64 + libnx + switch-tools），本轮禁装；krkr-ns 还需外部 CMake/Ninja/pkg-config 打包与自建 FFmpeg。
   - 产物可追溯：所有 release 资产不可直接信任（krkr-ns tag 矛盾、rfvp 无 Switch 资产、Ren2Switch 无 release）；应改为源码构建 + 固定 SHA256 + 内部制品库。
   - 法律边界：不得随框架分发商业游戏数据（ONScripter release 内的 Tsukihime/Kagetsu Tohya 数据、任何 FVP/KRKR 商业游戏资源）；测试资源用官方免费 demo 或合成样本，并保留许可证据。
4. 建议下一轮（获准写代码后）首先产出：krkr-ns 固定 commit 的离线可复现构建脚本 + 自构建 NRO 的 SHA256 + 最小合成 .xp3 回归样本；同时启动 Ren'Py 分支的授权联系与替代方案评估（如仅使用 Ren'Py 官方 MIT/LGPL 代码自行构建，不依赖无许可的 Switch 补丁仓库）。

<!-- AUDIT-JSON-BEGIN -->
```galnx-audit
[
  {
    "name": "DrFlyingPig/krkr-ns",
    "url": "https://github.com/DrFlyingPig/krkr-ns",
    "default_branch": "main",
    "head_sha": "949faf9a874f54b149a3fe5382cfccb38afb99bb",
    "head_date": "2026-10-16",
    "pinned": "v0.1.0 tag -> 949faf9a874f54b149a3fe5382cfccb38afb99bb (2026-10-16); release v0.1.0 published 2026-09-14",
    "license_spdx": "MIT",
    "license_file": "LICENSE",
    "license_notes": "仓库根 LICENSE 为 MIT 全文（Copyright (C) Kirikiri SDL2 Developers）；GitHub /license 判 NOASSERTION 但原文为 MIT。vendored krkrsdl2/krkrz 及插件为 KiriKiri Z 自定义宽松许可（BSD-3 风格，非 GPL）；FAudio 为 zlib 风格；发布 NRO 内含 tools/build_ffmpeg_switch.sh 以 --disable-gpl（LGPL 模式）构建的 FFmpeg 7.1 子集，仓库未附 FFmpeg 源码/许可文本，再分发需补 LGPL-2.1 合规材料。",
    "archived": false,
    "last_push": "2026-10-16",
    "stars": 21,
    "open_issues": 2,
    "build_system": "CMake + Ninja（krkrsdl2，NINTENDO_SWITCH=ON）+ devkitPro libnx + elf2nro；入口 build_nro.sh；FFmpeg 需先由 tools/build_ffmpeg_switch.sh 交叉构建",
    "build_deps": "devkitPro devkitA64、libnx、switch-tools、SDL2 portlibs（pkg-config sdl2 REQUIRED）、FAudio（vendored，zlib 许可）、krkrz（vendored；freetype/jxrlib/libjpeg-turbo/lpng/onig/zlib）、simde、plutovg、zlib、FFmpeg 7.1 自建子集、CMake 3.31.6、Ninja、pkg-config、Python（build 脚本内联 patch）、外部 Switch.toolchain.cmake（不在仓库）",
    "readme_claims": "吉里吉里/KiriKiri Switch 移植，实验性、稳定性无保证；基线 krkrsdl2 bf207f2 + krkrz b11c43a；支持常见 KRKR/KAG 游戏、xp3 入口、多资源包、快速存读档、补丁/翻译优先、中日本地化与字体兼容、脚本解密尝试、E-mote/AlphaMovie/LayerExRaster、部分 WMV/MP4/MPEG 视频与 WAV/OGG/Opus/AAC/M4A/MP3 音频（视频不支持变速与多音轨）；真机需完整内存模式 HBMenu（按住 R 进已安装游戏）；真机游戏路径不能含中文；不包含也不分发任何商业游戏资源。",
    "readme_claim_url": "https://github.com/DrFlyingPig/krkr-ns/blob/main/README.md",
    "risks": "release NRO 与 tag 时间线矛盾（tag 指向 2026-10-16 HEAD，release 发布于 2026-09-14）→ 资产不可溯源；构建依赖仓库外 /d/KRKR-ns-tools（含自定义 Switch.toolchain.cmake）与兄弟仓库 ../WA2-ns 默认路径；无 CI；FFmpeg 脚本默认路径未固化；NRO 含 LGPL FFmpeg 需补合规；实验性稳定性；真机路径须 ASCII。",
    "verification_level": "source-inspected",
    "verification_failures": "krkrsdl2 基线 bf207f2 无法用文件哈希证明（本仓库 CMakeLists.txt 哈希 1f15ee38e747 与上游 bf207f2 的 c55d6b6cc95a 不同）；release v0.1.0 与 tag 时间线矛盾，NRO 资产未能溯源；Switch.toolchain.cmake 未随仓库提供，无法核验；未执行构建。",
    "source_urls": [
      "https://api.github.com/repos/DrFlyingPig/krkr-ns",
      "https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/README.md",
      "https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/LICENSE",
      "https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/build_nro.sh",
      "https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/tools/build_ffmpeg_switch.sh",
      "https://raw.githubusercontent.com/DrFlyingPig/krkr-ns/main/compat-patches/README.md",
      "https://github.com/krkrsdl2/krkrsdl2",
      "https://github.com/krkrsdl2/krkrz",
      "https://github.com/DrFlyingPig/krkr-ns/releases"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "jvrcruzGAMES/RenpySwitch",
    "url": "https://github.com/jvrcruzGAMES/RenpySwitch",
    "default_branch": "master",
    "head_sha": "7824039a7d0353b7bfa79ddfcecbf30a375d3d62",
    "head_date": "2026-08-10",
    "pinned": "无 tag/release; pin HEAD 7824039a7d0353b7bfa79ddfcecbf30a375d3d62",
    "license_spdx": "",
    "license_file": "",
    "license_notes": "仓库无任何许可证文件；GitHub license API 返回 null；fork 自 knautilus/RenpySwitch（同样无许可证）；依赖 jvrcruzGAMES/NXPython（无许可证）；上游 Ren'Py 本体 MIT + LGPL 部分、pygame_sdl2 LGPL-2.1。无授权不得再分发 fork 或派生物。",
    "archived": false,
    "last_push": "2026-08-10",
    "stars": 2,
    "open_issues": 0,
    "build_system": "GitHub Actions（ubuntu-24.04 + docker devkitpro/devkita64:20230910）+ bash setup.bash/build.bash；switch/CMakeLists.txt 交叉编译 .nso；pack_nro.bash/pack_nsp.bash 打包 NRO/NSP",
    "build_deps": "devkitPro devkitA64 20230910（switch-dev + SDL2 全家桶 + switch-ffmpeg + freetype + curl/mbedtls/lzma/zstd/zlib/bzip2 + fribidi 1.0.12-1 + devkitpro-pkgbuild-helpers 2.2.4-2）；NXPython（CPython 3.14 静态库，pin 1b1c61a94f0685bb0be707b5374376f3084159fe）；Ren'Py SDK/source 8.3.4；pygame_sdl2 2.1.0；Cython 3.0.10；Ubuntu 24.04；icoutils；7z；CMake；libnx tools",
    "readme_claims": "Ren'Py on Switch 构建流水线（GitHub Actions + NXPython）：下载 Ren'Py 8.3.4 源码与 SDL2 bindings、打 Switch 补丁、Cython 编译、打包 lib.zip、交叉编译 .nso、组装 raw/ 空白 Switch 工程；提供 pack_nro.bash/pack_nsp.bash 打包游戏；本地构建需 Linux（Docker/WSL2）。README 未声称已在真机运行。",
    "readme_claim_url": "https://github.com/jvrcruzGAMES/RenpySwitch/blob/master/README.md",
    "risks": "无许可证（法律阻塞，All rights reserved）；仓库极新（2026-08-09 创建，约 1 天工作量）、无 release/tag、无真机/模拟器运行声明；NXPython 与父仓库同样无许可证；Ren'Py SDK/pygame_sdl2 下载无 sha256 校验；CPython 3.14 交叉构建重；未说明存档/字体/视频兼容性。",
    "verification_level": "source-inspected",
    "verification_failures": "未核验 CI Actions runs 结论；未验证 Ren'Py SDK/pygame_sdl2 下载 URL 可用性与哈希；未验证真机运行状态（README 未声明）；NXPython 无许可证无法审计其合规性。",
    "source_urls": [
      "https://api.github.com/repos/jvrcruzGAMES/RenpySwitch",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/README.md",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/setup.bash",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/build.bash",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/switch/CMakeLists.txt",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/.github/workflows/main.yml",
      "https://github.com/knautilus/RenpySwitch",
      "https://github.com/jvrcruzGAMES/NXPython"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "Otorhin/Ren2Switch",
    "url": "https://github.com/Otorhin/Ren2Switch",
    "default_branch": "master",
    "head_sha": "5fce4a28afaa1df262876b7bcce0bee10b3a0360",
    "head_date": "2023-09-04",
    "pinned": "无 release；pin HEAD 5fce4a28afaa1df262876b7bcce0bee10b3a0360；最新 tag v1.7.5 为上游遗留（e41dfbe5ee77e9ad673bb4d2854f5983d5f05935, 2020-12-20）",
    "license_spdx": "",
    "license_file": "",
    "license_notes": "仓库无任何许可证文件；GitHub license API 返回 null；fork 自 uyjulian/renpy-switch（isArchived=true，无许可证）；依赖 Ren'Py 7.6.1 / pygame_sdl2 2.1.0（Ren'Py MIT+LGPL、pygame_sdl2 LGPL-2.1）。未授权不得再分发。",
    "archived": false,
    "last_push": "2023-09-04",
    "stars": 12,
    "open_issues": 0,
    "build_system": "GitHub Actions ubuntu-latest + devkitpro/devkita64:20221113；bash setup.bash/build.bash（python2 工具链）；switch/CMakeLists.txt",
    "build_deps": "devkitPro devkitA64 20221113、python2.7 + pip2、python27-switch（Otorhin/scripts oof release）、devkitpro-pkgbuild-helpers 2.2.3-1、switch-libfribidi 1.0.12-1、SDL2 全家桶、ffmpeg 库、Ren'Py 7.6.1 sdk/source、pygame_sdl2 2.1.0、android-native-symbols.zip、rawproject.zip（dl.otorh.in）、p7zip、cmake",
    "readme_claims": "俄文：仓库包含在 Switch 运行 RenPy 所需文件，兼作 GitHub Actions 构建器（下载 RenPy/PyGame 源码、Android .so、打补丁、编译、打包 lib.zip、组装 PC/Android/Switch 空白工程）；README 未完成；未声明真机运行状态。",
    "readme_claim_url": "https://github.com/Otorhin/Ren2Switch/blob/master/README.md",
    "risks": "无许可证；2023-09 后停更；依赖 python2.7 与现代 Ubuntu 已移除的旧包；依赖外部下载站 dl.otorh.in 与 Otorhin/scripts（可用性未核验）；tags 全部为上游 2019-2020 遗留；无 release；父仓库已 archived。",
    "verification_level": "source-inspected",
    "verification_failures": "未验证 dl.otorh.in 与 Otorhin/scripts 下载可用性；未验证 python2.7 在现代 ubuntu-latest 容器中可安装；未核验 CI Actions runs 结论；未执行构建。",
    "source_urls": [
      "https://api.github.com/repos/Otorhin/Ren2Switch",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/README.md",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/setup.bash",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/build.bash",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/switch/CMakeLists.txt",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/.github/workflows/ci.yml",
      "https://github.com/uyjulian/renpy-switch"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "clamintus/ONScripter-NX",
    "url": "https://github.com/clamintus/onscripter-nx",
    "default_branch": "main",
    "head_sha": "a8439a86393f74c503d28df176f010ca544af56f",
    "head_date": "2026-01-14",
    "pinned": "v0.3.1 @ a8439a86393f74c503d28df176f010ca544af56f (2026-01-14)",
    "license_spdx": "GPL-2.0-or-later",
    "license_file": "COPYING",
    "license_notes": "COPYING=GNU GPL v2 文本；source/ONScripterLabel.cpp 与 source/switch_mitm.cpp 头均声明 GPL v2 or later（either version 2 of the License, or (at your option) any later version）→ GPL-2.0-or-later（GitHub licenseInfo=GPL-2.0）。分发修改版 NRO 必须提供完整对应源码并保留声明。romfs/default.ttf 为 Sazanami Gothic（efont，版权 Wada Laboratory），字体未内嵌许可条款需单独核实；release 附带 Tsukihime/Kagetsu Tohya 商业游戏数据 zip，GalNX 不得复用。",
    "archived": false,
    "last_push": "2026-01-15",
    "stars": 37,
    "open_issues": 0,
    "build_system": "Makefile（devkitPro libnx switch_rules）+ make（可选 ENABLE_HD=1）；Makefile.extlibs 重打 SDL2_ttf PKGBUILD（bug1433.patch）",
    "build_deps": "devkitPro switch-dev、switch-sdl2、switch-sdl2_image、switch-sdl2_mixer、switch-sdl2_ttf、switch-smpeg2、switch-libvorbis；链接还需 EGL/glapi/drm_nouveau/freetype/harfbuzz/bz2/png16/jpeg/webp/modplug/mpg123/opusfile/opus 等 portlibs；patch 与 dkp-toolchain-vars（仅 extlibs）",
    "readme_claims": "移植 onscripter-20060724-insani-sdl2 到 Switch，专门支持在新版 ONScripter/ONScripter-EN 会出问题的老 NScripter 游戏；4:3 模拟、触摸支持、RomFS 内嵌、优化 flush；已测 Tsukihime/Kagetsu Tohya，声称任何 legacy ONScripter 游戏应可运行；v0.3+ 支持 HD（仅缩放、CPU 负担增加、输入延迟、跳过变慢）；devkitPro pacman 的 switch-sdl2_ttf 有 bug 导致文字显示异常，需 Makefile.extlibs 修复；License 仅写 See COPYING。",
    "readme_claim_url": "https://github.com/clamintus/ONScripter-NX/blob/main/README.md",
    "risks": "GPL 传染性（GalNX 若链接/派生需整体 GPL 兼容，闭源分发不可行）；release 内嵌 Tsukihime/Kagetsu Tohya 商业游戏数据（作者侧再分发，GalNX 禁止复用）；Sazanami Gothic 字体许可未核实；HD 模式性能与输入延迟；硬编码 /opt/devkitpro 路径；switch-sdl2_ttf 需从源码重打包；无 CI，构建未自动验证。",
    "verification_level": "source-inspected",
    "verification_failures": "未下载/解包 release zip（避免触碰商业游戏数据），NRO 内容未核验；Sazanami Gothic 字体许可条款未取得（name 表无 nameID 13/14）；extlibs/SDL2_ttf 的 bug1433.patch 未逐行审阅；source/switch_mitm.h 首次按 source/ 路径取文件 HTTP 404，后确认实际路径为 include/switch_mitm.h。",
    "source_urls": [
      "https://api.github.com/repos/clamintus/ONScripter-NX",
      "https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/README.md",
      "https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/COPYING",
      "https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/Makefile",
      "https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/Makefile.extlibs",
      "https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/source/ONScripterLabel.cpp",
      "https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/source/switch_mitm.cpp",
      "https://raw.githubusercontent.com/clamintus/ONScripter-NX/main/romfs/default.ttf",
      "https://github.com/clamintus/onscripter-nx/releases",
      "https://github.com/clamintus/onscripter-20060724-insani-sdl2"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "xmoezzz/rfvp",
    "url": "https://github.com/xmoezzz/rfvp",
    "default_branch": "main",
    "head_sha": "9f07adef2eb5d559777f9bf59a67b756875cb24f",
    "head_date": "2026-10-25",
    "pinned": "0.7.0 @ 99435f22e94eaec27c0c1b9f22cc2a6b1910d7d1 (2026-10-19)；Switch NRO 不在 release，需 CI artifact 或本地构建",
    "license_spdx": "MPL-2.0",
    "license_file": "LICENSE",
    "license_notes": "LICENSE 为 MPL-2.0 全文；文件级 copyleft（修改 MPL 文件需公开该文件源码）；README 免责声明：逆向重实现、需持有正版游戏、禁止分发游戏数据/资源/内嵌可执行文件，原权利方保留全部 IP，仓库不含原版源码或游戏资源。Rust 依赖（crates.io）各自许可未逐项审计。",
    "archived": false,
    "last_push": "2026-10-25",
    "stars": 151,
    "open_issues": 0,
    "build_system": "Cargo（nightly-2026-02-01 + rust-src + 自定义 aarch64-nintendo-switch-rfvp target + -Zbuild-std）+ devkitPro libnx runtime/main.c + elf2nro；入口 platform/switch/build_switch.sh；CI 用 Dockerfile.console（ghcr.io 镜像）",
    "build_deps": "devkitPro devkitA64/libnx/switch-tools、rustup + nightly-2026-02-01 + rust-src、cargo build-std（core/alloc/compiler_builtins）、cc crate；运行需游戏 *.hcb/*.bin + CJK default.ttf + save/（不自带）；可选 nls.txt/config.toml",
    "readme_claims": "FVP 引擎与 IDE 的非官方 Rust 跨平台实现；Switch 为 Standalone .nro（arm64-v8a）状态 Experimental：CI 每次改动都构建、核心在桌面测试宿主能启动/运行/存档真实游戏，但尚未在主机上运行；截图来自模拟器（Switch 为 Ryujinx）；无启动器，读游戏目录 config.toml；需自备合法游戏；MPL-2.0；软件光栅器 1280x720；存档与桌面版不兼容。",
    "readme_claim_url": "https://github.com/xmoezzz/rfvp/blob/main/README.md",
    "risks": "Switch 从未真机验证（README/platform/switch/README.md 明确）；release 无 Switch NRO 资产，仅 CI artifact/本地构建；nightly 工具链 pin（2026-02-01）与 build-std 对演进敏感；软件光栅化 1280x720 性能/画质上限；需用户自备 FVP 游戏与 CJK 字体；逆向重实现兼容性未全覆盖；无合法免费 FVP 测试资源。",
    "verification_level": "source-inspected",
    "verification_failures": "未核验 CI artifact 实际可下载；未在 Ryujinx/真机运行；未验证 nightly-2026-02-01 安装与构建；未找到可合法分发的 FVP 测试游戏；releases 无 Switch .nro 资产（仅桌面/移动端）。",
    "source_urls": [
      "https://api.github.com/repos/xmoezzz/rfvp",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/README.md",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/switch/README.md",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/switch/build_switch.sh",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/consoles/toolchain.env",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/platform/switch/aarch64-nintendo-switch-rfvp.json",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/.github/workflows/console-artifacts.yml",
      "https://raw.githubusercontent.com/xmoezzz/rfvp/main/LICENSE",
      "https://github.com/xmoezzz/rfvp/releases"
    ],
    "audited_at": "2026-10-29"
  }
]
```
<!-- AUDIT-JSON-END -->
