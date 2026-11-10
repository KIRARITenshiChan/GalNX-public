# 043 — NVDEC 探针 probe5：envideo 官方参考解码在真机 PASS

- 日期：2026-11-08
- 关联：`docs/builds/041-nvdec-probe3.md`（probe1–3）、`docs/builds/042-nvdec-probe4.md`（CPU 直读方案）、`docs/builds/044-nvdec-probe6.md`（nvtegra 路线）、`docs/research/nvdec-probe5/`、`docs/milestones/evidence/P37-nvdec-probe5/`
- 上游：averne/envideo master `826f184a…`（参考实现 `test/decode.cpp`）；averne/FFmpeg envideo 分支 tarball sha256 `d1755f40…`

## 1. 背景与目标

probe4 真机回传的决定性事实（原件归档在 `docs/milestones/evidence/P36-nvdec-probe4/`）：

```
f001: fence_wait rc=-3420 took=5000151 us          # 5 s 超时，CPU 侧等 ev->fence 从未 signal
f001: raw head = 00 00 00 ...                       # 表面全 0
f001: trial ... psnrY=0.71  (8 组候选全部相同)      # 布局假设根本没被检验
f030: trial ... psnrY=3.40
decode error: avcodec_send_packet: Unknown error occurred (-1313558101 / 0xb1b4b1ab)
```

⇒ 表面全 0、fence 5 s 超时、PSNR 与布局无关。这意味着 probe4 的「CPU 直读 block-linear 表面 + de-tile」
**无法定位问题**：连“解码到底有没有写这块内存”都无法确认。

probe5 因此改变提问方式，先回答一个二元问题：

> NVDEC + envideo（解码、tiled 表面、Copy Engine tiled→linear、cache 操作、fence）在**这台真机**上到底能不能用？

做法是复刻 envideo 仓库自带的参考测试 `test/decode.cpp`：它有内嵌的 MPEG-2 128×128 素材、固定的命令序列、
以及**已知的正确结果哈希** `0xa2c4a330592602d5`。如果真机能复现这个哈希，就说明整条底层链路是好的，
probe3/probe4 的失败只能落在 FFmpeg 的封装/参数层，而不是硬件、CE 或 tiling 假设。

## 2. 结论摘要

| 项 | 结果 |
| --- | --- |
| probe5 Phase A（envideo 原生参考解码，真机） | ✅ **PASS**：`status error=0 mbs_ok=64 cycles=5042`，map/nv12 哈希 = `a2c4a330592602d5` = 官方期望值 |
| probe5 Phase B（FFmpeg envideo + VC-1，真机） | ❌ 仍失败：fence 2 s 轮询不 signal、raw 全 0、`AVERROR_UNKNOWN`（`envideo_decode.c:255`） |
| 失败域收缩 | 硬件/CE/tiling **排除**；问题在 FFmpeg 的 envideo VC-1 提交路径（参数、码流、status 检查） |
| Phase A 视觉证据 | `probe5-mpeg2-device.bmp`（128×128 彩条 + 时间码，像素正常），PNG 见证据目录 |
| 新路线 | 换 `averne/FFmpeg` 的 **nvtegra** hwaccel（SwitchWave 真机已验证 1080p VC-1 可放），即 probe6 / 044 |
| probe5 Citron 冒烟 | ✅ 链路完整且**优雅失败**（`device_create rc=-88` → `PHASE A verdict: FAIL`，不崩），Phase B 120 帧、`=== DONE ===` |

## 3. FFmpeg / envideo 源码事实（probe5 的设计依据）

