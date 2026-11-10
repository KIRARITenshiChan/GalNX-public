# M3：自包含 NSP 打包与模拟器验收

- 里程碑：M3（NSP 自包含打包 + 模拟器侧验收）
- 状态：已完成（模拟器级；真机 M3-d 待用户设备接入）
- 日期：2026-10-30

> 分工说明：本文件包含两个章节 —— **NSP 打包链（M3-a 负责，源自 `docs/builds/005-nsp-selfcontained.md`）** 与 **模拟器验收（M3-b 负责）**。打包链细节以 005 为准；模拟器验收细节以本文 §模拟器验收 与 `docs/environment/citron-harness.md` §13 为准。若两处描述冲突，以 Lead 裁决为准。

## 模拟器验收（M3-b 负责）

### 1. 验收结论（正式，模拟器侧）

**Citron nightly `main-0237a9b88` 可以用 `-g <.nsp>` 直接加载自包含 NSP 并运行应用，无需先安装到 NAND；标题栏正确读出 NACP 的 name/version。**

- 对象：`m0-real-build1.nsp`（309,464 B；PFS0 内 3 个 NCA：program 187,392 B + control 117,760 B + cnmt.nca 4,096 B；M3-a 打包链产出；两次构建 sha256 不同为 RSA-PSS 随机盐，Lead 已核实）。
- 结果：`status=loaded`、`elapsed_s=27`、窗口标题 `citron Nightly | 0237a9b88 | m0-hello (64-bit) | 1.0.0 | NVIDIA`、日志 `BootGame: Booting game: 0100000000001000 | m0-hello (64-bit) | 1.0.0`；截图实际画面为应用自身的 `Hello World!`。
- 复现：`m0-real-build2.nsp`（同内容、不同 sha256）同样 `status=loaded`（elapsed 27s，同一 boot 行、同一画面）→ 盐随机不影响加载。
- 机制：Citron（yuzu 血统，`src/citron/main.cpp`）把 `argv.size()==2` 且非 `-` 开头的参数当游戏路径，GameLoader 直接按 NSP 解析；本验收未走「Install files to NAND」，未改 Citron 用户配置，未读/打印密钥内容。
- **证据分级**：E1 = 模拟器实测（result.json + 窗口截图 + Citron 日志切片，见 §2）；E2 = Lead 独立复核（Lead 已独立读取 `M3b-m0-nsp-result.json` 与 `M3b-m0-nsp-boot-window.png` 并确认，2026-10-30）。E1 与 E2 结论一致。
- 措辞：**正式验收（仅模拟器侧）** —— M3-a 打包链报告（`docs/builds/005-nsp-selfcontained.md`）已发布，本结论不再使用 preliminary；真机安装/启动仍属 M3-d，不在本验收范围内。

### 2. 测试对象与证据

| 项目 | 值 |
| --- | --- |
| 被测 NSP（E1/E2） | `/e/galnx-build/m3-tools/out/m0-real-build1.nsp`，309,464 B，sha256 `cb6d061c4dbc60e6c858d51075de38639eb078f03c4328de292dfb9c9aca5be7` |
| 被测 NSP（复现） | `/e/galnx-build/m3-tools/out/m0-real-build2.nsp`，309,464 B，sha256 `818fcc0b6c148a4382d67c8f540b2dfe6d24ffb106ac5d4eefc89917a061db00` |
| 引导方式 | `bash scripts/citron_run.sh --game <nsp> --timeout 120 --settle 20 --expect-title m0-hello --app-log-regex "Booting game:"` |
| Citron | `workspaces/web-02/citron/citron.exe` 23,272,960 B，`citron Development Build | main-0237a9b88`，Windows msvc，Vulkan 后端 |
| 结果 | `status=loaded`、`signals.title_match=true`、`signals.boot_line=true`、`signals.app_output=true`、`screenshot_info.nonblack_ratio=0.1797`（黑底白字，合理） |
| 时间窗 | 02:16:47 首跑（与 M2-c 一次时间重叠，仍成功）；02:17:46 正式 run；02:24 后补测 build2 与 hbl 对照；每轮前后均用 `tasklist` 记录占用 |

