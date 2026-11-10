# M6 批量构建与回归（里程碑记录）

- 状态：**已完成（CLI 级）**（M6-a 批量预检/报告 MVP + M6-b 真实构建执行/缓存/依赖锁定 + M6-c 汇总；GUI 按计划顺序后置，未开始）
- 计划依据：`docs/PLAN_DRAFT_v0.8.md` §10「M6：批量构建与回归」
- 记录时间：2026-10-30
- 负责人：Lead（汇总）；M6-a 实施 audit-package

## 1. 目标与验收（计划 §10 原文）

| # | 计划验收条款 | 本轮判定 |
| --- | --- | --- |
| 1 | 批量预检/构建，单项目失败不破坏其他项目 | ✅ **达成**：`galnx batch run`（预检）+ `galnx batch build`（真实构建，M6-b）均逐项目隔离，坏项目只 fail 自己；构建失败只终止该项目剩余命令，其他项目继续 |
| 2 | 构建缓存/依赖锁定、测试报告差异、重新构建、清理工作区 | ✅ **达成**：`batch diff`（五类 + `artifact_changed`）、`batch build --rebuild`、sha256 缓存 miss→hit、`batch lock` + `--locked` 漂移检测、`batch clean --yes` 清理 `.galnx`（报告/缓存/日志） |
| 3 | CLI 稳定后再设计 GUI | ⬜ 未开始（符合计划顺序：CLI 稳定 → GUI） |

结论：第 1/2 条验收已全部达成并有实测证据（见 §4 与 §4A）；M6 剩余项为 GUI（按计划后置，M6-c 只做汇总）与 CI 接入。

## 2. 环境与版本

- 平台：Windows 10.0.26100 x64，Python 3（仓库 pytest 环境）
- 仓库基线：commit 0fa3562（M6-a 已提交）+ M6-b 未提交改动
- M6-b 工具链（缓存指纹实测）：`aarch64-none-elf-gcc.exe (devkitA64) 16.1.0`（`D:/devkitPro/devkitA64/bin`）、`cmake version 4.0.2`；Python 3.12.10
- 相关依赖：PyYAML、jsonschema（既有）；无新增第三方依赖
- 模拟器/真机：本轮不涉及（batch 不启动模拟器）

## 3. M6-a 交付物（批量预检/报告 MVP）

### 3.1 代码

| 文件 | 大小 | 作用 |
| --- | --- | --- |
| `src/galnx/batch/__init__.py` | 1,306 B | 包导出 |
| `src/galnx/batch/runner.py` | 16,038 B | manifest 扫描/显式列表、三阶段隔离执行、耗时与 check 汇总 |
| `src/galnx/batch/report.py` | 12,406 B | 报告构建/写盘、diff 五类分类、clean 保护 |
| `src/galnx/cli.py` | 追加 | `galnx batch run` / `diff` / `clean` 子命令 |
| `schemas/batch-report.schema.json` | 3,981 B | 报告契约（Draft 2020-12） |
| `tests/test_batch_runner.py` | 6,821 B | 隔离/未知 adapter/skip 选项/递归扫描 |
| `tests/test_batch_report.py` | 6,565 B | 保留策略/diff 分类/clean 保护/schema 校验 |
| `tests/test_batch_cli.py` | 5,793 B | CLI 退出码与输出 |
| `examples/batch/` | — | 2 个正常项目 + 1 个故意坏 manifest + fixture |
| `docs/batch/README.md` | 5,586 B | 用法、阶段语义、字段、退出码、边界 |

### 3.2 CLI 语义

- `galnx batch run --dir DIR [--manifest M]... [--recursive] [--skip-preflight] [--skip-output-checks] [--engines-dir D] [--keep N] [--json]`
  - 阶段：`manifest`（YAML+schema）→ `preflight`（源目录/TitleID/输出目录/keys 提示等）→ `engines`（`engines plan` 一致性校验，**只出计划不执行构建**）
  - 每项目独立 try/except：某项目抛错只记该项目的 `errors`，其余项目继续；被中止的阶段记为 `skip`
  - 报告写到 `<root>/.galnx/batch-report-<UTC>.json` 与 `latest.json`；默认保留 10 份；同秒冲突自动 `_2` 后缀保证排序
  - 退出码：0 = 全部 ok/warn；2 = 存在 fail 或参数错误
