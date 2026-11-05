"""Deterministic contracts for provider reliability controls and safe telemetry."""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest
from pydantic import SecretStr

import polaris.providers.nvidia as nvidia_module
from polaris.core.errors import BudgetExceededError, ProviderError
from polaris.core.models import BudgetTracker, ExecutionBudget, FindingCategory, LineRange, Severity, TokenUsage
from polaris.evaluation.models import EvaluationFixture, ExpectedFindingSpec
from polaris.evaluation.runner import evaluate_case, evaluate_corpus
from polaris.providers.base import ProviderRequest
from polaris.providers.nvidia import NvidiaProvider
from polaris.quota.store import RequestStatus, UsageStore


def _request() -> ProviderRequest:
    return ProviderRequest(system_prompt="system", user_prompt="user")


def _response(content: str = '{"findings": []}') -> str:
    return json.dumps(
        {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
        }
    )


def _fixture() -> EvaluationFixture:
    return EvaluationFixture(
        case_id="provider-reliability",
        description="provider reliability fixture",
        diff_text=(
            "diff --git a/sample.py b/sample.py\n"
            "--- a/sample.py\n"
            "+++ b/sample.py\n"
            "@@ -1 +1 @@\n"
            "-value = 0\n"
            "+value = 1\n"
        ),
        file_contents={"sample.py": "value = 1\n"},
    )


def test_separate_input_output_caps_are_reserved_before_transport() -> None:
    tracker = BudgetTracker(
        ExecutionBudget(
            max_requests=2,
            max_total_tokens=1_000,
            max_input_tokens=100,
            max_output_tokens=80,
            max_input_tokens_per_request=60,
            max_output_tokens_per_request=40,
        )
    )
    with pytest.raises(BudgetExceededError, match="Input token limit"):
        tracker.reserve_attempt(61, reserved_output_tokens=1)
    with pytest.raises(BudgetExceededError, match="Output token limit"):
        tracker.reserve_attempt(1, reserved_output_tokens=41)
    reservation = tracker.reserve_attempt(50, reserved_output_tokens=40)
    with pytest.raises(BudgetExceededError, match="Input token budget"):
        tracker.reserve_attempt(51, reserved_output_tokens=1)
    tracker.complete_attempt(reservation, TokenUsage(prompt_tokens=50, completion_tokens=40, total_tokens=90))


def test_missing_usage_failure_consumes_input_cap_and_blocks_retry() -> None:
    tracker = BudgetTracker(
        ExecutionBudget(max_requests=2, max_total_tokens=500, max_input_tokens=50, max_output_tokens=100)
    )
    reservation = tracker.reserve_attempt(50, reserved_output_tokens=10)
    tracker.fail_attempt(reservation, status=RequestStatus.UNCERTAIN, estimated_prompt_tokens=50)
    with pytest.raises(BudgetExceededError, match="Input token budget"):
        tracker.reserve_attempt(1, reserved_output_tokens=1)


def test_uncertain_attempt_keeps_full_persistent_reservation(tmp_path: Path) -> None:
    store = UsageStore(db_path=tmp_path / "usage.sqlite3")
    budget = ExecutionBudget(max_requests=2, max_total_tokens=100, max_input_tokens=50, max_output_tokens=40)
    tracker = BudgetTracker(budget, usage_store=store, provider_name="nvidia", model_name="test", quota_scope="scope")

    reservation = tracker.reserve_attempt(20, reserved_output_tokens=40)
    tracker.fail_attempt(reservation, status=RequestStatus.UNCERTAIN, estimated_prompt_tokens=20)

    snapshot = store.get_snapshot(provider="nvidia", model="test", quota_scope="scope")
    assert (snapshot.uncertain_today, snapshot.input_tokens_today, snapshot.output_tokens_today) == (1, 20, 40)
    with pytest.raises(BudgetExceededError, match="Output token budget"):
        tracker.reserve_attempt(1, reserved_output_tokens=1)


def test_attempt_deadline_is_passed_to_transport_and_success_telemetry_is_complete() -> None:
    timeouts: list[float] = []

    def transport(_request: object, timeout: float) -> tuple[int, dict[str, str], str]:
        timeouts.append(timeout)
        return 200, {}, _response()

    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        timeout_seconds=30.0,
        budget=ExecutionBudget(attempt_deadline_seconds=4.5, max_total_tokens=1000),
        transport_fn=transport,
    )
    response = provider.generate(_request())

    assert response.usage.total_tokens == 14
    assert timeouts == [4.5]
    attempt = provider.last_attempts[0]
    assert attempt.configured_attempt_timeout_seconds == 4.5
    assert attempt.termination_reason == "completed"
    assert attempt.transport_duration_ms is not None
    assert attempt.error_category is None