证据文件（`docs/milestones/evidence/`，sha256 清单见 `M3b-artifacts-sha256.txt`）：

| 文件 | sha256 | 说明 |
| --- | --- | --- |
| `M3b-m0-nsp-boot-window.png` | `9a7e729e51341e21870174831ae66b0dee605d28861cce8e2fdd494c8034bc92` | 引导成功截图（1728x1016，73,300 B，画面 `Hello World!`） |
| `M3b-m0-nsp-result.json` | `bf0d97ab9f59faa233d57697c7e1502157730d061bc4e7372e6386cbcd85e11f` | 正式 run 结果 JSON（`status=loaded`、`title_match=true`） |
| `M3b-m0-nsp-run.log` | `f83bdee1abe4d1f9a09f7815cbfecad22250de329a6ba0d1adda8dfaf4edc1e8` | harness run.log |
| `M3b-m0-nsp-citron-log-slice.txt` | `f1d7c14ed0bb40a2b49c132408844be2ceb94966135fe4744c069d292340d46c` | Citron 日志切片（`Loading m0-hello ...` / `Booting game: ...`） |
| `M3b-m0-nsp-firstboot-result.json` | `bfed6420ef71d3925fb74d55fd50465d2d20e144751d6bf70ebafd173c11ed57` | 首跑（未传 `--expect-title` → `title_match=false`，属预期） |
| `M3b-m0-build2-result.json` | `866dc63e27cff8055ac35b5d9792c73adb112300c5fa94401f4ed5e1fdeccc86` | build2 复现 run（同样 loaded） |
| `M3b-m0-build2-window.png` | `3dfc1125a2cf7eaefb8a5a93078adc18b9fc1971dbbb61212067358eae5ac180` | build2 画面（73,289 B） |
| `M3b-nro-regression-result.json` | `7d14895ded66f4b9f5b9c90e8d139c18f89ebab81c1e3470449a3bdd68bb95ea` | `--game` 跑 NRO 回归（KAG3 + `--input-click`，无回归） |
| `M3b-hbl-control-load-failed-result.json` | `4954c8de1fad4b90bd9614e082d4b022e22ba4fa66685981cf320e761b7393cb` | hbl 对照：加固后正确 `status=fail` / `load_failed` |
| `M3b-hbl-control-load-failed-window.png` | `8cdbdffc7aa949c94dc62b5f6ec7b8305e34283821b3442ed846cc1dfc744930` | hbl 对照截图（Citron 游戏列表，非应用画面） |
| `M3b-hbl-control-prehardening-result.json` | `76cfb7b296c0629131bdeb6803670e4ceee018f7a55d4ef0b76a177960e4a5d4` | 加固前误判 `status=loaded` 的 false positive 证据（保留说明加固动机） |
| `M3b-hbl-result-citron-already-running.json` | `b18907bc3f0db17673d3f31abb78ecfc571aa3a624ab61c8ae27d73024123a5d` | 被占用时 `status=fail` / `error=citron_already_running` 样例 |

### 3. 标题栏读出 NACP 元数据（旁证）

窗口标题 `citron Nightly | 0237a9b88 | m0-hello (64-bit) | 1.0.0 | NVIDIA` 里同时出现 NACP 的 **name（m0-hello）与 version（1.0.0）**，且 boot 行以 TitleID `0100000000001000` 标识（非 homebrew NRO 的 `0000000000000000` 路径）→ 说明 Citron 走的是「应用包（NSP/NCA/NACP）」加载路径，而不是「homebrew NRO」路径。这是元数据被系统正确读取的旁证，也是判定「这是应用 NSP 而非普通 NRO」的关键证据。

### 4. 对照：hbl.nsp 不能当自包含 NSP 的证据（反例）

