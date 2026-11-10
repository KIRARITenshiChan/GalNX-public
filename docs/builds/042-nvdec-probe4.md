# 042 — NVDEC 探针 probe4：绕过 Copy Engine 的 CPU 直读方案

- 日期：2026-11-08
- 关联：`docs/builds/041-nvdec-probe3.md`（probe1–3）、`docs/research/nvdec-probe4/`、`docs/milestones/evidence/P36-nvdec-probe4/`
- 上游：averne/envideo master `826f184a…`、averne/FFmpeg envideo 分支 tarball sha256 `d1755f40…`（pin 见 041 §4）

## 1. 背景与目标

probe3 在真机上把「FFmpeg + envideo 硬解 + SDL2 上屏」跑通了，但画面不可用。用户回传的日志
（`docs/milestones/evidence/P36-nvdec-probe4/nvdec-probe3-device.txt`，全文 12 行）给出决定性事实：

```
applet_type=0 application=1
info: 1920x1080 codec=vc1(70) pix_fmt=yuv420p fps=59.940 duration_ms=25130 frames_hint=-1 hw_requested=1
renderer=opengles2 flags=0xe
bmp: wrote sdmc:/nvdec-probe3-001.bmp (1920x1080)
frame=1 pts=33ms dec=1.67ms xfer=20000.25ms conv=35.35ms hw=1 1920x1080
progress: frames=1 fps=0.04 hw=1 sw=0
progress: frames=3 fps=0.10 hw=3 sw=0
progress: frames=5 fps=0.10 hw=5 sw=0
progress: frames=7 fps=0.10 hw=7 sw=0
```

截图（用户屏摄）表现为：整屏绿色 + 屏幕上方约 17% 是扫描线乱码。

于是问题被**切分成两半**：

1. 解码：`dec=1.67ms`、`hw=7 sw=0` ⇒ NVDEC 本身在真机完全可用，**不是**瓶颈。
2. 搬运：`xfer=20000.25ms`（首帧整数 20.000 s，后续约 10 s/帧）且产出错误 ⇒ 卡在
   `av_hwframe_transfer_data()`（Copy Engine，tiled→linear），而不是解码。

probe4 的目标不是继续调 CE，而是**绕过它**：把 NVDEC 表面（block-linear）直接当内存读出来，
在 CPU 上 de-tile，并用软件解码的同一帧做 PSNR 标定，让**一次真机运行**同时回答两件事：

- 这块表面到底是什么布局（平面 1 偏移、tile 行高）；
- 能不能用合理的 CPU 成本拿到正确像素。

## 2. 结论摘要

| 项 | 结果 |
| --- | --- |
| probe3 真机：硬解可用性 | ✅ 1080p VC-1 解码 1.67 ms/帧 |
| probe3 真机：CE tiled→linear | ❌ 20 s/帧（首帧）且内容错误（绿屏 + 扫描线） |
| probe4 设计 | CPU 直读 envideo map（Horizon 上 NVDEC 帧 map 是 CPU 可写主机内存）→ fence 等待 → 12 组候选布局 de-tile → 亮度 PSNR 选优 → 落盘 + 上屏 |
| probe4 构建 | ✅ 一次编译通过；NRO 9,420,856 B sha256 `b5acc4ded3991dbcc17e973c9631f5672e3ac9072452d746c50feb5cf3792acd` |
| probe4 模拟器（Citron） | ✅ 链路完整（软解参考 655.4 ms、SDL 初始化、120 帧、`=== DONE ===`），但 hw 分支未被走到（Citron 无 NVDEC，全部 `hw=0`） |
| probe4 真机 | ⏳ 待用户运行 `nvdec-probe4.nro`，回传 `nvdec-probe4.txt` + 2 张 BMP（raw/yuv 可选） |

## 3. 关键事实（查源码得到，构成 probe4 的假设）

| 事实 | 出处 |
| --- | --- |
| NVDEC 输出**必须**是 tiled，不能选 pitch-linear | `nvdec_drv.h`：`tileFormat:2 // 0:TBL 1:KBL 2:Tile16x16` |
| Horizon 上 envideo 的 NvMap 是 CPU 可写主机内存 | `envideo/src/nvgpu/device.cpp:794-797`：`#if defined(__SWITCH__) this->map_cpu();` |
| `envideo_map_pin` 缺失不是 CE 慢的原因 | `envideo/src/common.hpp:203 engine_is_multimedia()` 只对 Nvdec/Nvenc/Nvjpg/Vic/Ofa 为 true，**Copy/Host 为 false** ⇒ pin 对 Copy 通道是 no-op（推翻 041 §9 的怀疑项） |
| 帧布局参数（真机日志读出） | `linesize[0]=1920`、`linesize[1]=1920`、平面 1 偏移 **2,088,960 = 1920×1088**（`align(1080,32)`）、map 大小 **3,133,440 B**、`is_pitch=false`、`gob_height=2` |
| CE 的 20 s 更像 fence 超时而非真实搬运 | 20.000 s / 10 s 都是整数级；envideo 通道 submit timeout 为 1000 ms 量级，怀疑等待逻辑在错误 fence 上自旋 |

