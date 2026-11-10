# 集群 D 复核（v0.4）：NSP 打包链、测试后端与 prod.keys 合规（只读）

- 审计日期: 2026-10-29
- 审计员: audit-package（GalNX 团队审计员）
- 覆盖: 12 个条目（7 个 v0.3 核心对象的复核 + 5 个新增测试后端/生态对象）
- 方法: ① GitHub REST API（经 `cred_use` 的 GH_TOKEN，`/repos`、`/commits?per_page=1`、`/tags?per_page=100`、`/releases`、`/branches`、`/search/repositories`，2026-10-29 实测抓取）；② `raw.githubusercontent.com` 原文经本地代理 `http://127.0.0.1:7897` 用 curl 抓取（缓存于 `Workspace/GalNX/.cache/packaging-testing/refresh-20261029/`）；③ 本机文件仅做只读元数据核验（`sha256sum`/Python 读取 key 名，不输出 key 值）；④ 复用 v0.3 审计（`Workspace/GalNX/docs/audit/03-packaging-testing.md`）的原文证据并逐条重抓版本数字。本文件不提交 git，由 Lead 统一提交。
- 范围声明: 本轮不构建、不打包、不安装、不下载 release 二进制、不执行任何 NSP 生成；所有「真机可用」类结论均为 README/发布说明声称，未在本轮实测。

## 1. 总览表

| 条目 | 用途 | 精确版本（tag / commit） | 许可证(SPDX) | 健康（archive / last push / ★ / issues） | 结论 |
| --- | --- | --- | --- | --- | --- |
| rlaphoenix/NTON | PC 端 NRO→NSP forwarder 生成器（GUI/CLI） | `v3.0.1 = c5d543a91b7cd1df880f98c9ab831be9a40d024f`（2026-09-15） | GPL-3.0（LICENSE） | 否 / 2026-10-24 / 245★ / 8 | 与 v0.3 一致，无新版本；forwarder **仅作对照路线** |
| rlaphoenix/hacBrewPack | NSP/NCA 打包工具（NTON/Carafe 的打包后端） | `v3.05 = 745b16ecfc9ce055743067d200572204cb2aac6c`（代码 2019-10-13；镜像创建 2026-09-15） | GPL-2.0（LICENSE + LICENSES/） | 否 / 2026-09-15 / 2★ / 0 | **无变化**；无官方 release，需取二进制或自编译；GPL-2.0 隔离 |
| jakcron/nstool | NSP/XCI/NCA 等信息读取、提取与校验 | `v1.9.2 = e89ea84bd70c11b67ebec9153fb4a446f18a9d3d`（2024-10-14）；默认分支 HEAD `cfb826ca…` | MIT（LICENSE） | 否 / 2024-10-14 / 559★ / 16 | **产物校验第一步**；`-y` 校验不需 keys |
| TooTallNate/switch-nsp-forwarder | forwarder ROM 模板/入口实现（NTON 的 `rom/` 来源） | `0.0.8 = 61edd504e57c6007f23a3a242b386ac0372c0cee`（2026-05-03） | MIT（仅 package.json；**无 LICENSE 文件**，`/license` 404） | 否 / 2026-06-16 / 142★ / 14 | 与 v0.3 一致；仅作 forwarder 参考，不进入主路线 |
| carafe-nx/carafe | PC 工作台：Windows 游戏目录+Autorun 运行时 → 自包含 NSP | `v0.4.0 = 9b69701b8ae885126b09cf2ccdddef1eccee9732`（2026-10-25） | GPL-3.0（README：GPL-3.0-or-later；LICENSE） | 否 / 2026-10-29（非 main 分支）/ 255★ / 9 | 架构参考价值最高；**GPL-3.0 只做参考/子进程隔离** |
| autorunhq/autorun | Switch 上的 Windows PC 游戏兼容运行时（Wine fork） | `test-build-4 = 9b7170505f9084fee0ffe1a237b08557a6ab2868`（2026-09-23/24） | NOASSERTION（LICENSE 为 Wine LGPL-2.1+ 文本，另有 COPYING.LIB/NOTICES） | 否 / 2026-10-16 / 525★ / 62 | README 自称 experimental；**仅参考**，不分发 |
| autorunhq/autorun-horizon-dlls | Autorun 运行时所需的 Windows DLL 集合仓库 | `dlls = 4ab914bb4f7ffd35753934c02ecde05eed23a50f`（2026-09-28） | 无根 LICENSE（`/license` 404）；NOTICE.md 逐组件 | 否 / 2026-10-16 / 8★ / 0 | 与 v0.3 一致；许可为逐组件，**不可整体再分发** |
| switchbrew/nx-hbmenu | Switch Homebrew Menu（真机 NRO 启动入口） | `v3.6.1 = fd26270a4e4b6994886a57b0738d98229ab4094e`（2025-11-15） | ISC（LICENSE） | 否 / 2025-11-16 / 1406★ / 18 | 新增；真机测试栈必备，release zip 1,249,201 B |
| switchbrew/nx-hbloader | hbmenu 的加载器（hbl.nsp） | `v2.4.5 = 82b95122c5ae8dc059bf23893ba7623c72c86773`（2025-11-15） | ISC（LICENSE） | 否 / 2025-11-15 / 417★ / 3 | 新增；release `hbl.nsp` 40,946 B |
| rashevskyv/dbi | Switch 端 NSP 安装器 + MTP/USB 后端 | `912ru = e5ba732459c12b5777034678584f35e773c84c61`（2026-09-18，release tag；main HEAD `22090afc…` 2026-10-09） | **无**（仓库无 LICENSE，`/license` 404；README 未声明） | 否 / 2026-10-09 / 2986★ / 73 | 新增；**只作本机安装工具，不分发**（闭源二进制） |
| fortheusers/hb-appstore | Homebrew App Store（可选应用商店） | `v2.3.2 = cd74a989b9c6d5a1fe0eb621b91e331f8526f710`（2023-03-23；main HEAD `61d7ccb…` 2026-10-18） | GPL-3.0（LICENSE） | 否 / 2026-10-18 / 1468★ / 27 | 新增；release 停更于 2023，仅作可选工具，非 M3 依赖 |
| citron-neo/emulator（Citron Neo） | 第二测试后端（Switch 模拟器） | 最新 tag `2026-04-27 = 0076ee8fcaab0346de59a357a80700541decbaeb`；main HEAD `c3aa70f81e15ea97ee85b6a9a71cbf75d370851e`（2026-10-25） | GPL-3.0（README：GPL-3.0-or-later；LICENSE） | 否 / 2026-10-25 / 597★ / 93 | 新增登记；实测由另一任务完成（本文件不复测） |

## 2. 与 v0.3 记录的差异表

| 对象 | v0.3 记录（`03-packaging-testing.md`，2026-10-29 首轮） | 本轮 v0.4 复核（2026-10-29） | 差异 |
| --- | --- | --- | --- |
| rlaphoenix/NTON | v3.0.1 = c5d543a9…；pushed 2026-10-24；245★/8 | v3.0.1 = c5d543a9…（同）；pushed 2026-10-24；245★/8；release v3.0.1 仍为 latest | **无变化**（pushed_at 2026-10-24 来自 dependabot 分支，main 仍 c5d543a9） |
| rlaphoenix/hacBrewPack | v3.05 = 745b16ec…；2★/0；无 release | 同；pushed 2026-09-15；`/releases/latest` 仍 404 | **无变化** |
| jakcron/nstool | v1.9.2 = e89ea84b…；558★/16 | v1.9.2 = e89ea84b…（同）；559★/16；HEAD `cfb826ca…` | 版本无变化（★ +1） |
| TooTallNate/switch-nsp-forwarder | 0.0.8 = 61edd50…；142★/14；无 LICENSE | 同；pushed 2026-06-16；`/license` 仍 404 | **无变化**（许可证缺口仍在） |
| carafe-nx/carafe | v0.4.0 = 9b69701b…；pushed 2026-10-28；253★/9 | v0.4.0 = 9b69701b…（同）；pushed 2026-10-29T03:58:10Z；255★/9；main HEAD 仍 3334ebc | 版本无变化；新 push 来自 `optimization`/`dependabot/*` 分支，main 未动 |
| autorunhq/autorun | test-build-4 = 9b717050…；pushed 2026-10-16；525★/62 | 同；VERSION 仍 `Wine version 11.18`；3 个 tag 无新增 | **无变化** |
| autorunhq/autorun-horizon-dlls | dlls = 4ab914bb…；pushed 2026-10-16；8★/0 | 同；release `dlls` 2026-09-28 仍为 latest（zip 203,013,347 B / tar.zst 88,439,006 B） | **无变化** |
| switchbrew/switch-tools（nxlink） | v1.13.1 = 22756068…；ISC；181★/2 | v1.13.1 = 22756068…（同）；180★/2；pushed 2024-10-23 | 版本无变化（★ −1） |
| 测试后端 | v0.3 未单列 | 新增 nx-hbmenu v3.6.1、nx-hbloader v2.4.5、DBI 912ru、hb-appstore v2.3.2、Citron Neo tag 2026-04-27 | **新增 5 条** |
| Ryujinx | 网页侧 not-verified（git.ryujinx.app TLS 不可达、gitlab.hugofnm.fr 匿名需登录、mirror DMCA 451） | 本轮未重复抓取；**本机证据由 Lead 提供**：exe ProductVersion=1.3.265+4e81a4c 与源码 zip Comment=4e81a4c2f4fee6f31e28fbb129759ec2369da6eb 一致 | 维持 not-verified（网页侧）；本机版本固定依据见 §8 |

> 结论：本轮 7 个核心对象**没有出现新版本**，v0.3 的版本锁定表仍然有效；变化仅来自活跃度/星标等弱信号与新增的测试后端生态。

## 3. 条目详情

### 3.1 rlaphoenix/NTON（forwarder 生成器，仅作对照）

- URL: <https://github.com/rlaphoenix/NTON>；默认分支 `master`；HEAD `c5d543a91b7cd1df880f98c9ab831be9a40d024f`（2026-09-15，提交信息 "Bump to v3.0.1, update changelog"）；pushed_at 2026-10-24T00:04:29Z（main 之外分支的推送）。
- 最近 tag: `v3.0.1` = 上述 HEAD 的 commit（annotated tag 对象 `9587422b41e2ff22aec7fb0071a7d68249230a9c`）；release `v3.0.1` 发布于 2026-09-15T07:08:47Z，资产 `NTON-v3.0.1-portable.exe`（61,316,886 B）、`NTON-v3.0.1-setup.exe`（42,366,778 B）。
- 许可证: `GPL-3.0`（SPDX GPL-3.0-only，`pyproject.toml` 的 `license = "GPL-3.0-only"`；LICENSE 为 GPLv3 全文）。README §Licensing 明确列出随附第三方：hacBrewPack（The-4n，GPL-2.0，打包 NSP）、nstool（MIT，NRO 提取/校验）、hptnacp（hacPack，GPL-2.0，创建 NACP）、switch-nsp-forwarder 的 rom（MIT，启动 NRO），并写明 "No changes were made to any of the aforementioned software and copies of their licenses can be found next to their binaries within the bin folder."
- 健康: archived=false；last push 2026-10-24；245★；8 open issues。
- 构建系统 / 关键依赖: Python >=3.10 + hatchling + uv；`dependencies = click~=8.5.0, requests~=2.34.2, jsonpickle~=4.1.2, coloredlogs~=15.0.1, beautifulsoup4~=4.15.0, lxml~=6.1.3, pillow~=12.3.0`；GUI `PySide6-Essentials~=6.11.2`；打包 `pyinstaller~=6.22.3` + Inno Setup；CI `windows-latest`，Python 3.10–3.14 矩阵，用 `uv sync`，测试时从 `secrets.PROD_KEYS` 写 prod.keys 并构建 `sdl-hello.nro` 的 basic NSP forwarder（仅 CI，不入库）。CD：push tag `v*` → PyInstaller + Inno Setup + PyPI 发布。
- README 声称（原文要点，**均为项目方声称**）: 「NTON is a PC utility that let's you build an NSP application that launches right into an NRO file. Firmware 12.0.0 and newer is supported.」；Features：Title ID 冲突检查、从 NRO 自动提取标题信息与图标、约 1MB 安装体积、GUI+CLI；keys 需 `prod.keys`（用 Lockpick_RCM 从**自有主机**获取），可放 `C:\Users\<User>\.switch\prod.keys`、cwd 或安装目录；TitleID 默认随机分配，可用 `--id` 覆盖。
- README 风险原文（必须保留）: 「Installing these kinds of NSP files (NRO to NSP forwarders) can result in a console ban. This applies not just to this software but to all forms of NRO to NSP forwarder generators, including homebrew and web-app versions.」；Troubleshooting：「Please note that using Forwarders others have created has a good chance of not working on your system. The location of the NRO on their system may differ... hence the NSP won't be able to load the homebrew.」；「As the NSP forwarder's signature is not valid as we do not possess Nintendo's private signing keys, you cannot boot any NSP forwarder with CFW alone. Nintendo has DMCA'd the options that allow you to run these kinds of NSP files due to it allowing piracy.」
- 未验证 / 风险: 未在本机运行；未验证其打包二进制在 FW 12–21 的实际行为；forwarder **非自包含**（NRO 路径在生成时硬编码，换 SD 布局即失效）；安装有封禁与 DMCA 风险；需用户自备 prod.keys，不能入库/分发。
- 来源 URLs: <https://api.github.com/repos/rlaphoenix/NTON>、<https://api.github.com/repos/rlaphoenix/NTON/releases/latest>、<https://raw.githubusercontent.com/rlaphoenix/NTON/master/README.md>、<https://raw.githubusercontent.com/rlaphoenix/NTON/master/pyproject.toml>、<https://github.com/rlaphoenix/NTON>

