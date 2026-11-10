# AKASEKA HD（映入红瞳的世界 HD）真机验收记录

> 结论：**真机验收 PASS**（2026-11-10，用户 m39477）。OP 正常播放无卡顿、手柄映射符合预期、退出干净 ⇒ 按用户 m39029 的「打包即能玩 = stable」口径，GalNX 的 FVP（rfvp）适配达到 stable。
> 构建细节见 `docs/builds/050-akaseka-fd-nsp.md`；清单 `examples/pilot04-akaseka.yaml`。

## 1. 包

| 项 | 值 |
| --- | --- |
| 路径（本机） | `E:/galnx-build/p42/out/AKASEKA_HD-010047420000d000.nsp` |
| 大小 / sha256 | 6,676,387,544 B / `569af9fbffad68f9423c14b7072d29e14864dec503d5e6039e96b111f9585732` |
| TitleID / 名称 / 版本 | `010047420000D000` / `AKASEKA HD` / `1.4.0-test` |
| 自包含 | romfs 6,656,764,531 B / 141 文件；SD 卡不需要放任何游戏数据 |
| 安装 | MTP 拷到 SD 卡后用 DBI/Awoo 安装；签名「无效」属未签名自制包预期 |

## 2. 真机验收项（用户口述）

| 验收项 | 结果 |
| --- | --- |
| OP（720p H.264，11 秒白闪起播） | ✅ 正常播放、无卡顿 |
| 手柄映射 | ✅ A 确认 / B 返回 / 右摇杆光标 / 左摇杆滚轮 / PLUS 存档 / MINUS 退出 / R 快进 / ZR 左键 / ZL 右键 |
| 退出 | ✅ 干净退出，无错误框、无崩溃 |
| 汉化 | ✅ 中文标题、中文正文（romfs 内 Sarasa Gothic 字体） |

## 3. 已知限制

- 1080p 未启用：CPU NV12→RGBA + 整帧上传在 1080p 会逼近 16.67 ms 帧预算，720p 为默认档；后续需 GLES2 双平面 shader 零拷贝。
- 存档为 rfvp 自身格式（`sdmc:/switch/rfvp/saves`），未与 PC 版互通。
- 封面为 OP 截帧（`examples/pilot04/icon-256.jpg`），非官方 key art。

## 4. 复现要点（模拟器侧）

1. Citron 没有真 NVDEC：验证 H.264 电影必须放 `sdmc:/switch/rfvp/h264_sw.txt`（强制 CPU 解码），真机不需要也不应存在该文件。
2. 调试播片用 `sdmc:/switch/rfvp/movie_debug.txt` 内容 `movie=1`（裸 `1` 无效）；验证完删除。
3. 首启验证只需 `scripts/citron_run.sh --game <nsp> --no-stage --expect-title AKASEKA`，OP 证据见 `/e/galnx-build/p42/evidence/op3/`。
