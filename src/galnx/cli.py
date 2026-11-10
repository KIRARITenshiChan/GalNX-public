"""Command line entry point for the GalNX workbench."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, doctor, engines as engines_layer, input as input_layer, manifest as manifest_module, package as package_layer, preflight
from . import batch as batch_layer
from . import build as build_layer
from .package import nsp as nsp_layer
from .engines import source as engines_source
from .payload import cli as payload_cli
from .doctor import Check

ICONS = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}


def force_utf8_stdio() -> None:
    """Make CLI output UTF-8 regardless of the Windows console/page encoding.

    JSON payloads are dumped with ``ensure_ascii=False``, so on a cp936/cp1252
    Windows host redirected stdout would otherwise receive non-UTF-8 bytes.
    ``reconfigure`` is skipped for streams that do not support it (pytest capture).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            continue


def render(checks: list[Check]) -> None:
    width = max((len(c.name) for c in checks), default=0)
    for c in checks:
        icon = ICONS.get(c.status, c.status.upper())
        print("[%s] %s  %s" % (icon, c.name.ljust(width), c.detail))
        if c.hint and c.status in ("fail", "warn"):
            print("       hint: %s" % c.hint)


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = doctor.run_doctor()
    if args.json:
        print(doctor.dumps_json({"version": __version__, **doctor.summarise(checks)}))
    else:
        render(checks)
        fails = sum(1 for c in checks if c.status == "fail")
        warns = sum(1 for c in checks if c.status == "warn")
        print("\n%d checks: %d fail, %d warn" % (len(checks), fails, warns))
    return 1 if any(c.status == "fail" for c in checks) else 0


def cmd_preflight(args: argparse.Namespace) -> int:
    checks = preflight.run_preflight(Path(args.manifest))
    if args.json:
        print(json.dumps({"version": __version__, **preflight.summarise(checks)}, indent=2, ensure_ascii=False))
    else:
        render(checks)
    return 0 if not any(c.status == "fail" for c in checks) else 2


def cmd_input_list(args: argparse.Namespace) -> int:
    profiles = [profile for profile in (input_layer.get_builtin(name) for name in input_layer.list_builtin_names()) if profile is not None]
    if args.json:
        print(json.dumps(
            {"version": __version__, "builtin_profiles": [input_layer.profile_summary(profile) for profile in profiles]},
            indent=2,
            ensure_ascii=False,
        ))
        return 0
    print("Built-in input profiles:")
    name_width = max((len(profile.name) for profile in profiles), default=4)
    for profile in profiles:
        hotkeys = ", ".join("%s=%s" % (name, input_layer.format_combo(combo)) for name, combo in profile.hotkeys.items()) or "none"
        print("  %s  actions=%d  hotkeys=%s" % (profile.name.ljust(name_width), len(profile.button_map), hotkeys))
        print("  %s  %s" % ("".ljust(name_width), profile.description))
    print("")
    print("%d built-in profiles; validate a YAML profile with: galnx input validate <file>" % len(profiles))
    return 0


def cmd_input_validate(args: argparse.Namespace) -> int:
    result = input_layer.check_profile_file(Path(args.profile))
    if args.json:
        print(json.dumps({"version": __version__, **result.to_json()}, indent=2, ensure_ascii=False))
        return 0 if result.ok else 2
    checks: list[Check] = []
    if result.profile is None:
        for error in result.errors or ("cannot load input profile",):
            checks.append(Check("profile.error", "fail", error, "see docs/input/README.md"))
    else:
        profile = result.profile
        checks.append(Check("profile.parse", "ok", result.path))
        checks.append(Check("profile.name", "ok", profile.name, profile.description))
        checks.append(Check(
            "profile.button_map",
            "ok",
            "%d semantic actions, %d button bindings" % (len(profile.button_map), sum(len(buttons) for buttons in profile.button_map.values())),
        ))
        checks.append(Check(
            "profile.hotkeys",
            "ok",
            ", ".join("%s=%s" % (name, input_layer.format_combo(combo)) for name, combo in profile.hotkeys.items()) or "none",
        ))
        checks.append(Check(
            "profile.mouse",
            "ok",
            ", ".join("%s=%s" % (function, button) for function, button in profile.mouse.items()) or "none",
        ))
        if profile.adapter_defaults:
            checks.append(Check("profile.adapter_defaults", "ok", ", ".join(sorted(profile.adapter_defaults))))
        for error in result.errors:
            checks.append(Check("profile.conflicts", "fail", error))
        for warning in result.warnings:
            checks.append(Check("profile.conflicts", "warn", warning))
        checks.append(Check("profile.result", "ok" if result.ok else "fail", "valid input profile" if result.ok else "profile has errors"))
    render(checks)
    fails = sum(1 for check in checks if check.status == "fail")
    warns = sum(1 for check in checks if check.status == "warn")
    print("")
    print("%d checks: %d fail, %d warn" % (len(checks), fails, warns))
    return 0 if fails == 0 else 2


