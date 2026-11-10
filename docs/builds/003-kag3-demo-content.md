# 003 · KAG3 demo 合法测试内容包（data.xp3 自建）

- 日期：2026-10-30
- 负责人：Lead
- 关联：M1-d（KiriKiri 内容跑通）、计划 v0.4 §7.2、审计 v1.3 §4.B.8 / §4.B.7、任务 task-13（krkrsdl2 构建）
- 目标：为 krkrsdl2 的 Switch 构建提供**可合法再分发**的测试游戏数据 `data.xp3`，用于在 Citron / 真机上验证「KiriKiri 引擎 + KAG3 脚本 + 文字/图片/音频 + 字体」完整链路。

## 1. 结论速览

| 项 | 结果 |
| --- | --- |
| 上游现成资产可用性 | ❌ `krkrsdl2/krkrsdl2-kag3-demo` release `latest` 的 `data.xp3` 只有 **65 B**（空 XP3 存根），不可用 |
| 自建数据包 | ✅ 成功：`data.xp3` **4,764,317 B**（无字体）、`data-withfont.xp3` **6,628,897 B**（内嵌 IPAexGothic） |
| 打包工具 | ✅ `krkrrel.exe`（krkrrel-ng release `latest`，win32 版 1,396,346 B zip） |
| 字体 | ✅ IPAexGothic 004.01（IPA Font License 1.0，可再分发） |
| Citron 运行验证 | ⏳ 待 krkrsdl2 NRO 构建完成后进行（见 task-13 / 构建记录 001） |

## 2. 为什么上游资产不能用（根因）

- 实测下载 `https://github.com/krkrsdl2/krkrsdl2-kag3-demo/releases/download/latest/data.xp3` → **65 B**，hex 开头 `5850 330d 0a20 0a1a`（XP3 magic）+ 空索引。
- 该仓库 CI（`.github/workflows/ci.yml`）用 `actions/checkout@v4 with submodules: recursive` + `bash build.sh` 出包；`build.sh` 内容：
  `rsync -a external/kag3/data/ data-tmp; rsync -a data-demo/ data-tmp; krkrrel data-tmp -out data.xp3`。
- 推断：出包时 `external/kag3` 子模块未正确展开，导致 `data-tmp` 只有 demo 增量、甚至为空 → 得到 65 B 空包。**资产只有 65 B 且 `digest=None`**，与推断吻合。
- 处置：不依赖该资产，按同一 `build.sh` 流程本地重建。

## 3. 重建步骤（实测）

```bash
# 1. 取源码（含 kag3 子模块）
cd /e/galnx-build/m1-content
git clone --depth 1 --recursive https://github.com/krkrsdl2/krkrsdl2-kag3-demo.git demo
# 子模块 external/kag3 检出 commit b21b16ea684a3274488282687ca4184df49bec9f（branch krkrsdl2）

# 2. 取打包工具 krkrrel-ng（GitHub release latest 的 win32 资产）
#    https://github.com/krkrsdl2/krkrrel-ng/releases/download/latest/krkrrel-win32.zip
#    zip 1,396,346 B；解压得 krkrrel.exe

# 3. 等价 build.sh 的打包
cp -a demo/external/kag3/data/. data-tmp/
cp -a demo/data-demo/. data-tmp/
tools/krkrrel/krkrrel-win32/krkrrel.exe data-tmp -out data.xp3

# 4. 嵌入字体（关键，见 §5）
cp -a data-tmp data-tmp-font
cp ipaexg.ttf data-tmp-font/system_polyfill/font.ttf
cp IPA_Font_License_Agreement_v1.0.txt data-tmp-font/system_polyfill/FONT_LICENSE.txt
tools/krkrrel/krkrrel-win32/krkrrel.exe data-tmp-font -out data-withfont.xp3
```

## 4. 产物与哈希

| 文件 | 大小（B） | SHA-256 | 说明 |
| --- | ---: | --- | --- |
| `data.xp3` | 4,764,317 | `c12ba272b7757aa08dffca11b58f4159d36434f635c5b04b23d3f6c284a08c55` | KAG3 + demo，无字体（对照用） |
| `data-withfont.xp3` | 6,628,897 | `56538c91a515c9c592300d2a44ae2e1fca0c33c874a64f9e8aff3544dcce09c6` | **推荐**，内嵌 IPAexGothic |
| `ipaexg.ttf` | 6,099,900 | `3b9955a5e437ffb24c41548e79296fa724822da21ee75dc1b94f6ccdb8f400dd` | IPAexGothic 004.01 |

