# Payload 生成器（P3-a）

| 项 | 值 |
| --- | --- |
| 文号 | docs/packaging/payload.md |
| 任务 | task-40（P3-a：payload 生成器） |
| 执行 | audit-switch |
| 日期 | 2026-10-30 |
| 状态 | 代码、schema、示例与 105 个测试完成；已与真实 A2 romfs 对齐验收；`cli.py` 已由 Lead 接入（cli.py:14 / cli.py:703），正式 CLI 实跑通过 |

## 1. 目的与范围

自包含 NSP 需要把游戏数据（KiriKiri 的 xp3/cf/插件等，试点约 2.87 GB）随包塞进 romfs，由引擎在**首次运行时**解压到 SD 卡。本模块把 P1-d 临时脚本（`E:/galnx-build/pilot-01/make_payload_a2.py`，仓库外）里手工完成的这件事固化成可测试的 Python 模块。

四段能力：

1. **选择**：按 include/exclude glob 从只读游戏目录挑出 payload 文件，按扩展名分类，生成 `game_files.txt` 解压清单。
2. **键位**：为 K2NX 生成 `Kirikiroid2Preference.xml`（手柄虚拟键 → Windows VK 码），默认绑定与 pilot-01 黄金样本逐字节一致。
3. **计划**：只读规划 romfs 树（引擎 UI 文件 + payload 目录 + 生成文件），输出 16 项检查与 JSON 计划。
4. **落盘**：`materialize()` 把计划写成一个 romfs 目录（copy / hardlink / symlink 三种模式）。

边界：

- **不写引擎代码**：读取 `game_files.txt`、拷贝到 `target`、写 `marker` 是 K2NX 侧已有能力（P1-d 已验证），本模块只生成它读取的输入。
- **不校验游戏数据内容**：xp3 是否加密/脚本是否可移植由 `docs/pilot/P1-game-audit.md` 负责；本模块只读文件路径与大小，不解析内容。
- **不打包 NSP**：`elf2nso`/`hacbrewpack` 等由 P3-b 的 `src/galnx/package/nsp.py` 负责，本模块只产出 `--romfs-dir` 指向的目录。
- **不修改游戏目录**：`source_dir` 全程只读（`os.walk` + `stat`）。
- **不处理 xmoe 汉化容器**：`data.xm3` 等私有容器不可移植（P1-c 结论），示例 manifest 用 `*_chs.xp3` 排除汉化档。

## 2. 形态与 romfs 布局

```text
romfs/                                  ← materialize 的输出目录，交给 hacBrewPack --romfsdir
  Default/ img/ locale/ ui/ ...         ← ui_dir 原样照搬（引擎自带 UI，85 文件 / 7.55 MB）
  DroidSansFallback.ttf default.cur     ← 同上（字体回退与默认光标）
  game_files.txt                        ← 生成的解压清单（romfs 根）
  game/                                 ← payload_dir（默认 game）
    data.xp3
    haruno.cf
    plugin/*.tpm
    Kirikiroid2Preference.xml           ← 生成的键位映射（payload 根）
```

运行时契约（引擎侧，P1-d 已验证）：

1. K2NX 启动读 `romfs:/game_files.txt`；头部 5 行给出 `version`/`bytes`/`target`/`startup`/`marker`。
2. 对每个 `file=<rel>`：从 `romfs:/<payload_dir>/<rel>` 拷到 `<target>/<rel>`，`file=` 不带 `game/` 前缀。
3. 全部拷完后写 `marker`；`version` 变化时重新解压（覆盖旧目录）。
4. 启动 `startup`（`/kirikiri/haruno/data.xp3`）。

**布局是 romfs 契约的一部分**：UI 文件必须在根（引擎按 `romfs:/ui/...`、`romfs:/Default/...` 找），payload 必须在 `payload_dir` 下，清单必须在根。三处都不能由用户随意改动；改动只允许改 `payload_dir` 与 `manifest_name` 两个名字（引擎侧需同步支持）。

## 3. 模块布局与公共 API

新增文件（均为纯标准库，无第三方依赖）：

| 文件 | 职责 |
| --- | --- |
| `src/galnx/payload/__init__.py` | 再导出全部公共 API（12.8 KB 源码，导出 60 个名字） |
| `src/galnx/payload/content.py` | 路径规范化、分类、include/exclude 匹配、扫描、`game_files.txt` 渲染与解析 |
| `src/galnx/payload/keymap.py` | K2NX 键位映射：VK 常量、绑定解析/校验、模板渲染、黄金样本校验、profile 覆盖检查 |
| `src/galnx/payload/plan.py` | `PayloadConfig` / `PayloadPlan` / `build_plan()` / `materialize()` / schema 校验 |
| `src/galnx/payload/cli.py` | `register(subparsers)` + `cmd_payload_plan/materialize/verify` |
| `src/galnx/payload/templates/k2nx/Kirikiroid2Preference.xml` | 黄金样本的逐字节副本（模板基线） |

