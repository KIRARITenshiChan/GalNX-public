"""Tests for the engine descriptor model (M4-a)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import engines
from galnx.input import list_builtin_names

KRKR_KEYS = [
    "id", "display_name", "upstream_url", "pinned_commit", "pinned_version",
    "license_spdx", "license_url", "license_notes", "target_kind", "build_backend",
    "capabilities", "default_input_profile", "artifact_naming", "content_layout",
    "status", "status_reason", "artifact_sha256", "evidence_urls", "notes",
]
CORE_KEYS = [
    "id", "display_name", "upstream_url", "pinned_commit", "pinned_version",
    "license_spdx", "target_kind", "build_backend", "default_input_profile",
    "artifact_naming", "content_layout", "status", "artifact_sha256",
]
CAPABILITY_KEYS = ["audio", "graphics", "input", "movie", "save", "touch"]
OPTIONAL_KEYS = ["verification"]
VERIFICATIONS = [
    "source_review", "build_verified", "emulator_verified", "device_verified",
    "game_verified", "partial", "unknown", "in_progress",
]


def descriptor_dict(engine_id="krkrsdl2"):
    return engines.BUILTIN_ENGINES[engine_id].to_dict()


class BuiltinDescriptorTests(unittest.TestCase):
    def test_builtin_registry_has_three_engines(self):
        registry = engines.EngineRegistry.builtin()
        self.assertEqual(registry.ids(), ("brewser", "krkrsdl2", "onscripter-nx"))
        self.assertEqual(len(registry), 3)
        self.assertIn("krkrsdl2", registry)
        self.assertIn("onscripter-nx", registry)
        self.assertEqual(engines.BUILTIN_ORDER, ("krkrsdl2", "brewser", "onscripter-nx"))

    def test_builtin_descriptors_validate(self):
        for engine_id in ("krkrsdl2", "brewser", "onscripter-nx"):
            with self.subTest(engine=engine_id):
                descriptor = engines.BUILTIN_ENGINES[engine_id]
                self.assertEqual(descriptor.validate(), [])
                self.assertFalse(descriptor.is_ready)
                self.assertEqual(descriptor.status, "research")
                self.assertEqual(descriptor.warnings, ())

    def test_builtin_descriptors_match_schema(self):
        for engine_id in ("krkrsdl2", "brewser", "onscripter-nx"):
            with self.subTest(engine=engine_id):
                self.assertEqual(engines.validate_descriptor_data(descriptor_dict(engine_id)), [])

    def test_to_dict_and_summary_keys(self):
        data = engines.KRKRSDL2.to_dict()
        self.assertEqual(sorted(data), sorted(KRKR_KEYS + OPTIONAL_KEYS))
        summary = engines.KRKRSDL2.summary()
        self.assertEqual(len(summary), 11)
        self.assertIn("license_spdx", summary)
        self.assertNotIn("capabilities", summary)

    def test_krkrsdl2_pins_commit_license_and_layout(self):
        descriptor = engines.KRKRSDL2
        self.assertEqual(descriptor.pinned_commit, "124bdf841f09e7ce02aa99b7b55791a0f7a900ff")
        self.assertEqual(descriptor.license_spdx, "MIT")
        self.assertIn("github.com/krkrsdl2/krkrsdl2", descriptor.license_url)
        self.assertEqual(descriptor.default_input_profile, "krkrsdl2")
        self.assertEqual(descriptor.target_kind, "nro")
        self.assertEqual(descriptor.build_backend, "cmake-switch")
        self.assertEqual(descriptor.content_layout["mode"], "romfs")
        self.assertEqual(descriptor.content_layout["entry"], "data.xp3")
        self.assertIn(descriptor.default_input_profile, list_builtin_names())

    def test_brewser_is_prebuilt_web_engine(self):
        descriptor = engines.BREWSER
        self.assertEqual(descriptor.target_kind, "web")
        self.assertEqual(descriptor.build_backend, "prebuilt")
        self.assertEqual(
            descriptor.artifact_sha256,
            "8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13",
        )
        self.assertEqual(descriptor.content_layout["mode"], "sdmc")
        self.assertIn("switch/brewser/apps", descriptor.content_layout["destination"])
        self.assertEqual(descriptor.default_input_profile, "kb_mouse")

    def test_onscripter_nx_is_devkitpro_make_engine(self):
        descriptor = engines.ONSCRIPTER_NX
        self.assertEqual(descriptor.pinned_commit, "a8439a86393f74c503d28df176f010ca544af56f")
        self.assertEqual(descriptor.license_spdx, "GPL-2.0-or-later")
        self.assertIn("onscripter-nx", descriptor.license_url)
        self.assertEqual(descriptor.target_kind, "nro")
        self.assertEqual(descriptor.build_backend, "devkitpro-make")
        self.assertEqual(descriptor.content_layout["mode"], "romfs")
        self.assertEqual(descriptor.content_layout["entry"], "ons-content")
        self.assertEqual(descriptor.default_input_profile, "kb_mouse")
        self.assertIn(descriptor.default_input_profile, list_builtin_names())
        self.assertEqual(sorted(engines.CAPABILITY_KEYS), sorted(descriptor.capabilities))
        self.assertEqual(sorted(descriptor.capabilities), CAPABILITY_KEYS)
        self.assertTrue(descriptor.capabilities["graphics"]["supported"])
        self.assertTrue(descriptor.capabilities["input"]["supported"])
        self.assertTrue(descriptor.capabilities["movie"]["supported"])
        self.assertEqual(descriptor.capabilities["movie"]["verification"], "unknown")
        self.assertFalse(descriptor.capabilities["audio"]["supported"])
        self.assertFalse(descriptor.capabilities["save"]["supported"])
        self.assertFalse(descriptor.capabilities["touch"]["supported"])
        for name in engines.REQUIRED_VERIFICATION_KEYS:
            self.assertIn(descriptor.capabilities[name]["verification"], VERIFICATIONS)
        self.assertEqual(
            engines.format_artifact_name(descriptor, "1.0.0"),
            "onscripter-nx-1.0.0.nro",
        )

    def test_capabilities_cover_six_keys(self):
        for engine_id in ("krkrsdl2", "brewser", "onscripter-nx"):
            with self.subTest(engine=engine_id):
                capabilities = engines.BUILTIN_ENGINES[engine_id].capabilities
                self.assertEqual(sorted(capabilities), CAPABILITY_KEYS)
                self.assertNotIn("video", capabilities)
                for name, entry in capabilities.items():
                    self.assertIsInstance(entry["supported"], bool)
                    self.assertIsInstance(entry["note"], str)
                    if name in engines.REQUIRED_VERIFICATION_KEYS:
                        self.assertIn(entry["verification"], VERIFICATIONS, name)


class ArtifactNamingTests(unittest.TestCase):
    def test_template_rendering(self):
        self.assertEqual(engines.format_artifact_name(engines.KRKRSDL2, "1.0"), "krkrsdl2-1.0.nro")
        self.assertEqual(engines.format_artifact_name(engines.BREWSER), "brewser.nro")

    def test_version_falls_back_to_pinned_version(self):
        name = engines.format_artifact_name(engines.BREWSER)
        self.assertEqual(name, "brewser.nro")
        descriptor = engines.EngineDescriptor(id="demo", display_name="Demo", upstream_url="https://example.invalid/demo",
                                              pinned_commit="0" * 40, license_spdx="MIT", license_url="https://example.invalid/license",
                                              target_kind="nro", build_backend="prebuilt", pinned_version="v1",
                                              artifact_naming="{id}-{version}.nro",
                                              capabilities={key: {"supported": True, "note": "", "verification": "unknown"}
                                                            for key in engines.CAPABILITY_KEYS})
        self.assertEqual(engines.format_artifact_name(descriptor), "demo-v1.nro")

    def test_placeholders(self):
        self.assertEqual(engines.artifact_placeholders("{id}-{version}.nro"), ["id", "version"])
        self.assertEqual(engines.artifact_placeholders("plain.nro"), [])
        self.assertEqual(engines.artifact_placeholders("{id.nro"), ["<unclosed>"])
        self.assertEqual(engines.artifact_placeholders("id}.nro"), ["<stray>"])
        self.assertEqual(engines.artifact_placeholders("{{id}}.nro"), [])


class ValidationTests(unittest.TestCase):
    def _bad(self, **changes):
        data = descriptor_dict()
        data.update(changes)
        return data

    def test_valid_copy_roundtrips(self):
        copy = descriptor_dict()
        descriptor = engines.descriptor_from_dict(copy)
        self.assertEqual(descriptor.to_dict(), copy)
        self.assertEqual(engines.descriptor_from_dict(copy, validate_schema=False).id, "krkrsdl2")

    def test_bad_slug(self):
        with self.assertRaises(engines.EngineDescriptorError):
            engines.descriptor_from_dict(self._bad(id="Krkr_SDL2"))

    def test_bad_upstream_url(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(upstream_url="http://example.invalid/repo"))
        self.assertIn("upstream_url", str(ctx.exception))

    def test_source_build_requires_pinned_commit(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(pinned_commit=""))
        self.assertIn("pinned_commit", str(ctx.exception))

    def test_bad_pinned_commit(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(pinned_commit="abc123"))
        self.assertIn("pinned_commit", str(ctx.exception))

    def test_devkitpro_make_is_a_valid_source_backend(self):
        data = self._bad(build_backend="devkitpro-make")
        descriptor = engines.descriptor_from_dict(data)
        self.assertEqual(descriptor.build_backend, "devkitpro-make")
        self.assertEqual(descriptor.validate(), [])

    def test_devkitpro_make_still_requires_pinned_commit(self):
        data = self._bad(build_backend="devkitpro-make", pinned_commit="")
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(data)
        self.assertIn("pinned_commit", str(ctx.exception))

    def test_unknown_build_backend(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(build_backend="zig"))
        self.assertIn("build_backend", str(ctx.exception))

    def test_prebuilt_requires_pinned_version(self):
        data = descriptor_dict("brewser")
        data["pinned_version"] = ""
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(data)
        self.assertIn("pinned_version", str(ctx.exception))

    def test_bad_license(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(license_spdx="", license_url=""))
        self.assertIn("license", str(ctx.exception))

    def test_bad_target_kind(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(target_kind="android"))
        self.assertIn("target_kind", str(ctx.exception))

    def test_missing_capability(self):
        data = descriptor_dict()
        del data["capabilities"]["touch"]
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(data)
        self.assertIn("touch", str(ctx.exception))

    def test_unknown_capability(self):
        data = descriptor_dict()
        data["capabilities"]["network"] = {"supported": True, "note": "extra"}
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(data)
        self.assertIn("network", str(ctx.exception))

    def test_unknown_input_profile(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(default_input_profile="does-not-exist"))
        self.assertIn("default_input_profile", str(ctx.exception))

    def test_artifact_naming_suffix_must_match_target(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(artifact_naming="{id}.zip"))
        self.assertIn("artifact_naming", str(ctx.exception))

    def test_artifact_naming_unknown_placeholder(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(artifact_naming="{unknown}.nro"))
        self.assertIn("unknown", str(ctx.exception))

    def test_content_layout_mode_and_entry(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(content_layout={"mode": "romfs"}))
        self.assertIn("content_layout", str(ctx.exception))
        with self.assertRaises(engines.EngineDescriptorError):
            engines.descriptor_from_dict(self._bad(content_layout={"mode": "http"}))

    def test_blocked_requires_reason(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(status="blocked", status_reason=""))
        self.assertIn("status_reason", str(ctx.exception))
        data = self._bad(status="blocked", status_reason="upstream does not boot on firmware 23.0.0")
        descriptor = engines.descriptor_from_dict(data)
        self.assertFalse(descriptor.is_ready)

    def test_bad_artifact_sha256(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(self._bad(artifact_sha256="xyz"))
        self.assertIn("artifact_sha256", str(ctx.exception))

    def test_unknown_top_level_key_rejected(self):
        with self.assertRaises(engines.EngineDescriptorError):
            engines.descriptor_from_dict(self._bad(extra_key=True))

    def test_non_mapping_rejected(self):
        with self.assertRaises(engines.EngineDescriptorError):
            engines.descriptor_from_dict(["not", "a", "mapping"])

    def test_direct_constructor_validation(self):
        descriptor = engines.EngineDescriptor(id="Bad Id", display_name="X")
        problems = descriptor.validate()
        self.assertTrue(any("id:" in problem for problem in problems))
        self.assertTrue(any("license_spdx" in problem for problem in problems))


class DescriptorVerificationTests(unittest.TestCase):
    def test_video_alias_maps_to_graphics_with_warning(self):
        data = descriptor_dict()
        capabilities = {
            name: dict(entry)
            for name, entry in data["capabilities"].items()
            if name in ("audio", "input", "save", "touch")
        }
        capabilities["video"] = {"supported": True, "note": "legacy renderer"}
        data["capabilities"] = capabilities
        descriptor = engines.descriptor_from_dict(data)
        self.assertEqual(sorted(descriptor.capabilities), CAPABILITY_KEYS)
        self.assertTrue(descriptor.capabilities["graphics"]["supported"])
        self.assertEqual(descriptor.capabilities["graphics"]["verification"], "unknown")
        self.assertFalse(descriptor.capabilities["movie"]["supported"])
        self.assertEqual(descriptor.validate(), [])
        self.assertEqual(len(descriptor.warnings), 1)
        self.assertIn("video", descriptor.warnings[0])
        self.assertIn("graphics", descriptor.warnings[0])

    def test_missing_required_verification_is_rejected(self):
        data = descriptor_dict()
        del data["capabilities"]["graphics"]["verification"]
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(data)
        self.assertIn("capabilities.graphics.verification", str(ctx.exception))

    def test_invalid_verification_is_rejected(self):
        data = descriptor_dict()
        data["capabilities"]["graphics"]["verification"] = "device-tested"
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(data)
        message = str(ctx.exception)
        self.assertIn("graphics", message)
        self.assertIn("verification", message)
        self.assertIn("device-tested", message)

    def test_touch_verification_is_optional(self):
        data = descriptor_dict()
        del data["capabilities"]["touch"]["verification"]
        descriptor = engines.descriptor_from_dict(data)
        self.assertEqual(descriptor.validate(), [])

    def test_capability_backend_features_details_roundtrip(self):
        data = descriptor_dict()
        data["capabilities"]["movie"]["backend"] = "nvdec+nvtegra"
        data["capabilities"]["movie"]["features"] = ["h264", "nvidia-nv12-zero-copy"]
        data["capabilities"]["movie"]["details"] = {"max_width": 1920}
        descriptor = engines.descriptor_from_dict(data)
        movie = descriptor.to_dict()["capabilities"]["movie"]
        self.assertEqual(movie["backend"], "nvdec+nvtegra")
        self.assertEqual(movie["features"], ["h264", "nvidia-nv12-zero-copy"])
        self.assertEqual(movie["details"], {"max_width": 1920})

    def test_engine_verification_block_roundtrips(self):
        data = descriptor_dict()
        verification = data["verification"]
        self.assertEqual(verification["status"], "emulator_verified")
        descriptor = engines.descriptor_from_dict(data)
        self.assertEqual(descriptor.verification["status"], "emulator_verified")
        self.assertEqual(descriptor.to_dict()["verification"], verification)

    def test_engine_verification_unknown_key_rejected(self):
        data = descriptor_dict()
        data["verification"]["unknown_key"] = "x"
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.descriptor_from_dict(data)
        self.assertIn("verification", str(ctx.exception))


class FileLoadingTests(unittest.TestCase):
    def test_example_krkrsdl2_matches_builtin(self):
        descriptor = engines.load_descriptor(ROOT / "examples" / "engines" / "krkrsdl2.yaml")
        self.assertEqual(descriptor.to_dict(), descriptor_dict("krkrsdl2"))

    def test_example_brewser_core_fields_match(self):
        descriptor = engines.load_descriptor(ROOT / "examples" / "engines" / "brewser.yaml")
        builtin = descriptor_dict("brewser")
        loaded = descriptor.to_dict()
        for key in CORE_KEYS:
            self.assertEqual(loaded[key], builtin[key], key)
        self.assertEqual(sorted(loaded["capabilities"]), sorted(builtin["capabilities"]))
        for key, entry in builtin["capabilities"].items():
            self.assertEqual(loaded["capabilities"][key]["supported"], entry["supported"], key)
        self.assertEqual(descriptor.validate(), [])

    def test_example_onscripter_matches_builtin(self):
        descriptor = engines.load_descriptor(ROOT / "examples" / "engines" / "onscripter-nx.yaml")
        self.assertEqual(descriptor.to_dict(), descriptor_dict("onscripter-nx"))

    def test_missing_file_raises(self):
        with self.assertRaises(engines.EngineDescriptorError) as ctx:
            engines.load_descriptor(ROOT / "examples" / "engines" / "missing.yaml")
        self.assertIn("not found", str(ctx.exception))

    def test_bad_yaml_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text("id: [unclosed", encoding="utf-8")
            with self.assertRaises(engines.EngineDescriptorError) as ctx:
                engines.load_descriptor(path)
            self.assertIn("parse error", str(ctx.exception))

    def test_empty_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.yaml"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(engines.EngineDescriptorError):
                engines.load_descriptor(path)

    def test_check_descriptor_file_does_not_raise(self):
        ok = engines.check_descriptor_file(ROOT / "examples" / "engines" / "krkrsdl2.yaml")
        self.assertTrue(ok.ok)
        self.assertEqual(ok.errors, ())
        self.assertEqual(ok.to_json()["path"], str(ROOT / "examples" / "engines" / "krkrsdl2.yaml"))
        broken = engines.check_descriptor_file(ROOT / "examples" / "engines" / "missing.yaml")
        self.assertFalse(broken.ok)
        self.assertTrue(broken.errors)
        self.assertIn("not found", broken.errors[0])


if __name__ == "__main__":
    unittest.main()
