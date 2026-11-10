#!/usr/bin/env python3
"""Build the public-release copy of the GalNX repository (fail-closed).

The repository doubles as a lab notebook: docs/milestones/evidence/ and
docs/assets/ contain Citron and hardware screenshots of commercial games,
plus per-title covers and icons. Those images are third-party copyrighted
and must not be redistributed. Some evidence directories also contain raw
game-data captures (for example decoded video frames). The public tree is
produced by copying the tracked files, skipping that material, rewriting
markdown references, redacting personal home paths, and then scanning the
generated tree (and, when requested, the ZIP archive) for policy violations.
Any BLOCK finding aborts the build with a non-zero exit code.

Policy and review procedure: docs/environment/public-release.md

Usage:
    python scripts/public_release_sanitize.py --out E:/galnx-build/public/GalNX
    python scripts/public_release_sanitize.py --out ... --zip GalNX-public.zip

Exit codes:
    0  public tree written (and optionally zipped); scan BLOCK findings == 0
    1  policy file missing, output unusable, or a BLOCK finding was found
"""
from __future__ import annotations

import argparse
import hashlib
import os
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
GAME_ART_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")

# Raw game-data captures that are not images but are equally non-redistributable.
GAME_DATA_SUFFIXES = (".nv12", ".nsa")

DEFAULT_ALLOWLIST_REASON = "explicitly allowlisted by the public release policy"

# Images that are NOT game art may be allowlisted here. Entries are either a
# path string or {"path": ..., "reason": ...}; always give a reason.
IMAGE_ALLOWLIST: tuple[object, ...] = ()

# Kept files whose extension would otherwise be blocked may be allowlisted
# here, again with an explicit reason. Keep this list as short as possible.
FILE_ALLOWLIST: tuple[object, ...] = (
    {
        "path": "examples/batch/games/demo-a/data.xp3",
        "reason": (
            "62-byte UTF-8 placeholder fixture for the batch demo; it does not "
            "start with the XP3 magic and contains no game data"
        ),
    },
)

NOTES_NAME = "PUBLIC_RELEASE.md"
EXCLUSIONS_NAME = "PUBLIC_RELEASE_ART_EXCLUSIONS.txt"

# VCS metadata is never part of the public snapshot. The publish mirror keeps a
# .git directory across rebuilds, and scanning git's compressed objects would
# block on binary content even though no git object is ever published.
SKIP_DIR_NAMES = (".git",)

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

# ---------------------------------------------------------------------------
# Fail-closed scan policy
# ---------------------------------------------------------------------------

SEVERITY_BLOCK = "BLOCK"
SEVERITY_REVIEW = "REVIEW"
SEVERITY_ALLOW = "ALLOW"

# Extensions that must never appear in a public snapshot.
HIGH_RISK_SUFFIXES = (
    ".nsp",
    ".xci",
    ".nca",
    ".nro",
    ".nso",
    ".npdm",
    ".kip",
    ".kipx",
    ".nsz",
    ".ncz",
    ".xcz",
    ".tik",
    ".cert",
    ".xp3",
    ".xmoe",
    ".hcb",
    ".wmv",
    ".mp4",
    ".mkv",
    ".ogg",
    ".mp3",
    ".wav",
    ".flac",
    ".ttf",
    ".otf",
    ".bin",
    ".iso",
    ".img",
    ".rom",
    ".sav",
    ".dll",
    ".exe",
    ".msi",
    ".dmg",
    ".so",
    ".dylib",
    ".nsa",
    ".nv12",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".xz",
    ".keys",
)

HIGH_RISK_NAMES = (
    "prod.keys",
    "title.keys",
    "console.keys",
    "keys.txt",
)

# Path keywords that always deserve human review; a high-risk extension makes
# the same hit a hard block instead.
PATH_REVIEW_KEYWORDS = (
    "save",
    "dump",
    "romfs",
    "game_data",
    "keys",
    "cert",
    "token",
    "password",
    "secret",
)

# Binaries whose leading bytes identify a format we never want to publish.
IMAGE_MAGIC_RULES = (
    (b"\x89PNG\r\n\x1a\n", "PNG image"),
    (b"\xff\xd8\xff", "JPEG image"),
    (b"BM", "BMP image"),
)

