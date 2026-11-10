# P20b · 真机崩溃报告取证（2026-11-01）

来源：Switch 真机 `sdmc:/atmosphere/crash_reports/`，经 MTP（Shell COM `GetFolder` + `CopyHere(20)`）拉到 `E:/galnx-build/p20/device-logs/crash/`，再复制入库。

## 文件

| 文件 | 大小 | 进程 / Program ID | 结论 |
| --- | --- | --- | --- |
| `01793296796_010000000000100f.log` | 42,493 B | `LibAppletOf` / `010000000000100f` | 系统 applet（library applet）崩溃，`Result 0x0 (2000-0000)` User Break，模块 `[86daffa6]`，**与本项目无关** |
| `01793356593_01009bc00c38a000.log` | 28,852 B | `hbloader` / `01009bc00c38a000` | hbmenu/sphaira 崩溃：`Result 0x4A8 (2168-0002)`、`Data Abort`、`Fault Address 0`、PC `sphaira + 0x16af60`，模块只有 `sphaira`，**与本项目无关** |
| `01793356593_01009bc00c38a000.jpg` | 172,310 B | — | 上述 hbloader 崩溃的截图 |

## 为什么与本项目无关

- 我们的 NSP Title ID 是 `010047420000a000`（IROSEKA FHD），两份报告分别是 `010000000000100f`（系统 applet）与 `01009bc00c38a000`（hbloader），**没有一份属于我们的程序**。
- 真机 `/switch/rfvp/last_error.txt` 不存在 → rfvp 侧没有 Rust panic 记录。
- 因此 v1.0.6「进游戏黑屏」**不是崩溃**，而是挂起/空渲染（详见 `docs/builds/026-rfvp-async-watchdog.md` §2）。

## 限制

- crash report 只覆盖 Atmosphère 捕获到的异常；hang（无异常退出）不会生成报告，这正是黑屏的情形。
- hbloader（sphaira）本身稳定性问题不属于 GalNX 范围，但会影响真机上传/安装流程（用 DBI FTP 或 MTP 时注意）。