"""Unit tests for the galnx package CLI (plan/check)."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import cli  # noqa: E402

BASE = "0100A1B2C3D4E000"

MANIFEST = chr(10).join([
    "schema_version: 1",
    "",
    "game:",
    "  id: cli-test-game",
    "  title: CLI test game",
    "  version: 1.0.0",
    "  source_dir: E:/galnx-build/none",
    "",
    "engine:",
    "  adapter: krkrsdl2",
    "  entry: data.xp3",
    "",
    "switch:",
    "  title_id: " + BASE,
    "  title: CLITest",
    "  author: GalNX",
    "  icon: icon.jpg",
    "  target: nsp",
    "",
    "build:",
    "  output_dir: E:/galnx-build/cli-test",
    "",
    "package:",
    "  type: self_contained_nsp",
    "  startup_user_account: 1",
    "  romfs_dir: romfs",
]) + chr(10)

NSTOOL = chr(10).join([
    "[PartitionFs]",
    "  Type:        PFS0",
    "  FileNum:     3",
    "[NCA Header]",
    "  Content Type:    Program",
    "  ProgID:          0x0100000000001000",
    "  Size:            0x2dc00",
    "[NCA Header]",
    "  Content Type:    Control",
    "  ProgID:          0x0100000000001000",
    "  Size:            0x1cc00",
    "[NCA Header]",
    "  Content Type:    Meta",
    "  ProgID:          0x0100000000001000",
    "  Size:            0x1000",
]) + chr(10)


def make_jpeg(width=256, height=256):
    app0 = bytes([0xFF, 0xE0, 0x00, 0x10]) + b"JFIF" + bytes([0]) + bytes([1, 1, 0, 0, 1, 0, 1, 0, 0])
    sof = bytes([0xFF, 0xC0, 0x00, 0x11, 0x08,
                 (height >> 8) & 0xFF, height & 0xFF,
                 (width >> 8) & 0xFF, width & 0xFF, 0x03])
    sof += bytes([1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    return bytes([0xFF, 0xD8]) + app0 + sof + bytes([0xFF, 0xD9])


def run_cli(*argv):
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue()


class PackagePlanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        (self.dir / "icon.jpg").write_bytes(make_jpeg(256, 256))
        romfs = self.dir / "romfs"
        romfs.mkdir()
        (romfs / "hello.txt").write_text("hello", encoding="utf-8")
        self.manifest = self.dir / "game.yaml"
        self.manifest.write_text(MANIFEST, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_plan_text_ok(self):
        code, out = run_cli("package", "plan", "--manifest", str(self.manifest))
        self.assertEqual(code, 0)
        self.assertIn("Packing plan (self-contained NSP):", out)
        self.assertIn("title_id: " + BASE, out)
        self.assertIn("0 fail", out)
        self.assertIn("package.result", out)

    def test_plan_json_ok(self):
        code, out = run_cli("package", "plan", "--manifest", str(self.manifest), "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(set(payload), {"version", "manifest", "package", "checks", "ok", "errors"})
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["package"]["type"], "self_contained_nsp")
        self.assertEqual(payload["package"]["title_id"], BASE)
        statuses = {check["id"]: check["status"] for check in payload["checks"]}
        self.assertEqual(statuses["package.result"], "ok")
        self.assertEqual(statuses["package.icon"], "ok")
        self.assertEqual(statuses["package.romfs"], "ok")

    def test_plan_registry_entry_present(self):
        registry = self.dir / "registry.json"
        registry.write_text(json.dumps({"schema_version": 1, "generated_by": "galnx", "entries": [
            {"title_id": BASE, "name": "cli-test-game"}]}), encoding="utf-8")
        code, out = run_cli("package", "plan", "--manifest", str(self.manifest),
                            "--registry", str(registry), "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        statuses = {check["id"]: check["status"] for check in payload["checks"]}
        self.assertEqual(statuses["package.registry"], "ok")
        self.assertEqual(statuses["package.registry.entry"], "ok")

    def test_plan_registry_missing_entry_is_warning(self):
        registry = self.dir / "registry.json"
        registry.write_text(json.dumps({"schema_version": 1, "generated_by": "galnx", "entries": [
            {"title_id": "010047414C4E0000", "name": "other"}]}), encoding="utf-8")
        code, out = run_cli("package", "plan", "--manifest", str(self.manifest),
                            "--registry", str(registry), "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        statuses = {check["id"]: check["status"] for check in payload["checks"]}
        self.assertEqual(statuses["package.registry.entry"], "warn")

    def test_plan_missing_manifest(self):
        code, out = run_cli("package", "plan", "--manifest", str(self.dir / "nope.yaml"))
        self.assertEqual(code, 2)
        self.assertIn("FAIL", out)

    def test_plan_invalid_manifest_json(self):
        bad = self.dir / "bad.yaml"
        bad.write_text("schema_version: 1" + chr(10) + "game: [unclosed", encoding="utf-8")
        code, out = run_cli("package", "plan", "--manifest", str(bad), "--json")
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertIsNone(payload["package"])
        self.assertTrue(payload["errors"])

    def test_plan_icon_missing_fails(self):
        (self.dir / "icon.jpg").unlink()
        code, out = run_cli("package", "plan", "--manifest", str(self.manifest))
        self.assertEqual(code, 2)
        self.assertIn("package.icon", out)


class PackageCheckDirTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "stage"
        self.root.mkdir()
        exefs = self.root / "exefs"
        exefs.mkdir()
        (exefs / "main").write_bytes(b"NSO0" + bytes(0x40))
        (exefs / "main.npdm").write_bytes(b"META" + bytes(0x100))
        control = self.root / "control"
        control.mkdir()
        nacp = bytearray(0x4000)
        nacp[:11] = b"Sample Game"
        (control / "control.nacp").write_bytes(bytes(nacp))
        (control / "icon_AmericanEnglish.dat").write_bytes(make_jpeg(256, 256))
        romfs = self.root / "romfs"
        romfs.mkdir()
        (romfs / "hello.txt").write_text("hello", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_check_dir_text_ok(self):
        code, out = run_cli("package", "check", "--dir", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("0 fail", out)
        self.assertIn("romfs", out)

    def test_check_dir_missing_exefs_main(self):
        (self.root / "exefs" / "main").unlink()
        code, out = run_cli("package", "check", "--dir", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("FAIL", out)

    def test_check_dir_json(self):
        code, out = run_cli("package", "check", "--dir", str(self.root), "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(set(payload), {"version", "kind", "target", "package_type", "checks", "ok", "errors"})
        self.assertEqual(payload["kind"], "dir")
        self.assertEqual(payload["package_type"], "self_contained_nsp")
        self.assertTrue(payload["ok"])

    def test_check_dir_forwarder_skips_romfs(self):
        import shutil
        shutil.rmtree(self.root / "romfs")
        code, out = run_cli("package", "check", "--dir", str(self.root),
                            "--type", "forwarder_nsp", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        statuses = {check["id"]: check["status"] for check in payload["checks"]}
        self.assertEqual(statuses["contract.romfs"], "skip")


class PackageCheckNstoolTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.log = self.dir / "nstool.log"
        self.log.write_text(NSTOOL, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_check_nstool_ok(self):
        code, out = run_cli("package", "check", "--nstool-json", str(self.log))
        self.assertEqual(code, 0)
        self.assertIn("PFS0 type", out)

    def test_check_nstool_expected_title_id_ok(self):
        code, out = run_cli("package", "check", "--nstool-json", str(self.log),
                            "--title-id", "0100000000001000", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["kind"], "nstool")
        statuses = {check["id"]: check["status"] for check in payload["checks"]}
        self.assertEqual(statuses["nstool.progid.expected"], "ok")

    def test_check_nstool_expected_title_id_mismatch(self):
        code, out = run_cli("package", "check", "--nstool-json", str(self.log),
                            "--title-id", BASE)
        self.assertEqual(code, 2)
        self.assertIn("expected ProgID", out)

    def test_check_nstool_missing_file(self):
        code, out = run_cli("package", "check", "--nstool-json", str(self.dir / "nope.log"))
        self.assertEqual(code, 2)
        self.assertIn("nstool.file", out)

    def test_check_requires_a_target(self):
        with self.assertRaises(SystemExit):
            run_cli("package", "check")


class ParserTests(unittest.TestCase):
    def test_package_subcommands_registered(self):
        parser = cli.build_parser()
        args = parser.parse_args(["package", "plan", "--manifest", "x.yaml"])
        self.assertEqual(args.command, "package")
        self.assertEqual(args.package_command, "plan")
        args = parser.parse_args(["package", "check", "--dir", "out"])
        self.assertEqual(args.package_command, "check")
        self.assertEqual(args.type, "self_contained_nsp")


if __name__ == "__main__":
    unittest.main()
