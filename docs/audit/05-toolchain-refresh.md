# 集群 A：Switch 基础工具链版本复核（只读的对照审计）

- 审计日期: 2026-10-29
- 审计员: audit-switch
- 方法: （1）本机 MSYS2 内执行 `pacman -Sy --noconfirm` 同步 dkp-libs / dkp-windows / msys 三个仓库，再 `pacman -Si` 导出全量 1088 条包元数据（719699 B），`pacman -Q` 导出本机 212 包，脚本按包名 join 对比；证据目录 `E:/galnx-build/t9/`（run-date.txt = 2026-10-29T15:10:50Z）。（2）GitHub REST API 经 cred_use(GH_TOKEN)：/repos、/commits?per_page=1、/releases/latest、/tags、/git/commits/{sha}、/license。（3）raw.githubusercontent.com 原始文件（curl 走 127.0.0.1:7897 代理）读 README 说明。（4）Docker Hub tags API 取 devkitpro/devkita64 镜像 tag 与 digest。（5）本机 MSYS2 内用 devkitA64 + CMake 实测含空格路径构建（两次：无空格目录与含空格目录），只编译、不运行。
- 覆盖: 8 个上游对象（installer、pacman-packages、buildscripts、devkitPro/pacman、libnx、Atmosphère、nx-hbmenu、nx-hbloader）+ 本机 17 个 switch 相关包 + 18 个关键 portlib 仓库版本 + 1 项 CMake 构建路径实测

## 总览表
| 条目 | 用途 | 精确版本（tag/commit） | 许可证(SPDX) | 健康 | 结论 |
|---|---|---|---|---|---|
| devkitPro/installer | Windows 官方图形安装器（唯一官方安装路径） | repo HEAD 5d820f47（2023-09-11）；release v3.0.3（2018-06-03） | NOASSERTION（无 LICENSE） | archived=false，last_push 2023-09-11，stars 453，open 4 | 可用但停更；2026-10-29 本机安装链路实测成功 |
| devkitPro/pacman-packages | 包定义（PKGBUILD）源 | master HEAD b9e8b0de（2026-10-16） | NOASSERTION（无仓库级 LICENSE） | archived=false，last_push 2026-10-16，stars 169，open 37 | 仅作包定义元数据源；本机 17 包版本以 dkp-libs.db 为准 |
| devkitPro/buildscripts | 工具链源码构建脚本（复现参考） | release devkitA64_r29.1（2026-10-11）；tag devkitA64_r30 = 9b57a022（2026-06-10） | NOASSERTION（无 LICENSE） | archived=false，last_push 2026-10-10，stars 186，open 2 | 发布页滞后：GitHub 最新 release 是 r29.1，而 pacman 包为 r30 |
| devkitPro/pacman | pacman/ALPM 源码 fork（背景） | master HEAD cf473bcf（2024-08-02）；release v6.0.2（2023-04-05） | GPL-2.0（COPYING） | archived=false，last_push 2024-09-01，stars 204，open 5 | 仅背景；本机 pacman 6.1.0-26 来自 MSYS2 msys 仓库 |
| switchbrew/libnx | 核心用户态库（核心依赖） | HEAD b156b477（2026-10-19）；tag/release v4.12.0 = 7644c9b2（release 2026-09-28） | ISC（LICENSE.md） | archived=false，last_push 2026-10-19，stars 1476，open 13 | 本机包 libnx 4.12.0-1 与最新 release 一致；HEAD 已领先 tag |
| Atmosphere-NX/Atmosphere | 真机 CFW（仅测试环境背景，不作依赖） | release 1.12.1（2026-10-16）；HEAD 6b0c077b | GPL-2.0（LICENSE） | archived=false，last_push 2026-10-16，stars 20252，open 20 | 最新正式版；release 声明支持 firmware 23.0.0；与模拟器链路无关 |
| switchbrew/nx-hbmenu | 真机 Homebrew 菜单（背景） | release v3.6.1（2025-11-15，tag fd26270a）；HEAD 089fdf85（2025-11-16） | ISC（LICENSE.md） | archived=false，last_push 2025-11-16，stars 1406，open 18 | 与 Atmosphère 1.12.1 捆绑版本一致 |
| switchbrew/nx-hbloader | 真机 hbl 加载器（NRO 启动机制参考，背景） | v2.4.5（tag 与 HEAD 同为 82b95122，2025-11-15） | ISC（LICENSE.md） | archived=false，last_push 2025-11-15，stars 417，open 3 | 与 Atmosphère 1.12.1 捆绑 hbl 2.4.5 一致 |

## 与本机 / 上一轮已知状态的差异

| # | 检查项 | 上一轮（00-switch-base.md / devkitpro-2026-10-29.md） | 本次复核（2026-10-29 23:10–23:15 +08:00） | 差异 |
|---|---|---|---|---|
| 1 | 本机 switch 包是否有更新 | 已装 17 个 switch 相关包（14 包 switch-dev 事务 + catnip/general-tools/devkit-env 等） | `pacman -Sy` 后 dkp-libs.db 内 90 个 switch 相关包与本机 17 包全部 same，0 可升级；73 个 portlib 未安装 | 无 |
| 2 | devkitA64 元包 | r30-1 | dkp-libs 仍为 r30-1 | 无 |
| 3 | buildscripts 发布 | 上一轮记 release devkitA64_r29.1 | tag devkitA64_r30 存在但无 release（/releases/tags/devkitA64_r30 = 404）；HEAD 5740da9b（2026-10-10，devkitPPC: update gcc to 16.2.0） | 记录上游发布页滞后 |
| 4 | libnx | 包 4.12.0-1；release v4.12.0 | HEAD b156b477（2026-10-19）领先 tag v4.12.0（tag commit 2026-02-04）；release published 2026-09-28 | 新增 HEAD 事实 |
| 5 | Atmosphère | 1.12.1（2026-10-16） | 仍是最新 release；HEAD 6b0c077b（2026-10-15） | 无 |
| 6 | nx-hbmenu | 上一轮未单列 | v3.6.1（tag fd26270a，2025-11-15）；HEAD 089fdf85（2025-11-16） | 新增条目 |
| 7 | nx-hbloader | 上一轮记录 v2.4.5 与迁移到 switchbrew | v2.4.5（tag = HEAD = 82b95122，2025-11-15） | 补充精确 SHA |
| 8 | devkitPro installer | v3.0.3（2018） | 仍为 v3.0.3；HEAD 5d820f47（2023-09-11） | 无 |
| 9 | pacman-packages | 上一轮经本地解压核对 PKGBUILD | HEAD b9e8b0de（2026-10-16，devkitPPC: release 51） | 无（PKGBUILD 逐条 diff 未重做） |
| 10 | MSYS2 cmake / make | 上一轮记 cmake 4.0.2-1、make 4.4.1-2 | 仓库最新 cmake 4.4.4-1、make 4.4.1-3（均 OUTDATED） | 仅 msys 工具，不影响 aarch64 交叉编译 |
| 11 | Docker devkita64 latest | digest 20260219 | latest 与 20260219 同 digest，last_updated 2026-02-19T17:59 | 无；镜像早于本机 r30 包 |
| 12 | 含空格路径构建 | 上一轮只证明 make 模板在空格路径失败 | CMake 工程在空格路径 configure/build 均成功 | 新增结论（见下节） |

