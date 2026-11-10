# GalNX

**Galgame → Nintendo Switch 移植工作台**：PC 端的编排层——把「引擎构建 → 内容打包 → 自包含 NSP → 模拟器/真机验证」串成一条可复现的流水线。GalNX 不自研游戏引擎，只做适配器、清单、打包与验证。

> 状态（2026-11-10）：框架里程碑 M0–M6 全部完成（CLI 级），已在 **4 个垂直试点**上产出可在真机运行的中文自包含 NSP；最近一款《AKASEKA HD（映入红瞳的世界 HD）》**当天打包、用户真机直接可玩**。开发主仓库（含全部证据与历史）为私有远端 <https://github.com/KIRARITenshiChan/GalNX>；公开镜像是 sanitized 快照（只含代码/文档/补丁，不含游戏截图与封面）<https://github.com/KIRARITenshiChan/GalNX-public>，由 `scripts/public_release_sanitize.py` + `scripts/public_release_publish.py` 生成。

## 试点成果

| # | 游戏 | 引擎适配器 | 形态 | 最新版本 / 产物 | 验收 |
| --- | --- | --- | --- | --- | --- |
| Pilot-01 | 晴霁之后定是菜花盛开的好天气（CN） | `kirikiroid2-nx` | 自包含 NSP（romfs 2.87 GB） | A10 **1.0.9**，2,870,911,704 B sha256 `0efc23f6…` | **真机 PASS**（2026-10-31） |
| Pilot-02 | IROSEKA FHD（CN） | `rfvp` | 自包含 NSP（romfs 9.98 GB） | **1.2.4-test**，10,087,536,344 B sha256 `8b12f57f…` | **真机 PASS**（OP/映射/退出），残余 CG·背景切换卡顿持续优化 |
| Pilot-03 | さくら、もゆ。（CN） | `rfvp` | 自包含 NSP | **1.3.2-test**，8,116,836,056 B sha256 `8df0d398…` | **真机 PASS**（含标题粒子修复） |
| Pilot-04 | AKASEKA HD 映入红瞳的世界 HD | `rfvp` | 自包含 NSP（romfs 6.66 GB） | **1.4.0-test**，6,676,387,544 B sha256 `569af9fb…` | **真机 PASS**（2026-11-10，OP 无卡顿 / 映射符合预期 / 干净退出） |

rfvp 运行时目前具备：SDL2/GLES2 后端 **60 FPS**、H.264 OP（**真机 NVDEC 硬解**，720p/540p/480p/360p 分档）、资源三 LRU 缓存 + 启动预读 + zlib、大图异步解码与异步读档（CG 入口 632 → 273 ms）、惰性存档编码（逐句 112–135 → **5.3–5.8 ms**）、音频 JIT（延迟 ≈128 ms）、存档缩略图 GPU 下采样。

> 每款游戏的封面归该游戏所有（HOME 图标按作品单独制作）；GalNX 没有统一项目形象图。

## 引擎适配器

| 适配器 | 上游 / 许可 | 状态 | 说明 |
| --- | --- | --- | --- |
| `rfvp` | xmoezzz/rfvp · MPL-2.0 | **真机 stable**（3 部作品） | Rust 重写 FVP；GalNX 提供 Switch 后端、输入映射、电影、缓存等补丁栈 |
| `kirikiroid2-nx` | Erige005/Kirikiroid2-NX · 非 SPDX | **真机 stable**（1 部作品） | KiriKiri2 系；补丁 A–I 覆盖首启解包/自启动/内部插件/虚拟光标/存档 UI/退出崩溃/输入 |
| `krkrsdl2` | krkrsdl2 · MIT | 模拟器级完成 | 上游自带 Switch 目标；KAG3 内容包已在 Citron 出画面并可推进 |
| `onscripter-nx` | ONScripter-NX · GPL-2.0-or-later | 有条件（P2） | 零源码修改即可构建、Citron R1–R5 通过；缺启动器 UI，GPL 传染需法务评估 |
| `brewser` | Brewser · MPL-2.0 | 模拟器级完成 | Web 引擎；页内 localStorage 跨 run 不持久（上游 flush 依赖正常卸载），不适合做存档 |
| `renpy` | Ren'Py · MIT（引擎）/ 社区移植无 LICENSE | 暂缓 | 社区 Switch 移植无可分发许可，不接入 |

