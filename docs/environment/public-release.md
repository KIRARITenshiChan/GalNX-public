# 公开仓库前的素材隔离与 fail-closed 安全检查

> 状态：生效中（v1.44 起为 fail-closed 自动扫描；v1.40 引入素材隔离）。相关：[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)、[LICENSE](../../LICENSE)、[docs/builds/patches/LICENSE.md](../builds/patches/LICENSE.md)。
>
> 本文由 TASK-PUBLIC（0.1 Preview 收敛）更新：脚本不再只是「按前缀排除图片」，而是生成树 + ZIP 双重扫描闸门，任何 BLOCK 命中都非零退出并拒绝发布。

## 1. 为什么需要隔离

GalNX 仓库同时承担「框架代码」和「实验记录」两个角色。按当前基线，`git ls-files` 跟踪 1,377 个文件，其中：

- **游戏素材** 357 个（350 png + 6 jpg + 1 bmp），约 367 MB：
  - `docs/milestones/`：Citron / 真机截图，含商业游戏的标题画面、立绘、CG、OP 帧；
  - `docs/assets/`：4 张作品封面（pilot01–04）；
  - `examples/pilot0*/`：NSP 图标；
- **原始游戏数据** 2 个：`docs/milestones/evidence/P37-nvdec-probe5/probe5-mpeg2.nv12`（解码后的视频帧）与 `docs/milestones/evidence/M4c-build-20261030/content/arc.nsa`（空占位归档）。

这些游戏画面的版权属于各发行商/开发方（FAVORITE 等），**不在 MIT 许可范围内**，也不能随仓库公开。
从工作树删掉并不能保护它们，**私有历史里仍然存在**。所以公开流程是「先导出干净树，再以干净树发布」，不是「删文件后直接 push」。

## 2. 判定规则

脚本 `scripts/public_release_sanitize.py` 分两层：**导出策略**（决定哪些文件不进公开树）与 **扫描闸门**（决定公开树/ZIP 是否可发布）。改规则必须同步改测试 `tests/test_public_release.py`。

### 2.1 导出策略：素材排除

| 类别 | 判定 | 处理 |
| --- | --- | --- |
| 游戏图片 | 后缀为 `.png/.jpg/.jpeg/.webp/.gif/.bmp`，且路径以 `docs/milestones/`、`docs/assets/`、`examples/pilot` 开头 | 排除（kind=`art`） |
| 原始游戏数据 | 任意位置后缀为 `.nv12/.nsa` | 排除（kind=`data`） |
| 其它文件（代码、清单、日志、哈希清单、文本证据、补丁） | — | 保留 |

白名单均为「带理由」的结构（`{"path": ..., "reason": ...}`，也接受纯路径字符串并为旧条目补默认理由）：

- `IMAGE_ALLOWLIST` 默认空：非游戏图片必须显式加入并写明理由，否则一律按游戏素材处理；
- `FILE_ALLOWLIST` 默认只有 1 条：`examples/batch/games/demo-a/data.xp3`（62 字节 UTF-8 占位 fixture，不以 XP3 magic 开头、不含游戏数据，属于 batch demo 测试夹具）。扩展名虽然高危，但按内容与用途允许保留。

