# P34：WMV2 OP 左缘马赛克修复证据（v1.1.10-test）

背景/根因/修法见 `docs/builds/040-wmv2-left-edge.md`。本目录只放**决定性证据**，完整截图/探针产物在
`E:/galnx-build/p33/`（不入库）。

## 文件

| 文件 | 说明 |
| --- | --- |
| `old-left-edge.png` | 修复前：`docs/milestones/evidence/P33a-op-quality/n03-op-scene.png` 的视频区左缘裁 140 px ×3 放大（可见竖直一列马赛克方块） |
| `new-left-edge.png` | 修复后：同一区域（Citron run `20261108-014309-rfvp` 的 `step-20-f10.png`），干净天空渐变 |
| `fixed-op-frame.png` | 修复后完整帧（Citron 截屏，854×480 视频上屏） |
| `citron-result.json` | Citron NRO 运行结果（status=loaded、nonblack_ratio=0.9018） |
| `movie-log-lines.txt` | `debug_report.txt` 的 Movie 行（打开 `01_q480.wmv`、854×480、decode_us/convert_us、音轨） |

## 数值（宿主 oracle，见 040 §5.1）

同一帧（pts=30000）vs ffmpeg 解出的 Y 平面：

- mean |Δ| 2.918 → **1.470**；`|Δ|>32` 像素 6,777（1.653%）→ **30（0.007%）**
- 左侧 12 列均值 |Δ| 63.35 → **3.36**；右缘 0.22 → 0.18（无回归）
- 「行首被复写」检测：29/58 行 → **0/0**
- 输出仍为 854×480（coded 864×480 解码后裁剪）

## 复现

```bash
cd /e/galnx-build/p33/probe-wmv && cargo build --offline    # 宿主探针（path 依赖引擎 crate）
bash /e/galnx-build/p33/run-fix.sh /e/galnx-build/p33/lto3/rfvp.nro   # Citron detach
```
