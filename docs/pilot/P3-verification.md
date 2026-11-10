# P3-f：A3 合规 TitleID 自包含 NSP 独立复核（P3 验证文档）

- 任务：task-45（P3-f；P3 验证文档新建，audit-package 独占写权）
- 日期：2026-10-30（Asia/Shanghai）
- 作者：audit-package
- 状态：**已完成——A2 反例（§3）+ A3 正式复核（§4）全部回填；结论见 §4.4**
- 边界：只读验证；不改代码、不 commit、不启动 Citron（Citron 冒烟由 Lead 统一跑，本文只读引用其结果）；keyset 只用显式路径传入，只记录 path/size/sha256，不读取/打印/复制内容；原始输出只落 `.cache/verification-p3/`（gitignored），文中只引用关键行与哈希。

---

## 0. 结论摘要（A3 复核完成）

| # | 结论 | 证据 |
| --- | --- | --- |
| 1 | **A3 TitleID 合规**：`010047410000A000` 低 13 位 = 0 → `classify()==BASE`，且为 0x2000 的倍数；plan `rc=0`、errors=0。 | §4.2 V1 |
| 2 | **容器与 NCA 结构合法**：nstool NSP 层 rc=0、PFS0 FileNum=3；三个 NCA = Program 2,906,009,600 B / Control 117,760 B / Meta 4,096 B，ProgID 全为 `0x010047410000A000`。 | §4.2 V3/V4 |
| 3 | **签名 FAIL 归 warn**：4 条 `Signature: FAIL`（3× NCA Header Main + 1× ACID）均记录为 verify.signature warn——未签名 homebrew 的预期现象，不是缺陷。 | §4.2 V5 |
| 4 | **provenance 自洽**：schema `galnx-nsp-provenance`/v1、`dry_run=false`；keyset 仅 `[mode,path,size,sha256,note]`（real / 12,007 B / `7bb3b6d2…`）；文本 13,501 B 内 `header_key`/`key_area_key` 计数均 0；inputs（elf/romfs/icon/npdm_template）与 5 个工具的哈希逐个实测一致；artifact size+sha256 与实际 NSP 一致。 | §4.2 V7/V8 |
| 5 | **romfs 对齐 oracle**：109 文件 / 2,878,186,922 B；romfs digest `53535c68…`（独立重算，A2 同）；`game_files.txt` 600 B / `0e6757d9…`；keymap 1,293 B / `aa4fa8aa…`；max path 63（A3 根前缀比 A2 短 4 字符，最长相对路径相同）。 | §4.2 V9 |
| 6 | **NACP/NPDM 元数据实测**：name=Haruno（lang[0..11]）、author=GalNX、display_version=1.0.2、startup_user_account=1、save_data_owner_id=`0x010047410000A000`、add_on_content_base_id=`0x010047410000B000`；NPDM title id 位于偏移 832（0x340）=A000；与 provenance/NPDM/ProgID 自洽。 | §4.2 附加 |
| 7 | **V10 可加载（Lead 执行，本文只引用）**：Citron 加载 A3 NSP 成功——`status=loaded`、boot line `Booting game: 010047410000A000 \| Haruno (64-bit) \| 1.0.2`、38 s、标题/开始/推进三张截图、`steps_failed=0`。 | §4.2 V10 |
| 8 | **结论：A3 满足 P3 验收标准**（V1–V10 全过，仅签名 warn 属预期）；A2（b0b4）作为反例留档，P3 验收以 A3 为准。 | §4.4 |

**一句话**：A3 是「合规 TitleID + CLI 管线 + 可核对 provenance」的验收产物；A2 是「非合规 TitleID + 无 provenance」的历史反例，只用于证明验证器能抓出问题。

---

## 1. 验证目标与验收标准

目标：独立复核 Lead 用 GalNX CLI 管线产出的 A3 自包含 NSP（TitleID 为合规 base），确认其结构、元数据、romfs 内容与 provenance 可复现，且不依赖 Lead 的临时脚本。

