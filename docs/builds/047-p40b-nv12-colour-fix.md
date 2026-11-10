# 047 · P40b：修正 NV12 色度步进（真机 OP 颜色异常）

- 日期：2026-11-09
- 相关：`docs/builds/046-op-h264-nvtegra.md`、`docs/builds/patches/rfvp-switch/P40b-nv12-color.diff`、`docs/milestones/evidence/P41-op-nv12-color/`
- 状态：Citron 影子验证 PASS；v1.2.1-test 已构建并 verify；真机验收待用户

## 1. 症状

v1.2.0-test（P40）在真机上 OP 不慢放，但颜色明显错误。用户 m36342 的原话：

> op确实没慢放，但是颜色有问题。看起来像是一个正常的黑白图层在底下，彩色图层在其上，但是彩色图层被巨幅拉伸

这说明亮度（Y）平面是对的，只有色度（UV）错位/被横向拉伸——典型的 NV12 交织 UV 步进错误。

## 2. 根因

`platform/switch/runtime/rfvp_movie_color.c` 的 `nv12_row_neon()` 每次处理 16 个输出像素，但读 UV 时用：

```c
/* 旧（错） */
chroma_dup(vld1_u8(uvr + (i >> 1)), &u0, &v0);
chroma_dup(vld1_u8(uvr + (i >> 1) + 4), &u1, &v1);
```

NV12 的 UV 是交织的 `U0 V0 U1 V1 ...`，每 16 个输出像素恰好对应 16 个 UV 字节。`(i >> 1)` 让指针每 16 像素只前进 8 字节，色度以一半速度读取 ⇒ **横向 2 倍拉伸**；Y 平面按正常步进，所以黑白底图正确。

为什么 Citron 影子验证没发现：Citron 没有真实 NVDEC，`avcodec_send_packet` 在第二个包就因 nvdec_status 报错（见 046 §5），因此冒烟一律写 `h264_sw.txt` 强制软解，走的是 `AV_PIX_FMT_YUV420P` 的 **planar 分支**（`galnx_yuv420p_to_rgba`，本来就对）；标量尾分支用 `uvr[(i >> 1) * 2]` = `uvr[i]` 也是对的。**只有真机硬件帧（`AV_PIX_FMT_NVTEGRA` → transfer 后的 NV12）会走这条 NEON 源码**。

## 3. 修复

```c
/* 新（对）：16 像素读 16 个交织 UV 字节 */
chroma_dup(vld1_u8(uvr + i), &u0, &v0);
chroma_dup(vld1_u8(uvr + i + 8), &u1, &v1);
```

`chroma_dup()` 内部用 `vuzp1q_s16/vuzp2q_s16` 提取偶/奇字节再 `vzip1q_s16` 复制成 8 lane，语义本身没有问题，问题只在传入的地址。改动仅 2 行，另加注释记录旧值与原因。

## 4. 影子测试（Citron）

硬件分支在模拟器上永远走不到，因此加了一个只在模拟器开启的自检：把软解得到的 planar 帧按显示宽度重新打包成 NV12，喂给**同一份硬件 kernel**，再与 planar kernel 的结果逐字节比较。

| 组件 | 内容 |
| --- | --- |
| C 侧开关 | `sdmc:/switch/rfvp/h264_nv12_selftest.txt` 存在 → `g_nv12_selftest=1`；`galnx_movie_nv12_selftest()` 暴露给 Rust |
| Rust 侧 | `horizon_h264.rs`：`H264Playback` 新字段 `nv12_scratch` / `shadow_rgba`；`nv12_shadow_compare()` 重打包 + 调 kernel + 比较；`decode_one()` 在 `planar != 0 && selftest` 时调用 |
| 日志 | `movie h264: nv12 shadow frame={} match={} diff_bytes={} planar_crc={:016x} nv12_crc={:016x}`（前 5 帧 + 每 30 帧；FNV-1a 64 位） |

结果（脚本 `run-h264-citron.sh`，run_dir `E:/galnx-build/p40/run-citron-04/h264/20261109-123716-rfvp`）：

