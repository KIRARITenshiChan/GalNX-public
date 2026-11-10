# rfvp Switch patches（GalNX P9 / P10）

`rfvp-sdl2-backend.patch` — 把 rfvp 的 Switch 显示后端从 **CPU 软光栅 + libnx framebuffer** 换成 **SDL2/GLES2**。

- 上游：https://github.com/xmoezzz/rfvp
- pin：HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`（tag `pre-release` 同 commit；版本 tag `0.7.0` = `99435f22`）
- 补丁大小：1,238 行 / 6 文件 / SHA-256 `515af726a8f6804102b3ffd99a3a1e9e1edfa567694e48ccc9cee3ba712b77c7`
- 应用：`git apply .../rfvp-sdl2-backend.patch`（`git apply --check` 已在纯净 worktree 通过）
- 记录：`docs/builds/016-rfvp-sdl2-backend.md`

## 文件清单

| 文件 | 作用 |
| --- | --- |
| `platform/switch/runtime/sdl_video.c`（新） | SDL2 视频 shim：纹理 upsert、像素格式转换、blend 映射、`SDL_RenderGeometry` 四边形、读回缩略图/BMP 截图 |
| `platform/switch/runtime/main.c` | 主循环改由 SDL 驱动（不再 `appletMainLoop`），删除 libnx framebuffer 与截图函数 |
| `platform/switch/host/src/render.rs` | `HorizonRenderer` 不再持有 `SoftRaster`，全部转发 C shim |
| `platform/switch/host/src/ffi.rs` | `present()` 不再写 framebuffer；打印 `perf avg over 60 ticks` |
| `platform/switch/host/build.rs` | Windows 下 devkitA64 工具探测加 `.exe`（否则 cc 回落宿主 gcc 生成 COFF） |
| `platform/switch/build_switch.sh` | SDL2/EGL 头与库、编译 `sdl_video.c`、链接顺序 |

## 必须注意的两点

1. **纹理 create 必须是 upsert**。引擎 `crates/rfvp/src/rendering/prim_commands.rs:224` 的 `upload_graph_if_needed()` 在 graph generation 变化时对同一 `TextureHandle(graph_id)` 反复 `create_texture`；后端若「已存在即失败」，文字层（`graph_id = 4064 + slot`）会永久冻结在首帧空纹理。软光栅后端本身就是覆盖语义。
2. **链接顺序**：`-lSDL2 -lEGL -lglapi -ldrm_nouveau -lpthread -lstdc++ -L libnx/lib -lnx -lm`。`-lnx` 放到 `-ldrm_nouveau` 前面会 `undefined reference to nvGpuChannelKickoff / nvGpuChannelAppendEntry`。

## 验收（Citron Nightly 0237a9b88）

- 60.0 fps 满帧（原 17–19 fps），`render 15.57 ms`（含 vsync 等待）、`vm 0.56 ms`、`scene 0.23 ms`
- 标题画面 + 中文正文「从天而降的羽毛。」正确渲染；截图须在启动 ≥90 s 后拍（正文 t≈63.5 s 才出现）
- 产物：`rfvp.nro` 7,823,416 B，SHA-256 `e3acbce42ae2e55acae386ece29ba1f794b029dc6e9b2e48302993b87b0d9399`
- 证据：`docs/milestones/evidence/P9a-rfvp-sdl2/`

---

# rfvp-input.patch（GalNX P10，增量）

`rfvp-input.patch` — 手柄映射 + 快捷存读档。**必须先应用 `rfvp-sdl2-backend.patch`**（两者都改 `platform/switch/runtime/main.c`）。

- 上游：https://github.com/xmoezzz/rfvp，同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 补丁大小：9,886 B / 4 文件 +124/−4 / SHA-256 `aeb8f226e6464f8b07c041f0235a86a381e7efc62bb4443410b19b5fcda0ba84`
- 全量对照：`rfvp-full.diff` 55,781 B / 9 文件 / SHA-256 `aa73cc50e0fca2c9faa727b65ea5315d6e682dd29590f91c1017ced0efd8082f`（HEAD→当前工作树，含新文件 `sdl_video.c`）
- 应用：`git apply rfvp-sdl2-backend.patch && git apply rfvp-input.patch`（或直接 `git apply rfvp-full.diff`）
- 记录：`docs/builds/017-rfvp-input.md`

## 文件清单

| 文件 | 作用 |
| --- | --- |
| `crates/rfvp/src/host_api/event.rs` | `RfvpEvent` 新增 `QuickSave` / `QuickLoad` |
| `crates/rfvp/src/no_std_core.rs` | 处理上述事件 → `legacy::save_quick/load_quick(slot 0)`；并在 VM tick 后取 `take_pending_save_load_request()` 兜底到槽 0（Switch 没有桌面槽位 UI，不兜底会挂起 VM） |
| `platform/switch/runtime/main.c` | `RfvpSwitchInput` 增加右摇杆字段（`padGetStickPos(&pad, 1)`） |
| `platform/switch/host/src/event.rs` | PLUS 改为热键修饰键（PLUS+ZR 快速存档 / PLUS+ZL 快速读档，松开 PLUS 才退出）；右摇杆发 Wheel 事件（上=历史记录）；光标除数 18000→6000 |

## 产物

- 最终 `rfvp.nro` 7,827,512 B，SHA-256 `b95cd26bb9c4699f6a9a08cc880e1665710702becf2ae6be00ee1463baab155e`（替代 016 的 7,823,416 B / `e3acbce4…`）
- 证据：`docs/milestones/evidence/P10-rfvp-input/`

---

# rfvp-romfs.patch（GalNX P11，增量）

`rfvp-romfs.patch` — 运行期游戏根选择，让自包含 NSP 从 **romfs** 读游戏数据。**必须先依次应用 `rfvp-sdl2-backend.patch`、`rfvp-input.patch`**（三者都改 `platform/switch/runtime/main.c`）。

- 上游：https://github.com/xmoezzz/rfvp，同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 补丁大小：2,430 B / 1 文件 +38/−1 / SHA-256 `710a373e227d815eff9069bd55b33270cf8c503b7a20ce843717e8e2af37e489`
- 全量对照：`rfvp-full.diff` 57,536 B / 9 文件 / SHA-256 `a6da02027d870b2f1453424742341b509f17a2ac54a997f78a8e6917fa4c71f4`（HEAD→当前工作树，含新文件 `sdl_video.c`）
- 应用：`git apply rfvp-sdl2-backend.patch && git apply rfvp-input.patch && git apply rfvp-romfs.patch`（或直接 `git apply rfvp-full.diff`）
- 记录：`docs/builds/018-rfvp-nsp.md`

## 文件清单

| 文件 | 作用 |
| --- | --- |
| `platform/switch/runtime/main.c` | `romfsInit()`/`romfsExit()`；`dir_has_game_script()` 用 `.hcb` 探测有效游戏根；`sdmc:/switch/rfvp/game` 无游戏且 `romfs:/game` 有游戏时切到 romfs；日志 `rfvp: game root: ... (romfs mounted|no romfs)` |

## 必须注意

1. 只有 romfs 挂载成功 **且** `romfs:/game` 里存在 `.hcb` 时才切根；否则回落 SD 路径（NRO 形态照旧可用）。
2. 存档路径与游戏根无关，仍在 `sdmc:/switch/rfvp/saves/<game-id>/`；切到 romfs 不会破坏存档。
3. romfs 打包用硬链接：`scripts/build_nsp_game.sh --romfs-mode hardlink`，避免复制 9.2 GiB；顶层 `save/` 会被跳过。

## 产物（P11）

- NSP 9,979,435,224 B，SHA-256 `4592385c1c3e6b166172315a1c79c574b9241f6f8c57244b2e050e0292549189`（`E:/galnx-build/p11/out/`，不入库）
- romfs 9,932,275,140 B / 161 顶层条目
- 证据：`docs/milestones/evidence/P11-rfvp-nsp/`

---

# rfvp-input-remap.patch（GalNX P12，增量 / 替换 P10 的映射层）

`rfvp-input-remap.patch` — 按用户 m18283 的要求重写 `platform/switch/host/src/event.rs` 的手柄映射。**必须先依次应用 `rfvp-sdl2-backend.patch`、`rfvp-input.patch`、`rfvp-romfs.patch`**（四者都改 `main.c`/`event.rs` 相关文件）。

- 上游：https://github.com/xmoezzz/rfvp，同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 补丁大小：413 行 / 1 文件 +264/−56 / SHA-256 `44fd0722a23479108c51e03efeea127385948888f0d12d35a9178127a343ecef2`
- 全量对照：`rfvp-full.diff` 68,536 B / 9 文件 +1278/−173 / SHA-256 `026a7cee248decd8f60d1394383d63eb6c11fdada81837541a8e43f93553ff29`（HEAD→当前工作树，含新文件 `sdl_video.c`）
- 应用：`git apply rfvp-sdl2-backend.patch && git apply rfvp-input.patch && git apply rfvp-romfs.patch && git apply rfvp-input-remap.patch`，或直接 `git apply rfvp-full.diff`
- 记录：`docs/builds/019-rfvp-input-mapping.md`

## 映射（1280x720 游戏坐标）

| 绑定 | 行为 |
| --- | --- |
| A / B | Return / Escape（B 打开游戏暂停菜单） |
| D-Pad | 方向键（不再移动光标） |
| 右摇杆 | 指针移动（`POINTER_DIVISOR=3000`） |
| 左摇杆纵向 | Wheel ±120（上=BACKLOG，首 poll 即发、每 6 poll 重复） |
| ZR / ZL | 左键 / 右键按下-松开（真按住语义） |
| R | `KeyDown/KeyUp(Control)`（按住快进） |
| X | 点击工具栏 AUTO `(1079,700)` |
| Y | Esc→菜单→LOAD `(960,217)` |
| PLUS | Esc→菜单→SAVE `(1117,171)` |
| MINUS | Esc→菜单→EXIT `(654,608)`→确认「确定」`(560,379)` |

## 产物（P12）

- NRO 7,839,800 B，SHA-256 `093ad9e0b5130ff728b23928bf0d92d002f9ede16acdbca18bbe9eb55fed66f6`
- ELF 17,046,880 B，SHA-256 `0bfc77e1617c05a390161643b5652f86d0dc2c3c4cfea41d051d734030ad4c1d`
- NSP 9,979,435,736 B（v1.0.1），SHA-256 `0fda623c37dc8664492341d00a103eaf606eb1a88583f0101508cefd39467419`（`E:/galnx-build/p11/out/`，不入库）
- 证据：`docs/milestones/evidence/P12-rfvp-input/`

---

# rfvp-device-fixes.patch（GalNX P13，增量）

`rfvp-device-fixes.patch` — 修用户真机反馈的四项缺陷（无光标 / 性能卡顿 / 原生退出黑屏 / − 键不退出）。**必须先依次应用 016/017/018/019 四个补丁**。

- 上游：https://github.com/xmoezzz/rfvp，同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 补丁大小：109,915 B / 7 文件 / SHA-256 `9b65b8b272837ad3eb17b8e7f4d785652702a005e48bd39859cd8f2887573eb6`
- 全量对照：`rfvp-full.diff` 85,712 B / 10 文件 / SHA-256 `f195683ed99a7e2243cc2e81e4b66cf5e30c3bb79c83c21168d7771f2463596a`（HEAD→当前工作树；其中 `platform/switch/build_switch.sh` 与 `host/src/render.rs` 仅 CRLF/LF 差异，用 `diff --strip-trailing-cr` 比较为相同，不参与增量补丁）
- 基线复现：`git worktree add --detach /e/galnx-build/rfvp-base 9f07ade` → 依次 apply 016/017/018/019 → `git apply --check rfvp-device-fixes.patch` 通过
- 记录：`docs/builds/020-rfvp-device-fixes.md`

## 文件清单

| 文件 | 作用 |
| --- | --- |
| `platform/switch/runtime/sdl_video.c` | 新增主机层叠加层（自绘黑白菱形光标 + `QUIT GAME?` 面板 + 5×7 点阵字体），随 `SDL_RenderPresent` 绘制；纹理 create 复用同 id 同尺寸 `SDL_Texture`、`scratch` 缓冲只增不减，消除每帧重建 |
| `platform/switch/runtime/main.c` | 每帧把指针可见性/坐标/确认框状态推给 shim（`galnx_sdl_set_overlay`） |
| `platform/switch/host/src/event.rs` | `MINUS` 改为打开主机确认框（不再合成游戏内点击）；确认框期间 A/B 不转发；记录 `pointer_seen`；新增 `pointer()/quit_dialog_open()/take_quit_confirmed()/debug_line()` |
| `platform/switch/host/src/app.rs` | 暴露 `request_quit()/pointer_state()/quit_dialog_open()/take_quit_confirmed()/input_debug_line()` |
| `platform/switch/host/src/ffi.rs` | 导出 `rfvp_switch_pointer`；每帧消费 `take_quit_confirmed()` → `push_event(RfvpEvent::Quit)`（引擎正常关闭 + 存档 flush） |
| `crates/rfvp/src/no_std_core.rs` | 消费引擎 `ExitDialog` 挂起请求与 `ExitMode(3)`（`lock_scripter && main_thread_exited`）→ `quit_requested`，修复原生退出黑屏 |
| `crates/rfvp/src/host_api/event.rs` | 供上述退出路径使用的 `RfvpEvent::Quit` 通路一致化（无行为变更） |

## 映射变更（相对 P12）

| 绑定 | P12 | P13 |
| --- | --- | --- |
| −（MINUS） | Esc→菜单→点 EXIT→点「确定」 | **主机自绘 `QUIT GAME?`**：A 确认退出 / B 取消；确认框打开时 A/B 不转发 |
| 光标 | 依赖游戏自绘 | **主机自绘黑白菱形**（出现指针事件后显示），与游戏自绘青色菱形可并存 |
| 游戏内原生 EXIT | 播完动画黑屏 | 引擎正常退出，回桌面 |

其余（A=Enter、B=Esc、X=AUTO、Y=LOAD、+=SAVE、ZR/ZL=左右键、R=Ctrl、D-Pad=方向键、左摇杆=滚轮、右摇杆=光标）不变。

## 产物（P13）

- 构建：`env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m5-switch-build3.sh'`
- `rfvp.nro` 7,839,800 B，SHA-256 `4f096dd6ae5a50647a499711f036da8658c632d8f56070433e40f1bcc7c2370f`（`E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/`，不入库）
- `rfvp.elf` SHA-256 `f34992a3e68269b51ac7e8eaacf23831ef0ee352b570b16daf5472f6616feeb3`（`target/rfvp-switch-runtime/`）
- NSP v1.0.2：9,979,437,784 B / SHA-256 `ff259aa49780b6c93e79762c6db5c670c6a979ffb6ddcd7c6ab4ce95e09c0d9b`（`E:/galnx-build/p12/out/`，不入库；DBI FTP 上传 1,548.7 s ≈6.15 MiB/s，真机安装）
- 证据：`docs/milestones/evidence/P12b-rfvp-device-fixes/`