| # | 验收项 | 通过标准 | 证据形态 | 当前状态 |
| --- | --- | --- | --- | --- |
| V1 | plan 合规 | TitleID `classify()==BASE` 且 0x2000 对齐；plan errors=0；plan checks 无 fail | plan JSON + 本文 §4.2 | 已通过 |
| V2 | 构建完成 | 4 steps（elf2nso→npdm→nacp→hacbrewpack）exit 0；产物存在且 >0 B | provenance build 段 + 步骤日志 | 已通过 |
| V3 | 容器结构 | nstool NSP 层 rc=0；PFS0 Type/FileNum=3 | 原始 nstool 输出 | 已通过 |
| V4 | NCA 结构 | 3 个 NCA：Program/Control/Meta 齐全；ProgID 全等且 == `0x010047410000A000` | verify checks | 已通过 |
| V5 | 签名预期 | `Signature: FAIL` 仅记为 warning（未签名 homebrew，不是缺陷） | verify.signature | 已通过（warn） |
| V6 | verify 汇总 | verify 无 fail；summary ok | verify checks | 已通过 |
| V7 | provenance | schema=galnx-nsp-provenance/1；`dry_run=false`；keyset 只含 path/size/sha256=12,007 B/`7bb3b6d2…`；无任何密钥内容；tools/inputs/commands 完整 | provenance JSON 关键字段 | 已通过 |
| V8 | 日志脱敏 | build 日志与 provenance 中无 `Key area key` 原文（grep 计数=0） | 日志文件 | 已通过 |
| V9 | romfs 对齐 oracle | 109 文件 / 2,878,186,922 B；`game_files.txt` 600 B sha256 `0e6757d9…`；keymap 1,293 B sha256 `aa4fa8aa…` | romfs inventory + 文件哈希 | 已通过 |
| V10 | 可加载性 | 自包含 NSP 可直接加载（Citron 冒烟由 Lead 执行后引用其结果；本文不改判定） | Lead 的 Citron 运行记录 | 已通过（Lead 执行） |

> 说明：V1 的 plan checks 由 8 项扩容为 10 项（新增 `nsp.out_path`/`nsp.work_dir` 重跑检查）；A3 实测 10 项 = 8 ok + 2 warn（out 已存在、work 非空，属重跑预期，非缺陷）。verify 阶段回归由 CLI 独立子命令 `galnx package nsp verify` 执行（本次实现并跑通，见 §2）。

---

## 2. 方法与工具

| 项 | 值 |
| --- | --- |
| Python | 3.12.10（`D:\Scoop\apps\python312\current\python.exe`） |
| 验证入口 1 | CLI 独立子命令 `galnx package nsp verify`（本次在 `src/galnx/package/nsp.py` 新增；argparse harness 为 `.cache/packaging-testing/run_nsp_cli.py`，挂在 `nsp.register()` 上） |
| 验证入口 2 | Python API `galnx.package.nsp.verify_nsp()`（与 CLI 同一实现），**不复用** `build_a2.sh` / `build_pilot_nsp.sh` |
| 独立旁证 | ① raw nstool 直接读 NSP 与三个 NCA（不经 GalNX 代码）；② 按 `/d/devkitPro/libnx/include/switch/nacp.h` 结构独立解析 NACP/NPDM；③ 按 `nsp.py` `digest_romfs()` 公式独立重算 romfs digest；④ provenance 文本扫描（密钥关键字计数）；⑤ build 步骤日志扫描（`Key area key` 计数） |
| nstool | v1.9.2（`E:/galnx-build/m3-tools/nstool.exe`，MIT，commit e89ea84b） |
| keyset | `E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys`，12,007 B，sha256 `7bb3b6d2a2eedc83c9f244ee2ed2eaa4d59eb9ad95b66df575f7dfffa71a2a40`（显式传入；只记录元数据） |
| 复核脚本 | `.cache/verification-p3/a3_facts.py`（A3 哈希/romfs/provenance 采集）、`.cache/packaging-testing/run_nsp_cli.py`（CLI harness）；A2 反例用 `a2_counterexample.py` |
| 工作目录 | `.cache/verification-p3/`（gitignored，`.gitignore:2:.cache/`） |
| 约束 | 不启动 Citron、不改仓库代码、不读取 keys 内容、不 commit |

CLI verify 实际命令（`PYTHONUTF8=1` 必须：`json.dumps(ensure_ascii=False)` 假定 UTF-8 stdout）：

```bash
cd '/e/Othergames/Nintendo Switch/Workspace/GalNX'
PYTHONUTF8=1 python .cache/packaging-testing/run_nsp_cli.py nsp verify \
  --nsp 'E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-010047410000A000.nsp' \
  --manifest examples/pilot01-haruno.yaml \
  --nstool 'E:/galnx-build/m3-tools/nstool.exe' \
  --keyset 'E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys' \
  --provenance 'E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-010047410000A000.nsp.PROVENANCE.json' \
  --work-dir .cache/verification-p3/work-a3-verify --json
# rc=0
```

