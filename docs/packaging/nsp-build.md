# NSP 打包驱动器（P3-b）

| 项 | 值 |
| --- | --- |
| 文号 | docs/packaging/nsp-build.md |
| 任务 | task-41（P3-b：NSP 打包驱动器） |
| 执行 | audit-package |
| 日期 | 2026-10-30 |
| 状态 | 代码与测试完成；A2 输入 dry-run 验收；**独立 `verify` 子命令已实现并跑通**（tests 48→68）；真实 A3 构建由 P3-f 复核（见 `docs/pilot/P3-verification.md` §4）；`cli.py` 接入由 Lead 完成 |

## 1. 目的与范围

本文件描述 GalNX 框架侧的 **NSP 打包驱动器**：把 P1-d 验证过的 shell 链路（`scripts/build_pilot_nsp.sh`）固化成 Python 模块 `src/galnx/package/nsp.py`，提供可测试、可重复的 plan / build / verify / provenance 四段能力。

范围与边界：

- 只做**自包含 NSP**（ELF → elf2nso → npdmtool/nacptool/icon → hacBrewPack → nstool）。forwarder NSP 明确不在范围内（签名、封禁与 DMCA 风险，见 `docs/packaging/README.md` §2）。
- keyset **必须显式传入**（路径或 `synthetic`），禁止环境变量/默认路径自动拾取；模块只记录 keyset 的 path/size/sha256，不读取、不打印、不复制内容。
- `plan_nsp_build()` 是纯静态规划：只读文件系统、不执行工具、不落盘；`build_nsp()` 才真正调用子进程。
- 真实构建（2.9 GB 级 romfs）不在本任务验收范围；本任务只用 A2 输入验证 plan 与命令行序列。实际 shell 构建证据见 `docs/builds/005-nsp-selfcontained.md` 与 `docs/pilot/P1-nsp-packaging.md`。

## 2. 与 shell 脚本的对照

P1-d 的 `scripts/build_pilot_nsp.sh` 是当前唯一实际出包路径；P3-b 把其中可复用的部分按下列映射搬进 Python：

| shell 脚本步骤 | Python 实现 | 差异 |
| --- | --- | --- |
| 参数解析（--elf/--romfs-dir/--title-id/--keyset/--out/--work/工具路径） | `plan_nsp_build()` 关键字参数 + CLI `--*` | 工具可显式指定或从 PATH 查找；keyset 不接受隐式默认 |
| romfs 统计（count/total/max path） | `inventory_romfs()` | 额外记录 dirs/最大文件/unreadable |
| elf2nso | step `elf2nso` | 同样的 `[elf2nso, elf, work/exefs/main]` |
| 渲染 npdm.json + npdmtool | step `npdm` | 模板占位符替换逻辑相同（`0100000000001000` → title_id） |
| nacptool --create | step `nacp` | 相同的参数顺序与 `--titleid=` 大写格式 |
| hacBrewPack | step `hacbrewpack` | 相同：`--nologo -k <keyset> --romfsdir <romfs>`，cwd=work |
| nstool 两层校验 | `verify_nsp()` | 结构化 Check；签名 FAIL 只记 warning |
| 手工记录输入/工具哈希 | `write_provenance()` | 机读 JSON（`<out>.provenance.json`） |

## 3. 模块布局与公共 API

新增文件：`src/galnx/package/nsp.py`（纯 Python 标准库，无第三方依赖）。不修改 `cli.py`，只导出 `register()` / `cmd_nsp()` 供其接入。

### 3.1 数据结构

| 名称 | 说明 |
| --- | --- |
| `NspToolchain` | elf2nso / npdmtool / nacptool / hacbrewpack / nstool 五个可选路径；`resolve()` 返回 (paths, sources)，source 取 `explicit` / `PATH` / `missing` |
| `KeysetRef` | keyset 元数据：path、size、sha256、synthetic；`mode` 为 `real` / `synthetic`；`to_dict()` 不含内容 |
| `RomfsInventory` | root/files/dirs/total_bytes/max_path_len/max_path/largest_file_bytes/largest_file/unreadable |
| `BuildStep` | 计划中的一步：name/argv/cwd/note/outputs |
| `StepResult` | 实际执行结果：name/argv/cwd/exit_code/duration_s/stdout_tail/stderr_tail/log_path/note |
| `BuildResult` | ok/out_path/work_dir/steps/artifact/error/duration_s；artifact=`{path,size,sha256,produced_by}` |
| `VerifyResult` | ok/nsp/nstool/checks/ncas/artifact/error |
| `NspBuildPlan` | metadata/elf/romfs_dir/inventory/out_path/work_dir/title_id/keyset/npdm/npdm_template/nacp/icon/tools/tool_sources/steps/issues；`errors`/`warnings`/`ok` 为派生属性 |

