# 011 · K2NX 退出崩溃修复（补丁 F）

- 日期：2026-10-30
- 上游：`Erige005/Kirikiroid2-NX` @ `e96b6034c292c6ccdb099823ab6a0a6b505f77f3`（tag `v1.0.1`）
- 补丁：`docs/builds/patches/k2nx-switch/F-close-exit.patch`（4,592 B，sha256 `21af948cd538ef3f3380b90228571ddedff8f88668880e0027ad0271f1828337`）
- 状态：**模拟器级 PASS（Citron nightly 0237a9b88）**；真机复验待 A5 NSP（`docs/pilot/P4-device-runbook.md`）

## 1. 症状（真机报告）

在 Switch 上通过 K2S 抽屉的电源按钮退出游戏后，画面弹出错误框并不返回 HOME：

```
Error Code: 2-0000
NX 1.0.1 (Kirikiroid2 1.3.9) 晴のちきっと菜の花びより
晴のちきっと菜の花びより
Member "SystemObj" does not exist
@line(365) checkdialog.tjs
OK
```

同一崩溃在 Citron 上可复现（`docs/builds/010` §6 E4 已记录 `Member "minimized" does not exist` 的 ESC 分支），说明它属于**引擎 teardown 路径的通用问题**，不是真机网络/文件系统差异。

## 2. 复现路径（模拟器）

1. Citron 以 `--detach` 加载 K2NX NRO/NSP，等 `title.ks` 出现（`--settle 25`）。
2. 按 X（补丁 E/F 的诊断热键）→ `GalNX_EvalTJS("MainObj.onCloseQuery(true)")`，复刻 K2S 电源键经引擎 `Close()` 到达的同一个入口。
3. 游戏弹出「ゲームを終了しますか？」确认框；用 Y（虚拟光标）+ DPAD 移光标 → A 点「はい」。
4. 未修复版本：确认后走 `OnCloseQueryCalled(true)` 的 desktop 分支 → `invalidate()` → TJS 世界按任意顺序析构 → 报 `SystemObj` / `minimized`。

## 3. 根因

两条异常都来自 **desktop 的「关闭主窗口」语义在 Switch 上不成立**：

- **路径 A（确认框 finalize）**：`OnCloseQueryCalled(true)` 在 desktop 上先 `SetVisible(false)` 再 `invalidate()` 脚本对象，让 TJS 引擎自行拆世界；但游戏自己的对话框 finalizer（`checkdialog.tjs:365`）仍要 `MainWnd.SystemObj.FileStop()`。`MainWnd` 是全局变量，会被 `BaseObject/BaseLayer/Parser/SoundObject` 等构造函数反复赋值，一旦拆解顺序把 `MainWnd` 指向已失效对象，就报 `Member "SystemObj" does not exist`。
- **路径 B（ESC 最小化）**：`BASE ADV SYSTEM` 的 `MainWindow.EscapeWork`（`MainWindow.tjs:3417`）写的是 `if (this.minimized == false) ... this.minimize()`；K2NX 的 `Window` 没有 `minimized/maximized/minimize()` 这些 Win32 遗留成员，于是 `Member "minimized" does not exist`。

两者本质相同：Switch 没有「可最小化的 OS 窗口」，也没有「关窗后还能继续跑的世界」，所以正确语义应该是 **确认关闭 = 退出应用**，而不是让 desktop 的 invalidate 路径继续跑。

## 4. 修复（补丁 F，2 文件）

### 4.1 `src/core/environ/cocos2d/MainScene.cpp`（+18/−6）

在 `OnCloseQueryCalled(bool b)` 里、`SetVisible(false)` 之后与 `Closing = false;` 之前插入 Switch 专用分支：

```cpp
#ifdef __SWITCH__
    if (TJSNativeInstance && TJSNativeInstance->IsMainWindow()) {
        GalNXLog("[close] main window close confirmed; terminating application");
        TVPExitApplication(0);
        return;
    }
#endif
```

`TVPExitApplication(0)` 的 Switch 实现（`src/core/environ/switch/SwitchUtils.cpp:304`）走 `TVPDeliverCompactEvent → K2SResetCpuBoost → RecycleProcess → exit(code)`，进程立即退出，不进入 TJS 析构。此时游戏自己的关闭处理器已经把该保存的数据存好（本作在确认框里保存 system 数据），符合「退出前已落盘」。

同文件还把 E 补丁的 X 诊断热键从探针改成 `MainObj.onCloseQuery(true)`（用于本轮复现；发布版可移除，见 §6）。

