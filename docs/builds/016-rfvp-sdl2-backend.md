# 016 — rfvp Switch 渲染后端改造：CPU 软光栅 → SDL2/GLES2（60 fps）

- 编码：016
- 对象：xmoezzz/rfvp（Nintendo Switch target：platform/switch）
- 版本/commit：HEAD 9f07adef2eb5d559777f9bf59a67b756875cb24f；toolchain pin nightly-2026-02-01
- 许可证：MPL-2.0（仓库 LICENSE，platform/switch/host/Cargo.toml 同）
- 日期：2026-10-30 / 2026-10-31
- 执行：Lead（P9 性能改造）
- 结论：**模拟器级 PASS**。Citron Nightly 0237a9b88 实测 **60.0 fps 满帧**（原软光栅 17–19 fps），标题画面与中文正文均正确渲染；真机未验证。
- 产物：rfvp.nro **7,823,416 B，SHA-256 e3acbce42ae2e55acae386ece29ba1f794b029dc6e9b2e48302993b87b0d9399**（构建树 E:/galnx-build/m5-rfvp，产物不入库）
- 补丁：docs/builds/patches/rfvp-switch/rfvp-sdl2-backend.patch，1,238 行 / 6 文件（含 1 新文件），SHA-256 515af726a8f6804102b3ffd99a3a1e9e1edfa567694e48ccc9cee3ba712b77c7
- 证据：docs/milestones/evidence/P9a-rfvp-sdl2/（title-t0.png、story-t5.png、story-t5-zoom.png、diag6-story-t5.png、perf.txt、SHA256SUMS.txt）

## 1. 目标

用户（m15372）把「解决巨大性能问题」定为当前最高优先级。008 评估记录的本机 Citron 实测为 **17.5 fps**，debug_report 的 perf 汇总显示 render ≈ 38.8 ms/帧、整帧 ≈ 39 ms —— 瓶颈在引擎自带的 **CPU 软光栅**（crates/rfvp/src/soft_render/），它把整幅 1920x1080 虚拟画面逐像素合成到内存，再整帧拷进 libnx framebuffer。

本记录目标：在不改游戏语义、不碰输入/音频/文件 IO 的前提下，把 Switch 显示路径换成 **SDL2 + GLES2（GPU）**，让 Citron 内达到 vsync 上限 60 fps，并保证文字层正确显示。

## 2. 环境与工具链（实测）

| 组件 | 版本/路径 | 说明 |
| --- | --- | --- |
| 宿主 | Windows 10.0.26100 x64 / 16 核 | 构建根 E:/galnx-build/m5-rfvp（无空格） |
| devkitPro | D:/devkitPro | devkitA64 r30-1、gcc 16.1.0-1、libnx 4.12.0-1、switch-tools 1.13.1-1 |
| Switch SDL2 | devkitPro/portlibs/switch，**SDL2 2.28.5** | include/SDL2/SDL.h、lib/libSDL2.a；Switch video driver 为 opengles2 |
| Rust | rustc 1.95.0-nightly | toolchain nightly-2026-02-01 + rust-src（与上游 platform/consoles/toolchain.env 一致） |
| Citron | Nightly 0237a9b88 | 单实例，-g 直接加载 NRO |
| 构建命令 | env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/m5-switch-build3.sh' | wrapper 设 DEVKITPRO=D:/devkitPro、CARGO_HOME、代理，日志尾部打印 NRO sha256 |

## 3. 改造前基线（软光栅）

| 指标 | 数值 | 来源 |
| --- | --- | --- |
| Citron 帧率 | 17–19 fps | debug_report.txt 首行 |
| render / 帧 | ≈ 38.8 ms | perf avg over 60 ticks |
| 整帧 | ≈ 39 ms | 同上 |
| 画面 | 正确（标题 + 正文都在） | p0-e 系列 run |
| NRO | 1,372,216 B 4964dda9… | 008 记录 |

软光栅是纯 CPU 路径：SoftRaster::present() 把 1280x720 RGBA 每行 copy 到 libnx framebuffer；present() 与 draw_* 都在主线程，无可并行空间。

## 4. 方案：SDL2/GLES2 后端

### 4.1 分层

- **保留**：libnx 输入（pad/touch）、audio_init/audio_pump（audren）、rfvp_switch_log（svcOutputDebugString）、文件 IO FFI。
- **替换**：显示层。删除 framebufferCreate/framebufferMakeLinear/framebufferBegin/End 与 save_screenshot，改由 SDL2 独占 nwindow：SDL_Init(VIDEO) → SDL_CreateWindow(1280x720, FULLSCREEN) → SDL_CreateRenderer(ACCELERATED|PRESENTVSYNC)。
- **新增**：Rust HorizonRenderer 不再持有 SoftRaster，改为把 RfvpRenderer 的每个方法转发给新的 C shim（platform/switch/runtime/sdl_video.c）。

