# 004 — krkrsdl2 Switch 模拟器兼容修复与干净重建（M1-c 收尾）

| 项 | 值 |
| --- | --- |
| 编号 | 004 |
| 对象 | krkrsdl2 上游（commit `124bdf84`）+ GalNX Switch 兼容修复包 |
| 关联任务 | task-13（构建）/ M1-c / M1-d / M1-e |
| 构建时间 | 2026-10-30 01:31–01:33（+08:00） |
| 源码目录 | `E:/galnx-build/m1-krkrsdl2`（上游 baseline `124bdf84`，`external/krkrz` 子模块未改） |
| 构建根 | `E:/galnx-build/m1-krkrsdl2/build5`（Ninja，CMake 4.0.2 + devkitPro `Switch.cmake`） |
| 修复包 | `docs/builds/patches/krkrsdl2-switch-emulator/krkrsdl2-switch-emulator-fixes.patch`（2,869 B，4 文件 +38 行） |
| 结果 | ✅ 构建成功；✅ Citron 运行出画面（KAG3 demo 标题画面，日文/英文渲染正常） |
| 前置记录 | `001-krkrsdl2-upstream.md`（未改源码的首次构建成功）、`003-kag3-demo-content.md`（合法内容包） |

## 1. 目标

M1-c 的首轮构建（001）只证明「能编出 NRO」，在 Citron 上运行时 guest 在创建窗口之前退出。本记录验证：**在不修改测试内容、不降级工具链的前提下，用最小补丁让上游 krkrsdl2 在 Switch 模拟器（Citron）里完整启动并渲染 KAG3 demo**。

## 2. 结论摘要

1. 上游 `124bdf84` 在 Switch 平台层有 4 个真实缺陷，全部集中在「路径 / 命令行」桥接，**不涉及渲染、脚本引擎或 KiriKiri 内核**；GalNX 以 38 行 `#ifdef __SWITCH__` 补丁全部规避。
2. 干净重建产物 `krkrsdl2.nro` **17,911,329 B**，SHA-256 `8124ffd2e8c813de6f1929a16aa69322878c47af5631d089c3809a576d1c52a7`，romfs 内只含 `data.xp3`（6,628,897 B，即 003 的 `data-withfont.xp3` 改名）。
3. Citron nightly `0237a9b88` 运行该 NRO：窗口标题 `citron Nightly | 0237a9b88 | Kirikiri SDL2 (64-bit) | NVIDIA`，截图 940,588 B（非黑占比 0.7159），画面为 KAG3 demo 标题页（青色标题「吉里吉里とKAGの紹介 / Introduction to Kirikiri and KAG」+ 波纹背景），日文字形正常（内嵌 IPAexGothic 生效）。
4. 干净重建的截图与插桩版**逐字节相同**（SHA-256 `0bce597c…`），说明补丁没有改变渲染结果。
5. 早期怀疑的 `nxlinkStdio()` 阻塞**被证伪**：干净构建保留上游 `nxlinkStdio();` 原样，Citron 依然正常出画面。该调用不做修改（真机 `nxlink -s` 依赖它）。
6. 上游官方 release 的预编译 NRO（`krkrsdl2.nro` 12,011,585 B，SHA-256 `a11ec7bef9fc39dc630af731644fbbba85cd08ca53d699976ff39c53b32db23a`）在**同一个 Citron** 上无法出画面（停在 VI `GetManagerDisplayService (STUBBED)` 之后），因此「模拟器兼容性」不能直接用上游产物证明；本次结论只对**本记录产物**成立。

## 3. 失败链与 4 个修复（全部有诊断实证）

调试方法：在 guest 内写 `sdmc:/galnx-diag.txt`（Citron 不转发 guest stdout），逐段插桩定位；插桩版完整 diff 归档于 `docs/milestones/evidence/M1c-krkrsdl2-instrumented.diff`（16,436 B，SHA-256 `58f44a31…`）。

### 3.1 症状 A：启动即抛 `Not supported media type ""`（无窗口）