| 事实 | 出处 |
| --- | --- |
| `envideo_fence_wait(EnvideoDevice*, EnvideoFence, uint64_t timeout_us)`；Switch 后端 `Device::wait` → `nvFenceWait`，libnx 单位是**微秒** | `include/envideo.h:167`、`src/envideo.cpp:108`、`device.cpp:595`、`/d/devkitPro/libnx/include/switch/nvidia/fence.h:15` |
| hw 帧 `AVEnvideoFrame { EnvideoMap *map; EnvideoFence fence; bool is_pitch; uint8_t gob_height; }`，get_buffer 时 `f->fence = 0`，只有 transfer 路径才写 fence | `libavutil/hwcontext_envideo.h:223/:385` |
| `ff_envideo_wait_decode`（等 `field->operation.fence`）**唯一调用点是 VP9**；VC-1 路径从不等解码 fence | `libavcodec/envideo_decode.c:153-177`、`envideo_vp9.c:671` |
| `end_frame` 提交后写 `field->operation.fence` 与 `evframe->fence`；`start_frame` 轮询上一批 op 的 fence 并检查 `nvdec_status`，`error_status != 0 || mbs_in_error != 0` 即返回 `AVERROR_UNKNOWN` | `envideo_decode.c:245/:252-255/:392/:404` |
| envideo 自带测试只有原生 API（channel/cmdbuf/copy/decode/device/map），**没有 FFmpeg hwaccel 测试** | `/e/galnx-build/nvdec/research/envideo/test/` |
| 参考测试 `test/decode.cpp` 完全自包含（MPEG-2 128×128、命令数组、CE copy、期望哈希 `0xa2c4a330592602d5`） | `research/envideo/test/decode.cpp` 276–709 行 |

## 4. Phase A 实现（envideo 参考解码复刻）

新增/复用文件（全部归档在 `docs/research/nvdec-probe5/`）：

| 文件 | 作用 |
| --- | --- |
| `source/mpeg2_ref.cpp`（19,796 B） | 照抄参考流程：device/channel/cmdbuf + 4 个 map、命令序列 `SET_APPLICATION_ID=MPEG12` / `SET_CONTROL_PARAMS(GPTIMER_ON\|ERR_CONCEAL_ON\|MBTIMER_ON)` / 4 个 reloc / `SET_PICTURE_LUMA\|CHROMA_OFFSET0 Tiled` / `EXECUTE`；poll 解码 fence；copy 通道 `surface_transfer` + `cache_op Writeback` + submit；Invalidate 后 poll |
| `include/ref_mpeg2_data.h`（41,171 B） | 内嵌素材：setup 344 B / bitstream 6,426 B / sliceoffs 32 B |
| `source/xxh64.c` + `include/xxh64.h` | XXH64 实现，PC 侧单测三向量通过（`ef46db3751d8e999` / `d24ec4f1a98c6e5b` / `44bc2cf5ad770999`） |
| `source/galnx_probe4.c`（18,059 B） | Phase B：把 probe4 的 5 s 阻塞 wait 改为 100 ms×20 轮询（上限 2 s）+ 包探测 `pkt[i] size head` |
| `source/galnx_nvdec.c` / `source/galnx_swref.c` / `source/main.cpp` | Phase B 的 FFmpeg 解码、软解参考帧、报告与 SDL 显示 |

关键设计决定：**不改 `__nx_nv_service_type`，保留 libnx 默认 Auto**。理由：probe3 真机已用 Auto 成功解码 VC-1（`dec=1.67 ms`），
envideo 参考 fixture 用 Factory 只是为了 NVJPG；且 libnx 的 nv 初始化早于 `main()`，在 main 里赋值大概率无效。

## 5. Phase A 真机结果（决定性）

日志原件：`docs/milestones/evidence/P37-nvdec-probe5/nvdec-probe5-device.txt`（8,349 行原始 → 去 `[ffmpeg]` 后 160 行）。

