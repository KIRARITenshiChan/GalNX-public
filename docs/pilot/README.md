# GalNX 首款垂直试点：《晴霁之后定是菜花盛开的好天气》→ Switch

> 状态：**P0–P3 + 存档/读档（U20）+ 真机退出崩溃修复（U21，模拟器级）全部完成（2026-10-30）**——自包含 NSP 已在 Citron 模拟器上直接启动、手柄可推进剧情（用户完成标准达成），整条流水线已固化进 GalNX CLI（源码准备 → payload → romfs → NSP → verify，一条命令复现）；A4 NSP 起**手柄可独立完成存档/读档**（patch D/E，见 `docs/builds/010`）；A5 NSP 起**主窗口确认关闭不再崩溃**（patch F，见 `docs/builds/011`，模拟器级 PASS，待真机复验）；P4 真机待用户设备。
> 本目录记录试点专用文档；里程碑文档在 `docs/milestones/`，通用构建记录在 `docs/builds/`。

## 1. 用户目标与完成标准（m04829）

- 新增候选引擎：**Kirikiroid2-NX**（`Erige005/Kirikiroid2-NX`，KiriKiri2 播放器，zeas2 Kirikiroid2 1.3.9 源码移植）。
- 首款垂直试点：`E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气/`（PC 版，非 Kirikiroid 成品）。
- **完成标准（用户定义）**：在模拟器（Citron）上「已打包 NSP、可直接启动、支持手柄操作」；达标后才做真机（用户设备 NS1）。
- 中文/日语版本、存档等细项在达标后继续。

## 2. 结论速览（P2/P3 判定）

| 用户标准 | 判定 | 证据 |
| --- | --- | --- |
| 已打包 NSP（自包含） | ✅ | `Kirikiroid2-NX-010047410000b0b4.nsp` 2,906,125,016 B sha256 `eb6c6a15…c705f`，romfs 109 文件/2,878,186,922 B 内含 23 个游戏 payload |
| 可直接启动 | ✅ | 全新 SD 首启自动解包 23 文件（14.4 s）→ autostart → 07:40:47 `title.ks`；二启 `already extracted` → 48 s 到标题 |
| 支持手柄操作 | ✅ | RIGHT+C → `start.ks` → `@0000A_Z01.ks` 正文；A 推进；60 FPS、0 exception |
| 存档/读档（U20） | ✅ | **全手柄**闭环：PLUS→SAVE 界面→Y 光标→D-Pad 选槽→A 存档=45,941 B 落盘；重启→R→LOAD 界面→A 读档→回到存档点→A 继续推进（NRO + A4 NSP 双形态；`docs/pilot/saveload-acceptance.md`） |
| 退出游戏（U21） | ✅（模拟器级） | 真机 A4 报 Error Code 2-0000 / Member "SystemObj" does not exist @line(365) checkdialog.tjs；patch F 两处修复（关闭链直接 `TVPExitApplication(0)`、补 Window TJS 兼容成员）后 Citron exit3 + A5 回归双 PASS：glog 记录「[close] main window close confirmed; terminating application」，0 error，回到游戏列表（`docs/builds/011`、`saveload-acceptance.md` §8/§9）；真机待 A5 复验 |
| 手柄存档实现 | ✅ | 引擎 patch D（虚拟鼠标光标）+ patch E（原生存档/读档热键，手写 TJS 求值）；源码级可复现，见 `docs/builds/010` |
| 模拟器平台 | ✅ | Citron Nightly `0237a9b88`（Windows x64 / Vulkan） |
| 工程化复现（P3） | ✅ | GalNX CLI 一条命令链产出 A3 NSP；`galnx preflight/payload plan/payload materialize/package nsp` 全绿，romfs 复现 oracle 逐字节一致 |
| 合规 TitleID（P3） | ✅ | A3 NSP `Kirikiroid2-NX-010047410000A000.nsp` 2,906,131,672 B sha256 `1f54bdf1…`（base 0x2000 对齐；A2 的 `…b0b4` 属 DLC 区，`validate_base` 已能拦截） |
| 真机 | ⬜ P4 | 待用户设备（需 Atmosphère + sigpatches） |

