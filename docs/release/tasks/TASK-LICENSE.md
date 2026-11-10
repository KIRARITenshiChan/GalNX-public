# TASK-LICENSE 任务报告：SBOM 与 FFmpeg GPL 审计

## 1. Task ID

TASK-LICENSE（P0-4：许可证与最终交付产物逐项对账 / SBOM），共享任务 task-62。2026-11-11 复核轮落实 owner 决策 B（保留 NVDEC + GPL-2.0-or-later 合规分发）。

## 2. Source commit

基线：974a4141af4a86a83f9434ea69ebb9dc9ffe4834（main，2026-11-11 审计时 HEAD）。
本任务不改 src，只在 docs/third_party、scripts、tests、仓库根 NOTICE 与 docs/release/tasks 下工作。

## 3. Files changed

| 文件 | 状态 | 规模 |
| --- | --- | --- |
| docs/third_party/inventory.yaml | 新增 | 985 行 / 42,308 B，33 个组件 / 4 个产物 |
| scripts/check_license_inventory.py | 新增 | 372 行 / 15,917 B，stdlib+PyYAML，退出码 0/1，支持 --json |
| tests/test_license_inventory.py | 新增 | 320 行 / 12,093 B，24 个 unittest 用例 |
| THIRD_PARTY_NOTICES.md | 重写 | 78 → 108 行 / 11,937 B（复核轮后） |
| docs/third_party/README.md | 修改 | 37 → 43 行，新增「机器可读清单与校验」小节（指向 inventory/checker/NOTICES） |
| docs/release/tasks/TASK-LICENSE.md | 新增 | 本报告 114 行 / 约 12.1 KB（docs/release/ 目录本次新建） |