- XP3 magic 校验通过：`58 50 33 0d 0a 20 0a 1a`。
- 内容（`data-tmp`）：60 个文件，含 kag3 引擎 `system/*.tjs`、demo `scenario/first.ks`（28,416 B）与 `snow.ks`（6,510 B）、背景/前景图与音频资源。
- 位置：`/e/galnx-build/m1-content/`（构建缓存，不入库）。

## 5. 字体为什么必须内嵌（源码实证）

- krkrsdl2 SDL2 平台层**没有系统字体**：`src/core/sdl2/SDLApplication.cpp:3164 TVPGetDefaultFontName()` 默认 `-deffont` = `"Noto Sans CJK JP"`；`TVPGetAllFontList` 是空实现（只有 Win32/Android 有系统字体枚举）。
- KAG3 的字体 polyfill（`system_polyfill/PolyfillInitialize.tjs:52-78`）：检测到 `global.Font.addFont` 后，依次检查 data 内 `system_polyfill/font.ttf`、`system_polyfill/font.otf`；命中则 `Font.addFont(font_to_add)` 并把返回的字体名 `setArgument("-deffont", ...)`。
- 因此：**字体文件必须放在 data.xp3 的 `system_polyfill/font.ttf|font.otf`**，否则 Switch 上无字可用（KAG3 demo 默认的 `ＭＳ Ｐ明朝` 是 Windows 字体）。krkr-ns 也是同一思路（其 RomFS 内置 `notosanssc.ttf` + compat-patches）。
- 选 IPAexGothic：体积 6.1 MB 适中、覆盖日文假名/常用汉字、IPA Font License 1.0 明确允许再分发与嵌入（须随附许可文本）。
- 未选 Noto Sans CJK JP（16.5 MB，OFL-1.1）与 Noto Sans JP 变量字体（9.6 MB，FreeType 兼容性未验证），详见 `docs/third_party/README.md`。

## 6. 许可与合规

| 组件 | 许可 | 依据 |
| --- | --- | --- |
| KAG3 引擎数据（`external/kag3/data`） | KAG3 许可（非 OSI/SPDX）：README 原文「Copyright (C)2001-2009, W.Dee and contributors 改変・配布は自由です」 | 仓库 README（06 审计 §6 T1 已记录） |
| kag3-demo 脚本/图片/音频（`data-demo`） | README 声明与 KAG3 相同 | 仓库 README |
| IPAexGothic 004.01 | IPA Font License 1.0 | `docs/third_party/fonts/IPA_Font_License_Agreement_v1.0.txt` |
| 打包工具 krkrrel-ng | 仓库 license=NOASSERTION（未声明） | GitHub API 实测 2026-10-30；仅本机构建使用，不再分发其二进制 |

- 仓库**只提交文档与许可原文**，不提交 `data.xp3`/字体二进制（见 §4 哈希 + §3 复现步骤）。
- 该内容包仅用于 GalNX 测试，不并入对外发布物。商业游戏数据（如 ONScripter-NX release 内的商业游戏 zip）一律不使用。

## 7. 未验证 / 后续

- ✅ 已用该数据包构建并运行 krkrsdl2 NRO：在 Citron 上渲染出 KAG3 demo 标题画面（见 `004-krkrsdl2-switch-fixes.md`、`docs/milestones/M1-kirikiri.md`）。
- ⚠ **romfs 内文件名必须是 `data.xp3`**：krkrsdl2 的项目目录探测只认 `data.xp3`/`content-data`/`data` 等固定名；直接把 `data-withfont.xp3` 当 romfs 文件名会导致 `Cannot find storage`（实测踩坑，已由 004 的重打包步骤修正）。
- 字体在 devkitPro FreeType 上的实际渲染（字形覆盖、中文缺字、粗体/斜体合成）未验证；`@font italic=true` 等 KAG 标签行为未验证。
- 音频输出（KAG3 demo 内含音频）、存档/系统变量文件路径（Switch SD 卡写入）未验证。
- 若后续改用 krkr-ns 启动器路线，其自带字体/兼容补丁与本内容包的组合方式待 M1/ M4 再定。

## 8. 关联文件

- 内容构建脚本：无（步骤见 §3；如需固化可加入 `scripts/`）。
- 第三方资源登记：[`docs/third_party/README.md`](../third_party/README.md)
- krkrsdl2 构建记录（task-13）：[`docs/builds/001-krkrsdl2-upstream.md`](001-krkrsdl2-upstream.md)（待交付）
- 构建索引：[`docs/builds/README.md`](README.md)