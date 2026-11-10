# K2NX 自包含 NSP 构建链与引擎描述符（P3-c）

| 项 | 值 |
| --- | --- |
| 文号 | docs/builds/009-k2nx-selfcontained-build.md |
| 任务 | task-42（P3-c：引擎描述符与源码准备工具） |
| 执行 | audit-engines |
| 日期 | 2026-10-30 |
| 状态 | 本次实现完成：schema/descriptor/contract/source.py/描述符/测试 + k2nx-src check-only 验收通过（含真 CLI 路径）；cli.py 已由 Lead 接线（cli.py:13 import、cli.py:701 register） |
| 关联 | docs/builds/patches/k2nx-switch/README.md、docs/pilot/P1-engine-k2nx.md、docs/pilot/P2-acceptance.md、docs/builds/001-krkrsdl2-upstream.md |

## 1. 目的与范围

本文件把 P1/P2 阶段人工跑通的 Kirikiroid2-NX（下称 K2NX）构建链，固化为「可机读的引擎描述符 + 可重复的源码准备工具」，并记录完整构建链的事实与 Windows 侧踩坑，供 CI/后续人工复现。

范围：

- 上游：https://github.com/Erige005/Kirikiroid2-NX ，pin commit e96b6034c292c6ccdb099823ab6a0a6b505f77f3（tag v1.0.1，2026-10-18T17:27:29Z）。
- 本机实测环境：Windows 10.0.26100 + devkitPro（D:/devkitPro）+ MSYS2 + Git for Windows 2.55.0.windows.4。
- 只记录「构建出 ELF/NRO」与「ELF→自包含 NSP」的事实；不含任何密钥内容（NSP 打包的 keyset 必须由用户显式提供，禁止入库/入 CI）。
- 本次未修改 src/galnx/cli.py（Lead 独占）；prepare 子命令的 argparse 注册由本模块 register() 提供，Lead 已在 cli.py 完成接线（cli.py:13 from .engines import source as engines_source、cli.py:701 engines_source.register(engines_sub)）。

## 2. 源码 pin 与三条补丁

上游仓库/commit/tag：

| 项 | 值 |
| --- | --- |
| upstream_url | https://github.com/Erige005/Kirikiroid2-NX |
| pinned_commit | e96b6034c292c6ccdb099823ab6a0a6b505f77f3 |
| pinned_version | v1.0.1（2026-10-18T17:27:29Z） |
| license_spdx | NOASSERTION（LICENSE 为 KiriKiri BSD-style 非 SPDX 文本；THIRD_PARTY_LICENSES.md 另列 FFmpeg LGPL-2.1、OpenCV BSD-3、cocos2d-x MIT、UnRAR 限制等，详见 P1 §1.2） |
| build_backend | cmake-switch |
| target_kind | self_contained_nsp |

补丁从 P1 的合并 diff 拆为三条独立 git 补丁，落盘 docs/builds/patches/k2nx-switch/：

| 补丁 | 目标文件 | 变更 | 字节 | sha256 | 作用 |
| --- | --- | --- | --- | --- | --- |
| A-autostart.patch | src/core/environ/switch/SwitchUtils.cpp | +45 | 2,698 | e6a07534b51be5b996af9098df273fd8062404e9a4622239d55a26ebd859e2f2 | TVPCheckStartupArg 改为读 sdmc:/switch/kirikiroid2/autostart.txt 并 startupFrom()，实现开机直进游戏 |
| B-extract-v2.patch | src/core/environ/switch/main.cpp | +270 | 11,196 | bafa71effedd2d6d52bd896a3676a2c25332256f5e19969108cd0185c98f7b5e | romfsInit 后调用 GalNX_MaybeExtractGame()：按 romfs:/game_files.txt 首启解包 23 个 payload 到 sdmc:/kirikiri（statvfs 空间预检、marker、同大小跳过、目录创建、fflush） |
| C-plugin-alias.patch | src/plugins/InternalPlugins.cpp | +26/-2 | 1,753 | 9806b23f304ffc1fe1371c2a7d4510f00f87d2a3310d52e70781758402b3b186 | TVPLoadPlugin 在内建插件表里对 .tpm 名回退 .dll 名，激活 windowEx 等内建插件 |

权威对照仍是合并 diff：docs/builds/patches/k2nx-switch/k2nx-patched-vs-v1.0.1.diff（16,216 B，sha256 f36cbaa3...），三条补丁必须能还原它。

