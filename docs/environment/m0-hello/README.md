# m0-hello 最小 Homebrew 构建记录

- 日期: 2026-10-29 22:12:21 (+0800)
- 执行: audit-switch（M0 实测归档 task-8）
- 状态: **构建通过（make 退出码 0），未上机运行**
- 上游来源: devkitPro 官方模板 `$DEVKITPRO/examples/switch/templates/application`（switch-examples 20260201-1），源码未修改

## 1. 结论

本目录归档了 GalNX 的 M0 最小 Homebrew 构建：用 devkitPro 官方 application 模板在无空格的构建目录 `E:/galnx-build/m0-hello` 执行 `make -j4`，产出可用的 NRO（166,085 B）及 ELF/NACP，`make` 退出码 0。这是计划 §10「M0 已完成验收」中“最小 Homebrew 构建通过”一项的证据。

未完成部分: 没有把 NRO 放进模拟器（Ryujinx）或真机（hbmenu/网络加载器）运行，因此“可启动/可交互”仍未验证；“Hello World!”只是模板代码的打印内容，不是运行结果。

## 2. 构建环境

| 项 | 值 |
| --- | --- |
| 宿主 | Windows_NT 10.0.26100 x64，16 核 |
| 构建 shell | MSYS2（`D:/devkitPro/msys2`），`MSYSTEM=MSYS` |
| MSYS2 内核 | `MSYS_NT-10.0-26100 <主机名> 3.6.11-00eb8435.x86_64 2026-10-16 10:03 UTC x86_64 Msys` |
| DEVKITPRO | `/opt/devkitpro`（MSYS2 内路径，对应 Windows `D:/devkitpro`） |
| 编译器 | `aarch64-none-elf-gcc (devkitA64) 16.1.0` |
| binutils | `GNU ld (GNU Binutils) 2.46.0.20260210` |
| libnx | 4.12.0-1 |
| make | GNU Make 4.4.1（MSYS2） |
| 构建目录 | `E:/galnx-build/m0-hello`（**无空格**） |
| 归档目录 | `E:/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m0-hello`（含空格） |

完整工具链版本见 `docs/environment/devkitpro-2026-10-29.md` 与 `build-provenance.json`；环境快照原文见 `env/raw_env_snapshot.txt`（345 行）。

## 3. 构建命令

由 `scripts/m0_build_hello.sh` 在 MSYS2 登录 shell 内执行，等价命令:

```bash
BUILD=/e/galnx-build/m0-hello
TRACE=/e/Othergames/Nintendo\ Switch/Workspace/GalNX/workspaces/m0-hello
mkdir -p "$BUILD"
cp -r /opt/devkitpro/examples/switch/templates/application/. "$BUILD/"
cd "$BUILD"
make -j4
```

实际调用形式: `env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc "..."`。

## 4. 执行日志与退出码

`build.log`（356 B，11 行，sha256 `4692f60fb68aae291ee7e84b493628a114cda7b1ada4480d01ac935b18c8b737`）记录了以下关键行:

- `date=2026-10-29T22:12:21+08:00`
- `uname=MSYS_NT-10.0-26100 <主机名> 3.6.11-00eb8435.x86_64 2026-10-16 10:03 UTC x86_64 Msys`
- `DEVKITPRO=/opt/devkitpro`、`MSYSTEM=MSYS`
- `build_dir=/e/galnx-build/m0-hello`、`trace_dir=/e/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m0-hello`
- 编译与链接步骤: `main.c` → `built ... m0-hello.nacp` → `linking m0-hello.elf` → `built ... m0-hello.nro`
- **`make_exit=0`**

日志中的主机名为 GBK 编码（Windows 主机名非 ASCII），直接按 UTF-8 读取会出现替换字符；这不影响其他字段。

## 5. 产物清单

| 文件 | 大小（字节） | SHA-256 | 说明 |
| --- | ---: | --- | --- |
| `m0-hello.nro` | 166,085 | `a341e7750e099da94c12541d8fb173793cc348688824c69f5f76c7ce29b9318b` | Homebrew 可执行文件（NRO），M0 验收对象 |
| `m0-hello.elf` | 2,878,832 | `71179a97c0c556b7433101e6f6525f8d8ba84ae439a0740f085c815e1ef8ef6c` | 链接产物（含调试信息） |
| `m0-hello.nacp` | 16,384 | `88115686a4c3eb71efdee214ad42bfc107865403c50b6ec35b948b62894e360f` | 应用元数据（NACP），16 KiB 对齐 |

三个产物均归档在本目录；同批哈希另见 `docs/environment/evidence/nro-sha256.txt`。

## 6. 构建输入

| 输入 | 大小 | SHA-256 |
| --- | ---: | --- |
| `Makefile`（模板原文） | 7,654 | `ef3376322f62bb88339bc61a5299b3bc130eb9c794b594f3ff41d41ce44ff50f` |
| `source/main.c`（模板原文，未改动） | 1,820 | `b2dcdd896f4a420b4b0053194a63f7ddc8572e4892692edc69285c112dea84d0` |

