#!/usr/bin/env bash
# citron_run.sh -- GalNX M1 reusable Citron Neo smoke harness for Nintendo Switch NRO milestones.
#
# Purpose : launch an arbitrary homebrew NRO on Citron Neo (Windows), detect whether it really
#           started, capture a window screenshot and archive the Citron log, then emit one
#           machine-readable JSON line on stdout.
# Author  : audit-web (task-15, 2026-10-30). Read-only tooling: it never builds, patches or
#           redistributes Citron/Brewser; it only runs an already-downloaded official binary.
# Usage   : bash scripts/citron_run.sh --nro /path/to/app.nro [--timeout 60] [--settle 6]
#                                      [--expect-title app] [--expect-file switch/app/marker.txt]
#                                      [--app-log-regex REGEX] [--keep] [--allow-existing]
#                                      [--game /path/to/app.nsp]   (alias: --nsp)
#                                      [--input-click X,Y] [--input-keys C,ENTER] [--input-delay 1500]
#                                      [--input-settle 1200] [--input-region 70,950]
#                                      [--input-steps 'click:X,Y;wait:MS;key:C;capture:NAME']
#                                      [--input-steps @steps.json]  (P1-a multi-step input)
#                                      [--detach]  (P3-d: detached job; --status/--wait-job queries)
# Input   : M2-a feature. Injects input into the running Citron instance and proves it reached
#           the emulated application by capturing a before/after window screenshot and a pixel
#           diff over the game region. Mouse: SendInput mouse_event at virtual-screen coordinates.
#           Keyboard: PostMessage(WM_KEYDOWN/WM_KEYUP) to the Citron main window (SendInput does
#           NOT reach Citron's Qt key handler in this environment; see docs/environment/
#           citron-harness-input.md). Never touches Citron config; only reads keys file paths.
# File    : M3-b. --game PATH (alias --nsp) launches any game file Citron can load
#           (.nro/.nsp/.xci/.nsz/.xcz); the file is staged into the virtual SD exactly like
#           an NRO. --nro stays fully supported and is equivalent. The JSON reports
#           game_type/game_path/stage_path next to the legacy nro/nro_staged fields.
# Output  : progress on stderr; final single-line JSON on stdout.
# Exit    : 0 = loaded, 1 = timeout, 2 = fail (argument/setup/runtime failure).
# Safety  : never reads or prints keys (*.keys) contents; only tests that they exist.
#           never edits Citron user config; only copies the NRO into the virtual SD card.
set -o pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

POWERSHELL="$POWERSHELL"
[ -n "$POWERSHELL" ] || POWERSHELL="powershell.exe"

NRO=""
GAME=""
TIMEOUT=60
SETTLE=6
EXPECT_TITLE=""
EXPECT_FILE=""
APP_LOG_REGEX=""
CITRON_EXE_ARG="$CITRON_EXE"
SD_ARG="$CITRON_SD"
OUT_ROOT="$CITRON_HARNESS_OUT"
DO_KILL=1
ALLOW_EXISTING=0
NO_STAGE=0
RUN_LOG=""
INPUT_KEYS=""
INPUT_CLICK=""
INPUT_DELAY=""
INPUT_SETTLE=""
INPUT_REGION=""
INPUT_HOLD=""
INPUT_GAP=""
INPUT_STEPS=""
INPUT_STEPS_FILE=""
DETACH=0
STATUS_DIR=""
WAIT_DIR=""
WAIT_TIMEOUT=""
JOB_MODE=""
JOB_DIR=""
ORIG_ARGS=()

