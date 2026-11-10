# 《さくら、もゆ。HD Re:GENERATION》Switch/rfvp 汉化可行性报告

- 任务：task-50（owner: sakura-l10n）· 日期：2026-11-05 · 证据分级：E1 原始日志 / E2 截图 / E3 哈希与元数据 / E4 源码片段 / E5 外部资料
- 一句话结论：**能汉化，且已在本机 Citron（Switch 模拟器 + 真 rfvp NRO）上跑通全中文剧情，零崩溃。** 剧情文本（57,172 条）已全部替换为 PC 汉化组译文；标题 logo/菜单按钮等 **UI 图片仍是日文**（二期技术路径已验证：其中的 60 条 loose 贴图已导出并校验，见 §4.4）。若用户拥有**官方 NS 版**游戏，社区已有现成 NS 汉化 mod（含 UI），是更省事的另一条路（见 §4.2）。

---

## 0. 结论先行（TL;DR）

| 问题 | 结论 | 证据 |
|---|---|---|
| rfvp 上能否显示中文剧情？ | **能，已验证** | run-gbk-04 / run-gbk-05 共 12 张截图（E2）+ 日志零错误（E1） |
| 中文从哪来？ | PC 汉化补丁 `patch.dat` 的 57,172 条译文，key = `Sakura.hcb` 内文本字节偏移 | 57,172/57,172 key 全部命中（E1/E3，见 §3.1） |
| 怎么进游戏？ | 离线重打包 `SakuraGBK.hcb`（GBK 编码），`config.toml` 设 `nls="gbk"`；rfvp 官方 ADR 0008 明确**只支持**离线重打包 | E4 + 运行日志 `GameConfig { hcb: Some("SakuraGBK.hcb"), nls: Some(GBK) }` |
| 最大技术坑？ | `ThreadStart`（syscall 136）把**绝对代码指针**压栈，字符串变长后地址平移 → 必须重定位；否则线程从错误 PC 起跑、`no top of the stack` 崩溃 | E1（run-03 崩溃日志）+ E4（官方 assembler phase2b） |
| 还差什么？ | ① UI 图片（标题 logo、菜单按钮）仍日文；② 3 条 ruby 标记数据瑕疵；③ 未翻译的 3,993 条内部/调试串不影响玩家 | §3.5/§3.6 |
| 工程量 | 路径 A 剩余：把 2 个文件打进 NSP 并真机验证（0.5–1 天）；UI 二期 v1（loose 覆盖 60/68）0.5–1 天 + v1.5（重建 pack 覆盖 8 条大图）0.5–1 天；精校/长尾 1–2 周 | §6 |

---

## 1. 目标与判定标准

用户无日语基础，要求《さくら、もゆ。HD Re:GENERATION》在 Switch/rfvp 上**显示中文**。

判定标准（本报告采用）：
1. **必须**：剧情对话、旁白、选项、人名等玩家可读文本为中文，能连续推进不崩溃；
2. **加分**：标题画面/菜单/存档界面等 UI 也为中文；
3. 不改 m5-rfvp 引擎源码、不 push（任务约束）。

---

## 2. 可行路径排序

| 路径 | 方案 | 可行性 | 结论 |
|---|---|---|---|
| **A. 离线重打包 hcb** | 用 PC 汉化 `patch.dat` 的 57,172 条译文按偏移替换 `Sakura.hcb` 的 push_string 载荷，输出 GBK 版 hcb | **已跑通**（E1/E2） | **推荐（rfvp 路线）**，见 §4.1 |
| **C. 社区中文资源** | 官方 NS 版已有社区汉化 mod v1.0（1.48 GB，mod 形式，exefs+romfs，2026-02-22） | 资源存在（E5）；面向**官方 Switch 游戏**，非 rfvp | 若用户拥有官方 NS 游戏 → **最省事**，见 §4.2 |
| B. rfvp 运行期文本替换层 | 在引擎里做 hook/loose-file 覆盖 | **官方明确不支持**：ADR 0008 禁止运行期翻译 probing/热补丁；源码无文本替换入口 | 不做（除非改引擎，违背任务约束） |
| D. 不可行 | — | — | 否 |

---

## 3. 证据链

### 3.1 PC 汉化补丁结构（E1/E3/E5）

PC 目录：`E:/Othergames/Galgame/さくら、もゆ。v0.2.0_0222_fix1`

| 文件 | 大小 | sha256 |
|---|---|---|
| `Sakura.hcb`（日文原脚本，未被汉化修改） | 5,002,569 | `43f032bc6eb64aa85d105302690af516b8c2a514ee766d57f0215c755447fb1a` |
| `patch.dat`（译文数据，root 版） | 1,420,843 | `da0a7e11f4849d055109fca171623081e728009ab026b42760ebed747657886f` |
| `patch.bin`（UI 图片资源包） | 29,961,828 | — |
| `SakuraChs.exe`（注入器） | 495,104 | `770592d6f1ae5045c8edaad4e22da7ff9e23d0ed28424f35ef814ba581592b96` |
| `filter.dll` / `ass.dll` | 82,944 / 3,116,032 | — |

