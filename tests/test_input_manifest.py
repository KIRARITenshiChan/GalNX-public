"""Unit tests for manifest input resolution (schema hook + profile references)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import manifest  # noqa: E402
from galnx.input.profiles import InputProfileError  # noqa: E402
from galnx.input.resolve import (  # noqa: E402
    DEFAULT_MODE,
    DEFAULT_PROFILE,
    DEFAULT_TOGGLE_COMBO,
    MODES,
    resolve_input,
    resolve_manifest_input,
    validate_manifest_input,
)

EXAMPLE_MANIFEST = ROOT / "examples" / "manifest.krkr.yaml"

SMALL_PROFILE = "name: custom\nbutton_map:\n  advance_text: [A]\n"


def example_manifest_data():
    data, errors = manifest.load_and_validate(EXAMPLE_MANIFEST)
    assert errors == [], errors
    assert data is not None
    return data


def copy_manifest(data):
    return json.loads(json.dumps(data))


def write_profile(directory, relative, text):
    path = Path(directory) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class ExampleManifestTests(unittest.TestCase):
    def test_example_manifest_is_valid(self):
        data, errors = manifest.load_and_validate(EXAMPLE_MANIFEST)
        self.assertEqual(errors, [])
        self.assertEqual(
            data["input"],
            {
                "default_mode": "keyboard_mouse",
                "toggle_combo": "L+R+PLUS",
                "profile": "generic-vn",
            },
        )

    def test_validate_function_matches_load_and_validate(self):
        data = example_manifest_data()
        self.assertEqual(manifest.validate(data), [])
        self.assertEqual(manifest.validate(data, base_dir=EXAMPLE_MANIFEST.parent), [])

    def test_missing_input_section_is_backward_compatible(self):
        data = copy_manifest(example_manifest_data())
        del data["input"]
        self.assertEqual(manifest.validate(data), [])
        resolved = resolve_manifest_input(data)
        self.assertEqual(resolved.mode, DEFAULT_MODE)
        self.assertEqual(resolved.profile.name, DEFAULT_PROFILE)


class ManifestValidationTests(unittest.TestCase):
    def test_unknown_builtin_profile(self):
        data = copy_manifest(example_manifest_data())
        data["input"]["profile"] = "does-not-exist"
        errors = manifest.validate(data)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("unknown input profile", errors[0])
        self.assertIn("does-not-exist", errors[0])

    def test_bad_default_mode_is_reported_by_schema(self):
        data = copy_manifest(example_manifest_data())
        data["input"]["default_mode"] = "gamepad"
        errors = manifest.validate(data)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith("input/default_mode:"), errors[0])

    def test_toggle_combo_accepts_string_and_list(self):
        data = copy_manifest(example_manifest_data())
        for combo in ("L+R+PLUS", ["L", "R", "PLUS"], ["ZL", "ZR"]):
            with self.subTest(combo=combo):
                data["input"]["toggle_combo"] = combo
                self.assertEqual(manifest.validate(data), [])

    def test_single_button_toggle_combo_is_rejected(self):
        data = copy_manifest(example_manifest_data())
        data["input"]["toggle_combo"] = ["L"]
        errors = manifest.validate(data)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("toggle_combo", errors[0])

    def test_profile_reference_resolves_relative_to_manifest_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, "profiles/custom.yaml", SMALL_PROFILE)
            data = copy_manifest(example_manifest_data())
            data["input"]["profile"] = "profiles/custom.yaml"
            self.assertEqual(manifest.validate(data, base_dir=tmp), [])
            data["input"]["profile"] = "profiles/nope.yaml"
            errors = manifest.validate(data, base_dir=tmp)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn("input profile not found", errors[0])


class ResolveInputTests(unittest.TestCase):
    def test_defaults_when_section_is_absent(self):
        resolved = resolve_input(None)
        self.assertEqual(resolved.mode, DEFAULT_MODE)
        self.assertEqual(resolved.profile.name, DEFAULT_PROFILE)
        self.assertEqual(resolved.profile_source, "builtin:kb_mouse")
        self.assertEqual(resolved.toggle_combo, DEFAULT_TOGGLE_COMBO)
        self.assertEqual(resolved.hotkeys["soft_reset"], DEFAULT_TOGGLE_COMBO)
        self.assertEqual(len(resolved.warnings), 1)
        self.assertIn("collides with soft_reset", resolved.warnings[0])

    def test_builtin_profile_reference(self):
        resolved = resolve_input({"profile": "generic-vn"})
        self.assertEqual(resolved.profile.name, "generic-vn")
        self.assertEqual(resolved.profile_source, "builtin:generic-vn")
        self.assertEqual(resolved.warnings, ())
        self.assertEqual(resolved.hotkeys["toggle_mode"], DEFAULT_TOGGLE_COMBO)

    def test_toggle_override_warns(self):
        resolved = resolve_input({"profile": "krkrsdl2", "toggle_combo": "L+R+MINUS"})
        self.assertEqual(resolved.toggle_combo, ("L", "R", "MINUS"))
        self.assertEqual(resolved.hotkeys["toggle_mode"], ("L", "R", "MINUS"))
        self.assertTrue(any("overrides" in warning for warning in resolved.warnings))

    def test_off_mode_and_modes_constant(self):
        self.assertEqual(MODES, ("keyboard_mouse", "controller", "off"))
        self.assertEqual(resolve_input({"default_mode": "off"}).mode, "off")

    def test_invalid_mode_raises(self):
        with self.assertRaises(InputProfileError) as context:
            resolve_input({"default_mode": "gamepad"})
        self.assertIn("input.default_mode", str(context.exception))

    def test_invalid_combo_raises(self):
        with self.assertRaises(InputProfileError) as context:
            resolve_input({"toggle_combo": "L"})
        self.assertIn("input.toggle_combo", str(context.exception))

    def test_non_mapping_section_raises(self):
        with self.assertRaises(InputProfileError) as context:
            resolve_input(["not", "a", "mapping"])
        self.assertIn("must be a mapping", str(context.exception))

    def test_profile_file_relative_and_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_profile(tmp, "profiles/custom.yaml", SMALL_PROFILE)
            relative = resolve_input({"profile": "profiles/custom.yaml"}, base_dir=tmp)
            self.assertEqual(relative.profile.name, "custom")
            self.assertEqual(relative.profile_source, "file:" + str(path))
            absolute = resolve_input({"profile": str(path)})
            self.assertEqual(absolute.profile.name, "custom")

    def test_missing_profile_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(InputProfileError) as context:
                resolve_input({"profile": "profiles/nope.yaml"}, base_dir=tmp)
            self.assertIn("input.profile", str(context.exception))
            self.assertIn("not found", str(context.exception))

    def test_adapter_events_and_to_json(self):
        resolved = resolve_input({"profile": "krkrsdl2"})
        events = resolved.adapter_events("krkrsdl2")
        self.assertIn("RETURN", events["advance_text"])
        payload = resolved.to_json()
        self.assertEqual(
            set(payload),
            {"mode", "toggle_combo", "profile", "hotkeys", "warnings"},
        )
        self.assertEqual(payload["profile"]["name"], "krkrsdl2")
        self.assertEqual(payload["profile"]["source"], "builtin:krkrsdl2")


class ValidateManifestInputTests(unittest.TestCase):
    def test_none_is_valid(self):
        self.assertEqual(validate_manifest_input(None), [])

    def test_bad_section_returns_readable_error(self):
        errors = validate_manifest_input({"profile": "nope"})
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown input profile", errors[0])


if __name__ == "__main__":
    unittest.main()
