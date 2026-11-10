"""Engine source preparation: pinned checkouts, patches and lock records.

This module turns the source/patches/portlibs/build sections of an engine
descriptor into a reproducible local engine source tree:

  verify_pin(repo_dir, commit)   check that a checkout contains the pinned commit
  prepare(source, dest, ...)     check out the pin, apply patches, write a lock
  register(subparsers)           add the "galnx engines prepare" subcommand

Preparation is offline by default: dest must already be a git repository that
contains the pinned commit. Pass fetch=True (--fetch) to clone source.url when
dest does not exist yet. Nothing here downloads game data, keys or firmware;
patches are plain git patches and portlibs are only recorded, never built by
GalNX.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .descriptor import EngineDescriptorError, load_descriptor

LOCK_DIR = ".galnx"
LOCK_NAME = "engine-lock.json"
LOCK_SCHEMA_VERSION = 1
GIT_TIMEOUT_SECONDS = 300
SHA256_CHUNK = 1024 * 1024


class EnginePrepareError(RuntimeError):
    """Raised when an engine source tree cannot be verified or prepared."""


@dataclass(frozen=True)
class SourceSpec:
    """Normalised source descriptor section."""

    url: str = ""
    commit: str = ""
    submodules: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_value(cls, value: Any) -> "SourceSpec":
        if value is None:
            return cls()
        if isinstance(value, SourceSpec):
            return value
        if not isinstance(value, Mapping):
            raise EnginePrepareError("source must be a mapping with url/commit/submodules")
        modules = value.get("submodules") or ()
        if not isinstance(modules, (list, tuple)):
            raise EnginePrepareError("source.submodules must be a list")
        normalised: list[dict[str, Any]] = []
        for item in modules:
            if not isinstance(item, Mapping):
                raise EnginePrepareError("source.submodules entries must be mappings")
            entry: dict[str, Any] = {"path": str(item.get("path", "") or ""), "url": str(item.get("url", "") or "")}
            if item.get("commit"):
                entry["commit"] = str(item["commit"])
            normalised.append(entry)
        return cls(
            url=str(value.get("url", "") or ""),
            commit=str(value.get("commit", "") or ""),
            submodules=tuple(normalised),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "commit": self.commit,
            "submodules": [dict(item) for item in self.submodules],
        }


@dataclass(frozen=True)
class PrepareResult:
    """Outcome of prepare() (also the --json payload of the CLI)."""

    status: str
    dest: str
    commit: str
    head: str = ""
    check_only: bool = False
    fetched: bool = False
    patches: tuple[dict[str, Any], ...] = ()
    portlibs: tuple[dict[str, Any], ...] = ()
    lock_path: str = ""
    errors: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "dest": self.dest,
            "commit": self.commit,
            "head": self.head,
            "check_only": self.check_only,
            "fetched": self.fetched,
            "patches": [dict(item) for item in self.patches],
            "portlibs": [dict(item) for item in self.portlibs],
            "lock_path": self.lock_path,
            "errors": list(self.errors),
        }


def _git(
    args: Sequence[str],
    cwd: str | Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["git", *[str(item) for item in args]]
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env=env,
        )
    except FileNotFoundError as exc:
        raise EnginePrepareError("git is required to prepare engine sources") from exc
    except subprocess.TimeoutExpired as exc:
        raise EnginePrepareError("git %s timed out after %ss" % (command[1], GIT_TIMEOUT_SECONDS)) from exc
    if check and completed.returncode != 0:
        raise EnginePrepareError(
            "git %s failed (rc=%d): %s"
            % (" ".join(command[1:]), completed.returncode, _detail(completed))
        )
    return completed


def _detail(completed: subprocess.CompletedProcess[str]) -> str:
    text = (completed.stderr or completed.stdout or "").strip()
    if not text:
        return "no output"
    return text.splitlines()[-1]


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(SHA256_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_commit(commit: str) -> str:
    value = (commit or "").strip().lower()
    if not value:
        return ""
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise EnginePrepareError("source.commit must be 40 hex characters, got %r" % commit)
    return value


def _is_git_repo(path: Path) -> bool:
    if not path.is_dir():
        return False
    result = _git(["rev-parse", "--is-inside-work-tree"], path, check=False)
    return result.returncode == 0 and result.stdout.strip() == "true"


def _commit_present(repo_dir: str | Path, commit: str) -> bool:
    """Return True when commit names a commit object in repo_dir.

    Uses "git cat-file -t" instead of the "<sha>^{commit}" revision suffix:
    some git builds or Windows shim layers mangle the caret-brace suffix.
    """
    kind = _git(["cat-file", "-t", commit], repo_dir, check=False)
    return kind.returncode == 0 and kind.stdout.strip() == "commit"


def head_commit(repo_dir: str | Path) -> str:
    """Return the current HEAD commit of repo_dir (runtime error when absent)."""
    return _git(["rev-parse", "HEAD"], Path(repo_dir)).stdout.strip().lower()


def dirty_entries(repo_dir: str | Path) -> list[str]:
    """Tracked local changes in repo_dir (untracked files are ignored)."""
    output = _git(["status", "--porcelain", "--untracked-files=no"], Path(repo_dir)).stdout
    return [line for line in output.splitlines() if line.strip()]


def verify_pin(repo_dir: str | Path, commit: str) -> dict[str, Any]:
    """Verify that repo_dir is a git repository containing commit.

    Returns a JSON-friendly dict with the pinned commit, the current HEAD and
    whether they match. Raises EnginePrepareError when the directory is not a
    repository or the pinned commit is missing.
    """
    repo = Path(repo_dir)
    pinned = _normalise_commit(commit)
    if not pinned:
        raise EnginePrepareError("a pinned commit is required to verify the source pin")
    if not repo.exists():
        raise EnginePrepareError("source directory %s does not exist" % repo)
    if not _is_git_repo(repo):
        raise EnginePrepareError("source directory %s is not a git repository" % repo)
    if not _commit_present(repo, pinned):
        raise EnginePrepareError(
            "pinned commit %s is not present in %s (fetch the pinned commit first)" % (pinned, repo)
        )
    head = head_commit(repo)
    return {
        "repo": str(repo.resolve()),
        "commit": pinned,
        "head": head,
        "matches": head == pinned,
        "dirty": dirty_entries(repo),
    }


def _resolve_patch_path(value: str, base_dir: str | Path | None) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate
    bases = [Path.cwd()]
    if base_dir is not None:
        bases.append(Path(base_dir))
    for base in bases:
        resolved = base / value
        if resolved.exists():
            return resolved.resolve()
    return (Path.cwd() / value).resolve()


def _patch_entry(item: Any, base_dir: str | Path | None) -> dict[str, Any]:
    if isinstance(item, str):
        path = item
        notes = ""
    elif isinstance(item, Mapping):
        path = str(item.get("path", "") or "")
        notes = str(item.get("notes", "") or "")
    else:
        raise EnginePrepareError("patch entries must be mappings with a path")
    if not path:
        raise EnginePrepareError("patch path is required")
    resolved = _resolve_patch_path(path, base_dir)
    if not resolved.is_file():
        raise EnginePrepareError("patch file %s does not exist" % resolved)
    return {"path": path, "notes": notes, "absolute": str(resolved), "sha256": _sha256(resolved)}


def _lock_record(entry: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {"path": entry["path"], "sha256": entry["sha256"]}
    if entry.get("notes"):
        record["notes"] = entry["notes"]
    return record


def _utc_stamp(now: datetime | None) -> str:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rollback(repo: Path, commit: str, applied: Sequence[dict[str, Any]]) -> None:
    for entry in reversed(applied):
        _git(["apply", "-R", entry["absolute"]], repo, check=False)
    _git(["reset", "--hard", commit], repo, check=False)


def _write_lock(
    repo: Path,
    spec: SourceSpec,
    commit: str,
    portlibs: Sequence[Mapping[str, Any]],
    patches: Sequence[Mapping[str, Any]],
    now: datetime | None,
) -> str:
    lock_dir = repo / LOCK_DIR
    lock_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": LOCK_SCHEMA_VERSION,
        "kind": "engine-source",
        "source": {"url": spec.url, "commit": commit},
        "patches": [dict(item) for item in patches],
        "portlibs": [dict(item) for item in portlibs],
        "prepared_at": _utc_stamp(now),
    }
    target = lock_dir / LOCK_NAME
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return str(target)


def prepare(
    source: "SourceSpec | Mapping[str, Any] | None",
    dest: str | Path,
    patches: Sequence[Any] = (),
    portlibs: Sequence[Any] = (),
    *,
    fetch: bool = False,
    check_only: bool = False,
    base_dir: str | Path | None = None,
    now: datetime | None = None,
) -> PrepareResult:
    """Check out the pinned commit in dest and apply the patches.

    Offline by default: dest must be an existing git repository containing the
    pinned commit. With fetch=True a missing/empty dest is cloned from
    source.url first. check_only=True verifies the pin, the clean worktree and
    every patch with "git apply --check" and writes nothing.

    patches are descriptor patch mappings (or plain paths). Relative paths
    resolve against the current directory first, then base_dir (normally the
    descriptor file's directory).
    """
    spec = SourceSpec.from_value(source)
    commit = _normalise_commit(spec.commit)
    if not commit:
        raise EnginePrepareError("source.commit is required to prepare engine sources")
    patch_entries = [_patch_entry(item, base_dir) for item in patches or ()]
    portlib_entries = [dict(item) for item in portlibs or () if isinstance(item, Mapping)]
    dest_path = Path(dest)
    fetched = False
    if not _is_git_repo(dest_path):
        if dest_path.exists() and any(dest_path.iterdir()):
            raise EnginePrepareError(
                "destination %s exists but is not a git repository (move it away first)" % dest_path
            )
        if not fetch:
            raise EnginePrepareError(
                "destination %s does not contain a git repository; pass --fetch to clone %s"
                % (dest_path, spec.url or "<source.url>")
            )
        if not spec.url:
            raise EnginePrepareError("source.url is required to clone the engine sources")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", "--no-hardlinks", spec.url, str(dest_path)], dest_path.parent)
        fetched = True
    if not _is_git_repo(dest_path):
        raise EnginePrepareError("destination %s is not a git repository after clone" % dest_path)
    if not _commit_present(dest_path, commit) and fetch:
        _git(["fetch", "--tags", "--prune", "origin"], dest_path, check=False)
    if not _commit_present(dest_path, commit):
        raise EnginePrepareError(
            "pinned commit %s is not present in %s (fetch the pinned commit first)" % (commit, dest_path)
        )
    head = head_commit(dest_path)
    dirty = dirty_entries(dest_path)
    if check_only:
        errors: list[str] = []
        if head != commit:
            errors.append(
                "source HEAD is %s, expected pinned commit %s (re-run without --check-only to check it out)"
                % (head, commit)
            )
        if dirty:
            errors.append("source worktree has local changes: %s" % "; ".join(dirty[:5]))
        records: list[dict[str, Any]] = []
        for entry in patch_entries:
            record = _lock_record(entry)
            if not errors:
                result = _git(["apply", "--check", entry["absolute"]], dest_path, check=False)
                if result.returncode != 0:
                    errors.append("patch %s does not apply: %s" % (entry["path"], _detail(result)))
                    record["applies"] = False
                else:
                    record["applies"] = True
            records.append(record)
        status = "checked" if not errors else "failed"
        return PrepareResult(
            status=status,
            dest=str(dest_path.resolve()),
            commit=commit,
            head=head,
            check_only=True,
            fetched=fetched,
            patches=tuple(records),
            portlibs=tuple(portlib_entries),
            lock_path="",
            errors=tuple(errors),
        )
    if dirty:
        raise EnginePrepareError(
            "source worktree %s has local changes; commit or reset them before preparing (%s)"
            % (dest_path, "; ".join(dirty[:5]))
        )
    if head != commit:
        _git(["checkout", "--detach", commit], dest_path)
        head = head_commit(dest_path)
    if head != commit:
        raise EnginePrepareError(
            "failed to check out pinned commit %s in %s (HEAD is %s)" % (commit, dest_path, head)
        )
    applied: list[dict[str, Any]] = []
    records = []
    errors = []
    for entry in patch_entries:
        record = _lock_record(entry)
        checked = _git(["apply", "--check", entry["absolute"]], dest_path, check=False)
        if checked.returncode != 0:
            errors.append("patch %s does not apply: %s" % (entry["path"], _detail(checked)))
            record["applied"] = False
            records.append(record)
            break
        outcome = _git(["apply", entry["absolute"]], dest_path, check=False)
        if outcome.returncode != 0:
            errors.append("patch %s failed to apply: %s" % (entry["path"], _detail(outcome)))
            record["applied"] = False
            records.append(record)
            break
        record["applied"] = True
        records.append(record)
        applied.append(entry)
    if errors:
        _rollback(dest_path, commit, applied)
        for record in records:
            if record.get("applied"):
                record["applied"] = False
                record["rolled_back"] = True
        return PrepareResult(
            status="failed",
            dest=str(dest_path.resolve()),
            commit=commit,
            head=commit,
            fetched=fetched,
            patches=tuple(records),
            portlibs=tuple(portlib_entries),
            lock_path="",
            errors=tuple(errors),
        )
    lock_path = _write_lock(dest_path, spec, commit, portlib_entries, records, now)
    return PrepareResult(
        status="ready",
        dest=str(dest_path.resolve()),
        commit=commit,
        head=head,
        fetched=fetched,
        patches=tuple(records),
        portlibs=tuple(portlib_entries),
        lock_path=lock_path,
        errors=(),
    )


def _descriptor_source(descriptor: Any) -> dict[str, Any]:
    source = dict(descriptor.source) if isinstance(descriptor.source, Mapping) else {}
    return {
        "url": source.get("url") or descriptor.upstream_url,
        "commit": source.get("commit") or descriptor.pinned_commit,
        "submodules": source.get("submodules") or (),
    }


def cmd_prepare(args: Any) -> int:
    """Run "galnx engines prepare": 0 ok / 1 runtime failure / 2 descriptor error."""
    try:
        descriptor = load_descriptor(args.descriptor)
    except (EngineDescriptorError, OSError) as exc:
        print("galnx engines prepare: %s" % exc, file=sys.stderr)
        return 2
    if descriptor.build_backend == "prebuilt":
        print(
            "galnx engines prepare: engine %r ships a prebuilt artifact; there is no source to prepare"
            % descriptor.id,
            file=sys.stderr,
        )
        return 2
    source = _descriptor_source(descriptor)
    try:
        result = prepare(
            source,
            args.dest,
            descriptor.patches,
            descriptor.portlibs,
            fetch=args.fetch,
            check_only=args.check_only,
            base_dir=Path(args.descriptor).expanduser().resolve().parent,
        )
    except EnginePrepareError as exc:
        print("galnx engines prepare: %s" % exc, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result.to_json(), indent=2, sort_keys=False))
    if result.status == "failed":
        for error in result.errors:
            print("error: %s" % error, file=sys.stderr)
        print("engine prepare failed: %s" % result.dest, file=sys.stderr)
        return 1
    print(
        "engine prepare %s: %s at %s (%d patch(es), %d portlib(s))"
        % (result.status, result.commit, result.dest, len(result.patches), len(result.portlibs)),
        file=sys.stderr,
    )
    for record in result.patches:
        print("  patch %s %s" % (record.get("path"), record.get("sha256", "")), file=sys.stderr)
    if result.lock_path:
        print("  lock %s" % result.lock_path, file=sys.stderr)
    return 0


def register(subparsers: Any) -> None:
    """Register the "engines prepare" subcommand on an argparse subparsers object."""
    parser = subparsers.add_parser(
        "prepare",
        help="check out a pinned engine source tree and apply patches (offline by default)",
    )
    parser.add_argument("--descriptor", required=True, help="engine descriptor YAML file")
    parser.add_argument(
        "--dest",
        required=True,
        help="engine source directory (an existing git checkout unless --fetch)",
    )
    parser.add_argument("--fetch", action="store_true", help="clone source.url into --dest when it is missing")
    parser.add_argument(
        "--check-only",
        action="store_true",
        dest="check_only",
        help="verify the pin, the clean worktree and the patches without writing anything",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output on stdout")
    parser.set_defaults(func=cmd_prepare)