### 3.2 rlaphoenix/hacBrewPack（NSP/NCA 打包后端）

- URL: <https://github.com/rlaphoenix/hacBrewPack>（描述 "Make NCAs/NSPs from Nintendo Switch homebrews (Mirror of now deleted The-4n/hacBrewPack)"）；默认分支 `master`；HEAD `745b16ecfc9ce055743067d200572204cb2aac6c`（2019-10-13，提交信息 "Updated sample hbmenu loader"）；pushed_at 2026-09-15T06:38:33Z（镜像创建时间 2026-09-15）。
- 最近 tag: `v3.05` = HEAD 同一 commit（轻量 tag，代码实际停在 2019-10-13）；**无 GitHub release**（`/releases/latest` 404）。
- 许可证: `GPL-2.0`（LICENSE 为 GPLv2 全文；`LICENSES/` 另含 `hactool.LICENSE`、`switch-tools.LICENSE`）；README「This software is licensed under the terms of the GNU General Public License, version 2.」
- 健康: archived=false；2★；0 open issues。
- 构建系统 / 关键依赖: C + Makefile；先构建随附 `mbedtls/`，`gcc -O2 -Wall -Wextra -pedantic -std=gnu11 -fPIC`，链接 `-lmbedtls -lmbedx509 -lmbedcrypto`；无其它外部依赖。**没有官方预编译二进制**。
- README 声称（构建契约，原文要点）: 输入需要 `build/exefs/main`、`build/exefs/main.npdm`、`[TARGET].nacp`（改名为 control/control.nacp 放 control/）；icon 必须 `icon_{Language}.dat`（实际是改名的 JPEG，**必须 256×256**，EXIF 可能导致图标占位或安装卡住）；`logo/` 需 `NintendoLogo.png`+`StartupMovie.gif`（官方资源无许可，可 `--nologo`）；TitleID 必须小写且落在 `0x0100000000000000 - 0x0fffffffffffffff`（建议不超过 `0x01ffffffffffffff`），Makefile 与 npdm.json 必须一致；keys 默认找 `keys.dat`，否则回退 `keys.txt`/`keys.ini`/`prod.keys`/`~/.switch/prod.keys`，可用 `-k/--keyset`；必需 key 为 `header_key` 与 `key_area_key_application_xx`。CLI 关键选项：`--nspdir/--ncadir/--exefsdir/--romfsdir/--titleid/--titlename(≤512B)/--titlepublisher(≤256B)/--keygeneration/--keyareakey/--sdkversion(默认 000C1100)/--plaintext/--nosignncasig2/--nologo`。「hacBrewPack doesn't need any options to work.」
- 未验证 / 风险: 未在本机编译（本轮禁止构建）；Windows 预编译二进制只能来自 NTON portable 的 `bin/` 或第三方构建（**来源与哈希需记录，未实测**）；会**就地修改输入文件**（Carafe 文档记录 `npdm.c:18,118`、`nacp.c:16,88,119` 的覆盖行为 → 必须传副本）；RSA-PSS 随机盐导致构建**非确定性**（同一输入两次产物的 NCA header 0x100–0x1FF 不同）；Windows MAX_PATH 259 B 限制（Carafe 实测 258/259 通过、260/270 失败 "Failed to stat"）；GPL-2.0 → 不得并入 GalNX 源树，只能子进程隔离。
- 来源 URLs: <https://api.github.com/repos/rlaphoenix/hacBrewPack>、<https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/README.md>、<https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/Makefile>、<https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/CHANGELOG.txt>

### 3.3 jakcron/nstool（产物检查/校验）

- URL: <https://github.com/jakcron/nstool>；默认分支 `development-tip`；HEAD `cfb826ca6c165fbcd816fd7949df88ef3d72a948`（2024-10-14，"Update libtoolchain to v0.8.0 (fixes VS dup issue)"）。
- 最近 tag: `v1.9.2 = e89ea84bd70c11b67ebec9153fb4a446f18a9d3d`（2024-10-14）；release `v1.9.2` 发布于 2024-10-14T01:37:38Z，资产含 `nstool-v1.9.2-win_x64`（487,087 B）、`win_x86`（434,872 B）、Linux/macOS 包。
- 许可证: `MIT`（LICENSE，MIT 全文）。
- 健康: archived=false；pushed 2024-10-14；559★；16 open issues；（自 v1.9.2 起近两年无提交，进入维护停滞状态）。
- 构建系统 / 关键依赖: C++，Linux/macOS 用 `make deps`+make；Windows 用 `build/visualstudio/nstool.sln`（VS2015/2017/2019）；git submodules：`deps/libmbedtls`、`libfmt`、`libtoolchain`、`liblz4`、`libpietendo`（均 `github.com/jakcron/*`）。
- README 声称: 支持 PFS0/HFS0/RomFS/NCA/NSP/XCI/META/NACP/CNMT/CERT/TIK/NSO/NRO/INI1/KIP1；默认输出一般信息，`--showlayout`、`--showkeys`、`-v`；`-t/--type` 覆盖类型；`-y/--verify` 校验 NCA Header Sig0/Sig1、META、XCI、CERT/TIK（v1.6.0 起内置 Root/XCI/ACID/NCA Header 公钥，**校验不需要 keys**）；`-x` 提取（整个 FS/子目录/单文件/重命名）；`--basenca` 处理 patch NCA；`-d/--dev` 开发者模式。README：「NSTool doesn't embed any keys that are copyright protected」。
- 未验证 / 风险: 未执行校验样本；`development-tip` 分支非稳定分支 → 版本锁定必须用 tag `v1.9.2`；对最新固件/新 key generation 的 NCA 是否完全支持未验证（2024-10 后无更新）。
- 来源 URLs: <https://api.github.com/repos/jakcron/nstool>、<https://api.github.com/repos/jakcron/nstool/releases/latest>、<https://raw.githubusercontent.com/jakcron/nstool/development-tip/README.md>、<https://raw.githubusercontent.com/jakcron/nstool/development-tip/BUILDING.md>

### 3.4 TooTallNate/switch-nsp-forwarder（forwarder 模板/入口实现）

- URL: <https://github.com/TooTallNate/switch-nsp-forwarder>；默认分支 `main`；HEAD `845811585e0b0d8881745afd50eca25d203957fd`（2026-05-03，"Update dependencies to address security advisories..."）。
- 最近 tag: `0.0.8 = 61edd504e57c6007f23a3a242b386ac0372c0cee`（2026-05-03）；release 0.0.8 发布 2026-05-03T07:27:22Z，资产 `nsp-forwarder.nro`（11,585,582 B）、`nsp-forwarder.nsp`（9,123,544 B）。
- 许可证: **仓库无 LICENSE 文件**，`/license` 返回 404；`package.json` 声明 `"license": "MIT"`。→ SPDX 记为 MIT（仅 package.json 声明，法律文本缺失，属许可证缺口）。
- 健康: archived=false；pushed 2026-06-16；142★；14 open issues。
- 构建系统 / 关键依赖: JavaScript/TypeScript + nx.js；`esbuild` 构建、`nxjs-nro`/`nxjs-nsp` 打包；deps：`@nx.js/clkrst ^1.0.1`、`@nx.js/constants ^0.4.0`、`@nx.js/install-title ^0.0.3`、`@nx.js/ncm ^1.2.0`、`@tootallnate/nacp ^0.2.0`、`jimp 1.6.0`、`react ^18.3.1`、`react-router-dom ^6.30.2`、`react-tela ^1.0.1`；devDeps `@nx.js/nro|nsp|runtime 0.0.69`、`esbuild ^0.28.0`、`typescript ^5.8.3`；pnpm@10.33.2。
- README 声称: 仅一句「Generate and Install NSP to NRO forwarders on your Switch」+ Releases 链接（README 272 B）；CHANGELOG：0.0.8 重建 forwarder ROM 修复 NRO 退出后按键死循环；0.0.7 起 TitleID 由 NRO 路径与参数的 SHA-256 派生（与 sphaira 逻辑一致）。
- 与 NTON 的关系: NTON README §Licensing 明确其 `rom/`（forwarder ROM 模板）来自本仓库（MIT），NTON 分发其编译产物并在 `bin/` 旁附许可证；NTON 不修改该软件。→ **NTON 的 forwarder 入口实现即本仓库**，两者版本需一并记录。
- 未验证 / 风险: 未运行；无 LICENSE 文本 → 作为依赖/再分发时法律依据不足；仅适用于 forwarder 路线，不解决自包含 NSP。
- 来源 URLs: <https://api.github.com/repos/TooTallNate/switch-nsp-forwarder>、<https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/README.md>、<https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/package.json>、<https://github.com/TooTallNate/switch-nsp-forwarder/releases/tag/0.0.8>

### 3.5 carafe-nx/carafe（PC 工作台 → 自包含 NSP，架构参考）

- URL: <https://github.com/carafe-nx/carafe>；默认分支 `main`；HEAD `3334ebc66e9bb2f6c12364a7b0b9a7472381fc3e`（2026-10-25，"docs(roadmap): mark the v0.4.0 items done"）；pushed_at 2026-10-29T03:58:10Z（来自 `optimization`/dependabot 分支，main 未动）。
- 最近 tag: `v0.4.0 = 9b69701b8ae885126b09cf2ccdddef1eccee9732`（2026-10-25）；release v0.4.0 发布 2026-10-25T08:34:35Z，资产 `Carafe_0.4.0_x64-setup.exe` 228,142,873 B、`arm64-setup.exe` 227,864,387 B、`latest.json` 2,594 B、`SHA256SUMS.txt` 188 B。
- 许可证: 仓库 `GPL-3.0`（GitHub 元数据）；README 写 `GPL-3.0-or-later`；LICENSE 为 GPLv3 全文；`runtime/` 内 overlay/patches 标 LGPL-2.1-or-later、loader 标 ISC、`external/` 各自许可。
- 健康: archived=false；255★；9 open issues；CI `check.yml`（windows-latest、node 24、rust 1.99.0、`npm run check`、bindings diff）、`release.yml`（tag 必须 `^vX.Y.Z$`，push tag 触发 docker compose 构建 runtime/hacbrewpack + tauri NSIS 打包，**安装包未签名**）。
- 架构（README/`docs/architecture.md`/`CONTRIBUTING.md`/`runtime/Makefile` 取证）:
  - `app/`：Tauri 2（Rust core + React 19/TypeScript 前端）；`app/crates/carafe-core` 负责目录扫描、元数据生成、NSP 写出、路径长度预检（`path_limit.rs`）。
  - `runtime/`：基于 Autorun（Wine 11.18 + Box64/FEX + DXVK/Mesa）的 Switch 运行时 + loader（ISC）+ overlay/patches（LGPL-2.1+）+ Docker 构建；`runtime/Makefile` 默认 `TITLE_ID ?= 055d76078fd54000`、`ADDRESS_SPACE ?= 39`、`SAVE_SIZE 0x10000000`、`SAVE_JOURNAL_SIZE 0x4000000`；`check-image` 校验 `docker/Dockerfile` 与 `switch-dev.txt` 一致。
  - `external/hacbrewpack`：hacBrewPack **v3.05（745b16e）** + mbedTLS 2.6.1（bundled），Carafe 在其上打 0001 补丁修复 romfs 缓冲 bug（大 RomFS 27s vs 120s）并沿用其原地修改输入的特性（必须传副本）。
  - 任务编排与元数据（`docs/nsp.md`）：①读游戏目录（`carafe-folder` 列出 exe/位数/product/company/installers/steam_api.dll）②向导③生成 `main.npdm`（TitleID + 39/32bit address space）、`control.nacp`（名称/发行商/图标/存档大小）、`carafe/argv`、`carafe/title`、`carafe/icon.jpg`、`<exe>.keys.txt/.wine-nx.txt/.args.txt` ④预检（4×游戏大小 + runtime 空间、每路径 ≤259 B）⑤`.carafe/build/<Title ID>` 布局（loader 作 ExeFS main、boot splash 作 logo）⑥hacBrewPack 生成 Program/Control NCA，Carafe **自己写 NSP**（NCAs+carafe.json，先 `.nsp.part` 再改名）⑦DBI MTP 安装。
  - NSP 内容布局：ExeFS `main`+`main.npdm`；RomFS `switch/wine/{wine-nx-runtime.nro,prefix,DLLs,fonts,nls}` + `drive_c/Games/<folder>` + `carafe/`；Control NACP + 每语言 icon；Logo NintendoLogo.png/StartupMovie.gif；`carafe.json` 构建记录。
