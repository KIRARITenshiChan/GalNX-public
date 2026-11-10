# 005 — 自包含 NSP 打包链（M3-a）

| 项 | 值 |
| --- | --- |
| 编号 | 005 |
| 对象 | GalNX 自包含 NSP（hacBrewPack 打包链 + nstool 结构校验） |
| 任务 | task-19（M3-a：NSP 自包含链路打通） |
| 执行 | audit-package |
| 构建时间 | 2026-10-30T02:05–02:18+08:00（工具构建 + 4 次 NSP 构建） |
| 工程目录 | `Workspace/GalNX/scripts/build_nsp_demo.sh`、`Workspace/GalNX/examples/nsp/` |
| 构建根目录 | `/e/galnx-build/m3-tools`（无空格路径） |
| 结果 | **打包链与结构校验通过**；真机安装/启动未验证（权威运行验证由 M3-b 的 Citron 承担，见 `docs/milestones/M3-nsp.md`） |

## 1. 目标

验证 GalNX M3 阶段「自包含 NSP」链路的最小闭环：

1. 用 devkitPro 工具把已有 ELF 变成 NSP 所需的三类内容：`exefs/main`（NRO/NSO）、`main.npdm`、`control.nacp` + 图标；
2. 用 hacBrewPack v3.05 打出 NSP，并回答计划中的关键问题：**hacBrewPack 是否需要 prod.keys**；
3. 用 nstool v1.9.2 在 NSP 层与 NCA 层做只读结构校验（含 Extract round-trip）；
4. 记录构建的非确定性（同输入两次构建 SHA-256 是否相同）与原因；
5. 把上述流程固化为参数化脚本 `scripts/build_nsp_demo.sh`，供 M3-c/M3 后续复用（不触碰 `scripts/citron_run.sh`）。

## 2. 结论摘要

1. **链路打通**：m0-hello（84,060 B NSO）→ `m0-hello-0100000000001000.nsp` 309,464 B；m1-sdl2（3,836,556 B NSO）→ `m1-sdl2-0100000000001001.nsp` 4,063,448 B。
2. **必须 keyset**：无 keyset 时 hacBrewPack rc=1 直接失败；最小可用 keyset = `header_key`（32 B / 64 hex）+ `key_area_key_application`（16 B / 32 hex，默认 keygen 1 时取 `_00`）。合成假 keyset 可产出结构合法 NSP，但**真机无法解密，NOT INSTALLABLE**。
3. **结构校验通过**：nstool NCA 层 exit 0，Program/Control/Meta 三个 NCA 的 header 字段正确、ProgID 一致；`nstool -x` 提取结果与暂存输入逐字节一致（round-trip）。
4. **签名必然 FAIL（预期）**：`NCA Header Main Signature: FAIL`、`ACID Signature: FAIL`——没有任天堂私钥，任何自制工具都无法产生有效签名；真机运行依赖 Atmosphère/sigpatches 跳过签名校验。
5. **非确定性已证实**：同一输入树、同一 keyset 两次构建，NSP 大小相同（309,464 B）但 SHA-256 不同；源码依据是 `rsa.c` 用 RSA-PSS + ctr_drbg 随机盐对 NCA header 签名（`nca.c:667-670`）。Control NCA 因不含随机签名，跨构建哈希恒定。
6. **NSP 内不含 ticket/cert**：PFS0 仅 3 个文件（cnmt + program + control），属 homebrew NSP 形态；`nstool -y` 只校验 NSP 层 PFS0 结构，**不深入校验 NCA**，必须逐个 NCA 再验。
7. **已知产物限制（记录待 M3-c 处理）**：`nacptool` 默认写入 62 MiB 存档 + 1 MiB journal（非 0）；`nacptool --create name author version` 把版本串写入 NACP 的 `DisplayVersion`（ASCII 字符串字段），实测传入 `1.0.0` 后读回为 `"1.0."`（4 字节，尾部 NUL 截断），而 `AppVersion`（u32）=0（v0）、CNMT Version=0.0.0；Citron 标题栏显示 `1.0.0`。**显示版本与 AppVersion 是两套字段**，M3-c 需分别明确写入值（不能假设 nacptool 已写全）。
8. **环境限制**：DSH 会把名字含 `KEY/PASSWORD/SECRET/TOKEN` 的环境变量从子进程环境剔除，因此不能用 `GALNX_PROD_KEYS` 之类环境变量传 keyset；脚本改为**只接受显式 `--keyset <path|synthetic>`**，绝不内置默认路径、绝不自动搜索。

