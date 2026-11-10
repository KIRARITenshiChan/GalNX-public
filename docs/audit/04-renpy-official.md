# 集群 E（补充）：Ren'Py 官方源码与 Switch 独立移植可行性 审计（只读）

- 审计日期: 2026-10-29
- 审计员: audit-engines（Team Lead: lead；共享任务 task-6）
- 方法: GitHub REST v3 与 GraphQL v4（经 cred_use 携 GH_TOKEN，读仓库元数据/tag 对象/commit 日期/release 资产清单，UTC 日期）；raw.githubusercontent.com 原文经 env_download 走本机代理 http://127.0.0.1:7897 落盘后逐文件通读（README.rst/pyproject.toml/setup.py/run.sh/renpy.py/bootstrap.py/loader.py/audio.py/gl2shadercache.py/gl2draw.pyx/distribute.py/sphinx/source/{license,android,ios,web}.rst 等）；renpy-build 的 README/prepare.sh/build.sh/tasks/*.py/runtime/*.c 原文；四个社区移植的 README/setup.bash/build.bash/switch/CMakeLists.txt/CI/renpy.patch 原文（补丁仅统计文件与 hunk 数、阅读关键 hunk，不复制代码）；NXPython 的 README/build.sh/CPYTHON_COMMIT/patches 统计与关键行。全程只读：未安装任何软件/包、未构建/编译、未克隆仓库、未下载运行任何 release 二进制、未接触商业游戏数据/密钥/固件。本文件为第一轮审计的补充集群（用户新增 Ren'Py 方向），不修改 00–03 与索引文件（索引/合并由 Lead 决定）。
- 覆盖: 7 个条目（renpy/renpy、renpy/renpy-build、jvrcruzGAMES/NXPython、jvrcruzGAMES/RenpySwitch、knautilus/RenpySwitch、Otorhin/Ren2Switch、uyjulian/renpy-switch）

## 0. 结论先行（TL;DR）

