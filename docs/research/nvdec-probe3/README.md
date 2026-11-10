# NVDEC 探针（probe1/2/3）与构建配方

本目录保存 GalNX 评估「Switch 真机 NVDEC 硬解 → SDL2 上屏」这条链路时写下的**自有代码**与构建配方。
上游依赖（averne/envideo、averne/FFmpeg envideo 分支、SwitchWave）不在此目录，按下面 pin 的上游取回即可。

许可提醒：envideo 为 GPL-2.0，FFmpeg envideo 构建启用 `--enable-gpl`。探针/未来 NSP 若分发，整体构成 GPL 组合
（rfvp 为 MPL-2.0，兼容；自用无碍，公开分发需附源码）。本目录代码仅作研究记录，不承诺随 NSP 发布。

## 一、上游 pin（2026-11-08 实测）

| 组件 | pin | 说明 |
| --- | --- | --- |
| averne/envideo | master `826f184a1117fd1a4d79be77da05c05aa83b3b81`（2026-10-24，nvidia: fix unbounded timeout） | 提供 `libenvideo.a`：nvhost-nvdec 通道、cmdbuf、surface transfer、constraints |
| averne/FFmpeg（envideo 分支） | tarball sha256 `d1755f40023f1d094fe316d8770ea72872be1891ac11cd34c44b1ade7b169329`（16,916,472 B，下载时上游分支 HEAD `8a49f6e67e2ca3160706f90cde3d06c6709f9542`） | 提供 `AV_HWDEVICE_TYPE_ENVIDEO` / `AV_PIX_FMT_ENVIDEO` 与 vc1/h264 等 hwaccel；tarball 无 git 元数据，按 sha pin |
| averne/SwitchWave 源码 | tarball sha256 `89294b12e320052d3299c95d8942a69a325dbcb17903a989c457fc6eeb573f61`（142,691 B） | 仅作参考（应用模式 / `__nx_nv_service_type` / transfermem 配置） |

产物哈希（本机实测）：
- `libenvideo.a` 87,816 B sha256 `0d0cbc733a4727337f1a7e5ac07277cfd65c6cb0a3782c38d5bc60571e946983`（elf64-littleaarch64）
- FFmpeg：`libavformat.a` 791,028 B `bc9558a1…`、`libavcodec.a` 2,748,142 B `2ed10f2e…`、`libavutil.a` 1,262,206 B `e9eb4b3d…`

## 二、envideo 手动交叉编译（无 meson 时的可行路径）

devkitPro MSYS2 里 pacman 装不上 meson（代理 XferCommand 报 curl 47 重定向），所以手工编译 5 个源：

- 编译器：`/d/devkitPro/devkitA64/bin/aarch64-none-elf-g++.exe`
- 源：`src/cmdbuf.cpp src/constraints.cpp src/envideo.cpp src/nvgpu/device.cpp src/nvgpu/channel.cpp`
- 关键 flags：`-std=gnu++20 -D__SWITCH__ -D_GNU_SOURCE -D_POSIX_VERSION=200809L -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIC -ftls-model=local-exec -O2 -w`
- include：`-I<envideo root> -I<root>/include -I<root>/src/nvclasses -I<root>/src/nvgpu/uapi -I<build> -I$DKP/portlibs/switch/include -isystem $DKP/libnx/include`
- 生成 `config.h`：`#pragma once` + `#define CONFIG_NVGPU 1`
- 坑：所有 `-I` 与路径必须 `cygpath -m` 转成 Windows 形式，否则 `nvmisc.h: No such file or directory`。
- 脚本留在 `E:/galnx-build/nvdec/build-envideo2.sh`（本目录不重复保存环境相关路径）。

## 三、FFmpeg（envideo 分支）静态库交叉编译

在 devkitPro MSYS2 中 configure（必须在 MSYS2 里跑：`env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '...'`，`DEVKITPRO=/opt/devkitpro`）：

```
--target-os=horizon --enable-cross-compile --cross-prefix=aarch64-none-elf- \
--arch=aarch64 --cpu=cortex-a57 --enable-neon --enable-static --disable-shared \
--disable-autodetect --disable-runtime-cpudetect --disable-debug --disable-doc \
--disable-programs --disable-encoders --disable-muxers --disable-devices \
--disable-network --disable-swresample --disable-filters --disable-everything \
--enable-envideo --enable-gpl --enable-decoder='vc1,h264,wmv3' \
--enable-parser='vc1,h264' --enable-demuxer='asf,mov' --enable-protocol=file \
--enable-hwaccel='vc1_envideo,h264_envideo' \
--extra-cflags='-O2 -fPIC' \
--extra-ldflags='-fPIE -specs=/opt/devkitpro/libnx/switch.specs -L/opt/devkitpro/libnx/lib'
```

