#!/usr/bin/env bash
# GalNX P1-d: build a self-contained (unsigned) NSP from a prebuilt NRO or a rebuilt ELF.
#
# Input forms:
#   --nro FILE   prebuilt NRO (NRO0 @0x10 + ASET assets + optional embedded RomFS).
#                The script turns NRO segments into a synthetic ELF (keeping the NRO
#                BuildId), extracts ASET assets (icon / control.nacp) and, when an
#                embedded RomFS is present, unpacks it into a directory that is then
#                re-packed as the NSP RomFS. Then: elf2nso -> npdmtool -> hacBrewPack.
#   --elf FILE   rebuilt ELF (future P1-b artifact) with optional --npdm/--nacp/
#                --icon/--romfs-dir; goes through the same packaging chain.
#
# Dependencies:
#   - devkitPro: elf2nso / npdmtool / nacptool  (--devkitpro or DEVKITPRO or /d/devkitPro)
#   - hacBrewPack executable (required, no default path; --hacbrewpack or GALNX_HACBREWPACK)
#   - python (PATH; only for NRO parsing/asset extraction, no third-party packages)
#   - nstool (optional): --nstool enables structural verification
#
# keys policy (hard constraints, same as scripts/build_nsp_demo.sh):
#   --keyset is mandatory and explicit; this script has no default keyset path and
#   performs no automatic search/fallback.
#     --keyset /path/to/prod.keys   real keyset, local offline build (only metadata is
#                                   recorded: path/size/sha256/mtime; contents never read)
#     --keyset synthetic            internally generated fixed fake values; offline/CI
#                                   smoke only, NOT INSTALLABLE on real hardware
#   The keyset is only passed to hacBrewPack via -k; no environment variables are used
#   (DSH strips variables whose names contain KEY). hacBrewPack prints a derived
#   "Key area key N: ..." line which is filtered out before the log is written.
#
# Output: default E:/galnx-build/pilot-01/out/ (never committed; only this script and
#         docs/pilot/P1-nsp-packaging.md are stored in the repository).
#
# In-place modification warning (hard requirement): hacBrewPack rewrites the staging
# copies of exefs/main.npdm and control/control.nacp in place (their SHA-256 changes
# after a build). ALWAYS re-stage fresh copies from the inputs for every build; never
# reuse the staging directory of a previous run (this script rebuilds it with rm -rf).
#
# Determinism: the NSP SHA-256 differs between two builds of identical inputs because
# hacBrewPack signs NCAs with RSA-PSS and a random salt. Lock versions with component
# hashes (exefs/main, main.npdm, control.nacp, RomFS payload), not with the NSP hash.
#
# Examples:
#   scripts/build_pilot_nsp.sh --nro "E:/.../Kirikiroid2-NX-v1.0.1.nro" \
#       --title-id 010047410000b0b1 --name "Kirikiroid2-NX" \
#       --hacbrewpack E:/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c/hacbrewpack.exe \
#       --nstool E:/galnx-build/m3-tools/nstool.exe \
#       --keyset "E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys" \
#       --out E:/galnx-build/pilot-01/out --work E:/galnx-build/pilot-01/build/k2nx

set -o pipefail
set +u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
NPDM_TEMPLATE="$REPO_ROOT/examples/nsp/npdm.json"

die() { printf "ERROR: %s\n" "$*" >&2; exit 1; }

usage() {
  printf "%s\n" \
    "Usage: build_pilot_nsp.sh --nro FILE | --elf FILE [options]" \
    "" \
    "Input (one required):" \
    "  --nro FILE          prebuilt NRO (NRO0 @0x10; ASET assets; optional embedded RomFS)" \
    "  --elf FILE          rebuilt ELF (devkitPro)" \
    "" \
    "Required:" \
    "  --title-id HEX16    16 lowercase hex chars, e.g. 010047410000b0b1" \
    "  --keyset PATH        explicit real prod.keys path, or the literal word synthetic" \
    "  --hacbrewpack FILE  hacBrewPack executable (or env GALNX_HACBREWPACK)" \
    "" \
    "Options:" \
    "  --name NAME         display name (default: NRO/ELF file stem)" \
    "  --author NAME       publisher for nacptool fallback (default GalNX)" \
    "  --version VER       version for nacptool fallback (default 1.0.0)" \
    "  --npdm FILE         prebuilt NPDM (default: npdmtool from examples/nsp/npdm.json)" \
    "  --nacp FILE         prebuilt control.nacp (default: NRO embedded NACP, else nacptool)" \
    "  --icon FILE         JPEG icon 256x256 (default: NRO embedded icon, else devkitPro default)" \
    "  --romfs-dir DIR     RomFS content directory (default: extracted NRO embedded RomFS; else empty)" \
    "  --no-romfs          force an empty RomFS (do not extract NRO embedded RomFS)" \
    "  --zero-nro-header   zero the 0x70-byte NRO header slot inside .text (default: keep)" \
    "  --out DIR           output dir (default /e/galnx-build/pilot-01/out)" \
    "  --work DIR          work dir   (default /e/galnx-build/pilot-01/build)" \
    "  --nstool FILE       optional nstool executable for structure verification" \
    "  --devkitpro DIR     devkitPro root (default GALNX_DEVKITPRO / DEVKITPRO / /d/devkitPro)" \
    "  -h, --help          show this help"
}

