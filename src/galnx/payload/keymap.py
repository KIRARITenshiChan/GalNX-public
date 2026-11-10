"""KiriKiri2 / K2NX per-game keymap generation (GalNX P3-a).

K2NX reads a per-game preference file named Kirikiroid2Preference.xml from the
game folder. Each <KeyMap key="pad" value="vk"/> entry converts one KiriKiri
pad code (VK_PAD*) into a standard Windows virtual-key code, so the game's
keyboard-driven ADV scripts react to controller input.

Evidence (K2NX source, pilot-01 checkout):
  - VK_PADLEFT=0x1B5(437) ... VK_PAD10=0x1C9(457) live in
    src/core/base/ScriptMgnIntf.cpp:308-320 ("VK_PADXXXX are KIRIKIRI specific").
  - TVPConvertPadKeyCodeToVKCode (CCKeyCodeConv.cpp:191-206) maps libnx
    BUTTON_A to VK_PAD1, B to VK_PAD2, X to VK_PAD4, etc.
  - MainScene.cpp reads the map with IndividualConfigManager::GetKeyMap();
    UsePreferenceAt(folder) loads it from the folder holding the startup xp3.

The pilot-01 golden file is
docs/builds/patches/k2nx-switch/keymap/Kirikiroid2Preference.xml
(1,293 B, sha256 aa4fa8aa...f9543). Its byte copy is the built-in template:
render_with_template() only rewrites the value digits, so the default bindings
reproduce the golden file byte for byte.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .content import PayloadError, sha256_bytes

#: KiriKiri pad codes (ScriptMgnIntf.cpp:308-320).
VK_PADLEFT = 0x1B5
VK_PADUP = 0x1B6
VK_PADRIGHT = 0x1B7
VK_PADDOWN = 0x1B8
VK_PAD1 = 0x1C0
VK_PAD2 = 0x1C1
VK_PAD3 = 0x1C2
VK_PAD4 = 0x1C3
VK_PAD5 = 0x1C4
VK_PAD6 = 0x1C5
VK_PAD7 = 0x1C6
VK_PAD8 = 0x1C7
VK_PAD9 = 0x1C8
VK_PAD10 = 0x1C9

PAD_CODES: tuple[int, ...] = (
    VK_PAD1,
    VK_PAD2,
    VK_PAD3,
    VK_PAD4,
    VK_PAD5,
    VK_PAD6,
    VK_PAD7,
    VK_PAD8,
    VK_PAD9,
    VK_PAD10,
    VK_PADLEFT,
    VK_PADUP,
    VK_PADRIGHT,
    VK_PADDOWN,
)

PAD_NAMES: dict[int, str] = {
    VK_PAD1: "VK_PAD1",
    VK_PAD2: "VK_PAD2",
    VK_PAD3: "VK_PAD3",
    VK_PAD4: "VK_PAD4",
    VK_PAD5: "VK_PAD5",
    VK_PAD6: "VK_PAD6",
    VK_PAD7: "VK_PAD7",
    VK_PAD8: "VK_PAD8",
    VK_PAD9: "VK_PAD9",
    VK_PAD10: "VK_PAD10",
    VK_PADLEFT: "VK_PADLEFT",
    VK_PADUP: "VK_PADUP",
    VK_PADRIGHT: "VK_PADRIGHT",
    VK_PADDOWN: "VK_PADDOWN",
}

#: libnx / K2NX button names mapped to their KiriKiri pad codes
#: (CCKeyCodeConv.cpp:191-206 and the Switch START/SELECT aliases).
BUTTON_PAD_CODES: dict[str, int] = {
    "A": VK_PAD1,
    "B": VK_PAD2,
    "C": VK_PAD3,
    "X": VK_PAD4,
    "Y": VK_PAD5,
    "Z": VK_PAD6,
    "L": VK_PAD7,
    "R": VK_PAD8,
    "LSTICK": VK_PAD9,
    "RSTICK": VK_PAD10,
    "START": VK_PAD9,
    "SELECT": VK_PAD10,
    "PLUS": VK_PAD9,
    "MINUS": VK_PAD10,
    "LEFT": VK_PADLEFT,
    "DLEFT": VK_PADLEFT,
    "UP": VK_PADUP,
    "DUP": VK_PADUP,
    "RIGHT": VK_PADRIGHT,
    "DRIGHT": VK_PADRIGHT,
    "DOWN": VK_PADDOWN,
    "DDOWN": VK_PADDOWN,
    "PAD1": VK_PAD1,
    "PAD2": VK_PAD2,
    "PAD3": VK_PAD3,
    "PAD4": VK_PAD4,
    "PAD5": VK_PAD5,
    "PAD6": VK_PAD6,
    "PAD7": VK_PAD7,
    "PAD8": VK_PAD8,
    "PAD9": VK_PAD9,
    "PAD10": VK_PAD10,
}

#: Standard Windows virtual-key codes used by the pilot keymap.
VK_NAMES: dict[int, str] = {
    0x08: "VK_BACK",
    0x09: "VK_TAB",
    0x0D: "VK_RETURN",
    0x1B: "VK_ESCAPE",
    0x20: "VK_SPACE",
    0x21: "VK_PRIOR",
    0x22: "VK_NEXT",
    0x25: "VK_LEFT",
    0x26: "VK_UP",
    0x27: "VK_RIGHT",
    0x28: "VK_DOWN",
    0x52: "VK_R",
    0xA0: "VK_LSHIFT",
    0xA1: "VK_RSHIFT",
    0xA2: "VK_LCONTROL",
    0xA3: "VK_RCONTROL",
}

#: Keyboard aliases accepted in a payload configuration / keymap binding.
KEY_ALIASES: dict[str, int] = {
    "VK_RETURN": 0x0D,
    "RETURN": 0x0D,
    "ENTER": 0x0D,
    "VK_ESCAPE": 0x1B,
    "ESCAPE": 0x1B,
    "ESC": 0x1B,
    "VK_SPACE": 0x20,
    "SPACE": 0x20,
    "VK_LEFT": 0x25,
    "LEFT": 0x25,
    "VK_UP": 0x26,
    "UP": 0x26,
    "VK_RIGHT": 0x27,
    "RIGHT": 0x27,
    "VK_DOWN": 0x28,
    "DOWN": 0x28,
    "VK_BACK": 0x08,
    "VK_TAB": 0x09,
    "VK_PRIOR": 0x21,
    "PAGEUP": 0x21,
    "VK_NEXT": 0x22,
    "PAGEDOWN": 0x22,
    "VK_R": 0x52,
    "R": 0x52,
    "VK_LSHIFT": 0xA0,
    "VK_LCONTROL": 0xA2,
}

#: Pilot-01 default bindings: A confirms, B backs out, X advances, D-pad moves.
DEFAULT_BINDINGS: tuple[tuple[int, int], ...] = (
    (VK_PAD1, 0x0D),
    (VK_PAD2, 0x1B),
    (VK_PAD4, 0x20),
    (VK_PADLEFT, 0x25),
    (VK_PADUP, 0x26),
    (VK_PADRIGHT, 0x27),
    (VK_PADDOWN, 0x28),
)

#: Golden file recorded by the pilot build (P3-a acceptance input).
GOLDEN_KEYMAP_BYTES = 1293
GOLDEN_KEYMAP_SHA256 = (
    "aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543"
)
GOLDEN_KEYMAP_RELPATH = "docs/builds/patches/k2nx-switch/keymap/Kirikiroid2Preference.xml"

TEMPLATE_PACKAGE = "templates/k2nx/Kirikiroid2Preference.xml"

#: Semantic input actions a keymap profile may declare (galnx.input names).
PROFILE_ACTIONS: tuple[str, ...] = (
    "advance_text",
    "confirm_choice",
    "back",
    "open_menu",
    "show_history",
    "auto_mode",
    "skip_hold",
)

_KEYMAP_LINE = re.compile(
    r'(?P<prefix><KeyMap\s+key=")(?P<key>\d+)(?P<mid>"\s+value=")(?P<value>\d+)(?P<suffix>")'
)


@dataclass(frozen=True)
class Binding:
    """One pad-to-keyboard binding with resolved names."""

    pad: int
    vk: int

    @property
    def pad_name(self) -> str:
        return PAD_NAMES.get(self.pad, "0x%03X" % self.pad)

    @property
    def vk_name(self) -> str:
        return VK_NAMES.get(self.vk, "0x%02X" % self.vk)

    def to_json(self) -> dict:
        return {
            "pad": self.pad,
            "pad_name": self.pad_name,
            "vk": self.vk,
            "vk_name": self.vk_name,
        }


def resolve_pad(value) -> int:
    """Resolve a pad code from int, numeric string, VK_PADn or button name."""
    return _resolve(value, PAD_CODES, BUTTON_PAD_CODES, "pad")


def resolve_vk(value) -> int:
    """Resolve a Windows virtual-key code from int, numeric string or alias."""
    allowed = frozenset(range(0x08, 0xFF))
    code = _resolve(value, allowed, KEY_ALIASES, "vk")
    if not 0x08 <= code <= 0xFE:
        raise PayloadError("keyboard virtual-key code out of range: %r" % (value,))
    return code


def _resolve(value, allowed: Iterable[int], aliases: Mapping[str, int], what: str) -> int:
    if isinstance(value, bool):
        raise PayloadError("keymap %s must not be a boolean" % what)
    if isinstance(value, int):
        code = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise PayloadError("keymap %s must not be empty" % what)
        upper = text.upper()
        if upper.startswith("VK_"):
            upper = upper[3:]
        if upper in aliases:
            code = aliases[upper]
        else:
            try:
                code = int(text, 0)
            except ValueError:
                raise PayloadError("unknown keymap %s %r" % (what, value)) from None
    else:
        raise PayloadError("keymap %s must be int or string, got %r" % (what, type(value)))
    if code not in allowed:
        raise PayloadError("unsupported keymap %s %r" % (what, code))
    return code


def template_path() -> Path:
    return Path(__file__).resolve().parent / TEMPLATE_PACKAGE


def load_template() -> str:
    path = template_path()
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PayloadError("cannot read built-in keymap template %s: %s" % (path, exc)) from None


def parse_keymap(xml: str) -> dict[int, int]:
    """Extract the KeyMap entries of a preference file, in document order."""
    bindings: dict[int, int] = {}
    for match in _KEYMAP_LINE.finditer(xml):
        pad = int(match.group("key"))
        vk = int(match.group("value"))
        if pad in bindings:
            raise PayloadError("duplicate KeyMap pad code %d" % pad)
        bindings[pad] = vk
    return bindings


def normalize_bindings(bindings) -> dict[int, int]:
    """Accept {pad: vk}, [(pad, vk), ...] or {button: vk} and return int keys."""
    if isinstance(bindings, Mapping):
        items = list(bindings.items())
    else:
        items = list(bindings)
    result: dict[int, int] = {}
    for pad_raw, vk_raw in items:
        pad = resolve_pad(pad_raw)
        if pad in result:
            raise PayloadError("duplicate keymap pad binding for %s" % PAD_NAMES[pad])
        result[pad] = resolve_vk(vk_raw)
    if not result:
        raise PayloadError("keymap bindings must not be empty")
    return result


def validate_bindings(bindings: Mapping[int, int]) -> list[str]:
    """Return human-readable problems with a resolved binding map."""
    errors: list[str] = []
    if not bindings:
        return ["keymap bindings must not be empty"]
    seen_vk: dict[int, int] = {}
    for pad, vk in bindings.items():
        if pad not in PAD_CODES:
            errors.append("unsupported pad code %r" % (pad,))
        if not 0x08 <= vk <= 0xFE:
            errors.append("keyboard vk out of range for %s: %r" % (pad, vk))
        if vk in seen_vk:
            errors.append(
                "keymap value %r is bound to both %s and %s"
                % (vk, PAD_NAMES.get(seen_vk[vk], seen_vk[vk]), PAD_NAMES.get(pad, pad))
            )
        else:
            seen_vk[vk] = pad
    return errors


def render_with_template(
    bindings: Mapping[int, int],
    template: str | None = None,
) -> str:
    """Rewrite only the value digits of a preference template.

    Every pad code present in the template must also be present in bindings
    (and vice versa): the template is a byte-pinned golden sample, so a
    mismatch means the caller is using the wrong template.
    """
    text = load_template() if template is None else template
    resolved = normalize_bindings(bindings)
    template_map = parse_keymap(text)
    missing = sorted(set(template_map) - set(resolved))
    unknown = sorted(set(resolved) - set(template_map))
    if missing or unknown:
        problems: list[str] = []
        if missing:
            problems.append(
                "bindings missing pad codes: %s"
                % ", ".join(PAD_NAMES.get(code, str(code)) for code in missing)
            )
        if unknown:
            problems.append(
                "bindings contain pads absent from template: %s"
                % ", ".join(PAD_NAMES.get(code, str(code)) for code in unknown)
            )
        raise PayloadError("keymap template mismatch: " + "; ".join(problems))

    def _replace(match: re.Match) -> str:
        pad = int(match.group("key"))
        return match.group("prefix") + str(pad) + match.group("mid") + str(resolved[pad]) + match.group("suffix")

    return _KEYMAP_LINE.sub(_replace, text)


def render(bindings: Mapping[int, int]) -> str:
    """Generate a preference file from scratch (used for non-pilot layouts)."""
    resolved = normalize_bindings(bindings)
    errors = validate_bindings(resolved)
    if errors:
        raise PayloadError("invalid keymap bindings: " + "; ".join(errors))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!--",
        "  Generated by galnx payload keymap (KiriKiri2 / K2NX per-game preference).",
        "  Pad codes are KiriKiri VK_PAD codes (ScriptMgnIntf.cpp:308-320); values",
        "  are Windows virtual-key codes converted in CCKeyCodeConv.cpp:191-206.",
        "  This file is read by IndividualConfigManager via UsePreferenceAt(folder).",
        "-->",
        "<GlobalPreference>",
    ]
    for pad in sorted(resolved, key=lambda code: (PAD_CODES.index(code) if code in PAD_CODES else 0x1000 + code)):
        vk = resolved[pad]
        lines.append(
            '    <KeyMap key="%d" value="%d"/><!-- %s -> %s -->'
            % (pad, vk, PAD_NAMES.get(pad, str(pad)), VK_NAMES.get(vk, "0x%02X" % vk))
        )
    lines.append("</GlobalPreference>")
    return "\n".join(lines) + "\n"


def default_bindings() -> dict[int, int]:
    return dict(DEFAULT_BINDINGS)


def render_default() -> str:
    """Render the pilot default keymap (reproduces the golden file byte for byte)."""
    return render_with_template(default_bindings())


def verify_golden() -> list[tuple[str, bool, str]]:
    """Check the built-in template against the recorded pilot-01 golden sample."""
    checks: list[tuple[str, bool, str]] = []
    path = template_path()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [("keymap-template", False, "cannot read %s: %s" % (path, exc))]
    checks.append(
        (
            "keymap-template-size",
            len(raw) == GOLDEN_KEYMAP_BYTES,
            "%d B (golden %d B)" % (len(raw), GOLDEN_KEYMAP_BYTES),
        )
    )
    digest = hashlib.sha256(raw).hexdigest()
    checks.append(
        (
            "keymap-template-sha256",
            digest == GOLDEN_KEYMAP_SHA256,
            "%s (golden %s)" % (digest[:16] + "...", GOLDEN_KEYMAP_SHA256[:16] + "..."),
        )
    )
    try:
        rendered = render_default()
    except PayloadError as exc:
        checks.append(("keymap-template-render", False, str(exc)))
        return checks
    rendered_raw = rendered.encode("utf-8")
    checks.append(
        (
            "keymap-default-render",
            rendered_raw == raw,
            "%d B rendered, sha256 %s" % (len(rendered_raw), sha256_bytes(rendered_raw)[:16] + "..."),
        )
    )
    return checks


def profile_alignment(profile) -> list[tuple[str, str, bool, str]]:
    """Report which semantic actions a keymap profile can trigger.

    Returns tuples (action, buttons_text, covered, detail). The keymap binds
    pad codes to keyboard keys, so an action is covered when at least one of
    the buttons the profile assigns to it maps to a bound pad code.
    """
    if profile is None:
        return []
    button_map = getattr(profile, "button_map", None)
    if button_map is None and isinstance(profile, Mapping):
        raw = profile.get("button_map")
        button_map = raw if isinstance(raw, Mapping) else {}
    if not isinstance(button_map, Mapping):
        return []
    resolved = normalize_bindings(default_bindings())
    rows: list[tuple[str, str, bool, str]] = []
    for action in PROFILE_ACTIONS:
        if action not in button_map:
            continue
        raw_buttons = button_map[action]
        if isinstance(raw_buttons, str):
            buttons = [raw_buttons]
        else:
            buttons = list(raw_buttons)
        covered = False
        detail: list[str] = []
        for button in buttons:
            try:
                pad = resolve_pad(button)
            except PayloadError as exc:
                detail.append("%s: %s" % (button, exc))
                continue
            if pad in resolved:
                covered = True
                detail.append("%s -> %s -> %s" % (button, PAD_NAMES[pad], VK_NAMES.get(resolved[pad], resolved[pad])))
            else:
                detail.append("%s -> %s (not bound)" % (button, PAD_NAMES[pad]))
        rows.append(("%s" % action, "+".join(str(item) for item in buttons), covered, "; ".join(detail)))
    return rows


def keymap_sha256(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))
