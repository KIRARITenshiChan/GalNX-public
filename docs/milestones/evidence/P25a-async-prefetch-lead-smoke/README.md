# P25a — v1.1.1-test（prefetch-only）Lead 独立 Citron 验收

日期：2026-11-05 23:32–23:35
引擎：rfvp 1.1.1-test（prefetch-only async，async.txt=on）
产物 NSP：`E:/galnx-build/p25/out/IROSEKA_FHD-010047420000a000-v1.1.1-test.nsp`
9,979,496,152 B sha256 `bf83fa6edb0134c60c04756b6c02c21b191b43e3567561e68628962b4ded2e5b`

## 路线（与 async-fix 主证据一致，但由 Lead 独立执行）
1. 启动 NSP → 标题（60 FPS）
2. 点击 Continue(1386,638) → 读档列表（DATA_001 有存档）
3. 点击 DATA_001(420,300) → 等 18 s → **CG 完整显示**（真红 CG，无缺层/无残留）
4. 连续 6 次 `key:C` 推进 → CG 场景内文本正常、场景切换后画面正常

## 结论（对应 P25 真机待验 4 项中的 Citron 可验部分）
- ① CG 正常显示：**PASS**（`step-08-f2-cg.png` sha `68e3eeaa…a1f5`，`step-14-f4.png` `f6df85f7…49fd`）
- ② UI 无残留：**机制上已消除**（prefetch-only 不再有「不画该层也不清屏」的延迟路径）；关闭动作仍未做专项点击探针（输入坐标问题，非应用缺陷）
- ④ async=on 不冻结：**PASS** — `async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=105000 stage=0 cpu=1 wdt=1 main=6785 stalled=0`；`frame_status.txt` = `frame=6840 status=0 async=1`；`last_error.txt` 不存在；35 个输入步骤 0 失败；60 FPS
- ③ OP：Citron 构建无 movie decoder，预期仍跳过（与 async 无关）

## 证据文件与 sha256
- step-02-f0-title.png `7e2faa75…0882d`
- step-05-f1-list.png `d3221ccc…f8918`
- step-08-f2-cg.png `68e3eeaa…a1f5`
- step-14-f4.png `f6df85f7…49fd`
- step-26-f8.png `d7b3d185…335e68`
- async_status.txt `4b90423d…66d859`；frame_status.txt `985a693f…e4e4d1`
- 全量校验见 `SHA256SUMS.txt`；原始日志 `lead-v111c-smoke.log`、`debug_report.txt`、`perf_slow.log`

## 限制
- Citron 与 audit-engines 的 baseline 轮在 23:33–23:34 发生单实例重叠；本目录证据窗口标题为 1.1.1-test、时间戳连续，按有效记录。
- 真机 10 分钟验收仍待用户执行（见 032 §5）。