1. **移植基线必须锁 8.5.3 发布线，不能用 master。** 官方 8.5.3.26051504 = commit 39895c1e017f0b36ffea2447d97eccd69d76ee1c（2026-05-16）仍用 **SDL2**（setup.py 的 pkg-config 依赖为 sdl2），而 master（pyproject version 8.99.99，HEAD 98401410…）已整体迁到 **SDL3**（packages="sdl3"、renpy/pygame 重写为 SDL3 绑定）。devkitPro 侧现成的是 switch-sdl2 2.28.5-4；switch-sdl3 的可用性本轮未验证。
2. **官方没有任何 Switch 目标，也明确不支持交叉编译。** README.rst 原文："Setup.py does not support cross-compiling. See https://github.com/renpy/renpy-build ..."；renpy-build 的 build.py 平台矩阵只有 linux（x86_64/aarch64）、windows（x86_64）、mac（x86_64/arm64）、android（x86_64/arm64_v8a/armeabi_v7a）、ios（arm64/模拟器）、web（wasm），**没有 switch**；runtime/librenpython.c 的平台宏只有 LINUX/MAC/WINDOWS/IOS/WEB。
3. **可行路径是"官方源码 + 自建 Switch 平台层"，不是"套用现成移植"。** 官方代码分层清楚（renpy/__init__.py 平台判定、renpy.py 路径、renpy/loader.py 文件、renpy/display/core.py 渲染器、renpy/audio/audio.py、renpy/bootstrap.py 启动），8.5.3 已把 pygame_sdl2 系 SDL2 绑定内置为 renpy.pygame.*（setup.py 直接编译 src/pygame/*.c），这比 8.3.4 时代（外部 pygame_sdl2 2.1.0）少一个移植件。
4. **真正硬骨头是 CPython 3.12.8 交叉编译到 devkitA64/newlib**（官方 pyproject requires-python ">=3.12.8,<3.13"）。jvrcruzGAMES/NXPython 用 299,892 B 的 CPython 3.14 补丁栈给出了"CPython 能在 Switch 上跑"的**存在性证据**（sys.platform == "nx"、romfs:/sdmc: 路径根语义），但该仓库**无许可证**（licenseInfo=null、/license 404），不能复用其代码；且 3.14 ≠ Ren'Py 8.5.3 要求的 3.12.x。次难是 SDL2/GLES 渲染与 ffmpeg 音频。
5. **四个社区 Ren'Py Switch 移植全部无许可证**（jvrcruzGAMES、knautilus、Otorhin、uyjulian 均为 /license 404、licenseInfo=null）→ **禁止直接接入、禁止复制其补丁**；只能作"需要改哪几层"的技术参考。uyjulian/renpy-switch 已 archived，README 建议改用 Switchroot Android + 官方 Ren'Py。
6. **建议幅度：不要把 Ren'Py 原生移植排进近期里程碑。** 先做 4–6 周、1–2 人的 go/no-go 探针（PC 侧官方构建 + Switch 上 CPython REPL + SDL2 窗口三件套）；探针通过再按 3–5 人月算最小可跑、6–12 人月算可发布。备选捷径是 Switchroot Android + 官方 Android 构建（法律最干净、工程最省，但不是原生 NRO/NSP）。

## 总览表

| 条目 | 用途 | 精确版本（tag/commit） | 许可证(SPDX) | 健康 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1. renpy/renpy | 官方引擎源码（移植基线） | 8.5.3.26051504 = 39895c1e（2026-05-16）；master 98401410（2026-10-29，8.99.99/SDL3） | MIT（含 LGPL 部分；无根 LICENSE，文本在 sphinx/source/license.rst） | 活跃：stars 6951、forks 957、open issues 251（含 48 PR，纯 issue 203）、release 44 | 基线锁 8.5.3；官方无 Switch 目标、不支持交叉编译 |
| 2. renpy/renpy-build | 官方跨平台构建系统（依赖版本锁定参照） | renpy-8.5.3.26051504 = 7bfab40c（2026-05-13）；master cff4919a（2026-10-26） | NOASSERTION（无 LICENSE、/license 404） | 活跃：stars 120、forks 85、open issues 16（含 9 PR）、releases 0、无 CI | 平台矩阵无 switch；脚本本身无许可证 → 只能参照不能复制 |
| 3. jvrcruzGAMES/NXPython | CPython 的 Switch 补丁栈（存在性证据） | HEAD 86cde186（2026-08-09）；CPYTHON_COMMIT 1b1c61a9 | NOASSERTION（无 LICENSE） | 弱：stars 0、单日仓库、无 tag/release | 证明 CPython 可在 Switch 跑，但无许可证不可复用；3.14≠8.5.3 要求 |
| 4. jvrcruzGAMES/RenpySwitch | 社区 Ren'Py 8.3.4 Switch 移植 | 无 tag/release；HEAD 7824039a（2026-08-10） | NOASSERTION（无 LICENSE） | 低：stars 2、forks 2；2026-08 更新 | 技术参考；无许可证禁止接入；基线 8.3.4 落后 |
| 5. knautilus/RenpySwitch | 社区 Ren'Py 7.6.3 移植（上一代） | 7.6.3_1.0 = d361e44f（2025-06-21） | NOASSERTION（无 LICENSE） | 低：stars 6、forks 4；最后 push 2026-02-07 | 技术参考；Python 2.7；无许可证 |
| 6. Otorhin/Ren2Switch | 社区 Ren'Py 7.6.1 移植（更早一代） | HEAD 5fce4a28（2023-09-04）；tag 继承上游 v1.7.5 = e41dfbe5 | NOASSERTION（无 LICENSE） | 停滞：2023-09 后无提交；stars 12 | 技术参考；Python 2；依赖托管在个人域名 |
| 7. uyjulian/renpy-switch | 2019–2020 的 Ren'Py Switch 移植（已归档） | v1.7.5 = e41dfbe5（2020-12-20）；landing HEAD 8a75ca3b（2022-01-04） | NOASSERTION（无 LICENSE） | 已归档：stars 70、7 open issues、14 releases | 不可用；官方建议改 Switchroot Android |

## 条目详情

### 1. renpy/renpy

- URL: https://github.com/renpy/renpy ；默认分支 master
- HEAD SHA: 98401410511152b98f2b38fecc942dc084f523eb ；提交日期 2026-10-29T03:38:36Z（pushed_at 2026-10-29T13:57:34Z；created_at 2012-06-28；仓库 size 233673 KB；描述 "The Ren'Py Visual Novel Engine"；homepage http://www.renpy.org/）
- 最近 tag/release: **8.5.3.26051504** = annotated tag oid 3c707741828458ce41ee76cd7b5b688a48eead56 → commit **39895c1e017f0b36ffea2447d97eccd69d76ee1c**（commit 日期 2026-05-16T01:14:41Z；tagger 时间 2026-05-15T21:39:18-04:00 = 2026-05-16T01:39:18Z；release "Ren'Py 8.5.3" published 2026-05-16T02:09:49Z）。次新 tag 8.5.3.26051401 = commit a9f46bff5f4768d94ecc3575e3ede89d23cb98c6（2026-05-15T02:32:34Z）。release 总数 44。
- release 资产（14 个，GraphQL 实抓名称+字节）：android-native-symbols.zip 88,772,150；renpy-8.5.3-sdk.tar.bz2 153,611,590；renpy-8.5.3-sdkarm.tar.bz2 166,255,505；renpy-8.5.3-source.tar.bz2 77,069,263；public_key.pem 178；updates.ecdsa 64；renpy-8.5.3-sdk.7z.exe 121,796,873；renpy-8.5.3-steam.zip 380,030；renpy-8.5.3-web.zip 12,938,159；renpy-8.5.3-rapt.zip 68,554,524；renpy-8.5.3-sdk.zip 163,008,121；renpy-8.5.3-renios.zip 129,711,186；renpy-8.5.3-sdk.dmg 156,995,588；checksums.txt 3,001。注：sdkarm 资产的目标架构本轮未取证（仅见文件名与大小），不能据此断言官方支持树莓派。
- 许可证（SPDX: MIT，但含 LGPL 部分）: **仓库无根目录 LICENSE 文件**（REST /license 404、GraphQL licenseInfo=null），许可证文本只存在于 `sphinx/source/license.rst`（master 102,253 B / 2,088 行）与 https://www.renpy.org/doc/html/license.html；master 的 pyproject.toml 用 PEP 639 写 `license = "MIT"`。license.rst 首段原文："Most of Ren'Py is covered by the terms of the following (MIT) license"；随后关键原文："Portions of Ren'Py are derived from source code that is licensed under the GNU Lesser General Public License, so Ren'Py games must be distributed in a manner that satisfies the LGPL."；LGPL 合规段原文把依赖源码位置限定为 renpy/renpy 与 renpy/renpy-build 两个仓库。**Generated Project Dedication**：未修改 Ren'Py 生成的新项目文件（game/gui.rpy、game/options.rpy、game/screens.rpy、game/script.rpy、game/gui 下图片）为 CC0 1.0 公有领域；引擎本身仍 MIT+LGPL+其他。依赖清单（license.rst 原文汇总）：LGPL（chardet、FFmpeg、Fribidi、libusb）、MPL-2.0（certifi）、Apache-2.0（requests、rsa）、Zlib（SDL2、SDL2_image、SDL2_ttf、Freetype、tinyfiledialogs、zlib）、3-clause BSD（ANGLE、libyuv、assimp、MetalANGLE、pysocks、websockets、xz）、Python License、AOM BSD+专利许可、Artistic（zsync）、Old MIT（harfbuzz）等。义务要点：分发 Ren'Py 或其衍生作品需保留 MIT 声明；LGPL 组件（FFmpeg、Fribidi 等）以静态库链接时需提供可重链接的目标文件/源码；生成项目文件可自由使用（CC0）。
- 健康: archived=false；last push 2026-10-29T13:57:34Z；stars 6,951；forks 957；open issues 251（GraphQL issues.totalCount 含 48 个 open PR → 纯 issue 203）；homepage http://www.renpy.org/；语言以 Python/Cython/C 为主。
- 构建系统: setuptools + Cython（`setup.py build_ext` 按 pkg-config 探测依赖；本机开发用 `uv sync` 建 venv 后 `./run.sh`）；pyproject.toml **无 build-system 段**（原文注释："For now, Ren'Py isn't using a build system, as build isolation makes building too slow."）。README.rst 明确 "Setup.py does not support cross-compiling. See https://github.com/renpy/renpy-build for software that cross-compiles Ren'Py for many platforms."；开发脚本假定 POSIX-like（Linux/macOS；Windows 需 MSYS）；可用 RENPY_CFLAGS/RENPY_LDFLAGS/RENPY_CC/RENPY_CXX/RENPY_LD 覆盖编译参数。
- 关键依赖（原文）: requires-python ">=3.12.8,<3.13"；运行时依赖 future>=1.0.0、six>=1.17.0、pefile>=2024.8.26、requests>=2.34.2、rsa>=4.9.1、chardet>=7.7.0、websockets>=17.3、pysocks>=1.7.1、certifi>=2026.10.23、jinja2>=3.1.6、truststore>=0.10.5；dev 组 setuptools>=84.2.1、cython>=3.3.0、pkgconfig>=1.6.0、ruff、sphinx、pytest。8.5.3 的 setup.py 显示 C 扩展分组：`_renpy`（src/IMG_savepng.c + src/core.c）、`renpy.pygame.*`（display/draw/surface/event/key/mouse/joystick/controller/time/power/transform/scrap/image/locals/color/rect/error/gfxdraw/iostream，源 src/pygame/SDL2_rotozoom.c、SDL_gfxPrimitives.c、write_jpeg.c、write_png.c、alphablit.c 等，pkg-config packages "sdl2"）、`renpy.audio.renpysound`（src/renpysound_core.c + src/ffmedia.c，packages "libavformat libavcodec libavutil libswresample libswscale sdl2"）、`renpy.text.ftfont`（src/ftsupport.c + ttgsubtable.c，packages "freetype2 harfbuzz"）、`renpy.text.bidi`（src/renpybidicore.c，packages "fribidi"）、`renpy.gl2.assimp`（src/assimpio.cc）。master 的 setup.py 改由 scripts.setuplib 生成，全部 packages="sdl3"。
- README 声称（README.rst 原文要点）: apt 依赖列表含 python3-dev、libassimp-dev、libav{codec,format,util,resample,scale}-dev、libharfbuzz-dev、libfreetype6-dev、libfribidi-dev、libsdl2-dev、libsdl2-{image,gfx,mixer,ttf}-dev、libjpeg-dev、pkg-config（注意：README 的 apt 列表对应 8.5.x 的 SDL2 时代，master 已迁 SDL3，文档滞后）；"Ren'Py requires SDL_image 2.6 or greater"；分支策略 fix（修补，自动并回 master）/master（下一版本）/work/history；建议 `uv sync`；编译模块用 `./run.sh`；Other Platforms 用 pkg-config 找 include/lib。贡献按 MIT 提交（可保留版权或转让给 Tom Rothamel）；README 含 AI 使用政策（不接受无人工审查的 agent 变更）。
- 未验证 / 风险: (a) master 已迁 SDL3，devkitPro 的 switch-sdl3 可用性未验证——若跟 master 会把 SDL3 一并引入风险；(b) 无根 LICENSE 文件，GitHub API 无法识别 SPDX，许可证结论基于 license.rst 原文（2088 行中第三方组件清单未逐项核对 SPDX）；(c) LGPL 组件（FFmpeg/Fribidi/chardet 等）静态链接时需准备可重链接机制与源码提供，法务成本实打实；(d) 官方无 Switch 平台分支，renpy/__init__.py 平台分组只有 windows/mac/linux/android/ios/web 六组；(e) 官方发布资产的 sdkarm 目标架构未验证；(f) 真机/模拟器运行未验证（本轮禁止构建）。
- 来源 URLs: https://github.com/renpy/renpy ; https://api.github.com/repos/renpy/renpy ; https://api.github.com/repos/renpy/renpy/releases/tags/8.5.3.26051504 ; https://api.github.com/graphql ; https://raw.githubusercontent.com/renpy/renpy/master/README.rst ; https://raw.githubusercontent.com/renpy/renpy/master/pyproject.toml ; https://raw.githubusercontent.com/renpy/renpy/8.5.3.26051504/setup.py ; https://raw.githubusercontent.com/renpy/renpy/master/setup.py ; https://raw.githubusercontent.com/renpy/renpy/master/sphinx/source/license.rst ; https://raw.githubusercontent.com/renpy/renpy/master/run.sh ; https://raw.githubusercontent.com/renpy/renpy/8.5.3.26051504/renpy/__init__.py ; https://raw.githubusercontent.com/renpy/renpy/master/renpy.py ; https://raw.githubusercontent.com/renpy/renpy/master/renpy/bootstrap.py ; https://raw.githubusercontent.com/renpy/renpy/master/renpy/loader.py ; https://raw.githubusercontent.com/renpy/renpy/master/renpy/audio/audio.py ; https://raw.githubusercontent.com/renpy/renpy/master/renpy/gl2/gl2shadercache.py ; https://raw.githubusercontent.com/renpy/renpy/master/renpy/gl2/gl2draw.pyx ; https://raw.githubusercontent.com/renpy/renpy/master/distribute.py

### 2. renpy/renpy-build

- URL: https://github.com/renpy/renpy-build ；默认分支 master
- HEAD SHA: cff4919ae0ff9976470dbc1d78a1a3ec7fb6432f ；提交日期 2026-10-26T05:55:15Z（pushed_at 2026-10-26T05:55:42Z；created_at 2018-01-01；仓库 size 558057 KB）
- 最近 tag: **renpy-8.5.3.26051504** = annotated tag oid 0cacf3957d4194e29f01c2c5bbb39bb9060b463a → commit **7bfab40c1174f622f644b24669afd5fb167fbb79**（2026-05-13T04:17:01Z，提交信息 "Update urllib3 to 2.7.0."）；renpy-8.5.3.26051401 指向同一 commit；releases 0（只用 tag 标记构建快照）。
- 许可证: **无 LICENSE 文件**（REST /license 404、GraphQL licenseInfo=null）→ SPDX NOASSERTION。README 未声明许可证。义务要点：公开仓库不等于可复用代码——本仓库的 tasks/*.py、runtime/*.c 无许可声明（默认保留所有权利），只能在阅读层面参照"要构建哪些件、版本是多少"，不能把脚本并入 GalNX 或再分发。其产出的第三方组件各自按其许可（Python、FFmpeg LGPL、SDL zlib 等）。
- 健康: archived=false；stars 120；forks 85；open issues 16（含 9 open PR → 纯 issue 7）；**无 CI**（.github/ 为空目录）；无 releases。
- 构建系统: uv + Python 任务模块（tasks/*.py，每个第三方库一个 task：hostpython3.py、python3.py、pythonlib.py、sdl3.py、ffmpeg.py、freetype.py、harfbuzz.py、fribidi.py、libjpeg_turbo.py、libpng.py、zlib.py、openssl.py、angle.py、metalangle.py、assimp.py、sysroot.py、toolchain.py 等）；入口 `build.sh` = `exec uv --project renpy run -m renpybuild "$@"`；环境准备 `prepare.sh` 全局改系统（apt 安装 git/build-essential/ccache/autoconf/automake/libtool-bin/pkg-config/llvm-22/clang-22/python3-dev/python3-venv/curl/debootstrap/libgmp-dev/libmpfr-dev/libmpc-dev/libssl-dev/libbz2-dev/liblzma-dev/bc/cmake/ninja-build/libassimp-dev/libav*-dev/libharfbuzz-dev/libfreetype6-dev/libfribidi-dev/libsdl3-dev/libsdl3-image-dev/libjpeg-dev 等，解压 prebuilt/clang_rt.tar.gz，安装 uv）。README.rst 原文要求：Ubuntu 24.04；部分流程必须 root；建议虚拟机；**至少 64 GB 磁盘、8 vCPU/16 GB RAM**；"Support for unofficial builds of Ren'Py will be limited."。
- 平台矩阵（README 表 + build.py）: linux x86_64/aarch64、windows x86_64、mac x86_64/arm64、android x86_64/arm64_v8a/armeabi_v7a、ios arm64/sim-x86_64/sim-arm64、web wasm —— **无 switch**。
- 版本锁定（master 的 source/ 与 tasks/ 原文）: Python 3.12.8（Windows 3.12.7；Python-3.12.8.tar.xz 与 Python-3.12.7/3.12.8-Setup.stdlib）、**SDL3 3.4.18**（tasks/sdl3.py 原文 version="3.4.18"，从 libsdl-org/SDL release-3.4.18 下载并打 4 个下游补丁：sdl3-opengl-ios.diff、sdl3-metalangle.diff、sdl3-ios27-orientation.diff、sdl3-ios27-statusbar.diff；cmake -DSDL_STATIC=ON -DSDL_SHARED=OFF -DSDL_CAMERA=OFF -DSDL_DEPS_SHARED=ON -DSDL_TESTS=OFF）、ffmpeg-4.3.1、freetype-2.13.3、harfbuzz-8.0.1、fribidi-1.0.7、libjpeg-turbo-1.5.3、libpng-1.6.43、zlib-1.3.1、openssl-3.3.2、brotli-1.2.1、bzip2-1.0.8、xz-5.4.2、nasm-2.14.02、zsync-0.6.2、pyjnius-1.7.0、MetalANGLE.framework/xcframework。**8.5.3 标签处相反**：tasks 里是 sdl2.py/sdl2_image.py（无 sdl3.py），source 里是 SDL2-2.0.14.tar.gz、SDL2-2.0.20.tar.gz、SDL2_image-2.6.2.tar.gz → 证明 8.5.3 发布线用 SDL2、master 才用 SDL3。
- runtime/ 关键文件: librenpython.c（10,393 B）、renpython_posix.c（119 B，仅 #define 后 include）、launcher_posix.c（117 B）、librenpython_android.c、librenpy_inittab.c、launcher_win.c、renpython_win.c、renpy.sh（1,646 B）、iossupport.py、sysconfig.py、sitecustomize.py、windows_manifest.xml、web/。
- librenpython.c 实读要点: 导出 `renpython_main`（Py_RunMain）与 `launcher_main`（游戏启动器，初始化 runtime 后 PyConfig_SetBytesArgv）；initialize_runtime() 设 PyPreConfig utf8_mode=1、use_environment=0；Python home 定位 marker 文件 "lib/<PYTHONVER>/site.pyc" 或 "lib/python<PYCVER>.zip"；module_search_paths = <home>/lib/<PYTHONVER> + <home>/lib/python<PYCVER>.zip；若未设 RENPY_PLATFORM 则 putenv("RENPY_PLATFORM=" PLATFORM "-" ARCH)；平台宏只有 #ifdef LINUX / MAC / WINDOWS / IOS / WEB（iOS 特判 "/base/"）→ **加 Switch 必须新增 #ifdef SWITCH 分支并定义 RomFS 下的 home 布局**。
- 交叉编译可复用性: python3.py 依赖 autoconf/configure（autoreconf -vfi）与 config.site（ac_cv_file__dev_ptmx=no、ac_cv_file__dev_ptc=no），sysroot.py 用 debootstrap 装 Ubuntu jammy 的 **glibc sysroot**（含 libasound2-dev/libpulse-dev/libx11-dev/libdrm-dev/libgbm-dev/libgl1-mesa-dev/libgles2-mesa-dev/libegl1-mesa-dev/libwayland-dev 等 31 个包）；toolchain.py 交叉链：windows=llvm-mingw-20241217-ucrt-ubuntu-20.04-x86_64、android=NDK zip、mac=MacOSX12.3.sdk.tar.bz2、ios=需用户自备 iPhoneOS.sdk.tar.gz（仓库不含，缺则 raise RuntimeError）、web=emsdk 5.0.2。→ 该体系假设 POSIX/glibc，**不能直接用于 devkitA64/newlib**；但"分任务、锁版本"的结构可作为自建构建编排的参照。
- README 声称: 见上（Ubuntu 24.04/root/64GB/8vCPU）；另 README 说明 iOS 构建用 SDL 3.4.18 + 下游方向补丁，当前 SDK 输入 iPhoneOS/iPhoneSimulator 27.1，最低部署目标 iOS 15.0。
- 未验证 / 风险: (a) 无 LICENSE → 脚本不可复用；(b) 无 CI，构建流程无法从仓库自动复现（依赖 prepare.sh 全系统改环境）；(c) README 要求 root + 64GB，本机不满足（本轮禁止构建）；(d) 需自备 iOS SDK 与大量第三方源码（README 的 tars/README.rst 要求自行下载）；(e) 平台矩阵无 switch，必须自写平台后端。
- 来源 URLs: https://github.com/renpy/renpy-build ; https://api.github.com/repos/renpy/renpy-build ; https://raw.githubusercontent.com/renpy/renpy-build/master/README.rst ; https://raw.githubusercontent.com/renpy/renpy-build/master/build.sh ; https://raw.githubusercontent.com/renpy/renpy-build/master/prepare.sh ; https://raw.githubusercontent.com/renpy/renpy-build/master/runtime/librenpython.c ; https://raw.githubusercontent.com/renpy/renpy-build/master/tasks/python3.py ; https://raw.githubusercontent.com/renpy/renpy-build/master/tasks/sysroot.py ; https://raw.githubusercontent.com/renpy/renpy-build/master/tasks/toolchain.py ; https://raw.githubusercontent.com/renpy/renpy-build/master/tasks/sdl3.py

### 3. jvrcruzGAMES/NXPython

- URL: https://github.com/jvrcruzGAMES/NXPython ；默认分支 main
- HEAD SHA: 86cde186653a89593359bd59102ed2b878c6fa5b ；提交日期 2026-08-09T00:58:47Z（pushed_at 2026-08-09T22:35:16Z；created_at 2026-08-09T22:35:13Z；仓库 size 78 KB）
- 最近 tag: 无（无 tag、无 release；只有 main 分支）
- 许可证: **无 LICENSE**（REST /license 404、GraphQL licenseInfo=null）→ SPDX NOASSERTION。**这是关键风险：其 299,892 B 的 CPython 补丁栈无任何许可声明，不能复制/复用。**
- 健康: archived=false；stars 0；forks 0；open issues 0；主语言 Shell；描述为空；单日创建并推送（bus factor = 1，脆弱）。
- 构建系统 / 关键依赖: 以补丁为核心的仓库（README 原文："NXPython keeps the Nintendo Switch CPython port outside the CPython checkout. This repository tracks patch files only; CPython itself is downloaded into ignored working directories."）；CPYTHON_COMMIT = **1b1c61a94f0685bb0be707b5374376f3084159fe**；补丁 patches/0001-nxpython-cpython-3.14.patch（299,892 B）；build.sh 4,240 B，构建命令 `DEVKITPRO=/opt/devkitpro DEVKITA64=/opt/devkitpro/devkitA64 PATH=/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin:$PATH ./build.sh -j 8`；参数透传给 CPython 的 Platforms/NX/build-portlibs.sh（--destdir 可选）；产物 static libpython3.14.a 安装进 devkitPro portlibs。
- 技术要点（补丁文本实读）: ① 设 `sys.platform == "nx"`（原文 "_NX = (sys.platform == 'nx')"、"@_is_nx = sys.platform == 'nx'@"；测试用 @unittest.skipUnless(sys.platform == 'nx', 'NX-specific filesystem roots')@）；② 给 CPython 增加 **romfs:/ 与 sdmc:/ 两种挂载根**的 POSIX 路径语义（romfs: 与 romfs:/ 等价、sdmc: 与 sdmc:/ 等价；posixpath.splitroot("sdmc:/switch/python") 返回 ("sdmc:", "/", "switch/python")；posixpath.join("romfs:/Lib","/site.py") 返回 "romfs:/site.py"）；③ 可执行文件内嵌 romfs:/python/lib/python3.14 与 romfs:/python_site；④ build-portlibs.sh 支持 --runtime-prefix sdmc:/python；⑤ 全补丁中 romfs 命中 244 次、sdmc 42 次、sys.platform 6 次，**horizon/save:///devoptab 命中 0**。→ 这是 CPython 在 Switch 上可跑的最直接证据（但只是"补丁存在"，未独立构建/运行验证）。
- README 声称: 见上（补丁仓库、CPython 自行下载）；构建命令与产物（libpython3.14.a）来自 build.sh 与 README 组合。
- 未验证 / 风险: (a) 无许可证 → 法律上不可复用（可参考"需要改哪几类路径"的设计，代码必须自写）；(b) 未构建/未运行验证（本轮禁令）；(c) CPython **3.14** 而 Ren'Py 8.5.3 要求 3.12.8–3.12.x（pyproject requires-python），jvrcruz 8.3.4 用 3.14 属于绕过官方组合的特例，C-API/字节码兼容风险高；(d) 单人单日仓库，无 issue/PR 历史，维护风险极高；(e) 静态 libpython 与 Ren'Py C 扩展的链接顺序/符号冲突未验证。
- 来源 URLs: https://github.com/jvrcruzGAMES/NXPython ; https://api.github.com/repos/jvrcruzGAMES/NXPython ; https://raw.githubusercontent.com/jvrcruzGAMES/NXPython/main/README.md ; https://raw.githubusercontent.com/jvrcruzGAMES/NXPython/main/CPYTHON_COMMIT ; https://raw.githubusercontent.com/jvrcruzGAMES/NXPython/main/build.sh ; https://github.com/jvrcruzGAMES/NXPython/blob/main/patches/0001-nxpython-cpython-3.14.patch

### 4. jvrcruzGAMES/RenpySwitch

- URL: https://github.com/jvrcruzGAMES/RenpySwitch ；默认分支 master
- HEAD SHA: 7824039a7d0353b7bfa79ddfcecbf30a375d3d62 ；提交日期 2026-08-10T19:16:50Z（pushed_at 2026-08-10T19:17:04Z；created_at 2026-08-09；size 7,458 KB；fork=true，parent 为 knautilus/RenpySwitch；homepage https://lemmasoft.renai.us/forums/viewtopic.php?p=512484）
- 对应引擎与版本范围: **Ren'Py 8.3.4**（setup.bash 原文 `export RENPY_VER=8.3.4`，下载 renpy-8.3.4-sdk.zip / renpy-8.3.4-source.tar.bz2 / pygame_sdl2-2.1.0+renpy8.3.4.tar.gz）；运行时 Python **3.14 via NXPython**；Cython 3.0.10。
- 最近 tag: **无**（tags 0、releases 0）；只有 main/master 分支滚动构建，无版本锚点。
- 许可证: **无 LICENSE 文件**（REST /license 404、GraphQL licenseInfo=null）→ SPDX NOASSERTION。README 未声明许可。再分发义务：由于无授权声明，**默认保留所有权利**——不得把其补丁/脚本/二进制并入 GalNX 或分发；其产物若含 Ren'Py 引擎代码，仍受 Ren'Py 的 MIT+LGPL 约束（义务回溯到上游，而非该仓库给了授权）。
- 健康: archived=false；stars 2；forks 2；open issues 0；open PR 0；created 2026-08-09（单日建仓，之后一次性推送）；无 tag/release；CI 为 push 触发构建 artifact（.github/workflows/main.yml）。
- 上游依赖（实抓）: devkitPro 容器 **devkitpro/devkita64:20230910**；dkp-pacman 包（setup.bash L78–81 原文）= switch-mesa、switch-glad、switch-libdrm_nouveau、switch-sdl2、switch-sdl2_gfx、switch-sdl2_image、switch-sdl2_mixer、switch-sdl2_ttf、switch-ffmpeg、switch-freetype、switch-curl、switch-mbedtls、switch-liblzma、switch-libzstd、switch-zlib、switch-bzip2；另有从 knautilus/Utils release 下载的 devkitpro-pkgbuild-helpers-2.2.4-2 与 switch-libfribidi-1.0.12-1；NXPython 的 CPython commit 1b1c61a94f0685bb0be707b5374376f3084159fe（构建时若 portlibs 已有 libpython3.14.a/pyconfig.h 则复用）；pygame_sdl2 2.1.0（REN'PY 8.3.4 配套）。switch/CMakeLists.txt 用 pkg_check_modules REQUIRED 声明：egl、freetype2、glapi、glesv2、libavcodec、libavfilter、libavformat、libavutil、libdrm_nouveau、libswresample、libswscale、sdl2、SDL2_gfx、SDL2_image、SDL2_mixer、SDL2_ttf、zlib。
- 构建系统 / 入口 / 产物: GitHub Actions（on: push；runs-on ubuntu-24.04；container devkitpro/devkita64:20230910）依次 `sudo bash setup.bash` → `sudo bash build.bash` → upload artifact raw。需要 devkitPro（devkitA64 工具链）与 **Linux 环境**（README 明说用 WSL2 或 Docker，`docker pull devkitpro/devkita64:20230910`）。build.bash 流程：本地先编 pygame_sdl2 与 renpy-source/module（RENPY_DEPS_INSTALL=/usr/lib/x86_64-linux-gnu:/usr:/usr/local，含 RENPY_STATIC=1/PYGAME_SDL2_STATIC=1 的容错尝试）→ source /opt/devkitpro/switchvars.sh → cmake 构建 ./switch/build/renpy-switch.nso → 拷到 raw/switch/exefs/main → 组装 raw/switch/romfs/Contents/{renpy.py、renpy/common、lib.zip（含 CPython stdlib + 编译产物）} → 用 renpy SDK 的 lib 与 renpy-source/module/renpy/renpy.py + script.rpy 运行 `./renpy.sh . compile` 生成 .rpyc → python generate_private.py。**NRO/NSP 打包**由仓库自带 pack_nro.bash / pack_nsp.bash 完成（build_romfs + nacptool + build_pfs0；NSP Title ID 默认由 exe SHA-256 派生 0100<8hex>0000）。注意：CI 本身只上传 raw/ 目录，不产出 NRO/NSP。
- README 声称（原文）: "Build pipeline for Ren'Py on Nintendo Switch, powered by GitHub Actions and NXPython"；README 表格：Ubuntu 24.04、devkitpro/devkita64 20230910、Ren'Py SDK 8.3.4、Python 3.14 (via NXPython)、Cython 3.0.10；流程 6 步：下载 Ren'Py 8.3.4 源码和 SDL2 绑定 → 应用 Switch 专用补丁 → Cython 编译 Ren'Py 模块 → 打包运行时进 lib.zip → 交叉编译 Switch 可执行文件 .nso → 在 raw/ 组装空白 Switch 项目。**README 未声称真机验证通过**；本轮未运行，真机/模拟器状态未验证。
- 已知限制（来自 renpy.patch 与源码事实，非 README 声明）: 渲染器强制 `renderers = [ "gles" ]` 且 `config.gl2 = False`（放弃 GL2/GLSL ES 3.0 渲染器，画面能力与性能受限）；关闭自动存档（has_autosave/autosave_on_choice/autosave_on_input/save_on_mobile_background 全 False）；`sys.platform == "horizon"` 下的路径被写死为 romfs:/Contents/game、romfs:/Contents/renpy/common、save:/Data/；通过随包的 native 库 `_otrhlibnx` 做 boost/restart/commitsave；视频/音频/字体只做了路径级适配（ffmedia.c +33/−4、renpysound.pyx +4/−4、ftfont.pyx/hbfont.pyx 各 +2/−2）；非 ASCII 路径、触摸/手柄、性能均无证据；patch 共 **19 个文件、51 个 hunk**（21,918 B）。
- 未验证 / 风险: 无许可证（最大风险）、无 tag/release（不可锁定）、基线 8.3.4 落后当前 8.5.3、Python 3.14 与 Ren'Py 8.3.4 官方要求的 3.8–3.12 组合不一致（属私改组合）、CMakeLists 有大量硬编码 /opt/devkitpro 路径（可复现性差）、真机未验证。
- 来源 URLs: https://github.com/jvrcruzGAMES/RenpySwitch ; https://api.github.com/repos/jvrcruzGAMES/RenpySwitch ; https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/README.md ; https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/setup.bash ; https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/build.bash ; https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/switch/CMakeLists.txt ; https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/renpy.patch ; https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/.github/workflows/main.yml ; https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/pack_nro.bash ; https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/pack_nsp.bash

### 5. knautilus/RenpySwitch

- URL: https://github.com/knautilus/RenpySwitch ；默认分支 master
- HEAD SHA: d361e44fbf15cd1bda66d77cce74e29fc2a7f115 ；提交日期 2025-06-21T22:10:45Z（pushed_at 2026-02-07T14:12:46Z；created_at 2025-06-21；size 246 KB；fork=true，parent 为 Otorhin/Ren2Switch；homepage 同 lemmasoft p=512484）
- 对应引擎与版本范围: **Ren'Py 7.6.3**（Python 2.7 时代）；README 表格：ubuntu-24.04、devkitpro/devkita64:20230910、renpy sdk 7.6.3、python 2.7、pefile 2019.4.18、cython 0.29.36、setuptools 0.9.8。
- 最近 tag: **7.6.3_1.0**（也是唯一 tag）= commit d361e44fbf15cd1bda66d77cce74e29fc2a7f115（2025-06-21T22:10:45Z）；releases 1："Renpy 7.6.3" published 2025-06-21T22:42:38Z。
- 许可证: **无 LICENSE 文件**（/license 404、licenseInfo=null）→ SPDX NOASSERTION；再分发义务同条目 4：默认保留所有权利，不可复用代码；其产物中 Ren'Py 部分仍受上游 MIT+LGPL 约束。
- 健康: archived=false；stars 6；forks 4；open issues 0；open PR 0；2026-02-07 后无 push；fork 自 Ren2Switch。
- 上游依赖: devkitPro（devkitpro/devkita64:20230910）、Ren'Py SDK/source 7.6.3、Python 2.7（Switch portlibs 里的 python27）、pygame_sdl2 2.x（7.6 系配套）、Cython 0.29.36、setuptools 0.9.8、pefile 2019.4.18。
- 构建系统 / 入口 / 产物: GitHub Actions（俄罗斯语 README 原文："Данный репозиторий служит сборщиком RenPy на Github Actions" 即"本仓库作为在 GitHub Actions 上构建 RenPy 的构建器"）；入口 setup.bash → build.bash；产物组装进 raw/ 目录（游戏启动器布局，含 private 数据与 romfs），打包脚本同族（CMakeLists 输出 renpy-switch.nso）。具体 NRO/NSP 脚本在本仓库根目录未见（只有 CMakeLists.txt/README.md/build.bash/generate_private.py/link_sources.bash/renpy.patch/script.rpy/setup.bash/subprocess.pyo/switch/）→ **NRO/NSP 打包环节在本仓库未验证**。
- README 声称: 见上（构建器定位 + 版本表）；无真机验证声明。
- 已知限制: Ren'Py 7.6.3 是 Python 2.7 旧线（已停止维护，与 8.x 游戏不兼容）；补丁规模 **44 个文件、116 个 hunk（59,058 B）**，改动层包括音频后端（audio/androidhw.py、audio/ioshw.py、audio/audio.py）、渲染（gl/gldraw.pyx、gl2/gl2draw.pyx、gl2/live2d.py）、显示（display/core.py、display/screen.py、display/transform.py、display/video.py）、解析/执行（ast.py、sl2/slast.py、sl2/slparser.py、execution.py、rollback.py、revertable.py）、平台（renpy.py、bootstrap.py、loader.py、savelocation.py、persistent.py、log.py、main.py）等；说明"要在 Switch 上跑 Ren'Py 7.6，至少要动这 6 层"。
- 未验证 / 风险: 无许可证、Python 2 已死、无 NRO/NSP 脚本证据、无真机证据、2026-02 后无更新。
- 来源 URLs: https://github.com/knautilus/RenpySwitch ; https://api.github.com/repos/knautilus/RenpySwitch ; https://raw.githubusercontent.com/knautilus/RenpySwitch/master/README.md ; https://raw.githubusercontent.com/knautilus/RenpySwitch/master/renpy.patch ; https://raw.githubusercontent.com/knautilus/RenpySwitch/master/setup.bash ; https://raw.githubusercontent.com/knautilus/RenpySwitch/master/build.bash

### 6. Otorhin/Ren2Switch

- URL: https://github.com/Otorhin/Ren2Switch ；默认分支 master
- HEAD SHA: 5fce4a28afaa1df262876b7bcce0bee10b3a0360 ；提交日期 2023-09-04T22:05:13Z（= pushed_at；created_at 2022-09-06；size 263 KB；fork=true，parent 为 uyjulian/renpy-switch；homepage https://lemmasoft.renai.us/forums/viewtopic.php?p=512484）
- 对应引擎与版本范围: **Ren'Py 7.6.1**（Python 2 时代）：setup.bash `export RENPY_VER=7.6.1`，下载 renpy-7.6.1-sdk.zip / renpy-7.6.1-source.tar.bz2 / pygame_sdl2-$PYGAME_SDL2_VER-for-renpy-7.6.1.tar.gz；python2 工具链。
- 最近 tag: 仓库 tags 14 个（v1.0、v1.1、v1.2、v1.3、v1.4、v1.5、v1.6、v1.6.1、v1.7、v1.7.1、v1.7.2、v1.7.3、v1.7.4、v1.7.5），**这些 tag 是从上游 uyjulian/renpy-switch fork 继承的**（最新 v1.7.5 = e41dfbe5ee77e9ad673bb4d2854f5983d5f05935，2020-12-20T05:10:03Z），**不是本仓库自身版本线**；本仓库自身无 release（releases 0）。
- 许可证: **无 LICENSE 文件**（/license 404、licenseInfo=null）→ SPDX NOASSERTION；不可复用其代码/补丁。
- 健康: archived=false；stars 12；forks 4；open issues 0；最后 push 2023-09-04（已停滞约 3 年）；fork 自 uyjulian/renpy-switch。
- 上游依赖: devkitPro 容器 **devkitpro/devkita64:20221113**；python2 + pip2（future/six/typing/requests/ecdsa/pefile==2019.4.18/Cython==0.29.36）；从 https://github.com/Otorhin/scripts/releases/download/oof/ 下载 devkitpro-pkgbuild-helpers-2.2.3-1、python27-switch.tar.gz、switch-libfribidi-1.0.12-1；从 https://dl.otorh.in/github/rawproject.zip 下载空白项目骨架（含 PC/Win/Linux、Android、Switch）；android-native-symbols.zip。**依赖托管在个人域名 dl.otorh.in 与个人 release 上，外链稳定性差**。
- 构建系统 / 入口 / 产物: .github/workflows/ci.yml（on push；ubuntu-latest；container devkitpro/devkita64:20221113）；setup.bash → build.bash（python2 setup.py …）；产物 raw/switch/exefs/main（renpy-switch.nso）+ raw/switch/romfs/Contents/{renpy.py、renpy/common、lib.zip}（python2.7 stdlib 进 private/lib/python2.7），最后 `7z a -tzip raw.zip ./raw/*`；switch/CMakeLists.txt 的 SWITCH_VERSION 为 "7.6.1"、INCLUDES 指向 python2.7、与 8.x 版同一组 REQUIRED pkg-config 依赖（egl/freetype2/glapi/glesv2/libav*/libdrm_nouveau/libsw*/SDL2*、zlib）。
- README 声称: 未提供可用中文/英文的明确"真机可用"声明（README 主要描述构建流水线）；无 tag/release 绑定到自身提交。
- 已知限制: Python 2 旧线；依赖外部个人站点；无许可证；2023 年后停滞；无 NRO 打包脚本（与 knautilus 版差异：knautilus 加了 NRO/NSP 打包脚本）。
- 未验证 / 风险: 无许可证、依赖外链可能失效、基线 7.6.1 + Python2 与现代 Ren'Py 游戏不兼容、真机未验证。
- 来源 URLs: https://github.com/Otorhin/Ren2Switch ; https://api.github.com/repos/Otorhin/Ren2Switch ; https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/README.md ; https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/setup.bash ; https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/build.bash ; https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/switch/CMakeLists.txt ; https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/.github/workflows/ci.yml

