#!/usr/bin/env bash
set -u
export DEVKITPRO=/opt/devkitpro
export DEVKITA64=/opt/devkitpro/devkitA64
export PATH=/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin:/opt/devkitpro/portlibs/switch/bin:$PATH
cd /e/galnx-build/m4-ons || exit 9
echo "HEAD=$(git rev-parse HEAD)"
echo "MAKE_VERSION=$(make --version | head -1)"
echo "SDL2_CFLAGS=$(sdl2-config --cflags)"
echo "SMPEG2_CFLAGS=$(smpeg2-config --cflags)"
START=$(date +%s)
make -j16 2>&1
RC=$?
END=$(date +%s)
echo "MAKE_EXIT=$RC"
echo "ELAPSED_S=$((END-START))"
ls -la *.nro *.elf *.nacp 2>/dev/null
exit $RC
