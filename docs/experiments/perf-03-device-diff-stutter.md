# perf-03 真机 CG 差分切换卡顿：SD 读放大与 4K 差分解码

- 日期：2026-11-06
- 构建：IROSEKA v1.1.1-test（async prefetch-only；sha256 `bf83fa6edb0134c60c04756b6c02c21b191b43e3567561e68628962b4ded2e5b`）
- 设备：Nintendo Switch 真机（emuMMC + SD）
- 触发：用户 m27413 —— 「cg完整，ui问题消失，不过cg差分切换时仍有明显（且有时会超过1秒的）卡顿」
- 证据：`docs/milestones/evidence/P26a-device-diff-stutter/`

## 1. 现象

在 Album（鉴赏模式）中打开一张 CG 后按左键依次切换差分，每次切换出现明显冻结；用户体感「有时超过 1 秒」。剧情内 CG 首次进入的加载也有同类长帧，但本次聚焦差分切换。

## 2. 取证方法

1. 用户真机取存档 + 日志（MTP 取回，见 `E:/galnx-build/p26/fetch-all.ps1`）。
2. 存档：`saves/iroseka-2ae7dc8e/save`（20 文件，含 s481–s491 Album 槽）。
3. 日志：`perf_slow.log`（慢帧 >25 ms 记录，2394 行）、`debug_report.txt`（vfs/graph decode/cache 诊断行）、`async_status.txt`、`frame_status.txt`、`watchdog_status.txt`。
4. 全局：`frame=15225 status=0 async=1`；async 健康（`enabled=1 hb=290000 stage=0 cpu=1 wdt=1`），但 `stalled=1`，且 `watchdog_status.txt` 记录过一次 `stalled_ms=3000`（frame 4133）。

## 3. 帧级拆解（Album 差分切换，原样日志）

```
frame 14402 slow 1569.8 ms | vm 1443.93 scene 0.76 render 119.66 ms | ops 6210 | mark 500 |
  stages(ms): ... tree 55.91 ... vm 1443.93 syscalls 1442.46 vfs_read 1097.76 graph_decode 325.35 |
  host(ms): ... upload 55.84/1 present 0.46 draws 4
frame 14617 slow 1570.8 ms | vm 1449.06 scene 0.71 render 120.43 ms | ops 3042 | mark 500 |
  stages(ms): ... tree 53.17 ... vm 1449.06 syscalls 1448.21 vfs_read 1102.67 graph_decode 326.17 |
  host(ms): ... upload 53.10/1 present 0.46 draws 2
```

对应的 vfs / 解码行：

```
[probe] graph_load path="graph_vis2/MIO_e01c"
[cache] bytes put size=8001842 total=171943153/201326592
vfs path="graph_vis2/MIO_e01c" bytes=8001842 us=1097751
graph decode path="graph_vis2/MIO_e01c" bytes=8001842
[cache] texture put size=33177600 total=162494724/167772160
graph decoded path="graph_vis2/MIO_e01c" 3840x2160 us=325330

[probe] graph_load path="graph_vis2/MIO_e01b"
[cache] bytes put size=8038985 total=180045513/201326592
vfs path="graph_vis2/MIO_e01b" bytes=8038985 us=1102667
graph decoded path="graph_vis2/MIO_e01b" 3840x2160 us=326163
```

| 阶段 | 耗时 | 说明 |
| --- | --- | --- |
| vfs_read | 1097.76 / 1102.67 ms | 8.0 MB pack 条目，≈7.3 MB/s |
| graph_decode | 325.35 / 326.17 ms | 解码为 3840×2160 RGBA（33,177,600 B） |
| texture upload | 55.84 / 53.10 ms | 33 MB 纹理上传（host 计时） |
| tree/ops | ≈55 ms / 6210 ops | 场景树重建 |
| 总计 | 1569.8 / 1570.8 ms | 与用户体感一致 |

## 4. 根因

### 4.1 SD 读放大：4 KiB read_to_end × newlib 1 KiB 缓冲

