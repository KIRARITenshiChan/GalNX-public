# P1-c 试点游戏数据审计（只读）

- 任务：task-34（P1-c，试点垂直切片）
- 审计日期：2026-10-29
- 审计员：audit-switch
- 审计对象：`E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气/`（PC 版，KiriKiri2）
- 本文档：`docs/pilot/P1-game-audit.md`（本任务唯一写权限文件；游戏原件全程只读，未启动 Citron，未在真机运行，未修改任何游戏文件）

**方法**：自写只读 XP3 解析器（zlib index 链 + info/segm chunk + UTF-16LE 文件名）解析 14 个原版归档与 4 个汉化归档；SHA-256 全量哈希；PE 头/节表/导入表/字符串扫描；295 个脚本/文本全量抽取后 grep 依赖；K2NX（Kirikiroid2-NX v1.0.1）源码逐点对照；补丁/升级档与根目录哈希比对。

**证据分级**（沿用 `docs/milestones/README.md`）：E1 运行日志 / E2 截图 / E3 哈希或文件结构 / E4 源码或文件内容片段；无法取证标注 **not-verified**。

---

## 0. 结论摘要

| # | 结论 | 证据 |
| --- | --- | --- |
| 1 | **XP3 数据未加密**：14 个原版归档全部可用 zlib 直接解包，`flags=0x80000000`（TVP_XP3_FILE_PROTECTED）只是「禁止提取」标记，内容为明文 Shift-JIS（E4 已验证 startup.tjs/Init.tjs/Parser.tjs 以 `//---` 明文开头）。数据层不需要任何 key 或 xp3filter。 | E3+E4 |
| 2 | **`.sig` 不构成移植阻塞**：K2NX 全源码无任何 `.sig`/签名校验代码（E4 强证据）；原版 `haruno.exe` 字符串中无 SIGNATURE/SHA256/.sig 命中（E1/E4 字符串层）；校验功能由独立工具 `ファイル破損チェックツール.exe`（sigchk）提供。原版启动是否强制校验 **not-verified**。 | E3+E4 |
| 3 | **汉化补丁不可直接移植**：xmoe 私有容器（`data.xm3` + `haruno.xmoe`）+ Windows 注入式加壳 PE（`haruno_chs.exe` / `xmoeParser.dll` / `xmoe_haruno_chs.dll`），补丁不含 `scenario.xp3` 文本替换；K2NX 源码 grep `xmoe` 0 命中，无兼容层。 | E3+E4 |
| 4 | **日文原版是保底主线**：脚本依赖的 `CSVParser`（csvParser.tpm）与 `Storages.fstat`（fstat.tpm）均在 K2NX 内建插件中；未使用 K2NX 已知未移植的 KAGParserEx / json / sqlite / scriptsEx / motion。运行风险集中在 **haruno.cf anti-tamper**、**字体回退**、**plugin/ 下 Windows tpm 自动加载失败是否致命**（未验证）。 | E4 |
| 5 | **字体**：脚本字体为 `メイリオ,ＭＳ ゴシック`，无内嵌 TTF；K2NX 对未知字体名回退 `DroidSansFallback.ttf`（CJK 覆盖）→ 日文可显示、中文回填后理论上可显示（未实测）。 | E4 |
| 6 | **安装版本 = 官方 1.02 + 汉化 V2.0**：根目录 6 个 1.02 文件与升级档 1.02 的 sha256 全部一致；根目录 8 个汉化文件与汉化补丁 V2.0 的 sha256 全部一致。 | E3 |
| 7 | **汉化作者明确禁止移植**（原文「禁止提取文本 / 禁止移植 / 禁止以任何方式用于商业目的」）→ 中文路线只能自研文本回填，且存在法务风险，不作为 P1 目标。 | E3 |
| 8 | 对 GalNX 的直接价值：本作可作为「KiriKiri2 多 xp3 + 插件 + anti-tamper + .sig」四要素齐全的**最坏情况样本**；manifest / engine adapter 需新增 §9 字段才能忠实描述它。 | 本文 §9 |

**结论对路径选择的影响**（对应 `docs/pilot/README.md` §5）：路径 A（重建 K2NX + romfs 首启解包）在数据层没有障碍；路径 B 亦可行；路径 C（krkrsdl2）在插件/anti-tamper 上的证据尚未取得，风险更高。汉化不进入 P1 范围，R4 维持「中文作为后续研究项」。

---

## 1. 游戏档案

### 1.1 基本信息

| 项 | 值 | 证据 |
| --- | --- | --- |
| 游戏目录 | `E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气/` | 目录列表 |
| 目录大小 | 约 3.6 GB（其中 14 个原版 xp3 合计 2,869,566,751 B；汉化/字体/补丁副本另计） | E3 求和 |
| 主程序 | `haruno.exe` 3,655,680 B，sha256 `fdc6782bab1086b9833c8b76eab19936adc63d2522e4481024f29decf8a6d96f`；PE Time/Date 2013-03-30；字符串含 `TVP(kirikiri) for win32` | E3+E4 |
| 引擎 | **KiriKiri2**（Kikyou ADV system，作者 Kazuyuki Uchino，脚本头 `Data : 2008/04/03`） | E4 |
| ADV 脚本层 | `sys_source/*.tjs` 30 个 + `macro/*.ks` 6 个，全部在 data.xp3 内 | E3+E4 |
| 剧情脚本 | `scenario.xp3` 236 条（235 个 `.ks` + 1 个 `.soc`） | E3 |
| 规模 | 14 个归档共 20,000+ 条目；语音 720 MB+、图像 1.7 GB+、影片 164 MB | E3 |
| 插件体系 | `plugin/` 下 8 个 Windows PE（`.tpm` / `.dll`），每个带 212 B `.sig` | E3 |
| 签名体系 | 每个原版 xp3 旁 212 B `.sig`（`-- SIGNATURE - SHA256/PSS/RSA --` + base64） | E3+E4 |
| 反篡改 | `haruno.cf`（769 B）必须存在且含四个 `hk*` 空值选项，否则 Init.tjs 主动退出 | E4 |
| 官方版本 | **1.02**（已应用官方升级档） | E3 |
| 汉化状态 | 汉化补丁 V2.0（xmoe）已应用到根目录 | E3 |
| 存档 | `savedata/krenvprf.kep` 80 B（偏好）；运行时存档由引擎写入 `savedata/` | E3+E4 |

### 1.2 原版归档（14 个 xp3 + 14 个 .sig）

下表 SHA-256 为完整 64 hex（E3 实测；`.sig` 与同名 xp3 成对，哈希见 `hash_full.txt` 报告）。

