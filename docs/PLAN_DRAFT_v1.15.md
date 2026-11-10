# GalNX：Nintendo Switch 视觉小说移植框架计划草案

- **文档状态：** 讨论草案 v1.15（在 v1.14 基础上回填 **M5-h：rfvp 真机掉帧修复（GPU prev-frame + 关闭诊断回读 + 顶点批处理）**：用户 m20518/m20552 真机与 Ryujinx 同为「转场掉帧 / 音频停滞 / 每约 5 秒卡顿 / 启动与存档尖峰」。四类根因 = ① `crates/rfvp/src/no_std_core.rs:857-871` 每帧 `capture_thumbnail(1920×1080)` 回读 8.29 MB 再上传为 prev-frame 纹理（帧 81–85 thumb 45.48–66.49 ms，转场主因）② `platform/switch/host/src/ffi.rs` 每 300 帧写 `debug_screen.bmp` 回读 41 ms（5 秒周期卡顿的伪影）③ 每 sprite 一次 `SDL_RenderGeometry`（稳态 14 draws/14 flushes）+ 缺宿主阶段计时 ④ 冷启动 `vfs_read` 675 ms / `graph_decode` 521 ms、存档 `save_finalize` 32 ms + 缩略图 11 ms。修法 = 6 文件：`sdl_video.c` 双 1280×720 `SDL_TEXTUREACCESS_TARGET` 轮换（场景入 target、present RenderCopy、`PREV_FRAME_TEXTURE_ID` 取上一 target）+ 顶点批处理（8192 顶点/12288 索引）+ 宿主阶段计时；`host_api/render.rs` 加 `supports_gpu_prev_frame`、`prim_commands.rs` 加 `set_prev_frame_gpu`、`no_std_core.rs` 走 GPU 分支并保留 CPU fallback、`host/src/render.rs` 覆盖 true、`ffi.rs` 关 `DEBUG_SCREEN_ENABLED`。Citron 同探针（perf3→perf4）：slow 行 154→19、帧>7 慢帧 151→15、≥50 ms 136→5、thumb≥20 ms 142→0、slow 总时长 12,133.7→3,567.8 ms，稳态 60.0 fps；标题/正文逐项目视一致。产物 = 补丁 `rfvp-perf-gpu-prev-frame.patch`（32,781 B / +481 −50 sha256 `e64dfb71…`）+ 全量 diff 107,938 B / 12 文件 + NRO 7,843,896 B sha256 `e5373bd7…` + ELF 17,069,080 B sha256 `e4040e7b…` + 自包含 NSP v1.0.3 9,979,441,368 B sha256 `b9e0d6a5…`；`galnx package nsp verify` ok=true 12 checks（1 warn = 未签名），Citron NSP 形态冒烟 PASS（romfs:/game、中文正文、主机光标、QUIT GAME?、0 exceptions）；**真机复验 V14/V15 待用户**（NSP v1.0.3 已 DBI FTP 上传真机：9,979,441,368 B / 1,529.0 s ≈ 6.22 MiB/s，25 分 29 秒，DBI 自动安装）；冷启动/存档尖峰列 U19/U20，GPU target 真机支持列 U21。详见 §10 M5-h 与 `docs/builds/021-rfvp-perf-gpu-prev-frame.md`）。
- **文档状态：** 讨论草案 v1.14（在 v1.13 基础上回填 **M5-g：rfvp 真机四项缺陷修复（光标 / 性能 / 原生退出 / − 键确认退出）**：用户 m19465/m19535 真机反馈 ① 无鼠标光标 ② 进正文后卡顿 ③ 游戏暂停菜单 EXIT 退出黑屏 ④ MINUS 直接退出、无确认框。根因与修法：① no_std 端无 winit 光标 → 主机层 `platform/switch/runtime/sdl_video.c` 用 SDL overlay 画菱形光标（新增 `galnx_sdl_set_overlay()`，纹理 scratch 复用，`main.c` 每帧喂状态）；② 纹理反复 create/ReadPixels 导致 GPU 抖动 → 按 id upsert + 单张 scratch 复用 + `render.rs` 只转发（Citron 60 fps、render 15.75 ms/帧）；③ 游戏 ExitDialog 的退出请求在 no_std 端无人消费 → `crates/rfvp/src/no_std_core.rs` 消费 `ExitDialog` pending 请求与 `ExitMode(3)`，日志 `quit requested by the game (ExitDialog confirmed)` 并走引擎正常关闭 + `save_global_if_changed()`；④ MINUS 改为只弹主机层自绘 `QUIT GAME?` 面板（A=YES → `request_quit()` 正常关闭，B=NO 取消），退出确认与光标此后不再依赖游戏 UI / 坐标宏。产物 = 补丁 `rfvp-device-fixes.patch`（109,915 B / 7 文件 sha256 `9b65b8b2…`）+ 全量 diff 85,712 B + NRO 7,839,800 B sha256 `4f096dd6…` + 自包含 NSP v1.0.2 9,979,437,784 B sha256 `ff259aa4…`；Citron NRO/NSP 双形态全项 PASS（中文正文 / 主机光标 / 确认框 / 干净退出，0 exceptions）、`galnx package nsp verify` ok=true 12 checks（1 warn = NCA 未签名），DBI FTP 实测 9,979,437,784 B / 1,548.7 s ≈ 6.15 MiB/s（25.8 分钟，DBI 自动安装），**真机复验 V1–V14 待用户**）。
- **文档状态：** 讨论草案 v1.13（在 v1.12 基础上回填 **M5-f：rfvp 手柄映射重写（Citron 级逐项验证）**：上游 `platform/switch/host/src/event.rs` 按用户 m18283 的映射表整体重写——A=Enter、B=Esc（游戏暂停菜单）、方向键=方向键、R=Ctrl、ZR/ZL=鼠标左/右键（按压语义）、右摇杆=光标（POINTER_DIVISOR=3000）、左摇杆上下=Wheel（±120，6 poll 重复）、X=工具栏 AUTO、Y=暂停菜单 LOAD、PLUS=暂停菜单 SAVE、MINUS=暂停菜单 EXIT+退出确认；菜单/工具栏一律用「Esc 宏开菜单 → 指针移到实测锚点 → 左键」的三段宏（阶段机 + 90 poll 淡入等待），锚点由 Citron 悬停扫描实测：SAVE=(1117,171)、LOAD=(960,217)、EXIT=(654,608)、AUTO=(1079,700)、退出确认=(560,379)。产物 = 补丁 `rfvp-input-remap.patch`（413 行 / +264 −56）+ NSP v1.0.1（9,979,435,736 B sha256 `0fda623c…67419`），Citron 已验证 B=Esc 菜单、ZL=右键关菜单、Y/PLUS/MINUS 三项宏、方向键、左摇杆滚轮、右摇杆光标、X=AUTO；R=Ctrl 快进的跳读效果在 Citron 未复现，列 U3 待真机复验）
- **文档状态：** 讨论草案 v1.12（在 v1.11 基础上回填 **M5-e：rfvp 自包含 NSP（romfs）**：`platform/switch/runtime/main.c` 在 romfs 挂载且 `romfs:/game` 存在 `.hcb`、SD 侧 `sdmc:/switch/rfvp/game` 无游戏时切到 romfs 游戏根，存档仍留 SD（`saves/<game-id>/` 不受影响）；新增通用打包脚本 `scripts/build_nsp_game.sh`（elf2nso → npdmtool → nacptool → romfs 硬链接 → hacBrewPack → nstool）。产物 NSP 9,979,435,224 B sha256 `4592385c…`、romfs 9,932,275,140 B / 161 顶层条目、TitleID `010047420000A000`；Citron 把 SD 游戏目录改名 `game.sd-bak` 后仍从 `romfs:/game` 启动（t=8.41 `(romfs mounted)`）、加载 GBK 中文脚本、显示中文正文「从天而降的羽毛。」、PLUS 干净退出（0 exceptions），NRO 形态回归 PASS；`galnx package nsp verify` 12 checks（11 ok / 1 warn = 未签名预期）。**真机安装未验证**（9.98 GB 必须 exFAT SD 或 NAND；DBI FTP 约 25–30 分钟），音频 / movie / 4 GB 内存余量未测。记录 `docs/builds/018-rfvp-nsp.md`、补丁 `patches/rfvp-switch/rfvp-romfs.patch`、证据 `docs/milestones/evidence/P11-rfvp-nsp/`、清单 `examples/pilot02-iroseka.yaml`。）

- **文档状态：** 讨论草案 v1.11（在 v1.10 基础上回填 **M5-d：rfvp 手柄输入与快捷存读档**：上游 `platform/switch/host/src/event.rs` 基线映射实测成立（十字键/左摇杆=虚拟光标、A=左键、B=右键（隐藏消息窗）、X=回车、Y=空格、L/R/ZL/ZR=按住 Ctrl 跳过、PLUS=退出）；两个结构性缺口 = ① 游戏内 system 菜单只认指针（Enter/方向键/肩键全无反应）② `legacy::save_file/load_file` 置 pending 请求并 `should_break()` 后由**桌面专属** `legacy_save_load_ui` 消费，Switch 无消费者 → 点中 SAVE/LOAD 永久挂起，且上游不产生 `Wheel` 事件（backlog 无输入源）。patch J 在 4 文件补 `RfvpEvent::QuickSave/QuickLoad`、`no_std_core` 事件处理 + `take_pending_save_load_request()` 兜底到快速槽 0、右摇杆字段与 `Wheel{±120}`、PLUS 改修饰键（PLUS+ZR 快速存档 / PLUS+ZL 快速读档 / 松开才退出）、光标除数 18000→6000；最终 NRO 7,827,512 B sha256 `b95cd26b…`。Citron P10-h 实测 `quick save: wrote slot 0` / `quick load: read slot 0`、新增 `rfvp_s000.bin` 490,104 B、右摇杆上推弹出 BACKLOG、PLUS 干净退出；组合键（harness 无法同时按两键）、真机、游戏自带多槽位 SAVE 面板仍为未验证项。记录 `docs/builds/017-rfvp-input.md`、补丁 `docs/builds/patches/rfvp-switch/rfvp-input.patch`、证据 `docs/milestones/evidence/P10-rfvp-input/`。）
- **文档状态：** 讨论草案 v1.10（在 v1.9 基础上回填 **M5-c：rfvp Switch 渲染后端改为 SDL2/GLES2，性能 17–19 fps → 60.0 fps**：引擎仍 pin `9f07adef` + `nightly-2026-02-01`，只改 `platform/switch` 显示层三处（`runtime/sdl_video.c` 新建 C shim、`host/src/render.rs` 全部转发、`runtime/main.c` 改 SDL 主循环；libnx 只留输入与音频）并调整链接顺序（`-lnx` 必须排在 `-lSDL2`/`-ldrm_nouveau` 之后）。Citron 0237a9b88 实测 `frame 8280: 60.0 fps`、`perf avg vm 0.56 / scene 0.23 / render 15.57 / total 16.37 ms`，标题画面与中文正文「从天而降的羽毛。」渲染正确、0 异常；NRO 7,823,416 B sha256 `e3acbce4…`。两个真因：① C shim 的 `create_texture` 必须 **upsert**（引擎 `prim_commands.rs:224 upload_graph_if_needed` 对同一 `graph_id` 反复 create；文字图 `graph_id=4064+slot`）；② 早期截图拍在文字首现（启动后 t≈63.5 s）之前，属采样时机问题。框架同时新增 `build_backend: custom-script` 与 `examples/engines/rfvp.yaml`；记录 `docs/builds/016-rfvp-sdl2-backend.md`、补丁 `docs/builds/patches/rfvp-switch/`、证据 `docs/milestones/evidence/P9a-rfvp-sdl2/`。真机 / 音频 / CJK / 手柄 / 内存 / MPL-2.0 合规仍为未验证项，rfvp 保持研究项。）
- **文档状态：** 讨论草案 v1.9（在 v1.8 基础上回填 **A10 真机验收 PASS 与首款垂直试点完成**：用户 m13918（2026-10-31）真机复验确认 v1.8 四问题（设置持久 / SAVE·LOAD 时间文本与 NEW / 继续游戏强制终止警告 / ZR 按住拖动）全部解决、暂未发现明显问题；A10 中文 CN NSP（1.0.9，2,870,911,704 B sha256 `0efc23f6…`）经 DBI FTP 上传自动安装（449.7 s ≈6.12 MiB/s）；首款垂直试点按用户定义完成标准达成，后续进入多游戏工程化 / `build.commands` / CI 与 A10 长流程回归）
- **文档状态：** 讨论草案 v1.8（在 v1.7 基础上回填 **P8 退出存档 / 按住鼠标（patch I）与 A10 中文 NSP**：定位 patch F/G 的立即 TVPExitApplication 跳过 MainWindow.finalize()（唯一 SystemSave/TraceSave 点）导致设置不持久、SAVE/LOAD 无时间文本/NEW 卡槽 1、「继续游戏」被判强制终了；patch I 在关闭路径显式 TraceSave+SystemSave 后延迟 1 s 退出、ZR/ZL 改按住鼠标并重显淡出光标、onAxisEvent 的 PrimaryLayerArea 早退移到 __SWITCH__ 之后；Citron i6/i8 与 A10（1.0.9，2,870,911,704 B sha256 0efc23f6…）首启冒烟 A–D 全 PASS，仅待 A10 真机复验）
- **文档状态：** 讨论草案 v1.7（在 v1.6 基础上做 **封面归属澄清**：本项目不设统一项目封面，封面属于具体游戏——《晴霁之后定是菜花盛开的好天气》的封面只作该作 HOME 图标与文档展示，后续每款移植游戏各自制图；README 顶部不再挂游戏封面，改到垂直试点小节内并加范围说明，`## 约定` 增第 7 条封面规则，`docs/builds/014` §4 同步注明范围；计划快照 v1.7。）
- **文档状态：** 讨论草案 v1.6（在 v1.5 基础上回填 **P7 输入微调 / 封面 / A9 中文 NSP**：patch H 让 R 肩键按住持续发 Ctrl（配合游戏 `SkipCheck()` 轮询 `System.getKeyState(VK_CONTROL)` 实现快进）、左摇杆上下滚轮方向跟正（上推=打开 BackLog、下拉=下一句）、NSP 首页图标换成用户提供的封面图（256x256 JPEG）；Citron h1 实测 R 快进跨脚本（@0000A_Z01→Z02）、上推开 BackLog、A 仍推进；A9 中文 CN NSP（version 1.0.8）2,870,911,192 B sha256 `ee0603b4…`，`package nsp verify` 19 checks，Citron 首启解包 23 文件 → 中文标题/正文 → R 快进 → BackLog → MINUS 确认 → 干净退出全通，仅待 A9 真机复验）
- **文档状态：** 讨论草案 v1.5（在 v1.4 基础上回填 **P6 手柄映射 v2 / 三个真机 bug 修复 / A8 中文 NSP**：patch G 在引擎 pad 层实现用户指定映射（A=Enter、B=原生 back、X=自动、Y=读档、+=存档、-=退出、ZR/ZL=鼠标左右键、右摇杆半速光标、左摇杆滚轮单步、D-Pad=方向键），并修复 ①K2S 表单叠热键冻结 ②K2S 抽屉电源键退出触发 SystemObj 崩溃 ③光标过快，另修 Minus 键不达引擎；A8 中文 CN NSP（version 1.0.7）2,870,873,816 B sha256 `ec74b0b4…`，`package nsp verify` 19 checks，Citron 首启解包 23 文件 → 中文标题/正文 → MINUS 干净退出全通，仅待真机复验）
- **文档状态（v1.4，保留）：** 讨论草案 v1.4（在 v1.3 基础上回填 **P5 中文 OP / A7**：从 PC 中文版 `movie_chs.xp3` 取中文硬字幕 `opening.mpg`（134,811,648 B，114.5 s）替换 payload 的 `movie.xp3`，先以 op1 场景实测端到端播放 PASS，再打 **A7 中文 CN NSP**（version 1.0.6，2,870,879,960 B sha256 `c23a519a…`，`package nsp verify` 19 checks / 18 ok / 1 warn，Citron 首启解包 23 文件后中文标题菜单 + 中文正文 + 0 异常）；至此中文试点（标题/正文/OP）在模拟器级全部走通，仅剩真机对 A5/A7 的最终复验），供后续与 Agent 协作拆解、验证和修订
（v1.3 文档状态行保留：讨论草案 v1.3（在 v1.2 基础上回填 **P4 退出修复 A5** 与 **P5 汉化 A6**：patch F 让主窗口确认关闭直接 `TVPExitApplication(0)` 并补 Window 的 Win32 兼容成员；汉化改用公开汉化源码 `t-satoru-Studio/haruno_script` 重打包 XP3（零引擎改动，data/scenario/image00 三包），A6 中文 CN NSP 在 Citron 上中文标题菜单 + 中文正文全通、`package nsp verify` 19 checks；A5（日文 1.0.4）与 A6（中文 1.0.5）均待真机最终复验），供后续与 Agent 协作拆解、验证和修订）
（v1.1 文档状态行保留：讨论草案 v1.1（在 v1.0 基础上回填 **P3.5 手柄存档/读档**：K2NX patch D 手柄可控虚拟鼠标 + patch E 用 `TVPExecuteExpression` 调本作 TJS 原生存档 API，全手柄完成「存档→落盘→重启→读档→续玩」闭环，NRO 与 A4 自包含 NSP 双形态实测通过；A4 NSP 2,906,135,768 B sha256 `2003ec1e…`、`package nsp verify` 19 checks；P4 真机待用户设备），供后续与 Agent 协作拆解、验证和修订）
- **最后整理日期：** 2026-11-01（v1.15）
- **版本记录约定【v0.2】：** 后续修改在对应位置用 `【v0.x】` 标记并登记到文末“修订记录”；每次升版先把上一版备份到 `Workspace/`（v0.1 备份：`GalNX_移植框架计划草案_v0.1_20261029.md`；v0.2 备份：`GalNX_移植框架计划草案_v0.2_20261029.md`；v0.3 备份：`GalNX_移植框架计划草案_v0.3_20261029.md`）。【v0.4】沿用同一约定，本次升版已备份 v0.3。【v0.5】沿用同一约定，本次升版已备份 v0.4（`GalNX_移植框架计划草案_v0.4_20261030.md`）。【v0.6】沿用同一约定，本次升版已备份 v0.5（`GalNX_移植框架计划草案_v0.5_20261030.md`）。【v0.7】沿用同一约定，本次升版已备份 v0.6（`GalNX_移植框架计划草案_v0.6_20261030.md`）。【v0.8】沿用同一约定，本次升版已备份 v0.7（`GalNX_移植框架计划草案_v0.7_20261030.md`）。【v0.9】沿用同一约定，本次升版已备份 v0.8（`GalNX_移植框架计划草案_v0.8_20261030.md`，90,986 B）。【v1.0】沿用同一约定，本次升版已备份 v0.9（`GalNX_移植框架计划草案_v0.9_20261030.md`，98,868 B sha256 `422b6d5e…`）。【v1.1】沿用同一约定，本次升版已备份 v1.0（`GalNX_移植框架计划草案_v1.0_20261030.md`，106,842 B sha256 `e08afd602946c83b2826284fafd831f333e4c3b3b56fec9ea1cffd5a7ee95f96`）。【v1.2】沿用同一约定，本次升版已备份 v1.1（`GalNX_移植框架计划草案_v1.1_20261030.md`，115,640 B sha256 `950794caf3cbb9d60cb94e77a9ed4b5dae85eec02eabb1844bc0888f35051b50`）。【v1.3】沿用同一约定，本次升版已备份 v1.2（`GalNX_移植框架计划草案_v1.2_20261030.md`，123,781 B sha256 `7223c98999de460a57ce2dd88323b9a33a09115d4a8ec6700189ec6ac1a65442`）。【v1.4】沿用同一约定，本次升版已备份 v1.3（`GalNX_移植框架计划草案_v1.3_20261030.md`，131,379 B sha256 `2559d063d66d275e8d0692d6ad733090027f4b30f01037fd06d8d59b641dcaef`）。【v1.5】沿用同一约定，本次升版已备份 v1.4（`GalNX_移植框架计划草案_v1.4_20261030.md`，138,634 B sha256 `9d6337deb98cbf016265e11c69d266d92266545e472ddb9858f4e0110a57e716`）。【v1.6】沿用同一约定，本次升版已备份 v1.5（`GalNX_移植框架计划草案_v1.5_20261030.md`，149179 B sha256 `e9a407b7ca2d340863418152b3ff530d933f6a36576e5aa1244d166f809e86e5`）。 【v1.7】沿用同一约定；本次升版已备份 v1.6（`GalNX_移植框架计划草案_v1.6_20261030.md`，157,561 B sha256 `f5508b7e118fef10de2875d4d885ccd68bc059200f73dad3ec29999691d52949`）。 【v1.8】沿用同一约定；本次升版已备份 v1.7（`GalNX_移植框架计划草案_v1.7_20261030.md`，159,457 B sha256 `fc68a1cd6bb307c8a01b7b229e0083a2319b24fac9211113c2056ece5c02a183`）。 【v1.9】沿用同一约定；本次升版已备份 v1.8（`GalNX_移植框架计划草案_v1.8_20261031.md`，165,697 B sha256 `f7d4d4e3b71b4dd99f2cbaced8d60f222e07f0a3cbf95bc2cb6f02dc2bdd11df`）。【v1.10】沿用同一约定，本次升版已备份 v1.9（`GalNX_移植框架计划草案_v1.9_20261031.md`，168,422 B sha256 `18362ae1…`）。 【v1.11】沿用同一约定，本次升版已备份 v1.10（`GalNX_移植框架计划草案_v1.10_20261031.md`，177,112 B sha256 `6f3dbfd3…`）。 【v1.12】沿用同一约定，本次升版已备份 v1.11（`GalNX_移植框架计划草案_v1.11_20261031.md`，184,371 B sha256 `c8045ae2…`）。；【v1.13】沿用同一约定，本次升版已备份 v1.12（`GalNX_移植框架计划草案_v1.12_20261031.md`，190,291 B sha256 `07e53496…`）。 【v1.15】沿用同一约定，本次升版已备份 v1.14（`GalNX_移植框架计划草案_v1.14_20261031.md`，208,286 B sha256 `c0ae22b4ad5db8de6c4d9df4ffcfdc0f05f2a59e76359909ba41b4f5e43fa106`）。
- **暂定项目名：** GalNX（名称可改）
- **目标平台：** Nintendo Switch / NS1（Horizon OS，Homebrew 环境）
- **开发主机：** Windows PC；允许通过 WSL2、Docker 或 Linux 构建环境执行部分工具链
- **重要约定：** 本文中的“已知”表示已找到公开项目或文档，不表示已在本机成功构建，更不表示已在真实主机上验证。所有适配状态均应通过实际测试更新。

---

## 1. 项目目标

构建一个运行于 PC 的、可扩展的 Galgame 移植工作台。它负责组织一部视觉小说从原始游戏目录到 Switch 可运行程序、测试、打包和归档的整个流程。

长期目标是：在已支持的引擎范围内，用户选择本地游戏目录、确认识别结果和适配配置后，框架能够自动生成可安装的 NSP；安装后游戏拥有独立的 HOME 菜单图标与名称，点击即可启动，并提供合理的控制器体验。

### 1.1 目标体验

- 游戏能够通过 HOME 菜单中的独立图标直接启动。
- 每部游戏拥有唯一的 Title ID、标题名、图标、配置和存档隔离策略。
- 通用键鼠模拟是默认输入模式，不要求每个游戏先有专门手柄配置。
- 对已经完成适配的游戏，可选用专门的手柄语义映射，并可通过组合键切换模式。
- PC 端工作台能够管理适配器、依赖版本、补丁、构建日志和测试结果。
- 开发阶段优先使用 NRO 与模拟器进行快速迭代；确认运行稳定后，再验证最终 NSP。
- 保留每次构建的输入、配置、工具版本和输出记录，便于复现与回归测试。

### 1.2 非目标（第一阶段不做）

- 不承诺自动兼容任意 Windows 游戏或任意 Galgame 引擎。
- 不在第一阶段自行开发一套通用视觉小说引擎。
- 不把任意进程内存读写、内核级调试或主机系统修改作为框架的前置条件。
- 不先开发复杂 GUI；先以 CLI、配置文件和清晰的构建日志跑通工作流。
- 不把“生成 NSP”与“游戏可运行”视为同一件事。
- 不随框架分发商业游戏原始资源、商业字体、视频、音频、脚本或其他未获授权的数据。

---

## 2. 设计原则

1. **工作台与运行时分离。** PC 端工作台负责编排流程；实际游戏由 Switch 端的引擎或运行时执行。
2. **引擎适配器优先。** 以引擎为单位复用移植成果，必要时允许单个游戏增加独立补丁。
3. **原始游戏目录只读。** 所有修改均发生在由工作台创建的临时或持久化工作区中。
4. **先构建 NRO，再构建 NSP。** NRO 便于调试；NSP 是后续发布和 HOME 菜单体验的构建目标。二者必须区分。
5. **区分转发包与自包含包。** NRO-to-NSP forwarder 仅提供 HOME 菜单入口，通常仍依赖 SD 卡上的 NRO 和其他文件；自包含 NSP 的运行时与资源布局完全不同。
6. **通用输入先行，游戏语义映射可选。** 默认提供键盘/鼠标事件模拟；只有在有适配配置时才启用游戏专用手柄映射。
7. **模拟器和真机测试互补。** 模拟器用于高频功能回归；真实主机用于硬件兼容、性能和最终体验验收。
8. **所有工具链都锁定版本。** 不依赖随时间变化的 `latest` 作为唯一构建基准；记录 Git 提交、release、镜像标签和依赖版本。
9. **许可证和来源可追踪。** 接入第三方引擎或工具时记录许可证、修改内容、上游来源和分发义务。
10. **允许逐步支持不同技术路线。** Web 游戏、开源/重实现引擎、已存在的原生移植和 Windows 兼容运行时不应被强行塞进同一套执行模型。

---

## 3. 总体架构

```text
┌─────────────────────────────────────────────────────────────┐
│                       GalNX Workbench                        │
│                 PC 端 CLI（后续可加 GUI）                    │
├─────────────────────────────────────────────────────────────┤
│ 项目/游戏清单 │ 识别与检查 │ 依赖锁定 │ 构建编排 │ 日志/报告 │
├─────────────────────────────────────────────────────────────┤
│ 引擎适配器注册表                                             │
│  ├─ KiriKiri / KRKR                                           │
│  ├─ Ren'Py                                                     │
│  ├─ NScripter / ONScripter                                     │
│  ├─ Web / HTML5 / TyranoScript / RPG Maker MV 类              │
│  ├─ FVP / rfvp（实验）                                         │
│  └─ Windows 兼容运行时（备选，不作为默认路线）                │
├─────────────────────────────────────────────────────────────┤
│ 通用输入配置 │ 资源布局 │ 补丁管理 │ NRO 构建 │ NSP 打包     │
├─────────────────────────────────────────────────────────────┤
│ 测试后端：Citron／Ryujinx（固定版本）│ 真机部署/日志 │ 结果归档 │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 模块职责建议

| 模块 | 职责 | 第一版要求 |
|---|---|---|
| CLI / Workbench | 接收命令、读取配置、调度任务 | 必须 |
| Game Manifest | 保存游戏身份、引擎、资源路径、图标、输入配置 | 必须 |
| Engine Registry | 注册可用适配器、报告支持范围与依赖 | 必须 |
| Game Analyzer | 扫描目录、根据文件特征辅助判断引擎 | 可从规则式识别开始；必须允许手动指定 |
| Workspace Manager | 创建可清理、可复现的构建工作区 | 必须 |
| Patch Manager | 对运行时/资源应用有版本和哈希记录的补丁 | 第一版可简化，但接口需预留 |
| Input Profiles | 管理键鼠模拟、语义映射和模式切换 | 先定义配置与事件模型，再逐步集成 |
| Build Backend | 调用上游构建脚本/交叉编译器，输出 NRO | 必须 |
| Package Backend | 输出 forwarder NSP 或自包含 NSP；两种模式不能混淆 | 第二阶段接入也可，但接口应预留 |
| Test Backend | 启动模拟器、传入产物、收集日志与退出码 | 第一版至少支持手动/半自动；自动测试逐步增加。【v0.4】测试后端优先级=①Citron Neo（开发循环，实测能跑 Brewser）②本机留档 Ryujinx 1.3.265（第二意见）③真机 NS1（唯一验收权威）；见 §7.6 |
| Device Backend | 真机部署、命令、日志拉取或诊断接口 | 先做明确可控的传输与日志，避免任意内存读写依赖 |
| Artifact Store | 归档二进制、清单、哈希、构建日志、测试结果 | 必须 |

---

## 4. 标准工作流程

### 4.1 游戏导入

1. 用户选择本地游戏目录。
2. 框架扫描目录结构、入口文件、资源文件类型、可执行文件和已知引擎特征。
3. 输出识别建议及不确定项；用户可以手动指定引擎和游戏版本。
4. 创建游戏清单，原始目录保持只读。
5. 检查授权资源是否由用户自行提供；框架只负责处理资源，不内置或代为分发商业游戏文件。

### 4.2 选择适配器与准备工作区

1. 从引擎注册表选择适配器。
2. 检查宿主工具、交叉编译工具、依赖库、SDK/运行时版本和补丁版本。
3. 将依赖固定到明确版本或 commit；缺失时给出可复现的安装/构建提示。
4. 创建独立工作区，复制或引用只读资源，应用补丁和路径/输入配置。
5. 输出 preflight 报告：已满足、警告、阻断构建的问题分开列出。

### 4.3 构建与测试

1. 调用适配器构建 NRO 或其他引擎规定的中间产物。
2. 对产物进行基础检查：文件存在、大小合理、构建退出码为 0、元数据/资源清单完整。
3. 在固定版本的 Ryujinx 中启动，收集模拟器日志、程序日志、退出码和测试记录。
4. 通过后，再向真实 NS1 部署开发版本（通常先用 NRO），验证硬件表现。
5. 修复兼容性问题；补丁、配置或依赖变化后执行受影响测试和必要回归。

### 4.4 打包与验收

1. 选择以下一种构建目标：
   - **NRO 开发包：** 适合快速部署和调试。
   - **NRO-to-NSP forwarder：** HOME 菜单入口，运行文件仍需位于预期路径，不能称为自包含包。
   - **自包含 NSP：** 将目标运行时、配置和所需游戏数据按该引擎支持的布局组织为独立应用包。
2. 生成唯一且无冲突的 Title ID、标题、发布者、图标和版本信息。
3. 检查安装包清单；确认所需资源没有被意外遗漏，也没有把无权分发的游戏内容带入可分发构建。
4. 真机安装并从 HOME 菜单启动最终 NSP；不以模拟器加载 NRO 代替此项验收。
5. 生成报告并归档：源码版本、依赖、补丁、游戏版本/资源哈希、构建日志、测试结果和输出包哈希。

---

## 5. 输入系统草案

### 5.1 基础模式：键盘/鼠标模拟

所有已适配运行时尽可能实现基础输入模式，不要求游戏拥有专门手柄配置。

建议初始默认值（可配置，不作为不可更改的统一标准）：

| Switch 输入 | 基础模式行为（示例） |
|---|---|
| 右摇杆 | 鼠标指针移动 |
| A | 鼠标左键 |
| B | Escape 或鼠标右键，具体由配置选择 |
| X / Y | 可映射为鼠标中键、Enter、Space 等键 |
| 十字键 / 左摇杆 | 方向键或鼠标微调，按游戏类型选择 |
| ZR / ZL | 可映射为按住 Ctrl、Shift、快进键等 |
| 触摸屏 | 鼠标移动、点击；优先保留原生触摸支持 |

实现要求：

- 输入后端要维护明确的 key-down / key-up、mouse-down / mouse-up 状态，避免长按与释放错误。
- 鼠标指针应处理窗口/画面缩放、宽高比和边缘裁切。
- 支持组合键及组合键优先拦截，触发切换的按键不得再被游戏接收。
- 不同运行时可能有不同输入接口；通用层应输出统一事件，再由适配器转换为 SDL、libnx、浏览器 DOM 或引擎内部事件。

### 5.2 可选模式：游戏专用手柄语义映射

仅当该游戏有经过验证的配置时才提供此模式。语义动作例如：

- `advance_text`
- `confirm_choice`
- `back`
- `open_menu`
- `show_history`
- `auto_mode`
- `skip_hold`
- `previous_choice` / `next_choice`

建议提供组合键切换，例如 L + R + PLUS，但最终按键应可配置，并确认不会与目标游戏的常规操作冲突。切换时显示短暂提示。

### 5.3 输入配置优先级

建议采用以下优先级（由高到低）：

1. 单个游戏覆写配置
2. 引擎级默认映射
3. 框架通用默认映射

适配器需声明其支持哪些语义动作和输入能力；若目标不支持某语义动作，构建器应给出警告，而不是静默吞掉映射。

### 5.4 【v0.5】输入层实现进展（M2 交付）

- **数据模型已落地**（`src/galnx/input/`）：4 个内置 profile（`kb_mouse`/`generic-vn`/`krkr-ns`/`krkrsdl2`）、7 个语义动作（`advance_text`/`confirm_choice`/`back`/`open_menu`/`show_history`/`auto_mode`/`skip_hold`）、7 条冲突规则（`button_duplicate`/`button_ambiguous`/`action_unmapped`/`hotkey_duplicate_combo`/`hotkey_overlap`/`adapter_key_ambiguous`/`mouse_pointer_missing`）、manifest `input` 段与 `schemas/input-profile.schema.json`、CLI `galnx input list|validate`（支持 `--json`，rc 0/2）；pytest 87 项 + 11 subtests 通过。详见 `docs/input/README.md`。
- **模拟器侧注入已实测可用**（`scripts/citron_run.sh` 输入模式）：鼠标点击走 SendInput `mouse_event` 有效；键盘 SendInput 到不了 Citron 的 Qt key handler（`src/citron/bootmanager.cpp:505-560` 的 `keyPressEvent` 有 `if (!first_frame) { event->ignore(); return; }`），改 **PostMessage(WM_KEYDOWN/WM_KEYUP)** 有效；必须等游戏首帧且焦点在渲染子窗口。KAG3 demo 上标题页→正文页 diff≈0.554、正文页 A 键/鼠标推进 diff≈0.556 可复现；B(Esc) 隐藏消息层后同值 diff 可复现往返。
- **未落地/未验证**：真机（libnx/SDL 侧）输入语义与组合键拦截（L+R+PLUS 热键吃掉逻辑）、指针缩放与触摸事件在真机上的表现、KAG3 键位未逐键核验（社区常见默认）。语义取证见 `docs/milestones/M2-kag3-input.md`。

---

## 6. Game Manifest 配置样例

以下为第一版的概念示例，字段和格式需在 M0 中再确定；不是与任何现有上游直接兼容的配置格式。

```yaml
schema_version: 1