### 7. uyjulian/renpy-switch

- URL: https://github.com/uyjulian/renpy-switch ；默认分支 **landing**（注意：落地分支已不是 master；根目录只有 README.md）
- HEAD SHA: 8a75ca3bd5f1c50612a33abae216ecf772b7d330 ；提交日期 2022-01-04T04:13:35Z（pushed_at 2022-01-04T04:13:50Z；created_at 2019-06-02；stars 70；forks 24）
- 对应引擎与版本范围: 2019–2020 年的 Ren'Py 7.x 线（14 个 release，v1.0 → v1.7.5；最后 release v1.7.5 于 2020-12-20）。具体 Ren'Py 版本未在元数据中给出，未取证。
- 最近 tag: v1.7.5 = e41dfbe5ee77e9ad673bb4d2854f5983d5f05935（2020-12-20T05:10:03Z）；v1.7.4 68573bddfa93e55fb167ea2993bd800e0d898aa0、v1.7.3 315726fb8561b462adfa828df74f83eb0b6b79f8、v1.7.2 63d5e26814046a412abd140045b94e44d8942015、v1.7.1 8435dd3e7c3fe5d96417d0b8130e01a3b548a4a0、v1.7 22217e2778a7f049577aaf255f43c72e900ad777、v1.6.1 7de22ed9625e0429e8e476be6609e421bfb1205b、v1.6 2d7b36063efb688be84ab3206ddd746cda32ae7d、v1.5 c1d4a4339ec23eb6470f983d8fbc84a2ddaf0d69、v1.4 305ecbb43db23f4f8e38721bc0d84dd159a2a965。
- 许可证: **无 LICENSE 文件**（/license 404、licenseInfo=null）→ SPDX NOASSERTION；不可复用。
- 健康: **archived=true**（已归档，只读）；open issues 7；open PR 0；14 releases；最后提交 2022-01-04；仓库描述原文："(Project archived, please use Switchroot Android with the official port of Ren'Py) Open source port of Ren'Py to the Nintendo Switch"。
- 构建系统 / 依赖: 落地分支（landing）根目录只有 README.md，**构建脚本不在默认分支可见**（需查 history/ 或其他分支，本轮未取证）；无 CI 证据。
- README 声称（原文）: "Sorry, this project is archived! Please use [Switchroot Android](https://switchroot.org/) with the [official port of Ren'Py](https://renpy.org/)." → **作者本人建议走 Switchroot Android + 官方 Ren'Py，而不是继续原生移植**。
- 已知限制: 归档、过时、无许可、无源码可见性；技术上已被后继（Otorhin → knautilus → jvrcruz）取代。
- 未验证 / 风险: 归档不可用风险最高；本轮未查其构建脚本内容；无许可。
- 来源 URLs: https://github.com/uyjulian/renpy-switch ; https://api.github.com/repos/uyjulian/renpy-switch ; https://raw.githubusercontent.com/uyjulian/renpy-switch/landing/README.md ; https://api.github.com/repos/uyjulian/renpy-switch/releases

