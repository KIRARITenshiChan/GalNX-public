# P43 · 剧情触发 OP + 可跳过（P40c）

- 日期：2026-11-09
- 相关：`docs/builds/048-p40c-op-story-trigger.md`、`docs/builds/patches/rfvp-switch/P40c-op-story-trigger.diff`
- 状态：Citron 两形态验证 PASS（本目录：NRO + NSP(romfs)），真机待验

## 1. 这份证据回答什么

用户 m36793 提出「现在的版本会在游戏开始时播放 OP 且不可跳过」，要求 OP 回到剧情触发。

根因是 P33 时代留下的调试钩子：`platform/switch/runtime/main.c` 的 `rfvp_switch_debug_movie()`
读 `sdmc:/switch/rfvp/debug.txt` 的 `movie=1`，设备上残留的 debug.txt 让每次启动都强制播 modal OP。
P40c 把该钩子改成只读 `sdmc:/switch/rfvp/movie_debug.txt`，debug.txt 不再触发影片。

本目录保存两次 Citron 运行的证据快照：

1. **NRO 形态**（run_dir `E:/galnx-build/p40/run-citron-08/op-skip/20261109-231904-rfvp`，
   NRO sha256 `2666286e44a14662f1fabf00533f05f08c1f1c7e6faa96acf99a98bd92fdae19`）：
   从存档 DATA.005 载入 → 推进一句 → OP 由剧情脚本触发 → 按 R（Citron 键盘 E）→ 播放中断回到正文。
2. **NSP(romfs) 形态**（run_dir
   `E:/galnx-build/p40/run-citron-09/nsp-romfs/20261109-235305-IROSEKA_FHD-010047420000a000`，
   NSP sha256 `51d0f8c716db614b7376776bf8d0e6004f08f21448e7b856ad41ca16d435bdda`）：
   SD game 目录被临时挪走（`JUNCTION_PARKED`），资产全部来自 NSP romfs；同样走
   载入存档 → 推进 → 剧情触发 OP → 按 R 回正文，18/18 步 ok。

## 2. 能证明什么

1. 去掉 debug 钩子后，**引擎启动不再自动播放 OP**（run-05/06 点 New Game 进入序章正文时 debug_report 里
   0 条 `MoviePlay`）。
2. OP 会由**游戏脚本自己**在剧情点触发：`MoviePlay: path=movie/01.wmv flag=Nil is_layer_effect=true`，
   紧随 `Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4`，随后 decoded frame 递进。
3. 播放期间按 R（pad R → Ctrl，`event.rs` 的 skip 键）→ **MovieStop 生效、回到正文**（截图 05/06 为正文画面）。
4. `flag=Nil` 说明是**非 modal** 播放（可被跳过）；modal 才是不可跳过。
5. **NSP(romfs) 形态同样成立**：`JUNCTION_PARKED` 后仍能打开 `movie/01_h264.mp4`（说明资产确实进了 romfs 且
   路径解析正确），并在按 R 后 `movie audio: stopped movie/01.ogg` + 出现 `history_set` 行（回到消息层）。
6. `history_set: unexpected value for set_voice/set_name : Nil` 只是进正文消息层的副作用，不是致命错误。

## 3. 不能证明什么

1. **不能证明真机硬解分支**：Citron 无 NVDEC，两次运行都是 FFmpeg 软解 + NEON（`hw=0`），
   硬解路径（`hw=1`）的真机表现由 P42 证据覆盖，本目录不覆盖。
2. 不能证明真机上的跳过按键（手持 R = Ctrl）时序手感，只能证明「Ctrl 键会被游戏当作跳过」。
3. 不能证明 ED（`f_000426A7(2, nil)`）：iroseka 的 `movie/` 没有 `02.*`，ED 路径要用 moyu 的
   `02_h264.mp4` 另测。

## 4. 文件

| 文件 | 说明 |
| --- | --- |
| `citron-op.png` | NRO run：剧情触发的 OP 画面（staff credits，降采样到 1280 宽） |
| `citron-after-skip.png` | NRO run：按 R 之后回到正文 |
| `citron-story.png` | NRO run：继续推进后的正文 |
| `citron-result.json` | NRO run 的 result.json（24/24 步 ok、窗口标题、nonblack_ratio） |
| `citron-debug-report-movie.txt` | NRO run debug_report 节选：`MoviePlay` / `movie h264` / EOS / `history_set` |
| `nsp-romfs-op.png` | NSP(romfs) run：剧情触发的 OP 画面（staff credits，降采样到 1280 宽） |
| `nsp-romfs-after-skip.png` | NSP(romfs) run：按 R 之后回到正文（悠马「一定要赶上！」） |
| `nsp-romfs-result.json` | NSP(romfs) run 的 result.json（18/18 步 ok、`1.2.2-test` 窗口标题） |
| `nsp-romfs-debug-report-movie.txt` | NSP(romfs) run debug_report 节选：movie 段 + 回正文 history_set 段 |
| `SHA256SUMS` | 上面九个文件的校验和 |

## 5. 复现

```bash
# NRO 形态（run-08）
bash /e/galnx-build/p40/run-op-device-save.sh
# NSP(romfs) 形态（run-09，需先把 sdmc 的 game 目录挪开）
bash /e/galnx-build/p40/run-nsp-romfs-citron-122.sh
```

关键前置：`sdmc:/switch/rfvp/debug.txt` 只写 `shot=900`（**不要** `movie=1`），
删除 `sdmc:/switch/rfvp/movie_debug.txt`，`h264_sw.txt` 写 soft（Citron 无 NVDEC）。
