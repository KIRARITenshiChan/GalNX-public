"""打包元数据模型（GalNX M3-c）。

PackageMetadata 描述「打成一个可安装 NSP/NRO 需要哪些元数据」，只做校验与
规划（galnx package plan），不调用 hacBrewPack、不接触 prod.keys/title.keys。

NSP 元数据字段依据（2026-10-30，M3-a 实测 + 开源工具源码）：
- NACP 字段（hacBrewPack nacp.c）：ApplicationTitleName（<=0x200 bytes）、
  Publisher（<=0x100 bytes）、TitleVersion（u32，major<<16|minor<<8|micro）、
  StartupUserAccount（0..2）、图标 256x256 JPEG；
- 图标文件 M3-a 产物为 control/icon_AmericanEnglish.dat（JPEG ffd8...ffd9，
  SOF 解析 256x256）；
- NSP 自包含结构（M3-a 实测）：exefs/main（NSO0）、exefs/main.npdm（META）、
  control/control.nacp（16384 B）、control/icon*.dat、romfs/。

PackageType 三种目标：
- self_contained_nsp：游戏本体 + romfs 全打进 NSP，独立可安装；
- forwarder_nsp：小 NSP 引导 sdmc 上的 NRO（不嵌入游戏资源）；
- nro：直接 Homebrew NRO（不做 NSP 封装）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Mapping, Optional, Tuple, Union

from .titleid import (
    TitleIdIssue,
    format_title_id,
    parse_title_id,
    validate_base,
)

NACP_TITLE_NAME_MAX = 0x200
NACP_AUTHOR_MAX = 0x100
NACP_ICON_SIZE = 256
NACP_STARTUP_USER_ACCOUNT_RANGE = (0, 2)

_JPEG_SOF_MARKERS = frozenset((
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
))
_JPEG_SOI = bytes([0xFF, 0xD8])
_JPEG_EOI = bytes([0xFF, 0xD9])


class PackageMetadataError(ValueError):
    """打包元数据非法（字段类型/枚举值/无法解析的 manifest 等）。"""


class PackageType(str, Enum):
    SELF_CONTAINED_NSP = "self_contained_nsp"
    FORWARDER_NSP = "forwarder_nsp"
    NRO = "nro"

    @property
    def is_nsp(self) -> bool:
        return self in (PackageType.SELF_CONTAINED_NSP, PackageType.FORWARDER_NSP)

    @property
    def label(self) -> str:
        return {
            PackageType.SELF_CONTAINED_NSP: "self-contained NSP",
            PackageType.FORWARDER_NSP: "forwarder NSP",
            PackageType.NRO: "NRO homebrew",
        }[self]


class MetadataIssue:
    """一条元数据校验结果。severity 只取 error/warning。"""

    def __init__(self, field: str, message: str, severity: str = "error") -> None:
        if severity not in ("error", "warning"):
            raise ValueError("severity must be error or warning")
        self.field = field
        self.message = message
        self.severity = severity

    @property
    def is_error(self) -> bool:
        return self.severity == "error"

    def to_dict(self) -> dict:
        return {"field": self.field, "message": self.message, "severity": self.severity}

    def __repr__(self) -> str:
        return "MetadataIssue(field=%r, severity=%r, message=%r)" % (
            self.field, self.severity, self.message)


def parse_version_code(version: Union[str, int]) -> int:
    """把 '1.0.0' 解析为 NACP 的 u32 版本号（major<<16|minor<<8|micro）。"""
    if isinstance(version, bool):
        raise PackageMetadataError("version must be a string like 1.0.0, got bool")
    if isinstance(version, int):
        if version < 0 or version > 0xFFFFFF:
            raise PackageMetadataError("version code out of range: %d" % version)
        return version
    if not isinstance(version, str):
        raise PackageMetadataError("version must be a string like 1.0.0, got %s" % type(version).__name__)
    text = version.strip()
    parts = text.split(".")
    if len(parts) != 3:
        raise PackageMetadataError("version must be major.minor.micro, got %r" % version)
    numbers: List[int] = []
    for part in parts:
        if not part.isdigit():
            raise PackageMetadataError("version component is not a number: %r" % part)
        number = int(part, 10)
        if number < 0 or number > 255:
            raise PackageMetadataError("version component must be 0-255, got %d" % number)
        numbers.append(number)
    return (numbers[0] << 16) | (numbers[1] << 8) | numbers[2]


def format_version_code(code: int) -> str:
    return "%d.%d.%d" % ((code >> 16) & 0xFF, (code >> 8) & 0xFF, code & 0xFF)


def jpeg_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """纯 Python 读取 JPEG 的 (width, height)；不是 JPEG 返回 None。

    扫描 JPEG 标记段直到 SOFn（SOF0/1/2/3/5/6/7/9/10/11/13/14/15）。
    """
    if len(data) < 4:
        return None
    if data[0] != 0xFF or data[1] != 0xD8:
        return None
    total = len(data)
    index = 2
    while index + 3 < total:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker == 0xFF:
            index += 1
            continue
        if marker == 0xD8:
            index += 2
            continue
        if marker == 0xDA or marker == 0xD9:
            return None
        if index + 3 >= total:
            return None
        segment_length = (data[index + 2] << 8) | data[index + 3]
        if segment_length < 2:
            return None
        if marker in _JPEG_SOF_MARKERS:
            if index + 8 >= total:
                return None
            height = (data[index + 5] << 8) | data[index + 6]
            width = (data[index + 7] << 8) | data[index + 8]
            return (width, height)
        index += 2 + segment_length
    return None


def bmp_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """纯 Python 读取 BMP 的 (width, height)；不是 BMP 返回 None。"""
    if len(data) < 26:
        return None
    if data[0] != 0x42 or data[1] != 0x4D:
        return None
    width = int.from_bytes(data[18:22], "little", signed=True)
    height = int.from_bytes(data[22:26], "little", signed=True)
    if width <= 0:
        return None
    return (width, abs(height))


def is_jpeg(data: bytes) -> bool:
    return len(data) >= 4 and data[0] == 0xFF and data[1] == 0xD8 and data[-2] == 0xFF and data[-1] == 0xD9


def image_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    dims = jpeg_dimensions(data)
    if dims is not None:
        return dims
    return bmp_dimensions(data)


@dataclass
class PackageMetadata:
    """一次 NSP/NRO 打包所需的元数据（不包含任何密钥）。"""

    title_name: str = ""
    title_author: str = ""
    version: str = "1.0.0"
    title_id: str = ""
    package_type: PackageType = PackageType.SELF_CONTAINED_NSP
    icon_path: Optional[Union[str, Path]] = None
    romfs_dir: Optional[Union[str, Path]] = None
    startup_user_account: int = 0
    notes: str = ""
    base_dir: Path = field(default_factory=lambda: Path("."))

    # ---- 路径/版本辅助 ----
    def resolve(self, path: Union[str, Path]) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return Path(self.base_dir) / candidate

    def icon_file(self) -> Optional[Path]:
        if self.icon_path is None:
            return None
        return self.resolve(self.icon_path)

    def romfs_path(self) -> Optional[Path]:
        if self.romfs_dir is None:
            return None
        return self.resolve(self.romfs_dir)

    def version_code(self) -> int:
        return parse_version_code(self.version)

    def formatted_title_id(self) -> str:
        if not self.title_id:
            return ""
        try:
            return format_title_id(self.title_id)
        except Exception:
            return str(self.title_id)

    def to_dict(self) -> dict:
        try:
            version_code = self.version_code()
        except PackageMetadataError:
            version_code = None
        return {
            "type": self.package_type.value,
            "type_label": self.package_type.label,
            "title_name": self.title_name,
            "title_author": self.title_author,
            "version": self.version,
            "version_code": version_code,
            "title_id": self.formatted_title_id(),
            "icon": None if self.icon_path is None else str(self.icon_path),
            "romfs_dir": None if self.romfs_dir is None else str(self.romfs_dir),
            "startup_user_account": self.startup_user_account,
            "notes": self.notes,
        }

    # ---- 校验 ----
    def validate(self) -> List[MetadataIssue]:
        """返回全部字段校验问题（errors + warnings），空列表表示通过。"""
        issues: List[MetadataIssue] = []
        package_type = self.package_type
        if not isinstance(package_type, PackageType):
            issues.append(MetadataIssue("package.type", "unknown package type: %r" % (package_type,)))
            package_type = PackageType.SELF_CONTAINED_NSP

        if not self.title_name.strip():
            issues.append(MetadataIssue("title_name", "title_name is required"))
        else:
            name_bytes = self.title_name.encode("utf-8")
            if len(name_bytes) > NACP_TITLE_NAME_MAX:
                issues.append(MetadataIssue(
                    "title_name",
                    "title_name is %d bytes UTF-8, NACP limit is %d" % (len(name_bytes), NACP_TITLE_NAME_MAX)))

        if not self.title_author.strip():
            issues.append(MetadataIssue("title_author", "title_author is required"))
        else:
            author_bytes = self.title_author.encode("utf-8")
            if len(author_bytes) > NACP_AUTHOR_MAX:
                issues.append(MetadataIssue(
                    "title_author",
                    "title_author is %d bytes UTF-8, NACP limit is %d" % (len(author_bytes), NACP_AUTHOR_MAX)))

        try:
            self.version_code()
        except PackageMetadataError as exc:
            issues.append(MetadataIssue("version", str(exc)))

        self._validate_title_id(package_type, issues)
        self._validate_startup_user_account(package_type, issues)
        self._validate_icon(package_type, issues)
        self._validate_romfs(package_type, issues)
        return issues

    def _validate_title_id(self, package_type: PackageType, issues: List[MetadataIssue]) -> None:
        text = self.title_id.strip() if isinstance(self.title_id, str) else ""
        if not text:
            if package_type.is_nsp:
                issues.append(MetadataIssue("title_id", "title_id is required for NSP packages"))
            return
        title_issues: List[TitleIdIssue] = validate_base(text)
        for issue in title_issues:
            severity = "error" if issue.is_error else "warning"
            if package_type == PackageType.NRO and issue.is_error:
                severity = "warning"
            issues.append(MetadataIssue("title_id", issue.message, severity=severity))

    def _validate_startup_user_account(self, package_type: PackageType, issues: List[MetadataIssue]) -> None:
        value = self.startup_user_account
        if isinstance(value, bool) or not isinstance(value, int):
            issues.append(MetadataIssue(
                "startup_user_account", "startup_user_account must be an integer 0-2, got %r" % (value,)))
            return
        low, high = NACP_STARTUP_USER_ACCOUNT_RANGE
        if value < low or value > high:
            issues.append(MetadataIssue(
                "startup_user_account",
                "startup_user_account must be %d-%d, got %d" % (low, high, value)))
        elif not package_type.is_nsp and value != 0:
            issues.append(MetadataIssue(
                "startup_user_account",
                "startup_user_account is only used by NSP packages; NRO ignores it",
                severity="warning"))

    def _validate_icon(self, package_type: PackageType, issues: List[MetadataIssue]) -> None:
        icon = self.icon_file()
        if icon is None:
            if package_type.is_nsp:
                issues.append(MetadataIssue("icon", "icon is required for NSP packages (256x256 JPEG)"))
            return
        if not icon.is_file():
            issues.append(MetadataIssue("icon", "icon file not found: %s" % icon))
            return
        try:
            data = icon.read_bytes()
        except OSError as exc:
            issues.append(MetadataIssue("icon", "cannot read icon %s: %s" % (icon, exc)))
            return
        dims = jpeg_dimensions(data)
        if dims is None:
            bmp = bmp_dimensions(data)
            if bmp is None:
                issues.append(MetadataIssue("icon", "icon is neither JPEG nor BMP: %s" % icon))
                return
            if bmp != (NACP_ICON_SIZE, NACP_ICON_SIZE):
                issues.append(MetadataIssue(
                    "icon", "icon must be %dx%d, got %dx%d (%s)" % (
                        NACP_ICON_SIZE, NACP_ICON_SIZE, bmp[0], bmp[1], icon)))
                return
            issues.append(MetadataIssue(
                "icon", "BMP icon accepted for preview but NACP requires JPEG: %s" % icon,
                severity="warning"))
            return
        if dims != (NACP_ICON_SIZE, NACP_ICON_SIZE):
            issues.append(MetadataIssue(
                "icon", "icon must be %dx%d JPEG, got %dx%d (%s)" % (
                    NACP_ICON_SIZE, NACP_ICON_SIZE, dims[0], dims[1], icon)))
        if not is_jpeg(data):
            issues.append(MetadataIssue("icon", "icon is missing the JPEG EOI marker (FFD9): %s" % icon,
                                        severity="warning"))

    def _validate_romfs(self, package_type: PackageType, issues: List[MetadataIssue]) -> None:
        romfs = self.romfs_path()
        if package_type == PackageType.SELF_CONTAINED_NSP:
            if romfs is None:
                issues.append(MetadataIssue(
                    "romfs_dir", "romfs_dir is required for a self-contained NSP (game assets live there)"))
                return
        if romfs is None:
            return
        if not romfs.is_dir():
            if package_type == PackageType.FORWARDER_NSP:
                issues.append(MetadataIssue(
                    "romfs_dir", "forwarder NSP does not embed romfs; configured romfs_dir is ignored: %s" % romfs,
                    severity="warning"))
            else:
                issues.append(MetadataIssue("romfs_dir", "romfs directory not found: %s" % romfs))
            return
        if package_type == PackageType.SELF_CONTAINED_NSP:
            children = [child for child in romfs.iterdir()]
            if not children:
                issues.append(MetadataIssue(
                    "romfs_dir", "romfs directory is empty; the self-contained NSP would ship without assets: %s" % romfs,
                    severity="warning"))

    # ---- 从 manifest 构造 ----
    @classmethod
    def from_manifest(cls, manifest: Mapping, base_dir: Union[str, Path]) -> "PackageMetadata":
        if not isinstance(manifest, Mapping):
            raise PackageMetadataError("manifest must be a mapping, got %s" % type(manifest).__name__)
        switch = manifest.get("switch") or {}
        game = manifest.get("game") or {}
        package = manifest.get("package") or {}
        if not isinstance(switch, Mapping) or not isinstance(game, Mapping):
            raise PackageMetadataError("manifest switch/game sections must be mappings")
        if not isinstance(package, Mapping):
            raise PackageMetadataError("manifest package section must be a mapping")

        target = switch.get("target")
        raw_type = package.get("type")
        if raw_type is None:
            raw_type = PackageType.NRO.value if target == "nro" else PackageType.SELF_CONTAINED_NSP.value
        try:
            package_type = PackageType(raw_type)
        except ValueError:
            allowed = ", ".join(item.value for item in PackageType)
            raise PackageMetadataError(
                "package.type must be one of %s, got %r" % (allowed, raw_type)) from None

        raw_startup = package.get("startup_user_account", 0)
        if isinstance(raw_startup, bool) or not isinstance(raw_startup, int):
            raise PackageMetadataError(
                "package.startup_user_account must be an integer 0-2, got %r" % (raw_startup,))

        icon = package.get("icon", switch.get("icon"))
        romfs = package.get("romfs_dir")
        title_id = switch.get("title_id") or ""
        title_name = switch.get("title") or game.get("title") or ""
        title_author = switch.get("author") or "GalNX"
        version = game.get("version") or "1.0.0"

        return cls(
            title_name=str(title_name),
            title_author=str(title_author),
            version=str(version),
            title_id=str(title_id),
            package_type=package_type,
            icon_path=None if icon is None else str(icon),
            romfs_dir=None if romfs is None else str(romfs),
            startup_user_account=raw_startup,
            notes=str(package.get("notes") or ""),
            base_dir=Path(base_dir),
        )


def errors_of(issues: List[MetadataIssue]) -> List[MetadataIssue]:
    return [issue for issue in issues if issue.is_error]


def warnings_of(issues: List[MetadataIssue]) -> List[MetadataIssue]:
    return [issue for issue in issues if not issue.is_error]


def issues_to_dict(issues: List[MetadataIssue]) -> List[dict]:
    return [issue.to_dict() for issue in issues]
