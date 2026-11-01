"""Data models for measuring DEICIDE finding quality, precision, recall, latency, and tokens."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from deicide.core.models import (
    CandidateFinding,
    Finding,
    FindingCategory,
    LineRange,
    Severity,
    TokenUsage,
)
from deicide.providers.base import ProviderAttempt


class ChangeType(StrEnum):
    """Semantic classification of code changes in benchmark fixtures."""

    DEFECT_INTRODUCTION = "defect_introduction"  # Buggy change that introduces a defect
    VULNERABLE_SNAPSHOT = "vulnerable_snapshot"  # Vulnerable pre-fix snapshot
    CLEAN_BUG_FIX = "clean_bug_fix"  # Clean change that fixes an existing defect
    CLEAN_UNRELATED = "clean_unrelated"  # Clean change unrelated to a defect


class ContextRequirement(StrEnum):
    """How much repository context is required to establish fixture ground truth."""

    DIFF_ONLY = "diff_only"
    CONTEXT_ASSISTED = "context_assisted"
    CONTEXT_REQUIRED = "context_required"


class NegativeChangeType(StrEnum):
    """Semantic classification for a clean evaluation fixture."""

    BEHAVIOR_PRESERVING = "behavior_preserving"
    CLEAN_BUG_FIX = "clean_bug_fix"


class GroundTruthVerificationStatus(StrEnum):
    """Independent confidence level for a real-world fixture's ground truth."""

    EXECUTABLE_VERIFIED = "EXECUTABLE_VERIFIED"
    DOCUMENTED_VERIFIED = "DOCUMENTED_VERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ExpectedFindingSpec(BaseModel):
    """Ground-truth expectation for a known correctness bug in an evaluation fixture.

    Category Alternatives and Matching Semantics:
    --------------------------------------------
    An expected defect specifies a primary `category` (e.g. `FindingCategory.CORRECTNESS`)
    and may optionally specify `allowed_categories` (or `alternative_categories`) to accommodate
    semantically equivalent classifications of the defect (such as `boundary_condition` for a
    division-by-zero or off-by-one error).

    Effect on TP, FP, and FN:
    - True Positive (TP): When an actual finding identifies the expected defect at the valid
      file/line location, and its category matches the primary or any allowed alternative category,
      it is matched as a True Positive.
    - False Positive (FP): If an actual finding's category is unrelated to the defect's allowed
      categories, or its file/line location does not match, it cannot match the expected defect
      and is scored as a False Positive.
    - False Negative (FN): If no actual finding matches the expected defect under the allowed
      categories and location constraints, the expected defect is scored as a False Negative.
    - Strict 1-to-1 Matching: Exactly one actual finding can claim an expected defect. If multiple
      actual findings match the same expected defect, the first match claims TP and subsequent
      competing findings are scored as False Positives.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str
    line_range: LineRange
    category: FindingCategory | None = None
    alternative_categories: list[FindingCategory] = Field(default_factory=list)
    allowed_categories: list[FindingCategory] = Field(default_factory=list)
    severity: Severity | None = None
    evidence: str | None = None

    @property
    def acceptable_categories(self) -> set[FindingCategory] | None:
        """Set of acceptable finding categories, or None if category matching is unconstrained."""
        cats: set[FindingCategory] = set()
        if self.category is not None:
            cats.add(self.category)
        if self.alternative_categories:
            cats.update(self.alternative_categories)
        if self.allowed_categories:
            cats.update(self.allowed_categories)
        return cats if cats else None

    def category_matches(self, actual_category: FindingCategory) -> bool:
        """Check whether actual finding category matches expected or allowed alternative categories."""
        accepted = self.acceptable_categories
        if accepted is None:
            return True
        return actual_category in accepted

    def location_matches(self, actual: Finding) -> bool:
        """Check whether a finding points to this expected defect's source location."""
        return actual.file_path == self.file_path and actual.line_range.overlaps_or_adjacent(
            self.line_range, tolerance=2
        )

    def matches(self, actual: Finding, strict_severity: bool = False) -> bool:
        """Check if an actual finding identifies this expected bug."""
        if not self.location_matches(actual):
            return False
        if not self.category_matches(actual.category):
            return False
        if not strict_severity or self.severity is None:
            return True
        return actual.severity == self.severity

    def severity_matches(self, actual: Finding) -> bool:
        """Check whether actual finding severity exactly matches expected severity."""
        return self.severity is None or actual.severity == self.severity