usage() {
  cat >&2 <<'EOF'
Usage: bash scripts/citron_run.sh --nro <path-to.nro> [options]

Required (exactly one of --nro / --game)
  --no-stage            Launch in place instead of copying into the virtual SD (large NSPs)
  --nro PATH            Homebrew NRO to launch (copied into Citron virtual SD: sdmc/switch/galnx-harness/)
  --game PATH           Any game file Citron can load: .nro, .nsp, .xci, .nsz, .xcz (M3-b).
                        Alias: --nsp PATH. Staged like an NRO; type auto-detected and reported
                        as JSON game_type. --nro is equivalent to --game for .nro files.

Timing
  --timeout SECONDS     Max seconds to wait for boot evidence (default 60)
  --settle SECONDS      Extra seconds after boot line before screenshot (default 6)

Success signals (all reported; JSON has a boolean per signal)
  --expect-title TEXT   Window title must contain TEXT (default: NRO file stem)
  --expect-file REL     SD-relative file expected after launch (e.g. switch/app/ready.txt)
  --app-log-regex RE    Regex expected in Citron log slice (application self-output)

Input injection (M2-a; optional, needs a loaded application window)
  --input-click X,Y     Click once at window-image pixel X,Y (1:1 with window.png; mouse_event)
  --input-keys LIST     Comma key list, names or decimal VK codes: C,ENTER,SPACE,DOWN,67
                        (delivered with PostMessage WM_KEYDOWN/WM_KEYUP to the Citron window)
  --input-delay MS      Wait before injecting, lets the app draw its first frame (default 1500)
  --input-settle MS     Wait after injecting before the after screenshot (default 1200)
  --input-region T,B    Game-region y range used for the pixel diff (default 70,950; the
                        top menu bar and bottom status bar of the Citron window are excluded)
  --input-hold MS       Key hold time (default 60)
  --input-gap MS        Gap between keys (default 250)
#
# Multi-step input script (P1-a; runs after --input-delay)
#  --input-steps SPEC    Semicolon-separated steps, each one of:
#                          click:X,Y      click at window-image pixel X,Y (same as --input-click; SendInput)
#                          pclick:X,Y     left click at window-image pixel X,Y via PostMessage (R10 workaround:
#                                         reaches the window without foreground acquisition)
#                          prclick:X,Y    right-button PostMessage click (VN menus open on right click)
#                          key:LIST       comma key list (same names/VK codes as --input-keys)
#                          wait:MS        sleep MS milliseconds
#                          capture:NAME   capture the window to step-NN-NAME.png in the run dir
#                        Example: 'click:1233,406;wait:1500;click:1233,248;capture:dir'
#                        Example: 'wait:90000;prclick:860,500;wait:3000;capture:menu'
#  --input-steps @FILE   Read steps from a JSON array file:
#                          [{"action":"click","x":1233,"y":406},{"action":"wait","ms":1500},
#                           {"action":"key","keys":"C"},{"action":"capture","name":"after"}]
#                        (--input-steps-file FILE is the equivalent long form)
#                        Old --input-click / --input-keys still work unchanged (run first).

Environment / cleanup
  --citron-exe PATH     citron.exe to use (default: discover workspaces/*/citron/citron.exe)
  --sd PATH             Citron virtual SD root (default: <user dir>/sdmc)
  --out DIR             Run archive root (default: <repo>/workspaces/citron-harness/runs)
  --keep                Leave Citron running after evidence collection
  --allow-existing      Allow launching while another citron.exe is already running
  -h, --help            This help

Output JSON fields
  nro, game_type, game_path, stage_path, status (loaded|timeout|fail), window_title, screenshot,
  log_path, boot_line,
  run_dir, nro_staged, citron_exe, citron_build, expected_title, signals{title_match,
  boot_line, app_output, app_output_source}, screenshot_info{method,bytes,nonblack_ratio},
  elapsed_s, pid, error, admin_elevated_shell, killed,
  input{injected,key_method,keys_requested,keys_sent,focus_ok,clicks,screenshot_before,
  screenshot_after,diff_ratio,nonblack_before,nonblack_after,region,error}
  input.steps[] (index,action,argument,status,detail,screenshot,elapsed_ms), input.steps_failed,
  input.steps_diff_ratio, input.steps_final, input.steps_error
#
# Detached job mode (P3-d; fixes R14 -- the caller process tree may be reaped early)
#  --detach              Do the work in a detached Windows process and return immediately.
#                        Prints one JSON line {mode:"detach",status:"started",run_dir,
#                        result_json,done_marker,harness_pid,launcher_pid,...} and exits 0.
#                        The child keeps running after the caller shell/job ends.
#  --status DIR          Print the job state JSON now and exit (no waiting).
#                        Exit: 0 done+loaded, 1 done+failed, 2 running/unknown/timeout.
#  --wait-job DIR        Like --status but poll until the job finishes (.done marker).
#  --wait-timeout SEC    Max seconds for --wait-job (default 600).
#
# Job directory (the run_dir printed by --detach) contains: job.json (launcher metadata),
#   harness.pid (child PID), harness.out / harness.err (child stdout/stderr), harness.log
#   (harness progress log), result.json (same JSON as a normal run), .done (marker with
#   status/rc/finished), plus all normal evidence (window*.png, citron_log*.txt, ...).
EOF
}

log() { printf '[citron_run] %s\n' "$*" >&2; }

emit_result() {
  GLX_NRO="$J_NRO" GLX_STATUS="$J_STATUS" GLX_TITLE="$J_TITLE" GLX_SHOT="$J_SHOT" \
  GLX_LOG="$J_LOG" GLX_BOOT="$J_BOOT" GLX_RUNDIR="$J_RUNDIR" GLX_STAGED="$J_STAGED" \
  GLX_EXE="$J_EXE" GLX_BUILD="$J_BUILD" GLX_EXPECT="$J_EXPECT" GLX_TITLE_MATCH="$J_TITLE_MATCH" \
  GLX_GAMETYPE="$J_GAMETYPE" GLX_GAMEPATH="$J_GAMEPATH" GLX_STAGEPATH="$J_STAGEPATH" \
  GLX_APP_OUT="$J_APP_OUT" GLX_APP_SRC="$J_APP_SRC" GLX_ELAPSED="$J_ELAPSED" GLX_PID="$J_PID" \
  GLX_ERR="$J_ERR" GLX_ELEVATED="$J_ELEVATED" GLX_KILLED="$J_KILLED" GLX_SHOT_METHOD="$J_SHOT_METHOD" \
  GLX_SHOT_BYTES="$J_SHOT_BYTES" GLX_SHOT_NONBLACK="$J_SHOT_NONBLACK" \
  GLX_ROUTE="${LAUNCH_MODE:-}" \
  GLX_IN_DONE="$J_INPUT_DONE" GLX_IN_FOCUS="$J_INPUT_FOCUS" GLX_IN_CLICKS="$J_INPUT_CLICKS" \
  GLX_IN_KEYS="$J_INPUT_KEYS_SENT" GLX_IN_VKS="$INPUT_VKS" GLX_IN_BEFORE="$J_INPUT_BEFORE" \
  GLX_IN_AFTER="$J_INPUT_AFTER" GLX_IN_DIFF="$J_INPUT_DIFF" GLX_IN_NBB="$J_INPUT_NBB" \
  GLX_IN_NBA="$J_INPUT_NBA" GLX_IN_REGION="$J_INPUT_REGION" GLX_IN_ERR="$J_INPUT_ERR" \
  GLX_STEPS_FILE="$J_STEPS_FILE" GLX_STEPS_FAILED="$J_STEPS_FAILED" GLX_STEPS_DIFF="$J_STEPS_DIFF" \
  GLX_STEPS_FINAL="$J_STEPS_FINAL" GLX_STEPS_ERR="$J_STEPS_ERR" \
  node -e 'const e=process.env;const codes=(e.GLX_IN_VKS||"").split(",").filter(Boolean).map(Number);const fs=require("fs");let steps=[];try{if(e.GLX_STEPS_FILE){const raw=fs.readFileSync(e.GLX_STEPS_FILE,"utf8").split("\n");for(const ln of raw){if(!ln)continue;const p=ln.split("\t");steps.push({index:Number(p[0]||0),action:p[1]||"",argument:p[2]||"",status:p[3]||"",detail:p[4]||"",screenshot:p[5]||"",elapsed_ms:Number(p[6]||0)});}}}catch(_){steps=[];}const o={nro:e.GLX_NRO||"",game_type:e.GLX_GAMETYPE||"",game_path:e.GLX_GAMEPATH||"",stage_path:e.GLX_STAGEPATH||"",status:e.GLX_STATUS||"",window_title:e.GLX_TITLE||"",screenshot:e.GLX_SHOT||"",log_path:e.GLX_LOG||"",boot_line:e.GLX_BOOT||"",run_dir:e.GLX_RUNDIR||"",nro_staged:e.GLX_STAGED||"",citron_exe:e.GLX_EXE||"",citron_build:e.GLX_BUILD||"",expected_title:e.GLX_EXPECT||"",signals:{title_match:e.GLX_TITLE_MATCH==="1",boot_line:(e.GLX_BOOT||"").length>0,app_output:e.GLX_APP_OUT==="1",app_output_source:e.GLX_APP_SRC||""},screenshot_info:{method:e.GLX_SHOT_METHOD||"",bytes:Number(e.GLX_SHOT_BYTES||0),nonblack_ratio:Number(e.GLX_SHOT_NONBLACK||0)},input:{injected:e.GLX_IN_DONE==="1",key_method:e.GLX_IN_KEYS!=="0"||codes.length>0?"postmessage":"",keys_requested:codes,keys_sent:Number(e.GLX_IN_KEYS||0),focus_ok:e.GLX_IN_FOCUS==="1",clicks:Number(e.GLX_IN_CLICKS||0),screenshot_before:e.GLX_IN_BEFORE||"",screenshot_after:e.GLX_IN_AFTER||"",diff_ratio:Number(e.GLX_IN_DIFF||0),nonblack_before:Number(e.GLX_IN_NBB||0),nonblack_after:Number(e.GLX_IN_NBA||0),region:e.GLX_IN_REGION||"",error:e.GLX_IN_ERR||"",steps:steps,steps_failed:Number(e.GLX_STEPS_FAILED||0),steps_diff_ratio:Number(e.GLX_STEPS_DIFF||0),steps_final:e.GLX_STEPS_FINAL||"",steps_error:e.GLX_STEPS_ERR||""},elapsed_s:Number(e.GLX_ELAPSED||0),pid:Number(e.GLX_PID||0),error:e.GLX_ERR||"",admin_elevated_shell:e.GLX_ELEVATED==="1",launch_route:e.GLX_ROUTE||"",killed:e.GLX_KILLED==="1"};console.log(JSON.stringify(o));'
}

state_reset() {
  J_NRO=""; J_STATUS=""; J_TITLE=""; J_SHOT=""; J_LOG=""; J_BOOT=""
  J_RUNDIR=""; J_STAGED=""; J_EXE=""; J_BUILD=""; J_EXPECT=""
  J_GAMETYPE=""; J_GAMEPATH=""; J_STAGEPATH=""
  J_TITLE_MATCH="0"; J_APP_OUT="0"; J_APP_SRC=""; J_ELAPSED="0"; J_PID="0"
  J_ERR=""; J_ELEVATED="0"; J_KILLED="0"; J_SHOT_METHOD=""; J_SHOT_BYTES="0"; J_SHOT_NONBLACK="0"
  J_INPUT_DONE="0"; J_INPUT_FOCUS=""; J_INPUT_CLICKS="0"; J_INPUT_KEYS_SENT="0"
  J_INPUT_BEFORE=""; J_INPUT_AFTER=""; J_INPUT_DIFF=""; J_INPUT_NBB=""; J_INPUT_NBA=""
  J_INPUT_REGION=""; J_INPUT_ERR=""
  J_STEPS_FILE=""; J_STEPS_FAILED="0"; J_STEPS_DIFF=""; J_STEPS_FINAL=""; J_STEPS_ERR=""
}

fail_early() {
  # failure before the run archive exists: still emit one JSON line for scripts
  local reason="$1"
  local msg="$2"
  log "FAIL: $reason ($msg)"
  state_reset
  J_STATUS="fail"
  J_ERR="$reason: $msg"
  if [ "$JOB_MODE" = "child" ] && [ -n "$JOB_DIR" ]; then
    job_write_fail_result "$reason" "$msg"
  fi
  emit_result
  exit 2
}

fail_now() {
  # failure after the run archive exists: emit JSON + persist result.json + close a detached job
  local reason="$1"
  local msg="$2"
  log "FAIL: $reason ($msg)"
  state_reset
  J_STATUS="fail"
  J_RUNDIR="$RUN_DIR"
  J_EXE="$CITRON_EXE"
  J_EXPECT="$EXPECT_TITLE"
  J_ERR="$reason: $msg"
  local out
  out="$(emit_result)"
  printf '%s\n' "$out" > "$RUN_DIR/result.json" 2>/dev/null || true
  printf '%s\n' "$reason: $msg" >> "$RUN_LOG" 2>/dev/null || true
  if [ "$JOB_MODE" = "child" ] && [ -n "$JOB_DIR" ]; then
    if [ "$RUN_DIR" != "$JOB_DIR" ] && [ -f "$RUN_DIR/result.json" ]; then
      cp -f "$RUN_DIR/result.json" "$JOB_DIR/result.json" 2>/dev/null || true
    fi
    job_mark_done "fail" 2
  fi
  printf '%s\n' "$out"
  exit 2
}

win_path() { cygpath -w "$1"; }

slice_log() {
  # print log lines after the last "citron Version:" launch marker
  awk 'BEGIN { last=0 } { lines[NR]=$0 } /citron Version:/ { last=NR }
       END { for (i=last+1; i<=NR; i++) print lines[i] }' "$1" 2>/dev/null
}
# ---------- detached job support (P3-d; fixes R14 "harness exits early, Citron still alive") ----------
job_mark_done() {
  # $1 = status, $2 = exit code
  [ -n "$JOB_DIR" ] || return 0
  mkdir -p "$JOB_DIR" 2>/dev/null || true
  printf 'status=%s\nrc=%s\nfinished=%s\n' "$1" "$2" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$JOB_DIR/.done" 2>/dev/null || true
}

job_write_fail_result() {
  # persist result.json + .done for a detached child that failed before its run archive existed
  local reason="$1" msg="$2" out
  [ -n "$JOB_DIR" ] || return 0
  mkdir -p "$JOB_DIR" 2>/dev/null || true
  if [ -z "$J_RUNDIR" ]; then J_RUNDIR="$(win_path "$JOB_DIR" 2>/dev/null || printf '%s' "$JOB_DIR")"; fi
  J_STATUS="fail"
  J_ERR="$reason: $msg"
  out="$(emit_result)" || out=""
  [ -n "$out" ] && printf '%s\n' "$out" > "$JOB_DIR/result.json" 2>/dev/null || true
  printf '%s: %s\n' "$reason" "$msg" >> "$JOB_DIR/harness.err" 2>/dev/null || true
  job_mark_done "fail" 2
}

job_query() {
  # $1 = run/job dir, $2 = optional wait seconds (empty = answer from current state)
  local dir="$1" wait_sec="$2" start now waited out
  QUERY_RC=2
  if [ -z "$dir" ] || [ ! -d "$dir" ]; then
    printf '%s\n' '{"state":"unknown","run_dir":"","error":"job dir not found"}'
    return 0
  fi
  start="$(date +%s)"
  while :; do
    [ -f "$dir/.done" ] && break
    [ -z "$wait_sec" ] && break
    now="$(date +%s)"
    waited=$((now - start))
    [ "$waited" -ge "$wait_sec" ] && break
    sleep 1
  done
  waited=$(( $(date +%s) - start ))
  out="$(node -e 'const fs=require("fs"),path=require("path");const dir=process.argv[1],waited=Number(process.argv[2]||0);const rd=p=>{try{return fs.readFileSync(p,"utf8")}catch(_){return ""}};let done=false,status="",rc=null,finished="";const raw=rd(path.join(dir,".done"));if(raw){done=true;for(const ln of raw.split("\n")){const m=ln.match(/^([a-z_]+)=(.*)$/);if(!m)continue;if(m[1]==="status")status=m[2];else if(m[1]==="rc")rc=Number(m[2]);else if(m[1]==="finished")finished=m[2];}}let result=null,job=null,pid=null;const rraw=rd(path.join(dir,"result.json"));if(rraw){try{result=JSON.parse(rraw)}catch(_){}}const jraw=rd(path.join(dir,"job.json"));if(jraw){try{job=JSON.parse(jraw)}catch(_){}}const praw=rd(path.join(dir,"harness.pid")).trim();if(praw){const n=Number(praw);if(n>0)pid=n}if(!status&&result&&result.status)status=result.status;const state=done?"done":(pid?"running":"unknown");console.log(JSON.stringify({run_dir:dir,state:state,status:status,rc:rc,finished:finished,harness_pid:pid,result_json:path.join(dir,"result.json"),done_marker:path.join(dir,".done"),job:job,result:result,waited_s:waited}));' "$dir" "$waited" 2>/dev/null)" || out=""
  [ -n "$out" ] || out='{"state":"unknown","run_dir":""}'
  QUERY_RC="$(printf '%s' "$out" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{try{const o=JSON.parse(s);process.stdout.write(o.state==="done"?(o.status==="loaded"?"0":(o.status==="timeout"?"2":"1")):"2")}catch(_){process.stdout.write("2")}})')"
  printf '%s\n' "$out"
}

detach_launch() {
  # parent side of --detach: spawn a detached Windows process tree (WMI Create) and return at once
  local jdir jdir_win jdir_fwd launcher_dir launcher_win bash_bin bash_win script_abs repo_win
  local job_cmd_win ps_out lpid hpid i jout n arg v f
  local -a child_arg_list
  if [ -z "$NRO_ABS" ] || [ ! -f "$NRO_ABS" ]; then
    fail_early "game_not_found" "--detach needs an existing --game/--nro file"
  fi
  [ -n "$OUT_ROOT" ] || OUT_ROOT="$REPO_ROOT/workspaces/citron-harness/runs"
  mkdir -p "$OUT_ROOT" || fail_early "run_dir_unwritable" "$OUT_ROOT"
  RUN_ID="$(date +%Y%m%d-%H%M%S)-$STEM"
  jdir="$OUT_ROOT/$RUN_ID"
  mkdir -p "$jdir" || fail_early "run_dir_unwritable" "$jdir"
  JOB_DIR="$jdir"
  RUN_DIR="$jdir"
  RUN_LOG="$jdir/harness.log"
  : > "$RUN_LOG" 2>/dev/null || true
  J_RUNDIR="$(win_path "$jdir")"
  jdir_win="$J_RUNDIR"
  jdir_fwd="$(printf '%s' "$jdir_win" | sed -e 's|\\|/|g')"
  bash_bin="$(command -v bash)"
  [ -n "$bash_bin" ] || fail_now "bash_missing" "cannot locate bash"
  bash_win="$(win_path "$bash_bin")"
  script_abs="$SCRIPT_DIR/$(basename "$0")"
  repo_win="$(win_path "$REPO_ROOT")"
  launcher_dir="${TEMP:-/tmp}/galnx-jobs/$RUN_ID"
  mkdir -p "$launcher_dir" || fail_now "launcher_dir_unwritable" "$launcher_dir"
  launcher_win="$(win_path "$launcher_dir")"
  # child argument vector: drop --detach/--status/--wait-* and the original --game/--nro pair,
  # absolutize multi-step JSON files, then append the validated absolute game path
  child_arg_list=()
  n="${#ORIG_ARGS[@]}"
  i=0
  while [ "$i" -lt "$n" ]; do
    arg="${ORIG_ARGS[$i]}"
    case "$arg" in
      --detach) i=$((i+1)) ;;
      --status|--wait-job|--wait-timeout) i=$((i+2)) ;;
      --nro|--game|--nsp) i=$((i+2)) ;;
      --input-steps|--input-steps-file)
        v="${ORIG_ARGS[$((i+1))]:-}"
        if [ -n "$v" ]; then
          case "$v" in
            @*) f="${v#@}"; [ -f "$f" ] && v="@$(cd "$(dirname "$f")" && pwd)/$(basename "$f")" ;;
            *)  [ -f "$v" ] && v="$(cd "$(dirname "$v")" && pwd)/$(basename "$v")" ;;
          esac
        fi
        child_arg_list+=("$arg" "$v")
        i=$((i+2)) ;;
      *) child_arg_list+=("$arg"); i=$((i+1)) ;;
    esac
  done
  child_arg_list+=("--game" "$NRO_ABS")
  # 1) _job.sh: exec the harness in child mode (bash -quoted arguments, paths may contain spaces)
  {
    printf '%s\n' '#!/usr/bin/env bash'
    printf 'export CITRON_USER_DIR=%q\n' "$USER_DIR"
    printf 'export CITRON_SD=%q\n' "$SD"
    if [ -n "$CITRON_EXE" ]; then printf 'export CITRON_EXE=%q\n' "$CITRON_EXE"; fi
    if [ -n "$APPDATA" ]; then printf 'export APPDATA=%q\n' "$APPDATA"; fi
    printf 'exec %q %q --job-mode child --job-dir %q' "$bash_bin" "$script_abs" "$jdir"
    if [ "${#child_arg_list[@]}" -gt 0 ]; then printf ' %q' "${child_arg_list[@]}"; fi
    printf '\n'
  } > "$launcher_dir/_job.sh"
  # 2) job.cmd: no-space launcher (cmd.exe /c can then be used without nested quoting)
  {
    printf '@echo off\r\n'
    printf 'cd /d "%s"\r\n' "$repo_win"
    printf '"%s" "%s" 1>> "%s" 2>> "%s"\r\n' "$bash_win" "$launcher_win\\_job.sh" "$jdir_win\\harness.out" "$jdir_win\\harness.err"
  } > "$launcher_dir/job.cmd"
  # 3) job.ps1: WMI Win32_Process.Create -> parent is WmiPrvSE, not our shell/job object
  cat > "$launcher_dir/job.ps1" <<'PSEOF'
param([string]$Cmd,[string]$WorkDir)
$ErrorActionPreference = "Stop"
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $Cmd; CurrentDirectory = $WorkDir }
if ($null -eq $r) { Write-Output "ERR null"; exit 1 }
if ($r.ReturnValue -ne 0) { Write-Output ("ERR " + $r.ReturnValue); exit 1 }
Write-Output $r.ProcessId
PSEOF
  job_cmd_win="$launcher_win\\job.cmd"
  ps_out="$("$POWERSHELL" -NoProfile -ExecutionPolicy Bypass -File "$(win_path "$launcher_dir/job.ps1")" -Cmd "cmd.exe /c $job_cmd_win" -WorkDir "$repo_win" 2>>"$RUN_LOG")"
  lpid="$(printf '%s\n' "$ps_out" | tail -n 1 | tr -d '\r' | tr -cd '0-9')"
  if [ -z "$lpid" ]; then
    fail_now "detach_launch_failed" "WMI Win32_Process.Create failed: $(printf '%s' "$ps_out" | tr '\n' ' ')"
  fi
  # keep a copy of the launcher scripts inside the run archive (evidence / reproducibility)
  cp -f "$launcher_dir/_job.sh" "$jdir/_job.sh" 2>/dev/null || true
  cp -f "$launcher_dir/job.cmd" "$jdir/job.cmd" 2>/dev/null || true
  cp -f "$launcher_dir/job.ps1" "$jdir/job.ps1" 2>/dev/null || true
  hpid=""
  i=0
  while [ "$i" -lt 25 ]; do
    if [ -s "$jdir/harness.pid" ]; then hpid="$(tr -d '[:space:]' < "$jdir/harness.pid" 2>/dev/null)"; break; fi
    sleep 0.2
    i=$((i+1))
  done
  jout="$(GLX_JRUNDIR="$jdir_fwd" GLX_JUNIX="$jdir" GLX_HPID="$hpid" GLX_LPID="$lpid" GLX_LAUNCHER="$launcher_win" GLX_CMD="cmd.exe /c $job_cmd_win" node -e 'const e=process.env;const r=e.GLX_JRUNDIR||"";console.log(JSON.stringify({mode:"detach",status:"started",run_dir:r,run_dir_unix:e.GLX_JUNIX||"",result_json:r+"/result.json",done_marker:r+"/.done",harness_out:r+"/harness.out",harness_err:r+"/harness.err",launcher_dir:e.GLX_LAUNCHER||"",harness_pid:Number(e.GLX_HPID||0),launcher_pid:Number(e.GLX_LPID||0),command:e.GLX_CMD||"",started_at:new Date().toISOString()}))' 2>>"$RUN_LOG")"
  [ -n "$jout" ] || jout="{\"mode\":\"detach\",\"status\":\"started\",\"run_dir\":\"$jdir_fwd\",\"harness_pid\":0,\"launcher_pid\":$lpid}"
  printf '%s\n' "$jout" > "$jdir/job.json" 2>/dev/null || true
  log "detached job started: run_dir=$jdir harness_pid=${hpid:-pending} launcher_pid=$lpid"
  printf '%s\n' "$jout"
  exit 0
}

state_reset

ORIG_ARGS=("$@")

while [ $# -gt 0 ]; do
  case "$1" in
    --nro) NRO="$2"; shift 2 ;;
    --game|--nsp) GAME="$2"; shift 2 ;;
    --no-stage) NO_STAGE=1; shift ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --settle) SETTLE="$2"; shift 2 ;;
    --expect-title) EXPECT_TITLE="$2"; shift 2 ;;
    --expect-file) EXPECT_FILE="$2"; shift 2 ;;
    --app-log-regex) APP_LOG_REGEX="$2"; shift 2 ;;
    --citron-exe) CITRON_EXE_ARG="$2"; shift 2 ;;
    --sd) SD_ARG="$2"; shift 2 ;;
    --out) OUT_ROOT="$2"; shift 2 ;;
    --input-keys) INPUT_KEYS="$2"; shift 2 ;;
    --input-click) INPUT_CLICK="$2"; shift 2 ;;
    --input-delay) INPUT_DELAY="$2"; shift 2 ;;
    --input-settle) INPUT_SETTLE="$2"; shift 2 ;;
    --input-region) INPUT_REGION="$2"; shift 2 ;;
    --input-hold) INPUT_HOLD="$2"; shift 2 ;;
    --input-gap) INPUT_GAP="$2"; shift 2 ;;
    --input-steps) INPUT_STEPS="$2"; shift 2 ;;
    --input-steps-file) INPUT_STEPS_FILE="$2"; shift 2 ;;
    --detach) DETACH=1; shift ;;
    --status) STATUS_DIR="$2"; shift 2 ;;
    --wait-job) WAIT_DIR="$2"; shift 2 ;;
    --wait-timeout) WAIT_TIMEOUT="$2"; shift 2 ;;
    --job-mode) JOB_MODE="$2"; shift 2 ;;
    --job-dir) JOB_DIR="$2"; shift 2 ;;
    --keep) DO_KILL=0; shift ;;
    --allow-existing) ALLOW_EXISTING=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) log "ERROR: unknown argument: $1"; usage; exit 2 ;;
  esac
done

# ---------- detached job queries (P3-d) run before any launch validation ----------
if [ -n "$STATUS_DIR" ]; then
  job_query "$STATUS_DIR" ""
  exit "$QUERY_RC"
fi
if [ -n "$WAIT_DIR" ]; then
  [ -n "$WAIT_TIMEOUT" ] || WAIT_TIMEOUT=600
  job_query "$WAIT_DIR" "$WAIT_TIMEOUT"
  exit "$QUERY_RC"
fi

# detached child: publish our PID immediately so the parent can report it
if [ "$JOB_MODE" = "child" ] && [ -n "$JOB_DIR" ]; then
  mkdir -p "$JOB_DIR" 2>/dev/null || true
  printf '%s\n' "$$" > "$JOB_DIR/harness.pid" 2>/dev/null || true
fi

# ---------- normalize input injection arguments (M2-a) ----------
INPUT_VKS=""
if [ -n "$INPUT_KEYS" ]; then
  NEW_KEYS="$(printf '%s' "$INPUT_KEYS" | tr ',' ' ')"
  for _tok in $NEW_KEYS; do
    _tok="$(printf '%s' "$_tok" | tr -d '[:space:]' | tr 'a-z' 'A-Z')"
    [ -n "$_tok" ] || continue
    case "$_tok" in
      ENTER|RETURN) _vk=13 ;;
      SPACE) _vk=32 ;;
      ESC|ESCAPE) _vk=27 ;;
      TAB) _vk=9 ;;
      BACKSPACE|BACK) _vk=8 ;;
      UP) _vk=38 ;;
      DOWN) _vk=40 ;;
      LEFT) _vk=37 ;;
      RIGHT) _vk=39 ;;
      SHIFT) _vk=16 ;;
      CTRL|CONTROL) _vk=17 ;;
      ALT) _vk=18 ;;
      A|B|C|D|E|F|G|H|I|J|K|L|M|N|O|P|Q|R|S|T|U|V|W|X|Y|Z) _vk="$(printf '%d' "'$_tok")" ;;
      0|1|2|3|4|5|6|7|8|9) _vk=$((48 + _tok)) ;;
      *)
        case "$_tok" in
          ''|*[!0-9]*) fail_early "input_keys_invalid" "unknown key name: $_tok (use names like C,ENTER,SPACE or decimal VK codes)" ;;
          *) _vk="$_tok" ;;
        esac
        ;;
    esac
    INPUT_VKS="$INPUT_VKS${INPUT_VKS:+,}$_vk"
  done
  [ -n "$INPUT_VKS" ] || fail_early "input_keys_invalid" "--input-keys produced no usable key codes"
fi

vk_list_of() {
  # convert a comma key list (names or decimal VK codes) into a comma-separated VK list
  local _list="$1" _out="" _tok _vk="" _bad="" _sp
  _sp="$(printf '%s' "$_list" | tr ',' ' ')"
  for _tok in $_sp; do
    _tok="$(printf '%s' "$_tok" | tr -d '[:space:]' | tr 'a-z' 'A-Z')"
    [ -n "$_tok" ] || continue
    case "$_tok" in
      ENTER|RETURN) _vk=13 ;;
      SPACE) _vk=32 ;;
      ESC|ESCAPE) _vk=27 ;;
      TAB) _vk=9 ;;
      BACKSPACE|BACK) _vk=8 ;;
      UP) _vk=38 ;;
      DOWN) _vk=40 ;;
      LEFT) _vk=37 ;;
      RIGHT) _vk=39 ;;
      SHIFT) _vk=16 ;;
      CTRL|CONTROL) _vk=17 ;;
      ALT) _vk=18 ;;
      A|B|C|D|E|F|G|H|I|J|K|L|M|N|O|P|Q|R|S|T|U|V|W|X|Y|Z) _vk="$(printf '%d' "'$_tok")" ;;
      0|1|2|3|4|5|6|7|8|9) _vk=$((48 + _tok)) ;;
      *)
        case "$_tok" in
          ''|*[!0-9]*) _bad="$_tok" ;;
          *) _vk="$_tok" ;;
        esac
        ;;
    esac
    if [ -n "$_bad" ]; then break; fi
    _out="$_out${_out:+,}$_vk"
  done
  if [ -n "$_bad" ]; then
    printf 'unknown key name: %s\n' "$_bad" >&2
    return 1
  fi
  printf '%s' "$_out"
}
INPUT_X=-1
INPUT_Y=-1
if [ -n "$INPUT_CLICK" ]; then
  case "$INPUT_CLICK" in
    *,*) : ;;
    *) fail_early "input_click_invalid" "--input-click expects X,Y pixel coordinates" ;;
  esac
  INPUT_X="$(printf '%s' "$INPUT_CLICK" | cut -d, -f1)"
  INPUT_Y="$(printf '%s' "$INPUT_CLICK" | cut -d, -f2)"
  case "$INPUT_X" in ''|*[!0-9]*) fail_early "input_click_invalid" "--input-click X must be a non-negative integer" ;; esac
  case "$INPUT_Y" in ''|*[!0-9]*) fail_early "input_click_invalid" "--input-click Y must be a non-negative integer" ;; esac
fi
if [ -z "$INPUT_DELAY" ]; then INPUT_DELAY=1500; fi
if [ -z "$INPUT_SETTLE" ]; then INPUT_SETTLE=1200; fi
if [ -z "$INPUT_HOLD" ]; then INPUT_HOLD=60; fi
if [ -z "$INPUT_GAP" ]; then INPUT_GAP=250; fi
INPUT_REGION_TOP=70
INPUT_REGION_BOTTOM=950
if [ -n "$INPUT_REGION" ]; then
  INPUT_REGION_TOP="$(printf '%s' "$INPUT_REGION" | cut -d, -f1)"
  INPUT_REGION_BOTTOM="$(printf '%s' "$INPUT_REGION" | cut -d, -f2)"
  case "$INPUT_REGION_TOP" in ''|*[!0-9]*) fail_early "input_region_invalid" "--input-region expects TOP,BOTTOM integers" ;; esac
  case "$INPUT_REGION_BOTTOM" in ''|*[!0-9]*) fail_early "input_region_invalid" "--input-region expects TOP,BOTTOM integers" ;; esac
fi

# ---------- multi-step input script normalization (P1-a) ----------
STEP_KINDS=()
STEP_ARGS=()
STEP_ARGS2=()
STEP_LABELS=()
if [ -z "$INPUT_STEPS" ] && [ -n "$INPUT_STEPS_FILE" ]; then INPUT_STEPS="@$INPUT_STEPS_FILE"; fi
if [ -n "$INPUT_STEPS" ] && [ -f "$INPUT_STEPS" ]; then INPUT_STEPS="@$INPUT_STEPS"; fi
if [ -n "$INPUT_STEPS" ]; then
  case "$INPUT_STEPS" in
    @*)
      _steps_json="$(printf '%s' "$INPUT_STEPS" | sed 's/^@//')"
      [ -f "$_steps_json" ] || fail_early "input_steps_invalid" "--input-steps @file not found: $_steps_json"
      _steps_norm="$(node -e '
const fs=require("fs");
const p=process.argv[1];
let raw;
try{raw=fs.readFileSync(p,"utf8");}catch(e){console.error("read error: "+e.message);process.exit(2);}
let a;
try{a=JSON.parse(raw);}catch(e){console.error("JSON parse error: "+e.message);process.exit(3);}
if(!Array.isArray(a)){console.error("steps JSON must be an array");process.exit(4);}
const out=[];
for(let i=0;i<a.length;i++){
  const s=a[i]||{};
  const act=String(s.action||"").toLowerCase();
  if(act==="click"){ if(!Number.isInteger(s.x)||!Number.isInteger(s.y)){console.error("step "+i+": click needs integer x,y");process.exit(5);} out.push("click:"+s.x+","+s.y); }
  else if(act==="pclick"||act==="prclick"){ if(!Number.isInteger(s.x)||!Number.isInteger(s.y)){console.error("step "+i+": pclick needs integer x,y");process.exit(5);} out.push(act+":"+s.x+","+s.y); }
  else if(act==="key"){ const k=String(s.keys||s.key||""); if(!k){console.error("step "+i+": key needs keys");process.exit(6);} out.push("key:"+k); }
  else if(act==="wait"){ const ms=Number(s.ms); if(!Number.isFinite(ms)||ms<0){console.error("step "+i+": wait needs ms");process.exit(7);} out.push("wait:"+Math.round(ms)); }
  else if(act==="capture"){ let n=String(s.name||("shot"+(i+1))).replace(/[^A-Za-z0-9._-]/g,"_"); out.push("capture:"+n); }
  else { console.error("step "+i+": unknown action: "+act); process.exit(8); }
}
process.stdout.write(out.join(";"));
' "$_steps_json")" || fail_early "input_steps_invalid" "cannot parse --input-steps JSON file: $_steps_json"
      INPUT_STEPS="$_steps_norm"
      ;;
  esac
  _old_ifs="$IFS"
  IFS=';' read -r -a _raw_steps <<< "$INPUT_STEPS"
  IFS="$_old_ifs"
  for _rs in "${_raw_steps[@]}"; do
    _st="$(printf '%s' "$_rs" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [ -n "$_st" ] || continue
    case "$_st" in
      click:*)
        _p="$(printf '%s' "$_st" | sed 's/^click://')"
        case "$_p" in
          *,*) : ;;
          *) fail_early "input_steps_invalid" "step click needs X,Y: $_st" ;;
        esac
        _sx="$(printf '%s' "$_p" | cut -d, -f1)"
        _sy="$(printf '%s' "$_p" | cut -d, -f2)"
        case "$_sx" in ''|*[!0-9]*) fail_early "input_steps_invalid" "step click X must be a non-negative integer: $_st" ;; esac
        case "$_sy" in ''|*[!0-9]*) fail_early "input_steps_invalid" "step click Y must be a non-negative integer: $_st" ;; esac
        STEP_KINDS+=("click"); STEP_ARGS+=("$_sx"); STEP_ARGS2+=("$_sy"); STEP_LABELS+=("click:$_sx,$_sy")
        ;;
      pclick:*|prclick:*)
        _kind="${_st%%:*}"
        _p="$(printf '%s' "$_st" | sed 's/^pclick://; s/^prclick://')"
        case "$_p" in
          *,*) : ;;
          *) fail_early "input_steps_invalid" "step $_kind needs X,Y: $_st" ;;
        esac
        _sx="$(printf '%s' "$_p" | cut -d, -f1)"
        _sy="$(printf '%s' "$_p" | cut -d, -f2)"
        case "$_sx" in ''|*[!0-9]*) fail_early "input_steps_invalid" "step $_kind X must be a non-negative integer: $_st" ;; esac
        case "$_sy" in ''|*[!0-9]*) fail_early "input_steps_invalid" "step $_kind Y must be a non-negative integer: $_st" ;; esac
        STEP_KINDS+=("$_kind"); STEP_ARGS+=("$_sx"); STEP_ARGS2+=("$_sy"); STEP_LABELS+=("$_kind:$_sx,$_sy")
        ;;
      key:*)
        _p="$(printf '%s' "$_st" | sed 's/^key://')"
        _vklist="$(vk_list_of "$_p")" || fail_early "input_steps_invalid" "step key has an unknown key name: $_st"
        [ -n "$_vklist" ] || fail_early "input_steps_invalid" "step key produced no VK codes: $_st"
        STEP_KINDS+=("key"); STEP_ARGS+=("$_vklist"); STEP_ARGS2+=(""); STEP_LABELS+=("key:$_p")
        ;;
      wait:*)
        _p="$(printf '%s' "$_st" | sed 's/^wait://')"
        case "$_p" in ''|*[!0-9]*) fail_early "input_steps_invalid" "step wait needs milliseconds: $_st" ;; esac
        STEP_KINDS+=("wait"); STEP_ARGS+=("$_p"); STEP_ARGS2+=(""); STEP_LABELS+=("wait:$_p")
        ;;
      capture:*)
        _p="$(printf '%s' "$_st" | sed 's/^capture://')"
        [ -n "$_p" ] || _p="shot"
        _p="$(printf '%s' "$_p" | sed 's/[^A-Za-z0-9._-]/_/g')"
        STEP_KINDS+=("capture"); STEP_ARGS+=("$_p"); STEP_ARGS2+=(""); STEP_LABELS+=("capture:$_p")
        ;;
      *) fail_early "input_steps_invalid" "unknown step (use click:X,Y / key:LIST / wait:MS / capture:NAME): $_st" ;;
    esac
  done
  [ "${#STEP_KINDS[@]}" -gt 0 ] || fail_early "input_steps_invalid" "--input-steps produced no steps"
  log "input steps: ${#STEP_KINDS[@]} step(s) parsed"
fi
sleep_ms() {
  sleep "$(awk -v ms="$1" 'BEGIN { printf "%.3f", ms / 1000 }')" 2>/dev/null || sleep 1
}

# ---------- argument validation ----------
if [ -n "$GAME" ] && [ -n "$NRO" ] && [ "$GAME" != "$NRO" ]; then
  fail_early "argument_conflict" "pass either --nro or --game/--nsp, not both"
fi
if [ -n "$GAME" ] && [ -z "$NRO" ]; then NRO="$GAME"; fi
[ -n "$NRO" ] || fail_early "argument_missing" "one of --nro / --game / --nsp is required (see --help)"
[ -f "$NRO" ] || fail_early "game_not_found" "$NRO"
case "$TIMEOUT" in ''|*[!0-9]*) fail_early "bad_argument" "--timeout must be a non-negative integer" ;; esac
case "$SETTLE" in ''|*[!0-9]*) fail_early "bad_argument" "--settle must be a non-negative integer" ;; esac

NRO_ABS="$(cd "$(dirname "$NRO")" && pwd)/$(basename "$NRO")"
NRO_BASE="$(basename "$NRO_ABS")"
GAME_LOWER="$(printf '%s' "$NRO_BASE" | tr 'A-Z' 'a-z')"
GAME_TYPE="unknown"
case "$GAME_LOWER" in
  *.nro) GAME_TYPE="nro" ;;
  *.nsp) GAME_TYPE="nsp" ;;
  *.nsz) GAME_TYPE="nsz" ;;
  *.xci) GAME_TYPE="xci" ;;
  *.xcz) GAME_TYPE="xcz" ;;
esac
if [ "$GAME_TYPE" = "unknown" ]; then
  log "WARNING: unrecognised game file extension in '$NRO_BASE' (expected .nro/.nsp/.xci/.nsz/.xcz); passing it to Citron anyway"
fi
STEM="$(printf '%s' "$NRO_BASE" | sed -E 's/\.(nro|nsp|nsz|xci|xcz)$//')"
[ -n "$EXPECT_TITLE" ] || EXPECT_TITLE="$STEM"

# ---------- locate citron.exe ----------
CITRON_EXE=""
if [ -n "$CITRON_EXE_ARG" ] && [ -f "$CITRON_EXE_ARG" ]; then
  CITRON_EXE="$(cd "$(dirname "$CITRON_EXE_ARG")" && pwd)/$(basename "$CITRON_EXE_ARG")"
fi
if [ -z "$CITRON_EXE" ]; then
  for cand in "$REPO_ROOT/workspaces/citron-harness/citron/citron.exe" \
              "$REPO_ROOT/workspaces/web-02/citron/citron.exe" \
              "$REPO_ROOT"/workspaces/*/citron/citron.exe; do
    [ -f "$cand" ] && { CITRON_EXE="$(cd "$(dirname "$cand")" && pwd)/$(basename "$cand")"; break; }
  done
fi
[ -n "$CITRON_EXE" ] || fail_early "citron_exe_missing" "pass --citron-exe PATH or set CITRON_EXE"
CITRON_DIR="$(dirname "$CITRON_EXE")"

# ---------- resolve Citron user dir (portable 'user/' next to exe wins, else %APPDATA%/citron) ----------
USER_DIR=""
if [ -n "$CITRON_USER_DIR" ] && [ -d "$CITRON_USER_DIR" ]; then
  USER_DIR="$(cd "$CITRON_USER_DIR" && pwd)"
elif [ -d "$CITRON_DIR/user" ]; then
  USER_DIR="$CITRON_DIR/user"   # Citron portable layout: <exe dir>/user/{keys,log,sdmc,...}
elif [ -n "$APPDATA" ] && [ -d "$(cygpath -u "$APPDATA")/citron" ]; then
  USER_DIR="$(cygpath -u "$APPDATA")/citron"
fi
[ -n "$USER_DIR" ] || fail_early "citron_user_dir_missing" "run Citron once, or set CITRON_USER_DIR"

# log path used by Citron dev builds (always-on log; see docs/environment/citron-harness.md)
LOG_RAW="$USER_DIR/log/citron_log.txt"

# keys: existence/size check only -- contents are never read, printed or copied
[ -s "$USER_DIR/keys/prod.keys" ] || fail_early "keys_missing" "expected $USER_DIR/keys/prod.keys (user-provided; this script never copies keys)"

# ---------- resolve virtual SD root ----------
SD=""
if [ -n "$SD_ARG" ]; then
  SD="$(cd "$SD_ARG" 2>/dev/null && pwd)" || fail_early "sd_missing" "--sd not a directory: $SD_ARG"
elif [ -d "$USER_DIR/sdmc" ]; then
  SD="$USER_DIR/sdmc"
fi
[ -n "$SD" ] || fail_early "sd_missing" "expected $USER_DIR/sdmc"

# ---------- detach mode: parent returns at once, detached child does the work (P3-d) ----------
if [ "$DETACH" = "1" ] && [ "$JOB_MODE" != "child" ]; then
  detach_launch
fi

# ---------- run archive dir ----------
[ -n "$OUT_ROOT" ] || OUT_ROOT="$REPO_ROOT/workspaces/citron-harness/runs"
if [ "$JOB_MODE" = "child" ]; then
  [ -n "$JOB_DIR" ] || fail_early "job_dir_missing" "--job-mode child requires --job-dir"
  RUN_DIR="$JOB_DIR"
  mkdir -p "$RUN_DIR" || fail_early "run_dir_unwritable" "$RUN_DIR"
  RUN_ID="$(basename "$RUN_DIR")"
else
  mkdir -p "$OUT_ROOT" || fail_early "run_dir_unwritable" "$OUT_ROOT"
  RUN_ID="$(date +%Y%m%d-%H%M%S)-$STEM"
  RUN_DIR="$OUT_ROOT/$RUN_ID"
  mkdir -p "$RUN_DIR" || fail_early "run_dir_unwritable" "$RUN_DIR"
fi
RUN_LOG="$RUN_DIR/run.log"
: > "$RUN_LOG"
J_RUNDIR="$(win_path "$RUN_DIR")"

# ---------- embedded window helper (PowerShell 5.1; written into the run archive) ----------
WIN_PS="$RUN_DIR/citron_win.ps1"
cat > "$WIN_PS" <<'PSEOF'
param(
  [Parameter(Mandatory=$true)][ValidateSet('list','capture','kill','input','diff','clickpost')][string]$Mode,
  [string]$Hwnd = '',
  [string]$Out = '',
  [string]$Pids = '',
  [string]$Vks = '',
  [int]$X = -1,
  [int]$Y = -1,
  [int]$HoldMs = 60,
  [int]$GapMs = 250,
  [string]$Button = 'left',
  [string]$Before = '',
  [string]$After = '',
  [int]$RegionTop = 70,
  [int]$RegionBottom = 950
)
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Threading;
public class CitronWin {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint flags);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hwnd, ref POINT pt);
  [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr hwnd, ref POINT pt);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT pt);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, IntPtr pid);
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint attach, uint attachTo, bool doAttach);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
  [DllImport("user32.dll", SetLastError=true)] public static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint mapType);
  [DllImport("user32.dll", EntryPoint = "GetWindowThreadProcessId")] public static extern uint GetWindowThreadProcessIdOut(IntPtr hwnd, out uint pid);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr hwnd, System.Text.StringBuilder name, int max);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hwnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, ChildProc cb, IntPtr param);
  public delegate bool ChildProc(IntPtr hwnd, IntPtr param);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
  public static string[] Children(IntPtr parent) {
    System.Collections.Generic.List<string> acc = new System.Collections.Generic.List<string>();
    EnumChildWindows(parent, delegate(IntPtr c, IntPtr q) {
      RECT cr;
      GetClientRect(c, out cr);
      System.Text.StringBuilder sb = new System.Text.StringBuilder(256);
      GetClassName(c, sb, 256);
      uint cpid;
      GetWindowThreadProcessIdOut(c, out cpid);
      acc.Add(c.ToInt64().ToString("X8") + "|" + sb.ToString() + "|" + (cr.Right - cr.Left) + "|" + (cr.Bottom - cr.Top) + "|" + (IsWindowVisible(c) ? 1 : 0) + "|" + cpid);
      return true;
    }, IntPtr.Zero);
    return acc.ToArray();
  }
  public static long[] Rect(IntPtr h) {
    RECT r;
    if (!GetWindowRect(h, out r)) return new long[0];
    return new long[] { r.Left, r.Top, r.Right, r.Bottom };
  }
}
'@
[CitronWin]::SetProcessDPIAware() | Out-Null