切分与验证方法（可复现）：

- 不从合并 diff 手切：k2nx-src 的 core.autocrlf=true，worktree 是 CRLF 而索引 blob 是 LF，手切 CRLF hunk 会被 git apply 拒绝。
- 正确做法：git clone --no-hardlinks k2nx-src 到临时目录，checkout e96b6034，把 k2nx-ws/src 下三个已打补丁文件覆盖进去，再 git diff --no-color -- <rel> 生成 LF 规范补丁（diff --git a/<rel> b/<rel> 开头）。
- 验证：三条补丁在 scratch clone 上按 A→B→C 顺序 git apply 均 rc=0，git diff --stat 合计 339 insertions(+), 2 deletions(-)；apply 后归一化（LF）内容与 k2nx-ws 三文件逐字节相等；对 pristine 树每条独立 git apply --check rc=0。

## 3. 工具链前置（本机实测版本）

| 组件 | 版本 | 说明 |
| --- | --- | --- |
| devkitA64 | r30-1 | devkitPro pacman 元包 |
| devkita64-gcc | 16.1.0-1 | GCC15+ 会删 TJS2 空指针检查，上游已用 -fno-delete-null-pointer-checks 规避 |
| devkita64-binutils | 2.46.0-1 | |
| devkita64-newlib | 4.6.0.20260123-4 | |
| libnx | 4.12.0-1 | romfs devoptab、sdmc 自动挂载、audren |
| switch-tools | 1.13.1-1 | elf2nro / nacptool / build_romfs |
| switch-dev + switch-portlibs 组 | - | 必须安装；K2NX 依赖的 libonig/libopenal/libarchive/libglfw3/libzstd/liblz4/libexpat 都在组内 |
| cocos2d-x | 3.11.1 | fetch_cocos.sh：git clone --branch cocos2d-x-3.11.1 + v3-deps-94.zip + 两个 Switch patch |
| p7zip / LZMA SDK | 16.02 / 16.04 | fetch_lzma_sdk.sh，硬依赖宿主 7z 命令 |
| 宿主工具 | bash、make、cmake>=3.21、ninja、git、curl、sed、tar、xz、python3、unzip、7z、patch | MSYS2 提供；MSYS2 侧原缺 unzip/python3/patch/7z，需用 /d/devkitPro/msys2/usr/bin/pacman.exe 补装 |

进入 MSYS2 的固定姿势（Windows 本机）：

~~~
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/<script>.sh'
~~~

注意 devkit-env.sh 只把 /opt/devkitpro/tools/bin 加进 PATH；构建脚本还需手工补 /opt/devkitpro/devkitA64/bin 与 /opt/devkitpro/portlibs/switch/bin（build_k2.sh 内部会处理，外部调 portlibs 脚本时需自己补）。

## 4. 七个自建 portlibs

这七个库不在 devkitPro switch-portlibs 组里，必须用仓库内脚本自建（脚本位于 platforms/switch/tools/portlibs/build_<name>.sh）：

| 库 | 版本/commit | 来源 | 关键处理 | 不能升级的原因 |
| --- | --- | --- | --- | --- |
| GNU libiconv | 1.17 | https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.17.tar.gz | --host=aarch64-none-elf --disable-shared --enable-static --disable-nls；先 make -C libcharset | newlib 无 iconv，引擎编码转换需要 |
| FFmpeg | 3.2.19 | https://ffmpeg.org/releases/ffmpeg-3.2.19.tar.xz | 给 libavcodec/aarch64/{fft_neon.S,imdct15_neon.S} 加 relocate=1（PIE NRO 只读段重定位）；--target-os=none --extra-libs=-lnx；只关 encoder；构建后 sed HAVE_SECTION_DATA_REL_RO=1 | K2 1.3.9 movie 用 FFmpeg 5.0 前 API（AVStream->codec / avcodec_decode_video2），devkitPro 自带 FFmpeg 7.1 不可用 |
| OpenCV | 3.4.20 | https://github.com/opencv/opencv/archive/refs/tags/3.4.20.tar.gz | -DBUILD_LIST=core,imgproc；sed modules/core/src/system.cpp，在 __SWITCH__ 下置 have[CV_CPU_NEON]=true、have[CV_CPU_FP16]=true | 1.3.9 用 OpenCV 3.0/3.1 era API，新版 baseline 检测启动抛异常 |
| UnRAR | 5.6.5 | https://www.rarlab.com/rar/unrarsrc-5.6.5.tar.gz | 条件化 newlib 缺失的 utimensat/UTIME_NOW；static RARDLL | 1.3.9 同期 import；再分发受 UnRAR 源码许可限制（不得用于重建 RAR 压缩器） |
| libbpg | 0.9.8 | https://bellard.org/bpg/libbpg-0.9.8.tar.gz | decoder only + patches/libbpg_gray_line.c 与头文件声明 | 1.3.9 的 BPG 图片支持 |
| jxrlib | master（未 pin） | https://github.com/4creators/jxrlib/archive/refs/heads/master.tar.gz | -D__ANSI__ -DDISABLE_PERF_MEASUREMENT -D_byteswap_ulong=__builtin_bswap32；产物 libjpegxr/libjxrglue | JPEG XR 支持；master 不固定是可重复性风险（P1 R9），建议 CI 锁 sha256 |
| Blend2D | d2027ebfd6aaf53b190b6b3b497425fc85f14251 | build_blend2d.sh 内 clone + checkout | 为 __SWITCH__ 启用 Apple 分支（newlib 64-bit off_t、无 *64 file API） | krkr2 的 LayerExDraw 用 camelCase API（对应 vcpkg baseline 2025-03-08 commit） |

