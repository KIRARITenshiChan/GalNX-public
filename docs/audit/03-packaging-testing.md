# 集群 D：NSP 打包与测试环境 审计（只读）

- 审计日期: 2026-10-29
- 审计员: audit-package
- 方法: GitHub REST API（经 cred_use 的 GH_TOKEN，使用 /repos、/tags、/releases、/license、/commits、/orgs、/search 端点）；`git ls-remote` 取精确 ref（GIT_TERMINAL_PROMPT=0，经 http://127.0.0.1:7897 代理）；`curl -x http://127.0.0.1:7897` 抓取 raw.githubusercontent.com 原文（README、LICENSE、构建脚本、CI、docs）；Wayback CDX 检索 Ryujinx 网页旁证；GitLab API（curl 经代理）尝试 gitlab.hugofnm.fr 镜像（失败，见「未验证 / 失败项」）。所有 SHA、日期、许可证均来自实际抓取，未使用记忆值。
- 覆盖: 9 个条目（原派发 8 项 = 7 个 GitHub 仓库 + Ryujinx 源流；按 Lead 指示补充 switchbrew/switch-tools 的 nxlink 作为测试环境工具；Ryujinx 条目仅做网页侧旁证，最终归属结论由 Lead 汇总）
- 说明: 本轮为只读审计，未安装任何软件、未编译构建、未克隆仓库、未读取商业游戏数据/模拟器密钥/固件；README 的可用性主张一律标注为「README 声称」。

## 总览表

| 条目 | 用途 | 精确版本（tag/commit） | 许可证(SPDX) | 健康 | 结论 |
| --- | --- | --- | --- | --- | --- |
| rlaphoenix/NTON | NRO→NSP forwarder 生成器（CLI+GUI） | v3.0.1 @ c5d543a91b7c（2026-09-15） | GPL-3.0 | 245★ / 8 open / pushed 2026-10-24 | 可用，但只产 forwarder：风险与封禁警告最高 |
| rlaphoenix/hacBrewPack | NSP/NCA 打包引擎（NTON、Carafe 的底层） | v3.05 @ 745b16ecfc9c（提交 2019-10-13；镜像建于 2026-09-15） | GPL-2.0 | 2★ / 0 open / 无 release | 采用作为打包内核（锁 v3.05） |
| jakcron/nstool | NSP/NCA/NACP/CNMT 检查、校验、提取 | v1.9.2 @ e89ea84bd70c（2024-10-14） | MIT | 558★ / 16 open / 2024-10 后无提交 | 采用作为产物检查器（锁 v1.9.2） |
| TooTallNate/switch-nsp-forwarder | Switch 端 forwarder 生成器 + ROM 模板 | 0.0.8 @ 61edd504e57c（2026-05-03） | 仓库无根 LICENSE；package.json 声明 MIT | 142★ / 14 open / pushed 2026-06-16 | 仅作模板/机制参考，再分发许可需确认 |
| switchbrew/switch-tools（nxlink） | 开发期 NRO 热加载与 stdout/stderr 回传 | v1.13.1 @ 22756068dd0e（2024-10-23） | ISC | 181★ / 2 open / 2024-10 后无提交 | 开发内循环可用；不是打包工具 |
| autorunhq/autorun | Windows 游戏兼容运行时（Wine 11.18 fork） | test-build-4 @ 9b7170505f90（2026-09-24） | NOASSERTION（Wine LGPL-2.1-or-later 为主体，逐组件） | 525★ / 62 open / README 自述 experimental | 仅参考，不进入 GalNX v0.1 必需链 |
| autorunhq/autorun-horizon-dlls | Autorun runtime 所需 Windows DLL 内容包 | dlls @ 4ab914bb4f7f（2026-09-28） | NOASSERTION（无根 LICENSE，NOTICE.md 逐组件） | 8★ / 0 open / release 2026-09-28 | 仅参考；体积大（zip 203 MB） |
| carafe-nx/carafe | 参考实现：游戏目录+runtime→NSP 全流程 | v0.4.0 @ 9b69701b8ae8（2026-10-25） | GPL-3.0-or-later | 253★ / 9 open / pushed 2026-10-28 | 仅设计参考（GPL 传染，代码不可直接并入） |
| Ryujinx 源流（网页侧旁证） | 测试用模拟器版本对应与固定依据 | 官方源不可达；本机二进制 1.3.265+4e81a4c（Lead 取证） | 无法验证 | Ryubing/UpdateServer 30★；ryujinx-mirror 451 DMCA | not-verified；结论由 Lead 定稿 |

## 条目详情

### 1. rlaphoenix/NTON

- URL: https://github.com/rlaphoenix/NTON
- 默认分支 / HEAD: `master`；HEAD `c5d543a91b7cd1df880f98c9ab831be9a40d024f`（2026-09-15，提交信息 `Bump to v3.0.1, update changelog`）；pushed_at 2026-10-24T00:04:29Z
- 最近 tag: `v3.0.1` = `c5d543a91b7cd1df880f98c9ab831be9a40d024f`（annotated tag 对象 `9587422b41e2ff22aec7fb0071a7d68249230a9c`；GitHub Release 发布于 2026-09-15T07:08:47Z，资产 `NTON-v3.0.1-portable.exe` 61316886 B、`NTON-v3.0.1-setup.exe` 42366778 B）。历史 tag：v3.0.0 `852f0686`、v2.2.0 `94d45dc2`、v2.1.1 `daa25916`、v2.1.0 `43b61e0a`、v2.0.1 `037f5b1b`、v2.0.0 `95525262`、v1.4.0 `8604ea82`（共 16 个 tag）
- 许可证: SPDX `GPL-3.0`；文件根目录 `LICENSE`（35149 B，GPLv3 全文，GitHub /license 返回 blob sha `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`）；`pyproject.toml` 声明 `license = "GPL-3.0-only"`。义务要点：分发二进制需提供对应源码（tag v3.0.1 可对应）并保留许可文本。仓库还捆绑再分发：hacBrewPack（GPL-2.0）、nstool（MIT）、hptnacp from hacPack（GPL-2.0）、switch-nsp-forwarder 的 rom（MIT）——README Licensing 节称『No changes were made to any of the aforementioned software and copies of their licenses can be found next to their binaries within the bin folder.』
- 健康: archived=false；最后 push 2026-10-24；stars 245；open issues 8；主语言 Python；近期仍活跃（CHANGELOG 3.0.1 于 2026-09-15）
- 构建系统 / 关键依赖: Python >=3.10；hatchling 构建后端 + uv（存在 `uv.lock`）；PyInstaller ~=6.22.3 打便携 exe；Inno Setup（`setup.iss`）做安装器。运行依赖：click ~=8.5.0、requests ~=2.34.2、jsonpickle ~=4.1.2、coloredlogs ~=15.0.1、beautifulsoup4 ~=4.15.0、lxml ~=6.1.3、pillow ~=12.3.0；GUI 额外 PySide6-Essentials ~=6.11.2。CI（`.github/workflows/ci.yml`）：windows-latest，Python 3.10/3.11/3.12/3.13/3.14 矩阵，`uv sync` 后用 `secrets.PROD_KEYS` 写 prod.keys 并构建 `sdl-hello.nro` 的 basic NSP forwarder 作测试；lint 用 pre-commit。CD（`cd.yml`）：push tag `v*` → windows-2022，PyInstaller + Inno Setup（iscc）→ PyPI 与 GitHub Release（marvinpinto/action-automatic-releases）
- README 声称: 『NTON is a PC utility that let's you build an NSP application that launches right into an NRO file. Firmware 12.0.0 and newer is supported.』（https://github.com/rlaphoenix/NTON/blob/master/README.md）。Features：固件 12.0.0+、Title ID 冲突检查、自动从 NRO 提取标题信息与图标、1 MB NSP 安装体积、GUI 与 CLI。Keys 节要求 `prod.keys`（由 Lockpick_RCM 从自有 Switch 提取），可放 `C:\Users\<User>\.switch\prod.keys`、当前目录或安装目录。storage sizes 一律为 0（forwarder 无存档需求）。CHANGELOG：3.0.1（2026-09-15）移除 Python 3.9、图标 JPEG 质量 75%→98%、4:2:0；3.0.0（2026-01-19）支持 FW 21.0.0+、Python 3.13/3.14、迁移 uv/hatchling
- README 原文警示（重要，作为风险证据）: ①『Installing these kinds of NSP files (NRO to NSP forwarders) can result in a console ban. This applies not just to this software but to all forms of NRO to NSP forwarder generators, including homebrew and web-app versions.』（README CAUTION 节，第 36–37 行附近）。②『Please note that using Forwarders others have created has a good chance of not working on your system. The location of the NRO on their system may differ... hence the NSP won't be able to load the homebrew.』（Troubleshooting 节，约 144–147 行）。③『As the NSP forwarder's signature is not valid as we do not possess Nintendo's private signing keys, you cannot boot any NSP forwarder with CFW alone. Nintendo has DMCA'd the options that allow you to run these kinds of NSP files due to it allowing piracy.』（Troubleshooting 节，约 151–153 行）。④README 第 31–32 行给出产品定位与固件下限（见上）
- 未验证: 未运行 NTON、未生成或安装 forwarder；prod.keys 的获取路径与 FW 12.0.0+/21.0.0+ 实际兼容性未实测；CI 中 `secrets.PROD_KEYS` 的来源不可见（本审计不读取任何密钥）；README 关于『1 MB 安装体积』未实测
- 风险: ①官方 README 明确承认安装 forwarder 可能被封禁；②forwarder 签名无效，必须依赖 CFW/sigpatches，且任天堂已对可运行此类 NSP 的方案发出 DMCA；③NRO 路径硬编码在 NSP 中，换机/移动 SD 卡内容即失效；④TitleID 随机分配，需 `--id` 显式指定以避免冲突；⑤打包需 prod.keys，合规与再分发敏感；⑥GPLv3 主体 + 捆绑 GPL-2.0/MIT 组件，内部集成时需保留许可与源码义务
- 来源 URLs: https://api.github.com/repos/rlaphoenix/NTON · https://api.github.com/repos/rlaphoenix/NTON/tags?per_page=100 · https://api.github.com/repos/rlaphoenix/NTON/releases/latest · https://api.github.com/repos/rlaphoenix/NTON/license · https://raw.githubusercontent.com/rlaphoenix/NTON/master/README.md · https://raw.githubusercontent.com/rlaphoenix/NTON/master/pyproject.toml · https://raw.githubusercontent.com/rlaphoenix/NTON/master/CHANGELOG.md · https://raw.githubusercontent.com/rlaphoenix/NTON/master/.github/workflows/ci.yml · https://raw.githubusercontent.com/rlaphoenix/NTON/master/.github/workflows/cd.yml · `git ls-remote https://github.com/rlaphoenix/NTON`

### 2. rlaphoenix/hacBrewPack

- URL: https://github.com/rlaphoenix/hacBrewPack（描述：`Make NCAs/NSPs from Nintendo Switch homebrews (Mirror of now deleted The-4n/hacBrewPack)`）
- 默认分支 / HEAD: `master`；HEAD `745b16ecfc9ce055743067d200572204cb2aac6c`（2019-10-13，提交信息 `Updated sample hbmenu loader`）；pushed_at 2026-09-15T06:38:33Z（镜像仓库本身创建于 2026-09-15T06:38:26Z）
- 最近 tag: `v3.05` = `745b16ecfc9ce055743067d200572204cb2aac6c`（轻量 tag，与 HEAD 同一 commit，2019-10-13）；全仓仅此 1 个 tag，无 GitHub Release（`/releases/latest` 返回 404）
- 许可证: SPDX `GPL-2.0`；文件根目录 `LICENSE`（18092 B）；`LICENSES/` 内含 `hactool.LICENSE`、`switch-tools.LICENSE`（历史来源的第三方许可）。义务要点：GPL-2.0 分发须附源码与许可；作为独立可执行程序被 NTON/Carafe 调用（非链接）时属聚合分发，但 Carafe 作为整体发行仍需满足 GPL 义务
- 健康: archived=false；最后 push 2026-09-15；stars 2；open issues 0；主语言 C；代码实际停留在 2019-10-13（镜像仅重建仓库，无新提交）；原仓库 The-4n/hacBrewPack 已被删除，本仓库为社区镜像
- 构建系统 / 关键依赖: 普通 Makefile（`gcc -O2 -Wall -Wextra -pedantic -std=gnu11 -fPIC`），先构建内置 mbedtls，链接 `-lmbedtls -lmbedx509 -lmbedcrypto` 与 `-lm`；无其它外部依赖。CLI 选项（README）：`--nspdir/--ncadir/--tempdir/--backupdir/--exefsdir/--romfsdir/--logodir/--controldir/--noromfs/--nologo/--keygeneration/--keyareakey/--sdkversion`（默认 `000C1100`）/`--plaintext/--keepncadir/--nosignncasig2/--titleid/--titlename`（512 B）/`--titlepublisher`（256 B）/`--nopatchnacplogo`；『hacBrewPack doesn't need any options to work』
- README 声称: 『tool for creating Nintendo Switch NCAs ... from homebrews and pack them into NSPs』。输入机制：①密钥：`keys.dat`（或回退 `keys.txt`/`keys.ini`/`prod.keys`/`~/.switch/prod.keys`，可用 `-k` 指定），必需 `header_key` 与 `key_area_key_application_xx`（仅描述机制，本审计未读取密钥）；②编译好的 homebrew：`build/exefs/main` + `main.npdm` + `[TARGET].nacp`（须改名为 `control/control.nacp`）；TitleID 必须是小写 `0x0100000000000000`–`0x0fffffffffffffff` 且 Makefile 与 npdm.json 一致；③图标：`icon_<Language>.dat`，必须 256×256 JPEG（含 EXIF 可能导致占位图/安装卡住）；④logo：`logo/` 下 `NintendoLogo.png` 与 `StartupMovie.gif`（README 称无许可，可 `--nologo` 省略）；⑤RomFS 目录（可 `--noromfs` 省略）。输出为 NCA（Program/Control/Meta 等）并打包为 NSP
- 未验证: 未编译（本轮禁止构建）、未运行、未用真实 keys 生成 NSP；README 所述 keygeneration 8+ / `--nosignncasig2` 行为未实测
- 风险: ①代码停更于 2019-10-13，仅支持到 keygeneration 8+（CHANGELOG v3.05），新固件/新 key 代际兼容性未知；②原仓库已删除，这是社区镜像，上游修复不会回流；③依赖用户自备 `prod.keys`，合规与密钥泄露风险；④Windows 下输入路径受 MAX_PATH 259 字节限制（Carafe 实测 258/259 成功、260/270 失败，见条目 8）；⑤会就地修改输入（Carafe 文档指出需传副本）；⑥图标/logo 要求严格（256×256 JPEG、GPL 未覆盖的任天堂 logo 素材）
- 来源 URLs: https://api.github.com/repos/rlaphoenix/hacBrewPack · https://api.github.com/repos/rlaphoenix/hacBrewPack/tags?per_page=100 · https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/README.md · https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/Makefile · https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/config.mk.template · https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/CHANGELOG.txt · https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/LICENSE · `git ls-remote https://github.com/rlaphoenix/hacBrewPack`

