"""Isolated, deterministic, versioned Quality Engine, Quality Gate, and PR Baseline comparison."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polaris.core.models import AnalysisReport, AnalysisWarning, Confidence, Finding, Severity
from polaris.intelligence.deduplicator import (
    are_categories_compatible,
    are_findings_duplicates,
    extract_code_tokens,
    extract_defect_concepts,
    normalize_code_evidence,
    token_jaccard,
)
from polaris.intelligence.evidence_validator import normalize_ws

QUALITY_FORMULA_VERSION = "polaris-quality-v1"
QUALITY_GATE_VERSION = "polaris-gate-v1"
PR_COMPARISON_VERSION = "polaris-pr-v1"

INCOMPLETE_WARNING_CODES: frozenset[str] = frozenset(
    {
        "DIFF_TRUNCATED",
        "MAX_FILES_EXCEEDED",
        "CONTEXT_BUDGET_REACHED",
        "FILE_TOO_LARGE",
        "TOKEN_BUDGET_TRUNCATED",
        "BUDGET_EXCEEDED_INCOMPLETE",
        "PROVIDER_SKIPPED_BUDGET",
        "PROVIDER_STAGE_FAILED_STATIC_PRESERVED",
    }
)


class QualityGrade(StrEnum):
    """Discrete Polaris quality grades plus explicit NOT_RATED when evidence is insufficient."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"
    NOT_RATED = "NOT_RATED"


class OperationalStatus(StrEnum):
    """Operational execution state separated from code quality grade."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    EMPTY_DIFF = "empty_diff"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class QualityGateStatus(StrEnum):
    """Quality Gate evaluation status."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class FindingDeltaClassification(StrEnum):
    """Classification of findings when comparing a candidate/PR change against a baseline."""

    NEW = "new"
    EXISTING = "existing"
    RESOLVED = "resolved"
    UNCERTAIN = "uncertain"


SEVERITY_PENALTY: dict[Severity, float] = {
    Severity.CRITICAL: 45.0,
    Severity.HIGH: 22.0,
    Severity.MEDIUM: 10.0,
    Severity.LOW: 4.0,
    Severity.INFO: 1.0,
}

CONFIDENCE_WEIGHT: dict[Confidence, float] = {
    Confidence.HIGH: 1.0,
    Confidence.MEDIUM: 0.75,
    Confidence.LOW: 0.5,
}


class AnalysisScopeSummary(BaseModel):
    """Explicit separation of analyzed scope and operational coverage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operational_status: OperationalStatus
    files_analyzed_count: int = Field(default=0, ge=0)
    files_analyzed: list[str] = Field(default_factory=list)
    modules_executed: list[str] = Field(default_factory=list)
    is_complete: bool = False
    has_sufficient_evidence: bool = False
    truncation_warnings: list[str] = Field(default_factory=list)
    warning_count: int = Field(default=0, ge=0)


class FindingPenaltyEvidence(BaseModel):
    """Auditable breakdown of how a single finding contributed to the quality score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    stable_fingerprint: str
    file_path: str
    start_line: int
    end_line: int
    severity: Severity
    confidence: Confidence
    category: str
    base_penalty: float
    confidence_multiplier: float
    effective_penalty: float
    evidence_excerpt: str


class QualityEvaluation(BaseModel):
    """Versioned, deterministic A-F quality rating separated from operational status and scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    formula_version: str = Field(default=QUALITY_FORMULA_VERSION)
    grade: QualityGrade
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    total_penalty: float = Field(default=0.0, ge=0.0)
    not_rated_reason: str | None = None
    explanation: str
    severity_counts: dict[str, int] = Field(default_factory=dict)
    confidence_counts: dict[str, int] = Field(default_factory=dict)
    vulnerability_count: int = Field(default=0, ge=0)
    bug_count: int = Field(default=0, ge=0)
    scope: AnalysisScopeSummary
    criteria: dict[str, object] = Field(default_factory=dict)
    evidence_used: list[FindingPenaltyEvidence] = Field(default_factory=list)


class QualityGateConfig(BaseModel):
    """Configurable, objective criteria for the Polaris Quality Gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_version: str = Field(default=QUALITY_GATE_VERSION)
    min_grade: Literal["A", "B", "C", "D"] = "C"
    max_critical_findings: int = Field(default=0, ge=0)
    max_high_findings: int = Field(default=0, ge=0)
    max_new_critical_findings: int = Field(default=0, ge=0)
    max_new_high_findings: int = Field(default=0, ge=0)
    max_total_new_findings: int = Field(default=3, ge=0)
    require_complete_analysis: bool = True


class QualityGateConditionResult(BaseModel):
    """Single objective criterion evaluated by a Quality Gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    criterion: str
    passed: bool
    actual: str
    threshold: str
    reason: str


class QualityGateResult(BaseModel):
    """Result of evaluating a QualityEvaluation (and optional PR comparison) against a QualityGateConfig."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_version: str = Field(default=QUALITY_GATE_VERSION)
    status: QualityGateStatus
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    conditions: list[QualityGateConditionResult] = Field(default_factory=list)
    config: QualityGateConfig


