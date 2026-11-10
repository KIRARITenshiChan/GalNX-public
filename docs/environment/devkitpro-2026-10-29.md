# devkitPro 安装实录（M0 实测归档）

- 记录日期: 2026-10-29
- 执行: audit-switch（M0 实测归档任务 task-8）
- 机器: Windows_NT 10.0.26100 x64 · 16 核 · 宿主 shell PowerShell 7 · 仓库 E:/Othergames/Nintendo Switch
- 方法: 回读安装日志与包数据库（MSYS2 登录 shell 内执行 pacman -Q / -Qi / -Sg、uname、gcc、nxlink）、Windows 侧 sha256sum 复核产物、核对 /etc/pacman.conf 与 /etc/fstab 原文
- 结论: devkitPro（devkitA64 r30 + libnx 4.12.0）在本机可用；官方图形安装器内置 2018 年 MSYS2，Switch 开发包事务因 pkg.devkitpro.org 的 Cloudflare 403 静默失败，经 XferCommand 代理+UA 修复后手工补装成功；已用官方 application 模板构建出最小 NRO（166,085 B），构建目录必须无空格。

## 1. 安装背景与官方安装器

- 安装方式: devkitPro 官方 Windows 图形安装器 `devkitProUpdater` v3.0.3（发布 2018-06-03），由用户以管理员权限安装到 `D:/devkitPro`，安装时勾选了 `Switch Development` 组件。
- 安装器内置 MSYS2 2.10.0（安装器 INI 记录 `[msys2] Version=2.10.0`、`File=msys-2.10.0.1.7z`），安装后先自更新 `pacman -Syu --noconfirm`；因此 2026-10-29 的实际基础包为 MSYS2 更新后版本（见 §4）。
- 官方 wiki 称 “We provide an installer for 64bit windows which sets up a customised msys2 install already set up with the devkitPro packages.”（devkitPro pacman wiki），与本次安装方式一致。
- 安装器行为（NSIS 源码 `devkitPro/installer` 的 `nsis/devkitPro.nsi`）: 解压 MSYS2 到 `$INSTDIR/msys2`，改写 `msys2/etc/fstab` 把 `D:/devkitPro` 映射为 `/opt/devkitpro`，把 `msys2/usr/bin` 写入系统 PATH 最前，执行 `pacman.exe -Syu --noconfirm`，再按组件调用 `updateGroup`（Switch 组件对应 `switch-dev`），并写系统环境变量 `DEVKITPRO=/opt/devkitpro`、`DEVKITARM=/opt/devkitpro/devkitARM`、`DEVKITPPC=/opt/devkitpro/devkitPPC`。

## 2. Switch 开发包事务静默失败与 403 根因

### 2.1 日志证据（/var/log/pacman.log，2026-10-29）

| 时间（+0800） | 日志行 | 结果 |
| --- | --- | --- |
| 15:31:46 | `pacman -Syu --noconfirm` | 15:32:28 事务完成，升级 bash/filesystem/mintty/msys2-runtime/pacman-mirrors/pacman |
| 15:32:33 | `pacman -S --noconfirm --needed gba-dev` | 无事务记录 |
| 15:32:59 | `pacman -S --noconfirm --needed gp32-dev` | 15:33:34 事务完成（含 general-tools 1.4.4-1、devkit-env 1.0.1-2） |
| 15:34:20 | `pacman -S --noconfirm --needed nds-dev` | 15:34:20 事务完成（含 catnip 0.2.0-1） |
| 15:34:23 | `pacman -S --noconfirm --needed 3ds-dev` | 无事务记录 |
| 15:34:48 | `pacman -S --noconfirm --needed gamecube-dev` | 无事务记录 |
| 15:35:21 | `pacman -S --noconfirm --needed wii-dev` | 15:35:59 事务完成 |
| 15:36:07 | `pacman -S --noconfirm --needed switch-dev` | **只有 Running 行，之后无 transaction started/installed/completed**（静默失败） |
| 22:00:14 | `pacman -S --needed --noconfirm switch-dev`（手工重试） | 无事务记录 |
| 22:02:19 | 同上 | 无事务记录 |
| 22:05:42 | 同上 | 无事务记录 |
| 22:06:39 | 同上 | 无事务记录 |
| 22:07:08 | 同上（修复后） | 22:07:08 事务开始，22:07:16 完成，安装 14 个包 |
| 22:09:14 | `pacman -Sw --noconfirm --needed switch-sdl2` | 仅下载缓存，未安装 |

日志总行数 266；`grep switch-dev` 命中 5 条 Running 行，其中前 4 次均无后续 ALPM 事务行。静默失败表现为 pacman 退出但未输出/未记录事务，符合“包下载阶段被 Cloudflare 拒绝、脚本未捕获失败”的特征。

