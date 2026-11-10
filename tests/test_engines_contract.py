"""Tests for the adapter contract: build plans, artifact checks, run specs (M4-a)."""
import dataclasses
import hashlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import engines
from galnx.engines import contract as contract_module

KRKR_STEPS = ["manifest", "source", "patches", "prepare-data", "configure", "compile", "artifact", "verify"]
BREWSER_STEPS = ["manifest", "fetch", "verify-source", "content", "install", "artifact"]
ONSCRIPTER_STEPS = ["manifest", "source", "prepare-content", "compile", "artifact", "verify"]


def load_manifest(relative):
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))


ONS_EXAMPLES = ROOT / "examples"


def load_onscripter_manifest():
    return load_manifest("examples/manifest.onscripter.yaml")


def brewser_manifest():
    data = load_manifest("examples/manifest.packaged.yaml")
    data["engine"]["adapter"] = "brewser"
    data["engine"]["adapter_version"] = "brewser@8040580e (v0.1.1.31)"
    return data


def nro_bytes(size=0x40, homebrew=True, magic=True):
    data = bytearray(size)
    if homebrew:
        data[8:16] = b"HOMEBREW"
    if magic and size > 0x14:
        data[0x10:0x14] = b"NRO0"
    return bytes(data)


def statuses(checks):
    return {check.id: check.status for check in checks}