class ComparedFindingItem(BaseModel):
    """A finding classified during baseline vs PR comparison with explicit match rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    classification: FindingDeltaClassification
    finding: Finding
    stable_fingerprint: str
    matched_baseline_finding_id: str | None = None
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str
    is_vulnerability: bool = False
    addressed_gate_conditions: list[str] = Field(default_factory=list)


class PullRequestComparisonResult(BaseModel):
    """Complete baseline vs candidate/PR quality evaluation, finding delta, and Quality Gate verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_version: str = Field(default=PR_COMPARISON_VERSION)
    base_revision: str | None = None
    head_revision: str | None = None
    base_evaluation: QualityEvaluation
    pr_evaluation: QualityEvaluation
    quality_gate: QualityGateResult
    grade_delta: str
    score_delta: float | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    new_findings: list[ComparedFindingItem] = Field(default_factory=list)
    existing_findings: list[ComparedFindingItem] = Field(default_factory=list)
    resolved_findings: list[ComparedFindingItem] = Field(default_factory=list)
    uncertain_findings: list[ComparedFindingItem] = Field(default_factory=list)
    summary: str


class GitHubCheckAnnotationContract(BaseModel):
    """Contract for future GitHub Checks API annotation payload (prepared without running a GitHub App)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    start_line: int = Field(..., ge=1)
    end_line: int = Field(..., ge=1)
    annotation_level: Literal["notice", "warning", "failure"]
    title: str
    message: str
    raw_details: str | None = None


class GitHubCheckRunContract(BaseModel):
    """Contract for future GitHub Checks API integration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "Polaris / Quality Gate"
    head_sha: str
    status: Literal["queued", "in_progress", "completed"]
    conclusion: Literal["success", "failure", "neutral", "Action_required"] | None = None
    title: str
    summary: str
    text: str
    annotations: list[GitHubCheckAnnotationContract] = Field(default_factory=list)


_GRADE_ORDER: dict[QualityGrade, int] = {
    QualityGrade.A: 5,
    QualityGrade.B: 4,
    QualityGrade.C: 3,
    QualityGrade.D: 2,
    QualityGrade.F: 1,
    QualityGrade.NOT_RATED: 0,
}

VULNERABILITY_RULE_PREFIXES: tuple[str, ...] = (
    "[DET-SQL-INTERPOLATION]",
    "[DET-SSRF",
    "[DET-OPEN-REDIRECT",
    "[DET-WEBHOOK-SIGNATURE",
    "[DET-UNSIGNED-TOKEN",
    "[DET-UNTRUSTED-HOST",
    "[DET-REDIRECT-HOST-STRIPPING",
    "[DET-PATH-CONTAINMENT",
    "[DET-COLLECTION-FILTER",
    "[DET-AUTH",
    "[DET-CSRF",
    "[DET-XSS",
    "[DET-COMMAND-INJECTION",
    "[DET-SECRET",
)

VULNERABILITY_KEYWORDS: tuple[str, ...] = (
    "sql injection",
    "interpolated into a sql",
    "path containment",
    "directory traversal",
    "path traversal",
    "open redirect",
    "webhook signature",
    "unsigned token",
    "untrusted host",
    "redirect host stripping",
    "visibility filter removed",
    "authorization",
    "command injection",
    "ssrf",
)


def is_vulnerability_finding(finding: Finding | dict[str, object]) -> bool:
    """Deterministically classify whether a finding represents a security vulnerability vs a correctness bug."""
    if isinstance(finding, dict):
        title = str(finding.get("title") or "")
        desc = str(finding.get("description") or "")
        module_id = str(finding.get("module_id") or "")
    else:
        title = finding.title
        desc = finding.description
        module_id = finding.module_id

    if module_id.lower() in {"diomedes", "security"}:
        return True
    upper_title = title.upper()
    if any(upper_title.startswith(prefix) or prefix in upper_title for prefix in VULNERABILITY_RULE_PREFIXES):
        return True
    combined = f"{title} {desc}".lower()
    return any(keyword in combined for keyword in VULNERABILITY_KEYWORDS)