function Get-NonBlackRatio($bmp, $step) {
  $total = 0
  $nb = 0
  for ($y = 0; $y -lt $bmp.Height; $y += $step) {
    for ($x = 0; $x -lt $bmp.Width; $x += $step) {
      $c = $bmp.GetPixel($x, $y)
      $total = $total + 1
      if (($c.R -gt 8) -or ($c.G -gt 8) -or ($c.B -gt 8)) { $nb = $nb + 1 }
    }
  }
  if ($total -eq 0) { return [double]0 }
  return [math]::Round([double]$nb / [double]$total, 4)
}

if ($Mode -eq 'list') {
  Get-Process -Name citron -ErrorAction SilentlyContinue | ForEach-Object {
    $proc = $_
    if ($proc.MainWindowHandle -ne 0) {
      $hw = '0x' + ([int64]$proc.MainWindowHandle).ToString('X8')
      Write-Output ('W' + [char]9 + $proc.Id + [char]9 + $hw + [char]9 + $proc.Responding + [char]9 + $proc.MainWindowTitle)
    } else {
      Write-Output ('P' + [char]9 + $proc.Id + [char]9 + $proc.Responding)
    }
  }
  exit 0
}

if ($Mode -eq 'kill') {
  $items = $Pids -split ','
  foreach ($it in $items) {
    $n = 0
    if ([int]::TryParse($it.Trim(), [ref]$n)) {
      Stop-Process -Id $n -Force -ErrorAction SilentlyContinue
    }
  }
  Write-Output 'KILLED'
  exit 0
}

