# 008 — rfvp（xmoezzz/rfvp，FVP 引擎 Rust 重实现）评估

- 编码：008
- 对象：xmoezzz/rfvp（Nintendo Switch target：platform/switch）
- 版本/commit：HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`（2026-10-25T14:17:46Z，`add adr`），tag `pre-release` 指向同一 commit；版本 tag `0.7.0` = `99435f22e94eaec27c0c1b9f22cc2a6b1910d7d1`（2026-10-19T06:12:39Z）
- 评估日期：2026-10-30
- 执行：audit-engines（M5-a / task-26）
- 结论：**继续研究（P3 研究项）**。构建可复现、Citron 可运行、PC host harness 可运行；但无合法真实 FVP 内容验证、软光栅性能远低于可玩、真机未验证、Windows 构建需本地补丁、上游自述 experimental。
- 产物：`E:/galnx-build/m5-artifacts/rfvp.nro`（1,372,216 B，sha256 `4964dda90a45c6aacff9268687438130c16742317d52de7d717087b6f3a930bb`）

## 1. 目标

按《GalNX 计划草案 v0.6》§10 M5 的五条验收项，对 rfvp 的 Switch target 做逐条评估：

1. 联网复核上游最新 tag / commit / README / CI / `platform/switch/README.md`；
2. 记录构建命令、依赖（rustup target、linker、devkitPro 参与方式），并实际构建；
3. 检查产物（NRO 大小 / sha256 / nstool 静态结构）；
4. 用自建合法内容在 PC host harness 上跑通，记录渲染 / 音频 / 文件 IO / 输入 / 存档后端完成度（区分「源码实现」与「README/issue 声称」）；
5. 在 Citron（Switch 模拟器）上实测 NRO 启动与输入链路；
6. 给出三选一结论（正式适配 / 继续研究 / 搁置）+ 理由 + 前置条件。

## 2. 环境与工具链（实测）

| 组件 | 版本/路径 | 说明 |
| --- | --- | --- |
| 宿主 | Windows 10.0.26100 x64 / 16 核 | 构建根 `E:/galnx-build/m5-rfvp` |
| devkitPro | `D:/devkitPro`（`DEVKITPRO`） | devkitA64 r30-1、gcc 16.1.0、libnx 4.12.0、switch-tools 1.13.1 |
| Rust | `rustc 1.95.0-nightly (905b92696 2026-01-31)` / `cargo 1.95.0-nightly (fe2f314ae 2026-01-30)` | toolchain `nightly-2026-02-01-x86_64-pc-windows-msvc` + `rust-src` |
| rustup | 1.29.2（scoop） | `CARGO_HOME=D:/Scoop/persist/rustup/.cargo`、`RUSTUP_HOME=D:/Scoop/persist/rustup/.rustup` |
| 网络 | 代理 `http://127.0.0.1:7897` | rustup / cargo 下载依赖使用 |
| Citron | Nightly `0237a9b88` | 路径见 §6 |

devkitPro pacman 实测包版本：

- `devkitA64 r30-1`、`devkita64-gcc 16.1.0-1`、`devkita64-binutils 2.46.0-1`、`devkita64-newlib 4.6.0.20260123-4`、`devkita64-rules 1.1.1-1`、`libnx 4.12.0-1`、`switch-tools 1.13.1-1`。

上游 `platform/consoles/toolchain.env` 原文：

    RFVP_CONSOLE_NIGHTLY=nightly-2026-02-01

    注释：Keep it pinned: a floating nightly breaks these builds whenever a dependency such as unwinding stops compiling on the newest compiler.

本机 `nightly-2026-02-01` 与上游 pin 一致，未出现 toolchain 漂移问题。

## 3. 构建

### 3.1 上游命令

    ./platform/switch/build_switch.sh
    # -> target/rfvp-switch/switch/rfvp.nro

