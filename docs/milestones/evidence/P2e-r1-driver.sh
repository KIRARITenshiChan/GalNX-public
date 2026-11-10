set -uo pipefail
OUT=E:/galnx-build/pilot-01/review/a2-indep
cd '/e/Othergames/Nintendo Switch/Workspace/GalNX'
export CITRON_USER_DIR=/c/Users/ACETaffy/AppData/Roaming/citron
SD=/c/Users/ACETaffy/AppData/Roaming/citron/sdmc
{
  echo "prewipe_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "kirikiri_before=$([ -e "$SD/kirikiri" ] && echo present || echo absent)"
  echo "marker_before=$([ -e "$SD/switch/kirikiroid2/.galnx_extracted" ] && echo present || echo absent)"
  echo "autostart_before=$([ -e "$SD/switch/kirikiroid2/autostart.txt" ] && echo present || echo absent)"
} > "$OUT/r1-prewipe.txt"
rm -rf "$SD/kirikiri"
rm -f "$SD/switch/kirikiroid2/.galnx_extracted" "$SD/switch/kirikiroid2/autostart.txt"
echo "post_wipe_kirikiri=$([ -e "$SD/kirikiri" ] && echo present || echo absent) post_wipe_marker=$([ -e "$SD/switch/kirikiroid2/.galnx_extracted" ] && echo present || echo absent)" >> "$OUT/r1-prewipe.txt"
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
bash scripts/citron_run.sh --game /e/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b4.nsp --timeout 300 --settle 25 --expect-title 'Kirikiroid' --input-delay 3000 --input-gap 250 --input-steps 'wait:120000;capture:title;key:RIGHT;wait:2500;key:C;wait:15000;capture:started;key:C;wait:5000;capture:adv1' > "$OUT/r1.out.log" 2> "$OUT/r1.err.log"
RC=$?
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "RC=$RC start=$START end=$END" > "$OUT/r1.done"
cp -f "$SD/switch/kirikiroid2/k2s_log.txt" "$OUT/k2s-r1.txt" 2>/dev/null
cp -f "$SD/switch/kirikiroid2/k2s_log.prev.txt" "$OUT/k2s-r1-prev.txt" 2>/dev/null
cp -f "$SD/switch/kirikiroid2/.galnx_extracted" "$OUT/marker-r1.txt" 2>/dev/null
cp -f "$SD/switch/kirikiroid2/autostart.txt" "$OUT/autostart-r1.txt" 2>/dev/null
cp -f "$SD/kirikiri/haruno/Kirikiroid2Preference.xml" "$OUT/pref-r1.xml" 2>/dev/null
{ echo "postrun_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; ls -la "$SD/switch/kirikiroid2"; } > "$OUT/r1-sd-switch.txt" 2>&1
echo driver_done
