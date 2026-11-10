# galnx batch —— 批量预检/构建/报告（M6-a / M6-b）

状态：M6-a 初版 + M6-b 真实构建（2026-10-30）。对应计划 v0.6 §10 M6 的 CLI 侧实现：批量扫描项目 manifest、逐项目隔离预检、执行 manifest 声明的构建命令、构建缓存、依赖锁定、生成可比较的 JSON 报告。

`batch run` **只做预检与构建计划（preflight / plan）**，不执行任何真实构建命令；`batch build` 才会执行 manifest `build.commands` 中的命令（M6-b，见下文）。

## 快速开始

在仓库根目录执行（源码布局，未安装为包时需要 PYTHONPATH）：

```bash
# 扫描目录顶层 manifest，跑三阶段，写 .galnx 报告
PYTHONPATH=src python -m galnx batch run --dir examples/batch

# 机器可读：把报告 JSON 打到 stdout
PYTHONPATH=src python -m galnx batch run --dir examples/batch --json

# 比较两次运行（回归分析）
PYTHONPATH=src python -m galnx batch diff .galnx/batch-report-A.json .galnx/batch-report-B.json

# 清理报告目录（先 dry-run，再真删）
PYTHONPATH=src python -m galnx batch clean --dir examples/batch
PYTHONPATH=src python -m galnx batch clean --dir examples/batch --yes
```

## 扫描规则

| 场景 | 行为 |
| --- | --- |
| 默认 | 只扫描 `--dir` 顶层的 `*.yaml` / `*.yml` |
| `--recursive` | 递归扫描子目录；跳过 `.galnx`、`.git`、`node_modules`、`__pycache__`、`workspaces` |
| `--manifest a.yaml --manifest b.yaml` | 只跑显式列出的 manifest（相对 `--dir` 解析，可重复） |
| 结果排序 | 按 manifest 根相对 POSIX 路径升序，报告稳定可比对 |

## 三个阶段（每个项目独立执行）

| 阶段 | 内容 | 失败后的行为 |
| --- | --- | --- |
| `manifest` | 读取 YAML、JSON Schema 校验、input 段校验 | 后两个阶段标记 skip，其他项目继续 |
| `preflight` | 复用现有 preflight 检查：source_dir、engine.entry、title_id、target、output_dir、build root、prod.keys | 记录 fail，继续 engines 阶段 |
| `engines` | engine registry 解析、adapter 计划（`plan_build`）、pin/license 警告 | 记录 fail，项目判 fail |

隔离保证：runner 对每个 manifest 外层 try/except，单项目异常只把该项目记为 fail（附 `stage.exception` 检查），绝不中断整批。

## 报告字段（schema：`schemas/batch-report.schema.json`）

| 字段 | 说明 |
| --- | --- |
| `schema_version` | 报告格式版本，当前 1 |
| `generated_at` | UTC 时间戳 `YYYY-MM-DDTHH:MM:SSZ` |
| `root` | 批处理根目录（绝对 POSIX 路径） |
| `totals` | `total` / `ok` / `warn` / `fail` / `skipped` / `duration_s` |
| `projects[]` | 每项目：`path`、`name`、`adapter`、`status`、`stages[]`、`checks[]`、`errors[]`、`duration_s` |
| `stages[].checks[]` | 检查项：`id` / `name` / `status` / `detail` / `hint` |

写盘位置：`<root>/.galnx/batch-report-<UTC时间戳>.json`，另外写一份同内容 `latest.json`；默认保留最近 10 份（`--keep N` 可调）。同一秒内多次运行会追加 `_2`、`_3` 后缀，保证文件名排序与时间顺序一致。`.galnx/` 已加入仓库 `.gitignore`。

## 状态语义与退出码

| 状态 | 含义 |
| --- | --- |
| `ok` | 所有检查通过 |
| `warn` | 有警告但无失败（如 adapter_version 未含 pinned commit、engine 标记 research） |
| `fail` | 至少一项检查失败 |
| `skipped` | 项目全部检查被 skip（如 `--skip-preflight` 后无其他阶段） |

退出码：`0` = 全部 ok/warn；`2` = 存在 fail、参数错误或未确认的 clean。

## diff 分类

