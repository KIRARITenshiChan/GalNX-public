# 025 · rfvp 异步解码开关（v1.0.7 黑屏回归修复）

> 里程碑：M5-l（rfvp Switch 后端）
> 日期：2026-11-01
> 引擎：rfvp 上游 HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
> 游戏：`E:/Othergames/Galgame/五彩斑斓的世界HD`（IROSEKA FHD，自包含 NSP）
> 触发：用户 m24478 真机反馈「启动游戏后卡黑屏」

## 1. 现象与目标

v1.0.6（P18 大图异步解码 + 读档异步 restore）在 Citron 上首启正常、CG/背景切换明显变快，但推到真机后**进入游戏即黑屏**。目标：先让真机恢复到 v1.0.5 的可玩基线（不黑屏），同时保留 P16/P17 的存档/缓存优化，并把 P18 异步能力做成**可运行时开关**用于 A/B 诊断。

## 2. 根因判断

v1.0.6 相对 v1.0.5 新增了一个**无条件创建**的解码 worker 线程（P18）：

```
platform/switch/runtime/main.c
  threadCreate(&decode_thread, rfvp_decode_thread, NULL, NULL, 0x20000, 0x30, -2);
  threadStart(&decode_thread);        // 返回值未检查
```

而 `graph_load` 在大图（≥1 MiB）时一旦 `submit_graph` 成功就**立即 `return Ok(Variant::Nil)`**，等 worker 解码完成后再由 `apply_async_decodes` 替换纹理。若真机上线程未创建成功 / 未运行 / 卡死，大图永远拿不到内容，标题与背景全空 → 黑屏。Citron/Ryujinx 在线程正常时无法复现，因此该缺陷只在真机暴露。

关键代码位（v1.0.6）：

| 位置 | 行为 |
| --- | --- |
| `crates/rfvp/src/subsystem/components/syscalls/graph.rs:1049-1054` | `if size>=ASYNC_INLINE_MIN_BYTES && submit_graph(...) { return Ok(Variant::Nil); }` |
| `crates/rfvp/src/subsystem/resources/async_decode.rs` | `submit_graph/submit_parts/submit_prefetch_graph` 入队即返回 true |
| `crates/rfvp/src/no_std_core.rs:523`（`apply_async_decodes`） | 每帧从 `DONE` 取结果替换纹理 |
| `platform/switch/runtime/main.c:285-287` | worker `threadCreate/threadStart` 未检查返回值 |

## 3. 措施（v1.0.7）

### 3.1 异步解码改为运行时开关，默认关闭

- `platform/switch/runtime/main.c` 新增全局开关与状态落盘：
  - `int g_rfvp_async_enabled = 0;`、`int rfvp_switch_async_enabled(void)` 供引擎侧查询。
  - 启动时 `read_async_enabled()` 读 `sdmc:/switch/rfvp/async.txt`：内容含 `on`/`ON`/`1` 才开启，缺省**关**。
  - `threadCreate`/`threadStart` 返回值被检查，任一失败立即回落 `g_rfvp_async_enabled = 0`。
  - 状态写 `sdmc:/switch/rfvp/async_status.txt`，格式 `enabled=%d create=0x%x start=0x%x hb=%u`（`hb` = worker 心跳，每 1000 次循环刷新，可判定线程是否真的在跑）。
  - worker 循环每次 `g_rfvp_async_heartbeat++`，空闲 `svcSleepThread(1 ms)`。
- `crates/rfvp/src/subsystem/resources/async_decode.rs` 新增 `async_enabled()`（`feature = "switch-async"` + `no_std` 时走 `extern "C" rfvp_switch_async_enabled()`，否则按构建特性返回），并在五个入口加 guard：
  - `submit_graph` / `submit_parts` / `submit_prefetch_graph` → 关闭时直接 `return false`，调用方回落同步解码路径；
  - `wait_for_graph` / `wait_for_parts` → 关闭时直接查缓存返回（不做轮询等待）。

即：**关闭时行为等价 v1.0.5 的同步解码**，大图不再 `return Nil`，不会留空纹理。

### 3.2 版本

`platform/switch/host/Cargo.toml` version `0.1.0` → `1.0.7`（`Cargo.lock` 同步 1 行）。

## 4. 验证

### 4.1 构建

