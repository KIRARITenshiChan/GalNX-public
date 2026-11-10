"""Unit tests for galnx.package.registry (M3-c TitleID registry)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.package import registry as R  # noqa: E402

BASE = "0100A1B2C3D4E000"
GALNX_ID = "010047414C4E0000"
EXAMPLE_REGISTRY = ROOT / "examples" / "packaging" / "titleid-registry.json"


class EntryTests(unittest.TestCase):
    def test_normalizes_title_id(self):
        entry = R.TitleIdEntry("0x0100a1b2c3d4e000", "demo")
        self.assertEqual(entry.title_id, BASE)
        self.assertEqual(entry.note, "")

    def test_name_is_required(self):
        with self.assertRaises(R.RegistryError):
            R.TitleIdEntry(BASE, "")
        with self.assertRaises(R.RegistryError):
            R.TitleIdEntry(BASE, "   ")

    def test_invalid_title_id_rejected(self):
        for value in ("", "zz", "0100A1B2C3D4E00"):
            with self.subTest(value=value):
                with self.assertRaises(R.RegistryError):
                    R.TitleIdEntry(value, "demo")

    def test_from_dict(self):
        entry = R.TitleIdEntry.from_dict({"title_id": BASE, "name": "demo", "note": "hi"})
        self.assertEqual(entry.to_dict(), {"title_id": BASE, "name": "demo", "note": "hi"})

    def test_from_dict_rejects_unknown_keys(self):
        with self.assertRaises(R.RegistryError) as ctx:
            R.TitleIdEntry.from_dict({"title_id": BASE, "name": "demo", "secret": "prod.keys"})
        self.assertIn("must not store secrets", str(ctx.exception))

    def test_from_dict_requires_title_id_and_name(self):
        with self.assertRaises(R.RegistryError):
            R.TitleIdEntry.from_dict({"title_id": BASE})
        with self.assertRaises(R.RegistryError):
            R.TitleIdEntry.from_dict({"name": "demo"})
        with self.assertRaises(R.RegistryError):
            R.TitleIdEntry.from_dict(["not", "a", "mapping"])

    def test_from_dict_rejects_non_string_note(self):
        with self.assertRaises(R.RegistryError):
            R.TitleIdEntry.from_dict({"title_id": BASE, "name": "demo", "note": 5})

    def test_validate_flags_system_id(self):
        entry = R.TitleIdEntry("0100000000000000", "fs")
        codes = [(issue.severity, issue.code) for issue in entry.validate()]
        self.assertIn(("error", "system_reserved"), codes)


class RegistryFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_missing_file_is_empty(self):
        registry = R.load_registry(self.tmp / "none.json")
        self.assertEqual(len(registry), 0)
        self.assertEqual(registry.entries, [])

    def test_load_missing_file_strict_raises(self):
        with self.assertRaises(R.RegistryError):
            R.load_registry(self.tmp / "none.json", missing_ok=False)

    def test_load_bad_json_raises(self):
        path = self.tmp / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(R.RegistryError) as ctx:
            R.load_registry(path)
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_save_load_roundtrip(self):
        path = self.tmp / "registry.json"
        registry = R.TitleIdRegistry(entries=[R.TitleIdEntry(GALNX_ID, "sample")])
        written = registry.save(path)
        self.assertEqual(written, path)
        loaded = R.load_registry(path)
        self.assertEqual(loaded.ids(), [GALNX_ID])
        self.assertEqual(loaded.find(GALNX_ID).name, "sample")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["generated_by"], "galnx")
        self.assertEqual(payload["entries"][0]["title_id"], GALNX_ID)

    def test_save_without_path_raises(self):
        with self.assertRaises(R.RegistryError):
            R.TitleIdRegistry().save()

    def test_from_dict_rejects_bad_schema_version(self):
        with self.assertRaises(R.RegistryError) as ctx:
            R.TitleIdRegistry.from_dict({"schema_version": 2, "entries": []})
        self.assertIn("schema_version", str(ctx.exception))

    def test_from_dict_rejects_non_list_entries(self):
        with self.assertRaises(R.RegistryError):
            R.TitleIdRegistry.from_dict({"schema_version": 1, "entries": {}})
        with self.assertRaises(R.RegistryError):
            R.TitleIdRegistry.from_dict([])


class RegistryQueryTests(unittest.TestCase):
    def registry(self):
        return R.TitleIdRegistry(entries=[
            R.TitleIdEntry(GALNX_ID, "sample-game"),
            R.TitleIdEntry("010047414C4E2000", "second-game"),
        ])

    def test_ids_find_find_by_name(self):
        registry = self.registry()
        self.assertEqual(registry.ids(), [GALNX_ID, "010047414C4E2000"])
        self.assertEqual(registry.find(GALNX_ID).name, "sample-game")
        self.assertEqual(registry.find("0x010047414c4e0000").name, "sample-game")
        self.assertIsNone(registry.find("0100A1B2C3D4E000"))
        self.assertIsNone(registry.find("zz"))
        self.assertEqual(registry.find_by_name("second-game").title_id, "010047414C4E2000")
        self.assertIsNone(registry.find_by_name("nope"))

    def test_add_and_duplicate(self):
        registry = R.TitleIdRegistry()
        registry.add(R.TitleIdEntry("010047414C4E4000", "third"))
        self.assertEqual(len(registry), 1)
        with self.assertRaises(R.RegistryError) as ctx:
            registry.add(R.TitleIdEntry("010047414C4E4000", "again"))
        self.assertIn("already registered", str(ctx.exception))

    def test_add_replace(self):
        registry = R.TitleIdRegistry(entries=[R.TitleIdEntry(GALNX_ID, "old")])
        registry.add(R.TitleIdEntry(GALNX_ID, "new"), replace=True)
        self.assertEqual(len(registry), 1)
        self.assertEqual(registry.find(GALNX_ID).name, "new")

    def test_add_mapping(self):
        registry = R.TitleIdRegistry()
        registry.add({"title_id": "010047414C4E6000", "name": "from-dict"})
        self.assertEqual(registry.find("010047414C4E6000").name, "from-dict")

    def test_add_system_id_is_rejected_by_conflicts(self):
        registry = R.TitleIdRegistry()
        with self.assertRaises(R.RegistryError):
            registry.add(R.TitleIdEntry("0100000000000000", "fs"))

    def test_entries_sorted_by_title_id(self):
        registry = R.TitleIdRegistry()
        registry.add(R.TitleIdEntry("010047414C4E4000", "c"))
        registry.add(R.TitleIdEntry("010047414C4E2000", "b"))
        self.assertEqual(registry.ids(), ["010047414C4E2000", "010047414C4E4000"])

    def test_remove(self):
        registry = self.registry()
        self.assertTrue(registry.remove(GALNX_ID))
        self.assertEqual(registry.ids(), ["010047414C4E2000"])
        self.assertFalse(registry.remove(GALNX_ID))

    def test_conflicts_for(self):
        registry = R.TitleIdRegistry()
        self.assertEqual(registry.conflicts_for(GALNX_ID), [])
        codes = [(issue.severity, issue.code) for issue in registry.conflicts_for(BASE)]
        self.assertEqual(codes, [("warning", "outside_allocation_block")])
        registry.add(R.TitleIdEntry(GALNX_ID, "sample"))
        codes = [(issue.severity, issue.code) for issue in registry.conflicts_for(GALNX_ID)]
        self.assertNotIn(("error", "duplicate"), codes)

    def test_conflicts_and_errors(self):
        registry = R.TitleIdRegistry(entries=[R.TitleIdEntry("0100000000000000", "fs")])
        self.assertTrue(any(issue.is_error for issue in registry.conflicts()))
        errors = registry.errors()
        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("fs:", errors[0])


class ExampleRegistryTests(unittest.TestCase):
    def test_example_registry_loads(self):
        self.assertTrue(EXAMPLE_REGISTRY.is_file())
        registry = R.load_registry(EXAMPLE_REGISTRY, missing_ok=False)
        self.assertEqual(len(registry), 1)
        entry = registry.find(BASE)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.name, "sample-kirikiri-game")

    def test_example_registry_has_no_secret_keys(self):
        payload = json.loads(EXAMPLE_REGISTRY.read_text(encoding="utf-8"))
        for item in payload["entries"]:
            self.assertEqual(set(item), {"title_id", "name", "note"})


if __name__ == "__main__":
    unittest.main()
