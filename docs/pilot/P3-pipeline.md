# P3 打包工程化：游戏原件 → 自包含 NSP 的一条命令链

> 状态：**代码与流程已完成（2026-10-30）**；A3 合规 TitleID NSP 已由 GalNX CLI 构建、Citron 全新 SD 冒烟 PASS；独立复跑见 P3-f。
> 上游里程碑：P2（手工流程跑通，见 `docs/pilot/P2-acceptance.md`）。本文件记录 P3 如何把手工流程固化为 CLI 能力，以及固化的实测结果。

## 1. P3 目标与验收

P2 证明了「K2NX 源码 + 三补丁 + 首启解包 + autostart + per-game KeyMap → 自包含 NSP」这条路能跑通，但每一步都是 `E:/galnx-build/pilot-01/` 下的一次性脚本。P3 的目标是：

1. 把 payload 生成、NSP 打包、引擎源码准备、harness 注入全部收进 `galnx` CLI；
2. 用一份 `game manifest` 驱动整条流水线，产物带 `PROVENANCE`；
3. 一条命令链从游戏原件复现出**合规 TitleID** 的自包含 NSP，并在 Citron 全新 SD 上冒烟通过；
4. 把 P2 踩到的两个坑固化成硬约束：TitleID 必须 base 对齐（§8）、Citron harness 必须脱离调用方进程树（§9）。

P3 的验收不是「文档写完」，而是：**CLI 端到端跑出的 NSP 与 P2 的 A2 在组件级一致（romfs/payload/exefs），且运行时行为一致（全新 SD 首启 + 手柄进正文）。**

## 2. 交付总览

| 任务 | 负责人 | 交付 | 测试 |
| --- | --- | --- | --- |
| P3-a task-40 | audit-switch | `src/galnx/payload/`（content 347 / keymap 484 / plan 1,030 / cli 341 行）+ `schemas/payload.schema.json` + `galnx payload plan|materialize` + `docs/packaging/payload.md`（427 行） | 105 用例 |
| P3-b task-41 | audit-package | `src/galnx/package/nsp.py`（约 950 行：plan/build/verify/provenance）+ `galnx package nsp` + `docs/packaging/nsp-build.md`（347 行） | 48 用例 |
| P3-c task-42 | audit-engines | `src/galnx/engines/source.py`（约 520 行：verify_pin/prepare/check-only/lock）+ descriptor schema 扩展 + `examples/engines/kirikiroid2-nx.yaml` + 三补丁入库 + `docs/builds/009-k2nx-selfcontained-build.md` | 24 用例 |
| P3-d task-43 | audit-web | `scripts/citron_run.sh` `--detach`/`--wait-job`/`--status`（修 R14）+ `docs/environment/citron-harness.md` §15 | 兼容回归 + R14 复现 |
| P3-e task-44 | Lead | cli 接线（`force_utf8_stdio`、payload/engines/nsp register）、`examples/pilot01-haruno.yaml`、A3 NSP、Citron 冒烟、本文件、计划 v1.0 | 全量 600 passed / 63 subtests |
| P3-f task-45 | audit-package | `galnx package nsp verify` 子命令 + `docs/pilot/P3-verification.md`（独立 verify） | 并入 package 测试 |
| P3-g task-46 | audit-web | A3 独立全新 SD 冒烟 + `docs/pilot/P3-smoke-independent.md` | 运行时 |

全量测试基线：**600 passed, 63 subtests passed**（`PYTHONPATH=src python -m pytest -q`，44 s）。运行 CLI 需要 `PYTHONPATH=src`（仓库未 `pip install`）。

## 3. CLI 能力

```
galnx preflight  --manifest YAML                    # manifest + 环境前置检查
galnx engines    prepare --descriptor YAML --dest DIR [--check-only] [--fetch]
galnx engines    list|info|plan
galnx payload    plan       --manifest YAML [--no-files] [--json]
galnx payload    materialize --manifest YAML --out DIR [--mode copy|hardlink|symlink]
galnx package    nsp --manifest YAML --elf ELF --romfs-dir DIR --keyset KEYS
                     [--dry-run|--build] [--provenance JSON] [工具路径覆盖...]
galnx package    nsp verify --nsp FILE --manifest YAML [--keyset KEYS] [--provenance JSON]
```

约定：

