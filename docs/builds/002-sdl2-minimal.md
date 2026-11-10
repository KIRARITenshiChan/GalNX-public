# 002 — GalNX 最小 SDL2 应用构建记录（M1-a）

| 项 | 值 |
| --- | --- |
| 编号 | 002 |
| 对象 | GalNX 最小 SDL2 应用（m1-sdl2） |
| 任务 | task-14（M1-a：最小 SDL2 应用构建 NRO） |
| 执行 | audit-switch |
| 构建时间 | 2026-10-30T00:18:07+08:00（CMake） / 00:18:42+08:00（Make） |
| 工程目录 | `Workspace/GalNX/workspaces/m1-sdl2` |
| 构建根目录 | `/e/galnx-build/m1-sdl2`（CMake） / `/e/galnx-build/m1-sdl2-make`（Make） |
| 结果 | **两条后端均构建成功**；**运行未验证**（未上真机、未在 Citron 启动） |

## 1. 目标

验证 GalNX M1 阶段「从源码到最小 SDL2 NRO」的完整链路，覆盖：

1. devkitPro 交叉工具链（aarch64-none-elf-gcc / binutils / newlib / libnx）可用；
2. switch-sdl2（2.28.5-4）可被编译并静态链接；
3. devkitPro 提供的两种构建方式均可产出 NRO：`$DEVKITPRO/cmake/Switch.cmake` 与 devkitPro application 模板 Makefile；
4. 产物可校验（大小、SHA-256、NRO/ELF/NACP 结构）；
5. 为 M1 后续「运行验证（真机或模拟器）」准备可复现的构建记录。

## 2. 结论摘要

1. **CMake 后端通过**：`configure_exit=0`（8154 ms）、`build_exit=0`（4634 ms），产出 `m1-sdl2.nro` 6,740,165 B。
2. **devkitPro make 模板后端通过**（补 `-lm` 后）：`make_exit=0`，耗时 6812 ms，产出同大小 NRO。
3. 两后端 NRO 大小完全相同（6,740,165 B）、NACP 哈希完全一致；NRO 仅 384 字节不同（ELF 相差 144 B），判定**功能等价**。
4. **关键坑**：devkitPro 的 `sdl2-config --libs` 不含 `-lm`，Make 模板必须显式追加，否则链接失败；CMake 后端由平台 `NX_STANDARD_LIBRARIES="-lnx -lm"` 自带，不受影响。
5. **含空格路径**：CMake 后端可在含空格源路径直接构建（本工程即如此）；Make 模板必须先把源码暂存到无空格目录再构建。
6. 产物含非确定性内容，NRO/ELF **不保证比特可复现**；版本锁定应记录源码 + 工具链版本 + 产物哈希，而不是要求可复现构建。

## 3. 环境（实测）

| 组件 | 版本 | 证据 |
| --- | --- | --- |
| 宿主 | Windows NT 10.0.26100 x64（16 核） | `uname` 行 |
| MSYS2 | 3.6.11（`D:/devkitPro/msys2`） | `uname` 行 |
| DEVKITPRO | `/opt/devkitpro`（fstab: `D:\devkitPro /opt/devkitpro`） | 环境变量 / fstab |
| MSYSTEM | `MSYS` | 构建脚本 |
| devkitA64 | r30-1 | `pacman -Q` |
| gcc | aarch64-none-elf-gcc (devkitA64) 16.1.0 | `--version` / configure 日志 |
| binutils | GNU ld 2.46.0 | `ld --version` |
| newlib | 4.6.0.20260123-4 | `pacman -Q` |
| libnx | 4.12.0-1 | `pacman -Q` |
| switch-sdl2 | 2.28.5-4 | `pacman -Q` / pkg-config |
| switch-cmake | 1.5.2-1 | `pacman -Q` |
| switch-tools | 1.13.1-1 | `pacman -Q`（elf2nro/nacptool） |
| switch-pkg-config | 0.28-4 | `pacman -Q` |
| CMake | 4.0.2（MSYS2 包） | `cmake --version` |
| make | GNU Make 4.4.1（MSYS2 包） | `make --version` |
| pkg-config | 2.4.3（`aarch64-none-elf-pkg-config`） | configure 日志 |
| SDL2 | pkg-config 模块 2.28.5 | configure 日志 / `sdl2-config --version` |

