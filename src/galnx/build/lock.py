"""Engine lockfile support (M6-b): record and verify dependency pins.

``galnx batch lock`` writes ``.galnx/engine-lock.json`` with the engine pin,
toolchain fingerprint and manifest digest of every project.  ``galnx batch build
--locked`` compares the current state against that file and refuses to build a
project whose manifest, engine descriptor or toolchain drifted.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .cache import fingerprint_toolchain

LOCK_SCHEMA_VERSION = 1
LOCK_NAME = "engine-lock.json"


class LockError(ValueError):
    """Raised when the lockfile cannot be read."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lock_path(root: Path | str) -> Path:
    return Path(root) / ".galnx" / LOCK_NAME


def manifest_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def build_lock(
    entries: Mapping[str, Mapping[str, Any]],
    toolchain: Mapping[str, str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "toolchain": dict(toolchain if toolchain is not None else fingerprint_toolchain()),
        "projects": {key: dict(value) for key, value in entries.items()},
    }


def read_lock(root: Path | str) -> dict[str, Any] | None:
    path = lock_path(root)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LockError("invalid lock file %s: %s" % (path, exc)) from exc
    if not isinstance(document, dict):
        raise LockError("invalid lock file %s: top level is not an object" % path)
    if document.get("schema_version") != LOCK_SCHEMA_VERSION:
        raise LockError(
            "unsupported lock schema_version %r in %s"
            % (document.get("schema_version"), path),
        )
    if not isinstance(document.get("projects"), dict):
        raise LockError("invalid lock file %s: projects is not an object" % path)
    return document


def write_lock(root: Path | str, lock: Mapping[str, Any]) -> Path:
    path = lock_path(root)
    _write_text(path, json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True))
    return path


def _short(value: Any) -> str:
    text = str(value or "")
    return text[:8] if text else "-"


def _compare_scalar(drift: list[str], where: str, old: Any, new: Any) -> None:
    if str(old or "") == str(new or ""):
        return
    if where.startswith("toolchain.") or where == "manifest_sha256":
        drift.append("%s changed (%s -> %s)" % (where, _short(old), _short(new)))
    else:
        drift.append("%s drift (%s -> %s)" % (where, old if old else "-", new if new else "-"))


def compare_projects(
    lock: Mapping[str, Any] | None,
    entries: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Return {project: [drift message, ...]} for every project that drifted.

    A missing lock file reports every project as drifted with a single reason.
    """
    if lock is None:
        return {
            path: ["lock file missing (.galnx/engine-lock.json not found)"]
            for path in entries
        }
    locked_projects = lock.get("projects") or {}
    result: dict[str, list[str]] = {}
    for path, entry in entries.items():
        drift: list[str] = []
        locked = locked_projects.get(path)
        if not isinstance(locked, Mapping):
            drift.append("not recorded in lock file")
            result[path] = drift
            continue
        _compare_scalar(
            drift,
            "manifest_sha256",
            locked.get("manifest_sha256"),
            entry.get("manifest_sha256"),
        )
        engine = entry.get("engine") or {}
        locked_engine = locked.get("engine") or {}
        for key in ("adapter", "pinned_commit", "build_backend"):
            _compare_scalar(
                drift,
                "engine.%s" % key,
                locked_engine.get(key),
                engine.get(key),
            )
        toolchain = entry.get("toolchain") or {}
        locked_toolchain = locked.get("toolchain") or {}
        for key in sorted(set(toolchain) | set(locked_toolchain)):
            _compare_scalar(
                drift,
                "toolchain.%s" % key,
                locked_toolchain.get(key),
                toolchain.get(key),
            )
        if drift:
            result[path] = drift
    return result


def describe_drift(drift: Mapping[str, list[str]]) -> str:
    parts = []
    for path in sorted(drift):
        parts.append("%s: %s" % (path, "; ".join(drift[path])))
    return " | ".join(parts)