`galnx batch diff <before> <after>` 按项目 `path` 对齐，输出 `added` / `fixed` / `regressed` / `still_failing` / `removed` 五类与计数 `counts`（含 `unchanged`、`skipped`）。退出码：无回归且无仍失败项时 `0`，否则 `2`。

## clean

`galnx batch clean --dir <root>` 只删除 `<root>/.galnx` 报告目录。不带 `--yes` 时只统计文件数并返回 2；带 `--yes` 才真正删除。目标不存在时返回 0。

## 示例

仓库内 `examples/batch/` 提供 3 个项目：两个正常项目（krkrsdl2 / brewser）与一个故意坏掉的 manifest，用于演示隔离。详见 `examples/batch/README.md`。

## 与计划 v0.6 §10 M6 的对应

| 计划验收项 | 本实现状态 |
| --- | --- |
| 批量预检 | 已完成（`batch run`） |
| 单项目失败不影响其他项目 | 已完成（逐项目隔离 + 测试覆盖） |
| 测试报告差异 | 已完成（`batch diff`） |
| 清理工作区 | 已完成（`batch clean` 清理 `.galnx`：报告、缓存、日志；不带 `--yes` 只统计） |
| 构建缓存 / 依赖锁定 / 重新构建 | 已完成（`batch build` + `--rebuild` + `batch lock` / `--locked`） |
| GUI | 未做（计划要求 CLI 稳定后再设计） |

## 设计边界与已知限制

1. 不执行任何构建命令；`engines` 阶段只产出计划（report 中 `engine.plan` 写明 step 数且标注 not executed）。
2. `preflight` 复用 `src/galnx/preflight.py` 的现有检查，未重写校验逻辑；相对 `source_dir` 按当前进程工作目录解析（与单项目 `galnx preflight` 行为一致）。
3. `--skip-output-checks` 用于屏蔽与机器相关的 `build.output_dir` 检查（例如跨机器跑同一批项目）。
4. 报告 JSON 受 `schemas/batch-report.schema.json` 约束，由测试用 Draft 2020-12 validator 校验。

## M6-b：真实批量构建

### 命令

```bash
# 批量构建（默认读缓存；写报告到 <root>/.galnx/）
PYTHONPATH=src python -m galnx batch build --dir examples/batch

# 忽略缓存 / 强制重建 / 校验依赖锁
PYTHONPATH=src python -m galnx batch build --dir examples/batch --no-cache
PYTHONPATH=src python -m galnx batch build --dir examples/batch --rebuild
PYTHONPATH=src python -m galnx batch lock --dir examples/batch
PYTHONPATH=src python -m galnx batch build --dir examples/batch --locked

# 单个 manifest（root 取 manifest 所在目录）
PYTHONPATH=src python -m galnx build run --manifest examples/batch/demo-build.yaml
```

`batch build` 与 `batch run` 共享扫描、manifest/preflight/engines 三阶段与隔离语义；区别在于额外执行 `cache`、`build`（以及 `--locked` 时的 `lock`）阶段，并且只有 manifest `build` 段声明了 `commands` + `artifact` 的项目才会真正执行命令。未声明构建命令的项目照常通过前三个阶段并在 `build` 阶段标记 skip（项目状态仍可为 ok）。

### manifest `build` 段新增字段

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `commands` | 数组 | 无（不构建） | 每个元素是参数数组（argv，`shell=False`）或字符串（`shell=True`，Windows 走 `cmd.exe`）；按顺序执行，任一失败即停止 |
| `workdir` | 字符串 | manifest 所在目录 | 相对 manifest 目录解析；命令的 cwd |
| `artifact` | 字符串 | 无 | 相对 `workdir` 的产物路径；声明了 `commands` 就必须声明 `artifact`，构建后必须存在 |
| `env` | 映射 | 无 | 追加到子进程环境（值可为字符串/数字/布尔）；另有 `GALNX_MANIFEST`、`GALNX_PROJECT` 注入 |
| `timeout_s` | 数字 | 600 | 单条命令超时（秒），超时记为失败 |

命令的 stdout/stderr 写入 `<root>/.galnx/logs/<project>-<step>.log`（单文件上限约 256 KiB，保留头部与尾部并标注截断）；报告 `commands[].log` 给出该日志的 root 相对路径。