### 3.1 公共 API 速查

| API | 说明 |
| --- | --- |
| `classify_path(rel)` | 按扩展名返回 `xp3` / `config` / `plugin` / `font` / `other`（`.xp3/.cf/.tpm/.ttf/.ttc/.otf`，其余 other） |
| `normalize_relpath(value)` | 去前导 `/`、折叠空段与 `.`；遇到 `..`、反斜杠、首段含 `:` 报错 |
| `match_pattern(rel, pattern)` / `match_any` | 无 shell 的 glob：`*``?` 不跨 `/`，`**` 匹配零或多段，锚定 payload 根；模式含 `..` 报错 |
| `scan_payload(source, include, exclude)` | 递归扫描只读目录，只收普通文件；返回按（分类, 相对路径）排序的 `PayloadFile` 列表 |
| `render_game_files(version, target, startup, marker, files)` | 生成 `game_files.txt`（UTF-8/LF/结尾换行）；内部再排序并做重复与路径校验 |
| `parse_game_files(text)` | 严格解析回 `{version, bytes:int, target, startup, marker, files[]}`（供黄金样本验证） |
| `PayloadFile(rel, size, category, source=None, symlink=False, sparse=False)` | 不可变数据类；`to_json()` 输出 `{path, bytes, category, symlink, sparse}` |
| `PayloadError` | 所有输入错误的统一异常（`ValueError` 子类） |
| `resolve_pad(value)` / `resolve_vk(value)` | 接受整数、数字字符串、`VK_PAD1`、按钮名（`A`/`B`/`X`/`Y`/`L`/`R`/`PLUS`/`MINUS`/`LEFT`…）；非法值报错 |
| `normalize_bindings(bindings)` / `validate_bindings(map)` | 规范化各种输入；校验重复 pad、VK 越界（0x08-0xFE）、同一 VK 绑两个 pad |
| `render_with_template(bindings, template=None)` | 读模板，只替换 `<KeyMap key="N" value="M"/>` 的 M；要求模板 pad 集合与绑定完全一致，其余字节原样保留 |
| `render(bindings)` | 不依赖模板、从零生成带注释的 XML（通用路径） |
| `load_template()` / `template_path()` | 读内置模板及其路径（`importlib.resources` 风格定位） |
| `parse_keymap(xml)` | 反解析 `<KeyMap>` 行为 `{pad: vk}` |
| `verify_golden()` | 3 项自检：模板 1293 B、模板 sha256、默认绑定渲染结果 sha256 |
| `profile_alignment(profile)` | 把 input profile 的语义动作与默认绑定交叉比对，返回 `(action, buttons, covered, detail)` |
| `PayloadConfig.from_mapping(data, base_dir)` | 解析 manifest 的 `payload` 段（未知字段/必填/路径/键位校验） |
| `validate_manifest_payload(payload, base_dir)` | 先 JSON Schema 再 from_mapping，返回 `"payload/field: msg"` 形式错误列表（空列表=通过） |
| `build_plan(config, source_dir=None, ui_dir=None, link_mode="copy")` | 只读规划；返回带 16 项检查的 `PayloadPlan` |
| `materialize(plan, out_dir, mode=None, force=False)` | 按计划写 romfs；返回统计字典 |
| `PayloadPlan.to_json(include_files=True)` / `plan_to_json` | 计划 JSON 视图 |
| `payload_validator()` / `load_payload_schema()` / `payload_schema_path()` | `schemas/payload.schema.json` 的 Draft 2020-12 校验器 |

常量：`CATEGORY_ORDER=("xp3","config","plugin","font","other")`、`DEFAULT_INCLUDE=("*.xp3","*.cf","plugin/*.tpm")`、`DEFAULT_EXCLUDE=("*.sig","**/*.sig")`、`DEFAULT_PAYLOAD_DIR="game"`、`DEFAULT_MANIFEST_NAME="game_files.txt"`、`DEFAULT_KEYMAP_FILE="Kirikiroid2Preference.xml"`、`FAT32_MAX_FILE=2**32-1`、`WINDOWS_PATH_MAX=259`、`WINDOWS_PATH_WARN=200`、`LINK_MODES=("copy","hardlink","symlink")`。

## 4. manifest 的 payload 段

### 4.1 完整示例（`examples/payload/manifest.pilot01.yaml` 节选）

```yaml
payload:
  version: pilot01-r2
  target: /kirikiri/haruno
  startup: /kirikiri/haruno/data.xp3
  marker: sdmc:/switch/kirikiroid2/.galnx_extracted
  source_dir: E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气
  ui_dir: E:/galnx-build/pilot-01/k2nx-ws/build/romfs
  include:
    - "*.xp3"
    - "*.cf"
    - "plugin/*.tpm"
  exclude:
    - "*_chs.xp3"
    - "*.sig"
  keymap:
    profile: generic-vn
  payload_dir: game
  manifest_name: game_files.txt
```

