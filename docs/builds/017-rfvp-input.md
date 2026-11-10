# 017 — rfvp Switch 手柄映射与快捷存读档（patch J）

- 编码：017
- 对象：xmoezzz/rfvp（Nintendo Switch target：platform/switch）
- 版本/commit：HEAD 9f07adef2eb5d559777f9bf59a67b756875cb24f；toolchain pin nightly-2026-02-01
- 许可证：MPL-2.0（仓库 LICENSE；patch J 修改的 4 个文件均为 MPL-2.0 源码）
- 日期：2026-10-31
- 执行：Lead（P10 手柄映射）
- 结论：**模拟器级 PASS**。上游 event.rs 的默认映射（方向键光标 / A 左键 / B 右键 / X Enter / Y Space / MINUS Esc / PLUS 退出 / 肩键 Ctrl / 左摇杆光标）在 Citron 实测可用；本记录新增 patch J，补上 **右摇杆滚轮（历史记录）**、**Plus+ZR 快速存档槽 0 / Plus+ZL 快速读档槽 0**，以及引擎侧 **pending save/load 请求的兜底消费**（否则游戏内 SAVE/LOAD 菜单在 Switch 无槽位 UI 时会挂起 VM）。真机未验证（组合键尤其需要真机确认）。
- 产物：rfvp.nro **7,827,512 B，SHA-256 b95cd26bb9c4699f6a9a08cc880e1665710702becf2ae6be00ee1463baab155e**（构建树 E:/galnx-build/m5-rfvp，产物不入库）
- 补丁：`docs/builds/patches/rfvp-switch/rfvp-input.patch`，9,886 B / 4 文件 +124/−4，SHA-256 `aeb8f226e6464f8b07c041f0235a86a381e7efc62bb4443410b19b5fcda0ba84`（**增量补丁**：先应用 `rfvp-sdl2-backend.patch`，再应用此补丁）；全量对照 `rfvp-full.diff` 55,781 B / 9 文件，SHA-256 `aa73cc50e0fca2c9faa727b65ea5315d6e682dd29590f91c1017ced0efd8082f`
- 证据：`docs/milestones/evidence/P10-rfvp-input/`（12 张关键截图 + ODS 日志切片 + 存档清单 + SHA256SUMS.txt）

## 1. 目标

用户（m13963）要求 rfvp 试点先把「能玩」补齐：标题 → 进正文 → 翻页/回看/快进/菜单/存读档都要能用手柄完成。P9 只验证了渲染（60 fps），输入完全没有校准；本记录按 P10-a/b/c/f/g/h 逐段实证，最后用 patch J 补掉两个结构性缺口。

## 2. 环境与工具链（实测）

| 项 | 值 |
| --- | --- |
| 构建 | `bash /e/galnx-build/m5-switch-build3.sh`（wrapper 设 DEVKITPRO=D:/devkitPro、CARGO_HOME=D:/Scoop/persist/rustup/.cargo） |
| 产物 | `target/rfvp-switch/switch/rfvp.nro`（增量构建约 11–15 s） |
| 模拟器 | Citron Nightly `0237a9b88`（GPL-3.0-or-later），Vulkan |
| harness | `scripts/citron_run.sh --detach --input-steps 'wait:MS;capture:NAME;key:LIST'`（PowerShell 侧 PostMessage 逐键注入，**不能同时按住两个键**） |
| guest 数据 | `C:/Users/ACETaffy/AppData/Roaming/citron/sdmc/switch/rfvp/game`（IROSEKA_FHD 解包数据，default.ttf=Sarasa Gothic SC Bold，nls=GBK） |
| 存档根 | `sdmc/switch/rfvp/saves/iroseka-2ae7dc8e/save/`（文件名规则 `rfvp_s{slot:03}.bin`，见 `crates/rfvp/src/subsystem/resources/save_manager.rs:91`） |

Citron 侧键盘→手柄重映射（`qt-config.ini [Controls]`，用于 harness 喂手柄）：

| 虚拟手柄键 | 键盘 | 虚拟手柄键 | 键盘 |
| --- | --- | --- | --- |
| A | C (VK 67) | X | V (86) |
| B | X (88) | Y | Z (90) |
| L / R | Q (81) / E (69) | ZL / ZR | R (82) / T (84) |
| PLUS / MINUS | M (77) / N (78) | 十字键 | 16777234–16777237 |
| 左摇杆 | W/A/S/D + Shift 半幅 | 右摇杆 | I/J/K/L |

## 3. 基线：上游已有的映射（未改动部分）

上游 `platform/switch/host/src/event.rs`（上游 commit c4240ad，非 GalNX 补丁）已实现完整映射，关键常量：

