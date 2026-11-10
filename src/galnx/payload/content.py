"""Payload content classification, selection and game_files.txt rendering (GalNX P3-a).

A payload is the dataset the engine must copy from romfs to the SD card at
runtime: KiriKiri2 archives (data.xp3, ...), the game configuration
(haruno.cf), plugins (plugin/*.tpm) and generated files such as the keymap
(Kirikiroid2Preference.xml). This module is pure planning: it scans,
classifies, sorts and renders text. It never builds, packages or touches keys.

game_files.txt is the unpack contract between the engine and the workbench
(one of the M0 acceptance inputs):

    version=<payload version label>
    bytes=<total payload bytes, generated files included>
    target=<installation directory on the SD card>
    startup=<engine entry point, must live under target>
    marker=<marker file written after extraction>
    file=<path relative to the payload root>    (0..n lines)

Pilot pilot-01 measured: 28 lines / 600 B, UTF-8, LF, trailing newline.

Categories are listed in CATEGORY_ORDER: xp3 (game data), config (*.cf),
plugin (*.tpm), font (*.ttf/*.ttc/*.otf) and other. game_files.txt is ordered
by (category order, relative path); generated files (keymap, manifest) are
appended by the caller so the pilot sample is reproduced byte for byte.
"""
from __future__ import annotations

import fnmatch
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

CATEGORY_ORDER: tuple[str, ...] = ("xp3", "config", "plugin", "font", "other")

EXTENSION_CATEGORIES: dict[str, str] = {
    ".xp3": "xp3",
    ".cf": "config",
    ".tpm": "plugin",
    ".ttf": "font",
    ".ttc": "font",
    ".otf": "font",
}

#: Default include patterns: the set measured for pilot-01.
DEFAULT_INCLUDE: tuple[str, ...] = ("*.xp3", "*.cf", "plugin/*.tpm")
#: Default exclude patterns: signature files are never copied (P1-c audit).
DEFAULT_EXCLUDE: tuple[str, ...] = ("*.sig", "**/*.sig")

DEFAULT_MANIFEST_NAME = "game_files.txt"
MANIFEST_HEADER_KEYS: tuple[str, ...] = (
    "version",
    "bytes",
    "target",
    "startup",
    "marker",
)

#: Windows path limit (without the terminating NUL); SD and romfs paths use it.
WINDOWS_PATH_MAX = 259
#: Warn above this length to leave room for callers that join paths.
WINDOWS_PATH_WARN = 200
#: FAT32 per-file limit (4 GiB - 1 B); anything larger needs exFAT.
FAT32_MAX_FILE = 4 * 1024**3 - 1

FILE_ATTRIBUTE_SPARSE_FILE = 0x200


class PayloadError(ValueError):
    """Raised when payload configuration or content cannot be planned."""


def normalize_relpath(value: str) -> str:
    """Return a clean POSIX relative path, rejecting escapes and absolutes."""
    if not isinstance(value, str) or not value:
        raise PayloadError("payload path must be a non-empty string")
    if "\\" in value:
        raise PayloadError("payload path must use '/' separators: %r" % value)
    if "\n" in value or "\r" in value:
        raise PayloadError("payload path must not contain newlines: %r" % value)
    parts: list[str] = []
    for part in value.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise PayloadError("payload path must not escape its root: %r" % value)
        parts.append(part)
    if not parts:
        raise PayloadError("payload path is empty after normalisation: %r" % value)
    if ":" in parts[0]:
        raise PayloadError("payload path must be relative: %r" % value)
    return "/".join(parts)


def classify_path(relpath: str) -> str:
    """Classify one relative path into a CATEGORY_ORDER category."""
    suffix = Path(relpath).suffix.lower()
    return EXTENSION_CATEGORIES.get(suffix, "other")


def _validate_pattern(pattern: str) -> list[str]:
    if not isinstance(pattern, str) or not pattern:
        raise PayloadError("glob pattern must be a non-empty string")
    parts = pattern.split("/")
    for part in parts:
        if part == "..":
            raise PayloadError("glob pattern must not escape its root: %r" % pattern)
    return parts


