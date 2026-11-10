# 020 · rfvp 真机缺陷修复（光标 / 性能 / 原生退出 / − 键确认退出）

- 日期：2026-10-31
- 上游：rfvp `9f07adef2eb5d559777f9bf59a67b756875cb24f`（MPL-2.0）
- 前置补丁：`016` sdl2 后端 → `017` 输入 → `018` romfs → `019` 输入映射重写
- 本补丁：`patches/rfvp-switch/rfvp-device-fixes.patch`（7 文件，109,915 B SHA-256 `9b65b8b272837ad3eb17b8e7f4d785652702a005e48bd39859cd8f2887573eb6`）
- 产物：`rfvp.nro` 7,839,800 B SHA-256 `4f096dd6ae5a50647a499711f036da8658c632d8f56070433e40f1bcc7c2370f`；`rfvp.elf` SHA-256 `f34992a3e68269b51ac7e8eaacf23831ef0ee352b570b16daf5472f6616feeb3`；自包含 NSP v1.0.2（见 §7）

## 1. 症状（真机反馈）

用户在真机上试玩 P12 的 NSP（v1.0.1）后给出四项反馈（m19465 / m19535）：

| # | 症状 | 严重度 |
|---|---|---|
| 1 | 没有鼠标光标；右摇杆移动后看不到指在哪 | 阻塞（游戏大量交互依赖指针） |
| 2 | 性能卡顿：logo 动画约 20 fps、场景转场与 CG 卡、音频与画面不同步 | 高 |
| 3 | 用游戏内原生路径退出（暂停菜单 EXIT → 游戏自己的确认框）时，退出动画播完（"Dreams are the seedlings of realities."）后**永久黑屏**，不回桌面 | 高（只能强制关闭） |
| 4 | − 键既不退出游戏，也不弹确认框 | 中（缺少退出方式） |

Citron 侧复现结论：1、3、4 可稳定复现；2 在 Citron 上表现为 60 fps 但真机掉帧（见 §6）。

## 2. 根因

### 2.1 光标（#1）
引擎的 `CursorShow/CursorMove/CursorChange` 三个 syscall（`crates/rfvp/src/subsystem/components/syscalls/cursor.rs`）只把光标状态写进 `subsystem/resources/window.rs`；**消费方只有 winit（std）路径 `crates/rfvp/src/app.rs` 与软光栅 `soft_host.rs`**。Switch 走的是 `no_std_core.rs` + GLES2 路径，没有人读这份状态、也没有系统光标可借（libnx 无窗口概念）→ 光标永远不可见。

### 2.2 性能（#2）
`platform/switch/runtime/sdl_video.c` 的 `galnx_sdl_texture_create` 每次调用都 `SDL_CreateTexture` + `calloc` + 全图格式转换 + `SDL_UpdateTexture` + 立刻 `SDL_DestroyTexture` 同 id 旧纹理；`galnx_sdl_texture_update` 对非 RGBA8888 源每帧 `malloc/free` 整张图。引擎 `prim_commands.rs upload_graph_if_needed` 只在 generation 变化时 upload，但**文字每帧都在变**（对白逐字显示），所以这条路径就是每帧热路径。

### 2.3 原生退出（#3）
游戏自身的退出链最终调用 `ExitDialog()`（`crates/rfvp/src/subsystem/components/syscalls/utils.rs exit_dialog`），它只置 `EXIT_DIALOG_STATE.pending_request` 并让脚本 break；**唯一消费者是 winit 的 `app.rs take_pending_exit_dialog_request()`**（Confirmed → close_immediate）。`no_std_core` 没有消费者 → 脚本停掉、游戏淡出到黑、进程留在那里永不退出。
另外 `ExitMode(1/3)` 与窗口关闭路径也依赖桌面事件循环：retail 引擎靠"主脚本上下文已退出"结束事件循环，主机上没有这个循环。

### 2.4 − 键退出（#4）
P12 的实现是「− 键 → 合成 Esc 打开游戏暂停菜单 → 点击 EXIT → 点击确认」的宏。这个宏依赖：当前不在标题/读档界面、Esc 未被游戏吞掉、菜单坐标不变。真机上只要有一次状态不符（例如在标题画面、或 Esc 没开菜单）宏就全部落空，看起来就是"按了没反应"。**方案本身脆弱，改为不依赖游戏 UI。**