## 本机工具链基线（2026-10-29 实测）

### 已安装的 17 个 switch 相关包（pacman -Q 与 -Si 对比：17/17 same，0 可升级）

| 包 | 仓库 | 本机版本 | 仓库版本 | 状态 |
|---|---|---|---|---|
| catnip | dkp-libs | 0.2.0-1 | 0.2.0-1 | same |
| deko3d | dkp-libs | 0.5.0-1 | 0.5.0-1 | same |
| devkitA64 | dkp-libs | r30-1 | r30-1 | same |
| devkita64-cmake | dkp-libs | 1.1.3-1 | 1.1.3-1 | same |
| devkita64-newlib | dkp-libs | 4.6.0.20260123-4 | 4.6.0.20260123-4 | same |
| devkita64-rules | dkp-libs | 1.1.1-1 | 1.1.1-1 | same |
| libnx | dkp-libs | 4.12.0-1 | 4.12.0-1 | same |
| switch-cmake | dkp-libs | 1.5.2-1 | 1.5.2-1 | same |
| switch-examples | dkp-libs | 20260201-1 | 20260201-1 | same |
| switch-pkg-config | dkp-libs | 0.28-4 | 0.28-4 | same |
| devkit-env | dkp-windows | 1.0.1-2 | 1.0.1-2 | same |
| devkitA64-gdb | dkp-windows | 14.1-1 | 14.1-1 | same |
| devkita64-binutils | dkp-windows | 2.46.0-1 | 2.46.0-1 | same |
| devkita64-gcc | dkp-windows | 16.1.0-1 | 16.1.0-1 | same |
| general-tools | dkp-windows | 1.4.4-1 | 1.4.4-1 | same |
| switch-tools | dkp-windows | 1.13.1-1 | 1.13.1-1 | same |
| uam | dkp-windows | 1.1.0-2 | 1.1.0-2 | same |

包级 License 字段（pacman -Qi，2026-10-29 采集）：libnx custom、devkita64-gcc GPL-3.0-or-later、devkita64-binutils 多许可 SPDX 表达式、devkita64-newlib None、devkitA64 GPL、devkitA64-gdb GPL、deko3d custom、uam ISC、switch-tools ISC、switch-examples custom、switch-cmake None、devkita64-rules custom、catnip custom、general-tools ISC、devkit-env GPL（devkita64-cmake、switch-pkg-config 本轮未取 License 字段）。注意 pacman 元数据许可证与上游仓库 SPDX 不一定一致：例如 libnx 上游 ISC，包内记 custom。

### 仓库中可安装但未安装的关键 portlibs（18 个，版本取自 dkp-libs.db）

| 包 | 最新版本 | 仓库 | pacman -Si URL 字段 | 说明 |
|---|---|---|---|---|
| switch-sdl2 | 2.28.5-4 | dkp-libs | https://libsdl.org | 未安装，未编译验证 |
| switch-freetype | 2.13.3-1 | dkp-libs | https://www.freetype.org/ | 未安装，未编译验证 |
| switch-curl | 7.69.1-5 | dkp-libs | http://www.zlib.net/ | URL 字段指向 zlib.net，与包名不符，未核 PKGBUILD |
| switch-opusfile | 0.10-3 | dkp-libs | https://opus-codec.org/ | 未安装，未编译验证 |
| switch-ffmpeg | 7.1-5 | dkp-libs | https://ffmpeg.org/ | 未安装，未编译验证 |
| switch-libmpv | 0.39.0-4 | dkp-libs | https://mpv.io/ | 未安装，未编译验证 |
| switch-mesa | 20.1.0-5 | dkp-libs | https://mesa.freedesktop.org/archive | 未安装，未编译验证 |
| switch-zlib | 1.3.1-1 | dkp-libs | http://www.zlib.net | 未安装，未编译验证 |
| switch-libpng | 1.6.48-1 | dkp-libs | http://www.libpng.org | 未安装，未编译验证 |
| switch-libjpeg-turbo | 2.1.2-2 | dkp-libs | https://github.com/libjpeg-turbo/libjpeg-turbo | 未安装，未编译验证 |
| switch-harfbuzz | 10.0.1-1 | dkp-libs | https://harfbuzz.github.io/ | 未安装，未编译验证 |
| switch-sdl2_ttf | 2.22.0-2 | dkp-libs | https://libsdl.org/projects/SDL_ttf/ | 未安装，未编译验证 |
| switch-sdl2_image | 2.0.4-1 | dkp-libs | https://libsdl.org/projects/SDL_image/ | 未安装，未编译验证 |
| switch-sdl2_mixer | 2.0.4-2 | dkp-libs | https://libsdl.org/projects/SDL_mixer/ | 未安装，未编译验证 |
| switch-openal-soft | 1.21.1-5 | dkp-libs | https://openal-soft.org/ | 未安装，未编译验证 |
| switch-libvorbis | 1.3.7-1 | dkp-libs | https://wiki.xiph.org/Vorbis | 未安装，未编译验证 |
| switch-libopus | 1.3-2 | dkp-libs | https://opus-codec.org/ | 未安装，未编译验证 |
| switch-mupdf | 1.17.0-1 | dkp-libs | https://www.mupdf.com/ | 未安装，未编译验证 |

### 本机 MSYS2 基础包版本

