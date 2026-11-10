# 035 — rfvp 转场（Mask Dissolve）修复（v1.1.4-test）

- 日期：2026-11-07
- 版本：1.1.4-test（nacp 版本号取自 platform/switch/host/Cargo.toml:3）
- 分支基线：p27-work HEAD `7210094`（含 P27 音频连续性；不并入 P24 音频流式补丁）
- 构建 worktree：`/e/galnx-build/p28/rfvp-v114`（detach 7210094，不污染 m5-rfvp 主树）
- 状态：源码修复完成 + CPU 无头 harness 验证 PASS + Citron(GPU) 级视觉证据已取得（多帧渐变中间态）；**真机未验证**；与 P27 音频合并出 1.1.5-test 由 Lead 统一执行
- 用户现象（m28040 转述）：真机 v1.1.2-test「切换场景之间的过渡动画从未出现，背景切换都是硬切」

## 1. 缺陷

用户在真机游玩 IROSEKA（五彩斑斓的世界 HD Re:GENERATION）时，场景切换是**瞬间替换**，没有原版的淡入/擦除过渡。

修复前证据（CPU 无头 harness，v1.1.2-test 源码 + 仅诊断打点）：

- 同一条自动路线（点 New Game 后自动推进）中，第 1061 帧发生 `Dissolve(5410ms, "graph/diss00", inout=true)` = MaskFadeInOut；
- 但画面在 1062 帧**直接由纯黑变为纯白 255**，之后 114 帧保持纯白（mean=255, std=0），没有任何擦除中间态；
- harness 诊断计数：`mask_build=0`、`mask_phase=0`、`mask_nosnap=4000`。

## 2. 根因：no_std（Switch）渲染路径缺少「上一帧快照」接线

rfvp 的掩膜溶解（Mask Dissolve）实现本身是完整的，并在两条渲染路径上分别接线：

| 路径 | 快照来源 | 证据（修复前） |
| --- | --- | --- |
| std / desktop GPU | `app.rs` 每帧在 rebuild 前判断并回读渲染目标 | crates/rfvp/src/app.rs:968 `if self.prim_renderer.mask_wants_snapshot(&gd.motion_manager)` → :978 `set_mask_snapshot(...)`；注释原文「A mask dissolve that just started wipes away the frame last shown, which is still in the render target.」 |
| soft（CPU 光栅） | 软渲染器自己保存 | crates/rfvp/src/rendering/soft_render/renderer.rs 内部 set_snapshot |
| **no_std（Switch NRO 实际走这条）** | **无** | crates/rfvp/src/no_std_core.rs 修复前无任何 `mask_wants_snapshot` / `set_mask_snapshot` 调用 |

缺失快照时，`mask_dissolve.rs` 的 `prepare()` 走 nosnap 分支（源码注释 crates/rfvp/src/rendering/mask_dissolve.rs:45）：
「Without the previous frame there is nothing to wipe: the new scene shows at once.」
→ 即**硬切**。这与用户现象完全一致，也解释了为什么 ColoredFadeIn/Out（纯色淡入淡出）在 Switch 上正常、只有掩膜转场坏掉。

接口在两条渲染路径都已存在，只差 no_std_core 调用：

- crates/rfvp/src/rendering/prim_commands.rs:110 `mask_frame_wants_snapshot`、:116 `set_mask_snapshot`（HostPrimRenderCache）
- crates/rfvp/src/rendering/gpu_prim.rs:180 同名方法
- platform/switch/host/src/render.rs:410 `capture_thumbnail`（Switch 宿主：`galnx_sdl_read_pixels_scaled` 回读上一帧）

## 3. 修复（patch：docs/builds/patches/rfvp-switch/rfvp-transition.patch）

- 文件：`docs/builds/patches/rfvp-switch/rfvp-transition.patch`
- 大小：3,178 B；行数 76；sha256 `b9717fea74a1c46e4ca2e42e22433b15d015d851bccb45aeb2dd58bae21a7d83`
- 改动：**4 文件 / +31 / -2**（`git -C /e/galnx-build/p28/rfvp-v114 diff --numstat 7210094` 后应用验证同值）
- 应用：在 7210094 干净树 `git apply --check` 4/4 通过；**必须用 git apply**（源文件是基线 CRLF + 新增行 LF 的混合行尾，git 会规范化；不要用 patch(1) 直接打）

