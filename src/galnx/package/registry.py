"""Title ID 注册表（GalNX M3-c）。

注册表只记录 title_id + 名称 + 备注，绝不记录 prod.keys/title.keys 或任何
密钥材料。仓库内示例：examples/packaging/titleid-registry.json。

JSON 文件格式（schema_version 1）：

{
  "schema_version": 1,
  "generated_by": "galnx",
  "entries": [
    {"title_id": "010047414C4E0000", "name": "sample-game", "note": "..."}
  ]
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Union

from .titleid import (
    TitleIdError,
    TitleIdIssue,
    check_conflicts,
    format_title_id,
    parse_title_id,
    validate_base,
)

REGISTRY_SCHEMA_VERSION = 1
ALLOWED_ENTRY_KEYS = frozenset(("title_id", "name", "note"))


class RegistryError(ValueError):
    """注册表文件/条目非法。"""


@dataclass(frozen=True)
class TitleIdEntry:
    title_id: str
    name: str
    note: str = ""

    def __post_init__(self) -> None:
        try:
            normalized = format_title_id(self.title_id)
        except TitleIdError as exc:
            raise RegistryError("invalid entry title id %r: %s" % (self.title_id, exc)) from None
        object.__setattr__(self, "title_id", normalized)
        if not isinstance(self.name, str) or not self.name.strip():
            raise RegistryError("entry name is required for title id %s" % normalized)

    def validate(self) -> List[TitleIdIssue]:
        return validate_base(self.title_id)

    def to_dict(self) -> dict:
        return {"title_id": self.title_id, "name": self.name, "note": self.note}

    @classmethod
    def from_dict(cls, data: Mapping) -> "TitleIdEntry":
        if not isinstance(data, Mapping):
            raise RegistryError("registry entry must be an object, got %s" % type(data).__name__)
        unknown = sorted(set(data) - ALLOWED_ENTRY_KEYS)
        if unknown:
            raise RegistryError(
                "registry entry has unsupported keys %s (allowed: %s); the registry must not store secrets" % (
                    unknown, sorted(ALLOWED_ENTRY_KEYS)))
        if "title_id" not in data or "name" not in data:
            raise RegistryError("registry entry requires title_id and name keys")
        note = data.get("note", "")
        if not isinstance(note, str):
            raise RegistryError("registry entry note must be a string")
        return cls(title_id=str(data["title_id"]), name=str(data["name"]), note=note)


@dataclass
class TitleIdRegistry:
    entries: List[TitleIdEntry] = field(default_factory=list)
    path: Optional[Path] = None

    # ---- 读写 ----
    @classmethod
    def load(cls, path: Union[str, Path], missing_ok: bool = True) -> "TitleIdRegistry":
        target = Path(path)
        if not target.exists():
            if missing_ok:
                return cls(entries=[], path=target)
            raise RegistryError("registry file not found: %s" % target)
        try:
            text = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise RegistryError("cannot read registry %s: %s" % (target, exc)) from None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RegistryError("registry is not valid JSON (%s): %s" % (target, exc)) from None
        registry = cls.from_dict(data)
        registry.path = target
        return registry

    def save(self, path: Optional[Union[str, Path]] = None) -> Path:
        target = Path(path) if path is not None else self.path
        if target is None:
            raise RegistryError("registry path is not set; pass a path to save()")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json() + chr(10), encoding="utf-8")
        self.path = target
        return target

    def to_dict(self) -> dict:
        return {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "generated_by": "galnx",
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Mapping) -> "TitleIdRegistry":
        if not isinstance(data, Mapping):
            raise RegistryError("registry must be a JSON object, got %s" % type(data).__name__)
        version = data.get("schema_version", REGISTRY_SCHEMA_VERSION)
        if version != REGISTRY_SCHEMA_VERSION:
            raise RegistryError("unsupported registry schema_version %r (expected %d)" % (
                version, REGISTRY_SCHEMA_VERSION))
        raw_entries = data.get("entries", [])
        if not isinstance(raw_entries, list):
            raise RegistryError("registry entries must be a list")
        entries = [TitleIdEntry.from_dict(item) for item in raw_entries]
        return cls(entries=entries)

    # ---- 查询/修改 ----
    def __len__(self) -> int:
        return len(self.entries)

    def ids(self) -> List[str]:
        return [entry.title_id for entry in self.entries]

    def find(self, title_id: Union[str, int]) -> Optional[TitleIdEntry]:
        try:
            normalized = format_title_id(title_id)
        except TitleIdError:
            return None
        for entry in self.entries:
            if entry.title_id == normalized:
                return entry
        return None

    def find_by_name(self, name: str) -> Optional[TitleIdEntry]:
        for entry in self.entries:
            if entry.name == name:
                return entry
        return None

    def add(self, entry: Union[TitleIdEntry, Mapping], replace: bool = False) -> TitleIdEntry:
        if not isinstance(entry, TitleIdEntry):
            entry = TitleIdEntry.from_dict(entry)
        existing = self.find(entry.title_id)
        if existing is not None and not replace:
            raise RegistryError("title id %s already registered as %r" % (entry.title_id, existing.name))
        issues = self.conflicts_for(entry.title_id)
        errors = [issue for issue in issues if issue.is_error]
        if errors:
            raise RegistryError("; ".join(issue.message for issue in errors))
        if existing is not None:
            self.entries[self.entries.index(existing)] = entry
        else:
            self.entries.append(entry)
        self.entries.sort(key=lambda item: item.title_id)
        return entry

    def remove(self, title_id: Union[str, int]) -> bool:
        entry = self.find(title_id)
        if entry is None:
            return False
        self.entries.remove(entry)
        return True

    # ---- 冲突检查 ----
    def conflicts_for(self, title_id: Union[str, int]) -> List[TitleIdIssue]:
        others = [entry.title_id for entry in self.entries if entry.title_id != _safe_format(title_id)]
        return check_conflicts(title_id, others)

    def conflicts(self) -> List[TitleIdIssue]:
        issues: List[TitleIdIssue] = []
        seen: List[str] = []
        for entry in self.entries:
            issues.extend(check_conflicts(entry.title_id, seen))
            seen.append(entry.title_id)
        return issues

    def errors(self) -> List[str]:
        errors: List[str] = []
        for entry in self.entries:
            for issue in entry.validate():
                if issue.is_error:
                    errors.append("%s: %s" % (entry.name, issue.message))
        for issue in self.conflicts():
            if issue.is_error:
                errors.append("%s: %s" % (issue.title_id, issue.message))
        return errors


def _safe_format(title_id: Union[str, int]) -> str:
    try:
        return format_title_id(title_id)
    except TitleIdError:
        return str(title_id)


def load_registry(path: Union[str, Path], missing_ok: bool = True) -> TitleIdRegistry:
    return TitleIdRegistry.load(path, missing_ok=missing_ok)