- `SCREEN_WIDTH=1280`、`SCREEN_HEIGHT=720`、`STICK_DEADZONE=8000`、`DPAD_CURSOR_STEP=12`
- `KEYS`：方向键→Up/Down/Left/Right、MINUS→Escape、X→Return、Y→Space、L|R|ZL|ZR→Control
- PLUS→`RfvpEvent::Quit`；A/B 在虚拟光标处发 `PointerDown/PointerUp`（左/右键）；左摇杆 / `STICK_CURSOR_DIVISOR` 移动光标；触摸转发 Pointer/Touch 事件

引擎侧语义：`RfvpEvent::KeyDown{key}` 走 `InputGetKey`/`InputGetKeyState`；游戏是 FVP（Ren'Py 血统的 KeyCode 枚举：Shift=0,Ctrl=1,LeftClick=2,RightClick=3,MouseLeft=4,MouseRight=5,Esc=6,Enter=7,Space=8,Up=9,Down=10,Left=11,Right=12）。

## 4. 实测：映射可用性矩阵（P10-a/b/c）

| 输入 | 期望 | 实测 | 证据 |
| --- | --- | --- | --- |
| 方向键 RIGHT×10 | 光标移到 New Game 上（悬停） | ✅ 出现白色高亮；两次独立 run 截图**逐字节相同**（sha `3650c304…`） | 01-title-cursor-hover.png |
| A（光标处左键） | 确认，进入游戏 | ✅ 淡入白场（white=0.93） | — |
| X（Enter） | 推进正文 | ✅ 文字从「……」变成「从天而降的羽毛。」 | 02-story-enter.png |
| Y（Space） | 推进正文 | ✅ 又换一条 | 03-story-space.png |
| B（右键） | 隐藏/恢复消息窗 | ✅ 按一次文字层消失（纯白），再按恢复（原文字回来） | 04-rmenu-hide.png、P10-c c-B1/c-B2 |
| 肩键 L/R/ZL/ZR（Ctrl） | 快进 | ✅ 连按后连续换场景（P10-b step-50/57） | 05-skip-ctrl-L.png、06-skip-ctrl-R.png |
| MINUS（Esc） | 打开游戏内 system 菜单 | ✅ 出现青色时钟背景的 SAVE/LOAD/HIDE/UNDO/OPTION/TITLE/EXIT/RETURN 竖排菜单 | 07-system-menu.png |
| PLUS | 退出 | ✅ 画面全黑、进程正常结束 | 12-quit-plus.png |
| 右摇杆（上/下） | 滚轮：上滚=历史记录 | ✅ 打开 BACKLOG 界面（左侧竖排 BACKLOG、正文「……羽毛。」、右侧滚动条）；下滚不关闭（BACKLOG 需 B/Esc 关） | 09-backlog-wheel-up.png |
| 游戏内 system 菜单项（Enter/方向键） | 选择 SAVE/LOAD | ❌ **完全无反应**（59 步 run 里菜单画面 sha 逐字节不变，无 save 请求日志） | P10-g |

结论：可玩所需的核心操作（翻页、回看、快进、隐藏文字、退出）都在手柄上成立；唯一结构性缺口是**游戏内 SAVE/LOAD 菜单**。

## 5. 两个结构性缺口（根因）

### 5.1 游戏内 system 菜单是纯指针驱动的

P10-g 用 Enter/方向键/DOWN×3 操作菜单，菜单画面 sha 全程不变（`4152234255…`），citron_log 无任何 `save request`/`quick save` 记录。P10-c 的 `step-48-c-ctrl.png` 显示：指针移到 SAVE 上时游戏画出了中文 tooltip「保存存档」——说明**菜单只吃指针 hover/click，不吃键盘/方向键**。Switch 端光标虽然能移过去（左摇杆/十字键），但把 1280x720 指针精确落到右边缘竖排菜单项上，在 720p letterbox + 无坐标反馈的条件下不可靠（几何换算已尝试，客户区无纯黑边可标定，放弃硬算坐标）。

### 5.2 引擎的 save/load 请求在 Switch 端无人消费

源码链路（已读）：

- `crates/rfvp/src/subsystem/components/syscalls/legacy.rs:367 load_file()` → `set_pending_save_load_request(LoadFile); game_data.thread_wrapper.should_break();`
- `legacy.rs:377 save_file()` → `request_prepare_local_savedata(); set_pending_save_load_request(SaveFile); should_break();`
- 桌面端消费者：`crates/rfvp/src/app.rs:650-703 next_frame()` 取 pending 请求 → `legacy_save_load_ui.open()`（wgpu+winit 桌面 UI，`app.rs:79`）→ UI 关闭后 `gd.set_halt(false)`
- Switch 端：`crates/rfvp/src/no_std_core.rs` **没有任何 take_pending_save_load_request 引用** → 请求被丢弃，而 `should_break()` 已让 VM 挂起等待，菜单点 SAVE 只会静默卡住
- Switch 端已具备的能力：`no_std_core.rs:566 commit_prepared_save(host)` / `:569 capture_pending_save(host)`；`legacy.rs:469 save_quick()` / `:476 load_quick()`、`legacy.rs:178 get_quick_slot()`（Int 0..4 或 Nil→0）

