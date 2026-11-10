"""Unit tests for galnx.package.metadata (M3-c packaging metadata model)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.package import metadata as M  # noqa: E402

BASE = "0100A1B2C3D4E000"
GALNX_ID = "010047414C4E0000"


def make_jpeg(width=256, height=256, eoi=True):
    app0 = bytes([0xFF, 0xE0, 0x00, 0x10]) + b"JFIF" + bytes([0]) + bytes([1, 1, 0, 0, 1, 0, 1, 0, 0])
    sof = bytes([0xFF, 0xC0, 0x00, 0x11, 0x08,
                 (height >> 8) & 0xFF, height & 0xFF,
                 (width >> 8) & 0xFF, width & 0xFF, 0x03])
    sof += bytes([1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    data = bytes([0xFF, 0xD8]) + app0 + sof
    if eoi:
        data += bytes([0xFF, 0xD9])
    return data


def make_bmp(width=256, height=256):
    header = b"BM" + (54).to_bytes(4, "little") + bytes(4) + (54).to_bytes(4, "little")
    header += (40).to_bytes(4, "little")
    header += width.to_bytes(4, "little", signed=True)
    header += height.to_bytes(4, "little", signed=True)
    return header + bytes(54 - len(header))


def errors(issues):
    return [issue for issue in issues if issue.is_error]


def warnings(issues):
    return [issue for issue in issues if not issue.is_error]


def fields(issues):
    return [issue.field for issue in issues]


class VersionCodeTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(M.parse_version_code("1.2.3"), 0x010203)
        self.assertEqual(M.parse_version_code("255.255.255"), 0xFFFFFF)
        self.assertEqual(M.parse_version_code("0.0.0"), 0)
        self.assertEqual(M.parse_version_code(0x010203), 0x010203)

    def test_parse_rejects_bad_values(self):
        for value in ("1.0", "1.2.3.4", "1.a.3", "256.0.0", "", "-1.0.0", True, 0x1000000, -1):
            with self.subTest(value=value):
                with self.assertRaises(M.PackageMetadataError):
                    M.parse_version_code(value)

    def test_format(self):
        self.assertEqual(M.format_version_code(0x010203), "1.2.3")
        self.assertEqual(M.format_version_code(0), "0.0.0")
        self.assertEqual(M.format_version_code(0xFFFFFF), "255.255.255")


class ImageDimensionTests(unittest.TestCase):
    def test_jpeg_dimensions(self):
        self.assertEqual(M.jpeg_dimensions(make_jpeg(256, 256)), (256, 256))
        self.assertEqual(M.jpeg_dimensions(make_jpeg(128, 64)), (128, 64))
        self.assertEqual(M.jpeg_dimensions(make_jpeg(1, 1)), (1, 1))

    def test_jpeg_dimensions_rejects_non_jpeg(self):
        self.assertIsNone(M.jpeg_dimensions(b""))
        self.assertIsNone(M.jpeg_dimensions(b"not a jpeg"))
        self.assertIsNone(M.jpeg_dimensions(bytes([0xFF, 0xE0, 0, 0])))

    def test_bmp_dimensions(self):
        self.assertEqual(M.bmp_dimensions(make_bmp(256, 256)), (256, 256))
        self.assertEqual(M.bmp_dimensions(make_bmp(32, -48)), (32, 48))
        self.assertIsNone(M.bmp_dimensions(b"BM"))
        self.assertIsNone(M.bmp_dimensions(b"XX" + bytes(30)))

    def test_image_dimensions_prefers_jpeg(self):
        self.assertEqual(M.image_dimensions(make_jpeg(256, 256)), (256, 256))
        self.assertEqual(M.image_dimensions(make_bmp(256, 256)), (256, 256))
        self.assertIsNone(M.image_dimensions(b"nope"))

    def test_is_jpeg_requires_soi_and_eoi(self):
        self.assertTrue(M.is_jpeg(make_jpeg(256, 256)))
        self.assertFalse(M.is_jpeg(make_jpeg(256, 256, eoi=False)))
        self.assertFalse(M.is_jpeg(b""))


class MetadataFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.icon = self.tmp / "icon.jpg"
        self.icon.write_bytes(make_jpeg(256, 256))
        self.romfs = self.tmp / "romfs"
        self.romfs.mkdir()
        (self.romfs / "hello.txt").write_text("hello", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def metadata(self, **overrides):
        kwargs = dict(
            title_name="Sample Game",
            title_author="GalNX",
            version="1.2.3",
            title_id=BASE,
            package_type=M.PackageType.SELF_CONTAINED_NSP,
            icon_path="icon.jpg",
            romfs_dir="romfs",
            startup_user_account=0,
            base_dir=self.tmp,
        )
        kwargs.update(overrides)
        return M.PackageMetadata(**kwargs)


class ValidateTests(MetadataFixture):
    def test_valid_self_contained_nsp(self):
        issues = self.metadata().validate()
        self.assertEqual(errors(issues), [])
        self.assertEqual(fields(warnings(issues)), ["title_id"])
        self.assertIn("outside the GalNX allocation block", warnings(issues)[0].message)

    def test_valid_nsp_in_galnx_block_has_no_issues(self):
        issues = self.metadata(title_id=GALNX_ID).validate()
        self.assertEqual(issues, [])

    def test_missing_required_text(self):
        issues = self.metadata(title_name="", title_author="").validate()
        self.assertIn("title_name", fields(errors(issues)))
        self.assertIn("title_author", fields(errors(issues)))

    def test_text_limits(self):
        issues = self.metadata(title_name="x" * 513, title_author="y" * 257).validate()
        self.assertIn("title_name", fields(errors(issues)))
        self.assertIn("title_author", fields(errors(issues)))

    def test_bad_version(self):
        issues = self.metadata(version="1.0").validate()
        self.assertIn("version", fields(errors(issues)))

    def test_title_id_required_for_nsp(self):
        issues = self.metadata(title_id="").validate()
        self.assertIn("title_id", fields(errors(issues)))

    def test_system_title_id_is_error_for_nsp(self):
        issues = self.metadata(title_id="0100000000000000").validate()
        self.assertIn("title_id", fields(errors(issues)))

    def test_icon_required_for_nsp(self):
        issues = self.metadata(icon_path=None).validate()
        self.assertIn("icon", fields(errors(issues)))

    def test_icon_missing_file(self):
        self.icon.unlink()
        issues = self.metadata().validate()
        self.assertIn("icon", fields(errors(issues)))

    def test_icon_wrong_size(self):
        self.icon.write_bytes(make_jpeg(128, 128))
        issues = self.metadata().validate()
        self.assertIn("icon", fields(errors(issues)))
        self.assertIn("256x256", errors(issues)[0].message)

    def test_icon_bmp_is_warning(self):
        self.icon.write_bytes(make_bmp(256, 256))
        issues = self.metadata().validate()
        self.assertEqual(errors(issues), [])
        self.assertTrue(any(issue.field == "icon" and "BMP" in issue.message for issue in warnings(issues)))

    def test_icon_garbage_is_error(self):
        self.icon.write_bytes(b"not an image")
        issues = self.metadata().validate()
        self.assertIn("icon", fields(errors(issues)))

    def test_icon_missing_eoi_is_warning(self):
        self.icon.write_bytes(make_jpeg(256, 256, eoi=False))
        issues = self.metadata().validate()
        self.assertEqual(errors(issues), [])
        self.assertTrue(any(issue.field == "icon" and "EOI" in issue.message for issue in warnings(issues)))

    def test_romfs_required_for_self_contained(self):
        issues = self.metadata(romfs_dir=None).validate()
        self.assertIn("romfs_dir", fields(errors(issues)))

    def test_romfs_missing_directory(self):
        issues = self.metadata(romfs_dir="missing-romfs").validate()
        self.assertIn("romfs_dir", fields(errors(issues)))

    def test_romfs_empty_directory_warns(self):
        empty = self.tmp / "empty-romfs"
        empty.mkdir()
        issues = self.metadata(romfs_dir="empty-romfs").validate()
        self.assertEqual(errors(issues), [])
        self.assertTrue(any(issue.field == "romfs_dir" and not issue.is_error for issue in issues))

    def test_forwarder_romfs_is_not_embedded(self):
        issues = self.metadata(
            package_type=M.PackageType.FORWARDER_NSP, romfs_dir="missing-romfs").validate()
        self.assertEqual(errors(issues), [])
        self.assertTrue(any(issue.field == "romfs_dir" and "ignored" in issue.message for issue in issues))

    def test_startup_user_account_range(self):
        for value in (3, -1, "1", True):
            with self.subTest(value=value):
                issues = self.metadata(startup_user_account=value).validate()
                self.assertIn("startup_user_account", fields(errors(issues)))

    def test_nro_ignores_nsp_only_fields(self):
        issues = self.metadata(
            package_type=M.PackageType.NRO, title_id="", icon_path=None,
            romfs_dir=None, startup_user_account=1).validate()
        self.assertEqual(errors(issues), [])
        self.assertTrue(any(issue.field == "startup_user_account" for issue in warnings(issues)))

    def test_nro_bad_title_id_is_warning(self):
        issues = self.metadata(package_type=M.PackageType.NRO, title_id="0100000000000000").validate()
        self.assertEqual(errors(issues), [])
        self.assertTrue(any(issue.field == "title_id" for issue in warnings(issues)))


class FromManifestTests(MetadataFixture):
    def manifest(self, **overrides):
        data = {
            "game": {"title": "Manifest Title", "version": "2.0.0"},
            "switch": {"title": "Switch Title", "author": "GalNX", "title_id": BASE, "icon": "icon.jpg"},
            "package": {"type": "self_contained_nsp", "romfs_dir": "romfs", "startup_user_account": 1},
        }
        data.update(overrides)
        return data

    def test_defaults_from_switch_and_game(self):
        metadata = M.PackageMetadata.from_manifest(self.manifest(), self.tmp)
        self.assertEqual(metadata.title_name, "Switch Title")
        self.assertEqual(metadata.title_author, "GalNX")
        self.assertEqual(metadata.version, "2.0.0")
        self.assertEqual(metadata.title_id, BASE)
        self.assertEqual(metadata.package_type, M.PackageType.SELF_CONTAINED_NSP)
        self.assertEqual(metadata.startup_user_account, 1)
        self.assertEqual(metadata.icon_file(), self.tmp / "icon.jpg")
        self.assertEqual(metadata.romfs_path(), self.tmp / "romfs")

    def test_type_derived_from_target(self):
        data = self.manifest()
        del data["package"]
        data["switch"]["target"] = "nro"
        self.assertEqual(M.PackageMetadata.from_manifest(data, self.tmp).package_type, M.PackageType.NRO)
        data["switch"]["target"] = "nsp"
        self.assertEqual(
            M.PackageMetadata.from_manifest(data, self.tmp).package_type,
            M.PackageType.SELF_CONTAINED_NSP)

    def test_explicit_forwarder_type(self):
        data = self.manifest()
        data["package"] = {"type": "forwarder_nsp"}
        metadata = M.PackageMetadata.from_manifest(data, self.tmp)
        self.assertEqual(metadata.package_type, M.PackageType.FORWARDER_NSP)
        self.assertIsNone(metadata.romfs_dir)

    def test_unknown_type_raises(self):
        data = self.manifest()
        data["package"] = {"type": "zip"}
        with self.assertRaises(M.PackageMetadataError) as ctx:
            M.PackageMetadata.from_manifest(data, self.tmp)
        self.assertIn("self_contained_nsp", str(ctx.exception))

    def test_bad_startup_user_account_raises(self):
        data = self.manifest()
        data["package"] = {"type": "self_contained_nsp", "startup_user_account": "one"}
        with self.assertRaises(M.PackageMetadataError):
            M.PackageMetadata.from_manifest(data, self.tmp)

    def test_non_mapping_sections_raise(self):
        with self.assertRaises(M.PackageMetadataError):
            M.PackageMetadata.from_manifest([], self.tmp)
        data = self.manifest()
        data["package"] = ["x"]
        with self.assertRaises(M.PackageMetadataError):
            M.PackageMetadata.from_manifest(data, self.tmp)

    def test_fallbacks(self):
        data = {
            "game": {"title": "Game Only"},
            "switch": {"target": "nro"},
        }
        metadata = M.PackageMetadata.from_manifest(data, self.tmp)
        self.assertEqual(metadata.title_name, "Game Only")
        self.assertEqual(metadata.title_author, "GalNX")
        self.assertEqual(metadata.version, "1.0.0")
        self.assertIsNone(metadata.icon_path)


class ToDictTests(MetadataFixture):
    def test_to_dict_keys_and_values(self):
        payload = self.metadata().to_dict()
        self.assertEqual(set(payload), {
            "type", "type_label", "title_name", "title_author", "version",
            "version_code", "title_id", "icon", "romfs_dir",
            "startup_user_account", "notes",
        })
        self.assertEqual(payload["type"], "self_contained_nsp")
        self.assertEqual(payload["type_label"], "self-contained NSP")
        self.assertEqual(payload["version_code"], 0x010203)
        self.assertEqual(payload["title_id"], BASE)
        self.assertEqual(payload["startup_user_account"], 0)

    def test_to_dict_bad_version_keeps_version_code_none(self):
        payload = self.metadata(version="bad").to_dict()
        self.assertIsNone(payload["version_code"])

    def test_formatted_title_id(self):
        self.assertEqual(self.metadata(title_id="0x0100a1b2c3d4e000").formatted_title_id(), BASE)
        self.assertEqual(self.metadata(title_id="").formatted_title_id(), "")

    def test_metadata_issue_payload(self):
        issue = M.MetadataIssue("icon", "boom", severity="warning")
        self.assertEqual(issue.to_dict(), {"field": "icon", "message": "boom", "severity": "warning"})
        with self.assertRaises(ValueError):
            M.MetadataIssue("icon", "boom", severity="fatal")


if __name__ == "__main__":
    unittest.main()
