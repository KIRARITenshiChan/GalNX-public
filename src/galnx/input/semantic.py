"""Semantic input actions, button combos and binding conflict checks.

This module is the pure data-model layer of the GalNX input stack. It knows
nothing about an operating system, SDL or a running game: it names the
semantic actions a visual-novel runtime understands, parses Switch button
combos and keeps the bidirectional button <-> semantic mapping used by input
profiles.

Physical button names follow libnx HID naming (HID_BUTTON_A without the
prefix). Contexts are a deliberate part of the model: a visual novel routinely
uses the same button to advance text and to confirm a choice, so the same
button may carry different actions in different contexts. Only two bindings
inside the same context are a hard conflict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

# libnx HID button names, uppercase and without the HID_BUTTON_ prefix.
SWITCH_BUTTONS: tuple[str, ...] = (
    "A", "B", "X", "Y",
    "L", "R", "ZL", "ZR",
    "PLUS", "MINUS", "HOME", "CAPTURE",
    "DUP", "DDOWN", "DLEFT", "DRIGHT",
    "LSTICK", "RSTICK",
    "LUP", "LDOWN", "LLEFT", "LRIGHT",
    "RUP", "RDOWN", "RLEFT", "RRIGHT",
    "SL", "SR",
)
SWITCH_BUTTON_SET = frozenset(SWITCH_BUTTONS)
BUTTON_ALIASES = {"+": "PLUS", "-": "MINUS"}

ENGINE_EVENT_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")

# Input contexts. The same button may mean different things in different
# contexts; only collisions inside one context are ambiguous for the runtime.
CONTEXT_TEXT = "text"
CONTEXT_CHOICE = "choice"
CONTEXT_MENU = "menu"


class SemanticAction(str, Enum):
    """Actions the input layer emits after mode-specific translation."""

    ADVANCE_TEXT = "advance_text"
    CONFIRM_CHOICE = "confirm_choice"
    BACK = "back"
    OPEN_MENU = "open_menu"
    SHOW_HISTORY = "show_history"
    AUTO_MODE = "auto_mode"
    SKIP_HOLD = "skip_hold"


ACTION_CONTEXT: dict[SemanticAction, str] = {
    SemanticAction.ADVANCE_TEXT: CONTEXT_TEXT,
    SemanticAction.CONFIRM_CHOICE: CONTEXT_CHOICE,
    SemanticAction.BACK: CONTEXT_MENU,
    SemanticAction.OPEN_MENU: CONTEXT_MENU,
    SemanticAction.SHOW_HISTORY: CONTEXT_MENU,
    SemanticAction.AUTO_MODE: CONTEXT_TEXT,
    SemanticAction.SKIP_HOLD: CONTEXT_TEXT,
}


class HotkeyAction(str, Enum):
    """Combos the input layer intercepts before forwarding input to the game."""

    TOGGLE_MODE = "toggle_mode"
    SOFT_RESET = "soft_reset"


class MouseFunction(str, Enum):
    """Virtual mouse functions a keyboard/mouse profile can drive."""

    POINTER = "pointer"
    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"
    MIDDLE_CLICK = "middle_click"
    WHEEL_UP = "wheel_up"
    WHEEL_DOWN = "wheel_down"


def parse_action(value: str | SemanticAction) -> SemanticAction:
    """Return a SemanticAction from its wire name or enum value."""
    if isinstance(value, SemanticAction):
        return value
    try:
        return SemanticAction(str(value).strip())
    except ValueError:
        known = ", ".join(action.value for action in SemanticAction)
        raise ValueError("unknown semantic action %r (known: %s)" % (value, known)) from None


def parse_button(value: str) -> str:
    """Normalise one Switch button name (accepts lowercase, +, -)."""
    if not isinstance(value, str):
        raise ValueError("Switch button must be a string, got %r" % (value,))
    token = value.strip().upper()
    token = BUTTON_ALIASES.get(token, token)
    if token not in SWITCH_BUTTON_SET:
        raise ValueError("unknown Switch button %r (expected one of: %s)" % (value, ", ".join(SWITCH_BUTTONS)))
    return token


def parse_engine_event(value: str) -> str:
    """Validate an adapter-level event name such as RETURN, LCTRL or MOUSE_LEFT.

    The set of engine events is intentionally open: adapters translate semantic
    actions into whatever keyboard/mouse/gamepad events their engine expects,
    so the model only enforces an upper-case token convention.
    """
    if not isinstance(value, str):
        raise ValueError("engine event must be a string, got %r" % (value,))
    token = value.strip().upper()
    if not ENGINE_EVENT_RE.match(token):
        raise ValueError("invalid engine event %r (expected upper-case A-Z, 0-9 and _)" % (value,))
    return token


def parse_combo(value: str | Sequence[str], *, min_buttons: int = 1) -> tuple[str, ...]:
    """Parse a hotkey combo such as "L+R+PLUS" or ["L", "R", "PLUS"].

    Returns canonical upper-case button names in the given order.
    """
    if isinstance(value, str):
        raw = value.split("+")
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        raw = list(value)
    else:
        raise ValueError("hotkey combo must be a string like L+R+PLUS or a list of buttons, got %r" % (value,))
    if not raw:
        raise ValueError("hotkey combo is empty")
    buttons: list[str] = []
    for part in raw:
        if not isinstance(part, str):
            raise ValueError("hotkey combo items must be strings, got %r" % (part,))
        button = parse_button(part)
        if button in buttons:
            raise ValueError("hotkey combo repeats button %s: %s" % (button, format_combo(tuple(buttons))))
        buttons.append(button)
    if len(buttons) < min_buttons:
        raise ValueError("hotkey combo needs at least %d buttons, got %d" % (min_buttons, len(buttons)))
    return tuple(buttons)


def format_combo(combo: Sequence[str]) -> str:
    """Render a button tuple back to its canonical "L+R+PLUS" form."""
    return "+".join(combo)


@dataclass(frozen=True)
class InputConflict:
    """One configuration problem found by find_conflicts()."""

    severity: str
    code: str
    message: str

    def __post_init__(self) -> None:
        if self.severity not in ("error", "warning"):
            raise ValueError("conflict severity must be 'error' or 'warning', got %r" % (self.severity,))

    @property
    def is_error(self) -> bool:
        return self.severity == "error"

    def to_json(self) -> dict[str, str]:
        return {"severity": self.severity, "code": self.code, "message": self.message}


class KeyBindings:
    """Bidirectional Switch button <-> semantic action mapping.

    A button may appear under several actions (cross-context multiplexing,
    e.g. A advances text and confirms a choice). buttons_for()/actions_for()
    expose both directions; context_conflicts() reports buttons that would be
    ambiguous inside a single context.
    """

    def __init__(self) -> None:
        self._by_button: dict[str, list[SemanticAction]] = {}
        self._by_action: dict[SemanticAction, list[str]] = {}
        self.duplicates: list[tuple[str, SemanticAction]] = []

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str | Sequence[str]]) -> KeyBindings:
        bindings = cls()
        for action_value, buttons in mapping.items():
            action = parse_action(action_value)
            if isinstance(buttons, str):
                buttons = (buttons,)
            for button in buttons:
                bindings.bind(button, action)
        return bindings

    def bind(self, button: str, action: str | SemanticAction) -> bool:
        canonical = parse_button(button)
        semantic = parse_action(action)
        current = self._by_button.get(canonical, [])
        if semantic in current:
            self.duplicates.append((canonical, semantic))
            return False
        current.append(semantic)
        self._by_button[canonical] = current
        self._by_action.setdefault(semantic, []).append(canonical)
        return True

    def __len__(self) -> int:
        return len(self._by_action)

    def actions_for(self, button: str) -> tuple[SemanticAction, ...]:
        return tuple(self._by_button.get(parse_button(button), ()))

    def buttons_for(self, action: str | SemanticAction) -> tuple[str, ...]:
        return tuple(self._by_action.get(parse_action(action), ()))

    def resolve(self, button: str) -> SemanticAction:
        """Return the only semantic action bound to a button."""
        actions = self.actions_for(button)
        if not actions:
            raise KeyError("button %s is not bound to any semantic action" % parse_button(button))
        if len(actions) > 1:
            names = ", ".join(action.value for action in actions)
            raise ValueError("button %s is ambiguous (%s); use context-conflict resolution" % (parse_button(button), names))
        return actions[0]

    def as_action_map(self) -> dict[str, tuple[str, ...]]:
        return {action.value: tuple(buttons) for action, buttons in self._by_action.items()}

    def as_button_map(self) -> dict[str, tuple[str, ...]]:
        return {button: tuple(action.value for action in actions) for button, actions in self._by_button.items()}

    def context_conflicts(self) -> dict[str, tuple[SemanticAction, ...]]:
        conflicts: dict[str, tuple[SemanticAction, ...]] = {}
        for button, actions in self._by_button.items():
            by_context: dict[str, list[SemanticAction]] = {}
            for action in actions:
                by_context.setdefault(ACTION_CONTEXT[action], []).append(action)
            ambiguous = [action for actions_in_context in by_context.values() if len(actions_in_context) > 1 for action in actions_in_context]
            if ambiguous:
                conflicts[button] = tuple(ambiguous)
        return conflicts


def find_conflicts(profile: Any) -> list[InputConflict]:
    """Check one input profile for ambiguous or incomplete bindings.

    profile is duck-typed (button_map, hotkeys, adapter_defaults, mouse) so the
    data model stays independent from the profile class that owns it.
    """
    conflicts: list[InputConflict] = []
    bindings = profile.bindings()

    for button, action in bindings.duplicates:
        conflicts.append(InputConflict(
            "error", "button_duplicate",
            "button %s is bound twice to %s in button_map" % (button, action.value),
        ))

    for button, actions in bindings.context_conflicts().items():
        names = ", ".join(action.value for action in actions)
        conflicts.append(InputConflict(
            "error", "button_ambiguous",
            "button %s maps to several actions in one context (%s); the input layer cannot choose a semantic action" % (button, names),
        ))

    for action in SemanticAction:
        if not bindings.buttons_for(action):
            conflicts.append(InputConflict(
                "warning", "action_unmapped",
                "semantic action %s has no Switch button in button_map (controller mode cannot emit it)" % action.value,
            ))

    hotkeys = list(profile.hotkeys.items())
    for index in range(len(hotkeys)):
        for other in range(index + 1, len(hotkeys)):
            name_a, combo_a = hotkeys[index]
            name_b, combo_b = hotkeys[other]
            if combo_a == combo_b:
                conflicts.append(InputConflict(
                    "error", "hotkey_duplicate_combo",
                    "hotkeys %s and %s share the same combo %s" % (name_a, name_b, format_combo(combo_a)),
                ))
            elif set(combo_a) < set(combo_b) or set(combo_b) < set(combo_a):
                conflicts.append(InputConflict(
                    "error", "hotkey_overlap",
                    "hotkey %s (%s) is a button subset of %s (%s); interception would be ambiguous" % (
                        name_a, format_combo(combo_a), name_b, format_combo(combo_b)),
                ))

    for adapter, mapping in profile.adapter_defaults.items():
        by_event: dict[str, list[SemanticAction]] = {}
        for action_value, events in mapping.items():
            semantic = parse_action(action_value)
            for event in events:
                by_event.setdefault(event, []).append(semantic)
        for event, actions in by_event.items():
            by_context: dict[str, list[SemanticAction]] = {}
            for action in actions:
                by_context.setdefault(ACTION_CONTEXT[action], []).append(action)
            ambiguous = [action for grouped in by_context.values() if len(grouped) > 1 for action in grouped]
            if ambiguous:
                names = ", ".join(action.value for action in ambiguous)
                conflicts.append(InputConflict(
                    "error", "adapter_key_ambiguous",
                    "adapter %s: engine event %s maps to several actions in one context (%s)" % (adapter, event, names),
                ))

    if profile.mouse and MouseFunction.POINTER.value not in profile.mouse:
        conflicts.append(InputConflict(
            "warning", "mouse_pointer_missing",
            "mouse mapping has entries but no pointer function; right-stick mouse movement is disabled",
        ))

    return conflicts


def conflict_errors(conflicts: Sequence[InputConflict]) -> list[str]:
    return [conflict.message for conflict in conflicts if conflict.is_error]


def conflict_warnings(conflicts: Sequence[InputConflict]) -> list[str]:
    return [conflict.message for conflict in conflicts if not conflict.is_error]