上游 `platform/switch/README.md` 要求：devkitPro（devkitA64 + libnx + switch-tools，`DEVKITPRO` 默认 `/opt/devkitpro`）+ rustup；脚本会自行 `rustup toolchain install` pin 的 nightly。target 是内置 `aarch64-nintendo-switch-freestanding` 的拷贝，关闭 `dynamic-linking`（否则 rustc 会连带编 `cdylib` 并因缺 global allocator 失败）。

### 3.2 本机实际命令

    cd /e/galnx-build/m5-rfvp
    DEVKITPRO=D:/devkitPro bash platform/switch/build_switch.sh

脚本关键步骤（原文取读 `platform/switch/build_switch.sh`）：

1. `source platform/consoles/toolchain.env`，导出 `TOOLCHAIN=$RFVP_CONSOLE_NIGHTLY`；
2. 检查 `$DEVKITPRO/tools/bin/elf2nro`、`nacptool`、`$DEVKITA64/bin/aarch64-none-elf-gcc`、`$DEVKITPRO/libnx/lib/libnx.a`；
3. `rustup toolchain install "$TOOLCHAIN" --profile minimal --component rust-src --no-self-update`；
4. `cargo +$TOOLCHAIN build -p rfvp-horizon --release --target platform/switch/aarch64-nintendo-switch-rfvp.json -Zjson-target-spec -Zbuild-std=core,alloc,compiler_builtins`；
5. gcc 编 `runtime/main.c`（`-march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE -std=gnu17 -O2 -g`，`-I $DEVKITPRO/libnx/include`）；
6. gcc 链接 `-specs=$DEVKITPRO/libnx/switch.specs -lnx -lm` → `rfvp.elf`；
7. `nacptool --create rfvp rfvp "$VERSION"` → NACP；`elf2nro` → `target/rfvp-switch/switch/rfvp.nro`。

### 3.3 关键依赖（源码取证）

- Rust 侧：`platform/switch/host/Cargo.toml` — package `rfvp-horizon` 0.1.0、`crate-type=["staticlib"]`、`license="MPL-2.0"`；依赖 `rfvp = { path="../../../crates/rfvp", default-features=false, features=["no_std"] }`；build-dep `cc = "1"`。
- C 侧：`platform/switch/host/build.rs` 用 `cc` 编 `crates/rfvp/vendor/rfvp_ogg_vorbis.c`（Ogg Vorbis 解码），compiler/archiver 指向 devkitA64 的 `aarch64-none-elf-gcc` / `-ar`；`cargo:rustc-link-lib=m`。
- 自定义 target：`platform/switch/aarch64-nintendo-switch-rfvp.json` — `arch aarch64`、`os horizon`、`panic-strategy abort`、`position-independent-executables true`、`linker rust-lld`、`dynamic-linking false`、`features "+v8a,+neon,+crypto,+crc"`、自定义 link-script 把 `.bss` 放入 data 段。
- libnx：`runtime/main.c` 直接用 libnx（`-lnx`、`switch.specs`），音频 `audren`、手柄 `pad`、触摸、`armTicksToNs`、`svcOutputDebugString`。
- 无 SDL、无 ffmpeg 链接依赖（视频解码是 Rust crate `na_mpeg2_decoder` / `na_wmv_player`，本 target 未验证）。

### 3.4 Windows 构建 bug 与修复（重要）

**现象**：Rust 编译成功，链接阶段报

    D:/devkitPro/.../ld.exe: .../librfvp_horizon.a: error adding symbols: file format not recognized; collect2.exe: error: ld returned 1 exit status

