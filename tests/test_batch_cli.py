"""Tests for the 'galnx batch' CLI subcommands."""
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

AUDIT_SCHEMA = ROOT / "schemas" / "batch-report.schema.json"


def run_cli(argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = cli.main(argv)
    return code, buffer.getvalue()


def write_manifest(root: Path, slug: str, title_id: str = "010047410000A001", adapter: str = "krkrsdl2") -> Path:
    source = root / "games" / slug
    source.mkdir(parents=True, exist_ok=True)
    (source / "data.xp3").write_text("placeholder\n", encoding="utf-8")
    ignored = adapter  # adapter is exercised indirectly; keep manifest valid for krkrsdl2
    data = {
        "schema_version": 1,
        "game": {"id": slug, "title": "Test " + slug, "source_dir": str(source)},
        "engine": {
            "adapter": "krkrsdl2",
            "adapter_version": "krkrsdl2@124bdf84 (2026-10-01)",
            "profile": "default",
            "entry": "data.xp3",
        },
        "switch": {"title_id": title_id, "target": "nro", "display_mode": "handheld"},
        "build": {"output_dir": str(root / "out" / slug), "keys_env": "GALNX_PROD_KEYS"},
    }
    path = root / (slug + ".yaml")
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def write_broken(root: Path) -> Path:
    source = root / "games" / "broken"
    source.mkdir(parents=True, exist_ok=True)
    path = root / "broken.yaml"
    path.write_text("schema_version: 1\nswitch:\n  title_id: NOPE\n", encoding="utf-8")
    return path


class BatchCliTests(unittest.TestCase):
    def test_run_json_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "demo-a")
            code, out = run_cli(["batch", "run", "--dir", str(root), "--json"])
            self.assertEqual(code, 0)
            report = json.loads(out)
            # krkrsdl2 is research-level (emulator-verified only), so the project
            # status is warn: exit code stays 0 because there is no failure.
            self.assertEqual(report["totals"]["ok"], 0)
            self.assertEqual(report["totals"]["warn"], 1)
            self.assertTrue((root / ".galnx" / "latest.json").is_file())

    def test_run_failing_project_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "demo-a")
            write_broken(root)
            code, out = run_cli(["batch", "run", "--dir", str(root), "--json"])
            self.assertEqual(code, 2)
            report = json.loads(out)
            self.assertEqual(report["totals"]["fail"], 1)
            self.assertEqual(report["totals"]["ok"], 0)
            self.assertEqual(report["totals"]["warn"], 1)

    def test_run_human_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "demo-a")
            code, out = run_cli(["batch", "run", "--dir", str(root)])
            self.assertEqual(code, 0)
            self.assertIn("demo-a.yaml", out)
            self.assertIn("report", out.lower())

    def test_run_explicit_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "demo-a")
            write_manifest(root, "demo-b", title_id="010047410000A002")
            code, out = run_cli(
                ["batch", "run", "--dir", str(root), "--manifest", "demo-a.yaml", "--json"]
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["totals"]["total"], 1)

    def test_run_missing_directory_returns_2(self) -> None:
        code, out = run_cli(["batch", "run", "--dir", str(Path(tempfile.gettempdir()) / "galnx-no-such-dir")])
        self.assertEqual(code, 2)
        self.assertIn("FAIL", out)

    def test_diff_fixed_returns_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "demo-a")
            broken = write_broken(root)
            code, _ = run_cli(["batch", "run", "--dir", str(root)])
            self.assertEqual(code, 2)
            first = max(
                (root / ".galnx").glob("batch-report-*.json"), key=lambda p: p.stat().st_mtime_ns
            )
            write_manifest(root, "broken", title_id="010047410000A009")
            code, _ = run_cli(["batch", "run", "--dir", str(root)])
            self.assertEqual(code, 0)
            second = max(
                (root / ".galnx").glob("batch-report-*.json"), key=lambda p: p.stat().st_mtime_ns
            )
            code, out = run_cli(["batch", "diff", str(first), str(second), "--json"])
            self.assertEqual(code, 0)
            diff = json.loads(out)
            self.assertEqual(diff["counts"]["fixed"], 1)

    def test_clean_requires_yes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(root, "demo-a")
            run_cli(["batch", "run", "--dir", str(root)])
            report_dir = root / ".galnx"
            self.assertTrue(report_dir.is_dir())
            code, out = run_cli(["batch", "clean", "--dir", str(root)])
            self.assertEqual(code, 2)
            self.assertIn("--yes", out)
            self.assertTrue(report_dir.is_dir())
            code, out = run_cli(["batch", "clean", "--dir", str(root), "--yes"])
            self.assertEqual(code, 0)
            self.assertFalse(report_dir.exists())

    def test_help_exits_zero(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.main(["batch", "--help"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