class PlanTests(unittest.TestCase):
    def test_krkrsdl2_plan_steps(self):
        plan = engines.plan_build(load_manifest("examples/manifest.krkr.yaml"))
        self.assertEqual(plan.adapter, "krkrsdl2")
        self.assertEqual([step.id for step in plan.steps], KRKR_STEPS)
        descriptors = {step.id: step for step in plan.steps}
        self.assertIn("124bdf841f09e7ce02aa99b7b55791a0f7a900ff", descriptors["source"].command)
        self.assertIn("git -C src/engine apply", descriptors["patches"].command)
        self.assertIn("data.xp3", descriptors["prepare-data"].command)
        self.assertIn("Switch.cmake", descriptors["configure"].command)
        self.assertIn("EMBED_DATA_PATH=data.xp3", descriptors["configure"].command)
        self.assertIn("cmake --build", descriptors["compile"].command)
        self.assertEqual(descriptors["artifact"].command, "krkrsdl2-1.0.nro")

    def test_brewser_plan_steps(self):
        plan = engines.plan_build(brewser_manifest())
        self.assertEqual(plan.adapter, "brewser")
        self.assertEqual([step.id for step in plan.steps], BREWSER_STEPS)
        descriptors = {step.id: step for step in plan.steps}
        self.assertIn("raw.githubusercontent.com/natureglass/Brewser", descriptors["fetch"].command)
        self.assertIn("8ce31f5b7dfb617c18a705d0c5fc955b59f60d445b5a76e250a1dd98ccd04b13", descriptors["verify-source"].notes)
        self.assertIn("switch/brewser/apps", descriptors["content"].command)
        self.assertIn("sd", descriptors["install"].command)

    def test_onscripter_plan_steps(self):
        plan = engines.plan_build(load_onscripter_manifest(), base_dir=ONS_EXAMPLES)
        self.assertEqual(plan.adapter, "onscripter-nx")
        self.assertEqual([step.id for step in plan.steps], ONSCRIPTER_STEPS)
        by_id = {step.id: step for step in plan.steps}
        self.assertIn("a8439a86393f74c503d28df176f010ca544af56f", by_id["source"].command)
        self.assertIn("src/engine/romfs", by_id["prepare-content"].command)
        self.assertIn("ons-content", by_id["prepare-content"].command)
        self.assertIn("make clean", by_id["compile"].command)
        self.assertEqual(by_id["artifact"].command, "onscripter-nx-1.0.0.nro")

    def test_generic_devkitpro_make_backend(self):
        descriptor = dataclasses.replace(engines.KRKRSDL2, id="generic-dkp", build_backend="devkitpro-make")
        adapter = engines.adapter_for(descriptor)
        self.assertEqual(adapter.name, "descriptor")
        steps = adapter.plan_build(descriptor, load_manifest("examples/manifest.onscripter.yaml"))
        self.assertEqual([step.id for step in steps], ONSCRIPTER_STEPS)
        by_id = {step.id: step for step in steps}
        self.assertIn("mkdir -p src/engine/romfs", by_id["prepare-content"].command)
        self.assertIn("make clean", by_id["compile"].command)

    def test_generic_custom_script_backend(self):
        descriptor = dataclasses.replace(
            engines.KRKRSDL2,
            id="generic-script",
            build_backend="custom-script",
            build={"workdir": ".", "commands": ["bash build_custom.sh"]},
        )
        adapter = engines.adapter_for(descriptor)
        self.assertEqual(adapter.name, "descriptor")
        steps = adapter.plan_build(descriptor, load_manifest("examples/manifest.onscripter.yaml"))
        by_id = {step.id: step for step in steps}
        # A custom-script descriptor keeps manifest/source/content/artifact/verify
        # but must not emit a generic make/cmake compile step; the descriptor
        # build.commands drive the build through the engine-build step.
        self.assertEqual([step.id for step in steps], ["manifest", "source", "engine-build", "content", "artifact", "verify"])
        self.assertNotIn("compile", by_id)
        self.assertNotIn("configure", by_id)
        self.assertEqual(by_id["engine-build"].command, "bash build_custom.sh")
        self.assertIn("Commands come from the descriptor build section", by_id["engine-build"].notes)

    def test_rfvp_custom_script_descriptor_plan(self):
        descriptor = engines.load_descriptor(ROOT / "examples/engines/rfvp.yaml")
        self.assertEqual(descriptor.build_backend, "custom-script")
        steps = engines.adapter_for(descriptor).plan_build(descriptor, load_manifest("examples/manifest.onscripter.yaml"))
        self.assertEqual(
            [step.id for step in steps],
            ["manifest", "source", "patches", "portlibs", "engine-build", "content", "artifact", "verify"],
        )
        by_id = {step.id: step for step in steps}
        self.assertIn("9f07adef2eb5d559777f9bf59a67b756875cb24f", by_id["source"].command)
        self.assertIn("rfvp-sdl2-backend.patch", by_id["patches"].command)
        self.assertIn("switch-sdl2", by_id["portlibs"].command)
        self.assertEqual(by_id["engine-build"].command, "bash platform/switch/build_switch.sh")
        # P11 moved the game tree into romfs: the content step stages build/romfs
        # and the descriptor layout points at romfs:/game.
        self.assertEqual(descriptor.content_layout.get("destination"), "romfs:/game")
        self.assertIn("build/romfs", by_id["content"].command)
        self.assertIn("default.ttf", by_id["content"].command)

    def test_plan_to_dict_keys(self):
        plan = engines.plan_build(load_manifest("examples/manifest.krkr.yaml"))
        payload = plan.to_dict()
        self.assertEqual(sorted(payload), ["adapter", "build_steps", "engine", "expected_artifact", "input_profile", "run_spec"])
        self.assertEqual(payload["adapter"], "krkrsdl2")
        self.assertEqual(payload["engine"]["id"], "krkrsdl2")
        self.assertEqual(len(payload["build_steps"]), len(KRKR_STEPS))
        self.assertEqual(sorted(payload["build_steps"][0]), ["command", "id", "notes", "requires", "summary"])
        self.assertEqual(payload["input_profile"], {"name": "generic-vn", "source": "manifest"})

    def test_expected_artifact_names(self):
        krkr = engines.plan_build(load_manifest("examples/manifest.krkr.yaml"))
        self.assertEqual(krkr.expected_artifact, "krkrsdl2-1.0.nro")
        brewser = engines.plan_build(brewser_manifest())
        self.assertEqual(brewser.expected_artifact, "brewser.nro")
        onscripter = engines.plan_build(load_onscripter_manifest(), base_dir=ONS_EXAMPLES)
        self.assertEqual(onscripter.expected_artifact, "onscripter-nx-1.0.0.nro")

    def test_input_profile_precedence(self):
        manifest = load_manifest("examples/manifest.krkr.yaml")
        self.assertEqual(engines.plan_build(manifest).input_profile_source, "manifest")
        without_input = dict(manifest)
        without_input.pop("input")
        plan = engines.plan_build(without_input)
        self.assertEqual(plan.input_profile, "krkrsdl2")
        self.assertEqual(plan.input_profile_source, "engine-default")
        brewser = brewser_manifest()
        brewser.pop("input")
        self.assertEqual(engines.plan_build(brewser).input_profile, "kb_mouse")

    def test_adapters_are_concrete(self):
        self.assertIsInstance(engines.adapter_for(engines.KRKRSDL2), contract_module.Krkrsdl2Adapter)
        self.assertIsInstance(engines.adapter_for(engines.BREWSER), contract_module.BrewserAdapter)
        self.assertIsInstance(engines.adapter_for(engines.ONSCRIPTER_NX), contract_module.OnscripterNxAdapter)
        self.assertEqual(engines.adapter_for(engines.KRKRSDL2).name, "krkrsdl2")
        self.assertEqual(engines.adapter_for(engines.ONSCRIPTER_NX).name, "onscripter-nx")
        self.assertEqual(engines.EngineAdapter().name, "descriptor")

    def test_plan_errors(self):
        with self.assertRaises(engines.EngineRegistryError) as ctx:
            engines.plan_build({})
        self.assertIn("manifest.engine", str(ctx.exception))
        with self.assertRaises(engines.EngineRegistryError) as ctx:
            engines.plan_build({"engine": {"adapter": "nope"}})
        self.assertIn("unknown engine adapter", str(ctx.exception))
        with self.assertRaises(engines.EngineRegistryError) as ctx:
            engines.plan_build({"engine": {}})
        self.assertIn("engine.adapter", str(ctx.exception))


