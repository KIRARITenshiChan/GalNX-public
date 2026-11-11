# FIX-04：未声明 build.inputs 的构建缓存保护

## Task ID

FIX-04（共享任务板 task-64；执行者 async-rca；来源：用户专家复审问题 4，m42143）。

## Source commit

c7d389e（main 分支 HEAD：docs: record GalNX-public snapshot 5 (0.1.0-preview) in the release log）。

测试与端到端实测在包含未提交工作树的该提交上进行；工作树同时包含另一个并发 FIX 任务对 README.md、src/galnx/cli.py、docs/MANIFEST.md 等文件的改动（详见 Deviation 与 Unverified assumptions）。

## Files changed

| 文件 | 类型 | 变更量 | 说明 |
| --- | --- | --- | --- |
| src/galnx/build/cache.py | 修改 | +31 / -5 | 新增「有 build.commands 但未声明 build.inputs 即阻断缓存」判定；cache 段新增 inputs_declared；miss_reasons 复用 blocking+degraded 组合 |
| docs/MANIFEST.md | 修改 | 本任务 +1 行（文件整体 +2 / -0） | 第 42 行新增一条：未声明 build.inputs 的工程不参与缓存。另一行为并发任务的 --yes 说明，非本任务产出 |
| tests/test_build_cache_inputs.py | 修改 | +172 / -1 | 新增 BUILD_SCRIPT、MissingInputsCacheTests（3 个 payload 单测）、BatchMissingInputsCacheCliTests（2 个 CLI 端到端测试） |
| tests/test_batch_build_cli.py | 修改 | 本任务 +1 行（文件整体 +16 / -15） | Deviation：默认 fixture 增加 inputs 一行；其余约 15 处 --yes 为并发任务改动 |
| docs/release/tasks/FIX-04.md | 新增 | 本报告 | — |