独立 raw nstool 调用形态（旁证，不经 GalNX 代码）：

```bash
# NSP 容器层
nstool -y -k <prod.keys> <A3.nsp>
# 抽取 NCA（输出目录在 .cache）
nstool -x .cache/verification-p3/a3-nca -k <prod.keys> <A3.nsp>
# NCA 层逐个校验（Program / Control / Meta）
nstool -y -k <prod.keys> .cache/verification-p3/a3-nca/<nca>
```

---

## 3. A2 反例（known-issue）✔ 已取证

对象：`E:/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b4.nsp`
大小 2,906,131,672 B；sha256 `eb6c6a15151c2a5936c6549eebb26ca25a059744f0136cb5b8cce773fd9c705f`；mtime 2026-10-30 07:34:52。该文件是 `build_a2.sh`（shell）产出、**不经 GalNX driver** 的历史产物。

### 3.1 计划阶段：TitleID 不合规，rc=2

命令（等价于 `galnx package nsp --dry-run --json`，用 `.cache/packaging-testing/a2-dryrun-b0b4.manifest.yaml`，title_id=b0b4）：

```bash
PYTHONUTF8=1 python .cache/packaging-testing/run_nsp_cli.py nsp \
  --manifest .cache/packaging-testing/a2-dryrun-b0b4.manifest.yaml \
  --elf E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.elf \
  --romfs-dir E:/galnx-build/pilot-01/nsp/romfs-a2 \
  --keyset 'E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys' \
  --dry-run --json
# rc=2
```

结果（`.cache/verification-p3/a2-b0b4-plan.json`）：

- `ok=false`，`plan.ok=false`，`plan.steps=[]`（0 steps）。
- errors 唯一一条：`field=title_id`，`message="title id 010047410000B0B4 is an add-on content id (base | 0x1000 | index); allocate the base id instead"`，severity=error。
- checks：`nsp.title_id=fail`、`nsp.plan=fail`（detail `0 steps, 1 error(s), 0 warning(s)`），其余 7 项 ok（nsp.romfs 109 files/2.7 GiB/max path 67、nsp.keyset.mode、5 个工具 nsp.tool.*）。
- 根因（源码）：`src/galnx/package/titleid.py:138-145` 按低 13 位分类，`low>=DLC_OFFSET(0x1000)` → DLC；`validate_base()` `titleid.py:259-261` 对 DLC 报上述 error。b0b4 的 `0xB0B4 & 0x1FFF = 0x10B4`。规则来源见 `titleid.py:1-24` docstring（gbatemp wiki：base 以 Y000 结尾、0x2000 倍数）。

### 3.2 结构验证：expected 不符按预期 fail

用 driver API `verify_nsp(A2.nsp, nstool, keyset=<explicit>, expected_title_id="010047410000A000", work_dir=.cache/verification-p3/work-a2)`（A2 的 ProgID 是 b0b4，故意用 A3 的合规 expected 验证比对逻辑）：

| 项 | 结果 |
| --- | --- |
| nstool NSP 层 | rc=0；输出 `[PartitionFs] Type: PFS0 / FileNum: 3`；stderr 空 |
| NCA 数量 | 3（抽取到 work-a2/nstool-nca，verify 总耗时 5.49 s） |
| Program NCA | 2,906,009,600 B（0xad363000），Content Type Program，ProgID `0x010047410000b0b4` |
| Control NCA | 117,760 B（0x1cc00），Content Type Control，ProgID `0x010047410000b0b4` |
| Meta NCA | 4,096 B（0x1000），Content Type Meta，ProgID `0x010047410000b0b4` |
| 签名 | 4 条 `NCA Header Main Signature: FAIL`（+ACID FAIL）→ verify.signature=warn（未签名 homebrew 预期） |
| verify checks | 共 13 项：10 ok、1 warn（signature）、2 fail（`nstool.progid.expected`、`verify.summary`） |
| fail 原因 | `ProgID 0x010047410000B0B4 does not match expected 0x010047410000A000` |

结论：容器与 NCA 结构合法，验证器按 expected=合规 A000 正确报 fail；该 fail **来源于 A2 的 b0b4**，不是结构缺陷。

