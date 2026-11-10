#!/usr/bin/env bash
# GalNX M3-a: 从 ELF 构建自包含（未签名）NSP 的离线演示脚本。
#
# 依赖:
#   - devkitPro (elf2nso / npdmtool / nacptool)          默认 $DEVKITPRO 或 /d/devkitPro
#   - hacBrewPack (自源码构建, 见 docs/builds/005-nsp-selfcontained.md)  必需, 无默认路径
#   - nstool (可选): --nstool 给出时自动做结构校验
#
# keys 策略 (硬约束):
#   --keyset 必须显式给出, 本脚本不内置默认路径, 不做任何自动搜索/回退。
#     --keyset /path/to/prod.keys   使用真实 keyset (本机离线构建; 不复制, 不打印内容)
#     --keyset synthetic           内部生成固定假值 keyset, 仅用于离线/CI 冒烟;
#                                  产物结构有效但 NOT INSTALLABLE (真机无法解密 NCA 内容)
#   keyset 只以 --keyset/-k 显式传给 hacBrewPack, 不写环境变量 (DSH 会剔除名字含 KEY 的变量)。
#
# 用法示例:
#   scripts/build_nsp_demo.sh --elf /e/galnx-build/m0-hello/m0-hello.elf \
#       --title-id 0100000000001000 --name m0-hello --author GalNX --version 1.0.0 \
#       --keyset synthetic --hacbrewpack /e/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c/hacbrewpack.exe \
#       --out /e/galnx-build/m3-tools/out --work /e/galnx-build/m3-tools/script-demo

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
NPDM_TEMPLATE="$REPO_ROOT/examples/nsp/npdm.json"

die() { printf "ERROR: %s\n" "$*" >&2; exit 1; }

usage() {
  printf "%s\n" \
    "Usage: build_nsp_demo.sh --elf FILE --title-id HEX16 --name NAME --keyset PATH|synthetic [options]" \
    "" \
    "Required:" \
    "  --elf FILE          ELF (devkitPro 构建产物, 如 /e/galnx-build/m0-hello/m0-hello.elf)" \
    "  --title-id HEX16    16 位小写十六进制 TitleID, 如 0100000000001000" \
    "  --name NAME         应用显示名 (NACP Title Name)" \
    "  --keyset PATH       显式真实 prod.keys 路径, 或字面量 synthetic (假值冒烟)" \
    "" \
    "Options:" \
    "  --author NAME       发布者名 (默认 GalNX)" \
    "  --version VER       版本字符串 (默认 1.0.0)" \
    "  --icon FILE         JPEG 图标, 必须 256x256 (默认 DEVKITPRO/libnx/default_icon.jpg)" \
    "  --romfs DIR         可选 RomFS 内容目录" \
    "  --out DIR           产物目录 (默认 WORK/out)" \
    "  --work DIR          工作目录 (默认 /e/galnx-build/m3-tools/nsp-demo)" \
    "  --hacbrewpack FILE  hacBrewPack 可执行文件 (或用环境变量 GALNX_HACBREWPACK)" \
    "  --nstool FILE       可选 nstool 可执行文件, 给出时对 NSP 做结构校验" \
    "  --devkitpro DIR     devkitPro 根目录 (默认 \$DEVKITPRO 或 /d/devkitPro)" \
    "  -h, --help          显示本帮助"
}

ELF=""
TITLE_ID=""
APP_NAME=""
APP_AUTHOR="GalNX"
APP_VERSION="1.0.0"
ICON=""
ROMFS=""
KEYSET=""
OUT_DIR=""
WORK_DIR="/e/galnx-build/m3-tools/nsp-demo"
HACBREWPACK="${GALNX_HACBREWPACK:-}"
NSTOOL_BIN=""
DKP=""

while [ $# -gt 0 ]; do
  case "$1" in
    --elf) ELF="${2:-}"; shift 2 ;;
    --title-id) TITLE_ID="${2:-}"; shift 2 ;;
    --name) APP_NAME="${2:-}"; shift 2 ;;
    --author) APP_AUTHOR="${2:-}"; shift 2 ;;
    --version) APP_VERSION="${2:-}"; shift 2 ;;
    --icon) ICON="${2:-}"; shift 2 ;;
    --romfs) ROMFS="${2:-}"; shift 2 ;;
    --keyset) KEYSET="${2:-}"; shift 2 ;;
    --out) OUT_DIR="${2:-}"; shift 2 ;;
    --work) WORK_DIR="${2:-}"; shift 2 ;;
    --hacbrewpack) HACBREWPACK="${2:-}"; shift 2 ;;
    --nstool) NSTOOL_BIN="${2:-}"; shift 2 ;;
    --devkitpro) DKP="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (use --help)" ;;
  esac
