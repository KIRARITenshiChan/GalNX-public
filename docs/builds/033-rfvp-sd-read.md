# 033 — rfvp SD 读吞吐与 4K 纹理缓存修复（v1.1.2-test）

- 日期：2026-11-06
- 目标：修复真机 v1.1.1-test 在 Album 内切换 CG 差分时的 >1 s 卡顿（真机 perf_slow 两次 1569.8 / 1570.8 ms），同时让 P25 的 async prefetch-only 对 4K CG 真正生效。
- 版本：1.1.2-test（nacp 版本号来自 `platform/switch/host/Cargo.toml:3`）
- 分支基线：6c166f6（P22 v1.1.0-test 源码副本）＋ P25 prefetch-only（p25-base=8210f38 / v1.1.1-test）
- 构建 worktree：`/e/galnx-build/p25/rfvp-v111`（分支 p26-work，不污染 m5-rfvp 主树）
- 状态：Citron 级验证 PASS（probe6）；真机验收待 Lead 统一执行。P24 音频流式补丁未并入本线。

## 1. 缺陷与根因

### 1.1 真机证据（E:/galnx-build/p26/device-logs-20261106/）

`perf_slow.log`：

| 帧 | 慢帧 | 其中 vfs_read | 其中 graph_decode |
| --- | --- | --- | --- |
| frame 14402 | 1569.8 ms | 1097.76 ms | 325.35 ms |
| frame 14617 | 1570.8 ms | 1102.67 ms | 326.17 ms |

`debug_report.txt`（同一台机）：

- `graph_vis2/MIO_e01b bytes=8038985 us=1102667`
- `graph_vis2/MIO_e01c bytes=8001842 us=1097751`
- `graph_bg/BG042_000 bytes=4451365 us=687868`
- `voice/... bytes=63002 us=13299` —— 6 万字节也要 13 ms，有效吞吐只有 **6.4–7.3 MB/s**。

### 1.2 根因 A：stdio 1024 字节缓冲 × 4 KiB `read_to_end`

读一条 pack 条目的调用链：

```
VfsFile::read_file -> open_stream_with_len -> Read::read_to_end
  (crates/rfvp/src/lib.rs:551 用固定 4 KiB 栈缓冲循环 read)
-> PackSlice::read -> HostPackFile::read_at
-> HorizonFile::read_at (platform/switch/host/src/fs.rs: fseek + fread, 阻塞 SD)
-> newlib stdio (默认 BUFSIZ=1024)
```

8 MB 条目 = 2048 次 4 KiB 引擎读 = **8192 次 fsFileRead**（每次 ~134 us）≈ 1.10 s，再加 inflate ~0.3 s ≈ 1.4 s，与真机 1.57 s 吻合。

Lead 用 objdump 反汇编 `/d/devkitPro/devkitA64/aarch64-none-elf/lib/large/libc.a`（libc_a-makebuf.o / refill.o / fread.o）核实：`_IONBF` 流的 `_fread_r` 走 0x14c–0x204 的直接读分支——`_bf._base` 指向调用者 buffer、`_bf._size` 为剩余字节，`__srefill_r` 直接 `_read(remaining)`。因此 `setvbuf(_IONBF)` 能让一次大 `fread(4 MiB)` 变成少量大 read，而不是 4 次 1 KiB 系统调用。

### 1.3 根因 B：`MAX_ENTRY_BYTES=16 MiB` 把 4K CG 全部拒之缓存

`crates/rfvp/src/subsystem/resources/resource_cache.rs` 原第 28 行：

```rust
const MAX_ENTRY_BYTES: usize = 16 * 1024 * 1024;
```

4K 差分解码后是 3840x2160 RGBA = **33,177,600 B** > 16 MiB，`put_texture` 在插入前静默 return。后果：

- P25 的 async prefetch 解码成功，但结果被缓存丢弃 → 下一次切换仍然 miss；
- 每次 Enter 切差分都重新 SD 读 8 MB + inflate ≈ 1.6 s（真机）；
- Citron 宿主文件系统很快，只看到 ~200 ms 解码，看起来「只是慢」而不像「缓存没生效」。

