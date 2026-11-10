"""Batch JSON report writing, diffing and cleanup (M6-a).

The batch layer never executes builds. It records what the manifest,
preflight and engine-planning stages found so that two runs can be compared.
Reports are written under <root>/.galnx/ with a stable project list keyed by
the manifest path relative to the batch root.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

REPORT_SCHEMA_VERSION = 2
REPORT_DIRNAME = ".galnx"
REPORT_PREFIX = "batch-report-"
REPORT_SUFFIX = ".json"
LATEST_NAME = "latest.json"
DEFAULT_KEEP = 10
PROJECT_STATUSES = ("ok", "warn", "fail", "skipped")
BUILD_STATES = (
    "not_run",
    "not_configured",
    "executed",
    "cache_hit",
    "failed",
    "skipped",
)


class ReportError(ValueError):
    """Raised when a batch report cannot be read, written or compared."""


def utc_now() -> str:
    """Return the current UTC time as YYYY-MM-DDTHH:MM:SSZ."""

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def report_stamp(generated_at: str) -> str:
    """Turn an ISO timestamp into the compact stamp used in report filenames."""

    return str(generated_at).replace("-", "").replace(":", "")


def report_name(generated_at: str) -> str:
    """Return the timestamped report filename for generated_at."""

    return "%s%s%s" % (REPORT_PREFIX, report_stamp(generated_at), REPORT_SUFFIX)


def _round(value: float) -> float:
    return round(float(value), 4)


def build_report(
    root: Any,
    projects: Sequence[dict[str, Any]],
    duration_s: float,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Wrap the per-project results in the versioned report envelope."""

    generated = generated_at or utc_now()
    totals = {
        "total": len(projects),
        "ok": 0,
        "warn": 0,
        "fail": 0,
        "skipped": 0,
        "duration_s": _round(duration_s),
        "executed": 0,
        "not_configured": 0,
        "cache_hits": 0,
        "cache_misses": 0,
    }
    for project in projects:
        status = str(project.get("status", ""))
        if status in PROJECT_STATUSES:
            totals[status] += 1
        build_state = str(project.get("build_state", ""))
        if build_state == "executed":
            totals["executed"] += 1
        elif build_state == "not_configured":
            totals["not_configured"] += 1
        if (project.get("cache") or {}).get("hit"):
            totals["cache_hits"] += 1
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated,
        "root": Path(str(root)).resolve().as_posix(),
        "totals": totals,
        "projects": list(projects),
    }


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _write_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(path)
    except OSError as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise ReportError("cannot write report %s: %s" % (path, exc))


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    index = 2
    while True:
        candidate = path.with_name("%s_%d%s" % (stem, index, suffix))
        if not candidate.exists():
            return candidate
        index += 1


def write_report(report: dict[str, Any], keep: int = DEFAULT_KEEP) -> dict[str, Any]:
    """Write the timestamped report and latest.json, then prune old ones."""

    root = Path(str(report.get("root") or "."))
    report_dir = root / REPORT_DIRNAME
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ReportError("cannot create report directory %s: %s" % (report_dir, exc))

    filename = report_name(str(report.get("generated_at") or utc_now()))
    target = _unique_path(report_dir / filename)
    payload = _json_text(report)
    _write_text(target, payload)
    latest = report_dir / LATEST_NAME
    _write_text(latest, payload)
    removed = prune_reports(report_dir, keep=keep, protect=(target, latest))
    return {
        "path": target.as_posix(),
        "latest": latest.as_posix(),
        "pruned": [path.as_posix() for path in removed],
    }


def prune_reports(
    report_dir: Any,
    keep: int = DEFAULT_KEEP,
    protect: Iterable[Any] = (),
) -> list[Path]:
    """Delete timestamped reports beyond the newest keep files."""

    directory = Path(report_dir)
    if not directory.is_dir():
        return []
    try:
        count = max(0, int(keep))
    except (TypeError, ValueError):
        count = DEFAULT_KEEP
    protected = {Path(item).resolve() for item in protect}
    files = sorted(
        (path for path in directory.glob(REPORT_PREFIX + "*" + REPORT_SUFFIX) if path.is_file()),
        key=lambda path: path.name,
        reverse=True,
    )
    kept = {path.resolve() for path in files[:count]}
    removed: list[Path] = []
    for path in files:
        resolved = path.resolve()
        if resolved in protected or resolved in kept:
            continue
        try:
            path.unlink()
        except OSError as exc:
            raise ReportError("cannot prune report %s: %s" % (path, exc))
        removed.append(path)
    return removed