| 文件 | 大小(B) | SHA-256 | 条目数 | 内容 |
| --- | --- | --- | --- | --- |
| `data.xp3` | 198,550 | `15707da93ad08e82ac8db012d4c4d713a58b342833878f99ac17cd7405366415` | 37 | 脚本引擎核心（sys_source/macro/startup.tjs） |
| `scenario.xp3` | 1,551,254 | `b07ed66c9eee9f8f9587bed67d55ec8283460de705b39bc62b19f4cadd491b19` | 237 | 剧情 .ks 脚本 |
| `image00.xp3` | 22,230,877 | `9b4117f6ac83afe83b3cf398c82abba241c676ad464414e4cd210b0fc3cb5e65` | 141 | UI/图标 png |
| `image01.xp3` | 542,381,164 | `8285fc1d362a8553029418fe68225e581081805a247a247da8bc593722b0155f` | 221 | CG/立绘 |
| `image02.xp3` | 472,173,601 | `73c54d2887c97fa22c398d1b235fc6b97c40f4ab0bf45175e65a39b1dca599da` | 703 | CG/立绘 |
| `image02_2.xp3` | 74,766,214 | `5c396c7376de9b7b8b719d0b175dbade4f4a24c3d60f271898c3901ab789fc64` | 124 | 1.02 追加图像 |
| `image03.xp3` | 31,429,614 | `b95dda50401d245c2dca61791281f1904d16d829d5eb606f4c286c4b3232ff7b` | 123 | 事件 CG |
| `image04.xp3` | 646,837,304 | `a89bdf9aade10c656fa2b5254b5033c5046e00492d6b5fb619596180f9591e81` | 1755 | CG/立绘（最大） |
| `image06.xp3` | 14,762,304 | `e6b9f07ac64f23da14b110b1cba62610dead654129b3b7ff67f5b1b5eed14e1c` | 51 | 27 png + 23 csv |
| `media.xp3` | 110,513,170 | `ee24984680b6a47089044d7669663d11772d870b09c6d0e582b95f3efd00a702` | 222 | 201 ogg + 20 sli |
| `movie.xp3` | 164,394,346 | `0118480c7adfb2788c2d5fcbf37003ea8b8580f49b07e07c07aad6bf69545c19` | 3 | logo.mpg + opening.mpg |
| `voice01.xp3` | 17,431,512 | `fa10a3d537c82a73e88b81128fe97cc25d8ecc6acebf5fd0bc81cff007444ab5` | 382 | 语音 ogg |
| `voice02.xp3` | 717,704,696 | `55ef1c310b3337915655863a2c738e0c49202848b59fd0b640d5e32daf287a6d` | 14027 | 语音 ogg（最大条目数） |
| `voice02_2.xp3` | 53,192,145 | `63988dff208c153968b9e0edb7dd9c2732af6479650116c5ba9a01d371fec874` | 1113 | 1.02 追加语音 |

每个归档另有同名 `.sig`（212 B）。`.sig` 清单：data/scenario/image00/image01/image02/image02_2/image03/image04/image06/media/movie/voice01/voice02/voice02_2，共 14 个。

### 1.3 程序与工具文件

| 文件 | 大小(B) | SHA-256 | 说明 |
| --- | --- | --- | --- |
| haruno.exe | 3,655,680 | `fdc6782bab1086b9833c8b76eab19936adc63d2522e4481024f29decf8a6d96f` | 原版主程序（TVP KiriKiri win32，2013-03-30） |
| エンジン設定.exe | 10,752 | `029a1be44b2e0f7a5fb79b484335a6739711579ae7c4c87815f95ef26f560cbd` | 引擎设置工具（2003 年代码风格） |
| ファイル破損チェックツール.exe | 588,800 | `142878442629bd70c778ada6046fd30f2f64a1f3c47424b30e53461a8bdd5cf3` | 文件损坏检查/签名校验工具（sigchk） |
| ファイル破損チェックツール.ini | 889 | `a22f3d2d6fc9bde0abb9cf212b51bf65075431d00981100750551e75605c61fb` | sigchk 配置 |
| haruno.cf | 769 | `5fef39fd848185f7c257cd0fdaeef0eb3e3cff524c6eb10f4ca6cbdd7be91bcf` | 引擎配置 + anti-tamper 校验对象 |
| dummy.png | 44,322 | `82411bca82d8c2b1b877e6c3e046f747a5359afb2f8b5ba176c05a655d79f40e` | 占位图 |

### 1.4 汉化文件（xmoe 体系）

| 文件 | 大小(B) | SHA-256 | 作用（推断，E3+E4） |
| --- | --- | --- | --- |
| data.xm3 | 375,939 | `67736e7a8554cfb4cc71cfe4fd36090f92ceb7bb637479d84ec6ac7f098e6378` | xmoe 编译资源包（头 `X'moe.Data.Compiled.Res.2.0`） |
| haruno.xmoe | 2,695,766 | `2be0542ba2eab5a9051630995c0355eb7e1ca6b52abd49017581511e416c4146` | xmoe 容器（头 `XMOE`） |
| haruno_chs.exe | 2,041,344 | `a79454543eb4e8e67f7785257f794bf4379a9fcb014fb28fa586db6a32d36d35` | 汉化入口 exe（加壳，仅 kernel32/comctl32 导入） |
| xmoeParser.dll | 2,792,448 | `a8168b8cf9fec08cf22cced0c1f5433c2696601a0fe5aca11b13927f75159c59` | xmoe 解析器（加壳） |
| xmoe_haruno_chs.dll | 3,965,952 | `a95776148adc62e9795ea0028fea8ad202cf76007adc3df4a75c39e27456e118` | 汉化逻辑 DLL（加壳） |
| image00_chs.xp3 | 22,985,356 | `bf4f9efb733556f4aaee869db9d12291d03a6e2fc2597cd39c8fba440e1f7366` | 汉化 UI 图（140 png，无 protected flag） |
| extra_chs.xp3 | 195,056 | `0aa9350102f53d05ca9940647bfbfbe79c1020455ecfcf126c1d66a77f03f97a` | 附加资源（dummy.png） |
| movie_chs.xp3 | 197,246,119 | `b5d16a741f5fc1e3c2514e798c269bf71ba2b1be8778806f56a589a52ee996e7` | 汉化影片（OP 等 3 条） |

### 1.5 字体

| 文件 | 大小(B) | SHA-256 | 说明 |
| --- | --- | --- | --- |
| simhei.ttf | 9,751,960 | `336a838f4a78e150826be608dae69de59d50948c3d2b71760e096ae764154bdc` | 黑体（汉化补丁附带，根目录，非 xp3） |
| simsun.ttc | 15,323,200 | `ff7d69bfa6588d3fdedbddbe3a29ac11f0c50236723ee72a9ea49ec3e2553f5d` | 宋体（同上） |

> 注意：simhei/simsun 为商业字体，不具备随包分发许可；GalNX 仓库与 NSP 产物都不得包含它们。

