# 019 — rfvp 手柄映射重写（P12）

| 项 | 值 |
| --- | --- |
| 对象 | rfvp（IROSEKA_FHD「五彩斑斓的世界 HD Re:GENERATION」）HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`（MPL-2.0） |
| 增量补丁 | `docs/builds/patches/rfvp-switch/rfvp-input-remap.patch` — 413 行 / 1 文件 +264 −56，SHA-256 `44fd0722a23479108c51e03efeea127385948888f0d12d35a9178127a343ecef2`；应用顺序 sd2 → input → romfs → input-remap |
| 全量对照 | `docs/builds/patches/rfvp-switch/rfvp-full.diff` — 68,536 B / 9 文件 +1278 −173，SHA-256 `026a7cee248decd8f60d1394383d63eb6c11fdada81837541a8e43f93553ff29` |
| 产物（NRO） | `E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro` — 7,839,800 B SHA-256 `093ad9e0b5130ff728b23928bf0d92d002f9ede16acdbca18bbe9eb55fed66f6`（不进仓库） |
| 产物（ELF） | 17,046,880 B SHA-256 `0bfc77e1617c05a390161643b5652f86d0dc2c3c4cfea41d051d734030ad4c1d` |
| 产物（NSP） | `E:/galnx-build/p11/out/IROSEKA_FHD-010047420000a000.nsp` — 9,979,435,736 B SHA-256 `0fda623c37dc8664492341d00a103eaf606eb1a88583f0101508cefd39467419`，version 1.0.1，Title ID `010047420000A000` |
| 证据 | `docs/milestones/evidence/P12-rfvp-input/`（15 张 PNG + 2 个 input-steps 日志 + SHA256SUMS） |
| 结论 | Citron 级逐项通过（用户 m18283 的 12 项映射全部实测）；R=Ctrl 的跳读效果未在模拟器复现（U1），真机复验；NSP 已 v1.0.1 重新打包并通过 `galnx package nsp verify` |

## 1. 用户需求（m18283）

真机试玩 P11 后用户给出最终映射表（原话要点）：A=Enter；B=Esc（游戏里应打开暂停菜单）；X=自动模式；Y=读档；ZR=左键（按住=左键按住）；ZL=右键（按住=右键按住，点击=隐藏对话框）；R=Ctrl（按住持续快进）；方向键=键盘方向键；左摇杆上下=滚轮（上=backlog/文字回看，下=下一句）；右摇杆=鼠标光标；+=存档；-=退出。同时报告 4 个 bug：① 无鼠标光标 ② ZR/ZL/R 都触发 Ctrl ③ `+` 未显示确认框直接退出 ④ 方向键既走方向又移光标。

## 2. 上游基线：为什么必须重写 `event.rs`

上游 `platform/switch/host/src/event.rs`（由上游 commit `c4240ad` 带入，P10 已核对）把整套映射写死：

- `KEYS` 只有 8 项：`(UP,Up)(DOWN,Down)(LEFT,Left)(RIGHT,Right)(MINUS,Escape)(X,Return)(Y,Space)(L|R|ZL|ZR,Control)` —— 即 **ZR/ZL/R 全部发 Ctrl**、X 发 Enter、Y 发 Space（bug ②）。
- `PLUS` 按下置 pending_quit，松开时若期间没按 ZR/ZL 就发 `RfvpEvent::Quit` —— **`+` 直接退出，没有游戏内确认框**（bug ③）。
- 方向键既发 `Up/Down/Left/Right`，又在 `move_cursor()` 里每 poll 移动虚拟指针 12 px（bug ④）。
- 光标只能靠方向键/左摇杆移动，没有「右摇杆=鼠标」；且指针没有可见的鼠标图形（bug ①）。
- 引擎的 `exit_confirm_ui.rs` / `legacy_save_load_ui.rs` 只在 winit（std）路径编译，Switch no_std 端没有现成 UI，因此「存档/读档/退出」只能复用游戏自己的界面。

## 3. 实现（`platform/switch/host/src/event.rs`，404 行）

### 3.1 常量与按键映射

| 常量 | 值 | 用途 |
| --- | --- | --- |
| `SCREEN_WIDTH/HEIGHT` | 1280 / 720 | 指针坐标空间 |
| `STICK_DEADZONE` | 8000 | 左右摇杆死区 |
| `POINTER_DIVISOR` | 3000 | 右摇杆满偏 ≈ 11 px/poll（旧左摇杆为 6000，减半提速） |
| `WHEEL_STEP` / `WHEEL_REPEAT_POLLS` | 120 / 6 | 左摇杆纵向滚轮：首个 poll 立即发，之后每 6 poll 重复 |
| `MENU_SAVE` | (1117,171) | 暂停菜单 SAVE 实测锚点 |
| `MENU_LOAD` | (960,217) | 暂停菜单 LOAD |
| `MENU_EXIT` | (654,608) | 暂停菜单 EXIT |
| `EXIT_CONFIRM` | (560,379) | 退出确认框「确定」 |
| `TOOLBAR_AUTO` | (1079,700) | 正文工具栏 AUTO 图标 |

绑定（libnx 位 → 动作）：

| 物理键 | 行为 |
| --- | --- |
| A | `KeyDown/Up(Return)` |
| B | `KeyDown/Up(Escape)` |
| 方向键 | `KeyDown/Up(Up/Down/Left/Right)`（不再移动指针） |
| R | `KeyDown/Up(Control)`（按住=持续按住；L 预留） |
| ZR | `PointerDown/Up(Left)` 于当前指针位置（按住=左键按住） |
| ZL | `PointerDown/Up(Right)` |
| 右摇杆 | `PointerMove`，钳制在 1280×720 内 |
| 左摇杆纵向 | `Wheel{delta_y: ±120}`（上=+120=backlog） |
| X | 宏：点 `TOOLBAR_AUTO`（开关 AUTO） |
| Y | 宏：Esc 开菜单 → 点 `MENU_LOAD` |
| PLUS | 宏：Esc 开菜单 → 点 `MENU_SAVE` |
| MINUS | 宏：Esc 开菜单 → 点 `MENU_EXIT` → 点 `EXIT_CONFIRM` |
| 触摸 | 原样转发（PointerMove/Down/Up + 左键） |

### 3.2 菜单宏（`MenuMacro` 阶段机）

```rust
struct MenuMacro { x: i32, y: i32, stage: u8, waits: u8, open_menu: bool, click2: Option<(i32, i32)> }
```

- stage 0：`open_menu` 时 `key_down(Escape)`（触发暂停菜单），否则直接进入移动；
- stage 1：`key_up(Escape)` 后等 **90 poll（≈1.5 s）** 等菜单淡入完成（早期版本只等 15 poll，点击被吞，p12-h 复现）；
- stage 2：`pointer_move(x, y)` 并等 3 poll；
- stage 3：`PointerDown(Left)` 等 3 poll；stage 4：`PointerUp`；
- `click2` 存在时：再等 30 poll，然后重复「移动 → 按下 → 抬起」点击第二个锚点（用于 EXIT → 确定）。

所有锚点都是 1280×720 游戏坐标，通过 Citron 悬停扫描（p12-f 的 12 点探针 + 亮帧高亮/tooltip 判读）测得；换算公式 `gx=(px-112)/1.175`、`gy=(py-117)/1.175`（Citron 窗口 1728×1016，内容区 (112,117)-(1616,963)）。

## 4. 与上游差异 / 构建

- 只改 1 个文件：`platform/switch/host/src/event.rs`（+264 −56）；不触碰游戏数据、不注入 TJS，全部走引擎既有事件（`RfvpEvent::{KeyDown,KeyUp,PointerMove,PointerDown,PointerUp,Wheel}`）。
- 构建（复用 016 的 wrapper）：`env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m5-switch-build3.sh'`，产物 `E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro`，ELF 在 `target/rfvp-switch-runtime/rfvp.elf`。
- NSP 重打包（`scripts/build_nsp_game.sh`，必须显式给工具路径，否则报 `--hacbrewpack is required`）：

