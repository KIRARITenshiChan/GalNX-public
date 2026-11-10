"""Tests for scripts/public_release_sanitize.py (public release policy).

The sanitizer is fail-closed: game art / game data are excluded by policy, then
the generated tree and (optionally) the ZIP archive are scanned for high-risk
files, blocked magic bytes, credentials and personal paths. Any BLOCK finding
must abort the build with a non-zero exit code, and the publisher must refuse to
stage or commit the tree.

The tests build small throwaway git repositories in tmp_path so they exercise
the real git-tracked-file enumeration without touching the working tree.
"""

import hashlib
import importlib.util
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SANITIZE_SCRIPT = ROOT / "scripts" / "public_release_sanitize.py"
PUBLISH_SCRIPT = ROOT / "scripts" / "public_release_publish.py"
GIT_AVAILABLE = shutil.which("git") is not None
requires_git = pytest.mark.skipif(not GIT_AVAILABLE, reason="git not available")

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-png-payload"
JPEG_BYTES = b"\xff\xd8\xff" + b"test-jpeg-payload"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sanitize = _load("public_release_sanitize", SANITIZE_SCRIPT)
publish = _load("public_release_publish", PUBLISH_SCRIPT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_POLICY_FILES = {
    "LICENSE": "MIT License\n\nCopyright (c) GalNX test fixture\n",
    "THIRD_PARTY_NOTICES.md": "# Third-party notices\n\nTest fixture.\n",
    "docs/builds/patches/LICENSE.md": "# Patch licenses\n",
    "docs/builds/patches/rfvp-switch/LICENSE": "MIT\n",
    "docs/builds/patches/krkrsdl2-switch-emulator/LICENSE": "GPL-3.0\n",
    "docs/builds/patches/k2nx-switch/LICENSE": "MIT\n",
}


def _run_git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _track(repo, rel, data):
    """Write a file and stage it so git ls-files sees it."""
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    _run_git(repo, "add", "--", rel)


@pytest.fixture()
def fake_repo(tmp_path):
    repo = tmp_path / "private"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    for rel, text in REQUIRED_POLICY_FILES.items():
        _track(repo, rel, text)
    return repo


def _rules(findings):
    return [finding["rule"] for finding in findings]


def _severities(findings):
    return {finding["severity"] for finding in findings}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tree_snapshot(root):
    snapshot = {}
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == sanitize.NOTES_NAME:
            continue
        snapshot[rel] = path.read_bytes()
    return snapshot


def _stable_notes(root):
    lines = (Path(root) / sanitize.NOTES_NAME).read_text(encoding="utf-8").splitlines()
    return "\n".join(
        line
        for line in lines
        if not line.startswith("- Generated (UTC):")
        and not line.startswith("- ZIP:")
    )


# ---------------------------------------------------------------------------
# Exclusion policy (unchanged behaviour)
# ---------------------------------------------------------------------------


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


def test_allowlist_overrides_prefix_rule(monkeypatch):
    reason = "hand-drawn diagram, not game art"
    monkeypatch.setattr(
        sanitize,
        "IMAGE_ALLOWLIST",
        ({"path": "docs/assets/diagram.png", "reason": reason},),
    )
    assert sanitize.is_game_asset("docs/assets/diagram.png") is False
    assert sanitize.is_game_asset("docs/assets/cover.png") is True
    assert (
        sanitize._allowlist_match("docs/assets/diagram.png", sanitize.IMAGE_ALLOWLIST)
        == reason
    )


def test_file_allowlist_records_reason():
    findings = sanitize.scan_bytes(
        "examples/batch/games/demo-a/data.xp3", b"placeholder fixture\n"
    )
    assert _rules(findings) == ["allowlist"]
    assert findings[0]["severity"] == "ALLOW"
    assert "placeholder fixture" in findings[0]["detail"]


@requires_git
def test_required_policy_files_are_tracked():
    missing = sanitize._missing_required(ROOT)
    assert missing == [], "public release would be license-incomplete: %s" % missing


@requires_git
def test_collect_splits_art_and_data():
    kept, excluded = sanitize.collect(ROOT)
    assert kept, "expected tracked files"
    assert excluded, "expected game material to be excluded"
    assert not [rel for rel in kept if sanitize.exclusion_kind(rel)]
    kinds = {sanitize.exclusion_kind(rel) for rel in excluded}
    assert kinds <= {"art", "data"}
    assert "art" in kinds
    assert not [rel for rel in kept if rel.lower().endswith(sanitize.GAME_ART_SUFFIXES)]


@requires_git
def test_collect_matches_git_ls_files():
    tracked = sanitize.tracked_files(ROOT)
    kept, excluded = sanitize.collect(ROOT)
    assert sorted(kept + excluded) == sorted(tracked)


# ---------------------------------------------------------------------------
# Generated report
# ---------------------------------------------------------------------------


def test_notes_render_counts_and_manifest():
    notes = sanitize._render_notes(
        ROOT,
        ["README.md"],
        ["docs/assets/a.png", "docs/evidence/frame.nv12"],
        "deadbee",
        generated_at="2026-10-29T00:00:00Z",
    )
    assert "deadbee" in notes
    assert "Generated (UTC): 2026-10-29T00:00:00Z" in notes
    assert "Excluded game-art files: 1" in notes
    assert "Excluded game-data files: 1" in notes
    assert "docs/assets/: 1 files" in notes
    assert "BLOCK findings: 0" in notes
    manifest = sanitize._render_exclusions(["docs/assets/a.png"])
    assert "docs/assets/a.png" in manifest.splitlines()


def test_notes_render_scan_section():
    scan = {
        "scanned_files": 7,
        "blocked": 0,
        "review": 2,
        "review_by_rule": {"dev machine absolute path": 2},
        "warnings": [
            {
                "path": "docs/build.log",
                "rule": "dev machine absolute path",
                "detail": "2 hit(s)",
            }
        ],
        "allowlist_hits": [{"path": "data.xp3", "reason": "fixture reason"}],
    }
    digest = "f" * 64
    notes = sanitize._render_notes(
        ROOT,
        ["README.md"],
        [],
        "deadbee",
        scan=scan,
        zip_info={"path": "public.zip", "size": 10, "sha256": digest},
        generated_at="2026-10-29T00:00:00Z",
    )
    assert "Scanned files in tree: 7" in notes
    assert "BLOCK findings: 0" in notes
    assert "REVIEW findings: 2 (dev machine absolute path: 2)" in notes
    assert "- docs/build.log: dev machine absolute path (2 hit(s))" in notes
    assert "- data.xp3: fixture reason" in notes
    assert "ZIP size: 10 bytes" in notes
    assert "ZIP sha256: " + digest in notes


def test_notes_render_rewrite_counts():
    notes = sanitize._render_notes(
        ROOT,
        ["README.md"],
        ["docs/assets/a.png"],
        "deadbee",
        rewritten_files=2,
        rewritten_refs=3,
    )
    assert "Markdown references rewritten: 3 in 2 files" in notes


# ---------------------------------------------------------------------------
# Markdown reference rewriting (unchanged behaviour)
# ---------------------------------------------------------------------------


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
    assert count == 1
    assert "docs/MANIFEST.md" in rewritten


def test_rewrite_markdown_refs_skips_fenced_code():
    fence = "\x60" * 3
    text = fence + "\n![x](docs/assets/a.png)\n" + fence + "\n"
    rewritten, count = sanitize.rewrite_markdown_refs(text)
    assert count == 0
    assert rewritten == text


# ---------------------------------------------------------------------------
# Scan policy: benign content passes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel, text",
    [
        ("docs/notes.md", "# Notes\n\nBuild notes.\n"),
        ("src/galnx/cli.py", "tokens = values.strip().upper()\n"),
        ("docs/data.json", '{"display_name": "GalNX"}\n'),
        ("examples/demo.yaml", "engine: kirikiri2\n"),
    ],
)
def test_scan_allows_ordinary_text(rel, text):
    assert sanitize.scan_bytes(rel, text.encode("utf-8")) == []