### 3.2 函数

| API | 说明 |
| --- | --- |
| `inventory_romfs(root)` | 递归清点目录：文件数、目录数、总字节、最长路径、最大文件、unreadable |
| `digest_romfs(root)` | romfs 汇总哈希：按相对路径排序后 `relpath + NUL + size + NUL + sha256` 逐项喂给 SHA-256；与文件 mtime/顺序无关 |
| `sha256_file(path)` | 分块 sha256 |
| `plan_nsp_build(metadata, *, elf, romfs_dir, out_path, work_dir, keyset, toolchain, icon, npdm, npdm_template, nacp)` | 纯静态校验 + 生成 4 步命令列表；非法输入进 issues 而非抛异常 |
| `build_nsp(plan, *, timeout_s=1800.0, runner=None)` | 执行 plan.steps；失败即停、保留 work 与每步日志；runner 可注入（测试用 fake） |
| `verify_nsp(nsp, nstool, *, keyset=None, expected_title_id=None, work_dir=None, timeout_s=300.0, runner=None)` | 用 nstool 做只读校验（NSP 层 PFS0 + 可选 NCA 层），返回 `VerifyResult` |
| `write_provenance(*, path, plan, result=None, verify=None, romfs_digest=True, environment=None)` | 原子写 provenance JSON |
| `register(subparsers)` / `cmd_nsp(args)` | 注册/执行 `galnx package nsp` 子命令 |
| `cmd_nsp_verify(args)` / `_check_provenance(path, *, nsp, expected_title_id, keyset)` | 执行 `galnx package nsp verify` 子命令：`verify_nsp()` + 可选 provenance 交叉核对 |

`Runner` 类型为 `(argv, cwd, timeout_s) -> (exit_code, stdout, stderr)`；默认实现 `subprocess.run(argv, cwd=..., stdin=DEVNULL, stdout=PIPE, stderr=PIPE, timeout=..., shell=False)`。参数始终是列表，无 shell。

## 4. 构建计划（plan_nsp_build）

### 4.1 输入与默认值

| 输入 | 来源/默认 | 说明 |
| --- | --- | --- |
| metadata | `PackageMetadata.from_manifest()` | 必须 `package_type == self_contained_nsp`；title_id 必须是合法 base |
| elf | `--elf`，必填 | ELF 文件；NRO 必须先经 P1-d 流程合成 ELF（NRO 头不是 ELF magic） |
| romfs_dir | `--romfs-dir` 或 metadata.romfs_dir | 自包含 NSP 必须有非空 romfs |
| out_path | `--out` 或 `build/nsp/<safe title>-<title_id>.nsp` | 必须以 `.nsp` 结尾；不得与 work 相同 |
| work_dir | `--work` 或 `build/nsp/work-<title_id>` | 暂存目录；非空只 warning |
| keyset | `--keyset`，必填；路径或 `synthetic` | 无默认路径、无环境变量拾取 |
| icon | `--icon` 或 metadata.icon_file() | 必须 256x256 JPEG（bmp 会被 metadata.validate() 报警告） |
| npdm / nacp | `--npdm` / `--nacp` | 预置产物；给了就跳过对应生成步骤 |
| npdm_template | `--npdm-template` 或 `examples/nsp/npdm.json` | 缺 title_id 占位符只 warning |
| 工具 | `--elf2nso` 等或 PATH | 显式路径优先；elf2nso/hacbrewpack 必填，其余按需 |

### 4.2 校验规则（plan 不通过时的报错原文）

