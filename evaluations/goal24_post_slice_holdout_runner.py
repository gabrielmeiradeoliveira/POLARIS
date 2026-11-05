"""Runner for the frozen, internally authored post-slice holdout."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass

from evaluations.fixtures.goal24_post_slice_holdout.catalog import CASES, PostSliceScenario

from polaris.core.models import FindingCategory, LineRange, Severity
from polaris.evaluation.models import ChangeType, EvaluationFixture, EvaluationSummary, ExpectedFindingSpec
from polaris.evaluation.runner import evaluate_corpus
from polaris.providers.fake import FakeProvider


def corpus_sha256(cases: tuple[PostSliceScenario, ...] = CASES) -> str:
    serialized = "\n".join(
        "\x1f".join(
            (
                case.id,
                case.kind,
                case.category,
                case.expected_path,
                str(case.expected_line),
                case.entrypoint,
                case.oracle,
                repr(tuple(sorted(case.before_files.items()))),
                repr(tuple(sorted(case.after_files.items()))),
            )
        )
        for case in cases
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _diff_for(case: PostSliceScenario) -> str:
    chunks: list[str] = []
    for path in sorted(set(case.before_files) | set(case.after_files)):
        before = case.before_files.get(path, "")
        after = case.after_files.get(path, "")
        if before == after:
            continue
        patch = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
        chunks.append(f"diff --git a/{path} b/{path}\n{patch}")
    return "".join(chunks)


def fixture_for(case: PostSliceScenario) -> EvaluationFixture:
    expected = (
        [
            ExpectedFindingSpec(
                file_path=case.expected_path,
                line_range=LineRange(start_line=case.expected_line, end_line=case.expected_line),
                category=FindingCategory(case.category),
                severity=Severity.MEDIUM,
            )
        ]
        if case.kind == "positive"
        else []
    )
    return EvaluationFixture(
        case_id=case.id,
        description=f"Frozen post-slice causal scenario: {case.oracle}",
        diff_text=_diff_for(case),
        file_contents=case.after_files,
        expected_findings=expected,
        is_clean=case.kind == "negative",
        provenance="agent_authored_post_slice_holdout",
        change_type=ChangeType.DEFECT_INTRODUCTION if case.kind == "positive" else ChangeType.CLEAN_UNRELATED,
    )


@dataclass(frozen=True)
class PostSliceHoldoutResult:
    sha256: str
    summary: EvaluationSummary


def run_post_slice_holdout(cases: tuple[PostSliceScenario, ...] = CASES) -> PostSliceHoldoutResult:
    fixtures = [fixture_for(case) for case in cases]
    summary = evaluate_corpus(
        fixtures,
        FakeProvider(scripted_responses=["{}"] * len(fixtures)),
        force_end_to_end=True,
        behavioral_delta_enabled=False,
    )
    return PostSliceHoldoutResult(corpus_sha256(cases), summary)
