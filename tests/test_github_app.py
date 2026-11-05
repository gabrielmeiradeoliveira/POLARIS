"""Offline coverage for GitHub App trust boundaries."""

from __future__ import annotations

import hashlib
import hmac
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from polaris.integrations.github.app import GitHubAppClient, GitHubAppCredentials, verify_webhook_signature
from polaris.integrations.github.client import GitHubClient
from polaris.integrations.github.models import HttpResponse
from polaris.web.api import create_app


def _signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_signature_is_constant_time_compatible() -> None:
    body = b'{"ok":true}'
    assert verify_webhook_signature(body, _signature(body, "webhook-secret"), "webhook-secret")
    assert not verify_webhook_signature(body, "sha256=" + "0" * 64, "webhook-secret")
    assert not verify_webhook_signature(body, None, "webhook-secret")


def test_app_uses_short_lived_token_and_paginates_repositories(tmp_path) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path = tmp_path / "app.pem"
    key_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )

    class Transport:
        def request(self, method, path, *, headers, body, timeout_seconds):
            del headers, body, timeout_seconds
            if path.endswith("access_tokens"):
                return HttpResponse(status_code=201, body='{"token":"short-lived"}')
            if path.endswith("page=1"):
                return HttpResponse(
                    status_code=200,
                    body='[{"id":1,"full_name":"acme/one"}]',
                    headers={
                        "Link": '<https://api.github.com/installation/repositories?per_page=100&page=2>; rel="next"'
                    },
                )
            assert method == "GET"
            return HttpResponse(status_code=200, body='[{"id":2,"full_name":"acme/two"}]')

    client = GitHubAppClient(Transport(), GitHubAppCredentials("123", key_path))
    assert [entry["id"] for entry in client.list_repositories(9)] == [1, 2]


def test_webhook_rejects_bad_signature_and_deduplicates(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-secret")
    client = TestClient(create_app(f"sqlite:///{tmp_path / 'github.sqlite3'}", initialize=True))
    body = json.dumps(
        {"installation": {"id": 9, "account": {"id": 7, "login": "acme", "type": "Organization"}}}
    ).encode()
    headers = {
        "X-GitHub-Delivery": "delivery-1",
        "X-GitHub-Event": "installation",
        "X-Hub-Signature-256": _signature(body, "webhook-secret"),
    }
    assert (
        client.post(
            "/api/github/webhooks", content=body, headers={**headers, "X-Hub-Signature-256": "sha256=bad"}
        ).status_code
        == 401
    )
    assert client.post("/api/github/webhooks", content=body, headers=headers).json() == {"status": "accepted"}
    assert client.post("/api/github/webhooks", content=body, headers=headers).json() == {"status": "duplicate"}


def test_policy_requires_admin_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("POLARIS_ADMIN_TOKEN", "local-only")
    store_url = f"sqlite:///{tmp_path / 'github.sqlite3'}"
    client = TestClient(create_app(store_url, initialize=True))
    store = client.app.state if hasattr(client.app, "state") else None
    del store
    # Installations originate only from a signed GitHub event.
    from polaris.web.store import WebStore

    database = WebStore(store_url, initialize=True)
    installation = database.upsert_github_installation({"id": 9, "account": {"id": 7, "login": "acme"}})
    assert (
        database.sync_github_repositories(
            9, [{"id": 3, "name": "repo", "full_name": "acme/repo", "owner": {"login": "acme"}}]
        )
        == 1
    )
    assert client.get("/api/github/installations/9/repositories").json()[0]["full_name"] == "acme/repo"
    path = "/api/github/installations/9/policies"
    assert client.post(path, json={"policy": {"minimum_grade": "B"}}).status_code == 401
    response = client.post(
        path, json={"policy": {"minimum_grade": "B"}}, headers={"X-Polaris-Admin-Token": "local-only"}
    )
    assert response.status_code == 201
    assert response.json()["version"] == 1
    assert installation["status"] == "active"


def test_pat_status_and_repository_pagination(tmp_path) -> None:
    class Transport:
        def request(self, method, path, *, headers, body, timeout_seconds):
            del method, headers, body, timeout_seconds
            if path == "/user":
                return HttpResponse(status_code=200, body='{"id":1,"login":"local-dev"}')
            if path.endswith("page=1"):
                return HttpResponse(
                    status_code=200,
                    body='[{"id":1,"name":"one","full_name":"local/one","owner":{"login":"local"}}]',
                    headers={
                        "Link": '<https://api.github.com/user/repos?affiliation=owner,collaborator,organization_member&per_page=100&page=2>; rel="next"'
                    },
                )
            return HttpResponse(
                status_code=200,
                body='[{"id":2,"name":"two","full_name":"local/two","owner":{"login":"local"},"default_branch":"main"}]',
            )

    client = TestClient(
        create_app(
            f"sqlite:///{tmp_path / 'pat.sqlite3'}",
            github_client=GitHubClient(Transport(), token="test"),
            initialize=True,
        )
    )
    assert client.get("/api/github/pat/status").json() == {"configured": True, "login": "local-dev", "id": 1}
    assert [item["full_name"] for item in client.get("/api/github/pat/repositories").json()] == [
        "local/one",
        "local/two",
    ]


def test_pat_reports_auth_failure(tmp_path) -> None:
    class Transport:
        def request(self, *args, **kwargs):
            return HttpResponse(status_code=401, body="{}")

    client = TestClient(
        create_app(
            f"sqlite:///{tmp_path / 'pat.sqlite3'}",
            github_client=GitHubClient(Transport(), token="test"),
            initialize=True,
        )
    )
    assert client.get("/api/github/pat/status").status_code == 502


def test_pat_pr_analysis_pins_base_and_head(tmp_path) -> None:
    class Transport:
        def request(self, method, path, *, headers, body, timeout_seconds):
            del method, headers, body, timeout_seconds
            if path.startswith("/user/repos"):
                return HttpResponse(
                    status_code=200,
                    body='[{"id":2,"name":"repo","full_name":"local/repo","owner":{"login":"local"},"default_branch":"main"}]',
                )
            return HttpResponse(
                status_code=200,
                body='{"state":"open","head":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"base":{"sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}',
            )

    database = f"sqlite:///{tmp_path / 'pr.sqlite3'}"
    client = TestClient(create_app(database, github_client=GitHubClient(Transport(), token="test"), initialize=True))
    project = client.post("/api/github/pat/import", json={"repository_id": 2}).json()
    response = client.post(f"/api/projects/{project['id']}/github/pull-requests", json={"number": 7})
    assert response.status_code == 202
    candidate = client.get(f"/api/analyses/{response.json()['candidate_job_id']}").json()
    assert candidate["base_revision"] == "b" * 40
    assert candidate["head_sha"] == "a" * 40
    assert candidate["pull_request_number"] == 7