## 专项 A：官方构建依赖与平台抽象层（独立移植的落点）

### A1. 平台分组：官方只有 6 组，没有 switch
renpy/__init__.py（8.5.3 与 master 同构）注释原文："We break the platforms up into 6 groups - windows-like, mac-like, linux-like, android-like, ios-like and web (aka. emscripten)."；布尔量 windows / macintosh / linux / android / ios / emscripten；判定顺序：`platform.win32_ver()[0]` → windows；环境变量 `@RENPY_PLATFORM`@ 以 "ios" 开头 → ios；`platform.mac_ver()[0]` → macintosh；然后 android（环境/构建标志）；`sys.platform == "emscripten"` 或 RENPY_EMSCRIPTEN → emscripten；否则 linux=True。arch 取 RENPY_PLATFORM 按 "-" 的最后一段；`mobile = android or ios or emscripten`；`experimental = "RENPY_EXPERIMENTAL" in os.environ`。
→ **Switch 要么"伪装成 linux"（大量代码按 linux 处理，但路径/存档/输入全要另改），要么新增第 7 组（社区移植的做法：加 `renpy.switch` 布尔量 + `@sys.platform == "horizon"`@）。官方没有任何一行 switch 分支。**

### A2. 路径抽象：平台差异的集中点
renpy.py 顶层函数 path_to_gamedir()、path_to_common()、path_to_saves(gamedir, save_directory)、path_to_renpy_base()、path_to_logdir()、predefined_searchpath(commondir)。Android/iOS 分支读环境变量（ANDROID_PUBLIC/ANDROID_PRIVATE、ANDROID_OLD_PUBLIC、ANDROID_PACK_FF1..4；iOS 用 pyobjus 取 NSDocumentDirectory）；通用分支依次：RENPY_PATH_TO_SAVES 环境变量 → 向上找 "Ren'Py Data" 目录 → mac 的 ~/Library/RenPy/… → windows 的 %APPDATA%/RenPy → 否则 ~/.renpy/<save_directory>。
→ **Switch 没有 home 目录、没有 %APPDATA%**：必须重写 path_to_saves / path_to_logdir / path_to_renpy_base（例如 sdmc:/switch/<title-id>/saves、log 落 sdmc）。这是社区补丁必改的第一批文件之一。