@pytest.mark.parametrize(
    "rel, data",
    [("docs/assets/diagram.png", PNG_BYTES), ("docs/assets/photo.jpg", JPEG_BYTES)],
)
def test_scan_allows_allowlisted_images(monkeypatch, rel, data):
    monkeypatch.setattr(
        sanitize,
        "IMAGE_ALLOWLIST",
        ({"path": rel, "reason": "non-game diagram"},),
    )
    findings = sanitize.scan_bytes(rel, data)
    assert _rules(findings) == ["allowlist"]
    assert findings[0]["severity"] == "ALLOW"


def test_scan_blocks_image_outside_allowlist():
    findings = sanitize.scan_bytes("docs/assets/diagram.png", PNG_BYTES)
    assert "image file outside allowlist" in _rules(findings)
    assert _severities(findings) == {"BLOCK"}


def test_scan_blocks_unknown_binary():
    findings = sanitize.scan_bytes("docs/blob.txt", b"\x00\x01\x02" + b"\x00" * 32)
    assert "binary content" in _rules(findings)
    assert "BLOCK" in _severities(findings)


# ---------------------------------------------------------------------------
# Scan policy: high-risk extensions, magic bytes, secrets, paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel",
    [
        "examples/demo/sample.xp3",
        "docs/media/demo.wmv",
        "docs/roms/game.xci",
        "build/out.nsp",
        "docs/local/prod.keys",
        "keys.txt",
    ],
)
def test_scan_blocks_high_risk_extensions_and_names(rel):
    findings = sanitize.scan_bytes(rel, b"plain text placeholder\n")
    assert "high-risk file type" in _rules(findings)
    assert "BLOCK" in _severities(findings)


