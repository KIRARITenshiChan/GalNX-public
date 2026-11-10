# rfvp 自包含 NSP 真机安装与验收 runbook（P11→P14，IROSEKA_FHD）

> 适用产物（当前）：`IROSEKA_FHD-010047420000a000.nsp` v1.0.3（含 P13 真机缺陷修复 + P14 性能修复；位于 `E:/galnx-build/p14/out/`，不入库）
> 大小 / SHA-256：9,979,441,368 B / `b9e0d6a54a44bf3a3dde8e3f32f22f41d3ee4e009101e9df4f6892e4fb85aa3e`（`galnx package nsp verify` ok=true，12 checks 0 fail/1 warn）
> 历史产物：v1.0.2 9,979,437,784 B，SHA-256 `ff259aa49780b6c93e79762c6db5c670c6a979ffb6ddcd7c6ab4ce95e09c0d9b`（P13 真机缺陷修复）；v1.0.1 9,979,435,736 B，SHA-256 `0fda623c37dc8664492341d00a103eaf606eb1a88583f0101508cefd39467419`（P12 输入映射重写）。
> 历史产物（P11）：9,979,435,224 B，SHA-256 `4592385c…`。
> 构建记录：`docs/builds/018-rfvp-nsp.md`（NSP 打包）、`docs/builds/019-rfvp-input-mapping.md`（P12 输入层）、`docs/builds/020-rfvp-device-fixes.md`（P13）、`docs/builds/021-rfvp-perf-gpu-prev-frame.md`（P14）；证据：`evidence/P11-rfvp-nsp/`、`evidence/P12-rfvp-input/`、`evidence/P14-rfvp-perf/`、`evidence/P12b-rfvp-device-fixes/`。

## 1. 前置条件

| 项 | 要求 |
| --- | --- |
| 主机 | 已破解 Switch（Atmosphère + sigpatches；homebrew NSP 未签名，无 sigpatches 会安装后无法启动） |
| 存储 | **exFAT** microSD 或足够 NAND；FAT32 单文件上限 4 GiB，装不下 9.98 GB 的 NSP |
| 空间 | 安装约需 10 GB 可用空间（romfs 内容按 NCA 加密压缩后仍接近 9.9 GB） |
| 网络 | 可选：DBI FTP（Switch 与 PC 同一局域网，端口 5000）或 USB MTP |
| PC 工具 | `ftp`（Windows 自带）或 FileZilla；`nstool`（可选，本机 `E:/galnx-build/m3-tools/nstool.exe`） |

## 2. 上传与安装（DBI FTP）

1. Switch：打开 **DBI** → `FTP`（或 `Run FTP server`），记下屏幕上的 `ftp://<ip>:5000`。
2. PC（PowerShell 或 cmd）：

   ```powershell
   ftp <switch-ip> 5000
   # 登录后：
   binary
   put "E:/galnx-build/p11/out/IROSEKA_FHD-010047420000a000.nsp"
   ```

   DBI 的 FTP 服务端对 `put` 到根目录的 `.nsp` 会**自动安装**；**P11 版实测 2026-10-31：9,979,435,224 B / 1,579.1 s ≈ 6.03 MiB/s（26.3 分钟）；P12 版 v1.0.1 实测 9,979,435,736 B / 1,462.2 s ≈ 6.52 MiB/s（24.4 分钟）；P13 版 v1.0.2 实测 9,979,437,784 B / 1,548.7 s ≈ 6.15 MiB/s（25.8 分钟）；P14 版 v1.0.3 实测 9,979,441,368 B / 1,529.0 s ≈ 6.22 MiB/s（25.5 分钟）；**P16 版 v1.0.4 实测 9,979,446,488 B / 1,636.4 s ≈ 5.82 MiB/s（27.3 分钟，**浏览 SD 卡模式**，见下）**；**P17 版 v1.0.5 实测 9,979,481,304 B / 1,686.5 s ≈ 5.64 MiB/s（28.1 分钟，浏览 SD 卡模式）**，无中断。也可用 FileZilla 拖拽。
3. 等待 DBI 显示安装完成；若中断，重新 `put` 同名文件（DBI 会覆盖/续装）。

