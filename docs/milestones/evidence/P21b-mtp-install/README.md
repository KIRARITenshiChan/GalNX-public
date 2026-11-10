# P21b：IROSEKA v1.0.9 与 Sakura NSP 的 MTP 安装记录（2026-11-05）

目的：把两个自包含 NSP 复制进 DBI 的 `5: SD Card install` 虚拟目录，由 DBI 自动安装。

| 项 | 值 |
| --- | --- |
| 宿主脚本 | `E:/galnx-build/p21/mtp-install-two.ps1` |
| 日志 | `device-install.log`（本目录） |
| IROSEKA | `IROSEKA_FHD-010047420000a000.nsp` 9,979,495,640 B sha256 `726bb2d1…` |
| Sakura | `SAKURA_MOYU-010047420000c000.nsp` 7,990,691,032 B sha256 `d2d42783…` |

## 观察
- 06:31:53 对 IROSEKA 发起 `CopyHere`；06:35:59 截图显示复制进度约 85%（约剩 3 分 30 秒）。
- 06:37:04 对 Sakura 发起第二个 `CopyHere`；两个复制对话框并行，随后 IROSEKA 对话框显示「正在等待: Switch 正忙。」——说明 DBI 已开始处理 IROSEKA 安装。
- 06:42:05 Sakura 复制等待超时；06:43:40 两个对话框均消失，复制结束。
- 脚本用 Shell 枚举 `5: SD Card install` 始终为 0 项（DBI 该目录是写入即安装的虚拟目录，文件不落盘），因此 `WARN ... not confirmed` 不是失败，只是无法用枚举确认。

## 无法从宿主侧确认安装结果的原因
- 本机 Switch 使用 emuMMC；安装后的 title 落在 emuMMC 的 raw 分区内，MTP 暴露的 `1: SD Card` FAT32 分区剩余空间与 `Nintendo/Contents/registered` 都不会反映 emuMMC 内的安装。实测复制前后 FAT32 剩余空间均为 67,256,713,216 B。
- 结论：最终验收必须在 Switch 主界面确认两个新图标，并启动游戏；确认清单见 `docs/pilot/P4-device-runbook.md` §13.2/§13.3。

## 证据文件
- `copy-iroseka-waiting.png`：IROSEKA 复制对话框（「正在等待: Switch 正忙。」）。
- `copy-sakura.png`：Sakura 复制对话框（约剩 1 分 45 秒）。
- `device-install.log`：脚本日志（含两条 `not confirmed` 警告与 `ALL_FINISHED`）。

## SHA256SUMS
```
fb4084be8a4cf147a6fd779ef7a0ba568ccd063f6e759d0d2d2b5806d81f7d04  copy-iroseka-waiting.png  30517
d4707d95c13061e36185940e82383c390c431216bbf148091b21b8d9f53b6ec1  copy-sakura.png  33384
04aed061232f6c62f754e9b318432cc56a1a83da34ad8a3e9736634ec946a2a4  device-install.log  636
```