## 快速开始

依赖：

- Windows 10/11（构建/打包在本机 Windows 上验证；Linux 未验证）
- Python **3.11+**
- devkitPro（`switch-dev` + `switch-sdl2` 等 portlibs）
- `hacBrewPack`、`nstool`（打包与校验）
- 自己的 `prod.keys`（**不入库、不进日志、只按显式路径读取**）

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
galnx doctor                 # 20 项环境检查
galnx engines list           # 内置适配器
```

用清单驱动（清单格式见 [docs/MANIFEST.md](docs/MANIFEST.md)，示例见 `examples/`）：

```powershell
galnx preflight --manifest examples/pilot04-akaseka.yaml
galnx engines plan --manifest examples/pilot04-akaseka.yaml
galnx payload plan --manifest examples/pilot01-haruno-cn.yaml
```

构建与打包（需要真实 keyset 时**显式**传路径）：

```bash
# 1) 引擎构建（示例：rfvp）——由适配器 descriptor 的 build.commands 驱动
galnx build run --manifest examples/pilot04-akaseka.yaml

# 2) 内容暂存 + NSP 打包（elf2nso → npdmtool → nacptool → hacBrewPack → nstool）
galnx package nsp plan  --manifest examples/pilot04-akaseka.yaml
galnx package nsp build --manifest examples/pilot04-akaseka.yaml \\
    --elf <engine.elf> --romfs-dir <romfs> --out <out.nsp> --keyset <prod.keys>

# 3) 独立校验（TitleID/ProgID、NCA、romfs 摘要）
galnx package nsp verify --nsp <out.nsp> --manifest examples/pilot04-akaseka.yaml \\
    --nstool <nstool.exe> --keyset <prod.keys>
