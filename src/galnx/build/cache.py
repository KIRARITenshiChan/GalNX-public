"""Content-addressed build cache (M6-b).

Cache keys are sha256 digests of a canonical JSON payload describing everything
that may change the artifact: manifest identity, engine pin, normalized build
commands, the input section, an explicit build.inputs digest, a toolchain
fingerprint (including the list of unknown components) and the host platform.
Cache entries store artifact metadata (path, size, sha256); verification
re-hashes the artifact so a tampered or deleted artifact turns into a cache miss
instead of a silent hit.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .. import paths
from .config import DEFAULT_TOOLCHAIN_COMPONENTS, BuildConfig, command_display
from .executor import compute_artifact, normalize_commands, sha256_file

CACHE_SCHEMA_VERSION = 2
CACHE_DIRNAME = (".galnx", "cache")
VERSION_TIMEOUT_S = 10.0

# Directories that never contribute to a build-input tree.
DEFAULT_IGNORED_DIRS = (".git", ".galnx")

# Tool version commands used by fingerprint_toolchain().
_TOOL_COMMAND = {
    "cmake": ("cmake", "--version"),
    "ninja": ("ninja", "--version"),
    "rustc": ("rustc", "--version"),
    "cargo": ("cargo", "--version"),
}

_TOOLCHAIN_CACHE: dict[str, str] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_version(argv: list[str] | tuple[str, ...]) -> str:
    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=VERSION_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    text = (completed.stdout or completed.stderr or "").strip()
    first = text.splitlines()[0].strip() if text else ""
    return first or "unknown"


def _find_devkit_gcc() -> str | None:
    bin_dirs: list[Path] = []
    for env_var in ("GALNX_DEVKITPRO", "DEVKITPRO"):
        value = os.environ.get(env_var)
        if value:
            bin_dirs.append(Path(value) / "devkitA64" / "bin")
    bin_dirs.append(paths.DEVKITPRO / "devkitA64" / "bin")
    candidates: list[str] = []
    for bin_dir in bin_dirs:
        candidates.append(str(bin_dir / "aarch64-none-elf-gcc.exe"))
        candidates.append(str(bin_dir / "aarch64-none-elf-gcc"))
    found = shutil.which("aarch64-none-elf-gcc")
    if found:
        candidates.append(found)
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    return None


def _find_sdl2_pc() -> Path | None:
    """Locate a devkitPro pkg-config file for SDL2 (best effort)."""
    pc_dirs: list[Path] = []
    for env_var in ("GALNX_DEVKITPRO", "DEVKITPRO"):
        value = os.environ.get(env_var)
        if value:
            root = Path(value)
            pc_dirs.append(root / "portlibs" / "switch" / "lib" / "pkgconfig")
            pc_dirs.append(root / "msys2" / "mingw64" / "lib" / "pkgconfig")
    root = paths.DEVKITPRO
    pc_dirs.append(root / "portlibs" / "switch" / "lib" / "pkgconfig")
    pc_dirs.append(root / "msys2" / "mingw64" / "lib" / "pkgconfig")
    for directory in pc_dirs:
        for name in ("sdl2.pc", "SDL2.pc"):
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def _sdl2_version() -> str:
    pc = _find_sdl2_pc()
    if pc is not None:
        try:
            for line in pc.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if stripped.startswith("Version:"):
                    value = stripped.split(":", 1)[1].strip()
                    return value or "unknown"
        except OSError:
            return "unknown"
        return "unknown"
    return _run_version(["pkg-config", "--modversion", "sdl2"])


def _ffmpeg_source_commit() -> str:
    source = os.environ.get("GALNX_FFMPEG_SRC")
    if not source:
        return "unknown"
    return _run_version(["git", "-C", source, "rev-parse", "HEAD"])


def host_platform() -> dict[str, str]:
    """Host identity that may change build output (never raises)."""
    return {
        "platform": sys.platform,
        "machine": platform.machine() or "unknown",
    }


def fingerprint_toolchain(force_refresh: bool = False) -> dict[str, str]:
    """Best-effort toolchain fingerprint; missing tools become "unknown"."""
    global _TOOLCHAIN_CACHE
    if _TOOLCHAIN_CACHE is not None and not force_refresh:
        return dict(_TOOLCHAIN_CACHE)
    gcc = _find_devkit_gcc()
    host = host_platform()
    fingerprint = {
        "devkitpro_gcc": _run_version([gcc, "--version"]) if gcc else "unknown",
        "cmake": _run_version(_TOOL_COMMAND["cmake"]),
        "ninja": _run_version(_TOOL_COMMAND["ninja"]),
        "rustc": _run_version(_TOOL_COMMAND["rustc"]),
        "cargo": _run_version(_TOOL_COMMAND["cargo"]),
        "sdl2": _sdl2_version(),
        "ffmpeg_source_commit": _ffmpeg_source_commit(),
        "host_platform": "%s-%s" % (host["platform"], host["machine"]),
    }
    _TOOLCHAIN_CACHE = dict(fingerprint)
    return dict(fingerprint)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _toolchain_section(
    fingerprint: Mapping[str, str],
    components: tuple[str, ...],
) -> dict[str, Any]:
    versions = {str(key): str(value) for key, value in dict(fingerprint).items()}
    unknown = sorted(key for key, value in versions.items() if value == "unknown")
    degraded = [
        component
        for component in components
        if versions.get(component, "unknown") == "unknown"
    ]
    return {
        "components": list(components),
        "versions": versions,
        "unknown": unknown,
        "degraded": degraded,
    }


def _is_ignored(rel: str, name: str, is_dir: bool, patterns: tuple[str, ...]) -> bool:
    for raw in patterns:
        pattern = raw.replace("\\", "/").strip()
        if not pattern:
            continue
        directory_only = pattern.endswith("/")
        pattern = pattern.rstrip("/")
        if not pattern:
            continue
        if directory_only and not is_dir:
            continue
        if fnmatch.fnmatchcase(rel, pattern) or fnmatch.fnmatchcase(name, pattern):
            return True
    return False


def _tree_entries(root: Path, ignores: tuple[str, ...]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    patterns = tuple(ignores)

    def walk(directory: Path, prefix: str) -> None:
        with os.scandir(directory) as iterator:
            children = sorted(iterator, key=lambda item: item.name.encode("utf-8"))
        for child in children:
            name = child.name
            rel = prefix + name
            try:
                is_dir = child.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            if name in DEFAULT_IGNORED_DIRS:
                continue
            if _is_ignored(rel, name, is_dir, patterns):
                continue
            if is_dir:
                walk(Path(child.path), rel + "/")
                continue
            entry: dict[str, Any] = {
                "path": rel,
                "type": "symlink" if child.is_symlink() else "file",
            }
            if entry["type"] == "symlink":
                try:
                    target = os.readlink(child.path)
                except OSError:
                    target = ""
                entry["sha256"] = hashlib.sha256(target.encode("utf-8")).hexdigest()
                entry["size"] = 0
            else:
                file_path = Path(child.path)
                entry["sha256"] = sha256_file(file_path)
                entry["size"] = file_path.stat().st_size
            entries.append(entry)

    walk(root, "")
    entries.sort(key=lambda item: str(item["path"]).encode("utf-8"))
    return entries


def _input_spec(
    raw_path: str,
    kind: str,
    optional: bool,
    ignore: tuple[str, ...],
    base: Path,
) -> dict[str, Any]:
    resolved = Path(raw_path)
    if not resolved.is_absolute():
        resolved = base / resolved
    spec: dict[str, Any] = {
        "path": Path(raw_path).as_posix(),
        "kind": kind,
        "optional": bool(optional),
        "ignore": list(ignore),
        "state": "ok",
        "digest": None,
        "entries": [],
        "bytes": 0,
    }
    if kind == "file":
        if not resolved.is_file():
            spec["state"] = "optional-missing" if optional else "missing"
            return spec
        digest = sha256_file(resolved)
        size = resolved.stat().st_size
        spec["digest"] = digest
        spec["entries"] = [
            {"path": resolved.name, "type": "file", "sha256": digest, "size": size}
        ]
        spec["bytes"] = size
        return spec
    if not resolved.is_dir():
        spec["state"] = "optional-missing" if optional else "missing"
        return spec
    try:
        entries = _tree_entries(resolved, ignore)
    except OSError:
        spec["state"] = "error"
        return spec
    spec["entries"] = entries
    spec["bytes"] = sum(int(entry["size"]) for entry in entries)
    spec["digest"] = hashlib.sha256(
        canonical_json({"kind": "tree", "entries": entries}).encode("utf-8")
    ).hexdigest()
    return spec


def _manifest_base(manifest_ref: str, root: Path | str | None) -> Path:
    manifest = Path(manifest_ref)
    if not manifest.is_absolute() and root is not None:
        manifest = Path(root) / manifest
    return manifest.resolve().parent


def build_inputs_digest(config: BuildConfig, base: Path | str) -> dict[str, Any]:
    """Deterministic digest of every build.inputs entry, relative to base."""
    base_path = Path(base)
    specs: list[dict[str, Any]] = []
    missing: list[str] = []
    unreadable: list[str] = []
    for item in getattr(config, "inputs", ()):
        spec = _input_spec(item.path, item.kind, item.optional, item.ignore, base_path)
        specs.append(spec)
        if spec["state"] == "missing":
            missing.append(str(spec["path"]))
        elif spec["state"] == "error":
            unreadable.append(str(spec["path"]))
    state = "ok"
    if missing:
        state = "missing"
    elif unreadable:
        state = "error"
    return {
        "state": state,
        "missing": missing,
        "unreadable": unreadable,
        "specs": specs,
    }


def _cache_reason_sections(
    toolchain: Mapping[str, Any],
    inputs: Mapping[str, Any],
    *,
    commands_declared: bool = False,
    inputs_declared: bool = True,
) -> tuple[list[str], list[str]]:
    """Split cache validity reasons into (blocking, degraded).

    blocking: neither reading nor writing the cache is safe. This happens when
    a required build.inputs entry is missing or unreadable, and also when a
    project declares build.commands but no build.inputs at all: without a
    declared input set the cache key cannot describe the build inputs, so a
    stale artifact could be reused after the sources changed.
    degraded: a toolchain component version is unknown. The unknown marker is
    part of the cache key and surfaced as a warning, but a local cache entry is
    still usable (the cache lives under the project root, not across machines).
    """
    blocking: list[str] = []
    degraded: list[str] = []
    if commands_declared and not inputs_declared:
        blocking.append(
            "build.inputs is not declared: cache disabled for this project"
        )
    unknown = list(toolchain.get("degraded") or [])
    if unknown:
        degraded.append(
            "degraded toolchain: unknown version for %s" % ", ".join(unknown)
        )
    missing = list(inputs.get("missing") or [])
    if missing:
        blocking.append("required build input missing: %s" % ", ".join(missing))
    unreadable = list(inputs.get("unreadable") or [])
    if unreadable:
        blocking.append("build input unreadable: %s" % ", ".join(unreadable))
    return blocking, degraded


def _cache_miss_reasons(
    toolchain: Mapping[str, Any],
    inputs: Mapping[str, Any],
    *,
    commands_declared: bool = False,
    inputs_declared: bool = True,
) -> list[str]:
    blocking, degraded = _cache_reason_sections(
        toolchain,
        inputs,
        commands_declared=commands_declared,
        inputs_declared=inputs_declared,
    )
    return blocking + degraded


def cache_payload(
    manifest_ref: str,
    data: Mapping[str, Any],
    config: BuildConfig,
    engine: Mapping[str, Any] | None = None,
    fingerprint: Mapping[str, str] | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Canonical payload whose sha256 is the cache key.

    Relative build.inputs paths resolve against the manifest directory; pass
    root (the batch/project root) when manifest_ref is itself relative.
    """
    engine_meta = {
        "adapter": str((engine or {}).get("adapter", "")),
        "pinned_commit": str((engine or {}).get("pinned_commit", "")),
        "build_backend": str((engine or {}).get("build_backend", "")),
    }
    fingerprint_map = dict(
        fingerprint if fingerprint is not None else fingerprint_toolchain()
    )
    components = tuple(
        getattr(config, "toolchain_components", DEFAULT_TOOLCHAIN_COMPONENTS)
    )
    toolchain = _toolchain_section(fingerprint_map, components)
    base = _manifest_base(manifest_ref, root)
    inputs = build_inputs_digest(config, base)
    commands_declared = bool(getattr(config, "has_commands", False) or config.commands)
    inputs_declared = bool(config.inputs)
    blocking_reasons, degraded_reasons = _cache_reason_sections(
        toolchain,
        inputs,
        commands_declared=commands_declared,
        inputs_declared=inputs_declared,
    )
    return {
        "schema": CACHE_SCHEMA_VERSION,
        "manifest": Path(manifest_ref).as_posix(),
        "engine": engine_meta,
        "build": {
            "commands": normalize_commands(config.commands),
            "workdir": config.workdir.as_posix(),
            "artifact": config.artifact or "",
            "env": dict(sorted(config.env.items())),
            "timeout_s": float(config.timeout_s),
        },
        "input": data.get("input") or {},
        "inputs": inputs,
        "toolchain": toolchain,
        "host_platform": host_platform(),
        "cache": {
            "miss_reasons": blocking_reasons + degraded_reasons,
            "blocking_reasons": blocking_reasons,
            "degraded_reasons": degraded_reasons,
            "inputs_declared": inputs_declared,
        },
    }