- `crates/rfvp/src/lib.rs:551-567` 自定义 `Read::read_to_end` 用固定 **4 KiB** 栈缓冲循环 `read`；8 MB 条目 = **2048 次** `read`。
- `crates/rfvp/src/subsystem/resources/vfs.rs:470-474`：`read_file` = `open_stream_with_len` + `stream.read_to_end`；每次 read 落到 `HostPackFile::read_at`（`vfs.rs` ~182-197）→ `HorizonFile::read_at` = `fseek` + `fread(4 KiB)`。
- `platform/switch/host/src/fs.rs` 的 `HorizonFile::open` 只调 `fopen`，未设置缓冲；devkitPro newlib 的 `BUFSIZ = 1024`（`/d/devkitPro/devkitA64/aarch64-none-elf/include/stdio.h:126-129`）→ 每次 `fread(4 KiB)` 内部拆成 **4 次** `fsFileRead`。
- 合计 ≈ 2048 × 4 = **8192 次小 IPC**；按日志实测 ≈134 µs/次（63 KB voice 13.3 ms、158 KB graph 28.6 ms，均 ≈200 µs/KiB）→ **≈1.10 s**，与 `us=1097751` 完全吻合。
- 因此这不是「SD 卡慢」，而是**每 1 KiB 一次同步 FS IPC** 的固定开销；顺序吞吐只有 ~7 MB/s。

> 参考：newlib 反汇编确认（devkitA64 libc.a → `libc_a-makebuf.o` / `libc_a-refill.o` / `libc_a-fread.o`）——
> - unbuffered 流的 `_bf._size` 初始为 1，但 `_fread_r` 对 `__SNBF` 走直接读分支（把 `_bf._base` 指向调用者 buffer、`_bf._size` 设为剩余字节），因此 `setvbuf(_IONBF)` 后**一次大 fread 会转成少量大 read**，不会退化成 1 字节/次；配合大块 `read_at` 即可消除放大。

### 4.2 差分图是 4K：解码与纹理内存双重成本

- 日志显示差分图解码后为 **3840×2160**（`graph decoded ... 3840x2160`），RGBA 纹理 **33,177,600 B/张**。
- 纹理缓存预算 160 MB（`texture put ... total=162494724/167772160`），只能容纳约 **4.9 张** 4K 纹理 → 差分序列来回切换时容易触发淘汰与重复解码。
- 字节缓存预算 192 MB（`bytes put ... total=180045513/201326592`）已接近上限。
- 解码 325 ms 虽小于读盘 1.10 s，但修掉读放大后它将成为主要剩余成本（约 0.33 s/次）；只做预取不做解码前的像素裁剪时，切换仍会有可感停顿。

### 4.3 graph_vis* 没有差分预取

- `crates/rfvp/src/subsystem/components/syscalls/graph.rs:964-1000` 的 `prefetch_graph_siblings` 只覆盖 `graph_bg`（X/Xb）与 `graph_bs`（X_昞忣）。
- Album 差分位于 `graph_vis / graph_vis1 / graph_vis2`（如 `graph_vis2/MIO_e01b`、`MIO_e01c`），**没有任何预取** → 每次切换都在主线程同步读盘 + 解码。

### 4.4 全局影响

- 2394 条慢帧中：p50 32.8 ms；**98 帧 ≥1000 ms**（含每次启动的 frame1 约 4.3 s、换场景 frame 777 4473.7 ms、frame 2777 2391.1 ms 等）；**146 帧 vfs_read ≥300 ms**。
- 同类大读贯穿：`graph_bg/BG042_000` 4.45 MB/688 ms、`graph_bs/CHR_*_昞忣` 3.44 MB/475 ms、`graph_vis/ETC_e50a` 3.52 MB/483 ms。
- 结论：P26 的读放大修复不仅服务 Album 差分，也会显著改善启动、换场景、剧情 CG 的加载时间。

## 5. 修复方案（P26，task-54）

| 编号 | 措施 | 预期 |
| --- | --- | --- |
| A | `platform/switch/host/src/ffi.rs` 增加 `setvbuf` extern；`fs.rs::HorizonFile::open` 对读模式句柄 `setvbuf(file, null, _IONBF, 0)` | 消除 newlib 1 KiB 缓冲拆包 |
| B | `crates/rfvp/src/subsystem/resources/vfs.rs::read_file` 用条目 size 分配，按 ≤4 MiB 块 `read_at` 一次读满（失败回退 `read_to_end`）；vfs 日志增加 `reads=N` | 8 MB 条目 2048 次小读 → 个位数大读；目标 <300 ms |
| C | `graph.rs` 对 `graph_vis/graph_vis1/graph_vis2` 预取后继 1–2 个条目（`submit_prefetch_graph` 入队，不改变 `graph_load` 同步返回语义） | 用户看图时后台完成下一张的读+解码，切换时命中缓存 |
| D（备选，需用户决策） | 显示输出 720p，考虑将 4K 差分解码裁剪/降采样到 1080p（纹理 8.3 MB、解码约 1/4、缓存可容 ~19 张） | 内存与解码大幅下降，但会损失未来 4K 输出/放大的画质余量 |

