# P26a：真机 CG 差分切换卡顿证据（IROSEKA v1.1.1-test）

- 设备：Nintendo Switch（真实硬件）
- 构建：`IROSEKA_FHD-010047420000a000-v1.1.1-test.nsp`（9,979,496,152 B，sha256 `bf83fa6edb0134c60c04756b6c02c21b191b43e3567561e68628962b4ded2e5b`）
- 状态：async=on（`sdmc:/switch/rfvp/async.txt` = "on"），debug 心跳开启
- 取回时间：2026-11-06 04:28（主机 MTP，脚本 `E:/galnx-build/p26/fetch-all.ps1`）
- 用户反馈（m27413）：CG 完整、UI 残留已消失；但 Album 内差分切换仍明显卡顿，有时 >1s。

## 文件
| 文件 | 说明 |
| --- | --- |
| `perf_slow.log` | 设备慢帧日志（2394 行；p50 32.8 ms，98 帧 ≥1000 ms，146 帧 vfs_read ≥300 ms） |
| `debug_report.txt` | 设备诊断报告（含 vfs / graph decode / cache 行；113,652 B） |
| `async_status.txt` | `enabled=1 create=0x0 start=0x0 hb=290000 stage=0 cpu=1 wdt=1 main=15223 stalled=1` |
| `frame_status.txt` | `frame=15225 status=0 async=1` |
| `watchdog_status.txt` | `frame=4133 stalled_ms=3000 stage=0 hb=85083 enabled=1 cpu=1`（记录过一次 3 s 主线程停顿） |
| `SHA256SUMS.txt` | 上述文件校验和 |

## 关键行（原样）
```
frame 14402 slow 1569.8 ms | vm 1443.93 ... stages(ms): ... vfs_read 1097.76 graph_decode 325.35 | host(ms): ... upload 55.84/1 ... draws 4
frame 14617 slow 1570.8 ms | vm 1449.06 ... stages(ms): ... vfs_read 1102.67 graph_decode 326.17 | host(ms): ... upload 53.10/1 ... draws 2

[diag] vfs path="graph_vis2/MIO_e01c" bytes=8001842 us=1097751
[diag] graph decoded path="graph_vis2/MIO_e01c" 3840x2160 us=325330
[diag] vfs path="graph_vis2/MIO_e01b" bytes=8038985 us=1102667
[diag] graph decoded path="graph_vis2/MIO_e01b" 3840x2160 us=326163
```

## 结论
差分切换单次 ≈1.57 s = SD pack 读取 ≈1.10 s（8 MB，约 7.3 MB/s）+ 4K 差分解码 ≈0.33 s + 纹理上传 ≈55 ms。
根因见 `docs/experiments/perf-03-device-diff-stutter.md`（SD 读放大：4 KiB read_to_end × newlib 1 KiB 缓冲 ⇒ ≈8192 次小读；且 graph_vis* 无差分预取）。
