"""Ephemeral, non-executing GitHub App repository checkout."""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_PART = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{40,64}$")


class GitHubCheckoutError(RuntimeError):
    """A safe checkout failure without token or URL disclosure."""


def _validate(value: str, expression: re.Pattern[str], label: str) -> str:
    if not expression.fullmatch(value):
        raise GitHubCheckoutError(f"Invalid GitHub {label}.")
    return value


def _size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _encode_basic_token(token: str) -> str:
    return base64.b64encode(f"x-access-token:{token}".encode()).decode("ascii")


def _classify_git_failure(stage: str, exc: Exception) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"Authorized repository checkout failed ({stage} timed out after {int(exc.timeout)}s)."
    if isinstance(exc, subprocess.CalledProcessError):
        stderr = (exc.stderr or "").lower()
        if (
            "could not read username" in stderr
            or "authentication failed" in stderr
            or "invalid username or token" in stderr
            or "the requested url returned error: 401" in stderr
            or "the requested url returned error: 403" in stderr
        ):
            reason = "Git HTTP authentication rejected by remote"
        elif "repository not found" in stderr or "the requested url returned error: 404" in stderr:
            reason = "remote repository not found or inaccessible"
        elif (
            "reference is not a tree" in stderr
            or "did not match any file(s) known to git" in stderr
            or "unable to read tree" in stderr
            or "bad object" in stderr
        ):
            reason = "target commit SHA not found in repository"
        elif (
            "unable to access" in stderr
            or "could not resolve host" in stderr
            or "ssl certificate problem" in stderr
            or "gnutls_handshake" in stderr
        ):
            reason = "Git HTTPS or TLS connectivity error"
        elif "no space left on device" in stderr:
            reason = "temporary workspace out of disk space"
        else:
            reason = f"exit code {exc.returncode}"
        return f"Authorized repository checkout failed ({stage}: {reason})."
    if isinstance(exc, FileNotFoundError):
        return f"Authorized repository checkout failed ({stage}: git executable not found)."
    return f"Authorized repository checkout failed ({stage}: {type(exc).__name__})."


@contextmanager
def checkout_github_repository(
    owner: str,
    repository: str,
    revision: str,
    token: str,
    *,
    timeout_seconds: int = 60,
    max_bytes: int = 512 * 1024 * 1024,
) -> Iterator[Path]:
    """Yield a detached checkout. Git hooks, local protocols and config are disabled."""
    owner = _validate(owner, _PART, "owner")
    repository = _validate(repository, _PART, "repository")
    revision = _validate(revision, _SHA, "revision")
    if not token or not token.strip():
        raise GitHubCheckoutError("GitHub installation token is unavailable.")
    basic_credentials = _encode_basic_token(token.strip())
    with tempfile.TemporaryDirectory(prefix="polaris-github-") as workspace:
        path = Path(workspace) / "repository"
        environment = os.environ | {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic_credentials}",
        }
        stage = "git clone"
        try:
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-c",
                    "protocol.file.allow=never",
                    "clone",
                    "--no-checkout",
                    "--filter=blob:none",
                    f"https://github.com/{owner}/{repository}.git",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=environment,
            )
            stage = "git checkout"
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(path),
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-c",
                    "protocol.file.allow=never",
                    "checkout",
                    "--detach",
                    revision,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise GitHubCheckoutError(_classify_git_failure(stage, exc)) from None
        if _size(path) > max_bytes:
            raise GitHubCheckoutError("Repository checkout exceeds configured disk limit.")
        yield path
        shutil.rmtree(path, ignore_errors=True)
