# 024 — rfvp 大图异步解码与读档异步 restore（P18）

> 里程碑：M5-l ｜ 日期：2026-11-01 ｜ 引擎：rfvp `9f07adef2eb5d559777f9bf59a67b756875cb24f`（MPL-2.0）
> 游戏：五彩斑斓的世界 HD Re:GENERATION（`E:/Othergames/Galgame/IROSEKA_FHD`）
> 目标：处理用户 m23257 复验 P17（`023-rfvp-resource-cache.md`）后剩下的两类卡顿——**CG 里的表情切换**与**背景切换**。

## 1. 现象与目标

P17 修完 UI 重开的卡顿后，用户真机复验（m23257）确认「UI / 存档读档正常」，但**CG 表情切换**与**背景切换**仍然卡。两者都不是缓存命中问题：P17 已缓存解码结果，但**首次**出现的大图仍要在主线程上同步完成「读盘 → inflate → 像素转换 → 上传」，而一次切换往往同时要进 2–4 张 2400×1350 的图。

## 2. 根因（Citron，真机复杂存档 + 诊断构建）

### 2.1 单张大图解码成本

| 资源 | 尺寸 | `graph_decode` |
| --- | --- | --- |
| `graph_bg/BG043_000` | 2400×1350 | 160,324 us |
| `graph_bg/BG062_000` | 2400×1350 | 133,993 us |
| `graph_bs/CHR_*`（表情图集） | 2048×2048 级 | 83,739–113,472 us |

表情切换除图集本身外还要读 parts 差分 sheet（1.2–3.8 MB/张），背景切换直接进整张 BG。2–4 张叠加即在主线程上产生 200–600 ms 的空转。

### 2.2 读档 restore 才是 CG 入口的真瓶颈

先按「大图解码慢」优化后，CG 入口帧仍有 ~600 ms。抓 `perf_slow.log` 后发现慢帧里 `ops 0`、`render` 占比低，真正耗时在 `vm` + `vfs_read`：读档时 `MotionManager::apply_snapshot_v1` 会**同步**逐个 `vfs.read_file` + `load_texture` 恢复快照里的每一张图，CG 场景一次要恢复数张大图，全部压在进入 CG 的那一帧上。

## 3. 措施

### 3.1 新增 `crates/rfvp/src/subsystem/resources/async_decode.rs`

进程级异步解码队列（`spin::Mutex`，no_std 可用）：

- 四个表：`QUEUE`（待办）、`DONE`（结果）、`PENDING`（进行中，按 id）、`REQUESTED`（已请求的 path→id）；
- `Job{kind, id, path, bytes, …}`，kind = `KIND_GRAPH=0` / `KIND_PARTS=1` / `KIND_GRAPH_PREFETCH=2`；
- 阈值 `ASYNC_INLINE_MIN_BYTES = 1 MiB`：只对**大图**走异步，小图（UI 贴图）仍同步解码，避免打乱 UI 首帧；
- `run_next_job()` 由宿主线程每帧调用一次；`wait_for_*` 供「必须同步拿到」的路径（prefetch 命中失败等）兜底；`prefetch_path()` 入 `KIND_GRAPH_PREFETCH`。

### 3.2 主线程保留旧图，tick 里 apply

大图 submit 后**不立刻换纹理**：`graph_buff.rs`/`parts_manager.rs` 的加载路径返回「已排队」，主线程继续用上一张图渲染；`no_std_core.rs` 新增 `apply_async_decodes()` 在每帧 tick 检查 `DONE`，并用 `requested_matches` 校验代际，防止陈旧结果覆盖新请求。

### 3.3 读档 restore 走同一个队列

`graph_buff.rs::apply_snapshot_v1` / `parts_manager.rs::apply_snapshot_v1` 增加 `async_id` 参数：restore 到 ≥1 MiB 的图时改为提交 `KIND_GRAPH`/`KIND_PARTS` 任务并保留旧纹理，`[probe] restore path="graph_bg/BG043_000" queued=async bytes=3838866`。

### 3.4 宿主线程

`platform/switch/runtime/main.c` 用 libnx `threadCreate` 起解码线程；`platform/switch/host/src/decode.rs` 新增 `rfvp_switch_decode_step`；`host/src/lib.rs` 导出。

### 3.5 放弃的两条路线（负结果）

1. **大图直接 `return Nil` 异步加载**：破坏了游戏的加载时序（同一资源被重复同步加载、id 重新分配、worker 与主线程争 pack 锁），实测 `applied=0` —— 弃用；
2. **prefetch + wait**（预取 `X`↔`Xb` 姐妹资源与 `..._昞忣` 表情差分，加载时 `wait_for_*` 400–600 ms）：有效但仍是「第一张同步解」，收益只到 299 ms —— 保留为兜底，不作为主路径。

