# 012 · K2NX 中文内容包（X'moe 汉化移植）

- 日期：2026-10-30
- 引擎：K2NX（`Erige005/Kirikiroid2-NX` @ `e96b6034c292c6ccdb099823ab6a0a6b505f77f3`，tag v1.0.1）+ 补丁 A–F（`docs/builds/patches/k2nx-switch/`）
- 中文内容来源：`t-satoru-Studio/haruno_script`（main 分支，X'moe 汉化组公开的汉化源码）
- 状态：**模拟器级 PASS（Citron nightly 0237a9b88；run CN7 = NRO 形态，A6/A7 首启冒烟 = NSP 形态）**；A6 自包含 NSP 已构建（2,906,318,552 B，sha256 `1941a317…`）并通过 `galnx package nsp verify` 与 A6 形态 Citron 冒烟；A7 在 A6 基础上把 `movie.xp3` 换成中文 OP 版（2,870,879,960 B，sha256 `c23a519a…`，verify 19 checks + 首启冒烟 PASS），manifest 分别为 `examples/pilot01-haruno-cn.yaml`（A6）与 `examples/pilot01-haruno-cn2.yaml`（A7，推荐）

## 1. 结论先行

汉化**不需要**逆向 `xmoeParser.dll` / 解密 `haruno.xmoe`，也**不需要**引擎侧文本替换补丁（原计划中的 patch G 未实施）。做法是：

1. 用汉化组公开仓库里的 UTF-8 中文脚本 / TJS / 图片，按日文原版的条目名**重新打包成 XP3**；
2. 在 `data.xp3>startup.tjs` 里设 `Scripts.textEncoding = "utf8"`，并在执行 `sys_source/Init.tjs` 之前补注册 scenario/image00/movie 三个归档的子目录 autopath；
3. 只替换 payload 里的 `data.xp3`/`scenario.xp3`/`image00.xp3` 三个文件，引擎（ELF/NRO）与日文版逐字节相同（A5 产物哈希不变），字体沿用 romfs 内置 `DroidSansFallback.ttf`。

## 2. 来源与许可

| 项 | 值 |
| --- | --- |
| 仓库 | https://github.com/t-satoru-Studio/haruno_script |
| 下载 | `https://codeload.github.com/t-satoru-Studio/haruno_script/zip/refs/heads/main` |
| 归档 | `E:/galnx-build/pilot-01/p3/xmoe-script.zip`，26,451,029 B，sha256 `582f73ecd0591f99fc7f64ccd38a0f5f841b9d75cac5323d2ef75602796d2d69` |
| 解压 | `E:/galnx-build/pilot-01/p3/xmoe-script/haruno_script-main/` |
| 许可声明 | 仓库 readme：X'moe 汉化组逆向工程；PC 资源无加密；**汉化补丁著作权归 X'moe 汉化组** |

仓库结构：`KR/` = 面向 krkr2 引擎（与 K2NX 同引擎代）的汉化源码，含 `scenario/`（234 个 .ks + `startup.soc`）、`image00/`（142 个 png）、`macro/`（6 ks）、`sys_source/`（30 个 tjs，含 `Init_fix.tjs`）、`startup.tjs`；`PC/` = 面向 krkrz + k2compat 的改动版（本方案未采用）。

注意：K2NX 打包的 A6 NSP 内含游戏本体数据（romfs 2.87 GB），**仅用于本机试点**，不得公开分发；对外分享只应分发补丁/脚本与说明。

## 3. 内容映射（三包）

日文原包备份：`E:/galnx-build/pilot-01/p4/backup-jp/`（data.xp3 198,550 B sha `15707da9…`、scenario.xp3 1,551,254 B sha `b07ed66c…`、image00.xp3 22,230,877 B sha `9b4117f6…`）。

| 包 | 项数 | 内容 | 产物 | 大小 / sha256 |
| --- | --- | --- | --- | --- |
| `data.xp3` | 37 | macro 6 ks（KR）+ sys_source 30 tjs（KR）+ **自定义 startup.tjs** + 警告 txt | `E:/galnx-build/pilot-01/p3/cn-pack/data.xp3` | 207,728 B / `e30251c772dceafdea440d8f49f79c6c0bc7237c2aa69c953ec94455ec9b5867` |
| `scenario.xp3` | 237 | 235 ks（KR 234 + JP 回退 1：`D_雨音/D0901A_G04.ks`）+ startup.soc（KR，UTF-8）+ 警告 txt | `.../cn-pack/scenario.xp3` | 1,719,460 B / `4da3742e0456b162fbde21061948f910da6d136fed416657eca77fa2b570c184` |
| `image00.xp3` | 141 | 140 png（KR）+ 1 png（JP 回退） | `.../cn-pack/image00.xp3` | 22,248,684 B / `5baf63a6cdc756ada63693fce76bc48ba09ebff240efdb3f9e63a7897d053071` |