### A3. 文件层：loader.py 与 RPA 归档
renpy/loader.py（25,865 B）：index_files()/index_archives()/walkdir()/scandirfiles()；读文件优先级 `file_open_callbacks` 顺序 = load_from_file_open_callback → load_from_filesystem（open_file = IOPath，来自 renpy.pygame.iostream）→ load_from_archive（RPAv1/v2/v3 handler，用 IOSubFile(afn, base=offset, length=dlen) 偏移随机读）→ load_from_apk（仅 Android）；remote/webloader 分支仅在 emscripten / RENPY_SIMULATE_DOWNLOAD 下启用；依赖 os.scandir/os.path、threading（自动重载监听）、zlib、unicodedata（lower_map NFC）。
→ **Switch 需要**：libnx 的 romfs devoptab 支持 opendir/readdir（newlib 侧需验证）、.rpa 归档内偏移 fseek 随机读、把 cache/ 与临时文件重定向到 sdmc（社区补丁即 `if fn.startswith("cache/") and renpy.switch: fn = "save://" + fn`）。无 MMU/内存受限下还要注意 zipimport 与 mmap 不可用。

### A4. 显示层：renderer 选择与 GL2 的硬条件
renpy/display/core.py（113,504 B）选择 renderer 列表；社区补丁把它改成 switch 仅 ["gles"]，并关闭 gl2。官方证据：renpy/gl2/gl2shadercache.py `DIALECT_VERSIONS = {100: (100, 120), 300: (300, 330)}`（dialect 100 = GLSL ES 1.00，300 = GLSL ES 3.00），注释说明 glsl=300 的 shader part 只有缺特性时才不能跑在仅 GLSL ES 1.00 的设备；renpy/gl2/gl2draw.pyx `pygame.display.hint("SDL_OPENGL_ES_DRIVER", "1" if gles else "0")`、读 `GL_SHADING_LANGUAGE_VERSION`、并用 `ShaderCache("cache/shaders.txt", …)`。
→ **gl2 渲染器要求 GLSL ES 3.00（GLES3）**；Switch 的 mesa/nouveau 提供 GLES3，但 shader cache 写盘（cache/shaders.txt）在 RomFS 只读时需重定向；若放弃 gl2 走旧 gles 渲染器，画面效果/性能会明显降级（社区移植都这么干）。这部分**必须在真机或模拟器上实测**，只读审计无法判定。

### A5. 音频与文本：C 扩展直连系统库
renpy/audio/audio.py `import renpy.audio.renpysound as renpysound`（C 扩展，由 src/renpysound_core.c + src/ffmedia.c 构建，pkg-config 链 libavformat/libavcodec/libavutil/libswresample/libswscale + sdl2；**不使用 pygame.mixer**）；`lock = threading.RLock()` 协调 periodic 与主线程。文本：renpy.text.ftfont（src/ftsupport.c + ttgsubtable.c，链 freetype2 + harfbuzz）、renpy.text.bidi（src/renpybidicore.c，链 fribidi）。
→ Switch 上对应 devkitPro portlibs：switch-ffmpeg、switch-freetype、switch-libfribidi（1.0.12 prebuilt）、harfbuzz（devkitPro 的 SDL2_ttf 依赖里有）；**CJK 字体文件必须随游戏分发（法律与体积问题），引擎不自带字体**。

### A6. 启动链与 native 入口
启动链（AGENTS.md 原文 Code map）：renpy.py → renpy/bootstrap.py → renpy/main.py；bootstrap.py（18,616 B）检查 -X utf8、处理 environment.txt、set_utf8_locale()、sys.path.insert(0, basedir)、`import renpy.pygame` 并 `import_as_pygame()`、`import _renpy`、renpy.import_all()、循环调用 renpy.main.main()、finally 里调 renpy.audio.audio.quit()/draw.quit()；含 subprocess.Popen 处理；android 分支用 jnius/System.exit(0)。
→ Switch 需要：自定义 `librenpython.c` 式 native 入口（renpy-build 的 runtime/librenpython.c 导出 renpython_main/launcher_main，Python home 在可执行文件旁，平台宏 #ifdef LINUX/MAC/WINDOWS/IOS/WEB），加 #ifdef SWITCH 分支把 home 指向 romfs 内的 python 目录；退出路径不能依赖 sys.exit/扫描线程（社区补丁：main.py 跳过 sys.exit、savelocation.quit() 直接 return、config.save_on_mobile_background=False）。

### A7. SDL 绑定：8.5.3 = SDL2 内置绑定，master = SDL3 重写
8.5.3 的 setup.py：`renpy.pygame.*` 全部 packages="sdl2"，源为 src/pygame/SDL2_rotozoom.c、SDL_gfxPrimitives.c、write_jpeg.c/write_png.c、alphablit.c 等（即 pygame_sdl2 系 SDL2 绑定被内置进 renpy 仓库）；master 的 setup.py：packages="sdl3"，源为 src/pygame/SDL3_rotozoom.c、SDL3_gfxPrimitives.c 等，模块名重写为 renpy.pygame.{iostream,locals,image,controller,joystick,time,power,transform,scrap,key,mouse,event,display,color,rect,error,surface,draw,gfxdraw}。
→ **选 8.5.3 可以用 devkitPro 现成的 switch-sdl2 2.28.5-4（上一轮集群 A 已核实存在）；选 master 则要 switch-sdl3，未验证，且必须跟官方 SDL3 3.4.18 的 API。**

### A8. 官方平台矩阵与对 Switch 的参考价值

| 平台 | 官方构建方式 | 运行时前提 | 对 Switch 的参考价值 |
| --- | --- | --- | --- |
| Linux x86_64/aarch64 | renpy-build sysroot（debootstrap Ubuntu jammy glibc） | glibc、X11/Wayland、GL/GLES、PulseAudio/ALSA | aarch64 交叉流程可参考；但 glibc→newlib 不可直接搬 |
| Windows x86_64 | llvm-mingw | Win32 + ANGLE（DirectX 后端） | ANGLE 思路可参考（Switch 有 GLES，不需要 ANGLE） |
| macOS x86_64/arm64 | Xcode SDK 12.3 | Cocoa、Metal/OpenGL | 收益低 |
| Android（x86_64/arm64_v8a/armeabi_v7a） | NDK + rapt.py + SDL2/GLES | **OpenGL ES 3.0、Android 5.0+** | **最有参考价值**：GLES3、触屏、SDL2、静态 libpython 打包都为 Switch 所类似；Android 的 platform differences 文档（触屏当鼠标、renpy.input 受限）就是 Switch 触屏的预演 |
| iOS arm64/sim | Xcode + renios.py | MetalANGLE、SDL 3.4.18 + 方向补丁 | LGPL 合规声明写法可参考；工程不可复用 |
| Web (wasm) | emsdk 5.0.2 | 浏览器、**无多线程**、无网络 | 证明 Ren'Py 可在弱环境跑，但不适用 |

官方文档原文（android.rst L7–17）："Ren'Py runs on Android 5.0 and later, on devices that support OpenGL ES 3.0. It will not start on a device that only supports OpenGL ES 2.0."；L51–64 Platform Differences：触屏映射为鼠标（仅触摸时产生 mouse events）、"Text input (such as renpy.input) is limited to the input methods that do not require completions to work. (Western languages probably work, while other languages might not.)"。ios.rst：iOS 构建需 Mac/Xcode，部分库为 LGPL、分发需遵守；"The current Ren'Py iOS support is a work in progress."。web.rst：视频用浏览器内置播放、仅 renpy.movie_cutscene；"The web port doesn't support multi-threading, so functions like renpy.invoke_in_thread and the Python threading module are not supported."；Networking is not supported。
**树莓派/ARM**：官方 build 矩阵没有 Raspberry Pi 条目，只有 linux aarch64 与 "renpy-8.5.3-sdkarm" 资产（其目标架构未取证）；不能断言官方支持树莓派。

## 专项 B：社区移植技术差异对照（仅技术参考，禁止复制代码）

### B1. 血统
uyjulian/renpy-switch（2019–2020，14 releases，2022 归档）→ Otorhin/Ren2Switch（fork 自 uyjulian，Ren'Py 7.6.1，2023 停滞）→ knautilus/RenpySwitch（fork 自 Otorhin，Ren'Py 7.6.3，2025-06）→ jvrcruzGAMES/RenpySwitch（fork 自 knautilus，Ren'Py 8.3.4 + NXPython CPython 3.14，2026-08）。**四者全部无许可证**，且 fork 关系意味着 jvrcruz 的补丁是 knautilus 补丁的再衍生（法律上更不可复用）。

### B2. 改动规模与改动层对照

| 维度 | uyjulian（归档） | Otorhin/Ren2Switch | knautilus/RenpySwitch | jvrcruzGAMES/RenpySwitch |
| --- | --- | --- | --- | --- |
| Ren'Py 基线 | 7.x（具体未取证） | 7.6.1 | 7.6.3 | 8.3.4 |
| Python | （未取证） | 2.7 | 2.7 | 3.14（NXPython） |
| CI 容器 | 无 CI 证据 | devkitpro/devkita64:20221113 | devkitpro/devkita64:20230910 | devkitpro/devkita64:20230910 |
| 补丁规模 | 未取证（落地分支仅 README） | 复用上游补丁 | **44 文件 / 116 hunk / 59,058 B** | **19 文件 / 51 hunk / 21,918 B** |
| 渲染 | 未取证 | （未详） | gles + 关 gl2（改 gl/gldraw.pyx、gl2/gl2draw.pyx） | renderers=["gles"]、config.gl2=False |
| 路径/存档 | 未取证 | （未详） | romfs:/ + save:/ 改写（renpy.py、loader.py、savelocation.py、persistent.py） | 同左 + save://cache 重定向 |
| native 层 | 未取证 | 无 _otrhlibnx 证据 | 未见 _otrhlibnx（7.6 线） | 随包 _otrhlibnx（boost/restart/commitsave） |
| 打包 | 14 releases（产物类型未取证） | raw.zip（NSO + romfs 布局） | raw/ 布局，无 NRO/NSP 脚本证据 | pack_nro.bash / pack_nsp.bash（NRO/NSP） |
| 许可证 | 无 | 无 | 无 | 无 |

### B3. 六层改动模式（从社区 patch 归纳出的"必须动哪几层"，**不是**可复制的实现方案）
1. **平台识别**：加 switch 布尔量 / 把 sys.platform 认成 horizon（jvrcruz 用 `elif sys.platform == "horizon": switch = True`，并把 mobile 扩为 `android or ios or emscripten or switch`）；关闭 renpy.encryption。
2. **路径与存档**：romfs:/Contents 下只读资源 + save:/Data/ 可写区；改 renpy.py 的 path_to_gamedir/path_to_common/path_to_renpy_base/path_to_saves、config.searchpath、savelocation 的 FileLocation。
3. **渲染器**：强制 gles、关 gl2、关后台截图（`if background and not (renpy.emscripten or renpy.switch)`）。
4. **启动/主循环/退出**：presplash 换 native 实现（renpy/display/presplash.py 新增 start_switch(gamedir)）、跳过 sys.exit、不启扫描线程、stderr 重定向到文件（log.py）。
5. **文件缓存/持久化/自动存档**：cache/ 重定向到可写区、关自动存档/移动端后台存档、00sync.rpy 适配。
6. **媒体与字体**：ffmedia.c 的路径/解码适配、renpysound.pyx 与 ftfont.pyx/hbfont.pyx 的路径级改动。
→ 这 6 层与专项 A 的官方抽象层一一对应，**可以作为 GalNX 自己写平台层的需求清单**（仅借"改哪里"，不借"怎么改"的代码）。

## 专项 C：独立移植技术断点逐项判定