## 3. 环境（实测）

| 组件 | 版本 / 来源 | 证据 |
| --- | --- | --- |
| 宿主 | Windows NT 10.0.26100 x64（16 核） | `uname` 行 |
| bash | GNU bash 5.3.15（`/d/Scoop/apps/git/current/bin/bash.exe`） | `bash --version` |
| gcc（构建 hacBrewPack） | 16.2.0（x86_64-posix-seh-rev1，MinGW-Builds） | `gcc --version` |
| make | GNU Make 4.4.1（devkitPro msys2） | `make --version` |
| devkitPro | `D:\devkitPro`；`tools/bin` 内 elf2nso/npdmtool/nacptool 均 2024-10-23 23:42:13 | `ls -l` |
| elf2nso.exe | 94,720 B，sha256 `d41476f5…94d99f` | `sha256sum` |
| npdmtool.exe | 106,496 B，sha256 `7fbce929…c8fde` | `sha256sum` |
| nacptool.exe | 74,240 B，sha256 `d899dd37…a034` | `sha256sum` |
| libnx default_icon.jpg | 6,285 B，256x256 JPEG RGB，EXIF=0 | PIL 读取 |
| hacBrewPack | v3.05 / commit `745b16ecfc9ce055743067d200572204cb2aac6c`；源码 zip sha256 `77d7c659…e601`；自编译 `hacbrewpack.exe` 508,983 B sha256 `5623fd2b…2c7b` | `sha256sum` / `--version` 输出 |
| nstool | v1.9.2（`Built: 01:34:03 Oct 14 2024`）；release zip sha256 `34659dc4…9374`；解压 exe 1,050,112 B sha256 `84464819…6b6ca9` | banner + `sha256sum` |
| nx-hbloader（NPDM 模板参考） | v2.4.5 / `82b95122…`；源 zip sha256 `98a59fb2…fa68` | 下载记录 |

hacBrewPack 构建：`cp config.mk.template config.mk`（`CC=gcc`、`CFLAGS=-O2 -Wall -Wextra -pedantic -std=gnu11 -fPIC`、`LDFLAGS=-lmbedtls -lmbedx509 -lmbedcrypto`）→ `make -j8`，rc=0（mbedtls 先构建，随后编译 15 个 .o）；警告仅 `utils.h:41-42 fseeko64/ftello64 redeclared without dllimport`。

## 4. 输入契约与关键发现

### 4.1 NRO ≠ PFS0（重要）

devkitPro `elf2nro` 产出的 `.nro`（m0 166,085 B / m1 6,740,165 B）并不是 PFS0 容器：前 16 字节为 `20 00 00 14 f0 00 00 00` + ASCII `HOMEBREW`，`NRO0` magic 在 0x10；全文件搜索无 `PFS0`/`NSO0`/`NCA0` magic，nstool 从其中解析出 NRO 头、Program Sections 与内嵌 `[ApplicationControlProperty]`。**因此不能按「NRO=PFS0」拆 ExeFS**；本链改走「ELF → elf2nso → exefs/main」路线，已验证成功。

### 4.2 hacBrewPack 期望的输入树

```
<work>/
  exefs/
    main              # NSO（elf2nso 产物）
    main.npdm         # npdmtool 产物
  control/
    control.nacp      # nacptool 产物（含图标元数据；TitleID 一致）
    icon_AmericanEnglish.dat   # 必须 256x256 JPEG（EXIF 可能导致占位/安装卡住）
  romfs/              # 可选（自包含游戏数据）
  logo/               # 可选；NintendoLogo.png + StartupMovie.gif，无授权，本链用 --nologo 跳过
```

TitleID 约定：小写 `0x0100000000000000`–`0x0fffffffffffffff`（本链测试用 `0100000000001000`/`0100000000001001`；建议不超过 `0x01ffffffffffffff` 以免与系统 title 冲突）。

### 4.3 NPDM 模板（`examples/nsp/npdm.json`）