class RunSpecTests(unittest.TestCase):
    def test_krkrsdl2_run_spec(self):
        spec = engines.run_spec(load_manifest("examples/manifest.krkr.yaml"))
        self.assertEqual(spec["engine"], "krkrsdl2")
        self.assertEqual(spec["harness"], "citron")
        self.assertEqual(spec["target_kind"], "nro")
        self.assertEqual(spec["load"], "nro")
        self.assertEqual(spec["artifact"], "krkrsdl2-1.0.nro")
        self.assertEqual(spec["arguments"], ["-g", "<artifact>"])
        self.assertIsNone(spec["sdmc"])
        self.assertEqual(len(spec["notes"]), 3)

    def test_brewser_run_spec_has_sdmc(self):
        spec = engines.run_spec(brewser_manifest())
        self.assertEqual(spec["engine"], "brewser")
        self.assertEqual(spec["target_kind"], "web")
        self.assertIn("switch/brewser/apps", spec["sdmc"])
        self.assertEqual(len(spec["notes"]), 4)

    def test_onscripter_run_spec(self):
        spec = engines.run_spec(load_onscripter_manifest(), base_dir=ONS_EXAMPLES)
        self.assertEqual(spec["engine"], "onscripter-nx")
        self.assertEqual(spec["target_kind"], "nro")
        self.assertEqual(spec["load"], "nro")
        self.assertEqual(spec["artifact"], "onscripter-nx-1.0.0.nro")
        self.assertIsNone(spec["sdmc"])
        self.assertEqual(len(spec["notes"]), 4)

    def test_run_spec_keys(self):
        spec = engines.run_spec(load_manifest("examples/manifest.krkr.yaml"))
        self.assertEqual(
            sorted(spec),
            ["arguments", "artifact", "engine", "harness", "load", "notes", "sdmc", "target_kind"],
        )