| 检查 | 严重度 | 示例报错 |
| --- | --- | --- |
| title_id 非合法 base | error | `title id 010047410000B0B4 is an add-on content id (base | 0x1000 | index); allocate the base id instead` |
| package.type 非自包含 | error | `P3-b NSP driver builds self-contained NSP only; package.type is 'forwarder_nsp' ...` |
| elf 缺失/非 ELF | error | `elf is required: pass --elf <path> ...` / `elf is not an ELF image (magic b'NRO0') ...` |
| out 后缀/同目录冲突 | error | `out_path must end with .nsp: ...` / `out_path and work_dir must differ` |
| work 非空 | warning | `work dir ... already exists ...` |
| out 已存在 | warning | `... already exists and will be overwritten` |
| keyset 缺失 | error | `keyset is required and must be explicit: pass --keyset <prod.keys path> or --keyset synthetic (no default path, no environment variable auto-discovery)` |
| keyset 不存在/为空 | error | `keyset file not found: ...` / `keyset file is empty: ...` |
| keyset 在仓库内 | warning | keyset 路径位于仓库根下，提示不要入库 |
| keyset 在 romfs 内 | error | `prod.keys would be packaged into the NSP: ...` |
| synthetic 模式 | warning | 只做结构冒烟，产物 NOT INSTALLABLE |
| romfs 空/文件超 4 GiB/路径超限 | error/warning | `romfs ... is empty` / 单文件 ≥ FAT32 4 GiB-1 / 最长路径 ≥ 259 字符 |
| 磁盘余量不足 | error | `free ... < estimated peak ...`（估算 NSP ≈ romfs+elf+64 MiB；同卷时 work 需要额外一份 NSP 空间） |
| 工具缺失 | error（nstool 除外） | `<name> not found: pass --<name> <path> or put it on PATH`；仅 nstool 缺失为 warning |
| npdm 模板缺占位符 | warning | 仍可生成 NPDM，但 title_id 不会替换 |

关键字过滤器：`plan.ok` 只取决于是否存在 error；warning 保留在 plan.issues 与 CLI checks 中。

### 4.3 四步命令（顺序固定）

| # | step | argv（模板） |
| --- | --- | --- |
| 1 | `elf2nso` | `[elf2nso, <elf>, <work>/exefs/main]` |
| 2 | `npdm`（仅当未提供 --npdm） | `[npdmtool, <work>/npdm.json, <work>/exefs/main.npdm]` |
| 3 | `nacp`（仅当未提供 --nacp） | `[nacptool, "--create", <title_name>, <title_author>, <version>, <work>/control/control.nacp, "--titleid=<TITLE_ID_UPPER>"]` |
| 4 | `hacbrewpack` | `[hacbrewpack, "--nologo", "-k", <keyset 或 synthetic.keys>, "--romfsdir", <romfs>]` |

所有 step 的 cwd 都是 `work`。第 2 步执行前会把 `examples/nsp/npdm.json` 中的占位符 `0100000000001000` 替换为实际 title_id，写到 `work/npdm.json`（不修改仓库模板）。

## 5. 构建执行（build_nsp）

### 5.1 暂存与逐步执行

每次 build 都重建以下目录，避免上一次产物污染（hacBrewPack 会**就地改写**暂存的 main.npdm/control.nacp，P1-d 实测）：

```text
work/
  exefs/              exefs/main（elf2nso）、exefs/main.npdm
  control/            control.nacp、icon_AmericanEnglish.dat
  hacbrewpack_nsp/    hacBrewPack 输出目录
  hacbrewpack_nca/    暂存
  nstool-nca/         verify 时抽取的 NCA
  logs/               每步一个 <step>.log
  npdm.json           渲染后的模板（若需生成 NPDM）
  synthetic.keys      仅 synthetic 模式
```

暂存动作同样记为 step（成功时出现在 build.steps 前部）：

| step | 动作 |
| --- | --- |
| `stage-icon` | icon → `control/icon_AmericanEnglish.dat` |
| `stage-npdm` | 预置 NPDM → `exefs/main.npdm`（仅 `--npdm`） |
| `stage-nacp` | 预置 NACP → `control/control.nacp`（仅 `--nacp`） |

执行每步时记录：argv、cwd、exit_code、duration_s、stdout/stderr 尾部（各默认 40 行）、日志路径。任一步非 0 立即停止；失败信息含退出码与日志路径。`TimeoutExpired` 报 `step ... timed out after ...s`；`OSError` 报 `could not start ...`。