game:
  id: example_title
  title: Example Title
  publisher: User
  version: "1.0"
  source_dir: "D:/Games/ExampleTitle"
  source_version: "user-supplied"
  # 可选：对关键资源文件生成相对路径 + SHA-256 清单

engine:
  adapter: tyrano_web
  adapter_version: "git:abcdef123456"
  profile: default
  entry: index.html

switch:
  title_id: "0x0100ABCDEF012000" # 示例 ID；实际构建时必须生成并检查冲突
  icon: assets/icon.png
  target: nro_then_nsp
  display_mode: fit
  save_policy: per_title

input:
  default_mode: keyboard_mouse
  toggle_combo: [L, R, PLUS]
  profile: custom_title

build:
  output_dir: "artifacts/example_title"
  reproducible: true
  clean_workspace_before_build: false
```

注意：Title ID 的具体生成规则、合法性与冲突检查必须根据最终采用的打包工具验证，样例值不可直接复用。

---

## 7. 已知工具链与仓库索引

本节用于 Agent 后续调查。链接指向截至文档日期找到的公开仓库或文档。先做仓库健康度、许可证、构建依赖和真实主机状态审查；不要仅凭 README 将项目标记为“可直接使用”。

### 7.1 Switch 通用开发基础

| 工具/仓库 | 地址 | 用途 | 当前判断 / 待验证事项 |
|---|---|---|---|
| devkitPro 文档 | <https://devkitpro.org/wiki/Getting_Started> | Switch Homebrew 编译环境安装入口 | 作为通用工具链安装参考；记录实际安装版本 |
| devkitPro pacman packages | <https://github.com/devkitPro/pacman-packages> | Switch 相关包定义、依赖包构建信息 | 用于核验 SDL2、音视频库等包版本 |
| libnx（Switchbrew） | <https://github.com/switchbrew/libnx> | Horizon OS Homebrew API | 核心依赖；优先通过 devkitPro 的包管理安装，版本锁定 |
| Atmosphère | <https://github.com/Atmosphere-NX/Atmosphere> | NS1 Homebrew 常见的系统环境背景 | 不作为 GalNX 的依赖库；仅记录真机测试所依赖的环境/版本 |
| nx-hbloader 【v0.2 URL 修正】 | <https://github.com/switchbrew/nx-hbloader> | Homebrew NRO 加载相关组件 | 原 `Atmosphere-NX/nx-hbloader` 已 404；真实仓库为 `switchbrew/nx-hbloader`，`v2.4.5 = 82b95122…`（2025-11-15，ISC）。研究 NRO 启动机制时参考；不默认要求修改主机系统 |

**提醒：** 第一版尽量不自行构建或修改 CFW。构建应用优先依赖公开 Homebrew 工具链和普通应用 API。

**【v0.2】devkitPro 实际安装状态（2026-10-29 实测）**

- 已安装于 `D:\devkitPro`（官方安装器 v3.0.3 + 内置 MSYS2）；`switch-dev` 14 个包 / 434.93 MiB：`devkitA64 r30-1`、`devkita64-gcc 16.1.0-1`、`devkita64-binutils 2.46.0-1`、`devkita64-newlib 4.6.0.20260123-4`、`libnx 4.12.0-1`、`deko3d 0.5.0-1`、`switch-cmake 1.5.2-1`、`switch-tools 1.13.1-1` 等。`aarch64-none-elf-gcc 16.1.0`、`nxlink` 验证通过。
- **安装渠道注意**：`pkg.devkitpro.org` 对直连返回 HTTP 403（Cloudflare），而 devkitPro MSYS2 的 login shell 没有代理变量；需在 `D:\devkitPro\msys2\etc\pacman.conf` 的 `XferCommand` 中显式经本地代理 + 浏览器 UA 下载。换机/CI 必须重做，且不能假定代理端口恒定（本机为 `127.0.0.1:7897`）。
- **构建路径不能含空格**：devkitPro 的 make 工程在 `E:\Othergames\Nintendo Switch\...` 下会因 `$(CURDIR)` 空格拆词失败；目录 junction 与 8.3 短路径都被 MSYS2 解析回长物理路径，同样无效。M0 最小构建改在 `E:\galnx-build\m0-hello` 完成（`m0-hello.nro` 166,085 B，sha256 `a341e775…`，make 退出码 0）。
- 详见 `docs/TOOLCHAIN_AUDIT.md` §8 与 `docs/environment/`。

**【v0.4】工具链刷新复核（2026-10-29 联网实测，`docs/audit/05-toolchain-refresh.md`）**

- 本机 17 个 Switch 相关包 **17/17 与上游 dkp-libs.db 一致、0 个可升级** → 工具链未落后；安装器仍是 2018 年的 v3.0.3，但包仓库为滚动发布，安装器版本不决定工具链版本。
- 锁定基线（三位一体）：`pacman -Q` 快照 + `D:\devkitPro\msys2\var\cache\pacman\pkg` 包缓存（64 包含 SHA-256）+ 产物 SHA-256（`m0-hello.nro a341e775…`）；MSYS2 侧 cmake 4.0.2-1 / make 4.4.1-2 落后于仓库最新（4.4.4-1 / 4.4.1-3），不影响 switch-dev，若升级需单独记录。
- **CMake 空格路径实测通过**：devkitPro `$DEVKITPRO/cmake/Switch.cmake` 在含空格目录下 configure+build 均成功（`m0-cmake.nro` 161,989 B，sha256 `f4c08034…`）；受空格限制的只是 make 模板。→ GalNX 构建后端优先采用 CMake。
- libnx 基线仍取 release `v4.12.0 = 7644c9b2`（`b156b477` 为开发提交，若使用须注明）；Atmosphère 1.12.1（2026-10-16，release 声明支持 firmware 23.0.0）、nx-hbmenu v3.6.1、nx-hbloader v2.4.5 仅作测试环境记录，不作依赖。
- 下一步实测：安装 `switch-sdl2 2.28.5-4` + `switch-freetype 2.13.3-1` 做最小 SDL2 窗口+字体链接验证；音视频 portlibs（ffmpeg/libmpv/openal）后置。

### 7.2 现成 Galgame 引擎移植

| 引擎/项目 | 地址 | 用途 / 可复用内容 | 当前判断 / 风险 |
|---|---|---|---|
| KRKR-ns | <https://github.com/DrFlyingPig/krkr-ns> | KiriKiri / KRKR Switch 移植；基于 krkrsdl2，参考 Kirikiroid2；含启动器、平台适配、兼容补丁、插件、构建和测试资料 | **优先研究样板，且已定为第一款原型（v0.2 拍板）**。项目明确标注实验性；需按目标游戏验证 XP3、TJS、插件、视频、E-mote、字体与存档兼容性。真机路径对非 ASCII 字符存在限制。【v0.2 审计】MIT，HEAD `949faf9a`（2026-10-16）；release `v0.1.0` 的 tag 已移动到 HEAD → 发布 NRO 不可按 tag 溯源，M1 只从源码自建；构建需 devkitPro + CMake 3.31.6 + 自建 FFmpeg 7.1，且依赖仓库外的 `Switch.toolchain.cmake`（KRKR-ns-tools） |
| RenpySwitch | <https://github.com/jvrcruzGAMES/RenpySwitch> | Ren'Py Switch 构建流水线；下载 Ren'Py/Pygame 相关源码、应用补丁、编译模块并生成 Switch 项目 | 【v0.2 审计】**无任何 LICENSE（父仓库 knautilus/RenpySwitch 同）→ 法律硬阻塞，取得书面授权前不接入**。Ren'Py 路线已改为**官方源码独立移植**：`renpy/renpy`（主源码）+ `renpy/renpy-build`（构建仓库），可行性见 `docs/audit/04-renpy-official.md`。【v0.3 审计交付】该专项已完成（`docs/audit/04-renpy-official.md`，7 条记录 / 84,638 B，全部 source-inspected）：基线（【v0.4 更正】）`renpy/renpy` 的 GitHub 并无现代 release tag（只有 7.x 及更早旧 tag）；版本由 **`renpy/renpy-build` 的 tag `renpy-8.5.3.26051504`**（annotated tag `0cacf395…` → commit `7bfab40c…`，2026-05-13）定义，对应 `renpy/renpy` 源码 commit `39895c1e…`（2026-05-16）；官方平台表无 Switch 且明确不支持 cross-compiling；**唯一硬阻塞=CPython 3.12.8 交叉到 devkitA64/newlib**；建议先用 4–6 周 go/no-go 探针，未过则改走 Switchroot Android + 官方 Android 构建 |
| Ren2Switch | <https://github.com/Otorhin/Ren2Switch> | Ren'Py 的 Switch 移植/构建工程，fork 自 renpy-switch | 【v0.2 审计】无许可证、2023-09 停更、父仓库 uyjulian/renpy-switch 已 archived → **不接入** |
| ONScripter-NX | <https://github.com/clamintus/onscripter-nx> | 较旧 ONScripter 版本的 Switch 移植，目标是兼容部分旧 NScripter 游戏；支持触摸与特定控制器操作 | 【v0.2 审计】GPL-2.0-or-later，`v0.3.1 = a8439a86…`（2026-01-14）；构建最简单（make）；但 release 附商业游戏数据 zip（**禁止复用资产**），字体许可未核实。**第二接入候选（视 GPL 决策）** |
| RFVP / rfvp | <https://github.com/xmoezzz/rfvp> | Rust 编写的非官方 FVP 引擎及工具重实现；目标包含 FVP 脚本/资源格式 | **实验研究项，不作为首个里程碑依赖**。仓库列出 Switch NRO 为 experimental，且说明尚未在真实 Switch 上运行。【v0.2 审计】MPL-2.0，`0.7.0 = 99435f22…`（2026-10-19）；需 Rust nightly + build-std + 自定义 target；releases 无 Switch NRO。【v0.7 实测·M5-a】构建闭环已打通（pin `nightly-2026-02-01` + devkitA64 r30 → `rfvp.nro` 1,372,216 B sha256 `4964dda9…`；Windows 需 `build.rs` 的 `.exe` 探测补丁），Citron 渲染 Luax Painter（17.5 fps）且注入 M=Plus 触发 `quit requested by host event`（输入链路成立），PC host `no_std_harness` 2/3 通过；结论=继续研究（P3 研究项），不做首款原型（真实 FVP 内容/性能/真机未验证，见 `docs/builds/008-rfvp-evaluation.md`、`docs/milestones/M5-fvp.md`） 【v1.10 实测·M5-c】Switch 渲染后端由 CPU 软光栅改为 **SDL2/GLES2**（`platform/switch/runtime/sdl_video.c` C shim + `host/src/render.rs` 转发 + `runtime/main.c` SDL 主循环；libnx 只保留输入/音频），Citron 实测 **60.0 fps**（原 17–19 fps）、render 15.57 ms（含 vsync），标题与中文正文正确；NRO 7,823,416 B sha256 `e3acbce4…`；仍为研究项（真机/音频/CJK/手柄/内存未验，`docs/builds/016-rfvp-sdl2-backend.md`）。 |

**【v0.4】引擎路线复核（2026-10-29 联网实测，`docs/audit/06-engines-refresh.md`，14 条记录）**

- **重大更正：krkrsdl2 上游本体已官方支持 Switch**——`CMakeLists.txt` 含 `if(NINTENDO_SWITCH)` 分支（SWITCH_APP_NAME "Kirikiri SDL2"、作者 uyjulian、`SWITCH_VERSION v2.0.0`、nacptool+elf2nro），`.github/workflows/ci.yml` 矩阵含 `switch`（容器 `devkitpro/devkita64:20241023`），release tag `latest` 附 `krkrsdl2.nro` 12,011,585 B。但 README 完全不提 Switch 且原文声明不支持未修改商业游戏 → 属“有实现、无文档”，随时可能被移除。
  → **第一款原型策略改为双层**：① **krkrsdl2 上游先行**（MIT、CI 出包、可复现；`main HEAD 124bdf84…`，2026-10-01）验证“自有 data.xp3 → NRO”最小闭环；② **krkr-ns 作产品化启动器**（启动器/存档隔离/E-mote/AlphaMovie/LayerExRaster 等增量，`949faf9a…`、实验性、构建依赖仓库外 `KRKR-ns-tools` 与兄弟仓库 `WA2-ns`）。上游 NRO 是单游戏内嵌（`-DEMBED_DATA_PATH=data.xp3`）形态，没有多游戏启动器，因此两者不可互相替代。
- **新增候选（06 §2）**：① `wetor/ONScripter-jh-Switch`（GPL-2.0，`v21.2.1` = annotated `15a6fec3…` → commit `573301c1…`（2026-02-01）；NRO 16,735,572 B；中文 UI + 游戏浏览器；ONScripter Yuri 系，活跃度优于 ONScripter-NX）；② `Erige005/Kirikiroid2-NX`（Kirikiroid2 1.3.9 移植，KiriKiri 自定义 BSD-style 许可，`v1.0.1` = `e96b6034…`，NRO 42,338,934 B；插件缺 E-mote/motion player/scriptsEx 等；构建链最重且需官方 APK 资源）；③ `xmoezzz/siglus_rs`（MPL-2.0，`5f358ef1…`，pre-release `siglus-switch.nro` 14,531,824 B，deko3d 渲染，未真机）。
- **ONScripter 双实现法务注意**：两者的 `COPYING` 均判 **GPL-2.0-only**（无 “or later”）；ONScripter-NX release 内嵌月姬/歌月十夜商业数据 → 只能本地取引擎部分，**禁止下载/再分发其数据 zip**。
- **Ren'Py 复核结论（06 §8）**：8.5.3.26051504 仍是官方最新稳定（SDL2），master `8.99.99` 已全面迁 SDL3 → **移植基线锁 8.5.3，禁止用 master**；官方平台矩阵仍无 Switch；4 个社区移植与 NXPython 逐一复核仍**全部无 LICENSE** → 法律阻塞未解除，继续只作技术参考、禁止接码。
- **版本锁定基线（06 §8.1）**：krkr-ns `949faf9a`（release v0.1.0 的 published/created 时间戳矛盾，资产 2026-10-16 上传，**禁止只按 tag 溯源**）；krkrsdl2 `124bdf84` 或 CI 镜像 `devkitpro/devkita64:20241023`；ONScripter-NX `a8439a86`；ONScripter-jh `35f55c89`（`573301c1` 为 tag 指向 commit）；rfvp `9f07adef` + nightly；siglus_rs `5f358ef1`；Ren'Py 官方 `39895c1e` + renpy-build `7bfab40c`。
- **接入排序（06 §5.1 修订）**：krkrsdl2 上游 → krkr-ns → ONScripter-jh / ONScripter-NX（二选一，接受 GPL-2.0）→ Kirikiroid2-NX（非 SPDX + 重构建链，第三梯队）→ rfvp / siglus_rs（研究项，均未真机、不进首批）→ Ren'Py 独立移植（长期，先解 CPython 交叉）。社区 Ren'Py 移植与 NXPython **一律不接入**。【v1.10】rfvp 的性能门槛已解决（60.0 fps），但真机 / 音频 / CJK / 输入语义仍未验证，**排序不变**（仍在研究项、不进首批）；SDL2/GLES2 后端使「研究项」与「可玩」之间的差距只剩前端与内容侧。【v1.11】手柄语义与快捷存读档（patch J）在 Citron 实测打通，「可玩」剩下的门槛已收窄为**游戏自带槽位 UI 未移植**（Switch 只能落引擎快速槽 0）、音频与真机；排序仍不变。【v1.12】romfs 自包含 NSP（9,979,435,224 B）已在 Citron 双形态验证，rfvp 的「打包」门槛关闭；距「可交付真机」只剩真机安装、音频/movie、4 GB 内存余量，排序仍不变。

- **【v0.6 实测·M4-c】ONScripter-NX 构建与运行闭环（2026-10-30，`docs/builds/007-onscripter-nx.md`）**：源码 HEAD `a8439a86393f74c503d28df176f010ca544af56f`（2026-01-14），**零源码修改**，devkitPro MSYS2 `make -j16` clean build 20 s；自建合法 NScript 测试内容（`0.txt` 418 B / `bg.png` 10,854 B，MIT）内嵌 romfs → `m4-ons-with-content.nro` 10,449,140 B sha256 `d8f9bb11…`。Citron `0237a9b88` 实测 R1–R5 全部通过：R1 启动渲染、R2 翻页后出现 Branch A/B 选项（diff 0.01296）、R3 方向键定位+确认进入 Branch B、R5 再确认 Branch A；负结果 R4a=只按确认键不按方向键时 RETURN 不确认选项（光标需方向键定位）。结论：**ONScripter-NX = 正式适配候选（P2，有条件）**，前置条件=上游无启动器/多游戏管理、无 KAG 式菜单与存档 UI（需 GalNX 自建）、GPL-2.0-or-later 传染需法务确认、真机与 HD 内容 CPU 代价未验证。v0.4 接入排序不变。- **合法测试资源（06 §6，待用户核实）**：首选自建 Ren'Py 工程（生成项目文件 CC0 1.0）；其次 krkrsdl2-kag3-demo（KAG3 自定义“自由修改/分发”条款、非 SPDX，内嵌字体许可需单独核实）；官方 SDK 示例 `the_question`/`tutorial` 资产无明确许可，**仅本地测试**。
- **硬限制（产品级）**：krkr-ns 真机路径（游戏目录/入口 .xp3/SD 路径）不得含中文；必须 .xp3 入口；HBMenu 需按住 R 以完整内存模式加载 NRO。

### 7.3 Web / JavaScript 运行时与游戏专用样板

| 工具/仓库 | 地址 | 用途 / 可复用内容 | 当前判断 / 风险 |
|---|---|---|---|
| Brewser | <https://github.com/natureglass/Brewser> | 面向 Switch 的完整 Web runtime 外壳；可参考离线 Web 应用的运行、发布和应用管理 | 【v0.2 审计】MPL-2.0（LICENSE 为准；package.json 写 MIT 属冲突）；`v0.1.1.31 = 8040580e…`（2026-09-17；release 名称 `Brewser v0.1.131`）；`brewser.nro` 76,546,123 B / sha256 `8ce31f5b…`，另带 `brewser-forwarder.nsp`；默认 `make` 只需 node/npm/python（复用预编译引擎），重建引擎才需 devkitPro。**M4 首选评估对象**；但 shell 运行时源码/@switch-web/runtime 不可得，不能作发布依赖。 |
| nx.js_extended | <https://github.com/natureglass/nx.js_extended> | Brewser 背后的扩展 JavaScript/Web 技术运行时之一，包含 V8、Skia、WebGL 等能力和相应自定义依赖 | 【v0.2 审计】MIT，`f41fb550`（v1.0.0-beta.6）；引擎为 switch-v8 15.0.243-9 + switch-skia 149-3 + Mesa Nouveau，版本不可随意升。私有 `@switch-web/runtime` 源码不可得 → **不作发布依赖**；上游通用底座为 `TooTallNate/nx.js`（MIT，`v1.0.0-beta.7 = a649611a…`，无 DOM/CSS，可作 HTML5/Canvas 底座） |
| BurialNX | <https://github.com/ETCHDEV/BurialNX> | 基于 nx.js 的 Switch Homebrew loader，面向特定 RPG Maker MV 游戏；有输入、显示、存档路径与诊断示例 | **仅作架构/诊断参考，不应当当作通用 RPG Maker MV 引擎**。仓库明确声明是针对特定游戏的专用运行时，其他游戏不受支持。【v0.2 审计】AGPL-3.0-or-later，`v0.1.1 = c2c6691c…`（2026-10-19）→ **禁止引代码**，只参考设计 |

**Web 方向初步假设：** 某些 HTML5/TyranoScript 游戏可能适合通过 Web runtime 适配，而不必移植 Electron 本身。但每个游戏仍要核验其实际发行版本、Electron/NW.js 特有 API、Node API、插件、文件系统访问和存档机制。不得只凭 `index.html` 存在就认定可以直接运行。

**【v0.2 决策】** Web 方向先做“可行性小验证”而不是直接接引擎：用已校验的 Brewser `brewser.nro` 在本机 Ryujinx 上跑最小 HTML 页（DOM+canvas+JS），实测通过后 M4 再谈 RPG Maker MV；Teaching Feeling 是否为合适首目标待其发行包结构核验。证据与结论见 `docs/experiments/web-01-brewser-smoke.md`。

**【v0.3 实测·阻塞】Web 冒烟结论（2026-10-29）：** 本机 Ryujinx Canary 1.3.265 能正常加载普通 homebrew（nx-hbmenu v3.6.1、hb-appstore v2.3.2 均 `Application Loaded` 并渲染），但 **nx.js 系 NRO 稳定停滞在 `LoadGuestApplication: Loading as homebrew.` 之后**：Brewser `brewser.nro`（76,546,123 B，sha256 `8ce31f5b…`，与 release digest 三方一致）3 次、上游 nx.js beta.7 2 次复现；SD 卡无 `switch/brewser/` seed → 主程序从未执行。差异线索：失败 NRO 代码段约 44 MB（对照 1.7/7.3 MB），根因未定位；约 127 s 后的 `HLE Process map ... process with ID 0` 异常属 Ryujinx 自身 bug（关 discord 集成仍复现）。**结论边界：不能据此判定 Brewser/Web 路线可行或不可行**（Brewser 运行时能力全部未验证，verification_level=`not-verified`）。M4 验证改走：真机（Atmosphère 1.10+ + hbmenu，完整内存 application mode）优先，或换模拟器/版本并用 hbmenu/appstore 作“加载链路健康检查”对照。实验记录：`docs/experiments/web-01-brewser-smoke.md`（158 行）。

**【v0.4 实测·恢复】Web 路线模拟器侧已打通（2026-10-29，`docs/audit/07-web-citron.md` + `docs/experiments/web-02-citron-smoke.md`）**

- 换用 **Citron Neo nightly `0237a9b88`**（Windows msvc / Vulkan 后端）后，Brewser v0.1.131 预编译 NRO **完整运行、2/2 复现**：DOM＋CSS＋inline JS＋`setInterval`＋rAF＋Canvas2D＋`localStorage` 全通过，WebGL 上下文 `OpenGL ES 3.2 Mesa 20.1.0-rc3`；Brewser 完成 `sdmc:/switch/brewser/` 首次 seed（`seed-fingerprint`、`shell/home.html` 39,591 B）→ 主程序真实执行。web-01 在 Ryujinx 上的停滞归因为**模拟器环境问题**，不是 Brewser 缺陷。
- 版本锁定必须锁**资产 SHA-256**：release tag `2026-04-27 = 0076ee8f` 与 Windows 资产的构建 commit `0237a9b88` 不一致 → 基线为 `Citron-windows-nightly-0237a9b88-x64-msvc.zip` 40,497,628 B、sha256 `0d2c9bf3…`，运行后用日志确认 `citron Development Build | main-0237a9b88`。
- M4 开发循环 = Citron（Brewser 官方 `make sdmc`）+ CI 冒烟三件套（窗口标题含 `brewser (64-bit)`；日志含 `Loading brewser (01F5905036D20000)` 与 `Booting game`；`seed-fingerprint` 生成）；Ryujinx 1.3.265 降为第二意见/回归对照；**真机仍是最终验收门槛**（模拟器无固件、硬编码 22.0.0-3.0，显卡/驱动路径与 Tegra X1 不同）。
- 仍未验证：Brewser 私有 `@switch-web/runtime` 源码不可得（不作发布依赖）；RPG Maker MV/TyranoScript 兼容层未验证；输入/音频/联网/长时稳定未测。

- **【v0.6 实测·M4-b】Brewser Web 适配器端到端（2026-10-30，`docs/builds/006-brewser-web-adapter.md`）**：自建合法 Web VN 内容包（MIT，`examples/web-vn/`）按 Brewser 约定放 `sdmc:/switch/brewser/apps/<appId>/{manifest.json,index.html,assets/}`，并在 `sdmc:/switch/brewser/configs/config.json` 设 `autorunApp` 直接进入页面（与 `brewser://apps/<appId>/index.html` 同源，实测生效）；无需 devkitPro / `make sdmc`。Citron `0237a9b88` 实跑 brewser.nro：status=loaded、窗口标题含 `brewser (64-bit)`、boot 行 `Booting game: 01F5905036D20000`、37 s；9 次输入把 title→scene1→scene2→scene3→endingA/endingB 两分支稳定复现。页内 `localStorage` 正常（SAVE=present），但 `apps/<id>/localStorage/` 运行中为空 → **跨 run 落盘未验证（M4 存档阻塞项）**；DOM `<button>` 点击存在坐标偏移（实测 css≈0.8514×client−93.9/−61.0）→ 判定改为点击屏幕左右半区，不得写成 DOM 按钮点击已通；真机/纯触摸/WebGL 像素级/性能未验证。
### 7.4 Windows PC 兼容运行时（备选路线）

| 工具/仓库 | 地址 | 用途 / 可复用内容 | 当前判断 / 风险 |
|---|---|---|---|
| Autorun（原 Wine-NX） | <https://github.com/autorunhq/autorun> | 在 Switch Horizon OS 上运行 Windows 程序；组合 Wine、CPU 翻译、Mesa、DXVK/VKD3D-Proton 等 | 实验性兼容路线。适合评估缺少原生移植的游戏，不作为默认 Galgame 执行方案。需按游戏逐一测试性能和 API 兼容性 |
| Autorun DLL 仓库 | <https://github.com/autorunhq/autorun-horizon-dlls> | Autorun 使用的 Windows DLL / 运行环境内容 | 作为 Autorun 构建依赖参考；锁定版本，不在本项目中自行复制/分发不符合其许可证的文件 |
| Carafe | <https://github.com/carafe-nx/carafe> | PC 桌面工具，将 Windows 游戏文件夹与 Autorun 运行时/配置制作成独立 NSP；使用者可以设置游戏名和图标 | 是“PC 工作台→独立 NSP”概念的直接参考。重点研究其任务编排、元数据生成、构建日志和打包依赖，不要假设其 Windows 兼容运行适用于每部 Galgame |
| Carafe 构建依赖说明 | 同上仓库 `CONTRIBUTING.md` / `runtime` 目录 | Docker、Node、Rust、hacBrewPack 等构建链 | 后续按其锁定的版本与许可证做依赖审查 |

### 7.5 NRO / NSP 与应用打包

| 工具/仓库 | 地址 | 用途 | 限制/注意事项 |
|---|---|---|---|
| NTON | <https://github.com/rlaphoenix/nton> | PC 端 NRO-to-NSP forwarder 生成器；可设置标题、图标、Title ID 等 | **生成的是转发器，不是把 NRO/游戏资源自动装进 NSP 的自包含包**；运行时仍依赖 SD 卡上固定路径的 NRO。其 README 明确提示此类 NSP 安装可能有主机封禁风险，需纳入风险说明。【v0.2 审计】GPL-3.0，`v3.0.1 = c5d543a9…`（2026-09-15）；Windows PyInstaller；需 prod.keys；FW 12.0.0+ → **仅作对照，不作主路线** |
| hacBrewPack（NTON 所用） | <https://github.com/rlaphoenix/hacBrewPack> | NSP 构建工具，供 NTON 等项目打包使用 | 接入前确认上游来源、许可证、所需输入/密钥处理方式和当前兼容性；不要将 forwarder 与完整自包含应用混为一谈。【v0.2 审计】GPL-2.0，`v3.05 = 745b16ec…`（代码停 2019-10，2026-09 由 rlaphoenix 镜像重建）；C/Makefile，CLI 支持 `--exefsdir/--romfsdir/--titleid/--titlename` 等；需 header_key + key_area_key；输出 RSA-PSS 随机盐**非确定性**。主路线采用“子进程调用”，不把 GPL 代码并入 GalNX |
| nstool | <https://github.com/jakcron/nstool> | NSP/NRO 等相关文件的信息提取与检查工具；NTON 的依赖之一 | 用于构建产物检测时需要固定版本并验证读取范围。【v0.2 审计】MIT，`v1.9.2 = e89ea84b…`（2024-10-14）；默认分支 `development-tip`（锁版本只用 tag）；`-y` 校验不需密钥 → 作为**产物验证第一步** |
| switch-nsp-forwarder | <https://github.com/TooTallNate/switch-nsp-forwarder> | NRO forwarder 的模板/相关实现，可研究启动入口 | 仅是转发路线的参考；需单独检查许可证、兼容性和系统风险。【v0.2 审计】`0.0.8 = 61edd504…`（2026-05-03）；无根 LICENSE，仅 package.json 声明 MIT；TitleID 由 NRO 路径 SHA-256 派生（与 sphaira 一致）→ 只引用其模板思路 |
| nx-link / nxlink 【v0.2 归属修正】 | 上游 `switchbrew/switch-tools`（<https://github.com/switchbrew/switch-tools>），devkitPro 包名 `switch-tools` | 将 homebrew 构建产物通过网络传输/启动，辅助快速调试 | 【v0.2 实测】本机 devkitPro 已装 `switch-tools 1.13.1-1`（v1.13.1 = `22756068…`，2024-10-23，ISC）；命令 `nxlink [-a addr] [-p port] [-s] nro`，`-s` 可回收程序 stdout/stderr（开发期日志通道）。不得硬编码只适用于某一主机地址的参数 |

**【v0.2 决策】NSP 首个目标 = 自包含包（非 forwarder）。** 路线=ExeFS 启动器 + RomFS 游戏数据，由 GalNX 编排 `hacBrewPack`（子进程）+ `nstool`（产物校验）生成，可控制 HOME 图标/名称/存档命名空间；前置条件=用户自备 `prod.keys`（**绝不入库/绝不注入 CI**）+ CFW/sigpatches。forwarder（NTON 路线）只作对照实验，因其仍依赖 SD 卡上固定路径的 NRO、且上游 README 明确提示封禁与 DMCA 风险。详见 `docs/TOOLCHAIN_AUDIT.md` §4.D 与附录 B。

