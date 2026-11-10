"""Centralised path and environment defaults.

GalNX does not hard-code a contributor's personal directories. Every location
below can be overridden through an environment variable; when it is not set we
fall back to a conventional, machine-independent location (and, for devkitPro,
probe the two documented installer roots). Anything that is missing is reported
by `galnx doctor` with a suggestion instead of silently pointing at somebody
else's disk.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def repo_root() -> Path | None:
    """Return the GalNX repository root (directory that contains schemas/)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "schemas" / "game-manifest.schema.json").is_file():
            return parent
    return None


def schema_path(name: str = "game-manifest.schema.json") -> Path:
    """Locate a JSON schema, honouring GALNX_SCHEMA_DIR and the repo layout."""
    env_dir = os.environ.get("GALNX_SCHEMA_DIR")
    if env_dir:
        candidate = Path(env_dir) / name
        if candidate.is_file():
            return candidate
    root = repo_root()
    if root is not None:
        candidate = root / "schemas" / name
        if candidate.is_file():
            return candidate
        raise FileNotFoundError("schema not found: %s (looked in %s)" % (name, root / "schemas"))
    raise FileNotFoundError("schema not found: %s (set GALNX_SCHEMA_DIR)" % name)


def _env_path(var: str) -> Path | None:
    value = os.environ.get(var)
    return Path(value) if value else None


def _first_dir(*candidates: Path | None) -> Path | None:
    for candidate in candidates:
        if candidate is not None and candidate.is_dir():
            return candidate
    return None


def _devkitpro_default() -> Path:
    explicit = _env_path("GALNX_DEVKITPRO") or _env_path("DEVKITPRO")
    if explicit is not None:
        return explicit
    # devkitPro's own installer documents C:/devkitPro as the default root; a
    # data-drive install is common enough to be worth probing.
    found = _first_dir(
        Path("C:/devkitPro"),
        Path("D:/devkitPro"),
        Path.home() / "devkitPro",
    )
    if found is not None:
        return found
    return Path("C:/devkitPro")


def _build_root_default() -> Path:
    explicit = _env_path("GALNX_BUILD_ROOT")
    if explicit is not None:
        return explicit
    # Temporary directories are space-free on every supported platform, which
    # matters because the devkitPro make templates break on paths with spaces.
    return Path(tempfile.gettempdir()) / "galnx-build"


def _prod_keys_default() -> Path:
    explicit = _env_path("GALNX_PROD_KEYS")
    if explicit is not None:
        return explicit
    return Path.home() / ".galnx" / "prod.keys"


def _emulator(var: str, *relative: str) -> Path:
    explicit = _env_path(var)
    if explicit is not None:
        return explicit
    return Path.home().joinpath(*relative)


# --- configurable locations (all overridable through environment variables) ---
DEVKITPRO = _devkitpro_default()
BUILD_ROOT = _build_root_default()
PROD_KEYS = _prod_keys_default()
CITRON = _emulator("GALNX_CITRON", "citron", "citron.exe")
RYUJINX = _emulator("GALNX_RYUJINX", "Ryujinx", "Ryujinx.exe")
MSYS2_BASH = DEVKITPRO / "msys2" / "usr" / "bin" / "bash.exe"
