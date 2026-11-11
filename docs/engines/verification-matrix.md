# 引擎能力验证矩阵

- 日期: 2026-11-11
- 适用版本: galnx 0.1.0
- 相关文件: `docs/engines/README.md`（术语与能力模型）、`examples/engines/*.yaml`（引擎描述符）、`schemas/engine.schema.json`
- 数据来源: 只从仓库已有记录提取（README 试点表、`docs/pilot/`、`docs/builds/`、`docs/experiments/`），本文件不新增真机结论

本文件把「引擎级能力」与「游戏级兼容性」分开记录：

- **引擎级**（descriptor 顶层 `verification` 块）：这个引擎整体在什么环境验证过，属于哪一档。
- **游戏级**（本矩阵）：某款具体游戏在某个 runtime 版本上，哪些测试项真正跑过。

两者不能互相替代：一个引擎可以是 `device_verified`，但某款游戏仍然只做过模拟器验证。

## 1 验证等级定义

| 等级 | 含义 |
| --- | --- |
| `source_review` | 只读过源码/文档，未构建、未运行 |
| `build_verified` | 在本仓库工具链下构建成功，未运行 |
| `emulator_verified` | 在模拟器（当前为 Citron Nightly）里跑通所述测试项 |
| `device_verified` | 在 Nintendo Switch 真机上跑通所述测试项（至少启动/画面） |
| `game_verified` | 真机上完成单款游戏的完整验收（启动→剧情→存档/读档→手柄→退出） |
| `partial` | 只有部分测试项通过，或有已知阻塞缺陷 |
| `unknown` | 没有证据，不要据此承诺 |
| `in_progress` | 正在验证，结果尚未定稿 |

约定：`supported: true` 只表示「实现存在且被验证过的部分可用」，具体到哪一档必须看 `verification`。真机结论一律以用户签收为准（引用用户消息编号或验收文档），模拟器结论不作为真机结论使用。

## 2 真机验收索引（device_verified / game_verified）

下表是**当前交付版本**的真机验收结果。真机结论一律以用户签收为准，签收消息编号见末列与 `docs/pilot/0.1.0-device-acceptance.md`。

| # | 游戏（语言） | adapter | runtime 版本 | 包大小 / sha256 | 测试环境 | 日期 | 启动 | 剧情 | 存档 | 读档 | 视频 | 手柄 | 退出 | 粒子 | 结论 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pilot-01 | 晴霁之后定是菜花盛开的好天气（CN） | `kirikiroid2-nx` | A10 1.0.9 | 2,870,911,704 B / `0efc23f6…` | Switch 真机（hbloader，DBI FTP 安装） | 2026-10-31 | ✓ | ✓ | ✓ | ✓ | ✓（中文 OP） | ✓ | ✓ | — | **game_verified PASS**（用户 m13918） | `docs/pilot/P4-device-runbook.md` §12.4；`docs/pilot/saveload-acceptance.md`；`docs/builds/015-k2nx-save-exit-drag.md` |
| Pilot-02 | IROSEKA FHD（CN） | `rfvp` | **1.2.5-test** | 10,087,541,464 B / `f6860842…` | Switch 真机（MTP 安装） | 2026-11-11 | ✓ | ✓ | ✓ | 未单独记录 | ✓（OP） | ✓ | ✓ | — | **device_verified PASS**（用户 m41226：测试通过、图标正确） | `docs/builds/051-rfvp-nv12-zerocopy.md`、`052-rfvp-p45-sync.md` |
| Pilot-03 | さくら、もゆ。（CN） | `rfvp` | **1.3.3-test** | 8,116,841,176 B / `965ee356…` | Switch 真机（MTP 安装） | 2026-11-11 | ✓ | ✓ | ✓ | 未单独记录 | ✓（OP，分档待确认） | ✓ | ✓ | ✓（标题粒子修复） | **device_verified PASS**（用户 m41226：测试通过、图标正确） | `docs/builds/049-p41-snow-particles.md`、`051`、`052` |
| Pilot-04 | AKASEKA HD 映入红瞳的世界 HD | `rfvp` | **1.4.1-test** | 6,738,209,496 B / `db31a312…` | Switch 真机（MTP 安装） | 2026-11-11 | ✓ | 未单独记录 | 未单独记录（rfvp 私有存档格式） | 未单独记录 | ✓（1080p H.264 OP + NV12 零拷贝，颜色正确、播放流畅） | ✓（A 确认 / B 返回 / 双摇杆 / PLUS 存档 / MINUS 退出 / R 快进 / ZR·ZL） | ✓（干净退出） | — | **device_verified PASS**（用户 m39477、m40951；缺剧情全流程与存档/读档验收，见 §6） | `docs/pilot/akaseka-fd-acceptance.md`；`docs/builds/050-akaseka-fd-nsp.md`、`051-rfvp-nv12-zerocopy.md` |