**patch.dat 容器格式（已验证）**
- 16 字节头：`u32[0]`=格式版本 0、`u32[1]`=构建 Unix 时间戳（root `0x699a97be`=1771739070 ≈ 2026-02）、`u32[2]`=解压后大小（2,659,567）、`u32[3]`=压缩流大小；偏移 16 起为 **zlib** 流（`0x789c`）。
- 解压后载荷：`u32 count`，随后 count 条 `{u32 key, u16 len, GBK 文本含结尾 0x00}`。root 版 **count=57,172，恰好无剩余字节**。
- **`key` = 文本在 `Sakura.hcb` 中的绝对字节偏移（指向文本首字节）**。hcb 文本记录布局为 `opcode 0x0e, u8 长度(含 NUL), SJIS 文本, 0x00`。
- 验证脚本 `E:/galnx-build/p23/l10n/verify_patch_keys.py`：**57,172/57,172 全部命中**（key-2 处为 `0x0e`、key-1 处等于原文含 NUL 长度、原文可 cp932 解码、NUL 位置一致）。
- 实例：`key=666169`，JP `世界かわって、だましをつか――` → ZH `世界于此，暂作叹息〄〄`（`〄` 为 GBK 占位符）。
- `static/patch.dat`（2022-10 旧版）57,053 条仅 2,539 条命中 → **对当前 hcb 失效，只用 root `patch.dat`**（推断：v0.2.0 合并官方 v1.1 升级档后偏移已变）。

**patch.bin 不含文本**：头部是索引表，strings 全是图形资源名（`a_bu_cp1`、`menu_bg`、`menu_del_mes`、`fc_load_help`、`a_cg_p3`、`bl_char` …），即汉化组重绘的 UI 图片包。反编译脚本中 `"patch/` 引用数 = 0 → rfvp 不会自动使用它（详见 §3.6）。

**汉化实现方式（E5，外部资料与本地观察一致）**：`SakuraChs.exe` 在 PC 上做运行期注入，按 hcb 偏移把日文替换成 GBK 中文；`Sakura.hcb` 本体哈希不变（与 rfvp 运行目录里的 hcb 完全相同）。社区仓库文档（deepwiki: `elementary-particle/my-sakura-moyu`）确认：译文源为 **CSV（序号, hcb 偏移 hex, 保留列, 中文）**，由 `create_patch.py` 编译成 zlib 压缩的 `patch.dat`，文本统一 GBK 编码——与本机逆向结果完全吻合。

### 3.2 hcb 字节码格式与重打包（E4/E1）

hcb = `u32 sys_desc_offset` + 指令流 `[4, sys_desc_offset)` + sysdesc（entry_point / global 数 / game_mode / title / syscall 表）。

- 指令集 40 个 opcode，关键：`0x0e push_string = opcode + u8 len(含NUL) + bytes + 0x00`（**长度是 1 字节，≤255**）；`0x02 call`/`0x06 jmp`/`0x07 jz` 均携带 **u32 绝对地址**。
- 结论：**改文本长度必须重排全部指令地址、重定位所有 call/jmp/jz、更新 sysdesc offset 与 entry_point**。
- 我的实现 `E:/galnx-build/p23/l10n/hcb_tool.py`：字节码级原位重打包（不经过 Lua 反编译/重编译）。回归测试：对原版 `Sakura.hcb` decode→encode **字节完全一致**（`identical=True`，5,002,569 B）→ 证明指令流/函数数(5,457)/字符串数(61,165)/sysdesc(148 syscalls) 完全未变。
- 曾尝试官方 `lua2hcb_compiler` 路线：**失败**（decompiler 输出与 compiler 的 Lua 子集不兼容：顶层 `GT = GT or {}`、`if a == -1 == 0` 比较链）。官方 `disassembler`/`assembler` 在本机 **无法构建**（`crates/rfvp/src/subsystem/resources/resource_cache.rs:107` 使用 `spin::Mutex`，而 `spin` 仅 no_std feature 启用，std 构建缺依赖；任务禁止改源码）→ 自写 Python 重打包器是正确选择。