### 4.2 字段表

| 字段 | 必填 | 类型/默认 | 说明 |
| --- | --- | --- | --- |
| `version` | 是 | string，`^[A-Za-z0-9][A-Za-z0-9._-]*$` | 解压代次，写入 `game_files.txt`；include/exclude 变化时必须递增，否则引擎不会重新解压 |
| `target` | 是 | string，绝对 SD 路径，非根 | 首次启动时 payload 的落点，如 `/kirikiri/haruno`；不得是卡根 |
| `startup` | 是 | string，必须在 `target` 下 | 解压完成后引擎启动的文件，如 `/kirikiri/haruno/data.xp3` |
| `marker` | 是 | string，绝对 SD 路径，可带 `sdmc:` 前缀 | 解压成功标记文件，如 `sdmc:/switch/kirikiroid2/.galnx_extracted` |
| `source_dir` | 否 | 路径，默认取 `game.source_dir` | 只读游戏目录；相对路径相对 manifest 所在目录 |
| `ui_dir` | 否 | 路径 | 引擎 romfs UI 目录，其内容整体放到 romfs 根；不配则 `payload-ui` 检查为 skip |
| `include` | 否 | string[]，默认 3 条 | 以 `source_dir` 为根的 glob；给空数组非法 |
| `exclude` | 否 | string[]，默认 `*.sig` 等 2 条 | include 命中后再剔除；可给空数组 |
| `keymap` | 否 | string 或对象 | 字符串 = profile 名简写；对象字段 `profile` / `template` / `bindings` / `file` |
| `payload_dir` | 否 | 默认 `game` | romfs 下放 payload 的子目录名（不得含 `/` 或反斜杠） |
| `manifest_name` | 否 | 默认 `game_files.txt` | 清单文件名（不得含路径分隔符） |
| `notes` | 否 | string | 操作者备注，工具不消费 |

### 4.3 校验接线

- `schemas/payload.schema.json`：13 个属性、`additionalProperties: false`、必填 4 项、字段级 pattern（target/marker 拒绝控制字符与空格、`payload_dir`/`manifest_name` 拒绝分隔符、keymap 用 `oneOf`）。
- `schemas/game-manifest.schema.json`：顶层新增可选 `"payload": {"type": "object"}`（宽松占位，详细校验交给 payload schema），旧 manifest 行为不变。
- `src/galnx/manifest.py`：`validate()` 在 schema → input → engine 之后追加 `validate_manifest_payload(data.get("payload"), base_dir=base_dir)`；无 `payload` 段返回空列表。
- 错误格式：`payload/target: 'x' is not of type 'string'` 或 `payload: unknown payload fields: foo`；schema 错误路径前缀固定 `payload/`。

## 5. 文件选择与分类

- 扫描入口 `scan_payload(source_dir, include, exclude)`：`os.walk` 后对每个普通文件用 `normalize_relpath` 得到 POSIX 相对路径，先 `match_any(rel, include)` 再 `!match_any(rel, exclude)`；符号链接不跟随（`os.walk(followlinks=False)`），符号链接目标存在风险时记 `payload-symlink` warn。
- 排序：`sort_files` 按（分类序，相对路径）稳定排序，分类序即 `xp3 → config → plugin → font → other`。这保证同一批文件每次生成的 `game_files.txt` 顺序一致（与目录遍历顺序无关）。
- 大小写：匹配按字面（`fnmatch.fnmatchcase`），但 SD 卡/FAT32 大小写不敏感，因此另做 casefold 冲突检查（`payload-name-collision`，含与 `manifest_name` 的冲突）。
- 试点选择结果：`*.xp3` 命中 17 个 → 排除 3 个 `*_chs.xp3` 得 14 个；加 `haruno.cf` 1 个、`plugin/*.tpm` 7 个，共 22 个；`Kirikiroid2Preference.xml` 为生成文件（共 23）。`.sig`、`krmovie.dll`、`simhei.ttf`/`simsun.ttc` 均未选入（默认 exclude 与 include 未覆盖）。

## 6. game_files.txt 规格

格式固定、可逐字节复现（黄金样本：`examples/payload/expected/game_files.pilot01.txt`，28 行、600 B、sha256 `0e6757d9901d4a4abb95a220f9d8e1714b0b858c421ec328e6802a10d4e3fd61`）：

```text
version=pilot01-r2
bytes=2870635309
target=/kirikiri/haruno
startup=/kirikiri/haruno/data.xp3
marker=sdmc:/switch/kirikiroid2/.galnx_extracted
file=data.xp3
file=image00.xp3
...（共 23 行 file=，顺序 = 分类序 + 相对路径排序）
file=Kirikiroid2Preference.xml
```

