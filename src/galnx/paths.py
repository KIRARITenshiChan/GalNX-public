"""Centralised path and environment defaults.

Machine-specific paths live here so a future `galnx config` command can replace
them from a profile file. Every default can be overridden by an environment
variable, which keeps the codebase portable across the dev machines we use.
"""
from __future__ import annotations

import os
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


def _env_path(var: str, default: str) -> Path:
    return Path(os.environ.get(var, default))


# --- local machine defaults (overridable through env vars) -------------------
DEVKITPRO = _env_path("GALNX_DEVKITPRO", "D:\\devkitPro")
BUILD_ROOT = _env_path("GALNX_BUILD_ROOT", "E:\\galnx-build")
PROD_KEYS = _env_path(
    "GALNX_PROD_KEYS",
    "E:\\Othergames\\Nintendo Switch\\Ryujinx-canary\\portable\\system\\prod.keys",
)
CITRON = _env_path(
    "GALNX_CITRON",
    "E:\\Othergames\\Nintendo Switch\\Workspace\\GalNX\\workspaces\\web-02\\citron\\citron.exe",
)
RYUJINX = _env_path(
    "GALNX_RYUJINX",
    "E:\\Othergames\\Nintendo Switch\\Ryujinx-canary\\Ryujinx.exe",
)
MSYS2_BASH = DEVKITPRO / "msys2" / "usr" / "bin" / "bash.exe"