## 3. 修复

### 3.1 主机层叠加层（overlay）：光标 + 退出确认框
新增于 `platform/switch/runtime/sdl_video.c`，在 `galnx_sdl_present` 里、`SDL_RenderPresent` 之前绘制：

- `galnx_sdl_set_overlay(int cursor_visible, int x, int y, int dialog)` —— 每帧由 `main.c` 调用，把状态推进渲染层。
- `overlay_fill()`（走游戏坐标 → 屏幕映射，颜色 `0xAABBGGRR`）、`overlay_diamond()`（窗口像素坐标，与指针事件同空间）、5×7 点阵字体（字符集 `A B E G I M N O Q S T U Y ? = 空格`）与 `overlay_text()`。
- 光标：黑色描边菱形 r=9·map_scale + 白色内菱形 r·0.72，跟随引擎指针。
- 退出确认框：640×220 居中面板（外框 `0xff3a5f8a`、内底 `0xf0121a26`）+ 标题 `QUIT GAME?`（scale 6）+ 提示 `A = YES    B = NO`（scale 4，`0xff9fd8ff`）。

指针状态来源：`event.rs` 的 `HorizonInput` 新增 `pointer_seen`（首次指针事件置位）、`cursor_x/cursor_y`（已在）以及公开方法 `pointer() -> (i32, i32, bool)`；`ffi.rs` 新增 `rfvp_switch_pointer(session, &x, &y, &visible, &dialog)` 导出；`main.c` 每帧取回后调 `galnx_sdl_set_overlay`。**只有收到过至少一次指针事件才显示光标**，避免标题画面就出现一个不知所措的指针。

### 3.2 纹理路径复用 + scratch 缓冲
`sdl_video.c`：

- 新增 `static uint8_t* scratch; static size_t scratch_bytes; static uint8_t* scratch_reserve(size_t)`（只增不减的 `realloc`）。
- `galnx_sdl_texture_create`：同 id 且同宽高时**复用已有 `SDL_Texture`**，只 `SDL_UpdateTexture`；RGBA8888 源直接上传，其它格式经 `scratch` 转换一次；无像素数据时不再 `memset` 全零；新建纹理统一 `BLENDMODE_BLEND` + `ScaleModeLinear`。
- `galnx_sdl_texture_update`：RGBA8888 直传，其它格式走 `scratch`，不再每帧 `malloc/free` 整图。

### 3.3 原生退出：no_std 消费退出请求
`crates/rfvp/src/no_std_core.rs` 在 `tick()` 末尾（`frame_index` 自增之前）新增两段：

```rust
// 游戏自己的 ExitDialog() → 视为已确认退出
if take_pending_exit_dialog_request() {
    log("quit requested by the game (ExitDialog confirmed)");
    self.quit_requested = true;
    self.save_global_if_changed(host);
}
// ExitMode(3)：主脚本上下文真的退出了（retail 靠这个结束事件循环）
if !self.quit_requested && get_lock_scripter() && get_main_thread_exited() {
    log("quit requested by the game (ExitMode(3) main script exited)");
    self.quit_requested = true;
    self.save_global_if_changed(host);
}
```

`ffi.rs` 的 `rfvp_switch_frame` 因此返回 1，`main.c` 正常走收尾链（`rfvp_switch_stop` → 音频/视频/romfs 关闭）→ 回到主界面。**退出前全局存档会 flush**（`save_global_if_changed`）。

### 3.4 − 键 → 主机自绘确认框
`event.rs`：

- 新增 `quit_dialog` / `quit_confirmed` 状态；`MINUS` 按下只置 `quit_dialog = true`，不再合成任何游戏内点击。
- 确认框打开期间 **A/B 不再转发给游戏**（避免同时触发游戏内确认或返回）；A → `quit_confirmed = true`、关框；B → 关框。
- `app.rs` 新增 `take_quit_confirmed()` / `request_quit()` / `pointer_state()` / `quit_dialog_open()`；`ffi.rs` 在每帧开头消费 `take_quit_confirmed()` → 写日志 `rfvp: exit confirmed by the player, closing` → `push_event(RfvpEvent::Quit)` → 引擎正常关闭（含存档 flush）。

