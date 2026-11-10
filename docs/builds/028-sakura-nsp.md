# 028 · さくら、もゆ。720p 自包含 NSP（rfvp，Pilot-03）

> 日期：2026-11-05（Asia/Shanghai）
> 引擎：rfvp（FVP / Favorite View Point System），上游 pin `9f07adef2eb5d559777f9bf59a67b756875cb24f`（MPL-2.0）
> 目标：给「NS 硬件性能是否够 1080p」这个问题提供 **720p 对照实验**（用户 m25411），同时验证 rfvp 适配器对**第二款商业游戏**的通用性
> 结论：**PASS（Citron 级）** —— 自包含 NSP 7,990,691,032 B 可直接启动，标题/正文日文显示正确，稳定 **60 FPS**（60 帧窗口 slowest 17.4 ms，见 §4）；真机待复验

---

## 1. 背景与目标

用户 m25411 提出：IROSEKA（Pilot-02）是原生 **1080p**，卡顿可能来自 NS 性能不足，也可能来自资源规格；
用一款原生 **720p** 的 FVP 游戏做对照，即可把「硬件瓶颈」与「资源规格」分开。

选定 **「さくら、もゆ。-as the Night's, Reincarnation- HD Re:GENERATION」v0.2.0_0222_fix1**
（`E:/Othergames/Galgame/さくら、もゆ。v0.2.0_0222_fix1`），原因：

1. 同为 FVP 引擎、同用 `.hcb` 数据容器，**不改一行引擎代码**即可复用 rfvp 适配器；
2. 原生 1280×720 → 与 IROSEKA 1920×1080 形成可控对照；
3. 体量 7.5 GB、资源分档清晰（`graph.bin` / `graph_bg.bin` / `graph_vis.bin` 等），便于后续做资源压缩实验。

## 2. 内容组装与配置

游戏目录组装到 `E:/galnx-build/sakura-test/game`（总 ~7.5 GB），关键文件：

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `Sakura.hcb` | 5,002,569 | 脚本/表数据容器（SJIS 文本） |
| `graph.bin` / `graph_bg.bin` / `graph_bs.bin` / `graph_sd.bin` | 354,017,024 / 703,338,219 / 798,099,049 / 427,708,462 | 立绘 / 背景 / 事件 CG 等 |
| `graph_vis.bin` / `graph_vish.bin` | 2,008,972,031 / 1,116,635,151 | 视觉小说主体图像 |
| `bgm.bin` / `voice.bin` / `se*.bin` | 984,835,075 / 1,069,344,978 / 105,872,097 + 98,729,276 + 3,309,764 | 音频 |
| `movie/{01,02}.wmv` | — | 视频（本作 OP/ED；rfvp 的 wmv 播放未在本次验收覆盖） |
| `default.ttf` | 22,839,132 | 复用 IROSEKA 的日文字体 |
| `config.toml` | 86 B | `[game] hcb="Sakura.hcb" nls="sjis"` |

**编码关键**：`nls` 必须 **sjis**。实测 gbk 会输出乱码（`亏婁佈侃侷偲凵偵簾儔乗乗`），sjis 正常显示
`世界がそっと、ため息をつく――` / `胸に。`；`.hcb` 内文本为 Shift-JIS。

**汉化说明**：PC 中文版通过 `SakuraChs.exe + patch.bin` 运行时注入实现，Switch 不能复用；本 NSP **显示日文原版**。
若要中文，需要像 KiriKiri 试点那样另找可重打包的内容源或移植文本层（见 §7）。

## 3. 打包

| 项 | 值 |
| --- | --- |
| 清单 | `examples/pilot03-sakura.yaml`（schema_version 1，engine rfvp，`options: {nls: sjis}`） |
| TitleID | `010047420000C000`（base 0x2000 对齐，合规） |
| 版本 / 名称 | 1.0.0 / `SAKURA MOYU` |
| 图标 | `examples/pilot03/icon-256.jpg`（256×256，取自标题截图 logo + 夜樱背景） |
| ELF | 复用 IROSEKA v1.0.9 的 `rfvp.elf`（同一 rfvp 引擎 + P16/P17 性能补丁，**async 强制关**） |
| 打包命令 | `scripts/build_nsp_game.sh --game-dir E:/galnx-build/sakura-test/game --romfs-mode hardlink ...`（脚本 `E:/galnx-build/p21/build-sakura-nsp.sh`） |
| 产物 | `E:/galnx-build/p21/out/SAKURA_MOYU-010047420000c000.nsp` **7,990,691,032 B** sha256 `d2d4278372eb9a79d18d42932d0ad9722585bef9cfc48301abbc3000c72bd5cf` |
| 打包耗时 | hacBrewPack OK in **328 s**；romfs `hardlinked=17 copied=0` |

