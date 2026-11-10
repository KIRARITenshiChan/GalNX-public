# 052 · P45：把 NV12 零拷贝引擎同步到 IROSEKA FHD 与 さくら、もゆ。（+ 用户封面图标）

- 日期：2026-11-11
- 相关：`docs/builds/051-rfvp-nv12-zerocopy.md`、`docs/builds/patches/rfvp-switch/rfvp-nv12-zerocopy.patch`、`examples/pilot02-iroseka.yaml`、`examples/pilot03-sakura-cn.yaml`、`docs/milestones/evidence/P45-fvp-sync/`、计划 v1.43（决策 58）
- 状态：模拟器（Citron）首启 PASS + NSP verify PASS；真机由用户安装 v1.2.5-test / v1.3.3-test 验收

## 1. 背景与目标

P44（`docs/builds/051`）在 AKASEKA HD 上把电影路径改成「SDL NV12 双平面纹理 + GPU 做 YUV→RGB」，1080p 下 CPU 转换 7.3→1.8 ms、上传 8.29→3.11 MB（6.75→2.72 ms），单帧省约 9.5 ms；真机验收 PASS（用户 m40951：「真机测试颜色正确，播放相当流畅」）。

同一轮用户要求：**把这项优化同步到 IROSEKA FHD 与 さくら、もゆ。，并把先前那两张自制封面套上去，最后同步到公开仓库**（AKASEKA 保持默认封面）。本文件记录这两个包的 P45 重建。

## 2. 输入与工具链（与 P44 完全一致）

| 项目 | 值 |
| --- | --- |
| 引擎 ELF（NV12 零拷贝版） | `E:/galnx-build/p40/rfvp/target/rfvp-switch-runtime/rfvp.elf` 20,418,056 B sha256 `296b198c6b1dc970ed6544cac40c0c4da97bf581dda031c0a8acb4cc0a073973` |
| 打包器 | `scripts/build_nsp_game.sh`（--romfs-mode hardlink） |
| hacBrewPack | `/e/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c/hacbrewpack.exe` |
| keyset（只读，不入库） | `E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys` 12,007 B sha256 `7bb3b6d2a2eedc83c9f244ee2ed2eaa4d59eb9ad95b66df575f7dfffa71a2a40` |
| 构建脚本 | `/e/galnx-build/p46/build-iroseka.sh`、`build-moyu.sh`、`build-both.sh`；产物 `/e/galnx-build/p46/out` |

游戏树沿用既有打包根（内容未变，仅换引擎与图标）：IROSEKA `/e/galnx-build/p31/game`（9.4 GB，含 720p H.264 `movie/01_h264.mp4` 108,361,267 B + `01.ogg`），さくら、もゆ。`/e/galnx-build/p23/cn-game`（7.6 GB，含 `movie/01_h264.mp4` 56,397,760 B 与 `movie/02_h264.mp4` 49,083,815 B + 各自 `01.ogg`/`02.ogg`）。

## 3. 图标：用户自制封面

原来两个包里的图标是 P40/P41 时期的旧图标（生成于 11-10 05:xx），用户封面 16:42 才生成，所以必须重打包才能换图标。本次直接用 `examples/pilot02/icon-256.jpg`（26,706 B）与 `examples/pilot03/icon-256.jpg`（25,886 B），由 `build_nsp_game.sh --icon` 写入 control NCA。

打包后的 control 内容（构建日志 `===INPUTS` 段，可复核）：

| 包 | icon_AmericanEnglish.dat | sha256 |
| --- | --- | --- |
| IROSEKA FHD | 26,706 B | `f35ac15670f52122f67b1e50d184e5171cf4839c0e7090ca2d8a3e35d51dc4f5`（= 用户封面原文件，逐字节相同） |
| SAKURA MOYU CN | 25,886 B | `12ea3a073db6db6fcf50a991caa289611a92c0d6a6d2e847408608c3c13a9443`（= 用户封面原文件，逐字节相同） |

AKASEKA HD 不改：沿用 P44 的 OP 抽帧图标（`examples/pilot04/icon-256.jpg` 15,158 B sha256 `707fb9f3…`）。

## 4. 产物

| 包 | 版本 | 体积 | sha256 | romfs |
| --- | --- | --- | --- | --- |
| IROSEKA FHD | 1.2.5-test | 10,087,541,464 B | `f686084205890638fda6bee97a5359774f5a8306beec9d161dc3f39093e815e8` | 10,038,390,763 B / 166 文件 |
| SAKURA MOYU CN | 1.3.3-test | 8,116,841,176 B | `965ee35682df72969465f321c3699ba377a545774745d57234983a14472f2b5f` | 8,094,409,871 B / 81 文件 |

