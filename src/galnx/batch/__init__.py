"""Batch preflight, planning, builds and reporting (M6-a/M6-b).

The batch command scans a directory of game manifests, runs the existing
preflight checks and engine planning for each project in isolation, and (M6-b)
can execute the manifest build commands with an artifact cache and an engine
lockfile. It never launches emulators and never touches keys.
"""

from .report import (
    DEFAULT_KEEP,
    LATEST_NAME,
    REPORT_DIRNAME,
    REPORT_PREFIX,
    REPORT_SCHEMA_VERSION,
    ReportError,
    build_report,
    clean_reports,
    diff_reports,
    load_report,
    print_diff,
    print_summary,
    prune_reports,
    report_name,
    utc_now,
    write_report,
)
from .runner import (
    BUILD_STAGE,
    CACHE_STAGE,
    LOCK_STAGE,
    BatchError,
    EXCLUDED_DIRS,
    MANIFEST_SUFFIXES,
    STAGE_NAMES,
    build_project,
    collect_lock_entries,
    discover_manifests,
    resolve_manifests,
    run_batch,
    run_batch_build,
    run_project,
)

__all__ = [
    "BUILD_STAGE",
    "BatchError",
    "CACHE_STAGE",
    "DEFAULT_KEEP",
    "EXCLUDED_DIRS",
    "LATEST_NAME",
    "LOCK_STAGE",
    "MANIFEST_SUFFIXES",
    "REPORT_DIRNAME",
    "REPORT_PREFIX",
    "REPORT_SCHEMA_VERSION",
    "ReportError",
    "STAGE_NAMES",
    "build_project",
    "build_report",
    "clean_reports",
    "collect_lock_entries",
    "diff_reports",
    "discover_manifests",
    "load_report",
    "print_diff",
    "print_summary",
    "prune_reports",
    "report_name",
    "resolve_manifests",
    "run_batch",
    "run_batch_build",
    "run_project",
    "utc_now",
    "write_report",
]