`main.c` 是 libnx 官方控制台示例: `consoleInit(NULL)` → `padConfigureInput` → `printf("Hello World!\n")` → `appletMainLoop()` 内 `consoleUpdate`，按 `HidNpadButton_Plus` 退出并 `consoleExit`。

Makefile 关键变量: `TARGET=$(notdir $(CURDIR))`（即 `m0-hello`）、`BUILD=build`、`SOURCES=source`、`ARCH=-march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE`、`CFLAGS=-g -Wall -O2 -ffunction-sections`、include `$(DEVKITPRO)/libnx/switch_rules`。

## 7. 归档与清理策略

- 构建发生在 `E:/galnx-build/m0-hello`，**不在**仓库内；仓库内只保留产物、日志与快照（本目录）。
- 原因: devkitPro 模板的 Makefile 在 `all` 规则里用 `$(MAKE) -C $(BUILD) -f $(CURDIR)/Makefile`，`$(CURDIR)` 未加引号，路径含空格会被拆词；8.3 短路径与 junction 都会被 MSYS2 还原为长物理路径。详见 `docs/environment/devkitpro-2026-10-29.md` §6。
- `build/` 中间目录未归档，可由命令重新生成。

## 8. 与计划的验收映射

| 计划要求 | 证据 | 状态 |
| --- | --- | --- |
| §10 M0「固定 devkitPro/libnx 版本、构建环境说明」 | `build-provenance.json`、`docs/environment/devkitpro-2026-10-29.md`、`docs/environment/evidence/pacman-Q-switch.txt` | 通过 |
| §10 M0「最小 Homebrew 构建通过」 | 本目录产物 + `build.log`（`make_exit=0`） | 通过 |
| §9.2「保存依赖版本、源码 commit、构建日志、资源哈希和测试结果」 | `build-provenance.json`（版本与输入哈希）、`build.log`、产物 SHA-256 | 通过（工具链与模板；游戏资源尚未涉及） |
| §9.2「能在固定版模拟器上启动并收集日志」 | 无 | **未验证** |
| §9.2「能在真实 NS1 上手动完成基本流程」 | 无 | **未验证** |
| §10 M0「模拟器最小启动测试（把 m0-hello.nro 跑进 Ryujinx 并收日志）」 | 无 | **未完成**（M0 收尾待办） |
| §14「在干净环境复现一个简单 Homebrew 工程的构建：devkitPro 补装（14 包）+ m0-hello.nro」 | 本目录产物与 `build.log`；14 包安装明细见 `docs/environment/devkitpro-2026-10-29.md` | 通过（本记录为该条的执行证据） |
| §14「明确本机 Ryujinx 1.3.265 二进制与源码提交的对应关系」 | 无 | 不在本记录范围（见 `docs/TOOLCHAIN_AUDIT.md` §5，标 `not-verified`） |

## 9. 复现步骤

前提: 已按 `docs/environment/devkitpro-2026-10-29.md` 安装 devkitPro 并补装 `switch-dev`；构建目录所在盘符有足够空间（ELF 约 2.9 MB，中间对象另计）。

1. 在 MSYS2 登录 shell 内确认 `echo $DEVKITPRO` 输出 `/opt/devkitpro`。
2. 创建无空格构建目录: `mkdir -p /e/galnx-build/m0-hello`。
3. 复制模板: `cp -r /opt/devkitpro/examples/switch/templates/application/. /e/galnx-build/m0-hello/`。
4. 构建: `cd /e/galnx-build/m0-hello && make -j4`。
5. 校验产物: `sha256sum m0-hello.nro m0-hello.elf m0-hello.nacp`，与本目录哈希对照；若工具链版本完全一致应得到相同哈希（本次为单次记录，未做重复构建对照，哈希一致性暂标“待实测”）。
6. 归档: 把三个产物、`build.log`、`env/raw_env_snapshot.txt` 复制回本目录。

## 10. 已知限制

- 只验证“能构建”，未验证“能运行”。NRO 未进模拟器、未上真机。
- 模板使用默认配置: 无自定义图标、无 `APP_TITLE`/`APP_AUTHOR`/`APP_TITLEID`、无 RomFS，产物名取自目录名。
- 只依赖 libnx 基础库；未链接 SDL2、freetype、mpv 等 portlibs（switch-sdl2 仅预下载缓存，未安装）。
- 单次构建，未做可复现性对照（相同输入重建是否得到相同哈希未验证）。
- 主机名为 GBK 编码，`build.log`/快照中的主机名在 UTF-8 视角下为乱码，属已知显示问题。

## 11. 相关文件

- `build-provenance.json` — 机读构建出处记录
- `build.log` — 构建日志（11 行）
- `env/raw_env_snapshot.txt` — 构建时环境变量与工具链快照（345 行）
- `Makefile`、`source/main.c` — 模板构建输入
- `docs/environment/devkitpro-2026-10-29.md` — 安装实录（含 403 修复、路径约束）
- `docs/environment/evidence/` — 证据索引与原始数据
