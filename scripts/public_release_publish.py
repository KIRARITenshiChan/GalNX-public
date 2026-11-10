#!/usr/bin/env python3
"""Publish the sanitized GalNX tree into a local mirror repository.

The private repository at KIRARITenshiChan/GalNX stays the development home
(full history, all evidence). The public repository GalNX-public only ever
receives sanitized snapshots produced by scripts/public_release_sanitize.py.

This script:
  1. rebuilds the sanitized tree directly inside the mirror directory,
  2. initializes it as a git repository (main) if needed, or replaces the
     working tree while keeping .git,
  3. stages and commits the snapshot (commit message records the private
     source commit),
  4. prints the push command. It never handles tokens itself: push through
     cred_use(GH_TOKEN, mode=exec, command=git, args=["-C", mirror, "push",
     "origin", "main"]) so the credential is injected by the broker.

Usage:
    python scripts/public_release_publish.py --mirror E:/galnx-build/public/GalNX-public
    python scripts/public_release_publish.py --mirror ... --remote https://github.com/... --message "..."

Policy: docs/environment/public-release.md
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SANITIZE_SCRIPT = SCRIPT_DIR / "public_release_sanitize.py"
DEFAULT_REMOTE = "https://github.com/KIRARITenshiChan/GalNX-public.git"
DEFAULT_BRANCH = "main"


def load_sanitize():
    spec = importlib.util.spec_from_file_location("public_release_sanitize", SANITIZE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sanitize = load_sanitize()


def _out(args: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _git(mirror: Path, *args: str) -> str:
    return _out(["git", "-C", str(mirror), *args])


def commit_subject(source_head: str) -> str:
    return "Public snapshot of private commit %s" % source_head


def _clear_worktree(mirror: Path) -> None:
    """Delete everything except .git so the sanitized tree replaces it exactly."""
    for child in mirror.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def prepare_mirror(
    repo: Path,
    mirror: Path,
    *,
    remote: str | None = DEFAULT_REMOTE,
    message: str | None = None,
) -> dict:
    """Build, commit and report; returns a JSON-friendly summary."""
    repo = repo.resolve()
    mirror = mirror.resolve()
    if mirror == repo or repo in mirror.parents:
        raise SystemExit("refusing to write inside the repository: %s" % mirror)
    if mirror.exists() and any(mirror.iterdir()) and not (mirror / ".git").is_dir():
        raise SystemExit("mirror directory is not a git repository: %s" % mirror)

    mirror.mkdir(parents=True, exist_ok=True)
    existing = (mirror / ".git").is_dir()
    if existing:
        _clear_worktree(mirror)
    else:
        _out(["git", "init", "-b", DEFAULT_BRANCH, str(mirror)])

    summary = sanitize.build_public_tree(repo, mirror, force=True,
                                         zip_path=None)
    # build_public_tree refuses to write inside the source repo only; the mirror
    # above is external, so the check cannot trigger here.

    if remote:
        remotes = _git(mirror, "remote").split()
        if "origin" in remotes:
            _git(mirror, "remote", "set-url", "origin", remote)
        else:
            _git(mirror, "remote", "add", "origin", remote)

    subject = message or commit_subject(summary["head"])
    _git(mirror, "add", "-A")
    staged = _git(mirror, "status", "--porcelain")
    committed = False
    public_head = None
    if staged:
        _git(mirror, "commit", "-m", subject)
        committed = True
        public_head = _git(mirror, "rev-parse", "--short", "HEAD")
    else:
        try:
            public_head = _git(mirror, "rev-parse", "--short", "HEAD")
        except subprocess.CalledProcessError:
            public_head = None

    push_command = (
        'cred_use(GH_TOKEN, mode=exec, command="git", '
        'args=["-C", %r, "push", "origin", "%s"])' % (str(mirror), DEFAULT_BRANCH)
    )
    return {
        "mirror": str(mirror),
        "repo": str(repo),
        "source_head": summary["head"],
        "public_head": public_head,
        "committed": committed,
        "kept": summary["kept"],
        "excluded": summary["excluded"],
        "rewritten_files": summary["rewritten_files"],
        "rewritten_refs": summary["rewritten_refs"],
        "bytes": summary["bytes"],
        "remote": remote,
        "push_command": push_command,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_default = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=repo_default,
                        help="private GalNX checkout (default: repo root)")
    parser.add_argument("--mirror", type=Path, required=True,
                        help="local clone of the public repository")
    parser.add_argument("--remote", default=DEFAULT_REMOTE,
                        help="origin URL (default: %s)" % DEFAULT_REMOTE)
    parser.add_argument("--message", default=None,
                        help="commit subject (default: snapshot of private commit)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        summary = prepare_mirror(
            args.repo,
            args.mirror,
            remote=args.remote,
            message=args.message,
        )
    except subprocess.CalledProcessError as exc:
        print("git failed: %s" % exc, file=sys.stderr)
        return 1
    print("mirror: %(mirror)s" % summary)
    print("source commit: %(source_head)s" % summary)
    print("public head: %(public_head)s (committed=%(committed)s)" % summary)
    print("kept=%(kept)d excluded=%(excluded)d rewritten_refs=%(rewritten_refs)d" % summary)
    print("push with: %(push_command)s" % summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
