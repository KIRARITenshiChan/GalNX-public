# P19c：真机日志取证（v1.0.6 黑屏）

来源：真机 SD 卡 `/switch/rfvp/`（DBI FTP，192.168.31.254:5000），2026-11-01 21:2x 拉取。

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `debug_report-v106.txt` | 114,823 B | 每 60 帧覆盖写；头行 `frame 9600: 59.9 fps ...`，含 1,938×`Invalid id`、462×`graph_load: invalid id : Nil` |
| `perf_slow-v106.log` | 111,565 B | 380 行，含 5 次 `frame 1`（多次启动 append），最大 `frame 1 slow 4191.7 ms` |

结论与限制：

1. `debug_report` 的最后一帧是 9600 帧、全程 60 fps 的会话 → **不是黑屏那次**；黑屏若发生在首帧 60 帧内就不会刷新该文件，故这份 report 是上一次正常会话的残留。
2. 真机 `/atmosphere/crash_reports/` 下只有两条报告，均与 rfvp 无关：`010000000000100f`（LibAppletOf，User Break）、`01009bc00c38a000`（hbloader，Data Abort）。
   **rfvp（010047420000A000）没有崩溃报告**，且 `/switch/rfvp/last_error.txt` 不存在（panic handler 未触发）→ 黑屏更可能是挂起/渲染空白，而非崩溃。
3. `[async]` 诊断行走 host.log→ODS（仅 nxlink 可见），不进 ring_log，因此 report 里 0 条 async 行不能证明 async 未运行。
4. 由此 v1.0.6 黑屏根因仍**未确证**；v1.0.7 采用「async 运行时开关、默认关」作为安全回退，并用 A/B 方式定位（`sdmc:/switch/rfvp/async.txt` 写 `on`）。