- 来源：`nx-hbloader` 的 `hbl.json`（ISC）与 hacBrewPack `template/npdm.json`（GPL-2.0）的结构，取 `application_type=1`、`is_64_bit=true`、`address_space_type=1`、`filesystem_access.permissions=0xFFFFFFFFFFFFFFFF`、`service_host/service_access=["*"]`、`kernel_capabilities`（含 kernel_flags 与 syscall 表）；
- **坑**：devkitPro 2024 版 `npdmtool` 拒绝 `debug_flags` 中多个 true 并存——若同时设 allow_debug/force_debug/force_debug_prod 会报 `Only one of allow_debug, force_debug, or force_debug_prod can be set!` + `Failed to parse descriptor json!`；模板改为 `allow_debug=true, force_debug=false, force_debug_prod=false` 后 rc=0（仍对缺失可选字段打 11 条警告，不影响产物）。
- `title_id` 与 `title_id_range_min/max` 由脚本按 `--title-id` 注入，不手工编辑。

## 5. 关键步骤与命令

### 5.1 构建 hacBrewPack（一次性）

```bash
cd /e/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c
cp config.mk.template config.mk
make -j8            # rc=0 -> ./hacbrewpack.exe
```

### 5.2 脚本用法（三种模式）

```bash
# A) 合成 keyset 冒烟（离线/CI 可用；NOT INSTALLABLE）
./scripts/build_nsp_demo.sh \
  --elf /e/galnx-build/m0-hello/m0-hello.elf \
  --title-id 0100000000001000 --name m0-hello --author GalNX --version 1.0.0 \
  --keyset synthetic \
  --hacbrewpack /e/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c/hacbrewpack.exe \
  --nstool /e/galnx-build/m3-tools/nstool.exe \
  --out /e/galnx-build/m3-tools/out/script-synth --work /e/galnx-build/m3-tools/script-work-synth

# B) 真实 keyset（本机离线；脚本只做显式参数，无默认路径、无自动搜索）
./scripts/build_nsp_demo.sh \
  --elf /e/galnx-build/m0-hello/m0-hello.elf \
  --title-id 0100000000001000 --name m0-hello --author GalNX --version 1.0.0 \
  --keyset "/e/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys" \
  --hacbrewpack .../hacbrewpack.exe --nstool /e/galnx-build/m3-tools/nstool.exe \
  --out /e/galnx-build/m3-tools/out/script-real-a --work /e/galnx-build/m3-tools/script-work-real-a

# C) 含 RomFS（自包含数据）
./scripts/build_nsp_demo.sh ... --romfs /e/galnx-build/m3-tools/romfs-fixture \
  --out /e/galnx-build/m3-tools/out/script-real-r --work /e/galnx-build/m3-tools/script-work-real-r
```

脚本内部 5 步：`elf2nso` → `npdmtool` → `nacptool` + 拷贝图标 → `hacbrewpack --nologo -k <keyset>` → 可选 `nstool` 结构检查；产物拷到 `OUT/<name>-<tid>.nsp`，打印 `===EXIT` / `===ARTIFACTS`（大小 + SHA-256）/ `===INPUTS` / `===LOGTAIL`。hacBrewPack 的原始日志先落盘，再用 `grep -v "Key area key"` 生成 `hacbrewpack.log` 并删除 raw，避免把 16 B derived key area key 写进仓库/日志。

### 5.3 nstool 复核命令（Lead 复核用法）

```bash
# NSP 层：只看 PFS0（不校验 NCA）
nstool -k <prod.keys> --fstree <nsp>
# Control NCA：partition0 解出 control.nacp + icon
nstool -k <prod.keys> --part0 <dir> <control.nca>
# CNMT：标题/版本/类型与内容哈希
nstool -t cnmt <cnmt.nca>
```

## 6. 日志摘要与证据

### 6.1 产物 NSP