**根因**：`platform/switch/host/build.rs` 用无扩展名路径 `devkitA64/bin/aarch64-none-elf-gcc` / `...-ar`；Windows 下实际文件是 `.exe`，`Path::exists()` 为 false，`cc` crate 静默回落到宿主 mingw gcc（它仍用 devkitA64 newlib 头，所以日志里出现 `sys/reent.h` 等 warning）。产物 `librfvp_horizon.a` 共 166 个成员，其中 `*-rfvp_ogg_vorbis.o` 是 x86-64 COFF（前 4 字节 `64 86 cf 00` = `IMAGE_FILE_MACHINE_AMD64` 0x8664），aarch64 GNU ld 拒绝；其余 165 个成员是 ELF aarch64（`7f 45 4c 46`）。

**采用的修复（本地补丁，未提交上游）**：在 `build.rs` 的 `let compiler` / `let archiver` 前插入 `tool()` helper：

    // [GalNX local patch, M5-a] On Windows the devkitPro tools carry a .exe suffix, so the
    // extensionless paths never exist and cc silently fell back to the host compiler
    // (producing x86-64 COFF objects the AArch64 linker rejects). Probe both spellings.
    fn tool(devkitpro: &std::path::Path, rel: &str) -> PathBuf {
        let base = devkitpro.join(rel);
        if base.exists() { base } else { base.with_extension("exe") }
    }
    let compiler = tool(&devkitpro, "devkitA64/bin/aarch64-none-elf-gcc");
    let archiver = tool(&devkitpro, "devkitA64/bin/aarch64-none-elf-ar");

补丁全文见证据 `M5a-build/local-patch-build.rs.patch`（1,351 B）。修复后该 C 对象 magic 变为 `7f454c46`，链接通过。

**可选替代 workaround（未在本机采用）**：构建前导出 cc-rs 约定的环境变量指向 devkitA64 工具（`CC_aarch64_nintendo_switch_rfvp`、`AR_aarch64_nintendo_switch_rfvp`、`CXX_...`、`TARGET_CC`、`TARGET_AR`），并删除 `target/aarch64-nintendo-switch-rfvp` 坏缓存。两种方式都应写进 GalNX 的构建说明；本仓库补丁是「源码级修复」，更适合长期使用。

### 3.5 构建结果

- 退出码 0；日志末尾 `Finished release profile [optimized] target(s) in 5.90s`、`[switch] /e/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro`（本次为增量构建；首次 Rust 全量约 60 s，补丁后重建脚本 11 s）。
- 仓库状态：`git status --short` 仅 ` M platform/switch/host/build.rs`；HEAD `9f07ade`。
- 构建日志：证据 `M5a-build/build.log`（52,914 B，sha256 `8a14e39c…`）。

## 4. 产物静态检查（nstool）

产物 `E:/galnx-build/m5-artifacts/rfvp.nro`：

| 项目 | 值 |
| --- | --- |
| 大小 | **1,372,216 B** |
| sha256 | **`4964dda90a45c6aacff9268687438130c16742317d52de7d717087b6f3a930bb`** |
| EntryPoint | `0x14000020` |
| ModuleId | `e89739fd668a6dd7a63b24477a9611781333e25e000000000000000000000000` |
| 段 | `.text off 0x0 size 0xfd000`；`.ro off 0xfd000 size 0x3f000`；`.data off 0x13c000 size 0xf000`；`.bss size 0xd000` |
| NroSize | `0x14b000`（1,355,776） |
| ASET | Icon 0、NACP off `0x38` size `0x4000`、RomFs 0 |
| NACP Title/Publisher | 全语言 `rfvp` |
| DisplayVersion | `0.1.0` |
| NACP 其他 | StartupUserAccount Required、DataLossConfirmation Required、RatingAge CERO 12/ESRB 10/USK 12/PEGI 12/ACB 13、UserAccountSaveDataSize 62 MiB、JournalSize 1 MiB、LogoType Nintendo、LogoHandling None |

`.bss` 非 0（0xd000）说明上游自定义 link-script 生效（把 `.bss` 放 data 段让 `elf2nro` 看到大小）。nstool 无 prod.keys，仅报 NACP 签名解析 warning，不影响结构事实。完整输出见 `M5a-build/nstool.txt`。

