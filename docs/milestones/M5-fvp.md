# M5 — FVP 引擎移植评估（rfvp）

> 本文件为 M5 里程碑汇总。状态：**已完成（研究级）**。M5-a 章节由 audit-engines 撰写，M5-b 汇总由 Lead 补写（2026-10-30）。

## M5-a：rfvp（xmoezzz/rfvp）Switch target 评估

- 任务：task-26；执行：audit-engines；日期：2026-10-30
- 上游：https://github.com/xmoezzz/rfvp
- 版本：HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`（2026-10-25T14:17:46Z，tag `pre-release` 同 commit；版本 tag `0.7.0` = `99435f22e94eaec27c0c1b9f22cc2a6b1910d7d1`）
- 许可证：MPL-2.0（仓库 `LICENSE`）；Switch host crate `platform/switch/host/Cargo.toml` 同样声明 `license = "MPL-2.0"`
- 结论：**继续研究（P3 研究项）**——构建可复现、Citron 可运行、PC host harness 可运行；但无合法真实 FVP 内容验证、软光栅性能远低于可玩、真机未验证、Windows 构建需本地补丁。
- 详细记录：`docs/builds/008-rfvp-evaluation.md`

### 关键证据

| 项目 | 结果 |
| --- | --- |
| Switch NRO 构建 | 成功；`DEVKITPRO=D:/devkitPro bash platform/switch/build_switch.sh` → `target/rfvp-switch/switch/rfvp.nro` |
| 产物 | `rfvp.nro` 1,372,216 B，sha256 `4964dda90a45c6aacff9268687438130c16742317d52de7d717087b6f3a930bb` |
| nstool | NRO0 / EntryPoint `0x14000020` / NACP `rfvp` `0.1.0` / .bss 0xd000（自定义 link-script 生效）/ RomFs 0 |
| Windows 构建 bug | `build.rs` 无扩展名探测 devkitA64 工具失败 → cc 回落宿主 mingw → COFF 对象链接失败；已本地补丁（`M5a-build/local-patch-build.rs.patch`）；另有 cc-rs 环境变量 workaround |
| PC host harness | Windows 原生跑通；`boots_and_runs_a_real_game` 与 `the_global_save_is_written_and_read_back` 通过；`saves_and_loads_a_slot` 因 Win95 Painter demo 非 VN 内容失败（内容不匹配） |
| Citron R1 | 启动成功，完整渲染 Luax Painter UI；日志 `parsed real HCB, initialized real GameData, and started VmRunner` / `the first frame was drawn`；无 `last_error.txt` |
| Citron R2 | 输入注入 `C,C,UP,UP,RIGHT,RIGHT,C` → 画面 diff 0（游戏语义，非链路不通） |
| Citron R3 | 注入 `M`（=Plus→Quit）→ diff 0.933325，日志 `quit requested by host event` → 键→手柄→hid→引擎链路成立 |
| 性能 | Citron 17.5 fps（软光栅 CPU）；host harness 14.81 ms/帧；第三方真机报告 issue #39 约 885 ms render/帧 |
| 真机 | 未验证；README 自述 `**Status: experimental.** It runs in Ryujinx at 60 fps with picture and sound; it has not been run on a console yet.` |

### 未验证项（详见 008 §9）

U1 真机、U2 真实 FVP 内容、U3 性能、U4 demo 素材版权、U5 存档路径（README `game/save/` vs `fs.rs` `saves/<game>/`）、U6 音频/视频、U7 CJK/字体、U8 输入坐标语义、U9 构建补丁维护、U10 内存、U11 MPL-2.0 合规。

### 证据路径

`docs/milestones/evidence/M5a-build/`、`M5a-run-boot/`、`M5a-run-input/`、`M5a-run-quit/`、`M5a-host-harness/`（均在 `docs/milestones/evidence/` 下）。

## M5-b：里程碑汇总（Lead 裁决，2026-10-30）

**结论：M5 完成（研究级）——rfvp 判为「继续研究（P3 研究项）」，不进入首批适配。**

### 计划 §10「M5 验收」五条逐条判定

| # | 验收项 | 判定 | 依据 |
| --- | --- | --- | --- |
| 1 | 确认当前 Switch target 的构建命令、依赖与输出产物 | ✅ | `platform/switch/build_switch.sh`；devkitA64 r30-1 / gcc 16.1.0 / binutils 2.46.0 / newlib 4.6.0.20260123-4 / libnx 4.12.0-1 / switch-tools 1.13.1-1；rustup pin `nightly-2026-02-01`（rustc 1.95.0-nightly）+ rust-src；产物 `rfvp.nro` 1,372,216 B sha256 `4964dda9…f3a930bb`；nstool：NRO0 / EntryPoint `0x14000020` / .bss `0xd000` / NACP `rfvp` `0.1.0` / RomFs 0；Windows 下 `build.rs` 需本地补丁（008 §3.4） |
| 2 | 在 PC host 测试中验证脚本和资源读取 | ✅（slot 存档 ◐） | Windows 原生 `no_std_harness`：`boots_and_runs_a_real_game` 通过（打开 `painter.hcb` + `default.ttf`、300 帧 1280x720、avg 14.81 ms/帧，其中 13.95 ms 软光栅、peak heap 13,094 KiB）；`the_global_save_is_written_and_read_back` 通过（262,184 B）；`saves_and_loads_a_slot` 失败 = Win95 Painter demo 非 VN 内容（断言 `the story did not move on`），属内容不匹配而非引擎缺陷，slot 存档语义未证 |
| 3 | 查明 Switch 端渲染、音频、文件 I/O、输入和存档后端完成度 | ◐ | 渲染 ✅（Citron 完整渲染 Luax Painter，无 `last_error.txt`，debug_report virtual 1024x640 / 17.5 fps）；输入 ✅（注入 M=Plus → 日志 `quit requested by host event`，键→手柄→hid→引擎链路成立；R2 点击无像素变化归因坐标/游戏语义）；文件 I/O ✅（HCB/字体打开、全局存档读写；Citron 侧实际落盘路径未实测）；存档 ◐（host 全局存档 OK；slot 未过；README `game/save/` 与 `fs.rs` `saves/<game>/` 不一致 = U5）；音频/视频 ⬜（未采集 = U6）；CJK/字体 ⬜（U7） |
| 4 | 不将仓库标注的 experimental 状态误写成已在真机可用 | ✅ | 008 §8 引上游 README 原文「Status: experimental. It runs in Ryujinx at 60 fps with picture and sound; it has not been run on a console yet.」；结论明确真机未验证，不据此宣称真机可用 |
| 5 | 根据验证结果决定是正式适配、继续研究还是搁置 | ✅ | **继续研究（P3 研究项）**：构建/Citron/host 三项证据齐，但无合法真实 FVP 内容、软光栅性能不可玩（Citron 17.5 fps；上游 issue #39 旧 commit 真机报告 ≈885 ms/帧）、真机未验证、Windows 需补丁 → 不作为 GalNX 首款原型 |

### 与「正式适配」的差距（008 §10 前置条件 5 条）

1. 至少一个可合法分发/免费的真实 FVP 内容用于端到端验证（渲染、音频、存档、影片、CJK）；
2. 性能达到可玩阈值（真机或 Citron ≥30 fps 稳定），或上游合并 GPU renderer；
3. 上游真机验证（issue #39 类报告在当前 HEAD 复现通过）；
4. 存档路径 / NLS / `config.toml` 行为与 README 对齐（或 GalNX 启动器统一约定）；
5. MPL-2.0 合规声明 + `build.rs` 补丁的升级维护策略。

### 里程碑判定

- 计划 §10 M5 五条验收：1/2/4/5 ✅，3 ◐（渲染/输入/IO 有实测证据；音频/视频/CJK/真机路径未验）。判定 **M5 完成（研究级）**——该里程碑要的是「决定性结论」，不等同正式适配。
- 计划 §7.2 接入排序不变：rfvp / siglus_rs 仍排研究项，不影响首批适配顺序（krkrsdl2 / ONScripter-NX 等）。
- 遗留未验证项 U1–U11：真机、真实 FVP 内容、性能、demo 素材版权、存档路径、音频/视频、CJK、输入坐标、Windows 补丁维护、大包内存、MPL-2.0 合规。

### 证据入口

- `docs/builds/008-rfvp-evaluation.md`（25,162 B / 288 行）
- `docs/milestones/evidence/M5a-build/`（build.sh、build.log 52,914 B、local-patch-build.rs.patch、nstool.txt、sha256.txt）
- `docs/milestones/evidence/M5a-run-boot|input|quit/`（每 run：result.json + run.log + 1 张关键截图）
- `docs/milestones/evidence/M5a-host-harness/`（host-harness.sh、host-harness.log 50,222 B、frame_00000.png 1280x720）

### 本机新增工具

- rustup 1.29.2（scoop 安装；`CARGO_HOME=D:/Scoop/persist/rustup/.cargo`、`RUSTUP_HOME=D:/Scoop/persist/rustup/.rustup`），用于 rfvp pin 的 `nightly-2026-02-01` + rust-src 组件；记录见 `docs/environment/rust-toolchain-2026-10-30.md`。除 rustup/rust 外未安装其他系统级组件。

## M5-c：SDL2/GLES2 性能改造（P9，2026-10-31）

**结论：rfvp 的 Switch 端「不可玩」主因是 CPU 软光栅，不是引擎逻辑。** 把渲染后端从 libnx framebuffer + `SoftRaster` 换成 SDL2/GLES2 后，同一台 Citron（nightly `0237a9b88`）上从 17–19 fps 提升到 **60.0 fps 满帧**，画面与中文正文渲染正确；`docs/builds/016-rfvp-sdl2-backend.md` 记录完整方案，补丁 `docs/builds/patches/rfvp-switch/rfvp-sdl2-backend.patch`（1,238 行 / 6 文件 / SHA-256 `515af726…b77c7`）已在纯净 worktree `git apply --check` 通过。

### 性能前后对比（Citron，1280x720 窗口，虚拟帧 1920x1080）

| 指标 | 软光栅（旧） | SDL2/GLES2（新） | 说明 |
| --- | --- | --- | --- |
| 帧率 | 17–19 fps | **60.0 fps** | 受 vsync 上限；debug_report 首行 `frame N: 60.0 fps over the last 60 frames` |
| render/帧 | ≈38.8 ms | 15.57 ms（含 vsync 等待） | 同报告末行 `perf avg over 60 ticks` |
| vm / scene | — | 0.56 / 0.23 ms | 引擎逻辑不再是瓶颈 |
| NRO 体积 | 1,372,216 B | 7,823,416 B | 新增 SDL2/EGL/GLES2 静态链接 |
| 产物 sha256 | `4964dda9…f3a930bb` | `e3acbce42ae2e55acae386ece29ba1f794b029dc6e9b2e48302993b87b0d9399` | 干净构建（诊断插桩已全部移除） |

### 改造要点（4 层）

1. **SDL2 主循环**（`platform/switch/runtime/main.c`）：删除 `framebufferCreate/Begin/End/Close`，改由 SDL2 独占显示；`appletMainLoop` 由 `SDL_PumpEvents` 内部 tick，主循环改为 `galnx_sdl_pump_events()` → 读 pad/触摸 → `rfvp_switch_frame(app,&input,NULL,0)` → `audio_pump`；截图走 `galnx_sdl_write_screen_bmp`（`SDL_RenderReadPixels`）。libnx 的 input/audio 后端全部保留。
2. **C shim**（新增 `platform/switch/runtime/sdl_video.c`，17,054 B）：对外导出 init/shutdown/texture_create/update/destroy/begin/draw_quad/draw_solid/present/pump_events/read_pixels_scaled/write_screen_bmp；虚拟坐标 → 1280x720 letterbox 变换、scissor 与内容区求交后 `SDL_RenderSetClipRect`、`SDL_RenderGeometry`（4 顶点 + 6 索引 `{0,1,2,2,1,3}`）、纹理 `ABGR8888 + STREAMING`、BlendMode（Opaque/Alpha/Add/Multiply/Screen）映射到 SDL blend / `SDL_ComposeCustomBlendMode` 都在 C 里做。
3. **Rust 后端**（重写 `platform/switch/host/src/render.rs`，13,117 B）：`HorizonRenderer` 不再持有 `SoftRaster`，全部 `RfvpRenderer` 方法转发 C shim；`capture_thumbnail` 用 `galnx_sdl_read_pixels_scaled` 读回已 present 的上一帧后盒式缩放（保持引擎原有语义）；`screen_bmp()` 同样走读回。
4. **构建**（`platform/switch/build_switch.sh`）：用 `-I$DEVKITPRO/portlibs/switch/include/SDL2` 与 `libSDL2.a` 编译；链接顺序必须 `main.o sdl_video.o librfvp_horizon.a -lSDL2 -lEGL -lglapi -ldrm_nouveau … -lnx -lm`——`-lnx` 若放在 `-ldrm_nouveau` 之前会 `undefined reference to nvGpuChannelKickoff/nvGpuChannelAppendEntry`。

### 「文字不可见」的两个真因（已修）

1. **后端 create_texture 必须是 upsert，不是一次性 create。** 引擎 `crates/rfvp/src/rendering/prim_commands.rs:224 upload_graph_if_needed` 在 graph generation 变化时用同一个 `graph_id`（文字层恒为 `4064 + slot`，见 :829-857）反复 `create_texture`，`host_texture_id(graph_id) = TextureHandle(graph_id as u32)`（:287-289）；软光栅后端是 insert 覆盖语义，而新 C shim 最初 `if (find_texture(id) != NULL) return -3;` → 日志出现 144 条 `rfvp: texture create failed: id=4064 1024x540 rc=-3`，文字纹理永远停在首帧空内容。改为 upsert（已存在则 `SDL_DestroyTexture` 后复用槽位）后日志归零、文字出现。
2. **截图早于文字出现**（诊断陷阱）：本作 New Game 后有长白场 + typewriter，diag5 日志显示文字纹理首次 create 在启动后 **t≈63.5 s**，而早期所有 run 最晚截图只到 ~58 s → 画面里确实没有字，但渲染链路是好的。验收截图必须 ≥ 启动后 90–100 s。

### 证据入口

- `docs/builds/016-rfvp-sdl2-backend.md`（方案/基准/实测/复现/未验证项）
- `docs/builds/patches/rfvp-switch/README.md` + `rfvp-sdl2-backend.patch`
- `docs/milestones/evidence/P9a-rfvp-sdl2/`：`title-t0.png` SHA-256 `3dde7224…d7ee`、`story-t5.png` SHA-256 `65e2c440…2e34`、`story-t5-zoom.png` SHA-256 `038b652f…fc7a`、`perf.txt`（fps / perf avg / virtual frame 三行）、`SHA256SUMS.txt`
- 引擎描述符：`examples/engines/rfvp.yaml`（`build_backend: custom-script`，artifact sha256 = 干净 NRO）

### 仍未验证 / 仍未做

- U1 真机；U2 音频输出；U3 中文 NLS（游戏内文本编码/nls 开关）；U4 手柄完整语义映射；U5 大包内存峰值；U6 MPL-2.0 合规声明与补丁升级维护；U7 movie 播放（`.mpg`）。
- 本里程碑只证明「渲染与帧率」，不等于 rfvp 已达正式适配：真实内容可玩性（存档/选项/回放）、音频与真机仍是门槛。

## M5-d：手柄输入与快捷存读档（P10，2026-10-31）

### 基线（上游自有映射，未改动前即可用）

上游 `platform/switch/host/src/event.rs`（commit c4240ad "Run the Switch port on libnx"）已实现一套映射，P10-a/b/c 实测确认四条：

| 输入 | 引擎事件 | 实测结果 |
| --- | --- | --- |
| 十字键 / 左摇杆 | `PointerMove`（步长 12 px，摇杆/18000） | 10×RIGHT 把虚拟光标从 (640,360) 移到 New Game 上，出现白色悬停高亮（截图与 P10-a step-23 逐字节相同） |
| A | `PointerDown{Left}` @光标 | 点击 New Game 进入游戏（白场淡入） |
| B | `PointerDown{Right}` | 正文界面 = 隐藏/恢复消息窗（toggle，两次 B 后画面复原） |
| X / Y | `Return` / `Space` | 均能推进正文（截图为不同台词） |
| L / R / ZL / ZR | `Control`（按住） | Ctrl 连按可跳过剧情（左右肩都成立） |
| PLUS | `RfvpEvent::Quit` | 立即退出到 Citron 主界面（全黑） |

标题画面 Enter/Space 无反应属游戏行为（不是映射问题）；Minus（`Escape`）在正文里打开游戏内 system 菜单。

### 两个结构性缺口（P10 的直接动因）

1. **游戏内 system 菜单只认指针**：Minus 打开的 SAVE/LOAD/HIDE/UNDO/OPTION/TITLE/EXIT/RETURN 菜单对 Enter、方向键、Space、肩键全部无反应（P10-g：Enter/DOWN×3/Enter 后画面 sha 逐字节相同，`415223425549fedb`），只能靠光标悬停选中后点击；而光标每帧 12 px、菜单在右边缘（虚拟 x≈1255），可靠点击代价高。
2. **SAVE/LOAD 会挂起 VM**：`legacy::load_file/save_file` 置 `set_pending_save_load_request(...)` 并 `should_break()`，由桌面端 `legacy_save_load_ui` 消费后 `set_halt(false)` 恢复；Switch 端没有任何消费者 → 点中 SAVE/LOAD 会永久挂起。
3. 上游没有产生 `Wheel` 事件，backlog（历史记录）无输入源。

### patch J（`rfvp-input.patch`）做了什么

| 改动 | 位置 | 语义 |
| --- | --- | --- |
| 新增 `RfvpEvent::QuickSave` / `QuickLoad` | `crates/rfvp/src/host_api/event.rs` | 供 host 层发快捷存读档 |
| 事件处理 + pending 兜底 | `crates/rfvp/src/no_std_core.rs` | QuickSave→`legacy::save_quick(slot 0)`、QuickLoad→`load_quick(slot 0)`；VM tick 后取 `take_pending_save_load_request()`，SaveFile/SaveTitle→写槽 0，LoadFile/LoadTitle→读槽 0，避免挂死 |
| 右摇杆字段 | `platform/switch/runtime/main.c` | `padGetStickPos(&pad, 1)` → `right_stick_x/y` |
| PLUS 变修饰键 + 右摇杆滚轮 + 光标加速 | `platform/switch/host/src/event.rs` | PLUS+ZR=快速存档、PLUS+ZL=快速读档（PLUS 松开才 Quit）；右摇杆竖向 `Wheel{±120}`（上=打开历史记录）；光标除数 18000→6000 |

最终手柄语义：**A 左键 / B 右键（隐藏消息窗）/ X 回车 / Y 空格 / 方向键+左摇杆 光标 / 右摇杆上下 滚轮（历史记录）/ L R ZL ZR 按住 Ctrl 跳过 / Minus 游戏菜单 / PLUS+ZR 快速存档 / PLUS+ZL 快速读档 / 单击 PLUS 退出**。

### 验证（Citron，P10-h；证据 `evidence/P10-rfvp-input/`）

- `rfvp [info] quick save: wrote slot 0`（t=169.95 s）与 `quick load: read slot 0`（t=179.00 s）出现在 guest ODS 日志中；存档目录新增 `saves/iroseka-2ae7dc8e/save/rfvp_s000.bin` 490,104 B（SHA-256 `7cac48ab…`）。
- `09-backlog-wheel-up.png` SHA-256 `eec9f46f…`：右摇杆上推后出现 BACKLOG 界面（左侧竖排 BACKLOG 标题、滚动条、正文），滚轮链路成立。
- `10-quicksave.png` `d1f5c064…`、`11-quickload.png` `91d1add9…`：存档/读档后画面变化；`12-quit-plus.png` 全黑（PLUS 正常退出）。
- 组合键（PLUS+ZR/ZL）在 Citron 上无法用 harness 直接测（`scripts/citron_run.sh` 按键注入是逐键 PostMessage，不能同时按住两键）；P10-h 用「临时的 L/R 单键映射」验证了事件→存档链路本身，随后删除临时映射并重建。**组合键、真机、菜单点击仍是未验证项（U1–U7）**。

### 最终 NRO 复验（P10-i，无诊断代码）

- run dir `E:/galnx-build/m5-rfvp-run/p10-i/20261031-051324-rfvp`（status=loaded rc=0，finished 2026-10-30T21:17:19Z，citron_log 148,931 B，panic=0 / EXCEPTION=0）。
- 序列：标题 → 光标悬停 New Game（`13-i-final-title-hover.png` `378603c3…`）→ A 进入 → 等 65 s → Enter 推进（`14-i-final-story-enter.png` `85d636e8…`，台词变化）→ 右摇杆上推打开 BACKLOG（`15-i-final-backlog.png` `112c80cf…`）→ 右摇杆下推 / Enter（截图与打开帧逐字节相同，面板不关闭）→ PLUS 干净退出（`16-i-final-quit.png` `e84daad0…`）。
- 结论：交付用 NRO（无任何临时诊断映射）上，光标悬停、A 点击、Enter 推进、右摇杆 Wheel→BACKLOG、PLUS 退出均成立；BACKLOG 需 B（右键）或 Minus 关闭。

### 本机不是「已可玩」的部分

- 存档只能落在引擎快速槽 0（`rfvp_s000.bin`），游戏自带的 SAVE 面板（多槽位、缩略图、注释）仍然不可用；它在 Switch 上属于「桌面专属 UI」，要补齐需要移植一套槽位选择 UI。
- 音乐/语音音频输出仍未在真机验证；movie（`.mpg`）播放未验证。

### M5-e（P11）：自包含 NSP（romfs）

- 目标：把 ~9.2 GiB 游戏数据打进单个 NSP，真机可安装、插卡即玩（P9/P10 仍要求 SD 目录）。
- 实现：`platform/switch/runtime/main.c` 运行期选择游戏根（romfs 挂载且 `romfs:/game` 有 `.hcb` 且 SD 侧无游戏 → `romfs:/game`，否则回落 SD）；`scripts/build_nsp_game.sh` 通用打包脚本（elf2nso → npdmtool → nacptool → romfs 硬链接 → hacBrewPack → nstool）。
- 产物：NSP **9,979,435,224 B**，SHA-256 `4592385c1c3e6b166172315a1c79c574b9241f6f8c57244b2e050e0292549189`；romfs 9,932,275,140 B / 161 顶层条目；Title ID `010047420000A000`。
- 验证（Citron，P11-nsp2）：把 SD 游戏目录改名 `game.sd-bak` 后，NSP 仍从 `romfs:/game` 启动（t=8.41 `(romfs mounted)`）、加载 GBK 中文脚本、显示中文正文「从天而降的羽毛。」、PLUS 干净退出（0 exceptions）；NRO 形态回归 PASS。
- 独立校验：`galnx package nsp verify` ok=true，12 checks（11 ok / 1 warn = 未签名预期），3 NCAs 的 ProgID 均 `010047420000A000`。
- 限制：真机未验证（9.98 GB 必须 exFAT SD 或 NAND；DBI FTP 约 25–30 分钟）；音频 / movie / 内存余量未测（018 §9 U1–U8）。
- 补丁/记录：`patches/rfvp-switch/rfvp-romfs.patch` 2,430 B `710a373e…`；`docs/builds/018-rfvp-nsp.md`；证据 `evidence/P11-rfvp-nsp/`。

### M5-f（P12）：手柄映射重写（Citron 级逐项验证）

- 目标：把用户 m18283 在真机上提出的最终映射表落到 Switch 输入层——A=Enter、B=Esc、X=自动、Y=读档、ZR/ZL=左右键（按压）、R=Ctrl、方向键=方向键、左摇杆上下=滚轮、右摇杆=光标、+=存档、-=退出（带游戏确认框）。
- 实现：整体重写 `platform/switch/host/src/event.rs`（404 行，+264 −56）。上游把 ZR/ZL/R 全绑成 Ctrl、PLUS 直接 `Quit`，且 no_std 端没有 `exit_confirm_ui`/`legacy_save_load_ui`，因此改绑硬件键后，用「Esc 打开游戏暂停菜单 → 指针移到实测锚点 → 左键」的 `MenuMacro` 阶段机复用游戏原生 UI；锚点 SAVE=(1117,171)、LOAD=(960,217)、EXIT=(654,608)、AUTO=(1079,700)、确认=(560,379)，来自 Citron 悬停扫描；菜单淡入等待 90 poll（早期 15 poll 时点击被吞）。
- 验证（Citron，p12-c/d/f/g/h/i/n/o/p）：A 完成打字并推进场景、B 打开暂停菜单、ZL 右键关闭菜单（Esc 关不掉，游戏只认指针）、ZR 左键推进正文、方向键与左摇杆滚轮、右摇杆移动游戏自绘光标、X=AUTO（出现进度条+「自动播放」）、Y=FILE LOAD、PLUS=FILE SAVE、MINUS=EXIT→中文确认框→全黑退出（0 异常）。逐项证据见 `docs/builds/019-rfvp-input-mapping.md` 与 `evidence/P12-rfvp-input/`。
- 产物：NRO 7,839,800 B `093ad9e0…`、ELF 17,046,880 B `0bfc77e1…`、自包含 NSP v1.0.1 **9,979,435,736 B** SHA-256 `0fda623c…`（romfs 9,932,275,140 B / 161 entries；`galnx package nsp verify` ok=true，12 checks = 0 fail / 1 unsigned warn）；NSP 形态 Citron 冒烟确认从 `romfs:/game` 启动并渲染中文标题。
- 补丁/记录：`patches/rfvp-switch/rfvp-input-remap.patch`（413 行，`44fd0722…`）+ 全量 `rfvp-full.diff` 68,536 B（`026a7cee…`）；`docs/builds/019-rfvp-input-mapping.md`；计划 v1.13。
- 遗留：**R=Ctrl 的跳读效果 Citron 未复现**（引擎输入状态已置位，游戏侧 `TextSkip` 调用条件未知，U1）；Esc 不能关闭菜单（U2，用 ZL 代替）；锚点为该作布局专属（U3）；真机手感（右摇杆速度、ZR 拖拽、MINUS 退出链路）待复验（U4）。

### M5-g（P13）：真机四项缺陷修复（光标 / 性能 / 原生退出 / 确认框）

- 目标：修用户在真机 m19465/m19535 报的四项缺陷——① 看不到鼠标光标；② 进正文后卡顿；③ 用游戏暂停菜单 EXIT 退出后黑屏、进程不退出；④ 按 MINUS 直接退出、无确认框。
- 根因 1（光标）：Switch no_std 路径没有 winit，`exit_confirm_ui` / `legacy_save_load_ui` 都不可用，指针位置只存在于 `event.rs` 的 `cursor_x/cursor_y`；游戏只在收到 `PointerMove` 后画光标，静止时看不到指针。
- 根因 2（性能）：早期实现每帧 `create_texture` + `ReadPixels` 读回，纹理反复重建 + GPU 同步造成抖动；改为按 id upsert + 单张 scratch 纹理复用后 Citron 稳定 60 fps（`render` 15.75 ms/帧）。
- 根因 3（原生退出黑屏）：游戏暂停菜单 EXIT 触发引擎 `ExitDialog` 请求，但 `RfvpEvent` 没有对应事件、no_std 端无人消费 → 主循环继续跑却没有场景可画。
- 根因 4（MINUS 无确认）：`event.rs` 里 MINUS 直接置 `pending_quit` 并在松开时发 `RfvpEvent::Quit`，绕过确认流程。
- 修复（7 文件，补丁 `patches/rfvp-switch/rfvp-device-fixes.patch` 109,915 B / 7 文件 `9b65b8b2…`，基线 worktree `9f07ade` + 顺序 apply 016/017/018/019）：
  - `platform/switch/runtime/sdl_video.c`：主机层 overlay —— 菱形光标 + `QUIT GAME?` 面板 + 5×7 点阵字体（英文），新增 `galnx_sdl_set_overlay()`，纹理 scratch 复用；
  - `platform/switch/host/src/event.rs`：`DIRECTIONS`/`ACTIONS` 重构，ZR/ZL = 左右键按压、R = Ctrl、MINUS 只打开主机确认框，新增 `pointer()` / `quit_dialog_open()` / `take_quit_confirmed()` / `debug_line()`；
  - `platform/switch/host/src/app.rs`（CRLF 文件）：`request_quit` / `pointer_state` / `quit_dialog_open` / `take_quit_confirmed` / `input_debug_line`；
  - `platform/switch/host/src/ffi.rs`：每帧 `take_quit_confirmed()` → `request_quit()`，导出 `rfvp_switch_pointer`、`rfvp_switch_input_debug`；
  - `platform/switch/runtime/main.c`：每帧 `galnx_sdl_set_overlay()` 喂光标与确认框状态；
  - `crates/rfvp/src/no_std_core.rs`：消费 `ExitDialog` pending 请求与 `ExitMode(3)` → 日志 `quit requested by the game (ExitDialog confirmed)` / `(ExitMode(3) main script exited)`，置 `quit_requested` + `save_global_if_changed()`；
  - `crates/rfvp/src/host_api/event.rs`：退出对话状态字段。
- 验证（Citron）：NRO 形态（p12-o / p12-q / p12-s）与 NSP 形态（p13-nsp）全 PASS —— 中文正文「……羽毛。」、主机黑菱形光标随右摇杆移动（n2）、`QUIT GAME? / A = YES  B = NO` 面板（n3）、A 确认后窗口关闭回 Citron 列表（n5）、日志 `exit confirmed by the player, closing` → `quit requested by host event`、EXCEPTION/panic 0、60 fps。
- 产物：NRO 7,839,800 B sha256 `4f096dd6…c2370f`、ELF sha256 `f34992a3…6feeb3`；自包含 NSP v1.0.2 **9,979,437,784 B** sha256 `ff259aa4…09c0d9b`（exefs/main 4,614,659 B `92d0c308…`、romfs 9,932,275,140 B / 161 条目）；`galnx package nsp verify` ok=true，12 checks（11 ok / 1 warn = NCA 未签名预期）；DBI FTP 上传 9.98 GB **实测 1,548.7 s ≈ 6.15 MiB/s（25.8 分钟）**。
- 补丁/记录：`docs/builds/020-rfvp-device-fixes.md`、证据 `evidence/P13-rfvp-nsp/`、runbook `docs/pilot/P11-rfvp-nsp-device-runbook.md`（V1–V14 / U12–U17）、全量 `rfvp-full.diff` 85,712 B（`f195683e…`，10 文件）。
- 遗留（U 项）：U12 真机光标可见性与速度、U13 真机确认框 A/B 按键、U14 原生 EXIT 真机退出与全局存档落盘、U15 真机性能（低帧 / 输入延迟是否消除）、U16 NSP 冷启动 romfs 读取、U17 4 GB 机型内存余量。

### M5-h（P14）：真机掉帧修复——GPU prev-frame + 关闭诊断回读

- 目标：用户 m20518/m20552 报真机 8 类掉帧/音频停滞（转场卡、每几秒卡一下、音频断续等），要求修复后再复验。P13 的纹理复用只解决了「每帧重建纹理」，没有解决主瓶颈。
- 定位：先用 Citron 同款探针（perf3）抓 `rfvp: frame N slow` 全量行并新增宿主计时（begin/upload/present/thumb/draws/flushes）。结论 = 四类根因：
  - R1（主因）引擎的「上一帧」纹理（`DrawTextureKey::PrevFrame`）走 CPU 回读：`no_std_core.rs` 每帧 `capture_thumbnail(1920,1080)` 读回 8.29 MB 再上传，转场/淡入帧 `thumb 45–66 ms` 直接撑爆帧预算；
  - R2 每 300 帧写一次 `debug_screen.bmp`（`ffi.rs`）同样走全屏回读，制造每 5 秒一次的 36–41 ms 周期卡顿；
  - R3 启动/首次加载（`vfs_read 675 ms`、`graph_decode 521 ms`）与存档（`save_finalize`/缩略图）尖峰；
  - R4 Citron 环境 `audio_cmds 150 ms`（真机待确认）。
- 修复（6 文件，补丁 `patches/rfvp-switch/rfvp-perf-gpu-prev-frame.patch` 32,781 B `e64dfb71…`）：
  - `platform/switch/runtime/sdl_video.c`：两张 1280×720 `SDL_TEXTUREACCESS_TARGET` 离屏 target，每帧先画进当前 target、present 时拷贝到窗口并轮换，`PREV_FRAME_TEXTURE` id 直接解析为上一帧 target（GPU 采样，零回读）；同状态连续 quad 合批到一次 `SDL_RenderGeometry`；导出宿主计时 `galnx_sdl_take_stats()`；
  - `platform/switch/host/src/ffi.rs`：透传宿主计时并输出 `host avg over 60 frames` 行；`DEBUG_SCREEN_ENABLED=false` 编译掉周期 BMP；
  - `platform/switch/host/src/render.rs` + `crates/rfvp/src/host_api/render.rs`：新增 `supports_gpu_prev_frame()`（Switch host 返回 true）；
  - `crates/rfvp/src/rendering/prim_commands.rs`：新增 `set_prev_frame_gpu()`（只记尺寸、清 wants_prev_frame，不碰 backend）；
  - `crates/rfvp/src/no_std_core.rs`：支持 GPU 时走新路径，否则保持旧 CPU 回读。
- 验证（Citron，同一探针脚本 perf3 vs perf4）：slow 行 **154→19**、帧>7 慢帧 **151→15**、≥50 ms **136→5**、`thumb≥20 ms` 帧 **142→0**、slow 总时长 **12,133.7→3,567.8 ms**（帧>7 部分 9,221.4→639.9 ms）；转场帧 81–85 与每 300 帧周期卡顿全部消失；视觉 3 张截图与 P13 正确画面一致（标题/淡入/正文+光标）；稳态仍 60 fps（render≈present=VSync 等待 15.3–15.7 ms）。
- 产物：NRO 7,843,896 B `e5373bd7…`、ELF 17,069,080 B `e4040e7b…`；自包含 NSP v1.0.3 **9,979,441,368 B** sha256 `b9e0d6a5…b85aa3e`；`galnx package nsp verify` ok=true（12 checks = 11 ok / 0 fail / 1 warn 未签名）；Citron NSP 形态冒烟 PASS（`romfs:/game (romfs mounted)`、first frame 6.70 s、EXCEPTION/panic 0）。
- 补丁/记录：`docs/builds/021-rfvp-perf-gpu-prev-frame.md`、`patches/rfvp-switch/rfvp-full.diff` 107,938 B `2050a79c…`（12 文件）、证据 `evidence/P14-rfvp-perf/`、runbook V14/V15 + U18–U21、计划 v1.15。
- 遗留：U18 真机转场/周期卡顿复验、U19 冷启动停顿未优化、U20 存档尖峰未优化、U21 真机 SDL target 支持确认。
### M5-i（P16）：逐句存档卡顿修复——惰性状态编码

- 目标：修用户 m21366 报告的真机缺陷——「稍推进后的略复杂场景会瞬时卡顿并带音频一起卡，几乎每句话卡一下」。
- 定位（真机 P15 取证 + 本机 Citron 复现）：真机 114 个 save 慢帧恰为 55 对、对内相差 2 帧、对间隔 44–184 帧（≈每句一次）；每对 = 大档 `save_finalize` 40.5–80.0 ms + 小档 7.8–9.5 ms，缩略图 24.8–25.5 ms；复杂场景存档 10.94 MB vs 标题 0.49 MB。把真机复杂存档复制进 Citron 后复现：每句触发 2 次 `SaveCreate(3) value=Nil`，每次 `finalize_local_savedata_prepare` 把 10.27 MB `SaveStateSnapshotV1`（motion 10,250,941 B，占 99.8%）做 `postcard` 编码，`encode_ms=99.17–108.00`；两次都不带 slot，编码结果被下一次 prepare 丢弃，纯浪费。附加发现：`save_state.rs` 的诊断日志为打印各分量字节数额外做了 4 次 `encode`，接近翻倍实测编码量。
- 修复（6 文件，补丁 `patches/rfvp-switch/rfvp-save-lazy.patch` 357 行 +162/−19 `941f9504…`）：
  - `crates/rfvp/src/subsystem/resources/save_manager.rs`（CRLF）：新增 `PendingPrepare{thumb_w,thumb_h,thumb_rgba,state}` 字段与 `pending_prepare`；`finalize_local_savedata_prepare(thumb_w,thumb_h,thumb_rgba,state)` 只存快照不编码；新增 `materialize_pending_local_savedata(nls)` 在 `try_commit_local_savedata` 真正需要文件时才 `build_save_file_bytes`+`append_state_chunk_v1`；`wants_vm_snapshot_capture`/`pending_save_capture`/`has_local_saved` 纳入 pending；`request_prepare_local_savedata` 清 pending；
  - `crates/rfvp/src/subsystem/save_state.rs`：删除 4 次诊断编码，只 encode 一次 + `[save] state total=..B`；
  - `crates/rfvp/src/no_std_core.rs` / `crates/rfvp/src/app.rs`：调用点去掉 nls 参数，prepared 日志加 `pending=`；
  - `crates/rfvp/src/ring_log.rs`：容量 400→1200，保留完整 `[save]` 轨迹；
  - `platform/switch/runtime/sdl_video.c`：缩略图改 GPU 下采样——新建/复用目标尺寸 `SDL_TEXTUREACCESS_TARGET` 纹理，`SDL_RenderCopy` 从上一帧 target 缩放后只读回 w×h，失败回落旧全帧路径。
- 验证（Citron，复杂存档 + 12 次推进）：
  - 逐句 24 次 `SaveCreate(3) value=Nil` **全部无编码**（`prepared bytes=None pending=true`），每帧 save 阶段 **112–135 ms → 5.27–5.67 ms**，缩略图 10–12 ms → **1.03–2.16 ms**；
  - 真实落盘路径仍完整：系统档 901/906 `materialize encode_ms=17.61 / 6.84` → `commit slot=901 len=489531 write_ms=6.47 ok=true`、`slot=906 write_ms=2.25 ok=true`；
  - 12 句推进截图逐句变化、0 exceptions；NRO 形态（未合 NSP）验证。
- 产物：NRO 7,852,088 B `3aff4de3…`、ELF 17,077,488 B `9adc739f…`；自包含 NSP v1.0.4 见 §产物；全量 `rfvp-full.diff` 3,131 行 / 17 文件 `626e7aa9…`，已在纯净 HEAD worktree `git apply --check` 通过。
- 补丁/记录：`docs/builds/022-rfvp-save-latency.md`、证据 `evidence/P16-rfvp-save-latency/`、计划 v1.16。
- 遗留：U22 真机复验逐句卡顿是否消失；U23 每句仍抓 10 MB 快照（~5 ms ×2）；U24 若后续出现每句 `SaveWrite` 大档需再节流；U25 启动 vfs/graph_decode 与 Citron audio_cmds 尖峰不属本补丁。

### M5-j（P17）：资源缓存、启动预读与 zlib inflate

- 目标：修用户 m22537 报告的「CG 表情切换 / 背景切换 / 每次打开 UI 界面都卡」；方向由用户指定为「预读 + 缓存」。
- 定位：`graph_load`/`parts_load`/`vfs_load_file` 每次都完整「读盘 → zlib inflate → 逐像素转 RGBA → 上传」，无任何缓存；ESC 菜单一次打开要现解数十张 `sys_*` 小图 + `sys_window_left/right/title`（154–354 KB），慢帧 350–1417 ms；inflate 占解码成本绝对主导（66 张 `graph/*` 共 204,407 us vs 像素转换 24,589 us），两个 `slf_*_bg` 单文件 inflate 各约 57 ms。
- 修复（28 文件，补丁 `patches/rfvp-switch/rfvp-cache.patch` 33,076 B / 849 行 `8b97c147…`）：
  - 新增 `crates/rfvp/src/subsystem/resources/resource_cache.rs`：进程级 LRU 三缓存（textures 160 MiB / parts 48 MiB / bytes 192 MiB，单条 ≤16 MiB）+ `spin::Mutex` 惰性初始化；
  - 5 处接线：`graph_buff.rs::load_texture`/`graph.rs::graph_load`、`parts_manager.rs::load_texture`/`parts.rs::parts_load`、`vfs.rs::read_file`；
  - 启动预读：`no_std_core.rs::try_boot` 枚举 `graph/` 的 `sys_/menu_/config_/slf_/btn_/cursor/diss/prompt/mouse` 前缀，单条 ≤4 MiB、总预算 96 MiB（实测 66 张）；
  - 解码提速：`texture.rs` 三处像素转换改 `chunks_exact` 块拷贝 + `ImageBuffer::from_raw`（单帧 buffer 直接 move 进 slices）、新增 feature `switch-zlib` 用 devkitPro zlib `uncompress()` 替代 miniz、`build_switch.sh` 链接 `-lz`；
  - 观测：单文件解码 >4 ms 打 `graph decoded ... us=`、inflate/convert 分项 `graph decode split`；ring 容量 1200→4000。
- 验证（Citron，同一份真机复杂存档）：重复打开 ESC 菜单两次截图**逐字节相同**（sha `3174b312…`）且无解码/存档慢帧；`graph cache hit` 193、`vfs cache hit` 106、`texture put` 154、运行期 `graph decoded` 仅 10 次；zlib vs miniz 同一批 66 张：inflate 204,407→**133,686 us（1.53×）**，convert 24,589→24,942 us（已非瓶颈）；texture 缓存峰值 123,259,040/167,772,160 B。剩余大尖峰 frame 2490 838.5 ms（首次一批 `vfs` 236.66 + `graph` 146.79 + `parts` 74.36）与 frame 4078 218.7 ms，属首次加载大 CG/表情图集。
- 产物：NRO 7,905,336 B `331e0a25…`、ELF 17,218,328 B `0c216c9b…`；自包含 NSP v1.0.5 见 `docs/builds/023-rfvp-resource-cache.md` §6.3；全量 `rfvp-full.diff` 3,950 行 / 28 文件 `6930bb65…`（纯净 `9f07ade` worktree apply --check 通过）。
- 补丁/记录：`docs/builds/023-rfvp-resource-cache.md`、证据 `evidence/P17-rfvp-cache/`（16 文件 + SHA256SUMS）、计划 v1.17。
- 遗留（U 项）：U26 真机复验三类卡顿；U27 首次加载大 CG/表情图集仍 0.1–0.8 s（`graph_bg/`、`graph_bs/`、`parts/` 未预读）；U28 `graph/dissNN`（8-bit 遮罩）预读被类型过滤跳过 55 条；U29 缓存内存（texture 160 + parts 48 + bytes 192 MiB）对 4 GB 机型余量；U30 启动预读同步执行会拉长启动；U31 miniz 基线日志未归档（数值取自当次运行）。

### M5-k（P18）：大图异步解码与读档异步 restore

- 目标：处理用户 m23257 复验 P17 后剩下的两类卡顿——**CG 里的表情切换**与**背景切换**。
- 定位：P17 已有缓存，但首次出现的大图仍要在主线程同步完成「读盘 → inflate → 像素转换 → 上传」；单张 2400×1350 `graph_bg` 解码 134–160 ms、`graph_bs/CHR_*` 表情图集 84–113 ms，一次切换进 2–4 张即 200–600 ms。进一步发现 CG 入口的真瓶颈是**读档 restore**：`MotionManager::apply_snapshot_v1` 同步逐个 `vfs.read_file`+`load_texture` 恢复快照里的每张图（慢帧 `ops 0`、`vm`/`vfs_read` 占主导）。
- 修复（17 文件，补丁 `patches/rfvp-switch/rfvp-async-decode.patch` 43,704 B / 1,089 行 `7c0c1367…`）：
  - 新增 `crates/rfvp/src/subsystem/resources/async_decode.rs`：`QUEUE/DONE/PENDING/REQUESTED` 四表 + `Job`，kind=`KIND_GRAPH`/`KIND_PARTS`/`KIND_GRAPH_PREFETCH`，阈值 `ASYNC_INLINE_MIN_BYTES=1 MiB`（小图仍同步，避免打乱 UI 首帧）；
  - 大图 submit 后**主线程保留旧图**，`no_std_core.rs` 每帧 `apply_async_decodes()` 消费 `DONE`（`requested_matches` 防陈旧结果覆盖新请求）；
  - `graph_buff.rs`/`parts_manager.rs` 的 `apply_snapshot_v1` 增加 `async_id`：restore 的大图同样排队并保留旧纹理；
  - 宿主：`platform/switch/host/src/decode.rs` `rfvp_switch_decode_step` + `runtime/main.c` `threadCreate` 解码线程；`build_switch.sh` 编译新文件。
- 两条负结果：①「大图 `return Nil` 直接异步」破坏游戏加载时序（重复同步加载、id 重分配、worker 与主线程争 pack 锁，`applied=0`）→ 弃用；②libdeflate 替换 inflate 后 Citron 启动 5.58 s 崩溃（`Cannot execute instruction at unmapped address 0x0`）→ 回退 zlib。
- 验证（Citron，同一份真机复杂存档进 CG）：CG 入口慢帧 632.2（p18-i，仅 prefetch+wait）→ 299.1（p18-j，+大图异步）→ **273.4 ms**（p18-k，+restore 异步）；p18-k 帧 2601 `vm 145.41 / render 116.17 / tree 28.16 / audio_cmds 85.38 / vfs_read 23.74 / upload 27.63`、`ops 0`，随后 45.7 / 41.2 ms，异步 apply 6 次，画面正确、0 exception。
- 产物：NRO 7,929,912 B `796679ce…`、ELF 17,254,624 B `741b92ea…`；自包含 NSP v1.0.6 见 `docs/builds/024-rfvp-async-decode.md` §5.1；全量 `rfvp-full.diff` 190,338 B / 4,858 行 / 17 文件 `5c012b7a…`。
- 补丁/记录：`docs/builds/024-rfvp-async-decode.md`、证据 `evidence/P18-rfvp-async/`、计划 v1.18。
- 遗留（U 项）：U32 真机复验 CG/背景切换；U33 异步期间显示旧图 1–2 帧（刻意取舍）；U34 restore 异步窗口内取图尺寸理论上可能拿到旧值；U35 解码线程栈/内存在 4 GB 机型余量未测；U36 parts 异步 apply 后色调回落默认 100；U37 libdeflate 已回退；U38 启动帧 2.3 s 未优化。

### M5-l（P19）：异步解码运行时开关（真机黑屏回归修复）

- 触发：用户 m24478 真机反馈 v1.0.6「启动游戏后卡黑屏」。
- 定位：P18 新增的 worker 线程在 `platform/switch/runtime/main.c` **无条件 `threadCreate`/`threadStart` 且不检查返回值**，而 `graph.rs:1049-1054` 对大图 `submit_graph` 成功后立即 `return Ok(Variant::Nil)`；真机线程若未起/未跑，大图永远拿不到内容 → 黑屏。Citron 线程正常无法复现。
- 修复（4 文件，补丁 `patches/rfvp-switch/rfvp-async-toggle.patch` 6,988 B / 189 行 `6bdc0a61…`）：
  - `async_decode.rs`：新增 `async_enabled()` + 五个入口 guard；关闭时 `submit_*` 返回 false、`wait_for_*` 直接查缓存 → 回落同步解码（等价 v1.0.5）；
  - `runtime/main.c`：`g_rfvp_async_enabled` 默认 0、`read_async_enabled()` 读 `sdmc:/switch/rfvp/async.txt`、`write_async_status()` 落 `async_status.txt`（`enabled/create/start/hb`）、threadCreate/Start 失败自动回落关、worker heartbeat；
  - `host/Cargo.toml` 升 `1.0.7`（Cargo.lock 1 行）。
- 验证（Citron NRO，默认关）：`status=loaded`、窗口 `rfvp (64-bit)`、两帧 nonblack 0.9018、推进 diff 0.455366、exception 0；`async_status.txt` = `enabled=0 create=0x0 start=0x0 hb=0`（默认关生效）。
- 代价：默认关闭后 P18 的 CG 入口 632→273 ms 在真机不生效；A/B 打开方式见 `025` §6。
- 产物：NRO 7,929,912 B `a6efe53b…`、ELF 17,257,504 B `98c6464b…`、全量 `rfvp-full.diff` 194,079 B / 4,968 行 `d0a5d090…`、NSP v1.0.7 见 `docs/builds/025-rfvp-async-toggle.md` §4.3。
- 记录：`docs/builds/025-rfvp-async-toggle.md`、证据 `evidence/P19-rfvp-async-toggle/`、计划 v1.19。
- 遗留：U39 真机黑屏直接证据未取得（设备未开 DBI FTP）；U40 async 在真机上的行为待 A/B；U41 `async.txt` 为临时诊断通道需转正式配置；U42 默认关使 P18 性能收益在真机暂时搁置。

### M5-m（P20）：异步解码阶段诊断 + 看门狗自愈

- 触发：用户 m24478「真机启动黑屏」、m24969「开启 async 确实会黑屏」。
- 取证（MTP 从真机拉文件）：`async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=4`（线程创建/启动成功、心跳只到 4 次）；`debug_report.txt` 为上一次正常会话残留、无 `[async]` 行；`perf_slow.log` 全是历次正常启动；`/atmosphere/crash_reports/` 两份报告分别属 `LibAppletOf`（`010000000000100f`）与 `hbloader/sphaira`（`01009bc00c38a000`），**均与本项目无关**；无 `last_error.txt` → 判定为**整进程挂起**而非崩溃。
- 修复（5 文件，补丁 `patches/rfvp-switch/rfvp-async-watchdog.patch` 10,494 B / 280 行 `3613a6db…`）：
  - `async_decode.rs`：`report_stage()`（0 idle/1 pop/2 read/3 decode/4 publish）+ `watchdog_stalled()`（3 s pending 不变）+ `drain_inline()`（主线程同步补完队列）+ `finish_job()` 抽取；
  - `no_std_core.rs`：`apply_async_decodes` 开头检测卡死 → inline drain + 关 async + 告警；
  - `runtime/main.c`：`rfvp_switch_async_stage()` / `rfvp_switch_async_disable()`；`async_status.txt` 增加 `stage=`；主线程每 600 帧刷新；worker 栈 0x20000→0x100000；
  - `host/Cargo.toml` 升 `1.0.8`（Cargo.lock 1 行）。
- 验证（Citron，async=on 关键回归）：`status=loaded`、nonblack 0.9018、10 步全 ok；`async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=77000 stage=0`（worker 75k 次循环、回 idle、无卡死）；`debug_report.txt` 30 条 `[async]` 行（`graph/title_bg1_A` 2,051,578 B `us=384739`、`graph_bg/BG043_000` 3,838,866 B `us=138489`、parts `CHR_…_昞忣` 3,447,414 B）；无 `last_error.txt`。
- 代价：默认仍关 async（真机可玩性优先）；`async_status.txt` 的 `stage=` 为下次真机复现提供卡点，看门狗只救「worker 卡住但主线程仍进帧」。
- 产物：NRO 7,929,912 B `d16fc0d3…`、ELF 见 `docs/builds/026` §5、全量 `rfvp-full.diff` 198,586 B / 5,082 行 `19720846…`、NSP v1.0.8 见 `docs/builds/026` §4.3。
- 记录：`docs/builds/026-rfvp-async-watchdog.md`、证据 `evidence/P20-rfvp-async-watchdog/` 与 `evidence/P20b-device-crash/`、计划 v1.20。
- 遗留：U43 真机 async=on 黑屏未定位到具体一帧（本版只提供 stage 诊断 + 兜底）；U44 主线程自旋场景看门狗无效；U45 `async.txt` 仍为临时诊断开关。

### M5-n（v1.0.9）：async 强制关闭 + 帧心跳

- 触发：真机 v1.0.7/v1.0.8 黑屏；`async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=3 stage=0` → 整进程冻结而非崩溃；3 s 看门狗只在主线程 tick 内检查，主线程一卡即结构性失效。
- 措施：`runtime/main.c` 的 `read_async_enabled()` 恒返回 0（不读 `async.txt`，保留代码路径与注释）、新增 opt-in 帧心跳（`sdmc:/switch/rfvp/debug.txt` 存在时每 15 帧写 `frame_status.txt`）；版本升 1.0.9。
- 验证：NSP 9,979,495,640 B `726bb2d1…`，nstool+GalNX verify 12 checks（1 warn 未签名）；Citron 首启冒烟 19 s / 6 steps / nonblack 0.9018，`async_status.txt` = `enabled=0 …`（`async.txt=on` 仍忽略），`frame_status.txt` = `frame=4290 status=0 async=0`。
- 根因归档：`docs/experiments/rfvp-async-hang-rca.md`（H1 同核优先级反转 + spin 锁跨阻塞 SD 读 ≈85%；H2 resource_cache 临界区 log/drop；看门狗结构性失效 100%）。
- 记录：`docs/builds/027-rfvp-async-off.md`、证据 `evidence/P21a-v109-nsp-smoke/`；补丁 `rfvp-async-off.patch` 3,490 B `35658e39…` + 全量 199,493 B `9901a14d…`。

### M5-o（v1.0.0）：さくら、もゆ。720p 自包含 NSP

- 目的：用原生 720p 作品对照 1080p 的 IROSEKA，判断卡顿是否来自 NS 算力。
- 结果（Citron）：1280×720、稳定 60.0 FPS、slowest 18.0 ms、render 15.55 ms；慢帧全一次性；结论 **NS 算力非瓶颈**，IROSEKA 优先消除一次性长帧、资源压缩降备选。
- NSP 1.0.0：7,990,691,032 B `d2d42783…`，verify 12 checks；Citron 首启 / New Game / 日文正文 PASS，0 exception；`async_status.txt` = `enabled=0 …`。
- 要点：`config.toml` 的 `nls="sjis"` 必需；汉化 `patch.bin`/`SakuraChs.exe` 为 PC 注入、rfvp 不加载。
- 记录：`docs/builds/028-sakura-nsp.md`、`docs/experiments/perf-01-sakura-720p.md`、证据 `evidence/PERF-01-sakura-720p/` 与 `evidence/PERF-01b-sakura-nsp/`。

### M5-p（v1.1.0-test）：async 并发修复（pack 睡眠锁 + 换核 + 独立看门狗）

- 触发：M5-n 关闭 async 后确认黑屏根因是 async 路径冻结；`docs/experiments/rfvp-async-hang-rca.md` 给 H1 同核优先级反转 + spin 锁跨阻塞 SD 读。
- 修复：`vfs.rs` 的 `pack_lock::PackMutex` 把 `spin::Mutex` 换 libnx 睡眠互斥（svcArbitrateLock，带优先级继承）；worker 换核 cpuid=1（失败回退 -2）、prio 0x30；独立看门狗线程 prio 0x2F 监视主线程帧计数（3 s 写 `watchdog_status`、10 s 自动关 async）；`resource_cache` 把 log/perf/大 Arc drop 移出临界区；worker 读 1 MiB 分块 + `report_stage(2)`；恢复 `async.txt` 读取（默认关）。
- 验证（Citron）：73/73 步 320 s / 19,200 帧，`async_status` 终值 `enabled=1 hb=295384 main=19199 stage=0 cpu=1 wdt=1 stalled=0`，无 `watchdog_status` / `last_error`，60.0 fps slowest 19.6 ms，8 次 async decode applied；另一轮 10.6 min / 39,600 帧长跑不冻结。
- 产物：测试 NSP `E:/galnx-build/p22/out/IROSEKA_FHD-010047420000a000-v1.1.0-test.nsp` 9,979,498,200 B `753082b7…`；补丁 `rfvp-async-fix.patch` 24,772 B `203d936d…`（6 文件 +321/−69）+ 全量 212,537 B `3d25d9b8…`（暂存仓库外）；NRO `69bdd09c…` / ELF `ef311f9a…`。
- 记录：`docs/builds/029-rfvp-async-fix.md`、证据 `E:/galnx-build/p22/evidence-clean/`；**真机确认前不推送**。
- 真机验收：装 NSP → `sdmc:/switch/rfvp/async.txt=on` → 清旧日志 → 进正文玩 3–5 min → 判定 `hb` 递增 / `cpu=1` / `wdt=1` / `stalled=0` / 无 `watchdog_status` 与 `last_error`。

### M5-q（v1.0.1 / v1.0.2）：さくら、もゆ。中文剧情与 UI 贴图

- 中文来源：PC 汉化补丁 `patch.dat`（57,172/57,172 条命中）；**字节码级原位重打包**（不反编译）——只改 hcb `push_string` 载荷、按指令边界重算绝对地址；`ThreadStart`（syscall 136）前 1 条 `push_i32/i16` 是函数入口绝对地址，字符串变长后需 phase2b 重定位（99/99 站点）。
- v1.0.1：`Sakura.hcb → SakuraGBK.hcb` 4,283,683 B `4d4fd729…` + `config.toml` 的 `nls=gbk`；NSP **7,989,970,136 B `91ad7b96…`**（title_id `010047420000C200`），Citron 标题→正文中文 PASS。
- v1.0.2：把 `patch.bin` 内 60 条 hzc1 UI 贴图（14,358,332 B）以 loose 文件覆盖 `graph/graph_vis`；NSP **8,004,355,288 B `5708da95…`**，verify 12 checks（0 fail + 1 warn），Citron 冒烟 11/11 步、60 FPS、无错位；标题 logo 中文，菜单按钮仍英文+日文 ruby（资产缺口）。
- 记录：`docs/builds/031-sakura-cn-nsp.md`（§1–§8 剧情、§9 UI 贴图）、`docs/experiments/l10n-02-sakura.md`（路径 A 推荐 / C 备选 / B 禁止）、证据 `evidence/P22a-sakura-cn-nsp/` 与 `evidence/P22b-sakura-cn-nsp-v2/`。
- 限制：UI 菜单贴图未全中文；译文 CC-BY-NC-SA 4.0；3 处 ruby 排版瑕疵；未真机。

### M5-r：真机残余卡顿画像（v1.0.9 日志）

- 取证：用户取回 13 次运行 `perf_slow.log` / `debug_report.txt`（`E:/galnx-build/p21/device-logs/`）；1079 慢帧。
- 画像：真实写盘 save 137 帧 p50 **89.98 ms**（finalize 59.58 + thumb 24.73 + snapshot ~5）；`vfs_read` 223 帧 p50 192.59 / p90 1235.88 / max 3382.21；`graph_decode` 166 帧 p50 159.37；`audio_cmds` >100 ms 34 帧 415–1314；启动 frame1 1.35–4.45 s；大过渡 f777 4473.7 ms / f825 3962.8 ms。
- 关键根因：Switch 后端未实现 `load_stream` → `flush_audio`（`no_std_core.rs:729-731`）走 `read_all + load_encoded`，整条 BGM/语音在**主线程**从 SD 全量读出解码；缩略图 GPU 快路径在真机未生效（回退 CPU 24.7 ms）。
- 记录：`docs/experiments/perf-02-device-v109.md`（含 §7 audio 根因、修复优先级表）；后续优化=P24 task-51（vfs 异步读 / audio 流式或异步 / 写盘 90 ms）。

### M5-s（v1.1.1-test）：async 返工为 prefetch-only（P25）

- 触发：M5-p 真机未通过 —— 部分 CG 只剩对话框/UI、UI 开合残留旧像素、序幕→第一章 OP 跳过（`docs/experiments/rfvp-async-device-defect.md`、证据 `evidence/P22d-async-device-fail/`）。根因：P18 的「大图 submit 后立即 `return Ok(Variant::Nil)`，下一 tick 补图」延迟绘制语义，与 rfvp 按 id 逐帧重画不兼容；纹理未就绪即不画、不清屏（残留），id 在解码完成前重分配则结果丢弃（CG 整段缺失）。**与锁无关**。
- 修复（prefetch-only）：`graph_load` / `parts_load` 删除延迟提交与「返回 Nil」路径 —— 未命中→预取同组伙伴图→最多等 300 ms→命中即用，否则同步 `vfs_load_file` 解码返回真实纹理；snapshot 只保留 prefetch 预热；队列按 path 去重、on-demand 入队头、prefetch 入队尾；`apply_async_decodes` 只服务预取缓存。改动 8 文件 +87/−110。
- 验证（Citron）：async-fix 长测 152/152 步 0 failed、连续 5.8 min，`enabled=1 hb=456000 stage=0 cpu=1 wdt=1 main=29812 stalled=0`、无 `watchdog_status`/`last_error`、60.0 fps slowest 17.2 ms；Lead 独立冒烟标题→读档列表→DATA_001 真红 CG 完整→CG 内推进→切场景全部 PASS（`enabled=1 hb=105000`，`frame=6840`），截图与 SHA256 见 `evidence/P25a-async-prefetch-lead-smoke/`。
- OP 跳过独立根因：no_std 构建未启用 native-video，`videoplayer/mod.rs:113-115` 直接 `bail!("no movie decoder in this build")` → 脚本继续；本次仅加诊断 warn，播放能力另立项。
- 产物：NSP `E:/galnx-build/p25/out/IROSEKA_FHD-010047420000a000-v1.1.1-test.nsp` 9,979,496,152 B `bf83fa6e…`；verify 12 checks（0 fail + 1 warn）；NRO `08354233…` / ELF `a4243c24…`；补丁 `rfvp-async-prefetch.patch` 17,298 B `295ee725…` + 全量 212,899 B `4c3cd3b7…`。
- 记录：`docs/builds/032-rfvp-async-prefetch.md`；真机 CG/UI/OP 三项验收通过前不推送。

### M5-t（v1.0.10-test2）：rfvp 音频流式与缓存预算（P24）

- 触发：真机 perf 画像里 `audio_cmds` 34 帧 >100 ms（415–1314 ms）；根因=Switch 后端未实现 `load_stream`，`AudioCommand::LoadStream` 回退 `read_all + load_encoded`，整条 BGM/语音在**主线程**从 SD 全量读出解码（`no_std_core.rs:729-731`）。
- 修复：`platform/switch/host/src/audio.rs` 实现 `load_stream` / `read_stream` 回调（+72 行）走流式；`resource_cache.rs` TEXTURE_BUDGET 160→256 MiB、MAX_ENTRY_BYTES 16→48 MiB。4 文件、补丁 159 行。
- 验证（Citron）：同内容帧 audio_cmds **180.08/335.17 → 29.39/21.34 ms**（−83.7%/−93.6%），>100 ms 音频帧 **2 → 0**；vfs p50 目标 −30% **未达成**（+8.8%），写盘无样本 **未验证**，纹理缓存 **无可观测收益**（峰值 123.26 MB 未触旧限）。
- 限制：baseline 全量补跑两次 abort（P25 冒烟撞车 + Citron 被他人占用），前 407 s 为正式对比窗口；旧原始日志被覆盖，统计存 `E:/galnx-build/p24/compare-win.json` 与 `compare-full.json`。
- 产物：NSP `E:/galnx-build/p24/out/IROSEKA_FHD-010047420000a000.nsp` 9,979,497,176 B `79aedc03…`；补丁 `rfvp-perf.patch` 6,057 B `9418d20f…`。
- 记录：`docs/builds/030-rfvp-perf.md`、`docs/experiments/perf-02-device-v109.md` §8；后续 vfs 预取与写盘分帧单独立项。


### M5-v（v1.1.3-test）：rfvp 音频连续性（P27）

- 缺陷（用户 m28040）：主线程长帧卡顿时音频随之断续；根因 = `platform/switch/runtime/main.c` 的 `audio_pump()` 只在主循环每帧调用一次，6×`AudioDriverWaveBuf`×1024 帧 ≈128 ms 硬件缓冲，主线程被 vfs/解码卡住 300–1500 ms 即 underrun。
- 修复（`rfvp-audio-continuity.patch` 22,016 B sha `4f7a207f…`，3 文件 +330/−4）：3.07 s SPSC ring（144 页×1024 = 147,456 帧）+ 独立音频线程（prio 0x2D、栈 0x10000、cpu{2,1,-2}，每帧最多渲染 8 页≈170 ms，失败回退 `audio_pump_direct`）+ `debug.txt` 的 `stall=NNNN`/`stall_at=NNNN` 注入 + `audio_status.txt`/`audio_stall.txt` 观测。
- 验证（Citron，Lead 独立）：注入 3×1.2 s 主线程停顿，`audio_status` = `driver=1 thread=1 alive=1 cpu=2 cap=147456 ring=147456 underrun=0 max_underrun_ms=0 starve_ms=0 stalls=3 stall_ms=1200`；三对 `audio_stall` pre(147456)→post(90112/90112/89088)、间隔 1.2015–1.2017 s；60 FPS、无 `last_error`。
- 产物：NSP v1.1.3-test 9,979,503,320 B sha `eaea4446…`；NRO 7,938,104 B `e3557f53…`、ELF 17,284,120 B `437862fe…`；记录 `docs/builds/034-rfvp-audio-continuity.md`、证据 `docs/milestones/evidence/P27a-audio-continuity/`、全量 `E:/galnx-build/p27/rfvp-full-v113.diff`。
- 未闭环/限制：①真机听感未验（随 v1.1.4-test 一起）；②ring 常驻 ≈576 KiB，音频线程实时性与 SD 争用未测；③stall 注入仅用于验证，默认不生效。

### M5-w（v1.1.4-test）：rfvp 场景切换过渡动画（P28）

- 缺陷（用户 m28040）：场景/背景切换一直硬切、从未出现过渡动画。
- 根因：反编译 `iroseka.hcb`（4,275,282 B、948,219 指令、5,064 次 syscall）确认转场 100% 走 Dissolve 家族（Dissolve ×2、DissolveWait ×16，无 rule/trans）；rfvp `other_anm.rs` 已实现 MaskFadeInOut/FadeIn/ColoredFadeOut/In，但 no_std 路径 `no_std_core.rs::render_game_frame` 未把上一帧作为 mask 快照传入 → `mask_dissolve.rs` 的 nosnap 分支「没有上一帧就一次性换场」= 硬切（std 路径 `app.rs` 有该接线）。
- 修复（`rfvp-transition.patch` 3,178 B / 76 行 sha `b9717fea…`，4 文件 +31/−2）：no_std 路径在 `render_motion_to_host` 前按 `mask_frame_wants_snapshot` 调 `capture_thumbnail` → `set_mask_snapshot`，并在 `prim_commands.rs` 补两个转发方法；版本 1.1.4-test。
- 验证：CPU harness 修复前 run4 在 MaskFadeInOut 后 1062 帧起纯白 255 持续 114+ 帧（硬切），修复后 run5 `mask_build=1`（graph/diss00 1920×1080）、`mask_phase=188`、188 帧灰度渐变；Citron GPU v114 NRO 抓到白场 4–5 帧淡出/淡入与 CG 双重曝光中间态。
- 产物：合并 NSP v1.1.4-test 9,979,503,832 B sha `444af465…`（基线 = P26+P27，romfs 161 条目全内嵌；verify 12 checks / 0 fail / 1 warn）；NRO 7,938,104 B `641af84c…`、ELF 17,284,272 B `aed842f7…`；记录 `docs/builds/035-rfvp-transition.md`、`docs/experiments/trans-01-iroseka.md`、证据 `docs/milestones/evidence/P28a-transition/` 与 `P28b-lead-smoke/`、全量 `E:/galnx-build/p28/rfvp-full-v114.diff` 675,760 B sha `4cc7a268…`。
- 未闭环/限制：①真机过渡观感未验；②每次 mask 转场多一次 8,294,400 B 回读，耗时/内存未测，Citron 回读时序 ≠ 真机 EGL；③Citron 日志仍有约 3,968 条 `Invalid duration`（motion.rs，独立缺陷）；④OP/Movie 另立项 P29。

### M5-x（v1.1.6-test）：rfvp 音频 JIT（P30，修复 3 秒延迟）

- 缺陷：v1.1.4-test 真机「所有音频约 3 秒后才播放」。根因=P27 的 3.07 s 预渲染 ring 在主线程侧被填满（每帧最多渲染 8 页 ≈170 ms），音频线程按硬件节奏只消费最旧 6 页 → 听到的永远是约 3 秒前的混音；预渲染量与延迟不可兼得。
- 修复：音频线程按需（JIT）apply `AudioCommand` + 即时 mix；帧线程只入队；删除 ring/producer。延迟回落至硬件 FIFO 深度（6×1024 帧 ≈128 ms）。
- 验证：Citron 注入 3×1.2 s 主线程停顿 → `mode=jit lag_ms=-101 underrun=0 max_refill_gap_ms=44 stalls=3`；三对 pre/post 的 rendered_ms 各推进 1194–1195 ms；async 回归 `enabled=1 hb=120000 wdt=1 stalled=0`、无 last_error。
- 产物：NSP v1.1.6-test `d7eb77ec…`（9,979,505,368 B）；补丁 `rfvp-audio-jit.patch`（1,059 行 `e81cd49c…`）；全量 688,326 B `a489c3e9…`；文档 `docs/builds/037-rfvp-audio-jit.md`。
- 限制：音频线程内首次解码可能一次轻微 gap（实测 44 ms）；真机实时性与堆待观察；尚未并入 P29 OP 播放。

### M5-y（v1.1.7-test）：rfvp OP 影片播放（P31+P32，P29 合并）

- 目标：把 P29 的 OP/Movie 播放与 P30 音频 JIT 合并为 1.1.7-test，在 Citron 上验证「OP 画面 + 内嵌音轨」端到端（用户 m28838 要求「视频解码做好 = rfvp 试点完美收工」）。
- P31（画面，`rfvp-op-movie.patch` 46,709 B sha `95abafc8…`）：no_std 路径接入 720p30 WMV 软解（videoplayer），`movie/01.wmv` 124,386,038 B sha `62abe508…`、`movie/01.ogg` 2,343,033 B；每 tick 最多解 1 帧（`MAX_DECODE_PER_TICK: usize = 1`，`horizon.rs`），按 `target_pts_ms = base_pts_ms + elapsed_ms` 丢弃落后帧只呈现最新帧 → 解码吞吐低于源帧率时呈慢放而非延迟累积；romfs 162 项 9,814,160,982 B。
- P32（音轨，`rfvp-op-audio.patch` 338 行 / 3 文件 +203/−18 sha `9e429779…`）：`AudioStreamId::MOVIE = Self(0x2000)`（`crates/rfvp/src/host_api/audio.rs:89`），`classify()` 新增 `AudioSlotKind::Movie`（mixer 容量检查最多一路），OP 音轨走 P30 音频 JIT 线程混音；无 WMA 解码器，故音轨固定为同名 `.ogg`（Vorbis）。
- Citron 验收（双形态）：NRO 22 步 PASS；Lead 独立 NSP 36/36 步 0 failed（run dir `E:/galnx-build/p32/run-lead-op/20261107-165307-…`，18 张截图 sha 互异、相邻 mad 42.93–81.22、`steps_diff_ratio=0.822764`、窗口 `1.1.7-test`）。`debug_report.txt`：`Movie: opened` / `movie audio: loaded` / `playing` 各 1、`decoded`/`presented` 各 109、帧 1..3240、`pts=108075 ms`；`audio_status.txt` = `mode=jit lag_ms=-102 underrun=0 max_refill_gap_ms=44 stalls=0 rendered_ms=200640 uptime_ms=200538`；`async_status` = `enabled=1 hb=197000 stage=0 cpu=1 wdt=1 stalled=0`；无 `last_error.txt`。
- 产物：NRO 8,290,360 B `a8fb7b7b…`、ELF 17,684,312 B `e9ee44c9…`、**NSP v1.1.7-test 9,861,393,624 B sha256 `cb019f27…`**（verify 13 checks / 0 fail / 1 warn 未签名）；全量 `/e/galnx-build/p31/rfvp-full-v117.diff` 305,725 B / 62 文件 `cf911433…`；记录 `docs/builds/038-rfvp-op-playback.md`、证据 `docs/milestones/evidence/P32a-op-nsp-lead/`。
- 限制：①Citron 只有 15 FPS（OP 呈 0.5–0.6× 慢放，是模拟器解码吞吐不足而非补丁缺陷；真机实时性待验）；②OP 触发依赖 `debug.txt` 的 `movie=1` 调试钩子（剧情内自然触发点未在真机确认）；③音轨无 WMA 解码，遇到只含 WMA 音轨的 WMV 会静音；④日志有 1 条 `[ERROR] id must be in range 0..256`（Movie 流 0x2000 相关，未影响播放）。

### M5-z（v1.1.9-test）：rfvp OP 分档（720/540/480/360）+ 原生尺寸路径（P33）

- 目标：P32 的 v1.1.7-test 在 Citron 只有 15 FPS（`MAX_DECODE_PER_TICK=1`），真机 720p 软解是否实时未知；把 OP 做成可切换的分辨率档位，并去掉「720p 源先上采样到 1920×1080 再全屏拉伸」的浪费。
- 实现：romfs 内嵌 4 档变体（`01.wmv` 1280×720p30 124,386,038 B；`01_q540.wmv` 960×540@29.97 59,387,638 B；`01_q480.wmv` 854×480@24 38,610,038 B；`01_q360.wmv` 640×360@24 17,870,838 B），`sdmc:/switch/rfvp/video.txt` 单行关键词选档（缺/非法**默认 480**，变体缺失回退原片并 log）；`yuv420p_to_rgba_native_into` 按变体原生尺寸转换、渲染层 GPU 拉伸全屏；spare RGBA buffer 复用；帧内计时改宿主 `perf::start()` 微秒时钟（no_std `Instant` 只在 tick 前进，测不到帧内耗）；`debug.txt` 新增 `movie=nil` 复现游戏真实的 layer-movie 调用。10 文件 +414/−79，`rfvp-op-quality.patch` 30,381 B sha `76e2f12d…`（基准 P32 合并树 `3dd9e56`，非单一 commit）；全量 62 文件 +6,250/−322 sha `e1793be2…`。
- 验收（Citron NSP 形态，36/36 步 PASS，run dir `E:/galnx-build/p33/run-lead-119/20261107-232940-…`）：`video.txt=480` → 打开 `movie/01_q480.wmv level=2 bytes=38610038`；854×480 原生尺寸（桌面 decode 8.4–15.1 ms + convert 3.0–5.8 ms/帧），decoded/presented 2880 帧 / `pts=119958 ms` 播完整段 OP，随后 `movie audio: stopped`，n12–n18 同哈希 = OP 结束后静止标题帧（非卡死）；`audio_status` `lag_ms=-108 underrun=0 max_refill_gap_ms=56`；perf total 16.49 ms（Citron 60 fps）；窗口 `1.1.9-test`。
- 产物：NRO 8,228,920 B `cb018355…`、ELF 17,421,312 B `d8daa643…`、**NSP v1.1.9-test 9,977,492,184 B sha256 `bd909c1e…`**（verify 13 checks / 0 fail / 1 warn 未签名；romfs 9,930,029,496 B / 165 项）。
- 限制：①**真机帧率仍未证**（本轮设备离线未上传；480p 桌面 11–21 ms/帧，A57 估 3–5×）；②默认档 480p 画质下降，真机 720p 流畅时应写 `720`；③变体只降视频，音轨仍为同名 `.ogg`；④OP 触发仍靠 `debug.txt movie=1` 钩子；⑤NSP 已逼近 10 GB（9.98 GB）；⑥NRO 形态本轮未回归。
- 记录：`docs/builds/039-rfvp-op-quality.md`、证据 `docs/milestones/evidence/P33a-op-quality/`、补丁 `docs/builds/patches/rfvp-switch/rfvp-op-quality.patch`、runbook §13.10。

### M5-aa（v1.1.10-test）：WMV2 左缘马赛克修复（P34）

- 缺陷（用户 m31365，真机 v1.1.9-test）：OP「很流畅，但糊；最左侧有一列均匀排布的马赛克方格」。ffmpeg 解出的源帧左缘干净（第 720 帧），Citron 可稳定复现 → 缺陷在 crate 自带 WMV2 软解链路。
- 定位：`01_q480.wmv` 854×480（=16×53+6，非 16 对齐）。宿主 oracle 探针 `E:/galnx-build/p33/probe-wmv`（Cargo path 依赖 `crates/na_wmv_player`，`default-features=false, features=["std-error"]`，`cargo build --offline` 10–17 s）取 pts=30000 帧 dump Y 平面，与 ffmpeg rawvideo 第 720 帧逐列比对：旧解码左 12 列 |ΔY| 63–84，且 col0 内容对应 ffmpeg 列 848–850 → 越界写按 stride 折返到下一行行首；P 帧 MC 再从被污染参考帧向内扩散（84→20→2 随列衰减）。
- 根因：`crates/na_wmv_player/src/na_wmv2dsp.rs:102/127` 的 `wmv2_idct_add`/`wmv2_idct_put` 写循环只判 `idx >= dest.len()`，没有行边界守卫；`mb_w = 854.div_ceil(16) = 54`，末列宏块 `bx = 848/856` 写出界 2/8 列（chroma 同样溢出：`mb_col*8 = 424`，chroma 宽 427）。同文件 `write_intra_block*`/`add_residual_block_i16` 四条写路径都有 `by + r >= ph` / `bx + c >= stride` 守卫，只漏 IDCT 两条。
- 修法（`rfvp-wmv2-padding.patch` 101 行 / 1 文件 / sha256 `b221b708…`，基准 P33 树）：照搬同 crate Wmv3/WVC1 既有模式——`crates/na_wmv_player/src/api.rs` 用 coded 尺寸（864×480）解码 + `visible/crop_frame` 裁剪回 854×480 输出。关键点：`Wmv2Params::new` 必须传 coded 尺寸（否则 `decoder.rs:6395` 会把 `MacroblockDecoder` 重置回 display 尺寸）、参考帧保持 coded（P 帧 MC 在完整宏块面上做）、`ffi.rs` 的 `current_frame()` 必须返回 display 尺寸帧（stride=854）。
- 验收：宿主 oracle mean|ΔY| 2.918→**1.470**、`|Δ|>32` 像素 6,777(1.653%)→**30(0.007%)**、左 12 列均值 63.35→**3.36**、右缘 0.22→0.18（无回归）、行首复写检测 29/58 行→**0/0**、输出仍 854×480；Citron（NSP 形态 `video.txt=480`）`Movie: opened … name=movie/01_q480.wmv level=2 bytes=38610038`、decode_us 8.1–15.2 / convert_us 3.4–6.0（与 P33 持平）、左缘干净（`cmp-old-left.png` 有竖直马赛克列 / `cmp-new-left.png` 干净渐变）、0 exception；`[ERROR] id must be in range 0..256` 仍为 Movie 流 0x2000 已知噪声。
- 产物：NRO 8,228,920 B `a80f7289…`、ELF 17,421,328 B `c516046b…`、**NSP v1.1.10-test 9,977,492,696 B sha256 `fc35fa9880ba9e38db737f2648bfa309b4e54ab0dd2571265af58d7156c4ee1d`**（verify 13 checks / 0 fail / 1 warn 未签名；romfs 9,930,029,496 B / 165 项不变，仅 exefs/main 变化）。
- 限制：①真机未验（NSP 由用户自行安装）；②「糊」未解决——480 档仅 854×480 上屏必糊，需用户以 `video.txt=540/720` 对照决定默认档；③WVC1/Wmv3 路径已有裁剪但未做全量 16 对齐回归；④Citron 偶发启动崩溃仍在（harness 重试）。
- 记录：`docs/builds/040-wmv2-left-edge.md`、证据 `docs/milestones/evidence/P34-wmv2-left-edge/`、runbook §13.11、补丁 README P34。

### M5-ab：NVDEC 硬解探针（probe1-4，P35/P36）

- 动因（用户 m32205）：OP 走 no_std 软解「480 糊、720 慢放」；用户用 SwitchWave 确认真机能放 1080p VC-1，于是立项评估 NVDEC。
- probe1（真机，application 模式）：`/dev/nvhost-nvdec` 可开、全 rc=0、VC-1 `max_mbs=8192`（1080p 需 8,160）；`applet_type=0 application=1`。
- probe2（Citron，无 NVDEC）：demux + hwdevice 链路 + 750 帧，DECODE avg 19.50 ms（软解兜底）。
- probe3（Citron）：FFmpeg + envideo + SDL2 全片 750 帧 PASS，fps 18.896、DECODE 19.926 ms、CONVERT 27.779 ms；像素校验显示帧 180 ≡ 解码序 179（luma mean|Δ| 5.25 / PSNR 32.42 dB，仿射 BT.601 limited→full 后 0.21 / 58.47 dB）。
- **probe3 真机结论（决定路线）**：`dec=1.67ms` 但 `xfer=20000.25ms`，`hw=7 sw=0 fps=0.10`，屏幕整屏绿 + 顶部约 17% 扫描线 ⇒ **NVDEC 解码可用、Copy Engine 的 tiled→linear 转换不可用**。
- 否定假设：`envideo_map_pin` 缺失不是 CE 慢的原因（`common.hpp:203 engine_is_multimedia()` 对 Copy/Host 为 false ⇒ pin 是 no-op）。
- **probe4（P36，绕过 CE）**：Horizon 上 NVDEC 帧的 envideo map 是 CPU 可写主机内存（`device.cpp:794-797`）⇒ fence 等待 + CPU 直读 block-linear 表面 + 软件 de-tile + 用软解同帧 PSNR 标定布局（平面 1 偏移 3 候选 × tile 行高 4 候选 = 12 组）。NRO 9,420,856 B `b5acc4de…`；Citron 链路级 PASS（`swref found=2 655.4 ms`、120 帧全 `hw=0`、`=== DONE ===`），hw 分支只能真机验证。
- 限制：布局未验证（2,088,960 / tile 行 16 行来自驱动字段推导）；CE 根因仍未定；未接入 rfvp 播放器（下一步 P37 1080p VC-1 直放 + 480 兜底）；envideo GPL-2.0 + gpl FFmpeg ⇒ 分发需附源码。
- 记录：`docs/builds/041-nvdec-probe3.md`、`docs/builds/042-nvdec-probe4.md`、`docs/research/nvdec-probe3/`、`docs/research/nvdec-probe4/`、证据 `docs/milestones/evidence/P35-nvdec-probe3/` 与 `P36-nvdec-probe4/`。

### M5-ac：NVDEC 探针 probe5/6（P37/P38）

- probe4 真机回传（P36）：`fence_wait rc=-3420 took=5000151 us`、`raw head` 全 0、8 组 de-tile 候选 psnrY 全 0.71 ⇒ 表面全 0，布局假设未被检验；`decode error: avcodec_send_packet ... (-1313558101)`。
- **probe5（P37）思路**：先证底层——复刻 envideo 官方参考测试（MPEG-2 128×128 + 已知哈希 `0xa2c4a330592602d5`），回答「NVDEC + tiled + CE + cache + fence 在本机能不能用」。
- **probe5 真机 Phase A = PASS**：`device_create rc=0`、`decode signalled after 0 us`、`status error=0 mbs_ok=64 cycles=5042`、`hash map(24576)=nv12(24576)=expected=a2c4a330592602d5`、`PHASE A verdict: PASS`；BMP 可见彩条与时间码 ⇒ **硬件/CE/tiling 全部排除**。
- probe5 真机 Phase B（FFmpeg envideo + VC-1）= 仍 FAIL：fence 2 s 轮询不 signal、`AVERROR_UNKNOWN`（`envideo_decode.c:255` 的 nvdec_status 检查）⇒ 失败域收缩到 FFmpeg 的 envideo 封装路径（上游无 hwaccel 自测覆盖）。
- probe5 Citron：`device_create rc=-88` → `PHASE A verdict: FAIL`（优雅降级、不崩），Phase B 120 帧、`=== DONE ===`。
- **路线切换**：改用 `averne/FFmpeg` 的 **nvtegra** hwaccel（分支 tip `caeec83b791be08ed43468a2ef426d6901d51c78`；SwitchWave 1.1.2 用 `--enable-nvtegra` 且真机放过 1080p VC-1），即 probe6。
- **probe6（P38）工程**：`AV_HWDEVICE_TYPE_NVTEGRA` + `AV_PIX_FMT_NVTEGRA`（sw_format NV12），hw 不可用自动降级软解；SD 产物 `nvdec-probe6.txt` + 目标帧 BMP + PSNR 对照。
- probe6 构建坑：`libavutil/nvhost_ioctl.h:27` 在非 `__SWITCH__` 下引 `linux/ioctl.h` ⇒ devkitA64 不自动定 `__SWITCH__`，须 `--extra-cflags="-D__SWITCH__ -D_GNU_SOURCE -D_POSIX_VERSION=200809L -isystem /opt/devkitpro/libnx/include"`；修复后 libavcodec/libavformat/libavutil 三静态库构建成功。
- probe6 修 bug：`frame_index` 初版只在 hw 帧自增 ⇒ Citron（软解）永不命中目标帧；改为**显示序**计数器后 BMP/PSNR 才生效。
- probe6 Citron（两次）：`hw: nvtegra device created` + `frames ctx 1920x1080 format=nvtegra sw=nv12`（上下文可建，但解码帧 `hw=0`）、软解 120 帧 `elapsed=10027 ms`、`PROBE6 verdict: hw=SOFTWARE-ONLY`、`=== DONE ===` ⇒ Citron 不能作为硬解证据。
- 片头白帧疑点排除：Citron `probe6-f001.bmp` 纯白（mean 255 / std 0），PC ffmpeg 9.0 解同一 wmv 显示序第 0/1 帧同样纯白、第 30 帧彩色 ⇒ 片源白闪，探针正确（ffmpeg 9.0 需用 `-fps_mode passthrough`，`-vsync` 已移除）。
- 产物：probe5 NRO 9,437,240 B `e438c91f…`；probe6 NRO 9,117,752 B `92e1796a…`；真机包 `E:/galnx-build/nvdec/device-test-v5/` 与 `device-test-v6/`（README+SHA256SUMS+NRO+wmv），设备写入由用户执行。
- 限制：probe6 真机结果未回（`hw=1` 与 `psnrY>40` 才算通）；nvtegra 是 FFmpeg 分支非上游；`--enable-gpl` ⇒ 分发需附源码；probe6 走 `av_hwframe_transfer_data` 多一次拷贝，不代表最终播放器性能。
- 记录：`docs/builds/043-nvdec-probe5.md`、`docs/builds/044-nvdec-probe6.md`、`docs/research/nvdec-probe5/`、`docs/research/nvdec-probe6/`、证据 `docs/milestones/evidence/P37-nvdec-probe5/` 与 `P38-nvdec-probe6/`。

### M5-ad：NVDEC 探针 probe9（P39，真机硬解 297.8 fps，慢放真因 = CPU NV12→RGBA 43.5 ms）

- **probe8 作废**：真机 10.77 fps 是探针自身日志污染——日志 4,922,445 B / 70,478 行，其中 70,175 行 FFmpeg TRACE，每帧 61–72 行、每行 1.4–3.1 ms 逐行 fflush 到 SD；仅日志写入就约 140 s，与其 decode-only 同量级。probe8 的 HARDWARE PROOF: PASS 仍有效（帧格式统计与时间无关）。
- **probe9 五项改动**：av_log_set_level(AV_LOG_ERROR) + 回调只计数；logf 2 秒缓冲；galnx_nvdec_next() 内拆 read/recv 计时（GalnxNvdecTiming）；io_bench() SD 读基准；log_clocks()；新增 B2-h264 交叉验证（同一 OP 的 H.264 转码 200 帧）。
- **真机结果（决定性）**：get_format chosen: nvtegra (hardware) 每阶段成立、HARDWARE PROOF: PASS (frames=60 hw=60 sw=0 strict_failed=0)；
  - A-verify 60 帧 218.3 ms = **274.84 fps**；B-decode600 600 帧 2,014.8 ms = **297.80 fps**（decode mean **0.44 ms**，p50 0.37 / p95 0.71）；
  - B2-h264 200 帧 600.6 ms = **332.98 fps**；
  - C1-transfer 120 帧 704.7 ms = **170.29 fps**（xfer mean **3.79 ms**，p95 3.87）；
  - **C2-rgba 60 帧 10,900.2 ms = 5.50 fps（rgba mean 43.54 ms，p50 43.54 / p99 43.57）**；
  - C3-upload 17.50 fps（upload 8.16）、C4-render 17.16 fps（render 2.44）、C5-pace 16.93 fps；
  - PROBE9 verdict: hardware_decode=CONFIRMED decode_only_fps=297.80 rgba_fps=5.50 render_fps=17.16 paced_fps=16.93 h264_fps=332.98。
- **结论**：NVDEC 解码与 Copy Engine 传输在真机都完全可用且极快，probe1–5 所有「硬解不可用」结论全部推翻（那是 FFmpeg envideo 封装与旧路径问题）；**慢放唯一主因是 CPU NV12→RGBA 43.54 ms/帧**（占 C2 每帧 48.65 ms 的 89%），把 60 fps 压到 ~17 fps。
- **对 movie player 的路线**：read 1.5 + decode 0.44 + xfer 3.79 + upload(NV12 双平面) ~3 + shader ~2 ≈ 10.7 ms/帧（~93 fps）；即去掉 CPU RGBA，改 NV12 双平面纹理 + GLES2 fragment shader 做 BT.601/709 矩阵。更远为零拷贝（deko3d/NVN，Moonlight/SwitchWave/night100 路线）。
- **其他真机数字**：SD 读 30.2 MiB/s（2.072 ms per 64 KiB，4 KiB 跳读 0.419 ms）；clocks 仍读不到（rc=0x00004b59）；frame pool pool_size=0 是探针取池方式问题。
- **产物**：NRO 9708465d859600aa84e56ed6bff068fd5592e700eba32cbec1de8ad0229f3773（9,134,136 B）、ELF aca57a8e88f411f8009e3a403d1bfcb13056b9803924c85f81d7b6c3ecdd9bdd。
- **真机包**：E:/galnx-build/nvdec/device-test-v9/（probe9 NRO + VC-1 wmv + H.264 mp4 + README + SHA256SUMS）。
- **记录**：docs/builds/045-nvdec-probe9.md、docs/research/nvdec-probe9/、docs/milestones/evidence/P39-nvdec-probe9/。
- **限制**：单线程串行、无 decode-ahead；未验证音频同步/丢帧/长播；双平面 shader 与零拷贝路径均未实现（只有预算估算）。

### M5-ae：OP 换 H.264 + NVDEC(nvtegra) 硬解接入（P40，v1.2.0-test）

- 动机：M5-ad 已证真机 NVDEC 解码 297.80 fps、CE 传输 3.79 ms，慢放唯一主因是 CPU NV12→RGBA 43.54 ms；而游戏真 OP 是 `wmv2 1280x720 30000/1001 8 Mbps 120.02 s`——Tegra 无 WMV2 硬解（nvtegra 只覆盖 vc1/wmv3/h264）。
- 资产：ffmpeg 重编码 H.264 High/4.0/crf18，显式写 BT.709 三件套与 `-color_range tv`，`-an`（音轨仍用 `movie/01.ogg`）→ `movie/01_h264.mp4` 108,361,267 B sha256 `bddf82fc7e78e256d812051a4f548c2dce07d8cdcda6c80562ea588f32757bad`（120.0199 s，7,220,533 bps）。
- 代码（2 接线点 + 5 新文件）：`platform/switch/runtime/rfvp_movie_h264.c/.h`（FFmpeg+nvtegra 播放器；`file:` 协议前缀、持久错误缓冲、`sdmc:/switch/rfvp/h264_sw.txt` 强制软解）、`rfvp_movie_color.c`（BT.709 limited→full 定点 + NEON 16 像素 kernel）、`videoplayer/horizon_h264.rs`（`H264Playback` 实现 `MovieSource`，复用 `load_movie_audio`，失败回落 WMV2）、`horizon.rs`（子模块 + `try_open`）、`main.c`（`galnx_movie_init(game_root)`）、`build_switch.sh`（FFmpeg 头/库路径与 `--start-group` 链接）。
- 构建坑：①`libavutil/avconfig.h` 在 build 目录生成 → CFLAGS 必须同时 `-I$FFMPEG_SRC -I$FFMPEG_BUILD`；②`rfvp_movie_color.c` 缺 `<stddef.h>` → `size_t` 未声明。
- Citron 影子验证（无真 NVDEC，一律 `h264_sw.txt` 强制软解、`hw=0`）：
  - NRO 形态（SD 游戏目录）：24/24 步 ok，`Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4`，整段 OP **3597 帧 EOS**，`convert_us` p50 2,520 µs。
  - NSP 形态（romfs，冒烟前挪走 `sdmc:/switch/rfvp/game` junction → `game_root=romfs:/game`）：24/24 步 ok，`nonblack_ratio=0.9018`，OP 3597 帧 EOS，OP 后 `frame 5880: 60.0 fps over the last 60 frames, slowest frame 18.1 ms`；`convert_us` n=190 p50 2,532 / p95 3,053 / max 8,260 µs（对比 probe9 的 43.54 ms 标量）。
- 产物：`rfvp.nro` 10,670,136 B sha256 `875336aa1efb0996abff222429bca80eaca0867fb648be1ed826eb5f9de39519`；`rfvp.elf` 20,397,352 B sha256 `9ff49413bd9e5d7e04a82375b24f31a722296dccec993878a228cbd265b9197f`；NSP v1.2.0-test 10,087,535,320 B sha256 `5bc45ace24a3b262ebbbbc09f74652921237bc6e65a01e1065a39ceb82d8b3e8`（verify 13 checks / 0 fail / 1 未签名 warn，romfs 166 项）。
- 补丁：`docs/builds/patches/rfvp-switch/P40-op-h264.diff` 41,286 B / 1,179 行 / 7 文件 sha256 `026e34c189a743a89300b1e74e4fdc6db393f73362dda6bb71019be59f04b491`（基准 `/e/galnx-build/p31/rfvp-v117`）。
- 限制：Citron 不能证明硬件路径（nvtegra HLE 首帧后 `AVERROR_UNKNOWN -1313558101`），真机 60 fps 待用户验收；硬帧仍走 `av_hwframe_transfer_data` 到 CPU（如需再省，下一步是 tiled 表面直绑 GLES 纹理 + shader YUV→RGB 的零拷贝）；H.264 只有 720p 单档，540/480/360 只对 WMV2 兜底有效。
- 记录：`docs/builds/046-op-h264-nvtegra.md`；证据 `docs/milestones/evidence/P40-op-h264/`。

### M5-af：P40b 修正 NV12 色度步进（v1.2.1-test）

- 症状（用户 m36342）：v1.2.0-test 真机 OP 不慢放但颜色错——「正常的黑白图层在底下，彩色图层在其上，但是彩色图层被巨幅拉伸」⇒ 亮度对、色度横向 2 倍拉伸。
- 根因：`platform/switch/runtime/rfvp_movie_color.c` 的 `nv12_row_neon()` 用 `uvr + (i >> 1)` / `uvr + (i >> 1) + 4` 读 NV12 交织 UV，每 16 像素只前进 8 字节；正确为 `uvr + i` / `uvr + i + 8`。只有真机硬件帧（`AV_PIX_FMT_NVTEGRA` → transfer 后 NV12）走这条 NEON 分支；Citron 强制软解走 planar 分支，故 046 的冒烟未发现。
- 修复：2 行代码 + 注释；全量解析见补丁 `P40b-nv12-color.diff`（226 行 / 4 文件 / sha256 `2904ab90…`，须在 `P40-op-h264.diff` 之后应用）。
- 影子测试（模拟器专用，默认关闭）：marker `sdmc:/switch/rfvp/h264_nv12_selftest.txt`；把软解 planar 帧按显示宽度重打包成 NV12，喂同一份硬件 kernel，与 planar kernel 的 RGBA 逐字节比较并打 FNV-1a 64 校验。
- Citron NRO 影子（run-citron-04）：103 条记录全 `match=1 diff_bytes=0`（frame 1…2940），`convert_us` p50 ≈ 2,544 µs。
- 构建：`bash /e/galnx-build/p40/build.sh` → NRO 10,670,136 B `b93f34e3…`、ELF 20,399,744 B `c9abd983…`。
- v1.2.1-test NSP：`E:/galnx-build/p40/out121/IROSEKA_FHD-010047420000a000.nsp` 10,087,536,344 B `16d4cee0…`；verify 13 checks / 0 fail / 1 未签名 warn；romfs 166 文件含 `movie/01_h264.mp4`。
- Citron NSP(romfs) 冒烟：窗口 `1.2.1-test`、24/24 步 ok、`Movie: opened (Switch NVDEC H.264)` 从 romfs 打开、109 条 shadow 全 match（frame 1…3120）、`convert_us` n=175 p50 2,530 p95 3,697 max 7,687 µs。
- 限制：硬件分支在模拟器不可达，本证据是「kernel 等价性 + 真机症状待验」的组合；影子测试按 stride=width 重打包，真机 `linesize[1]` padding 只能真机确认。
- 记录：`docs/builds/047-p40b-nv12-colour-fix.md`、`docs/builds/patches/rfvp-switch/P40b-nv12-color.diff`；证据 `docs/milestones/evidence/P41-op-nv12-color/`；计划 v1.36。
- 真机验收（v1.2.1-test，2026-11-09，用户 m36694）：「颜色正常，播放速度正常」⇒ P40b 修复在硬件 NV12 分支生效。设备日志（MTP 只读）`debug_report.txt` 101,342 B / 1,210 行：`Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4`、decoded 采样 124 行全 `hw=1`（`hw=0` 为 0）、`decode_us` 1,886–9,264 µs、`convert_us` ≈3.5 ms、`end of stream after 3597 frames (3597 hardware)`、OP 后 `frame 7620: 60.0 fps over the last 60 frames, slowest frame 26.0 ms`。
- 遗留（非 OP）：`perf_slow.log` 2,632,802 B / 10,563 行显示故事区既有慢帧（`save_finalize` 60–80 ms、`vfs_read`/`audio_cmds` 数秒级尖峰，如 frame 777 `4473.7 ms` 中 `vfs_read 2116.72`/`audio_cmds 1314.16`/`vm 3023.81`）；文件跨会话累积、无法按 OP 切分，后续取证前须先改名旧日志。
- 记录（验收）：`docs/builds/047-p40b-nv12-colour-fix.md` §9；证据 `docs/milestones/evidence/P42-op-h264-device/`；计划 v1.37。

### M5-ag：P40c OP 改回剧情触发并可跳过（v1.2.2-test）

- 症状（用户 m36793）：「现在的版本会在游戏开始时播放op且不可跳过」；OP 本身已不慢放、颜色正常（P40/P40b），问题只在触发点与可跳过性。
- 根因：P33 时代留下的调试通道 —— `crates/rfvp/src/no_std_core.rs:665-703` 的 tick 在 `horizon::debug_movie_requested()` 为真时调 `movie_play("movie/01.wmv", flag)`，`flag` 默认 `Variant::True`（modal，不可跳过）；`platform/switch/runtime/main.c:101-125` 从 `sdmc:/switch/rfvp/debug.txt` 的 `movie=1` 读该开关，设备上 debug.txt 长期是 `shot=900` + `movie=1`。游戏脚本本身支持剧情触发与跳过。
- 脚本侧事实（反编译 `iroseka.lua`）：`f_00034356`(:38572) 是 OP/ED 调度器，默认分支 `f_000426A7(1,nil)` 播 OP、`a1==10` 播 ED(2)；`f_000426A7`(:58131) 构造 `movie/NN.wmv` → `Movie(a0,nil)`，播片循环里 `InputGetState() & 3`（Ctrl/Shift）即 `MovieStop()`。调用者：`f_00033B33`/`f_00033BC0`/`f_00033E17`/`f_00033FC4`/`f_00034721`/`f_00067E15`。
- 修复（2 行代码 + 注释同步）：`main.c` 新增 `MovieDebugFile = "sdmc:/switch/rfvp/movie_debug.txt"` 与 `read_movie_debug_file()`，`rfvp_switch_debug_movie()`/`_nil()` 只读该文件；`debug.txt` 仅保留 `shot=`/debug_report 开关，不再触发影片。补丁 `P40c-op-story-trigger.diff` 103 行 / 3 文件（main.c + horizon.rs + no_std_core.rs）/ sha256 `06f92900…`，应用顺序 P40 → P40b → P40c。
- Citron NRO（run-05/run-06，标题 New Game 起步）：debug_report 969 / 1000 行里 **0 条 `MoviePlay`** ⇒ 启动不再自动播片（修复生效）；序章篇幅长，点击 13 次未到 OP 触发点。
- Citron NRO run-08（用户提供存档 DATA.005，m36982）：`MoviePlay: path=movie/01.wmv flag=Nil is_layer_effect=true` → `Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4` → decoded 1/2/3/4/5/30/…/390（pts 12979 ms）→ 按 R（Citron 键盘 E，hold 800 ms）后 `MovieStop`、无新 decoded 行 → 回正文（截图 step-16/18 为「从少女跳下的灯塔……」）。
- 构建：NRO 10,670,136 B `2666286e…`；ELF 20,400,232 B `258a312d…`。
- v1.2.2-test NSP：`E:/galnx-build/p40/out122/IROSEKA_FHD-010047420000a000.nsp` 10,087,536,344 B `51d0f8c7…`；`galnx package nsp verify` 13 checks / 0 fail / 1 未签名 warn；romfs 166 项 hardlink（含 `movie/01_h264.mp4` 108,361,267 B）。
- Citron NSP(romfs) 冒烟：`JUNCTION_PARKED` 后启动，18/18 步 ok，窗口标题 `1.2.2-test`；日志 `MoviePlay flag=Nil` → `Movie: opened (Switch NVDEC H.264)` 从 romfs 打开 → decoded 至 frame 450（pts 14981 ms）→ 按 R 后 `movie audio: stopped movie/01.ogg` 回正文；`history_set: unexpected value for set_voice/set_name : Nil` 为进消息层副作用（非致命）。
- 限制：Citron 无 NVDEC（`hw=0` 软解），真机硬解 + 跳过手感待验；**ED 未验证** —— iroseka 的 `movie/` 只有 `01.*`，`f_000426A7(2,nil)` 会失败并跳过，ED 路径等 moyu（`movie/02.wmv` 存在）同步时验证。
- 记录：`docs/builds/048-p40c-op-story-trigger.md`、`docs/builds/patches/rfvp-switch/P40c-op-story-trigger.diff`；证据 `docs/milestones/evidence/P43-op-story-trigger/`。
### M5-ah：もゆ标题粒子三处修复 + 调试播片序号（P41，v1.3.2-test / v1.2.4-test）

- 背景：用户 m38188 对比 PC 版与 NS 版《さくら、もゆ。》标题画面 —— PC 版背景有大量红色粒子全程向上飘动，NS 版完全没有；m38329 确认首轮修复后「出现少量粒子但仍远不及 PC」，m38555 要求说明方法与对比数据。
- 第一层根因：`Snow()` 把 arg10 按 arg9 的 flake 表上限校验（1..=1024），而 arg10 是每周期 Y 位移（速度量）；もゆ标题传 2000/2500 被拒，整次 `Snow()` 返回 Nil，粒子系统根本没建立。修复：arg10 范围放宽到 -65535..=65535。
- 第二层根因：`PrimSetSnow(id, mode, x, y)` 的 mode 是 snow slot（0/1），但 `graph.rs` 忽略它，而渲染器用 prim 的 texture_id 当 snow slot ⇒ 两个 snow prim 都画 motion 0（60 flake），motion 1 的 1024 flake 永不绘制。修复：`prim_set_snow` 把 mode 写入 `prim_set_texture_id`。
- 第三层根因：`SnowFlake.variant_idx` 生成 `base_tex + variant` 的 graph id，而标题只 `GraphLoad` 了 base 两张图（1592/1593），`variant_count=5` ⇒ 4/5 flake 因贴图未上传被 `continue` 丢弃（1024 里只画约 205）。修复：`emit_snow()` 在变体图缺失/未上传时回退 base 贴图。
- 量化（Citron 标题截图间隔 3 s 的时序差分，区域 x=40..0.45W / y=40..0.60H，灰度差 >25，每万像素）：修复前 1.10 → 双 slot 修复 5.56 → 变体回退 39.49；清插桩后的干净构建 32.84，1.3.1-test NSP(romfs) 33.19。干净构建 `debug_report.txt` 里 `snow:` 报错 0 行、`snow_id=1 count=1024 drawn=1024`。
- 附带调试通道：`movie_debug.txt` 新增 `movie=N`/`index=N` 指定调试播片序号（`no_std_core.rs` 钩子拼 `movie/{index:02}.wmv`），Citron 用 `index=2` 验证 `movie/02_h264.mp4`；结论：`movie/02` 是**真結局 OP**（用户 m38780 确认），不是 ED —— 游戏 `movie/` 只有 01/02 两个视频，ED 应为脚本演出。另加 `skip=1` 自测通道（强制输入层按住 R = Ctrl），只在标记文件存在时生效，发布版不创建。
- 产物：`rfvp.elf` 20,406,336 B sha256 `0a24d18c926b6d652a074b1d51eca48fa4396a2e8dc15167cc8603ddb03f71ee`、`rfvp.nro` sha256 `4ee6f67d956abca60c677386b4f363a055ba242e9134737d3e859ec82a54052b`。
- NSP：SAKURA MOYU CN v1.3.2-test（010047420000c200）8,116,836,056 B sha256 `8df0d39823ec14082187c94b56a9142ce151e499d59d5604fc73bcebe2dfafef`；IROSEKA FHD v1.2.4-test（010047420000a000）10,087,536,344 B sha256 `8b12f57fa5938f9c5c5b6c0f27d39500d214bdf533e4d262c2d09da6c0b6e44a`。两枚均 `galnx package nsp verify` 13 checks / 0 fail / 1 未签名 warn。
- 补丁：`docs/builds/patches/rfvp-switch/P41-snow-particles.diff` 232 行 / 7 文件 / +116 −22 / sha256 `4cbb337b273e92de06ebbce60f626c1b7028ddea0bfd1f232704df6104aee3ea`；应用顺序 P40 → P40b → P40c → P41（roundtrip 校验通过）。
- 记录：`docs/builds/049-p41-snow-particles.md`；证据 `docs/milestones/evidence/P44-snow-particles/`。
- 限制：变体语义未证实（脚本只加载 base 图，当前按独立 graph id 处理并回退）；粒子运动速度未对齐 PC（用户 m38513 明确不追速度）；真机粒子观感与 ED 行为待用户验收。
### 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-30 | M5-b 汇总：五条验收逐条判定、结论「继续研究（P3）」、与正式适配的差距 5 条、遗留 U1–U11、新增工具记录；M5 里程碑定稿 |
| 2026-10-31 | M5-c：rfvp SDL2/GLES2 渲染后端（P9）——Citron 17–19 fps → 60.0 fps、中文正文渲染正确；patch/016/P9a 证据入库；build_backend 新增 custom-script |
| 2026-10-31 | M5-d：手柄输入与快捷存读档（P10）——基线映射实测 6 项成立；patch J 补 QuickSave/QuickLoad + pending 请求兜底 + 右摇杆滚轮 + 光标加速；证据 P10-rfvp-input / 017 |
| 2026-10-31 | M5-e：自包含 NSP（P11）——游戏数据 romfs 打包，NSP 9,979,435,224 B；Citron 在 SD 无数据时从 `romfs:/game` 启动并显示中文正文；NRO 回归 PASS；`galnx package nsp verify` 12 checks（1 warn = 未签名）；patch/018/P11 证据入库；真机待装 |
| 2026-10-31 | M5-f：手柄映射重写（P12）——`event.rs` 按用户映射表整体重写（A=Enter/B=Esc/X=AUTO/Y=LOAD/+=SAVE/−=EXIT+确认/ZR·ZL=左右键/R=Ctrl/D-Pad/双摇杆），菜单用实测锚点宏复用游戏原生 UI；Citron 逐项验证 11/12 项（R=Ctrl 跳读未复现，U1）；NSP v1.0.1 9,979,435,736 B `0fda623c…` 重新打包 + verify PASS；patch/019/P12 证据入库 |
| 2026-10-31 | M5-h：真机掉帧修复（P14）——prev-frame 由 CPU 每帧回读改为 GPU 双离屏 target、编译掉 debug_screen.bmp 周期回读、顶点批处理与宿主计时；同探针 slow 行 154→19、thumb≥20 ms 帧 142→0；NSP v1.0.3 9,979,441,368 B `b9e0d6a5…`，Citron NSP 冒烟 PASS，真机待复验 |
| 2026-10-31 | M5-g：真机四项缺陷修复（P13）——主机层 SDL overlay 光标 + `QUIT GAME?` 确认框、纹理 scratch 复用（60 fps / render 15.75 ms）、`no_std_core` 消费 ExitDialog/ExitMode(3) 走引擎正常关闭；NSP v1.0.2 9,979,437,784 B `ff259aa4…`，Citron NRO/NSP 双形态 PASS，真机 V1–V14 待复验 |
| 2026-11-01 | M5-i：逐句存档卡顿修复（P16）——rFVP 每句 2 次 `SaveCreate(3)` 会各编码 10.27 MB 快照（motion 99.8%，`encode_ms≈100`）后丢弃；改为 `PendingPrepare` 惰性编码、只在 `try_commit` 落盘前 materialize，并删掉诊断用 4 次额外 encode、缩略图改 GPU 小 target 下采样。Citron 复现同一复杂存档：逐句 save 阶段 112–135 ms → **5.27–5.67 ms**，缩略图 10–12 → 1.03–2.16 ms，系统档 materialize+commit 仍 PASS；NRO `3aff4de3…` / ELF `9adc739f…`，patch `941f9504…` + 全量 `626e7aa9…`，NSP v1.0.4 已构建，真机待复验 |
| 2026-11-01 | M5-j：资源缓存/启动预读/zlib inflate（P17）——新增进程级 LRU 三缓存（textures 160/parts 48/bytes 192 MiB）与 5 处接线、启动预读 66 张 `graph/*` UI 图集、像素转换块拷贝、devkitPro zlib 替换 miniz；Citron 重复打开 ESC 菜单两次截图逐字节相同且无解码慢帧（`graph cache hit` 193 / `vfs cache hit` 106），66 张 inflate 204.4→133.7 ms（1.53×）；首次加载大 CG 仍有 0.1–0.8 s；NRO `331e0a25…` / ELF `0c216c9b…`，patch `8b97c147…` + 全量 `6930bb65…`，NSP v1.0.5 待真机复验 |
| 2026-11-01 | M5-k：大图异步解码 + 读档异步 restore（P18）——新增 `async_decode` 队列（大图 ≥1 MiB 交 worker、主线程保留旧图、每帧 apply）、restore 的 `apply_snapshot_v1` 走同一队列、宿主 `threadCreate` 解码线程；CG 入口慢帧 632.2→299.1→**273.4 ms**（p18-k，异步 apply 6 次、0 exception）；放弃「大图 return Nil」与 libdeflate 两条路线；NRO `796679ce…` / ELF `741b92ea…`，patch `7c0c1367…` + 全量 `5c012b7a…`，NSP v1.0.6 真机待复验 |
| 2026-11-01 | M5-l：异步解码运行时开关（P19）——P18 worker 线程无条件创建且未检查返回值，真机上大图 `return Nil` 后永久空白 → 黑屏（Citron 无法复现）；改为运行时开关默认关闭 + `async_status.txt` 落盘 + 失败自动回落同步解码（等价 v1.0.5）。Citron NRO 冒烟 PASS（nonblack 0.9018、exception 0、`enabled=0`）；NRO `a6efe53b…` / ELF `98c6464b…`，patch `rfvp-async-toggle.patch` 6,988 B / 189 行 `6bdc0a61…` + 全量 194,079 B / 4,968 行 `d0a5d090…`，NSP v1.0.7 待真机复验 |
| 2026-11-01 | M5-m：异步解码阶段诊断 + 看门狗自愈（P20）——真机 async=on 会话 `enabled=1 create=0x0 start=0x0 hb=4` 后 60 帧内整进程冻结（无 crash report、无 last_error），判定为挂起；新增 `report_stage`/`watchdog_stalled`（3 s）+`drain_inline` 自愈、`async_status.txt` 带 `stage=`、worker 栈 1 MiB；Citron async=on 冒烟 PASS（hb=77000、stage=0、30 条 async 日志）；真机 crash_reports 取证确认两份报告属 LibAppletOf / hbloader·sphaira，与本项目无关；NRO `d16fc0d3…`、patch 10,494 B / 280 行 `3613a6db…`、全量 198,586 B / 5,082 行 `19720846…`，NSP v1.0.8 经 MTP 上传真机 `/switch/galnx-nsp/`（`ExtendedProperty('System.Size')`=9,979,496,664 与本地字节数一致，约 10 min），详见 `docs/builds/026` |
| 2026-11-05 | M5-n：async 强制关闭 + 帧心跳（P21）——`read_async_enabled()` 恒 0、忽略 `async.txt`，新增 opt-in `frame_status.txt`；真机黑屏定位为 async 路径整进程冻结（看门狗结构性失效），根因报告归档；NSP v1.0.9 9,979,495,640 B `726bb2d1…`，Citron 冒烟 PASS（`enabled=0`、frame=4290），真机待复验 |
| 2026-11-05 | M5-p 真机**未通过**：机制不冻结（`enabled=1 cpu=1 wdt=1 stalled=0`）但 CG 不显示/UI 残留/OP 跳过，根因=延迟绘制语义与逐帧重画不兼容，已回退 v1.0.9，改 P25 prefetch-only；见 `docs/experiments/rfvp-async-device-defect.md` |
| 2026-11-05 | M5-p：async 并发修复（v1.1.0-test）——pack 读锁换 libnx 睡眠互斥（优先级继承）、worker 换核 cpuid=1、独立看门狗线程（3 s 状态 / 10 s 自动关）、resource_cache 临界区去 log/drop；Citron 73/73 步 19,200 帧 `stage=0 cpu=1 wdt=1 stalled=0`，10.6 min 长跑不冻结；测试 NSP 9,979,498,200 B `753082b7…`、补丁 `203d936d…`；真机确认后推送 |
| 2026-11-05 | M5-q：Sakura 中文 NSP（v1.0.1 / v1.0.2）——`patch.dat` 57,172 条经 hcb 字节码原位重打包（ThreadStart 指针 phase2b 99/99）+ `nls=gbk`，v1.0.1 剧情中文 `91ad7b96…`；v1.0.2 再叠加 60 条 patch.bin UI 贴图覆盖，标题 logo 中文化 `5708da95…`，verify 12 checks，Citron 冒烟 11/11 步 |
| 2026-11-05 | M5-r：真机残余卡顿画像（perf-02）——13 次运行 1079 慢帧；写盘 save p50 89.98 ms、vfs_read p90 1235.88、graph_decode p50 159.37、audio_cmds >100 ms 34 帧；根因含 Switch 未实现 `load_stream` 致主线程整条音频读解码、GPU 缩略图快路径未生效；P24 task-51 承接 |

| 2026-11-05 | M5-o：さくら、もゆ。720p 自包含 NSP（P22）——720p 基线 60.0 FPS / slowest 18.0 ms，慢帧全一次性 → NS 算力非瓶颈、资源压缩降备选；`nls=sjis` 必需；NSP 1.0.0 7,990,691,032 B `d2d42783…`，verify 12 checks，Citron 首启/正文 PASS |
| 2026-11-05 | M5-s：async 返工为 prefetch-only（P25，v1.1.1-test）——删除「大图 submit 后返回 Nil」的延迟绘制路径，命中即用/未命中同步 decode（预取最多等 300 ms），队列 path 去重 + on-demand 优先；Citron 152/152 步 + Lead 独立读档→CG PASS（`enabled=1 hb=105000 stage=0 cpu=1 wdt=1 stalled=0`）；NSP 9,979,496,152 B `bf83fa6e…`、补丁 `295ee725…`；OP 跳过=no_std 无 movie 解码器（另立项）；真机三项验收通过前不推送 |
| 2026-11-05 | M5-t：rfvp 音频流式与缓存预算（P24，v1.0.10-test2）——Switch 后端实现 `load_stream` 流式回调，消除 `flush_audio` 主线程整读回退；同内容帧 audio_cmds 335.17→21.34 ms、>100 ms 音频帧 2→0；vfs（+8.8%）、写盘、纹理缓存三项未达成/未验证；NSP 9,979,497,176 B `79aedc03…`、补丁 `9418d20f…`；记录 `docs/builds/030-rfvp-perf.md` |
| 2026-11-07 | M5-v：音频连续性（P27）——`audio_pump()` 仅主线程每帧一次 + 6×1024 帧≈128 ms 缓冲导致长帧断流；改为 3.07 s SPSC ring（147,456 帧）+ 独立音频线程（prio 0x2D/cpu{2,1,-2}）+ `stall` 注入 + `audio_status/audio_stall` 落盘；Citron 注入 3×1.2 s 停顿 `underrun=0`、三对 pre(147456)→post(90112/90112/89088)、60 FPS，NSP v1.1.3-test `eaea4446…`；真机听感待验 |
| 2026-11-07 | M5-w：场景切换过渡动画（P28）——hcb 转场 100% 为 Dissolve 家族，但 no_std 渲染未把上一帧作为 mask 快照 → 硬切；补 `capture_thumbnail`→`set_mask_snapshot`（4 文件 +31/−2）；CPU harness `mask_phase=188`、Citron GPU 抓到 4–5 帧白场渐变与 CG 双重曝光；合并 NSP v1.1.4-test `444af465…`；真机待验 |
| 2026-11-07 | M5-x：音频 JIT（P30，v1.1.6-test）——v1.1.4-test 真机「音频约 3 秒延迟」根因=P27 的 3.07 s 预渲染 ring 稳态填满；改为音频线程按需 apply+mix（延迟回落 ≈128 ms），Citron 注入 3×1.2 s 停顿 `lag_ms=-101 underrun=0`、rendered 每次推进 ≈1195 ms；NSP 9,979,505,368 B `d7eb77ec…`、补丁 `e81cd49c…`；真机待验 |
| 2026-11-07 | M5-y：OP 影片播放（P31+P32，v1.1.7-test）——no_std 接入 720p30 WMV 软解（每 tick 1 帧、按 pts 丢落后帧）与同名 OGG 音轨（`AudioStreamId::MOVIE=0x2000` → `AudioSlotKind::Movie`，走 P30 JIT 音频线程）；Citron NRO 22 步 + Lead 独立 NSP 36/36 步双 PASS（decoded/presented 109、`lag_ms=-102 underrun=0`、18 张截图互异）；NSP 9,861,393,624 B `cb019f27…`、补丁 `95abafc8…` + `9e429779…`；Citron 仅 15 FPS → OP 慢放，真机实时性待验 |
| 2026-11-08 | M5-z：OP 分档播放（P33，v1.1.9-test）——romfs 内嵌 4 档 OP 变体（720/540/480/360，视频合计 240,254,552 B）+ `video.txt` 选档（缺省 480、变体缺失回退原片）+ 原生尺寸转换（不再上采样 1080p）+ spare RGBA buffer 复用 + 宿主微秒计时 + `movie=nil` 调试；Citron NSP 36/36 步 PASS（`01_q480 level=2`、854×480、2880 帧 / 119,958 ms 播完、`lag_ms=-108 underrun=0`），桌面 decode 8.4–15.1 + convert 3.0–5.8 ms/帧；NSP 9,977,492,184 B `bd909c1e…`、补丁 `76e2f12d…`；真机档位待验 |
| 2026-11-08 | M5-aa：WMV2 左缘马赛克修复（P34，v1.1.10-test）——真机 OP 最左侧一列马赛克根因=854 宽（非 16 对齐）末列宏块 IDCT 写循环无行守卫、越界字节按 stride 折返污染下一行行首；改 coded 864×480 解码 + 可见尺寸裁剪；宿主 oracle 左 12 列均值 63.35→3.36、>32 像素 6,777→30、行首复写 29/58→0/0；Citron 左缘干净、decode_us 8.1–15.2；NSP v1.1.10-test `fc35fa98…`；真机待用户复验 |
| 2026-11-08 | M5-ab：NVDEC 硬解探针（probe1–4，P35/P36）——probe1 真机 NVDEC 可开（VC-1 max_mbs=8192）、probe2/3 Citron 链路 PASS；**probe3 真机 = 解码 1.67 ms/帧但 CE tiled→linear 20 s/帧且绿屏**；据此 pivot 到 probe4「fence 等待 + CPU 直读 block-linear + 软解 PSNR 标定布局」（12 组候选），NRO `b5acc4de…`，Citron 链路级 PASS（hw=0，hw 分支仅真机可验），真机测试包 v4 待用户运行 |
| 2026-11-08 | M5-ac：NVDEC 探针 probe5/6（P37/P38）——probe5 复刻 envideo 官方参考测试，**真机 Phase A PASS**（`mbs_ok=64 cycles=5042`、哈希 = 官方 `a2c4a330592602d5`）⇒ 硬件/CE/tiling 全排除；Phase B（FFmpeg envideo VC-1）仍 FAIL（`AVERROR_UNKNOWN`）⇒ 失败域收缩到 envideo 封装层。改用 averne/FFmpeg **nvtegra**（probe6，NRO `92e1796a…`），Citron 仅软解可验（`hw=0`），真机包 v6 待用户回传 |
| 2026-11-08 | M5-ac 附：probe6 构建坑修正（`__SWITCH__` + `-isystem /opt/devkitpro/libnx/include`）、`frame_index` 改显示序、片头白帧经 PC ffmpeg 对照排除；文档 `043`/`044`、`docs/research/nvdec-probe5`/`probe6`、证据 `P37`/`P38` 入库；计划提升到 v1.33 |
| 2026-11-09 | M5-ad：NVDEC 探针 probe9（P39）——**真机 NVDEC 硬解 + CE 传输全链路可用**：decode 0.44 ms/帧（297.80 fps）、av_hwframe_transfer_data 3.79 ms/帧（C1 170.29 fps）；**慢放真因 = CPU NV12→RGBA 43.54 ms/帧**（C2 5.50 fps）、upload 6.46–8.16、render 2.44；probe8 的 10.77 fps 系日志污染（4.9 MB/70,478 行）作废；结论：movie player 去 CPU RGBA，改 NV12 双平面 GLES2 shader（预算 ~10.7 ms/帧） |
| 2026-11-09 | M5-ad 附：H.264 交叉验证 332.98 fps 排除「VC-1 解码慢」；NRO 9708465d…；文档 045、docs/research/nvdec-probe9、证据 P39 入库；计划提升到 v1.34 |
| 2026-11-09 | M5-ae：OP 换 H.264 + NVDEC(nvtegra) 硬解接入（P40，v1.2.0-test）——WMV2 无硬解 ⇒ OP 重编码 H.264 High/4.0/crf18（显式 BT.709，108,361,267 B `bddf82fc…`）；新增 `rfvp_movie_h264.c`（FFmpeg+nvtegra，硬帧 transfer 得 NV12）+ `rfvp_movie_color.c`（NEON BT.709 NV12→RGBA）+ `horizon_h264.rs`（`MovieSource`，失败回落 WMV2）；Citron NRO/NSP(romfs) 双冒烟各 3597 帧 EOS、convert p50 2.52–2.53 ms（对比标量 43.54 ms）；NSP 10,087,535,320 B `5bc45ace…`、补丁 `026e34c1…`；真机 60 fps 待验 |
| 2026-11-09 | M5-ae 附：构建坑（FFmpeg 生成头在 build 目录需双 `-I`、`rfvp_movie_color.c` 缺 `<stddef.h>`）、`file:` 协议前缀、Citron force-software 标记 `h264_sw.txt`；文档 046、证据 P40 入库；计划提升到 v1.35 |
| 2026-11-09 | M5-af：P40b 修正 NV12 色度步进（v1.2.1-test）——真机 OP 颜色错（亮度对、色度横向 2 倍拉伸，m36342）根因 = `nv12_row_neon()` 用 `uvr + (i >> 1)` 每 16 像素只前进 8 个交织 UV 字节；修为 `uvr + i` / `uvr + i + 8`（仅真机硬件 NV12 分支，Citron 软解遮蔽）；新增模拟器影子比较（planar→NV12 重打包 + 逐字节比 + FNV-1a 64，默认关闭），Citron NRO 103 条 / NSP(romfs) 109 条全 `match=1 diff_bytes=0`；NRO `b93f34e3…`、NSP 10,087,536,344 B `16d4cee0…`、补丁 `2904ab90…`；真机颜色待验 |
| 2026-11-09 | M5-af 附：Citron 冒烟只能覆盖软解 planar 分支（硬件分支不可达），因此用「影子等价性测试」兜底；文档 047、补丁 P40b、证据 P41 入库；计划提升到 v1.36 |
| 2026-11-09 | M5-af 真机验收 PASS（v1.2.1-test）：用户 m36694「颜色正常，播放速度正常」；设备日志 decoded 124/124 `hw=1`、`decode_us` 1.8–9.3 ms、`convert_us` ≈3.5 ms、`end of stream after 3597 frames (3597 hardware)`、OP 后 `frame 7620: 60.0 fps`；证据 P42 入库；OP 里程碑关闭，零拷贝/1080p 降为可选优化（计划 v1.37） |
| 2026-11-09 | M5-af 附：`perf_slow.log`（2,632,802 B / 10,563 行）确认故事区仍有既有慢帧（非 OP），跨会话累积无法切分 ⇒ 作为下一任务候选，取证前先改名旧日志 |
| 2026-11-09 | M5-ag：P40c OP 改回剧情触发并可跳过（v1.2.2-test）——v1.2.1-test 启动即播 modal OP（用户 m36793），根因 = P33 调试通道 `no_std_core.rs:665-703` + `main.c:101-125` 读 `debug.txt` 的 `movie=1`（默认 `Variant::True`）；修法：强制播片只认新的 `sdmc:/switch/rfvp/movie_debug.txt`，`debug.txt` 仅留 `shot=`；Citron NRO run-05/06 启动 0 条 `MoviePlay`、run-08 存档点触发（`MoviePlay flag=Nil`）+ 按 R `MovieStop` 回正文；NRO `2666286e…`、ELF `258a312d…`、NSP 10,087,536,344 B `51d0f8c7…`（verify 13/0 fail/1 warn）、NSP(romfs) 冒烟 18/18 步 ok；ED 未验（iroseka 无 `movie/02.*`） |
| 2026-11-09 | M5-ag 附：`docs/builds/048`、补丁 `P40c-op-story-trigger.diff`（103 行 / 3 文件 / `06f92900…`）、证据 P43 入库；计划提升到 v1.38 |
| 2026-11-10 | M5-ah：もゆ标题粒子三处修复（P41，v1.3.2-test / v1.2.4-test）——PC 版有大量红色上升粒子、NS 版全无（m38188/m38329/m38555）；三层根因 = `Snow()` arg10 按 flake 上限误拒（2000/2500 被拦 → 整次返回 Nil）、`PrimSetSnow` 的 mode 未存成 snow slot（两套都画 motion 0）、`base_tex + variant` 变体贴图未加载丢弃 4/5 flake；修复后 1024/1024 全部绘制、`snow:` 报错 0 行；时序差分 1.10 → 5.56 → 39.49（干净构建 32.84、NSP 33.19）；补丁 `P41-snow-particles.diff` 232 行 / 7 文件 / `4cbb337b…` |
| 2026-11-10 | M5-ah 附：`movie_debug.txt` 支持 `movie=N`/`index=N` 调试播片序号（Citron 验证 `movie/02_h264.mp4`）；确认 `movie/02` 是真結局 OP 而非 ED（游戏只有 01/02 两个视频，ED 为脚本演出）；`skip=1` 自测通道仅在标记文件存在时生效；记录 049 与证据 P44 入库，计划推进 v1.39 |
| 2026-11-10 | M5-ai：GLES2 双平面零拷贝（P44，v1.4.1-test）——H.264 电影路径把解码器 NV12 双平面经 `SDL_UpdateNVTexture` 直传 GPU（GLES2 NV12 BT.709 shader 做 YUV→RGB），不再 CPU 转 RGBA；13 文件 / +446−24、补丁 `rfvp-nv12-zerocopy.patch`（`afbf3fb0…`）；Citron A/B 1080p：CPU 转换 9.25→1.81 ms、上传 6.75→2.72 ms（8.29→3.11 MB，1.5 B/px），单帧省 ~9.5 ms；NSP v1.4.1（romfs 6,718,475,156 B / 141 文件）6,738,209,496 B `db31a312…`、verify 13 checks、冒烟 `upload=nv12` + 中文标题 + 1080p OP；文档 051、证据 P44 入库；真机待用户验收 |
| 2026-11-11 | M5-aj：P45 同步（IROSEKA v1.2.5-test / MOYU v1.3.3-test）——把 P44 的 NV12 零拷贝引擎（ELF `296b198c…`）重新打进两个既有试点包，并换成用户自制封面（icon dat 26,706 B `f35ac156…` / 25,886 B `12ea3a07…`，与 `examples/pilot02|03/icon-256.jpg` 逐字节相同）；IROSEKA 10,087,541,464 B `f6860842…`（romfs 10,038,390,763 B/166 文件）、MOYU 8,116,841,176 B `965ee356…`（romfs 8,094,409,871 B/81 文件）；两包 verify 13/12 checks 0 fail（唯一 warn 为未签名预期），Citron 首启窗口 1.2.5-test / 1.3.3-test、中文标题画面 PASS；文档 052、证据 P45 入库；真机待用户验收 |