| 项 | 值 |
| --- | --- |
| 构建根 | `/e/galnx-build/m5-rfvp`（`git` 仓库，HEAD `9f07ade`） |
| 命令 | `bash /e/galnx-build/p19/m5-build-p19.sh`（`build_switch.sh` 删掉 `rustup toolchain install` 行后执行；需 `DEVKITPRO`/`CARGO_HOME`/代理环境） |
| 耗时 | 24 s（增量） |
| NRO | `target/rfvp-switch/switch/rfvp.nro` 7,929,912 B sha256 `a6efe53b6af9253653eacc62bc91ce058972fbef08c783072648ef27c06fad0f` |
| ELF | `target/rfvp-switch-runtime/rfvp.elf` 17,257,504 B sha256 `98c6464b76b4e429f2d031d1bb5d5ec98b31cefe0195a95714b912f779c74fb5` |

### 4.2 Citron NRO 冒烟（默认 async 关）

| 项 | 值 |
| --- | --- |
| 命令 | `scripts/citron_run.sh --nro .../rfvp.nro --detach --timeout 120 --settle 8 --out /e/galnx-build/p19/run-nro --input-steps 'wait:14000;capture:n0-title;key:C;wait:2500;capture:n1-adv'` |
| 结果 | `status=loaded`；窗口标题 `citron Nightly | 0237a9b88 | rfvp (64-bit) | NVIDIA`；boot 行 `Booting game: 0000000000000000 | rfvp (64-bit) |` |
| 画面 | 两帧 nonblack **0.9018**；推进前后 diff **0.455366**（C 生效） |
| 异常 | `log_slice_latest.txt` 中 exception 行 **0** |
| 开关状态 | `sdmc:/switch/rfvp/async_status.txt` = `enabled=0 create=0x0 start=0x0 hb=0`（默认关、线程未创建，符合预期） |

### 4.3 NSP v1.0.7

| 项 | 值 |
| --- | --- |
| NSP | `E:/galnx-build/p19/out/IROSEKA_FHD-010047420000a000.nsp` **9,979,495,640 B** sha256 `97d679ffc2eb70354ec75fcf85ebccc0582d75b3c7454ad1135160acc3096323` |
| 版本 | `1.0.7`（v1.0.6 = 9,979,494,616 B / `ca7c7c04…`；+1,024 B 为版本串差异） |
| romfs | 9,932,275,140 B / 161 项（与 v1.0.6 相同） |
| 构建 | `bash /e/galnx-build/p19/build-nsp.sh`（hacBrewPack 约 535 s；构建前 `E:` 余量 261 GB） |
| 输入 | main 4,672,527 B、main.npdm 972 B、control.nacp 16,384 B、icon 22,454 B（`examples/pilot02/icon-256.jpg`） |
| verify | `galnx package nsp verify`（显式 `--nstool E:/galnx-build/m3-tools/nstool.exe` + `--keyset …/prod.keys`）= **13 checks / 0 fail / 1 warn / 0 skip**；PFS0 FileNum 3；3 NCA ProgID 全 `0x010047420000A000` |
| warn | 未签名 homebrew 的 NCA signature FAIL（预期，hacBrewPack 非 Nintendo 密钥） |

Citron NSP 首启冒烟（`/e/galnx-build/p19/run-nsp107.sh`，默认 async 关）：

| 项 | 值 |
| --- | --- |
| run_dir | `E:/galnx-build/p19/run-nsp/20261101-nsp107/20261101-210157-IROSEKA_FHD-010047420000a000` |
| 结果 | `status=loaded`；窗口标题 `citron Nightly | 0237a9b88 | IROSEKA FHD (64-bit) | 1.0.7 | NVIDIA`；boot 行含 `1.0.7` |
| 画面 | 7 帧 nonblack 全 **0.9018**；20 步 0 失败；首帧→末帧 diff **0.806295**（读档 + 4 次 C 推进） |
| 内容 | 读档进入正文（悠马「家庭教师？」）→ 4 次 C 后中文对白推进（泽「你不是只要努力还是能做好的吗？」），60 FPS |
| 异常 | `log_slice_latest.txt` 中 exception 行 **0** |
| 开关状态 | `sdmc:/switch/rfvp/async_status.txt` = `enabled=0 create=0x0 start=0x0 hb=0`（NSP 形态亦默认关、线程未创建） |
| 证据 | `docs/milestones/evidence/P19b-rfvp-nsp107/`（`nsp107-load.png` `133fc45f…`、`nsp107-adv4.png` `acc2fff4…`、`result.json` `d4c36046…`、`citron-log-slice.txt` `128d9483…`、`async_status.txt`） |

