"""Offline PAT flow: API import, isolated Git checkout, worker, and PR gate."""

from __future__ import annotations

import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from polaris.integrations.github.client import GitHubClient
from polaris.integrations.github.models import HttpResponse
from polaris.web.api import create_app
from polaris.web.store import WebStore
from polaris.web.worker import StaticAnalysisWorker


def _git(path: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=path, text=True).strip()


def test_pat_import_worker_and_pr_gate(monkeypatch, tmp_path: Path) -> None:
    repository = tmp_path / "fixture"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.email", "test@example.invalid")
    _git(repository, "config", "user.name", "Polaris Test")
    source = repository / "demo.py"
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "clean")
    base_sha = _git(repository, "rev-parse", "HEAD")
    source.write_text("def value():\n    return 1 / 0\n", encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "defect")
    head_sha = _git(repository, "rev-parse", "HEAD")

    class Transport:
        def request(self, method, path, *, headers, body, timeout_seconds):
            del method, headers, body, timeout_seconds
            if path.startswith("/user/repos"):
                return HttpResponse(
                    status_code=200,
                    body='[{"id":99,"name":"fixture","full_name":"local/fixture","owner":{"login":"local"},"default_branch":"main"}]',
                )
            if "/commits/main" in path:
                return HttpResponse(status_code=200, body=f'{{"sha":"{head_sha}"}}')
            return HttpResponse(
                status_code=200, body=f'{{"state":"open","head":{{"sha":"{head_sha}"}},"base":{{"sha":"{base_sha}"}}}}'
            )

    @contextmanager
    def local_checkout(owner: str, name: str, revision: str, token: str, **kwargs):
        del owner, name, token, kwargs
        with tempfile.TemporaryDirectory(prefix="polaris-e2e-") as workspace:
            checkout = Path(workspace) / "repository"
            subprocess.run(
                ["git", "clone", "--no-checkout", str(repository), str(checkout)], check=True, capture_output=True
            )
            subprocess.run(
                ["git", "-C", str(checkout), "checkout", "--detach", revision], check=True, capture_output=True
            )
            yield checkout

    monkeypatch.setattr("polaris.web.worker.checkout_github_repository", local_checkout)
    monkeypatch.setattr("polaris.web.worker.GitHubApiTransport", Transport)
    monkeypatch.setenv("POLARIS_GITHUB_TOKEN", "offline-test-token")
    monkeypatch.setenv("POLARIS_WEB_DATABASE", str(tmp_path / "pat-e2e.sqlite3"))
    database_url = f"sqlite:///{tmp_path / 'pat-e2e.sqlite3'}"
    store = WebStore(database_url, initialize=True)
    client = TestClient(
        create_app(
            database_url,
            worker=StaticAnalysisWorker(store),
            github_client=GitHubClient(Transport(), token="offline-test-token"),
            initialize=True,
        )
    )

    imported = client.post("/api/github/pat/import", json={"repository_id": 99})
    assert imported.status_code == 201
    project = imported.json()
    manual = client.post(f"/api/projects/{project['id']}/analyses", json={})
    assert manual.status_code == 202
    baseline = client.get(f"/api/analyses/{manual.json()['id']}").json()
    assert baseline["status"] == "completed"
    assert baseline["quality"]["grade"] == "F"

    pr = client.post(f"/api/projects/{project['id']}/github/pull-requests", json={"number": 7})
    assert pr.status_code == 202
    candidate = client.get(f"/api/analyses/{pr.json()['candidate_job_id']}").json()
    assert candidate["status"] == "completed"
    assert candidate["base_revision"] == base_sha
    assert candidate["head_sha"] == head_sha
    assert candidate["comparison"]["grade_delta"] == "A -> F"
    assert candidate["comparison"]["counts"]["new"] >= 1
    assert candidate["comparison"]["quality_gate"]["status"] == "FAILED"
