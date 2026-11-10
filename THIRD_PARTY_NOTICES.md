# 第三方组件与许可声明（THIRD_PARTY_NOTICES）

> 元数据：生成日期 2026-11-11；对照基线 commit 974a4141af4a86a83f9434ea69ebb9dc9ffe4834（main）。
> 机器可读清单：[docs/third_party/inventory.yaml](docs/third_party/inventory.yaml)（33 个组件 / 4 个产物），
> 校验脚本：[scripts/check_license_inventory.py](scripts/check_license_inventory.py)。
> 本文件只界定许可边界，不构成法律意见。

## 0. 分发边界与合规结论（先读这一节）

- **本仓库自身代码是 MIT**（Copyright (c) 2026 KIRARITenshiChan，全文见 [LICENSE](LICENSE)），仅覆盖本项目撰写的内容；第三方组件、引擎补丁、游戏素材不在 MIT 范围内。
- **当前测试产物**（均含商业游戏数据/素材，本来就不能对外分发，此处仅记录边界）：IROSEKA 1.2.5-test（10,087,541,464 B，sha256 f6860842…）、SAKURA 1.3.3-test（8,116,841,176 B，sha256 965ee356…）、K2NX A10 CN 1.0.9（sha256 0efc23f6…），详见 inventory 的 scope.artifacts。
- **P0 结论：rfvp 产物静态链接的 FFmpeg 是 GPL，不是 LGPL。** 该 FFmpeg 来自 averne/FFmpeg 的 nvtegra 分支（commit caeec83b791be08ed43468a2ef426d6901d51c78，基于 FFmpeg 7.1），配置为 --enable-gpl --enable-nvtegra；config.h 中 FFMPEG_LICENSE 为 "GPL version 2 or later"，且 configure 里 nvtegra_deps="gpl"——**保留 NVDEC 硬解就无法去掉 --enable-gpl**。证据见 docs/builds/046-op-h264-nvtegra.md 与 nvdec 构建记录。旧版本文档把它写成 LGPL-2.1+ 是错误，本版已纠正。
- **决策：方案 B（保留 NVDEC + GPL-2.0-or-later 合规分发），2026-11-11 由项目 owner 拍板。** 理由：NVDEC 是 Switch 真机 60fps 电影路径的前提（probe9 硬解 decode 0.44 ms；软解会回到 30fps 以下并占满 CPU），方案 A 会推翻已验收的 P40/P44 成果；GPL 义务可控：GalNX 公共仓库只分发 MIT 编排层与上游 MPL/MIT 补丁，**不发布 NSP 二进制**，NSP 由用户本机构建/安装（GPL 组合作品的私有使用）；若将来对外分发 NSP，随包提供对应源码（rfvp fork + FFmpeg nvtegra 分支 + 构建脚本）即可满足。
- 因此：rfvp.elf / NSP 整体按 GPL-2.0-or-later 组合作品处理；对外分发时的义务 = 对应源码、构建脚本、修改声明、许可文本（详见第 6 节）。MPL-2.0（rfvp 上游）与 GPL 组合的兼容性仍需专门评估，本文件不作断言。
- **K2NX 路线**：Kirikiroid2-NX 的 LICENSE 是 KiriKiri BSD-style 日文条款（非 SPDX），其自带 THIRD_PARTY_LICENSES 还列出 FFmpeg 3.2.19（LGPL）、OpenCV（BSD-3-Clause）、cocos2d-x（MIT）、UnRAR（再分发限制）、libbpg、jxrlib 等。**K2NX CN 内容补丁来自 t-satoru-Studio/haruno_script，该仓库没有 LICENSE 文件，默认版权保留 → 汉化内容与脚本不可再分发，只限本地自用。**
- 构建/打包/测试工具（devkitA64 工具链、switch-tools、hacBrewPack、nstool、NTON、Atmosphère/nx-hbloader）**不进入 NSP 产物**，见第 2、3 节。

## 1. 随产物分发（runtime-linked / runtime-bundled）

### 1.1 rfvp 产物：IROSEKA / SAKURA（静态链接进 rfvp.elf）

| 组件 | 版本 | 许可 | 链接 | 义务要点 |
| --- | --- | --- | --- | --- |
| rfvp（上游 xmoezzz/rfvp） | 9f07adef2eb5d559777f9bf59a67b756875cb24f（0.7.0 = 99435f22） | MPL-2.0 | static | 文件级 copyleft：提供修改源文件与 MPL 全文；修改已以 diff 公开（第 4 节） |
| FFmpeg（averne/FFmpeg nvtegra 分支） | 7.1 + caeec83b791be08ed43468a2ef426d6901d51c78 | **GPL-2.0-or-later** | static | **P0，决策 B**：整套产物按 GPL-2.0-or-later 处理；公共仓库不含 NSP，对外分发 NSP 时提供对应源码 + 构建脚本 + 许可文本 |
| SDL2（devkitPro switch-sdl2） | 2.28.5 | Zlib（上游） | static | 保留版权与许可声明；devkitPro 包元数据误标 LGPL，按上游 zlib 处理 |
| zlib（switch-zlib） | 1.3.1 | Zlib | static | 保留声明 |
| libdeflate | 1.24（P18 试用） | MIT | **未链接** | P18 接入后 Citron 崩溃（Cannot execute instruction at unmapped address 0x0），已回退 zlib；最终 ELF 无 libdeflate 符号，仅作 build-only 历史记录 |
| Mesa（switch-mesa，libEGL/libglapi） | 20.1.0-5 | MIT | static | 保留声明 |
| libdrm_nouveau | 1.0.1-2 | MIT | static | 保留声明 |
| libnx | 4.12.0 | ISC | static | 保留声明 |
| GCC runtime（libstdc++ / libgcc） | devkitA64 GCC 16.1.0 | GPL-3.0-or-later WITH GCC-exception-3.1 | static | 运行时例外允许专有链接；保留声明 |