@pytest.mark.parametrize(
    "data, label",
    [
        (b"MZ" + b"\x00" * 32, "PE executable (MZ)"),
        (b"\x7fELF" + b"\x00" * 32, "ELF executable"),
        (b"PFS0" + b"\x00" * 32, "Nintendo PFS0/NSP archive"),
    ],
)
def test_scan_blocks_disguised_executables(data, label):
    findings = sanitize.scan_bytes("docs/notes.txt", data)
    assert "blocked file magic" in _rules(findings)
    detail = [
        finding["detail"]
        for finding in findings
        if finding["rule"] == "blocked file magic"
    ][0]
    assert label in detail


def test_scan_blocks_disguised_zip_container():
    findings = sanitize.scan_bytes("docs/bundle.dat", b"PK\x03\x04" + b"\x00" * 24)
    assert "blocked file magic" in _rules(findings)


def test_scan_blocks_key_material_assignment():
    line = "header_key = " + ("00" * 32) + "\n"
    findings = sanitize.scan_bytes("docs/config.txt", line.encode("utf-8"))
    assert "Nintendo key material assignment" in _rules(findings)
    assert "BLOCK" in _severities(findings)


def test_scan_blocks_github_token_and_redacts_detail():
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    data = ("leaked " + token + "\n").encode("utf-8")
    findings = sanitize.scan_bytes("docs/leak.md", data)
    assert "github token" in _rules(findings)
    detail = [f["detail"] for f in findings if f["rule"] == "github token"][0]
    assert token not in detail
    assert detail.startswith("ghp_A1")
    assert "len=" in detail


def test_scan_blocks_private_key_block():
    block = "-----BEGIN " + "RSA PRIVATE KEY-----"
    findings = sanitize.scan_bytes("docs/notes.txt", (block + "\n").encode("utf-8"))
    assert "private key block" in _rules(findings)
    assert "BLOCK" in _severities(findings)


def test_scan_blocks_personal_home_path():
    home = "C:" + "\\" + "Users" + "\\" + "someone"
    findings = sanitize.scan_bytes("docs/log.txt", (home + "\\file\n").encode("utf-8"))
    assert "personal home path" in _rules(findings)
    assert "BLOCK" in _severities(findings)


def test_scan_reviews_dev_machine_absolute_path():
    dev = "E:" + "/galnx-build/out"
    findings = sanitize.scan_bytes("docs/log.txt", ("built at " + dev + "\n").encode("utf-8"))
    assert "dev machine absolute path" in _rules(findings)
    assert _severities(findings) == {"REVIEW"}


def test_scan_reviews_sensitive_path_keywords():
    findings = sanitize.scan_bytes("docs/romfs/notes.md", b"ordinary notes\n")
    assert "sensitive path keyword" in _rules(findings)
    assert _severities(findings) == {"REVIEW"}


def test_scan_blocks_sensitive_path_with_high_risk_extension():
    findings = sanitize.scan_bytes("docs/save/game.xci", b"placeholder\n")
    assert _severities(findings) == {"BLOCK"}


def test_scan_reviews_large_file():
    data = b"a" * (sanitize.LARGE_FILE_LIMIT_BYTES + 1)
    findings = sanitize.scan_bytes("docs/big.log", data)
    assert "large file" in _rules(findings)
    assert _severities(findings) == {"REVIEW"}


# ---------------------------------------------------------------------------
# Summaries, tree scanning and ZIP rescan
# ---------------------------------------------------------------------------


def test_summarize_scan_groups_rules():
    findings = [
        {"path": "a", "rule": "x", "severity": "BLOCK", "detail": "d"},
        {"path": "b", "rule": "y", "severity": "REVIEW", "detail": "d"},
        {"path": "c", "rule": "y", "severity": "REVIEW", "detail": "d"},
        {"path": "d", "rule": "allowlist", "severity": "ALLOW", "detail": "r"},
    ]
    summary = sanitize.summarize_scan(findings, 4)
    assert summary["scanned_files"] == 4
    assert summary["blocked"] == 1
    assert summary["review"] == 2
    assert summary["review_by_rule"] == {"y": 2}
    assert summary["allowlist_hits"] == [{"path": "d", "reason": "r"}]
    assert summary["blocked_findings"][0]["path"] == "a"