保留 P12 的其余映射不变：A=Enter、B=Esc、X=AUTO、Y=LOAD、+=SAVE、ZR=左键、ZL=右键、R=Ctrl、D-Pad=方向键、左摇杆=滚轮、右摇杆=光标。

## 4. 验证（Citron，模拟器侧）

| 用例 | 操作 | 期望 | 结果 | 证据 |
|---|---|---|---|---|
| V1 光标可见 | 进正文 → 右摇杆下/右 | 出现黑白菱形光标并跟随移动 | ✅ | `evidence/P12b-…/s-cursor-story.png`、`q-cursor-settled.png` |
| V2 确认框 | 游戏中按 − | 弹出 `QUIT GAME? / A = YES  B = NO` | ✅ | `o-quit-dialog.png`、`q-quit-dialog.png` |
| V3 取消 | 确认框内按 B | 关框、回游戏、游戏未收到 A/B | ✅ | p12-o step-20；p12-q step-18 |
| V4 确认退出 | 确认框内按 A | 引擎日志 `exit confirmed by the player` → 进程退出、Citron 回空游戏列表 | ✅ | `o-after-confirm-citron-list.png`、`q-exit-log-lines.txt` |
| V5 原生退出 | 暂停菜单 EXIT → 游戏确认框点「确定」 | 播完退出动画后真退出，不再黑屏 | ✅ | `q-after-native-exit.png`（= Citron 空列表）、`q-exit-log-lines.txt` 含 `ExitMode(3)` |
| V6 性能 | 同一 run 的 `debug_report.txt` | 60.0 fps；render 为全部开销 | ✅ `frame 9360: 60.0 fps … slowest 49.1 ms`；`perf avg: vm 0.00 / scene 0.02 / render 15.75 / total 15.77 ms` | p12-o run dir |
| V7 NRO 形态回归 | `rfvp: game root: sdmc:/switch/rfvp/game (no romfs)` | SD 数据仍可启动 | ✅ | p12-o citron_log |

全部 run 的 `EXCEPTION`/`panic` 计数为 0。

## 5. 与上游的差异

补丁 7 文件（相对 P12 v1.0.1 基线）：

| 文件 | 行数 |
|---|---|
| `crates/rfvp/src/host_api/event.rs` | 16 |
| `crates/rfvp/src/no_std_core.rs` | 117 |
| `platform/switch/host/src/app.rs` | 32 |
| `platform/switch/host/src/event.rs` | 878 |
| `platform/switch/host/src/ffi.rs` | 89 |
| `platform/switch/runtime/main.c` | 615 |
| `platform/switch/runtime/sdl_video.c` | 1185 |

基线复现：`git worktree add --detach /e/galnx-build/rfvp-base 9f07ade`，依次 apply 016/017/018/019 补丁，然后 apply 本补丁 —— `git apply --check` 通过。

上游 HEAD→工作树的全量对照 `rfvp-full.diff` 为 85,712 B / 10 文件，SHA-256 `f195683ed99a7e2243cc2e81e4b66cf5e30c3bb79c83c21168d7771f2463596a`；其中 `platform/switch/build_switch.sh` 与 `platform/switch/host/src/render.rs` 仅 CRLF/LF 差异（`diff --strip-trailing-cr` 相同），因此不计入增量补丁。

## 6. 性能数据

| 版本 | 场景 | fps | render | total |
|---|---|---|---|---|
| 软光栅（P8 之前） | 标题 | 17–19 | ~38 ms | ~39 ms |
| SDL2/GLES2（016） | 标题 | 60.0 | ~15 ms | ~16 ms |
| 本版（020，纹理复用） | 正文 | 60.0 | 15.75 ms | 15.77 ms |

真机 #2（logo 20 fps / 转场卡）的根因是**每帧纹理重建**在 Tegra 上的额外开销；本版把它降为一次 `UpdateTexture`。真机帧率仍待用户复验（U4）。

## 7. 产物（自包含 NSP）

