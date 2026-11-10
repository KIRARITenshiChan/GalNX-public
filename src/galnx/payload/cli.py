"""Command handlers for the galnx payload command (P3-a).

The handlers follow the workbench CLI conventions: JSON on stdout when --json
is passed, human-readable lines otherwise, exit code 0 when nothing failed and
2 when the plan has failed checks or the arguments are invalid.

They are registered from src/galnx/cli.py through register(subparsers). Every
cmd_* function takes an argparse.Namespace and returns an int exit code.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import __version__, manifest as manifest_module
from ..package.contract import Check, checks_to_dict
from . import keymap as keymap_module
from . import plan as plan_module

ICONS = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}


def _check(check_id: str, status: str, detail: str = "", hint: str = "") -> Check:
    return Check(id=check_id, name=check_id, status=status, detail=detail, hint=hint)


def _render(checks: list[Check]) -> None:
    width = max((len(check.name) for check in checks), default=0)
    for check in checks:
        icon = ICONS.get(check.status, check.status.upper())
        print("[%s] %s  %s" % (icon, check.name.ljust(width), check.detail))
        if check.hint and check.status in ("fail", "warn"):
            print("       hint: %s" % check.hint)


def _summary(checks: list[Check]) -> None:
    fails = sum(1 for check in checks if check.status == "fail")
    warns = sum(1 for check in checks if check.status == "warn")
    print("")
    print("%d checks: %d fail, %d warn" % (len(checks), fails, warns))


def _load_config(manifest_path: Path):
    data, errors = manifest_module.load_and_validate(manifest_path)
    if data is None or errors:
        return None, [
            _check("manifest", "fail", error)
            for error in (errors or ["manifest could not be loaded"])
        ]
    payload = data.get("payload")
    if payload is None:
        return None, [
            _check(
                "payload",
                "fail",
                "manifest has no payload section",
                "Add a payload: section to the manifest (see docs/packaging/payload.md).",
            )
        ]
    try:
        config = plan_module.load_payload_config(payload, manifest_path.resolve().parent)
    except plan_module.PayloadError as exc:
        return None, [_check("payload", "fail", str(exc))]
    return config, []


def _build(args: argparse.Namespace, config) -> plan_module.PayloadPlan:
    # "plan" exposes --link-mode while "materialize" exposes --mode; both feed
    # the same planning check so the plan reports how files would be placed.
    link_mode = (
        getattr(args, "link_mode", None)
        or getattr(args, "mode", None)
        or plan_module.DEFAULT_LINK_MODE
    )
    return plan_module.build_plan(
        config,
        source_dir=args.source_dir,
        ui_dir=args.ui_dir,
        link_mode=link_mode,
    )


def _print_plan(plan: plan_module.PayloadPlan) -> None:
    config = plan.config
    print("Payload plan: %s -> romfs:/%s" % (config.target, config.payload_dir))
    print("  payload version: %s" % config.version)
    print("  source:          %s" % (config.source_dir or "(not configured)"))
    print("  ui dir:          %s" % (config.ui_dir or "(not configured)"))
    print("  startup:         %s" % config.startup)
    print("  marker:          %s" % config.marker)
    print(
        "  payload files:   %d selected + %d generated, %d bytes"
        % (len(plan.files), len(plan.generated), plan.payload_bytes)
    )
    print("  ui files:        %d, %d bytes" % (len(plan.ui_files), plan.ui_bytes))
    print("  romfs total:     %d bytes" % plan.romfs_total_bytes)
    if plan.manifest_text:
        raw = plan.manifest_text.encode("utf-8")
        print(
            "  extraction list: %s, %d lines, %d bytes"
            % (config.manifest_name, plan.manifest_text.count("\n"), len(raw))
        )
    if plan.keymap_text is not None:
        print(
            "  keymap:          %s, %d bytes"
            % (config.keymap_file, len(plan.keymap_text.encode("utf-8")))
        )


def cmd_payload_plan(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    config, problems = _load_config(manifest_path)
    plan = None
    checks = list(problems)
    if config is not None:
        try:
            plan = _build(args, config)
        except plan_module.PayloadError as exc:
            checks = [_check("payload", "fail", str(exc))]
        else:
            checks = plan.checks
    fails = [check for check in checks if check.is_fail]
    ok = plan is not None and not fails
    if args.json:
        document = {"version": __version__, "manifest_path": str(manifest_path)}
        if plan is not None:
            document.update(plan.to_json(include_files=not args.no_files))
        else:
            document.update(
                {
                    "config": None,
                    "checks": checks_to_dict(checks),
                    "ok": False,
                    "errors": [check.detail for check in fails],
                }
            )
        print(json.dumps(document, indent=2, ensure_ascii=False))
        return 0 if ok else 2
    if plan is not None:
        _print_plan(plan)
    _render(checks)
    _summary(checks)
    return 0 if ok else 2


def cmd_payload_materialize(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    out_dir = Path(args.out)
    config, problems = _load_config(manifest_path)
    checks = list(problems)
    result = None
    plan = None
    if config is not None:
        try:
            plan = _build(args, config)
        except plan_module.PayloadError as exc:
            checks = [_check("payload", "fail", str(exc))]
        else:
            checks = list(plan.checks)
            if plan.is_ok() or args.force:
                try:
                    result = plan_module.materialize(
                        plan, out_dir, mode=args.mode, force=args.force
                    )
                except plan_module.PayloadError as exc:
                    checks.append(_check("payload-materialize", "fail", str(exc)))
                else:
                    checks.append(
                        _check(
                            "payload-materialize",
                            "ok",
                            "%d payload + %d generated + %d ui files, %d bytes -> %s"
                            % (
                                result["payload_files"],
                                result["generated_files"],
                                result["ui_files"],
                                result["bytes"],
                                result["out_dir"],
                            ),
                        )
                    )
            else:
                checks.append(
                    _check(
                        "payload-materialize",
                        "fail",
                        "plan has failed checks",
                        "Fix the failed checks or pass --force to write anyway.",
                    )
                )
    fails = [check for check in checks if check.is_fail]
    ok = result is not None and not fails
    if args.json:
        document = {
            "version": __version__,
            "manifest_path": str(manifest_path),
            "out_dir": str(out_dir),
            "result": result,
            "checks": checks_to_dict(checks),
            "ok": ok,
            "errors": [check.detail for check in fails],
        }
        print(json.dumps(document, indent=2, ensure_ascii=False))
        return 0 if ok else 2
    if result is not None:
        print("Materialized romfs in %s (%s):" % (result["out_dir"], result["mode"]))
        print("  payload files:   %d" % result["payload_files"])
        print("  generated files: %d" % result["generated_files"])
        print("  ui files:        %d" % result["ui_files"])
        print("  bytes written:   %d" % result["bytes"])
        if result["hardlinked"]:
            print("  hardlinks:       %d" % result["hardlinked"])
        if result["fallback_copy"]:
            print("  fell back to copies: %d" % result["fallback_copy"])
        print("")
    _render(checks)
    _summary(checks)
    return 0 if ok else 2


def cmd_payload_verify(args: argparse.Namespace) -> int:
    checks = [
        _check(check_id, "ok" if ok else "fail", detail)
        for check_id, ok, detail in keymap_module.verify_golden()
    ]
    if args.manifest:
        manifest_path = Path(args.manifest)
        data, errors = manifest_module.load_and_validate(manifest_path)
        if data is None or errors:
            checks.extend(
                _check("manifest", "fail", error)
                for error in (errors or ["manifest could not be loaded"])
            )
        else:
            payload = data.get("payload")
            if payload is None:
                checks.append(
                    _check("payload", "warn", "manifest has no payload section")
                )
            else:
                problems = plan_module.validate_manifest_payload(
                    payload, manifest_path.resolve().parent
                )
                if problems:
                    checks.extend(
                        _check("payload", "fail", problem) for problem in problems
                    )
                else:
                    checks.append(
                        _check(
                            "payload",
                            "ok",
                            "payload section valid (%s)" % manifest_path,
                        )
                    )
    fails = [check for check in checks if check.is_fail]
    if args.json:
        print(
            json.dumps(
                {
                    "version": __version__,
                    "manifest_path": str(args.manifest) if args.manifest else None,
                    "checks": checks_to_dict(checks),
                    "ok": not fails,
                    "errors": [check.detail for check in fails],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if not fails else 2
    _render(checks)
    _summary(checks)
    return 0 if not fails else 2


def register(subparsers) -> None:
    """Register the payload command tree on an argparse subparsers action."""
    parser = subparsers.add_parser(
        "payload",
        help="plan and assemble a self-contained NSP romfs payload (no build)",
    )
    payload_sub = parser.add_subparsers(dest="payload_command", required=True)

    p = payload_sub.add_parser(
        "plan", help="validate the manifest payload section and print the romfs plan"
    )
    p.add_argument("--manifest", required=True, help="path to manifest YAML")
    p.add_argument(
        "--source-dir", default=None, help="override payload.source_dir"
    )
    p.add_argument("--ui-dir", default=None, help="override payload.ui_dir")
    p.add_argument(
        "--link-mode",
        choices=list(plan_module.LINK_MODES),
        default=plan_module.DEFAULT_LINK_MODE,
        help="how materialize would place files (the plan itself never writes)",
    )
    p.add_argument(
        "--no-files", action="store_true", help="omit the per-file list from --json output"
    )
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_payload_plan)

    q = payload_sub.add_parser(
        "materialize", help="write the planned romfs tree to a directory"
    )
    q.add_argument("--manifest", required=True, help="path to manifest YAML")
    q.add_argument("--out", required=True, help="output romfs directory")
    q.add_argument("--source-dir", default=None, help="override payload.source_dir")
    q.add_argument("--ui-dir", default=None, help="override payload.ui_dir")
    q.add_argument(
        "--mode",
        choices=list(plan_module.LINK_MODES),
        default=plan_module.DEFAULT_LINK_MODE,
        help="copy (default), hardlink or symlink payload files",
    )
    q.add_argument(
        "--force", action="store_true", help="write despite failed checks or existing files"
    )
    q.add_argument("--json", action="store_true", help="machine-readable output")
    q.set_defaults(func=cmd_payload_materialize)

    r = payload_sub.add_parser(
        "verify",
        help="check the built-in keymap template/golden sample and an optional manifest payload section",
    )
    r.add_argument(
        "--manifest", default=None, help="optional manifest YAML whose payload section to validate"
    )
    r.add_argument("--json", action="store_true", help="machine-readable output")
    r.set_defaults(func=cmd_payload_verify)


__all__ = [
    "cmd_payload_materialize",
    "cmd_payload_plan",
    "cmd_payload_verify",
    "register",
]
