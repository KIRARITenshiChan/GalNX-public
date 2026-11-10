# 026 · rfvp 异步解码看门狗与阶段诊断（v1.0.8）

> 里程碑：M5-m（rfvp Switch 后端）
> 日期：2026-11-01
> 引擎：rfvp 上游 HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`
> 游戏：`E:/Othergames/Galgame/五彩斑斓的世界HD`（IROSEKA FHD，自包含 NSP）
> 触发：用户 m24478「真机启动游戏后卡黑屏」+ m24969「开启 async 确实会黑屏」

## 1. 现象与目标

v1.0.6（P18 大图异步解码）推到真机后进入游戏即黑屏；v1.0.7（P19）把异步解码做成运行时开关并默认关闭，真机恢复到 v1.0.5 的可玩基线，但 P18 的 CG 收益在真机不可用。用户 m24969 实测确认：**`async.txt` 写 `on` 后确实黑屏**。

目标：在真机上把异步解码**安全打开**（不黑屏 + 恢复 CG 收益），并留下足以定位卡点的阶段诊断。

## 2. 根因取证（真机 async=on 会话）

用 MTP（Shell COM，`GetFolder` + `CopyHere(20)`）从真机拉 `/switch/rfvp/` 与 `/atmosphere/crash_reports/`：

| 文件 | 内容 | 判定 |
| --- | --- | --- |
| `async_status.txt` | `enabled=1 create=0x0 start=0x0 hb=4` | 开关生效、`threadCreate`/`threadStart` 均成功（`0x0`）、写状态时 worker 已跑 4 次心跳 |
| `async.txt` | `off` | 用户测完已改回 |
| `debug_report.txt` | 头行 `frame 2760: 60.0 fps … slowest 17.9 ms`；`[async]` 行 0 条 | **不是 async=on 那次**（黑屏会话在 60 帧内冻住，report 未刷新，仍是上一次正常会话残留） |
| `perf_slow.log` | 8 次 `frame 1` 启动记录；尾部 `frame 1 slow 4337.9 ms \| vm 651.52 … vfs_read 3267.02` | 同样为多次正常启动的累积，非黑屏会话 |
| `/atmosphere/crash_reports/01793356593_01009bc00c38a000.log` | `Process Name: hbloader`、`sphaira + 0x16af60` PC、`Data Abort` | **与本项目无关**（hbmenu/sphaira 自己的崩溃，非 IROSEKA/rfvp） |
| `/switch/rfvp/last_error.txt` | 不存在 | 无 Rust panic → 不是 panic 退出 |

**推断链**：`enabled=1` + `create/start=0x0` + `hb=4` 说明线程确实起来并进了循环，但心跳只到 4；同期主线程在 60 帧内停止刷新 report、屏幕全黑、无崩溃报告 → **整进程挂起**，不是单纯纹理缺失。最可能是 worker 在首个 decode 内阻塞/死锁（持某把 `spin::Mutex`），主线程随后在 `submit_graph` 或缓存锁上自旋。

## 3. 措施（v1.0.8）

### 3.1 阶段诊断（可定位卡在哪一步）

- `crates/rfvp/src/subsystem/resources/async_decode.rs`：新增 `pub fn report_stage(stage: i32)`（0 idle / 1 pop / 2 read / 3 decode / 4 publish），`switch-async` + `no_std` 时调用 C 侧 `rfvp_switch_async_stage()`，其余构建为 no-op；`run_next_job()` 在 pop 后、读包前/解码前、publish 后、回到空闲时分别上报。
- `platform/switch/runtime/main.c`：`static volatile int g_rfvp_async_stage`，新增 `void rfvp_switch_async_stage(int)` 与 `void rfvp_switch_async_disable(void)`；`write_async_status()` 格式扩展为 `enabled=%d create=0x%x start=0x%x hb=%u stage=%d`；除 worker 每 1000 次心跳刷新外，主线程每 600 帧也刷一次（即使 worker 卡住，`stage` 会停在卡点）。

### 3.2 看门狗自愈（最坏情况只卡一次）

- 新增 `const WATCHDOG_STALL_US: u64 = 3_000_000;` + `WATCH_PENDING: spin::Mutex<Option<(usize, u64)>>`；`pub fn watchdog_stalled() -> bool`：pending 归零则清状态；pending 数与 3 s 前相同则判定卡死。
- `pub fn drain_inline() -> usize`：主线程直接 pop 队列，复用 `read_bytes` + `decode` 同步解码并 `finish_job` 推进 `DONE`。
- `crates/rfvp/src/no_std_core.rs` 的 `apply_async_decodes` 开头：`watchdog_stalled()` 为真时 `drain_inline()` + `log::warn!` + C 侧关掉 async + `report_stage(0)`，下一帧 apply 队列即可恢复画面。
- 效果：worker 若在真机卡死，最坏情况是**黑 3 秒后被同步补完并自动关闭 async**，不再永久黑屏。

### 3.3 资源与版本

- worker 线程栈 `0x20000` → `0x100000`（1 MiB），降低大图解码爆栈风险。
- `platform/switch/host/Cargo.toml` version `1.0.7` → `1.0.8`（`Cargo.lock` 同步 1 行）。

## 4. 验证

### 4.1 构建

| 项 | 值 |
| --- | --- |
| 构建根 | `/e/galnx-build/m5-rfvp`（HEAD `9f07ade`） |
| 命令 | `bash /e/galnx-build/p19/m5-build-p19.sh`（删 `rustup toolchain install` 行；需 `DEVKITPRO`/`CARGO_HOME`/代理） |
| 耗时 | 23 s（增量） |
| NRO | 7,929,912 B sha256 `d16fc0d3781965cf26dc4e4d9040e09dd9c17d3c347b7f934f659ad5d218921a` |
| ELF | `target/rfvp-switch-runtime/rfvp.elf`（同步更新） |

### 4.2 Citron async=on 冒烟（关键回归项）

先写 `sdmc:/switch/rfvp/async.txt` = `on`，清 `async_status.txt`/`debug_report.txt`/`perf_slow.log`/`last_error.txt`，再：

```
bash scripts/citron_run.sh --nro .../rfvp.nro --detach --timeout 180 --settle 8 \
  --out /e/galnx-build/p20/run-async-on --allow-existing \
  --input-steps 'wait:14000;capture:a0-title;click:1386,638;wait:8000;capture:a1-list;click:455,911;wait:20000;capture:a2-loaded;key:C;wait:2500;capture:a3-adv'
