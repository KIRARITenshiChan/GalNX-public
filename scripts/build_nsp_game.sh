#!/usr/bin/env bash
# GalNX P11: 构建"自包含游戏 NSP"（把整个游戏数据根塞进 romfs/game）。
#
# 与 scripts/build_nsp_demo.sh 的差别:
#   * --game-dir 直接把游戏根放到 romfs/game，默认用硬链接 (--romfs-mode hardlink) 暂存，
#     几十 GiB 的游戏数据不复制、不占额外磁盘; 需要给 CI/别的文件系统时可用 copy。
#   * 会跳过游戏根下的存档目录 save/（存档在运行时写 SD 卡，见 rfvp fs.rs）。
#
# 依赖与 keys 策略同 build_nsp_demo.sh（--keyset 必须显式给出, 不内置路径, 不打印内容）。
#
# 用法:
#   scripts/build_nsp_game.sh --elf PATH --game-dir DIR --title-id HEX16 --name NAME \
#       --keyset PATH --hacbrewpack PATH [--icon FILE] [--out DIR] [--work DIR] [--nstool FILE]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
NPDM_TEMPLATE="$REPO_ROOT/examples/nsp/npdm.json"

die() { printf "ERROR: %s\n" "$*" >&2; exit 1; }
usage() {
  printf "%s\n" \
    "Usage: build_nsp_game.sh --elf FILE --game-dir DIR --title-id HEX16 --name NAME --keyset PATH --hacbrewpack FILE [options]" \
    "" \
    "Required:" \
    "  --elf FILE          devkitPro ELF (e.g. rfvp.elf)" \
    "  --game-dir DIR      游戏数据根, 会被放到 romfs/game/" \
    "  --title-id HEX16    16 位小写十六进制 TitleID (base 必须 0x2000 对齐)" \
    "  --name NAME         NACP 显示名" \
    "  --keyset PATH       显式真实 prod.keys 路径 (或字面量 synthetic, 仅结构冒烟)" \
    "  --hacbrewpack FILE  hacBrewPack 可执行文件" \
    "" \
    "Options:" \
    "  --author NAME       默认 GalNX" \
    "  --version VER       默认 1.0.0" \
    "  --icon FILE         JPEG 256x256 (默认 DEVKITPRO/libnx/default_icon.jpg)" \
    "  --romfs-mode MODE   hardlink (默认) | copy" \
    "  --out DIR           产物目录 (默认 WORK/out)" \
    "  --work DIR          工作目录 (默认 /e/galnx-build/nsp-game)" \
    "  --nstool FILE       可选, 给出时做结构校验" \
    "  --devkitpro DIR     devkitPro 根 (默认 ${DEVKITPRO:-} 或 /d/devkitPro)"
}

ELF=""; GAME_DIR=""; TITLE_ID=""; APP_NAME=""; APP_AUTHOR="GalNX"; APP_VERSION="1.0.0"
ICON=""; KEYSET=""; HACBREWPACK="${GALNX_HACBREWPACK:-}"; NSTOOL_BIN=""; DKP=""
ROMFS_MODE="hardlink"; OUT_DIR=""; WORK_DIR="/e/galnx-build/nsp-game"

while [ $# -gt 0 ]; do
  case "$1" in
    --elf) ELF="${2:-}"; shift 2 ;;
    --game-dir) GAME_DIR="${2:-}"; shift 2 ;;
    --title-id) TITLE_ID="${2:-}"; shift 2 ;;
    --name) APP_NAME="${2:-}"; shift 2 ;;
    --author) APP_AUTHOR="${2:-}"; shift 2 ;;
    --version) APP_VERSION="${2:-}"; shift 2 ;;
    --icon) ICON="${2:-}"; shift 2 ;;
    --keyset) KEYSET="${2:-}"; shift 2 ;;
    --hacbrewpack) HACBREWPACK="${2:-}"; shift 2 ;;
    --nstool) NSTOOL_BIN="${2:-}"; shift 2 ;;
    --devkitpro) DKP="${2:-}"; shift 2 ;;
    --romfs-mode) ROMFS_MODE="${2:-}"; shift 2 ;;
    --out) OUT_DIR="${2:-}"; shift 2 ;;
    --work) WORK_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (use --help)" ;;
  esac