与上游 CI 发布资产对比：pre-release 的 `rfvp.nro` 为 **1,364,024 B**、digest `sha256:0591ada244460cb3e9592b777eea110a7476f3ec934b8611c388ce27b0e614d5`（2026-10-25T14:30:54Z 上传，22 资产之一）。两者大小不同属正常（环境/编译选项差异），说明产物量级与上游一致。

## 5. PC host harness（自建合法内容）

### 5.1 内容

使用仓库自带 `win95_painter_demo/`（项目自身产物，仓库 license MPL-2.0，属项目内素材；正式分发前仍需确认素材全部为作者原创——见 §9 U4）：

- `painter.hcb`（5,834 B，唯一的 `.hcb`；由 `lua2hcb_compiler` 从 `painter.luax` + `painter.yaml` 编译）；
- `graph/w95_{pencil,eraser,bucket,close}` 各约 108–120 B（NVSG 16×16，hzc1 压缩）；
- `painter.yaml`：`nls: ShiftJIS`、`game_mode: 7`、`game_title: Win95-Painter`、`syscall_count: 148`、`custom_syscall_count: 0`。

字体：本机测试用 `Roboto-Regular.otf`（106,380 B，Apache-2.0，取自本机 LDPlayer 安装目录）作为 `default.ttf`，**仅本机测试、不入库、不分发**。

### 5.2 命令与坑

    cd /e/galnx-build
    cargo +nightly-2026-02-01 test --manifest-path /e/galnx-build/m5-rfvp/crates/rfvp/Cargo.toml \
      --lib --release --no-default-features --features no_std no_std_harness -- --nocapture

环境变量：`CARGO_HOME` / `RUSTUP_HOME` / `PATH` 加 rustup bin、`CARGO_TARGET_DIR=/e/galnx-build/m5-harness-target`、`RFVP_HARNESS_GAME=/e/galnx-build/m5-harness-content`、`RFVP_HARNESS_FONT=.../default.ttf`、`RFVP_HARNESS_OUT=/e/galnx-build/m5-harness-out`、`RFVP_HARNESS_FRAMES=300`。

**坑**：仓库根 `.cargo/config.toml` 有 `[unstable] build-std = ["core","alloc","compiler_builtins"]`（对所有 cargo 调用生效），在仓库目录内跑 `cargo test` 会报 `error[E0152]: duplicate lang item in crate core (which std depends on): sized`（build-std 的 core 与 rustlib 的 std 冲突）。**解决**：在仓库外目录（`/e/galnx-build`）用 `--manifest-path` 运行，避免发现该配置。

### 5.3 结果（`no_std_harness` 三个测试，2 通过 1 失败）

| 测试 | 结果 | 关键输出 |
| --- | --- | --- |
| `boots_and_runs_a_real_game` | **通过** | `booted: virtual 1024x640, rss 0 MiB -> 0 MiB, files opened: ["...\\painter.hcb", "default.ttf"]`；`done: 300 frames at 1280x720, peak rss 0 MiB, peak texture memory 0 MiB, avg 14.81 ms/frame (13.95 ms of it in the rasterizer), worst 24.94 ms`；frame 0 heap 6162 KiB（peak 8011 KiB）、textures 7、CPU images 2、sprites 3227 |
| `the_global_save_is_written_and_read_back` | **通过** | `global save is 262184 bytes`、`2 lines marked as read` |
| `saves_and_loads_a_slot` | 失败（内容不匹配） | `slot file is 433986 bytes`、`thumbnail is 96x72`，随后 panic：`crates\rfvp\src\no_std_harness.rs:891: assertion left != right failed: the story did not move on`（left=right=11908318807776354367） |

第三项失败原因：该测试期待「读档后剧情推进（文本行变化）」，而 Win95 Painter demo 不是故事型 VN，文本行不会变化 → 属**测试内容不匹配**，不是引擎缺陷；但这也说明该测试需要配一个真实 VN 内容才能通过，GalNX 后续应自建最小 VN 内容替代。

