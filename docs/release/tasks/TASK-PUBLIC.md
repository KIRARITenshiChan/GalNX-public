# TASK-PUBLIC

## Task ID

TASK-PUBLIC（专家计划 P0-3：补强公开快照安全检查）

## Source commit

`974a414`（`main`，任务开始时 HEAD）。注意：执行期间其他队友在并行修改源码/文档，工作树含未提交改动；本文数字取自 2026-11-11 02:38 的本地工作树快照（脚本实时计算，随工作树漂移）。

## Files changed

| 文件 | 行数 | 说明 |
| --- | --- | --- |
| `scripts/public_release_sanitize.py` | 1,043 | 重写：导出策略（art/data 排除、markdown 改写、home 路径脱敏）+ fail-closed 扫描闸门（BLOCK/REVIEW/ALLOW）+ 确定性 ZIP + 报告生成 |
| `scripts/public_release_publish.py` | 273 | 增加 BLOCK 中止、幂等（仅时间戳变化不产生快照提交） |
| `tests/test_public_release.py` | 667 | 重写扩充：60 个用例（原 12 个） |
| `docs/environment/public-release.md` | 244 | 文档同步 fail-closed 规则、脱敏决策、基线数字、验收清单 |
| `docs/release/tasks/TASK-PUBLIC.md` | 本文件 | 任务报告 |

## Observed problem

1. 旧 `public_release_sanitize.py` 只按「三个路径前缀 + 图片后缀」排除游戏素材，不做任何内容检查：伪装扩展名的 PE/ELF、NSP/NCA、XP3/WMV、keys 文本、token/私钥、个人目录路径都可能进入公开树。
2. 旧 `public_release_publish.py` 生成树后直接 `git add -A` 并提交，即使公开树包含违规文件也会发布（只在打印推送命令前停下，没有闸门）。
3. `PUBLIC_RELEASE.md` 的数字由人维护，容易与真实快照漂移；文档里的「grep token / find png」等检查靠手工，不可审计。
4. 真实仓库历史里存在大量开发机痕迹：`C:\Users\<user>` 形式的个人目录路径 190 个文件 / 448 处（历史日志切片），`E:/`、`D:/` 开发机路径 484 个文件 / 4,203 处。如果对个人目录直接 BLOCK，公开快照将永远无法生成（任务同时要求「真实仓库 sanitize 通过、block=0」）。
5. 幂等性未验证：重复运行 publish 可能因为 `PUBLIC_RELEASE.md` 的生成时间戳变化而每轮制造空提交；mirror 保留的 `.git` 目录在第二次生成时会被扫描器当成二进制内容误报。

## Decision made

1. **两层策略**：导出策略决定「哪些文件不进公开树」，扫描闸门决定「公开树/ZIP 是否可发布」。任一 BLOCK → 异常 + 退出码 1，publish 不 stage/不 commit、不打印推送命令。
2. **排除类型分为 art / data**：art = 三个前缀下的 `.png/.jpg/.jpeg/.webp/.gif/.bmp`（新增 `.bmp`，因为 `probe5-mpeg2-device.bmp` 是商业游戏解码帧）；data = 任意位置的 `.nv12/.nsa`（新增，裸 NV12 帧与空 nsa 占位）。两类分别统计，避免「图片数」掩盖数据文件。
3. **白名单带 reason**：`IMAGE_ALLOWLIST` 与 `FILE_ALLOWLIST` 条目为 `{"path", "reason"}`（兼容旧字符串）。默认 `FILE_ALLOWLIST` 仅 1 条：`examples/batch/games/demo-a/data.xp3`（62 B UTF-8 占位 fixture，无 XP3 magic），避免高危扩展名规则误杀合法测试夹具；命中项在报告中列为 allowlist（ALLOW）并展示理由。
4. **高危扩展名/文件名 + magic bytes + 文本规则 + REVIEW 分级**：按任务清单实现，并按仓库实际内容校准（真实仓库扫描 0 误杀：合法 jpg/png/yaml/json/py/md、4 个 latin-1 无 NUL 的历史日志均通过）。`>8 MiB` 定为 **REVIEW**（不是 BLOCK）：当前仓库无超限文件，BLOCK 会让未来合法的 PDF/大日志无法发布，而复核成本低；理由写入文档。
5. **个人目录路径：导出时确定性脱敏 + 扫描器仍 BLOCK 残留**。这是对任务「个人目录 → 阻断」的有意偏离：真实仓库 190 文件/448 处历史路径若 BLOCK 会导致快照永远无法生成。做法是在生成公开树时把 `C:\Users\<name>` / `C:/Users/<name>` 确定性改写为 `C:\Users\<user>` / `C:/Users/<user>`，统计 `redacted_files`/`redacted_home_hits` 写入报告；扫描器本身仍把 home 路径判 BLOCK（二进制/不可解码文件不做改写，残留即阻断）。
6. **扫描两次**：生成树扫一次（跳过 `.git` 与两个脚本生成报告文件），ZIP 打包后从 ZIP 条目复扫一次（直接读字节判定，不解包）。ZIP 采用确定性参数（排序、固定 date_time、固定权限位），保证同输入两次 zip sha256 相同。
7. **报告脚本生成**：`PUBLIC_RELEASE.md` 的 source commit、计数、扫描结果、allowlist 命中、ZIP 大小/sha256 全部由脚本计算；唯一允许的时间戳是 `generated_at`（UTC）。
8. **publish 幂等**：比较新旧 `PUBLIC_RELEASE.md` 时忽略 `Generated (UTC)` 行；等价时回退报告文件精确字节，避免「仅时间戳变化」的空提交。mirror 的 `.git` 在扫描/打包时跳过。
9. **顺带修复**：markdown 围栏代码块识别补上反引号（原实现只识别 `~~~`，与 docstring 承诺不符；tests 已覆盖）。