| 文件 | 改动 |
| --- | --- |
| crates/rfvp/src/rendering/prim_commands.rs | +12：在 HostPrimRenderCache 增加两个转发方法（cfg(not(feature="psx"))）`mask_frame_wants_snapshot` → `self.mask_frame.wants_snapshot(motion)`；`set_mask_snapshot` → `self.mask_frame.set_snapshot(motion, frame)` |
| crates/rfvp/src/no_std_core.rs | +17：render_game_frame 内、prev-frame(Sprt -1) 逻辑之后、`render_motion_to_host` 之前：当 `render_cache.mask_frame_wants_snapshot(&motion_manager)` 为真时 `capture_thumbnail(virtual_width, virtual_height)` 取上一帧 RGBA → `image::RgbaImage::from_raw` → `set_mask_snapshot(...)` |
| platform/switch/host/Cargo.toml | 版本 1.1.3-test → 1.1.4-test |
| Cargo.lock | 对应版本号行 |

为什么放在 `render_motion_to_host` 之前：此时渲染目标里仍是**上一帧**内容（与 app.rs 的注释语义一致），在渲染本帧动画/转场前把底帧存下来，mask_dissolve 擦除时才有可擦的「旧画面」。

## 4. 构建

- 脚本：`/e/galnx-build/p28/build-114.sh`（devkitPro + switch runtime；日志 `/e/galnx-build/p28/build-114.log`，状态 `build-114.status`）
- 结果：`BUILD_EXIT=0 ELAPSED_S=30`
- 产物（sha256 见 `/e/galnx-build/p28/build-114.sha256`）：

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| target/rfvp-switch/switch/rfvp.nro | 7,938,104 B | `641af84ce8bb9f2f86058a54454321d666397b08fbd89612c48be98f2f5f9648` |
| target/rfvp-switch-runtime/rfvp.elf | 17,284,272 B | `aed842f7587f08ea01b643cad3703ba093a2529af6d3566dfd30ceb65b995f92` |

## 5. NSP 打包（100% 内嵌 romfs）

- 脚本：`/e/galnx-build/p28/build-nsp-114.sh`（WMI 脱离启动：`launch-nsp.cmd` + `launch-nsp.ps1`，pid 2108），日志 `/e/galnx-build/p28/nsp-run.log`
- 参数：title-id 010047420000a000、name「IROSEKA FHD」、author GalNX、version 1.1.4-test、romfs-mode hardlink、game-dir `/e/galnx-build/m5-rfvp-run/game`（**161 个文件 hardlinked=161 copied=0**，即 100% 内嵌 romfs）
- 时间：02:03 STEP 1 → 02:11 NSP 写出 → `NSP_BUILD_DONE`（约 8 分钟，STEP 5/6 hacBrewPack 占绝大部分）
- 产物：

| 项 | 值 |
| --- | --- |
| 路径 | `/e/galnx-build/p28/out/IROSEKA_FHD-010047420000a000-v1.1.4-test.nsp` |
| 大小 | 9,979,503,832 B（比 P27 的 1.1.3-test 大 8,192 B，差值为 exefs 中 NRO 体积差） |
| sha256 | `444af465aa5250312a9d2d205eb711c67d7c1bbbcf23e8268b4ecd52a9223113`（`/e/galnx-build/p28/out/nsp-sha256.txt`） |
| 元数据核验 | staging 的 `nspwork/control/control.nacp`（16,384 B）中 `strings` 可见 `IROSEKA FHD` / `GalNX` / `1.1.4-test`；exefs 含 main + main.npdm |

## 6. 验证

### 6.1 CPU 无头 harness（源码级，可复现）

方法：rfvp 自带 `crates/rfvp/src/no_std_harness.rs`（cfg(all(test, feature="no_std"))）在 std 宿主上跑同一个 no_std 核心 + CPU 软光栅，逐帧输出 PPM；用 P28DIAG 打点观察 mask 路径。命令见 §7。

对照（同一路线、同一起点 0.84,0.50 点 New Game，自动推进）：

| 指标 | run4（修复前，仅诊断打点） | run5（修复后） |
| --- | --- | --- |
| 帧数/输出窗口 | 4000 帧，PPM 1035–1176 每 3 帧 | 1250 帧，PPM 1040–1260 每 4 帧 |
| dissolve_call / start_dissolve | 11 / 11 | 4 / 4 |
| mask_build | **0** | **1**（`path=graph/diss00 dims=Some((1920,1080)) snap=true`） |
| mask_phase | **0** | **188**（phase 508→215，hard=false，gen 0→187） |
| Mask 类型走 mask_nosnap | 4000（含非转场帧） | Mask* 转场 0 |
| 1061 帧转场视觉 | 1062 帧起纯白 255，std=0，持续 >114 帧（硬切） | 黑→灰度单调渐变：1160 mean 0.1 / 1164 22.1 / 1168 50.1 / 1176 81.0 / 1200 131.0 / 1240 183.0（188 帧渐变） |

