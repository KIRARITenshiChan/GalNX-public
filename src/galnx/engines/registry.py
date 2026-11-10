"""Engine registry: built-in adapters plus YAML descriptor overlays.

The registry answers "which adapters does GalNX know about". Built-in entries
live in this module as Python literals, so importing the registry never depends
on YAML files; additional engines are loaded from descriptor YAML files supplied
through --engines-dir or through the optional engine.descriptor manifest field.

Adding a third engine therefore needs no change to the core workflow: add one
YAML descriptor, and only write a Python adapter subclass when the generic
descriptor-driven adapter in contract.py is not enough.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from .descriptor import (
    CAPABILITY_KEYS,
    EngineDescriptor,
    EngineDescriptorError,
    load_descriptor,
)

BUILTIN_ORDER = ("krkrsdl2", "brewser", "onscripter-nx")


class EngineRegistryError(ValueError):
    """Raised when the registry cannot register or load an engine descriptor."""


def _capabilities(
    notes: Mapping[str, str] | None = None,
    supported: Mapping[str, bool] | None = None,
    verification: Mapping[str, str] | None = None,
    backends: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the six-entry capability mapping for a built-in descriptor."""
    notes = notes or {}
    verification = verification or {}
    backends = backends or {}
    flags = {"graphics": True, "movie": True, "audio": True, "input": True, "save": True, "touch": False}
    flags.update(supported or {})
    result: dict[str, dict[str, Any]] = {}
    for key in CAPABILITY_KEYS:
        entry: dict[str, Any] = {
            "supported": flags[key],
            "note": notes.get(key, ""),
            "verification": verification.get(key, "unknown"),
        }
        if key in backends:
            entry["backend"] = backends[key]
        result[key] = entry
    return result


def _builtin(descriptor: EngineDescriptor) -> EngineDescriptor:
    problems = descriptor.validate()
    if problems:
        raise RuntimeError(
            "built-in engine descriptor %r is invalid: %s" % (descriptor.id, "; ".join(problems))
        )
    return descriptor


KRKRSDL2 = _builtin(EngineDescriptor(
    id="krkrsdl2",
    display_name="KiriKiri SDL2",
    upstream_url="https://github.com/krkrsdl2/krkrsdl2",
    pinned_commit="124bdf841f09e7ce02aa99b7b55791a0f7a900ff",
    pinned_version="krkrsdl2@124bdf84 (2026-10-01)",
    license_spdx="MIT",
    license_url="https://github.com/krkrsdl2/krkrsdl2/blob/main/LICENSE",
    license_notes=(
        "Upstream LICENSE (1063 bytes, Kirikiri SDL2 Developers) is MIT. Bundled submodules "
        "(krkrz / FAudio / simde / zlib) keep their own licenses; the upstream README states that "
        "src is MIT and third-party components are not GPL."
    ),
    target_kind="nro",
    build_backend="cmake-switch",
    capabilities=_capabilities(
        notes={
            "graphics": "SDL2 renderer through switch-sdl2 + EGL (Mesa Nouveau).",
            "movie": "Upstream movie path (FFmpeg/AVI) is linked but no run has exercised video playback.",
            "audio": "FAudio (built from external/FAudio) plus the SDL2 audio device; no run has verified sound output.",
            "input": "SDL2 joystick/keyboard; the GalNX input layer injects keyboard/mouse events. Citron M1 title + advance passed.",
            "save": "KiriKiri save data through the libnx save namespace (per-title); not exercised in the M1 run.",
            "touch": "Not wired in the upstream SDL2 backend.",
        },
        verification={
            "graphics": "emulator_verified",
            "movie": "unknown",
            "audio": "unknown",
            "input": "emulator_verified",
            "save": "unknown",
            "touch": "unknown",
        },
        backends={
            "graphics": "sdl2-egl",
            "movie": "ffmpeg",
            "audio": "faudio+sdl2",
        },
    ),
    default_input_profile="krkrsdl2",
    artifact_naming="{id}-{version}.nro",
    content_layout={
        "mode": "romfs",
        "entry": "data.xp3",
        "destination": "romfs/data.xp3",
        "notes": "Upstream CMake takes -DEMBED_DATA_PATH=<file> and embeds it as romfs/<basename> through elf2nro.",
    },
    status="research",
    status_reason=(
        "Emulator-level only: a clean GalNX build renders the title screen and advances text in "
        "Citron Nightly 0237a9b88, but no Switch hardware run exists yet, audio/movie/save are "
        "unverified and the engine has no on-device launcher/menu work. Use it for build plans and "
        "emulator experiments, not for device claims."
    ),
    verification={
        "status": "emulator_verified",
        "hardware": "Citron Nightly 0237a9b88 (Windows, Vulkan)",
        "tested_at": "2026-10-26",
        "evidence": (
            "docs/builds/001-krkrsdl2-upstream.md",
            "docs/builds/004-krkrsdl2-switch-fixes.md",
        ),
        "notes": "Title screen plus input passed in Citron; no Switch hardware run.",
    },
    evidence_urls=(
        "docs/builds/001-krkrsdl2-upstream.md",
        "docs/builds/004-krkrsdl2-switch-fixes.md",
        "docs/audit/01-engines.md",
    ),
    notes="GalNX pins the commit and applies four compatibility patches recorded in docs/builds/patches/krkrsdl2-switch-emulator/.",
))

