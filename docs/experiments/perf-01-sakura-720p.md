# perf-01 · 720p FVP 基线：さくら、もゆ。在 Citron + rfvp（稳定 60 FPS）

> 日期：2026-11-05
> 目的：用一款**原生 720p** 的 FVP 作品作为性能对照，判断「iroseka 1080p 的卡顿」是否来自 NS/Citron 的持续渲染性能瓶颈，并为 iroseka 资源压缩决策提供依据（用户 m25411 假设）。
> 引擎：rfvp 上游 HEAD `9f07ade` + GalNX P11–P20 补丁（v1.0.8 NRO）
> 游戏：`E:/Othergames/Galgame/さくら、もゆ。v0.2.0_0222_fix1`（FVP，日文原版；汉化补丁 `patch.bin`/`SakuraChs.exe` 是 PC 运行时注入，rfvp 不加载）
> 证据：`docs/milestones/evidence/PERF-01-sakura-720p/`（含 notes.md、截图、debug_report、perf_slow、result.json、SHA256SUMS）

## 1. 结论（Citron 侧）

1. **720p 下 rfvp 渲染管线稳定 60.0 FPS**：6000 帧窗口 `slowest frame 18.0 ms`，`render 15.55 ms / present 15.15 ms / draws 15`，CPU VM 仅 `0.55–0.66 ms`。说明 Switch 级 GPU/带宽在 720p 下跑这类 2D ADV 有充足余量，**持续性能不是瓶颈**。
2. **真机可感知的卡顿来自一次性长帧**（资源解码 / 存档 / 音频初始化 / 启动装载），与本作同型的尖峰在 iroseka 上也已定位并部分修复（P16–P18）。这类长帧与分辨率无强相关——720p 本作同样出现 106–228 ms 的单帧。
3. 因此 **iroseka 资源压缩不是解决「卡顿」的必要手段**；若做压缩，收益主要在下载体积、显存占用与解码时间，优先级低于继续消除一次性长帧（尤其真机侧解码/IO）。是否压缩应另按「存储/内存/加载时间」目标决策，而不是按掉帧。
4. 本结论建立在 Citron 上；真机 720p 复测后才能作为最终判断（见 `8）。

## 2. 环境与游戏组装

| 项 | 值 |
| --- | --- |
| 源目录 | `E:/Othergames/Galgame/さくら、もゆ。v0.2.0_0222_fix1`（FVP 资源：`Sakura.hcb` 5,002,569 B + 12 个 `*.bin` + `movie/01.wmv`、`02.wmv` + `default.ttf`） |
| 运行副本 | `E:/galnx-build/sakura-test/game`（约 7.5 GB，同卷 NTFS hardlink） |
| 关键资源 | bgm.bin 984,835,075；graph.bin 354,017,024；graph_bg.bin 703,338,219；graph_bs.bin 798,099,049；graph_sd.bin 427,708,462；graph_vis.bin 2,008,972,031；graph_vish.bin 1,116,635,151；voice.bin 1,069,344,978；se.bin 105,872,097；se_env.bin 98,729,276；se_sys.bin 3,309,764；patch.bin 29,961,828；default.ttf 22,839,132（复用 iroseka 字体，非本作自带） |
| `config.toml`（86 B） | `[game]` / `hcb = "Sakura.hcb"` / `nls = "sjis"` |
| NRO | `E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro` 7,929,912 B（v1.0.8，P11–P20） |

**陷阱：Citron 实际读取的是** `C:/Users/ACETaffy/AppData/Roaming/citron/sdmc/switch/rfvp/game`，该路径当前是一份 **7.5 GB 真实拷贝**（此前用 git-bash `ln -s` 时 MSYS 退化成复制，无 reparse point）。**改 `config.toml` 必须改 sdmc 里那份**，改 `E:/galnx-build/sakura-test/game` 不影响运行。两处现均为 `nls="sjis"`。

## 3. 启动与输入注入

```bash
cd '/e/Othergames/Nintendo Switch/Workspace/GalNX'
bash scripts/citron_run.sh --game E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro \
  --detach --timeout 240 --settle 8 --allow-existing \
  --out /e/galnx-build/sakura-test/runs \
  --input-steps 'wait:18000;capture:00-title;click:1451,250;wait:8000;capture:01-after-newgame;
                 click:864,600;wait:7000;capture:02-text1;click:864,600;wait:7000;capture:03-text2;
                 wait:12000;capture:04-baseline'
