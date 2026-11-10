# GalNX 输入配置数据模型（M2-b）

- 文档状态：已实现（2026-10-30）
- 对应任务：task-17 / M2-b「输入配置数据模型」
- 代码位置：`src/galnx/input/`
- 相关文件：`schemas/input-profile.schema.json`、`examples/input-profile.kb-mouse.yaml`、`tests/test_input_*.py`
- 范围：数据模型 + 校验 + manifest 解析；**不含 HID 注入**（注入属后续工作台实现）

## 1. 目标与范围

本层定义「玩家输入 → 语义动作 → 引擎按键」的数据模型，并提供：

1. 4 个内置 profile（键盘鼠标模拟、通用 VN、krkrsdl2、krkr-ns 引擎覆写）
2. profile 文件的 JSON Schema 校验与零异常检查（`galnx input validate`）
3. manifest 的 input 段解析：默认模式、组合键、profile 引用
4. 冲突检测（同键多语义、热键重叠、引擎事件歧义等）

不做：HID 注入、组合键拦截、指针缩放/边缘裁切——这些属于工作台（M2 后续任务）。

## 2. 模块布局

| 文件 | 内容 |
| --- | --- |
| `src/galnx/input/__init__.py` | 公共 API 导出 |
| `src/galnx/input/semantic.py` | 语义动作/按钮/热键枚举，combo 解析，KeyBindings 双向映射，冲突检测 find_conflicts |
| `src/galnx/input/profiles.py` | InputProfile 数据类，schema 校验，YAML 加载，ProfileCheck |
| `src/galnx/input/builtin.py` | 4 个内置 profile 定义（不依赖 schema 文件即可 import） |
| `src/galnx/input/resolve.py` | manifest input 段解析（模式/组合键/profile 引用）→ ResolvedInput |
| `schemas/input-profile.schema.json` | profile 文件 JSON Schema（Draft 2020-12） |
| `examples/input-profile.kb-mouse.yaml` | kb_mouse 示例文件 |
| `tests/test_input_*.py` | 74 个新增单元用例（全套 87 passed） |

## 3. InputProfile 字段

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| name | string | 是 | — | 小写标识，正则 `^[a-z0-9][a-z0-9_-]{1,63}$`（至少 2 字符） |
| description | string | 否 | "" | 人类可读说明 |
| adapter_defaults | object | 否 | {} | 引擎名 → 语义动作 → 引擎事件列表 |
| button_map | object | 否 | {} | 语义动作 → Switch 按钮列表 |
| hotkeys | object | 否 | {} | 仅允许 `toggle_mode` / `soft_reset` |
| mouse | object | 否 | {} | 6 个鼠标功能 → Switch 按钮 |
| analog | object | 否 | deadzone 0.25 / pointer_speed 1.0 / invert_y false | 摇杆参数 |

约束：`adapter_defaults` 的引擎名为小写 slug；`button_map` 的键必须是 7 个语义动作之一；按钮名使用 libnx 名称（A/B/X/Y/L/R/ZL/ZR/PLUS/MINUS/HOME/CAPTURE/DUP/DDOWN/DLEFT/DRIGHT/LSTICK/RSTICK/LUP/LDOWN/LLEFT/LRIGHT/RUP/RDOWN/RLEFT/RRIGHT/SL/SR），另接受别名 `+`（PLUS）与 `-`（MINUS）。

## 4. 语义动作与上下文

| 动作 | 含义 | 上下文 |
| --- | --- | --- |
| advance_text | 推进文本 | text |
| confirm_choice | 确认选项 | choice |
| back | 返回/取消 | menu |
| open_menu | 打开菜单 | menu |
| show_history | 历史/回想 | menu |
| auto_mode | 自动模式 | text |
| skip_hold | 按住快进 | text |

上下文规则：同一按键**可以**在不同上下文绑定不同动作（如 A 同时是 advance_text 与 confirm_choice），但同一上下文内一键多语义视为冲突（`button_ambiguous`）。7 个动作是 M2-b 的最小集合；PLAN §5.2 的 previous_choice/next_choice 等暂未纳入，后续按适配器声明扩展。

## 5. 默认按钮映射（kb_mouse 与内置 VN 共用）

| 语义动作 | Switch 按钮 |
| --- | --- |
| advance_text | A |
| confirm_choice | A |
| back | B |
| open_menu | PLUS、X |
| show_history | MINUS、Y |
| auto_mode | R |
| skip_hold | L |

