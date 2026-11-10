"""Tests for the engine registry and manifest/engine consistency (M4-a)."""
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import engines
from galnx import manifest as manifest_module


def write_descriptor(directory, data, name=None):
    path = Path(directory) / (name or (data["id"] + ".yaml"))
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def variant(engine_id, **changes):
    data = engines.KRKRSDL2.to_dict()
    data["id"] = engine_id
    data.update(changes)
    return data


class RegistryTests(unittest.TestCase):
    def test_builtin_registry(self):
        registry = engines.EngineRegistry.builtin()
        self.assertEqual(registry.ids(), ("brewser", "krkrsdl2", "onscripter-nx"))
        self.assertEqual(len(registry), 3)
        self.assertIn("krkrsdl2", registry)
        self.assertIn("onscripter-nx", registry)
        self.assertEqual(registry.get("onscripter-nx").build_backend, "devkitpro-make")
        self.assertNotIn("renpy", registry)
        self.assertEqual(registry.get("krkrsdl2").display_name, "KiriKiri SDL2")
        self.assertIsNone(registry.get("renpy"))

    def test_require_unknown_message(self):
        registry = engines.builtin_registry()
        with self.assertRaises(engines.EngineRegistryError) as ctx:
            registry.require("renpy")
        message = str(ctx.exception)
        self.assertIn("unknown engine adapter", message)
        self.assertIn("brewser", message)
        self.assertIn("krkrsdl2", message)

    def test_descriptors_are_sorted_and_summarised(self):
        registry = engines.EngineRegistry.builtin()
        descriptors = registry.descriptors()
        self.assertEqual([item.id for item in descriptors], ["brewser", "krkrsdl2", "onscripter-nx"])
        summaries = registry.summary()
        self.assertEqual([item["id"] for item in summaries], ["brewser", "krkrsdl2", "onscripter-nx"])
        self.assertEqual(sorted(summaries[1]), sorted(engines.KRKRSDL2.summary()))

    def test_register_rejects_duplicates_and_invalid(self):
        registry = engines.EngineRegistry()
        registry.register(engines.KRKRSDL2)
        with self.assertRaises(engines.EngineRegistryError) as ctx:
            registry.register(engines.KRKRSDL2)
        self.assertIn("already registered", str(ctx.exception))
        self.assertEqual(len(registry.register(engines.KRKRSDL2, replace=True).id and registry), 1)
        broken = engines.EngineDescriptor(id="broken", display_name="")
        with self.assertRaises(engines.EngineRegistryError) as ctx:
            registry.register(broken)
        self.assertIn("invalid engine descriptor", str(ctx.exception))
        with self.assertRaises(engines.EngineRegistryError):
            engines.EngineRegistry([engines.KRKRSDL2, engines.KRKRSDL2])

    def test_load_file_and_load_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            one = write_descriptor(tmp, variant("custom-a"))
            write_descriptor(tmp, variant("custom-b"))
            registry = engines.EngineRegistry.builtin()
            loaded = registry.load_file(one)
            self.assertEqual(loaded.id, "custom-a")
            self.assertEqual(registry.ids(), ("brewser", "custom-a", "krkrsdl2", "onscripter-nx"))
            many = engines.EngineRegistry.builtin().load_dir(tmp)
            self.assertEqual([item.id for item in many], ["custom-a", "custom-b"])

    def test_load_dir_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope"
            with self.assertRaises(engines.EngineRegistryError) as ctx:
                engines.EngineRegistry.builtin().load_dir(missing)
            self.assertIn("directory not found", str(ctx.exception))

    def test_registry_for_engines_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_descriptor(tmp, variant("custom-a"))
            registry, errors = engines.registry_for(tmp)
            self.assertEqual(errors, [])
            self.assertIn("custom-a", registry)
            registry, errors = engines.registry_for([tmp, Path(tmp) / "missing"])
            self.assertIn("custom-a", registry)
            self.assertEqual(len(errors), 1)
            self.assertTrue(errors[0].startswith("engines: "))
            self.assertIn("directory not found", errors[0])

    def test_registry_for_accepts_none_and_empty(self):
        for value in (None, "", []):
            with self.subTest(value=value):
                registry, errors = engines.registry_for(value)
                self.assertEqual(errors, [])
                self.assertEqual(registry.ids(), ("brewser", "krkrsdl2", "onscripter-nx"))