### 1.6 安装版本判定（E3）

- **官方 1.02 已应用**：根目录 `data.xp3`、`image02_2.xp3`、`image03.xp3`、`image06.xp3`、`scenario.xp3`、`voice02_2.xp3`（含各自 `.sig`）与 `补丁/升级档/haruno_update_1.02/data/` 下同名文件 **sha256 全部相同**。
- **1.01 未采用**：`haruno_update101` 中 `data.xp3` 198,568 B、`image02_2.xp3` 8,455,200 B、`image06.xp3` 14,090,525 B、`scenario.xp3` 1,439,792 B、`voice02_2.xp3` 2,496,547 B，均与根目录不同。
- **汉化 V2.0 已应用**：根目录 8 个汉化文件（§1.4 前 8 项）与 `补丁/汉化补丁/…-汉化补丁V2.0/` 下同名文件 **sha256 全部相同**；补丁 `Readme.txt` 未复制到根目录。
- 结论：当前根目录是 **1.02 + 汉化 V2.0** 的组合；日文原版主程序 `haruno.exe` 与汉化入口 `haruno_chs.exe` 并存。

---

## 2. 打包形态：XP3 归档

### 2.1 格式结构（E4）

解析依据：自写解析器 + K2NX 源码 `src/core/base/XP3Archive.cpp` / `XP3Archive.h` 交叉验证。

- **Header**：11 B magic `58 50 33 0D 0A 20 0A 1A 8B 67 01`（`XP3\r\n \n\x1a\x8bg\x01`）+ 8 B LE `index_ofs`（相对归档 base offset；归档可嵌在 MZ 内，扫描 16 字节对齐找 magic）。
- **index 链**：读 `index_ofs` 处 1 B `flag`；`method = flag & 0x07`（0=RAW，1=ZLIB），`continue = flag & 0x80`（`TVP_XP3_INDEX_CONTINUE`）。ZLIB 分支 = 8 B compressed_size + 8 B uncompressed_size + zlib 数据；RAW 分支 = 8 B size + 原始 index 数据。带 0x80 时继续读下一个 index_ofs（链式）。
- **index 内容** = 若干 chunk：4 B 名称（`File`/`info`/`segm`/`aldr`）+ 8 B LE size + payload。
- **info chunk**：`flags`(u32，`TVP_XP3_FILE_PROTECTED = 1<<31`) + `orgsize`(u64) + `arcsize`(u64) + `namelen`(i16) + `name`(UTF-16LE)。
- **segm chunk**：N × 28 B（`flags` u32、`start` u64、`orgsize` u64、`arcsize` u64）；segment `flags & 0x07`：0=RAW，1=ZLIB。
- **aldr chunk**：`filehash` u32。

### 2.2 实测索引链

全部 14 个原版归档的 index 链形状一致：

```
chain = [(index_ofs = 23, flag = 0x80, size = 0),
         (index_ofs = <归档尾部>, flag = 0x01, size = <zlib index 长度>)]
```

已记录的具体值：`data.xp3` 第二个 offset = 196,910、zlib index 6,184 B；`scenario.xp3` 第二个 offset = 1,545,081、zlib index 33,622 B。其余归档未逐项记录（按同一模式解析成功即可）。

### 2.3 protected flag 实测与含义（关键）

- `data.xp3` 37 条中：仅第 1 条 157 B 的日文版权警告文本 `flags = 0x00000000`；其余 36 条（`macro/*.ks` 6、`startup.tjs`、`sys_source/*.tjs` 30）**全部 `flags = 0x80000000`**（`TVP_XP3_FILE_PROTECTED`）。
- `scenario.xp3`：237 条中 236 条为 `0x80000000`。
- 但解包内容为**明文**：`startup.tjs`（474 B）、`Init.tjs`（16,297 B）、`Parser.tjs`（62,581 B）解压后首字节为 `2F 2F 2D 2D`（即 `//---` 注释头），按 Shift-JIS 可直接阅读。
- **结论**：本作的 protected flag 只是「禁止提取」的声明标记，**不是加密**；不需要 key、不需要 `xp3filter.tjs`。数据层对任何守法实现完全可读。

### 2.4 各归档内容统计（E3）

| 归档 | 条目 | 扩展名分布 | 解压后总大小(B) |
| `data.xp3` | 37 | ks/tjs | 966,220 |
| `scenario.xp3` | 237 | 236 ks + 1 soc | 6,662,830 |
| `image00.xp3` | 141 | 140 png | 22,225,946 |
| `image01.xp3` | 221 | 220 png | 542,374,454 |
| `image02.xp3` | 703 | 702 png | 473,388,200 |
| `image02_2.xp3` | 124 | 123 png | 74,787,913 |
| `image03.xp3` | 123 | 122 png | 31,445,337 |
| `image04.xp3` | 1,755 | 1754 png | 646,793,136 |
| `image06.xp3` | 51 | 27 png + 23 csv | 14,779,671 |
| `media.xp3` | 222 | 201 ogg + 20 sli | 111,004,758 |
| `movie.xp3` | 3 | 2 mpg + 1 条目 | 164,393,125 |
| `voice01.xp3` | 382 | 381 ogg | 18,877,621 |
| `voice02.xp3` | 14,027 | 14026 ogg | 771,119,968 |
| `voice02_2.xp3` | 1,113 | 1112 ogg | 57,421,776 |
| `image00_chs.xp3（汉化）` | 140 | 140 png | 22,981,888 |
| `extra_chs.xp3（汉化）` | 1 | png | 194,953 |
| `movie_chs.xp3（汉化）` | 3 | mpg | 197,245,937 |

### 2.5 目录布局（XP3 内路径）

- `sys_source/`：30 个引擎级 tjs（Init、Parser、ConfigObject、MainWindow、MessObject、LogObject、SaveLoadObject、SoundObject、MovieObject、CgmodeReplay 等）；
- `macro/`：6 个 ADV 宏（start、title、logo、eyecatch、userFix、userMacro）；
- `scenario/`：按角色/章节分组，如 `@_共通/@0000A_Z01.ks`、`A_菜乃花/A0001A_A01.ks`（名字为 UTF-16LE 日文）；
- `image0x`：png（UI、CG、立绘）；`media`：ogg + `.sli` 循环点；`voice`：按场景 ogg；`image06`：csv 表数据。

---

## 3. 引擎与脚本依赖分析

### 3.1 启动链（E4）