- README 声称: 把 Windows 游戏目录变成带独立图标/存档/加载屏的 Switch title；运行基于 Autorun；要求 Atmosphère+sigpatches、DBI、Win10/11 x64/ARM64；安装包未签名。
- 未验证 / 风险: 未运行 Carafe、未核对 228MB 安装包内容；其 license 与 Autorun 相同 → **GPL-3.0 传染风险**，只能文档/子进程参考；其 NSP 写出逻辑可借鉴但不可复制代码；全部真机测试（`docs/testing.md` 明确无 emulator loop），日志在 `sdmc:/switch/carafe/<TitleID>/`（保留最近 5 次）。
- 来源 URLs: <https://api.github.com/repos/carafe-nx/carafe>、<https://api.github.com/repos/carafe-nx/carafe/releases/latest>、<https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/nsp.md>、<https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/testing.md>、<https://raw.githubusercontent.com/carafe-nx/carafe/main/runtime/Makefile>、<https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/architecture.md>

### 3.6 autorunhq/autorun（Windows 兼容运行时，仅参考）

- URL: <https://github.com/autorunhq/autorun>；默认分支 `main`；HEAD `1ac9b6cf37b90f2d5783dd7ef389bebbe1c68877`（2026-10-16，"horizon-dlls: README with Autorun's header and what the files are, and aren't."）。
- 最近 tag/release: `test-build-4 = 9b7170505f9084fee0ffe1a237b08557a6ab2868`（commit 2026-09-23T23:29:36Z；release 2026-09-24T10:59:45Z，资产 `autorun-test-build-4.zip` 64,978,068 B）；此前 test-build-3（`f86a318e…`，2026-09-19，61,408,112 B）、test-build-2（`1bc4e451…`，2026-09-15，81,519,917 B + `sphaira-32bit-forwaders.nro` 5,059,009 B）。
- 许可证: GitHub `NOASSERTION/Other`；仓库 `LICENSE` 为 824 B 的 **Wine LGPL-2.1-or-later** 文本，另附 `COPYING.LIB`、`NOTICES.md`（67,272 B）、`AUTHORS`。→ 作为 Wine 派生作品，整体义务按 LGPL-2.1+ 及 `NOTICES.md` 逐组件执行；第三方组件许可（README Credits）含 Wine LGPL-2.1+、FEX MIT、Box64 MIT、DXVK zlib/libpng、VKD3D-Proton LGPL-2.1+、Mesa/mesa-switch MIT(mostly)、LSFG-VK GPL-3.0+、libusbhsfs ISC、Atmosphère/Horizon-OC GPL-2.0、libnx/devkitPro ISC、SDL2/FreeType/HarfBuzz/libpng/zlib 等。
- 健康: archived=false；pushed 2026-10-16；525★；62 open issues。
- 技术栈（README 与构建脚本原文）:
  - `VERSION` 文件：`Wine version 11.18`（运行时为 Wine 11.18 分支）。
  - CPU 翻译：x86/x64 用 **FEX**（`build-amd64-components.sh` 中 `--enable-archs=aarch64,arm64ec,i386`、`--enable-winebox64=aarch64 --enable-winebox64ec=arm64ec`）；32 位用 **Box64** 作为第二翻译器（`WINE_NX_BOX64_DYNAREC=ON`，`bootstrap-box64-core.sh` 固定 revision `2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a`，`git fetch --depth=1`）。
  - 图形：Mesa 26 `mesa-switch`；DXVK（D3D8–11）、VKD3D-Proton（D3D12）；可选 LSFG-VK 帧生成（需自备 Lossless Scaling）。
  - Windows DLL：不在此仓库，来自 `horizon-dlls` 子模块；由 `runtime-interfaces.json` manifest 匹配后才启动。
  - x86 runtime（nx-wow64-dynarec-*）走 WoW64+Box64；AMD64（nx-amd64-fex-*）走 FEX；构建用 `switch-dev` 容器 + llvm-mingw-20260505-ucrt 工具链。
  - 安装：解压 release zip 到 SD 根（全部进 `switch/wine`）；需 CFW（Atmosphère）+ microSD + 约 200MB DLL + PC 游戏目录；Quick setup 放 HOME 菜单并安装 boot changes（Mesosphere 低内存地址 + stock loader 或 Horizon-OC）。
- README 声称（原文要点）: 「**Autorun is experimental.** Some games run well, many start and then stop on something that isn't done yet. Every run writes a log that says where. A game compatibility list is coming.」；「Not a piracy or circumvention tool」；不支持盗版/破解/第三方整合包；USB 存储映射 D:–H:。
- 未验证 / 风险: 未跑任何游戏；「experimental」明确；性能/兼容性无量化证据；LGPL/GPL 组件多，若随 GalNX 分发运行时须提供源码与许可（**GalNX 决定只参考、不分发**）；README 的「真机可运行」为项目方声明。
- 来源 URLs: <https://api.github.com/repos/autorunhq/autorun>、<https://raw.githubusercontent.com/autorunhq/autorun/main/README.md>、<https://raw.githubusercontent.com/autorunhq/autorun/main/VERSION>、<https://raw.githubusercontent.com/autorunhq/autorun/main/build-x86.sh>、<https://raw.githubusercontent.com/autorunhq/autorun/main/build-amd64-components.sh>、<https://github.com/autorunhq/autorun/releases/tag/test-build-4>

### 3.7 autorunhq/autorun-horizon-dlls（运行时 DLL 集合）

- URL: <https://github.com/autorunhq/autorun-horizon-dlls>；默认分支 `main`；HEAD `67e2303dee9191b7ce4e2d1ccb47957d15c8a98b`（2026-10-16，"README: Autorun's header, and not a piracy or circumvention tool"）。
- 最近 tag/release: `dlls = 4ab914bb4f7ffd35753934c02ecde05eed23a50f`（commit 2026-09-28T11:43:20Z；release `dlls` 发布 2026-09-28T11:53:27Z，资产 `horizon-dlls.tar.zst` 88,439,006 B、`horizon-dlls.zip` 203,013,347 B）。
- 许可证: **无根 LICENSE**（`/license` 404）；`NOTICE.md`（65,295 B）逐组件列许可（Capstone BSD-3-Clause、FFmpeg LGPL-2.1+、FluidSynth LGPL-2.1+、ICU Unicode-DFS-2016 AND ICU、Little CMS MIT、musl MIT、Wine LGPL-2.1+、vkd3d LGPL-2.1+、zlib、DXVK-zlib、DXBC/DXIL-SPIRV 等）；`LICENSES/` 目录含逐组件许可全文。→ 不能整体再分发，只能逐组件遵循。
- 获取方式: 由 Autorun 自动下载并增量更新（README：「Every module a Windows game expects to find in system32 (ARM64X) and syswow64 (i386), built from Autorun's Wine, with FEX's CPU modules and the bundled DXVK and VKD3D-Proton」；「Autorun downloads horizon-dlls.tar.zst itself for a card that has few of them」）；离线可手动解压 release zip 到 `switch/`；每文件带 version/size/SHA-256，只取变化。
- 是否随发行分发: **是**——Autorun 发行包不含 DLL，运行时按 manifest 从本仓库 release 下载；GalNX 若使用 Autorun 运行时则需要这一下载路径（联网/离线包），但 GalNX 不分发 Autorun（参考路线）。
- 健康: archived=false；pushed 2026-10-16；8★；0 open issues。
- 未验证 / 风险: 未下载 203MB 资产、未校验 SHA-256；逐组件许可未做法务级复核；NOTICE 引用的构建 commit（`97422507a2bc8100c6ba32a13828109a340e9131`）早于当前 HEAD，版本对应关系未逐文件核验。
- 来源 URLs: <https://api.github.com/repos/autorunhq/autorun-horizon-dlls>、<https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/README.md>、<https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/NOTICE.md>、<https://github.com/autorunhq/autorun-horizon-dlls/releases/tag/dlls>
### 3.8 switchbrew/nx-hbmenu（Homebrew Menu）

- URL: <https://github.com/switchbrew/nx-hbmenu>；默认分支 `master`；HEAD `089fdf85ff82ad7077527092f8615f2e57ffc985`（2025-11-16）；pushed_at 2025-11-16T19:55:33Z。
- 最近 tag/release: `v3.6.1 = fd26270a4e4b6994886a57b0738d98229ab4094e`（2025-11-15）；release `v3.6.1` 发布于 2025-11-15T16:53:18Z，资产 `nx-hbmenu_v3.6.1.zip`（1,249,201 B）。
- 许可证: `ISC`（LICENSE）；README Credits 注明部分代码源于 3DS `new-hbmenu`，并使用 `libjpeg-turbo`（图标）与 `c11threads` 第三方组件。
- 健康: archived=false；1406★；18 open issues。
- 构建系统 / 关键依赖: `make nx`（Switch）/ `make pc`；Switch 需 devkitPro pacman 包 `switch-dev`、`switch-freetype`、`switch-libconfig`、`switch-libjpeg-turbo`、`switch-physfs`；PC 需 libfreetype/libconfig/libjpeg-turbo/libphysfs/sdl2；构建需 `zip`；C11 Threads。
- README 声称: 「See Homebrew_Applications for SD layout and applications, etc. See Switchbrew for hbmenu docs.」；最新版从 releases 下载。用途：真机上浏览/启动 SD 卡上的 NRO（应用模式），是 NSP 内 loader 的常规启动目标。
- 未验证 / 风险: 未在真机运行；SD 布局/应用模式细节依赖 Switchbrew wiki（本轮未抓取该 wiki）；版本必须与 Atmosphère/FW 组合记录。
- 来源 URLs: <https://api.github.com/repos/switchbrew/nx-hbmenu>、<https://api.github.com/repos/switchbrew/nx-hbmenu/releases/latest>、<https://raw.githubusercontent.com/switchbrew/nx-hbmenu/master/README.md>

### 3.9 switchbrew/nx-hbloader（hbmenu 加载器）

- URL: <https://github.com/switchbrew/nx-hbloader>；默认分支 `master`；HEAD `82b95122c5ae8dc059bf23893ba7623c72c86773`（2025-11-15）。
- 最近 tag/release: `v2.4.5 = 82b95122c5ae8dc059bf23893ba7623c72c86773`（2025-11-15）；release 资产 `hbl.nsp`（40,946 B）。
- 许可证: `ISC`（LICENSE）。
- 健康: archived=false；pushed 2025-11-15；417★；3 open issues。
- 构建系统 / 关键依赖: C + Makefile（仓库仅 60 KB，源码/构建极简）；**仓库无 README**（`/contents/README.md` 404），用途依据 switchbrew 生态与 hbl.nsp 发布物。
- README 声称: 无（null）。
- 未验证 / 风险: 未验证 `hbl.nsp` 与目标 FW/Atmosphère 的组合；本轮无 README 可引用，只能引用 release 资产本身。
- 来源 URLs: <https://api.github.com/repos/switchbrew/nx-hbloader>、<https://api.github.com/repos/switchbrew/nx-hbloader/releases/latest>

