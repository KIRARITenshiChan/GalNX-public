# さくら、もゆ。（FVP v0.2.0_0222_fix1 / JP）Citron + rfvp v1.0.8 基线运行记录

- 任务：GalNX task-47（teammate sakura-runner），2026-11-05 05:52–06:08（Asia/Shanghai）
- 结论：**成功**。rfvp NRO 在 Citron 上可启动、渲染、进入正篇；nls 必须 = sjis（gbk 会乱码）；720p 内部渲染（1280x720），Citron 状态栏稳定 60 FPS / ~16.6 ms。
- 取证根目录：`E:/galnx-build/sakura-test/evidence/`（子目录 prev-m5-ref / run1-gbk / run2-gbk / run3-sjis）

## 1. 环境与启动配方（复现用）

- 游戏源：`E:/Othergames/Galgame/さくら、もゆ。v0.2.0_0222_fix1`（FVP：Sakura.hcb 5,002,569 B + graph*.bin 等 12 个 *.bin + movie/01.wmv、02.wmv + default.ttf）
- 组装副本：`E:/galnx-build/sakura-test/game`（7.5G，同卷 NTFS hardlink，不占额外空间；含空 save/；default.ttf 22,839,132 B 复用 m5-rfvp-run）
- **重要布局事实**：Citron 实际读取的是 `C:/Users/ACETaffy/AppData/Roaming/citron/sdmc/switch/rfvp/game`，而该路径当前是**一份 7.5G 的真实拷贝**（此前用 Git-bash `ln -s` 创建链接时 MSYS 回退成了复制；`cmd dir /AL` 和 PowerShell Attributes 均确认无 reparse point）。**修改 nls 必须改 sdmc 里那份 config.toml，改 E:/galnx-build/sakura-test/game/… 不会影响运行**。两处现均为 sjis。
- config.toml（实际生效的一份，sdmc/switch/rfvp/game/config.toml，86 B）：
  ```
  # GalNX sakura-test config (Sakura, Moyu. FVP)
  [game]
  hcb = "Sakura.hcb"
  nls = "sjis"
  ```
- NRO：`E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro`（7,929,912 B，rfvp v1.0.8，含 P11–P20 补丁），由 harness 自动 stage 到 `sdmc/switch/galnx-harness/rfvp.nro`。
- 诊断开关：`sdmc/switch/rfvp/debug.txt` = 1；无 `async.txt`（异步解码未启用）。
- 启动命令（Workspace/GalNX）：
  ```bash
  cd '/e/Othergames/Nintendo Switch/Workspace/GalNX'
  export CITRON_USER_DIR=/c/Users/ACETaffy/AppData/Roaming/citron
  export CITRON_SD=$CITRON_USER_DIR/sdmc
  export CITRON_EXE='E:\\Othergames\\Nintendo Switch\\Workspace\\GalNX\\workspaces\\web-02\\citron\\citron.exe'
  export APPDATA='C:\\Users\\ACETaffy\\AppData\\Roaming'
  bash scripts/citron_run.sh --game E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro \\
    --detach --timeout 240 --settle 8 --allow-existing \\
    --out /e/galnx-build/sakura-test/runs \\
    --input-steps 'wait:18000;capture:00-title;click:1451,250;wait:8000;capture:01-after-newgame;click:864,600;wait:7000;capture:02-text1;click:864,600;wait:7000;capture:03-text2;wait:12000;capture:04-baseline'
  # 随后 bash scripts/citron_run.sh --status <run_dir> / --wait-job，或轮询 run_dir/.done + result.json
  ```
- 每次运行结束 harness 会 stop Citron（result.killed=true）；运行后核实无残留 citron.exe。窗口始终：`citron Nightly | 0237a9b88 | rfvp (64-bit) | NVIDIA`（1728x1016 client，Vulkan）。

## 2. 三次运行与 nls 实验（核心）

| run | run_dir | nls | 结果 |
|---|---|---|---|
| run1 | `E:/galnx-build/sakura-test/runs/20261105-055607-rfvp` | gbk | status=loaded，标题画面正常；但输入只用了 pclick/key，均无效（停在标题，diff_ratio 0.18） |
| run2 | `E:/galnx-build/sakura-test/runs/20261105-060029-rfvp` | gbk | 前台 click 生效，进入正篇；**文字乱码**（GBK 误解 SJIS） |
| run3 | `E:/galnx-build/sakura-test/runs/20261105-060457-rfvp` | **sjis** | 前台 click 生效，进入正篇；**日文显示正确** ✅ |

