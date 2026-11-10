# P40 证据：OP 换 H.264 + NVDEC(nvtegra) 解码接入（v1.2.0-test）

- 日期：2026-11-09
- 记录：`docs/builds/046-op-h264-nvtegra.md`
- 补丁：`docs/builds/patches/rfvp-switch/P40-op-h264.diff`

## 这两组冒烟分别证明了什么

### A. NRO 形态（Citron，强制软解）→ `citron-nro-*`

证明 **播放链路本身正确**：`sdmc:/switch/rfvp/game` 是 SD 卡游戏目录（含 `movie/01_h264.mp4`），
NRO 从 SD 读同一份资产，FFmpeg 软解 H.264 → NEON NV12→RGBA → 纹理上传 → SDL 上屏。

- 整段 OP 播完：`movie h264: end of stream after 3597 frames`
- 24 步截图全部 ok，颜色正确（staff credits / CG 画面）
- `convert_us` 中位 2.52 ms（720p，NEON 内核）

### B. NSP 形态（Citron，romfs 内的资产）→ `citron-nsp-romfs-*`

证明 **自包含 NSP 的 romfs 路径可用**：冒烟前把 `sdmc:/switch/rfvp/game` junction 临时挪走
（`JUNCTION_PARKED`），main.c 的 `dir_has_game_script(GameRoot)` 因此为假 → `game_root = romfs:/game`，
游戏与 OP 资产全部来自 NSP 的 romfs。跑完 `JUNCTION_RESTORED`。

- 窗口标题：`citron Nightly | 0237a9b88 | IROSEKA FHD (64-bit) | 1.2.0-test`
- 24/24 步 ok，`nonblack_ratio=0.9018`
- `Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4`
- 整段 OP 播完：`end of stream after 3597 frames`（120.0 s 内容，pts 到 119,085 ms）
- OP 后游戏继续正常运行：`frame 5880: 60.0 fps over the last 60 frames, slowest frame 18.1 ms`
- 唯一 ERROR 是既有无关项 `id must be in range 0..256`（`color.rs:35`）

## 不能证明什么

1. **不能证明硬件解码**。Citron 的 nvtegra 只有 HLE，第二个包就会 `AVERROR_UNKNOWN (-1313558101)`，
   所以冒烟一律用 `sdmc:/switch/rfvp/h264_sw.txt` 强制软解（日志里 `hw=0`）。
   真机硬解由 probe9 单独证明（297.80 fps decode / 3.79 ms xfer），合并验证在 v1.2.0-test 真机运行。
2. 不能证明真机 60 fps 满帧——Citron 的软解帧率（4.4–16 fps）与真机无关。
3. 不能证明音频；音轨仍走既有 `movie/01.ogg`，不在本次改动内。

## 文件

| 文件 | 内容 |
| --- | --- |
| `citron-nro-result.json` | NRO 冒烟 result.json（24 步，窗口标题 1.2.0-test） |
| `citron-nro-debug-report-movie.txt` | NRO 冒烟 debug_report 的 movie 相关行 + 统计 |
| `citron-nro-op-credits.png` | NRO 冒烟 OP staff credits 截图（降采样） |
| `citron-nro-op-characters.png` | NRO 冒烟 OP 角色画面截图（降采样） |
| `citron-nsp-romfs-result.json` | NSP(romfs) 冒烟 result.json（24/24 步 ok，nonblack 0.9018） |
| `citron-nsp-romfs-debug-report-movie.txt` | NSP(romfs) 冒烟 movie 相关行 + convert/decode 统计 + 错误计数 |
| `citron-nsp-romfs-op-credits.png` | NSP(romfs) OP staff credits 截图（跑在 14 s 处，降采样） |
| `citron-nsp-romfs-op-cg.png` | NSP(romfs) OP 画面截图（降采样） |

## 复跑

```bash
# 1) NRO 影子验证（SD 卡游戏目录 + 本地 NRO）
bash /e/galnx-build/p40/run-h264-citron.sh

# 2) NSP(romfs) 冒烟（自动挪走 game junction、写完恢复）
bash /e/galnx-build/p40/run-nsp-romfs-citron.sh
```

两个脚本都必须用 **git-bash** 启动（`/d/Scoop/apps/git/current/bin/bash.exe`）：
`scripts/citron_run.sh` 用 `/c/Users/...` 解析 user 目录，devkitPro 的 MSYS2 bash 没有 `/c` 挂载。