### 3.10 rashevskyv/dbi（Switch 安装器 + MTP/USB）

- URL: <https://github.com/rashevskyv/dbi>；默认分支 `main`；HEAD `22090afc64cc7b5d645a99bf3d4d8625a67b766e`（2026-10-09，提交 "Release 921"）。仓库描述：「Author is duckbill」。
- 最近 tag/release: `912ru = e5ba732459c12b5777034678584f35e773c84c61`（commit 2026-09-18T07:12:57Z，信息 "Updated to 912"；release 发布 2026-09-18T07:14:24Z）。资产：`DBI.nro` 16,657,965 B、`dbibackend-qt.exe` 51,350,472 B、`dbibackend.exe` 10,609,140 B、`dbi.config` 7,705 B、`latest.zip` 7,820,469 B、`dbibackend.tar.xz` 2,336 B。
- 许可证: **无**——仓库只有 `README.md`/`README_RU.md`/`dbi.config`/`dbi.locations`/`dbibackend*`，无 LICENSE 文件，`/license` 404，GitHub 元数据 license=null，README 未声明许可；`DBI.nro` 为闭源发行二进制。→ 仅可作为本机工具，**不得随 GalNX 分发/打包**。
- 健康: archived=false；pushed 2026-10-09；2986★；73 open issues。
- 构建系统 / 关键依赖: 无源码构建（发布预编译 `DBI.nro` + Python 版 `dbibackend` 脚本 + Windows `dbibackend.exe`/`dbibackend-qt.exe`）。
- MTP 安装方式（README 原文要点）: 「Run MTP responder activates the built-in MTP server in DBI for exchanging data with a PC or an Android device via USB-C OTG」；连接 USB 后在 PC 侧出现 MTP 盘：`SD Card`、`NAND User`、`NAND System`、`Installed games`、**`SD install`**、**`NAND install`**、`Saves`、`Album`、`Gamecard`；「**SD install** - Drop or copy your NSP/NSZ/XCI or XCZ files in this folder. When the transfer is complete the game will be installed on the SD card of your console.」（NAND install 同理装到内置存储）。备选 USB 安装：「Install title from DBIbackend」用 `dbibackend.exe` 从 PC 发送文件（Windows 需装 libusbK v3.1.0.0 驱动，经 Zadig 安装）。
- 未验证 / 风险: 未真机测试 MTP 安装；无许可证 → 法律状态不明；本仓库为第三方分发（作者 duckbill 的闭源工具），上游发布渠道不可验证（可能随时消失）；版本 tag 命名（`912ru`）与 UI 内 `dbi: XXX` 版本号对应关系未逐字核对。
- 来源 URLs: <https://api.github.com/repos/rashevskyv/dbi>、<https://api.github.com/repos/rashevskyv/dbi/releases/tags/912ru>、<https://raw.githubusercontent.com/rashevskyv/dbi/main/README.md>

### 3.11 fortheusers/hb-appstore（可选 Homebrew 商店）

- URL: <https://github.com/fortheusers/hb-appstore>；默认分支 `main`；HEAD `61d7ccb679b2d2ad97a604e10f70f553a757fb36`（2026-10-18）。
- 最近 tag/release: `v2.3.2 = cd74a989b9c6d5a1fe0eb621b91e331f8526f710`（2023-03-23）；release `v2.3.2` 发布于 2023-03-23T15:54:19Z，资产含 `appstore.nro`（11,104,808 B）、`switch-extracttosd.zip`（7,784,395 B）。
- 许可证: `GPL-3.0`（LICENSE 为 GPLv3 全文；README「This software is licensed under the GPLv3.」）。
- 健康: archived=false；pushed 2026-10-18；1468★；27 open issues；**release 停更于 2023-03**（源码仍在维护，PC 构建走 nightly.link）。
- 构建系统 / 关键依赖: C++/SDL2 + Chesto；`libget` 包管理器；Switch 安装到 `sd:/switch/appstore/`，从 hbmenu 启动；PC 客户端由 GitHub Actions 构建（README 指向 nightly.link）。
- README 声称: GUI 访问开源 homebrew 在线仓库；Switch 需要 Homebrew Menu；可用网页端 apps.fortheusers.org。
- 未验证 / 风险: 未安装；非 M3 必需依赖（可选工具）；在线仓库内容不受 GalNX 控制。
- 来源 URLs: <https://api.github.com/repos/fortheusers/hb-appstore>、<https://api.github.com/repos/fortheusers/hb-appstore/releases/latest>、<https://raw.githubusercontent.com/fortheusers/hb-appstore/main/README.md>

### 3.12 citron-neo/emulator（Citron Neo，第二测试后端，登记）

- URL: <https://github.com/citron-neo/emulator>；默认分支 `main`；HEAD `c3aa70f81e15ea97ee85b6a9a71cbf75d370851e`（2026-10-25，"Merge pull request #386 from HopeSuffers/fix/macos-thread-priority"）。
- 最近 tag/release: `2026-04-27 = 0076ee8fcaab0346de59a357a80700541decbaeb`（tag 为日期命名；release 发布 2026-04-27T13:57:23Z）；资产为 nightly 构建（如 `Citron-windows-nightly-0237a9b88-x64-clangtron.zip` 53,286,760 B、`-msvc.zip` 40,497,628 B、Linux AppImage 约 96–97 MB、macOS dmg 73,751,331 B、Android APK 22,157,733 B）。
- 许可证: `GPL-3.0`（GitHub 元数据）；README「GPL-3.0-or-later. See LICENSE. Third-party components and their licences are in LICENSES/.」。
- 健康: archived=false；created 2026-03-14；pushed 2026-10-25；597★；93 open issues；描述 "The switch fell off https://citron-neo.org/"。
- 构建系统 / 关键依赖: C++/CMake；依赖由 CPM 在 configure 时拉取（README 明确不需先初始化 submodules）；Linux `./build-citron-linux.sh setup` 后 `use --pgo none --lto full`；Windows 用 clang-cl 或 llvm-mingw；Android 用 gradle。
- README 声称: Citron Neo 是延续 Citron 代码库的开源模拟器，支持 Windows/Linux/macOS/Android(arm64)。
- 未验证 / 风险: **本轮不复测**——Citron 的实测结果由另一任务（测试后端实测）提供，本文件只登记版本/许可证元数据；release 为 nightly 二进制，与 tag commit 的映射未逐资产核验（资产名内嵌 `0237a9b88`）；GPL-3.0 仅在本机测试使用，不分发。
- 来源 URLs: <https://api.github.com/repos/citron-neo/emulator>、<https://api.github.com/repos/citron-neo/emulator/releases/tags/2026-04-27>、<https://raw.githubusercontent.com/citron-neo/emulator/main/README.md>

## 4. 测试后端生态与真机安装路径（新增）

### 4.1 三个测试层级

| 层级 | 用途 | 工具（锁定版本） | 验证边界 |
| --- | --- | --- | --- |
| 产物层（PC，无真机） | 校验 NSP 结构/签名/元数据，不需要 keys | nstool `v1.9.2`（`e89ea84b`） | 只证明包结构与签名链符合工具预期，不证明可启动 |
| 真机层（CFW） | 安装 + HOME 启动 + 存档隔离 | nx-hbmenu v3.6.1、nx-hbloader v2.4.5、DBI 912、Atmosphère+sigpatches（版本由环境任务记录） | 真机验收唯一依据 |
| 模拟器层（PC） | 快速回归/日志采集 | Ryujinx 1.3.265+4e81a4c2（本机留档）、Citron Neo tag 2026-04-27（第二后端，另一任务实测） | 不能替代真机验收；Ryujinx 官方更新源不可达 |

### 4.2 真机安装与启动路径（本轮只登记、未执行）

1. SD 卡布局：hbmenu 与 homebrew NRO 按 Switchbrew 约定放 `sd:/switch/`（nx-hbmenu README 指向 Homebrew_Applications 文档）；hb-appstore（可选）解压到 `sd:/switch/appstore/`。
2. 启动 homebrew：Atmosphère 环境进入 hbmenu（application/applet 模式），选择 NRO 运行；`hbl.nsp`（nx-hbloader）为 hbmenu 的 NSP 加载形式（用于无 hbmenu 入口时的加载链）。
3. 安装到本机：DBI 的 MTP responder 打开后，PC 侧向 MTP 盘的 `SD install`/`NAND install` 目录复制 NSP，传输完成即安装（README 原文见 §3.10）；备选 DBIbackend USB 安装（需要 libusbK 驱动）。
4. 启动：HOME 菜单出现独立图标/名称，点击启动（前提：CFW + sigpatches；NSP 签名非 Nintendo 官方有效签名）。
5. 失败诊断：Carafe 的日志模式可借鉴——`sdmc:/switch/carafe/<TitleID>/`（`carafe-overlay.log`、`logs/autorun_runtime.log`，保留最近 5 次）；loader 错误码 `2347-01xx`（101 sm / 102 fs / 103 heap / 104 session / 105 thread / 106 receiving handle / 107 no handle / 108 unload .nro / 109 path 不在预期位置）。

### 4.3 工具获取方式与许可注意

- nstool：官方 release 提供 `win_x64` 二进制（487,087 B），MIT，可直接锁定。
- hacBrewPack：**无官方 release**；可行来源仅 ① NTON portable `bin/` 内随附的已编译二进制（NTON README 说明 "next to their binaries within the bin folder"，**本轮未下载核验**）② 自行编译（C + 随附 mbedtls；本轮禁止构建）。→ M3 需要先决定二进制来源并记录 SHA-256。
- nx-hbmenu / nx-hbloader：官方 release zip / `hbl.nsp`，ISC。
- DBI：官方 release `DBI.nro`，**无许可证**；仅本机使用，不进 GalNX 产物。
- hb-appstore：release 停更（v2.3.2，2023），可选，不列入 M3 依赖。
- Citron：nightly release 二进制，GPL-3.0；仅作第二测试后端。

## 5. prod.keys / title.keys 合规策略

### 5.1 本机 keys 来源与可用性核实（只记录元数据，不读取/不输出 key 值）

| 文件 | 路径 | 大小 | SHA-256（记录入 PROVENANCE 用） | 结构统计（仅 key 名） |
| --- | --- | --- | --- | --- |
| prod.keys | `E:\Othergames\Nintendo Switch\Ryujinx-canary\portable\system\prod.keys` | 12,007 B | `7bb3b6d2a2eedc83c9f244ee2ed2eaa4d59eb9ad95b66df575f7dfffa71a2a40` | 221 条 key 名；含 `header_key`；含 `key_area_key_application_00`–`key_area_key_application_15`（含 `_source` 变体）；含 `master_key_00`、`aes_kek_generation_source` |
| title.keys | `E:\Othergames\Nintendo Switch\Ryujinx-canary\portable\system\title.keys` | 11,492 B | `2b338398a2df5bad0e620da572cd3a5a3f6787d03b35109d73833e6370fc5f32` | 169 条 title key 条目（**打包不需要**，仅 Ryujinx 解密游戏内容时使用） |

- 来源：用户提供的 Ryujinx canary portable 安装目录自带 keyset（用户明确允许本机使用）；该目录同时含 `Profiles.json`（65,647 B），**不含**固件或游戏数据。
- 可用性判断（静态）：hacBrewPack 必需的两类 key（`header_key`、`key_area_key_application_xx`）均存在，且 application key 覆盖到 `_15` 代；按 v0.3 记录的机制，足以支撑 hacBrewPack 打包。**未实际打包验证**（本轮禁止构建），因此「keys 可用」只到「必需 key 名齐全」级别，未到「可产出可安装 NSP」级别。
- nstool `-y` 校验不需要 keys（内置公钥）；title.keys 与 NSP 打包无关。

### 5.2 GalNX key 规范（建议，写入 M3 前置）

