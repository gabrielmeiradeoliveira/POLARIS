"""Offline API and worker coverage for the local dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from polaris.core.models import AnalysisReport, AnalysisWarning, ProviderInfo, TokenUsage
from polaris.web.api import create_app
from polaris.web.store import WebStore
from polaris.web.worker import StaticAnalysisWorker


class InlineWorker:
    def __init__(self, store: WebStore) -> None:
        self.worker = StaticAnalysisWorker(store)

    def start(self, job_id: str) -> None:
        self.worker.run_inline(job_id)


def test_projects_and_static_analysis_are_persisted(temp_git_repo: Path, tmp_path: Path) -> None:
    (temp_git_repo / "src" / "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a / 0\n", encoding="utf-8"
    )
    store = WebStore(f"sqlite:///{tmp_path / 'dashboard.sqlite3'}", initialize=True)
    client = TestClient(create_app(store.database_url, worker=InlineWorker(store), initialize=True))

    created = client.post("/api/projects", json={"name": "Sample", "path": str(temp_git_repo)})
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert client.get("/api/projects").json()[0]["id"] == project_id

    started = client.post(f"/api/projects/{project_id}/analyses", json={})
    assert started.status_code == 202
    detail = client.get(f"/api/analyses/{started.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"
    assert detail.json()["findings"]
    assert client.get("/api/analyses").json()[0]["id"] == started.json()["id"]


def test_rejects_non_repository_and_reports_missing_resources(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{tmp_path / 'dashboard.sqlite3'}", initialize=True))
    assert client.post("/api/projects", json={"name": "No", "path": str(tmp_path)}).status_code == 422
    assert client.get("/api/analyses/missing").status_code == 404


def test_api_persists_partial_analysis_status(temp_git_repo: Path, tmp_path: Path) -> None:
    store = WebStore(f"sqlite:///{tmp_path / 'dashboard.sqlite3'}", initialize=True)
    project = store.create_project("Sample", str(temp_git_repo))
    job = store.create_job(project["id"], None)
    assert store.complete(
        job["id"],
        store.claim_job(job["id"])["claim_token"],
        AnalysisReport(
            repository_root=str(temp_git_repo),
            target_description="synthetic partial analysis",
            modules_executed=["code_review"],
            provider=ProviderInfo(provider_name="fake", model_name="fake"),
            usage=TokenUsage(),
            warnings=[AnalysisWarning(code="PROVIDER_SKIPPED_BUDGET", message="synthetic")],
            status="incomplete",
        ),
    )

    detail = TestClient(create_app(store.database_url, initialize=True)).get(f"/api/analyses/{job['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "incomplete"


def test_claim_token_blocks_stale_worker_completion(tmp_path: Path) -> None:
    store = WebStore(f"sqlite:///{tmp_path / 'dashboard.sqlite3'}", initialize=True)
    project = store.create_project("Sample", str(tmp_path))
    job = store.create_job(project["id"], None)
    claim = store.claim_job(job["id"])
    assert claim is not None
    assert store.recover_interrupted_jobs(stale_after_seconds=-1) == 1
    replacement = store.claim_job(job["id"])
    assert replacement is not None
    assert replacement["claim_token"] != claim["claim_token"]
    assert not store.fail(job["id"], claim["claim_token"], "stale")


def test_worker_start_uses_a_separate_process(monkeypatch, tmp_path: Path) -> None:
    started: list[object] = []

    class ProcessStub:
        def __init__(self, **kwargs) -> None:
            started.append(kwargs)

        def start(self) -> None:
            started.append("started")

    worker = StaticAnalysisWorker(WebStore(f"sqlite:///{tmp_path / 'dashboard.sqlite3'}", initialize=True))
    worker.start("job-id")
    assert started == []
