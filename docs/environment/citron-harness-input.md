# Citron 冒烟工具的输入注入能力（M2-a）

- 文档版本：M2-a（2026-10-30）
- 关联：`scripts/citron_run.sh`（`--input-*` 参数）、`docs/environment/citron-harness.md`（基础冒烟工具）、`docs/milestones/evidence/M2a-*`（实证证据）
- 结论一句话：**在 Citron 上，鼠标点击注入（SendInput mouse_event）与键盘 PostMessage 注入都能被运行中的 krkrsdl2/KAG3 收到并推进游戏**；KAG3 demo 已验证「标题画面 → 正文页」的真实状态变化（仅游戏区像素差异 0.494）。

## 0. 边界声明

本能力只做「模拟器内的输入注入 + 取证」，用于在 NRO 里程碑上验证「应用能进入交互状态」。它不修改 Citron 配置、不读写钥匙文件内容、不涉及商业游戏数据；注入的是模拟输入，不是真机手柄/触摸链路。**模拟器上通过 ≠ 真机通过**（真机输入层仍需 M2 真机阶段验证）。

## 1. 能力与实证结果

`citron_run.sh` 新增输入注入阶段：拿到 Boot 行 + 截图后，先等 `--input-delay`，再按参数执行「一次鼠标点击」和/或「一串键盘按键」，然后等 `--input-settle` 截取注入后画面，并对**游戏区**（默认 y=70..950，去掉顶部 Citron 菜单与底部状态栏）做像素差异统计。

实测（krkrsdl2 clean NRO，Citron nightly `main-0237a9b88`，2026-10-30）：

| 运行 | 注入 | clicks | keys_sent | focus_ok | diff_ratio（仅游戏区） | 画面结果 |
| --- | --- | --- | --- | --- | --- | --- |
| `runs/20261030-020438-krkrsdl2` | 点击「What is KAG?」链接 | 1 | 0 | true | **0.49446** | 标题菜单 → KAG3「What is KAG?」正文（打字中） |
| `runs/20261030-020644-krkrsdl2` | 同一点击 + 按键 C | 1 | 1 | true | **0.494313** | 标题菜单 → 正文页（完整文本 + ▼ 继续标记） |
| 手工（同一 `--keep` 实例，仅按键 C×2） | PostMessage VK 67 | 0 | 2 | false | **0.556076**（每次按键后） | 正文页 → 翻页过渡帧 → 下一页完整文本 |

三条 JSON 走「click-only / click+key」两种组合都验证了注入通道本身工作；键盘是否推进特定画面取决于应用交互设计（KAG3 的标题菜单是**链接点击**交互，按键 C 映射到游戏内按钮 A，在该页不触发导航；正文页的「继续」才吃按键）。

## 2. 技术原理

### 2.1 Citron 的输入链路（源码依据：本地 clone `/e/galnx-build/m2-tools/citron-src`，HEAD `c3aa70f`）

- **鼠标/触摸**：`src/citron/bootmanager.cpp` 的 `GRenderWindow::mousePressEvent` 里，先用 `mapFromGlobal(QCursor::pos())` 取坐标（**注意读的是当前系统光标位置，不是事件坐标**），再 `input_subsystem->GetMouse()->PressButton(...)`，并且调用 `PressTouchButton(touch_x, touch_y, button)` —— 即**鼠标按下会同时产生一条触摸输入**（`src/input_common/drivers/mouse.cpp` 的 `Mouse::PressTouchButton`，设备 ID 为 `mouse_touch_identifier`）。
- **krkrsdl2 侧**：`src/core/sdl2/SDLApplication.cpp` 设置了 `SDL_HINT_TOUCH_MOUSE_EVENTS=1`，触摸事件会合成鼠标事件；KAG3 的链接点击走 `OnClick`，因此「Citron 鼠标点击 → 触摸/鼠标事件 → SDL → TJS OnClick」这条路通。
- **键盘**：`GRenderWindow::keyPressEvent` 开头有首帧门控 `if (!first_frame) { event->ignore(); return; }`，之后做热键匹配，最后 `input_subsystem->GetKeyboard()->PressKey(event->key())`（Qt key 值）——手柄映射里的 `engine:keyboard,code:67` 用的就是这条通道（`src/input_common/drivers/keyboard.cpp` 的 `PressKey` → `SetButton`）。
- **first_frame 的后果**：注入必须发生在应用画出首帧之后。工具默认 `--input-delay 1500`（毫秒），并在拿到 Boot 行 + `--settle` 截图之后才注入；实测 1500–2500 ms 都足够。

### 2.2 焦点