1. **只读路径配置**：`GALNX_PROD_KEYS`（或配置文件 `keys.prod_keys_path`）指向用户本机 keyset；框架不复制、不改写、不缓存内容；启动时只检查文件存在 + 大小 + `sha256`。
2. **PROVENANCE 记录**：构建记录中只写 `path`（可脱敏为相对路径）、`size`、`sha256`、`mtime`、来源说明（「用户 Ryujinx 自带 keyset」）；**绝不写 key 内容**。
3. **禁止入库/入日志/进 CI**：`.gitignore` 覆盖 `*.keys`、`prod.keys`、`title.keys`、`*.nsp` 中间产物；日志脱敏规则拦截 32/64 hex 长串与已知 key 名；CI 只允许用 `secrets` 注入到临时目录并在 job 结束删除（NTON 的 CI 即用 `secrets.PROD_KEYS` 写临时 prod.keys，可借鉴但其产物不入库）。
4. **构建沙箱与清理**：hacBrewPack 子进程以最小环境变量启动（只传 keyset 路径），工作目录在临时目录，构建后删除临时 keyset 副本（若必须复制）、NCA 中间目录与日志中的敏感行；Windows 上用受限 ACL 的临时目录。
5. **失败提示**：keys 缺失/格式错误/不含必需 key 时给出可操作提示（「需 `header_key` 与 `key_area_key_application_xx`，请用自有主机提取并只放在本机路径」），不回显文件内容。
6. **许可/法律边界**：keyset 属于用户自有主机的派生数据，不得随 GalNX 或生成的 NSP 分发；文档中只描述提取方法与路径，不提供下载源、不内置 payload。

### 5.3 Lockpick_RCM 真机提取步骤（概要，本轮未执行、未下载）

> **重要**：Lockpick_RCM 的 GitHub 仓库 `shchmue/Lockpick_RCM` 当前返回 **451 Repository access blocked**，block.reason=`dmca`、created_at=2023-05-08、DMCA 记录 <https://github.com/github/dmca/blob/master/2023/05/2023-05-04-nintendo-4.md>；因此本审计**不提供下载链接**，也不下载 payload。以下为社区通行流程概要，**未在本轮实测**：

1. 主机需已具备 CFW 环境（Atmosphère；具体版本由环境任务记录），能通过 Hekate/payload 链启动自制 payload。
2. 将 Lockpick_RCM payload（`.bin`）放在 SD 的 `bootloader/payloads/`，从 Hekate 的 payloads 菜单启动（或在 CFW 中通过 hbmenu 启动其 NRO 版本）。
3. 在 Lockpick_RCM 中选择「Dump from SysNAND」，工具会把 keyset 写到 SD 卡 `/switch/prod.keys` 与 `/switch/title.keys`（具体文件名以工具版本为准）。
4. 把文件复制到 PC 的只读路径（如 `%USERPROFILE%\.switch\prod.keys`），记录 size/sha256，删除 SD 上的副本（或保留由用户决定）。
5. 仅限自有主机、仅本机使用；不得上传、不得随 NSP/框架分发；Nintendo 版权与 DMCA 风险由用户承担；GalNX 文档只写步骤，不内置工具。

### 5.4 哪些步骤必须 keys

| 步骤 | 必须 keys？ | 依据 |
| --- | --- | --- |
| hacBrewPack 生成 NCA/NSP | **是**：`header_key` + `key_area_key_application_xx` | hacBrewPack README §Keys（原文见 §3.2） |
| hacBrewPack `--plaintext` / `--nosignncasig2` | 仍需要 key 派生/签名材料（不确定是否可完全免 key；未验证） | README 选项存在，但未做免 key 实验 |
| nstool `-y` 校验 NSP/NCA | **否**（内置公钥） | nstool README：校验 NCA Header Sig0/Sig1、META、XCI、CERT/TIK；「NSTool doesn't embed any keys that are copyright protected」 |
| nstool 读取/提取内容 | 否（只读结构）；解密内容才需 keys | nstool README |
| 真机安装 NSP | 不需要 keys 文件，但需要 CFW + **sigpatches**（非官方签名被系统拒绝） | NTON README 原文（「signature is not valid ... cannot boot any NSP forwarder with CFW alone」） |
| forwarder 运行 NRO | 生成 forwarder 时需 keys（NTON 打包用 hacBrewPack）；运行时不需要 | NTON README |

## 6. NSP 自包含最小可行路径（M3 技术契约，未实测）

### 6.1 hacBrewPack 输入/输出布局（依据 README 原文）

```
work/
├── exefs/                  # --exefsdir，默认 ./exefs/
│   ├── main                # ExeFS 主程序（NRO→NSO 后的产物，或 loader NRO 的 exefs）
│   └── main.npdm           # NPDM（含 TitleID、address space 等）
├── control/                # --controldir，默认 ./control/
│   ├── control.nacp        # 由 [TARGET].nacp 改名；含名称/发行商/版本/图标索引
│   └── icon_AmericanEnglish.dat   # 256×256 JPEG（可多语言）
├── romfs/                  # --romfsdir，默认 ./romfs/（自包含包的游戏数据+运行时）
├── logo/                   # --logodir，可 --nologo；NintendoLogo.png + StartupMovie.gif（无许可，建议自备）
└── (keyset)                # keys.dat 或 -k 指定；回退 keys.txt/keys.ini/prod.keys/~/.switch/prod.keys
输出：<titleid>.nsp（--nspdir）、NCA（--ncadir/--keepncadir）、临时目录（--tempdir）
```

- TitleID：小写 `0x0100000000000000`–`0x0fffffffffffffff`，建议不超过 `0x01ffffffffffffff`；Makefile/npdm.json（以及 Carafe 场景下的 NACP）必须一致；hacBrewPack 的 `--titleid` 只改 ACI0 一处，Carafe 因此**不传 --titleid**、自己写三处元数据（`docs/nsp.md` 记录）。
- 签名：hacBrewPack 用随附/用户 key 生成 NCA header 签名（RSA-PSS，随机盐）→ **两次构建产物不同（非确定性）**；因此日志/验收要记录「输入哈希 + 工具版本 + 输出哈希」，不能靠 diff 判断。
- 已知坑：就地修改输入（必须传副本）；icon EXIF 可能导致占位/安装卡住；Windows 259 B 路径上限；Logo 资源无官方许可（用自有素材 + `--nologo` 或替换）。

### 6.2 GalNX 编排契约建议（子进程，GPL 隔离）

- 输入：`{exefs_dir, romfs_dir, control_dir, logo_dir?, title_id, title_name, publisher, version, keyset_path, sdk_version?, output_dir}`，全部由 GalNX 预检（TitleID 范围/冲突、路径长度 ≤259 B、控制文件完整性、keyset 含必需 key 名）。
- 子进程调用：`hacbrewpack.exe --exefsdir ... --romfsdir ... --controldir ... --nspdir ... --titlename ... --titlepublisher ... -k <keyset>`（不带 `--titleid`，若由 GalNX 统一写三处元数据；否则传 `--titleid` 并接受单点覆盖风险）。
- 输出捕获：解析 stdout/stderr + 退出码（hacBrewPack 无文档化退出码，需以「产物存在 + nstool 校验」为准）；记录 argv、工具 exe SHA-256、输入目录树哈希、keyset size/sha256（**不含内容**）、耗时、产物 SHA-256。
- 校验链：产物 → `nstool -y <nsp>`（返回非 0 或报告校验证书错误即失败）→ 可选 `nstool -x` 解包核对 ExeFS/RomFS 结构 → 真机安装（DBI MTP）→ HOME 启动 → 存档隔离/卸载重装（v0.3 已有验收清单）。
- 失败分类：`KEYS_MISSING`/`KEYS_INVALID`、`TITLEID_INVALID`、`INPUT_LAYOUT_INVALID`、`PATH_TOO_LONG`、`PACK_FAILED`、`VERIFY_FAILED`、`INSTALL_FAILED`（真机）、`BOOT_FAILED`（真机）。

### 6.3 真机安装前置（M3 阻塞项）

- 需 CFW（Atmosphère）+ **sigpatches**；NSP 签名非 Nintendo 私钥签名，系统默认拒装/拒启。
- 需真机与 DBI（MTP）或 DBIbackend；需记录主机 FW 版本、Atmosphère 版本、sigpatches 版本、hbmenu/hbloader 版本。
- 需用户提供游戏数据目录与（如适用）运行时文件；GalNX 不分发游戏数据/运行时。

## 7. 测试环境固定方案

| 后端 | 固定对象 | 固定方式 | 证据/日志 |
| --- | --- | --- | --- |
| Ryujinx（主测试后端） | `1.3.265+4e81a4c` | 本机留档 exe + 源码 zip（Lead 已核：exe ProductVersion=1.3.265+4e81a4c；zip Comment=`4e81a4c2f4fee6f31e28fbb129759ec2369da6eb`）；记录 exe/zip 的 SHA-256 与文件大小入 PROVENANCE | 网页侧 not-verified（官方更新源 git.ryujinx.app TLS 不可达、gitlab 镜像需登录、ryujinx-mirror DMCA 451）→ **不得依赖在线获取，必须本地留档**；日志/退出码由 Lead 的本机验证补充 |
| Citron Neo（第二后端） | tag `2026-04-27` = `0076ee8fcaab0346de59a357a80700541decbaeb`（或记录夜间构建资产名内嵌的 commit） | 记录 release 资产名 + SHA-256（本轮未下载）；实测结论引用另一任务 | 该后端仅做回归，不作为验收权威（模拟器不等同真机） |
| 真机 | FW + Atmosphère + sigpatches + hbmenu v3.6.1 + hbloader v2.4.5 + DBI 912 | 逐项版本记录到测试矩阵 | DBI MTP 安装 + HOME 启动 + 存档隔离；日志按 §4.2 的 Carafe 模式采集 |

采集建议（可执行契约）：包装器每次运行记录 `{tool, tool_version, tool_sha256, command_line, inputs_sha256, start/end_time, exit_code, stdout_tail, stderr_tail, artifacts{name,sha256}}`；真机侧保留屏幕照片/视频与 `sdmc:/switch/<app>/<TitleID>/` 日志；Ryujinx/Citron 侧记录日志文件路径与版本号（模拟器版本必须与 commit 对应，不能只写 "latest"）。

## 8. M3 前置条件结论

**已具备**：
1. keys 来源合法且本机可用：Ryujinx 自带 `prod.keys`（12,007 B，sha256 `7bb3b6d2…`）含 `header_key` 与 `key_area_key_application_00–15`；用户明确允许使用；不涉及分发。
2. 打包工具链版本可锁定：nstool `v1.9.2`（有官方 win_x64 二进制）、hacBrewPack `v3.05`（GPL-2.0，子进程隔离）、NTON `v3.0.1`（仅对照）。
3. 产物校验路径明确：nstool `-y` 不需要 keys，可作 CI/本机的第一道闸。
4. 测试后端版本可固定：Ryujinx 1.3.265+4e81a4c2 本机留档；Citron tag 2026-04-27 登记。
5. NSP 输入/输出契约与已知坑（非确定性、就地修改、259 B 路径、icon EXIF）已有原文依据。

**仍缺 / 阻塞**：
1. **hacBrewPack 可执行二进制来源未定**：仓库无 release；只能从 NTON portable 的 `bin/` 提取（未核验）或自编译（本轮禁止；需要 C 工具链 + mbedtls，或复用 Carafe 的 Docker 构建）。→ M3 第一步必须解决并记录该二进制 SHA-256 与许可证副本。
2. **真机 CFW/sigpatches 状态未确认**：M3 验收要求真机安装+HOME 启动+存档隔离；用户侧是否已装 Atmosphère/sigpatches、FW 版本未记录。
3. **DBI 许可缺失**：安装工具可用但无许可证文本，不能进入任何自动分发/CI 缓存；只能本机手工安装。
4. **Ryujinx 官方源不可达**：无法在线复现 1.3.265 构建；只能依赖本机留档（Lead 已核）。
5. **未实测打包**：本轮禁止构建，因此「keys 可用→NSP 可装」全链路尚未打通；M3 需一次最小端到端实测（自包含 NSP 的 ExeFS loader + RomFS 数据 + nstool 校验 + 真机安装）。

## 9. 未验证 / 失败项

