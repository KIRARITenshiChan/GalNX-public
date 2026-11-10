"""Manifest-declared build commands (M6-b).

This module only interprets the ``build`` section of a game manifest.  It never
touches the engines layer and never executes anything; command execution lives in
``galnx.build.executor``.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence, Union

DEFAULT_TIMEOUT_S = 600.0

# Toolchain components whose unknown version makes a build non-cacheable by
# default.  Manifests may override this with ``build.toolchain_components``.
DEFAULT_TOOLCHAIN_COMPONENTS = ("devkitpro_gcc", "cmake", "ninja")

# Either an argv vector (executed with shell=False) or a shell command string.
Command = Union[tuple[str, ...], str]


class BuildError(ValueError):
    """Raised when a manifest build section cannot be interpreted."""


@dataclass(frozen=True)
class BuildInput:
    """One explicit build input declared under ``build.inputs``."""

    path: str
    kind: str = "tree"
    optional: bool = False
    ignore: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuildConfig:
    """Normalized, executable view of a manifest ``build`` section."""

    commands: tuple[Command, ...] = ()
    workdir: Path = Path(".")
    artifact: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    timeout_s: float = DEFAULT_TIMEOUT_S
    raw: dict[str, Any] = field(default_factory=dict)
    inputs: tuple[BuildInput, ...] = ()
    toolchain_components: tuple[str, ...] = DEFAULT_TOOLCHAIN_COMPONENTS

    @property
    def has_commands(self) -> bool:
        return bool(self.commands)

    @property
    def has_artifact(self) -> bool:
        return bool(self.artifact)

    @property
    def execution_state(self) -> str:
        """Classify the build section for reporting.

        configured     -- commands and artifact are both declared
        not_configured -- neither is declared; nothing to execute
        incomplete     -- only one of the two is declared (rejected by the parser)
        """

        if self.commands and self.artifact:
            return "configured"
        if not self.commands and not self.artifact:
            return "not_configured"
        return "incomplete"

    @property
    def executable(self) -> bool:
        """True when the manifest declares commands *and* an artifact."""
        return self.execution_state == "configured"


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BuildError("%s must be a mapping, got %s" % (where, type(value).__name__))
    return value


def _command(value: Any, index: int) -> Command:
    if isinstance(value, str):
        if not value.strip():
            raise BuildError("build.commands[%d]: shell command must not be empty" % index)
        return value
    if isinstance(value, (list, tuple)):
        argv = tuple(value)
        if not argv:
            raise BuildError("build.commands[%d]: argv command must not be empty" % index)
        for part in argv:
            if not isinstance(part, str) or not part:
                raise BuildError(
                    "build.commands[%d]: argv entries must be non-empty strings" % index
                )
        return argv
    raise BuildError(
        "build.commands[%d]: expected a string or an argv array, got %s"
        % (index, type(value).__name__),
    )


def _env(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    mapping = _mapping(value, "build.env")
    result: dict[str, str] = {}
    for key, item in mapping.items():
        if not isinstance(key, str) or not key:
            raise BuildError("build.env: keys must be non-empty strings")
        if isinstance(item, bool):
            result[key] = "true" if item else "false"
        elif isinstance(item, (str, int, float)):
            result[key] = str(item)
        else:
            raise BuildError(
                "build.env[%s]: expected a string, number or boolean, got %s"
                % (key, type(item).__name__),
            )
    return result


_INPUT_KEYS = frozenset({"path", "kind", "optional", "ignore"})
_INPUT_KINDS = ("file", "tree")


def _build_inputs(value: Any) -> tuple[BuildInput, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise BuildError("build.inputs must be an array")
    inputs: list[BuildInput] = []
    for index, item in enumerate(value):
        where = "build.inputs[%d]" % index
        mapping = _mapping(item, where)
        unknown = sorted(set(mapping) - _INPUT_KEYS)
        if unknown:
            raise BuildError("%s: unknown key(s): %s" % (where, ", ".join(unknown)))
        raw_path = mapping.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise BuildError("%s.path must be a non-empty string" % where)
        kind = mapping.get("kind", "tree")
        if kind not in _INPUT_KINDS:
            raise BuildError("%s.kind must be one of: file, tree" % where)
        optional = mapping.get("optional", False)
        if not isinstance(optional, bool):
            raise BuildError("%s.optional must be a boolean" % where)
        raw_ignore = mapping.get("ignore")
        ignore: tuple[str, ...] = ()
        if raw_ignore is not None:
            if not isinstance(raw_ignore, (list, tuple)):
                raise BuildError("%s.ignore must be an array" % where)
            patterns: list[str] = []
            for pattern_index, pattern in enumerate(raw_ignore):
                if not isinstance(pattern, str) or not pattern.strip():
                    raise BuildError(
                        "%s.ignore[%d]: expected a non-empty string"
                        % (where, pattern_index)
                    )
                patterns.append(pattern)
            ignore = tuple(patterns)
        inputs.append(
            BuildInput(path=raw_path, kind=kind, optional=optional, ignore=ignore)
        )
    return tuple(inputs)


def _toolchain_components(value: Any) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_TOOLCHAIN_COMPONENTS
    if not isinstance(value, (list, tuple)):
        raise BuildError("build.toolchain_components must be an array")
    components: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise BuildError(
                "build.toolchain_components[%d]: expected a non-empty string" % index
            )
        components.append(item)
    if not components:
        raise BuildError("build.toolchain_components must not be empty")
    return tuple(components)


def parse_build_section(data: Mapping[str, Any], manifest_path: Path | str) -> BuildConfig:
    """Interpret a manifest dict into a :class:`BuildConfig`.

    Relative ``workdir`` values are resolved against the manifest directory;
    relative ``artifact`` values are resolved against the work directory by the
    executor (``artifact`` keeps its manifest spelling here so reports and cache
    payloads stay stable across machines).
    """
    manifest_path = Path(manifest_path)
    raw_build = data.get("build")
    if raw_build is None:
        raw_build = {}
    build = _mapping(raw_build, "build")

    raw_commands = build.get("commands")
    commands: list[Command] = []
    if raw_commands is not None:
        if not isinstance(raw_commands, (list, tuple)):
            raise BuildError("build.commands must be an array")
        for index, item in enumerate(raw_commands):
            commands.append(_command(item, index))

    raw_workdir = build.get("workdir", ".")
    if not isinstance(raw_workdir, str) or not raw_workdir.strip():
        raise BuildError("build.workdir must be a non-empty string")
    workdir = Path(raw_workdir)
    if not workdir.is_absolute():
        workdir = manifest_path.parent / workdir
    workdir = workdir.resolve()

    raw_artifact = build.get("artifact")
    artifact: str | None = None
    if raw_artifact is not None:
        if not isinstance(raw_artifact, str) or not raw_artifact.strip():
            raise BuildError("build.artifact must be a non-empty string")
        candidate = Path(raw_artifact)
        if candidate.is_absolute():
            raise BuildError("build.artifact must be relative to build.workdir")
        artifact = raw_artifact

    env = _env(build.get("env"))
    inputs = _build_inputs(build.get("inputs"))
    toolchain_components = _toolchain_components(build.get("toolchain_components"))

    # A build contract is either fully declared or absent.  Commands without an
    # artifact can never produce a verifiable result, and an artifact without
    # commands cannot be produced by the workbench.
    if commands and not artifact:
        raise BuildError(
            "build.artifact is required when build.commands is declared"
            " (steps that only live in scripts stay scripts, not manifests)"
        )
    if artifact and not commands:
        raise BuildError("build.commands is required when build.artifact is declared")

    if artifact is not None:
        escaped = (workdir / artifact).resolve()
        try:
            escaped.relative_to(workdir)
        except ValueError:
            raise BuildError(
                "build.artifact must stay inside build.workdir: %s" % artifact
            ) from None

    raw_timeout = build.get("timeout_s", DEFAULT_TIMEOUT_S)
    if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, (int, float)):
        raise BuildError("build.timeout_s must be a number")
    timeout_s = float(raw_timeout)
    if timeout_s <= 0:
        raise BuildError("build.timeout_s must be greater than zero")

    return BuildConfig(
        commands=tuple(commands),
        workdir=workdir,
        artifact=artifact,
        env=env,
        timeout_s=timeout_s,
        raw=dict(build),
        inputs=inputs,
        toolchain_components=toolchain_components,
    )


def command_display(command: Command) -> str:
    """Human-readable, log/report friendly rendering of a command."""
    if isinstance(command, str):
        return command
    return subprocess.list2cmdline(list(command))
