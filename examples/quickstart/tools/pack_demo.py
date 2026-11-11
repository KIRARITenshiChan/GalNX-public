#!/usr/bin/env python3
"""Deterministically pack a directory into out/demo.pak.

This is the "build tool" of the quickstart example: it stands in for a real
devkitPro/Rust build so the manifest -> CLI -> cache loop can be exercised on a
clean machine that only has Python.

Container format (all integers big-endian, little-endian-free):

    magic  8 bytes   b"GALNXPK1"
    count  u32       number of files
    entry  ...       repeated count times, sorted by POSIX relative path:
                       name_len u16 | name (utf-8) | size u64
                       | sha256 (32 bytes) | payload (size bytes)
"""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

MAGIC = b"GALNXPK1"
OUTPUT = Path("out/demo.pak")


def collect(root: Path) -> list[tuple[str, bytes]]:
    """Return (relative POSIX path, payload) pairs in deterministic order."""
    pairs: list[tuple[str, bytes]] = []
    for path in root.rglob("*"):
        if path.is_file():
            pairs.append((path.relative_to(root).as_posix(), path.read_bytes()))
    pairs.sort(key=lambda item: item[0])
    return pairs


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: pack_demo.py CONTENT_DIR", file=sys.stderr)
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print("content directory not found: %s" % root, file=sys.stderr)
        return 2
    files = collect(root)
    blob = bytearray(MAGIC)
    blob += struct.pack(">I", len(files))
    for name, payload in files:
        encoded = name.encode("utf-8")
        blob += struct.pack(">H", len(encoded)) + encoded
        blob += struct.pack(">Q", len(payload))
        blob += hashlib.sha256(payload).digest()
        blob += payload
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(bytes(blob))
    print("packed %d file(s) into %s (%d bytes)" % (len(files), OUTPUT, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