调用 MSYS2 的统一模板（宿主 bash）：

```
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc "<命令>"
```

构建根目录一律在无空格路径：CMake 用 `/e/galnx-build/m1-sdl2`，Make 用 `/e/galnx-build/m1-sdl2-make`。

## 4. 源码与工程结构

### 4.1 `src/main.c`（205 行，全新原创）

功能：

- `SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS | SDL_INIT_JOYSTICK)`；
- 1280x720 窗口（`SDL_WINDOWPOS_CENTERED`，标题 `GalNX m1-sdl2`）；
- `SDL_CreateRenderer(win, 0, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC)`，失败回退 `SDL_RENDERER_SOFTWARE`；
- 24 条横向色带的动态渐变 + 两个往返方块 + 底部橙色横线（验证几何绘制与动画时序）；
- `while (!g_quit && appletMainLoop())` 主循环；`SDL_QUIT`、`SDLK_PLUS`、joystick `button == 10`（Switch 的 (+)）均可退出并打日志；
- `SDL_Log` 输出：SDL compiled/linked 版本、video driver、renderer 名称/flag/max_texture、窗口尺寸、桌面显示模式、joystick 数量；每秒输出一次 `fps`/`frames`/`total`/`window`；退出时输出总帧数、耗时、平均 FPS；
- 无第三方代码拷贝；参考 devkitPro 官方 `sdl2-simple` 示例的初始化顺序（未复制其代码）。

### 4.2 `CMakeLists.txt`（856 B）

- `cmake_minimum_required(VERSION 3.13)`；`project(m1-sdl2 C)`；C11；
- `find_package(PkgConfig REQUIRED)` + `pkg_check_modules(SDL2 REQUIRED IMPORTED_TARGET sdl2)`（devkitPro 的 `Switch.cmake` 已保证使用 `aarch64-none-elf-pkg-config`）；
- `add_executable(m1-sdl2 src/main.c)`；`-O2 -Wall`；`target_link_libraries(... PkgConfig::SDL2)`；
- `nx_create_nro(m1-sdl2)`：使用 `Platform/NintendoSwitch.cmake` 封装的 `elf2nro`，默认生成 `<target>.nro` 到构建目录，NACP 由 `nx_generate_nacp` 生成（默认名/作者/版本）。

### 4.3 `Makefile`（7697 B，devkitPro application 模板派生）

- 由 devkitPro application 模板改写：`TARGET := m1-sdl2`、`SOURCES := source`、`BUILD := build`；
- 追加：`CFLAGS += $(INCLUDE) -D__SWITCH__ $(shell sdl2-config --cflags)`；
- 关键修改：`LIBS := $(shell sdl2-config --libs) -lm`（原始 `sdl2-config --libs` 缺 `-lm`，见第 8 节）。

### 4.4 构建脚本

- `scripts/build-cmake.sh`（2090 B）：清理构建目录 → CMake configure → build（`-j 8`）→ 记录耗时/退出码 → 生成产物哈希与 `build.log`；
- `scripts/build-make.sh`（1819 B）：把 Makefile 与 `src/main.c` 暂存到 `/e/galnx-build/m1-sdl2-make`（`source/main.c`）→ `make -j 8` → 记录耗时/退出码/哈希。

## 5. 构建命令与结果

### 5.1 CMake（主后端）

```
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash "/e/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m1-sdl2/scripts/build-cmake.sh"'
```

脚本内部等价命令：