- `galnx batch diff BEFORE AFTER [--json]`：五类分类 added/fixed/regressed/still_failing/removed，退出码同上
- `galnx batch clean --dir DIR [--yes] [--json]`：删除 `.galnx/`；不带 `--yes` 只报告将删除数量并以 2 退出

### 3.3 报告结构（实测 `--json` 输出经 schema 校验 0 errors）

顶层键：`schema_version`、`root`、`generated_at`、`totals{total,ok,warn,fail,skipped,duration_s}`、`projects[]`；
项目键：`name`、`path`、`adapter`、`status`、`stages`、`checks`、`errors`、`duration_s`。

## 4. 实测证据

- 证据文件：`docs/milestones/evidence/M6a-batch-smoke.txt`（sha256 `10a82d3292385a7d3e342c0bfb8b0ad64ea4fd97330d99f66f13eba3f41f6558`，35 行，Lead 独立复跑，含命令与真实输出）
- 关键输出：
  - `batch run --dir examples/batch` → `3 project(s): 2 ok, 0 warn, 1 fail, 0 skipped`，rc=2
  - 坏项目 `demo-broken.yaml`：`fail: <root>: 'engine' is a required property`、`fail: switch/title_id: 'NOT-A-TITLE-ID' does not match '^01[0-9A-Fa-f]{14}$'`；另两个项目不受影响
  - `--json` 报告经 `schemas/batch-report.schema.json` 校验通过（projects=3）
  - `batch diff report report` → added/fixed/regressed 0、`still failing: 1`、`unchanged: 2`，rc=2
  - `batch clean`（无 `--yes`）→ `would remove 3 file(s) ...; pass --yes to delete`，rc=2；`--yes` → 删除，rc=0
  - `pytest` → **367 passed, 63 subtests passed**（M4 基线 344/63；新增 23 个 batch 用例）
- `.gitignore` 已加入 `.galnx/`（报告是本地产物，不入库）

## 4A. M6-b 交付物与实测（2026-10-30，task-30 / audit-package）

### 4A.1 代码与契约

| 文件 | 大小 | 作用 |
| --- | --- | --- |
| `src/galnx/build/config.py` | 5,381 B | manifest `build` 段解析（commands/workdir/artifact/env/timeout_s），`BuildError` |
| `src/galnx/build/executor.py` | 6,801 B | 子进程执行（argv=shell False / 字符串=shell True）、超时、日志截断、产物 sha256 |
| `src/galnx/build/cache.py` | 7,269 B | 缓存 key（canonical JSON + 工具链指纹）、条目读写、命中校验（存在/大小/sha256） |
| `src/galnx/build/lock.py` | 5,258 B | `engine-lock.json` 构建/读写、manifest sha256、漂移比较 |
| `src/galnx/batch/runner.py` | 35,578 B | 追加 `run_batch_build` / `build_project`（lock/cache/build 阶段）与 `collect_lock_entries` |
| `src/galnx/batch/report.py` | 13,904 B | totals 增加 cache_hits/cache_misses/built；diff 增加 `artifact_changed`；clean 统计缓存/日志；summary 打 cache 行 |
| `src/galnx/cli.py` | 36,272 B | 新增 `batch build` / `batch lock` / `build run` 子命令 |
| `schemas/game-manifest.schema.json` | 8,362 B | `build` 段新增 commands/workdir/artifact/env/timeout_s（向后兼容，原有必填不变） |
| `schemas/batch-report.schema.json` | 6,100 B | 新增 totals 缓存计数、`artifact` / `cache` / `commands` 结构（旧报告仍合法） |
| `examples/batch/demo-build.yaml` + `engines/custom-demo.yaml` + `games/demo-build/` | — | 确定性构建演示（内联 `adapter: custom`、`build_backend: none`，仅跑 Python 脚本） |
| `tests/test_build_executor.py` / `test_build_cache.py` / `test_build_lock.py` / `test_batch_build_cli.py` | 8,345 / 6,655 / 3,983 / 10,485 B | M6-b 单测 34 个（合计 24 个类内用例 + 10 个 CLI 用例，见 §4A.3） |
| `docs/batch/README.md` | 11,237 B | 补 M6-b 命令、build 字段表、缓存/锁语义、报告新字段、限制 |