Markdown 引用处理：生成时若发现指向被排除素材的 `![]()` 或 `[]()` 引用，图片改写为占位符 `*[game art removed from public tree]*`，普通链接保留标签文本；**围栏代码块**（`~~~` 与 ``` 两种）内的路径保持原样，因为它们记录的是构建命令。排除清单写入输出树的 `PUBLIC_RELEASE_ART_EXCLUSIONS.txt`。

### 2.2 扫描闸门：高危扩展名 / 文件名（BLOCK）

以下后缀出现在待发布文件中即 BLOCK：

```text
.nsp .xci .nca .nro .nso .npdm .kip .kipx .nsz .ncz .xcz .tik .cert
.xp3 .xmoe .hcb .wmv .mp4 .mkv .ogg .mp3 .wav .flac .ttf .otf
.bin .iso .img .rom .sav .dll .exe .msi .dmg .so .dylib .nsa .nv12
.zip .7z .rar .tar .gz .xz .keys
```

文件名命中 `prod.keys`、`title.keys`、`console.keys`、`keys.txt` 同样 BLOCK。
命中 `FILE_ALLOWLIST` 的条目记为 `allowlist` 命中（ALLOW），并在报告中列出理由。

### 2.3 扫描闸门：magic bytes（BLOCK）

没有扩展名、或改了扩展名的文件按内容判定，命中即 BLOCK：

- `MZ`（PE 可执行）、`\x7fELF`（ELF）；
- `PFS0`（NSP）、`NCA3/NCA2/NCA0`（NCA）、`NSO0`/`NRO0`（Switch 可执行）；
- `XP3\r\n `（KiriKiri 归档）、`PK\x03\x04`（ZIP，需显式 allowlist 的合法场景）、`7z\xbc\xaf\x27\x1c`、`Rar!\x1a\x07`、gzip `\x1f\x8b`；
- `OggS`、`ftyp`（MP4/ISO-BMFF，偏移 4）、`RIFF`+`WAVE`（WAV）；
- PNG/JPEG/BMP magic：只允许 `IMAGE_ALLOWLIST` 中的路径，否则按「allowlist 之外的图片」BLOCK。

首 8 KiB 内出现 NUL 字节、且不是文本的文件，判定为 `binary content` 并 BLOCK（二进制无法做文本级扫描）。

### 2.4 扫描闸门：文本敏感信息（BLOCK）

对可解码文本（UTF-8，失败则 latin-1）扫描，命中即 BLOCK：

- GitHub token 前缀（`gh[pousr]_` 与 `github_pat_` 后接长串）；
- AWS access key id（`AKIA` + 16 位大写字母数字）；
- PEM 私钥块（RSA/OpenSSH/EC/DSA/PGP）；
- 通用密钥赋值：`token`/`password`/`secret`/`api_key` 等后跟长字面量；
- Nintendo 密钥材料赋值（`header_key`、`key_area_key_*`、`title_key_*`、`titlekek_*`、`master_key_*` 后跟十六进制长串）；
- 个人 Windows 主目录路径 `C:\Users\<name>` 或 `C:/Users/<name>`。

报告中的命中值一律脱敏（前 6 字符 + 长度），不落原文。

### 2.5 仅 REVIEW（警告，不阻断）

- 路径关键词：`save`、`dump`、`romfs`、`game_data`、`keys`、`cert`、`token`、`password`、`secret`（若同一路径同时命中高危扩展名/文件名，升级为 BLOCK）；
- 开发机绝对路径：`E:/`、`D:/` 等盘符路径（历史构建日志允许存在，只计数）；
- 大文件：单文件 > 8 MiB（图片白名单除外）→ REVIEW，提示人工确认内嵌数据。

### 2.6 导出时确定性脱敏（与「个人目录」规则的衔接）

任务要求「个人目录路径 → BLOCK」，但真实仓库的历史证据/规划文档里本来就有 190 个文件 / 448 处 `C:\Users\<name>` 形式的路径（绝大多数是 Citron/命令行日志切片）。如果直接 BLOCK，公开快照将永远无法生成。

因此本流程采用「**导出时确定性脱敏 + 扫描器仍 BLOCK 残留**」的双层策略：

1. 生成公开树时，对所有非二进制文件把 `C:\Users\<name>` / `C:/Users/<name>` 统一改写为 `C:\Users\<user>` / `C:/Users/<user>`（确定性，不含真实用户名），并统计 `redacted_files` / `redacted_home_hits` 写入 `PUBLIC_RELEASE.md`；
2. 扫描器本身仍把个人主目录路径判为 BLOCK——**二进制或不可解码文件不会被改写**，一旦残留（例如伪装成文本的二进制）仍会阻断发布。

这是对任务规则的一处有意偏离（保持历史文档可通过），理由与统计已写入 TASK-PUBLIC 报告。

### 2.7 扫描时机与可复现性

1. 生成树写完后扫描一次（跳过 `.git` 与两个脚本生成的报告文件，避免规则描述自触发）；
2. 若请求 ZIP，按确定性方式打包后再**从 ZIP 条目复扫一次**（直接读条目的字节判定 magic/文本，不解包）；
3. 任一 BLOCK → 抛 `SanitizationError`、CLI 退出码 1，publish 拒绝 stage/commit；
4. 同一输入两次生成：树内逐文件内容一致，ZIP sha256 一致；唯一允许变化的是 `PUBLIC_RELEASE.md` 的 `generated_at`（UTC 时间戳）。

## 3. 生成公开树

```bash
cd "E:/Othergames/Nintendo Switch/Workspace/GalNX"
python scripts/public_release_sanitize.py \
  --out E:/galnx-build/public/GalNX \
  --zip E:/galnx-build/public/GalNX-public.zip