| 包 | 仓库 | 本机版本 | 仓库最新 | 状态 | 说明 |
|---|---|---|---|---|---|
| pacman | msys | 6.1.0-26 | 6.1.0-26 | same | 与 devkitPro/pacman 仓库 release v6.0.2 无关 |
| msys2-runtime | msys | 3.6.11-4 | 3.6.11-4 | same | — |
| cmake | msys | 4.0.2-1 | 4.4.4-1 | OUTDATED | 仅 msys 本地工具；CMake 构建已实测可用 |
| make | msys | 4.4.1-2 | 4.4.1-3 | OUTDATED | 仅 msys 本地工具 |

## CMake 含空格路径构建实测（新增结论）

已安装的 devkitPro CMake 平台文件位于 `/opt/devkitpro/cmake/Switch.cmake`（include devkitA64.cmake、NX_ROOT=$DEVKITPRO/libnx、要求 aarch64-none-elf-pkg-config，查找 elf2nro/elf2kip/elf2nso/build_pfs0/nacptool/npdmtool/uam）与 `Platform/NintendoSwitch.cmake`（含 nx_generate_nacp、nx_create_nro、NX_ARCH_SETTINGS）。MSYS2 内 cmake 4.0.2、make 4.4.1、无 ninja。

测试项目（两份内容相同）：CMakeLists.txt 为 `cmake_minimum_required(VERSION 3.13)` / `project(m0cmake C)` / `add_executable(m0-cmake main.c)` / `nx_create_nro(m0-cmake NACP)`；main.c 为 libnx consoleInit/printf/consoleUpdate/svcSleepThread/consoleExit 最小程序。构建命令：

```
cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/Switch.cmake"
cmake --build build
```

| 目录 | 是否含空格 | configure | build | 产物 | sha256 |
|---|---|---|---|---|---|
| `/e/galnx-build/t9/cmake-nospace` | 否 | exit 0 | exit 0 | m0-cmake.nro 161989 B | f4c080347eba0f065a76e7c2a13f9fbf682c06ccc07e5f5d953d6687426cc99e |
| `/e/galnx-build/t9/space test/cmake-hello` | 是（space test） | exit 0 | exit 0 | m0-cmake.nro 161989 B | c7b6bb30d87a68b0a97c1a05a81d907bb4205a496edf6a4a9fc1fed733336128 |

输入哈希：CMakeLists.txt 6b192dfd090af40a63b142b6415bc00f213d0e53928708697fc25951cda6cbf5；main.c 87df2daeb2303b4c3db81d0c88c3ad7c9d8da73e47803b4bd9076554110ffbd7。两次 sha256 不同来自 NACP 内嵌时间等非确定性内容，未做可复现性分析。configure 仅出现 CMake 开发者告警 CMP0174（我的 CMakeLists 把 NACP 作空值关键字传入），非致命。

对照：devkitPro make 模板（application）在含空格路径无法构建（switch_rules 内 `$(MAKE) -C $(BUILD) -f $(CURDIR)/Makefile` 未加引号，2026-10-29 已实测），而 CMake 路径实测可行。尚未在真机或模拟器运行该 NRO。

## 条目详情

### 1. devkitPro/installer（Windows 图形安装器）

- URL: https://github.com/devkitPro/installer；默认分支 master；HEAD 5d820f47efb0a7802d71bfcb0249b5ff80c8b759，committer date 2023-09-11T12:26:29Z（repair minor typos (#41)）
- 最近 tag: v3.0.3 = 2ba59cbb90883300826a3a86dbe7bc42a68f7776；release v3.0.3 published 2018-06-03T16:10:25Z，asset devkitProUpdater-3.0.3.exe（196304 B）；tags 另有 v3.0.2/v3.0.1/v3.0.0/v2.2.1
- 许可证: 仓库无 LICENSE（/license 404）→ NOASSERTION；安装行为细节见 `docs/environment/devkitpro-2026-10-29.md`（NSIS、默认路径 c:/devkitPro、内置 MSYS2 2.10.0.1）
- 健康: archived=false；last push 2023-09-11T12:26:29Z；open issues 4；stars 453
- 构建系统: NSIS（nsis/ 目录）；顶层另有 perl/（旧版 devkit*update.pl）
- README 声称: 无 README（raw 404）
- 未验证 / 风险: 2018 年安装器内置 MSYS2 2.10.0，2026 年可用性依赖安装后 pacman -Syu；本机 2026-10-29 安装链路已成功但本轮未重新执行安装器；无许可证声明
- 来源: https://api.github.com/repos/devkitPro/installer ，https://api.github.com/repos/devkitPro/installer/releases/latest ，https://api.github.com/repos/devkitPro/installer/commits?per_page=1

### 2. devkitPro/pacman-packages（包定义仓库）

- URL: https://github.com/devkitPro/pacman-packages；默认分支 master；HEAD b9e8b0de6a6423557fd2a57dc100bf327c79dd4a，2026-10-16T18:41:47Z（devkitPPC: release 51）
- 最近 tag: 无（该仓库为滚动 master，未见 tag 使用；本轮未取 tags 端点）
- 许可证: 无仓库级 LICENSE（/license 404）→ NOASSERTION；各 PKGBUILD 的 license= 字段未逐条核
- 健康: archived=false；last push 2026-10-16T18:42:00Z；open issues 37；stars 169
- 构建系统: PKGBUILD（pacman 包定义），顶层为每包目录（如 libgba、switch-*）
- README 声称: 「devkitPro portlibs：此处所有库均可通过 devkitPro pacman 安装」（README.md 133 B）
- 未验证 / 风险: /contents 根目录响应 >20K 被截断，未枚举顶层；未克隆仓库做 PKGBUILD diff；本机包版本以 dkp-libs.db 为准
- 来源: https://api.github.com/repos/devkitPro/pacman-packages ，https://api.github.com/repos/devkitPro/pacman-packages/commits?per_page=1 ，https://raw.githubusercontent.com/devkitPro/pacman-packages/master/README.md

### 3. devkitPro/buildscripts（工具链源码构建脚本）

