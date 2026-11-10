# P3-f：A3 自包含 NSP 全新 SD 冒烟独立复跑

- 日期：2026-10-30
- 执行：audit-web（独立于 P3-a/P3-b/P3-c/P3-e 的 Lead 构建/冒烟）
- 对象：`E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-010047410000A000.nsp`（2,906,131,672 B）
- TitleID：010047410000A000（合规 base，0x2000 对齐）
- 环境：Windows 10.0.26100 x64 / Citron Nightly `main-0237a9b88`（23,272,960 B，Vulkan，firmware 22.0.0）/ 虚拟 SD `%APPDATA%\citron\sdmc` / 键集用户自备（只校验存在，不读内容）
- 用途：复现 P3-e 的 A3 验收结论（全新 SD 首启 → 标题 → 手柄进正文 → 推进），只做运行时冒烟，不做打包 verify。

## 结论：**PASS**（7/7 判据满足，与 Lead 结论一致）

`status=loaded`；窗口标题 `citron Nightly | 0237a9b88 | Haruno (64-bit) | 1.0.2 | NVIDIA`；`boot_line` 含 `Booting game: 010047410000A000 | Haruno (64-bit) | 1.0.2`；三张截图均为游戏内容且 `nonblack` > 0.9；k2s_log 时间线完整覆盖「首次解包 23 文件 → title.ks → start.ks → @0000A_Z01.ks」；解包总量 23 文件 / 2,870,635,309 B；keymap XML sha256 与期望值一致。

## 1. 前置断言与 fresh wipe

- Citron 实例数 **0**（`Get-Process -Name citron`）后才启动；全程无其他 Citron。
- 独立校验 NSP：`Get-FileHash -Algorithm SHA256` → `1F54BDF105FDFC0E88A81E5AAEC954FFD4C349132FE7BBADCF394948CDE994D4`（与 task 给定值一致，见 `P3f-nsp-hash.txt`）。
- Wipe（严格按 task）：`rm -rf sdmc/kirikiri`；删 `sdmc/switch/kirikiroid2/{.galnx_extracted,autostart.txt,k2s_log.txt,k2s_log.prev.txt,k2s_boot.txt,k2s_crash.txt}`。
- 额外加强：同时删 `sdmc/switch/kirikiroid2/.preference/`（K2NX 文件选择器历史路径，Lead 的 wipe 清单未含）。该目录不是 autostart 的一部分，删除只为避免「选择器记忆」造成的伪首启；副作用仅记录，不影响判据。
- wipe 后确认：`sdmc/kirikiri` 不存在、`kirikiroid2/` 仅剩空目录（无 marker/autostart/日志）。

## 2. 命令（实际执行，未改脚本）

```bash
cd 'E:/Othergames/Nintendo Switch/Workspace/GalNX'
bash scripts/citron_run.sh --game 'E:/galnx-build/pilot-01/p3/out/Kirikiroid2-NX-010047410000A000.nsp' \
  --detach --timeout 420 --settle 25 --expect-title Haruno --input-delay 3000 --input-gap 250 \
  --input-steps 'wait:120000;capture:title;key:RIGHT;wait:2500;key:C;wait:15000;capture:started;key:C;wait:5000;capture:adv1'
# run_dir = workspaces/citron-harness/runs/20261030-091112-Kirikiroid2-NX-010047410000A000
bash scripts/citron_run.sh --wait-job <run_dir> --wait-timeout 420   # rc=0，waited_s=224
```

- 父进程 5 s 内返回 detach JSON（harness_pid=33922、launcher_pid=26448、launch_route=schtasks-limited）。
- 子进程 `.done`：`status=loaded / rc=0 / finished=2026-10-30T01:15:11Z`；harness `killed=true`；结束后 Citron 实例数 **0**（无需手工杀）。

## 3. 时间线（本地时间 UTC+8，证据见 P3f-k2s_log.txt / P3f-run.log）

