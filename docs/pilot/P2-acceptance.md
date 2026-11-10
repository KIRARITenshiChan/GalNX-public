# P2 验收：自包含 NSP + 手柄操作（模拟器级）

> 状态：**P2 完成（Lead 亲自实测，2026-10-30）**。用户完成标准（m04829）在 Citron 模拟器上全部达成，真机（P4）待用户设备。
> 上游文档：`docs/pilot/P1-engine-k2nx.md`（引擎机制/三补丁/未验证项 U1–U20）、`docs/pilot/P1-nsp-packaging.md`（NSP 打包可行性）、`docs/pilot/README.md`（试点总览）。
> 证据分级沿用 `docs/milestones/README.md`：E1 原始日志 / E2 截图 / E3 哈希元数据 / E4 源码片段。

## 1. 用户完成标准逐条判定

用户标准（m04829 原文要点）：在模拟器上「已打包 NSP、可直接启动、支持手柄操作」；达标后才做真机。

| # | 标准 | 判定 | 实测证据（本轮 Lead 跑） |
| --- | --- | --- | --- |
| S1 | **已打包 NSP**（自包含，游戏数据在 NSP 内） | ✅ 通过 | `Kirikiroid2-NX-010047410000b0b4.nsp` 2,906,125,016 B sha256 `eb6c6a15151c2a5936c6549eebb26ca25a059744f0136cb5b8cce773fd9c705f`；romfs 109 文件 / 2,878,186,922 B 内含 23 个 payload（14 xp3 + haruno.cf + 7 tpm + 键位 XML），无外部数据依赖 |
| S2 | **可直接启动**（安装后启动即进游戏，无需文件选择器/手动操作） | ✅ 通过 | 全新 SD（删除 `sdmc:/kirikiri`、marker、autostart）首启：自动解包 23 文件（14.4 s，≈205 MB/s）→ 自动 autostart → 07:40:47 `Scenario loaded : title.ks`；二启：`payload pilot01-r2 already extracted` → 07:51:53 title |
| S3 | **支持手柄操作**（手柄语义可推进剧情/选菜单） | ✅ 通过 | 手柄键序 RIGHT+C → `start.ks` → `@0000A_Z01.ks`（正文首句「懸命に手を伸ばした。」）；C 再推进 → 第二句；60 FPS、0 exception。链路=游戏内 per-game `Kirikiroid2Preference.xml` 把 `VK_PAD*` 映射到 `VK_RETURN`/方向键（E4：`CCKeyCodeConv.cpp:191-216`、`IndividualConfigManager.cpp:49-58`） |
| S4 | **模拟器平台** | ✅ 通过 | Citron Nightly `0237a9b88`（Windows x64 MSVC）、Vulkan、窗口标题 `citron Nightly | 0237a9b88 | Kirikiroid2-NX (64-bit) | 1.0.1 | NVIDIA`、boot 行 `Booting game: 010047410000B0B4` |
| S5 | **真机**（NS1 实机运行） | ⬜ 未验证（按用户要求达标后再做） | 阶段 P4；需要 CFW（Atmosphère + sigpatches）与用户设备 |

补充：S3 的「手柄」在本轮是通过 **Citron 的键盘→虚拟手柄映射**（`input_common` keyboard profile，按键码 39=RIGHT/67=C 等）驱动虚拟手柄按钮，再经游戏内 KeyMap 落到游戏认的键；**物理手柄未接入**（本机无 USB/蓝牙手柄），真机上会重新验证一次物理手柄路径。

## 2. 交付物清单