```
ref: device_create rc=0 dev=0x5739c44020
ref: device info tegra_layout=1
ref: map_create(input) size=8192 rc=0     / map_create(frame) size=24576 rc=0
ref: map_create(result) size=24576 rc=0   / cmdbuf_map size=65536
ref: input layout status=0 setup=256 bitstream=768 sliceoffs=7424 input_size=8192
ref: device tegra_layout=1 -> tileFormat=1 (setup was 1)
ref: decode fence = 68719477795
ref: decode signalled after 0 us (poll)
ref: copy fence = 111680022267
ref: copy signalled after 0 us (poll)
ref: status error=0 mbs_ok=64 mbs_err=0 cycles=5042 slice_err=0
ref: status+00 = 40 00 00 00 00 00 00 00 b2 13 00 00 ...
ref: status verdict = OK
ref: hash map(24576 B)=a2c4a330592602d5 nv12(24576 B)=a2c4a330592602d5 expected=a2c4a330592602d5
ref: result+00 = 4d 47 4b 4e 47 4b 4e 48 4e 52 52 51 51 51 52 4f
REF_MPEG2: status=OK hash=MATCH verdict=PASS
PHASE A verdict: PASS (rc=0)
```

判读：

1. **解码可用**：`decode signalled after 0 us`、`mbs_ok=64 mbs_err=0`、`cycles=5042`；
2. **tiled 表面 + Copy Engine 可用**：copy fence 0 us signal，且 map 内容与另存的 `probe5-mpeg2.nv12`（24,576 B）逐字节相同；
3. **cache 管理可用**：Writeback + Invalidate 之后哈希才等于期望值；
4. **像素正确**：`a2c4a330592602d5` 与 envideo 官方期望值完全一致；BMP（`probe5-mpeg2-device.bmp`，49,206 B）肉眼可见彩条与时间码 `00:00:00.000`。

⇒ probe3/probe4 的绿屏与全 0 **不是**硬件、不是 CE、不是 tiling 布局假设的问题。

## 6. Phase B 真机结果（仍失败，但失败域已收缩）

```
f001: fence_poll NOT signalled after 2000000 us (poll rc=0), wait(0) rc=-3420
f001: raw head = 00 ...                                # 表面全 0
f001: trial tile_rows=16 off1=2088960 rows0=1088 detile=2.97ms psnrY=0.71
... 8 组候选 psnrY 全部 0.71（f030 全部 3.40）
f001: chosen tile_rows=16 off1=2088960 psnrY=0.71
decode error: avcodec_send_packet: Unknown error occurred (-1313558101 / 0xb1b4b1ab)
summary: rendered=2 skipped=71 hw=1 idx=73 elapsed=20130.8 ms
PHASE B rc=0 (informational; see report above)
=== DONE ===
```

- `-1313558101` == `AVERROR_UNKNOWN`，来源 `libavcodec/envideo_decode.c:255` 的 `nvdec_status` 检查
  ⇒ 至少有一个已提交 job 的 fence 轮询到 done（`envideo_fence_poll`），但硬件状态报错（VC-1 参数/码流层）；
  这也解释了「fence 不 signal」与「表面全 0」：解码没有真正产出有效帧。
- 包探测：`pkt[0] size=9198 head=c0 82 ...`、`pkt[1] size=1 head=f2`、`pkt[2] 11774`、`pkt[3] 13562`、`pkt[4] 16306`、
  `pkt[5] 20168`、`pkt[6] 23628`、`pkt[7] 20436`；VC-1 raw ES 没有 `00 00 01 0x` 起始码，首包 `c0 82`（BDU 起始码）正常，
  `pkt[1]` 只有 1 字节可疑。
- Phase A 已证底层可用 ⇒ 剩余问题在 FFmpeg 的 envideo VC-1 封装路径（上游未自测覆盖）。

## 7. Citron 冒烟（只能证明链路与降级，不作为 Phase A 证据）

```
nv: keeping libnx default nv service type (probe3 decoded with it)
ref: device_create rc=-88 dev=0x0
PHASE A verdict: FAIL (rc=-1)
summary: rendered=120 skipped=0 hw=0 idx=0 elapsed=6546.5 ms
PHASE B rc=0 (informational; see report above)
=== DONE ===
```