- 所有文本条目统一 **UTF-8 BOM + CRLF**；打包后逐项反解校验 `invalid_utf8 = 0`。
- 其余 11 个 xp3（image01/02/02_2/03/04/06/media/voice*/movie）不含台词，直接沿用日文原包。

## 4. XP3 格式与 writer（`E:/galnx-build/pilot-01/p3/xp3pack.py`）

格式由 K2NX 自身解析器实证（`src/core/base/XP3Archive.cpp tTVPXP3Archive::Init`），并用自建 `E:/galnx-build/m1-content/data-withfont.xp3` 做 oracle：

```
header  = b'XP3\r\n \n\x1a\x8b\x67\x01' (11 B) + u64le(index_offset=23) + b'\x01\x00\x00\x00'
@23     = 0x80 + u64le(0) + u64le(real_index_offset)      # CONTINUE 空块
data    = 按 segm 顺序排列的文件数据（zlib 或 raw）
index   = 0x01 + u64le(comp) + u64le(raw) + zlib(index_body)
body    = 每个文件 chunk('File', chunk('info')+chunk('segm')+chunk('adlr'))
info    = u32le(flags) u64le(orgsize) u64le(arcsize) i16le(namelen) + name.encode('utf-16le')
segm    = 每段 28 B: u32le(method) u64le(start) u64le(orgsize) u64le(arcsize)   # method 0=raw 1=zlib
adlr    = adler32 的 4 B **大端**
chunk   = tag(4 B) + u64le(size) + body
```

`write_xp3(path, [(name, bytes), ...])` 自动选 zlib/raw、算 start/arcsize/adler；roundtrip 读回逐字节一致。读取侧用 `E:/galnx-build/pilot-01/p3/xp3tool.py`（`read_all_items` / `extract_item`）。

## 5. 四个必踩的坑（修复链）

### 5.1 startup.soc 编码（第一次跑崩的直接原因）

首次打包时 scenario.xp3 的 `startup.soc` 直接抄了日文原包（Shift-JIS，527 B）。而 `Scripts.textEncoding = "utf8"` 要求所有脚本是 UTF-8，于是 `parser.tjs(270) loadScenario("startup.soc")` 抛 `eTJSScriptError`（**TJS 层 try/catch 捕不到**，只在 k2s 日志留下未捕获异常 dump）。

修复：改用仓库自带的 `KR/scenario/startup.soc`（823 B，UTF-8）→ 统一转 UTF-8 BOM + CRLF（826 B）。

### 5.2 归档子目录 autopath（CN 译制包假定「已解包成文件夹」）

CN 版 `sys_source/Init.tjs` 被汉化组改过：**删除了 scenario/image00/movie 三个 xp3 的注册**，改用 `scenario/`、`scenario/@_共通/`、`image00/` 之类的文件夹 autopath（他们是按解包目录发布的）。我们保持 XP3 布局，于是 `@0000A_Z01.ks` 之类的根目录外文件找不到（表现为「が見つかりません。」）。

修复：自定义 `startup.tjs` 在 `execStorage("sys_source/Init.tjs")` 之前按日文版 `Init.tjs` 的等价布局补注册：

```tjs
Scripts.textEncoding = "utf8";
function GalNXRegArchive(name) {
    if (Storages.isExistentStorage(System.exePath + name)) {
        Storages.addAutoPath(System.exePath + name + ">");
        return System.exePath + name + ">";
    }
    return "";
}
var galnxScn = GalNXRegArchive("scenario.xp3");
// + @_共通/ A_菜乃花/ B_このみ/ C_花梨/ D_雨音/ E_彩菜/ Replay/ エクストラ/ 体験版/
var galnxImg00 = GalNXRegArchive("image00.xp3");   // + map/ csv/
var galnxMovie = GalNXRegArchive("movie.xp3");
Scripts.execStorage("sys_source/Init.tjs");
```

### 5.3 TJS 不支持 \uXXXX 转义（最隐蔽的一个）