def cache_key(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def cache_root(root: Path | str) -> Path:
    return Path(root).joinpath(*CACHE_DIRNAME)


def entry_path(root: Path | str, key: str) -> Path:
    return cache_root(root) / key[:16] / "meta.json"


def read_cache_entry(root: Path | str, key: str) -> dict[str, Any] | None:
    path = entry_path(root, key)
    if not path.is_file():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict) or entry.get("key") != key:
        return None
    if entry.get("schema_version") != CACHE_SCHEMA_VERSION:
        return None
    return entry


def verify_cache_entry(entry: Mapping[str, Any]) -> tuple[bool, str]:
    """Check that a cache entry still points at the recorded artifact."""
    schema = entry.get("schema_version")
    if schema != CACHE_SCHEMA_VERSION:
        return False, "cache entry schema_version %r != %d" % (
            schema,
            CACHE_SCHEMA_VERSION,
        )
    artifact_abs = entry.get("artifact_abs")
    if not artifact_abs:
        return False, "cache entry has no artifact path"
    path = Path(str(artifact_abs))
    if not path.is_file():
        return False, "artifact missing: %s" % path
    recorded_size = entry.get("size")
    size = path.stat().st_size
    if recorded_size is not None and size != recorded_size:
        return False, "artifact size changed (%s -> %s bytes)" % (recorded_size, size)
    recorded_sha = str(entry.get("sha256") or "")
    digest = sha256_file(path)
    if recorded_sha and digest != recorded_sha:
        return False, "artifact sha256 changed (%.12s... -> %.12s...)" % (recorded_sha, digest)
    return True, ""


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_cache_entry(
    root: Path | str,
    key: str,
    payload: Mapping[str, Any],
    artifact: Mapping[str, Any],
    duration_s: float,
    commands: list[Mapping[str, Any]],
) -> dict[str, Any]:
    entry = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "key": key,
        "key_payload": dict(payload),
        "artifact_abs": str(artifact.get("abs_path", "")),
        "artifact_rel": str(artifact.get("path", "")),
        "size": int(artifact.get("size", 0) or 0),
        "sha256": str(artifact.get("sha256", "")),
        "created_at": utc_now(),
        "duration_s": round(float(duration_s), 4),
        "commands": [dict(command) for command in commands],
    }
    path = entry_path(root, key)
    _write_text(path, json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True))
    return entry


def artifact_from_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": str(entry.get("artifact_rel", "")),
        "abs_path": str(entry.get("artifact_abs", "")),
        "size": int(entry.get("size", 0) or 0),
        "sha256": str(entry.get("sha256", "")),
    }


def describe_artifact(artifact: Mapping[str, Any] | None) -> str:
    if not artifact:
        return "missing"
    return "%s (%s bytes, sha256 %s)" % (
        artifact.get("path", ""),
        artifact.get("size", 0),
        artifact.get("sha256", ""),
    )
