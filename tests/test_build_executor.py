"""Tests for galnx.build.executor (M6-b command execution and caching helpers)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import build  # noqa: E402


def build_data(**build_section):
    return {"schema_version": 1, "build": dict(build_section)}


def write_script(directory: Path, name: str, source: str) -> Path:
    path = directory / name
    path.write_text(source, encoding="utf-8")
    return path


class ExecutorTests(unittest.TestCase):
    def test_argv_command_produces_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "project.yaml"
            script = write_script(
                root,
                "build.py",
                "from pathlib import Path\n"
                "Path('out').mkdir(parents=True, exist_ok=True)\n"
                "Path('out/demo.bin').write_bytes(b'galnx-demo')\n",
            )
            data = build_data(
                commands=[[sys.executable, script.name]],
                artifact="out/demo.bin",
            )
            results, ok = build.run_build_commands(manifest, data, root / "logs", "demo")
            self.assertTrue(ok)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["exit_code"], 0)
            self.assertTrue((root / "out" / "demo.bin").is_file())
            log = Path(results[0]["log"])
            self.assertTrue(log.is_file())
            self.assertIn("# command:", log.read_text(encoding="utf-8"))
            artifact = build.compute_artifact(root, "out/demo.bin")
            self.assertIsNotNone(artifact)
            assert artifact is not None
            self.assertEqual(artifact["path"], "out/demo.bin")
            self.assertEqual(artifact["size"], len(b"galnx-demo"))
            self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")

    def test_workdir_and_env_are_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workdir = root / "sub"
            workdir.mkdir()
            script = write_script(
                workdir,
                "build.py",
                "import os\n"
                "from pathlib import Path\n"
                "Path('out').mkdir(parents=True, exist_ok=True)\n"
                "Path('out/env.txt').write_text(os.environ.get('GALNX_TEST_VALUE', 'missing'))\n",
            )
            data = build_data(
                commands=[[sys.executable, script.name]],
                artifact="out/env.txt",
                workdir="sub",
                env={"GALNX_TEST_VALUE": "hello"},
            )
            results, ok = build.run_build_commands(root / "project.yaml", data, root / "logs", "demo")
            self.assertTrue(ok)
            self.assertEqual((workdir / "out" / "env.txt").read_text(encoding="utf-8"), "hello")
            artifact = build.compute_artifact(workdir, "out/env.txt")
            assert artifact is not None
            self.assertEqual(artifact["abs_path"], str((workdir / "out" / "env.txt").resolve()))

    def test_multiple_commands_run_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = write_script(
                root,
                "one.py",
                "from pathlib import Path\nPath('order.txt').write_text('one')\n",
            )
            second = write_script(
                root,
                "two.py",
                "from pathlib import Path\n"
                "text = Path('order.txt').read_text()\n"
                "Path('order.txt').write_text(text + '+two')\n",
            )
            data = build_data(commands=[[sys.executable, first.name], [sys.executable, second.name]])
            results, ok = build.run_build_commands(root / "project.yaml", data, root / "logs", "demo")
            self.assertTrue(ok)
            self.assertEqual(len(results), 2)
            self.assertEqual((root / "order.txt").read_text(encoding="utf-8"), "one+two")
            self.assertTrue(Path(results[1]["log"]).is_file())

    def test_failure_stops_remaining_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = build_data(
                commands=[
                    [sys.executable, "-c", "import sys; sys.exit(3)"],
                    [sys.executable, "-c", "open('should_not_exist.txt', 'w').write('x')"],
                ]
            )
            results, ok = build.run_build_commands(root / "project.yaml", data, root / "logs", "demo")
            self.assertFalse(ok)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["exit_code"], 3)
            self.assertFalse(results[0]["ok"])
            self.assertFalse((root / "should_not_exist.txt").exists())
            log = Path(results[0]["log"]).read_text(encoding="utf-8")
            self.assertIn("command exited with code 3", log)

    def test_timeout_returns_none_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = build_data(
                commands=[[sys.executable, "-c", "import time; time.sleep(5)"]],
                timeout_s=0.5,
            )
            results, ok = build.run_build_commands(root / "project.yaml", data, root / "logs", "demo")
            self.assertFalse(ok)
            self.assertEqual(len(results), 1)
            self.assertIsNone(results[0]["exit_code"])
            self.assertIn("timed out", results[0]["error"])
            self.assertIn("[galnx] timed out after 0.5s", Path(results[0]["log"]).read_text(encoding="utf-8"))

    def test_shell_string_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = build_data(commands=["echo hello from galnx"])
            results, ok = build.run_build_commands(root / "project.yaml", data, root / "logs", "demo")
            self.assertTrue(ok)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["shell"])
            self.assertEqual(results[0]["exit_code"], 0)
            self.assertIn("hello from galnx", Path(results[0]["log"]).read_text(encoding="utf-8"))

    def test_missing_artifact_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = build_data(
                commands=[[sys.executable, "-c", "pass"]],
                artifact="out/missing.bin",
            )
            results, ok = build.run_build_commands(root / "project.yaml", data, root / "logs", "demo")
            self.assertTrue(ok)
            self.assertIsNone(build.compute_artifact(root, "out/missing.bin"))

    def test_invalid_commands_raise_build_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "project.yaml"
            for commands in ("not-a-list", [[sys.executable, 3]], [""]):
                with self.assertRaises(build.BuildError):
                    build.parse_build_section(build_data(commands=commands), manifest)
            # An empty array is harmless at parse time; the manifest schema rejects it.
            self.assertEqual(build.parse_build_section(build_data(commands=[]), manifest).commands, ())

    def test_parse_build_section_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "project.yaml"
            config = build.parse_build_section({"schema_version": 1}, manifest)
            self.assertEqual(config.commands, ())
            self.assertIsNone(config.artifact)
            self.assertEqual(config.timeout_s, 600.0)
            self.assertEqual(config.workdir, Path(tmp).resolve())
            self.assertFalse(config.executable)

    def test_absolute_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "project.yaml"
            with self.assertRaises(build.BuildError):
                build.parse_build_section(build_data(artifact="C:/abs/demo.bin"), manifest)


if __name__ == "__main__":
    unittest.main()
