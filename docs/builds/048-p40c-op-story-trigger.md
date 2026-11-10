# 048 · P40c：OP 改回剧情触发并可跳过（去掉启动自动播片钩子）

- 日期：2026-11-09
- 相关：`docs/builds/046-op-h264-nvtegra.md`、`docs/builds/047-p40b-nv12-colour-fix.md`、`docs/builds/patches/rfvp-switch/P40c-op-story-trigger.diff`、`docs/milestones/evidence/P43-op-story-trigger/`
- 状态：Citron 两形态（NRO + NSP romfs）PASS；v1.2.2-test NSP 已构建并 verify；真机验收待用户

## 1. 症状

用户 m36793：

> 别急，现在的版本会在游戏开始时播放 op且不可跳过，我觉得现在应当先把op视频改回由剧情正常出发，然后ed我也没测……

也就是说：P40/P40b 交付的 v1.2.1-test 一启动就自动播 OP，且无法按键跳过。OP 本身已经「不慢放、颜色正常」
（P40/P40b 的成果），问题只在**触发点和可跳过性**。

## 2. 根因：P33 时代的调试钩子还在

P33 做 OP 分档时留了一条调试通道，用来在模拟器里反复调播片：

- `crates/rfvp/src/no_std_core.rs:665-703`：tick 里 `if !self.debug_movie_started && horizon::debug_movie_requested()`
  就 `movie_play("movie/01.wmv", flag)`；
- `flag` 由 `horizon::debug_movie_nil_requested()` 决定，默认 `Variant::True`（**modal**，不可跳过）；
- `platform/switch/runtime/main.c:101-125` 的 `rfvp_switch_debug_movie()` / `..._nil()` 读
  `sdmc:/switch/rfvp/debug.txt` 的 `movie=1` / `movie=nil`。

做性能测试时设备上的 debug.txt 一直是 `shot=900\nmovie=1`，所以每次启动都强制播 modal OP。
**这不是游戏脚本的行为，而是我们的调试开关。**

游戏脚本本身完全支持剧情触发 + 跳过：

- `iroseka.lua:38572` `function f_00034356(a0, a1)` 是 OP/ED 调度器：默认分支调 `f_000426A7(1,nil)` 播 OP，
  `a1==10` 分支播 ED（`f_000426A7(2,nil)`）；
- `f_00034356` 的调用者（均传 `GT[1353][g1406], GT[1351][g1406]`）：`f_00033B33`(`:96665`)、`f_00033BC0`(`:96674`)、
  `f_00033E17`(`:96683`)、`f_00033FC4`(`:96692`)、`f_00034721`(`:96710`)、`f_00067E15`(`:96566`)；
- `iroseka.lua:58131` `f_000426A7` 构造 `movie/01.wmv`（失败再试 `.mpg`）→ `Movie(a0, nil)`，播片循环里
  `InputGetState()` 的 `& 3` 或 `& 1` 非零就 `MovieStop()`——即 Ctrl / Shift 跳过（KiriKiri 经典）。

## 3. 修复（P40c）

`platform/switch/runtime/main.c`：

```c
static const char* const MovieDebugFile = "sdmc:/switch/rfvp/movie_debug.txt";
static int read_movie_debug_file(char* buf, size_t cap);
/* rfvp_switch_debug_movie()/_nil() 改为只读 movie_debug.txt（接受 movie=1/modal 与 movie=nil/nil） */
```

`debug.txt` 仍然负责 `shot=` 截图与 debug_report 开关，但**不再触发影片**；要强制播片必须显式创建
`sdmc:/switch/rfvp/movie_debug.txt`。另外同步了 `horizon.rs` / `no_std_core.rs` 里的注释（功能不变）。

补丁：`docs/builds/patches/rfvp-switch/P40c-op-story-trigger.diff`，3 文件 +26/−37，
sha256 `06f9290041ff58cf1324141e7817730f68d5314734f82f4d41220855a03a2d2b`，
对 P40b 态工作树 `git apply --check` RC=0。

## 4. 构建

```bash
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p40/build.sh'
```

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| `rfvp.nro` | 10,670,136 B | `2666286e44a14662f1fabf00533f05f08c1f1c7e6faa96acf99a98bd92fdae19` |
| `rfvp.elf` | 20,400,232 B | `258a312d4e77ee31d8b0c0a5442ed9f9ab6f324d0701276da9f708c1704675d3` |

（Rust 只改注释，C 改 main.c；NRO 尺寸与 P40b 相同但内容不同。）

## 5. Citron 验证：先证明「启动不再播 OP」

run-05（`E:/galnx-build/p40/run-op-story-citron.sh`）与 run-06（`run-op-story-long.sh`）都从标题 New Game 起步：

- run-05：New Game → 序章正文（灰转场 → 白底「……羽毛。」→ 蓝天「从天而降的羽毛。」），
  debug_report 969 行里 **0 条 `MoviePlay`**；
