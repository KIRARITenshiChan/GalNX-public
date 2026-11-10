"""Tests for the payload CLI handlers (galnx.payload.cli).

The payload command tree is registered by src/galnx/cli.py; these tests build a
standalone argparse parser so they do not depend on that wiring.
"""

import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from galnx.payload import cli as payload_cli  # noqa: E402

EXAMPLE_MANIFEST = ROOT / "examples/payload/manifest.pilot01.yaml"
PILOT_GAME = Path("E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气")
PILOT_UI = Path("E:/galnx-build/pilot-01/k2nx-ws/build/romfs")


def make_parser():
    parser = argparse.ArgumentParser(prog="galnx-test")
    sub = parser.add_subparsers(dest="command", required=True)
    payload_cli.register(sub)
    return parser


def run_cli(*argv):
    parser = make_parser()
    args = parser.parse_args(list(argv))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = int(args.func(args))
    return code, out.getvalue()


def write_tree(root, files):
    for rel, data in files.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="galnx-payload-cli-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.source = self.tmp / "game"
        self.ui = self.tmp / "ui"
        write_tree(
            self.source,
            {
                "data.xp3": b"XP3!",
                "data_chs.xp3": b"CHS",
                "haruno.cf": b"CF",
                "plugin/a.tpm": b"TPM",
                "plugin/a.tpm.sig": b"SIG",
            },
        )
        write_tree(self.ui, {"img/a.png": b"PNG!!", "ui/b.png": b"UI"})
        self.manifest = self.write_manifest()

    def write_manifest(self, payload_overrides=None, drop_payload=False):
        if EXAMPLE_MANIFEST.is_file():
            data = yaml.safe_load(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
        else:  # pragma: no cover - examples ship with the repo
            self.skipTest("examples/payload/manifest.pilot01.yaml is missing")
        data["game"]["source_dir"] = str(self.source)
        data["game"]["id"] = "cli-test-game"
        payload = data["payload"]
        payload["source_dir"] = str(self.source)
        payload["ui_dir"] = str(self.ui)
        payload["keymap"] = {"profile": "generic-vn"}
        payload.pop("notes", None)
        if payload_overrides:
            payload.update(payload_overrides)
        if drop_payload:
            data.pop("payload")
        path = self.tmp / "manifest.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return path

    def json_document(self, stdout):
        return json.loads(stdout)


class PlanCliTests(CliTestCase):
    def test_json_plan(self):
        code, out = run_cli("payload", "plan", "--manifest", str(self.manifest), "--json")
        self.assertEqual(code, 0, out)
        doc = self.json_document(out)
        self.assertEqual(doc["version"], "0.1.0")
        self.assertEqual(doc["manifest_path"], str(self.manifest))
        self.assertEqual(doc["manifest"]["name"], "game_files.txt")
        self.assertEqual(doc["config"]["target"], "/kirikiri/haruno")
        self.assertEqual(doc["file_count"], 3)  # data.xp3, haruno.cf, plugin/a.tpm
        self.assertEqual(doc["total_file_count"], 4)  # + generated keymap
        self.assertEqual(doc["generated"][0]["path"], "Kirikiroid2Preference.xml")
        self.assertEqual(doc["generated"][0]["bytes"], 1293)
        self.assertEqual([item["path"] for item in doc["files"]],
                         ["data.xp3", "haruno.cf", "plugin/a.tpm"])
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["errors"], [])
        self.assertEqual([check["id"] for check in doc["checks"]][:3],
                         ["payload-link-mode", "payload-source", "payload-files"])

    def test_no_files_flag_omits_per_file_list(self):
        code, out = run_cli(
            "payload", "plan", "--manifest", str(self.manifest), "--json", "--no-files"
        )
        self.assertEqual(code, 0)
        doc = self.json_document(out)
        self.assertIsNone(doc["files"])
        self.assertEqual(doc["file_count"], 3)

    def test_human_plan_output(self):
        code, out = run_cli("payload", "plan", "--manifest", str(self.manifest))
        self.assertEqual(code, 0)
        self.assertIn("Payload plan: /kirikiri/haruno -> romfs:/game", out)
        self.assertIn("payload files:   3 selected + 1 generated", out)
        self.assertIn("1 warn", out)  # generic-vn leaves three actions unbound
        self.assertIn("[OK  ] payload source directory", out)

    def test_override_source_dir(self):
        other = self.tmp / "other"
        write_tree(other, {"data.xp3": b"X"})
        code, out = run_cli(
            "payload", "plan", "--manifest", str(self.manifest),
            "--source-dir", str(other), "--json",
        )
        self.assertEqual(code, 0)
        doc = self.json_document(out)
        self.assertEqual(doc["file_count"], 1)

    def test_bad_source_dir_fails(self):
        code, out = run_cli(
            "payload", "plan", "--manifest", str(self.manifest),
            "--source-dir", str(self.tmp / "nope"), "--json",
        )
        self.assertEqual(code, 2)
        doc = self.json_document(out)
        self.assertFalse(doc["ok"])
        # the JSON plan document carries check dicts, not plain strings
        self.assertTrue(
            any("not a directory" in check["detail"] for check in doc["errors"])
        )

    def test_missing_manifest_file(self):
        code, out = run_cli(
            "payload", "plan", "--manifest", str(self.tmp / "nope.yaml"), "--json"
        )
        self.assertEqual(code, 2)
        doc = self.json_document(out)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["config"], None)

    def test_manifest_without_payload_section(self):
        manifest = self.write_manifest(drop_payload=True)
        code, out = run_cli("payload", "plan", "--manifest", str(manifest), "--json")
        self.assertEqual(code, 2)
        doc = self.json_document(out)
        self.assertIn("no payload section", doc["errors"][0])

    def test_manifest_with_invalid_payload(self):
        manifest = self.write_manifest(payload_overrides={"target": "relative"})
        code, out = run_cli("payload", "plan", "--manifest", str(manifest), "--json")
        self.assertEqual(code, 2)
        doc = self.json_document(out)
        self.assertTrue(doc["errors"])

    def test_invalid_link_mode_is_rejected_by_argparse(self):
        with self.assertRaises(SystemExit) as ctx:
            make_parser().parse_args(
                ["payload", "plan", "--manifest", str(self.manifest), "--link-mode", "teleport"]
            )
        self.assertEqual(ctx.exception.code, 2)