NRO=""
ELF=""
TITLE_ID=""
APP_NAME=""
APP_AUTHOR="GalNX"
APP_VERSION="1.0.0"
NPDM=""
NACP=""
ICON=""
ROMFS_DIR=""
NO_ROMFS=0
ZERO_NRO_HEADER=0
KEYSET=""
OUT_DIR="/e/galnx-build/pilot-01/out"
WORK_DIR="/e/galnx-build/pilot-01/build"
HACBREWPACK=""
NSTOOL_BIN=""
DKP=""

if [ -n "$GALNX_HACBREWPACK" ]; then HACBREWPACK="$GALNX_HACBREWPACK"; fi
DKP=""
for cand in "$GALNX_DEVKITPRO" "$DEVKITPRO" /d/devkitPro "D:/devkitPro" /opt/devkitpro; do
  if [ -n "$cand" ] && [ -d "$cand" ]; then DKP="$cand"; break; fi
done

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
  esac
  if [ $# -lt 2 ]; then die "missing value for $1 (use --help)"; fi
  case "$1" in
    --nro) NRO="$2"; shift 2 ;;
    --elf) ELF="$2"; shift 2 ;;
    --title-id) TITLE_ID="$2"; shift 2 ;;
    --name) APP_NAME="$2"; shift 2 ;;
    --author) APP_AUTHOR="$2"; shift 2 ;;
    --version) APP_VERSION="$2"; shift 2 ;;
    --npdm) NPDM="$2"; shift 2 ;;
    --nacp) NACP="$2"; shift 2 ;;
    --icon) ICON="$2"; shift 2 ;;
    --romfs-dir) ROMFS_DIR="$2"; shift 2 ;;
    --keyset) KEYSET="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --work) WORK_DIR="$2"; shift 2 ;;
    --hacbrewpack) HACBREWPACK="$2"; shift 2 ;;
    --nstool) NSTOOL_BIN="$2"; shift 2 ;;
    --devkitpro) DKP="$2"; shift 2 ;;
    *) die "unknown argument: $1 (use --help)" ;;
  esac
done
set -u

resolve_exe() {
  if [ -x "$1" ]; then printf "%s\n" "$1"; return 0; fi
  if [ -x "$1.exe" ]; then printf "%s\n" "$1.exe"; return 0; fi
  return 1
}
need_file() { [ -f "$1" ] || die "$2 not found: $1"; }

# ---- argument validation ----
if [ -z "$NRO" ] && [ -z "$ELF" ]; then die "one of --nro or --elf is required"; fi
if [ -n "$NRO" ] && [ -n "$ELF" ]; then die "--nro and --elf are mutually exclusive"; fi
if [ -n "$NRO" ]; then need_file "$NRO" "NRO"; fi
if [ -n "$ELF" ]; then need_file "$ELF" "ELF"; fi
if [ -z "$KEYSET" ]; then die "--keyset is required: pass an explicit prod.keys path or the literal word synthetic"; fi
case "$TITLE_ID" in
  ""|*[!0-9a-f]*) die "--title-id must be 16 lowercase hex chars, got: $TITLE_ID" ;;
esac
TID_LEN="$(printf "%s" "$TITLE_ID" | wc -c | tr -d " ")"
if [ "$TID_LEN" -ne 16 ]; then die "--title-id must be 16 lowercase hex chars (got $TID_LEN)"; fi
if [ -n "$NPDM" ]; then need_file "$NPDM" "NPDM"; fi
if [ -n "$NACP" ]; then need_file "$NACP" "NACP"; fi
if [ -n "$ICON" ]; then need_file "$ICON" "icon"; fi
if [ -n "$ROMFS_DIR" ] && [ ! -d "$ROMFS_DIR" ]; then die "--romfs-dir is not a directory: $ROMFS_DIR"; fi
need_file "$NPDM_TEMPLATE" "NPDM template"
PYTHON="$(command -v python3 || command -v python)" || die "python3/python not found in PATH"

# ---- locators ----
if [ -z "$DKP" ]; then
  for cand in /d/devkitPro "D:/devkitPro" /opt/devkitpro; do
    if [ -d "$cand" ]; then DKP="$cand"; break; fi
  done
fi
if [ -z "$DKP" ] || [ ! -d "$DKP" ]; then die "devkitPro not found; pass --devkitpro DIR"; fi
DKP_BIN="$DKP/tools/bin"
ELF2NSO="$(resolve_exe "$DKP_BIN/elf2nso")" || die "elf2nso not found under $DKP_BIN"
NPDMTOOL="$(resolve_exe "$DKP_BIN/npdmtool")" || die "npdmtool not found under $DKP_BIN"
NACPTOOL="$(resolve_exe "$DKP_BIN/nacptool")" || die "nacptool not found under $DKP_BIN"
LIB_DEFAULT_ICON="$DKP/libnx/default_icon.jpg"

