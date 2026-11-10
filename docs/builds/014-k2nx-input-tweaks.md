# 014 — K2NX 输入细节修正（patch H）：R 肩键持续 Ctrl、左摇杆滚轮方向、封面图标

- 条目：GALNX-BUILD-014
- 日期：2026-10-30
- 状态：**模拟器级 PASS**（Citron，NRO run h1）｜**A9 中文 NSP 已构建 + 结构校验 19 checks + 首启冒烟 PASS**（待真机）
- 上游：`Erige005/Kirikiroid2-NX` pin `e96b6034c292c6ccdb099823ab6a0a6b505f77f3`（= tag v1.0.1）
- 关联：[013 patch G](013-k2nx-controller-input-v2.md)、[012 CN 内容](012-k2nx-cn-content.md)、[P4 runbook §11](../pilot/P4-device-runbook.md)

## 1. 背景（真机反馈 m12633）

A8（1.0.7，patch G）真机初测通过（开始游戏/PLUS 菜单正常、退出不崩）后，用户提出三点：

1. **R 肩键 = Ctrl，按住持续触发**（本作 Ctrl = 快进 skip，长按跳过已读/自动推进）。
2. **左摇杆上下方向相反**：摇杆向上应该触发「上滚轮」= 打开 backlog（LOG）；向下应该触发「下滚轮」= 下一句。当时的实现正好反了。
3. **用自制封面图做封面**：用户已 p 好一张图放在 Workspace。

## 2. R 肩键 = 持续 Ctrl

### 2.1 游戏侧语义（BASE ADV SYSTEM）

`KR/sys_source/MainWindow.tjs:2121` 的 `SkipCheck()`：

```tjs
if((SkipFlag) || ((WndActiveFlag == true) && System.getKeyState(VK_CONTROL))){
    ...
    return true;
}
```

`TitleObject.tjs:1145` 另外显式忽略 `VK_CONTROL`（标题画面不触发 skip）。

关键点：游戏**轮询键状态**（`System.getKeyState`），不依赖 keydown/keyup 事件序列，也不消费 `VK_PAD*`。所以只要让 `getKeyState(VK_CONTROL)` 在按住期间返回非 0 即可，不需要往 TJS 事件队列塞任何东西。

### 2.2 引擎实现（MainScene.cpp）

- `TVPGetKeyMouseAsyncState`（`MainScene.cpp:114`）：
  `tjs_uint8 code = _scancode[keycode]; _scancode[keycode] &= 1; return code & (getcurrent ? 1 : 0x10);`
- `SystemImpl.cpp:888 getKeyState` → `TVPGetAsyncKeyState` → 非 PAD 走上面这条。
- 按下（`onPadKeyDown`，R = `BUTTON_RIGHT_SHOULDER`，cocos keyCode 1016）：
  `_scancode[VK_CONTROL] = 0x11;  _currentWindowLayer->InternalKeyDown(VK_CONTROL, TVPGetCurrentShiftKeyState());  GalNXLog("[pad] ctrl down");`
- 抬起（`onPadKeyUp`）：
  `bool was = (_scancode[VK_CONTROL] & 1) != 0;  _scancode[VK_CONTROL] &= 0x10;  if (was) _currentWindowLayer->OnKeyUp(VK_CONTROL, shift);  GalNXLog("[pad] ctrl up");`
- 位含义：bit0 = 当前按下（`getKeyState(..., false)` 的返回值），0x10 = 「曾经按下」标记，供 `OnKeyUp` / 既有 shift 判定复用；与引擎自己的触摸/鼠标注入写法一致（`MainScene.cpp:560-690`、`:2772` 的 `if (_scancode[VK_CONTROL] & 1) f |= ssCtrl;`）。

### 2.3 与 patch G 映射表的关系

R 在 patch E 之后只当过诊断热键（已移除），patch G 的映射表里没有它 → **R 现在专用于 Ctrl**，与 A/B/X/Y/PLUS/MINUS/ZL/ZR 不冲突。按住期间每帧 `SkipCheck()` 都为真，松开立刻停（不需要再按一次）。

## 3. 左摇杆滚轮方向