- 构建：`scripts/build_nsp_game.sh` + `hacBrewPack`（显式 `--hacbrewpack/--nstool/--work`）
- 版本：v1.0.2；title id `010047420000a000`；romfs `romfs:/game`
- 文件：`E:/galnx-build/p12/out/IROSEKA_FHD-010047420000a000.nsp`
- 大小 / SHA-256：**9,979,437,784 B** / `ff259aa49780b6c93e79762c6db5c670c6a979ffb6ddcd7c6ab4ce95e09c0d9b`
- 组件：romfs 9,932,275,140 B（161 条目）；`exefs/main` 4,614,659 B sha256 `92d0c3084ea0c542954df78d532ce4d197c0f001b9f1c256a111b18fe083ad82`；`main.npdm` 972 B `3cfb9877…`；`control.nacp` 16,384 B `7db30b9d…`；icon 22,454 B `10daef90…`
- `galnx package nsp verify`（`--manifest examples/pilot02-iroseka.yaml --nstool E:/galnx-build/m3-tools/nstool.exe`）：**ok=true，12 checks = 0 fail / 1 warn / 11 ok**；3 个 NCA（Program/Control/Meta）ProgID 全部 `0x010047420000A000`；唯一 warn 为未签名 NCA（homebrew 预期）。JSON 存 `E:/galnx-build/p12/verify.json`
- Citron（NSP 形态，`--no-stage` 直接加载 9.98 GB NSP，SD 的 `game` 目录临时改名以强制走 romfs）：**PASS** —— 启动日志 `rfvp: game root: romfs:/game`（证明走 romfs 而非 SD）、`GameConfig { hcb: Some(".iroseka.hcb"), nls: Some(GBK) }`、`the first frame was drawn` @5.55 s；标题（窗口 `IROSEKA FHD 1.0.2`）→ 中文正文「……羽毛。」→ 右摇杆驱动主机自绘光标 → `-` 弹 `QUIT GAME?` 面板 → `A` 确认后日志 `rfvp: exit confirmed by the player, closing` / `quit requested by host event` → Citron 回到游戏列表；`EXCEPTION` 0 次、`panic` 0 次。证据：`docs/milestones/evidence/P13-rfvp-nsp/`（`nsp-title.png` e7221cd7…、`nsp-story.png` 93f05e62…、`nsp-cursor.png` 7feb780d…、`nsp-quit-dialog.png` c186ae9d…、`nsp-after-exit.png` e84daad0…、`nsp-run-log-lines.txt`、`SHA256SUMS.txt`）
- DBI FTP 上传：**已实测 2026-10-31 22:50:16→23:16:06，9,979,437,784 B / 1,548.7 s ≈ 6.15 MiB/s（25.8 分钟）**，无中断；STOR 完成后 DBI 根目录回到投放占位条目（`/Place NSP, NSZ, XCI, XCZ or MSP files here`），说明 NSP 已被接收并自动安装。记录：`docs/milestones/evidence/P13-rfvp-nsp/device-upload.txt`（sha256 `fa73c184…`）。

## 8. 限制与未验证

- **U1**：真机上的光标可见性与跟手程度（Citron 已验证，真机待复验）。
- **U2**：真机性能（logo 动画 / 转场 / CG / 音频同步）是否达到可接受水平。
- **U3**：真机原生 EXIT 是否真的回到 HOME（Citron 已验证，真机退出链还与 Atmosphère/固件行为有关）。
- **U4**：真机 − 键确认框与 A 确认退出。
- **U5**：确认框文案为英文（5×7 点阵字体无 CJK 字形）；中文需要外挂位图字库，暂不做。
- **U6**：光标始终显示（一旦出现不再隐藏）；游戏内 `CursorHide` 未消费。
- **U7**：虚拟分辨率 1920×1080 时光标绘制按 `kx=1.5` 换算，若后续改虚拟分辨率需重新核对叠加层坐标。

## 9. 复现步骤

```bash
# 1) 基线
git worktree add --detach /e/galnx-build/rfvp-base 9f07ade
cd /e/galnx-build/rfvp-base
git apply .../rfvp-sdl2-backend.patch .../rfvp-input.patch .../rfvp-romfs.patch .../rfvp-input-remap.patch
git apply .../rfvp-device-fixes.patch

# 2) 构建（MSYS2）
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m5-switch-build3.sh'

# 3) Citron 验证（进标题后真鼠标点 New Game）
export CITRON_USER_DIR="C:/Users/ACETaffy/AppData/Roaming/citron"
export TEMP=/c/Users/ACETaffy/AppData/Local/Temp
bash scripts/citron_run.sh --nro .../rfvp.nro --detach --timeout 300 --settle 8 \
  --input-steps 'wait:9000;click:1386,560;wait:55000;key:K*8;key:N;key:C'
```
