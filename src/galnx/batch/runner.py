"""Batch preflight, build-plan and build runner (M6-a/M6-b).

The runner walks manifest files, validates each one, asks the engines layer for
a build plan and (M6-b) optionally executes the manifest build commands with a
content-addressed artifact cache and an engine lockfile. Projects are isolated:
an exception while processing one project is recorded as a failed project in the
report and every remaining project is still processed.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .. import build as build_layer
from .. import engines as engines_layer
from .. import manifest as manifest_module
from .. import paths
from .. import preflight as preflight_module
from ..input import validate_manifest_input
from .report import build_report

STAGE_NAMES = ("manifest", "preflight", "engines")
MANIFEST_SUFFIXES = (".yaml", ".yml")
EXCLUDED_DIRS = frozenset({".galnx", ".git", "node_modules", "__pycache__", "workspaces"})
OUTPUT_DIR_CHECK = "build.output_dir"
BUILD_STAGE = "build"
CACHE_STAGE = "cache"
LOCK_STAGE = "lock"


class BatchError(ValueError):
    """Raised for invalid batch invocations (bad root, no manifests, ...)."""


def _round(value: float) -> float:
    return round(float(value), 4)


def discover_manifests(root: Any, recursive: bool = False) -> list[Path]:
    """Return manifest files directly under root (or recursively below it)."""

    root_path = Path(root)
    if not root_path.is_dir():
        raise BatchError("batch root is not a directory: %s" % root_path)
    if recursive:
        found: list[Path] = []
        for candidate in root_path.rglob("*"):
            if not candidate.is_file() or candidate.suffix.lower() not in MANIFEST_SUFFIXES:
                continue
            try:
                relative = candidate.relative_to(root_path)
            except ValueError:
                relative = candidate
            if any(part.lower() in EXCLUDED_DIRS for part in relative.parts[:-1]):
                continue
            found.append(candidate)
    else:
        found = [
            candidate
            for candidate in root_path.iterdir()
            if candidate.is_file() and candidate.suffix.lower() in MANIFEST_SUFFIXES
        ]
    return sorted(found, key=lambda candidate: candidate.as_posix())


def resolve_manifests(root: Any, names: Any) -> list[Path]:
    """Resolve explicit manifest arguments against the batch root."""

    root_path = Path(root)
    resolved: list[Path] = []
    for name in names:
        candidate = Path(str(name))
        if not candidate.is_absolute():
            candidate = root_path / candidate
        resolved.append(candidate)
    return resolved


def run_batch(
    root: Any,
    manifests: Any = None,
    recursive: bool = False,
    skip_preflight: bool = False,
    skip_output_checks: bool = False,
    engines_dir: Any = None,
) -> dict[str, Any]:
    """Preflight and plan every manifest, returning a complete batch report."""

    started = time.perf_counter()
    root_path = Path(root)
    if manifests:
        if not root_path.is_dir():
            raise BatchError("batch root is not a directory: %s" % root_path)
        targets = resolve_manifests(root_path, manifests)
        if not targets:
            raise BatchError("no manifest paths were given")
    else:
        targets = discover_manifests(root_path, recursive=recursive)
        if not targets:
            raise BatchError("no manifest files (*.yaml/*.yml) found under %s" % root_path)
    projects: list[dict[str, Any]] = []
    for manifest_path in targets:
        try:
            projects.append(
                run_project(
                    manifest_path,
                    root_path,
                    skip_preflight=skip_preflight,
                    skip_output_checks=skip_output_checks,
                    engines_dir=engines_dir,
                )
            )
        except Exception as exc:  # isolation boundary: never abort the batch
            projects.append(
                _failed_project(manifest_path, root_path, "unexpected batch error: %s" % exc)
            )
    duration = time.perf_counter() - started
    return build_report(root_path, projects, duration)


def run_project(
    manifest_path: Any,
    root: Any,
    *,
    skip_preflight: bool = False,
    skip_output_checks: bool = False,
    engines_dir: Any = None,
) -> dict[str, Any]:
    """Run the manifest/preflight/engines stages for a single project."""

    started = time.perf_counter()
    target = Path(manifest_path)
    stages: list[dict[str, Any]] = []
    manifest_stage, data = _timed_stage("manifest", lambda: _manifest_stage(target))
    stages.append(manifest_stage)
    plan = None
    if manifest_stage["status"] == "fail":
        stages.append(_skipped_stage("preflight", "preflight.skip", "manifest stage failed"))
        stages.append(_skipped_stage("engines", "engines.skip", "manifest stage failed"))
    else:
        preflight_stage, _ = _timed_stage(
            "preflight",
            lambda: _preflight_stage(
                data,
                skip_preflight=skip_preflight,
                skip_output_checks=skip_output_checks,
            ),
        )
        stages.append(preflight_stage)
        engines_stage, plan = _timed_stage(
            "engines", lambda: _engines_stage(target, data, engines_dir)
        )
        stages.append(engines_stage)
    checks = [check for stage in stages for check in stage["checks"]]
    errors: list[str] = []
    for check in checks:
        if check["status"] != "fail":
            continue
        detail = check.get("detail") or check.get("id") or ""
        if detail and detail not in errors:
            errors.append(detail)
    return {
        "path": _display_path(Path(root), target),
        "name": _manifest_name(data, target),
        "adapter": _manifest_adapter(data, plan),
        "status": _project_status(stages, checks),
        "stages": stages,
        "checks": checks,
        "errors": errors,
        "duration_s": _round(time.perf_counter() - started),
    }


def _display_path(root: Path, value: Path) -> str:
    try:
        return value.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        try:
            return value.resolve().as_posix()
        except OSError:
            return value.as_posix()


def _check(check_id: str, status: str, detail: str = "", hint: str = "") -> engines_layer.Check:
    return engines_layer.Check(id=check_id, status=status, detail=detail, hint=hint)


def _from_doctor(check: Any) -> engines_layer.Check:
    return engines_layer.Check(
        id=str(check.name),
        name=str(check.name),
        status=str(check.status),
        detail=str(check.detail),
        hint=str(check.hint),
    )


def _stage_status(checks: list[Any]) -> str:
    statuses = {str(check.status) for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    if statuses and statuses <= {"skip"}:
        return "skip"
    return "ok"


def _stage(name: str, checks: list[Any], duration_s: float) -> dict[str, Any]:
    return {
        "name": name,
        "status": _stage_status(checks),
        "duration_s": _round(duration_s),
        "checks": [check.to_dict() for check in checks],
    }


def _skipped_stage(name: str, check_id: str, detail: str) -> dict[str, Any]:
    return _stage(name, [_check(check_id, "skip", detail)], 0.0)


def _timed_stage(
    name: str, callback: Callable[[], tuple[list[Any], Any]]
) -> tuple[dict[str, Any], Any]:
    started = time.perf_counter()
    try:
        checks, value = callback()
    except Exception as exc:  # a single stage must not abort its project
        checks, value = [_check("stage.exception", "fail", "%s: %s" % (name, exc))], None
    return _stage(name, checks, time.perf_counter() - started), value


def _project_status(stages: list[dict[str, Any]], checks: list[dict[str, Any]]) -> str:
    statuses = {str(stage.get("status")) for stage in stages}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    if checks and all(str(check.get("status")) == "skip" for check in checks):
        return "skipped"
    return "ok"


def _failed_project(manifest_path: Path, root: Path, message: str) -> dict[str, Any]:
    target = Path(manifest_path)
    stage = _stage("manifest", [_check("stage.exception", "fail", message)], 0.0)
    stages = [
        stage,
        _skipped_stage("preflight", "preflight.skip", "manifest stage failed"),
        _skipped_stage("engines", "engines.skip", "manifest stage failed"),
    ]
    checks = [check for item in stages for check in item["checks"]]
    return {
        "path": _display_path(Path(root), target),
        "name": target.stem,
        "adapter": "",
        "status": "fail",
        "stages": stages,
        "checks": checks,
        "errors": [message],
        "duration_s": 0.0,
    }


def _manifest_name(data: Any, manifest_path: Path) -> str:
    if isinstance(data, dict):
        game = data.get("game")
        if isinstance(game, dict):
            game_id = game.get("id")
            if isinstance(game_id, str) and game_id:
                return game_id
    return manifest_path.stem


def _manifest_adapter(data: Any, plan: Any) -> str:
    if plan is not None:
        return str(plan.descriptor.id)
    if isinstance(data, dict):
        engine = data.get("engine")
        if isinstance(engine, dict):
            adapter = engine.get("adapter")
            if isinstance(adapter, str):
                return adapter
    return ""


def _manifest_stage(manifest_path: Path) -> tuple[list[Any], Any]:
    checks: list[Any] = [check for check in ()]
    try:
        data = manifest_module.load_manifest(manifest_path)
    except Exception as exc:
        checks.append(
            _check(
                "manifest.parse",
                "fail",
                "cannot load manifest: %s" % exc,
                "manifest must be a YAML mapping",
            )
        )
        return checks, None
    checks.append(_check("manifest.parse", "ok", manifest_path.name))
    schema_errors = _schema_errors(data)
    if schema_errors:
        for error in schema_errors:
            checks.append(_check("manifest.schema", "fail", error, "fix the manifest structure"))
        return checks, data
    checks.append(_check("manifest.schema", "ok", "schema_version=%s" % data.get("schema_version")))
    input_errors = validate_manifest_input(
        data.get("input"), base_dir=manifest_path.resolve().parent
    )
    if input_errors:
        for error in input_errors:
            checks.append(_check("manifest.input", "fail", error, "see docs/input/README.md"))
        return checks, data
    checks.append(_check("manifest.input", "ok", "input section resolved"))
    game = data.get("game") or {}
    switch = data.get("switch") or {}
    checks.append(
        _check(
            "manifest.game",
            "ok",
            "%s (target=%s)" % (game.get("id", "?"), switch.get("target", "?")),
        )
    )
    return checks, data


def _schema_errors(data: Any) -> list[str]:
    validator = manifest_module.build_validator()
    errors: list[str] = []
    for error in sorted(
        validator.iter_errors(data), key=lambda item: tuple(str(part) for part in item.absolute_path)
    ):
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append("%s: %s" % (location, error.message))
    return errors


def _preflight_stage(
    data: Any,
    *,
    skip_preflight: bool,
    skip_output_checks: bool,
) -> tuple[list[Any], Any]:
    if skip_preflight:
        return [_check("preflight.skipped", "skip", "disabled with --skip-preflight")], None
    game = data.get("game") or {}
    engine = data.get("engine") or {}
    switch = data.get("switch") or {}
    build = data.get("build") or {}
    checks: list[Any] = [
        _from_doctor(preflight_module._check_source_dir(game)),
        _from_doctor(preflight_module._check_entry(engine, Path(str(game.get("source_dir", ""))))),
        _from_doctor(preflight_module._check_title_id(switch)),
        _from_doctor(preflight_module._check_target(switch, build)),
    ]
    if skip_output_checks:
        checks.append(
            _check(
                OUTPUT_DIR_CHECK + ".skipped",
                "skip",
                "output_dir checks disabled with --skip-output-checks",
            )
        )
    else:
        checks.extend(_from_doctor(check) for check in preflight_module._check_output_dir(build))
    checks.append(_from_doctor(preflight_module.check_build_root(paths.BUILD_ROOT)))
    if switch.get("target") == "nsp":
        checks.append(_from_doctor(preflight_module.check_keys(paths.PROD_KEYS)))
    else:
        checks.append(_check("prod.keys", "skip", "NRO target does not need keys"))
    return checks, None


def _engines_stage(manifest_path: Path, data: Any, engines_dir: Any) -> tuple[list[Any], Any]:
    checks: list[Any] = []
    base_dir = manifest_path.resolve().parent
    engine = data.get("engine") or {}
    registry, registry_errors = engines_layer.registry_for_manifest(
        engine, base_dir=base_dir, engines_dir=engines_dir
    )
    for error in registry_errors:
        checks.append(
            _check(
                "engine.registry",
                "fail",
                str(error),
                "fix the engine descriptor path or its YAML",
            )
        )
    try:
        plan = engines_layer.plan_build(
            data,
            manifest_path=manifest_path,
            registry=registry,
            base_dir=base_dir,
        )
    except Exception as exc:
        checks.append(
            _check(
                "engine.adapter",
                "fail",
                str(exc),
                "use a built-in adapter id or register <id>.yaml under an engines directory",
            )
        )
        return checks, None
    descriptor = plan.descriptor
    checks.append(_check("engine.adapter", "ok", "%s (%s)" % (descriptor.id, plan.adapter)))
    if descriptor.pinned_commit:
        checks.append(_check("engine.pinned", "ok", descriptor.pinned_commit))
    else:
        checks.append(
            _check(
                "engine.pinned",
                "warn",
                "no pinned_commit recorded",
                "pin the upstream commit for reproducible builds",
            )
        )
    if descriptor.license_spdx:
        checks.append(_check("engine.license", "ok", descriptor.license_spdx, descriptor.license_url))
    else:
        checks.append(
            _check("engine.license", "warn", "no license recorded", descriptor.license_url)
        )
    checks.extend(_warning_checks(engine, base_dir, engines_dir))
    checks.append(
        _check(
            "engine.input_profile",
            "ok",
            "%s (%s)" % (plan.input_profile, plan.input_profile_source),
        )
    )
    checks.append(
        _check("engine.plan", "ok", "%d build step(s) planned (not executed)" % len(plan.steps))
    )
    checks.append(_check("engine.artifact", "ok", plan.expected_artifact))
    checks.append(_check("engine.result", "ok", "build plan ready; no commands executed"))
    return checks, plan


def _warning_checks(engine: Any, base_dir: Path, engines_dir: Any) -> list[Any]:
    checks: list[Any] = []
    try:
        messages = engines_layer.manifest_engine_warnings(
            engine, base_dir=base_dir, engines_dir=engines_dir
        )
    except Exception as exc:
        checks.append(_check("engine.warning", "warn", "cannot collect engine warnings: %s" % exc))
        return checks
    for message in messages:
        lowered = str(message).lower()
        if "is blocked" in lowered or "research" in lowered:
            check_id = "engine.status"
        elif "adapter_version" in lowered:
            check_id = "engine.adapter_version"
        else:
            check_id = "engine.warning"
        checks.append(_check(check_id, "warn", str(message), "see docs/engines/README.md"))
    return checks

# --- M6-b: real build execution, cache and lock ----------------------------


def run_batch_build(
    root: Any,
    manifests: Any = None,
    recursive: bool = False,
    skip_preflight: bool = False,
    skip_output_checks: bool = False,
    engines_dir: Any = None,
    *,
    no_cache: bool = False,
    rebuild: bool = False,
    locked: bool = False,
) -> dict[str, Any]:
    """Run the preflight/plan stages and then execute each project build."""

    started = time.perf_counter()
    root_path = Path(root)
    if not root_path.is_dir():
        raise BatchError("batch root is not a directory: %s" % root_path)
    if manifests is not None:
        targets = resolve_manifests(root_path, manifests)
        if not targets:
            raise BatchError("no manifest paths were given")
    else:
        targets = discover_manifests(root_path, recursive=recursive)
        if not targets:
            raise BatchError("no manifest files (*.yaml/*.yml) found under %s" % root_path)
    projects: list[dict[str, Any]] = []
    for manifest_path in targets:
        try:
            projects.append(
                build_project(
                    manifest_path,
                    root_path,
                    skip_preflight=skip_preflight,
                    skip_output_checks=skip_output_checks,
                    engines_dir=engines_dir,
                    no_cache=no_cache,
                    rebuild=rebuild,
                    locked=locked,
                )
            )
        except Exception as exc:  # isolation boundary: never abort the batch
            projects.append(
                _failed_build_project(
                    manifest_path, root_path, "unexpected batch error: %s" % exc
                )
            )
    duration = time.perf_counter() - started
    report = build_report(root_path, projects, duration)
    totals = report["totals"]
    totals["cache_hits"] = sum(1 for item in projects if (item.get("cache") or {}).get("hit"))
    totals["cache_misses"] = sum(
        1
        for item in projects
        if isinstance(item.get("cache"), dict)
        and not item["cache"].get("hit")
        and item["cache"].get("key")
    )
    totals["executed"] = sum(
        1 for item in projects if item.get("build_state") == "executed"
    )
    totals["not_configured"] = sum(
        1 for item in projects if item.get("build_state") == "not_configured"
    )
    totals["built"] = sum(
        1
        for item in projects
        if not (item.get("cache") or {}).get("hit")
        and any(
            stage.get("name") == "build" and stage.get("status") in ("ok", "fail")
            for stage in item.get("stages", [])
        )
    )
    return report


def build_project(
    manifest_path: Any,
    root: Any,
    *,
    skip_preflight: bool = False,
    skip_output_checks: bool = False,
    engines_dir: Any = None,
    no_cache: bool = False,
    rebuild: bool = False,
    locked: bool = False,
) -> dict[str, Any]:
    """Run every stage for one project and execute its build commands."""

    started = time.perf_counter()
    target = Path(manifest_path)
    root_path = Path(root)
    stages: list[dict[str, Any]] = []
    manifest_stage, data = _timed_stage("manifest", lambda: _manifest_stage(target))
    stages.append(manifest_stage)
    plan = None
    config: Any = None
    config_error = ""
    cache_value: dict[str, Any] = {"hit": False, "key": ""}
    build_commands: list[dict[str, Any]] = []
    artifact: dict[str, Any] = {}
    if manifest_stage["status"] == "fail":
        stages.append(_skipped_stage("preflight", "preflight.skip", "manifest stage failed"))
        stages.append(_skipped_stage("engines", "engines.skip", "manifest stage failed"))
        if locked:
            stages.append(_skipped_stage(LOCK_STAGE, "lock.skip", "manifest stage failed"))
        stages.append(_skipped_stage(CACHE_STAGE, "cache.skip", "manifest stage failed"))
        stages.append(_skipped_stage(BUILD_STAGE, "build.skip", "manifest stage failed"))
    else:
        preflight_stage, _ = _timed_stage(
            "preflight",
            lambda: _preflight_stage(
                data,
                skip_preflight=skip_preflight,
                skip_output_checks=skip_output_checks,
            ),
        )
        stages.append(preflight_stage)
        engines_stage, plan = _timed_stage(
            "engines", lambda: _engines_stage(target, data, engines_dir)
        )
        stages.append(engines_stage)
        try:
            config = build_layer.parse_build_section(data, target)
        except build_layer.BuildError as exc:
            config_error = str(exc)
        lock_ok = True
        if locked:
            lock_stage, _ = _timed_stage(
                LOCK_STAGE,
                lambda: _lock_stage(target, root_path, data, plan),
            )
            stages.append(lock_stage)
            lock_ok = lock_stage["status"] != "fail"
        if engines_stage["status"] == "fail":
            stages.append(_skipped_stage(CACHE_STAGE, "cache.skip", "engines stage failed"))
            stages.append(_skipped_stage(BUILD_STAGE, "build.skip", "engines stage failed"))
        elif not lock_ok:
            stages.append(_skipped_stage(CACHE_STAGE, "cache.skip", "lock check failed"))
            stages.append(_skipped_stage(BUILD_STAGE, "build.skip", "lock check failed"))
        elif config_error:
            stages.append(
                _stage(
                    CACHE_STAGE,
                    [_check("cache.config", "fail", "invalid build section: %s" % config_error)],
                    0.0,
                )
            )
            stages.append(
                _stage(
                    BUILD_STAGE,
                    [_check("build.config", "fail", "invalid build section: %s" % config_error)],
                    0.0,
                )
            )
        else:
            cache_stage, cache_value = _timed_stage(
                CACHE_STAGE,
                lambda: _cache_stage(
                    target,
                    root_path,
                    data,
                    config,
                    plan,
                    no_cache=no_cache,
                    rebuild=rebuild,
                ),
            )
            stages.append(cache_stage)
            if cache_value.get("hit"):
                artifact = _artifact_report(cache_value.get("artifact") or {})
                build_commands = [
                    _command_report(item) for item in (cache_value.get("commands") or [])
                ]
                stages.append(
                    _skipped_stage(BUILD_STAGE, "build.skipped", "cache hit, commands not executed")
                )
            else:
                build_stage, build_value = _timed_stage(
                    BUILD_STAGE,
                    lambda: _build_stage(
                        target,
                        root_path,
                        data,
                        config,
                        cache_value,
                        no_cache=no_cache,
                    ),
                )
                stages.append(build_stage)
                artifact = _artifact_report(build_value.get("artifact") or {})
                build_commands = build_value.get("commands") or []
    build_state = "not_run"
    if cache_value.get("hit"):
        build_state = "cache_hit"
    else:
        final_build = next(
            (item for item in stages if item.get("name") == BUILD_STAGE), None
        )
        if final_build is not None:
            check_ids = {str(check.get("id")) for check in final_build.get("checks", [])}
            if final_build.get("status") == "fail":
                build_state = "failed"
            elif "build.not_configured" in check_ids:
                build_state = "not_configured"
            elif final_build.get("status") in ("ok", "warn"):
                build_state = "executed"
            else:
                build_state = "skipped"
    checks = [check for stage in stages for check in stage["checks"]]
    errors: list[str] = []
    for check in checks:
        if check["status"] != "fail":
            continue
        detail = check.get("detail") or check.get("id") or ""
        if detail and detail not in errors:
            errors.append(detail)
    project: dict[str, Any] = {
        "path": _display_path(root_path, target),
        "name": _manifest_name(data, target),
        "adapter": _manifest_adapter(data, plan),
        "status": _project_status(stages, checks),
        "stages": stages,
        "checks": checks,
        "errors": errors,
        "duration_s": _round(time.perf_counter() - started),
        "cache": {
            "hit": bool(cache_value.get("hit")),
            "key": str(cache_value.get("key") or ""),
        },
        "build_state": build_state,
        "commands": build_commands,
    }
    if artifact:
        project["artifact"] = artifact
    return project


def _lock_stage(
    target: Path, root: Path, data: Any, plan: Any
) -> tuple[list[Any], Any]:
    checks: list[Any] = []
    entry = _lock_entry(target, root, data, plan)
    try:
        lock = build_layer.read_lock(root)
    except build_layer.LockError as exc:
        checks.append(
            _check("lock.invalid", "fail", str(exc), "regenerate with: galnx batch lock")
        )
        return checks, None
    drift = build_layer.compare_projects(lock, {entry["path"]: entry})
    messages = drift.get(entry["path"]) or []
    if messages:
        checks.append(
            _check(
                "lock.drift",
                "fail",
                "; ".join(messages),
                "run: galnx batch lock --dir <dir>",
            )
        )
    else:
        checks.append(
            _check("lock.verified", "ok", "lock matches manifest, engine pin and toolchain")
        )
    return checks, lock


def _lock_entry(target: Path, root: Path, data: Any, plan: Any) -> dict[str, Any]:
    path = _display_path(root, target)
    engine = {"adapter": "", "pinned_commit": "", "build_backend": ""}
    if plan is not None:
        descriptor = plan.descriptor
        engine = {
            "adapter": str(descriptor.id),
            "pinned_commit": str(descriptor.pinned_commit),
            "build_backend": str(descriptor.build_backend),
        }
    elif isinstance(data, dict):
        section = data.get("engine")
        if isinstance(section, dict):
            engine["adapter"] = str(section.get("adapter") or "")
    return {
        "path": path,
        "manifest": path,
        "engine": engine,
        "toolchain": build_layer.fingerprint_toolchain(),
        "manifest_sha256": _manifest_digest(target),
        "artifact": _artifact_value(data),
    }


def _cache_stage(
    target: Path,
    root: Path,
    data: Any,
    config: Any,
    plan: Any,
    *,
    no_cache: bool,
    rebuild: bool,
) -> tuple[list[Any], Any]:
    if not config.has_commands:
        checks = [
            _check(
                "cache.not_configured",
                "skip",
                "manifest declares no build.commands; nothing to cache",
            )
        ]
        return checks, {"hit": False, "key": ""}
    if no_cache:
        checks = [_check("cache.disabled", "skip", "cache disabled (--no-cache)")]
        return checks, {"hit": False, "key": ""}
    if rebuild:
        checks = [_check("cache.rebuild", "skip", "forced rebuild (--rebuild)")]
        return checks, {"hit": False, "key": ""}
    engine = None
    if plan is not None:
        descriptor = plan.descriptor
        engine = {
            "adapter": descriptor.id,
            "pinned_commit": descriptor.pinned_commit,
            "build_backend": descriptor.build_backend,
        }
    payload = build_layer.cache_payload(
        _display_path(root, target), data, config, engine=engine, root=root
    )
    cache_info = payload.get("cache") or {}
    blocking = list(cache_info.get("blocking_reasons") or [])
    if blocking:
        checks = [_check("cache.miss", "warn", "; ".join(blocking))]
        return checks, {"hit": False, "key": "", "payload": None}
    degraded = list(cache_info.get("degraded_reasons") or [])
    degraded_checks = (
        [_check("cache.degraded", "warn", "; ".join(degraded))] if degraded else []
    )
    key = build_layer.cache_key(payload)
    entry = build_layer.read_cache_entry(root, key)
    if entry is None:
        checks = degraded_checks + [
            _check("cache.miss", "ok", "no cached artifact for key %s" % key[:16])
        ]
        return checks, {"hit": False, "key": key, "payload": payload}
    ok, reason = build_layer.verify_cache_entry(entry)
    if not ok:
        checks = degraded_checks + [
            _check("cache.stale", "warn", reason or "cached artifact is invalid")
        ]
        return checks, {"hit": False, "key": key, "payload": payload, "stale": True}
    artifact = build_layer.artifact_from_entry(entry)
    checks = degraded_checks + [
        _check("cache.hit", "ok", build_layer.describe_artifact(artifact))
    ]
    return checks, {
        "hit": True,
        "key": key,
        "payload": payload,
        "artifact": artifact,
        "commands": list(entry.get("commands") or []),
    }


def _build_stage(
    target: Path,
    root: Path,
    data: Any,
    config: Any,
    cache_value: Any,
    *,
    no_cache: bool,
) -> tuple[list[Any], Any]:
    if not config.has_commands:
        checks = [
            _check(
                "build.not_configured",
                "skip",
                "manifest declares no build.commands; nothing was executed",
            )
        ]
        return checks, {"artifact": {}, "commands": [], "build_state": "not_configured"}
    started = time.perf_counter()
    logs_dir = root / ".galnx" / "logs"
    label = _manifest_name(data, target)
    results, ok = build_layer.run_build_commands(target, data, logs_dir, label)
    commands = [_command_report(result) for result in results]
    for item in commands:
        if item["log"]:
            item["log"] = _display_path(root, Path(item["log"]))
    checks: list[Any] = []
    for index, result in enumerate(results, start=1):
        status = "ok" if result.get("ok") else "fail"
        checks.append(
            _check(
                "build.command.%d" % index,
                status,
                str(result.get("command") or ""),
                str(result.get("log") or ""),
            )
        )
    artifact: dict[str, Any] = {}
    if not ok:
        failed = next((item for item in results if not item.get("ok")), None)
        exit_code = failed.get("exit_code") if failed is not None else None
        detail = "command failed with exit code %s" % (
            exit_code if exit_code is not None else "timeout"
        )
        checks.append(_check("build.result", "fail", detail))
        return checks, {"artifact": artifact, "commands": commands, "build_state": "failed"}
    artifact = build_layer.compute_artifact(config.workdir, config.artifact) or {}
    if not artifact:
        checks.append(
            _check(
                "build.artifact",
                "fail",
                "artifact not found: %s" % config.artifact,
                "checked relative to %s" % config.workdir,
            )
        )
        checks.append(
            _check("build.result", "fail", "build finished without the declared artifact")
        )
        return checks, {"artifact": {}, "commands": commands, "build_state": "failed"}
    checks.append(_check("build.artifact", "ok", build_layer.describe_artifact(artifact)))
    cache = cache_value if isinstance(cache_value, dict) else {}
    key = str(cache.get("key") or "")
    payload = cache.get("payload")
    if key and payload is not None and not no_cache:
        build_layer.write_cache_entry(
            root,
            key,
            payload,
            artifact,
            time.perf_counter() - started,
            commands,
        )
        checks.append(_check("build.cache", "ok", "cached artifact under key %s" % key[:16]))
    checks.append(_check("build.result", "ok", "%d command(s) succeeded" % len(results)))
    return checks, {"artifact": artifact, "commands": commands, "build_state": "executed"}


def _command_report(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"command": "", "duration_s": 0.0, "exit_code": None, "log": ""}
    exit_code = result.get("exit_code")
    if not isinstance(exit_code, int):
        exit_code = None
    return {
        "command": str(result.get("command") or ""),
        "duration_s": _round(result.get("duration_s") or 0.0),
        "exit_code": exit_code,
        "log": str(result.get("log") or ""),
    }


def _artifact_report(artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, dict) or not artifact:
        return {}
    return {
        "path": str(artifact.get("path") or ""),
        "size": int(artifact.get("size") or 0),
        "sha256": str(artifact.get("sha256") or ""),
    }


def _manifest_digest(target: Path) -> str:
    try:
        return build_layer.manifest_sha256(target)
    except OSError:
        return ""


def _artifact_value(data: Any) -> str:
    section = data.get("build") if isinstance(data, dict) else None
    if isinstance(section, dict) and isinstance(section.get("artifact"), str):
        return section["artifact"]
    return ""


def _failed_build_project(manifest_path: Path, root: Path, message: str) -> dict[str, Any]:
    target = Path(manifest_path)
    stages = [
        _stage("manifest", [_check("stage.exception", "fail", message)], 0.0),
        _skipped_stage("preflight", "preflight.skip", "manifest stage failed"),
        _skipped_stage("engines", "engines.skip", "manifest stage failed"),
        _skipped_stage(CACHE_STAGE, "cache.skip", "manifest stage failed"),
        _skipped_stage(BUILD_STAGE, "build.skip", "manifest stage failed"),
    ]
    checks = [check for item in stages for check in item["checks"]]
    return {
        "path": _display_path(root, target),
        "name": target.stem,
        "adapter": "",
        "status": "fail",
        "stages": stages,
        "checks": checks,
        "errors": [message],
        "duration_s": 0.0,
        "cache": {"hit": False, "key": ""},
        "commands": [],
    }


def collect_lock_entries(
    targets: Any,
    root: Any,
    engines_dir: Any = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Build lock entries (engine pin, toolchain, manifest digest) for targets."""

    root_path = Path(root)
    fingerprint = build_layer.fingerprint_toolchain()
    entries: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for manifest_path in targets:
        target = Path(manifest_path)
        path = _display_path(root_path, target)
        engine = {"adapter": "", "pinned_commit": "", "build_backend": ""}
        try:
            data = manifest_module.load_manifest(target)
        except Exception as exc:
            errors.append("%s: %s" % (path, exc))
            entries[path] = {
                "path": path,
                "manifest": path,
                "engine": engine,
                "toolchain": fingerprint,
                "manifest_sha256": "",
                "artifact": "",
                "error": str(exc),
            }
            continue
        section = data.get("engine") if isinstance(data, dict) else None
        if isinstance(section, dict):
            engine = {
                "adapter": str(section.get("adapter") or ""),
                "pinned_commit": str(section.get("pinned_commit") or ""),
                "build_backend": "",
            }
        try:
            registry, registry_errors = engines_layer.registry_for_manifest(
                section, base_dir=target.resolve().parent, engines_dir=engines_dir
            )
            if registry_errors:
                raise build_layer.BuildError("; ".join(registry_errors))
            plan = engines_layer.plan_build(
                data,
                manifest_path=target,
                registry=registry,
                base_dir=target.resolve().parent,
            )
            descriptor = plan.descriptor
            engine = {
                "adapter": str(descriptor.id),
                "pinned_commit": str(descriptor.pinned_commit),
                "build_backend": str(descriptor.build_backend),
            }
        except Exception as exc:
            errors.append("%s: %s" % (path, exc))
            entries[path] = {
                "path": path,
                "manifest": path,
                "engine": engine,
                "toolchain": fingerprint,
                "manifest_sha256": _manifest_digest(target),
                "artifact": _artifact_value(data),
                "error": str(exc),
            }
            continue
        entries[path] = {
            "path": path,
            "manifest": path,
            "engine": engine,
            "toolchain": fingerprint,
            "manifest_sha256": _manifest_digest(target),
            "artifact": _artifact_value(data),
        }
    return entries, errors
