#!/usr/bin/env bash
set -u
export DEVKITPRO=/opt/devkitpro
export DEVKITA64=/opt/devkitpro/devkitA64
export PATH=/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin:/opt/devkitpro/portlibs/switch/bin:$PATH
cd /e/galnx-build/m4-ons || exit 9
echo "PWD=$(pwd)"
echo "GCC=$($DEVKITA64/bin/aarch64-none-elf-gcc --version | head -1)"
ls -l romfs
make clean >/dev/null 2>&1
T0=$(date +%s)
make -j16 2>&1
RC=$?
T1=$(date +%s)
echo "MAKE_EXIT=$RC"
echo "ELAPSED_S=$((T1-T0))"
ls -l m4-ons.nro m4-ons.elf m4-ons.nacp 2>&1
sha256sum m4-ons.nro m4-ons.elf m4-ons.nacp 2>&1
exit $RC