class MaterializeCliTests(CliTestCase):
    def test_materialize_json_and_overwrite_guard(self):
        out_dir = self.tmp / "romfs"
        code, out = run_cli(
            "payload", "materialize", "--manifest", str(self.manifest),
            "--out", str(out_dir), "--json",
        )
        self.assertEqual(code, 0, out)
        doc = self.json_document(out)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["result"]["payload_files"], 3)
        self.assertEqual(doc["result"]["generated_files"], 1)
        self.assertEqual(doc["result"]["ui_files"], 2)
        self.assertTrue((out_dir / "game/data.xp3").is_file())
        self.assertTrue((out_dir / "game_files.txt").is_file())

        code, out = run_cli(
            "payload", "materialize", "--manifest", str(self.manifest),
            "--out", str(out_dir), "--json",
        )
        self.assertEqual(code, 2)
        doc = self.json_document(out)
        self.assertTrue(any("refusing to overwrite" in error for error in doc["errors"]))

        code, out = run_cli(
            "payload", "materialize", "--manifest", str(self.manifest),
            "--out", str(out_dir), "--force", "--json",
        )
        self.assertEqual(code, 0)
        self.assertTrue(self.json_document(out)["ok"])

    def test_materialize_failed_plan_refuses_without_force(self):
        other = self.tmp / "other"
        write_tree(other, {"other.xp3": b"O"})
        code, out = run_cli(
            "payload", "materialize", "--manifest", str(self.manifest),
            "--source-dir", str(other), "--out", str(self.tmp / "romfs"), "--json",
        )
        self.assertEqual(code, 2)
        doc = self.json_document(out)
        self.assertTrue(any("failed checks" in error for error in doc["errors"]))

    def test_materialize_human_output(self):
        out_dir = self.tmp / "romfs"
        code, out = run_cli(
            "payload", "materialize", "--manifest", str(self.manifest),
            "--out", str(out_dir),
        )
        self.assertEqual(code, 0)
        self.assertIn("Materialized romfs in", out)
        self.assertIn("[OK  ] payload-materialize", out)

    def test_materialize_missing_out_argument(self):
        with self.assertRaises(SystemExit) as ctx:
            make_parser().parse_args(
                ["payload", "materialize", "--manifest", str(self.manifest)]
            )
        self.assertEqual(ctx.exception.code, 2)