- `downloads/hbl.nsp` 40,946 B（nx-hbloader 前端产物）= PFS0 里只有 `main` + `main.npdm` 的 **homebrew 形态**，不是标准 NSP（无 NCA/CNMT/NACP）。
- Citron 用 `-g` 打开它后：日志 `Failed to load ROM (Error 32)!` / `Frontend <Critical> citron\main.cpp:2232:LoadROM: Failed to load ROM! (0007-0020)`，界面回落到 Citron 自己的游戏列表。
- 结论：**「Citron 能打开 PFS0」≠「可运行的应用 NSP」**；hbl.nsp 只能当反例/对照组，不能作为 M3 自包含 NSP 的证据。

### 5. 未签名 NSP：模拟器可运行 ≠ 真机可安装

- Citron 作为模拟器不校验签名/ticket 链（homebrew 友好），所以未签名/自签名 NSP 能直接跑。
- 真机（Switch + Atmosphère）需要 **sigpatches**（或等价的签名补丁环境）+ 正确安装（NAND/SD title）；否则安装/启动会被签名校验拒绝。
- 真机验证不在 M3-b 范围 → 记入 **M3-d**（待用户设备与 CFW 环境）。因此 M3-b 的结论只覆盖「模拟器侧验收」。

### 6. 失败模式（判定口径）

| 现象 | JSON | 判定/处理 |
| --- | --- | --- |
| Citron 已被占用（M2-c 等） | `status=fail`、`error=citron_already_running` | 单实例限制；等 60–120s 重试，不要 `--allow-existing` 抢占（样例：`M3b-hbl-result-citron-already-running.json`） |
| `--expect-title` 不匹配 | `title_match=false`（其余信号可正常） | NSP 标题来自 NACP name，不是文件名 stem：`m0-hello` vs `m0-real-build1` 即此情况（样例：`M3b-m0-nsp-firstboot-result.json`）；显式给 NACP 名即可 |
| 文件不是可运行应用包（如 hbl.nsp） | `status=fail`、`error=load_failed: ... Failed to load ROM! (0007-0020)` | 应用包本身问题，不是脚本误判；换正确 NSP |
| 长时间无 boot 行、进程活着 | `status=timeout`、`error=not_booted` | 文件/密钥问题或直接加载不受支持；查日志与密钥 |

判定口径加固（2026-10-30 02:26，`scripts/citron_run.sh` 39,030 B / 876 行）：非 `nro` 类型不再接受 `citron starting` 宽松 fallback（必须有 `Booting game:`）；出现 `Failed to load ROM` 立即 fail（`load_failed`）；`screenshot_nonblack` 仅在命中 boot 行后才可作为应用输出信号。详见 `docs/environment/citron-harness.md` §13.5。

### 7. 复用与操作要点

1. 单实例：跑前 `tasklist | findstr /i citron`，被占用时等 60–120 s 重试，不要 `--allow-existing` 抢占（Team 内多人共用 Citron）。
2. NSP 窗口标题来自 NACP 应用名（本例 `m0-hello`），不是文件名 → 必须显式 `--expect-title`。
3. 直接加载 NSP 不写 NAND；若后续要验证「安装到 NAND 再启动」路径，需要 Citron GUI（Install files to NAND），M3-b 未做。
4. 参数、JSON 字段、失败码见 `docs/environment/citron-harness.md` §4/§5/§7/§13。

### 8. 限制与待办（M3-b）

- [x] `m0-real-build1.nsp` 直接引导 → loaded（E1+E2）
- [x] `m0-real-build2.nsp` 复现（盐随机不影响加载）
- [x] `downloads/hbl.nsp` 对照组（load_failed 反例）
- [x] 判定口径加固（load_failed / 非 NRO 严格 boot 行）
- [ ] 未测 `.xci/.nsz/.xcz`（脚本已支持类型识别与 stage；合规原因不引入商业内容）
- [ ] 未测「安装到 NAND 再启动」路径（依赖 GUI 操作）
- [ ] 真实游戏 NSP 不做（合规边界）
- [x] 待 M3-a 报告发布后合并打包链章节（已完成：见本文开头的 M3-a 章节），本结论已转为正式验收（模拟器侧）

