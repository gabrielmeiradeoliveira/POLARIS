"""Regression coverage for per-case versus corpus token accounting."""

from pathlib import Path

from deicide.evaluation.runner import evaluate_corpus, load_fixtures_from_file
from deicide.providers.fake import FakeProvider


def test_case_usage_is_incremental_while_summary_remains_aggregate() -> None:
    fixtures = load_fixtures_from_file(Path("evaluations/fixtures/end_to_end_context_benchmark.json"))[:2]
    summary = evaluate_corpus(fixtures, FakeProvider(), force_end_to_end=True)
    assert sum(case.usage.total_tokens for case in summary.case_results) == summary.usage.total_tokens
