# 050 · AKASEKA HD（映入红瞳的世界 HD）自包含 NSP（P42，v1.4.0-test）

- 日期：2026-11-10
- 相关：`examples/pilot04-akaseka.yaml`、`examples/pilot04/icon-256.jpg`、`docs/assets/pilot04-cover.png`、`docs/pilot/akaseka-fd-acceptance.md`、计划 v1.39
- 状态：**真机验收 PASS**（用户 m39477：OP 正常播放无卡顿、手柄映射符合预期、干净退出）

## 1. 目标

用户 m39029 要求把 FVP 系新作《AKASEKA_HD》（`E:/Othergames/Galgame/AKASEKA_HD`，iroseka 的 FD）用与 iroseka / moyu 相同的方案打成**含汉化的自包含 NSP**，并设定验收口径：用户直接真机测试，若「立刻能玩」则说明 GalNX 对 FVP 引擎的适配达到 stable。

## 2. 源资产与打包树

| 项 | 值 |
| --- | --- |
| 引擎 | FVP（`FVPKernel.dll`），与 iroseka 同族；rfvp 直接复用 |
| 脚本 | 根 `.akaseka.hcb` 1,439,856 B sha256 `bec63a5f0c67b1cb8cfeec4542f872b59ff64c36c91d0779399eeccc2257e3b0`（GBK，183,246 个汉字）；该 HCB 自带汉化 |
| 图像 | `graph/` 122 文件，已核对含汉化补丁（`eyecatch_title_A..D`、`slf_prt_sheet` 等哈希与汉化补丁一致） |
| 字体 | `default.ttf` = sarasa-gothic-sc-bold，sha256 `dda756bdc25a8481bb9a0546549640d7ea3d1cc29719eb8cdfff1a047c3d0291`（与 iroseka 相同） |
| OP 源 | `movie/01.wmv` VC-1 1920x1080、227,331,063 B；ffmpeg 实测解码 3,364 帧 / 112.24 s = **29.97 fps**（容器标称 60000/1001 是误标，不是掉帧） |
| 排除 | `saev/`（PC 存档）与 `Assembly-CS.dll` 不入包 |

打包树 `/e/galnx-build/p42/game` 6.2 GB / 141 文件：`.akaseka.hcb` + 11 个 `.bin` + `graph/` 121 文件 + `font/`（LICENSE+bold+semibold）+ `default.ttf` + `movie/`；`config.toml`：

```toml
[game]
hcb = ".akaseka.hcb"
nls = "gbk"
```

## 3. OP 转码（P40 H.264 管线）

Tegra 无 VC-1 硬解，必须重编码；沿用 P40 建立的 H.264 + nvtegra 路线：

```bash
ffmpeg -i 01.wmv -vf scale=1280:720 -c:v libx264 -profile:v high -preset slow \
  -crf 20 -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -r 30000/1001 -an -movflags +faststart movie/01_h264.mp4
ffmpeg -i 01.wmv -vn -c:a libvorbis -q:a 6 movie/01.ogg
```

| 产物 | 大小 | sha256 |
| --- | --- | --- |
| `movie/01_h264.mp4` | 59,890,911 B | `038816f82f48dd7b959f312a3bd660bd13c95a30ed7d68da95fa3b239cacbf86` |
| `movie/01.ogg` | 2,250,777 B | `ac4bff629b3a7afd2d71051be58c6771c4c425dc3e4ca64c83fe4727c7f26885` |

选择 720p：掌机原生分辨率，且 1080p 会逼近帧预算（见 §7）。

## 4. 图标与清单

- exe 关联图标只有 32x32 不可用 → 从 OP `t=45s` 的真红特写（`/e/galnx-build/p42/icon/src45.png`）中心裁 720 方形 → 256：`examples/pilot04/icon-256.jpg` 15,158 B sha256 `707fb9f3cd4676abe001a054337a3489ca81cf57e38d024080ecc49663a8b23f`；展示用封面 `docs/assets/pilot04-cover.png` 339,720 B sha256 `3cc4ce278f431fa747a237ab9352fcc7a98dfa7454eb6be533b9d5fa8603733b`。
- 清单 `examples/pilot04-akaseka.yaml`：`game.id pilot04-akaseka`、title 映入红瞳的世界 HD、version `1.4.0-test`、engine.adapter rfvp、entry `.akaseka.hcb`、options `{config: config.toml, nls: gbk}`、`switch.title_id 010047420000D000`、package `self_contained_nsp`。

## 5. NSP 构建与校验