BREWSER = _builtin(EngineDescriptor(
    id="brewser",
    display_name="Brewser (nx.js web runtime)",
    upstream_url="https://github.com/natureglass/Brewser",
    pinned_commit="8040580e92e40a60f704a6478ee296b105212f1b",
    pinned_version="v0.1.1.31 (brewser 0.1.131)",
    license_spdx="MPL-2.0",
    license_url="https://github.com/natureglass/Brewser/blob/main/LICENSE",
    license_notes=(
        "The Brewser repository is MPL-2.0. The prebuilt brewser.nro bundles nx.js / V8 / Skia / "
        "Mesa components that keep their own licenses; the binary is redistributed from upstream "
        "release assets (dist/brewser.nro, sha256 recorded in the descriptor)."
    ),
    target_kind="web",
    build_backend="prebuilt",
    capabilities=_capabilities(
        notes={
            "graphics": "V8 + Skia Canvas2D, WebGL 1/2 through Mesa Nouveau; Citron smoke render passed.",
            "movie": "HTML5 video depends on the nx.js runtime codecs; playback has not been exercised.",
            "audio": "Web Audio API bridged onto the nx.js audio backend; sound output has not been exercised.",
            "input": "Web Gamepad/keyboard events; the GalNX input layer supplies the keyboard/mouse defaults.",
            "save": "localStorage/IndexedDB persisted under sdmc:/switch/brewser (globally shared). Citron runs show values do not survive a restart.",
            "touch": "Touch events are exposed to web apps; not exercised.",
        },
        supported={"touch": True},
        verification={
            "graphics": "emulator_verified",
            "movie": "unknown",
            "audio": "unknown",
            "input": "source_review",
            "save": "emulator_verified",
            "touch": "source_review",
        },
        backends={
            "graphics": "skia+webgl",
            "audio": "web-audio",
            "movie": "html5-video",
        },
    ),
    default_input_profile="kb_mouse",
    artifact_naming="brewser.nro",
    content_layout={
        "mode": "sdmc",
        "entry": "index.html",
        "destination": "sdmc:/switch/brewser/apps/<app-id>/",
        "notes": "Sideload a directory named after the reverse-domain app id; brewser.nro itself is copied to sdmc:/switch/brewser.nro. Saves and config live under sdmc:/switch/brewser/.",
    },
    status="research",
    status_reason=(
        "Emulator-only web runtime: the prebuilt brewser.nro loads HTML/Canvas2D/WebGL apps in "
        "Citron, but localStorage does not survive a restart (M4-g), no Switch hardware run exists, "
        "and save/audio/video behaviour is unverified."
    ),
    verification={
        "status": "emulator_verified",
        "hardware": "Citron Nightly 0237a9b88 (Windows, Vulkan)",
        "tested_at": "2026-10-29",
        "evidence": (
            "docs/audit/02-web.md",
            "docs/experiments/web-02-citron-smoke.md",
            "docs/builds/006-brewser-web-adapter.md",
        ),
        "notes": "Prebuilt NRO renders HTML/Canvas2D/WebGL in Citron; localStorage persistence across runs disproved.",
    },
    artifact_sha256="8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13",
    evidence_urls=(
        "docs/audit/02-web.md",
        "docs/experiments/web-02-citron-smoke.md",
    ),
    notes="Prebuilt upstream artifact (brewser.nro, 76546123 bytes, sha256 recorded above); no local engine build is needed. M4-b covers mounting the emulator SD card tree.",
))

