# P5 · 汉化可行性研究（v0.4）

- 状态：**已完成（模拟器级 PASS，A7 为最终产物）**——2026-10-30 用公开汉化源码重打包 XP3，在 K2NX + Citron 上跑通中文标题菜单与中文正文（CN7 = NRO 形态，证据见 `docs/builds/012-k2nx-cn-content.md` §6）；A6 自包含 NSP 通过 `galnx package nsp verify`（19 checks）与首启冒烟（1.0.5，证据 §7）；**A7** 在 A6 基础上加入中文 OP（`movie_chs.xp3` 的 `opening.mpg` 替换），同样 verify 19 checks + 首启冒烟 PASS（中文标题/正文、0 异常、窗口标题 `Haruno CN (64-bit) | 1.0.6`，证据 §8）。
- 本文 v0.2 是对 v0.1 的**重大更正**：v0.1 判定「中文文本在 `haruno.xmoe` 里、需逆向/运行时抓取」，并记录「PC 中文版本机启动失败」——两处都不成立（见 §2）。
- 相关文档：`docs/builds/012-k2nx-cn-content.md`（实施细节）、`docs/builds/011-k2nx-exit-crash-fix.md`（补丁 F）、`docs/pilot/P4-device-runbook.md`（真机）。

## 1. 资产盘点（历史记录）

游戏目录：`E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气/`

- PC 日文原版：`haruno.exe` 3,655,680 B（`@TVP(kirikiri) for win32` = KiriKiri2 引擎），14 个 xp3 共约 2.87 GB。
- PC 中文版（X'moe 汉化组 V2.0）：`haruno_chs.exe` + `haruno.xmoe`（2,695,766 B）+ `xmoeParser.dll`（2,953,216 B）+ `xmoe_haruno_chs.dll`（7,258,112 B，SDL2 版引擎导出 219 个符号）+ 17 个 xp3（含 `*_chs.xp3`）。
- 中文版与日文版**共用** `data.xp3/scenario.xp3/image0*.xp3` 等主体数据，中文台词由 `haruno.xmoe` + `*_chs.xp3` 提供（Windows DLL 注入方式，Switch 上不可直接复用）。

## 2. 关键发现（v0.1 的两处错误）

