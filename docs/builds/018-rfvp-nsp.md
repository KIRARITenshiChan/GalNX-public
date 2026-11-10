# 018 — rfvp 自包含 NSP（romfs 打包，P11）

- 编码：018
- 对象：xmoezzz/rfvp（Nintendo Switch target：platform/switch）
- 版本/commit：HEAD `9f07adef2eb5d559777f9bf59a67b756875cb24f`；toolchain pin nightly-2026-02-01 + devkitA64
- 许可证：MPL-2.0（rfvp 仓库 LICENSE；本记录涉及的两个文件均为其源码）
- 日期：2026-10-31
- 执行：Lead（P11 NSP 打包）
- 结论：**模拟器级 PASS**。9.2 GiB 游戏数据经 romfs 打进单个自包含 NSP（9,979,435,224 B），Citron 在 **SD 上没有任何游戏数据**的情况下从 romfs 启动、进入中文正文并干净退出；同一 ELF 的 NRO 形态回归不受影响。**真机未验证**（9.98 GB 必须 exFAT SD 或 NAND 安装）。
- 产物：`E:/galnx-build/p11/out/IROSEKA_FHD-010047420000a000.nsp` **9,979,435,224 B，SHA-256 `4592385c1c3e6b166172315a1c79c574b9241f6f8c57244b2e050e0292549189`**（产物不入库）
- 补丁：`docs/builds/patches/rfvp-switch/rfvp-romfs.patch`，2,430 B / 1 文件 +38/−1，SHA-256 `710a373e227d815eff9069bd55b33270cf8c503b7a20ce843717e8e2af37e489`（**增量补丁**：依次应用 016 的 `rfvp-sdl2-backend.patch`、017 的 `rfvp-input.patch`，再应用此补丁）；全量对照 `rfvp-full.diff` 57,536 B / 9 文件，SHA-256 `a6da02027d870b2f1453424742341b509f17a2ac54a997f78a8e6917fa4c71f4`
- 证据：`docs/milestones/evidence/P11-rfvp-nsp/`（10 张关键截图 + 两份 ODS 日志切片 + `nsp-verify.json` + `nsp-provenance.txt` + SHA256SUMS.txt）
- 清单：`examples/pilot02-iroseka.yaml`（P11 试点 manifest，title id `010047420000A000`）

## 1. 目标

P9/P10 已把 rfvp 跑成「Citron 上 60 fps + 手柄可玩」，但游戏数据仍放在 **SD 卡目录** `sdmc:/switch/rfvp/game`。真机安装要求只有一个可安装的 NSP；本记录把 ~9.2 GiB 游戏数据放进 **romfs**，让 NSP 自包含、插卡即玩，同时不破坏存档与 NRO 形态。

## 2. 方案：romfs 自包含 + 运行期游戏根选择

| 项 | 设计 |
| --- | --- |
| 数据位置 | romfs 内 `/game/`（161 个顶层游戏条目，9,932,275,140 B） |
| 运行期游戏根 | 有 romfs 且 `romfs:/game` 存在 `.hcb` 且 SD 侧 `sdmc:/switch/rfvp/game` 无 `.hcb` → 用 `romfs:/game`；否则维持 SD 路径 |
| 存档 | 不变，仍在 `sdmc:/switch/rfvp/saves/iroseka-2ae7dc8e/`（游戏根切换不影响存档路径，`fs.rs` 无需改动） |
| 配置/字体 | `config.toml`（`hcb = ".iroseka.hcb"`、`nls = "gbk"`）与 `default.ttf`（22,839,132 B，覆盖 CJK）都在 romfs 内，随 NSP 一起走 |
| NRO 形态 | 没有 romfs 时自动回落 SD 路径，行为与 P10 完全一致（回归见 §6.1） |

选择理由：