## 6. patch J 的内容（4 文件 +124/−4）

| 文件 | 改动 |
| --- | --- |
| `crates/rfvp/src/host_api/event.rs` | `RfvpEvent` 新增 `QuickSave` / `QuickLoad`（桌面端仍有自己的槽位 UI，主机端由 host 发事件） |
| `crates/rfvp/src/no_std_core.rs` | ① tick 的 drain 循环处理 QuickSave/QuickLoad → `legacy::save_quick/load_quick(&mut game_data, &Variant::Int(0))`，成功/失败写 host.log；② 在 VM tick 之后、flush_audio 之前取 `take_pending_save_load_request()`：SaveFile/SaveTitle → 快速存档槽 0，LoadFile/LoadTitle → 快速读档槽 0，日志写明「no slot UI on this target」 |
| `platform/switch/runtime/main.c` | `RfvpSwitchInput` 增加 `right_stick_x/right_stick_y`，主循环用 `padGetStickPos(&pad, 1)` 填充 |
| `platform/switch/host/src/event.rs` | ① PLUS 改为「修饰键」：按下先记 pending_quit，按住期间 ZR→QuickSave、ZL→QuickLoad（并取消退出），松开才发 Quit；② 右摇杆竖向 `\|v\|>=8000` 每 6 poll 发 `Wheel{±120}`（首个 poll 立即发一次，短按也能滚一行）；③ 光标除数 18000→6000（移动快 3 倍） |

最终手柄语义（主机端）：

| 键 | 语义 |
| --- | --- |
| 方向键 / 左摇杆 | 虚拟光标（方向键 12 px/次，摇杆更快） |
| A / B | 光标处鼠标左键 / 右键（确认 / 隐藏文字） |
| X / Y | Enter / Space（推进正文） |
| MINUS | Esc（打开游戏内 system 菜单） |
| 肩键 L/R/ZL/ZR | Ctrl（快进） |
| 右摇杆上/下 | 滚轮（上=历史记录 BACKLOG） |
| PLUS | 单击 = 退出游戏 |
| PLUS + ZR | 快速存档到槽 0 |
| PLUS + ZL | 快速读档槽 0 |

## 7. 验证（P10-h，Citron）

- run dir：`E:/galnx-build/m5-rfvp-run/p10-h/20261031-050445-rfvp`（status=loaded rc=0 finished=2026-10-30T21:08:57Z，10 PNG）
- harness 无法同时按两键，因此验证时用**临时单键诊断映射**（L→QuickSave、R→QuickLoad，仅在诊断构建中存在 3 分钟，产物 sha `7da3c0cf…`），验证事件→引擎→落盘整条链；随后删除诊断、重建最终产物
- ODS 日志（切片见 `evidence/P10-rfvp-input/ods-log.txt`）：
  - `rfvp [info] quick save: wrote slot 0`
  - `rfvp [info] quick load: read slot 0`
  - `rfvp [info] quit requested by host event`
- 落盘证据：`saves/iroseka-2ae7dc8e/save/rfvp_s000.bin` 490,104 B，SHA-256 `7cac48abadc850f30beac555d67a3213…`（存档目录清单见 `saves-list.txt`；另有游戏自身滚动写的 `rfvp_s481..s490.bin`）
- 画面证据：`09-backlog-wheel-up.png`（滚轮打开 BACKLOG）、`10-quicksave.png`、`11-quickload.png`、`12-quit-plus.png`

### 7.1 最终 NRO 复验（P10-i，无诊断代码）

- run dir：`E:/galnx-build/m5-rfvp-run/p10-i/20261031-051324-rfvp`（status=loaded rc=0 finished=2026-10-30T21:17:19Z；citron_log 148,931 B，panic=0 / EXCEPTION=0）
- 序列：标题 → 10×RIGHT 悬停 New Game → A 进入 → 等 65 s → Enter 推进 → 右摇杆上推 → 右摇杆下推 → Enter → PLUS
- 关键帧（已复制进 `evidence/P10-rfvp-input/`）：
  - `13-i-final-title-hover.png` SHA-256 `378603c3…`（悬停高亮）
  - `14-i-final-story-enter.png` `85d636e8…`（Enter 推进后新台词，与上一帧不同）
  - `15-i-final-backlog.png` `112c80cf…`（右摇杆上推 → BACKLOG 画面：左侧竖排 BACKLOG + 右侧滚动条）
  - `16-i-final-quit.png` `e84daad0…`（PLUS 退出，全黑）