### 4.2 C shim 导出面（sdl_video.c，495 行）

    galnx_sdl_video_init / galnx_sdl_video_shutdown
    galnx_sdl_texture_create / galnx_sdl_texture_update / galnx_sdl_texture_destroy
    galnx_sdl_begin(vw, vh, clear_enabled, clear_rgba)
    galnx_sdl_draw_quad(id, xy8, uv8, colors4, blend, filter, scissor_valid, sx, sy, sw, sh)
    galnx_sdl_draw_solid(x, y, w, h, rgba, blend, scissor_valid, sx, sy, sw, sh)
    galnx_sdl_present / galnx_sdl_pump_events
    galnx_sdl_read_pixels_scaled(w, h, out) / galnx_sdl_write_screen_bmp(path)

映射规则：

- 输出固定 1280x720，scale = min(1280/vw, 720/vh)、内容区居中 letterbox（虚拟 1920x1080 → 输出 1280x720）。
- 虚拟坐标 → 输出坐标的变换在 C 内完成（map_scale/map_offset），Rust 只传虚拟坐标。
- 纹理：SDL_PIXELFORMAT_ABGR8888 + SDL_TEXTUREACCESS_STREAMING；Rgba8 直传（小端内存序恰为 R,G,B,A），Bgra8/Rgb8/Luma8/LumaA8/Alpha8 在 C 内转 RGBA。
- 混合：Opaque→NONE、Alpha→BLEND、Add→ADD、Multiply→SDL_ComposeCustomBlendMode(DST_COLOR,ZERO,ADD, ZERO,ONE,ADD)、Screen→ComposeCustomBlendMode(ONE,ONE_MINUS_SRC_COLOR,ADD, ONE,ONE_MINUS_SRC_ALPHA,ADD)。
- 绘制：SDL_RenderGeometry(renderer, tex, verts4, 4, indices6={0,1,2,2,1,3}, 6)；draw_solid 用 SetRenderDrawColor + RenderFillRect。
- 裁剪：基础裁剪 = 内容区，命令 scissor 与之求交后 SDL_RenderSetClipRect。
- 缩略图/截图：capture_thumbnail 与 screen_bmp() 用 SDL_RenderReadPixels 读回后盒式缩放；debug_screen.bmp 由 C 直接写 54 B BMP 头 + BGRA 行。

### 4.3 关键语义：create_texture 必须是 upsert

引擎 crates/rfvp/src/rendering/prim_commands.rs:224 的 upload_graph_if_needed() 在 generation 变化时直接 backend.create_texture(host_texture_id(graph_id), desc, pixels)?，而 host_texture_id(graph_id) = TextureHandle(graph_id as u32) —— **同一个 id 会被反复 create 覆盖**；只有 remove_graph 才 destroy_texture。软光栅后端 soft_raster.rs 的 create_texture 本身就是 insert 覆盖语义，所以旧后端天然正确。

C shim 第一版写成「已存在则返回 -3」，导致文字层（graph_id = 4064 + slot）只成功首帧（空纹理），之后所有上传被拒 —— 这是「文字不可见」的第一真因，见 §7。修正后：已存在则 SDL_DestroyTexture(entry->texture) 后复用槽位。

### 4.4 构建链接顺序坑

build_switch.sh 的链接顺序必须是：

    main.o sdl_video.o LIB -L portlibs/switch/lib -lSDL2 -lEGL -lglapi -ldrm_nouveau -lpthread -lstdc++ -L libnx/lib -lnx -lm

- -lnx 放在 -ldrm_nouveau 之前 → undefined reference to nvGpuChannelKickoff / nvGpuChannelAppendEntry（libdrm_nouveau 依赖 libnx，静态库顺序敏感）。
- libEGL.a 的 nv50_ir 需要 -lstdc++ 与 -lm（exp2f/pow/powf/log2f）。
- 不能用 sdl2-config 输出（它写死 MSYS 视角路径 /opt/devkitpro 与 /d/...），改为显式 -I$DEVKITPRO/portlibs/switch/include/SDL2 -D__SWITCH__ -D_REENTRANT -ftls-model=local-exec。

### 4.5 SDL 主循环