class RejectedCandidateDiagnostic(BaseModel):
    """Diagnostic details for a candidate finding rejected during validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str
    line_range: LineRange
    category: FindingCategory
    severity: Severity
    title: str
    reason: str
    rejection_code: str | None = None


class FindingMatchDiagnostic(BaseModel):
    """Diagnostic details for a finding that successfully matched an expected defect."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    file_path: str
    line_range: LineRange
    category: FindingCategory
    severity: Severity
    title: str
    expected_file_path: str
    expected_line_range: LineRange
    expected_category: FindingCategory | None = None
    expected_allowed_categories: list[FindingCategory] = Field(default_factory=list)
    severity_match: bool = True


class UnmatchedFindingDiagnostic(BaseModel):
    """Diagnostic details for an actual finding that did not match any expected defect."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    file_path: str
    line_range: LineRange
    category: FindingCategory
    severity: Severity
    title: str
    reasons: list[str] = Field(default_factory=list)
    reason: str = Field(default="")


class UnmatchedExpectedDiagnostic(BaseModel):
    """Diagnostic details for an expected defect that was not detected or matched."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str
    line_range: LineRange
    category: FindingCategory | None = None
    allowed_categories: list[FindingCategory] = Field(default_factory=list)
    severity: Severity | None = None
    reason: str = Field(default="")


class CategoryMismatchDiagnostic(BaseModel):
    """A location-matched finding whose category is not accepted by the fixture."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    file_path: str
    line_range: LineRange
    category: FindingCategory
    title: str
    expected_file_path: str
    expected_line_range: LineRange
    expected_category: FindingCategory | None = None
    expected_allowed_categories: list[FindingCategory] = Field(default_factory=list)


class CaseDiagnostics(BaseModel):
    """Finding-level evaluation diagnostics for a completed benchmark case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_findings: list[CandidateFinding] = Field(default_factory=list)
    validated_findings: list[Finding] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidateDiagnostic] = Field(default_factory=list)
    matched_findings: list[FindingMatchDiagnostic] = Field(default_factory=list)
    category_mismatches: list[CategoryMismatchDiagnostic] = Field(default_factory=list)
    unmatched_findings: list[UnmatchedFindingDiagnostic] = Field(default_factory=list)
    unmatched_expected: list[UnmatchedExpectedDiagnostic] = Field(default_factory=list)


class ContextSelectionDiagnostic(BaseModel):
    """Bounded context-selection metadata safe to persist for experiments."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    selected_files: int = Field(default=0, ge=0)
    selected_snippets: int = Field(default=0, ge=0)
    omitted_snippets: int = Field(default=0, ge=0)
    estimated_tokens: int = Field(default=0, ge=0)
    max_allowed_tokens: int = Field(default=0, ge=0)
    behavioral_deltas: int = Field(default=0, ge=0)
    truncated: bool = False
    diagnostics: list[str] = Field(default_factory=list)


class CaseObservability(BaseModel):
    """Optional, hash-only evaluation telemetry; never contains prompt or response bodies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    model: str
    attempts: list[ProviderAttempt] | None = None
    context: ContextSelectionDiagnostic | None = None


class EvaluationFixture(BaseModel):
    """Single curated evaluation test case containing a diff, context, and expected findings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    description: str
    diff_text: str
    file_contents: dict[str, str] = Field(default_factory=dict)
    expected_findings: list[ExpectedFindingSpec] = Field(default_factory=list)
    candidate_findings: list[CandidateFinding] = Field(default_factory=list)
    supplementary_snippets: list[dict[str, Any]] = Field(default_factory=list)
    repository: str | None = None
    commit_id: str | None = None
    is_clean: bool = False
    fix_reference: str | None = None
    provenance: str | None = None
    change_type: ChangeType | None = None
    suitable_for_live_benchmark: bool | None = None
    context_rationale: str | None = None
    context_requirement: ContextRequirement | None = None
    negative_change_type: NegativeChangeType | None = None
    parent_commit_id: str | None = None
    fix_commit_id: str | None = None
    verification_status: GroundTruthVerificationStatus | None = None
    independent_evidence: list[str] = Field(default_factory=list)
    reproduction_instructions: str | None = None
    known_limitations: list[str] = Field(default_factory=list)

    @property
    def resolved_provenance(self) -> str:
        """Categorize provenance into fully_verified, reference_modeled, or unverified."""
        if self.verification_status == GroundTruthVerificationStatus.EXECUTABLE_VERIFIED:
            return "fully_verified"
        if self.verification_status == GroundTruthVerificationStatus.DOCUMENTED_VERIFIED:
            return "documented_verified"
        if self.verification_status == GroundTruthVerificationStatus.INSUFFICIENT_EVIDENCE:
            return "unverified"
        if self.provenance:
            return self.provenance
        if self.commit_id in {"a76d89b", "ae580a6", "cfc826d"}:
            return "fully_verified"
        if self.is_clean:
            return "reference_modeled"
        return "fully_verified"

    @property
    def resolved_change_type(self) -> ChangeType:
        """Resolve the semantic change type."""
        if self.change_type is not None:
            return self.change_type
        if self.is_clean or not self.expected_findings:
            return ChangeType.CLEAN_UNRELATED
        return ChangeType.DEFECT_INTRODUCTION

    @property
    def is_suitable_for_live_benchmark(self) -> bool:
        """Determine whether the fixture is suitable for live defect detection benchmarking.

        A change that fixes an existing defect contains the fix rather than the bug,
        and cannot be used to measure true positive defect detection.
        """
        if self.suitable_for_live_benchmark is not None:
            return self.suitable_for_live_benchmark
        return self.resolved_change_type not in (ChangeType.CLEAN_BUG_FIX, ChangeType.VULNERABLE_SNAPSHOT)


class CaseEvaluationResult(BaseModel):
    """Evaluation outcome for a single fixture case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    true_positives: int = Field(default=0, ge=0)
    false_positives: int = Field(default=0, ge=0)
    false_negatives: int = Field(default=0, ge=0)
    category_mismatch_detections: int = Field(default=0, ge=0)
    undetected_expected_defects: int = Field(default=0, ge=0)
    duplicates_reduced: int = Field(default=0, ge=0)
    legitimate_rejected: int = Field(default=0, ge=0)
    severity_mismatches: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    actual_findings: list[Finding] = Field(default_factory=list)
    status: str = Field(default="completed")
    operational_state: str = Field(default="completed")
    error: str | None = Field(default=None)
    error_category: str | None = Field(default=None)
    http_status: int | None = Field(default=None)
    retries_attempted: int = Field(default=0, ge=0)
    provenance: str = Field(default="fully_verified")
    change_type: ChangeType | str | None = Field(default=None)
    diagnostics: CaseDiagnostics | None = Field(default=None)
    observability: CaseObservability | None = Field(default=None)