| 构建 | 大小 | SHA-256 |
| --- | ---: | --- |
| m0 synthetic（NOT INSTALLABLE） | 309,464 B | `0441af687061312d19028e0a629664e60b9f8c8a8b008117fda3c75d973be219` |
| m0 real A | 309,464 B | `cd7ff7492b5358a64b8ad9097eb547fe9ab79faf64ffda31fb4331c5fb706354` |
| m0 real B（同输入） | 309,464 B | `9a915ef2f41152aef25eee4780db67f5d51e752a2d8594a7c9bf28f557fdfc4d` |
| m0 real + RomFS | 309,464 B | `f89f7063d2fa9ba8a51c930f00c0a1993e230e1fbaf4dd0f83cb816ff9baa60f` |
| m1-sdl2 real | 4,063,448 B | `6f17a387cf0b045fd40625271b43dc46712b872897f16a8acf9d26945e804128` |
| 手工 build1 / build2（更早） | 各 309,464 B | `cb6d061c4dbc60e6c858d51075de38639eb078f03c4328de292dfb9c9aca5be7` / `818fcc0b6c148a4382d67c8f540b2dfe6d24ffb106ac5d4eefc89917a061db00` |

**最终交付给 M3-b 的产物 = 手工 `build1`**：`/e/galnx-build/m3-tools/out/m0-real-build1.nsp`，309,464 B，sha256 `cb6d061c4dbc60e6c858d51075de38639eb078f03c4328de292dfb9c9aca5be7`（Citron 已成功加载，见 `docs/milestones/M3-nsp.md` M3-b 章节）。

### 6.2 PFS0 内部布局（两次构建 entry 顺序不同）

| 构建 | 顺序 | 文件名 | offset | size | SHA-256 |
| --- | --- | --- | ---: | ---: | --- |
| real A | 1 | `5464a5d0….cnmt.nca` | 0x0 | 4,096 | `5464a5d000b2dbace943b597d6ec695925b08b24622a05a9b33372767a1ae01b` |
| real A | 2 | `c19149fb….nca`（Program） | 0x1000 | 187,392 | `c19149fbb0d815c1515799e945f82831ca5fe1239083fab0c85bb9aed5383986` |
| real A | 3 | `d5bcc2f6….nca`（Control） | 0x2ec00 | 117,760 | `d5bcc2f62e1f6e8852ba230b67179c1353119c8c009ea54f090886d31378230e` |
| real R | 1 | `3528a1de….nca`（Program） | 0x0 | 187,392 | `3528a1deaa977a1f681d18363d93702d58427168a6bb5338246dad413bc1809d` |
| real R | 2 | `77fad853….cnmt.nca` | 0x2dc00 | 4,096 | `77fad85376ac8fcfbcea55dedf8cae23e0019db17223c48c4cdb87c03bb3817a` |
| real R | 3 | `d5bcc2f6….nca`（Control） | 0x2ec00 | 117,760 | `d5bcc2f62e1f6e8852ba230b67179c1353119c8c009ea54f090886d31378230e` |

结论：不能依赖 NSP 内 NCA 的固定偏移/固定顺序，应按 cnmt 的 ContentInfo 或 Content Type 识别；Control NCA 哈希跨构建恒定，Program/Meta 因 RSA-PSS 随机盐每次不同。

### 6.3 nstool 结构校验（摘录；完整输出见 `docs/milestones/evidence/M3a-nstool-verify.txt`）

```
NSP 层: [PartitionFs] Type: PFS0 FileNum: 3        exit=0（只列 PFS0，不校验 NCA）
NCA Program: Content Type: Program / Size 0x2dc00 / ProgID 0x0100000000001000 / NCA3 / Download
             [WARNING] NCA Header Main Signature: FAIL
             [WARNING] ACID Signature: FAIL (Failed to verify Access Control Info Desc)
NCA Control: Content Type: Control / Size 0x1cc00
NCA Meta:    Content Type: Meta / Size 0x1000
全部 exit=0（结构可解析；签名 FAIL 为预期）
```

`nstool -x` 提取 Program NCA 得 `0/main`、`0/main.npdm`、`1/hello.txt`；提取 Control NCA 得 `0/control.nacp`、`0/icon_AmericanEnglish.dat`；与暂存输入 SHA-256 全部一致（round-trip 通过）。

### 6.4 Lead 独立复核（2026-10-30，`/e/galnx-build/lead-verify/VERIFICATION-M3a-nsp.md`）