### 3.3 known-issue 清单（A3 收口状态见 §3.4）

1. **A2 TitleID 不合规**：`010047410000b0b4` 被判 DLC，不能作为正式产物；P3 验收改用合规 base（如 `010047410000A000`）。A2 仅作历史证据。
2. **A2 无 provenance**：shell 脚本产出，缺少 schema/provenance/日志脱敏链路；无法做 V7/V8 核对。
3. **A2 NSP 哈希非确定**：hacBrewPack 用 RSA-PSS + 随机盐，同输入重建 NSP hash 会变；`eb6c6a15…` 只标识本次文件，A3 也不以 NSP hash 比较。
4. **签名 FAIL 非缺陷**：未签名 homebrew 的预期行为；只有 Atmosphère + sigpatches 真机环境才需另行处理。
5. **v0.1 期间 A2 曾被当作「已验收」使用**：本反例证明「自家校验器会拒绝自家产物」，正式流程必须让产物经 driver 校验（P3-e 集成后成为硬门槛）。

### 3.4 收口：A3 对 known-issue 的处置

| # | issue | A3 状态 |
| --- | --- | --- |
| 1 | A2 TitleID 不合规 | **已解决**：A3 用 `010047410000A000`（BASE、0x2000 对齐），plan rc=0；见 §4.2 V1 |
| 2 | A2 无 provenance | **已解决**：A3 由 CLI 管线产出 `<out>.PROVENANCE.json`（13,862 B / sha256 `8338e2df…`），字段与实测逐项一致；见 §4.2 V7 |
| 3 | NSP 哈希非确定 | **仍成立（限制，非缺陷）**：A3 与 A2 大小同为 2,906,131,672 B 但 sha256 不同；版本锁定用组件哈希，不用 NSP hash |
| 4 | 签名 FAIL 非缺陷 | **仍成立（预期）**：A3 同样 4 条 Signature FAIL → warn；见 §4.2 V5 |
| 5 | A2 曾当「已验收」用 | **已收口**：A3 走 CLI plan→build→verify 全链路，验收以 A3 为准；A2 降级为反例 |

---

## 4. A3 正式复核（已完成）

### 4.1 前置输入（Lead 已提供，逐项实测）

| 输入 | 值 |
| --- | --- |
| A3 NSP | `E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-010047410000A000.nsp`；2,906,131,672 B；sha256 `1f54bdf105fdfc0e88a81e5aaec954ffd4c349132fe7bbadcf394948cde994d4` |
| A3 provenance | 同目录 `Kirikiroid2-NX-010047410000A000.nsp.PROVENANCE.json`；13,862 B；sha256 `8338e2df1b4efd2dada7fbd516d608aa193b2f1994065b14b2aaab9b575bb014` |
| 构建日志 | `E:/galnx-build/pilot-01/p3/a3-build.log`（10 B，内容 `A3_EXIT=0`）+ `E:/galnx-build/pilot-01/p3/build/nsp/logs/`（4 个步骤日志） |
| manifest | `examples/pilot01-haruno.yaml`（3,223 B；`switch.title_id=010047410000A000`；engine.adapter=kirikiroid2-nx；package.type=self_contained_nsp；romfs_dir=E:/galnx-build/pilot-01/p3/romfs；icon=examples/pilot01/icon.jpg；startup_user_account=1） |
| ELF | `E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.elf`；113,874,760 B；sha256 `4b4515837d0239ee2e7448dd5dbed65e8fdda72c37fb0bac0d0dd10ef849b882`（P3 复用，不重建） |
| romfs | `E:/galnx-build/pilot-01/p3/romfs`；109 files / 9 dirs / 2,878,186,922 B；digest `53535c68d81a24d88fbac0a6fce0d710e0592558bc89286b732f88891b7d164e` |
| keyset | `prod.keys` 12,007 B；sha256 `7bb3b6d2…`（只记录元数据） |
| Citron 记录 | `workspaces/citron-harness/runs/20261030-090102-Kirikiroid2-NX-010047410000A000/`（Lead 执行，本文只读引用） |

### 4.2 验收执行表（实测）