MAGIC_RULES = (
    (b"MZ", "PE executable (MZ)"),
    (b"\x7fELF", "ELF executable"),
    (b"PFS0", "Nintendo PFS0/NSP archive"),
    (b"NCA3", "Nintendo NCA archive"),
    (b"NCA2", "Nintendo NCA archive"),
    (b"NCA0", "Nintendo NCA archive"),
    (b"XP3\r\n ", "KiriKiri XP3 archive"),
    (b"OggS", "Ogg media stream"),
    (b"\x1f\x8b", "gzip stream"),
    (b"\xbc\xaf\x27\x1c", "7-Zip archive"),
    (b"Rar!\x1a\x07", "RAR archive"),
    (b"NSO0", "Nintendo NSO executable"),
    (b"NRO0", "Nintendo NRO executable"),
    (b"PK\x03\x04", "ZIP archive"),
)

TOKEN_PATTERNS = (
    (
        "github token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    ("aws access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "private key block",
        re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----"),
    ),
)

SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(?P<name>token|password|passwd|secret|api[_-]?key|access[_-]?key)\s*[:=]\s*"
    r"(?:\"(?P<dq>[^\"\n]{16,})\"|'(?P<sq>[^'\n]{16,})'|(?P<uq>[A-Za-z0-9_./+=-]{24,}))"
)

KEY_MATERIAL_RE = re.compile(
    r"(?im)^\s*(?P<name>header_key|key_area_key_[a-z0-9_]+|title_key_[0-9a-fA-F]+|"
    r"titlekek_[0-9a-fA-F]+|master_key_[a-z0-9_]+)\s*=\s*[0-9a-fA-F]{16,}"
)

HOME_RE = re.compile(r"C:[\\/]+Users[\\/]+[A-Za-z0-9._-]+")
DEVMACHINE_RE = re.compile(r"(?<![A-Za-z0-9_])[EDed]:[\\/]")

LARGE_FILE_LIMIT_BYTES = 8 * 1024 * 1024
MAX_REPORTED_WARNINGS = 10
MAX_BLOCKED_IN_ERROR = 20

_SAMPLE_BYTES = 8192


class SanitizationError(RuntimeError):
    """Raised when the generated public tree or ZIP violates the policy."""

    def __init__(self, message: str, findings: list[dict] | None = None) -> None:
        super().__init__(message)
        self.findings = list(findings or [])


# ---------------------------------------------------------------------------
# Allowlist helpers
# ---------------------------------------------------------------------------


def _allowlist_path(entry: object) -> str:
    if isinstance(entry, str):
        return entry
    return str(entry["path"])  # type: ignore[index]


def _allowlist_reason(entry: object) -> str:
    if isinstance(entry, str):
        return DEFAULT_ALLOWLIST_REASON
    return str(entry.get("reason") or DEFAULT_ALLOWLIST_REASON)  # type: ignore[union-attr]


def _allowlist_match(rel: str, entries: tuple[object, ...]) -> str | None:
    """Return the allowlist reason when rel matches an entry, else None."""
    rel = rel.replace("\\", "/")
    for entry in entries:
        path = _allowlist_path(entry).replace("\\", "/")
        if path.endswith("/"):
            if rel.startswith(path):
                return _allowlist_reason(entry)
        elif rel == path:
            return _allowlist_reason(entry)
    return None


# ---------------------------------------------------------------------------
# Exclusion policy
# ---------------------------------------------------------------------------


def is_game_asset(rel: str) -> bool:
    """Return True when rel is a game screenshot, cover or icon."""
    rel = rel.replace("\\", "/")
    if _allowlist_match(rel, IMAGE_ALLOWLIST) is not None:
        return False
    return rel.lower().endswith(GAME_ART_SUFFIXES) and rel.startswith(GAME_ART_PREFIXES)


def is_game_data(rel: str) -> bool:
    """Return True for raw game-data captures (decoded frames, archives)."""
    rel = rel.replace("\\", "/")
    return rel.lower().endswith(GAME_DATA_SUFFIXES)


def exclusion_kind(rel: str) -> str | None:
    """Return "art", "data" or None when rel is kept in the public tree."""
    rel = rel.replace("\\", "/")
    if is_game_asset(rel):
        return "art"
    if is_game_data(rel):
        return "data"
    return None