> **DBI 两种 FTP 根目录模式（P16 实测）**：
> - **安装模式**（默认入口）：根目录是投放区，`put *.nsp` 到根目录即自动安装并覆盖同 TitleID 旧版——P11–P15 均用此模式。
> - **浏览 SD 卡模式**：根目录 = SD 根（可见 `Nintendo/`、`switch/`、`atmosphere/` 等），`put` 只落盘不安装；P16 v1.0.4 即以此模式上传到 `/switch/galnx-nsp/IROSEKA_FHD-010047420000a000.nsp`（9,979,446,488 B，5.82 MiB/s）；P17 v1.0.5 同路径（9,979,481,304 B，5.64 MiB/s，2026-11-01）。安装方式：Switch 打开 DBI → **浏览 SD 卡** → `switch/galnx-nsp/` → 选中 NSP → 安装（覆盖 1.0.3）。可用 `SITE FREESPACE SD` / `SITE FREESPACE NAND` 查剩余空间。

## 3. 首次启动确认

| 检查 | 期望 |
| --- | --- |
| 桌面图标/标题 | `IROSEKA FHD`（图标为 P9 标题截图裁剪） |
| 版本 | `1.0.3` |
| 启动 | 无「无法启动/签名无效」错误（否则检查 sigpatches） |
| 游戏根 | 进正文前不应要求 SD 上有 `sdmc:/switch/rfvp/game`（NSP 自带 romfs）；NRO 形态仍可从 SD 目录启动 |

## 4. 验收矩阵（手柄）

> P13（v1.0.2 NSP，补丁 `rfvp-input-remap.patch` + `rfvp-device-fixes.patch`）后的最终映射；Citron 已逐项验证（见 `docs/builds/019-rfvp-input-mapping.md` 与 `docs/builds/020-rfvp-device-fixes.md`），真机需按此表复核手感。

| # | 操作 | 期望 | 备注 |
| --- | --- | --- | --- |
| V1 | 启动 → 标题 | 中文标题 + New Game/Continue/Album/Option/Exit | romfs 自包含，无 SD 数据 |
| V2 | 右摇杆 | 屏幕出现**主机层自绘**的黑白菱形光标并随之移动（若游戏自身也画青色菱形，两者会同时出现） | P13 新增；光标只在出现过指针事件后显示 |
| V3 | 光标移到 New Game + ZR（左键） | 进入序章，60 fps | ZR 按住=左键按住 |
| V4 | A | 完成打字 / 推进正文 | A=Enter（不再映射空格） |
| V5 | B | 打开游戏暂停菜单（SAVE/LOAD/HIDE/UNDO/OPTION/TITLE/EXIT/RETURN 钟面） | **Esc 关不掉菜单**（游戏只认指针），关闭用 ZL 右键或点 RETURN |
| V6 | ZL | 右键：关闭暂停菜单 / 隐藏消息窗 | Citron 已证关菜单 |
| V7 | X | 正文工具栏 AUTO 打开（底部出现 AUTO 进度条 + 「自动播放」） | 点工具栏实测锚点 |
| V8 | Y | 打开 FILE LOAD 面板 | Esc 宏 + 点 LOAD 锚点 |
| V9 | +（PLUS） | 打开 FILE SAVE 面板 | Esc 宏 + 点 SAVE 锚点 |
| V10 | −（MINUS） | 弹出**主机自绘** `QUIT GAME? / A = YES  B = NO` 面板（不依赖游戏 UI，标题画面也能用）→ A 确认后干净返回桌面，B 取消回游戏 | P13 重做；确认框期间 A/B 不转发给游戏 |
| V11 | D-Pad | 键盘方向键（backlog 滚动/菜单导航） | 不再移动指针 |
| V12 | 左摇杆上下 / R | 滚轮（上开 BACKLOG、下下一句）/ R=Ctrl 按住快进 | **R 的跳读效果 Citron 未复现（U9），重点复核** |
| V13 | 游戏内原生 EXIT（暂停菜单 EXIT → 游戏自己的确认框点「确定」） | 播完退出动画后**真正退回桌面**，不再黑屏 | P13 修复（no_std 消费 ExitDialog / ExitMode(3)）；Citron 已证 |
| V14 | 性能（转场/周期卡顿） | logo 动画 / 转场 / CG / 每 5 秒周期性停顿消失，音频与画面同步 | **P14 重做：GPU prev-frame（不再每帧 CPU 回读）+ 编译掉 debug_screen.bmp 周期回读 + 顶点批处理；Citron 同探针 slow 行 154→19、thumb≥20 ms 帧 142→0** |
| V15 | 冷启动 / 存档尖峰 | 冷启动一次明显停顿可接受；存档瞬间（约每 2 分钟）不再卡顿 | P14 未优化启动 vfs_read（U19）；存档尖峰仍存在（U20） |