同时 160 MiB `TEXTURE_BUDGET` 对 4K 场景偏紧：当前图 33 MB + 两张预取 66 MB + 菜单纹理，容易让 LRU 淘汰正在显示的图。probe5（160 MiB、lookahead 2、无链式预取）实测：

- `[cache] texture put path="graph_vis/SHINKU_e01b" size=33177600 evicted=0 total=153789980/167772160`
- e01a 插入时 `evicted=17 evicted_bytes=24891276`

## 2. 修复设计（A–E）

### A. pack 读改无缓冲大读（`setvbuf(_IONBF)`）

- `platform/switch/host/src/ffi.rs`：`pub const IONBF: c_int = 2;`（L37）＋ `pub fn setvbuf(file, buf, mode, size) -> c_int`（L56）。
- `platform/switch/host/src/fs.rs:57-71`：`HorizonFile::open` 仅在读模式 `mode == c"rb"`、fopen 成功后、任何 I/O 之前调用 `setvbuf(file, null_mut(), IONBF, 0)`。失败只打印一次 `rfvp: setvbuf(_IONBF) failed; stdio keeps its 1024 byte buffer`，不影响功能。

### B. pack 整条目的一次分配、4 MiB 分块读（`read_entry`）

`crates/rfvp/src/subsystem/resources/vfs.rs`：

- `find_entry`（L421）：从 `open_stream_with_len` 抽出的索引查找（含 psx / 大小写别名表）。
- `read_entry`（L483-512）：按条目 size 分配 `Vec`，以 `READ_CHUNK_BYTES = 4 * 1024 * 1024` 循环 `pack.0.read_at(ent.offset + pos, &mut out[pos..end])`，返回 `(bytes, reads)`；任何短读/错误回退原 stream + `read_to_end` 路径（错误语义不变）。
- `read_file`（L514）改走 `read_entry`。
- `Vfs::read_file`：先用新增的 `pack_file_for`（L729）判断该路径是否被 loose file 遮蔽；未遮蔽时走 `read_entry`，否则保留原 stream 路径。

### C. 可观测性：`reads=N`

`crates/rfvp/src/subsystem/resources/vfs.rs:717-720`：`vfs path=... bytes=... us=... reads=N`，条件从 `us >= 10 ms` 放宽到 `us >= 10 ms || bytes >= 1 MB`。真机 `debug_report.txt` 可直接验证 8 MB 条目的读次数从 2048 降到个位数（Citron 实测 2）。

### D. graph_vis 差分预取（lookahead=1，且在 cache hit 上链式续预取）

`crates/rfvp/src/subsystem/components/syscalls/graph.rs`：

- `prefetch_graph_siblings`（L994-999）末尾：路径以 `graph_vis` 开头时调用 `prefetch_vis_sequence`。
- `prefetch_vis_sequence`（L1016-1034）：候选 = 路径末位 ASCII 字母 +1（`MIO_e01b` → `e01c`）；已缓存则记 `[probe] vis sibling cached`；`vfs.pack_location` 存在才 `submit_prefetch_graph` 并记 `[probe] vis sibling cand=... submitted=...`。**不改 `graph_load` 同步返回语义，不发 submit+return Nil。**
- cache hit 分支（L1073-1082）：`load_graph_cached + refresh_prims` 后、return 前再调一次 `prefetch_vis_sequence`。没有这一步，只有「未命中同步解码」时才预取，一旦命中过缓存，下一张就没人预热，又回到完整 SD 读。
- LRU 安全性（Lead 要求「hit 分支也要 touch」）：`resource_cache.rs` 的 `Lru::get`（L64-70）命中时已经调用 `self.touch(key)`（O(n) 移回队尾、不 clone key），所以正在显示的图在每次命中时都会刷新 recency，不会被后继预取淘汰；无需额外代码。

### E. 4K 纹理缓存放行与预算

`crates/rfvp/src/subsystem/resources/resource_cache.rs`：