ONSCRIPTER_NX = _builtin(EngineDescriptor(
    id="onscripter-nx",
    display_name="ONScripter-NX",
    upstream_url="https://github.com/clamintus/onscripter-nx",
    pinned_commit="a8439a86393f74c503d28df176f010ca544af56f",
    pinned_version="ONScripter-NX@a8439a86 (v0.3.1, 2026-01-14)",
    license_spdx="GPL-2.0-or-later",
    license_url="https://github.com/clamintus/onscripter-nx/blob/main/COPYING",
    license_notes=(
        "COPYING (18332 bytes) is the GPLv2 text; 24 of the 25 source/ files declare GPLv2 or any "
        "later version in their file headers, so the combined work is GPL-2.0-or-later. Shipping a "
        "built NRO therefore requires the corresponding source."
    ),
    target_kind="nro",
    build_backend="devkitpro-make",
    capabilities=_capabilities(
        notes={
            "graphics": "SDL2 renderer through switch-sdl2; Citron Nightly 0237a9b88 passed the R1-R5 run.",
            "movie": "Upstream movie playback is linked but no run has exercised video content.",
            "audio": "SDL2_mixer plus switch-libvorbis/opus are linked in; audio output is not verified on hardware.",
            "input": "Keyboard/keypad mapping in source/switch_mitm.cpp; Citron R2/R5 exercised advance and both branches.",
            "save": "ONScripter writes save*.dat to the process CWD; writability under a RomFS-only install is not verified.",
            "touch": "Touch injection is commented out in the upstream Switch backend.",
        },
        supported={"audio": False, "save": False},
        verification={
            "graphics": "emulator_verified",
            "movie": "unknown",
            "audio": "unknown",
            "input": "emulator_verified",
            "save": "unknown",
            "touch": "unknown",
        },
        backends={
            "graphics": "sdl2",
            "audio": "sdl2-mixer+vorbis",
        },
    ),
    default_input_profile="kb_mouse",
    artifact_naming="{id}-{version}.nro",
    content_layout={
        "mode": "romfs",
        "entry": "ons-content",
        "destination": "romfs/",
        "notes": "ONScripter-NX embeds the checked-out romfs/ directory at make time: copy the game content into src/engine/romfs/ before building and run make clean afterwards. Content needs *define/game/*start and at least one arc.nsa or arc.sar (a 0-byte placeholder passes the startup gate).",
    },
    status="research",
    status_reason=(
        "Build- and emulator-verified only: a clean devkitPro build runs self-authored *define "
        "content through R1-R5 in Citron, but there is no Switch hardware run, no multi-game "
        "launcher/menu or save UI, and GPL-2.0-or-later distribution needs legal sign-off plus the "
        "corresponding source."
    ),
    verification={
        "status": "emulator_verified",
        "hardware": "Citron Nightly 0237a9b88 (Windows, Vulkan)",
        "tested_at": "2026-10-30",
        "evidence": (
            "docs/builds/007-onscripter-nx.md",
            "docs/engines/verification-matrix.md",
        ),
        "notes": "Self-authored *define content passed R1-R5 (startup, advance, two branches); no Switch hardware run.",
    },
    evidence_urls=("docs/builds/007-onscripter-nx.md",),
    notes="Verified end-to-end in Citron (docs/builds/007); hardware unverified. Open framework gaps: no multi-game launcher (single arc.nsa directory model) and no save/load menu UI. GPL-2.0-or-later distribution needs the corresponding source.",
))

