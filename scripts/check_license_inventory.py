#!/usr/bin/env python3
"""校验 GalNX 第三方组件清单（SBOM）。

用法：
    python scripts/check_license_inventory.py
    python scripts/check_license_inventory.py --json
    python scripts/check_license_inventory.py --inventory <path> --root <repo-root>

退出码：0 = 通过；1 = 有错误（或文件无法读取/解析）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML 是项目依赖
    print("error: 需要 PyYAML（pip install pyyaml）", file=sys.stderr)
    raise SystemExit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]

LICENSE_FAMILIES = {"permissive", "weak-copyleft", "copyleft", "custom", "public-domain", "unknown"}
LINK_MODES = {"static", "dynamic", "none", "na"}
DISTRIBUTION_CLASSES = {"runtime-linked", "runtime-bundled", "build-only", "development-only"}
EVIDENCE_TYPES = {"repo", "local", "url"}
COPYLEFT_FAMILIES = {"copyleft", "weak-copyleft", "custom", "unknown"}

REQUIRED_COMPONENT_FIELDS = (
    "id", "name", "upstream", "version_or_commit", "license_family",
    "link_mode", "included_in_nsp", "distribution_class",
    "patches", "obligations", "evidence", "notes",
)

HOME_MARKERS = ("c:\\users", "/home/", "/users/", "%userprofile%", "$home", "~/")
ABS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/)")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _err(errors: list[str], where: str, message: str) -> None:
    errors.append(f"{where}: {message}")


def _is_abs(s: str) -> bool:
    return bool(ABS_PATH_RE.match(s))


def _has_home_path(s: str) -> bool:
    low = s.lower()
    return any(m in low for m in HOME_MARKERS)


def _check_repo_path(errors: list[str], where: str, rel: str, root: Path) -> None:
    if not isinstance(rel, str) or not rel.strip():
        _err(errors, where, "路径必须是非空字符串")
        return
    if _is_abs(rel) or "\\" in rel:
        _err(errors, where, f"必须是仓库相对 POSIX 路径，不能用绝对路径或反斜杠：{rel!r}")
        return
    if ".." in Path(rel).parts:
        _err(errors, where, f"不允许 '..' 路径穿越：{rel!r}")
        return
    if _has_home_path(rel):
        _err(errors, where, f"不允许个人用户目录路径：{rel!r}")
        return
    if not (root / rel).is_file():
        _err(errors, where, f"文件不存在：{rel}")


def _scan_home_markers(errors: list[str], where: str, value) -> None:
    """递归检查字符串是否含个人用户目录路径。"""
    if isinstance(value, str):
        if _has_home_path(value):
            _err(errors, where, f"含个人用户目录路径（禁止入库）：{value[:80]!r}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _scan_home_markers(errors, f"{where}[{i}]", item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _scan_home_markers(errors, f"{where}.{key}", item)


def _validate_evidence(errors: list[str], where: str, evidence, root: Path) -> None:
    if not isinstance(evidence, list) or not evidence:
        _err(errors, where, "必须是非空列表")
        return
    for i, item in enumerate(evidence):
        item_where = f"{where}[{i}]"
        if not isinstance(item, dict):
            _err(errors, item_where, "必须是 {type, ...} 对象")
            continue
        kind = item.get("type")
        if kind not in EVIDENCE_TYPES:
            _err(errors, item_where + ".type", f"必须是 {sorted(EVIDENCE_TYPES)} 之一，实际 {kind!r}")
            continue
        if kind == "repo":
            _check_repo_path(errors, item_where + ".path", item.get("path", ""), root)
        elif kind == "local":
            ref = item.get("ref", "")
            if not isinstance(ref, str) or not ref.strip():
                _err(errors, item_where + ".ref", "本机证据 ref 不能为空")
            elif _has_home_path(ref):
                _err(errors, item_where + ".ref", f"不允许个人用户目录路径：{ref[:80]!r}")
        else:
            url = item.get("url", "")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                _err(errors, item_where + ".url", "url 证据必须是 http(s) URL")


def _validate_artifacts(errors: list[str], scope: dict, root: Path) -> tuple[set[str], dict[str, dict]]:
    ids: set[str] = set()
    by_id: dict[str, dict] = {}
    artifacts = scope.get("artifacts", [])
    if not isinstance(artifacts, list):
        _err(errors, "scope.artifacts", "必须是列表")
        return ids, by_id
    for i, art in enumerate(artifacts):
        where = f"scope.artifacts[{i}]"
        if not isinstance(art, dict):
            _err(errors, where, "必须是对象")
            continue
        art_id = art.get("id")
        if not isinstance(art_id, str) or not art_id.strip():
            _err(errors, where + ".id", "必须是非空字符串")
            continue
        if art_id in ids:
            _err(errors, where + ".id", f"重复的 artifact id：{art_id}")
            continue
        ids.add(art_id)
        by_id[art_id] = art
        desc = art.get("description")
        if not isinstance(desc, str) or not desc.strip():
            _err(errors, where + ".description", "必须是非空字符串")
        sha = art.get("sha256")
        if sha is not None and not (isinstance(sha, str) and SHA256_RE.match(sha)):
            _err(errors, where + ".sha256", "必须是 64 位小写 hex")
        size = art.get("size_bytes")
        if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size <= 0):
            _err(errors, where + ".size_bytes", "必须是正整数（字节）")
        if "distributed" in art and not isinstance(art["distributed"], bool):
            _err(errors, where + ".distributed", "必须是布尔值")
        if "path" in art and not isinstance(art["path"], str):
            _err(errors, where + ".path", "必须是字符串")
        ev = art.get("evidence")
        if ev is not None:
            if not isinstance(ev, list):
                _err(errors, where + ".evidence", "必须是列表")
            else:
                for j, item in enumerate(ev):
                    if not isinstance(item, dict) or "path" not in item:
                        _err(errors, f"{where}.evidence[{j}]", "必须是 {path, note} 对象")
                        continue
                    _check_repo_path(errors, f"{where}.evidence[{j}].path", item["path"], root)
    return ids, by_id


def _validate_component(errors: list[str], warnings: list[str], where: str, comp, artifact_ids: set[str], root: Path) -> None:
    if not isinstance(comp, dict):
        _err(errors, where, "必须是对象")
        return

    for field in REQUIRED_COMPONENT_FIELDS:
        if field not in comp:
            _err(errors, where + "." + field, "缺少必填字段")

    comp_id = comp.get("id")
    if isinstance(comp_id, str):
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", comp_id):
            _err(errors, where + ".id", f"id 只能是小写字母/数字/连字符：{comp_id!r}")
    else:
        _err(errors, where + ".id", "必须是非空字符串")

    for field in ("name", "upstream", "version_or_commit"):
        value = comp.get(field)
        if not isinstance(value, str) or not value.strip():
            _err(errors, where + "." + field, "必须是非空字符串")

    notes = comp.get("notes")
    if not isinstance(notes, str) or not notes.strip():
        _err(errors, where + ".notes", "必须是非空字符串")

    # 许可证三元组：SPDX 或 (name + url)。NOASSERTION 必须同时给 name/url。
    spdx = comp.get("license_spdx", "")
    name = comp.get("license_name", "")
    url = comp.get("license_url", "")
    if spdx == "NOASSERTION":
        if not isinstance(name, str) or not name.strip():
            _err(errors, where + ".license_name", "NOASSERTION 时必须给出 license_name")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            _err(errors, where + ".license_url", "NOASSERTION 时必须给出 http(s) license_url")
    elif isinstance(spdx, str) and spdx.strip():
        pass
    else:
        if not isinstance(name, str) or not name.strip():
            _err(errors, where + ".license_name", "缺少 license_spdx 时必须给出 license_name")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            _err(errors, where + ".license_url", "缺少 license_spdx 时必须给出 http(s) license_url")

    license_file = comp.get("license_file")
    if license_file not in (None, ""):
        _check_repo_path(errors, where + ".license_file", license_file, root)

    family = comp.get("license_family")
    if family not in LICENSE_FAMILIES:
        _err(errors, where + ".license_family", f"必须是 {sorted(LICENSE_FAMILIES)} 之一")
    if comp.get("link_mode") not in LINK_MODES:
        _err(errors, where + ".link_mode", f"必须是 {sorted(LINK_MODES)} 之一")
    if comp.get("distribution_class") not in DISTRIBUTION_CLASSES:
        _err(errors, where + ".distribution_class", f"必须是 {sorted(DISTRIBUTION_CLASSES)} 之一")

    included = comp.get("included_in_nsp")
    if not isinstance(included, bool):
        _err(errors, where + ".included_in_nsp", "必须是布尔值")

    patches = comp.get("patches")
    if not isinstance(patches, list):
        _err(errors, where + ".patches", "必须是列表")
    else:
        for i, patch in enumerate(patches):
            _check_repo_path(errors, f"{where}.patches[{i}]", patch, root)

    obligations = comp.get("obligations")
    if not isinstance(obligations, list) or not all(isinstance(o, str) and o.strip() for o in obligations):
        _err(errors, where + ".obligations", "必须是非空字符串列表")
        obligations = []
    if included is True and family in COPYLEFT_FAMILIES and not obligations:
        _err(errors, where + ".obligations", f"included_in_nsp=true 且许可证族为 {family} 时必须列出义务")

    artifacts = comp.get("artifacts", [])
    if not isinstance(artifacts, list) or not all(isinstance(a, str) for a in artifacts):
        _err(errors, where + ".artifacts", "必须是字符串列表")
        artifacts = []
    else:
        for art in artifacts:
            if art not in artifact_ids:
                _err(errors, where + ".artifacts", f"未知 artifact id：{art}")
        if included is True and not artifacts:
            _err(errors, where + ".artifacts", "included_in_nsp=true 时必须列出所属 artifacts")

    _validate_evidence(errors, where + ".evidence", comp.get("evidence"), root)

    # 版本未锁定的提醒（不阻断）
    version = str(comp.get("version_or_commit", ""))
    if any(marker in version for marker in ("未锁定", "unpinned", "master 分支")):
        warnings.append(f"{where}: 版本未锁定（{version[:60]}），影响可复现性")


def validate_inventory(data, root: Path, inventory_path: Path) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict = {"components": 0, "artifacts": 0}

    if not isinstance(data, dict):
        return ["inventory: 顶层必须是对象（mapping）"], warnings, stats

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version < 1:
        _err(errors, "schema_version", "必须是 >= 1 的整数")

    generated_at = data.get("generated_at")
    if isinstance(generated_at, (datetime, date)):
        generated_at = generated_at.isoformat()
    if not isinstance(generated_at, str) or not DATE_RE.match(generated_at):
        _err(errors, "generated_at", "必须是 YYYY-MM-DD 字符串")
    else:
        try:
            datetime.strptime(generated_at, "%Y-%m-%d")
        except ValueError:
            _err(errors, "generated_at", f"不是合法日期：{generated_at}")

    scope = data.get("scope")
    if not isinstance(scope, dict):
        _err(errors, "scope", "必须是对象")
        scope = {}
    baseline = scope.get("baseline_commit")
    if not isinstance(baseline, str) or not COMMIT_RE.match(baseline or ""):
        _err(errors, "scope.baseline_commit", "必须是 7-40 位小写 hex commit")

    artifact_ids, _ = _validate_artifacts(errors, scope, root)
    stats["artifacts"] = len(artifact_ids)

    components = data.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components: 必须是非空列表")
        components = []
    stats["components"] = len(components)

    seen_ids: set[str] = set()
    for i, comp in enumerate(components):
        where = f"components[{i}]"
        if isinstance(comp, dict):
            cid = comp.get("id")
            if isinstance(cid, str):
                if cid in seen_ids:
                    _err(errors, where + ".id", f"重复的组件 id：{cid}")
                seen_ids.add(cid)
                where = f"components[{i}]（{cid}）"
        _validate_component(errors, warnings, where, comp, artifact_ids, root)

    # 全量扫描字符串中的个人目录路径（补丁/证据字段之外的 notes 等也要查）
    _scan_home_markers(errors, "inventory", data)

    return errors, warnings, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 GalNX 第三方组件清单（SBOM）")
    parser.add_argument("--inventory", type=Path, default=REPO_ROOT / "docs" / "third_party" / "inventory.yaml",
                        help="inventory YAML 路径（默认 docs/third_party/inventory.yaml）")
    parser.add_argument("--root", type=Path, default=REPO_ROOT,
                        help="仓库根目录，用于解析仓库相对路径（默认仓库根）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    inventory: Path = args.inventory
    root: Path = args.root

    errors: list[str] = []
    warnings: list[str] = []
    stats: dict = {"components": 0, "artifacts": 0}
    data = None

    if not inventory.is_file():
        errors.append(f"inventory: 文件不存在：{inventory}")
    else:
        try:
            with inventory.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            errors.append(f"inventory: YAML 解析失败：{exc}")
            data = None
        if data is not None or not errors:
            errors, warnings, stats = validate_inventory(data, root, inventory)

    ok = not errors
    generated_at_value = data.get("generated_at") if isinstance(data, dict) else None
    if isinstance(generated_at_value, (datetime, date)):
        generated_at_value = generated_at_value.isoformat()
    payload = {
        "ok": ok,
        "inventory": str(inventory),
        "root": str(root),
        "generated_at": generated_at_value,
        "components": stats["components"],
        "artifacts": stats["artifacts"],
        "errors": errors,
        "warnings": warnings,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"inventory: {inventory}")
        print(f"components: {stats['components']}  artifacts: {stats['artifacts']}")
        for warning in warnings:
            print(f"WARN  {warning}")
        for error in errors:
            print(f"ERROR {error}")
        print("OK" if ok else f"FAILED（{len(errors)} 个错误）")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
