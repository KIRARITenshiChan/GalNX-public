"""Tests for scripts/public_release_sanitize.py (public release policy)."""

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "public_release_sanitize.py"


def _load():
    spec = importlib.util.spec_from_file_location("public_release_sanitize", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sanitize = _load()


@pytest.mark.parametrize(
    "rel, expected",
    [
        ("docs/assets/pilot01-cover.png", True),
        ("docs/milestones/evidence/M1a/x.png", True),
        ("docs/milestones/M1-kirikiri.md", False),
        ("examples/pilot04/icon-256.jpg", True),
        ("examples/pilot04-akaseka.yaml", False),
        ("docs/milestones/evidence/SHA256SUMS", False),
        ("src/galnx/cli.py", False),
        ("docs/environment/git-eol-and-gh-push.md", False),
    ],
)
def test_is_game_asset(rel, expected):
    assert sanitize.is_game_asset(rel) is expected


def test_allowlist_overrides_prefix_rule():
    # The allowlist is empty today; make sure the contract works if it grows.
    original = sanitize.IMAGE_ALLOWLIST
    try:
        sanitize.IMAGE_ALLOWLIST = ("docs/assets/diagram.png",)
        assert sanitize.is_game_asset("docs/assets/diagram.png") is False
        assert sanitize.is_game_asset("docs/assets/cover.png") is True
    finally:
        sanitize.IMAGE_ALLOWLIST = original


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_required_policy_files_are_tracked():
    missing = sanitize._missing_required(ROOT)
    assert missing == [], "public release would be license-incomplete: %s" % missing


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_collect_never_keeps_game_art():
    kept, excluded = sanitize.collect(ROOT)
    assert kept, "expected tracked files"
    assert excluded, "expected game art to be excluded"
    assert not [rel for rel in kept if sanitize.is_game_asset(rel)]
    for rel in excluded:
        assert rel.lower().endswith(sanitize.GAME_ART_SUFFIXES)
        assert rel.startswith(sanitize.GAME_ART_PREFIXES)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_collect_matches_git_ls_files():
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    tracked = [line for line in out.splitlines() if line]
    kept, excluded = sanitize.collect(ROOT)
    assert sorted(kept + excluded) == sorted(tracked)


def test_notes_render_counts_and_manifest():
    notes = sanitize._render_notes(ROOT, ["README.md"], ["docs/assets/a.png"], "deadbee")
    assert "deadbee" in notes
    assert "Excluded game-art files: 1" in notes
    assert "docs/assets/: 1 files" in notes
    manifest = sanitize._render_exclusions(["docs/assets/a.png"])
    assert "docs/assets/a.png" in manifest.splitlines()

PUBLISH_SCRIPT = ROOT / "scripts" / "public_release_publish.py"


def _load_publish():
    spec = importlib.util.spec_from_file_location("public_release_publish", PUBLISH_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publish = _load_publish()


def test_rewrite_markdown_refs_drops_removed_art():
    text = (
        "See ![cover](docs/assets/pilot01-cover.png) and "
        "[screenshot](docs/milestones/evidence/P1/a.png).\n"
    )
    rewritten, count = sanitize.rewrite_markdown_refs(text)
    assert count == 2
    assert "docs/assets/pilot01-cover.png" not in rewritten
    assert "docs/milestones/evidence/P1/a.png" not in rewritten
    assert sanitize.ASSET_REF_PLACEHOLDER in rewritten
    assert "screenshot" in rewritten


def test_rewrite_markdown_refs_keeps_normal_refs():
    text = "![logo](docs/assets/logo.png) [manifest](docs/MANIFEST.md)\n"
    rewritten, count = sanitize.rewrite_markdown_refs(text)
    # docs/assets/logo.png is an image under docs/assets/ -> removed by policy;
    # rewrite must only change the image, not the ordinary markdown link.
    assert count == 1
    assert "docs/MANIFEST.md" in rewritten


def test_rewrite_markdown_refs_skips_fenced_code():
    fence = "`" * 3
    text = fence + "\n![x](docs/assets/a.png)\n" + fence + "\n"
    rewritten, count = sanitize.rewrite_markdown_refs(text)
    assert count == 0
    assert rewritten == text


def test_notes_render_rewrite_counts():
    notes = sanitize._render_notes(
        ROOT, ["README.md"], ["docs/assets/a.png"], "deadbee",
        rewritten_files=2, rewritten_refs=3,
    )
    assert "Markdown references rewritten: 3 in 2 files" in notes


def test_publish_commit_subject_records_private_commit():
    assert publish.commit_subject("abc1234") == (
        "Public snapshot of private commit abc1234"
    )