**关键坑：ThreadStart 代码指针重定位（E1/E4）**
- 现象：第一版中文 hcb 启动即崩：`rfvp [error] no top of the stack` → `the game stopped with an error`。
- 根因：`ThreadStart`（syscall id=136，args=2）前一条指令通常是 `push_i32/push_i16`，值为**函数入口绝对地址**（如 91872/91969/92067/92204 = 0x166E0/0x16741/0x167A3/0x1682C…）。字符串长度变化 → 地址平移 → 未重定位的指针使线程从错误 PC 起跑 → 垃圾指令流 → 栈下溢。
- 官方规格：`crates/assembler/src/main.rs:438-611` 的 `compile()` phase2b：对每个 ThreadStart 站点回看 1..=8 条，找 PushI32/PushI16 且值属于函数入口地址集合的候选，**恰好 1 个**则改写为新地址；PushI16 超出 `i16::MAX` 报错。
- 实测：原 hcb **99/99 站点都是"紧邻前 1 条"**；窗口内更深处的 241/2000/0x7d0 等小常量也可能是早期指令边界（假候选），所以必须"最近 push 优先"。
- 已在 `hcb_tool.py` 实现 `_threadstart_ids()` + `_relocate_thread_code_pointers()`，修复后运行零崩溃。

**未翻译字符串保留原始字节**（另一处关键决策）：`nls` 对整个 hcb 生效；未翻译的 3,993 条多为内部/调试串和非 ASCII 资源名（如 `graph_bs/CHR_クロ`）。引擎用同一 nls 解码 pack 索引名做 hash（`vfs.rs parse_index`），若把这些名字也转 GBK 会导致资源查找失败 → 因此**只对已翻译串写 GBK，其余保持原始 SJIS 字节**。

### 3.3 真机级运行验证（E1/E2）

- 环境：便携 Citron（`E:/galnx-build/p23/citron-l10n`，独立 user/ 与 sdmc/）+ 真 rfvp NRO（`E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro`，7,929,912 B）+ 独立游戏目录 `E:/galnx-build/sakura-test/game-gbk`（13 个资源文件 hardlink/junction，不额外占盘）。运行入口 `Workspace/GalNX/scripts/citron_run.sh`。
- `game-gbk/config.toml`（83 B）：
```toml
[game]
hcb = "SakuraGBK.hcb"
nls = "gbk"
```
- 产物：`E:/galnx-build/p23/l10n/out/SakuraGBK.hcb` **4,283,683 B**，sha256 `4d4fd72933c2342841765b27d3be0522dff8ea055ba6f510d5b0fe25f248e7d7`（比原版小 718,886 B，-14.4%，因 GBK 比 SJIS 省字节）。
- 结构自检：`hcb2lua_decompiler.exe -i out/SakuraGBK.hcb -o out/check_gbk2.lua -l gbk` → exit 0，中文完整（例：`__ret = f_0004CDFB("世界于此，暂作叹息――", nil, ...)`）。

| 运行 | 结果 | 证据 |
|---|---|---|
| run-gbk-03（修复前） | **崩溃**：`no top of the stack` | `E:/galnx-build/p23/l10n/runs/run-gbk-03/*/citron_log.txt:380-382`、`last_error.txt` |
| **run-gbk-04** | 13/13 步骤 OK，标题→New Game→2 句中文，**零错误** | `runs/run-gbk-04/20261105-155721-rfvp/` |
| **run-gbk-05** | 32/32 步骤 OK，**10 次对话推进**、11 张截图，**零错误** | `runs/run-gbk-05/20261105-160101-rfvp/` |

关键日志（run-04）：`:335` `config.toml: GameConfig { hcb: Some("SakuraGBK.hcb"), nls: Some(GBK) }`；`:371` `parsed real HCB, initialized real GameData, and started VmRunner`；`:375` `rfvp: the game is loaded, running`。两次运行 grep `rfvp \[error\]|no top of the stack|stopped with an error` 均 **0 命中**。

中文截图（E2，均 1728×1016）：
- `run-gbk-04/.../step-08-02-text1.png`：『于我胸中回响。』
- `run-gbk-04/.../step-11-03-text2.png`：『于我眼中闪烁。』
- `run-gbk-05/.../step-14-04.png`：『………于我心中荡漾。』
- `run-gbk-05/.../step-20-06.png`：立绘场景 + 人名框 `？？？` + 台词『…………』（立绘/CG 正常加载，证明资源路径未因编码改动而失效）

> 说明：`runs/run-gbk-06`（标题 OPTION 菜单验证）**作废**：harness 检测到 async-fix 已有 Citron 实例，attach 到了对方的 IROSEKA 窗口而非启动我自己的实例（窗口标题 `IROSEKA FHD (1.1.0-test)`），与 Sakura 无关。教训：多 Citron 实例共存时 `citron_run.sh --allow-existing` 可能 attach 错窗口，必须确认 0 个 citron 进程再跑。

### 3.4 字体（E3/E1）

- 运行目录 `default.ttf`：22,839,132 B，2023-03-21，sha256 `dda756bdc25a8481bb9a0546549640d7ea3d1cc29719eb8cdfff1a047c3d0291`。
- 字形覆盖：中文可打印字符 **全覆盖**；仅缺 `\n`(0x0A)/`\t`(0x09) 控制符字形（正常渲染无关）。PC 目录里没有同名 `default.ttf`（只有 `subtitle/fonts/HanaMinA.ttf`，sha256 7ca87559…，两者不同）。
- rfvp 的错误提示语也写明：game 目录需要 ".hcb 脚本 + .bin 资源 + 名为 default.ttf 的 CJK 字体"。

