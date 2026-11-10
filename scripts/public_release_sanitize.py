#!/usr/bin/env python3
"""Build a public-release copy of the GalNX repository.

The repository doubles as a lab notebook: docs/milestones/evidence/ and
docs/assets/ contain Citron and hardware screenshots of commercial games,
plus per-title covers and icons. Those images are third-party copyrighted
and must not be redistributed, so the public tree is produced by copying the
tracked files, skipping game art, and writing a manifest of what was removed.

Policy and review procedure: docs/environment/public-release.md

Usage:
    python scripts/public_release_sanitize.py --out E:/galnx-build/public/GalNX
    python scripts/public_release_sanitize.py --out ... --zip GalNX-public.zip

Exit codes:
    0  public tree written (and optionally zipped)
    1  policy file missing, output dir not empty, or a leak was detected
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# Any image under these prefixes is treated as game art (third-party copyright).
GAME_ART_PREFIXES = (
    "docs/milestones/",
    "docs/assets/",
    "examples/pilot",
)
GAME_ART_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")

# Images that are NOT game art may be allowlisted here, with a reason comment.
IMAGE_ALLOWLIST: tuple[str, ...] = ()

NOTES_NAME = "PUBLIC_RELEASE.md"
EXCLUSIONS_NAME = "PUBLIC_RELEASE_ART_EXCLUSIONS.txt"

# References to excluded art inside markdown are rewritten at export time, so the
# public docs never point at a file that is absent from the public tree.
ASSET_REF_PLACEHOLDER = "*[game art removed from public tree]*"

# Files that must exist in the public tree for the release to be license-clean.
REQUIRED_FILES = (
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "docs/builds/patches/LICENSE.md",
    "docs/builds/patches/rfvp-switch/LICENSE",
    "docs/builds/patches/krkrsdl2-switch-emulator/LICENSE",
    "docs/builds/patches/k2nx-switch/LICENSE",
)


def is_game_asset(rel: str) -> bool:
    """Return True when rel is a game screenshot, cover or icon."""
    rel = rel.replace("\\", "/")
    if rel in IMAGE_ALLOWLIST:
        return False
    return rel.lower().endswith(GAME_ART_SUFFIXES) and rel.startswith(GAME_ART_PREFIXES)



# Markdown target that looks like an excluded game asset (path inside a link).
_MD_ASSET_TARGET_RE = re.compile(
    r"(?:docs/(?:assets|milestones)/|examples/pilot)[^\s)]*"
    r"\.(?:png|jpg|jpeg|webp|gif)",
    re.IGNORECASE,
)
_MD_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
)
_MD_LINK_RE = re.compile(
    r"(?<!!)\[(?P<label>[^\]]+)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
)
_MD_FENCE_PREFIXES = ("```", "~~~")


def _is_removed_target(target: str) -> bool:
    """True when a markdown link target points at a file the public tree drops."""
    if not _MD_ASSET_TARGET_RE.search(target):
        return False
    rel = target.split("#", 1)[0].split("?", 1)[0]
    while rel.startswith("./"):
        rel = rel[2:]
    return is_game_asset(rel)


def rewrite_markdown_refs(text: str) -> tuple[str, int]:
    """Rewrite references to excluded game art; return (text, replacements).

    Images become a short placeholder, plain links keep their label, and fenced
    code blocks are left untouched because they document pipelines verbatim.
    """
    lines: list[str] = []
    rewritten = 0
    in_fence = False

    def image_repl(match: re.Match[str]) -> str:
        nonlocal rewritten
        if not _is_removed_target(match.group("target")):
            return match.group(0)
        rewritten += 1
        return ASSET_REF_PLACEHOLDER

    def link_repl(match: re.Match[str]) -> str:
        nonlocal rewritten
        if not _is_removed_target(match.group("target")):
            return match.group(0)
        rewritten += 1
        return match.group("label")

    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(_MD_FENCE_PREFIXES):
            in_fence = not in_fence
            lines.append(line)
            continue
        if in_fence:
            lines.append(line)
            continue
        new_line = _MD_IMAGE_RE.sub(image_repl, line)
        new_line = _MD_LINK_RE.sub(link_repl, new_line)
        lines.append(new_line)
    return "".join(lines), rewritten

def tracked_files(repo: Path) -> list[str]:
    """Return git-tracked paths (POSIX separators), in git order."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [item for item in proc.stdout.decode("utf-8").split("\0") if item]


def collect(repo: Path) -> tuple[list[str], list[str]]:
    """Split tracked files into (kept, excluded_game_art)."""
    files = tracked_files(repo)
    kept = [f for f in files if not is_game_asset(f)]
    excluded = [f for f in files if is_game_asset(f)]
    return kept, excluded


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _missing_required(repo: Path) -> list[str]:
    """Policy files that are absent or not yet tracked by git."""
    tracked = set(tracked_files(repo))
    return [rel for rel in REQUIRED_FILES if rel not in tracked]


def _count_prefixes(paths: list[str]) -> dict:
    counts = {}
    for rel in paths:
        for prefix in GAME_ART_PREFIXES:
            if rel.startswith(prefix):
                counts[prefix] = counts.get(prefix, 0) + 1
                break
    return counts


def _render_exclusions(excluded: list[str]) -> str:
    lines = [
        "# Game art excluded from the public tree",
        "# generated by scripts/public_release_sanitize.py; do not edit by hand",
        "#",
        "# These files stay in the private repository as development evidence.",
        "# Re-include only if the copyright holder grants redistribution rights.",
        "",
    ]
    lines.extend(excluded)
    return "\n".join(lines) + "\n"


