# 001 — krkrsdl2 上游 Switch 构建记录（M1 主体）

| 项 | 值 |
| --- | --- |
| 编号 | 001 |
| 对象 | krkrsdl2 上游（KiriKiri SDL2） |
| 任务 | task-13（M1：从源码到 NRO） |
| 执行 | audit-engines（Lead 协同：build5 首轮 ninja 排障 + data-withfont.xp3 内容包） |
| 构建时间 | 2026-10-30 00:38–00:40（+08:00）；首次成功 00:38:17，复现校验 00:39:45 |
| 工程目录 | `E:/galnx-build/m1-krkrsdl2`（克隆；工作区记录 `Workspace/GalNX/workspaces/m1-krkrsdl2`） |
| 构建根目录 | `E:/galnx-build/m1-krkrsdl2/build5` |
| 结果 | ✅ **构建成功**（两条含合法 KAG3 demo 数据的 NRO）；✅ **Citron 运行验证已由后续修复版完成**（见 `004-krkrsdl2-switch-fixes.md`：干净补丁版 NRO 在 Citron 渲染出 KAG3 demo 标题画面；本记录产物为未打补丁版，直接运行会在启动阶段退出） |

## 1. 目标

验证 GalNX M1 里程碑的「已有引擎 + 上游构建系统 → 可加载的 NRO」链路：

1. 在 Windows 本机（无容器）复现 krkrsdl2 上游 CI 的 `switch` 目标构建，源码锁定到 `124bdf84`；
2. 使用**可合法分发**的测试数据（KAG3 demo），而非上游 release 里的空壳 `data.xp3`；
3. 产出可校验的 NRO（大小、SHA-256、NRO/NACP 结构），并留下可复现的命令、日志与绕坑记录；
4. 为后续 M1-d（Citron/真机运行验证）交接一个「构建已通、内容已内嵌」的候选产物。

## 2. 结论摘要

1. **构建成功**：两条 NRO（含真实 KAG3 demo 数据）由本地 devkitPro 工具链产出，`ninja` 退出码 0；上游 408 个编译单元全部通过，无源码修改。
2. 主产物 A：`krkrsdl2-realdata.nro`（= `withfont.nro`）**17,907,245 B**，SHA-256 `e324c2d08b0a2d468b7bf9c2112d5fa699430875a6ffa187961b32ce3d32fffe`，内嵌 `data-withfont.xp3`（6,628,897 B）。
3. 对照产物 B：`krkrsdl2-dataxp3.nro` **16,042,653 B**，SHA-256 `d691471bd40673837148d22c8a4466bc98d6b5ad905414792b9e735d001a3d67`，内嵌 `data.xp3`（4,764,317 B）。
4. **内容级可复现**：产物 A 在「切换数据包 → 清 romfs → 切回」后重建，得到**完全相同的 SHA-256**（同源码/同工具链/同数据）。
5. 上游 CI 的 `switch` job 在 Linux 容器 `devkitpro/devkita64:20241023` + Ninja 下跑通；本地在 Windows 上复现时遇到 **4 个宿主专有坑**（MSYS2 cmake 强制、make depfile 盘符冒号、PCH 内嵌 POSIX 绝对路径、归档命令行超 32,767），均已绕开，**未改上游源码**。
6. 上游 release 里的 `data.xp3`（kag3-demo release 资产）实测只有 **65 B**（构建时子模块未展开产生的空 XP3 存根），不能用于内容验证；本记录改用 Lead 用 `kag3-demo` 子模块 `external/kag3@b21b16ea` + `krkrrel-ng` 打包的合法数据。
7. 产物是**单游戏内嵌数据**形态（`EMBED_DATA_PATH` 编进 RomFS），不是 krkr-ns 那种多游戏启动器；NRO 未做 NSP 打包。
8. 遗留风险：KAG3 demo 默认引用系统字体（MS PMincho/MS Gothic），Switch 无系统字体，运行期可能字体缺失；需 M1-d 实测（Lead 已准备换字体方案）。

## 3. 环境（实测）