- `startup.tjs`（474 B）全文只有一句：`Scripts.execStorage("sys_source/Init.tjs");`；头部注释 `// Note : BASE ADV SYSTEM` / `// Data : 2008/04/03` / `// Creator : Kazuyuki Uchino`。
- `sys_source/Init.tjs`（16,297 B）负责加载 `ArchiveStruct` 列表、设置存档目录/存档编码/字体/宏路径，并执行 anti-tamper 校验（§3.3）。
- `Parser.tjs:22`：`class Parser extends KAGParser {` —— KAG 解析器由引擎内置的 `KAGParser` 类提供。
- **引擎判定**：KiriKiri2 + **Kikyou ADV system**（Kazuyuki Uchino 的 kikyou.info ADV 系统），不是 KAG3 成品游戏；本作不使用 KAGParserEx / KAGEX 扩展。
- 全量 grep（295 个抽取脚本）：`KAGParserEx` 0、`json` 0、`sqlite` 0、`Motion` 0、`scriptsEx` 0、`KAGEX` 0、`Plugins.link` 0、`plugincall` 0、`.tpm` 0、`xp3filter` 0。

### 3.2 Init.tjs 关键配置（E4）

| 配置 | 值 | 影响 |
| --- | --- | --- |
| `Savefolder` | `System.exePath + "savedata/"` | 存档目录 = 游戏目录下 `savedata/`；K2NX 下映射到 `sdmc:/kirikiri/<game>/savedata/` |
| `CnfName` | `"haruno.cf"` | 配置文件；anti-tamper 校验对象（§3.3） |
| `scSaveMode` | `"z"` | 存档使用 zlib 压缩 |
| `scSaveDataId` | `a293c327-5c1a-4767-909e-693bde4d7342` | 存档命名空间 |
| `Storages.addAutoPath(Savefolder)` | 启用 | 存档目录加入搜索路径 |

**ArchiveStruct（15 项，按序 addAutoPath `name>`）**：

| # | 归档 | 本安装是否存在 |
| 1 | `scenario.xp3` | 是 |
| 2 | `image01.xp3` | 是 |
| 3 | `image02.xp3` | 是 |
| 4 | `image02_2.xp3` | 是 |
| 5 | `image03.xp3` | 是 |
| 6 | `image04.xp3` | 是 |
| 7 | `image04_2.xp3` | 否（预留补丁位） |
| 8 | `image05.xp3` | 否（预留补丁位） |
| 9 | `media.xp3` | 是 |
| 10 | `movie.xp3` | 是 |
| 11 | `voice01.xp3` | 是 |
| 12 | `voice02.xp3` | 是 |
| 13 | `voice02_2.xp3` | 是 |
| 14 | `image00.xp3` | 是 |
| 15 | `image06.xp3` | 是 |

- 判空逻辑：`useArchiveIfExists(name)` 只在文件存在时 `Storages.addAutoPath(arcname + ">")`，因此多出来的 `image04_2` / `image05` 缺失不报错。
- 追加 autoPath：`System.exePath + "/"`、`System.exePath + "data/"`、`sys_source/`、`macro/`；再追加场景子目录 `name + "@_共通/"`、`name + "A_菜乃花/"`（以及 B_このみ、C_花梨、D_雨音、E、Replay 等）。

### 3.3 anti-tamper 校验（运行硬前置，E4）

`Init.tjs` 在启动早期读取 `System.exePath + "haruno.cf"`，逐行校验以下四个 option **必须按此顺序出现且值为空**：

```
hkcontroller=""
hkeditor=""
hkwatch=""
hkconsole=""
```

- 失败（缺失、顺序错、值非空、文件读不到）→ `System.inform("正常に起動できませんでした"); System.exit();`，即启动即退出。
- `haruno.cf` 实测 769 B：注释头 + 上述四个 `hk*` 行（其中 `hkcontroller` 之后还夹 `hkpad` 等）+ 若干其他键 + `drawthread`（值用 PUA 转义写法，等于 `auto`）。
- **移植含义**：NSP 自包含解包/只读 romfs 方案必须把 `haruno.cf` **原样**放到解包后的游戏目录（System.exePath），不能改写、不能省；任何「清理配置」都会让游戏启动即退。
- 该机制是 K2NX 能跑通的前提之一：K2NX 的 app path 就是选中的游戏目录，因此只要目录完整复制即可满足。

### 3.4 插件依赖表（脚本证据 → Windows 插件 → K2NX 对应）

| 依赖 | 脚本证据（E4） | Windows 插件 | K2NX 对应（E4） | 结论 |
| --- | --- | --- | --- | --- |
| `CSVParser` | `Utility.tjs:322`：`var CSV = new CSVParser();` | `csvParser.tpm` | 内建 `csvParser.cpp`，注册 TJS 类 `CSVParser` | 满足 |
| `Storages.fstat` | `LogThumbObject.tjs:373`、`MainWindow.tjs:2245/2416/2467` | `fstat.tpm` | 内建 `fstat/main.cpp`（`TemporaryFiles`） | 满足 |
| ogg 语音/BGM | media/voice 均为 ogg（无 `wuvorbis` 字面） | `wuvorbis.tpm`、`wumsadp.tpm` | OpenAL + Ogg Vorbis/Opus/WAV 解码（README What works） | 预期满足（not-verified） |
| mpg 影片 | `movie.xp3`（logo.mpg、opening.mpg） | `krmovie.dll` | FFmpeg 3.2 MPEG-1 支持（README What works） | 预期满足（not-verified） |
| LayerExImage / WindowEx / Extrans | 类名 0 命中（未直接使用） | `layerExImage.tpm`、`windowEx.tpm`、`extrans.tpm` | 已编译进 K2NX（`--whole-archive kr2plugin`） | 无影响 |
| Affine | `Affine.tjs:21`：`var pluginName = "affine";` | 引擎内建插件 | 引擎内建 | 满足 |
| LayerExMovie / AlphaMovie / perspective / dirlist / saveStruct / varfile | 0 命中 | 同名插件 | 部分已编译 | 无影响 |

**插件加载机制**：脚本层**没有** `Plugins.link`/`plugincall`（0 命中），全部由引擎自动加载 —— 与 K2NX `TVPLoadPluigins()` 行为一致。

### 3.5 字体引用（E4）

- `userFix.ks:196`：`var stFONTNAME = "メイリオ,ＭＳ ゴシック";`
- `userFix.ks:312`：`var nSAVETEXT_FONTNAME = "メイリオ,ＭＳ ゴシック";`
- 全部 UI 层（`ConfigObject.tjs`、`LogObject.tjs`、`MessObject.tjs`、`SelectObject.tjs` 等 40 处）通过 `.font.face = stFONTNAME` 引用；`scenario` 脚本中 `font=` 标签 0 条（字体全局配置）。
- 无 `System.addFont`、无 `.ttf/.ttc/.otf` 资源引用 → **依赖 Windows 系统字体**（Meiryo / MS Gothic）。
- `simhei.ttf` / `simsun.ttc` 是汉化补丁附带（根目录），原版脚本不引用。

### 3.6 K2NX 插件自动加载与风险（E4）

K2NX 源码 `src/core/base/win32/PluginImpl.cpp:523-589`：

