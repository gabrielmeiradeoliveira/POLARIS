"""Production-parity evaluation controls for the E2E benchmark."""

from pathlib import Path

from polaris.context.context_models import ContextSelectionLimits
from polaris.core.models import ExecutionBudget
from polaris.evaluation.runner import (
    _prepare_production_parity_context,
    evaluate_corpus,
    load_fixtures_from_file,
)
from polaris.git.analyzer import parse_unified_diff
from polaris.git.models import DiffBundle
from polaris.modules.code_review import CodeReviewModule
from polaris.providers.fake import FakeProvider

FIXTURES = Path("evaluations/fixtures/end_to_end_context_benchmark.json")


def _bundle(fixture):
    return DiffBundle(
        repository_root="/evaluation/fixture",
        base_revision="HEAD",
        target_description=fixture.case_id,
        files=parse_unified_diff(fixture.diff_text),
    )


def test_production_parity_preserves_baseline_context_and_hides_ground_truth() -> None:
    fixture = load_fixtures_from_file(FIXTURES)[0]
    limits = ContextSelectionLimits(max_context_tokens=2000, behavioral_delta_reserved_tokens=500)
    module = CodeReviewModule()
    budget = ExecutionBudget(max_total_tokens=50_000)

    off_contexts, off = _prepare_production_parity_context(fixture, _bundle(fixture), budget, module, False, limits)
    on_contexts, on = _prepare_production_parity_context(fixture, _bundle(fixture), budget, module, True, limits)

    assert off_contexts == on_contexts
    assert off is not None and on is not None
    assert off.serialized_text == on.serialized_text
    assert off.selected_snippets == on.selected_snippets
    assert off.serialized_behavioral_deltas == ""
    assert off.total_estimated_tokens <= off.max_allowed_tokens
    assert on.total_estimated_tokens <= on.max_allowed_tokens

    prompt = module._build_user_prompt(_bundle(fixture).reviewable_files, on_contexts, context_result=on)
    assert fixture.description not in prompt
    assert fixture.expected_findings[0].evidence not in prompt
    assert "context_requirement" not in prompt


def test_case_id_selection_is_stable_and_rejects_unknown_ids() -> None:
    fixtures = load_fixtures_from_file(FIXTURES)
    selected = [fixtures[4].case_id, fixtures[1].case_id]
    summary = evaluate_corpus(fixtures, FakeProvider(), case_ids=selected)
    assert [result.case_id for result in summary.case_results] == selected

    try:
        evaluate_corpus(fixtures, FakeProvider(), case_ids=["missing"])
    except ValueError as exc:
        assert "Unknown evaluation case IDs" in str(exc)
    else:
        raise AssertionError("unknown batch case must be rejected")
