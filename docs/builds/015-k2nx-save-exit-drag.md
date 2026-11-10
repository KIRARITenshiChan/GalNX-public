# 015 — K2NX 退出存档与按住鼠标（patch I）：设置/存档持久化、继续游戏、ZR 拖拽

- 条目：GALNX-BUILD-015
- 日期：2026-10-30
- 状态：**模拟器级 PASS**（Citron i6/i8 + A10 首启冒烟 4 run）｜**A10 中文 NSP 已构建 + 结构校验 19 checks**（DBI FTP 真机验收待用户）
- 上游：`Erige005/Kirikiroid2-NX` pin `e96b6034c292c6ccdb099823ab6a0a6b505f77f3`（= tag v1.0.1）
- 关联：[013 patch G](013-k2nx-controller-input-v2.md)、[014 patch H](014-k2nx-input-tweaks.md)、[012 CN 内容](012-k2nx-cn-content.md)、[P4 runbook §11](../pilot/P4-device-runbook.md)

## 1. 背景（真机反馈 m13042）

A9（1.0.8，patch H）真机测试后用户提出四点：

1. **设置不持久**：在「游戏设置」里改的项，退出再进又回到默认/旧值。
2. **存档记录缺信息**：SAVE/LOAD 面板里的槽位没有时间与文本摘要，NEW 徽章总是挂在槽 1；设置项也锁在槽 1 的状态。
3. **「继续游戏」提示数据可疑**：读档前弹出「強制終了の為このデータが確実に使用可能か保証できません」。
4. **ZR 只能点、不能拖**：ZR 应该表现为「按住左键」，与右摇杆配合完成拖动（滚动条/滑块），当时只发了一次单击。

## 2. 根因

### 2.1 设置/存档/继续数据（问题 1–3，同一根因）

本作（BASE ADV SYSTEM）的**系统级持久化只发生在 `MainWindow.tjs` 的 `finalize()`**：

```tjs
// KR/sys_source/MainWindow.tjs:542（全树唯一 SystemSave 调用点）
function finalize(){
    ...
    SystemSave();   // 写 savedata/system.bmp（设置 + ContinueSave 元数据 + 缩略图索引）
    TraceSave();    // 写 savedata/trace.bmp（是否干净退出）
}
```

SLOT 存档（`savedata%03d.bmp`）本身在 `MainObj.SaveAction()` 时就落盘，但 SAVE/LOAD 面板显示的**时间/文本/缩略图/Continue 行**全部来自 `system.bmp`。

patch F（[011](011-k2nx-exit-crash-fix.md)）与 patch G（[013](013-k2nx-controller-input-v2.md)）为了修复 `SystemObj` 退出崩溃，把主窗口关闭改成**立即 `TVPExitApplication(0)`**——进程直接消失，TJS 的 `finalize()` 永远不会执行：

- `system.bmp` 从未更新 → 设置回退、SAVE/LOAD 面板无时间/文本、Continue 行不存在；
- `trace.bmp` 一直停在上一次干净退出的旧状态（或根本缺失）→ 游戏判定「前回不正常结束」，弹「强制终了…」提示。

即：退出崩溃修好了，但把**退出前的保存动作**一起跳过了。

### 2.2 ZR 不是按住（问题 4）

patch G 的 ZR/ZL 在 `onPadKeyDown` 里对 `TVPWindowLayer::OnMouseClick()` 只发一次点击，没有 down/up 状态，也没有配合 `onMouseMove`；K2 的滑块/滚动条需要 `onMouseDown` + 移动 + `onMouseUp` 三个事件序列。

### 2.3 标题/设置画面的轴事件被提前丢弃（顺带发现）

`TVPWindowLayer::onAxisEvent` 开头有：

```cpp
if (!_currentWindowLayer || !_currentWindowLayer->PrimaryLayerArea) return;
```

本作全篇没有 `PrimaryLayerArea`（ADV 引擎不用它做输入层），而 patch D/G 的右摇杆光标、左摇杆滚轮代码写在 `#ifdef __SWITCH__` 块里、位于这个 `return` 之后 → **标题画面、设置画面、SAVE/LOAD 画面上的摇杆输入全部被吞掉**（正文画面之所以能用，是因为那时 `PrimaryLayerArea` 被临时设置）。

## 3. patch I 的改动（三组）

补丁：`docs/builds/patches/k2nx-switch/I-save-exit-mouse.patch`，7,372 B，sha256 `3cbcad8dda05defb86a3b34c17d2acdbfc6dc713b277670ab8d0b51987501fc6`，**1 文件 +56/−14**（`src/core/environ/cocos2d/MainScene.cpp`，相对 patch H 之后状态）。