| 时间 | 事件 |
| --- | --- |
| 09:11:15 | detach job 启动（cmd.exe /c job.cmd，schtasks-limited） |
| 09:11:1x | Citron 起，`BootGame: Booting game: 010047410000A000 \| Haruno (64-bit) \| 1.0.2`（boot_line 3.955708 s） |
| 09:11:4x | `[GALNX] free space check ok: 25425 MiB free for a 2737 MiB payload` → `first boot: copying 23 payload file(s)` → `payload copy finished: 23 copied, 0 kept, 0 failed, 2737 MiB total` |
| 09:11:55 | `[GALNX] autostarting game from /kirikiri/haruno/data.xp3`；7 个内置插件以 `.tpm -> .dll` 别名加载成功；`Total 19153 file(s) found, 19141 file(s) activated` |
| 09:11:57 | Scenario loaded: startup.soc → userMacro.ks → startup.soc → eyecatch.ks → startup.soc → logo.ks（logo.mpg 播放） |
| 09:12:33 | **Scenario loaded : title.ks**（标题画面） |
| 09:14:17 | `capture:title` 截图 |
| 09:14:25 | **Scenario loaded : start.ks**（`key:C` 确认「はじめから」后） |
| 09:14:29 | **Scenario loaded : @0000A_Z01.ks**（正文） |
| 09:14:44 | `capture:started` 截图（正文第一句「懸命に手を伸ばした。」） |
| 09:14:47 | `key:C` 再次推进 |
| 09:14:56 | `capture:adv1` 截图（下一句「どこの誰かだかもわからない、目の前にある逆光の中の"彼女"に向けて……」） |
| 09:15:11 | 子进程写完 result.json/.done，Citron 被杀 |

## 4. 判据逐条核对

| # | 判据 | 实测 | 结论 |
| --- | --- | --- | --- |
| 1 | `status=loaded` | result.json status=loaded | **PASS** |
| 2 | signals title_match+boot_line+app_output 均 true | 三者 true，app_output_source=`screenshot_nonblack` | **PASS** |
| 3 | boot_line 含 010047410000A000 | `... Booting game: 010047410000A000 \| Haruno (64-bit) \| 1.0.2` | **PASS** |
| 4 | 3 个 capture step 全 ok 且 nonblack>0.5 | steps 10/10 ok；capture nonblack 0.9018 / 0.9018 / 0.9017；steps_diff_ratio=0.809225 | **PASS** |
| 5 | k2s_log 含四类关键行 | `first boot: copying 23 payload file(s)`(L3)；`payload copy finished: 23 copied, 0 kept, 0 failed`(L9)；`autostarting game from /kirikiri/haruno/data.xp3`(L13)；`Scenario loaded : title.ks`(L122) + `start.ks`(L130) + `@0000A_Z01.ks`(L132) | **PASS** |
| 6 | 解包 23 文件 / 2,870,635,309 B | `find sdmc/kirikiri -type f`：files=23 bytes=2870635309（P3f-sd-listing.txt） | **PASS** |
| 7 | keymap XML sha256 = aa4fa8aa… | `AA4FA8AAB256F73C6D73111A62305F7078BD9C1ECA3CD9D9128D0A51ABEF9543`（1,293 B） | **PASS** |
| 附加 | Citron 归零 / 进程被 harness 清理 | 结束后实例数 0；result.json killed=true | **PASS** |

## 5. 截图内容核对（人工 read_image，非仅脚本指标）

- `P3f-title.png`：完整标题画面 —— 「晴のちきっと菜の花びより」logo + 菜单（はじめから / ロード / クイックロード / コンティニュー / コンフィグ / スペシャル / 終了する），窗口标题栏为 `Haruno (64-bit) | 1.0.2`。
- `P3f-started.png`：正文画面，对话框「懸命に手を伸ばした。」，左侧游戏 logo 水印，画面无黑屏/控制台。
- `P3f-adv1.png`：下一句「どこの誰かだかもわからない、目の前にある逆光の中の"彼女"に向けて……」，与上一张内容不同 → 推进已生效。
- 三张 1728x1016，nonblack 0.9018/0.9018/0.9017，均非黑、非错误页。

## 6. 与 Lead run（20261030-090102）的差异

维度不可比，只比内容：