| 交付物 | 路径（构建机，不入库） | 大小 / sha256 |
| --- | --- | --- |
| **A2 自包含 NSP（可分发形态）** | `E:/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b4.nsp` | 2,906,125,016 B / `eb6c6a15151c2a5936c6549eebb26ca25a059744f0136cb5b8cce773fd9c705f` |
| A2 重建 NRO（调试形态） | `E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.nro` | 42,351,222 B / `f6134790c56ddb97b6a50b0160f69a0ba3cbf97216c3b15661f86f7ef6bbb7e8` |
| A2 重建 ELF（打包输入） | `E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.elf` | 113,874,760 B / `4b4515837d0239ee2e7448dd5dbed65e8fdda72c37fb0bac0d0dd10ef849b882` |
| A1 自包含 NSP（首版，无 keymap） | `E:/galnx-build/pilot-01/out/K2NX-A1-selfcontained-010047410000b0b2.nsp` | 2,906,131,672 B / `9678e992c07bcbe46aa70695957b948badd6f2adaf97e39401060ad196efc3d3` |
| 打包脚本 | `scripts/build_pilot_nsp.sh`（入库） | — |
| 补丁资产 | `docs/builds/patches/k2nx-switch/`（入库，见 §3.2） | — |

A2 = A1 + **keymap 内置**（`Kirikiroid2Preference.xml` 打进 romfs payload）。A1 只能点鼠标进游戏，A2 手柄可直接操作——这是 A1→A2 的唯一功能性差异。

NSP 关键内部构件（A2）：

| 构件 | 大小 | sha256 |
| --- | --- | --- |
| `exefs/main`（elf2nso 产物） | 22,082,152 B | `91d87fc93f89627d65b7627272a3ee8feadf0c024abcc926ba3386e424ee7b7f` |
| `exefs/main.npdm` | 972 B | `f2c020bbcaaeac7c1ca5dd5325f1bf90e1f8e6de2c348b84d0d747d9250f549c` |
| `control/control.nacp` | 16,384 B | `bef3efe17afcc4dbe0fa12b9f1f63d1b5b471bf6d2b2deb391e7313e03fa7838` |
| icon（devkitPro 默认） | 256×256 JPEG | — |
| romfs | 109 文件 / 2,878,186,922 B，最长路径 67 字符 | — |

## 3. 构建与打包链路（可复现）

### 3.1 源码与许可

- 仓库：`Erige005/Kirikiroid2-NX`（KiriKiri2 播放器，zeas2 Kirikiroid2 1.3.9 移植）。
- **pin**：`e96b6034c292c6ccdb099823ab6a0a6b505f77f3`（= tag `v1.0.1`）。
- 许可：仓库 LICENSE 为 KiriKiri 许可（NOASSERTION），**非 OSI 许可** → 作为引擎适配器只做本地构建/验证，不作为可自由分发组件对外发布；分发形态（NSP）只在用户本机，不入库、不上传。
- 构建机工作区：`E:/galnx-build/pilot-01/k2nx-ws/src`（源码）+ `k2nx-ws/build`（CMake 构建树）。

### 3.2 三处源码补丁（相对 v1.0.1，共 3 文件）

补丁包（入库）`docs/builds/patches/k2nx-switch/`：

| 文件 | 作用 |
| --- | --- |
| `k2nx-patched-vs-v1.0.1.diff` | 3 文件合计 diff（16,216 B，sha256 `f36cbaa3…`） |
| `galnx_autostart.inc` / `galnx_extract_v2.inc` | 补丁 A / B 的代码块（供 apply 脚本内联） |
| `apply_k2nx_patches.py` / `apply_plugin_alias_patch.py` / `apply_extract_v2.py` | 可重复应用的打补丁脚本 |
| `keymap/Kirikiroid2Preference.xml` | 游戏内键位映射（1,293 B，sha256 `aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543`） |

三处补丁：