- 103 条 shadow 记录，**全部 `match=1 diff_bytes=0`**，覆盖 frame 1 … 2940；两条 CRC 每次都相同（例：frame 1 = `64d90c15016fe325`）。
- `Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4`；解码节奏正常，`convert_us` p50 ≈ 2,544 µs（720p NEON）。
- 唯一 `[ERROR]` 是既有无关项 `id must be in range 0..256`（`crates/rfvp/src/subsystem/components/syscalls/color.rs:35`）。

## 5. 构建与产物

构建姿势不变（`build_switch.sh` 已含 FFmpeg 三静态库与新增 .c）：

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p40/build.sh'
```

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| `target/rfvp-switch/switch/rfvp.nro` | 10,670,136 B | `b93f34e3f4b1f50f4c0d43f1817199fbf39c14431d1f78969f5f2e52ebbdbee9` |
| `target/rfvp-switch-runtime/rfvp.elf` | 20,399,744 B | `c9abd983182dc27ceb983a86cb5f1e4d9b434d45513fc36956acb82bcba78184` |

补丁：`docs/builds/patches/rfvp-switch/P40b-nv12-color.diff`，226 行 / 4 文件 / sha256 `2904ab90b4a271125e5a628c64100d8ebbc83039abc7ddb3b7f19671f59931e4`；须在 `P40-op-h264.diff` 之后应用（P40 生成的 3 个平台文件 + P40 新增/修改的 `horizon_h264.rs`）。

补丁生成方式（避免 MSYS `diff -uN` 的坏 hunk 头）：把基树 `p31/rfvp-v117` 复制成 patchwork，先 `git apply -p1 P40-op-h264.diff` 得到 P40 态，再对 4 个文件 `git diff --no-index`，最后把 `diff --git/---/+++` 头重写为 `a/<相对路径>` `b/<相对路径>`。已在 P40 态上 `git apply --check` RC=0，且应用后 4 文件与当前树逐字节一致。

## 6. v1.2.1-test NSP

| 项 | 值 |
| --- | --- |
| NSP | `E:/galnx-build/p40/out121/IROSEKA_FHD-010047420000a000.nsp` 10,087,536,344 B sha256 `16d4cee091cdbe64ba3660344d29e781974b114ac24b60648c51afb2721e162d` |
| harness verify | 13 checks / 0 fail / 1 warn（未签名，符合 homebrew 预期）；3 个 NCA 的 ProgID 全为 `0x010047420000A000` |
| romfs | 166 个 hardlink 文件，`movie/01_h264.mp4` 108,361,267 B sha256 `bddf82fc7e78e256d812051a4f548c2dce07d8cdcda6c80562ea588f32757bad` |
| Citron 冒烟 | NSP(romfs) 形态：窗口 `IROSEKA FHD (64-bit) | 1.2.1-test`、`status=loaded`、24/24 步 ok、nonblack 0.9018；`Movie: opened (Switch NVDEC H.264)` 从 romfs 打开；**109 条 shadow 记录全部 match=1 diff_bytes=0**（frame 1…3120）；`convert_us` n=175 p50=2,530 p95=3,697 max=7,687 µs |

说明：Citron 冒烟是强制软解（`h264_sw.txt`），只能证明打包/接线/颜色 kernel 对 NV12 的解读正确；真机硬解路径本身仍由用户验收。冒烟窗口结束在 frame 3120（未整段 EOS），因为 harness 的等待/截图窗口先到点，OP 尾部没有跑完——这不影响颜色结论。

## 7. 限制

- 硬件分支在模拟器上不可达，本次验证是「kernel 等价性 + 真机症状消失（待验）」的组合，而不是真机硬解帧的像素比对。
- 影子测试按 `stride = width` 重新打包（1280）。若真机硬件帧的 `linesize[1]` 含 padding，kernel 按传入的 `uv_stride` 逐行取本身没问题，但这一点只能由真机确认。
- `h264_nv12_selftest.txt` 在生产 NSP 里默认不存在，自检完全关闭（不分配 scratch、零额外开销）。

## 8. 复现与教训

```bash
# 1) 构建 → 2) 影子验证（git-bash）→ 3) 看计数
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p40/build.sh'
/d/Scoop/apps/git/current/bin/bash.exe -c 'bash /e/galnx-build/p40/run-h264-citron.sh'
grep -c 'nv12 shadow.*match=1 diff_bytes=0' /e/galnx-build/p40/evidence/citron-04/debug_report.txt
```

教训：

1. **模拟器里跑不到的代码分支，必须用等价性测试而不是「截图看着对」来兜底。** Citron 的强制软解让 P40 的 planar 路径看起来完美，掩盖了硬件 NV12 路径的索引错误。
2. 索引类的 bug 有极强的症状特征：亮度对、色度横向拉伸 2 倍 ⇒ 先怀疑交织 UV 的步进（每像素 1 字节 vs 每 2 像素 4 字节）。
3. 影子测试要复用**生产 kernel 本身**，不要另写一份参考实现，否则测的是参考实现。
4. 修 bug 时把 marker 设计成「生产环境默认关闭、可随时开启」，这样回归测试不需要维护两套构建。
## 9. 真机验收（v1.2.1-test，2026-11-09）

用户回执（m36694）：

> 颜色正常，播放速度正常。
> 有需要的话你仍然可以从mtp拿log，不过我认为没什么问题了

设备日志（MTP **只读**拉取；设备写入归用户 m31356）：

| 文件 | 大小 / 行数 | 说明 |
| --- | --- | --- |
| `sdmc:/switch/rfvp/debug_report.txt` | 101,342 B / 1,210 行 | OP 段解码明细与帧率心跳 |
| `sdmc:/switch/rfvp/perf_slow.log` | 2,632,802 B / 10,563 行 | >25 ms 慢帧（跨会话累积） |

关键日志（原文）：

```text
[INFO] MoviePlay: path=movie/01.wmv flag=True is_layer_effect=false
[INFO] Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4
[INFO] movie h264: decoded frame=1 pts=0 ms 1280x720 hw=1 decode_us=7138 convert_us=3529
[INFO] movie h264: decoded frame=3570 pts=118966 ms 1280x720 hw=1 decode_us=5972 convert_us=3493
[INFO] movie h264: end of stream after 3597 frames (3597 hardware)
[INFO] movie h264: finished flag set (eof=true stash=0 decoded=3597 hw=3597)
frame 7620: 60.0 fps over the last 60 frames, slowest frame 26.0 ms
```

- **硬解比例**：decoded 采样 124 行全部 `hw=1`（`hw=0` 计数 0），EOS 记 `3597 hardware` ⇒ 整段 OP 全程硬件解码，无静默回落软解。
- **耗时**：`decode_us` 1,886–9,264 µs、`convert_us` ≈3.5 ms（720p NEON），与 Citron 软解路径 p50 2.5 ms 同量级 ⇒ 本轮只改 UV 读取地址，未改变时间预算。
- **帧率**：OP 后 `frame 7620: 60.0 fps over the last 60 frames, slowest frame 26.0 ms`，与 v1.2.0-test 的 60 fps 持平。
- **颜色**：用户观感「颜色正常」，即 `uvr + i` / `uvr + i + 8` 修复在真机硬件 NV12 分支生效。

**不能证明 / 未覆盖**：

- 只验证 720p30 H.264 一种资产（IROSEKA 的 120 s OP）；1080p60、HEVC、其它游戏资产未测。
- `perf_slow.log` 中故事区仍有既有慢帧（`save_finalize` 60–80 ms、`vfs_read`/`audio_cmds` 数秒级尖峰），本补丁不涉及；该文件跨运行累积，不能按 OP 段切分。
- 分发合规仍未处理（FFmpeg `--enable-gpl` + nvtegra ⇒ GPL 组合）。

证据：`docs/milestones/evidence/P42-op-h264-device/`（设备日志摘录 + `perf_slow` 统计 + SHA256SUMS）。
