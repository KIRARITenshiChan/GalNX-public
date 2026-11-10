"""Unit tests for galnx.package.nsp (P3-b self-contained NSP build driver).

The tests never invoke a real tool: every subprocess call goes through an injected
fake runner, and the tool/keyset/ELF/JPEG inputs are tiny synthesized files. They
also assert that keyset contents never leak into logs or provenance.
"""

import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.package import nsp as N  # noqa: E402
from galnx.package.metadata import PackageMetadata, PackageType  # noqa: E402

TITLE_ID = "010047410000a000"
TITLE_ID_UPPER = "010047410000A000"
ELF_BYTES = b"\x7fELF\x02\x01\x01" + b"\x00" * 64
FAKE_KEYSET = (
    "header_key = " + "ab" * 32 + "\n"
    "key_area_key_application_00 = " + "cd" * 16 + "\n"
)
SECRET_MARKER = "key-area-secret-value"


def make_jpeg(width=256, height=256):
    app0 = bytes([0xFF, 0xE0, 0x00, 0x10]) + b"JFIF" + bytes([0]) + bytes([1, 1, 0, 0, 1, 0, 1, 0, 0])
    sof = bytes([0xFF, 0xC0, 0x00, 0x11, 0x08,
                 (height >> 8) & 0xFF, height & 0xFF,
                 (width >> 8) & 0xFF, width & 0xFF, 0x03])
    sof += bytes([1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    return bytes([0xFF, 0xD8]) + app0 + sof + bytes([0xFF, 0xD9])


def nstool_nsp_text(title_id=TITLE_ID_UPPER, ncas=True):
    lines = ["[PartitionFs]", "Type: PFS0", "FileNum: 3"]
    if ncas:
        for content_type in ("Program", "Control", "Meta"):
            lines.extend([
                "[NCA Header]",
                "Content Type: %s" % content_type,
                "ProgID: 0x%s" % title_id.lower(),
                "Size: 0x1000",
                "NCA Header Main Signature: FAIL",
            ])
    return "\n".join(lines) + "\n"


def nstool_nca_text(content_type, title_id=TITLE_ID_UPPER):
    return "\n".join([
        "[NCA Header]",
        "Content Type: %s" % content_type,
        "ProgID: 0x%s" % title_id.lower(),
        "Size: 0x2000",
        "NCA Header Main Signature: FAIL",
    ]) + "\n"


class FakeRunner:
    """Callable runner matching build_nsp/verify_nsp's injected-runner contract."""

    def __init__(self, handler=None):
        self.handler = handler
        self.calls = []

    def __call__(self, argv, cwd, timeout_s):
        self.calls.append((list(argv), Path(cwd) if cwd is not None else None, timeout_s))
        if self.handler is None:
            return 0, "", ""
        return self.handler(argv, cwd, timeout_s)


def artifact_handler(title_id=TITLE_ID, filename=None, stdout="", stderr=""):
    def handler(argv, cwd, timeout_s):
        if "hacbrewpack" in Path(argv[0]).name.lower():
            out_dir = Path(cwd) / "hacbrewpack_nsp"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / ((filename or title_id) + ".nsp")).write_bytes(b"NSPDATA")
            return 0, stdout, stderr
        return 0, "", ""
    return handler


def tool_name(argv):
    return Path(argv[0]).name.lower().replace(".exe", "")


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.proj = self.root / "proj"
        self.proj.mkdir()
        self.inp = self.root / "in"
        self.inp.mkdir()
        self.elf = self.inp / "game.elf"
        self.elf.write_bytes(ELF_BYTES)
        self.icon = self.inp / "icon.jpg"
        self.icon.write_bytes(make_jpeg())
        self.romfs = self.root / "romfs"
        (self.romfs / "data").mkdir(parents=True)
        (self.romfs / "hello.txt").write_bytes(b"hello")
        (self.romfs / "data" / "a.bin").write_bytes(b"\x00" * 4)
        self.keyset = self.root / "keys" / "prod.keys"
        self.keyset.parent.mkdir()
        self.keyset.write_text(FAKE_KEYSET, encoding="utf-8")
        self.npdm_template = self.inp / "npdm.json"
        self.npdm_template.write_text(
            '{"title_id": "0100000000001000", "name": "demo"}', encoding="utf-8")
        self.tools = {}
        tool_dir = self.root / "tools"
        tool_dir.mkdir()
        for name in ("elf2nso", "npdmtool", "nacptool", "hacbrewpack", "nstool"):
            path = tool_dir / (name + ".exe")
            path.write_bytes(b"stub")
            self.tools[name] = path
        self.out = self.root / "out" / "demo.nsp"
        self.work = self.root / "work" / "demo"

    def tearDown(self):
        self._tmp.cleanup()

    def make_metadata(self, **overrides):
        values = dict(
            title_name="Demo",
            title_author="GalNX",
            version="1.0.0",
            title_id=TITLE_ID,
            package_type=PackageType.SELF_CONTAINED_NSP,
            icon_path=str(self.icon),
            romfs_dir=str(self.romfs),
            base_dir=self.proj,
        )
        values.update(overrides)
        return PackageMetadata(**values)

    def make_toolchain(self, **overrides):
        values = {name: str(path) for name, path in self.tools.items()}
        values.update(overrides)
        return N.NspToolchain(**values)

    def make_plan(self, **overrides):
        kwargs = dict(
            metadata=self.make_metadata(),
            elf=self.elf,
            romfs_dir=self.romfs,
            out_path=self.out,
            work_dir=self.work,
            keyset=str(self.keyset),
            toolchain=self.make_toolchain(),
            npdm_template=self.npdm_template,
        )
        kwargs.update(overrides)
        return N.plan_nsp_build(**kwargs)

    def error_texts(self, plan):
        return [issue.message for issue in plan.errors]

    def warning_texts(self, plan):
        return [issue.message for issue in plan.warnings]

    def keyset_ref(self):
        return N.KeysetRef(
            path=self.keyset,
            size=self.keyset.stat().st_size,
            sha256=N.sha256_file(self.keyset),
        )

    def cli_argv(self, extra=None):
        base = [
            "nsp",
            "--manifest", str(self.inp / "manifest.yaml"),
            "--elf", str(self.elf),
            "--romfs-dir", str(self.romfs),
            "--out", str(self.out),
            "--work", str(self.work),
            "--keyset", str(self.keyset),
            "--npdm-template", str(self.npdm_template),
        ]
        for name, path in self.tools.items():
            base.extend(["--" + name, str(path)])
        base.extend(extra or [])
        return base

    @staticmethod
    def cli_parser():
        parser = argparse.ArgumentParser(prog="galnx")
        subparsers = parser.add_subparsers(dest="command")
        N.register(subparsers)
        return parser


class PlanTests(Base):
    def test_valid_plan_has_four_ordered_steps(self):
        plan = self.make_plan()
        self.assertTrue(plan.ok, self.error_texts(plan))
        self.assertEqual(plan.title_id, TITLE_ID_UPPER)
        self.assertEqual([step.name for step in plan.steps],
                         ["elf2nso", "npdm", "nacp", "hacbrewpack"])
        self.assertIsNotNone(plan.inventory)
        self.assertEqual(plan.inventory.files, 2)
        self.assertEqual(plan.inventory.dirs, 1)
        self.assertEqual(plan.inventory.total_bytes, 9)
        self.assertEqual(plan.keyset.mode, "real")
        self.assertEqual(len(plan.keyset.sha256), 64)
        self.assertEqual(plan.tool_sources["hacbrewpack"], "explicit")

        elf2nso = plan.steps[0]
        self.assertEqual(elf2nso.argv, [
            str(self.tools["elf2nso"]), str(self.elf), str(self.work / "exefs" / "main")])
        npdm = plan.steps[1]
        self.assertEqual(npdm.argv, [
            str(self.tools["npdmtool"]), str(self.work / "npdm.json"),
            str(self.work / "exefs" / "main.npdm")])
        nacp = plan.steps[2]
        self.assertEqual(nacp.argv[0], str(self.tools["nacptool"]))
        self.assertIn("--titleid=" + TITLE_ID_UPPER, nacp.argv)
        hack = plan.steps[3]
        self.assertEqual(hack.argv, [
            str(self.tools["hacbrewpack"]), "--nologo", "-k", str(self.keyset),
            "--romfsdir", str(self.romfs)])
        for step in plan.steps:
            self.assertEqual(step.cwd, self.work)

    def test_non_base_title_id_is_rejected(self):
        # The pilot A2 build used 010047410000b0b4, which is not a valid
        # application base id (base ids are 0x2000-aligned). The driver must
        # reject it so a forked/rebuilt NSP cannot silently reuse it.
        plan = self.make_plan(metadata=self.make_metadata(title_id="010047410000b0b4"))
        self.assertFalse(plan.ok)
        self.assertEqual(plan.steps, [])
        self.assertTrue(any("add-on content id" in text
                            for text in self.error_texts(plan)),
                        self.error_texts(plan))

    def test_keyset_is_mandatory_and_explicit(self):
        plan = self.make_plan(keyset=None)
        self.assertFalse(plan.ok)
        self.assertEqual(plan.steps, [])
        self.assertTrue(any("keyset is required and must be explicit" in text
                            for text in self.error_texts(plan)))

    def test_synthetic_keyset_is_a_warning_only(self):
        plan = self.make_plan(keyset="synthetic")
        self.assertTrue(plan.ok, self.error_texts(plan))
        self.assertTrue(plan.keyset.synthetic)
        self.assertEqual(plan.keyset.mode, "synthetic")
        self.assertEqual(plan.synthetic_keys_path, self.work / "synthetic.keys")
        self.assertEqual(plan.steps[-1].argv[3], str(self.work / "synthetic.keys"))
        self.assertTrue(any("synthetic keyset" in text for text in self.warning_texts(plan)))
        checks = N._plan_checks(plan)
        mode_checks = [check for check in checks if check.id == "nsp.keyset.mode"]
        self.assertEqual([check.status for check in mode_checks], ["warn"])

    def test_plan_checks_summarize_success(self):
        plan = self.make_plan()
        checks = N._plan_checks(plan)
        by_id = {check.id: check for check in checks}
        self.assertEqual(by_id["nsp.plan"].status, "ok")
        self.assertIn("4 steps", by_id["nsp.plan"].detail)
        self.assertEqual(by_id["nsp.romfs"].status, "ok")
        self.assertEqual(by_id["nsp.keyset.mode"].status, "ok")
        for name in ("elf2nso", "npdmtool", "nacptool", "hacbrewpack", "nstool"):
            self.assertEqual(by_id["nsp.tool." + name].status, "ok")

    def test_elf_is_required(self):
        plan = self.make_plan(elf=None)
        self.assertFalse(plan.ok)
        self.assertTrue(any("elf is required" in text for text in self.error_texts(plan)))

    def test_non_elf_input_is_rejected(self):
        bad = self.inp / "not-elf.bin"
        bad.write_bytes(b"NRO0" + b"\x00" * 16)
        plan = self.make_plan(elf=bad)
        self.assertFalse(plan.ok)
        self.assertTrue(any("not an ELF image" in text for text in self.error_texts(plan)))

    def test_forwarder_package_type_is_out_of_scope(self):
        metadata = self.make_metadata(package_type=PackageType.FORWARDER_NSP)
        plan = N.plan_nsp_build(
            metadata, elf=self.elf, keyset=str(self.keyset), toolchain=self.make_toolchain(),
            out_path=self.out, work_dir=self.work, npdm_template=self.npdm_template)
        self.assertFalse(plan.ok)
        self.assertEqual(plan.steps, [])
        self.assertTrue(any("self-contained NSP only" in text
                            for text in self.error_texts(plan)))

    def test_out_path_must_be_nsp(self):
        plan = self.make_plan(out_path=self.root / "out" / "demo.zip")
        self.assertFalse(plan.ok)
        self.assertTrue(any("must end with .nsp" in text for text in self.error_texts(plan)))

    def test_work_dir_inside_romfs_is_rejected(self):
        plan = self.make_plan(work_dir=self.romfs / "staging")
        self.assertFalse(plan.ok)
        self.assertTrue(any("work_dir is inside romfs_dir" in text
                            for text in self.error_texts(plan)))

    def test_keyset_inside_romfs_is_rejected(self):
        packaged = self.romfs / "prod.keys"
        packaged.write_text(FAKE_KEYSET, encoding="utf-8")
        plan = self.make_plan(keyset=packaged)
        self.assertFalse(plan.ok)
        self.assertTrue(any("prod.keys would be packaged" in text
                            for text in self.error_texts(plan)))

    def test_existing_out_file_only_warns(self):
        self.out.parent.mkdir(parents=True)
        self.out.write_bytes(b"old")
        plan = self.make_plan()
        self.assertTrue(plan.ok, self.error_texts(plan))
        self.assertTrue(any("already exists and will be overwritten" in text
                            for text in self.warning_texts(plan)))

    def test_prebuilt_npdm_and_nacp_skip_steps(self):
        npdm = self.inp / "main.npdm"
        npdm.write_bytes(b"META" + b"\x00" * 64)
        nacp = self.inp / "control.nacp"
        nacp.write_bytes(b"\x00" * 0x4000)
        plan = self.make_plan(npdm=npdm, nacp=nacp)
        self.assertTrue(plan.ok, self.error_texts(plan))
        self.assertEqual([step.name for step in plan.steps], ["elf2nso", "hacbrewpack"])

    def test_bad_nacp_size_is_a_warning(self):
        nacp = self.inp / "short.nacp"
        nacp.write_bytes(b"\x00" * 16)
        plan = self.make_plan(nacp=nacp)
        self.assertTrue(plan.ok, self.error_texts(plan))
        self.assertTrue(any("expected 16384" in text for text in self.warning_texts(plan)))

    def test_npdm_template_without_placeholder_warns(self):
        template = self.inp / "no-placeholder.json"
        template.write_text('{"title_id": "0100000000000000"}', encoding="utf-8")
        plan = self.make_plan(npdm_template=template)
        self.assertTrue(plan.ok, self.error_texts(plan))
        self.assertTrue(any("placeholder" in text for text in self.warning_texts(plan)))

    def test_missing_npdm_template_is_an_error(self):
        plan = self.make_plan(npdm_template=self.inp / "missing.json")
        self.assertFalse(plan.ok)
        self.assertTrue(any("npdm template not found" in text
                            for text in self.error_texts(plan)))

    def test_missing_tools_are_reported(self):
        with mock.patch.object(N.shutil, "which", return_value=None):
            plan = N.plan_nsp_build(
                self.make_metadata(), elf=self.elf, romfs_dir=self.romfs,
                out_path=self.out, work_dir=self.work, keyset=str(self.keyset),
                toolchain=N.NspToolchain(), npdm_template=self.npdm_template)
        self.assertFalse(plan.ok)
        text = "\n".join(self.error_texts(plan))
        for name in ("elf2nso", "hacbrewpack", "npdmtool", "nacptool"):
            self.assertIn("%s not found" % name, text)
        self.assertTrue(any("nstool not found" in item
                            for item in self.warning_texts(plan)))

    def test_bad_icon_dimensions_are_rejected(self):
        small = self.inp / "small.jpg"
        small.write_bytes(make_jpeg(128, 128))
        plan = self.make_plan(metadata=self.make_metadata(icon_path=str(small)))
        self.assertFalse(plan.ok)
        self.assertTrue(any("256" in text and "icon" in text.lower()
                            for text in self.error_texts(plan)))

    def test_invalid_title_id_is_rejected(self):
        plan = self.make_plan(metadata=self.make_metadata(title_id="zzzz"))
        self.assertFalse(plan.ok)
        self.assertEqual(plan.title_id, "ZZZZ")
        self.assertTrue(self.error_texts(plan))

    def test_low_disk_space_is_an_error(self):
        fake_usage = SimpleNamespace(total=0, used=0, free=1024)
        with mock.patch.object(N.shutil, "disk_usage", return_value=fake_usage):
            plan = self.make_plan()
        self.assertFalse(plan.ok)
        self.assertTrue(any("free" in text and "estimated peak" in text
                            for text in self.error_texts(plan)))

    def test_default_out_and_work_locations(self):
        plan = N.plan_nsp_build(
            self.make_metadata(), elf=self.elf, romfs_dir=self.romfs,
            keyset=str(self.keyset), toolchain=self.make_toolchain(),
            npdm_template=self.npdm_template)
        self.assertTrue(plan.ok, self.error_texts(plan))
        self.assertEqual(plan.out_path.parent, self.proj / "build" / "nsp")
        self.assertTrue(plan.out_path.name.endswith("-" + TITLE_ID_UPPER + ".nsp"))
        self.assertEqual(plan.work_dir,
                         self.proj / "build" / "nsp" / ("work-" + TITLE_ID_UPPER))

    def test_inventory_and_digest(self):
        inventory = N.inventory_romfs(self.romfs)
        self.assertEqual((inventory.files, inventory.dirs, inventory.total_bytes), (2, 1, 9))
        self.assertGreaterEqual(inventory.max_path_len, len(str(self.romfs / "data" / "a.bin")))
        digest = N.digest_romfs(self.romfs)
        self.assertEqual(digest, N.digest_romfs(self.romfs))
        (self.romfs / "hello.txt").write_bytes(b"hello!")
        self.assertNotEqual(digest, N.digest_romfs(self.romfs))


class BuildTests(Base):
    def test_build_success_copies_artifact_and_writes_logs(self):
        runner = FakeRunner(artifact_handler())
        plan = self.make_plan()
        result = N.build_nsp(plan, runner=runner)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(len(runner.calls), 4)
        self.assertEqual([call[0] for call in runner.calls],
                         [step.argv for step in plan.steps])
        for argv, cwd, _timeout in runner.calls:
            self.assertIsInstance(argv, list)
            self.assertEqual(cwd, self.work)
        self.assertEqual(result.artifact["size"], 7)
        self.assertEqual(result.artifact["sha256"], N.sha256_file(self.out))
        self.assertTrue(self.out.is_file())
        self.assertEqual(self.out.read_bytes(), b"NSPDATA")
        logs = sorted(path.name for path in (self.work / "logs").glob("*.log"))
        self.assertEqual(logs, ["elf2nso.log", "hacbrewpack.log", "nacp.log", "npdm.log"])
        self.assertIn("# step: elf2nso", (self.work / "logs" / "elf2nso.log").read_text(encoding="utf-8"))
        step_names = [step.name for step in result.steps]
        self.assertEqual(step_names, ["stage-icon", "elf2nso", "npdm", "nacp", "hacbrewpack"])
        self.assertFalse(result.error)

    def test_logs_redact_key_material(self):
        runner = FakeRunner(artifact_handler(
            stdout="Key area key 2: " + SECRET_MARKER + "\nordinary line\n"))
        plan = self.make_plan()
        result = N.build_nsp(plan, runner=runner)
        self.assertTrue(result.ok, result.error)
        log_text = (self.work / "logs" / "hacbrewpack.log").read_text(encoding="utf-8")
        self.assertNotIn(SECRET_MARKER, log_text)
        self.assertIn("<redacted: key material line>", log_text)
        self.assertIn("ordinary line", log_text)
        self.assertNotIn(SECRET_MARKER, result.steps[-1].stdout_tail)

    def test_rebuild_clears_stale_staging(self):
        (self.work / "exefs").mkdir(parents=True, exist_ok=True)
        (self.work / "exefs" / "stale.bin").write_bytes(b"stale")
        (self.work / "control").mkdir(parents=True, exist_ok=True)
        (self.work / "control" / "stale.nacp").write_bytes(b"stale")
        runner = FakeRunner(artifact_handler())
        result = N.build_nsp(self.make_plan(), runner=runner)
        self.assertTrue(result.ok, result.error)
        self.assertFalse((self.work / "exefs" / "stale.bin").exists())
        self.assertFalse((self.work / "control" / "stale.nacp").exists())
        self.assertTrue((self.work / "control" / "icon_AmericanEnglish.dat").is_file())

    def test_failure_stops_after_first_failing_step(self):
        def handler(argv, cwd, timeout_s):
            if tool_name(argv) == "elf2nso":
                return 1, "", "boom"
            return 0, "", ""
        runner = FakeRunner(handler)
        result = N.build_nsp(self.make_plan(), runner=runner)
        self.assertFalse(result.ok)
        self.assertIn("exit code 1", result.error)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(result.steps[-1].name, "elf2nso")
        self.assertEqual(result.steps[-1].exit_code, 1)

    def test_timeout_is_reported(self):
        def handler(argv, cwd, timeout_s):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout_s)
        runner = FakeRunner(handler)
        result = N.build_nsp(self.make_plan(), runner=runner)
        self.assertFalse(result.ok)
        self.assertIn("timed out after", result.error)

    def test_missing_artifact_is_an_error(self):
        result = N.build_nsp(self.make_plan(), runner=FakeRunner())
        self.assertFalse(result.ok)
        self.assertIn("did not produce", result.error)

    def test_single_candidate_artifact_is_accepted(self):
        runner = FakeRunner(artifact_handler(filename="other"))
        result = N.build_nsp(self.make_plan(), runner=runner)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(Path(result.artifact["produced_by"]).name, "other.nsp")

    def test_synthetic_keyset_file_is_generated(self):
        runner = FakeRunner(artifact_handler())
        plan = self.make_plan(keyset="synthetic")
        result = N.build_nsp(plan, runner=runner)
        self.assertTrue(result.ok, result.error)
        synthetic = plan.synthetic_keys_path
        self.assertTrue(synthetic.is_file())
        text = synthetic.read_text(encoding="utf-8")
        self.assertIn("NOT A REAL KEYSET", text)
        self.assertIn("NOT INSTALLABLE", text)

    def test_invalid_plan_is_not_built(self):
        plan = self.make_plan(keyset=None)
        runner = FakeRunner()
        result = N.build_nsp(plan, runner=runner)
        self.assertFalse(result.ok)
        self.assertIn("build plan is invalid", result.error)
        self.assertEqual(runner.calls, [])


