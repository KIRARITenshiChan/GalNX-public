"""Built-in input profiles shipped with GalNX.

The profiles are constructed directly instead of being loaded from YAML so
importing the input layer never depends on the schema files being present at
runtime; the test suite validates every built-in profile against
schemas/input-profile.schema.json.

KAG3 event names (RETURN, SPACE, MOUSE_LEFT, MOUSE_RIGHT, LCTRL, ESCAPE,
PAGEUP) follow the M2-b task specification and common KAG3 defaults. They have
NOT been verified key-by-key on real hardware or in Citron.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .profiles import DEFAULT_ANALOG, InputProfile
from .semantic import (
    MouseFunction,
    parse_button,
    parse_combo,
    parse_engine_event,
)

# Physical Switch buttons for visual-novel semantics. A is deliberately bound
# to both advance_text and confirm_choice: the contexts differ, so the input
# layer can disambiguate without a conflict.
_VN_BUTTONS: dict[str, Sequence[str]] = {
    "advance_text": ("A",),
    "confirm_choice": ("A",),
    "back": ("B",),
    "open_menu": ("PLUS", "X"),
    "show_history": ("MINUS", "Y"),
    "auto_mode": ("R",),
    "skip_hold": ("L",),
}

_GENERIC_VN_EVENTS: dict[str, Sequence[str]] = {
    "advance_text": ("RETURN", "SPACE", "MOUSE_LEFT"),
    "confirm_choice": ("RETURN", "MOUSE_LEFT"),
    "back": ("ESCAPE",),
    "open_menu": ("MOUSE_RIGHT",),
    "show_history": ("PAGEUP", "MOUSE_WHEEL_UP"),
    "skip_hold": ("LCTRL",),
}

_KAG3_EVENTS: dict[str, Sequence[str]] = {
    "advance_text": ("RETURN", "SPACE", "MOUSE_LEFT"),
    "confirm_choice": ("RETURN", "MOUSE_LEFT"),
    "back": ("MOUSE_RIGHT",),
    "open_menu": ("ESCAPE",),
    "show_history": ("PAGEUP",),
    "skip_hold": ("LCTRL",),
}

_KB_MOUSE_MOUSE: dict[str, str] = {
    MouseFunction.POINTER.value: "RSTICK",
    MouseFunction.LEFT_CLICK.value: "A",
    MouseFunction.RIGHT_CLICK.value: "B",
    MouseFunction.MIDDLE_CLICK.value: "Y",
    MouseFunction.WHEEL_UP.value: "DUP",
    MouseFunction.WHEEL_DOWN.value: "DDOWN",
}

_TOGGLE_MODE = {"toggle_mode": "L+R+PLUS"}


def _profile(
    *,
    name: str,
    description: str,
    button_map: Mapping[str, Sequence[str]],
    hotkeys: Mapping[str, str],
    mouse: Mapping[str, str],
    adapter_defaults: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    analog: Mapping[str, Any] | None = None,
) -> InputProfile:
    return InputProfile(
        name=name,
        description=description,
        adapter_defaults={
            adapter: {action: tuple(parse_engine_event(event) for event in events) for action, events in mapping.items()}
            for adapter, mapping in (adapter_defaults or {}).items()
        },
        button_map={action: tuple(parse_button(button) for button in buttons) for action, buttons in button_map.items()},
        hotkeys={name_: parse_combo(combo, min_buttons=2) for name_, combo in hotkeys.items()},
        mouse={function: parse_button(button) for function, button in mouse.items()},
        analog=dict(analog or DEFAULT_ANALOG),
    )


BUILTIN_PROFILES: dict[str, InputProfile] = {
    "kb_mouse": _profile(
        name="kb_mouse",
        description=(
            "Keyboard and mouse simulation: right stick moves the pointer, A = left click, "
            "B = back / right click, L+R+PLUS = soft reset."
        ),
        button_map=_VN_BUTTONS,
        hotkeys={"soft_reset": "L+R+PLUS"},
        mouse=_KB_MOUSE_MOUSE,
    ),
    "generic-vn": _profile(
        name="generic-vn",
        description=(
            "Generic visual-novel defaults with a generic adapter event map "
            "(Enter / Space / left click advance, Esc menu, right click menu)."
        ),
        button_map=_VN_BUTTONS,
        hotkeys=_TOGGLE_MODE,
        mouse=_KB_MOUSE_MOUSE,
        adapter_defaults={"generic": _GENERIC_VN_EVENTS},
    ),
    "krkrsdl2": _profile(
        name="krkrsdl2",
        description=(
            "KAG3-style defaults for the krkrsdl2 engine (Enter / Space / left click advance, "
            "Ctrl skip, right click back, Esc menu)."
        ),
        button_map=_VN_BUTTONS,
        hotkeys=_TOGGLE_MODE,
        mouse=_KB_MOUSE_MOUSE,
        adapter_defaults={"krkrsdl2": _KAG3_EVENTS},
    ),
    "krkr-ns": _profile(
        name="krkr-ns",
        description=(
            "KAG3-style defaults for the krkr-ns engine (Enter / Space / left click advance, "
            "Ctrl skip, right click back, Esc menu)."
        ),
        button_map=_VN_BUTTONS,
        hotkeys=_TOGGLE_MODE,
        mouse=_KB_MOUSE_MOUSE,
        adapter_defaults={"krkr-ns": _KAG3_EVENTS},
    ),
}


def get_builtin(name: str) -> InputProfile | None:
    """Return a built-in profile by name, or None."""
    return BUILTIN_PROFILES.get(str(name).strip())


def list_builtin_names() -> tuple[str, ...]:
    """Built-in profile names in declaration order."""
    return tuple(BUILTIN_PROFILES)
