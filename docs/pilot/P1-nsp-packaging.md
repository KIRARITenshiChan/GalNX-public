# P1-d：NSP 自包含打包可行性与原型（只读审计 + 原型脚本）

- 任务：task-35（P1-d，试点垂直切片）
- 日期：2026-10-30（Asia/Shanghai）
- 作者：audit-package
- 写权限：本文档 + `scripts/build_pilot_nsp.sh`（其余一律只读）
- 边界：游戏原件 `E:/Othergames/Galgame/` 只读；未启动 Citron（单实例本轮归 P1-a）；未在真机运行；未读取/打印/复制任何 keys 内容（只经显式 `--keyset` 路径传入并记录文件元数据）；未 git add/commit/push
- 证据分级沿用 `docs/milestones/README.md`：E1 运行日志 / E2 截图 / E3 哈希或结构元数据 / E4 源码或文件内容片段；无法取证标注 **not-verified**

---

## 0. 结论摘要

| # | 结论 | 证据 |
| --- | --- | --- |
| 1 | **NRO → NSP 打包链路已打通**：预编译 NRO 无需源码即可出结构合法的自包含 NSP。路径 = NRO 段提取 → 合成 ELF → devkitPro `elf2nso` → exefs/main；ASET 内 icon/NACP 直接复用；内嵌 RomFS 解包后重打包。m0-hello（166 KB）、m1-sdl2（6.7 MB）、Kirikiroid2-NX（42.3 MB）三例全部出包且 nstool 结构校验通过。 | E1+E3 |
| 2 | **大 RomFS 可行**：3.4 GB RomFS 打出 NSP 3,572,693,208 B，整脚本耗时 95.2 s，hacBrewPack 峰值内存 111 MiB；nstool 抽出 Program NCA 的 RomFS 分区后 12/12 文件 SHA-256 与源完全一致（200 MB 例同样 12/12）。未触及 NCA section 大小上限。 | E1+E3 |
| 3 | **A 路线（自包含）体积 ≈ 游戏数据 + 引擎**：3.4 GB 游戏数据 → NSP ≈ 3.57 GB（RomFS 不压缩），仍在 FAT32 单文件 4 GiB 限制内（3,572,693,208 < 4,294,967,296，余量约 7.2 亿字节）；但构建需约 2 倍数据量的临时磁盘 + 最终 NSP。若把汉化副本/字体也塞进 RomFS 需重新核算。 | E3 |
| 4 | **首启解包（RomFS → sdmc）在打包侧可行，但必须有引擎补丁**：NSP 只能有一个 exefs main，无法 exec RomFS 里的另一个 NRO；解包代码必须编进 K2NX 本体（P1-b 的 romfs 首启解包/直读补丁）。解包形态额外占一份 sdmc 空间（3.4 GB → 总占用约 2 倍）。 | E4+设计 |
| 5 | **未签名 NSP 结构合法但签名无效（预期）**：nstool 三个 NCA 均 exit 0、NCA Header Main Signature FAIL、Program 另有 ACID FAIL；无 ticket/cert。Citron 是否装载本批产物 **not-verified**（Citron 单实例归 P1-a）；真机需 Atmosphère + sigpatches。 | E1 |
| 6 | **keys 是硬门槛**：hacBrewPack 必须 keyset（最小 = `header_key` 32 B + `key_area_key_application_00` 16 B，默认 keygeneration=1）；脚本只接受显式 `--keyset`，无默认路径、无自动搜索；合成 keyset 模式只用于 CI/离线结构冒烟，产物 **NOT INSTALLABLE**。 | E1+E4 |
| 7 | **构建非确定性**：同输入两次构建 NSP SHA-256 不同（hacBrewPack 用 RSA-PSS + 随机盐），但 Program NCA 的 exefs/RomFS 内容哈希可复现；版本锁定应记录组件哈希而非 NSP 哈希。另观察到 hacBrewPack 会**就地修改** exefs/main.npdm 与 control/control.nacp（构建后 SHA 变化），脚本只操作暂存副本。 | E1+E3 |
| 8 | **推荐**：P2 = P1-b 补丁（romfs 首启解包/直读 + 自动启动）+ 真实游戏数据打包；P3 = Citron 直接启动验收。当前**可立刻验证**的是 B 路线引擎 NSP（22,587,096 B，含 K2NX 自带 UI RomFS），以及 m0/m1 两个对照 NSP。 | 本文 §6 |

**一句话**：打包侧不是阻塞项——预编译 NRO 能出结构合法 NSP，3.4 GB RomFS 实测可打；真正阻塞在「NSP 只有一个入口 + K2NX 未改源码无法自动解包/自动启动」，需要 P1-b 补丁与 P2 重建。

---

## 1. 任务、范围与边界

- 目标：回答「K2NX 预编译 NRO 能否不经源码重建就打成自包含 NSP」「3.4 GB 游戏数据放 RomFS 是否可行」「首启解包方案是否成立」三个问题，并产出可复现脚本。
- 输入：m0-hello.nro（166,085 B）、m1-sdl2.nro（6,740,165 B）、Kirikiroid2-NX-v1.0.1.nro（42,338,934 B，`workspaces/pilot-01/`）。
- 工具：hacBrewPack v3.05（源码自建，commit 745b16ecfc9ce055743067d200572204cb2aac6c）、nstool v1.9.2（win_x64 release）、devkitPro 2024-10-23 工具链（elf2nso/npdmtool/nacptool）、Python 3.12 + Pillow。
- 不做：不启动 Citron（P1-a 占用中）、不在真机安装、不打包真实游戏数据（P1-c/P2 的输入决策未定）、不修改 K2NX 源码（P1-b 职责）。
- 产物一律放 `E:/galnx-build/pilot-01/`（不入库）；仓库只收本文档与脚本。

---

## 2. 输入格式解剖

### 2.1 NRO 文件布局（实测）

三个 NRO 开头 16 B 都是 `20 00 00 14 f0 00 00 00` + ASCII `HOMEBREW`（前 4 B 为 ARM64 分支指令 `b +0x80`），`NRO0` magic 在 0x10，NRO 头 0x70 B；段表为 3 个 `(u32 FileOff, u32 Size)` + bssSize + BuildId。

| 项 | m0-hello | m1-sdl2 | K2NX |
| --- | --- | --- | --- |
| 文件大小 (B) | 166,085 | 6,740,165 | 42,338,934 |
| 头内 size（=ASET 绝对偏移） | 143,360 | 6,684,672 (0x660000) | 34,738,176 (0x2121000) |
| .text（FileOff, Size） | 0, 94,208 | 0, 5,013,504 | 0, 24,588,288 |
| .rodata | 94,208, 28,672 | 5,013,504, 1,417,216 | 24,588,288, 8,650,752 |
| .data | 122,880, 20,480 | 6,430,720, 291,840 | 33,239,040, 1,499,136 |
| .bss | 16,384 | 94,208 | 11,837,440 |
| BuildId（前 20 B） | 3ea0bca519874411e7d431007615c81a | 99c98813415d472e362d7186ff353ffed | e3181864542bc0065e5ccd19a935dd77 |
| ASET 内 icon（offset/size） | 56 / 6,285 | 56 / 6,285 | 56 / 27,350 |
| ASET 内 NACP | 6,341 / 16,384 | 6,341 / 16,384 | 27,406 / 16,384 |
| ASET 内 RomFS | 无（0） | 无（0） | 43,790 / 7,556,968 |

### 2.2 段数据位置（关键坑）

- 段数据在**绝对文件偏移 = FileOff**，不是「0x10 + 头 + FileOff」。用 m0 原 ELF 交叉验证：ELF 3 个 PT_LOAD 的 vaddr/filesz 与 NRO 段表一致；NRO[0:0x17000] 与 ELF .text 匹配 94,174/94,208 字节，唯一差异在 0x10–0x80——那是 `elf2nro` 写入的 NRO 头副本，正好落在 ELF 链接器预留的头槽位里；.rodata/.data 段 100% 一致。原 ELF 的 `e_entry=0`，入口由偏移 0 的分支桩 `b +0x80` 跳到 0x80（即 text 本体）。
- 因此 NRO→NSO 的最小正确做法：NSO 段 = 原样截取 `NRO[FileOff:FileOff+Size]`，text 段保留开头 0x00–0x80 的分支桩+头副本（`--zero-nro-header` 可选清零 0x10–0x80 的头副本），data 段 bss = NRO bssSize。执行时内核从 NSO text 偏移 0 开始跑，分支桩行为与 NRO 完全一致。
- ASET 位于绝对偏移 = NRO 头里的 size 字段；ASET 头 56 B（`ASET` + version + 3 组 u64 offset/u64 size），**子项 offset 相对 ASET 头起点**。