done

resolve_exe() {
  if [ -x "$1" ]; then printf "%s\n" "$1"; return 0; fi
  if [ -x "$1.exe" ]; then printf "%s\n" "$1.exe"; return 0; fi
  return 1
}

[ -n "$ELF" ] || die "--elf is required"
[ -f "$ELF" ] || die "ELF not found: $ELF"
[ -n "$GAME_DIR" ] || die "--game-dir is required"
[ -d "$GAME_DIR" ] || die "game dir not found: $GAME_DIR"
[ -n "$APP_NAME" ] || die "--name is required"
[ -n "$KEYSET" ] || die "--keyset is required (explicit prod.keys path or the literal word synthetic)"
case "$TITLE_ID" in
  ""|*[!0-9a-f]*) die "--title-id must be 16 lowercase hex chars, got: ${TITLE_ID:-empty}" ;;
esac
[ "${#TITLE_ID}" -eq 16 ] || die "--title-id must be 16 lowercase hex chars (got ${#TITLE_ID})"
[ -f "$NPDM_TEMPLATE" ] || die "NPDM template missing: $NPDM_TEMPLATE"
case "$ROMFS_MODE" in hardlink|copy) ;; *) die "--romfs-mode must be hardlink or copy" ;; esac

if [ -z "$DKP" ]; then
  for cand in "${GALNX_DEVKITPRO:-}" "${DEVKITPRO:-}" /d/devkitPro "D:/devkitPro" /opt/devkitpro; do
    if [ -n "$cand" ] && [ -d "$cand" ]; then DKP="$cand"; break; fi
  done
fi
[ -n "$DKP" ] && [ -d "$DKP" ] || die "devkitPro not found; pass --devkitpro DIR"
DKP_BIN="$DKP/tools/bin"
ELF2NSO="$(resolve_exe "$DKP_BIN/elf2nso")" || die "elf2nso not found under $DKP_BIN"
NPDMTOOL="$(resolve_exe "$DKP_BIN/npdmtool")" || die "npdmtool not found under $DKP_BIN"
NACPTOOL="$(resolve_exe "$DKP_BIN/nacptool")" || die "nacptool not found under $DKP_BIN"
[ -n "$ICON" ] || ICON="$DKP/libnx/default_icon.jpg"
[ -f "$ICON" ] || die "icon not found: $ICON"
[ -n "$HACBREWPACK" ] || die "--hacbrewpack is required (or set GALNX_HACBREWPACK)"
HACBREWPACK="$(resolve_exe "$HACBREWPACK")" || die "hacBrewPack executable not found: $HACBREWPACK"
if [ -n "$NSTOOL_BIN" ]; then NSTOOL_BIN="$(resolve_exe "$NSTOOL_BIN")" || die "nstool executable not found: $NSTOOL_BIN"; fi

# ---- python 定位 (只在 hardlink 模式下打 romfs 用) ----
PY_BIN="${GALNX_PYTHON:-}"
if [ -z "$PY_BIN" ]; then
  for cand in python3 python py /d/Scoop/shims/python3.exe /c/Users/${USER:-ACETaffy}/scoop/shims/python3.exe; do
    if command -v "$cand" >/dev/null 2>&1; then PY_BIN="$cand"; break; fi
  done
fi
if [ "$ROMFS_MODE" = "hardlink" ] && [ -z "$PY_BIN" ]; then die "python not found for hardlink staging; pass --romfs-mode copy or set GALNX_PYTHON"; fi

