# 022 - rfvp 逐句存档卡顿修复（惰性编码，P16）

TASK: 修用户 m21366 报告的真机缺陷——「稍推进后的略复杂场景会瞬时卡顿并带音频一起卡，几乎每句话卡一下」。

结论先行：**不是写盘慢，也不是缩略图慢（P14 已修），而是每句会触发两次 10.2 MB 存档状态的 postcard 序列化，每次 ~100 ms**。把序列化从「准备阶段」推迟到「真正需要落盘时」后，逐句存档的引擎侧成本从 ~130 ms/帧 × 2 帧降到 ~5 ms/帧，写盘路径仍然正确。

## 1. 现象与真机取证

真机 P15 运行（`E:/galnx-build/p15/device/run1/perf_slow.log`，7410 帧 / 约 2 分钟）：

- 114 个含 `save` 阶段的慢帧，恰好组成 **55 对**，每一对固定相差 2 帧（例：f925/f927、f983/f985、f1111/f1113、f1175/f1177）；
- 对与对的间隔 44–184 帧（约 0.7–3 s），与「每句话」的节奏一致；
- 每对拆解：第一帧 `save_finalize` = 40.5–80.0 ms（大档），第二帧 `save_finalize` = 7.8–9.5 ms（小档）；两帧的 `save_snapshot` 只有 1.7–5.4 ms；**缩略图稳定 24.8–25.5 ms/次**（P14 之前的数据）；
- 结论：一次「逐句自动存档」= 2 个存档帧 ≈ 100 ms 卡顿，音频线程也被主线程拖住，和用户体感「带音频一起卡」吻合。

真机存档目录显示同一个游戏状态下 `rfvp_s001.bin` 10,941,755 B、`rfvp_s005/s905.bin` 10,360,096 B，而标题画面阶段的系统档只有 ~489 KB——**状态体积随剧情场景复杂度从 0.49 MB 涨到 10.2 MB**。

## 2. 根因链（本机 Citron 复现 + 插桩）

把真机复杂存档复制进 Citron SD（备份见 `E:/galnx-build/p16/citron-saves-backup/saves`），从标题 Continue → LOAD 列表底部 CONTINUE 进入正文，成功复现（run `p16-b`）：`debug_report.txt` 出现

```
[INFO] [save] SaveCreate(3) value=Nil
[INFO] [save] state total=10269622B motion=10250941B audio=579B globals=8935B vm=9166B
```

引用链（全部在 rfvp 上游源码）：

1. 游戏的每句自动存档调用 TJS 的 `SaveCreate(3)`（`crates/rfvp/src/subsystem/components/syscalls/saveload.rs:28`），**不带 slot**（`value=Nil`）时只做 `SaveManager::request_prepare_local_savedata()`；
2. `request_prepare_local_savedata`（`save_manager.rs:598`）把 `need_save_prepare=true`、`local_saved_bytes=None`；
3. 同一帧的 `capture_pending_save`（`no_std_core.rs:737`）取 `pending_save_capture()` → `(u32::MAX, w, h)`，只做「准备」：截缩略图 + 抓 `SaveStateSnapshotV1`；
4. 关键在 `finalize_local_savedata_prepare`（`save_manager.rs:614`）：旧实现会立刻 `build_save_file_bytes` + `append_state_chunk_v1`，后者对 ~10.2 MB 的 `SaveStateSnapshotV1` 执行 `postcard::to_allocvec`——**单次 100 ms**；`state total=10269622B` 里 `motion` 占 10,250,941 B（99.8%，主要是 `MotionManagerSnapshotV1.textures` 的 raw RGBA）；
5. 游戏每句连发两次 `SaveCreate(3)`（第二次在同一/下一帧清掉上一次结果再来一遍），所以是 **2 × 100 ms**；
6. 这两次都不带 slot，`try_commit_local_savedata` 不会真正写盘（`save_requested` 仅在 `SaveWrite` 时为真）——**编码出来的 10 MB 直接被丢弃**，纯浪费。

顺带发现并修掉一个仪器化误差：`save_state.rs` 的诊断日志为了打印 motion/audio/globals/vm 各自的字节数，对快照做了 4 次额外 `encode`，使实测编码量接近翻倍；本次一并删除。

## 3. 措施

### 3.1 惰性编码（核心）

`save_manager.rs` 新增：

```rust
#[derive(Debug)]
struct PendingPrepare {
    thumb_w: u32,
    thumb_h: u32,
    thumb_rgba: Box<[u8]>,
    state: Box<crate::subsystem::save_state::SaveStateSnapshotV1>,
}
```

