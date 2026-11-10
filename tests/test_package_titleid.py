"""Unit tests for galnx.package.titleid (M3-c, read-only model)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.package import titleid as T  # noqa: E402

BASE = "0100A1B2C3D4E000"
GALNX_ID = "010047414C4E0000"


class ParseTests(unittest.TestCase):
    def test_parse_accepts_strings_and_ints(self):
        self.assertEqual(T.parse_title_id(BASE), 0x0100A1B2C3D4E000)
        self.assertEqual(T.parse_title_id("0x0100a1b2c3d4e000"), 0x0100A1B2C3D4E000)
        self.assertEqual(T.parse_title_id(0x0100A1B2C3D4E000), 0x0100A1B2C3D4E000)

    def test_parse_rejects_bad_formats(self):
        for value in ("", "zz", "0100A1B2C3D4E00", "0x01ffffffffffffffff", 1 << 64, -1):
            with self.subTest(value=value):
                with self.assertRaises(T.TitleIdError):
                    T.parse_title_id(value)

    def test_format_uses_upper_hex(self):
        self.assertEqual(T.format_title_id(0x0100A1B2C3D4E000), BASE)
        self.assertEqual(T.format_title_id("0x0100a1b2c3d4e000"), BASE)


class ClassifyTests(unittest.TestCase):
    def test_kinds(self):
        cases = {
            BASE: "base",
            "0100A1B2C3D4E800": "patch",
            "0100A1B2C3D4F001": "dlc",
            "0100000000000000": "system",
            "0100A1B2C3D4E001": "invalid",
            "8000000000000000": "invalid",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(T.classify(value).value, expected)

    def test_base_alignment(self):
        for value in ("0100A1B2C3D4C000", "0100A1B2C3D4E000", "0100A1B2C3D40000"):
            with self.subTest(value=value):
                self.assertEqual(T.classify(value).value, "base")

    def test_patch_and_dlc_helpers(self):
        self.assertEqual(T.format_title_id(T.patch_id_of(BASE)), "0100A1B2C3D4E800")
        self.assertEqual(T.format_title_id(T.dlc_base_of(BASE)), "0100A1B2C3D4F000")
        self.assertEqual(T.format_title_id(T.dlc_id_of(BASE, 0)), "0100A1B2C3D4F000")
        self.assertEqual(T.format_title_id(T.dlc_id_of(BASE, 0xFFF)), "0100A1B2C3D4FFFF")
        with self.assertRaises(T.TitleIdError):
            T.dlc_id_of(BASE, 0x1000)
        self.assertEqual(T.base_of("0100A1B2C3D4E800"), 0x0100A1B2C3D4E000)
        self.assertIsNone(T.base_of("0100A1B2C3D4E001"))


class RangeTests(unittest.TestCase):
    def test_valid_range(self):
        self.assertTrue(T.in_valid_range("0100000000000000"))
        self.assertTrue(T.in_valid_range("01FFFFFFFFFFFFFF"))
        self.assertFalse(T.in_valid_range("0000000000000000"))
        self.assertFalse(T.in_valid_range("0200000000000000"))

    def test_system_reserved(self):
        expected = {
            "0100000000000000": "system modules",
            "0100000000000800": "system data",
            "0100000000001000": "system applets",
            "0100000000001FFF": "system applets",
            "0100000000002000": "development",
        }
        for value, needle in expected.items():
            with self.subTest(value=value):
                label = T.is_system_reserved(value)
                self.assertIsNotNone(label)
                self.assertIn(needle, label)
        self.assertIsNone(T.is_system_reserved("0100000000003000"))
        self.assertIsNone(T.is_system_reserved("0100A1B2C3D4E000"))


class ValidateBaseTests(unittest.TestCase):
    @staticmethod
    def codes(title_id):
        return [(issue.severity, issue.code) for issue in T.validate_base(title_id)]

    def test_valid_base_in_galnx_block_has_no_issues(self):
        self.assertEqual(self.codes(GALNX_ID), [])

    def test_valid_base_outside_block_warns(self):
        self.assertEqual(self.codes(BASE), [("warning", "outside_allocation_block")])

    def test_invalid_format(self):
        self.assertEqual(self.codes("xyz")[0], ("error", "invalid_format"))

    def test_system_reserved_is_error(self):
        codes = self.codes("0100000000000000")
        self.assertIn(("error", "system_reserved"), codes)

    def test_patch_and_dlc_are_not_bases(self):
        for value in ("0100A1B2C3D4E800", "0100A1B2C3D4F000"):
            with self.subTest(value=value):
                codes = self.codes(value)
                self.assertIn(("error", "not_base"), codes)

    def test_unaligned_is_error(self):
        codes = self.codes("0100A1B2C3D4E001")
        self.assertIn(("error", "not_aligned"), codes)

    def test_out_of_range_is_error(self):
        codes = self.codes("0x0200000000000000")
        self.assertTrue(any(severity == "error" for severity, _ in codes))


class ConflictTests(unittest.TestCase):
    @staticmethod
    def codes(new, existing=()):
        return [(issue.severity, issue.code) for issue in T.check_conflicts(new, existing)]

    def test_duplicate_base(self):
        codes = self.codes(BASE, [BASE])
        self.assertIn(("error", "duplicate"), codes)

    def test_new_base_vs_existing_patch(self):
        codes = self.codes(BASE, ["0100A1B2C3D4E800"])
        self.assertIn(("error", "duplicate"), codes)

    def test_new_base_vs_existing_dlc(self):
        codes = self.codes(BASE, ["0100A1B2C3D4F005"])
        self.assertIn(("error", "duplicate"), codes)

    def test_unrelated_id_has_no_errors(self):
        codes = self.codes("010047414C4E2000", [GALNX_ID])
        self.assertFalse(any(severity == "error" for severity, _ in codes))

    def test_invalid_new_id_reports_error(self):
        codes = self.codes("0100A1B2C3D4F001", [BASE])
        self.assertTrue(any(severity == "error" for severity, _ in codes))

    def test_warnings_and_errors_helpers(self):
        issues = T.check_conflicts(BASE, [BASE])
        self.assertEqual(len(T.errors_of(issues)), 1)
        self.assertEqual(len(T.warnings_of(issues)), 1)
        payload = T.conflicts_to_dict(issues)
        self.assertTrue(all("severity" in item and "code" in item for item in payload))


class AllocateTests(unittest.TestCase):
    def test_allocate_from_galnx_block(self):
        ids = [T.format_title_id(value) for value in T.allocate(count=3)]
        self.assertEqual(ids, ["010047414C4E0000", "010047414C4E2000", "010047414C4E4000"])

    def test_allocate_skips_used_ids(self):
        ids = [T.format_title_id(value) for value in T.allocate([GALNX_ID], count=2)]
        self.assertEqual(ids, ["010047414C4E2000", "010047414C4E4000"])

    def test_allocate_rejects_zero_count(self):
        with self.assertRaises(T.TitleIdError):
            T.allocate(count=0)

    def test_allocated_ids_validate_cleanly(self):
        allocated = T.allocate(count=2)
        for value in allocated:
            with self.subTest(value=value):
                self.assertEqual(T.validate_base(value), [])


if __name__ == "__main__":
    unittest.main()