mkdir -p "$WORK_DIR" || die "cannot create work dir: $WORK_DIR"
if [ "$KEYSET" = "synthetic" ]; then
  KEYPATH="$WORK_DIR/synthetic-test-keyset.dat"
  {
    printf "%s\n" "# SYNTHETIC TEST KEYSET - fabricated values, NOT console keys"
    printf "header_key = %s\n" "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
    printf "key_area_key_application_00 = %s\n" "202122232425262728292a2b2c2d2e2f"
  } > "$KEYPATH" || die "cannot write synthetic keyset"
  printf "WARN: --keyset synthetic -> fabricated keys, NSP is NOT INSTALLABLE\n" >&2
else
  [ -f "$KEYSET" ] || die "keyset file not found: $KEYSET"
  KEYPATH="$KEYSET"
  KS_SIZE="$(stat -c %s "$KEYPATH" 2>/dev/null || echo unknown)"
  KS_SHA="$(sha256sum "$KEYPATH" 2>/dev/null | cut -d" " -f1 || echo unknown)"
  KS_MTIME="$(stat -c %y "$KEYPATH" 2>/dev/null || echo unknown)"
  printf "PROVENANCE keyset=%s size=%s sha256=%s mtime=%s\n" "$KEYPATH" "$KS_SIZE" "$KS_SHA" "$KS_MTIME"
fi

EXEFS="$WORK_DIR/exefs"
CONTROL_DIR="$WORK_DIR/control"
ROMFS_DIR="$WORK_DIR/romfs"
GAME_DEST="$ROMFS_DIR/game"
rm -rf "$EXEFS" "$CONTROL_DIR" "$ROMFS_DIR" "$WORK_DIR/hacbrewpack_nsp" "$WORK_DIR/hacbrewpack_nca"
mkdir -p "$EXEFS" "$CONTROL_DIR" "$ROMFS_DIR" || die "cannot create input tree under $WORK_DIR"

printf "STEP 1/6 elf2nso -> exefs/main\n"
"$ELF2NSO" "$ELF" "$EXEFS/main" || die "elf2nso failed"
[ -s "$EXEFS/main" ] || die "elf2nso produced empty exefs/main"

printf "STEP 2/6 npdmtool -> exefs/main.npdm (title_id=0x%s)\n" "$TITLE_ID"
sed "s/0x0100000000001000/0x$TITLE_ID/" "$NPDM_TEMPLATE" > "$WORK_DIR/npdm.json" || die "cannot render npdm.json"
"$NPDMTOOL" "$WORK_DIR/npdm.json" "$EXEFS/main.npdm" || die "npdmtool failed"
[ -s "$EXEFS/main.npdm" ] || die "npdmtool produced empty main.npdm"

printf "STEP 3/6 nacptool -> control/control.nacp\n"
"$NACPTOOL" --create "$APP_NAME" "$APP_AUTHOR" "$APP_VERSION" "$CONTROL_DIR/control.nacp" "--titleid=$TITLE_ID" || die "nacptool failed"
cp "$ICON" "$CONTROL_DIR/icon_AmericanEnglish.dat" || die "cannot copy icon"

printf "STEP 4/6 stage romfs/game (mode=%s)\n" "$ROMFS_MODE"
if [ "$ROMFS_MODE" = "hardlink" ]; then
  STAGE_LOG="$WORK_DIR/stage.log"
  # Windows python does not understand MSYS paths (/e/...); hand it native paths.
  PY_SRC="$(cygpath -w "$GAME_DIR")"
  PY_DST="$(cygpath -w "$GAME_DEST")"
  "$PY_BIN" - "$PY_SRC" "$PY_DST" > "$STAGE_LOG" 2>&1 <<PY || { cat "$STAGE_LOG" >&2; die "hardlink staging failed"; }
import os, sys, shutil
src, dst = sys.argv[1], sys.argv[2]
SKIP_TOP = {"save"}
def make(a, b):
    try:
        os.link(a, b)
    except OSError:
        shutil.copy2(a, b)