---

# rfvp-perf-gpu-prev-frame.patch（GalNX P14，增量）

`rfvp-perf-gpu-prev-frame.patch` — 修真机反馈的转场/周期性卡顿：把 Sprt `texture id = -1` 的上一帧回读从 CPU 逐帧 `RenderReadPixels` 改为 GPU 双离屏 target，并关闭 `debug_screen.bmp` 周期回读、加顶点批处理与宿主层计时插桩。**必须先应用 P13 后的全量状态**（可用 `rfvp-full.diff` 一次应用，再应用本补丁）。

- 上游：https://github.com/xmoezzz/rfvp，同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 补丁大小：32,781 B / 6 文件 +481/−50 / SHA-256 `e64dfb71453a49095e303d8ad7f8fb39c4d59727ed7649049e526165299e4501`
- 全量对照：`rfvp-full.diff` 107,938 B / 12 文件 +2125/−183 / SHA-256 `2050a79c6cca851ca9bf1a1ed1a32eeb94c25cd5b03e1af966e97dc539500eca`（HEAD→当前工作树）
- 基线复现：`E:/galnx-build/rfvp-base-p14`（detach `9f07ade` + `git apply rfvp-full.diff` + commit `c100e1b`「state P13」）→ `git apply rfvp-perf-gpu-prev-frame.patch` 得到 P14 树；
  已在 `E:/galnx-build/rfvp-verify-p14`（c100e1b）通过 `git apply --check` 与实应用（6 文件 +481/−50 与 P14 树一致）
- 记录：`docs/builds/021-rfvp-perf-gpu-prev-frame.md`

## 文件清单

| 文件 | 作用 |
| --- | --- |
| `platform/switch/runtime/sdl_video.c` | 双 `SDL_TEXTUREACCESS_TARGET` 离屏 1280×720；`PREV_FRAME_TEXTURE_ID=0xFFFFFFFD` 特判用上一帧 target 当纹理；present 时 RenderCopy + 轮换；read_pixels/write_bmp 临时绑定上一帧读回；顶点批处理（8192 顶点/12288 索引，仅合并连续同状态）；`galnx_sdl_take_stats` 宿主计时 |
| `crates/rfvp/src/host_api/render.rs` | `RfvpRenderer::supports_gpu_prev_frame() -> bool { false }` 默认实现 |
| `platform/switch/host/src/render.rs` | `HorizonRenderer` 覆盖 `supports_gpu_prev_frame() = true` |
| `crates/rfvp/src/rendering/prim_commands.rs` | `set_prev_frame_gpu(width,height)`：只标记 `prev_frame=Some` 并清 `wants_prev_frame`，不建 CPU 纹理 |
| `crates/rfvp/src/no_std_core.rs` | 支持 GPU 时走 `set_prev_frame_gpu`，否则保留旧 `capture_thumbnail` 路径 |
| `platform/switch/host/src/ffi.rs` | `DEBUG_SCREEN_ENABLED=false` 关闭周期 `debug_screen.bmp`；消费 `galnx_sdl_take_stats` 输出 `host(ms): ...` 计时行 |