耗时：脚本总 123.6 s（含 release 编译 19.66 s），`HARNESS_EXIT=101`（因第三个测试失败）。截图 `frame_00000.png`（13,717 B，1280×720，PIL 从 PPM 转换）画面与 Switch 上的 Luax Painter UI 完全一致。证据：`M5a-host-harness/{host-harness.sh,host-harness.log,frame_00000.png}`。

## 6. Switch（Citron）实测

### 6.1 前提

- Citron Nightly `0237a9b88`（`workspaces/web-02/citron/citron.exe`），`CITRON_USER_DIR=C:/Users/ACETaffy/AppData/Roaming/citron`；
- 虚拟 SD：`.../citron/sdmc`；
- 内容布局（模拟 README 安装路径）：`sdmc/switch/rfvp/game/{painter.hcb, graph/w95_*, default.ttf, save/}`、`sdmc/switch/rfvp/debug.txt`（内容 `shot=0`）；**未建 `nls.txt`**（默认 ShiftJIS，与 `painter.yaml` 的 `nls: ShiftJIS` 一致）；
- 每个 run 前 tasklist 确认 0 个 citron 实例；只 kill 自己的 PID；`--keep` 保留证据。

### 6.2 三次 run

| # | run 目录 | PID | 注入 | 结果 |
| --- | --- | --- | --- | --- |
| R1 | `20261030-033018-rfvp` | 40660 | 无 | 启动成功，完整渲染 |
| R2 | `20261030-033146-rfvp` | 37072 | `C,C,UP,UP,RIGHT,RIGHT,C` | 画面 diff 0（无可见变化） |
| R3 | `20261030-033329-rfvp` | 19656 | `M`（=Plus→quit） | diff 0.933325，游戏退出→Citron 白屏 |

**R1 启动**：`status=loaded`、elapsed 17 s、title `citron Nightly | 0237a9b88 | rfvp (64-bit) | NVIDIA`、`title_match=true`、`boot_line=true`；nonblack 0.8302。截图为完整 **Luax Painter Win95 UI**（标题栏、工具栏铅笔/橡皮/油漆桶、调色板、白色画布、状态行 `Pencil  Color: Black  Right mouse: Erase`），Citron 状态栏 `Game: 18 FPS / Frame: 55.56 ms`。Citron 日志关键行：

    OutputDebugString: rfvp [info] rfvp no_std boot: parsed real HCB, initialized real GameData, and started VmRunner
    OutputDebugString: rfvp: the game is loaded, running
    OutputDebugString: rfvp: the first frame was drawn

SD 侧：`debug_report.txt` 96 B — `frame 240: 17.5 fps over the last 60 frames, slowest frame 71.4 ms` + `virtual frame 1024x640`；`debug_screen.bmp` 3,686,454 B（1280×720×32）；**`last_error.txt` 不存在** → 干净启动、无引擎错误。`virtual frame 1024x640` 被缩放到 1280×720 显示（截图可见左右黑边/letterbox）。

**R2 输入注入负结果**：`keys_requested=[67,67,38,38,39,39,67]`（C,C,UP,UP,RIGHT,RIGHT,C）、`keys_sent=7`、`key_method=postmessage`、`focus_ok=false`、`diff_ratio=0`、nonblack 0.8302→0.8302；before/after PNG 字节不同但像素 diff 0。原因需结合 R3 判定。

**R3 决定性输入验证**：`keys=[77]`（Citron 键盘 `M` → `Plus`）、`diff_ratio=0.933325`、nonblack 0.8302→0.9998（游戏退出后 Citron 主窗口白屏）。Citron 日志原文：

    [  19.194852] Debug.Emulated <Info> ... OutputDebugString: rfvp [info] quit requested by host event