| 组件 | 版本 | 证据 |
| --- | --- | --- |
| 宿主 | Windows NT 10.0.26100 x64（16 核） | env_report / 系统信息 |
| MSYS2 | 3.6.11（`D:/devkitPro/msys2`） | `uname -s -r` → `MSYS_NT-10.0-26100 3.6.11` |
| DEVKITPRO | `/opt/devkitpro`（fstab 映射 `D:\devkitPro /opt/devkitpro`） | 登录 shell 环境变量 |
| devkitA64 | r30-1 | `pacman -Q devkitA64` |
| gcc | aarch64-none-elf-gcc (devkitA64) 16.1.0 | `--version` / configure 日志 |
| libnx | 4.12.0-1 | `pacman -Q libnx` |
| switch-sdl2 | 2.28.5-4 | `pacman -Q` / pkg-config 模块 2.28.5 |
| switch-cmake | 1.5.2-1 | `pacman -Q` |
| switch-tools | 1.13.1-1（`elf2nro` 53,760 B） | `pacman -Q` / `stat` |
| switch-pkg-config | 0.28-4（`aarch64-none-elf-pkg-config` 2.4.3） | `pacman -Q` / `--version` |
| CMake | 4.0.2（MSYS2 包，POSIX 构建；**不是**原生 Windows cmake） | `cmake --version` |
| make | GNU Make 4.4.1-2（失败路线使用） | `pacman -Q make` |
| Ninja | 1.13.2-1（MSYS2 `/usr/bin/ninja`，**成功路线使用**） | `ninja --version` |
| SDL2 | pkg-config 模块 2.28.5（`-D__SWITCH__ -march=armv8-a+crc+crypto ...`） | configure 输出 |

统一调用模板（宿主 bash / PowerShell 均可用）：

```
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '<命令>'
```

## 4. 上游事实与构建入口

### 4.1 仓库与版本

- 上游：`https://github.com/krkrsdl2/krkrsdl2`（默认分支 `main`）
- 锁定 commit：`124bdf841f09e7ce02aa99b7b55791a0f7a900ff`（commit date 2026-09-30T22:11:23-05:00 = 2026-10-01T03:11:23Z，subject: cleanup: 0/nullptr/NULL comparison and control flow cleanups）
- 许可证：MIT（`LICENSE` 1,063 B，Copyright (C) Kirikiri SDL2 Developers）；README 声明 src 目录 MIT、含第三方组件（非 GPL）。
- 上游 README **不宣传** Switch 支持，但 CMake 与 CI 有完整 `NINTENDO_SWITCH` 目标（见 4.2/4.3）。

### 4.2 上游 CI 的 switch job（`.github/workflows/ci.yml`）

- matrix target：`switch`；`container: devkitpro/devkita64:20241023`；全局 `env: CMAKE_GENERATOR=Ninja`；`artifact-path: build/*.nro`；超时 20 min；
- 追加 configure 参数（`cmake-extra-configure-append`）：`-DCMAKE_TOOLCHAIN_FILE=${DEVKITPRO}/cmake/Switch.cmake -DEMBED_DATA_PATH=data.xp3`；
- 步骤：安装 `p7zip-full cmake make ninja-build git curl` → checkout（submodules recursive）→ 下载示例工程（`EXAMPLE_PROJECT_URL` = `https://github.com/krkrsdl2/krkrsdl2-kag3-demo/releases/download/latest/data.xp3`，落到仓库根）→ `cmake -S . -B build ... -DCMAKE_BUILD_TYPE=Release` → `cmake --build build`；
- `create-release` job 只在 `refs/heads/main` 上把 `build/*.nro` 附到 tag `latest` 的预发布（title「Latest development builds」）。

### 4.3 产物规则（根 `CMakeLists.txt`，769 行）