## 效果（Citron，同一脚本）

| 指标 | P13（CPU 回读） | P14（GPU prev-frame） |
|---|---|---|
| slow 帧行数 | 154 | 19 |
| 帧>7 的 slow 总时长 | 9,221.4 ms | 639.9 ms |
| thumb 回读 ≥20 ms 的帧 | 142 | 0 |

转场帧 81–85 在 P14 中完全不再进入 slow 列表；每 300 帧的诊断回读卡顿（thumb 38–41 ms）消失。
剩余尖峰：启动帧（vfs_read/graph_decode）、存档帧（save_finalize+缩略图）、Citron 音频（audio_cmds 150 ms），见 021 §9。

## 产物（P14）

- 构建：`env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m5-switch-build3.sh'`
- `rfvp.nro` 7,843,896 B，SHA-256 `e5373bd76f2beda3583711dea0eded5f00b10f542778bf73522e2fe2c97a2484`
- `rfvp.elf` 17,069,080 B，SHA-256 `e4040e7b6e759f6f30ee1351a9e74cc20f6ecb3dda2c7ddd8afb4055c9c9eb46`
- NSP v1.0.3：9,979,441,368 B / SHA-256 `b9e0d6a54a44bf3a3dde8e3f32f22f41d3ee4e009101e9df4f6892e4fb85aa3e`（`E:/galnx-build/p14/out/`，不入库）
- 证据：`docs/milestones/evidence/P14-rfvp-perf/`

---

# rfvp-save-lazy.patch（GalNX P16，增量）

`rfvp-save-lazy.patch` — 修复真机「每句话卡一下」：把 10.2 MB 存档状态的 postcard 编码从「准备阶段」推迟到「真正落盘时」。**必须先应用 P14 后的全量状态**（可用 `rfvp-full.diff` 一次应用，再应用本补丁）。

- 上游：https://github.com/xmoezzz/rfvp，同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 补丁大小：357 行 / 6 文件 +162/−19 / SHA-256 `941f9504eb04494cc0fc6bc6a7b477af67cbdc4dd2d71b75665f3c738496d332`
- 全量对照：`rfvp-full.diff` 3,131 行 / 17 文件 +2,289/−202 / SHA-256 `626e7aa95a7bbcb8f3b910e09db96f16d4ade6a56dddb75f33c798565bae072f`（HEAD→当前工作树）
- 基线复现：`E:/galnx-build/p16/p15base`（HEAD worktree + apply P14 的 `rfvp-full.diff` sha `2050a79c…` + commit）→ `git apply --check rfvp-save-lazy.patch` 通过
- 记录：`docs/builds/022-rfvp-save-latency.md`

## 文件清单

| 文件 | 作用 |
| --- | --- |
| `crates/rfvp/src/subsystem/resources/save_manager.rs` | 新增 `PendingPrepare{thumb_w,thumb_h,thumb_rgba,state}` 与 `pending_prepare`；`finalize_local_savedata_prepare` 只存快照不编码；`materialize_pending_local_savedata` 在 `try_commit_local_savedata` 需要文件时才 `build_save_file_bytes`+`append_state_chunk_v1`；`wants_vm_snapshot_capture`/`pending_save_capture`/`has_local_saved` 纳入 pending；`request_prepare_local_savedata` 清 pending |
| `crates/rfvp/src/subsystem/save_state.rs` | 删除 4 次诊断用额外 `encode`（曾使编码量翻倍），只 encode 一次并记 `[save] state total=..B` |
| `crates/rfvp/src/no_std_core.rs` | 调用点去掉 nls；prepared 日志加 `pending=` |
| `crates/rfvp/src/app.rs` | 同上（std 路径） |
| `crates/rfvp/src/ring_log.rs` | CAPACITY 400→1200，保留整段 `[save]` 轨迹 |
| `platform/switch/runtime/sdl_video.c` | 缩略图改 GPU 下采样：按目标尺寸复用 `SDL_TEXTUREACCESS_TARGET` 纹理，`SDL_RenderCopy` 缩放后只读回 w×h；失败回落旧全帧路径 |

## 效果（Citron，真机复杂存档）

| 指标 | 优化前 | 优化后 |
| --- | --- | --- |
| 每句 2× `SaveCreate(3)` | 各编码 10.27 MB（`encode_ms=99.17–108.00`）后丢弃 | 不编码（`pending=true`） |
| 每帧 save 阶段 | 112–135 ms | **5.27–5.67 ms** |
| 缩略图 | 10–12 ms | **1.03–2.16 ms** |
| 系统档 901/906 写盘 | `commit ok=true` | `materialize encode_ms=17.61/6.84` → `commit write_ms=6.47/2.25 ok=true`（不变） |

## 产物（P16）

- `rfvp.nro` 7,852,088 B，SHA-256 `3aff4de3327f5ec6165a86a5b1988bd9435ce1dbce60a22df05f38c582b16432`
- `rfvp.elf` 17,077,488 B，SHA-256 `9adc739f64a3daaea005bf691f47ae3d1c20804abd4ed480e1792ec7ee699396`
- NSP v1.0.4 见 §7；证据 `docs/milestones/evidence/P16-rfvp-save-latency/`


# rfvp-cache.patch（GalNX P17，增量）

`rfvp-cache.patch` — 修用户 m22537 报告的三类真机卡顿：CG 表情切换、背景切换、每次打开游戏 UI（ESC 菜单 / BACKLOG / 存档界面）。做法=资源 LRU 缓存 + 启动预读 + 解码提速（像素块拷贝 + devkitPro zlib inflate）。**必须先应用 P16 后的全量状态**（`rfvp-full.diff` 上一版，sha `626e7aa9…`）。

- 上游：https://github.com/xmoezzz/rfvp，同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 补丁大小：33,076 B / 849 行 / 28 文件（含新增 `crates/rfvp/src/subsystem/resources/resource_cache.rs`）/ SHA-256 `8b97c147cc40a294841ed910705f0a2b61826a63a286093156e02bda3aeb6920`
- 全量对照：`rfvp-full.diff` 154,886 B / 3,950 行 / 28 文件 / SHA-256 `6930bb65d75fe1c8eb73adf4dac2b00918c010492216647a6f23663df79766c2`（HEAD→当前工作树；纯净 `9f07ade` worktree `git apply --check` 通过）
- 基线复现：`E:/galnx-build/p17/wt-base`（HEAD worktree + P16 全量 `626e7aa9…` + commit）→ `git apply --check rfvp-cache.patch` 通过
- 记录：`docs/builds/023-rfvp-resource-cache.md`

## 文件清单（分组）

| 组 | 文件 | 作用 |
| --- | --- | --- |
| 缓存 | `crates/rfvp/src/subsystem/resources/resource_cache.rs`（新）、`resources/mod.rs` | 进程级 LRU 三缓存（textures 160 MiB / parts 48 MiB / bytes 192 MiB，单条 ≤16 MiB），key 归一 |
| 接线 | `graph_buff.rs`、`motion_manager/mod.rs`、`components/syscalls/graph.rs` | graph 命中 → `apply_cached_texture` / `load_graph_cached`，跳过读盘与解码 |
| 接线 | `parts_manager.rs`、`components/syscalls/parts.rs`、`texture.rs` | parts 命中 → 克隆纹理；`parts_load` 命中时跳过 `vfs_load_file`；`cache_size_hint()` |
| 接线 | `resources/vfs.rs` | `read_file` 命中 bytes 缓存 / 成功回填；`list_by_prefix()` 供预读枚举 |
| 预读 | `no_std_core.rs`、`resource_cache.rs` | `try_boot` 启动期预读 `graph/` 的 `sys_/menu_/config_/slf_/btn_/cursor/diss/prompt/mouse` 前缀，单条 ≤4 MiB、总预算 96 MiB |
| 解码 | `texture.rs`、`crates/rfvp/Cargo.toml`、`platform/switch/host/Cargo.toml`、`platform/switch/build_switch.sh` | BGRA→RGBA 等转换改 `chunks_exact` 块拷贝 + `ImageBuffer::from_raw`；新增 feature `switch-zlib` 用 devkitPro zlib `uncompress()` 替代 miniz；链接加 `-lz` |
| 观测 | `graph_buff.rs`、`ring_log.rs` | 单文件解码 >4 ms 打 `graph decoded ... us=`、inflate/convert 分项 `graph decode split`；ring 容量 1200→4000 |

## 效果（Citron，真机复杂存档）

