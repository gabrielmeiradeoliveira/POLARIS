"""Causal and end-to-end runner for the post-recovery GOAL24 holdout."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass

from evaluations.fixtures.goal24_holdout.catalog import CASES, HoldoutScenario

from polaris.core.models import FindingCategory, LineRange, Severity
from polaris.evaluation.models import ChangeType, EvaluationFixture, EvaluationSummary, ExpectedFindingSpec
from polaris.evaluation.runner import evaluate_corpus
from polaris.providers.fake import FakeProvider


def holdout_sha256(cases: tuple[HoldoutScenario, ...] = CASES) -> str:
    data = "\n".join("\x1f".join((case.id, case.before, case.after, case.oracle)) for case in cases)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def fixture_for(case: HoldoutScenario) -> EvaluationFixture:
    diff = "".join(
        difflib.unified_diff(
            case.before.splitlines(keepends=True),
            case.after.splitlines(keepends=True),
            fromfile=f"a/{case.path}",
            tofile=f"b/{case.path}",
        )
    )
    expected = (
        [
            ExpectedFindingSpec(
                file_path=case.path,
                line_range=LineRange(start_line=case.line, end_line=case.line),
                category=FindingCategory(case.category),
                severity=Severity.MEDIUM,
            )
        ]
        if case.kind == "positive"
        else []
    )
    return EvaluationFixture(
        case_id=case.id,
        description=f"Causal holdout scenario: {case.oracle}",
        diff_text=f"diff --git a/{case.path} b/{case.path}\n{diff}",
        file_contents={case.path: case.after},
        expected_findings=expected,
        is_clean=case.kind == "negative",
        provenance="agent_authored_post_recovery_holdout",
        change_type=ChangeType.DEFECT_INTRODUCTION if case.kind == "positive" else ChangeType.CLEAN_UNRELATED,
    )


@dataclass(frozen=True)
class HoldoutResult:
    sha256: str
    summary: EvaluationSummary


def run_holdout(cases: tuple[HoldoutScenario, ...] = CASES) -> HoldoutResult:
    fixtures = [fixture_for(case) for case in cases]
    summary = evaluate_corpus(
        fixtures,
        FakeProvider(scripted_responses=["{}"] * len(fixtures)),
        force_end_to_end=True,
        behavioral_delta_enabled=False,
    )
    return HoldoutResult(holdout_sha256(cases), summary)
