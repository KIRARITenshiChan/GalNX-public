# krkrsdl2 Switch 模拟器兼容修复包

上游 [krkrsdl2/krkrsdl2](https://github.com/krkrsdl2/krkrsdl2) 在 Switch 平台层的路径/命令行桥接有 4 处缺陷，导致 NRO 在模拟器（Citron）中启动阶段即退出、无法创建窗口。本补丁以 `#ifdef __SWITCH__` 最小分支修复，不改变非 Switch 平台行为。

| 项 | 值 |
| --- | --- |
| 上游基线 | `124bdf84`（2026-10-01，与 `docs/audit/06-engines-refresh.md` 记录一致） |
| 补丁文件 | `krkrsdl2-switch-emulator-fixes.patch`（2,869 B；`git apply` 可直接用） |
| 等价脚本 | `apply_clean_fixes.py`（4,070 B；按锚点打补丁，仅用于 Baseline 未变时） |
| 改动规模 | 4 文件，+38 行 |
| 验证产品 | `docs/builds/004-krkrsdl2-switch-fixes.md`（NRO 17,911,329 B，Citron 出画面） |

## 修复内容

| # | 文件 | 问题 | 修法 |
| --- | --- | --- | --- |
| F1 | `src/core/sdl2/SDLApplication.cpp` | 模拟器传 `argc == 0` → `_wargv` 为空 → `ExePath()` 越界读到垃圾串 | 空参数时回退 `argc=1, argv={"sdmc:/switch/galnx/app.nro"}` |
| F2 | `src/core/environ/sdl2/Application.cpp` | `ExePath()` 空值回退到 `_wargv[0]` | `__SWITCH__` 下回退到固定 app 路径（防御性） |
| F3 | `src/core/base/sdl2/SysInitImpl.cpp` | Switch 上 `SDL_GetBasePath()` 返回 NULL → 项目目录变成 `file://./` → startup.tjs 找不到 | 空 base 路径回退到 `romfs:/` |
| F4 | `src/core/base/sdl2/StorageImpl.cpp` | `?/romfs:/…` 被拼成 `./romfs:/…`，存在性检查恒失败 | `GetLocallyAccessibleName` 入口剥掉 `?/` 前缀，直接返回原生路径 |

## 用法

```bash
cd /path/to/krkrsdl2   # HEAD = 124bdf84
git apply /path/to/krkrsdl2-switch-emulator-fixes.patch
# 或（基线一致时）python apply_clean_fixes.py  —— 脚本里路径按本机 E:/galnx-build/m1-krkrsdl2 写死，需先改 ROOT
```

构建/重打包/Citron 验证步骤见 `docs/builds/004-krkrsdl2-switch-fixes.md` §4。

## 证据

- 修复前的崩溃链与逐段诊断：`docs/milestones/evidence/M1c-krkrsdl2-galnx-diag.txt`（2,558 行）、`M1c-krkrsdl2-instrumented.diff`（插桩版完整 diff）。
- 修复后 Citron 截图：`docs/milestones/evidence/M1c-krkrsdl2-kag3-title-citron-clean.png`。
- 补丁未改变渲染结果：插桩版与干净版截图 SHA-256 相同（`0bce597c…`）。

## 注意

1. 补丁只覆盖「模拟器/无参数启动」场景；真机（hbmenu 启动）通常自带 argv，F1/F2 不会触发。
2. 上游 CI 构建的 release NRO（SHA-256 `a11ec7be…`）在 Citron 上仍然失败，与本补丁无关；本补丁的结论只对本仓库构建产物成立。
3. 未确认上游是否已修复；升级 `krkrsdl2` 时先 rebase 本补丁并重跑 004 的验证流程。