- 链：Citron 传 `argc == 0` → `krkrsdl2_convert_set_args` 建出长度 0 的 `_wargv` → `ExePath()` 读 `_wargv[0]` 越界得到垃圾串 → `ApplicationSpecialPath::GetDataPathDirectory()` 中 `SDL_GetPrefPath` 返回 NULL → `TVPGetAppPath()` → `TVPNormalizeStorageName(垃圾串)` → media 名为空 → `ThrowUnsupportedMediaType` → `StartApplication` 返回 true，主程序退出。
- 修复 **F1**（`src/core/sdl2/SDLApplication.cpp`）：`__SWITCH__` 下 `argc<=0 || argv==NULL || argv[0]==NULL || argv[0][0]==0` 时回退 `argc=1, argv={"sdmc:/switch/galnx/app.nro"}`。
- 修复 **F2**（`src/core/environ/sdl2/Application.cpp`）：`ExePath()` 在 `__SWITCH__` 下空值回退同一常量路径（防御性，F1 已覆盖主路径）。

### 3.2 症状 B：startup.tjs 找不到（`Cannot find storage`）

- 链：`TVPBeforeSystemInit()` 里 `SDL_GetBasePath()` 在 Switch 返回 **NULL** → 跳过 base 路径探测 → 回退 `getcwd()`（`/`）→ `TVPProjectDir = file://./` → `startup.tjs` 归一化为 `file://./startup.tjs`，auto path 表为空 → `TVPSearchPlacedPath` 抛 `TVPCannotFindStorage`。
- 修复 **F3**（`src/core/base/sdl2/SysInitImpl.cpp`）：`__SWITCH__` 下 `base_path_utf8` 为空时置 `"romfs:/"`；随后正确探测到 `romfs:/data.xp3>`，项目目录 = `file://?/romfs:/data.xp3>`。

### 3.3 症状 C：`data.xp3` 在 romfs 里但存在性检查失败（`media=0`）

- 链：`TVPPreNormalizeStorageName` 在 Switch 把带冒号的原生路径包成 `file://?/romfs:/data.xp3`；`tTVPFileMedia::GetLocallyAccessibleName()` 的非 Windows 分段逻辑把 `?/romfs:/data.xp3` 拼成 `./romfs:/data.xp3` → `stat` 必失败 → `CheckExistentStorage` 返回 false。
- 修复 **F4**（`src/core/base/sdl2/StorageImpl.cpp`）：`GetLocallyAccessibleName` 入口处 `__SWITCH__` 判断，若名以 `?/` 开头则去掉该前缀直接返回原生路径（`romfs:/…` / `sdmc:/…`）。

## 4. 构建与运行命令（可复现）

```bash
# 1) 源码（见 001 §5）检出到 E:/galnx-build/m1-krkrsdl2，baseline 124bdf84；external/krkrz 等子模块按 .gitmodules 拉齐
# 2) 应用修复包（或在干净副本上运行 apply_clean_fixes.py）
cd /e/galnx-build/m1-krkrsdl2 && git apply '…/krkrsdl2-switch-emulator-fixes.patch'
# 3) 构建（在 devkitPro MSYS2 里；build5 已按 001 §6.1 配置，含 Ninja 归档补丁）
cd /e/galnx-build/m1-krkrsdl2/build5 && ninja -j16    # 370 步，exit 0
# 4) 重打包：romfs 只放 data.xp3（文件名必须是 data.xp3，否则 KiriKiri 找不到数据）
rm -rf romfs && mkdir romfs && cp /e/galnx-build/m1-content/data-withfont.xp3 romfs/data.xp3
/opt/devkitpro/tools/bin/elf2nro krkrsdl2.elf krkrsdl2.nro \
  --icon=/e/galnx-build/m1-krkrsdl2/src/resources/nswitch/icon.jpg \
  --nacp=krkrsdl2.nacp --romfsdir=/e/galnx-build/m1-krkrsdl2/build5/romfs
# 5) Citron 运行验证（仓库内脚本）
bash scripts/citron_run.sh --nro /e/galnx-build/m1-krkrsdl2/build5/krkrsdl2.nro \
  --timeout 70 --settle 12 --expect-title 'Kirikiri' --app-log-regex 'Booting game:'
```

注意：`ninja` 自身的 `romfs` 目标会同时写入 `data-withfont.xp3` 与符号链接 `data.xp3`（NRO 会变成 24.5 MB 且文件名不对），**每次构建后必须重打包**。

