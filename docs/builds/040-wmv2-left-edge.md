# 040 — P34：rfvp OP 左缘马赛克修复（WMV2 宏块对齐，v1.1.10-test）

> 后续于 P33（v1.1.9-test）。真机反馈「OP 很流畅，但糊；**最左侧有一列均匀排布的马赛克方格**」——
> 本文件修的是**马赛克列**（缺陷）；「糊」是 480p 上屏拉伸的固有代价，另见 §7。
> 根因在 **rfvp 自带的 WMV2 软解器**：854 宽非 16 对齐，末列宏块写出界后「换行」污染下一行行首。

## 1. 背景

- v1.1.9-test（P33）在真机用 480 档播放 OP：流畅、有声音，但画面很糊（480→1080 拉伸），且**视频区最左侧一列**有均匀排列的马赛克方块。
- 该缺陷在 Citron 上可稳定复现（`docs/milestones/evidence/P33a-op-quality/n03-op-scene.png`），说明不是真机/驱动问题。
- 判定链：源文件干净（ffmpeg）→ Citron 复现（引擎链路）→ 逐列比对定位到**解码器**。

## 2. 诊断

### 2.1 源文件干净

```bash
ffmpeg -v error -i /e/galnx-build/p33/movievar/01_q480.wmv -f rawvideo -pix_fmt yuv420p ff.yuv -y   # 1,770,854,400 B / 2880 帧
python -c "..."   # 第 720 帧（24 fps 的 t=30 s）Y 平面 -> ff720.y（409,920 B）
```

ffmpeg 解出的第 720 帧左缘**没有**马赛克；`01_q480.wmv` = WMV2 **854×480** yuv420p 24 fps。

### 2.2 宿主 oracle 探针

`E:/galnx-build/p33/probe-wmv`：一个独立 cargo 小工程，path 依赖引擎自己的解码 crate
（`wmv-decoder = { path = ".../crates/na_wmv_player", default-features = false, features = ["std-error"] }`，
`[profile.dev] opt-level = 2`），`cargo build --offline` 17.1 s。

- 取第一个 `pts_ms >= 30000` 的帧（= ffmpeg 的 720 帧），打印 `VideoStreamInfo`/尺寸/plane 长度，dump `f480.pgm`（Y 平面）与 `f480.rgba`。
- 实测：`VideoStreamInfo { width: 854, height: 480, codec_four_cc: [87,77,86,50] (WMV2) }`、`y_len=409920`、`cb_len=102480`。

### 2.3 逐列比对：左缘内容来自画面**右端**

把我们的 `f480.pgm` 与 ffmpeg 的 `ff720.y` 逐列求平均 |Δ|：

| 列 | 0 | 4 | 8 | 12 | 16 | 20 | 28 | 32 | 38+ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 均值 \|Δ\| | 81.1 | 82.1 | 70.0 | 22.1 | 21.7 | 20.7 | 20.2 | 20.6 | 2–4 |

overall mean 2.918、`|Δ|>32` 的像素 6,777（1.653%）。

再做「我们的列 → 最接近的 ffmpeg 列」匹配：col0→ff **848–850**、col4→ff **849–850**、col8→ff **718–720**，
col12 起才回到自身。**结论：左缘显示的是画面右端的内容** = 写越界后按 stride 折返到下一行行首；
其余列 20 左右的残差是 P 帧运动补偿从被污染的参考帧向内扩散（84 → 20 → 2 逐列衰减）。

## 3. 根因

`crates/na_wmv_player/src/na_wmv2dsp.rs`：

- `:102` `wmv2_idct_add(dest, dest_off, stride, block)`、`:127` `wmv2_idct_put(...)` 的写循环只判
  `if idx >= dest.len() { continue; }` —— **没有行边界判断**；x 越过 stride 后 idx 落到下一行行首。
- 调用方 `decoder.rs:7404` `wmv2_idct_put(plane, dst_off, stride, &mut block)`，`dst_off = by * stride + bx`；
  `bx/by` 来自 `decoder.rs:1733 block_coords()`：luma `bx = mb_col * 16`（blk 1/3 再 +8），chroma `bx = mb_col * 8`。