| 项 | 实测 | 判定 |
| --- | --- | --- |
| V1 plan checks | `rc=0`、`ok=true`、`errors=[]`；title_id=A000；romfs 109/9/2,878,186,922 B、max_path_len=63；keyset real 12,007 B；4 steps；checks 10 项 = 8 ok + 2 warn（`nsp.out_path` already exists、`nsp.work_dir` non-empty——A3 产物/工作目录已存在所致，重跑预期）。证据 `.cache/verification-p3/a3-plan.json` | 通过 |
| V2 build steps / 产物 | provenance `build.ok=true`、`duration_s=180.688`；steps exit 全 0：stage-icon 0.0 s、elf2nso 0.406 s、npdm 0.156 s、nacp 0.125 s、hacbrewpack 175.032 s；产物 2,906,131,672 B / `1f54bdf1…`；`a3-build.log=A3_EXIT=0` | 通过 |
| V3 nstool NSP 层 | `nstool -y -k <keyset> <A3.nsp>` rc=0；`[PartitionFs] Type: PFS0 / FileNum: 3`（stderr 仅 `Failed to load "title.keys"` 警告，预期） | 通过 |
| V4 NCA 类型 / ProgID | 抽取 3 个 NCA（rc=0）：Program 2,906,009,600 B（0xad363000）/ Control 117,760 B（0x1cc00）/ Meta 4,096 B（0x1000）；三者 Format Type NCA3 / Dist. Type Download / Key Generation 0 / Sig. Generation 0 / Kaek Index Application(0) / SdkAddon 0.12.17 (v790784)；ProgID 全 `0x010047410000a000`；`nstool.progid.consistent=ok`、`nstool.progid.expected=ok` | 通过 |
| V5 签名 warn | 三个 NCA 分别 1/2/1 条 `NCA Header Main Signature: FAIL`（Program 另加 `ACID Signature: FAIL`）→ 合计 4 条 `Signature: FAIL`；verify.signature=warn（detail: expected for unsigned homebrew NSP） | 通过（warn 预期） |
| V6 verify summary | CLI `nsp verify` `rc=0`、`ok=true`、`errors=[]`；**19 checks = 18 ok + 1 warn + 0 fail**：verify.nstool.nsp ok、partition.type/files ok、nca.0/1/2 ok、nca.type.* ok、progid.consistent/expected ok、verify.signature warn、verify.summary ok（`12 checks: 0 fail, 1 warn, 3 NCAs`）、provenance 6 项（schema/dry_run/title_id/artifact/keyset/no_secret）全 ok。证据 `.cache/verification-p3/a3-verify.json`（8,919 B） | 通过 |
| V7 provenance keyset 元数据 | keyset 字段恰好 `[mode,note,path,sha256,size]`（real / 显式路径 / 12,007 / `7bb3b6d2…`）；`dry_run=false`；schema `galnx-nsp-provenance`/v1；inputs ninja：elf `4b451583…`、romfs `{files:109,total_bytes:2878186922,sha256:53535c68…}`、icon 9,872 B/`7f6b9027…`、npdm_template 5,217 B/`ba4775e7…`（npdm/nacp 为生成式，字段为空属预期）；5 个工具哈希逐个实测一致（elf2nso 94,720/d41476f5…、npdmtool 106,496/7fbce929…、nacptool 74,240/d899dd37…、hacbrewpack 508,983/5623fd2b…、nstool 1,050,112/`844648190…`）；artifact size+sha256 与实际 NSP 一致 | 通过 |
| V8 日志脱敏 | build/nsp/logs 4 文件（elf2nso 297 B、npdm 927 B、nacp 314 B、hacbrewpack 17,605 B）`Key area key`/`key_area_key` 计数=0；`hacbrewpack.log` 第 294 行为 `<redacted: key material line>`（脱敏 1 行）；provenance 文本 13,501 B 中 `header_key`=0、`key_area_key`=0（prod.keys 路径出现 3 次，属允许的 path 元数据） | 通过 |
| V9 romfs oracle | 109 files / 9 dirs / 2,878,186,922 B；max_path_len=63（`E:\galnx-build\pilot-01\p3\romfs\Default\SliderNode_Disable.png`；A2 为 67 仅因根前缀多 4 字符）；max file 717,704,696 B（game/voice02.xp3）；独立重算 digest `53535c68…` = provenance `inputs.romfs.sha256`；`game_files.txt` 600 B / `0e6757d9…`；keymap（game/Kirikiroid2Preference.xml）1,293 B / `aa4fa8aa…` | 通过 |
| V10 Citron 可加载（Lead） | result.json：`status=loaded`、`elapsed_s=38`、`pid=25096`、`citron_build=main-0237a9b88`；window_title `citron Nightly \| 0237a9b88 \| Haruno (64-bit) \| 1.0.2 \| NVIDIA`；boot_line `Booting game: 010047410000A000 \| Haruno (64-bit) \| 1.0.2`；signals（title_match/boot_line/app_output）全 true；输入序列 3 张截图（标题/开始/推进）`steps_failed=0`、`steps_diff_ratio=0.809225` | 通过（Lead 执行，本文引用） |
| 附加：NACP 元数据 | 16,384 B / `8d02007b…`：lang[0..11] name=Haruno、author=GalNX（12 组非空，lang[12..15] 空）；display_version="1.0.2"；startup_user_account=1；save_data_owner_id=`0x010047410000A000`；add_on_content_base_id=`0x010047410000B000`（=title\|0x1000）；supported_language_flag=0xbff | 通过（自洽） |
| 附加：NPDM | 972 B / `d7a6d4ff…`；title id A000 位于偏移 832（0x340）；与 NACP owner id、ProgID 一致 | 通过（自洽） |