def addressed_gate_conditions(
    finding: Finding | dict[str, object],
    gate_result: QualityGateResult | dict[str, object] | None,
    *,
    classification: str = "new",
) -> list[str]:
    """Identify which failed Quality Gate criteria remediating a given finding directly addresses."""
    if gate_result is None:
        return []
    sev = (
        str(finding.get("severity") or "").lower()
        if isinstance(finding, dict)
        else finding.severity.value.lower()
    )
    conditions = (
        gate_result.get("conditions", [])
        if isinstance(gate_result, dict)
        else [c.model_dump(mode="json") for c in gate_result.conditions]
    )
    failed_criteria = {
        str(c.get("criterion"))
        for c in conditions
        if isinstance(c, dict) and not c.get("passed", True)
    }
    addressed: list[str] = []
    is_delta = classification in {"new", "uncertain"}
    if "minimum_grade" in failed_criteria and (is_delta or classification == "project"):
        addressed.append("minimum_grade")
    if sev == "critical":
        if "max_new_critical_findings" in failed_criteria and is_delta:
            addressed.append("max_new_critical_findings")
        if "max_critical_findings" in failed_criteria:
            addressed.append("max_critical_findings")
    if sev == "high":
        if "max_new_high_findings" in failed_criteria and is_delta:
            addressed.append("max_new_high_findings")
        if "max_high_findings" in failed_criteria:
            addressed.append("max_high_findings")
    if is_delta and "max_total_new_findings" in failed_criteria and classification == "new":
        addressed.append("max_total_new_findings")
    if (
        classification == "uncertain"
        and sev in {"critical", "high"}
        and "uncertain_high_or_critical_findings" in failed_criteria
    ):
        addressed.append("uncertain_high_or_critical_findings")
    return addressed