```bash
bash scripts/build_nsp_game.sh --elf /e/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.elf \
  --game-dir /e/galnx-build/m5-rfvp-run/game --title-id 010047420000a000 \
  --name "IROSEKA FHD" --author GalNX --version 1.0.1 --icon /e/galnx-build/p11/icon-256.jpg \
  --keyset "/e/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys" \
  --hacbrewpack /e/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c/hacbrewpack.exe \
  --nstool /e/galnx-build/m3-tools/nstool.exe --romfs-mode hardlink --work /e/galnx-build/p11/work-input2 \
  --out /e/galnx-build/p11/out/IROSEKA_FHD-010047420000a000.nsp
```

## 5. Citron 逐项验证

运行姿势：`"D:/Scoop/apps/git/current/bin/bash.exe" -c 'export CITRON_USER_DIR="C:/Users/<user>/AppData/Roaming/citron"; export TEMP=/c/Users/ACETaffy/AppData/Local/Temp; bash <脚本>'`，脚本内调 `scripts/citron_run.sh --nro <nro> --detach --timeout 400 --settle 8 --out <dir> --input-steps "..."`，run dir 出现 `.done` 即结束。Citron 键盘→手柄映射：C=pad A、X=pad B、V=pad X、Z=pad Y、Q=L、E=R、R=ZL、T=ZR、M=Plus、N=Minus、方向键=dpad、WASD=lstick、IJKL=rstick。

