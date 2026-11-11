"""Tests for the public quickstart example (examples/quickstart).

The quickstart is part of the release contract: a clean checkout with Python
only must be able to run one real build, verify its artifact, and hit the
cache on the second run. These tests copy the example to a temporary
directory so they never write into the repository working tree.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import cli  # noqa: E402

EXAMPLE = ROOT / "examples" / "quickstart"
PACK_MAGIC = b"GALNXPK1"


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli.main(list(argv))
    return int(code), stdout.getvalue(), stderr.getvalue()


def read_pack(path: Path) -> list[tuple[str, int, str]]:
    """Parse out/demo.pak and return (name, size, sha256) entries."""
    data = path.read_bytes()
    if data[:8] != PACK_MAGIC:
        raise AssertionError("bad pack magic: %r" % data[:8])
    count = int.from_bytes(data[8:12], "big")
    offset = 12
    entries: list[tuple[str, int, str]] = []
    for _ in range(count):
        name_len = int.from_bytes(data[offset : offset + 2], "big")
        offset += 2
        name = data[offset : offset + name_len].decode("utf-8")
        offset += name_len
        size = int.from_bytes(data[offset : offset + 8], "big")
        offset += 8
        digest = data[offset : offset + 32]
        offset += 32
        payload = data[offset : offset + size]
        offset += size
        if hashlib.sha256(payload).digest() != digest:
            raise AssertionError("digest mismatch for %s" % name)
        entries.append((name, size, digest.hex()))
    if offset != len(data):
        raise AssertionError("trailing bytes in pack")
    return entries


class QuickstartExampleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="galnx-quickstart-")
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        shutil.copytree(EXAMPLE, self.repo / "examples" / "quickstart")
        self.example = self.repo / "examples" / "quickstart"
        self.manifest = self.example / "manifest.yaml"
        self.artifact = self.example / "out" / "demo.pak"

    def build(self, json_mode: bool = True) -> tuple[int, str, str]:
        argv = ["build", "run", "--manifest", str(self.manifest), "--yes"]
        if json_mode:
            argv.append("--json")
        # The manifest's game.source_dir is resolved against the current
        # directory by preflight, so run from the copied repository root.
        with contextlib.chdir(self.repo):
            return run_cli(argv)

    def build_report(self) -> dict:
        code, stdout, stderr = self.build()
        self.assertEqual(code, 0, "exit code %d; stderr=%s" % (code, stderr))
        return json.loads(stdout)

    def test_build_artifact_and_cache_cycle(self) -> None:
        first = self.build_report()
        totals = first["totals"]
        self.assertEqual(totals["fail"], 0, first["projects"][0].get("errors"))
        self.assertEqual(totals["executed"], 1)
        self.assertEqual(totals["cache_hits"], 0)
        self.assertEqual(totals["cache_misses"], 1)
        self.assertEqual(totals["built"], 1)
        project = first["projects"][0]
        self.assertEqual(project["build_state"], "executed")
        self.assertEqual(project["name"], "quickstart-demo")
        self.assertEqual(project["adapter"], "krkrsdl2")

        self.assertTrue(self.artifact.is_file(), "artifact was not produced")
        entries = read_pack(self.artifact)
        self.assertEqual([item[0] for item in entries], ["demo.txt", "sub/extra.txt"])
        self.assertGreater(entries[0][1], 0)
        first_sha = hashlib.sha256(self.artifact.read_bytes()).hexdigest()

        second = self.build_report()
        totals = second["totals"]
        self.assertEqual(totals["fail"], 0)
        self.assertEqual(totals["executed"], 0)
        self.assertEqual(totals["cache_hits"], 1)
        self.assertEqual(totals["cache_misses"], 0)
        self.assertEqual(totals["built"], 0)
        self.assertEqual(second["projects"][0]["build_state"], "cache_hit")
        self.assertEqual(
            hashlib.sha256(self.artifact.read_bytes()).hexdigest(), first_sha
        )
        self.assertTrue((self.example / ".galnx" / "cache").is_dir())

        # Changing a declared build input must invalidate the cache and
        # produce a different artifact.
        demo = self.example / "content" / "demo.txt"
        demo.write_bytes(demo.read_bytes() + b"changed after first build\n")
        third = self.build_report()
        totals = third["totals"]
        self.assertEqual(totals["fail"], 0)
        self.assertEqual(totals["executed"], 1)
        self.assertEqual(totals["cache_hits"], 0)
        self.assertEqual(totals["cache_misses"], 1)
        self.assertEqual(third["projects"][0]["build_state"], "executed")
        self.assertNotEqual(
            hashlib.sha256(self.artifact.read_bytes()).hexdigest(), first_sha
        )

    def test_pack_demo_is_deterministic(self) -> None:
        packer = self.example / "tools" / "pack_demo.py"
        content = self.example / "content"
        shas: list[str] = []
        for _ in range(2):
            proc = subprocess.run(
                [sys.executable, str(packer), str(content)],
                cwd=str(self.example),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("packed 2 file(s)", proc.stdout)
            shas.append(hashlib.sha256(self.artifact.read_bytes()).hexdigest())
        self.assertEqual(shas[0], shas[1])
        self.assertEqual(read_pack(self.artifact)[0][0], "demo.txt")


if __name__ == "__main__":
    unittest.main()