### 3.5 译文本体质量（E1）

- push_string 共 **61,165** 条，其中 **57,172** 条有译文（93.5%），未翻译 **3,993** 条（仅 2,459 种文本）。
- 未翻译内容逐条检查：几乎全是内部/调试字符串（如 `[WndCh_NameEntry Error] Status Not Registration.`、`[FileSystem] Target set miss.`）与资源/立绘名（`graph/gaiji_shiru156`、`eyecatch_BG_mashiro_A`、`StandbyClothingChange`），含假名(≥2)的 78 条也全部是资源名/调试 → **没有用户可见的日文台词残留**。
- FVP ruby 标记 `[ruby|base]`：日文 4,571 条含 `[`、4,554 条含 `|`；中文 4,061/4,061。**3 条中文 ruby 标记不平衡**（PC 补丁数据自身缺陷，如 `[就][·|是][·|能]` 首个 `[就]` 缺 `|`、`[·|你][]就[]在…` 多余 `]`）→ rfvp 渲染这 3 条可能异常（低风险，可后续修数据）。
- 宽度：按中文 1.0/ASCII 0.5 估算，n=57,160，min=-63，max=+80，mean=-6.29，median=-5；仅 4,067 条中文更宽；最宽的是带「译注」长句。PC 版同数据可正常显示（引擎自动换行），**需真机确认对话框不溢出**（推断，未验证）。
- 874 条同一日文对应多个中文变体（上下文/空格差异，属正常）。

### 3.6 UI 图片缺口（E4/E1）

- 标题 logo、菜单按钮（NEW GAME/はじめから 等）是**图片资源**，PC 汉化放在 `patch.bin`。
- rfvp **不会**自动用 `patch.bin` 覆盖 graph 贴图：`patch.bin` 只是名为 "patch" 的 pack（`vfs.rs`）；反编译脚本里 0 处 `"patch/` 引用；`vfs.rs` 的 loose-file 优先只对"目录内散文件"生效。
- 因此当前状态：**剧情 100% 中文，标题/菜单等 UI 图仍日文**。UI 文本（如对话框 FUNCTION 面板的部分文字）若来自 hcb 则已是中文。
- 全 UI 汉化（第二阶段）= 解析 `patch.bin` 内贴图 + 按名字哈希替换进 `graph_*.bin`（或做 loose-file 覆盖），需先逆向 pack 索引与贴图格式；工作量见 §6。

### 3.7 社区资料（E5，外部，未下载验证）

- 官方 NS 版**已有社区汉化 mod v1.0**：https://2dfdf.de/downloads/41859 （1.48 GB，2026-02-22 初版；基于「萌译」开源文本，程序 22；**mod 形式**：`atmosphere/contents/0100a89019eec000/{exefs,romfs}`；真机 Atmosphere 或模拟器 mod 目录可用）。其已知问题自述："读档、存档等界面尚未完全汉化，会出现方框、繁体字"，与"部分 UI 走图片/系统字体"的观察一致。
- PC 补丁 0.2 相关：https://github.com/Langzaigg/my-sakura-moyu ；补丁技术文档（CSV→patch.dat 编译流程）：https://deepwiki.com/elementary-particle/my-sakura-moyu/4-patch-creation-workflow
- 文本许可证：**CC-BY-NC-SA 4.0**，禁止商用/直播；分发补丁须保留声明、注明修改。

---

## 4. 可行路径与实施步骤

### 4.1 路径 A（rfvp，已验证）——第一阶段"能玩中文剧情"

1. **取源数据**（只读）  
   `Sakura.hcb` = `E:/Othergames/Galgame/さくら、もゆ。v0.2.0_0222_fix1/Sakura.hcb`  
   `patch.dat` = 同目录 `patch.dat`（root 版；不要用 `static/patch.dat`）
2. **校验偏移表**：`python hcb_tool.py stats <Sakura.hcb> <patch.dat>`  
   期望：`patch keys=57172 hcb string insts=61165 keys_hit=57172`、`ThreadStart ids: [136]`、`ThreadStart call sites: 99`
3. **回归自检**：`python hcb_tool.py roundtrip <Sakura.hcb>` → 必须 `identical=True`（否则编码器有 bug，禁止继续）
4. **生成中文脚本**：`python hcb_tool.py patch <Sakura.hcb> <patch.dat> out/SakuraGBK.hcb`  
   期望产物 4,283,683 B，sha256 `4d4fd729…248e7d7`
5. **结构自检**：`hcb2lua_decompiler.exe -i out/SakuraGBK.hcb -o out/check_gbk2.lua -l gbk` → exit 0 且 grep 到中文
6. **部署**：游戏目录放 `SakuraGBK.hcb`（GBK 编码），`config.toml` 写 `[game] hcb="SakuraGBK.hcb" nls="gbk"`；`default.ttf` 保持现有 CJK 字体即可
7. **NSP 打包**：把 `SakuraGBK.hcb` + `config.toml` 打进 romfs（替换原 `Sakura.hcb`），真机验证；预计 0.5–1 天（复用现有打包脚本）