构造 startup 时曾把中文目录名写成 TJS 字符串里的 `"@_\\u5171\\u901a/"`。**TJS 词法只支持 \x / \0 / 单字符转义，没有 \uXXXX**（`src/core/tjs2/tjsLex.cpp TJSInternalParseString`），于是这些字符串被解析成 `@_u5171u901au901a/` 之类，所有中文子目录 autopath 静默失效。

修复：startup 里改用**真实 UTF-8 字符**（「@_共通/」等字面量），不再做 \u 替换。

### 5.4 让 UTF-8 真正生效

- 汉化组 `startup.tjs` 首行是 `System.setArgument("TextEncoding", "utf8")`——在 K2NX 里这是**空操作**（`System.setArgument` → `TVPSetCommandLine`，而读 encoding 的 `-readencoding` 参数处理被 `#if 0` 掉了）。
- 可用入口是 TJS 静态属性：`Scripts.textEncoding = "utf8"`（`ScriptMgnIntf.cpp` 的 `textEncoding` 属性 → `TVPSetDefaultReadEncoding`，接受 `utf8`/`gbk`/`sjis` 等）。
- 双保险：脚本文件本身带 UTF-8 BOM，引擎 BOM 分支会剥离并强制按 UTF-8 解码。

## 6. 验证（CN7，模拟器级）

- 部署：三包覆盖到 `C:/Users/ACETaffy/AppData/Roaming/citron/sdmc/kirikiri/haruno/`（marker `.galnx_extracted` 已存在 → 跳过解包），跑 K2NX NRO（干净构建）。
- run dir：`E:/Othergames/Nintendo Switch/Workspace/GalNX/workspaces/citron-harness/runs/20261030-153915-kirikiroid2`
- k2s：`E:/galnx-build/pilot-01/p4/cn7/k2s_cn7.txt`（2,142 行，sha `c7fa504d8c16f828f779130a6c6d737c4cc199f8d71d780d80448f98d8a7e282`）
  - autopath 计数：scenario.xp3 根 2、`@_共通/` 44、`a_菜乃花/` 43、`b_このみ/` 32、`c_花梨/` 39、`d_雨音/` 46、`e_彩菜/` 18、`Replay/` 13、`エクストラ/` 0、`体験版/` 0
  - 时间线：`Scenario loaded : title.ks` 15:40:12 → `start.ks` 15:40:30 → **`Scenario loaded : @0000A_Z01.ks` 15:40:34**
  - `script-exception` / `script-error` 计数 = **0**
- 截图（1728x1016，`E:/galnx-build/pilot-01/p4/cn7/`）：

| 文件 | 大小 | sha256 | 内容 |
| --- | --- | --- | --- |
| cn7-00-titlemenu.png | 2,378,891 B | `a3e62e9c2dc0531ff8c0a63b624c13bb65a8c8ced7749f4744b58f24a88d7e65` | 中文标题菜单：开始游戏/读档/快速读档/继续游戏/游戏设置/鉴赏模式/结束游戏 |
| cn7-02-start.png | 880,756 B | `507879521d0cf35b168b9da516890a21fa5b524560bee07906226ec8efd91b12` | 正文：「我拼命地伸出了手。」 |
| cn7-04-story1.png | 902,888 B | `aea099bb1706e4eda58fca33c53e60c5346391e18e8b860a1170fbe14b514880` | 「向着眼前不知何处、不知是谁的逆光中的……向着“她”…」 |
| cn7-06-story3.png | 904,091 B | `2a962a68a2c0253901ed61344617f8a69e937d85758a7c3d9755e3e914b310e4` | 「但是，无论多少次地伸出手，我都……无法触碰到“她”。」 |

- 字形：romfs 内置 `DroidSansFallback.ttf`（7,287,728 B）覆盖全部简体用字，无豆腐块、无乱码；**未内嵌任何商业字体**。
- 对照：CN 包内 `@_共通/@0000A_Z01.ks`（5,439 B，UTF-8 BOM）文本与截图一致。

诊断期临时加过两处 `#ifdef __SWITCH__` 日志（`tjs2/tjsInterCodeExec.cpp` 未捕获异常打印、`base/StorageIntf.cpp` autopath / storage-not-found 打印），验证后已用 `E:/galnx-build/pilot-01/p4/revert_dbg.py` **完全回退**；重建出的 ELF 113,892,064 B sha `02b70f18…` / NRO 42,363,510 B sha `41b7a745…` 与 A5 产物逐字节相同，证明引擎源码回到发布状态。

## 7. CN romfs 与 A6 NSP

