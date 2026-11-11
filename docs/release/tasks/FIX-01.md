# FIX-01 任务报告

> GalNX 0.1.0-preview 发版后收口修复：非 TTY 构建确认绕过（源自用户 m42143 专家复审表）。
> 本文件是任务交付报告；改动见同工作区 git diff（由 Lead 统一提交）。

## Task ID

FIX-01（专家复审 #1，最高风险项；执行者 lead）。共享任务板无独立 task 记录，本项由 Lead 直接执行。

## Source commit

`c7d389e9556a3bf76e71be236c724d05727cb57a`（main HEAD，docs: record GalNX-public snapshot 5 (0.1.0-preview)）。

## Files changed

| 文件 | 类型 | 行数变化 | 说明 |
| --- | --- | --- | --- |
| `src/galnx/cli.py` | 已跟踪修改 | +63 / -4 | 新增 `_stdin_is_interactive()` / `_confirm_execution()`；`build run` / `batch build` 非交互拒绝；EOF 视为拒绝 |
| `tests/test_build_contract.py` | 已跟踪修改 | +63 / -3 | `run_cli_split()`；2 个拒绝用例；`ConfirmHelperTests`（EOF/空输入/y） |
| `tests/test_batch_build_cli.py` | 已跟踪修改 | +16 / -16 | batch build 与 build run 调用补 `--yes` |
| `docs/MANIFEST.md` | 已跟踪修改 | +1 / -0 | 信任边界新增「非交互不默认放行」条目 |
| `docs/release/tasks/FIX-01.md` | 新增 | 本报告 | — |

## Observed problem

专家复审（m42143）指出：**非交互环境下缺少显式 `--yes` 时仍可能执行命令**。
复现：

1. `cmd_build_run` 的确认条件是 `if plan.get("state") == "configured" and not args.yes and sys.stdin.isatty():`——把 `isatty()` 当作「是否要确认」的判据，于是 stdin 不是 TTY 时**直接跳过确认并执行** `build.commands`。CI、管道、被其他脚本调用都属于这种情况。
2. `cmd_batch_build` 完全没有确认门：batch build 会对目录下每个 manifest 的 `build.commands` 直接 spawn，任何非交互调用都会执行。
3. 复跑取证时还发现一个附带缺陷：Windows 的 `NUL` 设备是字符设备，`isatty()` 会返回 True，此时 `input()` 抛 `EOFError`，CLI 以 traceback 崩溃（exit 1）而不是干净拒绝。

## Decision

- **改为 fail-closed**：非交互（`sys.stdin.isatty()` 为假）且没有 `--yes` 时，`build run` 与 `batch build` 一律拒绝执行，打印固定提示并用退出码 2 结束；不创建任何产物。
- **交互态仍保留二次确认**：终端下先打印执行计划，再问 `Execute these commands? [y/N]`，非 y/yes 中止。`--yes` 跳过确认，但计划仍然打印。
- **EOF 等价于拒绝**：`_confirm_execution()` 捕获 `EOFError` 返回 False，兼容 Windows `NUL`/已关闭 stdin，绝不把读不到输入当成同意。
- 不改动 `build run --dry-run`、`package`、`engines` 等不 spawn 的路径，也不改变 `batch build --yes` 在 CI 中的正常用法（现有测试统一补 `--yes`）。

## Behavior before

- 非交互 `galnx build run --manifest X`：**执行** `build.commands`（漏洞）。
- 非交互 `galnx batch build --dir D`：**执行**所有匹配 manifest 的 `build.commands`（漏洞）。
- Windows `NUL` stdin：`input()` 抛 `EOFError`，traceback，exit 1（未执行，但崩溃）。

## Behavior after

- 非交互 `galnx build run --manifest X`：先打印完整计划，随后 stderr 输出 `refusing to execute build.commands: no interactive terminal and no --yes; re-run with --yes to execute`，**exit 2，不执行**。
- 非交互 `galnx batch build --dir D`：同上，**exit 2，不执行**。
- Windows `NUL` stdin（isatty 为真但读不到输入）：stdout 打印 `aborted: user declined; nothing was executed`，**exit 2，不执行**，不再 traceback。
- 交互终端：计划照旧打印，问 `[y/N]`；`y/yes` 才执行。
- `--yes`：跳过确认，行为与 0.1.0-preview 相同（exit 0 / 产物 / 缓存照常）。

