"""FastAPI application for the Polaris (POLARIS) continuous code quality platform."""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from polaris.core.errors import RepositoryError
from polaris.git.analyzer import GitAnalyzer
from polaris.integrations.github.app import verify_webhook_signature
from polaris.integrations.github.client import GitHubClient
from polaris.integrations.github.http_transport import GitHubApiTransport
from polaris.integrations.github.models import GitHubIntegrationError, PullRequestMetadata
from polaris.quality import QualityGateConfig
from polaris.web.store import IntegrityError, WebStore
from polaris.web.worker import StaticAnalysisWorker, synchronize_github_platform


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1)
    gate_config: QualityGateConfig | None = None


class AnalysisCreate(BaseModel):
    base_revision: str | None = Field(default=None, max_length=200)
    analysis_mode: Literal["project", "pr"] = "project"
    baseline_job_id: str | None = Field(default=None, max_length=36)


class PullRequestComparisonCreate(BaseModel):
    baseline_job_id: str = Field(min_length=1, max_length=36)
    candidate_job_id: str = Field(min_length=1, max_length=36)
    gate_config: QualityGateConfig | None = None


class PolicyUpdate(BaseModel):
    policy: dict[str, object]
    repository_id: str | None = Field(default=None, max_length=36)


class GitHubImport(BaseModel):
    repository_id: int = Field(gt=0)


class GitHubPullRequestCreate(BaseModel):
    number: int = Field(gt=0)


class GitHubSyncRequest(BaseModel):
    sync_prs: bool = True
    enqueue_jobs: bool = True
    project_id: str | None = None


class SyncSettingsUpdate(BaseModel):
    auto_discover_repos: bool | None = None
    auto_analyze_initial: bool | None = None
    auto_analyze_prs: bool | None = None
    allow_private_repo_analysis: bool | None = None
    allow_fork_pr_analysis: bool | None = None
    sync_interval_seconds: int | None = Field(default=None, ge=30, le=86400)


_GRADE_SORT_RANK: dict[str, int] = {
    "A": 5,
    "B": 4,
    "C": 3,
    "D": 2,
    "F": 1,
    "NOT_RATED": 0,
}