class VerifyTests(Base):
    def setUp(self):
        super().setUp()
        self.nsp = self.root / "out" / "demo.nsp"
        self.nsp.parent.mkdir(parents=True)
        self.nsp.write_bytes(b"NSPDATA")
        self.nstool = self.tools["nstool"]

    def test_verify_unsigned_nsp_passes_with_signature_warning(self):
        runner = FakeRunner(lambda argv, cwd, timeout_s: (0, nstool_nsp_text(), ""))
        result = N.verify_nsp(self.nsp, self.nstool, keyset=self.keyset_ref(),
                              expected_title_id=TITLE_ID, runner=runner)
        self.assertTrue(result.ok, [check.detail for check in result.checks])
        self.assertEqual(result.ncas, 3)
        self.assertEqual(len(runner.calls), 1)
        argv = runner.calls[0][0]
        self.assertEqual(argv[0], str(self.nstool))
        self.assertEqual(argv[1], "-y")
        self.assertEqual(argv[2:4], ["-k", str(self.keyset)])
        self.assertEqual(argv[-1], str(self.nsp))
        statuses = {check.id: check.status for check in result.checks}
        self.assertEqual(statuses["verify.signature"], "warn")
        self.assertEqual(statuses["verify.summary"], "ok")
        self.assertNotIn("fail", [check.status for check in result.checks])
        self.assertEqual(result.artifact["sha256"], N.sha256_file(self.nsp))

    def test_verify_without_keyset_is_limited_but_ok(self):
        runner = FakeRunner(lambda argv, cwd, timeout_s: (0, nstool_nsp_text(ncas=False), ""))
        result = N.verify_nsp(self.nsp, self.nstool, runner=runner)
        self.assertTrue(result.ok, [check.detail for check in result.checks])
        self.assertEqual(result.ncas, 0)
        self.assertEqual(len(runner.calls), 1)
        self.assertNotIn("-k", runner.calls[0][0])
        statuses = {check.id: check.status for check in result.checks}
        self.assertEqual(statuses["verify.keyset"], "warn")
        self.assertEqual(statuses["verify.ncas"], "warn")

    def test_verify_synthetic_keyset_skips_nca_layer(self):
        runner = FakeRunner(lambda argv, cwd, timeout_s: (0, nstool_nsp_text(ncas=False), ""))
        result = N.verify_nsp(self.nsp, self.nstool, keyset=N.KeysetRef(synthetic=True),
                              work_dir=self.work, runner=runner)
        self.assertTrue(result.ok, [check.detail for check in result.checks])
        self.assertEqual(len(runner.calls), 1)
        statuses = {check.id: check.status for check in result.checks}
        self.assertEqual(statuses["verify.keyset"], "skip")

    def test_verify_extracts_ncas_when_work_dir_given(self):
        class ExtractionRunner:
            def __init__(self):
                self.calls = []
                self.nca_index = 0

            def __call__(self, argv, cwd, timeout_s):
                self.calls.append(list(argv))
                if "-x" in argv:
                    nca_dir = Path(argv[argv.index("-x") + 1])
                    nca_dir.mkdir(parents=True, exist_ok=True)
                    for name in ("00.nca", "01.nca", "02.nca"):
                        (nca_dir / name).write_bytes(b"nca")
                    return 0, "extracted", ""
                target = Path(argv[-1])
                if target.suffix.lower() == ".nca":
                    content_type = ("Program", "Control", "Meta")[self.nca_index % 3]
                    self.nca_index += 1
                    return 0, nstool_nca_text(content_type), ""
                return 0, nstool_nsp_text(ncas=False), ""

        runner = ExtractionRunner()
        result = N.verify_nsp(self.nsp, self.nstool, keyset=self.keyset_ref(),
                              expected_title_id=TITLE_ID, work_dir=self.work, runner=runner)
        self.assertTrue(result.ok, [check.detail for check in result.checks])
        self.assertEqual(result.ncas, 3)
        self.assertEqual(len(runner.calls), 5)
        self.assertTrue(any("-x" in call for call in runner.calls))
        statuses = {check.id: check.status for check in result.checks}
        self.assertEqual(statuses["nstool.progid.expected"], "ok")
        self.assertEqual(statuses["nstool.nca.type.program"], "ok")

    def test_verify_detects_title_id_mismatch(self):
        runner = FakeRunner(lambda argv, cwd, timeout_s: (0, nstool_nsp_text(), ""))
        result = N.verify_nsp(self.nsp, self.nstool, keyset=self.keyset_ref(),
                              expected_title_id="010047410000B0B5", runner=runner)
        self.assertFalse(result.ok)
        statuses = {check.id: check.status for check in result.checks}
        self.assertEqual(statuses["nstool.progid.expected"], "fail")
        self.assertEqual(statuses["verify.summary"], "fail")

    def test_verify_reports_nstool_failure(self):
        runner = FakeRunner(lambda argv, cwd, timeout_s: (2, "", "boom"))
        result = N.verify_nsp(self.nsp, self.nstool, runner=runner)
        self.assertFalse(result.ok)
        checks = {check.id: check.status for check in result.checks}
        self.assertEqual(checks["verify.nstool.nsp"], "fail")

    def test_verify_missing_nsp_or_nstool(self):
        missing = self.root / "missing.nsp"
        result = N.verify_nsp(missing, self.nstool, runner=FakeRunner())
        self.assertFalse(result.ok)
        self.assertEqual(result.checks[0].id, "verify.nsp")
        result = N.verify_nsp(self.nsp, self.root / "missing-nstool.exe", runner=FakeRunner())
        self.assertFalse(result.ok)
        self.assertEqual(result.checks[0].id, "verify.nstool")

    def test_verify_extraction_failure_is_a_warning(self):
        def handler(argv, cwd, timeout_s):
            if "-x" in argv:
                return 1, "", "cannot extract"
            return 0, nstool_nsp_text(ncas=False), ""
        runner = FakeRunner(handler)
        result = N.verify_nsp(self.nsp, self.nstool, keyset=self.keyset_ref(),
                              work_dir=self.work, runner=runner)
        self.assertTrue(result.ok, [check.detail for check in result.checks])
        statuses = {check.id: check.status for check in result.checks}
        self.assertEqual(statuses["verify.nstool.extract"], "warn")


