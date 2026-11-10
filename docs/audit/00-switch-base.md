# 集群 A：Switch 基础工具链 审计（只读）

- 审计日期: 2026-10-29
- 审计员: audit-switch（Team Lead: lead；共享任务 task-1）
- 方法: GitHub REST API v3（经 cred_use 携 GH_TOKEN，5000 次/小时）取仓库/提交/tag/release/license 元数据；raw.githubusercontent.com 与 web_fetch 取 README/LICENSE/Makefile/PKGBUILD/NSIS/Dockerfile 原文；git ls-remote 取精确 tag SHA；GitHub release asset HEAD 校验下载可达性；Docker Hub tags API；devkitpro.org wiki 两页全文；curl 经本机代理探测 pkg.devkitpro.org / downloads.devkitpro.org 可达性；pacman-packages 与 devkitPro/installer、buildscripts 归档解压后直读源码。全程只读：未安装任何软件/包、未编译、未克隆仓库、未接触商业游戏数据/密钥/固件。
- 覆盖: 6 个条目（devkitPro 安装与包体系、pacman-packages、libnx、Atmosphere、nx-hbloader、nxlink/switch-tools）

## 总览表

| 条目 | 用途 | 精确版本（tag/commit） | 许可证(SPDX) | 健康 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1. devkitPro 安装器 + pacman 包体系 | 工具链安装方式与包管理 | devkitPro Updater v3.0.3（2018-06-03，installer HEAD 5d820f47，2023-09-11）；内置 MSYS2 2.10.0 | NOASSERTION（installer 仓库无 LICENSE；pacman 本体 GPL-2.0） | installer 2023 年后停更；包库 pkg.devkitpro.org 实测 403 | 官方推荐路径可用性「待实测」；必须准备备选（现代 MSYS2 + dkp 仓库 / Docker） |
| 2. devkitPro/pacman-packages | 包名/版本/许可证/依赖取证 | HEAD b9e8b0de（2026-10-16）；devkitA64 r30-1、libnx 4.12.0-1、switch-sdl2 2.28.5-4、switch-freetype 2.13.3-1 | NOASSERTION（仓库无 LICENSE；271 个 PKGBUILD 各包内声明） | 活跃；37 open issues；无仓库级许可证 | 作为版本与许可证的取证源；不要用它直接构建；包定义不全（switch-tools/uam/hactool 不在公开仓库） |
| 3. switchbrew/libnx | 核心用户态库（UI/文件/服务封装） | v4.12.0 = 7644c9b2（2026-09-28）；pacman 包 libnx 4.12.0-1 | ISC | 活跃；1477 stars；13 open issues；HEAD 2026-10-19 | 核心依赖；固定 v4.12.0（源码 tag 与包版本一致） |
| 4. Atmosphere-NX/Atmosphere | 真机测试环境背景（非依赖） | 1.12.1 = 6b0c077b（2026-10-16） | GPL-2.0 | 活跃；20247 stars；20 open issues | 仅记录测试环境版本；不作为 GalNX 依赖、不随 GalNX 分发 |
| 5. switchbrew/nx-hbloader（原 Atmosphere-NX/nx-hbloader） | NRO 启动机制参考 / 测试环境 | v2.4.5 = 82b95122（2025-11-15） | ISC | 维护低频（上次 push 2025-11-15）；417 stars | 仅测试环境参考；PLAN 中原 URL 已 404，需改仓库地址 |
| 6. nxlink（switchbrew/switch-tools） | NRO 网络部署到真机 | v1.13.1 = 22756068（2024-10-23） | ISC | 稳定、低频更新；181 stars；2 open issues | 属于 pacman 包 switch-tools；用法已从源码 showHelp 取证；实测待 M0 |

## 条目详情

### 1. devkitPro 安装与包体系

- URL（文档）: https://devkitpro.org/wiki/Getting_Started ；https://devkitpro.org/wiki/devkitPro_pacman
- 安装器仓库: https://github.com/devkitPro/installer ；默认分支 master
- HEAD SHA: 5d820f47efb0a7802d71bfcb0249b5ff80c8b759 ；提交日期 2023-09-11T12:26:29Z（提交信息 "repair minor typos (#41)"；pushed_at 2023-09-11T12:26:29Z）
- 最近 tag: v3.0.3 = 2ba59cbb90883300826a3a86dbe7bc42a68f7776（release published 2018-06-03T16:10:25Z）；此前 tag v3.0.2 = 9bba6b22e269402231dab4c1a90ca7f86490bead、v3.0.1 = 42634c673da5786e69573a761618eb8b1f141904、v3.0.0 = edf57df048827d590174b1aafb31c369bb90457d、v2.2.1 = 6dbdda4e0e580b24435700d33493469009f12713
- 官方推荐安装方式（wiki 原文）: "On Windows, there is a graphical installer. On Unix-like platforms such as Linux/macOS, there is devkitPro pacman."；Windows 段：已有 msys2 者按 devkitPro_pacman 页加 dkp 仓库，否则 "download the latest version of the graphical installer from github and run it, following the instructions as you go. - An Internet connection is required."
- 安装器下载地址（GitHub release asset，HEAD 校验 HTTP 200）: https://github.com/devkitPro/installer/releases/download/v3.0.3/devkitProUpdater-3.0.3.exe （asset 大小 196,304 B；release 名 "devkitPro Updater v3.0.3"，published 2018-06-03T16:10:25Z）
- 建议安装路径: C:\\devkitPro（NSIS 源码 InstallDir "c:\\devkitPro"；安装器把 MSYS2 放 C:\\devkitPro\\msys2；MSYS 内映射为 /opt/devkitpro，见 fstab 改写逻辑）。[源码依据，实际行为待实测]
- 环境变量（安装器写 HKLM）: DEVKITPRO=/opt/devkitpro、DEVKITARM=/opt/devkitpro/devkitARM、DEVKITPPC=/opt/devkitpro/devkitPPC（devkitPro.nsi 原文）。[源码依据]
- PATH: 安装器把 C:\\devkitPro\\msys2\\usr\\bin 插入系统 PATH 最前（HKLM Session Manager\\Environment）；MSYS 内由 dkp-toolchain-vars 脚本（devkita64.sh）追加 /opt/devkitpro/tools/bin 与 /opt/devkitpro/devkitA64/bin；switchvars.sh 再追加 portlibs/switch 与 libnx 的 include/lib 及 LIBS=-lnx。[源码依据]
- pacman 初始化/更新命令（wiki 原文；Windows 的定制 MSYS2 内不加 sudo）:
  1) pacman-key --recv BC26F752D25B92CE272E0F44F7FD5492264BB9D0 --keyserver keyserver.ubuntu.com 与 pacman-key --lsign-key BC26F752D25B92CE272E0F44F7FD5492264BB9D0（已有 msys2 系统时；图形安装器已代做）
  2) pacman -U https://pkg.devkitpro.org/devkitpro-keyring.pkg.tar.zst（失败则 pacman-key --populate devkitpro）
  3) /etc/pacman.conf 增加 [dkp-libs] Server = https://pkg.devkitpro.org/packages ；msys2 另加 [dkp-windows] Server = https://pkg.devkitpro.org/packages/windows/$arch/
  4) pacman -Sy（同步）与 pacman -Syu（全量更新）
- 安装 Switch 开发包组与常用包（wiki groups 列表含 switch-dev；Dockerfile 佐证）:
  pacman -S switch-dev  ；pacman -S --needed switch-sdl2 switch-freetype  ；可选 pacman -S switch-portlibs
  （switch-sdl2 2.28.5-4、switch-freetype 2.13.3-1 均存在于 pacman-packages 公开仓库 → 包名有据；实际安装待实测）