if ($Mode -eq 'capture') {
  $hex = $Hwnd -replace '^0x', ''
  $h = [IntPtr]([Convert]::ToInt64($hex, 16))
  if ([CitronWin]::IsIconic($h)) { [CitronWin]::ShowWindow($h, 9) | Out-Null; Start-Sleep -Milliseconds 500 }
  $rc = [CitronWin]::Rect($h)
  if ($rc.Length -eq 0) { Write-Output ('ERR' + [char]9 + 'GetWindowRect failed'); exit 1 }
  $w = [int]($rc[2] - $rc[0])
  $ht = [int]($rc[3] - $rc[1])
  if (($w -le 0) -or ($ht -le 0)) { Write-Output ('ERR' + [char]9 + 'empty window rect'); exit 1 }
  $method = 'printwindow'
  $bmp = New-Object System.Drawing.Bitmap($w, $ht)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  $ok = [CitronWin]::PrintWindow($h, $hdc, 2)
  $g.ReleaseHdc($hdc)
  $g.Dispose()
  $ratio = Get-NonBlackRatio $bmp 4
  if ((-not $ok) -or ($ratio -lt 0.02)) {
    $method = 'copyfromscreen'
    $g2 = [System.Drawing.Graphics]::FromImage($bmp)
    $g2.Clear([System.Drawing.Color]::Black)
    [CitronWin]::SetForegroundWindow($h) | Out-Null
    Start-Sleep -Milliseconds 500
    $sz = New-Object System.Drawing.Size($w, $ht)
    $g2.CopyFromScreen([int]$rc[0], [int]$rc[1], 0, 0, $sz)
    $g2.Dispose()
    $ratio = Get-NonBlackRatio $bmp 4
  }
  $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  $bytes = 0
  try { $bytes = (Get-Item $Out).Length } catch { $bytes = 0 }
  Write-Output ('OK' + [char]9 + $method + [char]9 + $bytes + [char]9 + $ratio)
  exit 0
}