- PFS0 FileNum=3：program 187,392 B / control 117,760 B / cnmt.nca 4,096 B；NCA 头 Content Type 为 Program/Control/Meta，ProgID 均 `0x0100000000001000`，KeyGen 0，Kaek Index Application(0)；
- Program NCA：partition0 = `main` + `main.npdm`，partition1 = `romfs/hello.txt`；
- CNMT：TitleId `0x0100000000001000`、Version 0.0.0(v0)、Type Application(128)，ContentInfo 的 Program/Control 哈希与实际 NCA sha256 一致（内部一致性 OK）；ApplicationExtendedHeader PatchId `0x0100000000001800`；
- `control.nacp`：name=`m0-hello`、publisher=`GalNX`、`startup_user_account=0`；`DisplayVersion` 为 ASCII 字符串 `"1.0."`（Citron 标题栏显示 `1.0.0`）；`AppVersion`(u32)=0（v0），CNMT Version=0.0.0（见 §2 第 7 条）；
- icon 6,285 B JPEG RGB 256x256 ✓（当前为 libnx 默认图标，非自制）；
- NSP 内无 ticket/cert（homebrew NSP 形态）。

### 6.5 证据清单（E1/E3 已入库）

| 文件 | 内容 |
| --- | --- |
| `docs/milestones/evidence/M3a-nsp-script-output.txt` | 脚本三种模式运行记录、PFS0 entries、m1 构建 |
| `docs/milestones/evidence/M3a-nstool-verify.txt` | NSP/NCA/NACP 输出摘录、round-trip、跨 keyset 实验 |
| `docs/milestones/evidence/M3a-artifacts-sha256.txt` | 工具/输入/产物全量 SHA-256 表 + Lead 复核数字 |
| `docs/milestones/evidence/M3a-keyset-requirements.txt` | keyset 三种实验原文、最小 keyset 契约、源码依据 |

### 6.6 模拟器侧验证（Citron，M3-b 联合）

M3-b（audit-web）用 Citron `0237a9b88` 直接 `citron.exe -g /e/galnx-build/m3-tools/out/m0-real-build1.nsp` 引导成功（`status=loaded`、`elapsed_s=27`）：窗口标题 `citron Nightly | 0237a9b88 | m0-hello (64-bit) | 1.0.0 | NVIDIA`，日志 boot line `BootGame: Booting game: 0100000000001000 | m0-hello (64-bit) | 1.0.0`，截图显示应用自身 `Hello World!` 画面。

结论：结构合法、内容一致（ExeFS + control + cnmt）的自包含 NSP 在模拟器侧可加载并运行；未签名包 Citron 接受。**这不等于真机可安装/启动**——真机仍需 Atmosphère + sigpatches（见 §8 风险 1）。证据文件见 `docs/milestones/evidence/`（M3b-*，由 M3-b 负责）。

## 7. 失败点与坑（按影响排序）

1. **无 keyset 不可用**：`Error: Unable to open keyset file` / `Use -k or --keyset to specify ...`，rc=1；只有 header_key 时 `Error: key_area_key_application for keygeneration 1 is not present in keyset file`，rc=1。
2. **devkitPro npdmtool 的 debug_flags 坑**：多个 `true` 并存直接失败（原文见 §4.3）；模板只置 `allow_debug=true`。
3. **`DEVKITPRO` 环境变量在本机为 `/opt/devkitpro`（MSYS 视角路径，Windows 宿主不存在）**：脚本最初因此 die；改为按 `GALNX_DEVKITPRO` → `DEVKITPRO` → `/d/devkitPro` → `D:/devkitPro` → `/opt/devkitpro` 顺序找第一个存在的目录。
4. **nstool `-y` 只验 NSP 层**：要验内容必须逐个 NCA；且 NCA 头解密需要与构建一致的 header_key（不匹配时报 `Input file type was undetermined.`，exit=1）。
5. **构建日志泄漏风险**：hacBrewPack 会打印 `Key area key 2: <16 B hex>`（`--keyareakey` 默认值，非 prod.keys 派生）；脚本必须过滤，且 raw 日志不落仓库。
6. **NACP 存盘大小默认非 0**：nacptool 默认 62 MiB + 1 MiB journal，且无 CLI 选项；M3-c 若要精确控制存档大小，需要后处理 NACP 或换工具。
7. **版本字段语义**：`nacptool --create ... 1.0.0` 写入 NACP `DisplayVersion` ASCII 字符串，实测读回 `"1.0."`（尾部截断）；`AppVersion`(u32)=0、CNMT Version=0.0.0；Citron 标题栏显示 `1.0.0`。显示版本与 AppVersion 分离，M3-c 需分别写入，不能依赖 nacptool 呈现完整三段版本。
8. **Windows 路径长度**：hacBrewPack 使用 ANSI 路径 API，259 字符上限（Carafe 文档实测 260 失败，`Failed to stat`）；构建根必须短且无空格（本链使用 `/e/galnx-build/m3-tools`）。

