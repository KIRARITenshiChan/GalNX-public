#!/usr/bin/env bash
# FFmpeg nvtegra branch cross-build, must run inside devkitPro MSYS2 bash
set -e
export DEVKITPRO=/opt/devkitpro
export DEVKITA64=$DEVKITPRO/devkitA64
export PATH=$DEVKITA64/bin:$DEVKITPRO/tools/bin:/usr/bin:/bin
SRC=/e/galnx-build/nvdec/research/ffmpeg-nvtegra
BUILD=/e/galnx-build/nvdec/ffmpeg-build-nvtegra
LOGDIR=/e/galnx-build/nvdec
mkdir -p $BUILD && cd $BUILD
$SRC/configure \
 --target-os=horizon --enable-cross-compile --cross-prefix=aarch64-none-elf- \
 --host-cc="D:/Scoop/apps/mingw/current/bin/gcc.exe" --pkg-config=pkg-config \
 --arch=aarch64 --cpu=cortex-a57 --enable-neon \
 --enable-static --disable-shared --disable-autodetect --disable-runtime-cpudetect \
 --disable-debug --disable-doc --disable-programs --disable-encoders --disable-muxers \
 --disable-devices --disable-network --disable-swresample --disable-filters \
 --disable-everything --enable-gpl --enable-nvtegra \
 --enable-decoder=vc1,h264,wmv3 --enable-parser=vc1,h264 \
 --enable-demuxer=asf,mov --enable-protocol=file \
 --enable-hwaccel=vc1_nvtegra,wmv3_nvtegra \
 --extra-cflags="-D__SWITCH__ -D_GNU_SOURCE -D_POSIX_VERSION=200809L -isystem /opt/devkitpro/libnx/include -O2 -fPIC" \
 --extra-ldflags="-fPIE -specs=/opt/devkitpro/libnx/switch.specs -L/opt/devkitpro/libnx/lib" \
 > $LOGDIR/ffmpeg-nvtegra-configure.log 2>&1 || { echo CONFIGURE_FAILED; tail -40 $LOGDIR/ffmpeg-nvtegra-configure.log; exit 1; }
echo CONFIGURE_OK
grep -E "CONFIG_NVTEGRA=|CONFIG_VC1_NVTEGRA_HWACCEL=|CONFIG_WMV3_NVTEGRA_HWACCEL=|CONFIG_VC1_DECODER=" config.h config_components.h 2>/dev/null | head -8
make -j16 > $LOGDIR/ffmpeg-nvtegra-build.log 2>&1 || { echo BUILD_FAILED; tail -60 $LOGDIR/ffmpeg-nvtegra-build.log; exit 1; }
echo BUILD_OK
ls -l libavcodec/libavcodec.a libavutil/libavutil.a libavformat/libavformat.a