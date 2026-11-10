# nvdec-probe5 源码归档

对应记录：`docs/builds/043-nvdec-probe5.md`、证据：`docs/milestones/evidence/P37-nvdec-probe5/`。

这是 probe5 的完整可重建源码副本。目标：在真机上复刻 `averne/envideo` 官方参考测试（MPEG-2 128×128，已知正确哈希 `0xa2c4a330592602d5`），
以此证明 NVDEC + tiled 表面 + Copy Engine + cache + fence 链路可用，从而把 probe3/probe4 的失败域收缩到 FFmpeg 的 envideo VC-1 封装层。

## 文件

| 文件 | 大小 | 作用 |
| --- | --- | --- |
| `Makefile` | 3,311 B | devkitA64 构建（TARGET `nvdec-probe5`，APP_TITLEID `01000000000000A5`） |
| `gen_arrays.js` | 1,088 B | 把 envideo 参考测试内嵌的 MPEG-2 素材生成为 C 头文件 |
| `build-envideo.sh` | 418 B | 构建 libenvideo.a 的入口（在 MSYS2 内执行） |
| `source/main.cpp` | 12,986 B | 报告与 SDL 显示；Phase A→Phase B 顺序执行；写 `sdmc:/nvdec-probe5.txt` |
| `source/mpeg2_ref.cpp` | 19,796 B | **Phase A**：照抄 envideo `test/decode.cpp` 的原生流程（device/channel/cmdbuf、4 个 map、命令序列、poll fence、CE transfer、cache 操作、status + 哈希校验） |
| `source/galnx_probe4.c` | 18,059 B | Phase B：probe4 的 CPU 直读/de-tile 逻辑，fence 改为 100 ms×20 轮询 + 包探测 |
| `source/galnx_nvdec.c` | 17,742 B | Phase B：FFmpeg envideo 解码封装 |
| `source/galnx_swref.c` | 6,384 B | 软解参考帧（显示序 {1,30}） |
| `source/xxh64.c` | 2,391 B | XXH64（与 envideo 参考测试同算法） |
| `include/ref_mpeg2_data.h` | 41,171 B | 内嵌 MPEG-2 素材：setup 344 B / bitstream 6,426 B / sliceoffs 32 B |
| `include/mpeg2_ref.h` | 456 B | `int galnx_ref_mpeg2_run(void);` |
| `include/galnx_probe4.h` | 2,388 B | probe4 API（含 `galnx_probe4_note_packet`） |
| `include/galnx_nvdec.h` | 3,108 B | FFmpeg 解码 API |
| `include/galnx_swref.h` | 973 B | 软解参考帧 API |
| `include/xxh64.h` | 254 B | `uint64_t galnx_xxh64(const void*, size_t, uint64_t);` |

## 构建

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'cd /e/galnx-build/nvdec/probe5 && make -j8'
```

依赖：`/e/galnx-build/nvdec/envideo-prefix/lib/libenvideo.a`（87,816 B `0d0cbc73…`）、FFmpeg `envideo` 分支静态库、SDL2/EGL/glapi/drm_nouveau、libnx。

## 产物哈希

| 产物 | 大小 | SHA-256 |
| --- | --- | --- |
| `nvdec-probe5.nro` | 9,437,240 B | `e438c91fd4f128a96afb8b9f23b8b3f63b13bad5365a3ef99443826c2ec811ff` |
| `nvdec-probe5.elf` | 18,693,496 B | `82743399748bd83020153cb4f09bc6ed4869e6523a4d37bfb5965d67e2f3d5d1` |
| `nvdec-probe5.nacp` | 16,384 B | `3dfee6fae9f76573004ce42a085fe087767982f89bf34d0a8e4d9d310df0b23f` |

## 真机结果（一句话）

Phase A **PASS**：`status error=0 mbs_ok=64 cycles=5042`、`hash map=nv12=expected=a2c4a330592602d5`；Phase B（FFmpeg envideo VC-1）仍 FAIL（`AVERROR_UNKNOWN`）。
