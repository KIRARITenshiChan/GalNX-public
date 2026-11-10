# TASK-CACHE 任务报告

> GalNX 0.1 Preview 收敛整改 / 专家计划 P1-1：让构建缓存真正对构建输入敏感。
> 本文件是任务交付报告；代码改动见同工作区 git diff（未提交，由 Lead 统一提交）。

## Task ID
TASK-CACHE（共享任务板 task-60；执行者 async-rca）

## Source commit
974a414（main 分支；本报告中的测试与示例均基于该提交 + 当前未提交工作树）

## Files changed

| 文件 | 类型 | 变化 |
| --- | --- | --- |
| src/galnx/build/cache.py | 已跟踪修改 | +295/-11，当前 495 行：新增输入摘要、toolchain 指纹扩展、schema v2、degraded/missing 原因 |
| src/galnx/build/config.py | 已跟踪修改 | +127，当前 276 行：新增 BuildInput/BuildConfig.inputs/toolchain_components 与严格校验（其中约 25 行为并发任务的 has_commands/execution_state 扩展，非本任务产出） |
| schemas/game-manifest.schema.json | 已跟踪修改 | +98/-1，当前 399 行：本任务约 +49 行为 build.properties.inputs 与 toolchain_components；其余约 +49 行为并发任务的 commands↔artifact 成对 allOf 校验，非本任务产出 |
| tests/test_build_cache.py | 已跟踪修改 | +49，新增 2 个测试（旧 schema 拒绝、payload 新结构） |
| tests/test_build_cache_inputs.py | 新增（未跟踪） | 374 行，17 个测试 |
| docs/release/tasks/TASK-CACHE.md | 新增 | 本报告 |

