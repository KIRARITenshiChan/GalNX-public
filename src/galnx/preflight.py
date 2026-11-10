"""`galnx preflight`: static checks a game manifest must pass before any build.

The checks are read-only: they look for the source directory, validate the
title id / adapter / target combination, measure path lengths and verify the
local prerequisites (keys, build root). They never open game content and never
copy or modify the original game directory.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import manifest as manifest_mod
from . import paths
from .doctor import Check, check_build_root, check_keys

TITLE_ID_RE = re.compile(r"^01[0-9A-Fa-f]{14}$")
MAX_WINDOWS_PATH = 259


def _check_source_dir(game: dict[str, Any]) -> Check:
    raw = game.get("source_dir", "")
    path = Path(raw)
    if not path.is_dir():
        return Check("game.source_dir", "fail", raw,
                     "source directory not found (GalNX only reads it; it is never modified)")
    try:
        names = sorted(p.name for p in path.iterdir())
    except OSError as exc:
        return Check("game.source_dir", "fail", raw, "not readable: %s" % exc)
    sample = ", ".join(names[:5]) + (" ..." if len(names) > 5 else "")
    return Check("game.source_dir", "ok", "%s (%d entries: %s)" % (raw, len(names), sample))


def _check_entry(engine: dict[str, Any], source_dir: Path) -> Check:
    entry = engine.get("entry")
    if not entry:
        return Check("engine.entry", "skip", "not set", "optional; adapter profiles may define their own entry point")
    candidate = source_dir / entry if not Path(entry).is_absolute() else Path(entry)
    if candidate.exists():
        return Check("engine.entry", "ok", str(candidate))
    return Check("engine.entry", "warn", str(candidate), "declared entry file not found (adapter may still locate it)")


def _check_title_id(switch: dict[str, Any]) -> Check:
    title_id = switch.get("title_id", "")
    if isinstance(title_id, int):
        title_id = "%016X" % title_id
    if TITLE_ID_RE.match(title_id):
        return Check("switch.title_id", "ok", "0x%s" % title_id)
    return Check("switch.title_id", "fail", str(title_id),
                 "must be 16 hex chars in 0x0100000000000000-0x0fffffffffffffff (e.g. 0100A1B2C3D4E000)")


def _check_output_dir(build: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    out = str(build.get("output_dir", ""))
    if not out:
        return [Check("build.output_dir", "fail", "", "output_dir is required")]
    if " " in out:
        checks.append(Check("build.output_dir", "warn", out,
                             "prefer a space-free build path; devkitPro make templates break on spaces"))
    else:
        checks.append(Check("build.output_dir", "ok", out))
    length = len(out)
    checks.append(Check("build.output_dir.length", "ok" if length < MAX_WINDOWS_PATH else "fail",
                        "%d chars (limit %d)" % (length, MAX_WINDOWS_PATH),
                        "" if length < MAX_WINDOWS_PATH else "shorten output_dir"))
    return checks


def _check_target(switch: dict[str, Any], build: dict[str, Any]) -> Check:
    target = switch.get("target", "nro")
    if target == "nsp" and not build.get("keys_env"):
        return Check("switch.target", "warn", target, "NSP packaging needs prod.keys; pass explicit --keyset (build.keys_env is unreliable: DSH strips KEY-like vars)")
    return Check("switch.target", "ok", target)


def run_preflight(manifest_path: Path) -> list[Check]:
    checks: list[Check] = []
    data, errors = manifest_mod.load_and_validate(manifest_path)
    if data is None:
        return [Check("manifest.parse", "fail", str(manifest_path), errors[0] if errors else "cannot parse")]
    checks.append(Check("manifest.parse", "ok", str(manifest_path)))
    if errors:
        for err in errors:
            checks.append(Check("manifest.schema", "fail", err))
        return checks
    checks.append(Check("manifest.schema", "ok", "schema_version=%s" % data.get("schema_version")))

    game = data["game"]
    engine = data["engine"]
    switch = data["switch"]
    build = data["build"]

    checks.append(_check_source_dir(game))
    checks.append(_check_entry(engine, Path(game.get("source_dir", ""))))
    checks.append(_check_title_id(switch))
    checks.append(_check_target(switch, build))
    checks.extend(_check_output_dir(build))
    checks.append(check_build_root(paths.BUILD_ROOT))
    if switch.get("target") == "nsp":
        checks.append(check_keys(paths.PROD_KEYS))
    else:
        checks.append(Check("prod.keys", "skip", "NRO target does not need keys"))
    return checks


def summarise(checks: list[Check]) -> dict[str, object]:
    return {
        "checks": [c.to_json() for c in checks],
        "ok": not any(c.status == "fail" for c in checks),
        "failures": sum(1 for c in checks if c.status == "fail"),
        "warnings": sum(1 for c in checks if c.status == "warn"),
    }