| # | 技术断点 | 官方现状 | 判定 | 说明 |
| --- | --- | --- | --- | --- |
| C1 | CPython 3.12.8 交叉编译到 devkitA64/newlib | pyproject requires-python >=3.12.8,<3.13；官方 build 无 switch，python3.py 依赖 autoconf/configure + glibc sysroot | **硬阻塞（最大工作量）** | 需自写 CPython 补丁：sys.platform、romfs/sdmc devoptab、无 fork/exec、无 socket 或 stub、dlopen/mmap、locale/编码、静态 libpython3.12.a 与 C 扩展链接。NXPython 的 3.14 补丁栈（299,892 B）证明"有人做成过"，但无许可证不能用，且版本不匹配 |
| C2 | Cython 扩展编译 | Ren'Py 8.5.3 有 20+ C 扩展（_renpy、renpy.pygame.*、renpysound、ftfont、bidi、assimp…），由 setuptools+Cython 构建 | **中等**：无 JIT 不影响（Cython 是 AOT） | 需把 setuptools build_ext 换成 devkitA64 交叉（CC/CFLAGS/LDFLAGS 或自写构建脚本）；Cython 生成 C 后再编；注意 C++ 扩展（assimpio.cc）与 libstdc++ |
| C3 | SDL2 + GLES 上下文 | 官方 8.5.3 用 SDL2；devkitPro 有 switch-sdl2 2.28.5-4 | **低–中**：有现成 portlib | 需验证 SDL2 video/GLES（mesa + libdrm_nouveau）、音频（audren）、手柄/触摸；社区移植都能编过 |
| C4 | GL2 渲染器（GLSL ES 3.00） | gl2 需要 GLES3 + shader cache 写盘 | **中**：可先绕过 | 先只用 gles 渲染器（社区做法），把 gl2 作为后续优化；shader cache 需重定向到 sdmc |
| C5 | ffmpeg / 音视频 | 官方依赖 ffmpeg 4.3.1（renpy-build 锁定），renpysound 直接调 libav* API | **中** | devkitPro 的 switch-ffmpeg 版本需与 renpysound 的 API 匹配（4.3.1 vs portlib 版本），视频（movie）在 Switch 上性能/内存受限 |
| C6 | RomFS + 可写区 | loader.py 的 RPA 偏移读、os.scandir；renpy.py 的存档路径 | **中** | libnx romfs devoptab 是否支持 readdir/scandir 需实测；.rpa fseek 偏移读应可行；可写区只有 sdmc，需把 cache/、log、save 全部重定向 |
| C7 | 字体/文本（CJK） | freetype + harfbuzz + fribidi（portlibs 有）；引擎不带字体 | **低–中（法律>技术）** | 技术上能渲染；CJK 字体文件体积大且授权需自行解决 |
| C8 | 无 OS 服务（线程、网络、subprocess） | 官方 web 版无多线程；Ren'Py 用 threading 做自动重载/下载 | **中** | libnx newlib 的 pthread 支持需实测；必须关闭下载器/更新器/网络（websockets、requests 用不到）；subprocess（自带 Python 启动子进程）需 stub |
| C9 | 打包（NRO/NSP） | 官方 distribute.py 只做 PC 产物（SDK/zip/7z/dmg）；Switch 需 libnx 的 build_romfs/nacptool/build_pfs0 | **低**：上个集群已核实工具链可用 | RomFS 大小与私有权（private data）需处理；社区用 generate_private.py + RSA（renpy.encryption 已禁） |
| C10 | 性能 | Switch CPU 4×A57 @1.0GHz，内存 4GB（自制程序可用约 3GB） | **未知，需真机/模拟器实测** | CPython 解释器 + GLES，文字 AVG 逻辑轻、渲染重；无 JIT；启动时间与内存峰值是风险 |

## 专项 D：路线对比

| 路线 | 做法 | 法律 | 工作量 | 结论 |
| --- | --- | --- | --- | --- |
| a) 官方源码 + 自建 Switch 平台层 | 锁 8.5.3（SDL2），自写 CPython 3.12.8 交叉补丁 + 平台层（路径/渲染/存档/字体/媒体），自写 native 入口 | **干净**：Ren'Py MIT+LGPL（需 LGPL 合规）、CPython PSF | 4–6 周探针；3–5 人月最小可跑；6–12 人月可发布 | **推荐长期路线**；与 GalNX 自有框架目标一致 |
| b) NXPython 式补丁栈 | 复制/参考 NXPython 的 CPython 3.14 补丁 | **不干净**：NXPython 无许可证；且 3.14≠3.12.8 | 同 a 的 C1 | 不可直接用；只能"知道有人做成过" |
| c) .rpy 子集转译/预编译 | 不跑完整 Python，只实现 Ren'Py 子集 | 取决于实现 | 大（且永远追不上引擎） | 不推荐：Ren'Py 游戏大量依赖 Python 表达力 |
| d) Switchroot Android + 官方 Android 构建 | Switch 上装 Android，跑官方 Ren'Py Android 包 | **最干净**（官方支持路径） | 小（用户侧装 Android） | **可作"立即能玩"的备选与对照基线**；不是原生 NRO/NSP，性能/续航/门槛是代价 |

## 专项 E：可复现构建前置条件矩阵（路线 a）

| 前置条件 | 状态（本轮证据） | 缺口 / 风险 |
| --- | --- | --- |
| devkitPro devkitA64 工具链 | 已验证存在（上一轮集群 A：/opt/devkitpro/devkitA64，gcc 13.3.1） | 需 Linux/WSL2/Docker（devkitpro/devkita64 镜像） |
| devkitPro portlibs：switch-sdl2、switch-sdl2_image/mixer/ttf/gfx、switch-ffmpeg、switch-freetype、switch-libfribidi、switch-libpng/zlib/bzip2 | 社区 setup.bash 已列全包名，devkitPro pacman 可装 | harfbuzz 需随 SDL2_ttf（devkitPro 自带）；ffmpeg 版本与 8.5.3 要求（4.3.1）需核对 |
| CPython 3.12.8 交叉编译 | **缺失** | 需自写补丁（C1），最大工作量 |
| Ren'Py 8.5.3 源码 | 有（renpy-8.5.3-source.tar.bz2 77,069,263 B，或 git clone 8.5.3.26051504=39895c1e） | 无 |
| Cython 3.x + setuptools | pyproject dev 组 cython>=3.3.0 | 需在交叉环境外生成 C 或用 host 编译 |
| host Python 3.12（用于 Cython/构建脚本） | 官方要求 3.12.8–3.12.x | 需与目标 Python 版本区分 |
| 官方 renpy-build 参照 | 有 tag renpy-8.5.3.26051504=7bfab40c（SDL2 时代 tasks/sdl2.py） | 脚本无许可证，只能读不能抄 |
| NRO/NSP 打包 | devkitPro 的 build_romfs/nacptool/build_pfs0 可用 | RomFS 上限、private data 处理 |
| 测试游戏 | 见专项 G | 资产许可需核实 |
| 真机/模拟器 | 本轮禁止；可用 Ryujinx（上一轮集群 A 已核实存在） | 无 |

## 专项 F：对 GalNX 的结论与下一步 PoC 建议

### F1. 结论
- **Ren'Py 官方源码可以独立移植，但不是"接一个库"的量级**：它是一个完整 Python 运行时 + C 扩展 + 引擎，Switch 适配缺失的正好是最难的一层（CPython 交叉编译到 newlib、平台路径/存档、GLES 渲染器）。
- **不要用社区移植**（四个仓库全部无许可证，且 fork 血统复杂）；它们只能用来确认"哪些层必须改"。
- **版本必须锁 8.5.3.26051504（commit 39895c1e017f0b36ffea2447d97eccd69d76ee1c）**：SDL2（devkitPro 现成）、有完整源码与依赖锁（renpy-build 同 tag 7bfab40c）；**不要跟 master**（SDL3 迁移中，devkitPro switch-sdl3 未验证）。
- **法律上可行但需 LGPL 合规**：Ren'Py 主体 MIT、部分 LGPL（FFmpeg/Fribidi/chardet 等），分发静态链接产物时要提供可重链接方式与源码；生成的项目文件是 CC0，可自由分发。
- **备选捷径值得并列评估**：Switchroot Android + 官方 Android 构建（法律最干净、工程最省），可作为"用户现在就能玩"的兜底，并作为原生移植的对照基线。

### F2. 最小 PoC（4–6 周，1–2 人，go/no-go）
1. **PC 侧基线**（1 周）：Linux/WSL2 上按 README 用 uv + ./run.sh 构建 8.5.3，跑通官方 tutorial/the_question → 证明工具链与源码可用。
2. **CPython 交叉探针**（2–3 周，最高风险）：devkitA64 编出 **静态 libpython3.12.a** + 最小可执行，在 Switch（真机或 Ryujinx）上跑出 REPL / 打印 sys.platform、os.listdir("romfs:/")、open 读写 sdmc。**这是 go/no-go 的关键判据**；若 2–3 周内做不出来，转备选路线 d。
3. **SDL2 窗口探针**（1 周）：用 devkitPro switch-sdl2 开窗口 + GLES 清屏 + 读手柄/触摸，确认渲染与输入通路。
4. **Ren'Py 最小闭环**（1–2 周）：把 renpy.pygame 绑定 + _renpy 编进 Switch，用 romfs 放一个自建最小工程（一张图 + 一句台词），跑通"启动→显示→点击→退出"。
5. **判据**：能进游戏主菜单并稳定运行 10 分钟不崩、内存峰值可测、存档可写 sdmc。通过后再评估 3–5 人月的最小可跑版本。
- 投入估计：探针 4–6 周（1–2 人）；最小可跑 3–5 人月；可发布（含视频/字体/存档/性能调优）6–12 人月。

### F3. 风险表
| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| CPython 3.12 到 newlib 的交叉编译失败/超期 | **高** | 先做 F2.2 探针；不行转路线 d |
| LGPL 静态链接合规 | 中 | 保留 .o/提供源码与重链接脚本；发布前法务确认 |
| 无 JIT + 1.0GHz CPU 性能不足 | 中 | 先 gles 渲染器；限制视频；实测帧率/加载时间 |
| 字体（CJK）授权与体积 | 中 | 随游戏分发时由游戏方提供字体；框架不内置 |
| 存档/路径写死导致兼容性差 | 中 | 统一 sdmc:/switch/<title-id>/ 布局；用官方环境变量机制 |
| 社区移植无许可证的"污染" | 高 | **明令禁止复制其 patch/脚本**；自写实现并留证 |
| 跟 master 引入 SDL3 风险 | 中 | 锁 8.5.3；SDL3 另立后续评估 |

## 专项 G：可用于测试的合法资源候选（均需用户最终核实）

1. **自建 Ren'Py 工程（最干净，推荐首选）**：用官方 SDK/CLI 新建项目（renpy launcher 的 "Create New Project"），游戏内容 100% 自写。许可证依据：license.rst 的 Generated Project Dedication 明确"未修改的 Ren'Py 生成的新项目文件（game/gui.rpy、options.rpy、screens.rpy、script.rpy、game/gui 图片）为 CC0 1.0 公有领域"；引擎本身 MIT+LGPL。→ 可自由分发、可进仓库做回归测试资产（建议只提交自写的 .rpy 与占位图）。
2. **官方 SDK 内置 the_question（官方 demo 工程）**：位于官方 SDK（renpy-8.5.3-sdk.zip）内的 the_question/ 目录（distribute.py L182 原文 `for i in ["tutorial", "launcher", "the_question"]:` 证明官方分发这三个工程）。**但 license.rst 并未对其美术/脚本资产单独声明许可**（全文检索 tutorial/question/demo/example 零命中）→ **不能断言可自由分发**；只能作为本地测试素材，随框架分发前**必须由用户核实/取得授权**。
3. **官方 SDK 内置 tutorial（教程工程）**：同 2，资产许可未单列，需用户核实；适合做"引擎功能覆盖"测试（文本框、选项、存档、转场）。
4. （补充，非游戏）**renpy/renpy 仓库 testcases/pytests**：引擎自带 pytest 用例（MIT 代码），可在 PC 侧做构建回归，不能替代真机运行测试。

## 未验证 / 失败项