| 指标 | P16 基线 | P17 |
| --- | --- | --- |
| 重复打开 ESC 菜单 | 每次整套重解码（350–1417 ms 慢帧） | 缓存命中，两次截图**逐字节相同**、无解码/存档慢帧 |
| 首开 UI 图集 | 数十张现读现解 | 启动预读 66 张，运行期仅再解码 10 张 |
| `graph/slf_load_bg` 解码 | （miniz）57.9 ms | **36.7 ms** |
| 66 张 `graph/*` inflate 合计 | 204.4 ms（miniz） | **133.7 ms**（zlib，1.53×） |
| 缓存命中 | 无缓存 | `graph cache hit` 193、`vfs cache hit` 106、texture 缓存峰值 123/160 MiB |

## 产物（P17）

- `rfvp.nro` 7,905,336 B，SHA-256 `331e0a254034777da2c478091725a914097e5b25bae1153671ad2d07ad0e930c`
- `rfvp.elf` 17,218,328 B，SHA-256 `0c216c9bb52a16d0bd12a5762c06e21eb4120e490b9a55f0fd6aa26cbe226ae0`
- NSP v1.0.5 见 `docs/builds/023-rfvp-resource-cache.md` §6.3；证据 `docs/milestones/evidence/P17-rfvp-cache/`


# rfvp-async-decode.patch（GalNX P18，增量）

`rfvp-async-decode.patch` — 修用户 m23257 复验 P17 后剩下的两类卡顿：**CG 里的表情切换**与**背景切换**。做法=大图（≥1 MiB）解码移交 worker 线程 + 主线程保留旧图 + 读档 restore 走同一队列。**必须先应用 P17 后的全量状态**（`rfvp-full.diff` 上一版，sha `6930bb65…`）。

- 上游：https://github.com/xmoezzz/rfvp，同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 补丁大小：43,704 B / 1,089 行 / 17 文件（含新增 `crates/rfvp/src/subsystem/resources/async_decode.rs`、`platform/switch/host/src/decode.rs`）/ SHA-256 `7c0c13672027a8be251e07869d65cbced77ad7ed2107bc286c4e76ba6afe3565`
- 全量对照：`rfvp-full.diff` 190,338 B / 4,858 行 / 17 文件 / SHA-256 `5c012b7ae20835a227d5b25b7921c937b1c6564c9bf7c2bb8ce384c9292789fe`（HEAD→当前工作树）
- 应用：`git apply .../rfvp-full.diff`（也可以在前面各增量补丁之上再 apply 本补丁）
- 记录：`docs/builds/024-rfvp-async-decode.md`

## 文件清单（分组）

| 组 | 文件 | 作用 |
| --- | --- | --- |
| 队列 | `resources/async_decode.rs`（新）、`resources/mod.rs` | `QUEUE/DONE/PENDING/REQUESTED` 四表；`Job` + `KIND_GRAPH`/`KIND_PARTS`/`KIND_GRAPH_PREFETCH`；阈值 `ASYNC_INLINE_MIN_BYTES=1 MiB`；`run_next_job/wait_for_*/prefetch_path` |
| 接线 | `components/syscalls/graph.rs`、`components/syscalls/parts.rs`、`resources/graph_buff.rs`、`resources/parts_manager.rs`、`resources/motion_manager/mod.rs`、`resources/texture.rs`、`resources/vfs.rs` | graph/parts 加载命中大图时排队并保留旧纹理；`apply_snapshot_v1` 增加 `async_id`，restore 的大图同样排队；`vfs` 提供 `pack_location` |
| 应用 | `no_std_core.rs` | 每帧 `apply_async_decodes()`（`requested_matches` 防陈旧结果） |
| 宿主 | `platform/switch/host/src/decode.rs`（新）、`host/src/lib.rs`、`host/Cargo.toml`、`platform/switch/runtime/main.c`、`platform/switch/build_switch.sh` | `rfvp_switch_decode_step` + `threadCreate` 解码线程；编译新文件 |
| 其它 | `gaiji_manager.rs`、`crates/rfvp/Cargo.toml` | 快照应用签名对齐；依赖整理 |

## 效果（Citron，真机复杂存档进入 CG）

| 运行 | 措施 | CG 入口慢帧 |
| --- | --- | --- |
| p18-i | prefetch + wait | 632.2 ms |
| p18-j | + 大图异步（主线程保留旧图） | 299.1 ms |
| p18-k | + restore 走异步 | **273.4 ms** |

p18-k 帧 2601：`vm 145.41 / render 116.17 / tree 28.16 / audio_cmds 85.38 / vfs_read 23.74 / upload 27.63`，`ops 0`；异步 apply 6 次，0 exception。

## 两条负结果

1. **大图 `return Nil` 直接异步**：破坏游戏加载时序（重复同步加载、id 重分配、worker 与主线程争 pack 锁），`applied=0` —— 弃用；
2. **libdeflate 替换 inflate**：交叉编译接入后 Citron 启动 5.58 s 崩溃（`Cannot execute instruction at unmapped address 0x0`，CPU 特性派发取到空指针）—— 回退 devkitPro zlib。

## 产物（P18）

- `rfvp.nro` 7,929,912 B，SHA-256 `796679cefb5fbfae5af3028d327970883baa2093fbb0a6a16fc29a409e19076c`
- `rfvp.elf` 17,254,624 B，SHA-256 `741b92eae1b2dc7f516f83fd6b71b7c4e7a71b54080eae40a9101204dfa4f92b`
- NSP v1.0.6 见 `docs/builds/024-rfvp-async-decode.md` §5.1；证据 `docs/milestones/evidence/P18-rfvp-async/`

## 构建注意

`platform/switch/build_switch.sh` 里的 `rustup toolchain install` 在离线/网络抖动时会失败（`static.rust-lang.org` TLS 000）；本地用 wrapper 先 sed 删该行再执行，增量构建约 13–15 s。


---

## P19（v1.0.7）：异步解码运行时开关（真机黑屏回归修复）

- 上游：同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 增量补丁：`rfvp-async-toggle.patch` 6,988 B / **189 行 / 4 文件** / SHA-256 `6bdc0a61f65950cd9c0549c4dcd77370526cf9862c61f183cb03f06f5820208d`
- 全量对照：`rfvp-full.diff` 194,079 B / **4,968 行** / SHA-256 `d0a5d09042b03fae6159e69316da69f150f8352a52a41d7c2cf43e80e8f28c60`（P19 基线，含 P11–P19 全部改动；P18 时为 190,338 B / 4,858 行 `5c012b7a…`）
- 应用：`git apply .../rfvp-async-toggle.patch`（在 P18 全量之上），或直接 `git apply .../rfvp-full.diff`
- 记录：`docs/builds/025-rfvp-async-toggle.md`

### 改动（4 文件）

| 文件 | 改动 |
| --- | --- |
| `crates/rfvp/src/subsystem/resources/async_decode.rs` | +42 行：`async_enabled()`（`switch-async` + `no_std` 时读 `rfvp_switch_async_enabled()`）+ 五个入口 guard（submit_graph/submit_parts/submit_prefetch_graph 返回 false；wait_for_graph/wait_for_parts 直接查缓存） |
| `platform/switch/runtime/main.c` | +51/−4：`g_rfvp_async_enabled` 默认 0、`read_async_enabled()` 读 `sdmc:/switch/rfvp/async.txt`、`write_async_status()` 写 `async_status.txt`、`threadCreate/threadStart` 检查返回值、heartbeat |
| `platform/switch/host/Cargo.toml` | 版本 `0.1.0` → `1.0.7` |
| `Cargo.lock` | 版本同步 1 行 |

### 背景（为什么默认关）

P18 的 worker 线程在 `main.c` 里**无条件创建且不检查返回值**，而 `graph_load` 对大图 `submit_graph` 成功后立即 `return Ok(Variant::Nil)`。真机上若线程未起/未跑，大图永远拿不到内容 → **启动黑屏**（Citron 线程正常，无法复现）。P19 把异步改为运行时开关、默认关闭，关闭时回落到同步解码（等价 v1.0.5），并落 `async_status.txt` 供 A/B 判定线程状态。

### 效果与代价

- 默认关：真机可玩性优先，P18 的 CG 入口 632→273 ms 不再生效（同步解码，与 v1.0.5 同档）；
- 打开方式：`sdmc:/switch/rfvp/async.txt` 写入 `on`（或 `ON`/`1`）后重启，`async_status.txt` 会显示 `enabled=1 create=0x0 start=0x0 hb=…`；
- 若 A/B 证明 async 在真机可用，后续版本可重新默认开启并保留兜底。

## 产物（P19）

- `rfvp.nro` 7,929,912 B，SHA-256 `a6efe53b6af9253653eacc62bc91ce058972fbef08c783072648ef27c06fad0f`
- `rfvp.elf` 17,257,504 B，SHA-256 `98c6464b76b4e429f2d031d1bb5d5ec98b31cefe0195a95714b912f779c74fb5`
- NSP v1.0.7 见 `docs/builds/025-rfvp-async-toggle.md` §4.3；证据 `docs/milestones/evidence/P19-rfvp-async-toggle/`