## 5. 产物

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| 增量补丁 `rfvp-async-toggle.patch`（4 文件 / 189 行） | 6,988 B | `6bdc0a61f65950cd9c0549c4dcd77370526cf9862c61f183cb03f06f5820208d` |
| 全量 diff `rfvp-full.diff`（对上游 `9f07ade`） | 194,079 B / 4,968 行 | `d0a5d09042b03fae6159e69316da69f150f8352a52a41d7c2cf43e80e8f28c60` |
| NRO | 7,929,912 B | `a6efe53b6af9253653eacc62bc91ce058972fbef08c783072648ef27c06fad0f` |
| ELF | 17,257,504 B | `98c6464b76b4e429f2d031d1bb5d5ec98b31cefe0195a95714b912f779c74fb5` |
| NSP v1.0.7 | 9,979,495,640 B | `97d679ffc2eb70354ec75fcf85ebccc0582d75b3c7454ad1135160acc3096323` |

补丁文件位置：`docs/builds/patches/rfvp-switch/rfvp-async-toggle.patch`；全量 diff：`docs/builds/patches/rfvp-switch/rfvp-full.diff`（P19 基线）。

## 6. 证据

- 目录：`docs/milestones/evidence/P19-rfvp-async-toggle/`（NRO 冒烟）、`docs/milestones/evidence/P19b-rfvp-nsp107/`（NSP 首启冒烟）、`docs/milestones/evidence/P19c-device-logs/`（真机 v1.0.6 日志取证）
- 内容：`nro-title.png`、`nro-adv.png`、`result.json`、`citron-log-slice.txt`、`async_status.txt`、`rfvp-async-toggle.patch`、`nro-build.log`、`SHA256SUMS.txt`
- P19c 内容：`debug_report-v106.txt`（真机 `/switch/rfvp/debug_report.txt`，114,823 B）、`perf_slow-v106.log`（111,565 B）、`README.md`（结论与限制）、`SHA256SUMS.txt`；关键结论=**report 来自 9600 帧的正常会话（非黑屏那次）**、**rfvp 无崩溃报告且无 `last_error.txt`** → 黑屏更像挂起/空渲染而非崩溃。
- 复现：
  - 构建：`bash /e/galnx-build/p19/m5-build-p19.sh`
  - 冒烟：见 §4.2 命令（先删除 sdmc 下 `async_status.txt`/`async.txt`）
  - 真机 A/B：默认不建 `async.txt` = 关闭；写入 `on` 后重启 = 开启

## 7. 限制与未验证

- **U1**：真机黑屏的**直接证据仍未取得**。已从真机拉取 v1.0.6 的 `debug_report.txt`/`perf_slow.log`（见 `P19c-device-logs`）：report 末帧为 9600 帧的正常会话（黑屏若在 60 帧内不会刷新该文件，故为残留），且 `/atmosphere/crash_reports/` 无 rfvp 报告、`/switch/rfvp/last_error.txt` 不存在 → **判定为挂起/空渲染而非崩溃**，async 线程是否参与仍待 A/B 复验。
- **U2**：Citron 无法复现黑屏（Citron 线程调度正常），因此 v1.0.6 的失败机理仍属**推断**：线程未起/未跑或竞态；注意 `[async]` 诊断走 host.log→ODS（仅 nxlink 可见），不进 ring log，故 report 里无 `[async]` 行**不能**作为 async 未运行的证据。
- **U3**：默认关闭 async 后，P18 带来的 CG 入口 632→273 ms 收益在真机不再生效；若 A/B 证明 async 正常，可在 v1.0.8 重新默认开启并只对真机异常做兜底。
- **U4**：`async.txt` 开关是临时诊断通道，后续应换成配置项并写入文档。
- **U5**：NSP v1.0.7 未签名，真机仍需 CFG + sigpatches（与之前一致）。

## 8. 变更记录

| 日期 | 内容 |
| --- | --- |
| 2026-11-01 | 首版：async 运行时开关（默认关）+ threadCreate/Start 返回值检查 + async_status 落盘；NRO 冒烟 PASS；NSP v1.0.7 构建 |
| 2026-11-01 | 补 §4.3：NSP v1.0.7 9,979,495,640 B `97d679ff…`、verify 13 checks 0 fail 1 warn、Citron NSP 首启冒烟 PASS（7 帧 nonblack 0.9018、exception 0、async_status enabled=0）；产物表 NSP 行填实 |
| 2026-11-01 | 补 §6/§7：真机日志取证（`P19c-device-logs`），U1/U2 改写为「挂起/空渲染、无线下 async 证据」；NSP v1.0.7 已上传真机 `/switch/galnx-nsp/`（1468.3 s，6.48 MiB/s） |
