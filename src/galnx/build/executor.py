"""Execute manifest-declared build commands with per-command logging (M6-b).

The executor runs exactly what the user wrote in ``build.commands``.  It never
consults engine planning guidance: plan steps are advisory and are not executed
automatically.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .config import BuildConfig, BuildError, Command, command_display, parse_build_section

MAX_LOG_CHARS = 262144
_HEAD_CHARS = MAX_LOG_CHARS // 2
_TAIL_CHARS = MAX_LOG_CHARS - _HEAD_CHARS
TAIL_LINES = 20
_SAFE_LABEL = re.compile(r"[^A-Za-z0-9._-]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_label(value: str) -> str:
    """Filesystem-safe project label for log file names."""
    cleaned = _SAFE_LABEL.sub("_", value).strip("._-")
    return cleaned or "project"


def truncate_text(text: str, limit: int = MAX_LOG_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    head = text[:_HEAD_CHARS]
    tail = text[-_TAIL_CHARS:]
    dropped = len(text) - _HEAD_CHARS - _TAIL_CHARS
    marker = "\n...[truncated %d chars]...\n" % dropped
    return head + marker + tail, True


def tail_lines(text: str, count: int = TAIL_LINES) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in normalized.split("\n") if line != ""]
    return lines[-count:]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _combined_output(stdout: Any, stderr: Any) -> str:
    out = _text(stdout)
    err = _text(stderr)
    if out and err and not out.endswith("\n"):
        out += "\n"
    return out + err


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_artifact(workdir: Path | str, artifact: str | None) -> dict[str, Any] | None:
    """Return artifact metadata when the declared artifact exists, else None."""
    if not artifact:
        return None
    candidate = Path(artifact)
    path = candidate if candidate.is_absolute() else Path(workdir) / candidate
    if not path.is_file():
        return None
    resolved = path.resolve()
    return {
        "path": Path(artifact).as_posix(),
        "abs_path": str(resolved),
        "size": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def normalize_commands(commands: tuple[Command, ...]) -> list[Any]:
    normalized: list[Any] = []
    for command in commands:
        if isinstance(command, str):
            normalized.append(command)
        else:
            normalized.append(list(command))
    return normalized


def build_environment(config: BuildConfig, manifest_path: Path, project_label: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update(config.env)
    env["GALNX_MANIFEST"] = str(Path(manifest_path).resolve())
    env["GALNX_PROJECT"] = project_label
    return env


def _write_log(path: Path, header: list[str], output: str, truncated: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = list(header)
    lines.append("# truncated: %s" % ("yes" if truncated else "no"))
    lines.append("")
    body = "\n".join(lines) + output
    path.write_text(body, encoding="utf-8", errors="replace")


def run_build_commands(
    manifest_path: Path | str,
    data: Mapping[str, Any],
    logs_dir: Path | str,
    project_label: str,
) -> tuple[list[dict[str, Any]], bool]:
    """Run all declared commands sequentially, stopping at the first failure.

    Returns ``(commands, ok)`` where each command dict is report/cache friendly:
    ``{command, duration_s, exit_code, log, tail, ok}``.  ``exit_code`` is None
    for timeouts.
    """
    manifest_path = Path(manifest_path)
    config = parse_build_section(data, manifest_path)
    logs_dir = Path(logs_dir)
    label = safe_label(project_label)
    env = build_environment(config, manifest_path, project_label)
    results: list[dict[str, Any]] = []
    if not config.commands:
        return results, True
    logs_dir.mkdir(parents=True, exist_ok=True)
    for index, command in enumerate(config.commands, start=1):
        display = command_display(command)
        shell = isinstance(command, str)
        log_path = logs_dir / ("%s-%d.log" % (label, index))
        header = [
            "# command: %s" % display,
            "# shell: %s" % ("yes" if shell else "no"),
            "# cwd: %s" % config.workdir,
            "# timeout_s: %s" % config.timeout_s,
            "# env: %s" % ", ".join(sorted(config.env)),
            "# started: %s" % utc_now(),
        ]
        started = time.monotonic()
        timed_out = False
        exit_code: int | None = None
        output = ""
        error = ""
        try:
            completed = subprocess.run(
                command,
                shell=shell,
                cwd=str(config.workdir),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=config.timeout_s,
            )
            exit_code = completed.returncode
            output = _combined_output(completed.stdout, completed.stderr)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = None
            output = _combined_output(getattr(exc, "stdout", None), getattr(exc, "stderr", None))
            error = "timed out after %ss" % config.timeout_s
        except OSError as exc:
            exit_code = None
            error = "failed to start command: %s" % exc
        duration_s = round(time.monotonic() - started, 4)
        if timed_out:
            output += "\n[galnx] %s\n" % error
        elif exit_code != 0:
            output += "\n[galnx] command exited with code %s\n" % exit_code
        truncated_text, truncated = truncate_text(output)
        _write_log(log_path, header, truncated_text, truncated)
        ok = exit_code == 0
        results.append(
            {
                "command": display,
                "shell": shell,
                "duration_s": duration_s,
                "exit_code": exit_code,
                "log": str(log_path),
                "tail": tail_lines(output),
                "ok": ok,
                "error": error,
            }
        )
        if not ok:
            return results, False
    return results, True