- 验证命令（待实测）: aarch64-none-elf-gcc --version、aarch64-none-elf-gcc -dumpmachine（期望 aarch64-none-elf）、pacman -Q | wc -l、pacman -Sg switch-dev、nxlink --help、echo $DEVKITPRO
- 健康: archived=false；last push 2023-09-11；open issues 4；stars 453；仓库无 LICENSE 文件（GitHub API license=null），也无 README（contents/README.md 404）。
- 构建系统/依赖（安装器本体）: NSIS 脚本 nsis/devkitPro.nsi（PRODUCT_NAME devkitProUpdater，PRODUCT_VERSION 3.0.3，RequestExecutionLevel admin），sections "Minimal System"(SecMsys) 与 "Switch Development"(SecSwitchDev)；内置组件清单 nsis/INIfiles/devkitProUpdate.ini: Build=56、URL=http://downloads.devkitpro.org、[msys2] Version=2.10.0、File=msys-2.10.0.1.7z、Size=118660。安装器会解压该 MSYS2 后执行 pacman -Syu --noconfirm，并按勾选组件调用 updateGroup（SwitchDev → switch-dev 组）。
- README 声称: 无 README；wiki 声称 Windows 图形安装器「sets up a customised msys2 install already set up with the devkitPro packages」。
- 未验证/风险: (a) 安装器为 2018 年产物、内置 MSYS2 2.10.0，2026 年是否还能完成 pacman -Syu 并装上当前 dkp 包，完全未验证（待实测）；(b) 本审计实测 pkg.devkitpro.org 被 Cloudflare 403（curl 与 env_download 两种方式），安装器核心步骤（下载 keyring/包库）可能失败；(c) 安装器写 HKLM 与系统 PATH，属机器级改动，需管理员权限；(d) 包库为滚动 latest，无法从仓库锁定精确版本（见「版本锁定建议」）。
- 来源 URLs: https://devkitpro.org/wiki/Getting_Started ; https://devkitpro.org/wiki/devkitPro_pacman ; https://github.com/devkitPro/installer ; https://github.com/devkitPro/installer/releases/tag/v3.0.3 ; https://raw.githubusercontent.com/devkitPro/installer/master/nsis/devkitPro.nsi ; https://raw.githubusercontent.com/devkitPro/installer/master/nsis/INIfiles/devkitProUpdate.ini ; https://raw.githubusercontent.com/devkitPro/docker/master/devkita64/Dockerfile

#### 1.1 实测回填（2026-10-29，M0 安装完成后）

- 安装结果: 官方图形安装器 v3.0.3 实测可用，装到 `D:/devkitPro`（非默认 C 盘），MSYS2 位于 `D:/devkitPro/msys2`，`/etc/fstab` 将其映射为 `/opt/devkitpro`；`DEVKITPRO=/opt/devkitpro`、`MSYSTEM=MSYS` 生效。详见 `docs/environment/devkitpro-2026-10-29.md`。
- switch-dev 实测安装 14 包 / 434.93 MiB（`pacman -Sg switch-dev` 共 13 个成员 + 依赖带入的 devkitA64 工具链）；libnx 4.12.0-1、devkitA64 r30-1、aarch64-none-elf-gcc 16.1.0、switch-tools 1.13.1-1 均实测存在。
- 403 问题定位: MSYS2 登录 shell 不继承 Windows 代理，且无浏览器 UA 被 Cloudflare 拦截；`/etc/pacman.conf` 用 XferCommand 显式注入代理 + UA 后恢复（原文见环境实录 §2.3）。本次 `switch-dev` 前四次事务静默失败即此原因。
- 与本节预判的差异: (a) 安装路径实际为 `D:/devkitPro`（安装器允许自选盘符，非 C 盘亦可）；(b) 2018 年内置 MSYS2 2.10.0 仍能完成 `pacman -Syu` 升级到当前基础包，未出现版本兼容问题；(c) 系统 PATH 是否包含 MSYS2 未复核，MSYS2 内的 PATH 也不含 devkitA64/bin，调用 gcc 需绝对路径或自行 export。
- 仍未验证: nxlink 真机传输、switch-sdl2/freetype 的安装与链接、系统级 PATH/开始菜单快捷方式行为。

### 2. devkitPro/pacman-packages

- URL: https://github.com/devkitPro/pacman-packages ；默认分支 master
- HEAD SHA: b9e8b0de6a6423557fd2a57dc100bf327c79dd4a ；提交日期 2026-10-16T18:41:47Z（提交信息 "devkitPPC: release 51"），pushed_at 2026-10-16T18:42:00Z
- 最近 tag: 本仓库不使用 tag 发布（tags 列表未见与 switch 包相关的版本 tag）；以 HEAD 为准；包版本以 PKGBUILD 内 pkgver 为准。
- 许可证: 仓库无 LICENSE 文件（GitHub API license=null；contents/LICENSE 404）；每个 PKGBUILD 在 license=() 内各自声明。义务要点：各包按其上游许可证执行（GPL/LGPL/zlib/BSD/custom 等）；由于仓库自身无许可证，复用其 PKGBUILD 文本的法律依据不明，只能作为元数据参考。
- 健康: archived=false；stars 168；open issues 37；size 3262 KB；271 个 PKGBUILD；switch/ 下 76 个 portlibs 包定义。
- 构建系统: pacman PKGBUILD + makepkg（devkitPro 定制 msys2 内 makepkg）；交叉工具用 aarch64-none-elf-cmake + Ninja（switch-cmake / switch-pkg-config）。
- 关键包定义（节选，均为 PKGBUILD 原文）:
  - devkitA64（元包，devkita64/devkitA64/PKGBUILD）: pkgver r30-1，license GPL，depends devkita64-binutils>=2.46.0-1、devkita64-gcc>=16.1.0-1、devkita64-newlib>=4.6.0.20260123-4；无 groups 字段。
  - devkita64-rules 1.1.1-1，license custom，depends general-tools>=1.3.1（source https://github.com/devkitpro/devkita64-rules/archive/v1.1.1.tar.gz）。
  - devkita64-newlib 4.6.0.20260123-4（source sourceware newlib + buildscripts refs/tags/devkitA64_r29.2 的 newlib patch）。
  - libnx 4.12.0-1，license custom，groups switch-dev，makedepends devkitA64（source https://github.com/switchbrew/libnx/archive/v4.12.0.tar.gz）。
  - switch-cmake 1.5.2-1，groups switch-dev，depends devkita64-cmake、switch-tools、uam、switch-pkg-config。
  - devkita64-cmake 1.1.3-1，groups switch-dev，depends dkp-cmake-common-utils；catnip 0.2.0-1（多平台 groups，license custom）。
  - switch-pkg-config 0.28-4，groups switch-dev；deko3d 0.5.0-1，license custom，groups switch-dev，depends libnx。
  - switch-examples 20260201-1，license custom，groups switch-dev，makedepends devkitA64；source http://github.com/switchbrew/switch-examples/archive/v20260201.tar.gz；安装到 /opt/devkitpro/examples/switch。
  - 代表性 portlibs: switch-sdl2 2.28.5-4（LGPL，depends switch-mesa、libnx，configure --host=aarch64-none-elf --disable-shared --enable-static）；switch-freetype 2.13.3-1（GPL2+ custom:FreeType，depends switch-bzip2/libpng/zlib）；switch-ffmpeg 7.1-5（GPL）；switch-libmpv 0.39.0-4（GPL）；switch-mupdf 1.17.0-1（AGPL）；switch-harfbuzz 10.0.1-1（LGPL）；switch-mesa 20.1.0-5（MIT，depends switch-libdrm_nouveau）；switch-zlib 1.3.1-1（zlib）；switch-libpng 1.6.48-1（custom）；switch-libjpeg-turbo 2.1.2-2（IJG）；switch-openal-soft 1.21.1-5（LGPL）；switch-libvorbis 1.3.7-1（Xiph）；switch-libopus 1.3-2（BSD）；switch-sdl2_image 2.0.4-1（zlib）；switch-sdl2_mixer 2.0.4-2（zlib）；switch-sdl2_ttf 2.22.0-2（zlib，depends switch-freetype/harfbuzz）；switch-libarchive 3.7.2-7；switch-libwebp 1.0.2-2（BSD）；switch-libvpx 1.8.0-2（BSD）；switch-dav1d 1.5.0-1（BSD）；switch-libplacebo 6.338.2-1（LGPL2.1）。
