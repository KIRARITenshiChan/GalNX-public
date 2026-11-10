"""Tests for the M6-b batch build/lock CLI (galnx build/batch commands)."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import cli  # noqa: E402

BUILD_PY = """import argparse
import hashlib
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
args = parser.parse_args()
out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
payload = b"galnx-m6b-demo"
out.write_bytes(payload)
print("wrote", out, hashlib.sha256(payload).hexdigest())
"""


def run_cli(argv: list[str]) -> tuple[int, str]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = cli.main(argv)
    return code, stream.getvalue()


def write_yaml(path: Path, data) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def project_manifest(root: Path, slug: str = "demo", title_id: str = "010047410000A001", **build_overrides) -> dict:
    source = root / "games" / slug
    source.mkdir(parents=True, exist_ok=True)
    (source / "data.xp3").write_text("placeholder\n", encoding="utf-8")
    build = {
        "output_dir": str(root / "out" / slug),
        "clean_workspace_before_build": True,
        "reproducible": True,
        "keys_env": "GALNX_PROD_KEYS",
        "commands": [[sys.executable, "build.py", "--out", "out/demo.bin"]],
        "artifact": "out/demo.bin",
        "timeout_s": 60,
    }
    build.update(build_overrides)
    return {
        "schema_version": 1,
        "game": {"id": slug, "title": "Demo " + slug, "source_dir": str(source)},
        "engine": {
            "adapter": "krkrsdl2",
            "adapter_version": "krkrsdl2@124bdf84 (2026-10-01)",
            "profile": "default",
            "entry": "data.xp3",
        },
        "switch": {"title_id": title_id, "target": "nro", "display_mode": "handheld"},
        "build": build,
    }


class BatchBuildCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "build.py").write_text(BUILD_PY, encoding="utf-8")
        write_yaml(self.root / "demo.yaml", project_manifest(self.root))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def build_count(self) -> int:
        return len(list((self.root / ".galnx").glob("batch-report-*.json")))

    def test_batch_build_miss_then_hit(self) -> None:
        code, output = run_cli(["batch", "build", "--dir", str(self.root), "--json"])
        self.assertEqual(code, 0, output)
        report = json.loads(output)
        totals = report["totals"]
        self.assertEqual(totals["built"], 1)
        self.assertEqual(totals["cache_hits"], 0)
        self.assertEqual(totals["cache_misses"], 1)
        project = report["projects"][0]
        self.assertEqual(project["status"], "ok")
        self.assertEqual(project["cache"]["hit"], False)
        self.assertRegex(project["cache"]["key"], r"^[0-9a-f]{64}$")
        self.assertRegex(project["artifact"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(project["artifact"]["path"], "out/demo.bin")
        self.assertTrue((self.root / "out" / "demo.bin").is_file())
        check_ids = {check["id"] for check in project["checks"]}
        self.assertIn("cache.miss", check_ids)
        self.assertIn("build.command.1", check_ids)
        self.assertIn("build.cache", check_ids)
        self.assertTrue((self.root / project["commands"][0]["log"]).is_file())
        self.assertTrue((self.root / ".galnx" / "latest.json").is_file())

        code, output = run_cli(["batch", "build", "--dir", str(self.root), "--json"])
        self.assertEqual(code, 0, output)
        hit = json.loads(output)["projects"][0]
        self.assertEqual(hit["cache"]["hit"], True)
        self.assertEqual(hit["status"], "ok")
        self.assertEqual(json.loads(output)["totals"]["built"], 0)
        self.assertIn("cache.hit", {check["id"] for check in hit["checks"]})
        self.assertGreaterEqual(self.build_count(), 2)

    def test_rebuild_and_no_cache(self) -> None:
        run_cli(["batch", "build", "--dir", str(self.root)])
        code, output = run_cli(["batch", "build", "--dir", str(self.root), "--rebuild", "--json"])
        self.assertEqual(code, 0, output)
        report = json.loads(output)
        self.assertEqual(report["totals"]["built"], 1)
        self.assertEqual(report["totals"]["cache_hits"], 0)
        ids = {check["id"] for check in report["projects"][0]["checks"]}
        self.assertIn("cache.rebuild", ids)

        code, output = run_cli(["batch", "build", "--dir", str(self.root), "--no-cache", "--json"])
        self.assertEqual(code, 0, output)
        report = json.loads(output)
        self.assertEqual(report["totals"]["built"], 1)
        ids = {check["id"] for check in report["projects"][0]["checks"]}
        self.assertIn("cache.disabled", ids)
        self.assertNotIn("build.cache", ids)

    def test_stale_cache_rebuilds_after_artifact_removed(self) -> None:
        run_cli(["batch", "build", "--dir", str(self.root)])
        (self.root / "out" / "demo.bin").unlink()
        code, output = run_cli(["batch", "build", "--dir", str(self.root), "--json"])
        self.assertEqual(code, 0, output)
        report = json.loads(output)
        project = report["projects"][0]
        self.assertEqual(project["status"], "warn")
        self.assertEqual(report["totals"]["warn"], 1)
        self.assertEqual(report["totals"]["built"], 1)
        checks = {check["id"]: check for check in project["checks"]}
        self.assertEqual(checks["cache.stale"]["status"], "warn")
        self.assertIn("artifact missing", checks["cache.stale"]["detail"])
        self.assertTrue((self.root / "out" / "demo.bin").is_file())

    def test_lock_and_locked_drift(self) -> None:
        code, output = run_cli(["batch", "lock", "--dir", str(self.root)])
        self.assertEqual(code, 0, output)
        self.assertIn("lock:", output)
        lock_file = self.root / ".galnx" / "engine-lock.json"
        self.assertTrue(lock_file.is_file())
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
        self.assertEqual(lock["schema_version"], 1)
        entry = lock["projects"]["demo.yaml"]
        self.assertEqual(entry["engine"]["adapter"], "krkrsdl2")
        self.assertRegex(entry["manifest_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(entry["artifact"], "out/demo.bin")

        code, output = run_cli(["batch", "build", "--dir", str(self.root), "--locked", "--json"])
        self.assertEqual(code, 0, output)
        self.assertIn("lock.verified", {check["id"] for check in json.loads(output)["projects"][0]["checks"]})

        drifted = project_manifest(self.root)
        drifted["build"]["env"] = {"GALNX_DEMO_SEED": "drifted"}
        write_yaml(self.root / "demo.yaml", drifted)
        code, output = run_cli(["batch", "build", "--dir", str(self.root), "--locked", "--json"])
        self.assertEqual(code, 2, output)
        report = json.loads(output)
        project = report["projects"][0]
        self.assertEqual(project["status"], "fail")
        checks = {check["id"]: check for check in project["checks"]}
        self.assertIn("lock.drift", checks)
        self.assertIn("manifest_sha256 changed", checks["lock.drift"]["detail"])
        self.assertEqual(report["totals"]["built"], 0)

        code, output = run_cli(["batch", "build", "--dir", str(self.root)])
        self.assertEqual(code, 0, output)

    def test_locked_without_lock_file_fails(self) -> None:
        code, output = run_cli(["batch", "build", "--dir", str(self.root), "--locked", "--json"])
        self.assertEqual(code, 2, output)
        checks = {check["id"]: check for check in json.loads(output)["projects"][0]["checks"]}
        self.assertIn("lock.drift", checks)
        self.assertIn("lock file missing", checks["lock.drift"]["detail"])

    def test_bad_project_isolation(self) -> None:
        (self.root / "broken.yaml").write_text("game: [unclosed\n", encoding="utf-8")
        code, output = run_cli(["batch", "build", "--dir", str(self.root), "--json"])
        self.assertEqual(code, 2, output)
        report = json.loads(output)
        self.assertEqual(report["totals"]["total"], 2)
        self.assertEqual(report["totals"]["ok"], 1)
        self.assertEqual(report["totals"]["fail"], 1)
        self.assertTrue((self.root / "out" / "demo.bin").is_file())

    def test_report_matches_schema(self) -> None:
        run_cli(["batch", "build", "--dir", str(self.root)])
        report = json.loads((self.root / ".galnx" / "latest.json").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "schemas" / "batch-report.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(report), key=lambda error: list(error.path))
        self.assertEqual(errors, [], [error.message for error in errors])

    def test_batch_run_unchanged(self) -> None:
        code, output = run_cli(["batch", "run", "--dir", str(self.root), "--json"])
        self.assertEqual(code, 0, output)
        report = json.loads(output)
        self.assertEqual([stage["name"] for stage in report["projects"][0]["stages"]], ["manifest", "preflight", "engines"])
        self.assertNotIn("cache_hits", report["totals"])

    def test_batch_build_rejects_missing_directory(self) -> None:
        code, output = run_cli(["batch", "build", "--dir", str(self.root / "missing")])
        self.assertEqual(code, 2)
        self.assertIn("FAIL", output)

    def test_build_run_single_manifest(self) -> None:
        manifest = self.root / "demo.yaml"
        code, output = run_cli(["build", "run", "--manifest", str(manifest), "--json"])
        self.assertEqual(code, 0, output)
        report = json.loads(output)
        self.assertEqual(report["totals"]["total"], 1)
        self.assertEqual(report["projects"][0]["path"], "demo.yaml")
        self.assertTrue((self.root / ".galnx" / "latest.json").is_file())
        self.assertTrue((self.root / "out" / "demo.bin").is_file())


if __name__ == "__main__":
    unittest.main()