三个关键坑：
1. `--extra-ldflags` 必须含 `-fPIE`，否则 configure 的链接测试找不到入口失败。
2. FFmpeg envideo 后端会 include `<envideo/classes/nvmisc.h>` 等**内部头**；envideo 的 meson 只安装 `include/envideo.h`。需自建前缀头树 `envideo-prefix/include/envideo/{envideo.h,classes/*.h}`（classes 头从 `src/nvclasses/` 全量复制，14 个），并让 pkg-config 的 `Cflags` 指向它。
3. 组件宏在 `config_components.h`（不在 `config.h`）：`CONFIG_ENVIDEO` 在 config.h，`CONFIG_FILE_PROTOCOL` / `CONFIG_ASF_DEMUXER` / `CONFIG_VC1_DECODER` 在 config_components.h。

## 四、探针工程要点（Makefile）

- 必须嵌入 NACP，否则 Citron 报 `Could not determine title ID`：
  `ifneq ($(APP_TITLEID),) export NACPFLAGS += --titleid=$(APP_TITLEID) endif` +
  `ifeq ($(strip $(NO_NACP)),) export NROFLAGS += --nacp=$(CURDIR)/$(TARGET).nacp endif`
- include 顺序：switch_rules 的 `$(INCLUDE)` 含 `-I$(PORTLIBS)/include`（devkitPro FFmpeg 7.1），
  必须把 `-I$(FFMPEG_SRC) -I$(FFMPEG_BUILD) -I$(ENVIDEO_PREFIX)/include` 放在它**前面**，否则拿到旧 pixfmt.h，
  报 `AV_PIX_FMT_ENVIDEO was not declared`。
- 链接：`$(LIBPATHS)` 里 `-L$(PORTLIBS)` 先于 LIBS，会先命中 devkitPro 的 libav*；改为显式归档路径 + `--start-group`：
  `-Wl,--start-group <ffmpeg-build>/libavformat/libavformat.a .../libavcodec.a .../libavutil.a <envideo>/libenvideo.a -Wl,--end-group -lstdc++ -lnx -lm`
- 不要覆盖 `__nx_heap_size`：libnx 默认堆（application 模式）远大于 128 MiB；强行压到 128 MiB 会让 1080p VC-1
  的 `get_buffer()` 和 GLES 纹理创建 OOM（见 docs/builds/041）。

## 五、FFmpeg 在 horizon 上的两个行为坑

1. `sdmc:/x` 会被 `url_find_protocol()` 当作协议名（`is_dos_path()` 在 horizon 为假）→ `AVERROR_PROTOCOL_NOT_FOUND`
   （-1330794744 = 0x4F5250F8）。探针必须给路径加 `file:` 前缀；`file_open()` 会剥掉。
2. VC-1 解码不传播 pts（`frame->pts == AV_NOPTS_VALUE`）→ 播放 pacing 必须用 **packet pts**。

## 六、探针版本与真机结果

| 探针 | NRO sha256 | 作用 | 结果 |
| --- | --- | --- | --- |
| probe1 `envideo-probe.nro` 272,581 B | `e676728f74d78c7447e6cff428d3c9558c8a84c63f20e2433c6f47d336b220a9` | 只打开 NVDEC/VIC 通道 + 打各 codec constraints | **真机 PASS**：device rc=0；vc1 supported=1 48x16..2032x2032 max_mbs=8192（1920x1080=8160 放得下）；Nvdec/Vic channel rc=0；nv_service_type_used=0（普通 nvdrv，无需 factory） |
| probe2 `envideo-probe2.nro` 3,022,904 B | `829bc1e13b5a44e98926b42256e0739ba179ed64f03fd5fb1bcb577ef86ce4e7` | FFmpeg demux+decode 统计（sw 通路） | Citron PASS：750 包/750 帧解完、DECODE avg 19.50ms；真机待跑 |
| probe3 `nvdec-probe3.nro` 9,408,568 B | `c13b2aaecb19cda40013a661dbf3a27d640f18b7c08c4125fc57473997a804a8` | FFmpeg→(NVDEC)→NV12/YUV→RGBA→SDL2 播放 + 计时 + BMP | Citron PASS：750/750 帧、mode=gles、CONVERT avg 27.78ms；真机待跑（关键看 hw_frames=750 / TRANSFER 耗时） |

probe3 ELF 18,566,512 B sha256 `1bdd2f8c7af0d866deef7575d181bc386a494acb7d52cce362b80764c37f126b`。
