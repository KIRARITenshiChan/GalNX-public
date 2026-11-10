# rfvp async（v1.1.0-test）真机缺陷记录

日期：2026-11-05
状态：**真机验收未通过 → 已回退 v1.0.9（async off）**
相关：[029-rfvp-async-fix.md](../builds/029-rfvp-async-fix.md)、[perf-02-device-v109.md](perf-02-device-v109.md)、证据 [P22d-async-device-fail](../milestones/evidence/P22d-async-device-fail/)

## 1. 用户报告（真机，IROSEKA v1.1.0-test，async.txt=on）

1. **部分 CG 不显示**：只显示对话框与其它 UI；
2. **残留**：任何界面打开再关闭后，残留图像留在 UI 下，直到下一个可显示图像出现；
3. **OP 被跳过**：序幕转第一章的 OP 直接略过。

## 2. 设备日志证据

`E:/galnx-build/p21/device-logs/`（已归档 P22d）：

| 事实 | 数值 |
| --- | --- |
| async 状态 | `enabled=1 create=0x0 start=0x0 hb=1020000 stage=0 cpu=1 wdt=1 main=61018 stalled=0` |
| 帧 | `frame=61020 status=0 async=1`，59.0 fps，slowest 33.8 ms |
| 日志错误 | 3,547 条：`Invalid duration` 2,351、`Invalid id` 665、`prim_set_uv: invalid v : Nil` 461、`graph_load: invalid id : Nil` 44 |
| 异步任务 | 整段只有 3 次：`graph/opt_sheet1` 1.9 MB 182,682 us；`graph_vis1/KANA_e01b` 8.3 MB **589,851 us**；无 fallback 记录 |
| 长时间 pending | `[async] tick seen=0 pending=1` 连续多帧（至少 30+ 次采样）后该任务才完成 |

## 3. 根因（源码级）

`crates/rfvp/src/subsystem/components/syscalls/graph.rs:1046-1058`：大图（≥1 MiB）走
`async_decode::submit_graph(...)` 成功后**立即 `return Ok(Variant::Nil)`**，注释写明
"keep drawing the previous texture and apply the new one when it is ready"。

问题在于 rfvp 的绘制模型是"每帧按当前 id 重画"：

- 纹理尚未 decode 完（设备上 8.3 MB 图要 **0.59 s**）→ 该 id 没有可用纹理 → 该层不画 → **CG 不显示**；
- 图层不画时不会清屏/填底 → 画面上保留上一帧像素 → 这就同时解释了 **UI 关闭后的残留**（UI 最后一帧的像素留在目标缓冲里，直到下一张能画的图覆盖）；
- 若 id 在 decode 完成前被脚本重新分配，`requested_matches` 不匹配 → 结果被丢弃 → 该 CG **整段都不会出现**（`graph_load: invalid id : Nil` 44 条即此类绘制尝试）；
- 队列是单 worker 串行，CG 场景往往连发 2–4 张大图（本作 patch/立绘/CG），后一张的等待进一步拉长。

结论：这不只是锁的问题；**"先返回 Nil、稍后再贴图"的延迟绘制语义与 rfvp 的按 id 逐帧重画模型不兼容**，是 P18 设计缺陷，Citron 上因解码快、场景切换慢而未暴露。

OP 跳过：本日志中没有任何 movie/opening 相关记录，无法据日志定因；推测同一路径（大资源延迟/丢失后场景直接推进）。列为 Phase B 待查。

## 4. 处置（已执行）

- 设备回退：重装 v1.0.9 NSP（async 永久 off，同步解码），恢复"CG 一定显示"的确定性行为；
- 代码回退：v1.1.0-test 不并入主线；增量补丁 `rfvp-async-fix.patch` 只作为实验记录保留，**不推送**；
- 汉化不受影响：Sakura 中文 NSP（1.0.1/1.0.2）用 v1.0.9 运行时构建，CG/OP 行为同旧版。

## 5. 后续修复方向（P25）

按优先级：

1. **prefetch-only async**：async 只负责"预取"（KIND_GRAPH_PREFETCH），真正的 graph_load 永不返回 Nil——命中缓存就用，未命中就同步 decode（可选等待预取完成，超时即同步）。这样保住 X↔Xb、立绘 sheet 之类的可预测开销，又不牺牲正确性；
2. **延迟层补偿**：若必须保留 on-demand 延迟，则在不画该层时用上一帧快照覆盖该区域（或整帧 copy），杜绝 UI 残留；并在 apply 失败/不匹配时强制同步重解一次；
3. 单 worker 队列改为"按 path 去重 + 优先级"（on-demand 优先于 prefetch），避免 CG 连发时排队；
4. OP/movie 路径独立排查（是否走 graph 大资源、还是 mpg 播放窗口缺失）。

## 6. 复现

装 v1.1.0-test NSP → `sdmc:/switch/rfvp/async.txt` 写 `on` → 进正文推进到含 CG 的场景（序幕→第一章）→ 观察 CG 缺失与 UI 残留；取 `debug_report.txt` 搜 `[async] tick seen=0 pending=1` 与 `graph_load: invalid id`。

## 7. 证据文件

`P22d-async-device-fail/`：async_status.txt、frame_status.txt、debug_report.txt（118,677 B）、perf_slow.log（525,092 B）、SHA256SUMS.txt。

## 8. 补充证据：真机看门狗曾触发（2026-11-06 取证）

设备 `sdmc:/switch/rfvp/` 下存在 `watchdog_status.txt`（60 B，v1.1.0-test / v1.1.1-test 运行遗留）：

```
frame=4133 stalled_ms=3000 stage=0 hb=85083 enabled=1 cpu=1
```

- 该文件由**独立看门狗线程**写出（3 s 未看到主线程帧计数推进才落盘），因此可证明：真机运行时主线程确实发生过 ≥3 s 的阻塞，而不只是「绘制延迟」。
- 已反向取回并归档为 `P22d-async-device-fail/device-watchdog_status.txt`（sha256 `422e818ac405e747dbba7aaf94162ac5b2109364e561d83aaf92243846fa0b60`）。
- 对 v1.1.2 验收的影响：MTP 无法删除设备文件（CopyHere 对已存在文件静默跳过，InvokeVerb('delete') 会弹模态框），因此该文件会残留。验收时用「内容是否变化」判定：若运行后仍是 `frame=4133 … hb=85083`，说明没有新的 3 s 阻塞；若帧号/hb 变化，即为新发生的卡顿，按失败处理。