完整判定、构建链路、证据哈希、限制清单：**`docs/pilot/P2-acceptance.md`**（P2）、**`docs/pilot/P3-pipeline.md`**（P3 工程化）。

## 3. 试点对象档案（P0 只读侦察）

| 项 | 值 |
| --- | --- |
| 游戏目录 | `E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气/`（约 2.9 GB） |
| 引擎 | KiriKiri2（`haruno.exe` 3,655,680 B 含 `@TVP(kirikiri) for win32`；`.tpm` 插件体系） |
| XP3 数据 | 14 个 xp3，共约 2.87 GB（data / scenario / image00–06 / movie / voice01–02 等） |
| 签名 | 每个大 xp3 旁 212 B `.sig`（RSA-PSS）；K2NX 只读不校验，不影响运行 |
| 插件 | plugin/ 8 个：csvParser.tpm / extrans.tpm / fstat.tpm / layerExImage.tpm / windowEx.tpm / wumsadp.tpm / wuvorbis.tpm / krmovie.dll |
| 中文补丁 | xmoe 体系（haruno_chs.exe、`.xmoe`、xmoeParser.dll、data.xm3 等）= Windows DLL 注入，**Switch 不可移植** |
| 字体 | simhei.ttf、simsun.ttc（英文/日文路径用引擎自带字体，未用这两个） |
| 存档 | `savedata/krenvprf.kep`（KiriKiri 偏好）；游戏内存档目录运行时生成 |

## 4. 引擎选择与路径决策

候选对比见 `docs/pilot/P1-engine-k2nx.md`（预编译 NRO 验证、三路径对比）。**最终选定路径 A**：

> **路径 A（选定）：重建 K2NX 源码 + romfs 首启解包 + autostart + per-game KeyMap → 自包含 NSP。**

理由：
1. 预编译 K2NX NRO 能完整读取本作 14 个 XP3（19,171 文件激活），只差「插件别名」一处（补丁 C）即可跑进正文 → 源码构建收益最大、改动最小。
2. 源码级三段改造后，游戏数据可全部进 NSP romfs，满足严格「自包含」；用户不需要往 SD 拷 3.4 GB。
3. 自建 portlibs（FFmpeg 3.2.19 等）+ Windows 构建坑都有确定解法，构建可复现（详见 `P2-acceptance.md` §3）。
4. 备选路径 B（NRO 转 NSP + 数据外置）不满足「自包含」；路径 C（krkrsdl2）在 M1 已验证但插件层覆盖未知，作为后备。

## 5. 里程碑

| 里程碑 | 内容 | 验收 | 状态 |
| --- | --- | --- | --- |
| P0 | 侦察：引擎审计、游戏数据盘点、Citron 可行性 | NRO 能启动 + 数据/插件/汉化清单 | ✅ 完成 |
| P1-a | Citron 多步输入自动化 + K2NX 中引导游戏 | 进到标题/正文并截图取证 | ✅ 完成（run H/I 证据 `P1a-*`） |
| P1-b | K2NX 源码机制审计 + 自包含 NSP 改造可行性 | `docs/pilot/P1-engine-k2nx.md`（1,267 行） | ✅ 完成 |
| P1-c | 游戏数据审计（XP3/插件/汉化/sig/字体） | `docs/pilot/P1-game-audit.md` | ✅ 完成 |
| P1-d | NSP 自包含打包可行性与原型 | `docs/pilot/P1-nsp-packaging.md` + `scripts/build_pilot_nsp.sh` | ✅ 完成 |
| P2 | 源码构建（三补丁）+ A2 自包含 NSP + 手柄验收 | 用户完成标准（模拟器） | ✅ **完成**（`P2-acceptance.md`） |
| P3 | 打包工程化：源码构建→补丁→payload→NSP 固化进 GalNX CLI | 一条命令可复现产出 NSP + manifest | ✅ **完成**（`P3-pipeline.md`；A3 NSP 已验收） |
| P3.5 | 手柄存档/读档（U20）+ A4 NSP | 全手柄完成存→落盘→重启→读→续玩 | ✅ **完成**（`saveload-acceptance.md`、`docs/builds/010`） |
| P3.6 | 真机退出崩溃修复（U21）+ A5 NSP | 确认关闭不崩溃（模拟器级）+ A5 打包校验 | ✅ **完成（模拟器级）**（`docs/builds/011`、A5 2,906,138,328 B sha256 `f179f0a2…`，verify 19 checks；真机待复验） |
| P4 | 真机安装/启动/手柄/存档验证 | 用户设备 NS1 | ⬜ 待用户设备（runbook 已就绪：`P4-device-runbook.md`） |