Scope 遵守：
- 只改了上述 write scope 内文件；未触碰 README.md、docs/MANIFEST.md、src/galnx/cli.py、src/galnx/batch/runner.py、examples/engines/*、src/galnx/build/__init__.py。
- runner.py 需要的最小改动见附录 C，由 Lead 实施（该文件是 Lead write scope）。
- docs/MANIFEST.md 需要的文档文字见附录 D，由 Lead 合并。
- 仓库根出现未跟踪文件 _dbg_batch.py（非本任务创建，未处理）。
- 未执行任何 git 写操作；仅使用 git status/diff/numstat 只读命令。

## Observed problem

v1 缓存键（CACHE_SCHEMA_VERSION=1）实际只覆盖：

- manifest 路径（Path(manifest_ref).as_posix()，不是文件内容）；
- engine 三字段：adapter / pinned_commit / build_backend；
- build.commands / workdir / artifact / env / timeout_s；
- manifest 的 input 段（游戏输入配置）；
- toolchain：仅 devkitpro_gcc 与 cmake 两条 --version 首行。

由此产生的误命中/误读风险：

1. 同一路径下源码内容变化（例如 src/ 或补丁文件被改写、git 切换分支）时缓存仍命中，复用旧产物。
2. Rust/Cargo、ninja、SDL2、FFmpeg 源码或版本变化时缓存仍命中；只有 gcc/cmake 首行变化才会失效。
3. 旧 schema 条目没有 schema_version 拒绝逻辑：v1 meta.json 会被新代码当作有效条目读取，结构漂移时静默产生错误 payload/验证结果。
4. build 段在 schema 中 additionalProperties:false，若不同步 schema，manifest 无法声明新输入字段。

## Decision made

1. 新增 manifest build.inputs 显式清单（向后兼容，缺省为空数组）。元素 {path, kind: file|tree（默认 tree）, optional: bool（默认 false）, ignore: [glob...]}。相对路径按 manifest 所在目录解析，绝对路径原样接受。config.py 严格校验：非数组、未知 key、空 path、非法 kind、非 bool optional、非字符串 ignore 均报 BuildError（例如 "build.inputs[0]: unknown key(s): foo"）。
2. 确定性输入摘要 build_inputs_digest(config, base)：tree 用 os.scandir 递归收集，子项按名称 UTF-8 字节序排序，最终 entries 再按相对 POSIX 路径 UTF-8 字节序排序；每个条目记录 {path, type, sha256, size}（普通文件 type=file、内容 sha256；symlink 记 type=symlink、对 target 字符串 sha256、size=0）；任意层级永远跳过 .git 与 .galnx；ignore 用 fnmatch 匹配（pattern 反斜杠归一为 /；以 / 结尾只匹配目录；可匹配相对路径或 basename），命中目录则整棵剪枝；tree_digest = sha256(canonical_json({"kind": "tree", "entries": entries}))；单文件 kind=file 时 digest=sha256_file，entries 只含一个 {path: 文件名, type: file, ...}。
3. 状态与降级：optional=false 且路径不存在 -> spec.state=missing，顶层 inputs.state=missing、missing 列表记录路径；optional=true 且缺失 -> state=optional-missing（不影响 miss 判定）；扫描 OSError -> state=error，顶层 unreadable 记录。所有 spec 仍保留在 payload 中，便于诊断。
4. toolchain 指纹扩展为 8 个 flat key：devkitpro_gcc、cmake、ninja、rustc、cargo（各取 --version 首行）、sdl2（先找 devkitPro 下 portlibs/switch/lib/pkgconfig 与 msys2/mingw64/lib/pkgconfig 的 sdl2.pc/SDL2.pc 解析 Version:，兜底 pkg-config --modversion sdl2）、ffmpeg_source_commit（GALNX_FFMPEG_SRC 指向 git 仓库时 git -C <src> rev-parse HEAD，否则 unknown）、host_platform（sys.platform + platform.machine()）。best-effort，任何失败记 "unknown"。payload 中另有结构化 host_platform 字段 {"platform", "machine"}。
5. toolchain_components：manifest build.toolchain_components 缺省 ("devkitpro_gcc", "cmake", "ninja")（config.DEFAULT_TOOLCHAIN_COMPONENTS）。payload.toolchain = {components, versions, unknown（值为 unknown 的 key 排序列表）, degraded（components 中版本 unknown 的列表）}。payload.cache.miss_reasons 由 _cache_miss_reasons 生成，文案：
   - "degraded toolchain: unknown version for <逗号列表>"
   - "required build input missing: <列表>"
   - "build input unreadable: <列表>"
   未声明分量（如 rustc/sdl2/ffmpeg_source_commit）unknown 不会进入 degraded。
6. 强制 miss 的落点：cache.py 只负责计算与记录原因，不在 read_cache_entry 里拒绝 degraded 条目（保持既有 read 语义：只拒绝 schema_version 不等于当前值）。原因：
   - v1 单测与 runner 的 round-trip 语义要求 read_cache_entry 对结构正常条目返回 entry；
   - 强制 miss 属于批次策略，放在 runner 的 _cache_stage 最合适，且不用改 build/__init__.py 的导出（scope 外）。
   runner 最小 diff 见附录 C：读取 payload.cache.miss_reasons，非空则输出 cache.miss（warn）并返回 payload=None，从而 _build_stage 不写缓存条目（缓存保持"不记录降级结果"）。
7. CACHE_SCHEMA_VERSION 提升到 2：
   - read_cache_entry：非文件 / JSON 解析异常 / 非 dict / key 不匹配 / schema_version != CACHE_SCHEMA_VERSION -> 返回 None（安全失效，不抛异常）；
   - verify_cache_entry：schema_version != 2 时返回 (False, "cache entry schema_version <实际值> != 2")，之后才做 artifact 存在性/size/sha256 校验；
   - write_cache_entry：写入 schema_version=2。
8. cache_payload 增加可选 root 参数（相对 inputs 的解析基准；未传时用 manifest 路径所在目录）。新增 payload 键：inputs、toolchain（结构化）、host_platform、cache.miss_reasons；保留旧 input 段（游戏输入配置）以兼容。新增公开函数 build_inputs_digest / host_platform，但未加入 src/galnx/build/__init__.py 的 __all__（该文件是他人 scope）；runner 不需要调用它们，只读 payload 字段即可。

## Behavior before

- 缓存键 = sha256(canonical_json(payload_v1))；payload_v1 键：schema=1、manifest（路径）、engine、build（commands/workdir/artifact/env/timeout_s）、input、toolchain（仅 devkitpro_gcc/cmake 两条版本首行）。
- 同路径改源文件/补丁：key 不变 -> 命中旧产物（错误复用）。
- 改 Cargo.lock、ninja/Rust/SDL2/FFmpeg 输入：key 不变 -> 命中旧产物（错误复用）。
- 读取旧条目：read_cache_entry 不检查 schema_version，v1 meta.json 会被读出并参与 verify。
- 命中/未命中原因只有 cache.hit / cache.miss / cache.stale / cache.disabled / cache.rebuild / cache.not_configured，没有 degraded/missing 概念。

## Behavior after

- payload_v2 键：schema=2、manifest、engine、build、input、inputs{state, missing, unreadable, specs[...]}、toolchain{components, versions, unknown, degraded}、host_platform{platform, machine}、cache{miss_reasons}。
- 同一目录下改被跟踪源文件（同长度改字节也一样）、改 kind=file 的补丁、改声明为 inputs 的 Cargo.lock / ffmpeg configure 参数文件 -> digest 变化 -> key 变化 -> miss。
- 只改未声明进 inputs 的文档 -> key 不变 -> 仍命中。
- 产物被截断或改写 -> verify_cache_entry 返回 False（"artifact size changed ..." / "artifact sha256 changed ..."）-> runner 记 cache.stale 后重建。
- 读 schema_version=1 的旧条目 -> 返回 None / verify False，不抛异常；旧缓存全部安全失效。
- 声明分量（如 ninja）版本 unknown -> payload.toolchain.degraded 非空、payload.cache.miss_reasons 含 "degraded toolchain: ..."；optional=false 输入缺失 -> inputs.state=missing、miss_reasons 含 "required build input missing: ..."；optional=true 缺失不产生原因。
- 正常输入 + 全部声明工具链 known：payload.cache.miss_reasons 为空，缓存正常工作。
- 端到端实测（临时目录假构建工程，执行两次 galnx batch build --json）：
  - 第 1 次：cache.miss（"no cached artifact for key 5dc333da98d0a898"）+ build.cache ok；
  - 第 2 次：cache.hit（"out/demo.bin (14 bytes, sha256 588d04c9...)"），key 相同 5dc333da98d0a898 -> 证明 v2 schema + 新指纹下 miss->hit 链路正常。
- 注意：项目状态仍显示 warn，唯一非常规 check 是 engine.status（并发任务的引擎 research 标记），与本缓存改动无关（见附录 F）。

## Tests added

### tests/test_build_cache_inputs.py（新增，17 个测试）

映射需求 7 的验收点：

| 需求/验收点 | 测试 |
| --- | --- |
| 内容不变 -> hit（key 相同 + write/read/verify 往返） | test_unchanged_inputs_hit_and_round_trip |
| 同路径改被跟踪源文件 -> miss | test_changed_tracked_source_misses（同长度 aaaa -> bbbb） |
| 改补丁文件 -> miss | test_changed_patch_file_misses |
| 改 Cargo.lock / ffmpeg configure 参数文件（声明为 inputs）-> miss | test_changed_manifest_inputs_miss |
| 只改未跟踪无关文档 -> hit（key 不变） | test_untracked_document_does_not_invalidate |
| 产物被截断/改写 -> 校验失败并 miss | test_artifact_corruption_fails_verification（size changed 与同长度 sha256 changed 两种） |
| 旧 schema -> miss 不异常 | test_old_schema_entry_is_ignored_not_fatal |
| 声明工具链分量 unknown -> miss 原因 | test_declared_degraded_toolchain_component_misses（ninja=unknown；并把 components 缩到两项时无 degraded） |
| 未声明分量 unknown 不阻断 | test_undeclared_unknown_component_does_not_block（rustc/sdl2 unknown，默认三分量 known） |
| optional=false 缺失 -> miss | test_missing_required_input_misses |
| optional=true 缺失 -> 不影响其它输入 | test_optional_missing_input_does_not_invalidate |
| ignore 模式 + entries 排序确定性 | test_tree_ignores_and_deterministic_order（.git/.galnx 恒跳过；*.o、target/ 忽略；entries 顺序固定；两次 key 相同） |
| payload 含 host_platform 与 miss_reasons 槽位 | test_payload_contains_host_platform_and_miss_reason_slot |
| config 解析严格校验 | test_config_parser_rejects_bad_inputs（非法 kind、缺 path、未知 key、空 toolchain_components；kind=file+optional=true 可解析） |
| schema：旧 manifest 仍通过 | test_manifest_without_inputs_still_validates |
| schema：带 inputs/toolchain_components 通过 | test_manifest_with_inputs_and_components_validates |
| schema：坏 input 声明被拒（循环 4 个反例：非法 kind、缺 path、未知 key、ignore 含空串） | test_bad_input_declarations_are_rejected（subTest） |

实现细节：全部使用 tmp_path/临时目录假数据，不触碰真实游戏资源；setUp 中 mock.patch("galnx.build.cache.fingerprint_toolchain", return_value=HEALTHY)，HEALTHY 含 8 个 key 且全部非 unknown，保证测试确定性、不依赖本机工具链；schema 测试使用 Draft202012Validator + FormatChecker，路径为仓库根 schemas/game-manifest.schema.json。

### tests/test_build_cache.py（原有文件，补 2 个测试）

- test_read_and_verify_reject_old_schema_entries：手写 schema_version=1 的 meta.json -> read_cache_entry 返回 None；verify_cache_entry 返回 (False, 含 "cache entry schema_version" 的文案)，不抛异常。
- test_payload_includes_inputs_and_toolchain_sections：config 含 inputs 与 toolchain_components 时，payload["schema"]==2、inputs.state=="ok"、toolchain.components/degraded 正确、host_platform 有 platform、cache.miss_reasons 为空。

## Commands executed

在仓库根 E:/Othergames/Nintendo Switch/Workspace/GalNX（bash: /e/Othergames/Nintendo Switch/Workspace/GalNX）执行：

1. PYTHONPATH=src python -m pytest -q tests/test_build_cache.py tests/test_build_cache_inputs.py
2. PYTHONPATH=src python -m pytest -q tests/test_build_cache.py tests/test_build_cache_inputs.py tests/test_build_lock.py tests/test_build_executor.py tests/test_batch_build_cli.py tests/test_batch_runner.py tests/test_batch_report.py tests/test_batch_cli.py tests/test_manifest.py tests/test_input_manifest.py
3. PYTHONPATH=src python -m pytest -q（全量，后台执行，日志 /tmp/galnx_full_pytest_cache.txt）
4. python -c "import json; d=json.load(open('schemas/game-manifest.schema.json', encoding='utf-8')); ..."（schema JSON 合法性与 build.properties 键顺序检查）
5. 临时目录端到端脚本：构造假构建工程，连续两次调用 cli.main(["batch","build","--dir",...,"--json"])，对比 cache.miss -> cache.hit。
6. 临时目录 payload 示例脚本：parse_build_section + cache_payload(root=...) + cache_key，生成附录 A/B 的示例与被脱敏的路径。
7. git status --short / git diff --stat / git diff（只读，检查改动范围与并发改动归属）。
8. 未执行任何 git 写操作、未构建 NSP、未启动 Citron/模拟器。

## Test results

| 运行 | 命令 | 结果 |
| --- | --- | --- |
| 缓存相关单测 | 命令 1 | 26 passed in 0.51s（新增 17 + 原有 7 + 补 2） |
| 构建/批次/清单子集 | 命令 2 | 6 failed, 98 passed, 3 subtests passed in 26.72s；6 个失败全部是并发任务的 batch 报告断言，见附录 F；缓存相关测试全绿 |
| 全量 | 命令 3 | 23 failed, 622 passed, 57 subtests passed in 162.98s（17 FAILED + 6 SUBFAILED）；失败分布：tests/test_batch_*（6）、tests/test_engines_*（9 FAILED + 6 SUBFAILED）、tests/test_public_release.py（2）；tests/test_build_cache*.py、test_build_lock.py、test_build_executor.py、test_manifest.py、test_input_manifest.py 全部通过 |
| 端到端缓存往返 | 命令 5 | run1: cache.miss + build.cache ok（key 5dc333da98d0a898）；run2: cache.hit，key 相同；证明 v2 键在同机可稳定命中 |
| schema 合法性 | 命令 4 | JSON 可解析；build.properties 末尾键为 timeout_s、inputs、toolchain_components |

补充说明：会话早期（队友 WIP 未完成时）全量曾出现 61 failed / 4 errors（engines/descriptor.py 的 _capability_problems NameError 等），系并发编辑中间态；以上表为最终稳定测量值。全量中没有任何失败落在本任务新增或修改的测试上。

## Unverified assumptions

1. 运行时强制 miss 尚未生效：当前工作树的 runner.py 仍是旧逻辑，只读 key/entry；payload.cache.miss_reasons 已计算并写入 payload，但直到 Lead 应用附录 C 的 diff 前，degraded/missing 不会阻止缓存命中（tests 只验证 payload 中的原因字段，不验证 runner 行为——runner 不在本任务 write scope）。这是交付后的第一优先接手事项。
2. 仓库内没有声明 build.inputs 的真实游戏 manifest：examples/engines/* 属他人 scope，本任务未修改；在真实 manifest 补充 inputs 前，真实构建的缓存键仍只随旧字段变化（升级本身会因 schema=2 让所有历史条目一次性 miss）。
3. sdl2 版本探测依赖 devkitPro MSYS2 的 pkg-config .pc 布局猜测（portlibs/switch/lib/pkgconfig、msys2/mingw64/lib/pkgconfig），未在真实 devkitPro 安装上逐一验证两种布局；缺失时按 unknown 处理且默认 components 不含 sdl2，不影响默认命中。
4. ffmpeg_source_commit 仅在 GALNX_FFMPEG_SRC 指向 git 仓库时有效；未设置时 unknown，默认 components 不含它，不阻断命中。
5. host_platform 记录的是当前 Python 解释器平台（sys.platform + platform.machine()），未使用交叉编译目标三元组；对同机缓存是正确的。
6. 工具链指纹为 --version 首行截断；若某工具版本输出格式变化（前缀/多行），指纹字符串会变，导致一次性 miss（安全方向）。
7. schema 中 commands↔artifact 成对 allOf 校验是并发任务新增；本任务的 3 个 schema 测试验证了新旧 manifest 在该 allOf 存在时通过/拒绝行为，但未覆盖所有组合。
8. build.toolchain_components 的值未限制为已知指纹 key：声明拼错的名字会得到 versions 里缺失 -> 视为 unknown -> degraded（安全方向，但会在 miss_reasons 中暴露拼写）。

## Known limitations

- 树摘要每次缓存查找都读取全部文件内容（不做 mtime/size 捷径），这是确定性的代价；对巨大目录（例如把整个游戏资源目录声明为 tree）会明显变慢，建议只声明真正影响构建的窄输入（src/、patches/、Cargo.lock、构建脚本等）。
- 扫描不是原子快照：若在哈希过程中文件被同时改写，可能得到混合摘要；实现未加双遍校验。
- ignore 使用 fnmatch，不是完整 gitignore：不支持取反前缀 !、不支持 ** 递归语义；basename 匹配可能忽略嵌套同名目录；pattern 以 / 结尾仅匹配目录。
- 始终跳过任意层级的 .git 与 .galnx，但不会自动跳过其它 VCS 目录（.hg/.svn 等），需要 manifest 自行 ignore。
- tree 只记录文件（含 symlink 的 target 字符串），空目录不进入摘要；symlink 不解析目标内容（避免循环）。
- toolchain.versions 中同时含 host_platform 字符串，payload 顶层另有结构化 host_platform；信息重复但便于 lock 与巡检。
- schema 版本从 1 升到 2 会让所有旧缓存条目一次性失效（安全设计，非 bug），首次全量构建会变慢。
- 未在 build/__init__.py 导出 build_inputs_digest/host_platform/DEFAULT_TOOLCHAIN_COMPONENTS；外部 CLI/工具若想直接使用，需要 Lead 在该文件补充 import 与 __all__。
- read_cache_entry 不重新计算 entry.key_payload 的哈希（只比较 key 文件名/字段），理论上磁盘篡改且 key 匹配时可绕过；本次未扩展校验范围。

## Rollback method

1. 分任务回滚（推荐，因工作树混合多个任务改动）：由 Lead 在分任务提交后，对以下文件只回退本任务的 hunk：src/galnx/build/cache.py、src/galnx/build/config.py（注意保留并发任务的 has_commands/execution_state 与 commands↔artifact 校验）、schemas/game-manifest.schema.json（保留并发任务的 allOf 段）、tests/test_build_cache.py（保留原有测试）。
2. 直接整体回退（如果本任务单独提交）：git checkout -- src/galnx/build/cache.py src/galnx/build/config.py schemas/game-manifest.schema.json tests/test_build_cache.py；删除 tests/test_build_cache_inputs.py 与 docs/release/tasks/TASK-CACHE.md。
3. 缓存无需迁移：回滚后 read_cache_entry 只接受 schema_version=1，已写出的 v2 条目会被当作未知条目返回 None（安全 miss）；建议同时删除构建根下的 .galnx/cache/（缓存可随时重建，无持久数据）。
4. manifest 兼容性：无新字段的旧 manifest 在新 schema 下仍通过；若已写入了带 build.inputs/toolchain_components 的新 manifest，回滚 schema 后这些字段会因 additionalProperties:false 被拒绝，需要同时回滚这些 manifest 声明。
5. 无环境/依赖变化（未引入新依赖），回滚不涉及依赖安装。

## 附录 A：输入摘要示例 JSON（截断）

以下为临时目录假工程的实际 payload 片段（个人目录已脱敏为相对路径）：

~~~json
{
  "schema": 2,
  "manifest": "project/manifest.json",
  "inputs": {
    "state": "ok",
    "missing": [],
    "unreadable": [],
    "specs": [
      {
        "path": "src",
        "kind": "tree",
        "optional": false,
        "ignore": ["*.o", "target/"],
        "state": "ok",
        "digest": "000c3d42636d48a105fe7bc2bb1ca7f16f19619f298f3df02f8d942103a1c2c1",
        "entries": [
          {"path": "a.c", "type": "file", "sha256": "172c7228fff621cc9396d19cc8cf70b2d813bdc83f66eacd34b14e3afbf1a272", "size": 8},
          {"path": "sub/b.h", "type": "file", "sha256": "525ba263486540bb2749b5db788e790142303044542f053f02947455fb83c326", "size": 13}
        ],
        "bytes": 21
      },
      {
        "path": "patches/fix.patch",
        "kind": "file",
        "optional": false,
        "ignore": [],
        "state": "ok",
        "digest": "99fcc8c10081e1348e3a328e1ca48e773163fe20c8b9f188ffc8604e508adf9d",
        "entries": [{"path": "fix.patch", "type": "file", "sha256": "99fcc8c1...adf9d", "size": 14}],
        "bytes": 14
      },
      {
        "path": "assets-optional",
        "kind": "tree",
        "optional": true,
        "ignore": [],
        "state": "optional-missing",
        "digest": null,
        "entries": [],
        "bytes": 0
      }
    ]
  },
  "toolchain": {
    "components": ["devkitpro_gcc", "cmake", "ninja"],
    "versions": {
      "devkitpro_gcc": "aarch64-none-elf-gcc.exe (devkitA64) 16.1.0",
      "cmake": "cmake version 4.0.2",
      "ninja": "1.13.2",
      "rustc": "rustc 1.99.1 (58cf8f9c3 2026-10-13)",
      "cargo": "cargo 1.99.1 (5f94df478 2026-08-27)",
      "sdl2": "2.28.5",
      "ffmpeg_source_commit": "unknown",
      "host_platform": "win32-AMD64"
    },
    "unknown": ["ffmpeg_source_commit"],
    "degraded": []
  },
  "host_platform": {"platform": "win32", "machine": "AMD64"},
  "cache": {"miss_reasons": []}
}
~~~

契约说明：tree_digest = sha256(canonical_json({"kind": "tree", "entries": [...]}))，entries 已按相对 POSIX 路径 UTF-8 字节序排序；canonical_json 使用 sort_keys=True、separators=(",", ":")、ensure_ascii=False。

## 附录 B：缓存键前后对比

同一批临时输入（src/ 两文件 + patches/fix.patch + 缺失的 optional 目录）分别按 v1/v2 payload 结构计算：

| 版本 | payload 关键内容 | 示例 key |
| --- | --- | --- |
| v1 | schema=1；manifest 路径；engine；build；input；toolchain 仅 devkitpro_gcc/cmake 首行 | 5614c78b0d692075b174a949edcc7011aa11a21c9a2728e611fbe1aa142c0a3b |
| v2 | schema=2；+ inputs 摘要（tree/file digest）；+ 8 项 toolchain（含 unknown/degraded）；+ host_platform；+ cache.miss_reasons | 34aedb0535aee3855ec5c238816c369d353f52a8cb51fcef8fde665558c8dfe2 |

行为差异（测试已覆盖）：

- 同路径改 src/a.c 或 patches/fix.patch 一个字节 -> entries.sha256 与 digest 变化 -> key 变化 -> miss；
- 只改未声明文件 -> key 不变 -> hit；
- 改声明为 inputs 的 Cargo.lock / ffmpeg/configure.args -> key 变化 -> miss；
- schema 1 -> 2 的直接后果：所有历史缓存条目不可读（安全失效），首次运行必然 miss。

## 附录 C：需要 Lead 实施的 runner.py 最小 diff

文件：src/galnx/batch/runner.py（Lead write scope，本任务只读）。当前代码位置（工作树现行行号）：_cache_stage 中 cache_payload 调用在 793 行，cache_key 在 794 行，miss 分支在 796-798 行。

改动 1：把 root 传给 cache_payload，使 manifest 里的相对 build.inputs 一律相对批次根解析（与 manifest 路径展示口径一致）：

~~~diff
@@ -793 +793 @@ def _cache_stage(
-    payload = build_layer.cache_payload(_display_path(root, target), data, config, engine=engine)
+    payload = build_layer.cache_payload(_display_path(root, target), data, config, engine=engine, root=root)
~~~

改动 2：在 cache_payload 之后、cache_key 之前插入强制 miss 判定（降级工具链 / 必需输入缺失 / 输入不可读），并在 miss 分支前返回，使 _build_stage 因 payload=None 不写缓存条目：

~~~diff
@@ -793,6 +793,10 @@ def _cache_stage(
     payload = build_layer.cache_payload(_display_path(root, target), data, config, engine=engine, root=root)
+    reasons = list((payload.get("cache") or {}).get("miss_reasons") or [])
+    if reasons:
+        checks = [_check("cache.miss", "warn", "; ".join(reasons))]
+        return checks, {"hit": False, "key": "", "payload": None}
     key = build_layer.cache_key(payload)
~~~

效果与注意点：

- 命中文案不变（cache.hit）；正常 miss 仍是 cache.miss（ok）+ key 返回，不改变现有行为与测试。
- degraded/missing 时返回 warn 级 cache.miss，细节形如 "degraded toolchain: unknown version for ninja" 或 "required build input missing: src"；key 置空 => _build_stage 的 key/payload 检查会跳过 write_cache_entry，避免把降级结果写进缓存。
- 现有 tests/test_batch_build_cli.py 的 miss->hit 测试依赖本机工具链三分量 known（已实测：devkitpro_gcc/cmake/ninja 均 known，degraded=[]），应用本 diff 后仍会 hit，不会回归。
- 若 Lead 希望 miss 原因也出现在 report 的 build 阶段（build_state 语义），runner 已有 build_state=executed 等分类，无需额外改动；check id 复用 cache.miss 以兼容既有断言。
- 如果 Lead 不想改 runner 两处，也可以后续在 _build_stage 写缓存前判断 payload.cache.miss_reasons，但这样仍会先做一次 key 查找并可能命中旧条目，语义不如在 _cache_stage 前置判断直接。

## 附录 D：docs/MANIFEST.md 需要补充的文字（Lead 合并）

当前第 36 行 build 行原文：

| build | 是 | output_dir、reproducible、clean_workspace_before_build、keys_env（兼容字段；**实际出包用显式 --keyset**，见下）、romfs_mode；真实构建可选：commands（元素为 argv 数组或 shell 字符串）、workdir、artifact（相对 workdir）、env、timeout_s（默认 600） |

建议替换为：

| build | 是 | output_dir、reproducible、clean_workspace_before_build、keys_env（兼容字段；**实际出包用显式 --keyset**，见下）、romfs_mode；真实构建可选：commands（元素为 argv 数组或 shell 字符串）、workdir、artifact（相对 workdir）、env、timeout_s（默认 600）、inputs（显式构建输入清单，元素 path/kind(file 或 tree，默认 tree)/optional(默认 false)/ignore(glob 数组)；内容摘要纳入缓存键，optional=false 且路径缺失时该次缓存按 miss 处理）、toolchain_components（必须已知版本的工具链指纹分量，默认 devkitpro_gcc/cmake/ninja；任一声明分量的版本为 unknown 时该次缓存按 miss 处理） |

可选追加说明段落（放在第 39 行 additionalProperties:false 说明之后）：

- build.inputs 中的相对路径按 manifest 所在目录解析；tree 会递归收集文件并按相对 POSIX 路径排序计算 sha256 摘要，任意层级的 .git/.galnx 恒被忽略，ignore 使用 fnmatch 语义（不支持 ! 取反）。
- 缓存条目 schema 已升到 2：旧 schema 条目会被当作缺失处理（安全重建），不需要手工清理 .galnx/cache。

## 附录 E：build/__init__.py 导出说明

- 本任务未修改 src/galnx/build/__init__.py（他人 scope）。新增的公开函数 build_inputs_digest(config, base) 与 host_platform()、常量 DEFAULT_TOOLCHAIN_COMPONENTS 位于 cache.py/config.py，可通过模块路径直接 import；未加入 galnx.build 的 __all__。
- runner 不需要这些新函数：附录 C 的 diff 只读 payload 字段。
- 若后续 CLI（src/galnx/cli.py，他人 scope）要展示输入摘要或诊断 degraded，需要 Lead 在 build/__init__.py 的 import 与 __all__ 中补：build_inputs_digest、host_platform、DEFAULT_TOOLCHAIN_COMPONENTS（以及已有函数保持不动）。

## 附录 F：并发改动与测试失败归因（重要）

写报告时工作树是多任务并发状态（其他队友未提交改动，git status 可见 20+ 个 M 文件），本任务只拥有其中 5 个文件。因此全量测试的失败需要按文件归属拆开：

1. 6 个 batch 测试失败（test_batch_build_cli.py 2、test_batch_cli.py 2、test_batch_runner.py 2）不是缓存回归：
   - 复现：临时工程执行 galnx batch build --json 后 project.status=warn（测试期望 ok），totals.ok=0（测试期望 1）。
   - 唯一非常规非 ok check 是 {"id": "engine.status", "status": "warn", "detail": "engine.adapter: adapter 'krkrsdl2' is still marked research: Emulator-level only: ... no Switch hardware run exists yet ..."}（另有 prod.keys skip，NRO 目标预期）。
   - engine.status 的 warn 由并发任务的 engines/registry.py + engines/descriptor.py + schemas/engine.schema.json 改动引入；batch 报告 totals 结构（v2、cache_hits/executed/not_configured）由并发任务的 report.py/schemas/batch-report.schema.json 改动引入。这些文件均非本任务 write scope，也未被本任务修改。
2. 全量 23 failed 的分布：batch 6、engines_cli 1、engines_descriptor 6 FAILED + 6 SUBFAILED、engines_registry 2、public_release 2；没有任何一个失败位于 tests/test_build_cache.py、tests/test_build_cache_inputs.py、tests/test_build_lock.py、tests/test_build_executor.py、tests/test_manifest.py、tests/test_input_manifest.py。本任务相关的 26 个缓存测试全绿。
3. 本任务提交前请 Lead 注意：schemas/game-manifest.schema.json 与 src/galnx/build/config.py 同时含并发任务改动（commands↔artifact 成对校验、has_commands/execution_state），提交信息应按任务拆分，或至少注明混合作者；本报告不把这两部分记为本任务产出。
4. 仓库根未跟踪文件 _dbg_batch.py 非本任务创建，未清理。

## 附录 G：关键实现位置索引

src/galnx/build/cache.py（495 行）：
- CACHE_SCHEMA_VERSION = 2（29 行）；DEFAULT_IGNORED_DIRS = (".git", ".galnx")（34 行）；_TOOL_COMMAND（37 行）
- utc_now 47；_run_version 51；_find_devkit_gcc 70；_find_sdl2_pc 90；_sdl2_version 110；_ffmpeg_source_commit 125；host_platform 132；fingerprint_toolchain 140
- canonical_json 161；_toolchain_section 171；_is_ignored 190；_tree_entries 206；_input_spec 249；_manifest_base 297；build_inputs_digest 304；_cache_miss_reasons 330
- cache_payload 349（schema 字段写出于 377）；cache_key 395；cache_root 399；entry_path 403
- read_cache_entry 407（schema_version 检查 417）；verify_cache_entry 422（schema 检查 425）；_write_text 447；write_cache_entry 454（写 schema_version 463）；artifact_from_entry 479；describe_artifact 488

src/galnx/build/config.py（276 行）：
- DEFAULT_TOOLCHAIN_COMPONENTS = ("devkitpro_gcc", "cmake", "ninja")（18 行）；class BuildInput（29 行）；BuildConfig.inputs（48 行）、.toolchain_components（49 行）
- _build_inputs（131 行）；_toolchain_components（172 行，缺省返回 DEFAULT_TOOLCHAIN_COMPONENTS 174 行）；parse_build_section 中 inputs/toolchain_components 解析（230-231 行）

schemas/game-manifest.schema.json（399 行）：
- build.properties.inputs（262 行起）；build.properties.toolchain_components（301 行起）；两者均非 required，旧 manifest 不受影响

tests/：
- tests/test_build_cache_inputs.py（374 行；CacheInputTests 14 个 + ManifestSchemaInputTests 3 个）
- tests/test_build_cache.py（188 行；新增 test_read_and_verify_reject_old_schema_entries（137 行起）、test_payload_includes_inputs_and_toolchain_sections（160 行起））
