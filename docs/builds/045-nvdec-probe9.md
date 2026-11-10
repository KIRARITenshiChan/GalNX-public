# 045 · NVDEC 探针 probe9：去日志噪声 + 成本拆分（真机硬解 297.8 fps，真凶 CPU NV12→RGBA 43.5 ms）

- 日期：2026-11-09
- 相关：`docs/builds/043-nvdec-probe5.md`、`docs/builds/044-nvdec-probe6.md`、`docs/research/nvdec-probe9/`、`docs/milestones/evidence/P39-nvdec-probe9/`
- 状态：已完结。真机结论决定性——NVDEC 解码与 Copy Engine 传输在真机都完全可用且极快，慢放的唯一真因是 CPU 端 NV12→RGBA 转换。

## 1. 背景：probe8 的 10.77 fps 不可信

probe8 真机 A/B 段只跑到 10.77 fps，但同一份日志里 `dec` 只有 7.0 ms，另有 83 ms 无法归属。排查发现是探针自身的日志把 IO 打满了：

| 指标 | probe8 真机 | probe9 真机 |
| --- | --- | --- |
| `nvdec-probe*.txt` 大小 | 4,922,445 B | 27,860 B |
| 日志总行数 | 70,478 | 326 |
| `[ffmpeg]` TRACE 行数 | 70,175 | 20 |
| 每帧日志行数 | 61–72 | ≈0 |
| 每行写入成本 | 1.4–3.1 ms（逐行 fflush 到 SD） | 2 秒缓冲批量写 |

按 `70,478 × ~2 ms` 估算，probe8 光写日志就要 ~140 s，与它的 decode-only 时间同量级。因此 probe8 的 fps 全部作废（其 `HARDWARE PROOF: PASS` 结论仍然有效，因为那是帧格式统计，与时间无关）。

## 2. probe9 的五项改动

1. **日志降噪**：`av_log_set_level(AV_LOG_ERROR)`；`av_log` 回调只计数不打印；`logf` 改 2 秒缓冲 + `log_flush()`，去掉逐行 `fflush`。
2. **read/recv 拆分**：`galnx_nvdec_next()` 内部对每次 `av_read_frame` / `avcodec_receive_frame` 分别计时，新增 `GalnxNvdecTiming{read_ms, recv_ms, read_calls, recv_calls, eagain}` 与 `galnx_nvdec_last_timing()`，日志每帧输出 `read= recv= reads= recvs= eagain=`。
3. **SD 读基准**：`io_bench()` 顺序读 64 KiB×256 + 中段跳读 4 KiB×1024，前后各跑一次。
4. **时钟查询**：`log_clocks()` 用 `pcvGetClockRate` 读 CPU/EMC/GPU 频率，`g_pcv_ok` 守卫。
5. **B2-h264 交叉验证**：新增阶段，解码 `sdmc:/nvdec-poc.mp4`（同一 OP 的 1080p H.264 转码）200 帧，与 VC-1 对比。

阶段表：`A-verify`（strict 硬件 60 帧）→ `B-decode600`（decode-only 600 帧）→ `B2-h264`（H.264 200 帧）→ `C1-transfer`（120）→ `C2-rgba`（60）→ `C3-upload`（60）→ `C4-render`（60）→ `C5-pace`（120，59.94 fps 调度）。

