"""NSP 打包驱动器（GalNX P3-b）。

把 P1-d 实测的 "ELF -> elf2nso -> NPDM/NACP/icon staging -> hacBrewPack -> nstool
校验 -> provenance" 流程固化成可测试的 Python 模块。设计约束：

* **只读规划**：plan_nsp_build() 不落盘、不调用任何外部工具，只做静态校验并
  给出将要执行的命令列表（dry-run 用）。
* **keyset 必须显式**：不接受环境变量或默认路径自动拾取；只记 path/size/sha256，
  绝不读取、复制、打印 prod.keys 内容。synthetic 模式只用于 CI 结构冒烟
  （hacBrewPack 内部造键，产物不可安装）。
* **子进程无 shell**：argv 列表直接交给 subprocess.run；每步写 work/logs/<step>.log，
  并把 hacBrewPack 打印的 Key area key 行过滤掉。
* **验证**：nstool 解析复用 package.contract；未签名 homebrew NSP 的
  "NCA Header Main Signature: FAIL" 只记 warning，不判失败。
* **provenance**：产物旁写 <out>.provenance.json（工具版本、输入 sha256、
  keyset 元数据、命令、nstool 摘要），可用于版本锁定（hacBrewPack 的 RSA-PSS
  随机盐导致同输入两次 NSP sha256 不同，不能锁 NSP 哈希）。

CLI 集成：cli.py（Lead 独占）在 package_sub 上调用 nsp.register(subparsers) 即可
获得 "galnx package nsp --manifest ... [--dry-run|--build]" 与
"galnx package nsp verify --nsp ... --manifest ..."；本模块的 cmd_nsp /
cmd_nsp_verify 自带 set_defaults(func=...)。
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .. import __version__ as GALNX_VERSION
from .contract import (
    NACP_SIZE,
    NPDM_MAGIC,
    Check,
    check_nstool,
    checks_to_dict,
    has_failures,
    parse_nstool_output,
)
from .metadata import MetadataIssue, PackageMetadata, PackageMetadataError, PackageType
from .titleid import TitleIdError, format_title_id, parse_title_id

PROVENANCE_SCHEMA_VERSION = 1

#: FAT32 单文件上限（4 GiB - 1）；Switch 的 SD 卡/title 安装路径按 FAT32 考虑。
FAT32_MAX_FILE_BYTES = 4 * 1024 ** 3 - 1
#: Windows MAX_PATH 阈值（hacBrewPack 会 "Failed to stat" 超长路径）。
WINDOWS_MAX_PATH_CHARS = 259
WINDOWS_MAX_PATH_WARN = 240

#: npdm.json 模板里的占位 TitleID（examples/nsp/npdm.json 原值）。
TITLE_ID_PLACEHOLDER = "0100000000001000"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_NPDM_TEMPLATE = _REPO_ROOT / "examples" / "nsp" / "npdm.json"

_TOOL_ATTRS = ("elf2nso", "npdmtool", "nacptool", "hacbrewpack", "nstool")

#: 日志里出现即视为密钥材料，持久化前整行丢弃。
_LOG_SECRET_MARKERS = ("key area key", "key_area_key", "header_key", "key_area_key_application")

_MAX_LOG_TAIL_LINES = 20

Runner = Callable[[Sequence[str], Optional[Path], float], Tuple[int, str, str]]


# ---------------------------------------------------------------------------
# 基础工具函数
# ---------------------------------------------------------------------------

def sha256_file(path: Union[str, Path], chunk_size: int = 1024 * 1024) -> str:
    """流式计算文件 sha256。"""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def digest_romfs(root: Union[str, Path]) -> str:
    """romfs 内容指纹：sha256(sorted(relpath + NUL + size + NUL + filesha256))。

    这是版本锁定的输入指纹：不依赖文件系统顺序、mtime，也不读取文件内容两次。
    """
    root_path = Path(root)
    entries: List[Tuple[str, int]] = []
    for current, _dirs, files in os.walk(root_path):
        for name in files:
            full = Path(current) / name
            try:
                rel = full.relative_to(root_path).as_posix()
                size = full.stat().st_size
            except OSError:
                continue
            entries.append((rel, size))
    digest = hashlib.sha256()
    for rel, size in sorted(entries):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\x00")
        try:
            digest.update(sha256_file(root_path / rel).encode("ascii"))
        except OSError:
            digest.update(b"unreadable")
        digest.update(b"\n")
    return digest.hexdigest()


def _path_text(path: Optional[Union[str, Path]]) -> str:
    return "" if path is None else str(path)


def _format_bytes(value: Union[int, float]) -> str:
    number = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(number) < 1024.0 or unit == "TiB":
            if unit == "B":
                return "%d %s" % (int(number), unit)
            return "%.1f %s" % (number, unit)
        number /= 1024.0
    return "%.1f TiB" % number


def _tail(text: str, lines: int = _MAX_LOG_TAIL_LINES) -> str:
    if not text:
        return ""
    rows = text.splitlines()
    return "\n".join(rows[-lines:] if len(rows) > lines else rows)


def _sanitize_log(text: str) -> str:
    """过滤包含密钥材料标记的行（hacBrewPack 会打印 Key area key）。"""
    if not text:
        return ""
    kept: List[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(marker in lowered for marker in _LOG_SECRET_MARKERS):
            kept.append("<redacted: key material line>")
            continue
        kept.append(line)
    return "\n".join(kept) + ("\n" if kept else "")


def _resolve_arg(value: Optional[Union[str, Path]], base_dir: Path) -> Optional[Path]:
    if value is None:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(base_dir) / path
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _safe_filename(text: str, fallback: str = "game") -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_. ") else "_" for ch in (text or ""))
    cleaned = cleaned.strip(" ._")
    return cleaned[:80] or fallback


def _read_magic(path: Path, size: int = 4) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read(size)
    except OSError:
        return b""


def _existing_ancestor(path: Path) -> Optional[Path]:
    candidate = path
    for _ in range(64):
        if candidate.exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return None


def _volume_key(path: Path) -> str:
    anchor = _existing_ancestor(path)
    if anchor is None:
        return ""
    drive = os.path.splitdrive(str(anchor))[0]
    if drive:
        return drive.lower()
    try:
        return "dev:%d" % int(anchor.stat().st_dev)
    except OSError:
        return ""


def _same_volume(left: Path, right: Path) -> bool:
    key = _volume_key(left)
    return bool(key) and key == _volume_key(right)


def _is_within(path: Union[str, Path], root: Union[str, Path]) -> bool:
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except OSError:
        return False


def _reset_dir(path: Path) -> None:
    """删除并重建一个目录（hacBrewPack 会就地改写暂存文件，每次必须重新复制）。"""
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    path.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, payload: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NspToolchain:
    """打包工具链路径；None 表示从 PATH 查找（显式路径优先）。

    全部显式传入时 plan/build 不依赖 PATH（CI 可复现）。elf2nso/npdmtool/
    nacptool 来自 devkitPro，hacBrewPack 来自 rlaphoenix/hacBrewPack，
    nstool 来自 jakcron/nstool。
    """

    elf2nso: Optional[Union[str, Path]] = None
    npdmtool: Optional[Union[str, Path]] = None
    nacptool: Optional[Union[str, Path]] = None
    hacbrewpack: Optional[Union[str, Path]] = None
    nstool: Optional[Union[str, Path]] = None

    def resolve(self) -> Tuple[Dict[str, Optional[Path]], Dict[str, str]]:
        paths: Dict[str, Optional[Path]] = {}
        sources: Dict[str, str] = {}
        for name in _TOOL_ATTRS:
            explicit = getattr(self, name)
            if explicit is not None:
                paths[name] = _resolve_arg(explicit, Path.cwd())
                sources[name] = "explicit"
                continue
            found = shutil.which(name)
            paths[name] = Path(found) if found else None
            sources[name] = "PATH" if found else "missing"
        return paths, sources


@dataclass
class KeysetRef:
    """keyset 引用（只记录元数据，绝不保存内容）。"""

    path: Optional[Path] = None
    size: int = 0
    sha256: str = ""
    synthetic: bool = False

    @property
    def mode(self) -> str:
        return "synthetic" if self.synthetic else "real"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "path": _path_text(self.path),
            "size": self.size,
            "sha256": self.sha256,
            "note": (
                "fabricated keys generated at build time; result is NOT INSTALLABLE (structure-only smoke test)"
                if self.synthetic else "explicitly supplied keyset; contents intentionally not recorded"
            ),
        }


@dataclass
class RomfsInventory:
    root: Optional[Path] = None
    files: int = 0
    dirs: int = 0
    total_bytes: int = 0
    max_path_len: int = 0
    max_path: str = ""
    largest_file_bytes: int = 0
    largest_file: str = ""
    unreadable: int = 0

    def to_dict(self) -> dict:
        return {
            "root": _path_text(self.root),
            "files": self.files,
            "dirs": self.dirs,
            "total_bytes": self.total_bytes,
            "max_path_len": self.max_path_len,
            "max_path": self.max_path,
            "largest_file_bytes": self.largest_file_bytes,
            "largest_file": self.largest_file,
            "unreadable": self.unreadable,
        }


@dataclass
class BuildStep:
    name: str
    argv: List[str] = field(default_factory=list)
    cwd: Optional[Path] = None
    note: str = ""
    outputs: List[Path] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "argv": list(self.argv),
            "cwd": _path_text(self.cwd),
            "note": self.note,
            "outputs": [_path_text(item) for item in self.outputs],
        }


@dataclass
class StepResult:
    name: str
    argv: List[str] = field(default_factory=list)
    cwd: str = ""
    exit_code: int = -1
    duration_s: float = 0.0
    stdout_tail: str = ""
    stderr_tail: str = ""
    log_path: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "duration_s": self.duration_s,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "log_path": self.log_path,
            "note": self.note,
        }


@dataclass
class BuildResult:
    ok: bool
    out_path: Optional[Path] = None
    work_dir: Optional[Path] = None
    steps: List[StepResult] = field(default_factory=list)
    artifact: Optional[Dict[str, object]] = None
    error: str = ""
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "out_path": _path_text(self.out_path),
            "work_dir": _path_text(self.work_dir),
            "duration_s": self.duration_s,
            "error": self.error,
            "artifact": self.artifact,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass
class VerifyResult:
    ok: bool
    nsp: Optional[Path] = None
    nstool: Optional[Path] = None
    checks: List[Check] = field(default_factory=list)
    ncas: int = 0
    artifact: Optional[Dict[str, object]] = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "nsp": _path_text(self.nsp),
            "nstool": _path_text(self.nstool),
            "ncas": self.ncas,
            "error": self.error,
            "artifact": self.artifact,
            "checks": checks_to_dict(self.checks),
        }


@dataclass
class NspBuildPlan:
    metadata: PackageMetadata
    elf: Optional[Path] = None
    romfs_dir: Optional[Path] = None
    inventory: Optional[RomfsInventory] = None
    out_path: Optional[Path] = None
    work_dir: Optional[Path] = None
    title_id: str = ""
    keyset: KeysetRef = field(default_factory=KeysetRef)
    synthetic_keys_path: Optional[Path] = None
    npdm: Optional[Path] = None
    npdm_template: Optional[Path] = None
    nacp: Optional[Path] = None
    icon: Optional[Path] = None
    tools: Dict[str, Optional[Path]] = field(default_factory=dict)
    tool_sources: Dict[str, str] = field(default_factory=dict)
    steps: List[BuildStep] = field(default_factory=list)
    issues: List[MetadataIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[MetadataIssue]:
        return [issue for issue in self.issues if issue.is_error]

    @property
    def warnings(self) -> List[MetadataIssue]:
        return [issue for issue in self.issues if not issue.is_error]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self, include_commands: bool = True) -> dict:
        payload = {
            "metadata": self.metadata.to_dict(),
            "title_id": self.title_id,
            "elf": _path_text(self.elf),
            "romfs_dir": _path_text(self.romfs_dir),
            "romfs": None if self.inventory is None else self.inventory.to_dict(),
            "out_path": _path_text(self.out_path),
            "work_dir": _path_text(self.work_dir),
            "keyset": self.keyset.to_dict(),
            "npdm": _path_text(self.npdm),
            "npdm_template": _path_text(self.npdm_template),
            "nacp": _path_text(self.nacp),
            "icon": _path_text(self.icon),
            "tools": {
                name: {"path": _path_text(path), "source": self.tool_sources.get(name, "")}
                for name, path in self.tools.items()
            },
            "checks": [issue.to_dict() for issue in self.issues],
            "ok": self.ok,
        }
        if include_commands:
            payload["steps"] = [step.to_dict() for step in self.steps]
        return payload


# ---------------------------------------------------------------------------
# romfs 清点与校验
# ---------------------------------------------------------------------------

def inventory_romfs(root: Union[str, Path]) -> RomfsInventory:
    """统计 romfs 目录（文件数/字节数/最长路径/最大文件）。"""
    root_path = Path(root)
    inventory = RomfsInventory(root=root_path)
    if not root_path.is_dir():
        return inventory
    for current, dirs, files in os.walk(root_path):
        inventory.dirs += len(dirs)
        for name in files:
            full = Path(current) / name
            rel = full.relative_to(root_path).as_posix()
            try:
                size = full.stat().st_size
            except OSError:
                inventory.unreadable += 1
                continue
            inventory.files += 1
            inventory.total_bytes += size
            path_len = len(str(full))
            if path_len > inventory.max_path_len:
                inventory.max_path_len = path_len
                inventory.max_path = str(full)
            if size > inventory.largest_file_bytes:
                inventory.largest_file_bytes = size
                inventory.largest_file = str(full)
    return inventory


def _check_inventory(inventory: RomfsInventory, issues: List[MetadataIssue]) -> None:
    if inventory.files == 0:
        issues.append(MetadataIssue(
            "romfs_dir", "romfs directory contains no files: %s" % inventory.root, severity="warning"))
    if inventory.unreadable:
        issues.append(MetadataIssue(
            "romfs_dir", "%d romfs file(s) could not be stat'ed: %s" % (
                inventory.unreadable, inventory.root), severity="warning"))
    if inventory.max_path_len >= WINDOWS_MAX_PATH_CHARS:
        issues.append(MetadataIssue(
            "romfs_dir",
            "romfs path is %d chars, at/over Windows MAX_PATH (%d): hacBrewPack will fail to stat %s" % (
                inventory.max_path_len, WINDOWS_MAX_PATH_CHARS, inventory.max_path)))
    elif inventory.max_path_len >= WINDOWS_MAX_PATH_WARN:
        issues.append(MetadataIssue(
            "romfs_dir",
            "romfs path is %d chars, close to Windows MAX_PATH (%d): %s" % (
                inventory.max_path_len, WINDOWS_MAX_PATH_CHARS, inventory.max_path),
            severity="warning"))
    if inventory.largest_file_bytes >= FAT32_MAX_FILE_BYTES:
        issues.append(MetadataIssue(
            "romfs_dir",
            "romfs file is %s, over the FAT32 4 GiB per-file limit: %s" % (
                _format_bytes(inventory.largest_file_bytes), inventory.largest_file)))


def _check_disk(out_path: Path, work_path: Path, romfs_bytes: int, elf_bytes: int,
                issues: List[MetadataIssue]) -> None:
    """估算构建峰值磁盘需求，不足时 error（dry-run 即暴露）。"""
    nsp_estimate = romfs_bytes + elf_bytes + 64 * 1024 * 1024
    work_need = nsp_estimate + elf_bytes + 64 * 1024 * 1024
    out_need = nsp_estimate
    if _same_volume(out_path, work_path):
        # 产物在 work 内生成后再复制到 out：同卷时峰值 = work + 产物。
        work_need += nsp_estimate
        out_need = 0
    for label, target, need in (("work_dir", work_path, work_need), ("out_path", out_path, out_need)):
        if need <= 0:
            continue
        anchor = _existing_ancestor(target)
        if anchor is None:
            continue
        try:
            free = shutil.disk_usage(anchor).free
        except OSError:
            continue
        if free < need:
            issues.append(MetadataIssue(
                label,
                "%s: free %s < estimated peak %s (romfs %s + ELF %s + staging); target volume %s" % (
                    label, _format_bytes(free), _format_bytes(need),
                    _format_bytes(romfs_bytes), _format_bytes(elf_bytes), anchor)))
        elif free < need * 1.5:
            issues.append(MetadataIssue(
                label,
                "%s: free %s is tight for estimated peak %s; target volume %s" % (
                    label, _format_bytes(free), _format_bytes(need), anchor),
                severity="warning"))


# ---------------------------------------------------------------------------
# keyset 解析（显式；绝不自动拾取内容）
# ---------------------------------------------------------------------------

def _resolve_keyset(value: Optional[Union[str, Path, KeysetRef]], base_dir: Path) -> Tuple[KeysetRef, List[MetadataIssue]]:
    issues: List[MetadataIssue] = []
    if isinstance(value, KeysetRef):
        return value, issues
    if value is None:
        issues.append(MetadataIssue(
            "keyset",
            "keyset is required and must be explicit: pass --keyset <prod.keys path> or "
            "--keyset synthetic (no default path, no environment variable auto-discovery)"))
        return KeysetRef(), issues
    text = str(value).strip()
    if not text:
        issues.append(MetadataIssue(
            "keyset", "keyset value is empty: pass an explicit prod.keys path or 'synthetic'"))
        return KeysetRef(), issues
    if text.lower() == "synthetic":
        issues.append(MetadataIssue(
            "keyset",
            "synthetic keyset: hacBrewPack fabricates keys at build time; the NSP is for "
            "structure-only smoke tests and is NOT INSTALLABLE",
            severity="warning"))
        return KeysetRef(synthetic=True), issues
    path = _resolve_arg(text, base_dir)
    if path is None or not path.is_file():
        issues.append(MetadataIssue("keyset", "keyset file not found: %s" % path))
        return KeysetRef(path=path), issues
    try:
        size = path.stat().st_size
    except OSError as exc:
        issues.append(MetadataIssue("keyset", "cannot stat keyset %s: %s" % (path, exc)))
        return KeysetRef(path=path), issues
    if size == 0:
        issues.append(MetadataIssue("keyset", "keyset file is empty: %s" % path))
        return KeysetRef(path=path), issues
    try:
        digest = sha256_file(path)
    except OSError as exc:
        issues.append(MetadataIssue("keyset", "cannot read keyset %s: %s" % (path, exc)))
        return KeysetRef(path=path, size=size), issues
    reference = KeysetRef(path=path, size=size, sha256=digest)
    if _is_within(path, _REPO_ROOT):
        issues.append(MetadataIssue(
            "keyset",
            "keyset path is inside the GalNX repository (%s): never commit or distribute "
            "prod.keys; keep it outside the working tree" % path,
            severity="warning"))
    return reference, issues


# ---------------------------------------------------------------------------
# 计划
# ---------------------------------------------------------------------------

def _default_npdm_template() -> Path:
    return _DEFAULT_NPDM_TEMPLATE


def _default_out_path(metadata: PackageMetadata, base_dir: Path, title_id: str) -> Path:
    name = _safe_filename(metadata.title_name or "game")
    suffix = title_id or "unknown"
    return Path(base_dir) / "build" / "nsp" / ("%s-%s.nsp" % (name, suffix))


def _default_work_dir(metadata: PackageMetadata, base_dir: Path, title_id: str) -> Path:
    return Path(base_dir) / "build" / "nsp" / ("work-%s" % (title_id or "unknown"))


def _require_file(issues: List[MetadataIssue], field_name: str, path: Path, label: str,
                  min_size: int = 1) -> bool:
    if not path.is_file():
        issues.append(MetadataIssue(field_name, "%s file not found: %s" % (label, path)))
        return False
    try:
        size = path.stat().st_size
    except OSError as exc:
        issues.append(MetadataIssue(field_name, "cannot stat %s %s: %s" % (label, path, exc)))
        return False
    if size < min_size:
        issues.append(MetadataIssue(field_name, "%s is too small (%d bytes): %s" % (label, size, path)))
        return False
    return True


def plan_nsp_build(
    metadata: PackageMetadata,
    *,
    elf: Optional[Union[str, Path]] = None,
    romfs_dir: Optional[Union[str, Path]] = None,
    out_path: Optional[Union[str, Path]] = None,
    work_dir: Optional[Union[str, Path]] = None,
    keyset: Optional[Union[str, Path, KeysetRef]] = None,
    toolchain: Optional[NspToolchain] = None,
    icon: Optional[Union[str, Path]] = None,
    npdm: Optional[Union[str, Path]] = None,
    npdm_template: Optional[Union[str, Path]] = None,
    nacp: Optional[Union[str, Path]] = None,
) -> NspBuildPlan:
    """纯静态规划：校验输入并生成构建命令列表，不执行、不落盘。

    参数：
        metadata: PackageMetadata（title_id/名称/版本等；package.type 必须是
            self_contained_nsp）。
        elf: elf2nso 输入 ELF（P1-d 实测的 NRO->ELF 合成产物）。
        romfs_dir: 要嵌入的 romfs 目录；None 用 metadata.romfs_dir。
        out_path/work_dir: 输出与暂存目录；None 用 build/nsp/ 默认值。
        keyset: 显式 prod.keys 路径或 "synthetic"；**必须提供**。
        toolchain: 工具路径集合；显式路径优先于 PATH。
        icon/npdm/nacp/npdm_template: 覆盖 metadata/默认值。
    """
    if not isinstance(metadata, PackageMetadata):
        raise TypeError("metadata must be a PackageMetadata, got %s" % type(metadata).__name__)
    base_dir = Path(metadata.base_dir)
    issues: List[MetadataIssue] = []

    # ---- 元数据：图标/romfs 覆盖后统一校验 ----
    icon_path = _resolve_arg(icon, base_dir) if icon is not None else metadata.icon_file()
    romfs_path = _resolve_arg(romfs_dir, base_dir) if romfs_dir is not None else metadata.romfs_path()
    effective = replace(
        metadata,
        icon_path=None if icon_path is None else str(icon_path),
        romfs_dir=None if romfs_path is None else str(romfs_path),
    )
    issues.extend(effective.validate())

    if metadata.package_type != PackageType.SELF_CONTAINED_NSP:
        issues.append(MetadataIssue(
            "package.type",
            "P3-b NSP driver builds self-contained NSP only; package.type is %r "
            "(forwarder NSPs are intentionally out of scope: signature/ban/DMCA risk)" % (
                metadata.package_type.value,)))

    title_id = ""
    raw_title_id = metadata.title_id.strip() if isinstance(metadata.title_id, str) else ""
    if raw_title_id:
        try:
            title_id = format_title_id(raw_title_id)
        except TitleIdError:
            title_id = raw_title_id.upper()

    # ---- romfs 清点 ----
    inventory: Optional[RomfsInventory] = None
    if romfs_path is not None and romfs_path.is_dir():
        inventory = inventory_romfs(romfs_path)
        _check_inventory(inventory, issues)

    # ---- ELF ----
    elf_path = _resolve_arg(elf, base_dir)
    elf_size = 0
    if elf_path is None:
        issues.append(MetadataIssue(
            "elf", "elf is required: pass --elf <path> (elf2nso input; convert NRO to ELF first)"))
    elif _require_file(issues, "elf", elf_path, "ELF"):
        elf_size = elf_path.stat().st_size
        magic = _read_magic(elf_path)
        if magic != b"\x7fELF":
            issues.append(MetadataIssue(
                "elf",
                "elf is not an ELF image (magic %r): convert the NRO to ELF before packaging" % (magic,)))

    # ---- NPDM（可选预构建） ----
    npdm_path = _resolve_arg(npdm, base_dir)
    if npdm_path is not None and _require_file(issues, "npdm", npdm_path, "NPDM"):
        if _read_magic(npdm_path) != NPDM_MAGIC:
            issues.append(MetadataIssue(
                "npdm", "NPDM does not start with %r magic: %s" % (NPDM_MAGIC, npdm_path),
                severity="warning"))

    # ---- NACP（可选预构建） ----
    nacp_path = _resolve_arg(nacp, base_dir)
    if nacp_path is not None and _require_file(issues, "nacp", nacp_path, "NACP"):
        nacp_size = nacp_path.stat().st_size
        if nacp_size != NACP_SIZE:
            issues.append(MetadataIssue(
                "nacp", "NACP is %d bytes, expected %d (0x4000): %s" % (
                    nacp_size, NACP_SIZE, nacp_path), severity="warning"))

    # ---- NPDM 模板 ----
    template_path: Optional[Path] = None
    if npdm_path is None:
        template_path = (_resolve_arg(npdm_template, base_dir)
                         if npdm_template is not None else _default_npdm_template())
        if template_path is None or not template_path.is_file():
            issues.append(MetadataIssue(
                "npdm_template",
                "npdm template not found: %s; pass --npdm (prebuilt) or --npdm-template" % (
                    template_path,)))
        else:
            try:
                template_text = template_path.read_text(encoding="utf-8")
            except OSError as exc:
                issues.append(MetadataIssue(
                    "npdm_template", "cannot read npdm template %s: %s" % (template_path, exc)))
            else:
                if TITLE_ID_PLACEHOLDER not in template_text:
                    issues.append(MetadataIssue(
                        "npdm_template",
                        "npdm template does not contain the %s placeholder: title_id cannot be "
                        "injected and npdmtool would use the template verbatim" % TITLE_ID_PLACEHOLDER,
                        severity="warning"))

    # ---- 输出/暂存路径 ----
    out_value = (_resolve_arg(out_path, base_dir) if out_path is not None
                 else _default_out_path(metadata, base_dir, title_id))
    work_value = (_resolve_arg(work_dir, base_dir) if work_dir is not None
                  else _default_work_dir(metadata, base_dir, title_id))
    if out_value.suffix.lower() != ".nsp":
        issues.append(MetadataIssue("out_path", "out_path must end with .nsp: %s" % out_value))
    if out_value == work_value:
        issues.append(MetadataIssue("out_path", "out_path and work_dir must differ: %s" % out_value))
    if romfs_path is not None and romfs_path.is_dir():
        if _is_within(out_value, romfs_path):
            issues.append(MetadataIssue(
                "out_path", "out_path is inside romfs_dir: the NSP would be packaged into its "
                "own assets: %s" % out_value))
        if _is_within(work_value, romfs_path):
            issues.append(MetadataIssue(
                "work_dir", "work_dir is inside romfs_dir: staging files would be packaged: %s" % work_value))
        if elf_path is not None and _is_within(elf_path, romfs_path):
            issues.append(MetadataIssue(
                "elf", "elf is inside romfs_dir: the ELF/NRO would ship as a game asset: %s" % elf_path,
                severity="warning"))
        if (npdm_path is not None and _is_within(npdm_path, romfs_path)) or (
                nacp_path is not None and _is_within(nacp_path, romfs_path)):
            issues.append(MetadataIssue(
                "romfs_dir", "prebuilt NPDM/NACP is inside romfs_dir and would be packaged as an asset",
                severity="warning"))
    if out_value.exists():
        issues.append(MetadataIssue(
            "out_path", "out_path already exists and will be overwritten: %s" % out_value,
            severity="warning"))
    try:
        if work_value.exists() and any(work_value.iterdir()):
            issues.append(MetadataIssue(
                "work_dir", "work_dir already exists and is not empty; staged exefs/control and "
                "hacBrewPack outputs will be replaced: %s" % work_value, severity="warning"))
    except OSError:
        pass

    # ---- 工具链 ----
    toolchain = toolchain if toolchain is not None else NspToolchain()
    if not isinstance(toolchain, NspToolchain):
        raise TypeError("toolchain must be an NspToolchain")
    tools, tool_sources = toolchain.resolve()
    required = ["elf2nso", "hacbrewpack"]
    if npdm_path is None:
        required.append("npdmtool")
    if nacp_path is None:
        required.append("nacptool")
    for name in required:
        path = tools.get(name)
        if path is None:
            issues.append(MetadataIssue(
                name, "%s not found: pass --%s <path> or put it on PATH" % (name, name)))
        elif not Path(path).is_file():
            issues.append(MetadataIssue(name, "%s path is not a file: %s" % (name, path)))
    nstool_path = tools.get("nstool")
    if nstool_path is None:
        issues.append(MetadataIssue(
            "nstool",
            "nstool not found: post-build verification and signature reporting will be skipped; "
            "pass --nstool <path> to enable them",
            severity="warning"))
    elif not Path(nstool_path).is_file():
        issues.append(MetadataIssue("nstool", "nstool path is not a file: %s" % (nstool_path)))

    # ---- keyset ----
    keyset_ref, keyset_issues = _resolve_keyset(keyset, base_dir)
    issues.extend(keyset_issues)
    if keyset_ref.path is not None and romfs_path is not None and romfs_path.is_dir() and _is_within(keyset_ref.path, romfs_path):
        issues.append(MetadataIssue(
            "keyset", "keyset path is inside romfs_dir: prod.keys would be packaged into the NSP: %s" % (
                keyset_ref.path)))

    # ---- 磁盘余量（romfs 已知时） ----
    if inventory is not None:
        _check_disk(out_value, work_value, inventory.total_bytes, elf_size, issues)

    synthetic_keys_path = (work_value / "synthetic.keys") if keyset_ref.synthetic else None

    plan = NspBuildPlan(
        metadata=metadata,
        elf=elf_path,
        romfs_dir=romfs_path,
        inventory=inventory,
        out_path=out_value,
        work_dir=work_value,
        title_id=title_id,
        keyset=keyset_ref,
        synthetic_keys_path=synthetic_keys_path,
        npdm=npdm_path,
        npdm_template=template_path,
        nacp=nacp_path,
        icon=icon_path,
        tools=tools,
        tool_sources=tool_sources,
        issues=issues,
    )
    if plan.ok:
        plan.steps = _build_steps(plan)
    return plan


def _build_steps(plan: NspBuildPlan) -> List[BuildStep]:
    """生成命令列表（顺序与 scripts/build_pilot_nsp.sh/P1-d 实测一致）。"""
    work = plan.work_dir
    assert work is not None
    exefs = work / "exefs"
    control = work / "control"
    steps: List[BuildStep] = []

    steps.append(BuildStep(
        "elf2nso",
        [str(plan.tools["elf2nso"]), str(plan.elf), str(exefs / "main")],
        cwd=work,
        note="ELF -> NSO；输出 exefs/main（带 LZ4 压缩与 SHA256）",
        outputs=[exefs / "main"],
    ))
    if plan.npdm is None:
        steps.append(BuildStep(
            "npdm",
            [str(plan.tools["npdmtool"]), str(work / "npdm.json"), str(exefs / "main.npdm")],
            cwd=work,
            note="先渲染 examples/nsp/npdm.json（替换 title_id），再 npdmtool 生成 exefs/main.npdm",
            outputs=[exefs / "main.npdm"],
        ))
    if plan.nacp is None:
        steps.append(BuildStep(
            "nacp",
            [
                str(plan.tools["nacptool"]),
                "--create",
                plan.metadata.title_name,
                plan.metadata.title_author,
                plan.metadata.version,
                str(control / "control.nacp"),
                "--titleid=" + plan.title_id,
            ],
            cwd=work,
            note="nacptool 生成 control/control.nacp",
            outputs=[control / "control.nacp"],
        ))
    keyset_arg = (str(plan.synthetic_keys_path) if plan.keyset.synthetic
                  else str(plan.keyset.path))
    steps.append(BuildStep(
        "hacbrewpack",
        [
            str(plan.tools["hacbrewpack"]),
            "--nologo",
            "-k",
            keyset_arg,
            "--romfsdir",
            str(plan.romfs_dir),
        ],
        cwd=work,
        note="在 work 内以相对路径暂存；产物 work/hacbrewpack_nsp/<title_id>.nsp 再复制到 out",
        outputs=[work / "hacbrewpack_nsp" / (plan.title_id + ".nsp")],
    ))
    return steps


# ---------------------------------------------------------------------------
# 构建
# ---------------------------------------------------------------------------

def _default_runner(argv: Sequence[str], cwd: Optional[Path], timeout_s: float) -> Tuple[int, str, str]:
    completed = subprocess.run(
        list(argv),
        cwd=None if cwd is None else str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_s,
        shell=False,
    )
    return (
        completed.returncode,
        completed.stdout.decode("utf-8", errors="replace"),
        completed.stderr.decode("utf-8", errors="replace"),
    )


def _render_npdm_template(template: Path, title_id: str, destination: Path) -> bool:
    """把模板中的占位 TitleID 替换为实际 title_id，返回是否发生了替换。"""
    text = Path(template).read_text(encoding="utf-8")
    replaced = text.replace(TITLE_ID_PLACEHOLDER, title_id)
    destination.write_text(replaced, encoding="utf-8")
    return replaced != text


def _synthetic_keyset_text() -> str:
    """构造一个假 keyset（hacBrewPack 只做格式解析；产物不可安装）。"""
    return (
        "# GalNX P3-b synthetic keyset: fabricated values for STRUCTURE-ONLY smoke tests.\n"
        "# THIS IS NOT A REAL KEYSET AND THE RESULTING NSP IS NOT INSTALLABLE.\n"
        "header_key = " + "00" * 32 + "\n"
        "key_area_key_application_00 = " + "00" * 16 + "\n"
    )


def build_nsp(
    plan: NspBuildPlan,
    *,
    timeout_s: float = 1800.0,
    runner: Optional[Runner] = None,
) -> BuildResult:
    """执行 plan.steps；失败即停，保留 work 目录与每步日志。"""
    if not isinstance(plan, NspBuildPlan):
        raise TypeError("plan must be an NspBuildPlan")
    if not plan.ok:
        return BuildResult(ok=False, error="build plan is invalid: %d error(s)" % len(plan.errors),
                           out_path=plan.out_path, work_dir=plan.work_dir)
    runner = runner or _default_runner
    assert plan.work_dir is not None and plan.out_path is not None
    work = plan.work_dir
    started = time.monotonic()

    # ---- 暂存：每次都重建 exefs/control（hacBrewPack 会就地改写 main.npdm/control.nacp） ----
    work.mkdir(parents=True, exist_ok=True)
    logs_dir = work / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    exefs = work / "exefs"
    control = work / "control"
    _reset_dir(exefs)
    _reset_dir(control)
    _reset_dir(work / "hacbrewpack_nsp")
    _reset_dir(work / "hacbrewpack_nca")
    _reset_dir(work / "nstool-nca")

    staged: List[StepResult] = []
    try:
        assert plan.icon is not None
        icon_destination = control / "icon_AmericanEnglish.dat"
        shutil.copyfile(plan.icon, icon_destination)
        staged.append(StepResult(
            name="stage-icon", cwd=str(work), exit_code=0, duration_s=0.0,
            note="copied %s -> %s" % (plan.icon, icon_destination)))
        if plan.npdm is not None:
            npdm_destination = exefs / "main.npdm"
            shutil.copyfile(plan.npdm, npdm_destination)
            staged.append(StepResult(
                name="stage-npdm", cwd=str(work), exit_code=0, duration_s=0.0,
                note="copied %s -> %s" % (plan.npdm, npdm_destination)))
        if plan.nacp is not None:
            nacp_destination = control / "control.nacp"
            shutil.copyfile(plan.nacp, nacp_destination)
            staged.append(StepResult(
                name="stage-nacp", cwd=str(work), exit_code=0, duration_s=0.0,
                note="copied %s -> %s" % (plan.nacp, nacp_destination)))
        if plan.keyset.synthetic and plan.synthetic_keys_path is not None:
            plan.synthetic_keys_path.write_text(_synthetic_keyset_text(), encoding="utf-8")
    except OSError as exc:
        return BuildResult(
            ok=False, out_path=plan.out_path, work_dir=work, steps=staged,
            error="input staging failed: %s" % exc, duration_s=round(time.monotonic() - started, 3))

    steps: List[StepResult] = []
    for step in plan.steps:
        cwd = step.cwd or work
        cwd.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / (step.name + ".log")
        if step.name == "npdm" and plan.npdm is None and plan.npdm_template is not None:
            try:
                _render_npdm_template(plan.npdm_template, plan.title_id, work / "npdm.json")
            except OSError as exc:
                return BuildResult(
                    ok=False, out_path=plan.out_path, work_dir=work, steps=staged + steps,
                    error="npdm template render failed: %s" % exc,
                    duration_s=round(time.monotonic() - started, 3))
        started_step = time.monotonic()
        try:
            exit_code, stdout_text, stderr_text = runner(step.argv, cwd, timeout_s)
        except subprocess.TimeoutExpired as exc:
            steps.append(StepResult(
                name=step.name, argv=list(step.argv), cwd=str(cwd), exit_code=-1,
                duration_s=round(time.monotonic() - started_step, 3),
                stderr_tail="timeout after %ss" % timeout_s, log_path=str(log_path)))
            return BuildResult(
                ok=False, out_path=plan.out_path, work_dir=work, steps=staged + steps,
                error="step %s timed out after %ss (log: %s)" % (step.name, timeout_s, log_path),
                duration_s=round(time.monotonic() - started, 3))
        except OSError as exc:
            steps.append(StepResult(
                name=step.name, argv=list(step.argv), cwd=str(cwd), exit_code=-1,
                duration_s=round(time.monotonic() - started_step, 3),
                stderr_tail="%s" % exc, log_path=str(log_path)))
            return BuildResult(
                ok=False, out_path=plan.out_path, work_dir=work, steps=staged + steps,
                error="step %s could not start: %s (log: %s)" % (step.name, exc, log_path),
                duration_s=round(time.monotonic() - started, 3))
        duration = round(time.monotonic() - started_step, 3)
        clean_stdout = _sanitize_log(stdout_text)
        clean_stderr = _sanitize_log(stderr_text)
        header = "# step: %s\n# cwd: %s\n# argv: %s\n# exit: %d\n# duration_s: %.3f\n" % (
            step.name, cwd, json.dumps(list(step.argv), ensure_ascii=False), exit_code, duration)
        try:
            log_path.write_text(
                header + "--- stdout ---\n" + clean_stdout + "--- stderr ---\n" + clean_stderr,
                encoding="utf-8")
        except OSError:
            pass
        steps.append(StepResult(
            name=step.name, argv=list(step.argv), cwd=str(cwd), exit_code=exit_code,
            duration_s=duration, stdout_tail=_tail(clean_stdout), stderr_tail=_tail(clean_stderr),
            log_path=str(log_path), note=step.note))
        if exit_code != 0:
            return BuildResult(
                ok=False, out_path=plan.out_path, work_dir=work, steps=staged + steps,
                error="step %s failed with exit code %d (log: %s)" % (
                    step.name, exit_code, log_path),
                duration_s=round(time.monotonic() - started, 3))

    # ---- 定位并复制产物 ----
    produced = work / "hacbrewpack_nsp" / (plan.title_id + ".nsp")
    if not produced.is_file():
        try:
            candidates = sorted((work / "hacbrewpack_nsp").glob("*.nsp"))
        except OSError:
            candidates = []
        if len(candidates) == 1:
            produced = candidates[0]
        else:
            return BuildResult(
                ok=False, out_path=plan.out_path, work_dir=work, steps=staged + steps,
                error="hacBrewPack did not produce the expected %s (candidates: %s)" % (
                    plan.title_id + ".nsp", ", ".join(str(item.name) for item in candidates) or "none"),
                duration_s=round(time.monotonic() - started, 3))
    try:
        plan.out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(produced, plan.out_path)
        size = plan.out_path.stat().st_size
        if size == 0:
            raise OSError("artifact is empty")
        artifact = {
            "path": str(plan.out_path),
            "size": size,
            "sha256": sha256_file(plan.out_path),
            "produced_by": str(produced),
        }
    except OSError as exc:
        return BuildResult(
            ok=False, out_path=plan.out_path, work_dir=work, steps=staged + steps,
            error="artifact copy failed: %s" % exc,
            duration_s=round(time.monotonic() - started, 3))
    return BuildResult(
        ok=True, out_path=plan.out_path, work_dir=work, steps=staged + steps,
        artifact=artifact, duration_s=round(time.monotonic() - started, 3))


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

def verify_nsp(
    nsp: Union[str, Path],
    nstool: Union[str, Path],
    *,
    keyset: Optional[KeysetRef] = None,
    expected_title_id: Optional[str] = None,
    work_dir: Optional[Union[str, Path]] = None,
    timeout_s: float = 300.0,
    runner: Optional[Runner] = None,
) -> VerifyResult:
    """用 nstool 只读校验 NSP：PFS0 结构 + 3 个 NCA 的 Content Type/ProgID。

    未签名 homebrew NSP 的 "Signature: FAIL" 只记 warning（hacBrewPack 用的 RSA
    公钥不是 Nintendo 的，签名必然对不上）。
    """
    runner = runner or _default_runner
    nsp_path = Path(nsp)
    nstool_path = Path(nstool)
    checks: List[Check] = []
    logs: List[str] = []
    keyset_ref = keyset if isinstance(keyset, KeysetRef) else KeysetRef()

    if not nsp_path.is_file():
        return VerifyResult(
            ok=False, nsp=nsp_path, nstool=nstool_path,
            checks=[Check("verify.nsp", "NSP artifact", "fail",
                          "NSP not found: %s" % nsp_path)],
            error="nstool verify: NSP not found")
    if not nstool_path.is_file():
        return VerifyResult(
            ok=False, nsp=nsp_path, nstool=nstool_path,
            checks=[Check("verify.nstool", "nstool", "fail",
                          "nstool not found: %s" % nstool_path)],
            error="nstool verify: nstool not found")

    keyset_args: List[str] = []
    if keyset_ref.synthetic:
        checks.append(Check(
            "verify.keyset", "keyset", "skip",
            "synthetic keyset: NCA headers cannot be decrypted, NSP/PFS0 layer only"))
    elif keyset_ref.path is not None:
        keyset_args = ["-k", str(keyset_ref.path)]
    else:
        checks.append(Check(
            "verify.keyset", "keyset", "warn",
            "no keyset: nstool can only print the PFS0 header; NCA checks will be limited"))

    def run(arguments: List[str]) -> Tuple[int, str, str]:
        try:
            exit_code, stdout_text, stderr_text = runner(
                [str(nstool_path)] + arguments, None, timeout_s)
        except subprocess.TimeoutExpired:
            return -1, "", "timeout after %ss" % timeout_s
        except OSError as exc:
            return -1, "", "could not start nstool: %s" % exc
        clean_stdout = _sanitize_log(stdout_text)
        clean_stderr = _sanitize_log(stderr_text)
        logs.append(clean_stdout + "\n" + clean_stderr)
        return exit_code, clean_stdout, clean_stderr

    exit_code, stdout_text, stderr_text = run(["-y"] + keyset_args + [str(nsp_path)])
    if exit_code != 0:
        checks.append(Check(
            "verify.nstool.nsp", "nstool NSP layer", "fail",
            "nstool exited %d; tail: %s" % (exit_code, _tail((stderr_text or stdout_text), 5))))
        return VerifyResult(
            ok=False, nsp=nsp_path, nstool=nstool_path, checks=checks,
            artifact={"path": str(nsp_path), "size": nsp_path.stat().st_size,
                      "sha256": sha256_file(nsp_path)},
            error="nstool failed on the NSP layer")
    checks.append(Check("verify.nstool.nsp", "nstool NSP layer", "ok",
                        "nstool parsed the NSP container"))

    parsed = parse_nstool_output(stdout_text)
    if not parsed.get("ncas") and not keyset_ref.synthetic and keyset_ref.path is not None and work_dir is not None:
        nca_dir = Path(work_dir) / "nstool-nca"
        try:
            _reset_dir(nca_dir)
        except OSError as exc:
            checks.append(Check("verify.nstool.extract", "NCA extraction", "warn",
                                "cannot prepare NCA dir %s: %s" % (nca_dir, exc)))
        else:
            exit_code, stdout_text, stderr_text = run(
                ["-x", str(nca_dir)] + keyset_args + [str(nsp_path)])
            if exit_code != 0:
                checks.append(Check(
                    "verify.nstool.extract", "NCA extraction", "warn",
                    "nstool -x exited %d; NCA-level checks skipped: %s" % (
                        exit_code, _tail((stderr_text or stdout_text), 3))))
            else:
                try:
                    extracted = sorted(nca_dir.glob("*.nca"))
                except OSError:
                    extracted = []
                if not extracted:
                    checks.append(Check("verify.nstool.extract", "NCA extraction", "warn",
                                        "nstool -x produced no .nca files"))
                else:
                    nca_headers: List[Dict[str, str]] = []
                    failed = False
                    for index, nca in enumerate(extracted):
                        exit_code, stdout_text, stderr_text = run(
                            ["-y"] + keyset_args + [str(nca)])
                        if exit_code != 0:
                            checks.append(Check(
                                "verify.nca.%d" % index, "NCA %d" % index, "fail",
                                "nstool exited %d: %s" % (
                                    exit_code, _tail((stderr_text or stdout_text), 3))))
                            failed = True
                            break
                        nca_headers.extend(parse_nstool_output(stdout_text).get("ncas") or [])
                    if not failed:
                        parsed = dict(parsed)
                        parsed["ncas"] = nca_headers

    checks.extend(check_nstool(parsed, expected_title_id=expected_title_id))

    signature_failures = sum(log.count("Signature: FAIL") for log in logs)
    if signature_failures:
        checks.append(Check(
            "verify.signature", "NCA signature", "warn",
            "%d 'Signature: FAIL' line(s): expected for unsigned homebrew NSP; hacBrewPack's "
            "RSA key is not Nintendo's, so signatures cannot validate" % signature_failures))

    ncas = len(parsed.get("ncas") or [])
    if ncas == 0:
        checks.append(Check(
            "verify.ncas", "NCA headers", "warn",
            "no [NCA Header] sections: provide a matching keyset and work_dir to enable NCA checks"))

    fail_count = sum(1 for check in checks if check.status == "fail")
    warn_count = sum(1 for check in checks if check.status == "warn")
    checks.append(Check(
        "verify.summary", "nstool verify",
        "fail" if fail_count else "ok",
        "%d checks: %d fail, %d warn, %d NCAs" % (len(checks), fail_count, warn_count, ncas)))
    artifact = {
        "path": str(nsp_path),
        "size": nsp_path.stat().st_size,
        "sha256": sha256_file(nsp_path),
    }
    return VerifyResult(
        ok=not has_failures(checks), nsp=nsp_path, nstool=nstool_path, checks=checks,
        ncas=ncas, artifact=artifact)


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------

def _file_info(path: Optional[Path]) -> dict:
    if path is None:
        return {"path": "", "size": 0, "sha256": ""}
    target = Path(path)
    if not target.is_file():
        return {"path": str(target), "size": 0, "sha256": ""}
    try:
        return {"path": str(target), "size": target.stat().st_size,
                "sha256": sha256_file(target)}
    except OSError:
        return {"path": str(target), "size": 0, "sha256": ""}


def _tool_info(tool_path: Optional[Path], source: str) -> dict:
    info = _file_info(tool_path)
    return {"path": info["path"], "source": source,
            "size": info["size"], "sha256": info["sha256"]}


def write_provenance(
    *,
    path: Union[str, Path],
    plan: NspBuildPlan,
    result: Optional[BuildResult] = None,
    verify: Optional[VerifyResult] = None,
    romfs_digest: bool = True,
    environment: Optional[Mapping] = None,
) -> Path:
    """写 <out>.provenance.json；返回实际路径。

    版本锁定建议：锁 inputs 的 sha256 与 tools 的 sha256，不要锁 NSP sha256
    （hacBrewPack 的 RSA-PSS 随机盐导致同输入两次产物不同）。
    """
    target = Path(path)
    romfs_info = {
        "root": _path_text(plan.romfs_dir),
        "files": plan.inventory.files if plan.inventory else 0,
        "total_bytes": plan.inventory.total_bytes if plan.inventory else 0,
        "sha256": "",
    }
    if romfs_digest and plan.romfs_dir is not None and plan.romfs_dir.is_dir():
        try:
            romfs_info["sha256"] = digest_romfs(plan.romfs_dir)
        except OSError:
            romfs_info["sha256"] = ""
    payload = {
        "schema": "galnx-nsp-provenance",
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "galnx_version": GALNX_VERSION,
        "dry_run": result is None,
        "metadata": plan.metadata.to_dict(),
        "title_id": plan.title_id,
        "inputs": {
            "elf": _file_info(plan.elf),
            "romfs": romfs_info,
            "icon": _file_info(plan.icon),
            "npdm": _file_info(plan.npdm),
            "nacp": _file_info(plan.nacp),
            "npdm_template": _file_info(plan.npdm_template),
        },
        "keyset": plan.keyset.to_dict(),
        "tools": {
            name: _tool_info(tool_path, plan.tool_sources.get(name, ""))
            for name, tool_path in plan.tools.items()
        },
        "commands": [step.to_dict() for step in plan.steps],
        "build": None if result is None else result.to_dict(),
        "artifact": None if result is None else result.artifact,
        "verify": None if verify is None else {
            "ok": verify.ok,
            "ncas": verify.ncas,
            "checks": checks_to_dict(verify.checks),
            "artifact": verify.artifact,
        },
        "environment": dict(environment) if environment is not None else {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cwd": os.getcwd(),
        },
    }
    _atomic_write_json(target, payload)
    return target


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_path(value: Optional[str]) -> Optional[Path]:
    if value is None:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _load_metadata(manifest_path: Path) -> Tuple[Optional[PackageMetadata], List[str]]:
    from .. import manifest as manifest_module

    data, errors = manifest_module.load_and_validate(manifest_path)
    if data is None or errors:
        return None, list(errors)
    try:
        return PackageMetadata.from_manifest(data, manifest_path.resolve().parent), []
    except PackageMetadataError as exc:
        return None, ["package: %s" % exc]


def _plan_checks(plan: NspBuildPlan) -> List[Check]:
    checks: List[Check] = []
    seen: Dict[str, int] = {}

    def add_issue(field_name: str, issue: MetadataIssue) -> None:
        key = "nsp." + field_name
        count = seen.get(key, 0) + 1
        seen[key] = count
        checks.append(Check(
            id=key if count == 1 else "%s.%d" % (key, count),
            name=field_name,
            status="fail" if issue.is_error else "warn",
            detail=issue.message,
        ))

    for issue in plan.issues:
        add_issue(issue.field, issue)

    if plan.inventory is not None:
        checks.append(Check(
            "nsp.romfs", "romfs inventory", "ok",
            "%d files, %s, max path %d (%s)" % (
                plan.inventory.files, _format_bytes(plan.inventory.total_bytes),
                plan.inventory.max_path_len, plan.inventory.max_path or "n/a")))
    if plan.keyset.synthetic:
        checks.append(Check("nsp.keyset.mode", "keyset mode", "warn",
                            "synthetic keyset: NOT INSTALLABLE (structure-only smoke test)"))
    elif plan.keyset.path is not None:
        checks.append(Check(
            "nsp.keyset.mode", "keyset mode", "ok",
            "explicit real keyset: %d bytes, sha256 %s" % (
                plan.keyset.size, plan.keyset.sha256)))
    for name in ("elf2nso", "npdmtool", "nacptool", "hacbrewpack", "nstool"):
        tool_path = plan.tools.get(name)
        if tool_path is not None and Path(tool_path).is_file():
            checks.append(Check(
                "nsp.tool.%s" % name, "tool %s" % name, "ok",
                "%s (%s)" % (tool_path, plan.tool_sources.get(name, ""))))

    checks.append(Check(
        "nsp.plan", "NSP build plan",
        "ok" if plan.ok else "fail",
        "%d steps, %d error(s), %d warning(s)" % (
            len(plan.steps), len(plan.errors), len(plan.warnings))))
    return checks


def _render_checks(checks: Iterable[Check]) -> None:
    flat = list(checks)
    order = {"fail": 0, "warn": 1, "skip": 2, "ok": 3}
    flat.sort(key=lambda item: order.get(item.status, 4))
    if not flat:
        print("checks: none")
        return
    marks = {"ok": "ok", "warn": "warn", "fail": "FAIL", "skip": "skip"}
    width = min(max(len(check.name) for check in flat), 32)
    for check in flat:
        print("  [%-4s] %-*s  %s" % (marks.get(check.status, check.status), width, check.name, check.detail))
    counts = {status: sum(1 for check in flat if check.status == status) for status in marks}
    print("%d checks: %d fail, %d warn, %d skip" % (
        len(flat), counts["fail"], counts["warn"], counts["skip"]))


def _print_plan_text(plan: NspBuildPlan) -> None:
    print("NSP build plan (dry-run)")
    print("  title_id : %s" % (plan.title_id or "<missing>"))
    print("  elf      : %s" % _path_text(plan.elf))
    if plan.inventory is not None:
        print("  romfs    : %s (%d files, %s, max path %d)" % (
            _path_text(plan.romfs_dir), plan.inventory.files,
            _format_bytes(plan.inventory.total_bytes), plan.inventory.max_path_len))
    else:
        print("  romfs    : %s" % _path_text(plan.romfs_dir))
    print("  out      : %s" % _path_text(plan.out_path))
    print("  work     : %s" % _path_text(plan.work_dir))
    if plan.keyset.synthetic:
        print("  keyset   : synthetic (NOT INSTALLABLE)")
    else:
        print("  keyset   : %s (%d bytes, sha256 %s)" % (
            _path_text(plan.keyset.path), plan.keyset.size, plan.keyset.sha256))
    if plan.npdm is not None:
        print("  npdm     : %s (prebuilt)" % plan.npdm)
    else:
        print("  npdm     : template %s -> npdmtool" % _path_text(plan.npdm_template))
    if plan.nacp is not None:
        print("  nacp     : %s (prebuilt)" % plan.nacp)
    else:
        print("  nacp     : nacptool --create")
    for name in ("elf2nso", "npdmtool", "nacptool", "hacbrewpack", "nstool"):
        tool_path = plan.tools.get(name)
        print("  tool %-12s %s (%s)" % (name, _path_text(tool_path) or "MISSING",
                                        plan.tool_sources.get(name, "")))
    if plan.steps:
        print("  steps:")
        for index, step in enumerate(plan.steps, 1):
            print("    %d. %s  cwd=%s" % (index, step.name, step.cwd))
            print("       %s" % json.dumps(list(step.argv), ensure_ascii=False))


def register(subparsers) -> None:
    """在 CLI 的 package 子命令上注册 "nsp"。"""
    parser = subparsers.add_parser(
        "nsp",
        help="NSP 打包计划/构建/校验（自包含 NSP；keyset 必须显式）",
        description="Plan/build a self-contained NSP (ELF -> elf2nso -> hacBrewPack -> nstool).",
    )
    parser.add_argument("--manifest", help="game manifest (YAML); required for plan/build")
    parser.add_argument("--elf", help="ELF input for elf2nso (required)")
    parser.add_argument("--romfs-dir", help="romfs directory to embed")
    parser.add_argument("--out", help="output .nsp path (default build/nsp/<name>-<title_id>.nsp)")
    parser.add_argument("--work", help="staging work dir (default build/nsp/work-<title_id>)")
    parser.add_argument("--keyset",
                        help="explicit prod.keys path, or 'synthetic' for structure-only smoke tests; "
                             "required for plan/build")
    parser.add_argument("--icon", help="256x256 JPEG icon (default from manifest)")
    parser.add_argument("--npdm", help="prebuilt NPDM (skips npdmtool)")
    parser.add_argument("--npdm-template", help="npdm.json template (default examples/nsp/npdm.json)")
    parser.add_argument("--nacp", help="prebuilt NACP (skips nacptool)")
    parser.add_argument("--elf2nso", help="elf2nso path (default PATH)")
    parser.add_argument("--npdmtool", help="npdmtool path (default PATH)")
    parser.add_argument("--nacptool", help="nacptool path (default PATH)")
    parser.add_argument("--hacbrewpack", help="hacBrewPack path (default PATH)")
    parser.add_argument("--nstool", help="nstool path (default PATH)")
    parser.add_argument("--dry-run", action="store_true", help="plan only (default)")
    parser.add_argument("--build", action="store_true", help="execute the build")
    parser.add_argument("--no-verify", action="store_true", help="skip nstool verification")
    parser.add_argument("--no-romfs-digest", action="store_true",
                        help="skip the romfs sha256 in provenance (faster for huge romfs)")
    parser.add_argument("--step-timeout", type=float, default=1800.0,
                        help="per-step timeout in seconds (default 1800)")
    parser.add_argument("--provenance", help="provenance path (default <out>.provenance.json)")
    parser.add_argument("--json", action="store_true", help="emit one JSON document on stdout")
    parser.set_defaults(func=cmd_nsp)

    nsp_subparsers = parser.add_subparsers(dest="nsp_command", metavar="{verify}")
    verify_parser = nsp_subparsers.add_parser(
        "verify",
        help="verify an existing NSP with nstool (read-only; optional provenance cross-check)",
        description="Verify an existing NSP: nstool -y plus NCA extraction, title-id/Type checks, "
                    "and an optional provenance cross-check. Never builds or modifies the NSP.",
    )
    verify_parser.add_argument("--nsp", required=True, help="existing .nsp to verify")
    verify_parser.add_argument("--manifest", required=True,
                               help="game manifest (YAML) for title_id/name/author/version")
    verify_parser.add_argument("--nstool", help="nstool path (default PATH)")
    verify_parser.add_argument("--keyset",
                               help="explicit prod.keys path, or 'synthetic'; omit to skip keyed checks")
    verify_parser.add_argument("--expect-title-id",
                               help="expected title id (default: manifest switch.title_id)")
    verify_parser.add_argument("--provenance",
                               help="provenance JSON to cross-check against the NSP and manifest")
    verify_parser.add_argument("--work-dir",
                               help="keep nstool NCA extraction output here (default: temp dir, removed)")
    verify_parser.add_argument("--step-timeout", type=float, default=300.0,
                               help="nstool timeout in seconds (default 300)")
    verify_parser.add_argument("--json", action="store_true", help="emit one JSON document on stdout")
    verify_parser.set_defaults(func=cmd_nsp_verify)


def cmd_nsp(args) -> int:
    """galnx package nsp 入口；返回 0=成功，1=构建/校验失败，2=输入/计划错误。"""
    manifest_path = _cli_path(args.manifest)
    if manifest_path is None:
        print("package nsp: --manifest is required", file=sys.stderr)
        return 2
    metadata, errors = _load_metadata(manifest_path)
    if metadata is None:
        payload = {
            "tool": "package nsp",
            "manifest": str(manifest_path),
            "checks": [],
            "ok": False,
            "errors": errors,
        }
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            for error in errors:
                print("manifest error: %s" % error, file=sys.stderr)
        return 2

    if args.build and args.dry_run:
        print("package nsp: --build and --dry-run are mutually exclusive", file=sys.stderr)
        return 2

    toolchain = NspToolchain(
        elf2nso=args.elf2nso, npdmtool=args.npdmtool, nacptool=args.nacptool,
        hacbrewpack=args.hacbrewpack, nstool=args.nstool,
    )
    try:
        plan = plan_nsp_build(
            metadata,
            elf=_cli_path(args.elf),
            romfs_dir=_cli_path(args.romfs_dir),
            out_path=_cli_path(args.out),
            work_dir=_cli_path(args.work),
            keyset=args.keyset,
            toolchain=toolchain,
            icon=_cli_path(args.icon),
            npdm=_cli_path(args.npdm),
            npdm_template=_cli_path(args.npdm_template),
            nacp=_cli_path(args.nacp),
        )
    except (PackageMetadataError, TitleIdError, OSError, TypeError) as exc:
        payload = {"tool": "package nsp", "manifest": str(manifest_path),
                   "checks": [], "ok": False, "errors": ["plan: %s" % exc]}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("plan error: %s" % exc, file=sys.stderr)
        return 2

    checks = _plan_checks(plan)
    mode = "build" if args.build else "plan"
    if not plan.ok or mode == "plan":
        payload = {
            "tool": "package nsp",
            "mode": mode,
            "manifest": str(manifest_path),
            "plan": plan.to_dict(),
            "checks": checks_to_dict(checks),
            "ok": plan.ok,
            "errors": [issue.to_dict() for issue in plan.errors],
        }
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            _print_plan_text(plan)
            _render_checks(checks)
        return 0 if plan.ok else 2

    print("building NSP: %s" % plan.out_path, file=sys.stderr)
    result = build_nsp(plan, timeout_s=args.step_timeout)
    checks.append(Check(
        "nsp.build", "hacBrewPack build", "ok" if result.ok else "fail",
        ("artifact: %s (%s, sha256 %s)" % (
            result.artifact["path"], _format_bytes(result.artifact["size"]),
            result.artifact["sha256"])) if result.ok and result.artifact else result.error))
    verify: Optional[VerifyResult] = None
    if result.ok and not args.no_verify and result.artifact is not None:
        nstool_path = plan.tools.get("nstool")
        if nstool_path is None:
            checks.append(Check("nsp.verify", "nstool verification", "skip",
                                "nstool not available"))
        else:
            print("verifying with nstool ...", file=sys.stderr)
            verify = verify_nsp(
                result.artifact["path"], nstool_path, keyset=plan.keyset,
                expected_title_id=plan.title_id, work_dir=plan.work_dir,
                timeout_s=min(args.step_timeout, 300.0))
            checks.extend(verify.checks)
            checks.append(Check(
                "nsp.verify", "nstool verification", "ok" if verify.ok else "fail",
                "%d NCAs checked; %d fail, %d warn" % (
                    verify.ncas,
                    sum(1 for check in verify.checks if check.status == "fail"),
                    sum(1 for check in verify.checks if check.status == "warn"))))
    provenance_path: Optional[Path] = None
    if result.ok and result.artifact is not None:
        provenance_path = (Path(args.provenance) if args.provenance
                           else Path(result.artifact["path"] + ".provenance.json"))
        try:
            write_provenance(
                path=provenance_path, plan=plan, result=result, verify=verify,
                romfs_digest=not args.no_romfs_digest)
        except OSError as exc:
            checks.append(Check("nsp.provenance", "provenance", "fail",
                                "cannot write %s: %s" % (provenance_path, exc)))
            provenance_path = None
        else:
            checks.append(Check("nsp.provenance", "provenance", "ok",
                                str(provenance_path)))

    ok = result.ok and (verify is None or verify.ok) and not has_failures(checks)
    payload = {
        "tool": "package nsp",
        "mode": "build",
        "manifest": str(manifest_path),
        "plan": plan.to_dict(),
        "build": result.to_dict(),
        "verify": None if verify is None else verify.to_dict(),
        "provenance": _path_text(provenance_path),
        "checks": checks_to_dict(checks),
        "ok": ok,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if result.artifact:
            print("artifact: %s (%s, sha256 %s)" % (
                result.artifact["path"], _format_bytes(result.artifact["size"]),
                result.artifact["sha256"]))
        else:
            print("build failed: %s" % result.error, file=sys.stderr)
        if provenance_path is not None:
            print("provenance: %s" % provenance_path)
        _render_checks(checks)
    return 0 if ok else 1


def _resolve_nstool(value: Optional[str]) -> Tuple[Optional[Path], str]:
    """解析 nstool：显式路径优先，其次 PATH；返回 (path, source)。"""
    if value:
        path = _cli_path(str(value))
        if path is not None:
            return path, "explicit"
    for name in ("nstool", "nstool.exe"):
        found = shutil.which(name)
        if found:
            return Path(found), "PATH"
    return None, "missing"


_PROVENANCE_KEYSET_FIELDS = ("mode", "path", "size", "sha256", "note")


def _check_provenance(
    path: Path,
    *,
    nsp: Path,
    expected_title_id: str,
    keyset: Optional[KeysetRef] = None,
) -> List[Check]:
    """交叉核对 provenance JSON 与实际 NSP（只读；不信任 provenance 里的记录）。"""
    checks: List[Check] = []

    def add(check_id: str, status: str, detail: str) -> None:
        checks.append(Check(check_id, "provenance", status, detail))

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        add("verify.provenance", "fail", "cannot read %s: %s" % (path, exc))
        return checks
    try:
        payload = json.loads(text)
    except ValueError as exc:
        add("verify.provenance", "fail", "%s is not valid JSON: %s" % (path, exc))
        return checks
    if not isinstance(payload, dict):
        add("verify.provenance", "fail", "provenance root is not a JSON object")
        return checks

    if payload.get("schema") != "galnx-nsp-provenance":
        add("verify.provenance.schema", "fail",
            "unexpected schema %r (want 'galnx-nsp-provenance')" % payload.get("schema"))
    elif payload.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        add("verify.provenance.schema", "fail",
            "unexpected schema_version %r (want %r)" % (
                payload.get("schema_version"), PROVENANCE_SCHEMA_VERSION))
    else:
        add("verify.provenance.schema", "ok",
            "schema galnx-nsp-provenance v%d" % PROVENANCE_SCHEMA_VERSION)

    if payload.get("dry_run") is False:
        add("verify.provenance.dry_run", "ok", "recorded from a real build (dry_run=false)")
    else:
        add("verify.provenance.dry_run", "fail",
            "dry_run is not false: provenance was written without a build")

    recorded_title = str(payload.get("title_id") or "").strip().upper()
    if recorded_title == expected_title_id.upper():
        add("verify.provenance.title_id", "ok", recorded_title)
    else:
        add("verify.provenance.title_id", "fail",
            "provenance title_id %r != expected %r" % (recorded_title, expected_title_id.upper()))

    try:
        actual_size = nsp.stat().st_size
        actual_sha = sha256_file(nsp)
    except OSError as exc:
        add("verify.provenance.artifact", "fail", "cannot hash NSP %s: %s" % (nsp, exc))
        actual_size = -1
        actual_sha = ""
    artifact = payload.get("artifact")
    if actual_size >= 0:
        if not isinstance(artifact, dict):
            add("verify.provenance.artifact", "fail", "provenance has no artifact object")
        else:
            try:
                recorded_size = int(artifact.get("size"))
            except (TypeError, ValueError):
                recorded_size = -1
            recorded_sha = str(artifact.get("sha256") or "").lower()
            if recorded_size == actual_size and recorded_sha == actual_sha.lower():
                add("verify.provenance.artifact", "ok",
                    "%d bytes, sha256 %s (matches the NSP)" % (actual_size, actual_sha))
            else:
                add("verify.provenance.artifact", "fail",
                    "artifact mismatch: provenance size=%s sha256=%s, actual size=%s sha256=%s" % (
                        recorded_size, recorded_sha or "<missing>", actual_size, actual_sha))

    recorded_keyset = payload.get("keyset")
    if keyset is None or (keyset.path is None and not keyset.synthetic):
        add("verify.provenance.keyset", "skip",
            "no --keyset supplied; the provenance keyset record was not cross-checked")
    elif not isinstance(recorded_keyset, dict):
        add("verify.provenance.keyset", "fail", "provenance has no keyset object")
    else:
        extra = sorted(set(recorded_keyset) - set(_PROVENANCE_KEYSET_FIELDS))
        if extra:
            add("verify.provenance.keyset", "warn",
                "unexpected keyset fields %s (provenance must record metadata only)" % extra)
        if keyset.synthetic:
            if recorded_keyset.get("mode") == "synthetic":
                add("verify.provenance.keyset", "ok", "synthetic keyset recorded")
            else:
                add("verify.provenance.keyset", "fail",
                    "this run used a synthetic keyset but provenance mode is %r"
                    % recorded_keyset.get("mode"))
        else:
            problems: List[str] = []
            if recorded_keyset.get("mode") != "real":
                problems.append("mode=%r" % recorded_keyset.get("mode"))
            try:
                recorded_ks_size = int(recorded_keyset.get("size"))
            except (TypeError, ValueError):
                recorded_ks_size = -1
            if recorded_ks_size != keyset.size:
                problems.append("size=%s (actual %d)" % (recorded_ks_size, keyset.size))
            recorded_ks_sha = str(recorded_keyset.get("sha256") or "").lower()
            if recorded_ks_sha != keyset.sha256.lower():
                problems.append("sha256=%s (actual %s)" % (
                    recorded_ks_sha or "<missing>", keyset.sha256))
            if problems:
                add("verify.provenance.keyset", "fail",
                    "keyset record mismatch: %s" % "; ".join(problems))
            else:
                add("verify.provenance.keyset", "ok",
                    "%d bytes, sha256 %s (matches --keyset)" % (keyset.size, keyset.sha256))
                recorded_ks_path = str(recorded_keyset.get("path") or "")
                if recorded_ks_path and Path(recorded_ks_path) != keyset.path:
                    add("verify.provenance.keyset.path", "warn",
                        "path differs: provenance %r, --keyset %r"
                        % (recorded_ks_path, str(keyset.path)))

    leaked = [marker for marker in ("header_key", "key_area_key") if marker in text.lower()]
    if leaked:
        add("verify.provenance.no_secret", "fail",
            "provenance contains key-material markers %s" % ", ".join(leaked))
    else:
        add("verify.provenance.no_secret", "ok", "no key-material markers in provenance text")
    return checks


def cmd_nsp_verify(args) -> int:
    """galnx package nsp verify 入口；返回 0=通过，1=有 fail，2=输入错误。"""
    manifest_path = _cli_path(getattr(args, "manifest", None))
    nsp_path = _cli_path(getattr(args, "nsp", None))
    manifest_text = _path_text(manifest_path)
    nsp_text = _path_text(nsp_path)

    def fail(errors: List[str]) -> int:
        payload = {
            "tool": "package nsp",
            "mode": "verify",
            "manifest": manifest_text,
            "nsp": nsp_text,
            "checks": [],
            "ok": False,
            "errors": list(errors),
        }
        if getattr(args, "json", False):
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            for error in errors:
                print("package nsp verify: %s" % error, file=sys.stderr)
        return 2

    if manifest_path is None:
        return fail(["--manifest is required"])
    metadata, errors = _load_metadata(manifest_path)
    if metadata is None:
        return fail(errors or ["invalid manifest"])
    if nsp_path is None or not nsp_path.is_file():
        return fail(["NSP not found: %s" % nsp_text])
    nstool_path, nstool_source = _resolve_nstool(getattr(args, "nstool", None))
    if nstool_path is None or not nstool_path.is_file():
        return fail(["nstool not found: pass --nstool <path> or put it on PATH"])

    expected_title_id = getattr(args, "expect_title_id", None) or metadata.formatted_title_id()
    try:
        expected_title_id = format_title_id(parse_title_id(expected_title_id))
    except (TitleIdError, TypeError, ValueError) as exc:
        return fail(["invalid expected title id %r: %s" % (expected_title_id, exc)])

    keyset = KeysetRef()
    keyset_arg = getattr(args, "keyset", None)
    if keyset_arg:
        keyset_text = str(keyset_arg).strip()
        if keyset_text.lower() == "synthetic":
            keyset = KeysetRef(synthetic=True)
        else:
            keyset_path = _cli_path(keyset_text)
            if keyset_path is None or not keyset_path.is_file():
                return fail(["keyset file not found: %s" % keyset_text])
            try:
                keyset_size = keyset_path.stat().st_size
                if keyset_size <= 0:
                    return fail(["keyset file is empty: %s" % keyset_path])
                keyset = KeysetRef(path=keyset_path, size=keyset_size,
                                   sha256=sha256_file(keyset_path))
            except OSError as exc:
                return fail(["cannot read keyset %s: %s" % (keyset_path, exc)])

    work_dir = _cli_path(getattr(args, "work_dir", None))
    temp_dir: Optional[Path] = None
    if work_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="galnx-nsp-verify-"))
        work_dir = temp_dir
    try:
        verify = verify_nsp(
            nsp_path, nstool_path, keyset=keyset,
            expected_title_id=expected_title_id, work_dir=work_dir,
            timeout_s=float(getattr(args, "step_timeout", 300.0)))
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)

    checks: List[Check] = list(verify.checks)
    provenance_path = _cli_path(getattr(args, "provenance", None))
    provenance_checks: List[Check] = []
    if provenance_path is not None:
        provenance_checks = _check_provenance(
            provenance_path, nsp=nsp_path, expected_title_id=expected_title_id, keyset=keyset)
        checks.extend(provenance_checks)
    ok = not has_failures(checks)

    payload = {
        "tool": "package nsp",
        "mode": "verify",
        "manifest": manifest_text,
        "nsp": nsp_text,
        "expected_title_id": expected_title_id,
        "nstool": {"path": _path_text(nstool_path), "source": nstool_source},
        "keyset": keyset.to_dict(),
        "work_dir": _path_text(work_dir),
        "provenance": None if provenance_path is None else {
            "path": _path_text(provenance_path),
            "checks": checks_to_dict(provenance_checks),
        },
        "verify": verify.to_dict(),
        "checks": checks_to_dict(checks),
        "ok": ok,
        "errors": [],
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("verifying NSP: %s" % nsp_text)
        print("  expected title id: %s" % expected_title_id)
        print("  nstool: %s (%s)" % (_path_text(nstool_path), nstool_source))
        if keyset.synthetic:
            print("  keyset: synthetic (structure-only; NCA-level checks are limited)")
        elif keyset.path is not None:
            print("  keyset: %s (%d bytes, sha256 %s)" % (
                _path_text(keyset.path), keyset.size, keyset.sha256))
        else:
            print("  keyset: none (keyed checks skipped; signature FAIL is only a warning)")
        if verify.artifact:
            print("  artifact: %s (%s, sha256 %s)" % (
                verify.artifact.get("path"),
                _format_bytes(int(verify.artifact.get("size") or 0)),
                verify.artifact.get("sha256")))
        if provenance_path is not None:
            print("  provenance: %s" % provenance_path)
        _render_checks(checks)
    return 0 if ok else 1


__all__ = [
    "BuildResult",
    "BuildStep",
    "FAT32_MAX_FILE_BYTES",
    "KeysetRef",
    "NspBuildPlan",
    "NspToolchain",
    "PROVENANCE_SCHEMA_VERSION",
    "RomfsInventory",
    "StepResult",
    "TITLE_ID_PLACEHOLDER",
    "VerifyResult",
    "build_nsp",
    "cmd_nsp",
    "cmd_nsp_verify",
    "digest_romfs",
    "inventory_romfs",
    "plan_nsp_build",
    "register",
    "sha256_file",
    "verify_nsp",
    "write_provenance",
]