## NSP 打包链（M3-a 负责）

> 本章为 M3-a 摘要，完整记录见 `docs/builds/005-nsp-selfcontained.md`（19,889 B / 11 节，audit-package 定稿）；证据 `docs/milestones/evidence/M3a-*`。

### A1. 出包链步骤

1. **ELF → NSO**：devkitPro `elf2nso`（94,720 B）把 `.elf` 转为 ExeFS 的 `main`（m0-hello 84,060 B NSO；m1-sdl2 3,836,556 B NSO）。
2. **NPDM**：devkitPro `npdmtool`（106,496 B）按 `examples/nsp/npdm.json` 生成 `main.npdm`（application 类型、64 位、filesystem_access 全开；服务访问 `*`）。
3. **NACP + 图标**：devkitPro `nacptool`（74,240 B）生成 `control.nacp`（name/author/version + TitleID）；图标必须 256x256 JPEG（EXIF=0，否则可能安装卡住），本轮用 libnx 默认图标。
4. **打包**：hacBrewPack v3.05（commit `745b16ecfc9ce055743067d200572204cb2aac6c`，`gcc -O2` 自编译，508,983 B）以 `hacbrewpack --nologo -k <keyset>` 把 `exefs/ + control/ + romfs/` 打成 NSP。
5. **结构校验**：nstool v1.9.2（`--fstree` 看 NSP 层 PFS0、`--part0` 解 Control NCA、`-t cnmt` 看 CNMT、`-x` 做 round-trip 提取比对）。注意 `nstool -y` **只校验 NSP 层 PFS0**，不深入 NCA，必须逐个 NCA 再验。

固化为参数化脚本 `scripts/build_nsp_demo.sh`（三种模式：synthetic keyset 冒烟 / 真实 keyset / 含 RomFS），产物拷到 `OUT/<name>-<tid>.nsp` 并打印 `===EXIT/===ARTIFACTS/===INPUTS/===LOGTAIL`。

### A2. keyset 策略（重要）

- **必须显式 `--keyset <path|synthetic>`**：脚本无默认路径、无自动搜索；也不接受环境变量传递（DSH 会把含 KEY/TOKEN 的环境变量从子进程剔除）。
- 无 keyset → hacBrewPack rc=1（`Unable to open keyset file`）；只有 `header_key` 也失败（`key_area_key_application for keygeneration 1 is not present`）。
- **最小可用 keyset** = `header_key`（32 B / 64 hex）+ `key_area_key_application_00`（16 B / 32 hex，默认 keygen 1）。
- 真实 keys 仅本机离线使用（本轮实际使用 `E:\Othergames\Nintendo Switch\Ryujinx-canary\portable\system\prod.keys`，12,007 B；只记录路径/大小/sha256，不读内容、不复制、不入库）；**prod.keys/title.keys 不入仓库、不入 CI、不入文档**。
- CI 只能跑 synthetic keyset（结构合法但 **NOT INSTALLABLE**，真机无法解密）。

### A3. 非确定性与产物哈希

- **同一输入树、同一 keyset 两次构建：NSP 大小相同（309,464 B）但 SHA-256 不同**。源码依据：`rsa.c` 用 RSA-PSS + ctr_drbg 随机盐对 NCA header 签名（`nca.c:667-670`）。
- Control NCA 因不含随机签名，**跨构建哈希恒定**（`d5bcc2f62e1f6e8852ba230b67179c1353119c8c009ea54f090886d31378230e`）；Program/Meta 每次不同。
- 表述边界：**不承诺 bit 级可复现**。版本锁定记录「源码 commit + 工具版本 + keyset metadata + 产物实例哈希」。
- NSP 内 NCA 的偏移/顺序不固定（real A 与 real R 的 entry 顺序不同）→ 不能按固定偏移识别，应按 CNMT 的 ContentInfo 或 Content Type 识别。