**【v0.4 复核】打包链未变 + keys 合规策略（`docs/audit/08-packaging-refresh.md`，2026-10-29 联网复核）**

- 打包链与测试后端版本自 v0.3 起**无变化**：hacBrewPack v3.05=`745b16ec`、nstool v1.9.2=`e89ea84b`、NTON v3.0.1=`c5d543a9`、switch-nsp-forwarder 0.0.8=`61edd504`、Carafe v0.4.0=`9b69701b`、Autorun test-build-4=`9b717050`；新增登记：nx-hbmenu v3.6.1=`fd26270a`、nx-hbloader v2.4.5=`82b95122`、DBI 912ru=`e5ba7324`（**无许可证，不可分发**）、hb-appstore v2.3.2（停更，可选）。
- **keys 策略（已拍板）**：本机可用 Ryujinx 自带 `portable/system/prod.keys`（12,007 B，sha256 `7bb3b6d2…`；221 条 key 名，含 `header_key` 与 `key_area_key_application_00–15`）与 `title.keys`（11,492 B，sha256 `2b338398…`；打包不需要）。GalNX 只通过 `GALNX_PROD_KEYS` 只读路径读取，只记录 path+size+SHA-256；**不入库、不打印、不进日志/CI、不随产物分发**，`.gitignore` 覆盖 `*.keys`。
- **【v0.5 实测修正】环境变量通道不可用**：本机 DSH 运行时会从子进程环境中剔除名字匹配 `KEY/PASSWORD/SECRET/TOKEN` 的变量 → 计划中的 `GALNX_PROD_KEYS` 环境变量在本环境不可靠。改为**显式命令行参数**：`hacBrewPack --keyset <path>` / `nstool -k <path>`，脚本不内置默认路径、不 fallback；PROVENANCE 仍只记 path+size+SHA-256+mtime。实测可用 keyset：`E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys`（12,007 B，sha256 `7bb3b6d2…`）与 `C:/Users/<user>/AppData/Roaming/citron/keys/prod.keys`（同尺寸，同目录 `title.keys` 11,492 B）。注意：`C:/Users/<user>/.switch/prod.keys` **不存在**（旧记录有误）。
- **【v0.5 实测】hacBrewPack 强制要求 keyset**：即使 `--plaintext` 也报 `Error: Unable to open keyset file`（rc=1）；README 要求 `header_key` + `key_area_key_application_xx`。因此离线/CI 冒烟改用**合成 keyset 模式**，产物标 `NOT INSTALLABLE`，不得作为验收证据。
- **【v0.5 完成】自包含 NSP 出包链已打通**（M3-a，`docs/builds/005-nsp-selfcontained.md`）：ELF→`elf2nso`/`npdmtool`/`nacptool`→hacBrewPack→nstool 校验；产物 PFS0 含 Program/Control/Meta 三个 NCA，CNMT 的 ContentInfo 哈希与实际 NCA SHA-256 逐字节一致；两次构建 SHA-256 不同（非确定性已验证）。产物**未签名**（NCA Header / ACID Signature FAIL 属预期）→ 真机安装需 CFW+sigpatches（M3-d 待用户设备）。
- Lockpick_RCM 仓库已被 DMCA（`shchmue/Lockpick_RCM` HTTP 451，2023-05-04 Nintendo）→ 文档只写社区通行提取步骤概要，不提供下载源、不内置 payload；真机安装仍需 CFW + sigpatches。
- NSP 自包含契约：ExeFS(`main`+`main.npdm`) + control(`control.nacp`+256×256 JPEG 图标) + RomFS(+可选 logo)；输出**非确定性**（RSA-PSS 随机盐）→ 验收用 nstool 结构校验，不做 bitwise 对比；Windows 259 B 路径上限；hacBrewPack 会就地修改输入 → 必须传副本。M3 仍缺：hacBrewPack 二进制来源+哈希、真机 CFW/sigpatches 记录、端到端打包实测。

### 7.6 模拟器测试环境

| 工具/源码 | 地址 | 用途 | 当前判断 / 风险 |
|---|---|---|---|
| Ryujinx Canary-1.3.265 源码标签镜像 | <https://gitlab.hugofnm.fr/publicmirrors/Ryujinx/-/tags/Canary-1.3.265> | 用户已找到 1.3.265 构建产物；该镜像列出 `Canary-1.3.265` 标签，对应提交 `4e81a4c2` | 这是第三方公开镜像，不应无条件视为官方可信源。第一步验证源码快照、标签、提交和构建产物的对应关系，并保存本地 commit hash。【v0.2 实测】**该镜像匿名访问需登录（网页 302→登录页、GitLab API 404）**；官方 `git.ryujinx.app` 当前 TLS 不可达；GitHub `ryujinx-mirror/ryujinx` 已被 DMCA 屏蔽（451，2025-03-06 Nintendo）、`Ryubing/ryujinx` 404 → **官方 tag↔commit 的独立核验本轮未完成**。本机证据内部一致：`Ryujinx.exe` ProductVersion `1.3.265+4e81a4c`，同目录源码 zip 的 7z 归档 Comment=`4e81a4c2f4fee6f31e28fbb129759ec2369da6eb`。策略=本机二进制+源码 zip 只读留档 + SHA-256 校验 + 断网禁更新，证据等级标 `not-verified` |
| Ryujinx 项目说明 | <https://github.com/Ryujinx> | 原项目公告称原始 Ryujinx 项目已停止，建议关注 Ryubing 或 ryujinx-mirror | 测试环境应按具体分支/commit 固定；不要把“Ryujinx”抽象成永远不变的单一版本。【v0.2 实测】原组织 GitHub 仅剩 `.github` 仓库；现状=`Ryubing` fork（自管 GitLab `git.ryujinx.app`，MIT）+ 本机 1.3.265 留档。更新端点 `update.ryujinx.app` 在本机日志中 SSL 失败 → 按“离线固定环境”使用 |
| Citron Neo（第二测试后端）【v0.4 新增】 | <https://github.com/citron-neo/emulator> | Switch 模拟器（Citron 代码库续作）；Web/Brewser 开发循环与回归冒烟 | 【v0.4 实测】GPL-3.0-or-later；HEAD `c3aa70f8`（2026-10-25），597★/93 open，**无公开 CI**；最新 release tag `2026-04-27 = 0076ee8f`，但 Windows 资产构建 commit 为 `0237a9b88`（≠ tag）→ 锁资产 `Citron-windows-nightly-0237a9b88-x64-msvc.zip` 40,497,628 B / sha256 `0d2c9bf3…`。实测能完整运行 Brewser v0.1.131（见 §7.3）。**仅作外部工具，不捆绑不分发其代码，GPL 不传染；模拟器≠真机** |

**模拟器使用原则：** 将其作为回归测试工具，而非真机兼容性的最终裁判。模拟器配置、固件/密钥来源和测试 ROM/游戏数据由使用者自行合法准备；框架不应将其纳入公开发布包。

**【v0.2 实测】启动方式与已知坑：** 必须以**非管理员**启动（`E:\Othergames\Nintendo Switch\Ryujinx-canary\Run.bat` 用 `runas /trustlevel:0x20000` 降权；直接以管理员运行会报 “Ryujinx is not intended to be run as administrator.”）。若报 CET/硬件强制堆栈保护错误，按 `启动不了的解决办法.txt` 在 Windows 安全中心→Exploit Protection 中为该 exe 关闭硬件强制堆栈保护。自动化测试时的日志目录=`portable/Logs/`，文件名含版本与时间戳。

**【v0.4】模拟器生态现状（2026-10-29 联网核查）：** `suyu-emu/suyu` 已被 DMCA（GitHub 451）、`Eden-Emulator/eden` / `sudachi-emu/sudachi` / `Ryubing/CANARY` 均 404、Ryujinx 上游 TLS 不可达且镜像需登录/GitHub mirror 451 → **当前可公开访问的活跃开源 Switch 模拟器只剩 Citron Neo**。因此测试环境必须依赖本机留档 + 资产 SHA-256，不假定可在线获取；无论 Citron 还是 Ryujinx，都不能替代真机验收。

**【v0.5】Citron 自动化 harness（`scripts/citron_run.sh`，819 行）**：非管理员启动（`runas /trustlevel:0x20000`）、sdcard staging、`PrintWindow` 截图、日志切片、单行 JSON 结果、失败码（`no_window_or_boot`/`citron_already_running`/`input_helper_failed` 等）；支持 `--nro` 与 `--game/--nsp`（NSP 以 `-g` 直接加载），输入注入 `--input-click X,Y` / `--input-keys LIST`。**Citron 为单实例**（yuzu 血统，第二个实例只做转发）→ 并发任务必须时间窗排队：跑前 `tasklist | findstr /i citron` 确认 0 实例、以 `citron_already_running` 失败码为准，禁止 `--allow-existing` 抢占或 kill 他人进程。**M3-b 实测**：自包含 NSP 被 Citron 直接加载并运行（窗口标题 `m0-hello (64-bit) | 1.0.0`、日志 `Booting game: 0100000000001000 | m0-hello`、画面渲染 `Hello World!`）→ 未签名 homebrew NSP 在模拟器可运行，但**不能据此认定真机可安装**。详见 `docs/environment/citron-harness.md` 与 `docs/milestones/M3-nsp.md`。

### 7.7 可作为旁支研究、但暂不进入 GalNX 核心的工具

| 项目 | 地址 | 与本项目的关系 | 结论 |
|---|---|---|---|
| ReXGlue SDK | <https://github.com/rexglue/rexglue-sdk> | Xbox 360 PowerPC 静态重编译工具/运行时 | 主要针对 Xbox 360 游戏，不是 Galgame 核心路线；仅在之后研究主机版本代码重编译时参考 |
| XenonRecomp | <https://github.com/hedge-dev/XenonRecomp> | Xbox 360 机器码转 C++ 的静态重编译工具 | 不列入第一阶段依赖 |
| XenosRecomp | <https://github.com/hedge-dev/XenosRecomp> | Xbox 360 Xenos 着色器转换工具 | 不列入第一阶段依赖 |

---

## 8. 主机调试、存储与内存访问策略

### 8.1 第一阶段必须有的调试能力

- 运行时日志：初始化、资源加载、输入事件、存档、异常和退出原因。
- 日志导出：写入 SD 卡，或通过受控网络通道回传 PC。
- 可选诊断接口：报告引擎版本、游戏场景、FPS/帧时间、内存水位、当前输入模式、资源加载失败等。
- 构建产物部署、日志拉取与测试报告归档。
- 运行时崩溃后保留最近一段日志；敏感路径和用户内容可选择性脱敏。

### 8.2 不作为前置条件的能力

- 对任意游戏进程做无约束的内存读写。
- 修改任意主机进程或系统状态。
- 依赖未核实的特权接口来完成普通测试。

优先在自己控制的运行时中实现调试命令和诊断点。这比外部随意修改地址更容易复现，也更不容易因版本变化而失效。若后续确有需要，再独立评估合法、受控的调试方案。

---

## 9. 测试策略与验收矩阵

### 9.1 统一测试层次

1. **静态/预检：** 资源清单、配置格式、Title ID 冲突、依赖检查、构建工具版本检查。
2. **构建测试：** 适配器构建成功、输出文件存在、日志不含已知阻断错误、资源布局齐备。
3. **模拟器冒烟测试：** 启动、标题画面、输入、存档、音频、返回/退出、日志导出。
4. **真机冒烟测试：** 在实际使用模式启动，验证内存模式、性能、手柄、触摸、音视频和长时间稳定性。
5. **最终 NSP 验收：** 独立图标、名称、Title ID、安装、HOME 菜单直接启动、存档隔离、卸载/重装行为。
6. **回归测试：** 引擎、输入层、打包器或工具链变更后，重新运行受影响的测试集。

### 9.2 第一部游戏的最低验收标准

- 原始游戏目录不被修改。
- 通过一个命令或一份声明式配置完成预检和构建。
- 可以生成有效的 NRO。
- 能在固定版模拟器上启动，并且日志可以被框架收集。
- 能在真实 NS1 上手动完成基本流程；模拟器通过不代表此项自动通过。
- 基础键鼠模式可推进文本、点击选项、操作菜单和退出游戏。
- 若该游戏完成语义映射，则可通过组合键切换模式，且切换热键不会误传给游戏。
- 存档可持久化并与其他游戏隔离。
- 生成的 NSP 类型明确标识为 forwarder 或自包含包。
- 真机安装后的 HOME 菜单图标与标题正常；点击可启动预期游戏。
- 保存依赖版本、源码 commit、构建日志、游戏资源哈希和测试结果。

---

## 10. 里程碑草案

### M0：框架骨架和工具链审计

**工作项**

- [x] 【v0.2 已完成】选定项目语言和最小 CLI 方案：**Python CLI**；所有耗时工作通过子进程调用上游工具。
- [ ] 建立仓库结构、配置 schema、日志格式、工作区策略、引擎注册机制（仓库骨架与 `docs/` 已建，schema/CLI 待实现）。
- [x] 【v0.2 已完成】固定 devkitPro/libnx 版本、一个模拟器版本和构建环境说明（见 `docs/TOOLCHAIN_AUDIT.md` §8、`docs/environment/`；模拟器按本机 1.3.265 留档，标 `not-verified`）。
- [x] 【v0.2 已完成】对 §7 全部仓库（含 krkr-ns、RenpySwitch、Brewser/nx.js_extended、NTON/hacBrewPack、Carafe、Autorun、Ryujinx）做状态/许可证/构建可行性审计 → `docs/TOOLCHAIN_AUDIT.md` v1.1（26 个上游对象 / 27 条记录）。
- [x] 【v0.2 已完成】Ren'Py 官方源码独立移植可行性专项审计（`docs/audit/04-renpy-official.md`）。
- [x] 【v0.4 完成】Brewser 最小 Web 冒烟实验：web-01 在 Ryujinx 上阻塞（`not-verified`），web-02 换 Citron Neo 后**通过（2/2）**（见 §7.3）；记录 `docs/experiments/web-01-brewser-smoke.md`、`docs/experiments/web-02-citron-smoke.md`。
- [x] 【v0.4 完成】模拟器最小启动测试：Citron Neo nightly 成功加载运行 hbmenu v3.6.1、hb-appstore v2.3.2、Brewser v0.1.131 等 homebrew NRO（日志+截图见 `workspaces/web-02/evidence/`）；Ryujinx 1.3.265 亦能加载 hbmenu/appstore。**残余**：`m0-hello.nro` 尚未单独冒烟 → 移入 M1 首项。

**已完成验收（2026-10-29 实测）**

- devkitPro Switch 工具链补全并验证：`switch-dev` 14 包 / 434.93 MiB；`aarch64-none-elf-gcc 16.1.0`、`libnx 4.12.0-1`、`nxlink` 可用。
- 最小 Homebrew 构建通过：`m0-hello.nro` 166,085 B / sha256 `a341e775…`，`make` 退出码 0（构建须在无空格路径，见 `workspaces/m0-hello/`）。
- 第一轮审计文档 v1.1 提交；全部 27 条记录带 URL、commit/tag、最后验证日期与许可证字段。
- 【v0.4】4 份联网复核报告落盘：`docs/audit/05-toolchain-refresh.md`（工具链未落后 + CMake 空格路径通过）、`06-engines-refresh.md`（引擎路线复核）、`07-web-citron.md`（Citron 审计 + Web 冒烟通过）、`08-packaging-refresh.md`（打包链未变 + keys 合规）。

**待完成验收（M0 收尾）**

- 能读取一份 manifest，执行 preflight 并生成机器可读报告。
- 报告能区分阻断项、警告和可忽略信息。
- 不需要真正移植游戏就能完成最小端到端的流程编排测试。

### M1：第一款原型游戏跑通 NRO 流程

优先选取已存在 Switch 移植工程、文档相对完整、无复杂 DRM、能够合法使用资源的测试作品。不要为选择一个测试作品引入额外逆向工作。

**验收**

- 框架可以调用上游构建并输出 NRO。
- 输出产物与具体源版本/依赖版本绑定。
- 能在固定 Ryujinx 版本中启动并归档日志。
- 能在真实 NS1 上进行手动验证，记录未通过项。

### M2：输入层与通用配置

**验收**

- 建立统一输入事件模型。
- 基础键鼠模拟可在至少一个原生运行时或 Web 运行时中使用。
- 支持 key-down/key-up、mouse-down/mouse-up、触摸事件和组合键拦截。
- 支持游戏专用映射配置和能力校验。

**【v0.5】状态：M2 完成（模拟器级）。** 输入数据模型/校验/CLI 已实现（`src/galnx/input/`、`galnx input list|validate`、87 项测试）；Citron harness 注入通道打通并复现 KAG3 标题→正文推进；KAG3 输入语义取证见 `docs/milestones/M2-kag3-input.md`。未完成项=真机侧输入、组合键优先拦截、指针缩放/触摸。

### M3：NSP 打包后端

**验收**

- 清楚区分 NRO、forwarder NSP、自包含 NSP。
- 可以自动设置标题、图标、Title ID、版本等元数据。
- 检查 Title ID 冲突，避免不同游戏意外复用。
- 真机上验证最终包的安装与 HOME 菜单启动。
- 在用户文档中明确 forwarder 的资源路径依赖及封禁/系统环境风险。

**【v0.5】状态：M3 部分完成（模拟器级）。** 已完成=①NRO/forwarder/自包含 NSP 三者区分的契约与校验（`src/galnx/package/`）②元数据（标题/图标/TitleID/版本）与 TitleID 冲突检查 CLI（`galnx package plan|check`）③自包含 NSP 出包链（hacBrewPack+nstool）+ **模拟器（Citron）直接引导成功**。**未完成=真机安装与 HOME 菜单启动（M3-d，待用户设备 + CFW/sigpatches）。** 产出：`docs/builds/005-nsp-selfcontained.md`、`docs/milestones/M3-nsp.md`、`docs/packaging/README.md`；风险提示文档已有（forwarder 资源路径依赖、封禁风险）。

### M4：第二种引擎（优先 Web）

**候选**

- 使用 `nx.js_extended`/Brewser 研究 Web 运行环境。
- 使用 BurialNX 学习专用 Web/RPG Maker 游戏的输入、存档和诊断方式，但不要把它当成通用运行时。
- 对类似 Teaching Feeling 的目标，先核验实际 PC 发行版本的 Electron/TyranoScript 结构与 API 依赖，再决定是 Web runtime、原生移植还是其他方案。

**验收**

- 第二个适配器不需要修改核心工作流即可接入。
- 引擎配置、输入配置和构建参数保持独立。

**【v0.6】状态：M4 完成（模拟器级）。** 已完成=①引擎注册表与适配器契约（`src/galnx/engines/`：19 字段 descriptor + schema/语义校验 + 内置 krkrsdl2/brewser + 外部目录加载；`galnx engines list|info|plan`，331 passed/60 subtests）；②Brewser Web 适配器端到端（自建 MIT 内容包在 Citron 运行，输入推进/分支/页内存档验证）；③ONScripter-NX 构建+运行评估（零源码修改、R1–R5 通过，定位 P2 有条件）。**未完成=真机/纯触摸、Brewser localStorage 跨 run 落盘（存档阻塞项）、ONScripter 多游戏启动器与菜单存档 UI（需 GalNX 自建）、DOM 按钮精确点击。** 产出：`docs/milestones/M4-second-engine.md`、`docs/builds/006-brewser-web-adapter.md`、`007-onscripter-nx.md`、`docs/engines/README.md`、`schemas/engine.schema.json`、`examples/engines/`、`examples/web-vn/`。

### M5：FVP / rfvp 评估

**验收**

- 确认当前 Switch target 的构建命令、依赖与输出产物。
- 在 PC host 测试中验证脚本和资源读取。
- 查明 Switch 端渲染、音频、文件 I/O、输入和存档后端的完成情况。
- 不将仓库标注的 experimental 状态误写成“已在真机可用”。
- 根据验证结果决定是正式适配、继续研究还是搁置。

**【v0.7】状态：M5 完成（研究级）。** 已完成=①构建命令/依赖/产物确认（`platform/switch/build_switch.sh`；devkitA64 r30-1 + pin `nightly-2026-02-01` + rust-src；`rfvp.nro` 1,372,216 B sha256 `4964dda9…`；Windows 需 `build.rs` 补丁）；②PC host 验证（`no_std_harness` 2/3：HCB+字体打开、300 帧 1280x720 avg 14.81 ms/帧、global save 262,184 B 读写 OK；slot 因 demo 非 VN 失败）；③后端完成度（渲染 ✅ Citron 17.5 fps / 输入 ✅ M=Plus→quit / 文件 IO ✅ / 存档 ◐ / 音频·视频·CJK ⬜）；④experimental 边界如实标注（上游 README 原文未上真机）；⑤结论=**继续研究（P3 研究项）**，正式适配前置条件 5 条见 `docs/builds/008` §10。产出：`docs/builds/008-rfvp-evaluation.md`、`docs/milestones/M5-fvp.md`、`docs/environment/rust-toolchain-2026-10-30.md`。

**【v1.10】状态：M5-c 完成（模拟器级性能达标，研究项不变）。** rfvp 的 Switch 渲染后端从 CPU 软光栅（`soft_raster`，Citron 17–19 fps、render ≈38.8 ms/帧）改为 **SDL2/GLES2 硬件路径**：`platform/switch/runtime/sdl_video.c` 新建 C shim（`SDL_CreateWindow(1280x720 FULLSCREEN)` + `SDL_CreateRenderer(ACCELERATED|PRESENTVSYNC)`、纹理 ABGR8888/STREAMING、虚拟坐标→letterbox 在 C 内变换、blend 5 种映射、`SDL_RenderGeometry` 绘制、`SDL_RenderReadPixels` 读回缩略图/截图），`host/src/render.rs` 全部转发 C（不再持有 `SoftRaster`），`runtime/main.c` 删 libnx framebuffer 显示、改 SDL 主循环（libnx 只留 pad/触摸/音频），`build_switch.sh` 加 SDL2 编译与链接（**`-lnx` 必须排 `-lSDL2`/`-ldrm_nouveau` 之后**，否则 `nvGpuChannelKickoff` 未定义）。实测（Citron 0237a9b88）：`frame 8280: 60.0 fps over the last 60 frames, slowest frame 17.2 ms`、`perf avg over 60 ticks: vm 0.56 ms, scene 0.23 ms, render 15.57 ms, total 16.37 ms`、标题画面与中文正文「从天而降的羽毛。」渲染正确、0 异常；NRO 7,823,416 B sha256 `e3acbce4…`。两个真因：① C shim 的 `create_texture` 必须 **upsert**（`crates/rfvp/src/rendering/prim_commands.rs:224 upload_graph_if_needed` 对同一 `graph_id` 反复 `create_texture`、`host_texture_id(graph_id)=graph_id as u32`；文字图 `graph_id=4064+slot`，非 upsert 时日志 144 条 `texture create failed: id=4064 1024x540 rc=-3`，文字纹理停在首帧空内容）；② 早期截图拍在文字首现（启动后 t≈63.5 s）之前，属**采样时机**而非渲染缺陷。证据 `docs/milestones/evidence/P9a-rfvp-sdl2/`、补丁 `docs/builds/patches/rfvp-switch/rfvp-sdl2-backend.patch`（1,238 行 / 6 文件 / sha256 `515af726…`）、记录 `docs/builds/016-rfvp-sdl2-backend.md`。**未验证**：真机、音频、CJK 输入（nls/gbk）、手柄语义、内存、MPL-2.0 合规、movie 播放。

**【v1.11】状态：M5-d 完成（手柄输入与快捷存读档，模拟器级）。** 上游 `platform/switch/host/src/event.rs`（commit c4240ad）已自带映射，实测成立 6 项：十字键/左摇杆=虚拟光标（12 px 步进，10×RIGHT 可把光标从 (640,360) 移到 New Game 并出现悬停高亮）、A=`PointerDown{Left}`@光标（点进 New Game）、B=`PointerDown{Right}`（正文里=隐藏/恢复消息窗 toggle）、X/Y=`Return`/`Space`（均能推进正文）、L/R/ZL/ZR=按住 `Control`（可连按跳过剧情）、PLUS=`Quit`（立即退出）。**两个结构性缺口**：① 游戏内 system 菜单（Minus 打开 SAVE/LOAD/HIDE/UNDO/OPTION/TITLE/EXIT/RETURN）**只认指针**，Enter/方向键/Space/肩键全部无反应（P10-g 四次操作后画面 sha 逐字节相同）；② `crates/rfvp/src/subsystem/components/syscalls/legacy.rs:367/377` 的 `load_file/save_file` 置 `set_pending_save_load_request(...)` 并 `should_break()`，由**桌面专属** `legacy_save_load_ui`（`app.rs:650-703`）消费后 `set_halt(false)` 恢复，Switch 端无消费者 → 点中 SAVE/LOAD 永久挂起；另上游不产生 `Wheel` 事件（backlog 无输入源）。**patch J**（`rfvp-input.patch`，9,886 B / 4 文件 +124/−4 / sha256 `aeb8f226…`）＝ `RfvpEvent` 新增 `QuickSave`/`QuickLoad` + `no_std_core` 事件处理与 `take_pending_save_load_request()` 兜底到快速槽 0 + `main.c` 右摇杆字段 + `event.rs` 重写（PLUS 变修饰键：PLUS+ZR 快速存档、PLUS+ZL 快速读档、松开才 Quit；右摇杆 `Wheel{±120}` 上推=历史记录；光标除数 18000→6000）。最终 NRO 7,827,512 B sha256 `b95cd26b…`。实测（P10-h）：guest ODS `quick save: wrote slot 0`（t=169.95 s）/ `quick load: read slot 0`（t=179.00 s），存档目录新增 `rfvp_s000.bin` 490,104 B sha256 `7cac48ab…`；右摇杆上推弹出 BACKLOG（`eec9f46f…`）；PLUS 干净退出。**未验证**：PLUS+ZR/ZL 组合键（Citron harness 逐键 PostMessage 无法同时按住两键，P10-h 用临时单键映射验证了事件→存档链路后已删除）、真机、音频、movie、游戏自带多槽位 SAVE 面板（Switch 只落引擎快速槽 0）。

**【v1.12】状态：M5-e 完成（自包含 NSP，模拟器级）。** 游戏数据由 SD 目录改为 **romfs 打包**，使 NSP 自包含：`platform/switch/runtime/main.c` 增加 `romfsInit()`/`romfsExit()`、`dir_has_game_script()`（用 `.hcb` 判定有效游戏根）与运行期选择——romfs 挂载且 `romfs:/game` 有 `.hcb`、SD 路径无游戏 → 用 `romfs:/game`，否则回落 `sdmc:/switch/rfvp/game`（NRO 形态不变）。打包走新增 `scripts/build_nsp_game.sh`（通用，非 rfvp 专用）：elf2nso→npdmtool→nacptool→romfs 硬链接暂存（`hardlinked=161 copied=0`，不复制 9.2 GiB）→hacBrewPack（546 s）→nstool；产物 NSP **9,979,435,224 B sha256 `4592385c…`**，romfs **9,932,275,140 B / 161 顶层条目**，exefs/main 4,612,243 B `915cdf73…`、main.npdm 972 B `3cfb9877…`、control.nacp 16,384 B `8e9bbbd1…`、icon 22,454 B `10daef90…`。Citron 验证（P11-nsp2）：窗口 `IROSEKA FHD (64-bit) | 1.0.0`，t=8.41 `game root: romfs:/game (romfs mounted)`、t=8.43 `GameConfig { hcb: Some(".iroseka.hcb"), nls: Some(GBK) }`、t=8.81 loaded、t=9.28 first frame；方向键光标→New Game→A 进入→中文正文「从天而降的羽毛。」→PLUS 退出（t=182.03），EXCEPTION/panic 0；NRO 回归 PASS（t=5.089 `(no romfs)`）。独立校验 `galnx package nsp verify` ok=true、12 checks（11 ok / 1 warn = NCA 签名未签名预期）、3 NCAs ProgID 均 `010047420000A000`。**未验证**：真机安装/运行（9.98 GB 必须 exFAT SD 或 NAND，DBI FTP ≈25–30 分钟）、romfs 内音频/bgm 与 movie、4 GB 机型内存余量、romfs 冷读耗时（018 §9 U1–U8）。记录 `docs/builds/018-rfvp-nsp.md`、证据 `docs/milestones/evidence/P11-rfvp-nsp/`、补丁 `patches/rfvp-switch/rfvp-romfs.patch`（2,430 B / 1 文件 +38/−1，先应用 sdl2 与 input）。

**【v1.13】状态：M5-f 完成（手柄映射重写，Citron 级逐项验证；R=Ctrl 待真机）。**
- 改动文件：`platform/switch/host/src/event.rs` 整体重写（404 行；diff 413 行 / +264 −56），补丁 `docs/builds/patches/rfvp-switch/rfvp-input-remap.patch`（sha256 `44fd0722…`），全量 `rfvp-full.diff` 68,536 B（9 文件 +1278 −173）；应用顺序 sd2 → input → romfs → input-remap。
- 映射表（`event.rs` 常量 + `KEYS` + 分支）：A→`KeyCode::Return`、B→`KeyCode::Escape`、方向键→`Up/Down/Left/Right`、R→`Control`（按住 down/up，L 预留）、ZR→`PointerButton::Left` 按下/抬起、ZL→`PointerButton::Right`、右摇杆→`PointerMove`（`STICK_DEADZONE=8000`、`POINTER_DIVISOR=3000`）、左摇杆纵向→`Wheel{delta_y:±120}`（首 poll 即发、之后每 6 poll 重复）、X→工具栏 AUTO 宏、Y→暂停菜单 LOAD 宏、PLUS→暂停菜单 SAVE 宏、MINUS→暂停菜单 EXIT 宏 + 退出确认框二次点击。
- 宏机制：`MenuMacro { x, y, stage, waits, open_menu, click2 }` 阶段机 —— stage0 可选 `Escape` 按下 → stage1 抬起并等 90 poll（≈1.5 s，解决菜单淡入期点击被吞）→ stage2 指针移动 → stage3 左键按下 → stage4 抬起；`click2` 存在时等 30 poll 再做第二次移动/按下/抬起（用于「EXIT → 确定」）。
- 验证（Citron，`docs/builds/019-rfvp-input-mapping.md`）：B=Esc 打开暂停菜单（p12-g g3/g4）、ZL=右键可关闭菜单（p12-h h6，Esc 反而关不掉）、Y=FILE LOAD（p12-i i3）、PLUS=FILE SAVE（p12-i i2）、MINUS=EXIT+确认后干净退出（p12-i i5 全黑、无异常框）、方向键与左摇杆滚轮（p12-d/p12-n）、右摇杆光标（p12-f f3/f4）、X=AUTO（p12-n n4 出现 AUTO 进度条与「自动播放」tooltip）。
- 产物：NRO 7,839,800 B sha256 `093ad9e0…`、ELF 17,046,880 B sha256 `0bfc77e1…ad4c1d`、自包含 NSP v1.0.1 9,979,435,736 B sha256 `0fda623c…67419`（romfs 9,932,275,140 B / 161 entries，hacBrewPack 571 s，`galnx package nsp verify` ok=true 12 checks 0 fail / 1 unsigned warn），NSP 形态 Citron 冒烟（p12-m）确认 `rfvp: game root: … (romfs mounted)` + 中文标题渲染。
- 未验证（U 项）：U1 A=Enter 需真机复核（Citron 正文推进受打字/节流影响，证据不足）；U2 ZR=左键在正文的推进/拖拽手感；U3 R=Ctrl 的跳读效果 Citron 未观察到（引擎侧 `anzu_scene.rs` 跳读判定 = `inputs_manager` 的 Ctrl 位，`input_manager.rs` 会置位，但游戏是否调用 `TextSkip` 取决于脚本）。

