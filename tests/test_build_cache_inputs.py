"""Tests for build.inputs digests and toolchain component degradation."""
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
from galnx.build.config import BuildError  # noqa: E402

SCHEMA_PATH = ROOT / "schemas" / "game-manifest.schema.json"

HEALTHY = {
    "devkitpro_gcc": "aarch64-none-elf-gcc (devkitA64) 13.2.0",
    "cmake": "cmake version 3.27.0",
    "ninja": "1.11.1",
    "rustc": "rustc 1.75.0",
    "cargo": "cargo 1.75.0",
    "sdl2": "2.28.5",
    "ffmpeg_source_commit": "0123456789abcdef0123456789abcdef01234567",
    "host_platform": "win32-AMD64",
}


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build_data(**build_section):
    return {"schema_version": 1, "build": dict(build_section)}


def parse(tmp: Path, manifest_ref: str = "manifest.yaml", **build_section):
    return build.parse_build_section(
        build_data(**build_section), tmp / manifest_ref
    )


def payload(tmp: Path, manifest_ref: str = "manifest.yaml", fingerprint=None, **build_section):
    config = parse(tmp, manifest_ref=manifest_ref, **build_section)
    return build.cache_payload(
        manifest_ref,
        build_data(**build_section),
        config,
        engine={"adapter": "custom"},
        fingerprint=dict(HEALTHY if fingerprint is None else fingerprint),
        root=tmp,
    )


def artifact_for(path: Path) -> dict:
    return {
        "path": path.name,
        "abs_path": str(path.resolve()),
        "size": path.stat().st_size,
        "sha256": build.sha256_file(path),
    }


class CacheInputTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch(
            "galnx.build.cache.fingerprint_toolchain", return_value=dict(HEALTHY)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_unchanged_inputs_hit_and_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "src" / "main.c", b"int main(void){return 0;}")
            section = {"inputs": [{"path": "src", "kind": "tree"}]}
            first = payload(root, **section)
            second = payload(root, **section)
            self.assertEqual(build.cache_key(first), build.cache_key(second))
            self.assertEqual(first["schema"], build.CACHE_SCHEMA_VERSION)
            self.assertEqual(first["schema"], 2)
            self.assertEqual(first["inputs"]["state"], "ok")
            self.assertEqual(first["cache"]["miss_reasons"], [])
            artifact = root / "dist" / "demo.nro"
            write(artifact, b"nro-bytes")
            key = build.cache_key(first)
            build.write_cache_entry(root, key, first, artifact_for(artifact), 0.1, [])
            loaded = build.read_cache_entry(root, key)
            assert loaded is not None
            ok, reason = build.verify_cache_entry(loaded)
            self.assertTrue(ok, reason)

    def test_changed_tracked_source_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src" / "main.c"
            write(source, b"aaaa")
            section = {"inputs": [{"path": "src"}]}
            before = build.cache_key(payload(root, **section))
            write(source, b"bbbb")  # same length: content-only change must matter
            after = build.cache_key(payload(root, **section))
            self.assertNotEqual(before, after)

    def test_changed_patch_file_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patch = root / "patches" / "fix.patch"
            write(patch, b"--- a\n+++ b\n")
            section = {"inputs": [{"path": "patches/fix.patch", "kind": "file"}]}
            before = build.cache_key(payload(root, **section))
            write(patch, b"--- a\n+++ c\n")
            after = build.cache_key(payload(root, **section))
            self.assertNotEqual(before, after)

    def test_changed_manifest_inputs_miss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cargo_lock = root / "Cargo.lock"
            configure = root / "ffmpeg" / "configure.args"
            write(cargo_lock, b'version = 3\n')
            write(configure, b"--enable-foo\n")
            section = {
                "inputs": [
                    {"path": "Cargo.lock", "kind": "file"},
                    {"path": "ffmpeg/configure.args", "kind": "file"},
                ]
            }
            before = build.cache_key(payload(root, **section))
            write(cargo_lock, b'version = 4\n')
            cargo_changed = build.cache_key(payload(root, **section))
            write(configure, b"--enable-bar\n")
            both_changed = build.cache_key(payload(root, **section))
            self.assertNotEqual(before, cargo_changed)
            self.assertNotEqual(cargo_changed, both_changed)

    def test_untracked_document_does_not_invalidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "src" / "main.c", b"code")
            write(root / "docs" / "notes.md", b"v1")
            section = {"inputs": [{"path": "src"}]}
            before = build.cache_key(payload(root, **section))
            write(root / "docs" / "notes.md", b"v2 changed")
            after = build.cache_key(payload(root, **section))
            self.assertEqual(before, after)

    def test_artifact_corruption_fails_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "dist" / "demo.nro"
            write(artifact, b"abcdef")
            current = payload(root)
            key = build.cache_key(current)
            entry = build.write_cache_entry(
                root, key, current, artifact_for(artifact), 0.1, []
            )
            ok, reason = build.verify_cache_entry(entry)
            self.assertTrue(ok, reason)
            write(artifact, b"abc")  # truncated: size mismatch
            ok, reason = build.verify_cache_entry(entry)
            self.assertFalse(ok)
            self.assertIn("size changed", reason)
            write(artifact, b"abcdex")  # restored size, changed content
            ok, reason = build.verify_cache_entry(entry)
            self.assertFalse(ok)
            self.assertIn("sha256 changed", reason)

    def test_old_schema_entry_is_ignored_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "dist" / "demo.nro"
            write(artifact, b"nro")
            key = "a" * 64
            meta = build.entry_path(root, key)
            meta.parent.mkdir(parents=True)
            legacy = {
                "schema_version": 1,
                "key": key,
                "artifact_abs": str(artifact),
                "artifact_rel": "demo.nro",
                "size": 3,
                "sha256": build.sha256_file(artifact),
            }
            meta.write_text(json.dumps(legacy), encoding="utf-8")
            self.assertIsNone(build.read_cache_entry(root, key))
            ok, reason = build.verify_cache_entry(legacy)
            self.assertFalse(ok)
            self.assertIn("schema_version", reason)

    def test_declared_degraded_toolchain_component_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fingerprint = dict(HEALTHY, ninja="unknown")
            degraded = payload(root, fingerprint=fingerprint)
            self.assertEqual(degraded["toolchain"]["degraded"], ["ninja"])
            self.assertIn("ninja", degraded["toolchain"]["unknown"])
            self.assertTrue(
                degraded["cache"]["miss_reasons"][0].startswith(
                    "degraded toolchain: unknown version for ninja"
                )
            )
            custom = payload(
                root,
                fingerprint=dict(HEALTHY, ninja="unknown"),
                toolchain_components=["devkitpro_gcc", "cmake"],
            )
            self.assertEqual(custom["toolchain"]["degraded"], [])
            self.assertEqual(custom["cache"]["miss_reasons"], [])

    def test_undeclared_unknown_component_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fingerprint = dict(HEALTHY, rustc="unknown", sdl2="unknown")
            current = payload(root, fingerprint=fingerprint)
            self.assertEqual(current["toolchain"]["degraded"], [])
            self.assertEqual(current["cache"]["miss_reasons"], [])
            self.assertIn("rustc", current["toolchain"]["unknown"])
            self.assertEqual(
                current["toolchain"]["components"],
                ["devkitpro_gcc", "cmake", "ninja"],
            )

    def test_missing_required_input_misses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = payload(root, inputs=[{"path": "src"}])
            self.assertEqual(current["inputs"]["state"], "missing")
            self.assertEqual(current["inputs"]["missing"], ["src"])
            self.assertEqual(current["inputs"]["specs"][0]["state"], "missing")
            self.assertTrue(
                current["cache"]["miss_reasons"][0].startswith(
                    "required build input missing: src"
                )
            )

    def test_optional_missing_input_does_not_invalidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "src" / "main.c", b"code")
            without = payload(root, inputs=[{"path": "src"}])
            with_optional = payload(
                root,
                inputs=[{"path": "src"}, {"path": "vendor", "optional": True}],
            )
            self.assertEqual(with_optional["inputs"]["state"], "ok")
            self.assertEqual(with_optional["inputs"]["missing"], [])
            self.assertEqual(
                with_optional["inputs"]["specs"][1]["state"], "optional-missing"
            )
            self.assertEqual(with_optional["cache"]["miss_reasons"], [])
            self.assertEqual(
                with_optional["inputs"]["specs"][0]["digest"],
                without["inputs"]["specs"][0]["digest"],
            )

    def test_tree_ignores_and_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree = root / "tree"
            write(tree / "z-last.txt", b"z")
            write(tree / "a-first.txt", b"a")
            write(tree / "src" / "keep.c", b"keep")
            write(tree / "src" / "obj" / "a.o", b"obj")
            write(tree / "target" / "generated.bin", b"gen")
            write(tree / ".git" / "config", b"git")
            write(tree / ".galnx" / "cache" / "state.json", b"{}")
            section = {
                "inputs": [
                    {"path": "tree", "ignore": ["*.o", "target/", "*.tmp"]},
                ]
            }
            first = payload(root, **section)
            second = payload(root, **section)
            entries = first["inputs"]["specs"][0]["entries"]
            self.assertEqual(
                [entry["path"] for entry in entries],
                ["a-first.txt", "src/keep.c", "z-last.txt"],
            )
            self.assertEqual(build.cache_key(first), build.cache_key(second))
            serialized = json.dumps(entries, sort_keys=True)
            self.assertNotIn(".git", serialized)
            self.assertNotIn(".galnx", serialized)
            self.assertNotIn("a.o", serialized)
            self.assertNotIn("generated.bin", serialized)

    def test_payload_contains_host_platform_and_miss_reason_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = payload(root)
            self.assertIn("platform", current["host_platform"])
            self.assertIn("machine", current["host_platform"])
            self.assertEqual(current["cache"]["miss_reasons"], [])
            self.assertIn("inputs", current)
            self.assertIn("versions", current["toolchain"])

    def test_config_parser_rejects_bad_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(BuildError):
                parse(root, inputs=[{"path": "src", "kind": "archive"}])
            with self.assertRaises(BuildError):
                parse(root, inputs=[{"kind": "tree"}])
            with self.assertRaises(BuildError):
                parse(root, inputs=[{"path": "src", "surprise": True}])
            with self.assertRaises(BuildError):
                parse(root, toolchain_components=[])
            config = parse(
                root,
                inputs=[{"path": "src", "kind": "file", "optional": True}],
                toolchain_components=["cmake"],
            )
            self.assertEqual(config.inputs[0].kind, "file")
            self.assertTrue(config.inputs[0].optional)
            self.assertEqual(config.toolchain_components, ("cmake",))