### 5.2 日志与 keyset 脱敏

- 每步日志写入 `work/logs/<step>.log`，头部为 `# step: <name> | cwd: ... | argv: ... | exit: N | duration: ...`。
- stdout/stderr 在落日志前调用 `_sanitize_log()`：含 `Key area key` 或 `key_area_key` 的行整行替换为 `<redacted: key material line>`。hacBrewPack 会打印 Key area key，不能让密钥材料进入日志/证据。
- keyset 文件只按路径传给工具；模块**不打开读取**（sha256 除外）——sha256 只用于 provenance 标识。synthetic 模式在 work 内生成假 keyset，文件内容显式写 `NOT REAL KEYSET`，仅够 hacBrewPack 走通结构；产物不可安装。

### 5.3 产物定位与失败模式

期望产物为 `work/hacbrewpack_nsp/<title_id>.nsp`；若该文件不存在，回退为目录中唯一 `.nsp`；仍没有则报错 `hacBrewPack did not produce the expected ... (candidates: ...)`。找到后复制到 `plan.out_path`，记录 size/sha256/produced_by；空产物报 `artifact is empty`。

## 6. 只读校验（verify_nsp）

调用 nstool 做两层校验，全部只读：

1. **NSP/PFS0 层**：`nstool -y [-k <keyset>] <nsp>`。解析 `parse_nstool_output()` 后交给 `check_nstool()`：PFS0 Type、FileNum==3、Program/Control/Meta 三类 NCA、ProgID 一致性与期望 title_id 比对。
2. **NCA 层**（仅真实 keyset 且提供 work_dir）：`nstool -x <work>/nstool-nca -k <keyset> <nsp>` 抽出 3 个 NCA，再对每个 `.nca` 执行 `nstool -y -k <keyset> <nca>`，把结果合并回 parsed。synthetic keyset 跳过 NCA 层（header_key 不匹配，抽不出 NCA）。

check id 一览：

| id | 状态 | 含义 |
| --- | --- | --- |
| `verify.nsp` | fail | NSP 不存在 |
| `verify.nstool` | fail | nstool 路径不存在 |
| `verify.keyset` | skip/warn | synthetic 跳过 NCA 层；无 keyset 只做 PFS0 |
| `verify.nstool.nsp` | fail | nstool 在 NSP 层返回非 0 |
| `verify.nstool.extract` | warn | NCA 抽取失败，仍保留 PFS0 结果 |
| `verify.nca.<i>` | fail | 第 i 个 NCA 校验非 0 |
| `verify.signature` | warn | 日志中出现 `Signature: FAIL`——未签名 homebrew NSP 的预期现象，不判失败 |
| `verify.ncas` | warn | 未解析到任何 NCA 头（输出被截断/无 keyset） |
| `verify.summary` | ok/fail | 汇总 |

`VerifyResult.ok = not has_failures(checks)`；签名 FAIL 只产生 warning，因此未签名 NSP 的结构校验仍可 ok。

## 7. provenance 产物

`write_provenance()` 默认写 `<out>.provenance.json`，原子替换（`.tmp` + `os.replace`）。顶层字段：

| 字段 | 内容 |
| --- | --- |
| `schema` / `schema_version` | `galnx-nsp-provenance` / 1 |
| `generated_at` / `galnx_version` | UTC ISO 秒 / GalNX 版本 |
| `dry_run` | 无 build result 时为 true |
| `metadata` / `title_id` | PackageMetadata.to_dict() / 规范化 title id |
| `inputs` | elf、romfs{root,files,total_bytes,sha256}、icon、npdm、nacp、npdm_template 的 path/size/sha256 |
| `keyset` | mode/path/size/sha256 + note（**不含内容**） |
| `tools` | 每个工具的 path/source/size/sha256 |
| `commands` | plan.steps 的完整 argv/cwd |
| `build` / `artifact` | build 结果与产物哈希（dry-run 为 null） |
| `verify` | 校验 checks/ncas/artifact（未校验为 null） |
| `environment` | python/platform/machine/cwd |

