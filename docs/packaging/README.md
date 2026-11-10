# GalNX 打包数据模型与契约（M3-c）

| 项 | 值 |
| --- | --- |
| 文号 | docs/packaging/README.md |
| 任务 | task-21（M3-c：打包数据模型 + 契约校验） |
| 执行 | audit-switch |
| 日期 | 2026-10-30 |
| 状态 | 代码与测试完成；未接入实际打包器（hacBrewPack 由 M3-a 负责，见 005） |

## 1. 目的与范围

本文件描述 GalNX 框架侧的**打包数据模型**（元数据、TitleID、注册表）与**打包契约校验**（目录契约、nstool 文本契约），以及对应的 CLI。范围刻意限定为“只描述与校验，不出包”：

- 不执行 hacBrewPack / npdmtool / elf2nso；
- 不读取、不存储 prod.keys 或任何密钥；
- 不启动模拟器，不做真机安装。

实际打包链路的打通与实测记录见 `docs/builds/005-nsp-selfcontained.md`（M3-a）。

## 2. 三种打包形态对照

### 2.1 对照表

| 维度 | NRO（homebrew） | forwarder NSP | 自包含 NSP |
| --- | --- | --- | --- |
| 资源路径依赖 | 通常从 SD 卡的 `/switch/` 目录运行；资源可用 `elf2nro --romfs` 内嵌进 NRO，也可外置在 SD 卡 | 只含引导用的小程序；游戏资源仍在 SD 卡上，NSP 本身不携带资源 | 资源打进 NSP 的 RomFS，安装后不依赖 SD 卡目录布局 |
| HOME 菜单图标与名称 | 不进 HOME 菜单；由 hbmenu 读取 NRO 内嵌 NACP 的图标/名称显示 | 有独立图标/名称，指向被引导程序 | 有独立图标/名称（来自 Control NCA 的 icon + control.nacp） |
| 存档命名空间 | 默认没有独立安装身份；需要 fs 服务按 title id 挂载存档，hbmenu 启动形态下通常不做持久化存档 | 存档归属被引导的目标程序（forwarder 自身不产生独立存档） | 有独立存档命名空间，SaveDataOwnerId = 该 NSP 的 title_id（M3-a 实测 hacBrewPack 把 SaveDataOwnerId/PresenceGroupId 写成 title_id） |
| 封禁与系统环境风险 | 需要 CFW 或用户态漏洞 + hbmenu 环境；不写 HOME，系统面暴露最小 | 需要 CFW + sigpatches 安装未签名 NSP；写 HOME 列表，暴露面与自包含 NSP 相同 | 需要 CFW + sigpatches；未签名 NSP 无法在官方系统安装，联机/账号存在封禁风险（社区经验，本项目未实测） |
| TitleID 冲突风险 | 不安装到 HOME，无需全局唯一的 base TitleID；但 NACP 中的 id 仍应避免与真实游戏相同 | 需要唯一 base TitleID；与已安装应用冲突时无法安装或覆盖 | 需要唯一 base TitleID；冲突后果最严重（存档命名空间与 HOME 条目被顶掉） |
| 构建工具链 | devkitPro `elf2nro`（NRO 头 + 可选 romfs） | hacBrewPack + forwarder 模板（M3-b 负责） | elf2nso → exefs/main、npdmtool → main.npdm、nacptool → control.nacp + icon，hacBrewPack 出 NSP（M3-a 已验证） |
| 适用场景 | 开发期快速迭代、hbmenu 冒烟 | 复用 SD 卡资源、希望从 HOME 直接启动 | 发行形态、资源自包含、可交付单文件 |

### 2.2 选择建议

1. 开发与调试阶段一律先用 NRO（构建快、无需 keyset、可直接在 hbmenu / Citron 里跑）。
2. 需要从 HOME 启动但资源体积大或需热替换时用 forwarder NSP；此时资源目录仍在 SD 卡，交付文档必须写清目录约定。
3. 正式发行形态用自包含 NSP；必须先经过本文件的 `galnx package plan` 与 `galnx package check` 两道校验。

## 3. 模块布局与公共 API