| 项 | 原因 | 影响 |
| --- | --- | --- |
| 8.5.3 release 的 sdkarm 目标架构 | 仅取到资产名与字节数，未下载解包 | 不能断言官方支持树莓派/ARM Linux |
| renpy-build 的 tasks 全量依赖清单 | 逐 task 读取未穷尽（46 个 task 文件只精读 sdl3/python3/sysroot/toolchain） | 依赖锁版本表不完整，PoC 时需补 |
| uyjulian/renpy-switch 的构建脚本与 Ren'Py 版本 | 默认分支 landing 根目录只有 README，未查其他分支/history | 该条目的构建入口与产物类型未取证 |
| 社区移植在真机/模拟器的实际运行状态 | 本轮禁止构建/运行，只有 README 与 CI 配置证据 | 所有"能跑"均是 README/CI 声称，非已验证 |
| devkitPro switch-sdl3 的可用性 | master 迁 SDL3 后需要，但本轮未查 devkitPro 仓库 | 影响"跟 master"路线的可行性 |
| libnx romfs 的 opendir/scandir 支持、newlib pthread 支持 | 未在真机/源码级核实 libnx 版本细节 | 影响 loader.py 与线程模型 |
| devkitPro switch-ffmpeg 的具体版本与 renpysound API 匹配 | 未查 portlib 版本 | 影响视频/音频 |
| Ren'Py 8.5.3 的实际版本字符串（vc_version.py） | 未取（pyproject master 写 8.99.99 是开发版） | release 号以 tag 为准 |
| the_question/tutorial 资产许可证 | license.rst 未单列 | 测试资源只能本地用，不能随框架分发 |
| 网页版 web_fetch 通道 | 本会话 web_fetch 持续失败（HTTP 404 failed to fetch URL），全部改走 env_download + 代理 | 已用替代通道补齐，无缺口 |

## 对 GalNX 的建议

1. **版本锁定**：Ren'Py 基线锁 **8.5.3.26051504 = 39895c1e017f0b36ffea2447d97eccd69d76ee1c（2026-05-16）**，依赖参照 renpy-build 同 tag **7bfab40c1174f622f644b24669afd5fb167fbb79（2026-05-13，SDL2 2.0.20/2.0.14、SDL2_image 2.6.2、ffmpeg 4.3.1、Python 3.12.8、freetype 2.13.3、harfbuzz 8.0.1、fribidi 1.0.7）**。禁止追 master（8.99.99/SDL3）。
2. **接入顺序**：① 先做 F2 的 4 步探针（CPython 交叉是 go/no-go）；② 探针通过后写平台层（路径/存档/渲染器/媒体/字体，需求清单用专项 B3 的 6 层，实现自写）；③ 最后做打包（NRO/NSP）与性能/兼容性测试。
3. **法律前置**：把 LGPL 合规（FFmpeg/Fribidi/chardet 等静态链接）与字体授权列入发布清单；社区四个仓库代码**一律不得复制**（无许可证）。
4. **并行备选**：把 Switchroot Android + 官方 Android 构建作为"可立即玩"的兜底方案评估（官方支持、法律最干净），并作为原生移植的对照基线。
5. **阻塞项**：CPython 3.12.8 → devkitA64/newlib 的交叉编译（自研补丁）是唯一可能让路线 a 失败的点；建议在投入平台层之前先用 2–3 周验证。