- 注入前，助手会执行 `AttachThreadInput(当前线程, 前台窗口线程) → BringWindowToTop → SetForegroundWindow → 解除 attach`，绕开 Windows 前台锁。
- **点击前必须先把光标挪到目标**：`SetCursorPos(窗口左上+8,+8)` → 短暂停留 → `SetCursorPos(目标点)`，这样 Qt 的 `mousePressEvent` 才能从 `QCursor::pos()` 读到目标坐标。
- `focus_ok` 表示注入后 `GetForegroundWindow()` 是否等于 Citron 主窗口；点击路径通常为 true，纯按键路径可能为 false（不点击就没有抢焦点的动作），但 **PostMessage 按键不需要窗口在前台**，实测 focus_ok=false 时按键依然被处理。

### 2.3 两条注入通道的实测对比（关键结论）

| 通道 | 实测结果 | 说明 |
| --- | --- | --- |
| `SendInput`（键盘，扫描码 + VK，40 字节 INPUT 结构） | **无效**：`SendInput` 返回 1（成功插入），但游戏画面 diff ≈ 0.0003（仅 FPS 数字变化） | 疑似 Qt 对注入键盘事件的处理路径/焦点问题；根因未完全定论。**注意**：`INPUT` 结构必须是 40 字节（含 MOUSEINPUT 的 union），只含 KEYBDINPUT 的 32 字节版本会让 `SendInput` 返回 0 + `GetLastError=87(ERROR_INVALID_PARAMETER)` |
| `PostMessage`（`WM_KEYDOWN/0x0100` + `WM_KEYUP/0x0101`，lParam 带扫描码） | **有效**：一次按键即让 KAG3 正文 diff 0.556，连按可连续翻页 | 直接投递到 Citron 主窗口消息队列；不要求窗口在前台 |
| `SendInput`（鼠标，`SetCursorPos` + `mouse_event` 左键） | **有效**：点击「What is KAG?」链接，diff 0.494 | 走 §2.1 的 mouse→touch 链路 |

因此工具默认的按键通道是 **PostMessage**（JSON 里 `key_method="postmessage"`）。这是模拟器内的取证手段，**不是**硬件级输入注入；真机输入需另测。

### 2.4 截图与差异口径

- 前后图都由内嵌 PowerShell 助手用 `PrintWindow(hwnd, 2)` 抓取（`PrintWindow` 失败或全黑时回落到 `CopyFromScreen`），输出为窗口**物理像素**（本机 150% 缩放：窗口 1728×1016 物理像素，DPI 144）。
- `--input-click X,Y` 的坐标就是 **window.png 上的像素坐标**（1:1 物理像素），屏幕坐标 = 窗口物理左上 + (X,Y)。
- diff 只统计游戏区 `y∈[region_top, region_bottom)`（默认 70–950），每 2 个像素采样一次（总采样像素约 380,160），`|ΔR|+|ΔG|+|ΔB|` 超过 30 记为一个差异像素；`diff_ratio = 差异像素 / 采样像素`。排除顶部菜单与底部状态栏，避免 FPS/菜单动画污染。

## 3. 参数

在原有参数（见 `citron-harness.md` §4）之外新增：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--input-click X,Y` | 关 | 在 window.png 像素坐标 (X,Y) 处点击一次（含聚焦动作） |
| `--input-keys LIST` | 关 | 逗号分隔的按键列表，键名或十进制 VK：`C,ENTER,SPACE,DOWN,67` |
| `--input-delay MS` | 1500 | 截图完成后、注入前的等待（等首帧/loading 结束） |
| `--input-settle MS` | 1200 | 注入完成后、注入后截图前的等待 |
| `--input-hold MS` | 60 | 每个按键按下到抬起的间隔 |
| `--input-gap MS` | 250 | 相邻按键之间的间隔 |
| `--input-region T,B` | 70,950 | diff 统计的游戏区 y 范围（像素，相对窗口图像） |

键名 → VK 对照（脚本内归一化，大小写不敏感）：`ENTER=13`、`SPACE=32`、`ESC=27`、`TAB=9`、`BACKSPACE=8`、`UP=38`、`DOWN=40`、`LEFT=37`、`RIGHT=39`、`SHIFT=16`、`CTRL=17`、`ALT=18`、`A–Z`=ASCII、`0–9`=48+n；也接受任意十进制 VK 码。

Citron 默认手柄映射（`%APPDATA%\citron\config\qt-config.ini`，本机实测）：`player_0_button_a=engine:keyboard,code:67`（C）、`plus=77`（M）、`minus=78`（N）、方向键 = 16777234–16777237；因此「按 C」=「按 Switch 的 A」。KAG3 demo 的 `system/MainWindow.tjs` 里 `VK_PAD1 => VK_RETURN`，即游戏内 A 键映射为「推进」。

## 4. JSON 中的 `input` 字段

`result.json`（以及 stdout 的 JSON）新增：

| 字段 | 说明 |
| --- | --- |
| `input.injected` | 是否执行了注入阶段（false 表示未请求或前置条件不满足，见 `input.error`） |
| `input.key_method` | 实际生效的按键通道，恒为 `"postmessage"`（未请求按键时为空串） |
| `input.keys_requested` | 请求的 VK 码数组（如 `[67]`） |
| `input.keys_sent` | 实际投递的按键数 |
| `input.focus_ok` | 注入后 Citron 主窗口是否在前台 |
| `input.clicks` | 实际执行的鼠标点击次数（0/1） |
| `input.screenshot_before` / `input.screenshot_after` | 注入前/后截图绝对路径（`window-before-input.png` / `window-after-input.png`） |
| `input.diff_ratio` | 游戏区像素差异比例（0–1） |
| `input.nonblack_before` / `input.nonblack_after` | 前/后图非黑像素比例 |
| `input.region` | diff 区域描述，如 `1728x1016 y=70-950` |
| `input.error` | 失败原因码（成功为空串） |

示例（`docs/milestones/evidence/M2a-kag3-input-run-click-key.json`）：

```json
"input": {"injected": true, "key_method": "postmessage", "keys_requested": [67], "keys_sent": 1,
          "focus_ok": true, "clicks": 1, "diff_ratio": 0.494313,
          "nonblack_before": 0.7159, "nonblack_after": 0.7186, "region": "1728x1016 y=70-950", "error": ""}
