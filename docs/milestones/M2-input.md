# M2 输入层与通用配置

- 状态：**done（模拟器级）**（运行时 HID 注入与组合键拦截只在 Citron 验证，真机待 M3-d/M5）
- 日期：2026-10-30（Asia/Shanghai）
- 关联任务：task-16（M2-a，audit-web）、task-17（M2-b，audit-switch）、task-18（M2-c，audit-engines）、M2-d 由 Lead 汇总
- 上游依据：计划 v0.6 §5.4（输入层实现进展）、§10 M2 验收、§5 输入语义映射

## 1. 目标与验收标准

计划 L443-450 的 M2 验收四条，逐条判定：

| # | 验收标准 | 判定 | 依据 |
| --- | --- | --- | --- |
| 1 | 建立统一输入事件模型 | ✅ 数据模型完成 | `src/galnx/input/`：7 个语义动作（advance_text / confirm_choice / back / open_menu / show_history / auto_mode / skip_hold）+ 3 类上下文；`schemas/input-profile.schema.json` |
| 2 | 基础键鼠模拟可在至少一个原生或 Web 运行时使用 | ✅ 原生（Citron 模拟器）实测 | 鼠标 SendInput → KAG3 链接点击 diff 0.494465；键盘 PostMessage → advance diff 0.556076；见 §5 |
| 3 | 支持 key-down/up、mouse-down/up、触摸事件和组合键拦截 | ◐ 数据模型覆盖，运行时拦截未落地 | profile 含 mouse 6 项功能（左/右/中/滚轮上/下/指针缩放）、analog（摇杆轴/死区/灵敏度）、hotkeys 组合键（如 L+R+PLUS）；**拦截发生在引擎/适配器层，本里程碑只定义契约**（krkrsdl2 侧未改） |
| 4 | 支持游戏专用映射与能力校验 | ✅ | 4 个内置 profile（kb_mouse / generic-vn / krkr-ns / krkrsdl2）+ 7 条冲突规则（button_duplicate、button_ambiguous、action_unmapped、hotkey_duplicate_combo、hotkey_overlap、adapter_key_ambiguous、mouse_pointer_missing）+ `galnx input list/validate` CLI + manifest `input` 区块校验 |

补充说明：验收第 1/4 条是**框架侧**交付（纯 Python，可回归）；第 2 条是**模拟器侧**行为证据（Citron）；第 3 条在框架侧只到数据契约，真实 HID 事件队列（key-down/up 状态快照、触摸注入）要等 M4/M5 的引擎适配层实现。KAG3 取证结论明确指出引擎需要「按住状态快照」而非仅边沿事件（`checkProceedingKey` 用 getKeyState 轮询，MainWindow.tjs L3929-3961），这一点已写入 input/README.md 的适配器需求。

## 2. 环境与版本

| 组件 | 版本/哈希 | 用途 |
| --- | --- | --- |
| Citron 模拟器 | nightly 0237a9b88（Windows x64 msvc zip 40,497,628 B sha256 0d2c9bf3…） | 输入注入实测后端 |
| krkrsdl2 NRO | build5 clean 版 17,911,329 B sha256 8124ffd2…（M1-c） | 被测游戏运行时 |
| KAG3 demo 内容 | data-withfont.xp3 6,628,897 B sha256 56538c91…（IPAexGothic） | 被测剧本 |
| Python | 3.x（本机 python，`PYTHONPATH=src` 运行 CLI） | 框架侧与测试 |
| pytest | 87 passed + 11 subtests（M2 交付后、commit 1e86d36 前实测） | 回归 |

Citron 输入配置要点（只读取证，未改用户配置）：键盘映射 A/B/X/Y=C/X/V/Z、PLUS/MINUS=M/N、方向键=16777234-16777237、左摇杆=Shift+W/A/S/D；`keyboard_enabled=false` 只门控 HID 键盘设备，不门控 input_common 键盘→手柄映射（src/hid_core/resources/keyboard/keyboard.cpp:44 对比 src/input_common/drivers/keyboard.cpp）。

## 3. 步骤与命令

harness 输入注入（M2-a 交付）：

```bash
bash scripts/citron_run.sh \
  --nro /e/galnx-build/m1-krkrsdl2/build5/krkrsdl2.nro \
  --expect-title Kirikiri --timeout 90 \
  --input-click 861,589 --input-delay 2500 --input-settle 3000
# 键盘通道：--input-keys C（或 67 / DOWN / ENTER）
# 输出 runs/<ts>-<slug>/result.json 的 input{injected,key_method,focus_ok,diff_ratio,...}
```

框架侧（M2-b 交付）：

```bash
PYTHONPATH=src python -m galnx input list
PYTHONPATH=src python -m galnx input validate examples/input-profile.kb-mouse.yaml
PYTHONPATH=src python -m pytest tests/ -q
```

## 4. 证据清单