- 输入注入事实：`click:X,Y`（窗口相对坐标，harness 会 BringWindowToTop/SetForegroundWindow，focus_ok=1）→ 有效；`pclick:X,Y`（PostMessage 到最大子 hwnd，Qt 用 QCursor::pos()）→ 无效；`key:C`（PostMessage WM_KEYDOWN）→ 无效（Citron qt-config.ini 里 keyboard_enabled=false，键盘映射存在但不生效）。以后只用 click。
- nls=gbk（run2 证据，`evidence/run2-gbk/step-08-02-text1.png`、`step-13-04-baseline.png`）：第一句显示 `亏婁佈侃侷偲凵偵簾儔乗乗`，第二句 `亏婽偵Т` —— 典型“SJIS 字节被 GBK 解码”。
- nls=sjis（run3 证据，`evidence/run3-sjis/step-08-02-text1.png`、`step-11-03-text2.png`）：第一句 `世界がそっと、ため息をつく――`，第二句 `胸に。` —— 完全正确，无需再试 utf8。
- 结论：**Sakura.hcb 文本编码 = Shift-JIS，config.toml 必须 nls="sjis"（也是引擎默认值）；写 gbk 会乱码。** 汉化 patch.bin/SakuraChs.exe 是 PC 运行时注入，rfvp 不加载，故本 NRO 下显示日文原版（符合预期）；subtitle/ ASS 非引擎必需，未使用。
- 标题画面（run3 首图 `evidence/run3-sjis/step-02-00-title.png`）：さくら、もゆ。logo + NEW GAME(はじめから) / CONTINUE(つづきから) / ALBUM / OPTION(設定変更) / EXIT(終了)，右下 `Copyright FAVORITE All Rights Reserved.`；运行中新出现的自动存档目录 `saves/sakura-aad96959/save/`（rfvp_global.bin 264,026；rfvp_s901.bin 450,060；rfvp_s906.bin 454,865；06:00 生成，未删）。游戏内画面：月夜+花瓣开场、对话框、FUNCTION 菜单（Q.SAVE/Q.LOAD/LOG/AUTO/VOICE/SAVE/LOAD/MENU/SKIP）。

## 3. fps / 慢帧基线（run3 为主，run2/run1 对照）

- run3 debug_report.txt（`evidence/run3-sjis/debug_report.txt`，90,414 B）头行原文：
  ```
  frame 6000: 60.0 fps over the last 60 frames, slowest frame 18.0 ms
  stages (ms per frame): tree 0.05 submit 0.22 end_frame 15.15 vm 0.55 syscalls 0.14
  virtual frame 1280x720
  perf avg over 60 ticks: vm 0.55 ms, scene 0.02 ms, render 15.55 ms, total 16.12 ms
  host avg over 60 frames: begin 0.04 ms, upload 0.00 ms (0 calls), present 15.15 ms, thumb 0.00 ms (0 calls), draws 15.0, flushes 15.0
  ```
  frame_status.txt: `frame=6045 status=0 async=0`；async_status.txt: `enabled=0 create=0x0 start=0x0 hb=0 stage=0`
- run2 对照（`evidence/run2-gbk/debug_report.txt`）：`frame 6120: 60.0 fps …, slowest frame 19.0 ms`；vm 0.66 / scene 0.02 / render 15.34 / total 16.03；present 14.84、draws 15.0。
- run1（标题画面）：`frame 7200: 60.0 fps …, slowest frame 17.3 ms`；render 15.97 / total 16.18；present 15.55。
- Citron 状态栏实测：正篇稳定 `Game: 60 FPS / Frame 16.65–16.68 ms`；切换场景瞬间出现过 `45 FPS / 27.51 ms`（run2 的 step-05；run3 截图均为 60 FPS）。
- 结论：720p 下渲染管线约 15.5 ms/帧（end_frame/present 主导，draws 15–18），CPU VM ~0.55–0.66 ms，余量小但稳定 60；真正卡顿来自**资源解码/存档 IO 一次性长帧**，不是持续掉帧。
- run3 perf_slow.log（9 行，`evidence/run3-sjis/perf_slow.log`）摘要（均为一次性事件，稳态无慢帧）：
  - frame 1 = 1177.0 ms（启动装载，submit 74 ms，vm 203 ms）
  - frame 2 = 155.5 ms（save 140.08 ms → save_snapshot 18.91 / save_finalize 37.84）
  - frame 4 = 228.2 ms（vm 194.88，syscalls 190.51，vfs_read 93.09，graph_decode 81.06，tree 20.36）
  - frame 12 = 33.4 ms（end_frame 32.68）；frame 309 = 106.1 ms（audio_cmds 102.67）
  - frame 2657 = 40.8 ms（vm 37.75，vfs_read 36.80）
  - frame 2847 = 111.7 ms（vm 93.63，vfs_read 54.64，graph_decode 37.22）
  - frame 2848 = 124.5 ms（vm 100.29，vfs_read 37.45，graph_decode 25.17，cpu_restore 36.13）
  - frame 2849 = 143.0 ms（render 110.12，audio_cmds 103.46，cpu_restore 25.11）
