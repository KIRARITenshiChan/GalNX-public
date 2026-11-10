# 027 · rfvp async 强制关闭 + 帧心跳（v1.0.9）

> 里程碑：M5-m（rfvp Switch 后端）
> 日期：2026-11-05
> 引擎：rfvp 上游 HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
> 游戏：`E:/Othergames/Galgame/五彩斑斓的世界HD`（IROSEKA FHD，自包含 NSP）
> 触发：用户 m25411「1.0.8 的情况：依旧黑屏且无响应」

## 1. 结论

- v1.0.9 是**真机黑屏的止血版**：不再读取 `async.txt`，异步解码**永久关闭**（代码保留，`read_async_enabled()` 恒返回 0），保留 P11–P17 的同步路径性能补丁（SDL2/GLES2、输入、romfs、GPU prev-frame、惰性存档、资源缓存/预读/zlib）。
- 新增 opt-in 帧心跳：`sdmc:/switch/rfvp/debug.txt` 存在时，主循环写 `frame_status.txt`（`frame=<n> status=<c> async=0`），供下一次真机取证判断「卡在启动」还是「卡在渲染」。
- Citron 首启冒烟 PASS：即使 `async.txt` 写 `on`，`async_status.txt` 仍为 `enabled=0`；`frame_status.txt` 计数正常增长（见 `7）。

## 2. 背景：v1.0.8 为什么没解决问题

v1.0.8 加了 stage 诊断与 3 s 看门狗，但真机仍黑屏，且取回的 `async_status.txt` 为：

```
enabled=1 create=0x0 start=0x0 hb=3 stage=0
```

线程创建/启动都成功、心跳只到 3 次、stage 停在 0 → **整进程挂起**，而不是 worker 卡住而主线程继续跑帧。看门狗只在主线程每帧的 `apply_async_decodes()` 顶部调用，主线程一旦自旋就永远执行不到，因此**看门狗结构性失效**。

独立静态根因分析（teammate `async-rca`，436 行，已归档 `docs/experiments/rfvp-async-hang-rca.md`）：

1. **同核优先级反转 + 自旋锁跨阻塞 SD 读**（≈85% 置信）：worker 与主线程同 ideal core 0（Horizon 进程 ideal core；`threadCreate` cpuid=-2），主线程 prio `0x2C` 高于 worker `0x30`；worker 在 `read_bytes` 里以 `HostPackFile::read_at` 持 `spin::Mutex`（spin 0.9.8 纯自旋）做 `fseek+fread`，在 fs IPC 睡眠时**锁不释放**；主线程同帧继续同步读同一 pack，在自旋锁上用户态空转，永不让出 core 0 → worker 饿死、锁永不释放、双线程停住、黑屏且无崩溃。这也解释了为何 async=off 正常、Citron 不复现（guest 线程映射到宿主，无同核优先级语义）。
2. **resource_cache 自旋锁临界区过长**（中低）：持锁时 `perf::event → log::info!`（嵌套 LINES 锁）且 LRU 淘汰会 drop 13 MB 级 `Arc`。
3. **看门狗与关断入口无效**（100% 确定）：`watchdog_stalled()` 只在主线程 tick 调用；`rfvp_switch_async_disable` 全仓无调用者；`drain_inline` 恢复时也会撞同一把 pack 锁。

正确修法（改 pack 读为睡眠锁 / 主线程与 worker 各自 FILE 句柄 / 换核+改优先级 / 看门狗改独立线程）都在**并发模型层**，风险与验证成本高，不应与「黑屏修复」捆在同一版。故 v1.0.9 选择：**async 彻底关闭，先恢复真机可用**，async 的并发修复另立实验（见 `8）。

## 3. 措施（v1.0.9）

| 文件 | 改动 |
| --- | --- |
| `platform/switch/runtime/main.c` | `read_async_enabled()` 由「读 `sdmc:/switch/rfvp/async.txt`」改为 `return 0`，注释记录 v1.0.8 冻结签名（`hb=3 stage=0`）与看门狗失效原因；新增 `debug_probe_enabled()`（探测 `debug.txt` 是否存在）与 `write_frame_status()`；主循环在 `frame == 1` 或每 15 帧写一次心跳（仅 debug.txt 存在时）；sync 路径与 romfs/游戏根逻辑不变 |
| `platform/switch/host/Cargo.toml` | 版本 `1.0.8` → `1.0.9` |
| `Cargo.lock` | 版本同步 1 行 |