规则（实现于 `content.render_game_files`）：

- 编码 UTF-8、换行 LF、**结尾必须有换行**；头部 5 行顺序固定：`version/bytes/target/startup/marker`。
- `target` 必须以 `/` 开头且不是根；写出时去掉尾部 `/`；`startup` 必须落在 `target/` 前缀下。
- `bytes` = 全部 payload 文件（含生成的 keymap）大小之和，**不含** UI 文件与清单自身：试点 2,870,634,016 + 1,293 = 2,870,635,309。
- `file=` 的 rel 相对 payload 根（不带 `game/` 前缀），重复 rel 直接报错。
- 四个头部值都不得含换行；空字符串报错。
- `parse_game_files` 是严格反向解析（用于黄金样本校验和 plan 自检）：要求结尾换行、头部顺序一致、`bytes` 可转 int、之后每行必须 `file=`。

## 7. 键位映射（Kirikiroid2Preference.xml）

### 7.1 为什么需要它

K2NX 把 Switch 手柄按键转换成 Windows 虚拟键码（VK）后再交给 KiriKiri 的 `KeyMap` 逻辑。证据（K2NX 源码，只读核对）：

- `src/core/base/ScriptMgnIntf.cpp:308-320`：`VK_PADLEFT=0x1B5(437)` … `VK_PAD1=0x1C0(448)` … `VK_PAD10=0x1C9(457)`。
- `src/core/base/CCKeyCodeConv.cpp:191-206`：`BUTTON_A→VK_PAD1`、`B→VK_PAD2`、`X→VK_PAD4`、`Y→VK_PAD5`、`LEFT_SHOULDER→VK_PAD7`、`RIGHT_SHOULDER→VK_PAD8`、`START→VK_PAD9`、`SELECT→VK_PAD10`。
- `src/core/MainScene.cpp:1749-1756`：用 `IndividualConfigManager::GetKeyMap()` 组映射；per-game 文件由 `UsePreferenceAt(folder)` 读取，`folder = PathSplit(startup).first`。

因此 payload 根放一份 `Kirikiroid2Preference.xml`，K2NX 从游戏目录读取它就是「该游戏的键位」。

### 7.2 默认绑定（`DEFAULT_BINDINGS`）

| 手柄输入 | pad VK | → Windows VK | 语义 |
| --- | --- | --- | --- |
| A | 448 (VK_PAD1) | 13 VK_RETURN | 确认 / 推进文本 |
| B | 449 (VK_PAD2) | 27 VK_ESCAPE | 菜单 / 返回 |
| X | 451 (VK_PAD4) | 32 VK_SPACE | 推进（备用） |
| 十字键左 | 437 (VK_PADLEFT) | 37 VK_LEFT | 菜单左移 |
| 十字键上 | 438 (VK_PADUP) | 38 VK_UP | 菜单上移 |
| 十字键右 | 439 (VK_PADRIGHT) | 39 VK_RIGHT | 菜单右移 |
| 十字键下 | 440 (VK_PADDOWN) | 40 VK_DOWN | 菜单下移 |

### 7.3 生成方式与黄金样本

- 模板 = `src/galnx/payload/templates/k2nx/Kirikiroid2Preference.xml`（1,293 B，sha256 `aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543`，即 `docs/builds/patches/k2nx-switch/keymap/Kirikiroid2Preference.xml` 的逐字节副本）。
- `render_with_template(bindings)`：解析模板里的 `<KeyMap key="N" value="M"/>` 行，只改写 M 的数字；注释、缩进、行内对齐空格全部原样保留。模板 pad 集合必须与绑定集合完全一致，否则报 `keymap template mismatch`。
- 默认绑定渲染结果与模板**逐字节相同** → sha256 恒为黄金值；`verify_golden()` 的 3 项检查即验证这一点（CLI `payload verify` 会打印）。
- 若需要新键位（如 `show_history/auto_mode/skip_hold` 绑定 MINUS/Y/R/L），用 `keymap.bindings` 覆盖默认 7 条，或提供自己的模板；未覆盖的动作由 `profile_alignment` 报 warn。
- 与 input profile 的关系：`keymap.profile`（如 `generic-vn`）**只用于覆盖检查**，不参与生成；默认 7 条绑定是 K2NX 的既有约定，profile 的 7 个语义动作中 `show_history/auto_mode/skip_hold` 未被覆盖 → `payload-keymap-profile` 为 warn（试点实测）。这是有意的：把这 3 个动作绑到 MINUS/Y/R/L 需要额外 VK 语义（K2NX 对 MINUS/Y 有独立映射），留待输入层真机验证后再定。

## 8. romfs 组装计划与 materialize

### 8.1 计划（`build_plan`，只读）

