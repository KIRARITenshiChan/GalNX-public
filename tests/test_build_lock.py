"""Tests for galnx.build.lock (M6-b dependency locking)."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import build  # noqa: E402

TOOLCHAIN = {"devkitpro_gcc": "gcc test", "cmake": "cmake test"}


def entry(digest: str = "a" * 64, commit: str = "0123456789abcdef0123456789abcdef01234567") -> dict:
    return {
        "manifest": "project.yaml",
        "engine": {"adapter": "custom", "pinned_commit": commit, "build_backend": "none"},
        "toolchain": dict(TOOLCHAIN),
        "manifest_sha256": digest,
        "artifact": "out/demo.bin",
    }


class LockTests(unittest.TestCase):
    def test_manifest_sha256_matches_file_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.yaml"
            path.write_bytes(b"schema_version: 1\n")
            expected = hashlib.sha256(b"schema_version: 1\n").hexdigest()
            self.assertEqual(build.manifest_sha256(path), expected)

    def test_build_write_read_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(build.read_lock(root))
            lock = build.build_lock({"project.yaml": entry()}, toolchain=TOOLCHAIN, generated_at="2026-10-30T00:00:00Z")
            self.assertEqual(lock["schema_version"], build.LOCK_SCHEMA_VERSION)
            self.assertEqual(lock["generated_at"], "2026-10-30T00:00:00Z")
            path = build.write_lock(root, lock)
            self.assertEqual(path, root / ".galnx" / "engine-lock.json")
            loaded = build.read_lock(root)
            assert loaded is not None
            self.assertEqual(loaded["projects"]["project.yaml"]["manifest_sha256"], "a" * 64)

    def test_read_lock_rejects_corrupt_and_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = build.lock_path(root)
            path.parent.mkdir(parents=True)
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(build.LockError):
                build.read_lock(root)
            path.write_text(json.dumps({"schema_version": 99, "projects": {}}), encoding="utf-8")
            with self.assertRaises(build.LockError):
                build.read_lock(root)

    def test_compare_missing_lock_reports_every_project(self) -> None:
        drift = build.compare_projects(None, {"project.yaml": entry()})
        self.assertIn("project.yaml", drift)
        self.assertIn("lock file missing", drift["project.yaml"][0])

    def test_compare_clean_when_unchanged(self) -> None:
        lock = build.build_lock({"project.yaml": entry()}, toolchain=TOOLCHAIN)
        self.assertEqual(build.compare_projects(lock, {"project.yaml": entry()}), {})

    def test_compare_detects_manifest_engine_and_toolchain_drift(self) -> None:
        lock = build.build_lock({"project.yaml": entry()}, toolchain=TOOLCHAIN)
        changed = entry(digest="b" * 64, commit="f" * 40)
        changed["toolchain"] = {"devkitpro_gcc": "gcc other", "cmake": "cmake test"}
        drift = build.compare_projects(lock, {"project.yaml": changed})
        messages = drift["project.yaml"]
        joined = " | ".join(messages)
        self.assertIn("manifest_sha256 changed", joined)
        self.assertIn("engine.pinned_commit drift", joined)
        self.assertIn("toolchain.devkitpro_gcc changed", joined)
        self.assertIn("project.yaml", build.describe_drift(drift))

    def test_compare_reports_unrecorded_project(self) -> None:
        lock = build.build_lock({"project.yaml": entry()}, toolchain=TOOLCHAIN)
        drift = build.compare_projects(lock, {"other.yaml": entry()})
        self.assertIn("not recorded in lock file", drift["other.yaml"][0])


if __name__ == "__main__":
    unittest.main()
