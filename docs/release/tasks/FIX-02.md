# FIX-02 任务报告

> GalNX 0.1.0-preview 收口修复 / 专家复审 FIX-02：公开仓库需要一条「干净环境、只需 Python」就能跑通的完整构建示例。
> 本文件是任务交付报告；代码与示例改动见同工作区 git diff（未提交，由 Lead 统一提交）。

## Task ID
FIX-02（共享任务板 task-65；执行者 audit-switch）

## Source commit
c7d389e9（HEAD，main 分支；本报告的本地验证均基于该提交 + 当前未提交工作树）

工作树同时包含并行任务的未提交改动（README.md、docs/MANIFEST.md、docs/engines/*、docs/pilot/0.1.0-device-acceptance.md、examples/engines/rfvp.yaml、src/galnx/build/cache.py、src/galnx/cli.py、tests/test_batch_build_cli.py、tests/test_build_cache_inputs.py、tests/test_build_contract.py，以及未跟踪的 docs/release/tasks/FIX-03-FIX-05.md）。本任务未触碰这些文件；全量测试结果是在该并行工作树上取得的。

## Files changed

| 文件 | 类型 | 变化 |
| --- | --- | --- |
| examples/quickstart/manifest.yaml | 新增 | 41 行，2,158 B（sha256 `e92fbadf8fdb…`）：game/engine/switch/build 四段，声明 build.commands、build.artifact、build.inputs |
| examples/quickstart/tools/pack_demo.py | 新增 | 61 行，2,019 B（sha256 `d6ace5618ac2…`）：stdlib-only 确定性打包器，写 `out/demo.pak` |
| examples/quickstart/content/demo.txt | 新增 | 2 行，92 B（sha256 `eaf1f17e88f8…`）：小文本资产 |
| examples/quickstart/content/sub/extra.txt | 新增 | 1 行，60 B（sha256 `13f034d75e29…`）：验证嵌套 POSIX 路径保留 |
| examples/quickstart/README.md | 新增 | 56 行，2,000 B：运行方式、预期输出、文件表、示例演示了什么 |
| examples/quickstart/.gitignore | 新增 | 2 行：忽略示例生成的 `out/`（根 .gitignore 只忽略 `.galnx/`，不忽略 `out/`） |
| tests/test_quickstart_example.py | 新增 | 155 行，6,217 B（sha256 `fbc6bfd44a3b…`）：2 个测试，见「Tests added」 |
| .github/workflows/ci.yml | 已跟踪修改 | +12 行（当前 95 行）：新增 `Minimal build example (quickstart)` step |
| docs/release/tasks/FIX-02.md | 新增 | 本报告 |

Scope 遵守：
- 只改了 task-65 写入范围内的文件（examples/quickstart/**、tests/test_quickstart_example.py、.github/workflows/ci.yml、docs/release/tasks/FIX-02.md）。
- 未改 README.md、src/**、schemas/**、其他 docs；README 快速开始段落的建议文字见附录 A，由 Lead 合并。
- 未执行任何 git 写操作（只用 `git status`/`git diff`/`git rev-parse` 只读命令）。

## Observed problem

专家复审 FIX-02 指出：公开仓库缺少一条从干净环境（只需 Python）可执行的完整构建链路演示。审计事实：

1. 仓库内所有已跟踪 manifest（`examples/pilot*.yaml`、`examples/templates/*`、`examples/batch/*`）都没有声明 `build.commands`。CI 的构建 smoke 步骤甚至以「期望 exit 3（not_configured）」来断言这一点——即 CI 从未真正执行过一次构建。
2. 因此新用户/复审者无法只凭仓库证明「manifest 声明命令 → CLI 执行 → 校验 artifact → 第二次命中缓存」这条流水线；必须自备 devkitPro、Rust、FFmpeg 与商业游戏数据才能看到构建行为。
3. README「快速开始」只有被动命令（doctor / engines list / preflight / dry-run），没有一条会产生文件的命令；「构建」示例指向真实试点清单，而试点清单按契约拒绝执行。
4. `galnx build run` 的 cache 逻辑要求 `build.inputs`（无 inputs 时缓存被禁用且报 blocking），仓库里也没有任何示例演示这一契约，用户容易写出永远不命中的 manifest。

## Decision made

1. 新增自包含 `examples/quickstart/`，只依赖 Python 标准库：manifest 声明 `build.commands: [["python","tools/pack_demo.py","content"]]`、`build.artifact: out/demo.pak`、`build.inputs: [{content,tree},{tools/pack_demo.py,file}]`。命令由 CLI 真正执行（shell=False 的 argv），artifact 由 CLI 校验存在性，第二次运行命中内容寻址缓存。
2. 打包器 `pack_demo.py` 确定性：`rglob` 收集后按 POSIX 相对路径排序，容器格式 `GALNXPK1` + u32 文件数 + 逐文件 [u16 名长 + 名 + u64 大小 + sha256(32) + 内容]；同一输入重复运行字节级一致（有单测覆盖）。
3. `engine.adapter` 用内置 `krkrsdl2` 并写 `adapter_version: "krkrsdl2@124bdf84 (2026-10-01)"`：这是 schema enum 与内置 registry 都接受的组合；`adapter_version` 含 pinned commit 前 8 位，避免 engines 阶段出现 pin 警告。示例不调用任何引擎工具链，adapter 只用于 schema/registry 兼容。
4. `game.source_dir` 写 `examples/quickstart/content`（相对仓库根）：preflight 的 `_check_source_dir` 用 `Path(raw).is_dir()` 相对**进程 CWD** 判断，写 `content` 或绝对路径都会在文档化命令下失败/绑机器。README 明确要求从仓库根运行。
5. 测试把示例复制到 `tmp_path/repo/examples/quickstart`，用 `contextlib.chdir` 切到副本根后进程内调用 `cli.main(...)`，因此不写仓库工作树；断言首跑 executed/cache miss、二跑 cache hit 且 artifact 不变、改输入后 miss 且 artifact 变化；另测打包器确定性。
6. CI 新增 step：在 windows-latest 仓库根连续跑两次验收命令，并用 `python -c` 断言产物 magic `GALNXPK1`。
7. 额外加 `examples/quickstart/.gitignore`（`out/`）：根 .gitignore 不忽略 `out/`，防止示例产物被误提交；这是最小改动，Lead 也可改为根 .gitignore 条目（见附录 B）。

与任务书文字的偏差（Deviation）：
- 任务书示例命令写 `python tools/pack_demo.py originals`，但同一任务要求 `content/` 存放资产、`build.inputs path content`。实际用 `content`（目录与参数一致），报告此处记录偏差。
- 任务书问 `adapter custom 或内置适配器？`。选内置 `krkrsdl2`：`custom` 未在 registry 注册，除非再提供 `engine.descriptor`，会给一个「构建示例」引入无关复杂度。
- 任务书写 `entry content/demo.txt`。因 `source_dir=content`，entry 相对路径写 `demo.txt`；解析后的绝对路径就是 `examples/quickstart/content/demo.txt`（preflight 输出已证实），语义等价。

## Behavior before

从干净 checkout（只需 Python）：
- 没有任何可直接执行的构建示例；`galnx build run --manifest examples/pilot04-akaseka.yaml --yes` 按契约退出码 3（not_configured），不产生文件。
- CI 没有真实构建步骤，无法在公开仓库回归 executor/artifact 校验/cache 命中。
- 缓存命中与失效（`build.inputs`）契约没有可执行文档；README 快速开始无一条会产出文件的命令。

## Behavior after

从仓库根、只需 Python（本机实测）：

```
PYTHONPATH=src python -m galnx build run --manifest examples/quickstart/manifest.yaml --yes --json
```

- 首跑：exit 0，`executed=1, cache_hits=0, cache_misses=1, built=1`，`build_state=executed`；产出 `examples/quickstart/out/demo.pak` 269 B，magic `GALNXPK1`，2 个条目（`demo.txt` 92 B、`sub/extra.txt` 60 B），sha256 `5982bb067d6c48654f2b346168c3192de34e141a70d17f06fbdebc1660ef8870`。项目 `status=warn`（唯一 warn 来自既有检查 `build-root`：默认全局构建根目录尚未创建；与本示例无关，不阻塞、退出码 0）。
- 二跑同一命令：exit 0，`executed=0, cache_hits=1, cache_misses=0, built=0`，`build_state=cache_hit`，artifact 字节不变。
- 改动声明过的输入 `content/demo.txt` 后再跑：缓存 key 从 `4cd40986…` 变为 `c6e8b405…`，exit 0，`executed=1, cache_hits=0`，artifact sha256 变为 `cc5b0380b527636039b0692a3088999da2e5f3da27113a5b4d4e358ab0e63920`。

## Tests added

`tests/test_quickstart_example.py`（155 行，unittest，2 个测试方法）：

1. `test_build_artifact_and_cache_cycle`
   - 复制 `examples/quickstart` 到临时仓库根副本，chdir 后进程内调用 CLI（`--json`），解析 stdout JSON；
   - 首跑断言：exit 0、`fail==0`、`executed==1`、`cache_hits==0`、`cache_misses==1`、`built==1`、`build_state=="executed"`、`name=="quickstart-demo"`、`adapter=="krkrsdl2"`；
   - artifact 存在；用独立解析函数校验 magic、条目名排序 `["demo.txt","sub/extra.txt"]`、逐文件 sha256、无尾随字节；
   - 二跑断言：`executed==0`、`cache_hits==1`、`built==0`、`build_state=="cache_hit"`、artifact sha256 不变、`.galnx/cache` 存在；
   - 改 `content/demo.txt` 后三跑断言：`cache_hits==0`、`executed==1`、artifact sha256 变化。
2. `test_pack_demo_is_deterministic`：同一内容目录连续跑两次打包器，断言 exit 0、输出含 `packed 2 file(s)`、两次 artifact sha256 相同、首条目为 `demo.txt`。

测试隔离：全部写入临时目录（`tempfile.TemporaryDirectory`），不触碰仓库工作树；不需要 devkitPro/Rust/网络/游戏数据。

## Commands executed

```bash
# 1) 本机手工验证（在仓库根，先清理示例产物）
rm -rf examples/quickstart/out examples/quickstart/.galnx
PYTHONPATH=src python -m galnx build run --manifest examples/quickstart/manifest.yaml --yes --json
PYTHONPATH=src python -m galnx build run --manifest examples/quickstart/manifest.yaml --yes --json
echo "modified line" >> examples/quickstart/content/demo.txt
PYTHONPATH=src python -m galnx build run --manifest examples/quickstart/manifest.yaml --yes --json
# 恢复 content 并清理产物
rm -rf examples/quickstart/out examples/quickstart/.galnx

# 2) 新增测试
PYTHONPATH=src python -m pytest -q tests/test_quickstart_example.py

# 3) 回归（含并行任务工作树）
PYTHONPATH=src python -m pytest -q

# 4) CI YAML 静态校验
python -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml',encoding='utf-8')); print([s.get('name') for s in d['jobs']['ci']['steps']])"
```

三跑摘要（来自 CLI `--json` 报告的 `totals` / `projects[0]`）：

| 运行 | exit | executed | cache_hits | cache_misses | built | build_state | cache key 前 8 | artifact sha256 前 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 首跑 | 0 | 1 | 0 | 1 | 1 | executed | `4cd40986` | `5982bb06` |
| 二跑 | 0 | 0 | 1 | 0 | 0 | cache_hit | `4cd40986` | `5982bb06` |
| 改输入后 | 0 | 1 | 0 | 1 | 1 | executed | `c6e8b405` | `cc5b0380` |

artifact 解析（独立 Python 解析器）：magic `GALNXPK1`，文件数 2，条目 `demo.txt`（92 B，sha256 前缀 `eaf1f17e88f8`）与 `sub/extra.txt`（60 B，sha256 前缀 `13f034d75e29`），总 269 B，无尾随字节。

## Test results

- `PYTHONPATH=src python -m pytest -q tests/test_quickstart_example.py` → **2 passed in 2.06s**
- `PYTHONPATH=src python -m pytest -q` → **746 passed, 63 subtests passed in 78.94s**（该数字含并行任务未提交改动；FIX-02 自身增量为上述 2 个测试）
- CI YAML：`yaml.safe_load` 通过；steps 顺序为 … `Run test suite` → `CLI smoke tests` → `Build plan smoke test (no execution, expect not_configured)` → **`Minimal build example (quickstart)`** → `License inventory (SBOM) check` → `Build the public release tree and scan it`。
- 手工三跑：全部 exit 0，缓存命中/失效与 artifact 变化符合预期（见上表）。
- 清理确认：验证后已恢复 `content/demo.txt`（92 B，sha256 `eaf1f17e…`），删除 `examples/quickstart/out` 与 `.galnx`；`git status` 中本任务只显示 `.github/workflows/ci.yml` 修改与 `examples/quickstart/`、`tests/test_quickstart_example.py` 未跟踪。

## Unverified assumptions

1. **GitHub Actions 未实跑**：本任务禁止 push，`windows-latest` 上的新 step 未实际执行。仅验证了 YAML 可解析，并在本机（Windows 11 + Python 3.12.10）用同一条命令跑通。CI 上 `python` 由 setup-python 提供，manifest 内 argv `"python"` 依赖 PATH，本机已验证同名可解析。
2. **公共发布树未重新扫描**：`scripts/public_release_sanitize.py` 按 git 跟踪文件构建公开树；新文件当前未跟踪，因此「示例会被包含进公开树且扫描无 BLOCK」只能在 Lead 提交后验证。示例内容为纯 ASCII 小文本与 Python 源码，无游戏素材。
3. **缓存跨机器不复用**：cache key 含 `host_platform` 与 toolchain 指纹；干净机器上 toolchain 版本多为 `unknown`（degraded 警告但允许命中）。示例只保证同机重复构建命中，不承诺跨机器共享缓存。
4. **README 快速开始文字未改**：建议文字见附录 A，需 Lead 合并后才对用户可见。
5. **首跑 status=warn** 来自既有 `build-root` 检查（默认全局构建根不存在），非本示例产出；未在干净机器上单独确认该 warn 是否一致出现（退出码仍为 0）。

## Known limitations

1. **必须从仓库根运行**：`game.source_dir` 是 CWD 相对路径（preflight `_check_source_dir` 的既有语义，本任务不改 src）。把 `examples/quickstart/` 单独复制出去、不修改 `source_dir` 时，preflight 会 fail（退出码 2）。README 已注明从仓库根运行；根治需另立任务让 preflight 相对 manifest 目录解析。
2. **示例只验证构建管道**：`engine.adapter=krkrsdl2` 仅用于 schema/registry 兼容，不调用引擎工具链、不产出 NRO/NSP；`demo.pak` 是自定义演示容器，不是 romfs，也不能替代 M0 真机构建验收。
3. **adapter 语义**：示例把 `krkrsdl2` 写进 manifest，可能被误读为「该示例与 krkrsdl2 有关」。README 已说明不调用引擎工具链；若复审认为不妥，可改用 `custom` + `engine.descriptor`（会多一个文件与一次 registry 查找）。
4. **根 .gitignore 未统一**：仅在示例目录加局部 `.gitignore` 忽略 `out/`；若 Lead 更倾向根级规则，见附录 B。
5. **缓存目录仍会留在示例目录**：`.galnx/` 已被根 .gitignore 忽略，但测试/手工运行后本地会残留；不影响仓库洁净度。

## Rollback method

本任务不改 src/schema/依赖，纯新增示例 + 测试 + 一个 CI step，回滚无运行时影响：

```bash
# 提交前回滚（删除新增文件 + 还原 CI）
rm -rf examples/quickstart tests/test_quickstart_example.py docs/release/tasks/FIX-02.md
git checkout -- .github/workflows/ci.yml

# 提交后回滚
git revert <FIX-02 提交>
```

---

## 附录 A：README「快速开始」建议文字（Lead 合并）

建议插入在 README `## 快速开始` 的依赖列表与第一个 PowerShell 代码块之后（即 `galnx engines list` 那段之后），作为「先验证安装」的最小路径：

```markdown
### 最小可跑示例（只需 Python）

不想先装 devkitPro？用仓库自带的 quickstart 验证「manifest → 执行 → artifact → 缓存」整条链路：

```bash
PYTHONPATH=src python -m galnx build run --manifest examples/quickstart/manifest.yaml --yes
```

首跑会执行 `tools/pack_demo.py` 生成 `examples/quickstart/out/demo.pak`（269 B）；再跑一次会命中缓存：

```
build: 0 executed, 0 not configured, 1 cache hit(s)
```

改动 `examples/quickstart/content/` 下任一文件后再跑，缓存失效并重新生成。注意：该示例的 `game.source_dir` 相对当前目录解析，请**在仓库根执行**。完整说明见 [examples/quickstart/README.md](examples/quickstart/README.md)。
```

（上面代码块内的反引号按 README 实际需要调整；示例资产为纯文本，不含游戏素材。）

## 附录 B：可选的根 .gitignore 条目（Lead 决定）

若希望用一条根级规则代替 `examples/quickstart/.gitignore`，可在根 `.gitignore` 增加：

```
examples/quickstart/out/
```

两种方式等价；当前实现保留局部 `.gitignore`，因为它与示例自包含，复制走也不丢规则。
