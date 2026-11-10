"""TASK-LICENSE：SBOM 清单与校验脚本的测试。

覆盖 docs/third_party/inventory.yaml（仓库清单）与 scripts/check_license_inventory.py
的校验规则：必填字段、枚举、GPL 义务、artifacts 关联、补丁路径、个人目录泄漏等。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_license_inventory.py"
REPO_INVENTORY = ROOT / "docs" / "third_party" / "inventory.yaml"


def base_component(**overrides):
    comp = {
        "id": "demo-lib",
        "name": "Demo Lib",
        "upstream": "https://example.com/demo",
        "version_or_commit": "1.0.0",
        "license_spdx": "MIT",
        "license_url": "https://example.com/demo/LICENSE",
        "license_family": "permissive",
        "link_mode": "static",
        "included_in_nsp": False,
        "distribution_class": "development-only",
        "patches": [],
        "obligations": [],
        "evidence": [{"type": "repo", "path": "LICENSE", "note": "仓库许可证"}],
        "notes": "演示组件",
    }
    comp.update(overrides)
    return comp


def base_inventory():
    return {
        "schema_version": 1,
        "generated_at": "2026-11-11",
        "scope": {
            "project": "GalNX",
            "baseline_commit": "974a4141af4a86a83f9434ea69ebb9dc9ffe4834",
            "artifacts": [
                {
                    "id": "demo-nsp",
                    "description": "演示产物",
                    "sha256": "a" * 64,
                    "size_bytes": 123456,
                    "distributed": False,
                    "evidence": [{"path": "LICENSE", "note": "仓库许可证"}],
                }
            ],
        },
        "components": [base_component()],
    }


class CheckerFixtureMixin:
    """在临时仓库根上构造最小 inventory，调用真实脚本。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "demo.patch").write_text("diff\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_checker(self, data, inventory_path=None, root=None, json_output=True):
        if inventory_path is None:
            inventory_path = self.root / "inventory.yaml"
            with inventory_path.open("w", encoding="utf-8") as fh:
                yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
        args = [
            sys.executable,
            str(SCRIPT),
            "--inventory",
            str(inventory_path),
            "--root",
            str(root if root is not None else self.root),
        ]
        if json_output:
            args.append("--json")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env=env,
        )
        payload = None
        if json_output and proc.stdout.strip():
            payload = json.loads(proc.stdout)
        return proc, payload

    def assert_fails_with(self, data, needle, **kwargs):
        proc, payload = self.run_checker(data, **kwargs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIsNotNone(payload, proc.stdout + proc.stderr)
        self.assertFalse(payload["ok"])
        joined = "\n".join(payload["errors"])
        self.assertIn(needle, joined, joined)
        return payload


class RepositoryInventoryTest(unittest.TestCase):
    """仓库内真实清单必须通过校验。"""

    def test_repository_inventory_exists(self):
        self.assertTrue(REPO_INVENTORY.is_file(), f"缺少清单：{REPO_INVENTORY}")

    def test_repository_inventory_passes(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["errors"], [])
        self.assertGreaterEqual(payload["components"], 25)
        self.assertGreaterEqual(payload["artifacts"], 1)
        # 已知的未锁定风险以 warning 形式出现，而不是错误
        self.assertTrue(any("jxrlib" in w for w in payload["warnings"]))

    def test_repository_inventory_pins_ffmpeg_gpl(self):
        with REPO_INVENTORY.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        by_id = {c["id"]: c for c in data["components"]}
        ffmpeg = by_id["ffmpeg-nvtegra"]
        self.assertEqual(ffmpeg["license_spdx"], "GPL-2.0-or-later")
        self.assertTrue(ffmpeg["included_in_nsp"])
        self.assertTrue(ffmpeg["obligations"])
        # 旧 NOTICES 把 FFmpeg 写成 LGPL，本题要求改为 GPL 归类
        self.assertNotIn("LGPL", ffmpeg["license_spdx"])
        k2nx = by_id["kirikiroid2-nx"]
        self.assertEqual(k2nx["license_spdx"], "NOASSERTION")
        self.assertTrue(k2nx["license_name"])
        self.assertTrue(k2nx["license_url"])


class ValidationRulesTest(CheckerFixtureMixin, unittest.TestCase):
    """逐条验证 checker 的规则。"""

    def test_minimal_valid_inventory_passes(self):
        proc, payload = self.run_checker(base_inventory())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["components"], 1)

    def test_human_output_ok(self):
        proc, _ = self.run_checker(base_inventory(), json_output=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_missing_required_field_fails(self):
        data = base_inventory()
        del data["components"][0]["upstream"]
        self.assert_fails_with(data, "upstream")

    def test_bad_enum_fails(self):
        data = base_inventory()
        data["components"][0]["license_family"] = "proprietary-ish"
        self.assert_fails_with(data, "license_family")

    def test_duplicate_component_id_fails(self):
        data = base_inventory()
        data["components"] = [base_component(), base_component()]
        self.assert_fails_with(data, "重复的组件 id")

    def test_gpl_included_without_obligations_fails(self):
        data = base_inventory()
        data["components"] = [
            base_component(
                id="gpl-lib",
                license_spdx="GPL-2.0-or-later",
                license_family="copyleft",
                distribution_class="runtime-linked",
                included_in_nsp=True,
                artifacts=["demo-nsp"],
                obligations=[],
            )
        ]
        self.assert_fails_with(data, "obligations")

    def test_gpl_included_with_obligations_passes(self):
        data = base_inventory()
        data["components"] = [
            base_component(
                id="gpl-lib",
                license_spdx="GPL-2.0-or-later",
                license_family="copyleft",
                distribution_class="runtime-linked",
                included_in_nsp=True,
                artifacts=["demo-nsp"],
                obligations=["provide_corresponding_source", "include_license_text"],
            )
        ]
        proc, payload = self.run_checker(data)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(payload["ok"])

    def test_included_without_artifacts_fails(self):
        data = base_inventory()
        data["components"][0]["included_in_nsp"] = True
        data["components"][0]["distribution_class"] = "runtime-linked"
        self.assert_fails_with(data, "artifacts")

    def test_unknown_artifact_id_fails(self):
        data = base_inventory()
        data["components"][0].update(
            included_in_nsp=True,
            distribution_class="runtime-linked",
            artifacts=["nope-nsp"],
        )
        self.assert_fails_with(data, "未知 artifact id")

    def test_missing_patch_path_fails(self):
        data = base_inventory()
        data["components"][0]["patches"] = ["docs/builds/patches/nope.patch"]
        self.assert_fails_with(data, "文件不存在")

    def test_existing_patch_path_passes(self):
        data = base_inventory()
        data["components"][0]["patches"] = ["docs/demo.patch"]
        proc, payload = self.run_checker(data)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(payload["ok"])

    def test_absolute_patch_path_fails(self):
        data = base_inventory()
        data["components"][0]["patches"] = ["C:" + "/" + "Users" + "/alice/build.patch"]
        proc, payload = self.run_checker(data)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertFalse(payload["ok"])

    def test_parent_traversal_patch_path_fails(self):
        data = base_inventory()
        data["components"][0]["patches"] = ["../outside.patch"]
        self.assert_fails_with(data, "路径穿越")

    def test_noassertion_requires_name_and_url(self):
        data = base_inventory()
        data["components"][0].pop("license_url", None)
        data["components"][0]["license_spdx"] = "NOASSERTION"
        payload = self.assert_fails_with(data, "license_name")
        self.assertTrue(any("license_url" in e for e in payload["errors"]))

    def test_noassertion_with_name_and_url_passes(self):
        data = base_inventory()
        data["components"][0].update(
            license_spdx="NOASSERTION",
            license_name="Custom BSD-style license",
            license_url="https://example.com/demo/LICENSE",
        )
        proc, payload = self.run_checker(data)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(payload["ok"])

    def test_local_evidence_with_home_path_fails(self):
        data = base_inventory()
        data["components"][0]["evidence"] = [
            {"type": "local", "ref": "/" + "home" + "/alice/build/config.h", "note": "本机构建"}
        ]
        self.assert_fails_with(data, "个人用户目录")

    def test_missing_repo_evidence_path_fails(self):
        data = base_inventory()
        data["components"][0]["evidence"] = [
            {"type": "repo", "path": "docs/missing.h", "note": "不存在"}
        ]
        self.assert_fails_with(data, "文件不存在")

    def test_bad_generated_at_fails(self):
        data = base_inventory()
        data["generated_at"] = "2026/11/11"
        self.assert_fails_with(data, "generated_at")

    def test_bad_baseline_commit_fails(self):
        data = base_inventory()
        data["scope"]["baseline_commit"] = "not-a-sha"
        self.assert_fails_with(data, "baseline_commit")

    def test_missing_inventory_file_fails(self):
        proc, payload = self.run_checker(
            {}, inventory_path=self.root / "nope.yaml", json_output=True
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertFalse(payload["ok"])

    def test_unpinned_version_produces_warning_not_error(self):
        data = base_inventory()
        data["components"][0]["version_or_commit"] = "master 分支，未锁定 commit"
        proc, payload = self.run_checker(data)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(payload["ok"])
        self.assertTrue(any("未锁定" in w for w in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