| # | 项 | 期望 | 证据（run / 文件 / SHA-256 前 8） | 结论 |
| --- | --- | --- | --- | --- |
| 1 | A=Enter | 完成打字 + 推进场景 | p12-p `p2-after-A` a43a8c3e → `p3-after-A2` e07ccf12；p12-d d3 | ✅ |
| 2 | B=Esc | 打开游戏暂停菜单 | p12-g g3/g4、p12-h h5 (927606 B ba34c919) | ✅（Esc 关不掉，见 U2） |
| 3 | ZL=右键 | 关闭暂停菜单回到正文 | p12-h h6 c170f65c | ✅ |
| 4 | ZR=左键 | 正文推进（新行开始打字） | p12-o `o3` c092f856 → `o4` 79fb10d0 | ✅ |
| 5 | 方向键 | 键盘方向键（backlog 滚动） | p12-d d5 732f6f0b、d6 499a4bfe | ✅ |
| 6 | 左摇杆上下 | 滚轮：上开 BACKLOG | p12-d d4 591f08bd、p12-n | ✅（下=下一句同样由 Wheel 负值驱动） |
| 7 | 右摇杆 | 指针移动（游戏自绘青色菱形光标） | p12-f f3 c207b5cf / f4 be310cd0、p12-d d2 | ✅ |
| 8 | X=AUTO | 工具栏 AUTO 打开，出现进度条+「自动播放」 | p12-n n4 0393ca37、p12-h h3 84c3e834 | ✅ |
| 9 | Y=读档 | 打开 FILE LOAD 面板 | p12-i i3 15088646 | ✅ |
| 10 | PLUS=存档 | 打开 FILE SAVE 面板 | p12-i i2 d4b0b705 | ✅ |
| 11 | MINUS=退出 | 暂停菜单 EXIT → 中文确认框 → 干净退出（全黑、0 异常） | p12-g g10 39316cba（确认框）、p12-i i5 3f87a15f（70,697 B 全黑） | ✅ |
| 12 | R=Ctrl | 按住连续快进 | p12-j/k/l/o 多轮：只前进一句，未连续跳读 | ⚠ U1（见 §7） |

NSP 形态冒烟（p12-m，`Booting game: 010047420000A000 | IROSEKA FHD (64-bit) | 1.0.1`）：日志出现 `rfvp: game root: … (romfs mounted)`、`GameConfig { hcb: Some(".iroseka.hcb"), nls: Some(GBK) }`、`the first frame was drawn`，中文标题正常渲染（`13-nsp-romfs-title.png` d965c616），0 exceptions。

## 6. 产物校验

- `galnx package nsp verify --nsp … --manifest examples/pilot02-iroseka.yaml --nstool … --keyset … --expect-title-id 010047420000a000 --json` → **ok=true**，12 checks = 0 fail / 1 warn（未签名 NCA，自签名预期），3 个 NCA 的 ProgID 均为 `0x010047420000A000`。
- NRO 回归（p12-p）与 NSP 冒烟（p12-m）都在同一 commit 的源码上构建，`/e/galnx-build/m5-switch-build.log` 中 `^error` 为 0。

## 7. 未验证项（U 项）与限制