| 项 | 旧值 | 新值 | 理由 |
| --- | --- | --- | --- |
| `MAX_ENTRY_BYTES` | 16 MiB | **64 MiB**（L38） | 放行 33,177,600 B 的 4K 纹理；总量仍由 TEXTURE_BUDGET 约束 |
| `TEXTURE_BUDGET` | 160 MiB | **256 MiB**（L27） | 当前图 + 1 张预取 + 菜单纹理留出余量；纯缓存上限，可回退 |

- `put_texture` 超限时不再静默：`[cache] texture skip path=... size=... max=...`（L159）。
- 正常 put 日志（L177）：`[cache] texture put path=... size=... evicted=N evicted_bytes=... total=.../budget`；`evicted_bytes = before + size - after`，锁内计算、**锁外 drop evicted 与打日志**（保持 P22 / RCA H2 语义）。
- `async_decode.rs:459-465`：解码完打 `[async] decoded texture path=... WxH px=...`，真机可直接看到每张 graph_vis 的尺寸/字节（实测 3840x2160 px=33177600）。

## 3. 改动清单

增量：`git diff p25-base..HEAD`（p25-base = P25 v1.1.1-test），**8 files changed, +173 / −13**。

| 文件 | 变化 |
| --- | --- |
| crates/rfvp/src/subsystem/resources/vfs.rs | find_entry 抽取、read_entry 4 MiB 分块、Vfs::read_file 走 pack 直读、pack_file_for、reads=N 日志 |
| crates/rfvp/src/subsystem/resources/resource_cache.rs | MAX_ENTRY_BYTES 16→64 MiB、TEXTURE_BUDGET 160→256 MiB、skip/put/evicted 日志（锁外 drop） |
| crates/rfvp/src/subsystem/components/syscalls/graph.rs | prefetch_vis_sequence（lookahead=1）、graph_vis 差分预取接入、cache-hit 链式预取 |
| crates/rfvp/src/subsystem/resources/async_decode.rs | prefetch 解码后记录纹理尺寸/字节 |
| platform/switch/host/src/ffi.rs | IONBF 常量、setvbuf extern 声明 |
| platform/switch/host/src/fs.rs | 读模式 fopen 后 setvbuf(_IONBF)（一次性失败日志） |
| platform/switch/host/Cargo.toml | version 1.1.1-test → 1.1.2-test |
| Cargo.lock | rfvp-horizon 版本同步 |

## 4. Citron 验证

### 4.1 方法

- 构建：`bash /e/galnx-build/p26/build-instr.sh`（worktree 增量，BUILD_EXIT=0，ELAPSED_S=27）。
- 用 NRO 跑 Citron（宿主文件系统快，vfs_read 只有 ms 级，**不能代表 SD 吞吐**；只验证功能不回归、缓存/预取行为、是否存在 async 冻结）。
- Album 操作：标题 Album(1390,694) → CG MODE(1390,281) → 第一格(540,270) → 12 次 `key:C`（手柄 A=Enter，切下一张差分）→ 末尾点击中央 2 次验证放大/复原。
- ring 只有 4000 行，会被 `[cache] prefetch skip`/motion 错误刷掉，所以探针用 0.3 s 间隔快照（410 份）再 `sort -u` 取证。

### 4.2 probe5（本次改造前，用于定位 16 MiB 上限）

- e01b 首次切到命中预取（`graph cache hit path="graph_vis/SHINKU_e01b"`），但 e01c 首次仍 `vfs ... us=7135 reads=2` + 同步 decode `us=161228`；
- e01a 插入时 `evicted=17 evicted_bytes=24891276`，160 MiB 预算确实在挤出纹理。

### 4.3 probe6（最终验收，PASS）

run dir：`E:/galnx-build/p26/run-album-probe6/20261106-050546-rfvp`，56/56 步 ok。

状态：`enabled=1 hb=189000 stage=0 cpu=1 wdt=1 main=12267 stalled=0`，`frame=12270 status=0 async=1`；无 `watchdog_status.txt`、无 `last_error`（未冻结）。

ring 去重证据（`/e/galnx-build/p26/evidence/probe6/ring-evidence.txt`）：

