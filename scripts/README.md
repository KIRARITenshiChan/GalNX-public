# scripts/ — 可复现脚本

这些脚本是 M0 实测（2026-10-29）用到的入口，供复现与审计追溯。构建产物与日志归档在 `workspaces/m0-hello/`（`workspaces/` 不入库，见 `.gitignore`）。

| 脚本 | 用途 | 调用方式 |
| --- | --- | --- |
| `m0_build_hello.sh` | 在无空格构建目录编译 devkitPro `examples/switch/templates/application` 得到 hello-world NRO，并归档产物/日志/哈希 | `env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '"$0"' scripts/m0_build_hello.sh` |
| `collect_env_snapshot.sh` | 采集工具链环境：DEVKITPRO、gcc/ld 版本、target、nxlink 帮助、pacman 包清单、目录体积 | 同上方式在 MSYS2 shell 内执行 |
| `collect_env_snapshot2.sh` | 补充采集：gcc 绝对路径版本、`-dumpmachine`、libnx 版本、示例目录清单 | 同上 |

## 注意

- devkitPro 的 make 工程**不能在含空格路径下构建**（`switch_rules` 里 `$(MAKE) -C $(BUILD) -f $(CURDIR)/Makefile` 未加引号，`$(CURDIR)` 含空格会把 `-f` 参数拆词）。本机因此使用 `E:\galnx-build` 作为构建目录，再把产物归档回工作区。
- MSYS2 里没有代理环境变量；`pacman` 下载需要 `XferCommand` 显式带 `http_proxy=http://127.0.0.1:7897`，详见 `docs/TOOLCHAIN_AUDIT.md` §8.2 与 `docs/environment/`。
- 凭证、密钥、`workspaces/`、`.cache/` 一律不入库。