## 4. 验证（Citron，同一份真机复杂存档，进入 CG）

| 运行 | 措施 | CG 入口慢帧 |
| --- | --- | --- |
| p18-i | 仅 prefetch+wait | 632.2 ms |
| p18-j | + 大图异步 + 主线程保留旧图 | 299.1 ms |
| p18-k | + restore 走 async | **273.4 ms** |

p18-k 的 `perf_slow.log`（17 条慢帧）中：frame 2601（CG 入口）273.4 ms，其中 `vm 145.41`、`render 116.17`、`text 11.71`、`tree 28.16`、`audio_cmds 85.38`、`vfs_read 23.74`、`upload 27.63/16`、`ops 0`；随后 frame 2609 / 2617 降到 45.7 / 41.2 ms。异步结果 apply 共 6 次，画面正确（`after-p18k-cg.png` / `after-p18k-adv7.png`），全程 0 exception。

对比 p18-i：同一入口 632.2 ms，证明「主线程同步解 2–4 张大图 + restore 同步读图」是主因。

三次运行的 CG 入口截图**逐字节相同**（`before-p18i-cg.png` / `after-p18j-cg.png` / `after-p18k-cg.png` 的 sha256 均为 `8f7508e8…`），即画面状态一致、差异只在耗时，可直接作为同一场景的时序对比。

### 4.1 放弃 libdeflate

尝试把 inflate 换成 libdeflate（理论上比 zlib 再快 1.5–2×）：交叉编译接入后 Citron 启动 5.58 s 崩溃 —— `Cannot execute instruction at unmapped address 0x0`（libdeflate 的 CPU 特性派发在 aarch64/Citron 上取到空函数指针）。已整体回退到 P17 的 devkitPro zlib，不在本轮引入该依赖。

## 5. 产物

| 产物 | 值 |
| --- | --- |
| NRO | 7,929,912 B ｜ sha256 `796679cefb5fbfae5af3028d327970883baa2093fbb0a6a16fc29a409e19076c` |
| ELF | 17,254,624 B ｜ sha256 `741b92eae1b2dc7f516f83fd6b71b7c4e7a71b54080eae40a9101204dfa4f92b` |
| 增量补丁 `rfvp-async-decode.patch` | 43,704 B / 1,089 行 / 17 文件 ｜ sha256 `7c0c13672027a8be251e07869d65cbced77ad7ed2107bc286c4e76ba6afe3565`（需先应用 P17 全量） |
| 全量 `rfvp-full.diff` | 190,338 B / 4,858 行 / 17 文件 ｜ sha256 `5c012b7ae20835a227d5b25b7921c937b1c6564c9bf7c2bb8ce384c9292789fe` |
| 自包含 NSP v1.0.6 | 见 §5.1（TitleID `010047420000A000`，romfs 9,932,275,140 B / 161 条目） |

### 5.1 NSP v1.0.6

自包含 NSP（TitleID `010047420000A000`）：

| 项 | 值 |
| --- | --- |
| 文件 | `E:/galnx-build/p18/out/IROSEKA_FHD-010047420000a000.nsp` |
| 大小 | 9,979,494,616 B（romfs 9,932,275,140 B / 161 条目） |
| sha256 | `ca7c7c04ec21bb1b7c3aecc22b8f4ea2478696811088b70ea82b1db42143c528` |
| exefs/main | 4,671,503 B ｜ sha256 `3934a7b1e726f2daf52c331e221ee9b1f757b7c9b5cedd24a719b909b8a17df4` |
| exefs/main.npdm | 972 B ｜ sha256 `3cfb9877ba2b37018bbc66ec3c64c760c399ee80b4bc1bd6bee1d03b332ba565` |
| control/control.nacp | 16,384 B ｜ sha256 `435f7ffaf4314c310ac0b3e7001180227232d9b5ad7077038f5e5c3b6d32ed9f` |
| icon | 22,454 B ｜ sha256 `10daef90e30d9bcc7f4e40294f0694fd75c1b4f0c53d52b016cbdc2e2b980b79` |
| hacBrewPack | 535 s，STEP 6/6 nstool 结构检查 exit=0 |

构建前 E: 盘只剩 11 GB，第一次 hacBrewPack 在写盘中途 ENOSPC 被截断（产物 8,704,142,336 B，nstool 报 SubStream 越界，而 hacBrewPack 自身不报错）；清掉 6 个已被取代的旧 NSP（p18/p17/p16/p14/p12/p11 的 `out`）腾出 66 GB 后重建成功。**教训：构建 9.98 GB NSP 前先看 `df -h /e`；NSP 必须 ≥ romfs + 约 47 MB，失败只能靠尺寸和 nstool 警告识别。**