```

输出目录必须为空（或加 `--force`），且不能位于仓库内部。脚本会：

1. 校验许可文件齐全（`LICENSE`、`THIRD_PARTY_NOTICES.md`、三份上游 LICENSE）**且已被 git 跟踪**，缺一个就失败——保证发布树对应一个真实 commit；
2. `git ls-files` 取跟踪文件，按 2.1 分成保留/排除（排除统计分 `art`/`data`）；
3. 复制保留文件，改写 markdown 引用、脱敏个人目录路径；
4. 写 `PUBLIC_RELEASE_ART_EXCLUSIONS.txt`（排除清单）；
5. 扫描生成树；有 BLOCK 立即失败（树保留以便排查，但不写报告）；
6. 可选打确定性 ZIP，并从 ZIP 条目复扫；
7. 最后写脚本生成的 `PUBLIC_RELEASE.md`（来源 commit、计数、扫描结果、allowlist 命中、ZIP 大小与 sha256）。

退出码：`0` 成功（BLOCK=0）；`1` 策略文件缺失、输出不可用或有 BLOCK 命中。

当前基线（2026-11-11，0.1.0-preview 公开快照，私有源 `cc6148c`，脚本一次实际输出）：

```text
kept=1018 excluded=359 bytes=26606932 rewritten_refs=0
excluded kinds: {'art': 357, 'data': 2}
scan: block=0 review=469 scanned=1018
  review dev machine absolute path: 439
  review sensitive path keyword: 30
allowlist: examples/batch/games/demo-a/data.xp3 (62-byte UTF-8 placeholder fixture ...)
zip: E:/galnx-build/public/GalNX-v145-final.zip (9142838 bytes, sha256=17688031...)
```

`review=469` 是允许保留的历史证据（路径关键词与 `E:/` 构建路径），不是 BLOCK；发布前只需确认没有新增异常类别。

## 4. 发布方式（v1.41 起：公私双仓库）

### 4.1 仓库分工（当前采用）

| 仓库 | 可见性 | 内容 | 用途 |
| --- | --- | --- | --- |
| `KIRARITenshiChan/GalNX` | 私有 | 全部源码、文档、**357 张游戏截图/封面/图标 + 2 个原始游戏数据文件**、计划快照、实验日志 | 开发主仓库，每个里程碑都推这里 |
| `KIRARITenshiChan/GalNX-public` | 公开 | sanitized 快照（当前 1,018 个文件 / 约 26.6 MB），无游戏素材、无 keys、无游戏数据 | 对外展示与分发代码/补丁/文档 |

公开仓库只接收干净树快照，**不 push 私有历史**：公开历史从 0 开始，每个快照是一个独立 commit（message 记录私有源 commit），因此公开树里的图片路径永远不存在，也不会因为历史回溯而泄漏。私有仓库继续按原节奏开发，攒到「一个里程碑完成 / 一次真机验收通过 / 计划升版」后再同步公开仓库。

### 4.2 同步公开镜像（推荐流程）

首次：在 GitHub 建**空仓库**（不要勾选 README/.gitignore/LICENSE，否则首推会冲突），然后本地准备 mirror：

```bash
cd "E:/Othergames/Nintendo Switch/Workspace/GalNX"
python scripts/public_release_publish.py \
  --mirror E:/galnx-build/public/GalNX-public
# 首次会自动 git init -b main 并提交第一个快照；提交信息形如
#   Public snapshot of private commit <sha>
```

后续同步（私有仓库有新提交后）：

```bash
python scripts/public_release_publish.py --mirror E:/galnx-build/public/GalNX-public
```

推送由 `cred_use` 注入 token，脚本本身不接触凭据：

```text
cred_use(GH_TOKEN, mode=exec, command="git",
          args=["-C", "E:/galnx-build/public/GalNX-public", "push", "origin", "main"])
```

`public_release_publish.py` 的行为：清空 mirror 工作树（保留 `.git`）→ 重新生成 sanitized 树并扫描 → 设置 origin → `git add -A` + commit（没有变化则跳过 commit）→ 打印推送命令。

- **fail-closed**：生成本身就会扫描；任一 BLOCK 时脚本中止，不 stage、不 commit、不打印推送命令，退出码 1；
- **幂等**：重复运行只会在私有源 commit 变化时产生新快照；只有 `generated_at` 时间戳不同不会制造空提交（脚本检测到等价后回退报告文件）；
- 真正推送由 Lead 执行（不要裸 `git push`）。

### 4.3 备选：从干净树手工新建仓库/孤儿分支

```bash
# 在公开树里初始化一个全新仓库（或先建空 GitHub 仓库再 remote add）
cd E:/galnx-build/public/GalNX
git init -b main
git add -A
git commit -m "GalNX public snapshot"
git remote add origin https://github.com/KIRARITenshiChan/GalNX-public.git
# 推送用 cred_use（身份/凭据由 broker 注入），不要裸 git push
```

注意：公开树的提交历史从 0 开始，与原私有仓库没有 commit 关联。

### 4.4 备选：重写历史后推送

如果必须保留历史，用 git-filter-repo 把游戏素材路径整体移除（先备份裸库）：

```bash
git clone --mirror <private-repo> GalNX-mirror.git
cd GalNX-mirror.git
git filter-repo --force --invert-paths \
  --path docs/assets \
  --path examples/pilot01 --path examples/pilot02 --path examples/pilot03 --path examples/pilot04 \
  --path-glob "docs/milestones/**/*.png" --path-glob "docs/milestones/**/*.jpg"