设计取舍：不删 async 代码、不删 `threadCreate` 分支（`enabled==0` 时根本不执行），保留 P18 成果以便后续修好锁后一行开关就能重开；`async_status.txt` 仍照写（`enabled=0 create=0x0 start=0x0 hb=0 stage=0`），作为「async 已被硬关闭」的证据。

## 4. 构建

| 项 | 值 |
| --- | --- |
| 构建根 | `/e/galnx-build/m5-rfvp`（HEAD `9f07ade`，工作树含 P11–P20 全部改动） |
| 命令 | `env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m5-build-instr.sh'`（wrapper 先 sed 掉 `rustup toolchain install` 行；`DEVKITPRO=D:/devkitPro`、`CARGO_HOME=D:/Scoop/persist/rustup/.cargo`） |
| 耗时 | `BUILD_EXIT=0 ELAPSED_S=25` |
| NRO | `target/rfvp-switch/switch/rfvp.nro` 7,929,912 B，SHA-256 `d34380df1bdd67665116cd37c5f0488b465e7acbd5c20eec6ba8eea55e42f7ca` |
| ELF | `target/rfvp-switch-runtime/rfvp.elf` 17,258,040 B，SHA-256 `e06b165228e6b6ce7aee08f8c020cb80b5faa161b4236235de06ec6c609af6ff` |

main.c 最终 408 行 / 16,359 B（新增心跳函数与注释后比 v1.0.8 的 15,860 B 多 499 B）。

## 5. NSP 打包（v1.0.9，自包含）

| 项 | 值 |
| --- | --- |
| 输出 | `E:/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp` |
| 大小 / SHA-256 | 9,979,495,640 B / `726bb2d1b0494256b5e5b12ca9d8e08b053ab56022593f562762d256c0d3c0d9` |
| hacBrewPack | OK in 543 s（romfs 9,932,275,140 B，game entries 161） |
| main | 4,672,898 B，SHA-256 `b1744cd3…`（完整值见构建日志） |
| main.npdm | 972 B，SHA-256 `3cfb9877…` |
| control.nacp | 16,384 B，SHA-256 `77e13530…` |
| icon | 22,454 B，SHA-256 `10daef90…` |

命令与 `build_nsp_game.sh` 参数见 `E:/galnx-build/p21/build-nsp.sh`（显式 `--keyset`、`--romfs-mode hardlink`；keys 只本机离线使用，不入库/日志）。

**尺寸自检**：NSP 必须 ≥ romfs 大小 + 约 47 MB；P18 曾因 E: 盘只剩 11 GB 被写截断成 8.7 GB 而 hacBrewPack 仍 exit 0，nstool 才报 SubStream 越界。构建前务必 `df -h /e`。

## 6. verify

```bash
cd '/e/Othergames/Nintendo Switch/Workspace/GalNX'
PYTHONPATH=src python -m galnx package nsp verify \
  --nsp /e/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp \
  --manifest examples/pilot02-iroseka.yaml \
  --nstool /e/galnx-build/m3-tools/nstool.exe \
  --keyset 'E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys' --json
```

- 结果：`ok=true`；**12 checks = 11 ok + 1 warn**（`NCA signature FAIL` 属未签名 homebrew 的预期）；PFS0 3 files；3 个 NCA（Program 0x252d0e800 / Meta 0x1000 / Control 0x20c00）ProgID 全为 `0x010047420000A000`。
- 完整 JSON 归档：`/e/galnx-build/p21/verify.json`（构建机产物，不入库）。

## 7. Citron 首启冒烟（PASS）

前置（反向验证 async 硬关闭）：

1. 把 `C:/Users/<user>/AppData/Roaming/citron/sdmc/switch/rfvp/game` 改名为 `game-sakura-hold`，让 NSP 走内嵌 romfs；
2. **故意**写 `async.txt` = `on`、`debug.txt` = `shot=600`，清旧日志。

命令（`E:/galnx-build/p21/run-nsp109.sh`，detach 模式）：

