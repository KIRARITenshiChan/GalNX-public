#!/usr/bin/env python3
"""Deterministic demo build step for examples/batch/demo-build.yaml (M6-b).

Reads seed.txt (next to this file) and the GALNX_DEMO_SEED environment
variable, then writes a small deterministic artifact. No network, no
toolchain, no game data: the point is to give "galnx batch build" something
real to execute so cache hits/misses and command logs can be demonstrated.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GalNX M6-b deterministic demo build")
    parser.add_argument(
        "--out", required=True, help="artifact path, relative to the current working directory"
    )
    args = parser.parse_args(argv)
    seed = (HERE / "seed.txt").read_text(encoding="utf-8").strip()
    salt = os.environ.get("GALNX_DEMO_SEED", "")
    payload = "galnx-demo\0" + seed + "\0" + salt
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    out = pathlib.Path(args.out)
    if not out.is_absolute():
        out = pathlib.Path.cwd() / out
    out.parent.mkdir(parents=True, exist_ok=True)
    body = b"GALNX-DEMO\n" + digest.encode("ascii") + b"\n" + seed.encode("utf-8") + b"\n"
    out.write_bytes(body)
    print("wrote %s" % out)
    print("sha256 %s" % hashlib.sha256(body).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