class ProvenanceTests(Base):
    def test_dry_run_provenance_records_inputs_without_keyset_contents(self):
        plan = self.make_plan()
        target = self.out.with_suffix(".nsp.provenance.json")
        written = N.write_provenance(path=target, plan=plan)
        self.assertEqual(written, target)
        text = target.read_text(encoding="utf-8")
        payload = json.loads(text)
        self.assertEqual(payload["schema"], "galnx-nsp-provenance")
        self.assertEqual(payload["schema_version"], 1)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["title_id"], TITLE_ID_UPPER)
        self.assertEqual(payload["inputs"]["elf"]["sha256"], N.sha256_file(self.elf))
        self.assertEqual(payload["inputs"]["elf"]["size"], len(ELF_BYTES))
        self.assertEqual(payload["inputs"]["romfs"]["files"], 2)
        self.assertEqual(payload["inputs"]["romfs"]["sha256"], N.digest_romfs(self.romfs))
        self.assertEqual(payload["inputs"]["icon"]["size"], len(make_jpeg()))
        self.assertEqual(payload["keyset"]["mode"], "real")
        self.assertEqual(payload["keyset"]["sha256"], plan.keyset.sha256)
        self.assertEqual(payload["keyset"]["size"], self.keyset.stat().st_size)
        self.assertNotIn(FAKE_KEYSET.split("\n")[0].split(" = ")[1], text)
        self.assertNotIn("ab" * 32, text)
        self.assertEqual(payload["tools"]["hacbrewpack"]["source"], "explicit")
        self.assertEqual(len(payload["tools"]["hacbrewpack"]["sha256"]), 64)
        self.assertEqual(len(payload["commands"]), 4)
        self.assertIsNone(payload["build"])
        self.assertIsNone(payload["artifact"])
        self.assertIsNone(payload["verify"])
        self.assertIn("python", payload["environment"])

    def test_provenance_after_build_and_verify(self):
        build_runner = FakeRunner(artifact_handler())
        result = N.build_nsp(self.make_plan(), runner=build_runner)
        self.assertTrue(result.ok, result.error)
        verify_runner = FakeRunner(lambda argv, cwd, timeout_s: (0, nstool_nsp_text(), ""))
        verify = N.verify_nsp(self.out, self.tools["nstool"], keyset=self.keyset_ref(),
                              expected_title_id=TITLE_ID, runner=verify_runner)
        self.assertTrue(verify.ok)
        target = self.root / "provenance.json"
        N.write_provenance(path=target, plan=self.make_plan(), result=result, verify=verify)
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertFalse(payload["dry_run"])
        self.assertTrue(payload["build"]["ok"])
        self.assertEqual(payload["artifact"]["sha256"], N.sha256_file(self.out))
        self.assertEqual(payload["build"]["steps"][-1]["name"], "hacbrewpack")
        self.assertTrue(payload["verify"]["ok"])
        self.assertEqual(payload["verify"]["ncas"], 3)

    def test_provenance_can_skip_romfs_digest(self):
        target = self.root / "provenance.json"
        N.write_provenance(path=target, plan=self.make_plan(), romfs_digest=False)
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["inputs"]["romfs"]["sha256"], "")


