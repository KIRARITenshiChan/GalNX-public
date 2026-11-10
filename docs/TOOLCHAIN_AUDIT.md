# GalNX 工具链与上游生态审计报告（第一轮）

- 文档版本：v1.3（第一轮审计 + M0 工具链实测 + Web 冒烟 v2/Citron 实测 + 4 份联网复核报告合并，2026-10-29）
- 审计日期：2026-10-29（Asia/Shanghai）
- 审计执行者：Lead + 4 个只读审计 agent（audit-switch / audit-engines / audit-web / audit-package）
- 上游依据：计划草案 v0.1 → v0.4（`docs/PLAN_DRAFT_v0.1.md`～`v0.4.md`；v0.2 起按用户决策更新，v0.4 为 2026-10-29 联网复核后修订版）
- 审计范围：计划草案 §7 所列全部仓库 + §14 第一轮执行清单第 1–4 项
- 审计方式：**第一轮只读审计**：未安装 devkitPro、未构建、未克隆大仓库、未下载商业游戏数据
- 后续 M0 实测：2026-10-29 经用户授权在 `D:\devkitPro` 补装 Switch 工具链并完成最小 NRO 构建，结果见 §8（该部分属 M0 实测，不属只读审计）
- 文档状态：**v1.3**。4 个集群审计已合并（27 条记录 / 26 个唯一对象）；分项原始数据见 docs/audit/ 与 docs/audit/audit_merged.json；§8 已回填 2026-10-29 安装与最小构建结果（v1.1）；v1.3 增补 4 份联网复核报告结论（05 工具链 8 条、06 引擎 14 条、07 Web/Citron 7 条、08 打包 12 条）
- 补充审计：`docs/audit/04-renpy-official.md`（Ren'Py 官方源码独立移植可行性，7 条记录，2026-10-29；结论并入 §4.B.7）
- 环境实录：`docs/environment/devkitpro-2026-10-29.md` 与 `docs/environment/evidence/`（9 个证据文件；`docs/environment/m0-hello/` 归档构建记录快照）
- 实验记录：`docs/experiments/web-01-brewser-smoke.md`（Brewser 最小 Web 冒烟，Ryujinx 侧阻塞，2026-10-29；结论并入 §4.C.7，verification_level: **not-verified**）；`docs/experiments/web-02-citron-smoke.md`（换 Citron Neo 后**通过 2/2**，结论并入 §4.C.8）
- 复核报告（v1.3 新增，2026-10-29 联网复核）：`docs/audit/05-toolchain-refresh.md`（工具链有无落后 + CMake 空格路径实测）、`06-engines-refresh.md`（引擎路线复核与新候选）、`07-web-citron.md`（Citron Neo 审计 + Web 冒烟 v2）、`08-packaging-refresh.md`（打包链/测试后端复核 + keys 合规策略）
- 结论摘要：见下方 §0（8 条核心判断）

## 0. 结论摘要

**审计状态**：完成。共 27 条审计记录（26 个唯一上游对象；`switchbrew/switch-tools` 在 A/D 两集群各计一次），覆盖计划草案 §7 全部列出项，并补充 2 个计划未列对象（`devkitPro/installer` 官方安装器、上游 `TooTallNate/nx.js`）；对计划中以文字提及但未给链接的 `nxlink`，补齐其准确仓库 `switchbrew/switch-tools`。**补充审计（同日）**：Ren'Py 官方源码独立移植专项 `docs/audit/04-renpy-official.md`（7 条记录：`renpy/renpy`、`renpy/renpy-build`、`jvrcruzGAMES/NXPython` 与 4 个社区移植），结论并入 §4.B.7。本轮第一轮审计为纯只读：**未安装 devkitPro、未构建、未克隆大仓库、未下载/运行任何上游 release 二进制、未读取任何密钥内容、未接触商业游戏数据**。此后（2026-10-29 晚间）经用户授权补装 Switch 工具链并跑通最小 NRO 构建，该 M0 实测过程与证据见 §8。

### 核心判断（按对项目的影响排序）

1. **工具链可搭，但安装渠道先要排障（M0 第一阻塞）**：devkitPro 二进制包库 `pkg.devkitpro.org` 实测 HTTP 403（Cloudflare），`dkp-libs.db` 与包目录均不可取；官方 Windows 安装器 v3.0.3（2018-06-03，内置 MSYS2 2.10.0）安装后 `switch-dev` 静默失败；**2026-10-29 已定位根因为 Cloudflare 拦截直连（403）且 MSYS2 shell 无代理变量**，改由 `pacman.conf` 的 `XferCommand` 经本地代理（`127.0.0.1:7897`）+ 浏览器 UA 下载后完成安装，并跑通最小 NRO 构建（详见 §8）。Docker 镜像（`devkitpro/devkita64@sha256:1fc388c3…`）仍为 CI 锁定候选，未验证。
2. **devkitPro 没有版本化仓库**：官方 pacman 源是滚动 latest，wiki 未记载 snapshot 机制；锁定只能靠 `pacman -Q` 快照 + `pacman -Sw` 包缓存 + Docker 日期 tag digest + 上游源码 tag（`libnx v4.12.0 = 7644c9b2…`）。
3. **第一款原型＝KiriKiri 双层路线（v1.3 更正）**：复核发现 `krkrsdl2/krkrsdl2` 上游本体已有官方 Switch 目标与 CI 出包（`CMakeLists.txt` `if(NINTENDO_SWITCH)`、ci.yml matrix 含 `switch`、release `latest` 附 12.0 MB NRO，MIT），但为单游戏内嵌形态且 README 不提 Switch（「有实现、无文档」）；`DrFlyingPig/krkr-ns`（MIT，HEAD 949faf9a，2026-10-16）则是其上的**产品化启动器**（launcher/存档隔离/E-mote 等），release v0.1.0 的 tag 已移到 HEAD、时间戳矛盾 → **发布产物不可按 tag 溯源**。→ 路线：先用 **krkrsdl2 上游**验证「自有 data.xp3 → NRO」可复现构建，再用 krkr-ns 做启动器产品化。构建需要 devkitPro + CMake 3.31.6 + 自建 FFmpeg 7.1（LGPL 配置，sha256 40973d44…），krkr-ns 还依赖仓库外 `KRKR-ns-tools` 与兄弟仓库 `WA2-ns`、无 CI → 首个构建任务必须先固化构建配方（详见 §4.B.8、`docs/audit/06-engines-refresh.md`）。
4. **Ren'Py 路线：社区移植全部无许可证 → 改走官方源码独立移植**：`jvrcruzGAMES/RenpySwitch`、父仓库 `knautilus/RenpySwitch`、`Otorhin/Ren2Switch`、`uyjulian/renpy-switch`（已 archived）、`NXPython` **均无 LICENSE** → 取得书面授权前不得接入、不得复制代码。新方向 = `renpy/renpy` + `renpy/renpy-build` 官方源码：基线锁 `8.5.3.26051504 = 39895c1e…`（2026-05-16，仍用 SDL2；master 已迁 SDL3）、build 侧同 tag `7bfab40c…`；官方**无 Switch 平台**（`build.py` 平台表无 switch、`librenpython.c` 无 Switch 宏、README 明示不支持 cross-compiling）→ 唯一硬阻塞是 **CPython 3.12.8 交叉到 devkitA64/newlib**，建议先做 4–6 周 go/no-go 探针（详见 §4.B.7、`docs/audit/04-renpy-official.md`）。
5. **NSP 首个目标应从 forwarder 改为「自包含」**：`rlaphoenix/NTON` README 原文警示 forwarder 安装「can result in a console ban」、签名无效需 CFW、任天堂已 DMCA 此类方案；自包含路线（`nstool v1.9.2` 校验 + `hacBrewPack v3.05` 子进程打包 + 自研编排，参考 Carafe 流程但不复制 GPL 代码）才符合「点图标即玩」的发行形态。两条路线都需要用户自备 `prod.keys` 与 Atmosphère + sigpatches，GalNX 不得分发密钥或签名绕过组件。
6. **Web 路线 M4 首选 `natureglass/Brewser`**：MPL-2.0，官方 release 提供 76,546,123 B 的预编译 `brewser.nro`（sha256 `8ce31f5b…`），默认 `make` 只需 node/npm/python、无需 devkitPro；但其 V8/Skia 引擎链与私有 `@switch-web/runtime` 源码不可得，属「黑盒运行时」；RPG Maker MV / TyranoScript 需要 Node/fs 兼容层，Brewser 不能直接跑，M4 需要先做可行性验证。
7. **Ryujinx 1.3.265 本机证据自洽、独立核验未完成**：exe ProductVersion `1.3.265+4e81a4c` 与同目录源码 zip 的 7z Comment `4e81a4c2f4fee6f31e28fbb129759ec2369da6eb` 一致，运行日志独立确认版本 1.3.265；但 `git.ryujinx.app` TLS 不可达、GitLab 镜像需登录/API 404、GitHub 镜像 451 DMCA → 只能用「本机留档 + 哈希校验 + 断网 + 禁自动更新」固定测试环境（详见 §5）。
8. **计划草案有 4 处链接/描述需修正**（`nx-hbloader` 已迁移、`nx.js` 真实上游、`nxlink` 属 switch-tools、Ryujinx 源流描述），并建议把「首测游戏 = krkr-ns」「NSP 首目标 = 自包含」写入决策记录（详见 §9）。
9. **Web 路线模拟器侧已打通（v1.3 新增）**：Ryujinx 1.3.265 无法加载 nx.js 系 NRO（§4.C.7），换 **Citron Neo nightly `0237a9b88`** 后 Brewser v0.1.131 **完整运行 2/2**（§4.C.8，DOM/CSS/JS/Canvas2D/WebGL/localStorage 全通过、seed 生成）→ web-01 的阻塞应归因于 Ryujinx 环境而非 Web 路线本身。测试后端优先级 = Citron（开发循环/CI 冒烟）→ 本机留档 Ryujinx（第二意见）→ 真机（唯一验收权威）；Citron 为 GPL-3.0-or-later 外部工具，不捆绑不分发；其 release 资产与 tag 不对应，版本必须锁资产 sha256 `0d2c9bf3…`。

### 覆盖度与证据等级

- 26 个唯一对象中：`source-inspected` 22 条、`read-only` 4 条（`rexglue-sdk`、`XenonRecomp`、`XenosRecomp`、Ryujinx 源流）；仅 Ryujinx 上游 tag↔commit 的独立对应关系为 `not-verified`。
- 所有 SHA/日期/许可证均为 2026-10-29 实测；GitHub 元数据快照见 §10.2；逐条机读数据见 §10.1。
- README 声称的能力一律只记为「上游声称」，本轮未做任何本机复现（无安装/无构建/无运行）。

## 1. 审计方法与证据等级

本轮审计的每条事实按以下证据等级标注（字段 `verification_level`）：

| 等级 | 含义 |
| --- | --- |
| `read-only` | 通过 GitHub/GitLab API、raw 文件、`git ls-remote` 等只读网络请求实测得到：仓库存在性、默认分支、HEAD SHA、提交日期、LICENSE 原文、README 内容等 |
| `source-inspected` | 在 `read-only` 基础上，进一步下载并阅读了源码文件（README、LICENSE、构建脚本、CI 配置、目录结构等），确认其声明的能力/依赖 |
| 其余 | 一律写 `not-verified`，并在条目中写明未验证原因 |

基本原则：

- **README 声称 ≠ 已验证**：上游 README 声称的兼容性/功能只作为 `readme_claims` 记录，是否属实需在本机复现后才可升级证据等级。
- 所有 SHA/日期/许可证均来自实测，不采用记忆或二手转述。
- 网络取数时间：2026-10-29；GitHub API 快照见附录。
- 取数通道：GitHub API（`GH_TOKEN`，凭据经 cred_use 注入）＋ raw.githubusercontent.com ＋ `git ls-remote`（经 http://127.0.0.1:7897 代理）＋ Wayback Machine（仅作旁证）。

## 2. 本机环境基线

| 项 | 实测值 |
| --- | --- |
| OS | Windows 10.0.26100 x64（Windows 11 24H2 内核版本号） |
| CPU | 16 逻辑核 |
| 工作目录 | `E:\Othergames\Nintendo Switch` |
| Python | 3.12.10 |
| git | 2.56.0.windows.2 |
| Node.js | v26.7.0 |
| .NET SDK | 10.0.400 |
| cmake / ninja / 7z | 已安装（scoop） |
| devkitPro | **已安装 `D:\devkitPro`**（官方安装器 v3.0.3 + 内置 MSYS2，2026-10-29；`switch-dev` 14 包 / 434.93 MiB；`aarch64-none-elf-gcc 16.1.0`、`libnx 4.12.0-1`、`switch-tools 1.13.1-1`；`du -sh /opt/devkitpro` = 2.5 GB；最小 NRO 构建已通过，见 §8） |
| WSL | 未安装任何 Linux 发行版 |
| 磁盘空闲 | C: 57.4 GB / D: 515.5 GB / E: 491.3 GB / Z: 326.8 GB |
| Ryujinx | `E:\Othergames\Nintendo Switch\Ryujinx-canary\Ryujinx.exe`（Canary 1.3.265，见 §5） |

## 3. 仓库总览表