```

运行目录新增文件：`window-before-input.png`、`window-after-input.png`（`window.png` 仍是注入前的基线截图）。

## 5. 用法

```bash
# 1) 只点一次（KAG3 标题菜单 → 点「What is KAG?」：window.png 上 (861,589)）
bash scripts/citron_run.sh --nro E:/galnx-build/m1-krkrsdl2/build5/krkrsdl2.nro \
  --timeout 120 --settle 20 --expect-title Kirikiri --app-log-regex 'Booting game:' \
  --input-click 861,589 --input-delay 2500 --input-settle 3000

# 2) 点击 + 按键 C（= Switch A），验证「点击打开页面 → 按键推进」
bash scripts/citron_run.sh --nro <nro> --expect-title <stem> --app-log-regex 'Booting game:' \
  --input-click 861,589 --input-keys C --input-delay 2500 --input-settle 3000

# 3) 只用键盘（应用已能靠按键推进时）
bash scripts/citron_run.sh --nro <nro> --expect-title <stem> \
  --input-keys ENTER,ENTER --input-delay 2000 --input-settle 2500
```

判定：`input.injected=true` 且 `input.diff_ratio` 明显（>0.05 通常说明画面切换；纯动画/打字也会贡献差异），配合 `input.screenshot_before/after` 人工核对。`input.diff_ratio` **不是**「输入被应用接受」的充分条件，最终以「画面状态发生语义变化」为准；必要时对 after 图做 OCR/人工判读（本项目用 `read_image` 人工核验）。

## 6. 失败模式

| `input.error` / 现象 | 含义 | 处理 |
| --- | --- | --- |
| `no_window_or_boot: ...` | 没有窗口/没有 Boot 行，注入被跳过（此时 status 本身可能已失败） | 先修基础冒烟 |
| `no_before_screenshot: ...` | 基线 `window.png` 缺失 | 看截图阶段错误（§7 of citron-harness.md） |
| `input_helper_failed: ERR\t...` | PowerShell 助手失败（窗口句柄失效/GetWindowRect 失败等） | 检查 hwnd 是否仍有效；重跑 |
| `key_post_failed: helper posted 0 ...` | PostMessage 一个键都没投递 | 检查 VK 列表 |
| `after_screenshot_failed: ...` | 注入后截图失败 | 重试；确认窗口未最小化 |
| `diff_failed: ERR\t...` | 像素 diff 失败 | 检查前后图是否都存在 |
| `focus_ok=false`（不算错误） | 未点击时未抢到前台；按键仍可能生效 | 看 diff/画面确认 |

## 7. 实证证据（`docs/milestones/evidence/`）

| 文件 | 字节 | sha256 | 说明 |
| --- | --- | --- | --- |
| `M2a-kag3-title-before.png` | 940,588 | `0bce597c8866ee4b436c9bce391d6b5647fff7ccfd31b16e12844206cd2b2863` | 注入前：KAG3 标题菜单（与 M1c 标题截图同 hash） |
| `M2a-kag3-text-after-click.png` | 1,368,884 | `d97646f7eb15b89dd3b6c789d3b1899494a30ff847ed0e3bb56fbfe183f89ec0` | 点击「What is KAG?」后：正文页（打字中） |
| `M2a-kag3-text-after-click-key.png` | 1,381,403 | `c18da3c1f3fdb4ad11b2098a61c026b823b4a874abf4c12aad85f0e6437f6b15` | 点击 + 按键 C 后：正文页完整文本 + ▼ |
| `M2a-kag3-text-full-after-key.png` | 1,381,385 | `4fb288029cb245459c1903431f376df8c67d64dfca393075603458ce807c5c8d` | 仅按键 C×2 后：下一页完整文本（无 ▼） |
| `M2a-kag3-key-before.png` | 1,381,478 | `a6e2ee3381ad8a2ef1fe78e60d29025c07b631b621631f0d9362976650cd3d24` | 键盘辅助实验的 before（正文页 + ▼） |
| `M2a-kag3-key-after.png` | 1,723,557 | `ce6090b2e1be2a4e42569cedf467f34b3c43571aefd34e8dd1ef96ab155b96c9` | 按键 C 后：翻页过渡帧（纯背景） |
| `M2a-kag3-input-run-click.json` / `.log` | 1,852 / 1,364 | `803c2dfa…` / `5c9113f3…` | click-only 运行的 result.json / run.log |
| `M2a-kag3-input-run-click-key.json` / `.log` | 1,866 / 1,365 | `db3de149…` / `8b0564b6…` | click+key 运行的 result.json / run.log |
| `M2a-kag3-citron-log-slice.txt` | 43,421 | `b3333ea997acdb0a219ec86808095c7a09e4a1f3dfeb2c9f6ff1a7c86b2a1fc9` | click+key 运行对应的 Citron 日志段 |
| `M2a-kag3-artifacts-sha256.txt` | — | — | 上述证据的机读 sha256 清单 |

完整清单与 hash 复核命令：`docs/milestones/evidence/M2a-kag3-artifacts-sha256.txt`。

## 8. 已知限制与未验证

1. **只验证了 krkrsdl2/KAG3 demo**：其它引擎（TyranoScript、RPG Maker MV、Brewser 的 DOM 页面）的输入路径未验证；Brewser 的输入映射由 Web 页面自身决定。
2. **KAG3 demo 在 Citron 上只有 18–30 FPS**：打字/翻页动画期间截图可能截到过渡帧（`M2a-kag3-key-after.png` 就是过渡帧），故 after 图最好带 `--input-settle` ≥ 2500–3000 ms 再取。
3. **PostMessage 不是硬件级注入**：它跳过 HID/窗口焦点路径；真机上不存在这条通道。真机输入验证必须在 M2 真机阶段另做（hbmenu + 完整内存模式 + 物理手柄/触摸）。
4. **raw input / HID 键盘**：本机 `enable_raw_input=false`、`keyboard_enabled=false`，所以 PostMessage 可行；若打开 raw input 或 HID 键盘设备，该通道的行为可能不同（未验证）。
5. `focus_ok` 只反映前台窗口，不反映 Qt 内部焦点（Qt 单窗口模式下所有 widget 共用一个原生窗口，`GUITHREADINFO` 无法区分）；点击之所以可靠，是因为它走鼠标→触摸链路而非焦点键盘路径。
6. 未验证：手柄（Citron 的 SDL 控制器映射）注入、触摸屏注入、长时间连续注入的稳定性、多键组合（CTRL+C 等）。
7. 注入键序列的语义依赖应用：KAG3 标题菜单只认点击；同一按键在不同页面行为不同。工具只保证「事件被投递并产生画面变化」，不保证「触发某个具体功能」。
8. 密钥/配置：工具只检查 `keys/prod.keys` 存在与大小，不读取内容、不修改 `qt-config.ini`；本能力不写入任何 Citron 配置。

## 9. 复现（本机，2026-10-30 实测）

```bash
cd 'E:/Othergames/Nintendo Switch/Workspace/GalNX'
bash scripts/citron_run.sh \
  --nro E:/galnx-build/m1-krkrsdl2/build5/krkrsdl2.nro \
  --timeout 120 --settle 20 --expect-title Kirikiri --app-log-regex 'Booting game:' \
  --input-click 861,589 --input-keys C --input-delay 2500 --input-settle 3000
```

环境：Citron `Citron-windows-nightly-0237a9b88-x64-msvc.zip`（sha256 `0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb`），Windows 11 24H2，RTX 4060 Laptop，Vulkan 后端；NRO：`krkrsdl2.nro` 17,911,329 B sha256 `8124ffd2e8c813de6f1929a16aa69322878c47af5631d089c3809a576d1c52a7`。

## 10. 合规

- 不读取/复制/打印 `prod.keys`/`title.keys` 内容；不使用商业游戏数据、固件、密钥。
- 不修改 Citron 用户配置；`--input-* `只注入输入并截图。
- Citron 仅作为外部实验工具（GPL-3.0-or-later），本工具不与其链接、不将其代码纳入 GalNX。
- 证据图均为本项目自建 NRO 与开源 KAG3 demo 的画面，可入库（`docs/milestones/evidence/`）。