def _render_notes(
    repo: Path,
    kept: list[str],
    excluded: list[str],
    head: str,
    rewritten_files: int = 0,
    rewritten_refs: int = 0,
) -> str:
    per_prefix = _count_prefixes(excluded)
    rows = "\n".join("- %s: %d files" % (k, v) for k, v in sorted(per_prefix.items()))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return """# GalNX public release tree

This directory is a sanitized snapshot, not the full repository.

- Source commit: %s
- Generated (UTC): %s
- Kept tracked files: %d
- Excluded game-art files: %d
- Markdown references rewritten: %d in %d files

## Why some files are missing

GalNX keeps Citron/hardware screenshots, per-title covers and icons as
development evidence. They show commercial game art whose copyright belongs
to the respective publishers, so they are excluded from the public tree:

%s

The full list is in %s. Those files remain in the private repository and can
be restored only with the copyright holders permission.

Markdown references that pointed at excluded art were rewritten during export
(images replaced by a placeholder, plain links reduced to their label), so the
public docs do not link to files that are not part of this tree.

## Licensing

- Project code and docs: MIT, see LICENSE.
- Engine patches: follow their upstream licenses, see THIRD_PARTY_NOTICES.md
  and docs/builds/patches/LICENSE.md.
- No game data, prod.keys, title.keys or Nintendo certificates are included.

## Publishing

Push this tree as a fresh repository or an orphan branch (see
docs/environment/public-release.md): the private history still contains the
excluded images, so pushing the original history would republish them.
""" % (
        head,
        stamp,
        len(kept),
        len(excluded),
        rewritten_refs,
        rewritten_files,
        rows,
        EXCLUSIONS_NAME,
    )


def build_public_tree(
    repo: Path,
    out: Path,
    *,
    zip_path: Path | None = None,
    force: bool = False,
) -> dict:
    repo = repo.resolve()
    out = out.resolve()
    if out == repo or repo in out.parents:
        raise SystemExit("refusing to write inside the repository: %s" % out)
    missing = _missing_required(repo)
    if missing:
        raise SystemExit(
            "policy files missing, public release would be license-incomplete: %s"
            % ", ".join(missing)
        )
    if out.exists() and any(out.iterdir()) and not force:
        raise SystemExit("output directory is not empty (use --force): %s" % out)

    kept, excluded = collect(repo)
    head = _git(repo, "rev-parse", "--short", "HEAD")
    out.mkdir(parents=True, exist_ok=True)
    missing_out = [rel for rel in REQUIRED_FILES if not (repo / rel).is_file()]
    if missing_out:
        raise SystemExit(
            "policy files missing from the working tree: %s" % ", ".join(missing_out)
        )

    total_bytes = 0
    rewritten_files = 0
    rewritten_refs = 0
    for rel in kept:
        src = repo / rel
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel.lower().endswith(".md"):
            original = src.read_bytes().decode("utf-8")
            updated, replaced = rewrite_markdown_refs(original)
            if replaced:
                dst.write_bytes(updated.encode("utf-8"))
                rewritten_files += 1
                rewritten_refs += replaced
            else:
                shutil.copyfile(src, dst)
        else:
            shutil.copyfile(src, dst)
        total_bytes += src.stat().st_size

    leaks = [rel for rel in kept if is_game_asset(rel)]
    if leaks:
        raise SystemExit("game art leaked into the public tree: %s" % ", ".join(leaks))
    incomplete = [rel for rel in REQUIRED_FILES if not (out / rel).is_file()]
    if incomplete:
        raise SystemExit("public tree is license-incomplete: %s" % ", ".join(incomplete))

    notes = _render_notes(
        repo,
        kept,
        excluded,
        head,
        rewritten_files=rewritten_files,
        rewritten_refs=rewritten_refs,
    )
    (out / NOTES_NAME).write_text(notes, encoding="utf-8")
    (out / EXCLUSIONS_NAME).write_text(_render_exclusions(excluded), encoding="utf-8")

    zipped = None
    if zip_path is not None:
        zip_path = zip_path.resolve()
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in kept:
                zf.write(out / rel, rel)
            zf.write(out / NOTES_NAME, NOTES_NAME)
            zf.write(out / EXCLUSIONS_NAME, EXCLUSIONS_NAME)
        zipped = zip_path

    return {
        "out": str(out),
        "zip": str(zipped) if zipped else None,
        "head": head,
        "kept": len(kept),
        "excluded": len(excluded),
        "bytes": total_bytes,
        "excluded_by_prefix": _count_prefixes(excluded),
        "rewritten_files": rewritten_files,
        "rewritten_refs": rewritten_refs,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_default = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=repo_default, help="GalNX checkout (default: repo root)")
    parser.add_argument("--out", type=Path, required=True, help="empty directory to write the public tree")
    parser.add_argument("--zip", type=Path, default=None, help="optional zip archive of the public tree")
    parser.add_argument("--force", action="store_true", help="overwrite a non-empty output directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        summary = build_public_tree(args.repo, args.out, zip_path=args.zip, force=args.force)
    except subprocess.CalledProcessError as exc:
        print("git ls-files failed: %s" % exc, file=sys.stderr)
        return 1
    print("public tree: %(out)s" % summary)
    print("source commit: %(head)s" % summary)
    print(
        "kept=%(kept)d excluded=%(excluded)d bytes=%(bytes)d "
        "rewritten_refs=%(rewritten_refs)d" % summary
    )
    for prefix, count in sorted(summary["excluded_by_prefix"].items()):
        print("  excluded %s: %d" % (prefix, count))
    if summary["zip"]:
        print("zip: %(zip)s" % summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
