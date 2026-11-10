"""Input profile data model: YAML load, validation and normalisation.

An input profile is a portable, versionable description of how a device (or a
specific engine) maps physical inputs onto GalNX semantic actions. The format
is defined by schemas/input-profile.schema.json; this module turns that YAML
into a frozen InputProfile, validates it against the schema and reports the
ambiguities found by galnx.input.semantic.find_conflicts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator

from ..paths import schema_path
from .semantic import (
    HotkeyAction,
    InputConflict,
    KeyBindings,
    MouseFunction,
    conflict_errors,
    conflict_warnings,
    find_conflicts,
    format_combo,
    parse_action,
    parse_button,
    parse_combo,
    parse_engine_event,
)

PROFILE_SCHEMA_NAME = "input-profile.schema.json"

DEFAULT_ANALOG: dict[str, Any] = {
    "deadzone": 0.25,
    "pointer_speed": 1.0,
    "invert_y": False,
}


class InputProfileError(ValueError):
    """Raised when an input profile cannot be loaded or is semantically invalid."""


def load_schema(name: str = PROFILE_SCHEMA_NAME) -> dict[str, Any]:
    path = schema_path(name)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_validator(name: str = PROFILE_SCHEMA_NAME) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_profile_data(data: Any, name: str = PROFILE_SCHEMA_NAME) -> list[str]:
    """Return schema violations as readable "field: message" strings."""
    errors: list[str] = []
    for error in build_validator(name).iter_errors(data):
        location = "/".join(str(part) for part in error.absolute_path) or "profile"
        errors.append("%s: %s" % (location, error.message))
    return errors


def read_profile_file(path: str | Path) -> dict[str, Any]:
    """Read one YAML profile file, raising InputProfileError on any problem."""
    profile_path = Path(path)
    if not profile_path.exists():
        raise InputProfileError("input profile not found: %s" % profile_path)
    try:
        text = profile_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputProfileError("cannot read input profile %s: %s" % (profile_path, exc)) from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InputProfileError("input profile parse error in %s: %s" % (profile_path, exc)) from None
    if data is None:
        raise InputProfileError("input profile is empty: %s" % profile_path)
    if not isinstance(data, dict):
        raise InputProfileError("input profile must be a YAML mapping, got %s: %s" % (type(data).__name__, profile_path))
    return data


@dataclass(frozen=True)
class InputProfile:
    """A validated input profile.

    button_map: semantic action -> physical Switch buttons
    adapter_defaults: adapter name -> semantic action -> engine event names
    hotkeys: hotkey action (toggle_mode / soft_reset) -> button combo
    mouse: mouse function -> physical button (keyboard/mouse simulation only)
    analog: deadzone / pointer_speed / invert_y settings
    """

    name: str
    description: str = ""
    adapter_defaults: dict[str, dict[str, tuple[str, ...]]] = field(default_factory=dict)
    button_map: dict[str, tuple[str, ...]] = field(default_factory=dict)
    hotkeys: dict[str, tuple[str, ...]] = field(default_factory=dict)
    mouse: dict[str, str] = field(default_factory=dict)
    analog: dict[str, Any] = field(default_factory=dict)

    def bindings(self) -> KeyBindings:
        return KeyBindings.from_mapping(self.button_map)

    def conflicts(self) -> list[InputConflict]:
        return find_conflicts(self)

    def errors(self) -> list[str]:
        return conflict_errors(self.conflicts())

    def warnings(self) -> list[str]:
        return conflict_warnings(self.conflicts())

    def is_valid(self) -> bool:
        return not self.errors()

    def adapter_events(self, adapter: str) -> dict[str, tuple[str, ...]]:
        """Engine events for one adapter: generic defaults overlaid by adapter."""
        merged: dict[str, tuple[str, ...]] = dict(self.adapter_defaults.get("generic", {}))
        merged.update(self.adapter_defaults.get(adapter, {}))
        return merged

    def hotkey(self, action: str | HotkeyAction) -> tuple[str, ...] | None:
        key = action.value if isinstance(action, HotkeyAction) else str(action)
        return self.hotkeys.get(key)

    def to_dict(self) -> dict[str, Any]:
        """Canonical JSON-friendly representation (lists instead of tuples)."""
        return {
            "name": self.name,
            "description": self.description,
            "adapter_defaults": {
                adapter: {action: list(events) for action, events in mapping.items()}
                for adapter, mapping in self.adapter_defaults.items()
            },
            "button_map": {action: list(buttons) for action, buttons in self.button_map.items()},
            "hotkeys": {name: format_combo(combo) for name, combo in self.hotkeys.items()},
            "mouse": dict(self.mouse),
            "analog": dict(self.analog),
        }


def _profile_from_data(data: Mapping[str, Any]) -> InputProfile:
    """Parse already schema-validated profile data into an InputProfile."""
    name = str(data.get("name", "")).strip()
    if not name:
        raise InputProfileError("input profile has no name")
    description = str(data.get("description", "")).strip()

    button_map: dict[str, tuple[str, ...]] = {}
    raw_buttons = data.get("button_map") or {}
    if not isinstance(raw_buttons, Mapping):
        raise InputProfileError("button_map must be a mapping")
    for action_value, buttons in raw_buttons.items():
        try:
            action = parse_action(action_value)
            if isinstance(buttons, str):
                buttons = (buttons,)
            button_map[action.value] = tuple(parse_button(button) for button in buttons)
        except ValueError as exc:
            raise InputProfileError("button_map.%s: %s" % (action_value, exc)) from None

    hotkeys: dict[str, tuple[str, ...]] = {}
    raw_hotkeys = data.get("hotkeys") or {}
    if not isinstance(raw_hotkeys, Mapping):
        raise InputProfileError("hotkeys must be a mapping")
    for hotkey_value, combo in raw_hotkeys.items():
        try:
            hotkey = HotkeyAction(hotkey_value)
        except ValueError:
            known = ", ".join(item.value for item in HotkeyAction)
            raise InputProfileError("hotkeys.%s: unknown hotkey (known: %s)" % (hotkey_value, known)) from None
        try:
            hotkeys[hotkey.value] = parse_combo(combo, min_buttons=2)
        except ValueError as exc:
            raise InputProfileError("hotkeys.%s: %s" % (hotkey.value, exc)) from None

    mouse: dict[str, str] = {}
    raw_mouse = data.get("mouse") or {}
    if not isinstance(raw_mouse, Mapping):
        raise InputProfileError("mouse must be a mapping")
    for function_value, button in raw_mouse.items():
        try:
            function = MouseFunction(function_value)
            mouse[function.value] = parse_button(button)
        except ValueError as exc:
            raise InputProfileError("mouse.%s: %s" % (function_value, exc)) from None

    adapter_defaults: dict[str, dict[str, tuple[str, ...]]] = {}
    raw_adapters = data.get("adapter_defaults") or {}
    if not isinstance(raw_adapters, Mapping):
        raise InputProfileError("adapter_defaults must be a mapping")
    for adapter, mapping in raw_adapters.items():
        if not isinstance(mapping, Mapping):
            raise InputProfileError("adapter_defaults.%s must be a mapping" % adapter)
        events_by_action: dict[str, tuple[str, ...]] = {}
        for action_value, events in mapping.items():
            try:
                action = parse_action(action_value)
                if isinstance(events, str):
                    events = (events,)
                events_by_action[action.value] = tuple(parse_engine_event(event) for event in events)
            except ValueError as exc:
                raise InputProfileError("adapter_defaults.%s.%s: %s" % (adapter, action_value, exc)) from None
        adapter_defaults[str(adapter)] = events_by_action

    analog = dict(DEFAULT_ANALOG)
    raw_analog = data.get("analog") or {}
    if not isinstance(raw_analog, Mapping):
        raise InputProfileError("analog must be a mapping")
    for key, value in raw_analog.items():
        if key == "invert_y":
            if not isinstance(value, bool):
                raise InputProfileError("analog.invert_y must be a boolean")
            analog[key] = value
        elif key in ("deadzone", "pointer_speed"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise InputProfileError("analog.%s must be a number" % key)
            analog[key] = float(value)
        else:
            raise InputProfileError("analog.%s: unknown analog setting" % key)

    return InputProfile(
        name=name,
        description=description,
        adapter_defaults=adapter_defaults,
        button_map=button_map,
        hotkeys=hotkeys,
        mouse=mouse,
        analog=analog,
    )


def profile_from_dict(data: Any) -> InputProfile:
    """Validate one profile mapping and return a frozen InputProfile.

    Raises InputProfileError for schema violations and for semantic conflicts
    that would make runtime translation ambiguous.
    """
    errors = validate_profile_data(data)
    if errors:
        raise InputProfileError("invalid input profile: " + "; ".join(errors))
    profile = _profile_from_data(data)
    problems = profile.errors()
    if problems:
        raise InputProfileError("invalid input profile (semantic conflicts): " + "; ".join(problems))
    return profile


def load_profile(path: str | Path) -> InputProfile:
    """Load and fully validate one YAML input profile file."""
    return profile_from_dict(read_profile_file(path))


@dataclass(frozen=True)
class ProfileCheck:
    """Non-throwing result of validating one profile file."""

    path: str
    profile: InputProfile | None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.profile is not None and not self.errors

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ok": self.ok,
            "name": self.profile.name if self.profile else None,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def check_profile_file(path: str | Path) -> ProfileCheck:
    """Validate a profile file without raising; suitable for the CLI."""
    display = str(path)
    try:
        data = read_profile_file(path)
    except InputProfileError as exc:
        return ProfileCheck(display, None, (str(exc),), ())
    errors = validate_profile_data(data)
    if errors:
        return ProfileCheck(display, None, tuple(errors), ())
    try:
        profile = _profile_from_data(data)
    except InputProfileError as exc:
        return ProfileCheck(display, None, (str(exc),), ())
    conflicts = profile.conflicts()
    return ProfileCheck(
        display,
        profile,
        tuple(conflict.message for conflict in conflicts if conflict.is_error),
        tuple(conflict.message for conflict in conflicts if not conflict.is_error),
    )


def profile_summary(profile: InputProfile) -> dict[str, Any]:
    """Compact JSON-friendly description used by 'galnx input list --json'."""
    return {
        "name": profile.name,
        "description": profile.description,
        "button_map": {action: list(buttons) for action, buttons in profile.button_map.items()},
        "hotkeys": {name: format_combo(combo) for name, combo in profile.hotkeys.items()},
        "mouse": dict(profile.mouse),
        "adapter_defaults": sorted(profile.adapter_defaults),
        "analog": dict(profile.analog),
        "conflicts": [conflict.to_json() for conflict in profile.conflicts()],
    }