### 3.1 退出前显式保存 + 延迟退出（问题 1–3）

新增：

```cpp
static void GalNX_SaveGameDataOnExit() {
    // 用 TVPExecuteExpression 调本作自己的 TJS 收尾 API，等价于 finalize() 里那两句
    GalNXLog("[close] persisted system data (TraceSave + SystemSave)");
}
```

插入两条关闭路径（`TVPWindowLayer::CloseWork()` 与 `OnCloseQueryCalled()` 的主窗口分支）：

1. `setVisible(false)`（先让画面消隐，避免退出瞬间看到桌面);
2. `GalNX_SaveGameDataOnExit()` → `MainObj.TraceSave(); SystemSave();`;
3. `scheduleOnce(..., 1.0f, "galnx-exit")` → 1 秒后 `TVPExitApplication(0)`。

日志：

```text
[close] persisted system data (TraceSave + SystemSave)
[close] main window close confirmed; terminating application after save
```

为什么延迟 1 秒：`SystemSave()`/`TraceSave()` 是同步写盘（system.bmp/trace.bmp 几十 KB 级，1 秒足够）；延迟也保证 TJS 的写盘调用在进程退出前完成，同时保留 patch F/G 的「不让 TJS 乱序 teardown」的性质。

### 3.2 ZR/ZL 改为按住鼠标（问题 4）

`onPadKeyDown`（ZR = 右肩键 1017 / ZL = 1018）：

- 先把虚拟光标位置通过 `onMouseMove(x, y)` 同步给 TJS（K2 的 `MapRes` 依赖移动更新，只发点击不够）；
- 再 `onMouseDown(VK_LBUTTON / VK_RBUTTON, ...)`，日志 `[pad] mouse down left|right`；
- `onPadKeyUp` 对应 `onMouseUp(...)`，日志 `[pad] mouse up left|right`；
- 按下时 `stopAllActions() + setOpacity(255) + _refadeMouseCursor()`：patch D 起光标会在 1 秒后淡出，而 `isVisible()` 仍是 true，导致「按 ZR 光标不回来」；现在每次按下强制重显并重新起淡出动画。

### 3.3 轴事件早退后移（顺带修复）

把 `if (!_currentWindowLayer || !_currentWindowLayer->PrimaryLayerArea) return;` 从 `onAxisEvent` 开头移到 `#ifdef __SWITCH__` 块**之后**，于是：

- 标题/设置/SAVE/LOAD 画面：右摇杆移光标、左摇杆滚轮可用；
- 正文画面行为不变（原有逻辑仍先按 `PrimaryLayerArea` 分流）。

## 4. 验证（Citron，NRO 形态）

### 4.1 诊断性验证（i6）

为确认根因，先加了一个**临时**诊断热键 LB：直接调 `MainObj.SaveAction(10) + SystemSave()`，构建后跑一遍再重启：

| 步 | 观察 | 结果 |
| --- | --- | --- |
| 1 | glog `[tjs] dbgsave -> ok`、`[close] persisted system data (TraceSave + SystemSave)` | 收尾 API 可被引擎调用 |
| 2 | 退出后 `savedata010.bmp` 新建、`system.bmp` 965 → 984 B | SystemSave 真写盘 |
| 3 | 重启 → LOAD 面板槽 01 01：**NEW 徽章 + 缩略图 + 文本「我拼命地伸出了手。」+ 2026/10/30 23:26** | 问题 1–3 根因闭合 |

诊断代码已移除，终版源码与之无关。证据：`P8-i-loadpanel.png`（= i6-11-load2.png，sha256 `c79eaa17…`）。

### 4.2 终版验收（i8，双 run）

i7 单 run 设计失败：**虚拟光标显示时 `clickpost` 点击不再命中**（光标有自己的命中逻辑，覆盖绝对坐标），退出确认点不中「是」。这是测试 harness 限制，不是产品缺陷；改为 i8 双 run 分离验证：

