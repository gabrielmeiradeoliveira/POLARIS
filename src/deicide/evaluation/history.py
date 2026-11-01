"""Append-only, sanitized benchmark-validation history for DEICIDE."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from deicide.core.models import Confidence, FindingCategory, LineRange
from deicide.evaluation.models import CaseEvaluationResult, EvaluationSummary

_SECRET_PATTERNS = (
    re.compile(r"nvapi-[A-Za-z0-9_-]+", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9_.-]+", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[=:]\s*[^\s,;]+"),
)


class HistoryIntegrityError(ValueError):
    """Raised when an immutable history record is malformed or conflicts with disk."""


class DuplicateHistoryRunError(HistoryIntegrityError):
    """Raised when an existing run ID is submitted again."""


class ValidationOutcome(StrEnum):
    """Human or oracle validation outcome for a single finding."""

    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"
    NOT_ASSESSED = "not_assessed"


class VerificationMethod(StrEnum):
    """Documented method used to assess a finding."""

    EXECUTABLE_ORACLE = "executable_oracle"
    FIXTURE_GROUND_TRUTH = "fixture_ground_truth"
    DETERMINISTIC_VALIDATION = "deterministic_validation"
    HUMAN_REVIEW = "human_review"
    DOCUMENTED_OTHER = "documented_other"


class CorpusKind(StrEnum):
    """Corpus provenance class; aggregates never mix the two kinds implicitly."""

    REAL = "real"
    SYNTHETIC = "synthetic"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def sanitize_history_text(value: str | None, *, max_length: int = 1_000) -> str | None:
    """Redact likely credentials and bound persisted evidence/response excerpts."""
    if value is None:
        return None
    cleaned = value
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned[:max_length]


def canonical_sha256(payload: Any) -> str:
    """Hash JSON-compatible data using deterministic serialization."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


class FindingValidationRecord(BaseModel):
    """Sanitized, stable per-finding validation outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str = Field(min_length=5)
    case_id: str
    file_path: str
    line_range: LineRange
    category: FindingCategory
    evidence: str | None = None
    response_excerpt: str | None = None
    declared_confidence: Confidence | None = None
    numeric_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    validation_outcome: ValidationOutcome
    verification_method: VerificationMethod
    decision_reason: str
    decided_at: datetime = Field(default_factory=_utc_now)

    @field_validator("evidence", "response_excerpt", "decision_reason", mode="before")
    @classmethod
    def sanitize_persisted_text(cls, value: str | None) -> str | None:
        return sanitize_history_text(value)

    @model_validator(mode="after")
    def require_utc_timestamp(self) -> FindingValidationRecord:
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware UTC.")
        return self


class ValidationMetrics(BaseModel):
    """Metrics derived only from records whose outcomes are available."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_findings: int = Field(ge=0)
    assessed_findings: int = Field(ge=0)
    confirmed_findings: int = Field(ge=0)
    rejected_findings: int = Field(ge=0)
    uncertain_findings: int = Field(ge=0)
    not_assessed_findings: int = Field(ge=0)
    validation_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    confirmation_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class CalibrationBin(BaseModel):
    """Reliability-diagram bin, available only for explicitly numeric probabilities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lower_bound: float = Field(ge=0.0, le=1.0)
    upper_bound: float = Field(ge=0.0, le=1.0)
    sample_size: int = Field(ge=0)
    mean_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    observed_frequency: float | None = Field(default=None, ge=0.0, le=1.0)


class CalibrationMetrics(BaseModel):
    """Probability calibration, deliberately unavailable for qualitative confidence labels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    sample_size: int = Field(ge=0)
    minimum_sample_size: int = Field(ge=1)
    brier_score: float | None = Field(default=None, ge=0.0, le=1.0)
    bins: list[CalibrationBin] = Field(default_factory=list)
    reason: str | None = None


