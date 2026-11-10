# M2c 证据：KAG3 输入语义 Citron 实测（2026-10-30）

对应文档：docs/milestones/M2-kag3-input.md 第 8 节；任务：task-18（M2-c）。

- 被测对象：E:/galnx-build/m1-krkrsdl2/build5/krkrsdl2.nro（17,907,245 B，sha256 e324c2d08b0a2d46…；内嵌 KAG3 DEMO data-withfont.xp3）
- 模拟器：Citron Nightly main-0237a9b88；窗口 1728×1016，游戏区 y=70..950，diff 采样 380,160 点
- 注入：鼠标 SendInput mouse_event（click）与键盘 PostMessage WM_KEYDOWN/UP（Vks）；Citron 键盘→手柄 C=67(A)、X=88(B)、V=86(X)、Z=90(Y)

## 目录清单

| 证据目录 | run id | 原文件数（workspaces） | status | 仓库保留的关键截图 |
| --- | --- | --- | --- | --- |
| M2c-click-link-20261030-021105 | 20261030-021105-krkrsdl2 | 6 | loaded | 1364390 B / 61d60a6de38bc8ab0d0b0fca8f510e117b6c0695312a32629b07da2ec512cad5 |
| M2c-title-focus-confirm-20261030-021602 | 20261030-021602-krkrsdl2 | 8 | loaded | 1002571 B / a748b8ee38ba5d481d374864de97ae4eb029a950f16618cb8bc96dc30ba74c9f |
| M2c-body-semantics-20261030-021958 | 20261030-021958-krkrsdl2 | 12 | loaded | 1381441 B / 372944437cbf379f4bde469afc3db148d9f7c5143e88cd74974d8914fcff6830 |
| M2c-x-history-20261030-022129 | 20261030-022129-krkrsdl2 | 10 | loaded | 1381383 B / de1960129998329eb9f39b124ef44ce2794b8e8242f62cb5232f61df79ba4f19 |

仓库内每个目录只保留 result.json（机读结果）、run.log、citron_log_slice.txt 与一张关键截图（表中最后一列）；完整文件集（含 window.png、window-before-input.png 与全部分步 step*.png）位于本机 workspaces/citron-harness/runs/<run id>/（gitignore，不入库）。

## 关键数值（详见文档第 8.2 节）

- 标题链接点击：diff 0.494465（nonblack 0.7159→0.7193）
- 方向键焦点移动：0.007397 / 0.016511；A 确认进正文：0.554372
- 正文 A 推进：0.556076（0.7186→0.7211）；ESC 隐藏消息层：0.556076（→0.7186）；再 A 恢复：0.556076（→0.7211）
- X（PAD3 历史）：0.000000 / 0.0002（无可见变化，负面发现 U12）
- 鼠标推进：0.556042；键盘 C×3：0.556042

## 未验证

- 全部为 Citron 模拟器，非 Switch 真机；触摸/摇杆轴/ZL-ZR/PLUS-MINUS 真机索引未验证。
- 失败模式与实验规程见文档 8.4（含 2026-10-30 02:16:50 误注入事故记录）。