```

重写后所有 commit 哈希都会变；`docs/builds/` 里引用的证据路径会失效，需要按第 5 节复查。

### 4.5 发布记录

| 日期 | 私有源 commit | 公开 commit | 快照规模 | 说明 |
| --- | --- | --- | --- | --- |
| 2026-11-10 | `7306669` | `ff49e0d` | 967 文件 / 24,286,065 B（排除 351） | 首次公开快照：建空仓库 `GalNX-public` 后推送，公开历史从 1 个 commit 开始 |
| 2026-11-11 | `15f6d91` | `0f50c00` | 988 文件 / 25,342,753 B（排除 356） | 第 4 个快照：P44 NV12 零拷贝引擎同步到 IROSEKA / MOYU 两包 + 用户封面图标 + 计划 v1.43 |
| 2026-11-11 | `a798fac` | `26dedca` | 1,006 文件 / 26,078,021 B（排除 359，其中 art 357 + data 2） | 第 5 个快照：0.1.0-preview 收敛（构建契约 not_configured、引擎能力/verification、fail-closed 公开闸门、SBOM inventory、缓存 schema 2、CI），脚本 `0 BLOCK`，ZIP 8,913,959 B sha256 `7f793d07…` |
| 2026-11-11 | `cc6148c` | `071e2c9` | 1,018 文件 / 26,630,480 B（排除 359，其中 art 357 + data 2） | 第 6 个快照：专家复审 FIX-01..FIX-06 收口（非 TTY 构建确认 fail-closed、`examples/quickstart/` 可执行示例、Pilot-04 验证等级校准、未声明 `build.inputs` 禁用缓存）+ 计划 v1.45；sanitizer `0 BLOCK` / review 469（dev path 439 + keyword 30），导出 bytes 26,606,932，ZIP 9,142,838 B sha256 `17688031…`；公开仓库干净 clone 复跑 quickstart 首跑 artifact 269 B sha256 `5982bb06…`、二跑 cache hit |

上表只登记「发布事件」；日常增量同步按 4.2 执行，不再逐条登记（`ffe8db7`、`44d8e57` 为过渡期增量快照，未单列）。任一快照对应的私有源 commit 都写在公开树的 `PUBLIC_RELEASE.md` 中，可用它反查是哪个私有提交导出的。

## 5. 发布前验收清单

脚本已自动保证（无需手工 grep/find）：

- [x] 退出码 0 且报告 `BLOCK findings: 0`（生成树与 ZIP 各扫一次）；
- [x] 公开树内无游戏素材（`art`/`data` 排除统计可从 `PUBLIC_RELEASE.md` 与脚本输出核对）；
- [x] 高危扩展名、伪装 magic、token/私钥/Nintendo 密钥文本、个人目录路径均无 BLOCK 命中；
- [x] 生成报告里的 `Source commit`、`Kept/Excluded`、`ZIP sha256` 由脚本计算，不是手写。

仍需人工确认：

- [ ] `review` 计数（当前 461）里没有新增异常类别；`allowlist` 只有已知条目；
- [ ] mirror 仓库 `git log --oneline` 首行是 `Public snapshot of private commit <sha>`，且 `git status` 干净；
- [ ] 公开镜像 README 中同时给出私有主仓库与公开镜像地址；
- [ ] `LICENSE`、`THIRD_PARTY_NOTICES.md`、`docs/builds/patches/*/LICENSE` 存在且哈希与 [patch LICENSE 表](../builds/patches/LICENSE.md) 一致；
- [ ] 根 README 的许可段指向 MIT + NOTICE，不再写「尚未确定」；
- [ ] 若走 4.2，确认公开历史里也不存在 `docs/assets/`、`examples/pilot0*/`、`docs/milestones/**/*.png`。

## 6. 已知限制

- 脚本只处理 **git 跟踪的文件**；未跟踪的本地产物（`.cache/`、`workspaces/`）本来就不在发布候选里。
- 排除是「发布树」层面的：私有仓库仍保留全部证据，满足里程碑记录要求。
- 个人目录脱敏只作用于「可解码文本、且首 8 KiB 无 NUL」的文件；二进制不做改写，命中即 BLOCK——这是刻意的 fail-closed 行为。
- 扫描是「已知模式」匹配，不是通用 secret scanner；新形态的凭据/游戏数据格式需要更新 2.2–2.4 的规则与测试。
- `.git` 目录被跳过：publish mirror 会保留 `.git` 跨轮重建，扫描 git 压缩对象会误判；公开快照本身不含 git 元数据。
- 不处理作者/邮箱信息；身份统一由 `dsh-git-identity` + `gh_push` 负责。
- 游戏素材的再引入需要版权方许可，不在本流程范围内。
