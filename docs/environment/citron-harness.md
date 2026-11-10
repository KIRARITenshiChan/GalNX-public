# Citron 冒烟测试工具（citron-harness）

- 文档日期: 2026-10-30
- 维护: audit-web（task-15 / M1-b）
- 脚本: `scripts/citron_run.sh`（bash，git 入库）
- 证据: `workspaces/citron-harness/evidence/`（`workspaces/` 已被 .gitignore 忽略，不入库）

## 0. 边界声明

本工具只做「启动已构建好的 NRO → 取证 → 归档」：

- 不构建、不编译任何东西；不下载、不安装任何软件；
- 不读取、不打印、不复制 `prod.keys` / `title.keys` 的内容（只判断文件存在与非空）；
- 不修改 Citron 用户配置（`qt-config.ini`）；Citron 自己按 title 生成的 `config/custom/*.ini` 属于其运行时行为；
- 不删除虚拟 SD 中任何已有数据；
- 唯一写入虚拟 SD 的动作：把被测 NRO 复制到 `sdmc/switch/galnx-harness/`。

## 1. 用途与位置

给 M1 之后每个 NRO 里程碑（M1-d `m1-sdl2.nro` 起）提供一条可重复的冒烟命令：启动 Citron → 等启动证据 → 截窗口图 → 归档 Citron 日志 → 输出单行 JSON 结果。

```
scripts/citron_run.sh          # 唯一脚本（单文件；运行时把 PowerShell 窗口助手写进 run 目录）
workspaces/citron-harness/
  runs/<YYYYmmdd-HHMMSS>-<stem>/   # 每次运行一个归档目录
  evidence/                       # 人工挑出的自测证据（截图/result.json/日志副本）
```

每次运行的归档目录内容：

| 文件 | 说明 |
| --- | --- |
| `result.json` | 与 stdout 完全相同的单行 JSON |
| `run.log` | 人读运行日志（启动模式、wrapper、信号、错误） |
| `window.png` | 窗口截图（PowerShell PrintWindow 优先，失败回落 CopyFromScreen） |
| `citron_log.txt` | 运行后 `citron_log.txt` 的完整副本 |
| `citron_log_slice.txt` | 只保留最后一次 `citron Version:` 之后的日志（本次运行的段） |
| `citron_win.ps1` | 本次使用的窗口助手（便于复现/审计） |

## 2. 前置条件

1. **Windows** + PowerShell 5.1（`powershell.exe` 在 PATH；脚本可执行任意标准 bash，如 git-bash）。
2. **Citron Neo（nightly）已解压可用**。推荐资产（M1 锁定的版本，见 `docs/audit/07-web-citron.md`）：
   - 来源: `https://github.com/citron-neo/emulator/releases/download/2026-04-27/Citron-windows-nightly-0237a9b88-x64-msvc.zip`
   - 大小 40,497,628 B，sha256 `0d2c9bf3dabacfc7a729df38a6f97d5f88417ffab05ffb064cf930135f6d1acb`
   - 解压后 `citron.exe` 23,272,960 B；构建标识 `main-0237a9b88`
   - 本机解压位置：`Workspace/GalNX/workspaces/web-02/citron/citron.exe`（脚本默认会在这里找）
3. **keys 由用户自备**（本仓库不存放、不入库）：放到 Citron 用户目录的 `keys/prod.keys`、`keys/title.keys`。脚本只检查 `prod.keys` 存在且非空。
4. **Citron 至少启动过一次**，以便生成用户目录与日志（Windows 默认 `%APPDATA%\citron`）。
5. 被测 NRO 文件已存在（任意路径）；脚本不关心它是谁构建的。

> 本机现状（2026-10-30 实测）：`%APPDATA%\citron` 下 `keys/prod.keys` 12,007 B、`title.keys` 11,492 B；日志 `%APPDATA%\citron\log\citron_log.txt`；虚拟 SD 根 `%APPDATA%\citron\sdmc`（`use_virtual_sd=true`）。

## 3. 快速开始

```bash
# 最小用法：默认超时 60 s，标题期望 = NRO 文件名去掉 .nro
bash scripts/citron_run.sh --nro workspaces/web-01/brewser.nro

# 指定成功信号（推荐给 M1-d）：
bash scripts/citron_run.sh \
  --nro build/m1-sdl2.nro \
  --timeout 60 \
  --expect-title m1-sdl2 \
  --app-log-regex 'BootGame: Booting game:' \
  --settle 8
```

stdout 最后一行是 JSON；stderr 是进度日志；退出码：

| 退出码 | status | 含义 |
| --- | --- | --- |
| 0 | `loaded` | 拿到 Boot 行（应用已被 Citron 装载并进入引擎） |
| 1 | `timeout` | 超时，没有拿到 Boot 行（详见 JSON 的 `error` 原因码） |
| 2 | `fail` | 参数/环境/启动阶段失败（NRO 不存在、keys 缺失、已有 Citron 进程等） |