> 说明：Pilot-01 的存档/读档细节见 `docs/pilot/saveload-acceptance.md`（pad-only 存档路径、A4 NSP 内验证）；Pilot-04 的存档/读档没有单独验收记录，只确认了存档菜单可达与退出不丢设置。Pilot-02/03 的「视频」项只覆盖 OP 播放，未做逐档分辨率确认。Pilot-04 的签收证据只有 OP / 映射 / 干净退出，缺剧情全流程与存档/读档，因此结论按 device_verified 记录。

### 2.1 旧构建（已被上表取代，仅留档）

这些版本曾经交付并在真机验证过，但当前交付版本已更新；不重复计入验收，只作为回归对照。

| 游戏 | runtime 版本 | 包大小 / sha256 | 取代者 | 证据 |
| --- | --- | --- | --- | --- |
| IROSEKA FHD（CN） | 1.2.4-test | 10,087,536,344 B / `8b12f57f…` | 1.2.5-test（P45，同引擎 + NV12） | `docs/builds/049`、`052` |
| さくら、もゆ。（CN） | 1.3.2-test | 8,116,836,056 B / `8df0d398…` | 1.3.3-test（P45，同引擎 + NV12） | `docs/builds/049`、`052` |
| AKASEKA HD | 1.4.0-test | 6,676,387,544 B / `569af9fb…` | 1.4.1-test（P44，1080p OP + NV12） | `docs/pilot/akaseka-fd-acceptance.md`、`docs/builds/050`、`051` |
## 3 模拟器级验证（emulator_verified）

| 被测对象 | adapter | 环境 | 日期 | 已验证测试项 | 未验证 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| 晴霁之后（CN）A2–A9 构建 | `kirikiroid2-nx` | Citron Nightly 0237a9b88 | 2026-10-2x ~ 10-30 | 启动、剧情推进、存档/读档（虚拟光标）、手柄映射 v2、退出路径 | 音频/视频在真机前未量化 | `docs/builds/009`–`015`；`docs/pilot/P2-acceptance.md` |
| rfvp 引擎与 3 部作品构建线 | `rfvp` | Citron Nightly 0237a9b88 | 2026-10-2x ~ 11-1x | 渲染 60 FPS、输入映射、音频连续性、H.264/WMV2 OP、粒子、缓存与异步解码 | （真机项见上一节） | `docs/builds/008`–`052`；`docs/milestones/M5-fvp.md` |
| KAG3 demo（`data.xp3`） | `krkrsdl2` | Citron Nightly 0237a9b88 | 2026-10-26 | 标题画面渲染、输入注入 | 音频、存档、视频解码、真机 | `docs/builds/001-krkrsdl2-upstream.md`；`docs/builds/004-krkrsdl2-switch-fixes.md` |
| 自建最小 NScripter 脚本（自有版权内容） | `onscripter-nx` | Citron Nightly 0237a9b88 | 2026-10-30 | 启动、点击/A 推进、两分支选择 | 音频、存档写盘、触摸、真机、启动器 UI | `docs/builds/007-onscripter-nx.md`；`docs/milestones/evidence/M4c-*` |
| 自建 web app（HTML/CSS/JS/Canvas2D/WebGL） | `brewser` | Citron Nightly 0237a9b88 | 2026-10-29 | 页面渲染、DOM/CSS/JS、Canvas2D、WebGL、单次运行内 localStorage | 跨 run 存档（已证伪，重启后 SAVE=absent）、真机 | `docs/experiments/web-02-citron-smoke.md`；`docs/builds/006-brewser-web-adapter.md` |

## 4 引擎级能力汇总（descriptor 现状）

