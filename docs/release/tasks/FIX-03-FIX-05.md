# FIX-03 / FIX-05 任务报告

> GalNX 0.1.0-preview 发版后收口修复：Pilot-04 验收等级校准 + rfvp descriptor 旧版本信息清理（源自用户 m42143 专家复审）。
> 本文件是任务交付报告；改动见同工作区 git diff（未提交，由 Lead 统一提交）。

## Task ID

FIX-03 / FIX-05（共享任务板 task-66；执行者 audit-engines）。

## Source commit

`c7d389e9556a3bf76e71be236c724d05727cb57a`（main HEAD，docs: record GalNX-public snapshot 5 (0.1.0-preview)）。
本报告基于该提交 + 当前未提交工作树；任务 claim 时 git status 干净。

## Files changed

| 文件 | 类型 | 行数变化 | 说明 |
| --- | --- | --- | --- |
| `README.md` | 已跟踪修改 | +1 / -1 | 仅 Pilot-04 行结论与缺口说明 |
| `docs/engines/verification-matrix.md` | 已跟踪修改 | +4 / -3 | Pilot-04 结论、rfvp 能力汇总、§2 说明、§6 新增复审条目 |
| `docs/pilot/0.1.0-device-acceptance.md` | 已跟踪修改 | +4 / -1 | §1 口径说明、§2.2 未验证项、§3 未确认表 |
| `docs/engines/README.md` | 已跟踪修改 | +5 / -5 | rfvp 产物/能力/引擎级验证/已知限制、§12 分层表 |
| `examples/engines/rfvp.yaml` | 已跟踪修改 | +48 / -32 | graphics/input 降级、status_reason/notes/verification 重写、证据补充 |
| `docs/release/tasks/FIX-03-FIX-05.md` | 新增 | 本报告 | — |

Scope 遵守：只改上表 write scope 内文件；未改 `src/`、`schemas/`、`tests/`、`scripts/`、`docs/MANIFEST.md`、其他任务报告；未执行任何 git 写操作（仅 git status/diff/numstat 只读）。

### Deviation（任务描述与现实的偏差）

1. 任务描述给的行号基于旧版；按实际内容定位：matrix Pilot-04 行 = 39、rfvp 能力汇总行 = 66、§2 说明行 = 41、§6 末尾 = 97；README Pilot-04 行 = 14；`docs/engines/README.md` 产物/能力/引擎级/已知限制 = 246–249、§12 分层表 = 325；`examples/engines/rfvp.yaml` status_reason = 105–126、notes = 170–181、verification.notes = 202–219。
2. 任务只要求「第 30 行标题保持」；实际 §2 标题未动（仅改说明行 41）。
3. 额外修正 `docs/engines/README.md` §12 分层表「rfvp（4 个 Pilot）」→「rfvp（3 个 Pilot）」：原表述把 Pilot-01（kirikiroid2-nx）算进 rfvp，与本次证据对账同属一类错误，且在 write scope 内。

## Observed problem

1. FIX-03：Pilot-04（AKASEKA HD）在验证矩阵与 README 记为 `game_verified`，但用户签收 m39477 / m40951 只覆盖 1080p H.264 OP 颜色与流畅度、手柄映射、干净退出；剧情全流程、存档/读档、长时间 soak 均无验收记录。rfvp 的 graphics/input 能力继承该结论记为 `game_verified`，与矩阵对 `game_verified` 的定义（真机完整验收：启动→剧情→存档/读档→手柄→退出）不符。
2. FIX-05：`examples/engines/rfvp.yaml` 残留旧交付信息——status_reason/notes 仍写 1.2.4-test / 1.3.2-test / 1.4.0-test 与「v1.0.8 构建 9,979,496,664 B、真机安装待定」；verification.notes 称 Pilot-04 1.4.0-test 为正式验收、Pilot-02/03 为 1.2.4/1.3.2 且「无验收日志」，与当前交付（1.2.5-test `f6860842…` / 1.3.3-test `965ee356…` / 1.4.1-test `db31a312…`）及 `docs/pilot/0.1.0-device-acceptance.md` 不一致。

## Decision

FIX-03：把 Pilot-04 的游戏级结论与 rfvp 的 graphics/input 能力降为 `device_verified`（顶层 verification 原本已是 `device_verified`，本次不改 hardware / tested_at）；在 5 个文件同步缺口说明，不删除已有证据，也不把未验证项写成已验证。save 能力维持 `device_verified` 而非降到 `partial`：早前 rfvp 真机跑过 save/load 路径（P4-device-runbook §13 检查表、pilots 记录干净退出），但 0.1.0 签收未逐项列出，属「有证据但不完整」，故保留等级并写明缺口（见 Unverified assumptions）。