- **退出码**：`0` 成功、`1` 构建/校验失败、`2` 输入或计划错误（manifest 不合法、TitleID 不合规、工具缺失）。`verify` 用 `0/1/2`。
- **keyset 只显式**：`--keyset <path>` 或 `synthetic`（仅结构冒烟）；不读环境变量、不写日志、PROVENANCE 只记 path/size/sha256。这是 M3 决策 7 的延续（DSH 会剔除含 `KEY` 的环境变量，`GALNX_PROD_KEYS` 通道不可用）。
- **UTF-8 stdio**：`main()` 首行 `force_utf8_stdio()`（`cli.py:20`），修掉 Windows 重定向到 cp936 时含中文的 JSON 变成非 UTF-8 字节的问题。
- **默认 dry-run**：`package nsp` 不加 `--build` 只做计划 + 校验，绝不落 2.9 GB 产物。

## 4. 端到端流水线（2026-10-30 实测）

### 4.1 环境

| 项 | 值 |
| --- | --- |
| 仓库 | `E:/Othergames/Nintendo Switch/Workspace/GalNX`（HEAD `1ad2608` + P3 改动） |
| Python | 3.12.10 + PyYAML 6.0.3 + jsonschema 4.26.0 |
| C 工具链 | devkitPro `D:/devkitPro`（devkitA64 r30-1 / GCC 16.1.0 / libnx 4.12.0） |
| 打包工具 | `E:/galnx-build/m3-tools/nstool.exe`、`.../hacBrewPack-745b16ec.../hacbrewpack.exe`、`D:/devkitPro/tools/bin/{elf2nso,npdmtool,nacptool}.exe` |
| keyset | Ryujinx portable `prod.keys` 12,007 B sha256 `7bb3b6d2…`（只在命令行显式传入） |
| 模拟器 | Citron Nightly `0237a9b88`（Windows x64 / Vulkan） |

### 4.2 命令链

```bash
cd 'E:/Othergames/Nintendo Switch/Workspace/GalNX'
export PYTHONPATH=src

# 0) 前置检查
python -m galnx preflight --manifest examples/pilot01-haruno.yaml

# 1) payload → romfs（UI 资产 + 23 个游戏文件 + game_files.txt + keymap）
python -m galnx payload plan --manifest examples/pilot01-haruno.yaml
python -m galnx payload materialize --manifest examples/pilot01-haruno.yaml \
  --out E:/galnx-build/pilot-01/p3/romfs

# 2) 打包（dry-run 默认；--build 才落盘）
python -m galnx package nsp --manifest examples/pilot01-haruno.yaml \
  --elf E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.elf \
  --romfs-dir E:/galnx-build/pilot-01/p3/romfs \
  --keyset 'E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys' \
  --out E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-010047410000A000.nsp \
  --work E:/galnx-build/pilot-01/p3/build/nsp \
  --nstool E:/galnx-build/m3-tools/nstool.exe \
  --hacbrewpack E:/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c/hacbrewpack.exe \
  --elf2nso D:/devkitPro/tools/bin/elf2nso.exe \
  --npdmtool D:/devkitPro/tools/bin/npdmtool.exe \
  --nacptool D:/devkitPro/tools/bin/nacptool.exe \
  --build --provenance E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-010047410000A000.nsp.PROVENANCE.json

# 3) 复核
python -m galnx package nsp verify \
  --nsp E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-010047410000A000.nsp \
  --manifest examples/pilot01-haruno.yaml \
  --nstool E:/galnx-build/m3-tools/nstool.exe \
  --keyset '.../prod.keys' --provenance '...nsp.PROVENANCE.json' --json
```

### 4.3 各步实测输出

| 步骤 | 结果 |
| --- | --- |
| preflight | 10 项全 OK（manifest.schema、source_dir 48 entries、entry、title_id 0x010047410000A000、target nsp、output_dir、路径长度 26、磁盘 365.2 GiB、prod.keys 12,007 B） |
| payload plan | 15 checks / 0 fail / 1 warn（keymap 未绑定的 show_history/auto_mode/skip_hold）；payload 22 selected + 1 generated = 2,870,635,309 B；ui 85 files 7,551,013 B；romfs 合计 2,878,186,922 B |
| payload materialize | 16 checks / 0 fail / 1 warn；产物 **109 文件 / 2,878,186,922 B** |
| package nsp（dry-run） | 4 steps；8 checks / 0 fail |
| package nsp（--build） | **24 checks / 0 fail / 1 warn**（warn = ACID signature FAIL，未签名 homebrew 预期） |
| package nsp verify | **13 checks / 0 fail / 1 warn / 3 NCAs**（warn 同上；另含 PROVENANCE 交叉校验） |
| nstool | PFS0 FileNum=3；3 NCA 全 ProgID `0x010047410000A000`；Meta 0x1000 / Program 0xad363000 / Control 0x1cc00 |