- L132 `if(NINTENDO_SWITCH)`：`SWITCH_APP_NAME "Kirikiri SDL2"`、`SWITCH_AUTHOR "uyjulian"`、`SWITCH_VERSION "v2.0.0"`、`SWITCH_RESOURCES_ROOT src/resources/nswitch`；`EMBED_DATA_PATH` 默认 `${CMAKE_CURRENT_SOURCE_DIR}/data`；
- `L538 elseif(NINTENDO_SWITCH)`：`pkg_check_modules(SDL2 REQUIRED IMPORTED_TARGET sdl2)` → **Switch 分支不编译 `external/SDL` 子模块**（仅 iOS/Linux/Android/Win32/Vita 分支 add_subdirectory）；
- `L554-567`：`add_subdirectory(external/FAudio)` + `TVP_FAUDIO_IMPLEMENT` → **FAudio 子模块必需**；
- `L725-748`：`add_custom_target(krkrsdl2.nacp)` 调 `nacptool --create ...`；`add_custom_target(romfs ALL)` = `cmake -E create_symlink ${EMBED_DATA_PATH} .../romfs/<basename>`；`add_custom_target(krkrsdl2.nro ALL)` = `elf2nro ... --icon=${SWITCH_RESOURCES_ROOT}/icon.jpg --nacp=krkrsdl2.nacp --romfsdir=...`；
- `L85-91`：PCH 开关逻辑 —— 只有 `KRKRSDL2_ENABLE_PRECOMPILED_HEADERS` 显式 OFF 或 `WIN32` 为真才关；`CMAKE_SYSTEM_NAME=NintendoSwitch` 时 `WIN32` 为假 → **PCH 强制 ON**（对应坑 3）。

### 4.4 子模块（实测 pinned）

| 子模块 | commit | 说明 |
| --- | --- | --- |
| `external/krkrz` | `b11c43a07543756fcb943a60ff0a949a7f470f10` | KiriKiri Z 本体（必需） |
| `external/FAudio` | `e787ed76558db49927e2cce6f08735b93870bb16` | Switch 音频后端（必需） |
| `external/simde` | `dd0b662fd8cf4b1617dbbb4d08aa053e512b08e4` | SIMD 兼容层（必需） |
| `external/zlib` | `cacf7f1d4e3d44d871b605da3b647f07d718623f` | 必需 |
| `external/meson_toolchains` | `10c83e8aee101382925d29e14bb8b8c683afd71b` | 仅 meson 路线使用（本构建未用，但已初始化） |
| `external/SDL` | 未初始化（`-53dea98...`） | **Switch 分支不需要**（pkg-config 用 portlibs 的 SDL2） |

`external/krkrz` 的递归子模块：`angle f82b1b4d`、`baseclasses c9eb6589`、`freetype 09d51432`、`glm 5dcc5648`、`jxrlib 392d1c39`、`libjpeg-turbo 70e1c3ce`、`libogg 17c16b0d`、`lpng 5ed2d0a1`、`onig 2175d162`、`opus 4f7980cc`、`opusfile f1448619`、`zlib 7b1a58fd`。

## 5. 源码检出

```
cd /e/galnx-build
git clone https://github.com/krkrsdl2/krkrsdl2.git m1-krkrsdl2
cd m1-krkrsdl2
git checkout 124bdf841f09e7ce02aa99b7b55791a0f7a900ff
git submodule update --init external/FAudio external/krkrz external/meson_toolchains external/simde external/zlib
git -C external/krkrz submodule update --init --recursive
```

实测结果：仓库 214 MB（含子模块），`external/SDL` 保持未初始化（`git submodule status` 前缀 `-`）。

## 6. 构建步骤与命令（最终可用流程）

### 6.0 前置

- devkitPro 已安装于 `D:/devkitPro`（含 devkitA64、libnx、switch-tools、switch-cmake、switch-pkg-config、portlibs/switch 的 SDL2）；
- MSYS2 内需要 `cmake`（4.0.2）与 `ninja`（1.13.2）——**不能**用宿主原生 cmake（见坑 1）；
- 构建根目录不得含空格：`E:/galnx-build/m1-krkrsdl2/build5`。

### 6.1 配置（MSYS2 cmake + devkitPro Switch.cmake + Ninja）

```
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '
  export DEVKITPRO=/opt/devkitpro DEVKITA64=/opt/devkitpro/devkitA64
  export PATH=/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin:/opt/devkitpro/portlibs/switch/bin:\$PATH
  cd /e/galnx-build/m1-krkrsdl2
  cmake -S . -B build5 -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=/opt/devkitpro/cmake/Switch.cmake \
    -DEMBED_DATA_PATH=/e/galnx-build/m1-content/data-withfont.xp3 \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON \
    -DCMAKE_C_FLAGS=-Wno-implicit-function-declaration
'
```

