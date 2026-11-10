# TASK-ENGINES 任务报告

> GalNX 0.1 Preview 收敛整改 / 专家计划 P0-2 + P1-4 + P1-6（引擎侧）：能力模型与真机证据对账。
> 本文件是任务交付报告；代码改动见同工作区 git diff（未提交，由 Lead 统一提交）。

## Task ID
TASK-ENGINES（共享任务板 task-63；执行者 audit-engines）

## Source commit
974a414（main 分支 HEAD；本报告的测试与示例均基于该提交 + 当前未提交工作树）

## Files changed

| 文件 | 类型 | 变化 |
| --- | --- | --- |
| schemas/engine.schema.json | 已跟踪修改 | 179 行改动，当前 388 行 / 11,050 B：新增 $defs.capability 与 $defs.engineVerification、6 能力键 + video 弃用别名、顶层 verification |
| src/galnx/engines/descriptor.py | 已跟踪修改 | 288 行改动，当前 859 行 / 36,664 B：新常量、能力项字段与校验、verification 块、warnings 通道、video→graphics 映射 |
| src/galnx/engines/registry.py | 已跟踪修改 | 183 行改动，当前 477 行 / 20,250 B：3 个内置适配器改 research + 新能力模型 + verification 块；load_dir 对内置镜像去重 |
| src/galnx/engines/__init__.py | 已跟踪修改 | 17 行：导出新常量与 capability_warnings |
| examples/engines/rfvp.yaml | 已跟踪修改 | 226 行改动，当前 400 行：status ready、6 能力 + verification、顶层 device_verified、证据补 050/051/052 与 akaseka 验收 |
| examples/engines/kirikiroid2-nx.yaml | 已跟踪修改 | 98 行改动，当前 307 行：status_reason 由「hardware unverified」改为设备已验证、6 能力 + verification、game_verified |
| examples/engines/krkrsdl2.yaml | 已跟踪修改 | 57 行改动，当前 70 行：与内置项镜像同步（research） |
| examples/engines/onscripter-nx.yaml | 已跟踪修改 | 59 行改动，当前 71 行：与内置项镜像同步（research） |
| examples/engines/brewser.yaml | 已跟踪修改 | 62 行改动，当前 71 行：与内置项镜像同步（research） |
| docs/engines/README.md | 已跟踪修改 | 278 行改动，当前 350 行 / 29,688 B：按新术语与能力模型重写 |
| docs/engines/verification-matrix.md | 新增（未跟踪） | 94 行 / 10,404 B：pilot 真机验收索引 + 模拟器级 + 引擎能力汇总 |
| tests/test_engines_descriptor.py | 已跟踪修改 | 101 行改动，当前 406 行：新能力模型断言 + DescriptorVerificationTests 7 个测试 |
| tests/test_engines_registry.py | 已跟踪修改 | 44 行改动，当前 260 行：research 警告断言 + load_dir 去重测试 2 个 |
| tests/test_engines_cli.py | 已跟踪修改 | 4 行：plan checks 计数 9→10（research 多 1 warn） |
| tests/test_engines_source.py | 已跟踪修改 | 4 行：descriptor 顶层键数 23→24（新增 verification） |
| docs/release/tasks/TASK-ENGINES.md | 新增（未跟踪） | 本报告 |

Scope 遵守：只改了上表 write scope 内文件；未触碰 README.md、docs/MANIFEST.md、src/galnx/cli.py、examples/pilot*.yaml、THIRD_PARTY_NOTICES.md；未执行任何 git 写操作（仅 git status/diff/numstat/rev-parse 只读）。

## Observed problem

1. 能力模型是扁平 dict，CAPABILITY_KEYS 固定为 video/audio/input/save/touch，每项只有 {supported, note}：
   - video 语义歧义：既可能指「图形渲染」，也可能指「视频解码」，导致 rfvp 等引擎无法表达「渲染 OK 但 movie 解码有限」。
   - 无法表达证据等级：krkrsdl2 只在 Citron 验证过标题+输入，与 rfvp 真机 4 部试点 PASS 在数据上完全同构（都是 supported=true），文档/CLI/批量流水线无法据此分层。
   - 无法表达后端/特性：SDL2+GLES2、NVDEC+NV12 零拷贝、audren、faudio 等实现细节只能塞进长文本 note。
2. descriptor 状态与真机证据脱节：
   - rfvp（4 个试点真机 PASS，最新 1.4.1-test 获用户确认）仍是 status: research，status_reason 为约 7,600 字符历史流水，末段停在 v1.1.10-test。
   - kirikiroid2-nx 已是真机 PASS（Pilot-01 A10 1.0.9，用户确认），但 status_reason 仍写 Switch hardware is still unverified。
   - krkrsdl2 / onscripter-nx / brewser 只有模拟器级证据，却与真机引擎同为 status: ready，无法区分「研究路线」与「可交付」。