**【v1.14】状态：M5-g 完成（rfvp 真机四项缺陷修复，Citron 双形态验证；真机复验待用户）。**
- 症状（用户 m19465/m19535 真机）：① 画面看不到鼠标光标（游戏自绘的小菱形只在收到指针事件后出现）；② 进正文后明显卡顿（Citron 内 60 fps，真机低帧）；③ 用游戏暂停菜单 EXIT 退出后黑屏、进程不退出；④ 按 MINUS 直接退出游戏、没有确认框。
- 根因 1（光标）：Switch no_std 路径没有 winit，`exit_confirm_ui` / `legacy_save_load_ui` 都不可用，指针位置只存在于 `event.rs` 的 `cursor_x/cursor_y`；游戏侧只在收到 `PointerMove` 后画一次光标，静止时看不到。
- 根因 2（性能）：早期实现每帧 `create_texture` + `ReadPixels` 读回，纹理反复重建与 GPU 同步造成抖动；改为按 id upsert + 单张 scratch 纹理复用后 Citron 稳定 60 fps（`render` 15.75 ms/帧）。
- 根因 3（原生退出黑屏）：游戏暂停菜单 EXIT 触发引擎 `ExitDialog` 请求（`RfvpEvent` 无对应事件），no_std 端无人消费 → 主循环仍在跑但无场景可画 = 黑屏。
- 根因 4（MINUS 无确认）：`event.rs` 里 MINUS 直接置 `pending_quit` 并在松开时发 `RfvpEvent::Quit`，绕过了任何确认流程。
- 修复（7 文件，补丁 `rfvp-device-fixes.patch`，基线 worktree `9f07ade` + 顺序 apply 016/017/018/019）：
  - `platform/switch/runtime/sdl_video.c`：主机层 overlay —— 菱形光标 + `QUIT GAME?` 面板 + 5×7 点阵字体（英文），新增 `galnx_sdl_set_overlay()`，纹理 scratch 复用；
  - `platform/switch/host/src/event.rs`：`DIRECTIONS`/`ACTIONS` 重构，ZR/ZL = 鼠标左右键按压、R = Ctrl、MINUS 只打开主机确认框（`pointer()` / `quit_dialog_open()` / `take_quit_confirmed()` / `debug_line()`）；
  - `platform/switch/host/src/app.rs`（CRLF 文件）：`request_quit` / `pointer_state` / `quit_dialog_open` / `take_quit_confirmed` / `input_debug_line`；
  - `platform/switch/host/src/ffi.rs`：每帧 `take_quit_confirmed()` → `request_quit()`，导出 `rfvp_switch_pointer`、`rfvp_switch_input_debug`；
  - `platform/switch/runtime/main.c`：每帧 `galnx_sdl_set_overlay()` 传光标与确认框状态；
  - `crates/rfvp/src/no_std_core.rs`：消费 `ExitDialog` pending 请求与 `ExitMode(3)` → 日志 `quit requested by the game (ExitDialog confirmed)` / `(ExitMode(3) main script exited)`，置 `quit_requested` + `save_global_if_changed()`；
  - `crates/rfvp/src/host_api/event.rs`：退出对话状态字段。
- 验证（Citron）：NRO 形态（p12-o / p12-q / p12-s）与 NSP 形态（p13-nsp）全 PASS —— 中文正文「……羽毛。」、主机黑菱形光标随右摇杆移动（n2）、`QUIT GAME? / A = YES  B = NO` 面板（n3）、A 确认后窗口关闭回 Citron 列表（n5）、日志 `exit confirmed by the player, closing` → `quit requested by host event`、EXCEPTION/panic 0、60 fps。
- 产物：NRO 7,839,800 B sha256 `4f096dd6…c2370f`、ELF sha256 `f34992a3…6feeb3`；自包含 NSP v1.0.2 9,979,437,784 B sha256 `ff259aa4…09c0d9b`（exefs/main 4,614,659 B `92d0c308…`、romfs 9,932,275,140 B / 161 条目），`galnx package nsp verify` ok=true 12 checks（1 warn = NCA 未签名）；DBI FTP 上传 9.98 GB 实测 1,548.7 s ≈ 6.15 MiB/s（25.8 分钟，DBI 自动安装）。
- 记录：`docs/builds/020-rfvp-device-fixes.md`、证据 `docs/milestones/evidence/P13-rfvp-nsp/`、runbook `docs/pilot/P11-rfvp-nsp-device-runbook.md`（V1–V14 / U12–U17）、`docs/milestones/M5-fvp.md` M5-g 段。
- 未验证（U 项）：U12 真机光标可见性与速度、U13 真机确认框 A/B 按键、U14 原生 EXIT 真机退出与全局存档落盘、U15 真机性能（低帧 / 输入延迟是否消除）、U16 NSP 冷启动 romfs 读取、U17 4 GB 机型内存余量。

**【v1.15】状态：M5-h 完成（rfvp 真机掉帧修复：GPU prev-frame + 关闭诊断回读 + 顶点批处理；Citron 同探针验证，真机复验待用户）。**
- 症状（用户 m20518/m20552 真机，Ryujinx 复现同现象）：转场/淡入掉帧到约 10–20 fps、audio stall、每约 5 秒一次周期卡顿、启动与存档尖峰。
- 定位方法：宿主计时插桩（`galnx_sdl_take_stats` → `ffi.rs` debug_report 的 `host(ms)` 行）+ perf3/perf4 两个同步骤探针对比（Citron，同 NRO 步骤、同截图点位）。
- 根因 R1（决定性，转场）：`crates/rfvp/src/no_std_core.rs:857-871` 每帧在 `wants_prev_frame` 时调 `renderer().capture_thumbnail(1920,1080)` 回读 8.29 MB 再上传为 prev-frame 纹理（`Sprt texture_id == -1`），帧 81–85 实测 thumb 45.48–66.49 ms、slow 56–84 ms；清空 render 阶段后这 55 ms 全在宿主未计时路径。
- 根因 R2（周期卡顿）：`platform/switch/host/src/ffi.rs` 每 300 帧调 `galnx_sdl_write_screen_bmp` 写 `debug_screen.bmp`（全屏回读 41 ms）；perf3 帧 8401/8701/9001 slow 53.8/49.9/49.7 而 render 仅 0.64/0.58/0.47 ⇒ 「每 5 秒卡一次」的诊断伪影。
- 根因 R3（批处理/可观测性）：`sdl_video.c` 每个 sprite 一次 `SDL_RenderGeometry`（稳态 14 draws = 14 flushes），阶段耗时全部落在 submit，缺少宿主侧细分。
- 根因 R4（残余、本轮未修）：冷启动帧 1/4 slow 1744/818 ms（`vfs_read` 675 ms、`graph_decode` 521 ms）；存档帧 save 26.8–54.8 ms（`save_finalize` 13.5–32.4 ms + 缩略图 11 ms，约每 2 分钟）。
- 修复（6 文件，补丁 `rfvp-perf-gpu-prev-frame.patch` 32,781 B / 6 文件 +481 −50 sha256 `e64dfb71…`）：
  - `platform/switch/runtime/sdl_video.c`：两个 1280×720 `SDL_TEXTUREACCESS_TARGET` 离屏 target 轮换（`galnx_sdl_begin` 设 target、present 时 `RenderCopy` 到窗口再 swap），`PREV_FRAME_TEXTURE_ID`（0xFFFFFFFD）在 batch 中解析为 `frame_targets[frame_previous]`；顶点批处理（8192 顶点/12288 索引，只合并连续同 texture/blend/filter/clip，顺序语义不变）；宿主计时（begin/draw/upload/flush/present/thumb 的调用数与 µs）；
  - `crates/rfvp/src/host_api/render.rs`：`RfvpRenderer` 新增 `fn supports_gpu_prev_frame(&self) -> bool { false }`；
  - `crates/rfvp/src/rendering/prim_commands.rs`：新增 `set_prev_frame_gpu(width, height)`，只置 `prev_frame = Some(..)` 并清 `wants_prev_frame`，不 create/update 纹理；
  - `crates/rfvp/src/no_std_core.rs`：支持 GPU prev-frame 时跳过 `capture_thumbnail` 与 `set_prev_frame`，否则回落 CPU 路径（保留 fallback）；
  - `platform/switch/host/src/render.rs`：`HorizonRenderer` 覆盖 `supports_gpu_prev_frame() -> true`；
  - `platform/switch/host/src/ffi.rs`：`const DEBUG_SCREEN_ENABLED: bool = false` 关闭周期 BMP 回读（`main.c` 首帧 `shot` 写一次属一次性启动成本），debug_report 追加 `host avg over 60 frames: begin/upload/present/thumb/draws/flushes` 与 perf_slow 的 `host(ms)` 段。
- Citron 同探针（perf3 CPU 回读 → perf4 GPU target，同脚本步骤）：slow 行 154→19、帧>7 慢帧 151→15、≥30 ms 150→13、≥50 ms 136→5、slow 总时长 12,133.7→3,567.8 ms、帧>7 合计 9,221.4→639.9 ms；thumb≥20 ms 帧 142→0（logo/淡入帧 81–85 完全不再进 slow，最大 thumb 11.83 ms 仅存档缩略图）；稳态 60.0 fps、`render`≈`present` 15.3–16 ms，标题/正文/光标截图与 P13 一致（目视无花屏）。
- 产物：NRO 7,843,896 B sha256 `e5373bd7…a2484`、ELF 17,069,080 B sha256 `e4040e7b…6feeb3`；自包含 NSP **v1.0.3** 9,979,441,368 B sha256 `b9e0d6a5…5aa3e`（exefs/main 4,618,532 B `67a29a73…`、romfs 9,932,275,140 B / 161 条目，TitleID `010047420000A000`），`galnx package nsp verify` ok=true 12 checks（1 warn = NCA 未签名，3 NCA ProgID 全 `0x010047420000A000`）；Citron NSP 形态冒烟 PASS（SD 游戏目录改名 `game.sd-bak` 强制 `romfs:/game`、`GameConfig { hcb: Some(".iroseka.hcb"), nls: Some(GBK) }`、中文正文、主机光标、`QUIT GAME?`、EXCEPTION/panic 0，first frame 6.70 s、quit t=121.17 s）；DBI FTP v1.0.3 上传实测 9,979,441,368 B / 1,529.0 s ≈ 6.22 MiB/s（25 分 29 秒，DBI 根目录回占位=自动安装）。
- 记录：`docs/builds/021-rfvp-perf-gpu-prev-frame.md`、补丁 `patches/rfvp-switch/rfvp-perf-gpu-prev-frame.patch` 与全量 diff 107,938 B / 12 文件、证据 `docs/milestones/evidence/P14-rfvp-perf/`（perf3/perf4 slow 行、对比表、NSP 截图与冒烟日志）、runbook `docs/pilot/P11-rfvp-nsp-device-runbook.md`（P14 版 V1–V15）、`docs/milestones/M5-fvp.md` M5-h 段。
- 未验证（U 项）：U18 真机转场/周期卡顿复验（重点）；U19 冷启动 `vfs_read`/`graph_decode` 尖峰未优化；U20 存档 `save_finalize`+缩略图尖峰（`GLOBAL_SAVE_INTERVAL_US=120 s` 已在，仍存在）；U21 真机 SDL2 `SDL_TEXTUREACCESS_TARGET` 支持（GPU prev-frame 依赖，失败时回落 CPU 路径）。

### M6：批量构建、回归与可选 GUI

**验收**

- 支持批量预检/构建，单个项目失败不会破坏其他项目。
- 支持构建缓存、依赖锁定、测试报告差异、重新构建和清理工作区。
- 在 CLI 稳定后再设计 GUI，不以 GUI 进度替代引擎兼容工作。

**【v0.7】状态：M6 部分完成（M6-a 批量预检 MVP）。** M6-a：`src/galnx/batch/` + `galnx batch run|diff|clean`（单项目失败隔离、JSON 报告写 `<root>/.galnx/` 默认保留 10 份、退出码 0/2）+ `schemas/batch-report.schema.json` + 23 用例（全量 367 passed/63 subtests）；实测 `examples/batch` 3 项目 2 ok 1 fail rc=2、`diff` 分类、`clean` 无 `--yes` 保护。**未完成=M6-b 真实批量构建执行与缓存/依赖锁定/重建（当前 batch 只做预检+engines plan，不跑构建）、M6-c 汇总与 GUI 决策（GUI 明确后置）。** 产出：`docs/batch/README.md`、`docs/milestones/M6-batch.md`。

**【v0.8】状态：M6 完成（CLI 级；GUI 按计划后置）。** M6-b：新增 `src/galnx/build/`（executor/cache/lock）+ `galnx batch build` / `galnx batch lock` / `galnx build run`；执行器只执行 manifest 显式声明的 `build.commands`（argv 数组走 shell=False、字符串走 shell=True）、支持 `workdir`/`env`/`timeout_s`（默认 600），日志写 `<root>/.galnx/logs/`；sha256 构建缓存 key=canonical{manifest 路径, adapter+pinned_commit, build.*, 输入规范化, 工具链指纹(gcc/cmake 首行版本)}，命中前校验产物存在+sha256（失效记 `cache.stale` WARN 并重建），`--no-cache`/`--rebuild` 可绕过；`galnx batch lock` 写 `.galnx/engine-lock.json`（per-project adapter/pinned_commit/build_backend/toolchain/manifest_sha256/artifact），`batch build --locked` 漂移即 fail。实测（Lead 独立复核，`docs/milestones/M6-batch.md` §5A）：run1 cache miss→built=1、run2 cache hit→built=0，产物 `out/demo.bin` 91 B sha256 `3c9b52aa…` 两次一致；`--rebuild`/删产物触发 stale 重建/`--no-cache`/`--locked` 全通过；全量 pytest 401 passed/63 subtests（新增 34 用例）。**边界：** 真实引擎（krkrsdl2/ONScripter-NX/NSP）的 `build.commands` 尚未接入示例（执行器/缓存/锁定本体已用 `examples/batch/demo-build` 验证）；并发未做；缓存跨机器/跨路径命中不保证；CI 门槛未接；GUI 按计划后置（见 §12【v0.8】）。产出：`docs/batch/README.md`（11,237 B）、`docs/milestones/M6-batch.md` §5A、`docs/milestones/evidence/M6b-*`。

---

### P 系列：首款垂直试点（《晴霁之后定是菜花盛开的好天气》，2026-10-30）

**【v1.6】状态：P0–P3 + P3.5 完成（模拟器级），P4 真机可启动且退出崩溃已修复（patch F，A5），P5 汉化 + 中文 OP 完成（A7），P6 手柄映射 v2 与三个真机 bug 修复完成（patch G，A8），P7 输入微调 + 封面完成（patch H，A9 中文 NSP version 1.0.8：R 按住=Ctrl 快进、左摇杆滚轮方向跟正、首页图标换封面图；verify 19 checks，Citron 首启冒烟全通）；仅剩真机对 A9 的最终复验。**
**【v1.5】状态：P0–P3 + P3.5 完成（模拟器级），P4 真机可启动且退出崩溃已修复（patch F，A5），P5 汉化 + 中文 OP 完成（A7），P6 手柄映射 v2 与三个真机 bug 修复完成（patch G，A8 中文 NSP version 1.0.7：verify 19 checks、Citron 首启解包 + 中文标题/正文 + MINUS/抽屉电源键双退出路径干净退出、0 异常）；剩余仅真机对 A8 的最终复验。**
**【v1.4】状态：P0–P3 + P3.5 完成（模拟器级），P4 真机可启动且退出崩溃已修复（patch F，A5），P5 汉化完成并扩展到中文 OP（A7：中文标题/正文/OP、verify 19 checks、Citron 首启冒烟 PASS）；剩余仅真机对 A5/A7 的最终复验与可选增强。**
**【v1.3】状态：P0–P3 + P3.5 完成（模拟器级），P4 真机可启动且退出崩溃已修复（patch F，A5），P5 汉化完成（A6 中文 CN NSP：中文标题/正文、verify 19 checks、Citron 首启冒烟 PASS）；剩余仅真机对 A5/A6 的最终复验与可选增强。**
**【v1.2】状态：P0–P3 + P3.5 完成（模拟器级），真机退出崩溃已定位并修复（patch F），A5 自包含 NSP 已构建；用户完成标准已达成并经两条独立复跑确认；P4 真机已安装 A4 并可启动，A5（含退出修复）待用户设备复验。**
（v1.1 状态行保留：P0–P3 + P3.5 完成（模拟器级 + 工程化 + 全手柄存档/读档），用户完成标准已达成并经两条独立复跑确认；P4 真机待设备。）
（v1.0 状态行保留：P0–P3 完成，工程化链路可一条命令复现。）

- 用户指令（m04829）：新增候选 Kirikiroid2-NX；首款垂直试点 = `E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气/`（PC 版）；完成标准 = 模拟器上「已打包 NSP、可直接启动、支持手柄操作」；达标后才做真机。
- 路径决策：**路径 A（选定）** = K2NX 源码重建 + romfs 首启解包 + autostart + per-game KeyMap → 自包含 NSP。理由：预编译 NRO 已能读全部 14 个 XP3（19,171 文件激活），仅缺「插件名别名」一处；数据全部进 romfs 才满足严格自包含；构建链可复现。备选路径 B（数据外置）不满足自包含、路径 C（krkrsdl2）插件覆盖未知，保留为后备。
- 引擎 pin：`Erige005/Kirikiroid2-NX` `e96b6034c292c6ccdb099823ab6a0a6b505f77f3`（tag v1.0.1）；三处补丁 = A autostart（`SwitchUtils.cpp` 读 `sdmc:/switch/kirikiroid2/autostart.txt`）/ B 首启解包 v2（`main.cpp` 读 `romfs:/game_files.txt`、statvfs 预检 + FastLoad + 1 MiB 缓冲 + 同大小跳过 + marker）/ C 插件别名（`InternalPlugins.cpp` 把 `.tpm` 重试为 `.dll`）；补丁包入库 `docs/builds/patches/k2nx-switch/`。
- 构建：本机 MSYS2 devkitPro + **自建 7 个 portlibs**（libiconv 1.17 / jxrlib / UnRAR 5.6.5 / libbpg 0.9.8 / blend2d d2027ebf / **FFmpeg 3.2.19**（devkitPro 只有 7.x）/ OpenCV 3.4.20 core+imgproc）；两处 Windows 坑 = ar argv 过长（`libcocos2d.a` 约 800 对象 → `ar-chunk.sh` 每批 120 + 改 `rules.ninja`，且 ninja 日志里没有 `error:` 字样、需按行首 FAILED 检索）、reconfigure 会覆盖 `rules.ninja` 补丁须重打。产物：r2 ELF 113,874,760 B sha256 `4b451583…`、r2 NRO 42,351,222 B sha256 `f6134790…`。
- 打包：`scripts/build_pilot_nsp.sh`（ELF→elf2nso→hacBrewPack，romfs 直接内嵌 2.88 GB，峰值内存 111 MiB、95 s）。**A2 自包含 NSP** 2,906,125,016 B sha256 `eb6c6a15151c2a5936c6549eebb26ca25a059744f0136cb5b8cce773fd9c705f`（title_id `010047410000b0b4`，romfs 109 文件 / 2,878,186,922 B / 最长路径 67，payload 23 文件 = 14 xp3 + haruno.cf + 7 tpm + KeyMap XML）；keyset 走显式 `--keyset`（沿用【v0.5】策略）。
- 验收（Lead 亲自跑，证据入库 `docs/milestones/evidence/P2*`，详见 `docs/pilot/P2-acceptance.md`）：①全新 SD 首启 = 自动解包 23 文件 14.4 s（约 205 MB/s）→ autostart → 07:40:47 `title.ks`；②手柄 RIGHT+C → `start.ks` → `@0000A_Z01.ks` 正文（60 FPS、0 exception），C 推进 diff=0.0201；③二启 `payload pilot01-r2 already extracted`、48 s 到 title，标题截图 sha256 与首启逐字节相同（`06f4d1b8…`）；④harness 全流程 result：status=loaded、steps_failed=0、`Booting game: 010047410000B0B4`、nonblack 0.9018。
- 未验证/限制：真机（P4）、物理手柄、xmoe 中文（Windows DLL 注入体系不可移植）、B/ESC 菜单无可见变化、存档写读回、音频、Citron 下鼠标注入不稳定（键盘 PostMessage 稳定）。
- 教训：Citron 单实例会静默转发 → 两任务并发会混跑同一进程、互删 SD 数据、证据作废 → 改「申请-释放」制（见 §12 决策 14）。harness 早退（R14）根因 = 调用方回收 bash 进程树而 Citron 经 `runas` 存活 → 从已脱离的 shell/后台 job 启动可跑满。
- 产出：`docs/pilot/README.md`（v0.3）、`docs/pilot/P1-engine-k2nx.md`（1,500+ 行）、`docs/pilot/P1-game-audit.md`、`docs/pilot/P1-nsp-packaging.md`、`docs/pilot/P2-acceptance.md`、`docs/pilot/P3-pipeline.md`、`docs/pilot/P3-verification.md`、`docs/pilot/P3-smoke-independent.md`、`docs/builds/patches/k2nx-switch/`（7 文件 + README）、`scripts/build_pilot_nsp.sh`、证据 90+ 文件。

**【v1.0】P3 打包工程化（完成）**

- 三条 CLI 链把 P0–P2 的手工流程固化成一条命令（详见 `docs/pilot/P3-pipeline.md`）：
  1. `galnx engines prepare --descriptor examples/engines/kirikiroid2-nx.yaml --dest <src>`（pin 校验 + 脏树检测 + 三补丁 + portlibs + `.galnx/engine-lock.json`；`--check-only` 只读）；源码 `src/galnx/engines/source.py`。
  2. `galnx payload plan|materialize --manifest examples/pilot01-haruno.yaml`（romfs 内容清单、`game_files.txt`、per-game KeyMap 渲染；源码 `src/galnx/payload/`）。
  3. `galnx package nsp plan|build|verify --manifest … --elf … --romfs-dir … --keyset <path>`（elf2nso→npdm→nacp→hacBrewPack 四步 + nstool 13 checks + PROVENANCE 交叉核对 6 项）；源码 `src/galnx/package/nsp.py`；新增嵌套子命令 `package nsp verify`（19 checks）。
- **端到端复现 oracle 命中**：romfs 109 文件 / 2,878,186,922 B / 最长路径 67 / 摘要 `53535c68d81a24d88fbac0a6fce0d710e0592558bc89286b732f88891b7d164e`、`game_files.txt` 600 B sha256 `0e6757d9…`、KeyMap XML 1,293 B sha256 `aa4fa8aa…`；与 P2 手工产物逐项一致。
- **A3 合规 TitleID 自包含 NSP**：`Kirikiroid2-NX-010047410000A000.nsp` **2,906,131,672 B sha256 `1f54bdf105fdfc0e88a81e5aaec954ffd4c349132fe7bbadcf394948cde994d4`**（exefs/main 22,082,152 B sha256 `91d87fc9…` 与 A2 逐字节一致；NSP 层因 RSA-PSS 随机盐不具确定性）。构建 24 checks 0 fail/1 warn（未签名 homebrew 的 ACID signature 预期失败）。
- **验收（Lead 亲自跑 + 两条独立复跑）**：①Lead 构建后 Citron **全新 SD** 首启 38 s 到 title、解包 23 文件 / 2,870,635,309 B、手势 RIGHT+C → `start.ks` → `@0000A_Z01.ks`、status=loaded；②audit-package 独立 `package nsp verify` PASS（19 checks / 0 fail / 1 warn，3 NCA ProgID 全 `0x010047410000a000`，PROVENANCE 仅记 keyset 元数据）；③audit-web 独立 Citron 全新 SD 冒烟 PASS 7/7（`docs/pilot/P3-smoke-independent.md`）。
- `scripts/citron_run.sh` 新增 `--detach`/`--wait-job`/`--status`：WMI 建脱离进程 + `launch_route` 三值 + 陈旧日志假阳性检测，修掉 R14（详见 §12 决策 16）。
- 工程判据：`PYTHONPATH=src python -m pytest -q` → **600 passed / 63 subtests**；`galnx` 全部新能力均有 JSON 输出与退出码约定（0 成功 / 1 构建或校验失败 / 2 输入或计划错误）；CLI 统一 UTF-8 stdio（修 Windows cp936 重定向导致中文 JSON 非 UTF-8）。
- 已知边界：k2nx 仍为 overlay 示例不升 builtin（决策 17）；jxrlib 等 2 个 portlibs 未 pin 提交（R12）；NSP 形态鼠标注入无效沿用 R10；真机仍待 P4。

**【v1.1】P3.5 手柄存档/读档（完成）**

- 目标：在用户完成标准（自包含 NSP + 手柄推进剧情）之上补「存档/读档」，并解决「手柄操作」对**原生 UI**（K2S 抽屉 / 游戏内菜单 / 存档界面）的可达性——docked 真机没有触摸，手柄必须能独立完成存读档（详见 `docs/pilot/saveload-acceptance.md`、`docs/builds/010-k2nx-controller-saveload.md`）。
- 三条路线被排除（源码 + 实测）：①引擎 K2S 抽屉的 `btn_gamemenu` 与 `TVPInGameMenuForm` 全是 cocos 触摸控件，虚拟鼠标只把事件发给 `_currentWindowLayer->onMouseClick`，打不到 UI 层；②`TVPGetMenuDispatch()` 恒 NULL——本作是自研 **BASE ADV SYSTEM**（`MainWindow.tjs` by Kazuyuki Uchino，2008），既无 `Window.menu` 也无全局 `kag`，标准 KAG3 的 `kag.saveBookMark()` 路线不存在；③引擎内伪造触摸（`glView->handleTouchesBegin`）在 2 次会话中令 Citron **进程硬终止**（无 crash dump、citron_log 半行）→ 放弃。
- 本作真实存档 API（源码取证，`MainObj` = `new MainWindow(...)` 全局实例）：`MainObj.SaveAction(num)`（写 `savedata%03d.bmp` 缩略图 + `Dictionary.saveStruct`）、`MainObj.DataLoadAction(num)`、`MainObj.SaveLoadObj = new _SAVELOADOBJECT(MainObj, MainObj.PrimaryLayer, nSAVE_SC|nLOAD_SC)` + `ActiveObj = SaveLoadObj`（原生 SAVE/LOAD 界面）、`MainObj.SystemSave()`；槽号 = `NowPage*10 + DataNum`（「01 01」= `savedata010.bmp`），落盘目录 = `System.exePath + savedata/` = `sdmc:/kirikiri/haruno/savedata/`；确认框由系统字典 s 的 dlg_save / dlg_load 键控制。
- **patch D（手柄可控虚拟鼠标）** `docs/builds/patches/k2nx-switch/D-virtual-mouse-dpad.patch` 2,406 B sha256 `11f50193…`：`MainScene.cpp` 的 `onPadKeyDown` 加 PLUS 开关虚拟光标、D-Pad 每次 24 px 步进（clamp 到 GameNode 内容区）并同步 `onMouseMove`、A/B = 左/右键 `onMouseClick`；绕开 `onAxisEvent` 的 `PrimaryLayerArea` 早退（本作无该区域，摇杆永远不亮光标）。
- **patch E（手柄存档/读档热键 + 菜单键盘导航）** `docs/builds/patches/k2nx-switch/E-controller-ui-saveload.patch` 20,233 B sha256 `4ae7eda9…`（**必须在 D 之后应用**，5 文件）：核心是 `GalNX_QuickSaveLoad()` 用 `TVPExecuteExpression` 求值本作 TJS——L 键预置 savetitle + `SaveAction(1)` + `SystemSave()`、R 键关确认框后构造 nLOAD_SC 界面、PLUS 构造 nSAVE_SC 界面、ZR 直读槽 10、ZL 强制系统存档；同时给 `TVPInGameMenuForm` 加 D-Pad 选择/激活、`PreferenceForm` 加选中高亮（对支持 Window.menu 的游戏仍可用）。GalNXLog 诊断写 `sdmc:/galnx-input.log`（发布前删除）。
- 验收（模拟器级，全手柄、无触摸/鼠标）：**NRO（S27b）与 A4 NSP（a4smoke）双形态闭环**——PLUS → SAVE 界面 → Y 光标 → 11×LEFT + 15×DOWN + 9×UP 到槽 01 01 → A 存档 = `savedata010.bmp` 45,941 B + `system.bmp` 989 B 落盘；重启 → R 开 LOAD 界面（槽 01 01 显示 NEW + 缩略图 + 存档标题 + 日期）→ A 读档 → 回到存档点正文 → C 继续推进正常；k2s 全程 0 error/exception；证据 `docs/milestones/evidence/P3g-*`（21 文件 + sha256 清单）。
- **A4 自包含 NSP**（manifest version 1.0.3）：2,906,135,768 B sha256 `2003ec1eb1ccd78d4e74ff10965376a7248c00962262e7582258d8545fb03c39`，`galnx package nsp verify` 19 checks / 18 ok / 1 warn（未签名预期）；构建用 ELF 113,891,072 B sha256 `7461bbe0…`、NRO 42,363,510 B sha256 `a84f6be0…`（CRLF 归一前后哈希相同，见决策 20）。
- 限制：热键表达式绑定本作私有 TJS API（换游戏需重写，R13）；GalNXLog 诊断写 SD（R14）；物理手柄与真机仍待 P4；patch D/E 尚未在真机验证。
**【v1.2】P4 真机退出崩溃修复（模拟器级完成，待 A5 真机复验）**

- 真机现场（用户报）：Atmosphère + sigpatches 安装 A4 NSP 后可启动并游玩，但用 K2S 抽屉电源键退出时弹错误框并崩溃：`Error Code: 2-0000`、`NX 1.0.1 (Kirikiri2 1.3.9) 晴のちきっと菜の花びより`、`Member "SystemObj" does not exist`、`@line(365) checkdialog.tjs`（详见 `docs/builds/011-k2nx-exit-crash-fix.md` §1）。
- 根因两条（源码级 + 模拟器复现）：①确认框关闭链里 `CheckDialog.tjs` 的 finalize 依赖全局 `MainWnd.SystemObj`，而 `MainWnd` 在 BASE ADV SYSTEM 里被 `BaseObject`/`BaseLayer`/`Parser`/`SoundObject` 等构造函数反复赋值；主窗口确认关闭若走引擎 desktop 路径的 invalidate teardown，TJS 世界按任意顺序析构，finalizer 再读 `MainWnd.SystemObj` 即报 `Member "SystemObj" does not exist`。②ESC 路径：`MainWindow.tjs:3417` 判断 `this.minimized == false`，K2NX 的 Window TJS 类没有 `minimized` 成员 → `Member "minimized" does not exist`（Citron 13:59:29 日志复现）。
- **patch F（干净退出 + Win32 兼容成员）** `docs/builds/patches/k2nx-switch/F-close-exit.patch` 4,592 B sha256 `21af948cd538ef3f3380b90228571ddedff8f88668880e0027ad0271f1828337`（**必须在 E 之后应用**，2 文件）：
  - `MainScene.cpp`：`OnCloseQueryCalled()` 在 `SetVisible(false)` 之后、`Closing = false` 之前加 `#ifdef __SWITCH__` 分支——若确认关闭的是主窗口（`TJSNativeInstance->IsMainWindow()`），直接 `GalNXLog(...)` + `TVPExitApplication(0)` 并 `return`，不再进入 invalidate teardown（Switch 上主窗口确认关闭 == 离开游戏）；同时把 patch E 的 X 热键从探针改为 `GalNX_EvalTJS("MainObj.onCloseQuery(true)")`，便于复现关闭链。
  - `WindowIntf.cpp`：给 Window TJS 类补 Win32 兼容成员 `minimized`/`maximized`（只读，恒 0）与 `minimize()`/`maximize()`/`restore()`（no-op），修 ESC 路径的成员缺失。
- 验收（模拟器级，全程 `--detach`，证据 `docs/milestones/evidence/P4a-exit-*`）：标题画面按 X 弹「ゲームを終了しますか？」→ Y 开虚拟光标 → 11×LEFT 移到「はい」→ A 确认 → 日志末行 `[close] main window close confirmed; terminating application`；guest 进程干净退出（Citron 回到游戏列表、无错误弹窗、k2s 0 error/exception），退出后 `savedata010.bmp` 45,941 B / `system.bmp` 989 B 未变。
- 补丁栈 A→F 全量 diff `k2nx-patched-vs-v1.0.1.diff` 37,398 B sha256 `8ee1f77a…`（9 文件 677+/20−）；roundtrip 口径同决策 20（CRLF 归一后与构建树逐字节一致）。
- **A5 自包含 NSP**（manifest version 1.0.4）：2,906,138,328 B sha256 `f179f0a20b9ede113231a7bfd0046180a8b90d5408745fbcc73520d73ec3b188`；`galnx package nsp verify` 19 checks / 18 ok / 1 warn（未签名预期）；构建用 ELF 113,892,064 B sha256 `02b70f18…`、NRO 42,363,510 B sha256 `41b7a745…`；romfs 未变（109 文件 / 2,878,186,922 B）。
- 限制：①ESC 路径在标题画面未触发 `MainWindow.EscapeWork`（B 键三张截图无变化），`minimized` 修复目前只有源码级证据，未端到端复现；②X 热键是本轮诊断入口，正式发布前应移除（保留 A/B 正常手柄语义）；③真机退出路径待 A5 复验（用户操作 K2S 抽屉电源键）；④真机安装需 Atmosphère + sigpatches，homebrew NSP 未签名。
- 文档：`docs/builds/011-k2nx-exit-crash-fix.md`（根因链 / 修复 / 验证 / 限制 / 复现命令）；`docs/pilot/saveload-acceptance.md` §8 追加退出验收；补丁 README 更新为 A→F 六补丁；`examples/engines/kirikiroid2-nx.yaml` patches=6、artifact_sha256=A5。