说明：`-march/-mtune/-mtp/-ftls-model/-D__SWITCH__` 等由 devkitPro 的 `Platform/NintendoSwitch.cmake` 自动注入，无需手写；`-Wno-implicit-function-declaration` 用于 jxrlib 的 `wcslen` 隐式声明（gcc 16 默认报错，见坑 3 附注）；`-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON` 见坑 3。
实际 configure 结果：`CONFIGURE_EXIT=0`，耗时约 12.0 s（首次）+ 0.5 s（reconfigure），GNU 16.1.0，pkg-config 2.4.3，`Found sdl2, version 2.28.5`。

### 6.2 打 Ninja 归档规则补丁（绕 Windows 命令行上限，见坑 4/坑 5）

```
RULES=build5/CMakeFiles/rules.ninja
if grep -q 'rspfile = ' "$RULES"; then echo ALREADY_PATCHED; else
  awk 'BEGIN{inrule=0}
    /^rule CXX_STATIC_LIBRARY_LINKER__krkrsdl2common_Release$/ {inrule=1}
    { if (inrule && /^  command = /) { gsub(/gcc-ar\.exe qc \$TARGET_FILE \$LINK_FLAGS \$in/, "gcc-ar.exe qc $TARGET_FILE $LINK_FLAGS @$TARGET_FILE.rsp") } }
    { if (inrule && /^  restat = /) { print; print "  rspfile = $TARGET_FILE.rsp"; print "  rspfile_content = $in"; inrule=0; next } }
    { print }' "$RULES" > "$RULES.new" && mv "$RULES.new" "$RULES"
fi
```

补丁只改**构建目录内**生成的规则文件（`rules.ninja` 4056 B → 4123 B），不触碰上游源码。**每次 reconfigure 后必须重打**（坑 5）。

### 6.3 构建

```
/usr/bin/ninja -C build5 -j 16     # 首次全量：408 个编译单元 + 5 个收尾步骤
```

首轮全量编译在 Lead 的 build5 后台 ninja 中完成（`[406/408]` 时归档失败）；补丁后本次只需 5 步：

```
[1/5] /bin/sh CMakeFiles/krkrsdl2.nacp-5d39927.sh 12aadbbd78c3de49
[2/5] /bin/sh CMakeFiles/romfs-e4b6dfd.sh b9b7ea7b1dcf72c5
[3/5] Linking CXX static library libkrkrsdl2common.a
[4/5] Linking CXX executable krkrsdl2.elf
[5/5] /bin/sh CMakeFiles/krkrsdl2.nro-5524402.sh 1eae39f9365f3fd3
Visiting directories...
Calculating metadata...
Writing E:/galnx-build/m1-krkrsdl2/build5/romfs/data-withfont.xp3 to RomFS image...
NINJA_EXIT=0
```

### 6.4 校验

```
ls -l build5/krkrsdl2.nro build5/krkrsdl2.elf build5/krkrsdl2.nacp
sha256sum build5/krkrsdl2.nro build5/krkrsdl2.elf build5/krkrsdl2.nacp
xxd -s 0x10 -l 4 build5/krkrsdl2.nro      # 期望 4e524f30 = NRO0
```

实测 NRO 头：`bytes[0x00..0x04]=20000014`、`bytes[0x10..0x14]='NRO0'`；NRO 内可见 NACP 标题字符串 `Kirikiri SDL2` 与作者 `uyjulian`。

## 7. 日志摘要