- `TVPSearchPluginsAt(list, folder)` 用 `TVPListDir` 列目录，只收 `.tpm`；
- `TVPLoadPluigins()`（:558）先 `TVPLoadInternalPlugins()`，再取 `exepath = ExtractFileDir(TVPNativeProjectDir...)`，依次扫描 `exepath`、`exepath/system`、`exepath/plugin`，按文件名 ASCII 排序后逐个 `TVPLoadPlugin()`，并打 `"(info) Loading <name>"` 日志。

**本作影响**：`plugin/` 下 8 个 Windows PE 会被 K2NX **自动尝试加载**：

| 文件 | 说明 | Switch 预期 |
| --- | --- | --- |
| csvParser.tpm / fstat.tpm / extrans.tpm / layerExImage.tpm / windowEx.tpm | PE（Windows DLL 形态） | 加载失败（无 PE loader），但 K2NX 已有同名内建插件 → 功能不受影响 |
| krmovie.dll / wuvorbis.tpm / wumsadp.tpm | PE | 加载失败；功能由 FFmpeg/OpenAL 内建能力替代 |

**未验证（关键）**：加载失败是仅打印错误还是 fatal（K2NX 未移植插件时 README Known issues 提到「需要的游戏可能报错」，但未说明加载失败是否中止启动）。→ §8 U2。若致命，处理方式：解包后删除/重命名 `plugin/` 目录；或在 K2NX 侧加白名单跳过。

### 3.7 K2NX 已知未移植插件与本作影响

| K2NX 未移植（README Known issues） | 本作是否使用 | 影响 |
| --- | --- | --- |
| KAGParserEx | 否（0 命中） | 无 |
| E-mote / motion player | 否 | 无 |
| scriptsEx | 否 | 无 |
| layerExRaster / shrinkCopy | 否（类名 0 命中） | 无 |
| json / sqlite | 否 | 无 |

结论：**本作不属于「需要未移植插件」的游戏**；这一项风险已排除（E4）。

---
## 4. 签名（.sig）语义

### 4.1 结构实测（E3）

212 B 文本文件，CRLF 行尾，四行：

| 行 | 长度 | 内容 | base64 解码 |
| --- | --- | --- | --- |
| 1 | 33 字符 | `-- SIGNATURE - SHA256/PSS/RSA --` | 主题/魔数行（32 字符） |
| 2 | 65 字符 | base64 | 48 B |
| 3 | 65 字符 | base64 | 48 B |
| 4 | 45 字符 | base64 | 32 B（SHA-256 长度） |

- 合计解码 128 B；从头部标签推断为 **RSA-2048 PSS 签名 + SHA-256 摘要** 的组合（两段 48 B 与一段 32 B 的精确切分未进一步验证）。
- `.sig` 内**不含文件名**，靠同名约定与对应归档配对。

### 4.2 覆盖范围（E3）

| 类别 | 数量 | 清单 |
| --- | --- | --- |
| 原版 xp3 签名 | 14 | data / scenario / image00 / image01 / image02 / image02_2 / image03 / image04 / image06 / media / movie / voice01 / voice02 / voice02_2 |
| 插件签名 | 8 | plugin/ 下每个 `.tpm`/`.dll` 各一个 |
| 汉化文件签名 | 0 | data.xm3、haruno.xmoe、*_chs.xp3、xmoe*.dll 均无 `.sig` |

### 4.3 原版引擎是否强制校验（not-verified）

- `haruno.exe` 字符串扫描：无 `SIGNATURE` / `SHA256` / `.sig` 命中（E4 字符串层）→ 没有证据表明主程序内嵌验签逻辑。
- 独立工具 `ファイル破損チェックツール.exe`（588,800 B）字符串命中：`File signature checker`、`CORE_SIG_______`、`RELEASE_SIG____`、`sha256`、`-- SIGNATURE - SHA256/PSS/RSA --`、`Invalid signature file format`、`sigchk.exe`、`Digital signature/file integrity check tool` → **校验功能由该工具提供**（可由用户手动执行），而不是启动必经路径。
- 是否在启动时静默校验：**not-verified**（需要动态调试或删改文件后启动观察；本轮不启动 Citron、不动原件，无法验证）。

### 4.4 K2NX 行为（E4 强证据）

K2NX 源码全量 grep `.sig` / `SIGNATURE` / `PSS` / `RSA` / `verifySig` / `VerifySignature`：**没有任何读取或校验 `.sig` 的代码**（命中仅为 ZIP/RAR 内部 signature 字段、窗口消息 signature、`crypt_mode_sig` 等无关项）。

→ **K2NX 完全忽略 `.sig`**：删除、篡改、重打包 xp3 都不会被引擎发现（工程上「可运行」，但破坏了原版完整性声明）。

### 4.5 结论与风险

- 签名体系**不构成移植阻塞**（E4）。
- 若未来做数据变换（重打包 scenario.xp3 回填中文、改名替换 `image00.xp3`/`movie.xp3`），`.sig` 会失配——K2NX 不管，但：①原版 `ファイル破損チェックツール` 会报错；②对外分发时应如实声明「数据已修改」。
- 保留 `.sig` 原件的意义：可追溯官方升级档（1.02）与汉化补丁替换了哪些文件。

---

## 5. 汉化可行性

### 5.1 汉化构成与安装状态（E3）

| 组成 | 文件 | 角色（推断） |
| --- | --- | --- |
| 入口程序 | `haruno_chs.exe`（2,041,344 B） | 汉化版启动器（加壳：随机节名、仅 kernel32/comctl32 导入） |
| 注入 DLL | `xmoeParser.dll`（2,792,448 B）、`xmoe_haruno_chs.dll`（3,965,952 B） | xmoe 容器解析 + 文本替换（均加壳） |
| 资源容器 | `haruno.xmoe`（2,695,766 B，头 `XMOE`）、`data.xm3`（375,939 B，头 `X'moe.Data.Compiled.Res.2.0`） | 编译后的中文资源/文本，**非 XP3** |
| 图像覆盖 | `image00_chs.xp3`（22,985,356 B，140 png） | UI 中文图（与原版 image00 条目数一致） |
| 影片覆盖 | `movie_chs.xp3`（197,246,119 B） | 中文 OP 等影片 |
| 附加 | `extra_chs.xp3`（195,056 B） | 附加资源 |
| 字体 | `simhei.ttf`、`simsun.ttc` | 中文字体 |

- 根目录 8 个汉化文件与补丁 V2.0 同名文件 sha256 **全部一致** → 汉化已安装（§1.6）。
- 汉化 `Readme.txt`（1,017 B，utf-8-sig）要点：
  - 「本补丁基于官方V1.02制作，请在安装汉化补丁前打上官方补丁」；
  - 汉化组 credits（组长 萌喵LOLI酱；程序/压制 萌喵LOLI酱）；
  - **「禁止提取文本 / 禁止移植 / 禁止以任何方式用于商业目的（包括杂志赠品 和 某宝）」**。

