# M1 KiriKiri 原型打通（krkrsdl2 + 合法 KAG3 内容）

- 状态：**done（模拟器级）**；真机待验证
- 日期：2026-10-30（Asia/Shanghai）
- 关联任务：task-13（构建）、task-14（SDL2 基线）、task-15（Citron harness）、Lead 执行 M1-d/e
- 上游依据：计划 v0.4 §10 M1、§7.2（引擎路线）；审计 v1.3 §4.B / `docs/builds/001`、`004`

## 1. 目标与验收标准

| 验收项 | 标准 | 结果 |
| --- | --- | --- |
| M1-a 最小 SDL2 NRO | CMake/Make 退出 0；NRO 生成；SHA-256 记录 | ✅ `m1-sdl2.nro` 6,740,165 B，CMake 12.8 s，Make 6.8 s |
| M1-b Citron harness | 任意 NRO → 启动/截图/日志/JSON | ✅ `scripts/citron_run.sh`（21,897 B）+ `docs/environment/citron-harness.md`（227 行）；brewser 自测通过 |
| M1-c krkrsdl2 上游构建 | 从源码构建出 NRO | ✅ 首轮（001）+ 修复版（004）：NRO 17,911,329 B |
| M1-d 合法内容跑通 | 画面/文字至少一项可见 | ✅ KAG3 demo 标题画面在 Citron 渲染，日文/英文正常 |
| M1-e 里程碑记录 | 文档 + 证据 + 提交 | ✅ 本文件 + build 001/002/003/004 + evidence/ |

**一句话结论**：从零构建的 krkrsdl2 NRO 在 Citron（Switch 模拟器）中完整启动，渲染合法 KAG3 demo 标题画面；这是 GalNX 第一个端到端跑通的 KiriKiri 原型（模拟器级，真机与输入推进未验证）。

## 2. 环境与版本

| 组件 | 版本/标识 |
| --- | --- |
| 工具链 | devkitPro `D:\devkitPro`；devkitA64 r30-1、GCC 16.1.0、binutils 2.46.0、newlib 4.6.0.20260123-4、libnx 4.12.0-1、switch-tools 1.13.1-1、switch-cmake 1.5.2-1、switch-sdl2 2.28.5-4 |
| 构建系统 | CMake 4.0.2（MSYS2）+ Ninja 1.13.2 + `$DEVKITPRO/cmake/Switch.cmake` |
| 引擎 | krkrsdl2 上游 `124bdf84`（2026-10-01）+ 本仓库补丁包（`docs/builds/patches/krkrsdl2-switch-emulator/`） |
| 内容 | KAG3 demo（kag3-demo main，`external/kag3@b21b16ea`）+ IPAexGothic 004.01 字体 → `data.xp3` 6,628,897 B |
| 模拟器 | Citron Neo nightly `0237a9b88`（Windows msvc，Vulkan；GPL-3.0，外部工具不分发） |
| 宿主 | Windows 10.0.26100，16 核；构建根 `E:/galnx-build`（无空格） |

## 3. 关键步骤与命令

1. **工具链**：补装 switch-dev 14 包 + SDL2 图形栈（`docs/environment/devkitpro-2026-10-29.md`）。
2. **内容包**（003）：`krkrrel.exe data-tmp -out data.xp3`，放入 `system_polyfill/font.ttf`（IPAexGothic）→ `data-withfont.xp3`。
3. **构建**（001/004）：`cmake -S . -B build5 -G Ninja -DCMAKE_TOOLCHAIN_FILE=$DEVKITPRO/cmake/Switch.cmake -DEMBED_DATA_PATH=…/data-withfont.xp3 …` → `ninja -j16`（370 步，exit 0）。
4. **重打包**：romfs 只放 `data.xp3` → `elf2nro … --romfsdir=build5/romfs`（NRO 17,911,329 B）。
5. **运行**：`bash scripts/citron_run.sh --nro build5/krkrsdl2.nro --timeout 70 --settle 12 --expect-title 'Kirikiri' --app-log-regex 'Booting game:'` → `status=loaded`、`title_match=true`。

完整命令、失败点与绕法见 `docs/builds/001`、`004`；模拟器 harness 参数见 `docs/environment/citron-harness.md`。

## 4. 证据清单

