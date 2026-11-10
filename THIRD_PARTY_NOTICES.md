# 第三方组件与许可声明（THIRD_PARTY_NOTICES）

本文件说明 GalNX 仓库的**许可边界**。根目录 [LICENSE](LICENSE) 只覆盖本项目自己撰写的代码与文档；
仓库里还有三类内容**不适用** MIT，必须分别对待。

## 1. 本仓库自身代码：MIT

- 许可：MIT，Copyright (c) 2026 KIRARITenshiChan，全文见 [LICENSE](LICENSE)。
- 覆盖范围：`src/galnx/`、`scripts/`、`schemas/`、`tests/`、`examples/` 下的清单（`*.yaml`）与截图以外的素材、
  `docs/` 下由本项目撰写的文档与构建记录、根目录 `README.md`、`pyproject.toml`。
- 引用第三方代码的片段（补丁、源码取证引文）按其上游许可处理，见第 2 节。

## 2. 引擎补丁：随上游许可，**不是** MIT

`docs/builds/patches/` 下的补丁/diff 是对上游引擎源码的修改，按上游许可证分发。每个子目录都附有上游 LICENSE 原文：

| 目录 | 上游 | 许可 | 许可原文 |
| --- | --- | --- | --- |
| `docs/builds/patches/rfvp-switch/` | xmoezzz/rfvp 0.7.0（MPL-2.0） | MPL-2.0 | `rfvp-switch/LICENSE` |
| `docs/builds/patches/krkrsdl2-switch-emulator/` | krkrsdl2（MIT） | MIT | `krkrsdl2-switch-emulator/LICENSE` |
| `docs/builds/patches/k2nx-switch/` | Erige005/Kirikiroid2-NX（KiriKiri2 血统） | KiriKiri BSD-style 日文条款（非 SPDX） | `k2nx-switch/LICENSE` |
| `docs/builds/patches/k2nx-patched-vs-v1.0.1.diff` | 同上 | 同上 | `k2nx-switch/LICENSE` |

要点：

- **MPL-2.0（rfvp）是文件级 copyleft**：分发包含这些修改的二进制时，必须提供对应源文件与 MPL-2.0 全文；
  我们已把修改以 diff 形式公开在本仓库，满足可获取性。
- **KiriKiri 许可不是 SPDX 标识**：`examples/engines/kirikiroid2-nx.yaml` 的 `license_spdx` 因此是 `NOASSERTION`。
  该上游 LICENSE 还列出了其捆绑组件（FFmpeg LGPL-2.1、OpenCV BSD-3-Clause、cocos2d-x MIT、UnRAR 再分发限制等），
  若再分发 Kirikiroid2-NX 的 NSP，必须同时满足这些条款。
- 补丁目录里另有说明文件（`README.md`）与生成/回放脚本，按 MIT 处理（它们是本项目写的）。
- 总述见 [docs/builds/patches/LICENSE.md](docs/builds/patches/LICENSE.md)。

## 3. 游戏素材（截图、封面、图标）：第三方版权，**不在 MIT 范围内**

`docs/milestones/evidence/`（各里程碑与 P 系列的 Citron/真机截图）、`docs/assets/*-cover.png`、
`examples/pilot0*/icon-256.jpg` 中出现的游戏画面、角色、Logo、封面，版权归各发行商/开发方所有
（已涉及 FAVORITE 的《樱花，萌放。》《五彩斑斓的世界》《映入红瞳的世界》等）。

- 这些素材**仅用于开发记录与验收证据**，不构成对游戏的再分发许可，也不随 MIT 授权。
- **公开本仓库前必须把它们从发布树里隔离出去**：运行 `scripts/public_release_sanitize.py`，
  流程与判定规则见 [docs/environment/public-release.md](docs/environment/public-release.md)。
- 例外：由本项目自己生成的纯技术图像（无游戏素材）可以保留，但需要显式加入脚本的白名单并说明。

## 4. 密钥与游戏数据：不入库

- 仓库**不包含** `prod.keys`、`title.keys`、Nintendo 证书、游戏数据（`*.xp3`、`*.hcb`、`*.bin`、电影等）或其哈希以外的内容。
- NSP 打包时 keyset 只按**显式路径**读取（`galnx package nsp build --keyset <path>`），日志只记录 path/size/sha256/mtime，禁止入库/CI/日志明文。
- 用户自行安装的未签名 NSP 不得再分发。

## 5. 构建期第三方组件

| 组件 | 许可 | 用途 |
| --- | --- | --- |
| devkitPro / devkitA64 / libnx | GPL-2.0+ / ISC（libnx） | Switch 交叉编译与系统 API |
| SDL2（switch portlib） | zlib | rfvp / krkrsdl2 窗口与输入 |
| FFmpeg（含 nvtegra 补丁） | LGPL-2.1+ | H.264 OP 解码与 nvtegra 硬解（静态链接，分发二进制需履行 LGPL） |
| rfvp | MPL-2.0 | FVP 运行时 |
| krkrsdl2 | MIT | KiriKiri SDL2 运行时 |
| ONScripter-NX | GPL-2.0-or-later | NScripter 运行时（GPL 传染性需评估） |
| Brewser | MPL-2.0 | Web 运行时 |
| Kirikiroid2-NX | 非 SPDX（KiriKiri BSD-style） | KiriKiri2 运行时 |
| hacBrewPack | GPL-2.0 | NSP 打包（仅构建期工具） |
| nstool | MIT | NSP 解析与校验（仅构建期工具） |
| nx-hbloader / Atmosphère | ISC / GPL-2.0 | 真机自制环境（用户自有） |
| PyYAML / jsonschema | MIT / MIT | Python 依赖（运行时不随 NSP 分发） |
| IPAexGothic（仅 M1 KAG3 演示） | IPA Font License 1.0 | 参见 `docs/third_party/fonts/` |

## 6. 分发二进制时的义务

若要把本仓库产出的 NSP 交给第三方（不建议，且不含游戏数据时通常也不是完整游戏）：

1. 逐项核对第 2、5 节；GPL 组件（ONScripter-NX、devkitPro 工具链）与 LGPL（FFmpeg 静态链接）需要提供对应源码/目标文件与许可文本。
2. 不得包含第 3 节的游戏素材与第 4 节的密钥/游戏数据。
3. 保留本文件与各子目录 LICENSE。

---
如对某处版权归属有疑问，请开 issue；确认后会立即调整或移除相关内容。