<!-- AUDIT-JSON-BEGIN -->
```galnx-audit
[
  {
    "name": "renpy/renpy",
    "url": "https://github.com/renpy/renpy",
    "default_branch": "master",
    "head_sha": "98401410511152b98f2b38fecc942dc084f523eb",
    "head_date": "2026-10-29",
    "pinned": "8.5.3.26051504 = commit 39895c1e017f0b36ffea2447d97eccd69d76ee1c (2026-05-16)",
    "license_spdx": "MIT",
    "license_file": "sphinx/source/license.rst（仓库无根目录 LICENSE；REST /license 404、licenseInfo=null）",
    "license_notes": "主体 MIT，但含 LGPL 部分（license.rst 原文：Portions of Ren'Py are derived from source code that is licensed under the GNU Lesser General Public License, so Ren'Py games must be distributed in a manner that satisfies the LGPL）。依赖含 LGPL（FFmpeg、Fribidi、chardet、libusb）、MPL-2.0（certifi）、Apache-2.0（requests、rsa）、Zlib（SDL2、SDL2_image、SDL2_ttf、freetype、tinyfiledialogs、zlib）、3-clause BSD（ANGLE、libyuv、assimp、pysocks、websockets、xz）、Python License、AOM BSD+专利、Artistic（zsync）等。生成的新项目文件（未修改）为 CC0-1.0。静态链接 LGPL 组件分发时需提供可重链接方式与源码。",
    "archived": false,
    "last_push": "2026-10-29",
    "stars": 6951,
    "open_issues": 203,
    "build_system": "setuptools + Cython（setup.py build_ext，pkg-config 探测依赖；开发流程 uv sync 后 ./run.sh）；pyproject.toml 无 build-system 段；README 明示 setup.py 不支持交叉编译",
    "build_deps": "Python >=3.12.8,<3.13；Cython>=3.3.0；8.5.3 用 SDL2（pkg-config sdl2）；libavformat/libavcodec/libavutil/libswresample/libswscale；freetype2；harfbuzz；fribidi；assimp；zlib/libpng/libjpeg；master 已迁 SDL3（packages=sdl3）",
    "readme_claims": "README.rst：apt 依赖列表（libsdl2-*/libav*/harfbuzz/freetype/fribidi 等）、Ren'Py requires SDL_image 2.6 or greater、编译模块用 ./run.sh、其他平台用 pkg-config、可用 RENPY_CC/RENPY_CXX/RENPY_CFLAGS/RENPY_LDFLAGS 覆盖；关键声称：Setup.py does not support cross-compiling. See https://github.com/renpy/renpy-build for software that cross-compiles Ren'Py for many platforms.",
    "readme_claim_url": "https://raw.githubusercontent.com/renpy/renpy/master/README.rst",
    "risks": [
      "官方无 Switch 平台分支：renpy/__init__.py 平台组只有 windows/mac/linux/android/ios/web 六组",
      "master 已迁 SDL3，devkitPro switch-sdl3 可用性未验证；移植基线应锁 8.5.3（SDL2）",
      "无根目录 LICENSE 文件，GitHub API 识别不到 SPDX，许可证结论基于 license.rst 原文",
      "LGPL 组件静态链接的合规成本（可重链接、源码提供）",
      "官方不支持交叉编译，必须自写交叉构建与平台层"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "release 资产 renpy-8.5.3-sdkarm.tar.bz2 的目标架构未取证（仅取到名称与字节数）",
      "8.5.3 源码中 renpy/vc_version.py 的实际版本字符串未取（pyproject master 写 8.99.99 为开发版）",
      "真机/模拟器运行未验证（本轮禁止构建与运行）"
    ],
    "source_urls": [
      "https://github.com/renpy/renpy",
      "https://api.github.com/repos/renpy/renpy",
      "https://api.github.com/repos/renpy/renpy/releases/tags/8.5.3.26051504",
      "https://api.github.com/graphql",
      "https://raw.githubusercontent.com/renpy/renpy/master/README.rst",
      "https://raw.githubusercontent.com/renpy/renpy/master/sphinx/source/license.rst",
      "https://raw.githubusercontent.com/renpy/renpy/8.5.3.26051504/setup.py",
      "https://raw.githubusercontent.com/renpy/renpy/master/setup.py",
      "https://raw.githubusercontent.com/renpy/renpy/master/pyproject.toml",
      "https://raw.githubusercontent.com/renpy/renpy/master/renpy.py",
      "https://raw.githubusercontent.com/renpy/renpy/master/renpy/bootstrap.py",
      "https://raw.githubusercontent.com/renpy/renpy/master/renpy/loader.py",
      "https://raw.githubusercontent.com/renpy/renpy/master/renpy/audio/audio.py",
      "https://raw.githubusercontent.com/renpy/renpy/master/renpy/gl2/gl2shadercache.py",
      "https://raw.githubusercontent.com/renpy/renpy/master/sphinx/source/android.rst",
      "https://raw.githubusercontent.com/renpy/renpy/master/sphinx/source/ios.rst",
      "https://raw.githubusercontent.com/renpy/renpy/master/sphinx/source/web.rst"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "renpy/renpy-build",
    "url": "https://github.com/renpy/renpy-build",
    "default_branch": "master",
    "head_sha": "cff4919ae0ff9976470dbc1d78a1a3ec7fb6432f",
    "head_date": "2026-10-26",
    "pinned": "renpy-8.5.3.26051504 = commit 7bfab40c1174f622f644b24669afd5fb167fbb79 (2026-05-13)",
    "license_spdx": "NOASSERTION",
    "license_file": "无（REST /license 404、licenseInfo=null；仓库无 LICENSE 文件）",
    "license_notes": "无任何许可声明 → 默认保留所有权利；tasks/*.py 与 runtime/*.c 不可复制或并入 GalNX，也不可再分发。其产出的第三方组件各自按其许可（Python PSF、FFmpeg LGPL、SDL zlib、freetype FTL/Zlib 等）。",
    "archived": false,
    "last_push": "2026-10-26",
    "stars": 120,
    "open_issues": 7,
    "build_system": "uv + Python 任务模块（build.sh = exec uv --project renpy run -m renpybuild \"$@\"）；prepare.sh 全局改系统（apt/LLVM22/uv）；无 CI（.github/ 为空）；无 releases",
    "build_deps": "Ubuntu 24.04、root、≥64 GB 磁盘、8 vCPU/16 GB RAM；LLVM/clang 22；debootstrap（Ubuntu jammy glibc sysroot）；master 锁 SDL3 3.4.18 + 4 个下游补丁、Python 3.12.8（Win 3.12.7）、ffmpeg 4.3.1、freetype 2.13.3、harfbuzz 8.0.1、fribidi 1.0.7、libjpeg-turbo 1.5.3、libpng 1.6.43、zlib 1.3.1、openssl 3.3.2；8.5.3 tag 则用 SDL2 2.0.20/2.0.14、SDL2_image 2.6.2",
    "readme_claims": "README.rst：需 Ubuntu 24.04、部分流程必须 root、建议虚拟机、至少 64 GB 磁盘与 8 vCPU/16 GB RAM；Support for unofficial builds of Ren'Py will be limited；平台矩阵 linux x86_64/aarch64、windows x86_64、mac x86_64/arm64、android x86_64/arm64_v8a/armeabi_v7a、ios arm64/sim、web wasm（无 switch）",
    "readme_claim_url": "https://raw.githubusercontent.com/renpy/renpy-build/master/README.rst",
    "risks": [
      "无许可证：脚本只能读不能抄",
      "无 CI、prepare.sh 全局改系统：构建不可在干净环境自动复现",
      "平台矩阵无 switch，需自写平台后端",
      "iOS/mac 构建需自备封闭 SDK，仓库不含"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "46 个 tasks/*.py 未逐个精读，依赖锁版本表不完整（已精读 sdl3/python3/sysroot/toolchain）",
      "未构建（本轮禁止）"
    ],
    "source_urls": [
      "https://github.com/renpy/renpy-build",
      "https://api.github.com/repos/renpy/renpy-build",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/README.rst",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/build.sh",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/prepare.sh",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/runtime/librenpython.c",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/tasks/python3.py",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/tasks/sysroot.py",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/tasks/toolchain.py",
      "https://raw.githubusercontent.com/renpy/renpy-build/master/tasks/sdl3.py"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "jvrcruzGAMES/NXPython",
    "url": "https://github.com/jvrcruzGAMES/NXPython",
    "default_branch": "main",
    "head_sha": "86cde186653a89593359bd59102ed2b878c6fa5b",
    "head_date": "2026-08-09",
    "pinned": "无 tag/release；CPYTHON_COMMIT 1b1c61a94f0685bb0be707b5374376f3084159fe（CPython 3.14 补丁栈，299,892 B）",
    "license_spdx": "NOASSERTION",
    "license_file": "无（REST /license 404、licenseInfo=null）",
    "license_notes": "无任何许可声明 → CPython 3.14 的 Switch 补丁栈不可复制/复用；只能作为 CPython 可在 Switch 运行的存在性证据。其补丁基底是 CPython 上游（PSF 许可），但本仓库的改动部分无授权。",
    "archived": false,
    "last_push": "2026-08-09",
    "stars": 0,
    "open_issues": 0,
    "build_system": "补丁驱动的构建：build.sh（4,240 B）克隆 CPython、打 patches/0001-nxpython-cpython-3.14.patch、用 devkitA64 构建，产物静态 libpython3.14.a 装进 devkitPro portlibs；构建命令 DEVKITPRO=/opt/devkitpro DEVKITA64=/opt/devkitpro/devkitA64 PATH=... ./build.sh -j 8",
    "build_deps": "devkitPro devkitA64；CPython commit 1b1c61a9（3.14）；CPython Platforms/NX/build-portlibs.sh（--destdir 可选）；romfs:/ 与 sdmc:/ 两种路径根语义",
    "readme_claims": "README：NXPython keeps the Nintendo Switch CPython port outside the CPython checkout. This repository tracks patch files only; CPython itself is downloaded into ignored working directories.",
    "readme_claim_url": "https://raw.githubusercontent.com/jvrcruzGAMES/NXPython/main/README.md",
    "risks": [
      "无许可证 → 代码不可复用（最大风险）",
      "单人单日仓库、stars 0、无 issue/PR 历史，维护风险极高",
      "CPython 3.14 与 Ren'Py 8.5.3 要求的 3.12.8–3.12.x 不匹配",
      "未独立构建/运行验证，仅有补丁文本证据"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "未构建、未在 Switch 上运行（本轮禁令）",
      "未逐行审阅 299,892 B 补丁全文（只统计路径命中并读关键行）"
    ],
    "source_urls": [
      "https://github.com/jvrcruzGAMES/NXPython",
      "https://api.github.com/repos/jvrcruzGAMES/NXPython",
      "https://raw.githubusercontent.com/jvrcruzGAMES/NXPython/main/README.md",
      "https://raw.githubusercontent.com/jvrcruzGAMES/NXPython/main/CPYTHON_COMMIT",
      "https://raw.githubusercontent.com/jvrcruzGAMES/NXPython/main/build.sh",
      "https://github.com/jvrcruzGAMES/NXPython/blob/main/patches/0001-nxpython-cpython-3.14.patch"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "jvrcruzGAMES/RenpySwitch",
    "url": "https://github.com/jvrcruzGAMES/RenpySwitch",
    "default_branch": "master",
    "head_sha": "7824039a7d0353b7bfa79ddfcecbf30a375d3d62",
    "head_date": "2026-08-10",
    "pinned": "无 tag/release；HEAD 7824039a（Ren'Py 8.3.4 + NXPython CPython 3.14）",
    "license_spdx": "NOASSERTION",
    "license_file": "无（REST /license 404、licenseInfo=null）",
    "license_notes": "无任何许可声明 → 补丁/脚本不可复制或并入 GalNX，不可分发其产物中的自有部分。其产物含 Ren'Py 引擎代码的部分仍受上游 MIT+LGPL 约束（义务回溯上游，本仓库未授予任何权利）。",
    "archived": false,
    "last_push": "2026-08-10",
    "stars": 2,
    "open_issues": 0,
    "build_system": "GitHub Actions（on push；ubuntu-24.04；container devkitpro/devkita64:20230910）：sudo bash setup.bash → sudo bash build.bash → upload-artifact raw；switch/CMakeLists.txt 输出 renpy-switch.nso；pack_nro.bash/pack_nsp.bash 用 build_romfs/nacptool/build_pfs0 打 NRO/NSP",
    "build_deps": "Ren'Py 8.3.4；Python 3.14 via NXPython（commit 1b1c61a9）；Cython 3.0.10；pygame_sdl2 2.1.0；dkp-pacman：switch-mesa、switch-glad、switch-libdrm_nouveau、switch-sdl2、switch-sdl2_gfx/image/mixer/ttf、switch-ffmpeg、switch-freetype、switch-curl、switch-mbedtls、switch-liblzma、switch-libzstd、switch-zlib、switch-bzip2；另装 switch-libfribidi-1.0.12-1 与 devkitpro-pkgbuild-helpers-2.2.4-2",
    "readme_claims": "README：Build pipeline for Ren'Py on Nintendo Switch, powered by GitHub Actions and NXPython；版本表 Ubuntu 24.04 / devkitpro/devkita64 20230910 / Ren'Py SDK 8.3.4 / Python 3.14 (via NXPython) / Cython 3.0.10；6 步流程（下载源码与 SDL2 绑定→应用 Switch 补丁→Cython 编译 Ren'Py 模块→打包运行时 lib.zip→交叉编译 .nso→组装 raw/）；未声称真机验证通过",
    "readme_claim_url": "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/README.md",
    "risks": [
      "无许可证 → 禁止接入或复制补丁",
      "无 tag/release，无法锁定版本",
      "基线 Ren'Py 8.3.4 落后当前 8.5.3；Python 3.14 与 Ren'Py 官方支持组合不一致",
      "switch/CMakeLists.txt 大量硬编码 /opt/devkitpro 路径，可复现性差",
      "强制 gles 渲染器并关闭 gl2，放弃 GLSL ES 3.00 画面能力",
      "真机/模拟器运行状态未验证"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "未构建、未在真机或模拟器运行（本轮禁令）",
      "renpy.patch 中的 ffmedia/renpysound/ftfont 细节仅统计增删行数，未逐 hunk 解读"
    ],
    "source_urls": [
      "https://github.com/jvrcruzGAMES/RenpySwitch",
      "https://api.github.com/repos/jvrcruzGAMES/RenpySwitch",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/README.md",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/setup.bash",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/build.bash",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/renpy.patch",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/switch/CMakeLists.txt",
      "https://raw.githubusercontent.com/jvrcruzGAMES/RenpySwitch/master/.github/workflows/main.yml"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "knautilus/RenpySwitch",
    "url": "https://github.com/knautilus/RenpySwitch",
    "default_branch": "master",
    "head_sha": "d361e44fbf15cd1bda66d77cce74e29fc2a7f115",
    "head_date": "2025-06-21",
    "pinned": "7.6.3_1.0 = d361e44fbf15cd1bda66d77cce74e29fc2a7f115 (2025-06-21)",
    "license_spdx": "NOASSERTION",
    "license_file": "无（REST /license 404、licenseInfo=null）",
    "license_notes": "无任何许可声明 → 不可复制/接入。其 renpy.patch（44 文件/116 hunk）是 Ren'Py 7.6.3 的衍生改动，同样无授权。",
    "archived": false,
    "last_push": "2026-02-07",
    "stars": 6,
    "open_issues": 0,
    "build_system": "GitHub Actions 构建器（README：Данный репозиторий служит сборщиком RenPy на Github Actions）；入口 setup.bash → build.bash；产物组装 raw/（NSO + romfs 布局）；NRO/NSP 打包脚本在本仓库根目录未见",
    "build_deps": "devkitpro/devkita64:20230910；Ren'Py SDK 7.6.3；Python 2.7；pefile 2019.4.18；Cython 0.29.36；setuptools 0.9.8；pygame_sdl2（7.6 系）",
    "readme_claims": "README（俄语）：本仓库作为在 GitHub Actions 上构建 RenPy 的构建器；版本表 ubuntu-24.04 / devkitpro/devkita64:20230910 / renpy sdk 7.6.3 / python 2.7 / pefile 2019.4.18 / cython 0.29.36 / setuptools 0.9.8",
    "readme_claim_url": "https://raw.githubusercontent.com/knautilus/RenpySwitch/master/README.md",
    "risks": [
      "无许可证 → 禁止接入",
      "Ren'Py 7.6.3 + Python 2.7 已停止维护，与现代 Ren'Py 游戏不兼容",
      "补丁规模大（44 文件/116 hunk），覆盖音频/渲染/解析多层",
      "未见 NRO/NSP 打包脚本；真机未验证"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "未构建、未在真机或模拟器运行（本轮禁令）",
      "build.bash 中具体 dkp-pacman 包列表未逐行记录（只记录了版本表）"
    ],
    "source_urls": [
      "https://github.com/knautilus/RenpySwitch",
      "https://api.github.com/repos/knautilus/RenpySwitch",
      "https://raw.githubusercontent.com/knautilus/RenpySwitch/master/README.md",
      "https://raw.githubusercontent.com/knautilus/RenpySwitch/master/renpy.patch",
      "https://raw.githubusercontent.com/knautilus/RenpySwitch/master/setup.bash",
      "https://raw.githubusercontent.com/knautilus/RenpySwitch/master/build.bash"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "Otorhin/Ren2Switch",
    "url": "https://github.com/Otorhin/Ren2Switch",
    "default_branch": "master",
    "head_sha": "5fce4a28afaa1df262876b7bcce0bee10b3a0360",
    "head_date": "2023-09-04",
    "pinned": "无自身 release；HEAD 5fce4a28（Ren'Py 7.6.1）；tag v1.7.5 = e41dfbe5ee77e9ad673bb4d2854f5983d5f05935 系从上游 uyjulian/renpy-switch fork 继承",
    "license_spdx": "NOASSERTION",
    "license_file": "无（REST /license 404、licenseInfo=null）",
    "license_notes": "无任何许可声明 → 不可复制/接入；14 个 tag 与 release 历史都继承自上游，不代表本仓库授权。",
    "archived": false,
    "last_push": "2023-09-04",
    "stars": 12,
    "open_issues": 0,
    "build_system": "GitHub Actions（on push；ubuntu-latest；container devkitpro/devkita64:20221113）：setup.bash → build.bash（全程 python2）；产物 raw/switch/{exefs/main, romfs/Contents}，最后 7z 打成 raw.zip",
    "build_deps": "Ren'Py 7.6.1；python2.7 + pip2（future/six/typing/requests/ecdsa/pefile==2019.4.18/Cython==0.29.36）；依赖从 github.com/Otorhin/scripts/releases/download/oof/ 与 https://dl.otorh.in/github/rawproject.zip 下载（个人域名，外链稳定性差）；android-native-symbols.zip",
    "readme_claims": "README 描述构建流水线（setup.bash/build.bash + CI）；无明确的真机可用声明",
    "readme_claim_url": "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/README.md",
    "risks": [
      "无许可证 → 禁止接入",
      "2023-09 后停滞，依赖个人域名 dl.otorh.in 与外链 release，可能失效",
      "Ren'Py 7.6.1 + Python 2 旧线，与现代游戏不兼容",
      "无 NRO/NSP 打包脚本；真机未验证"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "未构建、未运行（本轮禁令）",
      "PYGAME_SDL2_VER 具体值未记录（setup.bash 中为变量）"
    ],
    "source_urls": [
      "https://github.com/Otorhin/Ren2Switch",
      "https://api.github.com/repos/Otorhin/Ren2Switch",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/README.md",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/setup.bash",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/build.bash",
      "https://raw.githubusercontent.com/Otorhin/Ren2Switch/master/.github/workflows/ci.yml"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "uyjulian/renpy-switch",
    "url": "https://github.com/uyjulian/renpy-switch",
    "default_branch": "landing",
    "head_sha": "8a75ca3bd5f1c50612a33abae216ecf772b7d330",
    "head_date": "2022-01-04",
    "pinned": "v1.7.5 = e41dfbe5ee77e9ad673bb4d2854f5983d5f05935 (2020-12-20)；仓库已 archived",
    "license_spdx": "NOASSERTION",
    "license_file": "无（REST /license 404、licenseInfo=null）",
    "license_notes": "无任何许可声明；仓库已归档（archived=true），默认分支 landing 仅 README.md，构建脚本不在默认分支可见 → 不可用。",
    "archived": true,
    "last_push": "2022-01-04",
    "stars": 70,
    "open_issues": 7,
    "build_system": "默认分支 landing 根目录仅 README.md；构建脚本与产物类型未取证（未查其他分支/history）",
    "build_deps": "未取证",
    "readme_claims": "README：Sorry, this project is archived! Please use Switchroot Android with the official port of Ren'Py.",
    "readme_claim_url": "https://raw.githubusercontent.com/uyjulian/renpy-switch/landing/README.md",
    "risks": [
      "已归档、作者本人建议改用 Switchroot Android + 官方 Ren'Py",
      "无许可证、源码不可见（landing 仅 README）",
      "2020 年后无更新，已被后继 fork 取代"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "构建脚本、Ren'Py 版本、产物类型未取证（默认分支仅 README.md，未查其他分支）"
    ],
    "source_urls": [
      "https://github.com/uyjulian/renpy-switch",
      "https://api.github.com/repos/uyjulian/renpy-switch",
      "https://api.github.com/repos/uyjulian/renpy-switch/releases",
      "https://raw.githubusercontent.com/uyjulian/renpy-switch/landing/README.md"
    ],
    "audited_at": "2026-10-29"
  }
]
```
<!-- AUDIT-JSON-END -->