### 4.3 与 A2 的差异表（已回填）

| 项 | A2 | A3 | 说明 |
| --- | --- | --- | --- |
| TitleID | `010047410000b0b4`（DLC，不合规） | `010047410000A000`（BASE，0x2000 对齐） | b0b4 低 13 位 0x10B4≥0x1000 → DLC；A000 低 13 位 0 |
| 构建方式 | shell `build_a2.sh` 直接调 hacBrewPack（无 driver） | GalNX CLI `package nsp --build`：plan→4 steps→verify→provenance | A3 走 P3-e 集成链路，带完整 provenance |
| NSP 大小 / sha256 | 2,906,131,672 B / `eb6c6a15…` | 2,906,131,672 B / `1f54bdf1…` | 大小相同因三分区尺寸一致；非确定性，不跨构建比 hash |
| exefs/main | 22,082,152 B / `91d87fc9…` | 同（P3 复用同一 r2 ELF） | elf2nso 产物 |
| NPDM | 972 B / `5c2640f2…`（title id b0b4 @832） | 972 B / `d7a6d4ff…`（A000 @832） | 仅 title id 不同 |
| NACP | 16,384 B / `c5ac3abf…`；name=Kirikiroid2-NX / author=GalNX pilot / 1.0.1 / owner b0b4 / aoc base `0x010047410000C0B4` | 16,384 B / `8d02007b…`；name=Haruno / author=GalNX / 1.0.2 / startup 1 / owner A000 / aoc base `0x010047410000B000` | 元数据随 manifest 更新 |
| icon | 6,285 B / `0b942950…` | 9,872 B / `7f6b9027…`（`examples/pilot01/icon.jpg`） | A3 用仓库内 256×256 JPEG |
| romfs 汇总 | 109 文件 / 2,878,186,922 B / max path 67；digest `53535c68…` | 109 / 2,878,186,922 B / max path 63；digest `53535c68…` | 同一份数据（max path 仅根前缀差 4 字符） |
| NCA 摘要 | Program 2,906,009,600 / Control 117,760 / Meta 4,096（ProgID b0b4） | 同尺寸（ProgID A000） | nstool 层一致 |
| verify 结果 | 13 checks：10 ok / 1 warn / 2 fail（expected 比对 + summary） | 19 checks：18 ok / 1 warn / 0 fail | 签名 warn 保留 |
| provenance | 无 | 13,862 B / `8338e2df…` | 可核对输入/工具/产物 |
| 结论 | 历史反例，不作为验收 | P3 验收产物（V1–V10 通过） | 验收以 A3 为准 |

### 4.4 最终结论

- **自包含 NSP 是否可直接加载：是**（依据 Lead 的 Citron 运行记录：`status=loaded`、boot line 含 `Booting game: 010047410000A000 | Haruno (64-bit) | 1.0.2`、38 s 内进入标题/开始/推进截图且 `steps_failed=0`）。本文只引用该记录，不代替他人复跑。
- **是否满足 P3 验收：是**——V1–V10 全部通过（§4.2）；唯一 warn 是「4 条签名 FAIL」，属未签名 homebrew 预期（§3.3 issue 4），不计 fail。
- **未验证项 / 限制**：
  1. 真机（Atmosphère + sigpatches）装载未测（本轮范围外）；
  2. DBI/MTP 安装 2.9 GB 的耗时与失败模式未测；
  3. NACP 语言槽仅 lang[0..11] 非空（devkitPro `nacptool` 默认行为），未逐字段对照 NACP 规范；
  4. Citron 为模拟器，非真机证据；
  5. NSP 哈希非确定（RSA-PSS 随机盐），版本锁定须用组件哈希（ELF/romfs digest/icon/provenance）。

