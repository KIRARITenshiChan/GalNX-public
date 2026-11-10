# 031 · さくら、もゆ。中文剧情自包含 NSP（Pilot-03 CN）

- 日期：2026-11-05
- 作者：GalNX（Lead）
- 引擎：rfvp（MPL-2.0）+ devkitA64，Switch 后端 P9–P21 补丁栈
- 产物：`E:/galnx-build/p23/out/SAKURA_MOYU_CN-010047420000c200.nsp`
- 结论：**中文剧情在 NSP（自包含 romfs）形态下首启可读、可推进、60 FPS，Citron 冒烟 PASS**；UI 图片仍为日文（二期）。

---

## 1. 背景与目标

用户（m26018）明确要求解决《さくら、もゆ。HD Re:GENERATION》的语言障碍，无日语背景。Pilot-03 日文版 NSP 已交付（`docs/builds/028-sakura-nsp.md`），本构建在其基础上替换剧情脚本为 PC 汉化组译文的 GBK 版本，产出独立 TitleID 的中文 NSP，与日文版并存。

验收标准（本阶段）：
1. NSP 首启进入标题，点击 New Game 能进正文；
2. 正文/旁白为**中文**，字体、标点、换行正常；
3. 连续翻页不崩溃，帧率 60 FPS（Citron）；
4. 不改 m5-rfvp 引擎源码（复用 v1.0.9 ELF）。

不含：UI 图片（标题 logo、菜单按钮、存档界面贴图）汉化；真机验收（待 MTP 安装后由用户/Lead 执行）。

---

## 2. 中文内容来源与生成方式

由 teammate `sakura-l10n`（task-50）完成，完整报告见 `docs/experiments/l10n-02-sakura.md`。

- 译文来源：PC 汉化补丁 `patch.dat`，57,172 条 key = `Sakura.hcb` 内文本字节偏移，**57,172/57,172 全部命中**。
- 生成方式：**字节码级原位重打包**（非反编译重编译）。工具 `E:/galnx-build/p23/l10n/hcb_tool.py` 解码原 hcb 的指令流，只替换 `push_string` 载荷，按指令边界重算绝对地址并重新编码。
- 正确性锚点：原版 decode→encode 输出**字节完全一致**（5,002,569 B，`identical=True`），证明未破坏脚本结构。
- 关键坑：`ThreadStart`（syscall id=136）前一条 `push_i32/i16` 是函数入口**绝对代码指针**，字符串变长后地址平移，必须重定位（官方 assembler phase2b 规则；本 hcb 99/99 站点命中）。漏改即 `[ERROR] Error while executing the script: "no top of the stack"`（`crates/rfvp/src/script/context.rs:220-249`）崩溃。
- 产物：`SakuraGBK.hcb` 4,283,683 B，sha256 `4d4fd72933c2342841765b27d3be0522dff8ea055ba6f510d5b0fe25f248e7d7`。
- 字体：沿用日语版 `default.ttf`（22,839,132 B），CJK 覆盖完整，无需替换。
- 编码链：`config.toml` 设 `nls = "gbk"`，rfvp Switch 端将 `sdmc:/switch/rfvp/nls.txt`/config.toml 的 nls 映射到文本解码器；日志实证 `GameConfig { hcb: Some("SakuraGBK.hcb"), nls: Some(GBK) }`。

引擎侧不改代码：rfvp 官方 ADR 0008 明确只支持离线重打包，不做运行期文本热替换，本方案与之一致。

---

## 3. 内容组装与打包

### 3.1 romfs 内容（`E:/galnx-build/p23/cn-game`，7.5 GB / 17 条）

从日文版内容 `E:/galnx-build/sakura-test/game` 以 hardlink（`cp -al`）复用，避免二次占盘：

| 操作 | 文件 |
|---|---|
| 替换 | `Sakura.hcb` → `SakuraGBK.hcb`（4,283,683 B） |
| 改写 | `config.toml` → `[game]\nhcb = "SakuraGBK.hcb"\nnls = "gbk"` |
| 删除 | `save/`（空目录，避免带入宿主存档） |
| 原样保留 | `bgm.bin`/`graph*.bin` 9 个/`voice.bin`/`se*.bin`/`patch.bin`/`movie/`/`default.ttf` |

