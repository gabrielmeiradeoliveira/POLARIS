"""Controlled prompt-efficiency measurements for the offline recovery."""

from polaris.evaluation.runner import evaluate_corpus
from polaris.providers.fake import FakeProvider
from tests.test_goal23_real_world import _cases, _fixture


def test_behavioral_delta_cost_is_measured_without_claiming_model_quality() -> None:
    fixtures = [_fixture(case) for case in _cases()]
    without_deltas = evaluate_corpus(
        fixtures,
        FakeProvider(scripted_responses=["{}"] * len(fixtures)),
        force_end_to_end=True,
        behavioral_delta_enabled=False,
    )
    with_deltas = evaluate_corpus(
        fixtures,
        FakeProvider(scripted_responses=["{}"] * len(fixtures)),
        force_end_to_end=True,
        behavioral_delta_enabled=True,
    )

    assert with_deltas.usage.is_estimated
    assert without_deltas.usage.is_estimated
    assert with_deltas.usage.prompt_tokens > without_deltas.usage.prompt_tokens
    assert (with_deltas.true_positives, with_deltas.false_positives, with_deltas.false_negatives) == (
        without_deltas.true_positives,
        without_deltas.false_positives,
        without_deltas.false_negatives,
    )