```

输入注入结论（对后续所有 Citron 实验有效）：

- `click:X,Y`（窗口相对坐标；harness 先 `BringWindowToTop/SetForegroundWindow`，`focus_ok=1`）→ **有效**；
- `pclick:X,Y`（PostMessage 到最大子窗口，Qt 用 `QCursor::pos()`）→ 无效；
- `key:C`（PostMessage `WM_KEYDOWN`）→ 无效（Citron `qt-config.ini` 里 `keyboard_enabled=false`）。

## 4. nls 编码实验（三次 run）

| run | run_dir | nls | 结果 |
| --- | --- | --- | --- |
| run1 | `.../runs/20261105-055607-rfvp` | gbk | 标题画面正常；但只用 pclick/key，输入无效，停在标题 |
| run2 | `.../runs/20261105-060029-rfvp` | gbk | 前台 click 生效进入正篇；**文字乱码** |
| run3 | `.../runs/20261105-060457-rfvp` | **sjis** | 进入正篇；**日文正确** ✅（最终基线） |

- gbk 乱码样例：第一句 `亏婁佈侃侷偲凵偵簾儔乗乗`、第二句 `亏婽偵Т` —— 典型「SJIS 字节被 GBK 解码」。
- sjis 正确样例：`世界がそっと、ため息をつく――`、`胸に。`。
- 结论：**`Sakura.hcb` 文本编码 = Shift-JIS，`config.toml` 必须 `nls="sjis"`（也是引擎默认值）。** 无需试 utf8。
- 游戏内自动存档目录：`saves/sakura-aad96959/save/`（`rfvp_global.bin` 264,026；`rfvp_s901.bin` 450,060；`rfvp_s906.bin` 454,865）。

## 5. fps 与帧时间基线（run3）

`debug_report.txt` 头行（原文）：

```
frame 6000: 60.0 fps over the last 60 frames, slowest frame 18.0 ms
stages (ms per frame): tree 0.05 submit 0.22 end_frame 15.15 vm 0.55 syscalls 0.14
virtual frame 1280x720
perf avg over 60 ticks: vm 0.55 ms, scene 0.02 ms, render 15.55 ms, total 16.12 ms
host avg over 60 frames: begin 0.04 ms, upload 0.00 ms (0 calls), present 15.15 ms, thumb 0.00 ms (0 calls), draws 15.0, flushes 15.0
```

- `frame_status.txt` = `frame=6045 status=0 async=0`；`async_status.txt` = `enabled=0 create=0x0 start=0x0 hb=0 stage=0`（未启用 async）。
- run2 对照：`frame 6120: 60.0 fps, slowest 19.0 ms`；vm 0.66 / render 15.34 / total 16.03。run1（标题）：`frame 7200, slowest 17.3 ms`；render 15.97。
- Citron 状态栏实测：正篇稳定 `60 FPS / Frame 16.65–16.68 ms`；切场景瞬间出现过单帧 `45 FPS / 27.51 ms`，非持续掉帧。
- 解读：`present 15.15 ms` 是 vsync 等待（60 Hz 上限），GPU 实际工作在 wait 内完成；余量体现在 `slowest frame` 只有 18 ms。

## 6. 慢帧：全部为一次性事件

run3 `perf_slow.log`（9 行）摘要：

| 帧 | 总时长 | 主要阶段 |
| --- | --- | --- |
| 1 | 1,177.0 ms | 启动装载（submit 74 / vm 203） |
| 2 | 155.5 ms | save 140.08（save_snapshot 18.91 / save_finalize 37.84） |
| 4 | 228.2 ms | vm 194.88 / syscalls 190.51 / vfs_read 93.09 / graph_decode 81.06 |
| 12 | 33.4 ms | end_frame 32.68 |
| 309 | 106.1 ms | audio_cmds 102.67 |
| 2657 | 40.8 ms | vm 37.75 / vfs_read 36.80 |
| 2847 | 111.7 ms | vm 93.63 / vfs_read 54.64 / graph_decode 37.22 |
| 2848 | 124.5 ms | vm 100.29 / cpu_restore 36.13 |
| 2849 | 143.0 ms | render 110.12 / audio_cmds 103.46 / cpu_restore 25.11 |

run2 独立复跑出现同型帧（2682 33.6 ms、2873 134.2 ms、2874 115.7 ms）→ 这些长帧是**确定性的资产预取/音频初始化开销**，不是随机卡顿，也不是渲染性能不足。

## 7. 错误摘要

run3 `debug_report.txt` 共 80 条 `[ERROR]`，全部非致命：25×`Invalid id`、24×`graph_load: invalid id : Nil`、24×`Invalid alpha motion id`、2×`snow: arg10 should be in range 1..1024`、2×`history_set: unexpected value for set_voice : Nil`、2×`history_set: unexpected value for set_name : Nil`、1×`id must be in range 0..256`。无 `last_error.txt`、无 Citron 崩溃，画面/流程正常。

另有大量 `[INFO] ... [cache] prefetch skip path="graph/dissXX": Unexpected texture type: Single8Bit`（dissolve 贴图不进预取缓存），非错误。

## 8. 与 iroseka（1080p）的对比与压缩判断

| 指标 | さくら、もゆ（720p） | iroseka（1080p，历史数据） |
| --- | --- | --- |
| virtual frame | 1280x720 | 1920x1080 |
| 稳态 fps | 60.0（slowest 18.0 ms） | 修复后 60.0（P9 起） |
| render/present | 15.55 / 15.15 ms | 同量级（vsync 上限内） |
| CPU VM | 0.55–0.66 ms | 0.2–0.6 ms 量级 |
| 卡顿来源 | 启动装载、存档、音频初始化、资产预取（一次性） | 同型 + 大图解码更贵（P16–P18 已优化） |

判断：

1. **720p 对照证明「渲染管线」不是卡顿源**；iroseka 1080p 的同等结论已被 P9（17→60 FPS）与后续性能补丁验证，因此无需用降分辨率/压缩资源去换帧率。
2. iroseka 的关键长帧是**大图解码**（2400×1350 背景 130–160 ms、角色 sheet 84–113 ms）与**存档编码**（10.2 MB postcard ~100 ms，P16 已消除），这些是**字节量/像素量**问题，不是分辨率渲染问题。压缩贴图（降分辨率、换格式）确实能线性缩短解码，但代价是画质；收益与 P16–P18 已取得的修复重叠，**当前不是优先级**。
3. 若后续仍要做资源优化，优先级建议：①启动装载/预读预算（减少首屏等待）→ ②大图解码异步化在真机的可行性（先修 async 锁模型，见 `docs/experiments/rfvp-async-hang-rca.md`）→ ③才对 iroseka 的大图做有损压缩。
4. 最终判断需真机 720p 复测：Citron 的 present 15 ms 是宿主 vsync 假象之一，真机 GPU 余量需实测（本作真机尚未部署）。

## 9. 未覆盖 / 风险

- `movie/*.wmv` 播放（本次只到开场几分钟）、音频实际输出（无录音校验）、长时稳定性（>10 分钟）、存档/读档往返；
- 未测 async 解码（`async.txt` 未启用）；未测 utf8（sjis 已正确，无必要）；
- sdmc 内 7.5 GB 为真实拷贝（C: 盘 +7.5 GB）；删除会破坏 Citron 可复现运行，重建需再复制或用真正的 junction。

## 10. 证据清单（已入库子集）

| 文件 | SHA-256 |
| --- | --- |
| `step-02-00-title.png`（标题） | `bb0e1d8d64d5f3e00912c74868b8160f0bac02f5cd1c2ad61c171eb524a62770` |
| `step-08-02-text1.png`（日文正文 1） | `56d2b9f2147365dba8e37c4a76b18dec7cbbfc72787dde72697ff1f49c130636` |
| `step-11-03-text2.png`（日文正文 2） | `9cde2aba193e74dc6a8e3b30761a73967677b06dbab0aaa5080a7d41ec8a6ae1` |
| `debug_report.txt` | `45399e665dd836900458b20463a3345a30c048ad1c2b2fe463182a886b5ec8d8` |
| `perf_slow.log` | `a41b4d6beca82de00ba854349736a76336399ef925ea87b10c4cf9b3b605bf29` |
| `result.json` | `c381aa7b53eb073e7ed31e44ea0daf566d01947595328d0b14af64f53f765172` |
| `notes.md`（原始完整记录，含 run1/run2 与取证清单） | `d6937ff0dfdecf3d593859a628b423f35006179f4213c35b2cb9d48087641df1` |

完整证据（run1-gbk / run2-gbk / run3-sjis / prev-m5-ref，约 40 MB）保留在 `E:/galnx-build/sakura-test/evidence/`（构建机产物，不入库）。