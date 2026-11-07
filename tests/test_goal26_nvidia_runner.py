import json

import pytest
from evaluations.goal26_nvidia_runner import (
    ArmOutcome,
    ConservativeBudgetTracker,
    PayloadBoundProvider,
    campaign_budget,
    comparable_metrics,
    load_manifest,
    request_wire_payload_bytes,
    run_campaign,
    validate_manifest,
)

from polaris.core.errors import BudgetExceededError
from polaris.core.models import BudgetTracker, TokenUsage
from polaris.evaluation.models import CaseEvaluationResult
from polaris.providers.base import ProviderRequest
from polaris.providers.fake import FakeProvider


def test_nvidia_manifest_freezes_the_approved_campaign() -> None:
    manifest = load_manifest()
    fixtures = validate_manifest(manifest)
    assert manifest["external_execution_authorized"] is True
    assert manifest["model"] == "minimaxai/minimax-m3.1-flash"
    assert len(fixtures) == 20
    assert campaign_budget(manifest).model_dump(include={"max_requests", "max_total_tokens", "max_retries"}) == {
        "max_requests": 40,
        "max_total_tokens": 100_000,
        "max_retries": 0,
    }


def test_preventive_reservation_rejects_an_over_budget_request() -> None:
    tracker = BudgetTracker(campaign_budget(load_manifest()))
    with pytest.raises(BudgetExceededError, match="Token budget exceeded"):
        tracker.reserve_attempt(96_000, reserved_output_tokens=4_096, safety_margin_tokens=256)
    assert tracker.requests_made == 0


def test_conservative_tracker_ignores_low_estimates() -> None:
    tracker = ConservativeBudgetTracker(campaign_budget(load_manifest()), input_reservation_tokens=96_000)
    with pytest.raises(BudgetExceededError, match="Token budget exceeded"):
        tracker.reserve_attempt(1, reserved_output_tokens=4_096)
    assert tracker.requests_made == 0


def test_wire_payload_limit_counts_escaped_unicode_and_blocks_before_provider_call() -> None:
    request = ProviderRequest(system_prompt="sys", user_prompt="é" * 100, max_output_tokens=4_096)
    size = request_wire_payload_bytes(request, "test")
    assert size > len((request.system_prompt + request.user_prompt).encode("utf-8"))
    provider = FakeProvider()
    bounded = PayloadBoundProvider(provider, max_wire_payload_bytes=size - 1)
    with pytest.raises(BudgetExceededError, match="wire-payload"):
        bounded.generate(request)
    assert provider.requests == []


def test_reported_overage_and_interruption_consume_conservative_reservation() -> None:
    tracker = ConservativeBudgetTracker(campaign_budget(load_manifest()), input_reservation_tokens=96_000)
    reservation = tracker.reserve_attempt(1, reserved_output_tokens=3_000)
    with pytest.raises(BudgetExceededError, match="Token budget exceeded"):
        tracker.complete_attempt(reservation, TokenUsage(prompt_tokens=97_000, completion_tokens=3_001, total_tokens=100_001))

    interrupted = ConservativeBudgetTracker(campaign_budget(load_manifest()), input_reservation_tokens=1_000)
    provider = FakeProvider(scripted_responses=[TimeoutError("offline interruption")])
    bounded = PayloadBoundProvider(provider, max_wire_payload_bytes=16_000)
    bounded.bind_tracker(interrupted)
    with pytest.raises(TimeoutError, match="offline interruption"):
        bounded.generate(ProviderRequest(system_prompt="sys", user_prompt="user", max_output_tokens=64))
    assert interrupted.usage.prompt_tokens == 1_000


def test_comparative_metrics_excludes_incomplete_pairs() -> None:
    off = ArmOutcome("off", (CaseEvaluationResult(case_id="a", true_positives=1), CaseEvaluationResult(case_id="b")), None)
    on = ArmOutcome("on", (CaseEvaluationResult(case_id="a", true_positives=1), CaseEvaluationResult(case_id="b", status="failed")), None)
    assert comparable_metrics((off, on))["complete_pair_ids"] == ["a"]


def test_runner_refuses_existing_output_without_making_provider_calls(tmp_path) -> None:
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    provider = FakeProvider()
    with pytest.raises(FileExistsError):
        run_campaign(provider, output_dir)
    assert provider.requests == []


def test_manifest_is_json_without_credentials() -> None:
    serialized = json.dumps(load_manifest()).lower()
    assert "nvidia_api_key=" not in serialized
    assert '"authorization"' not in serialized


