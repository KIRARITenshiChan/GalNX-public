#!/usr/bin/env bash
set -x
cd /e/galnx-build/nvdec/research/envideo || exit 1
pacman -S --noconfirm --needed meson gcc python 2>&1 | tail -15
export PKG_CONFIG_PATH=/opt/devkitpro/portlibs/switch/lib/pkgconfig
meson setup build-switch --crossfile misc/switch-crossfile.txt -Dnvgpu=enabled -Dnvidia=disabled -Dtests=false 2>&1 | tail -40
meson compile -C build-switch 2>&1 | tail -40
ls -l build-switch/*.a 2>/dev/null
