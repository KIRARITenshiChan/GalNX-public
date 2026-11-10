"""Unit tests for the galnx engines CLI subcommands."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import cli  # noqa: E402
from galnx.engines import KRKRSDL2  # noqa: E402

MANIFEST = ROOT / "examples" / "manifest.krkr.yaml"
PACKAGED = ROOT / "examples" / "manifest.packaged.yaml"
ONSCRIPTER = ROOT / "examples" / "manifest.onscripter.yaml"


def run_cli(argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = cli.main(argv)
    return exit_code, buffer.getvalue()


def write_descriptor(directory, engine_id):
    data = KRKRSDL2.to_dict()
    data["id"] = engine_id
    path = Path(directory) / ("%s.yaml" % engine_id)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def write_manifest(directory, adapter, adapter_version, base=PACKAGED):
    data = yaml.safe_load(base.read_text(encoding="utf-8"))
    data["engine"]["adapter"] = adapter
    data["engine"]["adapter_version"] = adapter_version
    path = Path(directory) / ("manifest-%s.yaml" % adapter)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


class EngineListTests(unittest.TestCase):
    def test_list_text(self):
        exit_code, output = run_cli(["engines", "list"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Registered engine adapters (3):", output)
        self.assertIn("brewser", output)
        self.assertIn("krkrsdl2", output)
        self.assertIn("onscripter-nx", output)
        self.assertIn("MPL-2.0", output)
        self.assertIn("MIT", output)
        self.assertIn("GPL-2.0-or-later", output)
        self.assertIn("devkitpro-make", output)
        self.assertIn("engines info", output)

    def test_list_json(self):
        exit_code, output = run_cli(["engines", "list", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["version"], "0.1.0")
        self.assertEqual(payload["count"], 3)
        self.assertEqual([item["id"] for item in payload["engines"]], ["brewser", "krkrsdl2", "onscripter-nx"])
        self.assertEqual(payload["engines"][1]["license_spdx"], "MIT")
        self.assertEqual(payload["engines"][2]["license_spdx"], "GPL-2.0-or-later")
        self.assertEqual(payload["engines"][2]["build_backend"], "devkitpro-make")

    def test_list_engines_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_descriptor(tmp, "renpy")
            exit_code, output = run_cli(["engines", "list", "--engines-dir", tmp])
        self.assertEqual(exit_code, 0)
        self.assertIn("Registered engine adapters (4):", output)
        self.assertIn("renpy", output)

    def test_list_missing_engines_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "nope")
            exit_code, output = run_cli(["engines", "list", "--engines-dir", missing])
        self.assertEqual(exit_code, 2)
        self.assertIn("FAIL", output)


class EngineInfoTests(unittest.TestCase):
    def test_info_text(self):
        exit_code, output = run_cli(["engines", "info", "krkrsdl2"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Engine adapter: krkrsdl2 (KiriKiri SDL2)", output)
        self.assertIn("124bdf841f09e7ce02aa99b7b55791a0f7a900ff", output)
        self.assertIn("krkrsdl2-krkrsdl2@124bdf84.nro", output)
        self.assertIn("Krkrsdl2Adapter", output)
        self.assertIn("mode=romfs", output)

    def test_info_json(self):
        exit_code, output = run_cli(["engines", "info", "krkrsdl2", "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["version"], "0.1.0")
        self.assertEqual(payload["engine"]["id"], "krkrsdl2")
        self.assertEqual(payload["adapter"]["class"], "Krkrsdl2Adapter")
        self.assertEqual(payload["adapter"]["methods"], ["plan_build", "verify_artifact", "run_spec"])
        self.assertEqual(payload["artifact_name"], "krkrsdl2-krkrsdl2@124bdf84.nro")
        self.assertEqual(payload["input_profile"], "krkrsdl2")
        self.assertEqual(payload["problems"], [])

    def test_info_brewser(self):
        exit_code, output = run_cli(["engines", "info", "brewser"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Brewser (nx.js web runtime)", output)
        self.assertIn("mpv", output.lower() + "mpv")
        self.assertIn("BrewserAdapter", output)

    def test_info_onscripter(self):
        exit_code, output = run_cli(["engines", "info", "onscripter-nx"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Engine adapter: onscripter-nx (ONScripter-NX)", output)
        self.assertIn("a8439a86393f74c503d28df176f010ca544af56f", output)
        self.assertIn("onscripter-nx-ONScripter-NX@a8439a86.nro", output)
        self.assertIn("OnscripterNxAdapter", output)
        self.assertIn("GPL-2.0-or-later", output)
        self.assertIn("devkitpro-make", output)
        self.assertIn("mode=romfs", output)

    def test_info_unknown_adapter(self):
        exit_code, output = run_cli(["engines", "info", "nope"])
        self.assertEqual(exit_code, 2)
        self.assertIn("unknown engine adapter", output)

    def test_info_engines_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_descriptor(tmp, "renpy")
            exit_code, output = run_cli(["engines", "info", "renpy", "--engines-dir", tmp])
        self.assertEqual(exit_code, 0)
        self.assertIn("Engine adapter: renpy", output)


class EnginePlanTests(unittest.TestCase):
    def test_plan_krkrsdl2(self):
        exit_code, output = run_cli(["engines", "plan", "--manifest", str(MANIFEST)])
        self.assertEqual(exit_code, 0)
        self.assertIn("Build plan (krkrsdl2, nro):", output)
        self.assertIn("input:     generic-vn (source: manifest)", output)
        self.assertIn("artifact:  krkrsdl2-1.0.nro", output)
        for step in ["manifest", "source", "patches", "prepare-data", "configure", "compile", "artifact", "verify"]:
            self.assertIn("[%s]" % step, output)
        self.assertIn("10 checks: 0 fail, 1 warn", output)

    def test_plan_json(self):
        exit_code, output = run_cli(["engines", "plan", "--manifest", str(MANIFEST), "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["version"], "0.1.0")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["adapter"], "krkrsdl2")
        self.assertEqual(payload["input_profile"], {"name": "generic-vn", "source": "manifest"})
        self.assertEqual(payload["expected_artifact"], "krkrsdl2-1.0.nro")
        self.assertEqual(len(payload["build_steps"]), 8)
        self.assertEqual(payload["build_steps"][0]["id"], "manifest")
        self.assertEqual(payload["run_spec"]["load"], "nro")

    def test_plan_brewser(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manifest(tmp, "brewser", "brewser@8040580e (v0.1.1.31)")
            exit_code, output = run_cli(["engines", "plan", "--manifest", str(path)])
        self.assertEqual(exit_code, 0)
        self.assertIn("Build plan (brewser, web):", output)
        self.assertIn("brewser.nro", output)
        self.assertIn("switch/brewser/apps", output)

    def test_plan_onscripter(self):
        exit_code, output = run_cli(["engines", "plan", "--manifest", str(ONSCRIPTER)])
        self.assertEqual(exit_code, 0)
        self.assertIn("Build plan (onscripter-nx, nro):", output)
        self.assertIn("artifact:  onscripter-nx-1.0.0.nro", output)
        self.assertIn("10 checks: 0 fail, 1 warn", output)
        for step in ["manifest", "source", "prepare-content", "compile", "artifact", "verify"]:
            self.assertIn("[%s]" % step, output)
        self.assertIn("src/engine/romfs", output)

    def test_plan_onscripter_json(self):
        exit_code, output = run_cli(["engines", "plan", "--manifest", str(ONSCRIPTER), "--json"])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["adapter"], "onscripter-nx")
        self.assertEqual(payload["expected_artifact"], "onscripter-nx-1.0.0.nro")
        self.assertEqual(len(payload["build_steps"]), 6)
        self.assertEqual([step["id"] for step in payload["build_steps"]],
                         ["manifest", "source", "prepare-content", "compile", "artifact", "verify"])
        self.assertEqual(payload["run_spec"]["engine"], "onscripter-nx")

    def test_plan_engines_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            engines = Path(tmp) / "engines"
            engines.mkdir()
            write_descriptor(engines, "renpy")
            path = write_manifest(tmp, "renpy", "renpy@124bdf84 (test)")
            exit_code, output = run_cli(
                ["engines", "plan", "--manifest", str(path), "--engines-dir", str(engines)]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("Build plan (renpy, nro):", output)
        self.assertIn("renpy-1.0.0.nro", output)

    def test_plan_bad_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text("schema_version: 1", encoding="utf-8")
            exit_code, output = run_cli(["engines", "plan", "--manifest", str(path)])
        self.assertEqual(exit_code, 2)
        self.assertIn("manifest", output)
        self.assertIn("fail", output.lower())

    def test_plan_unknown_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manifest(tmp, "renpy", "renpy@124bdf84 (test)")
            exit_code, output = run_cli(["engines", "plan", "--manifest", str(path)])
        self.assertEqual(exit_code, 2)
        self.assertIn("unknown engine adapter", output)

    def test_plan_missing_manifest(self):
        exit_code, output = run_cli(["engines", "plan", "--manifest", "examples/nope.yaml"])
        self.assertEqual(exit_code, 2)
        self.assertIn("FAIL", output)


if __name__ == "__main__":
    unittest.main()
