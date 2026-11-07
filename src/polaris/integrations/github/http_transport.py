"""Server-only GitHub API transport for local PAT development."""

from __future__ import annotations

from urllib.error import HTTPError
from urllib.request import Request, urlopen

from polaris.integrations.github.models import HttpResponse


class GitHubApiTransport:
    """Fixed GitHub API origin prevents arbitrary URL requests."""

    def request(
        self, method: str, path: str, *, headers: dict[str, str], body: str | None, timeout_seconds: float
    ) -> HttpResponse:
        if not path.startswith("/") or path.startswith("//"):
            raise OSError("Unsafe GitHub API path.")
        request = Request(
            "https://api.github.com" + path, data=body.encode() if body else None, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 -- fixed origin above
                return HttpResponse(
                    status_code=response.status, headers=dict(response.headers.items()), body=response.read().decode()
                )
        except HTTPError as exc:
            return HttpResponse(status_code=exc.code, headers=dict(exc.headers.items()), body=exc.read().decode())