if [ -z "$HACBREWPACK" ]; then die "--hacbrewpack is required (or set GALNX_HACBREWPACK)"; fi
HACBREWPACK="$(resolve_exe "$HACBREWPACK")" || die "hacBrewPack executable not found: $HACBREWPACK"
if [ -n "$NSTOOL_BIN" ]; then NSTOOL_BIN="$(resolve_exe "$NSTOOL_BIN")" || die "nstool executable not found: $NSTOOL_BIN"; fi

# ---- keyset resolution (explicit only) ----
KEYSET_MODE=""
mkdir -p "$WORK_DIR" || die "cannot create work dir: $WORK_DIR"
if [ "$KEYSET" = "synthetic" ]; then
  KEYSET_MODE="synthetic"
  KEYPATH="$WORK_DIR/synthetic-test-keyset.dat"
  {
    printf "%s\n" "# SYNTHETIC TEST KEYSET - fabricated values, NOT console keys / NOT prod.keys"
    printf "%s\n" "# Generated by scripts/build_pilot_nsp.sh for offline/CI smoke testing only."
    printf "%s\n" "# An NSP built with it is structurally valid but NOT INSTALLABLE (real hardware cannot decrypt NCAs)."
    printf "header_key = %s\n" "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
    printf "key_area_key_application_00 = %s\n" "202122232425262728292a2b2c2d2e2f"
  } > "$KEYPATH" || die "cannot write synthetic keyset"
  printf "WARN: --keyset synthetic -> fabricated keys, NSP is NOT INSTALLABLE (structure-only smoke test)\n" >&2
else
  KEYSET_MODE="real"
  need_file "$KEYSET" "keyset file"
  KEYPATH="$KEYSET"
  KS_SIZE="$(stat -c %s "$KEYPATH" 2>/dev/null || echo unknown)"
  KS_SHA="$(sha256sum "$KEYPATH" 2>/dev/null | cut -d" " -f1 || echo unknown)"
  KS_MTIME="$(stat -c %y "$KEYPATH" 2>/dev/null || echo unknown)"
  printf "PROVENANCE keyset=%s size=%s sha256=%s mtime=%s\n" "$KEYPATH" "$KS_SIZE" "$KS_SHA" "$KS_MTIME"
fi

# ---- staging tree ----
EXEFS="$WORK_DIR/exefs"
CONTROL_DIR="$WORK_DIR/control"
STAGE_ROMFS="$WORK_DIR/romfs"
INPUT_DIR="$WORK_DIR/in"
META="$WORK_DIR/input-meta.txt"
rm -rf "$EXEFS" "$CONTROL_DIR" "$STAGE_ROMFS" "$INPUT_DIR" "$WORK_DIR/hacbrewpack_nsp" "$WORK_DIR/hacbrewpack_nca"
mkdir -p "$EXEFS" "$CONTROL_DIR" "$STAGE_ROMFS" "$INPUT_DIR" || die "cannot create input tree under $WORK_DIR"
: > "$META"

# ---- path helper: convert msys style /e/... to native Windows E:/... ----
winpath() {
  printf "%s" "$1" | sed -e "s#^/e/#E:/#" -e "s#^/d/#D:/#" -e "s#^/c/#C:/#"
}
EXEFS_W="$(winpath "$EXEFS")"
CONTROL_W="$(winpath "$CONTROL_DIR")"
STAGE_ROMFS_W="$(winpath "$STAGE_ROMFS")"
WORK_W="$(winpath "$WORK_DIR")"
INPUT_W="$(winpath "$INPUT_DIR")"
META_W="$(winpath "$META")"
OUT_W="$(winpath "$OUT_DIR")"
mkdir -p "$OUT_DIR" || die "cannot create output dir: $OUT_DIR"

# ---- STEP 1: exefs/main (NRO/ELF -> NSO) ----
printf "\n== STEP 1: exefs/main\n"
ELF_PATH=""
EXTRACTED_ICON=""
EXTRACTED_NACP=""
EXTRACTED_ROMFS_DIR=""
UNPACK_EMBEDDED=1
if [ -n "$ROMFS_DIR" ] || [ "$NO_ROMFS" -eq 1 ]; then UNPACK_EMBEDDED=0; fi

if [ -n "$NRO" ]; then
  "$PYTHON" - "$(winpath "$NRO")" "$WORK_W" "$INPUT_W" "$META_W" "$ZERO_NRO_HEADER" "$UNPACK_EMBEDDED" <<'PY'
import hashlib
import os
import struct
import sys

nro_path, work, input_dir, meta_path, zero_hdr, unpack_embedded = sys.argv[1:7]
zero_hdr = zero_hdr == "1"
unpack_embedded = unpack_embedded == "1"
work = work.rstrip("/")
input_dir = input_dir.rstrip("/")

raw = open(nro_path, "rb").read()
if len(raw) < 0x80 or raw[0x10:0x14] != b"NRO0":
    sys.exit("not an NRO (missing NRO0 magic at 0x10): " + nro_path)
