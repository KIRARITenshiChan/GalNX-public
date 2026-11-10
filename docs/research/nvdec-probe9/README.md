# nvdec-probe9 源码归档

probe9 = probe8 + 日志降噪 + read/recv 拆分 + SD 读基准 + 时钟查询 + B2-h264 交叉验证。真机结论见 `docs/builds/045-nvdec-probe9.md`。

## 文件

| 文件 | 大小 | 用途 |
| --- | --- | --- |
| `Makefile` | 3,094 B | devkitA64 + libnx + SDL2 + FFmpeg nvtegra 静态库；`APP_TITLEID=01000000000000A9` |
| `include/galnx_nvdec.h` | 4,984 B | 解码封装 API：open/next/stats/last_timing/nv12/frame_index/require_hw/set_stage/close |
| `source/galnx_nvdec.c` | 22,464 B | FFmpeg 解码 + nvtegra 硬解初始化（只设 `hw_device_ctx`，由解码器派生 frames ctx）+ read/recv 计时 |
| `source/main.cpp` | 24,113 B | 8 个阶段（A/B/B2/C1–C5）、日志缓冲、io_bench、log_clocks、BMP 输出 |

## 构建

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  'cd /e/galnx-build/nvdec/probe9 && make -j8'
```

依赖：`E:/galnx-build/nvdec/research/ffmpeg-nvtegra`（源码）、`E:/galnx-build/nvdec/ffmpeg-build-nvtegra`（静态库，含 `h264_nvtegra`）、devkitPro 的 switch-sdl2/EGL/glapi/drm_nouveau。

## 产物

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| `nvdec-probe9.nro` | 9,134,136 B | `9708465d859600aa84e56ed6bff068fd5592e700eba32cbec1de8ad0229f3773` |
| `nvdec-probe9.elf` | 18,544,048 B | `aca57a8e88f411f8009e3a403d1bfcb13056b9803924c85f81d7b6c3ecdd9bdd` |

## 真机一句话结论

NVDEC 硬解 0.44 ms/帧（297.80 fps）、CE 传输 3.79 ms/帧都完全可用；慢放真因是 CPU NV12→RGBA 43.54 ms/帧。