```bash
bash scripts/citron_run.sh --game /e/galnx-build/p21/out/IROSEKA_FHD-010047420000a000.nsp \
  --no-stage --timeout 240 --settle 12 --allow-existing --expect-title IROSEKA \
  --out /e/galnx-build/p21/run-nsp \
  --input-steps 'wait:18000;capture:t1-title;wait:12000;capture:t2;wait:12000;capture:t3'
```

结果：`status=loaded`；窗口标题 `citron Nightly | 0237a9b88 | IROSEKA FHD (64-bit) | 1.0.9 | NVIDIA`；`boot_line` = `Booting game: 010047420000A000`；19 s、6/6 steps ok、截图 `nonblack=0.9018`、0 exception。

| 关键证据 | 值 |
| --- | --- |
| `async_status.txt` | `enabled=0 create=0x0 start=0x0 hb=0 stage=0`（async.txt=on 仍被忽略） |
| `frame_status.txt` | `frame=4290 status=0 async=0`（心跳生效、帧在推进） |
| run_dir | `E:/galnx-build/p21/run-nsp/20261105-060924-IROSEKA_FHD-010047420000a000` |
| 证据目录 | `docs/milestones/evidence/P21a-v109-nsp-smoke/`（result.json、run.log、3 张截图、input-steps.tsv、async/frame_status、perf_slow.log、debug_report.txt、SHA256SUMS） |

## 8. 预期、风险与后续

- **真机预期**：v1.0.8 的黑屏路径（async worker）不再可能触发；P18 的 CG 入口 632→273 ms 收益随 async 一起失效，CG/背景切换回到 P17 同步档（仍保留 P17 缓存+预读，UI 卡顿不会回到 v1.0.5）。
- **若真机仍黑**：先取 `frame_status.txt`——帧号增长说明渲染/显示层问题；不增长说明卡在启动装载（vfs/romfs/游戏根探测），与 async 无关；同时看 `debug_report.txt` 头行与 `perf_slow.log`。
- **async 重启条件**（另立实验，不阻塞交付）：pack 读改睡眠锁或每线程独立 FILE 句柄 + 看门狗改独立线程监视帧/心跳原子量；建议顺序：先 E1/E2 最小实验（worker 优先级 `0x30→0x2B`、cpuid `-2→1` 换核）在真机验证假设，再决定是否重写锁。
- **未验证**：真机（NSP 待用户安装）；720p 第二作基线见 `docs/experiments/perf-01-sakura-720p.md`。
- **回退**：`git apply -R docs/builds/patches/rfvp-switch/rfvp-async-off.patch` 并重构建。

## 9. 补丁与全量对照

| 产物 | 大小 | SHA-256 | 说明 |
| --- | --- | --- | --- |
| `rfvp-async-off.patch` | 3,490 B | `35658e39b30e3419b14f19a46dd97b2b40442eac0e6f3ef89430702670d83505` | 增量：2 文件 +25/−10（main.c + host/Cargo.toml） |
| `rfvp-full.diff` | 199,493 B | `9901a14dcd33fa448f9ff58add2a04daa49b00b4f17992e44859d3ba311efd43` | HEAD→v1.0.9 全量：33 文件 +3,811/−247 |

- 应用：`git apply rfvp-async-off.patch`（在 v1.0.8 全量树之上），或直接 `git apply rfvp-full.diff`。
- 基线复现：`git worktree add --detach /e/galnx-build/p21/rfvp-v108 9f07ade` → apply v1.0.8 全量 diff（`198,586 B / sha 19720846…`）→ commit（main.c 15,860 B）→ 覆盖 v1.0.9 的 main.c + Cargo.toml → `git diff`。
- **教训**：按 README 顺序 replay 11 个增量补丁在 `rfvp-input-remap.patch` 处触发 `event.rs:1` context 失败——增量链不是可靠的重建路径；每次发版应同时保存「HEAD→当前」全量 diff 并作为唯一下一版基线。

## 10. 相关记录

- 前一版：`docs/builds/026-rfvp-async-watchdog.md`（P20 / v1.0.8，stage 诊断 + 看门狗）
- async 根因：`docs/experiments/rfvp-async-hang-rca.md`（RCA，含 H1–H4 假设、证据与最小验证方案）
- 720p 第二作：`docs/experiments/perf-01-sakura-720p.md`
- 补丁索引：`docs/builds/patches/rfvp-switch/README.md`