- switch-dev 组: 公开仓库中显式声明 groups=switch-dev 的 PKGBUILD 共 7 个：libnx、switch-cmake、devkita64-cmake、catnip、deko3d、switch-examples、switch-pkg-config。devkitA64 元包与 devkita64-rules/newlib 无 groups 字段，因此无法从公开仓库判定 switch-dev 的完整成员；但 devkitPro/docker 的 devkita64/Dockerfile 先 dkp-pacman -S switch-dev、随后只补 switch-portlibs/devkitARM/dkp-toolchain-vars/hactool，可推断服务端 switch-dev 组包含工具链（待 pacman -Sg switch-dev 实测）。
- README 声称: "devkitPro portlibs / All the libraries here are installable through devkitPro pacman"（README.md 全文）。
- 未验证/风险: (a) 仓库无 LICENSE，不能当代码复用源；(b) switch-tools、uam、hactool、switch-portlibs 等包的 PKGBUILD 不在公开仓库（只在 depends 里被引用），这些包的定义/版本/许可证不可追踪；(c) 部分 portlibs 版本陈旧（mesa 20.1.0、libvpx 1.8.0、mupdf 1.17.0、SDL2 2.28.5），对现代 galgame 引擎（较新 OpenGL/视频解码）可能不够；(d) PKGBUILD 存在重复 sha256sums 行（switch-examples、devkita64-newlib），后一行覆盖前一行，属打包完整性问题；(e) 包库 DB 403，实际二进制版本与 PKGBUILD 是否一致未验证。
- 来源 URLs: https://github.com/devkitPro/pacman-packages ; https://raw.githubusercontent.com/devkitPro/pacman-packages/master/README.md ; https://raw.githubusercontent.com/devkitPro/pacman-packages/master/libnx/PKGBUILD ; https://raw.githubusercontent.com/devkitPro/pacman-packages/master/devkita64/devkitA64/PKGBUILD ; https://raw.githubusercontent.com/devkitPro/pacman-packages/master/switch/SDL2/PKGBUILD ; https://raw.githubusercontent.com/devkitPro/pacman-packages/master/switch/freetype/PKGBUILD ; https://raw.githubusercontent.com/devkitPro/pacman-packages/master/switch-examples/PKGBUILD

### 3. switchbrew/libnx