```

模拟器验证（Citron；一律 detach 运行）：

```bash
scripts/citron_run.sh --game <out.nsp> --no-stage --expect-title AKASEKA
```

> 模拟器没有真 NVDEC：验证 H.264 电影需放 `sdmc:/switch/rfvp/h264_sw.txt` 强制软解；调试播片用 `sdmc:/switch/rfvp/movie_debug.txt` 且内容必须是 `movie=1`。真机不要放这些 marker。

## 工作流

1. **写清单**（`examples/*.yaml`）：游戏元数据、引擎适配器、入口、Switch 参数、输入 profile、打包方式。
2. **静态检查**：`galnx preflight` / `galnx engines plan` / `galnx package plan`——不构建只验证。
3. **引擎构建**：适配器 `build.commands`（本机为 devkitPro / CMake / cargo 交叉编译）。
4. **内容暂存与打包**：`payload` 决定 romfs 放什么；`package nsp` 产出**自包含** NSP（游戏数据全在 romfs，SD 卡无需放数据）。
5. **验证**：`nstool` 校验 → Citron 首启/输入/存档冒烟 → 真机（MTP/DBI 安装）。
6. **记录**：编号构建文档 `docs/builds/NNN-*.md` + 证据 `docs/milestones/evidence/`（E1 日志 / E2 截图 / E3 哈希 / E4 源码片段）。

## 清单模型

`examples/` 下每种场景都有可跑示例：`manifest.krkr.yaml`、`pilot01-haruno-cn.yaml`、`pilot02-iroseka.yaml`、`pilot03-moyu.yaml`、`pilot04-akaseka.yaml`。关键约束：

- `switch.title_id` 必须落在 `0x0100000000000000–0x0fffffffffffffff`，且 base 低 13 位按 0x2000 对齐（否则被识别成 DLC/update）；
- `package.type: self_contained_nsp` 要求 `romfs_dir` 显式给全；
- 输入用 `input.default_mode: controller` + 语义动作 profile（`galnx input list`），不把按键硬编码进引擎；
- 构建产物可缓存（sha256 key）、可锁定（`.galnx/engine-lock.json`）。

## CLI 一览

| 命令 | 作用 |
| --- | --- |
| `galnx doctor` | 本机构建/测试环境检查（20 项） |
| `galnx preflight --manifest M` | 清单静态校验（schema、路径、TitleID、payload） |
| `galnx input list\|validate` | 输入 profile 列表 / 校验 |
| `galnx engines list\|info\|plan` | 引擎适配器与构建计划（不执行） |
| `galnx payload plan\|materialize\|verify` | 自包含 NSP 的 romfs 载荷规划/生成/校验 |
| `galnx package plan\|check\|nsp plan\|build\|verify` | NSP 元数据、暂存、打包与独立校验 |
| `galnx batch run\|diff\|clean\|build\|lock` | 多清单批量预检/构建、报告 diff、缓存锁 |
| `galnx build run --manifest M` | 单清单构建（带缓存与锁） |

## 仓库结构

```
LICENSE / THIRD_PARTY_NOTICES.md   MIT 与第三方许可边界（引擎补丁 / 游戏素材 / keys）
src/galnx/            CLI 与框架（manifest / doctor / preflight / input / engines / payload / package / batch / build）
schemas/              JSON Schema（game-manifest / engine / input-profile / payload / batch-report）
examples/             清单、引擎 descriptor、试点图标与打包示例
scripts/              构建与测试脚本（devkitPro 构建、NSP 打包、Citron harness、公开前素材隔离）
docs/builds/          编号构建记录 001–051 + Switch 补丁栈（docs/builds/patches/）
docs/milestones/      里程碑记录与证据（M1–M6、P 系列）
docs/pilot/           试点审计与验收（引擎、打包、真机 runbook、汉化）
docs/audit/           工具链与上游审计
docs/environment/     环境、工具链、harness 记录
docs/assets/          各作品封面（展示用，不打包进 NSP）
tests/                pytest（620 个用例 + 63 subtests）
```

## 文档地图

| 主题 | 入口 |
| --- | --- |
| 构建记录（按编号，含补丁与产物哈希） | [docs/builds/README.md](docs/builds/README.md) |
| 框架计划（v1.39 快照） | [docs/PLAN_DRAFT_v1.39.md](docs/PLAN_DRAFT_v1.39.md) |
| 工具链审计 | [docs/TOOLCHAIN_AUDIT.md](docs/TOOLCHAIN_AUDIT.md) |
| 清单格式 | [docs/MANIFEST.md](docs/MANIFEST.md) |
| 引擎适配器 | [examples/engines/](examples/engines/)、[docs/engines/README.md](docs/engines/README.md) |
| 打包与 TitleID | [docs/packaging/README.md](docs/packaging/README.md) |
| 试点验收 | [docs/pilot/akaseka-fd-acceptance.md](docs/pilot/akaseka-fd-acceptance.md)、[docs/pilot/P4-device-runbook.md](docs/pilot/P4-device-runbook.md) |
| 里程碑 M1–M6 | [docs/milestones/README.md](docs/milestones/README.md) |
| 环境与 harness | [docs/environment/citron-harness.md](docs/environment/citron-harness.md) |
| 许可与公开 | [LICENSE](LICENSE)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)、[docs/environment/public-release.md](docs/environment/public-release.md) |

## 设计原则

1. **工作台与运行时分离**：GalNX 只编排；引擎是第三方运行时，通过适配器接入。
2. **适配器优先**：游戏差异放在清单/适配器里，不进框架核心。
3. **原目录只读**：游戏源目录不被修改；所有中间产物写到独立 build 根。
4. **先 NRO 后 NSP**：先保证引擎能在模拟器跑通，再谈自包含打包。
5. **forwarder ≠ 自包含**：转发器包只是入口，不作为「移植完成」。
6. **自包含优先**：首个 NSP 目标就是游戏数据进 romfs、SD 卡零依赖。
7. **手柄优先**：输入按语义动作映射，必要时在引擎层做虚拟光标/按键重映射，不依赖触摸或鼠标注入。
8. **锁版本、可追踪**：上游 commit、工具链版本、产物 sha256、补丁 roundtrip 全部记录。

## 安全与合规

- 仓库**不包含**游戏数据、`prod.keys`、`title.keys`、Nintendo 证书或任何商业资源。密钥只在打包时按**显式路径**读取。
- 自包含 NSP 是**未签名自制包**，只应安装在你自己的自制系统设备上；不得分发含商业游戏内容的 NSP。
- 汉化文本/图像来自第三方汉化组或公开源码仓库，版权归原作者；仓库只记录处理流程与哈希，不附带资源本体。
- 第三方组件遵循各自许可证（见下）；分发二进制前需自行完成许可证义务评估，尤其是 GPL（ONScripter-NX、devkitPro 工具链）与 LGPL（FFmpeg 静态链接）。
- **公开仓库前必须隔离游戏素材**：`docs/milestones/` 截图、`docs/assets/` 封面、`examples/pilot0*/` 图标均为第三方版权（约 358 MB / 351 张），且私有 git 历史里仍然存在——用 `scripts/public_release_sanitize.py` 导出干净树后发布，流程见 [docs/environment/public-release.md](docs/environment/public-release.md)。

## 第三方组件与许可

| 组件 | 许可 | 用途 |
| --- | --- | --- |
| devkitPro / devkitA64 / libnx | GPL-2.0+ / ISC（libnx） | Switch 交叉编译与系统 API |
| SDL2（switch portlib） | zlib | rfvp / krkrsdl2 窗口与输入 |
| FFmpeg（含 nvtegra 补丁） | LGPL-2.1+ | H.264 OP 解码与 nvtegra 硬解 |
| rfvp | MPL-2.0 | FVP 运行时（GalNX 补丁按文件级 copyleft） |
| krkrsdl2 | MIT | KiriKiri SDL2 运行时 |
| ONScripter-NX | GPL-2.0-or-later | NScripter 运行时 |
| Brewser | MPL-2.0 | Web 运行时 |
| Kirikiroid2-NX | 非 SPDX（自用，不对外分发二进制） | KiriKiri2 运行时 |
| hacBrewPack | GPL-2.0 | NSP 打包 |
| nstool | MIT | NSP 解析与校验 |
| nx-hbloader / Atmosphère | ISC / GPL-2.0 | 真机自制环境（用户自有） |

本仓库自身代码（框架、CLI、脚本、文档）采用 **MIT** 许可，见 [LICENSE](LICENSE)，版权署名 KIRARITenshiChan。

但仓库里有两类内容**不适用** MIT，必须分别对待：

- **引擎补丁**（`docs/builds/patches/`）是对上游源码的修改，按上游许可分发（rfvp = MPL-2.0、krkrsdl2 = MIT、Kirikiroid2-NX = KiriKiri BSD-style 非 SPDX），每份补丁目录都附了上游 LICENSE 原文，总述见 [docs/builds/patches/LICENSE.md](docs/builds/patches/LICENSE.md)；
- **游戏截图/封面/图标**（`docs/milestones/`、`docs/assets/`、`examples/pilot0*/`）是第三方版权素材，仅作开发证据，**不随仓库公开**。

完整边界与再分发义务见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；公开仓库前必须按 [docs/environment/public-release.md](docs/environment/public-release.md) 隔离游戏素材。

## 开发与测试

```bash
pip install -e .
python -m pytest -q          # 620 个用例 + 63 subtests
```

约定：

- 每个构建/修复一条编号记录：`docs/builds/NNN-短名.md`（编号不重复、不重排）；
- 计划草案（唯一事实来源）在 `E:/Othergames/Nintendo Switch/Workspace/GalNX_移植框架计划草案.md`，每次改动打版本标记并备份上一版，同时把快照放进 `docs/`；
- 证据分级：E1 原始日志 / E2 截图 / E3 哈希元数据 / E4 源码片段；结论必须能追到证据。

## 已知限制

- 仅 Windows 构建链经过验证（Linux/macOS 未验证）。
- 模拟器侧 Citron 无真 NVDEC、鼠标默认走触摸语义；真机路径与模拟器路径的差异在文档里逐条记录。
- 1080p 电影未启用：CPU NV12→RGBA + 整帧上传会逼近 16.67 ms 预算；需 GLES2 双平面 shader 零拷贝后才考虑。
- GUI、真实引擎 `build.commands` 的通用接入与 CI 门槛属于 M6 之后的后续项。