- **U1 R=Ctrl 快进未在模拟器复现**：引擎侧确认 `notify_keycode_down` 会把 `Control` 写入 `new_input_state`（`crates/rfvp/src/subsystem/resources/input_manager.rs:383`），`anzu_scene.rs:49` 的 dissolve 快进也读该位；但 Citron 里按住 R（2.5 s / 5 s / 6 s）都只前进一句。可能属游戏脚本层面的 `TextSkip` 调用条件（如只在特定状态/开关下生效）。真机复验；若仍无效，备选方案是「按住 R 连发左键」。
- **U2 Esc 关不掉暂停菜单**：游戏菜单只认指针点击（p12-c c4/c5、p12-h 复现），所以 `B` 只用于「打开」，关闭用 `ZL` 右键或点 RETURN；已在 yaml/runbook 注明。
- **U3 锚点是本作布局专属**：SAVE/LOAD/EXIT/AUTO/确认框坐标来自本作 1280×720 UI 实测；换游戏或改 UI 缩放必须重新悬停扫描并改常量。
- **U4 真机手感未回填**：NSP v1.0.1 已于 2026-10-31 通过 DBI FTP 上传并自动安装（9,979,435,736 B / 1,462.2 s / 6.52 MiB/s，见 `evidence/P12-rfvp-input/device-upload.txt`），等待上机按 runbook §4 V1–V12 复验（重点：右摇杆光标速度、ZR 按住拖拽、MINUS 退出链路、U1 R=Ctrl）。
- 音频、movie 播放、内存余量仍沿用 018 §9 的 U1–U8，本轮未触碰。

## 8. 证据文件（`docs/milestones/evidence/P12-rfvp-input/`）

| 文件 | SHA-256 前 8 | 内容 |
| --- | --- | --- |
| 01-pause-menu.png | ba34c919 | B=Esc 打开暂停菜单 |
| 02-file-load.png | 15088646 | Y 宏 → FILE LOAD |
| 03-file-save.png | d4b0b705 | PLUS 宏 → FILE SAVE |
| 04-exit-black.png | 3f87a15f | MINUS 宏 → 确认 → 全黑退出（70,697 B） |
| 06-rightclick-close-menu.png | c170f65c | ZL=右键关闭暂停菜单 |
| 07-auto-toolbar.png / 08-auto-via-padx.png | 84c3e834 / 0393ca37 | X=AUTO（真鼠标点工具栏 / pad X 宏） |
| 09-rstick-cursor.png | be310cd0 | 右摇杆移动游戏自绘光标 |
| 10-left-stick-backlog.png / 11-dpad-backlog-scroll.png | 591f08bd / 732f6f0b | 左摇杆上=BACKLOG、方向键滚动 |
| 12-zr-leftclick-advance.png | 79fb10d0 | ZR=左键推进正文 |
| 13-nsp-romfs-title.png | d965c616 | NSP 从 romfs 启动、中文标题 |
| 14-a-enter-completes-typing.png / 15-a-enter-advance-scene.png | a43a8c3e / e07ccf12 | A=Enter 完成打字 / 推进到下一场景 |
| logs/i-macros-input-steps.tsv | c15fed0c | p12-i 宏操作序列 |
| logs/n-auto-input-steps.tsv | 79c7491c | p12-n A/AUTO 操作序列 |

## 9. 结论

用户 m18283 要求的映射表在 Switch no_std 输入层（`event.rs`）一次性重写完成，12 项中 11 项拿到 Citron 逐项证据（含「+ 存档 / − 退出（带游戏确认框）/ Y 读档 / X 自动」四个宏），第 12 项 R=Ctrl 的跳读语义需真机判定（U1）。实现不注入 TJS、不改游戏数据，NSP 仍是纯自包含（romfs 启动）；重打包后的 v1.0.1 NSP 通过独立 verify，可直接上真机复验。

## 10. 真机交付

- 2026-10-31 17:14：NSP v1.0.1 经 DBI FTP 上传到 Switch（`192.168.31.254:5000`），**9,979,435,736 B / 1,462.2 s / 6.52 MiB/s（24.4 分钟）**，无中断；上传后 DBI 根目录回到占位条目，表示文件已被接收并自动安装。
- 证据：`docs/milestones/evidence/P12-rfvp-input/device-upload.txt`（含上传日志尾部与两份日志的 SHA-256）。
- 下一步：用户在 Switch 上按 `docs/pilot/P11-rfvp-nsp-device-runbook.md` §4 的 V1–V12 验收，重点 U9（R=Ctrl 跳读）/ U10（右摇杆与 ZR 手感）/ U11（Esc 关菜单），结果回填本文件 §7、runbook §8 与 018 §9。
