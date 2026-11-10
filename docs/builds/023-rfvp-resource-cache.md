# 023 — rfvp 资源缓存、启动预读与 zlib inflate（P17）

> 里程碑：M5-j ｜ 日期：2026-11-01 ｜ 引擎：rfvp `9f07adef2eb5d559777f9bf59a67b756875cb24f`（MPL-2.0）
> 游戏：五彩斑斓的世界 HD Re:GENERATION（`E:/Othergames/Galgame/IROSEKA_FHD`）
> 目标：消除真机「CG 中的表情切换、背景切换、每次打开游戏 UI（ESC 菜单 / backlog / 存档界面）都卡」——用户 m22537。

## 1. 现象与目标

P16（`022-rfvp-save-latency.md`）修完「每句话卡一下」后，用户真机复验确认逐句卡顿消失、立绘表情切换也不卡，但仍有三类卡顿：

1. **CG 中的表情切换**卡；
2. **背景切换**卡；
3. **每次打开游戏 UI 界面**（ESC 暂停菜单、BACKLOG、FILE SAVE/LOAD 存档界面）都卡。

方向由用户指定：**预读 + 缓存**。

## 2. 根因

Citron 上把真机复杂存档加载进正文后复现（p17-a/p17-c），`perf_slow.log` 与 `debug_report.txt` 显示：

- `graph_load` / `parts_load` / `vfs_load_file` 每次都走完整的「读盘 → zlib inflate → 逐像素转 RGBA → 上传纹理」链路，**没有任何缓存**：同一套 ESC 菜单贴图（`graph/sys_*`、`sys_window_*` 等）每次打开都重新解码；
- UI 一次打开要现读现解码数十张小图 + `sys_window_left/right/title`（154–354 KB 压缩包），慢帧 350–1417 ms；
- 背景/CG 首次切换的慢帧 300–1200 ms（`vfs_read` 50–350 ms + `graph_decode` 100–600 ms + `parts_decode` 70–100 ms）；
- 解码成本中 **zlib inflate 占绝对主导**：对同一批 66 个 `graph/*` 贴图，miniz 总 inflate 204,407 us、像素转换 24,589 us；两个 1920×1080 的 `slf_*_bg` 单文件 inflate 各约 57 ms；
- `graph_decode` 的逐像素 BGR→RGBA 循环（`texture.rs::as_32bit_texture`）在同一帧里复制 2–3 次，单帧可达 380 ms。

## 3. 措施（三层）

### 3.1 资源缓存（`crates/rfvp/src/subsystem/resources/resource_cache.rs`，新增）

进程级 LRU 三缓存，`spin::Mutex` 惰性初始化（no_std 可用）：

| 缓存 | 内容 | 预算 |
| --- | --- | --- |
| `textures` | 已解码 `DecodedTexture`（`Arc<DynamicImage>` + 宽高/偏移/u/v） | 160 MiB |
| `parts` | 已解码 `NvsgTexture`（Multi32Bit 表情图集） | 48 MiB |
| `bytes` | 原始压缩字节（`Arc<[u8]>`） | 192 MiB |

单条上限 16 MiB；key 与 VFS 归一规则一致（去 `./`、反斜杠转 `/`、去前导 `/`、ASCII 小写）。接线 5 处：

- `graph_buff.rs::load_texture` 命中 `textures` → `apply_cached_texture()` 直接设置纹理与显示参数（跳过读盘+解码）；解码成功回填；
- `graph.rs::graph_load` 在读 buff 之前先查缓存，命中走 `motion_manager.load_graph_cached()`；
- `parts_manager.rs::PartsItem::load_texture` 命中 `parts` → 克隆纹理并置 `loaded`；解码成功回填；
- `parts.rs::parts_load` 命中 `parts` 时跳过 `vfs_load_file`（空 buff 交由上面第 3 步接管）；
- `vfs.rs::read_file` 命中 `bytes` 直接返回副本，读取成功回填。

### 3.2 启动预读（`resource_cache::prefetch_graph_textures`）