`src/galnx/package/` 由 5 个文件组成（均为纯 Python，无第三方依赖）：

| 文件 | 职责 |
| --- | --- |
| `src/galnx/package/metadata.py` | `PackageMetadata` 元数据模型、`PackageType` 枚举、版本码、JPEG/BMP 尺寸解析、`validate()` 规则、`from_manifest()` 映射 |
| `src/galnx/package/titleid.py` | TitleID 解析/格式化/分类、系统保留区间、`validate_base()`、`allocate()`、`check_conflicts()` |
| `src/galnx/package/registry.py` | 本地 TitleID 注册表（JSON）读写、查询、冲突检测；只允许 title_id/name/note 三个字段 |
| `src/galnx/package/contract.py` | 目录契约 `check_dir()`、nstool 文本解析 `parse_nstool_output()` 与契约 `check_nstool()`、`Check` 结构 |
| `src/galnx/package/__init__.py` | 公共 API 再导出 |

### 3.1 公共 API 速查

| API | 说明 |
| --- | --- |
| `PackageMetadata.from_manifest(manifest, base_dir)` | 从 manifest 的 game/switch/package 段构造元数据；`base_dir` 决定 icon/romfs 相对路径基准 |
| `PackageMetadata.validate()` | 返回 `list[MetadataIssue]`（field/message/severity），不抛异常 |
| `PackageMetadata.version_code()` | 三段式版本转 u32：`(major << 16) + (minor << 8) + micro`；非法版本抛 `PackageMetadataError` |
| `PackageMetadata.to_dict()` | 稳定可序列化结构（11 个键，见 4.1） |
| `parse_title_id / format_title_id` | 16 hex、大小写与 `0x` 前缀容忍；格式化输出大写 |
| `classify / base_of / patch_id_of / dlc_base_of / dlc_id_of` | TitleID 分类与派生化 |
| `validate_base / check_conflicts / allocate` | 基础 id 规则校验、与已注册集合查冲突、按 GalNX 块分配 |
| `TitleIdRegistry.load / save / add / find / conflicts_for` | 注册表文件读写与查询 |
| `check_dir(root, package_type, expected_title_id)` | 暂存目录契约检查，返回 `list[Check]` |
| `parse_nstool_output(text) / check_nstool(parsed, expected_title_id)` | nstool 文本解析与结构契约检查 |
| `checks_to_dict / has_failures` | 检查结果序列化与失败判定 |

## 4. 元数据（PackageMetadata）

### 4.1 字段表

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `title_name` | str | 空 | NACP 标题名；必填，UTF-8 不超过 0x200 字节 |
| `title_author` | str | 空 | NACP 作者；必填，UTF-8 不超过 0x100 字节 |
| `version` | str | `1.0.0` | 三段式 `major.minor.micro`（各 0-255），可转 version code |
| `title_id` | str | 空 | base TitleID，16 位十六进制；NSP 必填，NRO 可空 |
| `package_type` | `PackageType` | `self_contained_nsp` | 打包形态 |
| `icon_path` | str 或 None | None | 256x256 JPEG；NSP 必填，NRO 可选 |
| `romfs_dir` | str 或 None | None | RomFS 源目录；自包含 NSP 必填且必须存在 |
| `startup_user_account` | int | 0 | NACP StartupUserAccount，允许 0/1/2；NRO 忽略（非 0 只给 warning） |
| `notes` | str | 空 | 自由备注 |
| `base_dir` | Path | `.` | icon/romfs 相对路径的解析基准，通常为 manifest 所在目录 |

`PackageType` 三个取值：`self_contained_nsp`、`forwarder_nsp`、`nro`；对应中文标签分别是自包含 NSP、forwarder NSP、NRO homebrew。

`validate()` 的关键规则：