def test_retry_after_is_exact_without_jitter_and_jitter_is_only_for_fallback_backoff() -> None:
    sleeps: list[float] = []
    calls = 0

    def rate_then_success(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return 429, {"Retry-After": "2.5"}, "untrusted provider body"
        return 200, {}, _response()

    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        max_retries=1,
        jitter_ratio=1.0,
        random_fn=lambda: 0.9,
        sleep_fn=sleeps.append,
        transport_fn=rate_then_success,
    )
    provider.generate(_request())
    assert sleeps == [2.5]
    assert provider.last_attempts[0].retry_reason == "HTTP 429"

    fallback = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        initial_backoff_seconds=2.0,
        jitter_ratio=0.5,
        random_fn=lambda: 0.5,
        transport_fn=lambda *_: (200, {}, _response()),
    )
    assert fallback._compute_backoff(1, None) == 5.0

    default_sleeps: list[float] = []
    default_calls = 0

    def server_then_success(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal default_calls
        default_calls += 1
        return (503, {}, "untrusted") if default_calls == 1 else (200, {}, _response())

    default_provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        max_retries=1,
        sleep_fn=default_sleeps.append,
        transport_fn=server_then_success,
    )
    default_provider.generate(_request())
    assert default_sleeps == [1.0]


def test_transport_duration_excludes_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0]
    monkeypatch.setattr(nvidia_module.time, "perf_counter_ns", lambda: clock[0])
    calls = 0

    def transport(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal calls
        calls += 1
        clock[0] += 5_000_000
        return (503, {}, "untrusted") if calls == 1 else (200, {}, _response())

    def backoff(_seconds: float) -> None:
        clock[0] += 500_000_000

    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        max_retries=1,
        sleep_fn=backoff,
        transport_fn=transport,
    )
    provider.generate(_request())

    first_attempt = provider.last_attempts[0]
    assert first_attempt.transport_duration_ms == 5
    assert first_attempt.latency_ms == 505