1. **中文文本并非只能从 `haruno.xmoe` 逆向获取**。汉化组把**完整汉化源码**公开在 `t-satoru-Studio/haruno_script`：`KR/` 是面向 krkr2 引擎（与 K2NX 同代）的 script/tjs/image 源文件，可直接重打包成 XP3。架构上与「容器解密」无关。
2. **PC 中文版可以正常运行**（用户实机确认，窗口标题「[X'moe汉化组]晴霁之后定是菜花盛开的好天气V2.0」，标题菜单已汉化）。v0.1 记录的「启动即消失」是本机一次误判（进程枚举/窗口时机问题），不代表游戏不可跑。
3. `haruno.xmoe` 的容器加密**仍未破解**（见 §3），但它不再是汉化的必经之路。

## 3. `haruno.xmoe` 容器结构（历史调查，备查）

- 文件 2,695,766 B；magic `XMOE`（0..3）；u32@4 = 242（记录数）；u32@8 = 9696（数据区起始 = 12 + 9684）；索引区 9684 B（= 4 + 242×40）。
- 242 条记录，每条以 16 B 明文魔数 `STmoeSTmoeChu>_<` 开头；记录尺寸 362–38,400 B，payload 总约 2.68 MB；payload 熵 7.9–8.0，无 zlib/gzip/lz4/zstd/7z 特征。
- 记录头偏移 19/22/23 恒为 `0x47 0x12 0xcf`；聚合重复字节检验出现 L=31（0.0154）/L=62（0.0134）弱周期信号（基线 0.0039），疑似 31 字节周期异或/流密码，**未证实**。
- `xmoeParser.dll` 导出仅 `V2Link`/`V2Unlink`（KiriKiri 插件标准入口），strings 不含 `STmoe`/`XMOE` 特征串（可能运行时拼接）。

结论：如果将来要支持「只有中文整合版、没有源码」的其它游戏，仍需走 R1/R2 路线；本作不需要。

## 4. 路线对比与结论

| 路线 | 做法 | 覆盖 | 工作量 | 结论 |
| --- | --- | --- | --- | --- |
| R1 逆向 xmoe 容器 | Ghidra 分析 `xmoeParser.dll` 解密 → 导出对照表 → 引擎替换 | 全量 | L（数人日～1 周） | 本作**不需要**；其它游戏备选 |
| R2 运行时抓文本 | hook 中文版渲染文本 → 对齐日文剧本 | 全量 | M（2–4 人日） | 备用；对齐风险高 |
| R3 仅 UI 汉化 | 复用 `extra_chs.xp3`/`image00_chs.xp3` | 标题/菜单 | S | 覆盖不足，放弃 |
| R4 取现成翻译文本 | 搜公开翻译/对照表 | 视来源 | S–M | 演进为 R5 |
| **R5 公开汉化源码重打包 XP3** | 用 `t-satoru-Studio/haruno_script` 的 `KR/` 重打包 data/scenario/image00 + 自定义 startup | **全量正文 + UI** | **M（1 人日）** | **已实施并 PASS** |

## 5. 实施要点（R5）

只替换 payload 的 `data.xp3` / `scenario.xp3` / `image00.xp3`；引擎（ELF/NRO）与日文版逐字节相同，不引入任何引擎侧汉化补丁（原计划的 patch G 取消）。

四个必踩的坑（详见 `docs/builds/012` §5）：

1. `startup.soc` 必须是 UTF-8（首次打包误用日文原包的 Shift-JIS 版 → 未捕获的 `eTJSScriptError`）。
2. CN 版 `Init.tjs` 删除了 scenario/image00/movie 的 xp3 注册（假定已解包成文件夹）→ 需在 `startup.tjs` 里补 archive 子目录 autopath。
3. **TJS 词法不支持 `\uXXXX` 转义**（只有 \x / \0），写成转义的中文目录名会静默失效 → 必须用真实 UTF-8 字符。
4. `System.setArgument("TextEncoding", "utf8")` 在 K2NX 是空操作 → 用 `Scripts.textEncoding = "utf8"`，并给脚本加 UTF-8 BOM 双保险。

## 6. 引擎侧落点预研（历史结论，已被 R5 取代）

- v0.1 设想的 patch G（渲染前字符串替换 + `romfs:/i18n/zh.json` 译表）**未实施，也不需要**。R5 是数据层替换，零引擎改动。
- 引擎能力上真正被用到的只有两处：`Scripts.textEncoding` 静态属性（`ScriptMgnIntf.cpp`）与脚本 BOM 分支（`TextStream.cpp`）；归档 autopath 走 `Storages.addAutoPath`。
- 若将来对无源码的游戏做汉化，patch G 仍是候选（技术可行性未验证）。

## 7. 字体

- K2NX 的 Switch 字体顺序（`core/visual/FontImpl.cpp`）：`sdmc:/switch/kirikiroid2/default.ttf` → romfs 内置 `DroidSansFallback.ttf`（7,287,728 B）→ 默认字体。
- CN7 实测：DroidSansFallback 覆盖全部简体用字，无豆腐块；**未内嵌任何商业字体**（simhei/simsun 有许可风险，避免）。
- 如需更佳字形：放 `default.ttf`（Noto Sans CJK / Source Han，OFL）即可运行时覆盖。

## 8. 风险与未验证项（更新）

- **R8-x1**：真机未验证（A7 NSP 已通过结构校验与 Citron NSP 冒烟，经 DBI 上传后由用户试玩复验）。
- **R8-x2**：长流程/分支遍历未做（当前验证到序章正文前几句 + 存档/读档/退出链路在日文版已 PASS）。
- **R8-x3**：已解决——A7 把 `movie_chs.xp3` 的 `opening.mpg`（134,811,648 B，画面自带中文硬字幕）替换进 `movie.xp3`，Citron 端到端验证播放正常（§10 / 012 §8）；`OP.MPg`（另一段 PV）仍未使用。
- **R8-x4**：汉化文本著作权归 X'moe 汉化组；对外分发只提供补丁/构建脚本，不附带游戏数据。
- **R8-x5**：`haruno.xmoe` 容器仍未破解（对本作无影响，其它游戏需另立项）。

## 9. 结论与剩余工作

- 结论：**汉化可行且已在本作实现**（R5 路线，模拟器级 PASS）。不需要逆向、不需要运行时 hook、不需要引擎改造。
- 已完成（模拟器侧全链路）：CN 三包构建 → NRO 形态 CN7 PASS → CN romfs → A6 NSP 构建 → `galnx package nsp verify`（19 checks / 18 ok / 1 warn 未签名）→ A6 NSP 首启冒烟 PASS → 中文 OP 替换（op1 PASS）→ A7 NSP 构建 + verify 19 checks + 首启冒烟 PASS。
- **推荐产物：A7**（`Kirikiroid2-NX-A7-CN-010047410000A000.nsp`，2,870,879,960 B，sha256 `c23a519a…`）；A6 已被 A7 取代。
- 剩余：
  1. DBI FTP 上传真机复验（中文标题/正文/存档/退出）；
  2. 可选：加 `default.ttf`（Noto Sans CJK / Source Han）改善字形；
  3. 可选：长流程/分支遍历（当前验证到序章正文前几句）。

## 10. 证据与复现

- 汉化源码仓库：`https://github.com/t-satoru-Studio/haruno_script`（main），zip sha256 `582f73ecd0591f99fc7f64ccd38a0f5f841b9d75cac5323d2ef75602796d2d69`。
- 三包哈希、CN7 截图与 k2s、复现命令：见 `docs/builds/012-k2nx-cn-content.md` §3/§6/§8。
- 证据入仓：`docs/milestones/evidence/P5a-cn7-*`（CN7）、`P5b-a6-*`（A6 NSP 冒烟，清单 `P5b-a6.sha256`）、`P5c-op-*`（中文 OP op1，清单 `P5c-op.sha256`）、`P5d-a7-*`（A7 首启冒烟，清单 `P5d-a7.sha256`）。
- A7 产物（推荐）：2,870,879,960 B，sha256 `c23a519aeb602104aa7bd6f63d8f33c2d79de93af7d3d292e1811a0e4a37a5e6`；PROVENANCE sha256 `8dbcc568…`；`galnx package nsp verify` ok=true（19 checks）。
- A6 产物（已被 A7 取代）：2,906,318,552 B，sha256 `1941a317baea186bb6f8ac9cdd8e9d11d2125a25abfcc32f83a14339a70a49d7`；PROVENANCE sha256 `82ed427d…`。

## 11. 变更记录

| 日期 | 版本 | 内容 |
| --- | --- | --- |
| 2026-10-30 | v0.1 | 初版：资产盘点、xmoe 格式初探、DLL 机制、四条路线对比、引擎落点预研 |
| 2026-10-30 | v0.2 | 重大更正：CN 文本来自公开源码仓库（R5 已实施 PASS）、PC 中文版可运行；xmoe 调查降级为备查；取消 patch G；补字体/风险/证据 |
| 2026-10-30 | v0.3 | A6 CN NSP 构建 + verify 19 checks + 首启冒烟 PASS（中文标题/正文、0 异常）；剩余项收敛为真机复验与可选增强 |
| 2026-10-30 | v0.4 | 中文 OP 纳入（op1 端到端 PASS）+ A7 NSP 构建/verify/首启冒烟 PASS（1.0.6）；A7 取代 A6 为推荐产物；R8-x3 关闭 |
