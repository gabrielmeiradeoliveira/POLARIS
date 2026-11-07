"""Strict local fixture transport for the GitHub dry-run CLI.

This module deliberately implements no HTTP. It permits repeatable PR-review
demonstrations without credentials, network traffic, or publishing authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polaris.integrations.github.models import HttpResponse


class FixtureGitHubTransport:
    """Serve a single PR's API responses from a validated local JSON fixture."""

    def __init__(self, payload: dict[str, Any]) -> None:
        pull_request = payload.get("pull_request")
        files = payload.get("files")
        comments = payload.get("comments", [])
        if not isinstance(pull_request, dict) or not isinstance(files, list) or not isinstance(comments, list):
            raise ValueError("Fixture must contain object 'pull_request' and array 'files'/'comments' values.")
        self._pull_request = pull_request
        self._files = files
        self._comments = comments
        self.requests: list[tuple[str, str]] = []

    @classmethod
    def from_path(cls, path: Path) -> FixtureGitHubTransport:
        try:
            decoded = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"Cannot read GitHub fixture: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"GitHub fixture is not valid JSON: {path}") from exc
        if not isinstance(decoded, dict):
            raise ValueError("GitHub fixture root must be a JSON object.")
        return cls(decoded)

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        body: str | None,
        timeout_seconds: float,
    ) -> HttpResponse:
        del headers, body, timeout_seconds
        self.requests.append((method, path))
        if method != "GET":
            return HttpResponse(status_code=405, body=json.dumps({"message": "fixture is read-only"}))
        if "/files?" in path:
            return HttpResponse(status_code=200, body=json.dumps(self._files))
        if "/comments?" in path:
            return HttpResponse(status_code=200, body=json.dumps(self._comments))
        if "/pulls/" in path:
            return HttpResponse(status_code=200, body=json.dumps(self._pull_request))
        return HttpResponse(status_code=404, body=json.dumps({"message": "fixture path not found"}))