- URL: https://github.com/devkitPro/buildscripts；默认分支 master；HEAD 5740da9beb433ff9f5b724fafc1127f3a5ddc944，2026-10-10T22:47:45Z（devkitPPC: update gcc to 16.2.0）
- 最近 tag: devkitA64_r29.1 = 6af2efa45ab83f39416bc24d5c889c75a3ad6c03（commit 2026-02-01T23:50:47Z，remove unused patches）；devkitA64_r30 = 9b57a022648cbd971c2df3652671cc9deaa2482a（commit 2026-06-10T16:01:20Z，devkitA64: release 30）；/releases/tags/devkitA64_r30 返回 404；releases/latest = devkitA64_r29.1（published 2026-10-11T16:20:16Z，无 assets）
- 许可证: 无 LICENSE（/license 404）→ NOASSERTION；README.TXT 未给许可证条款
- 健康: archived=false；last push 2026-10-10T22:57:44Z；open issues 2；stars 186
- 构建系统: POSIX shell 脚本（build-binutils.sh、build-gcc-stage1.sh、build-gcc-stage2.sh、build-newlib.sh、build-crtls.sh、build-devkit.sh、build-mn10200-binutils.sh、makedist.sh、select_toolchain.sh、strip_*.sh）+ patches/
- README 声称: 用这些脚本从源码构建 devkitARM/devkitPPC/devkitA64；不保证自建产物与官方二进制行为一致，建议使用官方二进制；对脚本问题不提供支持；Windows 版工具链在 Linux 上交叉编译
- 未验证 / 风险: 最新 release（r29.1，2026-10-11）落后于 pacman 包（r30-1）对应 tag（2026-06-10）；从源码自建是否等价未验证
- 来源: https://api.github.com/repos/devkitPro/buildscripts ，https://api.github.com/repos/devkitPro/buildscripts/releases/latest ，https://api.github.com/repos/devkitPro/buildscripts/git/commits/6af2efa45ab83f39416bc24d5c889c75a3ad6c03 ，https://raw.githubusercontent.com/devkitPro/buildscripts/master/README.TXT

### 4. devkitPro/pacman（pacman/ALPM 源码 fork）

- URL: https://github.com/devkitPro/pacman；默认分支 master；HEAD cf473bcfbd275044250fa6ce3703dd7059a52273，2024-08-02T00:39:45Z（Ensure that the download process cannot get new privileges）
- 最近 tag: v7.0.0 等（上一轮记录）；release 最新 v6.0.2（2023-04-05T15:17:50Z，asset 仅 macOS 安装包）
- 许可证: GPL-2.0（COPYING；repo API license 字段）
- 健康: archived=false；last push 2024-09-01T06:44:50Z；open issues 5；stars 204
- 构建系统: C 项目，meson.build/meson_options.txt；ALPM 库
- README 声称: ALPM 库概览与内部实现说明（README 为 internals 文档）
- 未验证 / 风险: 本机 pacman 6.1.0-26 来自 MSYS2 msys 仓库，与此仓库 release 无对应关系；未核 fork 与上游差异
- 来源: https://api.github.com/repos/devkitPro/pacman ，https://api.github.com/repos/devkitPro/pacman/commits?per_page=1 ，https://raw.githubusercontent.com/devkitPro/pacman/master/README

### 5. switchbrew/libnx（核心库）

- URL: https://github.com/switchbrew/libnx；默认分支 master；HEAD b156b4774fb2df7b93402169509266da7547fc4c，2026-10-19T19:10:36Z（btdrv: fix size of action field in scan filter event structure and add enum for scan filter actions）
- 最近 tag: v4.12.0 = 7644c9b26099aa2d2145bc72a21ee24190e92085（tag commit 2026-02-04T10:02:17Z，fix mutex locking）；release v4.12.0 published 2026-09-28T07:48:46Z；v4.11.1 = 2fc36019d74785dc53e1ed36606e668ad519e249
- 许可证: ISC（LICENSE.md；/license 报 ISC）
- 健康: archived=false；last push 2026-10-19T19:10:36Z；open issues 13；stars 1476
- 构建系统: Makefile（顶层）；CI 工作流 build.yaml
- README 声称: Nintendo Switch AArch64-only userland library，基于 libctru；安装说明见 Switchbrew wiki
- 未验证 / 风险: HEAD 领先 v4.12.0（数量未取得）；本机包 libnx 4.12.0-1 与 release 一致，可作锁定基线；HEAD 特性不可当作 release 特性
- 来源: https://api.github.com/repos/switchbrew/libnx ，https://api.github.com/repos/switchbrew/libnx/releases/latest ，https://api.github.com/repos/switchbrew/libnx/tags?per_page=10 ，https://raw.githubusercontent.com/switchbrew/libnx/master/README.md

### 6. Atmosphere-NX/Atmosphere（真机 CFW，仅测试背景）

- URL: https://github.com/Atmosphere-NX/Atmosphere；默认分支 master；HEAD 6b0c077b4c608a3a2ee712b8dc35fee87ceb62e8，2026-10-15T23:17:09Z（git subrepo push libraries）；last push 2026-10-16T00:05:50Z
- 最近 tag/release: 1.12.1（published 2026-10-16T00:05:51Z，target master）；assets：atmosphere-1.12.1-master-6b0c077b4+hbl-2.4.5+hbmenu-3.6.1.zip（4772493 B）、fusee.bin（112064 B）
- release 正文要点: 第 94 个正式版；升级必须更新 fusee（fusee-primary 已废弃）；捆绑 hbl 2.4.5 与 hbmenu 3.6.1；支持 firmware 23.0.0（新增 sfdnsres c-ares 命令、fs.mitm BatchRead、browser applets patches 等）
- 许可证: GPL-2.0（LICENSE）
- 健康: archived=false；stars 20252；open issues 20
- 构建系统: Makefile + atmosphere.mk；多 subrepo；Dockerfile
- README 声称: work-in-progress customized firmware for the Nintendo Switch
- 未验证 / 风险: 与 GalNX 模拟器链路无依赖；release 的 firmware 支持声明未在真机验证；真机固件版本必须匹配；GPL-2.0 传染性对仅测试用途无影响，但不可链接进框架产物
- 来源: https://api.github.com/repos/Atmosphere-NX/Atmosphere ，https://api.github.com/repos/Atmosphere-NX/Atmosphere/releases/latest ，https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/README.md

### 7. switchbrew/nx-hbmenu（真机 Homebrew 菜单，背景）

