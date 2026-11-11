# CLEAN-01..CLEAN-04 — 专家清单第 3 轮收口（2026-11-11）

- **Task ID:** CLEAN-01 / CLEAN-02 / CLEAN-03 / CLEAN-04
- **Source commit:** `1595ae3`（私有 `KIRARITenshiChan/GalNX` main，工作树基线；C1 提交 `14e6f4c`，本报告随 C1 入库）
- **Files changed:** `README.md`、`THIRD_PARTY_NOTICES.md`、`docs/third_party/README.md`、`docs/third_party/inventory.yaml`、`docs/PLAN_DRAFT_v1.47.md`（新增）、`docs/release/tasks/CLEAN-01-04.md`（本文件）、`docs/environment/public-release.md`（CLEAN-04 登记）、`docs/release/0.1.0-preview.md`（CLEAN-04 登记）、`docs/release/expert-review-0.1.0.md`（§13）、`docs/release/README.md`（tasks 行）
- **Observed problem:** 专家第三轮清单指出 4 处收口问题：①README 的 Pilot-04 状态与 RFVP 试点数量与 `docs/engines/verification-matrix.md`/descriptor 不一致（写「4 部试点」且未说明 Pilot-04 只是 `device_verified`）；②README 把 `galnx build run --manifest examples/pilot04-akaseka.yaml --yes` 当「真正执行」示例，但 pilot 清单不声明 `build.commands`，该命令只会进入 `not_configured` 状态，误导新用户；③SBOM 漏掉第 5 个已交付 NSP（AKASEKA HD v1.4.1-test），组件与产物关联不完整；④公开发布材料需要按最新私有源重新生成快照并复核 REVIEW/ZIP。
- **Decision made:** 只做文档、元数据与发布操作，不改任何源码/引擎/产物行为；验收等级以验证矩阵为唯一口径（rfvp 3 部 FVP 试点、Pilot-04 `device_verified` 且注明缺口）；README 不再给 pilot 清单的「执行」示例，可执行示例只保留 `examples/quickstart/`；SBOM 覆盖全部 5 个已交付 NSP 并补齐组件 artifacts 关联；公开发布材料由 sanitizer/publish 脚本实跑生成，登记文档只追加。

## Behavior before

- README：rfvp 行写「4 部试点」；构建示例段给出 `examples/pilot04-akaseka.yaml --yes  # 真正执行`；工作流第 3 条暗示 pilot 清单可由 `galnx build run` 驱动真实引擎构建。
- SBOM：`docs/third_party/inventory.yaml` 只有 4 个产物（iroseka-nsp / sakura-nsp / k2nx-nsp / m0-hello-demo），AKASEKA HD 缺失且 8 个运行时组件未挂该产物；`THIRD_PARTY_NOTICES.md` 与 `docs/third_party/README.md` 写「33 个组件 / 4 个产物」；checker 输出 artifacts=4。
- 公开快照仍为第 6 个（源 `cc6148c`，公开 `071e2c9`），不含本轮 CLEAN 改动的登记。

## Behavior after

- README CLEAN-01：rfvp 行改为「3 部试点（Pilot-02/03/04，Pilot-01 是 kirikiroid2-nx）」；试点表中 Pilot-04 标注 `device_verified PASS` 并保留缺口说明（剧情全流程 / 存档读档 soak 未签收），与验证矩阵、`examples/engines/rfvp.yaml` 一致。
- README CLEAN-02：删除 pilot 清单的 `--yes`「真正执行」示例，明确「pilot 清单是真实记录、不声明 `build.commands`；真实引擎构建由 `docs/builds/` 记录的 `scripts/*.sh` 驱动」；`--dry-run` 输出 `state: not_configured`（退出码 3），`--yes` 只进入批处理预检（缺 prod.keys 时 preflight fail、退出码 2；前置齐全时退出码 3）且不生成构建产物；真正验证执行与缓存的示例统一指向 `examples/quickstart/`（FIX-02）。工作流第 3 条同步改写。
- SBOM CLEAN-03：`inventory.yaml` 新增 `akaseka-nsp` 产物（`AKASEKA HD`、v1.4.1-test、6,738,209,496 B sha256 `db31a312c745e46b73f11445168af94ad6790989d847f184a8d2cd6312190c8f`、path `/e/galnx-build/p45/out/AKASEKA_HD-010047420000d000.nsp`、`distributed: false`）；给 8 个运行时组件（rfvp、ffmpeg-nvtegra、sdl2、zlib、mesa-switch、libdrm-nouveau、libnx、gcc-runtime）补 `artifacts: [..., akaseka-nsp]`；baseline commit 更新为 `1595ae3…`；`THIRD_PARTY_NOTICES.md` / `docs/third_party/README.md` 改为「33 个组件 / 5 个产物」；checker 输出 artifacts=5、errors=0。
- CLEAN-04：在本轮提交后的 HEAD 上重新运行 sanitizer 生成第 7 个公开快照并推送 `GalNX-public`；快照元数据（源 commit、公开 commit、文件数、字节、BLOCK/REVIEW、ZIP sha256）登记到 `docs/environment/public-release.md` §4.5 与 `docs/release/0.1.0-preview.md` §8。实测：源 `14e6f4c` → 公开 `9fd346a`（tree `956c80df…`）；sanitizer kept=1,022 / excluded=359 / 导出 bytes 27,524,118 / `0 BLOCK` / review 473（dev path 443 + keyword 30）/ home 路径脱敏 539 处 191 文件；镜像 `git ls-files` 1,022 文件 / 27,547,657 B；ZIP 9,543,597 B sha256 `ffddcef4…`。