## 5. 复现 oracle（黄金值）

流水线是否「还在正确的位置」用下表判定。**NSP 整体 sha256 不能作为 oracle**：hacBrewPack 的 RSA-PSS 签名带随机盐，每次构建 NSP 字节都不同（P2 已记录）。要比较的是组件。

| 对象 | 期望值 | 来源 |
| --- | --- | --- |
| payload 文件数 | 23（14 xp3 + haruno.cf + 7 tpm + keymap XML） | `P3e-a3-k2s_log.txt` / PROVENANCE |
| payload 字节数 | 2,870,635,309 | PROVENANCE `inputs.romfs.bytes` 推导 + 解包目录 |
| romfs 文件数 | 109 | materialize / PROVENANCE |
| romfs 字节数 | 2,878,186,922 | materialize / PROVENANCE |
| romfs 最大绝对路径长 | 67 | materialize |
| romfs 汇总哈希 | sha256 `53535c68d81a24d88fbac0a6fce0d710e0592558bc89286b732f88891b7d164e` | PROVENANCE `inputs.romfs.sha256` |
| `game_files.txt` | 600 B / 28 行 / sha256 `0e6757d9901d4a4abb95a220f9d8e1714b0b858c421ec328e6802a10d4e3fd61` | P3-e 实测 |
| keymap XML | 1,293 B / sha256 `aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543` | 黄金样本（P2 起未变） |
| elfs/main | 22,082,152 B / sha256 `91d87fc93f89627d65b7627272a3ee8feadf0c024abcc926ba3386e424ee7b7f` | A2/A3 组件一致 |
| TitleID | `010047410000A000`（base，0x2000 对齐） | manifest |
| NSP | 2,906,131,672 B（每次字节不同，size 稳定） | A3 实测 |

## 6. A3 NSP：构建、结构、验收

### 6.1 构建

- 产物：`E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-010047410000A000.nsp` **2,906,131,672 B sha256 `1f54bdf105fdfc0e88a81e5aaec954ffd4c349132fe7bbadcf394948cde994d4`**
- PROVENANCE：同目录 `.nsp.PROVENANCE.json` 13,862 B（metadata / inputs / tools / keyset 四段；keyset 只记 path/size/sha256 + note `contents intentionally not recorded`）
- 构建阶段日志：`.../p3/build/nsp/logs/{elf2nso,npdm,nacp,hacbrewpack}.log`
- 与 A2 的差异：只换了 TitleID（`010047410000b0b4` → `010047410000A000`）与 NACP version（`1.0.2`），exefs/main 与 romfs 组件逐字节一致。

### 6.2 结构（nstool + verify）

- PFS0 3 文件；3 个 NCA 的 ProgID 均为 `0x010047410000A000`；类型 Program/Control/Meta 齐备。
- `galnx package nsp verify`（带 keyset）：12 项 nstool 检查 + 1 项 summary，0 fail、1 warn（`Signature: FAIL` ×4 行），PROVENANCE 校验通过。
- 无 keyset 时 verify 只能读 PFS0 头（3 warn），因此**复核必须带 keyset**；仓库证据里同时保留两份（`P3e-a3-verify.json` / `P3e-a3-verify-nokeyset.json`）。

### 6.3 Citron 全新 SD 冒烟（Lead，2026-10-30 09:01）

run dir：`workspaces/citron-harness/runs/20261030-090102-Kirikiroid2-NX-010047410000A000`（harness `--detach`）

