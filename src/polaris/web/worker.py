"""Offline static-analysis worker and continuous GitHub synchronization for PostgreSQL queue."""

from __future__ import annotations

import contextlib
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from polaris.cli import build_default_registry
from polaris.core.config import OutputFormat, PolarisConfig
from polaris.core.orchestrator import AnalysisOrchestrator
from polaris.git.analyzer import EMPTY_TREE_REVISION, GitAnalyzer
from polaris.integrations.github.checkout import checkout_github_repository
from polaris.integrations.github.client import GitHubClient
from polaris.integrations.github.http_transport import GitHubApiTransport
from polaris.integrations.github.models import GitHubIntegrationError
from polaris.providers.fake import FakeProvider
from polaris.web.store import WebStore, default_database_url


def run_static_job(store: WebStore, job_id: str | None = None) -> bool:
    job = store.claim_job(job_id)
    if job is None:
        return False
    checkout = None
    analyzed_sha: str | None = job.get("head_sha") or job.get("base_revision")
    try:
        repository_path = Path(job["project_path"])
        if job.get("github_owner"):
            token = os.environ.get("POLARIS_GITHUB_TOKEN", "")
            client = GitHubClient(GitHubApiTransport(), token=token)
            revision = (
                job.get("head_sha")
                or job["base_revision"]
                or client.branch_sha(job["github_owner"], job["github_name"], job["github_default_branch"])
            )
            analyzed_sha = revision
            checkout = checkout_github_repository(job["github_owner"], job["github_name"], revision, token)
            repository_path = checkout.__enter__()
        else:
            with contextlib.suppress(Exception):
                analyzed_sha = analyzed_sha or GitAnalyzer(repository_path).resolve_revision("HEAD")
        effective_base_revision = (
            (job["base_revision"] if job.get("analysis_mode") == "pr" else EMPTY_TREE_REVISION)
            if job.get("github_owner")
            else (job["base_revision"] or EMPTY_TREE_REVISION)
        )
        explicit_max_env = {k: v for k, v in os.environ.items() if k.startswith("POLARIS_MAX_")}
        config = PolarisConfig.from_env_and_args(
            repo_path=repository_path,
            base_revision=effective_base_revision,
            provider="fake",
            output_format=OutputFormat.JSON,
            max_files=500 if (effective_base_revision == EMPTY_TREE_REVISION and "POLARIS_MAX_FILES" not in explicit_max_env) else None,
            max_tokens=2_000_000 if (effective_base_revision == EMPTY_TREE_REVISION and "POLARIS_MAX_TOKENS" not in explicit_max_env) else None,
            environ=explicit_max_env,
        )
        if effective_base_revision == EMPTY_TREE_REVISION and not explicit_max_env:
            config = config.model_copy(
                update={
                    "budget": config.budget.model_copy(
                        update={
                            "max_files": 500,
                            "max_file_bytes": 1_000_000,
                            "max_total_context_bytes": 10_000_000,
                            "max_diff_bytes": 10_000_000,
                            "max_total_tokens": 2_000_000,
                        }
                    )
                }
            )
        provider = FakeProvider()
        provider.preserve_static_on_budget_skip = True
        store.complete(
            job["id"],
            job["claim_token"],
            AnalysisOrchestrator(config, provider, build_default_registry()).run(),
            analyzed_sha=analyzed_sha,
        )
    except Exception as exc:
        store.fail(job["id"], job["claim_token"], str(exc))
    finally:
        if checkout:
            checkout.__exit__(None, None, None)
    return True


class StaticAnalysisWorker:
    def __init__(self, store: WebStore) -> None:
        self.store = store

    def start(self, job_id: str) -> None:
        if self.store.database_url.startswith("sqlite") and os.environ.get("POLARIS_WEB_DATABASE"):
            self.run_inline(job_id)

    def run_inline(self, job_id: str) -> None:
        run_static_job(self.store, job_id)