```
cmake -S "/e/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m1-sdl2" \
      -B /e/galnx-build/m1-sdl2 \
      -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/Switch.cmake"
cmake --build /e/galnx-build/m1-sdl2 -j 8
```

| 指标 | 值 |
| --- | ---: |
| configure_exit | 0 |
| configure 耗时 | 8154 ms（日志: Configuring done 7.8s / Generating done 0.1s） |
| build_exit | 0 |
| build 耗时 | 4634 ms |
| total | 12788 ms |

configure 日志关键行：

```
-- Check for working C compiler: /opt/devkitpro/devkitA64/bin/aarch64-none-elf-gcc.exe - skipped
-- Found PkgConfig: /opt/devkitpro/portlibs/switch/bin/aarch64-none-elf-pkg-config (found version "2.4.3")
-- Checking for module sdl2 -- Found sdl2, version 2.28.5
-- GalNX: SDL2 pkg-config version=2.28.5
-- Configuring done (7.8s)
-- Generating done (0.1s)
```

build 日志关键行：

```
[ 25%] Building C object CMakeFiles/m1-sdl2.dir/src/main.o
[ 50%] Linking C executable m1-sdl2.elf
[ 50%] Built target m1-sdl2
[ 75%] Generating m1-sdl2_nro.default.nacp
[100%] Building NRO executable target m1-sdl2_nro
[100%] Built target m1-sdl2_nro
```

### 5.2 devkitPro make 模板（备选后端）

```
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash "/e/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m1-sdl2/scripts/build-make.sh"'
```

脚本先把 `Makefile` 与 `src/main.c` 暂存到 `/e/galnx-build/m1-sdl2-make`，再执行 `make -j 8`（PATH 前置 `$DEVKITPRO/portlibs/switch/bin` 以找到 `sdl2-config`）。结果：`make_exit=0`，elapsed 6812 ms。

```
main.c
built ... m1-sdl2.nacp
linking m1-sdl2.elf
built ... m1-sdl2.nro
```

## 6. 产物与哈希

| 后端 | 文件 | 大小（B） | SHA-256 |
| --- | --- | ---: | --- |
| CMake | m1-sdl2.nro | 6,740,165 | `d46ae7c0786ade931b4041778eca0d1b33831892818fc5bbe5bd94fbb6c575bf` |
| CMake | m1-sdl2.elf | 15,503,664 | `78e21a1e93eac5c38190eb0d66660069a19a0dcb1955b222ad8a59c3d10c4531` |
| CMake | m1-sdl2_nro.default.nacp | 16,384 | `ae53d5a22425e9de75c2bf9bd33586fead376c095162ebaacdde6b38bf530a1d` |
| Make | m1-sdl2.nro | 6,740,165 | `0a70b6f38f894770f90ea8afb267248e556c286309c052488d44dc45e2cc51b0` |
| Make | m1-sdl2.elf | 15,503,520 | `593ccd522ed22c8f5856193411d45e32ca0cab3024c7dd00f699456de8d27c6a` |
| Make | m1-sdl2.nacp | 16,384 | `ae53d5a22425e9de75c2bf9bd33586fead376c095162ebaacdde6b38bf530a1d` |

归档：CMake 三件产物复制到 `workspaces/m1-sdl2/` 根目录（`m1-sdl2.nro` / `m1-sdl2.elf` / `m1-sdl2_nro.default.nacp`），两后端全部产物副本在 `workspaces/m1-sdl2/evidence/`。

结构校验：

- **NRO 头**（两后端相同）：前 16 字节 `20 00 00 14 f0 00 00 00 48 4f 4d 45 42 52 45 57`；offset 8 起 ASCII `HOMEBREW`；`NRO0` magic 位于 offset 0x10。
- **ELF**（CMake 版）：ELF64 / little-endian / Type DYN (Position-Independent Executable) / Machine AArch64 / Entry point 0x0；符号表可见 `main`、`appletMainLoop`、`SDL_Init`、`SDL_CreateWindow`、`SDL_CreateRenderer`、`SDL_RenderPresent`。
- **NACP**：可打印串包含 `m1-sdl2` 与 `Unspecified Author`（默认作者，重复出现于各语言槽位）。