class VerifyArtifactTests(unittest.TestCase):
    def test_valid_nro(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.nro"
            data = nro_bytes()
            path.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            checks = engines.verify_artifact(path, descriptor=engines.KRKRSDL2, expected_sha256=sha)
            state = statuses(checks)
            self.assertNotIn("artifact.exists", state)
            self.assertEqual(state["artifact.file"], "ok")
            self.assertEqual(state["artifact.extension"], "ok")
            self.assertEqual(state["artifact.magic"], "ok")
            self.assertEqual(state["artifact.header"], "ok")
            self.assertEqual(state["artifact.sha256"], "ok")
            self.assertEqual(state["artifact.result"], "ok")
            self.assertEqual(state["artifact.engine"], "warn")
            self.assertFalse(engines.has_failures(checks))

    def test_onscripter_size_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            small = Path(tmp) / "small.nro"
            data = nro_bytes()
            small.write_bytes(data)
            checks = engines.verify_artifact(
                small, descriptor=engines.ONSCRIPTER_NX, expected_sha256=hashlib.sha256(data).hexdigest(),
            )
            self.assertEqual(statuses(checks)["artifact.engine"], "warn")
            big = Path(tmp) / "big.nro"
            data = nro_bytes(size=0x200000)
            big.write_bytes(data)
            checks = engines.verify_artifact(
                big, descriptor=engines.ONSCRIPTER_NX, expected_sha256=hashlib.sha256(data).hexdigest(),
            )
            state = statuses(checks)
            self.assertEqual(state["artifact.engine"], "ok")
            self.assertFalse(engines.has_failures(checks))

    def test_sha256_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.nro"
            path.write_bytes(nro_bytes())
            checks = engines.verify_artifact(path, descriptor=engines.KRKRSDL2, expected_sha256="0" * 64)
            state = statuses(checks)
            self.assertEqual(state["artifact.sha256"], "fail")
            self.assertEqual(state["artifact.result"], "fail")
            self.assertTrue(engines.has_failures(checks))

    def test_missing_expected_sha_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.nro"
            path.write_bytes(nro_bytes())
            checks = engines.verify_artifact(path, descriptor=engines.KRKRSDL2)
            self.assertEqual(statuses(checks)["artifact.sha256"], "warn")

    def test_wrong_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.zip"
            path.write_bytes(nro_bytes())
            checks = engines.verify_artifact(path, engine_id="krkrsdl2", expected_sha256=hashlib.sha256(nro_bytes()).hexdigest())
            self.assertEqual(statuses(checks)["artifact.extension"], "fail")

    def test_missing_and_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.nro"
            checks = engines.verify_artifact(missing, descriptor=engines.KRKRSDL2, expected_sha256="0" * 64)
            self.assertEqual([check.id for check in checks], ["artifact.exists"])
            self.assertEqual(checks[0].status, "fail")
            empty = Path(tmp) / "empty.nro"
            empty.write_bytes(b"")
            state = statuses(engines.verify_artifact(empty, descriptor=engines.KRKRSDL2, expected_sha256="0" * 64))
            self.assertEqual(state["artifact.size"], "fail")

    def test_bad_nro_magic_and_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.nro"
            data = nro_bytes(homebrew=False, magic=False)
            path.write_bytes(data)
            checks = engines.verify_artifact(path, descriptor=engines.KRKRSDL2, expected_sha256=hashlib.sha256(data).hexdigest())
            state = statuses(checks)
            self.assertEqual(state["artifact.magic"], "fail")
            self.assertEqual(state["artifact.header"], "warn")

    def test_web_engine_accepts_nro(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brewser.nro"
            data = nro_bytes()
            path.write_bytes(data)
            checks = engines.verify_artifact(path, descriptor=engines.BREWSER, expected_sha256=hashlib.sha256(data).hexdigest())
            state = statuses(checks)
            self.assertEqual(state["artifact.magic"], "ok")
            self.assertNotIn("artifact.engine", state)
            self.assertFalse(engines.has_failures(checks))

    def test_verify_artifact_needs_a_descriptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.nro"
            path.write_bytes(nro_bytes())
            with self.assertRaises(engines.EngineRegistryError) as ctx:
                engines.verify_artifact(path)
            self.assertIn("needs a descriptor or an engine_id", str(ctx.exception))

    def test_unknown_engine_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.nro"
            path.write_bytes(nro_bytes())
            with self.assertRaises(engines.EngineRegistryError):
                engines.verify_artifact(path, engine_id="nope")


class HelperTests(unittest.TestCase):
    def test_check_serialisation(self):
        check = contract_module.Check(id="artifact.magic", status="warn", detail="d")
        self.assertTrue(check.is_fail is False)
        self.assertEqual(sorted(check.to_dict()), ["detail", "hint", "id", "name", "status"])
        self.assertEqual(check.to_json(), check.to_dict())
        with self.assertRaises(ValueError):
            contract_module.Check(id="x", status="bad")

    def test_checks_helpers(self):
        checks = [contract_module.Check(id="a", status="ok"), contract_module.Check(id="b", status="fail")]
        self.assertTrue(engines.has_failures(checks))
        self.assertEqual([item["id"] for item in engines.checks_to_dict(checks)], ["a", "b"])
        self.assertEqual(contract_module.CHECK_STATUSES, ("ok", "warn", "fail", "skip"))

    def test_version_sanitising(self):
        self.assertEqual(engines.artifact_version({"game": {"version": "1.0"}}), "1.0")
        self.assertEqual(engines.artifact_version({}), "")
        self.assertEqual(engines.sanitize_artifact_version("1.0 beta@x"), "1.0-beta-x")
        self.assertEqual(engines.sanitize_artifact_version("--a_b.c--"), "a_b.c")

    def test_sha256_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.bin"
            path.write_bytes(b"galnx")
            self.assertEqual(engines.sha256_file(path), hashlib.sha256(b"galnx").hexdigest())


if __name__ == "__main__":
    unittest.main()