| 级别 | 证据 | 位置 |
| --- | --- | --- |
| E2 | 标题→正文（点击） | `docs/milestones/evidence/M2a-kag3-title-before.png` 940,588 B sha256 0bce597c…；`M2a-kag3-text-after-click.png` 1,368,884 B sha256 d97646f7… |
| E2 | 正文翻页（PostMessage 键盘） | `M2a-kag3-key-before.png` 1,381,478 B sha256 a6e2ee33…；`M2a-kag3-key-after.png` 1,723,557 B sha256 ce6090b2…（下一页） |
| E1 | harness 运行 JSON/日志 | `M2a-kag3-input-run-click.json`、`M2a-kag3-input-run-click-key.json`、`M2a-kag3-citron-log-slice.txt`（43,421 B） |
| E1/E2 | M2-c 语义矩阵 4 组 | `docs/milestones/evidence/M2c-README.md` + `M2c-click-link-20261030-021105/`、`M2c-title-focus-confirm-20261030-021602/`、`M2c-body-semantics-20261030-021958/`、`M2c-x-history-20261030-022129/` |
| E4 | KAG3/krkrsdl2 源码行号证据 | `docs/milestones/M2-kag3-input.md` §2-§7、§9（Conductor.tjs L55-189、MainWindow.tjs L3929-3961/L673-684/L2833-2855/L5116-5131、MessageLayer.tjs L1991-2014、SDLApplication.cpp L134-147/L2743-2797） |
| E3 | 交付提交 | commit 1e86d36（M2-a/M2-b，31 files +3105/−15） |

## 5. 结果与结论

**结论：输入层的数据模型与模拟器注入通道都已打通；KAG3 的语义映射有源码+实测双证；组合键拦截与触摸注入留给适配器层（M4/M5）。**

关键实测数值（Citron 0237a9b88，像素 diff 由 harness 内置 differ 计算，region 默认 y=70..950）：

- **advance_text**：A(=C, VK 67) → diff **0.556076**（nonblack 0.7186→0.7211，翻页且 ▼ 出现）；A→B→A 往返三次回到同一数值（像素级复位），说明指标稳定。
- **B / ESC**：隐藏消息层 diff **0.556076**（→0.7186），再按 A 恢复 0.556076。
- **confirm_choice（[link] 点击）**：标题页点击链接 diff **0.494465**；方向键移动焦点 0.007397 / 0.016511，A 确认 diff 0.554372 进入正文。
- **鼠标 vs 键盘通道**：鼠标推进 0.556042、键盘 0.556076（同量级，两通道都有效）；**SendInput 键盘在 Citron 无效**（0.0003），必须 PostMessage(WM_KEYDOWN/WM_KEYUP)：Qt key handler 只接受真实窗口消息，且 `keyPressEvent` 在首帧前 `event->ignore()`（src/citron/bootmanager.cpp:505-560）。
- **负面发现**：X（PAD3 → showHistoryByKey）在本 DEMO 无可见变化（0.000000/0.0002）——历史层需要 [history] 标签或非 sleep 状态；**Switch 上 KAG3 键盘快捷键 F/A/B/R/S/L 与系统菜单不可达**（手柄按钮只合成 RETURN/ESCAPE/方向键，菜单被 MenuItem_stub.tjs 桩掉）→ 存档/读档/自动/回退 UI 必须由 GalNX 或 krkr-ns 提供，不能指望 KAG3 自带。

工程结论：

1. Citron 是可行的输入回归后端，但单实例（yuzu 血统）→ 必须串行时间窗；harness 已加 `citron_already_running` 预检，实验规程写入 `M2-kag3-input.md` §8.4。
2. 输入注入有**首帧门控**（--input-delay < 2500ms 丢键）与**焦点前提**（目标窗口需前台，SendInput 鼠标同理）；已在 `docs/environment/citron-harness-input.md` 记录失败码。
3. 框架的 7 语义动作与 3 上下文可覆盖 KAG3 实测语义；同键跨上下文复用（A 同时 advance_text + confirm_choice）合法，同上下文一键多语义报 button_ambiguous。

## 6. 未验证与剩余风险

1. **真机（NS1）输入**：全部实测在 Citron 模拟器；HID 手柄索引、触摸屏、摇杆轴未验证。
2. **触摸事件**：数据模型有 touch 语义但未在 Citron 注入验证（Citron 触摸设备有 min/max 映射配置，可后续测）。
3. **组合键拦截**：hotkey（L+R+PLUS）只在 manifest/profile 层定义，运行时由适配器/引擎实现，本里程碑不验证拦截本身。
4. **X 历史层未生效**：KAG3 demo 未覆盖 [history] 场景；krkr-ns/真实游戏可能不同，需 M4 再验证。
5. **多游戏切换**：NRO 内嵌单份 data.xp3，未测多游戏会话。
6. **Citron 渲染约 18-30 FPS**，截图可能抓到过渡帧 → 判定靠多次一致性与「往返同值」，不靠单帧。
7. **KAG3 存档 UI 缺失**：这是引擎适配的硬需求（不是输入层 bug），已并入 M4/M5 的适配器需求清单。

## 7. 下一步

1. M3：自包含 NSP 出包链与 Citron 引导验证（本里程碑已给出 harness 输入回归基线，M3-b 直接复用）。
2. M4/M5：第二引擎接入时把 §1 第 3 条（按键状态快照、触摸、组合键拦截）落到适配器实现；优先验证 KAG3 存档/读档 UI 的 GalNX 自建方案。
3. 真机阶段（M3-d/M6）：用 NS1 复核 Citron 上的输入结论，特别是手柄按钮索引与触摸屏。

## 8. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-30 | 初版：汇总 M2-a（输入注入）、M2-b（数据模型）、M2-c（KAG3 语义取证+实测） |