def test_scan_tree_skips_notes_and_git_metadata(tmp_path):
    tree = tmp_path / "tree"
    (tree / "docs").mkdir(parents=True)
    (tree / "README.md").write_bytes(b"ok\n")
    token = "ghp_" + "a" * 30
    (tree / sanitize.NOTES_NAME).write_bytes(("token " + token + "\n").encode("utf-8"))
    (tree / ".git" / "objects").mkdir(parents=True)
    (tree / ".git" / "objects" / "pack").write_bytes(b"\x00" * 16)
    summary = sanitize.scan_tree(tree, skip_names=(sanitize.NOTES_NAME,))
    assert summary["blocked"] == 0
    assert summary["scanned_files"] == 1


def test_write_zip_is_deterministic_and_skips_notes(tmp_path):
    for name in ("tree-a", "tree-b"):
        tree = tmp_path / name
        (tree / "docs").mkdir(parents=True)
        (tree / "docs" / "a.md").write_text("hello\n", encoding="utf-8")
        (tree / sanitize.NOTES_NAME).write_text("report\n", encoding="utf-8")
    first = tmp_path / "a.zip"
    second = tmp_path / "b.zip"
    sanitize._write_zip(tmp_path / "tree-a", first)
    sanitize._write_zip(tmp_path / "tree-b", second)
    assert _sha256(first) == _sha256(second)
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["docs/a.md"]


def test_scan_zip_catches_hidden_violation(tmp_path):
    archive_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("docs/readme.txt", b"MZ" + b"\x00" * 32)
        archive.writestr("docs/ok.md", b"fine\n")
    summary = sanitize.scan_zip(archive_path)
    assert summary["blocked"] >= 1
    assert summary["blocked_findings"][0]["path"] == "docs/readme.txt"


# ---------------------------------------------------------------------------
# build_public_tree on a throwaway repository
# ---------------------------------------------------------------------------


def test_build_public_tree_rewrites_refs_and_excludes(fake_repo, tmp_path):
    _track(
        fake_repo,
        "README.md",
        "# GalNX\n\n![cover](docs/assets/cover.png)\n\n"
        "[shot](docs/milestones/M1/shot.png)\n",
    )
    _track(fake_repo, "docs/assets/cover.png", PNG_BYTES)
    _track(fake_repo, "docs/milestones/M1/shot.png", PNG_BYTES)
    _track(fake_repo, "docs/evidence/frame.nv12", b"\x00" * 16)
    out = tmp_path / "public"

    summary = sanitize.build_public_tree(fake_repo, out)

    assert summary["scan"]["blocked"] == 0
    assert summary["excluded_by_kind"] == {"art": 2, "data": 1}
    assert summary["excluded"] == 3
    assert summary["rewritten_refs"] == 2
    assert summary["rewritten_files"] == 1
    assert not (out / "docs/assets/cover.png").exists()
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert sanitize.ASSET_REF_PLACEHOLDER in readme
    assert "docs/assets/cover.png" not in readme
    notes = (out / sanitize.NOTES_NAME).read_text(encoding="utf-8")
    assert "BLOCK findings: 0" in notes
    assert "Excluded game-art files: 2" in notes
    assert "Excluded game-data files: 1" in notes
    assert "Source commit: unknown" in notes
    exclusions = (out / sanitize.EXCLUSIONS_NAME).read_text(encoding="utf-8")
    assert "docs/assets/cover.png" in exclusions.splitlines()


def test_build_public_tree_redacts_home_paths(fake_repo, tmp_path):
    home = "C:" + "\\" + "Users" + "\\" + "someone"
    _track(fake_repo, "docs/legacy.md", "old path " + home + "\\build\n")
    out = tmp_path / "public"

    summary = sanitize.build_public_tree(fake_repo, out)

    assert summary["scan"]["blocked"] == 0
    assert summary["redacted_home_hits"] == 1
    assert summary["redacted_files"] == 1
    exported = (out / "docs/legacy.md").read_text(encoding="utf-8")
    placeholder = "C:" + "\\" + "Users" + "\\" + "<user>"
    assert placeholder in exported
    notes = (out / sanitize.NOTES_NAME).read_text(encoding="utf-8")
    assert "Personal home paths redacted: 1 hits in 1 files" in notes