| 日志 | 关键内容 | 结果 |
| --- | --- | --- |
| 01-configure.log | 首次 configure，EMBED_DATA_PATH 指向 65 B 空 XP3 存根 | exit 0 |
| 02-configure-realdata.log | 换 4,764,317 B 合法 data.xp3 | exit 0，romfs/data.xp3 = 4,764,317 B |
| 03-build.log | -DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON + Unix Makefiles | ❌ `external/FAudio/CMakeFiles/FAudio.dir/compiler_depend.make:4: *** 多个目标匹配` |
| 04-configure.log / 04-build.log | Unix Makefiles + 关 PCH | configure exit 0；build 到 7% 被工具调用超时中断（非构建错误） |
| 05-build-fix.log | 手动分块归档（494 个 .o，36,843 字符 ⇒ E2BIG） | 手工生成 .a OK，但 ninja 重跑规则会删除重建 → 方案弃用 |
| 06-build-rsp-ninja.log | **rspfile 补丁后首次成功** | ✅ NINJA_EXIT=0，5/5 |
| 07-build-dataxp3.log | 切 data.xp3 后首次构建 | ⚠️ 未清 romfs → NRO 同时含两个数据包（22,671,617 B） |
| 07-build-dataxp3-clean.log | `rm -rf build5/romfs` 后重建 | ✅ 16,042,653 B，仅 data.xp3 |
| 08-final-withfont.log | 切回 withfont + 清 romfs 重建 | ✅ 17,907,245 B，SHA-256 与首次成功一致 |

完整日志在 `Workspace/GalNX/workspaces/m1-krkrsdl2/evidence/`。

## 8. 产物

| 产物 | 大小 (B) | SHA-256 | 内嵌数据 |
| --- | --- | --- | --- |
| `out/krkrsdl2-realdata.nro`（= `krkrsdl2-withfont.nro`） | 17,907,245 | `e324c2d08b0a2d468b7bf9c2112d5fa699430875a6ffa187961b32ce3d32fffe` | data-withfont.xp3 6,628,897 B |
| `out/krkrsdl2-dataxp3.nro` | 16,042,653 | `d691471bd40673837148d22c8a4466bc98d6b5ad905414792b9e735d001a3d67` | data.xp3 4,764,317 B |
| `build5/krkrsdl2.elf` | 58,374,744 | `59a1afd3aca90de5f9d8cb6a470a0f091bb9d607ed8d713c430476dea87228a8` | — |
| `build5/krkrsdl2.nacp` | 16,384 | `776f5b44a1b5c16d71988f306c77cbeae138dde864d748d0cbcd49a0d14e37bd` | — |
| `build5/libkrkrsdl2common.a` | 107,067,190 | `e7c6d57e1c6ab1dbf877bf05ecbc6a1857c8d81de6274a92727598a171108541` | — |

产物位置：`E:/galnx-build/m1-krkrsdl2/out/`（不提交仓库；NRO 可随时按第 6 节重建）。

## 9. Windows 宿主机构建坑与绕法（可复用资产）

| # | 现象（精确报错） | 根因 | 绕法 |
| --- | --- | --- | --- |
| 坑 1 | 原生 cmake 直接 FATAL：`CMake must be installed and launched from msys2: pacman -S cmake`；MSYS cmake 用 `DEVKITPRO=D:/devkitPro` 时找不到 `/e/.../D:/devkitPro/cmake/Switch.cmake` | `dkp-initialize-path.cmake` 在 `CMAKE_HOST_WIN32` 时 FATAL；POSIX cmake 把 `D:/` 当相对路径 | 只用 **MSYS2 的 POSIX cmake**，并把 `DEVKITPRO=/opt/devkitpro`（fstab 已映射） |
| 坑 2 | GNU make：`external/FAudio/CMakeFiles/FAudio.dir/compiler_depend.make:4: *** 多个目标匹配。 停止。` | 原生 Windows gcc 在依赖文件写 `D:/devkitPro/...` 带盘符冒号，POSIX make 把 `D:` 当目标分隔符 | 改用 **Ninja 生成器**（不解析 make depfile） |
| 坑 3 | `fatal error: /e/galnx-build/m1-krkrsdl2/src/core/sdl2/SDLPrecompiledHeader.h: No such file or directory` | CMake PCH 的 `cmake_pch.hxx` 内嵌 POSIX 绝对路径；原生 aarch64 gcc 不翻译文件内容 | `-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON`（CMake ≥3.16 全局变量；上游 CMakeLists 无此开关） |
| 坑 3b | `error: implicit declaration of function 'wcslen' [-Wimplicit-function-declaration]`（jxrlib `JXRGlueJxr.c:66`） | devkitA64 gcc 16.1.0 对 C 隐式声明默认报错；CI 容器 20241023 的 gcc 不报 | `-DCMAKE_C_FLAGS=-Wno-implicit-function-declaration` |
| 坑 4 | `/bin/sh: 行 1: ...gcc-ar.exe: Argument list too long`（退出码 126） | `krkrsdl2common` 494 个 .o，相对路径合计 **36,843 字符** > Windows CreateProcess 32,767 上限 | patch 归档规则用 `rspfile`/`rspfile_content`（gcc-ar 支持 `@file` response file，已实测） |
| 坑 5 | reconfigure 后归档再次 `Argument list too long` | `cmake` reconfigure 重新生成 `CMakeFiles/rules.ninja`，覆盖 rspfile 补丁 | 每次 configure 后**重打补丁**（脚本用 `grep -q 'rspfile = '` 判断，幂等） |
| 坑 6 | 切换 `EMBED_DATA_PATH` 后 NRO 里同时有两个数据包（22,671,617 B） | `romfs` custom target 只建新链接、不清旧文件；`elf2nro` 打包整个 romfs 目录 | 构建前 `rm -rf build5/romfs` |
| 坑 7（提示，非错误） | MSYS cmake 对 `/e/...` 绝对路径执行 `cmake -E create_symlink` 实际产生**真实文件副本**（实测非 symlink） | MSYS2 的 cmake `create_symlink` 实现差异 | 结果正确（`elf2nro` 读到真实数据），但会增加磁盘占用；不要误判成 symlink |

