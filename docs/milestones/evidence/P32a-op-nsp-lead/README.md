# P32a — v1.1.7-test 自包含 NSP OP 冒烟（Lead 独立）

2026-11-07。目的：在 Citron 上验证 **romfs 内嵌** 的 IROSEKA OP 影片（720p30 WMV 软解 + OGG 音轨）能真实播放、音轨与主线程 JIT 音频协同、且无回归。

## 环境与对象

- Citron Nightly `0237a9b88`；NSP `E:/galnx-build/p31/out/IROSEKA_FHD-010047420000a000.nsp` 9,861,393,624 B sha256 `cb019f27136b5b80936c5c5067477c6a08e19ae02a6535f48e9f12785ba16c7d`（v1.1.7-test，romfs 162 项 9,814,160,982 B）。
- 为了让 NSP 用内嵌 romfs：脚本把 sdmc `rfvp/game` 临时改名为 `game-sakura-hold`（trap 恢复）；`async.txt=on`；`debug.txt` 含 `shot=900` 与 `movie=1`（强制播放 `movie/01.wmv`）。
- 运行器：`scripts/citron_run.sh`（detach 模式）经 `E:/galnx-build/p32/run-lead-op.sh` 驱动；job `bash-dcd6a54213bd45ba` exit 0；run dir `E:/galnx-build/p32/run-lead-op/20261107-165307-IROSEKA_FHD-010047420000a000`。

## 结果（PASS）

- 窗口标题 `citron Nightly | 0237a9b88 | IROSEKA FHD (64-bit) | 1.1.7-test | NVIDIA`；boot 行 `Booting game: 010047420000A000`。
- 36/36 步 0 failed；`steps_diff_ratio=0.822764`；18 张截图 sha256 互不相同、相邻 mad 42.93–81.22 → 连续视频运动。
- 画面：n01 = staff 字幕「脚本 漆原雪人」；n05 = 「SDキャラ CHAN×CO」；n12/n17 = OP 动画场景（校园走廊、角色 CG）。
- 日志：`Movie: opened`（`movie/01.wmv bytes=124386038`）、`movie audio: loaded` / `playing`（`movie/01.ogg`，2,343,033 B）各 1；`decoded`=109 / `presented`=109、frame 1..3240、最后 `pts=108075 ms`。
- `audio_status`：`mode=jit driver=1 thread=1 alive=1 cpu=2 pages=9405 rendered_ms=200640 uptime_ms=200538 lag_ms=-102 underrun=0 max_refill_gap_ms=44 stalls=0`。
- `async_status`：`enabled=1 create=0x0 start=0x0 hb=197000 stage=0 cpu=1 wdt=1 main=3233 stalled=0`；`frame_status frame=3240 status=0 async=1`；无 `last_error`。
- 噪声：`[ERROR] id must be in range 0..256` ×1（紧随 Movie 音轨 `audio source id=8192`，未影响播放）；`[WARN] float_to_int: Invalid value type` ×2（既有）。

## 文件清单

| 文件 | 说明 |
| --- | --- |
| `result.json` | citron_run.sh 结果（status=loaded、expected_title 匹配、nonblack 0.9018） |
| `input-steps.tsv` | 36 步输入/等待/截图流水 |
| `async_status.txt` / `audio_status.txt` / `frame_status.txt` | 运行末状态快照 |
| `debug-report-movie-excerpt.txt` | `debug_report.txt` 中 movie/音频/ERROR/WARN 相关 224 行 |
| `n01-staff-script.png` `n05-sd-chara.png` `n12-op-scene.png` `n17-op-scene.png` | 4 张代表截图（OP staff 字、SD 角色、OP 动画场景×2） |
| `SHA256SUMS` | 上述文件哈希 |

完整 18 张截图、原始 `debug_report.txt`（90,980 B）与 `citron_log.txt` 留在 run dir（不入库）。同一构建的 NRO 形态冒烟见 `E:/galnx-build/p32/evidence/probe-movie-v2/`（22 步、decoded/presented 各 37、frame=1..1080、`lag_ms=-113 underrun=0`）。
