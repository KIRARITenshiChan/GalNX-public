# 049 · もゆ标题粒子三处修复 + 调试播片通道（P41，v1.3.2-test / v1.2.4-test）

- 日期：2026-11-10
- 相关：`docs/builds/patches/rfvp-switch/P41-snow-particles.diff`、`docs/milestones/evidence/P44-snow-particles/`、计划 v1.39
- 状态：模拟器（Citron）验证完成；真机由用户安装验收

## 1. 背景

用户 m38188 对比 PC 版与 NS 版《さくら、もゆ。》标题画面：PC 版背景有大量红色粒子全程向上飘动，NS 版完全没有；随后 m38329 确认第一次修复后「出现了少量粒子，但远不及 PC 版」，m38555 要求解释方法并继续提升密度。

标题粒子来自游戏脚本的 `Snow()` 粒子系统（`sakura.lua` 的 `f_0006A9A2`，约 96880–97620 行）：先 `GraphLoad(1592, "graph/particle500")` + `GraphLoad(1593, "graph/particle501")` 两张图，再 `PrimSetSnow(1592,0,0,0)` / `PrimSetSnow(1593,1,0,0)` 建两个 snow prim，并 `Snow(0,...)` / `Snow(1,...)` 各配一套参数，最后 `SnowStart(0,...)` / `SnowStart(1,...)` 启动。

## 2. 三层根因（按发现顺序）

### 2.1 `Snow()` 参数校验把整次调用拒掉

`crates/rfvp/src/subsystem/components/syscalls/other_anm.rs` 的 `snow()` 对 arg9、arg10 都要求 `1..=1024`。但源码字段语义是：`flake_count = arg9`（flake 表容量 1024），`base_y_per_period = arg10`（每周期 Y 位移，属于速度量）。もゆ标题传 `arg10 = 2000 / 2500`，于是 `Snow()` 打印 `snow: arg10 should be in range 1..1024` 并返回 Nil —— 粒子系统根本没建立，标题完全无粒子。

修复：arg10 校验改为 `-65535..=65535`（保留 arg9 的 1..=1024），并加注释说明两者语义不同。

### 2.2 两个 snow prim 都画到 motion 0

`PrimSetSnow(id, mode, x, y)` 的第二个参数就是 snow slot（0/1），但 `graph.rs` 的 `prim_set_snow()` 完全忽略 `mode`；而渲染器 `emit_snow()` 用 `prim.get_texture_id()` 当 motion slot。两个 prim 的 texture_id 都是 0 ⇒ 两套 snow 都画 motion 0 的 60 个 flake，motion 1 的 1024 个 flake 永远不画。

修复：`prim_set_snow()` 在 `prim_init_with_type(id, PrimTypeSnow)` 之后把 `mode` 写进 `prim_set_texture_id(id, mode)`。

### 2.3 变体贴图未加载，4/5 的 flake 被丢弃

`SnowFlake.variant_idx` 由 `next_u32() % variant_count` 生成，渲染端用 `base_tex + variant_idx` 取 graph。标题预设 `variant_count = 5`（`flake` 24×24，贴图 graph/particle501 实际 110×18），但脚本只 `GraphLoad` 了 1592/1593 两个 graph id，1594–1597 从未加载：`upload_graph_if_needed()` 返回 false，`continue` 丢掉该 flake ⇒ 1024 个里只画出约 205 个，与「密度变高但仍稀疏」吻合。

修复：`emit_snow()` 先试 `base_tex + variant`；graph 存在但贴图上传失败（或 graph 缺失）且 variant != 0 时回退到 `base_tex` 重新取图上传，并加注释说明「标题常常只为多 variant 的 Snow() 预加载 base 贴图」。

## 3. 量化验证（Citron，统一判据）

静止红点像素会被标题红色 logo 主导，不能反映粒子密度；改用**时序差分**：同一 run 间隔 3 s 的两张标题截图，区域 x=40..0.45W、y=40..0.60H，灰度差 >25 的采样点计数，换算每万像素。

| 阶段 | 可见 flake | 时序差分（/万像素） |
| --- | --- | --- |
| 仅放宽 arg10（修复前） | motion 0 的 60 | 1.10 |
| + PrimSetSnow slot 修复 | 约 205 + 60 | 5.56 |
| + 变体回退 base 贴图 | 1024 + 60 | 39.49 |
| 清理插桩后的干净构建 | 1024 + 60 | 32.84 |
| 1.3.1-test NSP（romfs 启动） | 1024 + 60 | 33.19 |

干净构建的 `debug_report.txt` 中 `snow:` 报错 0 行（`docs/milestones/evidence/P44-snow-particles/citron-clean-check.txt`），说明 `Snow()` 不再被参数校验拒绝。原始截图与指标见 `docs/milestones/evidence/P44-snow-particles/`（含三态对比拼图 `snow-compare-3up.png`）。

## 4. 调试播片通道（P41 附带）

为了在 Citron 复现 ED/第二个视频，本补丁把「强制播片」调试钩子从固定 `movie/01.wmv` 扩展为可指定序号，并沿用 P40c 的「调试开关独立文件」约定（默认不触发）：