### 2.2 403 根因

- 直连 `https://pkg.devkitpro.org/...` 被 Cloudflare 拦截返回 403（站点在 Cloudflare 后，curl 无浏览器 User-Agent 时被盾）。
- MSYS2 登录 shell 中没有 `http_proxy/https_proxy` 环境变量（Windows 的代理设置不会被 MSYS2 登录 shell 自动继承）；而 git-bash 环境自带 `http_proxy/https_proxy=127.0.0.1:7897`，所以“Windows 上能上网”并不意味着 MSYS2 内 pacman 能下载。
- 本轮安装期间由 Lead 实测对照: MSYS2 内直连 pkg.devkitpro.org 为 403；同一 MSYS2 shell 显式加 `http_proxy/https_proxy=127.0.0.1:7897` 并带浏览器 UA 后为 200。

### 2.3 修复（已生效）

`/etc/pacman.conf` 第 18 行改为使用 curl 并显式注入代理与浏览器 UA（原文，备份后修改）:

```ini
XferCommand = /usr/bin/env http_proxy=http://127.0.0.1:7897 https_proxy=http://127.0.0.1:7897 /usr/bin/curl -L -C - -f -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36" -o %o %u
```

- 修改前已备份: `/etc/pacman.conf.bak-galnx-20261029`（22:01，2512 B）、`/etc/pacman.conf.bak-galnx-20261029-220910`（22:09，2628 B）；当前 `/etc/pacman.conf` 2708 B（22:09）。
- dkp 仓库配置（`/etc/pacman.conf` 第 77-81 行）: `[dkp-libs] Server = https://pkg.devkitpro.org/packages`、`[dkp-windows] Server = https://pkg.devkitpro.org/packages/windows/$arch`。
- 兜底手段: 若某次仍下载失败，可先用浏览器/代理手工下载 `.pkg.tar.zst` 与 `.sig` 放入 `/var/cache/pacman/pkg/`，再执行安装（本次 64 个缓存包即由 pacman 经 XferCommand 下载）。

## 3. 安装结果（2026-10-29T22:07:08 事务）

`switch-dev` 组共 13 个成员，其中 catnip、general-tools、devkit-env 在此前 gp32/nds 事务中已装；22:07 这次事务安装了其余 14 个包（含依赖自动带入的 devkitA64 工具链）。

### 3.1 本次事务安装的 14 个包

| 包 | 版本 | 已安装大小 | pacman 许可证字段 | 来源 URL（pacman -Qi） |
| --- | --- | ---: | --- | --- |
| devkitA64 | r30-1 | 0.00 B（元包） | GPL | https://devkitpro.org |
| devkita64-gcc | 16.1.0-1 | 293.07 MiB | spdx:GPL-3.0-or-later | https://www.gnu.org/software/gcc/gcc.html |
| devkita64-binutils | 2.46.0-1 | 39.12 MiB | spdx:GPL-3.0-or-later AND GPL-2.0-or-later AND LGPL-3.0-or-later AND LGPL-2.0-or-later | https://www.gnu.org/software/binutils/binutils.html |
| devkita64-newlib | 4.6.0.20260123-4 | 8.86 MiB | None（新元数据未声明） | None |
| devkita64-rules | 1.1.1-1 | 4.21 KiB | custom | http://github.com/devkitpro/devkita64-rules |
| devkitA64-gdb | 14.1-1 | 10.35 MiB | GPL | https://www.gnu.org/software/gdb |
| libnx | 4.12.0-1 | 70.94 MiB | custom | http://github.com/switchbrew |
| deko3d | 0.5.0-1 | 7.20 MiB | custom | http://github.com/devkitPro/deko3d |
| switch-tools | 1.13.1-1 | 616.71 KiB | ISC | https://github.com/switchbrew/switch-tools |
| uam | 1.1.0-2 | 2.38 MiB | ISC | https://github.com/devkitPro/uam |
| switch-pkg-config | 0.28-4 | 25.00 KiB | None | http://devkitpro.org/ |
| switch-cmake | 1.5.2-1 | 10.76 KiB | None | https://devkitpro.org/ |
| switch-examples | 20260201-1 | 2.36 MiB | custom | http://github.com/switchbrew/switch-examples |
| devkita64-cmake | 1.1.3-1 | 279.00 B | None | http://devkitpro.org/ |