设计理由：贴近 Switch VN 常见习惯（A 推进/确认、B 返回、PLUS 菜单、MINUS 历史），并让 ZL/ZR 保留给引擎侧快进/跳过（见 §7 LCTRL 覆写）。

## 6. kb_mouse 键鼠模拟

| 鼠标功能 | Switch 按钮 | 作用 |
| --- | --- | --- |
| pointer | RSTICK | 右摇杆模拟鼠标指针 |
| left_click | A | 左键 = 确认/推进 |
| right_click | B | 右键 = 返回 |
| middle_click | Y | 中键 = 历史 |
| wheel_up | DUP | 滚轮上 = 历史记录 |
| wheel_down | DDOWN | 滚轮下 = 历史记录 |

`analog`：deadzone 0.25、pointer_speed 1.0、invert_y false。

模式说明：`keyboard_mouse` 模式下工作台把右摇杆映射为指针、A 映射为左键；`controller` 模式直接透传手柄；`off` 模式不注入任何输入。

## 7. 引擎覆写 adapter_defaults

| 语义动作 | generic（通用 VN） | krkrsdl2 / krkr-ns（KAG3 常见默认） |
| --- | --- | --- |
| advance_text | RETURN、SPACE、MOUSE_LEFT | RETURN、SPACE、MOUSE_LEFT |
| confirm_choice | RETURN、MOUSE_LEFT | RETURN、MOUSE_LEFT |
| back | ESCAPE | MOUSE_RIGHT |
| open_menu | MOUSE_RIGHT | ESCAPE |
| show_history | PAGEUP、MOUSE_WHEEL_UP | PAGEUP |
| skip_hold | LCTRL | LCTRL |

优先级：游戏 profile 的 `adapter_defaults` 覆盖内置同名引擎键，未声明时继承 generic 层。合并顺序由 `InputProfile.adapter_events(adapter)` 实现：先 generic 再 adapter 覆盖。

未验证：KAG3 键位来自任务说明与常见默认（ENTER/空格/左键推进、Ctrl 快进、Esc 菜单、右键返回），**未在真机/Citron 逐键验证**。若引擎实际默认键位不同，只需改 profile 的 `adapter_defaults`，不必改代码。

## 8. 热键与模式切换

- 热键只有两个：`toggle_mode`（切换输入模式）、`soft_reset`（软复位/退出）。
- 组合键写法：字符串 `L+R+PLUS` 或按钮数组 `["L","R","PLUS"]`；至少 2 个按钮；顺序无关；重复按钮报错。
- manifest `input.toggle_combo` 默认 `L+R+PLUS`；若 profile 自带 `toggle_mode` 且与 manifest 不同，以 manifest 为准并记 warning。
- 内置 `kb_mouse` 只有 `soft_reset` 没有 `toggle_mode`，因此默认 manifest 会得到 warning：组合键与 soft_reset 冲突、仅保留作模式切换。这是预期行为；正式配置建议给 profile 设 `toggle_mode` 或改 `toggle_combo` 以消除歧义。
- 组合键命中时必须优先拦截、不得传给游戏（见 §12）。

## 9. 冲突检测规则

| code | severity | 含义 | 例子 |
| --- | --- | --- | --- |
| button_duplicate | error | 同一语义动作内按钮重复（防御性检查） | advance_text: [A, A] |
| button_ambiguous | error | 同一上下文内一键多语义 | A 同时绑定 advance_text 与 back |
| action_unmapped | warning | 某语义动作没有任何按钮绑定 | skip_hold 未绑定 |
| hotkey_duplicate_combo | error | 两个热键使用同一组合键 | toggle_mode 与 soft_reset 都是 L+R+PLUS |
| hotkey_overlap | error | 一个热键组合是另一个的真子集 | L+R 与 L+R+PLUS |
| adapter_key_ambiguous | error | 同一引擎同一上下文一个事件映射到多个动作 | RETURN 同时 is advance_text 与 back |
| mouse_pointer_missing | warning | 声明了 mouse 映射但没有 pointer | mouse 只有 left_click |

错误级冲突会阻止 profile 通过校验（`galnx input validate` 返回 2）；警告只提示。跨上下文复用同键合法。

## 10. manifest 引用与解析

manifest 示例：