romfs 只有 17 个顶层条目（`.hcb` + 各 `.bin` + `movie/` + 字体），romfs 约 7.5 GB；9.98 GB 的 IROSEKA NSP 对照见 `docs/builds/027`。

### 3.1 结构校验

```
PYTHONPATH=src python -m galnx package nsp verify \
  --nsp /e/galnx-build/p21/out/SAKURA_MOYU-010047420000c000.nsp \
  --manifest examples/pilot03-sakura.yaml \
  --nstool /e/galnx-build/m3-tools/nstool.exe \
  --keyset 'E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys'
```

结果 **ok=true**，12 checks = **0 fail + 1 warn**（`verify.signature`：hacBrewPack 的 RSA 非任天堂密钥，未签名 homebrew 预期）。
PFS0 3 files；3 NCA = Program 0x1dc462800 / Control 0x20c00 / Meta 0x1000，ProgID 全为 `0x010047420000C000`。

## 4. Citron 首启冒烟（NSP 形态，romfs 直出）

方法与 IROSEKA v1.0.9 相同：把 `sdmc:/switch/rfvp/game` 移走，让 NSP 只可能从 **romfs** 取数据；
故意保留 `async.txt=on`（v1.0.9 必须忽略它），`debug.txt=shot=900` 开启帧心跳。

**结果**：`status=loaded`、窗口 `citron Nightly | 0237a9b88 | SAKURA MOYU (64-bit) | 1.0.0 | NVIDIA`、
boot_line `Booting game: 010047420000C000 | SAKURA MOYU (64-bit) | 1.0.0`；
11/11 input steps ok（3 次点击），0 异常。

| 检查点 | 证据（`docs/milestones/evidence/PERF-01b-sakura-nsp/`） | 结果 |
| --- | --- | --- |
| 标题画面 | `step-02-t1-title.png`（1,573,274 B，nonblack 0.9018） | 夜樱标题 + NEW GAME/CONTINUE/ALBUM/OPTION/EXIT |
| New Game → 序章 | `step-05-t2-after-newgame.png` | 月亮/樱花 + 演出（44 FPS 过渡帧） |
| 正文 1 | `step-08-t3-text1.png`（sha256 `c5b6b7f6…`） | 日文 `世界がそっと、ため息をつく――`，60 FPS |
| 正文 2 | `step-11-t4-text2.png`（sha256 `e0cdcc4f…`） | 日文 `胸に。`，FUNCTION 工具栏可呼出 |
| async 忽略 | `async_status.txt` | `enabled=0 create=0x0 start=0x0 hb=0 stage=0`（async.txt=on） |
| 帧心跳 | `frame_status.txt` | `frame=4905 status=0 async=0` |
| 稳态帧率 | `debug_report.txt` | `frame 4860: 60.0 fps over the last 60 frames, slowest frame 17.4 ms` |

**慢帧全表**（`perf_slow.log`，共 11 条，除启动/存读档外均一次性）：

| frame | 耗时 | 主要阶段 | 性质 |
| --- | --- | --- | --- |
| 1 | 1031.0 ms | vfs_read 397.01 / syscalls 131.20 / vm 147.69 / upload | 冷启动一次性 |
| 2 | 65.8 ms | save 50.49（save_finalize 32.25 + thumb 8.32） | 启动时自动存档一次性 |
| 4 | 198.0 ms | vfs_read 70.37 + graph_decode 75.11 + vm 165.15 | 首图加载一次性 |
| 16 | 35.1 ms | present 33.22 | 首帧呈现 |
| 310 | 118.3 ms | audio_cmds 114.74 | 音频初始化一次性 |
| 902 | 212.0 ms | present 0.31 / upload 0.00 | OP/过场切换一次性 |
| 2764 | 33.4 ms | vfs_read 30.37 | 单次资源读取 |
| 2954–2956 | 100.5 / 126.9 / 141.4 ms | vfs_read 45.98–35.66 + graph_decode 34.12–25.69 + cpu_restore 38.68/26.41 + audio 99.24 | 换场景一次性（3 帧连发） |

