# P27a — v1.1.3-test 音频连续性：Lead 独立 Citron 验收

- 日期：2026-11-07
- 目的：独立验证 P27（3.07 s SPSC ring + 独立音频线程）在 **NSP 形态、async=on、人为 1.2 s 长帧** 下音频不断流（underrun=0），并确认无 async/看门狗回归。
- 运行：`E:/galnx-build/p27/run-lead-audio/20261107-013414-IROSEKA_FHD-010047420000a000-v1.1.3-test`
- 游戏：`E:/galnx-build/p27/out/IROSEKA_FHD-010047420000a000-v1.1.3-test.nsp`（9,979,503,320 B，sha256 `eaea4446ac9b373b60a3b9c6f083b1567b931f1a38ee6ab8dd49b1ae62ca13a8`），NSP 内嵌 romfs（sdmc game 目录运行时改名 game-sakura-hold，结束后恢复）。
- 注入：`debug.txt` = `shot=600 / stall=1200 / stall_at=1800`；`async.txt` = `on`。
- 输入路线：标题 18 s → Continue (1386,638) → 读档列表 6 s → DATA_001 (420,300) → 正文 22 s → 再等 36 s（覆盖第 1800/2400/3000 帧三次人为 1.2 s 停顿）。14/14 步 ok，diff_ratio 0.812221，60 FPS。

## 结果（PASS）

`audio_status.txt`：
```
driver=1 thread=1 alive=1 cpu=2 cap=147456 ring=147456 min_water=91136 underrun=0 max_underrun_ms=0 starve_ms=0 produced=5186560 consumed=5039104 stalls=3 stall_ms=1200
```

`audio_stall.txt`（三对 pre/post，间隔 1.2015–1.2017 s）：
```
pre  stall=0 ring=147456 underrun=0 min_water=5120   t_us=...
post stall=1 ring=90112  underrun=0 min_water=90112
pre  stall=1 ring=147456 underrun=0 min_water=90112
post stall=2 ring=90112  underrun=0 min_water=90112
pre  stall=2 ring=147456 underrun=0 min_water=90112
post stall=3 ring=91136  underrun=0 min_water=91136
```

- 三次 1.2 s 主线程停顿期间 **underrun=0、max_underrun_ms=0**，ring 最低水位 90112 帧（≈1.88 s），与「3.07 s ring 吸收 1.2 s 停顿」的理论一致。
- 音频线程确实运行：`thread=1 alive=1 cpu=2`；boot 日志应含 `rfvp: audio thread cpu=2 ring=147456 frames prio=0x2d`（见 run.log / citron_log 切片）。
- async 回归：`async_status enabled=1 hb=104000 stage=0 cpu=1 wdt=1 main=6508 stalled=0`；`frame_status frame=6510 status=0 async=1`；无 `watchdog_status.txt`、无 `last_error.txt`。
- 画面：标题 / 读档列表 / 正文（同一句停留，a2=a3=a4=a5 字节相同）均正常渲染，无黑屏/残留。

## 文件

- 截图：`step-02-a0-title.png`、`step-05-a1-list.png`、`step-08-a2-story.png`、`step-14-a5.png`、`window-steps-final.png`
- 运行：`result.json`、`run.log`、`input-steps.tsv`
- 状态：`audio_status.txt`、`audio_stall.txt`、`async_status.txt`、`frame_status.txt`
- 附带日志：`logs/debug_report.txt`、`logs/perf_slow.log`（Citron 宿主侧，仅供上下文）

## 限制

- 听感未验证（Citron 无音频输出）；underrun/min_water 是设备侧 audren 路径的客观指标，真机需用户听感确认（尤其 Album 4K 差分切换、大 vfs 读、场景切换）。
- 1.2 s 是人为停顿上限（代码 `AudioStallMaxMs=2000`）；真机长于 3.07 s 的极端停顿仍会 underrun，可记录 `max_underrun_ms` 评估加大 ring。

## 仓库内证据裁剪

仓库内仅保留 1 张代表性截图（正文+主线程停顿注入时刻）；完整 5 张与原始 run 目录在 `E:/galnx-build/p27/run-lead-audio/20261107-013414-IROSEKA_FHD-010047420000a000-v1.1.3-test`。
完整原始集合：`E:/galnx-build/p27/run-lead-audio/20261107-013414-IROSEKA_FHD-010047420000a000-v1.1.3-test`。SHA256SUMS 仅覆盖本目录保留文件。
