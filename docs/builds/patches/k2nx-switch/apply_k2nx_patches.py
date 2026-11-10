#!/usr/bin/env python3
"""Apply the GalNX autostart + first-boot payload patch to a Kirikiroid2-NX source tree."""
import sys
from pathlib import Path

WS = Path("E:/galnx-build/pilot-01/k2nx-ws/src")
INC = Path("E:/galnx-build/pilot-01/patches")

autostart = (INC / "galnx_autostart.inc").read_text(encoding="utf-8")
extract = (INC / "galnx_extract.inc").read_text(encoding="utf-8")


def patch_switchutils():
    p = WS / "src/core/environ/switch/SwitchUtils.cpp"
    text = p.read_text(encoding="utf-8")
    if "[GalNX] autostart hook" in text:
        print("SwitchUtils.cpp: already patched")
        return
    anchor = '#include "ConfigManager/LocaleConfigManager.h"\n'
    assert text.count(anchor) == 1, "include anchor not unique"
    text = text.replace(anchor, anchor + '#include "cocos2d/MainScene.h"\n', 1)
    lines = text.split("\n")
    start = next(i for i, l in enumerate(lines) if "void TVPCheckAndSendDumps(" in l)
    body = next(i for i, l in enumerate(lines) if "bool TVPCheckStartupArg() {" in l)
    assert body == start + 1, (start, body)
    end = next(i for i, l in enumerate(lines) if "no launch arguments on Switch (yet)" in l)
    close = end + 1
    assert lines[close].strip() == "}", lines[close]
    new_lines = lines[:start] + autostart.split("\n")[:-1] + lines[close + 1:]
    p.write_text("\n".join(new_lines), encoding="utf-8")
    print("SwitchUtils.cpp: patched (TVPCheckStartupArg autostart)")


def patch_main():
    p = WS / "src/core/environ/switch/main.cpp"
    text = p.read_text(encoding="utf-8")
    if "[GalNX] self-contained game payload" in text:
        print("main.cpp: already patched")
        return
    inc_anchor = '#include "cocos2d/AppDelegate.h"\n'
    assert text.count(inc_anchor) == 1
    text = text.replace(inc_anchor, inc_anchor + "#include <string>\n#include <vector>\n", 1)
    boot_anchor = 'extern "C" void K2SBootMark(const char *stage); // K2SBootLog.cpp\n'
    assert text.count(boot_anchor) == 1
    text = text.replace(boot_anchor, extract + boot_anchor, 1)
    call_anchor = 'K2SBootMark(R_SUCCEEDED(rc0) ? "5 romfs ok" : "5 romfs FAILED");\n'
    assert text.count(call_anchor) == 1
    text = text.replace(call_anchor, call_anchor + '\tGalNX_MaybeExtractGame(); // [GalNX] first-boot payload copy (no-op without romfs:/game_files.txt)\n\tK2SBootMark("5b galnx payload");\n', 1)
    p.write_text(text, encoding="utf-8")
    print("main.cpp: patched (first-boot payload extraction)")


patch_switchutils()
patch_main()
print("DONE")