---

## P20（v1.0.8）：异步解码阶段诊断 + 看门狗自愈

- 上游：同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 增量补丁：`rfvp-async-watchdog.patch` 10,494 B / **280 行 / 5 文件** / SHA-256 `3613a6dbe97fdcb80cae322e5e81cf433f8814c4ea91dc9ff61f1b0ef53ddafb`
- 全量对照：`rfvp-full.diff` 198,586 B / **5,082 行 / 33 文件** / SHA-256 `197208462f7c615b72ebdc0982140eb19802732163c79e7ef1f571b8be3e3ec6`（P20 基线，含 P11–v1.0.8；P19 时为 194,079 B / 4,968 行 `d0a5d090…`）
- 应用：`git apply .../rfvp-async-watchdog.patch`（在 P19 全量之上），或直接 `git apply .../rfvp-full.diff`
- 记录：`docs/builds/026-rfvp-async-watchdog.md`

### 改动（5 文件）

| 文件 | 改动 |
| --- | --- |
| `crates/rfvp/src/subsystem/resources/async_decode.rs` | +137/−31：`report_stage()`（0 idle/1 pop/2 read/3 decode/4 publish）；`WATCHDOG_STALL_US=3s` + `watchdog_stalled()`；`drain_inline()`；`finish_job()` 抽取 |
| `crates/rfvp/src/no_std_core.rs` | +12：`apply_async_decodes` 开头检测卡死 → inline drain + 关 async + 告警 |
| `platform/switch/runtime/main.c` | +23/−4：`rfvp_switch_async_stage()` / `rfvp_switch_async_disable()`；`async_status.txt` 增加 `stage=`；每 600 帧刷新；线程栈 0x20000→0x100000 |
| `platform/switch/host/Cargo.toml` | 版本 `1.0.7` → `1.0.8` |
| `Cargo.lock` | 版本同步 1 行 |

### 背景（真机 async=on 黑屏的确证）

用 MTP 从真机取到 async=on 那次会话的 `async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=4`：线程创建/启动都成功、心跳只到 4 次，随后整进程在 60 帧内冻结（`debug_report.txt` 未刷新、无 crash report、无 `last_error.txt`）→ **挂起而非崩溃**，最可能是 worker 在首个 decode 内持锁阻塞、主线程随后自旋。P20 因此加阶段诊断（卡在哪一步一目了然）+ 看门狗（最坏黑 3 秒后自动同步补完并关掉 async）。

### 效果与代价

- 默认仍关闭 async（真机可玩性优先）；打开方式不变：`sdmc:/switch/rfvp/async.txt` 写 `on`；
- `async_status.txt` 现在带 `stage=`，下次真机复现可直接读出卡点；
- 看门狗只救「worker 卡住但主线程仍进帧」的情形，若主线程自旋则无能为力（U2），故本版不默认开。

## 产物（P20）

- `rfvp.nro` 7,929,912 B，SHA-256 `d16fc0d3781965cf26dc4e4d9040e09dd9c17d3c347b7f934f659ad5d218921a`
- `rfvp.elf` 见 `docs/builds/026-rfvp-async-watchdog.md` §5
- NSP v1.0.8 见同文档 §4.3；证据 `docs/milestones/evidence/P20-rfvp-async-watchdog/`、`docs/milestones/evidence/P20b-device-crash/`

---

## P21（v1.0.9）：async 强制关闭 + 帧心跳（真机黑屏止血）

- 上游：同 pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 增量补丁：`rfvp-async-off.patch` 3,490 B / **2 文件 +25/−10** / SHA-256 `35658e39b30e3419b14f19a46dd97b2b40442eac0e6f3ef89430702670d83505`
- 全量对照：`rfvp-full.diff` 199,493 B / **33 文件 +3,811/−247** / SHA-256 `9901a14dcd33fa448f9ff58add2a04daa49b00b4f17992e44859d3ba311efd43`（P21 基线，含 P11–v1.0.9；P20 时为 198,586 B / `19720846…`）
- 应用：`git apply .../rfvp-async-off.patch`（在 P20/v1.0.8 全量之上），或直接 `git apply .../rfvp-full.diff`
- 基线复现：`git worktree add --detach /e/galnx-build/p21/rfvp-v108 9f07ade` + apply v1.0.8 全量 diff（`198,586 B`）+ commit → 覆盖 v1.0.9 的 `main.c`/`host/Cargo.toml` → `git diff`。**注意**：按 README 增量链 replay 会在 `rfvp-input-remap.patch` 处 `event.rs:1` context 失败，增量链不可靠。
- 记录：`docs/builds/027-rfvp-async-off.md`

### 改动（2 文件）

| 文件 | 改动 |
| --- | --- |
| `platform/switch/runtime/main.c` | `read_async_enabled()` 改为恒返回 0（不再读 `async.txt`，注释记录 v1.0.8 `hb=3 stage=0` 冻结签名与看门狗失效原因）；新增 `debug_probe_enabled()`（探测 `debug.txt`）与 `write_frame_status()`（写 `frame_status.txt`）；主循环 `frame==1` 或每 15 帧写心跳（仅 `debug.txt` 存在时） |
| `platform/switch/host/Cargo.toml` | 版本 `1.0.8` → `1.0.9` |

### 背景（为什么直接关掉 async）

真机 async=on 时 `async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=3 stage=0` → 整进程挂起，看门狗只在主线程帧 tick 调用所以永远不执行。根因是 **worker 与主线程同 ideal core + 主线程在 pack 的 `spin::Mutex` 上用户态自旋**（详见 `docs/experiments/rfvp-async-hang-rca.md`），正确修复属并发模型层改动，风险高，不应与黑屏止血捆绑。v1.0.9 因此永久关闭 async，保留同步路径全部性能补丁；async 并发修复另立实验。

### 效果与代价

- 真机黑屏路径（async worker）不再可能触发；`async_status.txt` 恒为 `enabled=0 …`（即使 `async.txt=on`）；
- 新增 `frame_status.txt`（`frame=<n> status=<c> async=0`）用于下次真机取证区分「启动卡住」与「渲染卡住」；
- 代价：P18 的 CG 入口 632→273 ms 收益失效，CG/背景切换回到 P17 同步档（缓存+预读仍在）。

## 产物（P21）

- `rfvp.nro` 7,929,912 B，SHA-256 `d34380df1bdd67665116cd37c5f0488b465e7acbd5c20eec6ba8eea55e42f7ca`
- `rfvp.elf` 17,258,040 B，SHA-256 `e06b165228e6b6ce7aee08f8c020cb80b5faa161b4236235de06ec6c609af6ff`
- NSP v1.0.9：9,979,495,640 B / SHA-256 `726bb2d1b0494256b5e5b12ca9d8e08b053ab56022593f562762d256c0d3c0d9`（`E:/galnx-build/p21/out/`，不入库）
- 证据：`docs/milestones/evidence/P21a-v109-nsp-smoke/`

## P29（v1.1.5-test）：OP 视频播放（na_wmv_player no_std 移植，未并入主线）

- 背景：no_std 构建未启用 `native-video`，`crates/rfvp/src/videoplayer/mod.rs` 的 `open()` 直接 `bail!("no movie decoder in this build")` → `movie_play` 返回 Nil，脚本继续 = 序章→第一章 OP 被跳过。
- 改动：`na_wmv_player` 移植到 no_std + `switch-video` feature；`videoplayer/horizon.rs` 流式 Read+Seek；`raise_layer`；vfs `pack_location` 支持 loose 流式。
- 产物：NSP `/e/galnx-build/p29/out/IROSEKA_FHD-010047420000a000-v1.1.5-test.nsp` 9,979,732,184 B sha256 `9fbc17b04e2d8c4149a96ef5f740ba7a2a5cd381bfe5ca26186fc740c9e0aab0`；增量补丁 `rfvp-op-movie.patch`（46,709 B sha256 `95abafc8…`，基于 1c7c6e4 = v1.1.4）。
- Citron：OP 可播放（软解约 6 fps、静音），回归通过；尚未并入 v1.1.6 音频 JIT 线，待合并后另出 1.1.7-test。
- 文档：`docs/builds/036-rfvp-op-movie.md`。

## P30（v1.1.6-test）：音频 JIT（修复 3 秒延迟）

- 背景：P27 的 3.07 s 预渲染 ring 稳态被填满 → 所有音频比游戏状态晚约 3 s 触发（v1.1.4-test 真机反馈）。
- 改动：音频线程按需 apply `AudioCommand` 并即时 mix（JIT）；帧线程只入队；删除 ring/producer；保留 `stall` 注入与 `audio_status.txt`（新增 `mode=jit`/`lag_ms`/`max_refill_gap_ms`）。4 文件 +508/−382。
- 产物：NSP `/e/galnx-build/p30/out/IROSEKA_FHD-010047420000a000-v1.1.6-test.nsp` 9,979,505,368 B sha256 `d7eb77ecf8bcba1f131ccaa5e26136a913e080203ccf096eca51e3e995e14461`；增量补丁 `rfvp-audio-jit.patch`（1,059 行 sha256 `e81cd49c…`）。
- 全量（仓库外）：`/e/galnx-build/p30/rfvp-full-v116.diff` 688,326 B sha256 `a489c3e9…`（37 files +13,089/−8,590）。
- 验收：Citron 注入 3×1.2 s 停顿，`lag_ms=-101`、`underrun=0`、rendered 每次推进 ≈1195 ms；真机待验。文档 `docs/builds/037-rfvp-audio-jit.md`、证据 `docs/milestones/evidence/P30a-audio-jit/`。

