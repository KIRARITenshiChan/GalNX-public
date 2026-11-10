"""Resolve the manifest input section against built-in or file profiles.

The manifest stores only references (default_mode / toggle_combo / profile);
this module loads the profile, applies runtime defaults and returns a
ResolvedInput the workbench can consume. It raises InputProfileError with a
readable message so manifest validation can surface exactly which field is
wrong.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .builtin import BUILTIN_PROFILES, get_builtin
from .profiles import InputProfile, InputProfileError, load_profile
from .semantic import format_combo, parse_combo

MODES: tuple[str, ...] = ("keyboard_mouse", "controller", "off")
DEFAULT_MODE = "keyboard_mouse"
DEFAULT_PROFILE = "kb_mouse"
DEFAULT_TOGGLE_COMBO: tuple[str, ...] = parse_combo("L+R+PLUS", min_buttons=2)


@dataclass(frozen=True)
class ResolvedInput:
    """Fully resolved input configuration for one game session."""

    profile: InputProfile
    mode: str
    toggle_combo: tuple[str, ...]
    hotkeys: dict[str, tuple[str, ...]]
    profile_source: str
    warnings: tuple[str, ...] = ()

    def adapter_events(self, adapter: str) -> dict[str, tuple[str, ...]]:
        return self.profile.adapter_events(adapter)

    def to_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "toggle_combo": list(self.toggle_combo),
            "profile": {"name": self.profile.name, "source": self.profile_source},
            "hotkeys": {name: list(combo) for name, combo in self.hotkeys.items()},
            "warnings": list(self.warnings),
        }


def _looks_like_path(reference: str) -> bool:
    normalized = reference.replace(chr(92), "/")
    if "/" in normalized:
        return True
    return normalized.lower().endswith((".yaml", ".yml"))


def resolve_input(section: Any, *, base_dir: str | Path | None = None) -> ResolvedInput:
    """Resolve the manifest input mapping.

    An absent section means the documented defaults: keyboard_mouse mode with
    the built-in kb_mouse profile. profile may be a built-in name or a path to
    a YAML profile file; relative paths resolve against base_dir (the manifest
    directory in practice).
    """
    if section is None:
        section = {}
    if not isinstance(section, Mapping):
        raise InputProfileError("input: must be a mapping, got %s" % type(section).__name__)

    mode = section.get("default_mode", DEFAULT_MODE)
    if not isinstance(mode, str) or mode not in MODES:
        raise InputProfileError(
            "input.default_mode: must be one of %s (got %r)" % (", ".join(MODES), mode)
        )

    warnings: list[str] = []
    raw_profile = section.get("profile")
    if raw_profile is None or (isinstance(raw_profile, str) and not raw_profile.strip()):
        profile = BUILTIN_PROFILES[DEFAULT_PROFILE]
        profile_source = "builtin:" + DEFAULT_PROFILE
    elif not isinstance(raw_profile, str):
        raise InputProfileError(
            "input.profile: must be a string (built-in name or YAML path), got %s"
            % type(raw_profile).__name__
        )
    else:
        reference = raw_profile.strip()
        if _looks_like_path(reference):
            candidate = Path(reference)
            if not candidate.is_absolute() and base_dir is not None:
                candidate = Path(base_dir) / candidate
            try:
                profile = load_profile(candidate)
            except InputProfileError as exc:
                raise InputProfileError("input.profile: %s" % exc) from None
            profile_source = "file:" + str(candidate)
        else:
            found = get_builtin(reference)
            if found is None:
                raise InputProfileError(
                    "input.profile: unknown input profile %r (built-in: %s; or pass a path to a YAML input profile)"
                    % (reference, ", ".join(BUILTIN_PROFILES))
                )
            profile = found
            profile_source = "builtin:" + reference

    raw_combo = section.get("toggle_combo", DEFAULT_TOGGLE_COMBO)
    try:
        toggle_combo = parse_combo(raw_combo, min_buttons=2)
    except ValueError as exc:
        raise InputProfileError("input.toggle_combo: %s" % exc) from None

    hotkeys = dict(profile.hotkeys)
    if "toggle_mode" in hotkeys:
        if hotkeys["toggle_mode"] != toggle_combo:
            warnings.append(
                "input.toggle_combo %s overrides profile %r toggle_mode combo %s"
                % (format_combo(toggle_combo), profile.name, format_combo(hotkeys["toggle_mode"]))
            )
        hotkeys["toggle_mode"] = toggle_combo
    else:
        colliding = [name for name, combo in hotkeys.items() if combo == toggle_combo]
        if colliding:
            warnings.append(
                "profile %r has no toggle_mode hotkey; input.toggle_combo %s collides with %s and is kept only for the mode switch"
                % (profile.name, format_combo(toggle_combo), ", ".join(colliding))
            )

    return ResolvedInput(
        profile=profile,
        mode=mode,
        toggle_combo=toggle_combo,
        hotkeys=hotkeys,
        profile_source=profile_source,
        warnings=tuple(warnings),
    )


def resolve_manifest_input(manifest: Mapping[str, Any], *, base_dir: str | Path | None = None) -> ResolvedInput:
    """Resolve the input section of a manifest mapping."""
    section = manifest.get("input") if isinstance(manifest, Mapping) else None
    return resolve_input(section, base_dir=base_dir)


def validate_manifest_input(section: Any, *, base_dir: str | Path | None = None) -> list[str]:
    """Validate one manifest input section; returns readable errors (empty == ok)."""
    try:
        resolve_input(section, base_dir=base_dir)
    except InputProfileError as exc:
        return [str(exc)]
    return []