3. engines list 默认只列 3 个内置项；rfvp / kirikiroid2-nx 是 examples/engines 下的 external descriptor，需 --engines-dir。旧 docs/engines/README.md 未把 built-in adapter / external descriptor / engine runtime / game profile 区分清楚，且 examples/engines 中 3 个内置镜像会让 load_dir 报重复注册（engines info --engines-dir 不可用）。

## Decision made

1. 能力键升级为 graphics / movie / audio / input / save / touch（6 键）：
   - video 保留为 deprecated 别名：加载时自动映射到 graphics 并产生 warning，旧描述符自动补 movie={supported:false, verification:"unknown"}，新描述符禁止再写 video。
   - 每个能力项字段：supported（bool，保留兼容）、note（str）、verification（必填枚举，touch 可省略）、backend / features / details（可选）。
   - verification 枚举：source_review / build_verified / emulator_verified / device_verified / game_verified / partial / unknown / in_progress。
2. descriptor 增加可选顶层 verification 块（status / hardware / firmware / atmosphere / tested_at / evidence[] / notes），表达该引擎整体的真机结论；具体每部游戏的验收放进 docs/engines/verification-matrix.md，实现「引擎级能力实现」与「游戏级兼容性」分离。
3. warnings 与 errors 分离：EngineDescriptor 新增 warnings 字段（放在字段末尾，兼容位置参数构造），validate() 只返回 errors，新增 validate_with_warnings()；descriptor_from_dict 不因弃用别名 warning 抛错。to_dict() 输出 19 字段 + 非空 verification（20 键），不输出 warnings。
4. 3 个内置适配器（krkrsdl2 / onscripter-nx / brewser）降为 status: research 并附 status_reason 与 verification 块（emulator_verified）；rfvp / kirikiroid2-nx 升为 status: ready（top verification 分别为 device_verified / game_verified）。
5. EngineRegistry.load_dir：同名 id 若 to_dict() 完全相同则跳过（examples/engines 镜像内置项属正常），内容不同才报冲突；不改 src/galnx/cli.py。
6. examples/pilot*.yaml、README.md 能力描述、cli.py 输出展示属 Lead / 他人 scope，本任务只在报告附录给出最小改动建议。

## Behavior before

- CAPABILITY_KEYS = ("video","audio","input","save","touch")，无 evidence 等级、无 backend/features/details、无顶层 verification。
- engines list 显示 3 个内置适配器全部 ready；rfvp status=research 且 status_reason 为历史长文；kirikiroid2-nx 的 reason 仍称硬件未验证。
- engines info --engines-dir examples/engines 直接失败：engine adapter 'brewser' is already registered（内置镜像重复）。
- schema 的 capabilities 固定 required [video,audio,input,save,touch]，拒绝 graphics/movie。
- 旧描述符（只有 5 键）无法表达真机状态；批量流水线的 engine.status check 对 3 个内置项不再产生 research warning。

## Behavior after

- CAPABILITY_KEYS = ("graphics","movie","audio","input","save","touch")；video 作为别名接受 → 映射 graphics + warning + 自动补 movie(unknown/unsupported)；新描述符缺 graphics/movie/audio/input/save 的 verification 会报 "capabilities.<key>.verification: required (...)"。
- 每个能力项可带 backend/features/details，round-trip 保真（to_dict 后 descriptor_from_dict 结果相同）。
- 顶层 verification 块可 round-trip；未知键报错；非空块必须给 status。
- 5 个 descriptor 能力摘要（load_descriptor 实测）：

| descriptor | status | target / backend | 许可证 | graphics | movie | audio | input | save | touch | 顶层 verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rfvp | ready | self_contained_nsp / custom-script | MPL-2.0 | game_verified | device_verified | device_verified | game_verified | device_verified | unknown(false) | device_verified，2026-11-10 |
| kirikiroid2-nx | ready | self_contained_nsp / cmake-switch | NOASSERTION | game_verified | device_verified | device_verified | game_verified | device_verified | unknown(false) | game_verified，2026-10-31 |
| krkrsdl2 | research | nro / cmake-switch | MIT | emulator_verified | unknown | unknown | emulator_verified | unknown | unknown(false) | emulator_verified，2026-10-26 |
| onscripter-nx | research | nro / devkitpro-make | GPL-2.0-or-later | emulator_verified | unknown | unknown(false) | emulator_verified | unknown(false) | unknown(false) | emulator_verified，2026-10-30 |
| brewser | research | web / prebuilt | MPL-2.0 | emulator_verified | unknown | unknown | source_review | emulator_verified | source_review | emulator_verified，2026-10-29 |

  （supported 与 verification 独立：例如 krkrsdl2 的 movie 后端存在但尚无证据，故 supported=true / verification=unknown；onscripter-nx 的 audio/save 明确 supported=false。）