`galnx package nsp verify`（显式 `--nstool` + `--keyset`，13 项检查）：**0 fail / 1 warn / 0 skip**；3 个 NCA 的 ProgID 全为 `0x010047420000A000`，Program/Control/Meta 齐全，唯一 warn 是未签名 homebrew 的 RSA 签名 FAIL（预期）。无 keyset 时退化为 7 项检查（3 warn，PFS0 层正常）。

Citron 首启冒烟（`--game <nsp>`，detach，10 s 后点标题、点 CONTINUE、四次 `C` 推进）：窗口标题 `IROSEKA FHD (64-bit) | 1.0.6`，boot 行 `Booting game: 010047420000A000`，截图 nonblack 0.9018；进入存档画面（悠马「家庭教师？」）后四次推进读到「你不是只要努力还是能做好的吗？」，60 FPS，`0` 条 exception。证据 `docs/milestones/evidence/P18b-rfvp-nsp106/`。

**真机上传（DBI FTP，浏览 SD 卡模式）**：远端无同名文件（`SIZE_ERR 550`）→ 全新上传，9,979,494,616 B 用时 **1,409.6 s ≈ 6.75 MiB/s**，落在 `/switch/galnx-nsp/IROSEKA_FHD-010047420000a000.nsp`（上传后该目录仅此一个文件），SD 剩余 62.7 GB；日志 `/e/galnx-build/p18/upload/upload.log`（`UPLOAD_DONE`）。真机安装后按 §7 U1 复验 CG 表情切换、背景切换、打开游戏 UI 与整体手感。

## 6. 证据

### 6.1 目录

`docs/milestones/evidence/P18-rfvp-async/`：

- `before-p18i-cg.png`（632 ms 基线 CG）、`after-p18j-cg.png` / `after-p18j-adv7.png`、`after-p18k-cg.png` / `after-p18k-adv7.png`；
- `after-p18k-perf_slow.log`（17 条慢帧，含 CG 入口 273.4 ms）、`after-p18k-debug_report.txt`（ring log 93,634 B）；
- `after-p18j-ods-lines.txt` / `after-p18k-ods-lines.txt`（`async decode applied`、`graph async hit`、`[save] prepared` 等 ODS 切片）、`after-p18k-async-probe-lines.txt`（95 行 `[probe] restore` / `[async] submit` / `[async] decoded`）；
- `SHA256SUMS.txt`。

### 6.2 复现

```
# 1) 真机复杂存档放进 Citron sdmc，开启诊断
#    sdmc/switch/rfvp/saves/iroseka-2ae7dc8e/save/*.bin
#    sdmc/switch/rfvp/debug.txt = "1"
# 2) 跑 harness（docs/pilot/P11-rfvp-nsp-device-runbook.md 的 Citron 用法）
#    标题 Continue(1386,638) -> LOAD 列表 CONTINUE(455,911) -> 正文推进 7 句 -> 进 CG
# 3) 读 sdmc/switch/rfvp/perf_slow.log（CG 入口那帧的 stages）+ run dir 的 citron_log.txt（async applied）
```

## 7. 限制（U 项）

- **U1** 未在真机验证：全部数据来自 Citron x86_64；aarch64 的解码线程调度与内存带宽不同，需用户安装 v1.0.6 复验。
- **U2** 异步期间的可见降级：大图（≥1 MiB）异步解码时主线程继续显示**上一张图**，切换瞬间可能看到旧图停留 1–2 帧；这是刻意的取舍（不阻断渲染），不是丢帧。
- **U3** restore 走异步后，快照里的大图有极短窗口未就绪；若游戏在 restore 后立刻取该图尺寸做布局，理论上可能取到旧值（本作实测未见异常）。
- **U4** 自定义解码线程在 4 GB 机型的内存/栈余量未测；`threadCreate` 栈大小按 libnx 默认。
- **U5** parts 异步应用时色调恢复为默认 100（快照里的色调在 apply 时未逐项复原），本作 CG 表情切换未观察到偏色。
- **U6** libdeflate 路线已回退，未归档其补丁；结论仅记录为「Citron 上不可用」。
- **U7** 启动帧仍有 2.3 s（vfs_read 1.14 s + syscalls 191 ms），属冷启动一次性成本，未在本轮优化。

## 8. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-11-01 | 建立 P18：async_decode 队列 + 大图异步（≥1 MiB）+ 主线程保留旧图 + restore 走异步 + 宿主解码线程；CG 入口 632.2 → 273.4 ms；放弃 libdeflate；NSP v1.0.6 构建 |
| 2026-11-01 | NSP v1.0.6 经 DBI FTP 上传至真机 `/switch/galnx-nsp/`（1,409.6 s ≈ 6.75 MiB/s），待用户安装复验 |