七个库都静态链接进 NRO（K2NX 体积约 42 MB）。LGPL 类（FFmpeg、libiconv）再分发需提供 relink 手段，THIRD_PARTY_LICENSES.md 已声明。

## 5. 构建命令序

K2NX 脚本假定固定布局：仓库必须在 $K2NX_WS/src（fetch_cocos.sh 把 cocos 放 $K2NX_WS/src/vendor/cocos2d-x，源码缓存 $K2NX_WS/.cache/src）。完整顺序：

~~~
export K2NX_WS=/path/to/workspace          # 该目录下 src/ 就是 K2NX 仓库
export K2S_PORTLIBS=$HOME/k2s-portlibs     # 可选；默认值见 portlibs/env.sh

# 1) 工具链（本机已装可跳过；脚本需要 root/apt）
bash platforms/switch/tools/setup_wsl_devkitpro.sh

# 2) cocos2d-x 3.11.1 + Switch patch
bash platforms/switch/tools/fetch_cocos.sh

# 3) p7zip / LZMA SDK（需要宿主 7z）
bash platforms/switch/tools/fetch_lzma_sdk.sh

# 4) 七个自建 portlibs（顺序无关）
for s in libiconv ffmpeg opencv unrar libbpg jxrlib blend2d; do
  bash platforms/switch/tools/portlibs/build_$s.sh
done

# 5) 从 Kirikiroid2 1.3.9 APK 提取 UI 资源到 $K2NX_WS/build/romfs 与 build/icon.jpg
bash platforms/switch/tools/extract_apk_assets.sh

# 6) 构建 NRO（TGT=all，CFG=Release）
bash platforms/switch/tools/build_k2.sh all Release
~~~

build_k2.sh 内部：source /etc/profile.d/devkit-env.sh；用 /opt/devkitpro/portlibs/switch/bin/aarch64-none-elf-cmake 配置（wrapper 决定交叉工具链），-G Ninja、-DCMAKE_BUILD_TYPE=$CFG、-DCMAKE_POLICY_VERSION_MINIMUM=3.5；构建目录 $HOME/k2s-build/k2-$CFG；ninja -j4 -k 0 $TGT；CMake 变量 K2NX_ASSETS 指向 $K2NX_WS/build。

## 6. Windows / MSYS2 踩坑表（构建链）

