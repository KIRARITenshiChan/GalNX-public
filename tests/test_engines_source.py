"""Tests for engine source preparation (galnx.engines.source)."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx import cli as cli_module
from galnx import engines
from galnx.engines import source


def run_git(cwd, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError("git %s failed: %s" % (" ".join(args), proc.stderr))
    return proc


PATCH_GOOD = """diff --git a/data.txt b/data.txt
--- a/data.txt
+++ b/data.txt
@@ -1,2 +1,2 @@
 one
-two
+two patched
"""

PATCH_BAD = """diff --git a/data.txt b/data.txt
--- a/data.txt
+++ b/data.txt
@@ -10,2 +10,2 @@
 missing
-also missing
+replaced
"""

PATCH_CONFLICT = """diff --git a/data.txt b/data.txt
--- a/data.txt
+++ b/data.txt
@@ -1,2 +1,2 @@
 one
-two
+two other
"""


class TempRepoTest(unittest.TestCase):
    """A pristine temporary git repository with two commits and two patch files."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="galnx-source-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.email", "audit@example.com")
        run_git(self.repo, "config", "user.name", "Audit")
        run_git(self.repo, "config", "core.autocrlf", "false")
        (self.repo / "data.txt").write_text("one\ntwo\n", encoding="utf-8")
        run_git(self.repo, "add", "data.txt")
        run_git(self.repo, "commit", "-q", "-m", "first")
        self.first = run_git(self.repo, "rev-parse", "HEAD").stdout.strip()
        (self.repo / "data.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
        run_git(self.repo, "add", "data.txt")
        run_git(self.repo, "commit", "-q", "-m", "second")
        self.second = run_git(self.repo, "rev-parse", "HEAD").stdout.strip()
        run_git(self.repo, "reset", "-q", "--hard", self.first)
        self.patch_dir = self.tmp / "patches"
        self.patch_dir.mkdir()
        self.good = self.patch_dir / "good.patch"
        self.good.write_text(PATCH_GOOD, encoding="utf-8")
        self.conflict = self.patch_dir / "conflict.patch"
        self.conflict.write_text(PATCH_CONFLICT, encoding="utf-8")
        self.bad = self.patch_dir / "bad.patch"
        self.bad.write_text(PATCH_BAD, encoding="utf-8")

    def read(self, name="data.txt"):
        return (self.repo / name).read_text(encoding="utf-8")

    def lock(self):
        return json.loads((self.repo / ".galnx" / "engine-lock.json").read_text(encoding="utf-8"))


class VerifyPinTests(TempRepoTest):
    def test_verify_pin_reports_matching_head(self):
        report = source.verify_pin(self.repo, self.first)
        self.assertEqual(report["head"], self.first)
        self.assertTrue(report["matches"])
        self.assertEqual(report["dirty"], [])

    def test_verify_pin_rejects_unknown_commit(self):
        with self.assertRaises(source.EnginePrepareError):
            source.verify_pin(self.repo, "0" * 40)

    def test_verify_pin_rejects_plain_directory(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        with self.assertRaises(source.EnginePrepareError):
            source.verify_pin(plain, self.first)

    def test_verify_pin_rejects_missing_directory(self):
        with self.assertRaises(source.EnginePrepareError):
            source.verify_pin(self.tmp / "missing", self.first)

    def test_dirty_entries_reports_modified_tracked_file(self):
        (self.repo / "data.txt").write_text("dirty\n", encoding="utf-8")
        self.assertEqual(source.dirty_entries(self.repo), [" M data.txt"])


class PrepareTests(TempRepoTest):
    def test_prepare_applies_patches_and_writes_lock(self):
        result = source.prepare(
            source.SourceSpec(url=str(self.repo), commit=self.first),
            self.repo,
            [{"path": str(self.good), "notes": "first patch"}],
            [{"name": "libiconv", "version": "1.17"}],
        )
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.commit, self.first)
        self.assertEqual(result.head, self.first)
        self.assertFalse(result.check_only)
        self.assertFalse(result.fetched)
        self.assertEqual(self.read(), "one\ntwo patched\n")
        lock_path = self.repo / ".galnx" / "engine-lock.json"
        self.assertEqual(Path(result.lock_path), lock_path)
        payload = self.lock()
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["kind"], "engine-source")
        self.assertEqual(payload["source"], {"url": str(self.repo), "commit": self.first})
        self.assertEqual(payload["portlibs"], [{"name": "libiconv", "version": "1.17"}])
        self.assertEqual(len(payload["patches"]), 1)
        self.assertEqual(payload["patches"][0]["path"], str(self.good))
        self.assertEqual(payload["patches"][0]["notes"], "first patch")
        self.assertEqual(len(payload["patches"][0]["sha256"]), 64)
        self.assertTrue(payload["prepared_at"].endswith("Z"))

    def test_prepare_checks_out_the_pinned_commit(self):
        result = source.prepare(
            {"url": str(self.repo), "commit": self.first},
            self.repo,
            [str(self.good)],
        )
        self.assertEqual(result.status, "ready")
        self.assertEqual(source.head_commit(self.repo), self.first)
        self.assertEqual(self.read(), "one\ntwo patched\n")

    def test_prepare_resolves_relative_patch_path_against_base_dir(self):
        result = source.prepare(
            {"url": str(self.repo), "commit": self.first},
            self.repo,
            [{"path": "good.patch"}],
            base_dir=self.patch_dir,
        )
        self.assertEqual(result.status, "ready")
        self.assertEqual(self.read(), "one\ntwo patched\n")

    def test_prepare_conflict_rolls_back_and_writes_no_lock(self):
        result = source.prepare(
            {"url": str(self.repo), "commit": self.first},
            self.repo,
            [{"path": str(self.good)}, {"path": str(self.conflict)}],
        )
        self.assertEqual(result.status, "failed")
        self.assertTrue(result.errors)
        self.assertIn("does not apply", result.errors[0])
        self.assertFalse((self.repo / ".galnx" / "engine-lock.json").exists())
        self.assertEqual(source.dirty_entries(self.repo), [])
        self.assertEqual(self.read(), "one\ntwo\n")

    def test_prepare_rejects_dirty_worktree(self):
        (self.repo / "data.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaises(source.EnginePrepareError):
            source.prepare({"url": str(self.repo), "commit": self.first}, self.repo, [str(self.good)])

    def test_prepare_requires_commit(self):
        with self.assertRaises(source.EnginePrepareError):
            source.prepare({"url": str(self.repo)}, self.repo)

    def test_prepare_requires_fetch_for_missing_destination(self):
        dest = self.tmp / "missing-dest"
        with self.assertRaises(source.EnginePrepareError):
            source.prepare({"url": str(self.repo), "commit": self.first}, dest)

    def test_prepare_rejects_foreign_non_empty_destination(self):
        dest = self.tmp / "foreign"
        dest.mkdir()
        (dest / "keep.txt").write_text("keep\n", encoding="utf-8")
        with self.assertRaises(source.EnginePrepareError):
            source.prepare({"url": str(self.repo), "commit": self.first}, dest, fetch=True)

    def test_prepare_fetch_clones_and_checks_out_pin(self):
        dest = self.tmp / "clone"
        result = source.prepare(
            {"url": str(self.repo), "commit": self.first},
            dest,
            [str(self.good)],
            fetch=True,
        )
        self.assertEqual(result.status, "ready")
        self.assertTrue(result.fetched)
        self.assertEqual(source.head_commit(dest), self.first)
        self.assertEqual((dest / "data.txt").read_text(encoding="utf-8"), "one\ntwo patched\n")
        self.assertTrue((dest / ".galnx" / "engine-lock.json").is_file())


class CheckOnlyTests(TempRepoTest):
    def test_check_only_applies_nothing_and_writes_nothing(self):
        result = source.prepare(
            {"url": str(self.repo), "commit": self.first},
            self.repo,
            [str(self.good)],
            check_only=True,
        )
        self.assertEqual(result.status, "checked")
        self.assertTrue(result.check_only)
        self.assertEqual(result.head, self.first)
        self.assertEqual(result.errors, ())
        self.assertEqual(result.lock_path, "")
        self.assertTrue(result.patches[0]["applies"])
        self.assertEqual(self.read(), "one\ntwo\n")
        self.assertFalse((self.repo / ".galnx").exists())
        self.assertEqual(source.dirty_entries(self.repo), [])

    def test_check_only_reports_conflicting_patch(self):
        result = source.prepare(
            {"url": str(self.repo), "commit": self.first},
            self.repo,
            [str(self.bad)],
            check_only=True,
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(len(result.errors), 1)
        self.assertIn("does not apply", result.errors[0])
        self.assertFalse((self.repo / ".galnx").exists())
        self.assertEqual(self.read(), "one\ntwo\n")

    def test_check_only_reports_wrong_head(self):
        run_git(self.repo, "reset", "-q", "--hard", self.second)
        result = source.prepare(
            {"url": str(self.repo), "commit": self.first},
            self.repo,
            [str(self.good)],
            check_only=True,
        )
        self.assertEqual(result.status, "failed")
        self.assertTrue(any("expected pinned commit" in item for item in result.errors))
        self.assertEqual(source.head_commit(self.repo), self.second)


class DescriptorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.descriptor = engines.load_descriptor(ROOT / "examples" / "engines" / "kirikiroid2-nx.yaml")

    def test_descriptor_exposes_new_sections(self):
        data = self.descriptor.to_dict()
        self.assertEqual(sorted(data), sorted(set(data)))
        self.assertEqual(len(data), 23)
        for key in ("source", "patches", "portlibs", "build"):
            self.assertIn(key, data)
        self.assertEqual(self.descriptor.source["commit"], "e96b6034c292c6ccdb099823ab6a0a6b505f77f3")
        self.assertEqual(len(self.descriptor.patches), 9)
        patch_paths = [str(item["path"]) for item in self.descriptor.patches]
        self.assertTrue(patch_paths[-1].endswith("I-save-exit-mouse.patch"))
        self.assertTrue(patch_paths[-2].endswith("H-input-tweaks.patch"))
        self.assertTrue(patch_paths[-3].endswith("G-controller-input-v2.patch"))
        self.assertTrue(patch_paths[-4].endswith("F-close-exit.patch"))
        self.assertTrue(patch_paths[3].endswith("D-virtual-mouse-dpad.patch"))
        self.assertTrue(patch_paths[4].endswith("E-controller-ui-saveload.patch"))
        self.assertEqual(len(self.descriptor.portlibs), 7)
        self.assertEqual(len(self.descriptor.build["commands"]), 6)
        self.assertEqual(self.descriptor.validate(), [])
        self.assertEqual(engines.descriptor_prepare_errors(self.descriptor), [])

    def test_descriptor_prepare_errors_requires_commit_and_commands(self):
        from dataclasses import replace

        broken = replace(
            self.descriptor,
            source={"url": self.descriptor.upstream_url, "commit": ""},
            pinned_commit="",
            build={"commands": []},
        )
        problems = engines.descriptor_prepare_errors(broken)
        self.assertTrue(any("pinned commit is required" in item for item in problems))
        self.assertTrue(any("build.commands" in item for item in problems))

    def test_k2nx_plan_uses_descriptor_sections(self):
        import yaml as _yaml

        manifest = _yaml.safe_load((ROOT / "examples" / "manifest.krkr.yaml").read_text(encoding="utf-8"))
        steps = engines.adapter_for(self.descriptor).plan_build(self.descriptor, manifest)
        ids = [step.id for step in steps]
        self.assertEqual(
            ids,
            ["manifest", "source", "patches", "portlibs", "engine-build", "content", "artifact", "verify"],
        )
        self.assertIn("git -C src/engine apply", steps[2].command)
        self.assertIn("bash platforms/switch/tools/portlibs/build_libiconv.sh", steps[3].command)
        self.assertIn("build_k2.sh all Release", steps[4].command)
        self.assertTrue(steps[6].command.endswith(".nsp"))

    def test_source_spec_falls_back_to_upstream_fields(self):
        spec = engines.source_spec(engines.KRKRSDL2)
        self.assertEqual(spec["url"], engines.KRKRSDL2.upstream_url)
        self.assertEqual(spec["commit"], engines.KRKRSDL2.pinned_commit)


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="galnx-source-cli-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)

    def test_engines_info_json_includes_new_sections(self):
        engines_dir = self.tmp / "engines"
        engines_dir.mkdir()
        shutil.copyfile(
            ROOT / "examples" / "engines" / "kirikiroid2-nx.yaml",
            engines_dir / "kirikiroid2-nx.yaml",
        )
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli_module.main(
                ["engines", "info", "kirikiroid2-nx", "--engines-dir", str(engines_dir), "--json"]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        engine = payload["engine"]
        self.assertEqual(engine["id"], "kirikiroid2-nx")
        self.assertEqual(engine["source"]["commit"], engine["pinned_commit"])
        self.assertEqual(len(engine["patches"]), 9)
        self.assertEqual(len(engine["portlibs"]), 7)
        self.assertEqual(len(engine["build"]["commands"]), 6)
        self.assertEqual(payload["problems"], [])

    def test_prepare_parser_check_only_against_temp_repo(self):
        repo_dir = self.tmp / "repo"
        repo_dir.mkdir()
        run_git(repo_dir, "init", "-q")
        run_git(repo_dir, "config", "user.email", "audit@example.com")
        run_git(repo_dir, "config", "user.name", "Audit")
        run_git(repo_dir, "config", "core.autocrlf", "false")
        (repo_dir / "data.txt").write_text("one\ntwo\n", encoding="utf-8")
        run_git(repo_dir, "add", "data.txt")
        run_git(repo_dir, "commit", "-q", "-m", "first")
        commit = run_git(repo_dir, "rev-parse", "HEAD").stdout.strip()
        patch = self.tmp / "good.patch"
        patch.write_text(PATCH_GOOD, encoding="utf-8")

        data = json.loads(json.dumps(engines.BUILTIN_ENGINES["krkrsdl2"].to_dict()))
        data["id"] = "temp-engine"
        data["display_name"] = "Temp Engine"
        data["source"] = {"url": str(repo_dir), "commit": commit}
        data["pinned_commit"] = commit
        data["patches"] = [{"path": "good.patch"}]
        data["portlibs"] = [{"name": "libiconv", "version": "1.17"}]
        data["build"] = {"commands": ["echo build"], "workdir": "."}
        descriptor_path = self.tmp / "temp-engine.yaml"
        descriptor_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command", required=True)
        source.register(sub)
        args = parser.parse_args(
            [
                "prepare",
                "--descriptor",
                str(descriptor_path),
                "--dest",
                str(repo_dir),
                "--check-only",
                "--json",
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = args.func(args)
        self.assertEqual(code, 0, stderr.getvalue())
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "checked")
        self.assertEqual(payload["commit"], commit)
        self.assertEqual(payload["head"], commit)
        self.assertTrue(payload["check_only"])
        self.assertTrue(payload["patches"][0]["applies"])
        self.assertFalse((repo_dir / ".galnx").exists())

    def test_prepare_parser_rejects_prebuilt_descriptor(self):
        data = json.loads(json.dumps(engines.BUILTIN_ENGINES["brewser"].to_dict()))
        descriptor_path = self.tmp / "brewser.yaml"
        descriptor_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command", required=True)
        source.register(sub)
        args = parser.parse_args(
            ["prepare", "--descriptor", str(descriptor_path), "--dest", str(self.tmp / "unused")]
        )
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = args.func(args)
        self.assertEqual(code, 2)
        self.assertIn("prebuilt", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