| run | 注入 | 观察 | 结论 |
| --- | --- | --- | --- |
| A（纯退出存档） | title → RIGHT+A 进正文 → MINUS → 确认「是」 | `[tjs] exit -> ok`；glog 末尾 `[close] persisted system data (TraceSave + SystemSave)` + `[close] main window close confirmed; terminating application after save`；退出后 `savedata400.bmp` sha 更新为新值、`system.bmp` 988 B sha `b803401b…`（旧 984 B `915a7148…`）| 退出确实写了 system/trace |
| B（输入语义） | title 按 ZR → 右摇杆移动 → 左摇杆上推 → 正文 ZR 按住+右摇杆拖 | 光标出现（截图字节数随移动变化 2,545,534 → 2,545,741 / 2,544,847）；glog `ZR cursor=0x0 → mouse down left → mouse up left`；`[pad] wheel 120` 打开 backlog；B 关闭 backlog `[tjs] back ->`；ZR 按住+拖动截图 902,750 / 904,941 B | 按住语义 + 光标 + 滚轮全部生效，0 exception |

证据：`P8-i-*.png/txt`（13 文件，`P8-i.sha256`）。

## 5. A10 中文 NSP（1.0.9）

- manifest：`examples/pilot01-haruno-cn5.yaml`，5,109 B，sha256 `4b7529b5e6631e99139c488586acc748ee47c34ab92e67893dedb7c62d45c6eb`
- version 1.0.9 / version_code 65545 / title_id `010047410000A000` / title `Haruno CN`
- romfs 与 A8/A9 相同（`E:/galnx-build/pilot-01/p6/romfs-a8`，109 文件 / 2,843,019,052 B；payload `pilot01-cn3`）——本版只改 exefs
- 构建脚本 `E:/galnx-build/pilot-01/p8/build_a10.sh`，build duration 186.171 s，ROMFS_OFFSET_ALIGN=0x10000
- 产物：`E:/galnx-build/pilot-01/p8/out/Kirikiroid2-NX-A10-CN-010047410000A000.nsp`
  - **2,870,911,704 B，sha256 `0efc23f66f57a016c15ea3944cdb8ce5b396f03f6bef3b8f5ddc1794d03186f2`**
  - PROVENANCE：14,100 B（同名 `.PROVENANCE.json`）
- 结构校验（独立 `galnx package nsp verify`）：`ok=true`，**19 checks = 18 ok + 1 warn**（唯一 warn = 未签名 homebrew 的 `NCA signature FAIL`，预期）；3 个 NCA 的 ProgID 全部 `0x010047410000a000`
- 构建/校验日志：`p8/a10-build.json`、`p8/a10-verify.json`

## 6. 首启冒烟（NSP 形态，A10）

脚本 `E:/galnx-build/pilot-01/p8/run-a10smoke.sh`（RUN A/B）、`run-a10smoke_c.sh`（RUN C）、`run-a10smoke_d.sh`（RUN D）。RUN A 先清空 `sdmc:/kirikiri/haruno` 与 `.galnx_extracted` marker，强制首启解包。

| run | 内容 | 关键观察 | 结果 |
| --- | --- | --- | --- |
| A | 强制首启 → 标题 → RIGHT+A 进正文 → MINUS 退出 | 窗口 `Haruno CN (64-bit) | 1.0.9`；中文退出确认 → 「是」；glog `[tjs] exit -> ok` + `[close] persisted system data (TraceSave + SystemSave)` + `[close] main window close confirmed; terminating application after save`；退出后 `savedata400.bmp` 45,617 B sha `b7c5220a…`、`system.bmp` 951 B sha `68f4e494…`、`trace.bmp` 142 B sha `9b658990…` | PASS，0 exception |
| B | 重启（marker 已存在）→ 标题 → Y 打开 LOAD UI → MINUS 退出 | k2s `[GALNX] payload pilot01-cn3 already extracted, starting game`；LOAD 面板全 NO DATA（本 run 无槽位存档，预期）；退出同样 persisted + clean exit | PASS，0 exception |
| C | 重启 → RIGHT×4+A（落到「结束游戏吗？」）→ 退出 | 每次退出都重写 `system.bmp`（965 B sha `20b371ea…`）与 `trace.bmp`（145 B sha `99cbc147…`） | PASS，0 exception |
| D | 重启 → Y 打开 LOAD UI → 点「继续」 | Continue 行展开：**缩略图 + 文本「我拼命地伸出了手。」+ 时间 2026/10/30 23:46:5** | PASS：patch I 的退出存档跨进程持久并渲染 |

RUN D 的决定性证据截图：`P8a-a10-continue-runD.png`（sha256 `de176f0d…`）；A 的 `P8a-a10-after-yes.png` 与 i8-A5 同为 71,022 B（进程退出后的 Citron 列表）。全部证据与哈希见 `docs/milestones/evidence/P8a-a10.sha256`。

## 7. 全量补丁栈与构建产物

