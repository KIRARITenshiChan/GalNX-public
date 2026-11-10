"""Payload planning for the GalNX workbench (P3-a).

A payload plan answers one question without writing anything: which files must
ship inside the NRO/NSP romfs so the engine can copy them to the SD card on
first run, how large they are, which generated files (keymap, game_files.txt)
are added, and what could go wrong. The materialize step then builds the romfs
tree from that plan.

Layering:
    payload.schema.json  -> structure of the manifest payload section
    PayloadConfig        -> validated + resolved configuration (paths included)
    build_plan()         -> PayloadPlan (files, generated files, checks)
    materialize()        -> romfs/ directory on disk (copy/hardlink/symlink)

The module never builds the engine, never compiles, and never touches game
content beyond stat() (sizes only).
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from ..package.contract import Check, checks_to_dict
from . import content as content_mod
from . import keymap as keymap_mod
from .content import (
    DEFAULT_EXCLUDE,
    DEFAULT_INCLUDE,
    DEFAULT_MANIFEST_NAME,
    FAT32_MAX_FILE,
    WINDOWS_PATH_MAX,
    WINDOWS_PATH_WARN,
    PayloadError,
    PayloadFile,
    parse_game_files,
    render_game_files,
    scan_payload,
    sha256_bytes,
    total_bytes,
)

PAYLOAD_SCHEMA_NAME = "payload.schema.json"

DEFAULT_PAYLOAD_DIR = "game"
DEFAULT_KEYMAP_FILE = "Kirikiroid2Preference.xml"

LINK_MODES: tuple[str, ...] = ("copy", "hardlink", "symlink")
DEFAULT_LINK_MODE = "copy"

PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "version",
        "target",
        "startup",
        "marker",
        "source_dir",
        "ui_dir",
        "include",
        "exclude",
        "keymap",
        "payload_dir",
        "manifest_name",
        "notes",
    }
)

KEYMAP_KEYS: frozenset[str] = frozenset({"profile", "template", "bindings", "file"})


# ---------------------------------------------------------------------------
# schema helpers


def payload_schema_path() -> Path:
    from ..paths import schema_path

    return schema_path(PAYLOAD_SCHEMA_NAME)


def load_payload_schema() -> dict:
    with payload_schema_path().open("r", encoding="utf-8") as fh:
        return json.load(fh)


def payload_validator():
    from jsonschema import Draft202012Validator

    schema = load_payload_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def format_schema_errors(payload: object) -> list[str]:
    errors: list[str] = []
    for error in payload_validator().iter_errors(payload):
        parts = [str(part) for part in error.absolute_path]
        location = "payload" + ("/" + "/".join(parts) if parts else "")
        errors.append("%s: %s" % (location, error.message))
    return errors


def validate_manifest_payload(payload, base_dir: str | Path | None = None) -> list[str]:
    """Validate the optional manifest payload section (empty list == valid).

    Structure is checked against payload.schema.json; when that passes the
    section is resolved into a PayloadConfig (path joins, known input profile,
    template existence). The payload source directory is not required to exist
    at manifest-validation time because manifests are authored before the game
    is staged; build_plan() reports that as a failed check.
    """
    if payload is None:
        return []
    if not isinstance(payload, Mapping):
        return ["payload: must be an object, got %s" % type(payload).__name__]
    errors = format_schema_errors(dict(payload))
    if errors:
        return errors
    try:
        PayloadConfig.from_mapping(payload, base_dir=base_dir)
    except PayloadError as exc:
        return ["payload: %s" % exc]
    return []


# ---------------------------------------------------------------------------
# configuration


def _optional_str(data: Mapping, key: str, what: str = "payload") -> str | None:
    if key not in data or data[key] is None:
        return None
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise PayloadError("%s.%s must be a non-empty string" % (what, key))
    return value


def _required_str(data: Mapping, key: str) -> str:
    value = _optional_str(data, key)
    if value is None:
        raise PayloadError("payload.%s is required" % key)
    return value


def _resolve_path(value: str, base_dir: Path | None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if base_dir is None:
        raise PayloadError(
            "payload path %r is relative but no base directory is known" % value
        )
    return Path(base_dir) / path


def _pattern_list(
    data: Mapping, key: str, default: tuple[str, ...], allow_empty: bool
) -> tuple[str, ...]:
    raw = data.get(key)
    if raw is None:
        return tuple(default)
    if not isinstance(raw, list):
        raise PayloadError("payload.%s must be a list of glob patterns" % key)
    patterns = []
    for item in raw:
        if not isinstance(item, str) or not item:
            raise PayloadError("payload.%s entries must be non-empty strings" % key)
        patterns.append(item)
    if not patterns and not allow_empty:
        raise PayloadError("payload.%s must not be empty" % key)
    return tuple(patterns)


def known_input_profiles() -> list[str]:
    try:
        from ..input import list_builtin_names
    except Exception:  # pragma: no cover - input layer always ships with GalNX
        return []
    return list(list_builtin_names())


def _require_known_profile(name: str) -> None:
    from ..input import get_builtin

    try:
        profile = get_builtin(name)
    except Exception:  # unknown names normally resolve to None, never raise
        profile = None
    if profile is None:
        raise PayloadError(
            "payload.keymap.profile %r is not a built-in input profile (%s)"
            % (name, ", ".join(known_input_profiles()) or "none")
        )


def _validate_keymap_file(name: str) -> None:
    if "/" in name or "\\" in name or name in (".", ".."):
        raise PayloadError(
            "payload.keymap.file must be a file name in the payload root, got %r" % name
        )
    if not name.strip():
        raise PayloadError("payload.keymap.file must not be empty")


def _validate_dir_name(name: str, what: str) -> str:
    try:
        normalised = content_mod.normalize_relpath(name)
    except PayloadError as exc:
        raise PayloadError("payload.%s: %s" % (what, exc)) from None
    return normalised


@dataclass(frozen=True)
class PayloadConfig:
    """Resolved payload section of a game manifest."""

    version: str
    target: str
    startup: str
    marker: str
    source_dir: Path | None = None
    ui_dir: Path | None = None
    include: tuple[str, ...] = DEFAULT_INCLUDE
    exclude: tuple[str, ...] = DEFAULT_EXCLUDE
    keymap_profile: str | None = None
    keymap_template: Path | None = None
    keymap_bindings: Mapping[int, int] | None = None
    keymap_file: str = DEFAULT_KEYMAP_FILE
    payload_dir: str = DEFAULT_PAYLOAD_DIR
    manifest_name: str = DEFAULT_MANIFEST_NAME
    notes: str = ""

    @property
    def keymap_enabled(self) -> bool:
        return self.keymap_profile is not None or self.keymap_bindings is not None

    @classmethod
    def from_mapping(
        cls,
        data: Mapping,
        base_dir: str | Path | None = None,
    ) -> "PayloadConfig":
        if not isinstance(data, Mapping):
            raise PayloadError("payload must be a mapping, got %s" % type(data).__name__)
        unknown = sorted(set(data) - PAYLOAD_KEYS)
        if unknown:
            raise PayloadError("unknown payload fields: %s" % ", ".join(unknown))

        version = _required_str(data, "version")
        target = _required_str(data, "target")
        startup = _required_str(data, "startup")
        marker = _required_str(data, "marker")

        if not target.startswith("/"):
            raise PayloadError(
                "payload.target must be an absolute SD path such as /kirikiri/haruno, got %r"
                % target
            )
        stripped_target = target.rstrip("/")
        if not stripped_target:
            raise PayloadError("payload.target must not be the SD card root")
        if not startup.startswith(stripped_target + "/"):
            raise PayloadError(
                "payload.startup %r must live under payload.target %r" % (startup, target)
            )
        marker_path = marker[5:] if marker.startswith("sdmc:") else marker
        if not marker_path.startswith("/") or not marker_path.strip("/"):
            raise PayloadError(
                "payload.marker must be an absolute SD path, optionally prefixed "
                "with sdmc:, got %r" % marker
            )

        include = _pattern_list(data, "include", DEFAULT_INCLUDE, allow_empty=False)
        exclude = _pattern_list(data, "exclude", DEFAULT_EXCLUDE, allow_empty=True)

        base = Path(base_dir) if base_dir is not None else None
        source_dir = _optional_str(data, "source_dir")
        source_path = _resolve_path(source_dir, base) if source_dir is not None else None
        ui_dir = _optional_str(data, "ui_dir")
        ui_path = _resolve_path(ui_dir, base) if ui_dir is not None else None

        keymap_profile: str | None = None
        keymap_template: Path | None = None
        keymap_bindings: Mapping[int, int] | None = None
        keymap_file = DEFAULT_KEYMAP_FILE
        raw_keymap = data.get("keymap")
        if raw_keymap is not None:
            if isinstance(raw_keymap, str):
                keymap_profile = raw_keymap
            elif isinstance(raw_keymap, Mapping):
                unknown_keys = sorted(set(raw_keymap) - KEYMAP_KEYS)
                if unknown_keys:
                    raise PayloadError(
                        "unknown payload.keymap fields: %s" % ", ".join(unknown_keys)
                    )
                keymap_profile = _optional_str(raw_keymap, "profile", "payload.keymap")
                template_raw = _optional_str(raw_keymap, "template", "payload.keymap")
                if template_raw is not None:
                    keymap_template = _resolve_path(template_raw, base)
                keymap_file = (
                    _optional_str(raw_keymap, "file", "payload.keymap")
                    or DEFAULT_KEYMAP_FILE
                )
                bindings_raw = raw_keymap.get("bindings")
                if bindings_raw is not None:
                    if not isinstance(bindings_raw, Mapping):
                        raise PayloadError("payload.keymap.bindings must be a mapping")
                    keymap_bindings = keymap_mod.normalize_bindings(bindings_raw)
            else:
                raise PayloadError(
                    "payload.keymap must be a profile name or a mapping, got %s"
                    % type(raw_keymap).__name__
                )
        if keymap_profile is not None:
            _require_known_profile(keymap_profile)
        _validate_keymap_file(keymap_file)
        if keymap_template is not None and not keymap_template.is_file():
            raise PayloadError(
                "payload.keymap.template does not exist: %s" % keymap_template
            )

        payload_dir = _validate_dir_name(
            _optional_str(data, "payload_dir") or DEFAULT_PAYLOAD_DIR, "payload_dir"
        )
        manifest_name = _optional_str(data, "manifest_name") or DEFAULT_MANIFEST_NAME
        if "/" in manifest_name or "\\" in manifest_name or manifest_name in (".", ".."):
            raise PayloadError(
                "payload.manifest_name must be a file name in the romfs root, got %r"
                % manifest_name
            )
        notes = _optional_str(data, "notes") or ""

        return cls(
            version=version,
            target=target,
            startup=startup,
            marker=marker,
            source_dir=source_path,
            ui_dir=ui_path,
            include=include,
            exclude=exclude,
            keymap_profile=keymap_profile,
            keymap_template=keymap_template,
            keymap_bindings=keymap_bindings,
            keymap_file=keymap_file,
            payload_dir=payload_dir,
            manifest_name=manifest_name,
            notes=notes,
        )

    def to_json(self) -> dict:
        return {
            "version": self.version,
            "target": self.target,
            "startup": self.startup,
            "marker": self.marker,
            "source_dir": str(self.source_dir) if self.source_dir is not None else None,
            "ui_dir": str(self.ui_dir) if self.ui_dir is not None else None,
            "include": list(self.include),
            "exclude": list(self.exclude),
            "keymap_profile": self.keymap_profile,
            "keymap_template": (
                str(self.keymap_template) if self.keymap_template is not None else None
            ),
            "keymap_bindings": (
                {str(pad): vk for pad, vk in sorted(self.keymap_bindings.items())}
                if self.keymap_bindings is not None
                else None
            ),
            "keymap_file": self.keymap_file,
            "payload_dir": self.payload_dir,
            "manifest_name": self.manifest_name,
            "notes": self.notes,
        }


def load_payload_config(
    data: Mapping, base_dir: str | Path | None = None
) -> PayloadConfig:
    """Resolve a manifest payload section (raises PayloadError on problems)."""
    return PayloadConfig.from_mapping(data, base_dir=base_dir)


# ---------------------------------------------------------------------------
# plan


def _check(
    check_id: str,
    name: str,
    status: str,
    detail: str = "",
    hint: str = "",
) -> Check:
    return Check(id=check_id, name=name, status=status, detail=detail, hint=hint)


@dataclass
class PayloadPlan:
    config: PayloadConfig
    checks: list[Check] = field(default_factory=list)
    files: list[PayloadFile] = field(default_factory=list)
    generated: list[PayloadFile] = field(default_factory=list)
    ui_files: list[PayloadFile] = field(default_factory=list)
    manifest_text: str = ""
    keymap_text: str | None = None
    link_mode: str = DEFAULT_LINK_MODE

    @property
    def all_files(self) -> list[PayloadFile]:
        return list(self.files) + list(self.generated)

    @property
    def payload_bytes(self) -> int:
        return total_bytes(self.all_files)

    @property
    def ui_bytes(self) -> int:
        return total_bytes(self.ui_files)

    @property
    def manifest_bytes(self) -> int:
        return len(self.manifest_text.encode("utf-8"))

    @property
    def romfs_total_bytes(self) -> int:
        return self.payload_bytes + self.ui_bytes + self.manifest_bytes

    def errors(self) -> list[Check]:
        return [check for check in self.checks if check.is_fail]

    def warnings(self) -> list[Check]:
        return [check for check in self.checks if check.status == "warn"]

    def is_ok(self) -> bool:
        return not self.errors()

    def add(self, check: Check) -> Check:
        self.checks.append(check)
        return check

    def to_json(self, include_files: bool = True) -> dict:
        categories: dict[str, int] = {}
        for item in self.all_files:
            categories[item.category] = categories.get(item.category, 0) + 1
        rels = [item.rel for item in self.all_files]
        max_rel = max((len(rel) for rel in rels), default=0)
        device_max = max(
            (len(self.config.target.rstrip("/") + "/" + rel) for rel in rels), default=0
        )
        romfs_max = max(
            (len("romfs:/" + self.config.payload_dir + "/" + rel) for rel in rels),
            default=0,
        )
        manifest: dict | None = None
        if self.manifest_text:
            raw = self.manifest_text.encode("utf-8")
            manifest = {
                "name": self.config.manifest_name,
                "romfs_path": "romfs:/" + self.config.manifest_name,
                "lines": self.manifest_text.count("\n"),
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
            }
        return {
            "config": self.config.to_json(),
            "files": [item.to_json() for item in self.files] if include_files else None,
            "file_count": len(self.files),
            "total_file_count": len(self.all_files),
            "files_bytes": total_bytes(self.files),
            "generated": [item.to_json() for item in self.generated],
            "generated_bytes": total_bytes(self.generated),
            "total_bytes": self.payload_bytes,
            "categories": categories,
            "ui_file_count": len(self.ui_files),
            "ui_bytes": self.ui_bytes,
            "romfs_total_bytes": self.romfs_total_bytes,
            "max_rel_path_length": max_rel,
            "max_device_path_length": device_max,
            "max_romfs_path_length": romfs_max,
            "manifest": manifest,
            "keymap": (
                {
                    "file": self.config.keymap_file,
                    "bytes": len(self.keymap_text.encode("utf-8")),
                    "sha256": sha256_bytes(self.keymap_text.encode("utf-8")),
                }
                if self.keymap_text is not None
                else None
            ),
            "link_mode": self.link_mode,
            "checks": checks_to_dict(self.checks),
            "ok": self.is_ok(),
            "errors": [check.to_dict() for check in self.errors()],
            "warnings": [check.to_dict() for check in self.warnings()],
        }


def _render_keymap(config: PayloadConfig) -> str:
    if config.keymap_bindings is not None:
        bindings = dict(config.keymap_bindings)
        if config.keymap_template is not None:
            template = config.keymap_template.read_text(encoding="utf-8")
            return keymap_mod.render_with_template(bindings, template=template)
        return keymap_mod.render(bindings)
    if config.keymap_template is not None:
        template = config.keymap_template.read_text(encoding="utf-8")
        return keymap_mod.render_with_template(
            keymap_mod.default_bindings(), template=template
        )
    return keymap_mod.render_default()


def _keymap_is_golden(config: PayloadConfig) -> bool:
    if config.keymap_template is not None:
        return False
    if config.keymap_bindings is None:
        return True
    return dict(config.keymap_bindings) == keymap_mod.default_bindings()


def build_plan(
    config: PayloadConfig,
    source_dir: str | Path | None = None,
    ui_dir: str | Path | None = None,
    link_mode: str = DEFAULT_LINK_MODE,
) -> PayloadPlan:
    """Scan the payload source and produce a validated PayloadPlan (never writes)."""
    if link_mode not in LINK_MODES:
        raise PayloadError(
            "unknown link mode %r (choose from %s)" % (link_mode, ", ".join(LINK_MODES))
        )
    plan = PayloadPlan(config=config, link_mode=link_mode)
    plan.add(
        _check(
            "payload-link-mode",
            "romfs link mode",
            "ok",
            "materialize will use %s" % link_mode,
        )
    )

    source = Path(source_dir) if source_dir is not None else config.source_dir
    if source is None:
        plan.add(
            _check(
                "payload-source",
                "payload source directory",
                "fail",
                "payload.source_dir is not configured",
                "Set payload.source_dir in the manifest or pass --source-dir.",
            )
        )
    elif not Path(source).is_dir():
        plan.add(
            _check(
                "payload-source",
                "payload source directory",
                "fail",
                "not a directory: %s" % source,
                "Point payload.source_dir at the read-only game directory.",
            )
        )
    else:
        try:
            plan.files = scan_payload(source, config.include, config.exclude)
        except PayloadError as exc:
            plan.files = []
            plan.add(
                _check(
                    "payload-source",
                    "payload source directory",
                    "fail",
                    str(exc),
                    "Fix the include/exclude globs or the source directory.",
                )
            )
        else:
            plan.add(
                _check(
                    "payload-source",
                    "payload source directory",
                    "ok",
                    str(source),
                )
            )

    plan.add(
        _check(
            "payload-files",
            "payload selection",
            "ok" if plan.files else "fail",
            "%d files, %d bytes" % (len(plan.files), total_bytes(plan.files)),
            "No file matched include; check payload.include and payload.exclude."
            if not plan.files
            else "",
        )
    )

    # --- generated keymap ---------------------------------------------------
    if config.keymap_enabled:
        try:
            plan.keymap_text = _render_keymap(config)
        except PayloadError as exc:
            plan.add(
                _check(
                    "payload-keymap",
                    "generated keymap",
                    "fail",
                    str(exc),
                    "Check payload.keymap profile/bindings/template.",
                )
            )
        else:
            raw = plan.keymap_text.encode("utf-8")
            plan.generated.append(
                PayloadFile(
                    rel=config.keymap_file,
                    size=len(raw),
                    category=content_mod.classify_path(config.keymap_file),
                )
            )
            detail = "%s, %d B, sha256 %s" % (
                config.keymap_file,
                len(raw),
                sha256_bytes(raw),
            )
            plan.add(_check("payload-keymap", "generated keymap", "ok", detail))
            if _keymap_is_golden(config):
                golden = sha256_bytes(raw) == keymap_mod.GOLDEN_KEYMAP_SHA256
                plan.add(
                    _check(
                        "payload-keymap-golden",
                        "keymap matches pilot-01 golden sample",
                        "ok" if golden else "fail",
                        "sha256 %s%s"
                        % (
                            sha256_bytes(raw),
                            ""
                            if golden
                            else " != golden " + keymap_mod.GOLDEN_KEYMAP_SHA256,
                        ),
                        "Restore the built-in template or default bindings."
                        if not golden
                        else "",
                    )
                )
            try:
                profile = (
                    None
                    if config.keymap_profile is None
                    else _load_profile(config.keymap_profile)
                )
            except PayloadError:
                profile = None
            if profile is not None:
                rows = keymap_mod.profile_alignment(profile)
                uncovered = [row for row in rows if not row[2]]
                detail = "; ".join(
                    "%s=%s%s" % (action, buttons, "" if covered else " (unbound)")
                    for action, buttons, covered, _ in rows
                )
                plan.add(
                    _check(
                        "payload-keymap-profile",
                        "keymap vs input profile",
                        "warn" if uncovered else "ok",
                        detail
                        or "profile %r has no mapped actions" % config.keymap_profile,
                        "Unbound actions cannot be triggered from the controller; add "
                        "bindings or use a profile whose buttons are covered."
                        if uncovered
                        else "",
                    )
                )

    # --- manifest text + structural checks ----------------------------------
    target_root = config.target.rstrip("/")
    rels = [item.rel for item in plan.all_files]
    try:
        plan.manifest_text = render_game_files(
            config.version,
            config.target,
            config.startup,
            config.marker,
            plan.all_files,
        )
    except PayloadError as exc:
        plan.add(
            _check(
                "payload-manifest",
                "game_files.txt",
                "fail",
                str(exc),
                "Fix payload.target/startup/marker.",
            )
        )
    else:
        raw = plan.manifest_text.encode("utf-8")
        parsed = parse_game_files(plan.manifest_text)
        lines_ok = (
            parsed["version"] == config.version
            and parsed["target"] == target_root
            and parsed["startup"] == config.startup
            and parsed["marker"] == config.marker
            and parsed["files"] == rels
            and parsed["bytes"] == plan.payload_bytes
        )
        plan.add(
            _check(
                "payload-manifest",
                "game_files.txt",
                "ok" if lines_ok else "fail",
                "%d lines, %d B, sha256 %s"
                % (
                    len(plan.manifest_text.split("\n")) - 1,
                    len(raw),
                    sha256_bytes(raw),
                ),
                "Renderer and parser disagree; report a GalNX bug."
                if not lines_ok
                else "",
            )
        )

        startup_rel = config.startup[len(target_root) + 1:]
        try:
            startup_rel = content_mod.normalize_relpath(startup_rel)
        except PayloadError as exc:
            plan.add(
                _check("payload-startup", "startup file in payload", "fail", str(exc))
            )
        else:
            listed = startup_rel in rels
            plan.add(
                _check(
                    "payload-startup",
                    "startup file in payload",
                    "ok" if listed else "fail",
                    "%s%s"
                    % (
                        startup_rel,
                        "" if listed else " is missing from the selected files",
                    ),
                    "Include the startup archive (usually data.xp3) in payload.include."
                    if not listed
                    else "",
                )
            )

    # case-insensitive duplicates (SD card file systems are case-insensitive)
    folded: dict[str, str] = {}
    collisions: list[str] = []
    for rel in rels:
        key = rel.casefold()
        if key in folded:
            collisions.append("%s vs %s" % (folded[key], rel))
        else:
            folded[key] = rel
    manifest_key = config.manifest_name.casefold()
    if manifest_key in folded:
        collisions.append(
            "%s vs generated %s" % (folded[manifest_key], config.manifest_name)
        )
    plan.add(
        _check(
            "payload-name-collision",
            "case-insensitive name collisions",
            "ok" if not collisions else "fail",
            "%d selected names are unique" % len(rels)
            if not collisions
            else "; ".join(collisions),
            "Rename one of the files; FAT32/exFAT are case-insensitive.",
        )
    )

    # path lengths
    lengths: list[tuple[str, int]] = []
    for rel in rels:
        device = len(target_root + "/" + rel)
        romfs = len("romfs:/" + config.payload_dir + "/" + rel)
        lengths.append((rel, max(device, romfs)))
    longest = max(lengths, key=lambda item: item[1]) if lengths else ("", 0)
    if longest[1] > WINDOWS_PATH_MAX:
        status = "fail"
        hint = "Shorten payload.payload_dir or the file names."
    elif longest[1] > WINDOWS_PATH_WARN:
        status = "warn"
        hint = (
            "Long paths can break Windows builds; keep them under %d characters."
            % WINDOWS_PATH_WARN
        )
    else:
        status = "ok"
        hint = ""
    plan.add(
        _check(
            "payload-path-length",
            "path length limit",
            status,
            "longest %d chars (%s)" % (longest[1], longest[0] or "none"),
            hint,
        )
    )

    # FAT32 per-file limit
    oversized = [item for item in plan.all_files if item.size > FAT32_MAX_FILE]
    plan.add(
        _check(
            "payload-fat32-limit",
            "FAT32 per-file limit",
            "warn" if oversized else "ok",
            "all files fit FAT32"
            if not oversized
            else ", ".join("%s (%d B)" % (item.rel, item.size) for item in oversized),
            "Files above 4 GiB - 1 B require an exFAT-formatted SD card."
            if oversized
            else "",
        )
    )

    # symlinks / sparse files
    symlinks = [item.rel for item in plan.all_files if item.symlink]
    plan.add(
        _check(
            "payload-symlink",
            "symlinked payload files",
            "warn" if symlinks else "ok",
            ", ".join(symlinks) if symlinks else "none",
            "Materialize with copies; symlinks are not portable to the SD card."
            if symlinks
            else "",
        )
    )
    sparse = [item.rel for item in plan.all_files if item.sparse]
    plan.add(
        _check(
            "payload-sparse",
            "sparse payload files",
            "warn" if sparse else "ok",
            ", ".join(sparse) if sparse else "none",
            "Sparse files copy correctly but inflate the romfs on disk."
            if sparse
            else "",
        )
    )

    # UI directory
    ui = Path(ui_dir) if ui_dir is not None else config.ui_dir
    if ui is None:
        plan.add(_check("payload-ui", "engine UI files", "skip", "no ui_dir configured"))
    elif not Path(ui).is_dir():
        plan.add(
            _check(
                "payload-ui",
                "engine UI files",
                "fail",
                "not a directory: %s" % ui,
                "Point payload.ui_dir at the engine romfs UI directory.",
            )
        )
    else:
        try:
            plan.ui_files = scan_payload(ui, ("**/*",), ())
        except PayloadError as exc:
            plan.add(_check("payload-ui", "engine UI files", "fail", str(exc)))
        else:
            plan.add(
                _check(
                    "payload-ui",
                    "engine UI files",
                    "ok" if plan.ui_files else "fail",
                    "%d files, %d bytes"
                    % (len(plan.ui_files), total_bytes(plan.ui_files)),
                    "The engine UI directory is empty." if not plan.ui_files else "",
                )
            )
            if any(item.rel == config.manifest_name for item in plan.ui_files):
                plan.add(
                    _check(
                        "payload-ui-collision",
                        "UI vs manifest name",
                        "fail",
                        "ui_dir already contains %s" % config.manifest_name,
                    )
                )

    # summary
    plan.add(
        _check(
            "payload-total",
            "payload total",
            "ok" if plan.all_files else "fail",
            "%d payload files, %d bytes; ui %d files, %d bytes; manifest %d B; romfs %d bytes"
            % (
                len(plan.all_files),
                plan.payload_bytes,
                len(plan.ui_files),
                plan.ui_bytes,
                plan.manifest_bytes,
                plan.romfs_total_bytes,
            ),
        )
    )
    return plan


def _load_profile(name: str):
    from ..input import get_builtin

    return get_builtin(name)


# ---------------------------------------------------------------------------
# materialize


def _place(source: Path, dest: Path, mode: str, stats: dict) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if mode == "copy":
        shutil.copy2(source, dest)
        return
    if mode == "hardlink":
        try:
            os.link(source, dest)
            stats["hardlinked"] = stats.get("hardlinked", 0) + 1
            return
        except OSError:
            shutil.copy2(source, dest)
            stats["fallback_copy"] = stats.get("fallback_copy", 0) + 1
            return
    if mode == "symlink":
        try:
            os.symlink(source, dest)
        except OSError as exc:
            raise PayloadError(
                "cannot create symlink %s -> %s: %s" % (dest, source, exc)
            ) from None
        stats["symlinked"] = stats.get("symlinked", 0) + 1
        return
    raise PayloadError("unknown link mode %r" % mode)


def materialize(
    plan: PayloadPlan,
    out_dir: str | Path,
    mode: str | None = None,
    force: bool = False,
) -> dict:
    """Write the romfs tree described by plan into out_dir (copy by default)."""
    mode = mode or plan.link_mode
    if mode not in LINK_MODES:
        raise PayloadError(
            "unknown link mode %r (choose from %s)" % (mode, ", ".join(LINK_MODES))
        )
    if not force and not plan.is_ok():
        raise PayloadError(
            "refusing to materialize a plan with failed checks: %s"
            % "; ".join(
                "%s: %s" % (check.id, check.detail) for check in plan.errors()
            )
        )
    if not plan.manifest_text:
        raise PayloadError("plan has no game_files.txt (fix the failed checks first)")

    out = Path(out_dir)
    if out.exists() and not out.is_dir():
        raise PayloadError("materialize output is not a directory: %s" % out)
    out.mkdir(parents=True, exist_ok=True)

    stats: dict = {"payload": 0, "generated": 0, "ui": 0, "bytes": 0}
    for item in plan.ui_files:
        dest = out / item.rel
        if dest.exists() and not force:
            raise PayloadError("refusing to overwrite %s (pass force=True)" % dest)
        if item.source is None:
            raise PayloadError("UI file has no source path: %s" % item.rel)
        _place(Path(item.source), dest, mode, stats)
        stats["ui"] += 1
        stats["bytes"] += item.size
    for item in plan.files:
        dest = out / plan.config.payload_dir / item.rel
        if dest.exists() and not force:
            raise PayloadError("refusing to overwrite %s (pass force=True)" % dest)
        if item.source is None:
            raise PayloadError("payload file has no source path: %s" % item.rel)
        _place(Path(item.source), dest, mode, stats)
        stats["payload"] += 1
        stats["bytes"] += item.size
    if plan.keymap_text is not None:
        dest = out / plan.config.payload_dir / plan.config.keymap_file
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not force:
            raise PayloadError("refusing to overwrite %s (pass force=True)" % dest)
        payload = plan.keymap_text.encode("utf-8")
        dest.write_bytes(payload)
        stats["generated"] += 1
        stats["bytes"] += len(payload)
    manifest_dest = out / plan.config.manifest_name
    manifest_raw = plan.manifest_text.encode("utf-8")
    if manifest_dest.exists() and not force:
        raise PayloadError("refusing to overwrite %s (pass force=True)" % manifest_dest)
    manifest_dest.write_bytes(manifest_raw)
    stats["bytes"] += len(manifest_raw)
    return {
        "out_dir": str(out),
        "mode": mode,
        "payload_files": stats["payload"],
        "generated_files": stats["generated"],
        "ui_files": stats["ui"],
        "bytes": stats["bytes"],
        "manifest": {
            "path": str(manifest_dest),
            "bytes": len(manifest_raw),
            "sha256": sha256_bytes(manifest_raw),
        },
        "hardlinked": stats.get("hardlinked", 0),
        "fallback_copy": stats.get("fallback_copy", 0),
        "symlinked": stats.get("symlinked", 0),
        "ok": True,
    }


def plan_to_json(plan: PayloadPlan, include_files: bool = True) -> dict:
    """Small indirection kept for CLI/tests that only need the JSON view."""
    return plan.to_json(include_files=include_files)