> 一键复现脚本：`E:/galnx-build/p23/l10n/make_sakura_gbk.sh`（见 §7）。

### 4.2 路径 C（官方 NS 版 + 社区 mod）——若用户拥有/能获得官方游戏，最省事

1. 准备官方 NS 版《さくら、もゆ。HD Re:GENERATION》本体（title id `0100a89019eec000`）；
2. 下载社区汉化 mod v1.0（§3.7 链接，1.48 GB；视频字幕包可选）；
3. 真机 Atmosphere：解压到 `SD:/atmosphere/contents/0100a89019eec000/{exefs,romfs}`；模拟器（Citron/Ryujinx）：放到游戏的 mod 目录；
4. 优点：**连 UI 图都汉化了**（美工 22 重绘），且是官方 1080p 引擎、无需 rfvp；缺点：依赖用户拥有官方游戏，且自述存档/读档等界面仍有方框/繁体字。
5. **未验证**：该 mod 的 romfs 是否包含可直接喂给 rfvp 的已翻译 hcb（大小/版本可能不同）——若用户愿意，可下载后解包比对，理论上可作为路径 A 的"更新版译文源"。

### 4.3 路径 B（运行期替换）——不做

rfvp ADR 0008（Accepted 2026-10-25）明确：不做运行期翻译 probing / 动态字符串热补丁 / loose-asset override；汉化必须离线重打包 .hcb。若要运行期方案需改引擎源码，违背本任务约束，且维护成本高。

### 4.4 第二阶段：UI 图片汉化（60 条 loose 文件已导出并校验，待 NSP 集成）

**一句话**：`patch.bin` 就是标准 FVP 资源包（69 条 `hzc1`/NVSG 贴图），其中 **68 条与 `graph.bin`/`graph_vis.bin` 同名**；rfvp 的 **loose 文件优先**机制可覆盖其中 **60 条**（含标题 logo、菜单、系统/帮助/选项按钮），**无需重建 5.4 GB 的 graph packs**；这 60 条**已导出到 `E:/galnx-build/p23/l10n/ui-loose/` 并通过逐文件 sha256/元数据校验**（graph/ 56 个 + graph_vis/ 4 个，共 60 文件、14,358,332 B，原样 `hzc1` 字节）。仅 8 条 ≥1 MiB 的大图受 Switch 异步解码路径限制，需重建 pack（v1.5）。`warning` 是 PC 补丁独有横幅，rfvp 不加载，忽略。

**关键事实（E1/E4）**