- 关键依赖（pacman -Qi `Depends On`）: `devkitA64` 依赖 `devkita64-binutils>=2.46.0-1`、`devkita64-gcc>=16.1.0-1`、`devkita64-newlib>=4.6.0.20260123-4`；`devkita64-gcc` 依赖 `devkita64-binutils`、`devkita64-newlib`、`devkita64-rules`；`devkita64-rules` 依赖 `general-tools>=1.3.1`；`deko3d` 依赖 `libnx`；`switch-cmake` 依赖 `devkita64-cmake switch-tools uam switch-pkg-config`。
- 安装大小: 22:07 事务输出的 `Total Installed Size: 434.93 MiB`（Lead 记录）；本机 `pacman -Qi` 逐包复核这 14 包合计 **434.92 MiB**（差异 0.01 MiB 属舍入），相互印证。
- 若把同组的 catnip（26.72 KiB）、general-tools（278.39 KiB）、devkit-env（155 B）一并计入，17 包合计 435.22 MiB。

### 3.2 switch-dev 组成员（pacman -Sg switch-dev）

`catnip`、`deko3d`、`devkita64-cmake`、`libnx`、`switch-cmake`、`switch-examples`、`switch-pkg-config`、`devkit-env`、`devkitA64-gdb`、`devkita64-binutils`、`general-tools`、`switch-tools`、`uam`（13 个）。

注意: `devkitA64`、`devkita64-gcc`、`devkita64-newlib`、`devkita64-rules` 不在组列表里，但作为依赖随 `switch-dev` 自动安装。

### 3.3 全局状态

- `pacman -Q | wc -l` = **212** 个包（MSYS2 基础 + devkitARM/devkitPPC 等此前勾选组件 + switch 组件）。
- `/var/cache/pacman/pkg` 中 `*.pkg.tar.zst` 共 **64** 个；其中与 Switch 相关且已保留哈希的包括 devkitA64-r30-1、devkita64-gcc-16.1.0-1、devkita64-binutils-2.46.0-1、devkita64-newlib-4.6.0.20260123-4、devkita64-rules-1.1.1-1、libnx-4.12.0-1、switch-tools-1.13.1-1、switch-cmake-1.5.2-1、switch-examples-20260201-1、switch-pkg-config-0.28-4、uam-1.1.0-2、deko3d-0.5.0-1、catnip-0.2.0-1、general-tools-1.4.4-1、devkit-env-1.0.1-2，以及 22:09 预下载未安装的 switch-sdl2-2.28.5-4、switch-mesa-20.1.0-5、switch-libdrm_nouveau-1.0.1-2。
- 逐包 SHA-256 见 `docs/environment/evidence/cache-sha256-switch.txt`；完整包清单与哈希见同目录 `measure-2026-10-29.txt`。

## 4. 安装后环境（实测原文）

| 项 | 实测值 | 证据 |
| --- | --- | --- |
| MSYS2 根 | `D:/devkitPro/msys2` | 安装器行为 + `uname` |
| 路径映射 | `/etc/fstab`: `D:\devkitPro\ /opt/devkitpro`、`C:\Users /home` | `/etc/fstab` 原文 |
| DEVKITPRO | `/opt/devkitpro`（登录 shell 已导出） | `echo $DEVKITPRO` |
| MSYSTEM | `MSYS` | `echo $MSYSTEM` |
| 基础包 | bash 5.3.20-2、msys2-runtime 3.6.11-4、pacman 6.1.0-26、filesystem 2026.10.17-1、pacman-mirrors 20260129-1、mintty 1~3.8.3-1 | `pacman -Q` |
| 内核标识 | `MSYS_NT-10.0-26100 <主机名> 3.6.11-00eb8435.x86_64 2026-10-16 10:03 UTC x86_64 Msys` | `uname -a` |
| /etc/profile.d/devkit-env.sh | 仅导出 `DEVKITPRO`、`DEVKITARM`、`DEVKITPPC`，并把 `${DEVKITPRO}/tools/bin` 加入 PATH | 文件原文 |
| PATH | **不含** `/opt/devkitpro/devkitA64/bin`；直接调用 `aarch64-none-elf-gcc` 报“未找到命令” | 实测 |
| 磁盘 | `D:/devkitPro 754G 241G 513G 32% /opt/devkitpro`；`E: 1.9T 1.4T 492G 75% /e` | `df -h` |
| 目录体积 | `du -sh /opt/devkitpro` = 2.5G（含以前勾选安装的 devkitARM/devkitPPC 等多套工具链，不等于 switch 事务的 434.93 MiB） | `du -sh` |