BUILTIN_ENGINES: dict[str, EngineDescriptor] = {descriptor.id: descriptor for descriptor in (KRKRSDL2, BREWSER, ONSCRIPTER_NX)}


class EngineRegistry:
    """A mutable set of engine descriptors keyed by adapter id."""

    def __init__(self, descriptors: Iterable[EngineDescriptor] = ()) -> None:
        self._engines: dict[str, EngineDescriptor] = {}
        for descriptor in descriptors:
            self.register(descriptor)

    @classmethod
    def builtin(cls) -> "EngineRegistry":
        return cls(BUILTIN_ENGINES[key] for key in BUILTIN_ORDER)

    def register(self, descriptor: EngineDescriptor, replace: bool = False) -> EngineDescriptor:
        problems = descriptor.validate()
        if problems:
            raise EngineRegistryError(
                "invalid engine descriptor %r: %s" % (descriptor.id or "<no id>", "; ".join(problems))
            )
        if descriptor.id in self._engines and not replace:
            raise EngineRegistryError("engine adapter %r is already registered" % descriptor.id)
        self._engines[descriptor.id] = descriptor
        return descriptor

    def get(self, engine_id: str) -> EngineDescriptor | None:
        return self._engines.get(engine_id)

    def require(self, engine_id: str) -> EngineDescriptor:
        descriptor = self.get(engine_id)
        if descriptor is None:
            raise EngineRegistryError(
                "unknown engine adapter %r (registered: %s)" % (engine_id, ", ".join(self.ids()) or "none")
            )
        return descriptor

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._engines))

    def descriptors(self) -> tuple[EngineDescriptor, ...]:
        return tuple(self._engines[key] for key in self.ids())

    def __len__(self) -> int:
        return len(self._engines)

    def __contains__(self, engine_id: object) -> bool:
        return engine_id in self._engines

    def load_file(self, path: str | Path, replace: bool = False) -> EngineDescriptor:
        return self.register(load_descriptor(path), replace=replace)

    def load_dir(self, directory: str | Path, replace: bool = False) -> list[EngineDescriptor]:
        directory_path = Path(directory)
        if not directory_path.is_dir():
            raise EngineRegistryError("engine descriptor directory not found: %s" % directory_path)
        loaded: list[EngineDescriptor] = []
        paths = sorted(list(directory_path.glob("*.yaml")) + list(directory_path.glob("*.yml")))
        for path in paths:
            descriptor = load_descriptor(path)
            existing = self.get(descriptor.id)
            if existing is not None and not replace:
                if existing.to_dict() == descriptor.to_dict():
                    # Descriptor directories may mirror the built-ins (examples/engines/
                    # does): an identical copy is a no-op, not a registry conflict.
                    continue
                raise EngineRegistryError(
                    "engine adapter %r is already registered with a different descriptor"
                    % descriptor.id
                )
            self.register(descriptor, replace=replace)
            loaded.append(descriptor)
        return loaded

    def summary(self) -> list[dict[str, Any]]:
        return [descriptor.summary() for descriptor in self.descriptors()]


def builtin_registry() -> EngineRegistry:
    return EngineRegistry.builtin()


def _as_dirs(value: Any) -> list[Path]:
    if value is None or value == "":
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    return [Path(item) for item in value]