版本锁定建议：锁 `inputs.*.sha256`、`tools.*.sha256`、`commands`，**不要锁 NSP 的 sha256**——hacBrewPack 的 RSA-PSS 使用随机盐，同输入两次产物哈希不同（P1-d 实测，见 `docs/builds/005-nsp-selfcontained.md`）。

## 8. CLI 用法与集成

### 8.1 用法

```bash
# 计划（默认就是 dry-run）：
PYTHONUTF8=1 python -m galnx package nsp \
    --manifest game.yaml --keyset /path/to/prod.keys \
    --elf build/game.elf --romfs-dir romfs \
    --elf2nso /d/devkitPro/tools/bin/elf2nso.exe \
    --hacbrewpack /path/to/hacbrewpack.exe --nstool /path/to/nstool.exe \
    --dry-run --json

# 真构建 + 校验 + provenance：
PYTHONUTF8=1 python -m galnx package nsp \
    --manifest game.yaml --keyset /path/to/prod.keys \
    --elf build/game.elf --romfs-dir romfs --build

# 结构冒烟（无真 keyset；产物不可安装）：
python -m galnx package nsp --manifest game.yaml --keyset synthetic \
    --elf build/game.elf --romfs-dir romfs --build

# 独立校验已有 NSP（不构建；可选交叉核对 provenance）：
PYTHONUTF8=1 python -m galnx package nsp verify \
    --nsp build/game.nsp --manifest game.yaml \
    --nstool /path/to/nstool.exe --keyset /path/to/prod.keys \
    --provenance build/game.nsp.provenance.json --json
```

### 8.2 输出与退出码

- `--json`：整个 stdout 是**一个** JSON 文档（人类日志走 stderr）。plan 模式键：`tool`、`mode`(`plan`)、`manifest`、`plan`、`checks`、`ok`、`errors`；build 模式键：`tool`、`mode`(`build`)、`manifest`、`plan`、`build`、`verify`、`provenance`、`checks`、`ok`；verify 模式键：`tool`、`mode`(`verify`)、`manifest`、`nsp`、`expected_title_id`、`nstool`、`keyset`、`work_dir`、`provenance`、`verify`、`checks`、`ok`、`errors`。
- 文本模式：先打印 `NSP build plan (dry-run)` 摘要（title_id/elf/romfs/out/work/keyset/npdm/nacp/tools/steps），再渲染 checks。
- 退出码：`0` 无 fail；`1` 构建或校验失败；`2` 计划错误或参数非法（含 `--build` 与 `--dry-run` 同时给出）。三种模式（plan/build/verify）共用该约定。

### 8.3 接入 cli.py（由 Lead 完成）

`cli.py` 当前只有 `package plan` / `package check`。接入只需在 `package_sub` 建好之后、进入下一个子命令前加一行：

```python
from .package import nsp as nsp_module   # 文件顶部按现有 import 风格
...
nsp_module.register(package_sub)          # cli.py:658 之后（package check 之后）
```

`register()` 内部自己 `set_defaults(func=cmd_nsp)`，无需改 `main()` 分发逻辑。在接入前，本文件的 dry-run 用等价的临时 harness（`.cache/packaging-testing/run_nsp_cli.py`，argparse + `nsp.register()`）验证。

### 8.4 独立 verify 子命令（`galnx package nsp verify`）

只校验已有 NSP，不构建；内部复用 `verify_nsp()`，与 `--build` 末尾的自动校验是同一实现。

| 参数 | 说明 |
| --- | --- |
| `--nsp PATH`（必填） | 待校验的 NSP |
| `--manifest PATH`（必填） | 用于取 title_id/name/author/version；`--expect-title-id` 缺省时用它格式化出期望值 |
| `--nstool PATH` | 缺省从 PATH 查找 `nstool`/`nstool.exe` |
| `--keyset PATH` / `synthetic` | 缺省时只做 PFS0 层（`verify.keyset` warn）；真实 keyset 才会抽 NCA 做第二层 |
| `--expect-title-id ID` | 覆盖 manifest 的期望 title id；非法 id 直接 rc=2 |
| `--provenance PATH` | 可选；给出时追加 6 项 provenance 交叉核对（见下） |
| `--work-dir PATH` | 可选；NCA 抽取目录。缺省用 `tempfile.mkdtemp()` 并在结束时删除 |
| `--json` | 单文档 JSON 输出 |