```
[cache] texture put path="graph_vis/SHINKU_e01b" size=33177600 evicted=0 evicted_bytes=0 total=153789980/268435456
[cache] texture put path="graph_vis/SHINKU_e01a" size=33177600 evicted=0 evicted_bytes=0 total=186967580/268435456
[cache] texture put path="graph_vis/SHINKU_e01c" size=33177600 evicted=0 evicted_bytes=0 total=240567192/268435456
[async] decoded texture path="graph_vis/SHINKU_e01b" 3840x2160 px=33177600
[async] decoded "graph_vis/SHINKU_e01b" id=65535 bytes=6950234 us=190845 ok=true
[async] decoded "graph_vis/SHINKU_e01c" id=65535 bytes=6978199 us=166000 ok=true
vfs path="graph_vis/SHINKU_e01a" bytes=7480326 us=12169 reads=2
graph cache hit path="graph_vis/SHINKU_e01a"   (×多次)
graph cache hit path="graph_vis/SHINKU_e01b"
graph cache hit path="graph_vis/SHINKU_e01c"
```

- 3 张 33 MB 纹理全部进缓存且 `evicted=0`（256 MiB 预算生效）；
- 12 次切换中 9 次命中缓存（该 CG 只有 e01a/e01b/e01c 三个差分文件，Enter 循环回绕）；
- 新差分由 worker 预取解码（190.8 ms / 166.0 ms，宿主 CPU 解码），不再回 SD 重读；
- `reads=2`（4 MiB 分块 + 7.48 MB 文件）证明 B 生效（旧路径按 4 KiB 计约 1827 次）。

perf_slow（Citron 宿主 FS，仅供参考）：boot frame 1 1762.9 ms（vfs_read 624.84）；frame 4 406.8 ms（首次 4K 同步解码 graph_decode 242.10）；切换帧 175.1 / 222.6 / 309.5 ms（graph_decode 69–207 ms，无 SD 读），全程无 >1 s 帧。

截图：19 张，15 个不同 sha256；该 CG 只有 3 个差分源文件（其余是切换过渡/动画帧）。

### 4.4 Citron 的局限

Citron 读的是宿主文件（vfs_read 约 12 ms 读 7.5 MB），无法复现真机 SD 的 6.4–7.3 MB/s。真机收益需按以下预期验证：8 MB 条目 `reads` 从 2048 降至 2–5、vfs_read 从 ~1.1 s 降至 <300 ms、命中预取的差分切换总时长 <600 ms。

## 5. 产物

| 产物 | 路径 | sha256 |
| --- | --- | --- |
| NSP 1.1.2-test | `E:/galnx-build/p26/out/IROSEKA_FHD-010047420000a000-v1.1.2-test.nsp`（9,979,500,248 B） | 0cbac98ef8c292b69d64eef87d6340fee9477c8f007ee8b38e4d5cfb229789b8 |
| NRO | `/e/galnx-build/p25/rfvp-v111/target/rfvp-switch/switch/rfvp.nro` | 4e4c6db3fbd1d933348e33c1e234a363545d0cb547aca0e1ae4ac140f2ea5ae4 |
| ELF | `/e/galnx-build/p25/rfvp-v111/target/rfvp-switch-runtime/rfvp.elf` | e3defd75104af9b8b2bde8466573d0d28df3c435415af157acfe506ef776a297 |
| 增量 patch | `docs/builds/patches/rfvp-switch/rfvp-sd-read.patch` | 5642795914bf7dccdc7eead37a989bd29eafbdda3cddbafa1a6524c4d6fbdc91 |
| 全量 diff | `/e/galnx-build/p26/rfvp-full-v112.diff`（仓库外暂存） | cb711f9508276780abcc43f1e8e542f85c45a835236f3c50b582ecfdf3368d85 |
| 证据 | `E:/galnx-build/p26/evidence/`（probe5/probe6 截图、ring 证据、perf_slow、状态文件） | SHA256SUMS 见目录 |

- 增量 patch 已在 p25-base（8210f38）干净 worktree `git apply --check` 通过；全量 diff 已在 6c166f6 干净 worktree 通过。
- async 开关保持 v1.0.9 语义：默认关闭，`sdmc:/switch/rfvp/async.txt` 内容为 `on` 才启用。
- P24 音频流式补丁**未**并入本线，等 P26 真机验收通过后由 Lead 单独合并。