- 宏块数 `mb_w = width.div_ceil(16)`（`decoder.rs:3425`）→ 854 得 54 列；`mb_col = 53` 时
  `bx = 848`（写 848..855，溢出 2 列）与 `bx = 856`（8 列全溢出）→ 下一行 x=0..9 被覆盖 = 左侧马赛克列。
- chroma 侧同样溢出：`mb_col*8 = 424`，chroma 宽 427，8 宽块 → 5 列溢出。
- **对照**：同文件 `write_intra_block`(1761) / `write_intra_block_unsigned`(1794) / `write_intra_block_i16`(1836) /
  `add_residual_block_i16`(1867) 都有 `by + r >= ph` 与 `bx + c >= stride` 的守卫 —— 只有 IDCT 两条路径漏了。

## 4. 修法：coded 尺寸解码 + 输出裁剪（照搬同 crate 的 Wmv3/WVC1 模式）

`crates/na_wmv_player/src/api.rs`（**唯一改动文件，5 处**）：

1. `Wmv2Decoder` 增字段 `visible: YuvFrame, display_width: u32, display_height: u32`。
2. `new()`：`coded_width = width.saturating_add(15) / 16 * 16`（854→**864**）、`coded_height` 同理；
   `Wmv2Params::new(coded_width, coded_height)`、`MacroblockDecoder::new(coded, coded)`、`cur = YuvFrame::new(coded)`。
   **坑**：params 必须传 coded 尺寸，否则 `decoder.rs:6395` 的
   `if self.width != params.width ... { *self = MacroblockDecoder::new(params.width, params.height); }` 会把
   `mb_dec` 重置回 854×480，padding 白做。
3. `width()/height()` 返回 display 尺寸。
4. `current_frame()` → `&self.visible`；新增 `fn crop_frame(src, width, height) -> YuvFrame`（Y 逐行截断，
   chroma `cw=width/2`、`ch=height/2`、`src_cw=src.width/2`）。
5. `decode_frame()` 末：`decode_wmv2_frame` 成功后 `self.visible = Self::crop_frame(&self.cur, ...)`，
   返回 `Ok(Some(&self.visible))`。

配套确认：

- 参考帧仍用 coded 尺寸（`self.wmv2_ref = Some(self.cur.clone())`，`decoder.rs:7409`/`:7708`）→ P 帧 MC 在完整宏块面上做，语义正确。
- `mc_luma`（`decoder.rs:1612`）显式接 `src_stride/src_w/src_h` 并 clamp，不依赖帧内长宽。
- `platform/switch/runtime/ffi.rs` 的 `wmv2_decoder_get_frame` 用 `current_frame()` 且 `y_stride=f.width` → 必须拿到 **display 尺寸**帧，本方案正好满足。

## 5. 验证

### 5.1 宿主 oracle（决定性，PASS）

同一帧（pts=30000）与 ffmpeg 参考比较：

| 指标 | 修复前 | **修复后** |
| --- | --- | --- |
| mean \|Δ\|（全帧 Y） | 2.918 | **1.470** |
| `\|Δ\|>32` 像素 | 6,777（1.653%） | **30（0.007%）** |
| 左 12 列均值 \|Δ\| | 63.35 | **3.36**（col0 4.11，col≈20 时 2.3） |
| 右缘 842–853 均值 \|Δ\| | 0.22 | 0.18（无回归） |
| spill 检测（行首被复写） | exact 29 / near 58 行 | **0 / 0** |
| 输出尺寸 | 854×480 | 854×480（裁剪生效，`y_len=409920`） |

### 5.2 Citron NRO（PASS）

- 脚本 `E:/galnx-build/p33/run-fix.sh`（`citron_run.sh --detach`，sdmc `debug.txt=shot=900 + movie=1`、`video.txt=480`、`async=on`）；run dir `E:/galnx-build/p33/run-fix/20261108-014309-rfvp`，`status=loaded`、`nonblack_ratio=0.9018`、0 exception。
- 日志：`Movie: opened (Switch WMV video-only, streaming, P33 quality) name=movie/01_q480.wmv level=2 bytes=38610038`；
  `movie: decoded frame=1 ... 854x480 decode_us=18012 convert_us=5813`，frame 30–210 的 `decode_us=8.1–15.2 ms`、`convert_us=3.4–6.0 ms`（与 P33 基线一致，修复不引入开销）。