## 4. 实现

源码在 `docs/research/nvdec-probe4/`（4 个源文件 + 3 个头 + Makefile，全部为 GalNX 自有代码）：

- `source/galnx_probe4.c`（465 行）——de-tile / PSNR / NV12→RGBA / 落盘 / 候选扫描；
- `source/galnx_swref.c`——纯软解参考帧（显示序 1 与 30，planar YUV420P）；
- `source/galnx_nvdec.c`——probe3 的解码封装，新增 `probe_mode` 分叉：目标帧不 transfer 而是交探针；
- `source/main.cpp`——实验入口（参考帧 → NVDEC → 报告 → SDL 上屏 → BMP）。

### 4.1 句柄链路

```c
AVHWFramesContext      *fc = (AVHWFramesContext *)f->hw_frames_ctx->data;
AVHWDeviceContext      *dc = (AVHWDeviceContext *)fc->device_ref->data;
AVEnvideoDeviceContext *ec = (AVEnvideoDeviceContext *)dc->hwctx;
AVEnvideoFrame         *ev = (AVEnvideoFrame *)f->buf[0]->data;
EnvideoMap             *map = …;   /* 由 ev->map / map_from_fence 取得 */
envideo_fence_wait(ec->device, ev->fence, 5000000ULL);            /* 先等，记 rc 与耗时 */
envideo_map_cache_op(map, off0, msize - off0, EnvideoCache_Invalidate);
```

### 4.2 布局候选（12 组）

- 平面 1 偏移 ∈ {`f->data[1] - gpu0`（实测 2,088,960）, `stride0 × h`, `stride0 × align32(h)`}；
- tile 行高 ∈ {16, 8, 32, 64}（`gob_height=2` ⇒ 64 B × 16 行是首选，其它作为容错）；
- 每组 de-tile 后与参考帧算**亮度 PSNR**，取最高者，并在报告里打印全部候选的 PSNR，
  这样即使首选假设错了，也能从日志反推真实布局。

### 4.3 de-tile 公式

```
tile_w = 64; tiles_per_row = width_bytes / 64; tile_bytes = 64 * tile_rows
src_off(band b, tile t) = (b * tiles_per_row + t) * tile_bytes
dst_row(b, r) = b * tile_rows + r;  dst[dst_row][t*64 + c] = src[src_off + r*64 + c]
```

### 4.4 产物

真机运行后 SD 卡写入：

| 文件 | 大小 | 用途 |
| --- | --- | --- |
| `sdmc:/nvdec-probe4.txt` | 数 KB | 全部观测：fence rc/耗时、候选 PSNR、chosen、耗时、summary |
| `sdmc:/nvdec-probe4-f001-raw.bin` / `-f030-raw.bin` | 3,133,440 B | NVDEC 原始表面（PC 侧可离线复算布局） |
| `sdmc:/nvdec-probe4-f001-ref.yuv` 等 | 3,110,400 B | 软解参考帧（planar YUV420P） |
| `sdmc:/nvdec-probe4-f001-detiled.yuv` 等 | 3,110,400 B | de-tile 结果（判 PSNR 不等于 99 时逐行对比） |
| `sdmc:/nvdec-probe4-f001.bmp` / `-f030.bmp` | ~6 MB | 上屏用的 RGBA 转 BMP，人眼判据 |

