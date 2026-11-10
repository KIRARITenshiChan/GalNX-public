"""`galnx doctor`: verify that this machine can build and test Switch NROs.

Every check is read-only. Secrets (prod.keys) are only measured (size/SHA-256)
and their bytes are never printed or persisted.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from . import paths

STATUSES = ("ok", "warn", "fail", "skip")


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    hint: str = ""

    def to_json(self) -> dict[str, str]:
        return asdict(self)


def _run(cmd: list[str], timeout: int = 120, env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except FileNotFoundError:
        return 127, "command not found: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, "timeout after %ss" % timeout
    except OSError as exc:
        return 126, "exec error: %s" % exc


def _msys_env() -> dict[str, str]:
    env = dict(os.environ)
    env["MSYSTEM"] = "MSYS"
    env["CHERE_INVOKING"] = "1"
    return env


def check_python() -> Check:
    ok = sys.version_info >= (3, 11)
    return Check(
        "python",
        "ok" if ok else "fail",
        "%s (%s)" % (sys.version.split()[0], sys.executable),
        "" if ok else "GalNX requires Python 3.11+",
    )


def check_devkitpro(devkitpro: Path) -> list[Check]:
    checks: list[Check] = []
    if not devkitpro.is_dir():
        checks.append(
            Check("devkitpro", "fail", str(devkitpro),
                  "install devkitPro (docs/environment/devkitpro-2026-10-29.md)")
        )
        return checks
    checks.append(Check("devkitpro", "ok", str(devkitpro)))

    gcc = devkitpro / "devkitA64" / "bin" / "aarch64-none-elf-gcc.exe"
    if gcc.is_file():
        rc, out = _run([str(gcc), "--version"], timeout=30)
        first = out.splitlines()[0] if out else ""
        checks.append(Check("devkita64-gcc", "ok" if rc == 0 else "fail", first))
    else:
        checks.append(Check("devkita64-gcc", "fail", str(gcc), "pacman -S switch-dev"))

    tools_bin = devkitpro / "tools" / "bin"
    for tool in ("elf2nro.exe", "nacptool.exe", "nxlink.exe", "build_pfs0.exe"):
        candidate = tools_bin / tool
        if not candidate.is_file():
            candidate = tools_bin / Path(tool).stem
        checks.append(
            Check(tool.rsplit(".", 1)[0], "ok" if candidate.is_file() else "fail",
                  str(candidate) if candidate.is_file() else str(candidate),
                  "" if candidate.is_file() else "pacman -S switch-tools")
        )

    rules = devkitpro / "libnx" / "switch_rules"
    checks.append(
        Check("libnx", "ok" if rules.is_file() else "fail", str(rules),
              "" if rules.is_file() else "pacman -S libnx")
    )

    cmake_dir = devkitpro / "cmake" / "Switch.cmake"
    checks.append(
        Check("switch-cmake", "ok" if cmake_dir.is_file() else "warn", str(cmake_dir),
              "" if cmake_dir.is_file() else "pacman -S switch-cmake (needed for CMake builds)")
    )
    return checks


SWITCH_PACKAGES = (
    "devkitA64", "devkita64-gcc", "devkita64-binutils", "devkita64-newlib",
    "libnx", "switch-tools", "deko3d", "switch-cmake",
    "switch-sdl2", "switch-freetype", "switch-sdl2_ttf", "switch-sdl2_image", "switch-sdl2_mixer",
)


def check_packages(devkitpro: Path) -> Check:
    bash = devkitpro / "msys2" / "usr" / "bin" / "bash.exe"
    if not bash.is_file():
        return Check("switch-packages", "fail", "msys2 bash missing", "re-run the devkitPro installer")
    rc, out = _run([str(bash), "-lc", "pacman -Q " + " ".join(SWITCH_PACKAGES) + " 2>&1"],
                   timeout=180, env=_msys_env())
    installed = []
    missing = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if "was not found" in line or "error:" in line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in SWITCH_PACKAGES:
            installed.append("%s %s" % (parts[0], parts[1]))
    have = {item.split()[0] for item in installed}
    missing = [pkg for pkg in SWITCH_PACKAGES if pkg not in have]
    if missing:
        return Check("switch-packages", "warn",
                     "%d/%d installed; missing: %s" % (len(installed), len(SWITCH_PACKAGES), ", ".join(missing)),
                     "pacman -S --needed switch-dev switch-sdl2 switch-freetype switch-sdl2_ttf")
    return Check("switch-packages", "ok", "; ".join(installed))


def _keys_metadata(blob: bytes) -> tuple[bool, str]:
    has_header = b"header_key" in blob
    has_area = b"key_area_key_application_0" in blob
    return (has_header and has_area), hashlib.sha256(blob).hexdigest()


def check_keys(path: Path) -> Check:
    if not path.is_file():
        return Check("prod.keys", "fail", str(path),
                     "set GALNX_PROD_KEYS to a keyset you legally own (required for NSP packaging only)")
    blob = path.read_bytes()
    complete, digest = _keys_metadata(blob)
    detail = "%s (%d B, sha256 %s...)" % (path, len(blob), digest[:16])
    if not complete:
        return Check("prod.keys", "warn", detail, "keyset is missing header_key/key_area_key_application_*; NSP packaging will fail")
    return Check("prod.keys", "ok", detail)


def check_emulator(name: str, exe: Path) -> Check:
    if exe.is_file():
        return Check(name, "ok", str(exe))
    return Check(name, "warn", str(exe), "install/locate this emulator and set the matching GALNX_* env var")


def check_build_root(build_root: Path) -> Check:
    text = str(build_root)
    if " " in text:
        return Check("build-root", "fail", text,
                     "devkitPro make templates break on paths containing spaces; choose a space-free root")
    if not build_root.exists():
        return Check("build-root", "warn", text, "directory does not exist yet; galnx build will create it")
    try:
        probe = build_root / ".galnx-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable = True
    except OSError as exc:
        return Check("build-root", "fail", text, "not writable: %s" % exc)
    usage = shutil.disk_usage(build_root)
    return Check("build-root", "ok" if writable else "fail",
                 "%s (free %.1f GiB)" % (build_root, usage.free / 2 ** 30))


def check_tools() -> list[Check]:
    checks = []
    for name in ("git", "python", "cmake", "ninja", "7z"):
        found = shutil.which(name)
        checks.append(Check(name, "ok" if found else "warn", found or "not on PATH",
                            "" if found else "install %s" % name))
    return checks


def run_doctor() -> list[Check]:
    checks: list[Check] = [check_python()]
    checks.extend(check_devkitpro(paths.DEVKITPRO))
    checks.append(check_packages(paths.DEVKITPRO))
    checks.extend(check_tools())
    checks.append(check_keys(paths.PROD_KEYS))
    checks.append(check_emulator("citron", paths.CITRON))
    checks.append(check_emulator("ryujinx", paths.RYUJINX))
    checks.append(check_build_root(paths.BUILD_ROOT))
    namespace = paths.repo_root()
    checks.append(Check("repo-root", "ok" if namespace else "warn", str(namespace or "not found"),
                        "" if namespace else "schemas/ not found; set GALNX_SCHEMA_DIR"))
    return checks


def summarise(checks: list[Check]) -> dict[str, object]:
    return {
        "checks": [c.to_json() for c in checks],
        "counts": {status: sum(1 for c in checks if c.status == status) for status in STATUSES},
        "ok": not any(c.status == "fail" for c in checks),
    }


def dumps_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)