**【v1.3】P5 汉化（模拟器级完成，A6 中文 CN NSP 就绪）**

- **来源与许可**：汉化文本/资源来自公开仓库 `t-satoru-Studio/haruno_script`（`main`，zip 26,451,029 B sha256 `582f73ecd0591f99fc7f64ccd38a0f5f841b9d75cac5323d2ef75602796d2d69`；X'moe 汉化组，KR/ 为 KiriKiri2 汉化源码、PC/ 为 krkrz 迁移版）。游戏本体与汉化著作权归各自权利人，仓库只记录流程与哈希，不重新分发内容。
- **路线（见决策 22）**：不走逆向 `haruno.xmoe` 容器（v0.1 曾评估 242 条记录 / 16 B 魔数 `STmoeSTmoeChu>_<`），改用**公开源码重打包 XP3**——零引擎改动、不做 patch G。三包：`data.xp3` 207,728 B sha256 `e30251c7…`（37 项）、`scenario.xp3` 1,719,460 B sha256 `4da3742e0456b162fbde21061948f910da6d136fed416657eca77fa2b570c184`（237 项）、`image00.xp3` 22,248,684 B sha256 `5baf63a6cdc756ada63693fce76bc48ba09ebff240efdb3f9e63a7897d053071`（141 项）；自研 writer `xp3pack.py` 按引擎 `core/base/XP3Archive.cpp` 实测格式写入（索引链、`info`+`segm`+`adlr`、adler32 大端）并逐项 roundtrip 校验。
- **四个坑（全部已修）**：①`scenario.xp3` 的 `startup.soc` 必须转 UTF-8（原 KR 包是 Shift-JIS，UTF-8 解码失败抛 `eTJSScriptError`，TJS try/catch 抓不到，表现为 `parser.tjs(270) loadScenario("startup.soc")` 无消息中断）；②CN 版 `Init.tjs` 删掉了 xp3 注册、改认解包目录 → 自定义 `startup.tjs` 在 `execStorage` 前用 `Storages.addAutoPath(System.exePath+"scenario.xp3>…")` 补 archive 子目录 autopath（`@_共通/` 等 9 个 + image00 的 `map/`、`csv/` + movie）；③TJS 词法**不支持 `\uXXXX`**（只支持 `\x`/八进制），startup 必须写真实 UTF-8 字符；④`System.setArgument("TextEncoding","utf8")` 在本引擎是空操作（`-readencoding` 被 `#if 0`），要用脚本属性 `Scripts.textEncoding = "utf8"` 并对文本加 UTF-8 BOM。字体用 romfs 自带 `DroidSansFallback.ttf`，简体覆盖足够（CN7/A6 无豆腐块）。
- **验收**：CN7（NRO 形态）与 A6（NSP 形态）双 PASS——中文标题菜单（开始游戏/读档/快速读档/继续游戏/游戏设置/鉴赏模式/结束游戏）+ 中文正文（「我拼命地伸出了手。」等），`Scenario loaded : @0000A_Z01.ks` 命中，`exception|error` = 0；A6 = `Kirikiroid2-NX-A6-CN-010047410000A000.nsp` 2,906,318,552 B sha256 `1941a317baea186bb6f8ac9cdd8e9d11d2125a25abfcc32f83a14339a70a49d7`，`package nsp verify` 19 checks / 18 ok / 1 warn（未签名预期），首启解包 23 文件 2737 MiB → autostart → 中文正文，窗口标题 `Haruno CN (64-bit) | 1.0.5`。
- **证据**：`docs/builds/012-k2nx-cn-content.md`、`docs/pilot/P5-localization-feasibility.md` v0.3、`docs/milestones/evidence/P5a-cn7-*` 与 `P5b-a6-*`。
- **限制**：①A6 真机未验证（待 DBI 安装复验）；②`movie_chs.xp3`（197 MB 汉化 OP/字幕）未纳入，OP 仍是日文字幕；③只走通序章连续对白，长流程/选项分支/鉴赏模式未遍历；④汉化内容许可与分发边界属用户责任。

**【v1.4】中文 OP（A7，模拟器级完成）**

- **来源**：PC 中文版 `movie_chs.xp3`（197,246,119 B）内的 `opening.mpg` **134,811,648 B sha256 `276f671cbdc77a34…` / 114.48 s**（硬字幕中文歌词）；JP `movie.xp3` 内 `opening.mpg` 162,623,492 B sha256 `e88625704277d139…` / 111.99 s（无字幕）。两者均 mpeg1video 1280x720 60 fps + mp2 44100 Hz，可直接同名替换，无需转码。`logo.mpg` 两侧同 sha（1,769,476 B），`OP.MPg`（60,664,813 B）未用。
- **做法**：新 `movie.xp3` = JP 警告 txt + JP `logo.mpg` + CN `opening.mpg`，129,030,977 B sha256 `483bc72d9be9cc74a9c86baf55c0589228d3104446391f475a4a8f59105ec665`；`romfs-cn2` = romfs-cn 硬链接副本（109 文件，仅替换 `game/movie.xp3`，不动 romfs-cn）；`game_files.txt` version=pilot01-cn2 / bytes=2835467131；manifest `examples/pilot01-haruno-cn2.yaml`（game.version 1.0.6，title_id 不变）；打包脚本 `pilot-01/p5/a7-build.sh`。引擎零改动 —— OP 触发点 `@_共通/@0000A_Z02.ks:2024` 的 `[macPlayMovie file=opening mode=1 cursor=0]` 按名字找 `opening`，替换归档内同名文件即可。
- **验收**：op1 场景测试包（在 `@0000A_Z01.ks` BOM 后插入 `[macPlayMovie file=opening mode=1 cursor=0]`）在 Citron PASS —— k2s 出现 `Input #0, mpeg, from 'opening.mpg': Duration: 00:01:54.50 ... 1280x720`，截图含中文硬字幕「啊 透明的一秒 流逝而去」（`P5c-op1-08-title-cnsub.png` 2,224,638 B sha256 `2e34dc6d…`）。**A7 中文 CN NSP** 2,870,879,960 B sha256 `c23a519a…`（PROVENANCE 8dbcc568…，version 1.0.6 / version_code 65542），`package nsp verify` 19 checks（18 ok + 1 warn 未签名），Citron 首启解包 23 文件 2,704 MiB → title.ks → start.ks → @0000A_Z01.ks、0 异常、窗口 `Haruno CN (64-bit) | 1.0.6`。
- **证据**：`docs/milestones/evidence/P5c-op-*`、`P5d-a7-*`；细节见 `docs/builds/012-k2nx-cn-content.md` §8 与 `docs/pilot/P5-localization-feasibility.md` v0.4。
- **限制**：①A7 真机未验证；②A5/A6/A7 共用 TitleID `010047410000A000`，装机会互相覆盖（A7 取代 A6）；③`OP.MPg` 未使用（歌词版 MV）；④长流程遍历与汉化许可限制同 P5 段。

---

**【v1.5】P6 手柄映射 v2 与真机 bug 修复（patch G，A8，模拟器级完成）**

- **背景**：真机验收 A7 后用户反馈（m11780）：开始游戏 / PLUS 菜单正常，但 ①在 PLUS(K2S) 菜单打开时按 R 会冻结（UI 卡住只剩渐变动画，X 仍可走退出流程）②点 K2S 抽屉的电源按钮会在游戏弹确认框的同时触发 `Error Code 2-0000 / Member SystemObj does not exist @line(365) checkdialog.tjs` 崩溃 ③虚拟光标移动过快（要求至少减半）；同时给出新的默认手柄映射：A=Enter、B=Esc、ZL=右键、ZR=左键、右摇杆=光标、左摇杆上下=滚轮（每次只一步）、D-Pad=方向键、+=存档、-=退出、X=自动、Y=读档。
- **映射实现（引擎 pad 层，不动游戏 TJS）**：`MainScene.cpp` 的 `onPadKeyDown` / `onAxisEvent` 重写——A 与 D-Pad 仍走 `Kirikiroid2Preference.xml`（448→13、437/438/439/440→37/38/39/40）；B=游戏原生「返回」`MainObj.ActiveObj.RightMouseUpAction()`（**刻意偏差**：本作 `userFix.ks:500-505` 的 `nESC_KEY=false` 使 ESC 走 `EscapeWork()`→`minimize()`，Switch 上 `EscapeObj` 永不复位会假死，故不能用 ESC）；X=`MainObj.MessObj.AutoFlag` 取反；Y/+=先 `GalNX_CloseAllK2SForms()` 关掉 K2S 表单、再以 `_SAVELOADOBJECT(MainObj, PrimaryLayer, nLOAD_SC/nSAVE_SC)` 打开游戏原生读/存档面板（并 `dlg_load/dlg_save=false` 跳过二次确认）；-= `MainObj.onCloseQuery(true)` 退出；ZR/ZL=`_mouseBtn` + `_currentWindowLayer->onMouseClick(光标世界坐标)` 左右键；右摇杆 `JOYSTICK_RIGHT_X/Y` 移动光标、步长系数 12→6（+0.5 像素基线）；左摇杆 `JOYSTICK_LEFT_Y` 滚轮迟滞（|v|<0.25 复位、|v|>0.6 发一次 ±120，经新增 `TVPWindowLayer::GalNX_SendWheel` → `TJSNativeInstance->OnMouseWheel`）。
- **三个 bug 的根因与修法**：①冻结 = K2S 表单在栈顶吞输入 + 游戏面板成为第二层模态 → 热键先 pop 所有 K2S 表单；②SystemObj 崩溃 = K2S 抽屉电源键走 `TVPWindowLayer::Close()` 设 `ProgramClosing=true`，`OnCloseQuery()` 原来直接 `CanCloseWork = true` 放行，`OnClose()` 对主窗口执行 `obj->Invalidate()` 导致 TJS 世界乱序 teardown（patch F 的早退分支只在非 ProgramClosing 时生效）→ 改为 `CanCloseWork = false`（等游戏确认回调再放行）+ `OnClose()` 主窗口分支直接 `TVPExitApplication(0)`；③光标过快 = 步长系数减半。另发现并修复 **Minus 键根本不达引擎**：vendor `CCController-switch.cpp` 的 `kButtons[]` 缺 Minus（作者把它派发成 `KEY_MENU`），补 `{ HidNpadButton_Minus, Controller::BUTTON_SELECT }` 并删掉那段派发。
- **验收（Citron 端到端）**：g1 = A/D-Pad/X 自动（`[tjs] auto -> ok`）/Y 读档/PLUS 存档/B back/ZR 左键/ZL 右键 全正常，且在 K2S 抽屉打开状态下按 Y 仍能开读档面板（bug 1 修复）；g2 = MINUS（`[pad] key=1022`）→「结束游戏吗？」→ 是 → `[close] main window close confirmed` → 回 Citron 列表、0 异常；g3 = 抽屉 ☰ → 电源按钮 → 同一确认框 → 是 → `[close] program close of main window confirmed` → 干净退出、0 异常（bug 2 修复）。
- **产物**：patch G `docs/builds/patches/k2nx-switch/G-controller-input-v2.patch`（22,152 B sha256 `7cf01df0…`，2 文件 +199/−137，含 vendor `CCController-switch.cpp`）；keymap v2 1,600 B sha256 `bd9cfc34…`（仅 A 与 D-Pad）；全量 `k2nx-patched-vs-v1.0.1.diff` → 48,545 B sha256 `f79ad811…`（9 文件 +778/−56）；ELF 113,892,192 B sha256 `db84100d…`、NRO 42,363,510 B sha256 `012bc811…`；**A8 中文 CN NSP**（version 1.0.7）2,870,873,816 B sha256 `ec74b0b4…`（PROVENANCE `f61085e9…`），`package nsp verify` 19 checks（18 ok + 1 warn 未签名），Citron 首启解包 23 文件 2,704 MiB → 中文标题/正文 → MINUS 确认退出干净、0 异常。
- **证据**：`docs/milestones/evidence/P6-*`（g1/g2/g3 截图 + glog + k2s，12 文件 + sha256 清单）、`P6a-a8-*`（A8 冒烟 6 文件 + 清单）；文档 `docs/builds/013-k2nx-controller-input-v2.md`；真机安装与验收见 `docs/pilot/P4-device-runbook.md` §11。
- **限制**：①B 不是 ESC（见上，属刻意偏差）；②左摇杆滚轮为单步脉冲而非连续滚动；③光标/ZR/ZL 点击依赖虚拟光标（首次操作自动显示）；④真机未验证（A8 待用户装机）；⑤长流程与鉴赏模式未遍历。
---

**【v1.6】P7 输入微调与封面（patch H，A9，模拟器级完成）**

- **背景**：A8 真机初测通过后用户反馈（m12633）：①默认映射再加一条「R 键 = Ctrl（按住持续触发）」；②左摇杆上下与预期相反——上推应触发上滚轮（游戏里打开 BackLog），下拉应触发下滚轮（下一句）；③用用户自己 p 的图做封面（已放在 `Workspace/`）。
- **R = Ctrl（按住持续）**：游戏 `sys_source/MainWindow.tjs:2121` 的 `SkipCheck()` 用 `System.getKeyState(VK_CONTROL)` 判断快进；引擎侧 `TVPGetKeyMouseAsyncState` 读 `_scancode[VK_CONTROL]`（`&1`=当前态、`&0x10`=曾按下）。patch H 在 `onPadKeyDown`/`onPadKeyUp` 对 `BUTTON_RIGHT_SHOULDER` 置 `_scancode[VK_CONTROL] = 0x11` 并派发 `InternalKeyDown(VK_CONTROL)`，抬起时 `&= 0x10` 并 `OnKeyUp` → 按住期间 skip 生效、松开即停，不改游戏 TJS。
- **滚轮方向**：patch G 原为 `v < 0 ? -120 : 120`；按游戏 `MessObject.MouseWheelAction(shift, delta)` 约定（delta>0 → LOG，delta<0 → 下一句）改为 `v < 0 ? 120 : -120`（摇杆上推 v<0 = 正 delta = 打开 BackLog）。
- **封面**：源图 `E:/Othergames/Nintendo Switch/Workspace/1.png`（2,028,803 B sha256 `668e1169…`，1242x1100）；候选 A-center / B-right / C-fit 三版对比后选 **B-right**（右偏裁剪 x0=142，标题与五人完整）→ `examples/pilot01/icon-cover.jpg`（32,607 B sha256 `fb896d18…`，256x256 JPEG，NSP control icon）与 `docs/assets/pilot01-cover.png`（470,665 B sha256 `561561b1…`，512x512，README 展示）；A9 manifest `examples/pilot01-haruno-cn4.yaml` 的 `switch.icon` / `package.icon` 均指向该 JPEG。
- **验收（Citron h1，run `20261030-215600-kirikiroid2`）**：`[pad] ctrl down/up` 有效，按住 R 4 s 从 `@0000A_Z01.ks` 快进跨章到 `@0000A_Z02.ks`（0 exception）；W 按住 1.2 s → `[pad] wheel 120` 且截图出现 BackLog 面板（`Prologue` + 中文历史行）；S 按住 → `[pad] wheel -120` 回正文并推进；B 关面板后 A 仍可推进。
- **产物**：patch H `docs/builds/patches/k2nx-switch/H-input-tweaks.patch`（2,390 B sha256 `b28b77bd…`，1 文件 +20/−1；roundtrip 校验 patch 后 MainScene.cpp sha256 `c580b4c3…` 与构建树一致）；全量 diff `k2nx-patched-vs-v1.0.1.diff` 49,817 B sha256 `5e2726ac…`（9 文件 797/56，A→H）；引擎 ELF 113,892,216 B sha256 `3561b5d8…`、NRO 42,363,510 B sha256 `e9257fd1…`；A9 中文 CN NSP 2,870,911,192 B sha256 `ee0603b4…`（PROVENANCE 14,064 B sha256 `537c2ae7…`，version 1.0.8 / version_code 65544 / title_id `010047410000A000`），`package nsp verify` 19 checks / 18 ok / 1 warn（未签名预期）。
- **证据**：`docs/milestones/evidence/P7-h-*`（6 截图 + glog + k2s + sha256 清单）、`P7a-a9-*`（A9 首启冒烟 5 截图 + glog + k2s + 清单）；文档 `docs/builds/014-k2nx-input-tweaks.md`、runbook §11（v1.5 更新）。
- **限制**：①R=Ctrl 与游戏自身 skip 状态叠加，无单独「skip 开关」UI；②滚轮仍为单步脉冲（每次越过阈值只发一次），不能连续滚；③封面图由用户提供，仅本地打包使用，不随仓库对外分发原图；④A9 与其他产物共用 TitleID `010047410000A000`，装机即覆盖；⑤真机未验证。

- 【v1.7】封面归属：本节封面只属于《晴霁之后定是菜花盛开的好天气》这一款游戏，不代表 GalNX 项目形象；后续每款移植游戏各自制图（`examples/<game>/icon-cover.jpg` 256×256 JPEG 作 NSP icon、`docs/assets/<game>-cover.png` 作文档展示），规则写入 README `## 约定` 第 7 条与 `docs/builds/014` §4。

## 11. 建议的仓库目录（初稿）

```text
GalNX/
├─ README.md
├─ docs/
│  ├─ ARCHITECTURE.md
│  ├─ ROADMAP.md
│  ├─ TOOLCHAIN_AUDIT.md
│  ├─ TESTING.md
│  └─ decisions/                 # 架构决策记录（ADR）
├─ schemas/
│  └─ game-manifest.schema.json
├─ src/galnx/
│  ├─ cli/
│  ├─ manifest/
│  ├─ analyzer/
│  ├─ engines/
│  ├─ input/
│  ├─ build/
│  ├─ package/
│  ├─ test_backends/
│  ├─ device/
│  └─ artifacts/
├─ adapters/
│  ├─ krkr/
│  ├─ renpy/
│  ├─ onscripter/
│  ├─ web/
│  └─ fvp/
├─ profiles/
│  ├─ input-defaults/
│  └─ engines/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ fixtures/
├─ workspaces/                   # 可被清理，不提交原始游戏数据
└─ artifacts/                    # 构建输出、测试报告；按需忽略/外置
```

具体目录名可以随 Agent 的技术设计调整。原则是不要把第三方仓库源码直接混入核心逻辑；能作为独立子模块、固定版本外部依赖或构建依赖时优先保持边界。

---

## 12. 主要风险与待决策问题

