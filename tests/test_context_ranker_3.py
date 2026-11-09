"""Tests for ContextRanker 3.0 (GOAL 30 - Fase 30.9)."""

from polaris.context.context_ranker_3 import ContextRanker3
from polaris.context.impact_analysis import ImpactClassification, ImpactedConsumer


def test_context_ranker_3_deterministic_budget_enforcement():
    """Verify that ranker deterministically selects highest scored candidates within token limit."""
    consumer_direct = ImpactedConsumer(
        consumer_id="c1",
        consumer_name="caller_direct",
        file_path="caller_direct.py",
        classification=ImpactClassification.DIRECT,
    )
    consumer_trans = ImpactedConsumer(
        consumer_id="c2",
        consumer_name="caller_transitive",
        file_path="caller_trans.py",
        classification=ImpactClassification.TRANSITIVE,
    )

    contents = {
        "main.py": "x" * 400,         # ~100 tokens
        "caller_direct.py": "y" * 800, # ~200 tokens
        "caller_trans.py": "z" * 800,  # ~200 tokens
    }

    # Strict budget: 250 tokens -> Should fit main.py (100) + caller_direct (200) -> Wait, 100+200=300 > 250!
    # So with max_tokens=250, only main.py (100 tokens) fits, or caller_direct if main wasn't there.
    selected = ContextRanker3.rank_context(
        changed_files=["main.py"],
        impacted_consumers=[consumer_direct, consumer_trans],
        behavioral_changes=[],
        file_contents=contents,
        max_tokens=250,
    )

    assert len(selected) == 1
    assert selected[0].file_path == "main.py"
    assert selected[0].score == 100.0