## 5. 构建

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  'cd /e/galnx-build/nvdec/probe4 && make -j8'
```

结果：`BUILD_RC=0`，一次通过。产物：

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `nvdec-probe4.nro` | 9,420,856 B | `b5acc4ded3991dbcc17e973c9631f5672e3ac9072452d746c50feb5cf3792acd` |
| `nvdec-probe4.elf` | 18,631,880 B | `e56b76766af7d1320a54318cc511085b3988b11883df31a5702637a2450aeff9` |
| `nvdec-probe4.nacp` | 16,384 B | `7045f12bb07c5e9b5400b75c7ff772950a6b0ad35e0184afc51c9e1f26b40e98` |

## 6. 模拟器冒烟（Citron `0237a9b88`，无 NVDEC）

脚本 `E:/galnx-build/nvdec/run-probe4-citron.sh`（沿用 probe3 模板，一律 `--detach`），
run dir `E:/galnx-build/nvdec/run-citron4/20261108-120259-nvdec-probe4`。

| 项 | 值 |
| --- | --- |
| 退出码 | `CITRON_RC=0`；`status=loaded` |
| 软解参考 | `swref: found=2 1920x1080 time=655.4 ms err=-` → `swref[0]/[1] ok` |
| 媒体信息 | `1920x1080 codec=vc1(70) pix=yuv420p fps=59.940 duration=25130 ms` |
| SDL | `window=0x2101e0a4b0 renderer=0x2101ee1ea0 texture=0x2107de2920` |
| 解码循环 | 120 帧，全部 `hw=0`；`summary: rendered=120 skipped=0 hw=0 idx=0 elapsed=7056.0 ms` |
| 结束 | `=== DONE ===` |
| 窗口截图 | PrintWindow 71,022 B，`nonblack_ratio=0.9998`（但抓在程序退出后，只剩 Citron 列表页，不作为渲染证据） |

**这条证据的边界**：Citron 没有 NVDEC，`hw=0` 意味着 probe4 的 hw 分支（fence、CPU 直读、de-tile、PSNR）
**一行都没执行**。模拟器只证明「程序能启动、软解参考能跑、SDL 能出窗口、循环能结束、日志能落盘」，
布局与像素正确性只能由真机回答。

## 7. 真机测试包（v4）

目录 `E:/galnx-build/nvdec/device-test-v4/`（设备写入一律由用户执行）：

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `nvdec-probe4.nro` | 9,420,856 B | `b5acc4de…` |
| `poc-1080p-vc1.wmv` | 46,606,544 B | `923c33214f145ae47f1f3ee9a425780a26ee56b78236f129ec660e558cbd7948` |
| `README.md` | 4,538 B | 安装与回传说明（中文） |
| `SHA256SUMS` | — | 上述两项 |

步骤：`nvdec-probe4.nro` → `/switch/nvdec-probe4.nro`；`poc-1080p-vc1.wmv` → `/nvdec-poc.wmv`；
hbmenu 启动；等待 `=== DONE ===`。回传：`/nvdec-probe4.txt` + `-f001.bmp` + `-f030.bmp`（必需），
`-f001-raw.bin` / `-f001-ref.yuv`（可选，PC 复算布局）。

成功判据：`chosen: tile_rows=… psnrY=…`，`psnrY > 40` 可用（99 = 逐字节相同）；BMP 人像清楚不绿。

## 8. 限制与未验证

1. **布局未验证**：`2,088,960` 与 `tile_rows=16` 来自源码/驱动字段推导，尚未被真机 PSNR 证实。
2. **CPU 成本未知**：1080p 单平面 3.1 MB 的 de-tile + NV12→RGBA 在 A57 上的耗时由探针记录
   （`detile_ms`/`convert_ms`），但只有当布局正确时这些数字才有意义。
3. **CE 根因未定**：probe4 只是绕开，没有解释 `av_hwframe_transfer_data` 为什么 20 s。
   若未来要用 CE（例如零拷贝上屏），仍需回到 fence/几何细节。
4. **未接入产品代码**：probe4 是独立 NRO；接进 rfvp 影片播放器（1080p VC-1 直放 + 480 软解兜底）
   是下一步 P37，需先有真机 PSNR 结论。
5. **GPL**：探针依赖 envideo（GPL-2.0）+ 启用 gpl 的 FFmpeg ⇒ 若随 NSP 分发构成 GPL 组合，自用无碍。

## 9. 复现

```bash
# 1) 编译探针（唯一姿势：devkitPro MSYS2）
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  'cd /e/galnx-build/nvdec/probe4 && make -j8'

# 2) 模拟器冒烟（无 NVDEC，预期全 hw=0，只验链路）
bash /e/galnx-build/nvdec/run-probe4-citron.sh

# 3) 真机（由用户操作，GalNX 侧只做本地产物与只读分析）
#    cp nvdec-probe4.nro  -> sdmc:/switch/nvdec-probe4.nro
#    cp poc-1080p-vc1.wmv -> sdmc:/nvdec-poc.wmv
#    回传 sdmc:/nvdec-probe4.txt + 2 张 BMP
```

## 10. 教训

1. **先分割故障域再优化**：`dec` 与 `xfer` 分开计时后，"NVDEC 不可用"这个模糊结论立刻变成
   "解码 1.67 ms，搬运 20 s"两个独立问题，probe4 的设计因此只花了一次迭代。
2. **推翻假设要写进文档**：`envideo_map_pin` 一度被当作 CE 慢的原因，查源码确认 Copy 通道是 no-op 后
   必须在 041 §9 留下纠正记录，否则下一个人会重复验证。
3. **模拟器证据要标边界**：Citron 能跑 probe4 却完全不覆盖 hw 分支，若不写明「`hw=0` ⇒ hw 分支未执行」，
   很容易把"探针跑通了"误当成"直读方案可行"。
4. **让一次真机运行带回尽量多信息**：探针落盘 raw + ref + detiled + 12 组 PSNR 日志，即使首选布局错，
   也能在 PC 上离线复算，避免"再跑一次真机"。这一点直接来自 probe3 只能拿回 12 行日志的教训。
5. **整数级异常值优先怀疑超时逻辑**：20.000 s / 10 s 这种整齐数字几乎不可能是真实带宽造成的。