done

resolve_exe() {
  if [ -x "$1" ]; then printf "%s\n" "$1"; return 0; fi
  if [ -x "$1.exe" ]; then printf "%s\n" "$1.exe"; return 0; fi
  return 1
}

# ---- 参数校验 ----
[ -n "$ELF" ] || die "--elf is required"
[ -f "$ELF" ] || die "ELF not found: $ELF"
[ -n "$APP_NAME" ] || die "--name is required"
[ -n "$KEYSET" ] || die "--keyset is required: pass an explicit prod.keys path or the literal word synthetic"
case "$TITLE_ID" in
  ""|*[!0-9a-f]*) die "--title-id must be 16 lowercase hex chars, got: ${TITLE_ID:-empty}" ;;
esac
[ "${#TITLE_ID}" -eq 16 ] || die "--title-id must be 16 lowercase hex chars (got ${#TITLE_ID})"
[ -f "$NPDM_TEMPLATE" ] || die "NPDM template missing: $NPDM_TEMPLATE"

# ---- devkitPro 定位 ----
if [ -z "$DKP" ]; then
  for cand in "${GALNX_DEVKITPRO:-}" "${DEVKITPRO:-}" /d/devkitPro "D:/devkitPro" /opt/devkitpro; do
    if [ -n "$cand" ] && [ -d "$cand" ]; then DKP="$cand"; break; fi
  done
fi
[ -n "$DKP" ] && [ -d "$DKP" ] || die "devkitPro not found; pass --devkitpro DIR (tried GALNX_DEVKITPRO, DEVKITPRO, /d/devkitPro, D:/devkitPro, /opt/devkitpro)"
DKP_BIN="$DKP/tools/bin"
ELF2NSO="$(resolve_exe "$DKP_BIN/elf2nso")" || die "elf2nso not found under $DKP_BIN"
NPDMTOOL="$(resolve_exe "$DKP_BIN/npdmtool")" || die "npdmtool not found under $DKP_BIN"
NACPTOOL="$(resolve_exe "$DKP_BIN/nacptool")" || die "nacptool not found under $DKP_BIN"
[ -n "$ICON" ] || ICON="$DKP/libnx/default_icon.jpg"
[ -f "$ICON" ] || die "icon not found: $ICON"

# ---- hacBrewPack 定位 (必需, 无默认) ----
[ -n "$HACBREWPACK" ] || die "--hacbrewpack is required (build it from source, see docs/builds/005-nsp-selfcontained.md), or set GALNX_HACBREWPACK"
HACBREWPACK="$(resolve_exe "$HACBREWPACK")" || die "hacBrewPack executable not found: $HACBREWPACK"
if [ -n "$NSTOOL_BIN" ]; then NSTOOL_BIN="$(resolve_exe "$NSTOOL_BIN")" || die "nstool executable not found: $NSTOOL_BIN"; fi

# ---- keyset 解析 (只接受显式参数) ----
KEYSET_MODE=""
mkdir -p "$WORK_DIR" || die "cannot create work dir: $WORK_DIR"
if [ "$KEYSET" = "synthetic" ]; then
  KEYSET_MODE="synthetic"
  KEYPATH="$WORK_DIR/synthetic-test-keyset.dat"
  {
    printf "%s\n" "# SYNTHETIC TEST KEYSET - fabricated values, NOT console keys / NOT prod.keys"
    printf "%s\n" "# Generated by scripts/build_nsp_demo.sh for offline/CI smoke testing only."
    printf "%s\n" "# An NSP built with it is structurally valid but NOT INSTALLABLE (real hardware cannot decrypt NCAs)."
    printf "header_key = %s\n" "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
    printf "key_area_key_application_00 = %s\n" "202122232425262728292a2b2c2d2e2f"
  } > "$KEYPATH" || die "cannot write synthetic keyset"
  printf "WARN: --keyset synthetic -> fabricated keys, NSP is NOT INSTALLABLE (structure-only smoke test)\n" >&2
else
  KEYSET_MODE="real"
  [ -f "$KEYSET" ] || die "keyset file not found: $KEYSET"
  KEYPATH="$KEYSET"
  # 只记录 metadata, 绝不读取内容
  KS_SIZE="$(stat -c %s "$KEYPATH" 2>/dev/null || echo unknown)"
  KS_SHA="$(sha256sum "$KEYPATH" 2>/dev/null | cut -d" " -f1 || echo unknown)"
  KS_MTIME="$(stat -c %y "$KEYPATH" 2>/dev/null || echo unknown)"
  printf "PROVENANCE keyset=%s size=%s sha256=%s mtime=%s\n" "$KEYPATH" "$KS_SIZE" "$KS_SHA" "$KS_MTIME"
fi