```

| 项 | 值 |
| --- | --- |
| run_dir | `E:/galnx-build/p20/run-async-on/20261101-222311-rfvp` |
| 结果 | `status=loaded`；窗口标题 `citron Nightly | 0237a9b88 | rfvp (64-bit) | NVIDIA` |
| 画面 | nonblack **0.9018**；10 步全 ok（含两次点进读档/Continue） |
| 开关状态 | `async_status.txt` = `enabled=1 create=0x0 start=0x0 hb=77000 stage=0` → worker 跑 77,000 次循环、最终回到 idle、**无卡死** |
| 异常 | 无 `last_error.txt`；日志无 `stalled`（唯一命中是 Citron 自己的 `Installed firmware` 子串） |
| `[async]` 行 | `debug_report.txt` 中 30 条（submit/decoded/done 成对），如 `graph/title_bg1_A` 2,051,578 B `us=384739`、`graph_bg/BG043_000` 3,838,866 B `us=138489`、`graph_bg/BG043_000b` 2,223,174 B `us=170023`、`graph_bs/CHR_…_昞忣` parts 3,447,414 B |

即：**v1.0.8 的看门狗与阶段上报在模拟器上不误触发、异步路径照常工作**。

### 4.3 NSP v1.0.8

| 项 | 值 |
| --- | --- |
| 产物 | `E:/galnx-build/p20/out/IROSEKA_FHD-010047420000a000.nsp` **9,979,496,664 B** sha256 `6af9072904ac6bb57cb12753edd43a70d29e1bd87d51ea8198f31f6140ee130b`（v1.0.7 为 9,979,495,640 B `97d679ff…`，+1,024 B 属版本串差异） |
| 构建 | `hacBrewPack` OK in 537 s；`--romfs-mode hardlink`；romfs 9,932,275,140 B / 161 项（复用 `p18/work/romfs`，未重建）；构建前 E: 余量 242 GB（吸取上轮磁盘满教训） |
| verify | `galnx package nsp verify`（`--nstool E:/galnx-build/m3-tools/nstool.exe` + 显式 `--keyset`）：**13 checks / 0 fail / 1 warn / 0 skip**；PFS0 FileNum 3；3 个 NCA ProgID 全 `0x010047420000a000`；warn=未签名 homebrew（预期） |
| Citron 首启冒烟 | run_dir `E:/galnx-build/p20/run-nsp/20261101-nsp108/20261101-224015-IROSEKA_FHD-010047420000a000`；`status=loaded`；窗口标题 `citron Nightly | 0237a9b88 | IROSEKA FHD (64-bit) | 1.0.8 | NVIDIA`；boot 行含 `1.0.8`；7 帧 nonblack **0.9018**；20 步全 ok（读档 → 4 次 C 推进）；日志 exception 行 **0** |
| 开关状态 | `async_status.txt` = `enabled=0 create=0x0 start=0x0 hb=0 stage=0` → NSP 形态同样默认关、线程未创建 |
| 结论 | v1.0.8 在 NSP 形态下默认启动、读档、推进均正常；黑屏回归项只在"写 `async.txt`=on"路径待真机验证 |

### 4.4 真机上传（MTP）

本轮设备处于 **MTP 响应器**模式：DBI FTP 的 5000 端口探测为 `ConnectionRefusedError`，故改走 Windows Shell COM（WPD）。

| 项 | 值 |
| --- | --- |
| 通道路径 | `This PC → Switch → 1: SD Card → switch → galnx-nsp`（子目录必须用 `ShellFolderItem.GetFolder`，对 MTP 调 `NameSpace(path)` 会返回 `$null`） |
| 传输方式 | `$gn.CopyHere($srcItem, 20)`；**`CopyHere` 的 flags 不能抑制 MTP 进度框**，桌面会弹出系统「正在复制…」对话框（22:53 截图显示约 60% / 剩余 4 分钟，22:54 显示剩余 2 分钟） |
| 耗时 | 9,979,496,664 B 约 **10 分钟**（22:47:42 发出 `COPYHERE_ISSUED`，22:57:30 前后对话框消失） |
| 落地名 | `/switch/galnx-nsp/IROSEKA_FHD-010047420000a000.nsp`；`CopyHere` **不会重命名**，脚本里预设的 `-v108` 轮询名不生效（实际仍按源文件名落地），这是 MTP 路径的一个坑 |
| 校验 | MTP 的 `ShellFolderItem.Size` 恒为 `0`，必须读 `ExtendedProperty('System.Size')`：得到 **9979496664**，与 §4.3 的本地产物字节数一致，即 MTP 未截断 4 GiB/9.98 GB 大文件 |
| 证据 | `docs/milestones/evidence/P20d-device-mtp-upload/`（`mtp-upload.log`、两张进度对话框截图、`list-after.txt`、`SHA256SUMS.txt`） |

## 5. 产物

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| 增量补丁 `rfvp-async-watchdog.patch`（5 文件 / 280 行） | 10,494 B | `3613a6dbe97fdcb80cae322e5e81cf433f8814c4ea91dc9ff61f1b0ef53ddafb` |
| 全量 diff `rfvp-full.diff`（对上游 `9f07ade`，P16→v1.0.8） | 198,586 B / 5,082 行 | `197208462f7c615b72ebdc0982140eb19802732163c79e7ef1f571b8be3e3ec6` |
| NRO | 7,929,912 B | `d16fc0d3781965cf26dc4e4d9040e09dd9c17d3c347b7f934f659ad5d218921a` |
| NSP v1.0.8 | 9,979,496,664 B | `6af9072904ac6bb57cb12753edd43a70d29e1bd87d51ea8198f31f6140ee130b` |

补丁位置：`docs/builds/patches/rfvp-switch/rfvp-async-watchdog.patch`；全量 diff 覆盖 `docs/builds/patches/rfvp-switch/rfvp-full.diff`（P20 基线）。

## 6. 证据

- `docs/milestones/evidence/P20-rfvp-async-watchdog/`：`nro-build.log`、`async-on` 冒烟产物（标题/读档/推进截图、`result.json`、`async_status.txt`、`debug_report-async-lines.txt`）、`SHA256SUMS.txt`。
- `docs/milestones/evidence/P20b-device-crash/`：真机 `crash_reports` 日志与 jpg + `README.md`（结论：hbloader/sphaira 崩溃与本项目无关）。
- `docs/milestones/evidence/P20c-rfvp-nsp108/`：NSP v1.0.8 首启冒烟（`nsp108-loaded.png`、`nsp108-adv4.png`、`result.json`、`citron-log-slice.txt`、`async_status.txt`、`SHA256SUMS.txt`）。
- `docs/milestones/evidence/P20d-device-mtp-upload/`：真机 MTP 上传 NSP v1.0.8 的复制对话框截图、轮询日志与 `ExtendedProperty('System.Size')` 校验结果（9,979,496,664 B）。
- 复现：构建见 §4.1；Citron async=on 见 §4.2（测前写 `async.txt`，测后删/改回 `off`）。

## 7. 限制与未验证

- **U1**：真机 async=on 黑屏的**直接机理仍未定位到具体一帧**。v1.0.8 的 `stage` 字段与其说是修复不如说是取证：下次真机测试若仍黑，`async_status.txt` 的 `stage=` 可直接指出卡在 read / decode / publish 哪一步。
- **U2**：看门狗只能救「worker 卡住且主线程仍能进帧」的情形；若主线程在 `submit_graph`/缓存 `spin::Mutex` 上自旋（当前推断），看门狗本身也进不去。因此 v1.0.8 仍**不默认开启** async。
- **U3**：`async.txt` 仍是临时开关（写 `on` 开），后续应替换为配置项。
- **U4**：Citron 无法复现黑屏，所有真机结论均为线上日志推断。
- **U5**：NSP v1.0.8 未签名，真机仍需 CFG + sigpatches。
- **U6**：MTP 只能逐文件复制且不可续传；9.98 GB 单文件约 10 分钟、本次未截断，但如中途断连需整体重传。DBI FTP 恢复后优先用 FTP（约 24 分钟但可断点续传语义更清晰、无桌面对话框）。

## 8. 变更记录

| 日期 | 内容 |
| --- | --- |
| 2026-11-01 | 首版：阶段诊断（stage）+ 3 s 看门狗 inline drain + 1 MiB 栈；NRO 构建；Citron async=on 冒烟 PASS（hb=77000、stage=0、30 条 async 日志）；真机 crash report 取证（hbloader/sphaira，无关） |
| 2026-11-01 | NSP v1.0.8（9,979,496,664 B `6af90729…`）构建 + verify 13 checks + Citron 首启冒烟 PASS（20/20 步、0 exception、`enabled=0`） |
| 2026-11-01 | NSP v1.0.8 经 MTP 上传真机 `/switch/galnx-nsp/`（约 10 min，`System.Size`=9,979,496,664 校验一致） |