## P31（合并树，非增量补丁）：OP 视频并入音频 JIT 主线

- P29 与 P30 都基于 v1.1.4（1c7c6e4）且都改 `platform/switch/runtime/main.c`，**不能顺序 apply**。P31 用「反向合并」得到合并树：复制 P29 工作树 → 用 P30 的 `host/src/audio.rs`（JIT 版）与 `main.c` 覆盖 → 手工把 P29 的 `rfvp_switch_debug_movie()`（`debug.txt` 的 `movie=1`）插回 `rfvp_switch_async_disable()` 之后 → 版本改 `1.1.7-test`。合并后编译通过（22 s）。
- 坑：P29 工作树的 `.git` 是指向 p25 仓库的 worktree 指针文件，复制前必须删除。
- 素材：1080p 原片（VC-1 16 Mbps 59.94 tbr）宿主 decode+convert 29.7 ms/帧，Switch 无法实时 → 转 720p30 wmv2 8 Mbps（124,386,038 B sha `62abe508…`），540p30（84,808,438 B sha `76cedf0b…`）作退路。
- 两处 OP 调试钩子细节见 P32（flag 必须非 nil 才有音轨）。
- 记录：`docs/builds/038-rfvp-op-playback.md` §2–§4。

## P32（v1.1.7-test）：OP 音轨（同名 OGG，不改视频容器）

- 背景：no_std 无 WMA 解码器，P31 的 OP 只能静音。
- 思路：读取与 `.wmv` 同名的 `.ogg`（`movie/01.wmv` → `movie/01.ogg`），缺失只 warn、无声播放。
- 增量补丁：`rfvp-op-audio.patch` 338 行 / **3 文件 +203/−18** / SHA-256 `9e4297798fd6ea74f7d694743aa8645bdbc842552f5e470976537f619f2624c8`。
- **基准是 P31 合并树（P29+P30），不是单一 commit**；roundtrip 已在 P31 树拷贝上验证（`-R --check` → 反应用 → `--check` → 前应用 → `diff -r` 逐字节一致）。
- 改动（3 文件）：
  - `crates/rfvp/src/host_api/audio.rs`：新增 `AudioSlotKind::Movie`；`AudioStreamId::MOVIE = Self(0x2000)` 在 `classify()` 归为 Movie；mixer 容量检查对 Movie 直接 Ok（最多一路）。
  - `crates/rfvp/src/no_std_core.rs`：`movie_play` 调试钩子 flag 由 `Nil` 改 `True`（Nil 会映射 `MovieMode::LayerNoAudio` → 无音轨）。
  - `crates/rfvp/src/subsystem/resources/videoplayer/horizon.rs`：`MovieAudio`（`Arc<AudioManager>` + 内存 `Arc<[u8]>`）；`open()` 时读入 `movie/01.ogg`；**首个视频帧呈现时**才 `backend.load/play(AudioStreamId::MOVIE, Bytes, ...)`，命令进 P30 JIT 队列；`stop`/`Drop` 发 stop+unload。
- 全量对照（仓库外）：`/e/galnx-build/p31/rfvp-full-v117.diff` 305,725 B sha256 `cf911433f8983779f8c96659f7b989684c1f159d4494f4945affe30cda3a1270`；62 文件 +5,889/−296；基准 upstream `9f07ade` 且**两侧 LF 规范化**（直接 diff 会因 CRLF 得到 20.3 MB 假差异），apply 验证 `FULL_APPLY_CHECK_OK`。
- 产物（v1.1.7-test）：
  - `rfvp.nro` 8,290,360 B sha256 `a8fb7b7ba5f86f7e75f5c9fcc7ca218a75f9a3be1db6a9221581bade8fbf78a8`
  - `rfvp.elf` 17,684,312 B sha256 `e9ee44c986150d79a0e00b6ccaa5283601561b61a7f6c0646c08ddc1aa60c02f`
  - NSP `E:/galnx-build/p31/out/IROSEKA_FHD-010047420000a000.nsp` 9,861,393,624 B sha256 `cb019f27136b5b80936c5c5067477c6a08e19ae02a6535f48e9f12785ba16c7d`（romfs 162 项 9,814,160,982 B）；`galnx package nsp verify` = ok / 12 checks（0 fail，1 未签名 warn）
- 验收：P32 NRO 形态 Citron PASS（`movie audio: loaded/playing`、37 帧、`underrun=0`、lag -113 ms）；最终 NSP 冒烟见 `docs/builds/038-rfvp-op-playback.md` §6.2–6.3。
- 记录：`docs/builds/038-rfvp-op-playback.md`。

## P33（v1.1.9-test）：OP 分档（720/540/480/360）+ 原生尺寸路径

- 背景：P32 的 v1.1.7-test 在 Citron 上只有 15 FPS（`MAX_DECODE_PER_TICK=1`），720p30 软解在真机可能仍慢；且 720p 源在 no_std 路径会软件上采样到 1920×1080 再上传，浪费缓冲与带宽。
- 增量补丁：`rfvp-op-quality.patch` 30,381 B / 727 行 / **10 文件 +414/−79** / SHA-256 `76e2f12dfe1759b215a3abfede0af9a907e91e0184c26794760b95c42b90a920`。
- **基准是 P32 合并树（`3dd9e56` = v1.1.7-test），不是单一 commit**；验证：在 3dd9e56 worktree `git apply --check` rc0、apply 后与 p31 树比对 1135 文件仅 `platform/switch/build_switch_instr.sh`（本机构建脚本，故意不入补丁）不同。
- 改动（10 文件）：`videoplayer/horizon.rs`（`video.txt` 选档、变体命名/回退、`yuv420p_to_rgba_native_into`、spare buffer 复用、宿主时钟计时、`movie=nil` 调试）、`videoplayer/mod.rs`、`no_std_core.rs`、`host_api/audio.rs`（日志）、`color.rs`、`graph_buff.rs`、`motion_manager/mod.rs`、`prim_commands.rs`、`lib.rs`、`platform/switch/runtime/main.c`（`rfvp_switch_movie_quality` / `rfvp_switch_debug_movie_nil`）。
- 素材：`movie/01_q540.wmv` 59,387,638 B、`movie/01_q480.wmv` 38,610,038 B、`movie/01_q360.wmv` 17,870,838 B（均无音轨），romfs 9,814,160,982 → **9,930,029,496 B / 165 项**；音轨仍为 `movie/01.ogg`。
- 全量对照（仓库外）：`/e/galnx-build/p33/rfvp-full-v119.diff` 324,166 B / 8,182 行 / 62 文件 +6,250/−322 sha256 `e1793be2d35a9a01a9a8296b5f08e69ebd41a200d7c1994527fbf96d9d224a34`；基准 upstream `9f07ade`（两侧 LF 规范化）。
- 产物（v1.1.9-test）：`rfvp.nro` 8,228,920 B sha256 `cb018355…`；`rfvp.elf` 17,421,312 B sha256 `d8daa643…`；NSP `E:/galnx-build/p33/out2/IROSEKA_FHD-010047420000a000.nsp` 9,977,492,184 B sha256 `bd909c1eb1e6e3f9339a28b662943d0d06f74873b2dd36639824df54a90b535b`（verify 13 checks / 0 fail / 1 warn 未签名）。
- 验收：NSP 形态 Citron 36/36 步 PASS（`video.txt=480` → 打开 `01_q480.wmv level=2`，854×480 原生尺寸，decoded/presented 2880 帧 / pts 119,958 ms，`lag_ms=-108 underrun=0`）；真机待验。
- 记录：`docs/builds/039-rfvp-op-quality.md`。

## P34（v1.1.10-test）：WMV2 左缘马赛克修复（宏块对齐 + 裁剪输出）

- 背景：v1.1.9-test 真机 OP「很流畅，但糊；最左侧有一列均匀排布的马赛克方格」。源文件干净（ffmpeg 第 720 帧左缘正常），Citron 可稳定复现 → 缺陷在我们自己的解码链路。
- 根因（`crates/na_wmv_player`）：WMV2 视频宽 854（= 16×53 + 6，非 16 对齐），`mb_w = 854.div_ceil(16) = 54`，末列宏块 `bx = 848/856`；
  `na_wmv2dsp.rs:102/127` 的 IDCT 写入循环只判 `idx >= dest.len()`，**没有行边界守卫**，越界字节按 stride 折返到**下一行行首** → 每行开头 0..9 列被画面右端内容覆盖；P 帧 MC 再从被污染的参考帧向内扩散。
  同文件 `write_intra_block`/`add_residual_block_i16` 等 4 条写路径都有守卫，只有 IDCT 两条漏了。chroma 侧同样溢出（`mb_col*8 = 424`，chroma 宽 427）。