Citron 没有 envideo/NVDEC 后端，`device_create` 直接失败；探针按设计优雅降级（不崩溃）继续跑 Phase B 软解 120 帧。
证据：`docs/milestones/evidence/P37-nvdec-probe5/nvdec-probe5-citron.txt`、`citron-result.json`。

## 8. 构建

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'cd /e/galnx-build/nvdec/probe5 && make -j8'
```

依赖：`/e/galnx-build/nvdec/envideo-prefix/lib/libenvideo.a`（87,816 B `0d0cbc73…`）、FFmpeg envideo 分支静态库、SDL2/EGL/glapi/drm_nouveau。

| 产物 | 大小 | SHA-256 |
| --- | --- | --- |
| `nvdec-probe5.nro` | 9,437,240 B | `e438c91fd4f128a96afb8b9f23b8b3f63b13bad5365a3ef99443826c2ec811ff` |
| `nvdec-probe5.elf` | 18,693,496 B | `82743399748bd83020153cb4f09bc6ed4869e6523a4d37bfb5965d67e2f3d5d1` |
| `nvdec-probe5.nacp` | 16,384 B | `3dfee6fae9f76573004ce42a085fe087767982f89bf34d0a8e4d9d310df0b23f` |

## 9. 真机测试包 v5

目录 `E:/galnx-build/nvdec/device-test-v5/`（不入库，设备写入由用户执行）：

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `nvdec-probe5.nro` | 9,437,240 B | `e438c91f…c811ff` |
| `poc-1080p-vc1.wmv` | 46,606,544 B | `923c33214f145ae47f1f3ee9a425780a26ee56b78236f129ec660e558cbd7948` |
| `README.md` | 5,129 B | `a1ea4c9e460cb1c6150854958a5d0d640fe94b61c10850b997c968bcb4a45200` |
| `SHA256SUMS` | 167 B | `f1038a5dfec0a4b640c6fcbbf5bee495ca7883ffca998cef7a59c3a09468b540` |

用户真机回传：`nvdec-probe5.txt`（581,748 B）、`probe5-mpeg2.bmp`、`probe5-mpeg2.nv12`。

## 10. 限制

1. Phase A 只证明 **128×128 MPEG-2**；1080p VC-1 仍未通过（Phase B 失败）。
2. Phase B 的 FFmpeg envideo VC-1 封装未修（上游缺少 hwaccel 测试覆盖，参考实现只有原生 API）。
3. Phase A 能否用于实际播放器取决于两条路线之一：把 OP 重编码为 MPEG-2，或自研 VC-1 提交；两者都未落地。
4. envideo 为 GPL-2.0，FFmpeg 构建带 `--enable-gpl`；分发需附源码（内部研究探针暂不涉及分发）。

## 11. 复现

```text
1) 构建：见 §8（probe5 目录内 make）。
2) Citron：bash /e/galnx-build/nvdec/run-probe5-citron.sh（会拷 wmv 到 citron sdmc）。
3) 真机：nvdec-probe5.nro → sdmc:/switch/，poc-1080p-vc1.wmv → sdmc:/nvdec-poc.wmv，hbmenu 启动。
4) 判据：日志出现 REF_MPEG2: status=OK hash=MATCH verdict=PASS 与 PHASE A verdict: PASS。
```

## 12. 教训

1. **先证底层，再猜上层**：probe4 花了一整轮在「布局假设」上，而底层解码根本没工作；参考哈希一次就定案。
2. 官方自带的参考测试（含已知哈希）是最高性价比的诊断工具，优先复刻它而不是自创路径。
3. 「传输成功」不等于「像素正确」（probe3 的 CE 返回成功但全绿），必须做内容级校验（哈希/PSNR）。
4. 单位陷阱要写进日志：`envideo_fence_wait` 是微秒，5,000,000 就是 5 s，不是 5 ms。
5. 失败日志要落到文件并回传原件（本次 8,349 行），裁剪后的复现率会下降。