if ($Mode -eq 'diff') {
  $b1 = New-Object System.Drawing.Bitmap($Before)
  $b2 = New-Object System.Drawing.Bitmap($After)
  $w = [math]::Min($b1.Width, $b2.Width)
  $h = [math]::Min($b1.Height, $b2.Height)
  $top = [math]::Max(0, $RegionTop)
  $bot = [math]::Min($h, $RegionBottom)
  $diff = 0
  $total = 0
  for ($y = $top; $y -lt $bot; $y += 2) {
    for ($x = 0; $x -lt $w; $x += 2) {
      $c1 = $b1.GetPixel($x, $y)
      $c2 = $b2.GetPixel($x, $y)
      $d = [math]::Abs([int]$c1.R - [int]$c2.R) + [math]::Abs([int]$c1.G - [int]$c2.G) + [math]::Abs([int]$c1.B - [int]$c2.B)
      if ($d -gt 30) { $diff = $diff + 1 }
      $total = $total + 1
    }
  }
  $ratio = 0
  if ($total -gt 0) { $ratio = [math]::Round([double]$diff / [double]$total, 6) }
  $nb1 = Get-NonBlackRatio $b1 4
  $nb2 = Get-NonBlackRatio $b2 4
  Write-Output ('OK' + [char]9 + $ratio + [char]9 + $nb1 + [char]9 + $nb2 + [char]9 + $total + [char]9 + ($w.ToString() + 'x' + $h.ToString()) + [char]9 + $top + [char]9 + $bot)
  $b1.Dispose()
  $b2.Dispose()
  exit 0
}

if ($Mode -eq 'clickpost') {
  # R10 workaround v2 (2026-10-30). Two facts from Citron source decide the design:
  # 1) GRenderWindow sets WA_NativeWindow, so it owns a native CHILD hwnd; mouse messages
  #    posted to the top-level window never reach it -> post to the largest visible child.
  # 2) GRenderWindow::mousePressEvent/mouseMoveEvent ignore the posted lParam position and
  #    use mapFromGlobal(QCursor::pos()) instead -> the real cursor must be moved first
  #    (SetCursorPos needs no foreground), then post WM_MOUSEMOVE/LBUTTONDOWN/UP.
  $hex = $Hwnd -replace '^0x', ''
  $h = [IntPtr]([Convert]::ToInt64($hex, 16))
  if ([CitronWin]::IsIconic($h)) { [CitronWin]::ShowWindow($h, 9) | Out-Null; Start-Sleep -Milliseconds 400 }
  $rc = [CitronWin]::Rect($h)
  if ($rc.Length -eq 0) { Write-Output ('ERR' + [char]9 + 'GetWindowRect failed'); exit 1 }
  $sx = [int]$rc[0] + [int]$X
  $sy = [int]$rc[1] + [int]$Y
  $kids = [CitronWin]::Children($h)
  $target = $h
  $bestArea = 0
  $chosen = 'toplevel'
  foreach ($k in $kids) {
    $parts = $k -split '\|'
    if ([int]$parts[4] -ne 1) { continue }
    $area = [int]$parts[2] * [int]$parts[3]
    if ($area -gt $bestArea) { $bestArea = $area; $target = [IntPtr]([Convert]::ToInt64($parts[0], 16)); $chosen = ($parts[1] + ' ' + $parts[2] + 'x' + $parts[3] + ' pid=' + $parts[5]) }
  }
  $pt = New-Object 'CitronWin+POINT'
  $pt.X = $sx; $pt.Y = $sy
  [CitronWin]::ScreenToClient($target, [ref]$pt) | Out-Null
  $cx = [int]$pt.X
  $cy = [int]$pt.Y
  [CitronWin]::SetCursorPos($sx, $sy) | Out-Null
  Start-Sleep -Milliseconds 150
  $lp = [IntPtr]([int64]((($cy -band 0xFFFF) -shl 16) -bor ($cx -band 0xFFFF)))
  [CitronWin]::PostMessage($target, 0x0200, [IntPtr]::Zero, $lp) | Out-Null
  Start-Sleep -Milliseconds 100
  if ($Button -eq 'right') {
    [CitronWin]::PostMessage($target, 0x0204, [IntPtr]2, $lp) | Out-Null
    Start-Sleep -Milliseconds 90
    [CitronWin]::PostMessage($target, 0x0205, [IntPtr]::Zero, $lp) | Out-Null
  } else {
    [CitronWin]::PostMessage($target, 0x0201, [IntPtr]1, $lp) | Out-Null
    Start-Sleep -Milliseconds 90
    [CitronWin]::PostMessage($target, 0x0202, [IntPtr]::Zero, $lp) | Out-Null
  }
  Start-Sleep -Milliseconds 150
  Write-Output ('OK' + [char]9 + $cx + [char]9 + $cy + [char]9 + $Button + [char]9 + $chosen + [char]9 + $kids.Count)
  exit 0
}