## 6. 任务板映射与写权限（P1 阶段，已归档）

| 任务 | 负责人 | 写权限 |
| --- | --- | --- |
| task-32 P1-a | audit-web | `scripts/citron_run.sh`、`docs/environment/citron-harness.md`、`docs/milestones/evidence/` |
| task-33 P1-b | audit-engines | `docs/pilot/P1-engine-k2nx.md` |
| task-34 P1-c | audit-switch | `docs/pilot/P1-game-audit.md` |
| task-35 P1-d | audit-package | `docs/pilot/P1-nsp-packaging.md`、`scripts/build_pilot_nsp.sh` |
| task-38 P2-c | Lead | `docs/pilot/P2-acceptance.md`、证据、计划 v0.9 |
| P2 收尾 | Lead | 本文件、`docs/milestones/P*-*.md`、统一提交 |

## 7. 协作与证据约定

- Citron 单实例：同一时刻只允许一个任务使用；启动前 `tasklist` 断言 0 实例、三重校验（status=loaded、窗口标题匹配、PID 与 run 目录一致）、只 kill 自己 PID、用完 `taskkill` 并回报释放时间。**本轮教训**：两个任务同时启动会因 yuzu 系单实例转发混跑同一进程（`docs/pilot/P2-acceptance.md` §4.5 与 task-38 记录）。
- 游戏原件 `E:/Othergames/Galgame/` 只读；运行副本在 `C:/Users/<user>/AppData/Roaming/citron/sdmc/kirikiri/haruno/`（3.4 GB），可随时删除重跑。
- 证据分级沿用 `docs/milestones/README.md`（E1 原始日志 / E2 截图 / E3 哈希元数据 / E4 源码片段）；仓库只收结论 + 关键截图，完整 run 目录留在 `workspaces/`（gitignored）。
- 一切产物不入库：NRO/NSP/游戏数据/keys；`workspaces/`、`.galnx/` 已 gitignore。NSP 只在 `E:/galnx-build/pilot-01/out/`。

## 8. 风险登记（P2 收尾更新）