→ **PostMessage 键盘 → Citron 手柄 → libnx hid → rfvp Plus → Quit 链路成立**；R2 的 diff 0 因此判定为**游戏语义**（单击落在画布未产生可见像素变化 / `InputGetCurs` 与 host cursor 同步问题），不是输入链路不通。

### 6.3 证据

- `M5a-run-boot/{result.json,run.log,window.png}`（window.png 95,594 B，sha256 `caaf58eb…`）
- `M5a-run-input/{result.json,run.log,window-after-input.png}`
- `M5a-run-quit/{result.json,run.log,window-after-input.png}`（after 71,022 B）
- `M5a-build/{build.sh,build.log,local-patch-build.rs.patch,nstool.txt,sha256.txt}`
- `M5a-host-harness/{host-harness.sh,host-harness.log,frame_00000.png}`

完整 Citron harness run 目录在 `workspaces/citron-harness/runs/`（含 citron_log.txt、before/after 全图）。

## 7. 后端完成度（源码实现 vs 声称）

| 后端 | 源码实现（本机读源码确认） | 本机验证 | 声称/边界 |
| --- | --- | --- | --- |
| 渲染 | `SoftRaster` 1280×720 软光栅（`platform/switch/host/src/render.rs`），缩放+letterbox 后拷入 libnx framebuffer；线性光混合；`RfvpRenderer` 抽象可换 GPU | ✅ Citron 全 UI 渲染；host 300 帧画面一致 | 软光栅纯 CPU；Citron 17.5 fps，host 14.81 ms/帧；README 称 Ryujinx 60 fps（未复核） |
| 音频 | `runtime/main.c` audren 48 kHz、2 voices、6×1024-frame 立体声 buffer（约 21 ms/页）；`rfvp_switch_audio_render` 混音 | ❌ 未做音频采集/听感验证 | README 称 Ryujinx「picture and sound」 |
| 文件 IO | `fs.rs`：相对路径→`game_root`、`/` 开头→`sdmc:`；newlib stdio/dirent；`.hcb`/`.bin` 枚举为 pack、`save/` 例外 | ✅ 加载 `painter.hcb`、`default.ttf`、`graph/w95_*` | issue #39：每个 `.bin` 全量读入 RAM、save 目录 `.bin` 误当 pack、loose 资产目录（非 `.bin`）不支持 |
| 输入 | `event.rs`：A=左键、B=右键、X=Return、Y=Space、L/R/ZL/ZR=Ctrl、−=Esc、+=Quit、十字/摇杆移光标、触摸=指针；光标初值 (640,360)、十字步长 12 px、摇杆除数 18000 | ✅ R3 Quit 链路；⚠️ R2 单击无可见变化（语义/坐标待查） | README 控制表；触摸未验证 |
| 存档 | `postcard` 编码；`save_storage()` root `sdmc:/switch/rfvp`（注释每游戏 `saves/<game>/`）；全局设置/已读 + 每槽存档 + 缩略图 | ✅ host：global 262,184 B；slot 433,986 B + 96×72 缩略图；❌ Switch 未做存档实测 | README 称 `game/save/`（与代码路径不一致，见 U5）；与桌面版存档不兼容 |
| 字体/NLS | `default.ttf` 必读（缺失写 last_error.txt）；`nls.txt`/`config.toml` 支持 ShiftJIS/GBK/UTF-8 | ⚠️ 仅 Latin 字体 + ShiftJIS 默认路径跑通；CJK 渲染未验证 | README：可把 ttf 放 `font/`；翻译版需 Nls 切换 |
| 视频/电影 | crate 列表含 `na_mpeg2_decoder`、`na_wmv_player` | ❌ 未验证 | PR #58 仍在改 movie soundtrack |
| 调试 | `debug.txt` 触发每秒 `debug_report.txt`、每 5 s `debug_screen.bmp`；错误写 `last_error.txt`；panic handler 同上 | ✅ debug_report/BMP 生成；`last_error.txt` 不存在=干净启动 | README 一致 |