### 1.2 K2NX A10 产物（KiriKiri2 运行时，静态链接）

| 组件 | 版本 | 许可 | 链接 | 义务要点 |
| --- | --- | --- | --- | --- |
| Kirikiroid2-NX | e96b6034c292c6ccdb099823ab6a0a6b505f77f3（v1.0.1） | KiriKiri BSD-style 日文条款（非 SPDX） | static | 按 LICENSE 原文保留版权与条款；捆绑组件义务见下 |
| cocos2d-x | 3.11.1 | MIT | static | 保留声明 |
| FFmpeg（K2NX 用） | 3.2.19 | LGPL-2.1-or-later | static | 提供对应源码或书面要约，并保留重链接手段 |
| OpenCV | 3.4.20（仅 core, imgproc） | BSD-3-Clause | static | 保留声明 |
| libiconv | 1.17 | LGPL-2.1-or-later | static | 提供源码/重链接手段 |
| UnRAR | 5.6.5 | UnRAR License（非 OSI） | static | **限制**：不得用其代码重建 RAR 压缩算法；再分发须保留声明 |
| libbpg | 0.9.8 | BSD-2-Clause，内嵌 HEVC 解码器为 LGPL | static | 分别满足 BSD 与 LGPL 义务 |
| jxrlib | master 分支（未锁定 commit） | BSD-2-Clause | static | 保留声明；**版本未 pin，可复现性风险** |
| blend2d | d2027ebfd6aaf53b190b6b3b497425fc85f14251 | Zlib | static | 保留声明 |
| LZMA SDK / p7zip | 对应 K2NX 构建记录 | public domain + LGPL-2.1-or-later | static | 满足 LGPL 部分义务 |
| DroidSansFallback.ttf | AOSP | Apache-2.0 | bundled（romfs） | 保留 NOTICE/许可文本 |
| K2NX CN 内容补丁（haruno_script） | 无 commit pin | **无 LICENSE（版权保留）** | bundled | **不可再分发**，仅本地自用 |

## 2. 构建期组件（build-only，不随产物分发）

| 组件 | 版本 | 许可 | 用途 |
| --- | --- | --- | --- |
| devkitA64 GCC / binutils / newlib | 16.1.0 / 2.46.0 / 4.6.0.20260123 | GPL-3.0-or-later；GPL-2.0+/LGPL-3.0+/LGPL-2.0+；newlib BSD-style | 交叉编译工具链（本仓库不打包工具链） |
| switch-tools | 1.13.1 | ISC | elf2nso / elf2nro / nxlink / nacptool / npdmtool |
| devkitPro libnx（构建期头文件与库） | 4.12.0 | ISC | 系统 API（运行时部分见 1.1） |

## 3. 开发 / 打包 / 测试环境（development-only）

| 组件 | 版本 | 许可 | 用途 |
| --- | --- | --- | --- |
| hacBrewPack | v3.05（745b16ec） | GPL-2.0-only | NSP 打包；仅子进程调用，不链接进产物 |
| nstool | v1.9.2（e89ea84b） | MIT | NSP 解析与校验 |
| NTON | v3.0.1（c5d543a9） | GPL-3.0-only | Homebrew NSP 测试 |
| Atmosphère | 见 docs/audit/00-switch-base.md | GPL-2.0-only | 真机 CFW 测试环境，用户自行安装 |
| nx-hbloader | v2.4.5（82b95122） | ISC | 真机 Homebrew 加载，用户自行安装 |
| PyYAML / jsonschema | PyYAML 6.0.3 / jsonschema 4.26.0（本机验证） | MIT | Python 依赖，不随 NSP 分发 |

## 4. 引擎补丁与上游许可（**不是 MIT**）

docs/builds/patches/ 下的补丁是对上游源码的修改，按上游许可分发；每个目录附上游 LICENSE 原文：

