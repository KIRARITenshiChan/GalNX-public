"""NSP/NRO 打包契约检查（GalNX M3-c）。

只读检查，不写文件、不调用 hacBrewPack、不需要 prod.keys：

1. check_dir(root, package_type) 检查一个已准备好的打包输入目录，例如
   M3-a 实测的 work/real-build1/：
     exefs/main            84060 B，magic NSO0
     exefs/main.npdm       972 B，magic META
     control/control.nacp  16384 B（0x4000）
     control/icon_AmericanEnglish.dat  6285 B JPEG 256x256
     romfs/hello.txt
2. parse_nstool_output(text) 容错解析 nstool 文本输出。nstool v1.9.2 没有
   JSON 输出选项，M3-a 实测字段：
     [PartitionFs] Type: PFS0 / FileNum: 3
     [NCA Header] Content Type: Program|Control|Meta, ProgID: 0x..., Size: 0x...
   没有 title.keys 时 nstool 只打印 PFS0 头（3 行），解析器必须容错。
3. check_nstool(parsed, expected_title_id=...) 检查 3 个 NCA 的
   Program/Control/Meta 类型与 ProgID 一致性。

Check.status 取值 ok|warn|fail|skip，与 CLI 的 ICONS 一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .metadata import (
    NACP_ICON_SIZE,
    NACP_TITLE_NAME_MAX,
    PackageType,
    bmp_dimensions,
    image_dimensions,
    is_jpeg,
    jpeg_dimensions,
    parse_version_code,
)
from .titleid import TitleIdError, format_title_id, parse_title_id

NSO_MAGIC = b"NSO0"
NRO_MAGIC = b"NRO0"
NPDM_MAGIC = b"META"
NACP_SIZE = 0x4000
NPDM_MIN_SIZE = 0x80

NSP_CONTENT_TYPES = ("Program", "Control", "Meta")

CHECK_STATUSES = ("ok", "warn", "fail", "skip")


@dataclass(frozen=True)
class Check:
    id: str
    name: str
    status: str = "ok"
    detail: str = ""
    hint: str = ""

    def __post_init__(self) -> None:
        if self.status not in CHECK_STATUSES:
            raise ValueError("check status must be one of %s, got %r" % (CHECK_STATUSES, self.status))

    @property
    def is_fail(self) -> bool:
        return self.status == "fail"

    @property
    def is_error(self) -> bool:
        return self.status == "fail"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "hint": self.hint,
        }

    def to_json(self) -> dict:
        return self.to_dict()


def _check(check_id: str, name: str, status: str, detail: str = "", hint: str = "") -> Check:
    return Check(id=check_id, name=name, status=status, detail=detail, hint=hint)


def checks_to_dict(checks: Iterable[Check]) -> List[dict]:
    return [check.to_dict() for check in checks]


def has_failures(checks: Iterable[Check]) -> bool:
    return any(check.is_fail for check in checks)


def _read_head(path: Path, size: int = 16) -> bytes:
    with path.open("rb") as handle:
        return handle.read(size)


def _iter_control_candidates(control: Path) -> List[Path]:
    if not control.is_dir():
        return []
    candidates = []
    for child in sorted(control.iterdir()):
        if not child.is_file():
            continue
        name = child.name.lower()
        if name.startswith("icon"):
            candidates.append(child)
    return candidates


def check_dir(
    root: Union[str, Path],
    package_type: Union[PackageType, str] = PackageType.SELF_CONTAINED_NSP,
    expected_title_id: Optional[str] = None,
) -> List[Check]:
    """检查一个打包输入目录是否符合 NSP/NRO 契约。返回 Check 列表。"""
    if isinstance(package_type, str):
        try:
            package_type = PackageType(package_type)
        except ValueError:
            return [_check("contract.type", "package type", "fail",
                           "unknown package type: %r" % (package_type,))]
    base = Path(root)
    checks: List[Check] = []
    if not base.is_dir():
        return [_check("contract.dir", "package directory", "fail", "directory not found: %s" % base)]

    exefs = base / "exefs"
    main = exefs / "main"
    npdm = exefs / "main.npdm"
    control = base / "control"
    nacp = control / "control.nacp"
    romfs = base / "romfs"

    # --- exefs/main ---
    if not main.is_file():
        checks.append(_check("contract.exefs.main", "exefs/main", "fail",
                             "missing %s" % main, "build the NSO and stage it as exefs/main"))
    else:
        head = _read_head(main)
        magic = head[:4]
        size = main.stat().st_size
        if magic == NSO_MAGIC:
            checks.append(_check("contract.exefs.main", "exefs/main", "ok",
                                 "NSO0 executable, %d bytes" % size))
        elif magic == NRO_MAGIC:
            checks.append(_check("contract.exefs.main", "exefs/main", "warn",
                                 "NRO0 in ExeFS; an NSP app expects an NSO (convert with elf2nso / nro2nso)",
                                 "replace exefs/main with the NSO build artifact"))
        else:
            checks.append(_check("contract.exefs.main", "exefs/main", "fail",
                                 "unknown magic %r (expected NSO0)" % magic))

    # --- exefs/main.npdm ---
    if not npdm.is_file():
        checks.append(_check("contract.exefs.npdm", "exefs/main.npdm", "fail",
                             "missing %s" % npdm, "generate the NPDM for the application"))
    else:
        head = _read_head(npdm)
        size = npdm.stat().st_size
        if head[:4] != NPDM_MAGIC:
            checks.append(_check("contract.exefs.npdm", "exefs/main.npdm", "fail",
                                 "unknown magic %r (expected META)" % head[:4]))
        elif size < NPDM_MIN_SIZE:
            checks.append(_check("contract.exefs.npdm", "exefs/main.npdm", "fail",
                                 "NPDM is too small: %d bytes (expected >= %d)" % (size, NPDM_MIN_SIZE)))
        else:
            checks.append(_check("contract.exefs.npdm", "exefs/main.npdm", "ok",
                                 "META NPDM, %d bytes" % size))

    # --- control/control.nacp ---
    if not nacp.is_file():
        checks.append(_check("contract.control.nacp", "control/control.nacp", "fail",
                             "missing %s" % nacp, "generate the NACP (nacptool) and stage it"))
    else:
        size = nacp.stat().st_size
        if size == NACP_SIZE:
            checks.append(_check("contract.control.nacp", "control/control.nacp", "ok",
                                 "NACP is %d bytes (0x4000)" % size))
        else:
            checks.append(_check("contract.control.nacp", "control/control.nacp", "fail",
                                 "NACP is %d bytes, expected %d (0x4000)" % (size, NACP_SIZE)))
        try:
            data = nacp.read_bytes()
            name = data[:NACP_TITLE_NAME_MAX].split(b"\x00", 1)[0]
            if name:
                try:
                    checks.append(_check("contract.control.nacp.title", "NACP title name", "ok",
                                         "title name: %s" % name.decode("utf-8", "replace")))
                except Exception:
                    pass
            else:
                checks.append(_check("contract.control.nacp.title", "NACP title name", "warn",
                                     "NACP title name is empty"))
        except OSError as exc:
            checks.append(_check("contract.control.nacp.title", "NACP title name", "warn",
                                 "cannot read NACP: %s" % exc))

    # --- control/icon* ---
    icons = _iter_control_candidates(control)
    if not icons:
        checks.append(_check("contract.control.icon", "control icon", "fail",
                             "no control/icon* file found (NSP needs a 256x256 JPEG icon)"))
    else:
        icon = icons[0]
        try:
            data = icon.read_bytes()
        except OSError as exc:
            checks.append(_check("contract.control.icon", "control icon", "fail",
                                 "cannot read %s: %s" % (icon, exc)))
            data = b""
        if data:
            jpeg = jpeg_dimensions(data)
            if jpeg is not None:
                if jpeg == (NACP_ICON_SIZE, NACP_ICON_SIZE):
                    checks.append(_check("contract.control.icon", "control icon", "ok",
                                         "%s: JPEG %dx%d, %d bytes" % (icon.name, jpeg[0], jpeg[1], len(data))))
                else:
                    checks.append(_check("contract.control.icon", "control icon", "fail",
                                         "%s: JPEG is %dx%d, expected %dx%d" % (
                                             icon.name, jpeg[0], jpeg[1], NACP_ICON_SIZE, NACP_ICON_SIZE)))
            else:
                bmp = bmp_dimensions(data)
                if bmp is None:
                    checks.append(_check("contract.control.icon", "control icon", "fail",
                                         "%s is neither JPEG nor BMP" % icon.name))
                elif bmp != (NACP_ICON_SIZE, NACP_ICON_SIZE):
                    checks.append(_check("contract.control.icon", "control icon", "fail",
                                         "%s: BMP is %dx%d, expected %dx%d" % (
                                             icon.name, bmp[0], bmp[1], NACP_ICON_SIZE, NACP_ICON_SIZE)))
                else:
                    checks.append(_check("contract.control.icon", "control icon", "warn",
                                         "%s: BMP %dx%d accepted, but NACP expects JPEG" % (
                                             icon.name, bmp[0], bmp[1])))

    # --- romfs ---
    if package_type == PackageType.SELF_CONTAINED_NSP:
        if not romfs.is_dir():
            checks.append(_check("contract.romfs", "romfs", "fail",
                                 "missing romfs directory %s" % romfs,
                                 "self-contained NSP requires the game assets in romfs/"))
        else:
            count = 0
            total = 0
            for child in romfs.rglob("*"):
                if child.is_file():
                    count += 1
                    try:
                        total += child.stat().st_size
                    except OSError:
                        pass
            if count == 0:
                checks.append(_check("contract.romfs", "romfs", "warn",
                                     "romfs directory is empty: %s" % romfs))
            else:
                checks.append(_check("contract.romfs", "romfs", "ok",
                                     "%d files, %d bytes" % (count, total)))
    else:
        checks.append(_check("contract.romfs", "romfs", "skip",
                             "package type %s does not embed romfs" % package_type.value))

    # --- 可选 npdm.json（hacBrewPack 输入） ---
    npdm_json = base / "npdm.json"
    if npdm_json.is_file():
        checks.extend(_check_npdm_json(npdm_json, expected_title_id))
    return checks


def _check_npdm_json(path: Path, expected_title_id: Optional[str]) -> List[Check]:
    import json

    checks: List[Check] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [_check("contract.npdm_json", "npdm.json", "warn", "cannot parse %s: %s" % (path, exc))]
    if not isinstance(data, Mapping):
        return [_check("contract.npdm_json", "npdm.json", "warn", "npdm.json is not an object")]
    name = data.get("name")
    if name == "Application":
        checks.append(_check("contract.npdm_json.name", "npdm.json name", "ok", "name: Application"))
    else:
        checks.append(_check("contract.npdm_json.name", "npdm.json name", "warn",
                             "npdm.json name is %r, expected Application" % (name,)))
    title_id = data.get("title_id")
    if isinstance(title_id, str) and title_id:
        try:
            normalized = format_title_id(title_id)
        except TitleIdError as exc:
            checks.append(_check("contract.npdm_json.title_id", "npdm.json title_id", "fail", str(exc)))
        else:
            if expected_title_id:
                try:
                    expected = format_title_id(expected_title_id)
                except TitleIdError:
                    expected = str(expected_title_id)
                if expected.upper() != normalized:
                    checks.append(_check("contract.npdm_json.title_id", "npdm.json title_id", "fail",
                                         "title_id %s does not match expected %s" % (normalized, expected)))
                else:
                    checks.append(_check("contract.npdm_json.title_id", "npdm.json title_id", "ok",
                                         "title_id: %s" % normalized))
            else:
                checks.append(_check("contract.npdm_json.title_id", "npdm.json title_id", "ok",
                                     "title_id: %s" % normalized))
    return checks


# ---------------------------------------------------------------------------
# nstool 文本解析
# ---------------------------------------------------------------------------

def parse_nstool_output(text: str) -> dict:
    """把 nstool 的文本输出解析为 {"partition": {...}, "ncas": [...], "sections": [...]}。

    容错：没有 title.keys 时输出只有 PFS0 头，仍能解析出 partition；
    Program/Control/Meta NCA 头需要逐个 NCA 单独跑 nstool（M3-a 做法）。
    """
    partition: Dict[str, str] = {}
    ncas: List[Dict[str, str]] = []
    sections: List[Tuple[str, Dict[str, str]]] = []
    current: Optional[Dict[str, str]] = None
    if not isinstance(text, str):
        raise TypeError("nstool output must be text")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if name == "PartitionFs":
                current = {}
                partition = current
            elif name == "NCA Header":
                current = {}
                ncas.append(current)
            else:
                current = {}
            sections.append((name, current))
            continue
        if current is not None and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key:
                current[key] = value
    return {"partition": partition, "ncas": ncas, "sections": sections}


def _parse_int(value: Optional[str]) -> Optional[int]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.lower().startswith("0x"):
            return int(text[2:], 16)
        return int(text, 10)
    except ValueError:
        return None


def _parse_prog_id(value: Optional[str]) -> Optional[int]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        if text.lower().startswith("0x"):
            return int(text[2:], 16)
        return int(text, 16)
    except ValueError:
        return None


def check_nstool(
    parsed: Mapping,
    expected_title_id: Optional[Union[str, int]] = None,
) -> List[Check]:
    """检查 nstool 解析结果中的 NSP 结构（PFS0 + Program/Control/Meta）。"""
    checks: List[Check] = []
    if not isinstance(parsed, Mapping):
        return [_check("nstool.parse", "nstool output", "fail", "parsed nstool output must be a mapping")]

    partition = parsed.get("partition") or {}
    ncas = list(parsed.get("ncas") or [])

    if not partition:
        checks.append(_check("nstool.partition", "PFS0 partition", "fail",
                             "no [PartitionFs] section: nstool output may need prod.keys",
                             "run nstool -y -k <prod.keys> on the NSP"))
    else:
        pfs0_type = partition.get("Type", "")
        if pfs0_type.upper() == "PFS0":
            checks.append(_check("nstool.partition.type", "PFS0 type", "ok", "Type: PFS0"))
        else:
            checks.append(_check("nstool.partition.type", "PFS0 type", "fail",
                                 "expected Type: PFS0, got %r" % (pfs0_type,)))
        file_num = _parse_int(partition.get("FileNum"))
        if file_num == 3:
            checks.append(_check("nstool.partition.files", "PFS0 files", "ok", "FileNum: 3"))
        elif file_num is None:
            checks.append(_check("nstool.partition.files", "PFS0 files", "warn",
                                 "FileNum not reported in nstool output"))
        else:
            checks.append(_check("nstool.partition.files", "PFS0 files", "fail",
                                 "FileNum is %d, expected 3 (Program/Control/Meta NCA)" % file_num))

    if not ncas:
        checks.append(_check("nstool.ncas", "NCA headers", "warn",
                             "no [NCA Header] sections parsed",
                             "run nstool on each .nca inside the NSP"))
        return checks

    content_types: List[str] = []
    prog_ids: List[int] = []
    for index, nca in enumerate(ncas):
        content_type = nca.get("Content Type", "")
        if content_type:
            content_types.append(content_type)
        prog_id = _parse_prog_id(nca.get("ProgID") or nca.get("ProgramId") or nca.get("Program ID"))
        if prog_id is not None:
            prog_ids.append(prog_id)
        label = content_type or ("NCA #%d" % index)
        checks.append(_check("nstool.nca.%d" % index, "NCA %d" % index, "ok",
                             "%s, ProgID %s, Size %s" % (
                                 label,
                                 nca.get("ProgID", "?"),
                                 nca.get("Size", "?"))))

    for wanted in NSP_CONTENT_TYPES:
        if wanted in content_types:
            checks.append(_check("nstool.nca.type.%s" % wanted.lower(), "NCA type %s" % wanted, "ok",
                                 "%s NCA present" % wanted))
        else:
            checks.append(_check("nstool.nca.type.%s" % wanted.lower(), "NCA type %s" % wanted, "fail",
                                 "missing %s NCA (found: %s)" % (wanted, ", ".join(content_types) or "none")))

    if len(prog_ids) >= 2:
        if len(set(prog_ids)) == 1:
            checks.append(_check("nstool.progid.consistent", "NCA ProgID consistency", "ok",
                                 "all %d NCAs share ProgID 0x%016X" % (len(prog_ids), prog_ids[0])))
        else:
            checks.append(_check("nstool.progid.consistent", "NCA ProgID consistency", "fail",
                                 "NCA ProgIDs differ: %s" % ", ".join("0x%016X" % item for item in prog_ids)))

    if expected_title_id is not None:
        try:
            normalized_expected = parse_title_id(expected_title_id)
        except TitleIdError as exc:
            checks.append(_check("nstool.progid.expected", "expected ProgID", "warn", str(exc)))
            return checks
        if prog_ids and all(item == normalized_expected for item in prog_ids):
            checks.append(_check("nstool.progid.expected", "expected ProgID", "ok",
                                 "ProgID matches 0x%016X" % normalized_expected))
        elif prog_ids:
            checks.append(_check("nstool.progid.expected", "expected ProgID", "fail",
                                 "ProgID 0x%016X does not match expected 0x%016X" % (prog_ids[0], normalized_expected)))
        else:
            checks.append(_check("nstool.progid.expected", "expected ProgID", "warn",
                                 "nstool output does not include ProgID"))
    return checks


def load_nstool_file(path: Union[str, Path]) -> dict:
    target = Path(path)
    text = target.read_text(encoding="utf-8", errors="replace")
    return parse_nstool_output(text)