version, nro_size, flags = struct.unpack_from("<III", raw, 0x14)
segs = [struct.unpack_from("<II", raw, 0x20 + i * 8) for i in range(3)]
bss, unk3 = struct.unpack_from("<II", raw, 0x38)
build_id = raw[0x40:0x60]
for i, (fo, sz) in enumerate(segs):
    if fo + sz > len(raw):
        sys.exit("segment %d outside file: off %#x size %#x (file %#x)" % (i, fo, sz, len(raw)))

# ---- synthetic ELF (mirrors /e/galnx-build/pilot-01/nro2elf.py, verified) ----
PHOFF, PHNUM = 0x40, 3
EHDR_SIZE, PHDR_SIZE = 0x40, 56
DATA_START = 0x1000
EM_AARCH64 = 183
PT_LOAD, PT_NOTE = 1, 4
PF_R, PF_W, PF_X = 4, 2, 1
offsets = []
blobs = []
cur = DATA_START
for i, (fo, sz) in enumerate(segs):
    data = bytearray(raw[fo:fo + sz])
    if zero_hdr and i == 0 and len(data) >= 0x80:
        data[0x10:0x80] = b"\x00" * 0x70
    offsets.append(cur)
    blobs.append(bytes(data))
    cur += sz
note = struct.pack("<III", 4, 32, 3) + b"GNU\x00" + build_id
note_off = cur
shoff = note_off + len(note)
e_ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
ehdr = e_ident + struct.pack("<HHIQQQIHHHHHH", 2, EM_AARCH64, 1, 0, PHOFF, shoff, 0,
                             EHDR_SIZE, PHDR_SIZE, PHNUM, 64, 2, 0)
assert len(ehdr) == EHDR_SIZE
phdrs = b""
flags_by_idx = [PF_R | PF_X, PF_R, PF_R | PF_W]
for i, (fo, sz) in enumerate(segs):
    memsz = sz + (bss if i == 2 else 0)
    phdrs += struct.pack("<IIQQQQQQ", PT_LOAD, flags_by_idx[i], offsets[i], fo, fo, sz, memsz, 0x1000)
note_phdr = struct.pack("<IIQQQQQQ", PT_NOTE, PF_R, note_off, 0, 0, len(note), len(note), 4)
pad_len = DATA_START - (EHDR_SIZE + len(phdrs) + len(note_phdr))
if pad_len < 0:
    sys.exit("program headers do not fit before 0x1000: %d" % pad_len)
sh_null = bytes(64)
sh_note = struct.pack("<IIQQQQIIQQ", 0, 7, 0, 0, note_off, len(note), 0, 0, 4, 0)
out = ehdr + phdrs + note_phdr + b"\x00" * pad_len + b"".join(blobs) + note + sh_null + sh_note
assert len(out) == shoff + 128
elf_path = work + "/synthetic.elf"
open(elf_path, "wb").write(out)

meta = []
meta.append("NRO_PATH=" + nro_path.replace("\\", "/"))
meta.append("NRO_FILE_SIZE=%d" % len(raw))
meta.append("NRO_HDR_VERSION=%d" % version)
meta.append("NRO_HDR_SIZE=%d" % nro_size)
meta.append("NRO_FLAGS=%d" % flags)
meta.append("NRO_BSS_SIZE=%d" % bss)
meta.append("NRO_BUILD_ID=" + build_id.hex())
meta.append("NRO_TEXT_SIZE=%d" % segs[0][1])
meta.append("NRO_RODATA_SIZE=%d" % segs[1][1])
meta.append("NRO_DATA_SIZE=%d" % segs[2][1])
meta.append("SYNTH_ELF=" + elf_path)
meta.append("SYNTH_ELF_SIZE=%d" % len(out))