## Tests added

- 未新增测试：本轮只改文档与 SBOM 元数据，无代码路径变化。既有 `tests/test_license_inventory.py`（24 用例）覆盖 inventory 结构、产物关联、GPL 义务与路径安全，CLEAN-03 后仍全绿；`tests/test_public_release.py`（60 用例）覆盖 sanitizer；全量回归见下。

## Commands executed

```text
# CLEAN-02 取证
PYTHONPATH=src python -m galnx build run --manifest examples/pilot04-akaseka.yaml --dry-run
#   → DRY_RC=3，state: not_configured，artifact: (none)
PYTHONPATH=src python -m galnx build run --manifest examples/pilot04-akaseka.yaml --yes
#   → 无 GALNX_PROD_KEYS 时 YES_RC=2（preflight fail: prod.keys）
#   → GALNX_PROD_KEYS 指向 Ryujinx prod.keys 时 YES_RC=3，0 executed / 1 not configured

# CLEAN-03 校验
PYTHONPATH=src python scripts/check_license_inventory.py --json
#   → rc 0, ok=true, components=33, artifacts=5, errors=[], warnings=2
PYTHONPATH=src python -m pytest -q tests/test_license_inventory.py

# CLEAN-04（C1 提交后）
python scripts/public_release_sanitize.py --repo . --out E:/galnx-build/public/GalNX-v147 --zip E:/galnx-build/public/GalNX-v147.zip --force
python scripts/public_release_publish.py --repo . --mirror E:/galnx-build/public/GalNX-public
#   然后 cred_use GH_TOKEN（mode=exec, git）推送 mirror
```

## Test results

- `tests/test_license_inventory.py`：24 passed（CLEAN-03 后）。
- 全量回归：见提交前最后一次 `pytest -q`（`747 passed / 63 subtests` 基线，本轮文档改动后仍应保持；数字登记于 `docs/release/expert-review-0.1.0.md` §13.1 与计划 v1.47）。
- CLEAN-04 实测：源 `14e6f4c` → 公开 `9fd346a`；镜像 1,022 文件 / 27,547,657 B；`0 BLOCK` / review 473；ZIP 9,543,597 B sha256 `ffddcef4…`。
- CLEAN-02 实测：`--dry-run` 退出码 3；`--yes` 在缺 keys 时退出码 2、keys 齐全时退出码 3；两种情况均未生成构建产物（`examples/.galnx` 运行目录已清理，`.gitignore` 已忽略）。

## Unverified assumptions

- README 的 `--yes` 退出码描述基于本机两种前置状态（缺 prod.keys / 有 prod.keys）实测；其他 preflight 失败（如 build-root 不可写）同样会让退出码为 2，文档用「缺 prod.keys 等前置」概括，未穷举全部 preflight 检查。
- AKASEKA NSP 的 SBOM 条目复用既有 `db31a312…` 产物哈希，未在本轮重新构建或重新 verify（该产物已在 P44 完成 verify 与真机验收）。
- 公开快照的 REVIEW 数量依赖当前导出内容；CLEAN-04 实测 review=473（较上一快照 469 增加 4，来自本轮新增文档正文），后续如变化仍以 `docs/environment/public-release.md` §4.5 实跑数字为准。

## Known limitations

- 本轮不修复 README 之外的历史文档（`docs/builds/` 50+ 篇记录与旧计划快照仍可能含旧示例/旧数字，按「历史不可篡改」原则保留）。
- 公开树按决策 56 落后私有仓库一个 docs 提交：登记 CLEAN-04 快照数字的 docs 提交会进入下一个快照，`PUBLIC_RELEASE.md` 的快照源 commit 指向 C1 而非本登记提交。
- SBOM 的 `distributed: false` 表示仓库不分发 NSP 二进制；用户本机构建安装时仍需按 GPL-2.0-or-later 履约（FFmpeg nvtegra + NVDEC）。

## Rollback method

- 文档回滚：`git revert <CLEAN 提交>` 即可（无数据迁移、无 schema 变化）。
- SBOM 回滚：恢复 `docs/third_party/inventory.yaml` 与两份 notices 到 `1595ae3` 版本；checker 会回到 artifacts=4。
- 公开快照不可回滚（不 force-push）：如需纠正，按决策 56 追加一个新快照 commit，不回改历史。