### 4A.2 CLI 语义（M6-b 增量）

- `galnx batch build --dir DIR [--manifest M]... [--recursive] [--skip-preflight] [--skip-output-checks] [--engines-dir D] [--no-cache] [--rebuild] [--locked] [--keep N] [--json]`：在三阶段之后追加 `lock`（仅 `--locked`）、`cache`、`build`；只有声明 `build.commands` + `build.artifact` 的项目才执行命令，未声明的项目在 build 阶段 skip（项目可仍为 ok）。
- `galnx build run --manifest M [--no-cache] [--rebuild] [--engines-dir D] [--json]`：单项目构建，root 取 manifest 所在目录，报告写该目录 `.galnx/`。
- `galnx batch lock --dir DIR [--manifest M]... [--recursive] [--engines-dir D] [--json]`：写 `<root>/.galnx/engine-lock.json`；有 manifest 解析错误时仍写入可解析项目并返回 2。
- 退出码沿用：0 = 无 fail；2 = 存在 fail/参数错误（`--locked` 漂移计 fail）。

### 4A.3 实测证据

- 证据文件：
  - `docs/milestones/evidence/M6b-batch-build.log`（10,041 B，sha256 `04fbe0bcf1dd4a3e85adf6be4ea4cd414c8f2e01df8270caa95654e85bbfccb0`）：`set -x` transcript，7 次真实运行 + 工具链指纹。
  - `docs/milestones/evidence/M6b-batch-build-report.json`（35,479 B，sha256 `9f9a3433f49ba588fe40ab9aa949759a26133aa2443e7da13640968118abf32e`）：run1 的 `latest.json` 原样保存。
- 关键输出（`examples/batch/`，4 个项目：demo-a/demo-b/demo-build 正常 + demo-broken 故意坏）：
  - run1 首次构建：`4 project(s): 3 ok, 0 warn, 1 fail, 0 skipped`，`cache: 0 hit(s), 1 miss(es); built 1`，rc=2（仅 demo-broken schema fail）
  - run2 再跑：`cache: 1 hit(s), 0 miss(es); built 0`，rc=2
  - run3 `--rebuild`：`cache: 0 hit(s), 0 miss(es); built 1`，rc=2
  - run4 删除 `out/demo.bin` 后再跑：demo-build 变 `[WARN]`（`cache.stale`：`artifact missing`），重建，`cache: 0 hit(s), 1 miss(es); built 1`
  - run5 `--no-cache`：不读不写缓存，`built 1`
  - run6 `batch lock`：写 `examples/batch/.galnx/engine-lock.json`（4 个项目，其中 demo-broken 记 error），rc=2
  - run7 `--locked`：`cache: 1 hit(s), 0 miss(es); built 0`，锁验证通过
  - 产物：`out/demo.bin` 91 B，sha256 `3c9b52aafdcfbb5387b20b1c704304276538484afb69a29942206fc097f82c4e`（确定性脚本，重建不变）；cache key `2df60e09c72bd1d8ff3db09d47c2fdd72b96e240cd0cc76f1b31f19536b4f0d1`
- 全量 `pytest`：**401 passed, 63 subtests passed**（M6-a 基线 367/63，新增 34 个 M6-b 用例，全部通过）。
- 真实引擎路线（可选）：本轮未跑 devkitPro 真实 make smoke（`E:/galnx-build/m4-ons` 已有 M4 产物），理由：M6-b 验收只要求构建执行器+缓存+锁定，demo 已覆盖端到端；真实引擎构建由后续引擎准入时按 build.commands 接入。