devkitPro SDL2 的 Switch 视频驱动在 SDL_PumpEvents 内 tick 小程序循环，因此 main.c 不再调用 appletMainLoop()，改为：

    while (galnx_sdl_pump_events() == 0) {   // SDL_QUIT 返回 1
        /* pad + touch 采集 */
        rfvp_switch_frame(app, &input, NULL, 0);   // present 内部 SDL_RenderPresent
        /* shot 帧：galnx_sdl_write_screen_bmp(...) */
        audio_pump(app);
    }

## 5. 基准验证（先证明 SDL2/GLES2 在 Citron 下满帧）

改造前先写了一个最小 SDL2 基准 E:/galnx-build/m5-sdlbench（Makefile + source/main.c）：3 张流式纹理（2×1920x1080 全屏 + 1024x540 BLEND overlay），每帧 clear + 3 次 RenderCopy + present，每 60 帧写 fps。

| 指标 | 结果 |
| --- | --- |
| renderer | opengles2 flags=0xe vw=1280x720 |
| fps.txt | frame 420 fps 60.0 ms/frame 16.67 |
| 画面 | 渐变图案正确，nonblack_ratio=0.9018（无黑屏） |

注：Citron 日志会出现 [Critical] shader_recompiler/frontend/maxwell/decode.cpp:49 ... Invalid insn 断言，但画面正确，判定非致命。

## 6. 改造后实测（干净构建，无诊断插桩）

### 6.1 运行配置

- run：E:/galnx-build/m5-rfvp-run/p0-clean1/20261031-034816-rfvp，.done = status=loaded rc=0 finished=2026-10-30T19:51:08Z。
- 输入脚本（harness --input-steps）：wait:26000;capture:t0;click:1395,565;wait:35000;capture:t1;wait:10000;capture:t2;click:900,520;wait:6000;capture:t3;click:900,520;wait:6000;capture:t4;wait:12000;capture:t5。
- 关键：本作 New Game 后有很长白场 + typewriter，**正文首次出现约在启动后 63.5 s**，验收截图必须 ≥ 90–100 s（见 §7.2）。

### 6.2 性能（PASS）

| 指标 | 软光栅（008/改造前） | SDL2/GLES2（本次） |
| --- | --- | --- |
| 帧率 | 17–19 fps | **60.0 fps**（vsync 上限） |
| render / 帧 | ≈ 38.8 ms | **15.57 ms（含 vsync 等待）** |
| vm / scene | — | 0.56 ms / 0.23 ms |
| 整帧 | ≈ 39 ms | 16.37 ms |
| NRO | 1,372,216 B | 7,823,416 B（含 SDL2/EGL 静态链接） |

debug_report.txt 首行：frame 8340: 60.0 fps over the last 60 frames, slowest frame 17.2 ms；第二行 virtual frame 1920x1080；末行 perf avg over 60 ticks: vm 0.56 ms, scene 0.23 ms, render 15.57 ms, total 16.37 ms。

render 仍未归零是因为它统计了 present() 里的 vsync 阻塞（上限 60 fps 的必然等待），不是 GPU 负载。

### 6.3 画面正确性（PASS）

| 帧 | 内容 | 中心区白像素 |
| --- | --- | --- |
| t0（26 s） | 标题画面（五彩斑斓的世界 HD Re:GENERATION，New Game/Continue/Album/Option/Exit） | 2.71% |
| t1/t2（61/71 s） | 白场 + 打字机 | 99.85% |
| t3（77 s） | 白场 + 半截文字 | 99.51% |
| t4/t5（83/95 s） | 云海背景 + 正文 | 1.50% / 1.66% |

**t5 目视确认：云海背景上清晰白色中文正文「从天而降的羽毛。」**，字形、字号、位置（居中偏左，游戏原样）全部正确。放大图 story-t5-zoom.png。

健康度：citron_log.txt 136,650 B / 879 行，panic=0 EXCEPTION=0 Crash=0；texture create failed=0；无 last_error.txt。日志另有 2 条游戏自身的 [ERROR] history_set: unexpected value for set_name/set_voice : Nil（既有，非本次引入）。

## 7. 「文字不可见」的两个真因（排查记录，避免复踩）

### 7.1 真因一：C shim 的 create_texture 不是 upsert

现象：SDL 后端能跑满 60 fps、标题画面完美，但正文完全看不到文字；纹理转储 textdump_4064.bmp 只有几百个非黑像素。

定位：日志统计出 **144 条 rfvp: texture create failed: id=4064 1024x540 rc=-3** —— 文字图（graph_id = 4064 + slot）第一次 create 成功（空内容），之后每帧 recreate 都被「已存在」拒绝，纹理永久冻结在空帧。根因见 §4.3。修正为 upsert 后 create failed 归零、id=4064 的 568 次 create 全部成功。