class CliTests(Base):
    def parse(self, extra=None):
        return self.cli_parser().parse_args(self.cli_argv(extra))

    def test_register_wires_arguments(self):
        parser = self.cli_parser()
        args = parser.parse_args([
            "nsp", "--manifest", "m.yaml", "--keyset", "synthetic", "--elf", "game.elf"])
        self.assertIs(args.func, N.cmd_nsp)
        self.assertFalse(args.build)
        self.assertFalse(args.dry_run)
        self.assertFalse(args.json)
        self.assertEqual(args.step_timeout, 1800.0)

    def test_dry_run_json_emits_plan(self):
        args = self.parse(["--json"])
        buffer = io.StringIO()
        with mock.patch.object(N, "_load_metadata", return_value=(self.make_metadata(), [])):
            with contextlib.redirect_stdout(buffer):
                code = N.cmd_nsp(args)
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["tool"], "package nsp")
        self.assertEqual(payload["mode"], "plan")
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["plan"]["steps"]), 4)
        self.assertEqual(payload["plan"]["romfs"]["files"], 2)
        ids = {check["id"]: check for check in payload["checks"]}
        self.assertEqual(ids["nsp.plan"]["status"], "ok")

    def test_manifest_errors_exit_2(self):
        args = self.parse(["--json"])
        buffer = io.StringIO()
        with mock.patch.object(N, "_load_metadata", return_value=(None, ["bad manifest"])):
            with contextlib.redirect_stdout(buffer):
                code = N.cmd_nsp(args)
        self.assertEqual(code, 2)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"], ["bad manifest"])

    def test_build_and_dry_run_are_mutually_exclusive(self):
        args = self.parse(["--build", "--dry-run"])
        buffer = io.StringIO()
        with mock.patch.object(N, "_load_metadata", return_value=(self.make_metadata(), [])):
            with contextlib.redirect_stderr(buffer):
                code = N.cmd_nsp(args)
        self.assertEqual(code, 2)
        self.assertIn("mutually exclusive", buffer.getvalue())

    def test_build_success_writes_provenance(self):
        args = self.parse(["--build", "--json", "--no-verify"])
        self.out.parent.mkdir(parents=True)
        self.out.write_bytes(b"NSPDATA")
        result = N.BuildResult(
            ok=True, out_path=self.out, work_dir=self.work, steps=[],
            artifact={"path": str(self.out), "size": 7,
                      "sha256": N.sha256_file(self.out), "produced_by": str(self.out)})
        buffer = io.StringIO()
        with mock.patch.object(N, "_load_metadata", return_value=(self.make_metadata(), [])):
            with mock.patch.object(N, "build_nsp", return_value=result):
                with contextlib.redirect_stdout(buffer):
                    code = N.cmd_nsp(args)
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["mode"], "build")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["build"]["artifact"]["size"], 7)
        provenance = Path(payload["provenance"])
        self.assertTrue(provenance.is_file())
        self.assertFalse(json.loads(provenance.read_text(encoding="utf-8"))["dry_run"])

    def test_build_failure_exits_1(self):
        args = self.parse(["--build", "--json", "--no-verify"])
        result = N.BuildResult(ok=False, out_path=self.out, work_dir=self.work, steps=[],
                               error="step elf2nso failed with exit code 1")
        buffer = io.StringIO()
        with mock.patch.object(N, "_load_metadata", return_value=(self.make_metadata(), [])):
            with mock.patch.object(N, "build_nsp", return_value=result):
                with contextlib.redirect_stdout(buffer):
                    code = N.cmd_nsp(args)
        self.assertEqual(code, 1)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])
        self.assertIn("exit code 1", payload["build"]["error"])


