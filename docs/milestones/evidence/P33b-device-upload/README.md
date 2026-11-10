# P33b — v1.1.9-test 真机投放证据（MTP / WPD）

日期：2026-11-08（北京时间 00:2x–01:0x）
设备：Nintendo Switch（MTP 名 `Switch`，usb vid_057e pid_201d，serial xaj40080865533）
通路：Windows Shell COM（WPD/MTP），不使用 DBI FTP。方法与坑见 `docs/environment/mtp-wpd-transfer.md`。

## 1. 写设备侧配置文件（sdmc:/switch/rfvp/）

| 文件 | 写入内容 | 字节 | 说明 |
|---|---|---|---|
| `video.txt` | `480` + LF | 4 | P33 选档，缺省档 480p（854×480） |
| `debug.txt` | `movie=1` + LF | 8 | OP 调试钩子（强制带音轨路径），启动后播一次 OP |
| `async.txt` | `on` | 2 | 异步解码开（P18） |

- 三个文件均经 MTP 写入后**回读**（`mtp-pull.ps1`）用 `od -c` 核对，本目录 `video.txt` / `debug.txt` /
  `async.txt` 即回读的原始字节（`SHA256SUMS` 可校验）。
- `debug.txt` 原为 1 B（内容 `1`），MTP `CopyHere(...,20)` 对同名文件**静默跳过**；改用「先 `Name`
  改名为 `debug.txt.old`，再复制新文件」才成功 → 坑与配方记入 `docs/environment/mtp-wpd-transfer.md` §4。

## 2. 投放安装包

- 源：`E:/galnx-build/p33/out2/IROSEKA_FHD-010047420000a000.nsp`，9,977,492,184 B，
  sha256 `bd909c1eb1e6e3f9339a28b662943d0d06f74873b2dd36639824df54a90b535b`（v1.1.9-test）。
- 目标：`Switch\5: SD Card install`（放进该目录由设备侧自动安装，无需 FTP）。
- 过程截图：`mtp-copy-dialog.png`（Shell 复制对话框，进度约 45% 时 ETA 8 分 30 秒；
  窗口 `0x00060E06` / pid 22096 / 类 `#32770`，`window_capture` dwm-thumbnail 抓取）。

## 3. 安装与验收（待填）

- [ ] 复制完成：`5: SD Card install` 下 NSP 的 `System.Size` 达到 9,977,492,184（拷贝结束后用新 Shell 枚举校验）。
- [ ] 设备侧安装完成（Home 菜单出现 IROSEKA_FHD，版本 1.1.9-test）。
- [ ] 启动后自动播 OP：判定是否慢放/卡死，读 `debug_report.txt` 的 `Movie: opened … level=2`、
      `decoded … 854x480 decode_us/convert_us`、`audio_status.txt` 的 `lag_ms/underrun`。
- [ ] 档位 A/B：480（默认）→ 360 兜底 → 720 对照（改 `video.txt` 重启）。

## 4. 复现命令（本机）

```powershell
# 写配置/覆盖同名文件（rename 后 CopyHere）
powershell -NoProfile -ExecutionPolicy Bypass -File E:/galnx-build/p33/mtp-fix-debug.ps1
# 回读校验
powershell -NoProfile -ExecutionPolicy Bypass -File E:/galnx-build/p33/mtp-pull.ps1
# 投放 NSP（保持脚本存活到复制完成；期间用 window_list/window_capture 看“正在复制”对话框）
powershell -NoProfile -ExecutionPolicy Bypass -File E:/galnx-build/p33/mtp-upload-nsp.ps1
```
