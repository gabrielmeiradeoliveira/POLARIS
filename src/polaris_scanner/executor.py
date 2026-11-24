from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ExecutionResult:
    """Structured result of an isolated analyzer subprocess execution."""

    status: str  # OK | TIMEOUT | NON_ZERO_EXIT | INVALID_JSON | EXECUTION_ERROR
    exit_code: int | None
    stdout: str
    stderr: str
    payload: dict[str, Any] | None
    error_message: str | None = None
    truncated: bool = False


def _truncate_text(text: str, max_bytes: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text, False
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated, True


def run_analyzer_subprocess(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int = 60,
    max_output_bytes: int = 5 * 1024 * 1024,
    env_overrides: Mapping[str, str] | None = None,
    input_data: str | None = None,
) -> ExecutionResult:
    """Execute an analyzer command safely without shell=True."""
    if not command or not all(isinstance(arg, str) and arg != "" for arg in command):
        return ExecutionResult(
            status="EXECUTION_ERROR",
            exit_code=None,
            stdout="",
            stderr="",
            payload=None,
            error_message="Command must be a non-empty sequence of non-empty strings",
        )

    safe_env = {
        k: v
        for k, v in os.environ.items()
        if k in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE", "PYTHONPATH", "DOTNET_ROOT", "JAVA_HOME"}
    }
    safe_env["PYTHONIOENCODING"] = "utf-8"
    if env_overrides:
        safe_env.update(env_overrides)

    creation_flags = 0
    preexec = None
    if os.name == "nt":
        creation_flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    else:
        preexec = lambda: os.nice(10)

    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            env=safe_env,
            input=input_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
            creationflags=creation_flags,
            preexec_fn=preexec,
        )
    except subprocess.TimeoutExpired as exc:
        out_raw = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err_raw = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        out, out_trunc = _truncate_text(out_raw, max_output_bytes)
        err, err_trunc = _truncate_text(err_raw, max_output_bytes)
        return ExecutionResult(
            status="TIMEOUT",
            exit_code=None,
            stdout=out,
            stderr=err,
            payload=None,
            error_message=f"Subprocess timed out after {timeout_seconds}s",
            truncated=out_trunc or err_trunc,
        )
    except OSError as exc:
        return ExecutionResult(
            status="EXECUTION_ERROR",
            exit_code=None,
            stdout="",
            stderr="",
            payload=None,
            error_message=f"Failed to start subprocess: {exc}",
        )

    out, out_trunc = _truncate_text(completed.stdout or "", max_output_bytes)
    err, err_trunc = _truncate_text(completed.stderr or "", max_output_bytes)
    truncated = out_trunc or err_trunc

    if completed.returncode != 0:
        return ExecutionResult(
            status="NON_ZERO_EXIT",
            exit_code=completed.returncode,
            stdout=out,
            stderr=err,
            payload=None,
            error_message=f"Subprocess exited with code {completed.returncode}",
            truncated=truncated,
        )

    try:
        payload = json.loads(out)
        if not isinstance(payload, dict):
            return ExecutionResult(
                status="INVALID_JSON",
                exit_code=completed.returncode,
                stdout=out,
                stderr=err,
                payload=None,
                error_message="Subprocess JSON output must be an object",
                truncated=truncated,
            )
    except json.JSONDecodeError as exc:
        return ExecutionResult(
            status="INVALID_JSON",
            exit_code=completed.returncode,
            stdout=out,
            stderr=err,
            payload=None,
            error_message=f"Invalid JSON from subprocess: {exc}",
            truncated=truncated,
        )

    return ExecutionResult(
        status="OK",
        exit_code=0,
        stdout=out,
        stderr=err,
        payload=payload,
        error_message=None,
        truncated=truncated,
    )