- `finalize_local_savedata_prepare` 只把缩略图与状态快照按值存进 `pending_prepare`，**不编码、不拼文件字节**；
- 新增 `materialize_pending_local_savedata(nls)`：真正需要文件时才 `build_save_file_bytes` + `append_state_chunk_v1`，日志 `[save] materialize thumb=... encode_ms=... len=...`；
- `try_commit_local_savedata` 在 `local_saved_bytes` 为空时先 `materialize` 再写盘；
- `wants_vm_snapshot_capture()` / `pending_save_capture()` / `has_local_saved()` 都考虑 `pending_prepare`，第二次 `SaveCreate(3)` 只替换 pending，不重复编码；
- `request_prepare_local_savedata` 清空 pending，保持原有「重新准备」语义；
- 调用方 `no_std_core.rs` / `app.rs` 去掉不再需要的 `nls` 参数（`finalize_local_savedata_prepare(thumb_w, thumb_h, thumb_rgba, state)`）。

### 3.2 缩略图改 GPU 下采样

`platform/switch/runtime/sdl_video.c` 的 `galnx_sdl_read_pixels_scaled()` 旧路径会 `malloc` 1280×720×4、整帧 `SDL_RenderReadPixels` 再 CPU 盒式缩小。改为：按目标尺寸创建/复用一个 `SDL_TEXTUREACCESS_TARGET` 小纹理，`SDL_RenderCopy` 从上一帧 target 降采样，再只读回 `width×height`。失败自动回落旧路径。

### 3.3 保留诊断能力

- `ring_log.rs` 容量 400 → 1200，保证 `debug_report.txt` 能留下整段 `[save]` 轨迹；
- 保留 `[save] SaveCreate(3) value=...`、`SaveWrite slot=...`、`state total=...`、`capture ... thumb_ms=...`、`prepared bytes=... pending=...` 等低成本日志（都是微秒级格式化，不在热路径做额外编码）。

## 4. 结果对比（同一 Citron 复杂存档、同一推进脚本）

| 指标 | 优化前（p16-d） | 优化后（p16-e） |
| --- | --- | --- |
| 逐句 SaveCreate(3) | 每句 2 次，value=Nil | 每句 2 次，value=Nil（不变） |
| state 体积 | 10,269,622 B（motion 99.8%） | 10,228,000–10,269,000 B（不变） |
| 准备阶段编码 | `encode_ms=99.17–108.00` / 次 | **无编码**（`prepared bytes=None pending=true`） |
| 每帧 save 阶段耗时 | 112–135 ms（save_finalize 102–114 ms） | **5.27–5.67 ms**（只剩 save_snapshot 3.4–4.0 ms） |
| 缩略图 | 10–12 ms（P14 后） | **1.03–2.16 ms** |
| 逐句推进截图 | 正常 | 正常（e3/e4/e5 逐句变化，0 exceptions） |

真实落盘路径仍然完整走通（LOAD 列表阶段系统档 901/906）：

```
[INFO] [save] SaveCreate(3) value=Int(901)
[INFO] [save] state total=399110B
[INFO] [save] materialize thumb=200x113 encode_ms=17.61 len=489531
[INFO] [save] commit slot=901 len=489531 write_ms=6.47 ok=true
[INFO] [save] materialize thumb=200x113 encode_ms=6.84 len=491484
[INFO] [save] commit slot=906 len=491484 write_ms=2.25 ok=true
```

→ 惰性化只影响「什么时候编码」，不影响「编码出来的文件内容」；`commit ... ok=true` 与写盘耗时并存。

## 5. 产物

- 增量补丁 `docs/builds/patches/rfvp-switch/rfvp-save-lazy.patch`：357 行 / 6 文件 +162/−19，SHA-256 `941f9504eb04494cc0fc6bc6a7b477af67cbdc4dd2d71b75665f3c738496d332`；已在 P15 基线 worktree 通过 `git apply --check`；
- 全量 `docs/builds/patches/rfvp-switch/rfvp-full.diff`：3,131 行 / 17 文件 +2,289/−202，SHA-256 `626e7aa95a7bbcb8f3b910e09db96f16d4ade6a56dddb75f33c798565bae072f`；已在纯净 HEAD worktree 通过 `git apply --check`；
- `rfvp.nro` 7,852,088 B，SHA-256 `3aff4de3327f5ec6165a86a5b1988bd9435ce1dbce60a22df05f38c582b16432`（产物 `E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/`，不入库）；
- `rfvp.elf` 17,077,488 B，SHA-256 `9adc739f64a3daaea005bf691f47ae3d1c20804abd4ed480e1792ec7ee699396`（`target/rfvp-switch-runtime/`）；
- NSP v1.0.4 `IROSEKA_FHD-010047420000a000.nsp`：**9,979,446,488 B**，SHA-256 `5bcef902622637fcfecb79823279ab4d108c7ae6af87f8cb7d1301b0e74e1f2d`（TitleID `010047420000A000`、romfs 9,932,275,140 B / 161 条目、hacBrewPack 约 9 分钟；`galnx package nsp verify` 13 checks / 0 fail / 1 warn = 未签名 NCA）。
- NSP 形态 Citron 冒烟 PASS：自包含 NSP v1.0.4 通过 `romfs:/game` 载入复杂存档（`game.sd-bak` 遮蔽 SD 游戏目录）→ 标题 Continue → LOAD 列表 CONTINUE → 正文，pad A 推进 4 句；窗口 `IROSEKA FHD (64-bit) | 1.0.4`、60.0 fps、0 异常；`[save]` 仅系统槽 901/906 出现 `materialize`+`commit ok`，随后 8 次 `SaveCreate(3) value=Nil` 无任何 encode（帧 4591 `save 5.83 ms`）。