### 7.2 真因二：验收截图早于文字出现时间

修完 upsert 后仍看不到文字，进一步插桩（临时）后发现：文字纹理的 alpha_px 随时间增长 0 → 175 → … → 5406（bbox 最终 (57,16)-(287,46)，正好是「　……羽毛。」整行），**但首次出现时间在启动后 t≈63.5 s**，而当时所有 run 的截图最晚只到 ~58 s。把等待拉长到 95 s 后，正文如期出现（diag6 / p0-clean1 双确认）。

> 教训：本作 New Game 后有长白场 + 慢速 typewriter，**验收截图必须 ≥ 90 s**；此前「文字不可见」的很大一部分是采样时机问题。

## 8. 产物哈希

| 产物 | 大小 | SHA-256 |
| --- | --- | --- |
| rfvp.nro（干净构建） | 7,823,416 B | e3acbce42ae2e55acae386ece29ba1f794b029dc6e9b2e48302993b87b0d9399 |
| rfvp-sdl2-backend.patch | 1,238 行 / 6 文件 | 515af726a8f6804102b3ffd99a3a1e9e1edfa567694e48ccc9cee3ba712b77c7 |
| title-t0.png | 1,417,785 B | 3dde72246d03b2f13d52c5a24236c6f1daefc46ce12f16dda4c4a769a47fd7ee |
| story-t5.png | 1,493,686 B | 65e2c440b4a2e6f7adc28c7691479ed2a6fd0a880018dd6b9fb85821c6962e34 |
| story-t5-zoom.png | 280,467 B | 038b652f82117d6bd84d6030a6879889cd59d3cc60b51dc7e3d1b674521cfc7a |
| perf.txt | 175 B | 037f652f47ba8205c4b05ace73f8ed330eef124dc9087460901426fa19ea9f31 |

补丁文件清单（6 个，git apply --check 已在纯净 worktree 通过）：

1. platform/switch/build_switch.sh — SDL2 头/库、编译 sdl_video.c、链接顺序。
2. platform/switch/host/build.rs — Windows .exe 工具探测修复（缺此补丁会回落到宿主 gcc 生成 COFF 对象）。
3. platform/switch/host/src/ffi.rs — perf avg over 60 ticks 统计（验收证据；present() 不再传 framebuffer）。
4. platform/switch/host/src/render.rs — HorizonRenderer 转发 C shim（纹理格式表、capture_thumbnail 读回、screen_bmp、screen_to_virtual 逆变换、set_target 空实现）。
5. platform/switch/runtime/main.c — SDL 主循环、pad/touch、shot 截图。
6. platform/switch/runtime/sdl_video.c（新）— SDL2 视频 shim。

## 9. 复现步骤

    # 1. 打补丁（上游 HEAD 9f07adef）
    cd /e/galnx-build/m5-rfvp
    git apply "/e/Othergames/Nintendo Switch/Workspace/GalNX/docs/builds/patches/rfvp-switch/rfvp-sdl2-backend.patch"
    # 2. 构建
    env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc "bash /e/galnx-build/m5-switch-build3.sh"
    # -> target/rfvp-switch/switch/rfvp.nro
    # 3. Citron 运行（必须 git-bash，且显式 CITRON_USER_DIR）
    bash scripts/citron_run.sh --nro .../rfvp.nro --detach --timeout 200 --settle 8 --out <dir> --input-steps "wait:26000;capture:t0;click:1395,565;wait:35000;capture:t1;..." --allow-existing

## 10. 未验证项

| 编号 | 项 | 说明 |
| --- | --- | --- |
| U1 | 真机 | 仅 Citron 验证；Switch 硬件未测（用户设备后续）。 |
| U2 | 音频 | audio_init/audio_pump 路径未改，本次 run 未做听感/波形验证。 |
| U3 | 中文（NLS/GBK） | rfvp 自带 nls 支持但未验证中文文本；本次画面文字来自游戏自带 UTF-8 内容。 |
| U4 | 手柄映射 | 当前仅保留 libnx pad → RfvpSwitchInput，A/B/X/Y/十字/摇杆/PLUS/MINUS 的游戏内语义未标定。 |
| U5 | 内存 | 1920x1080 虚拟帧 + 多张 2400x1350 纹理在真机 4 GB 下的峰值未测。 |
| U6 | MPL-2.0 合规 | 分发含补丁的二进制需按 MPL-2.0 提供对应源码与声明。 |
| U7 | 视频播放 | 游戏内 movie 路径（movie/）未验证。 |

## 11. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-30 | 建立：SDL2/GLES2 后端落地，Citron 60 fps + 文字可见，干净构建与证据归档 |