| # | 现象 | 根因 | 处理 |
| --- | --- | --- | --- |
| 1 | 配置/构建时找不到交叉工具链、或 cmake 用宿主 gcc | PATH 只含 devkitpro/tools/bin；MSYS2 缺 unzip/python3/patch/7z | 进 MSYS2 bash；PATH 补 /opt/devkitpro/devkitA64/bin 与 /opt/devkitpro/portlibs/switch/bin；用 MSYS2 pacman 补装 |
| 2 | 链接期归档 libcocos2d.a 报 aarch64-none-elf-gcc-ar.exe: Argument list too long（ninja FAILED code=126，日志无 error: 行） | Windows 命令行 32,767 字符上限；494 个 .o 的目标文件列表过长 | build-scripts/ar-chunk.sh（CHUNK=120，首块 qc 后 q，另 ranlib）+ patch_ar_rules.py 改写 CMakeFiles/rules.ninja 里三条 CXX_STATIC_LIBRARY_LINKER__* 规则 |
| 3 | 重新 configure 后链接又超长 | CMake reconfigure 会覆盖 rules.ninja 的补丁 | 每次 reconfigure 后必须重跑 patch_ar_rules.py（run_build_k2.sh 已内置该步骤） |
| 4 | 补丁 git apply 失败 | 从 CRLF 合并 diff 手切 | 用 LF 规范补丁（本仓 A/B/C 三条）或从 autocrlf=true 仓库用 git diff 生成 |
| 5 | 仓库必须在 $K2NX_WS/src | fetch_cocos.sh 等脚本硬编码相对布局 | 按 §5 布局准备 workspace；仓库本身放 src/ 子目录 |
| 6 | fetch_lzma_sdk.sh 直接 exit 2 | 脚本 command -v 7z 硬依赖 | 宿主/MSYS2 安装 7z 后再跑 |

## 7. 产物与哈希（本机实测）

| 产物 | 路径（构建目录外） | 字节 | sha256 |
| --- | --- | --- | --- |
| r2 ELF | E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.elf | 113,874,760 | 4b4515837d0239ee2e7448dd5dbed65e8fdda72c37fb0bac0d0dd10ef849b882 |
| r2 NRO | E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.nro | 42,351,222 | f6134790c56ddb97b6a50b0160f69a0ba3cbf97216c3b15661f86f7ef6bbb7e8 |
| A2 自包含 NSP | E:/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b4.nsp | 2,906,131,672 | eb6c6a15151c2a5936c6549eebb26ca25a059744f0136cb5b8cce773fd9c705f |

NSP 打包链：scripts/build_pilot_nsp.sh（ELF → elf2nso → npdmtool/nacptool/icon → hacBrewPack，romfs 直嵌；TitleID 010047410000B0B4）。框架侧驱动说明见 docs/packaging/nsp-build.md（P3-b），真实 shell 构建证据见 docs/builds/005-nsp-selfcontained.md 与 docs/pilot/P1-nsp-packaging.md。

内容布局：ROMFS 里 UI 资源来自 Kirikiroid2 1.3.9 APK（83 文件约 7.5 MB，P1 实测）；A2 NSP 额外嵌入游戏 payload（首启解包 23 文件 2,737 MiB 到 sdmc:/kirikiri/haruno，实测约 13-14 s）。

## 8. 描述符化与 prepare 工具

### 8.1 schema 扩展（schemas/engine.schema.json）

在保持原有 19 字段兼容（required 不变、additionalProperties:false 不变）的前提下，新增 4 个可选顶层字段：

| 字段 | 结构 | 用途 |
| --- | --- | --- |
| source | {url, commit(40hex), submodules[{path,url,commit}]} | 源码来源与 pin（与 pinned_commit 交叉校验） |
| patches | [{path, notes}] | 源码树补丁清单（path 相对仓库根或描述符目录） |
| portlibs | [{name, version, source_url, recipe, notes}] | 需自建/额外准备的库清单 |
| build | {commands[], env{}, workdir} | 引擎自身构建命令（GalNX 只做规划，不执行） |

### 8.2 描述符层（descriptor.py / contract.py）

- descriptor.py：EngineDescriptor 增加 source/patches/portlibs/build 四字段（默认空）；新增归一化与语义校验（source.commit 必须与 pinned_commit 一致、patches[i].path 非空、build.commands 逐项非空、env 键值均为字符串）；to_dict() 仅在对应 section 非空时输出新键，保证既有 builtin 描述符仍是 19 键（既有测试硬断言）。
- contract.py：新增公开 helper source_spec / patch_specs / portlib_specs / build_spec / descriptor_prepare_errors；plan_build 在存在新字段时追加步骤：source（用 source.url/commit）→ patches（git apply 每条）→ portlibs（bash 配方脚本）→ engine-build（build.commands，GalNX 从不执行，仅规划）。
- 计划步骤对比（实测）：
  - krkrsdl2: manifest, source, patches, prepare-data, configure, compile, artifact, verify（不变）
  - brewser: manifest, fetch, verify-source, content, install, artifact（不变）
  - onscripter-nx: manifest, source, prepare-content, compile, artifact, verify（不变）
  - kirikiroid2-nx: manifest, source, patches, portlibs, engine-build, content, artifact, verify（build.commands 非空 ⇒ 跳过通用 configure/compile）