- **补丁 A（autostart，`src/core/environ/switch/SwitchUtils.cpp`）**：`TVPCheckStartupArg()` 优先读 `sdmc:/switch/kirikiroid2/autostart.txt`（单行 TJS 路径，不带媒体前缀）→ `TVPMainScene::GetInstance()->startupFrom(path); return true;`；读不到则回落原生文件选择器。绕过首次启动 Tips/帮助遮罩与选择器。
- **补丁 B（首启解包 v2，`src/core/environ/switch/main.cpp`）**：`romfsInit()` 之后调用 `GalNX_MaybeExtractGame()`：读 `romfs:/game_files.txt`（`version=` / `bytes=` / `target=` / `startup=` / `marker=` / `file=` 行），`statvfs` 空间预检（256 MiB 余量）、`appletSetCpuBoostMode(FastLoad)`、1 MiB 缓冲拷贝、同大小跳过、marker 命中后仍校验 startup 存在；成功写 marker + autostart。v1 的致命 bug（`MkDirs` 把文件路径本身 mkdir → EISDIR）在 v2 拆成 `MkDirs`/`MkParentDirs` 修复。
- **补丁 C（插件别名，`src/plugins/InternalPlugins.cpp`）**：K2NX 的 `TVPLoadPlugin` 在 Switch 上直接 return（外部 `.tpm` 全封死），而内置模块名全是 `*.dll`（NCB_MODULE_NAME），游戏 `plugin/` 里的 `windowEx.tpm` 等永不命中 → 在 `TVPLoadInternalPlugin` 原名失败后以 `.tpm`→`.dll` 别名重试并打印 `[GalNX] internal plugin loaded via .tpm alias: ...`。csvParser/fstat 等因此可用；wumsadp/wuvorbis 无内建模块（解码在核心层，不影响）。

**startup 路径必须是 `/kirikiri/haruno/data.xp3`**（补丁 B 里写死解析：`System.exePath` 取到最后一个分隔符）。

### 3.3 自建 portlibs（devkitPro 官方包不含/版本不符）

K2NX 需要 7 个第三方库；devkitPro 的 `switch-portlibs` 组只有 FFmpeg 7.1（K2NX 用 pre-5.0 API），因此在本机 MSYS2 devkitPro 环境自建（`E:/galnx-build/pilot-01/k2s-portlibs`）：

| 库 | 版本/来源 | 产物 |
| --- | --- | --- |
| libiconv | 1.17 | `libiconv.a` |
| jxrlib | K2NX 内置脚本 | `libjxr.a` |
| UnRAR | 5.6.5 | `libunrar.a` |
| libbpg | 0.9.8 | `libbpg.a` |
| blend2d | `d2027ebf` | `libblend2d.a` |
| FFmpeg | **3.2.19**（非 7.x） | `libavcodec/avformat/avutil/swscale/swresample/avfilter.a` |
| OpenCV | 3.4.20（core + imgproc） | `libopencv_core.a` / `libopencv_imgproc.a` |

驱动脚本：`k2nx-ws/build-scripts/run_portlibs.sh` + `run_portlibs2.sh`（断点续跑 libbpg 之后）；日志 `k2nx-ws/build-scripts/logs/portlibs*.log`。同时用 pacman 装了 `switch-portlibs` 组里的 glfw/onig/openal/libarchive/expat/lz4/zstd。

### 3.4 构建命令（Windows + MSYS2 devkitPro）

宿主机限制：devkitPro 的 MSYS2 树在 `D:/devkitPro`，只能用其自带 bash 调用（`git-bash` 里没有 `/opt/devkitpro`）：

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/pilot-01/k2nx-ws/build-scripts/run_build_k2.sh all Release'
```

`run_build_k2.sh` 的关键内容（环境变量 + 两处 Windows 坑的规避）：

```bash
export PATH=/opt/devkitpro/devkitA64/bin:/opt/devkitpro/portlibs/switch/bin:/opt/devkitpro/tools/bin:/usr/bin:/bin
export DEVKITPRO=/opt/devkitpro
export K2S_PORTLIBS=/e/galnx-build/pilot-01/k2s-portlibs
export PKG_CONFIG_LIBDIR=$K2S_PORTLIBS/lib/pkgconfig:/opt/devkitpro/portlibs/switch/lib/pkgconfig:/opt/devkitpro/libnx/lib/pkgconfig
export PKG_CONFIG_EXECUTABLE=/opt/devkitpro/portlibs/switch/bin/aarch64-none-elf-pkg-config

/opt/devkitpro/portlibs/switch/bin/aarch64-none-elf-cmake \
  -S $K2NX_WS/src/platforms/switch -B $B -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DK2S_PORTLIBS=$K2S_PORTLIBS -DPKG_CONFIG_EXECUTABLE=$PKG_CONFIG_EXECUTABLE

