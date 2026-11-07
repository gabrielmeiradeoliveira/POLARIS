"""Offline validation of the frozen GOAL25 A/B experiment harness."""

import json

from evaluations.goal25_runner import (
    MAX_ADDITIONAL_NVIDIA_REQUESTS,
    MAX_OUTPUT_TOKENS_PER_REQUEST,
    SAMPLE_CASE_IDS,
    frozen_sample,
    goal25_budget,
    goal25_live_budget,
    run_hybrid,
    run_static_only,
    safe_result,
    write_safe_result,
)
from pydantic import SecretStr

from polaris.providers.fake import FakeProvider
from polaris.providers.nvidia import NvidiaProvider
from polaris.quota.store import RequestStatus, UsageStore


def test_goal25_sample_is_fixed_stratified_and_direction_labeled() -> None:
    fixtures = frozen_sample()
    assert len(SAMPLE_CASE_IDS) == 12
    assert [fixture.case_id for fixture in fixtures] == list(SAMPLE_CASE_IDS)
    assert sum(bool(fixture.expected_findings) for fixture in fixtures) == 6
    assert sum(not fixture.expected_findings for fixture in fixtures) == 6
    assert any(case_id.startswith("g24-") for case_id in SAMPLE_CASE_IDS)
    assert any(case_id.startswith("psh-") for case_id in SAMPLE_CASE_IDS)


def test_goal25_budget_matches_approved_hard_limits() -> None:
    budget = goal25_budget()
    assert (budget.max_requests, budget.max_input_tokens, budget.max_output_tokens) == (60, 50_000, 20_000)
    assert (budget.max_input_tokens_per_request, budget.max_output_tokens_per_request) == (8_000, 2_000)
    assert (budget.request_timeout_seconds, budget.max_retries) == (90.0, 1)
    live_budget = goal25_live_budget()
    assert (live_budget.max_requests, live_budget.max_retries) == (MAX_ADDITIONAL_NVIDIA_REQUESTS, 0)
    assert live_budget.max_output_tokens_per_request == MAX_OUTPUT_TOKENS_PER_REQUEST
    assert live_budget.max_output_tokens >= MAX_ADDITIONAL_NVIDIA_REQUESTS * MAX_OUTPUT_TOKENS_PER_REQUEST


def test_static_and_controlled_hybrid_results_are_metrics_only() -> None:
    static = run_static_only()
    hybrid = run_hybrid(FakeProvider(scripted_responses=["{}"] * 12))
    payload = safe_result(hybrid, configuration="hybrid", provider="fake", model="test")
    assert static.dataset_size == hybrid.dataset_size == 12
    assert set(payload) == {"configuration", "provider", "model", "sample_case_ids", "preflight_requests_already_used", "summary", "cases"}
    assert all("content" not in case and "prompt" not in case for case in payload["cases"])


def test_goal25_hybrid_uses_provider_persistent_usage_store(tmp_path) -> None:
    store = UsageStore(db_path=tmp_path / "usage.sqlite3")
    previous = store.reserve(
        provider="nvidia",
        model="z-ai/glm-5.3-flash",
        quota_scope="previous-run",
        estimated_input_tokens=99,
        reserved_output_tokens=11,
    )
    store.reconcile(previous, status=RequestStatus.SUCCEEDED, input_tokens=99, output_tokens=11, is_estimated=False)
    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        usage_store=store,
        quota_scope="goal25-test",
        transport_fn=lambda *_: (
            200,
            {},
            json.dumps({"choices": [{"message": {"content": '{"findings": []}'}}], "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}}),
        ),
    )

    run_hybrid(provider)

    snapshot = store.get_snapshot(provider="nvidia", model=provider.model_name, quota_scope="goal25-test")
    assert (snapshot.succeeded_today, snapshot.input_tokens_today, snapshot.output_tokens_today) == (5, 50, 15)
    previous_snapshot = store.get_snapshot(provider="nvidia", model=provider.model_name, quota_scope="previous-run")
    assert (previous_snapshot.succeeded_today, previous_snapshot.input_tokens_today, previous_snapshot.output_tokens_today) == (1, 99, 11)


def test_metrics_result_persistence_rejects_sensitive_payloads(tmp_path) -> None:
    destination = tmp_path / "metrics.json"
    write_safe_result({"configuration": "static", "cases": []}, destination)
    assert destination.exists()
    try:
        write_safe_result({"prompt": "not permitted"}, destination)
    except ValueError as error:
        assert "forbidden" in str(error).lower()
    else:  # pragma: no cover - protects against accidental weakening.
        raise AssertionError("sensitive payload was persisted")