if ($Mode -eq 'input') {
  $hex = $Hwnd -replace '^0x', ''
  $h = [IntPtr]([Convert]::ToInt64($hex, 16))
  if ([CitronWin]::IsIconic($h)) { [CitronWin]::ShowWindow($h, 9) | Out-Null; Start-Sleep -Milliseconds 400 }
  $focusOk = 0
  $clicks = 0
  $keysSent = 0
  $cx = -1
  $cy = -1
  if (($X -ge 0) -and ($Y -ge 0)) {
    $rc = [CitronWin]::Rect($h)
    if ($rc.Length -eq 0) { Write-Output ('ERR' + [char]9 + 'GetWindowRect failed'); exit 1 }
    $fx = [int]$rc[0] + $X
    $fy = [int]$rc[1] + $Y
    $fg = [CitronWin]::GetForegroundWindow()
    $curThread = [CitronWin]::GetCurrentThreadId()
    $fgThread = [CitronWin]::GetWindowThreadProcessId($fg, [IntPtr]::Zero)
    [CitronWin]::AttachThreadInput($curThread, $fgThread, $true) | Out-Null
    [CitronWin]::BringWindowToTop($h) | Out-Null
    [CitronWin]::SetForegroundWindow($h) | Out-Null
    Start-Sleep -Milliseconds 200
    [CitronWin]::AttachThreadInput($curThread, $fgThread, $false) | Out-Null
    [CitronWin]::SetCursorPos(([int]$rc[0] + 8), ([int]$rc[1] + 8)) | Out-Null
    Start-Sleep -Milliseconds 120
    [CitronWin]::SetCursorPos($fx, $fy) | Out-Null
    Start-Sleep -Milliseconds 120
    [CitronWin]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 90
    [CitronWin]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 150
    $clicks = 1
    try {
      $pt = New-Object 'CitronWin+POINT'
      if ([CitronWin]::GetCursorPos([ref]$pt)) { $cx = $pt.X; $cy = $pt.Y }
    } catch { $cx = -1; $cy = -1 }
    if ([CitronWin]::GetForegroundWindow() -eq $h) { $focusOk = 1 }
  }
  if (($Vks -ne '') -and ($Vks -ne 'none')) {
    foreach ($v in ($Vks -split ',')) {
      $n = 0
      if (-not [int]::TryParse($v.Trim(), [ref]$n)) { continue }
      $scan = [int][CitronWin]::MapVirtualKey([uint32]$n, 0)
      $lpD = [IntPtr]([int64](1 -bor ($scan -shl 16)))
      $lpU = [IntPtr]([int64](1 -bor ($scan -shl 16) -bor 0xC0000000))
      [CitronWin]::PostMessage($h, 0x0100, [IntPtr]$n, $lpD) | Out-Null
      Start-Sleep -Milliseconds $HoldMs
      [CitronWin]::PostMessage($h, 0x0101, [IntPtr]$n, $lpU) | Out-Null
      $keysSent = $keysSent + 1
      Start-Sleep -Milliseconds $GapMs
    }
  }
  Write-Output ('OK' + [char]9 + $focusOk + [char]9 + $clicks + [char]9 + $keysSent + [char]9 + $cx + [char]9 + $cy)
  exit 0
}
PSEOF
PS_WIN="$(win_path "$WIN_PS")"
run_win() { "$POWERSHELL" -NoProfile -ExecutionPolicy Bypass -File "$PS_WIN" "$@" 2>/dev/null; }

# ---------- elevation detection (elevated shells need a de-elevation hop: runas /trustlevel) ----------
IS_ELEVATED=0
if net session >/dev/null 2>&1; then IS_ELEVATED=1; fi
J_ELEVATED="$IS_ELEVATED"
log "shell elevated: $IS_ELEVATED"

# ---------- pre-flight: refuse to launch on top of an existing Citron instance ----------
PRE_LIST="$(run_win -Mode list)"
PRE_PIDS=""
while IFS=$'\t' read -r kind a b c; do
  [ -n "$kind" ] || continue
  case "$kind" in
    P) PRE_PIDS="$PRE_PIDS $a" ;;
    W) PRE_PIDS="$PRE_PIDS $a" ;;
  esac
done <<< "$PRE_LIST"
PRE_PIDS="$(printf '%s' "$PRE_PIDS" | sed 's/^ *//')"
if [ -n "$PRE_PIDS" ]; then
  if [ "$ALLOW_EXISTING" = "1" ]; then
    log "WARNING: existing citron pid(s) $PRE_PIDS, continuing (--allow-existing)"
  else
    fail_now "citron_already_running" "existing citron pid(s): $PRE_PIDS (close them or pass --allow-existing)"
  fi
fi

# ---------- stage the game file into the virtual SD (offsets/size only; contents are user data) ----------
STAGE_DIR="$SD/switch/galnx-harness"
if [ "$NO_STAGE" = "1" ]; then
  # --no-stage: launch the file in place (needed for multi-GB NSPs that must not be copied into sdmc).
  STAGED="$NRO_ABS"
  log "game file: not staged (--no-stage); launching in place: $STAGED"
else
  mkdir -p "$STAGE_DIR" || fail_now "stage_failed" "cannot create $STAGE_DIR"
  STAGED="$STAGE_DIR/$NRO_BASE"
  cp -f "$NRO_ABS" "$STAGED" || fail_now "stage_failed" "cannot copy game file to $STAGED"
fi
case "$GAME_TYPE" in
  nro)
    MAGIC="$(dd if="$STAGED" bs=1 skip=16 count=4 2>/dev/null | tr -d '\000')"
    [ "$MAGIC" = "NRO0" ] || log "WARNING: NRO magic at offset 0x10 is '$MAGIC', expected 'NRO0' (continuing)"
    ;;
  nsp|nsz)
    MAGIC="$(dd if="$STAGED" bs=1 skip=0 count=4 2>/dev/null | tr -d '\000')"
    [ "$MAGIC" = "PFS0" ] || log "WARNING: $GAME_TYPE magic at offset 0x0 is '$MAGIC', expected 'PFS0' (continuing)"
    ;;
  xci|xcz)
    MAGIC="$(dd if="$STAGED" bs=1 skip=256 count=4 2>/dev/null | tr -d '\000')"
    [ "$MAGIC" = "HEAD" ] || log "WARNING: $GAME_TYPE magic at offset 0x100 is '$MAGIC', expected 'HEAD' (continuing)"
    ;;
esac
J_STAGED="$(win_path "$STAGED")"
J_EXE="$(win_path "$CITRON_EXE")"
J_NRO="$NRO_ABS"
J_GAMETYPE="$GAME_TYPE"
J_GAMEPATH="$NRO_ABS"
J_STAGEPATH="$STAGED"
J_EXPECT="$EXPECT_TITLE"
log "game file: $NRO_ABS (type=$GAME_TYPE) staged at $STAGED"

# ---------- launch (cmd wrapper; elevated shells hop to medium integrity via Task Scheduler, fallback runas) ----------
LAUNCH_EPOCH="$(date +%s)"
LOG_BASE_SIZE=0
LOG_BASE_MTIME=0
if [ -f "$LOG_RAW" ]; then
  LOG_BASE_SIZE="$(stat -c %s "$LOG_RAW" 2>/dev/null || echo 0)"
  LOG_BASE_MTIME="$(stat -c %Y "$LOG_RAW" 2>/dev/null || echo 0)"
fi
WRAP_DIR="/c/ProgramData/galnx-harness"
case "$WRAP_DIR" in *" "*) WRAP_DIR="/c/Windows/Temp/galnx-harness" ;; esac
mkdir -p "$WRAP_DIR" || fail_now "wrapper_dir_unavailable" "no writable space-free wrapper dir"
WRAP="$WRAP_DIR/launch-$RUN_ID.cmd"
{
  printf '@echo off\r\n'
  printf 'cd /d "%s"\r\n' "$(win_path "$CITRON_DIR")"
  printf 'start "" "%s" -g "%s"\r\n' "$(win_path "$CITRON_EXE")" "$(win_path "$STAGED")"
} > "$WRAP"
WRAP_WIN="$(win_path "$WRAP")"
TASK_NAME=""
LAUNCH_MODE=""
if [ "$IS_ELEVATED" = "1" ]; then
  # Citron refuses to run elevated: launch the wrapper as a one-shot task at medium integrity.
  # Preferred route is Task Scheduler (works when runas/Start-Process silently fail); runas is the fallback.
  TASK_NAME="GalNXHarness-$RUN_ID"
  TASK_NAME="$(printf '%s' "$TASK_NAME" | tr -c 'A-Za-z0-9._-' '_')"
  schtasks //Create //TN "$TASK_NAME" //TR "cmd.exe /c \"$WRAP_WIN\"" //SC ONCE //ST 23:59 //RL LIMITED //IT //F >/dev/null 2>&1
  CREATE_RC=$?
  if [ "$CREATE_RC" -eq 0 ]; then
    schtasks //Run //TN "$TASK_NAME" >/dev/null 2>&1 || true
    sleep 2
    TASK_RC="$("$POWERSHELL" -NoProfile -Command "(Get-ScheduledTaskInfo -TaskName '$TASK_NAME').LastTaskResult" 2>/dev/null | tr -d '\r' | tail -n 1)"
    case "$TASK_RC" in
      0|267009) LAUNCH_MODE="schtasks-limited" ;;
      *) LAUNCH_MODE="" ;;
    esac
  fi
  if [ -z "$LAUNCH_MODE" ]; then
    schtasks //Delete //TN "$TASK_NAME" //F >/dev/null 2>&1 || true
    TASK_NAME=""
    "$POWERSHELL" -NoProfile -Command "Start-Process -FilePath 'runas.exe' -ArgumentList '/trustlevel:0x20000','$WRAP_WIN'" >/dev/null 2>&1
    LAUNCH_MODE="runas-deelevated"
  fi
else
  LAUNCH_MODE="direct"
  "$POWERSHELL" -NoProfile -Command "Start-Process -FilePath '$WRAP_WIN'" >/dev/null 2>&1
fi
printf 'launch mode : %s\nwrapper     : %s\ncmdline     : "%s" -g "%s"\n' "$LAUNCH_MODE" "$WRAP_WIN" "$(win_path "$CITRON_EXE")" "$(win_path "$STAGED")" >> "$RUN_LOG"
printf 'game type   : %s\ngame path   : %s\nstage path  : %s\n' "$GAME_TYPE" "$NRO_ABS" "$STAGED" >> "$RUN_LOG"
printf 'log baseline: size=%s mtime=%s\n' "$LOG_BASE_SIZE" "$LOG_BASE_MTIME" >> "$RUN_LOG"
log "launched via $LAUNCH_MODE; polling up to $TIMEOUT s for boot evidence"