## 5. 存档位置与验证

- 存档在 SD：`sdmc:/switch/rfvp/saves/iroseka-2ae7dc8e/save/rfvp_s000.bin`（快速槽 0，约 490 KB）。
- 快速存/读后回读该文件；或用游戏自带 SAVE 面板（需指针点击，见 017 限制 U2）。
- 游戏自带多槽位 SAVE 面板在 Switch 上不可用（桌面专属 UI），只落快速槽 0。

## 6. 失败排查

| 症状 | 排查 |
| --- | --- |
| 安装失败/文件过大 | SD 是否 FAT32？换 exFAT 或装到 NAND；确认剩余空间 ≥10 GB |
| 启动报签名错误 | 装 sigpatches（Atmosphère 版本匹配）；homebrew NSP 未签名属预期 |
| 卡在加载 | 首次从 romfs 读 9.2 GiB，真机 I/O 未知；等 60 s 仍无画面则记录日志/截图 |
| 无声音 | 音频未在真机验证（U3），记录现象即可 |
| 视频不播放 | movie 未验证（U4），记录现象即可 |
| 内存不足闪退 | 4 GB 机型内存余量未测（U5）；记录发生场景 |

## 7. 取证

- 截图：标题、正文中文、BACKLOG、退出确认（保存到 `docs/milestones/evidence/P11-rfvp-nsp/device/`，不入库者放 `workspaces/`）。
- 哈希：真机安装后的 title id/版本可截图；安装包 SHA-256 与本文头部一致。
- 失败时抓 DBI/Atmosphère 报错屏与 `sdmc:/switch/rfvp/saves/` 列表。

## 8. 未验证项

018 §9 的 U1–U8 仍然有效（真机安装/运行、音频、movie、内存、romfs 首读、多游戏等；上传耗时已在 P11 实测关闭）。P12 新增：

- **U9（重点）R=Ctrl 的跳读效果**：Citron 中按住 R（2.5/5/6 s）只前进一句，未观察到连续跳读；引擎侧已确认 `Control` 位写入 `new_input_state`，游戏侧 `TextSkip` 调用条件未知。真机若也无效，备选实现「按住 R 连发左键」。
- U10 右摇杆光标速度与 ZR 按住拖拽手感需真机调参（`POINTER_DIVISOR=3000`）。
- U11 B=Esc 只能打开、不能关闭暂停菜单（游戏只认指针），真机用 ZL 右键或点 RETURN。

P13 新增：

- **U12（重点）真机光标**：主机层菱形的可见性、跟手程度、与游戏自绘菱形并存是否干扰。
- **U13（重点）真机性能**：logo 动画 / 转场 / CG / 音频同步是否达标。
- **U14（重点）真机原生退出**：游戏内 EXIT 是否真的回到 HOME（含退出前全局存档 flush）。
- **U15 真机 − 键**：确认框是否出现、A 确认是否退出、B 取消是否回游戏。
- U16 确认框文案为英文（5×7 点阵字体无 CJK 字形）。
- U17 光标一旦出现不再隐藏（游戏内 `CursorHide` 未消费）。

P14 新增：

- **U18（重点）真机转场/周期性卡顿**：Citron 已把 thumb 回读 142→0、slow 行 154→19；真机（含 Ryujinx）需确认 logo 淡入、CG 切换、每 5 秒周期停顿均消失。
- U19 冷启动首次 `vfs_read 675 ms` + `graph_decode 521 ms` 未优化，真机首启仍会停顿一次。
- U20 存档尖峰（`save_finalize 32 ms` + 缩略图 11 ms，约每 2 分钟）未优化。
- U21 GPU prev-frame 依赖 `SDL_TEXTUREACCESS_TARGET`；Citron 已通过，真机 SDL2 后端需随 U18 一并确认。

真机结果回填本文件与 018 §6/§9、019 §7、020 §8、021 §9。