### 5.2 xmoe 机制：为什么不能直接搬到 Switch（E3+E4）

1. **不是 xp3 文本替换**：汉化补丁不含 `scenario.xp3`，中文文本在 `haruno.xmoe` / `data.xm3` 私有容器里，由 `xmoeParser.dll` 在运行时替换/注入。
2. **Windows 专用注入链**：`haruno_chs.exe` + 两个 DLL（均加壳：随机节名如 `mvgtifuw`、`oizkhrdv`、`wfbzisab`、`bggfibgi`；导入表仅 kernel32/comctl32；前 200 KB 未检出 UPX/Enigma/VMProtect/Themida/ASProtect/MPRESS 明文字串，具体壳未确认）。Switch/K2NX 没有 Windows PE 加载器、没有 DLL 注入、没有 xmoe 运行时。
3. **K2NX 无兼容层**：K2NX 源码 grep `xmoe` **0 命中**。
4. **图像/影片覆盖件命名不同**：`image00_chs.xp3`、`movie_chs.xp3` 与原版 `image00.xp3`、`movie.xp3` 名字不同，而 `Init.tjs` 的 `ArchiveStruct` 用固定名加载 → 直接复制过去不会被加载。

结论：**汉化补丁在 Switch/K2NX 上完全不可用**。

### 5.3 三档方案评估

| 方案 | 做法 | 技术可行性 | 工作量 | 法务/声明风险 | 结论 |
| --- | --- | --- | --- | --- | --- |
| A 日文原版（保底） | 原目录原样复制到 `sdmc:/kirikiri/<game>/`，K2NX 直接启动 | 高（数据/插件/字体证据齐备） | 低 | 无（本地自用） | **P1 主线** |
| B 自研中文回填 | 抽取 `.ks` → 翻译 → 回填/重打包 `scenario.xp3`（或做同名 overlay xp3），配合字体默认覆盖 | 中：解析器已有、重打包可做；但需翻译文本，且补丁作者文本在 xmoe 内（要先逆向提取） | 极高 | **高**：汉化组明确「禁止提取文本/禁止移植」；游戏本作文本版权属 Parasol | 技术可行，法务不可行 → 不进入 P1/P3 默认路线，仅作研究记录 |
| C 仅替换图/影 | 把 `image00_chs.xp3` 改名为 `image00.xp3`、`movie_chs.xp3` 改名为 `movie.xp3` 后替换（格式：PNG/MPG，K2NX 支持） | 中：文件名可骗过 `ArchiveStruct`，但 xp3 内部条目名/哈希需与原版一致才被按路径命中（未验证） | 低 | 中（仍分发汉化组素材） | 可选演示增强；正文仍日文，优先级低，**不入库** |

### 5.4 法务要点（必须写入结论）

- 汉化补丁作者**明确禁止移植**（原文见 §5.1）→ GalNX 不应把「移植中文版」作为公开目标；即使技术上做，也只能是用户本地的私人研究，且不得分发汉化文本/素材。
- 游戏本体与数据版权属 Parasol；NSP 若含游戏数据，**只能本地构建、不入库、不分发**（与 `docs/pilot/README.md` R6 一致）。
- `simhei.ttf` / `simsun.ttc` 为商业字体：不得随 NSP 或仓库分发。

### 5.5 汉化结论

**P1 只做日文原版**；中文路线记录为「不可直接移植 + 禁止移植声明 + 自研回填成本极高」，不阻塞 M1/P1 验收。若用户后续坚持中文，正确路线是自建翻译流水线（`xp3` 解析 → `.ks` 文本抽取 → 翻译 → 重打包），而不是复用 xmoe 补丁。

---

## 6. 字体与 CJK 渲染

### 6.1 原版依赖（E4）

- 游戏字体 = `メイリオ,ＭＳ ゴシック`（Meiryo 优先，MS Gothic 后备），无内嵌字体文件、无 `System.addFont`。
- 因此原版在 Windows 上依赖系统字体；Switch 没有这两个字体。

### 6.2 K2NX 字体回退链（E4，`src/core/visual/FontImpl.cpp`）

`TVPInitFontNames()` 候选顺序：

1. 用户配置 `default_font`；
2. `TVPGetAppPath() + "default.ttf"` / `.ttc` / `.otf` / `.otc`（即**游戏目录**下的字体，优先级高）；
3. Switch 分支：`TVPEnumFontsProc("file://./switch/kirikiroid2/default.ttf")`（SD 卡全局默认字体），再加载 romfs 内的 `DroidSansFallback.ttf`（构建时从官方 APK 提取，含 CJK）；
4. 游戏目录 `<game>/fonts/` 下所有字体；
5. 若仍无 → 弹窗 `Could not found any font...`。

`TVPCreateFontStream(fontname)`：找不到请求字体名时回退 `TVPDefaultFontName`（= 候选列表最后一个 = `DroidSansFallback`）。

**含义**：本作的 `メイリオ,ＭＳ ゴシック` 在 K2NX 上会走回退 → 使用 DroidSansFallback（含日文假名/汉字/CJK 覆盖）。

### 6.3 中文显示结论

- 日文原版：DroidSansFallback 覆盖日文假名与常用汉字 → **可显示**（E4 推断；截图验证属 P1-a，not-verified）。
- 若将来回填中文：同一字体覆盖简体中文 → 理论上可显示；但字形风格与原文排版会有差异。
- 未验证：`stFONTNAME` 是逗号分隔的多字体名，K2NX 的 `TVPFindFont` 是否按逗号拆分成 fallback 列表（源码未见拆分逻辑，可能整体当做一个名字 → 直接落到默认字体）。

### 6.4 建议

| 需求 | 做法 | 备注 |
| --- | --- | --- |
| 不改游戏、最省事 | 依赖 DroidSansFallback 回退 | 默认行为，零配置 |
| 统一字体风格 | 放 `sdmc:/switch/kirikiroid2/default.ttf`（全局）或 `<game>/default.ttf`（单游戏） | 优先于回退；用户自备字体，不入库 |
| 强制指定 | 改 `userFix.ks` 的 `stFONTNAME` 后重打包 `data.xp3` | 改动数据，`.sig` 失效（K2NX 不校验）；不建议 P1 做 |
| 中文补丁字体 | 不建议使用 simhei/simsun | 商业字体，分发风险 |

---

## 7. K2NX 运行约定（与本作相关，E4）