## Tests added

`tests/test_build_contract.py`：

1. `run_cli_split(argv) -> (code, stdout, stderr)`：同时重定向两个流，便于断言 stderr 拒绝提示。
2. `test_build_run_refuses_non_interactive_without_yes`：断言 exit 2、stderr 含 `no interactive terminal and no --yes`、stdout 仍含 `build plan:`、`out/demo.bin` 不存在。
3. `test_batch_build_refuses_non_interactive_without_yes`：断言 batch build 同样 exit 2 且 stderr 含拒绝提示。
4. `ConfirmHelperTests.test_confirm_helper_treats_eof_as_decline`：`input` 抛 `EOFError` → False；`" y "` → True；空串 → False。

`tests/test_batch_build_cli.py`：14 处 `batch build` 与 1 处 `build run` 调用补 `--yes`（这些用例验证的是执行/缓存语义，不是确认门）。

## Commands

```bash
# 单元/契约测试
cd "E:/Othergames/Nintendo Switch/Workspace/GalNX"
PYTHONPATH=src GALNX_BUILD_ROOT=E:/galnx-build python -m pytest -q tests/test_build_contract.py
PYTHONPATH=src GALNX_BUILD_ROOT=E:/galnx-build python -m pytest -q tests/test_batch_build_cli.py tests/test_build_contract.py

# 取证脚本（临时工程 E:/galnx-build/fix01/proj，stdin=pipe 模拟 CI）
python E:/galnx-build/fix01_run_evidence.py
```

取证工程：`games/demo/data.xp3` + `build.py`（写 `out/demo.bin`）+ `demo.yaml`（`build.commands`/`artifact`/`inputs` 齐备，`switch.title_id=010047410000A001`）。

## Test results

| # | 场景 | stdin | `--yes` | 退出码 | 产物 | stderr / stdout 关键行 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `build run` | pipe | 无 | **2** | 无 | `refusing to execute build.commands: no interactive terminal and no --yes; re-run with --yes to execute` |
| 2 | `batch build` | pipe | 无 | **2** | 无 | 同上 |
| 3 | `build run` | Windows `NUL` | 无 | **2** | 无 | stdout `aborted: user declined; nothing was executed`（EOF 安全，无 traceback） |
| 4 | `build run` | pipe | `--yes` | **0** | `out/demo.bin` 16 B sha256 `c76faba18e8d5f062b307f3d0aeb9bb3d1bf876b2d588d930848b040983c9c94` | 计划 + 执行日志 |

- `tests/test_build_contract.py` → **19 passed in 2.26s**。
- `tests/test_batch_build_cli.py tests/test_build_contract.py` → **28 passed in 4.74s**。
- 全量回归见计划 v1.45 与提交说明（由 Lead 在合并所有 FIX 后统一跑）。

## Unverified assumptions

- 未在真实 GitHub Actions runner 上验证（本地用 `stdin=pipe` 等价模拟 CI；`isatty()` 语义在 windows-latest / ubuntu-latest 的 pipe 下均为 False）。
- `--yes` 在 CI 下不打印确认提示，仅打印执行计划，符合「先看后跑」但不构成人工复核——依赖 CI 日志留痕。

## Known limitations

- 拒绝时退出码统一为 2（与既有用法错误一致），没有单独的 `not_confirmed` 机器可读码；需要区分时看 stderr 文案。
- `batch build` 的拒绝发生在遍历 manifest 之前，因此不会产生任何报告文件。
- 交互态确认只接受 y/yes（大小写不敏感），其他输入（含空行）一律视为拒绝。

## Rollback

`git checkout c7d389e -- src/galnx/cli.py tests/test_build_contract.py tests/test_batch_build_cli.py docs/MANIFEST.md`（并删除本报告）。回滚后 `build run` 恢复「非 TTY 直接执行」的旧行为，不建议。
