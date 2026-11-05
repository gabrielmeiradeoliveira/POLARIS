"""Evaluation framework for DEICIDE analysis quality, precision, recall, latency, and tokens."""

from deicide.evaluation.history import (
    BenchmarkHistoryManifest,
    CorpusKind,
    FindingValidationRecord,
    ValidationOutcome,
    append_manifest,
    build_manifest,
    load_manifests,
    write_trend_reports,
)
from deicide.evaluation.models import (
    CaseDiagnostics,
    CaseEvaluationResult,
    EvaluationFixture,
    EvaluationSummary,
    ExpectedFindingSpec,
    FindingMatchDiagnostic,
    RejectedCandidateDiagnostic,
    UnmatchedExpectedDiagnostic,
    UnmatchedFindingDiagnostic,
)
from deicide.evaluation.runner import evaluate_case, evaluate_corpus, load_fixtures_from_file

__all__ = [
    "CaseDiagnostics",
    "CaseEvaluationResult",
    "BenchmarkHistoryManifest",
    "CorpusKind",
    "EvaluationFixture",
    "EvaluationSummary",
    "ExpectedFindingSpec",
    "FindingValidationRecord",
    "FindingMatchDiagnostic",
    "RejectedCandidateDiagnostic",
    "UnmatchedExpectedDiagnostic",
    "UnmatchedFindingDiagnostic",
    "ValidationOutcome",
    "append_manifest",
    "build_manifest",
    "evaluate_case",
    "evaluate_corpus",
    "load_fixtures_from_file",
    "load_manifests",
    "write_trend_reports",
]
