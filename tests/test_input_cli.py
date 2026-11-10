"""Unit tests for the galnx input CLI subcommands."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import cli  # noqa: E402

EXAMPLE_PROFILE = ROOT / "examples" / "input-profile.kb-mouse.yaml"
BUILTIN_NAMES = ["kb_mouse", "generic-vn", "krkrsdl2", "krkr-ns"]


def run_cli(argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = cli.main(argv)
    return exit_code, buffer.getvalue()


class InputListTests(unittest.TestCase):
    def test_list_text_output(self):
        exit_code, output = run_cli(["input", "list"])
        self.assertEqual(exit_code, 0)
        for name in BUILTIN_NAMES:
            self.assertIn(name, output)
        self.assertIn("4 built-in profiles", output)
        self.assertIn("actions=7", output)

    def test_list_json_output(self):
        exit_code, output = run_cli(["input", "list", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["version"], "0.1.0")
        self.assertEqual([item["name"] for item in payload["builtin_profiles"]], BUILTIN_NAMES)
        kb_mouse = payload["builtin_profiles"][0]
        for key in ("description", "button_map", "hotkeys", "mouse", "analog", "conflicts"):
            self.assertIn(key, kb_mouse)
        self.assertEqual(kb_mouse["conflicts"], [])


class InputValidateTests(unittest.TestCase):
    def test_validate_example_profile(self):
        exit_code, output = run_cli(["input", "validate", str(EXAMPLE_PROFILE)])
        self.assertEqual(exit_code, 0)
        self.assertIn("profile.result", output)
        self.assertIn("valid input profile", output)
        self.assertIn("0 fail", output)

    def test_validate_json(self):
        exit_code, output = run_cli(["input", "validate", "--json", str(EXAMPLE_PROFILE)])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["name"], "kb_mouse")
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["warnings"], [])

    def test_invalid_profile_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text("name: bad\nbutton_map:\n  advance_text: [NOPE]\n", encoding="utf-8")
            exit_code, output = run_cli(["input", "validate", str(path)])
            self.assertEqual(exit_code, 2)
            self.assertIn("[FAIL]", output)

    def test_invalid_profile_json_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text("name: [unclosed", encoding="utf-8")
            exit_code, output = run_cli(["input", "validate", "--json", str(path)])
            self.assertEqual(exit_code, 2)
            payload = json.loads(output)
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["errors"])
            self.assertIn("parse error", payload["errors"][0])

    def test_missing_profile_returns_two(self):
        exit_code, output = run_cli(["input", "validate", str(ROOT / "examples" / "nope.yaml")])
        self.assertEqual(exit_code, 2)
        self.assertIn("[FAIL]", output)
        self.assertIn("not found", output)


if __name__ == "__main__":
    unittest.main()