| 引擎 | status | graphics | movie | audio | input | save | touch | 引擎级 verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rfvp` | ready | device_verified | device_verified | device_verified | device_verified | device_verified | unknown | `device_verified`（Nintendo Switch，2026-11-10） |
| `kirikiroid2-nx` | ready | game_verified | device_verified | device_verified | game_verified | device_verified | unknown | `game_verified`（Nintendo Switch，2026-10-31） |
| `krkrsdl2` | research | emulator_verified | unknown | unknown | emulator_verified | unknown | unknown | `emulator_verified`（Citron，2026-10-26） |
| `onscripter-nx` | research | emulator_verified | unknown | unknown | emulator_verified | unknown | unknown | `emulator_verified`（Citron，2026-10-30） |
| `brewser` | research | emulator_verified | unknown | unknown | source_review | emulator_verified | source_review | `emulator_verified`（Citron，2026-10-29） |

能力实现与限制说明：

- `rfvp`：graphics = SDL2/GLES2；movie = H.264 + NVDEC + NV12 双平面零拷贝 + NV12→RGBA 软件回退 + 内建 WMV2/WMV3/VC-1 播放器；audio = audren + P27 连续性 ring + P30 audio JIT；save = 私有格式（不与 PC 互通）。
- `kirikiroid2-nx`：graphics = cocos2d-x 3.11.1 on Switch EGL；movie/audio = 随附 FFmpeg 3.2.19 portlib，真机回归清单覆盖中文 OP 与音频；save = 引擎原生存档 + 补丁 D/E/I。
- `krkrsdl2`：graphics/input 只在 Citron 标题+输入验证；音频（FAudio）、存档、视频解码、真机都未验证。
- `onscripter-nx`：graphics/input 在 Citron R1–R5 验证；无启动器/菜单 UI，音频、存档写盘、触摸、真机未验证；GPL-2.0-or-later 传染需法务评估。
- `brewser`：graphics 在 Citron 验证；input/touch 只有源码审阅（Web 层有事件，未逐项实测）；save 的跨 run 持久化已证伪，`supported` 仅表示页内可用。

## 5 如何新增一条游戏验收

1. 真机跑完后在 `docs/pilot/`（或 `docs/builds/`）写下验收文档：游戏、语言、adapter、runtime 版本、包大小与 sha256、测试环境、日期、逐项结果、用户签收消息编号。
2. 在本矩阵第 2 节加一行，逐项填「✓ / 未单独记录 / —」，`结论` 用 `device_verified` 或 `game_verified`，并写明证据路径。
3. 若这次验收改变了引擎整体结论（例如从 `emulator_verified` 升到 `device_verified`），同步更新 `examples/engines/<id>.yaml` 的顶层 `verification` 块与对应能力项的 `verification`，并更新第 4 节汇总表。
4. 跑 `PYTHONPATH=src python -m pytest -q tests/test_engines*.py`，确认描述符仍可加载。

## 6 未验证与限制

- 真机环境细节缺失：各验收文档没有记录 Switch firmware 与 Atmosphère 版本，因此 descriptor 的 `verification.firmware` / `verification.atmosphere` 故意留空，不要凭空填写。
- 真机环境：Pilot-02/03/04（1.2.5/1.3.3/1.4.1-test）的日期按用户签收消息（m41226、m40951）记为 2026-11-11，未记录具体时刻。
- 验收签收汇总见 `docs/pilot/0.1.0-device-acceptance.md`；它只做索引，不新增结论。
- `krkrsdl2` 只有模拟器标题+输入级证据，没有真机；`onscripter-nx` 只有自建最小内容 + 模拟器证据；`brewser` 只有模拟器 web 冒烟。三者都不应写成 device_verified。
- `touch` 在全部 5 个引擎上都没有真机验证（依赖触摸的 UI 也不能承诺可用）。
- IROSEKA / MOYU 当前包内仍是 720p OP（P45 只换引擎与图标，romfs 未变）；1080p 分档与 WMV2 回落路径只在 AKASEKA 源上验证过。
- `kirikiroid2-nx` 的音频/视频只出现在真机回归清单里，没有做量化（帧率/延迟）测量。
- Pilot-04 未达 game_verified：专家复审（2026-11-11）指出其证据只有 OP 播放、手柄映射与干净退出，缺剧情推进、存档/读档与结局级验收。在补一条完整流程验收记录之前，Pilot-04 与 rfvp 的 graphics/input 都保持 device_verified。