进入 MSYS2 登录 shell 的实测可用形式（从 Windows 宿主 git-bash 调用）:

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc "命令"
```

因为 `devkitA64/bin` 不在 PATH，构建系统（`switch_rules`）用绝对路径调用工具链；手工验证时需写绝对路径或自行 `export PATH=/opt/devkitpro/devkitA64/bin:$PATH`。

## 5. 验证命令与结果

| 命令 | 实测输出/结果 | 结论 |
| --- | --- | --- |
| `/opt/devkitpro/devkitA64/bin/aarch64-none-elf-gcc --version` | `aarch64-none-elf-gcc.exe (devkitA64) 16.1.0`，Copyright (C) 2026 FSF | 通过 |
| 同上 `-dumpmachine` | `aarch64-none-elf` | 通过（目标三元组正确） |
| `/opt/devkitpro/devkitA64/bin/aarch64-none-elf-ld --version` | `GNU ld (GNU Binutils) 2.46.0.20260210` | 通过 |
| `make --version` | `GNU Make 4.4.1`（为 x86_64-pc-msys 编译，由 MSYS2 提供） | 通过 |
| `nxlink --help` | `Usage: nxlink [options] nrofile`；选项 `--help/-h`、`--address/-a`、`--retries/-r`、`--path/-p`、`--args`、`--server/-s` | 通过（工具存在） |
| `pacman -V` | `Pacman v6.1.0 - libalpm v14.0.0` | 通过 |
| `pacman -Q | wc -l` | 212 | 通过 |
| 模板构建（详见 workspaces/m0-hello/README.md） | 2026-10-29T22:12:21+08:00 在 `E:/galnx-build/m0-hello` 执行 `make -j4`，make_exit=0，产出 m0-hello.nro 166,085 B（SHA-256 `a341e7750e099da94c12541d8fb173793cc348688824c69f5f76c7ce29b9318b`） | 通过（只验证构建，未上机运行） |

注意: `nxlink --help` 只能证明工具存在；本次**未**在真机/网络加载器上实测上传 NRO。

## 6. 关键约束: 构建目录不能含空格（硬约束）

现象: 在 `E:/Othergames/Nintendo Switch/...`（含空格）内构建失败；在 `E:/galnx-build/...`（无空格）内构建成功。

根因（源码可见）: devkitPro 官方 application 模板的 Makefile 在 `all` 规则里执行

```make
$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile
```

`$(CURDIR)/Makefile` 未加引号，CURDIR 含空格时被 MSYS2/GNU make 拆成多个参数，子 make 找不到 `-f` 指向的文件。`$(CURDIR)` 又会被解析为物理长路径。

补充实测（Lead 记录）: 8.3 短路径（如 `OTHERG~1`）与目录 junction 都会被 MSYS2 解析回长物理路径，因此短路径/junction 不是绕过方案。

结论: 构建目录必须是**不含空格**的路径（本次用 `E:/galnx-build/m0-hello`），产物与日志再归档回工作区。该约束与操作系统无关，属 devkitPro 模板本身；后续 GalNX 的工作区设计必须把“构建沙箱目录”与“仓库路径”分离。

## 7. 复现步骤（本机已验证）

以下步骤为本次已实际走通的命令级流程；标注“待实测”的为尚未验证部分。

1. 运行 `devkitProUpdater-3.0.3.exe`，安装到 `D:/devkitPro`，组件勾选至少 `Switch Development`（本次实际勾选为多平台）。
2. 安装完成后若 `switch-dev` 静默失败（`/var/log/pacman.log` 中只有 Running 行），按 §2.3 为 `/etc/pacman.conf` 增加 XferCommand（代理+UA），备份原文件。
3. 在 MSYS2 登录 shell 中执行下列命令（实测可用）:

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc "pacman -Sy"
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc "pacman -S --needed --noconfirm switch-dev"
```

4. 验证工具链（绝对路径，因为 PATH 不含 devkitA64/bin）:

```bash
/opt/devkitpro/devkitA64/bin/aarch64-none-elf-gcc --version
/opt/devkitpro/devkitA64/bin/aarch64-none-elf-gcc -dumpmachine
/opt/devkitpro/tools/bin/nxlink --help
```

5. 构建最小 Homebrew: 在无空格目录执行 `cp -r /opt/devkitpro/examples/switch/templates/application/. /e/galnx-build/m0-hello && cd /e/galnx-build/m0-hello && make -j4`；产物为 `m0-hello.nro`。
6. （待实测）真机联调: 主机进入 hbmenu/网络加载器环境后，用 `nxlink -a <主机IP> m0-hello.nro` 上传运行；本次未执行，也未验证 Atmosphere/hbmenu 版本匹配。
7. （待实测）若需要 SDL2 等 portlibs: `pacman -S switch-sdl2`（22:09 只做了 `pacman -Sw` 预下载，未安装、未验证链接）。