读取方式：`grep 'P28DIAG mask_build' run5.log.ring`、`grep 'P28DIAG mask_phase' run5.log.ring | head/tail`；帧统计脚本 `/e/galnx-build/p28/scripts/stat_frames.py`。

结论（**已证实**）：修复后 no_std 路径在 MaskFadeInOut 开始时正确生成快照，mask 擦除逐帧推进（188 帧、相位连续递减），不再走「无快照直接显示新场景」分支。

补充观察（未解释，见 §8）：CPU 软光栅输出的中间帧接近均匀灰度（std 0.2–1.2），看不出明显空间图案；这与 mask 素材本身的 alpha 分布、或软光栅合成路径有关，需在 GPU 路径上看真实形态（§6.2）。

### 6.2 Citron（GPU / Switch 运行时路径）实测

环境：Citron Nightly 0237a9b88（Vulkan，Windows），`scripts/citron_run.sh --nro <v114 NRO> --keep` 启动后保持进程，用 run 目录自带 `citron_win.ps1` 逐帧抓窗口（PrintWindow，约 0.66–0.75 s/帧，1728x1016）。

操作路线：标题 → 点 New Game(1378,536) → 黑场淡出 → FAVORITE/FVP logo 白场（此段点击无效，需按键）→ A×3+ENTER×2 跳过 logo/OP → 进入序章正文 → 每按一次 C(A) 推进一句、同时连拍 4 帧，共 ~70 轮。

抓到的转场中间态（关键帧，见 §9 证据目录）：

| 序列 | 帧 | 观察 |
| --- | --- | --- |
| 转场 A（白场淡出/淡入） | r20-1 → r20-2 → r20-3 → r20-4 → r21-1 → r22-4 | 云场景（1,474,747 B）→ 提亮（1,074,852）→ 近白（508,616）→ 纯白（78,966）→ 白场淡入新场景（96,769）→ 新场景正文「是梦。」；即 ColoredFadeIn(color_id=255) 的完整多帧过程 |
| 转场 B（CG 切换） | r68-1 → r68-2 → r68-3 | 清晰 CG（1,944,020 B）→ **同一 CG 多重复影/双重曝光中间态**（2,505,092 B，轮廓出现多个错位副本）→ 新构图清晰 CG（1,659,251 B） |
| 转场 C（CG 切换） | r38-4 → r39-1 → r39-2 | 清晰 CG → 中间态（2,812,883 B，重影/拖影）→ 新构图清晰 CG |

判读（区分已证实/未证实）：

- **已证实**：v1.1.4-test 在 GPU 路径上场景切换存在**多帧中间态**（每段至少 2–3 帧被 0.7 s 间隔的截图捕获），不再是一帧硬切；白场淡入淡出与 CG 重影两类转场都可观察到。
- **未证实**：中间帧的像素级形态是否与 PC 原版逐帧一致（截图间隔 0.7 s，转场时长 1.8–5.4 s，每段只抓到 2–5 帧）；r68-2/r39-1 的「重影」是 mask 擦除的空间图案还是 CG 缩放/运动叠加，未做像素级归因。
- **未验证**：真机（Switch 实机）表现。

### 6.3 与修复前的 GPU 对照

本轮**没有**在同一路线抓「修复前 NRO」的 GPU 帧（Citron 时间为 P27/P25 共享，只跑了一次 v114）。修复前硬切的 GPU 级证据由两点间接支撑：

1. 用户真机反馈（m28040 转述）；
2. §6.1 CPU harness 同核 no_std 代码的 run4 实测（mask_build=0，1 帧内切换为纯白）。

## 7. 复现命令

CPU harness（无头，不需要 Citron）：

~~~
# 构建（约 10-30 s）
bash /e/galnx-build/p28/harness-build.sh
# 运行：label frames out_from out_to out_every start_xy
bash /e/galnx-build/p28/run-harness.sh run5 1250 1040 1260 4 0.84,0.50
# 计数
grep -c 'P28DIAG mask_build' /e/galnx-build/p28/harness-out/run5.log.ring
~~~

Switch 构建 + 打包：

~~~
bash /e/galnx-build/p28/build-114.sh          # NRO/ELF
bash /e/galnx-build/p28/build-nsp-114.sh      # NSP（内嵌 romfs）
~~~

Citron GPU 取证：