`build_plan(config, source_dir=None, ui_dir=None, link_mode="copy")` 不做任何写入；产出的 `PayloadPlan` 含：`files`（选中）、`generated`（keymap）、`ui_files`、`manifest_text`、`keymap_text`、`checks`。派生属性：`payload_bytes`（含生成文件）、`ui_bytes`、`manifest_bytes`、`romfs_total_bytes`、`errors()`、`warnings()`、`is_ok()`。

16 项检查（按固定顺序；名称即文本输出里的 name 列）：

| # | check id | 名称 | 通过条件 / 失败示例 |
| --- | --- | --- | --- |
| 1 | `payload-link-mode` | romfs link mode | 模式合法（copy/hardlink/symlink） |
| 2 | `payload-source` | payload source directory | `source_dir` 存在且是目录 |
| 3 | `payload-files` | payload selection | 至少选中 1 个文件；detail「N files, M bytes」（不含生成文件） |
| 4 | `payload-keymap` | generated keymap | 生成成功；detail「file, N B, sha256 ...」 |
| 5 | `payload-keymap-golden` | keymap matches pilot-01 golden sample | 仅当用默认绑定且未换模板时添加；sha256 等于黄金值 |
| 6 | `payload-keymap-profile` | keymap vs input profile | 配了 profile 且所有动作被覆盖才 ok，否则 warn（详情列出未绑定动作） |
| 7 | `payload-manifest` | game_files.txt | 渲染后再 parse 回读，头部/files/bytes 全一致；detail「N lines, N B, sha256 ...」 |
| 8 | `payload-startup` | startup file in payload | `startup` 相对 `target` 的 rel 在选中文件里（通常 data.xp3） |
| 9 | `payload-name-collision` | case-insensitive name collisions | casefold 后无重复；含与 `manifest_name` 的冲突 |
| 10 | `payload-path-length` | path length limit | `max(len(target/rel), len(romfs:/payload_dir/rel))` ≤ 259；>200 warn，>259 fail |
| 11 | `payload-fat32-limit` | FAT32 per-file limit | 无文件 > 4 GiB-1；否则 warn（exFAT 需要） |
| 12 | `payload-symlink` | symlinked payload files | 无符号链接；有则 warn |
| 13 | `payload-sparse` | sparse payload files | 无稀疏文件（Windows 属性 0x200）；有则 warn |
| 14 | `payload-ui` | engine UI files | 配了 ui_dir：存在、非空；未配 → skip |
| 15 | `payload-ui-collision` | UI vs manifest name | ui_dir 里没有与 `manifest_name` 同名文件（否则 fail） |
| 16 | `payload-total` | payload total | 汇总：payload/UI/manifest 文件数与字节、romfs 总字节 |

### 8.2 落盘（`materialize`）

映射：`ui_files → out/<rel>`；`files → out/<payload_dir>/<rel>`；keymap → `out/<payload_dir>/<keymap_file>`；清单 → `out/<manifest_name>`。写入顺序：UI → payload → keymap → 清单。

安全规则：

- 计划有 fail 且未给 `force=True` → 拒绝（`PayloadError: refusing to materialize a plan with failed checks: ...`）。
- 目标文件已存在且未给 `force` → 拒绝（`refusing to overwrite <path> (pass force=True)`）。
- 模式：`copy`（默认，`shutil.copy2`）、`hardlink`（先 `os.link`，同卷失败自动回退 copy 并计入 `fallback_copy`）、`symlink`（`os.symlink`，失败直接报错）。
- 返回字典：`out_dir/mode/payload_files/generated_files/ui_files/bytes/manifest{path,bytes,sha256}/hardlinked/fallback_copy/symlinked/ok`；`bytes` 含 UI+payload+keymap+清单。
- 已知行为：对**已存在**文件用 `force` 时，`os.link` 因目标存在必然失败 → hardlink 模式全部回退 copy（实测 forced 6 个文件全部 fallback）；这是可接受的降级，但大 romfs 重复 materialize 时不要指望硬链接。

## 9. CLI 用法与实跑证据

### 9.1 用法（`PYTHONPATH=src python -m galnx payload ...`；仓库未安装 console script）

```bash
# 1) 只读计划（文本 + 全部检查）
PYTHONUTF8=1 python -m galnx payload plan --manifest examples/payload/manifest.pilot01.yaml

# 2) 计划 JSON（--no-files 省略文件清单，便于粘贴/对比）
PYTHONUTF8=1 python -m galnx payload plan --manifest examples/payload/manifest.pilot01.yaml --no-files --json

# 3) 生成 romfs（默认 copy；输出目录不能是已有内容的目录，除非 --force）
PYTHONUNBUFFERED=1 PYTHONUTF8=1 python -m galnx payload materialize \
    --manifest examples/payload/manifest.pilot01.yaml --out E:/galnx-build/pilot01/romfs

# 4) 黄金样本与 schema 自检（不读游戏目录）
PYTHONUTF8=1 python -m galnx payload verify --json
PYTHONUTF8=1 python -m galnx payload verify --manifest examples/payload/manifest.pilot01.yaml --json
```

