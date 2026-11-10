# P33a — v1.1.9-test 自包含 NSP OP 分档（480p）+ 原生尺寸路径冒烟（Lead 独立）

2026-11-07。目的：在 Citron 上验证 **romfs 内嵌 4 档 OP 变体** + `video.txt` 选档生效、**原生尺寸**解码路径（不再软件上采样到 1920×1080）、以及音轨在降档 OP 上仍正常。

## 环境与对象

- Citron Nightly `0237a9b88`；NSP `E:/galnx-build/p33/out2/IROSEKA_FHD-010047420000a000.nsp` 9,977,492,184 B sha256 `bd909c1eb1e6e3f9339a28b662943d0d06f74873b2dd36639824df54a90b535b`（v1.1.9-test；romfs 9,930,029,496 B / 165 项 = 01.wmv 720p + 01_q540/01_q480/01_q360 + 01.ogg）。
- 为了让 NSP 用内嵌 romfs：脚本把 sdmc `rfvp/game` 临时改名为 `game-sakura-hold`（trap 恢复）；`async.txt=on`；`debug.txt` 含 `shot=900` 与 `movie=1`；`video.txt` 内容 `480`（选 854×480 档）。
- 运行器：`scripts/citron_run.sh`（detach 模式）经 `E:/galnx-build/p33/run-lead-119.sh` 驱动；run dir `E:/galnx-build/p33/run-lead-119/20261107-232940-IROSEKA_FHD-010047420000a000`。

## 结果（PASS）

- 窗口标题 `citron Nightly | 0237a9b88 | IROSEKA FHD (64-bit) | 1.1.9-test | NVIDIA`；boot 行 `Booting game: 010047420000A000`。
- 36/36 步 0 failed；`steps_diff_ratio=0.820757`；18 张截图 n01–n18（n01–n09 内容逐帧变化，n10 之后为 OP 结束后的静止标题帧）。
- 选档生效：`Movie: opened (Switch WMV video-only, streaming, P33 quality) name=movie/01_q480.wmv level=2 bytes=38610038`（480p 变体 38,610,038 B）；未回退原片。
- 原生尺寸：`movie: decoded frame=1 pts=0 ms 854x480 decode_us=15134 convert_us=5764`（此前 720p 源会软件上采样到 1920×1080 再上传）；`presented frame=1 854x480 upload_us=410`。
- 播放到片尾：最后 `decoded/presented frame=2880 pts=119958 ms 854x480`（480p 变体全长 120 s），随后 `movie audio: stopped movie/01.ogg`；OP 结束后画面停在标题（n18 与 n12/n14/n16/n17 哈希相同 `34904f92…`，确认为静止标题帧而非卡死）。
- 音轨：`movie audio: loaded movie/01.ogg (Ogg Vorbis, 2343033 bytes)` → `playing` → 片尾 `stopped`；`audio_status.txt` = `mode=jit driver=1 thread=1 alive=1 cpu=2 pages=10376 rendered_ms=221354 uptime_ms=221246 lag_ms=-108 underrun=0 max_refill_gap_ms=56 stalls=0 stall_ms=0`；`audio_stall.txt` 空。
- 帧循环：`frame_status.txt` = `frame=13425 status=0 async=1`；`perf avg over 60 ticks: vm 0.17 ms, scene 0.02 ms, render 16.30 ms, total 16.49 ms`（Citron 60 fps）；`async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=206000 stage=0 cpu=1 wdt=1 main=13397 stalled=0`；无 `last_error`。
- 噪声：`[ERROR] id must be in range 0..256` ×1（紧随 Movie 音轨 `audio source id=8192`，P32 起既有，未影响播放）。

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `result.json` | citron_run.sh 结果（status=loaded、expected_title=IROSEKA） |
| `input-steps.tsv` | 36 步输入/等待/截图流水 |
| `async_status.txt` / `audio_status.txt` / `audio_stall.txt` / `frame_status.txt` | 运行末状态快照 |
| `debug-report-movie-excerpt.txt` | `debug_report.txt` 中 Movie/movie/audio/decoded/presented/perf/WARN/ERROR 相关 231 行 |
| `n01-staff.png` `n03-op-scene.png` | OP 前段截图（staff/画面，2 张） |
| `n18-title-after-op.png` | OP 结束后的标题帧（与最终画面一致） |
| `SHA256SUMS` | 上述文件哈希 |

完整 18 张截图、原始 `debug_report.txt`（93,148 B）与 `citron_log.txt` 留在 run dir（不入库）。同一构建的 720p 变体（`video.txt=720`）与 NRO 形态回归未在本轮重跑：720p 路径与 P31/P32 相同（只走原片），P33 差异仅在「按原生尺寸转换 + 复用自己的 RGBA buffer」。
