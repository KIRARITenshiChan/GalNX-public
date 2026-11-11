# git EOL 与 gh_push 注意事项（2026-11-09）

- 本仓库没有 `.gitattributes`，文本 blob 的 EOL 按目录而异：`docs/builds/*`、`docs/builds/README.md`、`docs/research/*`、`docs/milestones/evidence/*` 多为 LF；`docs/PLAN_DRAFT_v*.md`、`docs/milestones/M5-fvp.md` 为 CRLF。
- 2026-11-09 事故：`gh_push`（dsh-git-identity 插件）在提交 `b64e491` 时把 32 个既有 LF 文件规范化为 CRLF 一并提交，产生 46 files / +16,139 / −14,156 的纯 EOL diff。
  - 修复：`git checkout 886311f -- <32 paths>` 恢复父提交 blob，宿主 git 提交 `8dfeffa`（仅 32 文件、+14,155/−14,155，全部 EOL），随后 `cred_use GH_TOKEN mode=exec git ... push` 推送。
  - 修复后 `git diff --stat 886311f HEAD` 只剩 14 个预期文件（P40b 文档/补丁/证据/计划 v1.36）。
- 约定：本仓库提交用宿主 git（身份由插件以环境变量固定），推送用 `cred_use GH_TOKEN mode=exec git -c http.proxy=http://127.0.0.1:7897 -c credential.helper=... push origin main`；`gh_push` 仅在确认工作树字节与 blob 一致时使用（否则会再次引入 EOL churn）。
- 自检：提交前跑 `git diff --stat <prev> HEAD`；用 `git ls-files --eol <path>` 查看索引与工作树的 `i/lf`/`w/crlf` 状态。

## 2026-11-10 全仓库 commit 身份统一（filter-branch 失败 → git-filter-repo）

- 背景：仓库共 74 个 commit，其中旧身份 56×`GalNX Workbench <galnx@localhost>`、8×`GalNX <galnx@local>`、2×`KIRARITenshiChan <kirari@users.noreply.github.com>`、1×`KIRARITenshiChan <kirarituenshi@users.noreply.github.com>`，其余已是规范身份。目标：全部统一为 `KIRARITenshiChan <238937993+KIRARITenshiChan@users.noreply.github.com>`。
- `git filter-branch` 在本机不可用：Git for Windows `2.56.0.windows.4.niugit` 下，无论仓库路径是否含空格（在无空格 clone `E:/galnx-rewrite` 中同样复现），只要执行 `git filter-branch -f --env-filter 'true' -- --all` 就报 `fatal: not a git repository: '<msys-path>/.git'`；而同一 shell 的 `git rev-parse --git-dir`（→ `.git`）、`git status`、`git log` 均正常 ⇒ 是该 git 构建自带的 filter-branch 脚本不兼容，不是仓库损坏。
- 替代方案：`git filter-repo`（单文件 Python，版本 `31ebad4c8fb3`，下载自 https://raw.githubusercontent.com/newren/git-filter-repo/main/git-filter-repo ，207.3 KB sha256 `39d35fb2c35637a9d555353b6a8b53a223a227d3beb61a0ac7e1180bfa5572f1`，存 `E:/Othergames/Nintendo Switch/Workspace/tools/galnx-tools/git-filter-repo.py`（2026-11-11 前位于 `E:/galnx-tools/git-filter-repo.py`））。在无空格 clone `E:/galnx-rewrite` 中执行：

```bash
python "/e/Othergames/Nintendo Switch/Workspace/tools/galnx-tools/git-filter-repo.py" --force \
  --name-callback 'return b"KIRARITenshiChan"' \
  --email-callback 'return b"238937993+KIRARITenshiChan@users.noreply.github.com"'
```

- 校验：74 个 commit 的 author/committer 全部为规范身份；新 HEAD tree `edbe8c8da446e4a6b9dc8694ef3a2362e70dbc7e` 与旧 HEAD tree 完全相同 ⇒ 只改身份元数据，文件内容与提交顺序不变。原工作仓库保留 `backup/pre-identity-rewrite`（`1d029f5`，旧历史）作为本地回滚点。
- force push：`cred_use GH_TOKEN mode=exec git -c http.proxy=http://127.0.0.1:7897 -c credential.helper=... push --force origin main`，GitHub 远端 `8a6d112` → `3f19e7a`；`git ls-remote origin refs/heads/main` 复核为 `3f19e7a144d1c09d21c9232fa1c59711c6dc3888`。
- 工作仓库同步：原仓库从本地 clone `git fetch /e/galnx-rewrite main` 后 `git reset --hard 3f19e7a`（并 `git update-ref refs/remotes/origin/main 3f19e7a`），避免在含空格路径下走大对象 HTTP fetch；随后删除临时 clone。
- 约定：新提交仍由宿主 git 完成（dsh-git-identity 插件已通过 `GIT_AUTHOR_*`/`GIT_COMMITTER_*` 固定身份），推送仍用 `cred_use GH_TOKEN mode=exec git`（代理 + 内联 credential helper）；不要再手写 `-c user.name/-c user.email` 或 `--author`。


## 2026-11-11 工作区收归（路径迁移）

- 为让所有构建产物与工具集中到 `E:/Othergames/Nintendo Switch/Workspace`，把 `E:/galnx-build`（约 447.6 GiB / 212 顶层项）同卷移动到 `Workspace/build`，并保留目录 junction `E:/galnx-build -> E:/Othergames/Nintendo Switch/Workspace/build`，历史脚本与文档里的 3,700+ 处 `galnx-build` 引用继续可用。
- `E:/galnx-tools/git-filter-repo.py` 移到 `Workspace/tools/galnx-tools/git-filter-repo.py`（未建 junction；上面命令块中的旧路径为此处修订，正文其余历史记录未改）。
- `E:/tmptest`、`E:/d`（rustup 残留副本）归入 `Workspace/build/_legacy/`；空目录 `E:/e` 删除；`E:/galnx` junction 保留指向 `Workspace/GalNX`。
- 此后新的构建、下载与实验产物一律落在 `Workspace/build/`（或仓库内被 gitignore 的 `workspaces/`、`.cache/`），不要再写 `E:` 根目录。