# ---------- poll window + log for boot evidence ----------
CAP_PID=""
CAP_HWND=""
CAP_TITLE=""
BOOT_LINE=""
BUILD_LINE=""
EXC_LINE=""
LOAD_FAIL_LINE=""
SEE_NEW=""
DEAD=0
SLICE_FILE="$RUN_DIR/log_slice_latest.txt"
while :; do
  NOW="$(date +%s)"
  ELAPSED=$((NOW - LAUNCH_EPOCH))
  LIST_OUT="$(run_win -Mode list)"
  CUR_PIDS=""
  while IFS=$'\t' read -r kind a b resp c; do
    [ -n "$kind" ] || continue
    case "$kind" in
      P) CUR_PIDS="$CUR_PIDS $a" ;;
      W) CUR_PIDS="$CUR_PIDS $a"; CAP_PID="$a"; CAP_HWND="$b"; CAP_TITLE="$c" ;;
    esac
  done <<< "$LIST_OUT"
  for p in $CUR_PIDS; do
    case " $PRE_PIDS " in *" $p "*) continue ;; esac
    case " $SEE_NEW " in *" $p "*) continue ;; esac
    SEE_NEW="$SEE_NEW $p"
  done
  if [ -f "$LOG_RAW" ]; then
    slice_log "$LOG_RAW" > "$SLICE_FILE" 2>/dev/null || true
    BL="$(grep -aE 'BootGame: Booting game:' "$SLICE_FILE" | tail -n 1)"
    if [ -z "$BL" ] && [ "$GAME_TYPE" = "nro" ]; then
      BL="$(grep -aE 'BootGame: citron starting|Loading [^ ]+ \(' "$SLICE_FILE" | tail -n 1)"
    fi
    [ -n "$BL" ] && BOOT_LINE="$BL"
    VL="$(grep -aE 'citron Version:' "$LOG_RAW" 2>/dev/null | tail -n 1)"
    [ -n "$VL" ] && BUILD_LINE="$VL"
    XL="$(grep -aE 'Unhandled exception caught|Adler32|LoaderContext:.*failed' "$SLICE_FILE" | tail -n 1)"
    [ -n "$XL" ] && EXC_LINE="$XL"
    FL="$(grep -aE 'Failed to load ROM|LoadROM: Failed' "$SLICE_FILE" | tail -n 1)"
    [ -n "$FL" ] && LOAD_FAIL_LINE="$FL"
  fi
  if [ -n "$BOOT_LINE" ] && [ -n "$CAP_PID" ]; then break; fi
  if [ -z "$BOOT_LINE" ] && [ -n "$LOAD_FAIL_LINE" ]; then break; fi
  if [ -z "$BOOT_LINE" ] && [ -n "$SEE_NEW" ]; then
    if [ -z "$(printf '%s' "$CUR_PIDS" | tr -d ' ')" ]; then DEAD=1; break; fi
  fi
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then break; fi
  sleep 2
done
ELAPSED=$(( $(date +%s) - LAUNCH_EPOCH ))

# ---------- task cleanup (one-shot Task Scheduler task used only to launch the wrapper) ----------
if [ -n "$TASK_NAME" ]; then
  schtasks //Delete //TN "$TASK_NAME" //F >/dev/null 2>&1 || true
fi

# ---------- stale-log guard: if citron_log.txt did not move at all, Citron never started ----------
LOG_FRESH=1
if [ -f "$LOG_RAW" ]; then
  CUR_SIZE="$(stat -c %s "$LOG_RAW" 2>/dev/null || echo 0)"
  CUR_MTIME="$(stat -c %Y "$LOG_RAW" 2>/dev/null || echo 0)"
  if [ "$CUR_SIZE" = "$LOG_BASE_SIZE" ] && [ "$CUR_MTIME" = "$LOG_BASE_MTIME" ]; then LOG_FRESH=0; fi
else
  LOG_FRESH=0
fi
if [ "$LOG_FRESH" = "0" ]; then
  log "WARNING: citron log did not change since launch; discarding boot evidence (launcher may have failed)"
  BOOT_LINE=""; BUILD_LINE=""; EXC_LINE=""; LOAD_FAIL_LINE=""
fi

# ---------- settle, then capture the window ----------
J_TITLE="$CAP_TITLE"
if [ -n "$BOOT_LINE" ]; then
  sleep "$SETTLE"
  ELAPSED=$(( $(date +%s) - LAUNCH_EPOCH ))
  LIST_OUT="$(run_win -Mode list)"
  while IFS=$'\t' read -r kind a b resp c; do
    [ -n "$kind" ] || continue
    case "$kind" in
      W) CAP_PID="$a"; CAP_HWND="$b"; CAP_TITLE="$c" ;;
    esac
  done <<< "$LIST_OUT"
  J_TITLE="$CAP_TITLE"
fi

SHOT="$RUN_DIR/window.png"
if [ -n "$CAP_HWND" ]; then
  CAP_RES="$(run_win -Mode capture -Hwnd "$CAP_HWND" -Out "$(win_path "$SHOT")")"
  C1="$(printf '%s' "$CAP_RES" | awk -F'\t' '{print $1}')"
  if [ "$C1" = "OK" ]; then
    J_SHOT="$(win_path "$SHOT")"
    J_SHOT_METHOD="$(printf '%s' "$CAP_RES" | awk -F'\t' '{print $2}')"
    J_SHOT_BYTES="$(printf '%s' "$CAP_RES" | awk -F'\t' '{print $3}')"
    J_SHOT_NONBLACK="$(printf '%s' "$CAP_RES" | awk -F'\t' '{print $4}')"
  else
    log "capture failed: $CAP_RES"
  fi
else
  log "no citron window found; screenshot skipped"
fi

# ---------- optional input injection + before/after proof (M2-a) ----------
if [ -n "$INPUT_VKS" ] || [ "$INPUT_X" -ge 0 ]; then
  if [ -z "$CAP_HWND" ] || [ -z "$BOOT_LINE" ]; then
    J_INPUT_ERR="no_window_or_boot: input injection skipped (window=$CAP_HWND boot_line_empty=$([ -z "$BOOT_LINE" ] && echo 1 || echo 0))"
    log "input injection skipped: $J_INPUT_ERR"
  elif [ ! -s "$SHOT" ]; then
    J_INPUT_ERR="no_before_screenshot: input injection skipped because window.png is missing"
    log "input injection skipped: $J_INPUT_ERR"
  else
    log "input injection: waiting ${INPUT_DELAY} ms before injecting (keys='$INPUT_VKS' click='$INPUT_X,$INPUT_Y')"
    sleep_ms "$INPUT_DELAY"
    cp -f "$SHOT" "$RUN_DIR/window-before-input.png" 2>/dev/null || true
    J_INPUT_BEFORE="$(win_path "$RUN_DIR/window-before-input.png")"
    IN_RES="$(run_win -Mode input -Hwnd "$CAP_HWND" -Vks "$INPUT_VKS" -X "$INPUT_X" -Y "$INPUT_Y" -HoldMs "$INPUT_HOLD" -GapMs "$INPUT_GAP")"
    IN_OK="$(printf '%s' "$IN_RES" | awk -F'\t' '{print $1}')"
    if [ "$IN_OK" = "OK" ]; then
      J_INPUT_DONE=1
      J_INPUT_FOCUS="$(printf '%s' "$IN_RES" | awk -F'\t' '{print $2}')"
      J_INPUT_CLICKS="$(printf '%s' "$IN_RES" | awk -F'\t' '{print $3}')"
      IN_KEYS_SENT="$(printf '%s' "$IN_RES" | awk -F'\t' '{print $4}')"
      IN_CURSOR="$(printf '%s' "$IN_RES" | awk -F'\t' '{print $5 "," $6}')"
      J_INPUT_KEYS_SENT="$IN_KEYS_SENT"
      if [ "$IN_KEYS_SENT" = "0" ] && [ -n "$INPUT_VKS" ]; then
        J_INPUT_ERR="key_post_failed: helper posted 0 of the requested keys"
      fi
      log "input injected: focus_ok=$J_INPUT_FOCUS clicks=$J_INPUT_CLICKS keys_sent=$IN_KEYS_SENT cursor=$IN_CURSOR"
      sleep_ms "$INPUT_SETTLE"
      IAFTER="$RUN_DIR/window-after-input.png"
      CAP2="$(run_win -Mode capture -Hwnd "$CAP_HWND" -Out "$(win_path "$IAFTER")")"
      C2="$(printf '%s' "$CAP2" | awk -F'\t' '{print $1}')"
      if [ "$C2" = "OK" ]; then
        J_INPUT_AFTER="$(win_path "$IAFTER")"
        DIF_RES="$(run_win -Mode diff -Before "$(win_path "$RUN_DIR/window-before-input.png")" -After "$(win_path "$IAFTER")" -RegionTop "$INPUT_REGION_TOP" -RegionBottom "$INPUT_REGION_BOTTOM")"
        D1="$(printf '%s' "$DIF_RES" | awk -F'\t' '{print $1}')"
        if [ "$D1" = "OK" ]; then
          J_INPUT_DIFF="$(printf '%s' "$DIF_RES" | awk -F'\t' '{print $2}')"
          J_INPUT_NBB="$(printf '%s' "$DIF_RES" | awk -F'\t' '{print $3}')"
          J_INPUT_NBA="$(printf '%s' "$DIF_RES" | awk -F'\t' '{print $4}')"
          IN_PIXELS="$(printf '%s' "$DIF_RES" | awk -F'\t' '{print $5}')"
          J_INPUT_REGION="$(printf '%s' "$DIF_RES" | awk -F'\t' '{print $6 " y=" $7 "-" $8}')"
          log "input diff: ratio=$J_INPUT_DIFF over region y=$INPUT_REGION_TOP..$INPUT_REGION_BOTTOM ($IN_PIXELS sampled px); nonblack $J_INPUT_NBB -> $J_INPUT_NBA"
        else
          J_INPUT_ERR="diff_failed: $DIF_RES"
          log "input diff failed: $DIF_RES"
        fi
      else
        J_INPUT_ERR="after_screenshot_failed: $CAP2"
        log "after-input capture failed: $CAP2"
      fi
    else
      J_INPUT_ERR="input_helper_failed: $IN_RES"
      log "input helper failed: $IN_RES"
    fi
  fi
fi

