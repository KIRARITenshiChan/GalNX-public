"""Engine descriptor data model: YAML load, schema validation, normalisation.

An engine descriptor is a versionable record of one runtime adapter: where the
upstream project lives, which commit is pinned, which license it carries, which
target it produces, how it is built and verified, and which input profile it
defaults to. The format is defined by schemas/engine.schema.json; this module
turns that YAML into a frozen EngineDescriptor and reports problems as readable
"field: message" strings.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml
from jsonschema import Draft202012Validator

from ..input import list_builtin_names
from ..paths import schema_path

ENGINE_SCHEMA_NAME = "engine.schema.json"

TARGET_KINDS = ("nro", "self_contained_nsp", "web")
BUILD_BACKENDS = ("cmake-switch", "make-switch", "devkitpro-make", "custom-script", "prebuilt", "none")
STATUSES = ("ready", "research", "blocked")
CAPABILITY_KEYS = ("video", "audio", "input", "save", "touch")
CONTENT_MODES = ("romfs", "sdmc", "none")
CONTENT_LAYOUT_KEYS = ("mode", "entry", "destination", "notes")
SOURCE_KEYS = ("url", "commit", "submodules")
SUBMODULE_KEYS = ("path", "url", "commit")
PATCH_KEYS = ("path", "notes")
PORTLIB_KEYS = ("name", "version", "source_url", "recipe", "notes")
BUILD_KEYS = ("commands", "env", "workdir")
ARTIFACT_PLACEHOLDERS = ("id", "version", "target", "kind")
TARGET_SUFFIXES = {
    "nro": (".nro",),
    "self_contained_nsp": (".nsp",),
    "web": (".nro", ".nsp"),
}
SLUG_START = "abcdefghijklmnopqrstuvwxyz0123456789"
SLUG_CHARS = SLUG_START + "._-"
HEX_CHARS = "0123456789abcdefABCDEF"


class EngineDescriptorError(ValueError):
    """Raised when an engine descriptor cannot be loaded or is invalid."""


def load_schema(name: str = ENGINE_SCHEMA_NAME) -> dict[str, Any]:
    path = schema_path(name)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_validator(name: str = ENGINE_SCHEMA_NAME) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_descriptor_data(data: Any, name: str = ENGINE_SCHEMA_NAME) -> list[str]:
    """Return schema violations as readable "field: message" strings."""
    errors: list[str] = []
    for error in build_validator(name).iter_errors(data):
        location = "/".join(str(part) for part in error.absolute_path) or "descriptor"
        errors.append("%s: %s" % (location, error.message))
    return errors


def read_descriptor_file(path: str | Path) -> dict[str, Any]:
    """Read one YAML engine descriptor, raising EngineDescriptorError on problems."""
    descriptor_path = Path(path)
    if not descriptor_path.exists():
        raise EngineDescriptorError("engine descriptor not found: %s" % descriptor_path)
    try:
        text = descriptor_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EngineDescriptorError("cannot read engine descriptor %s: %s" % (descriptor_path, exc)) from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EngineDescriptorError("engine descriptor parse error in %s: %s" % (descriptor_path, exc)) from None
    if data is None:
        raise EngineDescriptorError("engine descriptor is empty: %s" % descriptor_path)
    if not isinstance(data, dict):
        raise EngineDescriptorError(
            "engine descriptor must be a YAML mapping, got %s: %s" % (type(data).__name__, descriptor_path)
        )
    return data


def is_slug(value: Any) -> bool:
    if not isinstance(value, str) or not 2 <= len(value) <= 64:
        return False
    if value[0] not in SLUG_START:
        return False
    return all(char in SLUG_CHARS for char in value)


def is_hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(char in HEX_CHARS for char in value)


def artifact_placeholders(template: str) -> list[str]:
    """Return the format placeholders used by an artifact naming template."""
    names: list[str] = []
    index = 0
    while index < len(template):
        char = template[index]
        if char == "{":
            if index + 1 < len(template) and template[index + 1] == "{":
                index += 2
                continue
            end = template.find("}", index)
            if end < 0:
                return ["<unclosed>"]
            names.append(template[index + 1:end])
            index = end + 1
            continue
        if char == "}":
            if index + 1 < len(template) and template[index + 1] == "}":
                index += 2
                continue
            return ["<stray>"]
        index += 1
    return names


def format_artifact_name(descriptor: "EngineDescriptor", version: str = "") -> str:
    """Render descriptor.artifact_naming with the values GalNX knows about."""
    values = {
        "id": descriptor.id,
        "version": version or descriptor.pinned_version or "unversioned",
        "target": descriptor.target_kind,
        "kind": descriptor.target_kind,
    }
    try:
        return descriptor.artifact_naming.format(**values)
    except (KeyError, IndexError, ValueError) as exc:
        raise EngineDescriptorError(
            "artifact_naming %r cannot be formatted: %s" % (descriptor.artifact_naming, exc)
        ) from None


@dataclass(frozen=True)
class EngineDescriptor:
    """A validated engine adapter descriptor.

    capabilities maps capability name (video/audio/input/save/touch) to
    {"supported": bool, "note": str}. content_layout describes where the game
    content lives for this runtime: romfs (embedded in the NRO), sdmc (SD card
    tree for a runtime such as Brewser) or none.
    """

    id: str
    display_name: str = ""
    upstream_url: str = ""
    pinned_commit: str = ""
    pinned_version: str = ""
    license_spdx: str = ""
    license_url: str = ""
    license_notes: str = ""
    target_kind: str = "nro"
    build_backend: str = "none"
    capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)
    default_input_profile: str = "kb_mouse"
    artifact_naming: str = "{id}.nro"
    content_layout: dict[str, Any] = field(default_factory=dict)
    status: str = "ready"
    status_reason: str = ""
    artifact_sha256: str = ""
    evidence_urls: tuple[str, ...] = ()
    notes: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    patches: tuple[dict[str, Any], ...] = ()
    portlibs: tuple[dict[str, Any], ...] = ()
    build: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"

    def validate(self) -> list[str]:
        """Return semantic problems (not covered by the JSON schema)."""
        problems: list[str] = []
        if not is_slug(self.id):
            problems.append("id: must be a lowercase slug (2-64 chars, [a-z0-9._-], starting alphanumeric)")
        if not self.display_name:
            problems.append("display_name: required")
        if not isinstance(self.upstream_url, str) or not self.upstream_url.startswith("https://"):
            problems.append("upstream_url: must be an https:// URL")
        if self.build_backend not in BUILD_BACKENDS:
            problems.append("build_backend: must be one of %s" % (BUILD_BACKENDS,))
        if self.pinned_commit:
            if not is_hex(self.pinned_commit, 40):
                problems.append("pinned_commit: must be 40 hex characters")
        elif self.build_backend in ("cmake-switch", "make-switch", "devkitpro-make", "custom-script"):
            problems.append("pinned_commit: required for source builds")
        if self.build_backend == "prebuilt" and not self.pinned_version:
            problems.append("pinned_version: required for prebuilt artifacts")
        if not self.license_spdx:
            problems.append("license_spdx: required")
        if not isinstance(self.license_url, str) or not self.license_url.startswith("http"):
            problems.append("license_url: required (link to the license evidence)")
        if self.target_kind not in TARGET_KINDS:
            problems.append("target_kind: must be one of %s" % (TARGET_KINDS,))
        for key in CAPABILITY_KEYS:
            entry = self.capabilities.get(key)
            if not isinstance(entry, Mapping):
                problems.append("capabilities.%s: required (supported/note)" % key)
                continue
            if not isinstance(entry.get("supported"), bool):
                problems.append("capabilities.%s.supported: must be a boolean" % key)
            if not isinstance(entry.get("note", ""), str):
                problems.append("capabilities.%s.note: must be a string" % key)
        for key in self.capabilities:
            if key not in CAPABILITY_KEYS:
                problems.append("capabilities.%s: unknown capability (allowed: %s)" % (key, ", ".join(CAPABILITY_KEYS)))
        if self.default_input_profile not in list_builtin_names():
            problems.append(
                "default_input_profile: %r is not a built-in input profile (built-in: %s)"
                % (self.default_input_profile, ", ".join(list_builtin_names()))
            )
        if not self.artifact_naming:
            problems.append("artifact_naming: required")
        else:
            for name in artifact_placeholders(self.artifact_naming):
                if name not in ARTIFACT_PLACEHOLDERS:
                    problems.append(
                        "artifact_naming: unknown placeholder %r (allowed: %s)"
                        % (name, ", ".join(ARTIFACT_PLACEHOLDERS))
                    )
            suffixes = TARGET_SUFFIXES.get(self.target_kind, ())
            if not self.artifact_naming.lower().endswith(suffixes):
                problems.append(
                    "artifact_naming: %r does not end with %s for target_kind %s"
                    % (self.artifact_naming, " or ".join(suffixes), self.target_kind)
                )
        if not isinstance(self.content_layout, Mapping):
            problems.append("content_layout: must be a mapping")
        else:
            mode = self.content_layout.get("mode")
            if mode not in CONTENT_MODES:
                problems.append("content_layout.mode: must be one of %s" % (CONTENT_MODES,))
            for key in self.content_layout:
                if key not in CONTENT_LAYOUT_KEYS:
                    problems.append("content_layout.%s: unknown key (allowed: %s)" % (key, ", ".join(CONTENT_LAYOUT_KEYS)))
            if mode != "none":
                if not self.content_layout.get("entry"):
                    problems.append("content_layout.entry: required when content_layout.mode is %r" % mode)
                if not self.content_layout.get("destination"):
                    problems.append("content_layout.destination: required when content_layout.mode is %r" % mode)
        if self.status not in STATUSES:
            problems.append("status: must be one of %s" % (STATUSES,))
        if self.status != "ready" and not self.status_reason:
            problems.append("status_reason: required when status is %r" % self.status)
        if self.artifact_sha256 and not is_hex(self.artifact_sha256, 64):
            problems.append("artifact_sha256: must be 64 hex characters when set")
        for index, url in enumerate(self.evidence_urls):
            if not isinstance(url, str) or not url:
                problems.append("evidence_urls[%d]: must be a non-empty string" % index)
        problems.extend(_source_problems(self.source))
        if self.source.get("commit") and self.pinned_commit and self.source["commit"] != self.pinned_commit:
            problems.append("source.commit: must match pinned_commit when both are set")
        problems.extend(_patch_problems(self.patches))
        problems.extend(_portlib_problems(self.portlibs))
        problems.extend(_build_problems(self.build))
        return problems

    def to_dict(self) -> dict[str, Any]:
        capability_dict = {
            key: {"supported": bool(entry.get("supported")), "note": str(entry.get("note", ""))}
            for key, entry in self.capabilities.items()
        }
        data: dict[str, Any] = {
            "id": self.id,
            "display_name": self.display_name,
            "upstream_url": self.upstream_url,
            "pinned_commit": self.pinned_commit,
            "pinned_version": self.pinned_version,
            "license_spdx": self.license_spdx,
            "license_url": self.license_url,
            "license_notes": self.license_notes,
            "target_kind": self.target_kind,
            "build_backend": self.build_backend,
            "capabilities": capability_dict,
            "default_input_profile": self.default_input_profile,
            "artifact_naming": self.artifact_naming,
            "content_layout": dict(self.content_layout),
            "status": self.status,
            "status_reason": self.status_reason,
            "artifact_sha256": self.artifact_sha256,
            "evidence_urls": list(self.evidence_urls),
            "notes": self.notes,
        }
        # Optional source-preparation sections: only present when the descriptor
        # actually records them, so pre-existing 19-key descriptors stay stable.
        if self.source:
            data["source"] = _dump_source(self.source)
        if self.patches:
            data["patches"] = [dict(item) for item in self.patches]
        if self.portlibs:
            data["portlibs"] = [dict(item) for item in self.portlibs]
        if self.build:
            data["build"] = _dump_build(self.build)
        return data

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "upstream_url": self.upstream_url,
            "pinned_commit": self.pinned_commit,
            "pinned_version": self.pinned_version,
            "license_spdx": self.license_spdx,
            "target_kind": self.target_kind,
            "build_backend": self.build_backend,
            "default_input_profile": self.default_input_profile,
            "status": self.status,
            "status_reason": self.status_reason,
        }


def _normalise_capabilities(value: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(value, Mapping):
        return result
    for key, entry in value.items():
        if isinstance(entry, Mapping):
            result[str(key)] = {
                "supported": bool(entry.get("supported", False)),
                "note": str(entry.get("note", "") or ""),
            }
        else:
            result[str(key)] = {"supported": False, "note": ""}
    return result


def _normalise_layout(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    layout: dict[str, Any] = {"mode": str(value.get("mode", "none"))}
    for key in ("entry", "destination", "notes"):
        if key in value:
            layout[key] = str(value.get(key, "") or "")
    return layout


def _normalise_source(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    source: dict[str, Any] = {}
    if "url" in value:
        source["url"] = str(value.get("url", "") or "")
    if "commit" in value:
        source["commit"] = str(value.get("commit", "") or "")
    if "submodules" in value:
        raw_modules = value.get("submodules") or ()
        modules: list[dict[str, str]] = []
        if isinstance(raw_modules, (list, tuple)):
            for item in raw_modules:
                if not isinstance(item, Mapping):
                    continue
                module = {"path": str(item.get("path", "") or ""), "url": str(item.get("url", "") or "")}
                if item.get("commit"):
                    module["commit"] = str(item.get("commit"))
                modules.append(module)
        source["submodules"] = modules
    return source


def _normalise_patches(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    patches: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        patch: dict[str, Any] = {"path": str(item.get("path", "") or "")}
        if item.get("notes"):
            patch["notes"] = str(item["notes"])
        patches.append(patch)
    return tuple(patches)


def _normalise_portlibs(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    portlibs: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        entry: dict[str, Any] = {"name": str(item.get("name", "") or "")}
        for key in ("version", "source_url", "recipe", "notes"):
            if item.get(key):
                entry[key] = str(item[key])
        portlibs.append(entry)
    return tuple(portlibs)


def _normalise_build(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    build: dict[str, Any] = {}
    if "commands" in value:
        commands = value.get("commands") or ()
        if isinstance(commands, (list, tuple)):
            build["commands"] = [str(command) for command in commands]
        else:
            build["commands"] = []
    if "env" in value:
        env = value.get("env") or {}
        if isinstance(env, Mapping):
            build["env"] = {str(key): str(item) for key, item in env.items()}
    if "workdir" in value:
        build["workdir"] = str(value.get("workdir", "") or "")
    return build


def _dump_source(source: Mapping[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if "url" in source:
        data["url"] = str(source.get("url", ""))
    if "commit" in source:
        data["commit"] = str(source.get("commit", ""))
    if "submodules" in source:
        data["submodules"] = [dict(item) for item in source.get("submodules") or ()]
    return data


def _dump_build(build: Mapping[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if "commands" in build:
        data["commands"] = [str(item) for item in build.get("commands") or ()]
    if "env" in build:
        data["env"] = {str(key): str(item) for key, item in (build.get("env") or {}).items()}
    if "workdir" in build:
        data["workdir"] = str(build.get("workdir", ""))
    return data


def _source_problems(source: Any) -> list[str]:
    if not source:
        return []
    if not isinstance(source, Mapping):
        return ["source: must be a mapping"]
    problems: list[str] = []
    for key in source:
        if key not in SOURCE_KEYS:
            problems.append("source.%s: unknown key (allowed: %s)" % (key, ", ".join(SOURCE_KEYS)))
    url = source.get("url", "")
    if not isinstance(url, str):
        problems.append("source.url: must be a string")
    commit = source.get("commit", "")
    if commit and not is_hex(commit, 40):
        problems.append("source.commit: must be 40 hex characters")
    submodules = source.get("submodules", ())
    if not isinstance(submodules, (list, tuple)):
        problems.append("source.submodules: must be a list")
        return problems
    for index, item in enumerate(submodules):
        if not isinstance(item, Mapping):
            problems.append("source.submodules[%d]: must be a mapping" % index)
            continue
        for key in item:
            if key not in SUBMODULE_KEYS:
                problems.append(
                    "source.submodules[%d].%s: unknown key (allowed: %s)" % (index, key, ", ".join(SUBMODULE_KEYS))
                )
        if not str(item.get("path", "") or ""):
            problems.append("source.submodules[%d].path: required" % index)
        if not str(item.get("url", "") or ""):
            problems.append("source.submodules[%d].url: required" % index)
        sub_commit = item.get("commit", "")
        if sub_commit and not is_hex(sub_commit, 40):
            problems.append("source.submodules[%d].commit: must be 40 hex characters" % index)
    return problems


def _patch_problems(patches: Any) -> list[str]:
    if not patches:
        return []
    if not isinstance(patches, (list, tuple)):
        return ["patches: must be a list"]
    problems: list[str] = []
    for index, item in enumerate(patches):
        if not isinstance(item, Mapping):
            problems.append("patches[%d]: must be a mapping" % index)
            continue
        for key in item:
            if key not in PATCH_KEYS:
                problems.append("patches[%d].%s: unknown key (allowed: %s)" % (index, key, ", ".join(PATCH_KEYS)))
        if not str(item.get("path", "") or ""):
            problems.append("patches[%d].path: required" % index)
        if not isinstance(item.get("notes", ""), str):
            problems.append("patches[%d].notes: must be a string" % index)
    return problems


def _portlib_problems(portlibs: Any) -> list[str]:
    if not portlibs:
        return []
    if not isinstance(portlibs, (list, tuple)):
        return ["portlibs: must be a list"]
    problems: list[str] = []
    for index, item in enumerate(portlibs):
        if not isinstance(item, Mapping):
            problems.append("portlibs[%d]: must be a mapping" % index)
            continue
        for key in item:
            if key not in PORTLIB_KEYS:
                problems.append("portlibs[%d].%s: unknown key (allowed: %s)" % (index, key, ", ".join(PORTLIB_KEYS)))
        if not str(item.get("name", "") or ""):
            problems.append("portlibs[%d].name: required" % index)
        for key in ("version", "source_url", "recipe", "notes"):
            if key in item and not isinstance(item.get(key, ""), str):
                problems.append("portlibs[%d].%s: must be a string" % (index, key))
    return problems


def _build_problems(build: Any) -> list[str]:
    if not build:
        return []
    if not isinstance(build, Mapping):
        return ["build: must be a mapping"]
    problems: list[str] = []
    for key in build:
        if key not in BUILD_KEYS:
            problems.append("build.%s: unknown key (allowed: %s)" % (key, ", ".join(BUILD_KEYS)))
    commands = build.get("commands", ())
    if not isinstance(commands, (list, tuple)):
        problems.append("build.commands: must be a list of non-empty strings")
    else:
        for index, command in enumerate(commands):
            if not isinstance(command, str) or not command:
                problems.append("build.commands[%d]: must be a non-empty string" % index)
    env = build.get("env", {})
    if not isinstance(env, Mapping):
        problems.append("build.env: must be a mapping of strings")
    else:
        for key, value in env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                problems.append("build.env.%s: key and value must be strings" % key)
    workdir = build.get("workdir", "")
    if not isinstance(workdir, str):
        problems.append("build.workdir: must be a string")
    return problems


def _descriptor_from_data(data: Mapping[str, Any]) -> EngineDescriptor:
    evidence = data.get("evidence_urls") or ()
    if isinstance(evidence, str):
        evidence = (evidence,)
    capabilities = _normalise_capabilities(data.get("capabilities"))
    descriptor = EngineDescriptor(
        id=str(data.get("id", "")),
        display_name=str(data.get("display_name", "")),
        upstream_url=str(data.get("upstream_url", "")),
        pinned_commit=str(data.get("pinned_commit", "") or ""),
        pinned_version=str(data.get("pinned_version", "") or ""),
        license_spdx=str(data.get("license_spdx", "")),
        license_url=str(data.get("license_url", "")),
        license_notes=str(data.get("license_notes", "") or ""),
        target_kind=str(data.get("target_kind", "nro")),
        build_backend=str(data.get("build_backend", "none")),
        capabilities=capabilities,
        default_input_profile=str(data.get("default_input_profile", "kb_mouse")),
        artifact_naming=str(data.get("artifact_naming", "{id}.nro")),
        content_layout=_normalise_layout(data.get("content_layout")),
        status=str(data.get("status", "ready")),
        status_reason=str(data.get("status_reason", "") or ""),
        artifact_sha256=str(data.get("artifact_sha256", "") or ""),
        evidence_urls=tuple(str(item) for item in evidence),
        notes=str(data.get("notes", "") or ""),
        source=_normalise_source(data.get("source")),
        patches=_normalise_patches(data.get("patches")),
        portlibs=_normalise_portlibs(data.get("portlibs")),
        build=_normalise_build(data.get("build")),
    )
    problems = descriptor.validate()
    if problems:
        raise EngineDescriptorError(
            "invalid engine descriptor %r: %s" % (descriptor.id or "<no id>", "; ".join(problems))
        )
    return descriptor


def descriptor_from_dict(data: Any, validate_schema: bool = True) -> EngineDescriptor:
    """Build a descriptor from a parsed mapping, validating schema and semantics."""
    if not isinstance(data, Mapping):
        raise EngineDescriptorError("engine descriptor must be a mapping, got %s" % type(data).__name__)
    if validate_schema:
        schema_errors = validate_descriptor_data(data)
        if schema_errors:
            raise EngineDescriptorError("invalid engine descriptor: %s" % "; ".join(schema_errors))
    return _descriptor_from_data(data)


def load_descriptor(path: str | Path) -> EngineDescriptor:
    return descriptor_from_dict(read_descriptor_file(path))


@dataclass(frozen=True)
class DescriptorCheck:
    """Result of checking one descriptor file without raising."""

    path: str
    descriptor: EngineDescriptor | None = None
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ok": self.ok,
            "descriptor": None if self.descriptor is None else self.descriptor.to_dict(),
            "errors": list(self.errors),
        }


def check_descriptor_file(path: str | Path) -> DescriptorCheck:
    try:
        descriptor = load_descriptor(path)
    except EngineDescriptorError as exc:
        return DescriptorCheck(path=str(path), descriptor=None, errors=(str(exc),))
    return DescriptorCheck(path=str(path), descriptor=descriptor, errors=())