provenance 交叉核对的 check id：

| id | 状态 | 含义 |
| --- | --- | --- |
| `verify.provenance` | fail | provenance 读不到/不是合法 JSON |
| `verify.provenance.schema` | fail | `schema != galnx-nsp-provenance` 或 `schema_version != 1` |
| `verify.provenance.dry_run` | fail | `dry_run` 不是 `false`（dry-run 证据不能证明真实产物） |
| `verify.provenance.title_id` | fail | provenance 的 title_id 与期望不一致 |
| `verify.provenance.artifact` | fail | provenance 的 artifact size/sha256 与实际 NSP 不一致 |
| `verify.provenance.keyset` | skip/ok/fail/warn | 未给 `--keyset` 时 skip；synthetic/real 模式、size、sha256 必须匹配；path 不同仅 warn |
| `verify.provenance.no_secret` | fail | provenance 文本出现 `header_key`/`key_area_key` 等密钥材料标记 |

返回码：`0` 全部通过（warn 不影响）；`1` 存在 fail；`2` 输入/参数错误（如 NSP/manifest 不存在、title id 非法）。

## 9. A2 真实输入 dry-run 验收

### 9.1 输入（全部为 P1-d 真实产物）

| 输入 | 值 |
| --- | --- |
| ELF | `E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.elf`，113,874,760 B，sha256 `4b4515837d0239ee2e7448dd5dbed65e8fdda72c37fb0bac0d0dd10ef849b882` |
| romfs | `E:/galnx-build/pilot-01/nsp/romfs-a2`，109 files / 9 dirs / 2,878,186,922 B / max path 67（最长 `.../Default/SliderNode_Disable.png`）/ 最大文件 717,704,696 B |
| icon | `E:/galnx-build/pilot-01/build/k2nx-a2/control/icon_AmericanEnglish.dat`，6,285 B，sha256 `0b942950df9fb30f08336b681e24a3ceeeaa6f0915d7dd404d5ebb9bd4e15214` |
| keyset | `E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys`，12,007 B，sha256 `7bb3b6d2a2eedc83c9f244ee2ed2eaa4d59eb9ad95b66df575f7dfffa71a2a40`（只读路径/大小/哈希） |
| title_id | `010047410000A000`（合法 base；见 §10） |
| 工具 | elf2nso/npdmtool/nacptool = `D:/devkitPro/tools/bin/*.exe`；hacBrewPack = `E:/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c/hacbrewpack.exe`；nstool = `E:/galnx-build/m3-tools/nstool.exe` |

manifest 使用 `.cache/packaging-testing/a2-dryrun.manifest.yaml`（package.type=self_contained_nsp、romfs_dir 指向上述目录、icon 绝对路径）。注意：该 checkout 的 engine registry 尚未注册 `kirikiroid2-nx`，manifest 校验会报 `unknown engine adapter`；dry-run 与打包无关，故测试 manifest 暂用已注册的 `krkrsdl2`，接入正式 manifest 时应先注册 descriptor（见 §12）。

### 9.2 结果

命令返回码 0（`--json` 与文本模式各跑一次，均 0）。文本输出摘要：

```text
NSP build plan (dry-run)
  title_id : 010047410000A000
  elf      : ...K2NX-rebuilt-galnx-r2.elf
  romfs    : ...romfs-a2 (109 files, 2.7 GiB, max path 67)
  keyset   : ...prod.keys (12007 bytes, sha256 7bb3b6d2...)
  npdm     : template examples/nsp/npdm.json -> npdmtool
  nacp     : nacptool --create
  steps:
    1. elf2nso  ...
    2. npdm     ...
    3. nacp     ...
    4. hacbrewpack  [... "--nologo", "-k", "...prod.keys", "--romfsdir", "...romfs-a2"]
  [ok] romfs inventory   109 files, 2.7 GiB, max path 67
  [ok] keyset mode       explicit real keyset: 12007 bytes, sha256 7bb3b6d2...
  [ok] tool elf2nso / npdmtool / nacptool / hacbrewpack / nstool  (explicit)
  [ok] NSP build plan    4 steps, 0 error(s), 0 warning(s)
8 checks: 0 fail, 0 warn, 0 skip
```