1. **单文件安装**：DBI/NAND 只认 NSP，散装 SD 目录在真机上要用户自己拷 9.2 GiB 文件，不可交付。
2. **romfs 是只读挂载**：游戏数据是纯读取资源，语义匹配；写操作（存档、debug.txt）继续走 SD。
3. **不侵入引擎资源层**：只改 `runtime/main.c` 一处决定游戏根，引擎按普通路径读取，避免在 Rust 侧改 fs 抽象。

## 3. 代码改动（`platform/switch/runtime/main.c`，+38/−1）

```c
static const char* const RomfsGameRoot = "romfs:/game";

static bool dir_has_game_script(const char* path) {
    DIR* dir = opendir(path);
    if (dir == NULL) return false;
    bool found = false;
    struct dirent* entry;
    while ((entry = readdir(dir)) != NULL) {
        const char* name = entry->d_name;
        size_t len = strlen(name);
        if (len > 4 && strcmp(name + len - 4, ".hcb") == 0) { found = true; break; }
    }
    closedir(dir);
    return found;
}

const bool romfs_mounted = R_SUCCEEDED(romfsInit());
const char* game_root = "sdmc:/switch/rfvp/game";
if (romfs_mounted && !dir_has_game_script(game_root) && dir_has_game_script(RomfsGameRoot))
    game_root = RomfsGameRoot;
log_text("rfvp: game root: ");
log_text(game_root);
log_text(romfs_mounted ? " (romfs mounted)" : " (no romfs)");
/* ... */
if (romfs_mounted) romfsExit();
```

要点：

- 用 **存在 `.hcb`** 判断「这里有游戏」，避免把空目录/半拷贝目录当成有效游戏根。
- 先检查 SD 再决定 romfs：开发迭代时 SD 目录优先，不用每次重打包 NSP。
- `romfsInit()` 失败不致命（NRO 形态本来就没有 romfs）。

## 4. 打包脚本 `scripts/build_nsp_game.sh`

通用脚本（不绑定 rfvp），流程与参数：

| 步骤 | 动作 |
| --- | --- |
| 1/6 | `elf2nso` → `exefs/main` |
| 2/6 | `npdmtool` 用模板 NPDM + `--title-id` → `exefs/main.npdm` |
| 3/6 | `nacptool` → `control/control.nacp` + `icon_AmericanEnglish.dat`（256×256 JPEG） |
| 4/6 | romfs 暂存：`--romfs-mode hardlink`（默认）对每个顶层条目建**硬链接**（跳过顶层 `save/`），实测 `hardlinked=161 copied=0`，不复制 9.2 GiB |
| 5/6 | `hacBrewPack --nologo -k <keyset>`（546 s） |
| 6/6 | `nstool -y` 结构检查 + 打印 `===ARTIFACTS / ===ROMFS / ===INPUTS` 摘要 |

脚本细节/坑：

- `USER` 可能未定义 → `${USER:-ACETaffy}`；
- Windows 版 python 不认 `/e/...` → 先 `cygpath -w` 再传；
- git-bash 里没有 `python` → 探测 `/d/Scoop/shims/python3.exe`；
- keyset 只显式传路径，脚本把 **size/sha256/mtime** 写进日志，不记录内容（`PROVENANCE keyset=...`）；
- 默认 TEMP 在 MSYS2 下不可用，脚本用 `--work` 显式工作目录。

## 5. 产物与 romfs 结构

| 项 | 值 |
| --- | --- |
| NSP | 9,979,435,224 B / SHA-256 `4592385c1c3e6b166172315a1c79c574b9241f6f8c57244b2e050e0292549189` |
| Title ID | `010047420000A000`（base 应用 id，0x2000 对齐） |
| 标题/作者/版本 | IROSEKA FHD / GalNX / 1.0.0；display mode handheld |
| exefs/main | 4,612,243 B / `915cdf7379ba784ad72a675837efb62ae829caab203e1b0341084fd3d028774b` |
| exefs/main.npdm | 972 B / `3cfb9877ba2b37018bbc66ec3c64c760c399ee80b4bc1bd6bee1d03b332ba565` |
| control.nacp | 16,384 B / `8e9bbbd1625360ccb9d76388b864212e07af380ce243965bc3399e3a5dddc470` |
| icon | 22,454 B / `10daef90e30d9bcc7f4e40294f0694fd75c1b4f0c53d52b016cbdc2e2b980b79`（P9 标题截图中心裁剪 256×256 q92；游戏美术版权不入库） |
| romfs | 9,932,275,140 B / 161 个顶层条目 |
| 引擎二进制 | NRO 7,839,800 B `9b5089f1…`；ELF 17,046,736 B `67f903d8…` |