未改动：src/galnx/batch/runner.py（现有 blocking 路径已满足需求，见 Decision 4）、src/galnx/build/config.py、schemas/*.json、src/galnx/cli.py、README.md、scripts/。未执行任何 git 写操作。

## Observed problem

build.inputs 缺省为空数组，而缓存 key 只包含「已声明 inputs 的摘要」：一个声明了 build.commands 但没有 build.inputs 的工程照样可以读写构建缓存。第一次构建写入条目后，源文件再变化不会改变 key，第二次构建直接复用旧产物，掩盖了本应触发的重建。专家复审 FIX-04 的要求是：未声明输入时不得复用缓存（安全优先）。

修改前，无 inputs 工程的 payload cache 段恒为：

~~~json
"cache": {
  "miss_reasons": [],
  "blocking_reasons": [],
  "degraded_reasons": []
}
~~~

该 payload 会被写成缓存条目，下一次构建 cache.hit。同时 payload 中没有任何字段能说明 inputs 是否声明，无法从报告层面区分「真的没有输入变化」与「根本没有声明输入」。

验收要求（来自任务描述）：(a) 有 commands 无 inputs 时两次运行都 cache miss、无缓存条目、报告含 cache.miss；(b) 声明 inputs 后 key 随文件内容变化、第二次命中；(c) cache_payload 的 blocking_reasons 含 build.inputs。

## Decision

1. 触发条件：commands_declared = bool(config.has_commands or config.commands)，inputs_declared = bool(config.inputs)；仅当 commands_declared 且 not inputs_declared 时把 "build.inputs is not declared: cache disabled for this project" 追加到 blocking_reasons（并由 miss_reasons = blocking + degraded 自然暴露）。判定放在 cache_payload 内，属于纯函数逻辑，不需要改 runner。
2. 无 commands 的工程不阻断：这类工程走 cache.not_configured，本来就不读不写缓存，再告警只是噪声；保持「只对会执行构建的工程做保护」。
3. CACHE_SCHEMA_VERSION 保持 2（不升版）：blocking 判定发生在 runner 读写缓存之前，旧条目不需要整体失效；升版会同时废弃全部旧条目，却并不比 blocking 逻辑多提供任何安全性。代价是 cache 段新增 inputs_declared 字段会让所有项目的 payload key 改变一次，即所有工程一次性重建（已写入 Known limitations，发布说明可提及）。
4. runner.py 不改：现有实现已经正确消费 blocking_reasons。src/galnx/batch/runner.py:796-800 在 blocking 非空时生成 cache.miss（warn，detail 为 blocking 拼接）并返回 {"hit": False, "key": "", "payload": None}；:893-896 的 _build_stage 只在 key 非空且 payload is not None 时 write_cache_entry，因此 blocker 情形既不读也不写缓存。任务描述第 ② 项「确认」即此结论。
5. 诊断字段：payload 的 cache 段新增布尔 inputs_declared，便于测试与诊断；batch-report 的 project.cache 仍只暴露 hit/key（schemas/batch-report.schema.json:187-202），报告 schema 不受影响。
6. 测试策略：3 个 payload 单测覆盖判定矩阵（缺失/已声明/无 commands），2 个 CLI 端到端测试覆盖验收 (a)(b)，并断言无缓存条目与 key 随内容变化。

## Behavior before

- 有 commands、无 inputs 的工程：cache 段 blocking/miss 均空；build.inputs.state 为 ok（未声明不等于缺失）；第一次构建写入缓存条目；第二次构建 cache.hit，即使源文件已变化也不重建（安全缺陷）。
- payload 不含 inputs_declared，无法从数据上判断工程是否声明了输入。
- 声明了 inputs 的工程：正常 miss 后 hit（本次不改变该路径行为）。
- 无 commands 的工程：不缓存（本次不改变该路径行为）。

## Behavior after

- 有 commands、无 inputs 的工程：每次运行 project.cache 为 {"hit": false, "key": ""}；checks 含 cache.miss（status warn，detail = "build.inputs is not declared: cache disabled for this project"）；.galnx/cache 下不产生任何 meta.json；totals.cache_hits = 0、totals.built = 1（blocked 不计入 cache_misses，见 Known limitations 1）。
- 声明 inputs 的工程：首次 cache.miss 并写入条目；第二次 cache.hit；被声明文件内容变化后 key 变化并再次 miss，随后再 hit。
- 无 commands 的工程：不阻断（blocking 为空，不产生 cache.miss 警告）。
- 实测的 payload 片段（声明 inputs 后，本机环境）：

~~~json
"cache": {
  "miss_reasons": [],
  "blocking_reasons": [],
  "degraded_reasons": [],
  "inputs_declared": true
}
~~~

- 端到端实测（临时工程，commands=[python build.py --out out/demo.bin]）：
  - 未声明 inputs，第 1/2 次：cache {"hit": false, "key": ""}，cache_hits 0 / cache_misses 0 / built 1，check cache.miss (warn) 含上述文案，.galnx/cache 条目数 0；两次结果一致。
  - 声明 inputs=[{"path": "build.py", "kind": "file"}] 第 1 次：key 为 aba6163868d2015ce186c6a90b29397e05fd6f454a30f8bb007abf3ed62ed3b6，cache.miss，条目 1；第 2 次：cache.hit，cache_hits 1 / built 0。
  - 给 build.py 追加一行后第 1 次：key 变为 824d266f30dc7238e1c466f9ec1e1f641e6a85d06653825c12216addc2046ac6，cache.miss，条目 2；第 2 次重新 hit。
  - 本机 toolchain 版本探测未知，实测会出现额外的 cache.degraded warn（degraded toolchain: unknown version for devkitpro_gcc），与本改动无关；blocking 文案仍只来自 blocking_reasons。

## Tests added

| 测试 | 覆盖 |
| --- | --- |
| tests/test_build_cache_inputs.py:394 MissingInputsCacheTests.test_payload_blocks_cache_when_inputs_are_missing | 验收 (c)：无 inputs + 有 commands 时 inputs_declared=False、blocking_reasons==[REASON]、miss_reasons==[REASON]，且 build.inputs.state 仍为 ok |
| tests/test_build_cache_inputs.py:409 MissingInputsCacheTests.test_payload_not_blocked_once_inputs_are_declared | 声明 inputs 后 blocking/miss 为空、inputs_declared=True |
| tests/test_build_cache_inputs.py:424 MissingInputsCacheTests.test_payload_without_commands_is_not_blocked | 无 commands 时不误报 |
| tests/test_build_cache_inputs.py:502 BatchMissingInputsCacheCliTests.test_undeclared_inputs_always_miss_and_write_no_cache | 验收 (a)：两次 CLI batch build 都 cache.miss warn、无 cache.hit、key 为空、totals.cache_hits 0、built 1、.galnx/cache 无条目 |
| tests/test_build_cache_inputs.py:519 BatchMissingInputsCacheCliTests.test_declared_inputs_miss_then_hit_and_follow_content | 验收 (b)：声明 inputs 后首次 miss 写 1 条、二次 hit；改文件后 key 变、条目 2；再次 hit |

测试夹具：BUILD_SCRIPT（:376）、MissingInputsCacheTests（:389）、BatchMissingInputsCacheCliTests（:433），REASON 常量分别为 :392 与 :436，CLI 辅助方法 setUp/write_manifest/run_cli/build_report/cache_entries 位于 :438-500。tests/test_batch_build_cli.py:59 的默认 fixture 增加一行 inputs（Deviation），使该文件原有 miss→hit、stale 测试在新规则下继续有意义。

## Commands

在工作树根目录执行（Windows，bash，Python 3.12，PYTHONPATH=src）：

- 目标测试：PYTHONPATH=src python -m pytest -q tests/test_build_cache.py tests/test_build_cache_inputs.py tests/test_batch_build_cli.py
- 相邻回归：PYTHONPATH=src python -m pytest -q tests/test_batch_cli.py tests/test_batch_runner.py tests/test_manifest.py
- 环境前置：mkdir -p /c/Users/ACETaffy/AppData/Local/Temp/galnx-build（见 Test results 的环境性失败说明）
- 说明：并发任务给 build run / batch build 加上非交互保护后，CLI 测试统一带 --yes；本任务新增测试同样带 --yes。

## Test results

- 目标三文件：41 passed in 5.26s（包含既有 test_build_cache.py、test_build_cache_inputs.py 原 17 个用例、test_batch_build_cli.py 全部用例，以及本任务新增 5 个用例）。
- 相邻回归三文件：24 passed in 1.30s。
- 全量 pytest：未运行（工作区含并发任务改动、全量耗时较长，且本任务只触碰 build 缓存与对应文档/测试）；如需发布前兜底，建议由 Lead 在合并后跑一次全量。
- 环境性失败（非本任务回归，已排除）：tests/test_batch_runner.py::test_healthy_project 在未创建默认 BUILD_ROOT 目录时失败（stages["preflight"] 为 warn）。根因是 src/galnx/paths.py:70-76 默认 BUILD_ROOT = tempfile.gettempdir()/galnx-build，本机该目录不存在，src/galnx/batch/doctor.py:163-169 的 check_build_root 返回 warn（directory does not exist yet）。未触碰 batch/preflight/doctor/paths；创建空目录后该文件 8 passed，相邻三文件整体 24 passed。已保留该空目录。

## Unverified assumptions

- 假定「有 commands 且无 inputs」是唯一需要阻断的情形；无 commands 的 plan-only 工程不提示，是产品判断，未与发布负责人确认。
- 假定 runner 是缓存读写唯一闸门：已 grep 确认 cache_payload 的源码调用点只有 src/galnx/batch/runner.py:793（其余为 build/__init__.py 导出与测试直调），CLI batch build / build run 均经 runner。
- 假定 batch-report 的消费方只使用 project.cache 的 hit/key（schema 只声明这两个字段），不依赖 payload 内部新增字段；payload 内容变化对外不可见的假设未做外部消费方调查。
- 假定一次性 key 变化（所有项目重建一次）可接受；未与发布负责人确认是否需要在发布说明中提示。
- 仅在 Windows + Python 3.12 实测；逻辑为纯 Python，无平台相关分支，但未在 Linux/macOS 复跑。
- 未验证旧缓存条目在 key 变化后的处置策略：不升 schema，旧条目留在磁盘但不会被命中，未实现主动清理。

## Known limitations

1. totals.cache_misses 不计入被阻断的项目：runner.py:519-525 只统计 cache 为 dict、非 hit 且 key 非空的项目；blocked 项 key 为空，因此只出现在 checks(cache.miss warn)、project.cache 与 totals.built 中。为保持最小改动与既有报告语义，本次不改 totals；新测试用 check 文案、空 key 与无缓存条目来断言，而不是 cache_misses。
2. 保护只发生在 build 阶段缓存读/写路径；preflight、doctor、lock 校验等不受影响（这些阶段不读写 .galnx/cache）。
3. 报告层面只能通过 cache.miss 的 detail 区分「未声明输入被阻断」与普通「首次 miss」；payload 内的 inputs_declared 不进 batch-report schema。若后续需要机器可读原因，应另立任务扩展报告 schema。
4. 工程显式声明 inputs=[]（空数组）等同未声明，会按新规则阻断；这是有意行为（空输入集无法描述构建输入），但文档未专门强调。
5. 本机环境会出现 cache.degraded warn（toolchain 版本未知），与本修复无关；测试只在声明场景中容忍其存在，不把 degraded 当作阻断。
6. 未跑全量测试；并发任务的 cli.py / README / 其他 FIX 文件与本次改动一起工作，最终回归归属需由 Lead 合并后确认。

## Rollback

- 代码：git checkout -- src/galnx/build/cache.py（若该文件没有其他任务的改动），或手工回退四处：_cache_reason_sections/_cache_miss_reasons 的 keyword-only 参数与 blocking 追加（:330-354、:370-380），cache_payload 的 commands_declared/inputs_declared 计算（:411-418），cache 段的 inputs_declared 字段（:432-440）。回退后 key 会再次改变（少一个字段），所有项目一次性重建；无需清理 .galnx/cache，旧条目自然不再命中。
- 文档：删除 docs/MANIFEST.md:42 本任务 bullet（保留并发任务在 :61 附近新增的「非交互不默认放行」bullet）。
- 测试：删除 tests/test_build_cache_inputs.py:376-545 新增块（BUILD_SCRIPT + 两个测试类）与文件顶部为此新增的 import；删除 tests/test_batch_build_cli.py:59 的 inputs 一行。
- 无数据迁移、无 schema 变更、无持久化状态，回滚后不需要额外清理。

## Deviation

- tests/test_batch_build_cli.py 不在任务给出的写入范围内，但本任务只增加 1 行 fixture（:59，project_manifest 默认 build 增加 "inputs": [{"path": "build.py", "kind": "file"}]）。原因：任务验收 ⑤ 要求该文件的测试通过，而新规则会让该文件原有的 miss→hit 与 stale 测试失败；把默认 fixture 的 build.py 声明为输入可保留这些测试原意。请 Lead 在提交时知悉并批准这一行；若不允许，需把这些测试改为显式声明 inputs。
- 该文件其余 diff（约 15 处 --yes）与 docs/MANIFEST.md 的另一条 bullet 来自并发 FIX 任务，不是本任务产出；src/galnx/cli.py、README.md 等并发文件未被本任务修改。
- 未改 src/galnx/batch/runner.py 是判断而非偏差：任务描述第 ② 项只要求确认 blocking 路径行为，现有实现已满足。
- schema 不升版为任务允许的自判（描述写明「是否升版自判并说明」），理由见 Decision 3。

## 附录

### A. payload 前后对比

修改前（无 inputs、有 commands）：

~~~json
"cache": {
  "miss_reasons": [],
  "blocking_reasons": [],
  "degraded_reasons": []
}
~~~

修改后（同一工程）：

~~~json
"cache": {
  "miss_reasons": ["build.inputs is not declared: cache disabled for this project"],
  "blocking_reasons": ["build.inputs is not declared: cache disabled for this project"],
  "degraded_reasons": [],
  "inputs_declared": false
}
~~~

声明 inputs 后：blocking_reasons 与 degraded_reasons 为空，inputs_declared 为 true；key 随被声明文件内容变化（本次实测 aba6163868d2015c… → 824d266f30dc7238…）。

### B. 关键行号索引

| 位置 | 内容 |
| --- | --- |
| src/galnx/build/cache.py:29 | CACHE_SCHEMA_VERSION = 2（未升版） |
| src/galnx/build/cache.py:330 | _cache_reason_sections 定义；:333-336 keyword-only 参数 |
| src/galnx/build/cache.py:350-354 | commands 已声明但 inputs 未声明时追加 blocking（文案 :352） |
| src/galnx/build/cache.py:370-380 | _cache_miss_reasons 透传两个标志 |
| src/galnx/build/cache.py:411-418 | cache_payload 计算 commands_declared / inputs_declared 并调用 |
| src/galnx/build/cache.py:432-440 | cache 段：miss_reasons/blocking_reasons/degraded_reasons/inputs_declared（:435、:438） |
| docs/MANIFEST.md:42 | 未声明 inputs 不参与缓存的说明 |
| tests/test_build_cache_inputs.py:376 | BUILD_SCRIPT |
| tests/test_build_cache_inputs.py:389 / :392 | MissingInputsCacheTests / REASON |
| tests/test_build_cache_inputs.py:394 / :409 / :424 | 3 个 payload 单测 |
| tests/test_build_cache_inputs.py:433 / :436 | BatchMissingInputsCacheCliTests / REASON |
| tests/test_build_cache_inputs.py:502 / :519 | 2 个 CLI 端到端测试 |
| tests/test_batch_build_cli.py:59 | Deviation：fixture inputs 一行 |
| src/galnx/batch/runner.py:793 | cache_payload 唯一源码调用点 |
| src/galnx/batch/runner.py:796-800 | blocking 非空 → cache.miss warn、hit False、key 空、payload None |
| src/galnx/batch/runner.py:893-896 | 仅 key 非空且 payload 非 None 时写缓存 |
| src/galnx/batch/runner.py:519-525 | totals.cache_misses 定义（不含 blocked） |
| schemas/batch-report.schema.json:187-202 | project.cache 仅 hit/key |

### C. 元信息

- 执行时间：2026-11-11（Asia/Shanghai）。
- 工作树 HEAD：c7d389e；本报告所述测试在该 HEAD + 本任务与并发任务未提交改动上运行。
- 本任务未执行 git add/commit/push 或任何 git 写操作；未新建除本报告外的文件。