| 截图 | 我的 run | Lead run | MAD（0–255） | 像素差>8 占比 |
| --- | --- | --- | --- | --- |
| title | P3f-title.png (2,377,262 B) | step-02-title.png (2,377,415 B) | 0.142 | 0.14% |
| started | P3f-started.png (883,561 B) | step-07-started.png (881,598 B) | 0.153 | 0.18% |
| adv1 | P3f-adv1.png (922,387 B) | step-10-adv1.png (921,533 B) | 0.149 | 0.16% |

- MAD ≈0.15/255、差>8 像素 <0.2%，差异集中在 60 FPS 渲染帧相位与对话框文字打字机进度；内容判定一致（同标题、同正文句、同推进关系）。
- 关键日志序列一致（首启 23 文件解包、7 插件别名、19153 文件、title.ks→start.ks→@0000A_Z01.ks），仅时间戳差几十秒。
- 流程差异：本次额外删 `.preference`（见 §1），Lead run 未删；本次 harness 走 `--detach`（P3-d 新路径），Lead run 亦为 detach。

## 7. 限制与未验证项

- **模拟器环境**：所有结论来自 Citron（yuzu 血统）nightly，非真机；真机仍需 Atmosphère/title-takeover 与 sigpatches，未验证。
- **「手柄操作」的边界**：本次推进用 `PostMessage` 把 Citron 的键盘映射（`player_0_button_a=engine:keyboard,code:67`，C=Switch A；方向键 16777234–16777237）送给窗口，属于「Citron 手柄映射 → 游戏」链路；真实 Joy-Con/Pro Controller 的 HID 输入、摇杆模拟量、震动未验证。注意 `focus_ok=false` 时 PostMessage 仍生效，不能把 focus 标志当作输入成功的判据。
- 只验证到「进正文并推进一句」；存档写入/读档、音频出声、长时稳定性、过场动画音画同步未验证。
- 未做 `galnx package nsp verify`（task 允许）；运行时不校验 NCA 签名/TitleID 一致性，仅由 boot 行与窗口标题反证 ProgID。
- 游戏原目录只读，未改动；`sdmc:/kirikiri/haruno` 为本地实验副本，不入库、不分发。
- 证据未 commit（按任务要求）。

## 8. 证据清单（docs/milestones/evidence/P3f-*，完整 sha256 见 P3f-artifacts-sha256.txt）

| 文件 | 字节 | 说明 |
| --- | --- | --- |
| P3f-result.json | 3,957 | 子进程 result.json（status/signals/steps/launch_route/killed） |
| P3f-run.log | 1,915 | harness run.log（boot 行、三信号、steps 汇总） |
| P3f-input-steps.tsv | 887 | 10 步逐条状态/耗时 |
| P3f-job.json | 1,258 | 父进程 detach JSON |
| P3f-title.png / P3f-started.png / P3f-adv1.png | 2,377,262 / 883,561 / 922,387 | 标题 / 正文首句 / 推进后一句 |
| P3f-k2s_log.txt / P3f-k2s_boot.txt | 7,995 / 234 | K2NX 运行日志与启动标记 |
| P3f-marker.txt / P3f-autostart.txt | 11 / 26 | `.galnx_extracted`=`pilot01-r2`；autostart=`/kirikiri/haruno/data.xp3` |
| P3f-Kirikiroid2Preference.xml | 1,293 | 游戏写入的 keymap（含手柄映射） |
| P3f-nsp-hash.txt / P3f-keymap-hash.txt | 295 / 158 | 独立哈希记录 |
| P3f-sd-listing.txt | 901 | 23 文件逐项字节 + 合计 |
| P3f-artifacts-sha256.txt | — | 本清单（sha256 + 字节 + 文件名） |

关键 sha256：result.json `fd06631a956dbbf57145aad744e1affab887114b79796dfe3699d149d845bc52`；title.png `b7291cc54f15a5a2fb1f3dae1ad76d9d8c6974ff66bfbd1107d2e2412da8de35`；k2s_log.txt `419c10dc6148896bd46955bd9a15ea02a8fd325e5b055ba5ddd4bd87dd791ea2`；keymap `aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543`。