---

## 5. 证据文件索引（`.cache/verification-p3/`，gitignored）

| 文件 | 内容 |
| --- | --- |
| `a2_counterexample.py` | A2 反例复核脚本（哈希/verify/抽取/NCA 层） |
| `a2-counterexample.json` | A2 反例结构化结果（NSP/三个 NCA 元数据、13 checks） |
| `a2-nstool-nsp.log` | A2 NSP 层原始 nstool 输出（rc=0，PFS0/FileNum 3） |
| `a2-nstool-nca-0/1/2.log` | A2 三个 NCA 层原始 nstool 输出（Program/Control/Meta，签名 FAIL） |
| `a2-b0b4-plan.json` / `.err.log` | plan 拒绝证据（rc=2，title_id DLC error） |
| `work-a2/nstool-nca/*.nca` | A2 抽取出的三个 NCA（约 2.9 GB，仅本地缓存） |
| `a3_facts.py` / `a3-facts.json` | A3 采集脚本与汇总（NSP/provenance/romfs/组件哈希） |
| `a3-plan.json` / `a3-plan.log` | A3 manifest 真实 dry-run（rc=0，10 checks：8 ok + 2 warn 重跑预期） |
| `a3-verify.json` / `a3-verify.log` | CLI `nsp verify` 输出（rc=0，19 checks：18 ok + 1 warn；log 0 B） |
| `a3-nstool-nsp.log` | A3 NSP 层原始 nstool 输出（102 B，rc=0） |
| `a3-nstool-extract.log` | 抽取 3 个 NCA 的 nstool 输出（364 B，rc=0） |
| `a3-nstool-nca-*.log` | 三个 NCA 层原始 nstool 输出（390/473/394 B，签名 FAIL） |
| `a3-nca/*.nca` | A3 抽取出的三个 NCA（约 2.9 GB，仅本地缓存） |
| `work-a3-verify/` | CLI verify 的 NCA 抽取工作目录（`--work-dir` 显式保留） |

---

## 6. 风险与限制

1. **keyset 合规**：prod.keys 仅作显式输入，本文只记录 path/size/sha256；任何日志/文档不得出现密钥内容（V8 已核：4 个 build 日志与 provenance 均无明文，日志中 1 行密钥区被替换为 `<redacted: key material line>`）。产物不入库、不进 CI。
2. **NSP 非确定性**：版本锁定用组件哈希（ELF/romfs digest/icon/provenance），不用 NSP hash。
3. **Citron 验证归 Lead**：本文只读引用 Lead 的运行记录，不代判「可加载」；真机（Atmosphère + sigpatches）不在本轮范围。
4. **nstool 视角限制**：NCA 层签名 FAIL 无法区分「预期未签名」与「结构损坏」，故以 Content Type/ProgID/Size 与 rc 为准。
5. **romfs 变更风险**：若 Lead 后续换 romfs，V9 需按新 oracle 重算（本次 A3 digest 与 A2 相同，说明数据同源未变）。
6. **verify 子命令已具备**：`galnx package nsp verify` 已实现并跑通；NCA 抽取需约 2.9 GB 临时磁盘（默认 `tempfile.mkdtemp` 用完即删，本次用 `--work-dir` 保留作证据）。
7. **NACP 语言槽**：12 个语言槽非空、4 个空是 devkitPro `nacptool` 默认行为，未逐字段对照规范；如需严格多语言元数据需另做填充。

---

## 7. 状态与下一步

- 当前：**task-45 完成**——本文 A2 反例（§3）与 A3 正式复核（§4）均已回填；结论见 §4.4。
- 执行记录：取数（NSP/provenance/romfs/组件哈希）→ CLI verify（19 checks）→ 独立 raw nstool（NSP+3 NCA）→ NACP/NPDM 独立解析 → 日志/文本密钥扫描 → A2/A3 差异表 → 结论 → 汇报 Lead + task complete。
- 不做：不 commit、不改 cli.py/nsp.py、不启动 Citron、不触碰 A2/A3 之外的构建产物。