### 3.2 打包

脚本 `E:/galnx-build/p23/build-sakura-cn-nsp.sh`，日志 `/e/galnx-build/p23/cn-nsp-build.log`：

```
scripts/build_nsp_game.sh \
  --elf /e/galnx-build/m5-rfvp/target/rfvp-switch-runtime/rfvp.elf \
  --game-dir /e/galnx-build/p23/cn-game \
  --title-id 010047420000c200 --name "SAKURA MOYU CN" --author GalNX --version 1.0.1 \
  --icon examples/pilot03/icon-256.jpg \
  --keyset '<Ryujinx portable>/system/prod.keys' \
  --hacbrewpack <hacBrewPack> --nstool <nstool> \
  --romfs-mode hardlink \
  --out /e/galnx-build/p23/out --work /e/galnx-build/p23/cn-work
```

- TitleID 规则：base `010047420000C200`（0x2000 对齐），与日文版 `010047420000C000` 并存，不冲突。
- 复用 v1.0.9 ELF（17,258,040 B sha256 `e06b165228e6b6ce7aee08f8c020cb80b5faa161b4236235de06ec6c609af6ff`），本构建**不含引擎改动**。
- 构建结果：hacBrewPack OK in 274 s，nstool structure exit=0。

### 3.3 产物

| 项 | 值 |
|---|---|
| NSP | `SAKURA_MOYU_CN-010047420000c200.nsp` |
| 大小 | **7,989,970,136 B** |
| sha256 | `91ad7b96d3362160d1af2fdbf5e83d6888a661c7197d1cac1045b18aa14d490e` |
| 清单 | `examples/pilot03-sakura-cn.yaml` |
| NCA | 3 个（Program / Control / Meta），ProgID 全 `0x010047420000C200` |

---

## 4. 打包校验（galnx package nsp verify）

```
cd Workspace/GalNX
PYTHONPATH=src python -m galnx package nsp verify \
  --nsp /e/galnx-build/p23/out/SAKURA_MOYU_CN-010047420000c200.nsp \
  --manifest examples/pilot03-sakura-cn.yaml \
  --nstool /e/galnx-build/m3-tools/nstool.exe \
  --keyset '<prod.keys>' --json
```

结果：**ok=true，12 checks = 0 fail + 1 warn**（`verify.signature` 未签名，homebrew 预期）；PFS0 3 files。

---

## 5. Citron 首启冒烟（PASS）

- 脚本 `E:/galnx-build/p23/run-cn-nsp.sh`；先把 `sdmc:/switch/rfvp/game` 移为 `game-sakura-hold`，确保 NSP 走内嵌 romfs；故意保留 `async.txt=on`、`debug.txt shot=600`；`--no-stage` 直接加载 NSP。
- 输入脚本：`wait:22000 → capture:t1-title → click:1451,250(New Game) → wait:9000 → capture:t2 → click:864,600 → wait:7000 → capture:t3-text1 → click → wait:7000 → capture:t4-text2`。
- run_dir：`E:/galnx-build/p23/run-cn-nsp/20261105-161851-SAKURA_MOYU_CN-010047420000c200`

| 项 | 结果 |
|---|---|
| status | `loaded` |
| window_title | `citron Nightly | 0237a9b88 | SAKURA MOYU CN (64-bit) | 1.0.1 | NVIDIA` |
| boot_line | `Booting game: 010047420000C200 | SAKURA MOYU CN (64-bit) | 1.0.1` |
| 输入步骤 | 11/11 ok，0 failed |
| 帧率 | 60 FPS（截图状态栏 `Game: 60 FPS`） |
| async | `async_status.txt` = `enabled=0 create=0x0 start=0x0 hb=0 stage=0`（v1.0.9 强制关闭，async.txt=on 被忽略） |
| 帧心跳 | `frame_status.txt` = `frame=5070 status=0 async=0` |