| 判据 | 实测 |
| --- | --- |
| 启动前断言 | `citron_before=0`；`wiped: kirikiri=absent` |
| 加载 | `status=loaded`，rc=0；窗口标题 `citron Nightly | 0237a9b88 | Haruno (64-bit) | 1.0.2 | NVIDIA`；boot_line `Booting game: 010047410000A000 | Haruno (64-bit) | 1.0.2` |
| 信号 | `title_match` / `boot_line` / `app_output` 均 true；nonblack 0.9018 |
| 首启解包 | `free space check ok: 25425 MiB free for a 2737 MiB payload` → `first boot: copying 23 payload file(s)` → `payload copy finished: 23 copied, 0 kept, 0 failed, 2737 MiB total` |
| autostart | `autostarting game from /kirikiri/haruno/data.xp3` → 09:01:49 startup.tjs → 09:02:27 `title.ks` |
| 手柄 | 10/10 步；RIGHT + C → 09:04:18 `start.ks` → 09:04:22 `@0000A_Z01.ks`；三张 capture 均 ok |
| 收尾 | harness `killed=true`；`citron_after=0` |
| 自包含证明 | NSP 内嵌 payload 解包出 23 文件 / 2,870,635,309 B；marker `pilot01-r2`；keymap XML 来自 NSP 且未被覆写（sha 与内置模板一致） |

### 6.4 NSP 独立 verify（P3-f，audit-package）

由 audit-package 用 `galnx package nsp verify` + 独立 raw `nstool`（不经 GalNX 代码）复核 A3 NSP，记录见 **`docs/pilot/P3-verification.md`**（253 行 / 24,302 B）：

| 项 | 结果 |
| --- | --- |
| CLI verify | `rc=0`，**19 checks = 18 ok + 1 warn**；唯一 warn = `verify.signature`（4 行 `Signature: FAIL`，hacBrewPack RSA 非任天堂密钥，未签名 homebrew 预期） |
| provenance 交叉核对 | 6 项全 ok（artifact size+sha256、keyset size/sha256、no_secret、schema、dry_run=false、title_id） |
| 独立 raw nstool | NSP 层 PFS0 FileNum=3 rc=0；3 个 NCA 逐个 rc=0；Meta `0x1000` / Program `0xad363000` / Control `0x1cc00`；ProgID 全 `0x010047410000a000`；签名 FAIL 合计 4 条与 CLI 一致 |
| romfs oracle | 109 files / 2,878,186,922 B / digest `53535c68…164e`（按 `digest_romfs` 公式独立重算，与 PROVENANCE 一致）；`game_files.txt` 600 B `0e6757d9…`、keymap 1,293 B `aa4fa8aa…` 均匹配；max_path_len **63**（A2 的 67 仅因 romfs 根前缀更长，最长相对路径相同） |
| PROVENANCE 合规 | keyset 段字段恰好 `[mode,path,size,sha256,note]`（real / 12,007 B / `7bb3b6d2…`）；全文 `header_key` 0 次、`key_area_key` 0 次；7 个输入哈希逐个实测 match；5 个 build step 全 exit 0 |
| 构建日志脱敏 | 4 个构建日志 grep 无 `Key area key`；`hacbrewpack.log` 第 294 行被 `<redacted: key material line>` 替换（redacted=1） |
| A2→A3 差异 | TitleID `…b0b4`→`…A000`（A2 被 `validate_base` 拒绝 rc=2）；NSP 大小相同但 sha256 不同（RSA-PSS 随机盐）；`exefs/main` 相同 `91d87fc9…`；npdm `5c2640f2…`→`d7a6d4ff…`；nacp `c5ac3abf…`→`8d02007b…`（Haruno/GalNX/1.0.2）；icon 6,285→9,872 B |

Lead 另用同一 `nsp verify` 命令独立复跑一次（`--keyset` + `--provenance`，输出 `docs/milestones/evidence/P3e-a3-verify-lead.json`）：**19 checks / 18 ok / 1 warn / rc=0**，与 audit-package 结论一致。

### 6.5 Citron 独立冒烟（P3-f，audit-web）

由 audit-web 用同一 NSP 独立重跑「全新 SD 首启 + 手柄进正文」→ **PASS（7/7 判据）**，记录见 **`docs/pilot/P3-smoke-independent.md`**（114 行），证据 `docs/milestones/evidence/P3f-*`（16 文件，15 条 sha256 经 Lead 逐条核对 15/15 吻合）。