| 目录 | 上游 | 许可 | LICENSE 路径 / 大小 / sha256 |
| --- | --- | --- | --- |
| docs/builds/patches/rfvp-switch/ | xmoezzz/rfvp | MPL-2.0 | LICENSE 16,725 B，sha256 1f256ecad192880510e84ad60474eab7589218784b9a50bc7ceee34c2b91f1d5 |
| docs/builds/patches/krkrsdl2-switch-emulator/ | krkrsdl2 | MIT | LICENSE 1,070 B，sha256 964036d9015b116d961623847ff3b482a2ccf1578f41c2511377c03b8ccfb427 |
| docs/builds/patches/k2nx-switch/ 与 k2nx-patched-vs-v1.0.1.diff | Erige005/Kirikiroid2-NX | KiriKiri BSD-style（非 SPDX） | LICENSE 44,184 B，sha256 27dd616ec1a5c6db6d65b51c887ff1b2c59633196a840a4523b5ba4af8e0c9a4 |

- **MPL-2.0**：分发包含这些修改的二进制时须提供对应源文件与 MPL-2.0 全文；修改已以 diff 形式公开在本仓库，满足可获取性。
- **KiriKiri 条款不是 SPDX 标识**：examples/engines/kirikiroid2-nx.yaml 的 license_spdx 因此为 NOASSERTION；该 LICENSE 还含其捆绑组件（FFmpeg LGPL、OpenCV、cocos2d-x、UnRAR 限制等）条款。
- 补丁目录里的 README 与生成/回放脚本是本项目撰写的，按 MIT 处理；映射总述见 docs/builds/patches/LICENSE.md。

## 5. 字体与素材

- **IPAexGothic 004.01**（仅 M1 KAG3 演示用，不随 0.1 Preview 的 rfvp/K2NX NSP 分发）：IPA Font License 1.0；字体 6,099,900 B，sha256 3b9955a5e437ffb24c41548e79296fa724822da21ee75dc1b94f6ccdb8f400dd；许可原文 docs/third_party/fonts/IPA_Font_License_Agreement_v1.0.txt（20,564 B）；登记见 docs/third_party/README.md。
- **DroidSansFallback.ttf**（K2NX romfs 内，7,287,728 B）：Apache-2.0（AOSP）。
- **游戏素材**（截图、封面、图标：docs/milestones/evidence/、docs/assets/*-cover.png、examples/pilot0*/icon-256.jpg）版权归各发行商/开发方，不在 MIT 内，仅用于开发记录与验收证据；公开仓库前必须运行 scripts/public_release_sanitize.py（规则见 docs/environment/public-release.md）。
- **密钥与游戏数据不入库**：仓库不含 prod.keys/title.keys/证书/游戏数据；NSP 打包时 keyset 仅按显式路径读取，日志只记录 path/size/sha256/mtime。

## 6. 许可证文本位置与源码获取方式

- 机器可读清单与校验：docs/third_party/inventory.yaml、scripts/check_license_inventory.py（运行 python scripts/check_license_inventory.py --json）。
- 引擎与补丁许可原文：docs/builds/patches/ 各子目录 LICENSE，映射见 docs/builds/patches/LICENSE.md。
- 字体许可原文：docs/third_party/fonts/。
- FFmpeg nvtegra 对应源码：https://github.com/averne/FFmpeg/tree/nvtegra（commit caeec83b791be08ed43468a2ef426d6901d51c78）；上游 FFmpeg 7.1 源码见 https://ffmpeg.org/releases/。
- devkitPro / libnx / switch-tools：https://github.com/devkitPro、https://github.com/switchbrew/libnx、https://github.com/switchbrew/switch-tools。
- 打包工具：hacBrewPack https://github.com/rlaphoenix/hacBrewPack、nstool https://github.com/jakcron/nstool、NTON https://github.com/DefenderOfHyrule/NTON。
- 按方案 B（GPL 合规分发），GPL 源码提供义务至少包含：① 对应源码的固定 commit/压缩包（rvfp fork、FFmpeg nvtegra 分支 caeec83b…）；② 修改声明（diff）；③ 构建脚本与工具链版本记录；④ GPL-2.0 文本；⑤ 有效期不少于 3 年的书面要约（若适用）。

## 7. 变更记录

- **2026-11-11**（TASK-LICENSE）：新增 docs/third_party/inventory.yaml 与校验脚本/测试；纠正 FFmpeg 归类（LGPL-2.1+ → **GPL-2.0-or-later**，附 config.h 与 configure 证据）；补齐 K2NX 组件清单（UnRAR/非 SPDX 条款、ffmpeg 3.2.19、opencv、cocos2d-x、libbpg、jxrlib、libiconv、blend2d、LZMA SDK）、字体、构建期/开发期工具与义务；登记 haruno_script 无许可（不可再分发）、jxrlib 未 pin；按四类分组重写本文件。
- **2026-11-11 复核（owner 决策 B）**：FFmpeg 条目固化为「保留 NVDEC + GPL-2.0-or-later 合规分发」，公共仓库不发布 NSP；纠正 libdeflate（P18 接入后 Citron 崩溃已回退 zlib，最终 ELF 无 libdeflate 符号，改记 build-only/未链接）；jxrlib 未 pin 保留 warning。
- 上一版：2026-10（0.1 Preview 收敛前）仅列构建期组件表，且 FFmpeg 许可归类有误。

---
如对某处版权归属有疑问，请开 issue；确认后会立即调整或移除相关内容。