# ---------- multi-step input script execution (P1-a) ----------
if [ "${#STEP_KINDS[@]}" -gt 0 ]; then
  if [ -z "$CAP_HWND" ] || [ -z "$BOOT_LINE" ]; then
    J_STEPS_ERR="no_window_or_boot: input steps skipped (window=$CAP_HWND boot_line_empty=$([ -z "$BOOT_LINE" ] && echo 1 || echo 0))"
    log "input steps skipped: $J_STEPS_ERR"
  elif [ ! -s "$SHOT" ]; then
    J_STEPS_ERR="no_before_screenshot: input steps skipped because window.png is missing"
    log "input steps skipped: $J_STEPS_ERR"
  else
    log "input steps: waiting ${INPUT_DELAY} ms before running ${#STEP_KINDS[@]} step(s)"
    sleep_ms "$INPUT_DELAY"
    STEPS_TSV="$RUN_DIR/input-steps.tsv"
    : > "$STEPS_TSV"
    STEPS_BEFORE="$RUN_DIR/window-steps-before.png"
    cp -f "$SHOT" "$STEPS_BEFORE" 2>/dev/null || true
    STEPS_TC=0
    STEPS_OK=0
    STEPS_FAILED=0
    for ((_si=0; _si<${#STEP_KINDS[@]}; _si++)); do
      _kind="${STEP_KINDS[$_si]}"
      _a="${STEP_ARGS[$_si]}"
      _b="${STEP_ARGS2[$_si]}"
      _label="${STEP_LABELS[$_si]}"
      _status="ok"
      _detail=""
      _shot=""
      _t0="$(date +%s%3N 2>/dev/null || date +%s)"
      case "$_kind" in
        click)
          _res="$(run_win -Mode input -Hwnd "$CAP_HWND" -X "$_a" -Y "$_b" -Vks "" -HoldMs "$INPUT_HOLD" -GapMs "$INPUT_GAP")"
          if [ "$(printf '%s' "$_res" | awk -F'\t' '{print $1}')" = "OK" ]; then
            _detail="focus_ok=$(printf '%s' "$_res" | awk -F'\t' '{print $2}')"
            J_INPUT_CLICKS=$((J_INPUT_CLICKS + 1))
          else
            _status="fail"; _detail="$_res"
          fi
          ;;
        pclick|prclick)
          _btn="left"; [ "$_kind" = "prclick" ] && _btn="right"
          _res="$(run_win -Mode clickpost -Hwnd "$CAP_HWND" -X "$_a" -Y "$_b" -Button "$_btn")"
          if [ "$(printf '%s' "$_res" | awk -F'\t' '{print $1}')" = "OK" ]; then
            _detail="button=$_btn client=$(printf '%s' "$_res" | awk -F'\t' '{print $2}'),$(printf '%s' "$_res" | awk -F'\t' '{print $3}')"
            J_INPUT_CLICKS=$((J_INPUT_CLICKS + 1))
          else
            _status="fail"; _detail="$_res"
          fi
          ;;
        key)
          _res="$(run_win -Mode input -Hwnd "$CAP_HWND" -X -1 -Y -1 -Vks "$_a" -HoldMs "$INPUT_HOLD" -GapMs "$INPUT_GAP")"
          if [ "$(printf '%s' "$_res" | awk -F'\t' '{print $1}')" = "OK" ]; then
            _sent="$(printf '%s' "$_res" | awk -F'\t' '{print $4}')"
            case "$_sent" in ''|*[!0-9]*) _sent=0 ;; esac
            _detail="keys_sent=$_sent"
            J_INPUT_KEYS_SENT=$((J_INPUT_KEYS_SENT + _sent))
          else
            _status="fail"; _detail="$_res"
          fi
          ;;
        wait)
          sleep_ms "$_a"
          _detail="waited ${_a}ms"
          ;;
        capture)
          _shot="$RUN_DIR/step-$(printf '%02d' $((_si + 1)))-$_a.png"
          _res="$(run_win -Mode capture -Hwnd "$CAP_HWND" -Out "$(win_path "$_shot")")"
          if [ "$(printf '%s' "$_res" | awk -F'\t' '{print $1}')" = "OK" ]; then
            _detail="bytes=$(printf '%s' "$_res" | awk -F'\t' '{print $3}') nonblack=$(printf '%s' "$_res" | awk -F'\t' '{print $4}')"
            _shot="$(win_path "$_shot")"
          else
            _status="fail"; _detail="$_res"; _shot=""
          fi
          ;;
      esac
      _t1="$(date +%s%3N 2>/dev/null || date +%s)"
      _ms=$((_t1 - _t0))
      STEPS_TC=$((STEPS_TC + 1))
      if [ "$_status" = "ok" ]; then STEPS_OK=$((STEPS_OK + 1)); else STEPS_FAILED=$((STEPS_FAILED + 1)); fi
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$_si" "$_kind" "$_label" "$_status" "$_detail" "$_shot" "$_ms" >> "$STEPS_TSV"
      log "input step $((_si + 1))/$STEPS_TC $_kind: $_status ($_detail)"
    done
    STEPS_FINAL="$RUN_DIR/window-steps-final.png"
    _fres="$(run_win -Mode capture -Hwnd "$CAP_HWND" -Out "$(win_path "$STEPS_FINAL")")"
    if [ "$(printf '%s' "$_fres" | awk -F'\t' '{print $1}')" = "OK" ]; then
      J_STEPS_FINAL="$(win_path "$STEPS_FINAL")"
      _difres="$(run_win -Mode diff -Before "$(win_path "$STEPS_BEFORE")" -After "$(win_path "$STEPS_FINAL")" -RegionTop "$INPUT_REGION_TOP" -RegionBottom "$INPUT_REGION_BOTTOM")"
      if [ "$(printf '%s' "$_difres" | awk -F'\t' '{print $1}')" = "OK" ]; then
        J_STEPS_DIFF="$(printf '%s' "$_difres" | awk -F'\t' '{print $2}')"
        J_INPUT_NBB="$(printf '%s' "$_difres" | awk -F'\t' '{print $3}')"
        J_INPUT_NBA="$(printf '%s' "$_difres" | awk -F'\t' '{print $4}')"
        J_INPUT_REGION="$(printf '%s' "$_difres" | awk -F'\t' '{print $6 " y=" $7 "-" $8}')"
      else
        J_STEPS_ERR="steps_diff_failed: $_difres"
      fi
    else
      J_STEPS_ERR="steps_final_capture_failed: $_fres"
    fi
    J_INPUT_DONE=1
    J_STEPS_FILE="$(win_path "$STEPS_TSV")"
    J_STEPS_FAILED="$STEPS_FAILED"
    if [ "$STEPS_FAILED" -gt 0 ] && [ -z "$J_STEPS_ERR" ]; then
      J_STEPS_ERR="steps_failed: $STEPS_FAILED of $STEPS_TC step(s) failed"
    fi
    log "input steps done: ok=$STEPS_OK failed=$STEPS_FAILED diff_ratio=$J_STEPS_DIFF final=$J_STEPS_FINAL"
  fi
fi

# ---------- archive logs ----------
if [ -f "$LOG_RAW" ]; then
  cp -f "$LOG_RAW" "$RUN_DIR/citron_log.txt" 2>/dev/null || true
  slice_log "$LOG_RAW" > "$RUN_DIR/citron_log_slice.txt" 2>/dev/null || true
  J_LOG="$(win_path "$RUN_DIR/citron_log.txt")"
fi
J_BUILD="$BUILD_LINE"

# ---------- stop only the Citron processes this run started ----------
if [ "$DO_KILL" = "1" ]; then
  LIST_OUT="$(run_win -Mode list)"
  KILL_LIST=""
  while IFS=$'\t' read -r kind a b c; do
    [ -n "$kind" ] || continue
    case " $PRE_PIDS " in *" $a "*) continue ;; esac
    case " $KILL_LIST " in *",$a,"*) continue ;; esac
    KILL_LIST="$KILL_LIST$a,"
  done <<< "$LIST_OUT"
  KILL_LIST="$(printf '%s' "$KILL_LIST" | sed 's/,$//')"
  if [ -n "$KILL_LIST" ]; then
    run_win -Mode kill -Pids "$KILL_LIST" >/dev/null
    sleep 1
    J_KILLED="1"
    log "stopped citron pid(s) $KILL_LIST"
  fi
else
  log "--keep given; leaving Citron running (pid $CAP_PID)"
fi

# ---------- three success signals + status ----------
EXPECT_LC="$(printf '%s' "$EXPECT_TITLE" | tr 'A-Z' 'a-z')"
TITLE_LC="$(printf '%s' "$J_TITLE" | tr 'A-Z' 'a-z')"
case "$TITLE_LC" in
  *"$EXPECT_LC"*) J_TITLE_MATCH="1" ;;
esac

J_APP_OUT="0"
J_APP_SRC=""
if [ -n "$APP_LOG_REGEX" ] && [ -f "$SLICE_FILE" ]; then
  if grep -aqE "$APP_LOG_REGEX" "$SLICE_FILE"; then J_APP_OUT="1"; J_APP_SRC="app_log_regex"; fi
fi
if [ "$J_APP_OUT" = "0" ] && [ -n "$EXPECT_FILE" ]; then
  EF="$SD/$EXPECT_FILE"
  if [ -e "$EF" ]; then
    EF_MTIME="$(stat -c %Y "$EF" 2>/dev/null || echo 0)"
    if [ "$EF_MTIME" -ge "$LAUNCH_EPOCH" ]; then J_APP_OUT="1"; J_APP_SRC="expected_file"; fi
  fi
fi
if [ "$J_APP_OUT" = "0" ] && [ -n "$BOOT_LINE" ] && [ "$J_SHOT_NONBLACK" != "" ]; then
  case "$J_SHOT_NONBLACK" in
    ''|*[!0-9.]*) : ;;
    *) if [ "$(printf '%.0f' "$J_SHOT_NONBLACK")" -ge 1 ] 2>/dev/null; then J_APP_OUT="1"; J_APP_SRC="screenshot_nonblack"; fi ;;
  esac
fi

J_ELAPSED="$ELAPSED"
J_PID="$CAP_PID"
if [ -n "$BOOT_LINE" ]; then
  J_BOOT="$BOOT_LINE"
  J_STATUS="loaded"
  J_ERR=""
  RC=0
else
  J_STATUS="timeout"
  RC=1
  if [ "$LOG_FRESH" = "0" ]; then
    J_ERR="citron_not_started: no fresh citron log after launch (launch_route=$LAUNCH_MODE; launcher may have failed; see docs/environment/citron-harness.md)"
  elif [ "$DEAD" = "1" ]; then
    J_ERR="process_exited_before_boot: citron was launched but exited without a Booting game line"
  elif [ -n "$LOAD_FAIL_LINE" ]; then
    J_STATUS="fail"
    RC=2
    J_ERR="load_failed: $LOAD_FAIL_LINE"
  elif [ -n "$EXC_LINE" ]; then
    J_ERR="hle_exception: $EXC_LINE"
  elif [ -n "$SEE_NEW" ]; then
    if [ "$GAME_TYPE" != "nro" ]; then
      J_ERR="not_booted: Citron received the $GAME_TYPE file but no 'Booting game' line appeared within $TIMEOUT s (direct $GAME_TYPE boot may be unsupported; see docs/environment/citron-harness.md)"
    else
      J_ERR="load_stalled_after_loading: process alive but no boot line within $TIMEOUT s"
    fi
  else
    J_ERR="boot_timeout_no_evidence: no citron process observed within $TIMEOUT s"
  fi
fi

OUT="$(emit_result)"
printf '%s\n' "$OUT" > "$RUN_DIR/result.json"
{
  printf 'status      : %s\n' "$J_STATUS"
  printf 'game        : %s (type %s)\n' "$J_GAMEPATH" "$J_GAMETYPE"
  printf 'window title: %s\n' "$J_TITLE"
  printf 'pid         : %s\n' "$J_PID"
  printf 'elapsed_s   : %s\n' "$J_ELAPSED"
  printf 'boot line   : %s\n' "$BOOT_LINE"
  printf 'signals     : title_match=%s boot_line=%s app_output=%s (%s)\n' "$J_TITLE_MATCH" "$( [ -n "$BOOT_LINE" ] && echo 1 || echo 0 )" "$J_APP_OUT" "$J_APP_SRC"
  printf 'screenshot  : %s (%s, %s bytes, nonblack=%s)\n' "$J_SHOT" "$J_SHOT_METHOD" "$J_SHOT_BYTES" "$J_SHOT_NONBLACK"
  printf 'log         : %s\n' "$J_LOG"
  printf 'error       : %s\n' "$J_ERR"
  if [ "$J_INPUT_DONE" = "1" ] || [ -n "$J_INPUT_ERR" ]; then
    printf 'input       : injected=%s focus_ok=%s clicks=%s keys_sent=%s diff_ratio=%s region=%s\n' "$J_INPUT_DONE" "$J_INPUT_FOCUS" "$J_INPUT_CLICKS" "$J_INPUT_KEYS_SENT" "$J_INPUT_DIFF" "$J_INPUT_REGION"
    printf 'input shots : before=%s after=%s\n' "$J_INPUT_BEFORE" "$J_INPUT_AFTER"
    printf 'input error : %s\n' "$J_INPUT_ERR"
  fi
  if [ "${#STEP_KINDS[@]}" -gt 0 ] || [ -n "$J_STEPS_ERR" ]; then
    printf 'input steps : done=%s failed=%s diff_ratio=%s\n' "$J_INPUT_DONE" "$J_STEPS_FAILED" "$J_STEPS_DIFF"
    printf 'steps file  : %s\n' "$J_STEPS_FILE"
    printf 'steps final : %s\n' "$J_STEPS_FINAL"
    printf 'steps error : %s\n' "$J_STEPS_ERR"
  fi
} >> "$RUN_LOG"
if [ "$JOB_MODE" = "child" ] && [ -n "$JOB_DIR" ]; then
  job_mark_done "$J_STATUS" "$RC"
fi
printf '%s\n' "$OUT"
exit "$RC"