| 问题 | 风险 | 建议验证方式 |
|---|---|---|
| 各类引擎的资源/脚本兼容范围 | 识别引擎不等于所有版本/插件兼容 | 每个适配器建立已测试游戏/版本清单，标注已知问题 |
| 专有引擎和游戏专用插件 | 可能需要大量逆向、重实现或兼容补丁 | 先寻找已有重实现和公开格式文档；给适配设置独立预算与退出条件 |
| Web 游戏依赖 Electron/Node API | 普通 Web runtime 不一定支持文件系统/Node 模块 | 先检查包结构、依赖及调用点，制作最小可运行样本 |
| 资源/补丁版本漂移 | 官方更新可能导致补丁失效 | 记录文件哈希、版本特征和补丁前置条件；不匹配时阻止静默构建 |
| NSP 生成路线 | forwarder 与完整应用包的行为不同 | 在 manifest 明确 `target_package_type`，验收分别进行 |
| 模拟器与真机差异 | 测试误报或漏报 | 记录测试平台和结果来源，不允许自动把模拟器通过改写为真机通过 |
| 可复现构建 | 上游分支变化或远程依赖改变结果 | 固定 commit/tag、容器镜像 digest、包版本和下载哈希 |
| 手柄映射冲突 | 热键误触发游戏操作，按键状态卡住 | 输入层集中拦截热键；测试 down/up、重复和焦点恢复 |
| 存档隔离 | 多游戏互相覆盖或路径变更导致存档丢失 | 以游戏 ID/标题 ID 为命名空间，提供备份/迁移策略 |
| 真机部署及日志 | 网络、应用退出后日志丢失 | SD 卡日志为基础，网络诊断为增强功能 |
| 前向兼容和系统风险 | Homebrew/NSP 转发方式可能受固件变化影响 | 工具与固件组合记录在测试矩阵中；明确风险并避免系统修改成为第一阶段条件 |
| 第三方许可证 | 引擎/工具可能要求署名、源码提供或保留版权声明 | 为每个适配器记录许可证、补丁差异、NOTICE 和分发要求 |
| 【v0.2】上游分发/网络可复现性 | devkitPro 包站对直连返回 403（Cloudflare）；Ryujinx 官方源 TLS 不可达、镜像需登录、GitHub 镜像被 DMCA 屏蔽 | 包下载显式走代理 + UA；把所需包/源码归档进本地缓存并留 SHA-256；报告证据等级如实标 `not-verified` |
| 【v0.2】构建路径含空格 | devkitPro make 工程在含空格路径下 `$(CURDIR)` 拆词失败（junction/短路径均无效） | 构建工作区强制放在无空格路径（如 `E:\galnx-build\`），产物归档回带空格的工作区 |
| 【v0.2】Ren'Py 交叉编译 | 官方无 Switch 平台且明确不支持 cross-compiling；唯一硬阻塞是 CPython 3.12.8 → devkitA64/newlib | 先做 4–6 周 go/no-go 探针；未过则改走 Switchroot Android + 官方 Android 构建 |
| 【v0.2】GPL/AGPL 传染 | hacBrewPack 为 GPL-2.0、Carafe/Autorun 为 GPL-3.0、BurialNX 为 AGPL-3.0 | 一律以子进程/文档参考方式隔离；不复制其代码进 GalNX 源树 |
| 【v0.3】模拟器无法加载 nx.js 系 NRO | Ryujinx Canary 1.3.265 加载 Brewser/上游 nx.js 的 NRO 时停在 guest 启动前（根因未定位，代码段约 44 MB 为差异线索）；普通 homebrew 正常 | **【v0.4 已缓解】**换 Citron Neo nightly 0237a9b88 后 Brewser 完整运行 2/2 → 归因 Ryujinx 环境问题；Ryujinx 降为第二意见 |
| 【v0.4】模拟器生态萎缩 / DMCA | Suyu 已 451、Eden/Sudachi/Ryubing 404、Ryujinx 官方源不可达、Lockpick_RCM 451 → 依赖面收窄，长期可维护性差 | 测试后端多版本本机留档并记录资产 SHA-256；不把模拟器放入发布路径；真机为最终依据 |
| 【v0.4】Citron 资产≠tag / GPL | release 资产由 nightly commit 构建，与 tag commit 不一致；仓库为 GPL-3.0-or-later | 锁**资产 SHA-256** 而非 tag；仅作外部工具，不捆绑/不分发其代码（GPL 不传染） |
| 【v0.4】keys 合规 | keyset 属用户主机派生数据，分发/入库/入日志有法律与安全风险 | `GALNX_PROD_KEYS` 只读、只记录 path+size+SHA-256、`.gitignore` 覆盖、日志脱敏、CI 禁注入 |
| 【v0.4】NSP 非确定性构建 | hacBrewPack 用 RSA-PSS 随机盐，两次产物不同 | 不做 bitwise 对比；用 nstool 结构校验 + TitleID/名称/图标断言 + 输入哈希 |
| 【v0.5】hacBrewPack 强依赖 keyset | 即使 `--plaintext` 也要求 keyset（rc=1），CI/离线环境无 keyset 无法真实出包 | 真实模式=显式 `--keyset` 参数（不内置路径/不 fallback）；CI 只跑合成 keyset 冒烟并标 `NOT INSTALLABLE`；keyset 只记元数据不入库 |
| 【v0.5】homebrew NSP 未签名 | 无任天堂私钥 → NCA/ACID 签名 FAIL 属预期；Citron 可运行，真机需 CFW+sigpatches，且属封禁风险面 | 模拟器结果不得冒充真机结论；真机验收（M3-d）只在用户设备+CFW 下进行并如实记录；用户文档写明风险 |
| 【v0.5】Citron 单实例与模拟器竞态 | 同 yuzu 血统只能有一个实例跑游戏；多 Agent/多任务并发会互相阻塞甚至误杀进程 | harness 内置 `citron_already_running` 失败码；跑前 tasklist 检查、禁止 `--allow-existing` 抢占；多任务用时间窗排队（M2-c/M3-b 已实践） |
| 【v0.5】DSH 环境变量脱敏 | 运行时剔除名字含 `KEY/PASSWORD/SECRET/TOKEN` 的子进程变量 → `GALNX_PROD_KEYS` 等通道失效 | 改用显式参数传 keyset 路径；文档与脚本不得依赖此类环境变量 |

| 【v0.6】Brewser localStorage 跨 run 落盘未验证 | M4-b 实测 `apps/<appId>/localStorage/` 运行中为空目录，页内 localStorage 正常但未确认跨进程/跨 run 落盘 → M4 存档阻塞项 | 存档先按 GalNX 宿主侧管理 + Web 内容包导出/导入 JSON 设计；落盘机制列为遗留验证项，真机复测 |
| 【v0.6】ONScripter-NX GPL-2.0-or-later 法务 | ONScripter-NX / ONScripter-jh 均为 GPL-2.0 系，直接链入 GalNX 会涉及整体许可边界 | 仅作外部适配器（独立进程/独立产物），源码不并入 GalNX 核心；分发前做许可确认并保留 COPYING 与来源记录 |
| 【v0.6】run_spec 仅 Citron + 真机未验证 | M4-a 适配器 `run_spec` 暂固定 Citron 参数；真机（hbmenu / Atmosphère）启动参数与 NRO 放置未实现 | 标注 experimental；真机接入（M3-d/M5）时补 device backend 的 `run_spec`，不据模拟器结论推断真机 |
| 【v0.7 → v1.10 已解决】rfvp 性能不可玩 | 软光栅渲染：Citron 17.5 fps、host 14.81 ms/帧（1280x720）、上游 issue #39 旧 commit 真机 ≈885 ms/帧 → 不满足可玩阈值。**【v1.10】已解决**：改用 SDL2/GLES2 后端后 Citron 实测 60.0 fps、render 15.57 ms（含 vsync）（M5-c）。 | 性能门槛关闭；rfvp 仍为研究项（真机/音频/CJK 未验），不进入首批适配（见下方新风险行）。 |
| 【v0.7】rfvp Windows 构建补丁需维护 | `platform/switch/host/build.rs` 用无扩展名路径探测 devkit 工具，Windows 下 `cc` 回落宿主 mingw 产生 COFF 对象导致 ld 失败；本地补丁未提交上游（008 §3.4） | 补丁归档到 `docs/builds/patches/rfvp-windows/`（待 M6-b/下轮）；升级 HEAD 时重打并复测；CI 在 Linux 无此问题 |
| 【v0.7】batch 只做预检、不执行构建 | M6-a 的 `batch run` 只跑 manifest→preflight→engines plan；真实构建执行/缓存/依赖锁定归 M6-b。单项目失败隔离目前只在预检层验证 | 文档明确 `batch` 不产生构建产物；M6-b 实现构建执行时沿用同一报告结构与失败隔离约定 |
| 【v0.8】构建缓存/依赖锁定的验证边界 | 缓存 key 含项目根路径与工具链首行版本，跨机器/跨路径命中不保证；`--locked` 只比对 `engine-lock.json` 记录的 adapter/pinned_commit/build_backend/toolchain/manifest_sha256，不覆盖编译器内部版本差异 | 缓存定位为本地加速而非可复现保证（可复现仍靠 pin + 产物 SHA-256）；CI 每次 `--no-cache` 或独立 cache 目录并归档 lock 文件 |
| 【v0.8】真实引擎 build.commands 未接入 | M6-b 只验证执行器/缓存/锁定本体（demo-build 的确定性 `python build.py`）；krkrsdl2/ONScripter-NX/NSP 的真实编译命令仍是脚本/文档化流程 | 引擎准入时逐个固化 `build.commands` 并用 `batch lock` 记录 pin；接入前不得宣称 `batch build` 能产出引擎产物 |
| 【v0.8】GUI 后置 | M6 第 3 条验收要求 CLI 稳定后再设计 GUI；当前交互全部为 CLI/JSON | GUI 不计入 M6 完成判据，作为 M6 之后独立工作项；先补 CI 门槛与真实引擎 build.commands |
| 【v0.9】K2NX 许可非 OSI | KiriKiri 系许可（NOASSERTION），不适合作为可自由分发的组件 | 仅本地构建/验证；产物（NRO/NSP）不入库、不分发；对外发布前做法务确认 |
| 【v0.9】物理手柄/真机路径未验证 | 本轮手柄语义经「Citron 键盘→虚拟手柄 + 游戏内 per-game KeyMap」，不是物理手柄 | P4 用物理手柄复核；真机验收另立证据，不据模拟器推断 |
| 【v0.9】Citron 单实例静默转发 | 多任务同时启动会合流到同一进程（yuzu 血统），互删 SD 数据导致证据作废（本轮已发生一次） | 启动前 `tasklist` 断言 0 实例 + 任务级「申请-释放」制；混跑 run 一律作废并标注 |
| 【v0.9】大 romfs NSP 与 FAT32 | 2.9 GB NSP 尚在 FAT32 单文件 4 GiB 内但余量有限；真机拷贝耗时/安装空间未验 | 保持小于 4 GiB；真机用 exFAT 或评估数据分层方案 |
| 【v1.0】NSP 形态鼠标注入无效 | 同一坐标在 NRO 形态可点中、在自包含 NSP 形态无响应（P2 RUN C/E/F，P3 A3 冒烟同样未用鼠标）；原因未定论 | 验收以手柄路径为准（已通过）；鼠标留给后续排查，不阻塞 P4 |
| 【v1.0】TitleID 必须合规（A2 反例） | A2 的 `010047410000b0b4` 低 13 位落在 DLC 区段，被 `validate_base` 拒绝；A3 改 `010047410000A000` 后通过 | 新项目一律先 `validate_base` 再分配（决策 15）；历史 A2 仅作证据、不得复用或分发 |
| 【v1.0】harness 判据与 wipe 陷阱 | ①`result.json focus_ok=false` 时 PostMessage 键盘仍生效（不得以 focus_ok 判输入失败）②wipe 若不含 `sdmc/switch/kirikiroid2/.preference/` 可能被选择器历史污染伪首启 | 输入成功判据 = steps/k2s 日志/截图三合一；标准 wipe 清单纳入 `.preference/`（`docs/pilot/P3-smoke-independent.md` 已记录） |
| 【v1.0】overlay 与 portlibs 未 pin 残留 | k2nx 保持 overlay（第三方 + NOASSERTION）；自建 portlibs 中 jxrlib/blend2d 等未以提交号 pin | P4 前补齐 portlibs pin 并写入 engine descriptor 的 `portlibs` 段；对外分发前法务确认（R7） |
| 【v1.1】手柄存档热键绑定本作 TJS API | `MainObj.SaveAction` / `_SAVELOADOBJECT` / `nSAVE_SC` 都是 BASE ADV SYSTEM 的私有实现，换引擎或换游戏要重写表达式；`TVPExecuteExpression` 失败只写日志、无 UI 反馈 | 表达式集中在 `GalNX_QuickSaveLoad()`（`MainScene.cpp`），改法记录在 `docs/builds/010` §6 E6；新作接入先 `typeof MainObj` 探针再启用热键 |
| 【v1.1】合成触摸注入不可用 | 引擎内 `handleTouchesBegin` 伪造触摸在两次会话中让 Citron 进程硬终止（无 crash dump、citron_log 半行），且触摸对 ADV 层无意义 | 只用「虚拟光标 + onMouseClick」与 TJS 求值两条通道；真机触摸另在 P4 验证 |
| 【v1.1】patch 顺序与 CRLF 归一 | E 建立在 D 之上；`InGameMenuForm.*` 被脚本重写为 LF 而仓库其余源码是 CRLF，直接生成补丁会让 `git apply` 自动转 CRLF 导致 roundtrip 不一致 | 补丁按 A→B→C→D→E 应用（engine descriptor 的 patches 已注明）；生成前统一 CRLF，并在 `tmp/verifyE5` 做逐字节 roundtrip 校验（5/5 相同）；产物哈希作为一致性判据 |
| 【v1.1】GalNXLog 诊断写 SD | `sdmc:/galnx-input.log` 会随发布产物存在并持续增长 | 已集中为单函数，正式构建删除；记录在 `docs/builds/010` §6 E5 |
| 【v1.2】主窗口关闭 teardown 顺序 | Switch 上确认关闭主窗口若走 desktop 的 invalidate 路径，TJS 世界按任意顺序析构，`CheckDialog.tjs` finalizer 读 `MainWnd.SystemObj` 即报 `Member "SystemObj" does not exist`（真机 `Error Code: 2-0000`） | 主窗口确认关闭直接 `TVPExitApplication(0)`（patch F），不进入 TJS teardown；真机用 K2S 抽屉电源键复验 |
| 【v1.2】Window TJS 类缺 Win32 成员 | `MainWindow.tjs:3417` 读 `this.minimized`，K2NX Window 无该成员 → ESC 路径抛 `Member "minimized" does not exist`；仅模拟器复现一次 | `WindowIntf.cpp` 补 `minimized`/`maximized`/`minimize()`/`maximize()`/`restore()` 兼容成员；ESC 未端到端复现，列为遗留验证 |
| 【v1.2】X 诊断热键随产物发布 | patch F 把 X 映射到 `MainObj.onCloseQuery(true)`，会弹退出确认框；误触可能退出游戏 | 诊断用 A5 保留以便真机复验；正式发布前移除 X 映射并重建（改动仅 1 行，无需新增补丁） |
| 【v1.2】A5 与真机验收边界 | A5 的退出修复目前只有 Citron 级验收；真机 K2S 抽屉电源键路径与模拟器 X 热键不完全等价 | 真机复验记录进 `docs/pilot/saveload-acceptance.md` §8；模拟器 PASS 不得写成真机 PASS |
| 【v1.3】CN 内容许可与分发边界 | A6 内含 X'moe 汉化衍生文本/图片，汉化著作权与游戏本体许可均不属本项目，重打包分发可能越界 | 只把 CN 产物当用户自有本地构建（DBI 上传到用户设备），仓库只提交流程/哈希/补丁，不公开分发 NSP 或 CN xp3；文档标注权利归属 |
| 【v1.3】TJS 不支持 `\uXXXX` | 脚本里若沿用 JSON 风格转义，字符串变成 `u5171` 字面量，autopath 静默失效（`@0000A_Z01.ks が見つかりません`） | 脚本生成一律写真实 UTF-8 字符并加 BOM；校验 = 反解 xp3 内 startup 检查不含 backslash-u |
| 【v1.3】CN 包覆盖面 | 只替换 data/scenario/image00，标题 LOGO、OP 影片字幕（movie_chs 197 MB）、部分大图仍是日文 | 文档明确 CN 适用范围；真机复验后按需追加 movie_chs / image0x_chs（PC 目录可提取） |
| 【v1.4】中文 OP 的编解码差异 | CN `opening.mpg` 114.48 s（134,811,648 B）与 JP 111.99 s 时长不同，K2NX 的 FFmpeg/VideoOverlay 解码差异可能导致黑屏、音画不同步或收尾卡顿；目前只在 Citron 单次验证（op1） | 视为可选增强，A6（日文 OP）保留为回退产物；真机验收时确认 OP 全程可播且可跳过，异常则回退 A6 |
| 【v1.4】A5/A6/A7 同 TitleID 互相覆盖 | 三个产物共用 `010047410000A000`，DBI/SD 安装会覆盖前一个；装机后若版本号不符会误判验收结论 | 装机前记录窗口标题版本号（1.0.4 / 1.0.5 / 1.0.6）并写入 `P4-device-runbook.md`；每次验收只装一个 |

| 【v1.5】B 键映射与用户期望的 ESC 不一致 | 本作 ESC 走 `EscapeWork()`→`minimize()`，Switch 上 `EscapeObj` 永不复位会假死；因此 patch G 把 B 实现为游戏原生「返回」而非 ESC | 文档（013 §2、runbook §11.3）明确该偏差；真机复验时单独确认 B 在各界面行为 |
| 【v1.5】patch G 改到 vendor 文件（不在上游 GitHub 树） | `CCController-switch.cpp` 由 pin 的构建环境（cocos2d-x current-3.11.1）提供，上游 K2NX 仓库无此文件，补丁无法从上游源码完整重放 | G patch 自包含该文件 diff；README/013 记录；重建机需保留同一 vendor 快照（构建根 `/e/galnx-build/pilot-01/k2nx-ws/src`） |
| 【v1.5】A5/A6/A7/A8 同 TitleID 互相覆盖 | 四个产物共用 `010047410000A000`，每次安装覆盖前一版；混装会误判验收结论 | 装机前记录窗口标题版本号（1.0.4/1.0.5/1.0.6/1.0.7）；runbook §11.1 标注 A8 取代前序，验收只装一个 |
| 【v1.6】R=Ctrl 与游戏 skip 状态叠加 | 按住 R 即让 `getKeyState(VK_CONTROL)` 恒真，游戏 `SkipCheck()` 持续快进；松开才停，无法只「点一下」进入 skip | 用户可知：想快进就按住 R；文档 014 §2 与 runbook §11.3 已写明 |
| 【v1.6】封面图著作权 | 封面由用户 p 图提供，随 A9 内嵌 256x256 JPEG；仓库内只保存裁剪后 icon（`examples/pilot01/icon-cover.jpg`）与 README 展示图 | 仅本地分发，不对外发布母图；如需公开须自行确认素材授权 |
| 【v1.6】A9 覆盖 A8 | A8 已真机初测通过，A9 与其同 TitleID `010047410000A000`，安装 A9 会覆盖 A8；若 A9 出问题无法并存回退 | 保留 A8 NSP 文件（`E:/galnx-build/pilot-01/p6/out/`）以便重装回退 |

| 【v1.8】patch I 退出保存是 best-effort | 收尾用 TJS `TraceSave`/`SystemSave` + 1 s 延迟 `TVPExitApplication(0)`；若 TJS 抛异常，进程仍退出但 system/trace 不更新（glog 缺 `[close] persisted …` 行） | 真机以「退出后重进设置是否保留」判断；缺行按 best-effort 记录，不阻塞验收 |
| 【v1.8】Citron 虚拟光标下 clickpost 失效 | 光标有独立命中逻辑，外置绝对坐标点击不生效（i7 失败原因），「单 run 同时验光标与退出」不可行 | 验收拆双 run（i8 A/B）；真机由 ZR 自身点击；不把 harness 限制写成产品缺陷 |
| 【v1.10】rfvp SDL2/GLES2 后端只有 Citron 级验收 | 60.0 fps 与画面正确性只在 Citron 0237a9b88（Vulkan）观察；未上真机，也未测 hbmenu/Atmosphère 下 SDL2 窗口与 GLES2 驱动行为 | 真机验收前不改「研究项」定性；上机时先跑 sdlbench 等价最小程序再跑 rfvp |
| 【v1.10】rfvp 音频 / 手柄 / 中文未接 | 本次只换渲染层：音频仍是 stub、输入未做 VN 语义映射、中文输入（nls gbk）与字体回退未接 | 按 rfvp 试点顺序：手柄映射 → 中文 → NSP 打包 → 真机；每项单独出证据，不合并验收 |
| 【v1.10】rfvp 后端函数面与 upsert 隐式契约 | C shim 只实现 create/update/destroy/begin/draw_quad/draw_solid/present/capture_thumbnail；upsert 语义是引擎行为推出来的隐式契约，上游若改为 destroy+create 或新增方法需同步 | 补丁 README 与 016 文档已写明 upsert 约定；升级 rfvp pin 时先跑文字/纹理回归（标题 + 正文可见） |
| 【v1.10】rfvp 许可组合未确认 | rfvp=MPL-2.0、SDL2=zlib、libnx/EGL/drm_nouveau 混合；当前只本地构建、未对外分发 | 对外发布前做许可清单与源码可得性确认；产物不入库、不分发 |
| 【v1.11 → 已部分解决】rfvp 无存档槽位 UI | 游戏内 SAVE/LOAD 面板只认指针、且桌面专属 `legacy_save_load_ui` 在 Switch 不存在；不处理则点中即挂起 VM | **【v1.11】已兜底**：patch J 把 pending 请求自动落到引擎快速槽 0（`rfvp_s000.bin`），并提供 PLUS+ZR/ZL 热键；**未解决**：多槽位/缩略图/注释面板仍是桌面专属，需自建 UI |
| 【v1.11】rfvp 组合键与真机输入未验证 | PLUS+ZR/ZL 的组合语义只在源码层实现；Citron harness 的按键注入是逐键 PostMessage，不能同时按住两个键，真机 JC/Pro 手柄行为也未测 | 上机首项验证组合键；失效时退回「单键临时映射 + 热键表固化」；文档 017 §10 已列 U1–U7 |
| 【v1.11】rfvp system 菜单指针命中精度 | 菜单在屏幕右缘（虚拟 x≈1255），光标 12 px/帧且不显示 hover 高亮，靠手柄悬停选中代价高；实测四次按键后画面 sha 完全不变 | 不把「手柄操作游戏自带菜单」列为 MVP 验收项；改用热键旁路；若需菜单，下一步补「光标加速档位」或移植简易槽位 UI |
| 【v1.12】rfvp NSP 体积与文件系统 | 自包含 NSP 9,979,435,224 B；FAT32 单文件上限 4 GiB 装不下，必须 exFAT SD 或足够 NAND；DBI FTP 实测 1,548.7 s ≈ 6.15 MiB/s（约 25.8 分钟） | 真机验收前确认 SD 为 exFAT；上传用 DBI FTP 并预留 ≥30 分钟；把「NSP 体积 + 上传耗时」写进真机 runbook |
| 【v1.12】romfs 首次读取与内存余量 | romfs 冷读 9.2 GiB，真机 I/O 特性与 4 GB 机型内存余量均未测；Citron 上 t=8.8 s 加载完成不能代表真机 | 上机先测进正文耗时与内存峰值；异常时退回 SD 目录形态或按章节拆分内容 |
| 【v1.13】宏点击依赖屏幕坐标 | 引擎热键（Y/PLUS/MINUS/X）用「Esc 开暂停菜单（或直接用工具栏）+ 固定像素点点击」实现，菜单与工具栏位置随游戏分辨率/UI 缩放变化即失效；缓解 = 锚点由 Citron 悬停扫描实测并写死在 `event.rs`（1280×720 游戏坐标），换游戏必须重新扫描；本作已实测 SAVE/LOAD/EXIT/AUTO 四点命中 |
| 【v1.13】R=Ctrl 跳读语义未在模拟器复现 | 引擎确实把 `Control` 写入 `new_input_state`（`input_manager.rs:383`），`anzu_scene.rs:49` 的 dissolve 快进也读该位，但 Citron 里按住 R 只前进一句、未连续跳读；可能属游戏脚本层面的 `TextSkip` 调用条件，留给真机复验（U3），若真机也不跳读则改用「按住 R 连发左键」备选 |
| 【v1.14】主机层光标与游戏自绘光标可能并存 | 光标由 SDL overlay 画（`sdl_video.c`），游戏在收到 PointerMove 后也会画自己的小菱形 → 两个指针同时出现；本作实测两者位置一致（游戏光标为淡青菱形、主机为黑边菱形），视觉上略重复 | 若真机反馈干扰，可在 overlay 侧加「收到指针事件后 2 s 内不画主机光标」或统一关闭游戏侧光标；不阻塞交付 |
| 【v1.14】主机确认框仅英文 5×7 点阵 | `QUIT GAME? / A = YES  B = NO` 无 CJK 字形，与中文游戏界面风格不一致；纯 SDL 手写点阵，扩展中文需内嵌字库（体积 + 许可） | 当前按「无歧义 + 零依赖」优先；若后续统一 UI 语言，可改为引擎内 TJS 对话框，或引入 stb_truetype + 子集字体（需另立任务） |
| 【v1.15】GPU prev-frame 依赖 render target | prev-frame 改为两个 `SDL_TEXTUREACCESS_TARGET` 离屏纹理轮换，需真机 SDL2 后端支持 render target 与 `RenderCopy`；Citron 正常，真机未验证 | 保留 CPU `capture_thumbnail` fallback（`supports_gpu_prev_frame()` 为 false 时自动回落）；真机若花屏/黑屏，先关 GPU 路径复测（U21），确认后再回滚方案 |
| 【v1.15】启动与存档尖峰仍在 | 冷启动帧 1/4 slow 1744/818 ms（`vfs_read` 675 ms + `graph_decode` 521 ms）；存档帧 save 26.8–54.8 ms（`save_finalize` 13.5–32.4 ms + 缩略图 11 ms，约每 2 分钟） | 下轮可做：纹理/脚本预热与异步解码、`GLOBAL_SAVE_INTERVAL_US` 延长或仅 dirty 时写、缩略图降低采样；不阻塞本轮真机复验（U19/U20） |

### 第一版需要由用户/Agent 明确的决策

1. 【v0.2 已拍板】工作台采用 **Python CLI**（之后才加 GUI）。
2. 【v0.2 已拍板】第一款端到端测试游戏 = **krkr-ns**（KiriKiri 引擎，源码自建；tag 已移动故不以 release NRO 为基线）。【v0.4 细化】KiriKiri 走**双层路线**：先用 `krkrsdl2` 上游本体（MIT、官方 CI 出包，HEAD `124bdf84`）验证「自有 data.xp3 → NRO」可复现构建，再用 krkr-ns 做启动器产品化（详见 §7.2【v0.4】引擎路线复核）。
3. 【v0.2 已拍板】第一版**先 NRO + 模拟器**，同时保留真实 NS1 的手动验收项（用户已有可用 NS1 真机）；不以模拟器结果冒充真机结果。
4. 【v0.2 已拍板】NSP 首个目标 = **自包含包**（ExeFS+RomFS），forwarder 仅作对照实验。
5. 【v0.3 已完成·阻塞】Web 方案先做 **Brewser 最小冒烟可行性验证** → 已执行并交付 `docs/experiments/web-01-brewser-smoke.md`：本机 Ryujinx 1.3.265 无法加载 nx.js 系 NRO（普通 homebrew 对照正常），结论 `not-verified`；M4 验证改走真机或换模拟器/版本。Teaching Feeling 是否适合作为首个 Web 目标，待其发行包结构/Electron/Node 依赖核验后再定。
6. 【v0.2 已延后】输入事件模型初版只读外置配置，**配置热加载延后**。
7. 【v0.5 已拍板】keyset 传参改**显式 `--keyset` 路径**（不依赖环境变量、不内置默认路径、不 fallback）；CI/离线冒烟只跑合成 keyset 并标 `NOT INSTALLABLE`。
7. 【v0.2 新增·已拍板】**GitLab 路线绕行**：用户在本机无法注册/登录 GitLab，也不接受依赖需登录的镜像；GalNX 不依赖任何 GitLab 资源，Ryujinx 改为“本机留档 + SHA-256 校验 + 断网使用”，证据等级标 `not-verified`。
8. 【v0.2 新增·已拍板】**Ren'Py 方向**：不接入任何无许可证的社区移植仓库；以 `renpy/renpy`（主源码）+ `renpy/renpy-build`（构建仓库）的**官方源码独立移植**为方向，可行性见 `docs/audit/04-renpy-official.md`（结论：唯一硬阻塞=CPython 3.12.8 交叉编译，建议先 4–6 周 go/no-go 探针）。
9. 【v0.4 已拍板】**测试后端优先级**：Citron Neo（开发循环/CI 冒烟，实测可跑 Brewser）→ 本机留档 Ryujinx 1.3.265（第二意见/回归对照）→ 真机 NS1（唯一验收权威）；模拟器结果不得写成真机通过。
10. 【v0.4 已拍板】**keys 使用策略**：直接使用本机 Ryujinx 自带 `prod.keys`/`title.keys`（用户已授权，本机自用）；框架只读、只记录元数据，禁止入库/入日志/进 CI/随产物分发；真机提取只写文档步骤（Lockpick_RCM 已被 DMCA，不提供下载源、不内置 payload）。
11. 【v0.4 已拍板】**构建后端改用 CMake**（含空格路径实测通过），make 模板仅作参考；构建根仍建议无空格路径。
12. 【v0.9 已拍板】**首款垂直试点引擎 = Kirikiroid2-NX（路径 A 源码重建）**：三补丁 + 自建 portlibs + 自包含 NSP；模拟器验收已通过，随后才做真机（P4）。不以模拟器结果冒充真机。
13. 【v0.9 已拍板】**手柄映射走 per-game `Kirikiroid2Preference.xml`**：用游戏内 `<KeyMap>` 把引擎的 `VK_PAD*` 映射到游戏认的 `VK_RETURN`/方向键，不改引擎源码；该文件由 GalNX 生成并随 NSP romfs 分发，引擎不覆写（实测 mtime 不变）。
14. 【v0.9 已拍板】**Citron 使用「申请-释放」制**：任何任务启动 Citron 前须 `tasklist` 断言 0 实例并与当前持有者交接；用完 `taskkill` 并回报释放时间；一旦并发/混跑，该轮证据作废。
15. 【v1.0 已拍板】**TitleID 分配必须合规**：base title id 以 `0x2000` 对齐（`0x…000/0x…2000/…`），不得落在 DLC 区段（`base|0x1000|index`）或系统保留区；由 `galnx package nsp` 内置 `validate_base` 强制，计划期就用 GalNX 分配块 `0x0100474100000000–0x01004741FFFFFFFF` 内取值（本期 A3 = `010047410000A000`）。
16. 【v1.0 已拍板】**Citron 自动化一律 `--detach`**：harness 用 WMI 建脱离进程树 + `--wait-job` 轮询 `.done`，不再依赖「调用方 shell 活着」；`launch_route`（direct/runas-deelevated/schtasks-limited）必须写入 result.json 并进证据，避免 R14 类假失败。
17. 【v1.0 已拍板】**k2nx 保持 overlay 适配器**：builtin（`src/galnx/engines/registry.py` 的 `BUILTIN_ENGINES`，当前 3 个：brewser/krkrsdl2/onscripter-nx）只收许可证清晰、可自由分发的引擎；K2NX 属第三方试点且 license=NOASSERTION，以 `examples/engines/kirikiroid2-nx.yaml` + `engines prepare` 方式使用。
18. 【v1.0 已拍板】**NSP 验收比对用组件哈希**：hacBrewPack 的 RSA-PSS 签名含随机盐，NSP 字节级不可复现；oracle 用 exefs/main + romfs 清单/摘要 + nstool 结构检查 + `game_files.txt`/KeyMap 单文件哈希。
19. 【v1.1 已拍板】**手柄操作优先「虚拟光标 + 原生 UI 热键」，不依赖触摸/鼠标注入**：docked 真机没有触摸屏，Citron 的触摸/鼠标注入对 ADV 层无效且合成触摸会崩；因此协议 = Y 开虚拟光标 + D-Pad 移动 + A/B 左右键（patch D），原生 SAVE/LOAD 界面由引擎热键经 `TVPExecuteExpression` 直接构造或调本作 TJS API（patch E），全程不碰触摸。
20. 【v1.1 已拍板】**引擎补丁按栈提交且必须可 roundtrip**：顺序 A→B→C→D→E，每个补丁对应 `docs/builds/patches/k2nx-switch/` 一个文件；生成后在 pristine 树做 `git apply --check` 并与构建树逐字节比对，换行差异必须归一（LF→CRLF 会让 `git apply` 二次转换）；再用 ELF/NRO 哈希确认补丁文本归一不改变产物（本轮归一前后哈希完全相同）。
21. 【v1.2 已拍板】**主窗口确认关闭 = 直接退出进程（patch F）**：Switch 上不存在「最小化到桌面」语义，主窗口确认关闭即离开游戏，走 `TVPExitApplication(0)` 并跳过 TJS invalidate teardown，从根上避免 `MainWnd.SystemObj` 类析构顺序错误；同时补 Window 的 Win32 兼容成员（`minimized` 等）以覆盖游戏 TJS 对桌面窗口属性的读取。不改游戏 TJS、不改引擎核心语义。

22. 【v1.3 已拍板】**汉化 = 数据层重打包 XP3，不逆向容器、不做 patch G**：汉化组已公开完整 UTF-8 源码，引擎原生支持 UTF-8/BOM、XP3 归档与子目录 autopath，故用自研 writer 重打包 data/scenario/image00 即可，零引擎改动；`haruno.xmoe`（242 记录、16 B 魔数、31 字节弱周期）与 `xmoeParser.dll` 逆向仅作备选记录在 P5 文档。

23. 【v1.4 已拍板】**汉化增强走「归档内同名文件替换」，不引入视频重编码链路**：PC 中文版 `movie_chs.xp3` 内的 `opening.mpg` 已是原生 mpeg1video 1280x720 + mp2 且带中文硬字幕（114.5 s），直接用 `xp3pack.py` 重打包成新 `movie.xp3` 替换同名文件即可，引擎侧 `[macPlayMovie]` 零改动；不做转码、不烧字幕、不追加字幕补丁；若真机播放异常则回退 A6（日文 OP），并保留 `movie_chs.xp3` 原文件作为可替换素材。


24. 【v1.5 已拍板】**手柄映射 v2 在引擎 pad 层实现，且不追 ESC 语义**：A/D-Pad 继续用 per-game `Kirikiroid2Preference.xml`，其余（B=原生返回、X=自动、Y/+=游戏原生读/存档面板、-=退出确认、ZR/ZL=鼠标左右键、右摇杆光标、左摇杆滚轮）全部在 `MainScene.cpp` 的 `onPadKeyDown`/`onAxisEvent` 内完成，不改游戏 TJS；B 刻意不映射 ESC（会经 `EscapeWork()` 假死），偏差写进 013 与 runbook。
25. 【v1.6 已拍板】**R=Ctrl 用 `_scancode` 位模拟，不改游戏 TJS；滚轮符号按游戏 `MouseWheelAction` 约定；封面由用户提供并只做本地内嵌**：引擎侧 `_scancode[VK_CONTROL]=0x11` 使 `System.getKeyState(VK_CONTROL)` 轮询生效（即游戏 `SkipCheck()` 的原生语义），避免注入式改写脚本；滚轮方向以 `delta>0 → LOG` 为准则；封面版权归用户，不进对外分发。


26. 【v1.8 已拍板】**退出前显式保存走 TJS 原生 `TraceSave`+`SystemSave`，并延迟 1 s 退出**：patch F/G 的立即 `TVPExitApplication(0)` 跳过了 `MainWindow.finalize()`（全树唯一 SystemSave/TraceSave 调用点，`MainWindow.tjs:542`），造成设置/存档元数据/continue 不落盘与「强制终了」判定；改为关闭路径先调本作收尾 API 再延迟退出，既保留 patch F/G「不让 TJS 乱序 teardown」的性质又恢复持久化；ZR/ZL 改为按住 `onMouseMove`+`onMouseDown/Up` 并重显淡出光标，`onAxisEvent` 的 `PrimaryLayerArea` 早退移到 `__SWITCH__` 块之后以覆盖标题/设置/存档画面。验证 = Citron i6/i8 + A10 冒烟 RUN A–D。
27. 【v1.9 已拍板】**首款垂直试点以 A10 真机验收为终点，目标完成**：用户 2026-10-31 真机确认 v1.8 四问题全部解决且暂未发现明显问题；A10（1.0.9，2,870,911,704 B sha256 `0efc23f6…`）作为本作交付基线，后续回归只做「不破坏 A10」的验证；试点遗留（长流程 / 分支 / 鉴赏模式未遍历、退出保存 best-effort、K2NX license NOASSERTION 仅私有使用）记录于 §12 与 `docs/pilot/P4-device-runbook.md` §12.3，不阻塞完成。
28. 【v1.10 已拍板】**Switch 显示层改用 SDL2/GLES2，libnx 只保留输入与音频**：CPU 软光栅在 Switch 上不可用（Citron 17–19 fps、render ≈38.8 ms/帧），而 SDL2 的 Switch 视频驱动在 Citron 内可满 60 fps（`sdlbench` 与 rfvp 改造双重验证）。因此新增 `platform/switch/runtime/sdl_video.c` 作为唯一显示出口（纹理 upsert、虚拟坐标 letterbox、blend 映射、`SDL_RenderGeometry`、`ReadPixels` 读回），Rust 侧 `HorizonRenderer` 只做转发；引擎核心与 `soft_raster` 保留不动（PC/其它后端仍可用），不重写 GPU 专用渲染器。

29. 【v1.13 已拍板】**rfvp 手柄映射在 Switch no_std 端 `event.rs` 实现，游戏内 UI 用「Esc 宏 + 实测锚点」复用原生界面，不注入 TJS、不改游戏数据**：上游 `event.rs` 把 ZR/ZL/R 全绑成 `Control`、PLUS 直接发 `Quit`，无法满足用户 m18283 的映射表；而 rfvp 的 `exit_confirm_ui`/`legacy_save_load_ui` 只在 winit（std）路径可用，no_std 下不存在现成 UI，故用引擎事件合成「Esc 开暂停菜单 → 指针移到 SAVE/LOAD/EXIT → 左键」三段宏复用游戏原生界面（AUTO 直接点工具栏），坐标由 Citron 悬停扫描实测后写死；代价 = 坐标绑定本作 1280×720 布局，换游戏需重扫，收益 = 零脚本注入、零游戏文件改动、与后续 NSP 打包解耦。

30. 【v1.14 已拍板】**退出确认与光标一律由主机层（SDL overlay）自绘，不依赖游戏 UI / 坐标宏**：原 MINUS=EXIT 走「Esc 宏开暂停菜单 + 实测锚点点击」，换画面或换分辨率即失效，且用户真机明确要求「按 − 要先确认」；`event.rs` 只产生 `pointer()` / `quit_dialog_open()` / `take_quit_confirmed()` 三个查询接口，`sdl_video.c` 负责画光标与确认框，A 确认进 `request_quit()` → 引擎正常关闭（全局存档落盘），B 取消。代价 = no_std 端自绘 UI 无 CJK 字库、风格与游戏不一致；收益 = 任意画面可用、与游戏 UI 坐标解耦、退出路径始终走引擎正常关闭（不再黑屏）。
31. 【v1.15 已拍板】**rfvp 渲染回读全部改成 GPU 侧，诊断回读默认编译关闭**：prev-frame 不再每帧 `capture_thumbnail` 回读 8.29 MB，改用两个离屏 render target 轮换（`PREV_FRAME_TEXTURE_ID` 解析为上一帧 target）；`debug_screen.bmp` 周期写由 `DEBUG_SCREEN_ENABLED=false` 关闭；宿主阶段计时保留在 debug_report（低开销，仅排障看）。理由：CPU 回读是转场卡顿主因（thumb 45–66 ms/帧）且 GPU 路径不改变引擎渲染语义；保留 CPU fallback 以防真机 render target 不可用。

---

## 13. Agent 协作方式建议

为了避免 Agent 在尚未验证上游工具前就大量写抽象层，建议按以下顺序推进：

1. **审计先于实现。** 逐个阅读所选仓库的 README、LICENSE、构建脚本、依赖定义、最近提交与已知问题。
2. **先复现上游。** 每次只选一个工具链，记录宿主环境、命令、产物、失败原因，不要直接把上游失败归咎于 GalNX。
3. **先建立最小端到端样板。** 从 manifest 读取一个已存在的移植工程，调用其构建脚本，输出 NRO，启动模拟器并归档日志。
4. **观察重复步骤再抽象。** 先实际构建两种工程，再决定哪些内容应进入统一接口，以免过早设计过度通用的插件系统。
5. **每项工作带有验收条件。** 不接受只新增代码而没有构建记录、测试结果或明确阻塞说明的里程碑。
6. **将研究结果落入文档。** 每个适配器维护 `README.md` 或独立兼容性矩阵，说明已验证、部分验证、未验证和不支持的项目。
7. **不要让 Agent 下载或提交商业游戏数据。** 测试资源由用户自行提供；测试 fixtures 应使用自制或可合法再分发的数据。

每次 Agent 完成任务，建议更新：

- `docs/TOOLCHAIN_AUDIT.md`：工具链状态、commit、依赖、许可证、可复现步骤。
- `docs/TESTING.md`：模拟器/真机环境、测试日期、测试结果和日志位置。
- `docs/decisions/`：需要长期保留的架构决定与原因。
- 版本化的 manifest/schema 和适配器兼容性声明。

---

## 14. 第一轮实际执行清单

以下清单适合作为计划获批后的第一个 Agent 任务集，不要求一次性实现全部功能。

- [x] 【v0.2】审核 devkitPro/libnx、KRKR-ns、RenpySwitch、Brewser/nx.js_extended、NTON、Carafe、Autorun、Ryujinx Canary-1.3.265 镜像的当前状态和许可证 → `docs/TOOLCHAIN_AUDIT.md` v1.1：26 个上游对象 / 27 条记录，全部带字段。
- [x] 【v0.2】把每个仓库的精确 URL、commit/tag、最后验证日期和许可证写入 `docs/TOOLCHAIN_AUDIT.md`（含未验证清单与需修正 URL：nx-hbloader、nx.js、nxlink、Ryujinx 镜像是重点）。
- [x] 【v0.2】在干净环境复现一个简单 Homebrew 工程的构建：devkitPro 补装（14 包）+ `m0-hello.nro`（166,085 B，sha256 `a341e775…`，make 退出码 0，`workspaces/m0-hello/`）。
- [x] 【v0.2】明确本机 Ryujinx 1.3.265 二进制与源码提交的对应关系 → 本机内部一致（`+4e81a4c` ↔ 7z Comment `4e81a4c2…`）；官方 tag↔commit 独立核验未完成，已标注 `not-verified`（`docs/TOOLCHAIN_AUDIT.md` §5）。
- [x] 【v0.5】建立 `game-manifest` 初版 schema 和 `galnx doctor` / `galnx preflight` 命令 → `galnx 0.1.0`（commit `1ebdb9a`），`doctor` 20 checks 0 fail/warn，`preflight` 可校验 manifest。
- [x] 【v0.8 完成·CLI 级】实现工作区、构建命令执行、stdout/stderr 日志保存、退出码归档 → `src/galnx/build/`（executor/cache/lock）+ `galnx build run` / `galnx batch build`，日志写 `<root>/.galnx/logs/`，退出码/超时/缓存状态进 JSON 报告。
- [ ] 通过配置调用一个现有适配器生成 NRO，并记录实际构建过程（注入点=`manifest.build.commands`，执行器已就绪；真实引擎命令尚未固化，见 §12【v0.8】`docs/builds/004-krkrsdl2-switch-fixes.md`）。
- [x] 【v0.5】在模拟器中完成一次最小启动测试 → Citron 0237a9b88：`m1-sdl2.nro` 渐变画面、`krkrsdl2` KAG3 标题/正文、自包含 `m0-hello` NSP（`Hello World!`）；真实 NS1 测试另行登记（M3-d），不根据模拟器结果推断。
- [x] 【v0.2】根据首次构建暴露的问题修订本文，而不是预先实现所有模块（本文 v0.2）。
- [x] 【v0.3 完成】Ren'Py 官方源码独立移植可行性审计 → `docs/audit/04-renpy-official.md`（7 条记录 / 84,638 B，全部 source-inspected；结论：唯一硬阻塞=CPython 3.12.8 交叉编译，建议 4–6 周 go/no-go 探针；是否进入探针待拍板）。
- [x] 【v0.3 完成·阻塞】Brewser 最小 Web 冒烟实验 → `docs/experiments/web-01-brewser-smoke.md`（158 行，`not-verified`；本机 Ryujinx 1.3.265 无法加载 nx.js 系 NRO，普通 homebrew 对照正常；M4 改走真机/换模拟器）。
- [x] 【v0.4 完成】工具链刷新复核（本机 17 包 17/17 最新、0 可升级；CMake 空格路径实测通过；Docker 不作基线）→ `docs/audit/05-toolchain-refresh.md`。
- [x] 【v0.4 完成】引擎路线复核与新增候选调研 → `docs/audit/06-engines-refresh.md`。
- [x] 【v0.4 完成】Web 路线复核 + Citron Neo 审计/实测（Brewser 2/2 通过）→ `docs/audit/07-web-citron.md`、`docs/experiments/web-02-citron-smoke.md`。
- [x] 【v0.4 完成】打包链与测试后端复核 + keys 合规策略 → `docs/audit/08-packaging-refresh.md`。
- [x] 【v0.5】M1 首项：把 `m0-hello.nro` 在 Citron/Ryujinx 中冒烟并归档日志（加载链健康检查）→ m0-hello 已以自包含 NSP 形式在 Citron 运行（M3-b）；NRO 形态未单独复跑（ELF→NSO 变体已由 `elf2nso` 流程覆盖）。
- [x] 【v0.5】安装 `switch-sdl2 2.28.5-4` + `switch-freetype 2.13.3-1`，验证最小 SDL2 窗口+字体链接 → `m1-sdl2.nro` 6,740,165 B sha256 `d46ae7c0…`（CMake 12.8 s exit 0，Citron 截图非黑 0.8907）。
- [x] 【v0.5 完成】M1：krkrsdl2 上游源码构建 + Switch 修复补丁 + Citron KAG3 出画面（`docs/milestones/M1-kirikiri.md`、`docs/builds/004-krkrsdl2-switch-fixes.md`）。
- [x] 【v0.5 完成】M2：输入数据模型 + CLI + Citron 注入 harness（`docs/milestones/M2-*.md`）。
- [x] 【v0.5 完成·模拟器级】M3：自包含 NSP 出包链 + Citron 直接引导（`docs/builds/005-nsp-selfcontained.md`、`docs/milestones/M3-nsp.md`）；真机安装=待用户设备。
- [x] 【v0.6 完成·模拟器级】M4：第二种引擎接入（`docs/milestones/M4-second-engine.md`）；M4-a 引擎注册表+适配器契约（krkrsdl2 nro/cmake-switch、brewser web/prebuilt，`galnx engines list|info|plan`，331 passed/60 subtests）、M4-b Brewser Web 端到端（`docs/builds/006-brewser-web-adapter.md`）、M4-c ONScripter-NX 评估（P2 有条件，`docs/builds/007-onscripter-nx.md`）；真机与 localStorage 落盘待后续。
- [x] 【v0.7 完成·研究级】M5：FVP/rfvp 评估（`docs/milestones/M5-fvp.md`）：构建 pin `nightly-2026-02-01`+devkitA64 r30（Windows 需 build.rs 补丁）→ `rfvp.nro` 1,372,216 B sha256 `4964dda9…`；Citron 渲染 Luax Painter + M=Plus→quit（输入链路成立）+ host harness 2/3；结论=继续研究（P3 研究项），不作首款原型。
- [x] 【v0.7 完成·M6-a】批量预检/报告 MVP（`docs/milestones/M6-batch.md`）：`src/galnx/batch/` + `galnx batch run|diff|clean` + JSON 报告 schema + 23 用例（367 passed/63 subtests）；单项目失败隔离（3 项目 2 ok 1 fail rc=2）；M6-b 真实构建/缓存与 M6-c 汇总待后续。
- [x] 【v0.8 完成·CLI 级】M6：批量构建执行 + 构建缓存 + 依赖锁定（`docs/milestones/M6-batch.md` §5A）：`src/galnx/build/`（executor/cache/lock）+ `galnx batch build|lock` + `galnx build run`；sha256 缓存 miss→hit（`out/demo.bin` 91 B sha256 `3c9b52aa…`）、`--rebuild`/`--no-cache`/`--locked` 实测；34 用例，401 passed/63 subtests；GUI 按计划后置，真实引擎 build.commands 与 CI 门槛留待后续。
- [x] 【v0.7 完成】M4-f ONScripter-NX 登记为第 3 内置适配器（`devkitpro-make` 后端，`galnx engines list` 3 个）+ M4-g Brewser localStorage 跨 run 持久化证伪（006 §12）。
- [x] 【v0.9 完成·模拟器级】首款垂直试点 P0–P2：P0 侦察（K2NX 预编译 NRO 读全部 14 个 XP3）、P1-b 引擎机制审计（`docs/pilot/P1-engine-k2nx.md`）、P1-d NSP 打包可行性（`docs/pilot/P1-nsp-packaging.md`）、P2 三补丁源码重建 + A2 自包含 NSP + 手柄验收（`docs/pilot/P2-acceptance.md`）。
- [x] 【v0.9 完成】K2NX 补丁包入库 `docs/builds/patches/k2nx-switch/`（diff 16,216 B sha256 `f36cbaa3…` + 3 个 apply 脚本 + `galnx_extract_v2.inc` + keymap XML 1,293 B sha256 `aa4fa8aa…`）；自建 portlibs 7 个（FFmpeg 3.2.19 等）。
- [x] 【v0.9 完成】A2 自包含 NSP 出包 + 实测：2,906,125,016 B sha256 `eb6c6a15…c705f`（title_id `010047410000b0b4`）；全新 SD 首启自动解包 23 文件（14.4 s）→ autostart → 手柄 RIGHT+C 进正文 → 二启 marker 命中（截图与首启逐字节相同）。
- [x] 【v1.0 完成】P3 打包工程化：`galnx engines prepare`（pin/脏树/补丁/portlibs/lock）+ `galnx payload plan|materialize` + `galnx package nsp plan|build|verify` 三条链；`examples/pilot01-haruno.yaml`（TitleID `010047410000A000`）一条命令链复现 romfs oracle（109 文件 / 2,878,186,922 B / `game_files.txt` sha256 `0e6757d9…` / KeyMap sha256 `aa4fa8aa…`）。
- [x] 【v1.0 完成】A3 合规 TitleID 自包含 NSP 构建 + 独立 verify + 两条 Citron 全新 SD 冒烟：NSP 2,906,131,672 B sha256 `1f54bdf105fdfc0e88a81e5aaec954ffd4c349132fe7bbadcf394948cde994d4`；`package nsp verify` 19 checks / 0 fail / 1 warn（未签名预期）；audit-package 独立 verify PASS；audit-web 独立冒烟 PASS 7/7（`docs/pilot/P3-smoke-independent.md`）。
- [x] 【v1.0 完成】`scripts/citron_run.sh --detach/--wait-job/--status`（WMI 脱离进程树 + `launch_route` + 陈旧日志检测）→ R14 修复；全量 600 passed / 63 subtests；CLI 统一 UTF-8 stdio。
- [x] 【v1.1 完成】**U20 存档/读档（模拟器级，全手柄）**：patch D（虚拟光标）+ patch E（`TVPExecuteExpression` 调本作 TJS 原生存档/读档热键），NRO + A4 NSP 双形态完成「PLUS 存 → `savedata010.bmp` 45,941 B + `system.bmp` 989 B 落盘 → 重启 → R 开 LOAD → A 读档 → 回到存档点 → C 续玩」；证据 `docs/milestones/evidence/P3g-*`（21 文件 + sha256 清单）、`docs/pilot/saveload-acceptance.md`、`docs/builds/010-k2nx-controller-saveload.md`。
- [x] 【v1.1 完成】A4 自包含 NSP（version 1.0.3）2,906,135,768 B sha256 `2003ec1eb1ccd78d4e74ff10965376a7248c00962262e7582258d8545fb03c39` + `package nsp verify` 19 checks / 18 ok / 1 warn；patch D/E 入库、`examples/engines/kirikiroid2-nx.yaml` 更新（save.supported=true、artifact_sha256=A4、patches 5 个）。
- [x] 【v1.2 完成·模拟器级】**U21 退出游戏**：patch F（主窗口确认关闭直接 `TVPExitApplication(0)`，并给 Window 补 `minimized`/`maximized`/`minimize()`/`maximize()`/`restore()` 兼容成员）；Citron exit3 验收 = 确认框「はい」→ `[close] main window close confirmed; terminating application` → guest 干净退出、k2s 0 error/exception；证据 `docs/milestones/evidence/P4a-exit-*`、`docs/builds/011-k2nx-exit-crash-fix.md`。
- [x] 【v1.2 完成】A5 自包含 NSP（version 1.0.4，含 patch F）2,906,138,328 B sha256 `f179f0a2…` + `package nsp verify` 19 checks / 18 ok / 1 warn；patch F 入库、补丁 README 更新为 A→F 六补丁、`examples/engines/kirikiroid2-nx.yaml` patches=6 且 artifact_sha256=A5。
- [ ] 【v1.2 待用户设备】P4 真机验证（更新版）：Atmosphère 1.12.1 + sigpatches 安装 **A5** NSP（`010047410000A000`，version 1.0.4）、首启解包、物理手柄 + 手柄存读档（patch D/E）、**K2S 抽屉电源键退出不崩溃（patch F）**、音频、性能；exFAT；补 portlibs pin（R12）。
- [x] 【v1.3 完成·模拟器级】**P5 汉化（CN7 + A6 双形态）**：公开仓库 `t-satoru-Studio/haruno_script` 重打包 XP3（无引擎改动）+ 自研 `xp3pack.py`；四坑修复（startup.soc 编码 / archive 子目录 autopath / TJS 无 `\uXXXX` / `Scripts.textEncoding`）；CN7 与 A6 均显示中文标题菜单与中文正文、`@0000A_Z01.ks` 命中、0 异常；证据 `P5a-cn7-*` / `P5b-a6-*`，文档 `docs/builds/012`。
- [x] 【v1.3 完成】A6 中文自包含 NSP：2,906,318,552 B sha256 `1941a317baea186bb6f8ac9cdd8e9d11d2125a25abfcc32f83a14339a70a49d7`，`package nsp verify` 19 checks / 18 ok / 1 warn；首启解包 23 文件 2737 MiB → autostart → 中文正文；engine descriptor 的 `artifact_sha256` 与 notes 已更新。
- [x] 【v1.4 完成·模拟器级】**中文 OP（A7）**：CN `movie_chs.xp3>opening.mpg`（134,811,648 B / 114.5 s，中文硬字幕）替换 `movie.xp3`，op1 场景实测 OP 播放 PASS；A7 中文 CN NSP 2,870,879,960 B sha256 `c23a519a…`，`package nsp verify` 19 checks，Citron 首启冒烟中文标题 + 中文正文 + 0 异常（版本 1.0.6）。
- [ ] 【v1.4 待用户设备】**A5/A7 真机复验**：装 A7（1.0.6：中文标题菜单 / 正文 / 中文 OP / 存读档 / 退出）与 A5（1.0.4：K2S 抽屉电源键退出不崩溃）；注意 A5/A7 同 TitleID 会互相覆盖、A7 取代 A6；exFAT + DBI 安装；结果记录进 `docs/pilot/saveload-acceptance.md` 与 `docs/pilot/P4-device-runbook.md`，并回填本计划 §14。
- [x] 【v1.5 完成·模拟器级】**P6 patch G（手柄映射 v2 + 三个真机 bug）**：A=Enter/B=原生返回/X=自动/Y=读档/+=存档/-=退出/ZR·ZL=左右键/右摇杆半速光标/左摇杆滚轮单步/D-Pad=方向键；修 ①K2S 表单叠热键冻结 ②K2S 抽屉电源键退出 SystemObj 崩溃 ③光标过快、另有 Minus 键不达引擎；Citron g1/g2/g3 端到端 PASS（`docs/builds/013-k2nx-controller-input-v2.md`，证据 `P6-*`）。
- [x] 【v1.5 完成】**A8 中文 CN NSP（version 1.0.7）**：2,870,873,816 B sha256 `ec74b0b4e39d14d9512a1656a3066397e21b1fdc9d79d6dfed4609d8fec5755b`，`package nsp verify` 19 checks / 18 ok / 1 warn；Citron 首启解包 + 中文标题/正文 + MINUS/抽屉电源键双退出路径干净退出（证据 `P6a-a8-*`）；engine descriptor patches=7、artifact_sha256=A8。
- [ ] 【v1.5 待用户设备】**A8 真机复验（取代 A5/A6/A7）**：装 A8（1.0.7）→ 中文标题/正文、+=存档、Y=读档、-=退出无 2-0000、K2S 抽屉电源键退出无 2-0000、B 返回、右摇杆光标半速、左摇杆滚轮、中文 OP、音频、二启 marker；注意同 TitleID 覆盖；结果回填 `docs/pilot/P4-device-runbook.md` §11 与本计划 §14。
- [x] 【v1.6 完成·模拟器级】P7 输入微调（patch H）：R 按住持续发 Ctrl（`_scancode[VK_CONTROL]`）→ Citron 实测跨脚本快进（@0000A_Z01→Z02）；左摇杆滚轮方向跟正（上推=BackLog、下拉=下一句，`v < 0 ? 120 : -120`）；封面图三候选选 B-right（icon 256x256 JPEG + README 512x512 PNG）。
- [x] 【v1.6 完成】A9 中文 CN NSP（version 1.0.8，含 patch H + 封面图标）2,870,911,192 B sha256 `ee0603b4…` + `package nsp verify` 19 checks / 18 ok / 1 warn + Citron 首启解包 23 文件 → 中文标题/正文 → R 快进 → BackLog → MINUS 确认 → 干净退出全通；patch H 入库、补丁 README 八补丁、engine descriptor patches=8、`docs/builds/014-*`、runbook §11 v1.5。
- [ ] 【v1.6 待用户设备】**A9 真机复验（取代 A5–A8）**：装 A9（1.0.8）→ 中文标题/正文、R 按住快进、左摇杆上推 BackLog / 下拉下一句、+=存档、Y=读档、-=退出无 2-0000、抽屉电源键退出无 2-0000、B 返回、右摇杆光标半速、X 自动、D-Pad、中文 OP、音频、HOME 图标为封面图、二启 marker；证据归档 `P7b-*`。
- [x] 【v1.8 完成·模拟器级】**P8 退出存档 + 按住鼠标（patch I）**：修用户 m13042 四问题——①设置不持久 ②SAVE/LOAD 无时间/文本、NEW 卡槽 1、设置锁槽 1 ③「继续游戏」提示强制终了 ④ZR 需按住可拖动；根因 = patch F/G 立即退出跳过 `MainWindow.finalize()`（全树唯一 `SystemSave`/`TraceSave` 调用点，`MainWindow.tjs:542`）；patch I 在关闭路径显式 `TraceSave`+`SystemSave` 后 1 s 延迟退出、ZR/ZL 改按住 `onMouseMove`+`onMouseDown/Up` 并重显淡出光标、`onAxisEvent` 的 `PrimaryLayerArea` 早退移到 `__SWITCH__` 块之后；Citron i6（临时诊断热键证明写盘 + 重启 LOAD 面板 NEW+缩略图+文本+时间）与 i8 双 run（退出 glog `[close] persisted system data (TraceSave + SystemSave)`、system/trace 哈希更新、ZR 光标/滚轮/back/按住拖动）PASS，0 异常；`docs/builds/015-*`。
- [x] 【v1.8 完成】**A10 中文 CN NSP（version 1.0.9）**：2,870,911,704 B sha256 `0efc23f6…`、PROVENANCE 14,100 B、`package nsp verify` 19 checks / 18 ok / 1 warn（未签名预期）；Citron 首启冒烟 A–D 全 PASS（A 强制首启解包 + 退出写 system/trace；B 二启 marker + LOAD 面板；C 反复退出持续写盘；D LOAD UI 的 Continue 行渲染持久化缩略图/文本/时间 2026/10/30 23:46:5），0 异常；patch I 入库、全量 diff 52,375 B `42436d3e…`（840/57）、补丁 README 九补丁 A→I、engine descriptor patches=9/artifact=A10、tests 断言 8→9。
- [x] 【v1.9 完成·真机】**A10 真机验收 PASS（首款垂直试点完成）**：装 A10（1.0.9）→ ①设置改变后退出重进是否保留 ②SAVE/LOAD 槽位时间+文本+NEW 徽章正确 ③「继续游戏」不再提示强制终了 ④ZR 按住+右摇杆拖动有效 ⑤其余沿用 A9 清单（中文标题/正文/OP、R 快进、BackLog、+=存档、Y=读档、-=退出无 2-0000、抽屉电源键退出无 2-0000、B 返回、右摇杆光标、X 自动、D-Pad、HOME 封面图标、二启 marker）；结果回填 `docs/pilot/P4-device-runbook.md` §11 与本计划 §14。；**用户 m13918（2026-10-31）真机复验确认四问题（设置持久 / SAVE·LOAD 时间文本与 NEW / 继续游戏强制终止警告 / ZR 按住拖动）全部解决、暂未发现明显问题 → 首款垂直试点按用户定义完成标准（模拟器上已打包 NSP、可直接启动、支持手柄操作，且已超额完成真机验证）达成，目标标记完成**。
- [x] 【v1.10 完成·模拟器级】M5-c：rfvp Switch 渲染后端改 SDL2/GLES2（性能 60.0 fps，原 17–19 fps）：`platform/switch/runtime/sdl_video.c` C shim + `host/src/render.rs` 转发 + `runtime/main.c` SDL 主循环 + `build_switch.sh` SDL2 链接（`-lnx` 顺序坑）；Citron 实测 60.0 fps / render 15.57 ms（vsync）/ vm 0.56 / scene 0.23，标题 + 中文正文可见、0 异常；NRO 7,823,416 B sha256 `e3acbce4…`；补丁 1,238 行 sha256 `515af726…`、记录 `docs/builds/016-rfvp-sdl2-backend.md`、证据 `P9a-rfvp-sdl2/`；框架新增 `custom-script` 构建后端 + `examples/engines/rfvp.yaml`。真机/音频/CJK/手柄/内存未验（研究项）。
- [x] 【v1.11 完成·模拟器级】M5-d：rfvp 手柄输入与快捷存读档 —— 基线映射实测 6 项成立（光标/A/B/X/Y/肩键/PLUS）；patch J 补 `QuickSave`/`QuickLoad` + pending 请求兜底到槽 0 + 右摇杆 Wheel（backlog）+ 光标加速，Citron P10-h 实测 `quick save/load: slot 0` 与 `rfvp_s000.bin` 490,104 B；产物 NRO 7,827,512 B sha256 `b95cd26b…`、补丁 `rfvp-input.patch` sha256 `aeb8f226…`、记录 `docs/builds/017`、证据 `docs/milestones/evidence/P10-rfvp-input/`。【v1.11 未验证】PLUS+ZR/ZL 组合键、真机、音频、movie、游戏自带多槽位 SAVE 面板。

---

- [x] 【v1.12 完成·模拟器级】M5-e：rfvp 自包含 NSP（romfs 打包）——`main.c` 运行期选择 `romfs:/game`（SD 无游戏时），新增 `scripts/build_nsp_game.sh`；NSP 9,979,435,224 B sha256 `4592385c…`、romfs 9,932,275,140 B / 161 条目；Citron 在 SD 无游戏数据时从 romfs 启动并显示中文正文、NRO 回归 PASS；`galnx package nsp verify` 12 checks（1 warn=未签名）；`docs/builds/018-rfvp-nsp.md`、`docs/milestones/evidence/P11-rfvp-nsp/`、`examples/pilot02-iroseka.yaml`；真机待装（9.98 GB 需 exFAT SD/NAND，018 §9 U1–U8）
- [x] 【v1.13 完成·模拟器级】M5-f：rfvp 手柄映射重写（`platform/switch/host/src/event.rs`）——A=Enter、B=Esc、方向键、R=Ctrl、ZR/ZL=鼠标左右键按压、右摇杆光标、左摇杆上下滚轮、X=AUTO、Y=读档、+=存档、-=退出（含游戏确认框）；Citron 逐项验证（p12-g/h/i/n/m），产物 = 补丁 `rfvp-input-remap.patch` + 全量 diff + NSP v1.0.1（9,979,435,736 B sha256 `0fda623c…`）；遗留 U1 A=Enter 真机复核、U2 ZR 左键手感、U3 R=Ctrl 跳读未在 Citron 复现。
- [x] 【v1.14 完成·模拟器级】M5-g：rfvp 真机四项缺陷修复 —— ① 主机层 SDL overlay 光标（`galnx_sdl_set_overlay`）+ 纹理 scratch 复用；② 性能恢复 60 fps（`render` 15.75 ms/帧）；③ 原生 EXIT 走引擎正常关闭（`no_std_core` 消费 `ExitDialog`/`ExitMode(3)` 并 `save_global_if_changed`）；④ MINUS 改为主机自绘 `QUIT GAME?` 确认框（A=YES 正常退出 / B=NO 取消）；产物 = 补丁 `rfvp-device-fixes.patch`（7 文件）+ 全量 diff 85,712 B + NRO `4f096dd6…` + NSP v1.0.2 `ff259aa4…`（9,979,437,784 B，verify ok=true 12 checks / 1 warn），Citron NRO/NSP 双形态 PASS，真机复验 V1–V14 待用户；U12–U17 记录于 runbook 与 020。
- [x] 【v1.15 完成·模拟器级】M5-h：rfvp 真机掉帧修复 —— prev-frame 改 GPU 双离屏 target（`sdl_video.c` + `supports_gpu_prev_frame`/`set_prev_frame_gpu`/`no_std_core` GPU 分支与 CPU fallback）、关闭 `debug_screen.bmp` 周期回读、顶点批处理与宿主计时；Citron 同探针 slow 154→19、帧>7 151→15、thumb≥20 ms 142→0、≥50 ms 136→5；产物 NRO `e5373bd7…`、ELF `e4040e7b…`、NSP v1.0.3 `b9e0d6a5…`（9,979,441,368 B，verify ok=true 12 checks / 1 warn），Citron NSP 形态冒烟 PASS；真机复验 V14/V15 待用户；U18–U21 记录于 021 §9 与 runbook。

## 15. 资料链接与状态说明

本草案以公开仓库主页、README 和构建文档为主要索引。项目的主分支、发布标签、依赖和兼容性可能变化；后续每次使用之前，均应重新确认。

重点入口汇总：

- [KRKR-ns](https://github.com/DrFlyingPig/krkr-ns)
- [RenpySwitch](https://github.com/jvrcruzGAMES/RenpySwitch)
- [Ren2Switch](https://github.com/Otorhin/Ren2Switch)
- [ONScripter-NX](https://github.com/clamintus/onscripter-nx)
- [rfvp](https://github.com/xmoezzz/rfvp)
- [Brewser](https://github.com/natureglass/Brewser)
- [nx.js_extended](https://github.com/natureglass/nx.js_extended)
- [BurialNX](https://github.com/ETCHDEV/BurialNX)
- [Autorun](https://github.com/autorunhq/autorun)
- [Autorun Horizon DLLs](https://github.com/autorunhq/autorun-horizon-dlls)
- [Carafe](https://github.com/carafe-nx/carafe)
- [NTON](https://github.com/rlaphoenix/nton)
- [hacBrewPack](https://github.com/rlaphoenix/hacBrewPack)
- [nstool](https://github.com/jakcron/nstool)
- [libnx](https://github.com/switchbrew/libnx)
- [devkitPro Getting Started](https://devkitpro.org/wiki/Getting_Started)
- [Atmosphère](https://github.com/Atmosphere-NX/Atmosphere)
- [Ryujinx Canary-1.3.265 标签镜像](https://gitlab.hugofnm.fr/publicmirrors/Ryujinx/-/tags/Canary-1.3.265)
- [ReXGlue SDK（旁支参考）](https://github.com/rexglue/rexglue-sdk)
- [XenonRecomp（旁支参考）](https://github.com/hedge-dev/XenonRecomp)

【v0.2 新增/修正】

- [Ren'Py 官方主源码](https://github.com/renpy/renpy)
- [Ren'Py 官方构建仓库](https://github.com/renpy/renpy-build)
- [nx-hbloader（修正：switchbrew）](https://github.com/switchbrew/nx-hbloader)
- [switch-tools（nxlink 上游）](https://github.com/switchbrew/switch-tools)
- [TooTallNate/nx.js（上游 nx.js）](https://github.com/TooTallNate/nx.js)
- [Citron Neo 模拟器（v0.4 新增，M4 测试后端）](https://github.com/citron-neo/emulator)

> 【v0.2 标注】Ryujinx Canary-1.3.265 标签镜像需登录且官方源当前不可达，本机留档与 SHA-256 为验证基线；GitHub 侧镜像存在 DMCA 屏蔽，**不要**再把 Ryujinx 源码作为可公开再分发的依赖。

**本草案不是对所有上述工具的兼容性背书。** 它的目的在于为后续调查建立共同清单，逐项将“看起来可能可行”转换为“能复现、有日志、有范围声明的实际结果”。

---

## 16. 修订记录

| 版本 | 日期 | 修订摘要 |
|---|---|---|
| v0.1 | 2026-10-29 | 初稿（讨论草案）。 |
| v0.2 | 2026-10-29 | 首轮工具链审计（26 个上游对象 / 27 条记录，`docs/TOOLCHAIN_AUDIT.md` v1.1）与 M0 实测后修订：①【§7.1】nx-hbloader 改 `switchbrew/nx-hbloader`，新增 devkitPro 实际安装状态（14 包、403/代理修复、无空格路径约束、m0-hello）；②【§7.2】KRKR-ns 定为第一款原型、RenpySwitch 无许可证不接入（改官方源码方向）、Ren2Switch 不接入、ONScripter-NX 第二候选（GPL 决策）、rfvp 研究项；③【§7.3】Brewser/nx.js_extended/BurialNX 许可证与可复现性结论、Web 先做最小冒烟；④【§7.5】nxlink 归属修正为 switchbrew/switch-tools，NSP 首个目标拍板“自包含包”；⑤【§7.6】Ryujinx 溯源实测（镜像需登录、官方 TLS 不可达、DMCA 451）→ 本机留档 + `not-verified`；⑥【§10】M0 完成项/新增项；⑦【§12】六项决策落定 + 新增 GitLab 绕行与 Ren'Py 官方源码方向，风险表补 4 行；⑧【§14】执行清单状态更新；⑨【§15】链接修正与新增。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.1_20261029.md`。 |
| v0.3 | 2026-10-29 | Ren'Py 补充审计与 Web 冒烟实验回填：①【§7.2】Ren'Py 官方源码专项审计交付（7 条记录、`8.5.3.26051504 = 39895c1e`、CPython 硬阻塞、4–6 周探针）；②【§7.3】Brewser Web 冒烟实测（本机 Ryujinx 1.3.265 无法加载 nx.js 系 NRO，普通 homebrew 对照正常，`not-verified`，M4 改走真机/换模拟器）；③【§12】风险表补 1 行、Web 决策项更新；④【§14】两项新增任务完成；⑤同步 `docs/TOOLCHAIN_AUDIT.md` v1.2（新增 §4.C.7、更新 R-18）与 `docs/experiments/web-01-brewser-smoke.md`。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.2_20261029.md`。 |
| v0.4 | 2026-10-29 | 全面联网复核与生态修补：①【§7.1】工具链刷新复核（本机 17 个 switch 相关包 17/17 与仓库最新一致、0 可升级；CMake 空格路径实测通过 `m0-cmake.nro` 161,989 B；锁定=pacman -Q 快照 + 包缓存 + 产物哈希三位一体；Docker `devkitpro/devkita64:latest` 不作基线；Atmosphère 1.12.1 声明支持 FW 23.0.0）；②【§7.2】Ren'Py 基线更正（`renpy/renpy` 无现代 release tag；版本由 `renpy/renpy-build` tag `renpy-8.5.3.26051504`=`7bfab40c` 定义，对应 renpy 源码 commit `39895c1e`）；③【§7.3】Brewser 版本表述统一为 v0.1.131（release tag `v0.1.1.31`）+ Web 路线模拟器侧**恢复**（Citron Neo nightly `0237a9b88` 完整运行 Brewser 2/2，探针页 DOM/CSS/JS/Canvas2D/WebGL/localStorage 全通过，M4 冒烟三件套）；④【§7.5】打包链零变化 + keys 合规策略（`GALNX_PROD_KEYS` 只读、只记元数据、不入库/不入日志/不进 CI；Lockpick_RCM 已被 DMCA 不提供下载源；NSP 非确定性）；⑤【§7.6】新增 Citron Neo 测试后端行与模拟器生态现状（suyu 451、Eden/Sudachi/Ryubing 404、Ryujinx 官方源不可达 → 仅 Citron 可公开访问；本机留档 + 资产 SHA-256）；⑥【§10】M0 两项改完成、4 份 refresh 报告记入已验收；⑦【§12】新增 4 条风险 + 3 项决策（测试后端优先级 Citron→Ryujinx→真机、keys 策略、构建后端改 CMake）；⑧【§14】4 项 refresh 标 [x] + 2 项新待办（m0-hello.nro 冒烟、装 switch-sdl2/freetype）；⑨【§15】新增 Citron Neo 链接；⑩【§7.2】krkrsdl2 上游官方 Switch 目标重大更正（CMake `NINTENDO_SWITCH` 分支 + CI matrix switch + release NRO 12.0 MB）→ KiriKiri 改为「krkrsdl2 上游先行可复现 / krkr-ns 启动器产品化」双层路线，新增 ONScripter-jh-Switch、Kirikiroid2-NX、siglus_rs 三个候选并修订接入排序；决策 2 补 v0.4 细化。本版同步产出 `docs/audit/05-toolchain-refresh.md`、`06-engines-refresh.md`、`07-web-citron.md`、`08-packaging-refresh.md` 与 `docs/experiments/web-02-citron-smoke.md`。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.3_20261029.md`。 |
| v0.5 | 2026-10-30 | M1/M2/M3 实现进展回填：①【§5.4 新增】输入层实现进展（`src/galnx/input/` 4 profile / 7 语义动作 / 7 冲突规则、`galnx input list|validate`、87 项 pytest；Citron 注入通道实测=mouse_event 有效、SendInput 键盘无效→PostMessage(WM_KEYDOWN/UP)、first_frame+焦点前提；KAG3 标题→正文 diff≈0.554）；②【§7.5】keys 通道修正（DSH 剔除 `KEY` 类环境变量→改显式 `--keyset`；`C:/Users/<user>/.switch/prod.keys` 不存在，实际路径=Ryujinx-canary 与 citron/keys；hacBrewPack 即使 `--plaintext` 也强制 keyset）+ 自包含 NSP 出包链打通（PFS0 三 NCA、CNMT 哈希一致、非确定性）；③【§7.6】Citron 自动化 harness 与单实例时间窗规程 + NSP 直接引导实测（`m0-hello` 渲染 `Hello World!`）；④【§10】M2 标完成（模拟器级）、M3 标部分完成（真机 M3-d 待用户设备）；⑤【§12】新增 4 条风险（keyset 强依赖/未签名 NSP/单实例竞态/DSH 变量脱敏）+ 决策 7；⑥【§14】执行清单状态同步（5 项打勾、3 项保留待办）。本版同步产出 `docs/milestones/M1-kirikiri.md`、`M2-kag3-input.md`、`M3-nsp.md`、`docs/builds/004-krkrsdl2-switch-fixes.md`、`005-nsp-selfcontained.md`、`docs/packaging/README.md`、`docs/input/README.md`、`docs/environment/citron-harness(-input).md` 等。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.4_20261030.md`。 |
| v0.6 | 2026-10-30 | M4 第二种引擎（Web 优先）收尾：①【§7.2】ONScripter-NX 实测（HEAD `a8439a86` 零源码修改、devkitPro clean build 20 s、Citron R1–R5 通过；负结果 R4a=RETURN 不确认选项需方向键；结论 P2 有条件，含 GPL-2.0-or-later 法务与真机未验证）；②【§7.3】Brewser Web 适配器端到端（内容包布局 `apps/<appId>/` + `configs/config.json` 的 `autorunApp`、9 次输入 title→endingA/B、页内 localStorage OK 但落盘未验证、DOM 按钮坐标偏移→整屏半区判定）；③【§10】M4 标完成（模拟器级）；④【§12】新增 3 条风险（localStorage 落盘 / GPL 法务 / run_spec 仅 Citron+真机未验证）；⑤【§14】M4 清单打勾。本版同步产出 `docs/milestones/M4-second-engine.md`、`docs/builds/006-brewser-web-adapter.md`、`007-onscripter-nx.md`、`docs/engines/README.md`、`schemas/engine.schema.json`、`examples/engines/`、`examples/web-vn/`。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.5_20261030.md`。 || v0.7 | 2026-10-30 | M5 FVP/rfvp 评估 + M6-a 批量预检 MVP 收尾：①【§7.2】rfvp 实测（pin nightly-2026-02-01 + devkitA64 r30 → rfvp.nro 1,372,216 B sha256 4964dda9…；Windows build.rs .exe 补丁；Citron 渲染 Luax Painter 17.5 fps + M=Plus→quit 输入链路；host no_std_harness 2/3；结论=继续研究 P3）；②【§10】M5 完成（研究级）、M6 部分完成（M6-a）；③【§12】新增 3 条风险（rfvp 性能 / Windows 补丁维护 / batch 只预检）；④【§14】执行清单新增 M5、M6-a、M4-f/M4-g 完成项；⑤ 产出：docs/builds/008-rfvp-evaluation.md、docs/milestones/M5-fvp.md、docs/milestones/M6-batch.md、docs/batch/README.md、docs/environment/rust-toolchain-2026-10-30.md。上一版备份：Workspace/GalNX_移植框架计划草案_v0.6_20261030.md。 |
| v0.8 | 2026-10-30 | M6 批量构建/缓存/依赖锁定收尾（CLI 级）：①【§10 M6】补 M6-b 实测与 M6 完成（CLI 级）状态段（`src/galnx/build/`、`galnx batch build|lock`、`galnx build run`；sha256 缓存 miss→hit、`--rebuild`/`--no-cache`/`--locked`；401 passed/63 subtests；Lead 独立复核）；②【§12】新增 3 条风险（缓存/锁定验证边界、真实引擎 build.commands 未接入、GUI 后置）；③【§14】M6 完成项打勾、构建执行/日志两项打勾；④ 产出：`docs/batch/README.md`、`docs/milestones/M6-batch.md` §5A、`docs/milestones/evidence/M6b-*`、`schemas/batch-report.schema.json` 扩展。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.7_20261030.md`。 |
| v0.9 | 2026-10-30 | 首款垂直试点 P0–P2 收尾（模拟器级达标）：①【§10 新增 P 系列】Kirikiroid2-NX 路径 A 落地 = 三补丁（autostart / romfs 首启解包 v2 / 插件 .tpm 别名）+ 自建 7 个 portlibs + `scripts/build_pilot_nsp.sh`；A2 自包含 NSP 2,906,125,016 B sha256 `eb6c6a15…`；全新 SD 首启解包 23 文件 14.4 s → autostart → 手柄 RIGHT+C 进正文（60 FPS / 0 exception）→ 二启 marker 命中；②【§12】新增 4 条风险（K2NX 许可 / 物理手柄与真机未验 / Citron 单实例静默转发 / 大 romfs 与 FAT32）与决策 12–14（试点引擎与路径 A、per-game KeyMap、Citron 申请-释放制）；③【§14】P0–P2 三项打勾 + P3/P4 两项待办；④ 产出：`docs/pilot/README.md`（v0.2）、`docs/pilot/P2-acceptance.md`、`docs/builds/patches/k2nx-switch/`（7 文件 + README）、`scripts/build_pilot_nsp.sh`、`docs/milestones/evidence/P2*`（证据 60+ 文件）。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.8_20261030.md`。 |
| v1.0 | 2026-10-30 | P3 打包工程化收尾（首款垂直试点模拟器级全链路可复现）：①【§10 P 系列】**P3 标完成**：三条 CLI 链（`engines prepare` / `payload plan|materialize` / `package nsp plan|build|verify`）+ 端到端 oracle 命中（romfs 109 文件 / 2,878,186,922 B / 摘要 `53535c68…d164e`；`game_files.txt` 600 B `0e6757d9…`；KeyMap `aa4fa8aa…`）；②A3 合规 TitleID 自包含 NSP 2,906,131,672 B sha256 `1f54bdf1…e994d4`（exefs/main 与 A2 逐字节一致）；独立 verify（19 checks / 0 fail）+ 两条 Citron 全新 SD 冒烟 PASS；③harness `--detach` 修 R14（WMI 脱离进程树 + launch_route + 陈旧日志检测）；④【§12】新增 4 条风险（NSP 形态鼠标无效 / TitleID 合规 A2 反例 / harness 判据与 wipe 陷阱 / overlay 与 portlibs 未 pin）与决策 15–18（TitleID 合规强制、Citron 一律 --detach、k2nx 保持 overlay、NSP 用组件哈希比对）；⑤【§14】P3 两项打勾 + A3/verify/独立冒烟打勾 + P4 更新；⑥ 产出：`docs/pilot/P3-pipeline.md`、`P3-verification.md`、`P3-smoke-independent.md`、`docs/packaging/{payload,nsp-build}.md`、`docs/builds/009-k2nx-selfcontained-build.md`、`src/galnx/{payload,package/nsp,engines/source}`、证据 `P2e/P3a/P3c/P3d/P3e/P3f-*`。上一版备份：`Workspace/GalNX_移植框架计划草案_v0.9_20261030.md`。 |
| v1.1 | 2026-10-30 | P3.5 手柄存档/读档收尾（首款垂直试点模拟器级功能完整）：①【§10 P 系列】**新增 P3.5 状态段并标完成**：patch D（虚拟鼠标光标：PLUS 开关、D-Pad 24 px 步进、A/B 左右键）+ patch E（`GalNX_QuickSaveLoad()` 用 `TVPExecuteExpression` 调本作 BASE ADV SYSTEM 的 `MainObj.SaveAction` / `DataLoadAction` / `_SAVELOADOBJECT` 原生 SAVE/LOAD 界面 / `SystemSave`；并给 `TVPInGameMenuForm` 加键盘导航、`PreferenceForm` 加选中高亮）；NRO + A4 NSP 双形态全手柄完成「存档→落盘→重启→读档→续玩」闭环；②**A4 自包含 NSP**（version 1.0.3）2,906,135,768 B sha256 `2003ec1e…`、verify 19 checks，ELF `7461bbe0…` / NRO `a84f6be0…`；③【§12】新增 4 条风险（热键绑定本作 TJS API / 合成触摸会崩 / patch 顺序与 CRLF 归一 / GalNXLog 写 SD）与决策 19–20（手柄优先虚拟光标+原生 UI 热键、补丁按栈可 roundtrip）；④【§14】新增 U20 与 A4 两项完成、P4 待办改为 A4 + 手柄存读档；⑤ 产出：`docs/builds/010-k2nx-controller-saveload.md`、`docs/pilot/saveload-acceptance.md`、`docs/pilot/P4-device-runbook.md`、`docs/builds/patches/k2nx-switch/{D,E}`、`docs/milestones/evidence/P3g-*`（21 文件）、`examples/pilot01-haruno.yaml`（1.0.3）、`examples/engines/kirikiroid2-nx.yaml` 更新。上一版备份：`Workspace/GalNX_移植框架计划草案_v1.0_20261030.md`（106,842 B sha256 `e08afd60…`）。 |
| v1.2 | 2026-10-30 | P4 真机退出崩溃修复 + A5 出包：①真机症状 `Error Code: 2-0000` / `Member "SystemObj" does not exist @line(365) checkdialog.tjs` 定位为确认框 finalize 依赖全局 `MainWnd.SystemObj` 而主窗口关闭走 invalidate teardown；②**patch F**（2 文件）主窗口确认关闭直接 `TVPExitApplication(0)` + Window 补 `minimized`/`maximized`/`minimize()`/`maximize()`/`restore()`，修 ESC 路径的 `Member "minimized"`；③Citron exit3 验收 PASS（确认框→はい→`[close] main window close confirmed; terminating application`→干净退出、k2s 0 error），证据 `P4a-exit-*`；④**A5 自包含 NSP**（version 1.0.4）2,906,138,328 B sha256 `f179f0a2…`、verify 19 checks / 18 ok / 1 warn；⑤补丁栈 A→F 全量 diff 37,398 B `8ee1f77a…`（9 文件 677+/20−），engine descriptor patches=6、artifact=A5，tests 断言 6 个；⑥【§12】新增 4 条风险与决策 21；⑦【§14】U21/A5 打勾、P4 改为 A5 + 退出复验；⑧ 产出 `docs/builds/011-k2nx-exit-crash-fix.md`、`P4a-exit-*` 证据、`docs/pilot/saveload-acceptance.md` §8、`docs/builds/patches/k2nx-switch/README.md` 更新。上一版备份：`Workspace/GalNX_移植框架计划草案_v1.1_20261030.md`（115,640 B sha256 `950794ca…`）。 |
| v1.3 | 2026-10-30 | P5 汉化收尾（模拟器级全通）：①【§10 P 系列】**新增 P5 段并标完成**——汉化路线定为公开仓库 `t-satoru-Studio/haruno_script` 重打包 XP3（零引擎改动、取消 patch G），自研 `xp3pack.py` 按 `XP3Archive.cpp` 格式写包并 roundtrip；四坑修复（startup.soc 必须 UTF-8 / CN Init.tjs 删 xp3 注册需 startup 补 archive 子目录 autopath / TJS 无 `\uXXXX` 须真实 UTF-8 / `Scripts.textEncoding`+BOM 而非 setArgument）；②A6 中文 CN NSP 2,906,318,552 B sha256 `1941a317…`，`package nsp verify` 19 checks / 18 ok / 1 warn，Citron 首启解包 23 文件后中文标题与中文正文、`@0000A_Z01.ks` 命中、0 异常；③新增 `docs/builds/012-k2nx-cn-content.md` 与 `docs/pilot/P5-localization-feasibility.md` v0.3，engine descriptor 更新 artifact_sha256/notes；④【§12】新增 3 条风险（CN 许可边界、TJS 无 `\uXXXX`、CN 包覆盖面）；⑤【§12】决策 22；⑥补丁栈不变（A→F 六补丁）；pytest 600 passed / 63 subtests。 |
| v1.4 | 2026-10-30 | P5 中文 OP + A7 出包（中文试点模拟器级全通）：①【§10 P 系列】**新增【v1.4】中文 OP（A7）段**——来源 PC 中文版 `movie_chs.xp3` 内 `opening.mpg` 134,811,648 B sha256 `276f671c…` / 114.48 s（中文硬字幕）；JP 版 162,623,492 B sha256 `e8862570…` / 111.99 s，两者同编码（mpeg1video 1280x720 60 fps + mp2），确认可同名替换、无需转码。②**做法**：新 `movie.xp3`（JP 警告 txt + JP `logo.mpg` + CN `opening.mpg`）129,030,977 B sha256 `483bc72d…`；`romfs-cn2` 为 romfs-cn 硬链接副本（109 文件，仅换 `game/movie.xp3`）；`game_files.txt` version=pilot01-cn2 / bytes=2835467131；manifest `examples/pilot01-haruno-cn2.yaml`（1.0.6）；`pilot-01/p5/a7-build.sh` 出包；引擎零改动（OP 触发点 `[macPlayMovie file=opening]` 同名命中）。③**验收**：op1 场景测试包（在 `@0000A_Z01.ks` 插 `[macPlayMovie]`）实测 k2s `Input #0, mpeg, from 'opening.mpg': Duration: 00:01:54.50 ... 1280x720`，截图含中文硬字幕；**A7 中文 CN NSP** 2,870,879,960 B sha256 `c23a519aeb602104aa7bd6f63d8f33c2d79de93af7d3d292e1811a0e4a37a5e6`（PROVENANCE 14,046 B sha256 `8dbcc568…`，1.0.6 / version_code 65542），`package nsp verify` **19 checks（18 ok + 1 warn 未签名）**，Citron 首启解包 23 文件 2,704 MiB → title.ks → start.ks → @0000A_Z01.ks、0 异常、窗口 `Haruno CN (64-bit) | 1.0.6`。④【§12】**新增 2 条风险**（中文 OP 编解码差异仅 Citron 单次验证、A6 保留回退；A5/A6/A7 同 TitleID 互相覆盖需记录版本号）。⑤【决策】**新增 23**：增强走归档内同名文件替换，不引入视频重编码链路。⑥【§14】**新增 A7 完成项（模拟器级）**，待用户设备项改为「A5/A7 真机复验」。⑦文档与证据：`docs/builds/012` §8（A7 产物/校验/冒烟/证据）、`docs/pilot/P5-localization-feasibility.md` v0.4、`docs/milestones/evidence/P5c-op-*` 与 `P5d-a7-*`、engine descriptor `artifact_sha256` → A7；`tests/test_engines_source.py` 24 passed。上一版备份 v1.3 = 131,379 B sha256 `2559d063…`。 |
| v1.5 | 2026-10-30 | P6 手柄映射 v2 + 三个真机 bug 修复 + A8 出包（模拟器级全通）：①【§10 P 系列】**新增【v1.5】P6 段**——用户 m11780 真机反馈三问题（PLUS 菜单开时按 R 冻结 / K2S 抽屉电源键退出 SystemObj 崩溃 / 光标过快）与新映射需求；patch G 在引擎 pad 层重写映射（A=Enter、B=游戏原生返回 RightMouseUpAction、X=自动、Y/+=游戏原生读/存档面板（先 pop K2S 表单）、-=退出确认、ZR/ZL=左右键、右摇杆步长 12→6、左摇杆滚轮迟滞单步、D-Pad 方向键），并修 OnCloseQuery() 放行时机 + OnClose() 主窗口直接退出（堵 ProgramClosing teardown）、补 vendor Minus→BUTTON_SELECT。②**验收**：Citron g1（映射全项 + 抽屉打开时 Y 热键正常）/g2（MINUS→确认→[close]→干净退出）/g3（抽屉电源键→确认→干净退出，bug 2 原复现路径）三组 PASS、0 异常。③**产物**：patch G 22,152 B sha256 7cf01df0…（2 文件 +199/−137）、keymap v2 1,600 B sha256 bd9cfc34…、全量 diff 48,545 B sha256 f79ad811…（9 文件 +778/−56）、ELF db84100d… / NRO 012bc811…；**A8 中文 CN NSP** 2,870,873,816 B sha256 ec74b0b4…（PROVENANCE f61085e9…，1.0.7 / version_code 65543），verify 19 checks，Citron 首启解包 23 文件 2,704 MiB → 中文标题/正文 → MINUS 退出干净。④【§12】**新增 3 条风险**（B≠ESC 的刻意偏差、patch G 依赖 vendor 文件、A5–A8 同 TitleID 覆盖）。⑤【决策】**新增 24**：映射在引擎 pad 层做且不追 ESC 语义。⑥【§14】**新增 3 条**（P6 完成、A8 完成、A8 真机复验待用户）。⑦文档与证据：docs/builds/013-k2nx-controller-input-v2.md、补丁 README（七处补丁、A→G 顺序）、docs/pilot/P4-device-runbook.md v1.4 §11、docs/milestones/evidence/P6-* 与 P6a-a8-*；tests/test_engines_source.py patches 6→7（24 passed）。上一版备份 v1.4 = 138,634 B sha256 9d6337de…。 |
| v1.6 | 2026-10-30 | P7 输入微调 + 封面 + A9 出包（模拟器级全通）：①【§10 P 系列】**新增【v1.6】P7 段**——用户 m12633 三诉求（R=Ctrl 按住、左摇杆滚轮方向相反、做封面）；②实现 = patch H（`_scancode[VK_CONTROL]=0x11` 让游戏 `SkipCheck()` 的 `getKeyState` 轮询生效；`v < 0 ? 120 : -120` 跟正滚轮方向），Citron h1 验收（ctrl down/up、wheel ±120、BackLog 面板、跨章快进、0 exception）；③封面三候选选 B-right → `examples/pilot01/icon-cover.jpg`（32,607 B sha256 `fb896d18…`）+ `docs/assets/pilot01-cover.png`（470,665 B sha256 `561561b1…`），A9 manifest 双 icon 字段；④**A9 中文 CN NSP（1.0.8）**2,870,911,192 B sha256 `ee0603b4…`、PROVENANCE 14,064 B `537c2ae7…`、verify 19 checks、Citron 首启解包 23 文件 → 中文标题/正文 → R 快进 → BackLog → MINUS 退出全通；⑤patch H 2,390 B `b28b77bd…` 入库、全量 diff 49,817 B `5e2726ac…`（797/56）、engine descriptor patches=8、tests 断言 8、runbook §11 更新到 A9、README 加封面图；⑥新增风险 3 条（R 与 skip 叠加、封面著作权、A9 覆盖 A8）与决策 25；⑦pytest 600 passed / 63 subtests；上一版备份 v1.5 见下条。 |
| v1.7 | 2026-10-30 | 封面归属澄清（文档层，无产物变更）：①【文档状态】新增 v1.7 行、日期改 v1.7、版本约定追加 v1.7 备份说明（上一版 v1.6 = 157,561 B sha256 `f5508b7e…`）；②【§10 P 系列 P7 段】新增【v1.7】封面归属 bullet——封面只属于本作、GalNX 无统一项目封面、后续每款游戏各自制图；③仓库文档同步：README 顶部游戏封面移入「### 垂直试点」小节并加范围 blockquote、`## 约定` 增第 7 条「封面按游戏各自制作」（`examples/<game>/icon-cover.jpg` + `docs/assets/<game>-cover.png`），`docs/builds/014` §4 加范围说明并修掉重复的 §8 空标题；④本轮无源码/产物变更（A9 仍为 2,870,911,192 B sha256 `ee0603b4…`，A8 真机初测通过，A9 已 DBI 上传待真机复验）。 |
| v1.8 | 2026-10-30 | P8 退出存档 + 按住鼠标（patch I）+ A10 出包（模拟器级全通）：①【§10/§14】**新增【v1.8】P8 段**——用户 m13042 真机四问题（设置不持久 / SAVE·LOAD 无时间文本、NEW 卡槽 1、设置锁槽 1 / 继续游戏提示强制终了 / ZR 只能点不能拖）；根因 = patch F/G 立即 `TVPExitApplication(0)` 跳过 `MainWindow.finalize()`（全树唯一 `SystemSave`/`TraceSave` 调用点 `MainWindow.tjs:542`），system.bmp 从不更新、trace 停在旧状态；②**patch I**（MainScene.cpp +56/−14，7,372 B sha256 `3cbcad8d…`）三组改动 = 关闭路径显式 `TraceSave`+`SystemSave` 后 1 s 延迟退出（glog `[close] persisted system data (TraceSave + SystemSave)`）、ZR/ZL 按住 `onMouseMove`+`onMouseDown/Up` 且 `stopAllActions+setOpacity(255)+_refadeMouseCursor` 重显光标、`onAxisEvent` 的 `PrimaryLayerArea` 早退移到 `__SWITCH__` 块后；③**Citron 验收**：i6 临时诊断热键证明 SystemSave 写盘（savedata010 新建、system.bmp 965→984 B）与重启 LOAD 面板（NEW + 缩略图 + 「我拼命地伸出了手。」+ 2026/10/30 23:26）；i8 双 run（A 退出 glog `[close] persisted` + system.bmp 988 B sha `b803401b…`；B ZR 光标/滚轮 120/back/按住拖动，0 异常）；④**A10 中文 CN NSP（1.0.9）**2,870,911,704 B sha256 `0efc23f6…`、PROVENANCE 14,100 B、verify 19 checks / 18 ok / 1 warn（未签名预期）、Citron 首启冒烟 A–D 全 PASS（D 的 Continue 行渲染持久化缩略图/文本/时间 23:46:5）；⑤patch I 入库、全量 diff 52,375 B `42436d3e…`（840/57）、补丁 README 九补丁 A→I、engine descriptor patches=9/artifact=A10、runbook §11 更新到 A10、`docs/builds/015-*`、证据 `P8-i-*` 与 `P8a-a10-*`；pytest 600 passed / 63 subtests；⑥pytest 600 passed / 63 subtests；上一版备份 v1.7 = 159,457 B sha256 `fc68a1cd…`。 |
| v1.9 | 2026-10-31 | A10 真机验收通过 + 首款垂直试点完成（无源码/产物变更，仅文档与计划）：①【文档状态】新增 v1.9 行、日期改 v1.9、版本约定追加 v1.9 备份说明（上一版 v1.8 = 165,697 B sha256 `f7d4d4e3…`）；②【§14】**A10 真机复验项由待办改为完成** —— 用户 m13918（2026-10-31）确认 ①设置改变后退出重进保留 ②SAVE/LOAD 槽位时间+文本+NEW 正确 ③「继续游戏」不再提示强制终了 ④ZR 按住+右摇杆拖动有效 ⑤其余 A9 清单项无明显问题；③【§12】决策新增 27：A10 为试点交付基线、目标完成、遗留项不阻塞；④仓库同步：`README.md` 状态行改为「首款垂直试点已完成（A10 真机验收通过）」、P 系列勾选 P8/A10/P7 真机复验、下一步更新；`docs/pilot/P4-device-runbook.md` 新增 §12.4 真机验收结果；⑤A10 仍为 2,870,911,704 B sha256 `0efc23f6…`（2026-10-31 DBI 上传 449.7 s 自动安装）。 |
| v1.10 | 2026-10-31 | M5-c：rfvp Switch 渲染后端改 SDL2/GLES2（性能 17–19 fps → 60.0 fps，模拟器级）：①【§10 M5】**新增【v1.10】M5-c 状态段**——`platform/switch/runtime/sdl_video.c`（新，17,054 B）C shim + `host/src/render.rs` 全部转发 + `runtime/main.c` SDL 主循环 + `build_switch.sh` SDL2 编译/链接（`-lnx` 必须排在 `-lSDL2`/`-ldrm_nouveau` 之后）；Citron 0237a9b88 实测 `frame 8280: 60.0 fps over the last 60 frames, slowest frame 17.2 ms`、`perf avg: vm 0.56 / scene 0.23 / render 15.57 / total 16.37 ms`、标题与中文正文正确、0 异常；NRO 7,823,416 B sha256 `e3acbce4…`；两个真因 = C shim `create_texture` 必须 upsert（`prim_commands.rs:224` 同 `graph_id` 反复 create；文字 `graph_id=4064+slot`，非 upsert 时 144 条 `rc=-3`）+ 早期截图早于文字首现 t≈63.5 s；②【§7.2】rfvp 行追加【v1.10 实测·M5-c】、接入排序补「性能门槛已解、仍研究项」；③【§12】rfvp 性能风险标为已解决，新增 4 条风险（Citron 级验证 / 音频手柄中文未接 / 后端函数面与 upsert 隐式契约 / 许可组合）；④【§14】新增 M5-c 完成项；⑤【决策】新增 28（SDL2/GLES2 取代 CPU 软光栅，libnx 只留输入音频）；⑥框架新增 `build_backend: custom-script`（schema/descriptor/contract + 单测）与 `examples/engines/rfvp.yaml`；补丁 `docs/builds/patches/rfvp-switch/rfvp-sdl2-backend.patch`（1,238 行 / 6 文件 / sha256 `515af726…`）、构建记录 `docs/builds/016-rfvp-sdl2-backend.md`、证据 `docs/milestones/evidence/P9a-rfvp-sdl2/`（5 文件含 SHA256SUMS）；pytest 602 passed / 63 subtests。上一版备份 v1.9 = 168,422 B sha256 `18362ae1…`。 |
| v1.11 | 2026-10-31 | M5-d：rfvp 手柄输入与快捷存读档（模拟器级）：①【§10 M5】**新增【v1.11】M5-d 状态段**——上游 event.rs 基线映射实测 6 项成立；两个结构性缺口（游戏内 system 菜单只认指针；`legacy::save_file/load_file` 的 pending 请求只由桌面专属 `legacy_save_load_ui` 消费，Switch 点中 SAVE/LOAD 会挂起 VM）；②patch J（`rfvp-input.patch` 9,886 B / 4 文件 / sha256 `aeb8f226…`）= `RfvpEvent::QuickSave/QuickLoad` + `no_std_core` 事件处理与 `take_pending_save_load_request()` 兜底槽 0 + `main.c` 右摇杆 + `event.rs` 重写（PLUS 修饰键、右摇杆 Wheel、光标除数 6000）；最终 NRO 7,827,512 B sha256 `b95cd26b…`；③实测 P10-h：`quick save: wrote slot 0` / `quick load: read slot 0`、`rfvp_s000.bin` 490,104 B、右摇杆上推弹 BACKLOG、PLUS 干净退出；④【§12】新增 3 条风险（无槽位 UI 部分解决 / 组合键与真机未验证 / 菜单指针精度）；⑤【§14】新增 M5-d 完成项；⑥【§7.2 接入排序】补【v1.11】说明（可玩门槛收窄为槽位 UI、音频、真机，排序不变）；⑦文档 `docs/builds/017-rfvp-input.md`、补丁 README、`examples/engines/rfvp.yaml`（input/save supported、artifact sha）、`docs/milestones/M5-fvp.md` M5-d 段、证据 `docs/milestones/evidence/P10-rfvp-input/`（12 截图 + ODS 日志 + 存档清单 + SHA256SUMS）。 |
| v1.12 | 2026-10-31 | M5-e：rfvp 自包含 NSP（romfs 打包，模拟器级）：①【§10 M5】**新增【v1.12】M5-e 状态段**——`runtime/main.c` 运行期游戏根选择（romfs 挂载且 `romfs:/game` 有 `.hcb`、SD 无游戏 → romfs，否则回落 SD）；新增通用 `scripts/build_nsp_game.sh`（elf2nso/npdmtool/nacptool/romfs 硬链接/hacBrewPack/nstool）；NSP 9,979,435,224 B sha256 `4592385c…`、romfs 9,932,275,140 B / 161 条目、TitleID `010047420000A000`；②Citron P11-nsp2：SD 游戏目录改名后仍从 `romfs:/game` 启动、中文正文「从天而降的羽毛。」、PLUS 干净退出（0 exceptions），NRO 回归 PASS；③【§12】新增 2 条风险（NSP 体积/文件系统、romfs 首读与内存）；④【§14】新增 M5-e 完成项；⑤【§7.2 接入排序】补【v1.12】说明（打包门槛关闭，排序不变）；⑥文档 `docs/builds/018-rfvp-nsp.md`、补丁 `rfvp-romfs.patch`（2,430 B sha `710a373e…`）/全量 `rfvp-full.diff`（57,536 B sha `a6da0202…`）、`examples/engines/rfvp.yaml`（target self_contained_nsp、romfs、artifact sha）、`docs/milestones/M5-fvp.md` M5-e、证据 `docs/milestones/evidence/P11-rfvp-nsp/`、清单 `examples/pilot02-iroseka.yaml`。 |
| v1.13 | 2026-10-31 | M5-f：rfvp 手柄映射重写（Citron 级逐项验证）：①【§10 M5】**新增【v1.13】M5-f 状态段**——`platform/switch/host/src/event.rs` 整体重写（404 行；diff 413 行 / +264 −56）：A→Return、B→Escape、方向键→方向键、R→Control（按住）、ZR/ZL→鼠标左/右键按压、右摇杆→PointerMove（POINTER_DIVISOR=3000）、左摇杆纵向→Wheel(±120，6 poll 重复)、X→工具栏 AUTO 宏、Y/PLUS→暂停菜单 LOAD/SAVE 宏、MINUS→EXIT+退出确认二次点击；②**宏机制**：`MenuMacro` 阶段机（Esc down/up → 90 poll 淡入等待 → 指针移动 → 左键 down/up，可带第二次 click2），锚点实测 SAVE=(1117,171)/LOAD=(960,217)/EXIT=(654,608)/AUTO=(1079,700)/确认=(560,379)；③【§12】**新增 2 条风险**（宏点击依赖屏幕坐标、R=Ctrl 跳读未在模拟器复现）；④【§12 决策】**新增决策 29**（no_std 端 event.rs 实现 + Esc 宏复用原生 UI，不注入 TJS、不改游戏数据）；⑤【§14】**新增 M5-f 完成项**与 U1–U3 遗留；⑥【§16】本行；⑦产物 NRO 7,839,800 B sha256 `093ad9e0…`、ELF 17,046,880 B sha256 `0bfc77e1…`、NSP v1.0.1 9,979,435,736 B sha256 `0fda623c…67419`（romfs 9,932,275,140 B/161 entries，verify ok=true 12 checks），Citron p12-g/h/i/n/m 逐项验证，补丁 `rfvp-input-remap.patch`（413 行 sha `44fd0722…`）+ 全量 diff 68,536 B（sha `026a7cee…`）。 |
| v1.14 | 2026-10-31 | M5-g：rfvp 真机四项缺陷修复（光标 / 性能 / 原生退出 / 确认框，Citron 双形态验证）：①【§10 M5】**新增【v1.14】M5-g 状态段**——症状 4 项、根因 4 项、7 文件修复（`sdl_video.c` 主机层 overlay 光标 + `QUIT GAME?` 面板 + 5×7 点阵 + scratch 纹理复用；`event.rs` DIRECTIONS/ACTIONS + MINUS 只开确认框；`app.rs`/`ffi.rs` 查询接口与每帧 `take_quit_confirmed`；`main.c` 每帧 `galnx_sdl_set_overlay`；`no_std_core.rs` 消费 `ExitDialog`/`ExitMode(3)` 并 `save_global_if_changed`；`host_api/event.rs`）；②【§12】**新增 2 条风险**（主机层光标与游戏自绘光标可能并存、确认框仅英文 5×7 点阵）；③【§12 决策】**新增决策 30**（退出确认与光标一律主机层 SDL overlay 自绘，不依赖游戏 UI / 坐标宏）；④【§14】**新增 M5-g 完成项**与 U12–U17；⑤产物 NRO 7,839,800 B sha256 `4f096dd6…`、ELF `f34992a3…`、NSP v1.0.2 9,979,437,784 B sha256 `ff259aa4…`（verify ok=true 12 checks / 1 warn，romfs 9,932,275,140 B / 161 entries），Citron NRO/NSP 双形态 PASS（中文正文 / 光标 / 确认框 / 干净退出、60 fps），DBI FTP 9.98 GB 实测 1,548.7 s ≈ 6.15 MiB/s（25.8 分钟）；⑥文档 `docs/builds/020-rfvp-device-fixes.md`、补丁 `rfvp-device-fixes.patch`（109,915 B / 7 文件 sha `9b65b8b2…`）+ 全量 diff 85,712 B、证据 `docs/milestones/evidence/P13-rfvp-nsp/`、runbook P13 V1–V14、`examples/engines/rfvp.yaml` 与 `examples/pilot02-iroseka.yaml`（artifact 1.0.2）；⑦【§16】本行。 |
| v1.15 | 2026-11-01 | M5-h：rfvp 真机掉帧修复（GPU prev-frame，Citron 同探针验证）：①【§10 M5】**新增【v1.15】M5-h 状态段**——4 类根因（prev-frame 每帧 CPU 回读 8.29 MB、debug BMP 周期回读 41 ms、逐 sprite 无批处理、冷启动/存档尖峰）；②修复 6 文件（`sdl_video.c` 双 render target + 批处理 + 计时、`host_api/render.rs` `supports_gpu_prev_frame`、`prim_commands.rs` `set_prev_frame_gpu`、`no_std_core.rs` GPU 分支 + CPU fallback、`host/src/render.rs` 覆盖 true、`ffi.rs` `DEBUG_SCREEN_ENABLED=false` + host 阶段行）；③【§12】**新增 2 条风险**（GPU prev-frame 依赖 render target、启动/存档尖峰仍在）；④【§12 决策】**新增决策 31**（渲染回读全部 GPU 侧、诊断回读默认关闭、保留 CPU fallback）；⑤【§14】**新增 M5-h 完成项**与 U18–U21；⑥产物 NRO 7,843,896 B sha256 `e5373bd7…`、ELF `e4040e7b…`、NSP v1.0.3 9,979,441,368 B sha256 `b9e0d6a5…`（verify ok=true 12 checks / 1 warn，romfs 9,932,275,140 B / 161 entries），Citron perf3→perf4 定量（slow 154→19、帧>7 151→15、thumb≥20 ms 142→0、slow 总时长 12,133.7→3,567.8 ms）；NSP v1.0.3 DBI FTP 上传 9,979,441,368 B / 1,529.0 s ≈ 6.22 MiB/s（25 分 29 秒，DBI 自动安装）；⑦文档 `docs/builds/021-rfvp-perf-gpu-prev-frame.md`、补丁 `rfvp-perf-gpu-prev-frame.patch`（32,781 B / +481 −50 sha `e64dfb71…`）、全量 diff 107,938 B / 12 文件、证据 `docs/milestones/evidence/P14-rfvp-perf/`、runbook P14 V1–V15、`examples/engines/rfvp.yaml`（artifact 1.0.3）；⑧【§16】本行。 |