| 编号 | 项 | 结果 | 备注 |
| --- | --- | --- | --- |
| U1 | gitlab.hugofnm.fr/publicmirrors/Ryujinx 的 Canary-1.3.265 | not-verified（延续 v0.3） | v0.3 实测匿名 401/404、网页 404；本轮未复测；官方 Canary 源证据指向 Forgejo git.ryujinx.app（TLS 不可达） |
| U2 | git.ryujinx.app / update.ryujinx.app / ryujinx.app | not-verified（延续 v0.3；本轮未复测） | TLS 握手失败/Cloudflare 403；因此 Canary-1.3.265 的官方 commit 归属只能由本机二进制/源码 zip 交叉证明（Lead 已提供 4e81a4c2… 一致） |
| U3 | shchmue/Lockpick_RCM | **失败：HTTP 451（DMCA）** | block.reason=dmca，created_at 2023-05-08；未获取 README，步骤为社区通行概要，未实机验证、未下载 |
| U4 | DBI 许可证 | 无 | 仓库无 LICENSE、`/license` 404、README 未声明；按不可再分发处理 |
| U5 | switch-nsp-forwarder LICENSE | 缺失 | `/license` 404；仅 package.json 声明 MIT |
| U6 | hacBrewPack 官方二进制 | 不存在 | 无 release；二进制来源待定（NTON bin 未核验 / 自编译未执行） |
| U7 | autorun-horizon-dlls 逐组件许可 | 部分 | 仅依据 NOTICE.md 摘要；未做法务级复核；NOTICE 引用 commit 早于当前 HEAD |
| U8 | Citron Neo 实测 | 引用他任务 | 本文件只登记元数据；release 资产未下载、SHA-256 未计算 |
| U9 | hb-appstore | 低相关 | release 停更 2023；未安装验证；非 M3 依赖 |
| U10 | 本机 keys 的实际打包能力 | 未验证 | 只做 key 名静态检查；未运行 hacBrewPack（本轮禁止构建） |
| U11 | 真机状态 | 未确认 | 无 CFW/FW/sigpatches 记录 |
| U12 | NTON portable `bin/` 内容 | 未核验 | 未下载 61MB 安装包；「随附已编译 hacBrewPack」来自 README 文字 |

## 10. 对 GalNX 的建议

### 10.1 版本锁定表（v0.4，全部 2026-10-29 复核）

| 角色 | 锁定版本 | commit | 许可证 | 使用方式 |
| --- | --- | --- | --- | --- |
| 打包 | hacBrewPack v3.05 | `745b16ecfc9ce055743067d200572204cb2aac6c` | GPL-2.0 | 子进程；二进制 SHA-256 待记录 |
| 校验 | nstool v1.9.2（win_x64） | `e89ea84bd70c11b67ebec9153fb4a446f18a9d3d` | MIT | 子进程，`-y` 校验 |
| forwarder（仅对照） | NTON v3.0.1 | `c5d543a91b7cd1df880f98c9ab831be9a40d024f` | GPL-3.0 | 不进主路线 |
| forwarder 模板（仅对照） | switch-nsp-forwarder 0.0.8 | `61edd504e57c6007f23a3a242b386ac0372c0cee` | MIT（缺 LICENSE 文件） | 不进入产物 |
| 真机 homebrew 入口 | nx-hbmenu v3.6.1 | `fd26270a4e4b6994886a57b0738d98229ab4094e` | ISC | 用户 SD 卡；不随 NSP 分发 |
| 真机 loader | nx-hbloader v2.4.5 | `82b95122c5ae8dc059bf23893ba7623c72c86773` | ISC | 用户 SD 卡 |
| 真机安装 | DBI 912（ru） | `e5ba732459c12b5777034678584f35e773c84c61` | 无（不可分发） | 用户本机手工 |
| 可选商店 | hb-appstore v2.3.2 | `cd74a989b9c6d5a1fe0eb621b91e331f8526f710` | GPL-3.0 | 可选，非依赖 |
| 测试后端 1 | Ryujinx 1.3.265+4e81a4c2 | 源码 zip Comment `4e81a4c2f4fee6f31e28fbb129759ec2369da6eb` | 本地留档 | 本机验收辅助 |
| 测试后端 2 | Citron Neo tag 2026-04-27 | `0076ee8fcaab0346de59a357a80700541decbaeb` | GPL-3.0 | 回归辅助（他任务实测） |
| 参考运行时 | Autorun test-build-4 / horizon-dlls dlls | `9b7170505f9084fee0ffe1a237b08557a6ab2868` / `4ab914bb4f7ffd35753934c02ecde05eed23a50f` | LGPL-2.1+/逐组件 | 只读参考，不分发 |
| 参考工作台 | Carafe v0.4.0 | `9b69701b8ae885126b09cf2ccdddef1eccee9732` | GPL-3.0 | 文档/子进程参考，不复制代码 |

### 10.2 集成顺序

1. **nstool**（先上）：只读、无 keys、MIT，可立即做 CI 校验闸；固定 `v1.9.2` win_x64 二进制并记录 SHA-256。
2. **hacBrewPack**（第二步）：解决二进制来源（优先自编译并记录来源/哈希，或从 NTON portable 提取并记录版本），跑通「ExeFS loader + RomFS 数据 → NSP」最小样本；所有输入传副本、处理 259 B 路径、固定 keyset 路径只读传入。
3. **自有编排层**（第三步）：实现 §6.2 契约（输入预检、子进程、日志/退出码、nstool 校验、PROVENANCE）。
4. **NTON / switch-nsp-forwarder**（对照实验，最后）：只用于验证「forwarder 与自包含的区别」，不进入产品路径。
5. **Carafe / Autorun**：只读参考；不引入其 GPL-3.0 代码/运行时；Autorun 的 experimental 状态不得写成「可用于生产」。

### 10.3 仍存在的阻塞项（M3 启动前必须关闭）

- **B1 hacBrewPack 二进制来源+哈希**（见 §8）。
- **B2 真机 CFW/sigpatches/FW 记录**：无真机记录则 M3 的「安装+HOME 启动」验收无法完成。
- **B3 DBI 不可分发**：安装步骤只能写进用户文档，不能进 CI/缓存/发行包。
- **B4 Ryujinx 源不可达**：测试环境必须依赖本机留档的 exe/zip；PROVENANCE 记录两者 SHA-256。
- **B5 keys 合规**：CI 禁止注入真实 keys；本地构建路径必须走 `GALNX_PROD_KEYS` 只读配置，日志脱敏。
- **B6 非确定性构建**：验收/回归不得用输出 bitwise 对比；改用 nstool 结构校验 + TitleID/名称/图标断言。

---


