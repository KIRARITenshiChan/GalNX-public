"""Unit tests for the semantic input model: buttons, actions, combos, conflicts."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.input.builtin import BUILTIN_PROFILES  # noqa: E402
from galnx.input.profiles import InputProfile  # noqa: E402
from galnx.input.semantic import (  # noqa: E402
    ACTION_CONTEXT,
    InputConflict,
    KeyBindings,
    MouseFunction,
    SWITCH_BUTTONS,
    SemanticAction,
    conflict_errors,
    conflict_warnings,
    find_conflicts,
    format_combo,
    parse_action,
    parse_button,
    parse_combo,
    parse_engine_event,
)


class SwitchButtonTests(unittest.TestCase):
    def test_button_table_matches_libnx_hid_names(self):
        self.assertEqual(len(SWITCH_BUTTONS), 28)
        for name in ("A", "B", "X", "Y", "L", "R", "ZL", "ZR", "PLUS", "MINUS",
                     "HOME", "CAPTURE", "LSTICK", "RSTICK", "DUP", "SL", "SR", "RUP"):
            self.assertIn(name, SWITCH_BUTTONS)

    def test_parse_button_accepts_aliases_and_lowercase(self):
        self.assertEqual(parse_button("+"), "PLUS")
        self.assertEqual(parse_button("-"), "MINUS")
        self.assertEqual(parse_button("a"), "A")
        self.assertEqual(parse_button(" rstick "), "RSTICK")

    def test_parse_button_rejects_unknown_or_non_string(self):
        for bad in ("HOME2", "", "PLUS_PLUS", "A+B"):
            with self.assertRaises(ValueError):
                parse_button(bad)
        with self.assertRaises(ValueError):
            parse_button(3)

    def test_action_contexts(self):
        self.assertEqual(len(SemanticAction), 7)
        self.assertEqual(ACTION_CONTEXT[SemanticAction.ADVANCE_TEXT], "text")
        self.assertEqual(ACTION_CONTEXT[SemanticAction.CONFIRM_CHOICE], "choice")
        self.assertEqual(ACTION_CONTEXT[SemanticAction.OPEN_MENU], "menu")
        self.assertEqual(ACTION_CONTEXT[SemanticAction.SKIP_HOLD], "text")

    def test_parse_action_accepts_enum_and_string(self):
        self.assertIs(parse_action("back"), SemanticAction.BACK)
        self.assertIs(parse_action(SemanticAction.BACK), SemanticAction.BACK)
        with self.assertRaises(ValueError):
            parse_action("quit_the_game")


class ComboTests(unittest.TestCase):
    def test_parse_combo_string_and_sequence(self):
        self.assertEqual(parse_combo("L+R+PLUS"), ("L", "R", "PLUS"))
        self.assertEqual(parse_combo(["l", "+"]), ("L", "PLUS"))
        self.assertEqual(parse_combo(("L", "R")), ("L", "R"))

    def test_parse_combo_preserves_order_and_formats(self):
        self.assertEqual(format_combo(parse_combo("plus+r+l")), "PLUS+R+L")
        self.assertEqual(format_combo(()), "")

    def test_parse_combo_rejects_bad_input(self):
        for value in ("", "L+L", "L+", "L+NOPE", "NOT_A_BUTTON"):
            with self.assertRaises(ValueError):
                parse_combo(value)
        with self.assertRaises(ValueError):
            parse_combo(123)
        with self.assertRaises(ValueError):
            parse_combo(["L", 3])
        with self.assertRaises(ValueError):
            parse_combo([])

    def test_parse_combo_min_buttons(self):
        self.assertEqual(parse_combo("L", min_buttons=1), ("L",))
        with self.assertRaises(ValueError):
            parse_combo("L", min_buttons=2)

    def test_parse_engine_event_convention(self):
        self.assertEqual(parse_engine_event("return"), "RETURN")
        self.assertEqual(parse_engine_event("mouse_left"), "MOUSE_LEFT")
        self.assertEqual(parse_engine_event("LCTRL"), "LCTRL")
        for bad in ("return!", "9RETURN", "MO USE"):
            with self.assertRaises(ValueError):
                parse_engine_event(bad)


class KeyBindingsTests(unittest.TestCase):
    def test_bidirectional_mapping(self):
        bindings = KeyBindings.from_mapping({
            "advance_text": "A",
            "confirm_choice": ["A"],
            "back": ["B", "MINUS"],
        })
        self.assertEqual(
            bindings.actions_for("a"),
            (SemanticAction.ADVANCE_TEXT, SemanticAction.CONFIRM_CHOICE),
        )
        self.assertEqual(bindings.buttons_for("advance_text"), ("A",))
        self.assertEqual(bindings.buttons_for(SemanticAction.BACK), ("B", "MINUS"))
        self.assertEqual(bindings.as_button_map()["A"], ("advance_text", "confirm_choice"))
        self.assertEqual(len(bindings), 3)

    def test_context_conflicts_allow_cross_context_reuse(self):
        bindings = KeyBindings.from_mapping({"advance_text": "A", "confirm_choice": "A"})
        self.assertEqual(bindings.context_conflicts(), {})

    def test_context_conflicts_detect_same_context_reuse(self):
        bindings = KeyBindings.from_mapping({"advance_text": "A", "auto_mode": "A"})
        conflicts = bindings.context_conflicts()
        self.assertEqual(list(conflicts), ["A"])
        self.assertEqual(
            set(conflicts["A"]),
            {SemanticAction.ADVANCE_TEXT, SemanticAction.AUTO_MODE},
        )

    def test_resolve_single_ambiguous_and_unbound(self):
        single = KeyBindings.from_mapping({"back": "B"})
        self.assertIs(single.resolve("B"), SemanticAction.BACK)
        ambiguous = KeyBindings.from_mapping({"advance_text": "A", "confirm_choice": "A"})
        with self.assertRaises(ValueError):
            ambiguous.resolve("A")
        with self.assertRaises(KeyError):
            single.resolve("A")

    def test_bind_records_duplicates(self):
        bindings = KeyBindings()
        self.assertTrue(bindings.bind("A", "back"))
        self.assertFalse(bindings.bind("a", SemanticAction.BACK))
        self.assertEqual(bindings.duplicates, [("A", SemanticAction.BACK)])


class ConflictTests(unittest.TestCase):
    def test_ambiguous_button_within_one_context_is_an_error(self):
        profile = InputProfile(
            name="t",
            button_map={"advance_text": ("A",), "auto_mode": ("A",)},
        )
        conflicts = find_conflicts(profile)
        self.assertIn("button_ambiguous", {c.code for c in conflicts})
        self.assertTrue(conflict_errors(conflicts))

    def test_cross_context_reuse_produces_no_errors(self):
        profile = InputProfile(
            name="t",
            button_map={"advance_text": ("A",), "confirm_choice": ("A",)},
        )
        self.assertEqual(conflict_errors(find_conflicts(profile)), [])

    def test_hotkey_overlap_and_duplicate(self):
        overlap = InputProfile(
            name="t",
            hotkeys={"toggle_mode": ("L", "R"), "soft_reset": ("L", "R", "PLUS")},
        )
        self.assertIn("hotkey_overlap", {c.code for c in find_conflicts(overlap)})
        duplicate = InputProfile(
            name="t",
            hotkeys={"toggle_mode": ("L", "R"), "soft_reset": ("L", "R")},
        )
        self.assertIn("hotkey_duplicate_combo", {c.code for c in find_conflicts(duplicate)})
        disjoint = InputProfile(
            name="t",
            hotkeys={"toggle_mode": ("L", "R"), "soft_reset": ("L", "R", "PLUS")},
        )
        self.assertNotIn("hotkey_duplicate_combo", {c.code for c in find_conflicts(disjoint)})

    def test_adapter_event_ambiguity_in_one_context(self):
        profile = InputProfile(
            name="t",
            adapter_defaults={
                "eng": {"advance_text": ("RETURN",), "auto_mode": ("RETURN",)},
            },
        )
        self.assertIn("adapter_key_ambiguous", {c.code for c in find_conflicts(profile)})

    def test_unmapped_actions_and_mouse_pointer_are_warnings(self):
        profile = InputProfile(
            name="t",
            button_map={"advance_text": ("A",)},
            mouse={"left_click": "A"},
        )
        conflicts = find_conflicts(profile)
        codes = {c.code for c in conflicts}
        self.assertIn("action_unmapped", codes)
        self.assertIn("mouse_pointer_missing", codes)
        self.assertEqual(conflict_errors(conflicts), [])
        self.assertTrue(conflict_warnings(conflicts))

    def test_conflict_severity_is_validated(self):
        with self.assertRaises(ValueError):
            InputConflict("fatal", "x", "y")
        conflict = InputConflict("warning", "w", "m")
        self.assertFalse(conflict.is_error)
        self.assertEqual(
            conflict.to_json(),
            {"severity": "warning", "code": "w", "message": "m"},
        )

    def test_builtin_profiles_have_no_conflicts(self):
        for name, profile in BUILTIN_PROFILES.items():
            with self.subTest(profile=name):
                self.assertEqual(profile.conflicts(), [])

    def test_mouse_function_names(self):
        self.assertEqual(
            {function.value for function in MouseFunction},
            {"pointer", "left_click", "right_click", "middle_click", "wheel_up", "wheel_down"},
        )


if __name__ == "__main__":
    unittest.main()
