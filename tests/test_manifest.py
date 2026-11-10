"""Tests for manifest loading/validation against schemas/game-manifest.schema.json."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import manifest  # noqa: E402

EXAMPLE = ROOT / "examples" / "manifest.krkr.yaml"


class ManifestSchemaTests(unittest.TestCase):
    def setUp(self):
        self.data = manifest.load_manifest(EXAMPLE)

    def test_schema_is_valid_draft_2020_12(self):
        manifest.build_validator()  # raises if the schema itself is broken

    def test_example_manifest_is_valid(self):
        self.assertEqual(manifest.validate(self.data), [])

    def test_missing_required_section(self):
        data = copy.deepcopy(self.data)
        data.pop("switch")
        errors = manifest.validate(data)
        self.assertTrue(any("switch" in err for err in errors), errors)

    def test_bad_title_id(self):
        data = copy.deepcopy(self.data)
        data["switch"]["title_id"] = "0100"
        errors = manifest.validate(data)
        self.assertTrue(any("title_id" in err for err in errors), errors)

    def test_title_id_must_start_with_01(self):
        data = copy.deepcopy(self.data)
        data["switch"]["title_id"] = "0200A1B2C3D4E000"
        errors = manifest.validate(data)
        self.assertTrue(any("title_id" in err for err in errors), errors)

    def test_unknown_adapter(self):
        data = copy.deepcopy(self.data)
        data["engine"]["adapter"] = "unity"
        errors = manifest.validate(data)
        self.assertTrue(any("adapter" in err for err in errors), errors)

    def test_bad_game_id(self):
        data = copy.deepcopy(self.data)
        data["game"]["id"] = "Bad Id!"
        errors = manifest.validate(data)
        self.assertTrue(any("game/id" in err for err in errors), errors)

    def test_unknown_top_level_key(self):
        data = copy.deepcopy(self.data)
        data["surprise"] = True
        self.assertTrue(manifest.validate(data))


if __name__ == "__main__":
    unittest.main()
