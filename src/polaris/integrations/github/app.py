"""Offline-safe GitHub App authentication and webhook primitives."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from polaris.integrations.github.client import GitHubClient
from polaris.integrations.github.models import body_as_object
from polaris.integrations.github.transport import GitHubTransport


class GitHubAppSecurityError(ValueError):
    """Raised without leaking credentials or webhook contents."""


def verify_webhook_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """Verify GitHub's sha256 signature before decoding an event body."""
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.removeprefix("sha256="), expected)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class GitHubAppCredentials:
    app_id: str
    private_key_path: Path

    def jwt(self, *, now: int | None = None) -> str:
        issued_at = int(time.time()) if now is None else now
        header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
        payload = _b64(json.dumps({"iat": issued_at - 60, "exp": issued_at + 540, "iss": self.app_id}, separators=(",", ":")).encode())
        try:
            key = serialization.load_pem_private_key(self.private_key_path.read_bytes(), password=None)
        except (OSError, ValueError, TypeError) as exc:
            raise GitHubAppSecurityError("GitHub App private key is unavailable or invalid.") from exc
        signature = key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
        return f"{header}.{payload}.{_b64(signature)}"


class GitHubAppClient:
    """GitHub App calls over an injected transport; tokens are never persisted."""

    def __init__(self, transport: GitHubTransport, credentials: GitHubAppCredentials) -> None:
        self._transport = transport
        self._credentials = credentials

    def installation_token(self, installation_id: int) -> str:
        if installation_id < 1:
            raise ValueError("GitHub installation id must be positive.")
        client = GitHubClient(self._transport, token=self._credentials.jwt())
        response = client._request("POST", f"/app/installations/{installation_id}/access_tokens")
        token = body_as_object(response.body).get("token")
        if not isinstance(token, str) or not token:
            raise GitHubAppSecurityError("GitHub installation token response is invalid.")
        return token

    def list_repositories(self, installation_id: int) -> list[dict[str, Any]]:
        token = self.installation_token(installation_id)
        entries = GitHubClient(self._transport, token=token)._list_pages("/installation/repositories?per_page=100&page=1")
        if not all(isinstance(entry, dict) for entry in entries):
            raise GitHubAppSecurityError("GitHub repository response is invalid.")
        return entries

    def create_check_run(self, installation_id: int, owner: str, repository: str, payload: dict[str, Any]) -> None:
        GitHubClient(self._transport, token=self.installation_token(installation_id))._request(
            "POST", f"/repos/{owner}/{repository}/check-runs", payload
        )