- URL: https://github.com/switchbrew/nx-hbmenu；默认分支 master；HEAD 089fdf85ff82ad7077527092f8615f2e57ffc985，2025-11-16T19:55:14Z（menu-entry: Load the ABI-rev for fileassoc.）
- 最近 tag: v3.6.1 = fd26270a4e4b6994886a57b0738d98229ab4094e；release v3.6.1 published 2025-11-15T16:53:18Z，asset nx-hbmenu_v3.6.1.zip（1249201 B）；与 Atmosphère 1.12.1 捆绑版本一致
- 许可证: ISC（LICENSE.md）
- 健康: archived=false；last push 2025-11-16T19:55:33Z；stars 1406；open issues 18
- 构建系统: Makefile.nx（Switch）/ Makefile.pc（PC）
- README 声称: make nx 构建 Switch 版、make pc 构建 PC 版，make 构建两者；Switch 版需要 switch-dev 包
- 未验证 / 风险: HEAD 领先 tag；仅真机菜单背景，不作依赖
- 来源: https://api.github.com/repos/switchbrew/nx-hbmenu ，https://api.github.com/repos/switchbrew/nx-hbmenu/releases/latest ，https://raw.githubusercontent.com/switchbrew/nx-hbmenu/master/README.md

### 8. switchbrew/nx-hbloader（hbl 加载器，NRO 启动机制参考）

- URL: https://github.com/switchbrew/nx-hbloader；默认分支 master；HEAD 82b95122c5ae8dc059bf23893ba7623c72c86773，2025-11-15T16:49:27Z（nx-hbloader v2.4.5）
- 最近 tag/release: v2.4.5（tag = HEAD = 82b95122…；release published 2025-11-15T16:51:11Z，asset hbl.nsp 40946 B）
- 许可证: ISC（LICENSE.md）
- 健康: archived=false；last push 2025-11-15T16:49:59Z；stars 417；open issues 3
- 构建系统: Makefile（顶层含 Makefile、hbl.json、source/）
- README 声称: 无 README（raw 404）
- 未验证 / 风险: 无文档；构建方式仅由文件列表推断；仅作 NRO 启动机制参考，不是 GalNX 构建依赖
- 来源: https://api.github.com/repos/switchbrew/nx-hbloader ，https://api.github.com/repos/switchbrew/nx-hbloader/releases/latest ，https://api.github.com/repos/switchbrew/nx-hbloader/tags?per_page=10

## 未验证 / 失败项（本轮）

1. libnx HEAD 相对 v4.12.0 的领先提交数未取得：`/compare/v4.12.0...master` 响应超过 cred_use 正文 20K 截断阈值，返回 HTTP 200 但 JSON 解析失败（换 /git/commits 也无法枚举列表）。
2. pacman-packages 与本机 dkp-libs.db 的逐包 PKGBUILD 对照未做：本会话未克隆仓库（禁止克隆大仓库），仅取 HEAD/tree 元数据；包版本以 pacman -Si 为准。
3. switch-sdl2 / switch-freetype 等 portlib 未安装、未编译链接：本机只有 switch-dev 组（含 libnx），portlibs 未装。
4. CMake 产物 m0-cmake.nro 未在 Ryujinx 或真机运行，只验证 configure/build；可运行性未验证。
5. 两次 CMake 构建产物 sha256 不同（161989 B 相同），未分析差异来源（NACP 内嵌时间等），未做可复现构建验证。
6. Docker 镜像 devkitpro/devkita64 latest 未拉取，镜像内工具链版本未核；其 last_updated 2026-02-19，早于本机 r30 包（2026-06 前后），不应视为等价基线。
7. installer v3.0.3 未重新执行安装：本轮只读审计；其内置 MSYS2 2.10.0 的升级路径在上一轮（2026-10-29）实测可用。
8. switch-curl 的 pacman -Si URL 字段为 http://www.zlib.net/（与 curl 不符），未核 PKGBUILD 确认原因。
9. nx-hbmenu HEAD 领先 v3.6.1 的提交未统计；nx-hbloader 无 README，构建方式仅推断。
10. 本轮未核对 buildscripts 的 tag 与 pacman 包实际源码的对应关系（r30 tag 无 release），自建等价性未验证。

## 对 GalNX 的建议

### 版本锁定（对应 PLAN 原则 8、9 与 M0 验收）
- 本机 17 个 switch 相关包 17/17 与当前 dkp-libs.db 一致、0 可升级 → **2026-10-29 的 pacman -Q 快照即当前可锁定基线**：devkitA64 r30-1 / devkita64-gcc 16.1.0-1 / binutils 2.46.0-1 / newlib 4.6.0.20260123-4 / libnx 4.12.0-1 / switch-tools 1.13.1-1 / devkita64-cmake 1.1.3-1 / switch-cmake 1.5.2-1。
- 三位一体锁定证据：① `pacman -Q` 全量快照（212 包，`docs/environment/evidence/pacman-Q-switch.txt`）；② `/var/cache/pacman/pkg` 包文件缓存（64 个包，sha256 已归档）；③ 构建产物 sha256（m0-hello.nro a341e775…、m0-cmake.nro f4c08034…）。
- 不要用 Docker `devkitpro/devkita64:latest` 作为锁定基线：latest digest 停在 2026-02-19，早于本机 r30 包；如用容器需先核镜像内 `pacman -Q`（未验证）。
- libnx 以 release v4.12.0（= 包 4.12.0-1）为基线；若未来必须使用 HEAD 特性，记录 b156b477（2026-10-19）并注明非 release。
- devkitPro 包为滚动仓库，无 snapshot 机制证据（上一轮已查 wiki 无 snapshot 说明）；可行替代=快照 + 缓存包归档 + 产物哈希，必要时再导出 `pacman -Sw` 预下载的包文件。

### 构建系统与路径约束
- make 模板工程（switch_rules）在含空格路径失败（已实测）；CMake 工程在含空格路径成功（本轮实测，2/2 exit 0）。GalNX 若自建构建系统，建议直接采用 CMake + devkitPro Switch.cmake，可避开该限制。
- 无论哪种，M0 验收脚本建议仍使用无空格构建根（如 `E:/galnx-build`），产物再归档回工作区，避免依赖单一构建系统的引号处理。

### 接入顺序（建议，均待实测）
1. 已完成：switch-dev（libnx/工具链/CMake 支持/模板示例）已装并构建出 NRO。
2. 下一步：安装 switch-sdl2（2.28.5-4）+ switch-freetype（2.13.3-1），做最小 SDL2 窗口 + 字体渲染链接验证；两者版本在 dkp-libs 中唯一，无版本选择空间。
3. 再装 switch-harfbuzz（10.0.1-1）、switch-sdl2_ttf（2.22.0-2）、switch-sdl2_image（2.0.4-1）按需。
4. 音视频（switch-libmpv 0.39.0-4 / switch-ffmpeg 7.1-5 / switch-openal-soft）后置，属重依赖，需评估体积与许可证（GPL 组件）。
5. Atmosphère 1.12.1 + hbl 2.4.5 + hbmenu 3.6.1 仅作为真机测试环境版本记录，不进入构建依赖；Ryujinx 模拟器链路不依赖 Atmosphère。