class EvaluationSummary(BaseModel):
    """Aggregated evaluation metrics across a curated fixture corpus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_size: int = Field(..., ge=0)
    positive_cases: int = Field(..., ge=0)
    negative_cases: int = Field(..., ge=0)
    successful_cases: int = Field(default=0, ge=0)
    timeout_cases: int = Field(default=0, ge=0)
    error_cases: int = Field(default=0, ge=0)
    unassessed_cases: int = Field(default=0, ge=0)
    failed_cases: int = Field(default=0, ge=0)
    api_failed_cases: int = Field(default=0, ge=0)
    budget_exhausted_cases: int = Field(default=0, ge=0)
    skipped_cases: int = Field(default=0, ge=0)
    true_positives: int = Field(..., ge=0)
    false_positives: int = Field(..., ge=0)
    false_negatives: int = Field(..., ge=0)
    category_mismatch_detections: int = Field(default=0, ge=0)
    undetected_expected_defects: int = Field(default=0, ge=0)
    detection_precision: float | None = Field(default=None, ge=0.0, le=1.0)
    detection_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    detection_precision_ci_lower: float | None = Field(default=None, ge=0.0, le=1.0)
    detection_precision_ci_upper: float | None = Field(default=None, ge=0.0, le=1.0)
    detection_recall_ci_lower: float | None = Field(default=None, ge=0.0, le=1.0)
    detection_recall_ci_upper: float | None = Field(default=None, ge=0.0, le=1.0)
    precision: float | None = Field(default=None, ge=0.0, le=1.0)
    recall: float | None = Field(default=None, ge=0.0, le=1.0)
    precision_ci_lower: float | None = Field(default=None, ge=0.0, le=1.0)
    precision_ci_upper: float | None = Field(default=None, ge=0.0, le=1.0)
    recall_ci_lower: float | None = Field(default=None, ge=0.0, le=1.0)
    recall_ci_upper: float | None = Field(default=None, ge=0.0, le=1.0)
    f1_score: float | None = Field(default=None, ge=0.0, le=1.0)
    false_positive_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    completion_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    duplicates_reduced: int = Field(default=0, ge=0)
    legitimate_rejected: int = Field(default=0, ge=0)
    severity_mismatches: int = Field(default=0, ge=0)
    evaluation_mode: str = Field(default="post_processing")
    total_latency_ms: int = Field(..., ge=0)
    average_latency_ms: float = Field(..., ge=0.0)
    usage: TokenUsage
    verified_cases: int = Field(default=0, ge=0)
    documented_verified_cases: int = Field(default=0, ge=0)
    reference_modeled_cases: int = Field(default=0, ge=0)
    unverified_cases: int = Field(default=0, ge=0)
    budget_exhausted: bool = Field(default=False)
    max_cases_applied: int | None = Field(default=None)
    case_results: list[CaseEvaluationResult] = Field(default_factory=list)