- 增量补丁：`rfvp-wmv2-padding.patch` 101 行 / **1 文件**（`crates/na_wmv_player/src/api.rs`）/ SHA-256 `b221b70819a244060ad4dcbd54e33c630d1b49c4937e763cb027a740a51a8c7e`。
- **基准是 P33 树（v1.1.9-test）**；只改 `na_wmv_player`，与其它补丁无文件冲突。
- 修法（照搬同 crate 里 Wmv3/WVC1 的既有模式）：coded 尺寸（864×480）解码 + `visible_frame/crop_frame` 裁剪回 854×480 输出。要点：
  - `Wmv2Params::new` 必须传 coded 尺寸，否则 `decoder.rs:6395` 会把 `MacroblockDecoder` 重置回 854×480（padding 失效）；
  - 参考帧保持 coded 尺寸（P 帧 MC 在完整宏块面上做）；`ffi.rs` 取 `current_frame()` 拿到的是裁剪后的 display 帧（stride = 854）。
- 验证（宿主 oracle，可复跑 `E:/galnx-build/p33/probe-wmv`，path 依赖本 crate，对照 ffmpeg rawvideo 第 720 帧）：
  mean |ΔY| **2.918 → 1.470**；`|Δ|>32` 像素 **6,777（1.653%）→ 30（0.007%）**；左 12 列均值 **63.35 → 3.36**；右缘 0.22 → 0.18（无回归）；「行首被复写」检测 **29/58 行 → 0/0**；输出仍 854×480。
- Citron（NRO）：`01_q480.wmv` 854×480，decode_us 8.1–15.2 ms / convert_us 3.4–6.0 ms（与 P33 基线持平），左缘干净（`cmp-new-left.png` vs `cmp-old-left.png`），0 exception。
- 产物（v1.1.10-test）：
  - `rfvp.nro` 8,228,920 B sha256 `a80f728977eb3cf38e8b3582e944ff862b31ab086568c649f3090b827e2e3a83`
  - `rfvp.elf` 17,421,328 B sha256 `c516046b1f81c49c1338c4562c0f06031b4c5d6e1b14202640af7f4e72374cbb`
  - NSP `E:/galnx-build/p33/out3/IROSEKA_FHD-010047420000a000.nsp` 9,977,492,696 B sha256 `fc35fa9880ba9e38db737f2648bfa309b4e54ab0dd2571265af58d7156c4ee1d`（verify 13 checks / 0 fail / 1 unsigned warn）
- 记录：`docs/builds/040-wmv2-left-edge.md`；证据 `docs/milestones/evidence/P34-wmv2-left-edge/`。

---

## P40（v1.2.0-test）：OP 换 H.264 + NVDEC(nvtegra) 硬解接入

- 背景：真机 OP 是 `wmv2`，Tegra 无 WMV2 硬解；probe9 真机证明 NVDEC 解码 297.80 fps、CE 传输 3.79 ms，慢放唯一主因是 CPU NV12→RGBA 43.54 ms（标量）。本补丁把 OP 换成 H.264 + nvtegra 硬解 + NEON NV12→RGBA。
- 上游：https://github.com/xmoezzz/rfvp，pin HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
- 基准树：`/e/galnx-build/p31/rfvp-v117`（P33 分档 + P34 WMV2 左缘修复之后的整树）
- 补丁：`P40-op-h264.diff` **41,286 B / 1,179 行 / 7 文件** SHA-256 `026e34c189a743a89300b1e74e4fdc6db393f73362dda6bb71019be59f04b491`
- 应用：`git apply P40-op-h264.diff`（对基准树 `git apply --check` 已通过）
- 依赖：`averne/FFmpeg` nvtegra 分支静态库（`--enable-nvtegra --enable-hwaccel=vc1_nvtegra,wmv3_nvtegra,h264_nvtegra`），见 `docs/builds/044-nvdec-probe6.md`；构建时用 `RFVP_FFMPEG_SRC`/`RFVP_FFMPEG_BUILD` 指向源码与构建目录
- 记录：`docs/builds/046-op-h264-nvtegra.md`；证据 `docs/milestones/evidence/P40-op-h264/`

### 文件清单

| 文件 | 作用 |
| --- | --- |
| `platform/switch/runtime/rfvp_movie_h264.c`（新） | FFmpeg + nvtegra 播放器（init/open/next/close + NV12 平面与 pts getter；`file:` 前缀、持久错误缓冲、`h264_sw.txt` 强制软解） |
| `platform/switch/runtime/rfvp_movie_h264.h`（新） | API 声明 |
| `platform/switch/runtime/rfvp_movie_color.c`（新） | BT.709 limited→full 定点 + NEON 16 像素 kernel（NV12 / YUV420P → RGBA） |
| `crates/rfvp/src/subsystem/resources/videoplayer/horizon_h264.rs`（新） | `H264Playback` 实现 `MovieSource`，复用 `load_movie_audio`；失败回落 WMV2 |
| `crates/rfvp/src/subsystem/resources/videoplayer/horizon.rs` | 子模块声明 + `open()` 先试 `h264_movie::try_open` |
| `platform/switch/runtime/main.c` | `galnx_movie_init(game_root)`（在 `rfvp_switch_start` 前） |
| `platform/switch/build_switch.sh` | FFmpeg 头/库路径、新源文件、`--start-group` 链接三静态库 |

### 产物（v1.2.0-test）

- `rfvp.nro` 10,670,136 B sha256 `875336aa1efb0996abff222429bca80eaca0867fb648be1ed826eb5f9de39519`
- `rfvp.elf` 20,397,352 B sha256 `9ff49413bd9e5d7e04a82375b24f31a722296dccec993878a228cbd265b9197f`
- NSP `E:/galnx-build/p40/out/IROSEKA_FHD-010047420000a000.nsp` 10,087,535,320 B sha256 `5bc45ace24a3b262ebbbbc09f74652921237bc6e65a01e1065a39ceb82d8b3e8`（verify 13 checks / 0 fail / 1 未签名 warn）

### 验收

- 资产：`game/movie/01_h264.mp4` 108,361,267 B sha256 `bddf82fc7e78e256d812051a4f548c2dce07d8cdcda6c80562ea588f32757bad`（h264 High 1280x720 BT.709，120.0 s）
- Citron NRO 影子：整段 OP 3597 帧 EOS，`convert_us` p50 2,520 µs
- Citron NSP(romfs)：24/24 步 ok，`Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4`，3597 帧 EOS，OP 后 `60.0 fps slowest 18.1 ms`
- 真机 60 fps 待用户验收（Citron 无真 NVDEC，冒烟走 `h264_sw.txt` 软解）

---

## P40b（v1.2.1-test）：修正 NV12 色度步进（真机 OP 颜色异常）

- 背景：P40 在真机上 OP 不慢放但颜色错误——亮度正常、色度横向 2 倍拉伸（用户 m36342）。根因是 `nv12_row_neon()` 每 16 个输出像素只前进 8 个交织 UV 字节（`uvr + (i >> 1)`），只有真机硬件帧（NV12）会走到这条分支；Citron 冒烟强制软解走 planar 分支，故未被发现。
- 上游：同 P40（rfvp pin `9f07adef2eb5d559777f9bf59a67b756875cb24f`）
- 基准树：P40 态（`/e/galnx-build/p31/rfvp-v117` + `P40-op-h264.diff`）
- 补丁：`P40b-nv12-color.diff` **226 行 / 4 文件** SHA-256 `2904ab90b4a271125e5a628c64100d8ebbc83039abc7ddb3b7f19671f59931e4`
- 应用：`git apply P40-op-h264.diff` 之后 `git apply P40b-nv12-color.diff`（已对 P40 态 `git apply --check` 通过，应用后 4 文件与工作树逐字节一致）
- 记录：`docs/builds/047-p40b-nv12-colour-fix.md`；证据 `docs/milestones/evidence/P41-op-nv12-color/`

### 文件清单

| 文件 | 作用 |
| --- | --- |
| `platform/switch/runtime/rfvp_movie_color.c` | `nv12_row_neon()` 的 UV 地址 `uvr + (i >> 1)` → `uvr + i`（以及 `+ 4` → `+ 8`） |
| `platform/switch/runtime/rfvp_movie_h264.c` | 新增 `g_nv12_selftest` 开关（marker `sdmc:/switch/rfvp/h264_nv12_selftest.txt`）与 getter |
| `platform/switch/runtime/rfvp_movie_h264.h` | `int galnx_movie_nv12_selftest(void);` |
| `crates/rfvp/src/subsystem/resources/videoplayer/horizon_h264.rs` | 影子比较（planar 帧重打包 NV12 → 硬件 kernel → 逐字节比 + FNV-1a 64），默认关闭 |