# ---- 输入树 ----
EXEFS="$WORK_DIR/exefs"
CONTROL_DIR="$WORK_DIR/control"
ROMFS_DIR="$WORK_DIR/romfs"
rm -rf "$EXEFS" "$CONTROL_DIR" "$ROMFS_DIR" "$WORK_DIR/hacbrewpack_nsp" "$WORK_DIR/hacbrewpack_nca"
mkdir -p "$EXEFS" "$CONTROL_DIR" "$ROMFS_DIR" || die "cannot create input tree under $WORK_DIR"

printf "STEP 1/5 elf2nso -> exefs/main\n"
"$ELF2NSO" "$ELF" "$EXEFS/main" || die "elf2nso failed"
[ -s "$EXEFS/main" ] || die "elf2nso produced empty exefs/main"

printf "STEP 2/5 npdmtool -> exefs/main.npdm (title_id=0x%s)\n" "$TITLE_ID"
sed "s/0x0100000000001000/0x$TITLE_ID/" "$NPDM_TEMPLATE" > "$WORK_DIR/npdm.json" || die "cannot render npdm.json"
"$NPDMTOOL" "$WORK_DIR/npdm.json" "$EXEFS/main.npdm" || die "npdmtool failed"
[ -s "$EXEFS/main.npdm" ] || die "npdmtool produced empty main.npdm"

printf "STEP 3/5 nacptool -> control/control.nacp\n"
"$NACPTOOL" --create "$APP_NAME" "$APP_AUTHOR" "$APP_VERSION" "$CONTROL_DIR/control.nacp" "--titleid=$TITLE_ID" || die "nacptool failed"
cp "$ICON" "$CONTROL_DIR/icon_AmericanEnglish.dat" || die "cannot copy icon"
if [ -n "$ROMFS" ]; then
  [ -d "$ROMFS" ] || die "--romfs is not a directory: $ROMFS"
  cp -R "$ROMFS/." "$ROMFS_DIR/" || die "cannot copy romfs content"
fi

printf "STEP 4/5 hacBrewPack (mode=%s)\n" "$KEYSET_MODE"
RAWLOG="$WORK_DIR/hacbrewpack.raw.log"
LOG="$WORK_DIR/hacbrewpack.log"
( cd "$WORK_DIR" && "$HACBREWPACK" --nologo -k "$KEYPATH" ) > "$RAWLOG" 2>&1
HWRC=$?
grep -v "Key area key" "$RAWLOG" > "$LOG" 2>/dev/null || true
rm -f "$RAWLOG"
if [ "$HWRC" -ne 0 ]; then
  printf "hacBrewPack failed with exit code %s; filtered log:\n" "$HWRC" >&2
  tail -n 20 "$LOG" >&2 || true
  die "hacBrewPack failed (see $LOG)"
fi

BUILT_NSP="$WORK_DIR/hacbrewpack_nsp/$TITLE_ID.nsp"
[ -f "$BUILT_NSP" ] || die "hacBrewPack finished but $BUILT_NSP is missing"
[ -n "$OUT_DIR" ] || OUT_DIR="$WORK_DIR/out"
mkdir -p "$OUT_DIR" || die "cannot create out dir: $OUT_DIR"
SAFE_NAME="$(printf "%s" "$APP_NAME" | tr " " "_")"
OUTFILE="$OUT_DIR/$SAFE_NAME-$TITLE_ID.nsp"
cp "$BUILT_NSP" "$OUTFILE" || die "cannot copy NSP to $OUTFILE"

if [ -n "$NSTOOL_BIN" ]; then
  printf "STEP 5/5 nstool structure check\n"
  "$NSTOOL_BIN" -y -k "$KEYPATH" "$OUTFILE" >> "$LOG" 2>&1
  printf "nstool exit=%s (see %s)\n" "$?" "$LOG"
fi

OUT_SIZE="$(stat -c %s "$OUTFILE")"
OUT_SHA="$(sha256sum "$OUTFILE" | cut -d" " -f1)"
printf "\n===EXIT=0\n"
printf "===ARTIFACTS\n"
printf "%s %s %s\n" "$(basename "$OUTFILE")" "$OUT_SIZE" "$OUT_SHA"
printf "===INPUTS\n"
for f in "$EXEFS/main" "$EXEFS/main.npdm" "$CONTROL_DIR/control.nacp" "$CONTROL_DIR/icon_AmericanEnglish.dat"; do
  [ -f "$f" ] && printf "%s %s %s\n" "$(basename "$f")" "$(stat -c %s "$f")" "$(sha256sum "$f" | cut -d" " -f1)"
done
printf "===LOG\n%s\n" "$LOG"
printf "===LOGTAIL\n"
tail -n 12 "$LOG" || true