def _filter_and_sort_projects(
    projects: list[dict[str, Any]],
    *,
    search: str | None = None,
    grade: str | None = None,
    status: str | None = None,
    sync_status: str | None = None,
    language: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[dict[str, Any]]:
    filtered = list(projects)
    if search and search.strip():
        q = search.strip().lower()
        filtered = [
            p
            for p in filtered
            if q in str(p.get("name") or "").lower()
            or q in str(p.get("owner") or "").lower()
            or q in str(p.get("language") or "").lower()
            or q in str(p.get("last_analyzed_sha") or "").lower()
        ]
    if grade and grade != "ALL":
        if grade == "NOT_RATED":
            filtered = [p for p in filtered if (p.get("latest_grade") or "NOT_RATED") == "NOT_RATED"]
        else:
            filtered = [p for p in filtered if p.get("latest_grade") == grade]
    if status and status != "ALL":
        filtered = [p for p in filtered if p.get("analysis_status") == status]
    if sync_status and sync_status != "ALL":
        filtered = [p for p in filtered if p.get("sync_status") == sync_status]
    if language and language != "ALL":
        filtered = [p for p in filtered if str(p.get("language") or "").lower() == language.lower()]

    reverse = sort_dir.lower() != "asc"
    if sort_by == "name":
        filtered.sort(key=lambda p: str(p.get("full_name") or p.get("name") or "").lower(), reverse=reverse)
    elif sort_by == "grade":
        filtered.sort(
            key=lambda p: _GRADE_SORT_RANK.get(str(p.get("latest_grade") or "NOT_RATED"), 0),
            reverse=reverse,
        )
    elif sort_by == "score":
        filtered.sort(
            key=lambda p: float(p["latest_score"]) if isinstance(p.get("latest_score"), (int, float)) else -1.0,
            reverse=reverse,
        )
    elif sort_by == "vulnerabilities":
        filtered.sort(
            key=lambda p: int(p["vulnerability_count"]) if isinstance(p.get("vulnerability_count"), int) else -1,
            reverse=reverse,
        )
    elif sort_by == "findings":
        filtered.sort(
            key=lambda p: int(p["findings_count"]) if isinstance(p.get("findings_count"), int) else -1,
            reverse=reverse,
        )
    elif sort_by == "last_analyzed":
        filtered.sort(
            key=lambda p: str(p.get("last_successful_analysis_at") or ""),
            reverse=reverse,
        )
    else:
        filtered.sort(key=lambda p: str(p.get("created_at") or ""), reverse=reverse)
    return filtered


def create_app(
    database_url: str | None = None,
    worker: StaticAnalysisWorker | None = None,
    github_client: GitHubClient | None = None,
    *,
    initialize: bool = False,
) -> FastAPI:
    store = WebStore(database_url, initialize=initialize)
    active_worker = worker or StaticAnalysisWorker(store)
    pat_client = github_client or (
        GitHubClient(GitHubApiTransport(), token=os.environ["POLARIS_GITHUB_TOKEN"])
        if os.environ.get("POLARIS_GITHUB_TOKEN")
        else None
    )
    app = FastAPI(title="Polaris Continuous Code Quality Platform", version="0.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_admin(x_polaris_admin_token: str | None = Header(default=None)) -> None:
        expected = os.environ.get("POLARIS_ADMIN_TOKEN")
        if not expected or not x_polaris_admin_token or not hmac.compare_digest(expected, x_polaris_admin_token):
            raise HTTPException(status_code=401, detail="Administrator authorization is required.")

    @app.get("/api/health")
    def health(response: Response) -> dict[str, str]:
        try:
            store.healthcheck()
        except Exception:
            response.status_code = 503
            return {"status": "unavailable", "product": "Polaris"}
        return {"status": "ok", "product": "Polaris"}

    def github_pat_client() -> GitHubClient:
        if pat_client is None:
            raise HTTPException(status_code=503, detail="POLARIS_GITHUB_TOKEN is not configured for local development.")
        return pat_client

    @app.get("/api/github/pat/status")
    def github_pat_status() -> dict[str, object]:
        try:
            user = github_pat_client().authenticated_user()
        except GitHubIntegrationError as exc:
            raise HTTPException(status_code=502, detail=f"GitHub authentication failed: {exc.category.value}.") from exc
        return {"configured": True, "login": user["login"], "id": user["id"]}

    @app.get("/api/github/pat/repositories")
    def github_pat_repositories() -> list[dict[str, object]]:
        try:
            repositories = github_pat_client().list_accessible_repositories()
        except GitHubIntegrationError as exc:
            raise HTTPException(
                status_code=502, detail=f"GitHub repository discovery failed: {exc.category.value}."
            ) from exc
        safe: list[dict[str, object]] = []
        for repository in repositories:
            owner = repository.get("owner") if isinstance(repository.get("owner"), dict) else {}
            if (
                isinstance(repository.get("id"), int)
                and isinstance(repository.get("name"), str)
                and isinstance(repository.get("full_name"), str)
                and isinstance(owner.get("login"), str)
            ):
                safe.append(
                    {
                        "id": repository["id"],
                        "owner": owner["login"],
                        "name": repository["name"],
                        "full_name": repository["full_name"],
                        "default_branch": repository.get("default_branch"),
                        "language": repository.get("language"),
                        "private": bool(repository.get("private", False)),
                        "archived": bool(repository.get("archived", False)),
                    }
                )
        return safe

    @app.post("/api/github/sync")
    @app.post("/api/github/pat/sync")
    def sync_github(payload: GitHubSyncRequest | None = None) -> dict[str, object]:
        req = payload or GitHubSyncRequest()
        client = github_pat_client()
        try:
            summary = synchronize_github_platform(
                store,
                client,
                worker=active_worker,
                sync_prs=req.sync_prs,
                enqueue_jobs=req.enqueue_jobs,
                project_id_filter=req.project_id,
            )
        except GitHubIntegrationError as exc:
            store.record_sync_outcome("failed", error=f"GitHub synchronization failed: {exc.category.value}.")
            raise HTTPException(
                status_code=502, detail=f"GitHub synchronization failed: {exc.category.value}."
            ) from exc
        return {
            **summary,
            "projects": store.list_projects(),
            "pull_requests": store.list_pull_requests(project_id=req.project_id),
            "settings": store.get_sync_settings(),
        }

    @app.post("/api/github/pat/import", status_code=201)
    def import_github_repository(payload: GitHubImport) -> dict[str, object]:
        try:
            repositories = github_pat_client().list_accessible_repositories()
        except GitHubIntegrationError as exc:
            raise HTTPException(
                status_code=502, detail=f"GitHub repository discovery failed: {exc.category.value}."
            ) from exc
        repository = next((item for item in repositories if item.get("id") == payload.repository_id), None)
        if repository is None:
            raise HTTPException(status_code=404, detail="GitHub repository is not accessible to this token.")
        try:
            return store.import_github_project(repository)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/github/pull-requests", status_code=202)
    def analyze_github_pull_request(project_id: str, payload: GitHubPullRequestCreate) -> dict[str, object]:
        project = store.get_project(project_id)
        if not project or not project.get("github_repository_id"):
            raise HTTPException(status_code=404, detail="Imported GitHub project not found.")
        try:
            accessible = github_pat_client().list_accessible_repositories()
            repository = next((item for item in accessible if item.get("id") == project["github_repository_id"]), None)
            if repository is None:
                store.reconcile_github_repositories(accessible, mark_missing_inaccessible=True)
                raise HTTPException(status_code=403, detail="GitHub repository is no longer accessible to this token.")
            pr = github_pat_client().get_pull_request(
                str(project["github_owner"]), str(project["github_name"]), payload.number
            )
        except GitHubIntegrationError as exc:
            raise HTTPException(
                status_code=502, detail=f"GitHub pull request lookup failed: {exc.category.value}."
            ) from exc
        store.reconcile_project_pull_requests(project_id, [pr], mark_missing_closed=False)
        if pr.state.lower() != "open":
            raise HTTPException(status_code=422, detail="Only open pull requests can be analyzed.")
        scheduled = store.ensure_pr_analysis_jobs(
            project_id,
            payload.number,
            pr.base_sha,
            pr.head_sha,
            is_fork=pr.is_fork,
            force=True,
        )
        if scheduled is None:
            raise HTTPException(status_code=422, detail="Unable to schedule pull request analysis.")
        if not scheduled.get("reused"):
            if not scheduled.get("base_reused") and scheduled.get("base_job_id"):
                active_worker.start(str(scheduled["base_job_id"]))
            active_worker.start(str(scheduled["candidate_job_id"]))
        return {
            "base_job_id": scheduled["base_job_id"],
            "candidate_job_id": scheduled["candidate_job_id"],
            "base_sha": pr.base_sha,
            "head_sha": pr.head_sha,
            "number": payload.number,
            "reused": bool(scheduled.get("reused", False)),
        }

    @app.get("/api/projects")
    def list_projects(
        search: str | None = None,
        grade: str | None = None,
        status: str | None = None,
        sync_status: str | None = None,
        language: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> list[dict[str, object]]:
        projects = store.list_projects()
        return _filter_and_sort_projects(
            projects,
            search=search,
            grade=grade,
            status=status,
            sync_status=sync_status,
            language=language,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

    @app.get("/api/repositories")
    def list_repositories(
        search: str | None = None,
        grade: str | None = None,
        status: str | None = None,
        sync_status: str | None = None,
        language: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = Query(default=1, ge=1),
        per_page: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, object]:
        all_projects = store.list_projects()
        languages = sorted(
            {str(p["language"]) for p in all_projects if isinstance(p.get("language"), str) and p["language"]}
        )
        filtered = _filter_and_sort_projects(
            all_projects,
            search=search,
            grade=grade,
            status=status,
            sync_status=sync_status,
            language=language,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        total = len(filtered)
        start = (page - 1) * per_page
        items = filtered[start : start + per_page]
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "languages": languages,
            "sync_settings": store.get_sync_settings(),
        }

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, object]:
        project = store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        all_jobs = store.list_jobs(project_id=project_id)
        project["analyses"] = all_jobs
        project["pull_requests"] = store.list_pull_requests(project_id=project_id)
        latest_job_id = project.get("latest_job_id")
        latest_job = store.get_job(str(latest_job_id)) if latest_job_id else None
        # Ensure strict repository isolation: never attach a job belonging to another project
        if latest_job and latest_job.get("project_id") == project_id:
            project["latest_analysis"] = latest_job
        else:
            project["latest_analysis"] = None

        project_runs = [
            j for j in reversed(all_jobs) if (j.get("analysis_mode") or "project") == "project" and not j.get("pull_request_number")
        ]
        project["quality_trend"] = [
            {
                "job_id": j["id"],
                "commit_sha": j.get("commit_sha") or j.get("head_sha") or j.get("base_revision"),
                "status": j.get("status"),
                "grade": j.get("quality", {}).get("grade") if isinstance(j.get("quality"), dict) else "NOT_RATED",
                "score": j.get("quality", {}).get("score") if isinstance(j.get("quality"), dict) else None,
                "findings_count": j.get("findings_count", 0),
                "vulnerability_count": j.get("vulnerability_count", 0),
                "bug_count": j.get("bug_count", 0),
                "created_at": j.get("created_at"),
            }
            for j in project_runs
        ]
        return project

    @app.get("/api/projects/{project_id}/pull-requests")
    def list_project_pull_requests(project_id: str, state: str | None = None) -> list[dict[str, object]]:
        if store.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return store.list_pull_requests(project_id=project_id, state=state)

    @app.get("/api/projects/{project_id}/pull-requests/{pr_number}")
    def get_project_pull_request_detail(project_id: str, pr_number: int) -> dict[str, object]:
        detail = store.get_pull_request(project_id=project_id, pr_number=pr_number)
        if detail is None:
            raise HTTPException(status_code=404, detail="Pull request not found.")
        return detail

    @app.get("/api/pull-requests")
    def list_all_pull_requests(
        project_id: str | None = None,
        state: str | None = None,
    ) -> list[dict[str, object]]:
        return store.list_pull_requests(project_id=project_id, state=state)

    @app.get("/api/pull-requests/{pr_id}")
    def get_pull_request_by_id(pr_id: str) -> dict[str, object]:
        detail = store.get_pull_request(pr_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Pull request not found.")
        return detail

    @app.get("/api/findings")
    def list_global_findings(
        project_id: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        finding_type: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, object]]:
        return store.list_global_findings(
            project_id=project_id,
            severity=severity,
            category=category,
            finding_type=finding_type,
            search=search,
        )

    @app.get("/api/analytics")
    def get_analytics() -> dict[str, object]:
        return store.get_analytics_summary()

    @app.get("/api/settings")
    def get_settings() -> dict[str, object]:
        settings = store.get_sync_settings()
        has_pat = pat_client is not None
        has_webhook = bool(os.environ.get("GITHUB_WEBHOOK_SECRET"))
        return {
            **settings,
            "pat_configured": has_pat,
            "github_app_webhook_configured": has_webhook,
            "sync_mode": "pat_polling" if has_pat else ("github_app_webhook" if has_webhook else "offline"),
            "realtime_webhooks": has_webhook and not has_pat,
            "pat_local_only": True,
        }

    @app.put("/api/settings")
    def update_settings(payload: SyncSettingsUpdate) -> dict[str, object]:
        dump = {k: v for k, v in payload.model_dump().items() if v is not None}
        store.update_sync_settings(dump)
        return get_settings()

    @app.put("/api/projects/{project_id}/gate")
    def update_project_gate(
        project_id: str, payload: QualityGateConfig, _: None = Depends(require_admin)
    ) -> dict[str, object]:
        updated = store.update_project_gate_config(project_id, payload)
        if updated is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return updated

    @app.post("/api/projects", status_code=201)
    def create_project(payload: ProjectCreate) -> dict[str, object]:
        path = Path(payload.path).expanduser().resolve()
        allowed_root = os.environ.get("POLARIS_REPOSITORIES_ROOT")
        if allowed_root and not path.is_relative_to(Path(allowed_root).resolve()):
            raise HTTPException(status_code=422, detail="Repository path is outside the allowed read-only mount.")
        try:
            GitAnalyzer(path)
        except RepositoryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            return store.create_project(payload.name.strip(), str(path), payload.gate_config)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Project path is already registered.") from exc

    @app.get("/api/analyses")
    def list_analyses(project_id: str | None = None) -> list[dict[str, object]]:
        return store.list_jobs(project_id=project_id)

    @app.post("/api/projects/{project_id}/analyses", status_code=202)
    def start_analysis(project_id: str, payload: AnalysisCreate) -> dict[str, object]:
        if store.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        if payload.baseline_job_id and store.get_job(payload.baseline_job_id) is None:
            raise HTTPException(status_code=404, detail="Baseline analysis job not found.")
        mode = "pr" if payload.baseline_job_id else payload.analysis_mode
        job = store.create_job(
            project_id,
            payload.base_revision,
            analysis_mode=mode,
            baseline_job_id=payload.baseline_job_id,
        )
        active_worker.start(job["id"])
        return store.get_job(job["id"]) or job

    @app.get("/api/analyses/{job_id}")
    def get_analysis(job_id: str) -> dict[str, object]:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis not found.")
        return job

    @app.post("/api/comparisons")
    def compare_analyses(payload: PullRequestComparisonCreate) -> dict[str, object]:
        result = store.compare_jobs(
            payload.baseline_job_id,
            payload.candidate_job_id,
            payload.gate_config,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Baseline or candidate analysis not found.")
        return result

    @app.post("/api/github/webhooks", status_code=202)
    async def github_webhook(
        request: Request,
        x_hub_signature_256: str | None = Header(default=None),
        x_github_delivery: str | None = Header(default=None),
        x_github_event: str | None = Header(default=None),
    ) -> dict[str, str]:
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        raw_body = await request.body()
        if not secret or not verify_webhook_signature(raw_body, x_hub_signature_256, secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature.")
        if not x_github_delivery or not x_github_event:
            raise HTTPException(status_code=422, detail="GitHub delivery and event headers are required.")
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="GitHub webhook body must be JSON.") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="GitHub webhook body must be an object.")
        if not store.record_webhook_delivery(x_github_delivery, x_github_event):
            return {"status": "duplicate"}
        installation = payload.get("installation")
        if x_github_event == "installation" and isinstance(installation, dict):
            if payload.get("action") in {"created", "new_permissions_accepted"}:
                store.upsert_github_installation(installation)
                repos = payload.get("repositories")
                if isinstance(repos, list):
                    store.reconcile_github_repositories(repos, mark_missing_inaccessible=False)
            elif payload.get("action") == "deleted" and isinstance(installation.get("id"), int):
                store.deactivate_github_installation(installation["id"])
        elif x_github_event == "installation_repositories":
            added = payload.get("repositories_added")
            if isinstance(added, list) and added:
                store.reconcile_github_repositories(added, mark_missing_inaccessible=False)
        elif x_github_event == "pull_request":
            repo_payload = payload.get("repository")
            pr_payload = payload.get("pull_request")
            action = str(payload.get("action") or "")
            if isinstance(repo_payload, dict) and isinstance(pr_payload, dict):
                proj = store.import_github_project(repo_payload)
                head = pr_payload.get("head") if isinstance(pr_payload.get("head"), dict) else {}
                base = pr_payload.get("base") if isinstance(pr_payload.get("base"), dict) else {}
                user = pr_payload.get("user") if isinstance(pr_payload.get("user"), dict) else {}
                head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
                base_repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
                if isinstance(head.get("sha"), str) and isinstance(base.get("sha"), str):
                    pr_meta = PullRequestMetadata(
                        owner=str(proj.get("github_owner") or "unknown"),
                        repository=str(proj.get("github_name") or "unknown"),
                        number=int(pr_payload.get("number") or payload.get("number") or 1),
                        title=str(pr_payload.get("title") or f"PR #{pr_payload.get('number', 1)}"),
                        state=str(pr_payload.get("state") or "open"),
                        head_sha=head["sha"],
                        base_sha=base["sha"],
                        head_ref=str(head.get("ref") or ""),
                        base_ref=str(base.get("ref") or ""),
                        author_login=str(user.get("login") or ""),
                        is_fork=bool(
                            head_repo.get("fork")
                            or (
                                head_repo.get("full_name")
                                and base_repo.get("full_name")
                                and head_repo.get("full_name") != base_repo.get("full_name")
                            )
                        ),
                        merged=bool(pr_payload.get("merged", False)),
                        html_url=str(pr_payload.get("html_url") or ""),
                    )
                    reconciled = store.reconcile_project_pull_requests(
                        proj["id"], [pr_meta], mark_missing_closed=False
                    )
                    if action in {"opened", "synchronize", "reopened"} and reconciled["needs_analysis"]:
                        scheduled = store.ensure_pr_analysis_jobs(
                            proj["id"],
                            pr_meta.number,
                            pr_meta.base_sha,
                            pr_meta.head_sha,
                            is_fork=pr_meta.is_fork,
                        )
                        if scheduled and not scheduled.get("reused"):
                            if not scheduled.get("base_reused") and scheduled.get("base_job_id"):
                                active_worker.start(str(scheduled["base_job_id"]))
                            active_worker.start(str(scheduled["candidate_job_id"]))
        return {"status": "accepted"}

    @app.post("/api/github/installations/{installation_id}/policies", status_code=201)
    def update_github_policy(
        installation_id: int, payload: PolicyUpdate, _: None = Depends(require_admin)
    ) -> dict[str, object]:
        installation = store.get_github_installation(installation_id)
        if installation is None or installation["status"] != "active":
            raise HTTPException(status_code=404, detail="Active GitHub installation not found.")
        return store.save_policy(str(installation["id"]), payload.policy, repository_id=payload.repository_id)

    @app.get("/api/github/installations/{installation_id}/repositories")
    def list_github_repositories(installation_id: int) -> list[dict[str, object]]:
        if store.get_github_installation(installation_id) is None:
            raise HTTPException(status_code=404, detail="GitHub installation not found.")
        return store.list_github_repositories(installation_id)

    return app