# 坑：Windows argv 长度上限，libcocos2d.a（~800 对象）-> "Argument list too long"
sed -i 's#aarch64-none-elf-gcc-ar.exe qc#bash .../ar-chunk.sh qc#' $B/CMakeFiles/rules.ninja
/usr/bin/ninja -j10 -k 0 -C $B all
```

两个 Windows 专属坑（首次构建 830/835 失败的真因）：

1. **ar 归档 argv 过长**：`libcocos2d.a` 归档约 800 个目标文件，Windows 命令行长度上限直接 `Argument list too long`；ninja 日志里**没有 `error:` 字样**，必须 `grep '^FAILED'` 才能发现。规避：`build-scripts/ar-chunk.sh`（每批 120 个文件调 `gcc-ar qc/q`）+ 改写 `build/CMakeFiles/rules.ninja`。
2. **reconfigure 会覆盖 rules.ninja 补丁** → 每次重新 configure 后必须重跑 `patch_ar_rules.py`/`sed`，否则再次 E2BIG。

产物：`build/cmake-Release/kirikiroid2.nro`、`kirikiroid2.elf`、`kirikiroid2.nacp`。

### 3.5 A2 NSP 打包

```bash
bash scripts/build_pilot_nsp.sh \
  --elf /e/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.elf \
  --romfs-dir /e/galnx-build/pilot-01/nsp/romfs-a2 \
  --title-id 010047410000b0b4 --name 'Kirikiroid2-NX' \
  --author 'GalNX pilot' --version '1.0.1' \
  --keyset '/e/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys' \
  --out /e/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b4.nsp \
  --work /e/galnx-build/pilot-01/build/k2nx-a2
```

链路：ELF → `elf2nso` → `exefs/main`；npdm 由 `examples/nsp/npdm.json` 生成（title_id 0x010047410000b0b4）；`nacptool` 生成 control.nacp；romfs 直接内嵌（2.88 GB，hacBrewPack 峰值内存 111 MiB、耗时 95.2 s）；最后 `nstool` 校验 NSP/NCA（exit 0，`ACID Signature: FAIL` 属未签名 homebrew 预期）。

- keyset 策略：**只允许显式 `--keyset` 传真实 `prod.keys`**（12,007 B sha256 `7bb3b6d2…`），不通过环境变量、不写日志、不入库；PROVENANCE 只记录 size/sha256/mtime。最小键集实测：即使 `--plaintext` 也强制需要 header_key(32B) + key_area_key_application_00(16B)。
- 路径长度：Windows 260 字符上限 → 打包脚本对 romfs 内路径做检查（实测最长 67 字符，安全）。

### 3.6 romfs 结构（A2）

`romfs/` = 85 个引擎 UI 资源（来自 `platforms/switch/romfs`）+ 23 个 payload + `game_files.txt`：

```
romfs:/game/                     # payload（首启解包到 sdmc:/kirikiri/haruno/）
  data.xp3 haruno.cf image00..06.xp3 media.xp3 movie.xp3
  scenario.xp3 voice01.xp3 voice01_2.xp3 voice02.xp3 voice02_2.xp3
  Kirikiroid2Preference.xml      # 键位映射（A2 新增）
  plugin/{csvParser,extrans,fstat,layerExImage,windowEx,wumsadp,wuvorbis}.tpm
romfs:/game_files.txt            # version=pilot01-r2 / target=/kirikiri/haruno /
                                 # startup=/kirikiri/haruno/data.xp3 /
                                 # marker=sdmc:/switch/kirikiroid2/.galnx_extracted / file=...