- `platform/switch/runtime/main.c` 新增 `rfvp_switch_debug_movie_index()`：读 `sdmc:/switch/rfvp/movie_debug.txt`，`movie=2` 或 `index=2` 返回 2（`3` 同理），否则 1。
- `videoplayer/horizon.rs` 新增 `pub(crate) fn debug_movie_index() -> u32`；`no_std_core.rs` 的调试钩子用它拼 `movie/{index:02}.wmv`（H.264 后端自动映射为 `movie/{index:02}_h264.mp4`）。
- `main.c` 新增 `rfvp_switch_skip_probe()`：`movie_debug.txt` 含 `skip=1` 时让输入层强制按住 R（=Ctrl），用于在 Citron 自测脚本的跳过分支；不创建该标记文件时行为完全不变（发布版不创建）。

验证：`movie_debug.txt = movie=nil + index=2` → Citron 日志 `Movie: opened (Switch NVDEC H.264) asset=movie/02_h264.mp4`、106 条 decoded 帧（1→1470+，pts 到 48.9 s），截图为「輪廻 rinne」与 さくら、もゆ logo。结论：`movie/02` 是**真結局 OP**（用户 m38780 确认），不是 ED；游戏 `movie/` 目录只有 01/02 两个视频，ED 应为脚本演出，无需再找 ED 视频资源。

## 5. 构建与产物

构建唯一姿势：

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p40/build.sh'
```

注意：不要在 `env` 前加 `MSYS_NO_PATHCONV=1`，否则 cargo 报 target json 路径非法。

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| `rfvp.elf`（最终干净） | 20,406,336 | `0a24d18c926b6d652a074b1d51eca48fa4396a2e8dc15167cc8603ddb03f71ee` |
| `rfvp.nro`（最终干净） | — | `4ee6f67d956abca60c677386b4f363a055ba242e9134737d3e859ec82a54052b` |

NSP（均为自包含 romfs，`--romfs-mode hardlink`，verify 13 checks / 0 fail / 1 未签名 warn）：

| 包 | 大小 | sha256 |
| --- | --- | --- |
| SAKURA MOYU CN v1.3.2-test（010047420000c200） | 8,116,836,056 | `8df0d39823ec14082187c94b56a9142ce151e499d59d5604fc73bcebe2dfafef` |
| IROSEKA FHD v1.2.4-test（010047420000a000） | 10,087,536,344 | `8b12f57fa5938f9c5c5b6c0f27d39500d214bdf533e4d262c2d09da6c0b6e44a` |

前期用上一版 ELF 构建的中间包（仅供追溯）：もゆ v1.3.1-test 8,116,837,080 B `624ba37814f5737c23186121821ab7925bed0325fa05dd23c0ccc4776d5d0e82`；iroseka v1.2.3-test 10,087,537,368 B `5c1a2374b5f10af012ccc99244ca4ac552ac751fdbbf7cf63402b9898a023952`。两者与最终源码只差一段不产生任何副作用的调试残留代码（清理后重建）。

## 6. 补丁

`docs/builds/patches/rfvp-switch/P41-snow-particles.diff`：232 行、7 文件、+116/−22，sha256 `4cbb337b273e92de06ebbce60f626c1b7028ddea0bfd1f232704df6104aee3ea`。应用顺序：P40 → P40b → P40c → P41；已在 P40c 基线树上 `git apply --check` 通过，应用后与构建树逐字节一致。

文件：`other_anm.rs`、`graph.rs`、`prim_commands.rs`、`main.c`、`event.rs`、`horizon.rs`、`no_std_core.rs`。

## 7. 限制

1. 变体语义未证实：脚本只加载 2 张图而 `variant_count=5`，当前实现把变体当独立 graph id（缺失回退 base）。真机原版如何采样这张 110×18 贴图未验证。
2. 粒子运动速度未对齐 PC（用户 m38513 明确不追速度；Citron 上肉眼观察缓慢上升，数量与 PC 接近）。
3. 截图来自 Citron 软解，帧率数值不代表真机性能；真机仍需用户安装 1.3.2-test / 1.2.4-test 后目视确认。
4. `skip=1` 调试通道属于自测设施，发布说明中要求用户不要创建 `movie_debug.txt`。

## 8. 复现

```bash
# 重建 ELF/NRO
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p40/build.sh'
# Citron 标题粒子冒烟（需 git-bash 启动）
/d/Scoop/apps/git/current/bin/bash.exe -c 'bash /e/galnx-build/p41/run-snow-verify.sh'
# 打包（もゆ）
/d/Scoop/apps/git/current/bin/bash.exe -c 'bash /e/galnx-build/p41/build-nsp-moyu-132.sh'
```

## 9. 教训

1. 参数校验不要照抄相邻参数的范围：`arg10` 是速度量，用 `arg9` 的 1024 上限会静默拒绝整次 `Snow()`。
2. 「修复一项后仍不够」要继续量化：只修 slot 时密度提升 5 倍仍远低于预期，统计 `drawn/missing/upload_fail` 才定位到变体贴图问题。
3. 输出型插桩（每次绘制都计数）比输入型日志更能解释「为什么少画」；但出包前必须整块删除并重建，避免死代码混入交付物。
4. 日志判定要用运行期快照或结束前抓取：SD 上的 `debug_report.txt` 会被后续运行覆盖，早期 run 的原始日志不可恢复（本次 P44 只保留了干净构建与 NSP 冒烟两份完整日志）。
5. 游戏视频资源的坑：`movie/02` 是真结局 OP 不是 ED；ED 前先看资源目录里到底有哪些视频文件。