### A4. CNMT / PFS0 结构数字（Lead 已独立复核）

- PFS0 FileNum=3：**Program NCA 187,392 B + Control NCA 117,760 B + cnmt.nca 4,096 B**（合计 309,464 B 之外还有 PFS0 头/填充，NSP 总大小 309,464 B）。
- TitleId `0x0100000000001000`；NCA 头 ContentType = Program/Control/Meta，ProgID 均 `0x0100000000001000`，KeyGen 0，Kaek Index Application(0)。
- Program NCA：partition0 = `main` + `main.npdm`，partition1 = `romfs/hello.txt`（由 ELF 内嵌 romfs 而来）。
- CNMT：TitleId `0x0100000000001000`、Version 0.0.0(v0)、Type Application(128)、PatchId `0x0100000000001800`；ContentInfo 的 Program/Control 哈希与实际 NCA sha256 一致（Lead 独立复核一致）。
- 签名必然 FAIL（`NCA Header Main Signature: FAIL`、`ACID Signature: FAIL`），原因是**没有任天堂私钥**，任何自制工具都无法产生有效签名；真机运行依赖 Atmosphère + sigpatches 跳过签名校验。

### A5. 产物路径与 SHA-256

| 构建 | 路径 | 大小 | SHA-256 |
| --- | --- | ---: | --- |
| **m0 manual build1（交付 M3-b、Citron 已验证）** | `/e/galnx-build/m3-tools/out/m0-real-build1.nsp` | 309,464 B | `cb6d061c4dbc60e6c858d51075de38639eb078f03c4328de292dfb9c9aca5be7` |
| m0 manual build2 | `/e/galnx-build/m3-tools/out/m0-real-build2.nsp` | 309,464 B | `818fcc0b6c148a4382d67c8f540b2dfe6d24ffb106ac5d4eefc89917a061db00` |
| m0 real A（脚本） | `/e/galnx-build/m3-tools/out/script-real-a/` | 309,464 B | `cd7ff7492b5358a64b8ad9097eb547fe9ab79faf64ffda31fb4331c5fb706354` |
| m0 real B（脚本、同输入） | 同上 | 309,464 B | `9a915ef2f41152aef25eee4780db67f5d51e752a2d8594a7c9bf28f557fdfc4d` |
| m0 real + RomFS | `/e/galnx-build/m3-tools/out/script-real-r/` | 309,464 B | `f89f7063d2fa9ba8a51c930f00c0a1993e230e1fbaf4dd0f83cb816ff9baa60f` |
| m1-sdl2 real | `/e/galnx-build/m3-tools/out/` | 4,063,448 B | `6f17a387cf0b045fd40625271b43dc46712b872897f16a8acf9d26945e804128` |
| m0 synthetic（NOT INSTALLABLE） | `/e/galnx-build/m3-tools/out/script-synth/` | 309,464 B | `0441af687061312d19028e0a629664e60b9f8c8a8b008117fda3c75d973be219` |

### A6. 已知限制（转 M3-c 处理）

- **NRO ≠ PFS0**：devkitPro `elf2nro` 产物不是 PFS0 容器（`NRO0` magic 在 0x10，全文件无 `PFS0`/`NSO0`/`NCA0`），不能按「NRO=PFS0」拆 ExeFS；本链走 ELF→NSO，**已有 NRO 直接封装 NSP 尚未实现**。
- **NACP 存档大小默认非 0**：`nacptool` 默认写入 62 MiB save + 1 MiB journal，且无 CLI 选项；需要后处理 NACP 或换工具。
- **版本字段语义**：`nacptool --create ... 1.0.0` 写入 NACP `DisplayVersion` ASCII 字符串，实测读回 `"1.0."`（尾部 NUL 截断）；`AppVersion`(u32)=0、CNMT Version=0.0.0（Citron 标题栏仍显示 `1.0.0`）。显示版本与 AppVersion 是两套字段，M3-c 需分别写入，不能假设 nacptool 已写全。
- **构建日志泄漏风险**：hacBrewPack 会打印 `Key area key 2: <16 B hex>`；脚本必须过滤，raw 日志不落仓库。
- **Windows 路径长度**：hacBrewPack 用 ANSI 路径 API，259 字符上限 → 构建根必须短且无空格（本链 `/e/galnx-build/m3-tools`）。
- **大 RomFS 未验证**：真实 KiriKiri 游戏 2+ GB RomFS 未做量级测试。