| 约定 | 内容 | 对本作影响 |
| --- | --- | --- |
| 路径风格 | 引擎只见 Unix 风格路径；`sdmc:` 前缀会被 TJS 当 media type 报错（源码 `SwitchUtils.cpp:99-104` 注释），libnx 把前导 `/` 映射到 SD 卡 | 自包含解包路径必须写 `/kirikiri/haruno` 这类 Unix 路径，不能写 `sdmc:/...` 传给引擎 |
| app path | `TVPGetAppPath()` 返回选中的游戏目录（`ExePath` 分支被 `#if 0` 禁用） | `savedata/`、`haruno.cf`、`xp3filter.tjs`、`default.ttf` 都以游戏目录为根 |
| 存档 | `Savefolder = System.exePath + "savedata/"`，`scSaveMode = "z"` | 存档写 `/kirikiri/<game>/savedata/`；需 SD 卡可写（K2NX `TVPCheckStartupPath` 恒 true） |
| 日志 | `sdmc:/switch/kirikiroid2/k2s_log.txt`（滚动 `.prev.txt`）、`k2s_boot.txt`、`k2s_crash.txt` | 真机/模拟器排障与 U2 验证的证据来源 |
| 系统对话框 | `TVPShowSimpleMessageBox` 用系统错误小程序，多按钮也只返回第一个 | 游戏内 Yes/No 确认可能总选第一个 → 存档覆盖等操作需谨慎 |
| 输入 | K2NX 默认：A=推进/确认、B=取消/右键、十字键=选择、`-`=菜单；左摇杆=鼠标指针 | 本作 Kikyou 层的右键隐藏文字层、滚轮历史等桌面操作需实际验证映射（not-verified） |
| 运行模式 | README 要求 **title-takeover**（按住 R 进 hbmenu），applet mode 内存不足 | 模拟器无此限制；真机必须按此方式启动 |

---

## 8. 未验证项清单

| 编号 | 事项 | 现状 | 验证方法 | 影响 |
| --- | --- | --- | --- | --- |
| U1 | 原版 exe 启动是否强制校验 `.sig` | haruno.exe 字符串无证据 | 删除/改动某 xp3 后启动原版；或调试器断点 | 低（K2NX 不校验，不影响移植） |
| U2 | K2NX 加载 `plugin/` 下 Windows tpm 失败是否致命 | 源码确定会自动尝试加载，失败后果未知 | 跑游戏后看 `k2s_log.txt` 的 `(info) Loading` 后续是否有 fatal | **高**：若致命需删 plugin/ 或改 K2NX |
| U3 | 游戏能否进标题/正文 | P1-a 负责 | Citron 自动输入 + 截图 | **高**（验收项） |
| U4 | 存档可写性与 `savedata/` 生成 | 未测 | 游戏内存档后检查目录 | 中 |
| U5 | DroidSansFallback 渲染日文/中文效果 | 源码推断 | 截图 | 中 |
| U6 | `stFONTNAME` 逗号列表是否被拆分 | 源码未见逻辑 | 截图/调试日志 | 中 |
| U7 | 从 xmoe 容器提取汉化文本的可行性 | 未做（补丁加壳） | 逆向工具 | 中文路线专用 |
| U8 | `image00_chs.xp3`/`movie_chs.xp3` 改名替换是否被加载 | 未做 | 改名为原版名后跑 | 低（方案 C） |
| U9 | 音频/影片实际播放（wuvorbis/wumsadp/krmovie 替代） | 未测 | P1-a 运行观察 | 中 |
| U10 | K2NX 预编译 NRO 与源码 commit 的对应关系 | 未确认（README 只写 v1.0.1） | 查仓库 tag/构建记录 | 中（版本锁定） |
| U11 | 游戏目录含 3.4 GB 数据时 Citron/真机的加载时间与内存 | 未测 | P1-a/P3 观测 | 中 |

---

## 9. 对 manifest / engine adapter 字段的建议

本作暴露了 KiriKiri2 引擎的多项「运行时契约」，现有 `engine` 段字段不足以描述。建议在 engine adapter 描述或 manifest 的 `engine.options` 中引入以下字段（向后兼容，全部可选）：

| 字段 | 类型 | 取值/示例 | 依据 | 说明 |
| --- | --- | --- | --- | --- |
| `adapter` | enum | `kirikiroid2-nx`（已在 game-manifest.schema.json 枚举内） | K2NX | 播放器适配器 |
| `engine.pinned_commit` | 40 hex | K2NX 源码 commit（not-verified，见 U10） | — | 版本锁定 |
| `target_kind` | enum | `nro` | K2NX 本身是 NRO | 数据外置形态；自包含走 NSP 另议 |
| `content_layout.mode` | enum | `sdmc` | app path = 游戏目录 | 数据放 SD 卡 |
| `content_layout.destination` | string | `sdmc:/kirikiri/<game-id>/` | README 安装说明 | 运行副本目录 |
| `content_layout.entry` | string | `data.xp3` | 文件选择器点 data.xp3 | 启动入口 |
| `xp3_files` | 有序数组 | 15 项 ArchiveStruct 顺序（见 §3.2） | Init.tjs | 需要支持「预留位缺失」 |
| `xp3_allow_missing` | bool | `true` | useArchiveIfExists | image04_2 / image05 允许缺失 |
| `required_plugins` | 数组 | `["csvParser","fstat"]` | 脚本证据 | 缺则功能失败 |
| `optional_plugins` | 数组 | `["wuvorbis","wumsadp","krmovie","layerExImage","windowEx","extrans"]` | plugin/ 目录 | 由引擎内建替代 |
| `plugin_dir_policy` | enum | `ignore` / `load` / `fail` | U2 | 控制 SD 卡上 Windows tpm 的处理方式 |
| `config_file` | string | `haruno.cf` | anti-tamper | 必须原样保留 |
| `anti_tamper` | object | `{type: "cf-options", required: ["hkcontroller","hkeditor","hkwatch","hkconsole"]}` | Init.tjs | 解包时必须校验 |
| `save_dir` | string | `<game>/savedata/` | Savefolder | 存档位置 |
| `save_codec` | enum | `zlib` | scSaveMode = "z" | 存档压缩 |
| `fonts.face_list` | 数组 | `["メイリオ","ＭＳ ゴシック"]` | userFix.ks | 请求字体名 |
| `fonts.fallback` | string | `DroidSansFallback.ttf`（K2NX 内建） | FontImpl.cpp | 回退字体 |
| `fonts.user_override` | string | `sdmc:/switch/kirikiroid2/default.ttf` | FontImpl.cpp | 可选用户字体 |
| `chinese_patch` | object | `{status: "unsupported", format: "xmoe", revision: "V2.0", legal_note: "author forbids porting"}` | §5 | 显式记录不可用 |
| `runtime_mode` | enum | `title-takeover` | K2NX README | 真机运行要求 |

示例（可放入 `examples/` 供 CLI plan 使用，YAML 片段）：