### 阻塞项与风险
- 无新增硬阻塞：dkp-libs 可访问（pacman -Sy 成功）、本机工具链版本已是最新。
- 风险：installer 停更（2018）；buildscripts 发布页滞后（release r29.1 vs 包 r30）；portlibs 版本偏旧（switch-sdl2 2.28.5、switch-curl 7.69.1、switch-mesa 20.1.0），Galgame 引擎所需 API 是否齐全未验证。

## 来源 URLs

- https://devkitpro.org/wiki/Getting_Started ，https://devkitpro.org/wiki/devkitPro_pacman （上一轮）
- https://api.github.com/repos/devkitPro/installer ，https://github.com/devkitPro/installer/releases/tag/v3.0.3
- https://api.github.com/repos/devkitPro/pacman-packages
- https://api.github.com/repos/devkitPro/buildscripts ，https://github.com/devkitPro/buildscripts/releases/tag/devkitA64_r29.1
- https://api.github.com/repos/devkitPro/pacman
- https://api.github.com/repos/switchbrew/libnx ，https://github.com/switchbrew/libnx/releases/tag/v4.12.0
- https://api.github.com/repos/Atmosphere-NX/Atmosphere ，https://github.com/Atmosphere-NX/Atmosphere/releases/tag/1.12.1
- https://api.github.com/repos/switchbrew/nx-hbmenu ，https://github.com/switchbrew/nx-hbmenu/releases/tag/v3.6.1
- https://api.github.com/repos/switchbrew/nx-hbloader ，https://github.com/switchbrew/nx-hbloader/releases/tag/v2.4.5
- https://hub.docker.com/v2/repositories/devkitpro/devkita64/tags?page_size=100
- 本机证据目录：`E:/galnx-build/t9/`（run-date.txt、pacman-Sy 日志、pacman-Q.txt、pacman-Si-all.txt、switch-compare.txt、docker-tags.json、cmake-nospace/、space test/cmake-hello/）