### A7. 证据

- `docs/milestones/evidence/M3a-nsp-script-output.txt`：脚本三种模式运行记录、PFS0 entries、m1 构建；
- `docs/milestones/evidence/M3a-nstool-verify.txt`：NSP/NCA/NACP 输出摘录、round-trip、跨 keyset 实验；
- `docs/milestones/evidence/M3a-artifacts-sha256.txt`：工具/输入/产物全量 SHA-256 表 + Lead 复核数字；
- `docs/milestones/evidence/M3a-keyset-requirements.txt`：keyset 三种实验原文、最小 keyset 契约、源码依据。

## M3-e 里程碑汇总（Lead 裁决，2026-10-30）

**状态：M3 完成（仅模拟器级）。** M3-a 出包链、M3-b Citron 直接引导、M3-c 打包数据模型/TitleID/契约校验、M3-e 汇总均已交付；**M3-d 真机安装与 HOME 菜单启动未完成**，待用户 NS1 接入（需 CFW/Atmosphère + sigpatches）。模拟器结论不得替代真机验收。

### 对照计划 §10「M3 验收」

| # | 计划验收条款 | 判定 | 依据 |
| --- | --- | --- | --- |
| 1 | 清楚区分 NRO、forwarder NSP、自包含 NSP | ✅ | `src/galnx/package/metadata.py` 三形态 `PackageType` + `docs/packaging/README.md` §2 对照表 |
| 2 | 自动设置标题、图标、Title ID、版本等元数据 | ◐ 部分 | `PackageMetadata` / `galnx package plan` 已建模并校验四类元数据；实际出包脚本仍手工传参，NACP 版本字段语义未闭环（005 A6）→ 待 M4 接入脚本 |
| 3 | 检查 Title ID 冲突，避免不同游戏意外复用 | ✅ | `titleid.py`（base/update/DLC 区间、系统保留区、冲突检测、GalNX 分配块）+ `registry.py` + `galnx package check` |
| 4 | 真机上验证最终包的安装与 HOME 菜单启动 | ⬜ 未完成 | M3-d：待用户设备；出包脚本与 nstool 校验已就绪，真机需 CFW+sigpatches，属封禁风险 |
| 5 | 用户文档说明 forwarder 的资源路径依赖及封禁/系统环境风险 | ✅ | `docs/packaging/README.md` §2/§11 + `docs/builds/005-nsp-selfcontained.md` 未签名说明 |

### 遗留（按优先级）

1. **M3-d 真机**：用户设备接入后执行安装 / HOME 启动 / 存档隔离 / 卸载重装，证据入 `docs/milestones/evidence/`。
2. **元数据自动化**：把 `PackageMetadata` 映射到 nacptool/npdmtool 参数，补齐 NACP DisplayVersion/AppVersion 双字段（M4 前置）。
3. **图标/存档默认值**：图标仍为 libnx 默认、NACP 默认 62 MiB 存档 → 打包脚本需后处理。
4. **大 RomFS（2+ GB）未验证**；NRO→NSP 直接封装未实现（当前 ELF→NSO 路线）。

### 证据入口

- 打包链：`docs/builds/005-nsp-selfcontained.md`、`scripts/build_nsp_demo.sh`、`docs/milestones/evidence/M3a-*`
- 模拟器验收：本文 §模拟器验收、`M3b-*`、`docs/environment/citron-harness.md` §13
- 数据模型：`docs/packaging/README.md`、`src/galnx/package/`、`tests/test_package_*.py`