### 产物（v1.2.1-test）

- `rfvp.nro` 10,670,136 B sha256 `b93f34e3f4b1f50f4c0d43f1817199fbf39c14431d1f78969f5f2e52ebbdbee9`
- `rfvp.elf` 20,399,744 B sha256 `c9abd983182dc27ceb983a86cb5f1e4d9b434d45513fc36956acb82bcba78184`
- NSP `E:/galnx-build/p40/out121/IROSEKA_FHD-010047420000a000.nsp` 10,087,536,344 B sha256 `16d4cee091cdbe64ba3660344d29e781974b114ac24b60648c51afb2721e162d`（verify 13 checks / 0 fail / 1 未签名 warn）

### 验收

- Citron NRO 影子：103 条 `nv12 shadow` 全 `match=1 diff_bytes=0`（frame 1…2940）
- Citron NSP(romfs)：24/24 步 ok、`Movie: opened (Switch NVDEC H.264)` 从 romfs 打开、109 条 shadow 全 match（frame 1…3120）、`convert_us` p50 2,530 µs
- 真机颜色待用户验收（模拟器无法覆盖硬件帧分支）

## P40c（v1.2.2-test）：OP 改回剧情触发并可跳过

- 背景：P40/P40b 交付的 v1.2.1-test 一启动就自动播 OP 且不可跳过（用户 m36793）。根因是 P33 时代留下的调试通道 —— `no_std_core.rs:665-703` 的 tick 在 `horizon::debug_movie_requested()` 为真时调 `movie_play("movie/01.wmv", flag)`，`flag` 默认 `Variant::True`（modal），而 `main.c:101-125` 从 `sdmc:/switch/rfvp/debug.txt` 的 `movie=1` 读该开关；设备上 debug.txt 长期是 `shot=900\nmovie=1`。游戏脚本本身支持剧情触发与跳过（`iroseka.lua:38572 f_00034356` → `f_000426A7`，播片循环 `InputGetState() & 3` 即 Ctrl/Shift 跳过）。
- 上游：同 P40（rfvp pin `9f07adef2eb5d559777f9bf59a67b756875cb24f`）
- 基准树：P40b 态（`/e/galnx-build/p31/rfvp-v117` + `P40-op-h264.diff` + `P40b-nv12-color.diff`）
- 补丁：`P40c-op-story-trigger.diff` **103 行 / 3 文件 / +26 −37** SHA-256 `06f9290041ff58cf1324141e7817730f68d5314734f82f4d41220855a03a2d2b`
- 应用顺序：`P40-op-h264.diff` → `P40b-nv12-color.diff` → `P40c-op-story-trigger.diff`（已对 P40b 态工作树 `git apply -R --check` 验证一致）
- 记录：`docs/builds/048-p40c-op-story-trigger.md`；证据 `docs/milestones/evidence/P43-op-story-trigger/`

### 文件清单

| 文件 | 作用 |
| --- | --- |
| `platform/switch/runtime/main.c` | 新增 `MovieDebugFile = "sdmc:/switch/rfvp/movie_debug.txt"` 与 `read_movie_debug_file()`；`rfvp_switch_debug_movie()`/`_nil()` 只读该文件，`debug.txt` 不再触发影片 |
| `crates/rfvp/src/subsystem/resources/videoplayer/horizon.rs` | 调试播片注释改为 `movie_debug.txt` |
| `crates/rfvp/src/no_std_core.rs` | tick 内注释同步（功能不变） |

### 产物（v1.2.2-test）

- `rfvp.nro` 10,670,136 B sha256 `2666286e44a14662f1fabf00533f05f08c1f1c7e6faa96acf99a98bd92fdae19`
- `rfvp.elf` 20,400,232 B sha256 `258a312d4e77ee31d8b0c0a5442ed9f9ab6f324d0701276da9f708c1704675d3`
- NSP `E:/galnx-build/p40/out122/IROSEKA_FHD-010047420000a000.nsp` 10,087,536,344 B sha256 `51d0f8c716db614b7376776bf8d0e6004f08f21448e7b856ad41ca16d435bdda`（verify 13 checks / 0 fail / 1 未签名 warn）

### 验收

- Citron NRO：run-05/run-06 从标题 New Game 起步，debug_report 里 0 条 `MoviePlay`（启动不再自动播片）
- Citron NRO run-08（设备存档 DATA.005）：`MoviePlay: path=movie/01.wmv flag=Nil is_layer_effect=true` → `Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4` → 按 R 后 `MovieStop` 回正文
- Citron NSP(romfs)：18/18 步 ok、OP 从 romfs 打开、按 R 跳过、窗口标题 `1.2.2-test`
- 真机与 ED 待验（iroseka 无 `movie/02.*`，ED 用 moyu 02.wmv 验证）

## P41（v1.3.2-test / v1.2.4-test）：もゆ标题粒子三处修复 + 调试播片序号

- 背景：用户 m38188 对比 PC 版与 NS 版《さくら、もゆ。》标题画面，PC 版有大量红色粒子全程向上飘动，NS 版完全没有；修复过程中依次暴露三层问题（m38329/m38555）。
- 上游：同 P40（rfvp pin `9f07adef2eb5d559777f9bf59a67b756875cb24f`）
- 基准树：P40c 态（`/e/galnx-build/p31/rfvp-v117` + `P40-op-h264.diff` + `P40b-nv12-color.diff` + `P40c-op-story-trigger.diff`；本次用 `/e/galnx-build/p40/patchbase` 复现）
- 补丁：`P41-snow-particles.diff` **232 行 / 7 文件 / +116 −22** SHA-256 `4cbb337b273e92de06ebbce60f626c1b7028ddea0bfd1f232704df6104aee3ea`
- 应用顺序：`P40-op-h264.diff` → `P40b-nv12-color.diff` → `P40c-op-story-trigger.diff` → `P41-snow-particles.diff`（已对 patchbase 副本 `git apply --check` 验证，应用后与构建树逐字节一致）
- 记录：`docs/builds/049-p41-snow-particles.md`；证据 `docs/milestones/evidence/P44-snow-particles/`

### 文件清单

| 文件 | 作用 |
| --- | --- |
| `crates/rfvp/src/subsystem/components/syscalls/other_anm.rs` | `Snow()` 的 arg10 校验从 1..=1024 放宽到 -65535..=65535（arg10 是每周期 Y 位移速度，不是 flake 数；もゆ标题传 2000/2500） |
| `crates/rfvp/src/subsystem/components/syscalls/graph.rs` | `PrimSetSnow(id, mode, x, y)` 把 `mode` 写入 `prim_set_texture_id`（渲染器用 texture_id 当 snow motion slot，否则双 snow 只画第一套） |
| `crates/rfvp/src/rendering/prim_commands.rs` | `emit_snow()` 在 `base_tex + variant` 贴图未上传/缺失时回退到 `base_tex`（多 variant 预设常只预加载 base 图，否则丢 4/5 flake） |
| `platform/switch/runtime/main.c` | 新增 `rfvp_switch_debug_movie_index()`（读 `movie_debug.txt` 的 `movie=N`/`index=N`）与 `rfvp_switch_skip_probe()`（`skip=1` 时输入层强制按住 R，仅供 Citron 自测） |
| `platform/switch/host/src/event.rs` | 读取 `rfvp_switch_skip_probe()`，为真时把 R 置按住（等价真机 R→Ctrl） |
| `crates/rfvp/src/subsystem/resources/videoplayer/horizon.rs` | 新增 `pub(crate) fn debug_movie_index() -> u32`（非 horizon 平台返回 1） |
| `crates/rfvp/src/no_std_core.rs` | 调试播片钩子由固定 `movie/01.wmv` 改为 `movie/{index:02}.wmv` |

### 产物（v1.3.2-test / v1.2.4-test）

- `rfvp.elf` 20,406,336 B sha256 `0a24d18c926b6d652a074b1d51eca48fa4396a2e8dc15167cc8603ddb03f71ee`
- `rfvp.nro` sha256 `4ee6f67d956abca60c677386b4f363a055ba242e9134737d3e859ec82a54052b`
- NSP 两枚见 `docs/builds/049-p41-snow-particles.md` §5（均 13 checks / 0 fail / 1 未签名 warn）

### 验收

- Citron 标题时序差分（间隔 3 s，灰度差 >25，每万像素）：修复前 1.10 → 双 slot 修复 5.56 → 变体回退 39.49；清插桩后的干净构建 32.84、NSP romfs 33.19
- 干净构建 `debug_report.txt` 中 `snow:` 报错 0 行；1024/1024 flake 全部绘制
- `movie_debug.txt = movie=nil + index=2` 在 Citron 播放 `movie/02_h264.mp4`（真結局 OP），106 条 decoded 帧
- 真机粒子密度与 ED 行为待用户验收
