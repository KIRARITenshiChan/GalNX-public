# Rust 工具链记录（rfvp 评估，2026-10-30）

> 目的：M5-a（rfvp Switch target 评估）需要 Rust nightly 工具链。本文记录安装方式、版本、环境变量与回滚方法，供后续复现与清理。

## 1. 为什么需要

- rfvp 的 Switch target 用 Rust + `build-std` 交叉编译（`cargo +nightly-2026-02-01 build ... -Zbuild-std=core,alloc,compiler_builtins`），上游 `platform/consoles/toolchain.env` 把 nightly **pin 在 `nightly-2026-02-01`**（注释：floating nightly 会因 unwinding 等依赖编译失败而破坏构建）。
- 本机原先没有 rustup/cargo，故安装 rustup 后再装 pin 的 toolchain + `rust-src` 组件。

## 2. 安装方式（scoop）

```powershell
scoop install rustup
```

- 安装后 `rustup` / `cargo` / `rustc` shim 在 PATH（`D:/Scoop/shims`）。
- 项目 toolchain（按 rfvp 构建脚本自动安装）：

```bash
rustup toolchain install nightly-2026-02-01 --profile minimal --component rust-src --no-self-update
```

## 3. 实测版本（2026-10-30）

| 组件 | 版本/说明 |
| --- | --- |
| rustup | 1.29.2（scoop） |
| toolchain | `nightly-2026-02-01-x86_64-pc-windows-msvc` |
| rustc | `1.95.0-nightly (905b92696 2026-01-31)` |
| cargo | `1.95.0-nightly (fe2f314ae 2026-01-30)` |
| 组件 | `rust-src`（build-std 必需）、minimal profile（无 docs/clippy） |

## 4. 环境变量（scoop 布局）

```text
CARGO_HOME  = D:/Scoop/persist/rustup/.cargo
RUSTUP_HOME = D:/Scoop/persist/rustup/.rustup
PATH        = D:/Scoop/persist/rustup/.cargo/bin;<原 PATH>
```

- 构建/测试时还需 `HTTP_PROXY` / `HTTPS_PROXY=http://127.0.0.1:7897`（cargo 下载 crates 走代理）。
- 注意：仓库 `rfvp` 根有 `.cargo/config.toml`（含 build-std 设置），在仓库内跑 `cargo test` 会报 `E0152`；host harness 测试必须 `cd` 到仓库外 + `--manifest-path`（见 `docs/builds/008-rfvp-evaluation.md` §5.2）。

## 5. 产物与清理

- rfvp 构建产物：`E:/galnx-build/m5-rfvp/target/rfvp-switch/switch/rfvp.nro`（不入库）；归档副本 `E:/galnx-build/m5-artifacts/rfvp.nro` 1,372,216 B sha256 `4964dda90a45c6aacff9268687438130c16742317d52de7d717087b6f3a930bb`。
- host harness 目标目录：`E:/galnx-build/m5-harness-target`（cargo target）、`E:/galnx-build/m5-harness-out`（帧/日志输出）。
- 如不再需要 Rust：`rustup self uninstall` 或 `scoop uninstall rustup`；`D:/Scoop/persist/rustup` 可手动删除（含 toolchain，约 1–2 GB）。

## 6. 备注

- 本次仅安装 rustup/rust 工具链，未装其他系统级组件。
- rfvp 评估结论为「继续研究（P3 研究项）」，若后续不再研究 Rust 引擎可回收该工具链；保留它不影响其他引擎（krkrsdl2/ONScripter-NX 用 devkitPro C/C++）。

## 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-30 | 初版：M5-a 安装 rustup 1.29.2 + nightly-2026-02-01 + rust-src，记录版本/环境变量/清理方式 |
