# P22d：IROSEKA v1.1.0-test 真机 async 缺陷取证（2026-11-05）

## 结论
async=on 的 v1.1.0-test 在真机上出现：①部分 CG 不显示（只剩对话框/UI）②界面开合残留旧像素 ③序幕→第一章 OP 被跳过。
机制本身没有冻结（watchdog/心跳正常），缺陷来自 P18「延迟绘制」语义与 rfvp 每帧按 id 重画模型不兼容：
`crates/rfvp/src/subsystem/components/syscalls/graph.rs` 对大图（>= 1 MiB）submit 后返回 Nil，下一 tick 才 apply；纹理未就绪/被重新分配时该层不画且不清屏。

## 设备日志（IROSEKA v1.1.0-test，async=on）
- `async_status.txt`：`enabled=1 create=0x0 start=0x0 hb=1020000 stage=0 cpu=1 wdt=1 main=61018 stalled=0`
- `frame_status.txt`：`frame=61020 status=0 async=1`；debug_report 尾部 59.0 fps / slowest 33.8 ms
- `debug_report.txt` 共 3,547 条：`Invalid duration` 2,351、`Invalid id` 665、`prim_set_uv: invalid v : Nil` 461、**`graph_load: invalid id : Nil` 44**、`history_set` 26
- 全程仅 3 次异步解码：`graph/opt_sheet1` 1.9 MB 182,682 us；`graph_vis1/KANA_e01b` 8.3 MB **589,851 us**
- 无 `last_error.txt`（未崩溃）

## 回退安装
`rollback-install-v1.0.9.log`：21:34:06 向 `5: SD Card install` 发起 IROSEKA v1.0.9（9,979,495,640 B，sha256 `726bb2d1b0494256b5e5b12ca9d8e08b053ab56022593f562762d256c0d3c0d9`）覆盖安装，复制对话框持续 323 s（saw_dialog=True），21:39:29 结束。
安装后应恢复旧行为（同步解码、CG 一定显示）；v1.1.0-test 不并入主线，补丁仅作实验记录。

## 关联
- 缺陷记录：`docs/experiments/rfvp-async-device-defect.md`
- 返工任务：task-53（P25，async 只做 prefetch + 延迟层补偿）
- 计划 v1.23 决策 37：async 只允许预取