from pathlib import Path

import pytest

from deicide.evaluation.fixture_integrity import FixtureIntegrityError, validate_fixture_diff
from deicide.evaluation.runner import load_fixtures_from_file


def test_real_world_fixture_diffs_round_trip() -> None:
    fixtures = load_fixtures_from_file(Path("evaluations/fixtures/real_world_verified_benchmark.json"))
    for fixture in fixtures:
        result = validate_fixture_diff(fixture.diff_text, fixture.file_contents)
        assert len(result) == 1
        assert result[0].after == fixture.file_contents[result[0].file_path]


@pytest.mark.parametrize(
    "diff_text, message",
    [
        ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,1 @@\n+x = 1\n", "Hunk counts"),
        ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -2,1 +2,1 @@\n x = 1\n", "New-side lines"),
    ],
)
def test_fixture_integrity_rejects_malformed_diffs(diff_text: str, message: str) -> None:
    with pytest.raises(FixtureIntegrityError, match=message):
        validate_fixture_diff(diff_text, {"a.py": "x = 1\n"})
