# P41 · P40b NV12 颜色修复证据（Citron 影子验证）

- 日期：2026-11-09
- 相关：`docs/builds/047-p40b-nv12-colour-fix.md`、`docs/builds/patches/rfvp-switch/P40b-nv12-color.diff`
- 状态：Citron 影子验证 PASS；真机硬解路径尚待用户验收（v1.2.1-test）

## 这批文件证明什么

1. P40 真机 OP 颜色异常的根因是 `nv12_row_neon()` 的 UV 读取步进错误：每 16 个输出像素只前进 8 个交织 UV 字节（`uvr + (i >> 1)`），色度横向被拉伸 2 倍，亮度平面不受影响，因此表现为「黑白底图正常 + 彩色层被巨幅拉伸」。
2. 修复后（`uvr + i` / `uvr + i + 8`），把 Citron 软解得到的 planar YUV420P 帧重新打包成 NV12、再喂给同一份硬件 NV12 kernel，其 RGBA 输出与 planar kernel 的 RGBA 输出 **逐字节相同**：`citron-nv12-shadow-lines.txt` 中 103 条记录全部 `match=1 diff_bytes=0`（覆盖 frame 1 … 2940，每 30 帧一次，含两次 FNV-1a 64 位校验）。
3. 颜色管线（NV12→RGBA、帧推进、OP 内容）在 Citron 影子环境下仍然正确：截图 `citron-nv12-op-credits.png` / `citron-nv12-op-cg.png` 显示 OP 的 staff credits 与原画画面对应位置的颜色正常。

## 这批文件不能证明什么

- **不能证明真机硬解路径的颜色已经正确**：Citron 没有真实 NVDEC，NRO 冒烟走的是 `h264_sw.txt` 强制软解 + planar 分支（`hw=0`），硬件帧（`AV_PIX_FMT_NVTEGRA` + `av_hwframe_transfer_data` 后的 NV12）从未在真实硬件上出现。影子测试只证明 kernel 本身对 NV12 布局的解读正确，不能替代真机验收。
- 不能证明 P40 版本在真机上「除颜色外一切正常」——那是用户 m36342 的观察（不慢放），本目录不重复取证。
- 不能证明 `uv_stride` 在真机硬件帧上一定等于宽度；影子测试按显示宽度重新打包（stride = width = 1280）。若真机 `linesize[1]` 有 padding，kernel 仍按 stride 逐行取，但这一点只能由真机验证。

## 环境

| 项 | 值 |
| --- | --- |
| 模拟器 | Citron nightly 0237a9b88（HLE，无真实 NVDEC） |
| 构建 | `bash /e/galnx-build/p40/build.sh`，BUILD_EXIT=0，NRO sha256 b93f34e3f4b1f50f4c0d43f1817199fbf39c14431d1f78969f5f2e52ebbdbee9 |
| 资产 | `movie/01_h264.mp4` 108,361,267 B sha256 bddf82fc7e78e256d812051a4f548c2dce07d8cdcda6c80562ea588f32757bad |
| 开关 | `sdmc:/switch/rfvp/h264_sw.txt`=soft（强制软解）、`h264_nv12_selftest.txt`=on（影子比较）、`debug.txt`=shot=900/movie=1、`video.txt`=720 |
| run_dir | `E:/galnx-build/p40/run-citron-04/h264/20261109-123716-rfvp`（中间产物，未入仓） |

## 文件

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `citron-nv12-result.json` | 6,010 B | Citron harness 的 result.json：窗口标题 `citron Nightly | 0237a9b88 | rfvp (64-bit)`、status=loaded、24 步输入全 ok、截图 nonblack 0.9018 |
| `citron-nv12-shadow-lines.txt` | 12,488 B | debug_report.txt 中 103 条 `movie h264: nv12 shadow` 记录（含行号），全部 match=1 / diff_bytes=0 |
| `citron-nv12-debug-report-movie.txt` | 1,401 B | movie 子系统日志摘录：`Movie: opened (Switch NVDEC H.264)`、解码/上屏节奏、末帧 2940 |
| `citron-nv12-op-credits.png` | 678,656 B | step-04 截图降采样到 1280 宽：OP staff credits 画面 |
| `citron-nv12-op-cg.png` | 947,593 B | step-10 截图降采样到 1280 宽：OP 角色 CG 画面 |

## 复现

```bash
# 1) 构建（MSYS2）
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p40/build.sh'
# 2) 影子验证（必须用 git-bash 启动 citron_run.sh）
/d/Scoop/apps/git/current/bin/bash.exe -c 'bash /e/galnx-build/p40/run-h264-citron.sh'
# 3) 检查（marker 由脚本写入 sdmc；期望计数 103）
grep -c 'nv12 shadow.*match=1 diff_bytes=0' /e/galnx-build/p40/evidence/citron-04/debug_report.txt
```

## 备注

- 日志在 `debug_report.txt` 的 `[INFO]` 行；真实设备上不需要 `h264_nv12_selftest.txt`，不写该 marker 即完全关闭影子比较（零额外开销）。
- 唯一 `[ERROR]` 是既有无关项 `id must be in range 0..256`（`color.rs:35`），P40 之前就存在。