| # | 风险 | 影响 | 缓解 | 状态 |
| --- | --- | --- | --- | --- |
| R1 | K2NX 对该游戏 `.sig`/插件不兼容 | 跑不起来 | 实测：三补丁后进正文，60 FPS | **关闭** |
| R2 | K2NX 本机无法构建 | 无法自包含 | 本机 MSYS2 devkitPro 构建成功（ar 分块 + 自建 portlibs） | **关闭** |
| R3 | 3.4 GB romfs NSP 出包/装载受限 | 自包含做不出 | A2 NSP 2,906,125,016 B 打包成功、Citron 加载成功 | **关闭**（真机 FAT32 4 GiB 限制待 P4） |
| R4 | 中文（xmoe）无法在 Switch 运行 | 中文版不可用 | 已定性为 Windows DLL 注入体系，不可移植；先保日文原版 | 保留（记录，不阻塞） |
| R5 | 性能不足 | 体验差 | Citron 60 FPS；真机待测 | 保留（P4 观察） |
| R6 | 版权/合规 | 法律风险 | 游戏数据不入库/不分发；NSP 仅本机 | 保留（长期约束） |
| R7 | 物理手柄未接入（本轮用键盘→虚拟手柄） | 手柄路径未完全验证 | 真机 P4 用物理手柄复核 | 新增 |
| R8 | 存档写读回未验证 | 无法续玩 | **模拟器级已关闭**：patch D/E 手柄存档/读档闭环（`saveload-acceptance.md`）；真机仍待 P4 复核 | **关闭（模拟器）** |
| R9 | 音频未验证 | 无声/异常 | P4 取证 | 保留（P4） |
| R10 | NSP 形态鼠标注入无效（NRO 有效） | 触摸/鼠标路径受限 | 已定位：guest ADV 层不消费触摸 + Citron 渲染子窗口是独立 HWND（`saveload-acceptance.md` §6）；改用「手柄 + 虚拟光标」路线，不再依赖鼠标注入 | 记录（已绕过） |
| R11 | K2NX 许可为 NOASSERTION（KiriKiri BSD-style 非 SPDX） | 产物不可对外分发 | 仅本机自用；descriptor `license_spdx=NOASSERTION` + THIRD_PARTY 清单 | 保留（长期约束） |
| R12 | `engines prepare` 不支持 prebuilt 后端 / jxrlib master 未 pin | 预编译上游不能走 prepare；重建可能漂移 | 显式报错；portlibs 待 pin（`P3-pipeline.md` §10） | 新增 |
| R13 | 手柄存档热键绑定本作 TJS API（`MainObj.SaveAction` / `_SAVELOADOBJECT`） | 换游戏需重写表达式 | 表达式集中在 `GalNX_QuickSaveLoad()`；`docs/builds/010` §2.2/§6 E6 记录改法 | 新增 |
| R14 | `GalNXLog` 诊断日志会写 `sdmc:/galnx-input.log` | 正式发布需移除 | 补丁里已集中为单个函数，删除即恢复 | 新增 |

## 9. 变更记录

| 日期 | 版本 | 内容 |
| --- | --- | --- |
| 2026-10-30 | v0.1 | P0 侦察完成：K2NX 预编译 NRO 在 Citron 启动成功、游戏数据入 sdmc、P1 四任务派发 |
| 2026-10-30 | v0.2 | P1 四任务完成 + P2 完成：路径 A 选定并落地（三补丁 + 自建 portlibs + A2 自包含 NSP），全新 SD 首启/手柄进正文/二启 marker 全部实测通过；R1/R2/R3 关闭；新增 `P2-acceptance.md`，计划升级 v0.9 |
| 2026-10-30 | v0.3 | P3 完成：payload/NSP driver/harness detach/引擎源码准备四模块 + CLI 接线，A3 合规 TitleID NSP 由 CLI 产出并在 Citron 全新 SD 冒烟通过；新增 `P3-pipeline.md`、`P3-verification.md`；R7/R8/R9 保留至 P4，新增 R10/R11/R12；计划升级 v1.0 |
| 2026-10-30 | v0.4 | U20 完成：K2NX 增加 patch D（手柄虚拟光标）+ patch E（原生存档/读档热键 + 菜单键盘导航），全手柄完成存→落盘→重启→读→续玩闭环；产出 A4 NSP（version 1.0.3，sha256 `2003ec1e…`）并通过 `galnx package nsp verify`（19 checks/18 ok/1 warn）；新增 `saveload-acceptance.md`、`docs/builds/010-k2nx-controller-saveload.md`、`P4-device-runbook.md`；R8 关闭（模拟器级）、R10 已绕过，新增 R13/R14 |
| 2026-10-30 | v0.5 | U21 完成（模拟器级）：patch F 修复真机退出崩溃（主窗口确认关闭 → `TVPExitApplication(0)`；Window 补 `minimized/maximized` 等兼容成员）；产出 A5 NSP（version 1.0.4，sha256 `f179f0a2…`）并通过 verify（19 checks/18 ok/1 warn）；Citron exit3 + A5 回归双 PASS；新增 `docs/builds/011-k2nx-exit-crash-fix.md`，runbook 全面改 A5（B5/B6 退出验收），计划升级 v1.2 |
