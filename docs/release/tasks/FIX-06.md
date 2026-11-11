# FIX-06 — 重新生成发布快照（公开树 6）并完成发布材料收尾

- 任务 ID：FIX-06
- 源 commit：`cc6148c`（私有 `KIRARITenshiChan/GalNX` main）
- 日期：2026-11-11
- 状态：完成（公开快照 6 已推送 `071e2c9`；本文档随 docs 收尾提交入库）

## 1. 观察到的实际问题

1. 0.1.0-preview 发布材料里的公开树数字停留在第 5 个快照：`docs/release/0.1.0-preview.md` §8 与 `docs/environment/public-release.md` 仍写 1,006 文件 / 26,078,021 B / 快照 `26dedca`。
2. 复审（`docs/release/expert-review-0.1.0.md` 图片版）指出 sanitizer 已达 0 BLOCK 但 REVIEW 数量偏高（上一轮 466），且快照元数据需要随 FIX 轮更新。
3. ZIP 归档需要在新一轮里重新生成并扫描（ZIP 内文件不在树扫描范围内）。
4. `PUBLIC_RELEASE.md` 里的生成时间 / 源 commit 需反映 FIX 轮收口后的真实状态。
5. 复核过程中发现 `docs/release/tasks/FIX-02.md` 与 `README.md` 的 quickstart 产物体积是旧迭代数字（283 B / demo.txt 106 B），与干净 clone 实测不符。

## 2. 决策

1. 用提交后的干净 HEAD `cc6148c` 全量重跑 sanitizer（fail-closed），并以它的输出作为第 6 个公开快照的唯一来源；不手工改公开树。
2. 把「0 BLOCK」与「REVIEW 逐类统计」分开记录：REVIEW 是人工复核队列，不是发布阻断项；本轮不逐条消减历史文档里的构建路径，只在 `public-release.md` §2.6 说明口径。
3. ZIP 在同一个 sanitizer 进程里生成并扫描（`scan_zip`），BLOCK 计数为树扫描 + ZIP 扫描之和，任一 BLOCK 都会让退出码非 0。
4. 公开仓库沿用「每快照一个追加 commit、不 force-push、不改写历史」的策略（决策 56）。
5. 用公开仓库的干净 clone 端到端复跑 `examples/quickstart` 作为发布验收（FIX-02 闭环），并把实测数字回填到 FIX-02 报告与 README，纠正旧笔误。

## 3. 行为变化（before → after）

| 项 | before | after |
|---|---|---|
| 私有源 commit（发布材料基线） | `c7d389e`（v1.44） | `cc6148c`（FIX-01..06 + 计划 v1.45） |
| sanitizer kept / excluded | 1,006 / 359 | **1,018 / 359**（art 357 + data 2） |
| 导出字节 | 26,078,021 | **26,606,932** |
| 扫描 BLOCK / REVIEW | 0 / 466 | **0 / 469**（dev path 439 + sensitive keyword 30） |
| 公开 commit | `26dedca` | **`071e2c9`** |
| 公开树（git ls-files） | 1,006 文件 / 26,078,021 B | **1,018 文件 / 26,630,480 B** |
| 发布 ZIP | 8.9 MB 级旧包 | **9,142,838 B** sha256 `17688031c987f29254801594c87c0137f1c44002eb3b430ce6a47e27cbd8ba90` |
| quickstart 产物口径 | 283 B（笔误） | **269 B** sha256 `5982bb06…`（干净 clone 实测） |

## 4. 改动文件

| 文件 | 内容 |
|---|---|
| `docs/release/tasks/FIX-06.md` | 本报告 |
| `docs/environment/public-release.md` | 基线数字（1,377 tracked / kept 1,018 / bytes 26,606,932 / block 0 / review 469 / ZIP 9,142,838 B sha256 `17688031…`）、§4.1 公开树 1,018 文件 / 约 26.6 MB、§4.5 第 6 快照行 |
| `docs/release/0.1.0-preview.md` | §8 Public mirror tree → 1,018 files / 26,630,480 B / snapshot `071e2c9` |
| `docs/release/expert-review-0.1.0.md` | §12 表格与 §12.2 实测数字（sanitizer、ZIP、干净 clone quickstart） |
| `docs/release/tasks/FIX-02.md` | 283→269 B、demo.txt 106→92 B、sha 前缀更正 |
| `README.md` | quickstart artifact 约 283 B → 269 B |
| `docs/release/README.md` | tasks 索引说明补充 FIX 报告 |
| `docs/PLAN_DRAFT_v1.46.md` + 计划原件 | v1.46 记录 |

## 5. 测试与验证