romfs 顶层内容：`.iroseka.hcb` 4,369,357 B（中文脚本）、`iroseka.hcb` 4,275,282 B、`default.ttf` 22,839,132 B、`graph.bin`/`graph_bg.bin`/`graph_bs.bin`/`graph_vis.bin`/`graph_vis1.bin`/`graph_vis2.bin`、`bgm.bin`/`bgm2.bin`、`se.bin`、`movie/`、`config.toml`。

## 6. 双形态验证（Citron Nightly `0237a9b88`，Vulkan）

### 6.1 NRO 回归（romfs 改造不影响 SD 形态）

run `E:/galnx-build/m5-rfvp-run/p11-nro/20261031-053103-rfvp`：status=loaded、rc=0、EXCEPTION/panic 0。

| 时间 | 事件 | 证据 |
| --- | --- | --- |
| t=5.089 | `rfvp: game root: sdmc:/switch/rfvp/game (no romfs)` | nro-log-slice.txt |
| t=5.817 | `the game is loaded, running` | — |
| t=7.007 | `the first frame was drawn` | 10-nro-title.png `44f4f0ed…` |
| t=144.005 | `quit requested by host event` | 13-nro-quit.png `e84daad0…` |

### 6.2 NSP 冒烟 run1（SD 游戏数据改名后仅靠 romfs）

run `E:/galnx-build/m5-rfvp-run/p11-nsp/20261031-054128-IROSEKA_FHD-010047420000a000`：rc=0；窗口标题 `IROSEKA FHD (64-bit) | 1.0.0`；启动、退出正常，但等待不足未进正文（仅作冒烟）。

### 6.3 NSP 决定性 run2（P11 验收）

run `E:/galnx-build/m5-rfvp-run/p11-nsp2/20261031-054615-IROSEKA_FHD-010047420000a000`：**status=loaded、rc=0、EXCEPTION/panic 0**，`citron_log.txt` 85,647 B。

| 时间 | 事件 | 证据（SHA-256） |
| --- | --- | --- |
| t=4.60 | `Loading IROSEKA FHD (010047420000A000)` | — |
| t=5.81 | `Booting game: 010047420000A000 | IROSEKA FHD (64-bit) | 1.0.0` | 01-nsp-title.png `ed44151c…` |
| t=8.41 | `rfvp: game root: romfs:/game (romfs mounted)` | nsp-log-slice.txt |
| t=8.43 | `config.toml: GameConfig { hcb: Some(".iroseka.hcb"), nls: Some(GBK) }` | — |
| t=8.81 | `the game is loaded, running` | — |
| t=9.28 | `the first frame was drawn` | — |
| — | 方向键×10 移动光标 → New Game 高亮 | 02-nsp-hover.png `e2acc3fd…` |
| — | A 点击进入游戏淡入 | 03-nsp-fade.png `be8663a1…` |
| — | 正文首句（白场小字） | 04-nsp-story1.png `058b92fb…` |
| — | **中文正文「从天而降的羽毛。」+ 蓝天羽毛背景** | 05-nsp-story2.png `429af490…` |
| t=182.03 | `quit requested by host event` | 06-nsp-quit.png `e84daad0…` |

结论：NSP 在 **SD 上完全没有游戏数据**（`game` 改名 `game.sd-bak`）时仍能从 romfs 启动、加载 GBK 中文脚本、显示中文正文并干净退出 → **自包含成立**。