JSON plan 中 `romfs` 的机读值为 `{"files":109,"dirs":9,"total_bytes":2878186922,"max_path_len":67,"max_path":"E:\\galnx-build\\pilot-01\\nsp\\romfs-a2\\Default\\SliderNode_Disable.png","largest_file_bytes":717704696}`；`steps` 为 4 条，argv/cwd 与 §4.3 一致。

### 9.3 复核结论

- romfs 清点与 P1-d 的 `romfs-a2` 实际统计（109 files、2,878,186,922 B、max path 67）**逐项一致**；
- 4 步命令序列与 `build_a2.sh` → `build_pilot_nsp.sh` 的实际执行顺序一致（ELF → NSO → NPDM → NACP → hacBrewPack）；
- 本任务（P3-b）**只 dry-run，不产出 NSP**；真实构建能力仍以 shell 脚本的 A2 实测为准。
- **真实 A3 构建已由 P3-f 用 CLI 管线验收**（`galnx package nsp --build`，4 steps exit 0、NSP 2,906,131,672 B、verify 19 checks 18 ok/1 warn），见 `docs/pilot/P3-verification.md` §4。

## 10. TitleID 合规性发现

framework 的 `validate_base()` 要求 base title id 低 13 位为 0（0x2000 对齐）；P1-d/A2 产物使用的 `010047410000b0b4` 不满足该规则（低 13 位 0x10B4 落在 DLC 区间），用 A2 原 id 跑 dry-run 会被拒绝：

```text
$ python ... nsp --manifest ... --keyset ... --dry-run --json   # title_id=010047410000b0b4
rc=2
error: title id 010047410000B0B4 is an add-on content id (base | 0x1000 | index); allocate the base id instead
```

判定细节：`classify()` 按低 13 位分类——0 → base；0x800 → patch；≥0x1000 → DLC；其余 invalid。`b0b4 & 0x1FFF = 0x10B4`，因此是 DLC；即使 `b000`（低 13 位 0x1000）也会被判 DLC。合法 base 例如 `010047410000A000`（0xA000 = 5×0x2000）。

结论：A2 只是 P1-d 直接用 `build_a2.sh` 调 nacptool 的试验产物，未经 GalNX 元数据校验，因此带上了不合规的 title id；**正式打包必须改用 0x2000 对齐的 base id**（例如 `010047410000A000`），并在 NACP/NPDM/CNMT 三处保持一致。已把该拒绝行为固化为测试 `test_non_base_title_id_is_rejected`。P3-f 已按此结论用 `010047410000A000` 重建 A3 并通过验收（`docs/pilot/P3-verification.md` §4）。

## 11. 测试

```bash
cd Workspace/GalNX
python -m pytest tests/test_package_nsp.py -q
# 68 passed（原 48 + verify 子命令 20）

python -m pytest -q        # 本文件最近一次实测：600 passed, 63 subtests passed
# 基线为 401 passed / 63 subtests；本任务累计新增 68 用例；
# 仓库内并行任务仍在增加用例，总数会变化，以本文件 68 passed 为准。
```

新增 `tests/test_package_nsp.py`（unittest 风格，fake runner，不调用任何真实工具）：

| 测试类 | 覆盖 |
| --- | --- |
| PlanTests | 4 步顺序、synthetic 仅 warning、非 base id 拒绝、预置 npdm/nacp 跳过生成、out 已存在 warning、坏 NACP 大小、模板缺占位符、默认 out/work 路径、磁盘不足 |
| BuildTests | 成功产物复制与日志、Key area key 脱敏、重建清理暂存、失败即停、超时、缺产物、单候选兜底、synthetic keyset 生成 |
| VerifyTests | PFS0/NCA 两层解析、签名 FAIL 只 warning、title id 不匹配 fail、synthetic 跳过 NCA 层 |
| ProvenanceTests | dry-run 记录输入且不含 keyset 内容、build+verify 后字段完整 |
| CliTests | dry-run JSON、build 成功写 provenance、失败退出码 1/2 |
| VerifyCliTests | `nsp verify` 参数接线、ok/fail JSON、缺 NSP/manifest/nstool、非法 expect-title-id、keyset 转发、文本输出、provenance 6 项交叉核对（schema/dry_run/title_id/artifact/keyset/no_secret） |