def test_build_public_tree_blocks_violation(fake_repo, tmp_path):
    token = "ghp_" + "a" * 30
    _track(fake_repo, "docs/leak.md", "leaked " + token + "\n")
    out = tmp_path / "public"

    with pytest.raises(sanitize.SanitizationError) as excinfo:
        sanitize.build_public_tree(fake_repo, out)

    findings = excinfo.value.findings
    assert any(
        finding["path"] == "docs/leak.md" and finding["rule"] == "github token"
        for finding in findings
    )
    assert (out / "docs/leak.md").is_file(), "blocked tree is kept for review"
    assert not (out / sanitize.NOTES_NAME).exists()


def test_build_public_tree_is_reproducible(fake_repo, tmp_path):
    dev = "E:" + "/galnx-build/out"
    _track(fake_repo, "docs/notes.md", "# notes\n\nbuilt at " + dev + "\n")
    _track(fake_repo, "docs/assets/cover.png", PNG_BYTES)

    first = sanitize.build_public_tree(fake_repo, tmp_path / "a", zip_path=tmp_path / "a.zip")
    second = sanitize.build_public_tree(fake_repo, tmp_path / "b", zip_path=tmp_path / "b.zip")

    assert first["scan"]["blocked"] == 0
    assert first["zip_scan"]["blocked"] == 0
    assert first["zip_sha256"] == second["zip_sha256"]
    assert _tree_snapshot(tmp_path / "a") == _tree_snapshot(tmp_path / "b")
    assert _stable_notes(tmp_path / "a") == _stable_notes(tmp_path / "b")


@requires_git
def test_real_repository_sanitizes_clean(tmp_path):
    out = tmp_path / "public"

    summary = sanitize.build_public_tree(ROOT, out)

    assert summary["scan"]["blocked"] == 0
    assert summary["excluded"] >= 300
    assert summary["kept"] > 800
    assert summary["redacted_home_hits"] >= 0
    notes = (out / sanitize.NOTES_NAME).read_text(encoding="utf-8")
    assert "BLOCK findings: 0" in notes
    assert "REVIEW findings:" in notes
    assert (out / "LICENSE").is_file()


# ---------------------------------------------------------------------------
# Publisher gate (fail-closed, idempotent)
# ---------------------------------------------------------------------------


def test_publish_commit_subject_records_private_commit():
    assert publish.commit_subject("abc1234") == (
        "Public snapshot of private commit abc1234"
    )


def test_notes_equivalent_ignores_only_timestamp():
    left = "a\n- Generated (UTC): 2026-10-29T00:00:00Z\nb\n"
    right = "a\n- Generated (UTC): 2026-10-30T00:00:00Z\nb\n\n"
    assert publish._notes_equivalent(left, right)
    assert not publish._notes_equivalent(left, right.replace("b", "c"))


def test_prepare_mirror_blocks_before_commit(fake_repo, tmp_path):
    token = "ghp_" + "a" * 30
    _track(fake_repo, "docs/leak.md", "token " + token + "\n")
    mirror = tmp_path / "mirror"

    with pytest.raises(publish.sanitize.SanitizationError):
        publish.prepare_mirror(fake_repo, mirror)

    assert (mirror / ".git").is_dir()
    assert not (mirror / sanitize.NOTES_NAME).exists()
    assert not publish._has_head(mirror)


def test_prepare_mirror_is_idempotent(fake_repo, tmp_path):
    _track(fake_repo, "docs/notes.md", "# notes\n")
    mirror = tmp_path / "mirror"

    first = publish.prepare_mirror(fake_repo, mirror)
    second = publish.prepare_mirror(fake_repo, mirror)

    assert first["committed"] is True
    assert first["scan"]["blocked"] == 0
    assert first["push_command"].startswith("cred_use(GH_TOKEN")
    assert second["committed"] is False
    assert second["public_head"] == first["public_head"]
    assert publish._git(mirror, "rev-list", "--count", "HEAD") == "1"
    assert publish._git(mirror, "status", "--porcelain") == ""


def test_publish_main_reports_blocked(fake_repo, tmp_path, capsys):
    token = "ghp_" + "a" * 30
    _track(fake_repo, "docs/leak.md", "token " + token + "\n")
    mirror = tmp_path / "mirror"

    rc = publish.main(["--repo", str(fake_repo), "--mirror", str(mirror)])

    captured = capsys.readouterr()
    assert rc == 1
    assert "public release blocked" in captured.err
    assert "docs/leak.md" in captured.err
    assert "push with:" not in captured.out


def test_sanitize_main_returns_nonzero_on_block(fake_repo, tmp_path):
    token = "ghp_" + "a" * 30
    _track(fake_repo, "docs/leak.md", "token " + token + "\n")

    rc = sanitize.main(["--repo", str(fake_repo), "--out", str(tmp_path / "public")])

    assert rc == 1