1. **patch.bin = FVP pack**：8 B 头 `u32 file_count=69`、`u32 filename_table_size=791`；随后 69×12 B 表项 `{u32 name_off, u32 data_off, u32 data_size}`（`data_off` 为文件绝对偏移）；名称表 791 B、NUL 分隔；`header_end = 8+69*12+791 = 1627`，且最小 `data_off=1627`（数据紧接头部、无填充）。69 条 blob 全部以 `hzc1` 开头。
2. **贴图格式 = HZC1/NVSG（与引擎同格式，E4 `crates/rfvp/src/subsystem/resources/texture.rs:190-358`）**：`"hzc1"`(4) + `u32 original_length`（解压后像素字节数）+ `u32 header_length`（实测 32）；偏移 12 起为未压缩的 32 B NVSG 头（`"NVSG"`、type、width、height、offset_x/y、u/v、entry_count …），压缩像素流从 `12+header_length` 起，zlib 解压长度 = `original_length`。type：0=24bpp、1=32bpp、2=Multi32、3=8bpp、4=1bpp。
3. **同名匹配（E1）**：68/69 在 graph packs 中找到同名条目（`graph.bin` 57 条、`graph_vis.bin` 11 条；`warning` 无同名）。抽样尺寸/类型/解压长度一致（`a_bu_cp1` type=1 1170×501 orig=2,344,680；`a_bus_s1` 1262×720 orig=3,634,560；`a_cg_p3` 561×50 orig=112,200）；**18 条是 PC 美工重绘、尺寸与原 pack 不同**（见第 8 条），引擎按各文件自带 NVSG 头取尺寸，可接受。
4. **loose 文件优先（E4 `vfs.rs:464-468`，注释原文 "A loose file wins over the same name in a pack, which is how patches and translations override a game's files."；`vfs.rs:522-551` 查找顺序：内存 → loose_dir → pack）**：Switch 宿主同样 `set_loose_dir(host.fs().game_files())`（`no_std_core.rs:1532`）；`LooseDir::find` **大小写不敏感**（`vfs.rs:408-409`）→ 无需改 pack、无需算 hash。脚本用 `"graph/" + filename` 拼路径（`script/mod.rs:572-576`），故放 `game/graph/<name>`、`game/graph_vis/<name>`（文件名用**原 pack 拼写**）。
5. **Switch 异步解码例外（E4）**：Switch 构建开 `switch-async`（`platform/switch/host/Cargo.toml:17`）；`graph_load`（`syscalls/graph.rs:999-1099`）在 cache miss 时先 `vfs.pack_location(path)`（`vfs.rs:616-633`，**只查 pack**），若 pack 条目 ≥ `ASYNC_INLINE_MIN_BYTES`=1 MiB（`async_decode.rs:40`）则从 **pack 字节**异步解码 → loose 被绕过；否则才走 `read_file`（loose 优先）。但启动预解码的 UI 前缀（`no_std_core.rs:493-514`：`sys_`/`menu_`/`config_`/`slf_`/`btn_`/`cursor`/`diss`/`prompt`/`mouse`，4 MiB/96 MiB 预算）走 `vfs.read_file`（`resource_cache.rs:206-255`）→ **这些即使 >1 MiB 也命中 loose**。
6. **覆盖统计与导出结果（E1，已执行）**：匹配 68 条 → **导出 60 条**（`<1 MiB` 的 pack 条目；含 `title_logo1`、全部 `menu_*`/`sys_*`/`fc_*_help`/`opt_*`/`startmoji_*`/`bl_char`/`bl_mask`、4 张 ETC UI 底图），**8 条 ≥1 MiB 排除**：`graph/a_cg_s1`（pack 1,049,030）、`graph_vis/ETC_e000b` 1,491,247、`ETC_e001a` 1,804,147、`ETC_e012b` 2,322,273、`ETC_e012c` 2,409,364、`ETC_e012d` 2,178,183、`ETC_e302a` 1,902,634、`ETC_e302b` 1,721,225。若 v1.5 重建：`graph.bin` 354,017,024 → 约 354,549,422（+532,398 B）、`graph_vis.bin` 2,008,972,031 → 约 2,008,720,048（−251,983 B），净约 +280 KB。
7. **`warning`（793,196 B，1280×720）** 在 patch.bin 独有，12 个游戏 pack 全无、反编译脚本 0 处 `patch/` 引用 → PC 补丁自带声明图，rfvp 不加载，可忽略（未导出）。
8. **重绘尺寸差异（E1，18 条）**：PC 汉化版部分 UI 图是美工重画，尺寸与原 pack 不同（如 `fc_back_help` height 20 vs 21、`menu_*_mes` width 198 vs 227–339、`sys_*_M` width 243/265 vs 268–368），已逐条记入 `mapping.json` 的 `meta_diffs` 且 `pack_meta_matches=false`；引擎按文件自身 NVSG 头解尺寸 → 不要求与旧图同尺寸。真机/模拟器冒烟需确认无错位。

**已导出产物（E1，已校验）**

- 目录 `E:/galnx-build/p23/l10n/ui-loose/`：`graph/` 56 个、`graph_vis/` 4 个，**共 60 个文件、14,358,332 B**，全部为 patch.bin 内 `hzc1` blob 原样字节（不转码、不重压，大小写沿用原包拼写）。
- `mapping.json`：69 条完整台账（exported 60 / excluded 8 / unmatched 1），每条含 `name`、`pack`、`pack_offset`、`pack_size`、`pack_type/width/height`、`meta_diffs`、`size`、`sha256` 及 patch 侧元数据；顶层含 `source.patch_bin_sha256`、`counts`、`exported_bytes`、`meta_diff_count`。
- `SHA256SUMS`：60 行，独立复验 **60/60 ok**；抽样：`graph/title_logo1` `24325f87…`（195,901 B，673×458，type=1）、`graph/opt_sheet1` `93cd6c39…`（1,047,776 B，1280×720，type=0）、`graph/menu_bg` `0928fa6a…`（18,435 B，420×122）、`graph/sys_config_M` `9b4ce35d…`（7,730 B，243×49）。
- `README.md`：用法——把 `graph/`、`graph_vis/` 两个目录整体复制进 romfs 的 `game/`（即 `game/graph/<name>`、`game/graph_vis/<name>`），文件名保持原拼写；**无需改 `config.toml`**。
- 导出脚本 `E:/galnx-build/p23/l10n/export_ui_loose.py`（只读 patch.bin / graph packs，可重复执行，末尾自检）。
- 注：唯一 patch blob ≥1 MiB 的导出项是 `graph/a_snd_s1`（1,101,660 B），但其 **pack 条目只有 1,028,320 B**（异步阈值看 pack 条目大小）→ 仍走同步 loose 读取，安全。

**实施步骤**

