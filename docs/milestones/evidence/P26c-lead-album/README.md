# P26c — Lead 独立 Citron 验收：Album 4K 差分切换（v1.1.2-test）

- 时间：2026-11-06 05:23–05:26
- 运行目录：`E:/galnx-build/p26/run-lead-album/20261106-052325-rfvp/`
- 被测：`E:/galnx-build/p26/out/IROSEKA_FHD-010047420000a000-v1.1.2-test.nsp`
  9,979,500,248 B，sha256 `0cbac98ef8c292b69d64eef87d6340fee9477c8f007ee8b38e4d5cfb229789b8`
- 目的：独立复跑 async-fix 的 Album 差分路线，确认 P26（SD 读吞吐 + 4K 缓存/链式预取）在 Citron 上**功能无回归、async 不冻结、差分可连续切换**。

## 路线

`wait 18s → 标题 → Album(1390,694) → CG MODE(1390,281) → 首个已解锁 4K CG(540,270) → 10× (key:C + 5 s 间隔) → 左键放大 → 恢复`

脚本：`E:/galnx-build/p26/run-lead-album-p26.sh`（citron_run.sh --no-stage --timeout 900 --settle 12 --allow-existing --expect-title IROSEKA）。

## 结果

| 项 | 结果 |
| --- | --- |
| 步数 | 44 步，0 failed，diff_ratio 0.811863 |
| 差分循环 | 截图字节循环 1,775,991 / 1,768,489 / 1,775,048 / 1,515,877（3 个差分源往复），无冻结、无黑帧 |
| 放大 | 左键后截图 1,806,012 B（放大/还原功能正常） |
| async | `async_status.txt` = `enabled=1 hb=170000 stage=0 cpu=1 wdt=1 main=11174 stalled=0` |
| 帧心跳 | `frame_status.txt` = `frame=11205 status=0 async=1` |
| 异常 | 无 `last_error.txt`、无 `watchdog_status.txt` |
| 回归 | 标题 / 正文 / 菜单显示正常 |

## 局限

本轮未做 ring 缓冲快照轮询，sdmc `debug_report.txt`（102,254 B）中 `texture put` / `reads=` / `decoded texture` 计数为 0，只有 1 条 `graph cache hit path="graph_vis/SHINKU_e01c"`。缓存命中与 reads 数字以 `E:/galnx-build/p26/evidence/probe6/` 的 ring 证据与真机日志为准；本轮结论限于功能/稳定性。

## 文件

| 文件 | 说明 |
| --- | --- |
| 01-b0-cg1.png | 进入 Album 后首个 4K CG |
| 02-b1-next.png / 03-b2-next.png / 04-b3-next.png | 连续 3 次差分（3 个源循环） |
| 05-b11-leftclick-zoom.png | 左键放大 |
| result.json / run.log / input-steps.tsv | citron_run.sh 运行产物 |
| async_status.txt / frame_status.txt / perf_slow.log / debug_report.txt | 运行结束时设备侧日志快照（sdmc） |
| SHA256SUMS.txt | 全部文件哈希 |

真机验收清单与回退见 `docs/builds/033-rfvp-sd-read.md` §6/§7。