- 旧（patch G）：`const int delta = v < 0 ? -120 : 120;` —— v<0 = 摇杆上推 → -120 → `MessObject.MouseWheelAction` 里 delta<0 = `GetNextTextWork()`（下一句）。
- 新（patch H）：`const int delta = v < 0 ? 120 : -120;`
  - 上推 → +120 → `MouseWheelAction` 的 delta>0 分支 = `MapReg = TempReg = 4; ButtonAction(4)` = 打开 LOG（backlog）。
  - 下拉 → -120 → 下一句。
- 其余逻辑不变：`|v| < 0.25` 回中复位、`|v| > 0.6` 且 ready 时发一次，经 `TVPWindowLayer::GalNX_SendWheel` → `TJSNativeInstance->OnMouseWheel(shift, delta, _LastMouseX, _LastMouseY)`。一次推杆只滚一格，不会连续滚。

## 4. 封面图标

> 范围说明：本封面**只属于《晴霁之后定是菜花盛开的好天气》这一款游戏**，随本作 NSP 作为 HOME 图标并在文档展示；GalNX 框架本身没有统一项目封面，后续每款移植游戏各自制图。

### 4.1 源图与裁剪

用户 p 图：`E:/Othergames/Nintendo Switch/Workspace/1.png`，2,028,803 B，sha256 `668e116979b697a6e9fe499aeb0b24b0ca333c337e24ba63de0f2a22872b17da`，1242×1100 RGB。

NSP 的 control icon 固定 256×256（JPEG）；从 1100 高出发需要 1100×1100 区域再缩放 → 只能在水平方向裁剪。三候选（`E:/galnx-build/pilot-01/p7/make_icon.py` → `icons/`）：

| 候选 | 裁剪起点 | 结果 | 结论 |
| --- | --- | --- | --- |
| A-center | x0=71 | 标题右侧「菜の花びより」被切 | 弃 |
| **B-right** | **x0=142** | **标题完整 + 五名角色完整** | **采用** |
| C-fit | 整图 + 模糊填充 | 上下/左右留边明显 | 弃 |

### 4.2 产物

| 文件 | 内容 | 用途 |
| --- | --- | --- |
| `examples/pilot01/icon-cover.jpg` | 256×256 JPEG，32,607 B，sha256 `fb896d18615317df3db92dc78968206f24be86f52638283d15aec9e4ca975adf` | NSP control icon（`switch.icon` / `package.icon`） |
| `docs/assets/pilot01-cover.png` | 512×512 PNG，470,665 B，sha256 `561561b10a169d74281027d1e2d14c24daec0b7d5794d673c3bd43b2d97257f4` | README / 文档封面展示 |

`examples/pilot01-haruno-cn4.yaml`（A9 manifest）已把两处 icon 指向 `pilot01/icon-cover.jpg`；`galnx package nsp` 在 metadata 阶段校验 256×256 + JPEG magic，再写进 control NCA。

> 说明：HOME 菜单图标只在真机可见；Citron 只用于验证包结构与游戏本身能跑，图标正确性以 `nstool` 读取控制 NCA 的结果为准。

## 5. patch H 与构建产物

| 项 | 值 |
| --- | --- |
| 补丁 | `docs/builds/patches/k2nx-switch/H-input-tweaks.patch`，2,390 B，sha256 `b28b77bd4d6abbb51d0e50644a5f88def4cab86d0f3361054b5149315d676296`，1 文件 +20/−1（相对 patch G 之后状态） |
| 补丁校验 | apply 到 prepatch 副本后 `MainScene.cpp` sha256 `c580b4c36be2e0cab5758bfac95f6d878ea82421eb9e873ee1bf08f0ee985331` = 构建树（ROUNDTRIP_MATCH） |
| 改后源码 | `MainScene.cpp` 100,544 B（patch G 后 99,621 B） |
| 全量 diff | `k2nx-patched-vs-v1.0.1.diff` 重生：49,817 B，sha256 `5e2726ace4336a10395b39c06df089e9ed24f2314b3af0af602feaf40355a11c`，9 文件 797 insertions / 56 deletions（A→H） |
| ELF | 113,892,216 B，sha256 `3561b5d8459decfc60c3d8382f2c0927a7ffb7f285ff074703fd4497cc477a4f` |
| NRO | 42,363,510 B，sha256 `e9257fd1e4401edcea14c67937c2b078d0baaddb5498dc707f1a25ce432cbec4` |
| 构建日志 | `E:/galnx-build/pilot-01/p7/build-h1.out`（NINJA_RC=0，0 error） |

