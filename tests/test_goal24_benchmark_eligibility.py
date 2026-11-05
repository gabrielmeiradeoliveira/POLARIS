"""Prevent fix diffs from being presented as defect-detection evidence."""

from pathlib import Path

import pytest
from evaluations.fixtures.goal24_rc1.catalog import CATALOG
from evaluations.goal24_runner import fixture_for

from polaris.evaluation.models import ChangeType
from polaris.evaluation.runner import load_fixtures_from_file


def test_goal24_positive_cases_are_explicit_defect_introductions() -> None:
    positives = [fixture_for(case) for case in CATALOG if case.kind == "positive"]

    assert positives
    assert all(fixture.change_type == ChangeType.DEFECT_INTRODUCTION for fixture in positives)
    assert all(fixture.is_suitable_for_live_benchmark for fixture in positives)


@pytest.mark.parametrize(
    "path",
    (
        "evaluations/fixtures/real_world_benchmark.json",
        "evaluations/fixtures/code_review_corpus.json",
    ),
)
def test_legacy_corpora_are_not_release_eligible_without_direction_metadata(path: str) -> None:
    fixtures = load_fixtures_from_file(Path(path))

    assert all(fixture.change_type is None for fixture in fixtures)
    assert any(fixture.expected_findings for fixture in fixtures)
