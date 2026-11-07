"""End-to-end detection coverage for the GOAL 24 causal runner."""

from evaluations.fixtures.goal24_rc1.catalog import CATALOG
from evaluations.goal24_runner import catalog_sha256, fixture_for, run_goal24_catalog

from polaris.evaluation.models import ChangeType


def test_goal24_runner_scores_every_catalog_case_and_separates_difficulty() -> None:
    result = run_goal24_catalog()

    assert len(result.catalog_sha256) == 64
    assert result.overall.dataset_size == 60
    assert result.overall.positive_cases == 30
    assert result.overall.negative_cases == 30
    assert set(result.by_difficulty) == {"N1", "N2", "N3"}
    assert {level: summary.dataset_size for level, summary in result.by_difficulty.items()} == {
        "N1": 12,
        "N2": 24,
        "N3": 24,
    }
    assert catalog_sha256() == result.catalog_sha256


def test_goal24_runner_uses_production_fixtures_with_explicit_ground_truth() -> None:
    positive = next(case for case in CATALOG if case.kind == "positive")
    negative = next(case for case in CATALOG if case.kind == "negative")

    assert fixture_for(positive).expected_findings
    assert fixture_for(negative).expected_findings == []
    assert fixture_for(positive).file_contents
    assert fixture_for(positive).change_type == ChangeType.DEFECT_INTRODUCTION
    assert fixture_for(negative).change_type == ChangeType.CLEAN_UNRELATED