画面证据（本仓库 `docs/milestones/evidence/P22a-sakura-cn-nsp/`）：
- `step-02-t1-title.png`：中文 NSP 标题画面（标题 logo 仍日文，UI 二期）；
- `step-08-t3-text1.png`：正文中文「世界于此，暂作叹息——」；
- `step-11-t4-text2.png`：正文中文「于我胸中回响。」；
- `result.json` / `run.log` / `input-steps.tsv` / `citron_log_slice.txt` / `window-steps-final.png`。

日志锚点（`citron_log.txt`）：
- `:334` `rfvp [info] config.toml: GameConfig { hcb: Some("SakuraGBK.hcb"), nls: Some(GBK) }`
- `:338` `rfvp [info] rfvp no_std boot: parsed real HCB, initialized real GameData, and started VmRunner`
- `:342` `rfvp: the game is loaded, running`

无 `last_error`、无 watchdog、无异常退出。

---

## 6. 已知限制

1. **UI 图片仍日文**：标题 logo、菜单按钮（New Game/Continue/Album/Option/Exit）、存档界面贴图均来自 pack 资源，PC 汉化把它们放在 `patch.bin`，rfvp 不加载 patch.bin（`crates/rfvp/src/subsystem/resources/vfs.rs` 无 patch 特判）。二期方案见 `docs/experiments/l10n-02-sakura.md` §4.4：patch.bin 是标准 FVP pack（69 条 hzc1 贴图），68/69 与 graph/graph_vis 同名，可用 loose 文件覆盖 60 条（v1，约 0.5–1 天），8 条 ≥1 MiB 大图需重建 pack（v1.5）。
2. **未真机验证**：本轮仅 Citron；真机需确认 1080p 下中文排版不溢出（PC 汉化统计宽度 p95 +1，风险中低）、存档界面字形、以及 MTP 安装。
3. **译文许可**：PC 汉化译文为 CC-BY-NC-SA 4.0（禁商用/直播），本 NSP 仅个人使用，不公开分发。
4. **3 条 ruby 标记数据瑕疵**（PC 补丁自身，低风险）；3,993 条未翻译串为内部/调试/资源名，无可见日文台词残留。
5. **潜在坑**：ThreadStart 类指针漏改（换 hcb/补丁版本必须重跑 l10n 的 stats 校验）；中文宽度导致个别行溢出（需真机确认）。

---

## 7. 复现

```bash
# 1) 生成 SakuraGBK.hcb（需 PC 汉化补丁 patch.dat；详见 docs/experiments/l10n-02-sakura.md）
bash E:/galnx-build/p23/l10n/make_sakura_gbk.sh

# 2) 组装 romfs（hardlink 复用以省盘）
cp -al /e/galnx-build/sakura-test/game /e/galnx-build/p23/cn-game
rm /e/galnx-build/p23/cn-game/Sakura.hcb
cp E:/galnx-build/p23/l10n/out/SakuraGBK.hcb /e/galnx-build/p23/cn-game/
printf '[game]\nhcb = "SakuraGBK.hcb"\nnls = "gbk"\n' > /e/galnx-build/p23/cn-game/config.toml
rm -rf /e/galnx-build/p23/cn-game/save

# 3) 打包（参数见 §3.2）
bash /e/galnx-build/p23/build-sakura-cn-nsp.sh

# 4) 校验 + Citron 冒烟
bash /e/galnx-build/p23/run-cn-nsp.sh
```

---

## 8. 教训

1. **字符串变长必须重定位绝对代码指针**：KiriKiri hcb 里 `ThreadStart` 前面的 push 是函数 PC；只改 push_string 而不做 phase2b 重定位，线程会从错误 PC 起跑，报错信息（`no top of the stack`）与真实原因相距很远。
2. **先证「无改动往返一致」再改内容**：原版 decode→encode 字节一致是判断工具正确性的最强锚点，比人工抽查可靠。
3. **NSP 冒烟必须把 sdmc 的 game 目录移走**：否则 rfvp 会优先读 sdmc 松散目录，测到的不是 NSP 内嵌 romfs 内容（本构建冒烟即为此专门改名 game-sakura-hold）。
4. **Citron 单实例纪律**：多实例会 attach 错窗口（task-50 run-06 事故），跑冒烟前先确认 0 个 citron 进程。
5. **UI 图片与剧情文本是两条链路**：剧情文本在 hcb（可离线重打包），UI 在 pack 贴图（loose 覆盖或重建 pack），二期须分开立项。