```

## 4. 运行验收实测

环境：Citron Nightly `0237a9b88`（Windows x64）、Vulkan、`sd/mc` 根 = `C:/Users/<user>/AppData/Roaming/citron/sdmc`。

### 4.1 全新 SD 首启（S2）

提前断言 Citron 0 实例，删除 `sdmc:/kirikiri`、marker、`autostart.txt`、`k2s_log.txt`，再启动 A2 NSP。`k2s_log.txt` 原文（E1）：

```text
[GALNX] free space check ok: 28196 MiB free for a 2737 MiB payload
[GALNX] first boot: copying 23 payload file(s) to sdmc:/kirikiri/haruno
[GALNX] payload copy finished: 23 copied, 0 kept, 0 failed, 2737 MiB total
[GALNX] autostarting game from /kirikiri/haruno/data.xp3
...
07:40:11 startup.soc / eyecatch / logo
07:40:47 Scenario loaded : title.ks
```

解包耗时 14.4 s（07:39:56.147 → 07:40:10.574），≈205 MB/s。启动到标题 110 s（含解包）。

### 4.2 手柄进入正文（S3）

标题菜单逻辑（游戏 KAG 脚本）：初始 `MapReg=0`，此时 RETURN 无效；`RIGHT` → `MapReg=1`（はじめから），再 `RETURN` 确认。**`LEFT` 会落到 `MapReg=7`（終了する，直接退出游戏）** —— 自动化/真机演示时禁按 LEFT。

| 步骤 | 输入 | 结果 |
| --- | --- | --- |
| 1 | 手柄 RIGHT（Citron 键盘码 39） | 菜单光标从「はじめから」位置生效（MapReg 0→1） |
| 2 | 手柄 A（键盘码 67，经 KeyMap → VK_RETURN） | `07:49:17 Scenario loaded : start.ks` |
| 3 | A 再推进 | `07:49:21 Scenario loaded : @0000A_Z01.ks`（正文首句「懸命に手を伸ばした。」） |

`k2s_log` 全程 0 exception，游戏区 60 FPS（Citron 底部状态栏）。

### 4.3 剧情推进（C 翻页，diff 证据）

- `step-07-started.png` → `step-10-adv1.png` 的像素 diff = 0.0201（画面主体不变，仅文字层变化）——证明输入确实推进了对话而非触发其他界面。
- 无输入时 diff ≈ 0（标题画面静止帧确定性，见 4.4）。

### 4.4 二启 marker（不重复解包）

不删 SD 直接再启 A2：`k2s_log` 出现 `[GALNX] payload pilot01-r2 already extracted, starting game`（无 copying 段），07:51:53 到 title；启动到 title 48 s（vs 首启 110 s）。

**决定性证据**：二启 title 截图 `P2d-secondboot-title.png` 与首启 run3 `P2c-run3-title.png` 的 sha256 **完全相同**（`06f4d1b8ab134399666a871ba304ecd3609fe22bc818dfbc0c01ef7fce83aac3`）→ 渲染确定性 + 首启/二启状态等价。

### 4.5 harness 全流程复跑（可自动化）

`scripts/citron_run.sh` 多步输入模式一次跑完「启动→标题→RIGHT→A→正文→A 推进」，result.json 关键字段：

```json
{"status":"loaded","window_title":"citron Nightly | 0237a9b88 | Kirikiroid2-NX (64-bit) | 1.0.1 | NVIDIA",
 "boot_line":"Booting game: 010047410000B0B4","keys_sent":3,"steps_failed":0,
 "steps_diff_ratio":0.809225,"killed":true,"capture":{"method":"printwindow","nonblack":0.9018}}