环境变量：本机控制台代码页为 cp936。P3-e 起正式入口 `main()` 首行调用 `force_utf8_stdio()`（cli.py:20 / cli.py:842）把 stdout/stderr 重配为 UTF-8，所以上面命令里的 `PYTHONUTF8=1` 只是双保险、可省略；绕开入口直接调用模块 API 时仍建议设置。

### 9.2 试点实测输出（`plan`，2026-10-30）

```text
Payload plan: /kirikiri/haruno -> romfs:/game
  payload version: pilot01-r2
  payload files:   22 selected + 1 generated, 2870635309 bytes
  ui files:        85, 7551013 bytes
  romfs total:     2878186922 bytes
  extraction list: game_files.txt, 28 lines, 600 bytes
  keymap:          Kirikiroid2Preference.xml, 1293 bytes
[OK  ] payload selection                      22 files, 2870634016 bytes
[OK  ] keymap matches pilot-01 golden sample  sha256 aa4fa8aab2... (完整 sha256 见 JSON)
[WARN] keymap vs input profile                advance_text=A; confirm_choice=A; back=B; open_menu=PLUS+X; show_history=MINUS+Y (unbound); auto_mode=R (unbound); skip_hold=L (unbound)
...
[OK  ] payload total                          23 payload files, 2870635309 bytes; ui 85 files, 7551013 bytes; manifest 600 B; romfs 2878186922 bytes

15 checks: 0 fail, 1 warn
```

15 项而非 16：`payload-ui-collision` 只在检测到冲突时才添加（试点无冲突）。warn 只有 `payload-keymap-profile`，不阻塞 materialize。

与真实 A2 romfs（`E:/galnx-build/pilot-01/nsp/romfs-a2`，P1-d 用临时脚本 `make_payload_a2.py` 生成）逐项对齐：

| 项 | A2 实际 | 本模块 plan | 一致 |
| --- | --- | --- | --- |
| romfs 文件总数 | 109（85 UI + 23 payload + 1 清单） | 85 + 23 + 1 | 是 |
| payload 文件数 | 23 | 22 + 1 generated | 是 |
| payload 字节 | 2,870,635,309 | 同 | 是 |
| romfs 总字节 | 2,878,186,922 | 同 | 是 |
| game_files.txt | 28 行 / 600 B / sha256 `0e67...` | 同（sha256 逐字节相同） | 是 |
| keymap | 1,293 B / sha256 `aa4f...` | 同 | 是 |
| 分类计数 | — | xp3 14 / config 1 / plugin 7 / other 1 | — |
| UI 字节 | 7,551,013 | 同 | 是 |

### 9.3 fixture materialize 实测

用小目录（4 个 payload 文件 + 2 个 UI 文件，合计 265 B）验证落盘：

- `payload_files=4 / generated_files=1 / ui_files=2 / bytes=1806`；清单 10 行 239 B sha256 `5b4ee0bbcf283ec5d4e50ef5ec75af014dd7262795c18c0b6c00b1d6825a5eaa`。
- 输出树 8 个文件（含 `Default/icon.png`、`img/ui.png`、`game/data.xp3`、`game/plugin/csvParser.tpm`、`game/simhei.ttf`、`game/Kirikiroid2Preference.xml`、`game_files.txt`）。
- hardlink 模式在全新目录：`hardlinked=6, fallback_copy=0`；对已存在目录重复 materialize 无 `--force` → 退出码 2。

证据目录（仓库外，可重跑）：`E:/galnx-build/p3a-evidence/`，含 `run_evidence.py`、`plan-pilot-path.txt`、`plan-pilot-full.json`、`plan-pilot-no-files.json`、`plan-fixture.json`、`verify-text.txt`、`verify-json.txt`、`verify-manifest-json.json`、`materialize-human.txt`、`materialize.json`、`materialize-refused.json`、`materialize-force.json`、`materialize-tree.txt`、`summary.json`。

### 9.4 JSON 输出契约

plan（`--json`，单文档）：`version`、`manifest_path`、`config`、`files`（`--no-files` 时为 null）、`file_count`、`total_file_count`、`files_bytes`、`generated`、`generated_bytes`、`total_bytes`、`categories`、`ui_file_count`、`ui_bytes`、`romfs_total_bytes`、`max_rel_path_length`、`max_device_path_length`、`max_romfs_path_length`、`manifest`、`keymap`、`link_mode`、`checks`、`ok`、`errors`、`warnings`。

注意两种 errors 形态（CLI 现状，接入时保持一致）：

- `plan --json` 的 `errors | warnings` 是 **check 字典数组**（`{id,name,status,detail,hint}`）。
- `materialize/verify --json` 的 `errors` 是**字符串数组**（detail 文本）。