- URL: https://github.com/switchbrew/libnx ；默认分支 master
- HEAD SHA: b156b4774fb2df7b93402169509266da7547fc4c ；提交日期 2026-10-19T19:10:36Z（提交信息 "btdrv: fix size of action field in scan filter event structu..."），pushed_at 2026-10-19T19:10:36Z
- 最近 tag/release: v4.12.0 = 7644c9b26099aa2d2145bc72a21ee24190e92085（release "v4.12.0" published 2026-09-28T07:48:46Z，无 assets）；此前 v4.11.1 = 2fc36019d74785dc53e1ed36606e668ad519e249（2026-02-04）、v4.11.0 = a70e0f0111863231f1e56342623190e31405c1ff（2026-02-02）、v4.10.0 = 48cd083ed86443bd51c5c0ea58bdcf1aafc52c80（2025-11-15）、v4.9.0 = 29f6f4fa7a1a884adce5f7115b66e97baa6661d0（2025-05-08）。
- 许可证: ISC（LICENSE.md，731 B，sha256 b8327e3f77c35baf0840797b542c67e5918367fe；原文 "Copyright 2017-2018 libnx Authors" + ISC 标准许可段）。义务要点：保留版权声明与许可声明，二进制分发需附 ISC 声明；无需开源衍生作品。
- 健康: archived=false；stars 1477；open issues 13；size 6567 KB；描述 "Library for Switch Homebrew"。
- 构建系统/依赖: GNU make。nx/Makefile 要求 DEVKITPRO 环境变量（未设置则报 "Please set DEVKITPRO in your environment. export DEVKITPRO=<path to>/devkitpro"），include $(DEVKITPRO)/devkitA64/base_rules，TARGET nx；CI .github/workflows/build.yaml 在 devkitpro/devkita64 容器内执行 make -C nx -j$(nproc)。依赖 devkitA64 交叉工具链（aarch64-none-elf-*）。
- 包关系: pacman-packages 的 libnx PKGBUILD = 4.12.0-1（与 v4.12.0 tag 对应），groups switch-dev；即经 devkitPro pacman 安装 libnx 4.12.0-1 与源码 tag 一致。
- README 声称: "Nintendo Switch AArch64-only userland library." / "Based on libctru."（两行）；安装说明指向 https://switchbrew.org/wiki/Setting_up_Development_Environment 。
- firmware API 覆盖: 源码树 nx/include/switch/services/*.h 共 95 个头文件、nx/include/switch/runtime/ 下 16 个头文件（master 递归树统计）——以服务头文件数量作为 API 覆盖度近似指标；具体固件版本覆盖未逐服务核对。
- 未验证/风险: (a) libnx 通过逆向工程获得系统服务接口，存在法律/合规灰区（许可证 ISC 只覆盖代码本身）；(b) 无 LTS 分支，API 随固件滚动，升级可能破 API；(c) 版本锁定需同时记录源码 tag 与 pacman 包（本审计已确认二者当前一致：4.12.0）。
- 来源 URLs: https://github.com/switchbrew/libnx ; https://api.github.com/repos/switchbrew/libnx ; https://api.github.com/repos/switchbrew/libnx/releases/latest ; https://raw.githubusercontent.com/switchbrew/libnx/master/LICENSE.md ; https://raw.githubusercontent.com/switchbrew/libnx/master/README.md ; https://raw.githubusercontent.com/switchbrew/libnx/master/nx/Makefile ; https://raw.githubusercontent.com/switchbrew/libnx/master/.github/workflows/build.yaml ; https://github.com/devkitPro/pacman-packages/blob/master/libnx/PKGBUILD

### 4. Atmosphere-NX/Atmosphere

- URL: https://github.com/Atmosphere-NX/Atmosphere ；默认分支 master
- HEAD SHA: 6b0c077b4c608a3a2ee712b8dc35fee87ceb62e8 ；提交日期 2026-10-15T23:17:09Z（提交信息 "git subrepo push libraries"），pushed_at 2026-10-16T00:05:50Z
- 最近 tag/release: 1.12.1 = 6b0c077b4c608a3a2ee712b8dc35fee87ceb62e8（release "Atmosphère 1.12.1" published 2026-10-16T00:05:51Z）；assets: atmosphere-1.12.1-master-6b0c077b4+hbl-2.4.5+hbmenu-3.6.1.zip（4,772,493 B）与 fusee.bin（112,064 B）。此前 1.12.0 = 28d6a2e11f2640077bbb8a9fbd463d3fa12b6984、1.11.2 = 5388824be146a89619e8d641acd64599cf1c5f62、1.11.1 = d04c20a049ca5190ddba84e8117abcbb5720b3ff、1.11.0 = 931e3c37fdb9b60956d2c8d01afc6bab09f80047、1.10.2 = eb34f9789c62745d87f37e76761b14d946bac300。
- 许可证: GPL-2.0（LICENSE，18,091 B，sha256 ecbc0593737be657aef92e3adcf3bcbd6fdb812e；全文为标准 GNU GPL v2）。README 的 Licensing 段说明：GPLv2 授权，Nintendo 相关部分有豁免，且作者可对其自写代码采用 Zero-Clause BSD。义务要点：分发二进制/衍生作品须按 GPLv2 提供对应源码与许可文本；与本项目代码混编/静态链接会带来传染性风险。
- 健康: archived=false；stars 20247；open issues 20；size 27900 KB；描述 "Atmosphère is a work-in-progress customized firmware for the Nintendo Switch."。
- 构建系统/依赖: GNU make（Makefile、atmosphere.mk）+ Dockerfile；Dockerfile 基于 devkitpro/devkita64:20260219，ARG PYTHON_VERSION=2.7.18（需 python2.7 构建脚本），并通过 dkp-pacman 安装 switch-tools 与 hactool。仓库组件：Fusée（第一级 loader）、Exosphère（TrustZone）、Thermosphère（EL2 EmuNAND）、Stratosphère（sysmodules）、Troposphère（Horizon OS patches）。
- README 声称: "Atmosphère is a work-in-progress customized firmware for the Nintendo Switch."；release 1.12.1 说明为第 94 个正式版本，随附 hbl 2.4.5 与 hbmenu 3.6.1，并提及对 firmware 23.0.0 的 dns.mitm/fs.mitm 适配。
- 与本项目关系: 仅作为真机测试环境背景记录（提供 hbmenu/hbl 以运行 NRO），不作为 GalNX 依赖、不随 GalNX 分发、不修改主机系统。
- 未验证/风险: (a) GPLv2 传染性；(b) 需对应最新固件版本（release notes 只提及 23.0.0 适配，未做机器验证）；(c) 修改/使用自定义固件存在 ban、变砖等风险，且可能违反 Nintendo 服务条款；(d) 本审计未验证任何真机行为。
- 来源 URLs: https://github.com/Atmosphere-NX/Atmosphere ; https://api.github.com/repos/Atmosphere-NX/Atmosphere ; https://api.github.com/repos/Atmosphere-NX/Atmosphere/releases/latest ; https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/README.md ; https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/LICENSE ; https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/Dockerfile

### 5. switchbrew/nx-hbloader（原 Atmosphere-NX/nx-hbloader）

- URL: https://github.com/switchbrew/nx-hbloader （注：PLAN_DRAFT_v0.1 中的 https://github.com/Atmosphere-NX/nx-hbloader 现已 404，仓库已迁至 switchbrew 组织）
- 默认分支: master
- HEAD SHA: 82b95122c5ae8dc059bf23893ba7623c72c86773 ；提交日期 2025-11-15T16:49:27Z（提交信息 "nx-hbloader v2.4.5"），pushed_at 2025-11-15T16:49:59Z
- 最近 tag/release: v2.4.5 = 82b95122c5ae8dc059bf23893ba7623c72c86773（release "nx-hbloader v2.4.5" published 2025-11-15T16:51:11Z，asset hbl.nsp）；此前 v2.4.4 = b38421d04a0e24a8d29d9b148ba02d658d77d435（2023-10-27）、v2.4.3 = f6c46269ef2429be9ae6e06b6b5c0b3780b78085（2022-10-15）、v2.4.2 = b1406d9eaa2551d8435ba441acea585a24bd72f6、v2.4.1 = 7aefc7a31229a69c54da96e2b8f4940ecc0a9469。
- 许可证: ISC（LICENSE.md，737 B；原文 "Copyright 2017-2018 nx-hbloader Authors" + ISC 标准段）。义务要点：保留版权与许可声明。
- 健康: archived=false；stars 417；open issues 3；size 60 KB；描述 "Host process for loading Switch homebrew NROs"。
- 构建系统/依赖: GNU make。Makefile 在 DEVKITPRO 未设置时报错 "Please set DEVKITPRO in your environment. export DEVKITPRO=<path to>/devkitpro"，include $(DEVKITPRO)/libnx/switch_rules，TARGET := hbl，LDFLAGS = -s -specs=$(DEVKITPRO)/libnx/switch.specs ...；使用 hbl.json（10,603 B，sha256 7cf2d0531d9a587017f5e23e67496b82d24708c2）作为应用元数据；source/ 仅 main.c 与 trampoline.s。依赖 devkitPro + libnx。
- README 声称: 无 README（contents/README.md 404）；仅仓库描述 "Host process for loading Switch homebrew NROs"。
- 与本项目关系: 研究 NRO 启动机制的参考、真机测试环境（Atmosphere 1.12.1 随附 hbl 2.4.5）；不作为 GalNX 依赖。
- 未验证/风险: (a) 仓库地址变迁，PLAN 需更新链接；(b) 需要 Atmosphere 等自定义固件环境才能使用；(c) 真实启动行为未实测。
- 来源 URLs: https://github.com/switchbrew/nx-hbloader ; https://api.github.com/repos/switchbrew/nx-hbloader ; https://api.github.com/repos/switchbrew/nx-hbloader/releases/latest ; https://raw.githubusercontent.com/switchbrew/nx-hbloader/master/Makefile ; https://raw.githubusercontent.com/switchbrew/nx-hbloader/master/LICENSE.md ; https://api.github.com/repos/Atmosphere-NX/nx-hbloader（404 证据）

### 6. nxlink（switchbrew/switch-tools）

- 结论: nxlink 属 devkitPro 包 switch-tools（上游 https://github.com/switchbrew/switch-tools），不是独立项目；Windows 上由 devkitPro 的 MSYS2 环境提供 aarch64-none-elf 工具链与 switch-tools。
- URL: https://github.com/switchbrew/switch-tools ；默认分支 master
- HEAD SHA: 22756068dd0ed6ff9734c59cb4f99ebd3f62555b ；提交日期 2024-10-23T15:24:50Z（提交信息 "npdmtool: don't error with missing debug flags, error with multiple set (#50)"），pushed_at 2024-10-23T15:41:48Z
- 最近 tag/release: v1.13.1 = 22756068dd0ed6ff9734c59cb4f99ebd3f62555b（release v1.13.1 published 2024-10-23T15:41:48Z，无 assets）；此前 v1.13.0 = 0098896307571e35d9c8f9dc8888daf0d1a7398a（2024-10-14）、v1.12.0 = 22471a1f5a854ceca7be9d7f517c30d036655cd2（2022-05-31）。
- 许可证: ISC（COPYING，726 B）。义务要点：保留版权与许可声明。
- 健康: archived=false；stars 181；open issues 2；README 为空文件（0 B）。
- 构建系统/依赖: GNU Autotools（configure.ac AC_INIT([switch-tools],[1.13.1])、Makefile.am）。bin_PROGRAMS = elf2nso elf2nro elf2kip build_pfs0 build_romfs nacptool npdmtool nxlink；nxlink_LDADD = @ZLIB_LIBS@ @NET_LIBS@；依赖 zlib 与 liblz4>=1.7.1；mingw 宿主 NET_LIBS=-lws2_32。
- nxlink 用法（src/nxlink.c showHelp() 原文）: "Usage: nxlink [options] nrofile"；选项 --help/-h、--address/-a（Hostname or IPv4 address of Switch）、--retries/-r（ping 重试次数，默认 10）、--path/-p（上传路径）、--args（传给 nro 的参数）、--server/-s（上传完成后启动服务）。典型用法: nxlink -s app.nro（先启动监听，再让 hbmenu 连接接收）。
- 包关系: pacman-packages 的 switch-cmake 1.5.2-1 depends 含 switch-tools；devkitPro 的 devkita64 Dockerfile 明确 dkp-pacman -S switch-dev + hactool（Atmosphere Dockerfile 另显式 -S switch-tools）。但 switch-tools 的 PKGBUILD 不在 pacman-packages 公开仓库中，故其 pacman 包版本/许可证字段未能取证（待 pacman -Q switch-tools 实测）。
- README 声称: README.md 为 0 字节，无声称内容；工具描述以 --help 源码为准。
- 未验证/风险: (a) pacman 包 switch-tools 的版本未知（可能比上游 1.13.1 新/旧）；(b) nxlink 只做网络传输，需 hbmenu/Atmosphere 环境与同网段 PC；(c) 未在真实 Switch 上验证传输。
- 来源 URLs: https://github.com/switchbrew/switch-tools ; https://api.github.com/repos/switchbrew/switch-tools ; https://raw.githubusercontent.com/switchbrew/switch-tools/master/src/nxlink.c ; https://raw.githubusercontent.com/switchbrew/switch-tools/master/Makefile.am ; https://raw.githubusercontent.com/switchbrew/switch-tools/master/configure.ac ; https://raw.githubusercontent.com/switchbrew/switch-tools/master/COPYING

## 版本锁定建议（devkitPro 滚动更新问题）

**事实依据**
- devkitPro 官方 wiki（Getting_Started、devkitPro_pacman）只描述 [dkp-libs]/[dkp-windows] 两个滚动仓库与 pacman -Syu，全文未出现 snapshot / versioned repository / archive 机制（已逐页读取，未发现）。
- 本审计实测 https://pkg.devkitpro.org/packages/dkp-libs.db 返回 HTTP 403 Forbidden（Cloudflare），curl 与 tools.env_download 两种方式均失败 → 无法枚举历史版本，也无法确认是否存在归档目录。
- Docker Hub devkitpro/devkita64 提供 63 个日期式 tag（latest=20260219，另有 20260215/20260202/20251231/20251117/20250728/20250527/20250512/20241023/.../20230419）；日期 tag = 可按 digest 锁定的快照。
- 上游源码可用 tag 固定：buildscripts 有 devkitA64_r27..r30；devkitA64_r29.1（release 2026-10-11，GCC 15.2.0 / binutils 2.45.1 / newlib 4.6.0.20260123）、devkitA64_r29.2（tag commit 9681963，2026-02-20）、devkitA64_r30（tag commit 9b57a02，2026-06-10）。
- 但 pacman-packages 中 devkitA64 元包（r30-1）要求 devkita64-gcc>=16.1.0-1、devkita64-binutils>=2.46.0-1、newlib>=4.6.0.20260123-4，即二进制包比 buildscripts 最新 release/r29.1 更新 → 源码 tag 不能直接代表 pacman 包版本。

**结论**: devkitPro 的 pacman 仓库是滚动 latest，官方未提供版本化仓库/镜像/snapshot，不能靠仓库本身锁定精确版本；只能靠「安装后记录 + 本地缓存 + 容器/源码」组合锁定。

**可行替代（按推荐顺序）**
1. pacman -Q 全量快照（最低成本，必做）：安装/每次更新后执行 `pacman -Q > dkp-pacman-Q-YYYYMMDD.txt`（另存 `pacman -Qk`；保存 /etc/pacman.conf 与 /etc/pacman.d/mirrorlist）。
2. 导出包文件（离线可重装）：`pacman -Sw --noconfirm <关键包>` 只下载不安装，然后归档 /var/cache/pacman/pkg/*.pkg.tar.zst 与 .sig；重装用 `pacman -U 归档/*.pkg.tar.zst`（先 pacman -U --print 检查依赖顺序）。注意包库 403 时该步骤可能无法执行（待实测）。
3. Docker 快照（跨机可复现）：`docker pull devkitpro/devkita64@sha256:1fc388c3a0d34bd2045a6dadcb1020e069d5f876a187fd705de14b4440c00282`（= tag 20260219/latest 的 multi-arch index digest；amd64 架构子 digest sha256:82575ea78651b530b2e232bb3799cfd1fe331514e053d5f724bb4b28191fb79d）。限制：镜像为 Linux、Windows 需 Docker Desktop/WSL2（本机未安装 docker）；最新 tag 只到 2026-02-19，可能落后滚动源数月。
4. 冻结升级：pacman.conf 加 `IgnorePkg = ...`（标准 pacman 功能，依据 Arch Wiki Pacman 页面；devkitPro 定制的 msys2 分支是否同支持「待实测」）；但仓库只有最新版，降级必须依赖第 2 步的缓存包。
5. 源码级复现：按 buildscripts tag 自建工具链（GCC/binutils/newlib 版本见上）；但 buildscripts 的 README.TXT 声明自建工具链 "for personal use only and may not be distributed by entities other than devkitPro" → 只能用于内部环境复现，不能作为发布物。
6. libnx 单独锁定：libnx 有清晰 tag（v4.12.0 = 7644c9b2），可源码固定；pacman 包 libnx 4.12.0-1 与之对应（当前一致）。switch-tools（nxlink/elf2nro 等）上游 tag v1.13.1 = 22756068，但 pacman 包版本未知，需以 `pacman -Q switch-tools` 为准并写入快照。

## Windows 安装步骤（待实测）

> **2026-10-29 更新: 本节步骤已在 M0 实测执行**（结果见 `docs/environment/devkitpro-2026-10-29.md`）：安装器 v3.0.3 → 补装 switch-dev → 模板构建 NRO 全部走通；唯一偏差是 pkg.devkitpro.org 403 需 XferCommand 修复、构建目录不能含空格。以下保留原始命令级草稿（含「待实测」标注）作为步骤依据，实测结果以环境实录为准。

**前置条件**: Windows 10/11 x64；管理员权限；联网；建议预留 2 GB 以上磁盘（待实测）；本机无 docker/无 MSYS2（本轮范围不装）。

1. [文档] 下载官方图形安装器（GitHub release asset，本审计 HEAD 校验 200）：
   https://github.com/devkitPro/installer/releases/download/v3.0.3/devkitProUpdater-3.0.3.exe
2. [文档] 以管理员身份运行（NSIS RequestExecutionLevel admin）；安装路径保持默认 C:\\devkitPro（源码 InstallDir "c:\\devkitPro"），MSYS2 将位于 C:\\devkitPro\\msys2。
3. [文档] 组件至少勾选 "Switch Development"（安装后执行 switch-dev 组）与 "Minimal System"（MSYS2 运行环境）。
4. [文档+待实测] 安装器会：解压内置 MSYS2 2.10.0（msys-2.10.0.1.7z）→ 写入 fstab 映射 /opt/devkitpro → 将 C:\\devkitPro\\msys2\\usr\\bin 前置到系统 PATH → pacman -Syu --noconfirm → 按组件安装 switch-dev → 写 HKLM 变量 DEVKITPRO=/opt/devkitpro、DEVKITARM、DEVKITPPC → 创建开始菜单 devkitPro → MSYS 快捷方式。**2018 年的内置 MSYS2 与今日包源是否兼容，待实测。**
5. [文档] 打开 MSYS 终端：开始菜单 → devkitPro → MSYS（或运行 C:\\devkitPro\\msys2\\msys2_shell.bat）。后续命令均在 MSYS 终端执行。
6. [待实测] 若安装器失败（例如 pkg.devkitpro.org 403 / 旧 MSYS2 不兼容）走备选方案：先安装官方现代 MSYS2，再按 devkitPro wiki 的 Existing Pacman Install 段：
   pacman-key --recv BC26F752D25B92CE272E0F44F7FD5492264BB9D0 --keyserver keyserver.ubuntu.com
   pacman-key --lsign-key BC26F752D25B92CE272E0F44F7FD5492264BB9D0
   pacman -U https://pkg.devkitpro.org/devkitpro-keyring.pkg.tar.zst   # 失败则 pacman-key --populate devkitpro
   编辑 /etc/pacman.conf 追加 [dkp-libs] Server = https://pkg.devkitpro.org/packages 与 [dkp-windows] Server = https://pkg.devkitpro.org/packages/windows/$arch/
   pacman -Sy && pacman -Syu --noconfirm
7. [待实测] 安装 Switch 开发包（package/group 名有 PKGBUILD/wiki 依据）：
   pacman -S switch-dev
   pacman -S --needed switch-sdl2 switch-freetype
   # 可选：pacman -S switch-portlibs switch-examples dkp-toolchain-vars
8. [待实测] 验证：
   echo $DEVKITPRO                     # 期望 /opt/devkitpro
   aarch64-none-elf-gcc --version      # 期望输出 GCC/binutils 版本
   aarch64-none-elf-gcc -dumpmachine    # 期望 aarch64-none-elf
   nxlink --help                        # 期望 Usage: nxlink [options] nrofile
   pacman -Sg switch-dev                # 记录组成员（快照用）
   pacman -Q > dkp-pacman-Q-$(date +%Y%m%d).txt
9. [待实测] 更新（滚动）：pacman -Syu --noconfirm，更新后立即重做第 8 步快照；如需冻结见「版本锁定建议」。

## 复现最小 Homebrew 构建的前置条件清单（M0 验收）

- [环境] Windows 10/11 x64 + devkitPro（MSYS2）安装成功；DEVKITPRO=/opt/devkitpro 生效。
- [工具链] devkitA64：aarch64-none-elf-gcc、aarch64-none-elf-ld、aarch64-none-elf-objcopy 可用（pacman 包 devkitA64 r30-1，依赖 gcc>=16.1.0 / binutils>=2.46.0 / newlib>=4.6.0.20260123）。
- [核心库] libnx 4.12.0-1（或源码 tag v4.12.0 = 7644c9b2）。
- [构建工具] make（MSYS2 自带）；switch-tools 包（含 elf2nro / nxlink；上游 v1.13.1）；switch-pkg-config（如果使用 portlibs 的 pkg-config）；使用 CMake 时 switch-cmake 1.5.2-1 + devkita64-cmake 1.1.3-1。
- [模板] switch-examples 20260201（安装到 /opt/devkitpro/examples/switch；模板 application 目录）或 switchbrew/switch-examples 的 templates/application；复制模板后 make。
- [产物] app.nro（由 elf2nro 生成）；记录 sha256。
- [测试] 真机：hbmenu（Atmosphere 1.12.1 随附 hbl 2.4.5/hbmenu 3.6.1）+ `nxlink -s app.nro`；或模拟器（属其他集群审计范围，本轮不评）。
- [记录] pacman -Q 快照、libnx tag/SHA、switch-tools 版本、构建命令、产物 hash、许可证清单（libnx ISC 等）。
- [禁止] 商业游戏数据、模拟器密钥、固件、主机改动均不在 M0 范围。

## 未验证 / 失败项

1. **pkg.devkitpro.org 不可达（HTTP 403, Cloudflare）**：curl（带 UA、走代理）与 tools.env_download 两种方式访问 https://pkg.devkitpro.org/packages/dkp-libs.db、https://pkg.devkitpro.org/packages/ 均 403；https://downloads.devkitpro.org/devkitProUpdater-3.0.3.exe 也 403（重定向到 pkg.devkitpro.org）。导致：switch-dev 组完整成员、各 pacman 包实际版本/哈希、包签名/数据库结构均无法取证；Windows 安装可行性因此标「待实测」。
2. **installer 2018 年内置 MSYS2 2.10.0 的可用性未验证**：无法判断 2024-2026 年的 dkp 包源是否仍能被旧 pacman 同步。
3. **switch-tools / uam / hactool / switch-portlibs 的 PKGBUILD 不在公开 pacman-packages 仓库**：这些包只出现在 depends/README/Dockerfile 引用中，版本与许可证不可追踪。
4. **switch-dev 组完整成员未验证**：公开仓库只有 7 个 PKGBUILD 显式声明 groups=switch-dev，devkitA64 元包无 groups 字段；推断工具链由服务端组带入，但无 `pacman -Sg switch-dev` 实测。
5. **devkitPro 版本锁定机制**：wiki 未记载 snapshot/版本化仓库（已读两页），但 403 导致无法确认是否有隐藏归档路径；IgnorePkg 在 dkp 定制 msys2 分支的支持未验证。
6. **本轮无任何实际执行**：禁止安装/编译，故 aarch64-none-elf-gcc --version、nxlink --help、make 模板构建、nxlink 真机传输全部未实测。
7. **Atmosphere 固件兼容性、nx-hbloader 启动行为未机器验证**：仅读取 release notes 与源码。
8. **Docker 镜像快照只到 2026-02-19**（Docker Hub tags 第一页 30 个中最新）：它不是当前滚动源的最新状态，不能代替 pacman -Q 快照。

**实测更新（2026-10-29，M0 安装/构建完成后）**: 第 1、2、4、5、6 项已由实测解除或部分解除——① 403 可用 XferCommand（代理+浏览器 UA）绕过，switch-dev 已安装成功；② 安装器内置旧 MSYS2 仍可完成 `pacman -Syu`；④ `pacman -Sg switch-dev` = 13 个成员（catnip、deko3d、devkita64-cmake、libnx、switch-cmake、switch-examples、switch-pkg-config、devkit-env、devkitA64-gdb、devkita64-binutils、general-tools、switch-tools、uam）；⑤ 仍无 snapshot/版本化仓库证据，改用 `pacman -Q` 快照 + `/var/cache/pacman/pkg` 包归档 + 产物哈希（64 个缓存包已留 SHA-256）；⑥ gcc/nxlink/make 构建已实测（NRO 166,085 B，make 退出码 0），唯 `nxlink` 真机传输仍未做。第 3 项部分解除: switch-tools/uam 已安装并记录版本/许可证（ISC），但其 PKGBUILD 仍不在公开仓库；第 7、8 项维持原状。详见 `docs/environment/devkitpro-2026-10-29.md`。

## 对 GalNX 的建议（版本锁定、接入顺序、阻塞项）

**接入顺序**
1. 先解决工具链安装（阻塞项）：用官方图形安装器 v3.0.3 或现代 MSYS2 + dkp 仓库；两条路都必须先解决 pkg.devkitpro.org 的 403/网络可达性。（2026-10-29 已解除: 图形安装器 v3.0.3 实测可用；403 用 `/etc/pacman.conf` 的 XferCommand 代理+UA 绕过。）
2. 装 switch-dev 后立即导出 `pacman -Q` 快照 + 归档包缓存，作为 M0 的环境真相。
3. 固定 libnx v4.12.0（源码 tag 与包版本一致，7644c9b2 / 4.12.0-1）；固定 switch-tools 上游 v1.13.1（nxlink/elf2nro 语义）。
4. 复现最小 Homebrew 构建（模板 application → make → app.nro），然后才引入 portlibs（SDL2 2.28.5、freetype 2.13.3 等）。

**版本锁定建议（项目层面）**
- 在仓库内维护 docs/audit/snapshots/ 下的 pacman -Q 快照（每次环境变更提交），并记录 pkg.devkitpro.org 可达性探测结果。
- CI/容器构建优先用 devkitpro/devkita64@sha256:1fc388c3...（或更新日期 tag 的 digest）+ 固定 libnx tag；不要依赖 :latest。
- 记录「二进制包版本 vs 源码 tag」对应关系；不要用 buildscripts 自建工具链当发布物（license 限制 personal use only）。

**阻塞项/风险**
- ~~阻塞~~（2026-10-29 已解除）：pkg.devkitpro.org 403（安装/更新/包缓存均受阻）→ 已用 `/etc/pacman.conf` 的 XferCommand（`http_proxy/https_proxy=127.0.0.1:7897` + 浏览器 UA）绕过并完成 switch-dev 安装；后续新机器仍须预先配置代理/UA。
- 风险：2018 安装器内置 MSYS2 2.10.0 可能无法完成今天的一次性安装；备选方案必须写入 M0 计划。
- 风险：PLAN 中 nx-hbloader 链接（Atmosphere-NX/nx-hbloader）已 404，需改为 https://github.com/switchbrew/nx-hbloader。
- 风险：portlibs 版本偏旧（mesa 20.1.0、libvpx 1.8.0 等），若目标引擎要求较新 OpenGL/视频解码，需要上游自行构建 portlibs（属后续阶段，本轮不做）。
- 风险：Atmosphere GPLv2 与测试环境隔离要求；GalNX 代码不得混入 Atmosphere 源码/二进制分发。

## 附：机读数据（供 Lead 脚本解析）

<!-- AUDIT-JSON-BEGIN -->
```galnx-audit
[
  {
    "name": "devkitPro 安装器 + pacman 包体系",
    "url": "https://devkitpro.org/wiki/Getting_Started",
    "default_branch": "master",
    "head_sha": "5d820f47efb0a7802d71bfcb0249b5ff80c8b759",
    "head_date": "2023-09-11",
    "pinned": "devkitPro Updater v3.0.3 (2018-06-03)；工具链为滚动 pacman 源，无法从仓库锁定精确版本",
    "license_spdx": "NOASSERTION",
    "license_file": "",
    "license_notes": "installer 仓库无 LICENSE 文件（GitHub API license=null），无 README；devkitPro/pacman 本体为 GPL-2.0（COPYING 17987B）；各 pacman 包在 PKGBUILD 内单独声明",
    "archived": false,
    "last_push": "2023-09-11T12:26:29Z",
    "stars": 453,
    "open_issues": 4,
    "build_system": "NSIS 安装器（nsis/devkitPro.nsi，PRODUCT_VERSION 3.0.3，RequestExecutionLevel admin）；包管理为 dkp-pacman（dkp-libs/dkp-windows 仓库）",
    "build_deps": "内置 MSYS2 2.10.0（msys-2.10.0.1.7z）；pacman -Syu；switch-dev 组；dkp-toolchain-vars",
    "readme_claims": "wiki: Windows 使用 graphical installer（从 GitHub 下载最新版），需联网；Windows 版安装器 sets up a customised msys2 install already set up with the devkitPro packages",
    "readme_claim_url": "https://devkitpro.org/wiki/Getting_Started",
    "risks": [
      "pkg.devkitpro.org 实测 HTTP 403（Cloudflare），安装器下载 keyring/包库可能失败",
      "内置 MSYS2 2.10.0 为 2018 年产物，2026 年可用性未验证",
      "安装器写 HKLM 环境变量并在系统 PATH 前置 msys2，属机器级改动",
      "滚动源无法从仓库锁定版本"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "pkg.devkitpro.org/packages/dkp-libs.db 与 /packages/ 均 HTTP 403 Forbidden（curl 与 env_download 两种方式均失败），包库内容未取证",
      "downloads.devkitpro.org/devkitProUpdater-3.0.3.exe 重定向到 pkg.devkitpro.org 后 403",
      "本轮禁止安装，安装/验证命令未实测"
    ],
    "source_urls": [
      "https://devkitpro.org/wiki/Getting_Started",
      "https://devkitpro.org/wiki/devkitPro_pacman",
      "https://github.com/devkitPro/installer",
      "https://github.com/devkitPro/installer/releases/tag/v3.0.3",
      "https://raw.githubusercontent.com/devkitPro/installer/master/nsis/devkitPro.nsi",
      "https://raw.githubusercontent.com/devkitPro/installer/master/nsis/INIfiles/devkitProUpdate.ini",
      "https://raw.githubusercontent.com/devkitPro/docker/master/devkita64/Dockerfile"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "devkitPro/pacman-packages",
    "url": "https://github.com/devkitPro/pacman-packages",
    "default_branch": "master",
    "head_sha": "b9e8b0de6a6423557fd2a57dc100bf327c79dd4a",
    "head_date": "2026-10-16",
    "pinned": "仓库 HEAD b9e8b0de（2026-10-16）；devkitA64 r30-1；libnx 4.12.0-1；switch-sdl2 2.28.5-4；switch-freetype 2.13.3-1；switch-tools/uam/hactool 定义不在公开仓库",
    "license_spdx": "NOASSERTION",
    "license_file": "",
    "license_notes": "仓库无 LICENSE 文件（API license=null，contents/LICENSE 404）；271 个 PKGBUILD 在 license=() 内各自声明（GPL/LGPL/zlib/BSD/custom 等），无 SPDX 元数据；仓库本身许可证不明",
    "archived": false,
    "last_push": "2026-10-16T18:42:00Z",
    "stars": 168,
    "open_issues": 37,
    "build_system": "pacman PKGBUILD（makepkg）；交叉编译用 aarch64-none-elf-cmake + Ninja（switch-cmake/switch-pkg-config）",
    "build_deps": "devkitA64 元包 depends devkita64-binutils>=2.46.0-1, devkita64-gcc>=16.1.0-1, devkita64-newlib>=4.6.0.20260123-4；libnx 4.12.0 makedepends devkitA64；switch-cmake deps devkita64-cmake/switch-tools/uam/switch-pkg-config",
    "readme_claims": "README: devkitPro portlibs / All the libraries here are installable through devkitPro pacman",
    "readme_claim_url": "https://raw.githubusercontent.com/devkitPro/pacman-packages/master/README.md",
    "risks": [
      "仓库无 LICENSE，不能作为代码复用源",
      "switch-tools、uam、hactool、switch-portlibs 的 PKGBUILD 不在公开仓库，版本/许可证不可追踪",
      "部分 portlibs 过旧（mesa 20.1.0、libvpx 1.8.0、mupdf 1.17.0）",
      "PKGBUILD 存在重复 sha256sums（switch-examples、devkita64-newlib）",
      "包库 DB 403，PKGBUILD 与二进制包一致性未验证"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "dkp-libs.db HTTP 403，无法核对 switch-dev 组完整成员与实际包版本",
      "switch-tools/uam/hactool PKGBUILD 不在仓库中（仅被 depends 引用）"
    ],
    "source_urls": [
      "https://github.com/devkitPro/pacman-packages",
      "https://raw.githubusercontent.com/devkitPro/pacman-packages/master/README.md",
      "https://raw.githubusercontent.com/devkitPro/pacman-packages/master/libnx/PKGBUILD",
      "https://raw.githubusercontent.com/devkitPro/pacman-packages/master/devkita64/devkitA64/PKGBUILD",
      "https://raw.githubusercontent.com/devkitPro/pacman-packages/master/switch/SDL2/PKGBUILD",
      "https://raw.githubusercontent.com/devkitPro/pacman-packages/master/switch/freetype/PKGBUILD",
      "https://raw.githubusercontent.com/devkitPro/pacman-packages/master/switch-examples/PKGBUILD"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "switchbrew/libnx",
    "url": "https://github.com/switchbrew/libnx",
    "default_branch": "master",
    "head_sha": "b156b4774fb2df7b93402169509266da7547fc4c",
    "head_date": "2026-10-19",
    "pinned": "v4.12.0 = 7644c9b26099aa2d2145bc72a21ee24190e92085（2026-09-28）；pacman 包 libnx 4.12.0-1（一致）",
    "license_spdx": "ISC",
    "license_file": "LICENSE.md",
    "license_notes": "ISC，LICENSE.md 731B，sha256 b8327e3f77c35baf0840797b542c67e5918367fe；原文 Copyright 2017-2018 libnx Authors；义务：保留版权与许可声明",
    "archived": false,
    "last_push": "2026-10-19T19:10:36Z",
    "stars": 1477,
    "open_issues": 13,
    "build_system": "GNU make（nx/Makefile，include $(DEVKITPRO)/devkitA64/base_rules，TARGET nx）；CI 在 devkitpro/devkita64 容器内 make -C nx -j",
    "build_deps": "devkitA64 交叉工具链（aarch64-none-elf-*），DEVKITPRO 环境变量",
    "readme_claims": "README 两行: Nintendo Switch AArch64-only userland library. / Based on libctru.；安装说明指向 switchbrew wiki Setting_up_Development_Environment",
    "readme_claim_url": "https://raw.githubusercontent.com/switchbrew/libnx/master/README.md",
    "risks": [
      "无 LTS，API 随固件滚动",
      "逆向工程接口存在法律/合规灰区（ISC 只覆盖代码）",
      "需要 devkitA64 工具链与 DEVKITPRO 环境"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://github.com/switchbrew/libnx",
      "https://api.github.com/repos/switchbrew/libnx",
      "https://api.github.com/repos/switchbrew/libnx/releases/latest",
      "https://raw.githubusercontent.com/switchbrew/libnx/master/LICENSE.md",
      "https://raw.githubusercontent.com/switchbrew/libnx/master/README.md",
      "https://raw.githubusercontent.com/switchbrew/libnx/master/nx/Makefile",
      "https://github.com/devkitPro/pacman-packages/blob/master/libnx/PKGBUILD"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "Atmosphere-NX/Atmosphere",
    "url": "https://github.com/Atmosphere-NX/Atmosphere",
    "default_branch": "master",
    "head_sha": "6b0c077b4c608a3a2ee712b8dc35fee87ceb62e8",
    "head_date": "2026-10-15",
    "pinned": "1.12.1 = 6b0c077b4c608a3a2ee712b8dc35fee87ceb62e8（2026-10-16）",
    "license_spdx": "GPL-2.0",
    "license_file": "LICENSE",
    "license_notes": "GPLv2 全文，LICENSE 18091B，sha256 ecbc0593737be657aef92e3adcf3bcbd6fdb812e；README Licensing 段称 Nintendo 相关部分豁免且作者可对自写代码用 Zero-Clause BSD；义务：分发须提供对应源码与许可文本，具有传染性",
    "archived": false,
    "last_push": "2026-10-16T00:05:50Z",
    "stars": 20247,
    "open_issues": 20,
    "build_system": "GNU make（Makefile/atmosphere.mk）+ Dockerfile（devkitpro/devkita64:20260219 + python2.7）",
    "build_deps": "devkitA64、switch-tools、hactool、python2.7、lz4（Dockerfile 安装 switch-tools/hactool）",
    "readme_claims": "README: Atmosphère is a work-in-progress customized firmware for the Nintendo Switch.；组件 Fusée/Exosphère/Thermosphère/Stratosphère/Troposphère；release 1.12.1 为第 94 个正式版，随附 hbl 2.4.5 与 hbmenu 3.6.1",
    "readme_claim_url": "https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/README.md",
    "risks": [
      "GPLv2 传染性，不可与 GalNX 代码混编分发",
      "需对应最新固件（release notes 仅提及 23.0.0 适配）",
      "自定义固件存在 ban/变砖及服务条款风险",
      "仅作测试环境背景，不作为依赖"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "固件兼容性与真机行为未机器验证（仅读文本/源码）"
    ],
    "source_urls": [
      "https://github.com/Atmosphere-NX/Atmosphere",
      "https://api.github.com/repos/Atmosphere-NX/Atmosphere",
      "https://api.github.com/repos/Atmosphere-NX/Atmosphere/releases/latest",
      "https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/README.md",
      "https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/LICENSE",
      "https://raw.githubusercontent.com/Atmosphere-NX/Atmosphere/master/Dockerfile"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "switchbrew/nx-hbloader",
    "url": "https://github.com/switchbrew/nx-hbloader",
    "default_branch": "master",
    "head_sha": "82b95122c5ae8dc059bf23893ba7623c72c86773",
    "head_date": "2025-11-15",
    "pinned": "v2.4.5 = 82b95122c5ae8dc059bf23893ba7623c72c86773（2025-11-15）",
    "license_spdx": "ISC",
    "license_file": "LICENSE.md",
    "license_notes": "ISC，LICENSE.md 737B；原文 Copyright 2017-2018 nx-hbloader Authors；义务：保留版权与许可声明",
    "archived": false,
    "last_push": "2025-11-15T16:49:59Z",
    "stars": 417,
    "open_issues": 3,
    "build_system": "GNU make（Makefile，include $(DEVKITPRO)/libnx/switch_rules，TARGET hbl，switch.specs）；hbl.json 元数据",
    "build_deps": "devkitPro + libnx（aarch64-none-elf 工具链）",
    "readme_claims": "无 README（contents/README.md 404）；仓库描述: Host process for loading Switch homebrew NROs",
    "readme_claim_url": "https://api.github.com/repos/switchbrew/nx-hbloader",
    "risks": [
      "PLAN_DRAFT 中链接 Atmosphere-NX/nx-hbloader 已 404，仓库迁至 switchbrew",
      "需 Atmosphere 等自定义固件环境",
      "真机启动行为未实测"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "Atmosphere-NX/nx-hbloader 仓库返回 404（已迁移）"
    ],
    "source_urls": [
      "https://github.com/switchbrew/nx-hbloader",
      "https://api.github.com/repos/switchbrew/nx-hbloader",
      "https://api.github.com/repos/switchbrew/nx-hbloader/releases/latest",
      "https://raw.githubusercontent.com/switchbrew/nx-hbloader/master/Makefile",
      "https://raw.githubusercontent.com/switchbrew/nx-hbloader/master/LICENSE.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "nxlink (switchbrew/switch-tools)",
    "url": "https://github.com/switchbrew/switch-tools",
    "default_branch": "master",
    "head_sha": "22756068dd0ed6ff9734c59cb4f99ebd3f62555b",
    "head_date": "2024-10-23",
    "pinned": "v1.13.1 = 22756068dd0ed6ff9734c59cb4f99ebd3f62555b（2024-10-23）；pacman 包 switch-tools 版本未取证",
    "license_spdx": "ISC",
    "license_file": "COPYING",
    "license_notes": "ISC，COPYING 726B；义务：保留版权与许可声明",
    "archived": false,
    "last_push": "2024-10-23T15:41:48Z",
    "stars": 181,
    "open_issues": 2,
    "build_system": "GNU Autotools（configure.ac AC_INIT([switch-tools],[1.13.1])、Makefile.am）；bin_PROGRAMS = elf2nso elf2nro elf2kip build_pfs0 build_romfs nacptool npdmtool nxlink",
    "build_deps": "zlib、liblz4>=1.7.1；mingw 宿主 NET_LIBS=-lws2_32",
    "readme_claims": "README.md 为 0 字节（无声称）；nxlink 用法见 src/nxlink.c showHelp: Usage: nxlink [options] nrofile，选项 -h/-a/-r/-p/--args/-s，默认 retries=10",
    "readme_claim_url": "https://raw.githubusercontent.com/switchbrew/switch-tools/master/src/nxlink.c",
    "risks": [
      "Switch 上 pacman 包 switch-tools 版本未知，需 pacman -Q 核对",
      "nxlink 只做网络传输，需 hbmenu/Atmosphere 测试环境且 PC 与 Switch 同网段",
      "真机传输未实测"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "switch-tools 的 PKGBUILD 不在 pacman-packages 公开仓库（仅被 switch-cmake depends 引用）"
    ],
    "source_urls": [
      "https://github.com/switchbrew/switch-tools",
      "https://api.github.com/repos/switchbrew/switch-tools",
      "https://raw.githubusercontent.com/switchbrew/switch-tools/master/src/nxlink.c",
      "https://raw.githubusercontent.com/switchbrew/switch-tools/master/Makefile.am",
      "https://raw.githubusercontent.com/switchbrew/switch-tools/master/configure.ac",
      "https://raw.githubusercontent.com/switchbrew/switch-tools/master/COPYING",
      "https://raw.githubusercontent.com/devkitPro/docker/master/devkita64/Dockerfile"
    ],
    "audited_at": "2026-10-29"
  }
]
```
<!-- AUDIT-JSON-END -->