## 6. 真机验收清单（Lead）

1. 装 `IROSEKA_FHD-...-v1.1.2-test.nsp`，`sdmc:/switch/rfvp/async.txt` 写 `on`。
2. Album → 任一 4K CG → 连续 Enter/右键切差分 ≥10 次：每次无 >1 s 冻结，目标 <600 ms。
3. `debug_report.txt` 检查：
   - `vfs path="graph_vis/... bytes=8xxxxxx us=< 300000 reads=<10`（旧版 us≈1,100,000 / reads 不可见）；
   - `[async] decoded texture ... 3840x2160 px=33177600`；
   - `[diag] graph cache hit path="graph_vis/...` 与 `[cache] texture put ... size=33177600 evicted=0`。
4. 无 `watchdog_status.txt`、无 `last_error`；`async_status.txt` 中 `cpu=1 wdt=1 stalled=0`。
5. 菜单/存档 UI 开关无残留；其他场景（正文、标题）无回归。
6. 若 256 MiB 预算导致内存压力（异常退出/分配失败），回退预算与 `MAX_ENTRY_BYTES` 后复测。

## 7. 风险与回退

- **`setvbuf(_IONBF)` 影响所有读模式文件**：小读不再被 stdio 合并。整文件读取已走 `read_entry` 大读，风险主要在仍按小 buffer 流式读的路径；真机若发现小文件读变慢，可只对 pack 文件句柄关闭缓冲（`HorizonFile` 增加显式开关）而不是全局。
- **256 MiB 纹理预算**：仅提高缓存上限；Switch 进程内存余量需真机观察。回退为 160 MiB + lookahead 0（关预取）即可恢复 P25 行为。
- **预取误解码**：候选按路径末位字母 +1 猜测，不存在时只多一次索引查找；若某 CG 命名不连续，仅表现为「未命中预取」，不影响正确性（`graph_load` 仍同步返回真实纹理）。
- **回退**：`git revert cf0ea4f b2a41cd` 回到 v1.1.1-test 行为；或安装 v1.1.1-test NSP。

## 8. Lead 独立 Citron 验收（2026-11-06 05:23，PASS / 无回归）

为排除 async-fix 自测偏差，Lead 用独立脚本 `E:/galnx-build/p26/run-lead-album-p26.sh` 复跑 Album 4K 差分路线（async=on）：

| 项 | 结果 |
| --- | --- |
| 运行 | `E:/galnx-build/p26/run-lead-album/20261106-052325-rfvp/`，44 步 0 failed |
| 路线 | 标题 → Album(1390,694) → CG MODE(1390,281) → 首个 4K CG(540,270) → 10× (`key:C` + 5 s) → 放大 → 恢复 |
| 差分循环 | 截图字节循环 1,775,991 / 1,768,489 / 1,775,048 / 1,515,877，3 个差分源往复，无冻结、无黑帧 |
| async | `async_status.txt` = `enabled=1 hb=170000 stage=0 cpu=1 wdt=1 main=11174 stalled=0`；`frame_status.txt` = `frame=11205 status=0 async=1` |
| 错误 | `last_error.txt` 不存在；无 `watchdog_status.txt` |
| 回归 | 标题 / 正文 / 菜单显示正常；放大（左键）功能正常 |
| 证据 | `docs/milestones/evidence/P26c-lead-album/`（5 截图 + result/run/input-steps + async/frame/perf_slow/debug_report + SHA256SUMS） |

局限：本轮未做 ring 缓冲快照轮询，sdmc `debug_report.txt` 中 `texture put` / `reads=` / `decoded texture` 计数为 0（只有 1 条 `graph cache hit path="graph_vis/SHINKU_e01c"`），因此缓存命中与 reads 数字以 §4 的 probe6 ring 证据与真机日志为准；本轮的结论是「功能无回归、async 不冻结、差分可连续切换」。

真机构建 `v1.1.2-test` 已置备待装，验收/回退见 §6/§7。

