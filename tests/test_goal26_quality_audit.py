from pathlib import Path

import pytest
from evaluations.goal26_quality_audit import Campaign, aggregate, comparable_groups, inventory


def test_inventory_reads_summary_and_classifies_comparability(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text('{"provider":"fake","model":"v1","corpus_sha256":"a","configuration":{"delta":false},"true_positives":1,"false_positives":0,"false_negatives":2}', encoding="utf-8")
    records = inventory(tmp_path)
    assert len(records) == 1
    assert aggregate(records) == (1, 0, 2)
    assert len(comparable_groups(records)) == 1


def test_aggregate_rejects_incompatible_campaigns() -> None:
    first = Campaign(Path("a"), "corpus-a", "fake", "v1", "{}", None, 1, 0, 0)
    second = Campaign(Path("b"), "corpus-b", "fake", "v1", "{}", None, 1, 0, 0)
    with pytest.raises(ValueError, match="incompatible"):
        aggregate([first, second])