class BenchmarkHistoryManifest(BaseModel):
    """Immutable, compact manifest for one completed benchmark execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.1"
    run_id: str = Field(min_length=8, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    timestamp_utc: datetime = Field(default_factory=_utc_now)
    git_commit: str
    deicide_version: str
    provider: str
    model: str
    configuration: str
    corpus_kind: CorpusKind
    corpus_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operational_limits: dict[str, int | float | bool | str | None] = Field(default_factory=dict)
    summary: EvaluationSummary
    findings: list[FindingValidationRecord] = Field(default_factory=list)
    findings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_metrics: ValidationMetrics | None = None
    calibration_metrics: CalibrationMetrics | None = None
    manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_integrity(self) -> BenchmarkHistoryManifest:
        if self.timestamp_utc.tzinfo is None or self.timestamp_utc.utcoffset() is None:
            raise ValueError("timestamp_utc must be timezone-aware UTC.")
        expected_findings_hash = canonical_sha256([record.model_dump(mode="json") for record in self.findings])
        if self.findings_sha256 != expected_findings_hash:
            raise ValueError("findings_sha256 does not match finding records.")
        if self.manifest_sha256 is not None and self.manifest_sha256 != manifest_payload_hash(self):
            raise ValueError("manifest_sha256 does not match manifest payload.")
        return self


def manifest_payload_hash(manifest: BenchmarkHistoryManifest) -> str:
    """Hash a manifest excluding its self-referential digest."""
    payload = manifest.model_dump(mode="json", exclude={"manifest_sha256"})
    # Version 1.0 predated per-run derived validation/calibration summaries.
    # Excluding absent-in-v1 fields preserves integrity verification for existing history.
    if (
        manifest.schema_version == "1.0"
        and manifest.validation_metrics is None
        and manifest.calibration_metrics is None
    ):
        payload.pop("validation_metrics", None)
        payload.pop("calibration_metrics", None)
    return canonical_sha256(payload)


def validation_metrics(records: list[FindingValidationRecord]) -> ValidationMetrics:
    """Calculate coverage and confirmation rate without treating unknowns as rejections."""
    counts = {outcome: 0 for outcome in ValidationOutcome}
    for record in records:
        counts[record.validation_outcome] += 1
    total = len(records)
    assessed = counts[ValidationOutcome.CONFIRMED] + counts[ValidationOutcome.REJECTED]
    return ValidationMetrics(
        total_findings=total,
        assessed_findings=assessed,
        confirmed_findings=counts[ValidationOutcome.CONFIRMED],
        rejected_findings=counts[ValidationOutcome.REJECTED],
        uncertain_findings=counts[ValidationOutcome.UNCERTAIN],
        not_assessed_findings=counts[ValidationOutcome.NOT_ASSESSED],
        validation_coverage=round(assessed / total, 4) if total else None,
        confirmation_rate=round(counts[ValidationOutcome.CONFIRMED] / assessed, 4) if assessed else None,
    )


def calibration_metrics(
    records: list[FindingValidationRecord], *, minimum_sample_size: int = 20, bins: int = 10
) -> CalibrationMetrics:
    """Calculate Brier/reliability values only for assessed numeric probabilities."""
    if minimum_sample_size < 1 or bins < 1:
        raise ValueError("minimum_sample_size and bins must be positive.")
    samples = [
        (record.numeric_probability, 1.0 if record.validation_outcome == ValidationOutcome.CONFIRMED else 0.0)
        for record in records
        if record.numeric_probability is not None
        and record.validation_outcome in {ValidationOutcome.CONFIRMED, ValidationOutcome.REJECTED}
    ]
    if len(samples) < minimum_sample_size:
        return CalibrationMetrics(
            available=False,
            sample_size=len(samples),
            minimum_sample_size=minimum_sample_size,
            reason="Insufficient assessed findings with explicitly numeric probabilities.",
        )
    reliability_bins: list[CalibrationBin] = []
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        members = [sample for sample in samples if lower <= sample[0] < upper or (index == bins - 1 and sample[0] == 1.0)]
        reliability_bins.append(
            CalibrationBin(
                lower_bound=lower,
                upper_bound=upper,
                sample_size=len(members),
                mean_probability=round(sum(item[0] for item in members) / len(members), 4) if members else None,
                observed_frequency=round(sum(item[1] for item in members) / len(members), 4) if members else None,
            )
        )
    brier = sum((probability - outcome) ** 2 for probability, outcome in samples) / len(samples)
    return CalibrationMetrics(
        available=True,
        sample_size=len(samples),
        minimum_sample_size=minimum_sample_size,
        brier_score=round(brier, 6),
        bins=reliability_bins,
    )


def _finding_records(case: CaseEvaluationResult) -> list[FindingValidationRecord]:
    diagnostics = case.diagnostics
    if diagnostics is None:
        return []
    matched_ids = {match.finding_id for match in diagnostics.matched_findings}
    records: list[FindingValidationRecord] = []
    for finding in case.actual_findings:
        confirmed = finding.id in matched_ids
        records.append(
            FindingValidationRecord(
                finding_id=finding.id,
                case_id=case.case_id,
                file_path=finding.file_path,
                line_range=finding.line_range,
                category=finding.category,
                evidence=sanitize_history_text(finding.evidence),
                response_excerpt=sanitize_history_text(f"{finding.title}: {finding.description}"),
                declared_confidence=finding.confidence,
                validation_outcome=ValidationOutcome.CONFIRMED if confirmed else ValidationOutcome.REJECTED,
                verification_method=VerificationMethod.FIXTURE_GROUND_TRUTH,
                decision_reason="Matched expected fixture defect." if confirmed else "Did not match fixture ground truth.",
            )
        )
    for rejected in diagnostics.rejected_candidates:
        payload = {
            "case_id": case.case_id,
            "file_path": rejected.file_path,
            "line_range": rejected.line_range.model_dump(mode="json"),
            "category": rejected.category.value,
            "title": rejected.title,
            "reason": rejected.reason,
        }
        records.append(
            FindingValidationRecord(
                finding_id=f"candidate-{canonical_sha256(payload)[:16]}",
                case_id=case.case_id,
                file_path=rejected.file_path,
                line_range=rejected.line_range,
                category=rejected.category,
                response_excerpt=sanitize_history_text(rejected.title),
                validation_outcome=ValidationOutcome.REJECTED,
                verification_method=VerificationMethod.DETERMINISTIC_VALIDATION,
                decision_reason=sanitize_history_text(rejected.reason) or "Rejected by deterministic validation.",
            )
        )
    return records


def current_git_commit(repo_root: Path) -> str:
    """Return the current commit without requiring network access."""
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def installed_deicide_version() -> str:
    """Return installed package version with a source-tree fallback."""
    try:
        return version("deicide")
    except PackageNotFoundError:
        return "0.1.0"


def build_manifest(
    *,
    run_id: str,
    summary: EvaluationSummary,
    corpus_path: Path,
    corpus_kind: CorpusKind,
    provider: str,
    model: str,
    configuration: str,
    operational_limits: dict[str, int | float | bool | str | None],
    repo_root: Path,
) -> BenchmarkHistoryManifest:
    """Build a self-verifying manifest from a completed offline or external evaluation."""
    corpus_sha256 = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    records = [record for case in summary.case_results for record in _finding_records(case)]
    findings_hash = canonical_sha256([record.model_dump(mode="json") for record in records])
    aggregate_summary = summary.model_copy(update={"case_results": []})
    unsealed = BenchmarkHistoryManifest(
        run_id=run_id,
        git_commit=current_git_commit(repo_root),
        deicide_version=installed_deicide_version(),
        provider=provider,
        model=model,
        configuration=configuration,
        corpus_kind=corpus_kind,
        corpus_sha256=corpus_sha256,
        operational_limits=operational_limits,
        summary=aggregate_summary,
        findings=records,
        findings_sha256=findings_hash,
        validation_metrics=validation_metrics(records),
        calibration_metrics=calibration_metrics(records),
    )
    return unsealed.model_copy(update={"manifest_sha256": manifest_payload_hash(unsealed)})


def append_manifest(history_root: Path, manifest: BenchmarkHistoryManifest) -> Path:
    """Persist a manifest exactly once; existing run IDs are never overwritten."""
    manifests_dir = history_root / "manifests"
    target = manifests_dir / f"{manifest.run_id}.json"
    if target.exists():
        try:
            existing = BenchmarkHistoryManifest.model_validate_json(target.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise HistoryIntegrityError(f"Existing history manifest is invalid: {target}") from exc
        if existing.manifest_sha256 == manifest.manifest_sha256:
            raise DuplicateHistoryRunError(f"Run ID '{manifest.run_id}' already exists with the same manifest hash.")
        raise HistoryIntegrityError(f"Run ID '{manifest.run_id}' already exists with a different manifest hash.")
    manifests_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def load_manifests(history_root: Path) -> list[BenchmarkHistoryManifest]:
    """Load and integrity-check append-only manifests deterministically."""
    manifests_dir = history_root / "manifests"
    if not manifests_dir.exists():
        return []
    manifests: list[BenchmarkHistoryManifest] = []
    seen_ids: set[str] = set()
    for path in sorted(manifests_dir.glob("*.json")):
        manifest = BenchmarkHistoryManifest.model_validate_json(path.read_text(encoding="utf-8"))
        if manifest.run_id in seen_ids:
            raise HistoryIntegrityError(f"Duplicate run ID '{manifest.run_id}' in history.")
        seen_ids.add(manifest.run_id)
        manifests.append(manifest)
    return manifests


def trend_summary(manifests: list[BenchmarkHistoryManifest], *, corpus_kind: CorpusKind) -> dict[str, Any]:
    """Return a provenance-separated trend summary suitable for Markdown or JSON output."""
    scoped = [manifest for manifest in manifests if manifest.corpus_kind == corpus_kind]
    runs = []
    for manifest in scoped:
        validation = manifest.validation_metrics or validation_metrics(manifest.findings)
        calibration = manifest.calibration_metrics or calibration_metrics(manifest.findings)
        runs.append(
            {
                "run_id": manifest.run_id,
                "timestamp_utc": manifest.timestamp_utc.isoformat(),
                "deicide_version": manifest.deicide_version,
                "provider": manifest.provider,
                "model": manifest.model,
                "configuration": manifest.configuration,
                "sample_size": manifest.summary.dataset_size,
                "precision": manifest.summary.precision,
                "recall": manifest.summary.recall,
                "f1_score": manifest.summary.f1_score,
                "false_positive_rate": manifest.summary.false_positive_rate,
                "completion_rate": round(manifest.summary.successful_cases / manifest.summary.dataset_size, 4)
                if manifest.summary.dataset_size
                else None,
                "validation": validation.model_dump(mode="json"),
                "calibration": calibration.model_dump(mode="json"),
            }
        )
    return {"corpus_kind": corpus_kind.value, "run_count": len(runs), "runs": runs}


def render_trend_markdown(summary: dict[str, Any]) -> str:
    """Render a compact, provenance-scoped trend report without invented certainty."""
    lines = [
        "# DEICIDE Validation History Trend",
        "",
        f"Corpus kind: `{summary['corpus_kind']}`",
        f"Runs: {summary['run_count']}",
        "",
        "| Run | Version | Provider/model | Configuration | Cases | Precision | Recall | F1 | Validation coverage |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for run in summary["runs"]:
        validation = run["validation"]
        def show(value: float | None) -> str:
            return f"{value:.4f}" if value is not None else "undefined"

        lines.append(
            "| {run_id} | {version} | {provider}/{model} | {configuration} | {cases} | {precision} | {recall} | {f1} | {coverage} |".format(
                run_id=run["run_id"],
                version=run["deicide_version"],
                provider=run["provider"],
                model=run["model"],
                configuration=run["configuration"],
                cases=run["sample_size"],
                precision=show(run["precision"]),
                recall=show(run["recall"]),
                f1=show(run["f1_score"]),
                coverage=show(validation["validation_coverage"]),
            )
        )
    lines.extend(
        [
            "",
            "Calibration is reported only when explicitly numeric probabilities and the configured minimum sample size exist.",
            "Qualitative confidence labels are not probabilities and are never converted to one.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_trend_reports(history_root: Path, *, run_id: str) -> tuple[Path, Path]:
    """Append run-scoped JSON/Markdown trends; never replace an earlier report."""
    reports_dir = history_root / "reports"
    manifests = load_manifests(history_root)
    json_path = reports_dir / f"trend-{run_id}.json"
    markdown_path = reports_dir / f"trend-{run_id}.md"
    if json_path.exists() or markdown_path.exists():
        raise DuplicateHistoryRunError(f"Trend report for run ID '{run_id}' already exists.")
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "real": trend_summary(manifests, corpus_kind=CorpusKind.REAL),
        "synthetic": trend_summary(manifests, corpus_kind=CorpusKind.SYNTHETIC),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(
        render_trend_markdown(payload["real"]) + "\n" + render_trend_markdown(payload["synthetic"]),
        encoding="utf-8",
    )
    return json_path, markdown_path