```

复跑注意（R14，已在 `docs/environment/citron-harness.md` 记录）：harness 用 `runas /trustlevel:0x20000` 降权启动 Citron，Citron 会脱离调用方进程树；若调用方（如 agent shell）提前回收进程树，会看到「脚本早退但 Citron 仍活着」的假失败。**从已脱离的 shell/后台 job 启动可正常跑满**；run3 = 3.5 min 正常收尾。

## 5. 证据清单（repo：`docs/milestones/evidence/`）

汇总文件 `P2-artifacts-sha256.txt`（sha256 + bytes + 文件名）。

| 文件 | 说明 |
| --- | --- |
| `P2c-run3-result.json` | run3 全流程 result（status=loaded、steps_failed=0） |
| `P2c-run3-title.png` | 标题菜单（手柄 RIGHT 前） |
| `P2c-run3-started.png` | 正文首句（A 确认后） |
| `P2c-run3-adv1.png` | C 推进后第二句 |
| `P2c-run3-window-final.png` | 末帧 |
| `P2c-run3-k2s_log.txt` | 引擎日志（title.ks → start.ks → @0000A_Z01.ks） |
| `P2c-run3-k2s_boot.txt` | 启动段日志 |
| `P2c-run3-keymap.xml` | SD 内键位映射（与 NSP romfs 内同文件同哈希） |
| `P2c-run3-harness-run.log` / `P2c-run3-input-steps.tsv` | harness 原始输出 / 输入步表 |
| `P2d-secondboot-result.json` / `P2d-secondboot-title.png` / `P2d-secondboot-k2s_log.txt` | 二启 marker 验证 |
| `P2a-*` / `P2b-*` | 前序实验（NRO 形态点击进正文、RUN G 手柄进正文） |
| `P2c-live-now.png` 等 | 手动接管 run 的补充截图（`E:/galnx-build/pilot-01/p2-evidence/`） |

关键哈希：run3 k2s_log `17612172f6206da5295275446fdc2227e3a1c85fa5557101471d8278fa8910ba`；二启 k2s_log `b097234b0fa48e1c1a0e4da90a05e310838225b1a746721d65c5a541ad0a4472`；story 首句截图 `243de31c4e92b1e9c2bf5efbc645b30cf86c96b76c8ca0355572f4467a9455e7`；推进后 `6603d6f934289c2398d2ec6a7367284f68abd3c5cac5290042e64a0e952f70db`。

## 6. 已知限制与未验证项

| # | 项 | 状态 | 说明 |
| --- | --- | --- | --- |
| L1 | **真机（NS1）运行** | 未验证 | P4；需要 Atmosphère + sigpatches（未签名 NSP） |
| L2 | 物理手柄 | 未验证 | 本轮手柄语义经 Citron 键盘→虚拟手柄 + 游戏内 KeyMap；真机上直接验证物理手柄 |
| L3 | 中文（xmoe） | 不可用 | xmoe 是 Windows DLL 注入体系（`haruno_chs.exe` + `.xmoe` + `xmoeParser.dll`），Switch 无法移植；当前为**日文原版**可玩 |
| L4 | B/ESC 菜单 | 无可见变化 | 按 B（VK_ESCAPE）截图无差异；游戏菜单可能需长按/组合键，未作结论（U 项） |
| L5 | 存档写读回 | 未验证 | K2NX 存档路径/格式未验证；`savedata/krenvprf.kep` 偏好可读 |
| L6 | 音频 | 未验证 | K2NX 音频后端在 Citron 下是否出声未取证 |
| L7 | 3.4 GB NSP 安装 | 模拟器通过 | Citron 直接 `-g` 加载成功；真机 FAT32 4 GiB 限制/安装耗时待 P4 |
| L8 | 文件选择器 UI | 仍存在（死代码） | autostart 命中后绕过；若 autostart 缺失会回落原生选择器（可接受） |
| L9 | 鼠标注入 | 不稳定 | Citron 下 `mouse_event` 注入坐标漂移/失效（U19）；键盘 PostMessage 稳定 → harness 用键盘通道 |
| L10 | 跨进程截图哈希 | 仅像素级一致 | 同一 Citron 会话内同画面截图逐字节相同（Lead 二启 title = 首启 title，`06f4d1b8…`）；**跨进程/跨 run 即使画面相同，PNG 字节也不同**（CTA 光标动画帧、OSD `Frame: 16.66/16.67 ms` 数字）。⇒ P2 验收判据为像素级（MAD≤0.02、变化像素≤0.05%），不承诺截图 sha256 跨 run 一致（证据与量化见 §7 附录 + `docs/milestones/evidence/P2e-artifacts-sha256.txt`） |

引擎侧未验证项全表见 `docs/pilot/P1-engine-k2nx.md` §8.2（U1–U20）。

## 7. 独立复跑（对抗性验证）

P2 验收采用「Lead 亲自跑 + audit-engines 独立复跑」双轨：独立复跑 checklist = R1 全新 SD 首启、R2 二启 marker、R3 手柄进正文，输入序列与本文 §4.2/4.5 一致，证据写回本文件附录（复跑结果：见文末「附录：独立复跑记录」）。

**执行状态（2026-10-30 08:10 回填）：已完成，结论 PASS。** audit-engines 于 2026-10-29T23:55:16Z–00:01:43Z（本地 07:55–08:01）独立执行 R1（全新 SD 首启）与 R2（二启 marker），run 目录 `20261030-075524-Kirikiroid2-NX-010047410000b0b4` / `20261030-075931-Kirikiroid2-NX-010047410000b0b4`（与 Lead 的 `20261030-074626` / `20261030-075105` 不同，独立驱动脚本）。结果：解包后 SD 23 文件 / 2,870,635,309 B 与 Lead 字节级一致、marker=pilot01-r2、keymap XML sha `aa4fa8aa…`（R2 后不变）、k2s 行数一致且仅时间戳不同、title.ks→start.ks→@0000A_Z01.ks 时序与 C 推进一致；截图与 Lead 的像素差 MAD≤0.0200 / 变化像素≤0.0489%（差异仅在 CTA 动画帧与 OSD Frame 数字，见 L10）。证据：`docs/milestones/evidence/P2e-*`（22 个文件，全量 sha256 见 `P2e-artifacts-sha256.txt`）。Citron 已于 08:01:43 释放（0 实例复查）。

## 8. 下一阶段

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| P3 | 打包工程化：把「源码重建 + 补丁 + payload 生成 + NSP 打包」固化进 GalNX CLI（或脚本参数化），产出可复现 manifest | 待办 |
| P4 | 真机验证：Atmosphère + sigpatches 安装 A2 NSP、首启解包、手柄操作、存档/性能 | 待用户设备 |
| 后续 | 中文（xmoe 等价路线）、存档兼容、音频、多游戏批量 | 待办 |

---

## 附录：独立复跑记录

**复跑者**：audit-engines（与 Lead 独立的 run 目录与驱动脚本；本机 Windows 10.0.26100 x64，Citron Nightly `0237a9b88`）；**被验收物**：A2 NSP `Kirikiroid2-NX-010047410000b0b4.nsp` 2,906,125,016 B sha256 `eb6c6a15151c2a5936c6549eebb26ca25a059744f0136cb5b8cce773fd9c705f`（romfs 内置 keymap XML，全新 SD 无需手工放盘）。**Citron 释放**：08:01:43（本地），复查 0 实例。**证据**：`docs/milestones/evidence/P2e-*`（22 个文件；全量 sha256 与对照见 `P2e-artifacts-sha256.txt`），原始备份 `E:/galnx-build/pilot-01/review/a2-indep/`。

| 轮次 | 时间（本地 / UTC） | 操作 | 结果 | 关键证据 sha256 |
| --- | --- | --- | --- | --- |
| R1-0 | 07:55:15 / 23:55:15Z | pre-wipe 快照：sdmc:/kirikiri 23 文件 2,870,635,309 B、marker `pilot01-r2`、autostart 均存在 → 删除三处 | 删除后 absent（`P2e-r1-prewipe.txt`） | `c7a8e96a…` |
| R1-1 | 07:55:16–07:58:49 / 23:55:16–23:58:49Z | harness 启动 A2 NSP，输入序列与 §4.5/Lead 相同：`wait:120000;capture:title;key:RIGHT;wait:2500;key:C;wait:15000;capture:started;key:C;wait:5000;capture:adv1`（`--timeout 300 --settle 25 --input-delay 3000 --input-gap 250`；32 s 完成、未触超时） | status=loaded、elapsed_s=32、10/10 步 ok、steps_diff_ratio=0.809225；k2s：`free space check ok: 28196 MiB free for a 2737 MiB payload` → `first boot: copying 23 payload file(s)` → `payload copy finished: 23 copied, 0 kept, 0 failed, 2737 MiB total` → `autostarting game from /kirikiri/haruno/data.xp3`；title.ks 07:56:26 → RIGHT+C → start.ks 07:58:13 → @0000A_Z01.ks 07:58:16 | result `bd149a3a…`；k2s `dde7eba6…`；title `5b001042…`；started `d10f50b0…`；adv1 `7d0e9436…` |
| R1-2 | 07:55:35.256–07:55:48.476 | 解包耗时（SD 文件 mtime 窗口，非墙钟） | 13.22 s（≈206 MB/s，Citron 虚拟 SD）；解包后 23 文件、2,870,635,309 B（与 wipe 前字节级一致） | `P2e-r1-sd-after.txt` `9890e003…` |
| R1-3 | 07:58 后 | 落地物检查 | marker 内容 `pilot01-r2`（11 B）；autostart=`/kirikiri/haruno/data.xp3`（26 B）；`Kirikiroid2Preference.xml` 1,293 B sha256 `aa4fa8aa…`（从 payload 解出，未被引擎覆写） | `5109bb58…` / `75b6df80…` / `aa4fa8aa…` |
| R2-1 | 07:59:30–08:01:43 / 23:59:30–00:01:43Z | 不清 SD，二启同一 NSP（`wait:80000;capture:second-title`） | status=loaded、elapsed_s=31、2/2 步 ok；k2s 首行 `[GALNX] payload pilot01-r2 already extracted, starting game` → autostarting → title.ks 08:00:19（launch→title 48 s，无解包段） | result `66c0aa04…`；k2s `5ec17d1d…`；title `884786a6…` |
| R2-2 | 08:01:43 | 收尾复查 | marker/autostart/keymap 三项 sha 全部不变；harness 自动 kill，Citron 0 实例（释放 08:01:43） | `b32a239a…`（poststate） |

**与 Lead 证据的一致项（逐项交叉校验）**

- 解包结果：23 文件 / 2,737 MiB / 0 failed；解包后 SD 23 文件 2,870,635,309 B —— 与 Lead 07:39 解包后**字节级完全一致**。
- k2s 行文一致：R1 133 行 vs Lead run3 133 行，逐行仅时间戳与一处 `(5ms)/(4ms)` 计时差；R2 116 行 vs Lead 二启 116 行，逐行仅时间戳差。
- marker=`pilot01-r2`、autostart=`/kirikiri/haruno/data.xp3`、keymap XML 1,293 B sha `aa4fa8aa…`（R2 后不变）与 Lead 记录相同。
- 时序链路一致：title.ks→（RIGHT+C）→start.ks→@0000A_Z01.ks，C 推进到下一句（E2 目视核对正文）。
- 起跑 SD 状态同源：我的 R1 前 k2s 旧内容 sha256 `b097234b…`（7,143 B）与 Lead 二启 k2s 快照 `b097234b…` 完全相同。

**差异项与判断**

- 截图 sha256 跨进程不同：R1 title `5b001042…` vs Lead `06f4d1b8…`；started `d10f50b0…` vs `243de31c…`；adv1 `7d0e9436…` vs `6603d6f9…`；R2 title `884786a6…` vs Lead 二启 `06f4d1b8…`。
- 像素对照（python3 + Pillow/numpy，整幅 1728x1016）：title MAD 0.0043 / changed(>8) 0.0059% / maxdiff 134；started MAD 0.0200 / 0.0489%（bbox 1404,913–1575,991，858 px）；adv1 MAD 0.0139 / 0.0390%（684 px）；R2 title MAD 0.0046 / 0.0063%。
- 目视裁剪（`P2e-crop-started-diff.png`，左=R1/中=Lead/右=差值）：差异只在**右下角游戏 UI 小图标动画状态**（水滴 vs 水滴框）与 Citron OSD `Frame: 16.66/16.67 ms` 数字；正文与画面主体逐像素一致。
- 判断：**渲染内容一致，P2 验收结论不受影响**；截图 sha256 只保证「同一 Citron 进程内逐字节可复现」（Lead 的「二启=首启同哈希」即此条件），跨进程不成立 → §6 增 L10，后续验收判据改用像素级。

**结论**：R1（全新 SD 首启：解包→autostart→title→手柄 RIGHT+C→start.ks/@0000A_Z01.ks→C 推进）与 R2（二启 marker 命中、无重复解包）均独立复现 **PASS**；与 Lead 证据无实质不一致，无阻塞项。未验证项维持 §6（B/ESC 菜单、存档写读回、真机等）。**方法注记**：R14 早退的规避方式是在单次 run_code 内同步 spawnSync 跑完 harness（DSH 会在 run_code 退出时杀掉其整棵进程树，node spawn(detached) 不足以规避）。