def _pkg_check(check_id: str, status: str, detail: str = "", hint: str = ""):
    return package_layer.Check(id=check_id, name=check_id, status=status, detail=detail, hint=hint)

def _package_issue_checks(issues) -> list:
    checks = []
    for issue in issues:
        status = "fail" if issue.is_error else "warn"
        checks.append(_pkg_check("%s.%s" % ("package", issue.field), status, issue.message))
    return checks


def _icon_summary(icon_path):
    if icon_path is None:
        return None
    try:
        data = Path(icon_path).read_bytes()
    except OSError:
        return None
    dims = package_layer.jpeg_dimensions(data)
    kind = "JPEG"
    if dims is None:
        dims = package_layer.bmp_dimensions(data)
        kind = "BMP"
    if dims is None:
        return None
    return "%dx%d %s, %d bytes" % (dims[0], dims[1], kind, len(data))


def _registry_checks(metadata, registry_path: str) -> list:
    checks = []
    try:
        registry = package_layer.load_registry(Path(registry_path), missing_ok=False)
    except package_layer.RegistryError as exc:
        checks.append(_pkg_check("package.registry", "fail", str(exc)))
        return checks
    checks.append(_pkg_check(
        "package.registry", "ok", "%d entries in %s" % (len(registry), registry.path)))
    title_id = metadata.formatted_title_id()
    if title_id:
        for issue in registry.conflicts_for(title_id):
            status = "fail" if issue.is_error else "warn"
            checks.append(_pkg_check("package.registry.conflict", status, issue.message))
        if registry.find(title_id) is None:
            checks.append(_pkg_check(
                "package.registry.entry", "warn", "title id %s is not registered yet" % title_id))
        else:
            checks.append(_pkg_check(
                "package.registry.entry", "ok", "title id %s is registered" % title_id))
    return checks


def _plan_checks(metadata, args: argparse.Namespace) -> list:
    checks = []
    checks.append(_pkg_check(
        "package.type", "ok", metadata.package_type.value, metadata.package_type.label))
    title_text = metadata.formatted_title_id()
    if title_text:
        checks.append(_pkg_check(
            "package.title_id", "ok", "%s (%s)" % (title_text, package_layer.classify(title_text).value)))
    issues = metadata.validate()
    fail_fields = {issue.field for issue in issues if issue.is_error}
    try:
        version_code = metadata.version_code()
    except package_layer.PackageMetadataError:
        version_code = None
    if version_code is not None and "version" not in fail_fields:
        checks.append(_pkg_check(
            "package.version", "ok", "%s (version code 0x%06X)" % (metadata.version, version_code)))
    if "icon" not in fail_fields:
        summary = _icon_summary(metadata.icon_file())
        if summary is not None:
            checks.append(_pkg_check("package.icon", "ok", summary))
    if "romfs_dir" not in fail_fields:
        romfs = metadata.romfs_path()
        if romfs is not None and romfs.is_dir():
            count = sum(1 for child in romfs.rglob("*") if child.is_file())
            checks.append(_pkg_check(
                "package.romfs", "ok", "%s (%d files)" % (romfs, count)))
    checks.extend(_package_issue_checks(issues))
    if args.registry:
        checks.extend(_registry_checks(metadata, args.registry))
    ok = not any(check.status == "fail" for check in checks)
    checks.append(_pkg_check(
        "package.result", "ok" if ok else "fail",
        "package plan is consistent" if ok else "package plan has errors"))
    return checks