class ManifestConsistencyTests(unittest.TestCase):
    def test_example_manifest_is_valid(self):
        data, errors = manifest_module.load_and_validate(ROOT / "examples" / "manifest.krkr.yaml")
        self.assertEqual(errors, [])
        self.assertIsNotNone(data)
        self.assertEqual(engines.validate_manifest_engine(data["engine"]), [])

    def test_onscripter_manifest_is_valid(self):
        data, errors = manifest_module.load_and_validate(ROOT / "examples" / "manifest.onscripter.yaml")
        self.assertEqual(errors, [])
        self.assertIsNotNone(data)
        self.assertEqual(data["engine"]["adapter"], "onscripter-nx")
        examples = ROOT / "examples"
        self.assertEqual(engines.validate_manifest_engine(data["engine"], base_dir=examples), [])
        self.assertEqual(engines.manifest_engine_warnings(data["engine"], base_dir=examples), [])

    def test_none_section_is_ignored(self):
        self.assertEqual(engines.validate_manifest_engine(None), [])

    def test_non_mapping_section(self):
        self.assertEqual(engines.validate_manifest_engine(["krkrsdl2"]), ["engine: must be a mapping"])

    def test_missing_adapter(self):
        self.assertEqual(engines.validate_manifest_engine({}), ["engine.adapter: required"])
        self.assertEqual(engines.validate_manifest_engine({"adapter": ""}), ["engine.adapter: required"])

    def test_unknown_adapter(self):
        errors = engines.validate_manifest_engine({"adapter": "renpy"})
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown engine adapter", errors[0])
        self.assertIn("engine.adapter", errors[0])

    def test_descriptor_from_engines_dir_registers_unknown_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_descriptor(tmp, variant("custom-a"))
            section = {"adapter": "custom-a"}
            self.assertEqual(engines.validate_manifest_engine(section, engines_dir=tmp), [])
            self.assertEqual(engines.validate_manifest_engine(section), [
                "engine.adapter: unknown engine adapter " + repr("custom-a")
                + " (registered: brewser, krkrsdl2, onscripter-nx; "
                "add a descriptor via engine.descriptor or --engines-dir)",
            ])

    def test_engine_descriptor_relative_to_manifest_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_descriptor(tmp, variant("custom-a"), name="custom.yaml")
            section = {"adapter": "custom-a", "descriptor": "custom.yaml"}
            self.assertEqual(engines.validate_manifest_engine(section, base_dir=tmp), [])
            registry, errors = engines.registry_for_manifest(section, base_dir=tmp)
            self.assertEqual(errors, [])
            self.assertIn("custom-a", registry)

    def test_engine_descriptor_id_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_descriptor(tmp, variant("custom-a"), name="custom.yaml")
            section = {"adapter": "custom-b", "descriptor": "custom.yaml"}
            errors = engines.validate_manifest_engine(section, base_dir=tmp)
            self.assertEqual(len(errors), 1)
            self.assertIn("engine.descriptor", errors[0])
            self.assertIn("does not match", errors[0])

    def test_engine_descriptor_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            section = {"adapter": "custom-a", "descriptor": "missing.yaml"}
            errors = engines.validate_manifest_engine(section, base_dir=tmp)
            self.assertEqual(len(errors), 1)
            self.assertTrue(errors[0].startswith("engine.descriptor: "))
            self.assertIn("not found", errors[0])

    def test_manifest_validate_reports_unknown_adapter(self):
        data = yaml.safe_load((ROOT / "examples" / "manifest.krkr.yaml").read_text(encoding="utf-8"))
        data["engine"]["adapter"] = "krkrsdl2"
        self.assertEqual(manifest_module.validate(data), [])
        data["engine"]["adapter"] = "renpy"
        errors = manifest_module.validate(data)
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown engine adapter", errors[0])


class WarningTests(unittest.TestCase):
    def _section(self, engine_id, adapter_version=None):
        section = {"adapter": engine_id}
        if adapter_version is not None:
            section["adapter_version"] = adapter_version
        return section

    def test_ready_adapter_has_no_warnings(self):
        self.assertEqual(
            engines.manifest_engine_warnings(self._section("krkrsdl2", "krkrsdl2@124bdf84 (2026-10-01)")),
            [],
        )

    def test_blocked_adapter_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = variant("blocked-engine", status="blocked", status_reason="does not boot on firmware 23.0.0")
            write_descriptor(tmp, data)
            warnings = engines.manifest_engine_warnings(self._section("blocked-engine"), engines_dir=tmp)
            self.assertEqual(len(warnings), 1)
            self.assertIn("blocked", warnings[0])
            self.assertIn("does not boot", warnings[0])
            # never-ready: the manifest still validates (a warning, not an error)
            self.assertEqual(engines.validate_manifest_engine(self._section("blocked-engine"), engines_dir=tmp), [])

    def test_research_adapter_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = variant("research-engine", status="research", status_reason="no successful build yet")
            write_descriptor(tmp, data)
            warnings = engines.manifest_engine_warnings(self._section("research-engine"), engines_dir=tmp)
            self.assertEqual(len(warnings), 1)
            self.assertIn("research", warnings[0])

    def test_adapter_version_must_mention_pinned_commit(self):
        warnings = engines.manifest_engine_warnings(self._section("krkrsdl2", "krkrsdl2@deadbeef"))
        self.assertEqual(len(warnings), 1)
        self.assertIn("does not mention the pinned commit", warnings[0])
        self.assertIn("124bdf84", warnings[0])
        self.assertEqual(engines.manifest_engine_warnings(self._section("krkrsdl2", None)), [])

    def test_unknown_adapter_has_no_warnings(self):
        self.assertEqual(engines.manifest_engine_warnings(self._section("renpy")), [])
        self.assertEqual(engines.manifest_engine_warnings(["not a mapping"]), [])


if __name__ == "__main__":
    unittest.main()
