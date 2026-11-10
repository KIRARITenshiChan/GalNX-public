#!/usr/bin/env bash
set -u
export DEVKITPRO=/opt/devkitpro
export PATH=/opt/devkitpro/tools/bin:$PATH
echo "BEFORE: $(pacman -Q switch-smpeg2 2>&1)"
pacman -S --needed --noconfirm switch-smpeg2 2>&1 | tail -30
echo "EXIT=$?"
echo "AFTER: $(pacman -Q switch-smpeg2 2>&1)"
ls -la /opt/devkitpro/portlibs/switch/lib/libsmpeg2.a 2>&1
ls -la /opt/devkitpro/portlibs/switch/bin/smpeg2-config 2>&1