## 4. 参数表

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--nro PATH` | 与 `--game` 二选一 | 被测 NRO；会先复制到虚拟 SD 的 `switch/galnx-harness/<basename>`。等价于 `--game`（M3-b 起保留向后兼容） |
| `--game PATH` | 与 `--nro` 二选一 | 任意 Citron 可加载的游戏文件：`.nro`、`.nsp`、`.xci`、`.nsz`、`.xcz`（M3-b）。同样复制到虚拟 SD 再以 `-g` 引导；类型按扩展名识别并写入 JSON `game_type` |
| `--nsp PATH` | — | `--game` 的别名（语义完全相同） |
| `--timeout SEC` | 60 | 等待 Boot 行的上限（秒） |
| `--settle SEC` | 6 | 拿到 Boot 行后再等多久才截图（给首帧渲染留时间） |
| `--expect-title TXT` | NRO stem | 窗口标题必须包含该子串（大小写不敏感）才算 title 信号命中 |
| `--expect-file REL` | 空 | 虚拟 SD 相对路径（如 `switch/m1-app/ready.txt`），mtime ≥ 启动时刻即视为应用自输出 |
| `--app-log-regex RE` | 空 | Citron 日志（本次运行段）中出现该 ERE 即视为应用自输出 |
| `--citron-exe PATH` | 自动发现 | 默认依次找 `workspaces/citron-harness/citron/citron.exe`、`workspaces/web-02/citron/citron.exe`、`workspaces/*/citron/citron.exe` |
| `--sd PATH` | `<user dir>/sdmc` | 虚拟 SD 根（覆盖用） |
| `--out DIR` | `workspaces/citron-harness/runs` | 归档根目录 |
| `--keep` | 关 | 取证后不杀本次启动的 Citron（调试用；默认只杀本次新增 pid） |
| `--allow-existing` | 关 | 已有 citron 进程时仍继续（默认直接 fail，避免误杀/串台） |
| `-h/--help` | — | 帮助，退出码 0 |
| `--input-click X,Y` | 关 | 在 `window.png` 像素坐标 (X,Y) 处点击一次（先抢焦点；M2-a 起） |
| `--input-keys LIST` | 关 | 逗号分隔按键列表：`C,ENTER,SPACE,DOWN,67`（M2-a 起） |
| `--input-delay MS` | 1500 | 截图后、注入前的等待（等首帧/loading 结束） |
| `--input-settle MS` | 1200 | 注入后、注入后截图前的等待 |
| `--input-hold MS` | 60 | 每个键按下→抬起间隔 |
| `--input-gap MS` | 250 | 相邻按键间隔 |
| `--input-region T,B` | 70,950 | 像素 diff 只统计的游戏区 y 范围（相对窗口图像） |
| `--input-steps SPEC` | 关 | 多步注入（P1-a 起）：`;` 分隔的 `click:X,Y` / `key:LIST` / `wait:MS` / `capture:NAME` |
| `--input-steps-file FILE` | 关 | 同上，从 JSON 数组文件读取（`--input-steps <文件路径>` 等价） |

输入注入的原理、实测对比（鼠标 SendInput 有效 / 键盘 PostMessage 有效 / 键盘 SendInput 无效）、失败模式与证据见 `docs/environment/citron-harness-input.md`。

多步注入语法、JSON 字段、K2NX 引导实验记录（P1-a）与相关失败模式见 §14。

环境变量（可选）：`CITRON_EXE`、`CITRON_USER_DIR`、`CITRON_SD`、`CITRON_HARNESS_OUT`、`POWERSHELL`。

## 5. 输出 JSON 字段

```json
{"nro":"...","game_type":"nro","game_path":"...","stage_path":"...","status":"loaded","window_title":"...","screenshot":"...","log_path":"...","boot_line":"...","run_dir":"...","nro_staged":"...","citron_exe":"...","citron_build":"...","expected_title":"...","signals":{"title_match":true,"boot_line":true,"app_output":true,"app_output_source":"app_log_regex"},"screenshot_info":{"method":"printwindow","bytes":153797,"nonblack_ratio":0.7932},"elapsed_s":14,"pid":12345,"error":"","admin_elevated_shell":true,"killed":true}
```

| 字段 | 说明 |
| --- | --- |
| `status` | `loaded` / `timeout` / `fail` |
| `game_type` | `nro` / `nsp` / `nsz` / `xci` / `xcz` / `unknown`（按扩展名识别；M3-b） |
| `game_path` | 输入游戏文件的绝对路径（`--nro`/`--game` 解析后） |
| `stage_path` | 复制进虚拟 SD 后的绝对路径；旧字段 `nro` / `nro_staged` 仍保留，分别等于 `game_path` / `stage_path`（向后兼容） |
| `boot_line` | 命中的 Citron 日志行（一般为 `BootGame: Booting game: <TID> | <name> (64-bit)`） |
| `window_title` | 取证时窗口标题（应含 `citron Nightly | <build> | <name> (64-bit) | <GPU>`） |
| `screenshot` | 截图绝对路径；失败为空串 |
| `log_path` | 归档的 Citron 日志副本路径 |
| `signals.title_match/boot_line/app_output` | 三条成功信号（见 §6） |
| `signals.app_output_source` | `app_log_regex` / `expected_file` / `screenshot_nonblack` |
| `screenshot_info.method` | `printwindow` 或 `copyfromscreen` |
| `screenshot_info.nonblack_ratio` | 采样非黑像素比例（用于判定「画面有内容」） |
| `error` | 失败/超时的原因码 + 详情（见 §7） |
| `admin_elevated_shell` | 是否检测到提权 shell（提权时脚本走 runas 降权启动） |
| `killed` | 是否已停掉本次启动的 Citron |

注意：参数/环境校验阶段的 `fail`（如 NRO 不存在）发生在提权检测之前，此 JSON 里 `admin_elevated_shell` 为 false、其余字段为空串——这是预期行为，不是检测失败。

带 `--input-*` 时 JSON 额外含 `input{injected,key_method,keys_requested,keys_sent,focus_ok,clicks,screenshot_before,screenshot_after,diff_ratio,nonblack_before,nonblack_after,region,error}`，运行目录另存 `window-before-input.png` / `window-after-input.png`；字段含义见 `docs/environment/citron-harness-input.md` §4。

带 `--input-steps` 时 `input` 另含 `steps[]{index,action,argument,status,detail,screenshot,elapsed_ms}`、`steps_failed`、`steps_diff_ratio`、`steps_final`、`steps_error`；运行目录另存 `input-steps.tsv`、`window-steps-before.png`、`window-steps-final.png` 及每步 `step-NN-<name>.png`（见 §14）。

## 6. 三条成功信号（判定口径）

1. **窗口标题匹配**：Citron 窗口标题包含 `--expect-title`（默认文件名 stem，大小写不敏感）。真机上 Citron 标题形如 `citron Nightly | 0237a9b88 | brewser (64-bit) | NVIDIA`。**注意**：NRO 的窗口名来自 NRO 本身，而 NSP/XCI 的窗口名来自 NACP 应用名，常不等于文件名 stem → 跑 NSP 时要么显式传 `--expect-title`，要么接受 `title_match=false`、只看 boot 行与截图。
2. **Boot 行**：Citron 日志（本次运行段）出现 `BootGame: Booting game:`（或退一步的 `BootGame: citron starting` / `Loading <name> (...)`）。`status=loaded` 只要求这一条。
3. **应用自输出**：三选一——`--app-log-regex` 命中日志；`--expect-file` 的文件 mtime ≥ 启动时刻；截图非黑像素比 ≥ 1%（`screenshot_nonblack`）。给 m1 类应用建议同时传 `--app-log-regex` 与 `--expect-file`，截图只作兜底。

推荐 M1-d 验收：`status=loaded` + `signals.title_match=true` + `signals.app_output=true`。

若用了输入注入（M2-a），额外要求 `input.injected=true` 且注入前后截图出现**语义可辨的状态变化**（`input.diff_ratio` 仅作参考，必须人工/pixel 复核 after 图）；`input.diff_ratio` 大不等于应用接受了输入。

## 7. 失败排查表

| 现象 / JSON `error` | 含义 | 排查 |
| --- | --- | --- |
| `game_not_found` | 路径不存在 | 检查 `--nro` / `--game`；路径可相对当前目录 |
| `argument_conflict` | 同时给了不同的 `--nro` 与 `--game` | 只传一个；两者等价 |
| `not_booted` | 非 NRO 文件（NSP/XCI 等）Citron 进程活着但超时内没有 `Booting game` 行 | 先确认文件是完整可加载应用（NSP 需正确 ticket/title key）；日志若出现 `Failed to load`/`Invalid NCA` 属文件/密钥问题；可改走「安装到 NAND 再启动」（见 §13） |
| `load_failed` | Citron 明确报 `LoadROM: Failed to load ROM!`（如 Error 32 / 0007-0020），界面回落游戏列表 | 文件不是可运行的应用包（例：只有 main+main.npdm 的 homebrew 形态 PFS0）或 NCA/密钥不匹配；这是**应用包本身的问题**，不是脚本误判（脚本对非 NRO 类型要求特定 `Booting game` 行，不再把 `citron starting` 当成功） |
| `citron_exe_missing` | 找不到 citron.exe | 传 `--citron-exe` 或先解压 Citron 到 `workspaces/<x>/citron/` |
| `citron_user_dir_missing` | 用户目录不存在 | 先手动启动一次 Citron；或 `CITRON_USER_DIR` 指向已有目录；便携模式（exe 同级有 `user/`）会自动识别 |
| `keys_missing` | `<user dir>/keys/prod.keys` 不存在/为空 | 用户自备 keys 放到该路径（脚本不会也不应复制密钥） |
| `sd_missing` | 虚拟 SD 目录不存在 | 确认 `use_virtual_sd=true` 或 `--sd` 指到正确目录 |
| `citron_already_running` | 已有 citron 进程 | 先关掉；或确实要串跑时加 `--allow-existing`（脚本只杀本次新增 pid，但同实例串台风险自负） |
| `process_exited_before_boot` | 进程起来又退出、没有 Boot 行 | 看 `citron_log.txt`/事件；常见为文件头损坏、NCA/密钥问题或 HLE 异常 |
| `load_stalled_after_loading` | 进程活着但超时内没有 Boot 行 | 提高 `--timeout`（大应用首包慢）；仍失败则看日志最后 20 行 |
| `boot_timeout_no_evidence` | 超时内没观察到 citron 进程 | 提权/UEV 相关：确认脚本以普通权限或已正确降权启动；看 wrapper 是否被拦 |
| `hle_exception` | 日志出现 Unhandled exception 等 | 记录日志并上报引擎问题；不是脚本误判 |
| 窗口标题是管理员相关弹窗 | 以管理员权限启动 Citron | 脚本在提权 shell 下会用 `runas /trustlevel:0x20000` 降权；若仍弹窗，手动以普通权限运行 |

截图方法说明：优先 `PrintWindow(PW_RENDERFULLCONTENT=2)`（可截被遮挡窗口）；若窗口最小化会先 `ShowWindow(SW_RESTORE)`；若 PrintWindow 失败或非黑像素比 < 2%，回落 `SetForegroundWindow + CopyFromScreen`（会短暂抢前台，脚本会记录 method）。

## 8. Citron 目录布局与 profile 事实（本机实测）

```
%APPDATA%\citron\                 # 非便携模式的用户目录（exe 同级没有 user/ 时）
  config\qt-config.ini            # 全局配置（本机 55,991 B / 1,372 行）
  config\custom\<TID>.ini         # Citron 按 title/NRO 自动生成的 per-game 覆盖（use_global=true）
  keys\{prod.keys,title.keys}     # 用户自备，不入库
  log\citron_log.txt              # dev build 常开日志（另有 .old.txt 轮转）
  sdmc\                           # 虚拟 SD 根（use_virtual_sd=true）
    switch\...
```

关键配置（本机实测值，一般无需改）：`use_virtual_sd=true`、`log_filter="*:Info"`、`enable_fs_access_log=false`、`use_debug_asserts=false`、`backend=0`、`use_multi_core=true`、`enable_telemetry=false`、`use_docked_mode`（默认 docked）、`enable_raw_input=false`、`enable_joycon_driver=true`、`enable_procon_driver=false`。

- 便携模式：若 `citron.exe` 同级存在 `user/` 目录，Citron 使用它作为用户目录（源码 `src/common/fs/path_util.cpp`）；本机 Citron 目录没有 `user/`，所以走 `%APPDATA%\citron`。脚本按同一顺序解析。
- 本机 Citron 没有固件镜像：日志 `Installed firmware: No firmware available`，使用硬编码 22.0.0 版本号。这会影响部分系统服务，但对 homebrew 冒烟通常无害；需要真实固件时另行准备（不与本工具耦合）。
- 日志行格式：`[   1.957278] Frontend <Info> citron\main.cpp:2475:BootGame: Booting game: ...`。脚本以最后一次 `citron Version:` 行为本次运行起点切片。

## 9. 合规

- keys 是用户自备的受版权材料：本工具只做存在性检查，不读内容、不打印、不复制、不入库（`.gitignore` 已忽略 `*.keys`/`prod.keys`/`title.keys`）。
- Citron Neo 为外部 GPL-3.0-or-later 工具，仅作为本地运行环境使用；本仓库不分发其二进制，下载动作由使用者按 release 资产自行完成。
- 被测 NRO 由我们自己的里程碑构建产出；不得用本工具去跑商业游戏数据（本工具也不做 ROM 处理）。
- 运行产物全部落在 `workspaces/`（git 忽略），不进入版本库。

## 10. 已知限制

1. 仅验证 Windows + Citron nightly `0237a9b88`（msvc 构建）；其他 Citron 版本/平台未验证。
2. 截图是「窗口」级画面，不是 WebGL/Canvas 像素级比对；跨机器/驱动可能有差异。
3. `nonblack_ratio ≥ 1%` 只是「有内容」的粗判，不能证明画面正确。
4. 音频、输入（手柄/触摸）、联网（socket HLE 多为 STUB）不在本脚本判定范围。
5. 无固件 + 无兼容性列表：部分应用行为与真机不同；本工具目标是「装得上、跑起来、有输出」，不是兼容性认证。
6. 脚本默认只杀本次新增 pid；若 Citron 自己 fork/复用进程导致 pid 不新增，可能漏杀（此时用 `--allow-existing` 前先手动清理）。
7. 超时判断依赖 2 s 轮询粒度，$`--timeout 1` 这类极小值会得到 `load_stalled_after_loading`（进程已起、未见 Boot 行），属预期。

## 11. 自测证据（2026-10-30）

成功用例（`brewser.nro`，76,546,123 B，sha256 `8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13`）：

```
status=loaded, elapsed_s=14, killed=true
window_title = citron Nightly | 0237a9b88 | brewser (64-bit) | NVIDIA
boot_line    = [   1.957278] Frontend <Info> citron\main.cpp:2475:BootGame: Booting game: 01F5905036D20000 | brewser (64-bit) |
citron_build = [   0.725264] Frontend <Info> citron\main.cpp:411:GMainWindow: citron Version: citron Development Build | main-0237a9b88
signals      = title_match=true boot_line=true app_output=true (app_log_regex)
screenshot   = printwindow, 154,618 B, nonblack_ratio=0.7921
```

截图显示 Brewser 的 `brewser://probe/` 页面（`GALNX WEB PROBE 01`、`STATIC DOM TEXT OK`、`JS: INLINE OK`、`TICKS 24`、`CANVAS 2D OK frame 331`、`localStorage:1 | WebGL:OK OpenGL ES 3.2 Mesa 20.1.0-rc3`），证明截图为真实应用画面而非空窗口。

失败/边界用例（全部通过）：

| 用例 | 退出码 | 结果 |
| --- | --- | --- |
| `--nro` 指向不存在文件 | 2 | `status=fail`, `error=nro_not_found`，stderr 打印 FAIL，JSON 正常输出 |
| `--help` | 0 | 打印帮助，不启动任何进程 |
| `--timeout 1`（brewser） | 1 | `status=timeout`, `error=load_stalled_after_loading`，`killed=true`，结束后 `Get-Process citron` 计数为 0 |

证据文件（`workspaces/citron-harness/evidence/`）：

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `selftest-brewser-window.png` | 154,618 | `a9304273ece62ab46a1cdc3a4a788acb413a307e783c3f0135a5fc1b3cb19c6b` |
| `selftest-brewser-result.json` | 1,337 | `7958085ec9798728676a73ff66211f5e7ee5b118da9036761184b4d54538cd82` |
| `selftest-brewser-run.log` | 952 | `3860d81cf15ba37a0b7c576dcae5d986cac3075a16a24ed6b665293904379e84` |
| `selftest-brewser-citron-log-slice.txt` | 78,475 | `a6f9738e87301520bea96024225fdf16de1f5f39f1019321136b8c31db41cf38` |

运行归档（`workspaces/citron-harness/runs/`）：`20261030-002029-brewser`（首跑，暴露 title 解析 bug）、`20261030-002226-brewser`（修复后成功）、`20261030-002257-brewser`（timeout 用例）。

## 12. 给 M1-d 的使用建议

```bash
bash scripts/citron_run.sh --nro <m1-sdl2.nro 路径> \
  --timeout 60 --settle 8 \
  --expect-title m1-sdl2 \
  --app-log-regex 'Booting game:' \
  --expect-file switch/m1-sdl2/ready.txt   # 若应用会写自己的标记文件
```

- 验收看 `status`、`signals.*`、`screenshot` 三处；把 `result.json` 与 `window.png` 附到里程碑记录即可。
- 若失败，先看 `run.log` 的 `error` 字段，再按 §7 排查；`citron_log_slice.txt` 是本次运行的完整 Citron 日志段，可直接归档上报。
- 不要提交 `workspaces/` 下的任何产物；本工具与文档分别位于 `scripts/`、`docs/environment/`。

### 12.1 输入注入示例（M2-a）

```bash
# 点击 KAG3 标题菜单的「What is KAG?」链接（window.png 像素坐标 861,589），再按 C（=Switch A）推进
bash scripts/citron_run.sh --nro E:/galnx-build/m1-krkrsdl2/build5/krkrsdl2.nro \
  --timeout 120 --settle 20 --expect-title Kirikiri --app-log-regex 'Booting game:' \
  --input-click 861,589 --input-keys C --input-delay 2500 --input-settle 3000
```

实测结果：`status=loaded`、`input.clicks=1`、`input.keys_sent=1`、`input.diff_ratio=0.494313`（仅游戏区），
标题菜单 → KAG3 正文页；证据见 `docs/milestones/evidence/M2a-*`，原理与限制见 `docs/environment/citron-harness-input.md`。

### 12.2 NSP 直接引导示例（M3-b）

```bash
# 自包含 NSP：Citron 直接加载，无需安装到 NAND
bash scripts/citron_run.sh --game /e/galnx-build/m3-tools/out/m0-real-build1.nsp \
  --timeout 120 --settle 20 --expect-title m0-hello --app-log-regex 'Booting game:'
```

实测（2026-10-30）：`status=loaded`、`elapsed_s=27`、`window_title="citron Nightly | 0237a9b88 | m0-hello (64-bit) | 1.0.0 | NVIDIA"`、
`boot_line="[   1.766935] Frontend <Info> citron\main.cpp:2475:BootGame: Booting game: 0100000000001000 | m0-hello (64-bit) | 1.0.0"`；
截图显示应用自身的 "Hello World!" 画面，`nonblack_ratio=0.1797`（黑底白字，比例低属正常，不是失败）。
注意 `--expect-title` 必须给 NACP 应用名（本例 `m0-hello`）；默认的 stem（`m0-real-build1`）不匹配，会得到 `title_match=false`。

## 13. NSP / XCI 直接引导（M3-b，模拟器侧验收）

### 13.1 结论

- Citron nightly `main-0237a9b88` **支持把 `.nsp` 当普通游戏文件直接加载**（与 `.nro` 相同的 argv 路径 / `-g` 路径），无需先 Install files to NAND。
- 实测对象 `m0-real-build1.nsp`（309,464 B，自包含：program NCA 187,392 B + control NCA 117,760 B + cnmt.nca 4,096 B，由 M3-a 打包链产出）：
  - `status=loaded`，`elapsed_s=27`；两次独立 run 均成功（2026-10-30 02:16:47 与 02:17:46，见 §13.2 证据）。
  - `window_title="citron Nightly | 0237a9b88 | m0-hello (64-bit) | 1.0.0 | NVIDIA"`；`boot_line` 含 `Booting game: 0100000000001000 | m0-hello (64-bit) | 1.0.0`。
  - 截图实际画面为 `Hello World!`（应用自渲染文本），`nonblack_ratio=0.1797`（黑底白字）。
- 机制：Citron 是 yuzu 血统，`src/citron/main.cpp` 中 `argv.size()==2` 且非 `-` 开头时把参数当游戏路径，GameLoader 按 NSP 解析；本机全程未使用 NAND 安装路径、未改用户配置、未读/打印密钥内容。
- 复现性：`m0-real-build2.nsp`（同内容、不同 sha256，RSA-PSS 随机盐）同样 `status=loaded`（elapsed 27s，同一 boot 行、同一画面）。

### 13.2 证据（`docs/milestones/evidence/`）

| 文件 | sha256 | 内容 |
| --- | --- | --- |
| `M3b-m0-nsp-boot-window.png` | `9a7e729e51341e21870174831ae66b0dee605d28861cce8e2fdd494c8034bc92` | 引导成功截图（1728x1016，73,300 B，画面 "Hello World!"） |
| `M3b-m0-nsp-result.json` | `bf0d97ab9f59faa233d57697c7e1502157730d061bc4e7372e6386cbcd85e11f` | 正式 run 的 result.json（`status=loaded`、`title_match=true`、`game_type=nsp`） |
| `M3b-m0-nsp-run.log` | `f83bdee1abe4d1f9a09f7815cbfecad22250de329a6ba0d1adda8dfaf4edc1e8` | harness run.log（启动模式/日志路径/清理记录） |
| `M3b-m0-nsp-citron-log-slice.txt` | `f1d7c14ed0bb40a2b49c132408844be2ceb94966135fe4744c069d292340d46c` | Citron 日志切片（含 `Loading m0-hello ...` / `Booting game: ...`） |
| `M3b-m0-nsp-firstboot-result.json` | `bfed6420ef71d3925fb74d55fd50465d2d20e144751d6bf70ebafd173c11ed57` | 首跑（未传 `--expect-title` → `title_match=false`，属预期） |
| `M3b-nro-regression-result.json` | `7d14895ded66f4b9f5b9c90e8d139c18f89ebab81c1e3470449a3bdd68bb95ea` | `--game` 跑 NRO（KAG3）回归，含 `--input-click`，无回归 |
| `M3b-hbl-result-citron-already-running.json` | `b18907bc3f0db17673d3f31abb78ecfc571aa3a624ab61c8ae27d73024123a5d` | 被占用时 `status=fail`/`error=citron_already_running`，失败语义样例 |
| `M3b-m0-build2-result.json` | `866dc63e27cff8055ac35b5d9792c73adb112300c5fa94401f4ed5e1fdeccc86` | 第二次构建（sha256 不同）同样 `loaded`，复现性证据（elapsed 27s） |
| `M3b-m0-build2-window.png` | `3dfc1125a2cf7eaefb8a5a93078adc18b9fc1971dbbb61212067358eae5ac180` | build2 画面（73,289 B，同为 Hello World!） |
| `M3b-m0-nsp-posthardening-result.json` | `f6b475f1097c171043c0df7cc7559c7764138251b368fa27627f511e5b23700c` | 判定口径加固后的回归 run（仍 `status=loaded`、title/boot/app_output 三信号 true） |
| `M3b-m0-nsp-posthardening-window.png` | `9a7e729e51341e21870174831ae66b0dee605d28861cce8e2fdd494c8034bc92` | 与正式 run 相同截图（sha256 一致，73,300 B） |
| `M3b-hbl-control-prehardening-result.json` | `76cfb7b296c0629131bdeb6803670e4ceee018f7a55d4ef0b76a177960e4a5d4` | 加固前 hbl.nsp 被误判 `status=loaded`（false positive 证据，保留说明加固动机） |
| `M3b-hbl-control-prehardening-window.png` | `8cdbdffc7aa949c94dc62b5f6ec7b8305e34283821b3442ed846cc1dfc744930` | 加固前截图（实际是 Citron 游戏列表 UI，被当成「应用输出」） |
| `M3b-hbl-control-load-failed-result.json` | `4954c8de1fad4b90bd9614e082d4b022e22ba4fa66685981cf320e761b7393cb` | 加固后正确判定：`status=fail`、`error=load_failed: ... LoadROM: Failed to load ROM! (0007-0020)`，elapsed 7s |
| `M3b-hbl-control-load-failed-window.png` | `8cdbdffc7aa949c94dc62b5f6ec7b8305e34283821b3442ed846cc1dfc744930` | 同加固前截图（Citron 游戏列表，非应用画面） |

另：`M3b-artifacts-sha256.txt` 为上述证据的 sha256 + 字节数清单（含 `M3b-nro-regression-result.json`）。

### 13.3 机制与注意事项

- **窗口名来源不同**：NSP/XCI 的窗口标题取自 NACP 应用名（本例 `m0-hello`），不是文件名 stem。跑 NSP 必须显式 `--expect-title <NACP 名>`，否则 `title_match=false`（首跑即此情况）。
- **密钥**：自包含 NSP 直接加载仍需正确 keyset（`<user dir>/keys/prod.keys`）解 NCA。脚本只检查存在性，不读取/不打印；若 NCA 加密超出 keyset 支持，会表现为 `not_booted` 或 `process_exited_before_boot`，需查日志。
- **单实例**：跑前 `tasklist | findstr /i citron`；被占用时 harness 默认 `fail`（`error=citron_already_running`），不要用 `--allow-existing` 抢占（Team 内其它成员也会用 Citron）。
- **不写 NAND**：直接加载 NSP 不安装到 NAND；「安装到 NAND 再启动」路径依赖 Citron GUI（Install files to NAND），M3-b 未做。
- `.xci/.nsz/.xcz` 已实现类型识别与 stage，但**未实测**（无对象且涉及商业内容合规，不做）。

### 13.4 限制与未验证

1. 只验证了 1 个自包含 NSP（m0 hello，非交互、单帧画面）；`--input-*` 未用于 NSP（应用无输入需求）。
2. `hbl.nsp` 对照组已跑完：加固前误判 loaded、加固后正确 `load_failed`（两版 result 均归档）。
3. 真实商业游戏 NSP 不做（合规）；xci/nsz/xcz 未测。
4. 结论标 **preliminary**：待 M3-a（打包链）报告出来后，再由里程碑记录统一写「验收」措辞（本轮 E1+E2 已足够支撑「模拟器验收通过（预）」）。

时间窗说明：M3-b 取证期间 audit-engines 的 M2-c 也周期性独占 Citron（单实例）；02:16:47 首跑与 M2-c 有一次时间重叠但仍成功，02:17:46 为独立无冲突 run；此后按 Lead 约定在 02:24 后继续。

### 13.5 判定口径加固（2026-10-30 02:26 起）

发现并修复了一个会污染 M3 验收的 false positive：

- **现象**：hbl.nsp（非标准 PFS0）加载失败时 Citron 仍会打 `BootGame: citron starting...`，且界面停在 Citron 自己的游戏列表（非黑像素比 0.9997）；旧逻辑把它当 boot 行 + `screenshot_nonblack` 应用输出 → 误报 `status=loaded`。
- **修复**（`scripts/citron_run.sh`，2026-10-30 02:26，39,030 B / 876 行）：① 非 `nro` 类型不再接受 `BootGame: citron starting` / `Loading ...` 这两个宽松 fallback，必须有 `BootGame: Booting game:` 才算 boot；② 日志出现 `Failed to load ROM|LoadROM: Failed` 时立即停止轮询并给出 `status=fail` / `error=load_failed: <行>`；③ `screenshot_nonblack` 只有在已命中 boot 行时才可作为「应用自输出」信号。
- **回归**：m0-real-build1.nsp 仍 `status=loaded`（elapsed 27s，三信号 true）；hbl.nsp 变为 `status=fail`、`error=load_failed: ... (0007-0020)`、elapsed 7s。加固前后两份 result 都归档为证据。

## 14. 多步输入自动化（`--input-steps`）与 K2NX 首轮引导（P1-a，2026-10-30）

> 本节记录 P1-a（首款垂直试点：PC KiriKiri2 游戏《晴霁之后定是菜花盛开的好天气》）用 harness 做的自动引导实验。
> 结论是**受阻于引擎兼容性缺口**（未到标题画面），不是 harness 能力不足；`--input-steps` 本身已通过 KAG3 回归验证。

### 14.1 语法与文件

- 分号分隔：`--input-steps 'wait:2000;click:1233,406;wait:1500;key:C;capture:after'`
- 每步四种类型：
  - `click:X,Y`：在 `window.png` 像素坐标点击（先抢焦点，走 SendInput mouse_event；见 `citron-harness-input.md`）
  - `key:LIST`：逗号分隔键名/十进制 VK（`C`、`ENTER`、`DOWN`、`67`…），走 PostMessage 到 Citron 主窗
  - `wait:MS`：等待毫秒
  - `capture:NAME`：额外截图 `step-<NN>-<NAME>.png`（NN 为从 1 开始的两步计数）
- JSON 数组文件：`--input-steps-file steps.json`，元素形如 `{"action":"click","x":1233,"y":406}`、`{"action":"wait","ms":1500}`、`{"action":"key","keys":"DOWN,C"}`、`{"action":"capture","name":"after"}`；也可直接 `--input-steps <文件路径>`（脚本识别已存在文件）。
- 执行顺序：`--input-click`/`--input-keys`（旧参数，先执行）→ `--input-steps` 逐步执行 → 抓 `window-steps-final.png` → 与 `window-steps-before.png` 做像素 diff（`steps_diff_ratio`，区域由 `--input-region` 控制）。
- 每步结果写 `$RUN_DIR/input-steps.tsv`（7 列：index、kind、label、status、detail、shot、elapsed_ms）；单步失败不中断，继续后续步骤。

> 坑：在 bash 命令行里传 `--input-steps @/abs/steps.json` 时，`@` 可能被外层 shell/工装展开成一串字符串（本机 `ops_bash` 实测），脚本收到的就不是路径。用 `--input-steps-file /abs/steps.json` 或纯路径最稳。

### 14.2 输出字段（steps 部分）

`input` 对象新增：`steps[]{index,action,argument,status,detail,screenshot,elapsed_ms}`、`steps_failed`、`steps_diff_ratio`、`steps_final`、`steps_error`；`steps_error` 非空时表示 steps 整体未跑起来（例如无窗口/无 boot 行）。

### 14.3 引导实验记录（E1 日志 / E2 截图）

对象：`Kirikiroid2-NX-v1.0.1.nro`（42,338,934 B，sha256 `ce3c0169610eb2d65f332e26a16d14c283f9dcf39634dc4f46c2c004860919b8`）；Citron nightly `main-0237a9b88`；游戏目录已复制到虚拟 SD `sdmc:/kirikiroid/haruno/`（`plugin/ savedata/ savedata_chs/ 补丁/ data.xm3 data.xp3 data.xp3.sig dummy.png extra_chs.xp3 haruno.cf`）。

| 步骤 | 证据 | 结果 |
| --- | --- | --- |
| K2NX 启动，进入自带文件选择器（picker） | `P1a-01-k2nx-picker-root.png` | picker 列出虚拟 SD 根 |
| 进入 `/kirikiri` → `haruno` | `P1a-02-k2nx-picker-haruno.png` | 目录 10 项；`data.xp3` 行中心约 image y=641 |
| 点击 `data.xp3` | `P1a-03-k2nx-input-overlay-blocking.png` | 弹出全屏「输入示意图」模态 overlay（右上角 X），期间引擎阻塞约 80 s |
| 点击右上 X 关闭 overlay | `P1a-k2s_log-run5-repro.txt` | 游戏真正启动：加载 `startup.tjs`、`haruno.cf`、全部 XP3 与插件 |
| 引擎读完全部数据 | 同上 | `Total 19183 file(s) found, 19171 file(s) activated. (299ms)`（各 XP3 计数一致） |
| 执行游戏脚本 | `P1a-04-k2nx-tjs-exception.png`、`P1a-05-k2nx-repro-exception-console.png` | 在 `mainwindow.tjs(990)` 抛 TJS 异常，**未到标题画面** |

关键日志原文（`P1a-k2s_log-run5-repro.txt`，4,604 B，sha256 `891e90ca1bab38afdf6bf9c9e040128d3a68a1b3bf161af40e4fd36c108fb945`；原文 `occured` 拼写照录）：

```
06:03:27 (info) Loading startup script : file://./kirikiri/haruno/data.xp3>startup.tjs
06:03:28 ==== An exception occured at mainwindow.tjs(990)[(function) SetExEvent], VM ip = 15 ====
06:03:28 #(990) 		this.registerExEvent();
06:03:28 00000015 calld %0, %-1.*2()	// *2 = (string)"registerExEvent"
```

判断：K2NX 的 XP3/插件/TJS 加载链路是通的（19171 个文件激活、插件 `csvParser/extrans/fstat/layerExImage/windowEx/wumsadp/wuvorbis` 全部 Loading 成功），卡在游戏脚本调用的 TJS 原生成员 `registerExEvent` 不存在。

**`P1a-03` 的 overlay 是什么（Lead 问）**：点击 `data.xp3` 后、引擎真正启动前，K2NX 在游戏窗口内画出一页**全屏「控制/输入示意图」模态 overlay**——图标依次是触摸点按、上下箭头、鼠标、拖拽、框选、指针、D-pad，底部一块蓝色 `ABC` 方块，右上角一个 `X`。观察：overlay 期间 `k2s_log` 停在读 XP3 前约 80 s 无推进；点击右上 X（image 1546,180）后引擎日志立即继续（`Loading startup script ...`）。所以它是**吞掉自动流程的模态遮罩**，不是 picker（picker 此时已关闭），也不是 TJS 异常页；后续自动验证必须在 steps 里显式点掉它，否则所有点击都落在 overlay 上。

上游对照（E4 源码，仓库 `Erige005/Kirikiroid2-NX`）：

- v1.0.1 commit（2026-10-18T17:00:15Z）标题为「v1.0.1: windowEx plugin, hide modal windows when closed (fixes #1)」；`src/plugins/windowEx/main.cpp` 注释原文：`games calling these methods (e.g. Window.registerExEvent() in "Ninki Seiyuu") don't stop with "Member ... does not exist"`，并注册 `Method(TJS_W("registerExEvent"), &Class::registerExEvent);`（空实现）。
- 但发布资产 NRO 的编译时间戳是 `Oct 18 2026 23:24:50`（`k2s_log` 第 1 行、`k2s_boot.txt` 第 0 行），且 NRO 明文里 grep 不到 `registerExEvent`；插件模块可能以编译/压缩形式嵌入，**不能据此断定 NRO 未含修复**。
- 另一种解释：本游戏在非 `Window` 对象上调用（K2NX 相较 krkr2 明确省略了 `Pad.registerExEvent`），或兼容层未覆盖该调用点。需 P1-b 提取 `data.xp3` 内 `mainwindow.tjs` 第 990 行上下文对照。

**Lead 源码级定位（2026-10-30 06:05，待重建 NRO 验证，E4-推理）**：K2NX 把游戏 `plugin/*.tpm` 交给 `TVPLoadInternalPlugin` 时，内置模块是以 `*.dll` 名注册的（`windowEx.dll` 等），按精确名查表永不命中 → 内置 windowEx 实际上从未注册 → `this.registerExEvent()` 抛「成员不存在」。Lead 已打「`.tpm`→`.dll` 别名 + 日志」补丁并在本地重建 NRO；重建产物在 Citron 里验证时需 grep `k2s_log.txt`：`[GalNX] internal plugin loaded via .tpm alias`、`Loading startup script`、`An exception occured`。若命中别名日志且异常消失，则本条根因成立。

复现命令（本机，Citron 单实例）：

```bash
bash scripts/citron_run.sh --game workspaces/pilot-01/Kirikiroid2-NX-v1.0.1.nro \
  --timeout 180 --settle 20 --expect-title Kirikiroid --input-delay 2500 \
  --input-steps 'wait:2500;capture:picker;click:1233,641;wait:5000;capture:overlay;click:1546,180;wait:2500;capture:postx;wait:26000;capture:crash'
```

该命令实测：`status=loaded`、`steps 10/10 ok`、`steps_diff_ratio=0.815152`、exit 0（run 目录 `workspaces/citron-harness/runs/20261030-060245-Kirikiroid2-NX-v1.0.1/`）。

### 14.3.1 重建 NRO 验证的 harness 用法（备用，待 Lead 提供重建产物）

- 前置：`sdmc:/switch/kirikiroid2/autostart.txt` 内容 `/kirikiri/haruno`（K2NX 会跳过 picker 直接进游戏；该文件由 Lead/P1-b 侧放置）。
- 建议命令：

```bash
bash scripts/citron_run.sh --game <rebuilt-K2NX.nro> --timeout 240 --settle 25 \
  --expect-title Kirikiroid --input-delay 3000 \
  --input-steps 'wait:8000;capture:boot;click:864,508;wait:2500;capture:adv1;key:C;wait:2500;capture:adv2'
```

- **首帧门控**：Citron 的 `keyPressEvent` 在 `first_frame` 之前直接 `event->ignore()`（见 `citron-harness-input.md`），所以按键类步骤必须排在 boot 行 + `--settle` + `--input-delay` 之后；上例 settle 25 s + delay 3 s + wait 8 s 足够。
- **到标题的等待**：K2NX 读 19171 个文件约 0.3 s，脚本加载 + 首帧预计 5–15 s；先 `wait:8000`，若截图仍黑/加载页就加到 15000。
- **日志取证**：`k2s_log.txt` 每次启动**覆盖**（仅保留一版 `k2s_log.prev.txt`），必须在 run 结束后立刻复制：

```bash
cp "$HOME/AppData/Roaming/citron/sdmc/switch/kirikiroid2/k2s_log.txt" docs/milestones/evidence/<tag>-k2s_log.txt
cp "$HOME/AppData/Roaming/citron/sdmc/switch/kirikiroid2/k2s_boot.txt" docs/milestones/evidence/<tag>-k2s_boot.txt
cp "$HOME/AppData/Roaming/citron/sdmc/switch/kirikiroid2/k2s_crash.txt" docs/milestones/evidence/ 2>/dev/null || true
```

- **判定**：标题/正文画面出现在截图里，或「`An exception occured` 消失 + 点击后像素有变化」；同时核对 `k2s_log` 中的别名日志行。

### 14.3.2 NSP 形态冒烟（2026-10-30 06:10，P1-a 补充）

审计包侧（task-35）用「预编译 NRO → 合成 ELF → elf2nso → NSP（romfs 解包重打包）」做出了 K2NX 的 NSP 形态，本轮验证「NRO→NSP 链路对 K2NX 是否成立」。

- 产物：`/e/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b1.nsp`，**22,587,096 B，sha256 `216efe02bda60587ed6a7c39a395e7c4f593f57833f52e113da7df7459cd24ba`**（本会话实测与审计包侧一致）。
- 命令：`bash scripts/citron_run.sh --game /e/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b1.nsp --timeout 180 --settle 20 --expect-title Kirikiroid --input-delay 3000 --input-steps 'wait:4000;capture:picker'`。
- 结果：exit 0、**status=loaded**、elapsed_s=34、pid 38304、`game_type=nsp`；窗口标题 `citron Nightly | 0237a9b88 | Kirikiroid2-NX (64-bit) | 1.0.1 | NVIDIA`；boot_line `[   3.935795] Frontend <Info> citron\main.cpp:2475:BootGame: Booting game: 010047410000B0B1 | Kirikiroid2-NX (64-bit) | 1.0.1`；三信号全 true（`app_output_source=screenshot_nonblack`）；截图 PrintWindow 197,824 B、nonblack 0.9018；`killed=true`。
- 画面：K2NX 的**文件选择器 UI 完整渲染**（左栏预览 `/kirikiri/haruno/data.xp3`、右栏 haruno 目录 10 项），且 recentpath 记忆生效（直接回到上次的 haruno）。说明 NSP 的 romfs（picker UI 资源）被正确加载、NSP 可被 Citron 以 `-g` 路径直接引导。
- **NACP 生效证据**：窗口标题与 boot 行都多了 `| 1.0.1`（同一 NRO 形态下标题只有 `Kirikiroid2-NX (64-bit)`，无版本）→ NSP 打包把 NACP 的 DisplayVersion 带进来了。
- **差异观察（未定因，不阻塞结论）**：
  - NSP 形态下 picker 把中文目录名 `补丁` 渲染成 `口口`（NRO 形态同一目录名渲染正常）→ 怀疑重打包后的 romfs 少了 picker 使用的 CJK 字体资源，或 NSP romfs 布局与 NRO 内嵌 romfs 不同；需审计包侧比对 NSP/NRO 的 romfs 文件清单（`nstool` 需 keyset，归 task-35）。
  - `k2s_boot.txt` 显示 `static-init start (image base 0x8000000, ...)`，NRO 形态为 `0x80000000` → 合成 ELF 的加载基址不同（仍能正常跑，记录备查）。
  - boot 行晚约 2 s（3.94 s vs NRO 1.96 s），符合 NSP/NCA 多一层解包的开销。
- 证据（`docs/milestones/evidence/`）：`P1a-k2nx-nsp-result.json` 2,587 B sha256 `755d62ad417cd8a6ac3572579703a7013458fbcc854ca281cfe9342675a8cc78`；`P1a-k2nx-nsp-picker.png` 197,824 B sha256 `4b9f5ba18302c1d2c4c6ec419ca215c23a8c7e6e749e67d7edb57dbf01ad8acc`；`P1a-k2nx-nsp-k2s_boot.txt` 217 B `341274bb4a2daaa622477cda33ddec14634bbe296048c13c2a294fc53b8e3afa`；`P1a-k2nx-nsp-k2s_log.txt` 154 B `0e4115a5715ed9bb6d626147f6ebb32d8911163552de23906402dd0c7d27d365`。
- **结论**：NRO→NSP 打包链路对 K2NX **成立**（直接加载 + NACP 生效 + romfs picker 资源可用）；CJK 字体差异待审计包侧确认。

### 14.3.3 CJK 目录名 A/B 对照（NRO 正常 / NSP 显示为豆腐块，2026-10-30 06:16）

用同一份 `sdmc:/kirikiri/haruno/` 内容、同一 harness 参数，分别加载 NRO 形态与 NSP 形态，比较 picker 右栏第 4 行目录名 `补丁`：

| 形态 | 命令要点 | status | 窗口标题 | 该行渲染 | 截图 sha256 |
| --- | --- | --- | --- | --- | --- |
| NRO | `--game workspaces/pilot-01/Kirikiroid2-NX-v1.0.1.nro --input-steps 'wait:4000;capture:picker'` | loaded（29 s, pid 40452） | `... Kirikiroid2-NX (64-bit) \| NVIDIA` | `补丁` 正常（中文可读） | `4cd19f470ef133a2c8b8b078d09ceb9f696d450ccd2a456b7ffc15b967e677fe` |
| NSP | `--game /e/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b1.nsp --input-steps 'wait:4000;capture:picker'` | loaded（34 s, pid 38304） | `... Kirikiroid2-NX (64-bit) \| 1.0.1 \| NVIDIA` | `口口`（两枚豆腐块，字形数=2 与原目录名一致） | `4b9f5ba18302c1d2c4c6ec419ca215c23a8c7e6e749e67d7edb57dbf01ad8acc` |
| NSP（修复版，全量 romfs） | 同 NSP，但用 `Kirikiroid2-NX-fixed-010047410000b0b3.nsp` | loaded（28 s, pid 27708） | `... Kirikiroid2-NX (64-bit) \| 1.0.1 \| NVIDIA` | `补丁` **正常**（关闭 TD 修复后的渲染与 NRO 完全一致） | `78029ba910ecd0b496e16cf2f1edcf9e448f8b667de73e2fa25ae4bb1e20a9b0` |

- 复现性：NRO 形态截图与更早的 `P1a-08-k2nx-picker-after-keys.png` **逐字节相同**（同 sha256），说明该 picker UI 渲染是确定性的，A/B 差异不是帧间噪声。
- 像素量化（Python/Pillow，`|dRGB|sum>72` 计差异像素）：整幅游戏区（y80–960，2 px 采样）diff **6.464%**；右栏各行带 diff **7.75%–22.15%**；`补丁` 行局部框（860,440,1360,540）diff **11.01%**。垂直平移搜索 dy∈[-4,4] 的最小值仍为 dy=3 的 10.86% → 两图存在全 UI 文本光栅差异（无法靠单一位移对齐消除），而 CJK 行的差异是明确的「补丁 vs 口口」。
- **结论**：问题出在 **NSP 形态**（合成 NSP 的 romfs / 字体相关资源），**不是 K2NX 引擎本身的 CJK 字体能力**——同一引擎、同一游戏目录、同一渲染路径，NRO 正常。已知 NSP 的 `k2s_boot.txt` 显示加载基址 `0x8000000`（NRO 为 `0x80000000`），指向 audit-package 侧 `hacBrewPack`/romfs 打包链路与 NRO 的差异。
- 交接建议（给 audit-package）：比对 NRO 与 NSP 的 romfs 文件清单（尤其 K2NX 内嵌字体/主题资源）与 NCA 内 romfs 的路径编码；该比对需要 keyset，归其负责。**本结论只覆盖 picker UI 的 CJK 字形，不覆盖游戏内文本**（游戏尚未过 registerExEvent 障碍）。

#### 14.3.3.1 打包修复验证（2026-10-30 06:20，audit-package 交付的 fixed NSP）

- 复用 audit-package 的修复版产物 `/e/galnx-build/pilot-01/out/Kirikiroid2-NX-fixed-010047410000b0b3.nsp`（29,877,976 B，sha256 `2bc724555ffa5c3f229748c68e6f06a1b13326619bf8162f045eb5964008dead`，TitleID `010047410000B0B3`）；其打包日志显示 Program NCA **内嵌 ROMFS**：`ROMFS_EMBEDDED_FILES=85`、`ROMFS_EMBEDDED_BYTES=7551013`（旧 NSP 未内嵌完整 romfs）。
- Citron 引导：`--game .../Kirikiroid2-NX-fixed-010047410000b0b3.nsp --input-steps 'wait:4000;capture:picker'` → `status=loaded`、28 s、pid 27708、boot 行 `[   2.405386] ... Booting game: 010047410000B0B3 | Kirikiroid2-NX (64-bit) | 1.0.1`、title 同前。picker 截图 sha256 `78029ba910ecd0b496e16cf2f1edcf9e448f8b667de73e2fa25ae4bb1e20a9b0`。
- **像素结论**：游戏区（y80–960，2 px 采样，阈值 sum>72）修复版 NSP vs NRO **diff = 0.000%**（逐像素一致）；修复版 vs 旧 NSP **6.464%**。即 CJK「口口」是 **romfs 未内嵌完整字体/主题资源** 的打包缺陷，补回 romfs 后与 NRO 渲染完全一致。
- 未覆盖：该验证只到 picker 阶段（游戏仍会在 `registerExEvent` 处崩溃，见 §14.3），不代表游戏内文本/标题画面已验证。
- **NSP 形态的游戏启动复核（同日 06:24）**：在 fixed NSP 里点击 `data.xp3` 后 6 s 内即进入 K2NX 自绘异常控制台；`k2s_log.txt` 原样复现 `==== An exception occured at mainwindow.tjs(990)[(function) SetExEvent], VM ip = 15 ====` / `#(990) 		this.registerExEvent();` / `00000015 calld %0, %-1.*2()	// *2 = (string)"registerExEvent"`（与 NRO 形态逐字一致；XP3 全量读取 19,183 文件 / 19,171 激活，插件 7 个全部 Loading 成功）。→ **打包修复只解决 CJK/资源，不改变 registerExEvent 兼容性缺口**（P1-b 结论不变）。
- 游戏启动复核证据：`P1a-k2nx-nsp-fixed-game-console.png` 428,261 B `936504352c3fd5fe27d95621f83c4846494fbb9874440c915530c7c5bb484686`；`P1a-k2nx-nsp-fixed-game-result.json` 4,190 B `75542be73dbb239189ee38dafb4bd1a7e25585b86091489fb92ead652699a972`；`P1a-k2nx-nsp-fixed-game-k2s_log.txt` 4,597 B `0d95c51770ed311faf30e01c5c91a359d39babf437bf24f4e171cc13ac4999fe`；`P1a-k2nx-nsp-fixed-game-k2s_boot.txt` 217 B `341274bb…3afa`。- 证据（`docs/milestones/evidence/`）：`P1a-k2nx-nsp-fixed-picker.png` 199,174 B `78029ba9…a9b0`；`P1a-k2nx-nsp-fixed-result.json` 2,641 B `9921feec51f8888d958a53f1ef5e9b1f23b7097e27dc5bdecfb2679595dd6dba`；`P1a-k2nx-nsp-fixed-k2s_log.txt` 154 B `0e4115a5…d365`；`P1a-k2nx-nsp-fixed-k2s_boot.txt` 217 B `341274bb…3afa`。
- 证据（`docs/milestones/evidence/`）：`P1a-k2nx-cjk-ab-nro.png` 198,722 B sha256 `4cd19f470ef133a2c8b8b078d09ceb9f696d450ccd2a456b7ffc15b967e677fe`；`P1a-k2nx-cjk-ab-nro-result.json` 2,560 B `bc7f4b34c30f27d71bc50384b5d920ebb3c3fd3afb2482bf3e8b4e9183fb3be1`；`P1a-k2nx-cjk-ab-crop.png`（上 NRO / 下 NSP 放大对照）sha256 `2855feba1aaabdb29b72cb9a8d138f702be4eb20464812ebf75dddd4c07eb628`。

### 14.4 K2NX 输入通路实测（P2-a：标题→正文已达成，手柄未验证）

**结论速览**：重建 NRO（补丁 A1/A2/C）在 Citron 上可以**从标题菜单进入游戏正文并连续翻页**；触发方式是**鼠标（SendInput 绝对坐标）点击**，不是按键。裸按 C（= Citron `player_0_button_a`，VK 67）对标题菜单无效属**源码预期行为**，不是注入通道问题。

- 运行：`--game /e/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r1.nro --timeout 240 --settle 35 --expect-title Kirikiroid --input-delay 4000 --input-steps 'wait:5000;capture:title;click:380,905;wait:4000;capture:afterclick;wait:5000;capture:story1' --keep`；pid 16996、hwnd `0x00600BDC`、`windowRect [426,167,2136,1174]`、client `1706x960`、`foreground=true`。
- **标题菜单命中**：点击 image 坐标 **(350,920)** → 前后 diff **0.795131**；`k2s_log.txt` 记录 `06:50:17 Scenario loaded : start.ks`、`06:50:21 Scenario loaded : @0000A_Z01.ks` → 进入正文（角色立绘 + 文本框「どこの誰かだかもわからない、目の前にある逆光の中の"彼女"に向けて……」）。
- **正文推进**：点击 image (864,520) 两次，每次 diff **0.020134 / 0.020063**（文本翻页）。
- **无效坐标（diff≈0，仅 FPS 数字变化）**：(405,934)、(405,950)、(300,934)、(450,934)、(350,900)、(450,910)、(550,920)、(700,912)、(900,912)。可点区在截图上约为 **y≈900–925 的菜单文字行**，はじめから 在 x≈300–500（中心 ≈400，实测 (350,920) 命中）。
- **坐标体系（易踩坑）**：`--input-click` / helper `-Mode input -X/-Y` 的 X,Y 都是**全窗图像坐标**（与 `capture` 的 PrintWindow 图 1728x1016 同一坐标系，窗口物理 1:1）；**client 坐标 = image 坐标 −(11,45)**（本环境窗口几何）。用 client 坐标直接喂会整体偏左上，点是空。
- **为什么裸按 C 无效（E4 源码）**：`E:/galnx-build/pilot-01/k2nx-ws/src/src/core/environ/cocos2d/MainScene.cpp` 里 `static bool _virutalMouseMode = false`（:58）；`onPadKeyDown`（:2365-2395）在 **虚拟鼠标模式**下 A/B 才是 `_currentWindowLayer->onMouseClick(GameNode->convertToWorldSpace(_mouseCursor->getPosition()))`，否则走 `TVPConvertPadKeyCodeToVKCode` → `InternalKeyDown`（KAG 标题 link 不响应这种按键）。虚拟光标只由 `onAxisEvent`（:2300）以 `JOYSTICK_LEFT_X/Y` 模拟量 `|value|>0.5` 触发显示，键盘/D-pad 不产生模拟量。
- **虚拟光标路线未成功**：`E:/galnx-build/p2a/vcursor.ps1` 用 PostMessage Shift(16) hold + S(83)×18 + C(67)，前后截图完全无变化（2,432,503 → 2,432,494 B）。原因判断：Citron `player_0_lstick` 映射为 `engine:analog_from_button`，需 Shift 才把 modifier_scale 0.5 补到满偏（>0.5），而 PostMessage 无法维持修饰键状态 → 未验证成功（不代表真机手柄不行，真机走真实 HID 模拟量）。
- **触屏路径**：`MainScene.cpp` `:539 TVPWindowLayer::onTouchBegan` / `:582-620 onTouchEnded` 在 touch 结束时补发 `tTVPOnMouseMoveInputEvent`+`tTVPOnMouseDownInputEvent`+`tTVPOnClickInputEvent`+`tTVPOnMouseUpInputEvent` → 触摸点击同样能驱动 KAG link；本次未单独测（`touchscreen_enabled=true`，Citron 鼠标点击已先走通）。
- **对照**：同一注入通道在 KAG3（krkrsdl2）里 C 键推进有效（diff 0.556）——K2NX 标题菜单不吃按键是它自己的输入模型，不是 Citron 映射坏了。
- **存档**：本次运行前后 `sdmc:/kirikiri/haruno/savedata/` 无新文件（仍为 `krenvprf.kep` 80 B / `krkr.console.log` 39,554 B）→ 未到存档点，**存档写入仍未验证**。
- 结论：**标题→正文推进已在模拟器侧达成**；「支持手柄操作」仍未验证（裸 A 无效是设计，需要摇杆产生模拟量或真机 HID）；存档未验证。

**P2-a 证据（`docs/milestones/evidence/`）**：

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `P2a-title-before-click.png` | 2,551,373 | `103ef0c7c65de67fe955f2c5ab7ba68decf6972a1a25432b2df96a5d1648635a` |
| `P2a-story-after-click-350-920.png` | 921,990 | `b6b23938f908931d0298da4474e29741bd18e35070ddac15166627561127b8e3` |
| `P2a-story-adv1.png` | 934,637 | `7eaafd84cd3b7c85f3a6d84001ab88c274631c00a65b3ba4aea4562b99ae6a79` |
| `P2a-story-adv2.png` | 911,153 | `a6c01e700d1961bf44e764fb2064e361c141ddfdd4a14018818c077eb306b458` |
| `P2a-run-result.json` | 3,453 | `3162381c81a6bafd908098f37a53b7120e41fc4e4d3f7ba03414ba15c8a2f716` |
| `P2a-run.log` | 1,801 | `291c2c68353d8aa39aa69c68e563f3a4a201e03afc42e9bec34ec61db7987355` |
| `P2a-k2s_log.txt` | 7,610 | `b7f9a0b8fc366503b3ad726f8107e039298b0683e2397a1645d4c90fd12f7455` |
| `P2a-k2s_boot.txt` | 235 | `6996c10885e4d98aaf1da5571b5a1496f8d4744487a02b921b187e031dbe3935` |
| `P2a-artifacts-sha256.txt` | 清单 | 全部 P2-a 证据的 sha256 + 字节数 |

### 14.5 K2NX / 坐标相关失败模式（新增）

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| picker 打开时不是 SD 根，而是上次目录（haruno） | K2NX 记住上次路径：`sdmc:/switch/kirikiroid2/.preference/recentpath.xml` | 每 run 先 `capture` 再按当前画面规划坐标；或删除该文件（会改变 K2NX 行为，需记录） |
| 按「SD 根」坐标点击 (1233,406) 后进了 `savedata_chs` | 画面状态已变，坐标按旧图算 | 依赖每步 `capture:` 留图核对；不要复用上一 run 的坐标 |
| 点 data.xp3 后画面停住约 80 s | 弹出「输入示意图」模态 overlay，未关闭不继续 | 点右上 X（image 1546,180）后再等 |
| 游戏崩溃后画面像正常界面（nonblack 0.9） | K2NX 把 TJS 异常打到自绘文本控制台 | 不能只看非黑比例；必须读画面文字 + `k2s_log.txt` |
| bash 传 `--input-steps @/abs/x.json` 参数变垃圾 | 外层工具展开 `@` | 用 `--input-steps-file` 或纯路径 |
| 取证后发现 `k2s_log.txt` 是别的 run 的 | K2NX 每次启动覆盖 `k2s_log.txt`，只保留一版 `.prev` | 该 run 结束后**立刻**复制 `k2s_log.txt` 到证据目录 |
| 标题菜单点 (405,934)/(300,934)/(450,934) 全无反应 | 菜单文字行在 y≈900–925，且可点矩形比文字窄；y=934 已偏下 | 用截图量文字行中心：はじめから ≈ (350,920)，其余项按同一行 x 递增 |
| 点击发生在标题出现前，被忽略 | 启动有 eyecatch/logo.mpg 视频（本例约 40 s 才进 title.ks） | 步骤里先 `wait`+`capture` 确认画面已是标题菜单再点；不要固定盲点 |
| 用 client 坐标注入，画面毫无反应 | `--input-click`/helper 要的是**全窗图像坐标** | image = client +(11,45)（本环境）；坐标一律以 `capture` 出的 1728x1016 图为准 |

### 14.6 限制与下一步

1. P2-a 已把「标题菜单 → 进入正文 → 正文翻页 ×2」打通（鼠标点击，§14.4）；但**存档写入、手柄/摇杆、音频、长时稳定性、真机均未验证**。NSP 打包链路已验证（§14.3.2），picker UI 的 CJK 字形 A/B 已完成（§14.3.3：NRO 正常 / NSP 豆腐块，归打包链），fixed NSP 与 NRO 逐像素一致（§14.3.3.1）；游戏内正文文本的 CJK 渲染与音频播放仍未单独取证。
2. 游戏原件（`E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气`）只读；虚拟 SD 里的 `sdmc:/kirikiri/haruno/` 是本地实验副本，不入库、不分发。
3. 下一步（P1-b 候选）：① 提取 `data.xp3` 内 `mainwindow.tjs:990` 上下文，判断是 `Window` 还是 `Pad`/其它对象上调用；② 若可用 loose-file 覆盖打补丁，则本地验证「路径通」；③ 向上游提 issue（附本例日志）；④ 同时评估 krkrsdl2（M1 已验证 KAG3）与 K2NX 双引擎路线。
4. 下一步（P2-b 候选，按优先级）：① 用 rebuild NRO 的 autostart 直达正文后测**存档写入**（进入存档点/菜单存一次，检查 `sdmc:/kirikiri/haruno/savedata/` 新文件 + 重新启动读档）；② 手柄验收：真机 Joy-Con/Pro Controller（或让 Citron 产生真实左摇杆模拟量）验证「摇杆出光标 + A 点击」；③ 音频（BGM/语音）是否真的出声；④ 用 A1 自包含 NSP 做「首启解包 → 自动进标题」验证。

### 14.7 P1-a 证据清单（`docs/milestones/evidence/`）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `P1a-01-k2nx-picker-root.png` | 92,221 | `91dd7e907e99d467b14bfaacc7a7874ec4b2861ea0b3e1a73567e70dc170b333` |
| `P1a-02-k2nx-picker-haruno.png` | 174,993 | `930d7f43158a930e0cc8cd00f59369157359c5168dd4f5e7cc3d397730d6ffb3` |
| `P1a-03-k2nx-input-overlay-blocking.png` | 144,967 | `d6b26b5157c206186649af92e5078e357dc2d1bbd71724c2a98f5992a9317b6f` |
| `P1a-04-k2nx-tjs-exception.png` | 427,927 | `8314432e7f2708dd94fdb4f276db55071ec9b32620828ff5fb4e3e931df976e5` |
| `P1a-05-k2nx-repro-exception-console.png` | 428,429 | `7ec824bbb2b46d8f77c396dc6a295f73b6f819720a7bc13dc9216a088cd3312e` |
| `P1a-06-k2nx-repro-result.json` | 4,060 | `564c38518af1ef4437caedd05b3be9e5affd9ebc93286ba526c095b3b96fe6a7` |
| `P1a-07-k2nx-picker-gamepad-key-noeffect.json` | 3,455 | `762e9a7c2870e019ffead66e72ed8b48f96e33935f8df35a736f4dc7a08738a9` |
| `P1a-08-k2nx-picker-after-keys.png` | 198,722 | `4cd19f470ef133a2c8b8b078d09ceb9f696d450ccd2a456b7ffc15b967e677fe` |
| `P1a-k2s_log-run1.txt` | 4,604 | `b97fccb30f2add1ae8b7353c3db5935e787ec975ec4ec2b9d2d231da4e34b549` |
| `P1a-k2s_log-run5-repro.txt` | 4,604 | `891e90ca1bab38afdf6bf9c9e040128d3a68a1b3bf161af40e4fd36c108fb945` |
| `P1a-k2s_boot.txt` | 218 | `e1519c61697b75ed2241e50be0040d0826027e441e1f76cf25bed58f10026816` |
| `P1a-k2nx-cjk-ab-nro.png` | 198,722 | `4cd19f470ef133a2c8b8b078d09ceb9f696d450ccd2a456b7ffc15b967e677fe` |
| `P1a-k2nx-cjk-ab-nro-result.json` | 2,560 | `bc7f4b34c30f27d71bc50384b5d920ebb3c3fd3afb2482bf3e8b4e9183fb3be1` |
| `P1a-k2nx-cjk-ab-crop.png` | 21,651 | `2855feba1aaabdb29b72cb9a8d138f702be4eb20464812ebf75dddd4c07eb628` |
| `P1a-k2nx-nsp-result.json` | 2,587 | `755d62ad417cd8a6ac3572579703a7013458fbcc854ca281cfe9342675a8cc78` |
| `P1a-k2nx-nsp-picker.png` | 197,824 | `4b9f5ba18302c1d2c4c6ec419ca215c23a8c7e6e749e67d7edb57dbf01ad8acc` |
| `P1a-k2nx-nsp-k2s_boot.txt` | 217 | `341274bb4a2daaa622477cda33ddec14634bbe296048c13c2a294fc53b8e3afa` |
| `P1a-k2nx-nsp-k2s_log.txt` | 154 | `0e4115a5715ed9bb6d626147f6ebb32d8911163552de23906402dd0c7d27d365` |
| `P1a-k2nx-nsp-fixed-picker.png` | 199,174 | `78029ba910ecd0b496e16cf2f1edcf9e448f8b667de73e2fa25ae4bb1e20a9b0` |
| `P1a-k2nx-nsp-fixed-result.json` | 2,641 | `9921feec51f8888d958a53f1ef5e9b1f23b7097e27dc5bdecfb2679595dd6dba` |
| `P1a-k2nx-nsp-fixed-k2s_log.txt` | 154 | `0e4115a5715ed9bb6d626147f6ebb32d8911163552de23906402dd0c7d27d365` |
| `P1a-k2nx-nsp-fixed-k2s_boot.txt` | 217 | `341274bb4a2daaa622477cda33ddec14634bbe296048c13c2a294fc53b8e3afa` |
| `P1a-k2nx-nsp-fixed-game-console.png` | 428,261 | `936504352c3fd5fe27d95621f83c4846494fbb9874440c915530c7c5bb484686` |
| `P1a-k2nx-nsp-fixed-game-result.json` | 4,190 | `75542be73dbb239189ee38dafb4bd1a7e25585b86091489fb92ead652699a972` |
| `P1a-k2nx-nsp-fixed-game-k2s_log.txt` | 4,597 | `0d95c51770ed311faf30e01c5c91a359d39babf437bf24f4e171cc13ac4999fe` |
| `P1a-k2nx-nsp-fixed-game-k2s_boot.txt` | 217 | `341274bb4a2daaa622477cda33ddec14634bbe296048c13c2a294fc53b8e3afa` |
| `P1a-artifacts-sha256.txt` | 清单 | 全部 P1a 证据的 sha256 + 字节数 |

## 15. 脱离进程树模式（`--detach` / `--status` / `--wait-job`，P3-d，2026-10-30）

### 15.1 为什么需要（R14 根因）

- **症状**：从 agent shell 启动既有 harness 时，脚本约 27 s 就早退（Citron 进程仍存活），run 目录里没有 `result.json`/截图/最终 JSON，调用方拿不到结论。
- **根因一（进程树）**：本机 shell 是 elevated，Citron 必须**降权**启动（`runas /trustlevel:0x20000` 或 Task Scheduler）；这类启动会脱离调用方进程树。当上层工具回收 bash 进程树时，harness 自己的轮询/截图循环被一起终止——Citron 却还活着，形成「脚本失败但进程正常」的假象。
- **根因二（陈旧日志假阳性）**：Citron 的 `log/citron_log.txt` 是覆盖式沿用文件，上一次 run 的 `BootGame: Booting game:` 行仍在新日志基线之前；启动失败时旧行会被当成本轮 boot 证据 → 误判 `loaded`（见 §15.6 失败案例 2）。
- **修复**：`--detach` 让父进程**立即返回** JSON（run_dir / harness pid / 结果文件路径），真正工作交给一个由 WMI `Win32_Process.Create` 创建、父进程为 `WmiPrvSE` 的脱离进程执行；子进程无论成功/失败/早退都写 `run_dir/result.json` + `.done`；调用方用 `--status` / `--wait-job` 收集结果。同时加「日志基线守卫」消除假阳性。

### 15.2 用法与退出码

```bash
# 1) 启动（父进程约 5 s 返回，不等游戏跑完）
bash scripts/citron_run.sh --game /e/galnx-build/m1-sdl2/m1-sdl2.nro \
  --timeout 90 --settle 10 --expect-title m1-sdl2 --detach

# 2) 一次性查询（已结束 → 直接打印最终 JSON；未结束 → state=running/starting）
bash scripts/citron_run.sh --status "<run_dir>"

# 3) 轮询等待（默认 120 s，可调 --wait-timeout；结束或超时后打印最终 JSON）
bash scripts/citron_run.sh --wait-job "<run_dir>" --wait-timeout 360
```

| 命令 | 退出码 | 含义 |
| --- | --- | --- |
| `--detach`（父） | 0 | 已成功创建脱离 job（**不代表游戏已跑完**） |
| `--detach`（父） | 2 | 参数/预检失败，未创建 job |
| `--status` / `--wait-job` | 0 | job 已结束且 `status=loaded` |
| `--status` / `--wait-job` | 1 | job 已结束但 `status=fail/timeout`（超时在 job 内部按 `--timeout` 判定） |
| `--status` / `--wait-job` | 2 | job 目录不存在 / 类目无法识别 / `--wait-timeout` 到期仍未结束（stdout 仍会给 `state=running` 快照） |

### 15.3 job 目录与文件

| 路径 | 内容 |
| --- | --- |
| `<run_dir>/job.json` | 父进程返回体（run_dir、result_json、done_marker、harness_pid、launcher_pid、command、started_at） |
| `<run_dir>/harness.pid` | 子 harness 的 pid（`--detach` 父 JSON 里的 `harness_pid` 同源） |
| `<run_dir>/.done` | 完成标记，三行：`status=<loaded|fail|timeout>`、`rc=<0|1|2>`、`finished=<ISO8601 UTC>` |
| `<run_dir>/result.json` | 与前台模式完全一致的最终 JSON（含 signals / screenshot_info / input.steps / launch_route ...） |
| `<run_dir>/harness.out` / `harness.err` | 子进程 stdout/stderr（`[citron_run]` 进度行；失败原因常在这里） |
| `<run_dir>/_job.sh` / `job.cmd` / `job.ps1` | 实际执行的 job 脚本副本（排查用） |
| `%TEMP%/galnx-jobs/<run_id>/` | launcher 目录（`job.cmd` 真正被 `cmd.exe /c` 执行的位置，`job.json` 里的 `launcher_dir`） |
| `%ProgramData%/galnx-harness/` | Windows 侧 wrapper 目录（`wrapper-<run_id>.cmd`，Task Scheduler 动作指向这里） |

`_job.sh` 由 cmd 调用的 bash 执行，必须显式 `export CITRON_USER_DIR/CITRON_SD/CITRON_EXE/APPDATA`——WMI 创建的进程**不继承**父 shell 环境（见失败案例 1）。

### 15.4 启动路由 `launch_route`

最终 JSON 新增字段 `launch_route`，取值：

| 值 | 触发条件 | 说明 |
| --- | --- | --- |
| `direct` | 非 elevated shell | 直接 `Start-Process wrapper.cmd` |
| `runas-deelevated` | elevated 且 schtasks 路由失败时回落 | `runas /trustlevel:0x20000 wrapper.cmd`（2026-10-30 08:1x 起在本机静默失效，见下） |
| `schtasks-limited` | elevated 且 Task Scheduler 创建 + 运行成功 | `schtasks //Create //TN GalNXHarness-<RUNID> //TR "cmd.exe /c \"<wrapper.cmd>\"" //SC ONCE //ST 23:59 //RL LIMITED //IT //F`，`LastTaskResult` 为 `0` 或 `267009`（正在运行）即视为已启动 |

- 关键点：Task Scheduler 的 `//TR` **必须**是 `cmd.exe /c "<wrapper.cmd>"`；直接把 `.cmd` 路径给 `//TR` 会 `LastTaskResult=1` 且不执行 payload。
- wrapper 目录固定 `C:\ProgramData\galnx-harness`（有空格时回落 `C:\Windows\Temp\galnx-harness`）。原因：本机 MSYS 把 `$TEMP=/tmp` 映射到 `D:/devkitPro/msys2/tmp`，Task Scheduler 侧看不到该路径。
- 一次性任务注册在 23:59；harness 结束前会 `schtasks //Delete //TN ... //F`。若 harness 被强杀，可能残留任务，手工清理：`schtasks //Delete //TN GalNXHarness-<RUNID> //F`。

### 15.5 陈旧日志守卫（防假阳性 `loaded`）

- 启动前记录 `citron_log.txt` 的 `size` 与 `mtime`（`LOG_BASE_SIZE`/`LOG_BASE_MTIME`）。
- 轮询结束（超时/未命中）时若日志 size/mtime 与基线**完全相同** → `LOG_FRESH=0`，清空已收集的 `boot line`/`citron build`/异常行，并按 `status=timeout` 处理，`error` 写：

```
citron_not_started: no fresh citron log after launch (launch_route=<route>; launcher may have failed; see docs/environment/citron-harness.md)
```

- 这样失败会**显式**报错，而不是拿上一次 run 的日志冒充本轮证据。

### 15.6 实测记录（2026-10-30）

| run | 场景 | 结果 |
| --- | --- | --- |
| `20261030-083250-m1-sdl2` | `--detach` + m1-sdl2 NRO | 父进程约 5 s 返回（`harness_pid=31210`、`launcher_pid=25788`）；子进程 `status=loaded`、`launch_route=schtasks-limited`、`elapsed_s=20`、截图 79,658 B / nonblack 0.8907、`.done`（`00:33:28Z`）、Citron 已 kill |
| `20261030-083721-Kirikiroid2-NX-010047410000b0b4` | `--detach` + A2 自包含 NSP（2,906,131,672 B）+ 7 步输入 | `status=loaded`、`game_type=nsp`、`launch_route=schtasks-limited`、`window_title=... Kirikiroid2-NX (64-bit) | 1.0.1`、steps 7/7、`steps_diff_ratio=0.809225`、**总耗时 222 s（00:37:24→00:41:03Z）**，对比修复前 27 s 早退 → R14 修复成立；k2s_log 显示 `[GALNX] payload pilot01-r2 already extracted`、5 条 `.tpm -> .dll` 插件别名、`Loading startup script`、19,153 files |
| `20261030-083515-m1-sdl2` | **不带** `--detach`（旧调用方式回归） | `status=loaded`、`elapsed_s=17`、截图 79,389 B，行为与修复前一致（兼容性未被破坏） |
| `20261030-081745-m1-sdl2` | 失败案例 1：WMI 子进程无 `APPDATA` | `status=fail`、`rc=2`、`citron_user_dir_missing` |
| `20261030-081901-m1-sdl2` | 失败案例 2：`runas` 路由失效 + 旧日志假阳性 | 修复前误判 `loaded`（`pid` 为空、截图 0 B）；守卫加入后同类情况必判 timeout |
| `20261030-082919-m1-sdl2` | 失败案例 3：wrapper 落在 MSYS 临时目录，Task Scheduler 取不到 | 守卫正确判 `status=timeout`，`error=citron_not_started: ...` |

查询接口实测：`--status <已完成 run>` → 退出码 0、打印最终 JSON；`--wait-job <已完成 run>` → 退出码 0、`waited_s=0`；`--wait-job /e/no-such-dir` → 退出码 2、stdout `{"state":"unknown","run_dir":"","error":"job dir not found"}`。

### 15.7 P3-d 证据清单（`docs/milestones/evidence/`）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `P3d-a2-parent.json` | 1,258 | `3b3ecd8171c25437bc75301580d14956e925bf3a0a8b6d83e4b9dc07c9aa0d21` |
| `P3d-a2-result.json` | 3,435 | `0a21c25debb635cadc480fa15cf657485e85e7c351b8e7fe0944f3d4f9d35cd2` |
| `P3d-a2-done.txt` | 49 | `103bd5104963a05e465cd7e0c5b1aea6010e2e4af5f05a43f74a8cf8a5535839` |
| `P3d-a2-run.log` | 1,925 | `aa3fb8d290bc1ef6345da33c6da6063cdbb3b3dca744ab929d570a75da415621` |
| `P3d-a2-harness.err.txt` | 1,100 | `f17955ade30424c1c81927510579175ce1433d9c95d91faf1d10280f2f64d7cb` |
| `P3d-a2-title-after-120s.png` | 2,377,784 | `884786a6ef6aa33a626fb52bc24d98c30289ef6bc35c1a154657e9b726c83994` |
| `P3d-a2-k2s-log-slice.txt` | 1,730 | `ebe96cfc1b63ce20fa9db713a2f316941dc1d5398f162a651caf3768f9168829` |
| `P3d-m1sdl2-result.json` | 1,807 | `db2e8aabe809a488ea9e179a6f269e662b4ce9bb0af27e2764522fd05a8048da` |
| `P3d-m1sdl2-done.txt` | 49 | `4f022010e55ca2a8dafc9beff52bdae5a18a038daa074e466cc37f5cbad5a82b` |
| `P3d-m1sdl2-job.json` | 1,066 | `e3dfa55591089cb1727883494c3f79bf257049da09cf98bb26d366f008cc67c2` |
| `P3d-m1sdl2-window.png` | 79,658 | `694f7001ab45ee7efb6bc4985e7eb002d186098716b3530e6649bc37ea9ad2f6` |
| `P3d-legacy-m1sdl2-result.json` | 1,807 | `682d15e14ac11e814c47d8e701787f0d4676ed5384f485fba0d405cf58f62dbc` |
| `P3d-failure-cases.txt` | 3,692 | `02fcbd9c91d00f0dd3a48c6838b617058d9ed537cf2a1c7b864dbdcdb4ec50f1` |
| `P3d-artifacts-sha256.txt` | 清单 | 上述全部文件的 sha256 + 字节数 |

### 15.8 限制与已知问题

1. `--detach` 只解决「调用方进程树被回收」；Citron 进程仍由该 job 拉起并在 harness 结束时 kill（`killed=true`）。不要在 job 未结束时手工再起 Citron（单实例预检会报 `citron_already_running`）。
2. Task Scheduler 依赖当前用户交互会话（`//IT`）；锁屏/切换用户可能影响拉起，失败会由 `schtasks` 路由回落或日志守卫显式报错。
3. 若 harness 被强杀，`%ProgramData%/galnx-harness/wrapper-*.cmd`、`%TEMP%/galnx-jobs/<run_id>/` 与一次性计划任务可能残留；不影响下次运行，但建议清理（计划任务同名带 run_id，不冲突）。
4. 本机 `runas /trustlevel:0x20000` 直接跑 `.cmd` 从 2026-10-30 08:1x 起静默失效（目标为 `cmd.exe /c` 时仍有效）——属本机环境现象，故默认走 Task Scheduler；非 elevated 环境仍走 `direct`。
5. `--wait-job` 的等待上限由 `--wait-timeout` 控制（默认 120 s）；A2 NSP 全流程约 222 s，调用方应按场景放大（本例 360 s）。
6. 真机（Atmosphère）上无「runas/Task Scheduler」概念，本机制只用于模拟器侧自动化；真机验收仍需独立步骤。