> 经验：这类「Linux CI 能过、Windows 宿主不过」的问题集中在 **路径语义（盘符冒号 / POSIX 绝对路径）** 与 **命令行长度** 两类；把生成器换成 Ninja + 关 PCH + rspfile 归档，可在**不改上游源码**的前提下复现。

## 10. 与上游 CI 的偏差

| 项 | 上游 CI | 本次本地 | 影响 |
| --- | --- | --- | --- |
| 容器/工具链 | `devkitpro/devkita64:20241023` | 本机 devkitPro（devkitA64 r30-1，gcc 16.1.0，libnx 4.12.0-1，switch-sdl2 2.28.5-4） | 编译告警/错误集合略有差异（见坑 3b） |
| 生成器 | Ninja（`CMAKE_GENERATOR=Ninja`） | Ninja 1.13.2（MSYS2） | 一致 |
| PCH | 开启（Linux 路径可用） | **关闭**（`CMAKE_DISABLE_PRECOMPILE_HEADERS=ON`） | 仅影响编译速度，不影响产物语义 |
| 归档规则 | 默认（Linux 无命令行上限） | rspfile 补丁（仅构建目录内） | 产物内容不变 |
| CFLAGS | CI 未加 | `-Wno-implicit-function-declaration` | 仅抑制 jxrlib 隐式声明报错 |
| 测试数据 | 下载 kag3-demo release 的 `data.xp3`（实测 65 B 空存根，因 CI 未展开子模块） | Lead 打的**真实 KAG3 demo**：data.xp3 4,764,317 B / data-withfont.xp3 6,628,897 B | 本地产物比 CI artifact 更有内容验证价值 |
| EMBED_DATA_PATH | 相对路径 `data.xp3` | 绝对 POSIX 路径 `/e/galnx-build/m1-content/...` | 规避相对 symlink 问题（坑 7 相关） |

## 11. 测试数据来源与合法性

| 数据包 | 大小 (B) | SHA-256 | 来源 |
| --- | --- | --- | --- |
| `data.xp3` | 4,764,317 | `c12ba272b7757aa08dffca11b58f4159d36434f635c5b04b23d3f6c284a08c55` | krkrsdl2-kag3-demo 的 `external/kag3@b21b16ea` + `data-demo/`，用 krkrrel-ng（release `latest` 的 `krkrrel-win32.zip`）打包；XP3 magic 校验通过 |
| `data-withfont.xp3` | 6,628,897 | `56538c91a515c9c592300d2a44ae2e1fca0c33c874a64f9e8aff3544dcce09c6` | 在上者基础上替换字体（Lead 制作，供 M1-d 字体测试） |

