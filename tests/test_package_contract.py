"""Unit tests for galnx.package.contract (M3-c NSP/NRO contract checks)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.package import contract as C  # noqa: E402

BASE = "0100A1B2C3D4E000"


def make_jpeg(width=256, height=256):
    app0 = bytes([0xFF, 0xE0, 0x00, 0x10]) + b"JFIF" + bytes([0]) + bytes([1, 1, 0, 0, 1, 0, 1, 0, 0])
    sof = bytes([0xFF, 0xC0, 0x00, 0x11, 0x08,
                 (height >> 8) & 0xFF, height & 0xFF,
                 (width >> 8) & 0xFF, width & 0xFF, 0x03])
    sof += bytes([1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    return bytes([0xFF, 0xD8]) + app0 + sof + bytes([0xFF, 0xD9])


def make_bmp(width=256, height=256):
    header = b"BM" + (54).to_bytes(4, "little") + bytes(4) + (54).to_bytes(4, "little")
    header += (40).to_bytes(4, "little")
    header += width.to_bytes(4, "little", signed=True)
    header += height.to_bytes(4, "little", signed=True)
    return header + bytes(54 - len(header))


def make_nacp(title=b"Sample Game"):
    data = bytearray(0x4000)
    data[:len(title)] = title
    return bytes(data)


def statuses(checks):
    return {check.id: check.status for check in checks}


def by_id(checks, check_id):
    for check in checks:
        if check.id == check_id:
            return check
    raise AssertionError("check id not found: " + check_id)


class DirFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "stage"
        self.root.mkdir()
        self.stage()

    def tearDown(self):
        self._tmp.cleanup()

    def stage(self):
        exefs = self.root / "exefs"
        exefs.mkdir()
        (exefs / "main").write_bytes(b"NSO0" + bytes(0x40))
        (exefs / "main.npdm").write_bytes(b"META" + bytes(0x100))
        control = self.root / "control"
        control.mkdir()
        (control / "control.nacp").write_bytes(make_nacp())
        (control / "icon_AmericanEnglish.dat").write_bytes(make_jpeg(256, 256))
        romfs = self.root / "romfs"
        romfs.mkdir()
        (romfs / "hello.txt").write_text("hello", encoding="utf-8")


class ValidNspDirTests(DirFixture):
    def test_all_ok(self):
        checks = C.check_dir(self.root)
        self.assertFalse(C.has_failures(checks))
        self.assertEqual(statuses(checks), {
            "contract.exefs.main": "ok",
            "contract.exefs.npdm": "ok",
            "contract.control.nacp": "ok",
            "contract.control.nacp.title": "ok",
            "contract.control.icon": "ok",
            "contract.romfs": "ok",
        })
        self.assertIn("title name: Sample Game", by_id(checks, "contract.control.nacp.title").detail)
        self.assertIn("NSO0 executable", by_id(checks, "contract.exefs.main").detail)
        self.assertIn("1 files", by_id(checks, "contract.romfs").detail)

    def test_accepts_string_package_type(self):
        checks = C.check_dir(str(self.root), "self_contained_nsp")
        self.assertFalse(C.has_failures(checks))

    def test_checks_serialize(self):
        checks = C.check_dir(self.root)
        payload = C.checks_to_dict(checks)
        self.assertEqual(len(payload), len(checks))
        self.assertEqual(set(payload[0]), {"id", "name", "status", "detail", "hint"})


class VariantTests(DirFixture):
    def test_missing_dir(self):
        checks = C.check_dir(self.root / "nope")
        self.assertEqual(by_id(checks, "contract.dir").status, "fail")

    def test_unknown_package_type(self):
        checks = C.check_dir(self.root, "zip")
        self.assertEqual(by_id(checks, "contract.type").status, "fail")

    def test_missing_exefs_main(self):
        (self.root / "exefs" / "main").unlink()
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.exefs.main").status, "fail")

    def test_nro_in_exefs_is_warning(self):
        (self.root / "exefs" / "main").write_bytes(b"NRO0" + bytes(0x40))
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.exefs.main").status, "warn")

    def test_garbage_exefs_main_is_failure(self):
        (self.root / "exefs" / "main").write_bytes(b"XXXX" + bytes(0x40))
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.exefs.main").status, "fail")

    def test_npdm_bad_magic(self):
        (self.root / "exefs" / "main.npdm").write_bytes(b"XXXX" + bytes(0x100))
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.exefs.npdm").status, "fail")

    def test_npdm_too_small(self):
        (self.root / "exefs" / "main.npdm").write_bytes(b"META")
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.exefs.npdm").status, "fail")

    def test_missing_npdm(self):
        (self.root / "exefs" / "main.npdm").unlink()
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.exefs.npdm").status, "fail")

    def test_nacp_wrong_size(self):
        (self.root / "control" / "control.nacp").write_bytes(bytes(0x1000))
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.control.nacp").status, "fail")

    def test_nacp_empty_title_warns(self):
        (self.root / "control" / "control.nacp").write_bytes(bytes(0x4000))
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.control.nacp").status, "ok")
        self.assertEqual(by_id(checks, "contract.control.nacp.title").status, "warn")

    def test_missing_icon(self):
        (self.root / "control" / "icon_AmericanEnglish.dat").unlink()
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.control.icon").status, "fail")

    def test_wrong_size_icon(self):
        (self.root / "control" / "icon_AmericanEnglish.dat").write_bytes(make_jpeg(128, 128))
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.control.icon").status, "fail")

    def test_bmp_icon_warns(self):
        (self.root / "control" / "icon_AmericanEnglish.dat").write_bytes(make_bmp(256, 256))
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.control.icon").status, "warn")

    def test_garbage_icon_fails(self):
        (self.root / "control" / "icon_AmericanEnglish.dat").write_bytes(b"nope")
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.control.icon").status, "fail")

    def test_missing_romfs_fails_for_self_contained(self):
        import shutil
        shutil.rmtree(self.root / "romfs")
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.romfs").status, "fail")

    def test_empty_romfs_warns(self):
        (self.root / "romfs" / "hello.txt").unlink()
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.romfs").status, "warn")

    def test_forwarder_skips_romfs(self):
        import shutil
        shutil.rmtree(self.root / "romfs")
        checks = C.check_dir(self.root, "forwarder_nsp")
        self.assertEqual(by_id(checks, "contract.romfs").status, "skip")

    def test_npdm_json_matching_title_id(self):
        (self.root / "npdm.json").write_text(
            '{"name": "Application", "title_id": "' + BASE + '"}', encoding="utf-8")
        checks = C.check_dir(self.root, expected_title_id=BASE)
        self.assertEqual(by_id(checks, "contract.npdm_json.name").status, "ok")
        self.assertEqual(by_id(checks, "contract.npdm_json.title_id").status, "ok")

    def test_npdm_json_title_id_mismatch(self):
        (self.root / "npdm.json").write_text(
            '{"name": "Application", "title_id": "' + BASE + '"}', encoding="utf-8")
        checks = C.check_dir(self.root, expected_title_id="010047414C4E0000")
        self.assertEqual(by_id(checks, "contract.npdm_json.title_id").status, "fail")

    def test_npdm_json_wrong_name_warns(self):
        (self.root / "npdm.json").write_text('{"name": "SystemProgram"}', encoding="utf-8")
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.npdm_json.name").status, "warn")

    def test_npdm_json_bad_json_warns(self):
        (self.root / "npdm.json").write_text("{not json", encoding="utf-8")
        checks = C.check_dir(self.root)
        self.assertEqual(by_id(checks, "contract.npdm_json").status, "warn")

MINIMAL = (
    "[WARNING] Failed to load title.keys keyfile." + chr(10) +
    "[PartitionFs]" + chr(10) +
    "  Type:        PFS0" + chr(10) +
    "  FileNum:     3" + chr(10)
)

FULL = (
    "[PartitionFs]" + chr(10) +
    "  Type:        PFS0" + chr(10) +
    "  FileNum:     3" + chr(10) +
    "[NCA Header]" + chr(10) +
    "  Content Type:    Program" + chr(10) +
    "  ProgID:          0x0100000000001000" + chr(10) +
    "  Size:            0x2dc00" + chr(10) +
    "[NCA Header]" + chr(10) +
    "  Content Type:    Control" + chr(10) +
    "  ProgID:          0x0100000000001000" + chr(10) +
    "  Size:            0x1cc00" + chr(10) +
    "[NCA Header]" + chr(10) +
    "  Content Type:    Meta" + chr(10) +
    "  ProgID:          0x0100000000001000" + chr(10) +
    "  Size:            0x1000" + chr(10)
)


class ParseNstoolTests(unittest.TestCase):
    def test_minimal_partition_only(self):
        parsed = C.parse_nstool_output(MINIMAL)
        self.assertEqual(parsed["partition"]["Type"], "PFS0")
        self.assertEqual(parsed["partition"]["FileNum"], "3")
        self.assertEqual(parsed["ncas"], [])

    def test_full_three_ncas(self):
        parsed = C.parse_nstool_output(FULL)
        self.assertEqual(len(parsed["ncas"]), 3)
        self.assertEqual(parsed["ncas"][0]["Content Type"], "Program")
        self.assertEqual(parsed["ncas"][1]["Content Type"], "Control")
        self.assertEqual(parsed["ncas"][2]["Content Type"], "Meta")

    def test_sections_order(self):
        parsed = C.parse_nstool_output(FULL)
        names = [name for name, _ in parsed["sections"]]
        self.assertEqual(names, ["PartitionFs", "NCA Header", "NCA Header", "NCA Header"])

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            C.parse_nstool_output(None)


class CheckNstoolTests(unittest.TestCase):
    def test_partition_only_warns_about_missing_ncas(self):
        checks = C.check_nstool(C.parse_nstool_output(MINIMAL))
        got = statuses(checks)
        self.assertEqual(got["nstool.partition.type"], "ok")
        self.assertEqual(got["nstool.partition.files"], "ok")
        self.assertEqual(got["nstool.ncas"], "warn")
        self.assertNotIn("nstool.nca.type.program", got)

    def test_full_nsp_ok(self):
        checks = C.check_nstool(C.parse_nstool_output(FULL))
        self.assertFalse(C.has_failures(checks))
        got = statuses(checks)
        self.assertEqual(got["nstool.nca.type.program"], "ok")
        self.assertEqual(got["nstool.nca.type.control"], "ok")
        self.assertEqual(got["nstool.nca.type.meta"], "ok")
        self.assertEqual(got["nstool.progid.consistent"], "ok")
        self.assertIn("all 3 NCAs share ProgID 0x0100000000001000",
                      by_id(checks, "nstool.progid.consistent").detail)

    def test_missing_partition(self):
        checks = C.check_nstool({})
        self.assertEqual(by_id(checks, "nstool.partition").status, "fail")

    def test_wrong_partition_type(self):
        checks = C.check_nstool({"partition": {"Type": "RomFs", "FileNum": "3"}, "ncas": []})
        self.assertEqual(by_id(checks, "nstool.partition.type").status, "fail")

    def test_wrong_file_num(self):
        checks = C.check_nstool({"partition": {"Type": "PFS0", "FileNum": "2"}, "ncas": []})
        self.assertEqual(by_id(checks, "nstool.partition.files").status, "fail")

    def test_missing_meta_nca(self):
        parsed = C.parse_nstool_output(FULL)
        parsed["ncas"] = [nca for nca in parsed["ncas"] if nca["Content Type"] != "Meta"]
        checks = C.check_nstool(parsed)
        self.assertEqual(by_id(checks, "nstool.nca.type.meta").status, "fail")

    def test_inconsistent_prog_ids(self):
        parsed = C.parse_nstool_output(FULL)
        parsed["ncas"][0]["ProgID"] = "0x0100A1B2C3D4E000"
        checks = C.check_nstool(parsed)
        self.assertEqual(by_id(checks, "nstool.progid.consistent").status, "fail")

    def test_expected_title_id_matches(self):
        checks = C.check_nstool(C.parse_nstool_output(FULL), expected_title_id="0100000000001000")
        self.assertEqual(by_id(checks, "nstool.progid.expected").status, "ok")

    def test_expected_title_id_mismatch(self):
        checks = C.check_nstool(C.parse_nstool_output(FULL), expected_title_id="0100A1B2C3D4E000")
        self.assertEqual(by_id(checks, "nstool.progid.expected").status, "fail")

    def test_expected_title_id_invalid_warns(self):
        checks = C.check_nstool(C.parse_nstool_output(FULL), expected_title_id="zzz")
        self.assertEqual(by_id(checks, "nstool.progid.expected").status, "warn")


class LoadNstoolFileTests(unittest.TestCase):
    def test_load_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nstool.log"
            path.write_text(FULL, encoding="utf-8")
            parsed = C.load_nstool_file(path)
        self.assertEqual(len(parsed["ncas"]), 3)


class CheckSerializationTests(unittest.TestCase):
    def test_check_dict_and_status_validation(self):
        check = C.Check("x", "X", "warn", "detail", "hint")
        payload = check.to_dict()
        self.assertEqual(payload, {"id": "x", "name": "X", "status": "warn",
                                   "detail": "detail", "hint": "hint"})
        self.assertFalse(check.is_fail)
        self.assertEqual(check.to_json(), payload)
        with self.assertRaises(ValueError):
            C.Check("x", "X", "bogus")


if __name__ == "__main__":
    unittest.main()