## 12. 已知限制与未验证项

1. **真实 build 已由 P3-f 用 CLI 链路验收**：A3（title_id `010047410000A000`，romfs 109 files/2,878,186,922 B）经 `galnx package nsp --build` 完成 4 steps（hacBrewPack 175.0 s，总 180.7 s），产物 2,906,131,672 B，随后 verify 19 checks 18 ok/1 warn，细节见 `docs/pilot/P3-verification.md` §4。本任务（P3-b）自身只交付模块与 dry-run 证据。
2. **JSON 编码**：全仓 CLI 约定 `json.dumps(..., ensure_ascii=False)`，在 Windows 下重定向到文件时按控制台代码页（本机 cp936/GBK）编码，中文 step note 会产生非 UTF-8 字节（实测 JSON 位置 3240 出现 0xA3），导致 UTF-8 JSON 解析失败。**取 JSON 必须设 `PYTHONUTF8=1`**（或后续把 CLI 改成 `ensure_ascii=True`）。
3. **cli.py 未接入**：本节所有 CLI 证据来自临时 harness；Lead 加一行 `nsp_module.register(package_sub)` 后才是正式入口。
4. **engine registry 未注册 kirikiroid2-nx**：manifest schema 的 enum 与 engine registry 不一致，`kirikiroid2-nx` 目前会报 `unknown engine adapter`；NSP 打包本身不依赖 adapter，但正式 manifest 提交前需注册 descriptor。
5. **nstool 无法解析 hacBrewPack CNMT**：NCA 层解析在 CNMT 扩展头处已知会失败（`Invalid extended header size`，P1-d 记录）；本模块对 NCA 层失败只 warn，不把 PFS0 层结果作废。
6. **synthetic 模式仅结构冒烟**：假 keyset 产物无法安装；不要用于真机。
7. **未覆盖 forwarder**：明确不做（签名/封禁/DMCA 风险），`package.type=forwarder_nsp` 直接报错。
8. **provenance 不锁 NSP 哈希**：由于 RSA-PSS 随机盐，NSP 每次构建哈希不同；版本锁定应锁输入与工具哈希。
9. **未验证项**：真机构建/安装（2.9 GB NSP 的 DBI MTP 安装耗时与失败模式）、3.4 GiB 档装载内存峰值、中文 NACP 名称显示——均属 P1-d 遗留 U12/U13/U14，与驱动器无关。
10. **verify 的 NCA 抽取需要临时磁盘**：真实 keyset 下 NCA 层校验会把 3 个 NCA 抽到 work_dir（约 2.9 GB）；缺省用 `tempfile.mkdtemp()` 用完即删，`--work-dir` 可保留作证据；synthetic keyset 跳过 NCA 层。

## 13. 相关文件与文档

| 文件 | 说明 |
| --- | --- |
| `src/galnx/package/nsp.py` | 本任务的 NSP 打包驱动器 |
| `tests/test_package_nsp.py` | 68 个用例（fake runner；含 `verify` 子命令 20 例） |
| `src/galnx/package/metadata.py` / `titleid.py` / `contract.py` | 元数据、TitleID、契约校验（P3-b 复用） |
| `scripts/build_pilot_nsp.sh` | P1-d shell 打包链（当前唯一真实出包路径） |
| `docs/builds/005-nsp-selfcontained.md` | M3-a：自包含 NSP 打包链实测（产物/keyset 要求/签名结论） |
| `docs/pilot/P1-nsp-packaging.md` | P1-d：A1/A2 试点打包全过程与真机/模拟器验收 |
| `docs/packaging/README.md` | M3-c：打包数据模型与契约（plan/check 语义） |
| `examples/nsp/npdm.json` | NPDM 模板（含 title_id 占位符） |

本地 dry-run 证据（不入库，`.cache/` 已在 .gitignore）：`.cache/packaging-testing/evidence/a2-dryrun-plan.json`、`a2-dryrun-plan.txt`、`a2d-b0b4-rejected.json`；A3 verify 证据见 `docs/pilot/P3-verification.md` §5（`.cache/verification-p3/`）。