def compute_stable_finding_fingerprint(finding: Finding) -> str:
    """Compute a line-drift-tolerant stable fingerprint for cross-revision finding identity.

    Uses module_id, normalized file_path, category, and normalized code evidence (without line numbers)
    so the same underlying defect shifting by a few lines across commits retains a stable identity.
    """
    norm_ev = normalize_code_evidence(finding.evidence) or normalize_ws(finding.evidence)
    concepts = ",".join(sorted(extract_defect_concepts(finding.title, finding.description, norm_ev)))
    raw = (
        f"{finding.module_id.strip().lower()}|"
        f"{finding.file_path.strip()}|"
        f"{finding.category.value.strip().lower()}|"
        f"{norm_ev}|"
        f"{concepts}"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"pol-{digest}"


def _extract_truncation_warnings(warnings: list[AnalysisWarning]) -> list[str]:
    return [f"{w.code}: {w.message}" for w in warnings if w.code in INCOMPLETE_WARNING_CODES]


def evaluate_quality(
    report: AnalysisReport | None,
    *,
    job_status: str | None = None,
    job_error: str | None = None,
) -> QualityEvaluation:
    """Deterministically evaluate code quality (A-F or NOT_RATED) from a real AnalysisReport.

    Explicit formula (`polaris-quality-v1`):
    - Each finding `i` receives `effective_penalty_i = SEVERITY_PENALTY[severity] * CONFIDENCE_WEIGHT[confidence]`:
      - Severity base penalties: CRITICAL=45, HIGH=22, MEDIUM=10, LOW=4, INFO=1
      - Confidence multipliers: HIGH=1.0, MEDIUM=0.75, LOW=0.5
    - `total_penalty = sum(effective_penalty_i)`
    - `score = max(0.0, round(100.0 - total_penalty, 2))`
    - Grade boundaries (with hard severity caps):
      - Any CRITICAL finding with HIGH/MEDIUM confidence -> Grade F (capped at D if LOW confidence)
      - Score >= 90.0 and 0 CRITICAL and 0 HIGH -> Grade A
      - Score >= 75.0 and 0 CRITICAL -> Grade B
      - Score >= 60.0 and 0 CRITICAL -> Grade C
      - Score >= 40.0 and 0 CRITICAL (or LOW-confidence CRITICAL) -> Grade D
      - Score < 40.0 or CRITICAL finding (HIGH/MEDIUM confidence) -> Grade F
    - Insufficient evidence rules (`NOT_RATED`):
      - Job status is queued, running, or failed, or report is None
      - Report status is `incomplete` or contains truncation/budget-skip warnings
      - Report status is `empty_diff` or `files_analyzed` is empty (0 files analyzed)
      - `modules_executed` is empty
    """
    criteria_doc: dict[str, object] = {
        "formula_version": QUALITY_FORMULA_VERSION,
        "severity_penalties": {k.value: v for k, v in SEVERITY_PENALTY.items()},
        "confidence_weights": {k.value: v for k, v in CONFIDENCE_WEIGHT.items()},
        "grade_boundaries": {
            "A": "score >= 90.0, critical == 0, high == 0",
            "B": "score >= 75.0, critical == 0",
            "C": "score >= 60.0, critical == 0",
            "D": "score >= 40.0, critical (high/medium confidence) == 0",
            "F": "score < 40.0 or any critical finding with high/medium confidence",
        },
    }

    sev_counts = {s.value: 0 for s in Severity}
    conf_counts = {c.value: 0 for c in Confidence}

    if job_status in {"queued", "running"}:
        op_status = OperationalStatus(job_status)
        scope = AnalysisScopeSummary(operational_status=op_status)
        return QualityEvaluation(
            grade=QualityGrade.NOT_RATED,
            not_rated_reason=f"Analysis is currently {job_status}.",
            explanation=f"Not rated because the analysis job is {job_status}.",
            severity_counts=sev_counts,
            confidence_counts=conf_counts,
            scope=scope,
            criteria=criteria_doc,
        )

    if job_status == "failed" or report is None:
        reason = f"Analysis failed: {job_error}" if job_error else "Analysis failed or produced no report."
        scope = AnalysisScopeSummary(operational_status=OperationalStatus.FAILED)
        return QualityEvaluation(
            grade=QualityGrade.NOT_RATED,
            not_rated_reason=reason,
            explanation="Not rated because the analysis failed before producing complete evidence.",
            severity_counts=sev_counts,
            confidence_counts=conf_counts,
            scope=scope,
            criteria=criteria_doc,
        )

    truncation_warnings = _extract_truncation_warnings(report.warnings)
    op_status = OperationalStatus(report.status)
    is_complete = report.status == "completed" and not truncation_warnings
    has_scope = len(report.files_analyzed) > 0 and len(report.modules_executed) > 0

    vuln_count = 0
    for finding in report.findings:
        sev_counts[finding.severity.value] = sev_counts.get(finding.severity.value, 0) + 1
        conf_counts[finding.confidence.value] = conf_counts.get(finding.confidence.value, 0) + 1
        if is_vulnerability_finding(finding):
            vuln_count += 1
    bug_count = max(0, len(report.findings) - vuln_count)

    scope = AnalysisScopeSummary(
        operational_status=op_status,
        files_analyzed_count=len(report.files_analyzed),
        files_analyzed=list(report.files_analyzed),
        modules_executed=list(report.modules_executed),
        is_complete=is_complete,
        has_sufficient_evidence=is_complete and has_scope,
        truncation_warnings=truncation_warnings,
        warning_count=len(report.warnings),
    )

    if report.status == "incomplete" or truncation_warnings:
        detail = truncation_warnings[0] if truncation_warnings else "Analysis report status is incomplete."
        return QualityEvaluation(
            grade=QualityGrade.NOT_RATED,
            not_rated_reason=f"Analysis incomplete ({detail}). Quality grade is withheld when scope is truncated or partial.",
            explanation="Not rated because analysis was incomplete; rating partial scope could mask defects.",
            severity_counts=sev_counts,
            confidence_counts=conf_counts,
            vulnerability_count=vuln_count,
            bug_count=bug_count,
            scope=scope,
            criteria=criteria_doc,
        )

    if report.status == "empty_diff" or not report.files_analyzed:
        return QualityEvaluation(
            grade=QualityGrade.NOT_RATED,
            not_rated_reason="No reviewable files were analyzed in the target scope (empty diff).",
            explanation="Not rated because zero reviewable source files were present in the analyzed scope.",
            severity_counts=sev_counts,
            confidence_counts=conf_counts,
            vulnerability_count=vuln_count,
            bug_count=bug_count,
            scope=scope,
            criteria=criteria_doc,
        )

    if not report.modules_executed:
        return QualityEvaluation(
            grade=QualityGrade.NOT_RATED,
            not_rated_reason="No analysis modules were executed.",
            explanation="Not rated because no analysis modules ran on the target scope.",
            severity_counts=sev_counts,
            confidence_counts=conf_counts,
            vulnerability_count=vuln_count,
            bug_count=bug_count,
            scope=scope,
            criteria=criteria_doc,
        )

    evidence_items: list[FindingPenaltyEvidence] = []
    total_penalty = 0.0

    for finding in report.findings:
        base_pen = SEVERITY_PENALTY[finding.severity]
        conf_mult = CONFIDENCE_WEIGHT[finding.confidence]
        eff_pen = round(base_pen * conf_mult, 2)
        total_penalty = round(total_penalty + eff_pen, 2)
        evidence_items.append(
            FindingPenaltyEvidence(
                finding_id=finding.id,
                stable_fingerprint=compute_stable_finding_fingerprint(finding),
                file_path=finding.file_path,
                start_line=finding.line_range.start_line,
                end_line=finding.line_range.end_line,
                severity=finding.severity,
                confidence=finding.confidence,
                category=finding.category.value,
                base_penalty=base_pen,
                confidence_multiplier=conf_mult,
                effective_penalty=eff_pen,
                evidence_excerpt=finding.evidence[:200],
            )
        )

    score = max(0.0, round(100.0 - total_penalty, 2))

    has_blocking_critical = any(
        f.severity == Severity.CRITICAL and f.confidence in {Confidence.HIGH, Confidence.MEDIUM}
        for f in report.findings
    )
    has_any_critical = sev_counts[Severity.CRITICAL.value] > 0
    has_any_high = sev_counts[Severity.HIGH.value] > 0

    if has_blocking_critical or score < 40.0:
        grade = QualityGrade.F
    elif score < 60.0 or has_any_critical:
        grade = QualityGrade.D
    elif score < 75.0:
        grade = QualityGrade.C
    elif score < 90.0 or has_any_high:
        grade = QualityGrade.B
    else:
        grade = QualityGrade.A

    if not report.findings:
        explanation = (
            f"Grade {grade.value} (100.0/100): 0 findings detected across "
            f"{len(report.files_analyzed)} analyzed file(s)."
        )
    else:
        cap_note = ""
        if has_blocking_critical and score >= 40.0:
            cap_note = " (capped at F due to critical-severity finding)"
        elif has_any_critical and score >= 60.0:
            cap_note = " (capped at D due to critical-severity finding)"
        elif has_any_high and score >= 90.0:
            cap_note = " (capped at B due to high-severity finding)"
        explanation = (
            f"Grade {grade.value} ({score:.1f}/100, penalty -{total_penalty:.1f}){cap_note}: "
            f"{len(report.findings)} finding(s) across {len(report.files_analyzed)} analyzed file(s)."
        )

    return QualityEvaluation(
        grade=grade,
        score=score,
        total_penalty=total_penalty,
        explanation=explanation,
        severity_counts=sev_counts,
        confidence_counts=conf_counts,
        vulnerability_count=vuln_count,
        bug_count=bug_count,
        scope=scope,
        criteria=criteria_doc,
        evidence_used=evidence_items,
    )


def evaluate_quality_gate(
    evaluation: QualityEvaluation,
    config: QualityGateConfig | None = None,
    *,
    new_findings: list[ComparedFindingItem] | None = None,
    uncertain_findings: list[ComparedFindingItem] | None = None,
) -> QualityGateResult:
    """Evaluate objective Quality Gate criteria against a QualityEvaluation and optional PR delta."""
    gate_cfg = config or QualityGateConfig()
    conditions: list[QualityGateConditionResult] = []
    reasons: list[str] = []

    if evaluation.grade == QualityGrade.NOT_RATED:
        reason = evaluation.not_rated_reason or "Quality grade is NOT_RATED due to insufficient evidence."
        conditions.append(
            QualityGateConditionResult(
                criterion="analysis_completeness",
                passed=False,
                actual=evaluation.scope.operational_status.value,
                threshold="completed with sufficient scope",
                reason=reason,
            )
        )
        return QualityGateResult(
            status=QualityGateGateStatus_INCONCLUSIVE,
            passed=False,
            reasons=[reason],
            conditions=conditions,
            config=gate_cfg,
        )

    # 1. Minimum grade check
    min_grade_enum = QualityGrade(gate_cfg.min_grade)
    grade_ok = _GRADE_ORDER[evaluation.grade] >= _GRADE_ORDER[min_grade_enum]
    grade_reason = (
        f"Quality grade {evaluation.grade.value} meets minimum required grade {gate_cfg.min_grade}."
        if grade_ok
        else f"Quality grade {evaluation.grade.value} is below minimum required grade {gate_cfg.min_grade}."
    )
    conditions.append(
        QualityGateConditionResult(
            criterion="minimum_grade",
            passed=grade_ok,
            actual=evaluation.grade.value,
            threshold=f">= {gate_cfg.min_grade}",
            reason=grade_reason,
        )
    )
    if not grade_ok:
        reasons.append(grade_reason)

    if new_findings is not None:
        # PR / Delta mode: evaluate introduced findings
        new_crit = sum(1 for item in new_findings if item.finding.severity == Severity.CRITICAL)
        crit_ok = new_crit <= gate_cfg.max_new_critical_findings
        crit_reason = (
            f"Introduced critical findings ({new_crit}) within threshold ({gate_cfg.max_new_critical_findings})."
            if crit_ok
            else f"Introduced {new_crit} new critical finding(s) (maximum allowed: {gate_cfg.max_new_critical_findings})."
        )
        conditions.append(
            QualityGateConditionResult(
                criterion="max_new_critical_findings",
                passed=crit_ok,
                actual=str(new_crit),
                threshold=f"<= {gate_cfg.max_new_critical_findings}",
                reason=crit_reason,
            )
        )
        if not crit_ok:
            reasons.append(crit_reason)

        new_high = sum(1 for item in new_findings if item.finding.severity == Severity.HIGH)
        high_ok = new_high <= gate_cfg.max_new_high_findings
        high_reason = (
            f"Introduced high findings ({new_high}) within threshold ({gate_cfg.max_new_high_findings})."
            if high_ok
            else f"Introduced {new_high} new high finding(s) (maximum allowed: {gate_cfg.max_new_high_findings})."
        )
        conditions.append(
            QualityGateConditionResult(
                criterion="max_new_high_findings",
                passed=high_ok,
                actual=str(new_high),
                threshold=f"<= {gate_cfg.max_new_high_findings}",
                reason=high_reason,
            )
        )
        if not high_ok:
            reasons.append(high_reason)

        total_new = len(new_findings)
        total_ok = total_new <= gate_cfg.max_total_new_findings
        total_reason = (
            f"Total new findings ({total_new}) within threshold ({gate_cfg.max_total_new_findings})."
            if total_ok
            else f"Introduced {total_new} total new finding(s) (maximum allowed: {gate_cfg.max_total_new_findings})."
        )
        conditions.append(
            QualityGateConditionResult(
                criterion="max_total_new_findings",
                passed=total_ok,
                actual=str(total_new),
                threshold=f"<= {gate_cfg.max_total_new_findings}",
                reason=total_reason,
            )
        )
        if not total_ok:
            reasons.append(total_reason)

        if uncertain_findings:
            unc_crit = sum(
                1 for item in uncertain_findings if item.finding.severity in {Severity.CRITICAL, Severity.HIGH}
            )
            if unc_crit > 0:
                unc_reason = (
                    f"{unc_crit} high/critical finding(s) have uncertain baseline lineage and require review."
                )
                conditions.append(
                    QualityGateConditionResult(
                        criterion="uncertain_high_or_critical_findings",
                        passed=False,
                        actual=str(unc_crit),
                        threshold="0",
                        reason=unc_reason,
                    )
                )
                reasons.append(unc_reason)
    else:
        # Standalone analysis mode
        crit_count = evaluation.severity_counts.get(Severity.CRITICAL.value, 0)
        crit_ok = crit_count <= gate_cfg.max_critical_findings
        crit_reason = (
            f"Critical findings ({crit_count}) within threshold ({gate_cfg.max_critical_findings})."
            if crit_ok
            else f"Detected {crit_count} critical finding(s) (maximum allowed: {gate_cfg.max_critical_findings})."
        )
        conditions.append(
            QualityGateConditionResult(
                criterion="max_critical_findings",
                passed=crit_ok,
                actual=str(crit_count),
                threshold=f"<= {gate_cfg.max_critical_findings}",
                reason=crit_reason,
            )
        )
        if not crit_ok:
            reasons.append(crit_reason)

        high_count = evaluation.severity_counts.get(Severity.HIGH.value, 0)
        high_ok = high_count <= gate_cfg.max_high_findings
        high_reason = (
            f"High findings ({high_count}) within threshold ({gate_cfg.max_high_findings})."
            if high_ok
            else f"Detected {high_count} high finding(s) (maximum allowed: {gate_cfg.max_high_findings})."
        )
        conditions.append(
            QualityGateConditionResult(
                criterion="max_high_findings",
                passed=high_ok,
                actual=str(high_count),
                threshold=f"<= {gate_cfg.max_high_findings}",
                reason=high_reason,
            )
        )
        if not high_ok:
            reasons.append(high_reason)

    passed = all(c.passed for c in conditions)
    if passed:
        reasons = ["All Quality Gate conditions passed."]
    return QualityGateResult(
        status=QualityGateStatus.PASSED if passed else QualityGateStatus.FAILED,
        passed=passed,
        reasons=reasons,
        conditions=conditions,
        config=gate_cfg,
    )


QualityGateGateStatus_INCONCLUSIVE = QualityGateStatus.INCONCLUSIVE


def _match_finding_against_baseline(
    candidate: Finding,
    baseline_findings: list[Finding],
    matched_baseline_ids: set[str],
) -> tuple[FindingDeltaClassification, Finding | None, float, str]:
    """Compare a candidate finding against unmatched baseline findings by stable identity and evidence."""
    cand_fp = compute_stable_finding_fingerprint(candidate)

    # 1. Exact ID or exact line-drift-tolerant fingerprint match
    for base in baseline_findings:
        if base.id in matched_baseline_ids:
            continue
        if candidate.id == base.id:
            return FindingDeltaClassification.EXISTING, base, 1.0, "identical_finding_id"
        if cand_fp == compute_stable_finding_fingerprint(base):
            return FindingDeltaClassification.EXISTING, base, 0.98, "identical_stable_fingerprint"

    # 2. Semantic duplicate within broader line shift (e.g. code moved within file)
    best_match: Finding | None = None
    best_score = 0.0
    best_reason = ""
    best_is_exact_dup = False

    ev_cand = normalize_code_evidence(candidate.evidence)
    tokens_cand = extract_code_tokens(ev_cand)
    concepts_cand = extract_defect_concepts(candidate.title, candidate.description, ev_cand)

    for base in baseline_findings:
        if base.id in matched_baseline_ids:
            continue
        if candidate.file_path != base.file_path or candidate.module_id != base.module_id:
            continue

        is_dup, sim_score, reason = are_findings_duplicates(candidate, base, max_line_proximity=25)
        if is_dup and sim_score > best_score:
            best_match = base
            best_score = sim_score
            best_reason = reason
            best_is_exact_dup = True
            continue

        # Check for ambiguous/uncertain lineage (same file + compatible category, partial evidence overlap or distant shift)
        if not best_is_exact_dup and are_categories_compatible(candidate.category, base.category):
            ev_base = normalize_code_evidence(base.evidence)
            ev_jacc = token_jaccard(tokens_cand, extract_code_tokens(ev_base))
            concepts_base = extract_defect_concepts(base.title, base.description, ev_base)
            shared_concepts = bool(concepts_cand and concepts_base and (concepts_cand & concepts_base))
            line_dist = abs(candidate.line_range.start_line - base.line_range.start_line)
            if (ev_jacc >= 0.45 and line_dist <= 50) or (shared_concepts and ev_jacc >= 0.35):
                ambig_score = round(max(ev_jacc, 0.55 if shared_concepts else 0.45), 4)
                if ambig_score > best_score:
                    best_match = base
                    best_score = ambig_score
                    best_reason = "ambiguous_shifted_or_modified_evidence"

    if best_match is not None:
        if best_is_exact_dup:
            return FindingDeltaClassification.EXISTING, best_match, best_score, best_reason
        return FindingDeltaClassification.UNCERTAIN, best_match, best_score, best_reason

    return FindingDeltaClassification.NEW, None, 0.0, "no_matching_baseline_finding"


def compare_pull_request(
    base_report: AnalysisReport | None,
    pr_report: AnalysisReport | None,
    *,
    base_job_status: str | None = None,
    base_job_error: str | None = None,
    pr_job_status: str | None = None,
    pr_job_error: str | None = None,
    gate_config: QualityGateConfig | None = None,
    base_revision: str | None = None,
    head_revision: str | None = None,
) -> PullRequestComparisonResult:
    """Compare baseline branch analysis and proposed PR analysis by stable finding identity and evidence.

    Calculates:
    - Separate baseline quality (`base_evaluation`)
    - Separate PR change quality (`pr_evaluation`), rated strictly on newly introduced / uncertain findings
      in the PR's analyzed scope (so existing legacy debt in the baseline does not unfairly tank a clean PR,
      while a PR introducing a critical defect into a Grade B project receives Grade F).
    - Finding classification (`new`, `existing`, `resolved`, `uncertain`)
    - Objective Quality Gate verdict (`PASSED`, `FAILED`, or `INCONCLUSIVE` when PR analysis is incomplete/failed).
    """
    cfg = gate_config or QualityGateConfig()
    base_eval = evaluate_quality(base_report, job_status=base_job_status, job_error=base_job_error)
    raw_pr_eval = evaluate_quality(pr_report, job_status=pr_job_status, job_error=pr_job_error)

    # If PR analysis itself is NOT_RATED (incomplete, failed, empty_diff), do not fabricate delta grades
    if raw_pr_eval.grade == QualityGrade.NOT_RATED or pr_report is None:
        inconclusive_gate = evaluate_quality_gate(raw_pr_eval, cfg)
        return PullRequestComparisonResult(
            base_revision=base_revision or (base_report.base_revision if base_report else None),
            head_revision=head_revision or (pr_report.base_revision if pr_report else None),
            base_evaluation=base_eval,
            pr_evaluation=raw_pr_eval,
            quality_gate=inconclusive_gate,
            grade_delta=f"{base_eval.grade.value} -> {raw_pr_eval.grade.value}",
            score_delta=None,
            counts={"new": 0, "existing": 0, "resolved": 0, "uncertain": 0},
            summary=raw_pr_eval.not_rated_reason or "PR analysis is incomplete or not rated; gate is inconclusive.",
        )

    baseline_findings = list(base_report.findings) if base_report is not None else []
    pr_findings = list(pr_report.findings)

    matched_baseline_ids: set[str] = set()
    new_items: list[ComparedFindingItem] = []
    existing_items: list[ComparedFindingItem] = []
    uncertain_items: list[ComparedFindingItem] = []
    resolved_items: list[ComparedFindingItem] = []

    for cand in pr_findings:
        classification, matched_base, sim_score, reason = _match_finding_against_baseline(
            cand, baseline_findings, matched_baseline_ids
        )
        fp = compute_stable_finding_fingerprint(cand)
        if matched_base is not None:
            matched_baseline_ids.add(matched_base.id)
        item = ComparedFindingItem(
            classification=classification,
            finding=cand,
            stable_fingerprint=fp,
            matched_baseline_finding_id=matched_base.id if matched_base else None,
            similarity_score=sim_score,
            reason=reason,
        )
        if classification == FindingDeltaClassification.NEW:
            new_items.append(item)
        elif classification == FindingDeltaClassification.EXISTING:
            existing_items.append(item)
        else:
            uncertain_items.append(item)

    pr_analyzed_files = set(pr_report.files_analyzed)
    for base_f in baseline_findings:
        if base_f.id in matched_baseline_ids:
            continue
        # If the baseline finding was in a file analyzed by the PR (or if base had full scope) and is no longer present
        if not pr_analyzed_files or base_f.file_path in pr_analyzed_files:
            resolved_items.append(
                ComparedFindingItem(
                    classification=FindingDeltaClassification.RESOLVED,
                    finding=base_f,
                    stable_fingerprint=compute_stable_finding_fingerprint(base_f),
                    matched_baseline_finding_id=base_f.id,
                    similarity_score=1.0,
                    reason="absent_in_pr_analyzed_scope",
                )
            )

    # Evaluate PR quality specifically on delta findings (new + uncertain) within the PR scope
    delta_findings = [item.finding for item in [*new_items, *uncertain_items]]
    pr_delta_report = pr_report.model_copy(update={"findings": delta_findings})
    pr_eval = evaluate_quality(pr_delta_report, job_status=pr_job_status, job_error=pr_job_error)

    gate_result = evaluate_quality_gate(
        pr_eval,
        cfg,
        new_findings=new_items,
        uncertain_findings=uncertain_items,
    )

    def _with_gate_metadata(items: list[ComparedFindingItem]) -> list[ComparedFindingItem]:
        return [
            item.model_copy(
                update={
                    "is_vulnerability": is_vulnerability_finding(item.finding),
                    "addressed_gate_conditions": addressed_gate_conditions(
                        item.finding,
                        gate_result,
                        classification=item.classification.value,
                    ),
                }
            )
            for item in items
        ]

    new_items = _with_gate_metadata(new_items)
    existing_items = _with_gate_metadata(existing_items)
    resolved_items = _with_gate_metadata(resolved_items)
    uncertain_items = _with_gate_metadata(uncertain_items)

    score_delta: float | None = None
    if base_eval.score is not None and pr_eval.score is not None:
        score_delta = round(pr_eval.score - base_eval.score, 2)

    grade_delta = f"{base_eval.grade.value} -> {pr_eval.grade.value}"
    counts = {
        "new": len(new_items),
        "existing": len(existing_items),
        "resolved": len(resolved_items),
        "uncertain": len(uncertain_items),
    }

    if gate_result.status == QualityGateStatus.PASSED:
        summary = (
            f"Quality Gate PASSED ({grade_delta}): {len(new_items)} new, "
            f"{len(resolved_items)} resolved, {len(existing_items)} existing finding(s)."
        )
    elif gate_result.status == QualityGateStatus.FAILED:
        summary = (
            f"Quality Gate FAILED ({grade_delta}): {'; '.join(gate_result.reasons)}"
        )
    else:
        summary = f"Quality Gate INCONCLUSIVE ({grade_delta}): {'; '.join(gate_result.reasons)}"

    return PullRequestComparisonResult(
        base_revision=base_revision or (base_report.base_revision if base_report else None),
        head_revision=head_revision or pr_report.base_revision,
        base_evaluation=base_eval,
        pr_evaluation=pr_eval,
        quality_gate=gate_result,
        grade_delta=grade_delta,
        score_delta=score_delta,
        counts=counts,
        new_findings=new_items,
        existing_findings=existing_items,
        resolved_findings=resolved_items,
        uncertain_findings=uncertain_items,
        summary=summary,
    )


def build_github_check_contract(
    comparison: PullRequestComparisonResult,
    *,
    head_sha: str,
) -> GitHubCheckRunContract:
    """Build a deterministic GitHub Checks API contract from a PullRequestComparisonResult."""
    conclusion_map: dict[QualityGateStatus, Literal["success", "failure", "neutral"]] = {
        QualityGateStatus.PASSED: "success",
        QualityGateStatus.FAILED: "failure",
        QualityGateStatus.INCONCLUSIVE: "neutral",
    }
    annotations: list[GitHubCheckAnnotationContract] = []
    for item in [*comparison.new_findings, *comparison.uncertain_findings]:
        finding = item.finding
        level: Literal["notice", "warning", "failure"] = (
            "failure"
            if finding.severity in {Severity.CRITICAL, Severity.HIGH}
            else ("warning" if finding.severity == Severity.MEDIUM else "notice")
        )
        annotations.append(
            GitHubCheckAnnotationContract(
                path=finding.file_path,
                start_line=finding.line_range.start_line,
                end_line=finding.line_range.end_line,
                annotation_level=level,
                title=f"[{item.classification.value.upper()}] {finding.title}",
                message=finding.description,
                raw_details=finding.evidence,
            )
        )

    title = (
        f"Gate {comparison.quality_gate.status.value} · "
        f"PR Grade {comparison.pr_evaluation.grade.value} (Base {comparison.base_evaluation.grade.value})"
    )
    text_lines = [
        f"Formula Version: {comparison.pr_evaluation.formula_version}",
        f"Comparison Version: {comparison.comparison_version}",
        f"Grade Delta: {comparison.grade_delta}",
        f"New: {comparison.counts.get('new', 0)} | Resolved: {comparison.counts.get('resolved', 0)} | "
        f"Existing: {comparison.counts.get('existing', 0)} | Uncertain: {comparison.counts.get('uncertain', 0)}",
    ]
    for reason in comparison.quality_gate.reasons:
        text_lines.append(f"- {reason}")

    return GitHubCheckRunContract(
        head_sha=head_sha,
        status="completed",
        conclusion=conclusion_map[comparison.quality_gate.status],
        title=title,
        summary=comparison.summary,
        text="\n".join(text_lines),
        annotations=annotations,
    )