`no_std_core::try_boot` 启动完成、进入主循环前，枚举 `graph/` 目录中以下前缀的贴图并批量「读盘 + 解码 + 入缓存」：`sys_`、`menu_`、`config_`、`slf_`、`btn_`、`cursor`、`diss`、`prompt`、`mouse`；单文件上限 4 MiB、总预算 96 MiB。实测启动预读 66 个贴图，UI 首开时只需再解码 10 个运行期新资源。

### 3.3 解码提速

- **inflate 后端换 devkitPro zlib C 实现**：`crates/rfvp` 新增 feature `switch-zlib`，`texture.rs` 用 `extern "C" uncompress()` 替代 miniz_oxide（`platform/switch/host/Cargo.toml` 启用，`build_switch.sh` 链接加 `-lz`）；
- **像素转换块拷贝**：`as_32bit_texture` / `as_24bit_to_32bit_texture` / `as_8bit_texture` 由 `enumerate_pixels_mut()` 逐像素改为 `chunks_exact` 块循环 + `ImageBuffer::from_raw`；inflate 单帧 buffer 在 `entry_count<=1` 时直接 move 进 `slices`，不再多一次 8 MB 拷贝；
- 单文件解码 >4 ms 时打 `graph decoded path=... us=`，并给 inflate/convert 分别计时（`graph decode split`），便于后续定位。

## 4. 验证（Citron，同一份真机复杂存档）

### 4.1 重复打开 UI

- p17-f：连续两次按 B（Esc）打开暂停菜单，截图 **逐字节相同**（sha256 前缀 `3174b312`），期间无 ≥100 ms 的 save/解码慢帧；
- BACKLOG、FILE SAVE 各打开一次后再次打开均命中缓存（`graph cache hit` 193 次、`vfs cache hit` 106 次）；
- 运行期 `graph decoded` 仅 10 次（预读 66 个已覆盖 UI 图集）。

### 4.2 zlib vs miniz inflate（同一批 66 个 `graph/*` 预读解码）

| 指标 | miniz_oxide（p17-e） | devkitPro zlib（p17-f） |
| --- | --- | --- |
| 总 inflate | 204,407 us | **133,686 us**（≈1.53×） |
| 总 convert | 24,589 us | 24,942 us（持平，已非瓶颈） |
| `graph/slf_load_bg` | 57,861 us | 36,669 us |
| `graph/slf_save_bg` | 57,773 us | 36,463 us |
| `graph/slf_prt_sheet` | 23,388 us | 15,682 us |
| `graph/sys_window_left` | 13,377 us | 10,102 us |
| `graph/sys_window_right` | 14,428 us | 10,067 us |
| `graph/menu_bg` | 8,864 us | 6,945 us |

### 4.3 慢帧（p17-f，15 条 >60 ms）

- 启动帧 1：2,072.6 ms（`vfs_read` 993.73——romfs 冷读，未优化）；
- 启动帧 4：456.0 ms（`graph_decode` 217.38、`upload` 85.27/17）；
- **唯一剩余的大尖峰** frame 2490：838.5 ms（`vm` 568.15、`audio_cmds` 150.31、`vfs_read` **236.66**、`graph_decode` 146.79、`parts_decode` 74.36、`upload` 81.33/18）——首次加载一批 CG/表情图集；
- frame 4078：218.7 ms（`vfs` 85.45、`graph` 43.90、`parts_decode` 70.11）；frame 1707：120.1 ms；frame 9394：142.1 ms；
- 其余为 `end_frame` 24.7–34.2 ms 的 vsync 等待（不算卡顿）。

### 4.4 缓存规模

`texture` 缓存峰值 **123,259,040 / 167,772,160 B**、`bytes` 缓存 246 次回填；预读跳过 55 条（全部为 `graph/dissNN`——8-bit 溶解遮罩，`is_picture` 类型过滤，未预读）。

## 5. 产物