class ManifestSchemaInputTests(unittest.TestCase):
    def setUp(self) -> None:
        from jsonschema import Draft202012Validator, FormatChecker

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def manifest(self, **build_section) -> dict:
        section = {"output_dir": "dist"}
        section.update(build_section)
        return {
            "schema_version": 1,
            "game": {"id": "demo", "title": "Demo", "source_dir": "/games/demo"},
            "engine": {"adapter": "custom"},
            "switch": {"title_id": "0100000000000000", "target": "nro"},
            "build": section,
        }

    def errors(self, data: dict) -> list[str]:
        return [error.message for error in self.validator.iter_errors(data)]

    def test_manifest_without_inputs_still_validates(self) -> None:
        self.assertEqual(self.errors(self.manifest()), [])
        self.assertEqual(
            self.errors(
                self.manifest(commands=[["python", "build.py"]], artifact="out/demo.nro")
            ),
            [],
        )

    def test_manifest_with_inputs_and_components_validates(self) -> None:
        data = self.manifest(
            inputs=[
                {"path": "src", "kind": "tree", "ignore": ["*.o"]},
                {"path": "patches/fix.patch", "kind": "file", "optional": True},
            ],
            toolchain_components=["devkitpro_gcc", "cmake", "ninja"],
        )
        self.assertEqual(self.errors(data), [])

    def test_bad_input_declarations_are_rejected(self) -> None:
        cases = [
            {"path": "src", "kind": "archive"},
            {"kind": "tree"},
            {"path": "src", "surprise": True},
            {"path": "src", "optional": "yes"},
        ]
        for item in cases:
            errors = self.errors(self.manifest(inputs=[item]))
            self.assertTrue(errors, item)
        self.assertTrue(self.errors(self.manifest(toolchain_components=[])))


if __name__ == "__main__":
    unittest.main()