### 构建缓存

- key = `sha256(canonical JSON)`，内容包含：manifest root 相对路径、引擎 `adapter` / `pinned_commit` / `build_backend`、`build.commands/workdir/artifact/env/timeout_s`、manifest `input` 段、工具链指纹（devkitA64 `aarch64-none-elf-gcc --version` 首行与 `cmake --version` 首行；找不到记 `unknown`，不使构建失败）。
- 条目：`<root>/.galnx/cache/<key[:16]>/meta.json`，记录 `key`、产物绝对路径/大小/sha256、命令与耗时。
- 命中条件：存在条目且产物文件存在、大小与 sha256 都相符；否则视为 miss 并重建（产物缺失/变化时报告 `cache.stale` 警告）。
- `--no-cache` 完全跳过缓存读写；`--rebuild` 跳过读取但仍写回新条目。
- 缓存只比较元数据与产物哈希，不缓存命令输出；同一 manifest 在同一机器、同一工具链下才稳定命中。

### 依赖锁定

`batch lock` 写 `<root>/.galnx/engine-lock.json`（`schema_version: 1`），按 manifest root 相对路径记录：引擎 `adapter` / `pinned_commit` / `build_backend`、工具链指纹、manifest 文件 sha256、产物路径。`batch build --locked` 时对每个项目比较锁文件：缺锁、manifest 内容变化、引擎 pin 或工具链指纹漂移都会让该项目 fail（check `lock.drift`）并跳过 cache/build，不执行任何命令。锁文件可单独取出存档（`.galnx/` 目录本身不入库）。

### 报告新增字段

| 字段 | 说明 |
| --- | --- |
| `totals.cache_hits` / `cache_misses` / `built` | 缓存命中数、未命中数（含 stale）、实际执行构建的项目数 |
| `projects[].artifact` | `{path, size, sha256}`，构建产物元数据 |
| `projects[].cache` | `{hit, key}`，本次缓存判定与 key |
| `projects[].commands` | `[{command, duration_s, exit_code, log}]`，实际执行的命令；超时 `exit_code = null` |
| `stages[]` | 新增 `lock`、`cache`、`build` 阶段（按本次实际执行情况出现） |

`batch diff` 在五类分类之外新增 `counts.artifact_changed`：同一项目两次报告都有 artifact 且 sha256 不同即计数（用于发现非确定性构建，例如 hacBrewPack 的 RSA-PSS 随机盐）。

### 退出码

与 `batch run` 一致：`0` = 无 fail；`2` = 存在 fail、参数错误（`--locked` 漂移、锁文件损坏等也计 fail）。`batch lock` 在有 manifest 解析错误时返回 `2`，但锁文件仍会写入可解析的项目。

### M6-b 已知限制

1. 引擎 plan 的 guidance 步骤不会被执行：真实命令完全由 manifest `build.commands` 声明（引擎适配器只提供计划与产物校验）。
2. Windows 上字符串命令经 `cmd.exe /c` 执行；带引号/特殊字符的复杂命令应改用 argv 数组形式。
3. 缓存只按 sha256 元数据与产物哈希判断有效性，不跟踪系统库、编译器小版本以外的环境差异（`cmake`/`gcc` 首行版本之外的漂移不敏感）。
4. 尚未接入 CI（M6-c 由 Lead 处理）；`.galnx/` 视为本地产物，不入库。

## 测试

```bash
PYTHONPATH=src python -m pytest -q tests/test_batch_runner.py tests/test_batch_report.py tests/test_batch_cli.py \
    tests/test_build_executor.py tests/test_build_cache.py tests/test_build_lock.py tests/test_batch_build_cli.py
```

覆盖：健康项目、坏 manifest 隔离、未知 adapter、skip 选项、递归/显式扫描、报告写盘与保留策略、diff 五类分类、clean 保护、报告 schema 校验、CLI 退出码；M6-b 追加：executor（argv/shell/超时/失败停止/env/workdir）、缓存（miss→hit→stale→rebuild→no-cache，key 稳定性）、依赖锁（写入/读取/漂移）、`batch build`/`build run`/`batch lock` 的退出码与 `--json` 报告 schema。
