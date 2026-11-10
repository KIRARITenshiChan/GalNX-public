"""Tests for galnx.build.cache (M6-b content-addressed build cache)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import build  # noqa: E402

FINGERPRINT = {"devkitpro_gcc": "gcc test 1.0", "cmake": "cmake version 0.0-test"}


def data_with_build(**build_section):
    return {"schema_version": 1, "build": dict(build_section)}


def artifact_for(path: Path, rel: str = "out/demo.bin") -> dict:
    return {
        "path": rel,
        "abs_path": str(path.resolve()),
        "size": path.stat().st_size,
        "sha256": build.sha256_file(path),
    }


class CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._patch = mock.patch("galnx.build.cache.fingerprint_toolchain", return_value=dict(FINGERPRINT))
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def config(self, tmp: Path, **build_section):
        section = {"commands": [["python", "build.py"]], "artifact": "out/demo.bin"}
        section.update(build_section)
        return build.parse_build_section(data_with_build(**section), tmp / "project.yaml")

    def test_cache_key_is_stable_and_order_insensitive(self) -> None:
        self.assertEqual(build.cache_key({"a": 1, "b": [2, 3]}), build.cache_key({"b": [2, 3], "a": 1}))
        self.assertRegex(build.cache_key({}), r"^[0-9a-f]{64}$")

    def test_payload_key_stable_and_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = data_with_build(commands=[["python", "build.py"]], artifact="out/demo.bin")
            first = build.cache_payload("project.yaml", data, self.config(root), engine={"adapter": "custom"})
            second = build.cache_payload("project.yaml", data, self.config(root), engine={"adapter": "custom"})
            self.assertEqual(build.cache_key(first), build.cache_key(second))
            changed_env = self.config(root, env={"GALNX_SEED": "a"})
            payload = build.cache_payload("project.yaml", data, changed_env, engine={"adapter": "custom"})
            self.assertNotEqual(build.cache_key(first), build.cache_key(payload))
            changed_engine = build.cache_payload(
                "project.yaml", data, self.config(root), engine={"adapter": "custom", "pinned_commit": "0123456789abcdef0123456789abcdef01234567"}
            )
            self.assertNotEqual(build.cache_key(first), build.cache_key(changed_engine))

    def test_write_read_and_verify_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / "out" / "demo.bin"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(b"galnx-artifact")
            config = self.config(root)
            payload = build.cache_payload("project.yaml", data_with_build(), config, engine={"adapter": "custom"})
            key = build.cache_key(payload)
            artifact = artifact_for(artifact_path)
            entry = build.write_cache_entry(root, key, payload, artifact, 0.25, [{"command": "python build.py"}])
            self.assertEqual(entry["key"], key)
            expected = root / ".galnx" / "cache" / key[:16] / "meta.json"
            self.assertTrue(expected.is_file())
            loaded = build.read_cache_entry(root, key)
            assert loaded is not None
            self.assertEqual(loaded["sha256"], artifact["sha256"])
            ok, reason = build.verify_cache_entry(loaded)
            self.assertTrue(ok, reason)
            recovered = build.artifact_from_entry(loaded)
            self.assertEqual(recovered["path"], "out/demo.bin")
            self.assertEqual(recovered["size"], artifact["size"])

    def test_verify_detects_deleted_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / "out" / "demo.bin"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(b"abc")
            payload = build.cache_payload("project.yaml", data_with_build(), self.config(root))
            key = build.cache_key(payload)
            entry = build.write_cache_entry(root, key, payload, artifact_for(artifact_path), 0.1, [])
            artifact_path.unlink()
            ok, reason = build.verify_cache_entry(entry)
            self.assertFalse(ok)
            self.assertIn("artifact missing", reason)

    def test_verify_detects_changed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / "out" / "demo.bin"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(b"abc")
            payload = build.cache_payload("project.yaml", data_with_build(), self.config(root))
            key = build.cache_key(payload)
            entry = build.write_cache_entry(root, key, payload, artifact_for(artifact_path), 0.1, [])
            artifact_path.write_bytes(b"xyz")
            ok, reason = build.verify_cache_entry(entry)
            self.assertFalse(ok)
            self.assertIn("sha256 changed", reason)
            artifact_path.write_bytes(b"abcdef")
            ok, reason = build.verify_cache_entry(entry)
            self.assertFalse(ok)
            self.assertIn("size changed", reason)

    def test_read_cache_entry_rejects_unknown_and_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(build.read_cache_entry(root, "0" * 64))
            key = "1" * 64
            meta = build.entry_path(root, key)
            meta.parent.mkdir(parents=True)
            meta.write_text("not json", encoding="utf-8")
            self.assertIsNone(build.read_cache_entry(root, key))
            meta.write_text(json.dumps({"key": "2" * 64}), encoding="utf-8")
            self.assertIsNone(build.read_cache_entry(root, key))

    def test_toolchain_fingerprint_shape(self) -> None:
        with mock.patch("galnx.build.cache._TOOLCHAIN_CACHE", None):
            with mock.patch("galnx.build.cache._find_devkit_gcc", return_value=None):
                with mock.patch("galnx.build.cache._run_version", return_value="tool v1"):
                    fingerprint = build.fingerprint_toolchain()
        self.assertEqual(fingerprint["devkitpro_gcc"], "unknown")
        self.assertEqual(fingerprint["cmake"], "tool v1")

    def test_read_and_verify_reject_old_schema_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = "f" * 64
            artifact = root / "out" / "demo.bin"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"abc")
            meta = build.entry_path(root, key)
            meta.parent.mkdir(parents=True)
            legacy = {
                "schema_version": 1,
                "key": key,
                "artifact_abs": str(artifact),
                "artifact_rel": "out/demo.bin",
                "size": 3,
                "sha256": build.sha256_file(artifact),
            }
            meta.write_text(json.dumps(legacy), encoding="utf-8")
            self.assertIsNone(build.read_cache_entry(root, key))
            ok, reason = build.verify_cache_entry(legacy)
            self.assertFalse(ok)
            self.assertIn("schema_version", reason)

    def test_payload_includes_inputs_and_toolchain_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_bytes(b"int main;")
            config = self.config(
                root,
                inputs=[{"path": "src"}],
                toolchain_components=["devkitpro_gcc", "cmake"],
            )
            data = data_with_build(commands=[["python", "build.py"]], artifact="out/demo.bin")
            payload = build.cache_payload(
                "project.yaml",
                data,
                config,
                fingerprint=dict(FINGERPRINT),
                root=root,
            )
            self.assertEqual(payload["schema"], build.CACHE_SCHEMA_VERSION)
            self.assertEqual(payload["schema"], 2)
            self.assertEqual(payload["inputs"]["state"], "ok")
            self.assertEqual(payload["toolchain"]["components"], ["devkitpro_gcc", "cmake"])
            self.assertEqual(payload["toolchain"]["degraded"], [])
            self.assertIn("platform", payload["host_platform"])
            self.assertEqual(payload["cache"]["miss_reasons"], [])


if __name__ == "__main__":
    unittest.main()