- CN romfs：`E:/galnx-build/pilot-01/p5/romfs-cn`（由 `E:/galnx-build/pilot-01/p3/romfs` 复制，替换上述三包；`game_files.txt` 改 `version=pilot01-cn1`、`bytes=2870830500`）。生成脚本 `E:/galnx-build/pilot-01/p4/make_cn_romfs.py`。
- manifest：`examples/pilot01-haruno-cn.yaml`（game.version 1.0.5，switch.title "Haruno CN"，title_id `010047410000A000`，payload.version pilot01-cn1）。
- 构建：`E:/galnx-build/pilot-01/p5/a6-build.sh`，产物 `E:/galnx-build/pilot-01/p5/out/Kirikiroid2-NX-A6-CN-010047410000A000.nsp`。
- A6 产物：**2,906,318,552 B，sha256 `1941a317baea186bb6f8ac9cdd8e9d11d2125a25abfcc32f83a14339a70a49d7`**；PROVENANCE 14,047 B sha256 `82ed427de9c0f891a5379d22f88d9471f7572b909c4f4e141ef7f122cb209ac8`（version 1.0.5 / version_code 65541 / romfs 109 文件 2,878,382,114 B / keyset 12,007 B sha `7bb3b6d2…` / no_secret）。
- 结构校验：`galnx package nsp verify --manifest examples/pilot01-haruno-cn.yaml --nstool … --keyset … --provenance …` → `ok=true`，19 checks = 18 ok + 1 warn（唯一 warn = `verify.signature`，未签名 homebrew 预期）；3 个 NCA 的 ProgID 全为 `010047410000a000`。
- A6 冒烟（`E:/galnx-build/pilot-01/p5/run-a6smoke.sh`，2026-10-30 15:49 起）：先 `rm -rf` 虚拟 SD 游戏区与 marker 强制首启解包 → `free space check ok: 17069 MiB free for a 2737 MiB payload` / `first boot: copying 23 payload file(s)` / `payload copy finished: 23 copied, 0 kept, 0 failed` → `[GALNX] autostarting game from /kirikiri/haruno/data.xp3` → 5 个 `.tpm → .dll` 内置插件别名命中 → `Scenario loaded : startup.soc`（15:49:43）→ `title.ks`（15:50:24）→ `start.ks`（15:50:44）→ **`@0000A_Z01.ks`（15:50:48）**；`exception|error` 计数 **0**；窗口标题 `Haruno CN (64-bit) | 1.0.5`。
- A6 证据（`docs/milestones/evidence/`，清单 `P5b-a6.sha256`）：

| 文件 | 大小 | sha256（前 16） | 内容 |
| --- | --- | --- | --- |
| `P5b-a6-00-titlemenu.png` | 2,376,225 B | `508304b988d98442` | 中文标题菜单：开始游戏/读档/快速读档/继续游戏/游戏设置/鉴赏模式/结束游戏 |
| `P5b-a6-02-start.png` | 880,993 B | `19cd976c01940f04` | 正文：「拼命地伸出了手。」 |
| `P5b-a6-04-story1.png` | 903,438 B | `56d9ac468d31b51b` | 「向着眼前不知何处、不知是谁的逆光中的……向着“她”…」 |
| `P5b-a6-05-story2.png` | 928,374 B | `2434bfba0113a5e5` | 「但是，无论多少次地伸出手，我都……无法触碰到“她”。」 |
| `P5b-a6-k2s.txt` | 8,256 B | `e2acb32840c72801` | 首启解包 + 场景加载 + 0 异常 |
| `P5b-a6-glog.txt` | 335 B | `83f41ff2acea9407` | 按键日志 |

## 8. 中文 OP（A7）