def test_default_transport_closes_response_when_read_raises_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stdlib response context manager must close even when a socket read fails."""
    closed = []

    class FailingResponse:
        status = 200
        headers: dict[str, str] = {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            closed.append((exc_type, exc))
            return False

        def read(self) -> bytes:
            raise TimeoutError("local read timeout")

    monkeypatch.setattr(nvidia_module.urllib.request, "urlopen", lambda *_args, **_kwargs: FailingResponse())
    with pytest.raises(TimeoutError, match="local read timeout"):
        NvidiaProvider._default_transport(object(), 1.0)  # type: ignore[arg-type]
    assert closed and closed[0][0] is TimeoutError


def test_retry_is_limited_to_retryable_failures_and_invalid_json_is_classified() -> None:
    forbidden_calls = 0

    def bad_request(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal forbidden_calls
        forbidden_calls += 1
        return 400, {}, "sensitive failure body"

    client_error = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        max_retries=2,
        transport_fn=bad_request,
    )
    with pytest.raises(ProviderError, match=r"HTTP 400") as client_exc:
        client_error.generate(_request())
    assert forbidden_calls == 1
    assert client_exc.value.failure_category == "client_error"
    assert "sensitive failure body" not in str(client_exc.value)

    invalid = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        transport_fn=lambda *_: (200, {}, "not valid json"),
    )
    with pytest.raises(ProviderError, match="invalid JSON") as invalid_exc:
        invalid.generate(_request())
    assert invalid_exc.value.failure_category == "invalid_response"
    assert invalid.last_attempts[0].termination_reason == "invalid_response"


def test_timeout_and_connection_error_are_distinct_and_budgeted_attempts_are_visible() -> None:
    for error, category in (
        (TimeoutError("read timed out"), "timeout"),
        (urllib.error.URLError("name resolution failed"), "connection_error"),
    ):
        provider = NvidiaProvider(
            api_key=SecretStr("nvapi-testing-key"),
            max_retries=0,
            budget=ExecutionBudget(max_total_tokens=1000, max_requests=1),
            transport_fn=lambda *_args, exc=error: (_ for _ in ()).throw(exc),
        )
        with pytest.raises(ProviderError) as exc_info:
            provider.generate(_request())
        assert exc_info.value.failure_category == category
        assert provider.last_attempts[0].error_category.value == category
        assert provider.last_attempts[0].usage is None


def test_case_deadline_after_provider_response_is_explicit_operational_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter((0.0, 0.0, 2.0))
    monkeypatch.setattr("polaris.evaluation.runner.time.monotonic", lambda: next(ticks))
    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        transport_fn=lambda *_: (200, {}, _response()),
    )

    result = evaluate_case(
        _fixture(),
        provider,
        force_end_to_end=True,
        budget=ExecutionBudget(case_deadline_seconds=1.0, max_total_tokens=10_000),
        observability=True,
    )

    assert result.status == "budget_exhausted"
    assert result.operational_state == "budget_exhausted"
    assert result.error_category == "budget_exhausted"
    assert result.observability is not None
    assert result.observability.attempts is not None


def test_skipped_case_has_explicit_skipped_operational_state() -> None:
    skipped = _fixture().model_copy(update={"suitable_for_live_benchmark": False})
    provider = NvidiaProvider(api_key=SecretStr("nvapi-testing-key"), transport_fn=lambda *_: (200, {}, _response()))
    result = evaluate_case(skipped, provider, skip_unsuitable=True)
    assert result.status == "skipped"
    assert result.operational_state == "skipped"


def test_observable_failure_never_persists_secret_or_provider_body() -> None:
    secret = "nvapi-private-telemetry-secret"
    body = "provider response body must never persist"
    provider = NvidiaProvider(
        api_key=SecretStr(secret),
        transport_fn=lambda *_: (503, {}, f"{body} {secret}"),
    )

    summary = evaluate_corpus([_fixture()], provider, force_end_to_end=True, observability=True)
    result = summary.case_results[0]
    serialized = result.model_dump_json()

    assert result.operational_state == "provider_http_error"
    assert body not in serialized
    assert secret not in serialized
    assert result.observability is not None
    assert result.observability.attempts is not None
    assert result.observability.attempts[0].response_hash is None


def test_token_reservation_rejects_insufficient_prompt_and_minimum_response() -> None:
    prompt_too_large = BudgetTracker(ExecutionBudget(max_total_tokens=700))
    with pytest.raises(BudgetExceededError, match="insufficient reservation"):
        prompt_too_large.available_output_tokens(estimated_prompt_tokens=400, requested_output_tokens=4096)

    no_minimum_response = BudgetTracker(ExecutionBudget(max_total_tokens=320))
    with pytest.raises(BudgetExceededError, match="minimum output"):
        no_minimum_response.available_output_tokens(estimated_prompt_tokens=1, requested_output_tokens=4096)


def test_nvidia_provider_dynamically_caps_output_before_transport() -> None:
    payloads: list[dict[str, object]] = []

    def transport(req: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        payloads.append(json.loads(req.data.decode("utf-8")))  # type: ignore[attr-defined]
        return 200, {}, _response()

    budget = ExecutionBudget(max_total_tokens=1_000, max_requests=1)
    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        budget=budget,
        transport_fn=transport,
    )
    tracker = BudgetTracker(budget, provider_name="nvidia", model_name=provider.model_name)
    provider.bind_tracker(tracker)
    provider.generate(_request())
    provider.bind_tracker(None)

    # Prompt estimate is three tokens; 256 safety tokens leave 741 for output.
    assert payloads[0]["max_tokens"] == 741
    assert tracker.requests_made == 1


def test_successive_attempts_and_retries_recompute_reserved_output() -> None:
    payloads: list[dict[str, object]] = []
    calls = 0

    def transport(req: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal calls
        calls += 1
        payloads.append(json.loads(req.data.decode("utf-8")))  # type: ignore[attr-defined]
        if calls == 1:
            return 429, {}, "rate limited"
        return 200, {}, _response()

    budget = ExecutionBudget(max_total_tokens=1_000, max_requests=2, max_retries=1)
    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        budget=budget,
        sleep_fn=lambda _: None,
        transport_fn=transport,
    )
    tracker = BudgetTracker(budget, provider_name="nvidia", model_name=provider.model_name)
    provider.bind_tracker(tracker)
    provider.generate(_request())
    provider.bind_tracker(None)

    assert tracker.requests_made == 2
    assert tracker.retries_performed == 1
    assert payloads[0]["max_tokens"] == 741
    # The failed attempt conservatively consumed its estimated two prompt tokens.
    assert payloads[1]["max_tokens"] == 738


def test_successive_completed_calls_recompute_output_from_actual_usage() -> None:
    payloads: list[dict[str, object]] = []

    def transport(req: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        payloads.append(json.loads(req.data.decode("utf-8")))  # type: ignore[attr-defined]
        return 200, {}, json.dumps(
            {
                "choices": [{"message": {"content": '{"findings": []}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
            }
        )

    budget = ExecutionBudget(max_total_tokens=1_000, max_requests=2)
    provider = NvidiaProvider(api_key=SecretStr("nvapi-testing-key"), budget=budget, transport_fn=transport)
    tracker = BudgetTracker(budget, provider_name="nvidia", model_name=provider.model_name)
    provider.bind_tracker(tracker)
    provider.generate(_request())
    provider.generate(_request())
    provider.bind_tracker(None)

    assert tracker.usage.total_tokens == 400
    assert payloads[0]["max_tokens"] == 741
    assert payloads[1]["max_tokens"] == 541


def test_retry_is_blocked_when_first_attempt_consumes_minimum_reservation() -> None:
    calls = 0

    def transport(_req: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal calls
        calls += 1
        return 429, {}, "rate limited"

    # Three estimated prompt tokens + 256 margin + 64 minimum output permits
    # exactly one attempt. Its conservative failed-attempt prompt charge then
    # leaves too little for a retry.
    budget = ExecutionBudget(max_total_tokens=323, max_requests=2, max_retries=1)
    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        budget=budget,
        sleep_fn=lambda _: None,
        transport_fn=transport,
    )
    tracker = BudgetTracker(budget, provider_name="nvidia", model_name=provider.model_name)
    provider.bind_tracker(tracker)
    with pytest.raises(BudgetExceededError, match="insufficient reservation"):
        provider.generate(_request())
    provider.bind_tracker(None)

    assert calls == 1
    assert tracker.requests_made == 1
    assert tracker.retries_performed == 0


def test_reported_usage_over_reservation_is_accounted_and_stops_budget() -> None:
    def transport(_req: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        return (
            200,
            {},
            json.dumps(
                {
                    "choices": [{"message": {"content": '{"findings": []}'}}],
                    "usage": {"prompt_tokens": 900, "completion_tokens": 200, "total_tokens": 1_100},
                }
            ),
        )

    budget = ExecutionBudget(max_total_tokens=1_000, max_requests=2)
    provider = NvidiaProvider(api_key=SecretStr("nvapi-testing-key"), budget=budget, transport_fn=transport)
    tracker = BudgetTracker(budget, provider_name="nvidia", model_name=provider.model_name)
    provider.bind_tracker(tracker)
    with pytest.raises(BudgetExceededError, match="used 1100 tokens"):
        provider.generate(_request())
    provider.bind_tracker(None)
    assert tracker.usage.total_tokens == 1_100
    with pytest.raises(BudgetExceededError):
        tracker.available_output_tokens(estimated_prompt_tokens=1, requested_output_tokens=64)


def test_missing_usage_keeps_pre_send_reservation_and_uses_estimate(tmp_path: Path) -> None:
    payloads: list[dict[str, object]] = []
    store = UsageStore(db_path=tmp_path / "usage.sqlite3")
    observed_reservations: list[tuple[int, int, int, int]] = []

    def transport(req: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        payloads.append(json.loads(req.data.decode("utf-8")))  # type: ignore[attr-defined]
        snapshot = store.get_snapshot(provider="nvidia", model="test", quota_scope="missing-usage")
        observed_reservations.append(
            (snapshot.active_reservations_today, snapshot.input_tokens_today, snapshot.output_tokens_today, snapshot.total_tokens_today)
        )
        return 200, {}, json.dumps({"choices": [{"message": {"content": '{"findings": []}'}}]})

    budget = ExecutionBudget(max_total_tokens=1_000, max_requests=1)
    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        model_name="test",
        budget=budget,
        usage_store=store,
        quota_scope="missing-usage",
        transport_fn=transport,
    )
    tracker = BudgetTracker(budget, usage_store=store, provider_name="nvidia", model_name=provider.model_name, quota_scope="missing-usage")
    provider.bind_tracker(tracker)
    response = provider.generate(_request())
    provider.bind_tracker(None)

    assert payloads[0]["max_tokens"] == 741
    assert observed_reservations == [(1, 259, 741, 1_000)]
    assert response.usage.is_estimated is True
    assert response.usage.total_tokens <= budget.max_total_tokens


def test_individual_caps_block_before_transport() -> None:
    calls: list[int] = []

    def transport(_req: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        calls.append(1)
        return 200, {}, _response()

    input_limited = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        budget=ExecutionBudget(max_total_tokens=1_000, max_input_tokens_per_request=2),
        transport_fn=transport,
    )
    with pytest.raises(BudgetExceededError, match="Input token limit"):
        input_limited.generate(_request())

    output_limited = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        budget=ExecutionBudget(max_total_tokens=1_000, max_output_tokens=63),
        transport_fn=transport,
    )
    with pytest.raises(BudgetExceededError, match="Output token budget"):
        output_limited.generate(_request())

    request_budget = ExecutionBudget(max_total_tokens=1_000, max_requests=1)
    request_limited = NvidiaProvider(api_key=SecretStr("nvapi-testing-key"), budget=request_budget, transport_fn=transport)
    tracker = BudgetTracker(request_budget, provider_name="nvidia", model_name=request_limited.model_name)
    request_limited.bind_tracker(tracker)
    request_limited.generate(_request())
    with pytest.raises(BudgetExceededError, match="request budget"):
        request_limited.generate(_request())
    request_limited.bind_tracker(None)

    assert len(calls) == 1


def test_local_transport_baseline_and_reliability_controls_preserve_outcomes() -> None:
    """Compare deterministic local contracts only; this is not an NVIDIA reliability simulation."""
    finding_response = _response(
        json.dumps(
            {
                "findings": [
                    {
                        "category": "logic_error",
                        "severity": "medium",
                        "confidence": "high",
                        "file_path": "sample.py",
                        "start_line": 1,
                        "end_line": 1,
                        "title": "Incorrect value assignment",
                        "description": "The changed assignment produces the wrong value for callers.",
                        "evidence": "value = 1",
                    }
                ]
            }
        )
    )
    fixture = _fixture().model_copy(
        update={
            "expected_findings": [
                ExpectedFindingSpec(
                    file_path="sample.py",
                    line_range=LineRange(start_line=1, end_line=1),
                    category=FindingCategory.LOGIC_ERROR,
                    severity=Severity.MEDIUM,
                )
            ]
        }
    )
    baseline_timeouts: list[float] = []
    controlled_timeouts: list[float] = []
    baseline = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        timeout_seconds=30.0,
        transport_fn=lambda _request, timeout: (baseline_timeouts.append(timeout) or (200, {}, finding_response)),
    )
    controlled = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        timeout_seconds=30.0,
        budget=ExecutionBudget(attempt_deadline_seconds=4.5, max_total_tokens=10_000),
        transport_fn=lambda _request, timeout: (controlled_timeouts.append(timeout) or (200, {}, finding_response)),
    )

    baseline_result = evaluate_case(fixture, baseline, force_end_to_end=True)
    controlled_result = evaluate_case(
        fixture,
        controlled,
        force_end_to_end=True,
        budget=ExecutionBudget(attempt_deadline_seconds=4.5, max_total_tokens=10_000),
    )

    assert (controlled_result.status, controlled_result.true_positives, controlled_result.false_positives) == (
        baseline_result.status,
        baseline_result.true_positives,
        baseline_result.false_positives,
    )
    assert baseline_timeouts == [30.0]
    assert controlled_timeouts == [4.5]

    failure_calls = 0

    def local_timeout(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal failure_calls
        failure_calls += 1
        raise TimeoutError("local deterministic timeout")

    failed = evaluate_case(
        _fixture(),
        NvidiaProvider(
            api_key=SecretStr("nvapi-testing-key"),
            max_retries=1,
            sleep_fn=lambda _seconds: None,
            transport_fn=local_timeout,
        ),
        force_end_to_end=True,
    )
    assert failure_calls == 2
    assert failed.status == "failed"
    assert failed.operational_state == "provider_timeout"