### 4.2 `src/core/visual/WindowIntf.cpp`（+57）

给 `Window` 补 Win32 兼容成员（`TJS_END_NATIVE_MEMBERS` 之前）：

- 只读属性 `minimized` / `maximized`，恒返回 0（Switch 上永不最小化/最大化）；
- `minimize()` / `maximize()` / `restore()` 均为 no-op 返回 `TJS_S_OK`。

这样即使游戏的 ESC 路径被调用（`this.minimized == false` 成立 → `this.minimize()`），也不再抛 TJS 异常。

全部新增代码带 `// [GalNX]` 注释；diff 见 `F-close-exit.patch`，A→F 全量重放结果见 `k2nx-patched-vs-v1.0.1.diff`（37,398 B，sha256 `8ee1f77a…`，9 文件 677 insertions / 20 deletions）。

## 5. 验证（Citron，exit3）

脚本 `E:/galnx-build/pilot-01/p3/save-exp/run-exit3.sh`，日志 `exit3.out.log`，产物目录 `.../save-exp/exit3/`：

流程：clean → harness `--detach --game kirikiroid2.nro --timeout 600 --settle 25 --expect-title Kirikiroid --input-steps wait:600000` → `title.ks`（loop 25）→ sleep 6 → hwnd `0x002702BC` → `cap 00-title.png` → key 86（X）→ `01-dialog.png`（确认框出现）→ key 90（Y，虚拟光标）→ `02-cursor.png` → LEFT×3 → `03-cursor-pos.png`（光标高亮「はい」）→ key 67（A 点击）→ sleep 8 → `04-after-yes.png`。

结果：

| 检查项 | 结果 |
| --- | --- |
| glog 是否走到新分支 | ✅ 末两行 `virt cursor=(408.0,270.0)` → `[close] main window close confirmed; terminating application` |
| 关闭后窗口 | ✅ 回到 Citron 游戏列表（`04-after-yes.png` 71,022 B），无错误弹窗、无崩溃 |
| k2s.txt | ✅ 无 `error` / `exception` / `SystemObj` 字样 |
| savedata | ✅ 未变（`savedata010.bmp` 45,941 B、`system.bmp` 989 B） |
| guest 进程 | ✅ 正常退出；Citron GUI 本身仍在（模拟器预期，真机对应行为=回 HOME） |

证据（已入仓 `docs/milestones/evidence/`）：

| 文件 | 大小 | sha256 |
| --- | --- | --- |
| `P4a-exit-01-dialog.png` | 1,768,685 B | `92cd9abd6b2c5b4f72e5f8e66aa41941b5d172c914d92aef68899e8d603ae6cc` |
| `P4a-exit-02-after-yes.png` | 71,022 B | `e84daad06101052e13664851aec23f63a472fdd4df056ecf008837007bfc5294` |
| `P4a-exit-glog.txt` | 789 B | `34caa6d054d478e1d3c316460ed151ec949763084ddc3be9d2d4cc82134de7cb` |
| `P4a-exit-k2s.txt` | 7,632 B | `d40177481537364cb35b3e31dc180c35853b39f9d3375c43333612458346c4c7` |

工作区另有 `00-title.png`（sha `ba248372…`）、`02-cursor.png`（`0a6c9ba5…`）、`03-cursor-pos.png`（`937ad3c0…`），因体积/重复未入仓。

构建产物（r3，patch A→F）：

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| ELF | 113,892,064 B | `02b70f18707d2db197e880312284ade5da1f7f8b13a1f7e35385ad4d69acd2ef` |
| NRO | 42,363,510 B | `41b7a74552dd424a3143f298930be874be942f18d5f61f685cf69c5f619e5abe` |

## 6. 未覆盖 / 限制

- **ESC 路径未端到端复现**：标题画面按 B（`VK_ESCAPE`）时游戏没有把 ESC 路由到 `MainWindow.EscapeWork`，三张截图逐字节同尺寸、glog 只有 `[pad] key=1005/key=1004`。因此 `minimized` 修复目前只有**源码级证据**（属性存在 + 语义正确），没有触发时的运行时证据；它不阻塞本次交付（用户报的是退出崩溃）。
- **X 诊断热键仍在补丁里**：`F-close-exit.patch` 把 X 改成 `MainObj.onCloseQuery(true)` 以便复现关闭链。发布给玩家的版本建议去掉该分支（不影响正常游玩，但它是一个隐藏的诊断入口）。
- **真机复验**：`TVPExitApplication` 在真机的实际表现（回 HOME、无错误码）需 A5 NSP 上机确认；模拟器只能证明「不再走 invalidate teardown」。
- 本作在确认框里是否持久化「最后进度」取决于游戏脚本本身，补丁不改变游戏存档行为。