### 3. jakcron/nstool

- URL: https://github.com/jakcron/nstool
- 默认分支 / HEAD: `development-tip`；HEAD `cfb826ca6c165fbcd816fd7949df88ef3d72a948`（2024-10-14，提交信息 `Update libtoolchain to v0.8.0 (fixes VS dup issue)`）；pushed_at 2024-10-14T01:37:38Z
- 最近 tag: `v1.9.2` = `e89ea84bd70c11b67ebec9153fb4a446f18a9d3d`（commit 2024-10-14T01:37:24Z，`Merge pull request #118 from jakcron/v1.9.2-release`；Release 发布于 2024-10-14T01:37:38Z，资产 `nstool-v1.9.2-win_x64.zip` 487087 B、`win_x86` 434872 B、`ubuntu_x86_64` 1261583 B、`macos_x86_64` 1383337 B、`macos_arm64` 1473441 B）。历史 tag：v1.9.1 `7fad6aa6`、v1.9.0 `9056cf1c`、v1.8.1 `5cf2ef95`、v1.8.0 `da13b0fd`、v1.7.0-r2 `d87c0fcf`；注意 v1.6.6 与 v1.7.0 均指向 `80cb738b5aa7b2fc5febbbe158aafb7f2981d893`（上游 tag 异常，锁版本时只用 v1.9.2）
- 许可证: SPDX `MIT`；文件根目录 `LICENSE`（1061 B）；`deps/` 下子模块各自许可（mbedtls 为 Apache-2.0/ GPL 双授权、libfmt MIT 等，具体以子模块为准，本次未逐个展开）
- 健康: archived=false；最后 push 2024-10-14；stars 558；open issues 16；主语言 C++；2024-10 之后无提交（维护放缓，但 v1.9.2 产物稳定）
- 构建系统 / 关键依赖: git 子模块：`deps/libmbedtls`、`deps/libfmt`、`deps/libtoolchain`、`deps/liblz4`、`deps/libpietendo`（均 github.com/jakcron/*）。构建（BUILDING.md）：`git submodule init && git submodule update`；Linux/macOS `make deps` 后 `make`；Windows 用 VS 方案 `build/visualstudio/nstool.sln`（文档写 VS2015/2017/2019，未列 2022）
- README 声称（只读检查能力）: 支持格式 PFS0/HFS0/RomFS/NCA/NSP/XCI/META/NACP/CNMT/CERT/TIK(v2)/NSO/NRO/INI1/KIP1；默认打印一般信息，`--showlayout` 显示布局、`--showkeys` 显示 keys 区、`-v` 详细；`-t/--type` 强制类型；`-y/--verify` 校验（NCA Header Sig0/Sig1、META、XCI、CERT/TIK；自 v1.6.0 起内置 Root/XCI/ACID/NCA Header 公钥）；`-x` 提取（整个文件系统/子目录/单文件/重命名）；`--basenca` 处理 patch NCA；`-d/--dev` 开发者模式。README 明确『NSTool doesn't embed any keys that are copyright protected』。产物检查流程可用：`nstool -y -x ...` 完成校验与提取，不需要 prod.keys（校验用内置公钥）
- 未验证: 未下载 win_x64 资产运行（本轮未安装/未执行二进制），校验/提取行为未实测；`deps/` 子模块的具体版本未逐一抓取
- 风险: ①2024-10 后停更，新固件新增格式（如新 NCA 变体）可能不支持；②默认分支为 `development-tip`（非稳定分支），版本锁定必须用 tag/commit 而非分支；③Windows 构建仅提供到 VS2019 的解决方案，现代工具链编译可能需调整（预编译 release 可规避）；④校验为格式/签名层面，不能证明 NSP 可被真机安装
- 来源 URLs: https://api.github.com/repos/jakcron/nstool · https://api.github.com/repos/jakcron/nstool/tags?per_page=100 · https://api.github.com/repos/jakcron/nstool/releases/latest · https://raw.githubusercontent.com/jakcron/nstool/development-tip/README.md · https://raw.githubusercontent.com/jakcron/nstool/development-tip/BUILDING.md · https://raw.githubusercontent.com/jakcron/nstool/development-tip/.gitmodules · https://raw.githubusercontent.com/jakcron/nstool/development-tip/LICENSE · `git ls-remote https://github.com/jakcron/nstool`

### 4. TooTallNate/switch-nsp-forwarder

- URL: https://github.com/TooTallNate/switch-nsp-forwarder
- 默认分支 / HEAD: `main`；HEAD `845811585e0b0d8881745afd50eca25d203957fd`（2026-05-03，提交信息 `Update dependencies to address security advisories ...`）；pushed_at 2026-06-16T09:04:56Z
- 最近 tag: `0.0.8` = `61edd504e57c6007f23a3a242b386ac0372c0cee`（commit 2026-05-03T07:26:42Z `Provide Switch keyset to release workflow`；Release 发布于 2026-05-03T07:27:22Z，资产 `nsp-forwarder.nro` 11585582 B、`nsp-forwarder.nsp` 9123544 B）。历史 tag：0.0.7 `71bb6b85b2a8`、0.0.6 `b9eefd4f0894`、0.0.5 `ac500517c68e`、0.0.4 `f33684cb8792`、0.0.3 `cb6df4aa6faf`、0.0.2 `12d1419b2c0f`、0.0.1 `77f86afb28db`
- 许可证: 仓库无根 LICENSE 文件，`/license` 返回 404；`package.json` 声明 `"license": "MIT"`（仅此声明，无许可全文）。再分发时须注意：发布二进制（.nro/.nsp）的许可依据只有 package.json 声明；`@nx.js/*` 与 `react` 等依赖各自许可需另行遵守
- 健康: archived=false；最后 push 2026-06-16；stars 142；open issues 14；主语言 JavaScript/TypeScript
- 构建系统 / 关键依赖: Node.js + pnpm 10.33.2；`scripts`: `build = esbuild`、`nro = nxjs-nro`、`nsp = nxjs-nsp`；依赖 `@nx.js/clkrst ^1.0.1`、`@nx.js/constants ^0.4.0`、`@nx.js/install-title ^0.0.3`、`@nx.js/ncm ^1.2.0`、`@tootallnate/nacp ^0.2.0`、`jimp 1.6.0`、`react ^18.3.1`、`react-router-dom ^6.30.2`、`react-tela ^1.0.1`；devDeps `@nx.js/nro|nsp|runtime 0.0.69`、`esbuild ^0.28.0`、`typescript ^5.8.3`；`nacp.id = 01c7d19eae2a0000`
- README 声称: README 仅一句『Generate and Install NSP to NRO forwarders on your Switch』并指向 Releases（正文 272 B）。CHANGELOG：0.0.8 重建 forwarder ROM，修复 NRO 退出后 `+` 键回 HOME 的死循环（fixes #29）；0.0.7 『Title IDs are now derived from a SHA-256 hash of the NRO path and arguments, matching sphaira's logic』（确定性 TitleID）
- 与 NTON 的关系: NTON README Licensing 节列 `rom from switch-nsp-forwarder (MIT, launching NRO)`，并指出该 rom 模板位于本仓库 `romfs/template/exefs`（https://github.com/TooTallNate/switch-nsp-forwarder/tree/main/romfs/template/exefs）；NTON README Credits 同时记『TooTallNate 的 ROM 修改支持 v19.0.0+』。即 NTON 复用本仓库的 forwarder ROM 作为启动模板，而本仓库自身是在 Switch 上用 nx.js 运行时生成/安装 forwarder 的 homebrew 应用。本审计未核验两者 ROM 文件是否逐字节相同
- 未验证: 未在 Switch 上运行该 homebrew；未比对 NTON 捆绑 ROM 与本仓库 ROM 的哈希；依赖版本的安全公告修复未验证
- 风险: ①无根 LICENSE 文件，只有 package.json 的 MIT 字段，再分发法律依据偏弱；②forwarder 机制与条目 1 相同的封禁/签名/DMCA 风险；③14 个 open issue，nx.js 生态较早（devDeps 0.0.69）；④TitleID 由路径派生，路径变化会改变 TitleID；⑤NTON 只取 ROM 模板，若上游改模板可能影响 NTON 行为
- 来源 URLs: https://api.github.com/repos/TooTallNate/switch-nsp-forwarder · https://api.github.com/repos/TooTallNate/switch-nsp-forwarder/tags?per_page=100 · https://api.github.com/repos/TooTallNate/switch-nsp-forwarder/releases · https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/README.md · https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/package.json · https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/CHANGELOG.md · `git ls-remote https://github.com/TooTallNate/switch-nsp-forwarder`

### 5. switchbrew/switch-tools（nxlink）

- URL: https://github.com/switchbrew/switch-tools（描述 `Helper tools for Switch homebrew development`；同时包含 elf2nso/elf2nro/elf2kip/build_pfs0/build_romfs/nacptool/npdmtool/nxlink）
- 默认分支 / HEAD: `master`；HEAD `22756068dd0ed6ff9734c59cb4f99ebd3f62555b`（2024-10-23，提交信息 `npdmtool: don't error with missing debug flags, error with multiple set (#50)`）；pushed_at 2024-10-23T15:41:48Z
- 最近 tag: `v1.13.1` = `22756068dd0ed6ff9734c59cb4f99ebd3f62555b`（与 HEAD 同一 commit，2024-10-23）；上一版 v1.13.0=`009889630757`（共 16 个 tag：v1.13.1/v1.13.0/v1.12.0/v1.11.1/v1.11.0/v1.10.0/v1.9.0/v1.8.0/v1.7.1/v1.7.0/v1.6.1/v1.6.0/v1.5.0/v1.4.1/v1.4.0/v1.3.0）
- 许可证: SPDX `ISC`；文件根目录 `COPYING`（726 B，『Copyright 2017 libnx Authors』ISC 全文）；无根 LICENSE 文件；同仓库其它工具同一许可声明
- 健康: archived=false；最后 push 2024-10-23；stars 181；open issues 2；主语言 C；仓库 README 为 0 字节空文件，无构建说明
- 构建系统 / 关键依赖: autotools（`autogen.sh`/`configure.ac`/`Makefile.am`）。`Makefile.am`：`bin_PROGRAMS = elf2nso elf2nro elf2kip build_pfs0 build_romfs nacptool npdmtool nxlink`；`nxlink_SOURCES = src/nxlink.c`、`nxlink_CPPFLAGS = @ZLIB_CFLAGS@`、`nxlink_LDADD = @ZLIB_LIBS@ @NET_LIBS@`；即依赖 zlib 与网络库。`src/nxlink.c`（17018 B）：`NETLOADER_SERVER_PORT 28280`、`NETLOADER_CLIENT_PORT 28771`、zlib 分块传输（ZLIB_CHUNK 16 KiB），含 win32 winsock/WSAPoll 分支
- README 声称: README 为空（0 字节），能力只能从源码取证。`showHelp()` 原文：『Usage: nxlink [options] nrofile』『--help,    -h   Display this information』『--address, -a   Hostname or IPv4 address of Switch』『--retries, -r   number of times to ping before giving up』『--path   , -p   set upload path for file』『--args          args to send to nro』『--server , -s   start server after completed upload』。用途：经 netloader 把 NRO 上传到真机运行，`-s` 在上传后启动服务器接收 NRO 的 stdout/stderr——这是本集群里唯一可脚本化采集「退出码/控制台日志」的开发期通道
- 未验证: 未在真机/模拟器运行 nxlink；Switch 端 netloader/homebrew 环境（如 nx-hbmenu netloader）版本未验证；devkitPro 包管理分发渠道未核实（pkg.devkitpro.org 被 Cloudflare 403、libnx.devkitpro.org TLS 失败，故以 GitHub 源码为准）
- 风险: ①README 为空、无文档，行为需按源码确认；②2024-10 后无提交；③需要 Switch 侧 netloader 环境，真机测试前置条件多；④只做开发加载，不参与 NSP 打包/安装，不能替代 nstool/hacBrewPack；⑤devkitPro 官方分发包未验证，若需预编译二进制要靠自家构建
- 来源 URLs: https://api.github.com/repos/switchbrew/switch-tools · https://api.github.com/repos/switchbrew/switch-tools/tags?per_page=100 · https://raw.githubusercontent.com/switchbrew/switch-tools/master/COPYING · https://raw.githubusercontent.com/switchbrew/switch-tools/master/Makefile.am · https://raw.githubusercontent.com/switchbrew/switch-tools/master/src/nxlink.c · https://raw.githubusercontent.com/switchbrew/switch-tools/master/README · `git ls-remote https://github.com/switchbrew/switch-tools`

### 6. autorunhq/autorun

- URL: https://github.com/autorunhq/autorun（描述 `Play Windows PC games on your Nintendo Switch.`）
- 默认分支 / HEAD: `main`；HEAD `1ac9b6cf37b90f2d5783dd7ef389bebbe1c68877`（2026-10-16，提交信息 `horizon-dlls: README with Autorun's header and what the files are, and aren't.`）；pushed_at 2026-10-16T18:18:50Z
- 最近 tag: `test-build-4` = `9b7170505f9084fee0ffe1a237b08557a6ab2868`（commit 2026-09-23T23:29:36Z `Autorun: Build the x86 runtime with USB storage.`；Release 发布于 2026-09-24T10:59:45Z，资产 `autorun-test-build-4.zip` 64978068 B）；历史：test-build-3 `f86a318ecaaf`（2026-09-19，`autorun-test-3.zip` 61408112 B）、test-build-2 `1bc4e45163f0`（2026-09-15，`wine-test-build-2.zip` 81519917 B + `sphaira-32bit-forwaders.nro` 5059009 B）。**无稳定版**，只有 3 个测试构建
- 许可证: GitHub /license 返回 `NOASSERTION`（Other）；根 `LICENSE`（824 B）为 Wine 的 LGPL-2.1-or-later 声明（Wine project authors，指向 `COPYING.LIB` 26434 B），本仓库是 Wine 11.18 的 fork；`NOTICES.md`（67272 B）收录 Wine 引入的第三方声明。README Credits 表逐组件标注许可：Wine LGPL-2.1-or-later、FEX MIT、Box64 MIT、DXVK zlib/libpng、VKD3D-Proton LGPL-2.1-or-later、Mesa/mesa-switch MIT(mostly)、LSFG-VK GPL-3.0-or-later、libusbhsfs ISC、Atmosphère/Horizon-OC GPL-2.0、libnx(devkitPro) ISC、SDL2/SDL2_ttf/FreeType/HarfBuzz/libpng/zlib 等。再分发义务：LGPL/GPL 组件需附许可文本并提供对应源码（Wine/Atmosphère/Horizon-OC/LSFG-VK），保留 NOTICES/AUTHORS；不存在单一 SPDX 能代表整包
- 健康: archived=false；最后 push 2026-10-16；stars 525；open issues 62；主语言 C；README 自述 experimental
- 构建系统 / 技术栈（从 README 与构建脚本取证）: `VERSION` 文件内容『Wine version 11.18』；Horizon 侧在 `horizon-wine/` 用 CMake + Ninja 构建 runtime NRO，两套 runtime：①x86 runtime = WoW64 + Box64 dynarec + mesa-switch（`build-x86.sh`，CMake 选项 `-DWINE_NX_BOX64_DYNAREC=ON -DWINE_NX_USB_STORAGE=ON`，产物 `wine-nx-runtime-nro`，在 Docker `switch-dev` 镜像内用 llvm-mingw 工具链 `llvm-mingw-20260505-ucrt-*` 交叉编译）；②AMD64 runtime = FEX（`build-amd64-components.sh`，`--enable-archs=aarch64,arm64ec,i386`、`--enable-winebox64=aarch64 --enable-winebox64ec=arm64ec`）。Box64 固定 revision `2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a`（`bootstrap-box64-core.sh` 中 `git fetch --depth=1 origin $revision` 并校验工作区干净）。`horizon-wine/README`：Windows DLL 不在本仓，来自 `horizon-dlls` 子模块，运行时校验 manifest `runtime-interfaces.json` 匹配后才启动；`horizon-dlls`、`game-fixes` 为 git submodule。`.gitlab-ci.yml` 仅定义 stages（232 B），无实际 job 内容
- 关键依赖（README 组件表）: FEX（x86/x64 翻译，来自 FEX-Emu/FEX）、Box64（32 位第二翻译器）、Mesa 26 / mesa-switch（OpenGL nvc0 + Vulkan NVK）、DXVK（D3D8–11）、VKD3D-Proton（D3D12）、LSFG-VK 帧生成（需自备 Lossless Scaling）、libusbhsfs（USB 存储）、Atmosphère/Horizon-OC（启动改动）、SDL2 系启动器
- README 声称: 在 Switch（Horizon OS）上跑 Windows 游戏：『> **Autorun is experimental.** Some games run well, many start and then stop on something that isn't done yet. Every run writes a log that says where. A game compatibility list is coming.』；需要 CFW(Atmosphère)、microSD、约 200 MB DLL、游戏的 Windows 安装目录；安装为解压 `autorun-NNN.zip` 到 SD 根（内容全部进 `switch/wine`），Quick setup 会把入口放到 HOME 菜单、下载 DLL、安装 boot changes（Mesosphere 低内存地址 + stock loader 或 Horizon-OC）；USB 盘显示为 D:–H:；单进程 Wine 限制；『## Not a piracy or circumvention tool』，不支持盗版/破解/第三方整包。所有『能跑游戏』均为项目自述，本审计未验证任何游戏
- 未验证: 未下载/运行 test-build ZIP；未核对 `autorun-NNN.zip` 内容与 README 是否一致；兼容性列表尚不存在；`horizon-wine/README` 所述 manifest 校验逻辑未实测；GitLab CI 实际构建配置不可见
- 风险: ①实验性、无稳定发布，仅 3 个测试构建；②需 CFW + Mesosphere 低地址启动改动（stock loader 或 Horizon-OC），安装门槛与合规风险高；③单进程 Wine，依赖商店客户端/反作弊/在线登录的游戏不可运行；④依赖自备游戏目录，NSP 不自包含游戏数据；⑤许可为 NOASSERTION，整包再分发需逐组件满足 LGPL/GPL；⑥构建链复杂（Docker switch-dev + llvm-mingw + 多 submodule + 多 patch），复现成本高；⑦项目鼓励只从官方渠道获取运行时，第三方重打包不可信
- 来源 URLs: https://api.github.com/repos/autorunhq/autorun · https://api.github.com/repos/autorunhq/autorun/tags?per_page=100 · https://api.github.com/repos/autorunhq/autorun/releases?per_page=20 · https://raw.githubusercontent.com/autorunhq/autorun/main/README.md · https://raw.githubusercontent.com/autorunhq/autorun/main/VERSION · https://raw.githubusercontent.com/autorunhq/autorun/main/LICENSE · https://raw.githubusercontent.com/autorunhq/autorun/main/COPYING.LIB · https://raw.githubusercontent.com/autorunhq/autorun/main/NOTICES.md · https://raw.githubusercontent.com/autorunhq/autorun/main/horizon-wine/README.md · https://raw.githubusercontent.com/autorunhq/autorun/main/horizon-wine/tools/bootstrap-box64-core.sh · https://raw.githubusercontent.com/autorunhq/autorun/main/build-x86.sh · https://raw.githubusercontent.com/autorunhq/autorun/main/.gitmodules · `git ls-remote https://github.com/autorunhq/autorun`

### 7. autorunhq/autorun-horizon-dlls

- URL: https://github.com/autorunhq/autorun-horizon-dlls
- 默认分支 / HEAD: `main`；HEAD `67e2303dee9191b7ce4e2d1ccb47957d15c8a98b`（2026-10-16，提交信息 `README: Autorun's header, and not a piracy or circumvention tool`）；pushed_at 2026-10-16T18:18:47Z
- 最近 tag: `dlls` = `4ab914bb4f7ffd35753934c02ecde05eed23a50f`（commit 2026-09-28T11:43:20Z；Release 发布于 2026-09-28T11:53:27Z，资产 `horizon-dlls.tar.zst` 88439006 B、`horizon-dlls.zip` 203013347 B）
- 许可证: 无根 LICENSE（`/license` 404）。`NOTICE.md`（65295 B）给出文件来源与逐组件许可表，`LICENSES/` 收录各组件全文：Wine LGPL-2.1-or-later、FFmpeg LGPL-2.1-or-later、vkd3d LGPL-2.1-or-later、mpg123 LGPL-2.1-only、FluidSynth LGPL-2.1-or-later、Capstone BSD-3-Clause、compiler-rt NCSA OR MIT、FAudio Zlib、libjpeg IJG、jxrlib BSD-2-Clause、Little CMS MIT、OpenLDAP OLDAP-2.8、musl MIT、libpng Libpng、SQLite blessing、SymCrypt MIT、libtiff、libxml2/libxslt MIT、zlib、DXBC-SPIRV/DXIL-SPIRV、DXVK-zlib 等。NOTICE 开头：『Built from Wine 11.18 as carried by https://github.com/autorunhq/autorun at commit 97422507a2bc8100c6ba32a13828109a340e9131. The source of every file is there, under the paths its manifest entry lists.』；再分发须保留 NOTICE/LICENSES 并遵守各 LGPL 组件的源码提供义务
- 健康: archived=false；最后 push 2026-10-16；stars 8；open issues 0；主语言 Python（构建脚本）；创建于 2026-09-25（新仓库）
- 构建系统 / 关键依赖: Python 脚本从 Wine 11.18 源码构建 Windows 侧模块（`tools/build-dlls.py`，另有 `build-dxvk.py`、`build-fex.sh`、`build-vkd3d.py` 及 `*_payload.py`）。产物按 SD 卡布局：`switch/wine/drive_c`（ARM64X system32 + i386 syswow64）、`switch/wine/horizon-dlls`（manifest + `classes.reg`）、`compressed/`（zlib 压缩副本，供 Autorun 增量下载）。每文件 manifest 条目含 version/size/SHA-256；附 PhysX 系统软件 9.13.0604（未修改）与开源 XLiveLess（替代已停服的 Games for Windows Live）
- README 声称: 『Every module a Windows game expects to find in system32 (ARM64X) and syswow64 (i386), built from Autorun's Wine, with FEX's CPU modules and the bundled DXVK and VKD3D-Proton』；Autorun 自动下载并保持更新（『nothing here needs to be copied by hand』），只传输字节有变化的文件；无网络时下载仓库 ZIP 解压 `switch/` 到 SD 根；release body：『Autorun downloads horizon-dlls.tar.zst itself for a card that has few of them』；明确『Not a piracy or circumvention tool』，不含 Microsoft 代码/游戏文件、不绕过 DRM
- 未验证: 未下载 release 资产核对 manifest 与实际文件的 SHA-256；未验证与 Autorun runtime 的接口匹配（`runtime-interfaces.json`）；PhysX/XLiveLess 的合规细节未展开
- 风险: ①无根 LICENSE，整体许可无法用单一 SPDX 表示，再分发必须逐文件遵守 NOTICE/LICENSES；②发行体积大（zip 203 MB / tar.zst 88 MB），若随 NSP 自包含打包会显著膨胀安装体积与安装时间；③内容与特定 Autorun runtime 接口绑定，版本不匹配时 DLL 被跳过导致游戏无法启动；④构建脚本生成而非逐文件人工审阅，完整性依赖 manifest 哈希清单；⑤仓库较新（2026-09-25 创建）、star 少，长期维护不确定
- 来源 URLs: https://api.github.com/repos/autorunhq/autorun-horizon-dlls · https://api.github.com/repos/autorunhq/autorun-horizon-dlls/releases?per_page=20 · https://api.github.com/repos/autorunhq/autorun-horizon-dlls/license · https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/README.md · https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/NOTICE.md · https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/tools/build-dlls.py · https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/tools/build-fex.sh · `git ls-remote https://github.com/autorunhq/autorun-horizon-dlls`

### 8. carafe-nx/carafe

- URL: https://github.com/carafe-nx/carafe（描述 `Desktop app that turns Windows games into Switch apps`）
- 默认分支 / HEAD: `main`；HEAD `3334ebc66e9bb2f6c12364a7b0b9a7472381fc3e`（2026-10-25，提交信息 `docs(roadmap): mark the v0.4.0 items done`）；pushed_at 2026-10-28T21:02:24Z（最新维护中）
- 最近 tag: `v0.4.0` = `9b69701b8ae885126b09cf2ccdddef1eccee9732`（commit 2026-10-25T08:01:52Z；Release 发布于 2026-10-25T08:34:35Z，资产 `Carafe_0.4.0_arm64-setup.exe` 227864387 B、`Carafe_0.4.0_x64-setup.exe` 228142873 B、`latest.json` 2594 B、`SHA256SUMS.txt` 188 B）。历史 tag：v0.3.1 `2d20b774`、v0.3.0 `6738c2ac`、v0.2.4 `97cc14d2`、v0.2.3 `b14114ab`、v0.2.2 `4393f4da`、v0.2.1 `46ace025`、v0.2.0 `0ed4c962`、v0.1.1 `78b4fde9`、v0.1.0 `a8101574`
- 许可证: SPDX `GPL-3.0-or-later`；根 `LICENSE`（35149 B，GPLv3 全文）。README 分解：runtime overlay 与 Autorun patches 为 LGPL-2.1-or-later（`runtime/overlay/LICENSE`、`runtime/patches/LICENSE`），loader 为 ISC（`runtime/loader/LICENSE`），`external/` 内第三方各自许可；发行包捆绑 hacBrewPack（GPL-2.0）与 Autorun runtime（含 LGPL/GPL 组件），发行时须一并满足（源码提供、许可文本随附）
- 健康: archived=false；最后 push 2026-10-28；stars 253；open issues 9；主语言 Rust；ROADMAP 显示 v0.4.0 已完成的活跃项目
- 架构（README + docs/architecture.md 取证）: `app/` = Tauri 2（Rust core + React 19/TypeScript 7 UI）；`runtime/{loader,overlay,patches/autorun}` 为 Switch 侧 runtime（基于 Autorun 的 Wine + Box64/FEX + DXVK + Mesa）；`tools/hacbrewpack` 为打包工具（hacBrewPack v3.05 + Carafe patch）。任务编排（architecture.md）：①`carafe-folder` 读取游戏目录（列 exe/位数/产品名/公司/安装器/`steam_api.dll`）②向导③`carafe-core` 生成 `main.npdm`（TitleID + address space 39/32bit）、`control.nacp`（name/publisher/icon/save size）、`carafe/argv`、`carafe/title`、`carafe/icon.jpg`、`<exe>.keys.txt/.wine-nx.txt/.args.txt` ④预检（4× 游戏+runtime 空间、逐个 RomFS 路径长度，hacBrewPack Windows 上限 259 B）⑤在 `.carafe/build/<Title ID>` 组装（loader 作 ExeFS `main`、boot splash 作 logo）⑥hacBrewPack 建 Program/Control NCA，Carafe 自己写 NSP（NCAs + `carafe.json`，先 `.nsp.part` 后改名）⑦DBI MTP 安装。NSP 结构：ExeFS `main`+`main.npdm`；RomFS `switch/wine/{wine-nx-runtime.nro,prefix,DLLs,fonts,nls}` + `drive_c/Games/<folder>` + `carafe/`；Control 含 NACP + 每语言 icon（icon JPEG）；Logo 为 `NintendoLogo.png`/`StartupMovie.gif`；`carafe.json` 记录构建信息
- 元数据/打包细节（docs/nsp.md，高价值可复用证据）: hacBrewPack v3.05（`745b16e`，位于 `external/hacbrewpack`）、mbedTLS 2.6.1 打包在内、无其它依赖；hacBrewPack **就地修改输入**（`npdm.c:18,118`、`nacp.c:16,88,119`），故 Carafe 传副本；TitleID 须在 `0x0100…`–`0x0fff…`（`npdm.c:86-94`），>0x01ff… 仅警告；`--titleid` 只改 ACI0（`npdm.c:100`），Carafe 因此自行写三处、不传 `--titleid`；输出 `<titleid>.nsp`（`main.c:382`）；进度行『Writing <file> to <romfs>』（`romfs.c:441`）、失败『Failed to open <path>!』走 stderr（`romfs.c:437`）；RSA-PSS 随机盐导致两次构建 NSP header `0x100–0x1FF` 不同（非确定性构建）；patch 0001 修 `romfs.c:446-449` 缓冲 bug（2.2 GB RomFS 从 120 s 降到 27 s）；Windows `MAX_PATH` 259 B（`filepath.h:61-62`、`utils.h:23-25`、`filepath.c:34-41/141-153`），实测 258/259 成功、260/270 失败『Failed to stat』、230 字符含 50 西里尔（280 UTF-8 B）失败；`C:\Library` 前缀到 `Games\` 为 77 字符，故路径预算有限；`app/crates/carafe-core/src/path_limit.rs` 做预检 `pathTooLong`；另注意 `main(int argc, char** argv)` 走 Windows ANSI 代码页，非 ASCII 路径可能丢字符
- README 声称: 『desktop app that turns a Windows game folder into a standalone app for a Switch with custom firmware』；游戏进 NSP 后从 HOME Menu 启动，有自己的图标/存档/加载屏；runtime 是 Autorun（Wine + Box64/FEX + DXVK + Mesa）；需要 Atmosphère + sigpatches、DBI(MTP) 安装；Windows 10/11 x64/ARM64；安装包未签名（『not signed yet』）；GPL-3.0-or-later
- 测试方法证据（docs/testing.md，可用于 GalNX 测试环境设计）: 不使用模拟器 loop，全部真机测试；安装用 DBI MTP；日志在 `sdmc:/switch/carafe/<Title ID>/`：`carafe-overlay.log`、`logs/autorun_runtime.log`（含 `[CARAFE]` 行），保留最近 5 次（`X.log`…`X.5.log`，首行带日期时间）；loader 错误码 `2347-01xx`（101 sm、102 fs、103 heap、104 session、105 thread、106 receiving handle、107 no handle、108 unload .nro、109 path 不在允许范围等）；测试后保留屏幕照片/视频与日志。CI：`check.yml` windows-latest + Node 24 + Rust 1.99.0 跑 `npm run check` 与 bindings 差异检查；`release.yml` 校验 tag 形如 `^vX.Y.Z$`、用 docker compose 构建 runtime/hacBrewPack、tauri build（NSIS，未签名）、`gh release create` 上传安装包与 `SHA256SUMS.txt`/`latest.json`
- 未验证: 未运行 Carafe、未安装其 NSP；文档中的性能与路径上限数据（patch 0001 27 s/120 s、259 B）为 Carafe 自述，本审计未独立复现；未确认 Carafe 构建期是否需要用户自备 prod.keys（文档未列为要求，实际密钥来源未验证）；未验证 release 安装包与 `SHA256SUMS.txt` 的对应
- 风险: ①GPL-3.0-or-later——直接复制/派生其代码会使 GalNX 受 GPL 约束，只能参考设计与流程；②依赖 hacBrewPack（GPL-2.0）与 Autorun（实验性 runtime），打包链/兼容性风险继承上游；③Windows-only 桌面 app、安装包未签名；源码构建 runtime 需 Docker；④安装需 Atmosphère + sigpatches + DBI，属 CFW/签名补丁生态，合规与封禁风险与 forwarder 同源；⑤自包含路线体积 = 游戏 + runtime（数百 MB 到数 GB），SD 卡与安装时间需评估；⑥外部依赖通过 submodule/release 产物传递，必须锁定 submodule commit 与 runtime 版本
- 来源 URLs: https://api.github.com/repos/carafe-nx/carafe · https://api.github.com/repos/carafe-nx/carafe/tags?per_page=100 · https://api.github.com/repos/carafe-nx/carafe/releases/latest · https://raw.githubusercontent.com/carafe-nx/carafe/main/README.md · https://raw.githubusercontent.com/carafe-nx/carafe/main/LICENSE · https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/architecture.md · https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/nsp.md · https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/testing.md · https://raw.githubusercontent.com/carafe-nx/carafe/main/runtime/Makefile · https://raw.githubusercontent.com/carafe-nx/carafe/main/.github/workflows/check.yml · https://raw.githubusercontent.com/carafe-nx/carafe/main/.github/workflows/release.yml · https://raw.githubusercontent.com/carafe-nx/carafe/main/compose.yaml · `git ls-remote https://github.com/carafe-nx/carafe`

### 9. Ryujinx 源流与版本对应（网页侧旁证；结论由 Lead 定稿）

- 目标 URL 与状态: 官方 Canary 源 `https://git.ryujinx.app/Ryubing/Canary`（由 Ryubing/UpdateServer 元数据证实，见下）**本次不可达**：DNS 解析 91.239.78.255，curl schannel TLS handshake failed、直连 20 s 超时、python SSL `UNEXPECTED_EOF_WHILE_READING`、http 经代理 502。`https://gitlab.hugofnm.fr/publicmirrors/Ryujinx` **匿名不可达**：`/api/v4/version` 401、`/api/v4/projects/publicmirrors%2FRyujinx` 404 `{"message":"404 Project Not Found"}`、`/api/v4/groups/publicmirrors/projects` 404、网页 `/publicmirrors/Ryujinx` 及其 `/-/tags` 404（实例本身有其它公开项目，故为项目不可见/需登录/路径不存在，而非实例宕机）
- 官方版本命名/更新源证据（Ryubing/UpdateServer，可达）: 仓库 https://github.com/Ryubing/UpdateServer（default `main`；stars 30；pushed_at 2026-08-26；无 license 文件）。`src/Server/appsettings.json`：Forgejo Endpoint = `https://git.ryujinx.app/`；`VersionCacheSources.Stable.Project = projects/Ryubing`；`VersionCacheSources.Canary.Project = Ryubing/Canary`，`Canary.DeriveLatestVersionManually = true`；端点 `/latest/query`、`/download/*`、`/api/v1/meta`、`/api/v1/admin/refresh_cache`、`/api/v1/versioning/*`；`MaxConcurrentDownloads = 1`。`src/Common/Enums/ReleaseChannel.cs`：`Stable, Canary, Custom1, KenjiNX`；`src/Common/Constants.cs`：StableRoute=`stable`、CanaryRoute=`canary` 等路由。`VersionCacheEntry` 字段含 tag/web_url/downloads{macOS,windows{x64,arm64},linux,linux_appimage}。→ **Canary 版本 tag 由 Forgejo 项目 `Ryubing/Canary` 产生**，Canary 版本与 commit 的权威对应只能从该 Forgejo 取；本次取不到
- github.com/Ryujinx 组织状态: `https://api.github.com/orgs/Ryujinx` → public_repos=1、followers=45、created_at 2024-12-30T16:18:39Z、is_verified=false；唯一仓库 `Ryujinx/.github`（default `main`，pushed 2024-12-31T00:10:45Z，仅 profile 内容）→ GitHub 上**已无官方模拟器源码仓库**
- Ryubing 组织状态: id 192939710、created_at 2024-12-27、public_repos=11、followers=4574、blog https://ryujinx.app、描述 `A fork of the discontinued Switch emulator, Ryujinx.`；11 个仓库为 UpdateServer、RyujinxHelper、Website、Compatibility、Assets、LdnServer、docs、Issues、LdnWebsite、Nfc、Ryuko，**无模拟器源码仓库**；`Ryubing/ryujinx` 返回 404 `{"message":"Not Found"}`（已删除/私有）
- 镜像状态: `ryujinx-mirror/ryujinx` 返回 **451** `{"message":"Repository access blocked","block":{"reason":"dmca","created_at":"2025-03-14T13:47:59Z","html_url":"https://github.com/github/dmca/blob/master/2025/03/2025-03-06-nintendo.md"}}`（任天堂 2025-03-06 DMCA 投诉）；该组织另有 ryujinx-games-list、unstable-commands（均 archived）。GitHub 搜索 `Canary-1.3.265` total=0；`ryujinx`+`canary` total=5
- 版本命名序列旁证（非权威）: `ewigl/ryubing-canary-mirror`（desc `Mirror of the Ryubing/Ryujinx Canary Windows x64 releases. For personal use only. Ryubing's official download service is currently down, so no updates until it's back.`；default `master`；pushed 2026-10-25）HEAD `e87e314ec4e5a08cc5689ae272d7d8d1db711a96`，tag `1.3.340`=`579794fc818f`、`1.3.341`=`8740477230d0`、`1.3.349/350/351`=`250158e9fb82`；Wayback CDX 有 `git.ryujinx.app/Ryubing/Canary/releases` 快照（2026-04-12 等）与 release 下载 URL（如 `.../releases/download/1.3.201/ryujinx-canary-1.3.201-linux_arm64.tar.gz`）→ Canary 采用 `1.3.x` 命名，1.3.265 属同一序列；该 mirror 从 1.3.340 起，**不含 1.3.265**，无法提供其 commit
- Canary-1.3.265 的归属与精确 commit（本审计可给出的结论）: ①版本命名体系来自 Ryubing 的官方 Forgejo（`git.ryujinx.app/Ryubing/Canary`），`1.3.265` 是该序列的 Canary 版本号；②本次无法从网络独立取得 `Canary-1.3.265` tag 的 40 位 commit SHA 与日期（GitLab hugofnm 镜像 404、git.ryujinx.app TLS 不可达），故**不填 SHA、不猜**，标 not-verified；③Lead 本机取证为二进制 ProductVersion=`1.3.265+4e81a4c`、同目录源码 zip Comment=`4e81a4c2f4fee6f31e28fbb129759ec2369da6eb`，两者前缀一致，可自洽地认定该二进制对应源码 commit `4e81a4c2f4fee6f31e28fbb129759ec2369da6eb`（此结论由 Lead 定稿并记入其报告，本条目只做旁证）；④`4e81a4c2` 开头与 Lead 待核实的 SHA 前缀一致，但**本审计无独立网页证据**证明该 commit 是 `Canary-1.3.265` 而非其它 1.3.x
- 官方/分支/镜像三者关系与可信度: ①官方历史：Ryujinx 于 2024-10 停止开发、GitHub 官方仓库随后下线（`github.com/Ryujinx` 仅剩 profile 仓库，2024-12-30 创建组织、2024-12-31 后无动态）；②分支：Ryubing 接续开发 Canary/Stable 渠道，源码与发行都迁移到自建 Forgejo `git.ryujinx.app`，GitHub 上的 Ryubing 组织只有配套服务仓库（UpdateServer/Website/Compatibility 等），没有源码；③镜像：GitHub 的 ryujinx-mirror 已被任天堂 DMCA 屏蔽（451），不可作为可信/长期来源；ewigl mirror 仅镜像 Windows x64 release 且从 1.3.340 起，属第三方个人镜像。可信度排序：本机留档的官方二进制+源码 zip（可校验 SHA-256）> 官方 Forgejo（当前不可达）> 第三方 mirror（不可复核）> Wayback 快照（只可作命名旁证）
- 本机源码复现需要什么: ①保留当前二进制与源码 zip，记录两者的 SHA-256 与文件大小，并把 ProductVersion/zip Comment 写进构建记录（Lead 已做）；②源码 zip 内应有 `4e81a4c2…` 对应的完整树；复现构建还需 .NET SDK（Ryujinx 用 .NET 8，本次未验证具体版本）、子模块（mbedtls/SDL2 等）与 `Directory.Build.props` 等，因源码资产不在网页可达范围，本审计不臆测具体依赖；③禁止自动更新（UpdateServer 的 canary 端点会拉最新版），测试环境应断网或屏蔽 `update.ryujinx.app`/`git.ryujinx.app`
- 未验证: Canary-1.3.265 的 tag SHA/日期（两路均失败）；官方 Forgejo 仓库可达性；本机源码 zip 内容与 commit 一致性（Lead 侧）；Ryujinx 构建所需的 .NET/子模块版本
- 风险: ①官方源与 GitLab 镜像均不可达，Canary-1.3.265 无法在线复核，长期可复现性依赖本机留档；②DMCA 风险使 GitHub 镜像不可靠，任何依赖 GitHub 镜像的 CI 会随时 451；③update.ryujinx.app/git.ryujinx.app 若恢复，版本与 commit 对应可能漂移，必须禁止自动更新并用哈希锁定；④Ryujinx 本身的法律风险（模拟器/密钥）需在 GalNX 边界内隔离，测试资产不得含固件/密钥
- 来源 URLs: https://api.github.com/orgs/Ryujinx · https://api.github.com/repos/Ryujinx/.github · https://api.github.com/orgs/Ryubing · https://api.github.com/users/Ryubing/repos?per_page=100 · https://api.github.com/repos/Ryubing/UpdateServer · https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Server/appsettings.json · https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Common/Enums/ReleaseChannel.cs · https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Common/Constants.cs · https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Common/Models/VersionCacheEntry.cs · https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Common/Models/VersionResponse.cs · https://api.github.com/repos/ryujinx-mirror/ryujinx（451 DMCA）· https://api.github.com/repos/ewigl/ryubing-canary-mirror · https://web.archive.org/cdx/search/cdx?url=git.ryujinx.app/Ryubing/Canary/releases&output=json&limit=5 · https://gitlab.hugofnm.fr/api/v4/projects/publicmirrors%2FRyujinx（404）

## 未验证 / 失败项

### 硬失败（未能取得数据，已按要求不推测）

1. **gitlab.hugofnm.fr/publicmirrors/Ryujinx 匿名不可达**：`/api/v4/version` → 401；`/api/v4/projects/publicmirrors%2FRyujinx` → 404 `404 Project Not Found`；`/api/v4/groups/publicmirrors/projects` → 404；网页 `/publicmirrors/Ryujinx`、`/-/tags` → 404。→ Canary-1.3.265 tag 的 commit SHA 与日期未验证（影响条目 9）。
2. **git.ryujinx.app 官方 Forgejo 不可达**：DNS→91.239.78.255，curl schannel handshake failed、直连 20 s timeout、python SSL `UNEXPECTED_EOF_WHILE_READING`、http 经代理 502。→ 官方 Canary 仓库/标签未直接验证。
3. **update.ryujinx.app TLS 握手失败**（Lead 实测；本审计未重复调用）→ 官方更新 API 未验证。
4. **github.com/Ryujinx 无可审计的模拟器源码**：public_repos=1（仅 `.github` profile）；`Ryubing/ryujinx` 404；`ryujinx-mirror/ryujinx` 451 DMCA；GitHub code search `Canary-1.3.265` total=0。

### 未能取证/仅部分取证

1. `/license` 为 404 或 null 的仓库：TooTallNate/switch-nsp-forwarder（仅 package.json MIT 声明）、autorunhq/autorun-horizon-dlls（仅 NOTICE/LICENSES）、Ryubing/UpdateServer（无 license）；已按实际原文判断，未以 SPDX 猜测。
2. devkitPro 的 switch-tools/nxlink 分发渠道未验证（pkg.devkitpro.org 403、libnx.devkitpro.org TLS 失败、pacman-packages raw 404），以 switchbrew/switch-tools 源码为准。
3. 未下载任何 release 二进制/压缩包（nstool win_x64、NTON installer、autorun test-build、horizon-dlls、Carafe installer），体积/内容/哈希未复核；本轮不安装不执行。
4. 未实测 prod.keys 机制：仅从 NTON/hacBrewPack README 记录机制描述，未读取、未使用任何密钥。
5. 未在真机/模拟器运行任何工具或 NSP；README 的可用性主张均为「README 声称」。
6. nstool `deps/` 子模块（mbedtls/fmt/libtoolchain/lz4/libpietendo）的精确版本未逐个子模块抓取。
7. Ryujinx 构建依赖（.NET SDK 版本、子模块）未验证，因源码不在可达范围。
8. Carafe 构建期是否需用户自备 prod.keys 未验证（文档未列为要求，实际机制不明）。

## 附录 A：NSP 打包路线能力矩阵（forwarder vs 自包含）

| 维度 | A. forwarder（NTON / switch-nsp-forwarder 模板） | B. 自包含（hacBrewPack + 自有编排；Carafe 为参考实现） |
| --- | --- | --- |
| NSP 内实际内容 | 仅 launch stub（forwarder ROM），NRO 仍在 SD 卡上被硬编码路径调用 | ExeFS 启动器（loader/runtime NRO）+ RomFS 内的全部游戏数据与 runtime |
| 安装体积 | README 声称约 1 MB（NTON Features） | 游戏 + runtime，数百 MB 到数 GB（Carafe 预检按 4× 游戏 + runtime 预留空间） |
| 所需输入 | NRO 文件；`prod.keys`；标题名/发布者/版本/图标（NTON 自动从 NRO 提取）；TitleID（随机或 `--id`） | `build/exefs/main` + `main.npdm` + `control.nacp` + 图标（256×256 JPEG）+ logo（可省）+ RomFS；`prod.keys` |
| 密钥机制 | 生成 NSP 时需 `prod.keys`（由 Lockpick_RCM 从自有 Switch 提取），NTON 从 `C:\Users\<User>\.switch\prod.keys`、cwd 或安装目录读取；不掌握任天堂私钥，forwarder 签名无效，需 CFW + sigpatches 才能运行（README 原文） | hacBrewPack 需 `header_key` 与 `key_area_key_application_xx`（keys.dat/keys.txt/keys.ini/prod.keys，机制描述见 README）；同样无任天堂私钥，NSP/NCA 无法通过官方签名校验，安装需 Atmosphère + sigpatches（Carafe README 要求） |
| 依赖链 | NTON v3.0.1（GPL-3.0）内部调用 hacBrewPack v3.05（GPL-2.0）+ nstool v1.9.2（MIT）+ hptnacp/hacPack（GPL-2.0）+ switch-nsp-forwarder ROM（MIT 声明） | hacBrewPack v3.05 + nstool v1.9.2 + 自有元数据生成（NPDM/NACP 可由代码生成，借鉴 Carafe 的 carafe-core）+ runtime（仅当做 Windows 游戏兼容时） |
| 优点 | 体积小、构建快、无需改动游戏数据；NTON 现成 CLI/GUI，`--id` 可固定 TitleID | 一次安装即自带游戏数据，不依赖 SD 卡上额外 NRO 路径，符合「Galgame 移植」的发行形态；可完全控制图标/名称/存档 |
| 风险 | ①README 明示安装 forwarder 可能封禁主机；②任天堂已 DMCA 运行此类 NSP 的方案；③NRO 路径硬编码，移动 SD 卡/换机即失效；④TitleID 随机可能冲突；⑤NRO 仍暴露在 SD 卡上 | ①体积大、打包耗时长（Carafe patch 前 2.2 GB RomFS 需 120 s，patch 后 27 s）；②Windows 路径 259 B 上限需预检；③hacBrewPack 就地修改输入、输出 NSP 非确定性（RSA-PSS 随机盐）；④GPL 义务与 CFW/签名补丁依赖；⑤无 emulator 测试循环，只能真机验证 |
| 关键证据 | NTON README（CAUTION/Troubleshooting/Licensing）、switch-nsp-forwarder CHANGELOG | carafe docs/architecture.md、docs/nsp.md、docs/testing.md、hacBrewPack README、Carafe release 产物 |
| 对 GalNX 的定位 | 只作为对照实验/演示，不进入 v0.1 主链 | v0.1 主链方向；但打包内核锁定 hacBrewPack v3.05，编排层自研（不直接派生 Carafe 代码，避免 GPL 传染） |

结论：GalNX 若目标是「Galgame 进 NSP、点图标即玩」，必须走自包含路线；forwarder 路线只解决启动器，不解决发行体与数据合规，且封禁/DMCA 警示最高，可作为最小的端到端验证（先证明产物能被 nstool 校验、能安装），不作为交付形态。

## 附录 B：工具版本锁定建议与集成顺序

### B1. 版本锁定表（全部来自本次实际抓取）

| 组件 | 锁定版本 | 精确 commit | 许可证 | 角色 |
| --- | --- | --- | --- | --- |
| jakcron/nstool | v1.9.2（2024-10-14） | `e89ea84bd70c11b67ebec9153fb4a446f18a9d3d` | MIT | 产物检查/校验/提取（第 1 步接入） |
| rlaphoenix/hacBrewPack | v3.05（2019-10-13 提交） | `745b16ecfc9ce055743067d200572204cb2aac6c` | GPL-2.0 | NSP/NCA 打包内核（子进程调用） |
| rlaphoenix/NTON | v3.0.1（2026-09-15） | `c5d543a91b7cd1df880f98c9ab831be9a40d024f` | GPL-3.0 | forwarder 对照实验（非主链） |
| TooTallNate/switch-nsp-forwarder | 0.0.8（2026-05-03） | `61edd504e57c6007f23a3a242b386ac0372c0cee` | 无根 LICENSE；package.json MIT | ROM 模板参考 |
| switchbrew/switch-tools（nxlink） | v1.13.1（2024-10-23） | `22756068dd0ed6ff9734c59cb4f99ebd3f62555b` | ISC | 开发期 NRO 热加载/日志 |
| carafe-nx/carafe | v0.4.0（2026-10-25） | `9b69701b8ae885126b09cf2ccdddef1eccee9732` | GPL-3.0-or-later | 设计参考（不引入代码） |
| autorunhq/autorun | test-build-4（2026-09-24） | `9b7170505f9084fee0ffe1a237b08557a6ab2868` | NOASSERTION | 参考（不纳入 v0.1） |
| autorunhq/autorun-horizon-dlls | dlls（2026-09-28） | `4ab914bb4f7ffd35753934c02ecde05eed23a50f` | NOASSERTION | 参考（不纳入 v0.1） |

### B2. 集成顺序（nstool → hacBrewPack → 自有编排 → NTON 仅参考）

1. **nstool v1.9.2**：先接只读检查链。用 `nstool -y` 校验 NSP/XCI/NCA 签名结构、`nstool --showlayout` 看分区、`nstool -x` 提取核对；不需要 keys、不改产物。可先固化 CI 脚本：对每个构建产物输出 `nstool -y <file>` 的退出码与 stderr。
2. **hacBrewPack v3.05**：作为独立子进程调用（不链接），输入必须是副本（源码会就地修改输入：`npdm.c:18,118`、`nacp.c:16,88,119`）；Windows 下预检每个 RomFS 路径 ≤259 B（Carafe 实测 258/259 成功、260 失败）；捕获 stdout/stderr，解析进度行『Writing <file> to <romfs>』与失败『Failed to open <path>!』；输出 NSP 后再次交给 nstool 校验。
3. **自有编排层（GalNX）**：借鉴 Carafe 的流程而不复制其 GPL 代码——目录扫描 → 元数据（name/publisher/icon/save size/TitleID/argv）→ 预检（空间、路径长度）→ 组装 `.build/<TitleID>` → 调 hacBrewPack 生成 NCA → 自行写 NSP（参考 Carafe 的 `.nsp.part` 原子改名做法）→ 产物哈希 + nstool 校验 → 安装（MTP/DBI 或 forwarder 方案）。
4. **NTON v3.0.1 仅作对照**：用同一 NRO 生成 forwarder，对比安装体积、启动链、封禁警示与可维护性；不把它作为 GalNX 发行路径。
5. **nxlink v1.13.1**：开发内循环可选，用于把 NRO 推到真机并回收 stdout/stderr（`-s` 服务器模式），不能用于 NSP 安装。

### B3. 阻塞项/前置条件

1. **密钥合规**：hacBrewPack/NTON 都需要用户自有 `prod.keys`；GalNX 仓库与 CI 不得包含/分发任何密钥，测试机密钥路径也不应写入产物。
2. **签名补丁与 CFW**：两条路线的产物都无任天堂签名，安装需 Atmosphère + sigpatches；这是环境前置而非代码问题，但决定了测试流程与用户门槛，需要产品层面明确「用户自备 CFW 环境」。
3. **DMCA/封禁风险**：NTON README 明示封禁可能；任天堂已对可运行未签名 NSP 的方案 DMCA。GalNX 应避免分发任何可绕过签名的组件，并在文档中明确合规边界。
4. **Ryujinx 测试环境不可在线复现**：官方源/gitlab 镜像不可达，只能依赖本机留档（见附录 C）；CI 不能拉取 Ryujinx。
5. **GPL 传染**：hacBrewPack(GPL-2.0) 以子进程聚合可接受；Carafe(GPL-3.0-or-later)/Autorun 的 GPL 组件不可直接并入闭源或不同许可的代码。

## 附录 C：测试环境固定方案（Ryujinx 版本/commit + 日志/退出码采集）

### C1. Ryujinx 版本固定（依据 Lead 已取证的本机事实）

1. 版本标识：本机 exe ProductVersion = `1.3.265+4e81a4c`；同目录源码 zip 的 Comment = `4e81a4c2f4fee6f31e28fbb129759ec2369da6eb`。二者前缀一致，固化为「Ryujinx Canary 1.3.265 / commit `4e81a4c2f4fee6f31e28fbb129759ec2369da6eb`」；网页侧无法独立复核（见条目 9），此条目标注为 Lead 取证结论。
2. 留档：把 exe、源码 zip、本审计/Lead 报告一起放入只读目录，记录每个文件的 SHA-256、字节数、抓取日期；构建/测试脚本启动前先校验哈希，不一致即拒绝运行（文件级锁定而非版本号字符串）。
3. 断网锁定：屏蔽 `update.ryujinx.app`、`git.ryujinx.app`（hosts 或防火墙），避免自动更新把 1.3.265 升走；UpdateServer 元数据证明官方 Canary 渠道由 `git.ryujinx.app/Ryubing/Canary` 提供（多版本端点 `/latest/query`、`/download/*`）。
4. 记录字段建议（JSONL，每条测试一行）：`date, emulator=ryujinx, version=1.3.265, commit=4e81a4c…, exe_sha256, source_zip_sha256, title_id, nsp_sha256, install_mode, exit_code, log_path, screenshot_path, result`。

### C2. 日志与退出码采集（本集群可用的证据）

1. **开发期（NRO 热加载）**：switchbrew/switch-tools 的 nxlink 支持 `-s/--server` 在上传完成后启动服务器接收 NRO 的 stdout/stderr（`src/nxlink.c` showHelp 原文），主机侧 TCP 端口 28280/28771；可用它把运行时日志直接回传到 PC 并落盘。
2. **NSP 安装后的真机日志（参考 Carafe 的成熟做法）**：日志目录 `sdmc:/switch/carafe/<Title ID>/`，包含 `carafe-overlay.log` 与 `logs/autorun_runtime.log`（带 `[CARAFE]` 标记行），保留最近 5 次启动日志（`X.log`…`X.5.log`，首行写日期时间）；loader 错误码 `2347-01xx`（101 sm、102 fs、103 heap、104 session、105 thread、106 receiving handle、107 no handle、108 unload .nro、109 path 不在允许范围等）。GalNX 可照此设计自己的日志目录与错误码表，但不要复制其 GPL 代码。
3. **模拟器侧（Ryujinx）**：本审计未验证 Ryujinx 的日志文件路径与命令行开关（官方文档不可达），因此采用外部 wrapper 采集——启动时重定向 stdout/stderr 到文件、等待进程结束记录退出码、同时记录 exe 哈希；wrapper 逻辑与日志路径需 Lead 在本机按实际版本确认后固化。
4. **安装通道**：Carafe/testing.md 用 DBI MTP 安装；本审计未验证 DBI 版本与 GalNX 目标环境兼容性。用 MTP 而非 SD 卡插拔可减少变量，并把安装结果（成功/失败/回滚）记为单独字段。
5. **不可自动化部分**：Carafe 明确「不使用 emulator loop，全部真机测试」；GalNX 的 NSP 安装/启动验证同样只能真机，模拟器只用于开发期 NRO 逻辑回归。测试记录必须保留屏幕照片/视频 + 日志（Carafe testing.md 的要求），否则无法区分「启动崩溃」与「画面异常」。

## 对 GalNX 的建议（版本锁定、接入顺序、阻塞项）

### 1) 版本锁定

- **主链锁定**：nstool `v1.9.2`（`e89ea84bd70c11b67ebec9153fb4a446f18a9d3d`，MIT）、hacBrewPack `v3.05`（`745b16ecfc9ce055743067d200572204cb2aac6c`，GPL-2.0，子进程调用）。锁定依据：两者都是当前唯一可用的成熟组合，且 Carafe 已在生产中使用同一 hacBrewPack commit（`745b16e`）+ nstool 生态，交叉验证了可用性；但 hacBrewPack 代码停在 2019，需在 CI 中加「keys 代际/固件版本」回归用例。
- **参考锁定（不引入依赖）**：NTON `v3.0.1`、switch-nsp-forwarder `0.0.8`、Carafe `v0.4.0`、Autorun `test-build-4`、horizon-dlls `dlls`；其中 NTON 只用于 forwarder 对照，Carafe/Autorun 只用于设计参考与兼容性预期。
- **开发工具**：nxlink `v1.13.1`（ISC）用于真机 NRO 热加载；测试模拟器固定为 Ryujinx `1.3.265 / 4e81a4c2f4fee6f31e28fbb129759ec2369da6eb`（本机留档 + 哈希校验 + 断网）。
- **禁止浮动版本**：所有 GitHub Actions/脚本只允许 tag 或 40 位 SHA，禁止 `main`/`master`/`latest`；Ryujinx 禁止自动更新。

### 2) 接入顺序

nstool（只读校验）→ hacBrewPack（打包内核）→ 自有元数据/编排（借鉴 Carafe 流程）→ 产物 nstool 复核 + 哈希登记 → 真机安装（MTP/DBI）→ 启动日志采集（对照 Carafe 日志/错误码设计）。NTON/nxlink 只作为旁路验证工具，不进主链。

### 3) 阻塞项（需在写框架代码前解决/明确）

1. **密钥与合规边界**：确认 GalNX 不接受、不分发 `prod.keys`/固件/商业游戏数据；测试密钥只存在于测试机本地，CI 不注入（NTON CI 用 `secrets.PROD_KEYS`，GalNX 不应照搬）。
2. **签名补丁/CFW 前置**：两条打包路线产物均无官方签名，安装需 Atmosphère + sigpatches；产品文档必须把这一点写成用户侧前置条件。
3. **DMCA/封禁风险**：forwarder 路线有 README 明示的封禁警告与任天堂 DMCA 历史；若 GalNX 需要公开分发，应只做自包含路线并避免提供签名绕过组件。
4. **Ryujinx 可复现性**：官方源与 gitlab 镜像均不可达，必须依赖本机留档；若后续拿到 1.3.265 的官方 tag 证据，应回填条目 9 的 SHA 并更新附录 C。
5. **GPL 边界**：hacBrewPack(GPL-2.0) 子进程调用可接受；Carafe(GPL-3.0-or-later)/Autorun(LGPL/GPL 混合) 不可直接复制代码，只能参考设计与流程。
6. **路径长度**：Windows 下 hacBrewPack 受 259 B 限制，编排层必须在打包前预检（参考 Carafe `path_limit.rs` 的行为，自研实现），尤其是含非 ASCII 的 Galgame 路径。

## 机读数据

<!-- AUDIT-JSON-BEGIN -->
```galnx-audit
[
  {
    "name": "rlaphoenix/NTON",
    "url": "https://github.com/rlaphoenix/NTON",
    "default_branch": "master",
    "head_sha": "c5d543a91b7cd1df880f98c9ab831be9a40d024f",
    "head_date": "2026-09-15",
    "pinned": "v3.0.1 (annotated tag object 9587422b41e2ff22aec7fb0071a7d68249230a9c -> commit c5d543a91b7cd1df880f98c9ab831be9a40d024f, 2026-09-15; release published 2026-09-15T07:08:47Z)",
    "license_spdx": "GPL-3.0-only",
    "license_file": "LICENSE",
    "license_notes": "根 LICENSE = GPLv3 全文（35149 B，GitHub /license 返回 blob sha f288702d2fa16d3cdf0035b15a9fcbc552cd88e7），许可证文件路径 LICENSE；pyproject 声明 license=\"GPL-3.0-only\"，GitHub /license 归一为 GPL-3.0。捆绑再分发第三方二进制：hacBrewPack（GPL-2.0）、nstool（MIT）、hptnacp from hacPack（GPL-2.0）、switch-nsp-forwarder 的 rom（MIT），README Licensing 节称『No changes were made ... copies of their licenses can be found next to their binaries within the bin folder』。",
    "archived": false,
    "last_push": "2026-10-24",
    "stars": 245,
    "open_issues": 8,
    "build_system": "Python >=3.10（hatchling 构建，uv.lock/uv 管理）；GUI 用 PySide6-Essentials；发行用 PyInstaller + Inno Setup（setup.iss、make.bat/make.sh、pyinstaller.py）；CI windows-latest 矩阵 Python 3.10/3.11/3.12/3.13/3.14（.github/workflows/ci.yml）；CD 在 v* tag 上 windows-2022 构建并发布 PyPI + GitHub Release（cd.yml）",
    "build_deps": "click~=8.5.0, requests~=2.34.2, jsonpickle~=4.1.2, coloredlogs~=15.0.1, beautifulsoup4~=4.15.0, lxml~=6.1.3, pillow~=12.3.0; gui: PySide6-Essentials~=6.11.2; pack: pyinstaller~=6.22.3; 运行需用户自备 prod.keys（Lockpick_RCM，路径 C:\\Users\\<User>\\.switch\\prod.keys / cwd / 安装目录）。CI 用 secrets.PROD_KEYS 生成测试 forwarder（sdl-hello.nro）",
    "readme_claims": "PC 端工具，构建直接启动 NRO 的 NSP 应用（『NSP application that launches right into an NRO file』），支持固件 12.0.0+；自动从 NRO 提取 Title/Publisher/Version/Icon；TitleID 随机分配并做冲突检查（可用 --id 覆盖）；1MB NSP 安装体积；forwarder 无存档/缓存需求，storage sizes 全部 0；需 prod.keys；CAUTION：『Installing these kinds of NSP files (NRO to NSP forwarders) can result in a console ban. This applies not just to this software but to all forms of NRO to NSP forwarder generators』；且 NSP 签名无效（无任天堂私钥），仅 CFW 不能启动，签名补丁被任天堂 DMCA；他人生成的 forwarder 很可能因 NRO 路径不同而无法工作（『using Forwarders others have created has a good chance of not working on your system』），即转发器不自包含 NRO",
    "readme_claim_url": "https://github.com/rlaphoenix/NTON/blob/master/README.md",
    "risks": [
      "安装/使用带来主机封禁风险（README 自述，覆盖所有 NRO->NSP forwarder 生成器）",
      "NSP 签名无效，需 CFW + 签名补丁；签名补丁途径已被任天堂 DMCA（README 自述）",
      "forwarder 只保存 NRO 路径引用，NRO 必须留在 SD 卡原路径，不属于自包含打包",
      "构建必须使用用户自备 prod.keys，禁止入库/分发密钥",
      "打包依赖 GPL-2.0 hacBrewPack 与 GPL-2.0 hptnacp 二进制，NTON 整体 GPL-3.0"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/rlaphoenix/NTON",
      "https://api.github.com/repos/rlaphoenix/NTON/tags?per_page=100",
      "https://api.github.com/repos/rlaphoenix/NTON/releases/latest",
      "https://api.github.com/repos/rlaphoenix/NTON/license",
      "https://raw.githubusercontent.com/rlaphoenix/NTON/master/README.md",
      "https://raw.githubusercontent.com/rlaphoenix/NTON/master/pyproject.toml",
      "https://raw.githubusercontent.com/rlaphoenix/NTON/master/CHANGELOG.md",
      "https://raw.githubusercontent.com/rlaphoenix/NTON/master/.github/workflows/ci.yml",
      "https://raw.githubusercontent.com/rlaphoenix/NTON/master/.github/workflows/cd.yml",
      "git ls-remote https://github.com/rlaphoenix/NTON"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "rlaphoenix/hacBrewPack",
    "url": "https://github.com/rlaphoenix/hacBrewPack",
    "default_branch": "master",
    "head_sha": "745b16ecfc9ce055743067d200572204cb2aac6c",
    "head_date": "2019-10-13",
    "pinned": "v3.05 (lightweight tag = branch master = HEAD 745b16ecfc9ce055743067d200572204cb2aac6c, commit 2019-10-13; repo created 2026-09-15 作为已删除的 The-4n/hacBrewPack 镜像)",
    "license_spdx": "GPL-2.0-only",
    "license_file": "LICENSE",
    "license_notes": "根 LICENSE = GPLv2 全文（18092 B）；README Licensing 节：『licensed under the terms of the GNU General Public License, version 2』并说明部分代码来自其它项目、见 LICENSES/（含 hactool.LICENSE、switch-tools.LICENSE 等上游许可原文）。捆绑 mbedTLS 2.6.1（其自身许可在 mbedtls/ 内）。",
    "archived": false,
    "last_push": "2026-09-15",
    "stars": 2,
    "open_issues": 0,
    "build_system": "C（gnu11，config.mk.template: gcc -O2 -Wall -Wextra -pedantic -std=gnu11 -fPIC，LDFLAGS=-lmbedtls -lmbedx509 -lmbedcrypto）；Makefile 先编 mbedtls 静态库再链接 hacbrewpack；无独立 release（/releases/latest 404）",
    "build_deps": "mbedTLS 2.6.1（内置 mbedtls/ 子目录，无其它外部依赖）；密钥机制：keys.dat 或 keys.txt/keys.ini/prod.keys/~/.switch/prod.keys（-k 指定），必需 header_key 与 key_area_key_application_xx（README 表）；输入：exefs/main + main.npdm、control/control.nacp + icon_<Language>.dat（JPEG 256x256）、romfs/、logo/（可 --nologo）、程序 titleid 需在 0x0100000000000000-0x0fffffffffffffff 且 Makefile/npdm.json 一致；输出：Program/Control(/LegalInformation/HtmlDocument) NCA + Meta NCA，打包为 <titleid>.nsp（main.c:382）",
    "readme_claims": "『hacBrewPack is a tool for creating Nintendo Switch NCAs ... from homebrews and pack them into NSPs』；需 keyset（header_key、key_area_key_application_xx）；按 exefs/control/romfs/logo 目录结构放置即可无参数运行；titleid 必须小写且在合法范围；icon 必须 256x256 JPEG（EXIF 可能导致占位图/安装卡住）；logo/ 的 Nintendo 素材自身不带许可、需用户自备或用 --nologo；支持 --titleid/--titlename/--titlepublisher 覆盖；v3.05 增加 keygeneration 8+ 支持（CHANGELOG）",
    "readme_claim_url": "https://github.com/rlaphoenix/hacBrewPack/blob/master/README.md",
    "risks": [
      "上游原始仓库 The-4n/hacBrewPack 已删除，本仓库是 2026-09-15 新建镜像（stars=2），上游维护状态/来源完整性无法从 GitHub 确认",
      "最后实质提交 2019-10-13（v3.05），无 CI、无 release，需本地构建并记录编译产物哈希",
      "新 keygeneration 支持止于 v3.05（CHANGELOG: Added support for keygeneration 8+），更高固件密钥代次需评估",
      "会就地修改输入 npdm/nacp（Carafe nsp.md: npdm.c:18,118 / nacp.c:16,88,119 取证），集成时必须传入副本",
      "Windows MAX_PATH 259 字节限制（Carafe 实测 258/259 通过、260/270 失败），长路径/非 ASCII 路径需预检查",
      "GPL-2.0：作为独立程序调用可接受，修改源码后分发需按 GPL-2.0 提供源码"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "无 GitHub Release（/releases/latest 返回 404），无法核对官方发行资产与哈希"
    ],
    "source_urls": [
      "https://api.github.com/repos/rlaphoenix/hacBrewPack",
      "https://api.github.com/repos/rlaphoenix/hacBrewPack/tags?per_page=100",
      "https://api.github.com/repos/rlaphoenix/hacBrewPack/contents/",
      "https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/README.md",
      "https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/CHANGELOG.txt",
      "https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/Makefile",
      "https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/config.mk.template",
      "https://raw.githubusercontent.com/rlaphoenix/hacBrewPack/master/LICENSE",
      "git ls-remote https://github.com/rlaphoenix/hacBrewPack"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "jakcron/nstool",
    "url": "https://github.com/jakcron/nstool",
    "default_branch": "development-tip",
    "head_sha": "cfb826ca6c165fbcd816fd7949df88ef3d72a948",
    "head_date": "2024-10-14",
    "pinned": "v1.9.2 (e89ea84bd70c11b67ebec9153fb4a446f18a9d3d, 2024-10-14; release published 2024-10-14T01:37:38Z)",
    "license_spdx": "MIT",
    "license_file": "LICENSE",
    "license_notes": "根 LICENSE = MIT（1061 B）；依赖通过 git submodule 引入（jakcron/libmbedtls、libfmt、libtoolchain、liblz4、libpietendo），各自许可见 deps/ 内副本。README 明确『NSTool doesn't embed any keys that are copyright protected』，密钥须用户自备。",
    "archived": false,
    "last_push": "2024-10-14",
    "stars": 558,
    "open_issues": 16,
    "build_system": "C++11；Linux/macOS: make deps 后 make（Makefile）；Windows: Visual Studio build/visualstudio/nstool.sln（BUILDING.md）；发布资产含 win_x64/win_x86/macos_arm64/macos_x86_64/ubuntu_x86_64",
    "build_deps": "git submodules: jakcron/libmbedtls、jakcron/libfmt、jakcron/libtoolchain（v0.8.0，见 HEAD 提交说明）、jakcron/liblz4、jakcron/libtoolchain；只读/提取能力见 README 支持格式（PFS0/HFS0/RomFS/NCA/NSP/XCI/META/NACP/CNMT/CERT/TIK/NSO/NRO/INI1/KIP1）",
    "readme_claims": "通用 Switch 文件格式读取/提取工具；默认打印一般信息，--showlayout/--showkeys/-v 增加布局/密钥/全量信息，-y/--verify 校验签名与哈希（NCA Header Sig0/Sig1、META、XCI header 等；v1.6.0 起内置 Root/XCI/ACID/NCA Header 公钥），-x 提取文件系统，--basenca 处理增量补丁 NCA；密钥不内嵌、需外部 keyset（SWITCH_KEYS.md）",
    "readme_claim_url": "https://github.com/jakcron/nstool/blob/development-tip/README.md",
    "risks": [
      "默认分支 development-tip 与 v1.9.2 tag 不同 commit（cfb826ca vs e89ea84b），必须锁定 tag 而非分支",
      "v1.7.0 与 v1.6.6 两个 tag 指向同一 commit 80cb738b5aa7b2fc5febbbe158aafb7f2981d893（上游 tag 异常），引用历史版本时需注明",
      "已 2 年无提交（最后 push 2024-10-14），open issues 16，后续固件/格式支持需自行评估",
      "校验需要用户提供密钥（NCA Header/ACID 公钥等），不能替代真机安装验证"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/jakcron/nstool",
      "https://api.github.com/repos/jakcron/nstool/tags?per_page=100",
      "https://api.github.com/repos/jakcron/nstool/releases/latest",
      "https://api.github.com/repos/jakcron/nstool/license",
      "https://raw.githubusercontent.com/jakcron/nstool/development-tip/README.md",
      "https://raw.githubusercontent.com/jakcron/nstool/development-tip/BUILDING.md",
      "https://raw.githubusercontent.com/jakcron/nstool/development-tip/.gitmodules",
      "git ls-remote https://github.com/jakcron/nstool"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "TooTallNate/switch-nsp-forwarder",
    "url": "https://github.com/TooTallNate/switch-nsp-forwarder",
    "default_branch": "main",
    "head_sha": "845811585e0b0d8881745afd50eca25d203957fd",
    "head_date": "2026-05-03",
    "pinned": "0.0.8 (61edd504e57c6007f23a3a242b386ac0372c0cee, 2026-05-03; release published 2026-05-03T07:27:22Z, assets nsp-forwarder.nro 11585582 B / nsp-forwarder.nsp 9123544 B)",
    "license_spdx": "MIT",
    "license_file": "package.json（\"license\": \"MIT\"）；仓库根目录无 LICENSE 文件，GitHub /license 为 404",
    "license_notes": "GitHub API license=null、/license 404；许可仅由 package.json 的 \"license\": \"MIT\" 声明（npm 生态约定）。依赖 @nx.js/*、react、jimp 等各自许可需随再分发核对；NTON README Licensing 节称其 rom 目录（romfs/template/exefs）为 MIT。",
    "archived": false,
    "last_push": "2026-06-16",
    "stars": 142,
    "open_issues": 14,
    "build_system": "Node.js/TypeScript + React（NX.js 运行时）；pnpm 10.33.2、esbuild 打包、@nx.js/nro 0.0.69 / @nx.js/nsp 0.0.69 生成 NRO/NSP；在 Switch 本体内生成并安装 forwarder（NSP -> NRO）；发行同时提供 .nro 与 .nsp",
    "build_deps": "dependencies: @nx.js/clkrst ^1.0.1, @nx.js/constants ^0.4.0, @nx.js/install-title ^0.0.3, @nx.js/ncm ^1.2.0, @tootallnate/nacp ^0.2.0, jimp 1.6.0, react ^18.3.1, react-router-dom ^6.30.2, react-tela ^1.0.1；devDeps 含 @nx.js/nro|nsp|runtime 0.0.69, esbuild ^0.28.0, typescript ^5.8.3",
    "readme_claims": "『Generate and Install NSP to NRO forwarders on your Switch』；从 Releases 下载最新版；0.0.8 重建 forwarder ROM 修复 NRO 退出（+ 键返回 HOME，不再无限重载），0.0.7 起 TitleID 由 NRO 路径与参数的 SHA-256 派生（与 sphaira 逻辑一致）",
    "readme_claim_url": "https://github.com/TooTallNate/switch-nsp-forwarder/blob/main/README.md",
    "risks": [
      "仓库根目录无 LICENSE 文件，只有 package.json 的 MIT 声明；再分发前需自行补充许可文本",
      "与 NTON 同类主机封禁/签名风险（NTON README 已声明该风险适用于所有 forwarder 生成器）",
      "forwarder 仅记录 NRO 路径，不自包含 NRO/游戏数据",
      "在机内直接生成安装，需 CFW 环境；依赖 NX.js 生态版本较新"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [],
    "source_urls": [
      "https://api.github.com/repos/TooTallNate/switch-nsp-forwarder",
      "https://api.github.com/repos/TooTallNate/switch-nsp-forwarder/tags?per_page=100",
      "https://api.github.com/repos/TooTallNate/switch-nsp-forwarder/releases?per_page=20",
      "https://api.github.com/repos/TooTallNate/switch-nsp-forwarder/license",
      "https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/README.md",
      "https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/package.json",
      "https://raw.githubusercontent.com/TooTallNate/switch-nsp-forwarder/main/CHANGELOG.md",
      "git ls-remote https://github.com/TooTallNate/switch-nsp-forwarder"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "switchbrew/switch-tools (nxlink)",
    "url": "https://github.com/switchbrew/switch-tools",
    "default_branch": "master",
    "head_sha": "22756068dd0ed6ff9734c59cb4f99ebd3f62555b",
    "head_date": "2024-10-23",
    "pinned": "v1.13.1 (22756068dd0ed6ff9734c59cb4f99ebd3f62555b, 2024-10-23; tag 与 HEAD 同一 commit；上一版 v1.13.0=009889630757)",
    "license_spdx": "ISC",
    "license_file": "COPYING",
    "license_notes": "COPYING（726 B）= ISC 许可，『Copyright 2017 libnx Authors』；无根 LICENSE 文件。仓库同时构建 elf2nso/elf2nro/elf2kip/build_pfs0/build_romfs/nacptool/npdmtool/nxlink，各自源码同仓库、同一 ISC 声明。",
    "archived": false,
    "last_push": "2024-10-23",
    "stars": 181,
    "open_issues": 2,
    "build_system": "autotools（autogen.sh / configure.ac / Makefile.am；README 为空文件，无构建文档）；Makefile.am: bin_PROGRAMS = elf2nso elf2nro elf2kip build_pfs0 build_romfs nacptool npdmtool nxlink；nxlink_SOURCES = src/nxlink.c，nxlink_CPPFLAGS=@ZLIB_CFLAGS@，nxlink_LDADD=@ZLIB_LIBS@ @NET_LIBS@",
    "build_deps": "zlib（nxlink 及其它工具）；网络库 NET_LIBS；nxlink 与主机侧 netloader 通过 TCP 28280（NETLOADER_SERVER_PORT）/ 28771（NETLOADER_CLIENT_PORT）通信",
    "readme_claims": "README 为空（0 字节），能力只能从源码取证：nxlink『Usage: nxlink [options] nrofile』，选项 --help/-h、--address/-a（Switch 主机名或 IPv4）、--retries/-r（ping 重试次数）、--path/-p（上传目标路径）、--args（传给 nro 的参数）、--server/-s（上传完成后启动服务器接收输出）；即通过 netloader 热加载 NRO 并回传控制台输出，适合开发内循环",
    "readme_claim_url": "https://github.com/switchbrew/switch-tools/blob/master/README（空文件）",
    "risks": [
      "README 为空、无发行说明文档，能力/兼容性需按源码核实，且本次未在真机运行",
      "nxlink 需要 Switch 侧 netloader/homebrew 环境（如 nx-hbmenu 的 netloader），本审计未验证具体版本可用性",
      "仓库 2024-10-23 后无提交，devkitPro 生态的包管理分发（pkg.devkitpro.org）本次因 Cloudflare 403/TLS 失败未能核实包名与版本",
      "nxlink 仅用于开发加载，不是 NSP 安装/打包工具，不能替代 nstool/hacBrewPack"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "devkitPro 的 switch-tools/nxlink 分发来源未验证：pkg.devkitpro.org 返回 Cloudflare 403，libnx.devkitpro.org TLS 失败，pacman-packages/switch-tools 等 raw 路径 404；以 GitHub switchbrew/switch-tools 源码为准",
      "README 文件为 0 字节，无官方能力声明，本条目 README 声称来自 src/nxlink.c 源码"
    ],
    "source_urls": [
      "https://api.github.com/repos/switchbrew/switch-tools",
      "https://api.github.com/repos/switchbrew/switch-tools/tags?per_page=100",
      "https://raw.githubusercontent.com/switchbrew/switch-tools/master/COPYING",
      "https://raw.githubusercontent.com/switchbrew/switch-tools/master/Makefile.am",
      "https://raw.githubusercontent.com/switchbrew/switch-tools/master/src/nxlink.c",
      "https://raw.githubusercontent.com/switchbrew/switch-tools/master/README",
      "git ls-remote https://github.com/switchbrew/switch-tools"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "autorunhq/autorun",
    "url": "https://github.com/autorunhq/autorun",
    "default_branch": "main",
    "head_sha": "1ac9b6cf37b90f2d5783dd7ef389bebbe1c68877",
    "head_date": "2026-10-16",
    "pinned": "test-build-4 (9b7170505f9084fee0ffe1a237b08557a6ab2868, 2026-09-24; release published 2026-09-24T10:59:45Z, asset autorun-test-build-4.zip 64978068 B；仅测试构建，无稳定版)",
    "license_spdx": "NOASSERTION",
    "license_file": "LICENSE（Wine 主许可文本）+ COPYING.LIB + NOTICES.md",
    "license_notes": "GitHub /license 返回 NOASSERTION；根 LICENSE 为 Wine 的 LGPL-2.1-or-later 声明（Copyright 1993-2026 the Wine project authors，指向 COPYING.LIB），本仓库是 Wine fork。README Credits 表逐组件标注：Wine LGPL-2.1-or-later、FEX MIT、Box64 MIT、DXVK zlib/libpng、VKD3D-Proton LGPL-2.1-or-later、Mesa/mesa-switch MIT(mostly)、LSFG-VK GPL-3.0-or-later、libusbhsfs ISC、Atmosphère/Horizon-OC GPL-2.0、libnx/devkitPro ISC(按组件)、启动器 SDL2/SDL2_ttf/FreeType/HarfBuzz/libpng/zlib 等；NOTICES.md（67272 B）收录 Wine 引入的第三方版权声明。再分发义务：随附 LGPL/GPL 文本与源码（Wine/Atmosphère/Horizon-OC 等 GPL/LGPL 组件）、保留 NOTICES/AUTHORS。",
    "archived": false,
    "last_push": "2026-10-16",
    "stars": 525,
    "open_issues": 62,
    "build_system": "Wine 11.18 fork（VERSION 文件：『Wine version 11.18』），Horizon 侧在 horizon-wine/ 用 CMake+Ninja 构建 runtime NRO，两套 runtime：x86（WoW64+Box64，cmeson 选项 WINE_NX_BOX64_DYNAREC）与 AMD64（FEX，WINE_NX_AMD64/WINE_NX_FEX）；构建在 Docker 的 switch-dev 镜像内（switch-dev.txt，llvm-mingw-20260505-ucrt 工具链，CMake 引用 WINE_NX_MESA_SWITCH_DIR/USB storage/LSFG-VK/libusbhsfs portlibs）；GitLab CI 仅 stages 定义（.gitlab-ci.yml，232 B）",
    "build_deps": "Wine 11.18；FEX（x64/32-bit 翻译，来自 FEX-Emu/FEX）；Box64（32 位第二翻译器，bootstrap-box64-core.sh 固定 revision 2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a，来自 ptitSeb/box64）；Mesa 26 / mesa-switch（OpenGL nvc0 + Vulkan NVK）；DXVK（D3D8-11）；VKD3D-Proton（D3D12）；LSFG-VK（帧生成，需自备 Lossless Scaling）；libusbhsfs（USB 存储）；Windows DLL 不在本仓，由 horizon-dlls 子模块（autorun-horizon-dlls）下载；game-fixes 子模块提供 per-game 修复",
    "readme_claims": "『Play Windows PC games on your Nintendo Switch』；Wine 跑在 Horizon OS 上，FEX 翻译 x86/x64、Box64 作为 32 位第二翻译器，Mesa 26 提供 OpenGL/Vulkan，DXVK 跑 D3D8-11、VKD3D-Proton 跑 D3D12，LSFG-VK 帧生成；Windows DLL 由 app 下载更新；USB 盘显示为 D:-H:；需要 CFW(Atmosphère)、SD 卡、约 200MB DLL；安装为解压到 SD 根目录 switch/wine，Quick setup 会下载 DLL、安装 Mesosphere 低地址启动改动（stock loader 或 Horizon-OC）；明确『Autorun is experimental. Some games run well, many start and then stop on something that isn't done yet. Every run writes a log that says where.』；声明不是盗版/绕过工具、单进程 Wine 限制、不支持盗版/第三方整包",
    "readme_claim_url": "https://github.com/autorunhq/autorun/blob/main/README.md",
    "risks": [
      "实验性项目（README 自述），无稳定发布，仅 test-build-2/3/4 三个测试构建",
      "需要 CFW + Mesosphere 启动改动（低内存地址）与签名补丁环境，安装门槛与合规风险高",
      "Wine 在 Switch 上单进程运行，需要商店客户端/反作弊/在线登录的游戏无法运行（README 自述）",
      "与游戏本体分离：游戏目录需用户自备，NSP 体积与兼容性取决于 runtime + 游戏数据",
      "许可证为 NOASSERTION，整体再分发需逐组件遵守 LGPL/GPL（Wine/VKD3D-Proton/Atmosphère/Horizon-OC/LSFG-VK）",
      "构建链复杂：Docker switch-dev 镜像 + llvm-mingw 工具链 + 多份 patch/submodule，复现成本高"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "未在真机/模拟器运行，README 的『部分游戏可运行』仅为项目自述，未逐条核验 issue/兼容性列表",
      "未下载 test-build ZIP 核对其内容与哈希"
    ],
    "source_urls": [
      "https://api.github.com/repos/autorunhq/autorun",
      "https://api.github.com/repos/autorunhq/autorun/tags?per_page=100",
      "https://api.github.com/repos/autorunhq/autorun/releases?per_page=20",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/README.md",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/VERSION",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/LICENSE",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/COPYING.LIB",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/NOTICES.md",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/horizon-wine/README.md",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/horizon-wine/tools/bootstrap-box64-core.sh",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/build-x86.sh",
      "https://raw.githubusercontent.com/autorunhq/autorun/main/.gitmodules",
      "git ls-remote https://github.com/autorunhq/autorun"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "autorunhq/autorun-horizon-dlls",
    "url": "https://github.com/autorunhq/autorun-horizon-dlls",
    "default_branch": "main",
    "head_sha": "67e2303dee9191b7ce4e2d1ccb47957d15c8a98b",
    "head_date": "2026-10-16",
    "pinned": "dlls tag (4ab914bb4f7ffd35753934c02ecde05eed23a50f, commit 2026-09-28; release published 2026-09-28T11:53:27Z, assets horizon-dlls.tar.zst 88439006 B / horizon-dlls.zip 203013347 B)",
    "license_spdx": "NOASSERTION",
    "license_file": "NOTICE.md + LICENSES/（无仓库根 LICENSE）",
    "license_notes": "GitHub /license 返回 null（404，无根 LICENSE）；NOTICE.md（65295 B）按文件说明来源与逐组件许可表，LICENSES/ 收录各组件许可全文（Wine LGPL-2.1-or-later、FFmpeg LGPL-2.1-or-later、vkd3d LGPL-2.1-or-later、mpg123 LGPL-2.1-only、Capstone BSD-3-Clause、FAudio Zlib、FluidSynth LGPL-2.1-or-later、ICU、libjpeg IJG、Little CMS MIT、musl MIT、libpng、SQLite blessing、SymCrypt MIT、DXVK zlib、DXBC/DXIL-SPIRV 等）。再分发义务：逐文件遵守其许可（LGPL 组件需附源码位置，NOTICE.md 指向 autorun commit 97422507a2bc8100c6ba32a13828109a340e9131）。",
    "archived": false,
    "last_push": "2026-10-16",
    "stars": 8,
    "open_issues": 0,
    "build_system": "由 Python 脚本（tools/build-dlls.py 及 build-dxvk.py / build-fex.sh / build-vkd3d.py / dxvk_payload.py / fex_payload.py / vkd3d_payload.py）从 Wine 11.18 源码构建 Windows 侧模块；产物按 SD 卡布局存放：switch/wine/drive_c（ARM64X system32 + i386 syswow64）、switch/wine/horizon-dlls（manifest + classes.reg）、compressed/（zlib 压缩副本，供 Autorun 增量下载）；release 提供 tar.zst/zip 整包",
    "build_deps": "Wine 11.18（autorunhq/autorun commit 97422507a2bc8100c6ba32a13828109a340e9131）；FEX 的 CPU 模块；DXVK；VKD3D-Proton；Mesa 相关组件；每文件 manifest 条目含 version/size/SHA-256；附 PhysX 系统软件 9.13.0604（未修改）与开源 XLiveLess；Python 构建脚本",
    "readme_claims": "『Every module a Windows game expects to find in system32 (ARM64X) and syswow64 (i386), built from Autorun's Wine』；Autorun 自动下载并保持更新（『nothing here needs to be copied by hand』），每文件有 version/size/SHA-256，卡上只取字节变化的文件；无网络时下载仓库 ZIP 解压 switch/ 到 SD 根；『Not a piracy or circumvention tool』，不含 Microsoft 代码/游戏文件、不绕过 DRM；含 PhysX 9.13.0604 与 XLiveLess（替代已停服的 Games for Windows Live）；『Autorun downloads horizon-dlls.tar.zst itself for a card that has few of them』（release 说明）",
    "readme_claim_url": "https://github.com/autorunhq/autorun-horizon-dlls/blob/main/README.md",
    "risks": [
      "仓库无根 LICENSE，整体许可无法用单一 SPDX 表示；再分发必须逐文件遵守 NOTICE.md/LICENSES/，否则违反 LGPL 等义务",
      "发行体积大（zip 203 MB / tar.zst 88 MB），随 NSP 自包含打包会显著膨胀",
      "内容依赖特定 Autorun runtime 的接口（runtime-interfaces.json），版本不匹配时 DLL 会被跳过",
      "文件由构建脚本生成而非逐文件审阅，完整性依赖 manifest 的 SHA-256 清单"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "未下载 release 资产核对 manifest 与 SHA-256 清单（仅读 README/NOTICE/release 元数据）"
    ],
    "source_urls": [
      "https://api.github.com/repos/autorunhq/autorun-horizon-dlls",
      "https://api.github.com/repos/autorunhq/autorun-horizon-dlls/releases?per_page=20",
      "https://api.github.com/repos/autorunhq/autorun-horizon-dlls/license",
      "https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/README.md",
      "https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/NOTICE.md",
      "https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/tools/build-dlls.py",
      "https://raw.githubusercontent.com/autorunhq/autorun-horizon-dlls/main/tools/build-fex.sh",
      "git ls-remote https://github.com/autorunhq/autorun-horizon-dlls"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "carafe-nx/carafe",
    "url": "https://github.com/carafe-nx/carafe",
    "default_branch": "main",
    "head_sha": "3334ebc66e9bb2f6c12364a7b0b9a7472381fc3e",
    "head_date": "2026-10-25",
    "pinned": "v0.4.0 (9b69701b8ae885126b09cf2ccdddef1eccee9732, 2026-10-25; release published 2026-10-25T08:34:35Z, assets Carafe_0.4.0_arm64-setup.exe 227864387 B / x64-setup.exe 228142873 B / latest.json / SHA256SUMS.txt)",
    "license_spdx": "GPL-3.0-or-later",
    "license_file": "LICENSE",
    "license_notes": "根 LICENSE = GPLv3 全文（35149 B）；README：Carafe 为 GPL-3.0-or-later，runtime overlay 与 Autorun patches 为 LGPL-2.1-or-later（runtime/overlay/LICENSE、runtime/patches/LICENSE），loader 为 ISC（runtime/loader/LICENSE），external/ 内第三方各自许可。随发行捆绑 hacBrewPack（GPL-2.0，作为独立程序调用）与 Autorun runtime（含 LGPL/GPL 组件），发行时须一并满足这些许可（源码提供、许可文本随附）。",
    "archived": false,
    "last_push": "2026-10-28",
    "stars": 253,
    "open_issues": 9,
    "build_system": "Tauri 2 + Rust 1.99（app/，Rust core + React 19/TypeScript 7 UI）；Docker compose 构建 Windows runtime 与 hacBrewPack；CI: check.yml（windows-latest，Node 24，rust 1.99.0，npm run check + TypeScript bindings 检查），release.yml（Ubuntu 构建 runtime/hacBrewPack 产物，windows-latest 与 windows-11-arm 跑 tauri build，NSIS 安装包，未签名）",
    "build_deps": "Rust 1.99.0、Node 24、Docker Desktop；hacBrewPack v3.05（tools/hacbrewpack，commit 745b16e，带 Carafe patch 0001）；Autorun runtime（external/autorun submodule，Wine 11.18 + Box64/FEX + DXVK + Mesa）；nx-hbloader（loader）；devkitPro 工具链；app 依赖 @tauri、React 等（见 app/package-lock.json）",
    "readme_claims": "『desktop app that turns a Windows game folder into a standalone app for a Switch with custom firmware』；游戏进 NSP 后从 HOME Menu 启动，有自己的图标/存档/加载屏；NSP 内是 Autorun runtime（Wine + Box64/FEX + DXVK + Mesa）；需要 Atmosphère + sigpatches、DBI(MTP) 安装；Windows 10/11 x64/ARM64；安装包未签名（『not signed yet』）；hacBrewPack 负责打包 NCA/NSP（tools/hacbrewpack）；nsp.md：hacBrewPack v3.05/745b16e，mbedTLS 2.6.1，Carafe 用 patch 0001 把 RomFS 打包从 120s 降到 27s（2.2GB），Windows 路径上限 259 字节、Carafe 预检查（pathTooLong），TitleID 自行写入 NPDM 三处而不传 --titleid",
    "readme_claim_url": "https://github.com/carafe-nx/carafe/blob/main/README.md",
    "risks": [
      "GPL-3.0-or-later：若 GalNX 直接复制其代码/派生作品，需以 GPL-3.0 发布；仅参考设计可规避",
      "依赖 hacBrewPack（GPL-2.0）与 Autorun（实验性 runtime）：打包链/兼容性风险继承上游",
      "Windows-only 桌面 app，release 安装包未签名；需要 Docker 才能从源码构建 runtime",
      "安装需 Atmosphère + sigpatches + DBI，属于签名补丁/CFW 生态，合规与主机封禁风险与 forwarder 相同",
      "NSP 为自包含路线，体积 = 游戏 + runtime（数百 MB 到数 GB），需评估 SD 卡与安装时间",
      "外部依赖版本通过 submodule/release 产物传递，需锁定 submodule commit 与 runtime 版本记录（release.yml 用 runtime-version 查找逻辑）"
    ],
    "verification_level": "source-inspected",
    "verification_failures": [
      "未运行 Carafe/未安装其 NSP，README 功能与 nsp.md 数据（如 patch 0001 性能数据、259 字节路径限制）来自其文档/源码引用，未独立复现"
    ],
    "source_urls": [
      "https://api.github.com/repos/carafe-nx/carafe",
      "https://api.github.com/repos/carafe-nx/carafe/tags?per_page=100",
      "https://api.github.com/repos/carafe-nx/carafe/releases/latest",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/README.md",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/LICENSE",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/architecture.md",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/nsp.md",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/docs/testing.md",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/runtime/Makefile",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/.github/workflows/check.yml",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/.github/workflows/release.yml",
      "https://raw.githubusercontent.com/carafe-nx/carafe/main/compose.yaml",
      "git ls-remote https://github.com/carafe-nx/carafe"
    ],
    "audited_at": "2026-10-29"
  },
  {
    "name": "Ryujinx 源流（网页侧旁证；结论由 Lead 定稿）",
    "url": "https://git.ryujinx.app/Ryubing/Canary （官方 Canary 源，TLS 不可达）；https://github.com/Ryubing/UpdateServer （更新服务元数据）",
    "default_branch": "",
    "head_sha": "",
    "head_date": "",
    "pinned": "",
    "license_spdx": "",
    "license_file": "",
    "license_notes": "官方 Canary 源码/发行位置由 Ryubing/UpdateServer 的 src/Server/appsettings.json 证实：Forgejo Endpoint=https://git.ryujinx.app/，VersionCacheSources.Canary.Project=Ryubing/Canary（Stable.Project=projects/Ryubing，Canary.DeriveLatestVersionManually=true）；ReleaseChannel 枚举含 Stable/Canary/Custom1/KenjiNX。GitHub 侧 Ryubing/ryujinx 已 404（不存在/删除/私有），ryujinx-mirror/ryujinx 被 DMCA 451 屏蔽；故官方许可证/仓库元数据本次无法从可达源核实（Canary 源码 zip 的 Comment=4e81a4c2f4fee6f31e28fbb129759ec2369da6eb 由 Lead 本机取证）。",
    "archived": "",
    "last_push": "2026-08-26（Ryubing/UpdateServer 的 pushed_at；非模拟器源码仓库）",
    "stars": 30,
    "open_issues": "",
    "build_system": "（无法验证）更新服务为 .NET 项目，自述提供 /latest/query、/download/*、/api/v1/meta、/api/v1/admin/refresh_cache、/api/v1/versioning/* 等端点，MaxConcurrentDownloads=1；模拟器本体构建方式无法从可达源取证",
    "build_deps": "（无法验证）从 VersionCacheEntry 字段可知发行覆盖 macOS/windows{x64,arm64}/linux/linux_appimage；Canary 版本命名形如 1.3.265（与 ewigl/ryubing-canary-mirror 的 1.3.340/1.3.341/1.3.349-351、Wayback CDX 的 git.ryujinx.app release 下载 URL 1.3.201/1.3.203 同序列）",
    "readme_claims": "Ryubing/UpdateServer README 记录官方下载服务端点；ewigl/ryubing-canary-mirror 描述『Mirror of the Ryubing/Ryujinx Canary Windows x64 releases. For personal use only. Ryubing's official download service is currently down, so no updates until it's back.』；ryujinx-mirror/ryujinx 的 GitHub 屏蔽页：Repository access blocked, reason=dmca, 对应 https://github.com/github/dmca/blob/master/2025/03/2025-03-06-nintendo.md",
    "readme_claim_url": "https://github.com/Ryubing/UpdateServer",
    "risks": [
      "官方源 git.ryujinx.app 与 gitlab.hugofnm.fr 匿名均不可达，Canary-1.3.265 的 commit SHA/日期无法独立验证（本审计 verification_failures 已记录）",
      "ryujinx-mirror/ryujinx 因任天堂 DMCA（2025-03-06 投诉）被 GitHub 451 屏蔽，镜像渠道不可作为可信/长期来源",
      "Ryubing/ryujinx 404，GitHub 上无官方源码仓库；GitHub code search『Canary-1.3.265』total=0",
      "固定测试环境只能依赖本机已有二进制+源码 zip（Lead 取证 ProductVersion=1.3.265+4e81a4c 与 zip Comment=4e81a4c2f4fee6f31e28fbb129759ec2369da6eb），需本地留档并计算 SHA-256，否则不可复现",
      "更新源（update.ryujinx.app / git.ryujinx.app）若恢复，版本与 commit 对应关系仍可能漂移，应禁止自动更新"
    ],
    "verification_level": "read-only",
    "verification_failures": [
      "GitLab API https://gitlab.hugofnm.fr/api/v4/projects/publicmirrors%2FRyujinx 返回 404 Project Not Found；/api/v4/version 返回 401；网页 /publicmirrors/Ryujinx 及其 /-/tags 返回 404（匿名需登录/路径不存在），Canary-1.3.265 tag 的 commit SHA 与日期未能验证",
      "git.ryujinx.app（DNS 91.239.78.255）TLS 不可达：curl schannel handshake failed、直连 20s timeout、python SSL UNEXPECTED_EOF_WHILE_READING、http 经代理 502，官方 Forgejo Canary 仓库/标签未直接验证",
      "update.ryujinx.app TLS 握手失败（Lead 实测），官方更新 API 未调用验证",
      "github.com/Ryujinx 组织仅剩 Ryujinx/.github profile 仓库（public_repos=1，pushed 2024-12-31），无模拟器源码；Ryubing 组织 11 个仓库中无模拟器源码仓库",
      "GitHub code search『Canary-1.3.265』total=0；Wayback 的 git.ryujinx.app 标签页 commit 区块不可信（Lead 结论），Wayback 仅作 1.3.x 命名旁证",
      "ryujinx-mirror/ryujinx 访问返回 451（Repository access blocked, dmca），无法读取 tags/metadata"
    ],
    "source_urls": [
      "https://api.github.com/orgs/Ryujinx",
      "https://api.github.com/repos/Ryujinx/.github",
      "https://api.github.com/orgs/Ryubing",
      "https://api.github.com/users/Ryubing/repos?per_page=100",
      "https://api.github.com/repos/Ryubing/UpdateServer",
      "https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Server/appsettings.json",
      "https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Common/Enums/ReleaseChannel.cs",
      "https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Common/Constants.cs",
      "https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Common/Models/VersionCacheEntry.cs",
      "https://raw.githubusercontent.com/Ryubing/UpdateServer/main/src/Common/Models/VersionResponse.cs",
      "https://api.github.com/repos/ryujinx-mirror/ryujinx（451 DMCA）",
      "https://api.github.com/repos/ewigl/ryubing-canary-mirror",
      "https://web.archive.org/cdx/search/cdx?url=git.ryujinx.app/Ryubing/Canary/releases&output=json&limit=5",
      "https://gitlab.hugofnm.fr/api/v4/projects/publicmirrors%2FRyujinx（404）"
    ],
    "audited_at": "2026-10-29"
  }
]
```
<!-- AUDIT-JSON-END -->
