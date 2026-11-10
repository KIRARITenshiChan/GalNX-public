set -uo pipefail
OUT=E:/galnx-build/pilot-01/review/a2-indep
cd '/e/Othergames/Nintendo Switch/Workspace/GalNX'
export CITRON_USER_DIR=/c/Users/ACETaffy/AppData/Roaming/citron
SD=/c/Users/ACETaffy/AppData/Roaming/citron/sdmc
{
  echo "second_boot_pre_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "kirikiri_before=$([ -e "$SD/kirikiri" ] && echo present || echo absent)"
  echo "marker_before=$(cat "$SD/switch/kirikiroid2/.galnx_extracted" 2>/dev/null | tr -d '\r\n')"
  echo "autostart_before=$(cat "$SD/switch/kirikiroid2/autostart.txt" 2>/dev/null | tr -d '\r\n')"
  echo "pref_sha_before=$(sha256sum "$SD/kirikiri/haruno/Kirikiroid2Preference.xml" 2>/dev/null | cut -d' ' -f1)"
} > "$OUT/r2-prestate.txt"
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
bash scripts/citron_run.sh --game /e/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b4.nsp --timeout 300 --settle 25 --expect-title 'Kirikiroid' --input-delay 3000 --input-gap 250 --input-steps 'wait:80000;capture:second-title' > "$OUT/r2.out.log" 2> "$OUT/r2.err.log"
RC=$?
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "RC=$RC start=$START end=$END" > "$OUT/r2.done"
cp -f "$SD/switch/kirikiroid2/k2s_log.txt" "$OUT/k2s-r2.txt" 2>/dev/null
cp -f "$SD/switch/kirikiroid2/k2s_log.prev.txt" "$OUT/k2s-r2-prev.txt" 2>/dev/null
{ echo "post_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; sha256sum "$SD/switch/kirikiroid2/.galnx_extracted" "$SD/switch/kirikiroid2/autostart.txt" "$SD/kirikiri/haruno/Kirikiroid2Preference.xml" 2>/dev/null; } > "$OUT/r2-poststate.txt" 2>&1
echo driver_done