- **许可依据**：`krkrsdl2/kag3` 的 README 原文「# KAG3 License / Copyright (C)2001-2009, W.Dee and contributors 改変・配布は自由です」（修改与分发自由；**非 OSI SPDX 许可**，属自定义条款）。
- demo 工程 README（krkrsdl2-kag3-demo）原文：「デモンストレーションプロジェクトのライセンスはKAG3と同じ」→ 示例工程许可随 KAG3。
- demo 内字体为「梅ゴシックO5」（Ume Gothic O5），其再分发条款需单独核实；data-withfont 包里的替代字体许可同样需用户复核。
- **未使用任何商业游戏数据**；不读取、不打包模拟器密钥/固件。

## 12. 未验证 / 已知限制

1. **本记录产物未打模拟器兼容补丁**：直接运行时 guest 在创建窗口前退出（原因是 4 处 Switch 路径/命令行缺陷，见 `004`）；打补丁后的干净重建版已在 Citron 验证出画面，本记录的两条 NRO 仅作构建产物留档。
2. **字体**：KAG3 demo 默认引用系统字体（MS PMincho/MS Gothic），Switch 无系统字体；`data-withfont.xp3` 内嵌 `system_polyfill/font.ttf`（IPAexGothic）后，Citron 实测日文字形正常（见 003/004）。
3. **单游戏内嵌形态**：`EMBED_DATA_PATH` 决定 RomFS 内容；本产物只能跑一个游戏，多游戏启动器需另做（krkr-ns fork 已有产品化启动器）。
4. **未打 NSP**：只产出 NRO；NSP 需 `build_pfs0` + Title ID + NACP 调整，未在本任务范围内。
5. **可复现性范围**：仅验证「同机、同工具链、同数据」下内容级可复现（两次构建 SHA-256 相同）；跨机器/跨容器未验证。
6. **上游 CI 数据资产缺陷**：`kag3-demo` release 的 `data.xp3` 是 65 B 空存根（子模块未展开），不能作为内容验证基准——此发现应回写上游 issue（未做）。
7. **KAG/VFS 行为**：Citron 已实测到 KAG3 demo 标题画面（004）；标题页之后的剧情推进、视频/音频/转场仍未验证（缺输入注入）。

## 13. 证据清单

`Workspace/GalNX/workspaces/m1-krkrsdl2/evidence/`：

- 成功路径：`06-ninja-rsp.sh`、`06-build-rsp-ninja.log`、`06-rules.ninja.orig`、`06-rules.ninja.patched`、`08-final-withfont.sh`、`08-final-withfont.log`、`07-artifact-hashes.txt`；
- 数据包变体：`07-build-variant.sh`、`07-build-dataxp3.log`、`07-build-dataxp3-clean.log`；
- 失败历史：`01-configure.log`、`02-configure-realdata.log`、`03-build.log`、`04-configure.log`、`04-build.log`、`05-fix-archive-and-build.sh`、`05-build-fix.log`；
- 归档说明：`README.md`。

## 14. 复现清单（可复制）

1. 装 devkitPro（devkitA64 + libnx + switch-tools + switch-cmake + switch-pkg-config + switch-sdl2）；确认 MSYS2 有 `cmake` 与 `ninja`；
2. `git clone` + `git checkout 124bdf84` + 初始化第 4.4 节列出的子模块（`external/SDL` 可跳过）；
3. 准备合法数据包（KAG3 demo），记录其 SHA-256；
4. 按第 6.1 节 configure（`-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON` + `-DCMAKE_C_FLAGS=-Wno-implicit-function-declaration`，`-G Ninja`）；
5. 按第 6.2 节重打 `rules.ninja` rspfile 补丁；
6. `rm -rf build5/romfs`（切换数据包时必做）→ `/usr/bin/ninja -C build5 -j 16`；
7. 校验 `build5/krkrsdl2.nro` 大小/SHA-256/`NRO0` 魔数；与第 8 节表对照。

预期（同环境同数据）：产物 A 17,907,245 B / `e324c2d0...`；产物 B 16,042,653 B / `d691471b...`。
