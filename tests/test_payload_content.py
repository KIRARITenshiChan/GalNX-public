"""Unit tests for galnx.payload.content (selection + game_files.txt)."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from galnx.payload.content import (  # noqa: E402
    CATEGORY_ORDER,
    DEFAULT_EXCLUDE,
    DEFAULT_INCLUDE,
    PayloadError,
    PayloadFile,
    classify_path,
    is_sparse,
    match_any,
    match_pattern,
    normalize_relpath,
    parse_game_files,
    render_game_files,
    scan_payload,
    sha256_bytes,
    sort_files,
    total_bytes,
)


def _write(path: Path, data: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class NormalizeRelpathTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(normalize_relpath("a/b.txt"), "a/b.txt")

    def test_collapses_separators_and_dots(self):
        self.assertEqual(normalize_relpath("./a//b/./c.xp3"), "a/b/c.xp3")

    def test_strips_leading_slash(self):
        self.assertEqual(normalize_relpath("/a/b"), "a/b")

    def test_rejects_parent_escape(self):
        with self.assertRaises(PayloadError):
            normalize_relpath("a/../b")
        with self.assertRaises(PayloadError):
            normalize_relpath("..")

    def test_rejects_drive_letters_and_backslashes(self):
        with self.assertRaises(PayloadError):
            normalize_relpath("C:/game/data.xp3")
        with self.assertRaises(PayloadError):
            normalize_relpath("plugin\\x.tpm")

    def test_rejects_empty_and_control(self):
        for value in ("", "/", "./", "a\nb"):
            with self.assertRaises(PayloadError):
                normalize_relpath(value)


class ClassifyPathTests(unittest.TestCase):
    def test_categories(self):
        cases = {
            "data.xp3": "xp3",
            "image01.XP3": "xp3",
            "haruno.cf": "config",
            "plugin/csvParser.tpm": "plugin",
            "font/simhei.ttf": "font",
            "font/simsun.ttc": "font",
            "font/Noto.otf": "font",
            "plugin/krmovie.dll": "other",
            "Kirikiroid2Preference.xml": "other",
            "readme.txt": "other",
        }
        for rel, expected in cases.items():
            self.assertEqual(classify_path(rel), expected, rel)
            self.assertIn(expected, CATEGORY_ORDER)


class MatchPatternTests(unittest.TestCase):
    def test_star_does_not_cross_directories(self):
        self.assertTrue(match_pattern("data.xp3", "*.xp3"))
        self.assertFalse(match_pattern("sub/data.xp3", "*.xp3"))
        self.assertTrue(match_pattern("plugin/x.tpm", "plugin/*.tpm"))
        self.assertFalse(match_pattern("plugin/sub/x.tpm", "plugin/*.tpm"))

    def test_double_star(self):
        self.assertTrue(match_pattern("a/b/c.txt", "**/*.txt"))
        self.assertTrue(match_pattern("c.txt", "**/*.txt"))
        self.assertTrue(match_pattern("plugin/a.tpm", "plugin/**"))
        self.assertTrue(match_pattern("a/b/c.txt", "a/**/c.txt"))

    def test_case_sensitive_and_any(self):
        self.assertFalse(match_pattern("data.XP3", "*.xp3"))
        self.assertTrue(match_any("plugin/x.tpm", ("*.xp3", "plugin/*.tpm")))
        self.assertFalse(match_any("plugin/x.tpm", ("*.xp3", "*.cf")))

    def test_rejects_parent_pattern_and_bad_path(self):
        with self.assertRaises(PayloadError):
            match_pattern("a.xp3", "../*.xp3")
        with self.assertRaises(PayloadError):
            match_pattern("a\\b", "*")


class ScanPayloadTests(unittest.TestCase):
    def test_selects_and_sorts_pilot_style_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "data.xp3", b"x" * 10)
            _write(root / "haruno.cf", b"abc")
            _write(root / "plugin" / "x.tpm", b"12345")
            _write(root / "plugin" / "x.tpm.sig", b"s")
            _write(root / "extra_chs.xp3", b"zz")
            _write(root / "sub" / "deep.xp3", b"deep")
            _write(root / "readme.txt", b"note")

            files = scan_payload(root)
            self.assertEqual(
                [item.rel for item in files],
                ["data.xp3", "extra_chs.xp3", "haruno.cf", "plugin/x.tpm"],
            )
            self.assertEqual(
                [item.category for item in files],
                ["xp3", "xp3", "config", "plugin"],
            )
            self.assertEqual(total_bytes(files), 20)
            self.assertTrue(all(not item.symlink for item in files))

    def test_signatures_are_excluded_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "data.xp3", b"x")
            _write(root / "data.xp3.sig", b"y")
            _write(root / "plugin" / "a.tpm", b"z")
            _write(root / "plugin" / "a.tpm.sig", b"w")
            self.assertEqual([item.rel for item in scan_payload(root)], ["data.xp3", "plugin/a.tpm"])

    def test_include_all_walks_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "data.xp3")
            _write(root / "sub" / "deep.xp3")
            _write(root / "readme.txt")
            files = scan_payload(root, ("**/*",), ())
            self.assertEqual(
                [item.rel for item in files], ["data.xp3", "sub/deep.xp3", "readme.txt"]
            )

    def test_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "data.xp3")
            with self.assertRaises(PayloadError):
                scan_payload(root / "missing")
            with self.assertRaises(PayloadError):
                scan_payload(root, ())
            with self.assertRaises(PayloadError):
                scan_payload(root, ("../*.xp3",))


class SortFilesTests(unittest.TestCase):
    def test_category_order_then_path(self):
        files = [
            PayloadFile("z.txt", 1, "other"),
            PayloadFile("b.xp3", 1, "xp3"),
            PayloadFile("plugin/b.tpm", 1, "plugin"),
            PayloadFile("a.xp3", 1, "xp3"),
            PayloadFile("haruno.cf", 1, "config"),
        ]
        ordered = sort_files(files)
        self.assertEqual(
            [item.rel for item in ordered],
            ["a.xp3", "b.xp3", "haruno.cf", "plugin/b.tpm", "z.txt"],
        )


def _pilot_style_files():
    return [
        PayloadFile("data.xp3", 10, "xp3"),
        PayloadFile("haruno.cf", 3, "config"),
        PayloadFile("plugin/x.tpm", 5, "plugin"),
    ]


class RenderGameFilesTests(unittest.TestCase):
    def test_renders_pilot_layout(self):
        text = render_game_files(
            "v1",
            "/kirikiri/haruno",
            "/kirikiri/haruno/data.xp3",
            "/sdmc/switch/kirikiroid2/.marker",
            _pilot_style_files(),
        )
        self.assertTrue(text.endswith("\n"))
        lines = text.split("\n")
        self.assertEqual(lines[0], "version=v1")
        self.assertEqual(lines[1], "bytes=18")
        self.assertEqual(lines[2], "target=/kirikiri/haruno")
        self.assertEqual(lines[3], "startup=/kirikiri/haruno/data.xp3")
        self.assertEqual(lines[4], "marker=/sdmc/switch/kirikiroid2/.marker")
        self.assertEqual(
            lines[5:9],
            ["file=data.xp3", "file=haruno.cf", "file=plugin/x.tpm", ""],
        )
        self.assertEqual(len(lines), 9)

    def test_round_trips_through_parser(self):
        text = render_game_files(
            "pilot01-r2",
            "/kirikiri/haruno/",
            "/kirikiri/haruno/data.xp3",
            "sdmc:/switch/kirikiroid2/.galnx_extracted",
            _pilot_style_files(),
        )
        parsed = parse_game_files(text)
        self.assertEqual(parsed["version"], "pilot01-r2")
        self.assertEqual(parsed["bytes"], 18)
        self.assertEqual(parsed["target"], "/kirikiri/haruno")
        self.assertEqual(parsed["startup"], "/kirikiri/haruno/data.xp3")
        self.assertEqual(parsed["files"], ["data.xp3", "haruno.cf", "plugin/x.tpm"])

    def test_rejects_invalid_layout(self):
        with self.assertRaises(PayloadError):
            render_game_files("v1", "kirikiri/haruno", "/kirikiri/haruno/data.xp3", "/m", [])
        with self.assertRaises(PayloadError):
            render_game_files("v1", "/kirikiri/haruno", "/other/data.xp3", "/m", [])
        duplicated = _pilot_style_files() + [PayloadFile("data.xp3", 1, "xp3")]
        with self.assertRaises(PayloadError):
            render_game_files("v1", "/kirikiri/haruno", "/kirikiri/haruno/data.xp3", "/m", duplicated)
        with self.assertRaises(PayloadError):
            render_game_files("", "/kirikiri/haruno", "/kirikiri/haruno/data.xp3", "/m", [])
        with self.assertRaises(PayloadError):
            render_game_files("v1\nx", "/kirikiri/haruno", "/kirikiri/haruno/data.xp3", "/m", [])

    def test_parser_rejects_malformed_text(self):
        good = "version=v1\nbytes=0\ntarget=/a\nstartup=/a/b\nmarker=/m\n"
        self.assertEqual(parse_game_files(good)["files"], [])
        bad_texts = [
            good.rstrip("\n"),
            "version=v1\nbytes=0\ntarget=/a\nstartup=/a/b\n",
            "bytes=0\nversion=v1\ntarget=/a\nstartup=/a/b\nmarker=/m\n",
            "version=v1\nbytes=nope\ntarget=/a\nstartup=/a/b\nmarker=/m\n",
            "version=v1\nbytes=0\ntarget=/a\nstartup=/a/b\nmarker=/m\nextra\n",
        ]
        for text in bad_texts:
            with self.assertRaises(PayloadError, msg=repr(text)):
                parse_game_files(text)


class MiscTests(unittest.TestCase):
    def test_sha256_bytes(self):
        self.assertEqual(
            sha256_bytes(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_regular_file_is_not_sparse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plain.bin"
            path.write_bytes(b"x" * 1024)
            self.assertFalse(is_sparse(path))

    def test_payload_file_validates_metadata(self):
        with self.assertRaises(PayloadError):
            PayloadFile("x.xp3", -1, "xp3")
        with self.assertRaises(PayloadError):
            PayloadFile("x.xp3", 1, "bogus")
        self.assertEqual(
            PayloadFile("x.xp3", 1, "xp3", symlink=True).to_json(),
            {"path": "x.xp3", "bytes": 1, "category": "xp3", "symlink": True, "sparse": False},
        )


if __name__ == "__main__":
    unittest.main()
