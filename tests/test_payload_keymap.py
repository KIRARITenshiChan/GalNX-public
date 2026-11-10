"""Unit tests for galnx.payload.keymap (KiriKiri2 / K2NX per-game keymap)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.input import get_builtin  # noqa: E402
from galnx.payload import keymap  # noqa: E402
from galnx.payload.content import PayloadError  # noqa: E402
from galnx.payload.keymap import (  # noqa: E402
    DEFAULT_BINDINGS,
    GOLDEN_KEYMAP_BYTES,
    GOLDEN_KEYMAP_SHA256,
    PAD_CODES,
    default_bindings,
    keymap_sha256,
    load_template,
    normalize_bindings,
    parse_keymap,
    profile_alignment,
    render,
    render_default,
    render_with_template,
    resolve_pad,
    resolve_vk,
    validate_bindings,
    verify_golden,
)

GOLDEN_RELPATH = ROOT / "docs/builds/patches/k2nx-switch/keymap/Kirikiroid2Preference.xml"

GOLDEN_MAP = {
    448: 13,
    449: 27,
    451: 32,
    437: 37,
    438: 38,
    439: 39,
    440: 40,
}


class ResolvePadTests(unittest.TestCase):
    def test_ints_numeric_strings_and_names(self):
        self.assertEqual(resolve_pad(448), 448)
        self.assertEqual(resolve_pad("448"), 448)
        self.assertEqual(resolve_pad("A"), 448)
        self.assertEqual(resolve_pad("VK_PAD1"), 448)
        self.assertEqual(resolve_pad("PLUS"), 456)
        self.assertEqual(resolve_pad("MINUS"), 457)
        self.assertEqual(resolve_pad("L"), 454)
        self.assertEqual(resolve_pad("R"), 455)
        self.assertEqual(resolve_pad("DLEFT"), 437)
        self.assertEqual(resolve_pad("dleft"), 437)

    def test_rejects_unknown(self):
        for value in ("NOPE", "VK_PAD99", 123, 999, None):
            with self.assertRaises(PayloadError):
                resolve_pad(value)


class ResolveVkTests(unittest.TestCase):
    def test_aliases_and_numbers(self):
        self.assertEqual(resolve_vk(13), 13)
        self.assertEqual(resolve_vk("13"), 13)
        self.assertEqual(resolve_vk("VK_RETURN"), 13)
        self.assertEqual(resolve_vk("RETURN"), 13)
        self.assertEqual(resolve_vk("ENTER"), 13)
        self.assertEqual(resolve_vk("ESC"), 27)
        self.assertEqual(resolve_vk("VK_SPACE"), 32)
        self.assertEqual(resolve_vk("VK_R"), 0x52)
        self.assertEqual(resolve_vk("PAGEDOWN"), 0x22)

    def test_rejects_out_of_range_and_pad_names(self):
        for value in ("VK_PAD1", 0x04, 0xFFFF, "NOPE"):
            with self.assertRaises(PayloadError):
                resolve_vk(value)


class NormalizeBindingsTests(unittest.TestCase):
    def test_mapping_sequence_and_button_names(self):
        self.assertEqual(normalize_bindings({"A": 13, "B": "VK_ESCAPE"}), {448: 13, 449: 27})
        self.assertEqual(normalize_bindings([(448, 13)]), {448: 13})
        self.assertEqual(normalize_bindings({448: 13}), {448: 13})
        self.assertEqual(normalize_bindings({"448": "13"}), {448: 13})

    def test_rejects_empty_and_duplicates(self):
        with self.assertRaises(PayloadError):
            normalize_bindings({})
        with self.assertRaises(PayloadError):
            normalize_bindings([(448, 13), ("A", 27)])


class ValidateBindingsTests(unittest.TestCase):
    def test_defaults_are_valid(self):
        self.assertEqual(validate_bindings(default_bindings()), [])

    def test_detects_duplicate_values_and_ranges(self):
        duplicate = validate_bindings({448: 13, 449: 13})
        self.assertTrue(any("bound to both" in item for item in duplicate))
        out_of_range = validate_bindings({448: 0x04})
        self.assertTrue(any("out of range" in item for item in out_of_range))
        self.assertEqual(validate_bindings({}), ["keymap bindings must not be empty"])


class RenderTests(unittest.TestCase):
    def test_template_is_the_golden_copy(self):
        template = load_template()
        raw = template.encode("utf-8")
        self.assertEqual(len(raw), GOLDEN_KEYMAP_BYTES)
        self.assertEqual(keymap_sha256(template), GOLDEN_KEYMAP_SHA256)
        self.assertTrue(keymap.template_path().is_file())

    def test_default_render_reproduces_golden_bytes(self):
        rendered = render_default()
        self.assertEqual(rendered.encode("utf-8"), load_template().encode("utf-8"))
        self.assertEqual(keymap_sha256(rendered), GOLDEN_KEYMAP_SHA256)

    def test_default_render_equals_render_with_default_bindings(self):
        self.assertEqual(render_with_template(default_bindings()), render_default())

    def test_render_with_custom_values_keeps_template_layout(self):
        changed = dict(default_bindings())
        changed[448] = 0x20
        text = render_with_template(changed)
        self.assertIn('<KeyMap key="448" value="32"/>', text)
        # both values are two digits, so only the digits change: byte length is stable
        self.assertEqual(len(text.encode("utf-8")), len(load_template().encode("utf-8")))
        self.assertEqual(keymap_sha256(text) != GOLDEN_KEYMAP_SHA256, True)

    def test_template_mismatch_raises(self):
        with self.assertRaises(PayloadError):
            render_with_template({448: 13})
        with self.assertRaises(PayloadError):
            render_with_template({448: 13, 449: 27})

    def test_render_from_scratch_round_trips(self):
        bindings = {448: 13, 451: 32, 437: 37}
        text = render(bindings)
        self.assertIn('<GlobalPreference>', text)
        self.assertEqual(parse_keymap(text), bindings)
        self.assertIn("VK_PAD1 -> VK_RETURN", text)

    def test_render_rejects_invalid_bindings(self):
        with self.assertRaises(PayloadError):
            render({448: 13, 449: 13})
        with self.assertRaises(PayloadError):
            render({448: 0x01})


class ParseTemplateTests(unittest.TestCase):
    def test_golden_mapping(self):
        self.assertEqual(parse_keymap(load_template()), GOLDEN_MAP)

    def test_parse_rejects_duplicate_pad(self):
        xml = (
            '<GlobalPreference>\n'
            '    <KeyMap key="448" value="13"/>\n'
            '    <KeyMap key="448" value="27"/>\n'
            "</GlobalPreference>\n"
        )
        with self.assertRaises(PayloadError):
            parse_keymap(xml)


class VerifyGoldenTests(unittest.TestCase):
    def test_all_checks_pass(self):
        checks = verify_golden()
        self.assertEqual(
            [check[0] for check in checks],
            ["keymap-template-size", "keymap-template-sha256", "keymap-default-render"],
        )
        for check_id, ok, detail in checks:
            self.assertTrue(ok, "%s: %s" % (check_id, detail))


class ProfileAlignmentTests(unittest.TestCase):
    def test_generic_vn_covers_return_and_dpad_actions(self):
        rows = profile_alignment(get_builtin("generic-vn"))
        covered = {action for action, _buttons, ok, _detail in rows if ok}
        uncovered = {action for action, _buttons, ok, _detail in rows if not ok}
        self.assertEqual(
            covered, {"advance_text", "confirm_choice", "back", "open_menu"}
        )
        self.assertEqual(uncovered, {"show_history", "auto_mode", "skip_hold"})
        for action, buttons, ok, detail in rows:
            self.assertTrue(buttons, action)
            self.assertTrue(detail, action)

    def test_none_profile_returns_empty(self):
        self.assertEqual(profile_alignment(None), [])

    def test_mapping_profile_is_accepted(self):
        rows = profile_alignment({"button_map": {"advance_text": "A", "back": "B"}})
        self.assertEqual([row[0] for row in rows], ["advance_text", "back"])
        self.assertTrue(all(row[2] for row in rows))


class DefaultBindingsTests(unittest.TestCase):
    def test_defaults_match_recorded_values(self):
        self.assertEqual(dict(DEFAULT_BINDINGS), GOLDEN_MAP)
        self.assertEqual(default_bindings(), GOLDEN_MAP)
        self.assertTrue(set(GOLDEN_MAP) <= set(PAD_CODES))

    def test_golden_repo_file_matches_when_present(self):
        if not GOLDEN_RELPATH.is_file():
            self.skipTest("golden keymap file not present")
        raw = GOLDEN_RELPATH.read_bytes()
        self.assertEqual(len(raw), GOLDEN_KEYMAP_BYTES)
        self.assertEqual(keymap_sha256(raw.decode("utf-8")), GOLDEN_KEYMAP_SHA256)


if __name__ == "__main__":
    unittest.main()