- 观察：BACKLOG 打开后右摇杆下推与 Enter 的截图与打开帧逐字节相同（滚轮在 backlog 内滚动、Enter 不关闭面板）；关闭 backlog 需 B（右键）或 Minus。这不影响验收，但已记入限制。

## 8. 产物哈希

| 产物 | 大小 | SHA-256 |
| --- | --- | --- |
| `rfvp.nro`（最终，无诊断） | 7,827,512 B | `b95cd26bb9c4699f6a9a08cc880e1665710702becf2ae6be00ee1463baab155e` |
| `rfvp.nro`（P10-h 诊断构建） | 7,827,512 B | `7da3c0cf9682664b1edbedb836bbc5e68a893d9af94f7fd3c5953ccd40af3349` |
| `rfvp-input.patch` | 9,886 B | `aeb8f226e6464f8b07c041f0235a86a381e7efc62bb4443410b19b5fcda0ba84` |
| `rfvp-full.diff`（HEAD→当前全部改动） | 55,781 B | `aa73cc50e0fca2c9faa727b65ea5315d6e682dd29590f91c1017ced0efd8082f` |

补丁应用顺序与回放校验：

```bash
# 在 rfvp HEAD 9f07adef 的干净树里：
git apply docs/builds/patches/rfvp-switch/rfvp-sdl2-backend.patch
git apply docs/builds/patches/rfvp-switch/rfvp-input.patch
# 或用全量：git apply docs/builds/patches/rfvp-switch/rfvp-full.diff
```

两份补丁都已在「HEAD→apply→与工作树逐文件比对」流程中验证：4/4 文件内容一致（`main.c` 因仓库 CRLF 设置差异，仅换行符不同，`diff --strip-trailing-cr` 为空）。全量 diff 覆盖 9 个文件（含新增 `sdl_video.c`），同样 9/9 一致。

## 9. 复现步骤

```bash
# 构建（增量）
bash /e/galnx-build/m5-switch-build3.sh
# 运行（Citron，harness detach）
export CITRON_USER_DIR="C:/Users/ACETaffy/AppData/Roaming/citron"
export TEMP=/c/Users/ACETaffy/AppData/Local/Temp
cd '/e/Othergames/Nintendo Switch/Workspace/GalNX'
bash scripts/citron_run.sh --nro E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro \
  --detach --timeout 320 --settle 8 --out E:/galnx-build/m5-rfvp-run/p10-h \
  --input-steps 'wait:8000;key:RIGHT;...;key:C;wait:65000;key:V;key:I;key:M'
```

harness 注入的原语：`wait:MS` / `capture:NAME` / `key:LIST`（单键 PostMessage，hold 60 ms、gap 250 ms）。断言用截图 sha + 白场比例 + citron_log 的 ODS 行。

## 10. 限制与未验证项

- **U1（真机组合键）**：Plus+ZR / Plus+ZL 是新增组合逻辑，harness 不能同时按两键，只在诊断单键路径上验证了事件→引擎→落盘链路；真机必须复验组合键。
- **U2（游戏内 system 菜单仍不可手柄操作）**：菜单是纯指针驱动，手柄只能靠移动光标点击；精确落点未解决。当前用 Plus 组合快速存读档绕过，菜单的 HIDE/UNDO/OPTION/TITLE 等项暂不可达。
- **U3（音频）**：仍未验证（同 016）。
- **U4（真机）**：全部结论来自 Citron；真机内存/性能/存档路径未验证。
- **U5（快速槽固定 0）**：仅槽 0；多槽位选择 UI 属后续工作。引擎内部单槽写盘约 490 KB，写盘时机沿用 `capture_pending_save/commit_prepared_save`。
- **U6（存档时机）**：快速存档在 skip/淡入期间的安全性未测；建议战斗/选项场景前手动存档。
- **U7（中文）**：本记录未涉及中文本地化流程（nls=GBK 已在 config 内生效，属于下一个里程碑）。

## 11. 变更记录

- 2026-10-31：首版。patch J 生成并入库；P10-a/b/c/f/g/h 六轮实测记录；最终 NRO `b95cd26b…`。
- 2026-10-31：补 §7.1 最终 NRO 复验（P10-i，无诊断代码）与 4 张证据帧；补 BACKLOG 关闭方式说明；证据目录 SHA256SUMS 刷新（16 截图 + ods-log + saves-list）。
