"""CLI stdio 编码回归：重定向输出必须是合法 UTF-8（P3-b 发现的 cp936 坑）。"""
from __future__ import annotations

import io
import json
import sys

from galnx import cli


def test_force_utf8_stdio_reconfigures_text_wrapper():
    raw = io.BytesIO()
    wrapper = io.TextIOWrapper(raw, encoding="cp936")
    old = sys.stdout
    try:
        sys.stdout = wrapper
        cli.force_utf8_stdio()
        assert wrapper.encoding.lower().replace("-", "") == "utf8"
        wrapper.write(json.dumps({"note": "中文 note"}, ensure_ascii=False))
        wrapper.flush()
        decoded = raw.getvalue().decode("utf-8")
        assert json.loads(decoded) == {"note": "中文 note"}
    finally:
        sys.stdout = old


def test_force_utf8_stdio_skips_streams_without_reconfigure():
    class Capture:
        encoding = "cp936"

        def write(self, text):
            return len(text)

        def flush(self):
            pass

    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout = Capture()
        sys.stderr = Capture()
        cli.force_utf8_stdio()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
