# 公开仓库前的素材隔离

> 状态：生效中（v1.40 起）。相关：[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)、[LICENSE](../../LICENSE)、[docs/builds/patches/LICENSE.md](../builds/patches/LICENSE.md)。

## 1. 为什么需要隔离

GalNX 仓库同时承担「框架代码」和「实验记录」两个角色。实验记录里有 351 张图片（约 358 MB）：

- `docs/milestones/`：342 张 Citron / 真机截图，含商业游戏的标题画面、立绘、CG、OP 帧；
- `docs/assets/`：4 张作品封面（pilot01–04）；
- `examples/pilot0*/`：5 张 NSP 图标。

这些游戏画面的版权属于各发行商/开发方（FAVORITE 等），**不在 MIT 许可范围内**，也不能随仓库公开。
而 `git ls-files` 显示被跟踪的 1,316 个文件里，图片占了 358 MB——从工作树删掉并不能保护它们，**私有历史里仍然存在**。
所以公开流程是「先导出干净树，再以干净树发布」，不是「删文件后直接 push」。

## 2. 判定规则

脚本 `scripts/public_release_sanitize.py` 的规则（改规则要同步改测试 `tests/test_public_release.py`）：

- 后缀属于 `.png/.jpg/.jpeg/.webp/.gif`，且路径以 `docs/milestones/`、`docs/assets/`、`examples/pilot` 开头 → **判定为游戏素材，排除**；
- 其它文件（代码、清单、日志、哈希清单、文本证据、补丁）→ 保留；
- 例外白名单 `IMAGE_ALLOWLIST` 默认空：新增非游戏图片必须显式加入并写理由，否则一律按游戏素材处理。

当前基线（commit `c52dec7`）：保留 965 个文件 / 23.84 MB，排除 351 个文件 / 358.2 MB；生成树共 967 个文件（含 PUBLIC_RELEASE.md 与排除清单），zip 8.0 MB，输出树内游戏图片数为 0。

Markdown 引用处理：生成时若发现指向被排除素材的 `![...]()` 或 `[...]()` 引用，会分别改写为占位符 `*[game art removed from public tree]*` 与纯文本标签；围栏代码块内的路径保持原样（它们记录的是构建命令）。当前跟踪的 `.md` 里没有这种引用（已用 `git grep` 核对），因此 `rewritten_refs=0`，规则留给后续新增文档使用。

## 3. 生成公开树

```bash
cd "E:/Othergames/Nintendo Switch/Workspace/GalNX"
python scripts/public_release_sanitize.py \
  --out E:/galnx-build/public/GalNX \
  --zip E:/galnx-build/public/GalNX-public.zip
```

输出目录必须为空（或加 `--force`），且不能位于仓库内部。脚本会：

1. 校验许可文件齐全（`LICENSE`、`THIRD_PARTY_NOTICES.md`、三份上游 LICENSE）**且已被 git 跟踪**，缺一个就失败——保证发布树对应一个真实 commit；
2. `git ls-files` 取跟踪文件，复制未被排除的部分；
3. 复制后再校验没有游戏图片漏进去；
4. 写 `PUBLIC_RELEASE.md`（来源 commit、计数、缺失原因）与 `PUBLIC_RELEASE_ART_EXCLUSIONS.txt`（排除清单）；
5. 可选打 zip。

## 4. 发布方式（v1.41 起：公私双仓库）

### 4.1 仓库分工（当前采用）

| 仓库 | 可见性 | 内容 | 用途 |
| --- | --- | --- | --- |
| `KIRARITenshiChan/GalNX` | 私有 | 全部源码、文档、**351 张游戏截图/封面/图标**、计划快照、实验日志 | 开发主仓库，每个里程碑都推这里 |
| `KIRARITenshiChan/GalNX-public` | 公开 | sanitized 快照（965 个文件 / 24 MB），无游戏素材、无 keys、无游戏数据 | 对外展示与分发代码/补丁/文档 |

公开仓库只接收干净树快照，**不 push 私有历史**：公开历史从 0 开始，每个快照是一个独立 commit（message 记录私有源 commit），因此公开树里的图片路径永远不存在，也不会因为历史回溯而泄漏。私有仓库继续按原节奏开发，攒到「一个里程碑完成 / 一次真机验收通过 / 计划升版」后再同步公开仓库，避免把逐次实验提交都镜像出去。

### 4.2 同步公开镜像（推荐流程）

首次：在 GitHub 建**空仓库**（不要勾选 README/.gitignore/LICENSE，否则首推会冲突），然后本地准备 mirror：

```bash
cd "E:/Othergames/Nintendo Switch/Workspace/GalNX"
python scripts/public_release_publish.py \
  --mirror E:/galnx-build/public/GalNX-public
# 首次会自动 git init -b main 并提交第一个快照；提交信息形如
#   Public snapshot of private commit 7306669
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

`public_release_publish.py` 的行为：清空 mirror 工作树（保留 `.git`）→ 重新生成 sanitized 树 → 设置 origin → `git add -A` + commit（没有变化则跳过 commit）→ 打印推送命令。它是幂等的：重复运行只会在私有源 commit 变化时产生新快照。

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

## 5. 发布前验收清单

- [ ] `python scripts/public_release_sanitize.py ...` 退出码 0，输出 `excluded` 数与 `PUBLIC_RELEASE_ART_EXCLUSIONS.txt` 行数一致；
- [ ] 公开树里 `find . -iname "*.png" -o -iname "*.jpg"` 为空（或只剩白名单）；
- [ ] mirror 仓库 `git log --oneline` 首行是 `Public snapshot of private commit <sha>`，且 `git status` 干净；
- [ ] 公开镜像 README 中同时给出私有主仓库与公开镜像地址；
- [ ] `LICENSE`、`THIRD_PARTY_NOTICES.md`、`docs/builds/patches/*/LICENSE` 存在且哈希与 [patch LICENSE 表](../builds/patches/LICENSE.md) 一致；
- [ ] 根 README 的许可段指向 MIT + NOTICE，不再写「尚未确定」；
- [ ] 不含 `prod.keys`、`title.keys`、`*.xp3`、`*.hcb`、`*.nsp`、`*.wmv`/`*.mp4` 游戏数据；
- [ ] 机密扫描：`grep -RIn "ghp_\|github_pat_\|prod.keys"` 只应命中说明文字；
- [ ] 若走 4.2，确认历史里也不存在 `docs/assets/`、`examples/pilot0*/`、`docs/milestones/**/*.png`。

## 6. 已知限制

- 脚本只处理 **git 跟踪的文件**；未跟踪的本地产物（`.cache/`、`workspaces/`）本来就不在发布候选里。
- 排除是「发布树」层面的：私有仓库仍保留全部证据，满足里程碑记录要求。
- 不处理作者/邮箱信息；身份统一由 `dsh-git-identity` + `gh_push` 负责。
- 游戏素材的再引入需要版权方许可，不在本流程范围内。