- engines list 只列 3 个内置（均 research，CLI 输出含 research 状态与 warning）；engines list --engines-dir examples/engines 列出 5 个；engines info --engines-dir examples/engines rfvp 正常（不再重复注册报错）。
- engines plan 对 research 引擎多 1 条 engine.status WARN（krkrsdl2 / onscripter-nx 由 9 checks 变 10 checks: 0 fail, 1 warn）。

## Tests added

- tests/test_engines_descriptor.py 新增 class DescriptorVerificationTests（7 个测试）：video 别名映射 graphics + warning + 自动补 movie；缺 graphics verification 报错；非法 verification 枚举报错；touch verification 可省略；能力项 backend/features/details round-trip；顶层 verification round-trip；顶层 verification 未知键报错。
- tests/test_engines_registry.py 新增：test_load_dir_skips_identical_builtin_duplicates、test_load_dir_rejects_conflicting_duplicate；并改写 research/ready 警告与 adapter_version 断言。
- 同步改动：BuiltinDescriptorTests 断言 3 内置 status=research / not is_ready；能力键 6 键且无 video；to_dict 键集 19+verification；ArtifactNaming 手工 descriptor 补 verification；test_blocked_requires_reason 先清空 status_reason；test_engines_cli.py plan checks 9→10；test_engines_source.py descriptor 顶层键数 23→24。

## Commands executed

~~~text
# 引擎测试（PYTHONPATH=src，cwd 仓库根）
python -m pytest -q tests/test_engines_descriptor.py tests/test_engines_registry.py tests/test_engines_contract.py tests/test_engines_cli.py tests/test_engines_source.py
# CLI 验收（均 exit 0）
python -m galnx engines list
python -m galnx engines info --engines-dir examples/engines rfvp
python -m galnx engines list --engines-dir examples/engines
python -m galnx engines plan --manifest examples/pilot04-akaseka.yaml --engines-dir examples/engines
python -m galnx engines info krkrsdl2
# 5 个 descriptor 加载/校验/能力摘要（load_descriptor + validate_with_warnings）
python <临时脚本 dump_caps.py / verify_yaml.py>
# 回归（他人文件，只读观察）
python -m pytest -q tests/test_manifest.py tests/test_preflight.py tests/test_build_contract.py tests/test_build_lock.py tests/test_batch_runner.py tests/test_batch_build_cli.py tests/test_cli_stdio.py
python -m pytest -q tests/test_batch_runner.py::BatchRunnerTests::test_healthy_project   # 带 GALNX_BUILD_ROOT=已存在目录
# 只读 git
git rev-parse HEAD / git status --porcelain / git diff --stat -- <我的文件>
~~~

## Test results

- 引擎测试：**145 passed, 12 subtests passed in 68.14s**（exit 0）。
- CLI：engines list（3 个内置，全部 research）；engines info --engines-dir examples/engines rfvp（capabilities: audio, graphics, input, movie, save；artifact rfvp-HEAD.nsp；input generic-vn）；engines list --engines-dir examples/engines（5 个，含 rfvp / kirikiroid2-nx ready）；engines plan pilot04（rfvp，self_contained_nsp，rfvp-1.4.1-test.nsp，pinned 9f07adef…，16 patches）；engines info krkrsdl2——全部 exit 0。
- descriptor 校验：5 个 YAML load_descriptor 成功、validate()==[]（research 引擎的 status_reason 为显式理由，不是错误）；内置镜像 3 个与 registry to_dict() 完全相等。
- 回归：他人并发修改的 tests/test_batch_runner.py::test_healthy_project 在默认环境下断言 preflight=ok 但实为 warn，warn 来自 preflight 的 build-root check（默认 build root 为临时目录下 galnx-build，目录不存在，detail 提示 directory does not exist yet）。该失败与引擎改动无关：设置 GALNX_BUILD_ROOT 指向已存在目录后该测试单项通过（1 passed），其余回归 50 passed。该文件不在本任务 write scope，未修改。

## Unverified assumptions