~~~
export CITRON_USER_DIR=/c/Users/ACETaffy/AppData/Roaming/citron
export APPDATA='C:\Users\<user>\AppData\Roaming'
cd "/e/Othergames/Nintendo Switch/Workspace/GalNX"
bash scripts/citron_run.sh --nro /e/galnx-build/p28/rfvp-v114/target/rfvp-switch/switch/rfvp.nro \
  --out /e/galnx-build/p28/run-keep --timeout 240 --settle 8 --keep \
  --input-steps 'wait:3000;capture:ready'
# 之后用 run 目录里的 citron_win.ps1（-Mode input/capture）逐帧操作与抓图
~~~

## 8. 风险与未验证

1. **真机未验证**：所有 GPU 证据来自 Citron（Vulkan + galnx_sdl_read_pixels_scaled）。真机 SDL/EGL 路径的回读时序（present 前后）未验证，可能出现快照拿到本帧而非上一帧，导致转场「首帧即新场景」。
2. **性能开销**：每次 MaskFadeInOut 开始要多做一次 1920×1080 RGBA 回读（8,294,400 B）+ 一张 RgbaImage（8.3 MB）+ mask 纹理（8.3 MB）。真机上这可能是一次 5–30 ms 的额外帧（v1.1.4 未做内存/耗时测量）。
3. **CPU 软光栅中间帧均匀灰**（§6.1）未解释；若 GPU 路径也是「整屏透明度混合」而非空间擦除，则视觉上仍不是原版擦除，需要在真机上和 PC 原版并排对比。
4. **Citron GPU 只抓到 2–3 帧/转场**，不能证明转场完整帧序（开始/中间/结束三阶段证据部分成立：r20 序列有 4 帧完整淡出+1 帧淡入）。
5. **`Invalid duration` 日志**：Citron 运行期间 debug_report 有 3,968 条 `[ERROR] Invalid duration`（crates/rfvp/src/subsystem/components/syscalls/motion.rs:76/205/326/470/593/739 六处之一），与本次转场修复无关，但说明 Motion 系 syscall 参数解析在真机路线上大量失败，属独立缺陷（本轮未追）。
6. **版本合并**：本补丁相对 7210094（含 P27 音频）；与 P24 音频流式、P25 async 等分支合并时只需 4 文件小改，冲突风险低，但 Cargo.toml 版本号需人工合并。
7. **P29（OP 视频）**：序章前的 OP movie 在 Switch 上表现为白场等待输入（本轮用按键跳过），属 native video 缺失，不在本补丁范围。

## 9. 证据路径

- 仓库外主目录：`/e/galnx-build/p28/evidence/`
  - `gpu-transition/`：13 张 Citron 关键帧（r20-1/2/3/4、r21-1、r22-4、r37-1、r38-4、r39-1/2、r68-1/2/3、title-ready.png）
  - `cpu-harness/`：run4（修复前）frame_01035/01062/01080/01110/01140/01176、run5（修复后）frame_1160/1164/1168/1176/1200/1240（640×360 PNG）
  - `SHA256SUMS`：上述文件清单
- harness 原始输出：`/e/galnx-build/p28/harness-out/run4/`、`run5/`（PPM + .log + .log.ring）
- Citron run 目录：`/e/galnx-build/p28/run-keep/20261107-015413-rfvp/`
- 构建/打包日志：`build-114.log`、`nsp-run.log`
- 全量 diff（仓库外，对上游 `9f07ade` 的干净 worktree）：`/e/galnx-build/p28/rfvp-full-v114.diff`，675,760 B / 22,270 行 / 36 文件，sha256 `4cc7a26881b8c9e485bb703a895dfaa82b7cadaff9cde052c030a9e3f44a8322`

## 10. 真机验收清单（交给 Lead / 用户）

1. 安装 1.1.4-test（或合并后的 1.1.5-test）NSP，从标题进入新游戏。
2. 观察序章期间**至少 3 次场景切换**：不是瞬间替换，而是有 1–5 s 的过渡；记录有无黑场/白场淡入淡出、有无空间擦除/重影。
3. 与 PC 原版同段并排对比（重点：转场形态是否一致，不只是「有动画」）。
4. 记录切换瞬间是否掉帧（预期一次额外回读，若出现 >100 ms 卡顿需回报）。
5. 检查转场结束后画面是否残留旧帧（快照未释放/纹理串帧）。
6. 覆盖保存/读档后再次切换场景（避免快照状态串到读档后首帧）。

## 11. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-11-07 | 初版：根因、修复、CPU/GPU 验证、NSP（1.1.4-test，sha256 444af465…）、真机清单 |
