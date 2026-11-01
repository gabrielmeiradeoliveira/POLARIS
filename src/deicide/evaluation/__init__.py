"""Evaluation framework for DEICIDE analysis quality, precision, recall, latency, and tokens."""

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
    "EvaluationFixture",
    "EvaluationSummary",
    "ExpectedFindingSpec",
    "FindingMatchDiagnostic",
    "RejectedCandidateDiagnostic",
    "UnmatchedExpectedDiagnostic",
    "UnmatchedFindingDiagnostic",
    "evaluate_case",
    "evaluate_corpus",
    "load_fixtures_from_file",
]
