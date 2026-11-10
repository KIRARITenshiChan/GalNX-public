"""Game manifest loading, JSON-Schema validation and input resolution."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .paths import schema_path

SCHEMA_NAME = "game-manifest.schema.json"


def load_schema(name: str = SCHEMA_NAME) -> dict[str, Any]:
    with schema_path(name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_validator(name: str = SCHEMA_NAME) -> Draft202012Validator:
    Draft202012Validator.check_schema(load_schema(name))
    return Draft202012Validator(load_schema(name))


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Read a YAML manifest and require a mapping at the top level."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        raise ValueError("manifest is empty: %s" % p)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a YAML mapping, got %s" % type(data).__name__)
    return data


def validate(
    data: dict[str, Any],
    name: str = SCHEMA_NAME,
    base_dir: str | Path | None = None,
    engines_dir: list[str | Path] | str | Path | None = None,
) -> list[str]:
    """Return schema, input-reference, engine-registry and payload violations (empty == valid).

    Schema violations are reported first; only when the structure is valid does
    validation resolve the input section against built-in/file input profiles.
    base_dir is the directory relative profile paths are resolved against (the
    manifest directory for load_and_validate). engines_dir lists extra engine
    descriptor directories used to resolve engine.adapter values that are not
    built in (the CLI --engines-dir option).
    """
    errors = []
    for err in build_validator(name).iter_errors(data):
        location = "/".join(str(part) for part in err.absolute_path) or "<root>"
        errors.append("%s: %s" % (location, err.message))
    if not errors:
        from .input import validate_manifest_input

        errors.extend(validate_manifest_input(data.get("input"), base_dir=base_dir))
    if not errors:
        from .engines import validate_manifest_engine

        errors.extend(
            validate_manifest_engine(data.get("engine"), base_dir=base_dir, engines_dir=engines_dir)
        )
    if not errors:
        from .payload import validate_manifest_payload

        errors.extend(validate_manifest_payload(data.get("payload"), base_dir=base_dir))
    return errors


def load_and_validate(
    path: str | Path, engines_dir: list[str | Path] | str | Path | None = None
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = load_manifest(path)
    except Exception as exc:  # YAML syntax errors, missing file, ...
        return None, ["parse: %s" % exc]
    return data, validate(
        data,
        base_dir=Path(path).resolve().parent,
        engines_dir=engines_dir,
    )
