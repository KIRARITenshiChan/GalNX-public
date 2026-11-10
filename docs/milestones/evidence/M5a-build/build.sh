#!/usr/bin/env bash
set -u
export DEVKITPRO="D:/devkitPro"
export CARGO_HOME=/d/Scoop/persist/rustup/.cargo RUSTUP_HOME=/d/Scoop/persist/rustup/.rustup
export PATH="$CARGO_HOME/bin:$PATH"
export HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897
cd /e/galnx-build/m5-rfvp
START=$(date +%s)
bash platform/switch/build_switch.sh > /e/galnx-build/m5-switch-build.log 2>&1
RC=$?; END=$(date +%s)
echo "BUILD_EXIT=$RC ELAPSED_S=$((END-START))"
tail -4 /e/galnx-build/m5-switch-build.log
echo "--- NRO"
ls -la target/rfvp-switch/switch/ 2>/dev/null
if [ -f target/rfvp-switch/switch/rfvp.nro ]; then sha256sum target/rfvp-switch/switch/rfvp.nro; fi
echo "--- C object magic"
rm -rf /e/galnx-build/m5-objcheck4; mkdir -p /e/galnx-build/m5-objcheck4; cd /e/galnx-build/m5-objcheck4
/d/devkitPro/devkitA64/bin/aarch64-none-elf-ar.exe x /e/galnx-build/m5-rfvp/target/aarch64-nintendo-switch-rfvp/release/librfvp_horizon.a 2>/dev/null || true
f=$(ls *vorbis*.o 2>/dev/null | head -1); if [ -n "$f" ]; then echo "$f magic=$(head -c4 "$f" | od -An -tx1 | tr -d ' \n')"; fi