---

## 9. v1.0.2：UI 图片汉化（loose 覆盖，2026-11-05 追加）

在 §1–§8（v1.0.1，剧情中文化）基础上，把 PC 汉化补丁 `patch.bin` 中的 UI 贴图以 **loose 文件覆盖**方式补进 romfs，title_id 不变（`010047420000C200`）、版本升为 1.0.2。

### 9.1 贴图来源与导出

由 teammate `sakura-l10n`（task-52）完成，产物 `E:/galnx-build/p23/l10n/ui-loose/`：

- `patch.bin`（29,961,828 B，sha256 `da0a7e11…`）解析为 69 条 `hzc1` 贴图；与 graph/graph_vis pack 同名匹配 68 条。
- 导出 **60 条**（graph/ 56 + graph_vis/ 4，合计 14,358,332 B），保持 hzc1 原始字节；台账 `mapping.json`（含 pack_offset、NVSG 元数据、meta_diffs、sha256）；`SHA256SUMS` 60/60 校验通过。
- 8 条 `≥1 MiB` 大图（a_cg_s1、graph_vis/ETC_e000b/e001a/e012b/e012c/e012d/e302a/e302b）走 async pack 路径，留 v1.5 处理；18 条为 PC 美工重绘、尺寸与原 pack 不同（引擎按 NVSG 自适应，冒烟无错位）。
- 文档：`docs/experiments/l10n-02-sakura.md` §4.4。

### 9.2 组装与打包

- 把 `ui-loose/graph`、`ui-loose/graph_vis` 复制进 `/e/galnx-build/p23/cn-game/`（romfs 由 17 条变 77 条，仍 7.5 GB）。
- 脚本 `E:/galnx-build/p23/build-sakura-cn-nsp-v2.sh`（与 v1 相同，仅 `--version 1.0.2`、`--out /e/galnx-build/p23/out-v2`、`--work /e/galnx-build/p23/cn-work-v2`）；日志 `E:/galnx-build/p23/cn-nsp-build-v2.log`；hacBrewPack OK。

| 项 | 值 |
|---|---|
| NSP | `SAKURA_MOYU_CN-010047420000c200.nsp`（v1.0.2） |
| 大小 | **8,004,355,288 B** |
| sha256 | `5708da95640b91928829a746c36a73571025c1db5ec83a8e4ce47bc9e64bad8b` |
| verify | ok=true，12 checks = 0 fail + 1 warn（未签名预期），3 NCA ProgID 全 `0x010047420000C200` |

### 9.3 Citron 冒烟（PASS）

- 脚本 `E:/galnx-build/p23/run-cn-nsp-v2.sh`（同 v1 流程：移走 sdmc game → `async.txt=on` 被忽略 → `--no-stage` 直接加载 NSP），run_dir `E:/galnx-build/p23/run-cn-nsp-v2/20261105-164111-SAKURA_MOYU_CN-010047420000c200`，11/11 步 ok、60 FPS、`frame_status frame=5130 status=0 async=0`、0 exception。
- **画面实证**：标题 logo 已变为中文（「樱花萌放」风格字标），正文中文正常（「世界于此，暂作叹息——」「于我胸中回响。」），无贴图错位、无黑块。
- 仍为日文的部分：标题右侧菜单按钮（NEW GAME/CONTINUE/ALBUM/OPTION/EXIT 及其下方日文 ruby）——PC 补丁未替换该组贴图，属译文/资产缺口，不影响剧情阅读。
- 证据：`docs/milestones/evidence/P22b-sakura-cn-nsp-v2/`（4 截图 + result.json + run.log + input-steps.tsv + citron_log_slice.txt + cn-v2-smoke.log + cn-nsp-build-v2.log + SHA256SUMS）。

### 9.4 结论

剧情 100% 中文 + 标题 logo 中文，UI 菜单按钮仍日文；v1.0.2 为当前**推荐真机试玩版本**（与日文版 1.0.0、剧情中文版 1.0.1 同 title_id 覆盖升级）。