class VerifyCliTests(Base):
    """Tests for "galnx package nsp verify" (cmd_nsp_verify + provenance cross-check)."""

    def verify_argv(self, extra=None):
        argv = [
            "nsp", "verify",
            "--nsp", str(self.out),
            "--manifest", str(self.inp / "manifest.yaml"),
            "--nstool", str(self.tools["nstool"]),
        ]
        argv.extend(extra or [])
        return argv

    def parse_verify(self, extra=None):
        return self.cli_parser().parse_args(self.verify_argv(extra))

    def make_nsp(self):
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_bytes(b"NSPDATA")
        return self.out

    def fake_verify(self, ok=True):
        return N.VerifyResult(
            ok=ok, nsp=self.out, nstool=self.tools["nstool"],
            checks=[N.Check("verify.summary", "nstool verification",
                            "ok" if ok else "fail", "fake nstool result")],
            ncas=3, artifact={"path": str(self.out), "size": 7, "sha256": "a" * 64})

    def run_verify(self, args, fake):
        buffer = io.StringIO()
        with mock.patch.object(N, "_load_metadata", return_value=(self.make_metadata(), [])):
            with mock.patch.object(N, "verify_nsp", return_value=fake) as patched:
                with contextlib.redirect_stdout(buffer):
                    code = N.cmd_nsp_verify(args)
        return code, buffer.getvalue(), patched

    def provenance_payload(self, nsp=None, **overrides):
        nsp = nsp or self.make_nsp()
        payload = {
            "schema": "galnx-nsp-provenance",
            "schema_version": 1,
            "dry_run": False,
            "title_id": TITLE_ID_UPPER,
            "artifact": {
                "path": str(nsp),
                "size": nsp.stat().st_size,
                "sha256": N.sha256_file(nsp),
            },
            "keyset": {
                "mode": "real",
                "path": str(self.keyset),
                "size": self.keyset.stat().st_size,
                "sha256": N.sha256_file(self.keyset),
                "note": "explicitly supplied keyset",
            },
        }
        payload.update(overrides)
        return payload

    def write_provenance(self, payload, name="provenance.json"):
        path = self.root / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    # -- parser wiring -----------------------------------------------------

    def test_register_wires_verify_arguments(self):
        args = self.parse_verify()
        self.assertIs(args.func, N.cmd_nsp_verify)
        self.assertEqual(args.nsp_command, "verify")
        self.assertEqual(args.step_timeout, 300.0)
        self.assertFalse(args.json)
        self.assertIsNone(args.provenance)
        self.assertIsNone(args.keyset)
        self.assertIsNone(args.expect_title_id)

    def test_plan_command_still_parses_without_verify(self):
        args = self.cli_parser().parse_args(["nsp", "--manifest", "m.yaml", "--keyset", "synthetic"])
        self.assertIs(args.func, N.cmd_nsp)
        self.assertEqual(args.nsp_command, None)

    # -- verify command ----------------------------------------------------

    def test_verify_ok_emits_json(self):
        self.make_nsp()
        args = self.parse_verify(["--json"])
        code, output, patched = self.run_verify(args, self.fake_verify(ok=True))
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["tool"], "package nsp")
        self.assertEqual(payload["mode"], "verify")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["expected_title_id"], TITLE_ID_UPPER)
        self.assertEqual(payload["nstool"]["source"], "explicit")
        self.assertIsNone(payload["provenance"])
        self.assertEqual(payload["verify"]["ncas"], 3)
        kwargs = patched.call_args.kwargs
        self.assertEqual(kwargs["expected_title_id"], TITLE_ID_UPPER)
        self.assertFalse(kwargs["keyset"].synthetic)
        self.assertIsNone(kwargs["keyset"].path)
        # the default work dir is a temporary directory removed after the run
        self.assertFalse(Path(payload["work_dir"]).exists())

    def test_verify_failure_exits_1(self):
        self.make_nsp()
        args = self.parse_verify(["--json"])
        code, output, _ = self.run_verify(args, self.fake_verify(ok=False))
        self.assertEqual(code, 1)
        payload = json.loads(output)
        self.assertFalse(payload["ok"])
        ids = {check["id"]: check for check in payload["checks"]}
        self.assertEqual(ids["verify.summary"]["status"], "fail")

    def test_verify_missing_nsp_exits_2(self):
        args = self.parse_verify(["--json"])
        code, output, patched = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 2)
        self.assertEqual(patched.call_count, 0)
        payload = json.loads(output)
        self.assertFalse(payload["ok"])
        self.assertIn("NSP not found", payload["errors"][0])

    def test_verify_manifest_errors_exit_2(self):
        self.make_nsp()
        args = self.parse_verify(["--json"])
        buffer = io.StringIO()
        with mock.patch.object(N, "_load_metadata", return_value=(None, ["bad manifest"])):
            with contextlib.redirect_stdout(buffer):
                code = N.cmd_nsp_verify(args)
        self.assertEqual(code, 2)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["errors"], ["bad manifest"])

    def test_verify_missing_nstool_exits_2(self):
        self.make_nsp()
        args = self.parse_verify(["--nstool", str(self.root / "missing-nstool.exe"), "--json"])
        buffer = io.StringIO()
        with mock.patch.object(N, "_load_metadata", return_value=(self.make_metadata(), [])):
            with contextlib.redirect_stdout(buffer):
                code = N.cmd_nsp_verify(args)
        self.assertEqual(code, 2)
        payload = json.loads(buffer.getvalue())
        self.assertIn("nstool not found", payload["errors"][0])

    def test_verify_invalid_expect_title_id_exits_2(self):
        self.make_nsp()
        args = self.parse_verify(["--expect-title-id", "not-a-title-id", "--json"])
        buffer = io.StringIO()
        with mock.patch.object(N, "_load_metadata", return_value=(self.make_metadata(), [])):
            with contextlib.redirect_stdout(buffer):
                code = N.cmd_nsp_verify(args)
        self.assertEqual(code, 2)
        payload = json.loads(buffer.getvalue())
        self.assertIn("invalid expected title id", payload["errors"][0])

    def test_verify_expect_title_id_override(self):
        self.make_nsp()
        args = self.parse_verify(["--expect-title-id", TITLE_ID.lower(), "--json"])
        code, output, patched = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 0)
        self.assertEqual(patched.call_args.kwargs["expected_title_id"], TITLE_ID_UPPER)
        self.assertEqual(json.loads(output)["expected_title_id"], TITLE_ID_UPPER)

    def test_verify_synthetic_keyset_is_forwarded(self):
        self.make_nsp()
        args = self.parse_verify(["--keyset", "synthetic", "--json"])
        code, output, patched = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 0)
        keyset = patched.call_args.kwargs["keyset"]
        self.assertTrue(keyset.synthetic)
        self.assertEqual(json.loads(output)["keyset"]["mode"], "synthetic")

    def test_verify_real_keyset_is_hashed(self):
        self.make_nsp()
        args = self.parse_verify(["--keyset", str(self.keyset), "--json"])
        code, output, patched = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 0)
        keyset = patched.call_args.kwargs["keyset"]
        self.assertEqual(keyset.path, self.keyset)
        self.assertEqual(keyset.size, self.keyset.stat().st_size)
        self.assertEqual(keyset.sha256, N.sha256_file(self.keyset))
        payload = json.loads(output)
        self.assertEqual(payload["keyset"]["sha256"], N.sha256_file(self.keyset))
        self.assertNotIn("header_key", output)

    def test_verify_text_output(self):
        self.make_nsp()
        args = self.parse_verify()
        code, output, _ = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 0)
        self.assertIn("verifying NSP:", output)
        self.assertIn("expected title id: %s" % TITLE_ID_UPPER, output)
        self.assertIn("checks:", output)

    # -- provenance cross-check -------------------------------------------

    def test_verify_provenance_match_exits_0(self):
        nsp = self.make_nsp()
        provenance = self.write_provenance(self.provenance_payload(nsp=nsp))
        args = self.parse_verify(["--keyset", str(self.keyset),
                                  "--provenance", str(provenance), "--json"])
        code, output, _ = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["provenance"]["path"], str(provenance))
        ids = {check["id"]: check for check in payload["checks"]}
        self.assertEqual(ids["verify.provenance.artifact"]["status"], "ok")
        self.assertEqual(ids["verify.provenance.keyset"]["status"], "ok")
        self.assertEqual(ids["verify.provenance.schema"]["status"], "ok")

    def test_verify_provenance_artifact_mismatch_exits_1(self):
        nsp = self.make_nsp()
        payload = self.provenance_payload(nsp=nsp)
        payload["artifact"]["sha256"] = "0" * 64
        provenance = self.write_provenance(payload)
        args = self.parse_verify(["--keyset", str(self.keyset),
                                  "--provenance", str(provenance), "--json"])
        code, output, _ = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 1)
        result = json.loads(output)
        self.assertFalse(result["ok"])
        ids = {check["id"]: check for check in result["checks"]}
        self.assertEqual(ids["verify.provenance.artifact"]["status"], "fail")
        self.assertIn("mismatch", ids["verify.provenance.artifact"]["detail"])

    def test_verify_provenance_dry_run_is_rejected(self):
        nsp = self.make_nsp()
        payload = self.provenance_payload(nsp=nsp, dry_run=True)
        provenance = self.write_provenance(payload)
        args = self.parse_verify(["--provenance", str(provenance), "--json"])
        code, output, _ = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 1)
        ids = {check["id"]: check for check in json.loads(output)["checks"]}
        self.assertEqual(ids["verify.provenance.dry_run"]["status"], "fail")

    def test_verify_provenance_title_id_mismatch_fails(self):
        nsp = self.make_nsp()
        payload = self.provenance_payload(nsp=nsp, title_id="010047410000B000")
        provenance = self.write_provenance(payload)
        args = self.parse_verify(["--provenance", str(provenance), "--json"])
        code, output, _ = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 1)
        ids = {check["id"]: check for check in json.loads(output)["checks"]}
        self.assertEqual(ids["verify.provenance.title_id"]["status"], "fail")

    def test_verify_provenance_keyset_mismatch_fails(self):
        nsp = self.make_nsp()
        payload = self.provenance_payload(nsp=nsp)
        payload["keyset"]["sha256"] = "0" * 64
        provenance = self.write_provenance(payload)
        args = self.parse_verify(["--keyset", str(self.keyset),
                                  "--provenance", str(provenance), "--json"])
        code, output, _ = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 1)
        ids = {check["id"]: check for check in json.loads(output)["checks"]}
        self.assertEqual(ids["verify.provenance.keyset"]["status"], "fail")

    def test_verify_provenance_keyset_skipped_without_keyset(self):
        nsp = self.make_nsp()
        provenance = self.write_provenance(self.provenance_payload(nsp=nsp))
        args = self.parse_verify(["--provenance", str(provenance), "--json"])
        code, output, _ = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 0)
        ids = {check["id"]: check for check in json.loads(output)["checks"]}
        self.assertEqual(ids["verify.provenance.keyset"]["status"], "skip")

    def test_verify_provenance_with_key_markers_fails(self):
        nsp = self.make_nsp()
        payload = self.provenance_payload(nsp=nsp)
        payload["keyset"]["header_key"] = "ab" * 32
        provenance = self.write_provenance(payload)
        args = self.parse_verify(["--provenance", str(provenance), "--json"])
        code, output, _ = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 1)
        ids = {check["id"]: check for check in json.loads(output)["checks"]}
        self.assertEqual(ids["verify.provenance.no_secret"]["status"], "fail")

    def test_verify_provenance_unreadable_exits_1(self):
        self.make_nsp()
        args = self.parse_verify(["--provenance", str(self.root / "missing.json"), "--json"])
        code, output, _ = self.run_verify(args, self.fake_verify())
        self.assertEqual(code, 1)
        ids = {check["id"]: check for check in json.loads(output)["checks"]}
        self.assertEqual(ids["verify.provenance"]["status"], "fail")


if __name__ == "__main__":
    unittest.main()