def load_report(path: Any) -> dict[str, Any]:
    """Read and sanity-check a batch report JSON file."""

    report_path = Path(path)
    try:
        text = report_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReportError("cannot read report %s: %s" % (report_path, exc))
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ReportError("invalid JSON in report %s: %s" % (report_path, exc))
    if not isinstance(payload, dict):
        raise ReportError("report %s is not a JSON object" % report_path)
    if not isinstance(payload.get("schema_version"), int):
        raise ReportError("report %s has no integer schema_version" % report_path)
    if not isinstance(payload.get("projects"), list):
        raise ReportError("report %s has no projects array" % report_path)
    return payload


def _project_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for project in report.get("projects") or []:
        if not isinstance(project, dict):
            continue
        project_path = project.get("path")
        if not isinstance(project_path, str) or not project_path:
            continue
        mapping[project_path] = project
    return mapping


def _status(project: dict[str, Any] | None) -> str:
    if not isinstance(project, dict):
        return ""
    status = project.get("status")
    return status if isinstance(status, str) else ""


def _artifact_sha256(project: dict[str, Any] | None) -> str:
    if not isinstance(project, dict):
        return ""
    artifact = project.get("artifact")
    if not isinstance(artifact, dict):
        return ""
    sha256 = artifact.get("sha256")
    return sha256 if isinstance(sha256, str) else ""


def _entry(project_path: str, after: dict[str, Any] | None, before: dict[str, Any] | None) -> dict[str, Any]:
    current = after if isinstance(after, dict) else {}
    previous = before if isinstance(before, dict) else {}
    return {
        "path": project_path,
        "name": current.get("name") or previous.get("name") or "",
        "status": _status(current),
        "previous_status": _status(previous),
        "artifact": _artifact_sha256(current) or _artifact_sha256(previous),
    }


def diff_reports(before_path: Any, after_path: Any) -> dict[str, Any]:
    """Classify projects between two reports as added/fixed/regressed/... ."""

    before = load_report(before_path)
    after = load_report(after_path)
    before_map = _project_map(before)
    after_map = _project_map(after)
    result: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "before": str(before_path),
        "after": str(after_path),
        "added": [],
        "fixed": [],
        "regressed": [],
        "still_failing": [],
        "removed": [],
        "counts": {
            "added": 0,
            "fixed": 0,
            "regressed": 0,
            "still_failing": 0,
            "removed": 0,
            "unchanged": 0,
            "skipped": 0,
            "artifact_changed": 0,
        },
    }
    for project_path in sorted(set(before_map) | set(after_map)):
        previous = before_map.get(project_path)
        current = after_map.get(project_path)
        if previous is None and current is not None:
            result["added"].append(_entry(project_path, current, None))
            continue
        if current is None and previous is not None:
            result["removed"].append(_entry(project_path, None, previous))
            continue
        if previous is None or current is None:
            continue
        previous_status = _status(previous)
        current_status = _status(current)
        previous_artifact = _artifact_sha256(previous)
        current_artifact = _artifact_sha256(current)
        if previous_artifact and current_artifact and previous_artifact != current_artifact:
            result["counts"]["artifact_changed"] += 1
        if current_status == "fail":
            bucket = "still_failing" if previous_status == "fail" else "regressed"
            result[bucket].append(_entry(project_path, current, previous))
        elif previous_status == "fail":
            result["fixed"].append(_entry(project_path, current, previous))
        elif current_status == "skipped":
            result["counts"]["skipped"] += 1
        else:
            result["counts"]["unchanged"] += 1
    for key in ("added", "fixed", "regressed", "still_failing", "removed"):
        result["counts"][key] = len(result[key])
    return result


def _count_files(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.rglob("*") if path.is_file())


