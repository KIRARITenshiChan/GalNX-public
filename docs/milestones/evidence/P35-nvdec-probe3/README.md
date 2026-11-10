# P35 — NVDEC 探针（probe1/2/3）证据

关联记录：`docs/builds/041-nvdec-probe3.md`；源码与上游 pin：`docs/research/nvdec-probe3/`。

## 文件

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `nvdec-probe3.txt` | 2,453 B | Citron 跑探针 3 的日志（软解，750 帧全片） |
| `citron-result.json` | 2,903 B | Citron harness 运行报告（窗口标题 / nonblack_ratio / 步骤） |
| `citron-window-p03.png` | 3,196,914 B | Citron 窗口截图（1080p 视频在 1280×720 窗口中播放） |
| `probe3-frame180.png` | 759,901 B | 探针第 180 个显示帧（BMP 转 PNG），用于与 ffmpeg 参考对比 |
| `ffmpeg-frame180.png` | 693,097 B | ffmpeg 解码序第 180 帧（参考） |

探针 NRO 本身不入库（9.4 MB），哈希：`nvdec-probe3.nro` 9,408,568 B sha256 `c13b2aaecb19cda40013a661dbf3a27d640f18b7c08c4125fc57473997a804a8`。

## 关键数字（Citron，无 NVDEC，走软解）

```
frames=750 hw_frames=0 sw_frames=750
hw_used=0 fps_overall=18.896 wall_ms=39691.0
DECODE   avg=19.926ms min=4.429ms max=63.357ms
TRANSFER avg=0.000ms min=0.000ms max=0.000ms
CONVERT  avg=27.779ms min=24.492ms max=43.914ms
mode=gles accelerated=1 headless=0
```

## 像素正确性

- 探针第 180 个显示帧 ≡ ffmpeg 解码序第 **179** 帧（B 帧 reorder 差 1）；
- 对齐后 Y 平面：mean_abs=5.25、PSNR=32.42 dB；
- 再做仿射拟合 `y_ff = 0.8661·y_probe + 15.72`（BT.601 limited→full 标准映射）后：**mean_abs=0.21、PSNR=58.47 dB**；
- 结论：解码内容与 ffmpeg 参考一致，差异仅来自色彩范围转换。

## 真机状态

真机测试包 `E:/galnx-build/nvdec/device-test/`（含 NRO + 25 s 1080p VC-1 样片 + README）；等待用户运行并回传 `/nvdec-probe3.txt` 与 BMP。