os.makedirs(dst, exist_ok=True)
linked = copied = 0
for root, dirs, files in os.walk(src, followlinks=True):
    rel = os.path.relpath(root, src)
    if rel == ".":
        dirs[:] = [d for d in dirs if d not in SKIP_TOP]
        out = dst
    else:
        out = os.path.join(dst, rel)
    os.makedirs(out, exist_ok=True)
    for name in files:
        a = os.path.join(root, name)
        b = os.path.join(out, name)
        if os.path.lexists(b):
            continue
        try:
            os.link(a, b)
            linked += 1
        except OSError:
            shutil.copy2(a, b)
            copied += 1
print("romfs/game staged: hardlinked=%d copied=%d" % (linked, copied))
PY
  cat "$STAGE_LOG"
else
  cp -RL "$GAME_DIR/." "$GAME_DEST/" || die "copy staging failed"
  rm -rf "$GAME_DEST/save" || true
fi

printf "STEP 5/6 hacBrewPack\n"
RAWLOG="$WORK_DIR/hacbrewpack.raw.log"
LOG="$WORK_DIR/hacbrewpack.log"
START_TS=$(date +%s)
( cd "$WORK_DIR" && "$HACBREWPACK" --nologo -k "$KEYPATH" ) > "$RAWLOG" 2>&1
HWRC=$?
grep -v "Key area key" "$RAWLOG" > "$LOG" 2>/dev/null || true
rm -f "$RAWLOG"
END_TS=$(date +%s)
if [ "$HWRC" -ne 0 ]; then
  printf "hacBrewPack failed with exit code %s; filtered log:\n" "$HWRC" >&2
  tail -n 30 "$LOG" >&2 || true
  die "hacBrewPack failed (see $LOG)"
fi
printf "hacBrewPack OK in %ss\n" "$((END_TS - START_TS))"

BUILT_NSP="$WORK_DIR/hacbrewpack_nsp/$TITLE_ID.nsp"
[ -f "$BUILT_NSP" ] || die "hacBrewPack finished but $BUILT_NSP is missing"
[ -n "$OUT_DIR" ] || OUT_DIR="$WORK_DIR/out"
mkdir -p "$OUT_DIR" || die "cannot create out dir: $OUT_DIR"
SAFE_NAME="$(printf "%s" "$APP_NAME" | tr " " "_")"
OUTFILE="$OUT_DIR/$SAFE_NAME-$TITLE_ID.nsp"
cp "$BUILT_NSP" "$OUTFILE" || die "cannot copy NSP to $OUTFILE"

if [ -n "$NSTOOL_BIN" ]; then
  printf "STEP 6/6 nstool structure check\n"
  "$NSTOOL_BIN" -y -k "$KEYPATH" "$OUTFILE" >> "$LOG" 2>&1
  printf "nstool exit=%s (see %s)\n" "$?" "$LOG"
fi

ROMFS_BYTES="$(du -sb "$ROMFS_DIR" | cut -f1)"
OUT_SIZE="$(stat -c %s "$OUTFILE")"
OUT_SHA="$(sha256sum "$OUTFILE" | cut -d" " -f1)"
printf "\n===EXIT=0\n"
printf "===ARTIFACTS\n"
printf "%s %s %s\n" "$(basename "$OUTFILE")" "$OUT_SIZE" "$OUT_SHA"
printf "===ROMFS\n"
printf "romfs_bytes=%s game_entries=%s\n" "$ROMFS_BYTES" "$(find "$GAME_DEST" -type f | wc -l)"
printf "===INPUTS\n"
for f in "$EXEFS/main" "$EXEFS/main.npdm" "$CONTROL_DIR/control.nacp" "$CONTROL_DIR/icon_AmericanEnglish.dat"; do
  [ -f "$f" ] && printf "%s %s %s\n" "$(basename "$f")" "$(stat -c %s "$f")" "$(sha256sum "$f" | cut -d" " -f1)"
done
printf "===LOG\n%s\n" "$LOG"
printf "===LOGTAIL\n"
tail -n 15 "$LOG" || true