materialize：`version`、`manifest_path`、`out_dir`、`result{...}`、`checks`、`ok`、`errors[]`。verify：`version`、`manifest_path`（可为 null）、`checks`（3 项 keymap + 可选 manifest/payload 检查）、`ok`、`errors[]`。

### 9.5 正式 CLI 证据文件

正式入口（`PYTHONPATH=src python -m galnx payload ...`，2026-10-30 实测）的输出存于 `E:/galnx-build/p3a-evidence/`：

| 文件 | 命令 | 结果 |
| --- | --- | --- |
| `payload-cli-verify.json` | `payload verify --json` | exit 0；3 项 keymap 检查全 ok，`ok: true` |
| `payload-cli-verify.txt` | `payload verify` | exit 0；文本输出 3 项 OK |
| `payload-cli-plan.json` | `payload plan --manifest examples/payload/manifest.pilot01.yaml --no-files --json` | exit 0；22 选中 + 1 生成，2,870,635,309 B |
| `payload-cli-plan.txt` | 同上（文本） | exit 0；15 checks: 0 fail, 1 warn |
| `payload-cli-help.txt` | `payload --help` | exit 0；列出 plan/materialize/verify |

仓库归档副本：`docs/milestones/evidence/P3a-payload-cli-*`（与上述文件逐字节相同，`cmp` 已核对），哈希清单 `docs/milestones/evidence/P3a-artifacts-sha256.txt`。

## 10. 退出码

| 退出码 | 含义 |
| --- | --- |
| 0 | 无 fail 级检查（warn 不影响退出码）；materialize 成功 |
| 2 | plan 存在 fail 检查；materialize 拒绝覆盖 / 计划不通过；参数非法（argparse）；manifest 解析或校验失败 |

verify 在 manifest 段校验失败时同样返回 2。

## 11. 与 manifest / CLI 的集成

已完成（本任务改动的共享文件，需 Lead 复核）：

- `schemas/game-manifest.schema.json`：顶层新增可选 `payload` 属性（宽松 object）。
- `src/galnx/manifest.py`：`validate()` 末尾追加 payload 段校验；docstring 更新。

**CLI 接线已完成**（Lead 在 `src/galnx/cli.py` 的两处实际改动）：

```python
# cli.py:14（文件顶部，与 package_cli 等 import 并列）
from .payload import cli as payload_cli

# cli.py:703（build_parser() 内，package_cli.register(sub) 之后）
payload_cli.register(sub)
```

`register()` 内部自己 `set_defaults(func=cmd_payload_plan/materialize/verify)`，`main()` 分发逻辑无需改动。正式入口已实测：`verify` 与 `plan` 均 exit 0（证据文件见 §9.5）。

向后兼容：无 `payload` 段的旧 manifest 校验结果不变（schema 顶层仍 `additionalProperties: false`，payload 是新增可选属性）；既有测试全部保持通过。

## 12. 测试

```bash
cd Workspace/GalNX
python -m pytest tests/test_payload_content.py tests/test_payload_keymap.py \
                 tests/test_payload_plan.py tests/test_payload_cli.py -q
# 105 passed

python -m pytest -q
# 本任务完成时（2026-10-30 09:01）：600 passed, 63 subtests passed（含其它并行任务新增用例）
# 本任务开工基线为 401 passed / 63 subtests；本任务新增 105 用例；
# 其它并行任务仍在增加用例，全仓总数会变化，以本文件 105 为准。
```

| 文件 | 用例数 | 覆盖 |
| --- | --- | --- |
| `tests/test_payload_content.py` | 23 | 路径规范化/分类、glob 语义（`*` 不跨目录、`**`、`..` 拒绝）、扫描、排序、`game_files.txt` 渲染与解析往返、错误分支 |
| `tests/test_payload_keymap.py` | 23 | pad/VK 解析别名、绑定规范化与校验、模板渲染逐字节、黄金 sha256、`profile_alignment`、`parse_keymap` |
| `tests/test_payload_plan.py` | 39 | Config 校验（未知字段/路径/keymap）、16 项检查各分支、JSON 视图、`materialize` 三种模式与拒绝覆盖、错误聚合 |
| `tests/test_payload_cli.py` | 20 | `register` 子命令树、plan 文本与 JSON、materialize、verify、退出码、试点真实数据集成（数据缺失时 `pytest.skip`） |

测试不写仓库内文件：materialize 一律用 `tmp_path`；试点集成测试读 `examples/payload/manifest.pilot01.yaml` 与其 `expected/` 黄金副本，游戏目录不存在时跳过。

## 13. 限制与未验证项