- 运行时 ELF 沿用 P40 栈的现有 rfvp 运行时（`E:/galnx-build/p40/rfvp/target/rfvp-switch-runtime/rfvp.elf` sha256 `0a24d18c926b6d652a074b1d51eca48fa4396a2e8dc15167cc8603ddb03f71ee`）——**本作没有新增任何引擎补丁**，直接复用 P40 的 H.264 电影管线。
- 构建脚本 `/e/galnx-build/p42/build-nsp.sh`（`scripts/build_nsp_game.sh` 封装）：romfs hardlink 141 文件，hacBrewPack 416 s。
- 产物：`/e/galnx-build/p42/out/AKASEKA_HD-010047420000d000.nsp`
  - 6,676,387,544 B，sha256 `569af9fbffad68f9423c14b7072d29e14864dec503d5e6039e96b111f9585732`
  - romfs 6,656,764,531 B / 141 文件（`du -sb` 与 `find -type f` 一致）
  - TitleID `010047420000D000`、Name `AKASEKA HD`、version `1.4.0-test`
- `galnx package nsp verify`：ok=true，12 checks / 0 fail / 1 warn（NCA 未签名，自制包预期）；3 个 NCA（Meta / Program 0x18defba00 / Control），ProgID 三处一致。
- 构建日志注意：STEP 6/6 的 nstool 由 harness 传参混用 `/` 与 `\\` 会报 `Path literal has both forward ('/') and backward ('\\') path separators` 并 exit=1；单独用全反斜杠路径跑 `nstool -y` 得 exit 0、PFS0 FileNum 3——是 harness 传参问题，不是 NSP 损坏。

## 6. 模拟器验证（Citron 0237a9b88）

1. **首启**：窗口标题 `citron Nightly | 0237a9b88 | AKASEKA HD (64-bit) | 1.4.0-test | NVIDIA`，中文标题画面（映入红瞳的世界 HD Re:GENERATION + New Game/Continue/Album/Option/Exit/Copyright），screenshot nonblack_ratio 0.9018，sha256 `36e902fe4beb0693fe0b9eff03897e6b379dcd20dc0509687b3db44e9144683c`。
2. **OP**：Citron 没有真 NVDEC，H.264 硬解在 try_open 阶段失败会回落 WMV2（本作 `01.wmv` 是 VC-1，模拟器里不出画面）。按 P40 的既定做法写两个 marker 后跑调试播片：
   - `sdmc:/switch/rfvp/h264_sw.txt`（强制 CPU 解码，**仅模拟器用，真机绝不放**）
   - `sdmc:/switch/rfvp/movie_debug.txt` 内容 `movie=1`（裸 `1` 无效）
   结果 4 张连续截图全部命中 OP 内容（白闪字幕淡入 → 夕阳下真红 → FAVORITE 标志），日志无 NVDEC OnOpen 行（CPU 软解），证据 `/e/galnx-build/p42/evidence/op3/`：

   | 证据 | sha256 |
   | --- | --- |
   | `step-01-opA.png` | `a592fe4181a23a4b7d8efb91837e2b0a4326649250ded14cf14354551e9fd3f2` |
   | `step-03-opB.png` | `dade7f71a7fbf981df5a903c264afd4cad1f506885d0bb06c0f6c3c0e45985bb` |
   | `step-05-opC.png` | `bc63f8b8312a7a4b221b2e0de6879da1240c8be0be9289027b7a29356b9e4e12` |
   | `step-07-opD.png` | `a4366b5c6c76bbcfc455f583182adc1710e905d16e4063e1c4a0ef37fcf70d48` |

3. 注意日志行 `debug movie: started movie/01.wmv` 打的是**请求路径名**，不代表走了 WMV2 解码；判断依据是 NVDEC 服务是否有 OnOpen、以及画面内容。

## 7. 1080p 性能判断

probe9 真机数据：decode 0.44 ms/帧、NV12 传输 3.79 ms/帧 → 解码与传输都不是瓶颈；瓶颈是 CPU NV12→RGBA（720p 2.52 ms）与整帧上传。1080p 像素量为 2.25×，估算 convert 5.5–8 ms + 8.3 MB 上传，总计约 13–15 ms，逼近 16.67 ms 帧预算，因此 **720p 是刻意选择的默认档**；要上 1080p 需把转换/上传改成 GLES2 双平面 shader 零拷贝（后续专项）。

## 8. 真机验收（用户 m39477）

用户 MTP 安装后直接真机测试：OP 正常播放无卡顿、手柄映射符合预期（A 确认 / B 返回 / 右摇杆光标 / 左摇杆滚轮 / PLUS 存档 / MINUS 退出）、退出干净。按 m39029 的口径，「打包即能玩」⇒ **GalNX 对 FVP 引擎的适配达到 stable**。

## 9. 未验证 / 限制

- 汉化仅覆盖本作自带补丁的文本与图像；OP 中文歌词未做字幕化（本作 OP 无中文歌词需求）。
- 存档走 rfvp 自身存档（`sdmc:/switch/rfvp/saves`），未验证与 PC 版存档互通。
- 图标封面来自 OP 截帧，非官方 key art。
- `01.wmv` 仍随包保留（作为 P40 的 WMV2 回退路径），因此 NSP 比纯 H.264 版大约 227 MB。
