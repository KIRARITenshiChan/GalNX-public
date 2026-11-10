#!/usr/bin/env bash
set -uo pipefail
OUT='/e/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m0-hello/env'
mkdir -p "$OUT"
exec > >(tee "$OUT/raw_env_snapshot.txt") 2>&1
echo "date=$(date -Is)"
echo "uname=$(uname -a)"
echo "## gcc"
aarch64-none-elf-gcc --version | head -3
echo "## ld"
aarch64-none-elf-ld --version | head -2
echo "## make"
make --version | head -2
echo "## nxlink"
nxlink --help | head -20
echo "## pacman -Q (all)"
pacman -Q
echo "## pacman -Q switch/aarch64 related (grep)"
pacman -Q | grep -Ei 'devkita64|libnx|switch|deko3d|uam' || true
echo "## switch-dev group"
pacman -Sg switch-dev || true
echo "## libnx dir"
ls /opt/devkitpro/libnx | head -20
echo "## devkitA64 bin (head)"
ls /opt/devkitpro/devkitA64/bin | head -30
echo "## cached packages sha256"
cd /var/cache/pacman/pkg && sha256sum *.pkg.tar.* 2>/dev/null | head -40
echo "## disk"
df -h /opt/devkitpro /e 2>/dev/null || true