- run-06：New Game 后连点 10 次推进（每 1.8 s）+ 两次等待，debug_report 1000 行、**仍 0 条 `MoviePlay`**。

结论：去掉钩子后引擎启动不再自动播片（修复生效）。但序章篇幅较长，点到第 13 次还没到 OP 触发点，
所以这条路径不能在有限步数内验证「剧情触发」。

## 6. Citron 验证：剧情触发 + 跳过（run-08）

改用设备存档 DATA.005（用户手动快进到接近 OP 的位置，m36982 提供）：

| 步骤 | 结果 |
| --- | --- |
| 标题 → Continue(1386,638) → 载入列表 | 截图确认 DATA.005 |
| 点 DATA.005 存档单元 (745,275) | 读档成功 |
| 推进一句 → 等 8 s | 1103 行 `MoviePlay: path=movie/01.wmv flag=Nil is_layer_effect=true` |
| 同一刻 | 1104 行 `Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4` |
| 播放中 | decoded frame 1/2/3/4/5/30/…/390（pts 0→12979 ms），presented 360/390 |
| 按 R（Citron 键盘 E，hold 800 ms） | `MovieStop` 生效；无新 decoded 行；回到正文 |
| 之后 | 截图 step-16/18 为正文「从少女跳下的灯塔，到我们之间的距离。相隔大约十米半。」 |

关键点：`flag=Nil` 说明游戏用**非 modal** 方式播 OP（可跳过）；`history_set: unexpected value for
set_voice/set_name : Nil` 是进正文消息层的副作用，不是致命错误。

## 7. v1.2.2-test NSP 与 NSP(romfs) 冒烟

| 项 | 值 |
| --- | --- |
| NSP | `E:/galnx-build/p40/out122/IROSEKA_FHD-010047420000a000.nsp` 10,087,536,344 B sha256 `51d0f8c716db614b7376776bf8d0e6004f08f21448e7b856ad41ca16d435bdda` |
| verify | 13 checks：0 fail / 1 warn（未签名，预期）；3 个 NCA ProgID 均 `0x010047420000A000` |
| romfs | 166 项 hardlink（含 `movie/01_h264.mp4` 108,361,267 B） |
| Citron NSP 冒烟 | run_dir `.../run-citron-09/nsp-romfs/20261109-235305-...`，`JUNCTION_PARKED` 后启动，18/18 步 ok，窗口标题含 `1.2.2-test` |

NSP(romfs) 冒烟的 movie 时间线（`debug_report.txt`）：

```
1102 [INFO] MoviePlay: path=movie/01.wmv flag=Nil is_layer_effect=true
1103 [INFO] Movie: opened (Switch NVDEC H.264) asset=movie/01_h264.mp4
1107 [INFO] movie h264: decoded frame=1 pts=0 ms 1280x720 hw=0 decode_us=18568 convert_us=5899
...
1143 [INFO] movie h264: decoded frame=450 pts=14981 ms 1280x720 hw=0 decode_us=23956 convert_us=2547
      [INFO] movie audio: stopped movie/01.ogg
      [ERROR] history_set: unexpected value for set_voice : Nil   (× 若干，进消息层)
```

即：**资产来自 romfs**（SD game 目录已被挪走），剧情触发 OP，按 R 后音频停止、回正文。

## 8. 限制

1. Citron 无 NVDEC，两次运行都是软解（`hw=0`）；真机硬解路径与跳过手感仍要靠真机验收。
2. run-05/06 只覆盖序章开头，「启动不自动播 OP」已证；「剧情触发」靠 run-08 的存档点证明。
3. **ED 未验证**：iroseka 的 `movie/` 只有 `01.*`，没有 `02.*`；`f_000426A7(2,nil)` 会失败并跳过。
   ED 路径要等 moyu（`movie/02.wmv` 存在）同步时验证。
4. 强制播片调试通道仍保留（`movie_debug.txt`），发布版不创建该文件即可。

## 9. 复现

```bash
# NRO 影子验证（run-08）
bash /e/galnx-build/p40/run-op-device-save.sh
# NSP(romfs) 影子验证（run-09）
bash /e/galnx-build/p40/run-nsp-romfs-citron-122.sh
```

## 10. 教训

1. **调试开关必须与「用户可见行为」隔离**：debug.txt 里一个 `movie=1` 让交付版看起来像功能缺陷，
   代价是两轮真机往返。以后调试通道单独文件 + 文档标注。
2. 反编译调用图（`f_00034356` → `f_000426A7`）比盲点对话框快得多：直接定位到「哪个函数播 OP、哪个键跳过」。
3. 序章很长时，不要指望用点击次数走到剧情点；**让用户给存档**是最省时间的做法（m36982）。
4. 玩家视角的「不可跳过」要拆成两件事验证：`flag` 是否 modal（引擎侧）+ 跳过键是否被游戏读到（脚本侧）。
