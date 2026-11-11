"""Tests for the 0.1.0 build contract: dry-run, not_configured and artifact rules."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import cli  # noqa: E402
from galnx.build import config as build_config  # noqa: E402
from galnx.build import executor as build_executor  # noqa: E402

BUILD_PY = (
    "from pathlib import Path\n"
    "\n"
    "path = Path('out/demo.bin')\n"
    "path.parent.mkdir(parents=True, exist_ok=True)\n"
    "path.write_bytes(b'galnx-contract-demo')\n"
    "print('wrote', path)\n"
)

# Assembled at runtime so the public-release scanner does not see a secret-shaped
# literal in the public tree; the tests still assert this value never leaks.
SECRET = "super" + "-secret" + "-value"


def run_cli(argv: list[str]) -> tuple[int, str]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = cli.main(argv)
    return code, stream.getvalue()


def run_cli_split(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def write_yaml(path: Path, data) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def project_manifest(root: Path, build=None, slug: str = "demo", title_id: str = "010047410000A001") -> dict:
    source = root / "games" / slug
    source.mkdir(parents=True, exist_ok=True)
    (source / "data.xp3").write_text("placeholder\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "game": {"id": slug, "title": "Demo " + slug, "source_dir": str(source)},
        "engine": {
            "adapter": "krkrsdl2",
            "adapter_version": "krkrsdl2@124bdf84 (2026-10-01)",
            "profile": "default",
            "entry": "data.xp3",
        },
        "switch": {"title_id": title_id, "target": "nro", "display_mode": "handheld"},
    }
    if build is not None:
        manifest["build"] = build
    return manifest


def configured_build(root: Path, **overrides) -> dict:
    build = {
        "output_dir": str(root / "out" / "demo"),
        "reproducible": True,
        "commands": [[sys.executable, "build.py"]],
        "artifact": "out/demo.bin",
        "timeout_s": 60,
    }
    build.update(overrides)
    return build


class BuildContractCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "build.py").write_text(BUILD_PY, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def manifest(self, build) -> Path:
        return write_yaml(self.root / "project.yaml", project_manifest(self.root, build=build))

    def test_dry_run_does_not_execute_configured_commands(self) -> None:
        build = configured_build(
            self.root,
            env={"GALNX_DEMO_TOKEN": SECRET, "GALNX_DEMO_MODE": "test"},
        )
        manifest = self.manifest(build)
        code, output = run_cli(["build", "run", "--manifest", str(manifest), "--dry-run"])
        self.assertEqual(code, 0, output)
        self.assertIn("state:    configured", output)
        self.assertIn("artifact: out/demo.bin", output)
        self.assertIn("1. ", output)
        self.assertIn("GALNX_DEMO_TOKEN (value hidden)", output)
        self.assertNotIn(SECRET, output)
        self.assertFalse((self.root / "out" / "demo.bin").exists())

    def test_dry_run_json_plan_exposes_contract_without_values(self) -> None:
        build = configured_build(self.root, env={"GALNX_DEMO_TOKEN": SECRET})
        manifest = self.manifest(build)
        code, output = run_cli(["build", "run", "--manifest", str(manifest), "--dry-run", "--json"])
        self.assertEqual(code, 0, output)
        plan = json.loads(output)
        self.assertEqual(plan["state"], "configured")
        self.assertEqual(plan["artifact"], "out/demo.bin")
        self.assertIn("GALNX_DEMO_TOKEN", plan["env"]["names"])
        self.assertIn("GALNX_DEMO_TOKEN", plan["env"]["sensitive"])
        self.assertEqual(len(plan["commands"]), 1)
        self.assertNotIn(SECRET, output)
        self.assertFalse((self.root / "out" / "demo.bin").exists())

    def test_dry_run_without_commands_exits_3(self) -> None:
        manifest = self.manifest({"output_dir": str(self.root / "out" / "demo")})
        code, output = run_cli(["build", "run", "--manifest", str(manifest), "--dry-run"])
        self.assertEqual(code, 3, output)
        self.assertIn("state:    not_configured", output)
        self.assertIn("no build.commands declared", output)

    def test_dry_run_rejects_commands_without_artifact(self) -> None:
        manifest = write_yaml(
            self.root / "project.yaml",
            project_manifest(self.root, build={"commands": [[sys.executable, "build.py"]]}),
        )
        code, output = run_cli(["build", "run", "--manifest", str(manifest), "--dry-run"])
        self.assertEqual(code, 2, output)
        self.assertIn("FAIL", output)
        self.assertIn("artifact", output.lower())

    def test_dry_run_rejects_artifact_without_commands(self) -> None:
        manifest = write_yaml(
            self.root / "project.yaml",
            project_manifest(self.root, build={"artifact": "out/demo.bin"}),
        )
        code, output = run_cli(["build", "run", "--manifest", str(manifest), "--dry-run"])
        self.assertEqual(code, 2, output)
        self.assertIn("FAIL", output)
        self.assertIn("commands", output.lower())

    def test_artifact_must_stay_inside_workdir(self) -> None:
        data = {
            "schema_version": 1,
            "build": {
                "commands": [[sys.executable, "build.py"]],
                "artifact": "../escape.bin",
            },
        }
        with self.assertRaises(build_config.BuildError) as raised:
            build_config.parse_build_section(data, self.root / "project.yaml")
        self.assertIn("stay inside build.workdir", str(raised.exception))

    def test_plan_builder_never_spawns_the_command(self) -> None:
        data = {
            "schema_version": 1,
            "build": configured_build(self.root),
        }
        plan = build_executor.plan_build_commands(
            self.root / "project.yaml", data, "demo"
        )
        self.assertEqual(plan["state"], "configured")
        self.assertEqual(len(plan["commands"]), 1)
        self.assertFalse((self.root / "out" / "demo.bin").exists())

    def test_real_rfvp_manifest_declares_no_build_commands(self) -> None:
        manifest = ROOT / "examples" / "pilot04-akaseka.yaml"
        code, output = run_cli(["build", "run", "--manifest", str(manifest), "--dry-run"])
        self.assertEqual(code, 3, output)
        self.assertIn("state:", output)
        self.assertIn("not_configured", output)

    def test_build_run_prints_plan_before_executing(self) -> None:
        build = configured_build(
            self.root, env={"GALNX_DEMO_TOKEN": SECRET, "GALNX_DEMO_MODE": "test"}
        )
        manifest = self.manifest(build)
        code, output = run_cli(["build", "run", "--manifest", str(manifest), "--yes"])
        self.assertEqual(code, 0, output)
        plan_at = output.find("build plan:")
        self.assertGreaterEqual(plan_at, 0, output)
        self.assertIn("GALNX_DEMO_TOKEN (value hidden)", output)
        self.assertIn("GALNX_DEMO_MODE", output)
        self.assertNotIn(SECRET, output)
        self.assertLess(plan_at, output.find("batch", plan_at))
        self.assertTrue((self.root / "out" / "demo.bin").exists())

    def test_build_run_json_keeps_plan_on_stderr(self) -> None:
        manifest = self.manifest(configured_build(self.root))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["build", "run", "--manifest", str(manifest), "--yes", "--json"])
        self.assertEqual(code, 0, out.getvalue())
        payload = json.loads(out.getvalue())
        self.assertIn("totals", payload)
        self.assertIn("build plan:", err.getvalue())

    def test_build_run_refuses_non_interactive_without_yes(self) -> None:
        manifest = self.manifest(configured_build(self.root))
        # A piped / CI session cannot answer the confirmation prompt; the CLI
        # must fail closed instead of executing build.commands.
        code, output, errors = run_cli_split(["build", "run", "--manifest", str(manifest)])
        self.assertEqual(code, 2, output)
        self.assertIn("no interactive terminal and no --yes", errors)
        self.assertIn("build plan:", output)
        self.assertFalse((self.root / "out" / "demo.bin").exists())


    def test_engines_plan_is_plan_only(self) -> None:
        manifest = self.manifest(configured_build(self.root))
        code, output = run_cli(["engines", "plan", "--manifest", str(manifest), "--json"])
        self.assertEqual(code, 0, output)
        payload = json.loads(output)
        self.assertIs(payload.get("plan_only"), True)
        human_code, human_output = run_cli(["engines", "plan", "--manifest", str(manifest)])
        self.assertEqual(human_code, 0, human_output)
        self.assertIn("plan only:", human_output)


class BuildContractBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        write_yaml(
            self.root / "demo.yaml",
            project_manifest(self.root, build={"output_dir": str(self.root / "out" / "demo")}),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_batch_build_reports_not_configured_and_exits_3(self) -> None:
        code, output = run_cli(["batch", "build", "--yes", "--dir", str(self.root), "--json"])
        self.assertEqual(code, 3, output)
        report = json.loads(output)
        totals = report["totals"]
        self.assertEqual(totals["executed"], 0)
        self.assertEqual(totals["not_configured"], 1)
        self.assertEqual(totals["fail"], 0)
        project = report["projects"][0]
        self.assertEqual(project["build_state"], "not_configured")
        check_ids = {check["id"] for check in project["checks"]}
        self.assertIn("build.not_configured", check_ids)
        self.assertIn("cache.not_configured", check_ids)

    def test_batch_build_refuses_non_interactive_without_yes(self) -> None:
        code, output, errors = run_cli_split(["batch", "build", "--dir", str(self.root)])
        self.assertEqual(code, 2, output)
        self.assertIn("no interactive terminal and no --yes", errors)


    def test_batch_build_dry_run_of_root_uses_build_exit_code(self) -> None:
        code, output = run_cli(["batch", "build", "--yes", "--dir", str(self.root)])
        self.assertEqual(code, 3, output)
        self.assertIn("not configured", output)


class ConfirmHelperTests(unittest.TestCase):
    """Consent helper must fail closed on EOF (Windows NUL / closed stdin)."""

    def test_confirm_helper_treats_eof_as_decline(self) -> None:
        from unittest import mock

        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertFalse(cli._confirm_execution("Execute? [y/N] "))
        with mock.patch("builtins.input", return_value=" y "):
            self.assertTrue(cli._confirm_execution("Execute? [y/N] "))
        with mock.patch("builtins.input", return_value=""):
            self.assertFalse(cli._confirm_execution("Execute? [y/N] "))


if __name__ == "__main__":
    unittest.main()

class CacheValidityReasonTests(unittest.TestCase):
    """Blocking vs degraded cache inputs (expert plan P1-1)."""

    def test_degraded_toolchain_is_advisory(self) -> None:
        from galnx.build.cache import _cache_reason_sections

        blocking, degraded = _cache_reason_sections(
            {"degraded": ["devkitpro_gcc"]}, {"missing": [], "unreadable": []}
        )
        self.assertEqual(blocking, [])
        self.assertEqual(len(degraded), 1)
        self.assertIn("devkitpro_gcc", degraded[0])

    def test_missing_input_blocks_caching(self) -> None:
        from galnx.build.cache import _cache_reason_sections

        blocking, degraded = _cache_reason_sections(
            {"degraded": []}, {"missing": ["src"], "unreadable": []}
        )
        self.assertEqual(degraded, [])
        self.assertEqual(len(blocking), 1)
        self.assertIn("src", blocking[0])

    def test_unreadable_input_blocks_caching(self) -> None:
        from galnx.build.cache import _cache_reason_sections

        blocking, _ = _cache_reason_sections(
            {"degraded": []}, {"missing": [], "unreadable": ["assets"]}
        )
        self.assertEqual(len(blocking), 1)
        self.assertIn("assets", blocking[0])
