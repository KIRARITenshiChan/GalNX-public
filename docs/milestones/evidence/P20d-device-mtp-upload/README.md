# P20d · rfvp NSP v1.0.8 真机 MTP 上传证据

日期：2026-11-01 22:47–22:58（Asia/Shanghai）
任务：修复真机 v1.0.6 黑屏（m24478）+ 确认 async 根因（m24969）→ 交付 v1.0.8（async 阶段诊断 + 3 s 看门狗自愈 + 1 MiB 栈）。

## 通路

- 设备处于 MTP 响应器模式；DBI FTP `192.168.31.254:5000` 探测 `ConnectionRefusedError`。
- Windows Shell COM（WPD）：`This PC → Switch → 1: SD Card → switch → galnx-nsp`，子目录用 `ShellFolderItem.GetFolder` 取得（`NameSpace(path)` 对 MTP 返回 `$null`）。
- `$gn.CopyHere($srcItem, 20)` 发起复制；系统弹出「正在复制…」对话框（flags 无法抑制），22:53 约 60% / 剩余 4 分钟，22:54 剩余 2 分钟，22:57:30 前后对话框消失。

## 结果

- 落地：`/switch/galnx-nsp/IROSEKA_FHD-010047420000a000.nsp`（`CopyHere` 不重命名，按源文件名落地；复制前目标目录为空）。
- 校验：`ShellFolderItem.Size` 对 WPD 恒为 0，改用 `ExtendedProperty('System.Size')` = **9,979,496,664**，与本地 NSP 字节数一致（见 `list-after.txt`）→ 未被 4 GiB 限制截断。
- 本地产物 sha256 `6af9072904ac6bb57cb12753edd43a70d29e1bd87d51ea8198f31f6140ee130b`，见 `docs/builds/026-rfvp-async-watchdog.md` §4.3。

## 文件

| 文件 | 说明 |
| --- | --- |
| `mtp-upload.log` | 上传脚本日志：BEFORE/COPYHERE_ISSUED/轮询（MTP 复制期间目录项 `Size` 显示 0 属正常） |
| `copy-dialog-2253.png` | 系统复制对话框截图（约 60%，剩余约 4 分钟） |
| `copy-dialog-2254.png` | 系统复制对话框截图（剩余约 2 分钟） |
| `list-after.txt` | 复制完成后 `ExtendedProperty('System.Size')` 校验输出 |
| `SHA256SUMS.txt` | 上述文件哈希 |

## 复验指引

1. 默认启动：不创建/删除 `sdmc:/switch/rfvp/async.txt`（默认关），应正常进入标题与正文，不黑屏。
2. async A/B：在 `sdmc:/switch/rfvp/async.txt` 写入 `on` 后重启；若仍黑屏，把 `sdmc:/switch/rfvp/async_status.txt`（现在带 `stage=`）回传，即可定位卡在 read/decode/publish 哪一步；若 watchdog 生效，画面应在 ~3 s 内恢复且 `async.txt` 被自动关闭（`enabled=0`）。
3. 测完请回传 `async_status.txt`、`debug_report.txt`、`perf_slow.log`。