### 8.3 source 准备工具（src/galnx/engines/source.py）

公共 API：

- verify_pin(repo_dir, commit)：git 校验 HEAD 与 commit 是否存在（实现用 git cat-file -t，见 §9 环境坑），返回 {repo, commit, head, matches, dirty}。
- prepare(source, dest, patches=(), portlibs=(), *, fetch=False, check_only=False, base_dir=None, now=None)：默认离线；dest 必须是 git 仓库；checkout --detach 到 pin；每条补丁先 git apply --check 再 apply；失败逆序回滚（git apply -R + git reset --hard）且不写 lock；成功写 <dest>/.galnx/engine-lock.json。
- register(subparsers)：注册 galnx engines prepare --descriptor <yaml> --dest <dir> [--fetch] [--check-only] [--json]。

lock 文件格式（与项目构建锁 src/galnx/build/lock.py 的 engine-lock.json 同名但用途不同，字段自定义）：

~~~
{
  "schema_version": 1,
  "kind": "engine-source",
  "source": {"url": "...", "commit": "..."},
  "patches": [{"path": "docs/builds/patches/k2nx-switch/A-autostart.patch", "sha256": "...", "notes": "..."}],
  "portlibs": [{"name": "libiconv", "version": "1.17", ...}],
  "prepared_at": "2026-10-30T00:00:00Z"
}
~~~

check-only 语义：只校验 HEAD 与 pin 一致、worktree 干净、每条补丁能对 pinned 树 git apply --check（各补丁独立判断），不写任何文件（不 checkout、不 apply、不写 lock）。

CLI 接入（已由 Lead 完成，见开头状态行）：以下命令已生效（退出码 0 成功 / 1 运行失败 / 2 用法或描述符错误；--json 时 stdout 只有一个 JSON 文档，人类日志走 stderr）：

~~~
python -m galnx engines prepare --descriptor examples/engines/kirikiroid2-nx.yaml \
    --dest /path/to/k2nx-src --check-only --json
python -m galnx engines prepare --descriptor examples/engines/kirikiroid2-nx.yaml \
    --dest /path/to/k2nx-src --fetch
~~~

### 8.4 真实描述符（examples/engines/kirikiroid2-nx.yaml）

包含：19 个既有字段 + source（url/commit）+ 3 条 patches + 7 条 portlibs（含 source_url/recipe/notes）+ build（6 条命令：setup_wsl_devkitpro.sh、fetch_cocos.sh、fetch_lzma_sdk.sh、for 循环 7 个 portlibs、extract_apk_assets.sh、build_k2.sh all Release）。default_input_profile 复用内建 krkr-ns（K2NX 的默认手柄映射需游戏侧 KeyMap，见 P1 §2.13）。

## 9. prepare --check-only 验收（k2nx-src）

对象：E:/galnx-build/pilot-01/k2nx-src，HEAD e96b6034c292c6ccdb099823ab6a0a6b505f77f3，只读（未做任何 checkout/apply）。

验收环境：Git for Windows 2.55.0.windows.4，core.autocrlf=true，git status --porcelain 为空（干净）。

结果（rc=0）：

| 项 | 值 |
| --- | --- |
| status | checked |
| commit / head | e96b6034c292c6ccdb099823ab6a0a6b505f77f3（一致） |
| patches | 3 条，applies 均为 true（A e6a07534... / B bafa71ef... / C 9806b23f...） |
| portlibs | 7 条（libiconv 1.17、ffmpeg 3.2.19、opencv 3.4.20、unrar 5.6.5、libbpg 0.9.8、jxrlib master、blend2d d2027ebfd6aaf53b190b6b3b497425fc85f14251） |
| lock_path | 空（check-only 不写） |
| 副作用 | 无：.galnx 未创建、HEAD 不变、git status 仍为空 |

证据（已入仓）：docs/milestones/evidence/P3c-acceptance-check-only.json（3,695 B，sha256 f0d78888d3f19fe423d1c470c5ddf17208d0950caccfd1815048136c66c4462c）与 P3c-acceptance-check-only.log（594 B）；原始目录 E:/galnx-build/p3c/ 不入库。完整清单见 docs/milestones/evidence/P3c-artifacts-sha256.txt。