构建命令与 patch G 相同：

```bash
cd /e/galnx-build/pilot-01/k2nx-ws && env MSYSTEM=MSYS CHERE_INVOKING=1 \
  /d/devkitPro/msys2/usr/bin/bash.exe -lc '/e/galnx-build/pilot-01/k2nx-ws/build-scripts/rerun_ninja.sh'
```

## 6. Citron 验证（NRO 形态，run h1）

脚本 `E:/galnx-build/pilot-01/p7/run-h1.sh`：部署 CN 四包（data/scenario/image00/movie）+ keymap v2 → Citron `--detach` 启动 K2NX NRO → 标题 → D-Pad RIGHT + A 进入 `start.ks` → 轮回 Z01 正文。

| 步 | 注入 | 期望 | 实测 | 证据 |
| --- | --- | --- | --- | --- |
| 1 | W 按住 1.2 s（= 左摇杆上推） | 打开 BackLog | **BackLog 面板出现**（标题 Prologue + 历史行），`[pad] wheel 120` | `P7-h-wheelup-backlog.png` |
| 2 | B | 关闭 BackLog | 回正文，`[tjs] back ->` | `P7-h-logclosed`（未入库，见 workspaces） |
| 3 | S 按住 1.2 s（= 左摇杆下拉） | 下一句 | 文本前进，`[pad] wheel -120` | `P7-h-wheeldown-next.png` |
| 4 | R 按住 4 s | 持续 skip（跨脚本） | 从 `@0000A_Z01.ks` 跳到 `@0000A_Z02.ks`（医院场景），`[pad] ctrl down` / `[pad] ctrl up` 各一次 | `P7-h-afterskip.png` |
| 5 | A（skip 之后） | 仍可正常推进（不冻结） | 新一句出现，`[pad] key=1004` | `P7-h-after-a.png` |

日志切片：`P7-h-glog.txt`（418 B）、`P7-h-k2s.txt`（9,715 B，0 条 `exception`）。完整哈希清单见 `docs/milestones/evidence/P7-h.sha256`。

## 7. A9 中文 NSP（1.0.8）

- manifest：`examples/pilot01-haruno-cn4.yaml`（game.version 1.0.8 / version_code 65544 / title_id `010047410000A000` / title `Haruno CN`）
- romfs 与 A8 相同（`E:/galnx-build/pilot-01/p6/romfs-a8`，109 文件；payload `pilot01-cn3`，23 文件）——本版只改 exefs 与 control icon
- 构建脚本：`E:/galnx-build/pilot-01/p7/a9-build.sh`
- 产物：`E:/galnx-build/pilot-01/p7/out/Kirikiroid2-NX-A9-CN-010047410000A000.nsp`
  - 2,870,911,192 B，sha256 `ee0603b45cb6d9b7223c224c4d118877a1ea3baa3174536ec5df2765ba4a39c3`
  - PROVENANCE：14,064 B（同名 `.PROVENANCE.json`）
- 结构校验：`galnx package nsp verify` → `ok=true`，19 checks = 18 ok + 1 warn（唯一 warn = 未签名 homebrew 的 `Signature: FAIL`，预期）
- Citron 首启冒烟（NSP 形态）：见 §8
- **DBI FTP 上传（真机安装）**：2026-10-30 22:17–22:25，`UPLOAD_DONE Kirikiroid2-NX-A9-CN-010047410000A000.nsp 2870911192 in 469.5 s`（≈5.85 MiB/s；脚本 `E:/galnx-build/pilot-01/p7/ftp_upload_a9.py`，日志 `ftp_a9.out.log`）。DBI 在上传完成后自动安装，A9 覆盖同一 TitleID 的 A8；真机验收清单见 `docs/pilot/P4-device-runbook.md` §11。

## 8. 首启冒烟（NSP 形态，A9）

脚本 `E:/galnx-build/pilot-01/p7/run-a9smoke.sh`：清空 `sdmc:/kirikiri/haruno` 与 `.galnx_extracted` marker，强制首启解包。