### 2.3 内嵌 RomFS（K2NX 的 UI 资源）

- K2NX NRO 的 ASET 内嵌 7,556,968 B RomFS 镜像。解包后：**83 个文件、payload 合计 258,999 B**（cocos UI：Default/Button_*.png、img/*.png、DroidSansFallback.ttf 等），其余约 7.3 MB 是 RomFS 镜像的对齐/元数据空洞。→ 重打包为 NSP RomFS 后只有 259 KB，**NSP 反而比 NRO 小**（22.6 MB vs 42.3 MB，另有 LZ4 压缩贡献）。
- m0/m1 的 ASET 无 RomFS；其 icon 就是 libnx 默认图标（6,285 B，sha256 `0b942950` 开头），NACP 由 elf2nro 内嵌（Title Name = NRO 文件名）。

### 2.4 NSO 生成（为什么不需要自写 LZ4）

- `switchbrew/switch-tools/src/elf2nso.c`（master，HEAD v1.13.1 = 22756068dd0ed6ff9734c59cb4f99ebd3f62555b）已确认：NSO 头 0x100 B（`NSO0` + 3×(FileOff,DstOff,DecompSz,AlignOrTotalSz) + BuildId[0x20] + CompSz[3] + Padding[0x24] + 2×u64 + 3×SHA-256[0x20]）；段数据用 LZ4 压缩（`LZ4_compress_default`），`Hashes[i] = SHA256(未压缩段)`；data 段 `AlignOrTotalSz = p_memsz - p_filesz` 即 bss；且 **elf2nso/elf2nro 都不使用 e_entry**（只校验 e_machine=AARCH64 与 phdr 范围）——这正是「合成 ELF」可行的源码依据。
- 实测自建 NSO（m0）：`seg0 FileOff=0x100 DstOff=0 AlignOrTotalSz=1`、`seg1 FileOff=0x106e4 DstOff=0x17000`、`seg2 AlignOrTotalSz=0x4000`；`hash0 = be72132416fd38ce` == sha256(NRO text raw)；nstool -t nso 显示 ModuleId=BuildId、.text/.ro/.data MemoryOffset 0/0x17000/0x1e000 与 .bss 0x4000。→ 与真实 NSO（hbl.nsp 提取的 main）同格式。

**synthetic ELF 构造规则（脚本 STEP 1 实现）**：3 个 PT_LOAD，文件偏移从 0x1000 起、`p_vaddr=FileOff`、`p_filesz=Size`、data 段 `p_memsz=Size+bss`、flags 5/4/6、align 0x1000；GNU build-id note 的 desc 用 NRO BuildId，保证 NSO BuildId 与原 NRO 一致。

---

## 3. 打包链路与脚本

### 3.1 链路

    NRO 文件 ──(python: 段截取 + ASET 解析 + 内嵌 RomFS 解包)──┐
      ├─ synthetic ELF ──> devkitPro elf2nso ──> exefs/main   │
      ├─ ASET icon.jpg ────────────────────────> control/icon_<Lang>.dat
      ├─ ASET control.nacp ────────────────────> control/control.nacp
      └─ ASET romfs ──(解包为目录)──┐                          │
    ELF 文件 ───────────────────────┼──> examples/nsp/npdm.json + npdmtool ──> exefs/main.npdm
    --romfs-dir ───────────────────┴──> control/ + romfs/ ──> hacBrewPack --nologo -k <显式 keyset> ──> NSP
    NSP ──> nstool -y（NSP 层）+ nstool -x/-y（NCA 层，仅 real keys）──> 结构报告

### 3.2 脚本用法

    # 1) 预编译 NRO 直接出包（复用 NRO 内嵌 icon/NACP/RomFS）
    bash scripts/build_pilot_nsp.sh --nro <file.nro> --title-id 010047410000b0b1 \
      --name Kirikiroid2-NX --hacbrewpack <hacbrewpack.exe> --nstool <nstool.exe> \
      --keyset "E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys"

    # 2) 重建 ELF 出包（P2 形态；数据目录另给）
    bash scripts/build_pilot_nsp.sh --elf <app.elf> --romfs-dir <game_romfs_dir> \
      --title-id 010047410000a0xx --name haruno --npdm <main.npdm>

    # 3) 无 keys 结构冒烟（CI 用；产物 NOT INSTALLABLE）
    bash scripts/build_pilot_nsp.sh --nro <m0.nro> --title-id 010047410000a010 --keyset synthetic

    # 4) 只读检查
    bash scripts/build_pilot_nsp.sh --help
    nstool -y -k <keys> <out.nsp>
    nstool -k <keys> --fstree <program.nca>
    nstool --part1 <outdir> -k <keys> <program.nca>

关键参数：`--nro` 与 `--elf` 二选一；`--title-id` 必须 16 位小写 hex；`--keyset` **必填**（路径或字面量 `synthetic`，无默认、无 fallback）；`--hacbrewpack` 必填（或环境变量 `GALNX_HACBREWPACK`）；`--out` 默认 `/e/galnx-build/pilot-01/out`；`--work` 默认 `/e/galnx-build/pilot-01/build`；`--nstool` 可选。

### 3.3 关键实现点（安全与可复现）

1. **keys 隔离**：真实模式只打印 PROVENANCE（path/size/sha256/mtime），不读内容、不复制进构建目录、不写日志；`synthetic` 模式在 WORK 内生成固定假值 keyset（带 NOT INSTALLABLE 注释），仅用于结构冒烟。
2. **就地修改防护**：hacBrewPack 会修改传入的 exefs/main.npdm 与 control/control.nacp（实测构建后 SHA 变化：m0 npdm e9df824b 变为 fda08f85；K2NX npdm 012aee95 变为 a95fc2cf；NACP 同样变化）。脚本把 NRO/ELF 资产复制到 WORK 暂存树再传，原文件与 `in/` 抽取资产保持只读原样（`===INPUTS` 里记录的是构建后暂存哈希，抽取原始哈希在 STEP 1/3 行记录）。
3. **日志脱敏**：hacBrewPack 的 `Key area key` / `key_area_key` 行一律过滤后才落盘；失败时只 tail 25 行报错。
4. **确定性限制**：两次构建 NSP SHA 不同（RSA-PSS 随机盐，nca.c rsa_sign 路径）；脚本输出组件哈希 + NSP 哈希，供复现记录时以组件为准。
5. **NCA 层校验**：NSP 层 nstool 只列 PFS0（FileNum 3）不做内容校验；real keys 时脚本额外抽 NCA 逐个 -y -k，输出 Content Type/Format/ProgID/KeyGen/Kaek/Size/SdkAddon 与签名 FAIL 行。synthetic 模式跳过 NCA 层（header_key 不匹配，必然报 `Input file type was undetermined`）。

### 3.4 一次完整复现（m0）

    bash scripts/build_pilot_nsp.sh \
      --nro "E:/galnx-build/m0-hello/m0-hello.nro" \
      --title-id 010047410000a010 --name m0-hello \
      --hacbrewpack "E:/galnx-build/m3-tools/hacBrewPack-745b16ecfc9ce055743067d200572204cb2aac6c/hacbrewpack.exe" \
      --nstool "E:/galnx-build/m3-tools/nstool.exe" \
      --keyset "E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys"
    # rc=0；产物 E:/galnx-build/pilot-01/out/m0-hello-010047410000a010.nsp 309,464 B
    # nstool: [PartitionFs] PFS0 FileNum: 3；3 个 NCA rc=0（签名 FAIL 预期）
---

## 4. 产物实测

### 4.1 总表

| 用例 | 输入 | title ID | NSP 产物 | 大小 (B) | NSP SHA-256 | NCA 结构（nstool） |
| --- | --- | --- | --- | --- | --- | --- |
| m0-hello | m0-hello.nro（166,085 B） | 010047410000a010 | m0-hello-010047410000a010.nsp | 309,464 | c4a0c70ff0ce1d707db3ac9cb630807eb30be6ec7f16da10833cae23bfda8aac（另次 96b0f443…） | Program 0x2dc00 / Control 0x1cc00 / Meta 0x1000，ProgID 0x010047410000a010 |
| m1-sdl2 | m1-sdl2.nro（6,740,165 B） | 010047410000a011 | m1-sdl2-010047410000a011.nsp | 4,063,448 | 77e8d8a6535b0b7f1975d3ba61f9955a1369ac2a124997888342dd117a1a5b4d | 三个 NCA 均 rc0（签名 FAIL 预期） |
| K2NX | Kirikiroid2-NX-v1.0.1.nro（42,338,934 B） | 010047410000b0b1 | Kirikiroid2-NX-010047410000b0b1.nsp | 22,587,096 | 216efe02bda60587ed6a7c39a395e7c4f593f57833f52e113da7df7459cd24ba | Program 0x1568a00 / Control 0x20c00 / Meta 0x1000 |
| scale200 | m0.nro + 200 MiB RomFS | 010047410000a020 | scale200-010047410000a020.nsp | 210,696,408 | ff0b6f26df41fdb8e9c6f8d9380c03895be00ac4ad2b26558c97210a52ed90ef | Program 210,574,336 / Control 117,760 / Meta 4,096 |
| scale3400 | m0.nro + 3400 MiB RomFS | 010047410000a030 | scale3400-010047410000a030.nsp | **3,572,693,208** | **670a7cda1c18d995ba92f786c4bb71cf50f59a67d6847f1d2339c51f06bba735** | Program 3,572,571,136 / Control 117,760 / Meta 4,096 |

产物目录：`E:/galnx-build/pilot-01/out/`（m0/m1/K2NX 日志同目录），scale 产物在 `E:/galnx-build/pilot-01/scale/out/`。

### 4.2 结构细节（m0，real keyset）

- NSP 层：`nstool -y -k <keys> m0.nsp` → exit 0，输出仅 `[WARNING] Failed to load "title.keys" keyfile.` 与 `[PartitionFs] Type: PFS0 FileNum: 3`——**NSP 层不深入 NCA、不做内容校验**。
- NCA 层（nstool -x 抽出 3 个 NCA 后逐个 `-y -k`）：三个均 exit 0，共同打印 `[WARNING] NCA Header Main Signature: FAIL`（Program 额外 `[WARNING] ACID Signature: FAIL (Failed to verify Access Control Info Desc)`），以及 `[NCA Header] Format Type: NCA3 / Dist. Type: Download / Content Type: Program|Control|Meta / Key Generation: 0 / Sig. Generation: 0 / Kaek Index: Application (0) / ProgID: 0x010047410000a010 / SdkAddon Ver.: 0.12.17 (v790784)`。
- exefs/main 84,166 B sha256 `f55f19f9688771666bbbb8e909242cec2dd5ec5f629031d21038abb2469c53c3`（合成 ELF 经 elf2nso）；main.npdm 972 B；control.nacp 16,384 B；icon 6,285 B（= libnx 默认图标）。
- 无 ticket / cert：homebrew NSP 形态，真机需 Atmosphère + sigpatches；模拟器（Citron）接受未签名包属已知行为（m0 由 M3-b 验证过，见下文 U8）。

### 4.3 K2NX 特殊点

- 预编译 NRO 带 ASET：icon 27,350 B（PIL 确认 JPEG 256x256 RGB）、NACP 16,384 B、内嵌 RomFS 7,556,968 B。脚本 STEP 1/3 自动复用 icon 与 NACP（`--icon`/`--nacp` 可覆盖），ROMFS 解包成目录（83 文件 / 258,999 B payload）后重打包。
- 合成 ELF 34,742,448 B → exefs/main 22,072,316 B（LZ4 压缩）；最终 NSP 22,587,096 B，**小于原 NRO 42,338,934 B**（RomFS 空洞消除 + LZ4）。
- 该 NSP 的 exefs main 是预编译 K2NX 本体：能启动到 K2NX UI（若 Citron 装载），但**不会自动加载游戏**（K2NX 未打自动启动补丁，且 RomFS 里只有 UI 资源，没有游戏数据）→ 仅供 P1-b/P2 参考与 Citron 装载试验，不是最终交付形态。

### 4.4 非确定性

| 构建 | NSP sha256 | 说明 |
| --- | --- | --- |
| m0 #1（脚本首次） | 96b0f443d9b063d39f035e436bb3e25329b84a3469b6d8271b85f961857847cf | 同输入 |
| m0 #2（脚本重跑） | c4a0c70ff0ce1d707db3ac9cb630807eb30be6ec7f16da10833cae23bfda8aac | 与 #1 不同，大小同 309,464 |

- 根因：hacBrewPack 的 NCA 签名用 RSA-PSS（`mbedtls_rsa_set_padding(..., MBEDTLS_RSA_PKCS_V21, MBEDTLS_SHA256)` + `mbedtls_ctr_drbg_random` 随机盐），Program/Meta NCA 每次不同 → NSP 哈希漂移。**版本锁定/CI 断言应记录组件哈希（exefs/main、main.npdm、control.nacp、romfs 内容）与 NSP 大小，不应断言 NSP 哈希。**
- 另：hacBrewPack 会就地修改传入的 main.npdm 与 control.nacp，导致同一暂存树重跑时组件哈希变化（见 §3.3 第 2 条）。脚本每次重建暂存树（`rm -rf`），故同一输入重跑时输入哈希一致；若手工复用暂存树需注意。

### 4.5 环境与时间

- 构建机：Windows 10.0.26100 x64，16 核；E: 盘约 445 G 可用（1.9 T 总量）。
- 耗时：m0 约 1 s、m1 约 2 s、K2NX 16 s、200 MB RomFS 20 s、3.4 GB RomFS 95.2 s（**吞吐约 36 MB/s**，实测采样 hacBrewPack 峰值内存 111 MiB）。
- 磁盘峰值：3.4 GB 用例约需「源 3.4 G + work NCA 3.4 G + 最终 NSP 3.4 G ≈ 10.2 GB」同时存在（脚本默认不保留 NCA 目录，可 `--keepncadir` 保留需另改；本脚本未暴露该开关）。
---

## 5. 大 RomFS 可行性与体积/时间估算

### 5.1 实测数据（scale test）

| 用例 | RomFS 文件数 / 大小 | 构建耗时 | NSP 大小 | NSP 相对 RomFS 开销 | 峰值内存 | round-trip |
| --- | --- | --- | --- | --- | --- | --- |
| scale200 | 12 / 209,977,386 B（200.25 MiB） | 20 s | 210,696,408 B | +719,022 B（≈0.7 MB，exefs+control+meta+对齐） | 未采样 | 12/12 OK |
| scale3400 | 12 / 3,565,420,587 B（3400.25 MiB） | **95.2 s** | **3,572,693,208 B** | +7,272,621 B（≈7.3 MB） | **111 MiB** | 12/12 OK |

- round-trip 方法：`hacbrewpack --romfsdir <dir>` 构建 → `nstool -x` 抽出 Program NCA → `nstool --part1 <outdir> -k <keys> <program.nca>` 抽出 RomFS 分区 → `cmp_romfs.py` 对每个文件比对 SHA-256（fixture 12 个文件含 3 个 hash 固定块 + 子目录 readme/small）。两次都输出 `missing=[] extra=[] ROUNDTRIP OK`。
- `nstool --fstree` 能正确列出 3.4 GB RomFS 全部 12 条目；`nstool -y` 对 3.57 GB NSP 也 exit 0（`PFS0 FileNum: 3`）→ **2 GB 以上 NSP/NCA 在 nstool 侧无解析问题**。
- hacBrewPack 对 3.4 GB RomFS 没有出现 NCA section 大小上限（NCA 3.0 的 RomFS section 为 64 位偏移/大小，实测 Program NCA 3,572,571,136 B 正常）；日志无报错，仅常规 `Writing ... to ... / Summary` 行。

### 5.2 外推到 3.4 GB 游戏数据（A 路线自包含）

- NSP 体积 ≈ RomFS 数据量 + 约 0.3–8 MB（引擎 exefs 压缩后 + control/meta + 对齐）。3.4 GB 游戏数据（`haruno` 目录约 3.6 GB，其中 14 个原版 xp3 合计 2,869,566,751 B，见 P1-game-audit）→ 预计 NSP **3.6–3.7 GB**；本次实测 3.57 GB 已验证量级。
- FAT32 单文件上限 4 GiB = 4,294,967,296 B：3.57 GB 可用（余量约 722 MB），但**装不下 4 GB 以上的游戏数据**；若把汉化副本、字体、存档模板等都塞进 RomFS 需重新核算。exFAT 无此限制但 Switch SD 卡常用 FAT32（Atmosphère 支持 exFAT，但存在损坏风险，团队约定见 docs/pilot/README.md R3）。
- 构建磁盘峰值 ≈ 3 倍数据量（源 RomFS + work 中间 NCA + 最终 NSP ≈ 10.2 GB）；构建时间约 36 MB/s（3.4 GB 约 95 s，不含磁盘拷贝与 nstool 校验）；若 CI 每次重建需预留 ≥ 15 GB 临时空间。
- 真机/模拟器装载 3.4 GB NSP 的耗时、内存与稳定性 **not-verified**（Citron 本轮单实例归 P1-a；DBI MTP 安装时间未测）。风险：大 NSP 通过 MTP 安装耗时长、易中断；Citron 从文件加载大 NSP 的解析/内存占用未知。

### 5.3 限制清单（打包侧）

| # | 限制 | 证据/状态 | 影响 |
| --- | --- | --- | --- |
| L1 | Windows MAX_PATH 259 B（hacBrewPack 的 filepath 实现） | Carafe docs/nsp.md 实测：258/259 通过、260/270 失败 `Failed to stat`；本任务 fixture 最长路径 56 字符 | RomFS 内路径总长（含 `romfs/` 前缀）超过约 250 B 会构建失败；需在打包前预检 |
| L2 | Windows 路径 ANSI 代码页（hacBrewPack `main(int argc, char** argv)`） | 源码观察（P1-b 复核范围内）；非 ASCII 路径（中文文件名）可能乱码/失败 | 游戏目录含中文文件名时需先转写或改工具；**not-verified**（未实测） |
| L3 | FAT32 单文件 4 GiB | 本任务实测 3.57 GB 通过 | 超过 4 GiB 的 NSP 无法放 FAT32 SD 卡 |
| L4 | 构建非确定性（RSA-PSS） | §4.4 | 不能断言 NSP 哈希；以组件哈希记录 |
| L5 | keyset 为硬前置 | §3.3 | CI 无 keys 只能 synthetic 结构冒烟；真机包需本机离线 real keys |
| L6 | NSP 只有一个 exefs main | 平台格式约束 | 无法从 NSP 启动 RomFS 里的另一个 NRO（见 §6） |

---

## 6. 首启解包/自动启动方案对比（A1 / A2 / B）

### 6.1 为什么必须改引擎（打包侧无法绕过）

- Switch NSP 的启动单元是 exefs 里的唯一 main（本任务打出的是 K2NX 本体 NSO）。NSP 里可以有 RomFS 数据，但**没有机制从 NSP 内部 exec 另一个 NRO**；K2NX 的 UI 资源在它自己的 ASET 内嵌 RomFS 里，游戏数据在 PC 侧单独目录。
- 因此要让「安装后直接玩」，必须把「读 RomFS/或读固定 sdmc 路径 → 自动进入游戏」的代码编进 K2NX 本体（P1-b 的 romfs 首启解包补丁 / 直读补丁 / 自动启动补丁）。打包侧能配合的只是**数据放在哪**：RomFS（NSP 内）或 sdmc（NSP 外）。
- libnx 在进程内提供 `romfs:/` devoptab（只读），可从 RomFS 读文件并写 `sdmc:/`；现实实现需考虑：进度日志、`.marker` 防重复解包、空间检查、原子写（先写临时文件再 rename）、失败可重试。

### 6.2 三种形态

| 形态 | exefs main | RomFS（NSP 内） | 游戏数据位置 | NSP 体积 | 首次启动 | 优点 | 缺点/风险 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **A1 全量自包含 + 首启解包** | K2NX + P1-b 补丁（romfs 读取 + 解包 + 自动启动） | UI 资源 + 游戏数据（约 3.6 GB） | RomFS → 首启拷到 `sdmc:/kirikiri/haruno`（或直读 romfs） | **3.6–3.7 GB** | 需解包（耗时取决于 SD 卡写速，未知） | 一个 NSP 就是完整游戏，安装即玩 | 构建/安装/占用三重大；SD 卡需双份空间（约 7 GB）；解包失败恢复复杂；FAT32 余量小 |
| **A2 引擎 + UI RomFS，数据在 sdmc**（当前试点已具备） | K2NX + P1-b 补丁（固定路径自动启动） | 仅 UI 资源（约 0.26 MB） | 用户经 USB/DBI 或 PC 拷贝到 `sdmc:/kirikiri/haruno` | **约 22.6 MB** | 立即启动，无需解包 | NSP 小、构建快、迭代成本低；本轮 K2NX NSP 已可验证装载 | 多一步拷数据（可由 P1-c/安装器 NSP 补）；需要固定 sdmc 路径约定 |
| **B forwarder**（NSP→sdmc 上的 NRO） | 通用 forwarder | 无/极小 | NRO 在 sdmc | 1 MB 级 | 直接跳 NRO | 体积最小 | 需签名补丁（sigpatches）绕过，NTON README 明确「forwarder 签名无效、无法仅靠 CFW 启动」且「Nintendo DMCA 过相关方案」；**合规与稳定性风险最高，本试点不采用** |

### 6.3 推荐

1. **P2 迭代先用 A2**：K2NX NSP（22.6 MB，含 UI RomFS）+ P1-b 自动启动补丁 + 游戏数据预先拷到 `sdmc:/kirikiri/haruno`。理由：当前游戏目录已在 Citron sdmc 下（P1-a 已复制 3.4 GB），无需重新打包 3.4 GB 就能在 Citron 上验证「安装 NSP → 启动 → 进游戏 → 手柄操作」的垂直切片；同时把打包链、TitleID、图标、存档隔离等 M3 契约一次跑通。
2. **P3 在 A2 验收后升级 A1**：把游戏数据放进 RomFS（3.57 GB 实测可行）+ 首启解包（或直读 romfs 补丁），作为「一个 NSP 完整游戏」的最终形态。若 SD 卡空间/安装时间不可接受，则最终交付保持 A2 + 一个「数据导入」引导流程。
3. **不采用 B**：合规风险高（DMCA 先例）、且与「自包含 NSP」目标相反；NTON forwarder 仅作历史参考。

**结论**：3.4 GB 自包含在**打包侧**已证明可行（NSP 3.57 GB、nstool 结构通过、RomFS round-trip 一致），是否作为最终形态取决于**引擎补丁**与**真机安装体验**——这两项分别是 P1-b 与 P2/P3 的验收项，本任务不越权结论。
---

## 7. 版本锁定、集成建议与数据模型

### 7.1 工具版本锁定（本次实测所用）

| 组件 | 精确版本 | 大小 / SHA-256 | 来源 |
| --- | --- | --- | --- |
| hacBrewPack | commit 745b16ecfc9ce055743067d200572204cb2aac6c（tag v3.05，GPL-2.0） | 源码 zip 3,164,885 B / 77d7c65976f5a4161219a0447a54a4fd40f18b9ee579d9325fa48986dc61e601；自建 hacbrewpack.exe 508,983 B / 5623fd2b51225b91d18e23f252bc8d21e440b94be53701f39e514358fecf2c7b（MinGW gcc 16.2.0） | github.com/rlaphoenix/hacBrewPack |
| nstool | v1.9.2 = e89ea84bd70c11b67ebec9153fb4a446f18a9d3d（MIT） | nstool.exe 1,050,112 B / 844648190dd8688098887a369da1126c1b3ab1c2a664fb603b01cb22e76b6ca9；release zip 487,087 B / 34659dc47249a3c00f7fc88a11f4e5ba14dfbec0a6a96b4f3f71368a7e1c9374 | github.com/jakcron/nstool |
| devkitPro elf2nso | 2024-10-23 工具链（switch-tools v1.13.1 = 22756068dd0ed6ff9734c59cb4f99ebd3f62555b） | elf2nso.exe 94,720 B / d41476f5f16f66345b2911b28ea8aabde2ea6ddfaf54d27e08f2ac98a794d99f | D:/devkitPro/tools/bin（switch-tools 源码 github.com/switchbrew/switch-tools） |
| devkitPro npdmtool | 同上 | npdmtool.exe 106,496 B / 7fbce9299a0d17fee0c396bfbd09e63cfaf97cfa8e153c0d1fe6d6ca318c8fde | 同上 |
| devkitPro nacptool | 同上 | nacptool.exe 74,240 B / d899dd3753f05a9a837fcc4877d52c052128d772977de6c3cfeb4607885fa034 | 同上 |
| libnx default_icon.jpg | 6,285 B / 0b942950df9fb30f08336b681e24a3ceeeaa6f0915d7dd404d5ebb9bd4e15214（256×256 RGB JPEG，EXIF 无） | — | D:/devkitPro/libnx/default_icon.jpg |
| 打包脚本 | `scripts/build_pilot_nsp.sh` 651 行 / 29,135 B / 0d62f78f2021b003db7e23735e7c6d699f351695bf1dc95ff9f9340e31055f93 | — | 本仓库 |
| Python / Pillow | Python 3.12.10（本机）；Pillow 用于 icon 256×256 JPEG 校验 | — | 本机 |

- **keyset（仅元数据，不记录内容）**：`E:/Othergames/Nintendo Switch/Ryujinx-canary/portable/system/prod.keys`，12,007 B，sha256 `7bb3b6d2a2eedc83c9f244ee2ed2eaa4d59eb9ad95b66df575f7dfffa71a2a40`，mtime 2026-03-19 07:25:45.902258500 +0800；首选 `C:/Users/ACETaffy/.switch/prod.keys` 不存在。脚本不内置默认路径、不自动搜索，构建日志中 hacBrewPack 的 `Key area key` 行已被过滤。
- CI 建议：仅用 `--keyset synthetic` 做离线结构冒烟（产物 NOT INSTALLABLE），绝不把真实 keys 写入 CI secrets/仓库；真机/模拟器验证由本机离线步骤完成。

### 7.2 与 GalNX 框架（M3/M6）的集成建议

1. **引擎适配器**：K2NX 作为新 adapter（`kirikiroid2-nx`），descriptor 的 `pinned_commit` 需指向 P1-b 重建后的源码提交；`artifact_naming` 为 `{id}-{version}.nro`、`content_layout.mode` 建议先 `sdmc`（A2 形态）后改 `romfs`（A1 形态）。
2. **打包输入契约（扩展 M3/M6 build 段）**：建议在 manifest 的 `build` 段新增（或复用一个 `package.nsp` 子段）：`title_id`（16 hex）、`icon`（jpg 路径，256×256 校验）、`romfs_dir`（可选）、`keyset_env`（环境变量名而非路径，避免把 keys 路径写进 manifest 仓库）、`output_dir`。M6-b 的 `build.commands` 可调用本脚本（argv 形式，显式传 `--keyset "$GALNX_PROD_KEYS"`）。
3. **缓存 key**：M6-b 现有 cache key 已含 build.commands/workdir/artifact/env/timeout/input/engine/toolchain fingerprint；打包产物额外依赖 keyset 元数据（内容不变即可复用，不应把 keyset 路径写入 key）与 TitleID/icon/romfs 内容哈希——建议把 `title_id`/`icon`/`romfs` 纳入 build 段 canonical JSON 即可，无需改缓存结构。
4. **报告**：M6-b 报告已有 `artifact{path,size,sha256}`、`commands[]`、`cache{hit,key}`；NSP 打包可沿用（artifact 记 NSP 路径/大小/sha256，commands 记脚本调用），无需新增字段。**注意 artifact sha256 记录 NSP 哈希会因 RSA-PSS 非确定性变化**，diff 会出现 artifact_changed——建议额外输出组件哈希文件（如 `<out>.components.txt`）并在报告 metadata 中引用；本任务未改框架代码，仅作建议。
5. **数据模型边界**：游戏数据目录（3.6 GB）与 RomFS 构建目录不应进入 git；只在 manifest 记绝对/相对路径与 SHA-256 清单（若需完整性）。

### 7.3 给 Lead / 其他任务的立即可做项

| # | 动作 | 产物 | 备注 |
| --- | --- | --- | --- |
| 1 | 用 Citron 装载 K2NX NSP 验证「NSP 能装、能启动、能进 UI」 | `E:/galnx-build/pilot-01/out/Kirikiroid2-NX-010047410000b0b1.nsp` 22,587,096 B sha256 216efe02bda60587ed6a7c39a395e7c4f593f57833f52e113da7df7459cd24ba | 需 Citron 窗口（P1-a 让出后）；启动后是 K2NX 文件选择器 UI，不自动进游戏 |
| 2 | 对照装载 m0 NSP（已知可运行） | `E:/galnx-build/pilot-01/out/m0-hello-010047410000a010.nsp` 309,464 B | 校验「NRO→NSP 链路」产物在模拟器侧可运行 |
| 3 | P1-b 补丁形态确认 | 需 K2NX 源码补丁：ROMFS/固定 sdmc 路径自动启动 + 可选首启解包（A2 先做） | 打包侧已证明数据放 RomFS 可行，补丁是唯一阻塞 |
| 4 | 选 A1 还是 A2 作为 P2 验收形态 | 建议 A2 先跑通垂直切片，A1 作为最终形态 | 见 §6.3 |
| 5 | 真机安装验收（后置） | DBI MTP 安装 K2NX NSP / A1 3.57 GB NSP | 未验证；需 Atmosphère + sigpatches；FAT32 余量约 722 MB |

---

## 8. 风险

| # | 风险 | 等级 | 缓解 |
| --- | --- | --- | --- |
| R1 | 未签名 NSP 无法仅靠 CFW 启动（需 Atmosphère + sigpatches） | 高（真机） | 真机验收前先确认环境；模拟器侧不受影响（M3-b 已知 Citron 可载未签名 m0 NSP） |
| R2 | 构建非确定性导致哈希漂移、CI 无法断言 NSP 哈希 | 中 | 记录组件哈希；CI 只断言组件/大小；synthetic 模式仅结构 |
| R3 | 3.4 GB NSP 的安装/装载时间与 SD 卡空间（A1 需约 2 倍空间） | 中 | 先 A2（22.6 MB）；A1 做空间预检与解包进度/断点续传；真机实测后再定 |
| R4 | Windows MAX_PATH 259 B 限制导致 RomFS 构建失败 | 中 | 打包前预检路径长度（Carafe 已有同类实现可参考）；本任务 fixture 最长 56 字符 |
| R5 | 非 ASCII（中文）路径在 hacBrewPack 内可能因 ANSI 代码页失败 | 中 | 预检/转写；**not-verified**（本任务未测中文路径） |
| R6 | keys 泄漏风险（prod.keys 是用户自备、不可分发） | 高（合规） | 脚本只显式 `--keyset`、只打 PROVENANCE 元数据、日志过滤 `Key area key`；绝不入库/入 CI |
| R7 | K2NX 预编译 NRO 无源码对应关系（版本 v1.0.1 的构建不可复现） | 中 | P1-b 重建产物替换；本任务产物只作原型验证 |
| R8 | 内嵌 RomFS 解包可能不完整（仅 83 文件 259 KB payload） | 中 | 已用 K2NX nstool NACP/UI 资源核对；**引擎运行时是否还需要其它文件 not-verified**，以 P1-b 重建版本为准 |
| R9 | NSP 单入口限制导致「解包器/引擎二选一」困境 | 高（设计） | 解包逻辑必须并入 K2NX 本体（P1-b）；打包侧无法绕过 |

---

## 9. 未验证项

| # | 项 | 说明 |
| --- | --- | --- |
| U1 | K2NX NSP 在 Citron 的装载/启动 | 未启动 Citron（单实例归 P1-a）；需 Lead 安排窗口 |
| U2 | 真机安装（DBI MTP）与启动 | 未做，需 Atmosphère + sigpatches |
| U3 | 3.4 GB 级 NSP 的 MTP 安装耗时/稳定性 | 未做 |
| U4 | 首启解包速度（RomFS→sdmc 写速） | 未做；取决于 SD 卡写速与补丁实现 |
| U5 | 中文/非 ASCII RomFS 路径构建 | 未做（风险 R5） |
| U6 | K2NX 内嵌 RomFS 的完整性（运行时是否还需要其它资源） | 未做；需 P1-b 重建后验证 |
| U7 | 游戏数据路径约定（sdmc:/kirikiri/haruno）与 K2NX 实际期望路径 | 由 P1-b/P1-a 确认；本任务只按试点现状假设 |
| U8 | 未签名 NSP 的模拟器/真机兼容矩阵 | 模拟器侧有历史证据（M3-b m0）；K2NX NSP 未测 |
| U9 | 存档隔离（save data size/title ID 唯一性） | 当前 npdm.json 模板固定 TitleID，控制 NACP 的 save 大小来自 nacptool 默认值（62 MiB + 1 MiB）；正式打包需按引擎需求设置，未验证 |
| U10 | 图标/启动画面（logo 段）与标题本地化 | 脚本用 `--nologo`（无 Nintendo logo/StartupMovie），NACP 各语言名来自 nacptool/内嵌 NACP；正式形态需美术资源，未做 |

---

## 10. 证据清单

### 10.1 E1 运行日志（不入库，路径供复核）

| 日志 | 内容 |
| --- | --- |
| `E:/galnx-build/pilot-01/out/m0-run.log` | m0 两次构建 + nstool NSP/NCA 层输出 |
| `E:/galnx-build/pilot-01/out/m1-run.log` | m1 构建 |
| `E:/galnx-build/pilot-01/out/k2nx-run.log` | K2NX 构建 + ASET/RomFS 解包 + nstool |
| `E:/galnx-build/pilot-01/out/scale200-run.log` 等 | 200 MB 构建、fstree、part1 抽取、round-trip |
| `E:/galnx-build/pilot-01/out/scale3400-run.log` 等 | 3.4 GB 构建（含内存采样结果行）、NSP/NCA 校验、fstree、part1 + round-trip |

### 10.2 E3 哈希/结构元数据（关键项）

| 对象 | 值 |
| --- | --- |
| m0-hello.nro | 166,085 B / a341e7750e099da94c12541d8fb173793cc348688824c69f5f76c7ce29b9318b |
| m1-sdl2.nro | 6,740,165 B / d46ae7c0786ade931b4041778eca0d1b33831892818fc5bbe5bd94fbb6c575bf |
| Kirikiroid2-NX-v1.0.1.nro | 42,338,934 B / ce3c0169610eb2d65f332e26a16d14c283f9dcf39634dc4f46c2c004860919b8 |
| m0 NSP（run2） | 309,464 B / c4a0c70ff0ce1d707db3ac9cb630807eb30be6ec7f16da10833cae23bfda8aac |
| m1 NSP | 4,063,448 B / 77e8d8a6535b0b7f1975d3ba61f9955a1369ac2a124997888342dd117a1a5b4d |
| K2NX NSP | 22,587,096 B / 216efe02bda60587ed6a7c39a395e7c4f593f57833f52e113da7df7459cd24ba |
| scale200 NSP | 210,696,408 B / ff0b6f26df41fdb8e9c6f8d9380c03895be00ac4ad2b26558c97210a52ed90ef |
| scale3400 NSP | 3,572,693,208 B / 670a7cda1c18d995ba92f786c4bb71cf50f59a67d6847f1d2339c51f06bba735 |
| m0 exefs/main（合成 NSO） | 84,166 B / f55f19f9688771666bbbb8e909242cec2dd5ec5f629031d21038abb2469c53c3 |
| K2NX exefs/main（合成 NSO） | 22,072,316 B / 07742ad99d643743af833cdc80e6aaf1b210194b15c8545b095a04821689f55d |
| K2NX 抽取 icon | 27,350 B / dff2e7943e0ce1306d243d314b2bcb7f1e7308fadd4e3ecb0053e181fdf80354 |
| K2NX 抽取 control.nacp | 16,384 B / 5c8bf82d9aef4c8066dfde456aaf45691d81ef430d09332fe48a19bd1cdbd57e |
| 打包脚本（v0.1） | 29,135 B / 0d62f78f2021b003db7e23735e7c6d699f351695bf1dc95ff9f9340e31055f93；修复根级文件链后为 30,229 B / 9f6a19888c8d5495fd20bf70f1b4db5202d016f8c5fc85b52f33ebb5d1cc7360（见 P1d-artifacts-sha256.txt） |

### 10.3 E4 源码依据

| 事实 | 来源 |
| --- | --- |
| NRO 头/ASET 结构 | `switchbrew/switch-tools/src/elf2nro.c`（master，HTTP 200，8,757 B；本地副本 `E:/galnx-build/pilot-01/ref/elf2nro.c`） |
| NSO 头 0x100 B、LZ4 压缩、段 SHA-256、不用 e_entry | `switchbrew/switch-tools/src/elf2nso.c`（master，HTTP 200，5,186 B；本地副本 `E:/galnx-build/pilot-01/ref/elf2nso.c`） |
| RSA-PSS 随机盐导致非确定性 | hacBrewPack `rsa.c` + `nca.c:667-670`（本机源码 `E:/galnx-build/m3-tools/hacBrewPack-745b16ec.../`） |
| 最小 keyset = header_key 32 B + key_area_key_application_00 16 B | hacBrewPack `main.c:100/320-344/410-414`（同目录；M3-a 已实测） |

---

## 11. 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-10-30 | 初版：NRO→NSP 链路打通（m0/m1/K2NX）、200 MB 与 3.4 GB RomFS scale test + round-trip、A1/A2/B 方案对比、版本锁定与证据清单。未启动 Citron、未真机、未打包真实游戏数据。 |
| v0.2 | 2026-10-30 | 补充：三档 scale（200 MB / 1 GB / 2.86 GiB 真实 payload）+ 3400 MiB 前科档；A1 最终自包含 NSP（010047410000b0b2，2,906,131,672 B）产出并 nstool/round-trip 校验；CJK「口口」根因（RomFS 根级文件被静默丢弃）定位与修复验证（b0b3）；ELF/NSO 程序头与加载基址解释；boot 时间归因；A1/A2/A3 选择依据、非确定性/就地修改、体积/时间预估、证据 P1d-* 入库。 |
| v0.3 | 2026-10-30 | U11 关闭：Lead 在 Citron 验证 A1 自包含 NSP 首启解包（22 文件/2737 MiB 拷贝 14 s 0 failed、autostart → title.ks、标题画面稳定 3 分钟）；新增 §12.12，同步 §12.1/§12.6/§12.9/§12.10/U11 与证据清单；新增证据 P1d-a1-firstboot-citron.txt + 3 个 k2s 日志副本。 |
---

## 12. v0.2 补充：真实 payload 三档 scale、最终 A1 产物与遗留问题

本节为 2026-10-30 06:18-06:56 的补充实测（Lead 追加要求：三档 scale、证据入库、A1/A2/A3 依据、CJK 根因、ELF 基址、boot 时间）。v0.1 正文（§1-§11）保持不变，本节为增量结论。

### 12.1 最终 A1 自包含 NSP（core deliverable）

| 项 | 值 |
| --- | --- |
| 输入 ELF | E:/galnx-build/pilot-01/out/K2NX-rebuilt-galnx-r2.elf 113,874,760 B / sha256 4b4515837d0239ee2e7448dd5dbed65e8fdda72c37fb0bac0d0dd10ef849b882（Lead 重建版，含自动启动/首启解包/插件别名三补丁） |
| RomFS 输入 | E:/galnx-build/pilot-01/nsp/romfs-a1 108 files / 2,878,185,598 B / 最长绝对路径 67 字符；UI 85 文件（含 DroidSansFallback.ttf 7,287,728 B）+ game/haruno 22 文件（3,071,419,729 B）+ game_files.txt（569 B / 27 行，bytes=2870634016，startup=/kirikiri/haruno/data.xp3） |
| TitleID / 名称 | 010047410000b0b2（TitleID 十六进制小写）；NACP 名称 "Kirikiroid2-NX"，作者 Erige005，版本 1.0.1（ASCII，暂不用中文名，见 §9 U10/U14） |
| 产物 | E:/galnx-build/pilot-01/out/K2NX-A1-selfcontained-010047410000b0b2.nsp 2,906,131,672 B / sha256 9678e992c07bcbe46aa70695957b948badd6f2adaf97e39401060ad196efc3d3 |
| 结构 | PFS0 FileNum 3：Program NCA 2,905,993,216 B、Control NCA 134,144 B、Meta(CNMT) NCA 4,096 B；均 NCA3/Download/KeyGen 0/Kaek Application(0)/ProgID 0x010047410000b0b2；签名 FAIL（预期） |
| 构建指标 | 端到端 288.4 s；hacBrewPack 峰值内存 111 MiB；磁盘峰值约 8.4 GB（romfs 2.878 + NCA 2.906 + NSP 2.906 阶段叠加）；rc=0 |
| 校验 | nstool -y NSP rc=0；--part1 抽回 romfs 108 files / 2,878,185,598 B，cmp_tree.py 与 romfs-a1 逐文件 MATCH（only_in_A=0 / only_in_B=0 / content_diff=0）；payload 22 文件 22/22 sha256 一致 |
| 首启验证 | Lead 已在 Citron 验证首启解包通过（U11 关闭，见 §12.12）：status=loaded、22 文件/2737 MiB 拷贝 14 s 0 failed、autostart data.xp3 → title.ks；我方未启动 Citron、未真机 |

### 12.2 RomFS scale 三档 + 3400 MiB 前科档

| 档 | romfs 输入（files / bytes） | 耗时 | 峰值内存 | work 目录峰值 | NSP 大小 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| 200 MiB | 12 / 209,977,386 | 20 s | 未采样 | 未采样 | 210,696,408 B | 通过，NSP 开销约 0.34% |
| 1024 MiB | 12 / 1,074,004,011 | 43 s | 未采到 | 2,153,131,368 B / 21 files | 1,076,410,584 B | 通过，开销约 0.22% |
| 2860 MiB 真实 payload（run1） | 108 / 2,878,185,572 | 231.9 s | 111 MiB | — | 2,884,106,456 B | 通过，开销约 0.21% |
| 2860 MiB（run2，1 Hz 采样） | 108 / 2,878,185,581 | 230 s | 111 MiB | 7,407,040,373 B / 33 files | 2,884,106,456 B | 通过；sha256 与 run1 不同（RSA-PSS） |
| 3400 MiB 前科档 | 12 / 3,565,420,587 | 95.2 s | 111 MiB | — | 3,572,693,208 B | 通过；12/12 round-trip |
| A1 最终（2860 真实 payload + 重建 ELF） | 108 / 2,878,185,598 | 288.4 s | 111 MiB | 约 8.4 GB（估算） | 2,906,131,672 B | 通过；108/108 round-trip |

结论：hacBrewPack v3.05 对 2.86 GiB 真实 payload 出包成功，Program NCA 2.88 GB 正常，无 >2 GiB NCA section 上限问题；内存与 romfs 体积解耦（流式拷贝 + IVFC 逐层临时文件）；吞吐约 36-37 MB/s；NSP 体积约等于 romfs + 0.2%，远小于 FAT32 4 GiB 单文件上限（3.4 GiB 档余量约 722 MB，2.86 GiB 档余量约 1.39 GB）。

### 12.3 CJK 口口根因（重打包丢根级文件，已修复并验证）

- 现象：NSP 形态 Citron 里中文目录名显示为「口口」，NRO 形态正常（audit-web A/B）。
- 根因：旧版脚本 RomFS 解包从 root.child（目录链）开始遍历，root 自身文件链未遍历，静默丢弃所有根级文件 —— 恰好是 DroidSansFallback.ttf（7,287,728 B）与 default.cur（4,286 B）；83 files / 258,999 B + 两者 = 85 files / 7,551,013 B 精确吻合。
- 修复：scripts/build_pilot_nsp.sh 显式遍历 root 文件链（root[3]）；重新打包预编译 NRO -> b0b3 NSP 29,877,976 B / sha256 2bc724555ffa5c3f229748c68e6f06a1b13326619bf8162f045eb5964008dead，--part1 抽回 85/85 MATCH。
- 影响：A1 的 romfs 直接来自 Lead 重建的 build/romfs（85 文件 7,551,013 B，与解包修复结果 0 diff），因此 A1 不受此 bug 影响；b0b3 可用于 audit-web 复测 CJK。
- 教训：RomFS 解析必须覆盖 root 目录项的两条链（child 目录链 + 文件链），仅遍历子目录会静默丢根级文件。

### 12.4 ELF/NSO 程序头与加载基址（回答"image base 0x8000000 vs 0x80000000"）

- 重建 r2 ELF（readelf -l）：ELF64 AArch64 DYN PIE，entry 0x0；LOAD0 off 0x10000 vaddr 0x0 filesz 0x1774968；LOAD1 off 0x1785000 vaddr 0x1775000 filesz 0x8403a0；LOAD2 off 0x1fc6000 vaddr 0x1fb6000 filesz 0x16d040 memsz 0xdb79d8。
- 合成 ELF（NRO 转换）：3×PT_LOAD，off 0x1000/0x18000/0x1f000，vaddr=0/0x17000/0x1e000，filesz=0x17000/0x7000/0x5000，第 3 段 memsz += NRO bss（0x4000 例），e_entry=0；GNU build-id = NRO BuildId。
- devkitPro elf2nso 只使用 p_vaddr（-> DstOff）、p_filesz（-> DecompSz）、第 3 段 p_memsz-p_filesz（-> bss），做 LZ4 压缩与每段 SHA-256；不使用 e_entry、不使用 p_paddr 决定加载基址。
- 因此 NSP 形态打印 image base 0x8000000 是「已安装 application 的 NSO」与「NRO homebrew（hbloader 0x80000000）」的固有差异，不是合成 ELF bug；不影响运行（重建版已在 Citron 跑通标题画面，见 §12.9）。
- 证据：docs/milestones/evidence/P1d-elf-nso-headers.txt（readelf 原文 + NSO 头 + 源码结构说明）。

### 12.5 boot 时间差异

NSP 形态 boot 行比 NRO 晚约 2 s（3.94 s vs 1.96 s）：归因于 NCA 层开销（PFS0 查找 + NCA 头/IVFC 校验 + 系统安装/挂载路径），属预期量级，不作为性能问题跟踪；若后续需要，可另立"启动耗时"验收项（模拟器侧）。

### 12.6 A1 / A2 / A3 选择依据

| 形态 | 定义 | 体积 | 构建/安装 | 真机可行性 | 结论 |
| --- | --- | --- | --- | --- | --- |
| A1 全量自包含 | NSP = 引擎 NSO + UI RomFS + game/haruno 全部游戏数据（2.86 GiB） | 约 2.9 GB | 构建 230-290 s、磁盘峰值 8.4 GB；DBI MTP 安装时间待测 | 需 FAT32 4 GiB 内（已满足）、需足够 SD 空间、需 sigpatches | **最终形态**（已验证可出包+结构+round-trip） |
| A2 引擎 NSP + 数据预拷 | NSP 只含引擎与 UI；游戏数据由 PC 预拷到 sdmc:/kirikiri/haruno | 约 23 MB（b0b1 22.6 MB） | 最快，无需大 NSP 安装 | 首次使用需拷数据、需自动启动/首启逻辑 | **先跑通形态**（Lead 已在 Citron 用 b0b1 装载成功） |
| A3 forwarder | 只放启动器 NSP，数据与引擎都在 SD | 约 1 MB | 最快 | 需 HBL/签名的路径问题，forwarder 签名限制（NTON README 已记录 DMCA 与 ban 风险） | **不采用** |

选择顺序：A2 先跑通（低风险、快速迭代 UI/自动启动）→ A1 最终（首启解包补丁 r2 已实现并有 ELF；A1 NSP 已在 Citron 验证首启解包通过，见 §12.12）。若 A1 安装/启动出现不可接受问题，回退 A2 作为发行形态。

### 12.7 非确定性与就地修改（打包工程注意）

- 非确定性：hacBrewPack 用 RSA-PSS + 随机盐签 NCA header（rsa.c / nca.c:667-670），同输入两次构建 NSP sha256 不同（m0 96b0f443… vs c4a0c70f…；2860 9091c09d… vs bcb93a3d…）。版本锁定请记录组件哈希（ELF/NPDM/NACP/icon/RomFS payload），不要锁 NSP 哈希；CI 中若要可复现，只能比对组件或做结构校验。
- 就地修改：hacBrewPack 会就地改写暂存输入（main.npdm、control.nacp 的哈希在构建后变化，m0 e9df824b… -> fda08f85…，K2NX 012aee95… -> a95fc2cf…）。脚本因此每次从输入重新复制暂存，禁止复用上一次构建目录；不要拿暂存目录做输入基线。
- 最小 keyset：header_key（32 B / 64 hex）+ key_area_key_application_00（16 B / 32 hex）；synthetic keyset 只能做离线冒烟（产物 NOT INSTALLABLE）。本轮真实 keys 仅以显式 --keyset 路径传入，未读取/复制/记录内容（只记 path/size/sha256/mtime）。

### 12.8 最终 A1 体积/时间/资源预估（供安装排期）

| 项 | 预估值 | 依据 |
| --- | --- | --- |
| NSP 体积 | 2.90-2.91 GB（实测 2,906,131,672 B） | A1 实测 |
| 构建时间 | 约 4-5 分钟（实测 288.4 s，含 ELF 转换） | A1 实测 |
| 磁盘峰值 | 约 8.5-11 GB（实测阶段叠加约 8.4 GB；若保留抽取副本再加 3 GB） | A1/2860 实测 |
| hacBrewPack 内存 | 111 MiB | 三档一致 |
| Windows 路径风险 | 仅影响源 romfs 路径（最长 67-76 字符 < 259）；不影响 NSP 产物路径 | 实测 |
| SD/安装 | 需 FAT32 单文件 < 4 GiB（实测 2.9 GB 满足）；DBI MTP 安装时间未测（U 项） | 推算/未测 |

### 12.9 与 P2/Lead 的衔接状态

- Lead 已用重建 K2NX 在 Citron 跑通自动启动 -> 标题画面（k2s_log：14 个 XP3 挂载、19183/19171 文件、5 个内置插件加载、0 exception；证据 E:/galnx-build/pilot-01/p2-evidence/lead-first-title-run/）。本报告不引用该运行细节为自身证据。
- Lead 已用 A1 自包含 NSP（010047410000b0b2）在 Citron 验证首启解包通过（2026-10-30 06:53-06:54，U11 关闭）：status=loaded、窗口标题含 1.0.1、boot 行 010047410000B0B2、22 文件/2737 MiB 拷贝 14 s 0 failed、autostart data.xp3、Scenario loaded : title.ks、标题画面 3 分钟稳定（3 张截图逐字节相同）。详见 §12.12 与 docs/milestones/evidence/P1d-a1-firstboot-citron.txt。
- audit-web 已用 Citron -g 装载 b0b1（预编译 NRO -> NSP）成功（窗口标题含 1.0.1、picker UI 渲染、boot 行 010047410000B0B1）→ NRO->NSP 链路对 K2NX 实证通过。
- 建议 audit-web 用 b0b3（CJK 修复版）做一次 CJK 复测；用 A1（010047410000b0b2）做首启解包 + 手柄操作验证。

### 12.10 §9 未验证项更新（U11-U14）

| # | 项 | 状态 |
| --- | --- | --- |
| U11 | A1 首启解包（romfs:/game -> sdmc:/kirikiri/haruno + .marker） | **已验证关闭**（Lead 在 Citron，2026-10-30 06:53-06:54）：5 romfs ok → 5b galnx payload → 22 文件/2737 MiB 拷贝（14 s，0 failed）→ marker pilot01-r1 → autostart data.xp3 → title.ks；详见 §12.12 |
| U12 | DBI MTP 安装 2.9 GB NSP 的耗时与失败模式 | 未验证（无真机；模拟器侧 Citron 直接 -g 加载不涉及安装） |
| U13 | 3.4 GiB 档 NSP 在 Citron/真机的装载内存峰值 | 未验证（本轮未启动 Citron） |
| U14 | 中文 NACP 名称/中文路径兼容 | 未做（A1 暂用 ASCII 名称；MAX_PATH 与 ANSI 代码页风险见 §8） |
- 另：nstool v1.9.2 无法解析 hacBrewPack CNMT（-t cnmt 报 Invalid extended header size），CNMT 细节字段（TitleId/Version/ContentInfo 哈希）未做工具校验；结构合法性已由 PFS0/NCA 头/romfs round-trip 间接验证。

### 12.11 v0.2 证据增补（入库：docs/milestones/evidence/）

| 文件 | 内容 |
| --- | --- |
| P1d-a1-final-nsp.txt | A1 输入/命令/指标/产物/NCA 头/round-trip/限制 |
| P1d-scale-tiers.txt | 三档 + 3400 + A1 汇总表与结论 |
| P1d-romfs-roundtrip.txt | 200/3400/2860/K2NX-fixed/A1 的全量 round-trip 与 22 payload 哈希表 |
| P1d-cjk-rootcause.txt | CJK 根因证据链与修复验证 |
| P1d-scale3400-nstool.txt | 3400 NSP 的 PFS0/NCA 头/fstree 完整列举 + nstool CNMT 限制 |
| P1d-elf-nso-headers.txt | r2/合成 ELF 程序头、NSO 头、elf2nro/elf2nso 源码结构、加载基址解释 |
| P1d-k2nx-repack.log | K2NX 修复版重打日志（7305 B 原文） |
| P1d-artifacts-sha256.txt | 工具/输入/产物/组件哈希清单（版本锁定用） |
| P1d-a1-firstboot-citron.txt | A1 首启解包 Citron 验证（U11 关闭）：运行参数/窗口标题/boot 行/截图哈希/k2s_boot/k2s_log 引用/sdmc 状态（v0.3 增补） |
| P1d-a1-k2s_boot.txt | 首启 k2s_boot.txt 原文（234 B；5 romfs ok / 5b galnx payload / 6 app delegate created） |
| P1d-a1-k2s_log-second-run.txt | 07:01 第二次运行日志副本（7,143 B；"payload pilot01-r1 already extracted"、07:01:39 title.ks） |
| P1d-a1-k2s_log-latest.txt | 07:03 第三次运行日志副本（7,366 B；marker 已存在直接启动） |

大文件（A1 2.9 GB NSP、3.4 GB scale NSP）不入库，路径见 §10.1/§12.11 与 P1d-a1-final-nsp.txt。

### 12.12 A1 自包含 NSP 首启解包验证（U11 关闭，Lead 在 Citron 执行）

- 时间/方式：2026-10-30 06:53-06:54，scripts/citron_run.sh --game E:/galnx-build/pilot-01/out/K2NX-A1-selfcontained-010047410000b0b2.nsp --timeout 700 ...（input steps 在 t=90/180/300 s 各截一帧）；Citron main-0237a9b88，status=loaded，elapsed_s=38。
- 窗口标题：citron Nightly | 0237a9b88 | Kirikiroid2-NX (64-bit) | 1.0.1 | NVIDIA；boot 行：Booting game: 010047410000B0B2 | Kirikiroid2-NX (64-bit) | 1.0.1。
- k2s_boot：5 romfs ok → 5b galnx payload → 6 app delegate created, entering run()（NSP 内 RomFS 挂载 + payload 逻辑执行 + 进入 run()）。
- k2s_log 首启解包：[GALNX] free space check ok: 27563 MiB free for a 2737 MiB payload → first boot: copying 22 payload file(s) → payload copy finished: 22 copied, 0 kept, 0 failed, 2737 MiB total（14 s，约 205 MB/s，audit-engines 独立核算）→ autostarting game from /kirikiri/haruno/data.xp3 → 06:54:43 Scenario loaded : title.ks；0 exception / 0 error。
- 画面：首次窗口先显示 CAUTION/18禁 提示（window.png 1,101,196 B），随后自动进入 title.ks —— 属游戏自身启动序列，不是障碍；t=90/180/300 s 三张标题截图逐字节相同（2,551,781 B，sha256 3fa32cd3f75b0b794cd24335e48fcdd8f24a93981c930c5a7bda939dd20ba9ca，nonblack=0.9008）→ 标题画面稳定 3 分钟。
- SD 状态：sdmc:/kirikiri/haruno/ 顶层 16 项，du -sb 2,870,634,016 B（= game_files.txt 的 bytes=2870634016）；其中 plugin/ 7 个 .tpm 合计 1,066,496 B，顶层文件合计 2,869,567,520 B（与 Lead 记录一致，两口径可对账）；marker .galnx_extracted = pilot01-r1；autostart.txt = /kirikiri/haruno/data.xp3。
- 证据：docs/milestones/evidence/P1d-a1-firstboot-citron.txt（归纳与哈希）+ P1d-a1-k2s_boot.txt（原文 234 B）+ P1d-a1-k2s_log-second-run.txt / -latest.txt（后续运行日志副本）；运行归档 E:/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/citron-harness/runs/20261030-065340-K2NX-A1-selfcontained-010047410000b0b2/（result.json、run.log、window.png、step-*.png）。
- 限制：仅 Citron（模拟器）验证，非真机；U12（DBI MTP 安装 2.9 GB 耗时）/ U13（3.4 GiB 装载内存）/ U14（中文 NACP 名称/路径）仍未验证。
