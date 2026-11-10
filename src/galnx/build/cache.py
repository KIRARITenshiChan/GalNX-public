"""Content-addressed build cache (M6-b).

Cache keys are sha256 digests of a canonical JSON payload describing everything
that may change the artifact: manifest identity, engine pin, normalized build
commands, the input section and a toolchain fingerprint.  Cache entries store
artifact metadata (path, size, sha256); verification re-hashes the artifact so a
tampered or deleted artifact turns into a cache miss instead of a silent hit.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .. import paths
from .config import BuildConfig, command_display
from .executor import compute_artifact, normalize_commands, sha256_file

CACHE_SCHEMA_VERSION = 1
CACHE_DIRNAME = (".galnx", "cache")
VERSION_TIMEOUT_S = 10.0

_TOOLCHAIN_CACHE: dict[str, str] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_version(argv: list[str]) -> str:
    try:
        completed = subprocess.run(
            argv,
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


def fingerprint_toolchain(force_refresh: bool = False) -> dict[str, str]:
    """Best-effort toolchain fingerprint; missing tools become "unknown"."""
    global _TOOLCHAIN_CACHE
    if _TOOLCHAIN_CACHE is not None and not force_refresh:
        return dict(_TOOLCHAIN_CACHE)
    gcc = _find_devkit_gcc()
    fingerprint = {
        "devkitpro_gcc": _run_version([gcc, "--version"]) if gcc else "unknown",
        "cmake": _run_version(["cmake", "--version"]),
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


def cache_payload(
    manifest_ref: str,
    data: Mapping[str, Any],
    config: BuildConfig,
    engine: Mapping[str, Any] | None = None,
    fingerprint: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Canonical payload whose sha256 is the cache key."""
    engine_meta = {
        "adapter": str((engine or {}).get("adapter", "")),
        "pinned_commit": str((engine or {}).get("pinned_commit", "")),
        "build_backend": str((engine or {}).get("build_backend", "")),
    }
    toolchain = dict(fingerprint if fingerprint is not None else fingerprint_toolchain())
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
        "toolchain": toolchain,
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
    return entry


def verify_cache_entry(entry: Mapping[str, Any]) -> tuple[bool, str]:
    """Check that a cache entry still points at the recorded artifact."""
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