<!-- AUDIT-JSON-BEGIN -->
```galnx-audit
[
  {
    "name": "rlaphoenix/NTON",
    "url": "https://github.com/rlaphoenix/NTON",
    "default_branch": "master",
    "head_sha": "c5d543a91b7cd1df880f98c9ab831be9a40d024f",
    "head_date": "2026-09-15",
    "pinned": "v3.0.1 = c5d543a91b7cd1df880f98c9ab831be9a40d024f (annotated tag object 9587422b41e2ff22aec7fb0071a7d68249230a9c)",
    "license_spdx": "GPL-3.0",
    "license_file": "LICENSE",
    "license_notes": "LICENSE 为 GPLv3 全文 (35149 B, sha f288702d...); pyproject license = GPL-3.0-only; README Licensing 节列明所捆绑第三方: hacBrewPack (The-4n, GPL-v2), nstool (MIT), hptnacp from hacPack (GPL-v2), rom from switch-nsp-forwarder (MIT), 并称未做修改、许可证副本随 bin/ 内二进制分发（本轮未下载核验）",
    "archived": false,
    "last_push": "2026-10-24",
    "stars": 245,
    "open_issues": 8,
    "build_system": "Python 3.10+; uv + hatchling (pyproject) 构建/测试, PyInstaller + Inno Setup (CD) 出 portable/setup exe",
    "build_deps": "click~=8.5.0, requests~=2.34.2, jsonpickle~=4.1.2, coloredlogs~=15.0.1, beautifulsoup4~=4.15.0, lxml~=6.1.3, pillow~=12.3.0; GUI 额外 PySide6-Essentials~=6.11.2; 打包 pyinstaller~=6.22.3",
    "readme_claims": "README 声称: 把 NRO 包装成 NSP forwarder; 支持 Firmware 12.0.0+; 支持 GUI 与 CLI; 从 NRO 自动提取标题信息与图标; NSP 安装体积约 1MB; README CAUTION 原文: Installing these kinds of NSP files (NRO to NSP forwarders) can result in a console ban. This applies not just to this software but to all forms of NRO to NSP forwarder generators, including homebrew and web-app versions. Troubleshooting 原文: As the NSP forwarder's signature is not valid as we do not possess Nintendo's private signing keys, you cannot boot any NSP forwarder with CFW alone. Nintendo has DMCA'd the options that allow you to run these kinds of NSP files due to it allowing piracy.",
    "readme_claim_url": "https://raw.githubusercontent.com/rlaphoenix/NTON/master/README.md",
    "risks": [
      "forwarder 不等于自包含: NRO 路径硬编码在 NSP 内, 他人生成的 forwarder 在本机很可能找不到 NRO (README Troubleshooting 原文)",
      "README 明确警告安装 NRO→NSP forwarder 可能导致主机封禁, 且该风险适用于所有同类生成器",
      "forwarder 签名非 Nintendo 私钥签名, 仅 CFW + sigpatches 环境可装/可启; 相关绕过方式已被 Nintendo DMCA",
      "版本锁定 v3.0.1; 上游 2026-10-24 仍有 push, 有新版本风险 (本轮不可用作 M3 主路径, 仅对照)"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "NTON portable 包内 bin/ 随附的 hacBrewPack/nstool/hptnacp/rom 二进制本轮未下载核验 (U12)"
    ],
    "source_urls": [
      "https://api.github.com/repos/rlaphoenix/NTON",
      "https://api.github.com/repos/rlaphoenix/NTON/releases/latest",
      "https://raw.githubusercontent.com/rlaphoenix/NTON/master/README.md",
      "https://raw.githubusercontent.com/rlaphoenix/NTON/master/pyproject.toml"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "rlaphoenix/hacBrewPack",
    "url": "https://github.com/rlaphoenix/hacBrewPack",
    "default_branch": "master",
    "head_sha": "745b16ecfc9ce055743067d200572204cb2aac6c",
    "head_date": "2019-10-13",
    "pinned": "v3.05 = 745b16ecfc9ce055743067d200572204cb2aac6c (lightweight tag; HEAD 与 tag 同 commit)",
    "license_spdx": "GPL-2.0",
    "license_file": "LICENSE",
    "license_notes": "GPL v2 (README Licensing 节); LICENSES/ 另含 hactool.LICENSE 与 switch-tools.LICENSE (第三方组件分发义务)",
    "archived": false,
    "last_push": "2026-09-15",
    "stars": 2,
    "open_issues": 0,
    "build_system": "C + Makefile (GNU make, gcc -O2 -Wall -Wextra -pedantic -std=gnu11 -fPIC); 内置/随附 mbedtls 先构建; 无 release 二进制",
    "build_deps": "mbedtls (随仓库 mbedtls/ 目录, 链接 -lmbedtls -lmbedx509 -lmbedcrypto), C 标准库; 无其它外部依赖",
    "readme_claims": "README 声称: tool for creating Nintendo Switch NCAs ... from homebrews and pack them into NSPs; keys 查找顺序 keys.dat 同目录 → keys.txt/keys.ini/prod.keys/~/.switch/prod.keys, -k 可指定; 必需 header_key 与 key_area_key_application_xx; 输入 build/exefs/main + main.npdm + [TARGET].nacp(改名 control/control.nacp 放 control/); icon 必须 256x256 JPEG; TitleID 小写 0x0100000000000000-0x0fffffffffffffff 且不建议超 0x01ffffffffffffff; hacBrewPack doesn't need any options to work.",
    "readme_claim_url": "https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/README.md",
    "risks": [
      "本仓库是 The-4n/hacBrewPack 已删除后的镜像, 镜像建于 2026-09-15 但源码最后提交为 2019-10-13; 上游维护者已停止维护",
      "无官方 release 二进制; 必须自编译或从 NTON portable 提取, 供应链可信度需自行记录 SHA-256",
      "会就地修改输入文件 (npdm.c/nacp.c), 调用方必须传副本",
      "RSA-PSS 随机盐导致同一输入两次构建产物不同 (非确定性)",
      "Windows 路径上限 259 B, 长路径会 Failed to stat",
      "logo/ 的 NintendoLogo.png 与 StartupMovie.gif 无官方许可, 需替换或 --nologo",
      "icon 必须为 256x256 JPEG, EXIF 可能导致占位/安装卡住",
      "GPL-2.0: 以子进程调用隔离, 不链接/不复制代码进 GalNX"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "/releases/latest 返回 404 (无 release), 无法记录官方二进制哈希 (U6)"
    ],
    "source_urls": [
      "https://api.github.com/repos/rlaphoenix/hacBrewPack",
      "https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/README.md",
      "https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/Makefile",
      "https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/CHANGELOG.txt"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "jakcron/nstool",
    "url": "https://github.com/jakcron/nstool",
    "default_branch": "development-tip",
    "head_sha": "cfb826ca6c165fbcd816fd7949df88ef3d72a948",
    "head_date": "2024-10-14",
    "pinned": "v1.9.2 = e89ea84bd70c11b67ebec9153fb4a446f18a9d3d (release 资产 nstool-v1.9.2-win_x64.zip 487087 B)",
    "license_spdx": "MIT",
    "license_file": "LICENSE",
    "license_notes": "MIT 全文 (1061 B); .gitmodules 依赖 jakcron/libmbedtls 等各自许可, 二进制 release 随附; 用户无需自行处理",
    "archived": false,
    "last_push": "2024-10-14",
    "stars": 559,
    "open_issues": 16,
    "build_system": "C++ / GNU make (makefile); git submodule init/update 后 make deps + make; Windows 另有 Visual Studio 解决方案 build/visualstudio/nstool.sln (VS2015/2017/2019); 官方 release 提供 win_x64/win_x86 二进制",
    "build_deps": "submodule: jakcron/libmbedtls, libfmt, libtoolchain, liblz4, libpietendo; 编译需 C++ 工具链",
    "readme_claims": "README 声称: General purpose read/extract tool for Nintendo Switch file formats; 支持 PFS0/HFS0/RomFS/NCA/NSP/XCI/META/NACP/CNMT/CERT/TIK/NSO/NRO/INI1/KIP1 等; 默认输出一般信息, --showlayout/-v 详细; -t/--type 覆盖类型; -y/--verify 校验 (NCA Header Sig0/Sig1, META, XCI, CERT/TIK, v1.6.0 起内置 Root/XCI/ACID/NCA Header 公钥, 不需要 keys); -x 提取; --basenca 处理 patch NCA; NSTool doesn't embed any keys that are copyright protected.",
    "readme_claim_url": "https://raw.githubusercontent.com/jakcron/nstool/development-tip/README.md",
    "risks": [
      "默认分支是 development-tip 而非 main/master, 版本固定必须用 tag v1.9.2 + 二进制 SHA-256 双记录",
      "上游最后提交 2024-10-14, 对新固件/格式的校验覆盖可能滞后",
      "release 二进制由上游 CI 构建, 仍需记录下载哈希"
    ],
    "verification_level": "read-only",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/jakcron/nstool",
      "https://api.github.com/repos/jakcron/nstool/releases/latest",
      "https://raw.githubusercontent.com/jakcron/nstool/development-tip/README.md",
      "https://raw.githubusercontent.com/jakcron/nstool/development-tip/BUILDING.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "TooTallNate/switch-nsp-forwarder",
    "url": "https://github.com/TooTallNate/switch-nsp-forwarder",
    "default_branch": "main",
    "head_sha": "845811585e0b0d8881745afd50eca25d203957fd",
    "head_date": "2026-05-03",
    "pinned": "0.0.8 = 61edd504e57c6007f23a3a242b386ac0372c0cee (release 资产 nsp-forwarder.nro 11585582 B / nsp-forwarder.nsp 9123544 B)",
    "license_spdx": "MIT",
    "license_file": "package.json (仓库无 LICENSE 文件; /license 404)",
    "license_notes": "仅在 package.json 声明 \"license\": \"MIT\"; 无根 LICENSE 文本, 无 /license API 元数据; 严格用法务视角属许可证声明不完整",
    "archived": false,
    "last_push": "2026-06-16",
    "stars": 142,
    "open_issues": 14,
    "build_system": "JavaScript/TypeScript (nx.js 运行时); esbuild 打包, pnpm (packageManager pnpm@10.33.2); nxjs-nro / nxjs-nsp 生成 NRO/NSP",
    "build_deps": "@nx.js/clkrst ^1.0.1, @nx.js/constants ^0.4.0, @nx.js/install-title ^0.0.3, @nx.js/ncm ^1.2.0, @tootallnate/nacp ^0.2.0, jimp 1.6.0, react ^18.3.1, react-router-dom ^6.30.2, react-tela ^1.0.1; dev: @nx.js/nro|nsp|runtime 0.0.69, esbuild ^0.28.0, typescript ^5.8.3",
    "readme_claims": "README 仅: Generate and Install NSP to NRO forwarders on your Switch (并链接 Releases); CHANGELOG 0.0.8: 重建 forwarder ROM 修复 NRO 退出后 + 键回 HOME 死循环; 0.0.7: TitleID 由 NRO 路径与参数 SHA-256 派生 (match sphaira)",
    "readme_claim_url": "https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/README.md",
    "risks": [
      "无 LICENSE 文件, 只有 package.json 声明 MIT, 分发/再分发前需向上游确认",
      "与 NTON 的关系: NTON README 明确其 rom/ 启动器 rom 来自 switch-nsp-forwarder (MIT), NTON 只说未修改并保留许可证副本; 版本 0.0.8 与本仓库 tag 不保证互为同一份 ROM",
      "forwarder 路线本身受封禁/DMCA 风险约束 (见 NTON README CAUTION)",
      "14 open issues, 依赖 nx.js 生态 (0.0.x 版本号)"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "/license 返回 404; 无根 LICENSE; 仅 package.json 声明 MIT (U5)"
    ],
    "source_urls": [
      "https://api.github.com/repos/TooTallNate/switch-nsp-forwarder",
      "https://api.github.com/repos/TooTallNate/switch-nsp-forwarder/releases/latest",
      "https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/package.json",
      "https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/CHANGELOG.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "carafe-nx/carafe",
    "url": "https://github.com/carafe-nx/carafe",
    "default_branch": "main",
    "head_sha": "3334ebc66e9bb2f6c12364a7b0b9a7472381fc3e",
    "head_date": "2026-10-25",
    "pinned": "v0.4.0 = 9b69701b8ae885126b09cf2ccdddef1eccee9732 (release 2026-10-25, x64-setup 228142873 B)",
    "license_spdx": "GPL-3.0-or-later",
    "license_file": "LICENSE",
    "license_notes": "LICENSE 为 GPLv3 全文 (35149 B); runtime/overlay 与 runtime/patches 为 LGPL-2.1-or-later, loader 为 ISC, external/ 各自许可 (README 声明)",
    "archived": false,
    "last_push": "2026-10-29",
    "stars": 255,
    "open_issues": 9,
    "build_system": "Tauri 2 (Rust core + React 19/TypeScript 前端) + 独立 runtime 构建: docker compose (docker/Dockerfile) 构建 runtime 与 hacBrewPack; GitHub Actions check.yml (windows-latest, node 24, rust 1.99.0) 与 release.yml (tag ^vX.Y.Z$, NSIS 打包, gh release create)",
    "build_deps": "Rust 1.99, Tauri 2, React 19, TypeScript 7, Docker (runtime 构建), Wine 11.18 + Box64/FEX + DXVK + Mesa (runtime 组件), hacBrewPack v3.05 (external/hacbrewpack), mbedTLS 2.6.1",
    "readme_claims": "README 声称: Desktop app that turns Windows games into Switch apps; 选游戏目录 → Build 打包 game+runtime+settings 进 NSP → USB(DBI) 安装; runtime 基于 Autorun (Wine+Box64/FEX+DXVK+Mesa) + hacBrewPack 打包 NSP; 需要 Atmosphère+sigpatches 与 DBI; 安装包未签名; 测试全部真机 (无 emulator loop)",
    "readme_claim_url": "https://raw.githubusercontent.com/carafe-nx/carafe/main/README.md",
    "risks": [
      "GPL-3.0: 只能文档/子进程方式参考, 不得复制其代码进 GalNX (Carafe 自身也不复用其代码)",
      "依赖 Docker 构建 runtime; 与 Autorun 运行时强绑定, Autorun 仍 experimental",
      "docs/nsp.md 明确 hacBrewPack 会就地修改输入、RSA-PSS 非确定性、259B 路径上限 — GalNX 需自行复现这些约束",
      "Windows 安装包未签名 (README); 发行物 227MB 级",
      "版本迭代快 (v0.4.0, 2026-10 多次提交), 作为参考时须锁 tag"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/carafe-nx/carafe",
      "https://api.github.com/repos/carafe-nx/carafe/releases/latest",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/nsp.md",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/architecture.md",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/testing.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "autorunhq/autorun",
    "url": "https://github.com/autorunhq/autorun",
    "default_branch": "main",
    "head_sha": "1ac9b6cf37b90f2d5783dd7ef389bebbe1c68877",
    "head_date": "2026-10-16",
    "pinned": "test-build-4 = 9b7170505f9084fee0ffe1a237b08557a6ab2868 (release 2026-09-24, autorun-test-build-4.zip 64978068 B)",
    "license_spdx": "NOASSERTION",
    "license_file": "LICENSE",
    "license_notes": "根 LICENSE 仅 Wine 的 LGPL-2.1+ 文本 (824 B), 另有 COPYING.LIB (26434 B); GitHub /license 返回 NOASSERTION/Other; 完整许可由 README Credits 表与 NOTICES.md 逐组件声明 (Wine LGPL-2.1+, FEX MIT, Box64 MIT, DXVK zlib/libpng, VKD3D-Proton LGPL-2.1+, Mesa MIT, LSFG-VK GPL-3.0+, Atmosphère/Horizon-OC GPL-2.0, libnx/devkitPro ISC, SDL2/FreeType 等)",
    "archived": false,
    "last_push": "2026-10-16",
    "stars": 525,
    "open_issues": 62,
    "build_system": "Autotools (configure/configure.ac, build.sh) + CMake (horizon-wine/CMakeLists.txt); GitLab CI (.gitlab-ci.yml, 仅 stages 定义); 多份 build-*.sh 构建 x86/amd64/boot 组件 (switch-dev docker 镜像, llvm-mingw-20260505-ucrt-macos-universal 工具链)",
    "build_deps": "Wine 11.18 (VERSION 文件), FEX, Box64 (bootstrap revision 2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a), Mesa 26 mesa-switch, DXVK (D3D8-11), VKD3D-Proton (D3D12), LSFG-VK; horizon-dlls 与 game-fixes 为 git submodule; 构建需 docker/switch-dev 与 llvm-mingw",
    "readme_claims": "README 声称: Play Windows PC games on your Nintendo Switch; FEX 翻译 x86/x64, Box64 作为 32 位第二翻译器, Mesa 26 mesa-switch, DXVK/VKD3D-Proton, LSFG-VK 帧生成, Windows DLL 由 app 下载; 原文 > **Autorun is experimental.** Some games run well, many start and then stop on something that isn't done yet. Every run writes a log that says where.; 声明 Not a piracy or circumvention tool; 需 CFW(Atmosphère)、microSD、约 200MB DLL",
    "readme_claim_url": "https://raw.githubusercontent.com/autorunhq/autorun/main/README.md",
    "risks": [
      "experimental 状态 (README 自述), 不能写成可用于生产",
      "LGPL-2.1+ / GPL-3.0+ 组件混杂, 再分发义务复杂; 根 LICENSE 仅 Wine 文本, 不能据此判断整体许可",
      "运行时 DLL 仓库 (autorun-horizon-dlls) 需逐组件许可复核",
      "依赖自建 docker 镜像/llvm-mingw 工具链, 复现构建成本高",
      "62 open issues; 仅 3 个 test-build tag, 无稳定 release",
      "GalNX 只应作只读参考, 不引入代码/运行时"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "README Credits 表的各组件版本未逐项到对应子仓库核实",
      "构建脚本未执行 (本轮禁止构建)"
    ],
    "source_urls": [
      "https://api.github.com/repos/autorunhq/autorun",
      "https://api.github.com/repos/autorunhq/autorun/releases/latest",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/README.md",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/horizon-wine/README.md",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/VERSION"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "autorunhq/autorun-horizon-dlls",
    "url": "https://github.com/autorunhq/autorun-horizon-dlls",
    "default_branch": "main",
    "head_sha": "67e2303dee9191b7ce4e2d1ccb47957d15c8a98b",
    "head_date": "2026-10-16",
    "pinned": "dlls = 4ab914bb4f7ffd35753934c02ecde05eed23a50f (release 2026-09-28; horizon-dlls.tar.zst 88439006 B / zip 203013347 B)",
    "license_spdx": "NOASSERTION",
    "license_file": "LICENSES/ (无根 LICENSE; /license 404)",
    "license_notes": "无根 LICENSE; 由 NOTICE.md (65295 B) + LICENSES/ 逐组件声明: Capstone BSD-3-Clause, FEX MIT, FFmpeg LGPL-2.1+, FAudio Zlib, FluidSynth LGPL-2.1+, ICU Unicode-DFS-2016 AND ICU, libjpeg IJG, Little CMS MIT, mpg123 LGPL-2.1-only, musl MIT, vkd3d/Wine LGPL-2.1+, DXVK-zlib, SQLite blessing 等; NOTICE 说明由 Wine 11.18 (autorun commit 97422507a2bc8100c6ba32a13828109a340e9131) 构建",
    "archived": false,
    "last_push": "2026-10-16",
    "stars": 8,
    "open_issues": 0,
    "build_system": "不直接构建: 由 Autorun 仓库的 Wine 源码树产出; 仓库 main 分支存放 DLL 文件 + manifest (runtime-interfaces.json / version / size / SHA-256 每文件), compressed/ 为 zlib 压缩; tools/tests/switch/documentation 辅助",
    "build_deps": "源自 Wine 11.18 + FEX CPU 模块 + DXVK + VKD3D-Proton; 分发形态为预编译 DLL 仓库 (tar.zst/zip)",
    "readme_claims": "README 声称: Every module a Windows game expects to find in system32 (ARM64X) and syswow64 (i386), built from Autorun's Wine, with FEX's CPU modules and the bundled DXVK and VKD3D-Proton; Autorun 自动下载/更新, 每文件 version/size/SHA-256, 只取变化; 无网络时下载 repo zip 解压到 switch/; 声明 Not a piracy or circumvention tool; 提及 PhysX 9.13.0604 未修改、XLiveLess 替代 GFWL",
    "readme_claim_url": "https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/README.md",
    "risks": [
      "NOTICE.md 引用 Wine 11.18 commit 早于 HEAD, 逐文件与 NOTICE 的对应关系未逐项复核",
      "无根 LICENSE; 若 GalNX 分发任何 DLL 必须逐组件合规 (LGPL 动态链接/源码提供等义务)",
      "203MB 级二进制仓库, 不适合进 GalNX 仓库",
      "GalNX 不引入: 只读参考"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "逐组件许可仅依据 NOTICE.md/LICENSES 摘要, 未做法务级复核 (U7)"
    ],
    "source_urls": [
      "https://api.github.com/repos/autorunhq/autorun-horizon-dlls",
      "https://api.github.com/repos/autorunhq/autorun-horizon-dlls/releases/tags/dlls",
      "https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/README.md",
      "https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/NOTICE.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "switchbrew/nx-hbmenu",
    "url": "https://github.com/switchbrew/nx-hbmenu",
    "default_branch": "master",
    "head_sha": "089fdf85ff82ad7077527092f8615f2e57ffc985",
    "head_date": "2025-11-16",
    "pinned": "v3.6.1 = fd26270a4e4b6994886a57b0738d98229ab4094e (release 2025-11-15, nx-hbmenu_v3.6.1.zip 1249201 B)",
    "license_spdx": "ISC",
    "license_file": "LICENSE",
    "license_notes": "ISC; README Credits 注明部分代码源于 3DS new-hbmenu, 并使用 libjpeg-turbo (图标) 与 c11threads 第三方组件",
    "archived": false,
    "last_push": "2025-11-16",
    "stars": 1406,
    "open_issues": 18,
    "build_system": "C + Makefile: make nx (Switch) / make pc; 需 devkitPro pacman 包 switch-dev, switch-freetype, switch-libconfig, switch-libjpeg-turbo, switch-physfs; 构建需 zip",
    "build_deps": "devkitPro switch-dev 工具链, freetype, libconfig, libjpeg-turbo, physfs; C11 Threads",
    "readme_claims": "README 声称: See Homebrew_Applications for SD layout and applications, etc. See Switchbrew for hbmenu docs.; 最新版从 releases 下载; 用途为真机上浏览/启动 SD 卡 NRO",
    "readme_claim_url": "https://raw.githubusercontent.com/switchbrew/nx-hbmenu/master/README.md",
    "risks": [
      "未在真机运行",
      "SD 布局细节依赖 Switchbrew wiki (本轮未抓取)",
      "版本须与 Atmosphère/FW 组合记录"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "未真机验证 hbmenu 在目标 FW/Atmosphère 上的运行"
    ],
    "source_urls": [
      "https://api.github.com/repos/switchbrew/nx-hbmenu",
      "https://api.github.com/repos/switchbrew/nx-hbmenu/releases/latest",
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
    "pinned": "v2.4.5 = 82b95122c5ae8dc059bf23893ba7623c72c86773 (release 资产 hbl.nsp 40946 B)",
    "license_spdx": "ISC",
    "license_file": "LICENSE",
    "license_notes": "ISC",
    "archived": false,
    "last_push": "2025-11-15",
    "stars": 417,
    "open_issues": 3,
    "build_system": "C + Makefile (仓库约 60 KB); 发布物为 hbl.nsp",
    "build_deps": "devkitPro switch-dev (推断自 switchbrew 生态, 仓库无 README 可引用)",
    "readme_claims": "无 README (contents/README.md 404); 用途依据 switchbrew 生态与 release 资产 hbl.nsp",
    "readme_claim_url": "",
    "risks": [
      "无 README 可引用",
      "hbl.nsp 与目标 FW/Atmosphère 组合未验证"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "README 抓取 404, 无文档声明可引用"
    ],
    "source_urls": [
      "https://api.github.com/repos/switchbrew/nx-hbloader",
      "https://api.github.com/repos/switchbrew/nx-hbloader/releases/latest"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "rashevskyv/dbi",
    "url": "https://github.com/rashevskyv/dbi",
    "default_branch": "main",
    "head_sha": "22090afc64cc7b5d645a99bf3d4d8625a67b766e",
    "head_date": "2026-10-09",
    "pinned": "912ru = e5ba732459c12b5777034678584f35e773c84c61 (release 2026-09-18; DBI.nro 16657965 B)",
    "license_spdx": "",
    "license_file": "",
    "license_notes": "无许可证: 仓库无 LICENSE, /license 404, README 未声明; DBI.nro 为作者 duckbill 的闭源发行二进制; 按不可再分发处理",
    "archived": false,
    "last_push": "2026-10-09",
    "stars": 2986,
    "open_issues": 73,
    "build_system": "无源码构建; 发布预编译 DBI.nro + Python dbibackend + Windows dbibackend.exe/dbibackend-qt.exe",
    "build_deps": "无 (二进制分发); DBIbackend Windows 端需 libusbK v3.1.0.0 驱动 (Zadig 安装)",
    "readme_claims": "README 声称: Run MTP responder activates the built-in MTP server in DBI for exchanging data with a PC or an Android device via USB-C OTG; MTP 盘含 SD Card/NAND User/NAND System/Installed games/SD install/NAND install/Saves/Album/Gamecard; SD install - Drop or copy your NSP/NSZ/XCI or XCZ files in this folder. When the transfer is complete the game will be installed on the SD card of your console.; 备选 Install title from DBIbackend (dbibackend.exe + libusbK 驱动)",
    "readme_claim_url": "https://raw.githubusercontent.com/rashevskyv/dbi/main/README.md",
    "risks": [
      "无许可证, 不可随 GalNX 分发或缓存",
      "第三方镜像仓库 (作者 duckbill), 上游发布渠道不可验证",
      "tag 命名 912ru 与 UI 内版本号对应关系未逐字核对",
      "未真机测试 MTP 安装"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "无 LICENSE 文件, /license 404 (U4)"
    ],
    "source_urls": [
      "https://api.github.com/repos/rashevskyv/dbi",
      "https://api.github.com/repos/rashevskyv/dbi/releases/tags/912ru",
      "https://raw.githubusercontent.com/rashevskyv/dbi/main/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "fortheusers/hb-appstore",
    "url": "https://github.com/fortheusers/hb-appstore",
    "default_branch": "main",
    "head_sha": "61d7ccb679b2d2ad97a604e10f70f553a757fb36",
    "head_date": "2026-10-18",
    "pinned": "v2.3.2 = cd74a989b9c6d5a1fe0eb621b91e331f8526f710 (release 2023-03-23; appstore.nro 11104808 B)",
    "license_spdx": "GPL-3.0",
    "license_file": "LICENSE",
    "license_notes": "LICENSE 为 GPLv3 全文; README: This software is licensed under the GPLv3.",
    "archived": false,
    "last_push": "2026-10-18",
    "stars": 1468,
    "open_issues": 27,
    "build_system": "C++/SDL2 + Chesto 前端; libget 包管理器; Switch 安装到 sd:/switch/appstore/; PC 客户端由 GitHub Actions 构建 (nightly.link)",
    "build_deps": "devkitPro switch-dev, SDL2, Chesto/libget, curl/mbedtls 等 (README 构建节)",
    "readme_claims": "README 声称: GUI 访问开源 homebrew 在线仓库; Switch 需要 Homebrew Menu; 可用网页端 apps.fortheusers.org",
    "readme_claim_url": "https://raw.githubusercontent.com/fortheusers/hb-appstore/main/README.md",
    "risks": [
      "release 停更于 2023-03 (源码仍在维护)",
      "非 M3 必需依赖, 仅可选工具",
      "在线仓库内容不受 GalNX 控制"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "未安装验证; release 二进制与 HEAD 源码不同步 (U9)"
    ],
    "source_urls": [
      "https://api.github.com/repos/fortheusers/hb-appstore",
      "https://api.github.com/repos/fortheusers/hb-appstore/releases/latest",
      "https://raw.githubusercontent.com/fortheusers/hb-appstore/main/README.md"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "citron-neo/emulator",
    "url": "https://github.com/citron-neo/emulator",
    "default_branch": "main",
    "head_sha": "c3aa70f81e15ea97ee85b6a9a71cbf75d370851e",
    "head_date": "2026-10-25",
    "pinned": "2026-04-27 = 0076ee8fcaab0346de59a357a80700541decbaeb (release 2026-04-27; nightly 资产名内嵌 commit 如 0237a9b88)",
    "license_spdx": "GPL-3.0",
    "license_file": "LICENSE",
    "license_notes": "GPL-3.0-or-later (README); LICENSE 为 GPLv3 全文 35149 B; LICENSES/ 收录第三方组件许可",
    "archived": false,
    "last_push": "2026-10-25",
    "stars": 597,
    "open_issues": 93,
    "build_system": "C++/CMake; 依赖由 CPM 在 configure 时拉取 (README 明确不需先初始化 submodules); Linux build-citron-linux.sh setup 后 --pgo none --lto full; Windows clang-cl 或 llvm-mingw; Android gradle",
    "build_deps": "CMake, C++ 工具链 (clang-cl/llvm-mingw), CPM 拉取的第三方依赖; Android 需 gradle/arm64",
    "readme_claims": "README 声称: Citron Neo 是延续 Citron 代码库的开源模拟器, 支持 Windows/Linux/macOS/Android(arm64); The switch fell off https://citron-neo.org/",
    "readme_claim_url": "https://raw.githubusercontent.com/citron-neo/emulator/main/README.md",
    "risks": [
      "仅第二测试后端, 不能替代真机验收",
      "release 为 nightly 二进制, tag commit 与资产映射未逐资产核验",
      "GPL-3.0 只在本机测试使用, 不分发",
      "实测结论引用另一任务 (本轮不重复)"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "本轮未下载/未实测, 实测由另一任务提供 (U8)"
    ],
    "source_urls": [
      "https://api.github.com/repos/citron-neo/emulator",
      "https://api.github.com/repos/citron-neo/emulator/releases/tags/2026-04-27",
      "https://raw.githubusercontent.com/citron-neo/emulator/main/README.md"
    ],
    "audited_at": "2026-10-29"
  }
]
```
<!-- AUDIT-JSON-END -->