路径：`E:/galnx-build/p46/out/IROSEKA_FHD-010047420000a000.nsp`、`E:/galnx-build/p46/out/SAKURA_MOYU_CN-010047420000c200.nsp`。
TitleID 与旧包一致（IROSEKA `010047420000A000`、MOYU `010047420000C200`），因此真机安装会覆盖升级、存档仍指向同一 title。两个包的 `exefs/main` 都是 6,385,492 B sha256 `536531738648db31fc466a1913a2d4607081b79cc302c9ff2a904eb25623ba11`（同一 ELF 编出的 NSO），`main.npdm` 因 TitleID 不同而不同。

hacBrewPack 耗时：IROSEKA 706 s、MOYU 575 s。STEP 6/6 的 `nstool exit=1` 仍是 harness 传参混用路径分隔符（`Path literal has both forward and backward path separators`），不是 NSP 损坏——独立 verify 与 Citron 加载都通过。

## 5. 校验与冒烟

### 5.1 `galnx package nsp verify`

| 包 | ok | 检查 | 说明 |
| --- | --- | --- | --- |
| IROSEKA | true | 13 checks / 0 fail / 1 warn | warn = NCA signature FAIL（未签名 homebrew 预期）；3 个 NCA ProgID 全为 `0x010047420000A000` |
| MOYU | true | 12+1 checks / 0 fail / 1 warn | 同上；ProgID 全为 `0x010047420000C200` |

结果文件：`docs/milestones/evidence/P45-fvp-sync/verify-iroseka.json`、`verify-moyu.json`（原始 `/e/galnx-build/p46/verify-*.json`）。

### 5.2 Citron 首启（NSP 形态，清掉全部调试 marker）

先删除 `sdmc:/switch/rfvp/{h264_sw.txt,movie_debug.txt,nv12_off.txt,video.txt}`，再用 `scripts/citron_run.sh --game <nsp> --no-stage --detach` 启动，等 `--wait-job` 收尾。

| 包 | 窗口标题 | boot 行 | 结果 |
| --- | --- | --- | --- |
| IROSEKA | `citron Nightly | 0237a9b88 | IROSEKA FHD (64-bit) | 1.2.5-test | NVIDIA` | `Booting game: 010047420000A000 | IROSEKA FHD (64-bit) | 1.2.5-test` | status=loaded，标题画面中文（五彩斑斓的世界 HD Re:GENERATION + New Game/Continue/Album/Option/Exit），59 FPS |
| MOYU | `citron Nightly | 0237a9b88 | SAKURA MOYU CN (64-bit) | 1.3.3-test | NVIDIA` | `Booting game: 010047420000C200 | SAKURA MOYU CN (64-bit) | 1.3.3-test` | status=loaded，标题画面中文（樱花、萌放。+ NEW GAME/CONTINUE/ALBUM/OPTION/EXIT），60 FPS |

截图：`docs/milestones/evidence/P45-fvp-sync/iroseka-title.png`（sha256 `7b884b86…`）、`moyu-title.png`（sha256 `6ac950e5…`）。

本轮没有重复播放 OP：两个游戏的 video 资源与 P40/P41 时逐字节相同，P44 已在同一 ELF 上验证过 NV12 电影路径（Citron `upload=nv12` + 1080p A/B），真机 OP 观感由用户这次一并验收。

## 6. 与旧包的关系

| 包 | 旧（P40/P41） | 新（P45） | 差异 |
| --- | --- | --- | --- |
| IROSEKA | 10,087,536,344 B `5bc45ace…`（v1.2.4-test） | 10,087,541,464 B `f6860842…`（v1.2.5-test） | 引擎换 NV12 零拷贝（ELF 差 5,120 B 量级）、图标换用户封面、版本号 |
| MOYU | 8,116,836,056 B `8df0d398…`（v1.3.2-test） | 8,116,841,176 B `965ee356…`（v1.3.3-test） | 同上 |

体积基本不变（romfs 文件集一致，仅 exefs/main 与 icon 变化），说明没有额外的运行时依赖被塞进包。

## 7. 限制与待验

- 真机：本次只做 Citron 首启；NVDEC 硬解 + NV12 直传只在 AKASEKA 上做过真机验收，IROSEKA/MOYU 的 OP 与 1080p/720p 行为需要用户在真机确认。
- `sdmc:/switch/rfvp/nv12_off.txt` 仍是回退开关（存在即走 CPU RGBA 路径）；`h264_sw.txt` 只用于无 NVDEC 的模拟器，真机不得放置。
- MOYU 的两段 OP（01/02）与 IROSEKA 的单段 OP 都走同一 `horizon_h264.rs` 管线，无需额外接线；但若某游戏未来的 movie 分辨率不是 16 对齐，NV12 紧密 pitch 的兼容性需要重新测（`uv_pitch = ((w+1)/2)*2`）。