## 5. 结果与结论

1. 批量预检链路可用：单项目失败不影响其他项目，失败原因结构化进报告与 CLI 输出，可用于 CI。
2. 报告可机器消费（schema 固定）+ 可比较（diff）+ 可清理（clean 保护），为 M6-b 的真实构建报告打了同一套壳。
3. 报告差异五类语义（added/fixed/regressed/still_failing/removed）能在「同一批项目、环境变化、代码变化」之间定位回归。
4. （M6-a 历史结论）`batch run` 不执行任何构建命令：`engines` 阶段只产出 plan，报告字段显式标注未执行。M6-b 的 `batch build` 只执行 manifest 显式声明的 `build.commands`，不执行引擎 plan 的 guidance。
5. 构建缓存以 sha256(canonical JSON) 为 key（manifest 相对路径、引擎 adapter/pinned_commit/build_backend、build 段、input 段、工具链指纹），命中前再校验产物存在/大小/sha256，避免把过期产物当命中。
6. 依赖锁定记录 manifest sha256 + 引擎 pin + 工具链指纹；`--locked` 漂移检测实测可让单项目 fail 而不执行命令，且不影响其他项目。
7. 报告差异新增 `artifact_changed`，可发现「同输入不同产物」的非确定性构建（如 NSP 打包的 RSA-PSS 随机盐）。

## 5A. Lead 独立复核与 M6-c 里程碑判定（2026-10-30）

### 5A.1 独立复核（不采信实现者自报）

复核方式：把 `examples/batch/` 整体复制到 `E:/galnx-build/m6b-verify/`（避免污染仓库），用仓库 CLI 重跑并直接读报告 JSON：

| 项目 | 结果 |
| --- | --- |
| `pytest -q` | **401 passed, 63 subtests**（M6-a 基线 367/63） |
| run1 `batch build --dir . --skip-preflight` | `totals: cache_hits=0, cache_misses=1, built=1`；`demo-build` `[OK]`；`cache.hit=false`，artifact `out/demo.bin` 91 B sha256 `3c9b52aafdcfbb5387b20b1c704304276538484afb69a29942206fc097f82c4e` |
| run2（同输入） | `totals: cache_hits=1, cache_misses=0, built=0`；`cache.hit=true`、key `fc5731c9…b421`、artifact 同上 → **miss→hit 独立复现** |
| `batch lock --dir .` | 写 `.galnx/engine-lock.json`（2,356 B，4 个项目）：`demo-a` krkrsdl2/cmake-switch pin `124bdf84…`、`demo-b` brewser/prebuilt pin `8040580e…`、`demo-build` custom；toolchain `{devkitpro_gcc: aarch64-none-elf-gcc.exe (devkitA64) 16.1.0, cmake: cmake version 4.0.2}`；`demo-broken` 记 `error` 仍写入其余项目（部分成功语义） |
| `batch build --locked` | 锁验证通过（`demo-build` 仍 `cache.hit=true`），坏项目照旧只 fail 自己 |
| 工作区卫生 | 仓库 `git status` 无 `examples/batch/out`/`.galnx` 残留；证据两文件 sha256 复核 = `04fbe0bc…ccb0`（log 10,041 B）与 `9f9a3433…f32e`（report 35,479 B） |

注：复核环境的 cache key（`fc5731c9…`）与实现者记录的 `2df60e09…` 不同，因为 key 包含项目根路径，属预期行为（跨目录不共享缓存）。

### 5A.2 计划 §10 M6 三条验收逐条判定