def synchronize_github_platform(
    store: WebStore,
    client: GitHubClient,
    worker: StaticAnalysisWorker | None = None,
    *,
    sync_prs: bool = True,
    enqueue_jobs: bool = True,
    project_id_filter: str | None = None,
) -> dict[str, Any]:
    """Synchronize accessible GitHub repositories, open PRs, and schedule initial/PR analyses per policy."""
    settings = store.get_sync_settings()
    repositories = client.list_accessible_repositories()
    repo_summary = store.reconcile_github_repositories(
        repositories,
        mark_missing_inaccessible=(project_id_filter is None),
    )

    initial_jobs_enqueued: list[str] = []
    pr_jobs_enqueued: list[str] = []
    prs_discovered_total = 0
    sync_errors: list[str] = []

    projects = store.list_projects()
    for proj in projects:
        if project_id_filter and proj["id"] != project_id_filter:
            continue
        if not proj.get("github_repository_id") or proj.get("sync_status") != "active" or proj.get("is_archived"):
            continue
        owner = proj.get("github_owner")
        name = proj.get("github_name")
        default_branch = proj.get("github_default_branch") or "main"
        if not owner or not name:
            continue

        # 1. Initial analysis scheduling for newly discovered or unanalyzed active repositories
        if (
            enqueue_jobs
            and settings["auto_analyze_initial"]
            and proj.get("auto_analyze", True)
            and (not proj.get("is_private") or settings["allow_private_repo_analysis"])
            and proj.get("analysis_status") == "NOT_ANALYZED"
        ):
            head_sha: str | None = None
            try:
                head_sha = client.branch_sha(str(owner), str(name), str(default_branch))
            except GitHubIntegrationError as exc:
                sync_errors.append(f"{owner}/{name} branch SHA lookup failed: {exc.category.value}")
            job = store.ensure_initial_project_job(proj["id"], head_sha=head_sha)
            if job is not None:
                initial_jobs_enqueued.append(job["id"])
                if worker is not None:
                    worker.start(job["id"])

        # 2. Open Pull Request discovery & SHA-change scheduling
        if sync_prs:
            try:
                open_prs = client.list_pull_requests(str(owner), str(name), state="open")
                pr_reconcile = store.reconcile_project_pull_requests(
                    proj["id"],
                    open_prs,
                    mark_missing_closed=True,
                )
                prs_discovered_total += int(pr_reconcile["discovered_open_count"])
                if enqueue_jobs and settings["auto_analyze_prs"] and proj.get("auto_analyze", True):
                    for candidate_pr in pr_reconcile["needs_analysis"]:
                        scheduled = store.ensure_pr_analysis_jobs(
                            proj["id"],
                            int(candidate_pr["number"]),
                            str(candidate_pr["base_sha"]),
                            str(candidate_pr["head_sha"]),
                            is_fork=bool(candidate_pr.get("is_fork", False)),
                        )
                        if scheduled is not None and not scheduled.get("reused"):
                            pr_jobs_enqueued.append(str(scheduled["candidate_job_id"]))
                            if worker is not None:
                                if not scheduled.get("base_reused") and scheduled.get("base_job_id"):
                                    worker.start(str(scheduled["base_job_id"]))
                                worker.start(str(scheduled["candidate_job_id"]))
            except GitHubIntegrationError as exc:
                sync_errors.append(f"{owner}/{name} PR discovery failed: {exc.category.value}")

    summary = {
        "sync_mode": "pat_polling",
        "discovered_count": repo_summary["discovered_count"],
        "new_count": len(repo_summary["new_project_ids"]),
        "updated_count": len(repo_summary["updated_project_ids"]),
        "renamed_count": len(repo_summary["renamed_project_ids"]),
        "archived_count": len(repo_summary["archived_project_ids"]),
        "inaccessible_count": len(repo_summary["inaccessible_project_ids"]),
        "prs_synced": prs_discovered_total,
        "initial_jobs_enqueued": len(initial_jobs_enqueued),
        "pr_jobs_enqueued": len(pr_jobs_enqueued),
        "jobs_enqueued": len(initial_jobs_enqueued) + len(pr_jobs_enqueued),
        "errors": sync_errors,
    }
    store.record_sync_outcome(
        "completed" if not sync_errors else "completed_with_warnings",
        summary=summary,
        error="; ".join(sync_errors) if sync_errors else None,
    )
    return summary


def run_worker() -> None:
    store = WebStore(default_database_url(), initialize=False)
    store.recover_interrupted_jobs(int(os.environ.get("POLARIS_JOB_RECOVERY_SECONDS", "600")))
    last_sync_check = 0.0
    while True:
        now = time.time()
        heartbeat_path = Path(tempfile.gettempdir()) / "polaris-worker-heartbeat"
        with heartbeat_path.open("w", encoding="utf-8") as heartbeat:
            heartbeat.write(str(now))

        token = os.environ.get("POLARIS_GITHUB_TOKEN", "").strip()
        auto_sync_enabled = os.environ.get("POLARIS_AUTO_SYNC_ENABLED", "false").lower() == "true"
        if token and auto_sync_enabled and (now - last_sync_check) >= 15.0:
            last_sync_check = now
            try:
                settings = store.get_sync_settings()
                interval = max(30, int(settings.get("sync_interval_seconds", 300)))
                should_sync = False
                if settings.get("auto_discover_repos", True):
                    if not settings.get("last_sync_at"):
                        should_sync = True
                    else:
                        from datetime import datetime

                        last_dt = datetime.fromisoformat(str(settings["last_sync_at"]))
                        elapsed = now - last_dt.timestamp()
                        if elapsed >= interval:
                            should_sync = True
                if should_sync:
                    client = GitHubClient(GitHubApiTransport(), token=token)
                    synchronize_github_platform(store, client, worker=None)
            except Exception as exc:
                store.record_sync_outcome("failed", error=str(exc))

        if not run_static_job(store):
            time.sleep(float(os.environ.get("POLARIS_WORKER_POLL_SECONDS", "1")))