构建（本机 Rust 工具链已离线）：`env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m5-build-instr.sh'`。
上游 `build_switch.sh` 里的 `rustup toolchain install ...` 在本次环境已无法联网（`static.rust-lang.org` TLS EOF），而 nightly-2026-02-01 + rust-src 本机已装；wrapper 用删除该行的 `build_switch_instr.sh` 构建，属本地环境绕行，未进补丁。

## 6. 证据

`docs/milestones/evidence/P16-rfvp-save-latency/`：

- `before-p16d-save-lines.txt` —— 优化前 debug_report 的 `[save]` 片段（含 `encode_ms=99.17–108.00`、`state total=10269622B`）；
- `before-p16d-perf_slow.log` —— 优化前慢帧阶段（save_finalize 102–114 ms）；
- `after-p16e-save-lines.txt` / `after-p16e-debug-report.txt` —— 优化后 `[save]` 轨迹（`pending=true`、无编码；系统档 materialize+commit 正常）；
- `after-p16e-perf_slow.log` —— 优化后慢帧（save 阶段 5.27–5.67 ms）；
- `after-p16e-loaded.png` / `after-p16e-adv4.png` —— 复杂存档读入正文、推进一句后的画面（非黑屏、文字正常）；
- `after-nsp-loaded.png` / `after-nsp-adv4.png` / `after-nsp-save-lines.txt` / `after-nsp-perf_slow.log` / `after-nsp-done.txt` —— NSP 形态冒烟（v1.0.4：读档进正文、推进 4 句、逐句无编码）；
- `device-upload-v104.txt` —— v1.0.4 真机上传实测（DBI 浏览 SD 卡模式：9,979,446,488 B / 1,636.4 s ≈ 5.82 MiB/s，落盘 `/switch/galnx-nsp/`，远端 SIZE 复查一致）；
- `SHA256SUMS.txt`。

## 7. 限制与遗留

1. **U1 真机未复验**：本机 Citron 已用 NRO 与 NSP（v1.0.4）双形态、同一份真机复杂存档复现并验证（逐句 save 帧 112–135 ms → 5.27–5.83 ms）；真机卡顿是否完全消失仍需用户装 v1.0.4 复跑。
2. **U2 每句仍抓 10 MB 状态**：惰性化省掉了编码，但 `SaveStateSnapshotV1::capture` 仍要把 motion 纹理像素拷进快照（~5 ms/次，2 次/句）。若真机仍有轻微卡顿，下一步是缩小 motion 快照（raw RGBA 只存引用/差异）或把 capture 也推迟/复用。
3. **U3 写盘频率**：真正 `SaveWrite` 仍是同步写（小档 2–6 ms、10 MB 档未在本次逐句路径出现）；如果后续发现游戏每句都 `SaveWrite` 大档，再加合并/节流。
4. **U4 其余慢帧未处理**：启动帧 vfs/graph_decode（~1–2 s 一次）、Citron 自身 audio_cmds 尖峰（150 ms 级）、原生 EXIT 动画等与逐句存档无关，不在本补丁范围。
5. `state total=...` 日志仍在（每句 2 行），对性能无影响；真机如果嫌日志多可在 `ring_log` 级别关闭。

## 8. 复现

1. 从真机复杂存档目录复制 `save/*.bin` 到 Citron `sdmc/switch/rfvp/saves/iroseka-2ae7dc8e/save/`；
2. `sdmc:/switch/rfvp/debug.txt` 写 `1`；删除 `perf_slow.log` / `debug_report.txt`；
3. 用 `scripts/citron_run.sh` 进游戏：标题 `click:1386,638`（Continue）→ LOAD 列表 `click:455,911`（底部 CONTINUE）→ 每句 `key:C`（pad A = Enter）；
4. 读 `debug_report.txt` 的 `[save]` 段与 `perf_slow.log` 的 save 慢帧。