## 8. 上游健康与 experimental 边界

- GitHub（2026-10-30 API）：default branch `main`、archived false、stars 152、forks 24、open issues 4（#39 真机报告、#33 剧情段崩溃、#58/#57 两个 PR）、created 2024-02-09、last push 2026-10-25T14:30:48Z。
- 最近 tag：`pre-release` = HEAD `9f07ade`（release `rfvp v0.7.0 pre-release (9f07ade)`，2026-10-25 发布，22 资产含 NRO）；语义版本 tag `0.7.0` = `99435f2`（2026-10-19）。
- CI：`Console Executables`（ubuntu-24.04，Docker `console-switch`，官方 `devkitPro/devkitA64 20260219`）会为每次 push/tag/PR 构建 Switch NRO 并挂到 pre-release；`build-homebrew-artifacts.yml` 注释明确「Switch and PS Vita are built by consoles.yml」。
- README 自述状态原文：`**Status: experimental.** It runs in Ryujinx at 60 fps with picture and sound; it has not been run on a console yet.` → **真机未验证**，所有真机结论只能作为「README 声称 / 第三方报告」引用。
- 真机第三方报告（issue #39，open，2026-10-10）：基于较旧 commit `81a8b68`，报告 boot 到标题菜单、触摸与音频可用但**极慢（render ≈885 ms + present ≈196 ms/帧）**，并列出一批当时已修/未修问题；维护者回复「I don't own a jailbroken switch, it should work well in the emulator」，未确认真机可用。当前 HEAD 已包含部分修复（如 `present()`、`boot()`、字体路径等），但无新的真机报告。
- 结论边界：**Switch 上「能启动并渲染 + 输入链路通」已被本机 Citron 证实；「可玩」未被任何一方证据支持。**

## 9. 未验证项 / 风险

- **U1 真机**：未上真机；README 自述「has not been run on a console yet」；issue #39 为旧 commit 第三方报告，当前 HEAD 未复核。
- **U2 真实 FVP 内容**：本机只用 `win95_painter_demo`（项目自带 demo，ShiftJIS 非 VN）；未用任何商业游戏数据。真实 FVP 游戏（`*.hcb` + `graph.bin`/`bgm.bin` 等大包、loose 资产目录、影片）兼容性未验证。
- **U3 性能**：Citron 17.5 fps（软光栅，宿主 CPU）；host harness 14.81 ms/帧；issue #39 真机 885 ms/帧。性能不满足「可玩」。
- **U4 demo 素材版权**：`win95_painter_demo` 属仓库产物（仓库 MPL-2.0），但美术素材是否全部为作者原创/可再分发**未逐项核实**，分发前须确认。
- **U5 存档路径不一致**：README 写 `game/save/`，`fs.rs` 的 `save_storage()` root 为 `sdmc:/switch/rfvp` 且注释 `saves/<game>/`；Switch 上实际落盘路径未实测。
- **U6 音频/视频**：未做音频输出采集、未测影片播放/字幕。
- **U7 CJK/字体**：未验证真实日文/中文 HCB 文本渲染与 `nls.txt`/`config.toml` 路径。
- **U8 输入语义**：R2 单击画布无可见像素变化，`InputGetCurs()` 与 host cursor 的坐标同步未在源码逐行确认；触摸未验证。
- **U9 构建可复现性**：Windows 必须打 build.rs 补丁（或导出 cc-rs 环境变量）；Linux/CI 无此问题。补丁未提交上游，升级时需重打。
- **U10 内存**：issue #39 指出 `build_host_vfs` 全量读 `.bin`；真实游戏包体积大时有 OOM 风险，未在本机验证。
- **U11 许可证**：MPL-2.0，文件级 copyleft；分发修改版（含 build.rs 补丁）需公开该文件源码并保留许可证声明；静态链接不传染闭源（与 GPL 不同），但须做合规声明。

