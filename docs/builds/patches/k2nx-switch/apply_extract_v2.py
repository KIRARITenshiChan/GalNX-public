#!/usr/bin/env python3
"""Replace the GalNX payload block in K2NX switch main.cpp with galnx_extract_v2.inc (idempotent)."""
from pathlib import Path

MAIN = Path("E:/galnx-build/pilot-01/k2nx-ws/src/src/core/environ/switch/main.cpp")
INC = Path("E:/galnx-build/pilot-01/patches/galnx_extract_v2.inc")

text = MAIN.read_text(encoding="utf-8")
lines = text.split("\n")
start = next(i for i, l in enumerate(lines) if l.startswith("// ---- [GalNX] self-contained game payload"))
anchor = next(i for i, l in enumerate(lines) if l.startswith('extern "C" void K2SBootMark'))
assert start < anchor, (start, anchor)
new = INC.read_text(encoding="utf-8").split("\n")
if new and new[-1] == "":
    new = new[:-1]
out = lines[:start] + new + [""] + lines[anchor:]
MAIN.write_text("\n".join(out), encoding="utf-8")
print("main.cpp: payload block replaced (v2), lines %d..%d -> %d lines" % (start, anchor, len(new)))