def registry_for(engines_dir: Any = None) -> tuple[EngineRegistry, list[str]]:
    """Built-in registry plus every descriptor found in the extra directories."""
    registry = EngineRegistry.builtin()
    errors: list[str] = []
    for directory in _as_dirs(engines_dir):
        try:
            registry.load_dir(directory)
        except EngineRegistryError as exc:
            errors.append("engines: %s" % exc)
    return registry, errors


def _section_adapter(section: Any) -> tuple[str | None, list[str]]:
    if not isinstance(section, Mapping):
        return None, ["engine: must be a mapping"]
    adapter = section.get("adapter")
    if not isinstance(adapter, str) or not adapter:
        return None, ["engine.adapter: required"]
    return adapter, []


def registry_for_manifest(
    engine_section: Any,
    base_dir: str | Path | None = None,
    engines_dir: Any = None,
) -> tuple[EngineRegistry, list[str]]:
    """Build a registry that also honours engine.descriptor from the manifest."""
    registry, errors = registry_for(engines_dir)
    if not isinstance(engine_section, Mapping):
        return registry, errors
    descriptor_value = engine_section.get("descriptor")
    if not descriptor_value:
        return registry, errors
    candidate = Path(descriptor_value)
    if not candidate.is_absolute() and base_dir is not None:
        candidate = Path(base_dir) / candidate
    try:
        descriptor = load_descriptor(candidate)
    except EngineDescriptorError as exc:
        errors.append("engine.descriptor: %s" % exc)
        return registry, errors
    adapter = engine_section.get("adapter")
    if adapter and descriptor.id != adapter:
        errors.append(
            "engine.descriptor: descriptor id %r does not match engine.adapter %r"
            % (descriptor.id, adapter)
        )
        return registry, errors
    try:
        registry.register(descriptor, replace=True)
    except EngineRegistryError as exc:
        errors.append("engine.descriptor: %s" % exc)
    return registry, errors


def validate_manifest_engine(
    engine_section: Any,
    base_dir: str | Path | None = None,
    engines_dir: Any = None,
) -> list[str]:
    """Errors that tie manifest.engine to the engine registry."""
    if engine_section is None:
        return []
    adapter, errors = _section_adapter(engine_section)
    if errors:
        return errors
    registry, errors = registry_for_manifest(engine_section, base_dir=base_dir, engines_dir=engines_dir)
    if errors:
        return errors
    if registry.get(adapter) is None:
        return [
            "engine.adapter: unknown engine adapter %r (registered: %s; add a descriptor via "
            "engine.descriptor or --engines-dir)" % (adapter, ", ".join(registry.ids()) or "none")
        ]
    return []


def manifest_engine_warnings(
    engine_section: Any,
    base_dir: str | Path | None = None,
    engines_dir: Any = None,
) -> list[str]:
    """Warnings that do not invalidate a manifest but should be shown to users."""
    if not isinstance(engine_section, Mapping):
        return []
    adapter, errors = _section_adapter(engine_section)
    if errors:
        return []
    registry, errors = registry_for_manifest(engine_section, base_dir=base_dir, engines_dir=engines_dir)
    if errors:
        return errors
    descriptor = registry.get(adapter)
    if descriptor is None:
        return []
    warnings: list[str] = []
    if descriptor.status == "blocked":
        warnings.append(
            "engine.adapter: adapter %r is blocked: %s" % (adapter, descriptor.status_reason or "no reason recorded")
        )
    elif descriptor.status == "research":
        warnings.append(
            "engine.adapter: adapter %r is still marked research: %s"
            % (adapter, descriptor.status_reason or "no reason recorded")
        )
    declared = engine_section.get("adapter_version")
    if isinstance(declared, str) and declared and descriptor.pinned_commit:
        short = descriptor.pinned_commit[:8]
        if short not in declared:
            warnings.append(
                "engine.adapter_version: %r does not mention the pinned commit %s"
                % (declared, descriptor.pinned_commit)
            )
    return warnings