结论：**720p 在 Citron 侧稳定 60 FPS、无周期性慢帧**；11 条慢帧全部是「启动 / 首次加载 / 过场切换」这类一次性成本。
[ERROR] 80 条为资源 id 找不到等非致命告警（与 720p NRO 基线同类，见 `docs/experiments/perf-01-sakura-720p.md`），不影响画面。

## 5. 与 IROSEKA（1080p）的对照

| 维度 | IROSEKA_FHD（Pilot-02） | さくら、もゆ。（Pilot-03） |
| --- | --- | --- |
| 原生分辨率 | 1920×1080 | 1280×720 |
| 数据规模 | romfs 9.93 GB，NSP 9.98 GB | romfs ~7.5 GB，NSP 7.99 GB |
| 引擎/补丁 | rfvp + P9–P17，async off（v1.0.9） | 同一 `rfvp.elf`，无新增补丁 |
| Citron 稳态 | 60.0 FPS（P16/P17 后） | 60.0 FPS |
| 慢帧形态 | 逐句 save 已消除；余 CG/背景一次性解码 | 同类一次性慢帧，无周期性成本 |

**判断**：rfvp 在 Citron 上对 720p/1080p 都能跑满 60 FPS，说明瓶颈不在「NS 级别算力跑不动 1080p 视觉小说」；
真机上 IROSEKA 的残留卡顿应优先按「消除一次性长帧 / 真机 IO 与线程调度」处理，**资源压缩降为备选**
（判断依据见 `docs/experiments/perf-01-sakura-720p.md`）。真机复验仍需用户设备确认（§8）。

## 6. 文件与仓库位置

- 清单：`examples/pilot03-sakura.yaml`；图标：`examples/pilot03/icon-256.jpg`
- 构建脚本（工作区外）：`E:/galnx-build/p21/build-sakura-nsp.sh`、`E:/galnx-build/p21/run-sakura-nsp.sh`
- 证据：`docs/milestones/evidence/PERF-01b-sakura-nsp/`（4 截图 + window + result.json + run.log + input-steps.tsv + citron_log_slice + debug_report + perf_slow + frame/async_status + SHA256SUMS）
- 720p NRO 基线：`docs/experiments/perf-01-sakura-720p.md`、`docs/milestones/evidence/PERF-01-sakura-720p/`

## 7. 限制与未验证

- **无中文**：PC 汉化为运行时注入，rfvp 不加载；本构建显示日文原版。
- **视频未验收**：`movie/*.wmv` 的播放路径未单独验证（OP 是否播放、音画同步未记录）。
- **音频未主观验收**：仅从慢帧日志确认 `audio_cmds` 在跑；BGM/语音是否可闻未记录。
- **长流程 / 分支 / 鉴赏模式 / 存读档往返**未遍历。
- **真机未验证**：NSP 能否在 NS1 上安装启动、720p 实际帧率、慢帧是否与 Citron 同构，均待用户设备复验。

## 8. 复现步骤

```bash
# 1) 组装游戏目录（Sakura.hcb、*.bin、movie/、default.ttf、config.toml=nls:sjis）
# 2) 打包（与 IROSEKA 相同引擎 ELF）
bash /e/galnx-build/p21/build-sakura-nsp.sh
# 3) 校验
cd 'E:/Othergames/Nintendo Switch/Workspace/GalNX'
PYTHONPATH=src python -m galnx package nsp verify \
  --nsp /e/galnx-build/p21/out/SAKURA_MOYU-010047420000c000.nsp \
  --manifest examples/pilot03-sakura.yaml \
  --nstool /e/galnx-build/m3-tools/nstool.exe \
  --keyset 'E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys'
# 4) 模拟器冒烟（把 sdmc/switch/rfvp/game 移走，让 NSP 走 romfs）
bash /e/galnx-build/p21/run-sakura-nsp.sh
```