def test_comparative_metrics_excludes_missing_on_arm() -> None:
    off = ArmOutcome("off", (CaseEvaluationResult(case_id="only-off", true_positives=1),), None)
    metrics = comparable_metrics((off,))
    assert metrics["complete_pair_ids"] == []
    assert metrics["off"]["tp"] == 0
    assert metrics["on"]["tp"] == 0


def test_comparative_metrics_excludes_missing_on_case() -> None:
    off = ArmOutcome("off", (CaseEvaluationResult(case_id="a"), CaseEvaluationResult(case_id="b")), None)
    on = ArmOutcome("on", (CaseEvaluationResult(case_id="a"),), None)
    assert comparable_metrics((off, on))["complete_pair_ids"] == ["a"]


def test_resume_rejects_ambiguous_inflight_without_provider_calls(tmp_path) -> None:
    from evaluations.goal26_nvidia_runner import _write_partial

    manifest = load_manifest()
    output = tmp_path / "campaign"
    output.mkdir()
    tracker = BudgetTracker(campaign_budget(manifest))
    _write_partial(
        output / "results.json",
        manifest,
        [ArmOutcome("off", (), None), ArmOutcome("on", (), None)],
        tracker,
        in_flight={"case_id": manifest["case_order"][0], "arm": "off"},
    )
    provider = FakeProvider()
    with pytest.raises(RuntimeError, match="in-flight"):
        run_campaign(provider, output, manifest, resume=True)
    assert provider.requests == []


def test_resume_rejects_modified_manifest_without_provider_calls(tmp_path) -> None:
    from evaluations.goal26_nvidia_runner import _write_partial

    manifest = load_manifest()
    output = tmp_path / "campaign"
    output.mkdir()
    tracker = BudgetTracker(campaign_budget(manifest))
    _write_partial(
        output / "results.json",
        manifest,
        [ArmOutcome("off", (), None), ArmOutcome("on", (), None)],
        tracker,
    )
    changed = {**manifest, "goal": "changed"}
    provider = FakeProvider()
    with pytest.raises(ValueError, match="manifest mismatch"):
        run_campaign(provider, output, changed, resume=True)
    assert provider.requests == []


def test_resume_continues_completed_pairs_without_duplicate_requests_and_preserves_budget(tmp_path) -> None:
    import hashlib
    from evaluations.goal26_nvidia_runner import _write_partial

    manifest = load_manifest()
    fixtures = validate_manifest(manifest)
    assert fixtures[0].case_id == "e2e-ctx-01-return-contract-multiple-callers"

    subset_fixtures = [fixtures[0].model_dump(mode="json"), fixtures[1].model_dump(mode="json")]
    fixtures_file = tmp_path / "subset_fixtures.json"
    content = json.dumps(subset_fixtures).encode("utf-8")
    fixtures_file.write_bytes(content)
    manifest_subset = {
        **manifest,
        "fixtures": str(fixtures_file),
        "fixture_sha256": hashlib.sha256(content).hexdigest(),
        "case_order": [fixtures[0].case_id, fixtures[1].case_id],
    }

    output = tmp_path / "campaign"
    output.mkdir()
    tracker = BudgetTracker(campaign_budget(manifest_subset))
    initial_requests = 2
    initial_usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    tracker.requests_made = initial_requests
    tracker.usage = initial_usage

    case_0_off = CaseEvaluationResult(
        case_id=fixtures[0].case_id,
        status="completed",
        usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    )
    case_0_on = CaseEvaluationResult(
        case_id=fixtures[0].case_id,
        status="completed",
        usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    )
    checkpoint_outcomes = [
        ArmOutcome("off", (case_0_off,), None),
        ArmOutcome("on", (case_0_on,), None),
    ]
    _write_partial(output / "results.json", manifest_subset, checkpoint_outcomes, tracker)

    provider = FakeProvider()
    outcomes = run_campaign(provider, output, manifest_subset, resume=True)

    # Asserts that pair 0 is NOT re-requested (no duplicate requests for already completed pairs)
    assert len(provider.requests) == 2
    for request in provider.requests:
        assert fixtures[0].case_id not in request.user_prompt
        assert "auth/token.py" not in request.user_prompt

    # Asserts only the remaining fixture pair is requested
    assert [case.case_id for case in outcomes[0].cases] == [fixtures[0].case_id, fixtures[1].case_id]
    assert [case.case_id for case in outcomes[1].cases] == [fixtures[0].case_id, fixtures[1].case_id]

    # Asserts results.json preserves and accumulates requests_made and global_usage.total_tokens from checkpoint
    final_results = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert final_results["requests_made"] == initial_requests + 2
    assert final_results["global_usage"]["total_tokens"] > initial_usage.total_tokens
    assert final_results["comparative_metrics"]["complete_pair_ids"] == [
        fixtures[0].case_id,
        fixtures[1].case_id,
    ]