未改动：src/**、examples/**、README.md、docs/MANIFEST.md、docs/builds/**、任何上游 LICENSE 原文。

## 4. Observed problem

1. **FFmpeg GPL 归类错误（P0）**：旧 THIRD_PARTY_NOTICES.md 第 5 节把随 rfvp 静态链接的 FFmpeg 写成「LGPL-2.1+」。实际构建配置为 GPL：
   - /e/galnx-build/nvdec/ffmpeg-build-nvtegra/config.h 第 4 行 FFMPEG_CONFIGURATION 含 --enable-gpl --enable-nvtegra，同文件 FFMPEG_LICENSE 为 "GPL version 2 or later"；
   - 源码为 averne/FFmpeg nvtegra 分支（commit caeec83b791be08ed43468a2ef426d6901d51c78，2024-10-06）；
   - configure:3156 有 nvtegra_deps="gpl"：**NVDEC 硬解强依赖 GPL，去掉 --enable-gpl 就不能启用 nvtegra**；
   - /e/galnx-build/nvdec/research/ffmpeg-nvtegra/libavcodec/nvtegra_decode.c 文件头为 GPL-2.0-or-later。
   - 因此 rfvp.elf / NSP 整体按 GPL-2.0-or-later 组合作品处理（决策 B）；旧 NOTICES 会误导分发决策。
2. 仓库缺少机器可读 SBOM：许可证信息散落在 README、docs/builds、patches/LICENSE.md、examples/engines/*.yaml 中，无法机器校验，易漂移。
3. K2NX 路线的非 SPDX 组件（KiriKiri BSD-style、UnRAR 限制条款、libbpg 内嵌 HEVC LGPL、haruno_script 无 LICENSE）未在单一清单中对账。
4. 复核纠正一处归类错误：libdeflate.a 曾被当作 runtime-linked 组件，实际 P18 接入后 Citron 崩溃（Cannot execute instruction at unmapped address 0x0）已回退 zlib，最终 rfvp.elf 无 libdeflate 符号（build-only 历史记录）。剩余未闭环风险：jxrlib 版本未 pin（上游 master）。

## 5. Decision made

1. **建立单一事实源**：docs/third_party/inventory.yaml 记录 33 个组件的 id/名称/上游/版本或 commit/许可（SPDX 或 name+url）/链接方式/是否进 NSP/分发类别/补丁路径/义务/证据/备注；4 个产物（iroseka-nsp 1.2.5-test、sakura-nsp 1.3.3-test、k2nx-a10-nsp 1.0.9、m1-kag3-demo）单列并附 sha256/size。
2. **把许可分类写死为可执行规则**：新增 scripts/check_license_inventory.py，校验必填字段、枚举合法性、id 唯一、artifacts 关联、补丁路径存在且为仓库相对 POSIX、禁止个人用户目录路径、included_in_nsp=true 的 copyleft/custom/unknown 组件必须有 obligations；未锁定的版本只告警不阻断。
3. **FFmpeg 按事实归类为 GPL-2.0-or-later；Lead 于 2026-11-11 拍板方案 B**：保留 NVDEC，rfvp/NSP 整体按 GPL-2.0-or-later 组合作品处理。理由：NVDEC 是 Switch 真机 60fps 电影路径的前提（probe9 硬解 decode 0.44 ms；软解会回到 30fps 以下并占满 CPU），方案 A 会推翻已验收的 P40/P44 成果；GPL 义务可控——GalNX 公共仓库只分发 MIT 编排层与上游 MPL/MIT 补丁、**不发布 NSP 二进制**，NSP 由用户本机构建/安装（GPL 组合作品的私有使用），对外分发 NSP 时提供对应源码（rvfp fork + FFmpeg nvtegra 分支 + 构建脚本）即可。方案 A 作为备选记录在案（未采用）。
4. **K2NX 组件全部入清单**：Kirikiroid2-NX 记为 NOASSERTION + KiriKiri BSD-style（附 license_url）；FFmpeg 3.2.19 LGPL、OpenCV BSD-3、cocos2d-x MIT、libiconv LGPL、UnRAR（限制）、libbpg、jxrlib、blend2d、LZMA SDK、DroidSansFallback Apache-2.0、haruno_script 无许可全部落项。
5. **不重建 FFmpeg、不重新打包、不安装任何软件**：所有结论来自只读抓取与现有构建记录；方案 A 的 LGPL 重建步骤仅作备选记录（见第 12 节末）。
6. THIRD_PARTY_NOTICES.md 重写为「分发边界与合规结论 → 四类分组清单 → 许可文本位置与源码获取方式」，并指向 inventory.yaml。

## 6. Behavior before

- 无 SBOM，无校验脚本/测试；许可信息口径不一，FFmpeg 被标为 LGPL-2.1+。
- NOTICES 只有零散表格与 3 条分发义务，未说明 GPL 组合作品问题。
- K2NX 非 SPDX 组件与 UnRAR 再分发限制只出现在 patches/LICENSE 与上游 THIRD_PARTY_LICENSES，未进入仓库级声明。
- 无法在 CI/发布前自动发现「GPL 组件缺义务」或「补丁路径失效」。

## 7. Behavior after

- 仓库有机器可读清单与校验器：
  - python scripts/check_license_inventory.py（默认仓库清单）→ 退出 0；
  - python scripts/check_license_inventory.py --json → 输出 ok/components/artifacts/errors/warnings，便于 CI/Lead 脚本消费；
  - 对仓库清单实测：ok=true，components=33，artifacts=4，errors=[]，warnings=2（jxrlib 未 pin、haruno-script 未 pin）。
- 复核轮按决策 B 更新 inventory/NOTICES：ffmpeg-nvtegra 的 notes 固化决策 B 与分发边界（公共仓库不发布 NSP，分发 NSP 时提供源码+构建脚本），obligations 增 provide_build_scripts；libdeflate 改为 link_mode=none / build-only / included_in_nsp=false（P18 回退 zlib，最终 ELF 无其符号）；NOTICES §0 由「方案 A/B 待拍板」改为「已拍板方案 B」。
- 新增 24 个测试覆盖：仓库清单通过、最小合法清单通过、缺字段、非法枚举、重复 id、GPL included 缺 obligations、included 缺 artifacts、未知 artifact、补丁缺失/绝对路径/穿越、NOASSERTION 缺 name+url、local evidence 含个人目录、repo evidence 路径不存在、日期/commit 格式、缺失清单文件、未锁定版本告警。
- THIRD_PARTY_NOTICES.md 明确：FFmpeg = GPL-2.0-or-later（含 config.h/configure 证据要点）与决策 B（保留 NVDEC、公共仓库不发布 NSP、分发 NSP 时提供源码+构建脚本）；libdeflate 未链接（P18 已回退 zlib）；K2NX UnRAR 限制与 haruno_script 不可再分发；build-only 与 development-only 工具不进入产物。

## 8. Tests added

tests/test_license_inventory.py（unittest 风格，可被 pytest 收集），24 个用例：
- RepositoryInventoryTest：清单存在；仓库清单通过（--json）；FFmpeg 必须为 GPL-2.0-or-later 且带义务；K2NX 必须 NOASSERTION + name/url。
- ValidationRulesTest：最小合法 fixture 通过；human 输出 OK；缺 upstream 失败；非法 license_family 失败；重复 id 失败；GPL included 缺 obligations 失败；GPL included 带 obligations 通过；included 缺 artifacts 失败；未知 artifact 失败；补丁缺失失败；补丁存在通过；绝对路径补丁失败；.. 穿越失败；NOASSERTION 缺 name/url 失败；NOASSERTION 齐全通过；local evidence 含 /home 失败；repo evidence 缺失失败；generated_at 非法失败；baseline_commit 非法失败；清单文件缺失失败；未 pin 版本产生 warning 而非 error。

## 9. Commands executed

在仓库根 E:/Othergames/Nintendo Switch/Workspace/GalNX：

    PYTHONPATH=src python scripts/check_license_inventory.py --json
    PYTHONPATH=src python -m pytest -q tests/test_license_inventory.py

取证命令（只读，不重复执行于本报告）：
- 读取 /e/galnx-build/nvdec/ffmpeg-build-nvtegra/config.h、/e/galnx-build/nvdec/research/ffmpeg-nvtegra/configure（grep nvtegra_deps）；
- aarch64-none-elf-nm / strings 分析 /e/galnx-build/p40/rfvp/target/rfvp-switch-runtime/rfvp.elf；
- 读取 docs/builds/046/052、docs/pilot/P1-engine-k2nx.md、examples/engines/*.yaml、docs/builds/patches/LICENSE.md；
- 读取 D:/devkitPro/msys2/var/lib/pacman/local/ 下包元数据；pacman -Qo 查 libdeflate（No package owns）；
- GitHub API 查询 t-satoru-Studio/haruno_script（license=null）。

## 10. Test results

- python scripts/check_license_inventory.py --json → rc=0，ok=true，components=33，artifacts=4，errors=[]，warnings=2（jxrlib/haruno-script 未 pin）。
- python -m pytest -q tests/test_license_inventory.py → 24 passed（2026-11-11 复核轮重跑，4.25 s，本机 Python 3.12.10 / PyYAML 6.0.3）。
- 未运行全量 pytest（并行任务正在改 src/，全量结果会混入他人改动；本任务只跑自身子集）。

## 11. Unverified assumptions

1. nvtegra 分支基于 FFmpeg 7.1 的依据是分支 commit message（"nvtegra/filter: update for ffmpeg 7.1"）与构建记录，未做逐提交 diff。
2. build_switch.sh 链接的 ffmpeg 三库确实来自 /e/galnx-build/nvdec/ffmpeg-build-nvtegra（elf strings 中出现该路径、同目录 config.h 为 GPL 配置），但未对 .a 做哈希级比对。
3. K2NX A10 NSP 的内部组成依赖上游 THIRD_PARTY_LICENSES 与构建脚本记录，未对 NSP 二进制重新做链接成分取证（本任务未启动 nstool/Citron）。
4. libdeflate 经复核确认未进入最终构建（P18 回退 zlib；ELF 中 libdeflate 符号 0 个，rfvp.map 中 zlib 引用 109 处）；其 .a（1.24，16,652 B，mtime 2026-11-01）仍不在 pacman 包管理内，仅作 build-only 历史记录，provenance 不影响产物。
5. jxrlib 上游 master 未 pin；haruno_script 无 LICENSE 的判断来自 GitHub API 当时快照。
6. 义务措辞是工程合规清单，非法律意见；MPL-2.0 与 GPL-2.0-or-later 的组合作品兼容性未断言。

## 12. Known limitations 与后续动作（均未执行）

- inventory 只覆盖本仓库记录到的组件，不等于完整 SBOM（如 devkitPro 包内二次捆绑的 zlib/libpng 等未逐个展开）。
- SDL2 许可采用上游 zlib，但 devkitPro 包元数据写 LGPL：清单在 notes 中标注差异，未改包元数据。
- 未新增许可证全文文件（只引用既有路径与 URL）；如需对外分发，应把 GPL/LGPL/UnRAR 全文随发布包附带。
- 产物 sha256 来自 docs/builds/052 与 p46 输出目录记录（大小一致），本任务未重新哈希 10 GB 级 NSP。
- 建议后续动作（不执行）：
  1) 方案 A/B 已由 owner 拍板为 B；方案 A 仅作备选记录（不执行）。若未来回退 A，需核对 devkitPro switch-ffmpeg 的 configure（应无 --enable-gpl）并在 rfvp 侧切回软解。
  2) 若将来对外分发 NSP：准备 GPL 合规材料（固定 nvtegra commit caeec83b、上游 FFmpeg 7.1 源码、rvfp 修改 diff、build_switch.sh 与工具链版本记录、GPL-2.0 全文、书面要约）；并请法务评估 MPL-2.0 + GPL 组合。
  3) 已确认 libdeflate 不进入构建；可清理 build_switch.sh 链接行残留的 -ldeflate（不影响产物，本轮未改构建）；把 jxrlib 固定到 commit；确认 K2NX CN 内容只自用。
  4) 把 check_license_inventory.py 接入发布前检查由 Lead 负责（Lead 已确认接入 release gate；本任务不改）。

## Rollback method

- 恢复 NOTICES：git restore THIRD_PARTY_NOTICES.md（或 git checkout -- THIRD_PARTY_NOTICES.md）。
- 删除本任务新增文件：docs/third_party/inventory.yaml、scripts/check_license_inventory.py、tests/test_license_inventory.py、docs/release/tasks/TASK-LICENSE.md（docs/release/ 若为空一并删除）。
- 无 src/行为变更，无需回滚代码或重建产物。
