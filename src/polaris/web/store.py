"""PostgreSQL persistence for Polaris (POLARIS) dashboard jobs, quality ratings, and PR comparisons."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
    text,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from polaris.core.models import AnalysisReport
from polaris.integrations.github.models import PullRequestMetadata
from polaris.quality import (
    QualityGateConfig,
    addressed_gate_conditions,
    build_github_check_contract,
    compare_pull_request,
    evaluate_quality,
    evaluate_quality_gate,
    is_vulnerability_finding,
)

DEFAULT_DATABASE_URL = "postgresql+psycopg://polaris:polaris@db:5432/polaris"


def default_database_url() -> str:
    if os.environ.get("POLARIS_DATABASE_URL"):
        return os.environ["POLARIS_DATABASE_URL"]
    if os.environ.get("POLARIS_WEB_DATABASE"):
        return f"sqlite:///{os.environ['POLARIS_WEB_DATABASE']}"
    return DEFAULT_DATABASE_URL


class Base(DeclarativeBase):
    pass


class ProjectRecord(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    github_repository_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    github_owner: Mapped[str | None] = mapped_column(String(255))
    github_name: Mapped[str | None] = mapped_column(String(255))
    github_default_branch: Mapped[str | None] = mapped_column(String(255))
    github_language: Mapped[str | None] = mapped_column(String(64))
    github_is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    github_is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    github_is_fork: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_status: Mapped[str] = mapped_column(String(32), default="active")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_analyzed_sha: Mapped[str | None] = mapped_column(String(64))
    last_successful_analysis_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_analyze: Mapped[bool] = mapped_column(Boolean, default=True)
    gate_config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    jobs: Mapped[list[JobRecord]] = relationship(back_populates="project", cascade="all, delete-orphan")
    pull_requests: Mapped[list[PullRequestRecord]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class JobRecord(Base):
    __tablename__ = "analysis_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    base_revision: Mapped[str | None] = mapped_column(String(200))
    analysis_mode: Mapped[str | None] = mapped_column(String(20), default="project")
    baseline_job_id: Mapped[str | None] = mapped_column(String(36))
    pull_request_number: Mapped[int | None] = mapped_column(Integer)
    head_sha: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[str | None] = mapped_column(String(36))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    quality_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    gate_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    comparison_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    project: Mapped[ProjectRecord] = relationship(back_populates="jobs")
    findings: Mapped[list[FindingRecord]] = relationship(back_populates="job", cascade="all, delete-orphan")


class FindingRecord(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("analysis_jobs.id"), primary_key=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    job: Mapped[JobRecord] = relationship(back_populates="findings")


class PullRequestRecord(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_pull_requests_project_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    author_login: Mapped[str | None] = mapped_column(String(255))
    head_ref: Mapped[str | None] = mapped_column(String(255))
    base_ref: Mapped[str | None] = mapped_column(String(255))
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    is_fork: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    merged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    html_url: Mapped[str | None] = mapped_column(Text)
    latest_base_job_id: Mapped[str | None] = mapped_column(String(36))
    latest_candidate_job_id: Mapped[str | None] = mapped_column(String(36))
    last_analyzed_head_sha: Mapped[str | None] = mapped_column(String(64))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    project: Mapped[ProjectRecord] = relationship(back_populates="pull_requests")


class SyncSettingsRecord(Base):
    __tablename__ = "sync_settings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    auto_discover_repos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_analyze_initial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_analyze_prs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_private_repo_analysis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_fork_pr_analysis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sync_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(64))
    last_sync_error: Mapped[str | None] = mapped_column(Text)
    last_sync_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class GitHubInstallationRecord(Base):
    __tablename__ = "github_installations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    github_installation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    github_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    account_login: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    repository_selection: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class GitHubRepositoryRecord(Base):
    __tablename__ = "github_repositories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    installation_id: Mapped[str] = mapped_column(ForeignKey("github_installations.id"), nullable=False)
    github_repository_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_login: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class GitHubWebhookDeliveryRecord(Base):
    __tablename__ = "github_webhook_deliveries"
    delivery_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    installation_id: Mapped[str | None] = mapped_column(String(36))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class PolarisPolicyRecord(Base):
    __tablename__ = "polaris_policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    installation_id: Mapped[str] = mapped_column(ForeignKey("github_installations.id"), nullable=False)
    repository_id: Mapped[str | None] = mapped_column(ForeignKey("github_repositories.id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)


class PolarisAuditLogRecord(Base):
    __tablename__ = "polaris_audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    installation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


def _build_github_blob_url(
    owner: str | None,
    repo: str | None,
    revision: str | None,
    file_path: str | None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str | None:
    if not owner or not repo or not revision or not file_path:
        return None
    clean_path = str(file_path).lstrip("/")
    anchor = ""
    if isinstance(start_line, int) and start_line >= 1:
        anchor = f"#L{start_line}"
        if isinstance(end_line, int) and end_line > start_line:
            anchor = f"#L{start_line}-L{end_line}"
    return f"https://github.com/{owner}/{repo}/blob/{revision}/{clean_path}{anchor}"


def _derive_safe_code_example(finding_dict: dict[str, Any]) -> str | None:
    """Provide a deterministic code example only when directly supported by actual evidence."""
    evidence = str(finding_dict.get("evidence") or "").strip()
    title = str(finding_dict.get("title") or "").upper()
    if not evidence:
        return None
    if "[DET-SQL-INTERPOLATION]" in title and ("execute(" in evidence or "SELECT" in evidence.upper()):
        return "cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))"
    if "[DET-DIV-ZERO]" in title and "/ 0" in evidence:
        lhs = evidence.split("/ 0")[0].strip()
        return f"{lhs} / divisor if divisor != 0 else 0"
    if "[DET-MUTABLE-DEFAULT]" in title and "=[]" in evidence.replace(" ", ""):
        return evidence.replace("=[]", "=None").replace("= []", "= None")
    if "[DET-SUBPROCESS-SHELL]" in title and "shell=True" in evidence:
        return evidence.replace("shell=True", "shell=False")
    if "[DET-YAML-UNSAFE-LOAD]" in title and "yaml.load(" in evidence:
        return evidence.replace("yaml.load(", "yaml.safe_load(")
    if "[DET-BROAD-EXCEPT-PASS]" in title:
        return "except SpecificError as exc:\n    logger.warning('Operation failed: %s', exc)\n    raise"
    return None


class WebStore:
    """Transaction-safe store shared by API and worker services."""

    def __init__(self, database_url: str | None = None, *, initialize: bool = False) -> None:
        self.database_url = database_url or default_database_url()
        args = {"check_same_thread": False} if self.database_url.startswith("sqlite") else {}
        self.engine = create_engine(self.database_url, pool_pre_ping=True, connect_args=args)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        if initialize or self.database_url.startswith("sqlite"):
            Base.metadata.create_all(self.engine)

    @staticmethod
    def _gate_config(item: ProjectRecord) -> QualityGateConfig:
        if item.gate_config_json:
            return QualityGateConfig.model_validate(item.gate_config_json)
        return QualityGateConfig()

    def _enrich_finding_dict(
        self,
        raw: dict[str, Any],
        *,
        owner: str | None = None,
        repo: str | None = None,
        revision: str | None = None,
        gate_json: dict[str, Any] | None = None,
        classification: str = "project",
    ) -> dict[str, Any]:
        enriched = dict(raw)
        is_vuln = is_vulnerability_finding(enriched)
        lr = enriched.get("line_range") if isinstance(enriched.get("line_range"), dict) else {}
        start_line = lr.get("start_line")
        end_line = lr.get("end_line")
        enriched["is_vulnerability"] = is_vuln
        enriched["finding_type"] = "vulnerability" if is_vuln else "bug"
        enriched["addressed_gate_conditions"] = addressed_gate_conditions(
            enriched, gate_json, classification=classification
        )
        enriched["github_blob_url"] = _build_github_blob_url(
            owner, repo, revision, enriched.get("file_path"), start_line, end_line
        )
        safe_example = _derive_safe_code_example(enriched)
        if safe_example:
            enriched["safe_code_example"] = safe_example
        return enriched

    def _project(self, item: ProjectRecord) -> dict[str, Any]:
        gate_cfg = self._gate_config(item).model_dump(mode="json")
        all_jobs = sorted(item.jobs, key=lambda j: j.created_at, reverse=True)
        project_jobs = [
            j for j in all_jobs if (j.analysis_mode or "project") == "project" and j.pull_request_number is None
        ]
        if not project_jobs:
            project_jobs = [j for j in all_jobs if (j.analysis_mode or "project") == "project"]

        latest = project_jobs[0] if project_jobs else None
        latest_completed = next((j for j in project_jobs if j.status == "completed"), None)
        latest_quality = latest.quality_json if latest and isinstance(latest.quality_json, dict) else None
        latest_gate = latest.gate_json if latest and isinstance(latest.gate_json, dict) else None

        analysis_status = latest.status if latest else "NOT_ANALYZED"
        latest_grade = latest_quality.get("grade") if latest_quality else ("NOT_RATED" if latest else None)
        latest_score = latest_quality.get("score") if latest_quality else None
        latest_gate_status = latest_gate.get("status") if latest_gate else None

        # Never fabricate metrics: distinguish NOT_ANALYZED / failed / queued from 0 findings
        vulnerability_count: int | None = None
        bug_count: int | None = None
        findings_count: int | None = None
        severity_counts: dict[str, int] | None = None

        if latest is not None and analysis_status in {"completed", "incomplete"}:
            raw_findings = (
                latest.report_json.get("findings", [])
                if isinstance(latest.report_json, dict) and isinstance(latest.report_json.get("findings"), list)
                else [f.payload_json for f in latest.findings]
            )
            findings_count = len(raw_findings)
            v_cnt = sum(1 for f in raw_findings if isinstance(f, dict) and is_vulnerability_finding(f))
            vulnerability_count = v_cnt
            bug_count = max(0, findings_count - v_cnt)
            sev_map = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
            for f in raw_findings:
                if isinstance(f, dict):
                    s = str(f.get("severity") or "info").lower()
                    if s in sev_map:
                        sev_map[s] += 1
            severity_counts = sev_map

        last_sha = (
            item.last_analyzed_sha
            or (latest_completed.head_sha or latest_completed.base_revision if latest_completed else None)
            or (latest.head_sha or latest.base_revision if latest else None)
        )
        last_success_at = (
            item.last_successful_analysis_at
            or (latest_completed.finished_at if latest_completed else None)
        )
        open_prs = sum(1 for pr in item.pull_requests if pr.state == "open")

        return {
            "id": item.id,
            "name": item.name,
            "path": item.path,
            "github_repository_id": item.github_repository_id,
            "github_owner": item.github_owner,
            "github_name": item.github_name,
            "github_default_branch": item.github_default_branch,
            "owner": item.github_owner or "local",
            "repository_name": item.github_name or item.name,
            "full_name": f"{item.github_owner}/{item.github_name}"
            if item.github_owner and item.github_name
            else item.name,
            "language": item.github_language,
            "default_branch": item.github_default_branch or "main",
            "is_private": bool(item.github_is_private),
            "is_archived": bool(item.github_is_archived),
            "is_fork": bool(item.github_is_fork),
            "sync_status": item.sync_status or ("active" if item.github_repository_id else "local"),
            "auto_analyze": True if item.auto_analyze is None else bool(item.auto_analyze),
            "last_synced_at": item.last_synced_at.isoformat() if item.last_synced_at else None,
            "last_analyzed_sha": last_sha,
            "last_successful_analysis_at": last_success_at.isoformat() if last_success_at else None,
            "created_at": item.created_at.isoformat(),
            "gate_config": gate_cfg,
            "analysis_count": len(all_jobs),
            "project_analysis_count": len(project_jobs),
            "open_pr_count": open_prs,
            "latest_job_id": latest.id if latest else None,
            "latest_status": latest.status if latest else None,
            "analysis_status": analysis_status,
            "latest_grade": latest_grade,
            "latest_score": latest_score,
            "latest_gate_status": latest_gate_status,
            "vulnerability_count": vulnerability_count,
            "bug_count": bug_count,
            "findings_count": findings_count,
            "severity_counts": severity_counts,
        }

    def _compute_job_quality_bundle(
        self,
        item: JobRecord,
        report: AnalysisReport | None,
        gate_cfg: QualityGateConfig,
        baseline_item: JobRecord | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
        evaluation = evaluate_quality(report, job_status=item.status, job_error=item.error)
        if (item.analysis_mode == "pr" or baseline_item is not None) and baseline_item is not None:
            base_report = (
                AnalysisReport.model_validate(baseline_item.report_json) if baseline_item.report_json else None
            )
            comparison = compare_pull_request(
                base_report=base_report,
                pr_report=report,
                base_job_status=baseline_item.status,
                base_job_error=baseline_item.error,
                pr_job_status=item.status,
                pr_job_error=item.error,
                gate_config=gate_cfg,
                base_revision=baseline_item.base_revision,
                head_revision=item.head_sha or item.base_revision,
            )
            gh_check = build_github_check_contract(
                comparison,
                head_sha=item.head_sha or item.base_revision or "HEAD",
            )
            comp_payload = comparison.model_dump(mode="json")
            comp_payload["github_check_contract"] = gh_check.model_dump(mode="json")
            return (
                comparison.pr_evaluation.model_dump(mode="json"),
                comparison.quality_gate.model_dump(mode="json"),
                comp_payload,
            )

        gate = evaluate_quality_gate(evaluation, gate_cfg)
        return evaluation.model_dump(mode="json"), gate.model_dump(mode="json"), None

    def _job(self, item: JobRecord, details: bool = True) -> dict[str, Any]:
        report_obj: AnalysisReport | None = None
        if item.report_json:
            try:
                report_obj = AnalysisReport.model_validate(item.report_json)
            except Exception:
                report_obj = None

        quality_json = item.quality_json
        gate_json = item.gate_json
        comparison_json = item.comparison_json

        if quality_json is None or gate_json is None:
            gate_cfg = self._gate_config(item.project)
            q_dump, g_dump, c_dump = self._compute_job_quality_bundle(item, report_obj, gate_cfg)
            quality_json = quality_json or q_dump
            gate_json = gate_json or g_dump
            comparison_json = comparison_json or c_dump

        warnings_list = item.report_json.get("warnings", []) if isinstance(item.report_json, dict) else []
        files_analyzed = item.report_json.get("files_analyzed", []) if isinstance(item.report_json, dict) else []
        revision = (
            item.head_sha
            or item.base_revision
            or item.project.last_analyzed_sha
            or item.project.github_default_branch
            or "main"
        )

        raw_findings_list = (
            [finding.payload_json for finding in item.findings]
            if details
            else (item.report_json.get("findings", []) if isinstance(item.report_json, dict) else [])
        )
        vuln_count = sum(1 for f in raw_findings_list if isinstance(f, dict) and is_vulnerability_finding(f))

        value: dict[str, Any] = {
            "id": item.id,
            "project_id": item.project_id,
            "project_name": item.project.name,
            "project_path": item.project.path,
            "github_owner": item.project.github_owner,
            "github_name": item.project.github_name,
            "github_default_branch": item.project.github_default_branch,
            "base_revision": item.base_revision,
            "analysis_mode": item.analysis_mode or "project",
            "baseline_job_id": item.baseline_job_id,
            "pull_request_number": item.pull_request_number,
            "head_sha": item.head_sha,
            "commit_sha": item.head_sha or item.base_revision or item.project.last_analyzed_sha,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
            "finished_at": item.finished_at.isoformat() if item.finished_at else None,
            "error": item.error,
            "report_json": item.report_json,
            "quality": quality_json,
            "quality_gate": gate_json,
            "comparison": comparison_json,
            "warnings": warnings_list,
            "files_analyzed": files_analyzed,
            "findings_count": len(raw_findings_list),
            "vulnerability_count": vuln_count,
            "bug_count": max(0, len(raw_findings_list) - vuln_count),
        }
        if details:
            value["findings"] = [
                self._enrich_finding_dict(
                    finding.payload_json,
                    owner=item.project.github_owner,
                    repo=item.project.github_name,
                    revision=revision,
                    gate_json=gate_json if isinstance(gate_json, dict) else None,
                    classification="new" if item.analysis_mode == "pr" else "project",
                )
                for finding in item.findings
            ]
        return value

    def get_sync_settings(self) -> dict[str, Any]:
        with self.sessions.begin() as session:
            item = session.scalars(select(SyncSettingsRecord).limit(1)).first()
            if item is None:
                item = SyncSettingsRecord(
                    id="default",
                    auto_discover_repos=True,
                    auto_analyze_initial=True,
                    auto_analyze_prs=True,
                    allow_private_repo_analysis=False,
                    allow_fork_pr_analysis=False,
                    sync_interval_seconds=300,
                )
                session.add(item)
            return {
                "id": item.id,
                "auto_discover_repos": True if item.auto_discover_repos is None else bool(item.auto_discover_repos),
                "auto_analyze_initial": True if item.auto_analyze_initial is None else bool(item.auto_analyze_initial),
                "auto_analyze_prs": True if item.auto_analyze_prs is None else bool(item.auto_analyze_prs),
                "allow_private_repo_analysis": bool(item.allow_private_repo_analysis),
                "allow_fork_pr_analysis": bool(item.allow_fork_pr_analysis),
                "sync_interval_seconds": int(item.sync_interval_seconds or 300),
                "last_sync_at": item.last_sync_at.isoformat() if item.last_sync_at else None,
                "last_sync_status": item.last_sync_status,
                "last_sync_error": item.last_sync_error,
                "last_sync_summary": item.last_sync_summary_json,
            }

    def update_sync_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.sessions.begin() as session:
            item = session.scalars(select(SyncSettingsRecord).limit(1)).first()
            if item is None:
                item = SyncSettingsRecord(
                    id="default",
                    auto_discover_repos=True,
                    auto_analyze_initial=True,
                    auto_analyze_prs=True,
                    allow_private_repo_analysis=False,
                    allow_fork_pr_analysis=False,
                    sync_interval_seconds=300,
                )
                session.add(item)
            for field in (
                "auto_discover_repos",
                "auto_analyze_initial",
                "auto_analyze_prs",
                "allow_private_repo_analysis",
                "allow_fork_pr_analysis",
            ):
                if field in payload and isinstance(payload[field], bool):
                    setattr(item, field, payload[field])
            if "sync_interval_seconds" in payload and isinstance(payload["sync_interval_seconds"], int):
                item.sync_interval_seconds = max(30, min(86400, payload["sync_interval_seconds"]))
        return self.get_sync_settings()

    def record_sync_outcome(
        self,
        status: str,
        summary: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        with self.sessions.begin() as session:
            item = session.scalars(select(SyncSettingsRecord).limit(1)).first()
            if item is None:
                item = SyncSettingsRecord(
                    id="default",
                    auto_discover_repos=True,
                    auto_analyze_initial=True,
                    auto_analyze_prs=True,
                    allow_private_repo_analysis=False,
                    allow_fork_pr_analysis=False,
                    sync_interval_seconds=300,
                )
                session.add(item)
            item.last_sync_at = datetime.now(UTC)
            item.last_sync_status = status
            item.last_sync_error = error[:1000] if error else None
            if summary is not None:
                item.last_sync_summary_json = summary
        return self.get_sync_settings()

    def create_project(
        self,
        name: str,
        path: str,
        gate_config: QualityGateConfig | None = None,
    ) -> dict[str, Any]:
        cfg = (gate_config or QualityGateConfig()).model_dump(mode="json")
        item = ProjectRecord(
            id=str(uuid.uuid4()),
            name=name,
            path=path,
            sync_status="local",
            gate_config_json=cfg,
        )
        with self.sessions.begin() as session:
            session.add(item)
        return self.get_project(item.id) or {"id": item.id, "name": name, "path": path}

    def import_github_project(self, repository: dict[str, Any]) -> dict[str, Any]:
        owner = repository.get("owner") if isinstance(repository.get("owner"), dict) else {}
        repo_id, name, full_name, owner_login = (
            repository.get("id"),
            repository.get("name"),
            repository.get("full_name"),
            owner.get("login") or repository.get("owner") if isinstance(repository.get("owner"), str) else owner.get("login"),
        )
        if not isinstance(repo_id, int) or not all(isinstance(value, str) for value in (name, full_name, owner_login)):
            raise ValueError("GitHub repository response is invalid.")
        is_archived = bool(repository.get("archived", False))
        is_private = bool(repository.get("private", False))
        is_fork = bool(repository.get("fork", False))
        language = repository.get("language") if isinstance(repository.get("language"), str) else None
        default_branch = (
            repository.get("default_branch") if isinstance(repository.get("default_branch"), str) else "main"
        )
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            existing = session.scalar(select(ProjectRecord).where(ProjectRecord.github_repository_id == repo_id))
            if existing is not None:
                existing.name = full_name
                existing.path = f"github://{full_name}"
                existing.github_owner = owner_login
                existing.github_name = name
                existing.github_default_branch = default_branch
                existing.github_language = language
                existing.github_is_private = is_private
                existing.github_is_archived = is_archived
                existing.github_is_fork = is_fork
                existing.sync_status = "archived" if is_archived else "active"
                existing.last_synced_at = now
                proj_id = existing.id
            else:
                item = ProjectRecord(
                    id=str(uuid.uuid4()),
                    name=full_name,
                    path=f"github://{full_name}",
                    github_repository_id=repo_id,
                    github_owner=owner_login,
                    github_name=name,
                    github_default_branch=default_branch,
                    github_language=language,
                    github_is_private=is_private,
                    github_is_archived=is_archived,
                    github_is_fork=is_fork,
                    sync_status="archived" if is_archived else "active",
                    last_synced_at=now,
                )
                session.add(item)
                proj_id = item.id
        return self.get_project(proj_id) or {"id": proj_id}

    def reconcile_github_repositories(
        self,
        repositories: list[dict[str, Any]],
        *,
        mark_missing_inaccessible: bool = True,
    ) -> dict[str, Any]:
        """Synchronize discovered GitHub repositories idempotently using github_repository_id."""
        now = datetime.now(UTC)
        seen_repo_ids: set[int] = set()
        new_project_ids: list[str] = []
        updated_project_ids: list[str] = []
        renamed_project_ids: list[str] = []
        archived_project_ids: list[str] = []
        inaccessible_project_ids: list[str] = []

        with self.sessions.begin() as session:
            for repository in repositories:
                owner = repository.get("owner") if isinstance(repository.get("owner"), dict) else {}
                owner_login = (
                    owner.get("login")
                    if isinstance(owner.get("login"), str)
                    else (repository.get("owner") if isinstance(repository.get("owner"), str) else None)
                )
                repo_id = repository.get("id")
                name = repository.get("name")
                full_name = repository.get("full_name")
                if not isinstance(repo_id, int) or not all(
                    isinstance(v, str) and v.strip() for v in (name, full_name, owner_login)
                ):
                    continue
                seen_repo_ids.add(repo_id)
                is_archived = bool(repository.get("archived", False))
                is_private = bool(repository.get("private", False))
                is_fork = bool(repository.get("fork", False))
                language = repository.get("language") if isinstance(repository.get("language"), str) else None
                default_branch = (
                    repository.get("default_branch") if isinstance(repository.get("default_branch"), str) else "main"
                )
                target_sync_status = "archived" if is_archived else "active"

                existing = session.scalar(select(ProjectRecord).where(ProjectRecord.github_repository_id == repo_id))
                if existing is None:
                    created = ProjectRecord(
                        id=str(uuid.uuid4()),
                        name=full_name,
                        path=f"github://{full_name}",
                        github_repository_id=repo_id,
                        github_owner=owner_login,
                        github_name=name,
                        github_default_branch=default_branch,
                        github_language=language,
                        github_is_private=is_private,
                        github_is_archived=is_archived,
                        github_is_fork=is_fork,
                        sync_status=target_sync_status,
                        last_synced_at=now,
                        auto_analyze=True,
                    )
                    session.add(created)
                    new_project_ids.append(created.id)
                    if is_archived:
                        archived_project_ids.append(created.id)
                else:
                    was_renamed = existing.name != full_name or existing.github_name != name or existing.github_owner != owner_login
                    existing.name = full_name
                    existing.path = f"github://{full_name}"
                    existing.github_owner = owner_login
                    existing.github_name = name
                    existing.github_default_branch = default_branch
                    if language is not None:
                        existing.github_language = language
                    existing.github_is_private = is_private
                    existing.github_is_archived = is_archived
                    existing.github_is_fork = is_fork
                    existing.sync_status = target_sync_status
                    existing.last_synced_at = now
                    updated_project_ids.append(existing.id)
                    if was_renamed:
                        renamed_project_ids.append(existing.id)
                    if is_archived:
                        archived_project_ids.append(existing.id)

            if mark_missing_inaccessible:
                for item in session.scalars(
                    select(ProjectRecord).where(ProjectRecord.github_repository_id.is_not(None))
                ):
                    if item.github_repository_id not in seen_repo_ids:
                        item.sync_status = "inaccessible"
                        item.last_synced_at = now
                        inaccessible_project_ids.append(item.id)

        return {
            "discovered_count": len(seen_repo_ids),
            "new_project_ids": new_project_ids,
            "updated_project_ids": updated_project_ids,
            "renamed_project_ids": renamed_project_ids,
            "archived_project_ids": archived_project_ids,
            "inaccessible_project_ids": inaccessible_project_ids,
        }

    def ensure_initial_project_job(
        self,
        project_id: str,
        head_sha: str | None = None,
        *,
        force: bool = False,
    ) -> dict[str, Any] | None:
        """Idempotently schedule an initial/branch project analysis when eligible under policy."""
        settings = self.get_sync_settings()
        with self.sessions.begin() as session:
            project = session.get(ProjectRecord, project_id)
            if project is None:
                return None
            if not force:
                if not settings["auto_analyze_initial"] or not project.auto_analyze:
                    return None
                if project.sync_status in {"archived", "inaccessible", "deleted"} or project.github_is_archived:
                    return None
                if project.github_is_private and not settings["allow_private_repo_analysis"]:
                    return None

            existing_jobs = list(
                session.scalars(
                    select(JobRecord)
                    .where(
                        JobRecord.project_id == project_id,
                        JobRecord.analysis_mode == "project",
                        JobRecord.pull_request_number.is_(None),
                    )
                    .order_by(JobRecord.created_at.desc())
                )
            )
            for job in existing_jobs:
                if (
                    job.status in {"queued", "running"}
                    and (head_sha is None or (job.head_sha or job.base_revision) in {None, head_sha})
                ):
                    return None
                if (
                    job.status in {"completed", "incomplete"}
                    and (head_sha is None or (job.head_sha or job.base_revision) == head_sha)
                ):
                    return None

        return self.create_job(
            project_id,
            base_revision=head_sha,
            analysis_mode="project",
            head_sha=head_sha,
        )

    def reconcile_project_pull_requests(
        self,
        project_id: str,
        prs: list[PullRequestMetadata],
        *,
        mark_missing_closed: bool = True,
    ) -> dict[str, Any]:
        """Persist discovered PR metadata and detect newly discovered or SHA-updated PRs."""
        now = datetime.now(UTC)
        seen_numbers: set[int] = set()
        needs_analysis: list[dict[str, Any]] = []
        updated_numbers: list[int] = []
        closed_numbers: list[int] = []

        with self.sessions.begin() as session:
            project = session.get(ProjectRecord, project_id)
            if project is None:
                raise ValueError("Project not found.")
            for pr in prs:
                seen_numbers.add(pr.number)
                normalized_state = "merged" if pr.merged else pr.state.lower()
                item = session.scalar(
                    select(PullRequestRecord).where(
                        PullRequestRecord.project_id == project_id,
                        PullRequestRecord.number == pr.number,
                    )
                )
                if item is None:
                    item = PullRequestRecord(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        number=pr.number,
                        title=pr.title or f"PR #{pr.number}",
                        state=normalized_state,
                        author_login=pr.author_login,
                        head_ref=pr.head_ref,
                        base_ref=pr.base_ref,
                        head_sha=pr.head_sha,
                        base_sha=pr.base_sha,
                        is_fork=bool(pr.is_fork),
                        merged=bool(pr.merged),
                        html_url=pr.html_url,
                        last_synced_at=now,
                    )
                    session.add(item)
                    if normalized_state == "open":
                        needs_analysis.append(
                            {
                                "pr_id": item.id,
                                "number": pr.number,
                                "base_sha": pr.base_sha,
                                "head_sha": pr.head_sha,
                                "is_fork": bool(pr.is_fork),
                                "reason": "newly_discovered",
                            }
                        )
                else:
                    sha_changed = item.head_sha != pr.head_sha or item.base_sha != pr.base_sha
                    not_yet_analyzed = item.last_analyzed_head_sha != pr.head_sha or item.latest_candidate_job_id is None
                    item.title = pr.title or item.title
                    item.state = normalized_state
                    item.author_login = pr.author_login or item.author_login
                    item.head_ref = pr.head_ref or item.head_ref
                    item.base_ref = pr.base_ref or item.base_ref
                    item.head_sha = pr.head_sha
                    item.base_sha = pr.base_sha
                    item.is_fork = bool(pr.is_fork)
                    item.merged = bool(pr.merged)
                    item.html_url = pr.html_url or item.html_url
                    item.last_synced_at = now
                    updated_numbers.append(pr.number)
                    if normalized_state == "open" and (sha_changed or not_yet_analyzed):
                        needs_analysis.append(
                            {
                                "pr_id": item.id,
                                "number": pr.number,
                                "base_sha": pr.base_sha,
                                "head_sha": pr.head_sha,
                                "is_fork": bool(pr.is_fork),
                                "reason": "sha_changed" if sha_changed else "unanalyzed",
                            }
                        )

            if mark_missing_closed:
                for existing_pr in session.scalars(
                    select(PullRequestRecord).where(
                        PullRequestRecord.project_id == project_id,
                        PullRequestRecord.state == "open",
                    )
                ):
                    if existing_pr.number not in seen_numbers:
                        existing_pr.state = "closed"
                        existing_pr.last_synced_at = now
                        closed_numbers.append(existing_pr.number)

        return {
            "project_id": project_id,
            "discovered_open_count": len(seen_numbers),
            "needs_analysis": needs_analysis,
            "updated_numbers": updated_numbers,
            "closed_numbers": closed_numbers,
        }

    def ensure_pr_analysis_jobs(
        self,
        project_id: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        *,
        is_fork: bool = False,
        force: bool = False,
    ) -> dict[str, Any] | None:
        """Idempotently schedule or reuse baseline + candidate jobs for a specific PR and (base_sha, head_sha)."""
        settings = self.get_sync_settings()
        with self.sessions.begin() as session:
            project = session.get(ProjectRecord, project_id)
            if project is None:
                return None
            if not force:
                if not settings["auto_analyze_prs"] or not project.auto_analyze:
                    return None
                if project.sync_status in {"archived", "inaccessible", "deleted"} or project.github_is_archived:
                    return None
                if project.github_is_private and not settings["allow_private_repo_analysis"]:
                    return None
                if is_fork and not settings["allow_fork_pr_analysis"]:
                    return None

            # Check if a candidate PR job already exists for this exact (project_id, pr_number, base_sha, head_sha)
            existing_cand = session.scalar(
                select(JobRecord)
                .where(
                    JobRecord.project_id == project_id,
                    JobRecord.analysis_mode == "pr",
                    JobRecord.pull_request_number == pr_number,
                    JobRecord.base_revision == base_sha,
                    JobRecord.head_sha == head_sha,
                )
                .order_by(JobRecord.created_at.desc())
            )
            if existing_cand is not None and (existing_cand.status != "failed" or not force):
                pr_rec = session.scalar(
                    select(PullRequestRecord).where(
                        PullRequestRecord.project_id == project_id,
                        PullRequestRecord.number == pr_number,
                    )
                )
                if pr_rec is not None:
                    pr_rec.latest_base_job_id = existing_cand.baseline_job_id
                    pr_rec.latest_candidate_job_id = existing_cand.id
                    pr_rec.last_analyzed_head_sha = head_sha
                return {
                    "base_job_id": existing_cand.baseline_job_id,
                    "candidate_job_id": existing_cand.id,
                    "base_sha": base_sha,
                    "head_sha": head_sha,
                    "number": pr_number,
                    "reused": True,
                    "base_reused": True,
                }

            # Look for an existing reusable baseline job for base_sha
            existing_base = session.scalar(
                select(JobRecord)
                .where(
                    JobRecord.project_id == project_id,
                    JobRecord.analysis_mode == "project",
                    JobRecord.base_revision == base_sha,
                    JobRecord.status.in_(["queued", "running", "completed"]),
                )
                .order_by(JobRecord.created_at.desc())
            )
            base_reused = existing_base is not None

        if existing_base is not None:
            base_job_id = existing_base.id
        else:
            base_job = self.create_job(project_id, base_sha, analysis_mode="project", head_sha=base_sha)
            base_job_id = base_job["id"]

        cand_job = self.create_job(
            project_id,
            base_sha,
            analysis_mode="pr",
            baseline_job_id=base_job_id,
            pull_request_number=pr_number,
            head_sha=head_sha,
        )

        with self.sessions.begin() as session:
            pr_rec = session.scalar(
                select(PullRequestRecord).where(
                    PullRequestRecord.project_id == project_id,
                    PullRequestRecord.number == pr_number,
                )
            )
            if pr_rec is not None:
                pr_rec.latest_base_job_id = base_job_id
                pr_rec.latest_candidate_job_id = cand_job["id"]
                pr_rec.last_analyzed_head_sha = head_sha

        return {
            "base_job_id": base_job_id,
            "candidate_job_id": cand_job["id"],
            "base_sha": base_sha,
            "head_sha": head_sha,
            "number": pr_number,
            "reused": False,
            "base_reused": base_reused,
        }

    def _pull_request_dict(
        self,
        item: PullRequestRecord,
        session: Any,
        *,
        details: bool = False,
    ) -> dict[str, Any]:
        project = item.project
        cand_job = session.get(JobRecord, item.latest_candidate_job_id) if item.latest_candidate_job_id else None
        base_job = session.get(JobRecord, item.latest_base_job_id) if item.latest_base_job_id else None
        if cand_job is None:
            cand_job = session.scalar(
                select(JobRecord)
                .where(
                    JobRecord.project_id == item.project_id,
                    JobRecord.analysis_mode == "pr",
                    JobRecord.pull_request_number == item.number,
                )
                .order_by(JobRecord.created_at.desc())
            )
            if cand_job and cand_job.baseline_job_id and base_job is None:
                base_job = session.get(JobRecord, cand_job.baseline_job_id)

        comp_json = cand_job.comparison_json if cand_job and isinstance(cand_job.comparison_json, dict) else None
        qual_json = cand_job.quality_json if cand_job and isinstance(cand_job.quality_json, dict) else None
        gate_json = cand_job.gate_json if cand_job and isinstance(cand_job.gate_json, dict) else None
        base_qual_json = (
            comp_json.get("base_evaluation")
            if comp_json and isinstance(comp_json.get("base_evaluation"), dict)
            else (base_job.quality_json if base_job and isinstance(base_job.quality_json, dict) else None)
        )

        analysis_status = cand_job.status if cand_job else "NOT_ANALYZED"
        stale_sha = bool(cand_job and cand_job.head_sha and cand_job.head_sha != item.head_sha)

        base_grade = base_qual_json.get("grade") if isinstance(base_qual_json, dict) else "NOT_RATED"
        base_score = base_qual_json.get("score") if isinstance(base_qual_json, dict) else None
        head_grade = qual_json.get("grade") if isinstance(qual_json, dict) else "NOT_RATED"
        head_score = qual_json.get("score") if isinstance(qual_json, dict) else None
        grade_delta = (
            comp_json.get("grade_delta")
            if comp_json and isinstance(comp_json.get("grade_delta"), str)
            else f"{base_grade} -> {head_grade}"
        )
        score_delta = comp_json.get("score_delta") if comp_json else None
        gate_status = gate_json.get("status") if isinstance(gate_json, dict) else "INCONCLUSIVE"

        new_findings_raw = comp_json.get("new_findings", []) if comp_json else []
        new_crit = sum(
            1
            for nf in new_findings_raw
            if isinstance(nf, dict)
            and isinstance(nf.get("finding"), dict)
            and nf["finding"].get("severity") == "critical"
        )
        new_high = sum(
            1
            for nf in new_findings_raw
            if isinstance(nf, dict)
            and isinstance(nf.get("finding"), dict)
            and nf["finding"].get("severity") == "high"
        )
        counts = comp_json.get("counts", {"new": 0, "existing": 0, "resolved": 0, "uncertain": 0}) if comp_json else {
            "new": 0,
            "existing": 0,
            "resolved": 0,
            "uncertain": 0,
        }

        owner = project.github_owner
        repo = project.github_name
        html_url = item.html_url or (
            f"https://github.com/{owner}/{repo}/pull/{item.number}" if owner and repo else None
        )
        diff_url = f"{html_url}/files" if html_url else None

        result: dict[str, Any] = {
            "id": item.id,
            "project_id": item.project_id,
            "project_name": project.name,
            "github_owner": owner,
            "github_name": repo,
            "number": item.number,
            "title": item.title,
            "state": item.state,
            "author_login": item.author_login or "unknown",
            "head_ref": item.head_ref or "head",
            "base_ref": item.base_ref or (project.github_default_branch or "main"),
            "head_sha": item.head_sha,
            "base_sha": item.base_sha,
            "is_fork": bool(item.is_fork),
            "merged": bool(item.merged),
            "html_url": html_url,
            "diff_url": diff_url,
            "analysis_status": analysis_status,
            "is_stale_sha": stale_sha,
            "latest_base_job_id": base_job.id if base_job else item.latest_base_job_id,
            "latest_candidate_job_id": cand_job.id if cand_job else item.latest_candidate_job_id,
            "last_analyzed_sha": cand_job.head_sha if cand_job else item.last_analyzed_head_sha,
            "last_analyzed_at": (
                cand_job.finished_at.isoformat()
                if cand_job and cand_job.finished_at
                else (cand_job.created_at.isoformat() if cand_job else None)
            ),
            "last_synced_at": item.last_synced_at.isoformat() if item.last_synced_at else None,
            "base_grade": base_grade,
            "base_score": base_score,
            "head_grade": head_grade,
            "head_score": head_score,
            "grade_delta": grade_delta,
            "score_delta": score_delta,
            "new_critical_count": new_crit,
            "new_high_count": new_high,
            "counts": counts,
            "quality_gate_status": gate_status,
            "quality_gate": gate_json,
            "error": cand_job.error if cand_job else None,
        }

        if details:
            enriched_comp = dict(comp_json) if isinstance(comp_json, dict) else None
            if enriched_comp is not None:
                for bucket_key, cls_name in (
                    ("new_findings", "new"),
                    ("existing_findings", "existing"),
                    ("resolved_findings", "resolved"),
                    ("uncertain_findings", "uncertain"),
                ):
                    raw_bucket = enriched_comp.get(bucket_key, [])
                    if isinstance(raw_bucket, list):
                        enriched_bucket = []
                        rev_for_link = item.base_sha if cls_name == "resolved" else item.head_sha
                        for entry in raw_bucket:
                            if not isinstance(entry, dict):
                                continue
                            entry_copy = dict(entry)
                            f_dict = entry_copy.get("finding")
                            if isinstance(f_dict, dict):
                                enriched_f = self._enrich_finding_dict(
                                    f_dict,
                                    owner=owner,
                                    repo=repo,
                                    revision=rev_for_link,
                                    gate_json=gate_json,
                                    classification=cls_name,
                                )
                                entry_copy["finding"] = enriched_f
                                entry_copy["is_vulnerability"] = enriched_f["is_vulnerability"]
                                entry_copy["addressed_gate_conditions"] = enriched_f["addressed_gate_conditions"]
                                entry_copy["github_blob_url"] = enriched_f["github_blob_url"]
                                entry_copy["safe_code_example"] = enriched_f.get("safe_code_example")
                            enriched_bucket.append(entry_copy)
                        enriched_comp[bucket_key] = enriched_bucket
            result["comparison"] = enriched_comp
            result["candidate_job"] = self._job(cand_job, details=True) if cand_job else None
            result["base_job"] = self._job(base_job, details=False) if base_job else None

        return result

    def list_pull_requests(
        self,
        *,
        project_id: str | None = None,
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.sessions() as session:
            query = select(PullRequestRecord).order_by(PullRequestRecord.created_at.desc())
            if project_id:
                query = query.where(PullRequestRecord.project_id == project_id)
            if state and state != "all":
                query = query.where(PullRequestRecord.state == state)
            records = list(session.scalars(query))
            return [self._pull_request_dict(item, session, details=False) for item in records]

    def get_pull_request(
        self,
        pr_id: str | None = None,
        *,
        project_id: str | None = None,
        pr_number: int | None = None,
    ) -> dict[str, Any] | None:
        with self.sessions() as session:
            if pr_id is not None:
                item = session.get(PullRequestRecord, pr_id)
            elif project_id is not None and pr_number is not None:
                item = session.scalar(
                    select(PullRequestRecord).where(
                        PullRequestRecord.project_id == project_id,
                        PullRequestRecord.number == pr_number,
                    )
                )
            else:
                item = None
            if item is None:
                return None
            return self._pull_request_dict(item, session, details=True)

    def list_global_findings(
        self,
        *,
        project_id: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        finding_type: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return findings strictly scoped to each repository's latest project analysis and commit SHA."""
        results: list[dict[str, Any]] = []
        with self.sessions() as session:
            proj_query = select(ProjectRecord).order_by(ProjectRecord.created_at.desc())
            if project_id:
                proj_query = proj_query.where(ProjectRecord.id == project_id)
            for proj in session.scalars(proj_query):
                if proj.sync_status == "inaccessible":
                    continue
                proj_jobs = sorted(
                    [
                        j
                        for j in proj.jobs
                        if (j.analysis_mode or "project") == "project" and j.pull_request_number is None
                    ],
                    key=lambda j: j.created_at,
                    reverse=True,
                )
                if not proj_jobs:
                    continue
                latest = proj_jobs[0]
                if latest.status not in {"completed", "incomplete"}:
                    continue
                sha = latest.head_sha or latest.base_revision or proj.last_analyzed_sha or proj.github_default_branch or "main"
                gate_json = latest.gate_json if isinstance(latest.gate_json, dict) else None
                for f_rec in latest.findings:
                    enriched = self._enrich_finding_dict(
                        f_rec.payload_json,
                        owner=proj.github_owner,
                        repo=proj.github_name,
                        revision=sha,
                        gate_json=gate_json,
                        classification="project",
                    )
                    enriched["project_id"] = proj.id
                    enriched["project_name"] = proj.name
                    enriched["github_owner"] = proj.github_owner
                    enriched["github_name"] = proj.github_name
                    enriched["job_id"] = latest.id
                    enriched["commit_sha"] = sha
                    enriched["analysis_status"] = latest.status
                    if severity and severity != "ALL" and str(enriched.get("severity")).lower() != severity.lower():
                        continue
                    if category and category != "ALL" and str(enriched.get("category")).lower() != category.lower():
                        continue
                    if finding_type and finding_type != "ALL" and enriched.get("finding_type") != finding_type.lower():
                        continue
                    if search:
                        q = search.strip().lower()
                        haystack = (
                            f"{enriched.get('title', '')} {enriched.get('file_path', '')} "
                            f"{enriched.get('description', '')} {enriched.get('evidence', '')} {proj.name}"
                        ).lower()
                        if q not in haystack:
                            continue
                    results.append(enriched)
        return results

    def get_analytics_summary(self) -> dict[str, Any]:
        """Compute portfolio-wide quality analytics strictly from real persisted data."""
        projects = self.list_projects()
        prs = self.list_pull_requests()
        grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0, "NOT_RATED": 0}
        status_dist = {
            "NOT_ANALYZED": 0,
            "completed": 0,
            "incomplete": 0,
            "failed": 0,
            "queued": 0,
            "running": 0,
        }
        gate_dist = {"PASSED": 0, "FAILED": 0, "INCONCLUSIVE": 0}
        total_vulnerabilities = 0
        total_bugs = 0
        severity_totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        scores: list[float] = []

        for p in projects:
            st = str(p.get("analysis_status") or "NOT_ANALYZED")
            status_dist[st] = status_dist.get(st, 0) + 1
            g = str(p.get("latest_grade") or "NOT_RATED")
            grade_dist[g if g in grade_dist else "NOT_RATED"] += 1
            gs = str(p.get("latest_gate_status") or "INCONCLUSIVE")
            gate_dist[gs if gs in gate_dist else "INCONCLUSIVE"] += 1
            if isinstance(p.get("latest_score"), (int, float)):
                scores.append(float(p["latest_score"]))
            if isinstance(p.get("vulnerability_count"), int):
                total_vulnerabilities += int(p["vulnerability_count"])
            if isinstance(p.get("bug_count"), int):
                total_bugs += int(p["bug_count"])
            sev_c = p.get("severity_counts")
            if isinstance(sev_c, dict):
                for k in severity_totals:
                    severity_totals[k] += int(sev_c.get(k, 0))

        open_prs = [pr for pr in prs if pr.get("state") == "open"]
        blocked_prs = [pr for pr in open_prs if pr.get("quality_gate_status") == "FAILED"]
        passed_prs = [pr for pr in open_prs if pr.get("quality_gate_status") == "PASSED"]

        return {
            "total_repositories": len(projects),
            "analyzed_repositories": sum(1 for p in projects if p.get("analysis_status") == "completed"),
            "not_analyzed_repositories": status_dist.get("NOT_ANALYZED", 0),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "grade_distribution": grade_dist,
            "status_distribution": status_dist,
            "gate_distribution": gate_dist,
            "total_vulnerabilities": total_vulnerabilities,
            "total_bugs": total_bugs,
            "severity_totals": severity_totals,
            "total_pull_requests": len(prs),
            "open_pull_requests": len(open_prs),
            "blocked_pull_requests": len(blocked_prs),
            "passed_pull_requests": len(passed_prs),
        }

    def update_project_gate_config(
        self,
        project_id: str,
        gate_config: QualityGateConfig,
        *,
        auto_analyze: bool | None = None,
    ) -> dict[str, Any] | None:
        with self.sessions.begin() as session:
            item = session.get(ProjectRecord, project_id)
            if item is None:
                return None
            item.gate_config_json = gate_config.model_dump(mode="json")
            if auto_analyze is not None:
                item.auto_analyze = bool(auto_analyze)
        return self.get_project(project_id)

    def healthcheck(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def record_webhook_delivery(self, delivery_id: str, event: str) -> bool:
        """Return false for a replayed, previously accepted GitHub delivery."""
        try:
            with self.sessions.begin() as session:
                session.add(GitHubWebhookDeliveryRecord(delivery_id=delivery_id, event=event, status="received"))
        except IntegrityError:
            return False
        return True

    def upsert_github_installation(self, payload: dict[str, Any]) -> dict[str, Any]:
        installation_id = int(payload["id"])
        account = payload.get("account") or {}
        if not isinstance(account.get("id"), int) or not isinstance(account.get("login"), str):
            raise ValueError("GitHub installation account is invalid.")
        with self.sessions.begin() as session:
            item = session.scalar(
                select(GitHubInstallationRecord).where(
                    GitHubInstallationRecord.github_installation_id == installation_id
                )
            )
            if item is None:
                item = GitHubInstallationRecord(
                    id=str(uuid.uuid4()),
                    github_installation_id=installation_id,
                    github_account_id=account["id"],
                    account_login=account["login"],
                    account_type=str(account.get("type", "Organization")),
                    repository_selection=str(payload.get("repository_selection", "selected")),
                    status="active",
                )
                session.add(item)
            else:
                item.github_account_id, item.account_login = account["id"], account["login"]
                item.repository_selection, item.status = str(payload.get("repository_selection", "selected")), "active"
        return self.get_github_installation(installation_id) or {}

    def deactivate_github_installation(self, github_installation_id: int) -> None:
        with self.sessions.begin() as session:
            item = session.scalar(
                select(GitHubInstallationRecord).where(
                    GitHubInstallationRecord.github_installation_id == github_installation_id
                )
            )
            if item:
                item.status = "removed"

    def get_github_installation(self, github_installation_id: int) -> dict[str, Any] | None:
        with self.sessions() as session:
            item = session.scalar(
                select(GitHubInstallationRecord).where(
                    GitHubInstallationRecord.github_installation_id == github_installation_id
                )
            )
            if item is None:
                return None
            return {
                "id": item.id,
                "github_installation_id": item.github_installation_id,
                "account_login": item.account_login,
                "account_type": item.account_type,
                "repository_selection": item.repository_selection,
                "status": item.status,
                "synced_at": item.synced_at.isoformat() if item.synced_at else None,
            }

    def sync_github_repositories(self, github_installation_id: int, repositories: list[dict[str, Any]]) -> int:
        with self.sessions.begin() as session:
            installation = session.scalar(
                select(GitHubInstallationRecord).where(
                    GitHubInstallationRecord.github_installation_id == github_installation_id
                )
            )
            if installation is None or installation.status != "active":
                raise ValueError("Active GitHub installation not found.")
            seen: set[int] = set()
            for repository in repositories:
                owner = repository.get("owner") if isinstance(repository.get("owner"), dict) else {}
                repo_id, name, full_name, owner_login = (
                    repository.get("id"),
                    repository.get("name"),
                    repository.get("full_name"),
                    owner.get("login"),
                )
                if not isinstance(repo_id, int) or not all(
                    isinstance(value, str) for value in (name, full_name, owner_login)
                ):
                    raise ValueError("GitHub repository response is invalid.")
                seen.add(repo_id)
                item = session.scalar(
                    select(GitHubRepositoryRecord).where(
                        GitHubRepositoryRecord.installation_id == installation.id,
                        GitHubRepositoryRecord.github_repository_id == repo_id,
                    )
                )
                if item is None:
                    item = GitHubRepositoryRecord(
                        id=str(uuid.uuid4()),
                        installation_id=installation.id,
                        github_repository_id=repo_id,
                        owner_login=owner_login,
                        name=name,
                        full_name=full_name,
                        default_branch=repository.get("default_branch")
                        if isinstance(repository.get("default_branch"), str)
                        else None,
                        is_active=True,
                    )
                    session.add(item)
                else:
                    item.owner_login, item.name, item.full_name, item.is_active = owner_login, name, full_name, True
            for item in session.scalars(
                select(GitHubRepositoryRecord).where(GitHubRepositoryRecord.installation_id == installation.id)
            ):
                if item.github_repository_id not in seen:
                    item.is_active = False
            installation.synced_at = datetime.now(UTC)
        return len(repositories)

    def list_github_repositories(self, github_installation_id: int) -> list[dict[str, Any]]:
        with self.sessions() as session:
            installation = session.scalar(
                select(GitHubInstallationRecord).where(
                    GitHubInstallationRecord.github_installation_id == github_installation_id
                )
            )
            if installation is None:
                return []
            records = session.scalars(
                select(GitHubRepositoryRecord)
                .where(GitHubRepositoryRecord.installation_id == installation.id)
                .order_by(GitHubRepositoryRecord.full_name)
            )
            return [
                {
                    "id": item.id,
                    "github_repository_id": item.github_repository_id,
                    "full_name": item.full_name,
                    "default_branch": item.default_branch,
                    "is_active": item.is_active,
                }
                for item in records
            ]

    def save_policy(
        self,
        installation_id: str,
        policy: dict[str, Any],
        *,
        repository_id: str | None = None,
        actor: str = "local-admin",
    ) -> dict[str, Any]:
        with self.sessions.begin() as session:
            version = (
                session.scalar(
                    select(PolarisPolicyRecord.version)
                    .where(
                        PolarisPolicyRecord.installation_id == installation_id,
                        PolarisPolicyRecord.repository_id == repository_id,
                    )
                    .order_by(PolarisPolicyRecord.version.desc())
                )
                or 0
            ) + 1
            item = PolarisPolicyRecord(
                id=str(uuid.uuid4()),
                installation_id=installation_id,
                repository_id=repository_id,
                version=version,
                policy_json=policy,
                created_by=actor,
            )
            session.add(item)
            session.add(
                PolarisAuditLogRecord(
                    id=str(uuid.uuid4()),
                    installation_id=installation_id,
                    action="policy.updated",
                    actor=actor,
                    payload_json={"policy_id": item.id, "version": version, "repository_id": repository_id},
                )
            )
            return {"id": item.id, "version": version, "policy": policy, "repository_id": repository_id}

    def list_projects(self) -> list[dict[str, Any]]:
        with self.sessions() as session:
            return [
                self._project(item)
                for item in session.scalars(select(ProjectRecord).order_by(ProjectRecord.created_at.desc()))
            ]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            item = session.get(ProjectRecord, project_id)
            return self._project(item) if item else None

    def create_job(
        self,
        project_id: str,
        base_revision: str | None = None,
        *,
        analysis_mode: str = "project",
        baseline_job_id: str | None = None,
        pull_request_number: int | None = None,
        head_sha: str | None = None,
    ) -> dict[str, Any]:
        queued_eval = evaluate_quality(None, job_status="queued")
        item = JobRecord(
            id=str(uuid.uuid4()),
            project_id=project_id,
            base_revision=base_revision,
            analysis_mode=analysis_mode,
            baseline_job_id=baseline_job_id,
            pull_request_number=pull_request_number,
            head_sha=head_sha,
            status="queued",
            quality_json=queued_eval.model_dump(mode="json"),
            gate_json=evaluate_quality_gate(queued_eval).model_dump(mode="json"),
        )
        with self.sessions.begin() as session:
            session.add(item)
        return self.get_job(item.id) or {"id": item.id}

    def list_jobs(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self.sessions() as session:
            query = select(JobRecord).order_by(JobRecord.created_at.desc())
            if project_id:
                query = query.where(JobRecord.project_id == project_id)
            return [self._job(item, False) for item in session.scalars(query)]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            item = session.get(JobRecord, job_id)
            return self._job(item) if item else None

    def compare_jobs(
        self,
        baseline_job_id: str,
        candidate_job_id: str,
        gate_config: QualityGateConfig | None = None,
    ) -> dict[str, Any] | None:
        with self.sessions.begin() as session:
            base_item = session.get(JobRecord, baseline_job_id)
            cand_item = session.get(JobRecord, candidate_job_id)
            if base_item is None or cand_item is None:
                return None
            cfg = gate_config or self._gate_config(cand_item.project)
            base_report = AnalysisReport.model_validate(base_item.report_json) if base_item.report_json else None
            cand_report = AnalysisReport.model_validate(cand_item.report_json) if cand_item.report_json else None
            comparison = compare_pull_request(
                base_report=base_report,
                pr_report=cand_report,
                base_job_status=base_item.status,
                base_job_error=base_item.error,
                pr_job_status=cand_item.status,
                pr_job_error=cand_item.error,
                gate_config=cfg,
                base_revision=base_item.base_revision,
                head_revision=cand_item.head_sha or cand_item.base_revision,
            )
            gh_check = build_github_check_contract(
                comparison,
                head_sha=cand_item.head_sha or cand_item.base_revision or "HEAD",
            )
            payload = comparison.model_dump(mode="json")
            payload["baseline_job_id"] = baseline_job_id
            payload["candidate_job_id"] = candidate_job_id
            payload["github_check_contract"] = gh_check.model_dump(mode="json")
            cand_item.baseline_job_id = baseline_job_id
            cand_item.analysis_mode = "pr"
            cand_item.quality_json = comparison.pr_evaluation.model_dump(mode="json")
            cand_item.gate_json = comparison.quality_gate.model_dump(mode="json")
            cand_item.comparison_json = payload
            return payload

    def claim_job(self, job_id: str | None = None) -> dict[str, Any] | None:
        with self.sessions.begin() as session:
            query = select(JobRecord).where(JobRecord.status == "queued").order_by(JobRecord.created_at)
            if job_id:
                query = query.where(JobRecord.id == job_id)
            if not self.database_url.startswith("sqlite"):
                query = query.with_for_update(skip_locked=True)
            item = session.scalars(query.limit(1)).first()
            if item is None:
                return None
            now = datetime.now(UTC)
            item.status, item.started_at, item.claimed_at, item.claim_token = "running", now, now, str(uuid.uuid4())
            job = self._job(item, False)
            job["claim_token"] = item.claim_token
            return job

    def recover_interrupted_jobs(self, stale_after_seconds: int = 300) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        with self.sessions.begin() as session:
            result = session.execute(
                update(JobRecord)
                .where(JobRecord.status == "running", JobRecord.claimed_at < cutoff)
                .values(status="queued", started_at=None, claimed_at=None, claim_token=None)
            )
            return int(result.rowcount)

    def complete(
        self,
        job_id: str,
        claim_token: str,
        report: AnalysisReport,
        *,
        analyzed_sha: str | None = None,
    ) -> bool:
        payload = report.model_dump(mode="json")
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            item = session.get(JobRecord, job_id)
            if item and item.status == "running" and item.claim_token == claim_token:
                item.status, item.finished_at, item.report_json = report.status, now, payload
                if analyzed_sha and not item.head_sha:
                    item.head_sha = analyzed_sha
                item.findings = [
                    FindingRecord(id=finding["id"], payload_json=finding) for finding in payload["findings"]
                ]
                baseline_item = session.get(JobRecord, item.baseline_job_id) if item.baseline_job_id else None
                gate_cfg = self._gate_config(item.project)
                q_dump, g_dump, c_dump = self._compute_job_quality_bundle(item, report, gate_cfg, baseline_item)
                item.quality_json = q_dump
                item.gate_json = g_dump
                item.comparison_json = c_dump
                if (item.analysis_mode or "project") == "project" and item.pull_request_number is None:
                    sha = analyzed_sha or item.head_sha or item.base_revision
                    if sha:
                        item.project.last_analyzed_sha = sha
                    if report.status == "completed":
                        item.project.last_successful_analysis_at = now
                return True
        return False

    def fail(self, job_id: str, claim_token: str, error: str) -> bool:
        with self.sessions.begin() as session:
            item = session.get(JobRecord, job_id)
            if item and item.status == "running" and item.claim_token == claim_token:
                item.status, item.finished_at, item.error = "failed", datetime.now(UTC), error[:2000]
                baseline_item = session.get(JobRecord, item.baseline_job_id) if item.baseline_job_id else None
                gate_cfg = self._gate_config(item.project)
                q_dump, g_dump, c_dump = self._compute_job_quality_bundle(item, None, gate_cfg, baseline_item)
                item.quality_json = q_dump
                item.gate_json = g_dump
                item.comparison_json = c_dump
                return True
        return False


__all__ = [
    "Base",
    "IntegrityError",
    "ProjectRecord",
    "PullRequestRecord",
    "SyncSettingsRecord",
    "WebStore",
    "default_database_url",
]