## 8. 未验证 / 剩余风险

| # | 项 | 影响 | 后续 |
| --- | --- | --- | --- |
| 1 | 真机安装/启动 | 未验证（仅 Citron 模拟器验证，见 M3-b） | 需 Atmosphère + sigpatches 真机；安装方式另测 |
| 2 | 图标/名称/发布者 | 当前 libnx 默认图标；名称 `m0-hello` 仅占位 | M3-c 换自制图标（256x256 JPEG、EXIF=0），接入真实游戏元数据 |
| 3 | NACP 存档大小/版本字段 | 默认 62 MiB；DisplayVersion `"1.0."`、AppVersion=0 | M3-c 契约层处理（NACP 后处理或换工具） |
| 4 | TitleID 冲突检查 | 未实现（当前手工指定测试值） | M3-c 打包数据模型 + 冲突检查 |
| 5 | RomFS 大文件（真实 KiriKiri 游戏，2+ GB） | 未验证 hacBrewPack 大 RomFS 性能/路径限制 | M3 后续用合法 fixture 放大量级测试 |
| 6 | keyset 供应链合规 | 真实 keys 仅本机离线；CI 无 keys | CI 只跑 synthetic 冒烟（NOT INSTALLABLE）；prod.keys 不入库/不入 CI/不入文档 |
| 7 | 非确定性 | 每次构建 SHA-256 不同 | 版本锁定记录「源码 commit + 工具版本 + keyset metadata + 产物实例哈希」，不承诺 bit 级可复现 |
| 8 | NRO 直出 NSP | 当前只能 ELF→NSO→NSP；未做「已有 NRO 直接封装」 | 若 M3 需要打包第三方 NRO，需单独实现 NRO→ExeFS 转换（NRO 非 PFS0，见 §4.1） |

## 9. 本机 keyset 位置（仅路径/大小，不含内容）

| 路径 | 大小 | 说明 |
| --- | ---: | --- |
| `E:\Othergames\Nintendo Switch\Ryujinx-canary\portable\system\prod.keys` | 12,007 B | 本任务实际使用（mtime 2026-03-19 07:25:45 +0800） |
| 同目录 `title.keys` | 11,492 B | 未使用 |
| `%APPDATA%\citron\keys\prod.keys` | 12,007 B | Citron 自带；本轮未使用 |
| `C:\Users\<user>\.switch\prod.keys` | — | **不存在**（原计划首选路径，实测缺失） |

脚本只接受显式 `--keyset <path>`，只记录 path/size/sha256/mtime 元数据，不读取、不复制、不打印 key 内容。

## 10. 复现步骤

1. 准备工具：按 §5.1 构建 hacBrewPack；解压 nstool v1.9.2 win_x64 到 `/e/galnx-build/m3-tools/nstool.exe`；确认 devkitPro `tools/bin` 可用。
2. 准备 ELF：使用 M0/M1 产物（`/e/galnx-build/m0-hello/m0-hello.elf` 或 `/e/galnx-build/m1-sdl2/m1-sdl2.elf`）。
3. 跑 synthetic 冒烟（无需真实 keys）：命令见 §5.2 A，期望 rc=0、NSP 约 309 KB、`nstool` NSP 层 exit 0。
4. 跑真实 keyset（本机离线）：命令见 §5.2 B，期望 rc=0；两次构建 SHA-256 不同属正常。
5. 校验：按 §5.3 用 nstool 做 NSP/NCA/CNMT 三层只读检查；提取物与暂存输入比对 SHA-256。

## 11. 引用

- v0.3 审计：`docs/audit/03-packaging-testing.md`（hacBrewPack 契约、nstool 能力、NTON 风险）
- 计划：`docs/PLAN_DRAFT_v0.3.md`（NSP 首个目标 = 自包含包；hacBrewPack 子进程 + nstool 校验）
- M3 里程碑：`docs/milestones/M3-nsp.md`
- 证据：`docs/milestones/evidence/M3a-*.txt`
- 脚本：`scripts/build_nsp_demo.sh`；NPDM 模板：`examples/nsp/`