```yaml
engine:
  adapter: kirikiroid2-nx
  pinned: "K2NX v1.0.1"
  target_kind: nro
options:
  content_layout:
    mode: sdmc
    destination: "sdmc:/kirikiri/haruno/"
    entry: data.xp3
  xp3_files:
    - scenario.xp3
    - image01.xp3
    - image02.xp3
    - image02_2.xp3
    - image03.xp3
    - image04.xp3
    - image04_2.xp3
    - image05.xp3
    - media.xp3
    - movie.xp3
    - voice01.xp3
    - voice02.xp3
    - voice02_2.xp3
    - image00.xp3
    - image06.xp3
  xp3_allow_missing: true
  required_plugins: [csvParser, fstat]
  plugin_dir_policy: ignore
  config_file: haruno.cf
  anti_tamper:
    type: cf-options
    required: [hkcontroller, hkeditor, hkwatch, hkconsole]
  save_dir: savedata/
  save_codec: zlib
  fonts:
    face_list: ["メイリオ", "ＭＳ ゴシック"]
    fallback: DroidSansFallback.ttf
  chinese_patch:
    status: unsupported
    format: xmoe
    revision: "V2.0"
```

**对 `plan_build` 的建议步骤**（供 engine contract 参考，不含实际构建）：

1. `fetch-engine`：取 K2NX v1.0.1 NRO（预编译）或按源码 commit 构建；
2. `stage-content`：把游戏目录原样复制到 `sdmc:/kirikiri/<game>/`（保留 `.sig`、`plugin/`、`haruno.cf`；若 `plugin_dir_policy=ignore` 则移动 `plugin/` 到备份目录）；
3. `verify-content`：校验 `data.xp3` 与 14 个 xp3 的 sha256（与 §1.2 一致）以及 `haruno.cf` 四个 `hk*` 行顺序；
4. `plan-verify`：`verify_artifact` 检查 NRO 头（NRO0@0x10）、大小（42,338,934 B）与 sha256；
5. （P1-d）`package-nsp`：自包含打包时把游戏数据放入 romfs，首启解包到 sdmc 后再按步骤 2-3 校验。

---

## 10. P1-c 验收对照

| 任务要求 | 交付 | 状态 |
| --- | --- | --- |
| ① XP3 索引解析器列出 data/scenario/image00 条目与压缩状态 | §2（14 个归档全解析，含条目数/大小/扩展名、index 链、protected flag） | 完成（E3+E4） |
| ① 抽取 .ks/.tjs 文本、找 startup.tjs / KAG 主脚本 / 插件引用 / xp3filter | §3（startup.tjs → Init.tjs 链、Parser extends KAGParser、插件依赖表、xp3filter 0 命中） | 完成（E4） |
| ② .sig 语义（是否强制校验、K2NX 能否通过、xp3filter 绕过） | §4（结构、覆盖、原版未验证、K2NX 不校验、本作无需 xp3filter） | 完成（E3+E4；U1 not-verified） |
| ③ 汉化可行性（补丁结构、xp3 替换 vs 注入、Switch/K2NX 可行性、日文原版保底） | §5（xmoe 注入式不可用、方案 A/B/C 评估、法务声明） | 完成（E3+E4） |
| ④ 字体/CJK（脚本字体、simhei/simsun 是否 xp3 引用、K2NX FreeType 覆盖） | §6（メイリオ/ＭＳ ゴシック、无内嵌、DroidSansFallback 回退） | 完成（E4；渲染 not-verified） |
| ⑤ 产出 `docs/pilot/P1-game-audit.md`（游戏档案/插件依赖/汉化/sig/字体/未验证/manifest 字段建议） | 本文 | 完成 |

**对 P1 上游任务的输入**：

- P1-a（audit-web）：U2/U3/U5/U9 需要运行证据；日志位置 `sdmc:/switch/kirikiroid2/k2s_log.txt`。
- P1-b（audit-engines）：本作对 K2NX 的硬约束是 `haruno.cf` anti-tamper、`plugin/` 加载策略、字体回退；romfs 首启解包需保持目录结构与文件名。
- P1-d（audit-package）：3.4 GB 数据如何放进 NSP romfs（NCA 大小限制）与首启解包策略；本作是「大 romfs」最坏样本。

---

## 11. 参考与证据文件

**仓库内文档**：

- `docs/pilot/README.md`（P0 侦察、里程碑、路径假设、风险登记）
- `docs/builds/007-onscripter-nx.md`（对比参照：另一 KiriKiri 系引擎的构建/运行契约）
- `docs/audit/01-engines.md`（引擎审计中的 KiriKiri 系条目）
- `docs/milestones/README.md`（E1-E4 证据分级定义）

**本任务临时证据（在 `E:/galnx-build/pilot-01/`，不入库）**：

| 文件 | 内容 |
| --- | --- |
| `xp3.py` | XP3 解析器（index 链/zlib/raw/UTF-16LE 名/protected flag/read_entry） |
| `extract/` | 295 个抽取文件（data 36、scenario 236、image06 23 等） |
| `report_hash_sig.txt` | 根文件哈希、补丁/根比对、`.sig` 原始结构、补丁目录树 |
| `hash_full.txt` | 53 个文件完整 sha256（含补丁 V2.0 文件） |
| `report_scripts.txt` / `report_scripts2.txt` | startup.tjs、Init.tjs、macro 全文与插件/字体 grep |
| `report_files.txt` | 根清单、PE 头、xmoe/xm3 头、haruno.cf 全文、补丁树 |
| `report_k2nx_plugins.txt` / `report_k2nx2.txt` / `report_k2nx3.txt` / `report_k2nx4.txt` | K2NX 插件机制、字体回退、app path、PluginImpl 源码摘录 |
| `report_plugins_scan.txt` / `report_pluginimpl.txt` | 脚本插件二次扫描、PluginImpl.cpp 原文 |
| `report_sig_xmoe.txt` | `.sig` 精确结构、xmoe/PE 头、加壳节名 |
| `k2nx-src/` | Kirikiroid2-NX 源码快照（只读引用，787 文件） |

**外部参考**：

- Kirikiroid2-NX v1.0.1 README（`/e/galnx-build/pilot-01/k2nx-src/README.md`）：安装路径、What works、Known issues、运行模式；
- K2NX 源码关键文件：`src/core/base/XP3Archive.cpp`、`src/core/base/win32/PluginImpl.cpp`、`src/plugins/xp3filter.cpp`、`src/core/visual/FontImpl.cpp`、`src/core/environ/switch/SwitchUtils.cpp`、`src/core/environ/Application.cpp`、`src/core/base/win32/StorageImpl.cpp`。

---

## 12. 变更记录

| 日期 | 版本 | 内容 |
| --- | --- | --- |
| 2026-10-29 | v1.0 | P1-c 首次完整审计：XP3 全解析、插件依赖、.sig、汉化、字体、manifest 字段建议 |