| # | 集群 | 对象 | 精确版本 / commit | 许可证 | 证据 | 健康度 | 定位建议 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A | [devkitPro 安装器 + pacman 包体系](https://devkitpro.org/wiki/Getting_Started) | DevkitPro Updater v3.0.3（2018-06-03） | NOASSERTION | source-inspected | 停更（2018） | M0 安装入口（待实测） |
| 2 | A | [devkitPro/pacman-packages](https://github.com/devkitPro/pacman-packages) | HEAD b9e8b0de（2026-10-16） | NOASSERTION | source-inspected | 活跃 | 包定义/版本锁定旁证 |
| 3 | A | [switchbrew/libnx](https://github.com/switchbrew/libnx) | v4.12.0 · 7644c9b2 | ISC | source-inspected | 活跃 | 核心运行库（源码锁定） |
| 4 | A | [Atmosphere-NX/Atmosphere](https://github.com/Atmosphere-NX/Atmosphere) | 1.12.1 · 6b0c077b | GPL-2.0 | source-inspected | 活跃 | 真机测试环境（不混编/不分发） |
| 5 | A | [switchbrew/nx-hbloader](https://github.com/switchbrew/nx-hbloader) | v2.4.5 · 82b95122 | ISC | source-inspected | 活跃 | 真机 hbmenu 组件 |
| 6 | A | [nxlink (switchbrew/switch-tools)](https://github.com/switchbrew/switch-tools) | v1.13.1 · 22756068 | ISC | source-inspected | 低活跃 | 开发期上传/日志工具 |
| 7 | B | [DrFlyingPig/krkr-ns](https://github.com/DrFlyingPig/krkr-ns) | v0.1.0 tag→949faf9a（release 2026-09-14） | MIT | source-inspected | 活跃 | **M1 第一款原型** |
| 8 | B | [jvrcruzGAMES/RenpySwitch](https://github.com/jvrcruzGAMES/RenpySwitch) | HEAD 7824039a（无 tag） | NOASSERTION | source-inspected | 低活跃 | 候选但法律阻塞 |
| 9 | B | [Otorhin/Ren2Switch](https://github.com/Otorhin/Ren2Switch) | HEAD 5fce4a28（2023-09-04 停更） | NOASSERTION | source-inspected | 停更 | 不接入 |
| 10 | B | [clamintus/ONScripter-NX](https://github.com/clamintus/onscripter-nx) | v0.3.1 · a8439a86 | GPL-2.0-or-later | source-inspected | 低活跃 | 第二候选（视 GPL） |
| 11 | B | [xmoezzz/rfvp](https://github.com/xmoezzz/rfvp) | 0.7.0 · 99435f22 | MPL-2.0 | source-inspected | 活跃 | 研究项（不排期） |
| 12 | C | [natureglass/Brewser](https://github.com/natureglass/Brewser) | v0.1.1.31 · 8040580e | MPL-2.0 | source-inspected | 活跃 | **M4 首选评估对象** |
| 13 | C | [natureglass/nx.js_extended](https://github.com/natureglass/nx.js_extended) | 分支 nxjs-extended@90fbed8b | MIT | source-inspected | 低活跃 | 引擎侧参考（源码不完整） |
| 14 | C | [ETCHDEV/BurialNX](https://github.com/ETCHDEV/BurialNX) | v0.1.1 · c2c6691c | AGPL-3.0-or-later | source-inspected | 活跃 | 仅参考设计（禁引码） |
| 15 | C | [TooTallNate/nx.js](https://github.com/TooTallNate/nx.js) | v1.0.0-beta.7 · a649611a | MIT | source-inspected | 活跃 | HTML5/Canvas 底座 |
| 16 | C | [rexglue/rexglue-sdk](https://github.com/rexglue/rexglue-sdk) | v0.10.0 · f5337cdc | BSD-3-Clause | read-only | 活跃 | 旁支登记（无关） |
| 17 | C | [hedge-dev/XenonRecomp](https://github.com/hedge-dev/XenonRecomp) | 无 tag · ddd128bc | MIT | read-only | 停更 | 不列入第一阶段 |
| 18 | C | [hedge-dev/XenosRecomp](https://github.com/hedge-dev/XenosRecomp) | 无 tag · 990d03b2 | MIT | read-only | 低活跃 | 不列入第一阶段 |
| 19 | D | [rlaphoenix/NTON](https://github.com/rlaphoenix/NTON) | v3.0.1 · c5d543a9 | GPL-3.0-only | source-inspected | 活跃 | forwarder 对照工具 |
| 20 | D | [rlaphoenix/hacBrewPack](https://github.com/rlaphoenix/hacBrewPack) | v3.05 · 745b16ec（代码 2019） | GPL-2.0-only | source-inspected | 代码停更（2019） | **M3 自包含打包器**（子进程） |
| 21 | D | [jakcron/nstool](https://github.com/jakcron/nstool) | v1.9.2 · e89ea84b | MIT | source-inspected | 低活跃 | **M3 校验工具**（必装） |
| 22 | D | [TooTallNate/switch-nsp-forwarder](https://github.com/TooTallNate/switch-nsp-forwarder) | 0.0.8 · 61edd504 | MIT | source-inspected | 低活跃 | 模板参考（对照） |
| 23 | D | [autorunhq/autorun](https://github.com/autorunhq/autorun) | test-build-4 · 9b717050 | NOASSERTION | source-inspected | 活跃（实验） | 仅参考（Windows 运行时） |
| 24 | D | [autorunhq/autorun-horizon-dlls](https://github.com/autorunhq/autorun-horizon-dlls) | dlls · 4ab914bb | NOASSERTION | source-inspected | 活跃 | 仅参考 |
| 25 | D | [carafe-nx/carafe](https://github.com/carafe-nx/carafe) | v0.4.0 · 9b69701b | GPL-3.0-or-later | source-inspected | 活跃 | 流程参考（禁引码） |
| 26 | D | [Ryujinx 源流（网页侧旁证；结论由 Lead 定稿）](https://git.ryujinx.app/Ryubing/Canary) | Canary 1.3.265（+4e81a4c） | NOASSERTION | read-only | 留档 | 固定测试环境（本机留档） |

## 4. 分项审计

### 4.A Switch 基础工具链（devkitPro / libnx / Atmosphère / nx-hbloader / nxlink）

| 对象 | 精确版本 / commit | 许可证 | 证据等级 | 定位建议 |
| --- | --- | --- | --- | --- |
| [devkitPro 安装器 + pacman 包体系](https://devkitpro.org/wiki/Getting_Started) | DevkitPro Updater v3.0.3（2018-06-03） | NOASSERTION | source-inspected | M0 安装入口（待实测） |
| [devkitPro/pacman-packages](https://github.com/devkitPro/pacman-packages) | HEAD b9e8b0de（2026-10-16） | NOASSERTION | source-inspected | 包定义/版本锁定旁证 |
| [switchbrew/libnx](https://github.com/switchbrew/libnx) | v4.12.0 · 7644c9b2 | ISC | source-inspected | 核心运行库（源码锁定） |
| [Atmosphere-NX/Atmosphere](https://github.com/Atmosphere-NX/Atmosphere) | 1.12.1 · 6b0c077b | GPL-2.0 | source-inspected | 真机测试环境（不混编/不分发） |
| [switchbrew/nx-hbloader](https://github.com/switchbrew/nx-hbloader) | v2.4.5 · 82b95122 | ISC | source-inspected | 真机 hbmenu 组件 |
| [nxlink (switchbrew/switch-tools)](https://github.com/switchbrew/switch-tools) | v1.13.1 · 22756068 | ISC | source-inspected | 开发期上传/日志工具 |

#### A.1 devkitPro 安装器与包体系

- **安装器 v3.0.3 是 2018-06-03 的产物**：`devkitPro/installer` HEAD `5d820f47efb0a7802d71bfcb0249b5ff80c8b759`（最后 push 2023-09-11），NSIS 脚本 `PRODUCT_VERSION 3.0.3`、`RequestExecutionLevel admin`、默认安装到 `C:\devkitPro`，内置 MSYS2 2.10.0（`msys-2.10.0.1.7z`）。下载资产 `https://github.com/devkitPro/installer/releases/download/v3.0.3/devkitProUpdater-3.0.3.exe`（196,304 B）实测 HTTP 200。
- **阻塞事实**：`https://pkg.devkitpro.org/packages/dkp-libs.db`、`https://pkg.devkitpro.org/packages/`、`https://downloads.devkitpro.org/devkitProUpdater-3.0.3.exe` 均实测 **HTTP 403（Cloudflare）**（curl 带 UA / env_download 两种方式），导致 `switch-dev` 组成员、各包版本与哈希、包签名数据库均无法取证。
- **包库滚动且无快照**：devkitPro wiki（Getting_Started / devkitPro_pacman 两页已逐页读取）只描述 `[dkp-libs]`/`[dkp-windows]` 两个滚动仓库与 `pacman -Syu`，全文无 snapshot/versioned repository 记载；`pacman-packages` 仓库 HEAD `b9e8b0de`（2026-10-16，"devkitPPC: release 51"），271 个 PKGBUILD 各自声明许可、无仓库级 LICENSE；`switch-sdl2 2.28.5-4`、`switch-freetype 2.13.3-1` 可查到，但 `switch-tools`/`uam`/`hactool` 的 PKGBUILD 不在公开仓库。
- **devkitA64 二进制代际**：pacman 元包 `devkitA64 r30-1` 要求 `devkita64-gcc>=16.1.0-1`、`binutils>=2.46.0-1`、`newlib>=4.6.0.20260123-4`，比 buildscripts 最新 release（`devkitA64_r29.1`，GCC 15.2.0）更新 → **源码 tag 不能代表 pacman 实际版本**；buildscripts README 明确自建工具链 "for personal use only and may not be distributed by entities other than devkitPro"，不能作为发布物。
- **Windows 环境依赖**：安装器会写 HKLM 变量 `DEVKITPRO=/opt/devkitpro`（另有 DEVKITARM/DEVKITPPC）、把 `C:\devkitPro\msys2\usr\bin` 前插系统 PATH，属机器级改动，需管理员权限，建议在干净环境/专用账户中执行（详见 §8）。

#### A.2 核心库与测试环境

- **libnx（ISC，核心依赖）**：`v4.12.0 = 7644c9b26099aa2d2145bc72a21ee24190e92085`（2026-09-28），HEAD `b156b477…`（2026-10-19）；pacman 包 `libnx 4.12.0-1` 与该 tag 一致，可源码锁定。
- **Atmosphère（GPL-2.0，只作真机测试环境）**：`1.12.1 = 6b0c077b4c608a3a2ee712b8dc35fee87ceb62e8`（2026-10-16）。不得与 GalNX 代码混编、不得随 GalNX 分发；仅作为 CFW 测试平台的背景依赖。
- **nx-hbloader（ISC）**：计划草案写的 `Atmosphere-NX/nx-hbloader` 已 404，**真实仓库为 `switchbrew/nx-hbloader`**，`v2.4.5 = 82b95122c5ae8dc059bf23893ba7623c72c86773`（2025-11-15，417★）。
- **nxlink（ISC）**：属 `switchbrew/switch-tools`，`v1.13.1 = 22756068dd0ed6ff9734c59cb4f99ebd3f62555b`（2024-10-23），同时提供 elf2nro/elf2nso/nacptool/npdmtool 等；`README` 为空（0 B），能力只能从源码取证：`nxlink --address/-a`、`--path/-p`、`--args`、`--server/-s`（上传后启动服务器回收 NRO 的 stdout/stderr），netloader 端口 28280/28771。devkitPro 包的 `switch-tools` 版本未取证（PKGBUILD 不在公开仓库）。
- **真机测试链依赖**：hbmenu 3.6.1 / nx-hbloader 2.4.5 随 Atmosphère 1.12.1 提供，`nxlink -s app.nro` 是唯一可脚本化回收日志/退出码的开发期通道（详见 §4.D）。

#### A.3 本轮已确认的风险

- `pkg.devkitpro.org` 403 是**安装/更新/包缓存**三类操作的共同前置阻塞；M0 必须先做可达性探测并记录结果。
- 2018 安装器内置的 MSYS2 2.10.0 可能无法完成今天的一次性安装（旧 pacman 同步新包源）；备选方案（现代 MSYS2 + dkp 仓库、Docker 镜像）必须写入 M0 计划。
- portlibs 版本偏旧（如 mesa 20.1.0、libvpx 1.8.0）；若目标引擎需要较新 OpenGL/视频解码，需上游自行构建 portlibs（后续阶段）。
- 计划草案 §7.1 的两个链接需修正（nx-hbloader、nxlink），见 §9。

### 4.B Galgame 引擎移植（KiriKiri / Ren'Py / ONScripter / FVP）

| 对象 | 精确版本 / commit | 许可证 | 证据等级 | 定位建议 |
| --- | --- | --- | --- | --- |
| [DrFlyingPig/krkr-ns](https://github.com/DrFlyingPig/krkr-ns) | v0.1.0 tag→949faf9a（release 2026-09-14） | MIT | source-inspected | **M1 第一款原型** |
| [jvrcruzGAMES/RenpySwitch](https://github.com/jvrcruzGAMES/RenpySwitch) | HEAD 7824039a（无 tag） | NOASSERTION | source-inspected | 候选但法律阻塞（不接入） |
| [renpy/renpy](https://github.com/renpy/renpy) + [renpy-build](https://github.com/renpy/renpy-build) | 8.5.3.26051504 · 39895c1e（build：7bfab40c） | MIT 主体 + LGPL/MPL/Apache/BSD 组件（无根 LICENSE，见 `license.rst`） | source-inspected | **官方源码独立移植方向**（先 go/no-go 探针） |
| [Otorhin/Ren2Switch](https://github.com/Otorhin/Ren2Switch) | HEAD 5fce4a28（2023-09-04 停更） | NOASSERTION | source-inspected | 不接入 |
| [clamintus/ONScripter-NX](https://github.com/clamintus/onscripter-nx) | v0.3.1 · a8439a86 | GPL-2.0-or-later | source-inspected | 第二候选（视 GPL） |
| [xmoezzz/rfvp](https://github.com/xmoezzz/rfvp) | 0.7.0 · 99435f22 | MPL-2.0 | source-inspected | 研究项（不排期） |

#### B.1 `DrFlyingPig/krkr-ns` —— 第一款原型首选

- **版本与许可**：MIT；HEAD `949faf9a874f54b149a3fe5382cfccb38afb99bb`（2026-10-16，21★）。`v0.1.0` tag 指向 HEAD，release v0.1.0（published 2026-09-14）附 `krkrsdl2.nro`（29.6 MB）→ **发布产物与代码不可按 tag 唯一对应**，引用时必须同时记录 release 时间与 SHA-256。
- **组成**：vendored `krkrsdl2`（MIT，上游 `main` 124bdf84，2026-10-01）+ `krkrz`（KiriKiri Z，自定义宽松许可，b11c43a）；SDL2 层 + KiriKiri Z 引擎。
- **构建依赖**：devkitPro 工具链 + CMake 3.31.6 + **自建 FFmpeg 7.1**（LGPL 模式，源码 sha256 `40973d44970dbc83ef302b0609f2e74982be2d85916dd2ee7472d30678a7abe6`，`--disable-gpl`），且需要仓库外的 `Switch.toolchain.cmake`（来自 `KRKR-ns-tools`）与兄弟仓库 `WA2-ns` 的默认路径；无 CI。
- **对 M1 的含义**：构建配方是本轮最大不确定性（外部 toolchain 文件、FFmpeg 配置、兄弟仓库路径都要固化进 GalNX 的 build backend 配置），建议 M1 的第一步不是改代码而是「在干净 workspace 复现上游 release」。

#### B.2 `jvrcruzGAMES/RenpySwitch` —— 法律硬阻塞（待授权）

- 仓库及父仓库 `knautilus/RenpySwitch` **无任何 LICENSE 文件**；HEAD `7824039a`（2026-08-10，2★，2026-08-09 创建）；NXPython + Ren'Py 8.3.4 流水线，提供 Docker + CI（工程上最可复现）；README 无真机验证声明。
- **结论**：在取得权利人书面授权前不得接入、不得分发衍生二进制；仅登记为「候选但法律不可用」。

#### B.3 `Otorhin/Ren2Switch` —— 不接入

- 无许可证；HEAD `5fce4a28`（2023-09-04）已停更；父仓库 `uyjulian/renpy-switch` 已 archived；Python 2.7 代际；14 个 tag 为 2019–2020 上游遗留。**不接入**。

#### B.4 `clamintus/ONScripter-NX` —— 第二候选（视 GPL 决策）

- GPL-2.0-or-later；`v0.3.1 = a8439a86393f74c503d28df176f010ca544af56f`（2026-01-14，37★）；构建最简单（普通 `make`）。
- **风险证据**：GitHub release assets 含 `tsukihime` / `kagetsu_tohya` 商业游戏数据 zip（已由 release API 证实）→ GalNX 禁止复用其资产；Sazanami Gothic 字体许可未核实；`switch-sdl2_ttf` 需修复后重打包。
- **结论**：若项目接受 GPL-2.0-or-later 传染（引擎本体作为独立 NRO、与工作台隔离分发），可作为第二引擎；否则降级为研究参考。

#### B.5 `xmoezzz/rfvp` —— 研究项

- MPL-2.0；`0.7.0 = 99435f22e94eaec27c0c1b9f22cc2a6b1910d7d1`（2026-10-19，151★），HEAD `9f07adef`（2026-10-25 pre-release）。
- Rust `nightly-2026-02-01` + build-std + 自定义 target；README 明确 **Switch 从未真机运行**（仅 Ryujinx 60 fps），releases 无 Switch NRO（需 CI artifact 或本地构建）→ 研究项，不排入 M1–M3。

#### B.6 接入排序建议

1. **krkr-ns（M1）**：唯一同时满足「MIT + 活跃 + 已有可运行 NRO + 有真实 galgame 生态」的候选；先复现构建、再做首款游戏冒烟。
2. **ONScripter-NX（M2/M3 备选）**：构建最简单，但需 GPL 决策与资产隔离；release 自带商业游戏数据必须剔除。
3. **rfvp**：仅跟踪，不排期。
4. **RenpySwitch / Ren2Switch**：无许可证 → 不接入（社区移植仅作技术差异参考）。

#### B.7 Ren'Py 官方源码独立移植专项（补充审计，2026-10-29）

- **基线**：`renpy/renpy` 最新 tag `8.5.3.26051504 = 39895c1e017f0b36ffea2447d97eccd69d76ee1c`（2026-05-16，annotated tag oid `3c707741…`），该发布仍用 **SDL2**；master 已迁 SDL3（`setup.py` packages="sdl3"）→ 移植必须锁 8.5.3 系，不能跟 master。`renpy-build` 同 tag = `7bfab40c1174f622f644b24669afd5fb167fbb79`（2026-05-13），锁定 Python 3.12.8 / FFmpeg 4.3.1 / SDL2 2.0.20 / freetype 2.13.3 / harfbuzz 8.0.1 / libpng 1.6.43。
- **许可**：两个官方仓库**都没有根 LICENSE**（`/license` 404），许可只写在 `sphinx/source/license.rst` 与 renpy.org 文档：主体 MIT，但原文明确「Portions of Ren'Py are derived from … LGPL, so Ren'Py games must be distributed in a manner that satisfies the LGPL」；依赖含 FFmpeg/Fribidi/chardet/libusb 等 LGPL，另有 MPL-2.0/Apache-2.0/BSD/Zlib/Python License。生成项目文件（未修改）为 CC0-1.0。接入前必须按该文件生成 NOTICE 并保证 LGPL 组件可替换。
- **无 Switch 平台**：`renpy-build/build.py` 平台表仅 linux(x86_64/aarch64)/windows/mac/android/ios/web；`runtime/librenpython.c` 只有 LINUX/MAC/WINDOWS/IOS/WEB 宏；README.rst 原文「Setup.py does not support cross-compiling」→ 独立移植 = **新写平台后端 + 平台层**，不是改开关。
- **技术断点（C1–C10 评估表见专项文件）**：唯一硬阻塞 = **CPython 3.12.8 交叉编译到 devkitA64/newlib**（C 扩展可 AOT、SDL2/GLES 有 portlib、romfs/scandir/存档/音频/字体为中等可解）。建议先做 **4–6 周 go/no-go 探针**（PC 官方构建 → CPython 交叉 REPL → SDL2 窗口三件套），估计 3–5 人月最小可跑、6–12 人月可发布；并行备选 = Switchroot Android + 官方 Android 构建（最干净、可立即玩，但需用户设备已 root）。
- **证据边界**：本轮未做任何真机/模拟器运行，未验证 Switch 上 threads/romfs 细节、`switch-sdl3` portlib 可用性、SDK 内置 demo 资产许可 → 均标 `not-verified`。
- **完整数据**：`docs/audit/04-renpy-official.md`（7 条记录 × 22 字段 + 专项 A–G）。

#### B.8 引擎路线复核与新候选（v1.3 补充，`docs/audit/06-engines-refresh.md`，14 条记录）

本轮对 00/01/04 的引擎结论做了联网刷新，**最重要更正**：`krkrsdl2/krkrsdl2` 上游本体已有官方 Switch 目标——`CMakeLists.txt` 含 `if(NINTENDO_SWITCH)` 分支（`SWITCH_APP_NAME "Kirikiri SDL2"`、`SWITCH_AUTHOR uyjulian`、`SWITCH_VERSION v2.0.0`、nacptool + elf2nro），`.github/workflows/ci.yml` 矩阵含 `switch`（容器 `devkitpro/devkita64:20241023`），release tag `latest` 附 `krkrsdl2.nro` 12,011,585 B。但其 README **完全不提 Switch** 且声明不支持未修改商业游戏 → 属「有实现、无文档」，支持可能无公告移除；且该 NRO 由 `-DEMBED_DATA_PATH=data.xp3` 构建，是**单游戏内嵌**形态，不含多游戏启动器。

→ 因此 `krkr-ns` 的定位从「唯一 KiriKiri Switch 路径」更正为**上游之上的产品化启动器**（增量 = 启动器 UI、存档隔离、E-mote/AlphaMovie/LayerExRaster 插件、音视频修复；MIT，`949faf9a…`，2026-10-16），其 release `v0.1.0` 的 `published_at`（2026-09-14）早于 `created_at`（2026-10-16）、tag 已指向当前 HEAD → **锁版本必须用 commit SHA 并自行重建**。

新增候选（06 §2 全部 `source-inspected`）：

| 仓库 | 许可 | 锁定版本 | 产物/体量 | 定位与风险 |
| --- | --- | --- | --- | --- |
| `wetor/ONScripter-jh-Switch` | GPL-2.0 | `v21.2.1`（annotated `15a6fec3…` → commit `573301c1…`，2026-02-01） | `ONScripter_Switch.nro` 16,735,572 B | ONScripter Yuri 系；中文 UI + 游戏浏览器；221★，2026-02 更新；ONScripter 双实现中更活跃者 |
| `Erige005/Kirikiroid2-NX` | KiriKiri 自定义 BSD-style（NOASSERTION，非 SPDX） | `v1.0.1 = e96b6034…`（2026-10-18） | `Kirikiroid2-NX.nro` 42,338,934 B | Kirikiroid2 1.3.9 移植；插件缺 E-mote/motion player/scriptsEx/layerExRaster/sqlite 等；构建链最重（8 个 portlibs 脚本 + 需官方 APK 资源）；2026-09-30 新建、单人维护 |
| `xmoezzz/siglus_rs` | MPL-2.0 | `5f358ef1…`（pre-release） | `siglus-switch.nro` 14,531,824 B | SiglusEngine Rust 重实现；deko3d + WGSL→GLSL 渲染链；未真机验证 → 研究项 |
| `krkrsdl2/krkrsdl2`（上游本体） | MIT | `main HEAD 124bdf84…`（2026-10-01）或 CI 镜像 `devkitpro/devkita64:20241023` | `krkrsdl2.nro` 12,011,585 B | **第一梯队入口**：官方 CI 可复现，适合验证「自有 data.xp3 → NRO」最小闭环；README 未承诺 Switch |

其他复核结论：①`clamintus/ONScripter-NX` 的 `COPYING` 无 “or later” 条款 → 判 **GPL-2.0-only**，release 内嵌月姬/歌月十夜商业数据 zip **禁止下载/再分发/用作测试数据**；②Ren'Py 官方 8.5.3.26051504 仍是最新稳定（SDL2），master `8.99.99` 已迁 SDL3 → **基线锁 8.5.3，禁止 master**（详见 B.7）；4 个社区移植与 NXPython 逐一复核**仍全部无 LICENSE**；③rfvp 复核确认 README 自述「从未真机运行、仅 Ryujinx 60 fps」→ 维持研究项。

**接入排序（v1.3 修订，替代 B.6）**：① `krkrsdl2` 上游自建（MIT + 官方 CI，先验证可复现）→ ② `krkr-ns`（启动器产品化，实验性）→ ③ ONScripter 双实现二选一（GPL-2.0，优先 `ONScripter-jh-Switch`）→ ④ `Kirikiroid2-NX`（非 SPDX 许可 + 重构建链，第三梯队）→ ⑤ rfvp / siglus_rs（研究项，不进首批）→ ⑥ Ren'Py 独立移植（长期，CPython 交叉硬阻塞）。社区 Ren'Py 移植与 NXPython **一律不接入**。

**合法测试资源**：首选自建 Ren'Py 工程（生成项目文件 CC0-1.0）；其次 `krkrsdl2-kag3-demo`（KAG3 自定义「自由修改/分发」条款，非 SPDX，内嵌 Ume Gothic O5 字体许可需单独核实）；Ren'Py 官方 SDK 示例 `the_question`/`tutorial` 资产无明确许可 → 仅本地测试、禁止再分发。

**证据边界**：06 全部条目为只读/源码级审计，**未在真机或模拟器运行任何引擎 NRO**（U1）；krkrsdl2 的 Switch 支持无文档承诺（U4）；K2NX/siglus_rs 的运行声称仅来自 README（U6/U5）。

### 4.C Web / JS 运行时（Brewser / nx.js / BurialNX / 旁支）

| 对象 | 精确版本 / commit | 许可证 | 证据等级 | 定位建议 |
| --- | --- | --- | --- | --- |
| [natureglass/Brewser](https://github.com/natureglass/Brewser) | v0.1.1.31 · 8040580e | MPL-2.0 | source-inspected | **M4 首选评估对象** |
| [natureglass/nx.js_extended](https://github.com/natureglass/nx.js_extended) | 分支 nxjs-extended@90fbed8b | MIT | source-inspected | 引擎侧参考（源码不完整） |
| [ETCHDEV/BurialNX](https://github.com/ETCHDEV/BurialNX) | v0.1.1 · c2c6691c | AGPL-3.0-or-later | source-inspected | 仅参考设计（禁引码） |
| [TooTallNate/nx.js](https://github.com/TooTallNate/nx.js) | v1.0.0-beta.7 · a649611a | MIT | source-inspected | HTML5/Canvas 底座 |
| [rexglue/rexglue-sdk](https://github.com/rexglue/rexglue-sdk) | v0.10.0 · f5337cdc | BSD-3-Clause | read-only | 旁支登记（无关） |
| [hedge-dev/XenonRecomp](https://github.com/hedge-dev/XenonRecomp) | 无 tag · ddd128bc | MIT | read-only | 不列入第一阶段 |
| [hedge-dev/XenosRecomp](https://github.com/hedge-dev/XenosRecomp) | 无 tag · 990d03b2 | MIT | read-only | 不列入第一阶段 |

#### C.1 `natureglass/Brewser` —— M4 首选评估对象

- **版本与许可**：LICENSE 为 **MPL-2.0**（全文已读），但 `package.json` 声明 MIT → **以 LICENSE 为准（MPL-2.0）**；`v0.1.1.31` tag = `8040580e92e40a60f704a6478ee296b105212f1b`（2026-09-17，15★）。
- **发布产物**：release 名 `v0.1.131`，published 2026-09-15（**早于 tag commit 日** → tag 可能后移；但 `dist/checksums.txt` 与 release asset digest 一致）：`brewser.nro` 76,546,123 B，sha256 `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13`；`brewser-forwarder.nsp` 363,224 B，sha256 `1e3268fe83d45a811c38366645ed59854d6a0a4243de9c97ab156ffdc1a33af8`。
- **构建方式**：默认 `make` 只需 node/npm/python（复用预编译 engine NRO），**重建引擎才需要 devkitPro**；运行时自研 DOM/CSS/layout + V8 JIT + Skia + Mesa Nouveau（WebGL 1/2）；需 Atmosphère CFW + hbmenu application mode。
- **对 M4 的含义**：无需先搭 devkitPro 就能验证「Web 游戏能否跑」，是 M4 成本最低的评估入口；但它是黑盒发行物（引擎源码不可得），GalNX 只能消费其 NRO，不能修补其运行时。

#### C.2 `natureglass/nx.js_extended` —— Brewser 的引擎侧（源码不完整）

- MIT（fork of `TooTallNate/nx.js`）；`main` HEAD `f41fb550…`（= 上游 v1.0.0-beta.6，2026-07-08，1★）；Brewser 实际使用分支 `nxjs-extended@90fbed8b7bb2f442b38521878a2aa315080bce1a`。
- engine = `switch-v8 15.0.243-9`（无 ICU、jitless、无 WASM）+ `switch-skia 149-3`（pin 不可随意升级）+ Mesa Nouveau；**私有 `@switch-web/runtime` 源码不可得**（npm/GitHub 均 404）→ shell 层无法完整审计；构建链重（devkitPro + GHCR 私有包）→ 不作为发布依赖。

#### C.3 `ETCHDEV/BurialNX` —— 仅参考设计（AGPL 禁引代码）

- AGPL-3.0-or-later；`v0.1.1 = c2c6691c0c73a2fbefadadd2bde8ecbe7d3f013b`（2026-10-19，2★，prerelease）。README IMPORTANT 原文：**specialized loader, not universal MV player**（单作品专用，不是通用 MV 播放器）→ GalNX 只能参考其分层/存档/诊断设计，**禁止引用其代码**（AGPL 传染）。

#### C.4 `TooTallNate/nx.js`（计划未列，真实上游）

- MIT；`v1.0.0-beta.7 = a649611a1a4daca09924cd1a436c7ca786f91592`（2026-10-13，269★，12 open issues）；发布 `nxjs.nro` 56,436,901 B；V8 + Skia + WebGL2 + FFmpeg，**无 DOM/CSS**，不是浏览器 → 可作为 HTML5/Canvas 底座。

#### C.5 §7.7 旁支登记

- `rexglue/rexglue-sdk`：BSD-3-Clause，`v0.10.0 = f5337cdc947ff6d4c4196737e2c807a48f2a1fc2`（2026-10-02，1200★）→ 与 Galgame 路线无关，仅登记。
- `hedge-dev/XenonRecomp`：MIT，HEAD `ddd128bc`，最后 push 2025-08-04（约 14 个月未更新）→ 不列入第一阶段。
- `hedge-dev/XenosRecomp`：MIT，HEAD `990d03b2`，最后 push 2026-03-12（低活跃）→ 不列入第一阶段。

#### C.6 Brewser 公开的 API 覆盖（官方自称，未实测）与 M4 差距

| 能力 | 官方自称（未实测） | 对 Galgame 的影响 |
| --- | --- | --- |
| DOM / HTML / CSS | 约 84% / 80% / 84% | TyranoScript、部分浏览器 AVG 可用；复杂 CSS 布局有风险 |
| WebGL 1 / WebGL 2 | 约 92% / 85% | 2D Canvas/WebGL 游戏大概率可用；Unity WebGL2 官方声明不支持 |
| Web Audio | graph 约 70% | 音乐/音效可用，需实测延迟与解码格式 |
| storage | **无 sessionStorage / Cache API** | 依赖 localStorage 的存档方案需 shim 或改用 GalNX 自己的存档策略 |
| Node / fs | 页面无 `require`/`fs` | **RPG Maker MV 不能直接跑**，需要 Node/fs 兼容层（M4 主要工作量） |

M4 前置风险：①`@switch-web/runtime` 与 `brewser-runtime-v8` 不可得，运行时内嵌 V8/Skia 版本只能由分支构建脚本推断；②RPG Maker MV 依赖 Node/fs，Brewser 不能直接跑，需先做兼容层可行性验证；③MPL-2.0 义务（修改文件需开源）与黑盒发行物的边界需在 M4 决策前明确；④无真机测试证据，只有发行者声明。

#### C.7 Web 冒烟实测（2026-10-29，补充实验）

实验记录：`docs/experiments/web-01-brewser-smoke.md`（158 行，verification_level: **not-verified**）；证据 `workspaces/web-01/evidence/`（6 张截图 + 6 份日志，gitignored）。目的：在 M4 之前用官方 Brewser NRO 做最小冒烟，验证 Web 路线在当前测试环境能否至少跑起来。

| 步骤 | 结果 |
| --- | --- |
| 资产校验 | brewser.nro 76,546,123 B，sha256 `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13`，与 release digest / checksums.txt 三方一致 |
| 对照物（普通 homebrew） | nx-hbmenu v3.6.1（2,455,539 B）、hb-appstore v2.3.2（11,104,808 B）均 `Application Loaded` 并渲染画面 → 模拟器 homebrew 加载链路健康 |
| Brewser | 3 次均停在 `LoadGuestApplication: Loading as homebrew.` 之后、guest 启动之前；无 GetNpdm/LoadNsos/`Application Loaded`；SD 卡无 `switch/brewser/` seed-fingerprint、无 shell seed → 主程序从未执行 |
| 上游 nx.js beta.7 对照 | 同样停滞（2 次，56,436,901 B，sha256 `602ced49d93afc1704c8dd14da199b151201cb9bcd55ce3b75738f5ae39637ae`）→ 属 nx.js 系 NRO 与 Ryujinx 1.3.265 的兼容问题，非 Brewser 独有 |
| Ryujinx 自身异常 | 约 127 s 后 `Ryujinx.Common.RyujinxException: The HLE Process map did not have a process with ID 0. Are you missing firmware?`（栈 ProcessLoader.get_ActiveApplication ← DiscordIntegrationModule.Use ← ProcessLoader.LoadNxo）；关 `enable_discord_integration=false` 仍复现 → 模拟器 bug，不归因 Brewser |
| 差异线索 | 失败 NRO 的 NRO header 代码段字段约 44 MB（nxjs 0x2a26000 / brewser 0x2a6b000），正常对照 1.7 MB / 7.3 MB；根因未定位 |

结论与边界：①本机 Ryujinx Canary 1.3.265 **不能**作为 M4 Web 验证工具（nx.js 系 NRO 加载阻塞，需单独立项）；②**不能**据此判定 Brewser/Web 路线可行或不可行（Brewser 运行时能力 V8/Skia/WebGL/DOM/CSS/JS/autorunApp 全部未验证）；③M4 验证改走：真机（Atmosphère 1.10+ + hbmenu，完整内存 application mode）优先，或换模拟器/版本并用 hbmenu/appstore 作“加载链路健康检查”对照；④可复用验证流程：portable + `runas /trustlevel:0x20000` 去提权 + `sdcard/switch/` 放 NRO + `window_capture` 截图 + 读 `portable/Logs/`；⑤环境坑：Ryujinx 不能以管理员启动；`Config.json` 开 debug/trace 日志会导致 CLI NRO 参数不被处理（已还原）。

#### C.8 Citron Neo 测试后端审计与 Web 冒烟 v2（2026-10-29 补充实验）

**Citron Neo 审计**（`docs/audit/07-web-citron.md`）：仓库 `citron-neo/emulator`，SPDX **GPL-3.0-or-later**，HEAD `c3aa70f81e15ea97ee85b6a9a71cbf75d370851e`（2026-10-25T23:55:59Z），597★/93 open，**无公开 CI**；最新 release tag `2026-04-27 = 0076ee8f`，但其 Windows 资产由 nightly commit `0237a9b88a5047b9940ab3b3c3412d71cf8e50be`（2026-04-27）构建 → **tag 与资产不对应，版本锁定必须锁资产 SHA-256**：`Citron-windows-nightly-0237a9b88-x64-msvc.zip` 40,497,628 B，sha256 `0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb`。仅作外部开发/测试工具、不捆绑不分发其代码 → GPL 不传染 GalNX。

**Web 冒烟 v2 实测结果**（`docs/experiments/web-02-citron-smoke.md`，**2/2 复现**）：同一 `brewser.nro`（76,546,123 B，sha256 `8ce31f5b…`）在 Citron 上**完整运行**——窗口标题 `citron Nightly | 0237a9b88 | brewser (64-bit)`，探针页 DOM+CSS+inline JS+`setInterval`+`requestAnimationFrame`+Canvas2D+**WebGL**+`localStorage` 全部通过（状态行 `localStorage:1 | WebGL:OK OpenGL ES 3.2 Mesa 20.1.0-rc3`，两次截图 TICKS 17→75、frame 219→1119），Brewser 完成 `sdmc:/switch/brewser/` 首次 seed（`seed-fingerprint`、`shell/home.html` 生成）。hbmenu 对照与 Ryujinx 一致（`Error: launchInit() failed.`，application 模式预期）。

结论与边界：①**web-01 的阻塞归因于 Ryujinx 1.3.265 环境问题，不是 Brewser/Web 路线问题** → Web 路线模拟器侧已打通；②Citron 无真实固件（硬编码 22.0.0-3.0）、运行期 112 条 `shader_recompiler ... Assertion Failed` 非致命、兼容性列表为空 → **模拟器≠真机**（NVIDIA Vulkan vs Tegra X1/Mesa Nouveau）；③未验证：输入/音频/联网（BSD socket 日志 `STUBBED`）/WebGL 像素级/长稳/商业游戏；④M4 冒烟三件套 = 窗口标题含 `brewser (64-bit)` + 日志含 `Loading brewser (01F5905036D20000)`/`Booting game: 01F5905036D20000 | brewser (64-bit)` + `sdmc:/switch/brewser/seed-fingerprint` 生成；⑤Ryujinx 降为第二意见/回归对照。

### 4.D NSP 打包与测试环境（nstool / hacBrewPack / NTON / forwarder / Ryujinx）

| 对象 | 精确版本 / commit | 许可证 | 证据等级 | 定位建议 |
| --- | --- | --- | --- | --- |
| [rlaphoenix/NTON](https://github.com/rlaphoenix/NTON) | v3.0.1 · c5d543a9 | GPL-3.0-only | source-inspected | forwarder 对照工具 |
| [rlaphoenix/hacBrewPack](https://github.com/rlaphoenix/hacBrewPack) | v3.05 · 745b16ec（代码 2019） | GPL-2.0-only | source-inspected | **M3 自包含打包器**（子进程） |
| [jakcron/nstool](https://github.com/jakcron/nstool) | v1.9.2 · e89ea84b | MIT | source-inspected | **M3 校验工具**（必装） |
| [TooTallNate/switch-nsp-forwarder](https://github.com/TooTallNate/switch-nsp-forwarder) | 0.0.8 · 61edd504 | MIT | source-inspected | 模板参考（对照） |
| [autorunhq/autorun](https://github.com/autorunhq/autorun) | test-build-4 · 9b717050 | NOASSERTION | source-inspected | 仅参考（Windows 运行时） |
| [autorunhq/autorun-horizon-dlls](https://github.com/autorunhq/autorun-horizon-dlls) | dlls · 4ab914bb | NOASSERTION | source-inspected | 仅参考 |
| [carafe-nx/carafe](https://github.com/carafe-nx/carafe) | v0.4.0 · 9b69701b | GPL-3.0-or-later | source-inspected | 流程参考（禁引码） |
| [Ryujinx 源流（网页侧旁证；结论由 Lead 定稿）](https://git.ryujinx.app/Ryubing/Canary) | Canary 1.3.265（+4e81a4c） | NOASSERTION | read-only | 固定测试环境（本机留档） |

#### D.1 两条打包路线对比（决定 M3 首目标）

| 方案 | 机制 | 体积 / 耗时 | 图标·名称·存档 | 主要风险 | 结论 |
| --- | --- | --- | --- | --- | --- |
| forwarder（NTON / switch-nsp-forwarder） | ExeFS 内放小启动器，运行 SD 卡上的 NRO | 安装体积约 1 MB、打包秒级 | 可换图标/名称；存档仍跟随 NRO；TitleID 随机或由 NRO 路径 SHA-256 派生 | **NRO 路径硬编码**，SD 卡变动即失效；README 原文警示「can result in a console ban」；签名无效必须 CFW；任天堂已 DMCA 此类方案 | 降级为**对照实现**，不作首目标 |
| 自包含（hacBrewPack + nstool） | ExeFS 放自研启动器，RomFS 打包游戏数据，生成完整 NSP | 体积≈游戏数据、打包分钟级 | 完整控制图标/名称/TitleID/存档策略，符合「HOME 点图标即玩」 | 需用户自备 `prod.keys`；必须 CFW + sigpatches 才安装；hacBrewPack 代码停在 2019；RSA-PSS 输出非确定性 | **GalNX 主方向**（M3） |

结论与 §0 判断 5 一致：**M3 首个 target 从计划草案的 forwarder 改为自包含**，forwarder 仅保留为对照/过渡能力。

#### D.2 自包含打包器：`rlaphoenix/hacBrewPack`（唯一可用实现）

- **版本与许可**：GPL-2.0；`v3.05 = 745b16ecfc9ce055743067d200572204cb2aac6c`（代码最后提交 2019-10-13，社区镜像于 2026-09-15 重建；原 `The-4n/hacBrewPack` 已删除）→ 只能以**独立子进程**调用，不得链接进 GalNX 二进制；分发聚合产物时需附源码/许可文本。
- **输入**：`build/exefs/main`（NRO/NSO）、`main.npdm`、`control.nacp`（含 256×256 JPEG 图标）、可选 logo、RomFS 目录。CLI：`--nspdir --ncadir --tempdir --backupdir --exefsdir --romfsdir --logodir --controldir --noromfs --nologo --keygeneration --keyareakey --sdkversion`（默认 `000C1100`）`--plaintext --keepncadir --nosignncasig2 --titleid --titlename --titlepublisher --nopatchnacplogo`。
- **密钥依赖**：`header_key` + `key_area_key_application_xx` → 由用户从自有主机提取（Lockpick_RCM），GalNX **不存储、不分发、不写入 CI 日志**，仅从用户指定的本地路径读取。
- **输出非确定性**：RSA-PSS 随机盐 → 同一输入两次打包的 NSP 文件哈希不同；「可复现构建」只能定义到**内容层**（nstool 提取出的 NCA/RomFS 哈希一致），不能定义到文件层。M3 验收标准必须按此表述。
- **Windows MAX_PATH 实测**：258/259 字符成功、260 失败 → 构建目录用短路径 `.build/<TitleID>/`，并做 ≤259 B 预检（与 Carafe 的 `path_limit 259B` 一致）。
- **就地修改输入**（`npdm.c`/`nacp.c`）→ 必须传副本目录，不得指向源缓存或用户游戏目录。

#### D.3 打包前校验与集成顺序

1. `nstool`（MIT，`v1.9.2 = e89ea84bd70c11b67ebec9153fb4a446f18a9d3d`，2024-10-14，558★；默认分支 `development-tip` → 锁版本只认 tag）做输入/输出校验：`-y` 用内置公钥验签（不需 keys）、`--showlayout`、`-x` 提取。支持 PFS0/HFS0/RomFS/NCA/NSP/XCI/META/NACP/CNMT/CERT/TIK/NSO/NRO/INI1/KIP1。2024-10 后无提交 → 若未来格式演进需自行维护 fork。
2. `hacBrewPack`（子进程，传副本、短路径、捕获 stdout/stderr、非零退出即失败）。
3. 产物再经 `nstool -y` 校验 + 记录内容层哈希。
4. `NTON`（GPL-3.0，`v3.0.1 = c5d543a9…`）仅用于**对照实验**，不进生产路径；其 README 对 forwarder 的封禁/DMCA 警告作为风险证据引用。
5. 真机安装走 **DBI MTP**（本轮未实测）。

#### D.4 测试环境固定（模拟器 + 真机）

- **Ryujinx 固定策略**：`Ryujinx.exe` + `ryujinx-Canary-1.3.265.zip` 只读留档；启动前校验 SHA-256（见 §5.1/§5.2）；断网（hosts 或防火墙屏蔽 `update.ryujinx.app`、`git.ryujinx.app`）并禁用自动更新；版本号写进 JSONL 记录。
- **可自动化采集**：①外部 wrapper 采集模拟器 stdout/stderr + exit code；②模拟器日志目录 `portable/Logs/`（文件名 `Ryujinx_Canary_1.3.265_<date>_<time>.log`）；③`nxlink -s app.nro` 回收 NRO 的 stdout/stderr（开发期内循环）；④真机日志可参考 Carafe 式落盘（`sdmc:/switch/carafe/<TitleID>/`，保留最近 5 次）。
- **不可自动化**：真机 hbmenu 启动、画面表现、输入手感 → 必须「屏摄 + 日志」人工记录。
- **JSONL 记录字段**（沿用集群 D 附录 C）：`date / emulator / version / commit / exe_sha256 / source_zip_sha256 / title_id / nsp_sha256 / install_mode / exit_code / log_path / screenshot_path / result`，并增加 `romfs_content_hash`（内容层可复现）。

#### D.5 组件版本锁定与角色（M3 前置）

| 组件 | 用途 | 锁定值 | 许可 | 角色 |
| --- | --- | --- | --- | --- |
| `jakcron/nstool` | 校验/提取 | v1.9.2 `e89ea84b` | MIT | 第 1 步，必装 |
| `rlaphoenix/hacBrewPack` | 自包含 NSP 打包 | v3.05 `745b16ec` | GPL-2.0 | 子进程调用 |
| `rlaphoenix/NTON` | forwarder 对照 | v3.0.1 `c5d543a9` | GPL-3.0 | 仅对照 |
| `TooTallNate/switch-nsp-forwarder` | 模板/参考 | 0.0.8 `61edd504` | MIT（`package.json`） | 参考 |
| `switchbrew/switch-tools`（nxlink） | 开发期日志回收 | v1.13.1 `22756068` | ISC | 开发内循环 |
| `carafe-nx/carafe` | 真机日志/流程参考 | v0.4.0 `9b69701b` | GPL-3.0-or-later | 参考，不引码 |
| `autorunhq/autorun` | Windows 兼容运行时参考 | test-build-4 `9b717050` | NOASSERTION | 仅参考 |
| `autorunhq/autorun-horizon-dlls` | 同上 | dlls `4ab914bb` | NOASSERTION | 仅参考 |

#### D.6 风险清单

- **密钥合规**：`prod.keys` 不得入库、不得注入 CI、不得随产物分发；测试记录只记「是否提供」不记内容。
- **CFW 前置**：自包含 NSP 需 sigpatches 才能安装运行 → 「可安装」不等于「可公开分发」，文档与 GUI 必须明示。
- **DMCA / 封禁**：任天堂已 DMCA forwarder 相关 GitHub 仓库（§5.4），线上分发此类工具存在下架风险。
- **GPL 边界**：`hacBrewPack`（GPL-2.0）子进程聚合可接受；`Carafe`/`Autorun`（GPL-3.0/AGPL 混合）**不可复制代码**。
- **Ryujinx 不可在线复现**：上游 TLS 不可达 + 镜像 404/451 → 只能依赖本机留档（§5.5）。
- **非确定性输出**与 **Windows 路径长度**见 D.2；`nstool` 停更见 D.3。

#### D.7 打包链刷新复核与 keys 合规策略（2026-10-29 联网复核）

- **版本零变化**（`docs/audit/08-packaging-refresh.md`，7 个核心对象与 v1.2 一致）：`hacBrewPack v3.05 = 745b16ec…`（GPL-2.0，无官方二进制）、`nstool v1.9.2 = e89ea84b…`（MIT）、`NTON v3.0.1 = c5d543a9…`（GPL-3.0，仅对照）、`switch-nsp-forwarder 0.0.8 = 61edd504…`（仍无根 LICENSE，仅 `package.json` MIT）、`Carafe v0.4.0 = 9b69701b…`（GPL-3.0-or-later，仅流程参考）、`Autorun test-build-4 = 9b717050…`（experimental，仅参考）、`switch-tools v1.13.1 = 22756068…`。
- **新增测试后端登记**：`nx-hbmenu v3.6.1 = fd26270a…`（ISC）、`nx-hbloader v2.4.5 = 82b95122…`（ISC；`hbl.nsp` 40,946 B）、`DBI 912ru = e5ba7324…`（**无 LICENSE → 不可分发**，只作真机安装操作工具）、`hb-appstore v2.3.2`（2023 停更，可选）。
- **keys 合规策略（已拍板）**：本机可用 `E:\Othergames\Nintendo Switch\Ryujinx-canary\portable\system\prod.keys`（12,007 B，sha256 `7bb3b6d2…`；221 条 key 名，含 `header_key` 与 `key_area_key_application_00–15`）与 `title.keys`（11,492 B，sha256 `2b338398…`；打包不需要）。框架只通过 `GALNX_PROD_KEYS` 只读路径读取，PROVENANCE 只记 path/size/SHA-256/mtime/来源；**不入库、不打印、不进日志、不进 CI、不随产物分发**，`.gitignore` 覆盖 `*.keys`。
- **真机提取**：`shchmue/Lockpick_RCM` 已被 DMCA（GitHub HTTP 451，DMCA 记录 2023-05-04 Nintendo）→ 文档只写社区通行步骤概要，不提供下载源、不内置 payload；真机安装仍需 CFW + sigpatches。
- **NSP 自包含契约**：ExeFS(`main`+`main.npdm`) + control(`control.nacp`+256×256 JPEG 图标) + RomFS(+可选 logo)；TitleID 0x0100000000000000–0x0fffffffffffffff；`hacBrewPack --titleid` 只改 ACI0 一处 → GalNX 需自写三处元数据；RSA-PSS 随机盐 → **输出非确定性**（不做 bitwise 对比，用 nstool 结构校验 + 输入哈希）；就地修改输入须传副本；Windows 259 B 路径上限；icon EXIF 可致安装卡住。
- **M3 剩余前置**：hacBrewPack 二进制来源 + SHA-256、真机 CFW/sigpatches/FW 记录、DBI 不可分发、Ryujinx 官方源不可达须本地留档、端到端打包未实测（详见 08 §8）。

## 5. Ryujinx Canary 1.3.265：本机二进制与源码对应关系（§14.4）

### 5.1 本机被测二进制

| 项 | 值 |
| --- | --- |
| 路径 | `E:\Othergames\Nintendo Switch\Ryujinx-canary\Ryujinx.exe` |
| 大小 | 73,137,536 B |
| SHA-256 | `379D890B60816C479B83978980183E6E55A3AED5F4027CF95DE65E9DCF67961B` |
| ProductVersion | `1.3.265+4e81a4c`（UTF-16 版本资源串中实测） |
| FileVersion | `1.3.265.0` |
| 二进制内短 SHA 出现次数 | 31 处 ASCII `4e81a4c`；无完整 40 位 SHA |

### 5.2 同目录源码归档

| 项 | 值 |
| --- | --- |
| 路径 | `E:\Othergames\Nintendo Switch\Ryujinx-canary\ryujinx-Canary-1.3.265.zip` |
| 大小 | 15,470,206 B |
| SHA-256 | `7D6D88FBB7D84C9D8CDE7078A4319006F1DAC4E1A890ABAD49AEF3AAF6CDA538` |
| 7z 归档 Comment | `4e81a4c2f4fee6f31e28fbb129759ec2369da6eb`（完整 40 位 commit SHA） |
| 内容 | 4264 files / 602 folders，解压 37,365,628 B，顶层目录 `ryujinx/`，内部 mtime 统一为 2026-03-15 22:46:36；**不含 exe**；唯一 DLL 为 `src/Ryujinx.Audio.Backends.SoundIo/Native/libsoundio/libs/libsoundio.dll` |
| 源码关键事实 | `Directory.Build.props`：`TargetFramework net10.0`、`LangVersion preview`；`README.md` 表明这是 **Ryubing fork**（自管 GitLab git.ryujinx.app，MIT，2024-10-01 Ryujinx 停更后的 QoL fork）；`.github/workflows/canary.yml` 为 Canary CI，`RYUJINX_TARGET_RELEASE_CHANNEL_NAME=canary`，matrix 含 win-x64/linux-x64/linux-arm64 |

### 5.3 运行日志旁证

`Ryujinx-canary/portable/Logs/Ryujinx_Canary_1.3.265_2026-10-29_05-09-01.log` 实测包含：

```
00:00:00.316 |N| Application PrintSystemInfo: Ryujinx Canary Version: 1.3.265
```

同日志显示更新检查 URL 为 `https://update.ryujinx.app/latest/query?os=win&arch=amd64&rc=canary`，并报 `CheckVersionAsync: HttpRequestException ... SSL connection could not be established`（与 §5.4 上游实例不可达一致）；guest firmware 版本 22.0.0。

### 5.4 外部溯源核验结果（独立核验未完成）

| 目标 | 结果（2026-10-29 实测） |
| --- | --- |
| 计划草案 §7.6 的标签镜像 `gitlab.hugofnm.fr/publicmirrors/Ryujinx/-/tags/Canary-1.3.265` | 根路径与 tags 页均 302 跳转登录页（返回"请登录以继续"）；GitLab API 返回 `{"message":"404 Project Not Found"}` → **匿名无法核验 tag→commit** |
| Ryubing 上游实例 `git.ryujinx.app`、`update.ryujinx.app` | curl 经代理与直连均报 `curl: (35) schannel: failed to receive handshake, SSL/TLS connection failed` → **当前不可访问** |
| GitHub `Ryujinx/Ryujinx`、`Ryubing/ryujinx`、`Ryubing/Canary` | HTTP 404（仓库不存在/已删除） |
| GitHub `ryujinx-mirror/ryujinx` | **HTTP 451**：`Repository access blocked`，reason: dmca，created_at: 2025-03-14T13:47:59Z，指向 GitHub DMCA 通知 `2025/03/2025-03-06-nintendo.md` |
| 第三方分发站 `ryujinx.dev`（非官方） | 页面标注 stable v1.3.3 / Canary v1.3.295（©2026，JS 渲染，无源码/commit 链接），仅作命名旁证 |
| Wayback Machine | `git.ryujinx.app/ryubing/canary/-/tags/1.3.265` 有 2026-03-17 快照；但多个归档标签详情页（1.3.103/1.3.259/1.3.264/1.3.265）均渲染同一条 commit `2060fd73…`（"Edit README.md / Jun 10, 2025"）→ **该渲染区块不可用于 tag→commit 定论**；CDX 无 `/-/commit/4e81a4c2*` 快照 |

### 5.5 结论

1. **本机证据内部一致**：exe 版本串中的短 SHA `4e81a4c` 与同目录源码归档 Comment 中完整 SHA `4e81a4c2f4fee6f31e28fbb129759ec2369da6eb` 前缀一致；归档内部 mtime（2026-03-15）与 Wayback 中 tag 1.3.265 页面快照日期（2026-03-17）相容。运行日志独立确认实际运行版本为 1.3.265。
2. **计划草案 §7.6 所述"标签 Canary-1.3.265 对应提交 4e81a4c2"与本机源码归档的 commit 一致**。
3. **但"官方发布 tag↔commit"的独立第三方核验本轮未完成**：镜像需登录、Ryubing 上游 TLS 不可达、GitHub 相关仓库 404/451、Wayback 标签页 commit 区块不可信。报告中不得声称已完成独立验证；建议后续（M1 前）在可访问网络时用上游 CI/发布记录补证，或改用 ryujinx.dev 提供的 SHA-256 清单交叉核对发布产物哈希。

## 6. 未验证 / 存疑 / 需修正的 URL 清单

下表按「对 M0–M3 的影响」排序；**「未验证」不等于「不可用」**，只表示本轮只读审计无法取证。

| # | 类型 | 对象 / 位置 | 本轮实测到的现状 | 处置建议 | 影响 |
| --- | --- | --- | --- | --- | --- |
| I-01 | **需修正 URL** | 计划 §7.1 `Atmosphere-NX/nx-hbloader` | 返回 404；真实仓库为 `switchbrew/nx-hbloader`，`v2.4.5 = 82b95122…`（2025-11-15，ISC，417★） | §9 修订计划草案；审计/文档统一改用新 URL | 中（仅文档/真机测试链） |
| I-02 | **需修正 URL** | 计划 §7.5 `nx-link/nxlink` | 404；`nxlink` 属 `switchbrew/switch-tools`（`v1.13.1 = 22756068…`，ISC）；devkitPro 包名为 `switch-tools`，其 PKGBUILD 不在公开仓库 | §9 修订；版本锁定写「switch-tools 分发包，版本待 `pacman -Q` 取证」 | 中 |
| I-03 | **需补录** | 计划 §7.3 只列 `nx.js_extended` | 真实上游 `TooTallNate/nx.js`（MIT，`v1.0.0-beta.7 = a649611a…`，269★）未列入；`nx.js_extended` 是其 fork | §9 增补为「上游底座」行 | 低 |
| I-04 | **不成立的前提** | 计划 §7.6 `gitlab.hugofnm.fr/publicmirrors/Ryujinx/-/tags/Canary-1.3.265` | 网页需登录、GitLab API 返回 404；`git.ryujinx.app` TLS 握手失败；GitHub `ryujinx-mirror/ryujinx` 为 **451（DMCA，2025-03-06 Nintendo）**；`Ryubing/ryujinx` 404 | §9 改为「本机留档 + 哈希校验 + 断网」策略；tag↔commit 独立核验标 not-verified | 高（测试环境可复现性） |
| I-05 | **已解决（2026-10-29）** | `pkg.devkitpro.org`（`dkp-libs.db`、`/packages/`） | 直连实测 **HTTP 403（Cloudflare）**；根因 = MSYS2 shell 无代理变量、请求直连被拦；`pacman.conf` 的 `XferCommand` 加本地代理 `127.0.0.1:7897` + 浏览器 UA 后下载 **200**，14 包全部安装成功 | 已回填 §8.2；换机/CI 必须显式配置代理与 UA（临时手段，非官方支持方案） | 高（已解除） |
| I-06 | **已验证（2026-10-29）** | devkitPro 官方安装器 `v3.0.3`（2018-06-03，内置 MSYS2 2.10.0） | 安装器可下载（196,304 B）并能完成基础安装（gba/nds/3ds/gamecube/wii 均成功），但 `switch-dev` 一步**静默失败**（同 I-05）；修复下载通道后补装成功 | 已回填 §8.2；安装器本身可用，但不能依赖其 `switch-dev` 步骤的成败作为判断 | 高（已解决） |
| I-07 | **已验证（2026-10-29）** | `switch-dev` 组成员、各包版本与哈希、包签名库 | `pacman -Sg switch-dev` 已取（dkp-libs 7 个 + dkp-windows 4 个条目）；实际安装 14 包、版本见 §8.3；签名校验通过，`pacman -Q` 全量快照（212 包）已留档 | 已回填 §8.3/§8.7；证据提交至 `docs/environment/evidence/` | 中（已关闭） |
| I-08 | **上游声称 ≠ 已验证** | `Brewser` release 的 `brewser.nro`（76,546,123 B）与 API 覆盖率 | 资产哈希已核对；**未在真机/模拟器运行** | M4 评估第一步：在 Ryujinx 固定环境跑官方 NRO 并采日志 | 中（M4） |
| I-09 | **不可溯源** | `krkr-ns` release `v0.1.0` 的 `krkrsdl2.nro`（29.6 MB） | `v0.1.0` tag 已移动到 HEAD（`949faf9a`），release 时间 2026-09-14 → 产物与代码不能按 tag 唯一对应 | M1 只从源码自建；发布 NRO 仅作对照并记录 SHA-256 | 中（M1） |
| I-10 | **法律阻塞** | `jvrcruzGAMES/RenpySwitch`、`Otorhin/Ren2Switch` | 均无 LICENSE；后者父仓库已 archived、2023-09 停更 | 取得书面授权前不接入、不分发 | 高（法律） |
| I-11 | **资产合规** | `clamintus/ONScripter-NX` release assets | 附带 `tsukihime` / `kagetsu_tohya` 商业游戏数据 zip（release API 已证实）；字体 Sazanami Gothic 许可未核实 | 禁止复用资产；字体许可需单独核实后方可打包 | 高（法律） |
| I-12 | **未实测构建** | `hacBrewPack` v3.05 / `nstool` v1.9.2 | 仅源码审阅 + CLI/输入格式取证；**未实际打包任何 NSP** | M3 第一项：在干净目录打包一个空 RomFS 测试 NSP 并用 nstool 校验 | 中 |
| I-13 | **未验证流程** | 真机 DBI MTP 安装；模拟器 `portable/games/` 安装与文件关联 | 均未实测（本轮无安装、无运行） | M3/M4 验收时补测并写 JSONL | 中 |
| I-14 | **未验证行为** | `nxlink -s` 在真机 hbmenu 3.6.1 的日志回收 | 仅从 `switch-tools` 源码与用法取证（端口 28280/28771，zlib 16 KiB 分块） | M1 真机冒烟时实测 | 低 |
| I-15 | **存疑** | devkitPro portlibs 版本（如 mesa 20.1.0、libvpx 1.8.0） | 来自 PKGBUILD/文档交叉推断，非 `pacman -Q` 实测 | M4/M5 若需较新 OpenGL/视频解码，预留自建 portlibs 工作量 | 中（Web/视频） |
| I-16 | **数据一致性说明** | 各审计条目的 stars / open_issues | 与 GitHub API 快照（§10.2）存在 ±1 漂移；`rfvp` 的 `open_issues` 上游报告写 0、API `open_issues_count = 4`（含 PR） | 报告统一以 §10.2 API 快照为准，本表不再重复 | 低 |

**结论**：真正影响 M0 启动的 **I-05/I-06/I-07（devkitPro 可达性与安装）已于 2026-10-29 实测解决**（§8）；剩余 I-08..I-16 多为运行期验证、法律前置与后续里程碑验收项，不阻塞审计结论成立。

## 7. 许可证与分发义务汇总

#### 7.1 按许可证分组的义务

| SPDX | 涉及对象 | 主要义务 | GalNX 处置 |
| --- | --- | --- | --- |
| **ISC** | `switchbrew/libnx`、`switchbrew/nx-hbloader`、`switchbrew/switch-tools`（nxlink） | 保留版权声明与许可文本 | 作为构建/开发工具与运行库，保留 NOTICE |
| **MIT** | `DrFlyingPig/krkr-ns`、`krkrsdl2`、`jakcron/nstool`、`TooTallNate/nx.js`、`nx.js_extended`、`TooTallNate/switch-nsp-forwarder`（仅 `package.json` 声明）、`XenonRecomp`、`XenosRecomp` | 保留版权与许可声明；无担保声明 | 正常引用；生成第三方许可清单 |
| **BSD-3-Clause** | `rexglue/rexglue-sdk` | 保留声明；不得用作者名义背书 | 旁支登记，不进依赖 |
| **MPL-2.0** | `natureglass/Brewser`、`xmoezzz/rfvp` | **文件级** copyleft：修改过的 MPL 文件须以同许可公开源码；分发二进制需提供对应源码获取方式 | 只消费官方 NRO（不修改）时义务最小；若 GalNX 修改 Brewser 文件必须开源该文件；`package.json` 写 MIT 与 LICENSE 冲突 → **以 LICENSE 为准** |
| **LGPL-2.1-or-later**（组件） | `autorun`（Wine 主体）、krkr-ns 依赖的 **FFmpeg 7.1**（LGPL 配置、`--disable-gpl`） | 提供库源码/替换方式；保留声明 | FFmpeg 以独立动态库/子进程方式使用；随产物附 LGPL 文本与源码链接；不得静态链接成不可替换形态 |
| **GPL-2.0(-or-later)** | `Atmosphere-NX/Atmosphere`、`hacBrewPack`、`ONScripter-NX` | 分发二进制须提供完整对应源码；衍生作品同许可 | Atmosphere 仅作真机测试环境、**不随 GalNX 分发**；hacBrewPack 仅**子进程调用**（聚合分发，需附其源码/许可）；ONScripter 若接入，引擎 NRO 独立分发并公开其修改源码 |
| **GPL-3.0(-or-later)** | `NTON`、`carafe-nx/carafe` | 同上，且含专利/反 Tivoization 条款 | 仅作对照工具/流程参考，**不复制代码**，不随 GalNX 分发 |
| **AGPL-3.0-or-later** | `ETCHDEV/BurialNX` | 网络交互也触发源码提供义务 | **禁止引用代码**，仅参考设计 |
| **MIT + 混合组件** | `renpy/renpy`、`renpy/renpy-build`（无根 LICENSE；`sphinx/source/license.rst` 声明） | 主体 MIT；部分组件 LGPL（必须可满足 LGPL 分发）/MPL-2.0/Apache-2.0/BSD/Zlib/Python License；生成项目文件 CC0-1.0 | 接入前按 `license.rst` 生成 NOTICE；LGPL 组件保持可替换；不复制社区无证移植代码 |
| **NOASSERTION** | `autorun`、`autorun-horizon-dlls`、`Ryujinx Canary`（源码归档）、`RenpySwitch`、`Ren2Switch` | 权利状态不明 → 默认不可分发 | 仅参考/比对；Ren'Py 两库在授权前**完全不接入** |

#### 7.2 非代码资产的合规约束

- **密钥**：`prod.keys` / `title.keys` 由用户从自有主机提取，属用户本地数据；GalNX 不采样、不入库、不写 CI 日志、不随产物分发。
- **商业游戏数据**：`ONScripter-NX` release 内附的 `tsukihime` / `kagetsu_tohya` 数据包、以及任何用户游戏目录，**一律不得复制进仓库/测试夹具/发布产物**；夹具只能自制或用许可允许再分发的样例。
- **字体**：Sazanami Gothic 许可未核实 → 在核实前不得随引擎打包；优先使用系统字体或 OFL 字体。
- **devkitPro 自建工具链**：`buildscripts` README 明确「for personal use only and may not be distributed by entities other than devkitPro」→ 不得重新分发自建工具链二进制。
- **Ryujinx**：源码归档本体 MIT，但其分发/使用背景涉及 DMCA 争议 → 仅本机留档，不进 GalNX 仓库，不随产品分发。

#### 7.3 对 GalNX 仓库许可证策略的建议

1. **GalNX 工作台本体**建议 Apache-2.0 或 MIT（与 Python CLI 生态一致），**引擎适配器**按各自上游许可独立声明（`adapters/<name>/LICENSE`）。
2. 每个产物（NRO/NSP/工具二进制）在 artifact store 记录：上游 commit、许可证 SPDX、许可证文本哈希、修改说明（`artifacts/<id>/PROVENANCE.json`）。
3. 分发时自动生成 `THIRD_PARTY_NOTICES`（从锁定表 + SPDX 推导），并在 CI 中检查「新依赖是否出现在许可证白名单」。
4. 若接入 ONScripter（GPL-2.0-or-later）或改为链接 hacBrewPack，必须先做 GPL 决策记录（`docs/decisions/000x-gpl-boundary.md`）。

## 8. devkitPro 工具链：实测安装结果、最小构建验证与版本锁定（2026-10-29 更新）

> 本轮审计开始时本节是「M0 执行预案（未执行）」。用户于 2026-10-29 授权后，Lead 在 `D:\devkitPro` 完成补装、跑通最小 NRO 构建并做环境取证；本节改为**实测记录 + 约束结论 + 后续锁定建议**。完整安装实录（含命令输出与证据文件）见 [`docs/environment/devkitpro-2026-10-29.md`](environment/devkitpro-2026-10-29.md)。

#### 8.1 实测结论速览

| 验收项 | 计划期望 | 实测结果 | 证据 |
| --- | --- | --- | --- |
| 安装路径 | `C:\devkitPro` 或自定 | **`D:\devkitPro`**（官方安装器 v3.0.3，用户执行） | `D:\devkitPro\installed.ini`、`msys2/`、`devkitA64/` |
| MSYS2 | 2.10.0（安装器内置） | MSYS2 3.6.11 / `pacman` 6.1.0-26，root=`D:\devkitPro\msys2` | `pacman -Q` 快照 |
| `DEVKITPRO` | `/opt/devkitpro` | **`/opt/devkitpro`**（`/etc/fstab` 把 `D:\devkitPro` 映射过去） | MSYS2 login shell `echo $DEVKITPRO` |
| switch-dev | `switch-dev` 元包 | ✅ **14 个包，434.93 MiB**（2026-10-29 22:0x 安装） | `pacman.log` 事务记录 + §8.3 表 |
| 交叉编译器 | GCC 版本与 `pacman -Q` 一致 | ✅ `aarch64-none-elf-gcc.exe (devkitA64) 16.1.0` | 绝对路径执行 `--version` |
| target | `aarch64-none-elf` | ✅ `aarch64-none-elf` | `-dumpmachine` |
| 链接器 | — | ✅ `GNU ld (GNU Binutils) 2.46.0.20260210` | `aarch64-none-elf-ld --version` |
| libnx | `libnx 4.12.0-1` | ✅ `libnx 4.12.0-1` | `pacman -Q` |
| nxlink | 输出 Usage 且含 `-s` | ✅ `/opt/devkitpro/tools/bin/nxlink`（switch-tools 1.13.1-1），`--help` 含 `-s/--server` | §8.4 |
| 最小构建 | `make` 产出 `.nro` 且退出码 0 | ✅ `m0-hello.nro` **166,085 B**，`sha256=a341e7750e099da94c12541d8fb173793cc348688824c69f5f76c7ce29b9318b` | §8.5 |
| 包快照 | `pacman -Q` 全量 | ✅ 212 个包，其中 Switch 相关 15 个 | 证据文件（§8.7） |
| 磁盘占用 | 2–3 GB（待实测） | ✅ **2.5 GB**（`du -sh /opt/devkitpro`） | 命令输出 |

#### 8.2 实际安装过程（为什么安装器「成功」却没装成 switch-dev）

1. 用户运行 `devkitProUpdater-3.0.3.exe`（196,304 B，可用副本：`E:\Chromedownload\`、`D:\devkitPro\`），选 `D:\devkitPro`，勾选 Switch Development。安装器依次 `-Syu`、gba/gp32/nds/3ds/gamecube/wii-dev 均成功；**最后一条 `pacman -S --noconfirm --needed switch-dev`（15:36:07）之后没有任何事务日志** → switch-dev 静默失败（安装器不报错，用户看到的是「下载失败」）。
2. 根因是 **`pkg.devkitpro.org` 对直连请求返回 HTTP 403（Cloudflare）**：devkitPro MSYS2 的 login shell 没有任何代理环境变量，pacman 调 curl 直连 → 403；而在本机 git-bash 中（自带 `http(s)_proxy=http://127.0.0.1:7897`，后端代理可出网）同一请求 200。实测矩阵：MSYS2 直连 403 / MSYS2 显式代理+浏览器 UA 200 / git-bash 直连（有代理变量）200。
3. 修复：在 `D:\devkitPro\msys2\etc\pacman.conf` 用 `XferCommand` 让 pacman 经本地代理 + 浏览器 UA 下载（原文件已备份为 `pacman.conf.bak-galnx-<时间戳>`）：

   ```ini
   XferCommand = /usr/bin/env http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 /usr/bin/curl -L -C - -f -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36" -o %o %u
   ```

4. 兜底：先用可出网的 `curl`（git-bash 的 curl 经代理 + UA）把 14 个包及 `.sig` 下载到 `D:\devkitPro\msys2\var\cache\pacman\pkg\`，再 `pacman -S --needed --noconfirm switch-dev` 命中本地缓存完成安装（安装器此前已缓存 5 个包但缺签名）。
5. 该修复是**本机环境改动**：换机/CI 需重做；且代理端口（7897）是用户本机代理，不可假定长期不变。GalNX 若要自动化安装 devkitPro，必须把「代理 + UA」作为显式参数，并在文档中注明这是绕过 Cloudflare 反爬的临时手段（而非官方支持方案）。

#### 8.3 实际安装包清单（`pacman -Q` 快照，2026-10-29）

| 包 | 版本 | 来源仓库 | 说明 |
| --- | --- | --- | --- |
| devkitA64 | r30-1 | dkp-libs | 工具链元包 |
| devkita64-gcc | 16.1.0-1 | dkp-windows | C/C++/objcopy 等 |
| devkita64-binutils | 2.46.0-1 | dkp-windows | ld 2.46.0.20260210 |
| devkita64-newlib | 4.6.0.20260123-4 | dkp-windows | libc |
| devkita64-rules | 1.1.1-1 | dkp-windows | make 规则 |
| libnx | 4.12.0-1 | dkp-libs | Switch 用户态库（对应 switchbrew/libnx v4.12.0 = `7644c9b2…`） |
| deko3d | 0.5.0-1 | dkp-libs | GPU 库 |
| switch-cmake | 1.5.2-1 | dkp-libs | CMake 工具链文件 |
| devkita64-cmake | 1.1.3-1 | dkp-libs | — |
| switch-pkg-config | 0.28-4 | dkp-libs | pkg-config 包装 |
| switch-examples | 20260201-1 | dkp-libs | 官方示例（`/opt/devkitpro/examples/switch/`） |
| switch-tools | 1.13.1-1 | dkp-windows | `nxlink`、`elf2nro`、`nacptool` 等 |
| devkitA64-gdb | 14.1-1 | dkp-windows | 调试器 |
| uam | 1.1.0-2 | dkp-windows | 用户态异常处理器 |

`switch-dev` 组还含 `catnip 0.2.0-1`、`general-tools 1.4.4-1`、`devkit-env 1.0.1-2`（安装器阶段已装或随组安装）。

#### 8.4 环境变量与正确调用方式

- `D:\devkitPro\msys2\etc\fstab` 把 `D:\devkitPro` 映射为 `/opt/devkitpro`；因此 MSYS2 内 `DEVKITPRO=/opt/devkitpro`。
- `/etc/profile.d/devkit-env.sh` 只导出 `DEVKITPRO=/opt/devkitpro`、`DEVKITARM`、`DEVKITPPC`，并把 `$DEVKITPRO/tools/bin` 加入 `PATH`；**`devkitA64/bin` 不在 `PATH`**。make 构建无需它（`switch_rules` 用 `$(DEVKITPRO)/devkitA64/bin/…` 绝对路径），但直接敲 `aarch64-none-elf-gcc` 会 not found；GalNX 的 doctor 检查应使用绝对路径或自行补 PATH（是否加 `/etc/profile.d/99-devkita64.sh` 属本机便利改动，尚未做）。
- 从 Windows 侧调用 MSYS2 的唯一可靠姿势（实测）：

  ```bat
  env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '<command>'
  ```

#### 8.5 最小构建验证（M0 §14.3 的最小形态）

- 工程：`/opt/devkitpro/examples/switch/templates/application`（consoleInit + 按 Plus 退出的 hello-world，Makefile 从 `$(DEVKITPRO)/libnx/switch_rules` include）。
- 构建脚本：[`scripts/m0_build_hello.sh`](../scripts/m0_build_hello.sh)；构建目录 `E:\galnx-build\m0-hello`（无空格，原因见 §8.6）；结果与日志归档在 [`workspaces/m0-hello/`](../workspaces/m0-hello/)。
- 结果：`make -j4` 退出码 **0**；产物 `m0-hello.nro` 166,085 B、`sha256=a341e7750e099da94c12541d8fb173793cc348688824c69f5f76c7ce29b9318b`；`m0-hello.elf` 2,878,832 B；`m0-hello.nacp` 16,384 B；NRO 头部 offset 8 为 `HOMEBREW` 魔数（elf2nro 产物特征）。
- 结论：**devkitA64 工具链 + libnx + switch-tools 在本机可复现构建 NRO**，M0 工具链前置条件满足。

#### 8.6 关键约束：devkitPro make 工程不能在含空格路径构建（实测）

- 现象：在 `E:\Othergames\Nintendo Switch\Workspace\...` 下构建失败，报错形如

  ```text
  make --no-print-directory -C build -f /e/Othergames/Nintendo Switch/Workspace/.../Makefile
  make[1]: /e/Othergames/Nintendo: No such file or directory
  ```

  即 `$(CURDIR)` 中的空格把 `-f` 参数拆成两个。
- 尝试的绕法均失败：目录 junction（`mklink /J E:\galnx → 含空格目录`）在 MSYS2 中被视为符号链接，`pwd -P`/make 的 `CURDIR` 仍解析回**长物理路径**（含空格）；Windows 8.3 短路径（`E:\OTHERG~1\NINTEN~1\...`）同样被解析回长路径。
- 可用解：在无空格目录构建（如 `E:\galnx-build`），再把产物/日志归档回工作区。**GalNX 的 workspace/build 目录设计必须保证无空格**（或改用 CMake 生成器并自行处理空格，尚未验证）。

#### 8.7 版本锁定策略（devkitPro 无版本化仓库，必须组合使用）

| 手段 | 锁定对象 | 本轮状态 |
| --- | --- | --- |
| `pacman -Q` 全量快照 | 每台构建机的精确包版本（本机 212 个包，Switch 相关 15 个） | ✅ 已采集（`docs/environment/evidence/`） |
| `/var/cache/pacman/pkg` 包缓存 + SHA-256 | 包文件本体（滚动仓库旧包会被替换） | ✅ 已缓存 14 包 + `.sig`（哈希见证据） |
| Docker digest | 整个工具链镜像 | 未验证（Docker 未安装）：`devkitpro/devkita64@sha256:1fc388c3…`（index）/`82575ea7…`（amd64） |
| 上游源码 tag | libnx `v4.12.0 = 7644c9b2…`、switch-tools `v1.13.1 = 22756068…` | ✅ 审计阶段已取证 |
| 构建产物哈希 | `m0-hello.nro` SHA-256（见 §8.5） | ✅ 已记录；同一包快照下应可复现 |

**不要**把 `devkitA64 r30-1` 当工具链版本：它只声明依赖下界（gcc≥16.1.0-1、binutils≥2.46.0-1、newlib≥4.6.0.20260123-4），实际版本必须由 `pacman -Q` 取证。

#### 8.8 后续 M0 动作（未完成项）

- [ ] 按实际需求补装 `switch-sdl2`（2.28.5-4）、`switch-freetype` 等 portlibs（krkr-ns 需要 SDL2；本轮未装）。
- [x] **CMake 工程构建已验证（2026-10-29）**：`cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/Switch.cmake"` + `cmake --build build` 在无空格路径与**含空格路径**（`space test/cmake-hello`）均 exit 0，产物 `m0-cmake.nro` 161,989 B；详见 §8.6 与 8.9。
- [x] **模拟器冒烟（2026-10-29，部分完成）**：Citron Neo nightly 成功加载运行 hbmenu v3.6.1、hb-appstore v2.3.2、Brewser v0.1.131（§4.C.8）；Ryujinx 1.3.265 加载 hbmenu/appstore 正常。**`m0-hello.nro` 自身尚未单独冒烟** → 留待 M1 首项。
- [ ] 真机冒烟：`nxlink -s` 上传到 NS1（hbmenu 环境），记录退出码与日志。
- [ ] 产出 `docs/decisions/0002-toolchain-install-path.md`（记录本机实测路径、快照哈希、验收命令输出）。

#### 8.9 工具链刷新复核：本机是否落后上游（2026-10-29，`docs/audit/05-toolchain-refresh.md`）

- **结论：不落后**。`pacman -Sy` 后 `pacman -Si` 全量 1088 条与本机 `pacman -Q` 212 包 join：**17 个 switch 相关包 17/17 与 `dkp-libs.db` 一致、0 可升级**（catnip 0.2.0-1、deko3d 0.5.0-1、devkitA64 r30-1、devkita64-cmake 1.1.3-1、devkita64-newlib 4.6.0.20260123-4、devkita64-rules 1.1.1-1、libnx 4.12.0-1、switch-cmake 1.5.2-1、switch-examples 20260201-1、switch-pkg-config 0.28-4、devkit-env 1.0.1-2、devkitA64-gdb 14.1-1、devkita64-binutils 2.46.0-1、devkita64-gcc 16.1.0-1、general-tools 1.4.4-1、switch-tools 1.13.1-1、uam 1.1.0-2）。
- **MSYS2 侧**：`pacman 6.1.0-26`、`msys2-runtime 3.6.11-4` 与仓库一致；`cmake 4.0.2-1`（仓库 4.4.4-1）、`make 4.4.1-2`（仓库 4.4.1-3）标 OUTDATED 但不影响 Switch 构建（devkitPro 用自带 `cmake/Switch.cmake` 与工具链绝对路径），暂不升级以免扰动已验证基线。
- **devkitPro 安装器仍停在 v3.0.3（2018-06-03）**，但包库是滚动 latest → 安装器版本不代表工具链版本；`libnx v4.12.0 = 7644c9b2…`（release 2026-09-28；tag commit 2026-02-04）、`Atmosphère 1.12.1 = 6b0c077b…`（2026-10-16，release 声明支持 **firmware 23.0.0**）、`nx-hbmenu v3.6.1`、`nx-hbloader v2.4.5` 均为最新。
- **CMake 空格路径实测（重要设计输入）**：`/e/galnx-build/t9/cmake-nospace` 与 `/e/galnx-build/t9/space test/cmake-hello` 两处 configure+build 均 exit 0，产物 `m0-cmake.nro` 161,989 B（sha256 `f4c08034…` / `c7b6bb30…`，差异来自 NACP 内嵌时间等非确定性）→ **GalNX 自建构建系统直接采用 CMake + devkitPro `Switch.cmake` 可绕开 8.6 的空格路径硬限制**；devkitPro make 模板仍不适用于含空格路径。
- **Docker 不作基线**：`devkitpro/devkita64:latest` 最新 tag `20260219`、digest 早于 devkitA64 r30 → CI 若用容器需自建镜像并固定 `pacman -Q` 快照。
- 锁定三位一体（沿用 8.7）：`pacman -Q` 快照 + `/var/cache/pacman/pkg` 包缓存（64 包，sha256 已归档）+ 产物 sha256（`m0-hello.nro` `a341e775…`、`m0-cmake.nro` `f4c08034…`）。

## 9. 对计划草案（v0.1 – v0.4）的修订建议

下表编号可直接作为 `docs/decisions/` 的议题；「已确认」表示本轮范围沟通中用户已拍板的决策。

| # | 计划位置 | 原文/现状 | 建议改为 | 依据 |
| --- | --- | --- | --- | --- |
| R-01 | §7.1 | `Atmosphere-NX/nx-hbloader` | `switchbrew/nx-hbloader`（`v2.4.5 = 82b95122…`，ISC） | 原链接 404，见 I-01 |
| R-02 | §7.5 | `nx-link/nxlink` | `switchbrew/switch-tools`（`v1.13.1 = 22756068…`，ISC；devkitPro 包名 `switch-tools`） | 原链接 404，见 I-02 |
| R-03 | §7.3 | 仅列 `natureglass/nx.js_extended` | 增补上游 `TooTallNate/nx.js`（MIT，`v1.0.0-beta.7 = a649611a…`，269★），并注明扩展分支 | 见 I-03 |
| R-04 | §7.6 | 以 `gitlab.hugofnm.fr` 标签镜像作为 Ryujinx 溯源依据 | 改为「本机二进制+源码归档留档（SHA-256 校验）+ 断网 + 禁自动更新」；tag↔commit 标注 not-verified | 镜像需登录/API 404、上游 TLS 不可达、GitHub 451，见 §5.4 |
| R-05 | §12 语言 | 建议 Python CLI（未决） | **Python 3.12 CLI 已确认**；目录结构按 §11 的 `src/galnx/` 包布局 | 用户已确认（m00003 范围沟通） |
| R-06 | §12 首测游戏 | 未决 | **第一款原型 = `DrFlyingPig/krkr-ns`**；ONScripter-NX 作第二候选（需 GPL 决策）；Ren'Py 两库待授权 | §4.B 接入排序 |
| R-07 | §12/§5 | NSP 首目标 = forwarder | **改为自包含 NSP**（`nstool` + `hacBrewPack` 子进程 + 自研编排）；forwarder 降为对照 | §4.D.1，NTON README 封禁/DMCA 警告 |
| R-08 | §12 Web 首目标 | 是否 Teaching Feeling 待定 | **先选 `natureglass/Brewser` 官方 NRO 做 M4 可行性验证**；Teaching Feeling 需先核实实际发行包是否 Electron/Node 依赖，再决定是否需 fs/Node 兼容层 | §4.C，Brewser 无 `fs`/`require` |
| R-09 | §5 输入系统 | 通用键鼠模拟 + 语义映射 + 组合键切换 | **M0/M1 只做通用键鼠模拟**；语义映射与热加载推迟到 M2，并先做输入层状态机单测 | 用户范围决策：先跑通再细化 |
| R-10 | §8 里程碑 M0 | 「框架骨架 + 工具链审计」 | M0 增加两项硬前置：①devkitPro 可达性排障（I-05）②工具链快照/锁定文件（§8.5）；审计产出作为 M0 出口条件 | 本轮审计结论 |
| R-11 | §7.4 | 平铺列 `autorun`/`carafe` | 明确标注：`carafe` GPL-3.0-or-later、`autorun` NOASSERTION → **仅参考流程，禁止引用代码** | §7.1 许可表 |
| R-12 | §7.7 | 列 `rexglue`/`XenonRecomp`/`XenosRecomp` | 保留登记，但注明「与 Galgame 移植路线无关，不列入第一阶段」 | §4.C.5 |
| R-13 | §7 新增行 | 未列 | 增补 `devkitPro/installer`（v3.0.3）、`devkitPro/buildscripts`（不可再分发）、`jakcron/nstool`、`rlaphoenix/hacBrewPack` 作为**直接依赖级**对象 | 本轮审计覆盖 |
| R-14 | §11 目录 | `docs/(ARCHITECTURE,ROADMAP,TOOLCHAIN_AUDIT,TESTING,decisions/)` | 增补 `docs/audit/`（分集群原始审计）、`docs/decisions/` 编号约定、`artifacts/<id>/PROVENANCE.json` | 便于审计留痕与许可追溯 |
| R-15 | 新增决策 | 无 | 增加 `decisions` 议题：0001 语言（Python CLI，已定）、0002 工具链安装路径与锁定（M0）、0003 NSP 形态（自包含，已建议）、0004 GPL 边界（ONScripter/hacBrewPack）、0005 测试环境固定（Ryujinx 留档） | §7/§8/§9 |
| R-16 | §9 验收底线 | 未含密钥/许可/测试环境固定 | 底线增加：①`prod.keys` 不落库不进日志 ②产物带 PROVENANCE ③测试环境 exe/zip 哈希校验 ④内容层可复现（NSP 文件哈希不强求） | §4.D、§7 |
| R-17 | §7.2 Ren'Py | 以社区移植（RenpySwitch/Ren2Switch）为参照 | **改为官方源码独立移植方向**：`renpy/renpy` + `renpy/renpy-build`，锁 8.5.3 系；社区仓库全部无许可证 → 只作技术差异参考，禁止复制代码 | §4.B.7、`docs/audit/04-renpy-official.md` |
| R-18 | §7.3/§12 Web | 直接讨论 M4 接 Brewser | M0/M1 先做 **Brewser 最小冒烟可行性验证**（官方 NRO + 最小 HTML 页），通过后再谈 RPG Maker MV/Teaching Feeling。**2026-10-29 实测两轮**：Ryujinx 1.3.265 无法加载 nx.js 系 NRO（§4.C.7）→ 换 **Citron Neo 后 2/2 完整运行通过**（§4.C.8，DOM/CSS/JS/Canvas2D/WebGL/localStorage 全通过、seed 生成）→ Web 路线模拟器侧已打通，M4 主验证后端改为 Citron、Ryujinx 降为第二意见；真机仍为最终依据 | §4.C.7/§4.C.8、`docs/experiments/web-01`、`web-02-citron-smoke.md` |
| R-19 | §7.2 接入排序 | krkr-ns 第一款原型 | **krkrsdl2 上游本体已有官方 Switch 目标与 CI 出包（MIT）→ 第一梯队改为「krkrsdl2 上游（可复现）→ krkr-ns（启动器/插件增强，实验性）」**；新增候选 `wetor/ONScripter-jh-Switch`（GPL-2.0，优先）、`Erige005/Kirikiroid2-NX`（KiriKiri 非 SPDX 许可）、`xmoezzz/siglus_rs`（MPL-2.0）；ONScripter-NX 判 GPL-2.0-only；Ren'Py 暂缓（已由 06 确认，见 §4.B.8） | `docs/audit/06-engines-refresh.md` |
| R-20 | §12 新增决策 | 未讨论 keys 来源与边界 | 增加决策（计划 v0.4 §12 第 10 条）**keys 策略**：使用本机 Ryujinx 自带 keyset（用户已授权），`GALNX_PROD_KEYS` 只读；只记录 path/size/SHA-256；不入库/不入日志/不进 CI/不随产物分发；Lockpick_RCM 已被 DMCA，只写步骤不提供下载源 | §4.D.7、`docs/audit/08-packaging-refresh.md` |
| R-21 | §12 测试后端 | 未定 | 增加决策（计划 v0.4 §12 第 9 条）**测试后端优先级**：Citron Neo（开发循环/CI 冒烟，实测可跑 Brewser）→ 本机留档 Ryujinx 1.3.265（第二意见/回归）→ 真机 NS1（唯一验收权威）；模拟器结果不得记为真机通过；Citron 锁资产 sha256 `0d2c9bf3…`、Ryujinx 锁 exe/zip 双哈希 | §4.C.8、`docs/audit/07-web-citron.md` |

#### 9.1 建议在 M0 完成的决策记录（模板要点）

- `0001-language-python-cli.md`：Python 3.12、`src/` 布局、CLI 框架（Typer/argparse 待定，M0 定）。
- `0002-toolchain-install-path.md`：实际安装路径/包快照哈希/验收输出/回滚方式。
- `0003-nsp-target-self-contained.md`：路线对比结论、密钥处理、内容层可复现定义。
- `0004-gpl-boundary.md`：哪些组件以子进程方式调用、哪些禁止引码、分发形态。
- `0005-test-env-fixed-ryujinx.md`：留档哈希、断网措施、JSONL 字段。

## 10. 附录

### 10.1 原始审计数据与取证复现

**文件位置**（均已提交仓库）：

| 文件 | 内容 | 条数 |
| --- | --- | --- |
| `docs/audit/00-switch-base.md` | 集群 A：devkitPro / libnx / Atmosphère / nx-hbloader / nxlink | 6 |
| `docs/audit/01-engines.md` | 集群 B：krkr-ns / RenpySwitch / Ren2Switch / ONScripter-NX / rfvp | 5 |
| `docs/audit/02-web.md` | 集群 C：Brewser / nx.js_extended / BurialNX / nx.js / rexglue / XenonRecomp / XenosRecomp | 7 |
| `docs/audit/03-packaging-testing.md` | 集群 D：NTON / hacBrewPack / nstool / switch-nsp-forwarder / nxlink / autorun / horizon-dlls / carafe / Ryujinx | 9 |
| `docs/audit/audit_merged.json` | 四条合并后的机读数据（27 条，含 `_cluster` 字段） | 27 |

每条审计在对应文件末尾以 ` ```galnx-audit ` 围栏内嵌一条 JSON（22 字段），`audit_merged.json` 是其合并、去重标注与规范化结果（`meta.normalization_notes` 记录规范化规则）。**合并 JSON 是本报告的机读底稿**：`tools/validate_audit.py` 可校验字段完整性、SHA 40 hex、日期格式与覆盖率。

**22 字段定义**：

| 字段 | 含义 |
| --- | --- |
| `name` | 对象名称（含 owner/repo 语义） |
| `url` | 规范化仓库/归档 URL（用于总览表链接） |
| `default_branch` / `head_sha` / `head_date` | 默认分支、审计当日的 HEAD 提交与提交日期 |
| `pinned` | 是否锁定了 tag/release；空表示未锁定 |
| `license_spdx` / `license_file` | SPDX 标识与许可证文件名（无文件则 `NOASSERTION`） |
| `license_notes` | 许可证细节（冲突、缺失、逐组件声明等） |
| `archived` / `last_push` / `stars` / `open_issues` | 仓库状态元数据（GitHub API 快照） |
| `build_system` / `build_deps` | 构建系统与关键依赖（工具链、外部仓库、密钥等） |
| `readme_claims` / `readme_claim_url` | 上游自述能力与其出处（**仅声称，未验证**） |
| `risks` | 已识别的许可/工程/合规风险 |
| `verification_level` | `read-only`（仅远程取证）/ `source-inspected`（源码/产物层面取证）/ `not-verified`（证据不足） |
| `verification_failures` | 无法验证的具体项 |
| `source_urls` | 取证用到的原始 URL 列表 |
| `audited_at` | 审计日期（统一 2026-10-29） |

**取证命令复现**（2026-10-29 实际使用，Windows + 代理 `http://127.0.0.1:7897`）：

```bash
# GitHub API（凭据经环境注入，不落盘；响应正文约 20 KB 截断，单仓库请求约 5-6 KB 安全）
curl -s -H "Accept: application/vnd.github+json" -H "Authorization: Bearer $GH_TOKEN" \
  https://api.github.com/repos/<owner>/<repo>
curl -s -H "Accept: application/vnd.github+json" -H "Authorization: Bearer $GH_TOKEN" \
  https://api.github.com/repos/<owner>/<repo>/releases/latest
# 原始文件 / LICENSE / PKGBUILD
curl -s https://raw.githubusercontent.com/<owner>/<repo>/<ref>/LICENSE
# 标签与 HEAD（git 需显式代理且禁止交互式凭据提示）
git -c http.proxy=http://127.0.0.1:7897 ls-remote --tags --heads https://github.com/<owner>/<repo>
# 包源可达性（本轮关键阻塞证据）
curl -sI https://pkg.devkitpro.org/packages/dkp-libs.db
curl -sI https://github.com/devkitPro/installer/releases/download/v3.0.3/devkitProUpdater-3.0.3.exe
# 发布资产哈希（GitHub API release assets 的 digest 字段 + 本地 sha256sum）
sha256sum brewser.nro
# 本机 Ryujinx 归档取证（7z 注释 + 文件表 + 内部 mtime）
7z l -slt Ryujinx-canary/ryujinx-Canary-1.3.265.zip | head -20
# 二进制版本信息（PowerShell）
(Get-Item Ryujinx-canary/Ryujinx.exe).VersionInfo | Format-List FileVersion,ProductVersion
```

**数据规范化说明**：①`switchbrew/switch-tools` 在 A/D 两集群各出现一次 → 总览表去重为 26 个唯一对象；②无 LICENSE 的两条（`RenpySwitch`、`Ren2Switch`）`license_spdx` 记为 `NOASSERTION`；③Ryujinx Canary 条按本机源码归档规范化（`head_date` 为归档内部 mtime，非提交时间，已在条目内注明）；④`stars`/`open_issues` 以 §10.2 快照为准。

### 10.2 GitHub API 元数据快照（2026-10-29）

| # | 对象 | HEAD SHA（12） | HEAD 日期 | GitHub API 许可证 | ★ | open | last push | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [devkitPro 安装器 + pacman 包体系](https://devkitpro.org/wiki/Getting_Started) | — | — | NOASSERTION | — | — | 2023-09-11 | 无 GitHub API 数据（非 GitHub 仓库/未收录） |
| 2 | [devkitPro/pacman-packages](https://github.com/devkitPro/pacman-packages) | b9e8b0de6a64 | 2026-10-16 | NOASSERTION | 168 | 37 | 2026-10-16 | — |
| 3 | [switchbrew/libnx](https://github.com/switchbrew/libnx) | b156b4774fb2 | 2026-10-19 | ISC | 1477 | 13 | 2026-10-19 | — |
| 4 | [Atmosphere-NX/Atmosphere](https://github.com/Atmosphere-NX/Atmosphere) | 6b0c077b4c60 | 2026-10-15 | GPL-2.0 | 20248 | 20 | 2026-10-16 | — |
| 5 | [switchbrew/nx-hbloader](https://github.com/switchbrew/nx-hbloader) | — | — | ISC | — | — | 2025-11-15 | 无 GitHub API 数据（非 GitHub 仓库/未收录） |
| 6 | [nxlink (switchbrew/switch-tools)](https://github.com/switchbrew/switch-tools) | — | — | ISC | — | — | 2024-10-23 | 无 GitHub API 数据（非 GitHub 仓库/未收录） |
| 7 | [DrFlyingPig/krkr-ns](https://github.com/DrFlyingPig/krkr-ns) | 949faf9a874f | 2026-10-16 | NOASSERTION | 21 | 2 | 2026-10-16 | 许可证以仓库 LICENSE 原文为准 |
| 8 | [jvrcruzGAMES/RenpySwitch](https://github.com/jvrcruzGAMES/RenpySwitch) | 7824039a7d03 | 2026-08-10 | — | 2 | 0 | 2026-08-10 | — |
| 9 | [Otorhin/Ren2Switch](https://github.com/Otorhin/Ren2Switch) | 5fce4a28afaa | 2023-09-04 | — | 12 | 0 | 2023-09-04 | — |
| 10 | [clamintus/ONScripter-NX](https://github.com/clamintus/onscripter-nx) | a8439a86393f | 2026-01-14 | GPL-2.0 | 37 | 0 | 2026-01-15 | 许可证以仓库 LICENSE 原文为准 |
| 11 | [xmoezzz/rfvp](https://github.com/xmoezzz/rfvp) | 9f07adef2eb5 | 2026-10-25 | MPL-2.0 | 151 | 4 | 2026-10-25 | — |
| 12 | [natureglass/Brewser](https://github.com/natureglass/Brewser) | 8040580e92e4 | 2026-09-17 | MPL-2.0 | 15 | 1 | 2026-09-17 | — |
| 13 | [natureglass/nx.js_extended](https://github.com/natureglass/nx.js_extended) | f41fb5506a2d | 2026-07-08 | MIT | 1 | 0 | 2026-09-17 | — |
| 14 | [ETCHDEV/BurialNX](https://github.com/ETCHDEV/BurialNX) | c2c6691c0c73 | 2026-10-19 | AGPL-3.0 | 2 | 2 | 2026-10-19 | 许可证以仓库 LICENSE 原文为准 |
| 15 | [TooTallNate/nx.js](https://github.com/TooTallNate/nx.js) | a649611a1a4d | 2026-10-13 | MIT | 269 | 12 | 2026-10-13 | — |
| 16 | [rexglue/rexglue-sdk](https://github.com/rexglue/rexglue-sdk) | c94f5ebdcb3c | 2026-08-21 | NOASSERTION | 1200 | 114 | 2026-10-02 | 许可证以仓库 LICENSE 原文为准 |
| 17 | [hedge-dev/XenonRecomp](https://github.com/hedge-dev/XenonRecomp) | ddd128bcca99 | 2025-08-04 | MIT | 6640 | 94 | 2025-08-04 | — |
| 18 | [hedge-dev/XenosRecomp](https://github.com/hedge-dev/XenosRecomp) | 990d03b28a27 | 2025-08-03 | MIT | 505 | 10 | 2026-03-12 | — |
| 19 | [rlaphoenix/NTON](https://github.com/rlaphoenix/NTON) | c5d543a91b7c | 2026-09-15 | GPL-3.0 | 245 | 8 | 2026-10-24 | 许可证以仓库 LICENSE 原文为准 |
| 20 | [rlaphoenix/hacBrewPack](https://github.com/rlaphoenix/hacBrewPack) | 745b16ecfc9c | 2019-10-13 | GPL-2.0 | 2 | 0 | 2026-09-15 | 许可证以仓库 LICENSE 原文为准 |
| 21 | [jakcron/nstool](https://github.com/jakcron/nstool) | cfb826ca6c16 | 2024-10-14 | MIT | 558 | 16 | 2024-10-14 | — |
| 22 | [TooTallNate/switch-nsp-forwarder](https://github.com/TooTallNate/switch-nsp-forwarder) | 845811585e0b | 2026-05-03 | — | 142 | 14 | 2026-06-16 | 许可证以仓库 LICENSE 原文为准 |
| 23 | [autorunhq/autorun](https://github.com/autorunhq/autorun) | 1ac9b6cf37b9 | 2026-10-16 | NOASSERTION | 525 | 62 | 2026-10-16 | — |
| 24 | [autorunhq/autorun-horizon-dlls](https://github.com/autorunhq/autorun-horizon-dlls) | 67e2303dee91 | 2026-10-16 | — | 8 | 0 | 2026-10-16 | — |
| 25 | [carafe-nx/carafe](https://github.com/carafe-nx/carafe) | 3334ebc66e9b | 2026-10-25 | GPL-3.0 | 253 | 9 | 2026-10-28 | 许可证以仓库 LICENSE 原文为准 |
| 26 | [Ryujinx 源流（网页侧旁证；结论由 Lead 定稿）](https://git.ryujinx.app/Ryubing/Canary) | — | — | NOASSERTION | — | — | 2026-08-26 | 无 GitHub API 数据（非 GitHub 仓库/未收录） |

---

*本报告为只读审计结果，不构成任何兼容性背书；所有"上游声称"均需后续本机复现验证。*