## 7. 独立结构校验（`galnx package nsp verify`）

```
ok = true
12 checks: 0 fail, 1 warn
NCAs: 3（Meta 0x1000 / Control 0x20c00 / Program 0x252cffc00）
all ProgID = 0x010047420000A000，与 manifest 期望一致
warn = NCA 签名 FAIL（未签名 homebrew 预期，hacBrewPack 的 RSA 键不是任天堂的）
```

完整输出：`docs/milestones/evidence/P11-rfvp-nsp/nsp-verify.json`（nstool 1.9.2，显式本地 prod.keys；只记 size/sha256，不记内容）。

## 8. 复现命令

```bash
# 1) 构建 romfs 版 NRO/ELF（wrapper 设 DEVKITPRO / CARGO_HOME）
"D:/Scoop/apps/git/current/bin/bash.exe" -lc 'bash /e/galnx-build/m5-switch-build3.sh'

# 2) 打包自包含 NSP（在 git-bash 中；keyset 仅本机离线显式传入）
bash "/e/Othergames/Nintendo Switch/Workspace/GalNX/scripts/build_nsp_game.sh" \
  --elf /e/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.elf \
  --game-dir /e/galnx-build/m5-rfvp-run/game \
  --title-id 010047420000a000 --name "IROSEKA FHD" --author GalNX --version 1.0.0 \
  --icon /e/galnx-build/p11/icon-256.jpg \
  --keyset "/e/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys" \
  --romfs-mode hardlink \
  --out /e/galnx-build/p11/out/IROSEKA_FHD-010047420000a000.nsp

# 3) 结构校验（cwd=GalNX）
PYTHONPATH=src /d/Scoop/shims/python3.exe -m galnx package nsp verify \
  --nsp "E:/galnx-build/p11/out/IROSEKA_FHD-010047420000a000.nsp" \
  --manifest examples/pilot02-iroseka.yaml \
  --nstool /e/galnx-build/m3-tools/nstool.exe \
  --keyset "E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys" --json
```

## 9. 限制与未验证

| 编号 | 项 | 说明 |
| --- | --- | --- |
| U1 | **真机安装/运行** | 未验证；NSP 9.98 GB，必须 exFAT SD 或足够 NAND（FAT32 单文件上限 4 GiB） |
| U2 | 上传耗时 | DBI FTP 实测约 6.4 MiB/s → 9.98 GB 约 25–30 分钟；需 CFW + sigpatches |
| U3 | 音频 | romfs 内 bgm/se 播放未做专项验证（仅到正文首段） |
| U4 | movie | `movie/` 下视频在 Switch 是否走引擎 videoplayer 未验证 |
| U5 | 内存余量 | 4 GB 机型上，romfs 大文件缓存 + 纹理峰值未测 |
| U6 | 首次读取耗时 | romfs 冷读 9.2 GiB 数据是否会拉长首次进正文（Citron 上 t=8.8 s 加载完成，真机 I/O 特性不同） |
| U7 | 组合键 | 沿用 017 的 PLUS+ZR/ZL 未在真机验证 |
| U8 | 多游戏 | 本脚本按「单游戏 romfs」设计；多游戏/切换需要另加启动器 |


**U2 更新（2026-10-31）**：真机 DBI FTP 上传已实测——9,979,435,224 B / 1,579.1 s ≈ **6.03 MiB/s（26.3 分钟）**，无中断，DBI 接收后回到投放占位目录；因此 U2 关闭，U1（安装后启动）仍待真机复验。证据：`docs/milestones/evidence/P11-rfvp-nsp/device-upload.txt`。
## 10. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-31 | 新建：rfvp romfs 自包含 NSP（P11）——main.c 运行期游戏根选择 + `build_nsp_game.sh` 打包脚本；NSP 9,979,435,224 B 双形态验证 PASS；`examples/pilot02-iroseka.yaml` 新增；补丁 `rfvp-romfs.patch` 入库 |