## 10. 结论

**继续研究（P3 研究项）**，不作为 GalNX 首款原型引擎。

理由（基于证据）：

1. **构建可复现**：pin 的 `nightly-2026-02-01` + devkitA64 r30 可构建出 NRO；唯一阻塞是 Windows 下 `build.rs` 的 `.exe` 探测 bug（已本地补丁，另有环境变量 workaround），CI 在 Linux 上无此问题。
2. **Citron 上可运行**：NRO 启动、完整渲染 demo UI，无 `last_error.txt`；输入链路（键→手柄→hid→Quit）已被 R3 证实。
3. **PC host 可运行**：`no_std_harness` 在 Windows 原生跑通 2/3 测试（第三项因 demo 非 VN 而失败），渲染/文件 IO/存档写出均验证。
4. **但「可玩」不成立**：软光栅性能（Citron 17.5 fps、真机报告 885 ms/帧）、无真实 FVP 内容兼容性证据、README 自述未上真机、issue #33 崩溃未修、PR #58 未合。
5. **集成定位**：适合作为「FVP 引擎兼容性研究/工具链样本」，排在 KiriKiri / ONScripter 之后；若后续出现合法真实 FVP 内容（如免费 FVP demo）且性能优化（GPU renderer / 硬件缩放）落地，可升级评估。

前置条件（若要推进到「正式适配」）：

1. 至少一个可合法分发/免费的真实 FVP 内容用于端到端验证（渲染、音频、存档、影片、CJK）；
2. 性能达到可玩阈值（真机或 Citron ≥30 fps 稳定），或上游合并 GPU renderer；
3. 上游真机验证（issue #39 类报告在当前 HEAD 复现通过）；
4. 存档路径/NLS/config.toml 行为与 README 对齐（或 GalNX 启动器统一约定）；
5. MPL-2.0 合规声明与 build.rs 补丁的升级维护策略。

## 11. 证据

| 证据 | 路径 | 说明 |
| --- | --- | --- |
| 构建脚本/日志 | `docs/milestones/evidence/M5a-build/build.sh`、`build.log` | 52,914 B，sha256 `8a14e39c…` |
| 本地补丁 | `M5a-build/local-patch-build.rs.patch` | 1,351 B |
| nstool | `M5a-build/nstool.txt` | 产物结构 |
| 哈希 | `M5a-build/sha256.txt` | NRO sha256 |
| Citron 启动 | `M5a-run-boot/` | window.png 95,594 B |
| Citron 输入（负结果） | `M5a-run-input/` | diff 0 |
| Citron Quit（输入链路） | `M5a-run-quit/` | diff 0.933325 |
| PC host | `M5a-host-harness/` | log 50,222 B、frame_00000.png |

## 12. 复现

1. 克隆 `https://github.com/xmoezzz/rfvp`，检出 `9f07adef2eb5d559777f9bf59a67b756875cb24f`；
2. 安装 devkitPro（devkitA64 + libnx + switch-tools）与 rustup；
3. 若在 Windows：给 `platform/switch/host/build.rs` 打 `.exe` 探测补丁（或导出 `CC_aarch64_nintendo_switch_rfvp` 等环境变量并删 target 缓存）；
4. `DEVKITPRO=<path> bash platform/switch/build_switch.sh` → `target/rfvp-switch/switch/rfvp.nro`；
5. 模拟器/真机：NRO 放 `sdmc:/switch/rfvp/rfvp.nro`，内容放 `sdmc:/switch/rfvp/game/`（`*.hcb`、`*.bin`、`default.ttf`），可选 `nls.txt`；
6. PC host：在仓库外目录用 `--manifest-path` 跑 `no_std_harness`（见 §5.2），设 `RFVP_HARNESS_GAME/FONT/OUT`。

## 13. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-30 | 初版：M5-a 五条验收 + Citron R1–R3 + host harness + 结论「继续研究」 |
