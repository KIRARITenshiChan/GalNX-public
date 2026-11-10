"""Tests for the reusable templates under examples/templates/.

The templates are the only sanctioned starting point for new ports, so they must
stay schema-valid, loadable by the real loaders, and free of developer-machine
absolute paths.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.engines.descriptor import check_descriptor_file, load_descriptor  # noqa: E402
from galnx.input.profiles import check_profile_file, load_profile  # noqa: E402
from galnx.manifest import load_and_validate  # noqa: E402

TEMPLATES = ROOT / "examples" / "templates"
MANIFEST = TEMPLATES / "minimal-manifest.yaml"
DESCRIPTOR = TEMPLATES / "external-engine-descriptor.yaml"
PROFILE = TEMPLATES / "input-profile.yaml"

# A drive letter followed by a separator, a UNC/personal home path, or one of
# the historical build roots used during development.
PERSONAL_PATH = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]|/home/|/Users/|\\\\[A-Za-z]")


class TemplateFilesTests(unittest.TestCase):
    def test_all_templates_exist(self):
        for path in (MANIFEST, DESCRIPTOR, PROFILE):
            self.assertTrue(path.is_file(), "missing template: %s" % path)

    def test_templates_contain_no_personal_paths(self):
        for path in sorted(TEMPLATES.glob("*.yaml")):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(
                PERSONAL_PATH.search(text),
                "template %s contains a personal absolute path" % path.name,
            )
            self.assertNotIn("Othergames", text)
            self.assertNotIn("galnx-build", text)

    def test_minimal_manifest_is_schema_valid(self):
        data, errors = load_and_validate(MANIFEST)
        self.assertIsNotNone(data)
        self.assertEqual(errors, [])

    def test_minimal_manifest_documents_placeholders(self):
        text = MANIFEST.read_text(encoding="utf-8")
        for token in ("CHANGE_ME", "schema_version: 1", "source_dir:", "build:"):
            self.assertIn(token, text)

    def test_external_descriptor_loads(self):
        descriptor = load_descriptor(DESCRIPTOR)
        self.assertEqual(descriptor.id, "my-engine")
        check = check_descriptor_file(DESCRIPTOR)
        self.assertTrue(check.ok, check.to_json())
        self.assertEqual(list(check.errors), [])

    def test_input_profile_loads(self):
        profile = load_profile(PROFILE)
        self.assertEqual(profile.name, "my-profile")
        check = check_profile_file(PROFILE)
        self.assertTrue(check.ok, check.to_json())
        self.assertEqual(list(check.errors), [])

    def test_pilot_manifests_are_marked_as_records(self):
        pilots = sorted((ROOT / "examples").glob("pilot0*.yaml"))
        self.assertGreaterEqual(len(pilots), 1)
        for path in pilots:
            head = path.read_text(encoding="utf-8")[:300]
            self.assertIn("not a reusable template", head, path.name)


if __name__ == "__main__":
    unittest.main()