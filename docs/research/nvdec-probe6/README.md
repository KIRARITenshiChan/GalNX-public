# nvdec-probe6 源码归档

对应记录：`docs/builds/044-nvdec-probe6.md`、证据：`docs/milestones/evidence/P38-nvdec-probe6/`。

probe6 改用 `averne/FFmpeg` 的 **nvtegra** hwaccel（分支 tip `caeec83b791be08ed43468a2ef426d6901d51c78`）解同一份
1080p VC-1 素材，用于判断「FFmpeg 封装层到底能不能在本机跑通 VC-1 硬解」。

## 文件

| 文件 | 大小 | 作用 |
| --- | --- | --- |
| `Makefile` | 3,093 B | devkitA64 构建（TARGET `nvdec-probe6`，APP_TITLEID `01000000000000A6`），链接 nvtegra 版 FFmpeg 三个静态库 |
| `build-ffmpeg-nvtegra-msys.sh` | 1,806 B | 交叉编译 nvtegra 版 FFmpeg（含 `__SWITCH__` 修法，见下） |
| `source/galnx_nvdec.c` | 17,289 B | FFmpeg 解码封装：`AV_HWDEVICE_TYPE_NVTEGRA` + `AV_PIX_FMT_NVTEGRA`，hw 失败自动降级软解；`emit_frame` 用 `av_hwframe_transfer_data` → RGBA |
| `source/main.cpp` | 14,573 B | 报告 `sdmc:/nvdec-probe6.txt`、软解参考帧、SDL 显示、`dec/xfer/conv` 计时、BMP 落盘、PSNR 对照、`PROBE6 verdict` |
| `source/galnx_swref.c` | 6,384 B | 软解参考帧（显示序 {1,30}） |
| `include/galnx_nvdec.h` | 2,995 B | 解码 API（含 `galnx_nv6_log`） |
| `include/galnx_swref.h` | 973 B | 软解参考帧 API |

## 构建

先编 FFmpeg（MSYS2）：

```bash
bash /e/galnx-build/nvdec/build-ffmpeg-nvtegra-msys.sh
```

关键坑：`nvhost_ioctl.h` 在非 `__SWITCH__` 下走 `#include <linux/ioctl.h>`，devkitA64 不会自动定义该宏，
故 `--extra-cflags` 必须含 `-D__SWITCH__ -D_GNU_SOURCE -D_POSIX_VERSION=200809L -isystem /opt/devkitpro/libnx/include`。

再编探针：

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'cd /e/galnx-build/nvdec/probe6 && make -j8'
```

## 产物哈希

| 产物 | 大小 | SHA-256 |
| --- | --- | --- |
| `nvdec-probe6.nro` | 9,117,752 B | `92e1796a3941b422ee259ba75939e992ccb0f4c1ed63a25b23306f35a9fb0d11` |
| `nvdec-probe6.elf` | 18,291,904 B | `75b6f3575ac6d7fa00f1247aadf3bacec14df435e42b8a29d14fd3ea1113f319` |
| `nvdec-probe6.nacp` | 16,384 B | `6d38784e626cc37d31f6f032f98dd079bbe303b01bfba7be2178edd2df082b9f` |

## 状态

Citron 冒烟通过（`hw: nvtegra device created` 但解码帧 `hw=0`，软解 120 帧、`=== DONE ===`）。
真机验证（device-test-v6）待用户回传 `nvdec-probe6.txt` + `probe6-f001.bmp` + `probe6-f030.bmp`。