def match_pattern(relpath: str, pattern: str) -> bool:
    """Match a POSIX relative path against one glob (no shell, no escapes).

    A star, question mark or character class never crosses '/'. A '**' path
    segment matches zero or more whole segments. Patterns are anchored at the
    payload root, so '*.xp3' selects only top-level xp3 files and
    'plugin/*.tpm' only the direct children of plugin/.
    """
    pattern_parts = _validate_pattern(pattern)
    path_parts = normalize_relpath(relpath).split("/")

    def _walk(path_index: int, pattern_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        part = pattern_parts[pattern_index]
        if part == "**":
            return any(
                _walk(index, pattern_index + 1)
                for index in range(path_index, len(path_parts) + 1)
            )
        if path_index == len(path_parts):
            return False
        return fnmatch.fnmatchcase(path_parts[path_index], part) and _walk(
            path_index + 1, pattern_index + 1
        )

    return _walk(0, 0)


def match_any(relpath: str, patterns: Iterable[str]) -> bool:
    return any(match_pattern(relpath, pattern) for pattern in patterns)


@dataclass(frozen=True)
class PayloadFile:
    """One selected payload file (metadata only; contents are never read here)."""

    rel: str
    size: int
    category: str
    source: Path | None = None
    symlink: bool = False
    sparse: bool = False

    def __post_init__(self) -> None:
        if self.size < 0:
            raise PayloadError("negative size for payload file %s" % self.rel)
        if self.category not in CATEGORY_ORDER:
            raise PayloadError("unknown payload category %r" % self.category)

    def to_json(self) -> dict:
        return {
            "path": self.rel,
            "bytes": self.size,
            "category": self.category,
            "symlink": self.symlink,
            "sparse": self.sparse,
        }


def _category_rank(category: str) -> int:
    return CATEGORY_ORDER.index(category)


def sort_files(files: Sequence[PayloadFile]) -> list[PayloadFile]:
    """Sort by (category order, relative path) - the game_files.txt order."""
    return sorted(files, key=lambda item: (_category_rank(item.category), item.rel))


def total_bytes(files: Iterable[PayloadFile]) -> int:
    return sum(item.size for item in files)


def is_sparse(path: Path) -> bool:
    """Best-effort sparse-file detection (Windows attribute / POSIX st_blocks)."""
    try:
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
            kernel32.GetFileAttributesW.restype = ctypes.c_uint32
            attributes = kernel32.GetFileAttributesW(str(path))
            if attributes == 0xFFFFFFFF:
                return False
            return bool(attributes & FILE_ATTRIBUTE_SPARSE_FILE)
        stat = path.stat()
        blocks = getattr(stat, "st_blocks", None)
        return blocks is not None and blocks * 512 < stat.st_size
    except (OSError, AttributeError):
        return False


def scan_payload(
    source_dir: str | Path,
    include: Sequence[str] = DEFAULT_INCLUDE,
    exclude: Sequence[str] = DEFAULT_EXCLUDE,
) -> list[PayloadFile]:
    """Walk source_dir and return the selected payload files (sorted).

    Only regular files are considered; symlinked files are reported but never
    followed into directories. include is required; exclude is applied after it
    (so '*_chs.xp3' can be dropped from '*.xp3').
    """
    root = Path(source_dir)
    if not root.is_dir():
        raise PayloadError("payload source_dir is not a directory: %s" % root)
    if not include:
        raise PayloadError("payload include list must not be empty")
    for pattern in list(include) + list(exclude):
        _validate_pattern(pattern)

    selected: list[PayloadFile] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            full = Path(current) / filename
            rel = full.relative_to(root).as_posix()
            if not match_any(rel, include) or match_any(rel, exclude):
                continue
            try:
                st = full.lstat()
            except OSError as exc:
                raise PayloadError(
                    "cannot stat payload file %s: %s" % (rel, exc)
                ) from None
            if (st.st_mode & 0o170000) != 0o100000:
                continue  # not a regular file
            selected.append(
                PayloadFile(
                    rel=normalize_relpath(rel),
                    size=st.st_size,
                    category=classify_path(rel),
                    source=full,
                    symlink=full.is_symlink(),
                    sparse=is_sparse(full),
                )
            )
    return sort_files(selected)


def _check_line_value(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise PayloadError("payload %s must be a non-empty string" % name)
    if "\n" in value or "\r" in value:
        raise PayloadError("payload %s must not contain newlines" % name)
    return value


def render_game_files(
    version: str,
    target: str,
    startup: str,
    marker: str,
    files: Sequence[PayloadFile],
) -> str:
    """Render the game_files.txt manifest text (UTF-8, LF, trailing newline)."""
    version = _check_line_value("version", version)
    target = _check_line_value("target", target)
    startup = _check_line_value("startup", startup)
    marker = _check_line_value("marker", marker)

    if not target.startswith("/") or not target.rstrip("/"):
        raise PayloadError(
            "payload target must be an absolute SD path, got %r" % target
        )
    expected_prefix = target.rstrip("/") + "/"
    if not startup.startswith(expected_prefix):
        raise PayloadError(
            "payload startup %r must live under target %r" % (startup, target)
        )

    ordered = sort_files(files)
    seen: set[str] = set()
    for item in ordered:
        rel = normalize_relpath(item.rel)
        if rel in seen:
            raise PayloadError("duplicate payload file in game_files.txt: %s" % rel)
        seen.add(rel)

    lines = [
        "version=%s" % version,
        "bytes=%d" % total_bytes(ordered),
        "target=%s" % target.rstrip("/"),
        "startup=%s" % startup,
        "marker=%s" % marker,
    ]
    lines.extend("file=%s" % item.rel for item in ordered)
    return "\n".join(lines) + "\n"


def parse_game_files(text: str) -> dict:
    """Parse game_files.txt back into a mapping (used to verify golden samples)."""
    if not text.endswith("\n"):
        raise PayloadError("game_files.txt must end with a newline")
    result: dict = {
        "version": None,
        "bytes": None,
        "target": None,
        "startup": None,
        "marker": None,
        "files": [],
    }
    lines = text.split("\n")[:-1]
    if len(lines) < len(MANIFEST_HEADER_KEYS):
        raise PayloadError(
            "game_files.txt has fewer than %d header lines"
            % len(MANIFEST_HEADER_KEYS)
        )
    for index, key in enumerate(MANIFEST_HEADER_KEYS):
        line = lines[index]
        prefix = key + "="
        if not line.startswith(prefix):
            raise PayloadError(
                "game_files.txt line %d must start with %r, got %r"
                % (index + 1, prefix, line)
            )
        value = line[len(prefix):]
        if key == "bytes":
            try:
                result[key] = int(value)
            except ValueError:
                raise PayloadError(
                    "game_files.txt bytes is not an integer: %r" % value
                ) from None
        else:
            result[key] = value
    for line in lines[len(MANIFEST_HEADER_KEYS):]:
        if not line.startswith("file="):
            raise PayloadError("unexpected game_files.txt line: %r" % line)
        result["files"].append(normalize_relpath(line[len("file="):]))
    return result


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