| 项 | 实测 |
| --- | --- |
| run dir | `workspaces/citron-harness/runs/20261030-091112-Kirikiroid2-NX-010047410000A000`，`--detach` 父 5 s 返回、`--wait-job` waited_s=224 rc=0、`killed=true` |
| NSP 独立哈希 | `Get-FileHash` = `1F54BDF1…E994D4`、2,906,131,672 B，与 Lead 一致 |
| 运行时 | `status=loaded`；`launch_route=schtasks-limited`；窗口标题 `… | Haruno (64-bit) | 1.0.2 | NVIDIA`；boot 行 `010047410000A000`；signals 三真；`elapsed_s=37` |
| 首启解包 | `first boot: copying 23 payload file(s)` → `23 copied, 0 kept, 0 failed, 2737 MiB`；盘上 23 文件 = 2,870,635,309 B（命中 oracle）；keymap sha256 命中 `aa4fa8aa…` |
| 剧情推进 | 09:12:33 `title.ks` → 09:14:25 `start.ks` → 09:14:29 `@0000A_Z01.ks`；三截图 nonblack 0.9018 / 0.9018 / 0.9017；steps 10/10 ok，`steps_diff_ratio=0.809225` |
| 与 Lead run 差异 | 三张截图 MAD 0.142 / 0.153 / 0.149（0–255），差值 >8 的像素 <0.2% → 帧相位与打字机进度差异，内容一致 |

过程注记（写入限制）：①独立复跑在 wipe 清单外**额外**删了 `sdmc/switch/kirikiroid2/.preference/`（K2NX 文件选择器历史路径），避免选择器记忆造成伪首启 —— 以后 wipe 清单应纳入；②key 注入时 `result.json focus_ok=false`，但 `keys_sent=1` 且三次均生效（PostMessage 不依赖前台焦点）→ **不得把 focus_ok 当输入成功判据**，判据看 steps/k2s/截图。

## 7. 适配器层级：builtin vs overlay

P3 决定 **`kirikiroid2-nx` 暂不升级为 builtin 适配器**，保持「overlay 示例」：

- **builtin**（`src/galnx/engines/registry.py` 的 `BUILTIN_ENGINES`）：可分发、许可清晰、无外部二进制/无 keys 依赖的适配器，随仓库一起测试。当前 3 个：`brewser`（MPL-2.0 / web / prebuilt）、`krkrsdl2`（MIT / nro / cmake-switch）、`onscripter-nx`（GPL-2.0-or-later / nro / devkitpro-make）。
- **overlay**：第三方/试点适配器，通过 manifest 的 `engine.descriptor` 指向仓库内 YAML（如 `examples/engines/kirikiroid2-nx.yaml`）显式启用，不进入 `galnx engines list` 的 builtin 集合。

理由：K2NX 属第三方上游（KiriKiri BSD-style + FFmpeg/OpenCV/UnRAR 依赖、许可 NOASSERTION），升 builtin 会把「不可再分发的构建前置」写进默认真值；且改动会牵动 3 处硬编码 builtin 断言测试。manifest 的 `adapter` 枚举里已含 `kirikiroid2-nx`，overlay 路径不改用户 API。

## 8. TitleID 必须 base 对齐（P3 新硬约束）

P2 的 A2 用了 `010047410000b0b4`，结构上能跑，但按 TitleID 规则低 13 位 `0x10B4` 落在 DLC 区（`base | 0x1000 | index`），正式发布/真机安装会出问题。P3 的 `validate_base()` 直接拦：

```
title id 010047410000B0B4 is an add-on content id (base | 0x1000 | index);
allocate the base id instead
```

规则（`src/galnx/package/titleid.py`）：base 低 13 位必须为 0（0x2000 对齐）、update = `base | 0x800`、DLC = `base | 0x1000 | index`；GalNX 试点分配块 `0x0100474100000000–0x01004741FFFFFFFF`。A3 使用 `010047410000A000`（合规 base，`4C4E`/`LN` 为分配语义标签）。

A2 保留为**历史证据与反例**，不再作为交付产物。

## 9. Harness 必须脱离调用方进程树（R14，决策 16）

P2 及 P3 早期出现过「harness 打印 launched 后 ~27 s 静默退出、Citron 仍在跑、无 result.json」的假失败。根因两条：

1. **进程树**：elevated shell 启动的 bash → Citron 由 runas/Task Scheduler 降权启动，脱离调用方进程树；调用方（DSH run_code / job）回收进程树时打断 harness 轮询。
2. **陈旧日志假阳性**：`citron_log.txt` 复用上一轮内容，上轮 `BootGame` 行会被当成本轮证据。

修法（`scripts/citron_run.sh`，`docs/environment/citron-harness.md` §15）：