验收线：真机 Album 差分连切 ≥10 次，**单次切换帧 <600 ms**、无 >1 s 帧；`debug_report` 中大图 vfs_read <300 ms 且 reads 次数从 2048 降到个位；async 仍健康（hb 递增、stalled=0、无 last_error）。

## 6. 风险与限制

- **SD 真实吞吐未知**：本机日志只能证明 IPC 放大；A+B 后是否达到 <300 ms 取决于 SD/emuMMC 顺序吞吐与 FS 解密开销，需真机复测。
- **unbuffered 依赖 newlib 行为**：已反汇编确认 fread 直接读分支；但仍需在真机日志中核对 reads/耗时，若异常则回退为「大 fread + 4 KiB 缓冲」的组合。
- **纹理缓存容量**：4K×33 MB 下 160 MB 预算只容 ~4.9 张；差分序列若跨 5 张以上仍可能抖动。方案 D 或提高预算（受内存上限约束）可缓解。
- **预取优先级**：预取必须让位于 on-demand；队列已有 path 去重与 push_front 机制（P25），需确认差分预取不会挤掉剧情加载。
- **Citron 不可作为吞吐验收**：宿主文件系统读 8 MB 仅几毫秒，Citron 只能验证功能不回归与预取可观测性；性能判定以真机 debug_report 为准。

## 7. 证据

- `docs/milestones/evidence/P26a-device-diff-stutter/`：`perf_slow.log`（664,857 B）、`debug_report.txt`（113,652 B）、`async_status.txt`、`frame_status.txt`、`watchdog_status.txt`、README、SHA256SUMS。
- 设备原始目录：`E:/galnx-build/p26/device-logs-20261106/`。
- 存档：`E:/galnx-build/p26/device-logs-20261106/saves/iroseka-2ae7dc8e/save`（已装入 Citron 复现环境）。

## 8. 后续

1. P26 A+B+C → 1.1.2-test；Citron 功能验证 + 真机日志验收。
2. 若修完读放大仍不够流畅：评估 D（4K→1080p 解码裁剪）与纹理缓存预算，需与用户确认画质取舍。
3. 同期可立项 OP 视频播放（no_std 无 movie decoder，`crates/rfvp/src/videoplayer/mod.rs:113-115`）。

## 附录 A：Album 复现路径（Citron / 真机通用坐标，窗口 1728x1016 1:1）

| 步骤 | 坐标 | 说明 |
| --- | --- | --- |
| 标题菜单 Album | (1390, 694) | 菜单项 y：New Game 534 / Continue 614 / Album 694 / Option 770 / Exit 850 |
| ALBUM MODE → CG MODE | (1390, 281) | 同页 SOUND MODE ≈(1390,416)、BACK ≈(1390,676) |
| CG MODE 第一个已解锁 CG | (540, 270) | 网格列中心 x≈540/745/950/1155/1360，行中心 y≈270/395/520/645 |
| 切差分 | **Enter（A 键）或右键（ZL）** | 左键=放大；Enter/右键=播下一张，末尾再按回列表 |

Citron 复现命令（NRO）：

```bash
bash scripts/citron_run.sh --nro <rfvp.nro> --timeout 240 --settle 10 --allow-existing --expect-title rfvp \
  --input-steps 'wait:16000;click:1390,694;wait:9000;click:1390,281;wait:9000;click:540,270;wait:9000;click:860,500;wait:7000;click:860,500;wait:7000;click:860,500' \
  --out <out-dir>
```

注意：左键是放大、Enter/右键 才是切差分（用户 2026-11-06 更正）。Citron 使用宿主文件系统，8 MB 读通常只有个位数毫秒，因此 Citron 只用于验证功能不回归与日志可观测性（`reads=N`、预取命中），性能验收必须在真机进行。