FIX-05：以当前交付版本与 0.1.0 签收索引为准重写 rfvp.yaml 的 status_reason / notes / verification.notes / evidence；`pinned_commit 9f07adef…` 与 `artifact_sha256 db31a312…` 保留（与验证矩阵一致）。不改 README 其他行、不改 `docs/release/0.1.0-preview.md`（不在 write scope，且其第 46 行已是 device_verified）。

## Behavior before

- `docs/engines/verification-matrix.md` 行 39 结论 = `game_verified PASS`（用户 m39477、m40951）；行 66 rfvp graphics/input = `game_verified`；无 Pilot-04 缺口说明。
- `README.md` 行 14 = `game_verified PASS`（未注明缺剧情全流程与存档/读档）。
- `docs/pilot/0.1.0-device-acceptance.md` 无 Pilot-04 缺口记录。
- `docs/engines/README.md` 产物例 = AKASEKA 1.4.0-test 6,676,387,544 B（`569af9fb…`）；能力 graphics/input = `game_verified`；引擎级「4 个 Pilot 真机 PASS」；§12 分层表 `rfvp`（4 个 Pilot）。
- `examples/engines/rfvp.yaml` graphics/input = `game_verified`；status_reason 写 1.2.4-test / 1.3.2-test / 1.4.0-test；notes 写 v1.0.8 待真机安装；verification.notes 写 1.4.0-test 正式验收、1.2.4/1.3.2 无验收日志。

## Behavior after

- `docs/engines/verification-matrix.md` 行 39 = `device_verified PASS`（用户 m39477、m40951；缺剧情全流程与存档/读档，见 §6）；行 41 说明补充「Pilot-04 按 device_verified 记录」；行 66 rfvp graphics/movie/audio/input/save = `device_verified`、touch = `unknown`；§6 新增「Pilot-04 未达 game_verified」复审条目。
- `README.md` 行 14 = `device_verified PASS`（1080p H.264 OP 颜色正确且流畅 / 映射符合预期 / 干净退出；缺剧情全流程与存档/读档验收）。
- `docs/pilot/0.1.0-device-acceptance.md`：§1 表后 blockquote 说明 Pilot-04 记 `device_verified`；§2.2 Pilot-04 行追加「未验证：剧情全流程推进、存档/读档、长时间 soak」；§3 未确认表新增对应行。
- `docs/engines/README.md`：产物例 = AKASEKA 1.4.1-test 6,738,209,496 B（`db31a312…`），1.4.0-test 标为上一版；能力 = graphics/input/movie/audio/save 全 `device_verified`、touch `unknown`；引擎级 = 「2026-11-10，3 个 rfvp Pilot 真机 PASS（Pilot-01 属 kirikiroid2-nx）」；§12 = `rfvp`（3 个 Pilot）；已知限制补 Pilot-04 缺口。
- `examples/engines/rfvp.yaml`：graphics/input = `device_verified` 且 note 写明未做 end-to-end story；save note 写明 0.1.0 签收未逐项列 save/load；status_reason 重写为三 pilot 当前包 + 缺口；notes 改为 P44/P45 当前三包已装真机；verification.evidence 补 `docs/pilot/0.1.0-device-acceptance.md`、`docs/builds/049-p41-snow-particles.md`；verification.notes 重写；pinned_commit / artifact_sha256 不变。
- 描述符与 CLI 复核：`load_descriptor` 返回 rc=0，capabilities = graphics/movie/audio/input/save `device_verified`、touch `unknown`、warnings = ()；`engines list` / `engines info rfvp` / `engines plan --manifest examples/pilot04-akaseka.yaml` 全部 exit 0。

## Tests added

none。本次只做文档与 descriptor 数据校准，无新增代码路径；描述符行为由既有测试覆盖：`tests/test_engines_descriptor.py`、`tests/test_engines_registry.py`、`tests/test_engines_contract.py`、`tests/test_engines_cli.py`、`tests/test_engines_source.py`、`tests/test_templates.py`。