## Behavior before

- `python scripts/public_release_sanitize.py --out ...`：仅排除图片；输出树可含任何其他文件；无扫描、无 BLOCK 概念；退出码 0。
- `python scripts/public_release_publish.py --mirror ...`：生成树后无条件 `git add -A` + commit，不检查内容；重复运行可能每轮产生新提交；第二次运行可能因 mirror 的 `.git` 命中二进制规则而误报（修复前无扫描，故未暴露）。
- `PUBLIC_RELEASE.md`：内容为手写模板 + 少量运行时数字，扫描结果/allowlist/ZIP 信息缺失。

## Behavior after

- sanitizer：`git ls-files` → art/data 排除 → 复制（markdown 改写 + home 脱敏）→ 写排除清单 → **扫树** → 可选**确定性 ZIP + 复扫** → 写报告。BLOCK>0 抛 `SanitizationError`、保留树供排查、不写报告、退出码 1；成功打印 kept/excluded/bytes、排除分类、scan block/review 分类、allowlist、ZIP size/sha。
- publish：生成/扫描失败即中止，不 stage/不 commit/不打印推送命令，退出码 1；成功打印 `scan: block=... review=...` 后才打印 `push with:`；幂等（源 commit 不变时第二次运行 committed=False，`git log` 仍只有一条快照提交）。
- 报告：脚本生成完整快照元数据；数字可复现。
- 真实仓库当前结果：`kept=985 excluded=359 bytes=25367155 rewritten_refs=0`；排除 `{'art': 357, 'data': 2}`；`scan block=0 review=461 scanned=985`（dev machine absolute path 431 + sensitive path keyword 30）；allowlist 命中 1 条；ZIP 8,618,045 B / sha256 `10dbb02cf5f20976c05caa9cb137fe02f3bd6f398687f2bc6d387ece7408670b`。

## Tests added

`tests/test_public_release.py` 从 12 个用例扩充到 **60 个**，覆盖任务要求的全部 10 类场景：

