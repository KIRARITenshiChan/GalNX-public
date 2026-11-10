# P30a — v1.1.6-test 音频 JIT 独立 Citron 验收证据

- 日期：2026-11-07
- 包：`E:/galnx-build/p30/out/IROSEKA_FHD-010047420000a000-v1.1.6-test.nsp`（9,979,505,368 B，sha256 `d7eb77ecf8bcba1f131ccaa5e26136a913e080203ccf096eca51e3e995e14461`）
- 目标：验证 P30 音频 JIT 改造（见 `docs/builds/037-rfvp-audio-jit.md`）在注入 3×1.2 s 主线程停顿期间仍保持音频连续、且 `lag_ms` 不再出现 P27 ring 路径的 ~+3000 ms。
- 环境：Citron nightly 0237a9b88，NSP 走内嵌 romfs；`sdmc:/switch/rfvp/async.txt`=`on`；`debug.txt`=`shot=900 / stall=1200 / stall_at=3800`。
- run_dir：`E:/galnx-build/p30/run-lead-audio-jit/20261107-034903-IROSEKA_FHD-010047420000a000-v1.1.6-test`
- 结果：35/35 步 ok、0 failed、diff_ratio 0.812134、60 FPS、无异常。

## 关键状态

`audio_status.txt`

```
mode=jit driver=1 thread=1 alive=1 cpu=2 pages=5879 rendered_ms=125418 uptime_ms=125317 lag_ms=-101 underrun=0 max_refill_gap_ms=44 stalls=3 stall_ms=1200
```

`audio_stall.txt`（三次注入停顿的 pre/post）

| # | pre rendered_ms | post rendered_ms | Δ | post lag_ms | underrun | gap_ms |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 64,874 | 66,069 | +1,195 ms | −87 | 0 | 44 |
| 1 | 76,032 | 77,226 | +1,194 ms | −95 | 0 | 44 |
| 2 | 87,210 | 88,405 | +1,195 ms | −91 | 0 | 44 |

`async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=120000 stage=0 cpu=1 wdt=1 main=7488 stalled=0`
`frame_status.txt` = `frame=7500 status=0 async=1`
无 `last_error`。

## 文件

| 文件 | 说明 |
| --- | --- |
| result.json / run.log / input-steps.tsv / lead-audio-jit-smoke.log | harness 输出与脚本日志 |
| citron_log_slice.txt | Citron 日志切片 |
| step-02-t0-title.png | 标题（1.1.6-test） |
| step-05-t1-loadlist.png | 读档列表 |
| step-08-t2-story.png | 正文（「映入眼瞳的是一位半透明的女孩。二阶堂真红。」） |
| step-33-t3-story-late.png | 后续场景 |
| step-35-t4-end.png | 结束态 |
| window-steps-final.png | 窗口终态 |
| audio_status.txt / audio_stall.txt / async_status.txt / frame_status.txt | 运行时状态文件（运行后从 sdmc 取回） |
| SHA256SUMS.txt | 本目录哈希清单 |

## 复现

```bash
bash /e/galnx-build/p30/run-lead-audio-jit.sh
```

判定：`mode=jit`、`lag_ms` 在 ±300 内、`underrun=0`；每次 1.2 s 停顿期间 `rendered_ms` 推进约 1200 ms。对照组为 P27 ring 版本（`lag_ms` ≈ +3000）。
