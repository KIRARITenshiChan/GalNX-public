# P28b：v1.1.4-test Lead 独立 Citron 冒烟（音频/async/画面）

日期：2026-11-07 02:16 · 执行：Lead（Citron NSP 直启，非 NRO）

## 运行
- 命令：`scripts/citron_run.sh --game /e/galnx-build/p28/out/IROSEKA_FHD-010047420000a000-v1.1.4-test.nsp --no-stage --timeout 420 --settle 15 --allow-existing --expect-title IROSEKA --out /e/galnx-build/p28/run-lead-trans`
- 脚本：`E:/galnx-build/p28/run-lead-trans.sh`（先移走 sdmc `switch/rfvp/game` junction 让 NSP 走内嵌 romfs，trap 恢复；写 async.txt=on；debug.txt = shot=900 / stall=1200 / stall_at=1200）
- run_dir：`E:/galnx-build/p28/run-lead-trans/20261107-021608-IROSEKA_FHD-010047420000a000-v1.1.4-test`
- 结果：116/116 步 ok、0 failed、diff_ratio 0.798177、60 FPS；窗口 `IROSEKA FHD (64-bit) | 1.1.4-test`；42 张 PNG。

## 关键判定（本目录快照）
- 音频连续性 PASS：`audio_status.txt` = driver=1 thread=1 alive=1 cpu=2 cap=147456 ring=147456 min_water=89088 **underrun=0 max_underrun_ms=0 starve_ms=0** produced=11939840 consumed=11792384 stalls=3 stall_ms=1200。
- 注入 3 次 1.2 s 停顿（debug.txt stall），`audio_stall.txt` 三对 pre(ring=147456) → post(ring=90112/90112/89088)，间隔 1.2015–1.2017 s，underrun 全 0、starve_ms=0 → 主线程长帧期间音频 ring 未断流（Citron 级）。
- async 无冻结：`async_status.txt` = enabled=1 hb=226000 stage=0 cpu=1 wdt=1 main=14517 stalled=0；`frame_status.txt` = frame=14535 status=0 async=1；无 last_error。
- 画面：`step-02-t0-title.png` 标题、`step-05-t1-loadlist.png` 读档列表、`step-08-t2-story.png` 正文与立绘、`step-11/14/98-seq*.png` CG 差分（构图/缩放变化）。无黑块、无 UI 残留。
- 过渡中间态：`diff-analysis.json` 显示 36 张 seq 截图只有 2 处大跳变（seq01→02 diff 63.4、seq30→31 diff 59.5），无 3–30 渐变段——原因是 `citron_run.sh` 每步 capture 开销约 4.7 s，采样间隔 ≈5.4 s，恰好跨过 5.4 s 的 dissolve 整段。**本快照不能证明 NSP 上过渡中间态**，过渡证据以 P28a 的 CPU harness + GPU NRO 为准。

## 复现
1. 恢复/移走 sdmc `switch/rfvp/game` junction；
2. `printf 'on' > sdmc:/switch/rfvp/async.txt`；`printf 'shot=900\nstall=1200\nstall_at=1200\n' > debug.txt`；
3. 运行上面的 citron_run.sh 命令；
4. 读取结束后 sdmc 的 audio_status/audio_stall/async_status/frame_status 四个文件（运行时以 "wb" 覆盖）。

## 仓库内证据裁剪

仓库内保留标题与第一张 seq 截图；完整 42 张在 `E:/galnx-build/p28/run-lead-trans/20261107-021608-IROSEKA_FHD-010047420000a000-v1.1.4-test`。
完整原始集合：`E:/galnx-build/p28/run-lead-trans/20261107-021608-IROSEKA_FHD-010047420000a000-v1.1.4-test`。SHA256SUMS 仅覆盖本目录保留文件。