| 项 | 值 |
| --- | --- |
| 补丁 I | 7,372 B，sha256 `3cbcad8d…`，1 文件 +56/−14 |
| 补丁校验 | apply 到 prepatch（patch H 状态 `100,544 B / c580b4c3…`）后 `MainScene.cpp` 102,771 B sha256 `eb25880012c007d96a2fdce5472477f6c2083ea8b7ac4a48b485e7d8e23e0c57` = 构建树（ROUNDTRIP_MATCH，CRLF 归一后逐字节一致） |
| 全量 diff | `k2nx-patched-vs-v1.0.1.diff` 重生：**52,375 B，sha256 `42436d3ef845cd1e924c4d0b423291950e88e5202c294768a3a36ea09bda9219`，9 文件 840 insertions / 57 deletions（A→I）** |
| ELF | 113,893,552 B，sha256 `ad5c0bfebbfcd351f9b288a2b381794e65f95f034a69cf365fb2703f4df332bb` |
| NRO | 42,363,510 B，sha256 `b021b3522660521d9917081f8a860d11043c7fe251557d5a48005fc60ec4a89e` |
| 构建日志 | `E:/galnx-build/pilot-01/p8/build/build-i*.out`（NINJA_RC=0，0 error/Failed） |

构建命令与 patch G 相同：

```bash
cd /e/galnx-build/pilot-01/k2nx-ws && env MSYSTEM=MSYS CHERE_INVOKING=1 \
  /d/devkitPro/msys2/usr/bin/bash.exe -lc '/e/galnx-build/pilot-01/k2nx-ws/build-scripts/rerun_ninja.sh'
```

## 8. 限制

- **L1 真机未验证**：A10 已通过 DBI FTP 上传并在真机安装，但四个问题的真机复验由用户完成（见 runbook §11）。
- **L2 Citron 虚拟光标显示时 `clickpost` 失效**：光标有独立命中逻辑，绝对坐标点击不生效（i7 因此失败）。这是自动化 harness 限制；真机由 ZR 自身完成点击。验收用 i8 双 run 分离覆盖。
- **L3 RUN D 只证明 UI 持久化**：Continue 行正确渲染缩略图/文本/时间，但没有再点一次真正载入该 Continue 的存档；「继续游戏」的读档链路在 i6/i8（NRO）已验证（DataLoadAction 有效）。
- **L4 收尾保存是 best-effort**：若 TJS 侧 `SystemSave` 抛异常，进程仍会在 1 秒后退出（只是 glog 缺少 `[close] persisted …` 行）。可在真机上通过「退出后重进设置是否保留」判断。
- **L5 每次退出都会重写 system/trace**：属预期（正常 PC 版行为），但意味着退出会比之前多花 ~0.1–1 s。
- **L6 1 秒延迟退出的画面行为**：退出瞬间先隐藏画面再退出，Citron 截图为空/列表属预期。

## 9. 复现

```bash
# 1) patch I（相对 patch H 之后状态）
cd /path/to/Kirikiroid2-NX && git apply -p1 --recount --whitespace=nowarn I-save-exit-mouse.patch
# 2) 构建
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '<repo>/build-scripts/rerun_ninja.sh'
# 3) 打包 A10（keyset 只显式传入，不入库）
PYTHONPATH=src python -m galnx package nsp --manifest examples/pilot01-haruno-cn5.yaml \
  --elf <...>/kirikiroid2.elf --romfs-dir <romfs-a8> --keyset <prod.keys> --out <A10.nsp> \
  --build --nstool <nstool> --hacbrewpack <hacbrewpack> --elf2nso <elf2nso> \
  --npdmtool <npdmtool> --nacptool <nacptool>
# 4) Citron 冒烟（先清 payload + marker 强制首启）
bash E:/galnx-build/pilot-01/p8/run-a10smoke.sh
```

## 10. 关联

- [014 — patch H 输入细节](014-k2nx-input-tweaks.md)（R=Ctrl、滚轮方向、封面图标）
- [013 — patch G 手柄映射 v2](013-k2nx-controller-input-v2.md)（B=back、X=自动、Y/+ = 读/存档、-=退出、ZR/ZL、右摇杆光标、左摇杆滚轮）
- [011 — patch F 退出崩溃修复](011-k2nx-exit-crash-fix.md)（本补丁的前置：`SystemObj` 崩溃）
- [P4 真机 runbook §11](../pilot/P4-device-runbook.md)
- 补丁总表：`docs/builds/patches/k2nx-switch/README.md`