> 注：MSYS2 未安装 `strings` 命令（`strings: command not found`），可打印串检查使用宿主 python 解析完成。

## 7. 双后端对比

| 项 | CMake 后端 | Make 后端 | 对比 |
| --- | --- | --- | --- |
| 构建结果 | exit 0 | exit 0 | 等价 |
| 耗时 | 12,788 ms（configure 8,154 + build 4,634） | 6,812 ms（含暂存拷贝） | Make 更快（无 CMake 配置阶段） |
| NRO 大小 | 6,740,165 B | 6,740,165 B | **完全相同** |
| NRO SHA-256 | `d46ae7c0...` | `0a70b6f3...` | **不同**，`cmp -l` 计 384 字节差异 |
| ELF 大小 | 15,503,664 B | 15,503,520 B | 差 144 B |
| NACP SHA-256 | `ae53d5a2...` | `ae53d5a2...` | **完全一致** |

差异分析：NACP 完全一致说明元数据（标题/作者/版本）生成相同；NRO 大小相同说明代码与数据段规模一致；NRO 内 384 字节与 ELF 144 字节差异来自两种后端的链接/编译参数差异（例如 CMake 平台额外传入 `NX_STANDARD_LIBRARIES`、Make 模板追加 `-D__SWITCH__` 与 `-lm` 的位置不同）以及调试信息/节布局差异。两后端产物均通过结构校验，判定功能等价。具体差异字节的含义未逐一分析。

**非比特可复现**：本会话早前一次 CMake 构建（同源码同构建目录）得到 ELF 15,503,656 B（本次 15,503,664 B），NRO 哈希也不同；说明产物中存在构建时可变内容（机制未定位，未做 `-frandom-seed`/`SOURCE_DATE_EPOCH` 实验）。版本锁定不能依赖哈希可复现，只能记录哈希作为“本次构建指纹”。

## 8. 失败点与修复

### 8.1 Make 后端首次链接失败（已修复）

- 现象：`make` exit 2，链接错误为未定义数学函数引用，例如：
  `undefined reference to atan2`、`atan2f`、`cos`、`cosf`、`sin`、`sinf`、`sqrt`、`sqrtf`、`powf`、`log2f`、`exp2f`、`logf`、`expf`；
  引用来自 `libSDL2.a(SDL_stdlib.o)`、`libEGL.a(main_light.c.o / m_matrix.c.o / ir_constant_expression.cpp.o)`。
- 根因：devkitPro 的 `sdl2-config --libs` 输出为：
  `-L/opt/devkitpro/portlibs/switch/lib /opt/devkitpro/portlibs/switch/lib/libSDL2.a -fPIE -L/opt/devkitpro/libnx/lib -lEGL -lstdc++ -lglapi -ldrm_nouveau -lnx -lpthread`（**不含 `-lm`**）；
  而 devkitPro CMake 平台文件自带 `NX_STANDARD_LIBRARIES="-lnx -lm"`，所以 CMake 后端不暴露此问题。
- 修复：Makefile 的 `LIBS` 追加 `-lm`，重新构建 `make_exit=0`。
- 复现建议：任何使用 devkitPro Makefile 模板 + SDL2（或其他依赖 libm 的 portlib）的工程都应显式链接 `-lm`。

### 8.2 其他环境问题