- 未新增自动化测试（本轮只改文档/发布材料；sanitizer 与 quickstart 的测试已在 TASK-PUBLIC / FIX-02 落地）。
- 全量回归：`PYTHONPATH=src GALNX_BUILD_ROOT=E:/galnx-build python -m pytest -q` → **747 passed, 63 subtests passed**（47 文件，76.35 s，exit 0）。
- sanitizer 实跑（fail-closed）：kept=1018 excluded=359 bytes=26606932 rewritten_refs=0；`scan: block=0 review=469 scanned=1018`；ZIP 9142838 B sha256 `17688031…`；退出码 0。
- 发布：`public_release_publish.py` → committed=True、source `cc6148c`、public head `071e2c9`；mirror `26dedca..071e2c9` 推送成功。
- 干净 clone 闭环：`git clone --depth 1 https://github.com/KIRARITenshiChan/GalNX-public.git` → HEAD `071e2c9`；`python -m galnx build run --manifest examples/quickstart/manifest.yaml --yes` 首跑 RC=0（1 executed / 1 cache miss）、二跑 RC=0（1 cache hit）；artifact 269 B sha256 `5982bb06…`，magic `GALNXPK1`，count=2 条目 `demo.txt` 92 B、`sub/extra.txt` 60 B。

## 6. 复现命令

```bash
cd 'E:/Othergames/Nintendo Switch/Workspace/GalNX'
python scripts/public_release_sanitize.py --repo . --out E:/galnx-build/public/GalNX-v145-final \
  --zip E:/galnx-build/public/GalNX-v145-final.zip --force > E:/galnx-build/fix06-final-sanitize.log 2>&1
python scripts/public_release_publish.py --repo . --mirror E:/galnx-build/public/GalNX-public
git -C E:/galnx-build/public/GalNX-public push origin main   # 经 cred_use 注入 token 与代理
```

## 7. 证据（可复核）

- sanitizer 日志：`E:/galnx-build/fix06-final-sanitize.log`（kept/excluded/bytes/scan/zip 行）。
- 公开树说明：`E:/galnx-build/public/GalNX-v145-final/PUBLIC_RELEASE.md`（源 commit cc6148c、生成时间 2026-11-11T08:53:12Z、home 路径脱敏 532 处 / 188 文件、排除前缀附表）。
- 干净 clone 构建日志：`E:/galnx-build/fix06-quick1.log`、`E:/galnx-build/fix06-quick2.log`。
- 远端一致性：public head `071e2c956b2184adc63e7d3da44cc6aadeb77d43`、tree `b7a26ed73dbca8e63db08380ba4be883e276abd6`、6 个快照 commit、`git ls-files` 1,018 文件 / 26,630,480 B。

## 8. 偏差（Deviation）

1. **REVIEW 不逐条清零**：469 条 REVIEW（dev machine absolute path 439、sensitive path keyword 30）来自历史文档里的构建路径；导出时已对 `C:\Users\<user>` 做确定性脱敏（532 处 / 188 文件），剩余 classify 为 review 而非 block。结论写进 `public-release.md` §2.6，未在发布前逐条改写历史审计文档。
2. **ZIP 扫描合并进 sanitizer 单次运行**：没有单独再跑一次「解包 ZIP 再扫」的脚本；`scan_zip` 与树扫描在同一 fail-closed 进程内完成，`block=0` 为二者之和（该行为由 `tests/test_public_release.py` 覆盖）。
3. **FIX-02 数字笔误在 FIX-06 内连带修正**：tasks/FIX-02.md 三处、README 一处、expert-review §12 表格一处，均为 283→269 B 系列；不算 FIX-02 行为变更，只改记录。
4. **公开仓库只追加**：`071e2c9` 为第 6 个快照 commit；按决策 56 不 rebase、不 force-push、不同步私有历史。

## 9. 未验证假设

1. 假设 REVIEW 的 469 条均为「构建路径/敏感词字样」类文本命中，人工未逐条阅读全部 469 条，只按类别计数与抽样（PUBLIC_RELEASE.md 前 10 条）。
2. 假设 GitHub 侧渲染/附件不影响文本扫描结论（未下载 release 附件复扫，因为 0.1.0 尚未创建 GitHub Release）。
3. 干净 clone 验收只覆盖 `examples/quickstart`（框架链路），未覆盖真实引擎构建（devkitPro/Rust 工具链不在公开验收范围）。

## 10. 已知限制

1. REVIEW 队列会在后续快照里随文档历史增长，当前流程靠「发布前记录数量 + 分类」而非清零。
2. 公开树不包含游戏素材与证据截图（359 文件被排除），因此公开仓库无法复现真机截图类证据，只能引用私有仓库路径与哈希。
3. ZIP 是导出物而不是 GitHub Release 资产；如需附件发布还需单独上传并复扫（未做）。

## 11. 回滚

- 文档侧：`git revert` 本次 docs 提交即可（不涉及代码/产物）。
- 公开侧：按决策 56 不 force-push；若快照有误，只能从修正后的私有 commit 再发布第 7 个快照并在 `public-release.md` §4.5 标注前一快照作废原因。
