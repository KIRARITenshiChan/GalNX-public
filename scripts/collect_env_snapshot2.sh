#!/usr/bin/env bash
set -uo pipefail
echo '## gcc version (absolute path)'
/opt/devkitpro/devkitA64/bin/aarch64-none-elf-gcc --version | head -2
echo '## dumpmachine'
/opt/devkitpro/devkitA64/bin/aarch64-none-elf-gcc -dumpmachine
echo '## ld version'
/opt/devkitpro/devkitA64/bin/aarch64-none-elf-ld --version | head -2
echo '## nxlink realpath'
which nxlink; command -v nxlink
echo '## pacman count'
pacman -Q | wc -l
echo '## switch-related count'
pacman -Q | grep -Ec 'devkita64|libnx|switch|deko3d|uam|devkit-env|catnip|general-tools'
echo '## devkitpro disk usage'
du -sh /opt/devkitpro 2>/dev/null
echo '## nro metadata (elf2nro header)'
xxd -l 16 '/e/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m0-hello/m0-hello.nro' 2>/dev/null || od -A x -t x1z -v -N 16 '/e/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m0-hello/m0-hello.nro'
echo '## nacp strings'
strings '/e/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m0-hello/m0-hello.nacp' 2>/dev/null | head -5