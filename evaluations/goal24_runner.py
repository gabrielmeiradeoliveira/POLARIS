"""Offline causal detection runner for the frozen GOAL 24 catalog.

The catalog's behavioral oracles are exercised separately. This module adapts
its before/after source pairs to the same public evaluation pipeline used by
production-like fixtures and returns a global and per-difficulty scorecard.
"""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass

from evaluations.fixtures.goal24_rc1.catalog import CATALOG, Scenario

from polaris.core.models import FindingCategory, LineRange, Severity
from polaris.evaluation.models import ChangeType, EvaluationFixture, EvaluationSummary, ExpectedFindingSpec
from polaris.evaluation.runner import evaluate_corpus
from polaris.providers.fake import FakeProvider


@dataclass(frozen=True)
class Goal24BenchmarkResult:
    """A reproducible aggregate and N1/N2/N3 breakdown."""

    catalog_sha256: str
    overall: EvaluationSummary
    by_difficulty: dict[str, EvaluationSummary]


def catalog_sha256(cases: tuple[Scenario, ...] = CATALOG) -> str:
    """Return a stable digest of the catalog's executable benchmark inputs."""
    serialized = "\n".join(
        "\x1f".join(
            (
                case.id,
                case.difficulty,
                case.kind,
                case.category,
                case.before,
                case.after,
                case.contract,
                ",".join(case.files),
                str(case.oracle_input),
                str(case.finding_line),
            )
        )
        for case in cases
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def fixture_for(case: Scenario) -> EvaluationFixture:
    """Adapt one causal catalog case to an end-to-end evaluation fixture."""
    path = f"goal24/{case.id}.py"
    diff = "".join(
        difflib.unified_diff(
            case.before.splitlines(keepends=True),
            case.after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    expected = (
        [
            ExpectedFindingSpec(
                file_path=path,
                line_range=LineRange(start_line=case.finding_line, end_line=case.finding_line),
                category=FindingCategory.BOUNDARY_CONDITION,
                severity=Severity.MEDIUM,
            )
        ]
        if case.kind == "positive"
        else []
    )
    return EvaluationFixture(
        case_id=case.id,
        description=case.contract,
        diff_text=f"diff --git a/{path} b/{path}\n{diff}",
        file_contents={path: case.after},
        expected_findings=expected,
        is_clean=case.kind == "negative",
        provenance="documented_verified",
        change_type=(ChangeType.DEFECT_INTRODUCTION if case.kind == "positive" else ChangeType.CLEAN_UNRELATED),
    )


def run_goal24_catalog(cases: tuple[Scenario, ...] = CATALOG) -> Goal24BenchmarkResult:
    """Run deterministic end-to-end scoring with controlled empty provider output."""
    fixtures = [fixture_for(case) for case in cases]
    overall = evaluate_corpus(
        fixtures,
        provider=FakeProvider(scripted_responses=["{}"] * len(fixtures)),
        force_end_to_end=True,
        behavioral_delta_enabled=False,
    )
    by_difficulty: dict[str, EvaluationSummary] = {}
    for difficulty in ("N1", "N2", "N3"):
        level_cases = tuple(case for case in cases if case.difficulty == difficulty)
        level_fixtures = [fixture_for(case) for case in level_cases]
        by_difficulty[difficulty] = evaluate_corpus(
            level_fixtures,
            provider=FakeProvider(scripted_responses=["{}"] * len(level_fixtures)),
            force_end_to_end=True,
            behavioral_delta_enabled=False,
        )
    return Goal24BenchmarkResult(catalog_sha256(cases), overall, by_difficulty)