def clean_reports(root: Any, yes: bool = False) -> dict[str, Any]:
    """Report on (and with yes remove) the <root>/.galnx directory."""

    root_path = Path(root)
    if not root_path.exists():
        raise ReportError("batch root does not exist: %s" % root_path)
    if not root_path.is_dir():
        raise ReportError("batch root is not a directory: %s" % root_path)
    report_dir = root_path / REPORT_DIRNAME
    if report_dir.is_symlink():
        raise ReportError("refusing to clean a symlinked report directory: %s" % report_dir)
    if report_dir.exists() and not report_dir.is_dir():
        raise ReportError("report path is not a directory: %s" % report_dir)
    result: dict[str, Any] = {
        "path": report_dir.as_posix(),
        "existed": report_dir.is_dir(),
        "dry_run": not yes,
        "files": 0,
        "removed": 0,
        "cache_files": _count_files(report_dir / "cache"),
        "logs_files": _count_files(report_dir / "logs"),
    }
    if not result["existed"]:
        return result
    files = [path for path in report_dir.rglob("*") if path.is_file()]
    result["files"] = len(files)
    result["cache_files"] = _count_files(report_dir / "cache")
    result["logs_files"] = _count_files(report_dir / "logs")
    if not yes:
        return result
    try:
        shutil.rmtree(report_dir)
    except OSError as exc:
        raise ReportError("cannot clean %s: %s" % (report_dir, exc))
    result["removed"] = len(files)
    result["dry_run"] = False
    return result


def print_summary(report: dict[str, Any], written: dict[str, Any] | None = None) -> None:
    """Print a short human-readable batch summary."""

    totals = report.get("totals") or {}
    print("batch root: %s" % report.get("root", ""))
    print(
        "%d project(s): %d ok, %d warn, %d fail, %d skipped in %.3fs"
        % (
            totals.get("total", 0),
            totals.get("ok", 0),
            totals.get("warn", 0),
            totals.get("fail", 0),
            totals.get("skipped", 0),
            float(totals.get("duration_s") or 0.0),
        )
    )
    if "cache_hits" in totals or "built" in totals:
        print(
            "cache: %d hit(s), %d miss(es); built %d"
            % (
                int(totals.get("cache_hits") or 0),
                int(totals.get("cache_misses") or 0),
                int(totals.get("built") or 0),
            )
        )
    print(
        "build: %d executed, %d not configured, %d cache hit(s)"
        % (
            int(totals.get("executed") or 0),
            int(totals.get("not_configured") or 0),
            int(totals.get("cache_hits") or 0),
        )
    )
    for project in report.get("projects") or []:
        build_state = project.get("build_state")
        state_suffix = "  build=%s" % build_state if build_state else ""
        print(
            "  [%s] %s  adapter=%s  %.3fs%s"
            % (
                str(project.get("status", "?")).upper(),
                project.get("path", ""),
                project.get("adapter") or "-",
                float(project.get("duration_s") or 0.0),
                state_suffix,
            )
        )
        for error in project.get("errors") or []:
            print("    fail: %s" % error)
    if written:
        print("report: %s" % written.get("path", ""))
        print("latest: %s" % written.get("latest", ""))
        pruned = written.get("pruned") or []
        if pruned:
            print("pruned %d old report(s)" % len(pruned))


def print_diff(diff: dict[str, Any]) -> None:
    """Print a short human-readable report diff."""

    counts = diff.get("counts") or {}
    print("batch diff: %s -> %s" % (diff.get("before", ""), diff.get("after", "")))
    for key, label in (
        ("added", "added"),
        ("fixed", "fixed"),
        ("regressed", "regressed"),
        ("still_failing", "still failing"),
        ("removed", "removed"),
    ):
        items = diff.get(key) or []
        print("%s: %d" % (label, len(items)))
        for item in items:
            print(
                "  %s  %s  [%s -> %s]"
                % (
                    item.get("path", ""),
                    item.get("name", ""),
                    item.get("previous_status") or "-",
                    item.get("status") or "-",
                )
            )
    if "artifact_changed" in counts:
        print("artifacts changed: %d" % counts.get("artifact_changed", 0))
    print("unchanged: %d, skipped: %d" % (counts.get("unchanged", 0), counts.get("skipped", 0)))