# ---- ASET assets (absolute offset == NroHeader.size) ----
icon_path = ""
nacp_path = ""
romfs_dir = ""
romfs_files = 0
romfs_bytes = 0
if nro_size + 8 <= len(raw) and raw[nro_size:nro_size + 4] == b"ASET":
    aver = struct.unpack_from("<I", raw, nro_size + 4)[0]
    meta.append("ASET_VERSION=%d" % aver)
    meta.append("ASET_ABS=%d" % nro_size)

    def section(idx):
        off, sz = struct.unpack_from("<QQ", raw, nro_size + 8 + idx * 16)
        return off, sz

    for idx, key in ((0, "ICON"), (1, "NACP"), (2, "ROMFS")):
        off, sz = section(idx)
        meta.append("ASET_%s_OFFSET=%d" % (key, off))
        meta.append("ASET_%s_ABS=%d" % (key, nro_size + off if sz else 0))
        meta.append("ASET_%s_SIZE=%d" % (key, sz))
    ioff, isz = section(0)
    if isz:
        icon_path = input_dir + "/icon.jpg"
        blob = raw[nro_size + ioff:nro_size + ioff + isz]
        open(icon_path, "wb").write(blob)
        meta.append("ASET_ICON_FILE=" + icon_path)
        meta.append("ASET_ICON_SHA256=" + hashlib.sha256(blob).hexdigest())
        print("extracted icon: %s (%d bytes, sha256 %s)" % (icon_path, len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    noff, nsz = section(1)
    if nsz:
        nacp_path = input_dir + "/control.nacp"
        blob = raw[nro_size + noff:nro_size + noff + nsz]
        open(nacp_path, "wb").write(blob)
        meta.append("ASET_NACP_FILE=" + nacp_path)
        meta.append("ASET_NACP_SHA256=" + hashlib.sha256(blob).hexdigest())
        print("extracted control.nacp: %s (%d bytes, sha256 %s)" % (nacp_path, len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    roff, rsz = section(2)
    if rsz:
        meta.append("ROMFS_EMBEDDED_SIZE=%d" % rsz)
        if unpack_embedded:
            romfs_dir = input_dir + "/extracted-romfs"
            os.makedirs(romfs_dir, exist_ok=True)
            (header_size, dir_hash_off, dir_hash_size, dir_meta_off, dir_meta_size,
             file_hash_off, file_hash_size, file_meta_off, file_meta_size, data_off) = struct.unpack_from("<10Q", raw, nro_size + roff)
            SENT = 0xFFFFFFFF

            def dir_entry(rel):
                o = nro_size + roff + dir_meta_off + rel
                parent, sibling, child, f, hashv, nl = struct.unpack_from("<6I", raw, o)
                name = raw[o + 24:o + 24 + nl].decode("utf-8", "replace")
                return parent, sibling, child, f, name

            def file_entry(rel):
                o = nro_size + roff + file_meta_off + rel
                parent, sibling, doff, dsize, hashv, nl = struct.unpack_from("<IIQQII", raw, o)
                name = raw[o + 32:o + 32 + nl].decode("utf-8", "replace")
                return parent, sibling, doff, dsize, name

            bad = set("<>:\"|?*")
            def safe(name):
                out_chars = []
                for ch in name:
                    out_chars.append("_" if (ch in bad or ord(ch) < 32) else ch)
                s = "".join(out_chars).rstrip(" .")
                if s in ("", ".", ".."):
                    s = "_" + s
                return s

            root = dir_entry(0)
            stack = [(root[2], ())]
            seen_dirs = set()
            found = []
            # The root directory's own file chain (root[3]) is not reachable by
            # walking the child directory chain, so seed it explicitly; without
            # this every root-level file (e.g. DroidSansFallback.ttf) is dropped.
            root_file = root[3]
            while root_file != 0xFFFFFFFF:
                fparent, fsibling, fdoff, fsize, fname = file_entry(root_file)
                found.append(((), fdoff, fsize, fname))
                root_file = fsibling
            while stack:
                rel, prefix = stack.pop()
                while rel != SENT:
                    if rel in seen_dirs:
                        break
                    seen_dirs.add(rel)
                    parent, sibling, child, f, dname = dir_entry(rel)
                    frel = f
                    seen_files = set()
                    while frel != SENT:
                        if frel in seen_files:
                            break
                        seen_files.add(frel)
                        fparent, fsibling, fdoff, fsize, fname = file_entry(frel)
                        parts = prefix + ((dname,) if dname else ())
                        found.append((parts, fdoff, fsize, fname))
                        frel = fsibling
                    if child != SENT:
                        stack.append((child, prefix + ((dname,) if dname else ())))
                    rel = sibling
            used = set()
            for parts, fdoff, fsize, fname in sorted(found, key=lambda item: "/".join(item[0] + (item[3],))):
                if data_off + fdoff + fsize > rsz:
                    print("WARN: romfs file outside image skipped: %r" % (parts + (fname,),))
                    continue
                dir_parts = [safe(p) for p in parts]
                target_dir = os.path.join(romfs_dir, *dir_parts) if dir_parts else romfs_dir
                os.makedirs(target_dir, exist_ok=True)
                base = safe(fname)
                candidate = os.path.join(target_dir, base)
                n = 2
                while candidate.lower() in used:
                    candidate = os.path.join(target_dir, base + "_" + str(n))
                    n += 1
                used.add(candidate.lower())
                blob = raw[nro_size + roff + data_off + fdoff:nro_size + roff + data_off + fdoff + fsize]
                open(candidate, "wb").write(blob)
                romfs_files += 1
                romfs_bytes += fsize
            meta.append("ROMFS_EMBEDDED_DIR=" + romfs_dir)
            meta.append("ROMFS_EMBEDDED_FILES=%d" % romfs_files)
            meta.append("ROMFS_EMBEDDED_BYTES=%d" % romfs_bytes)
            print("extracted embedded romfs: %s (%d files, %d payload bytes of %d image bytes)" % (romfs_dir, romfs_files, romfs_bytes, rsz))
    else:
        meta.append("ROMFS_EMBEDDED_SIZE=0")
else:
    meta.append("ASET_VERSION=-1")
    print("NO ASET found in NRO (no embedded icon/nacp/romfs)")

meta.append("EXTRACTED_ICON=" + icon_path)
meta.append("EXTRACTED_NACP=" + nacp_path)
meta.append("EXTRACTED_ROMFS_DIR=" + romfs_dir)
open(meta_path, "w", encoding="utf-8").write("\n".join(meta) + "\n")
print("nro: %s (%d bytes, hdr size %d, build id %s)" % (nro_path, len(raw), nro_size, build_id.hex()[:32]))
print("synthetic ELF: %s (%d bytes)" % (elf_path, len(out)))
PY
  [ "$?" -eq 0 ] || die "NRO parsing/ELF synthesis failed"
  ELF_PATH="$(sed -n "s/^SYNTH_ELF=//p" "$META")"
  EXTRACTED_ICON="$(sed -n "s/^EXTRACTED_ICON=//p" "$META")"
  EXTRACTED_NACP="$(sed -n "s/^EXTRACTED_NACP=//p" "$META")"
  EXTRACTED_ROMFS_DIR="$(sed -n "s/^EXTRACTED_ROMFS_DIR=//p" "$META")"
  [ -n "$ELF_PATH" ] || die "NRO conversion did not produce an ELF (see log)"
  [ -f "$ELF_PATH" ] || die "synthetic ELF missing: $ELF_PATH"
  printf "nro summary:\n"
  sed -n -e "s/^/  /p" "$META" | head -n 20
else
  ELF_PATH="$(winpath "$ELF")"
  printf "rebuilt ELF input: %s (%s bytes)\n" "$ELF_PATH" "$(stat -c %s "$ELF_PATH")"
fi

"$ELF2NSO" "$ELF_PATH" "$EXEFS_W/main" || die "elf2nso failed"
[ -f "$EXEFS/main" ] || die "elf2nso did not write $EXEFS/main"
printf "exefs/main: %s bytes sha256=%s\n" "$(stat -c %s "$EXEFS/main")" "$(sha256sum "$EXEFS/main" | cut -d" " -f1)"

# ---- STEP 2: main.npdm ----
printf "\n== STEP 2: main.npdm\n"
if [ -n "$NPDM" ]; then
  cp -f "$(winpath "$NPDM")" "$EXEFS_W/main.npdm" || die "cannot copy NPDM"
  printf "npdm: provided %s\n" "$NPDM"
else
  NPDM_JSON="$WORK_DIR/npdm.json"
  sed -e "s/0100000000001000/$TITLE_ID/g" "$NPDM_TEMPLATE" > "$NPDM_JSON" || die "cannot render npdm.json"
  grep -q "0x$TITLE_ID" "$NPDM_JSON" || die "npdm.json does not contain the requested title id"
  "$NPDMTOOL" "$(winpath "$NPDM_JSON")" "$EXEFS_W/main.npdm" || die "npdmtool failed"
  printf "npdm: generated from examples/nsp/npdm.json (title_id 0x%s)\n" "$TITLE_ID"
fi
[ -f "$EXEFS/main.npdm" ] || die "NPDM missing: $EXEFS/main.npdm"
printf "exefs/main.npdm: %s bytes sha256=%s\n" "$(stat -c %s "$EXEFS/main.npdm")" "$(sha256sum "$EXEFS/main.npdm" | cut -d" " -f1)"

# ---- STEP 3: control/control.nacp + icon ----
printf "\n== STEP 3: control NACP and icon\n"
NACP_SOURCE=""
if [ -n "$NACP" ]; then
  cp -f "$(winpath "$NACP")" "$CONTROL_W/control.nacp" || die "cannot copy NACP"
  NACP_SOURCE="provided: $NACP"
elif [ -n "$EXTRACTED_NACP" ] && [ -f "$EXTRACTED_NACP" ]; then
  cp -f "$EXTRACTED_NACP" "$CONTROL_W/control.nacp" || die "cannot copy extracted NACP"
  NACP_SOURCE="extracted from NRO: $EXTRACTED_NACP"
else
  "$NACPTOOL" --create "$APP_NAME" "$APP_AUTHOR" "$APP_VERSION" "$CONTROL_W/control.nacp" --titleid="$TITLE_ID" || die "nacptool failed"
  NACP_SOURCE="nacptool (name=$APP_NAME author=$APP_AUTHOR version=$APP_VERSION)"
fi
[ -f "$CONTROL_W/control.nacp" ] || die "control.nacp missing"
printf "control.nacp: %s bytes sha256=%s (%s)\n" "$(stat -c %s "$CONTROL_W/control.nacp")" "$(sha256sum "$CONTROL_W/control.nacp" | cut -d" " -f1)" "$NACP_SOURCE"

ICON_SOURCE=""
if [ -n "$ICON" ]; then
  ICON_SOURCE="$(winpath "$ICON")"
  printf "icon: provided %s\n" "$ICON"
elif [ -n "$EXTRACTED_ICON" ] && [ -f "$EXTRACTED_ICON" ]; then
  ICON_SOURCE="$EXTRACTED_ICON"
  printf "icon: extracted from NRO %s\n" "$EXTRACTED_ICON"
else
  ICON_SOURCE="$(winpath "$LIB_DEFAULT_ICON")"
  printf "icon: devkitPro default %s\n" "$LIB_DEFAULT_ICON"
fi
[ -f "$ICON_SOURCE" ] || die "icon not found: $ICON_SOURCE"
"$PYTHON" - "$ICON_SOURCE" <<'PY'
import sys
try:
    from PIL import Image
except ImportError:
    sys.exit("PIL is required to validate the icon (pip: Pillow)")
im = Image.open(sys.argv[1])
im.load()
print("icon check: format=%s size=%s mode=%s" % (im.format, im.size, im.mode))
if im.format != "JPEG" or im.size != (256, 256):
    sys.exit("icon must be a 256x256 JPEG, got %s %s" % (im.format, im.size))
PY
[ "$?" -eq 0 ] || die "icon validation failed"
cp -f "$ICON_SOURCE" "$CONTROL_W/icon_AmericanEnglish.dat" || die "cannot copy icon"
printf "control/icon_AmericanEnglish.dat: %s bytes sha256=%s\n" "$(stat -c %s "$CONTROL_W/icon_AmericanEnglish.dat")" "$(sha256sum "$CONTROL_W/icon_AmericanEnglish.dat" | cut -d" " -f1)"

# ---- STEP 4: RomFS content selection ----
printf "\n== STEP 4: RomFS\n"
ROMFS_RAW=""
ROMFS_W="$(winpath "$STAGE_ROMFS")"
ROMFS_SOURCE="empty"
if [ "$NO_ROMFS" -eq 1 ]; then
  ROMFS_SOURCE="empty (--no-romfs)"
elif [ -n "$ROMFS_DIR" ]; then
  ROMFS_RAW="$ROMFS_DIR"
  ROMFS_W="$(winpath "$ROMFS_DIR")"
  ROMFS_SOURCE="provided: $ROMFS_DIR"
elif [ -n "$EXTRACTED_ROMFS_DIR" ] && [ -d "$EXTRACTED_ROMFS_DIR" ]; then
  ROMFS_RAW="$EXTRACTED_ROMFS_DIR"
  ROMFS_W="$EXTRACTED_ROMFS_DIR"
  ROMFS_SOURCE="extracted from NRO: $EXTRACTED_ROMFS_DIR"
fi
if [ -z "$ROMFS_RAW" ]; then
  ROMFS_RAW="$STAGE_ROMFS"
  printf "romfs: empty (no --romfs-dir and no embedded RomFS)\n"
fi
[ -d "$ROMFS_RAW" ] || die "romfs source is not a directory: $ROMFS_RAW"
"$PYTHON" - "$ROMFS_RAW" "$META_W" <<'PY'
import os
import sys

root, meta = sys.argv[1], sys.argv[2]
count = 0
total = 0
worst = ("", 0)
for base, dirs, files in os.walk(root):
    for name in files:
        path = os.path.join(base, name)
        count += 1
        try:
            total += os.path.getsize(path)
        except OSError:
            pass
        if len(path) > worst[1]:
            worst = (path, len(path))
lines = ["ROMFS_SOURCE_DIR=" + root.replace("\\", "/"),
         "ROMFS_COUNT=%d" % count,
         "ROMFS_BYTES=%d" % total,
         "ROMFS_MAXPATH_LEN=%d" % worst[1],
         "ROMFS_MAXPATH=" + worst[0].replace("\\", "/")]
with open(meta, "a", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print("romfs: %d files, %d payload bytes, longest path %d chars" % (count, total, worst[1]))
if worst[1] >= 259:
    print("WARN: path length %d >= 259 (Windows MAX_PATH; hacBrewPack can fail with 'Failed to stat')" % worst[1])
if worst[1] >= 240:
    print("WARN: path length %d is close to the 259-byte practical limit" % worst[1])
PY
[ "$?" -eq 0 ] || die "romfs inventory failed"
ROMFS_COUNT="$(sed -n "s/^ROMFS_COUNT=//p" "$META")"
ROMFS_BYTES="$(sed -n "s/^ROMFS_BYTES=//p" "$META")"
ROMFS_MAXLEN="$(sed -n "s/^ROMFS_MAXPATH_LEN=//p" "$META")"

# ---- STEP 5: hacBrewPack ----
printf "\n== STEP 5: hacBrewPack\n"
RAWLOG="$WORK_DIR/hacbrewpack.raw.log"
LOG="$WORK_DIR/hacbrewpack.log"
rm -f "$RAWLOG" "$LOG"
( cd "$WORK_DIR" && "$HACBREWPACK" --nologo -k "$(winpath "$KEYPATH")" --romfsdir "$ROMFS_W" > "$RAWLOG" 2>&1 )
HBP_RC=$?
# hacBrewPack prints a derived key-area value; strip it from the persisted log.
if [ -f "$RAWLOG" ]; then
  grep -v -e "Key area key" -e "key_area_key" "$RAWLOG" > "$LOG" 2>/dev/null || : > "$LOG"
  rm -f "$RAWLOG"
else
  : > "$LOG"
fi
printf "hacBrewPack exit code: %s\n" "$HBP_RC"
if [ "$HBP_RC" -ne 0 ]; then
  printf "--- last 25 log lines ---\n" >&2
  tail -n 25 "$LOG" >&2
  die "hacBrewPack failed (rc $HBP_RC); log: $LOG"
fi
NSP_SRC="$WORK_DIR/hacbrewpack_nsp/$TITLE_ID.nsp"
[ -f "$NSP_SRC" ] || die "hacBrewPack did not produce $NSP_SRC"
OUT_NAME="$APP_NAME-$TITLE_ID.nsp"
OUT_NSP="$OUT_DIR/$OUT_NAME"
cp -f "$NSP_SRC" "$(winpath "$OUT_DIR")/$OUT_NAME" || die "cannot copy NSP to $OUT_DIR"
NSP_SIZE="$(stat -c %s "$OUT_NSP")"
NSP_SHA="$(sha256sum "$OUT_NSP" | cut -d" " -f1)"
printf "NSP: %s (%s bytes, sha256 %s)\n" "$OUT_NSP" "$NSP_SIZE" "$NSP_SHA"

# ---- optional structure verification with nstool ----
if [ -n "$NSTOOL_BIN" ]; then
  printf "\n== nstool: NSP layer\n"
  NSTOOL_LOG="$WORK_DIR/nstool-nsp.log"
  "$NSTOOL_BIN" -y -k "$(winpath "$KEYPATH")" "$(winpath "$OUT_NSP")" > "$NSTOOL_LOG" 2>&1
  NSTOOL_RC=$?
  grep -v -e "Key area key" -e "key_area_key" "$NSTOOL_LOG" | head -n 40
  printf "nstool NSP exit code: %s (log: %s)\n" "$NSTOOL_RC" "$NSTOOL_LOG"
  if [ "$KEYSET_MODE" = "real" ]; then
    printf "\n== nstool: NCA layer\n"
    NCA_DIR="$WORK_DIR/nstool-nca"
    rm -rf "$NCA_DIR"
    mkdir -p "$NCA_DIR"
    "$NSTOOL_BIN" -x "$(winpath "$NCA_DIR")" -k "$(winpath "$KEYPATH")" "$(winpath "$OUT_NSP")" > "$WORK_DIR/nstool-extract.log" 2>&1
    printf "nstool extract exit code: %s\n" "$?"
    NCA_INDEX=0
    for nca in "$NCA_DIR"/*; do
      [ -f "$nca" ] || continue
      NCA_INDEX=$((NCA_INDEX + 1))
      NCA_LOG="$WORK_DIR/nstool-nca-$NCA_INDEX.log"
      "$NSTOOL_BIN" -y -k "$(winpath "$KEYPATH")" "$(winpath "$nca")" > "$NCA_LOG" 2>&1
      NCA_RC=$?
      printf -- "--- %s (rc %s) ---\n" "$(basename "$nca")" "$NCA_RC"
      grep -e "Content Type" -e "Format Type" -e "ProgID" -e "Key Generation" -e "Kaek Index" -e "Size:" -e "SdkAddon" -e "NCA Header Main Signature" -e "ACID Signature" "$NCA_LOG" | head -n 12
      grep -q "Content Type: Program" "$NCA_LOG" && printf "  (program NCA verified)\n"
    done
    [ "$NCA_INDEX" -gt 0 ] || printf "WARN: no NCA extracted from the NSP\n"
  else
    printf "nstool: NCA-layer verification skipped for synthetic keyset (header_key mismatch)\n"
  fi
fi

# ---- summary ----
printf "\n===EXIT\n"
printf "%s\n" "$HBP_RC"
printf "===ARTIFACTS\n"
printf "%s %s %s\n" "$OUT_NAME" "$NSP_SIZE" "$NSP_SHA"
printf "===INPUTS\n" 
printf "keyset_mode %s\n" "$KEYSET_MODE"
printf "title_id %s\n" "$TITLE_ID"
printf "exefs_main %s %s\n" "$(stat -c %s "$EXEFS/main")" "$(sha256sum "$EXEFS/main" | cut -d" " -f1)"
printf "npdm %s %s\n" "$(stat -c %s "$EXEFS/main.npdm")" "$(sha256sum "$EXEFS/main.npdm" | cut -d" " -f1)"
printf "nacp %s %s\n" "$(stat -c %s "$CONTROL_W/control.nacp")" "$(sha256sum "$CONTROL_W/control.nacp" | cut -d" " -f1)"
printf "icon %s %s\n" "$(stat -c %s "$CONTROL_W/icon_AmericanEnglish.dat")" "$(sha256sum "$CONTROL_W/icon_AmericanEnglish.dat" | cut -d" " -f1)"
printf "===NRO\n"
sed -n "s/^/  /p" "$META"
printf "===ROMFS\n"
printf "source %s\n" "$ROMFS_SOURCE"
printf "files %s bytes %s max_path_len %s\n" "$ROMFS_COUNT" "$ROMFS_BYTES" "$ROMFS_MAXLEN"
printf "===LOG\n"
printf "%s\n" "$LOG"
printf "===LOGTAIL\n"
tail -n 18 "$LOG"