## 8. 版本锁定与可复现性建议

devkitPro 仓库是滚动更新的，`/license` 与 wiki 均未提供类似 snapshot/日期镜像的官方机制（详见 `docs/audit/00-switch-base.md` 的“版本锁定建议”）。本机可用的锁定/复现手段按可靠性排序:

1. **包级快照（已做）**: `pacman -Q` 全量清单（212 包）+ 逐包版本；见 `evidence/pacman-Q-switch.txt`。恢复时按此清单 `pacman -S 包=版本` 未必可用（滚动仓库通常只保留最新版），因此必须配合第 2 项。
2. **包文件归档（已做）**: `/var/cache/pacman/pkg` 中 64 个包（含本次所需的 16 个 switch 相关包），逐包 SHA-256 见 `evidence/cache-sha256-switch.txt`。建议把这批 `.pkg.tar.zst`（及 `.sig`）复制出仓库长期保存；重装时用 `pacman -U` 离线安装，即可绕开仓库滚动。
3. **容器镜像（未实测）**: devkitPro 提供 Docker 镜像（如 `devkita64`），可用 digest 固定；`docs/audit/00-switch-base.md` 记录了 2026-10-29 查询到的 index/amd64 digest（latest 与 20260219 同 digest）。本机未安装 Docker，未验证该镜像能否构建本模板。
4. **产物哈希（已做）**: m0-hello 三个产物的 SHA-256 已固定（见 workspaces/m0-hello/README.md 与 `evidence/nro-sha256.txt`），可作为“同版本工具链应产出同二进制”的基准。
5. **工具链构建脚本（参考）**: `devkitPro/buildscripts` 提供从源码构建工具链的脚本（release tag 如 `devkitA64_r29.1`、`devkitA64_r30`），可用于长期重建，但属重型方案（需自行编译 GCC/newlib），本次未执行，且仓库声明面向个人使用。

结论: 短期以“`pacman -Q` 快照 + `/var/cache/pacman/pkg` 包归档 + 产物哈希”作为锁定证据；中期建立离线仓库（把缓存包 + 自制 dkp 仓库索引纳入仓库/制品库）；容器化留作 M1 之后的选项（需先验证 Docker 可用）。

## 9. 未验证 / 限制

- 15:36:07 `switch-dev` 静默失败时 pacman 的具体报错文本未被保留（只有“无事务”的日志证据）；403 根因由后续修复与对照实验反推。
- `434.93 MiB` 取自 pacman 事务输出（Lead 记录，pacman.log 不记录该字段）；本机 `pacman -Qi` 复核 14 包为 434.92 MiB。
- 图形安装器写入的系统 PATH 是否包含 `D:/devkitPro/msys2/usr/bin`、以及新开 Windows 终端能否直接调用 MSYS2 工具，本次未验证（所有 MSYS2 命令均用绝对路径调用）。
- `nxlink` 仅验证 `--help`，未实际联网上传 NRO；真机 hbmenu/网络加载器环境未验证。
- SDL2 及 portlibs 仅预下载缓存，未安装、未编译、未链接验证。
- `sudo`/pacman-key 步骤属 Unix 安装路径，本机 Windows 未涉及。
- “构建目录不能含空格”的判定基于本机实测失败/成功对照与 Makefile 源码；未在另一台机器复验。

## 10. 来源

- 安装日志: `D:/devkitPro/msys2/var/log/pacman.log`（2026-10-29 段，266 行；节选见 `evidence/pacman-log-2026-10-29.txt`）
- 包数据库: `pacman -Q`（212 行）、`pacman -Qi`（17 包）、`pacman -Sg switch-dev`；证据见 `docs/environment/evidence/` 下 `pacman-Q-switch.txt`、`pacman-qi-switch.txt`、`measure-2026-10-29.txt`
- 配置文件原文: `/etc/fstab`、`/etc/profile.d/devkit-env.sh`、`/etc/pacman.conf`（第 18 行、第 77-81 行），备份见 `/etc/pacman.conf.bak-galnx-*`
- 构建证据: `Workspace/GalNX/workspaces/m0-hello/build.log`、`m0-hello.nro|elf|nacp`、`env/raw_env_snapshot.txt`
- 官方文档: https://devkitpro.org/wiki/Getting_Started 、https://devkitpro.org/wiki/devkitPro_pacman 、https://github.com/devkitPro/installer 、https://github.com/devkitPro/pacman-packages 、https://github.com/devkitPro/buildscripts/releases
- 相关审计: `docs/audit/00-switch-base.md`（devkitPro 安装预案与版本锁定建议的只读审计基线）
