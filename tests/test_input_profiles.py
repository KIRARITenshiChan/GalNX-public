"""Unit tests for the input profile data model and YAML loading."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.input.builtin import BUILTIN_PROFILES  # noqa: E402
from galnx.input.profiles import (  # noqa: E402
    DEFAULT_ANALOG,
    InputProfile,
    InputProfileError,
    check_profile_file,
    load_profile,
    profile_from_dict,
    profile_summary,
    read_profile_file,
    validate_profile_data,
)

EXAMPLE = ROOT / "examples" / "input-profile.kb-mouse.yaml"


def write_text_file(directory, name, text):
    path = Path(directory) / name
    path.write_text(text, encoding="utf-8")
    return path


class ExampleProfileTests(unittest.TestCase):
    def test_example_profile_loads(self):
        profile = load_profile(EXAMPLE)
        self.assertEqual(profile.name, "kb_mouse")
        self.assertEqual(len(profile.button_map), 7)
        self.assertEqual(profile.hotkeys["soft_reset"], ("L", "R", "PLUS"))
        self.assertEqual(profile.mouse["pointer"], "RSTICK")
        self.assertEqual(profile.analog, DEFAULT_ANALOG)

    def test_example_matches_builtin_kb_mouse(self):
        profile = load_profile(EXAMPLE)
        self.assertEqual(profile.to_dict(), BUILTIN_PROFILES["kb_mouse"].to_dict())

    def test_example_passes_schema_validation(self):
        self.assertEqual(validate_profile_data(read_profile_file(EXAMPLE)), [])

    def test_load_profile_roundtrip(self):
        profile = load_profile(EXAMPLE)
        again = profile_from_dict(profile.to_dict())
        self.assertEqual(profile, again)


class BuiltinProfileTests(unittest.TestCase):
    def test_all_builtins_are_schema_valid_and_conflict_free(self):
        self.assertEqual(
            tuple(BUILTIN_PROFILES),
            ("kb_mouse", "generic-vn", "krkrsdl2", "krkr-ns"),
        )
        for name, profile in BUILTIN_PROFILES.items():
            with self.subTest(profile=name):
                data = profile.to_dict()
                self.assertEqual(validate_profile_data(data), [])
                self.assertEqual(profile.errors(), [])
                self.assertEqual(profile.warnings(), [])
                self.assertEqual(profile_from_dict(data).to_dict(), data)

    def test_kag3_adapter_events(self):
        kag3 = BUILTIN_PROFILES["krkrsdl2"].adapter_events("krkrsdl2")
        self.assertIn("RETURN", kag3["advance_text"])
        self.assertIn("SPACE", kag3["advance_text"])
        self.assertIn("MOUSE_LEFT", kag3["advance_text"])
        self.assertIn("LCTRL", kag3["skip_hold"])
        self.assertIn("ESCAPE", kag3["open_menu"])
        self.assertEqual(BUILTIN_PROFILES["krkr-ns"].adapter_events("krkr-ns"), kag3)

    def test_generic_events_overlay(self):
        generic = BUILTIN_PROFILES["generic-vn"].adapter_events("generic")
        self.assertIn("PAGEUP", generic["show_history"])
        self.assertEqual(BUILTIN_PROFILES["generic-vn"].adapter_events("unknown"), generic)
        profile = InputProfile(
            name="overlay",
            adapter_defaults={
                "generic": {"advance_text": ("RETURN",)},
                "eng": {"advance_text": ("ENTER",), "back": ("ESCAPE",)},
            },
        )
        merged = profile.adapter_events("eng")
        self.assertEqual(merged["advance_text"], ("ENTER",))
        self.assertEqual(merged["back"], ("ESCAPE",))

    def test_hotkey_accessor(self):
        kb_mouse = BUILTIN_PROFILES["kb_mouse"]
        self.assertEqual(kb_mouse.hotkey("soft_reset"), ("L", "R", "PLUS"))
        self.assertIsNone(kb_mouse.hotkey("toggle_mode"))
        self.assertEqual(kb_mouse.hotkey("toggle_mode") or (), ())

    def test_profile_summary_shape(self):
        summary = profile_summary(BUILTIN_PROFILES["generic-vn"])
        self.assertEqual(summary["name"], "generic-vn")
        self.assertEqual(summary["adapter_defaults"], ["generic"])
        self.assertEqual(summary["conflicts"], [])
        self.assertIn("button_map", summary)
        self.assertIn("hotkeys", summary)


class SchemaValidationTests(unittest.TestCase):
    def assertInvalid(self, data, text=""):
        with self.assertRaises(InputProfileError) as context:
            profile_from_dict(data)
        if text:
            self.assertIn(text, str(context.exception))

    def test_missing_name_is_rejected(self):
        self.assertInvalid({"button_map": {"back": ["B"]}}, "name")

    def test_unknown_top_level_key_is_rejected(self):
        self.assertInvalid({"name": "test", "bogus": 1}, "bogus")

    def test_unknown_action_is_rejected(self):
        self.assertInvalid({"name": "test", "button_map": {"quit": ["A"]}}, "button_map")

    def test_unknown_button_is_rejected(self):
        self.assertInvalid({"name": "test", "button_map": {"back": ["HOME2"]}}, "button_map")

    def test_single_button_hotkey_is_rejected(self):
        self.assertInvalid({"name": "test", "hotkeys": {"toggle_mode": "L"}}, "hotkeys")

    def test_unknown_hotkey_name_is_rejected(self):
        self.assertInvalid({"name": "test", "hotkeys": {"turbo": "L+R"}}, "hotkeys")

    def test_analog_types_are_validated(self):
        self.assertInvalid({"name": "test", "analog": {"invert_y": "yes"}}, "analog")
        self.assertInvalid({"name": "test", "analog": {"deadzone": "high"}}, "analog")
        self.assertInvalid({"name": "test", "analog": {"speed": 2}}, "analog")

    def test_semantic_conflict_is_rejected(self):
        self.assertInvalid(
            {
                "name": "test",
                "button_map": {"advance_text": ["A"], "auto_mode": ["A"]},
            },
            "semantic conflicts",
        )


class FileLoadingTests(unittest.TestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(InputProfileError) as context:
            load_profile(ROOT / "examples" / "missing-profile.yaml")
        self.assertIn("not found", str(context.exception))

    def test_bad_yaml_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_text_file(tmp, "bad.yaml", "name: [unclosed")
            with self.assertRaises(InputProfileError) as context:
                load_profile(path)
            self.assertIn("parse error", str(context.exception))

    def test_empty_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_text_file(tmp, "empty.yaml", "")
            with self.assertRaises(InputProfileError) as context:
                load_profile(path)
            self.assertIn("empty", str(context.exception))

    def test_non_mapping_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_text_file(tmp, "list.yaml", "- A\n- B\n")
            with self.assertRaises(InputProfileError) as context:
                load_profile(path)
            self.assertIn("mapping", str(context.exception))

    def test_check_profile_file_ok(self):
        result = check_profile_file(EXAMPLE)
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, ())
        self.assertEqual(result.warnings, ())
        payload = result.to_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["name"], "kb_mouse")

    def test_check_profile_file_reports_errors_without_raising(self):
        result = check_profile_file(ROOT / "examples" / "does-not-exist.yaml")
        self.assertFalse(result.ok)
        self.assertIsNone(result.profile)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("not found", result.errors[0])

    def test_check_profile_file_semantic_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_text_file(
                tmp,
                "conflict.yaml",
                "name: conflict\nbutton_map:\n  advance_text: [A]\n  auto_mode: [A]\n",
            )
            result = check_profile_file(path)
            self.assertFalse(result.ok)
            self.assertTrue(any("advance_text" in error or "A" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
