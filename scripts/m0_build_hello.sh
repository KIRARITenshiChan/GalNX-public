#!/usr/bin/env bash
# M0 toolchain validation: build the devkitPro application template (hello world NRO).
# Usage: env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '"$0"' <this script>
# IMPORTANT: devkitPro make-based projects break when the project path contains spaces
#   (switch_rules does `$(MAKE) -C $(BUILD) -f $(CURDIR)/Makefile` unquoted).
#   Therefore we build in the space-free dir /e/galnx-build and archive results into the Workspace.
set -uo pipefail
BUILD=/e/galnx-build/m0-hello
TRACE='/e/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/m0-hello'
SRC=/opt/devkitpro/examples/switch/templates/application
rm -rf "$BUILD" "$TRACE"
mkdir -p "$BUILD" "$TRACE"
cp -r "$SRC"/. "$BUILD"/
cd "$BUILD" || { echo 'cd failed'; exit 2; }
LOG="$TRACE/build.log"
{ echo "date=$(date -Is)"; echo "uname=$(uname -a)"; echo "DEVKITPRO=${DEVKITPRO:-<unset>}"; echo "MSYSTEM=${MSYSTEM:-<unset>}"; echo "build_dir=$BUILD"; echo "trace_dir=$TRACE"; } > "$LOG"
make -j4 >> "$LOG" 2>&1
rc=$?
echo "make_exit=$rc" >> "$LOG"
# archive sources + artifacts into the Workspace trace dir
cp -r "$BUILD"/Makefile "$BUILD"/source "$TRACE" 2>/dev/null
find "$BUILD" -maxdepth 1 -type f \( -name '*.nro' -o -name '*.elf' -o -name '*.nacp' -o -name '*.nso' \) -exec cp {} "$TRACE"/ \;
echo "===EXIT=$rc"
echo '===BUILD_FILES'; ls -l "$BUILD" | head -20
echo '===TRACE_FILES'; ls -l "$TRACE" | head -20
echo '===ARTIFACTS'
for f in "$BUILD"/*.nro "$BUILD"/*.elf "$BUILD"/*.nacp; do [ -f "$f" ] && echo "$(basename "$f") size=$(stat -c %s "$f") sha256=$(sha256sum "$f" | cut -d' ' -f1)"; done
echo '===LOGTAIL'; tail -n 25 "$LOG"