## 5. 产物（实测）

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `build5/krkrsdl2.nro` | 17,911,329 B | `8124ffd2e8c813de6f1929a16aa69322878c47af5631d089c3809a576d1c52a7` |
| `build5/krkrsdl2.elf` | 58,391,328 B | `74d843cbf1ac633aa83af3f60b6d1049c4367de43c751738d386a913370d6cbe` |
| `build5/krkrsdl2.nacp` | 16,384 B | `776f5b44a1b5c16d71988f306c77cbeae138dde864d748d0cbcd49a0d14e37bd` |
| romfs `data.xp3` | 6,628,897 B | `56538c91a515c9c592300d2a44ae2e1fca0c33c874a64f9e8aff3544dcce09c6`（= 003 `data-withfont.xp3`） |

运行结果（Citron）：`status=loaded`、`title_match=true`、`elapsed_s=19`、截图 `printwindow` 940,588 B / 非黑 0.7159、boot 行 `Booting game: 0000000000000000 | Kirikiri SDL2 (64-bit)`；run 目录 `workspaces/citron-harness/runs/20261030-013339-krkrsdl2`。

## 6. 证据清单

| 证据 | 路径（仓库内） | 大小 | SHA-256 |
| --- | --- | --- | --- |
| 干净构建日志（370 步） | `docs/milestones/evidence/M1c-krkrsdl2-clean-build.log` | — | `7af79bbc5df38fb7e7b860862e10de3d0d0420d8f5abdb410038a4313d1193c8` |
| 干净产物哈希/大小 | `docs/milestones/evidence/M1c-krkrsdl2-clean-artifacts-sha256.txt` | — | `ed40d04c7b5853cf528be9e4a45b173e3d8703ecd666df3ba765d9a04c3bf000` |
| Citron 干净运行截图 | `docs/milestones/evidence/M1c-krkrsdl2-kag3-title-citron-clean.png` | 940,588 B | `0bce597c8866ee4b436c9bce391d6b5647fff7ccfd31b16e12844206cd2b2863` |
| Citron 结果 JSON | `docs/milestones/evidence/M1c-krkrsdl2-citron-clean-result.json` | 1,326 B | `29fa2525351e8d8ec8b256f6084834638c75cf137a5ac43e85daf6f304dc7ad0` |
| Citron 日志尾（120 行） | `docs/milestones/evidence/M1c-krkrsdl2-citron-clean-log-tail.txt` | — | `901558d636cef3f91a96bbc9f17ecdbc7924dd0c3186bf10e16b3b69f8442c21` |
| 插桩版完整 diff | `docs/milestones/evidence/M1c-krkrsdl2-instrumented.diff` | 16,436 B | `58f44a31e10d10bde8083ca4dcd9ea9f7897a1ce10f35946d4a4959a7c4afa65` |
| 插桩版诊断全文（2,558 行） | `docs/milestones/evidence/M1c-krkrsdl2-galnx-diag.txt` | 68,771 B | `bccbfda0e73d82bf5b96152576f41ab86f076b1fb145b44b08b76c4d28ee4441` |
| 插桩版截图（同一画面） | `docs/milestones/evidence/M1c-krkrsdl2-kag3-title-citron.png` | 940,588 B | `0bce597c8866ee4b436c9bce391d6b5647fff7ccfd31b16e12844206cd2b2863` |

原始证据（不入库）：`workspaces/m1-krkrsdl2/evidence/`、`workspaces/citron-harness/runs/20261030-013339-krkrsdl2/`。

## 7. 未验证 / 已知限制

1. 输入推进未验证：标题画面之后需要点击/回车推进，当前 harness 不发送输入事件；未见剧情第二页。
2. 音频未验证：KAG3 demo 的 BGM/SE 是否发声、Citron 音频后端行为均未测。
3. 真机（NS1）未验证：Citron ≠ 硬件（Vulkan/NVIDIA vs Tegra X1/Mesa Nouveau；Citron 无真实固件）。
4. 上游 release 预编译 NRO 在 Citron 上失败（VI STUBBED 后停滞），原因未定位；本结论不覆盖上游产物。
5. 修复包是 `#ifdef __SWITCH__` 编译期分支，未回测 PC/Linux 目标（理论上无影响，未实测）。
6. 使用 GCC 16.1.0 构建（上游 CI 镜像是更旧的 devkitA64），修复包与旧编译器兼容性未验证。