真 CLI 路径验收（Lead 接线后，2026-10-30）：用 python -m galnx engines prepare ...（与 §8.3 相同参数；因本仓库未 pip install，需设 PYTHONPATH=src，并把 Git for Windows 2.55 前置到 PATH），rc=0、status=checked、3 条补丁 applies 均 true、portlibs 7 条、lock_path 为空、errors 为空；stderr 人类摘要为 engine prepare checked: e96b6034... (3 patch(es), 7 portlib(s)) 加三行补丁 sha256。证据已入仓：docs/milestones/evidence/P3c-acceptance-cli-check-only.json（与库路径版 JSON 逐字节相同）、P3c-acceptance-cli-check-only.log（506 B）、P3c-accept-cli.py（驱动脚本）。k2nx-src 事后 HEAD 仍 e96b6034、无 .galnx、真 Git for Windows 视角 worktree 干净。

第一次失败记录（环境假阳性，非补丁问题）：PATH 上解析到 devkitPro MSYS2 自带的 git 2.49.0（其 exec-path 为 POSIX，不读 Git for Windows 全局 core.autocrlf=true），把 CRLF worktree 判成 688 个 modified，prepare 返回 rc=1、status=failed，错误原文 source worktree has local changes: M .gitattributes; M .gitignore; ...。换用 Git for Windows 2.55 后同一命令通过。

同环境还发现两个 git 兼容性问题（已在 source.py 规避）：

- git cat-file -e <sha>^{commit} 在该 msys2 git 下 rc=128，报 fatal: Not a valid object name <sha>^commit（大括号被吞）。改用 git cat-file -t <sha> 判类型，rc=0 且输出 commit 即存在。
- 该 git 对 file:///C:/... URI 解析错误（当成 /C:/...，clone 到 /home/...）。测试中 fetch 场景改用普通 Windows 路径克隆。

## 10. 测试与回归

- 新增 tests/test_engines_source.py：24 个用例（TempRepoTest 用本地临时 git 仓库造 pin/补丁），覆盖 verify_pin 正反例、prepare 应用+lock 断言、HEAD 不匹配自动 checkout、冲突回滚、dirty 拒绝、--fetch 本地克隆、check-only 零落地、描述符新 section、k2nx plan 步骤、CLI 注册与退出码（含 prebuilt 描述符 rc=2）。
- 全量回归：python -m pytest tests/ -q 结果 580 passed, 63 subtests passed（44.43s，rc=0），既有引擎/契约/CLI 测试未破坏（krkrsdl2/brewser/onscripter-nx 的 plan step id 与 19 键 to_dict 均不变）。

## 11. 未验证 / 风险

| 编号 | 项 | 说明 |
| --- | --- | --- |
| U1 | 真机未验证 | 整条链只在 Citron 模拟器验证（P2 已直启进正文），真机未测 |
| U2 | NSP 未签名 | Citron 可加载未签名 NSP；真机需 CFW + sigpatches，且属用户自担风险 |
| U3 | prepare 正常模式未对 k2nx-src 实跑 | 只对临时测试仓库做 checkout+apply+lock 验证；k2nx-src 保持 pristine 只读，只跑 --check-only |
| U4 | jxrlib master 未 pin | 构建可重复性风险（P1 R9）；CI 需锁 tar sha256 或缓存 |
| U5 | build.commands 仅规划 | GalNX 契约是只规划不执行；实际构建仍需人工/CI 在 MSYS2 跑 |
| U6 | portlibs 构建需网络 | 七个上游 URL 未做离线缓存策略 |
| U7 | cli.py 接线（已闭合） | Lead 已在 cli.py:13/701 接线，真 CLI 路径见 §9 验收；本次未改 cli.py |
| U8 | 补丁随上游变更 | 若上游更新到 v1.0.1 之后，A/B/C 需按新 HEAD 重新生成并重测 |

## 12. 变更记录

| 日期 | 任务 | 内容 |
| --- | --- | --- |
| 2026-10-30 | task-42（P3-c） | 新建；记录 K2NX 构建链、三补丁、七 portlibs、产物哈希、描述符化与 prepare --check-only 验收 |
| 2026-10-30 | task-42（P3-c） | 补记：cli.py 接线后真 CLI prepare --check-only 验收（rc=0/status=checked），U7 标记闭合 |
| 2026-10-30 | task-42（P3-c） | 验收证据入仓 docs/milestones/evidence/P3c-*（5 文件 + P3c-artifacts-sha256.txt），§9 内证据引用改为仓内路径 |