- 来源：PC 中文版 `E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气/movie_chs.xp3`（197,246,119 B），items = `logo.mpg` 1,769,476 B（sha `bc2b29ef17bb0a19`，与日文版相同）+ `OP.MPg` 60,664,813 B + `opening.mpg` **134,811,648 B sha `276f671cbdc77a34`**（画面自带中文硬字幕）。
- 对照 JP `movie.xp3`（164,394,346 B）：警告 txt 157 B + `logo.mpg` 同一 sha + `opening.mpg` 162,623,492 B sha `e88625704277d139`；ffprobe 两者均 mpeg1video 1280x720 60 fps + mp2 44.1 kHz，JP 111.99 s / CN 114.48 s。
- 判定依据：CN 版 OP 帧 `E:/galnx-build/pilot-01/p4/moviecheck/cn_30|60|90.png` 带中文字幕（cn_60「如果 用心聆听 总会听到 令人怀念的旋律」、cn_30「犹豫不决的回忆 和昏昏欲睡的每一天」），JP 帧 `jp_30|60|90.png` 同位置无字幕 → 只替换 `opening.mpg`。
- 新 `movie.xp3` = [JP 警告 txt + JP `logo.mpg` + CN `opening.mpg`] **129,030,977 B sha256 `483bc72d9be9cc74a9c86baf55c0589228d3104446391f475a4a8f59105ec665`**，由 `xp3pack.write_xp3` 重打包、roundtrip bad 0；脚本 `E:/galnx-build/pilot-01/p4/build_cn_movie.py`。
- 引擎侧依据：OP 触发点 `cn-scn/@_共通/@0000A_Z02.ks:2024` 的 `[macPlayMovie file=opening mode=1 cursor=0]`；类 `_MOVIEOBJECT extends VideoOverlay`（`KR/sys_source/MovieObject.tjs:18`），实例 `MainWnd.MovieObj`（`KR/sys_source/MainWindow.tjs:280`），`PlayFile()`（MovieObject.tjs:179）先 ResourceCheck 再 LoadFile → 替换归档内同名文件即可生效，无需改脚本。
- Citron 端到端验证（脚本 `E:/galnx-build/pilot-01/p4/run-op1.sh`，job bash-8d322af39aa14b7d，run `20261030-160539-kirikiroid2`）：测试 scenario `scenario-op-test.xp3`（1,719,490 B sha `07cde2af393c7ae63b2388795fd0ee6ae9ac3f2828791f45c2bc2ae3e64d0871`，在 `@0000A_Z01.ks` 的 BOM 后插入一行 `[macPlayMovie file=opening mode=1 cursor=0]`）→ k2s 记 `Input #0, mpeg, from 'opening.mpg': Duration: 00:01:54.50 … 1280x720 … mpeg1video`（= CN 114.5 s 版）→ 截图 `op-05` 日文卡拉OK行、`op-08` 标题 logo + 中文硬字幕「啊 透明的一秒 流逝而去」。
- 证据（`docs/milestones/evidence/`，清单 `P5c-op.sha256`）：`P5c-op1-08-title-cnsub.png`（2,224,638 B `2e34dc6d…`）、`P5c-op1-05-lyric.png`（181,559 B `265668e9…`）、`P5c-movie-cn_60.png`（306,349 B `176482e1…`）、`P5c-op-k2s.txt`（8,168 B `0b6f38b9…`）、`P5c-op-glog.txt`（471 B `03179fe8…`）。
- A7 打包：`E:/galnx-build/pilot-01/p5/romfs-cn2`（romfs-cn 的硬链接副本，仅替换 `game/movie.xp3`；`game_files.txt` 改 `version=pilot01-cn2` / `bytes=2835467131`，601 B sha `effc2c87…`），manifest `examples/pilot01-haruno-cn2.yaml`（game.version 1.0.6，romfs-cn2，payload pilot01-cn2），构建脚本 `E:/galnx-build/pilot-01/p5/a7-build.sh`。
- A7 产物：`E:/galnx-build/pilot-01/p5/out/Kirikiroid2-NX-A7-CN-010047410000A000.nsp` **2,870,879,960 B sha256 `c23a519aeb602104aa7bd6f63d8f33c2d79de93af7d3d292e1811a0e4a37a5e6`**（version 1.0.6 / version_code 65542；romfs 109 文件 2,843,018,745 B，payload 23 文件 2,835,467,131 B）；PROVENANCE 14,046 B sha `8dbcc568…`。
- A7 校验：`galnx package nsp verify --manifest examples/pilot01-haruno-cn2.yaml` → **ok=true，19 checks = 18 ok + 1 warn**（唯一 warn 为未签名 NCA signature，homebrew 预期）；3 个 NCA（Meta 0x1000 / Program 0xab1c4a00 / Control 0x1cc00）ProgID 均为 `0x010047410000a000`，provenance 交叉核对通过。
- A7 首启冒烟（NSP 形态，脚本 `E:/galnx-build/pilot-01/p5/run-a7smoke.sh`，run `20261030-161305-Kirikiroid2-NX-A7-CN-010047410000A000`）：删 payload + marker 强制首启解包 → `first boot: copying 23 payload file(s)` → `payload copy finished: 23 copied, 0 kept, 0 failed, 2704 MiB total` → 打开 `movie.xp3` → `Scenario loaded : title.ks`（16:14:23）→ `start.ks`（16:14:42）→ `@0000A_Z01.ks`（16:14:45）；exception 计数 0；窗口标题 `Haruno CN (64-bit) | 1.0.6`。
- A7 证据（`docs/milestones/evidence/`，清单 `P5d-a7.sha256`）：`P5d-a7-00-titlemenu.png`（2,376,237 B `c4cb234a…`，中文标题菜单）、`P5d-a7-04-story1.png`（903,075 B `8974e447…`，中文正文）、`P5d-a7-k2s.txt`（7,980 B `c0cbd5c5…`）、`P5d-a7-glog.txt`（268 B `a916ea03…`）。

