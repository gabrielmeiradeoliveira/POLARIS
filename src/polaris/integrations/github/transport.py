"""Injectable transport boundary. Production HTTP is intentionally not enabled here."""

from __future__ import annotations

from typing import Protocol

from polaris.integrations.github.models import HttpResponse


class GitHubTransport(Protocol):
    """Transport contract suitable for local fixtures and future authenticated adapters."""

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        body: str | None,
        timeout_seconds: float,
    ) -> HttpResponse: ...