## Commands

    # 1) 测试（repo 根，PYTHONPATH=src，PATH 需含 git 与 scoop shims）
    D:/Scoop/apps/python312/current/python.exe -m pytest -q tests/test_engines_descriptor.py tests/test_engines_registry.py tests/test_engines_contract.py tests/test_engines_cli.py tests/test_engines_source.py tests/test_templates.py

    # 2) 描述符校验
    PYTHONPATH=src python -c "from galnx.engines.descriptor import load_descriptor; d=load_descriptor('examples/engines/rfvp.yaml'); print(d.status, d.to_dict()['verification'], d.warnings)"

    # 3) CLI 冒烟
    PYTHONPATH=src python -m galnx engines list --engines-dir examples/engines
    PYTHONPATH=src python -m galnx engines info --engines-dir examples/engines rfvp
    PYTHONPATH=src python -m galnx engines plan --manifest examples/pilot04-akaseka.yaml --engines-dir examples/engines

    # 4) 只读 diff/numstat
    git status --porcelain
    git diff --numstat -- README.md docs/engines/verification-matrix.md docs/pilot/0.1.0-device-acceptance.md docs/engines/README.md examples/engines/rfvp.yaml

## Test results

- 最终：`152 passed, 12 subtests passed in 55.03s`（exit 0）。
- 首次失败说明：同一 pytest 命令在 PATH 限定为 python + System32 的 shell 下跑出 `134 passed, 18 failed`；18 个失败全部在 `tests/test_engines_source.py`（VerifyPinTests / PrepareTests / CheckOnlyTests / CommandLineTests），异常为 `FileNotFoundError: [WinError 2]` @ subprocess.Popen → 临时 git 仓库测试找不到 `git`。把 `D:/Scoop/apps/git/current/bin`、`D:/Scoop/apps/git/current/cmd`、`D:/Scoop/shims` 加回 PATH 后全绿。属测试环境 PATH 问题，不是代码回归。
- CLI 冒烟：`engines list` / `engines info rfvp` / `engines plan --manifest examples/pilot04-akaseka.yaml` 均 exit 0；info 输出显示 `audio=device_verified graphics=device_verified input=device_verified movie=device_verified save=device_verified touch=unknown`、engine verification `device_verified (tested 2026-11-10)`。
- 运行测试时工作树还包含他人的 FIX 系列未提交改动（`docs/MANIFEST.md`、`src/galnx/build/cache.py`、`src/galnx/cli.py`、`tests/test_build_cache_inputs.py`、`tests/test_batch_build_cli.py`、`tests/test_build_contract.py` 等），152 passed 是在该混合工作树上取得；本次未触碰这些文件。

## Unverified assumptions

1. save 能力仍记 `device_verified`：`docs/pilot/P4-device-runbook.md` §13 是检查表/流程文档，仓库内没有「执行结果」签收；pilots 的「干净退出」不等于 save→reload 验证。若 Lead 认为证据不足，可进一步降为 `partial`。
2. Pilot-04 的「手柄映射」证据来自 1.4.0-test（m39477）与 1.4.1-test（m40951 只报 OP 颜色/流畅）；把两条签收合并用于 Pilot-04 一行是验证矩阵既有口径，本次未改。
3. `docs/release/0.1.0-preview.md` 第 46 行已写 rfvp `device_verified`，本次未改（不在 write scope），假定其正确。
4. `docs/release/tasks/TASK-ENGINES.md` 是 task-63 当时的历史报告，含旧结论（game_verified / 4 个 Pilot）；按「不改其他任务文件」保留，未回改。

## Known limitations

- Pilot-04 仍未达 `game_verified`：缺剧情全流程、存档/读档、长时间 soak 的签收记录；补一条完整流程验收后可再升级。
- firmware / Atmosphere 版本未记录，descriptor 的 verification 块相应字段留空。
- 本次不改 `src/`、`schemas/`、`tests/`；CLI `info` 文本输出仍只打印 capabilities 的 supported 摘要（属 Lead / 其他任务 scope）。
- `docs/engines/README.md` §8.1 产物例已更新为 1.4.1-test，但该文档其余历史构建描述未逐条复核。
- 工作树存在其他队友未提交的 FIX 改动与临时文件（`.tmp_debug_fix04.py`、`examples/quickstart/` 等），提交前需由 Lead 归并甄别。

## Rollback

本次未做任何 git 写操作；回滚只需丢弃工作树改动：

    git checkout -- README.md docs/engines/verification-matrix.md docs/pilot/0.1.0-device-acceptance.md docs/engines/README.md examples/engines/rfvp.yaml
    rm docs/release/tasks/FIX-03-FIX-05.md

若这些文件已被 Lead 提交，则 `git revert` 对应提交。注意：同一工作树可能有其他 FIX 任务改动，回滚前先确认 diff 归属，避免误伤他人改动。