- `--detach`：用 WMI `Win32_Process.Create` 建**脱离**的 Windows 进程跑 harness，父进程 5 s 内返回 `{run_dir,harness_pid,launcher_pid,...}`；
- `--wait-job <run_dir> [--wait-timeout]` / `--status <run_dir>`：查 `.done` 与 `result.json`，退出码 0/1/2；
- 日志基线：记 `LOG_BASE_SIZE/MTIME`，未变则丢弃 boot 证据并报 `citron_not_started: ... (launch_route=...)`；
- `launch_route` 三值：`direct` / `runas-deelevated` / `schtasks-limited`（08:1x 起 runas 路由静默失效，已改 Task Scheduler）。

**使用约束：Citron run 一律 `--detach`，禁止前台长跑。** 本轮 A3 冒烟与 P3-d 回归均按此执行。

## 10. 限制与风险

| # | 限制/风险 | 影响 | 现状 / 缓解 |
| --- | --- | --- | --- |
| R1 | jxrlib 上游 master 未 pin | 重建可能漂移 | P3 已知风险，记录在 descriptor `portlibs`；后续 pin commit |
| R2 | NSP 非确定性（RSA-PSS 随机盐） | 无法用 NSP 哈希做复现 oracle | 用组件哈希（§5）；size 稳定 |
| R3 | 2.9 GB NSP / FAT32 4 GiB 上限 | 真机拷贝/安装受限 | 当前 < 4 GiB；更大游戏需 exFAT 或数据外置策略 |
| R4 | Citron 单实例转发 | 并发 run 会混跑同一进程 | 「申请-释放」+ 启动前 `tasklist` 断言 0 实例 |
| R5 | 真机未验证 | 完成标准只到模拟器 | P4 待用户设备（Atmosphère + sigpatches） |
| R6 | NSP 形态鼠标注入无效（NRO 有效） | 触摸/鼠标路径受限 | 与引擎无关，手柄路径已验收；记录 P2 限制 |
| R7 | 存档/读档、音频未验证 | 体验完整性未知 | P4 或后续专项 |
| R8 | 键材料策略 | 仓库/CI 不可含 keys | 只显式 `--keyset`；PROVENANCE 只记元数据；证据扫描无密钥 |
| R9 | Windows 259 B 路径上限 | romfs 深路径可能失败 | materialize 已报 max path；109 文件实测 67 |
| R10 | `engines prepare` 不支持 prebuilt 后端 | 预编译上游不能走 prepare | 显式报错；预编译产物走 `package nsp` 的 ELF 合成路径（P1 脚本保留） |

## 11. 证据索引

| 证据 | 内容 |
| --- | --- |
| `docs/milestones/evidence/P3a-*` | payload CLI verify/plan 输出 + sha256 清单 |
| `docs/milestones/evidence/P3c-*` | engines prepare check-only 输出（两次逐字节相同）+ 补丁 + sha256 清单 |
| `docs/milestones/evidence/P3d-*` | harness `--detach` 回归 + R14 复现 + 失败用例 |
| `docs/milestones/evidence/P3e-*` | A3 构建/verify/PROVENANCE、Citron 冒烟 result/截图/k2s/marker/keymap、sha256 清单（25 文件） |
| `docs/milestones/evidence/P3f-*` | A3 独立冒烟（P3-f，audit-web） |
| `docs/builds/009-k2nx-selfcontained-build.md` | K2NX 源码构建全链路（portlibs、补丁、Windows 坑） |
| `docs/packaging/payload.md` / `docs/packaging/nsp-build.md` | 模块级 API 与校验语义 |
| `docs/pilot/P3-verification.md` | A2/A3 独立 verify 与差异表 |
| `docs/pilot/P3-smoke-independent.md` | A3 Citron 独立冒烟（P3-f）7/7 判据 + 与 Lead run 差异 |

## 12. 状态与后续

- **P3 完成判定**：CLI 一条命令链复现 ✅；A3 合规 NSP ✅；Citron 全新 SD + 手柄冒烟 ✅（Lead，§6.3）；**NSP 独立 verify ✅**（P3-f，`P3-verification.md`）；**Citron 独立冒烟 ✅**（P3-f，`P3-smoke-independent.md`，7/7）；全量测试 600 passed ✅ → **P3 全部完成**。
- **已知未覆盖面**：真机（P4）、存档/音频、NSP 形态鼠标、`engines prepare` 的 prebuilt 分支、jxrlib pin。
- **P4 前置**（真机，待用户设备）：Atmosphère 1.12.1 + sigpatches、exFAT SD、NSP 安装方式（DBI/Goldleaf）、物理手柄复测。
- **后续工程化**（deferred）：`galnx package nsp` 纳入 `galnx build run` 缓存、CI、GUI。