- run2 perf_slow.log（14 行，`evidence/run2-gbk/perf_slow.log`）：同型，另有 frame 2682 33.6 ms（vfs_read 30.24）、frame 2873 134.2 ms（vm 110.73）、frame 2874 115.7 ms（audio_cmds 77.22）——与 run3 的 2657/2847–2849 组对应（同一段场景，重跑复现），说明这些长帧是资产预取/音频初始化的确定性一次性开销。

## 4. 错误摘要（全部非致命，无 last_error.txt / nls.txt）

- run3 debug_report.txt 共 80 条 `[ERROR]`：25×`Invalid id`、24×`graph_load: invalid id : Nil`、24×`Invalid alpha motion id`、2×`snow: arg10 should be in range 1..1024`、2×`history_set: unexpected value for set_voice : Nil`、2×`history_set: unexpected value for set_name : Nil`、1×`id must be in range 0..256`。均为未知/空 id 的非致命告警，画面与流程正常。
- run2：80 条同型（Invalid id / id range / snow arg10）。
- `[INFO]` 里有大量 `[cache] prefetch skip path="graph/dissXX": Unexpected texture type: Single8Bit`（dissolve 贴图不进预取缓存，非错误）。
- 无 `last_error.txt`、无 `nls.txt`、无 `debug_screen.bmp`（本次未触发错误截图）；Citron 自身未崩溃，harness 正常 kill。

## 5. 取证文件清单

- `E:/galnx-build/sakura-test/evidence/run1-gbk/`（17M）：debug_report.txt 86,011 B、perf_slow.log、frame_status.txt、async_status.txt、citron_log.txt、result.json、harness.err、log_slice_latest.txt、step-02-00-boot.png、step-04-01-title.png、step-07-02-click-center.png、step-10-03-keyC.png、step-13-04-keyC2.png、step-15-05-baseline.png、window*.png、debug_screen.bmp
- `E:/galnx-build/sakura-test/evidence/run2-gbk/`（15M）：debug_report.txt 90,204 B、perf_slow.log 4,550 B、step-02-00-title.png、step-05-01-after-newgame.png、step-08-02-text1.png（乱码）、step-13-04-baseline.png（乱码）、window*.png、citron_log.txt、result.json、harness.err、frame/async_status
- `E:/galnx-build/sakura-test/evidence/run3-sjis/`（11M，**最终基线**）：debug_report.txt 90,414 B、perf_slow.log 1,381 B、**step-02-00-title.png（首图/标题）**、step-05-01-after-newgame.png、**step-08-02-text1.png（日文正常）**、**step-11-03-text2.png（日文正常）**、step-13-04-baseline.png、window*.png、citron_log.txt、result.json 3,967 B、harness.err、frame_status.txt、async_status.txt
- `E:/galnx-build/sakura-test/evidence/prev-m5-ref/`（100K）：11-01 IROSEKA FHD 的 m5 基线 debug_report/perf_slow（对比用）
- run3 关键 result 字段：`status=loaded`、`window_title="citron Nightly | 0237a9b88 | rfvp (64-bit) | NVIDIA"`、`boot_line=true`、`screenshot_info={method:"printwindow", nonblack_ratio:0.9018}`、`input.steps_failed=0`、`steps_diff_ratio=0.616764`、`clicks=3`（3×focus_ok=1）、`elapsed_s=25`、`killed=true`。

## 6. 未覆盖 / 风险

- 未验证 movie/*.wmv 播放（本次只到开场前几分钟；wmv 全屏视频需再跑更长流程）、音频实际输出（无录音校验）、长时间稳定性（>10 分钟）、存档/读档往返。
- 未测 utf8（sjis 已正确，无必要）；未测 async 解码（async.txt 未启用）。
- 运行使用的 sdmc 内 7.5G 游戏为真实拷贝（非链接），C: 盘占用 +7.5G；若要清理请 Lead 确认，删除会破坏 Citron 可复现运行，重建可再复制/或改真 junction。