| 规则 | 严重度 |
| --- | --- |
| title_name 必填且 <= 0x200 字节 | error |
| title_author 必填且 <= 0x100 字节 | error |
| version 必须三段且每段 0-255 | error |
| NSP 的 title_id 必填且必须是合法 base（校验抛出的 error 在 NRO 降级为 warning） | error |
| startup_user_account 必须是 0/1/2 的整数 | error |
| NSP 的 icon 必填、文件必须存在、JPEG 必须是 256x256 | error |
| BMP 256x256 图标 | warning（NACP 实际要求 JPEG） |
| JPEG 缺 EOI（FFD9） | warning |
| 自包含 NSP 的 romfs_dir 必填、必须是存在的目录 | error |
| RomFS 目录为空 | warning |
| forwarder NSP 配置了 romfs_dir | warning（forwarder 不嵌 romfs） |

### 4.2 manifest 的 package 段（schema 扩展，向后兼容）

`schemas/game-manifest.schema.json` 顶层新增**可选** `package` 段；不写该段的旧 manifest 仍然完全有效：

```yaml
package:
  type: self_contained_nsp        # self_contained_nsp | forwarder_nsp | nro
  startup_user_account: 1         # 0..2
  romfs_dir: romfs                # 相对 manifest 所在目录
  icon: artifacts/icon.jpg        # 可选，覆盖 switch.icon
  notes: "Free-form note"
```

`type` 缺省时按 `switch.target` 推导：`nro` → `nro`，否则 `self_contained_nsp`。元数据构造只在此处做映射，不在 schema 里写死，因此旧 manifest 无需改动。

### 4.3 版本、图标与 NACP 字段的关系

- `version` 是**显示版本**（三段式字符串）；`version_code()` 计算 u32 版本码，供 NPDM/CNMT 使用。
- 注意 M3-a 的实测：`nacptool --create` 把版本串写进 NACP 的 `DisplayVersion`（ASCII，会被 NUL 截断），而 `AppVersion`（u32）与 CNMT Version 是另外的字段，M3-a 实测为 0。打包器接入时必须分别显式写入，不能假设一个 `--create` 全写好（见 `docs/builds/005-nsp-selfcontained.md` 结论第 7 条）。
- 图标只解析尺寸与格式（JPEG SOF / BMP 头），不校验色彩空间、EXIF 或压缩质量。

## 5. TitleID 规则与分配

### 5.1 布局

| 概念 | 规则 | 表达式 |
| --- | --- | --- |
| 有效范围 | 0x0100000000000000 – 0x01FFFFFFFFFFFFFF | `TITLE_ID_MIN` / `TITLE_ID_MAX` |
| base（应用本体） | 低 13 位为 0，即 0x2000 对齐 | `id & 0x1FFF == 0` |
| update（补丁） | base 置 bit11 | `base OR 0x800` |
| DLC | base 置 bit12，index 取 0x000-0xFFF | `base OR 0x1000 OR index`，index=0 即 `base + 0x1000` |
| 系统保留 | 0x0100000000000000 起若干段 | 见 5.2 |

`classify()` 的判定顺序：系统保留区间优先 → 低 13 位为 0 判 base → 等于 `base OR 0x800` 判 patch → 大于等于 `base + 0x1000` 判 DLC → 其余 invalid。

### 5.2 系统保留区间（`RESERVED_RANGES`）

| 区间 | 含义 |
| --- | --- |
| 0x0100000000000000 – 0x01000000000007FF | System Modules（fs/ldr/ncm/pm/sm/boot/usb 等） |
| 0x0100000000000800 – 0x0100000000000FFF | System Data Archives |
| 0x0100000000001000 – 0x0100000000001FFF | System Applets（含末尾占位 EndOceanProgramId） |
| 0x0100000000002000 – 0x0100000000002FFF | Development System Applets |

### 5.3 GalNX 分配块

| 常量 | 值 | 说明 |
| --- | --- | --- |
| `GALNX_ALLOCATION_BLOCK_MIN` | 0x0100474100000000 | 块下界 |
| `GALNX_ALLOCATION_BLOCK_MAX` | 0x01004741FFFFFFFF | 块上界 |
| `GALNX_ALLOCATION_START` | 0x010047414C4E0000 | 首选分配起点（含 ASCII “GALN”） |

该块位于 base 空间内，按 0x2000 步进可容纳 524,288 个 base id。它是 **GalNX 自己的本地约定**，不是任天堂注册的号段；`validate_base()` 对块外 id 只给 warning（合法但不推荐），`check_conflicts()` 对块外 id 也给 warning 而不是 error。