class VerifyCliTests(CliTestCase):
    def test_verify_without_manifest(self):
        code, out = run_cli("payload", "verify", "--json")
        self.assertEqual(code, 0, out)
        doc = self.json_document(out)
        self.assertTrue(doc["ok"])
        self.assertEqual(
            [check["id"] for check in doc["checks"]],
            ["keymap-template-size", "keymap-template-sha256", "keymap-default-render"],
        )

    def test_verify_with_valid_manifest(self):
        code, out = run_cli(
            "payload", "verify", "--manifest", str(self.manifest), "--json"
        )
        self.assertEqual(code, 0, out)
        doc = self.json_document(out)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["checks"][-1]["id"], "payload")
        self.assertEqual(doc["checks"][-1]["status"], "ok")

    def test_verify_with_invalid_payload(self):
        manifest = self.write_manifest(payload_overrides={"startup": "/elsewhere/data.xp3"})
        code, out = run_cli("payload", "verify", "--manifest", str(manifest), "--json")
        self.assertEqual(code, 2)
        doc = self.json_document(out)
        self.assertFalse(doc["ok"])
        self.assertTrue(any("startup" in error for error in doc["errors"]))

    def test_verify_human_output(self):
        code, out = run_cli("payload", "verify")
        self.assertEqual(code, 0)
        self.assertIn("[OK  ] keymap-template-size", out)
        self.assertIn("0 fail", out)


class RegisterTests(unittest.TestCase):
    def test_register_creates_payload_subcommands(self):
        parser = make_parser()
        args = parser.parse_args(["payload", "verify"])
        self.assertEqual(args.command, "payload")
        self.assertEqual(args.payload_command, "verify")
        args = parser.parse_args(["payload", "plan", "--manifest", "m.yaml"])
        self.assertEqual(args.payload_command, "plan")
        self.assertFalse(args.json)
        self.assertFalse(args.no_files)
        self.assertEqual(args.link_mode, "copy")


class PilotCliIntegrationTests(CliTestCase):
    """End-to-end CLI run against the read-only pilot-01 dataset."""

    @classmethod
    def setUpClass(cls):
        if not (PILOT_GAME.is_dir() and PILOT_UI.is_dir() and EXAMPLE_MANIFEST.is_file()):
            raise unittest.SkipTest("pilot-01 dataset not available")

    def test_plan_reports_golden_numbers(self):
        manifest = self.tmp / "pilot.yaml"
        data = yaml.safe_load(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
        data["payload"]["source_dir"] = str(PILOT_GAME)
        data["payload"]["ui_dir"] = str(PILOT_UI)
        manifest.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        code, out = run_cli("payload", "plan", "--manifest", str(manifest), "--json")
        self.assertEqual(code, 0, out)
        doc = json.loads(out)
        self.assertEqual(doc["file_count"], 22)
        self.assertEqual(doc["total_file_count"], 23)
        self.assertEqual(doc["total_bytes"], 2870635309)
        self.assertEqual(doc["ui_file_count"], 85)
        self.assertEqual(doc["romfs_total_bytes"], 2878186922)
        self.assertEqual(
            doc["manifest"]["sha256"],
            "0e6757d9901d4a4abb95a220f9d8e1714b0b858c421ec328e6802a10d4e3fd61",
        )
        self.assertEqual(doc["manifest"]["bytes"], 600)
        self.assertEqual(doc["manifest"]["lines"], 28)
        self.assertEqual(
            doc["keymap"]["sha256"],
            "aa4fa8aab256f73c6d73111a62305f7078bd9c1eca3cd9d9128d0a51abef9543",
        )
        self.assertTrue(doc["ok"])

    def test_verify_accepts_the_pilot_manifest(self):
        code, out = run_cli(
            "payload", "verify", "--manifest", str(EXAMPLE_MANIFEST), "--json"
        )
        self.assertEqual(code, 0, out)
        self.assertTrue(json.loads(out)["ok"])


if __name__ == "__main__":
    unittest.main()
