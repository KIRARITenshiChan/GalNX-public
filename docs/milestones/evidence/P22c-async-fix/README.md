# P22c async v1.1.0-test Citron 验证证据

IROSEKA FHD v1.1.0-test NSP（async 并发修复）在 Citron 上的主证据集，取自
`E:/galnx-build/p22/evidence-clean/`（run-nsp-clean，73/73 步、320 s / 19,200 帧、async=on）。

## 关键判据

- `async_status.txt`：终值 `enabled=1 hb=295384 main=19199 stage=0 cpu=1 wdt=1 stalled=0`
  —— worker 已换核（cpu=1）、独立看门狗在跑（wdt=1）、无停顿标记（stalled=0）。
- 无 `watchdog_status.txt`、无 `last_error.txt`：看门狗未触发，未发生崩溃。
- `debug_report.txt`：含 8 次 `async decode applied`，帧率 60.0 fps（slowest 19.6 ms）。
- `perf_slow.log`：慢帧均为一次性（启动/切场景），未出现 v1.0.8 式整进程冻结。
- 截图：标题 / 选择列表 / 正文 / 三次分钟级检查点 / 最终一帧。

## 文件

| 文件 | 说明 |
| --- | --- |
| async_status.txt | async 运行时状态（终值） |
| debug_report.txt | 帧率、阶段耗时、async 应用记录 |
| perf_slow.log | 慢帧明细 |
| result.json / input-steps.tsv | Citron harness 结果与注入步骤 |
| step-*.png | 关键时刻截图 |
| harness.err | harness stderr（4.8 KB） |

## 注意

本目录只证明 **Citron 级**不冻结。真机确认步骤见
`docs/pilot/P4-device-runbook.md` §13.5；真机通过前不推送修复。

SHA256 清单见 `SHA256SUMS.txt`。