<!-- AUDIT-JSON-BEGIN -->
```galnx-audit
[
  {
    "name": "devkitPro/installer",
    "url": "https://github.com/devkitPro/installer",
    "default_branch": "master",
    "head_sha": "5d820f47efb0a7802d71bfcb0249b5ff80c8b759",
    "head_date": "2023-09-11",
    "pinned": "v3.0.3（release, 2018-06-03；唯一官方 Windows 图形安装器）",
    "license_spdx": "NOASSERTION",
    "license_file": "",
    "license_notes": "GitHub /license 返回 404 Not Found；仓库顶层仅 .gitignore、nsis、perl，无 LICENSE 文件；安装器内含 MSYS2 与 devkitPro 组件，各部分许可随分发包各自声明，未逐项核。",
    "archived": false,
    "last_push": "2023-09-11T12:26:29Z",
    "stars": 453,
    "open_issues": 4,
    "build_system": "NSIS（仓库 nsis/ 目录；安装器产品名 devkitProUpdater）",
    "build_deps": "NSIS 构建；分发物内置 MSYS2 2.10.0.1 7z（安装器 INI 记录），安装时再 pacman -Syu 升级",
    "readme_claims": "无 README（raw.githubusercontent README.md 返回 404）",
    "readme_claim_url": "",
    "risks": "安装器 release 停留在 2018-06-03（v3.0.3），内置 MSYS2 2.10.0；2026 年安装依赖安装后 pacman -Syu 自升级路径（本机 2026-10-29 已实测该路径可用，但非本次重新执行安装器）",
    "verification_level": "read-only",
    "verification_failures": [
      "仓库无 LICENSE 文件，/license 404，无法给出 SPDX 许可证（记为 NOASSERTION）",
      "无 README，README 声称项无法取得"
    ],
    "source_urls": [
      "https://api.github.com/repos/devkitPro/installer",
      "https://api.github.com/repos/devkitPro/installer/commits?per_page=1",
      "https://api.github.com/repos/devkitPro/installer/releases/latest",
      "https://raw.githubusercontent.com/devkitPro/installer/master/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "devkitPro/pacman-packages",
    "url": "https://github.com/devkitPro/pacman-packages",
    "default_branch": "master",
    "head_sha": "b9e8b0de6a6423557fd2a57dc100bf327c79dd4a",
    "head_date": "2026-10-16",
    "pinned": "master@b9e8b0de（2026-10-16）；包版本以 pacman -Si 为准（滚动）",
    "license_spdx": "NOASSERTION",
    "license_file": "",
    "license_notes": "GitHub /license 返回 404 Not Found；顶层为每包目录（PKGBUILD），无仓库级 LICENSE；各 PKGBUILD 内 license= 字段未逐条核对（本会话未克隆仓库）。",
    "archived": false,
    "last_push": "2026-10-16T18:42:00Z",
    "stars": 169,
    "open_issues": 37,
    "build_system": "PKGBUILD 包定义（devkitPro pacman 仓库源）",
    "build_deps": "pacman/makepkg；具体构建依赖在各 PKGBUILD 的 makedepends 中（未逐条核）",
    "readme_claims": "devkitPro portlibs：此处所有库均可通过 devkitPro pacman 安装",
    "readme_claim_url": "https://raw.githubusercontent.com/devkitPro/pacman-packages/master/README.md",
    "risks": "仓库无仓库级许可证声明；本机已安装 17 个 switch 包版本来自 dkp-libs.db，未与 PKGBUILD 逐条 diff",
    "verification_level": "source-inspected",
    "verification_failures": [
      "/contents 根目录响应 >20K 被 cred_use 截断，未能枚举顶层目录（已用 HEAD commit 与 README 佐证结构）",
      "未克隆仓库，PKGBUILD 逐条核对未做",
      "仓库无 LICENSE（API 404）"
    ],
    "source_urls": [
      "https://api.github.com/repos/devkitPro/pacman-packages",
      "https://api.github.com/repos/devkitPro/pacman-packages/commits?per_page=1",
      "https://raw.githubusercontent.com/devkitPro/pacman-packages/master/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "devkitPro/buildscripts",
    "url": "https://github.com/devkitPro/buildscripts",
    "default_branch": "master",
    "head_sha": "5740da9beb433ff9f5b724fafc1127f3a5ddc944",
    "head_date": "2026-10-10",
    "pinned": "参考 tag devkitA64_r30 = 9b57a022（2026-06-10）；GitHub 最新 release 为 devkitA64_r29.1（2026-10-11）",
    "license_spdx": "NOASSERTION",
    "license_file": "",
    "license_notes": "GitHub /license 返回 404 Not Found；顶层无 LICENSE，仅 README.TXT 构建说明；README.TXT 未给出许可证条款，源码构建产物许可需按各组件（GCC/binutils/newlib 等）判断。",
    "archived": false,
    "last_push": "2026-10-10T22:57:44Z",
    "stars": 186,
    "open_issues": 2,
    "build_system": "POSIX shell 构建脚本（build-binutils.sh、build-gcc-stage1.sh、build-gcc-stage2.sh、build-newlib.sh、build-crtls.sh、build-devkit.sh、makedist.sh、select_toolchain.sh）",
    "build_deps": "GCC/binutils/newlib 源码与 patches/；README.TXT 称 Windows 版工具链在 Linux 上交叉编译",
    "readme_claims": "提供从源码构建 devkitARM/devkitPPC/devkitA64 的脚本；不保证自建产物与官方二进制行为一致，建议使用官方二进制分发；对脚本问题不提供支持",
    "readme_claim_url": "https://raw.githubusercontent.com/devkitPro/buildscripts/master/README.TXT",
    "risks": "发布页与 tag 不一致：最新 release devkitA64_r29.1（2026-10-11），而 pacman 包 devkitA64 r30-1 对应 tag devkitA64_r30（2026-06-10），/releases/tags/devkitA64_r30 实测 404；自建工具链与官方包不等价",
    "verification_level": "source-inspected",
    "verification_failures": [
      "tag devkitA64_r30 无对应 GitHub release（API 404 实测）",
      "无 LICENSE 文件",
      "未实际执行构建脚本（只读审计）"
    ],
    "source_urls": [
      "https://api.github.com/repos/devkitPro/buildscripts",
      "https://api.github.com/repos/devkitPro/buildscripts/commits?per_page=1",
      "https://api.github.com/repos/devkitPro/buildscripts/releases/latest",
      "https://api.github.com/repos/devkitPro/buildscripts/git/commits/6af2efa45ab83f39416bc24d5c889c75a3ad6c03",
      "https://api.github.com/repos/devkitPro/buildscripts/git/commits/9b57a022648cbd971c2df3652671cc9deaa2482a",
      "https://raw.githubusercontent.com/devkitPro/buildscripts/master/README.TXT"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "devkitPro/pacman",
    "url": "https://github.com/devkitPro/pacman",
    "default_branch": "master",
    "head_sha": "cf473bcfbd275044250fa6ce3703dd7059a52273",
    "head_date": "2024-08-02",
    "pinned": "不适用：本机 pacman 6.1.0-26 来自 MSYS2 msys 仓库；此仓库仅为 pacman/ALPM 源码 fork",
    "license_spdx": "GPL-2.0",
    "license_file": "COPYING",
    "license_notes": "仓库 /license 响应含大段 base64 被截断未能解析，但顶层存在 COPYING，且 repo API 报 GPL-2.0；与上游 pacman 许可一致。",
    "archived": false,
    "last_push": "2024-09-01T06:44:50Z",
    "stars": 204,
    "open_issues": 5,
    "build_system": "C 项目（pacman/ALPM fork）；顶层含 meson.build、meson_options.txt、build-aux/、src/",
    "build_deps": "meson 构建系统；ALPM 依赖（libarchive、curl、gpgme 等）未逐项核",
    "readme_claims": "README 为 ALPM 库概览与内部实现说明（非快速安装指南）",
    "readme_claim_url": "https://raw.githubusercontent.com/devkitPro/pacman/master/README",
    "risks": "仓库 2024-09 后无 push；发布页最新 release v6.0.2（2023-04-05）但 tags 存在 v7.0.0；本机实际 pacman 来自 MSYS2，不应把此仓库 release 与本机版本对应",
    "verification_level": "source-inspected",
    "verification_failures": [
      "/license 响应截断，未直接读取 COPYING 原文",
      "未核对本机 pacman 二进制与 fork 的差异"
    ],
    "source_urls": [
      "https://api.github.com/repos/devkitPro/pacman",
      "https://api.github.com/repos/devkitPro/pacman/commits?per_page=1",
      "https://api.github.com/repos/devkitPro/pacman/releases/latest",
      "https://raw.githubusercontent.com/devkitPro/pacman/master/README"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "switchbrew/libnx",
    "url": "https://github.com/switchbrew/libnx",
    "default_branch": "master",
    "head_sha": "b156b4774fb2df7b93402169509266da7547fc4c",
    "head_date": "2026-10-19",
    "pinned": "v4.12.0 = 7644c9b26099aa2d2145bc72a21ee24190e92085（release published 2026-09-28）；pacman 包 libnx 4.12.0-1 与之一致",
    "license_spdx": "ISC",
    "license_file": "LICENSE.md",
    "license_notes": "仓库 /license 报 ISC；顶层 LICENSE.md（/license 的 path 字段未取到，以顶层文件列表为准）",
    "archived": false,
    "last_push": "2026-10-19T19:10:36Z",
    "stars": 1476,
    "open_issues": 13,
    "build_system": "Makefile（仓库顶层含 Makefile）；CI 工作流 build.yaml",
    "build_deps": "devkitA64 交叉编译器（本机 aarch64-none-elf-gcc 16.1.0）；README 未列版本要求",
    "readme_claims": "Nintendo Switch AArch64-only userland library，基于 libctru；安装说明指向 Switchbrew wiki（Setting_up_Development_Environment）",
    "readme_claim_url": "https://raw.githubusercontent.com/switchbrew/libnx/master/README.md",
    "risks": "HEAD（2026-10-19）领先最新 tag v4.12.0；若使用 HEAD 特性则脱离 release；领先提交数未取得（compare API 响应超 20K 被截断）",
    "verification_level": "source-inspected",
    "verification_failures": [
      "v4.12.0...master 的领先提交数未取得（/compare 响应 >20K 被 cred_use 截断）",
      "firmware API 覆盖未在本轮重新核验"
    ],
    "source_urls": [
      "https://api.github.com/repos/switchbrew/libnx",
      "https://api.github.com/repos/switchbrew/libnx/commits?per_page=1",
      "https://api.github.com/repos/switchbrew/libnx/releases/latest",
      "https://api.github.com/repos/switchbrew/libnx/tags?per_page=10",
      "https://raw.githubusercontent.com/switchbrew/libnx/master/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "Atmosphere-NX/Atmosphere",
    "url": "https://github.com/Atmosphere-NX/Atmosphere",
    "default_branch": "master",
    "head_sha": "6b0c077b4c608a3a2ee712b8dc35fee87ceb62e8",
    "head_date": "2026-10-15",
    "pinned": "1.12.1（release published 2026-10-16；仅真机测试环境背景，不作构建依赖）",
    "license_spdx": "GPL-2.0",
    "license_file": "LICENSE",
    "license_notes": "顶层 LICENSE；仓库 repo API 报 GPL-2.0；/license 响应因 base64 正文过大截断未解析",
    "archived": false,
    "last_push": "2026-10-16T00:05:50Z",
    "stars": 20252,
    "open_issues": 20,
    "build_system": "Makefile + atmosphere.mk；多 subrepo（exosphere/mesosphere/stratosphere/thermosphere/troposphere）；含 Dockerfile",
    "build_deps": "devkitA64 工具链（仓库未在 release 正文列版本）；各组件依赖 subrepo",
    "readme_claims": "work-in-progress customized firmware for the Nintendo Switch（自定义固件，列出各组件）",
    "readme_claim_url": "https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/README.md",
    "risks": "GPL-2.0 且属系统级 CFW，与 GalNX 模拟器链路无依赖关系；release 声明支持 firmware 23.0.0（新增 c-ares sfdnsres、IStorageForBatchRead 等），真机固件版本需匹配；升级必须更新 fusee（fusee-primary 已废弃）",
    "verification_level": "source-inspected",
    "verification_failures": [
      "release 正文“支持 23.0.0”为 README/release 声称，未在真机验证",
      "未拉取源码构建（只读审计）"
    ],
    "source_urls": [
      "https://api.github.com/repos/Atmosphere-NX/Atmosphere",
      "https://api.github.com/repos/Atmosphere-NX/Atmosphere/commits?per_page=1",
      "https://api.github.com/repos/Atmosphere-NX/Atmosphere/releases/latest",
      "https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "switchbrew/nx-hbmenu",
    "url": "https://github.com/switchbrew/nx-hbmenu",
    "default_branch": "master",
    "head_sha": "089fdf85ff82ad7077527092f8615f2e57ffc985",
    "head_date": "2025-11-16",
    "pinned": "v3.6.1（tag fd26270a4e4b6994886a57b0738d98229ab4094e；release 2025-11-15）；与 Atmosphère 1.12.1 捆绑版本一致",
    "license_spdx": "ISC",
    "license_file": "LICENSE.md",
    "license_notes": "仓库 /license 报 ISC；顶层 LICENSE.md",
    "archived": false,
    "last_push": "2025-11-16T19:55:33Z",
    "stars": 1406,
    "open_issues": 18,
    "build_system": "Makefile.nx（Switch）/ Makefile.pc（PC）；README 明示 make nx 与 make pc",
    "build_deps": "pacman 包 switch-dev（README 明示）",
    "readme_claims": "用 make nx 构建 Switch 版、make pc 构建 PC 版，make 同时构建两者；构建 Switch 版需要 switch-dev 包；发布见 releases/latest；SD 布局见 switchbrew wiki",
    "readme_claim_url": "https://raw.githubusercontent.com/switchbrew/nx-hbmenu/master/README.md",
    "risks": "HEAD（2025-11-16）领先 v3.6.1 tag（2025-11-15）；仅真机 Homebrew 菜单背景，不作 GalNX 依赖",
    "verification_level": "source-inspected",
    "verification_failures": [
      "HEAD 领先 v3.6.1 的提交数未统计",
      "未构建验证"
    ],
    "source_urls": [
      "https://api.github.com/repos/switchbrew/nx-hbmenu",
      "https://api.github.com/repos/switchbrew/nx-hbmenu/commits?per_page=1",
      "https://api.github.com/repos/switchbrew/nx-hbmenu/releases/latest",
      "https://api.github.com/repos/switchbrew/nx-hbmenu/tags?per_page=10",
      "https://raw.githubusercontent.com/switchbrew/nx-hbmenu/master/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "switchbrew/nx-hbloader",
    "url": "https://github.com/switchbrew/nx-hbloader",
    "default_branch": "master",
    "head_sha": "82b95122c5ae8dc059bf23893ba7623c72c86773",
    "head_date": "2025-11-15",
    "pinned": "v2.4.5（tag 与 HEAD 同一 SHA；release 2025-11-15；Atmosphère 1.12.1 捆绑 hbl 2.4.5）",
    "license_spdx": "ISC",
    "license_file": "LICENSE.md",
    "license_notes": "仓库 /license 报 ISC；顶层 LICENSE.md",
    "archived": false,
    "last_push": "2025-11-15T16:49:59Z",
    "stars": 417,
    "open_issues": 3,
    "build_system": "Makefile（顶层含 Makefile、hbl.json、source/）",
    "build_deps": "devkitA64（Makefile 推断；仓库无 README 可供核实）",
    "readme_claims": "无 README（raw.githubusercontent README.md 返回 404）",
    "readme_claim_url": "",
    "risks": "仓库无 README；NRO 启动机制参考用途，非 GalNX 构建依赖；版本由 Atmosphère release 捆绑保持",
    "verification_level": "read-only",
    "verification_failures": [
      "无 README（404），README 声称项无法取得",
      "构建方式仅由顶层文件列表推断，未读 Makefile"
    ],
    "source_urls": [
      "https://api.github.com/repos/switchbrew/nx-hbloader",
      "https://api.github.com/repos/switchbrew/nx-hbloader/commits?per_page=1",
      "https://api.github.com/repos/switchbrew/nx-hbloader/releases/latest",
      "https://api.github.com/repos/switchbrew/nx-hbloader/tags?per_page=10"
    ],
    "audited_at": "2026-10-29"
  }
]
```
<!-- AUDIT-JSON-END -->
