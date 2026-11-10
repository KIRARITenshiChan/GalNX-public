"""Nintendo Switch Title ID 数据模型（GalNX M3-c）。

只读事实来源（2026-10-30 整理，详见 docs/packaging/README.md）：
1. gbatemp wiki "List of Switch homebrew titleID"（社区文档，非任天堂官方）：
   - 合法区间 0x0100000000000000 - 0x01FFFFFFFFFFFFFF；
   - 所有 title 以 0100 开头；System Title 都在 010000000000XXXX；
   - 游戏 base ID 以 Y000 结尾（Y 为偶数，即 base 为 0x2000 的倍数）；
   - 更新（patch）以 0800 结尾，即 base | 0x800；
   - DLC 以 YXXX 结尾（Y 为奇数），DLC = base | 1XXX，XXX 为 0x000-0xFFF。
2. switchbrew wiki "Title list/Games" 首行注记：
   "Game updates have the same ProgramId as the main application, except with
   bitmask 0x800 set."
3. switchbrew wiki "Title list"（system modules / system data / system applets /
   development system applets 的实际 ProgramId 区间）。
4. hacBrewPack 745b16ec 源码（M3-a 实际使用的打包器）：
   - cnmt.c:22  cnmt_ext_header.patch_title_id = cnmt_ctx->cnmt_header.title_id + 0x800;
   - nacp.c:96  nacp.AddOnContentBaseId = settings->title_id + 0x1000;
   - nacp.c:94-95 PresenceGroupId = SaveDataOwnerId = title_id.
5. M3-a 实测 npdm.json（work/m0/npdm.json）：
   title_id_range_min = 0x0100000000000000，title_id_range_max = 0x01ffffffffffffff。

注意：以上不是任天堂官方 SDK 文档；区间/位规则属于社区与开源工具共识，
GalNX 只把它用于「生成可安装的 homebrew NSP」的冲突检查，不作为系统级保证。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Optional, Sequence, Tuple, Union

TITLE_ID_MIN = 0x0100000000000000
TITLE_ID_MAX = 0x01FFFFFFFFFFFFFF
TITLE_ID_HEX_LEN = 16

APPLICATION_PREFIX = 0x0100
SYSTEM_TITLE_MAX = 0x010000000000FFFF

PATCH_OFFSET = 0x800
DLC_OFFSET = 0x1000
DLC_INDEX_MASK = 0xFFF
BASE_ALIGN = 0x2000
BASE_ALIGN_MASK = BASE_ALIGN - 1

# GalNX 自用分配块（"GALN" = 0x47414C4E），避免和常见 homebrew 生成器撞车。
GALNX_ALLOCATION_START = 0x010047414C4E0000
GALNX_ALLOCATION_BLOCK_MIN = 0x0100474100000000
GALNX_ALLOCATION_BLOCK_MAX = 0x01004741FFFFFFFF

_HEX_DIGITS = set("0123456789abcdefABCDEF")

RESERVED_RANGES: Tuple[Tuple[int, int, str], ...] = (
    (0x0100000000000000, 0x01000000000007FF, "system modules (fs/ldr/ncm/pm/sm/boot/usb/...)"),
    (0x0100000000000800, 0x0100000000000FFF, "system data archives"),
    (0x0100000000001000, 0x0100000000001FFF, "system applets"),
    (0x0100000000002000, 0x0100000000002FFF, "development system applets"),
)


class TitleIdError(ValueError):
    """Title ID 格式/语义错误。"""


class TitleKind(str, Enum):
    BASE = "base"
    PATCH = "patch"
    DLC = "dlc"
    SYSTEM = "system"
    INVALID = "invalid"


def parse_title_id(value: Union[str, int]) -> int:
    """把 '0100XXXXYYYY0000' / 0x0100XXXXYYYY0000 解析为整数。

    只做格式解析（16 位十六进制、64 位无符号）；范围/语义由 classify() 判定。
    """
    if isinstance(value, bool):
        raise TitleIdError("title id must be a string or integer, got bool")
    if isinstance(value, int):
        if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
            raise TitleIdError("title id out of 64-bit range: %d" % value)
        return value
    if not isinstance(value, str):
        raise TitleIdError("title id must be a string or integer, got %s" % type(value).__name__)
    text = value.strip()
    if text.lower().startswith("0x"):
        text = text[2:]
    if len(text) != TITLE_ID_HEX_LEN:
        raise TitleIdError("title id must be 16 hex digits, got %r" % value)
    if any(ch not in _HEX_DIGITS for ch in text):
        raise TitleIdError("title id contains non-hex characters: %r" % value)
    return int(text, 16)


def format_title_id(value: Union[str, int]) -> str:
    """规范化为 16 位大写十六进制字符串（无 0x 前缀）。"""
    return format(parse_title_id(value), "016X")


def is_system_reserved(value: Union[str, int]) -> Optional[str]:
    """若落在系统保留区间，返回区间说明；否则 None。"""
    try:
        title_id = parse_title_id(value)
    except TitleIdError:
        return None
    for start, end, name in RESERVED_RANGES:
        if start <= title_id <= end:
            return name
    return None


def in_valid_range(value: Union[str, int]) -> bool:
    try:
        title_id = parse_title_id(value)
    except TitleIdError:
        return False
    return TITLE_ID_MIN <= title_id <= TITLE_ID_MAX


def classify(value: Union[str, int]) -> TitleKind:
    """判定 base / patch / dlc / system / invalid。

    规则（低 13 位，即 BASE_ALIGN_MASK）：
      - system 区间（<= 0x010000000000FFFF）优先；
      - 低 13 位 == 0x0000 -> base（游戏/应用本体）；
      - 低 13 位 == 0x0800 -> patch（更新，base | 0x800）；
      - 低 13 位 >= 0x1000 -> dlc（base | 0x1000 | index，index 0x000-0xFFF）；
      - 其他（例如低 13 位 0x0001-0x07FF/0x0801-0x0FFF）-> invalid。
    """
    try:
        title_id = parse_title_id(value)
    except TitleIdError:
        return TitleKind.INVALID
    if title_id < TITLE_ID_MIN or title_id > TITLE_ID_MAX:
        return TitleKind.INVALID
    if title_id <= SYSTEM_TITLE_MAX:
        return TitleKind.SYSTEM
    low = title_id & BASE_ALIGN_MASK
    if low == 0:
        return TitleKind.BASE
    if low == PATCH_OFFSET:
        return TitleKind.PATCH
    if low >= DLC_OFFSET:
        return TitleKind.DLC
    return TitleKind.INVALID


def base_of(value: Union[str, int]) -> Optional[int]:
    """由 base/patch/dlc ID 反推 base ID；system/invalid 返回 None。"""
    kind = classify(value)
    title_id = parse_title_id(value)
    if kind == TitleKind.BASE:
        return title_id
    if kind == TitleKind.PATCH:
        return title_id - PATCH_OFFSET
    if kind == TitleKind.DLC:
        return title_id & ~BASE_ALIGN_MASK
    return None


def patch_id_of(base: Union[str, int]) -> int:
    base_id = _require_base(base)
    return base_id + PATCH_OFFSET


def dlc_base_of(base: Union[str, int]) -> int:
    """NACP AddOnContentBaseId = base + 0x1000（hacBrewPack nacp.c:96）。"""
    base_id = _require_base(base)
    return base_id + DLC_OFFSET


def dlc_id_of(base: Union[str, int], index: int) -> int:
    """单个 DLC 的 title id = base | 0x1000 | index（index 0x000-0xFFF）。"""
    base_id = _require_base(base)
    if not isinstance(index, int) or index < 0 or index > DLC_INDEX_MASK:
        raise TitleIdError("dlc index must be 0x000-0xFFF, got %r" % (index,))
    return base_id + DLC_OFFSET + index


def _require_base(value: Union[str, int]) -> int:
    kind = classify(value)
    if kind != TitleKind.BASE:
        raise TitleIdError("expected an application base title id, got %s (%s)" % (
            _safe_text(value), kind.value))
    return parse_title_id(value)


def _safe_text(value: object) -> str:
    try:
        return format_title_id(value)  # type: ignore[arg-type]
    except TitleIdError:
        return repr(value)


def _spans_for(base_id: int) -> Tuple[Tuple[int, int, str], ...]:
    return (
        (base_id, base_id, "application"),
        (base_id + PATCH_OFFSET, base_id + PATCH_OFFSET, "update"),
        (base_id + DLC_OFFSET, base_id + DLC_OFFSET + DLC_INDEX_MASK, "add-on content"),
    )


@dataclass(frozen=True)
class TitleIdIssue:
    severity: str
    code: str
    message: str
    title_id: str = ""

    def __post_init__(self) -> None:
        if self.severity not in ("error", "warning"):
            raise ValueError("severity must be error or warning")

    @property
    def is_error(self) -> bool:
        return self.severity == "error"

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "title_id": self.title_id,
        }


def _issue(severity: str, code: str, message: str, title_id: str = "") -> TitleIdIssue:
    return TitleIdIssue(severity=severity, code=code, message=message, title_id=title_id)


def _parse_existing(existing: Iterable[Union[str, int]]) -> List[int]:
    try:
        return [parse_title_id(value) for value in existing]
    except TitleIdError as exc:
        raise TitleIdError("existing title id list is invalid: %s" % exc) from exc


def validate_base(title_id: Union[str, int]) -> List[TitleIdIssue]:
    """校验某个 ID 能否作为 GalNX 分配的应用 base ID（errors only）。"""
    issues: List[TitleIdIssue] = []
    try:
        value = parse_title_id(title_id)
    except TitleIdError as exc:
        return [_issue("error", "invalid_format", str(exc), _safe_text(title_id))]
    text = format_title_id(value)
    if value < TITLE_ID_MIN or value > TITLE_ID_MAX:
        issues.append(_issue("error", "out_of_range",
                             "title id %s is outside 0x0100000000000000-0x01FFFFFFFFFFFFFF" % text, text))
        return issues
    reserved = is_system_reserved(value)
    if reserved is not None:
        issues.append(_issue("error", "system_reserved",
                             "title id %s is in a system-reserved range: %s" % (text, reserved), text))
        return issues
    kind = classify(value)
    if kind == TitleKind.PATCH:
        issues.append(_issue("error", "not_base",
                             "title id %s is an update (patch) id (base | 0x800); allocate the base id instead" % text, text))
    elif kind == TitleKind.DLC:
        issues.append(_issue("error", "not_base",
                             "title id %s is an add-on content id (base | 0x1000 | index); allocate the base id instead" % text, text))
    elif kind == TitleKind.INVALID:
        issues.append(_issue("error", "not_aligned",
                             "title id %s is not a valid application base id (base ids are multiples of 0x2000)" % text, text))
    elif value & BASE_ALIGN_MASK:
        issues.append(_issue("error", "not_aligned",
                             "application base id %s must be 0x2000-aligned" % text, text))
    if not (GALNX_ALLOCATION_BLOCK_MIN <= value <= GALNX_ALLOCATION_BLOCK_MAX):
        issues.append(_issue("warning", "outside_allocation_block",
                             "title id %s is outside the GalNX allocation block 0x0100474100000000-0x01004741FFFFFFFF" % text, text))
    return issues


def check_conflicts(
    new: Union[str, int, Sequence[Union[str, int]]],
    existing: Iterable[Union[str, int]] = (),
) -> List[TitleIdIssue]:
    """检查一个（或一组）base ID 与 existing 列表的冲突。

    返回 error/warning 列表；空列表 = 无冲突。existing 允许含 base/patch/dlc
    原始 ID（会先反推 base 再比较派生区间）。
    """
    if isinstance(new, (str, int)) and not isinstance(new, bool):
        candidates: List[Union[str, int]] = [new]
    else:
        candidates = list(new)  # type: ignore[arg-type]

    existing_ids = _parse_existing(existing)
    existing_bases: List[Tuple[str, int, Optional[int]]] = []
    for raw in existing_ids:
        existing_bases.append((format_title_id(raw), raw, base_of(raw)))

    issues: List[TitleIdIssue] = []
    seen_bases: List[int] = []
    for candidate in candidates:
        own = validate_base(candidate)
        issues.extend(own)
        if any(issue.is_error for issue in own):
            continue
        value = parse_title_id(candidate)
        text = format_title_id(value)
        if value in seen_bases:
            issues.append(_issue("error", "duplicate",
                                 "title id %s appears more than once in the new list" % text, text))
            continue
        seen_bases.append(value)
        own_spans = _spans_for(value)
        produced = set()
        for other_text, other_id, other_base in existing_bases:
            if other_base == value:
                if "duplicate" not in produced:
                    produced.add("duplicate")
                    issues.append(_issue("error", "duplicate",
                                         "title id %s is already registered (existing entry %s)" % (
                                             text, other_text), text))
                continue
            if other_base is None:
                other_spans = ((other_id, other_id, "non-application title id"),)
            else:
                other_spans = _spans_for(other_base)
            hit = None
            for start, end, label in other_spans:
                for own_start, own_end, own_label in own_spans:
                    if own_start <= end and start <= own_end:
                        hit = (start, end, label, own_start, own_end, own_label)
                        break
                if hit is not None:
                    break
            if hit is not None and other_text not in produced:
                produced.add(other_text)
                start, end, label, own_start, own_end, own_label = hit
                issues.append(_issue("error", "derived_conflict",
                                     "title id %s (%s range 0x%016X-0x%016X) overlaps existing %s (%s range 0x%016X-0x%016X)" % (
                                         text, own_label, own_start, own_end,
                                         other_text, label, start, end), text))
    return issues


def allocate(
    existing: Iterable[Union[str, int]] = (),
    count: int = 1,
    start: Union[str, int] = GALNX_ALLOCATION_START,
) -> List[int]:
    """在 GalNX 分配块内寻找空闲 base ID（0x2000 对齐，跳过系统保留与冲突）。"""
    if not isinstance(count, int) or count < 1:
        raise TitleIdError("count must be a positive integer")
    existing_ids = _parse_existing(existing)
    start_id = parse_title_id(start)
    if start_id & BASE_ALIGN_MASK:
        start_id = (start_id + BASE_ALIGN_MASK) & ~BASE_ALIGN_MASK
    result: List[int] = []
    candidate = start_id
    checked = 0
    while len(result) < count:
        if candidate > TITLE_ID_MAX or checked > 1 << 20:
            raise TitleIdError("no free title id found after scanning from %s" % format_title_id(start_id))
        checked += 1
        issues = check_conflicts(candidate, list(existing_ids) + result)
        if not any(issue.is_error for issue in issues):
            result.append(candidate)
        candidate += BASE_ALIGN
    return result


def conflicts_to_dict(issues: Iterable[TitleIdIssue]) -> List[dict]:
    return [issue.to_dict() for issue in issues]


def errors_of(issues: Iterable[TitleIdIssue]) -> List[TitleIdIssue]:
    return [issue for issue in issues if issue.is_error]


def warnings_of(issues: Iterable[TitleIdIssue]) -> List[TitleIdIssue]:
    return [issue for issue in issues if not issue.is_error]