1. 导出策略：`is_game_asset` 参数化 8 例、允许白名单带 reason 覆盖前缀规则、FILE_ALLOWLIST 的 `data.xp3` 单条 ALLOW 且理由生效、`collect` 区分 art/data、`collect == git ls-files`、required policy files tracked。
2. 报告：计数/兼容子串/scan 段/ZIP sha、rewrite 计数、`_notes_equivalent` 只忽略生成时间戳。
3. markdown：图片引用改写、普通链接保留标签、围栏代码块（反引号与 `~~~`）跳过。
4. 扫描：普通文本免杀 4 参数、白名单 PNG/JPEG 通过、非白名单图片 BLOCK、未知二进制 BLOCK、高危扩展名/文件名 6 参数（xp3/wmv/xci/nsp/prod.keys/keys.txt）、伪装 PE/ELF/PFS0 magic BLOCK、伪装 ZIP（PK）BLOCK、密钥材料赋值 BLOCK、GitHub token BLOCK 且 detail 脱敏、PEM 私钥 BLOCK、个人目录 BLOCK、开发机路径仅 REVIEW、敏感路径关键词 REVIEW / 与高危扩展名组合升级 BLOCK、>8 MiB REVIEW。
5. 汇总/树/ZIP：`summarize_scan` 分组、`scan_tree` 跳过报告文件与 `.git`、`_write_zip` 确定性（两树同 sha、跳过 notes）、`scan_zip` 捕获 ZIP 内藏 MZ 文件。
6. build/publish：改写+排除计数、home 路径导出脱敏、BLOCK 时树保留且无报告、可复现（两次 build 的 zip sha/树快照/稳定 notes 一致）、真实仓库 build block=0、publish BLOCK 时抛异常且 mirror 无 commit、幂等两轮（rev-list count=1）、`publish.main` 返回 1 且 stdout 无 `push with:`、`sanitize.main` 返回 1。

敏感样本均在运行时拼接（例如 `"ghp_" + "a"*30`），测试文件自身扫描结果为空，避免文档/测试自触发扫描规则。

## Commands executed

```bash
cd '/e/Othergames/Nintendo Switch/Workspace/GalNX'
python -m py_compile scripts/public_release_sanitize.py scripts/public_release_publish.py tests/test_public_release.py
PYTHONPATH=src python -m pytest tests/test_public_release.py -q
PYTHONPATH=src python -m pytest -q
python scripts/public_release_sanitize.py --out E:/galnx-build/public-check --zip E:/galnx-build/public-check.zip --force
python scripts/public_release_publish.py --mirror E:/galnx-build/public-mirror-check   # 连续 3 次，验证幂等
```

## Test results

- `tests/test_public_release.py`：**60 passed in 21.66s**。
- 全量回归：**723 passed, 63 subtests passed in 67.87s**（基线含其他队友改动）。
- sanitizer 真实仓库验收：**block=0**，`kept=985 / excluded=359 / bytes=25367155`，ZIP 8,618,045 B sha256 `10dbb02cf5f20976c05caa9cb137fe02f3bd6f398687f2bc6d387ece7408670b`（输出目录 `E:/galnx-build/public-check`，未写入仓库）。
- publish 幂等实测（真实仓库，mirror `E:/galnx-build/public-mirror-check`）：RUN1 committed=True，RUN2/RUN3 committed=False 且 head 不变，`git log` 仅 1 条快照提交，`git status` 干净，`ls-files=985`。

## Unverified assumptions

- 未执行真实的 GitHub 推送（按纪律由 Lead 推送）；`cred_use` 注入 token 的 push 命令仅打印，未实际运行。
- publish 的幂等只在本地 mirror 验证 3 次，未在真实 `GalNX-public` 仓库验证。
- 扫描规则是「已知模式」匹配，无法证明覆盖所有未来的凭据/游戏数据格式。
- 真实仓库数字会随其他队友未提交改动漂移；本文记录的是 2026-11-11 02:38 工作树。Lead 提交后应重跑一次 sanitizer 记录最终快照数字（新增的本报告与文档会进入 tracked 集，review 计数可能 +1~2）。
- ZIP 复扫未在 GitHub 侧或其他解压工具上交叉验证，只在脚本内部复扫。

## Known limitations

- 只处理 git 跟踪的文件；未跟踪产物不在候选内。
- 个人目录脱敏仅作用于可解码文本且首 8 KiB 无 NUL 的文件；二进制不改写，命中即 BLOCK。
- `.git` 目录被跳过（mirror 跨轮保留 `.git`，扫描压缩对象会误报）。
- 大文件 >8 MiB 仅 REVIEW，需要人工确认。
- 不处理作者/邮箱信息。
- 排除是发布树层面的，私有历史仍保留全部证据。

## Rollback method

本次改动尚未提交，全部集中在 5 个文件：

```bash
cd "E:/Othergames/Nintendo Switch/Workspace/GalNX"
git checkout -- scripts/public_release_sanitize.py scripts/public_release_publish.py tests/test_public_release.py docs/environment/public-release.md
rm docs/release/tasks/TASK-PUBLIC.md
```

不涉及数据迁移或外部状态；generated 产物（`E:/galnx-build/public-check*`、mirror）可直接删除。回滚后旧版脚本行为与文档恢复原状。
