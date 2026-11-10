"""GalNX input layer data model (workbench-side configuration only).

This package owns the versionable input configuration model: semantic actions,
Switch button combos, reusable input profiles, and the resolution of the
manifest input section. Runtime injection into a game (the workbench) is NOT
implemented here; the conventions it must follow are documented in
docs/input/README.md.
"""
from __future__ import annotations

from .builtin import BUILTIN_PROFILES, get_builtin, list_builtin_names
from .profiles import (
    DEFAULT_ANALOG,
    PROFILE_SCHEMA_NAME,
    InputProfile,
    InputProfileError,
    ProfileCheck,
    build_validator,
    check_profile_file,
    load_profile,
    profile_from_dict,
    profile_summary,
    read_profile_file,
    validate_profile_data,
)
from .resolve import (
    DEFAULT_MODE,
    DEFAULT_PROFILE,
    DEFAULT_TOGGLE_COMBO,
    MODES,
    ResolvedInput,
    resolve_input,
    resolve_manifest_input,
    validate_manifest_input,
)
from .semantic import (
    ACTION_CONTEXT,
    BUTTON_ALIASES,
    ENGINE_EVENT_RE,
    SWITCH_BUTTONS,
    HotkeyAction,
    InputConflict,
    KeyBindings,
    MouseFunction,
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

__all__ = [
    "ACTION_CONTEXT",
    "BUILTIN_PROFILES",
    "BUTTON_ALIASES",
    "DEFAULT_ANALOG",
    "DEFAULT_MODE",
    "DEFAULT_PROFILE",
    "DEFAULT_TOGGLE_COMBO",
    "ENGINE_EVENT_RE",
    "HotkeyAction",
    "InputConflict",
    "InputProfile",
    "InputProfileError",
    "KeyBindings",
    "MODES",
    "MouseFunction",
    "PROFILE_SCHEMA_NAME",
    "ProfileCheck",
    "ResolvedInput",
    "SWITCH_BUTTONS",
    "SemanticAction",
    "build_validator",
    "check_profile_file",
    "conflict_errors",
    "conflict_warnings",
    "find_conflicts",
    "format_combo",
    "get_builtin",
    "list_builtin_names",
    "load_profile",
    "parse_action",
    "parse_button",
    "parse_combo",
    "parse_engine_event",
    "profile_from_dict",
    "profile_summary",
    "read_profile_file",
    "resolve_input",
    "resolve_manifest_input",
    "validate_manifest_input",
    "validate_profile_data",
]