| 产物 | 值 |
| --- | --- |
| NRO | 7,905,336 B ｜ sha256 `331e0a254034777da2c478091725a914097e5b25bae1153671ad2d07ad0e930c` |
| ELF | 17,218,328 B ｜ sha256 `0c216c9bb52a16d0bd12a5762c06e21eb4120e490b9a55f0fd6aa26cbe226ae0` |
| 增量补丁 `rfvp-cache.patch` | 849 行 ｜ sha256 `8b97c147cc40a294841ed910705f0a2b61826a63a286093156e02bda3aeb6920`（需先应用 P16 全量） |
| 全量 `rfvp-full.diff` | 3,950 行 / 28 文件 ｜ sha256 `6930bb65d75fe1c8eb73adf4dac2b00918c010492216647a6f23663df79766c2`（校验：纯净 `9f07ade` worktree `git apply --check` 通过） |
| 自包含 NSP v1.0.5 | 9,979,481,304 B ｜ sha256 `6c7f668b218665c3c0189e5fad7f97c22b3d0a3182eca9e985b745288f5f030c`（TitleID `010047420000A000`，romfs 9,932,275,140 B / 161 条目；`galnx package nsp verify` 13 checks / 0 fail / 1 warn = 未签名 NCA，3 NCA ProgID 一致） |

## 6. 证据

### 6.1 目录

`docs/milestones/evidence/P17-rfvp-cache/`（16 文件 + `SHA256SUMS.txt`）：

- `p17-c-*`（纯缓存构建）、`p17-d-*`（+像素块优化/预算扩容）、`p17-f-*`（+zlib/预读）三组 `perf_slow.log` 与 `debug_report.txt`；
- 截图 `f2-loaded.png`、`f3-story.png`、`f5-esc2.png`、`f7-backlog1.png`、`f8-save1.png`；
- `zlib-vs-miniz-inflate.txt`、`graph-decode-split-p17f.txt`（66 行逐文件 inflate/convert）、`cache-hits-p17f.txt`、`prefetch-skips-p17f.txt`；
- `device-upload-v105.txt`（NSP v1.0.5 真机 DBI「浏览 SD 卡」FTP 上传实测：9,979,481,304 B / 1,686.5 s ≈ 5.64 MiB/s，落盘 `/switch/galnx-nsp/`）。

### 6.2 复现

```
# 1) 把真机复杂存档放进 Citron sdmc，开启诊断
#    sdmc/switch/rfvp/saves/iroseka-2ae7dc8e/save/*.bin
#    sdmc/switch/rfvp/debug.txt = "1"
# 2) 跑 harness（见 docs/pilot/P11-rfvp-nsp-device-runbook.md 的 Citron 用法）
#    标题 Continue(1386,638) -> LOAD 列表 CONTINUE(455,911) -> 正文推进 -> ESC/BACKLOG/存档 UI 反复开关
# 3) 读 sdmc/switch/rfvp/{perf_slow.log,debug_report.txt}
```

## 7. 限制（U 项）

- **U1** 未在真机验证：本轮全部数据来自 Citron x86_64；真机 aarch64 的 inflate/内存带宽与 SD 读速度不同，需用户安装 v1.0.5 复验。
- **U2** 首次加载大 CG/表情图集仍可能卡 0.1–0.8 s（frame 2490 类），因为当前只预读 `graph/` 的 UI 前缀；`graph_bg/`、`graph_bs/` 常用大图与 `parts/` 表情图集未预读。
- **U3** `graph/dissNN`（8-bit 溶解遮罩）预读被类型过滤跳过 55 条，首次转场可能仍有一次轻卡。
- **U4** 内存占用上升：texture 缓存预算 160 MiB + parts 48 MiB + bytes 192 MiB（实测峰值 123 MiB / bytes 未满），4 GB 机型余量需在真机观察。
- **U5** miniz 基线（p17-e）的 `debug_report.txt` 未归档，§4.2 的 miniz 列取自当次运行读取值；`convert` 与 `inflate` 分项计时已随 p17-f 归档。
- **U6** 启动预读在 `try_boot` 内同步执行，会拉长启动到可交互时间（66 个贴图，实测总 inflate 133.7 ms + 读盘），真机表现为启动稍慢属预期。

## 8. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-11-01 | 建立 P17：resource_cache 三缓存 + 5 处接线 + 启动预读 + 像素块拷贝 + devkitPro zlib inflate；Citron 复测 UI 重开无慢帧、zlib 比 miniz 快 1.53×；NSP v1.0.5 待真机复验 |