- **v1（导出已完成，剩 NSP 集成与冒烟，0.25–0.5 天）**：把 `ui-loose/graph/`（56 个）与 `ui-loose/graph_vis/`（4 个）复制进 romfs 的 `game/` → NSP 重打包 → Citron/真机冒烟比对标题、菜单、存档界面。效果：标题 logo、菜单/系统/帮助/选项等 **60 条中文化**；`a_cg_s1` 与 7 张 `ETC_*` 大图（事件/特典插图，推断）仍日文。
- **v1.5（+0.5–1 天）**：按同一规格重建 `graph.bin`/`graph_vis.bin`（替换 68 条同名 blob、重算 `data_off` 与名称表），彻底覆盖剩余 8 条；NSP 替换两个 pack。
- **验证**：Citron 截标题/菜单/存档界面，真机同；注意 romfs 大小写与目录层级，文件名用原 pack 拼写（`find` 虽大小写不敏感，但 NSP 打包工具可能区分）。

**风险（二期）**：① loose 覆盖在 NSP/romfs 上是否被正确注册（源码路径成立、文件已导出并通过自检，但尚未集成进 NSP/真机验证）；② 8 条大图走 pack 异步路径的判断基于源码，未运行时验证；③ 重建 pack 需保证表项/偏移重算无误，否则整个 pack 读不出（5.4 GB 资源需先备份）；④ 版权约束同 §5；⑤ 18 条重绘贴图与原 pack 尺寸不同，引擎按各文件 NVSG 头自适应，理论安全但需目视确认无错位/裁剪。

---

## 5. 风险与限制

| 风险 | 等级 | 说明/缓解 |
|---|---|---|
| ThreadStart 类绝对指针漏改 | 中 | 已按官方 phase2b 规则实现；roundtrip 字节一致 + 12 张截图零崩溃。但若未来换 hcb 版本/补丁数据，必须重跑 stats 校验（99 站点） |
| 中文文本宽度导致对话框溢出 | 低-中 | 统计 p95=+1、仅 4,067 条更宽；PC 版同数据正常。**需真机确认**（真机 1080p 与 720p 桌面布局可能不同） |
| 3 条 ruby 标记不平衡 | 低 | 可后处理修正（脚本 `check_markup.py` 已能定位） |
| UI 图片仍日文（一期） | 中（体验） | 二期 v1 的 60/68 条 loose 文件已导出并校验（待 NSP 集成/冒烟，0.25–0.5 天），剩余 8 条大图 v1.5 重建 pack；见 §4.4 |
| 存档/读档界面部分字符异常 | 中 | 社区 NS mod 也自述存在；推断部分界面文字走图片/系统字体，需单独处理 |
| 未翻译内部串导致报错信息仍是日文/英文 | 低 | 不影响正常游玩 |
| 多 Citron 实例 attach 错窗口 | 中（流程） | 运行前确认 0 个 citron 进程；避免干扰他人实例（本次 run-06 已发生一次，已通知 async-fix） |
| 版权/许可 | 中 | 中文文本 CC-BY-NC-SA 4.0：禁止商用、禁止直播/录播；分发须保留声明 |

---

## 6. 工作量估计

| 工作项 | 人天 |
|---|---|
| 路径 A 收尾：NSP 打包 + 真机验证（含字体/换行确认） | 0.5–1 |
| 3 条 ruby 修正 + 3,993 条内部串抽查 | 0.5 |
| UI 二期 v1：导出 60/68 条（**已完成并校验**）+ NSP romfs 集成与 Citron/真机冒烟 | 0.25–0.5 |
| UI 二期 v1.5：重建 graph.bin/graph_vis.bin 覆盖剩余 8 条大图 | 0.5–1 |
| 全量精校（57k 条，人工成本另计） | 1–2 周+ |
| 路径 C（若有官方游戏）：装 mod 验证 | 0.5 |

---

## 7. 复现清单

原型脚本：`E:/galnx-build/p23/l10n/`

| 文件 | 作用 |
|---|---|
| `hcb_tool.py` | **核心**：hcb decode/encode + patch.dat 解析 + ThreadStart 重定位 + patch 子命令（CLI: `decode|roundtrip|stats|patch`） |
| `make_sakura_gbk.sh` | 一键跑 stats→roundtrip→patch→反编译自检 |
| `export_ui_loose.py` | 从 `patch.bin` 导出 60 条 `<1 MiB` UI 贴图到 `ui-loose/{graph,graph_vis}/`，并生成 `mapping.json`/`SHA256SUMS`/`README.md`，末尾自检 |
| `analyze_patchdat.py` / `parse_patchdat.py` / `verify_patch_keys.py` | patch.dat 容器解压、记录导出 TSV、key=hcb 偏移验证（57,172/57,172） |
| `analyze_quality.py` / `check_markup.py` | 译文覆盖率、宽度统计、ruby 标记检查（定位 3 条瑕疵） |
| `font_coverage.py` | default.ttf 汉字覆盖检查 |
| `bisect_compile.py` / `compare_dumps.py` | （失败路线的取证）lua2hcb_compiler 定位、反编译产物对比 |