1. **含空格路径**：devkitPro 模板 `switch_rules` 中 `$(MAKE) -C $(BUILD) -f $(CURDIR)/Makefile` 未加引号，源码/构建路径含空格时拆词失败；Make 后端因此先暂存到 `/e/galnx-build/m1-sdl2-make`。CMake 后端无此问题。
2. **CMake 冷启动**：首次 configure 8.2 s（pkg-config/交叉编译器探测），非失败。
3. **日志编码**：`build.log` 的 `uname` 行含 GBK 编码主机名，按原始字节归档（不是合法 UTF-8），用 UTF-8 读取会显示替换字符；证据文件保留原始字节。
4. **首次失败日志**：Make 首次失败的错误日志被随后成功构建的日志覆盖，错误原文在本记录第 8.1 节留档。

## 9. 未验证 / 限制

- **未运行**：NRO 未在 Switch 真机、未在 Citron 模拟器启动；是否能被 hbmenu/Citron 加载、初始化是否成功均未验证。
- 渲染输出、Plus/(+) 退出、FPS 日志、joystick 编号（+ = button 10）均未运行验证；日志时序（每秒一次）未验证。
- 未测试 1920x1080 窗口模式（devkitPro 示例提到的另一可用模式）、romfs 资源加载、SDL_image/ttf/mixer 运行。
- NACP 使用默认作者 `Unspecified Author`，未配置 `APP_AUTHOR`/版本/图标（使用 libnx 默认 icon）。
- 未在含空格路径直接执行 Make 构建（仅 CMake 验证过含空格源路径）。
- 未验证 `nxlink` 网络部署方式（属 M1 后续任务）。
- 未做 `-frandom-seed`、`SOURCE_DATE_EPOCH` 等确定性构建实验。

## 10. 对 GalNX 的启示

1. **构建后端选 CMake 为主**：devkitPro 官方 `Switch.cmake` 支持的 CMake 路径可处理含空格源路径、pkg-config 依赖解析，且自动带上 `-lnx -lm`；Makefile 模板保留为兼容/对照路径。
2. **`-lm` 必须显式**：若使用 Makefile 模板 + SDL2 组合，必须验证链接行包含 `-lm`；否则会在链接期才报错。
3. **构建目录无空格仍是硬约定**：虽然 CMake 能构建含空格源路径，但 Make 模板不能，为统一 CI/脚本，构建根固定 `/e/galnx-build/<id>`。
4. **产物指纹而非可复现构建**：记录源码哈希 + 工具链版本（pacman -Q 快照）+ 产物 SHA-256；不要以“重建哈希相同”作为验收条件。
5. **下一步（M1 运行验证）**：优先用 Citron/真机 + nxlink 捕获 `SDL_Log`，确认 video driver/renderer/分辨率日志与 Plus 退出；NRO 6.74 MB（静态链接 SDL2+libnx）属正常规模。

## 11. 复现步骤

1. 环境检查（MSYS2 内）：`pacman -Q devkitA64 switch-sdl2 switch-cmake switch-tools switch-pkg-config libnx`；确认 `DEVKITPRO=/opt/devkitpro`。
2. 执行 5.1 或 5.2 的构建命令（脚本已封装）。
3. 校验：比对第 6 节大小；哈希应至少与“本次构建指纹”一致（注意 NRO 非比特可复现，重构建后哈希可能不同）。

## 12. 证据文件（`workspaces/m1-sdl2/evidence/`）

| 文件 | 大小（B） | 说明 |
| --- | ---: | --- |
| artifacts-sha256.txt | 587 | 两后端全部产物哈希清单 |
| cmake/build.log | 2047 | CMake 构建汇总（时间戳、版本、耗时、日志、产物） |
| cmake/logs-cmake-configure.log | 644 | configure 原始输出 |
| cmake/logs-cmake-build.log | 252 | build 原始输出 |
| cmake/m1-sdl2.nro | 6,740,165 | CMake 产物副本 |
| cmake/m1-sdl2.elf | 15,503,664 | CMake 产物副本 |
| cmake/m1-sdl2_nro.default.nacp | 16,384 | CMake 产物副本 |
| make/build.log | 1048 | Make 构建汇总 |
| make/logs-make-build.log | 72 | Make 原始输出 |
| make/m1-sdl2.nro | 6,740,165 | Make 产物副本 |
| make/m1-sdl2.nacp | 16,384 | Make 产物副本 |