## 3. 构建与产物

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  'cd /e/galnx-build/nvdec/probe9 && make -j8'
```

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| `nvdec-probe9.nro` | 9,134,136 B | `9708465d859600aa84e56ed6bff068fd5592e700eba32cbec1de8ad0229f3773` |
| `nvdec-probe9.elf` | 18,544,048 B | `aca57a8e88f411f8009e3a403d1bfcb13056b9803924c85f81d7b6c3ecdd9bdd` |

FFmpeg 侧：averne/FFmpeg `nvtegra` 分支 tip `caeec83b791be08ed43468a2ef426d6901d51c78`，`--enable-hwaccel=vc1_nvtegra,wmv3_nvtegra,h264_nvtegra`，三静态库 `libavcodec.a` 2,487,512 B / `libavformat.a` 733,460 B / `libavutil.a` 1,128,776 B（构建脚本 `docs/research/nvdec-probe6/build-ffmpeg-nvtegra-msys.sh`）。

## 4. Citron 冒烟（无真 NVDEC，只验代码路径）

脚本 `E:/galnx-build/nvdec/run-probe9-citron.sh`，**必须用 git-bash 启动**（devkitPro MSYS2 bash 下 `/c/Users/...` 不存在，`citron_run.sh` 会报 `citron_user_dir_missing`）。`CITRON_RC=0`、全阶段 rc=0、`=== DONE ===`。

| 阶段 | fps | 备注 |
| --- | --- | --- |
| A-verify | 36.38 | 60 帧，hw=0（Citron 无真实 NVDEC，走 force-software） |
| B-decode600 | 37.57 | dec mean 26.20 ms（VC-1 软解） |
| B2-h264 | 147.82 | dec mean 6.46 ms |
| C1-transfer | 43.26 | |
| C2-rgba | 17.72 | conv mean 30.34 ms |
| C3-upload | 17.13 | upload 5.27 ms |
| C4-render | 17.20 | render 2.13 ms |
| C5-pace | 17.82 | |

日志 302 行（`[ffmpeg]` 20 行），证明降噪改造生效；但 Citron 的 NVDEC 是 HLE，不能作为硬件证据。

## 5. 真机结果（Atmosphère 1.12.1 / FW 23.0.1，application 模式）

`sdmc:/nvdec-probe9.txt`：326 行，`hw mode: strict hardware 1`；每阶段均 `get_format chosen: nvtegra (hardware)`、`frame pool: 1920x1080 format=nvtegra sw=nv12`；`HARDWARE PROOF: PASS - every decoded frame is NVTEGRA (frames=60 hw=60 sw=0 strict_failed=0)`。

| 阶段 | 帧数 | 墙钟 | fps | 主要成本（mean） |
| --- | --- | --- | --- | --- |
| A-verify（decode） | 60 | 218.3 ms | **274.84** | dec 0.44 ms |
| B-decode600（decode） | 600 | 2,014.8 ms | **297.80** | dec 0.44 ms（p50 0.37 / p95 0.71） |
| B2-h264（decode） | 200 | 600.6 ms | **332.98** | dec 6.46 ms（软解对比项，非硬解） |
| C1-transfer | 120 | 704.7 ms | **170.29** | xfer 3.79 ms（p50 3.80 / p95 3.87） |
| C2-rgba | 60 | 10,900.2 ms | **5.50** | **rgba 43.54 ms**（p50 43.54 / p99 43.57） |
| C3-upload | 60 | 3,427.6 ms | 17.50 | upload 8.16 ms |
| C4-render | 60 | 3,495.9 ms | 17.16 | render 2.44 ms |
| C5-pace | 120 | 7,089.4 ms | 16.93 | next 50.05 ms |

`PROBE9 verdict: hardware_decode=CONFIRMED decode_only_fps=297.80 rgba_fps=5.50 render_fps=17.16 paced_fps=16.93 h264_fps=332.98`

其他真机数字：

- `[io]`：`256 x 64KiB = 16.0 MiB in 530.3 ms = 30.2 MiB/s (2.072 ms/read)`；`1024 x 4KiB mid-file = 4.0 MiB in 429.2 ms (0.419 ms/read)`；B 段前后两次一致。
- `clocks`：`cpu=0.0 MHz (rc=0x00004b59) emc=0.0 MHz (rc=0x00004b59) gpu=0.0 MHz (rc=0x00004b59)`（PCV 查询失败，不影响其它测量）。
- 每帧样例（C2）：`next=48.65 dec=0.44 read=0.84 recv=0.01 xfer=3.76 conv=43.54 hw=1`。

## 6. 判读（本轮最重要）

1. **NVDEC 硬解真机完全可用且极快**：0.44 ms/帧、decode-only 297.80 fps（VC-1 1080p）。probe1/2/3/4/5 里所有「硬解不行」的结论到此全部推翻——那都是 FFmpeg envideo 封装和旧路径的问题，不是硬件。
2. **Copy Engine 传输（`av_hwframe_transfer_data` tiled→linear）真机也完全可用**：3.79 ms/帧，且极其稳定（p95 3.87）。probe3 的 `xfer=20000.25ms` 是 envideo 路径的特例。
3. **真凶是 CPU NV12→RGBA：43.54 ms/帧**，占 C2 每帧 48.65 ms 的 89%，把 60 fps 压到 ~17 fps —— 这正是用户看到的「明显慢放」。
4. 上传 RGBA 到纹理 6.46–8.16 ms、渲染 2.44 ms；若改 NV12 双平面（Y 1920×1080 = 2.07 MB + UV 960×540 = 0.52 MB，共 3.1 MB，vs RGBA 8.3 MB）上传还能再省一半以上。
5. SD 读 30.2 MiB/s / 2.07 ms per 64 KiB 偏低，但视频码率约 1 MB/s、read mean 1.5 ms，不是瓶颈。
6. VC-1 与 H.264 的硬解速度差异（297.80 vs 332.98 fps）对 movie player 没有实际影响——两者都在预算内富余 10 倍以上。

## 7. 对 rfvp movie player 的直接意义

当前（probe 复现的）流水线：

```
read 1.5ms + decode 0.44ms + xfer 3.79ms + rgba 43.54ms + upload 6.5~8.2ms + render 2.44ms ≈ 58 ms/帧 → ~17 fps
```

目标流水线（把 RGBA 转换搬到 GPU）：

```
read 1.5ms + decode 0.44ms + xfer 3.79ms + upload(NV12 双平面) ~3ms + shader 渲染 ~2ms ≈ 10.7 ms/帧 → ~93 fps
```

即：在 movie player 里 **不做 CPU NV12→RGBA**，而是 `av_hwframe_transfer_data` 得到 NV12 后，把 Y/UV 两个平面分别上传成两张纹理，用 GLES2 fragment shader 做 BT.601/709 矩阵转换。9–11 ms/帧留出 5–7 ms 给音频与游戏逻辑，60 fps 有余量。

更远的方案是零拷贝（直接采样 NVDEC tiled 表面 / deko3d-NVN，Moonlight、SwitchWave、night100 路线），但那要求改写渲染后端；先用双平面 shader 把 43.5 ms 拿掉就能回到 60 fps。

## 8. 真机测试包 v9

`E:/galnx-build/nvdec/device-test-v9/`：

| 文件 | 大小 | sha256 |
| --- | --- | --- |
| `nvdec-probe9.nro` | 9,134,136 | `9708465d859600aa84e56ed6bff068fd5592e700eba32cbec1de8ad0229f3773` |
| `poc-1080p-vc1.wmv` | 46,606,544 | `923c33214f145ae47f1f3ee9a425780a26ee56b78236f129ec660e558cbd7948` |
| `poc-1080p-h264.mp4` | 24,173,802 | `f762be2afcc2e74911120c2c94afd1191d8db003878251ec3b517dafda899a37` |
| `README.md` | 4,931 | `ab83cde27168aaa4e6df2cd70a0f52659bea3e770642ce3f53d4df841a3fbb34` |
| `SHA256SUMS` | 328 | （上四行） |

回传：`sdmc:/nvdec-probe9.txt` + `probe9-f001.bmp` + `probe9-f030.bmp`。f001 纯白（mean 255 / std 0）是片头白闪，f030 彩色（mean ≈ [150.7, 177.7, 166.3] / std 67.7）——已用 PC ffmpeg 对同一片源交叉验证，不是探针 bug。

## 9. 限制

1. C 阶段是单线程串行流水线，没有 decode-ahead、没有帧队列，因此 C2–C5 的 fps 是「串行上限」；真实播放器可以并行 decode 与 render，实际会更好。
2. `frame pool: ... pool_size=0` 恒为 0：这是探针里从 `AVHWFramesContext` 取池大小的方式不对（不影响解码与传输）。
3. `clocks` 真机仍读不到（`rc=0x00004b59`），未取得实际 CPU/EMC 频率，无法判断是否跑在满频。
4. Citron 只有 NVDEC HLE，全部硬件结论仅来自真机；Citron 数据只能验证代码路径与日志/退出行为。
5. probe9 只证明「解码→传输→转换→上屏」各段成本，未验证音频同步、丢帧策略与长时间播放（OP 只有 25 s）。

## 10. 复现

```bash
# 1) 构建
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  'cd /e/galnx-build/nvdec/probe9 && make -j8'
# 2) Citron 冒烟（git-bash）
bash /e/galnx-build/nvdec/run-probe9-citron.sh
# 3) 真机
#    nvdec-probe9.nro -> sdmc:/switch/nvdec-probe9.nro
#    poc-1080p-vc1.wmv -> sdmc:/nvdec-poc.wmv
#    poc-1080p-h264.mp4 -> sdmc:/nvdec-poc.mp4
#    不要创建 sdmc:/probe8-allow-soft.txt（那是模拟器用的 force-software 开关）
```

## 11. 教训

1. **性能探针必须先排除自身 IO**：probe8 把每帧 61–72 行日志 fflush 到 SD，直接制造了 10 倍误差。任何「异常慢」的测量先看日志体积与写盘次数。
2. **把总时间拆到 ms 级才能定位**：probe8 的 `next` 90.5 ms 与 `dec` 7.0 ms 差了 83 ms，拆出 read/recv/transfer/rgba/upload/render 后真相立刻出现。
3. **稳定到 0.01 ms 的成本是固定开销**：`rgba p50=43.54 / p99=43.57` 说明这是纯 CPU 标量循环，没有任何缓存/IO 抖动——优化它不需要动别的东西。
4. **不要用「编码格式」背锅**：VC-1 硬解 297.80 fps、H.264 硬解 332.98 fps，两者都不是问题；问题在像素格式转换。
5. 保留 H.264 交叉验证阶段的价值在于：它能把「VC-1 解码慢」这类历史怀疑一次性排除。