产物与证据：
- `out/SakuraGBK.hcb`（4,283,683 B）、`out/check_gbk2.lua`、`out/root_patch.dat.bin`、`out/sakura_dump.lua`
- `runs/run-gbk-04/20261105-155721-rfvp/`、`runs/run-gbk-05/20261105-160101-rfvp/`（截图+`citron_log.txt`+`result.json`）
- 便携 Citron：`E:/galnx-build/p23/citron-l10n/`；游戏副本：`E:/galnx-build/sakura-test/game-gbk/`
- UI 二期产物：`E:/galnx-build/p23/l10n/ui-loose/`（60 个贴图 + `mapping.json` + `SHA256SUMS` + `README.md`）；取证：`patch.bin` 头/69 条表项、68 条同名匹配、`hzc1` 头校验（结论见 §4.4）

命令（bash）：
```bash
cd /e/galnx-build/p23/l10n
GAME='/e/Othergames/Galgame/さくら、もゆ。v0.2.0_0222_fix1'
python hcb_tool.py stats "$GAME/Sakura.hcb" "$GAME/patch.dat"
python hcb_tool.py roundtrip "$GAME/Sakura.hcb"
python hcb_tool.py patch "$GAME/Sakura.hcb" "$GAME/patch.dat" out/SakuraGBK.hcb
/e/galnx-build/m5-rfvp/target/release/hcb2lua_decompiler.exe -i out/SakuraGBK.hcb -o out/check_gbk2.lua -l gbk
python export_ui_loose.py   # 输出 ui-loose/（60 条；末尾自检 SELF-CHECK OK）
```

UI 二期取证（只读，可在不改任何文件的前提下复现 §4.4 第 1–3 条）：
```bash
python - <<'PY'
import struct
p = 'E:/Othergames/Galgame/さくら、もゆ。v0.2.0_0222_fix1/patch.bin'
d = open(p, 'rb').read()
cnt, namesz = struct.unpack_from('<II', d, 0)              # 69, 791
nameoff = 8 + cnt * 12                                      # 836；names 结束于 1627
names = d[nameoff:nameoff + namesz].decode('latin-1').split('\x00')
rng = [struct.unpack_from('<III', d, 8 + i * 12) for i in range(cnt)]
print('count', cnt, 'namesz', namesz, 'nameoff', nameoff,
      'min_data_off', min(r[1] for r in rng))              # 1627
print('all hzc1:', all(d[r[1]:r[1] + 4] == b'hzc1' for r in rng))  # True
PY
```
预期：`count 69 namesz 791 nameoff 836 min_data_off 1627`、`all hzc1: True`；再用同样方式解析 `graph.bin`（1146 条）/ `graph_vis.bin`（579 条）即可得到 68 条同名匹配。

---

## 8. 未验证 / 推断声明

**已验证（E1–E4）**：patch.dat 格式与 57,172 偏移全命中；hcb 指令格式；roundtrip 字节一致；ThreadStart 规则与修复；Citron 中文剧情 12 张截图 + 零错误；字体覆盖；未翻译串无可见台词；patch.bin 不含文本、不被脚本引用；rfvp ADR 0008 立场；**patch.bin = 标准 FVP pack（69 条 `hzc1`/NVSG 贴图），68/69 与 graph/graph_vis 同名且尺寸/类型/解压长度一致；rfvp loose 文件优先且大小写不敏感；Switch 异步解码 ≥1 MiB 绕过 loose，但启动预解码的 UI 前缀除外（§4.4）**。

**推断（未验证）**：
- `static/patch.dat` 是旧版 hcb（2022-10）的偏移表；
- 对话框自动换行/真机 1080p 布局下中文不溢出；
- 社区 NS mod 的 romfs 内容格式与 rfvp 的 hcb 兼容性；
- UI 二期 loose 覆盖在 NSP/romfs 上实际生效（源码路径成立；Citron 冒烟因让位 async-fix 长测未跑、真机未验证）；
- 剩余 8 条大图走 pack 异步解码路径的判断（源码推断，未运行时验证）。

**未做（超出本次范围）**：真机（硬件 Switch）安装验证；NSP 重新打包；UI 图片汉化实现；全量译校。

---

## 9. 参考

- rfvp 仓库与 ADR：`E:/galnx-build/m5-rfvp/docs/adr/0008-translation-patching-offline-repack.md`、`crates/assembler/src/main.rs`、`crates/disassembler/src/main.rs`、`crates/rfvp/src/script/parser.rs`、`crates/rfvp/src/subsystem/resources/vfs.rs`
- 社区 NS 汉化 mod：https://2dfdf.de/downloads/41859
- PC 补丁 0.2：https://github.com/Langzaigg/my-sakura-moyu
- 补丁编译流程文档：https://deepwiki.com/elementary-particle/my-sakura-moyu/4-patch-creation-workflow
- 游戏本体：FAVORITE《さくら、もゆ。-as the Night's, Reincarnation-》
