# P44 · もゆ标题粒子修复证据（P41）

日期：2026-11-10
相关：`docs/builds/049-p41-snow-particles.md`、`docs/builds/patches/rfvp-switch/P41-snow-particles.diff`

## 能证明什么

1. 修复前（P40c 基线 + 仅放宽 arg10）もゆ标题只画出 motion 0 的 60 个 flake：`citron-title-prefix.png`。
2. 只修「PrimSetSnow 第二参数没存 slot」后两套都进入绘制，但 1024 个 flake 里约 205 个可见（变体贴图未上传被丢弃）：`citron-title-double.png`。
3. 再加「变体贴图缺失时回退 base 贴图」后 1024/1024 全部绘制：`citron-title-fallback.png`；清理全部诊断插桩后的干净构建同样是 1024/1024：`citron-title-clean.png`。
4. 打包进自包含 NSP 后（romfs:/game，无 SD 覆盖）仍保持 1024/1024：`nsp-smoke-title.png`，对应 `nsp-romfs-debug-report.txt`。
5. 统一时序差分指标（间隔 3 s 的两张标题截图，区域 x=40..0.45W、y=40..0.60H，灰度差 >25 的采样点，每万像素）见 `title-particle-motion.txt`：1.10 → 5.56 → 39.49（干净构建 32.84、NSP 33.19）。
6. 干净构建的 debug_report 里 `snow:` 报错 0 行（`citron-clean-check.txt`），说明 `Snow()` 不再被参数校验拒绝。
7. `citron-movie02-debug-report.txt` 为 `movie_debug.txt` 调试通道（index=2）验证：播放 `movie/02_h264.mp4`（真结局 OP），证明调试播片通道与 H.264 管线对第 2 个视频同样成立。

## 不能证明什么

- 不能证明真机观感与 PC 版完全一致：真机尚未验收，且 PC 版粒子运动轨迹/速度未做逐帧对齐（用户 m38513 明确不追速度）。
- 不能证明变体贴图的原始语义：脚本只 `GraphLoad(1592/1593)` 两张图，而 `variant_count=5`；当前实现把变体当作独立 graph id，缺失时回退 base 图。真机版本的原版行为未证实。
- 截图来自 Citron（软解、无 NVDEC），颜色/密度可作为管线证据，帧率数值不可当真机性能。

## 文件

| 文件 | 说明 |
| --- | --- |
| `citron-title-prefix.png` | 修复前：只画 motion 0（60 flake） |
| `citron-title-double.png` | 双 snow slot 修复后：约 205/1024 |
| `citron-title-fallback.png` | 变体回退后：1024/1024 |
| `citron-title-clean.png` | 清理插桩后的干净构建 |
| `nsp-smoke-title.png` | 1.3.1-test NSP 经 romfs 启动的标题画面 |
| `snow-compare-3up.png` | 三态对比拼图（前/205/1024） |
| `title-particle-motion.txt` | 统一时序差分指标原始输出 |
| `citron-clean-check.txt` | 干净构建 snow 报错统计 |
| `citron-clean-debug-report.txt` | 干净构建 Citron debug_report（1081 行） |
| `nsp-romfs-debug-report.txt` | NSP romfs 冒烟 debug_report |
| `citron-movie02-debug-report.txt` | movie/02（真结局 OP）调试通道验证日志 |

## 复算

```bash
python /e/galnx-build/p41/metric_all.py   # 重新生成 title-particle-motion.txt
```
