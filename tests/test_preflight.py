"""Tests for `galnx preflight` static checks."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.doctor import check_build_root, check_keys  # noqa: E402
from galnx.preflight import run_preflight  # noqa: E402

EXAMPLE = ROOT / "examples" / "manifest.krkr.yaml"


class PreflightTests(unittest.TestCase):
    def test_missing_source_dir_is_reported(self):
        checks = run_preflight(EXAMPLE)
        names = {c.name for c in checks if c.status == "fail"}
        self.assertIn("game.source_dir", names)
        self.assertEqual(checks[0].status, "ok")  # manifest parsed

    def test_valid_manifest_with_existing_source_dir_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data.xp3").write_bytes(b"")
            text = EXAMPLE.read_text(encoding="utf-8")
            text = text.replace('source_dir: "E:/Othergames/Galgame/SampleGame"',
                                'source_dir: "%s"' % str(Path(tmp)).replace(chr(92), "/"))
            manifest_path = Path(tmp) / "manifest.yaml"
            manifest_path.write_text(text, encoding="utf-8")
            checks = run_preflight(manifest_path)
            fails = [c.to_json() for c in checks if c.status == "fail"]
            self.assertEqual(fails, [])

    def test_missing_file(self):
        checks = run_preflight(Path("E:/does-not-exist/manifest.yaml"))
        self.assertEqual(checks[0].status, "fail")


class DoctorChecksTests(unittest.TestCase):
    def test_build_root_with_space_fails(self):
        check = check_build_root(Path("E:/space dir/build"))
        self.assertEqual(check.status, "fail")

    def test_missing_keys_fails(self):
        check = check_keys(Path("E:/does-not-exist/prod.keys"))
        self.assertEqual(check.status, "fail")


if __name__ == "__main__":
    unittest.main()
