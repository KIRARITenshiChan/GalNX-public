# MTP（WPD / Shell COM）传输与覆盖写 —— 真机安装通路实测（2026-11-08）

真机走 USB 时，DBI 的 FTP 模式（192.168.31.254:5000）并非总在开启；而 Windows 对 Switch 的 MTP
（WPD）暴露是常驻的。本文记录只用 Windows 自带 Shell COM（WPD）完成「投放 NSP 自动安装」
「改写 sdmc:/switch/… 下的小配置文件」「回读校验」的可复现配方，以及在 P33 真机交付里踩到的坑。

## 1. 设备与驱动器映射

- MTP 设备名 <code>Switch</code>（usb vid_057e pid_201d，实测 serial xaj40080865533）。
- 设备内暴露多个「盘」条目，名字本身就说明用途：

| 条目 | 用途 | 实测容量 / 余量 |
|---|---|---|
| <code>1: SD Card</code> | SD 卡普通存储（sdmc:/ 根） | cap 127,901,106,176 / free 49,386,094,592 |
| <code>5: SD Card install</code> | **放进这里的 NSP 会被自动安装**（占位文件 Place NSP, NSZ, XCI, XCZ or MSP files here） | 同 <code>1: SD Card</code>（同一张卡） |
| <code>6: NAND install</code> | 装到本体的投放目录 | free 27,602,911,232 |
| <code>7: Saves</code> | 存档 | — |
| <code>8: Album</code> | 相册（实测空） | — |
| <code>相册工具</code> / <code>金手指和MOD放这</code> | 工具 / 金手指 | — |

结论：**给真机装 NSP 不需要 FTP** —— 把 NSP 复制到 <code>5: SD Card install</code> 即可，安装由设备侧自动完成。

## 2. 定位与列目录（PowerShell + Shell.Application）

```powershell
$shell = New-Object -ComObject Shell.Application
$pc    = $shell.NameSpace(17)                       # 17 = ssfDRIVES（此电脑）
$sw    = $pc.Items() | Where-Object { $_.Name -eq "Switch" }
$sd    = ($sw.GetFolder.Items() | Where-Object { $_.Name -eq "1: SD Card" }).GetFolder
$switch = ($sd.Items() | Where-Object { $_.Name -eq "switch" }).GetFolder   # sdmc:/switch
$rfvp   = ($switch.Items() | Where-Object { $_.Name -eq "rfvp" }).GetFolder # sdmc:/switch/rfvp
$rfvp.Items() | ForEach-Object { $_.Name }
```

WPD 的层级用 FolderItem.GetFolder.Items() 逐层下钻；没有盘符，不能直接 Get-ChildItem。

## 3. 两个必须知道的属性 / 行为

1. **大小只能用 ExtendedProperty("System.Size")**：WPD 项的 FolderItem.Size 恒为 0，
   用 $item.Size 判断「文件有没有写全」会永远得 0。
2. **CopyHere 是异步的**：调用立刻返回，真正的复制在 Shell 的进度对话框里继续（对话框标题
   「正在复制...」，窗口类 #32770，进程是发起复制的 powershell.exe）。
   → 发起脚本必须**保持存活**到复制完成，否则复制可能中断。

复制（本机文件 → 设备目录）：

```powershell
$dest = ($sw.GetFolder.Items() | Where-Object { $_.Name -eq "5: SD Card install" }).GetFolder
$srcFolder = $shell.NameSpace("E:\galnx-build\p33\out2")
$dest.CopyHere($srcFolder.ParseName("IROSEKA_FHD-010047420000a000.nsp"), 20)  # 20 = 0x14 无确认 / 无动画
```

## 4. 坑一：同名文件不会被覆盖（静默跳过）

CopyHere($item, 20) 对**已存在**的目标是「静默跳过」，不报错也不覆盖：
P33 真机联调要写 debug.txt 的 movie=1，原文件 1 B 内容 1；复制后回读仍是 1（1 B），
直到改用下面的「先改名再复制」才成功（新文件 8 B = movie=1 + LF）。

**可行覆盖配方（WPD 支持重命名）**：

```powershell
$dbg = $rfvp.Items() | Where-Object { $_.Name -eq "debug.txt" }
$dbg.Name = "debug.txt.old"        # 改名到旁路名字，WPD 会真正改掉
Start-Sleep -Seconds 3             # 等设备侧提交
# 重新取一次目录项（缓存项已失效），再 CopyHere 新文件
```

失败过的替代方案（不要再用）：删除走 InvokeVerb 会弹交互式确认框；CopyHere 换 flags 也不覆盖。

## 5. 坑二：长拷贝期间 WPD 目录枚举整体不可用

9.98 GB 拷贝进行中，任何 Shell 实例的枚举都会失败：持旧 FolderItem 的会抛
「You cannot call a method on a null-valued expression」（GetFolder 返回 null），
**每轮新建 Shell.Application 也一样**（实测 `mtp-monitor.ps1` 连续输出 `no install folder`）。
此时唯一可用的进度来源是 Shell 的复制对话框：

- window_list 找标题含「正在复制」的窗口（类 #32770，owner 是发起复制的 powershell.exe）；
- window_capture 截 client 区域即可读到文件名、目标路径、剩余时间与进度条
  （P33 证据 <code>E:/galnx-build/p33/evidence/mtp-copy-dialog.png</code>，45% 时 ETA 8 分 30 秒）。
- 拷贝结束后再重新枚举校验大小（届时 WPD 恢复可用）。

## 6. 回读校验

```powershell
$destLocal = $shell.NameSpace("E:\galnx-build\p33\pull")
$destLocal.CopyHere($rfvp.Items() | Where-Object { $_.Name -eq "video.txt" }, 20)
```

本机再 od -c / sha256 比对。P33 实测回读：video.txt = 480 + LF（4 B）、
debug.txt = movie=1 + LF（8 B）、async.txt = on（2 B）。

## 7. 实测耗时

- v1.0.8 NSP 9,979,496,664 B：MTP 投放约 10 分钟（docs/builds/026 §4.4）。
- P33 NSP 9,977,492,184 B：复制对话框 ETA 约 8 分 30 秒（进度 45% 时读数），与上一条同量级。
- 对照：DBI FTP 上传同一量级 NSP 约 1,640 s（5.8 MiB/s）；MTP 与之相当，但**不需要设备进 FTP 模式**。

## 8. 与 prod.keys 的关系

本通路只做文件搬运与安装，**不接触 prod.keys / title.keys**；签名/加密仍由设备侧 CFG 承担。
NSP 本身由 galnx package nsp build 用显式 --keyset 产出的未签名自包含包（见 docs/builds/005）。
