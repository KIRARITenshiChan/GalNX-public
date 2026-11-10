"""Unit tests for galnx.payload.plan (payload config, plan building, materialize)."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.payload import content as content_mod  # noqa: E402
from galnx.payload import keymap as keymap_mod  # noqa: E402
from galnx.payload import FAT32_MAX_FILE, GOLDEN_KEYMAP_SHA256  # noqa: E402
from galnx.payload.content import PayloadError  # noqa: E402
from galnx.payload.plan import (  # noqa: E402
    DEFAULT_KEYMAP_FILE,
    DEFAULT_PAYLOAD_DIR,
    LINK_MODES,
    PayloadConfig,
    build_plan,
    load_payload_config,
    materialize,
    plan_to_json,
    validate_manifest_payload,
)

GOLDEN_GAME_FILES_SHA256 = "0e6757d9901d4a4abb95a220f9d8e1714b0b858c421ec328e6802a10d4e3fd61"
PILOT_GAME = Path("E:/Othergames/Galgame/晴霁之后定是菜花盛开的好天气")
PILOT_UI = Path("E:/galnx-build/pilot-01/k2nx-ws/build/romfs")
PILOT_MANIFEST = ROOT / "examples/payload/manifest.pilot01.yaml"


def write_tree(root, files):
    for rel, data in files.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def minimal_payload(**overrides):
    data = {
        "version": "test-r1",
        "target": "/kirikiri/synth",
        "startup": "/kirikiri/synth/data.xp3",
        "marker": "sdmc:/switch/kirikiroid2/.galnx_extracted",
    }
    data.update(overrides)
    return data


class WorkdirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="galnx-payload-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.source = self.tmp / "source"
        self.source.mkdir()
        self.ui = self.tmp / "ui"
        self.ui.mkdir()

    def standard_source(self):
        write_tree(
            self.source,
            {
                "data.xp3": b"XP3",
                "data_chs.xp3": b"CHS",
                "haruno.cf": b"CF",
                "plugin/a.tpm": b"TPM",
                "plugin/b.tpm": b"TPM2",
                "plugin/ignored.sig": b"SIG",
            },
        )
        write_tree(self.ui, {"img/a.png": b"PNG!!", "ui/b.png": b"UI2"})

    def standard_config(self, **overrides):
        data = minimal_payload(
            source_dir=str(self.source),
            ui_dir=str(self.ui),
            include=["*.xp3", "*.cf", "plugin/*.tpm"],
            exclude=["*_chs.xp3", "*.sig"],
            keymap={"profile": "generic-vn"},
        )
        data.update(overrides)
        return load_payload_config(data, base_dir=self.tmp)


class PayloadConfigTests(WorkdirTestCase):
    def test_minimal_defaults(self):
        config = load_payload_config(minimal_payload())
        self.assertEqual(config.version, "test-r1")
        self.assertEqual(config.target, "/kirikiri/synth")
        self.assertEqual(config.startup, "/kirikiri/synth/data.xp3")
        self.assertEqual(config.include, content_mod.DEFAULT_INCLUDE)
        self.assertEqual(config.exclude, content_mod.DEFAULT_EXCLUDE)
        self.assertEqual(config.payload_dir, DEFAULT_PAYLOAD_DIR)
        self.assertEqual(config.manifest_name, "game_files.txt")
        self.assertEqual(config.keymap_file, DEFAULT_KEYMAP_FILE)
        self.assertFalse(config.keymap_enabled)
        self.assertIsNone(config.source_dir)

    def test_sdmc_marker_is_accepted_and_json_round_trips(self):
        config = load_payload_config(minimal_payload())
        payload = config.to_json()
        self.assertEqual(payload["marker"], "sdmc:/switch/kirikiroid2/.galnx_extracted")
        json.dumps(payload)  # must be JSON serialisable

    def test_relative_paths_resolve_against_base_dir(self):
        config = load_payload_config(
            minimal_payload(source_dir="game dir", ui_dir="ui dir"), base_dir=self.tmp
        )
        self.assertEqual(config.source_dir, self.tmp / "game dir")
        self.assertEqual(config.ui_dir, self.tmp / "ui dir")

    def test_keymap_as_string_profile(self):
        config = load_payload_config(minimal_payload(keymap="generic-vn"))
        self.assertEqual(config.keymap_profile, "generic-vn")
        self.assertTrue(config.keymap_enabled)

    def test_keymap_bindings_are_normalised(self):
        config = load_payload_config(
            minimal_payload(keymap={"bindings": {"A": "VK_RETURN", "B": 27}})
        )
        self.assertEqual(dict(config.keymap_bindings), {448: 13, 449: 27})

    def test_keymap_without_profile_or_bindings_disables_generation(self):
        config = load_payload_config(minimal_payload(keymap={"file": "Custom.xml"}))
        self.assertFalse(config.keymap_enabled)
        self.assertEqual(config.keymap_file, "Custom.xml")

    def test_rejects_unknown_fields(self):
        for bad in ({"bogus": 1}, {"keymap": {"bogus": 1}}):
            data = minimal_payload()
            data.update(bad)
            with self.assertRaises(PayloadError) as ctx:
                load_payload_config(data)
            self.assertIn("unknown", str(ctx.exception))

    def test_rejects_missing_required_fields(self):
        for key in ("version", "target", "startup", "marker"):
            data = minimal_payload()
            data.pop(key)
            with self.assertRaises(PayloadError) as ctx:
                load_payload_config(data)
            self.assertIn(key, str(ctx.exception))

    def test_rejects_bad_paths(self):
        cases = [
            {"target": "kirikiri/synth"},
            {"target": "/"},
            {"startup": "/elsewhere/data.xp3"},
            {"marker": "switch/x"},
            {"marker": "sdmc:"},
            {"marker": "/"},
        ]
        for overrides in cases:
            with self.assertRaises(PayloadError):
                load_payload_config(minimal_payload(**overrides))

    def test_rejects_unknown_profile_and_bad_keymap_file(self):
        with self.assertRaises(PayloadError):
            load_payload_config(minimal_payload(keymap="no-such-profile"))
        with self.assertRaises(PayloadError):
            load_payload_config(minimal_payload(keymap={"file": "sub/Key.xml"}))
        with self.assertRaises(PayloadError):
            load_payload_config(minimal_payload(keymap={"file": ""}))

    def test_rejects_missing_template(self):
        with self.assertRaises(PayloadError):
            load_payload_config(
                minimal_payload(keymap={"template": str(self.tmp / "missing.xml")})
            )

    def test_rejects_relative_path_without_base_dir(self):
        with self.assertRaises(PayloadError):
            load_payload_config(minimal_payload(source_dir="relative"))


class ValidateManifestPayloadTests(WorkdirTestCase):
    def test_none_is_valid(self):
        self.assertEqual(validate_manifest_payload(None), [])

    def test_non_mapping_is_reported(self):
        errors = validate_manifest_payload("nope")
        self.assertEqual(len(errors), 1)
        self.assertIn("must be an object", errors[0])

    def test_schema_errors_are_prefixed(self):
        errors = validate_manifest_payload({"version": "x"})
        self.assertTrue(errors)
        self.assertTrue(all(item.startswith("payload") for item in errors))

    def test_bad_target_pattern_is_reported(self):
        errors = validate_manifest_payload(minimal_payload(target="relative"))
        self.assertTrue(any("payload" in item for item in errors))

    def test_valid_payload(self):
        self.assertEqual(validate_manifest_payload(minimal_payload()), [])


class BuildPlanTests(WorkdirTestCase):
    def test_happy_path_with_keymap(self):
        self.standard_source()
        config = self.standard_config()
        plan = build_plan(config)

        self.assertTrue(plan.is_ok(), plan.errors())
        self.assertEqual(
            [check.id for check in plan.checks],
            [
                "payload-link-mode",
                "payload-source",
                "payload-files",
                "payload-keymap",
                "payload-keymap-golden",
                "payload-keymap-profile",
                "payload-manifest",
                "payload-startup",
                "payload-name-collision",
                "payload-path-length",
                "payload-fat32-limit",
                "payload-symlink",
                "payload-sparse",
                "payload-ui",
                "payload-total",
            ],
        )
        self.assertEqual(
            [item.rel for item in plan.files],
            ["data.xp3", "haruno.cf", "plugin/a.tpm", "plugin/b.tpm"],
        )
        self.assertEqual(
            [item.rel for item in plan.generated], [DEFAULT_KEYMAP_FILE]
        )
        self.assertEqual(content_mod.total_bytes(plan.files), 12)
        self.assertEqual(plan.payload_bytes, 12 + 1293)
        self.assertEqual(plan.manifest_bytes, len(plan.manifest_text.encode("utf-8")))
        self.assertEqual(plan.romfs_total_bytes, plan.payload_bytes + plan.ui_bytes + plan.manifest_bytes)
        self.assertEqual(plan.ui_bytes, 8)
        self.assertEqual(
            [item.rel for item in plan.ui_files], ["img/a.png", "ui/b.png"]
        )
        self.assertEqual(
            [check.status for check in plan.warnings()], ["warn"]
        )  # generic-vn: show_history/auto_mode/skip_hold unbound
        self.assertEqual(plan.warnings()[0].id, "payload-keymap-profile")

        # game_files.txt: 5 header lines + (4 payload files + keymap) file= lines
        self.assertEqual(plan.manifest_text.count("\n"), 10)
        self.assertEqual(
            plan.manifest_text.splitlines()[5:],
            [
                "file=data.xp3",
                "file=haruno.cf",
                "file=plugin/a.tpm",
                "file=plugin/b.tpm",
                "file=" + DEFAULT_KEYMAP_FILE,
            ],
        )
        json_view = plan_to_json(plan)
        self.assertTrue(json_view["ok"])
        self.assertEqual(json_view["total_file_count"], 5)
        self.assertEqual(json_view["categories"], {"config": 1, "other": 1, "plugin": 2, "xp3": 1})
        self.assertEqual(json_view["keymap"]["sha256"], GOLDEN_KEYMAP_SHA256)
        self.assertEqual(
            json_view["manifest"]["sha256"],
            content_mod.sha256_bytes(plan.manifest_text.encode("utf-8")),
        )

    def test_without_keymap_has_no_generated_files(self):
        self.standard_source()
        config = self.standard_config(keymap=None)
        plan = build_plan(config)
        self.assertEqual(plan.generated, [])
        self.assertIsNone(plan.keymap_text)
        self.assertNotIn("payload-keymap", [check.id for check in plan.checks])
        self.assertEqual(plan.manifest_text.count("\n"), 9)

    def test_missing_source_is_a_failed_check(self):
        config = self.standard_config(source_dir=str(self.tmp / "nope"))
        plan = build_plan(config)
        self.assertFalse(plan.is_ok())
        self.assertIn(
            ("payload-source", "fail"),
            [(check.id, check.status) for check in plan.checks],
        )

    def test_no_source_configured(self):
        config = self.standard_config(source_dir=None)
        plan = build_plan(config)
        self.assertIn("not configured", plan.errors()[0].detail)

    def test_missing_startup_file_fails(self):
        write_tree(self.source, {"other.xp3": b"O"})
        config = self.standard_config()
        plan = build_plan(config)
        check = [item for item in plan.checks if item.id == "payload-startup"][0]
        self.assertEqual(check.status, "fail")
        self.assertIn("missing from the selected files", check.detail)
        self.assertFalse(plan.is_ok())

    def test_override_source_and_ui_dir(self):
        self.standard_source()
        other = self.tmp / "other"
        other.mkdir()
        write_tree(other, {"data.xp3": b"X"})
        config = self.standard_config(keymap=None, ui_dir=None)
        plan = build_plan(config, source_dir=other)
        self.assertEqual([item.rel for item in plan.files], ["data.xp3"])
        self.assertEqual(plan.ui_files, [])
        ui_check = [item for item in plan.checks if item.id == "payload-ui"][0]
        self.assertEqual(ui_check.status, "skip")

    def test_long_paths_fail_the_length_check(self):
        write_tree(self.source, {"data.xp3": b"X"})
        target = "/" + "d" * 255
        config = load_payload_config(
            minimal_payload(
                target=target,
                startup=target + "/data.xp3",
                source_dir=str(self.source),
                keymap=None,
            )
        )
        plan = build_plan(config)
        check = [item for item in plan.checks if item.id == "payload-path-length"][0]
        self.assertEqual(check.status, "fail")
        self.assertGreater(plan.to_json()["max_device_path_length"], content_mod.WINDOWS_PATH_MAX)

    def test_ui_manifest_name_collision_fails(self):
        self.standard_source()
        write_tree(self.ui, {"game_files.txt": b"oops"})
        config = self.standard_config(keymap=None)
        plan = build_plan(config)
        ids = [check.id for check in plan.checks]
        self.assertIn("payload-ui-collision", ids)
        self.assertFalse(plan.is_ok())

    def test_case_collision_detection_is_reported_from_scan(self):
        # Windows cannot hold both names in one directory; assert the folded rule on
        # the plan helper path via a synthetic manifest name collision.
        self.standard_source()
        config = self.standard_config(keymap=None, manifest_name="DATA.XP3")
        plan = build_plan(config)
        check = [item for item in plan.checks if item.id == "payload-name-collision"][0]
        self.assertEqual(check.status, "fail")
        self.assertIn("generated DATA.XP3", check.detail)

    def test_unknown_link_mode_is_rejected(self):
        with self.assertRaises(PayloadError):
            build_plan(self.standard_config(), link_mode="teleport")

    def test_fat32_limit_constant(self):
        self.assertEqual(FAT32_MAX_FILE, 4 * 1024 ** 3 - 1)
        self.assertEqual(LINK_MODES, ("copy", "hardlink", "symlink"))


class MaterializeTests(WorkdirTestCase):
    def test_copy_materializes_the_romfs_tree(self):
        self.standard_source()
        config = self.standard_config()
        plan = build_plan(config)
        out = self.tmp / "romfs"

        result = materialize(plan, out)
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "copy")
        self.assertEqual(result["payload_files"], 4)
        self.assertEqual(result["generated_files"], 1)
        self.assertEqual(result["ui_files"], 2)
        self.assertTrue((out / "game/data.xp3").is_file())
        self.assertTrue((out / "game/plugin/a.tpm").is_file())
        self.assertEqual(
            (out / "game" / DEFAULT_KEYMAP_FILE).read_text(encoding="utf-8"),
            keymap_mod.render_default(),
        )
        self.assertTrue((out / "game_files.txt").is_file())
        self.assertEqual(
            (out / "game_files.txt").read_bytes(), plan.manifest_text.encode("utf-8")
        )
        self.assertTrue((out / "img/a.png").is_file())
        expected_bytes = (
            plan.payload_bytes + plan.ui_bytes + plan.manifest_bytes
        )
        self.assertEqual(result["bytes"], expected_bytes)
        self.assertEqual(result["manifest"]["sha256"], content_mod.sha256_bytes(plan.manifest_text.encode("utf-8")))

    def test_refuses_to_overwrite_without_force(self):
        self.standard_source()
        plan = build_plan(self.standard_config())
        out = self.tmp / "romfs"
        materialize(plan, out)
        with self.assertRaises(PayloadError) as ctx:
            materialize(plan, out)
        self.assertIn("refusing to overwrite", str(ctx.exception))
        result = materialize(plan, out, force=True)
        self.assertTrue(result["ok"])

    def test_refuses_failed_plan(self):
        write_tree(self.source, {"other.xp3": b"O"})
        plan = build_plan(self.standard_config())
        with self.assertRaises(PayloadError) as ctx:
            materialize(plan, self.tmp / "romfs")
        self.assertIn("failed checks", str(ctx.exception))

    def test_hardlink_mode_falls_back_or_links(self):
        self.standard_source()
        plan = build_plan(self.standard_config())
        result = materialize(plan, self.tmp / "romfs", mode="hardlink")
        self.assertEqual(result["mode"], "hardlink")
        self.assertEqual(result["hardlinked"] + result["fallback_copy"], 6)

    def test_unknown_mode_is_rejected(self):
        self.standard_source()
        plan = build_plan(self.standard_config())
        with self.assertRaises(PayloadError):
            materialize(plan, self.tmp / "romfs", mode="teleport")

    def test_output_file_path_is_rejected(self):
        self.standard_source()
        plan = build_plan(self.standard_config())
        blocker = self.tmp / "blocker"
        blocker.write_bytes(b"x")
        with self.assertRaises(PayloadError):
            materialize(plan, blocker)


class PilotIntegrationTests(unittest.TestCase):
    """Against the read-only pilot-01 dataset; skipped when the dataset is absent."""

    @classmethod
    def setUpClass(cls):
        if not (PILOT_GAME.is_dir() and PILOT_UI.is_dir() and PILOT_MANIFEST.is_file()):
            raise unittest.SkipTest("pilot-01 dataset not available")
        import yaml

        manifest = yaml.safe_load(PILOT_MANIFEST.read_text(encoding="utf-8"))
        cls.payload = manifest["payload"]
        cls.base_dir = PILOT_MANIFEST.parent
        cls.config = load_payload_config(cls.payload, base_dir=cls.base_dir)
        cls.plan = build_plan(cls.config)

    def test_manifest_section_validates(self):
        self.assertEqual(
            validate_manifest_payload(self.payload, base_dir=self.base_dir), []
        )

    def test_selection_matches_pilot_payload(self):
        self.assertEqual(
            content_mod.total_bytes(self.plan.files), 2870635309 - 1293
        )  # 23 payload files minus generated keymap
        self.assertEqual(self.plan.payload_bytes, 2870635309)
        self.assertEqual(plan_to_json(self.plan)["total_file_count"], 23)
        self.assertEqual(self.plan.config.manifest_name, "game_files.txt")
        self.assertEqual(len(self.plan.ui_files), 85)
        self.assertEqual(self.plan.ui_bytes, 7551013)
        self.assertEqual(self.plan.romfs_total_bytes, 2878186922)
        self.assertTrue(self.plan.is_ok())

    def test_golden_game_files_txt(self):
        raw = self.plan.manifest_text.encode("utf-8")
        self.assertEqual(len(raw), 600)
        self.assertEqual(raw.decode("utf-8").count("\n"), 28)
        self.assertEqual(content_mod.sha256_bytes(raw), GOLDEN_GAME_FILES_SHA256)
        expected = (ROOT / "examples/payload/expected/game_files.pilot01.txt").read_bytes()
        self.assertEqual(raw, expected)

    def test_golden_keymap(self):
        self.assertEqual(
            content_mod.sha256_bytes(self.plan.keymap_text.encode("utf-8")),
            GOLDEN_KEYMAP_SHA256,
        )
        self.assertEqual(len(self.plan.keymap_text.encode("utf-8")), 1293)
        checks = keymap_mod.verify_golden()
        self.assertEqual(
            [check[0] for check in checks],
            ["keymap-template-size", "keymap-template-sha256", "keymap-default-render"],
        )
        for check_id, ok, detail in checks:
            self.assertTrue(ok, "%s: %s" % (check_id, detail))
        self.assertIn("golden 1293 B", checks[0][2])
        self.assertIn(GOLDEN_KEYMAP_SHA256[:16], checks[1][2])

    def test_manifest_check_reports_600_bytes(self):
        check = [item for item in self.plan.checks if item.id == "payload-manifest"][0]
        self.assertEqual(check.status, "ok")
        self.assertIn("28 lines, 600 B", check.detail)


if __name__ == "__main__":
    unittest.main()