### 5.4 分配与冲突检测

```python
from galnx.package import allocate, check_conflicts, format_title_id

new_ids = allocate(existing=known_ids, count=3)
for title_id in new_ids:
    print(format_title_id(title_id))

issues = check_conflicts(new_ids[0], existing=known_ids)
for issue in issues:
    print(issue.severity, issue.code, issue.message)
```

`check_conflicts()` 内部把每个 base 展开成三个派生区间（本体、update、DLC 段）求交，并按 base 去重，每个已存在条目最多报一条 `duplicate` 或 `derived_conflict`。issue code 一览：

| code | 严重度 | 含义 |
| --- | --- | --- |
| `invalid_format` | error | 不是 16 位十六进制 |
| `out_of_range` | error | 超出有效范围 |
| `system_reserved` | error | 落在系统保留区间 |
| `not_base` | error | 该 id 是 update/DLC 而不是 base |
| `not_aligned` | error | 低 13 位不为 0 |
| `duplicate` | error | 与已注册 base 完全相同 |
| `derived_conflict` | error | 与已注册条目的 update/DLC 派生区间重叠 |
| `outside_allocation_block` | warning | 合法但不在 GalNX 分配块内 |

### 5.5 证据与置信度

| 事实 | 来源 | 置信度 |
| --- | --- | --- |
| 有效范围 0x0100000000000000 – 0x01FFFFFFFFFFFFFF；游戏 id 低 13 位为 0（`id & 0xFFFFFFFFFFFFE000`）；update 结尾 0800；DLC 为 base OR 0x1000 OR index（index 0x000-0xFFF），且 base 的倒数第四位 Y 为偶数 | [gbatemp wiki: List of Switch homebrew titleID](https://wiki.gbatemp.net/wiki/List_of_Switch_homebrew_titleID)（社区文档） | 中 |
| “Game updates have the same ProgramId as the main application, except with bitmask 0x800 set.” | [switchbrew: Title list/Games](https://switchbrew.org/w/api.php?action=parse&page=Title%20list%2FGames&prop=wikitext) | 高 |
| update id = title_id + 0x800 | hacBrewPack v3.05 源码 `cnmt.c:22`：`cnmt_ext_header.patch_title_id = cnmt_ctx->cnmt_header.title_id + 0x800;` | 高 |
| DLC base = title_id + 0x1000，SaveDataOwnerId = title_id | hacBrewPack v3.05 源码 `nacp.c:96`：`nacp.AddOnContentBaseId = settings->title_id + 0x1000;`；`nacp.c:94-95` `PresenceGroupId = SaveDataOwnerId = title_id` | 高 |
| 2375 个游戏的 TitleID 实测全部以 0100 开头、低 12 位全 0，范围 0100000000010000 – 0100FFA0093E8000 | 本地解析 [switchbrew: Title list/Games](https://switchbrew.org/w/api.php?action=parse&page=Title%20list%2FGames&prop=wikitext) 全文（2375/2375 符合） | 中（实证统计，非官方规范） |
| 系统模块/数据/小程序/dev 小程序四段区间 | [switchbrew: Title list](https://switchbrew.org/w/api.php?action=parse&page=Title%20list&prop=wikitext) | 高 |
| 自制程序 TitleID 范围与更新规则 | hacBrewPack README 与 gbatemp wiki 相互印证 | 中 |

## 6. TitleID 注册表（registry）

注册表是仓库内的普通 JSON 文件，用来记录“本项目已经占用了哪些 TitleID”。它**只存 title_id、name、note 三个字段**；解析时会拒绝任何额外键，并对含密钥含义的未知字段给出“the registry must not store secrets”的可读错误。

示例：`examples/packaging/titleid-registry.json`

```json
{
  "schema_version": 1,
  "generated_by": "galnx",
  "entries": [
    {
      "title_id": "0100A1B2C3D4E000",
      "name": "sample-kirikiri-game",
      "note": "example registry entry"
    }
  ]
}
```

规则：

- `schema_version` 必须为 1；其他值报 `RegistryError`。
- `title_id` 接受 `0x` 前缀与小写，输入后统一规范化为 16 位大写十六进制。
- `add()` 遇到重复 id 或与现有条目冲突时抛 `RegistryError`；`replace=True` 允许覆盖同 id 条目。
- `load(path, missing_ok=True)` 对不存在的文件返回空注册表（便于首次初始化），`missing_ok=False` 时抛错。
- `conflicts_for(title_id)` 返回 `TitleIdIssue` 列表，语义与 `check_conflicts()` 一致；`errors()` 汇总所有 error 级问题。
## 7. 打包契约校验（contract）

契约校验有两个入口，都是只读的：

1. `check_dir(root, package_type, expected_title_id)`：校验**打包暂存目录**（hacBrewPack 的输入树形态）；
2. `parse_nstool_output(text)` + `check_nstool(parsed, expected_title_id)`：校验**nstool 文本输出**（NSP 层 PFS0 与 NCA 头结构）。

两者都返回统一的 `list[Check]`，`Check` 结构为 `{id, name, status, detail, hint}`，status 取值 `ok` / `warn` / `fail` / `skip`。

### 7.1 目录契约检查项（check_dir）

约定输入树（与 M3-a 的 hacBrewPack 输入一致）：

```text
stage/
  exefs/main              # elf2nso 产物，magic NSO0
  exefs/main.npdm         # npdmtool 产物，magic META
  control/control.nacp    # 0x4000 字节
  control/icon*.dat       # 256x256 JPEG
  romfs/                  # 自包含 NSP 必须有且非空
  npdm.json               # 可选，打包脚本生成的 NPDM 参数存档
```

| check id | 检查内容 | 状态 |
| --- | --- | --- |
| `contract.dir` | 目录存在 | 不存在 fail |
| `contract.type` | package_type 合法 | 非法 fail |
| `contract.exefs.main` | magic NSO0 / NRO0 / 其他 | NSO0 ok；NRO0 warn（NSP 的 ExeFS 应是 NSO）；其他 fail |
| `contract.exefs.npdm` | magic META 且大小 >= 0x80 | 不满足 fail |
| `contract.control.nacp` | 大小必须 0x4000 | 不满足 fail |
| `contract.control.nacp.title` | 从 NACP 头部读 title name | 空标题 warn |
| `contract.control.icon` | 至少一个 `control/icon*`，JPEG 256x256 | 缺失/尺寸错 fail；BMP 256x256 warn |
| `contract.romfs` | 自包含 NSP 的 romfs 目录存在且非空 | 缺失 fail；空目录 warn；forwarder/NRO 为 skip |
| `contract.npdm_json` / `.name` / `.title_id` | 可选 npdm.json 解析、name == Application、title_id 与期望一致 | 解析失败 warn；name 非 Application warn；title_id 不匹配 fail |

### 7.2 nstool 文本契约（check_nstool）

nstool v1.9.2 没有 JSON 输出，只能解析文本。实现按 `[Section]` 分段、`key: value` 取值，能容忍没有 `prod.keys` 时的截断输出（只出现 `[PartitionFs]` 与 `FileNum`，没有 `[NCA Header]`）。

| check id | 检查内容 | 状态 |
| --- | --- | --- |
| `nstool.parse` | 输入是 mapping | 否则 fail |
| `nstool.partition` | 存在 `[PartitionFs]` 段 | 缺失 fail（提示需要 prod.keys 才能深入） |
| `nstool.partition.type` | Type == PFS0 | 否则 fail |
| `nstool.partition.files` | FileNum == 3 | 等于 3 ok；非数字 warn；其他 fail |
| `nstool.ncas` | 是否解析到 NCA 头 | 空则 warn 并结束 |
| `nstool.nca.<i>` | 每个 NCA 输出 Content Type / ProgID / Size | 信息性 ok |
| `nstool.nca.type.program/control/meta` | Program / Control / Meta 三类齐全 | 缺失各自 fail |
| `nstool.progid.consistent` | 全部 NCA 的 ProgID 一致 | 不一致 fail |
| `nstool.progid.expected` | ProgID 等于期望 TitleID（可选参数） | 解析失败 warn；不一致 fail |

### 7.3 实测样例（M3-a 产物，2026-10-30）

对 M3-a 的暂存目录 `/e/galnx-build/m3-tools/work/real-build1` 运行目录契约检查：

```text
[OK  ] exefs/main            NSO0 executable, 84060 bytes
[OK  ] exefs/main.npdm       META NPDM, 972 bytes
[OK  ] control/control.nacp  NACP is 16384 bytes (0x4000)
[OK  ] NACP title name       title name: m0-hello
[OK  ] control icon          icon_AmericanEnglish.dat: JPEG 256x256, 6285 bytes
[OK  ] romfs                 1 files, 29 bytes

6 checks: 0 fail, 0 warn
```

对 NCA 层 nstool 输出（有 prod.keys 时）的检查会额外得到三类 NCA 与 ProgID 一致性结论；对只有 PFS0 头的截断输出则只报 `nstool.ncas` warn。M3-a 记录的三个 NCA ProgID 均为 0x0100000000001000（m0 NSP，309,464 B），可用 `--title-id 0100000000001000` 断言。

## 8. CLI 用法

仓库内尚未安装为命令时，用 `PYTHONPATH=src python -m galnx ...`。

### 8.1 galnx package plan

只读校验 manifest + 元数据并打印打包计划，**不执行任何打包**：

```bash
PYTHONPATH=src python -m galnx package plan --manifest examples/manifest.packaged.yaml
PYTHONPATH=src python -m galnx package plan --manifest examples/manifest.packaged.yaml --json
PYTHONPATH=src python -m galnx package plan --manifest examples/manifest.packaged.yaml \
    --registry examples/packaging/titleid-registry.json
```

文本输出示例（示例 manifest 未随仓库附带 icon/romfs，因此这两项会 fail，属预期）：

```text
Packing plan (self-contained NSP):
  title:    SampleGame
  author:   GalNX
  version:  1.0.0
  title_id: 0100A1B2C3D4E000
  icon:     artifacts/icon.jpg
  romfs:    romfs
  account:  1

[OK  ] manifest           examples\manifest.packaged.yaml
[OK  ] package.type       self_contained_nsp
[OK  ] package.title_id   0100A1B2C3D4E000 (base)
[OK  ] package.version    1.0.0 (version code 0x010000)
[WARN] package.title_id   title id 0100A1B2C3D4E000 is outside the GalNX allocation block 0x0100474100000000-0x01004741FFFFFFFF
[FAIL] package.icon       icon file not found: ...examples/artifacts/icon.jpg
[FAIL] package.romfs_dir  romfs directory not found: ...examples/romfs
[FAIL] package.result     package plan has errors

8 checks: 3 fail, 1 warn
```

`--json` 输出固定键：`version`、`manifest`、`package`（元数据字典或 null）、`checks`、`ok`、`errors`。

### 8.2 galnx package check

校验暂存目录或 nstool 输出：

```bash
PYTHONPATH=src python -m galnx package check --dir /e/galnx-build/m3-tools/work/real-build1
PYTHONPATH=src python -m galnx package check --nstool-json nstool-info-real.log --title-id 0100000000001000
PYTHONPATH=src python -m galnx package check --dir stage/ --type forwarder_nsp --json
```

`--json` 输出固定键：`version`、`kind`（`dir` 或 `nstool`）、`target`、`package_type`、`checks`、`ok`、`errors`。

### 8.3 退出码

| 退出码 | 含义 |
| --- | --- |
| 0 | 没有 fail 级检查（warn 不影响退出码） |
| 2 | 存在 fail 级检查，或参数非法（argparse） |

## 9. 与 manifest / input 的集成与向后兼容

- `package plan` 复用 `galnx.manifest.load_and_validate()`：schema 错误、input 段错误都会先暴露，再进入元数据构造。
- 无 `package` 段的旧 manifest 行为不变：类型按 `switch.target` 推导，`icon` 取 `switch.icon`，`romfs_dir` 为空。
- `schemas/game-manifest.schema.json` 顶层仍为 `additionalProperties: false`，但 `package` 是新增的可选属性，因此旧 manifest 校验结果不受影响（既有 87 项测试保持全绿）。
- 未接入组件：本模块不写 NACP/NPDM/CNMT，也不调用 hacBrewPack；M3-a 的 `scripts/build_nsp_demo.sh` 是当前唯一实际出包路径。

## 10. 测试

```bash
cd Workspace/GalNX
python -m pytest -q
# 234 passed, 51 subtests passed
```

新增 5 个测试文件、147 项用例（既有 87 项未破坏）：

| 文件 | 覆盖 |
| --- | --- |
| `tests/test_package_titleid.py` | 解析/格式化、五类 classify、validate_base 各 code、冲突去重、allocate 跳过已占用 |
| `tests/test_package_metadata.py` | 版本码、JPEG/BMP 尺寸解析、validate 全部规则、from_manifest 推导、to_dict |
| `tests/test_package_registry.py` | 文件往返、未知字段拒绝、重复/冲突、查询、示例注册表 |
| `tests/test_package_contract.py` | 全部目录检查项（含 warn/skip 分支）、nstool 文本解析容错、NCA 契约、Check 序列化 |
| `tests/test_package_cli.py` | plan/check 文本与 --json、退出码、registry、缺失文件、argparse 互斥 |

## 11. 限制与未验证项

1. **未接入实际打包器**：数据模型与契约校验未写进 hacBrewPack 流程；把 `PackageMetadata` 映射到 nacptool/npdmtool 参数是后续工作。
2. **版本字段语义未闭环**：M3-a 证实现有 nacptool 调用下 DisplayVersion 会截断、AppVersion 为 0；模型只计算 version_code，不写 NACP，需在打包脚本中显式补齐。
3. **nstool 解析依赖文本格式**：字段名基于 nstool v1.9.2（2024-10-14）；换版本或换语言环境时可能解析不到字段（只会降级为 skip/warn，不会误报 ok）。
4. **NSP 层校验深度受限**：没有 prod.keys 时 nstool 只输出 PFS0 头，无法深入 NCA；契约检查因此只能验证 FileNum 与已解析到的字段。
5. **NRO 契约最弱**：不校验 NRO 头、NACP 内嵌与 romfs 布局，只做“不检查”级别的跳过；NRO 的正确性依赖构建文档（001/002）与模拟器/真机运行。
6. **图标只验证尺寸与格式**：不校验颜色空间、EXIF、文件上限与其他 NACP 图标（美/欧/日版）的差异。
7. **TitleID 分配块是本地约定**：GalNX 块（0x01004741…）未在任何官方/社区注册表登记，只在本仓库注册表内自洽，不能防止与其他自制项目的碰撞。
8. **注册表无并发保护**：本地 JSON 文件，无锁、无合并策略；多人同时编辑需要人工协调（后续可迁移到带校验的合并流程）。
9. **签名问题不在本模块范围**：任何自制 NSP 都无法产生任天堂有效签名，真机运行依赖 Atmosphère/sigpatches（M3-a 已记录签名必然 FAIL）。
10. **forwarder 契约未覆盖**：forwarder NSP 只跳过 romfs 检查，不校验其引导目标、启动参数与图标来源。

## 12. 相关文件与文档

| 文件 | 说明 |
| --- | --- |
| `src/galnx/package/metadata.py` | 元数据模型与校验 |
| `src/galnx/package/titleid.py` | TitleID 规则、分配与冲突 |
| `src/galnx/package/registry.py` | TitleID 注册表 |
| `src/galnx/package/contract.py` | 目录与 nstool 契约检查 |
| `schemas/game-manifest.schema.json` | manifest schema（含可选 package 段） |
| `examples/manifest.packaged.yaml` | 带 package 段的示例 manifest |
| `examples/packaging/titleid-registry.json` | 示例 TitleID 注册表 |
| `tests/test_package_*.py` | 5 个测试文件 |
| `docs/builds/005-nsp-selfcontained.md` | M3-a：自包含 NSP 打包链实测（产物、keyset 要求、签名结论） |
| `docs/milestones/M3-nsp.md` | M3 阶段验收记录 |
| `docs/MANIFEST.md` | manifest 字段的通用说明 |