| 证据 | 路径 | 大小 | SHA-256 |
| --- | --- | --- | --- |
| KAG3 demo 标题画面（Citron，干净版） | `docs/milestones/evidence/M1c-krkrsdl2-kag3-title-citron-clean.png` | 940,588 B | `0bce597c8866ee4b436c9bce391d6b5647fff7ccfd31b16e12844206cd2b2863` |
| Citron 结果 JSON（干净版） | `docs/milestones/evidence/M1c-krkrsdl2-citron-clean-result.json` | 1,326 B | `29fa2525351e8d8ec8b256f6084834638c75cf137a5ac43e85daf6f304dc7ad0` |
| Citron 日志尾（120 行） | `docs/milestones/evidence/M1c-krkrsdl2-citron-clean-log-tail.txt` | — | `901558d636cef3f91a96bbc9f17ecdbc7924dd0c3186bf10e16b3b69f8442c21` |
| 干净构建日志 | `docs/milestones/evidence/M1c-krkrsdl2-clean-build.log` | — | `7af79bbc5df38fb7e7b860862e10de3d0d0420d8f5abdb410038a4313d1193c8` |
| 最小 SDL2 应用截图（M1-a） | `docs/milestones/evidence/M1a-citron-m1-sdl2-window.png` | 79,701 B | `8be238c81223099e79abff5bb31b4266a6eff33f115808ba5beb2a96a6bbc1d3` |
| 最小 SDL2 结果 JSON（M1-a） | `docs/milestones/evidence/M1a-citron-m1-sdl2-result.json` | — | `ab25ef598892971eab8664dab5a8cfe171c9c89f726c76505308807f50dbb4bc` |
| 插桩诊断全文 | `docs/milestones/evidence/M1c-krkrsdl2-galnx-diag.txt` | 68,771 B | `bccbfda0e73d82bf5b96152576f41ab86f076b1fb145b44b08b76c4d28ee4441` |

运行原始证据（不入库）：`workspaces/citron-harness/runs/20261030-013339-krkrsdl2/`、`workspaces/m1-krkrsdl2/evidence/`。

## 5. 结果与结论

1. **端到端链路闭环**：源码 → devkitPro 交叉编译 → romfs 内嵌合法数据 → Citron 加载 → 渲染标题画面。M1 的核心风险（「Switch 上没有可用的 KiriKiri 运行路径」）已被证伪。
2. **上游缺陷是路径桥接类**：4 处 `__SWITCH__` 路径/命令行问题，38 行补丁即可修复，说明 krkrsdl2 的 SDL2 渲染、TJS 脚本引擎、KAG3 系统在 Switch 上工作正常。
3. **字体方案可复用**：KAG3 polyfill 的 `system_polyfill/font.ttf` + `Font.addFont` 机制在 SDL2 版同样有效，IPAexGothic 渲染正常；这为后续接入商业游戏（缺字体时）提供兜底。
4. **内嵌形态确认**：`EMBED_DATA_PATH` 把数据编进 RomFS（`romfs:/data.xp3`），单游戏内嵌、无启动器——与计划 §7.2 对 krkrsdl2「上游先行验证」的定位一致；产品化多游戏启动器仍需 krkr-ns 侧或自研 shell。

## 6. 未验证与剩余风险

| # | 未验证项 | 影响 | 后续 |
| --- | --- | --- | --- |
| 1 | 输入推进（点击/回车/方向键） | 只见到标题页，未验证剧情推进/选项 | M2 输入层一并测；或给 harness 加输入注入 |
| 2 | 音频输出 | BGM/SE 是否工作未知 | M2/M3 期间用真实游戏验证 |
| 3 | 真机 NS1 | Citron ≠ 硬件（Vulkan/Mesa 差异、无真实固件） | 用户真机可用时做 M1 真机冒烟 |
| 4 | 上游 release NRO 在 Citron 失败 | 官方产物无法直接当基线 | 已记录；以本仓库构建为基线 |
| 5 | 商业游戏（`.xp3` 非 demo）兼容性 | KAG3 demo 只用标准系统 | 等游戏资源环节再测（用户已表示 E:/Othergames/Galgame/ 待用） |
| 6 | 修复包在真机/旧 GCC 下未回测 | 理论无影响（`__SWITCH__` 分支） | 真机冒烟时一并验证 |

## 7. 下一步

1. **M2 输入层**：先给 `citron_run.sh` 加输入注入（点击/按键），验证 KAG3 demo 剧情推进；这与 M2 的「键鼠模拟」设计直接相关。
2. **M1 真机冒烟**（待用户）：NRO 拷入 SD 卡 `switch/`，hbmenu 启动，屏摄 + 日志；对比模拟器结果。
3. **M3 NSP 自包含**：把该 NRO 的 exefs/romfs 布局接入 hacBrewPack 流程（`docs/audit/08-packaging-refresh.md` §6 契约）。
4. 记录 `docs/builds/001` 的 Citron 验证结论与 data.xp3 命名要求（本轮已补）。