工程源码与产物哈希索引见 `workspaces/m1-sdl2/README.md`。

## 13. 相关文档

- 工程说明：[`workspaces/m1-sdl2/README.md`](../../workspaces/m1-sdl2/README.md)
- devkitPro 安装与环境实测：[`docs/environment/devkitpro-2026-10-29.md`](../environment/devkitpro-2026-10-29.md)
- 工具链审计（集群 A）：[`docs/audit/00-switch-base.md`](../audit/00-switch-base.md)
- 上游版本复核：[`docs/audit/05-toolchain-refresh.md`](../audit/05-toolchain-refresh.md)
- 构建记录索引：[`docs/builds/README.md`](README.md)

## 14. 运行验证（Lead 实测，2026-10-30 00:24，Citron nightly 0237a9b88）

本节为交付后由 Lead 补充的模拟器冒烟结果；原文第 9 节「未运行」的限制中，**模拟器启动/渲染部分已解除**（真机仍未验证）。

### 14.1 方法与证据

- 工具：`bash scripts/citron_run.sh --nro workspaces/m1-sdl2/m1-sdl2.nro --timeout 70 --settle 8 --expect-title m1-sdl2 --app-log-regex 'Booting game:'`（脚本来自 task-15/M1-b）。
- 退出码 0，`status=loaded`，`elapsed_s=15`。
- 窗口标题：`citron Nightly | 0237a9b88 | m1-sdl2 (64-bit) | NVIDIA`（标题含 NRO 名 → 信号 1 通过）。
- boot 行：`[   1.670244] Frontend <Info> citron\main.cpp:2475:BootGame: Booting game: 0000000000000000 | m1-sdl2 (64-bit)`（信号 2 通过）。
- 截图：`printwindow` 方法，79,701 B，`nonblack_ratio=0.8907`；人工核验画面为 SDL2 渲染的**垂直渐变背景 + 白色方块（左上）+ 黑色方块（中下）**，Citron 状态栏显示 `VULKAN / NORMAL / DOCKED / BILINEAR / NO AA / Game: 60 FPS / Frame: 16.66 ms`。
- 证据（已复制入库）：`docs/milestones/evidence/M1a-citron-m1-sdl2-window.png`（sha256 `8be238c81223099e79abff5bb31b4266a6eff33f115808ba5beb2a96a6bbc1d3`）、`docs/milestones/evidence/M1a-citron-m1-sdl2-result.json`（sha256 `ab25ef598892971eab8664dab5a8cfe171c9c89f726c76505308807f50dbb4bc`）。原始运行目录：`workspaces/citron-harness/runs/20261030-002444-m1-sdl2/`（gitignored）。

### 14.2 结论

- **M1-a 验收通过（模拟器范围）**：最小 SDL2 NRO 能被 Citron 加载、初始化 SDL2 video/renderer、稳定渲染并跑满 60 FPS；画面内容与源码逻辑（渐变 + 两个移动方块）一致。
- Citron 日志记录了 `Load: Loading m1-sdl2 (0000000000000000)` 与 boot 行，可作为后续 M2 输入层、M3 打包的观测点。
- 应用自身的 `SDL_Log` 输出未出现在 Citron 日志中（Citron 未转发 guest stdout）；因此「driver/renderer 名称、分辨率、帧数日志」需改用 nxlink（真机/网络调试）或后续在 GalNX 测试后端里采集 guest 控制台。**这是 Citron 测试后端的一条已知限制**，应在 M1 里程碑文档中登记。
- 仍未验证：真实 Switch 真机、Plus/(+) 退出路径（模拟器内未触发）、1080p 窗口模式、romfs/图片/字体加载。
