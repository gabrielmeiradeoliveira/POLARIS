"""Schema and end-to-end integrity checks for the context-dependent benchmark."""

from __future__ import annotations

from pathlib import Path

from polaris.evaluation.models import ChangeType, ContextRequirement, NegativeChangeType
from polaris.evaluation.runner import evaluate_corpus, load_fixtures_from_file
from polaris.git.analyzer import parse_unified_diff
from polaris.providers.fake import FakeProvider

BENCHMARK_PATH = Path("evaluations/fixtures/end_to_end_context_benchmark.json")


def test_context_benchmark_has_balanced_context_dependent_cases() -> None:
    fixtures = load_fixtures_from_file(BENCHMARK_PATH)
    assert len(fixtures) == 20
    assert sum(not fixture.is_clean for fixture in fixtures) == 12
    assert sum(fixture.is_clean for fixture in fixtures) == 8
    assert all(len(fixture.file_contents) >= 3 for fixture in fixtures)
    assert all(not fixture.candidate_findings for fixture in fixtures)
    for fixture in fixtures:
        assert fixture.context_rationale
        assert fixture.context_requirement is not None
        assert fixture.resolved_change_type in (ChangeType.DEFECT_INTRODUCTION, ChangeType.CLEAN_BUG_FIX, ChangeType.CLEAN_UNRELATED)
        diff_files = parse_unified_diff(fixture.diff_text)
        for expected in fixture.expected_findings:
            assert expected.evidence
            assert expected.file_path in fixture.file_contents
            changed_file = next(file for file in diff_files if file.new_path == expected.file_path)
            assert changed_file.has_changed_overlap(expected.line_range)

        if fixture.is_clean:
            assert fixture.negative_change_type is not None
            expected_negative_type = (
                NegativeChangeType.CLEAN_BUG_FIX
                if fixture.resolved_change_type is ChangeType.CLEAN_BUG_FIX
                else NegativeChangeType.BEHAVIOR_PRESERVING
            )
            assert fixture.negative_change_type is expected_negative_type
        else:
            assert fixture.negative_change_type is None

    assert {fixture.context_requirement for fixture in fixtures} == set(ContextRequirement)


def test_context_benchmark_runs_without_seeded_findings_end_to_end() -> None:
    fixtures = load_fixtures_from_file(BENCHMARK_PATH)
    summary = evaluate_corpus(fixtures, provider=FakeProvider(), force_end_to_end=True)
    assert summary.dataset_size == 20
    assert summary.evaluation_mode == "end_to_end"
    assert summary.successful_cases == 20
