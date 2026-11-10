#!/usr/bin/env bash
set -u
export DEVKITPRO=/opt/devkitpro
echo "BEFORE: $(pacman -Q switch-libvorbis 2>&1)"
pacman -S --needed --noconfirm switch-libvorbis 2>&1 | tail -20
echo "AFTER: $(pacman -Q switch-libvorbis 2>&1)"
ls -la /opt/devkitpro/portlibs/switch/include/vorbis/vorbisfile.h 2>&1
ls -la /opt/devkitpro/portlibs/switch/lib/libvorbis*.a 2>&1
