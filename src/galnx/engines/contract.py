"""Adapter contract: build plans, artifact verification and harness run specs.

An adapter is the code side of an engine descriptor. The contract has three
methods:

  plan_build(descriptor, manifest) -> list[BuildStep]
  verify_artifact(descriptor, path) -> list[Check]
  run_spec(descriptor, manifest) -> dict

EngineAdapter implements all three from the descriptor YAML alone; concrete
subclasses (krkrsdl2, brewser) only refine the details. Adding a third engine is
therefore one YAML descriptor in examples/engines/ plus, only when the generic
path is insufficient, one small subclass here.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .descriptor import (
    EngineDescriptor,
    TARGET_SUFFIXES,
    format_artifact_name,
)
from .registry import (
    EngineRegistry,
    EngineRegistryError,
    builtin_registry,
    registry_for_manifest,
)

CHECK_STATUSES = ("ok", "warn", "fail", "skip")
NRO_MAGIC = b"NRO0"
NRO_MAGIC_OFFSET = 0x10
NRO_HOMEBREW = b"HOMEBREW"
NRO_HOMEBREW_OFFSET = 0x08
PFS0_MAGIC = b"PFS0"
SHA256_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class BuildStep:
    """One step of a build plan. Commands are guidance, never executed by GalNX."""

    id: str
    summary: str
    command: str = ""
    requires: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "summary": self.summary,
            "command": self.command,
            "requires": list(self.requires),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class Check:
    """Result of one contract check (same shape as package/doctor checks)."""

    id: str
    name: str = ""
    status: str = "ok"
    detail: str = ""
    hint: str = ""

    def __post_init__(self) -> None:
        if self.status not in CHECK_STATUSES:
            raise ValueError(
                "check status must be one of %s, got %r" % (CHECK_STATUSES, self.status)
            )

    @property
    def is_fail(self) -> bool:
        return self.status == "fail"

    @property
    def is_error(self) -> bool:
        return self.status == "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name or self.id,
            "status": self.status,
            "detail": self.detail,
            "hint": self.hint,
        }

    def to_json(self) -> dict[str, Any]:
        return self.to_dict()


def checks_to_dict(checks: list[Check]) -> list[dict[str, Any]]:
    return [check.to_dict() for check in checks]


def has_failures(checks: list[Check]) -> bool:
    return any(check.status == "fail" for check in checks)


def sha256_file(path: str | Path, chunk_size: int = SHA256_CHUNK) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def artifact_version(manifest: Any) -> str:
    """Version string used in artifact names: game.version when set."""
    if isinstance(manifest, Mapping):
        game = manifest.get("game")
        if isinstance(game, Mapping):
            value = game.get("version")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def sanitize_artifact_version(value: str) -> str:
    if not value:
        return ""
    cleaned = []
    for char in value:
        cleaned.append(char if char.isascii() and (char.isalnum() or char in "._-") else "-")
    text = "".join(cleaned)
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-._")


def _artifact_version_for(manifest: Any, descriptor: EngineDescriptor) -> str:
    version = artifact_version(manifest)
    if version:
        return sanitize_artifact_version(version)
    pinned = descriptor.pinned_version.split(" ")[0] if descriptor.pinned_version else ""
    return sanitize_artifact_version(pinned)


def _source_dir(manifest: Any) -> str:
    if isinstance(manifest, Mapping):
        game = manifest.get("game")
        if isinstance(game, Mapping):
            value = game.get("source_dir")
            if isinstance(value, str) and value:
                return value
    return "<game.source_dir>"


def _app_id(manifest: Any) -> str:
    if isinstance(manifest, Mapping):
        game = manifest.get("game")
        if isinstance(game, Mapping):
            value = game.get("id")
            if isinstance(value, str) and value:
                return value
    return "<app-id>"


def _artifact_name(manifest: Any, descriptor: EngineDescriptor) -> str:
    return format_artifact_name(descriptor, _artifact_version_for(manifest, descriptor))


def source_spec(descriptor: EngineDescriptor) -> dict[str, Any]:
    """Effective source spec: the descriptor source section first, legacy fields as fallback."""
    source = descriptor.source if isinstance(descriptor.source, Mapping) else {}
    spec: dict[str, Any] = {}
    url = source.get("url") or descriptor.upstream_url
    commit = source.get("commit") or descriptor.pinned_commit
    if url:
        spec["url"] = str(url)
    if commit:
        spec["commit"] = str(commit)
    submodules = source.get("submodules")
    if isinstance(submodules, (list, tuple)) and submodules:
        spec["submodules"] = [dict(item) for item in submodules if isinstance(item, Mapping)]
    return spec


def patch_specs(descriptor: EngineDescriptor) -> tuple[dict[str, Any], ...]:
    """Descriptor patches as plain dicts (empty tuple when the section is absent)."""
    return tuple(dict(item) for item in descriptor.patches if isinstance(item, Mapping))


def portlib_specs(descriptor: EngineDescriptor) -> tuple[dict[str, Any], ...]:
    """Descriptor portlibs as plain dicts (empty tuple when the section is absent)."""
    return tuple(dict(item) for item in descriptor.portlibs if isinstance(item, Mapping))


def build_spec(descriptor: EngineDescriptor) -> dict[str, Any]:
    """Descriptor build section (commands/env/workdir) as a plain dict."""
    build = descriptor.build if isinstance(descriptor.build, Mapping) else {}
    spec: dict[str, Any] = {}
    commands = build.get("commands")
    if isinstance(commands, (list, tuple)):
        spec["commands"] = [str(command) for command in commands]
    env = build.get("env")
    if isinstance(env, Mapping) and env:
        spec["env"] = {str(key): str(value) for key, value in env.items()}
    if build.get("workdir"):
        spec["workdir"] = str(build["workdir"])
    return spec


def descriptor_prepare_errors(descriptor: EngineDescriptor) -> list[str]:
    """Semantic problems that block engine source preparation (empty when ready)."""
    problems: list[str] = []
    spec = source_spec(descriptor)
    if descriptor.build_backend in ("cmake-switch", "make-switch", "devkitpro-make", "custom-script") and not spec.get("commit"):
        problems.append("source.commit: a pinned commit is required to prepare engine sources")
    for index, patch in enumerate(patch_specs(descriptor)):
        if not str(patch.get("path", "") or ""):
            problems.append("patches[%d].path: required" % index)
    if descriptor.build and not build_spec(descriptor).get("commands"):
        problems.append("build.commands: at least one command is required when build is set")
    return problems


class EngineAdapter:
    """Generic adapter driven only by the descriptor YAML."""

    name = "descriptor"

    def plan_build(
        self,
        descriptor: EngineDescriptor,
        manifest: Any = None,
        manifest_path: str | Path | None = None,
    ) -> list[BuildStep]:
        manifest_text = str(manifest_path) if manifest_path is not None else "<manifest.yaml>"
        source = _source_dir(manifest)
        layout = descriptor.content_layout if isinstance(descriptor.content_layout, Mapping) else {}
        steps: list[BuildStep] = [
            BuildStep(
                "manifest",
                "Validate the manifest (no build)",
                "galnx preflight --manifest %s" % manifest_text,
                requires=("galnx",),
                notes="For an NSP target also run: galnx package plan --manifest %s" % manifest_text,
            )
        ]
        build = build_spec(descriptor)
        if descriptor.build_backend in ("cmake-switch", "make-switch", "devkitpro-make", "custom-script"):
            spec = source_spec(descriptor)
            source_url = spec.get("url") or descriptor.upstream_url
            source_commit = spec.get("commit") or descriptor.pinned_commit
            steps.append(BuildStep(
                "source",
                "Fetch the pinned upstream source",
                "git clone %s src/engine && git -C src/engine checkout %s" % (source_url, source_commit),
                requires=("git",),
                notes="Pinned commit %s" % source_commit,
            ))
            patches = patch_specs(descriptor)
            if patches:
                steps.append(BuildStep(
                    "patches",
                    "Apply the %d GalNX patch(es) to the pinned source" % len(patches),
                    " && ".join(
                        "git -C src/engine apply %s" % str(item.get("path", "")) for item in patches
                    ),
                    requires=("git",),
                    notes="Patches: %s" % ", ".join(str(item.get("path", "")) for item in patches),
                ))
            portlibs = portlib_specs(descriptor)
            if portlibs:
                steps.append(BuildStep(
                    "portlibs",
                    "Build the %d engine-specific portlib(s)" % len(portlibs),
                    " && ".join(
                        "bash %s"
                        % str(item.get("recipe") or ("portlibs/" + str(item.get("name", ""))))
                        for item in portlibs
                    ),
                    requires=("make", "devkitA64"),
                    notes="; ".join(
                        "%s %s" % (str(item.get("name", "")), str(item.get("version", ""))) for item in portlibs
                    ).strip(),
                ))
            if not build.get("commands"):
                if descriptor.build_backend == "cmake-switch":
                    steps.append(BuildStep(
                        "configure",
                        "Configure with the devkitPro Switch toolchain",
                        "cmake -S src/engine -B build -G Ninja "
                        "-DCMAKE_TOOLCHAIN_FILE=$DEVKITPRO/cmake/Switch.cmake -DCMAKE_BUILD_TYPE=Release",
                        requires=("cmake", "ninja", "devkitA64"),
                        notes="Build outside paths that contain spaces (devkitPro make rules quote bug).",
                    ))
                    steps.append(BuildStep(
                        "compile",
                        "Compile the engine",
                        "cmake --build build -j8",
                        requires=("devkitA64",),
                    ))
                elif descriptor.build_backend == "devkitpro-make":
                    steps.append(BuildStep(
                        "prepare-content",
                        "Stage the game content into the engine romfs before building",
                        "mkdir -p src/engine/romfs && cp -r %s/%s/. src/engine/romfs/"
                        % (_source_dir(manifest), layout.get("entry", "<content-dir>")),
                        notes=str(layout.get("notes", "")),
                    ))
                    steps.append(BuildStep(
                        "compile",
                        "Compile with the devkitPro switch_rules Makefile",
                        "cd src/engine && make clean && make -j8",
                        requires=("make", "devkitA64"),
                        notes="devkitPro make embeds romfs/ at build time, so stage content before compiling. Build outside paths that contain spaces (switch_rules quote bug).",
                    ))
                elif descriptor.build_backend == "custom-script":
                    pass  # the descriptor build.commands step below drives the build
                else:
                    steps.append(BuildStep(
                        "compile",
                        "Compile the engine with make",
                        "make -j8",
                        requires=("make", "devkitA64"),
                        notes="Build outside paths that contain spaces (switch_rules quote bug).",
                    ))
        build = build_spec(descriptor)
        if build.get("commands"):
            notes_parts = []
            if build.get("workdir"):
                notes_parts.append("workdir %s" % build["workdir"])
            if build.get("env"):
                notes_parts.append("env %s" % ", ".join("%s=%s" % item for item in build["env"].items()))
            notes_parts.append("Commands come from the descriptor build section; GalNX never executes them.")
            steps.append(BuildStep(
                "engine-build",
                "Run the engine-specific build entry point",
                " && ".join(str(command) for command in build["commands"]),
                requires=("devkitA64",),
                notes="; ".join(notes_parts),
            ))
        if layout.get("mode") == "romfs" and descriptor.build_backend != "devkitpro-make":
            steps.append(BuildStep(
                "content",
                "Stage game content into romfs",
                "mkdir -p build/romfs && cp %s build/romfs/%s"
                % (layout.get("entry", "<entry>"), layout.get("entry", "<entry>")),
                notes=str(layout.get("notes", "")),
            ))
        elif layout.get("mode") == "sdmc":
            steps.append(BuildStep(
                "content",
                "Stage game content into the emulator SD card tree",
                "mkdir -p %s && cp -r %s/. %s"
                % (layout.get("destination", "<sdmc-dir>"), source, layout.get("destination", "<sdmc-dir>")),
                notes=str(layout.get("notes", "")),
            ))
        steps.append(BuildStep(
            "artifact",
            "Collect the expected artifact",
            _artifact_name(manifest, descriptor),
            notes="Naming template: %s" % descriptor.artifact_naming,
        ))
        steps.append(BuildStep(
            "verify",
            "Verify the artifact before launching",
            "",
            notes="Run galnx.engines.contract.verify_artifact; check NRO0/PFS0 magic, size and sha256.",
        ))
        return steps

    def verify_artifact(
        self,
        descriptor: EngineDescriptor,
        path: str | Path,
        expected_sha256: str | None = None,
    ) -> list[Check]:
        artifact = Path(path)
        if not artifact.exists():
            return [Check("artifact.exists", "artifact.exists", "fail", "artifact not found: %s" % artifact)]
        if not artifact.is_file():
            return [Check("artifact.exists", "artifact.exists", "fail", "not a regular file: %s" % artifact)]
        size = artifact.stat().st_size
        checks: list[Check] = []
        checks.append(Check("artifact.file", "artifact.file", "ok", "%s (%d bytes)" % (artifact, size)))
        if size == 0:
            checks.append(Check("artifact.size", "artifact.size", "fail", "artifact is empty"))
        suffixes = TARGET_SUFFIXES.get(descriptor.target_kind, (".nro",))
        suffix = artifact.suffix.lower()
        checks.append(Check(
            "artifact.extension",
            "artifact.extension",
            "ok" if suffix in suffixes else "fail",
            "%s (expected %s for target_kind %s)"
            % (suffix or "<none>", " or ".join(suffixes), descriptor.target_kind),
        ))
        with artifact.open("rb") as handle:
            header = handle.read(0x20)
        if descriptor.target_kind == "self_contained_nsp":
            magic_ok = header[:4] == PFS0_MAGIC
            checks.append(Check(
                "artifact.magic",
                "artifact.magic",
                "ok" if magic_ok else "fail",
                "PFS0 partition at offset 0" if magic_ok else "missing PFS0 magic (not an NSP)",
            ))
        else:
            magic_ok = header[NRO_MAGIC_OFFSET:NRO_MAGIC_OFFSET + 4] == NRO_MAGIC
            checks.append(Check(
                "artifact.magic",
                "artifact.magic",
                "ok" if magic_ok else "fail",
                "NRO0 magic at offset 0x10" if magic_ok else "missing NRO0 magic at offset 0x10 (not a Switch NRO)",
            ))
            homebrew_ok = header[NRO_HOMEBREW_OFFSET:NRO_HOMEBREW_OFFSET + 8] == NRO_HOMEBREW
            checks.append(Check(
                "artifact.header",
                "artifact.header",
                "ok" if homebrew_ok else "warn",
                "HOMEBREW marker at offset 0x08"
                if homebrew_ok
                else "HOMEBREW marker missing at offset 0x08; some loaders may reject the NRO",
            ))
        expected = expected_sha256 or descriptor.artifact_sha256
        if expected:
            actual = sha256_file(artifact)
            checks.append(Check(
                "artifact.sha256",
                "artifact.sha256",
                "ok" if actual.lower() == expected.lower() else "fail",
                "sha256 %s (expected %s)" % (actual, expected),
            ))
        else:
            checks.append(Check(
                "artifact.sha256",
                "artifact.sha256",
                "warn",
                "no expected sha256 recorded for this engine",
                hint="Record artifact_sha256 in the descriptor or pass expected_sha256.",
            ))
        failures = [check for check in checks if check.status == "fail"]
        checks.append(Check(
            "artifact.result",
            "artifact.result",
            "fail" if failures else "ok",
            "%d checks failed" % len(failures) if failures else "artifact looks loadable",
        ))
        return checks

    def run_spec(self, descriptor: EngineDescriptor, manifest: Any = None) -> dict[str, Any]:
        layout = descriptor.content_layout if isinstance(descriptor.content_layout, Mapping) else {}
        return {
            "engine": descriptor.id,
            "harness": "citron",
            "target_kind": descriptor.target_kind,
            "load": "nsp" if descriptor.target_kind == "self_contained_nsp" else "nro",
            "artifact": _artifact_name(manifest, descriptor),
            "arguments": ["-g", "<artifact>"],
            "sdmc": layout.get("destination") if layout.get("mode") == "sdmc" else None,
            "notes": [],
        }


class Krkrsdl2Adapter(EngineAdapter):
    name = "krkrsdl2"

    def plan_build(
        self,
        descriptor: EngineDescriptor,
        manifest: Any = None,
        manifest_path: str | Path | None = None,
    ) -> list[BuildStep]:
        manifest_text = str(manifest_path) if manifest_path is not None else "<manifest.yaml>"
        entry = "data.xp3"
        layout = descriptor.content_layout if isinstance(descriptor.content_layout, Mapping) else {}
        entry = str(layout.get("entry") or entry)
        steps: list[BuildStep] = [
            BuildStep(
                "manifest",
                "Validate the manifest (no build)",
                "galnx preflight --manifest %s" % manifest_text,
                requires=("galnx",),
            ),
            BuildStep(
                "source",
                "Fetch pinned krkrsdl2",
                "git clone %s src/engine && git -C src/engine checkout %s"
                % (descriptor.upstream_url, descriptor.pinned_commit),
                requires=("git",),
                notes="Pinned commit %s (2026-10-01)." % descriptor.pinned_commit,
            ),
            BuildStep(
                "patches",
                "Apply the GalNX compatibility patches",
                "git -C src/engine apply <repo>/docs/builds/patches/krkrsdl2-switch-emulator/*.patch",
                requires=("git",),
                notes="Four patches (+38 lines) are recorded in docs/builds/004-krkrsdl2-switch-fixes.md.",
            ),
            BuildStep(
                "prepare-data",
                "Copy the KiriKiri archive next to the build",
                "cp %s/%s src/engine/%s" % (_source_dir(manifest), entry, entry),
                notes="Try the font-augmented data.xp3 (docs/builds/003-kag3-demo-content.md) so the KAG3 demo does not depend on Switch system fonts.",
            ),
            BuildStep(
                "configure",
                "Configure with the devkitPro Switch toolchain",
                "cmake -S src/engine -B build -G Ninja "
                "-DCMAKE_TOOLCHAIN_FILE=$DEVKITPRO/cmake/Switch.cmake "
                "-DCMAKE_BUILD_TYPE=Release -DEMBED_DATA_PATH=%s" % entry,
                requires=("cmake", "ninja", "devkitA64"),
                notes="Build outside paths that contain spaces (devkitPro make rules quote bug).",
            ),
            BuildStep(
                "compile",
                "Compile krkrsdl2",
                "cmake --build build -j8",
                requires=("devkitA64",),
            ),
            BuildStep(
                "artifact",
                "Collect the NRO",
                _artifact_name(manifest, descriptor),
                notes="Upstream target builds krkrsdl2.nro with an embedded romfs; rename to the GalNX artifact name.",
            ),
            BuildStep(
                "verify",
                "Verify the artifact before launching",
                "",
                notes="galnx.engines.contract.verify_artifact checks NRO0 magic, HOMEBREW marker and size.",
            ),
        ]
        return steps

    def verify_artifact(
        self,
        descriptor: EngineDescriptor,
        path: str | Path,
        expected_sha256: str | None = None,
    ) -> list[Check]:
        checks = super().verify_artifact(descriptor, path, expected_sha256=expected_sha256)
        artifact = Path(path)
        if artifact.is_file():
            size = artifact.stat().st_size
            if size < 1024 * 1024:
                checks.append(Check(
                    "artifact.engine",
                    "artifact.engine",
                    "warn",
                    "NRO is only %d bytes; the known krkrsdl2 build with embedded data.xp3 is about 17.9 MB" % size,
                ))
            else:
                checks.append(Check(
                    "artifact.engine",
                    "artifact.engine",
                    "ok",
                    "size is consistent with an embedded-data krkrsdl2 build",
                ))
        return checks

    def run_spec(self, descriptor: EngineDescriptor, manifest: Any = None) -> dict[str, Any]:
        spec = super().run_spec(descriptor, manifest)
        spec["notes"] = [
            "Applet-mode compatible NRO (appletMainLoop); on hardware launch from hbmenu in full-memory application mode.",
            "The KAG3 demo references system fonts (MS PMincho / MS Gothic); real games should ship a font in romfs.",
            "Citron boots the NRO directly; no NSP packaging is required for this adapter.",
        ]
        return spec


class BrewserAdapter(EngineAdapter):
    name = "brewser"

    def plan_build(
        self,
        descriptor: EngineDescriptor,
        manifest: Any = None,
        manifest_path: str | Path | None = None,
    ) -> list[BuildStep]:
        manifest_text = str(manifest_path) if manifest_path is not None else "<manifest.yaml>"
        steps: list[BuildStep] = [
            BuildStep(
                "manifest",
                "Validate the manifest (no build)",
                "galnx preflight --manifest %s" % manifest_text,
                requires=("galnx",),
            ),
            BuildStep(
                "fetch",
                "Download the pinned prebuilt brewser.nro",
                "curl -L -o dist/brewser.nro "
                "https://raw.githubusercontent.com/natureglass/Brewser/main/dist/brewser.nro",
                requires=("curl",),
                notes="Pinned release %s; the upstream dist/update.json can be used to cross-check the version." % descriptor.pinned_version,
            ),
            BuildStep(
                "verify-source",
                "Verify the downloaded NRO checksum",
                "sha256sum dist/brewser.nro",
                notes="Expected sha256 %s" % descriptor.artifact_sha256,
            ),
            BuildStep(
                "content",
                "Copy the web app into the emulator SD card tree",
                "mkdir -p <sdmc>/switch/brewser/apps/%s && cp -r %s/. <sdmc>/switch/brewser/apps/%s/"
                % (_app_id(manifest), _source_dir(manifest), _app_id(manifest)),
                notes="Folder name is the reverse-domain app id; index.html is the entry file.",
            ),
            BuildStep(
                "install",
                "Place brewser.nro on the SD card",
                "cp dist/brewser.nro <sdmc>/switch/brewser.nro",
                notes="On hardware install to sd:/switch/brewser.nro; on Citron use the harness SD card root.",
            ),
            BuildStep(
                "artifact",
                "Collect the expected artifact",
                _artifact_name(manifest, descriptor),
                notes="Prebuilt artifact; GalNX only verifies and stages it.",
            ),
        ]
        return steps

    def verify_artifact(
        self,
        descriptor: EngineDescriptor,
        path: str | Path,
        expected_sha256: str | None = None,
    ) -> list[Check]:
        return super().verify_artifact(descriptor, path, expected_sha256=expected_sha256)

    def run_spec(self, descriptor: EngineDescriptor, manifest: Any = None) -> dict[str, Any]:
        spec = super().run_spec(descriptor, manifest)
        spec["notes"] = [
            "On hardware Brewser requires an Atmosphare CFW and the hbmenu full-memory application mode (hold R when launching a game).",
            "Citron boots the NRO without sigpatches; the optional forwarder NSP is not required for emulator tests.",
            "Mount an SD card tree and sideload the app directory under switch/brewser/apps/<app-id>/.",
            "WebGL runs on Mesa Nouveau; --jitless (used by some emulator profiles) removes WebAssembly entirely.",
        ]
        return spec


class OnscripterNxAdapter(EngineAdapter):
    name = "onscripter-nx"

    def plan_build(
        self,
        descriptor: EngineDescriptor,
        manifest: Any = None,
        manifest_path: str | Path | None = None,
    ) -> list[BuildStep]:
        manifest_text = str(manifest_path) if manifest_path is not None else "<manifest.yaml>"
        layout = descriptor.content_layout if isinstance(descriptor.content_layout, Mapping) else {}
        entry = str(layout.get("entry") or "ons-content")
        steps: list[BuildStep] = [
            BuildStep(
                "manifest",
                "Validate the manifest (no build)",
                "galnx preflight --manifest %s" % manifest_text,
                requires=("galnx",),
            ),
            BuildStep(
                "source",
                "Fetch pinned ONScripter-NX",
                "git clone %s src/engine && git -C src/engine checkout %s"
                % (descriptor.upstream_url, descriptor.pinned_commit),
                requires=("git",),
                notes="Pinned commit %s (v0.3.1, 2026-01-14)." % descriptor.pinned_commit,
            ),
            BuildStep(
                "prepare-content",
                "Stage game content into the ONScripter romfs",
                "mkdir -p src/engine/romfs && cp -r %s/%s/. src/engine/romfs/"
                % (_source_dir(manifest), entry),
                notes="Content must contain *define/game/*start and at least one arc.nsa or arc.sar "
                      "(a 0-byte placeholder passes the startup gate). Run make clean after changing romfs.",
            ),
            BuildStep(
                "compile",
                "Compile with the devkitPro switch_rules Makefile",
                "cd src/engine && make clean && make -j8",
                requires=("make", "devkitA64"),
                notes="Plain devkitPro Makefile (include $(DEVKITPRO)/libnx/switch_rules); the verified build took about 20 s. Build outside paths that contain spaces.",
            ),
            BuildStep(
                "artifact",
                "Collect the NRO",
                _artifact_name(manifest, descriptor),
                notes="Upstream writes <clone-dir>.nro with the rsdk/romfs embedded; rename to the GalNX artifact name.",
            ),
            BuildStep(
                "verify",
                "Verify the artifact before launching",
                "",
                notes="galnx.engines.contract.verify_artifact checks NRO0 magic, HOMEBREW marker, size and sha256.",
            ),
        ]
        return steps

    def verify_artifact(
        self,
        descriptor: EngineDescriptor,
        path: str | Path,
        expected_sha256: str | None = None,
    ) -> list[Check]:
        checks = super().verify_artifact(descriptor, path, expected_sha256=expected_sha256)
        artifact = Path(path)
        if artifact.is_file():
            size = artifact.stat().st_size
            if size < 1024 * 1024:
                checks.append(Check(
                    "artifact.engine",
                    "artifact.engine",
                    "warn",
                    "NRO is only %d bytes; the verified ONScripter-NX build with embedded content is about 10.4 MB" % size,
                ))
            else:
                checks.append(Check(
                    "artifact.engine",
                    "artifact.engine",
                    "ok",
                    "size is consistent with an embedded-content ONScripter-NX build",
                ))
        return checks

    def run_spec(self, descriptor: EngineDescriptor, manifest: Any = None) -> dict[str, Any]:
        spec = super().run_spec(descriptor, manifest)
        spec["notes"] = [
            "Citron Nightly 0237a9b88 ran the 0.3.1 build through R1-R5 (docs/builds/007); real hardware is not verified.",
            "Content is embedded into romfs/ at make time; stage it into the checkout before building.",
            "No multi-game launcher or save/load menu UI; GalNX must provide those entry points.",
            "Touch input is commented out upstream; save/load writes to the process CWD and is unverified on hardware.",
        ]
        return spec


ADAPTER_FACTORIES: dict[str, type[EngineAdapter]] = {
    "krkrsdl2": Krkrsdl2Adapter,
    "brewser": BrewserAdapter,
    "onscripter-nx": OnscripterNxAdapter,
}


def adapter_for(descriptor: EngineDescriptor) -> EngineAdapter:
    return ADAPTER_FACTORIES.get(descriptor.id, EngineAdapter)()


@dataclass(frozen=True)
class BuildPlan:
    descriptor: EngineDescriptor
    adapter: str
    steps: tuple[BuildStep, ...]
    input_profile: str
    input_profile_source: str
    expected_artifact: str
    run_spec: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "engine": self.descriptor.summary(),
            "build_steps": [step.to_dict() for step in self.steps],
            "input_profile": {"name": self.input_profile, "source": self.input_profile_source},
            "expected_artifact": self.expected_artifact,
            "run_spec": self.run_spec,
        }


def _engine_section(manifest: Any) -> tuple[Mapping[str, Any], str]:
    if not isinstance(manifest, Mapping):
        raise EngineRegistryError("manifest must be a mapping")
    section = manifest.get("engine")
    if not isinstance(section, Mapping):
        raise EngineRegistryError("manifest.engine is missing or not a mapping")
    adapter = section.get("adapter")
    if not isinstance(adapter, str) or not adapter:
        raise EngineRegistryError("manifest.engine.adapter is missing")
    return section, adapter


def resolve_descriptor(
    manifest: Any,
    registry: EngineRegistry | None = None,
    base_dir: str | Path | None = None,
    engines_dir: Any = None,
) -> EngineDescriptor:
    section, adapter = _engine_section(manifest)
    if registry is None:
        registry, errors = registry_for_manifest(section, base_dir=base_dir, engines_dir=engines_dir)
        if errors:
            raise EngineRegistryError("; ".join(errors))
    descriptor = registry.get(adapter)
    if descriptor is None:
        raise EngineRegistryError(
            "unknown engine adapter %r (registered: %s)" % (adapter, ", ".join(registry.ids()) or "none")
        )
    return descriptor


def _effective_input_profile(descriptor: EngineDescriptor, manifest: Any) -> tuple[str, str]:
    if isinstance(manifest, Mapping):
        section = manifest.get("input")
        if isinstance(section, Mapping):
            value = section.get("profile")
            if isinstance(value, str) and value:
                return value, "manifest"
    return descriptor.default_input_profile, "engine-default"


def plan_build(
    manifest: Any,
    manifest_path: str | Path | None = None,
    registry: EngineRegistry | None = None,
    base_dir: str | Path | None = None,
    engines_dir: Any = None,
) -> BuildPlan:
    descriptor = resolve_descriptor(manifest, registry=registry, base_dir=base_dir, engines_dir=engines_dir)
    adapter = adapter_for(descriptor)
    steps = adapter.plan_build(descriptor, manifest, manifest_path=manifest_path)
    input_profile, input_profile_source = _effective_input_profile(descriptor, manifest)
    return BuildPlan(
        descriptor=descriptor,
        adapter=adapter.name,
        steps=tuple(steps),
        input_profile=input_profile,
        input_profile_source=input_profile_source,
        expected_artifact=_artifact_name(manifest, descriptor),
        run_spec=adapter.run_spec(descriptor, manifest),
    )


def verify_artifact(
    path: str | Path,
    descriptor: EngineDescriptor | None = None,
    engine_id: str | None = None,
    registry: EngineRegistry | None = None,
    expected_sha256: str | None = None,
) -> list[Check]:
    if descriptor is None:
        if engine_id is None:
            raise EngineRegistryError("verify_artifact needs a descriptor or an engine_id")
        registry = registry or builtin_registry()
        descriptor = registry.require(engine_id)
    return adapter_for(descriptor).verify_artifact(descriptor, path, expected_sha256=expected_sha256)


def run_spec(
    manifest: Any,
    registry: EngineRegistry | None = None,
    base_dir: str | Path | None = None,
    engines_dir: Any = None,
) -> dict[str, Any]:
    descriptor = resolve_descriptor(manifest, registry=registry, base_dir=base_dir, engines_dir=engines_dir)
    return adapter_for(descriptor).run_spec(descriptor, manifest)