- 真机验收版本对账：仓库内验收记录对应 README Pilot 表的 1.2.4 / 1.3.2 / 1.4.0-test 与 A10 1.0.9；Lead 任务书另称 1.2.5 / 1.3.3 / 1.4.1-test 用户已确认，但仓库内尚无对应验收日志。descriptor 的 device_verified 以仓库内 README + docs/pilot 验收文档为准，更新构建在 verification-matrix §2.1 单独标注「用户已确认、仓库缺验收记录」。
- rfvp 的 movie device_verified 依据 AKASEKA 1.4.1-test（用户 m40951「颜色正确、播放相当流畅」）与 1.4.0-test 验收（OP 无卡顿）；IROSEKA / SAKURA_MOYU 的 1080p/720p OP 分档仍待用户确认，已在 status_reason/矩阵中写明。
- kirikiroid2-nx 的 movie/audio device_verified 依据 P4-device-runbook §12.2 回归清单含「中文 OP / 音频」+ §12.4 A10 真机 PASS；无逐项量化日志（无帧率/延迟数据）。
- brewser 的 save emulator_verified 只表示「Citron 冒烟中 localStorage 可写」，跨 run 持久化已证伪（docs/builds/006），未写成 device_verified。

## Known limitations

- 能力模型仍是扁平能力表 + 单一 verification 枚举，不能表达「同一能力在哪些游戏上验证过」的粒度；该粒度放 docs/engines/verification-matrix.md（游戏级）。
- 3 个内置适配器降 research 后，任何用内置 krkrsdl2/onscripter-nx/brewser 的批量项目会多 1 条 engine.status WARN；这是刻意的「研究路线不得冒充可交付」提示，如有项目需要静音需 Lead 决定（不在本任务 scope）。
- CLI（src/galnx/cli.py）当前只打印 supported 的能力名，不显示 verification / backend / 顶层 verification；属 Lead scope，未改，最小 diff 建议见附录 A。
- README.md 的适配器状态表与 docs/MANIFEST.md 未同步（禁改），建议 Lead 合并附录 B 的文字。
- 真机 firmware / atmosphere 版本仓库无记录，descriptor 的 verification.firmware / atmosphere 留空。
- touch 能力 5 个引擎均未验证（supported=false 或 source_review）。

## Rollback method

- 代码/配置回滚（未提交，均是工作树改动）：
  git checkout -- schemas/engine.schema.json src/galnx/engines/descriptor.py src/galnx/engines/registry.py src/galnx/engines/__init__.py examples/engines/*.yaml docs/engines/README.md tests/test_engines_descriptor.py tests/test_engines_registry.py tests/test_engines_cli.py tests/test_engines_source.py
- 删除新增文件：rm docs/engines/verification-matrix.md docs/release/tasks/TASK-ENGINES.md
- 若只想撤销「内置改 research」：把 src/galnx/engines/registry.py 中 3 个内置的 status 改回 "ready"、清空 status_reason，并从 examples/engines/{krkrsdl2,onscripter-nx,brewser}.yaml 同步删除 status_reason（其余能力模型改动可保留）。
- 回滚后需重跑：python -m pytest -q tests/test_engines*.py（旧断言恢复原状）。

## 附录 A：src/galnx/cli.py 最小 diff 建议（Lead scope）

engines info 当前只输出 capabilities: audio, graphics, ...（仅 supported 项）。建议在 info 输出中追加一行能力证据摘要，不改数据结构：

~~~diff
   capabilities: audio, graphics, input, movie, save
+  verification: graphics=game_verified movie=device_verified audio=device_verified input=game_verified save=device_verified touch=unknown
+  engine verification: device_verified (tested 2026-11-10)
~~~

实现位置：cli.py 中 engines info 分支的 capabilities 打印处，遍历 descriptor.capabilities 取每项 verification 拼接；顶层用 descriptor.verification.get("status") / tested_at。约 6-10 行，无新依赖。

## 附录 B：README.md / docs/MANIFEST.md 文字建议（Lead scope）

- README 适配器状态表：rfvp 从「研究级」改为「真机验证（device_verified，4 部试点 PASS，AKASEKA 1.4.0/1.4.1-test）」；kirikiroid2-nx 从「硬件未验证」改为「真机验证（game_verified，A10 1.0.9，2026-10-31）」；krkrsdl2 / onscripter-nx / brewser 明确标注「模拟器级（emulator_verified），research 路线」。
- README 能力描述引用 docs/engines/verification-matrix.md 作为唯一游戏级验收索引，避免与 descriptor 双写。
- docs/MANIFEST.md 若索引 docs/engines/ 目录，需补 verification-matrix.md 与 README.md 的说明条目。

## 附录 C：并发工作树说明

报告生成时工作树含大量其他队友未提交改动（batch/build/public-release/third-party/CLI 等）。本任务只修改上表 16 个文件；引擎测试在包含这些并发改动的工作树上仍全绿（145 passed）。tests/test_batch_runner.py 的 preflight 断言失败属 build-root 环境问题（见 Test results），非引擎回归，未修改他人文件。