```yaml
input:
  default_mode: keyboard_mouse
  toggle_combo: "L+R+PLUS"
  profile: generic-vn
```

解析规则：

1. 无 input 段 → 默认 `keyboard_mouse` + 内置 `kb_mouse`，旧 manifest 继续有效（向后兼容）。
2. profile 可为内置名（`kb_mouse` / `generic-vn` / `krkrsdl2` / `krkr-ns`）或 YAML 路径（含 `/` 或反斜杠或 `.yaml`/`.yml` 视为路径，相对 manifest 所在目录解析）。
3. 未知内置名 → 错误 `input.profile: unknown input profile 'x' (built-in: ...)`；文件不存在 → `input.profile: input profile not found: <绝对路径>`。
4. default_mode 三值：`keyboard_mouse` / `controller` / `off`；非法值由 game-manifest schema 先报错。
5. toggle_combo 覆盖 profile 的 toggle_mode；两者不同记 warning。
6. 校验错误统一为 `<字段路径>: <说明>`，便于 CLI/工作台直接展示。

API：`resolve_manifest_input(manifest, base_dir=...)`、`validate_manifest_input(section, base_dir=...)`；`manifest.load_and_validate()` 已自动附带 input 解析错误。

## 11. CLI 用法

```bash
PYTHONPATH=src python -m galnx input list
PYTHONPATH=src python -m galnx input list --json
PYTHONPATH=src python -m galnx input validate examples/input-profile.kb-mouse.yaml
PYTHONPATH=src python -m galnx input validate path/to/profile.yaml --json
```

退出码：0 = 通过；2 = 校验失败（解析错误或语义冲突）；参数错误由 argparse 返回 2。

输出检查项：`profile.parse` / `profile.name` / `profile.button_map` / `profile.hotkeys` / `profile.mouse` / `profile.adapter_defaults` / `profile.conflicts` / `profile.result`；风格与 `galnx doctor/preflight` 一致（[OK  ]/[WARN]/[FAIL]）。

## 12. 后续注入实现约定（工作台实现者必读）

1. 事件模型统一为 down/up 两态，禁止只发 down；退出/切换模式时必须释放所有按下的按钮与摇杆，防止卡键（PLAN §12 风险）。
2. 组合键优先拦截：模式切换/软复位组合命中时不传给游戏；需设置合理判定窗口避免误触发。
3. 指针：右摇杆→屏幕坐标，按 1280x720 / 1920x1080 基准缩放，处理宽高比与边缘裁切；deadzone/pointer_speed 取自 profile。
4. 输入模式切换必须有屏幕提示（HUD），否则玩家无法感知当前模式（PLAN §9.2 验收要求）。
5. 适配器声明其支持的语义动作；不支持的动作在应用于游戏时应给警告，而非静默丢弃。
6. 引擎键位必须通过 profile 覆盖，代码内不得写死引擎按键。

## 13. 限制与未验证项

- 未实现 HID 注入，未在真机/Citron 验证真实按键路径；本任务只到数据模型与校验。
- KAG3（krkrsdl2 / krkr-ns）键位为常见默认，未逐项真机验证。
- 7 个语义动作是 M2-b 最小集合；PLAN §5.2 的 previous_choice/next_choice 等未纳入。
- mouse 的滚轮/中键映射（DUP/DDOWN/Y）为占位约定，注入实现前未验证游戏内可用性。
- 热键仅 toggle_mode / soft_reset 两种；快速存档、截图等未实现。
- `docs/MANIFEST.md` 的 input 段说明与已知限制已由 Lead 同步更新（2026-10-30，指向本页）。
- 测试覆盖 74 个新用例（全套 87 passed），未覆盖多文件继承等 schema 不支持的 YAML 变体。

## 14. 相关文件

- `src/galnx/input/{__init__,semantic,profiles,builtin,resolve}.py`
- `schemas/input-profile.schema.json`、`schemas/game-manifest.schema.json`（input 段）
- `examples/input-profile.kb-mouse.yaml`、`examples/manifest.krkr.yaml`
- `tests/test_input_{semantic,profiles,manifest,cli}.py`
- `src/galnx/manifest.py`、`src/galnx/cli.py`
- `docs/PLAN_DRAFT_v0.6.md` §5（输入层设计）、§9.2（验收）、§12（风险）

（文档随代码演进；如字段/默认值变更请同步更新本页与 schema。）