| 步 | 观察 | 结果 |
| --- | --- | --- |
| 1 | `[GALNX] free space check ok: 8855 MiB free for a 2704 MiB payload` → `first boot: copying 23 payload file(s)` → `payload copy finished: 23 copied, 0 kept, 0 failed, 2704 MiB total` | 首启解包 PASS |
| 2 | 窗口标题含 `Haruno CN (64-bit)` 与 `1.0.8`；`Scenario loaded : startup.soc → userMacro.ks → eyecatch.ks → logo.ks → title.ks (22:05:26)` | 版本与内容正确 |
| 3 | D-Pad RIGHT + A → `start.ks (22:05:45)` → `@0000A_Z01.ks (22:05:49)` | 中文标题菜单 + 正文可进 |
| 4 | R 按住 2 s（= Ctrl）→ `[pad] ctrl down` / `[pad] ctrl up`，剧本跳到 `@0000A_Z02.ks (22:06:06)` | R=Ctrl 快进跨章 |
| 5 | 左摇杆上推（W 按住 1.2 s）→ `[pad] wheel 120`，截图 BackLog 面板（Prologue + 中文历史行） | 上滚轮 = backlog |
| 6 | B → `[tjs] back ->` 关闭 BackLog，回正文 | back 语义正常 |
| 7 | MINUS → `[pad] key=1022` + `[tjs] exit -> ok` → 「结束游戏吗？是/否」→ 点击「是」→ `[close] main window close confirmed; terminating application` | 退出干净，无 2-0000 |
| 8 | 退出后截图 = Citron 游戏列表（71,022 B）；`grep -c exception k2s_a9.txt` = 0 | PASS |

证据（`docs/milestones/evidence/`，哈希清单 `P7a-a9.sha256`）：`P7a-a9-titlemenu.png`、`P7a-a9-afterskip.png`、`P7a-a9-backlog.png`、`P7a-a9-exitdlg.png`、`P7a-a9-after-yes.png`、`P7a-a9-glog.txt`、`P7a-a9-k2s.txt`。


## 9. 限制

- **L1 真机未验证**：R=Ctrl、滚轮方向、封面图标都只在 Citron 上验证；真机手感（skip 速度、滚轮单步节奏）需用户实测。
- **L2 R 与游戏内自己的 skip 状态叠加**：游戏里 LOG 面板/菜单打开时按住 R，`SkipCheck()` 也返回真；如果出现异常跳过，优先松开 R 或等面板关闭（与键盘 Ctrl 行为一致，不是新引入问题）。
- **L3 图标只在 HOME 菜单可见**：Citron 不显示；真机安装后需确认 HOME 图标为封面图（同 TitleID 会覆盖 A5–A8）。
- **L4 左摇杆仍只做滚轮**：不做上下左右光标；光标仍由右摇杆（patch G）。
- **L5 封面图著作权**：图由用户提供（p 图），仅随本地 A9 产物使用；如需公开分发需自行确认授权。

## 10. 复现

```bash
# 1) patch H（相对 patch G 之后状态）
cd /path/to/Kirikiroid2-NX && git apply -p1 --recount --whitespace=nowarn H-input-tweaks.patch
# 2) 构建
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc '<repo>/build-scripts/rerun_ninja.sh'
# 3) 打包 A9（keyset 只显式传入，不入库）
PYTHONPATH=src python -m galnx package nsp --manifest examples/pilot01-haruno-cn4.yaml \
  --elf <...>/kirikiroid2.elf --romfs-dir <romfs-a8> --keyset <prod.keys> --out <A9.nsp> \
  --build --nstool <nstool> --hacbrewpack <hacbrewpack> --elf2nso <elf2nso> \
  --npdmtool <npdmtool> --nacptool <nacptool>
```

## 11. 关联

- [013 — patch G 手柄映射 v2](013-k2nx-controller-input-v2.md)（B=back、X=自动、Y/+ = 读/存档、-=退出、ZR/ZL、右摇杆光标、左摇杆滚轮）
- [012 — 中文内容包](012-k2nx-cn-content.md)
- [P4 真机 runbook §11](../pilot/P4-device-runbook.md)
- 补丁总表：`docs/builds/patches/k2nx-switch/README.md`