- 视觉：`cmp-old-left.png`（P33a 真机/Citron 旧帧左缘裁 140 px 放大 3×）有竖直一列马赛克块；`cmp-new-left.png`（同一区域）是干净天空渐变。
  证据：`docs/milestones/evidence/P34-wmv2-left-edge/`。

### 5.3 NSP v1.1.10-test（verify PASS）

- 产物：`E:/galnx-build/p33/out3/IROSEKA_FHD-010047420000a000.nsp`，9,977,492,696 B
  SHA-256 `fc35fa9880ba9e38db737f2648bfa309b4e54ab0dd2571265af58d7156c4ee1d`；romfs 9,930,029,496 B / 165 项（与 v1.1.9-test 相同，只换 exefs/main）。
- `galnx package nsp verify`（`--manifest examples/pilot02-iroseka.yaml`、显式 `--keyset`）→ **13 checks / 0 fail / 1 warn**（NCA 签名 FAIL = 未签名 homebrew 预期）；PFS0 FileNum 3；Program/Control/Meta 三个 NCA 的 ProgID 均为 `0x010047420000A000`。
- 真机未验；本轮由用户自行安装（设备写操作归用户）。

## 6. 构建与产物

- 构建入口（LTO=fat、codegen-units=1、`-C target-cpu=cortex-a57`）：`E:/galnx-build/p33/build-fix.sh` → 97 s，产物复制到 `/e/galnx-build/p33/lto3/`。
- 增量补丁：`docs/builds/patches/rfvp-switch/rfvp-wmv2-padding.patch`，101 行，SHA-256 `b221b70819a244060ad4dcbd54e33c630d1b49c4937e763cb027a740a51a8c7e`（**唯一文件** `crates/na_wmv_player/src/api.rs`）。
- `rfvp.nro` 8,228,920 B SHA-256 `a80f728977eb3cf38e8b3582e944ff862b31ab086568c649f3090b827e2e3a83`
- `rfvp.elf` 17,421,328 B SHA-256 `c516046b1f81c49c1338c4562c0f06031b4c5d6e1b14202640af7f4e72374cbb`

## 7. 限制与未完成

- **「糊」未修**：480 档只有 854×480，上屏 1080 必糊。建议真机把 `sdmc:/switch/rfvp/video.txt` 改 `540` 或 `720` 做 A/B；
  若 540/720 帧率够则考虑把默认档提上去（决策待真机读数）。
- 只修 WMV2 路径；WMV3/WVC1（`api.rs:180/320`）本来就有 coded 尺寸 + `visible_frame()`。
- 真机未验证（本轮 NSP 由用户安装）。
- 无 romfs 变化（视频素材与 game 目录不动），NSP 大小与 v1.1.9-test 基本一致。

## 8. 复现

```bash
# 1) 宿主 oracle（可选：先看 ffmpeg 参考帧）
cd /e/galnx-build/p33/probe-wmv && cargo build --offline
ffmpeg -v error -i /e/galnx-build/p33/movievar/01_q480.wmv -f rawvideo -pix_fmt yuv420p ff.yuv -y
# 2) 引擎重建（97 s）
env MSYSTEM=MSYS CHERE_INVOKING=1 /d/devkitPro/msys2/usr/bin/bash.exe -lc 'bash /e/galnx-build/p33/build-fix.sh'
# 3) Citron 复现（detach）
bash /e/galnx-build/p33/run-fix.sh /e/galnx-build/p33/lto3/rfvp.nro
# 4) NSP
bash /e/galnx-build/p33/build-nsp-1110.sh
```

## 9. 教训

- **非 16 对齐宽度的视频解码器必须做宏块 padding，再裁剪可见区**；逐点加行守卫容易漏（本 crate 里 4 条写路径有守卫，2 条 IDCT 路径没有）。
- 画面某个边缘出现「内容来自另一端」时，优先怀疑 **stride 溢出换行**，而不是编码/上传/渲染。
- **宿主 oracle**（cargo path 依赖 + ffmpeg rawvideo 参考帧 + 逐列 MAD）比在模拟器截图里目视猜快一个数量级，而且给出可回归的数值。
- 「探针说不成立」要分清检测器本身是否有效：旧的「行尾 10 像素复制」检测对本例无效（溢出字节来自不存在的 x≥854），换成「列身份匹配（our col → 最佳 ff 列）」才定位到右端污染。
