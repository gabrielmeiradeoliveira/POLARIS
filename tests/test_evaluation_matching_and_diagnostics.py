"""Tests for evaluation matching improvements, category alternatives, and finding diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from deicide.cli import app
from deicide.core.errors import ExitCode
from deicide.core.models import (
    CandidateFinding,
    Confidence,
    Finding,
    FindingCategory,
    LineRange,
    Severity,
)
from deicide.evaluation.models import (
    EvaluationFixture,
    EvaluationSummary,
    ExpectedFindingSpec,
)
from deicide.evaluation.runner import evaluate_case, evaluate_corpus, load_fixtures_from_file
from deicide.providers.fake import FakeProvider

runner = CliRunner()

DIFF_MATH = """diff --git a/src/math.py b/src/math.py
--- a/src/math.py
+++ b/src/math.py
@@ -1,5 +1,5 @@
 def divide(a, b):
-    return a / b if b != 0 else 0
+    # check 1
+    # middle
+    return a / b
+    # check 2
"""

MATH_CONTENTS = {"src/math.py": "def divide(a, b):\n    # check 1\n    # middle\n    return a / b\n    # check 2\n"}


def _build_test_fixture(
    expected_findings: list[ExpectedFindingSpec] | None = None,
    candidate_findings: list[CandidateFinding] | None = None,
    case_id: str = "test-case-01",
    is_clean: bool = False,
) -> EvaluationFixture:
    return EvaluationFixture(
        case_id=case_id,
        description="Testing evaluation matching and diagnostics",
        diff_text=DIFF_MATH,
        file_contents=MATH_CONTENTS,
        expected_findings=expected_findings or [],
        candidate_findings=candidate_findings or [],
        repository="deicide/test",
        commit_id="1234567",
        is_clean=is_clean,
        fix_reference="test-fix",
        provenance="synthetic",
        suitable_for_live_benchmark=True,
    )


def test_exact_category_matching() -> None:
    """Exact category matching succeeds with TP=1, FP=0, FN=0."""
    spec = ExpectedFindingSpec(
        file_path="src/math.py",
        line_range=LineRange(start_line=4, end_line=4),
        category=FindingCategory.CORRECTNESS,
        severity=Severity.HIGH,
    )
    fixture = _build_test_fixture(
        expected_findings=[spec],
        candidate_findings=[
            CandidateFinding(
                category=FindingCategory.CORRECTNESS,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="src/math.py",
                start_line=4,
                end_line=4,
                title="ZeroDivisionError in divide",
                description="Division by zero when b == 0.",
                evidence="return a / b",
            )
        ],
    )

    res = evaluate_case(fixture, provider=FakeProvider())
    assert res.true_positives == 1
    assert res.false_positives == 0
    assert res.false_negatives == 0
    assert res.category_mismatch_detections == 0
    assert res.undetected_expected_defects == 0
    assert res.diagnostics is not None
    assert len(res.diagnostics.matched_findings) == 1
    assert len(res.diagnostics.unmatched_findings) == 0
    assert len(res.diagnostics.unmatched_expected) == 0

    matched = res.diagnostics.matched_findings[0]
    assert matched.category == FindingCategory.CORRECTNESS
    assert matched.file_path == "src/math.py"
    assert matched.severity_match is True


def test_accepted_alternative_category_matching() -> None:
    """Allowed alternative category matches and records correct diagnostics."""
    spec = ExpectedFindingSpec(
        file_path="src/math.py",
        line_range=LineRange(start_line=4, end_line=4),
        category=FindingCategory.CORRECTNESS,
        allowed_categories=[FindingCategory.CORRECTNESS, FindingCategory.BOUNDARY_CONDITION],
        severity=Severity.HIGH,
    )
    fixture = _build_test_fixture(
        expected_findings=[spec],
        candidate_findings=[
            CandidateFinding(
                category=FindingCategory.BOUNDARY_CONDITION,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="src/math.py",
                start_line=4,
                end_line=4,
                title="Boundary condition zero divisor",
                description="When b is 0, division causes ZeroDivisionError.",
                evidence="return a / b",
            )
        ],
    )

    res = evaluate_case(fixture, provider=FakeProvider())
    assert res.true_positives == 1
    assert res.false_positives == 0
    assert res.false_negatives == 0
    assert res.diagnostics is not None
    assert len(res.diagnostics.matched_findings) == 1

    matched = res.diagnostics.matched_findings[0]
    assert matched.category == FindingCategory.BOUNDARY_CONDITION
    assert matched.expected_category == FindingCategory.CORRECTNESS
    assert FindingCategory.BOUNDARY_CONDITION in matched.expected_allowed_categories


def test_unrelated_category_rejection_and_diagnostics() -> None:
    """An unrelated category is not matched and explicit mismatch reason is recorded."""
    spec = ExpectedFindingSpec(
        file_path="src/math.py",
        line_range=LineRange(start_line=4, end_line=4),
        category=FindingCategory.CORRECTNESS,
        allowed_categories=[FindingCategory.CORRECTNESS, FindingCategory.BOUNDARY_CONDITION],
        severity=Severity.HIGH,
    )
    fixture = _build_test_fixture(
        expected_findings=[spec],
        candidate_findings=[
            CandidateFinding(
                category=FindingCategory.CONCURRENCY,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="src/math.py",
                start_line=4,
                end_line=4,
                title="Race condition in math",
                description="Hallucinated concurrency defect.",
                evidence="return a / b",
            )
        ],
    )

    res = evaluate_case(fixture, provider=FakeProvider())
    assert res.true_positives == 0
    assert res.false_positives == 1
    assert res.false_negatives == 1
    assert res.category_mismatch_detections == 1
    assert res.undetected_expected_defects == 0
    assert res.diagnostics is not None
    assert len(res.diagnostics.category_mismatches) == 1
    category_mismatch = res.diagnostics.category_mismatches[0]
    assert category_mismatch.category == FindingCategory.CONCURRENCY
    assert category_mismatch.expected_category == FindingCategory.CORRECTNESS

    # Verify unmatched finding diagnostic
    assert len(res.diagnostics.unmatched_findings) == 1
    unmatched_f = res.diagnostics.unmatched_findings[0]
    assert unmatched_f.category == FindingCategory.CONCURRENCY
    assert any("category mismatch" in r for r in unmatched_f.reasons)
    assert "concurrency" in unmatched_f.reason

    # Verify unmatched expected defect diagnostic
    assert len(res.diagnostics.unmatched_expected) == 1
    unmatched_e = res.diagnostics.unmatched_expected[0]
    assert unmatched_e.file_path == "src/math.py"
    assert "category 'concurrency' not in" in unmatched_e.reason


def test_undetected_expected_defect_is_distinct_from_category_mismatch() -> None:
    """Missing candidates are counted as undetected, not category mismatches."""
    fixture = _build_test_fixture(
        expected_findings=[
            ExpectedFindingSpec(
                file_path="src/math.py",
                line_range=LineRange(start_line=4, end_line=4),
                category=FindingCategory.CORRECTNESS,
            )
        ]
    )

    result = evaluate_case(fixture, provider=FakeProvider())

    assert result.true_positives == 0
    assert result.false_positives == 0
    assert result.false_negatives == 1
    assert result.category_mismatch_detections == 0
    assert result.undetected_expected_defects == 1


def test_detection_metrics_report_category_mismatches_separately() -> None:
    """Location-matched category mismatches improve diagnostic, never strict, metrics."""
    mismatch_spec = ExpectedFindingSpec(
        file_path="src/math.py",
        line_range=LineRange(start_line=4, end_line=4),
        category=FindingCategory.CORRECTNESS,
    )
    mismatch_fixture = _build_test_fixture(
        expected_findings=[mismatch_spec],
        candidate_findings=[
            CandidateFinding(
                category=FindingCategory.LOGIC_ERROR,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="src/math.py",
                start_line=4,
                end_line=4,
                title="Wrongly categorized division defect",
                description="Division by zero remains possible.",
                evidence="return a / b",
            )
        ],
        case_id="category-mismatch",
    )
    missed_fixture = _build_test_fixture(
        expected_findings=[mismatch_spec],
        case_id="undetected",
    )

    summary = evaluate_corpus([mismatch_fixture, missed_fixture], provider=FakeProvider())

    assert (summary.true_positives, summary.false_positives, summary.false_negatives) == (0, 1, 2)
    assert summary.category_mismatch_detections == 1
    assert summary.undetected_expected_defects == 1
    assert summary.detection_precision == 1.0
    assert summary.detection_recall == 0.5


def test_incorrect_file_and_line_rejection() -> None:
    """Incorrect file or out-of-tolerance line range does not match expected defect."""
    spec = ExpectedFindingSpec(
        file_path="src/math.py",
        line_range=LineRange(start_line=2, end_line=2),
        category=FindingCategory.CORRECTNESS,
    )

    # 1. Spec with different file
    spec_wrong_file = ExpectedFindingSpec(
        file_path="src/other.py",
        line_range=LineRange(start_line=2, end_line=2),
        category=FindingCategory.CORRECTNESS,
    )
    actual = Finding(
        id="dcd-1",
        module_id="code_review",
        category=FindingCategory.CORRECTNESS,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="src/math.py",
        line_range=LineRange(start_line=2, end_line=2),
        title="ZeroDivisionError",
        description="divide by zero",
        evidence="return a / b",
    )
    assert not spec_wrong_file.matches(actual)

    # 2. Actual with out-of-tolerance lines (e.g. line 10 vs line 2)
    actual_far_line = Finding(
        id="dcd-2",
        module_id="code_review",
        category=FindingCategory.CORRECTNESS,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="src/math.py",
        line_range=LineRange(start_line=10, end_line=12),
        title="ZeroDivisionError",
        description="divide by zero",
        evidence="return a / b",
    )
    assert not spec.matches(actual_far_line)


def test_multiple_findings_competing_for_one_expected_defect() -> None:
    """Strict 1-to-1 matching: 2 findings matching the same defect produce TP=1, FP=1, FN=0."""
    spec = ExpectedFindingSpec(
        file_path="src/math.py",
        line_range=LineRange(start_line=3, end_line=3),
        category=FindingCategory.CORRECTNESS,
        allowed_categories=[FindingCategory.CORRECTNESS, FindingCategory.BOUNDARY_CONDITION],
        severity=Severity.HIGH,
    )
    fixture = _build_test_fixture(
        expected_findings=[spec],
        candidate_findings=[
            CandidateFinding(
                category=FindingCategory.CORRECTNESS,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="src/math.py",
                start_line=2,
                end_line=2,
                title="ZeroDivisionError 1",
                description="Division by zero candidate 1.",
                evidence="# check 1",
            ),
            CandidateFinding(
                category=FindingCategory.BOUNDARY_CONDITION,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="src/math.py",
                start_line=4,
                end_line=4,
                title="ZeroDivisionError 2",
                description="Division by zero candidate 2.",
                evidence="return a / b",
            ),
        ],
    )

    # Use baseline to bypass deduplication so both candidates become distinct actual findings
    res = evaluate_case(fixture, provider=FakeProvider(), use_baseline=True)
    assert len(res.actual_findings) == 2
    assert res.true_positives == 1
    assert res.false_positives == 1
    assert res.false_negatives == 0

    assert res.diagnostics is not None
    assert len(res.diagnostics.matched_findings) == 1
    assert len(res.diagnostics.unmatched_findings) == 1
    unmatched_diag = res.diagnostics.unmatched_findings[0]
    assert any("already claimed" in r for r in unmatched_diag.reasons)
    assert "one-to-one constraint" in unmatched_diag.reason


def test_rejected_candidate_diagnostics_capture_reasons() -> None:
    """Candidate findings rejected by validation are captured with rejection reason and code."""
    fixture = _build_test_fixture(
        expected_findings=[],
        candidate_findings=[
            CandidateFinding(
                category=FindingCategory.CORRECTNESS,
                severity=Severity.LOW,
                confidence=Confidence.LOW,
                file_path="src/math.py",
                start_line=2,
                end_line=2,
                title="Style nitpick: missing docstring",
                description="formatting nit on function",
                evidence="return a / b",
            ),
            CandidateFinding(
                category=FindingCategory.CORRECTNESS,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="src/math.py",
                start_line=2,
                end_line=2,
                title="Hallucinated evidence finding",
                description="Evidence not in diff or context",
                evidence="def non_existent_function_call(): pass",
            ),
        ],
    )

    res = evaluate_case(fixture, provider=FakeProvider())
    assert len(res.actual_findings) == 0
    assert res.diagnostics is not None
    assert len(res.diagnostics.rejected_candidates) == 2

    rej_style = res.diagnostics.rejected_candidates[0]
    assert rej_style.rejection_code == "FINDING_REJECTED_STYLE_NOISE"
    assert "stylistic recommendation" in rej_style.reason

    rej_ev = res.diagnostics.rejected_candidates[1]
    assert rej_ev.rejection_code == "FINDING_REJECTED_UNSUPPORTED_EVIDENCE"
    assert "evidence" in rej_ev.reason.lower()


def test_backward_compatibility_with_single_or_no_category() -> None:
    """Backward compatibility: single category or None category behave identically to legacy."""
    # 1. Spec with single category and no alternatives
    spec_legacy = ExpectedFindingSpec(
        file_path="src/math.py",
        line_range=LineRange(start_line=2, end_line=2),
        category=FindingCategory.CORRECTNESS,
    )
    assert spec_legacy.acceptable_categories == {FindingCategory.CORRECTNESS}

    actual_correct = Finding(
        id="dcd-1",
        module_id="code_review",
        category=FindingCategory.CORRECTNESS,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="src/math.py",
        line_range=LineRange(start_line=2, end_line=2),
        title="ZeroDivisionError",
        description="divide by zero",
        evidence="return a / b",
    )
    assert spec_legacy.matches(actual_correct)

    actual_boundary = Finding(
        id="dcd-2",
        module_id="code_review",
        category=FindingCategory.BOUNDARY_CONDITION,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="src/math.py",
        line_range=LineRange(start_line=2, end_line=2),
        title="ZeroDivisionError",
        description="divide by zero",
        evidence="return a / b",
    )
    assert not spec_legacy.matches(actual_boundary)

    # 2. Spec with category=None matches any category
    spec_none = ExpectedFindingSpec(
        file_path="src/math.py",
        line_range=LineRange(start_line=2, end_line=2),
        category=None,
    )
    assert spec_none.acceptable_categories is None
    assert spec_none.matches(actual_correct)
    assert spec_none.matches(actual_boundary)


def test_json_serialization_and_deserialization() -> None:
    """Evaluation summary with diagnostics serializes and deserializes cleanly in JSON."""
    spec = ExpectedFindingSpec(
        file_path="src/math.py",
        line_range=LineRange(start_line=4, end_line=4),
        category=FindingCategory.CORRECTNESS,
        allowed_categories=[FindingCategory.CORRECTNESS, FindingCategory.BOUNDARY_CONDITION],
        severity=Severity.HIGH,
    )
    fixture = _build_test_fixture(
        expected_findings=[spec],
        candidate_findings=[
            CandidateFinding(
                category=FindingCategory.BOUNDARY_CONDITION,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="src/math.py",
                start_line=4,
                end_line=4,
                title="ZeroDivisionError",
                description="divide by zero",
                evidence="return a / b",
            )
        ],
    )

    summary = evaluate_corpus([fixture], provider=FakeProvider())
    raw_json = summary.model_dump_json(indent=2)
    parsed = json.loads(raw_json)

    assert "case_results" in parsed
    case_0 = parsed["case_results"][0]
    assert "diagnostics" in case_0
    diag = case_0["diagnostics"]
    assert len(diag["matched_findings"]) == 1
    assert diag["matched_findings"][0]["category"] == "boundary_condition"
    assert "correctness" in diag["matched_findings"][0]["expected_allowed_categories"]

    # Deserialization check
    roundtripped = EvaluationSummary.model_validate(parsed)
    assert roundtripped.dataset_size == summary.dataset_size
    assert roundtripped.true_positives == 1
    assert roundtripped.case_results[0].diagnostics is not None
    assert len(roundtripped.case_results[0].diagnostics.matched_findings) == 1


def test_cli_detailed_diagnostics_flag(tmp_path: Path) -> None:
    """CLI --detailed and --diagnostics flags render finding-level diagnostics."""
    fixture_path = Path("evaluations/fixtures/bug_introduction_benchmark.json")

    # Invocation without --detailed: clean summary, no diagnostics heading
    res_standard = runner.invoke(
        app,
        ["evaluate", "--provider", "fake", "--fixtures", str(fixture_path), "--max-cases", "1"],
    )
    assert res_standard.exit_code == int(ExitCode.SUCCESS)
    assert "Finding-Level Evaluation Diagnostics:" not in res_standard.stdout

    # Invocation with --detailed: prints diagnostics section
    res_detailed = runner.invoke(
        app,
        ["evaluate", "--provider", "fake", "--fixtures", str(fixture_path), "--max-cases", "1", "--detailed"],
    )
    assert res_detailed.exit_code == int(ExitCode.SUCCESS)
    assert "Finding-Level Evaluation Diagnostics:" in res_detailed.stdout
    assert "Case ID: bug-intro-01-tqdm-zerodiv" in res_detailed.stdout
    assert "Parsed Candidates (1):" in res_detailed.stdout
    assert "Matched Findings (1):" in res_detailed.stdout

    # Invocation with --diagnostics alias
    res_alias = runner.invoke(
        app,
        ["evaluate", "--provider", "fake", "--fixtures", str(fixture_path), "--max-cases", "1", "--diagnostics"],
    )
    assert res_alias.exit_code == int(ExitCode.SUCCESS)
    assert "Finding-Level Evaluation Diagnostics:" in res_alias.stdout


def test_tqdm_zerodiv_fixture_matches_both_categories() -> None:
    """Fixture bug-intro-01-tqdm-zerodiv matches both correctness and boundary_condition."""
    benchmark_path = Path("evaluations/fixtures/bug_introduction_benchmark.json")
    fixtures = load_fixtures_from_file(benchmark_path)
    tqdm_case = next(f for f in fixtures if f.case_id == "bug-intro-01-tqdm-zerodiv")

    expected = tqdm_case.expected_findings[0]
    assert expected.category == FindingCategory.CORRECTNESS
    assert FindingCategory.BOUNDARY_CONDITION in expected.acceptable_categories
    assert FindingCategory.CORRECTNESS in expected.acceptable_categories

    # Test candidate with boundary_condition
    boundary_candidate = CandidateFinding(
        category=FindingCategory.BOUNDARY_CONDITION,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="tqdm/std.py",
        start_line=4,
        end_line=4,
        title="ZeroDivisionError when delta_t is zero",
        description="When delta_t <= 0 elapsed guard is missing.",
        evidence="return dn / delta_t",
    )
    modified_case = tqdm_case.model_copy(update={"candidate_findings": [boundary_candidate]})
    res_boundary = evaluate_case(modified_case, provider=FakeProvider())
    assert res_boundary.true_positives == 1
    assert res_boundary.false_positives == 0
    assert res_boundary.false_negatives == 0


def test_undefined_metric_denominators_produce_none_and_terminal_na(tmp_path: Path) -> None:
    """Verify precision, recall, and false positive rate undefined denominators yield None and 'N/A'."""
    # 1. Corpus with only positive case and no findings predicted:
    # Denominators: TP+FP = 0 (undefined -> None), TP+FN = 1 (defined -> 0.0), Negative cases = 0 (undefined -> None)
    pos_fixture = _build_test_fixture(
        expected_findings=[
            ExpectedFindingSpec(
                file_path="src/math.py",
                line_range=LineRange(start_line=4, end_line=4),
                category=FindingCategory.CORRECTNESS,
            )
        ],
        candidate_findings=[],
        case_id="pos-only",
        is_clean=False,
    )
    summary_pos_only = evaluate_corpus([pos_fixture], provider=FakeProvider())
    assert summary_pos_only.true_positives == 0
    assert summary_pos_only.false_positives == 0
    assert summary_pos_only.false_negatives == 1
    assert summary_pos_only.precision is None
    assert summary_pos_only.recall == 0.0
    assert summary_pos_only.false_positive_rate is None

    # Verify JSON output consistency
    json_pos = json.loads(summary_pos_only.model_dump_json())
    assert json_pos["precision"] is None
    assert json_pos["recall"] == 0.0
    assert json_pos["false_positive_rate"] is None

    # 2. Corpus with only clean negative case and no findings predicted:
    # Denominators: TP+FP = 0 (undefined -> None), TP+FN = 0 (undefined -> None), Negative cases = 1 (defined -> 0.0)
    clean_fixture = _build_test_fixture(
        expected_findings=[],
        candidate_findings=[],
        case_id="clean-only",
        is_clean=True,
    )
    summary_clean_only = evaluate_corpus([clean_fixture], provider=FakeProvider())
    assert summary_clean_only.true_positives == 0
    assert summary_clean_only.false_positives == 0
    assert summary_clean_only.false_negatives == 0
    assert summary_clean_only.precision is None
    assert summary_clean_only.recall is None
    assert summary_clean_only.false_positive_rate == 0.0

    json_clean = json.loads(summary_clean_only.model_dump_json())
    assert json_clean["precision"] is None
    assert json_clean["recall"] is None
    assert json_clean["false_positive_rate"] == 0.0

    # 3. Corpus with only clean negative case and 1 false positive predicted:
    # Denominators: TP+FP = 1 (defined -> 0.0), TP+FN = 0 (undefined -> None), Negative cases = 1 (defined -> 1.0)
    clean_with_fp = _build_test_fixture(
        expected_findings=[],
        candidate_findings=[
            CandidateFinding(
                category=FindingCategory.CORRECTNESS,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="src/math.py",
                start_line=4,
                end_line=4,
                title="Spurious bug in clean code",
                description="Hallucinated issue",
                evidence="return a / b",
            )
        ],
        case_id="clean-with-fp",
        is_clean=True,
    )
    summary_clean_fp = evaluate_corpus([clean_with_fp], provider=FakeProvider())
    assert summary_clean_fp.true_positives == 0
    assert summary_clean_fp.false_positives == 1
    assert summary_clean_fp.false_negatives == 0
    assert summary_clean_fp.precision == 0.0
    assert summary_clean_fp.recall is None
    assert summary_clean_fp.false_positive_rate == 1.0

    # 4. Verify CLI terminal output renders 'N/A' when metrics are None
    test_corpus_file = tmp_path / "test_corpus.json"
    test_corpus_file.write_text(
        json.dumps([pos_fixture.model_dump(mode="json")]),
        encoding="utf-8",
    )
    cli_res = runner.invoke(app, ["evaluate", "--provider", "fake", "--fixtures", str(test_corpus_file)])
    assert cli_res.exit_code == int(ExitCode.SUCCESS)
    assert "Precision           : N/A" in cli_res.stdout
    assert "Recall              : 0.00%" in cli_res.stdout
    assert "False Positive Rate : N/A" in cli_res.stdout
