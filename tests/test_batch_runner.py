"""Tests for the batch runner (galnx.batch.runner)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import batch  # noqa: E402


def write_yaml(path: Path, data) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def make_source(directory: Path, entry: str = "data.xp3") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / entry).write_text("placeholder\n", encoding="utf-8")
    return directory


def manifest(root: Path, slug: str, title_id: str = "010047410000A001", **overrides) -> dict:
    source = make_source(root / "games" / slug)
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
        "build": {
            "output_dir": str(root / "out" / slug),
            "clean_workspace_before_build": True,
            "reproducible": True,
            "keys_env": "GALNX_PROD_KEYS",
        },
    }
    for key, value in overrides.items():
        data[key] = value
    return data


class BatchRunnerTests(unittest.TestCase):
    def test_healthy_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml(root / "project.yaml", manifest(root, "demo-a"))
            report = batch.run_batch(root)
            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["root"], root.resolve().as_posix())
            totals = report["totals"]
            self.assertEqual(totals["total"], 1)
            self.assertEqual(totals["ok"], 1)
            self.assertEqual(totals["fail"], 0)
            project = report["projects"][0]
            self.assertEqual(project["status"], "ok")
            self.assertEqual([s["name"] for s in project["stages"]], ["manifest", "preflight", "engines"])
            for stage in project["stages"]:
                self.assertEqual(stage["status"], "ok")
            check_ids = {c["id"] for c in project["checks"]}
            self.assertIn("engine.plan", check_ids)
            self.assertIn("engine.artifact", check_ids)
            self.assertIn("manifest.parse", check_ids)
            self.assertEqual(project["errors"], [])

    def test_bad_yaml_does_not_stop_others(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml(root / "a.yaml", manifest(root, "demo-a"))
            (root / "b-broken.yaml").write_text("schema_version: 1\ngame: [unclosed\n", encoding="utf-8")
            write_yaml(root / "c.yaml", manifest(root, "demo-c", title_id="010047410000A003"))
            report = batch.run_batch(root)
            totals = report["totals"]
            self.assertEqual(totals["total"], 3)
            self.assertEqual(totals["ok"], 2)
            self.assertEqual(totals["fail"], 1)
            by_path = {p["path"]: p for p in report["projects"]}
            broken = by_path["b-broken.yaml"]
            self.assertEqual(broken["status"], "fail")
            self.assertEqual([s["name"] for s in broken["stages"]], ["manifest", "preflight", "engines"])
            self.assertEqual(broken["stages"][0]["status"], "fail")
            self.assertTrue(all(c["id"] != "manifest.parse" or c["status"] == "fail" for c in broken["checks"]))
            self.assertEqual(broken["stages"][1]["status"], "skip")
            self.assertEqual(broken["stages"][2]["status"], "skip")
            self.assertTrue(broken["errors"])

    def test_unknown_adapter_fails_engines_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = manifest(root, "demo-a")
            data["engine"] = {"adapter": "custom"}
            write_yaml(root / "custom.yaml", data)
            report = batch.run_batch(root)
            project = report["projects"][0]
            self.assertEqual(project["status"], "fail")
            engines = project["stages"][2]
            self.assertEqual(engines["status"], "fail")
            failing = [c for c in engines["checks"] if c["status"] == "fail"]
            self.assertTrue(failing)
            self.assertTrue(any(c["id"].startswith("engine.") for c in failing))

    def test_skip_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml(root / "project.yaml", manifest(root, "demo-a"))
            report = batch.run_batch(root, skip_preflight=True)
            project = report["projects"][0]
            self.assertEqual(project["stages"][1]["status"], "skip")
            self.assertIn("preflight.skipped", {c["id"] for c in project["checks"]})

    def test_skip_output_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml(root / "project.yaml", manifest(root, "demo-a"))
            report = batch.run_batch(root, skip_output_checks=True)
            ids = {c["id"] for c in report["projects"][0]["checks"]}
            self.assertIn("build.output_dir.skipped", ids)
            self.assertNotIn("build.output_dir", ids)

    def test_no_manifests_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(batch.BatchError):
                batch.run_batch(Path(tmp))

    def test_explicit_manifest_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml(root / "a.yaml", manifest(root, "demo-a"))
            write_yaml(root / "b.yaml", manifest(root, "demo-b", title_id="010047410000A002"))
            report = batch.run_batch(root, manifests=["a.yaml"])
            self.assertEqual(report["totals"]["total"], 1)
            self.assertEqual(report["projects"][0]["path"], "a.yaml")

    def test_recursive_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "nested"
            nested.mkdir()
            write_yaml(root / "top.yaml", manifest(root, "demo-a"))
            write_yaml(nested / "deep.yaml", manifest(root, "demo-b", title_id="010047410000A002"))
            self.assertEqual(batch.run_batch(root)["totals"]["total"], 1)
            self.assertEqual(batch.run_batch(root, recursive=True)["totals"]["total"], 2)


if __name__ == "__main__":
    unittest.main()
