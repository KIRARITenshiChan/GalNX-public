"""Tests for batch report writing, diffing and cleaning (galnx.batch.report)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import batch  # noqa: E402

SCHEMA_PATH = ROOT / "schemas" / "batch-report.schema.json"


def project(path: str, status: str, name: str = "demo") -> dict:
    return {
        "path": path,
        "name": name,
        "adapter": "krkrsdl2",
        "status": status,
        "stages": [],
        "checks": [],
        "errors": [] if status != "fail" else ["boom"],
        "duration_s": 0.01,
    }


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class BatchReportTests(unittest.TestCase):
    def test_build_report_totals(self) -> None:
        projects = [project("a.yaml", "ok"), project("b.yaml", "fail"), project("c.yaml", "warn")]
        report = batch.build_report("/tmp/root", projects, 1.5, generated_at="2026-10-30T03:00:00Z")
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["generated_at"], "2026-10-30T03:00:00Z")
        totals = report["totals"]
        self.assertEqual((totals["total"], totals["ok"], totals["warn"], totals["fail"], totals["skipped"]), (3, 1, 1, 1, 0))
        self.assertEqual(totals["duration_s"], 1.5)

    def test_write_report_and_prune(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            written = []
            for index in range(3):
                report = batch.build_report(
                    root,
                    [project("a.yaml", "ok")],
                    0.1,
                    generated_at="2026-10-30T03:00:0%dZ" % index,
                )
                written.append(batch.write_report(report, keep=2))
            self.assertTrue(Path(written[-1]["path"]).is_file())
            self.assertTrue(Path(written[-1]["latest"]).is_file())
            names = sorted(p.name for p in (root / batch.REPORT_DIRNAME).glob(batch.REPORT_PREFIX + "*.json"))
            self.assertEqual(len(names), 2)
            latest = json.loads(Path(written[-1]["latest"]).read_text(encoding="utf-8"))
            self.assertEqual(latest["schema_version"], 2)
            self.assertEqual(len(latest["projects"]), 1)

    def test_load_report_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(batch.ReportError):
                batch.load_report(root / "missing.json")
            bad = root / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(batch.ReportError):
                batch.load_report(bad)
            wrong = root / "wrong.json"
            write_json(wrong, {"schema_version": 1, "projects": "nope"})
            with self.assertRaises(batch.ReportError):
                batch.load_report(wrong)

    def test_diff_reports_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = batch.build_report(
                root,
                [
                    project("a.yaml", "fail"),
                    project("b.yaml", "fail"),
                    project("c.yaml", "ok"),
                    project("e.yaml", "ok"),
                ],
                0.1,
                generated_at="2026-10-30T03:00:00Z",
            )
            after = batch.build_report(
                root,
                [
                    project("a.yaml", "ok"),
                    project("b.yaml", "fail"),
                    project("c.yaml", "fail"),
                    project("d.yaml", "ok"),
                ],
                0.1,
                generated_at="2026-10-30T03:00:01Z",
            )
            before_path = write_json(root / "before.json", before)
            after_path = write_json(root / "after.json", after)
            diff = batch.diff_reports(before_path, after_path)
            self.assertEqual([item["path"] for item in diff["added"]], ["d.yaml"])
            self.assertEqual([item["path"] for item in diff["fixed"]], ["a.yaml"])
            self.assertEqual([item["path"] for item in diff["regressed"]], ["c.yaml"])
            self.assertEqual([item["path"] for item in diff["still_failing"]], ["b.yaml"])
            self.assertEqual([item["path"] for item in diff["removed"]], ["e.yaml"])
            counts = diff["counts"]
            self.assertEqual(counts["added"], 1)
            self.assertEqual(counts["fixed"], 1)
            self.assertEqual(counts["regressed"], 1)
            self.assertEqual(counts["still_failing"], 1)
            self.assertEqual(counts["removed"], 1)

    def test_clean_reports_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = batch.build_report(root, [project("a.yaml", "ok")], 0.1)
            batch.write_report(report)
            report_dir = root / batch.REPORT_DIRNAME
            self.assertTrue(report_dir.is_dir())
            result = batch.clean_reports(root, yes=False)
            self.assertTrue(result["existed"])
            self.assertTrue(result["dry_run"])
            self.assertGreaterEqual(result["files"], 1)
            self.assertTrue(report_dir.is_dir())
            result = batch.clean_reports(root, yes=True)
            self.assertFalse(result["dry_run"])
            self.assertFalse(report_dir.exists())

    def test_clean_reports_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = batch.clean_reports(Path(tmp), yes=True)
            self.assertFalse(result["existed"])
            self.assertEqual(result["removed"], 0)

    def test_report_matches_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = batch.build_report(root, [project("a.yaml", "ok"), project("b.yaml", "fail")], 0.2)
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            errors = sorted(validator.iter_errors(report), key=lambda e: list(e.path))
            self.assertEqual(errors, [], [e.message for e in errors])


if __name__ == "__main__":
    unittest.main()
