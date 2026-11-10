# P26b Album 差分复现路径（坐标取证）

- 目的：为 P26（CG 差分切换卡顿）与后续回归提供可复用的界面坐标，避免每次盲点。
- 环境：Citron Nightly 0237a9b88 + IROSEKA rfvp NRO，窗口 1728x1016（1:1）。
- 截图：`title-menu.png`（标题）、`album-menu.png`（ALBUM MODE）、`cg-grid.png`（CG MODE 网格）。
- 来源运行：`E:/galnx-build/p26/run-album-phase2/20261106-044324-rfvp/`。

## 坐标（点击点 = 元素中心）

| 界面 | 元素 | 坐标 |
| --- | --- | --- |
| 标题菜单 | New Game / Continue / Album / Option / Exit | (1390,534) / (1390,614) / **(1390,694)** / (1390,770) / (1390,850) |
| ALBUM MODE | CG MODE | **(1390,281)** |
| ALBUM MODE | SOUND MODE / BACK | (1390,416) / (1390,676) |
| CG MODE 网格 | 第一个已解锁 CG（左上） | **(540,270)** |
| CG MODE 网格 | 列中心 x / 行中心 y | 540/745/950/1155/1360；270/395/520/645 |

## 操作流

标题 → Album → CG MODE → 点第一个 CG → **按 Enter（A 键）或右键（ZL）** 播下一张差分（左键=放大）→ 切换完再按一次回列表。

## 说明

- 该路径仅用于导航；性能判定必须在真机进行（Citron 宿主文件系统读 8 MB 只需个位数毫秒）。
- 本目录截图取自 1.1.2-test 源码构建，界面与 1.0.9/1.1.1-test 一致。