1. **CLI 已接入并实测**（Lead 完成 cli.py:14 / cli.py:703）：`verify`/`plan` 走正式入口 exit 0；`materialize` 在 fixture 上走等价临时 register 链路验证，正式入口的 `materialize` 真实 2.9 GB 运行已由 Lead P3-e 实测成功（见第 2 条）。
2. **2.9 GB 规模 materialize 已实测（Lead P3-e，2026-10-30）**：`galnx payload materialize --manifest examples/pilot01-haruno.yaml --out E:/galnx-build/pilot-01/p3/romfs` 真跑成功，109 files / 2,878,186,922 B，0 fail 1 warn；该 romfs 随后用于 A3 NSP 构建。真实拷贝耗时与磁盘峰值以该次实测为准；失败后的半成品回滚仍无保护（见第 8 条）。
3. **引擎侧未真机验证本模块输出**：P1-d 已验证真实 romfs-a2 能装能跑，但那是临时脚本产物；本模块生成的 romfs 尚未上机（与 P1-d 布局字节一致是主要依据）。
4. **键位默认绑定只覆盖 7 条**：`show_history/auto_mode/skip_hold` 未绑定（warn）；MINUS/Y/R/L 的 VK 语义与 K2NX 实际表现未真机验证；输入层 toggle 组合（M2-b）同样未真机验证。
5. **`--force` 覆盖时硬链接全部退化为 copy**（`os.link` 目标存在失败），已实测；重复 materialize 大 romfs 会多写一份。
6. **路径长度阈值是 Windows 视角**：259/200 用于保护构建主机；Switch romfs/FAT32 的路径上限、单目录文件数上限未实测。
7. **文件名约束有限**：schema 禁止 target/marker 含空格与控制字符，但 payload rel 路径只校验 `..`/反斜杠/冒号；中文与超长文件名未做专门测试（试点文件名全 ASCII）。
8. **无并发与原子性保护**：materialize 直接写目标目录，多实例并发会互相覆盖；失败时已写文件不会回滚。
9. **选择规则按试点游戏定制**：默认 include/exclude 对 KiriKiri2 游戏够用；其他引擎（ONScripter/Brewser）的 payload 形态不同，接入时需扩展默认值或按引擎提供预设。
10. **未处理 `.sig` 之外的原版附带文件**（如 `krmovie.dll`、字体 `.ttf/.ttc` 默认不选）；是否应随包由各游戏审计结论决定。
11. **JSON 中文编码**：P3-e 起 `cli.py:842` 的 `main()` 首行调用 `force_utf8_stdio()`（cli.py:20，stdout/stderr reconfigure 为 UTF-8），正式入口 `python -m galnx ...` 不再需要 `PYTHONUTF8=1`；但直接调用模块 API / 自定义脚本仍受 cp936 控制台影响，需自行设置（本模块测试用捕获流，不受影响）。
12. **schema 与实现存在两处宽松**：`keymap.bindings` 的值上限 schema 允许 0-255 但实现只接受 0x08-0xFE；`payload_dir/manifest_name/file` 的 pattern 只拒绝分隔符，未限制 Windows 保留名（CON/NUL 等）。测试未覆盖这些边角。

## 14. 相关文件与文档

| 文件 | 说明 |
| --- | --- |
| `src/galnx/payload/content.py` | 分类、选择、`game_files.txt` 渲染/解析 |
| `src/galnx/payload/keymap.py` | K2NX 键位映射生成与黄金样本校验 |
| `src/galnx/payload/plan.py` | PayloadConfig / PayloadPlan / build_plan / materialize / schema 校验 |
| `src/galnx/payload/cli.py` | `payload plan / materialize / verify` 三条命令 |
| `src/galnx/payload/templates/k2nx/Kirikiroid2Preference.xml` | 黄金键位模板（逐字节副本） |
| `schemas/payload.schema.json` | payload 段 JSON Schema |
| `schemas/game-manifest.schema.json` | manifest schema（新增可选 payload 段） |
| `src/galnx/manifest.py` | manifest 校验链（已接 payload） |
| `examples/payload/manifest.pilot01.yaml` | 试点完整 manifest（含 payload 段） |
| `examples/payload/expected/game_files.pilot01.txt` | 黄金清单（600 B） |
| `examples/payload/expected/Kirikiroid2Preference.xml` | 黄金键位（1,293 B） |
| `tests/test_payload_*.py` | 105 个用例 |
| `docs/builds/005-nsp-selfcontained.md` | M3-a/P1-d：A2 romfs 与 NSP 打包链实测 |
| `docs/pilot/P1-nsp-packaging.md` | P1-d：A1/A2 试点打包与真机/模拟器验收 |
| `docs/pilot/P1-game-audit.md` | P1-c：试点游戏数据审计（xp3/插件/汉化/sig 结论） |
| `docs/packaging/README.md` | M3-c：打包数据模型与契约 |
| `docs/packaging/nsp-build.md` | P3-b：NSP 打包驱动器（消费本模块产出的 romfs） |
| `docs/PLAN_DRAFT_v0.1.md` | 计划草案（P3-a 任务定义） |
