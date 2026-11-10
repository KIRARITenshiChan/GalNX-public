#!/usr/bin/env bash
set -o pipefail
export CARGO_HOME=D:/Scoop/persist/rustup/.cargo
export RUSTUP_HOME=D:/Scoop/persist/rustup/.rustup
export PATH="/d/Scoop/persist/rustup/.cargo/bin:$PATH"
export HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897
export CARGO_TARGET_DIR=/e/galnx-build/m5-harness-target
export RFVP_HARNESS_GAME=/e/galnx-build/m5-harness-content
export RFVP_HARNESS_FONT=/e/galnx-build/m5-harness-content/default.ttf
export RFVP_HARNESS_OUT=/e/galnx-build/m5-harness-out
export RFVP_HARNESS_FRAMES=${RFVP_HARNESS_FRAMES:-300}
mkdir -p /e/galnx-build/m5-harness-out
# run outside the repo dir so the workspace .cargo/config.toml build-std setting does not leak into the host build
cd /e/galnx-build || exit 9
cargo +nightly-2026-02-01 test --manifest-path /e/galnx-build/m5-rfvp/crates/rfvp/Cargo.toml --lib --release --no-default-features --features no_std no_std_harness -- --nocapture
echo "HARNESS_EXIT=$?"
