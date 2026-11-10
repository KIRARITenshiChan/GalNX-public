# 补丁目录的许可说明

本目录（`docs/builds/patches/`）存放 GalNX 对上游引擎的修改补丁（`*.patch` / `*.diff`）以及生成、回放这些补丁的脚本。

## 适用范围

- **补丁本身是对上游源码的修改**，按上游许可证分发，**不适用**仓库根目录的 MIT：
  - `rfvp-switch/` → xmoezzz/rfvp，MPL-2.0，全文见 [rfvp-switch/LICENSE](rfvp-switch/LICENSE)；
  - `krkrsdl2-switch-emulator/` → krkrsdl2，MIT，全文见 [krkrsdl2-switch-emulator/LICENSE](krkrsdl2-switch-emulator/LICENSE)；
  - `k2nx-switch/`（含顶层 `k2nx-patched-vs-v1.0.1.diff`）→ Erige005/Kirikiroid2-NX（KiriKiri2 血统），
    KiriKiri BSD-style 日文条款（非 SPDX），全文见 [k2nx-switch/LICENSE](k2nx-switch/LICENSE)。
- **本目录里由 GalNX 撰写的辅助脚本与说明**（`apply_*.py`、`*.inc`、`README.md`、keymap XML 等）按仓库根 MIT 许可。

## 为什么每个子目录都放一份 LICENSE

补丁和上游源码是衍生关系。把上游许可原文放在补丁旁边，任何人拿到单个子目录时都能立刻知道适用条款，
也便于再分发时一并携带。上游 LICENSE 保持逐字节原样（哈希见下），不要修改。

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `rfvp-switch/LICENSE` | 16,725 B | `1f256ecad192880510e84ad60474eab7589218784b9a50bc7ceee34c2b91f1d5` |
| `krkrsdl2-switch-emulator/LICENSE` | 1,070 B | `964036d9015b116d961623847ff3b482a2ccf1578f41c2511377c03b8ccfb427` |
| `k2nx-switch/LICENSE` | 44,184 B | `27dd616ec1a5c6db6d65b51c887ff1b2c59633196a840a4523b5ba4af8e0c9a4` |

## 补丁回放

每个子目录的 `README.md` 记录了上游 commit、回放顺序与 roundtrip 校验方式；
构建流程见 `docs/builds/0xx-*.md` 与 [docs/builds/README.md](../README.md)。