| # | 计划验收条款 | 判定 | 依据 |
| --- | --- | --- | --- |
| 1 | 批量预检/构建，单项目失败不破坏其他项目 | ✅ 达成（CLI 级） | `batch run`（预检）+ `batch build`（真实构建）均单项目隔离；4 项目含 1 个故意坏 manifest，其余 3 个照常 ok |
| 2 | 构建缓存/依赖锁定、测试报告差异、重新构建、清理工作区 | ✅ 达成（CLI 级） | sha256 缓存 miss→hit、`--rebuild`/`--no-cache`、`batch lock`+`--locked` 漂移检测、`batch diff`（含 artifact_changed）、`batch clean --yes` 清 `.galnx/` |
| 3 | CLI 稳定后再设计 GUI | ⬜ 未开始（按计划后置） | 计划顺序明确；本轮只做 CLI，GUI 不在 M6 完成判定内 |

结论：**M6 完成（CLI 级）**；「GUI」按计划顺序后置，不作为本轮完成条件。M6 与真机/模拟器无关（batch 不启动模拟器、不接触 keys）。

### 5A.3 遗留与下一步（M6 之后）

1. 真实引擎 `build.commands` 接入（krkrsdl2 cmake-switch、ONScripter-NX devkitpro-make、NSP 出包脚本），首次构建后 `batch lock` 固化；
2. CI 门槛：`pytest` + `batch run` + `batch build --locked`（仓库暂未接 CI，属后续）；
3. GUI 设计（后置项，优先级低于引擎接入/真机验证）。

## 6. 未验证与剩余风险

1. 真实引擎（krkrsdl2 / ONScripter-NX / devkitPro make）的 `build.commands` 尚未接入示例：M6-b 只验证了执行器/缓存/锁定本身，真实编译命令需要在引擎准入时逐个固化（并配 `--locked` 锁文件）。
2. 并发未做：当前串行执行；多项目并行构建的日志隔离与资源竞争未设计。
3. 缓存有效性只覆盖 sha256 元数据 + 工具链首行版本；编译器小版本以外（系统库、环境变量、PATH 顺序）不敏感，跨机器命中不保证。
4. 报告保留策略（默认 10 份）在长跑 CI 下需要再评估；写盘已用 tmp+replace 原子替换，但 `latest.json` 与时间戳文件不是同一事务。
5. 依赖锁定的度：只校验本地记录与 manifest/工具链一致性，不校验上游仓库可获取性（离线/上游删除时无法自动发现）。
6. 真实游戏 manifest 的 preflight 需要源目录存在；CI 里只能跑示例项目（当前示例即如此设计）。
7. GUI 未开始（M6-c 由 Lead 按计划后置），当前一切以 CLI + JSON 报告为接口。
8. `batch lock` 遇到坏 manifest 时返回 2（项目计数含 error entry），锁文件仍写入可解析项目；这是有意的「部分成功」语义，CI 需要区分。

## 7. 下一步

1. 引擎接入：为 krkrsdl2 / ONScripter-NX（以及后续 M3 的 NSP 路线）写 `build.commands`，首次构建后 `batch lock` 固化锁文件，CI 用 `--locked` 防漂移。
2. GUI 设计（M6-c 之后的独立项，CLI 稳定后再做）；最小目标=项目列表/预检结果/构建按钮/报告查看。
3. 把 batch 接进仓库 CI（pytest + `batch run --dir examples/batch` + `batch build --dir examples/batch --locked` 作为回归门槛）。

## 8. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-30 | 初稿：记录 M6-a 批量预检/报告 MVP（task-29，audit-package）、Lead 独立验证与证据；M6-b/M6-c 待做 |
| 2026-10-30 | M6-b：真实构建执行（`batch build` / `build run`）、sha256 构建缓存、`engine-lock.json` 依赖锁定；新增 34 个单测（全量 401 passed / 63 subtests）；证据 `M6b-batch-build.log` + `M6b-batch-build-report.json`；M6-c 留 Lead |
| 2026-10-30 | M6-c：Lead 独立复核（cache miss→hit 独立复现、`batch lock`/`--locked` 实测、401 passed/63 subtests）+ 计划 §10 M6 三条验收逐条判定 + 结论 M6 完成（CLI 级）；计划升 v0.8 |