## 7. 复现命令

```bash
# 1. 构建（MSYS2 是唯一可用的 devkitPro 调用姿势）
cd /e/galnx-build/pilot-01/k2nx-ws
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc \
  '/e/galnx-build/pilot-01/k2nx-ws/build-scripts/rerun_ninja.sh'
# 2. exit3 验收
bash /e/galnx-build/pilot-01/p3/save-exp/run-exit3.sh
```

补丁应用顺序与幂等脚本见 `docs/builds/patches/k2nx-switch/README.md`（C→D→E→F，D/E/F 为增量 diff）。

## 8. 关联

- `docs/builds/010-k2nx-controller-saveload.md`：补丁 D/E（虚拟光标 + 存档/读档 UI）
- `docs/pilot/saveload-acceptance.md`：S7 退出验收 + §9 A5 回归
- `docs/pilot/P4-device-runbook.md`：真机安装/复验步骤
- `examples/engines/kirikiroid2-nx.yaml`：适配器描述（patches=A–F 六项、artifact=A5）

## 9. A5 NSP 冒烟（Citron，含 patch F 端到端）

A5 自包含 NSP（manifest version 1.0.4）构建完成后，用同一套 Citron harness 做「读档 + 退出」回归，确认补丁 F 在**打包形态**（exeFS 打进 NSP）下同样生效，而不只是 NRO 形态。

- 产物：`Kirikiroid2-NX-A5-010047410000A000.nsp` 2,906,138,328 B sha256 `f179f0a20b9ede113231a7bfd0046180a8b90d5408745fbcc73520d73ec3b188`；`galnx package nsp verify` 19 checks / 18 ok / 1 warn（未签名预期）。
- 运行目录：`GalNX/workspaces/citron-harness/runs/20261030-142454-Kirikiroid2-NX-A5-010047410000A000`；脚本 `/e/galnx-build/pilot-01/p3/save-exp/run-a5smoke.sh`（`--detach --expect-title Haruno`）。
- 窗口标题：`citron Nightly | 0237a9b88 | Haruno (64-bit) | 1.0.4 | NVIDIA` —— 打包版本号与 manifest 一致。

| 步骤 | 结果 | 证据 |
| --- | --- | --- |
| 启动 A5 NSP，等 title.ks | 标题画面正常（k2s 记 `Scenario loaded : title.ks`） | `P4b-a5-00-title.png`（2,378,108 B `a340da1d…`） |
| R（patch E 热键）开原生 LOAD UI | LOAD 界面打开，槽 01 01 显示 12:23 存档缩略图 + 标题 + 日期 | `P4b-a5-01-loadui.png`（1,598,534 B `303147d5…`） |
| 虚拟光标移到槽 01 01 → A | 读档成功，进入正文（k2s 记 `Scenario loaded : @0000A_Z01.ks`） | `P4b-a5-04-loaded.png`（935,381 B `32e0b2fa…`） |
| C 推进两次 | 文本正常前进（无异常） | a5-05/06-adv*.png（工作区保留） |
| X → `MainObj.onCloseQuery(true)` | 弹出「ゲームを終了しますか？」确认框 | `P4b-a5-07-close-dialog.png`（710,169 B `a721a269…`） |
| Y+LEFT×3+A 确认「はい」 | glog 末行 `[close] main window close confirmed; terminating application`；guest 干净退出 | `P4b-a5-glog.txt`（5,663 B `7ace5803…`） |
| 退出后 | Citron 回到游戏列表，无错误框；k2s 0 条 error/exception | `P4b-a5-09-after-yes.png`（71,022 B `e84daad0…`，与 A4 exit3 的同一张画面**逐字节相同**） |

补充观察：读档动作后游戏在 `sdmc:/kirikiri/haruno/savedata/` 新写了 `savedata400.bmp`（46,065 B，14:26），原有 `savedata010.bmp`（45,941 B）/ `system.bmp`（989 B）未变；疑为游戏自身记录的「最近使用槽」或自动快照，语义待后续确认，不影响本次判定。`P4b-a5-k2s.txt` 9,389 B sha256 `4354179b…`。

结论：**A5 在模拟器侧结构校验 + 读档 + 退出回归全 PASS**；真机复验（K2S 抽屉电源键）仍需用户设备。