def cmd_package_plan(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    data, errors = manifest_module.load_and_validate(manifest_path)
    checks = []
    metadata = None
    if data is None or errors:
        for error in errors or ("manifest could not be loaded",):
            checks.append(_pkg_check("manifest", "fail", error))
    else:
        try:
            metadata = package_layer.PackageMetadata.from_manifest(data, manifest_path.resolve().parent)
        except package_layer.PackageMetadataError as exc:
            checks.append(_pkg_check("manifest.package", "fail", str(exc)))
        else:
            checks.append(_pkg_check("manifest", "ok", str(manifest_path)))
    if metadata is not None:
        checks.extend(_plan_checks(metadata, args))
    fails = [check for check in checks if check.status == "fail"]
    if args.json:
        print(json.dumps({
            "version": __version__,
            "manifest": str(manifest_path),
            "package": None if metadata is None else metadata.to_dict(),
            "checks": package_layer.checks_to_dict(checks),
            "ok": not fails,
            "errors": [check.detail for check in fails],
        }, indent=2, ensure_ascii=False))
        return 0 if not fails else 2
    if metadata is not None:
        print("Packing plan (%s):" % metadata.package_type.label)
        print("  title:    %s" % metadata.title_name)
        print("  author:   %s" % metadata.title_author)
        print("  version:  %s" % metadata.version)
        print("  title_id: %s" % (metadata.formatted_title_id() or "(not set)"))
        print("  icon:     %s" % (metadata.icon_path or "(none)"))
        print("  romfs:    %s" % (metadata.romfs_dir or "(none)"))
        print("  account:  %d" % metadata.startup_user_account)
        print("")
    render(checks)
    fail_count = sum(1 for check in checks if check.status == "fail")
    warn_count = sum(1 for check in checks if check.status == "warn")
    print("")
    print("%d checks: %d fail, %d warn" % (len(checks), fail_count, warn_count))
    return 0 if fail_count == 0 else 2


def cmd_package_check(args: argparse.Namespace) -> int:
    target = args.dir or args.nstool_json
    if args.dir:
        checks = package_layer.check_dir(Path(args.dir), args.type, args.title_id)
        kind = "dir"
    else:
        try:
            parsed = package_layer.load_nstool_file(Path(args.nstool_json))
        except OSError as exc:
            checks = [_pkg_check("nstool.file", "fail", "cannot read nstool output: %s" % exc)]
            parsed = None
        else:
            checks = package_layer.check_nstool(parsed, args.title_id)
        kind = "nstool"
    fails = [check for check in checks if check.status == "fail"]
    if args.json:
        print(json.dumps({
            "version": __version__,
            "kind": kind,
            "target": str(target),
            "package_type": args.type,
            "checks": package_layer.checks_to_dict(checks),
            "ok": not fails,
            "errors": [check.detail for check in fails],
        }, indent=2, ensure_ascii=False))
        return 0 if not fails else 2
    render(checks)
    fail_count = sum(1 for check in checks if check.status == "fail")
    warn_count = sum(1 for check in checks if check.status == "warn")
    print("")
    print("%d checks: %d fail, %d warn" % (len(checks), fail_count, warn_count))
    return 0 if fail_count == 0 else 2


def _engine_check(check_id: str, status: str, detail: str = "", hint: str = "") -> engines_layer.Check:
    return engines_layer.Check(id=check_id, name=check_id, status=status, detail=detail, hint=hint)


def _engine_registry(engines_dir) -> engines_layer.EngineRegistry:
    registry = engines_layer.EngineRegistry.builtin()
    for directory in engines_dir or []:
        registry.load_dir(directory)
    return registry


def cmd_engines_list(args: argparse.Namespace) -> int:
    try:
        registry = _engine_registry(args.engines_dir)
    except engines_layer.EngineRegistryError as exc:
        print("FAIL  %s" % exc)
        return 2
    summaries = registry.summary()
    if args.json:
        payload = {"version": __version__, "engines": summaries, "count": len(summaries)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("Registered engine adapters (%d):" % len(summaries))
    width = max((len(item["id"]) for item in summaries), default=0)
    for item in summaries:
        print("  %s  %-8s %-19s %-12s %-10s %s" % (
            item["id"].ljust(width),
            item["status"],
            item["target_kind"],
            item["build_backend"],
            item["default_input_profile"],
            item["license_spdx"],
        ))
    print("")
    print("Inspect one adapter with: galnx engines info <id>")
    return 0


def cmd_engines_info(args: argparse.Namespace) -> int:
    try:
        registry = _engine_registry(args.engines_dir)
    except engines_layer.EngineRegistryError as exc:
        print("FAIL  %s" % exc)
        return 2
    descriptor = registry.get(args.engine)
    if descriptor is None:
        known = ", ".join(registry.ids()) or "none"
        print("FAIL  unknown engine adapter %r (registered: %s)" % (args.engine, known))
        return 2
    adapter = engines_layer.adapter_for(descriptor)
    pinned = descriptor.pinned_version.split(" ")[0] if descriptor.pinned_version else ""
    artifact = engines_layer.format_artifact_name(descriptor, pinned)
    problems = descriptor.validate()
    if args.json:
        payload = {
            "version": __version__,
            "engine": descriptor.to_dict(),
            "adapter": {
                "class": type(adapter).__name__,
                "methods": ["plan_build", "verify_artifact", "run_spec"],
            },
            "artifact_name": artifact,
            "input_profile": descriptor.default_input_profile,
            "problems": problems,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not problems else 2
    print("Engine adapter: %s (%s)" % (descriptor.id, descriptor.display_name))
    print("  upstream:    %s" % descriptor.upstream_url)
    print("  pinned:      %s" % (descriptor.pinned_commit or "(prebuilt artifact)"))
    print("  version:     %s" % (descriptor.pinned_version or "(not recorded)"))
    print("  license:     %s %s" % (descriptor.license_spdx, descriptor.license_url))
    print("  target:      %s via %s" % (descriptor.target_kind, descriptor.build_backend))
    print("  input:       %s" % descriptor.default_input_profile)
    print("  artifact:    %s" % artifact)
    layout = descriptor.content_layout or {}
    print("  content:     mode=%s entry=%s" % (layout.get("mode", "?"), layout.get("entry", "")))
    if layout.get("destination"):
        print("               destination=%s" % layout["destination"])
    print("  adapter:     %s (plan_build, verify_artifact, run_spec)" % type(adapter).__name__)
    supported = [key for key, value in descriptor.capabilities.items() if value.get("supported")]
    print("  capabilities: %s" % (", ".join(sorted(supported)) or "none"))
    if problems:
        print("")
        print("Problems:")
        for problem in problems:
            print("  - %s" % problem)
        return 2
    return 0


def _engine_plan_checks(plan, warnings) -> list:
    descriptor = plan.descriptor
    checks = []
    checks.append(_engine_check("engine.adapter", "ok", "%s (%s)" % (descriptor.id, plan.adapter)))
    if descriptor.pinned_commit:
        checks.append(_engine_check("engine.pinned", "ok", descriptor.pinned_commit))
    else:
        checks.append(_engine_check("engine.pinned", "warn", "no pinned commit recorded (prebuilt adapter)"))
    checks.append(_engine_check("engine.license", "ok", "%s %s" % (descriptor.license_spdx, descriptor.license_url)))
    for message in warnings:
        if "blocked" in message or "research" in message:
            check_id = "engine.status"
        elif "adapter_version" in message:
            check_id = "engine.adapter_version"
        else:
            check_id = "engine.warning"
        checks.append(_engine_check(check_id, "warn", message))
    checks.append(_engine_check("engine.input_profile", "ok", "%s (source: %s)" % (plan.input_profile, plan.input_profile_source)))
    checks.append(_engine_check("engine.build", "ok", "%d build steps planned (not executed)" % len(plan.steps)))
    checks.append(_engine_check("engine.artifact", "ok", plan.expected_artifact))
    checks.append(_engine_check("engine.target", "ok", "%s artifact" % descriptor.target_kind))
    fails = sum(1 for check in checks if check.status == "fail")
    if fails:
        checks.append(_engine_check("engine.result", "fail", "%d checks failed" % fails))
    else:
        checks.append(_engine_check("engine.result", "ok", "build plan ready (nothing executed)"))
    return checks


def _print_engine_plan(plan) -> None:
    descriptor = plan.descriptor
    print("Build plan (%s, %s):" % (descriptor.id, descriptor.target_kind))
    print("  engine:    %s" % descriptor.display_name)
    print("  upstream:  %s" % descriptor.upstream_url)
    print("  pinned:    %s" % (descriptor.pinned_commit or "(prebuilt artifact)"))
    print("  license:   %s" % descriptor.license_spdx)
    print("  input:     %s (source: %s)" % (plan.input_profile, plan.input_profile_source))
    print("  artifact:  %s" % plan.expected_artifact)
    spec = plan.run_spec or {}
    print("  harness:   %s load=%s args=%s" % (spec.get("harness", "?"), spec.get("load", "?"), " ".join(spec.get("arguments", []))))
    if spec.get("sdmc"):
        print("  sdmc:      %s" % spec["sdmc"])
    print("")
    for index, step in enumerate(plan.steps, 1):
        print("%d. [%s] %s" % (index, step.id, step.summary))
        if step.command:
            print("   $ %s" % step.command)
        if step.notes:
            print("   # %s" % step.notes)


def cmd_engines_plan(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    data, errors = manifest_module.load_and_validate(manifest_path, engines_dir=args.engines_dir)
    if data is None or errors:
        checks = []
        for message in errors or ["manifest is empty"]:
            checks.append(_engine_check("manifest", "fail", message))
        return _engine_plan_result(args, manifest_path, None, checks)
    checks = [_engine_check("manifest", "ok", str(manifest_path))]
    try:
        registry = _engine_registry(args.engines_dir)
        plan = engines_layer.plan_build(
            data,
            manifest_path=manifest_path,
            registry=registry,
            base_dir=manifest_path.resolve().parent,
        )
    except (engines_layer.EngineRegistryError, engines_layer.EngineDescriptorError, ValueError) as exc:
        checks.append(_engine_check("engine.adapter", "fail", str(exc)))
        return _engine_plan_result(args, manifest_path, None, checks)
    warnings = engines_layer.manifest_engine_warnings(
        data.get("engine"),
        base_dir=manifest_path.resolve().parent,
    )
    checks.extend(_engine_plan_checks(plan, warnings))
    return _engine_plan_result(args, manifest_path, plan, checks)


def _engine_plan_result(args: argparse.Namespace, manifest_path: Path, plan, checks: list) -> int:
    errors = [check.detail for check in checks if check.status == "fail"]
    warnings = [check.detail for check in checks if check.status == "warn"]
    ok = not errors
    if args.json:
        payload = {
            "version": __version__,
            "manifest": str(manifest_path),
            "ok": ok,
            "errors": errors,
            "warnings": warnings,
            "checks": [check.to_dict() for check in checks],
        }
        if plan is not None:
            payload["adapter"] = plan.adapter
            payload["engine"] = plan.descriptor.summary()
            payload["build_steps"] = [step.to_dict() for step in plan.steps]
            payload["input_profile"] = {"name": plan.input_profile, "source": plan.input_profile_source}
            payload["expected_artifact"] = plan.expected_artifact
            payload["run_spec"] = plan.run_spec
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if ok else 2
    if plan is not None:
        _print_engine_plan(plan)
        print("")
    render(checks)
    fails = sum(1 for check in checks if check.status == "fail")
    warns = sum(1 for check in checks if check.status == "warn")
    print("%d checks: %d fail, %d warn" % (len(checks), fails, warns))
    return 0 if ok else 2


def cmd_batch_run(args: argparse.Namespace) -> int:
    try:
        report = batch_layer.run_batch(
            Path(args.dir),
            manifests=args.manifest,
            recursive=args.recursive,
            skip_preflight=args.skip_preflight,
            skip_output_checks=args.skip_output_checks,
            engines_dir=args.engines_dir,
        )
        written = batch_layer.write_report(report, keep=args.keep)
    except (batch_layer.BatchError, batch_layer.ReportError) as exc:
        print("FAIL  %s" % exc)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        batch_layer.print_summary(report, written)
    return 0 if report["totals"]["fail"] == 0 else 2


def cmd_batch_diff(args: argparse.Namespace) -> int:
    try:
        diff = batch_layer.diff_reports(Path(args.before), Path(args.after))
    except (OSError, batch_layer.ReportError) as exc:
        print("FAIL  %s" % exc)
        return 2
    if args.json:
        print(json.dumps(diff, ensure_ascii=False, indent=2))
    else:
        batch_layer.print_diff(diff)
    counts = diff["counts"]
    return 2 if counts["regressed"] or counts["still_failing"] else 0


def cmd_batch_clean(args: argparse.Namespace) -> int:
    try:
        result = batch_layer.clean_reports(Path(args.dir), yes=args.yes)
    except (OSError, batch_layer.ReportError) as exc:
        print("FAIL  %s" % exc)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not result["existed"]:
        print("nothing to clean: %s" % result["path"])
    elif result["dry_run"]:
        print(
            "would remove %d file(s) under %s; pass --yes to delete"
            % (result["files"], result["path"])
        )
    else:
        print("removed %d file(s) under %s" % (result["removed"], result["path"]))
    if not result["existed"]:
        return 0
    return 0 if args.yes else 2


def cmd_batch_build(args: argparse.Namespace) -> int:
    try:
        report = batch_layer.run_batch_build(
            Path(args.dir),
            manifests=args.manifest,
            recursive=args.recursive,
            skip_preflight=args.skip_preflight,
            skip_output_checks=args.skip_output_checks,
            engines_dir=args.engines_dir,
            no_cache=args.no_cache,
            rebuild=args.rebuild,
            locked=args.locked,
        )
        written = batch_layer.write_report(report, keep=args.keep)
    except (batch_layer.BatchError, batch_layer.ReportError, build_layer.LockError) as exc:
        print("FAIL  %s" % exc)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        batch_layer.print_summary(report, written)
    return 0 if report["totals"]["fail"] == 0 else 2


def cmd_batch_lock(args: argparse.Namespace) -> int:
    root = Path(args.dir)
    try:
        if not root.is_dir():
            raise batch_layer.BatchError("batch root is not a directory: %s" % root)
        if args.manifest:
            targets = batch_layer.resolve_manifests(root, args.manifest)
        else:
            targets = batch_layer.discover_manifests(root, recursive=args.recursive)
        if not targets:
            raise batch_layer.BatchError(
                "no manifest files (*.yaml/*.yml) found under %s" % root
            )
        entries, errors = batch_layer.collect_lock_entries(
            targets, root, engines_dir=args.engines_dir
        )
        lock = build_layer.build_lock(entries)
        path = build_layer.write_lock(root, lock)
    except (batch_layer.BatchError, build_layer.LockError, OSError) as exc:
        print("FAIL  %s" % exc)
        return 2
    if args.json:
        print(json.dumps(lock, ensure_ascii=False, indent=2))
    else:
        print("lock: %s (%d project(s))" % (path, len(entries)))
        for message in errors:
            print("  warn: %s" % message)
    return 0 if not errors else 2


def cmd_build_run(args: argparse.Namespace) -> int:
    manifest = Path(args.manifest)
    root = manifest.resolve().parent
    try:
        report = batch_layer.run_batch_build(
            root,
            manifests=[manifest.name],
            no_cache=args.no_cache,
            rebuild=args.rebuild,
            engines_dir=args.engines_dir,
        )
        written = batch_layer.write_report(report, keep=batch_layer.DEFAULT_KEEP)
    except (batch_layer.BatchError, batch_layer.ReportError) as exc:
        print("FAIL  %s" % exc)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        batch_layer.print_summary(report, written)
    return 0 if report["totals"]["fail"] == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="galnx",
        description="GalNX - Nintendo Switch visual novel porting workbench",
    )
    parser.add_argument("--version", action="version", version="galnx %s" % __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check the local build/test environment")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("preflight", help="static checks for a game manifest (no build)")
    p.add_argument("--manifest", required=True, help="path to manifest YAML")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("input", help="inspect and validate input profiles")
    input_sub = p.add_subparsers(dest="input_command", required=True)

    q = input_sub.add_parser("list", help="list built-in input profiles")
    q.add_argument("--json", action="store_true", help="machine-readable output")
    q.set_defaults(func=cmd_input_list)

    q = input_sub.add_parser("validate", help="validate an input profile YAML file")
    q.add_argument("profile", help="path to input profile YAML")
    q.add_argument("--json", action="store_true", help="machine-readable output")
    q.set_defaults(func=cmd_input_validate)

    p = sub.add_parser("package", help="plan and validate NSP/NRO packaging (no packing)")
    package_sub = p.add_subparsers(dest="package_command", required=True)

    q = package_sub.add_parser("plan", help="validate manifest + package metadata and print a plan (no build)")
    q.add_argument("--manifest", required=True, help="path to manifest YAML")
    q.add_argument("--registry", default=None, help="optional title id registry JSON")
    q.add_argument("--json", action="store_true", help="machine-readable output")
    q.set_defaults(func=cmd_package_plan)

    q = package_sub.add_parser("check", help="check a staged NSP input directory or nstool output")
    source = q.add_mutually_exclusive_group(required=True)
    source.add_argument("--dir", help="staged packaging input directory (exefs/control/romfs)")
    source.add_argument("--nstool-json", help="saved nstool text output to parse")
    q.add_argument("--type", choices=[item.value for item in package_layer.PackageType],
                   default=package_layer.PackageType.SELF_CONTAINED_NSP.value)
    q.add_argument("--title-id", default=None, help="expected title id / ProgID")
    q.add_argument("--json", action="store_true", help="machine-readable output")
    q.set_defaults(func=cmd_package_check)
    nsp_layer.register(package_sub)

    p = sub.add_parser("engines", help="inspect engine adapters and plan a build (no build)")
    engines_sub = p.add_subparsers(dest="engines_command", required=True)

    q = engines_sub.add_parser("list", help="list registered engine adapters")
    q.add_argument("--engines-dir", action="append", default=None, help="extra directory of engine descriptor YAML files")
    q.add_argument("--json", action="store_true", help="machine-readable output")
    q.set_defaults(func=cmd_engines_list)

    q = engines_sub.add_parser("info", help="show one engine descriptor")
    q.add_argument("engine", help="engine adapter id (e.g. krkrsdl2)")
    q.add_argument("--engines-dir", action="append", default=None, help="extra directory of engine descriptor YAML files")
    q.add_argument("--json", action="store_true", help="machine-readable output")
    q.set_defaults(func=cmd_engines_info)

    q = engines_sub.add_parser("plan", help="print the build plan for a manifest (no build)")
    q.add_argument("--manifest", required=True, help="path to manifest YAML")
    q.add_argument("--engines-dir", action="append", default=None, help="extra directory of engine descriptor YAML files")
    q.add_argument("--json", action="store_true", help="machine-readable output")
    q.set_defaults(func=cmd_engines_plan)
    engines_source.register(engines_sub)

    payload_cli.register(sub)

    p = sub.add_parser("batch", help="batch preflight/plan across a manifest directory (no builds)")
    batch_sub = p.add_subparsers(dest="batch_command", required=True)

    q = batch_sub.add_parser("run", help="preflight and plan every manifest, write a JSON report")
    q.add_argument("--dir", required=True, help="root directory containing manifest YAML files")
    q.add_argument(
        "--manifest",
        action="append",
        default=None,
        help="explicit manifest path (relative to --dir); repeatable",
    )
    q.add_argument(
        "--recursive", action="store_true", help="also scan subdirectories for *.yaml/*.yml"
    )
    q.add_argument("--skip-preflight", action="store_true", help="skip the preflight stage")
    q.add_argument(
        "--skip-output-checks",
        action="store_true",
        help="drop build.output_dir checks (environment-specific paths)",
    )
    q.add_argument(
        "--engines-dir",
        action="append",
        default=None,
        help="extra directory of engine descriptor YAML files",
    )
    q.add_argument(
        "--keep",
        type=int,
        default=batch_layer.DEFAULT_KEEP,
        help="timestamped reports to keep under .galnx (default: %(default)s)",
    )
    q.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    q.set_defaults(func=cmd_batch_run)

    q = batch_sub.add_parser(
        "diff", help="compare two batch reports (added/fixed/regressed/still failing)"
    )
    q.add_argument("before", help="older report JSON")
    q.add_argument("after", help="newer report JSON")
    q.add_argument("--json", action="store_true", help="machine-readable diff on stdout")
    q.set_defaults(func=cmd_batch_diff)

    q = batch_sub.add_parser("clean", help="remove the .galnx report directory")
    q.add_argument("--dir", required=True, help="batch root directory")
    q.add_argument(
        "--yes", action="store_true", help="actually delete (without it nothing is removed)"
    )
    q.add_argument("--json", action="store_true", help="machine-readable output")
    q.set_defaults(func=cmd_batch_clean)

    q = batch_sub.add_parser(
        "build", help="execute build commands for every manifest and write a JSON report"
    )
    q.add_argument("--dir", required=True, help="root directory containing manifest YAML files")
    q.add_argument(
        "--manifest",
        action="append",
        default=None,
        help="explicit manifest path (relative to --dir); repeatable",
    )
    q.add_argument(
        "--recursive", action="store_true", help="also scan subdirectories for *.yaml/*.yml"
    )
    q.add_argument("--skip-preflight", action="store_true", help="skip the preflight stage")
    q.add_argument(
        "--skip-output-checks",
        action="store_true",
        help="drop build.output_dir checks (environment-specific paths)",
    )
    q.add_argument(
        "--engines-dir",
        action="append",
        default=None,
        help="extra directory of engine descriptor YAML files",
    )
    q.add_argument("--no-cache", action="store_true", help="disable the artifact cache")
    q.add_argument(
        "--rebuild", action="store_true", help="ignore cached artifacts and rebuild"
    )
    q.add_argument(
        "--locked",
        action="store_true",
        help="fail projects whose manifest/toolchain drifts from .galnx/engine-lock.json",
    )
    q.add_argument(
        "--keep",
        type=int,
        default=batch_layer.DEFAULT_KEEP,
        help="timestamped reports to keep under .galnx (default: %(default)s)",
    )
    q.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    q.set_defaults(func=cmd_batch_build)

    q = batch_sub.add_parser(
        "lock", help="write .galnx/engine-lock.json for reproducibility"
    )
    q.add_argument("--dir", required=True, help="root directory containing manifest YAML files")
    q.add_argument(
        "--manifest",
        action="append",
        default=None,
        help="explicit manifest path (relative to --dir); repeatable",
    )
    q.add_argument(
        "--recursive", action="store_true", help="also scan subdirectories for *.yaml/*.yml"
    )
    q.add_argument(
        "--engines-dir",
        action="append",
        default=None,
        help="extra directory of engine descriptor YAML files",
    )
    q.add_argument("--json", action="store_true", help="machine-readable lock on stdout")
    q.set_defaults(func=cmd_batch_lock)

    p = sub.add_parser("build", help="build a single manifest (M6-b execution)")
    build_sub = p.add_subparsers(dest="build_command", required=True)

    q = build_sub.add_parser("run", help="execute build commands for one manifest")
    q.add_argument("--manifest", required=True, help="path to manifest YAML")
    q.add_argument(
        "--engines-dir",
        action="append",
        default=None,
        help="extra directory of engine descriptor YAML files",
    )
    q.add_argument("--no-cache", action="store_true", help="disable the artifact cache")
    q.add_argument(
        "--rebuild", action="store_true", help="ignore cached artifacts and rebuild"
    )
    q.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    q.set_defaults(func=cmd_build_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdio()
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