def is_excluded(rel: str) -> bool:
    return exclusion_kind(rel) is not None


# Markdown target that looks like an excluded game asset (path inside a link).
_MD_ASSET_TARGET_RE = re.compile(
    r"(?:docs/(?:assets|milestones)/|examples/pilot)[^\s)]*"
    r"\.(?:png|jpg|jpeg|webp|gif|bmp)",
    re.IGNORECASE,
)
_MD_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
)
_MD_LINK_RE = re.compile(
    r"(?<!!)\[(?P<label>[^\]]+)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
)
_MD_FENCE_PREFIXES = ("~~~", "```")


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


# ---------------------------------------------------------------------------
# Repository enumeration
# ---------------------------------------------------------------------------


def tracked_files(repo: Path) -> list[str]:
    """Return git-tracked paths (POSIX separators), in git order."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [item for item in proc.stdout.decode("utf-8").split("\0") if item]


def collect(repo: Path) -> tuple[list[str], list[str]]:
    """Split tracked files into (kept, excluded)."""
    files = tracked_files(repo)
    kept = [f for f in files if exclusion_kind(f) is None]
    excluded = [f for f in files if exclusion_kind(f) is not None]
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


def _count_exclusion_kinds(paths: list[str]) -> dict:
    counts = {"art": 0, "data": 0}
    for rel in paths:
        kind = exclusion_kind(rel)
        if kind:
            counts[kind] = counts.get(kind, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Export-time transformation
# ---------------------------------------------------------------------------


def redact_home_paths(text: str) -> tuple[str, int]:
    """Replace personal Windows home directories with a deterministic placeholder."""
    hits = 0

    def _repl(match: re.Match[str]) -> str:
        nonlocal hits
        hits += 1
        sep = "\\" if "\\" in match.group(0) else "/"
        return "C:" + sep + "Users" + sep + "<user>"

    return HOME_RE.sub(_repl, text), hits


def _sanitize_export(rel: str, data: bytes) -> tuple[bytes, int, int]:
    """Return (bytes_to_write, markdown_refs_rewritten, home_paths_redacted)."""
    if b"\x00" in data[:_SAMPLE_BYTES]:
        return data, 0, 0
    try:
        text = data.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        text = data.decode("latin-1")
        encoding = "latin-1"
    updated = text
    refs = 0
    if rel.lower().endswith(".md"):
        updated, refs = rewrite_markdown_refs(updated)
    updated, home_hits = redact_home_paths(updated)
    if updated == text:
        return data, 0, 0
    return updated.encode(encoding), refs, home_hits


# ---------------------------------------------------------------------------
# Scan engine
# ---------------------------------------------------------------------------


def _finding(rel: str, rule: str, severity: str, detail: str = "") -> dict:
    return {"path": rel, "rule": rule, "severity": severity, "detail": detail}


def _redact_secret(value: str) -> str:
    value = value.strip().strip("\"'")
    return "%s... (len=%d)" % (value[:6], len(value))


def _decode_text(data: bytes) -> tuple[str, str]:
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("latin-1"), "latin-1"


def _magic_hit(data: bytes) -> tuple[str, str] | None:
    for magic, label in IMAGE_MAGIC_RULES:
        if data.startswith(magic):
            return (
                "image file outside allowlist",
                label + "; add it to IMAGE_ALLOWLIST with a reason if it is not game art",
            )
    for magic, label in MAGIC_RULES:
        if data.startswith(magic):
            return ("blocked file magic", label)
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return ("blocked file magic", "MP4/ISO-BMFF container (ftyp)")
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return ("blocked file magic", "RIFF/WAVE audio")
    return None


def _scan_text(rel: str, text: str) -> list[dict]:
    findings: list[dict] = []
    for rule, pattern in TOKEN_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(
                _finding(rel, rule, SEVERITY_BLOCK, _redact_secret(match.group(0)))
            )
    match = KEY_MATERIAL_RE.search(text)
    if match:
        findings.append(
            _finding(
                rel,
                "Nintendo key material assignment",
                SEVERITY_BLOCK,
                "%s = <redacted hex value>" % match.group("name"),
            )
        )
    match = SECRET_ASSIGN_RE.search(text)
    if match:
        value = next(group for group in match.groups()[1:] if group)
        findings.append(
            _finding(
                rel,
                "secret assignment",
                SEVERITY_BLOCK,
                "%s = %s" % (match.group("name"), _redact_secret(value)),
            )
        )
    match = HOME_RE.search(text)
    if match:
        findings.append(
            _finding(
                rel,
                "personal home path",
                SEVERITY_BLOCK,
                "Windows home directory path (redacted)",
            )
        )
    dev_hits = len(DEVMACHINE_RE.findall(text))
    if dev_hits:
        findings.append(
            _finding(
                rel,
                "dev machine absolute path",
                SEVERITY_REVIEW,
                "%d hit(s); historical logs may contain build paths" % dev_hits,
            )
        )
    return findings


def scan_bytes(rel: str, data: bytes) -> list[dict]:
    """Scan one file payload; returns findings (BLOCK/REVIEW) and allowlist hits."""
    rel = rel.replace("\\", "/")
    for entries, label in ((FILE_ALLOWLIST, "file"), (IMAGE_ALLOWLIST, "image")):
        reason = _allowlist_match(rel, entries)
        if reason is not None:
            return [_finding(rel, "allowlist", SEVERITY_ALLOW, reason)]

    findings: list[dict] = []
    lower = rel.lower()
    name = lower.rsplit("/", 1)[-1]
    high_risk_ext = lower.endswith(HIGH_RISK_SUFFIXES)
    high_risk_name = name in HIGH_RISK_NAMES
    if high_risk_ext or high_risk_name:
        findings.append(
            _finding(
                rel,
                "high-risk file type",
                SEVERITY_BLOCK,
                "blocked name: %s" % name,
            )
        )
    keywords = sorted({kw for kw in PATH_REVIEW_KEYWORDS if kw in lower})
    if keywords:
        severity = (
            SEVERITY_BLOCK if (high_risk_ext or high_risk_name) else SEVERITY_REVIEW
        )
        findings.append(
            _finding(
                rel,
                "sensitive path keyword",
                severity,
                "keywords: " + ", ".join(keywords),
            )
        )
    if len(data) > LARGE_FILE_LIMIT_BYTES:
        findings.append(
            _finding(
                rel,
                "large file",
                SEVERITY_REVIEW,
                "%d bytes exceeds %d; verify it holds no embedded game data"
                % (len(data), LARGE_FILE_LIMIT_BYTES),
            )
        )

    magic = _magic_hit(data)
    if magic is not None:
        findings.append(_finding(rel, magic[0], SEVERITY_BLOCK, magic[1]))
    if b"\x00" in data[:_SAMPLE_BYTES]:
        findings.append(
            _finding(
                rel,
                "binary content",
                SEVERITY_BLOCK,
                "%d bytes; no NUL-free text scan possible" % len(data),
            )
        )
        return findings

    text, _encoding = _decode_text(data)
    findings.extend(_scan_text(rel, text))
    return findings


def summarize_scan(findings: list[dict], scanned_files: int) -> dict:
    blocked = [f for f in findings if f["severity"] == SEVERITY_BLOCK]
    review = [f for f in findings if f["severity"] == SEVERITY_REVIEW]
    allowed = [f for f in findings if f["severity"] == SEVERITY_ALLOW]
    review_by_rule: dict[str, int] = {}
    for finding in review:
        review_by_rule[finding["rule"]] = review_by_rule.get(finding["rule"], 0) + 1
    return {
        "scanned_files": scanned_files,
        "blocked": len(blocked),
        "review": len(review),
        "blocked_findings": blocked[:MAX_BLOCKED_IN_ERROR],
        "review_by_rule": dict(sorted(review_by_rule.items())),
        "warnings": review[:MAX_REPORTED_WARNINGS],
        "allowlist_hits": [
            {"path": f["path"], "reason": f["detail"]} for f in allowed
        ],
    }


def scan_tree(root: Path, *, skip_names: tuple[str, ...] = ()) -> dict:
    root = Path(root)
    skip = set(skip_names)
    findings: list[dict] = []
    scanned = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_DIR_NAMES for part in rel.split("/")):
            continue
        if rel in skip or path.name in skip:
            continue
        scanned += 1
        findings.extend(scan_bytes(rel, path.read_bytes()))
    return summarize_scan(findings, scanned)


def scan_zip(zip_path: Path, *, skip_names: tuple[str, ...] = ()) -> dict:
    skip = set(skip_names)
    findings: list[dict] = []
    scanned = 0
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            rel = info.filename.replace("\\", "/")
            if any(part in SKIP_DIR_NAMES for part in rel.split("/")):
                continue
            if rel in skip or rel.rsplit("/", 1)[-1] in skip:
                continue
            scanned += 1
            findings.extend(scan_bytes(rel, archive.read(info)))
    return summarize_scan(findings, scanned)


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_zip(out: Path, zip_path: Path, *, skip_names: tuple[str, ...] = (NOTES_NAME,)) -> None:
    """Write a deterministic ZIP of the public tree (no timestamps, sorted entries)."""
    skip = set(skip_names)
    files = []
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(out).as_posix()
        if any(part in SKIP_DIR_NAMES for part in rel.split("/")):
            continue
        if rel in skip or path.name in skip:
            continue
        files.append(rel)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for rel in files:
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (out / rel).read_bytes())


def _render_exclusions(excluded: list[str]) -> str:
    lines = [
        "# Files excluded from the public tree (game art / game data)",
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
    *,
    kept_bytes: int | None = None,
    scan: dict | None = None,
    zip_info: dict | None = None,
    excluded_by_kind: dict | None = None,
    allowlist_hits: tuple[dict, ...] = (),
    redacted_files: int = 0,
    redacted_home_hits: int = 0,
    generated_at: str | None = None,
) -> str:
    per_prefix = _count_prefixes(excluded)
    rows = (
        "\n".join("- %s: %d files" % (key, value) for key, value in sorted(per_prefix.items()))
        or "- none"
    )
    if kept_bytes is None:
        kept_bytes = sum(
            (repo / rel).stat().st_size for rel in kept if (repo / rel).is_file()
        )
    resolved_kinds = dict(excluded_by_kind or _count_exclusion_kinds(excluded))
    art = resolved_kinds.get("art", 0)
    data = resolved_kinds.get("data", 0)
    stamp = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    resolved_scan = dict(scan or {})
    blocked = resolved_scan.get("blocked", 0)
    review = resolved_scan.get("review", 0)
    scanned = resolved_scan.get("scanned_files", 0)
    review_by_rule = resolved_scan.get("review_by_rule", {})
    warnings = resolved_scan.get("warnings", [])
    scan_allowlist = list(resolved_scan.get("allowlist_hits") or [])
    if not scan_allowlist:
        scan_allowlist = [dict(hit) for hit in allowlist_hits]

    review_detail = (
        " (" + ", ".join("%s: %d" % item for item in review_by_rule.items()) + ")"
        if review_by_rule
        else ""
    )
    warning_lines = []
    for warning in warnings:
        warning_lines.append(
            "- %s: %s (%s)" % (warning["path"], warning["rule"], warning["detail"])
        )
    if not warning_lines:
        warning_lines.append("- none")

    if zip_info:
        zip_line = "- ZIP: %s" % zip_info.get("path", "unknown")
        zip_size_line = "- ZIP size: %d bytes" % zip_info.get("size", 0)
        zip_sha_line = "- ZIP sha256: %s" % zip_info.get("sha256", "")
    else:
        zip_line = "- ZIP: not requested"
        zip_size_line = "- ZIP size: 0 bytes"
        zip_sha_line = "- ZIP sha256: n/a"

    allowlist_lines = []
    for hit in scan_allowlist:
        allowlist_lines.append("- %s: %s" % (hit["path"], hit["reason"]))
    if not allowlist_lines:
        allowlist_lines.append("- none")

    body = []
    body.append("# GalNX public release tree")
    body.append("")
    body.append("This directory is a sanitized snapshot, not the full repository.")
    body.append("It is generated by scripts/public_release_sanitize.py with a fail-closed")
    body.append("scan; publish only while the scan reports zero BLOCK findings.")
    body.append("")
    body.append("- Source commit: %s" % head)
    body.append("- Generated (UTC): %s" % stamp)
    body.append("- Kept tracked files: %d" % len(kept))
    body.append("- Kept bytes: %d" % kept_bytes)
    body.append("- Excluded game-art files: %d" % art)
    body.append("- Excluded game-data files: %d" % data)
    body.append("- Excluded files total: %d" % len(excluded))
    body.append("- Markdown references rewritten: %d in %d files" % (rewritten_refs, rewritten_files))
    body.append(
        "- Personal home paths redacted: %d hits in %d files"
        % (redacted_home_hits, redacted_files)
    )
    body.append("")
    body.append("## Scan results")
    body.append("")
    body.append("- Scanned files in tree: %d" % scanned)
    body.append("- BLOCK findings: %d" % blocked)
    body.append("- REVIEW findings: %d%s" % (review, review_detail))
    body.append("")
    body.append("### Review warnings (first %d)" % MAX_REPORTED_WARNINGS)
    body.append("")
    body.extend(warning_lines)
    body.append("")
    body.append("### Allowlist entries hit")
    body.append("")
    body.extend(allowlist_lines)
    body.append("")
    body.append("### ZIP archive")
    body.append("")
    body.append(zip_line)
    body.append(zip_size_line)
    body.append(zip_sha_line)
    body.append("")
    body.append("## Exclusions by prefix")
    body.append("")
    body.append(rows)
    body.append("")
    body.append("## Why some files are missing")
    body.append("")
    body.append("GalNX keeps Citron/hardware screenshots, per-title covers and icons as")
    body.append("development evidence. They show commercial game art whose copyright belongs")
    body.append("to the respective publishers, so they are excluded from the public tree.")
    body.append("Raw game-data captures (for example decoded video frames) are excluded for")
    body.append("the same reason.")
    body.append("")
    body.append("The full list is in %s. Those files remain in the private" % EXCLUSIONS_NAME)
    body.append("repository and can be restored only with the copyright holders permission.")
    body.append("")
    body.append("Markdown references that pointed at excluded art were rewritten during export")
    body.append("(images replaced by a placeholder, plain links reduced to their label), so the")
    body.append("public docs do not link to files that are not part of this tree.")
    body.append("")
    body.append("Personal home-directory paths found in tracked docs are rewritten to the")
    body.append("placeholder C:" + "\\" + "Users" + "\\" + "<user> at export time (deterministic).")
    body.append("The scanner still treats any remaining home path as a BLOCK finding.")
    body.append("")
    body.append("## Licensing")
    body.append("")
    body.append("- Project code and docs: MIT, see LICENSE.")
    body.append("- Engine patches: follow their upstream licenses, see THIRD_PARTY_NOTICES.md")
    body.append("  and docs/builds/patches/LICENSE.md.")
    body.append("- No game data, prod.keys, title.keys or Nintendo certificates are included.")
    body.append("")
    body.append("## Publishing")
    body.append("")
    body.append("Push this tree as a fresh repository or an orphan branch (see")
    body.append("docs/environment/public-release.md): the private history still contains the")
    body.append("excluded images, so pushing the original history would republish them.")
    body.append("")
    return "\n".join(body)


def build_public_tree(
    repo: Path,
    out: Path,
    *,
    zip_path: Path | None = None,
    force: bool = False,
) -> dict:
    repo = Path(repo).resolve()
    out = Path(out).resolve()
    if out == repo or repo in out.parents:
        raise SystemExit("refusing to write inside the repository: %s" % out)
    missing = _missing_required(repo)
    if missing:
        raise SystemExit(
            "policy files missing, public release would be license-incomplete: %s"
            % ", ".join(missing)
        )
    if out.exists() and any(out.iterdir()):
        if not force:
            raise SystemExit("output directory is not empty (use --force): %s" % out)
        for child in out.iterdir():
            if child.name == ".git":
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()

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
    redacted_files = 0
    redacted_home_hits = 0
    for rel in kept:
        src = repo / rel
        original = src.read_bytes()
        total_bytes += len(original)
        data, refs, home_hits = _sanitize_export(rel, original)
        if refs:
            rewritten_files += 1
            rewritten_refs += refs
        if home_hits:
            redacted_files += 1
            redacted_home_hits += home_hits
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)

    leaks = [rel for rel in kept if is_excluded(rel)]
    if leaks:
        raise SystemExit("game art leaked into the public tree: %s" % ", ".join(leaks))
    incomplete = [rel for rel in REQUIRED_FILES if not (out / rel).is_file()]
    if incomplete:
        raise SystemExit("public tree is license-incomplete: %s" % ", ".join(incomplete))

    (out / EXCLUSIONS_NAME).write_text(_render_exclusions(excluded), encoding="utf-8")

    tree_scan = scan_tree(out, skip_names=(NOTES_NAME, EXCLUSIONS_NAME))
    zip_scan = None
    zip_size = 0
    zip_sha256 = ""
    zipped: Path | None = None
    if zip_path is not None:
        zipped = Path(zip_path).resolve()
        _write_zip(out, zipped)
        zip_size = zipped.stat().st_size
        zip_sha256 = _sha256_file(zipped)
        zip_scan = scan_zip(zipped, skip_names=(NOTES_NAME, EXCLUSIONS_NAME))

    blocked = tree_scan["blocked"] + (zip_scan["blocked"] if zip_scan else 0)
    if blocked:
        findings = list(tree_scan["blocked_findings"])
        if zip_scan:
            findings.extend(zip_scan["blocked_findings"])
        raise SanitizationError(
            "public release blocked by %d scan finding(s); tree kept at %s for review"
            % (blocked, out),
            findings=findings,
        )

    kind_counts = _count_exclusion_kinds(excluded)
    notes = _render_notes(
        repo,
        kept,
        excluded,
        head,
        rewritten_files=rewritten_files,
        rewritten_refs=rewritten_refs,
        kept_bytes=total_bytes,
        scan=tree_scan,
        zip_info=(
            {"path": str(zipped), "size": zip_size, "sha256": zip_sha256}
            if zipped is not None
            else None
        ),
        excluded_by_kind=kind_counts,
        allowlist_hits=tuple(tree_scan["allowlist_hits"]),
        redacted_files=redacted_files,
        redacted_home_hits=redacted_home_hits,
    )
    (out / NOTES_NAME).write_text(notes, encoding="utf-8")

    return {
        "out": str(out),
        "zip": str(zipped) if zipped is not None else None,
        "head": head,
        "kept": len(kept),
        "excluded": len(excluded),
        "bytes": total_bytes,
        "excluded_by_prefix": _count_prefixes(excluded),
        "excluded_by_kind": kind_counts,
        "rewritten_files": rewritten_files,
        "rewritten_refs": rewritten_refs,
        "redacted_files": redacted_files,
        "redacted_home_hits": redacted_home_hits,
        "allowlist_hits": tree_scan["allowlist_hits"],
        "scan": tree_scan,
        "zip_scan": zip_scan,
        "zip_size": zip_size,
        "zip_sha256": zip_sha256,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_default = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=repo_default, help="GalNX checkout (default: repo root)")
    parser.add_argument("--out", type=Path, required=True, help="directory to write the public tree")
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
    except SanitizationError as exc:
        print("public release blocked: %s" % exc, file=sys.stderr)
        for finding in exc.findings[:MAX_BLOCKED_IN_ERROR]:
            print(
                "  BLOCK %s: %s (%s)"
                % (finding["path"], finding["rule"], finding["detail"]),
                file=sys.stderr,
            )
        return 1
    print("public tree: %(out)s" % summary)
    print("source commit: %(head)s" % summary)
    print(
        "kept=%(kept)d excluded=%(excluded)d bytes=%(bytes)d "
        "rewritten_refs=%(rewritten_refs)d" % summary
    )
    print("excluded kinds: %s" % summary["excluded_by_kind"])
    print(
        "scan: block=%(blocked)d review=%(review)d scanned=%(scanned_files)d"
        % summary["scan"]
    )
    for rule, count in summary["scan"]["review_by_rule"].items():
        print("  review %s: %d" % (rule, count))
    for hit in summary["allowlist_hits"]:
        print("allowlist: %s (%s)" % (hit["path"], hit["reason"]))
    if summary["zip"]:
        print(
            "zip: %(zip)s (%(zip_size)d bytes, sha256=%(zip_sha256)s)" % summary
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