## 9. 复现命令

```bash
# 1) 取汉化源码
curl -L -o xmoe-script.zip https://codeload.github.com/t-satoru-Studio/haruno_script/zip/refs/heads/main
# 2) 生成 CN 三包（需要 p3/xp3tool.py、p3/xp3pack.py、jp 提取结果 jp-data/ 与 JP 原包备份）
python E:/galnx-build/pilot-01/p3/cn_pack3.py      # data.xp3
python E:/galnx-build/pilot-01/p4/cn_fix5.py        # scenario.xp3 的 startup.soc 编码修复
python E:/galnx-build/pilot-01/p4/cn_fix6.py        # startup.tjs 真实 UTF-8 重写
python E:/galnx-build/pilot-01/p4/build_cn_movie.py # 中文 OP 版 movie.xp3
# 3) 模拟器验证（NRO 形态，不需要重打 NSP）
bash E:/galnx-build/pilot-01/p4/run-cn7.sh          # cleanup -> 部署三包 -> detach 运行 -> 截图 -> 归档
# 4) 组装 CN romfs + A6 NSP（日文 OP）
python E:/galnx-build/pilot-01/p4/make_cn_romfs.py
bash E:/galnx-build/pilot-01/p5/a6-build.sh
# 5) 组装 CN romfs（含中文 OP）+ A7 NSP
python E:/galnx-build/pilot-01/p5/make_romfs_cn2.py
bash E:/galnx-build/pilot-01/p5/a7-build.sh
```

## 10. 限制与后续

- **L1**：仅替换文本/图片（data/scenario/image00）；image01–04 等大图未本地化（原文本身不含台词，UI 之外的图片文字为 0）。
- **L2**：CN 译制包自带 `movie_chs.xp3`（197 MB）中的 `opening.mpg` 已纳入 A7（见 §8），因此 A7 起 OP 为中文硬字幕版；`OP.MPg`（60 MB，另一段 PV）未使用。A6 仍为日文 OP。
- **L3**：字体未内嵌，依赖 romfs 的 DroidSansFallback；如需更佳字形可加 `sdmc:/switch/kirikiroid2/default.ttf`（运行时优先）。
- **L4**：CN 版基于 krkr2 的 `KR/` 源码，与日文原版存在个别脚本差异（如 `MainWindow.tjs` 的 `extends global.Window`），当前测试未出现行为差异；长流程遍历未做。
- **L5**：真机未验证（A6 经 DBI 上传后由用户装机复验）；模拟器上 60 FPS、0 异常。真机与模拟器的差异点：真机无 Citron 的虚拟光标，需确认触摸/物理按键路径（K2NX 的虚拟鼠标模式在真机同样可用：PLUS 开光标、DPAD 移动、A/B 左右键）。
- **L6**：汉化文本著作权归 X'moe 汉化组；对外分发时只提供补丁与构建脚本，不附带游戏数据。

## 11. 变更记录

| 日期 | 版本 | 内容 |
| --- | --- | --- |
| 2026-10-30 | v1.0 | 初版：来源、三包映射、XP3 writer、四坑修复链、CN7 验证、A6 构建 |
| 2026-10-30 | v1.1 | A6 产物哈希 + verify 19 checks + A6 首启冒烟 PASS（中文标题/正文、0 异常、窗口标题 Haruno CN 1.0.5）；证据 P5b-a6-* |
| 2026-10-30 | v1.2 | 新增 §8 中文 OP（A7）：movie_chs 结构对比、op1 端到端 PASS、romfs-cn2 + A7 NSP（2,870,879,960 B sha `c23a519a…`）verify 19 checks + 首启冒烟 PASS（1.0.6）；证据 P5c-op-* / P5d-a7-* |
